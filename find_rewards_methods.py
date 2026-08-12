"""
find_rewards_methods.py
-----------------------
Downloads chunk-UAE6UW5T.js and prints the entire class that defines `/api/rewards`
and all its HTTP method calls (GET, POST, etc.) to discover guess endpoints.
"""

import asyncio
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-UAE6UW5T.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            
            # Print around '/api/rewards'
            idx = content.find("/api/rewards")
            if idx != -1:
                print("Found /api/rewards context:")
                print(content[max(0, idx-200):min(len(content), idx+1500)])
            else:
                print("Could not find '/api/rewards'")

if __name__ == "__main__":
    asyncio.run(main())
