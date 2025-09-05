import asyncio
from fastapi import APIRouter, Query
from telethon import TelegramClient, functions
from config import API_ID, API_HASH, SESSION_NAME

router = APIRouter()

async def search_channels(query: str):
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    links = set()
    try:
        await client.start()
        result = await client(functions.contacts.SearchRequest(q=query, limit=50))
        for chat in result.chats:
            if getattr(chat, "username", None):
                links.add(f"https://t.me/{chat.username}")
    finally:
        await client.disconnect()
    return list(links)


@router.get("/search")
async def search_channels_api(keyword: str = Query(..., description="Keyword to search channels for")):
    """
    Search Telegram channels based on a keyword.
    """
    links = await search_channels(keyword)
    return {"keyword": keyword, "found_channels": links, "count": len(links)}
