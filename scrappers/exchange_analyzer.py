import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# -------------------- Web Scraper Client -------------------- #
# Note: No client initialization is needed.
# We use the 'requests' library directly for scraping.
print("✅ Requests and BeautifulSoup ready for web scraping.")


# -------------------- Data Extraction -------------------- #
def get_bse_nse_data(url: str) -> dict:
    """
    Scrapes BSE/NSE announcements for fraud detection by cross-verifying
    corporate announcements against claims made on social media.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"error": f"Failed to fetch exchange data: HTTP {response.status_code}"}

        soup = BeautifulSoup(response.content, 'html.parser')

        title = "Exchange Announcement"
        announcement_content = "No announcement content found"

        # Define platform and content selectors based on URL
        if "bseindia.com" in url:
            platform = "BSE"
            content_selectors = [
                '.card-body', '.announcement-content', '.content-area',
                'table tr td', '.table-responsive'
            ]
        elif "nseindia.com" in url:
            platform = "NSE"
            content_selectors = [
                '.content-section', '.announcement-details', 'table tbody tr',
                '.data-table', '.corporate-announcement'
            ]
        else:
            # Fallback for unknown exchange platforms
            platform = "Exchange"
            content_selectors = [
                '.announcement', '.content', 'table', '.news-content'
            ]

        # Attempt to extract content using the selectors
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                texts = []
                for elem in elements[:5]:  # Get a few relevant blocks of text
                    text = elem.get_text().strip()
                    if text and len(text) > 25: # Filter out empty or very short strings
                        texts.append(text)
                if texts:
                    announcement_content = '\n\n'.join(texts)
                    break

        if soup.title:
            title = soup.title.get_text().strip()

        full_content = f"Title: {title}\n\nPlatform: {platform}\n\n--- Announcement ---\n\n{announcement_content}"

        return {
            "platform": platform,
            "title": title,
            "content": full_content.strip()
        }

    except Exception as e:
        return {"error": f"An error occurred while scraping exchange data: {e}"}


# -------------------- FastAPI Routes -------------------- #
class ExchangeRequest(BaseModel):
    url: str


@router.post("/extract")
def exchange_extract(req: ExchangeRequest):
    url = req.url.strip()
    if not url or ("bseindia.com" not in url and "nseindia.com" not in url):
        raise HTTPException(status_code=400, detail="Please provide a valid BSE or NSE link.")

    result = get_bse_nse_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result