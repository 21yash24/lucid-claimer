"""
search_secret_redeem.py
-----------------------
Downloads chunk-PHSFC5V5.js and searches for "secretRedeem" case-sensitively
to find the API submit logic and its payload fields.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-PHSFC5V5.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Find references
            pos = [m.start() for m in re.finditer(r'secretRedeem', content)]
            print(f"Matches: {pos}")
            for p in pos:
                snippet = content[max(0, p-200):min(len(content), p+500)]
                print(f"\n--- Snippet at {p} ---")
                print(snippet.strip())

if __name__ == "__main__":
    asyncio.run(main())
