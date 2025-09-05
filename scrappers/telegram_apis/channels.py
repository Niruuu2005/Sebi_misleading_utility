import asyncio
from fastapi import APIRouter, Query
from telethon import TelegramClient, functions
from config import API_ID, API_HASH, SESSION_NAME

router = APIRouter()

# ---------------- Utility ---------------- #
async def search_channels(query: str):
    """
    Search Telegram channels for a single keyword.
    """
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

# ---------------- APIs ---------------- #
@router.get("/search")
async def search_channels_api(
    keyword: str = Query(..., description="Keyword to search channels for")
):
    """
    Search Telegram channels based on a single keyword.
    """
    links = await search_channels(keyword)
    return {"keyword": keyword, "found_channels": links, "count": len(links)}


@router.get("/search_all")
async def search_all_channels_api():
    """
    Search Telegram channels using multiple predefined stock/finance keywords.
    Returns unique links across all queries.
    """
    INDIAN_STOCK_MARKET_QUERIES = [
        "NSE stocks",
        "BSE stocks",
        "Bank Nifty",
        "Nifty 50",
        "Nifty trading",
        "MCX trading",
        "Indian stock market",
        "share market India",
        "stock tips India",
        "intraday tips India",
        "equity tips India",
        "commodity tips India",
        "F&O trading India",
        "NSE options",
        "BSE updates",
        "ipo India",
        "Indian trading signals",
        "HDFC stock",
        "Reliance stock",
        "Infosys stock",
        "Indian investing",
        "stock picks India",
        "SEBI news",
        "Indian economy updates",
        "long-term investing India",
        "intraday stock calls",
        "swing trading India",
        "investment strategies India",
        "financial literacy India",
        "wealth management India",
    ]

    all_links = set()
    for query in INDIAN_STOCK_MARKET_QUERIES:
        links = await search_channels(query)
        all_links.update(links)

    return {
        "keywords": INDIAN_STOCK_MARKET_QUERIES,
        "found_channels": sorted(list(all_links)),
        "count": len(all_links),
    }
