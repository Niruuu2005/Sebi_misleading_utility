import re
from fastapi import APIRouter, HTTPException
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from config import YOUTUBE_API_KEY
from pydantic import BaseModel

router = APIRouter()

# -------------------- YouTube Client -------------------- #
youtube = None
try:
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    print("✅ YouTube client initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize YouTube client: {e}")


# -------------------- Data Extraction -------------------- #
def get_youtube_data(url: str) -> dict:
    if not youtube:
        return {"error": "YouTube client not initialized."}
    try:
        match = re.search(r"(?:v=|\/|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
        video_id = match.group(1) if match else None

        if not video_id:
            return {"error": "Could not find a valid YouTube video ID in the URL."}

        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        if not response.get("items"):
            return {"error": f"YouTube video with ID '{video_id}' not found."}

        snippet = response["items"][0]["snippet"]
        title = snippet["title"]
        description = snippet["description"]
        channel = snippet["channelTitle"]

        transcript = "No transcript available."
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            transcript = " ".join([item["text"] for item in transcript_list])
        except Exception as transcript_error:
            print(f"⚠️ Could not fetch transcript for video ID {video_id}: {transcript_error}")

        full_text = f"Title: {title}\n\nDescription: {description}\n\n--- Transcript ---\n\n{transcript}"
        return {"platform": "YouTube", "title": title, "content": full_text.strip()}
    except Exception as e:
        return {"error": f"An error occurred while fetching from YouTube: {e}"}


# -------------------- FastAPI Routes -------------------- #
class YouTubeRequest(BaseModel):
    url: str


@router.post("/extract")
def youtube_extract(req: YouTubeRequest):
    url = req.url.strip()
    if not url or "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid YouTube link.")

    result = get_youtube_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
