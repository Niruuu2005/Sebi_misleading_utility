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
def get_linkedin_data(url: str) -> dict:
    """
    Scrapes a public LinkedIn post to gather its content. This is useful
    for identifying fake advisors or fraudulent corporate announcements.
    Note: Scraping LinkedIn is challenging and may be unreliable on non-public posts.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"error": f"Failed to fetch LinkedIn data: HTTP {response.status_code}"}

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract post title from the page's title tag
        title = "LinkedIn Post"
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Attempt to find the main post content. These selectors are subject to change by LinkedIn.
        post_text = "Could not automatically extract post content."
        post_selectors = [
            '.feed-shared-update-v2__description-wrapper',
            '.feed-shared-text',
            '.show-more-less-html__markup'
        ]

        for selector in post_selectors:
            element = soup.select_one(selector)
            if element:
                post_text = element.get_text(strip=True)
                break

        full_content = f"Title: {title}\n\nPlatform: LinkedIn\n\n--- Post Content ---\n\n{post_text}"

        return {
            "platform": "LinkedIn",
            "title": title,
            "content": full_content.strip()
        }

    except Exception as e:
        return {"error": f"An error occurred while scraping LinkedIn: {e}"}


# -------------------- FastAPI Routes -------------------- #
class LinkedInRequest(BaseModel):
    url: str


@router.post("/extract")
def linkedin_extract(req: LinkedInRequest):
    url = req.url.strip()
    if not url or "linkedin.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid LinkedIn link.")

    result = get_linkedin_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result