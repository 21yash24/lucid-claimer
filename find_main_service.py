"""
find_main_service.py
--------------------
Downloads and searches main-TF6I67B4.js for "api/rewards/" to extract all
endpoints and payload keys for reward redemption.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/main-TF6I67B4.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Find references
            pos = [m.start() for m in re.finditer(r'api/rewards/', content)]
            print(f"Found {len(pos)} matches for 'api/rewards/':")
            for m in pos:
                snippet = content[max(0, m-150):min(len(content), m+350)]
                print(f"\n--- Match at {m} ---")
                print(snippet.strip())

if __name__ == "__main__":
    asyncio.run(main())
