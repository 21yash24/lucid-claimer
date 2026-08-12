"""
check_env_cookie.py
-------------------
Sends a request to /api/events/active using the BROWSER_COOKIE configured in .env
to verify if the cookie is still valid or if it has expired.
"""

import asyncio
import aiohttp
import sys

sys.path.insert(0, '.')
import config

async def main():
    if not config.BROWSER_COOKIE:
        print("❌ No BROWSER_COOKIE configured in .env")
        return
        
    headers = {
        "Cookie": config.BROWSER_COOKIE,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    url = "https://dash.lucidtrading.com/api/events/active"
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print(f"📡 Querying status endpoint with configured BROWSER_COOKIE...")
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            print(f"   Response Status: {resp.status}")
            print(f"   Response Body: {text}")

if __name__ == "__main__":
    asyncio.run(main())
