import re
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
from urllib.parse import urljoin

router = APIRouter()


# -------------------- Data Extraction -------------------- #
def extract_website_data(url: str) -> dict:
    """
    Extracts text, images, and videos from a given website URL.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return {"error": f"Failed to fetch URL (status {response.status_code})"}

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = soup.title.string.strip() if soup.title else "No title"

        # Extract main text content
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        content = "\n\n".join(paragraphs[:20])  # limit to 20 paragraphs for brevity

        # Extract images (absolute URLs)
        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                images.append(urljoin(url, src))

        # Extract video links (mp4, YouTube embeds, etc.)
        videos = []
        for video in soup.find_all("video"):
            src = video.get("src")
            if src:
                videos.append(urljoin(url, src))
            for source in video.find_all("source"):
                src = source.get("src")
                if src:
                    videos.append(urljoin(url, src))

        # YouTube/Vimeo embeds
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src")
            if src and any(x in src for x in ["youtube.com", "youtu.be", "vimeo.com"]):
                videos.append(src)

        return {
            "platform": "Website",
            "title": title,
            "content": content.strip(),
            "images": images,
            "videos": videos
        }

    except Exception as e:
        return {"error": f"An error occurred while fetching website: {e}"}


# -------------------- FastAPI Routes -------------------- #
class WebsiteRequest(BaseModel):
    url: str


@router.post("/extract")
def website_extract(req: WebsiteRequest):
    url = req.url.strip()
    if not url or not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="Please provide a valid website link (http/https).")

    result = extract_website_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
