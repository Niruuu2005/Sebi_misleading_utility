from fastapi import FastAPI
from scrappers.telegram_apis import channels, chats
from scrappers import reddit, youtube
from history import results

app = FastAPI(title="Telegram Stock API", version="1.0")

# Include Routers
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(results.router, prefix="/history", tags=["History"])
app.include_router(reddit.router, prefix="/reddit", tags=["reddit"])
app.include_router(youtube.router, prefix="/yt", tags=["youtube"])


@app.get("/")
def root():
    return {"message": "🚀 Telegram Stock API is running"}
