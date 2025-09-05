import asyncio
import os
from telethon import TelegramClient, functions

# Your API credentials from my.telegram.org/apps
API_ID = '21252171'
API_HASH = '485e5fec9f6090c7c0f461ab19bb5140'

async def search_telegram_channels_by_query(query):
    """
    Searches for Telegram channels based on a single text query
    and returns their public joining links.
    """
    client = TelegramClient('./Messaging_Apps\\my_session', API_ID, API_HASH)
    found_links = set()

    try:
        await client.start()
        print(f"Client started. Searching for channels related to: '{query}'...")

        result = await client(functions.contacts.SearchRequest(
            q=query,
            limit=50
        ))

        for chat in result.chats:
            if hasattr(chat, 'username') and chat.username:
                link = f"https://t.me/{chat.username}"
                found_links.add(link)
                
        return found_links

    except Exception as e:
        print(f"An error occurred during search for '{query}': {e}")
        return set()

    finally:
        await client.disconnect()
        
async def main():
    INDIAN_STOCK_MARKET_QUERIES = [
        # Indian-specific stock/finance keywords
        'NSE stocks',
        'BSE stocks',
        'Bank Nifty',
        'Nifty 50',
        'Nifty trading',
        'MCX trading',
        'Indian stock market',
        'share market India',
        'stock tips India',
        'intraday tips India',
        'equity tips India',
        'commodity tips India',
        'F&O trading India',
        'NSE options',
        'BSE updates',
        'ipo India',
        'Indian trading signals',
        'HDFC stock',
        'Reliance stock',
        'Infosys stock',
        'Indian investing',
        'stock picks India',
        'SEBI news',
        'Indian economy updates',
        'long-term investing India',
        'intraday stock calls',
        'swing trading India',
        'investment strategies India',
        'financial literacy India',
        'wealth management India'
    ]
    
    output_filename = '.\\Messaging_Apps\\indian_stock_telegram_links.txt'
    all_unique_links = set()

    for query in INDIAN_STOCK_MARKET_QUERIES:
        links_for_query = await search_telegram_channels_by_query(query)  # ✅ fixed bug (was "query")
        all_unique_links.update(links_for_query)
        print(f"Total unique channels found so far: {len(all_unique_links)}")

    if all_unique_links:
        print("\n--- Final Results ---")
        print(f"Found a total of {len(all_unique_links)} unique Indian stock market channel links.")
        print("Writing links to file...")
        
        try:
            with open(output_filename, 'w') as f:
                for link in sorted(list(all_unique_links)):
                    f.write(link + '\n')
            
            print(f"✅ Successfully wrote {len(all_unique_links)} links to '{output_filename}'.")
            
        except IOError as e:
            print(f"File writing error: {e}")
            
    else:
        print("No Indian public channels found for the given queries, or an error occurred.")

if __name__ == '__main__':
    asyncio.run(main())
