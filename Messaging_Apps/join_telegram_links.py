import asyncio
import random
from telethon import TelegramClient, functions

# Your API credentials
API_ID = "21252171"
API_HASH = "485e5fec9f6090c7c0f461ab19bb5140"

# Input file with saved links
INPUT_FILENAME = ".\\Messaging_Apps\\indian_stock_telegram_links.txt"


async def join_channels_from_file():
    client = TelegramClient("./Messaging_Apps\\my_session", API_ID, API_HASH)

    try:
        await client.start()
        print("Client started. Reading links from file...")

        with open(INPUT_FILENAME, "r") as f:
            links = [line.strip() for line in f if line.strip()]

        print(f"Found {len(links)} links. Attempting to join at safe intervals...")

        joined, failed = 0, 0
        retry_links = []  # store failed links here

        # First pass: try all links
        for link in links:
            try:
                await client(functions.channels.JoinChannelRequest(channel=link))
                print(f"✅ Joined: {link}")
                joined += 1
            except Exception as e:
                print(f"❌ Could not join {link}: {e}")
                retry_links.append(link)  # add to retry queue

            # Safe random wait between attempts
            wait_time = random.randint(30, 40)
            print(f"⏳ Sleeping for {wait_time} seconds before next join...")
            await asyncio.sleep(wait_time)

        # Second pass: retry failed links
        if retry_links:
            print(f"\n🔄 Retrying {len(retry_links)} failed links after 60s each...\n")
            for link in retry_links:
                await asyncio.sleep(60)  # wait before each retry
                try:
                    await client(functions.channels.JoinChannelRequest(channel=link))
                    print(f"✅ Retry successful: {link}")
                    joined += 1
                except Exception as e2:
                    print(f"❌ Retry failed for {link}: {e2}")
                    failed += 1

        print(
            f"\n--- Summary ---\nSuccessfully joined: {joined}\nFailed (after retry): {failed}"
        )

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(join_channels_from_file())
