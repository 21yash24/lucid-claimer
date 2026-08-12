import asyncio
import os
import sys
from twikit import Client

sys.path.append("/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer")
import config

async def test_timeline():
    client = Client('en-US')
    cookies_path = "x_cookies.json"
    
    if os.path.exists(cookies_path):
        client.load_cookies(cookies_path)
        print("🔓 Cookies loaded.")
    else:
        print("❌ No cookies found.")
        return
        
    try:
        print("📡 Querying get_latest_timeline...")
        tweets = await client.get_latest_timeline(count=5)
        print(f"✅ Success! Fetched {len(tweets)} tweets.")
        for t in tweets:
            print(f"- [@{t.user.screen_name}]: {t.text[:80]}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_timeline())
