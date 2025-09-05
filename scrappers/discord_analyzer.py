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
def get_discord_data(url: str) -> dict:
    """
    Scrapes a public Discord invite page to gather server information. This is
    useful for monitoring communities for stock tip fraud or pump-and-dump schemes.
    Note: Full message history is not available without authentication.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {"error": f"Failed to fetch Discord data: HTTP {response.status_code}"}

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract server name from the page title or meta tags
        title = "Discord Server"
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
        # Publicly visible messages are rare, so we provide a default note.
        messages_content = "No public messages found. Full server access requires authentication and joining the server."

        full_content = f"Title: {title}\n\nPlatform: Discord\n\n--- Server Info ---\n\n{messages_content}"

        return {
            "platform": "Discord",
            "title": title,
            "content": full_content.strip()
        }

    except Exception as e:
        return {"error": f"An error occurred while scraping Discord: {e}"}


# -------------------- FastAPI Routes -------------------- #
class DiscordRequest(BaseModel):
    url: str


@router.post("/extract")
def discord_extract(req: DiscordRequest):
    url = req.url.strip()
    if not url or "discord.com" not in url and "discord.gg" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Discord link.")

    result = get_discord_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result