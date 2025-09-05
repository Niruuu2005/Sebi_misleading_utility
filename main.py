from fastapi import FastAPI
from scrappers.telegram_apis import channels, chats
from scrappers import (
    reddit_analyzer as reddit, # Using an alias to match original import style
    youtube,
    exchange_analyzer,
    discord_analyzer,
    twitter_analyzer,
    linkedin_analyzer
)
from history import results

app = FastAPI(title="Social Media Stock Analyzer API", version="1.3")

# --- Include Routers ---
# Original Routers (assuming these are part of your project)
app.include_router(channels.router, prefix="/channels", tags=["Telegram Channels"])
app.include_router(chats.router, prefix="/chats", tags=["Telegram Chats"])
app.include_router(results.router, prefix="/history", tags=["History"])

# Social Media and Exchange Scrapers
app.include_router(reddit.router, prefix="/reddit", tags=["Reddit"])
app.include_router(youtube.router, prefix="/youtube", tags=["YouTube"])
app.include_router(exchange_analyzer.router, prefix="/exchange", tags=["Exchange"])
app.include_router(discord_analyzer.router, prefix="/discord", tags=["Discord"])
app.include_router(twitter_analyzer.router, prefix="/twitter", tags=["Twitter/X"])
app.include_router(linkedin_analyzer.router, prefix="/linkedin", tags=["LinkedIn"])


@app.get("/")
def root():
    """
    Root endpoint for the API, confirming the service is running.
    """
    return {"message": "🚀 Social Media Stock Analyzer API is running"}