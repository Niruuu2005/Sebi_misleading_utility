import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, functions, errors

# --- Configuration ---
API_ID = '21252171'
API_HASH = '485e5fec9f6090c7c0f461ab19bb5140'

# File paths
INPUT_FILENAME = './Messaging_Apps/indian_stock_telegram_links.txt'
OUTPUT_FILENAME = './Messaging_Apps/channel_chats.json'
STATE_FILENAME = './Messaging_Apps/scrape_state.json'
SESSION_NAME = './Messaging_Apps/my_session'

# Time constants
MIN_SLEEP_SECONDS = 20
MAX_SLEEP_SECONDS = 40
FULL_ITERATION_WAIT_MINUTES = 5
MESSAGE_FETCH_LIMIT = 200
DEFAULT_FETCH_HOURS = 1   # ⬅️ default last 1 hour if no last_scraped


# --- Core Functions ---

async def fetch_recent_chats(client, channel, since_time):
    """
    Fetches the latest messages from a given channel since a specified time.
    """
    messages_data = []
    try:
        async for msg in client.iter_messages(channel, limit=MESSAGE_FETCH_LIMIT):
            if msg.date < since_time:
                break
            if msg.message:
                messages_data.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "sender_id": msg.sender_id,
                    "text": msg.message
                })
    except Exception as e:
        print(f"⚠️ An error occurred while fetching chats: {e}")
    return messages_data


async def ensure_joined(client, entity):
    """
    Checks if the user is a member of a channel and joins if not.
    """
    try:
        await client(functions.channels.GetParticipantRequest(
            channel=entity,
            participant='me'
        ))
        return True
    except errors.UserNotParticipantError:
        print(f"❌ Not joined: {entity.title or entity.username or entity.id}. Attempting to join...")
        try:
            await client(functions.channels.JoinChannelRequest(channel=entity))
            print(f"✅ Successfully joined {entity.title or entity.username or entity.id}.")
            await asyncio.sleep(5)
            return True
        except errors.ChannelPrivateError:
            print(f"⚠️ Cannot join {entity.title or entity.username or entity.id}. It is a private channel.")
            return False
        except Exception as e:
            print(f"⚠️ Could not join {entity.title or entity.username or entity.id}: {e}")
            return False
    except Exception as e:
        print(f"⚠️ Could not check membership for {entity.title or entity.username or entity.id}: {e}")
        return False


def get_fetch_start_time(last_scraped_str, hours=DEFAULT_FETCH_HOURS, minutes=10):
    """
    Calculates the timestamp from which to start fetching messages.
    - If last_scraped exists: fetch from slightly before it (buffer).
    - Else: fetch from last N hours.
    """
    if last_scraped_str:
        last_scraped = datetime.fromisoformat(last_scraped_str)
        return last_scraped - timedelta(minutes=minutes)
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def deduplicate_messages(existing_messages, new_messages):
    """
    Remove duplicates based on message ID.
    """
    existing_ids = {m["id"] for m in existing_messages}
    return [m for m in new_messages if m["id"] not in existing_ids]


# --- Main Orchestration ---

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    # Load persistent state
    try:
        with open(STATE_FILENAME, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}

    try:
        with open(OUTPUT_FILENAME, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = {}

    try:
        await client.start()
        print("🚀 Client started. Continuous monitoring...")

        while True:
            try:
                with open(INPUT_FILENAME, 'r') as f:
                    links = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print(f"❌ Input file not found: {INPUT_FILENAME}. Exiting.")
                return

            print(f"\n🔄 New iteration at {datetime.now(timezone.utc).isoformat()}, found {len(links)} links")

            for link in links:
                try:
                    entity = await client.get_entity(link)
                    is_joined = await ensure_joined(client, entity)

                    if is_joined:
                        last_scraped_str = state.get(link, {}).get("last_scraped")
                        since_time = get_fetch_start_time(last_scraped_str, hours=DEFAULT_FETCH_HOURS)

                        print(f"📡 Fetching chats from {link} since {since_time.isoformat()}...")
                        new_messages = await fetch_recent_chats(client, entity, since_time)

                        if new_messages:
                            if link not in all_data:
                                all_data[link] = []

                            # ✅ Deduplicate
                            deduped = deduplicate_messages(all_data[link], new_messages)
                            all_data[link].extend(deduped)

                            print(f"✅ Collected {len(deduped)} new messages from {link}")
                        else:
                            print(f"ℹ️ No new messages found in {link}")

                        # ✅ Always update last_scraped
                        state[link] = {"last_scraped": datetime.now(timezone.utc).isoformat()}

                except Exception as e:
                    print(f"⚠️ Could not process {link}: {e}")

                wait_time = random.randint(MIN_SLEEP_SECONDS, MAX_SLEEP_SECONDS)
                print(f"⏳ Sleeping for {wait_time}s...")
                await asyncio.sleep(wait_time)

            # Save state & data after each round
            with open(STATE_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)

            print(f"\n💾 Saved state and data. Waiting {FULL_ITERATION_WAIT_MINUTES} minutes before next full iteration...")
            await asyncio.sleep(FULL_ITERATION_WAIT_MINUTES * 60)

    finally:
        await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
