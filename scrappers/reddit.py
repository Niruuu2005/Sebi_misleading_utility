import re
import requests
import praw
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

# Router for Reddit
router = APIRouter()

# -------------------- Reddit Client -------------------- #
reddit = None
try:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    print("✅ Reddit client initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize Reddit client: {e}")


# -------------------- Data Extraction Logic -------------------- #
def get_reddit_data_api(url: str) -> dict:
    """Try to get Reddit data using the official API first"""
    if not reddit:
        return None
    try:
        match = re.search(r"comments/(\w+)", url)
        if not match:
            return None

        submission = reddit.submission(id=match.group(1))
        if submission.selftext in ['[deleted]', '[removed]']:
            return {"error": "This Reddit post has been deleted or removed."}

        title = submission.title
        selftext = submission.selftext
        full_text = f"Title: {title}\n\n{selftext}\n\n--- Comments ---\n\n"

        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)
        for i, comment in enumerate(submission.comments):
            if i < 5:
                full_text += f"Comment by {comment.author}: {comment.body}\n\n"
            else:
                break

        return {"platform": "Reddit", "title": title, "content": full_text.strip()}
    except Exception as e:
        print(f"Reddit API failed: {e}")
        return None


def get_reddit_data_scrape(url: str) -> dict:
    """Fallback: scrape Reddit using web scraping"""
    try:
        json_url = url.rstrip('/') + '.json'
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(json_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"error": f"Failed to fetch Reddit data: HTTP {response.status_code}"}

        data = response.json()
        if not data or len(data) < 1:
            return {"error": "No Reddit data found"}

        post_data = data[0]['data']['children'][0]['data']
        title = post_data.get('title', 'No title')
        selftext = post_data.get('selftext', '')

        full_text = f"Title: {title}\n\n{selftext}\n\n--- Comments ---\n\n"

        if len(data) > 1 and 'data' in data[1]:
            comments = data[1]['data']['children']
            comment_count = 0
            for comment in comments:
                if comment_count >= 5:
                    break
                if comment['kind'] == 't1' and 'data' in comment:
                    comment_data = comment['data']
                    author = comment_data.get('author', 'Unknown')
                    body = comment_data.get('body', '')
                    if body and body not in ['[deleted]', '[removed]']:
                        full_text += f"Comment by {author}: {body}\n\n"
                        comment_count += 1

        return {"platform": "Reddit", "title": title, "content": full_text.strip()}
    except Exception as e:
        return {"error": f"An error occurred while scraping Reddit: {e}"}


def get_reddit_data(url: str) -> dict:
    """Try API first, then fallback to web scraping"""
    result = get_reddit_data_api(url)
    if result and "error" not in result:
        return result

    print("⚠️ Reddit API failed, trying web scraping...")
    return get_reddit_data_scrape(url)


# -------------------- FastAPI Routes -------------------- #
class RedditRequest(BaseModel):
    url: str


@router.post("/extract")
def reddit_extract(req: RedditRequest):
    """
    Extract Reddit post data (title, text, and top comments).
    Tries API first, falls back to scraping.
    """
    url = req.url.strip()
    if not url or "reddit.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Reddit link.")

    result = get_reddit_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
