import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from telethon import TelegramClient, functions, errors
from config import API_ID, API_HASH, SESSION_NAME

router = APIRouter()

# State file to persist last_scraped timestamps
STATE_FILE = "./data/scrape_state.json"


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


async def ensure_joined(client, entity):
    try:
        await client(functions.channels.GetParticipantRequest(channel=entity, participant="me"))
        return True
    except errors.UserNotParticipantError:
        try:
            await client(functions.channels.JoinChannelRequest(channel=entity))
            return True
        except Exception:
            return False
    except Exception:
        return False


async def fetch_new_messages(channel: str, hours: int = 1):
    """
    Fetch messages from last stored timestamp until now.
    If no timestamp found, fetch from last `hours`.
    """
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    messages_data = []
    state = load_state()

    try:
        await client.start()
        entity = await client.get_entity(channel)

        joined = await ensure_joined(client, entity)
        if not joined:
            return {"error": f"Could not join {channel}"}

        # Get last_scraped timestamp if exists
        last_scraped_str = state.get(channel, {}).get("last_scraped")
        if last_scraped_str:
            since_time = datetime.fromisoformat(last_scraped_str)
        else:
            since_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Fetch messages since last_scraped
        async for msg in client.iter_messages(entity, limit=500):
            if msg.date < since_time:
                break
            if msg.message:
                messages_data.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "sender_id": msg.sender_id,
                    "text": msg.message
                })

        # Update state with new timestamp
        state[channel] = {"last_scraped": datetime.now(timezone.utc).isoformat()}
        save_state(state)

    finally:
        await client.disconnect()

    return messages_data


@router.get("/get")
async def get_channel_chats(
    channel: str = Query(..., description="Channel link or username"),
    hours: int = Query(1, description="If first time, fetch last N hours")
):
    """
    Get new chats from a Telegram channel (only messages since last scrape).
    - Auto joins if not already joined.
    - Stores last_scraped timestamp per channel.
    """
    chats = await fetch_new_messages(channel, hours)
    return {
        "channel": channel,
        "messages_fetched": len(chats) if isinstance(chats, list) else 0,
        "messages": chats
    }
