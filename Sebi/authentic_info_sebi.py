import os
import hashlib
import time
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from playwright.sync_api import sync_playwright
from pinecone import Pinecone, ServerlessSpec
from pinecone.core.openapi.shared.exceptions import ServiceException


# Load keys
load_dotenv()
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME')

SEBI_URL = "https://www.sebi.gov.in"
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
MAX_DEPTH = 2  # Maximum crawling depth (0 = main page only, 1 = main + first level, etc.)
MAX_PAGES = 500  # Maximum number of pages to process to avoid infinite crawling


def delete_index_if_exists(pc, index_name):
    existing_indexes = [x.name for x in pc.list_indexes()]
    if index_name in existing_indexes:
        print(f"Deleting existing index: {index_name}")
        pc.delete_index(index_name)
        time.sleep(2)  # Wait to ensure deletion completes
    else:
        print(f"Index '{index_name}' does not exist, no deletion needed.")


def create_index_if_missing(pc, index_name):
    existing_indexes = [x.name for x in pc.list_indexes()]
    if index_name not in existing_indexes:
        print(f"Creating index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(2)  # Wait for index readiness
    else:
        print(f"Index '{index_name}' already exists.")


def extract_hrefs_from_page(page, url):
    """Extract all SEBI internal links from a given page"""
    try:
        page.goto(url, timeout=30000)
        content = page.content()
    except Exception as e:
        print(f"Failed to load {url}: {e}")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    hrefs = set()
    for tag in soup.find_all('a', href=True):
        href = urljoin(url, tag['href'])
        if urlparse(href).netloc.endswith("sebi.gov.in"):
            # Normalize URL to remove fragments and query parameters
            parsed_url = urlparse(href)
            normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            hrefs.add(normalized_url)
    return list(hrefs)


def crawl_sebi_links_recursive(page, start_url, max_depth=2, max_pages=500):
    """Recursively crawl SEBI website to discover all internal links"""
    discovered_urls = set()
    urls_to_process = [(start_url, 0)]  # (url, depth)
    processed_urls = set()
    
    print(f"Starting recursive crawl with max depth: {max_depth}, max pages: {max_pages}")
    
    with tqdm(desc="Discovering links", unit="pages") as pbar:
        while urls_to_process and len(discovered_urls) < max_pages:
            current_url, current_depth = urls_to_process.pop(0)
            
            # Skip if already processed or depth exceeded
            if current_url in processed_urls or current_depth > max_depth:
                continue
                
            processed_urls.add(current_url)
            discovered_urls.add(current_url)
            pbar.update(1)
            pbar.set_postfix({"Depth": current_depth, "Found": len(discovered_urls)})
            
            # Extract links from current page if we haven't reached max depth
            if current_depth < max_depth:
                try:
                    new_hrefs = extract_hrefs_from_page(page, current_url)
                    for href in new_hrefs:
                        if href not in processed_urls and href not in [url for url, _ in urls_to_process]:
                            urls_to_process.append((href, current_depth + 1))
                except Exception as e:
                    print(f"Error extracting links from {current_url}: {e}")
                    continue
                
                # Small delay to be respectful to the server
                time.sleep(0.5)
    
    print(f"Crawl completed. Discovered {len(discovered_urls)} unique URLs across {len(processed_urls)} processed pages.")
    return list(discovered_urls)


def fetch_and_extract_blocks(page, url):
    try:
        page.goto(url, timeout=20000)
        html = page.content()
    except Exception as e:
        print(f"Failed to load {url}: {e}")
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
    blocks = [b for b in set(blocks) if len(b.split()) > 10]
    return blocks


def embed_and_store(index, embedding_model, url, blocks, max_retries=3):
    vectors = []
    for i, block in enumerate(blocks):
        emb = embedding_model.encode(block).tolist()
        meta = {"text": block, "source_url": url}
        vector_id = hashlib.md5(f"{url}-{i}".encode()).hexdigest()
        vectors.append((vector_id, emb, meta))

    if not vectors:
        return

    for attempt in range(1, max_retries + 1):
        try:
            index.upsert(vectors)
            break
        except ServiceException as e:
            print(f"Pinecone ServiceException on upsert attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(3)
            else:
                print("Max retries exceeded. Skipping this batch.")
        except Exception as e:
            print(f"Unexpected exception during upsert: {e}")
            break


def main():
    # Initialize Pinecone client
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Delete existing index if any
    delete_index_if_exists(pc, PINECONE_INDEX_NAME)

    # Create index fresh
    create_index_if_missing(pc, PINECONE_INDEX_NAME)

    # Index handle and embedding model init
    index = pc.Index(PINECONE_INDEX_NAME)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Perform recursive link discovery starting from SEBI main page
        all_urls = crawl_sebi_links_recursive(page, SEBI_URL, MAX_DEPTH, MAX_PAGES)
        
        print(f"Starting content extraction from {len(all_urls)} discovered URLs...")

        # Process each discovered URL with progress bar
        successful_extractions = 0
        failed_extractions = 0
        
        for url in tqdm(all_urls, desc="Extracting content"):
            try:
                blocks = fetch_and_extract_blocks(page, url)
                if blocks:
                    embed_and_store(index, embedding_model, url, blocks)
                    successful_extractions += 1
                else:
                    print(f"No content blocks found for: {url}")
                    
            except Exception as e:
                print(f"Error processing '{url}': {e}")
                failed_extractions += 1
                continue
                
            # Small delay between requests
            time.sleep(0.2)

        browser.close()
        
    print(f"\nScraping completed!")
    print(f"Successfully processed: {successful_extractions} pages")
    print(f"Failed to process: {failed_extractions} pages")
    print(f"Total URLs discovered: {len(all_urls)}")
    print("SEBI contextual blocks stored in Pinecone.")


if __name__ == "__main__":
    main()