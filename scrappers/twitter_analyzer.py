import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# -------------------- Web Scraper Client -------------------- #
# Note: No specific client initialization is needed.
# We use the 'requests' library directly for web scraping.
print("✅ Requests and BeautifulSoup are ready for web scraping.")


# -------------------- Data Extraction -------------------- #
def get_twitter_data(url: str) -> dict:
    """
    Scrapes a public Twitter/X post to gather its content. This is useful
    for tracking fraudulent investment advice, fake profiles, or misinformation.
    Note: Scraping Twitter can be unreliable due to frequent HTML structure changes.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"error": f"Failed to fetch Twitter/X data: HTTP {response.status_code}"}

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract post title from the page's title tag
        title = "Twitter/X Post"
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Attempt to find the main tweet content. These selectors are subject to change by Twitter.
        tweet_text = "Could not automatically extract tweet content."
        tweet_selectors = [
            'div[data-testid="tweetText"]',
            'article div[lang]'
        ]

        for selector in tweet_selectors:
            element = soup.select_one(selector)
            if element:
                tweet_text = element.get_text(strip=True)
                break

        full_content = f"Title: {title}\n\nPlatform: Twitter/X\n\n--- Post Content ---\n\n{tweet_text}"

        return {
            "platform": "Twitter",
            "title": title,
            "content": full_content.strip()
        }

    except Exception as e:
        return {"error": f"An error occurred while scraping Twitter/X: {e}"}


# -------------------- FastAPI Routes -------------------- #
class TwitterRequest(BaseModel):
    url: str


@router.post("/extract")
def twitter_extract(req: TwitterRequest):
    url = req.url.strip()
    if not url or ("twitter.com" not in url and "x.com" not in url):
        raise HTTPException(status_code=400, detail="Please provide a valid Twitter or X.com link.")

    result = get_twitter_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result