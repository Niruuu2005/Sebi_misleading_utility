from fastapi import FastAPI
from telegram_apis import channels, chats

app = FastAPI(title="Telegram Stock API", version="1.0")

# Include Routers
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])


@app.get("/")
def root():
    return {"message": "🚀 Telegram Stock API is running"}
