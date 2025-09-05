import praw
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
import re

router = APIRouter()

# -------------------- Reddit Client -------------------- #
reddit_client = None
try:
    reddit_client = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    print("✅ Reddit PRAW client initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize Reddit PRAW client: {e}")


# -------------------- Data Extraction -------------------- #
def get_reddit_data(url: str) -> dict:
    """
    Extracts content from a Reddit post using the PRAW library. This includes
    the post's title, body, author, and top comments, which is valuable for
    analyzing suspicious stock tips or market manipulation discussions.
    """
    if not reddit_client:
        return {"error": "Reddit client not initialized."}
    try:
        # Extract submission ID from URL
        match = re.search(r"comments/(\w+)", url)
        if not match:
            return {"error": "Could not find a valid Reddit submission ID in the URL."}
        
        submission = reddit_client.submission(id=match.group(1))

        # Check if the post is deleted or removed
        if submission.selftext == '[deleted]' or submission.selftext == '[removed]':
            return {"error": "This Reddit post has been deleted or removed."}

        title = submission.title
        author = str(submission.author) if submission.author else "[deleted]"
        content = submission.selftext

        # Fetch top comments to add context
        comment_text = ""
        submission.comment_sort = "top"
        submission.comments.replace_more(limit=0)
        for i, comment in enumerate(submission.comments):
            if i < 5:  # Limit to top 5 comments
                comment_author = str(comment.author) if comment.author else "[deleted]"
                comment_text += f"Comment by u/{comment_author}: {comment.body}\n\n"
            else:
                break

        full_content = (
            f"Title: {title}\n"
            f"Author: u/{author}\n\n"
            f"--- Post ---\n{content}\n\n"
            f"--- Top Comments ---\n{comment_text}"
        )

        return {
            "platform": "Reddit",
            "title": title,
            "content": full_content.strip()
        }

    except Exception as e:
        return {"error": f"An error occurred while fetching from Reddit: {e}"}


# -------------------- FastAPI Routes -------------------- #
class RedditRequest(BaseModel):
    url: str


@router.post("/extract")
def reddit_extract(req: RedditRequest):
    url = req.url.strip()
    if not url or "reddit.com" not in url:
        raise HTTPException(status_code=400, detail="Please provide a valid Reddit link.")

    result = get_reddit_data(url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result