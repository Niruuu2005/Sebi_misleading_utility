import os
import hashlib
import time
import json
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque

from dotenv import load_dotenv
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from playwright.sync_api import sync_playwright
from pinecone import Pinecone, ServerlessSpec
from pinecone.core.openapi.shared.exceptions import ServiceException

# Load Pinecone keys and config from environment
load_dotenv()
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME_CHITORGARH')

# Constants for scraping
CHITTORGARH_URL = "https://www.chittorgarh.com"
CHITTORGARH_DOMAIN = "chittorgarh.com"
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

# File paths for persistence
SCRAPED_URLS_FILE = "scraped_urls.json"
LOG_FILE = "chittorgarh_scraper.log"


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def load_scraped_urls():
    """Load previously scraped URLs from file"""
    if os.path.exists(SCRAPED_URLS_FILE):
        try:
            with open(SCRAPED_URLS_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('scraped_urls', [])), data.get('last_scrape_time', '')
        except Exception as e:
            logging.error(f"Error loading scraped URLs: {e}")
            return set(), ''
    return set(), ''


def save_scraped_urls(scraped_urls, start_time):
    """Save scraped URLs to file"""
    try:
        data = {
            'scraped_urls': list(scraped_urls),
            'last_scrape_time': start_time,
            'total_urls': len(scraped_urls)
        }
        with open(SCRAPED_URLS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logging.debug(f"Saved {len(scraped_urls)} URLs to {SCRAPED_URLS_FILE}")
    except Exception as e:
        logging.error(f"Error saving scraped URLs: {e}")


def append_scraped_url(url, start_time):
    """Quickly append a single URL to the scraped URLs file"""
    try:
        # Load existing data
        if os.path.exists(SCRAPED_URLS_FILE):
            with open(SCRAPED_URLS_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {'scraped_urls': [], 'last_scrape_time': start_time, 'total_urls': 0}
        
        # Append new URL if not already present
        if url not in data['scraped_urls']:
            data['scraped_urls'].append(url)
            data['total_urls'] = len(data['scraped_urls'])
            data['last_scrape_time'] = start_time
            
            # Write back to file
            with open(SCRAPED_URLS_FILE, 'w') as f:
                json.dump(data, f, separators=(',', ':'))  # Compact format for speed
                
    except Exception as e:
        logging.error(f"Error appending scraped URL {url}: {e}")


def get_user_choice():
    """Get user choice for continuing or starting fresh"""
    if os.path.exists(SCRAPED_URLS_FILE):
        scraped_urls, last_time = load_scraped_urls()
        if scraped_urls:
            print(f"\n{'='*60}")
            print(f"Previous scraping session found:")
            print(f"- Last scrape time: {last_time}")
            print(f"- URLs already scraped: {len(scraped_urls)}")
            print(f"{'='*60}")
            
            while True:
                choice = input("\nDo you want to continue from the last scrape? (y/n): ").lower().strip()
                if choice in ['y', 'yes']:
                    logging.info("User chose to continue from last scrape")
                    return 'continue', scraped_urls
                elif choice in ['n', 'no']:
                    logging.info("User chose to start fresh")
                    return 'fresh', set()
                else:
                    print("Please enter 'y' or 'n'")
    
    logging.info("No previous scraping session found, starting fresh")
    return 'fresh', set()


def delete_index_if_exists(pc, index_name):
    """Delete Pinecone index if it exists"""
    existing_indexes = [x.name for x in pc.list_indexes()]
    if index_name in existing_indexes:
        logging.info(f"Deleting existing index: {index_name}")
        pc.delete_index(index_name)
        time.sleep(2)
    else:
        logging.info(f"Index '{index_name}' does not exist, no deletion needed.")


def create_index_if_missing(pc, index_name):
    """Create Pinecone index if it doesn't exist"""
    existing_indexes = [x.name for x in pc.list_indexes()]
    if index_name not in existing_indexes:
        logging.info(f"Creating index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=384,  # embedding dimension for all-MiniLM-L6-v2
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(2)
    else:
        logging.info(f"Index '{index_name}' already exists.")


def extract_chittorgarh_hrefs(page, base_url):
    """Extract all Chittorgarh internal links from a page"""
    try:
        page.goto(base_url, timeout=30000)
        content = page.content()
        logging.debug(f"Successfully loaded content from: {base_url}")
    except Exception as e:
        logging.error(f"Failed to load {base_url}: {e}")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    hrefs = set()
    for tag in soup.find_all('a', href=True):
        href = urljoin(base_url, tag['href'])
        if urlparse(href).netloc.endswith(CHITTORGARH_DOMAIN):
            href_no_fragment = urlparse(href)._replace(fragment="").geturl()
            hrefs.add(href_no_fragment)
    
    logging.debug(f"Found {len(hrefs)} links on {base_url}")
    return list(hrefs)


def fetch_and_extract_blocks(page, url):
    """Extract text blocks from a webpage"""
    try:
        page.goto(url, timeout=20000)
        html = page.content()
        logging.debug(f"Successfully fetched content from: {url}")
    except Exception as e:
        logging.error(f"Failed to load {url}: {e}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    blocks, current = [], []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
        if tag.name.startswith('h') and current:
            blocks.append(' '.join(current))
            current = []
        txt = tag.get_text(strip=True)
        if txt:
            current.append(txt)
    if current:
        blocks.append(' '.join(current))
    
    # Filter blocks with more than 10 words
    blocks = [b for b in set(blocks) if len(b.split()) > 10]
    logging.debug(f"Extracted {len(blocks)} content blocks from {url}")
    return blocks


def embed_and_store(index, embedding_model, url, blocks, max_retries=3):
    """Create embeddings and store in Pinecone"""
    vectors = []
    for i, block in enumerate(blocks):
        emb = embedding_model.encode(block).tolist()
        meta = {"text": block, "source_url": url}
        vector_id = hashlib.md5(f"{url}-{i}".encode()).hexdigest()
        vectors.append((vector_id, emb, meta))

    if not vectors:
        logging.warning(f"No vectors to store for {url}")
        return

    for attempt in range(1, max_retries + 1):
        try:
            index.upsert(vectors)
            logging.debug(f"Successfully stored {len(vectors)} vectors for {url}")
            break
        except ServiceException as e:
            logging.error(f"Pinecone ServiceException on upsert attempt {attempt} for {url}: {e}")
            if attempt < max_retries:
                time.sleep(3)
            else:
                logging.error(f"Max retries exceeded for {url}. Skipping this batch.")
        except Exception as e:
            logging.error(f"Unexpected exception during upsert for {url}: {e}")
            break


def main():
    # Setup logging
    logger = setup_logging()
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info("="*60)
    logger.info("Starting Chittorgarh scraper")
    logger.info(f"Start time: {start_time}")
    logger.info("="*60)
    
    # Get user choice and load previous state
    choice, previously_scraped = get_user_choice()
    
    # Initialize Pinecone client
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Handle index deletion based on user choice
    if choice == 'fresh':
        # Truncate the scraped URLs file
        if os.path.exists(SCRAPED_URLS_FILE):
            os.remove(SCRAPED_URLS_FILE)
            logger.info("Removed previous scraped URLs file")
        
        # Delete and recreate index
        delete_index_if_exists(pc, PINECONE_INDEX_NAME)
        previously_scraped = set()
    
    # Create index if needed
    create_index_if_missing(pc, PINECONE_INDEX_NAME)
    
    # Initialize index handle and embedding model
    index = pc.Index(PINECONE_INDEX_NAME)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    # Statistics tracking
    stats = {
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'new_urls_found': 0
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        queue = deque([CHITTORGARH_URL])
        visited = set(previously_scraped)  # Initialize with previously scraped URLs
        newly_scraped = set()
        
        logger.info(f"Starting with {len(visited)} previously scraped URLs")
        logger.info(f"Queue initialized with base URL: {CHITTORGARH_URL}")
        
        while queue:
            current_url = queue.popleft()
            
            # Skip if already processed
            if current_url in visited:
                stats['skipped'] += 1
                continue

            visited.add(current_url)
            newly_scraped.add(current_url)
            stats['processed'] += 1
            
            logger.info(f"Processing URL [{stats['processed']}]: {current_url}")

            try:
                page = browser.new_page()

                # Extract content blocks
                blocks = fetch_and_extract_blocks(page, current_url)
                if blocks:
                    embed_and_store(index, embedding_model, current_url, blocks)
                    stats['successful'] += 1
                    logger.info(f"Successfully processed {current_url} - {len(blocks)} blocks")
                    
                    # Immediately save this URL to file after successful processing
                    append_scraped_url(current_url, start_time)
                    
                else:
                    logger.warning(f"No content blocks found for {current_url}")
                    # Still save URL even if no blocks found (to avoid reprocessing)
                    append_scraped_url(current_url, start_time)

                # Extract new links
                hrefs = extract_chittorgarh_hrefs(page, current_url)
                new_hrefs_count = 0
                for href in hrefs:
                    if href not in visited:
                        queue.append(href)
                        new_hrefs_count += 1
                
                stats['new_urls_found'] += new_hrefs_count
                logger.debug(f"Added {new_hrefs_count} new URLs to queue from {current_url}")

                page.close()
                
                # Log progress every 10 URLs (but don't do full file rewrite)
                if stats['processed'] % 10 == 0:
                    logger.info(f"Progress update - Processed: {stats['processed']}, Queue size: {len(queue)}, Success rate: {stats['successful']}/{stats['processed']}")

            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Error processing {current_url}: {e}")
                # Still save failed URL to avoid reprocessing
                append_scraped_url(current_url, start_time)
                continue

        browser.close()

    # Final comprehensive save (ensures data integrity)
    save_scraped_urls(visited, start_time)
    
    # Print final statistics
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("="*60)
    logger.info("Scraping completed!")
    logger.info(f"Start time: {start_time}")
    logger.info(f"End time: {end_time}")
    logger.info(f"Total URLs processed: {stats['processed']}")
    logger.info(f"Successfully processed: {stats['successful']}")
    logger.info(f"Failed to process: {stats['failed']}")
    logger.info(f"Skipped (already processed): {stats['skipped']}")
    logger.info(f"New URLs discovered: {stats['new_urls_found']}")
    logger.info(f"Total unique URLs in database: {len(visited)}")
    logger.info("All relevant Chittorgarh contextual blocks stored in Pinecone.")
    logger.info("="*60)


if __name__ == "__main__":
    main()