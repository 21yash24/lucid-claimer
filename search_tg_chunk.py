"""
search_tg_chunk.py
------------------
Audits chunk-TGAQVISN.js for redeemSecret to see the exact HTTP request URL and body.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-TGAQVISN.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Find references
            pos = [m.start() for m in re.finditer(r'redeemSecret', content, re.IGNORECASE)]
            print(f"Matches for 'redeemSecret' in chunk-TGAQVISN: {pos}")
            for p in pos:
                snippet = content[max(0, p-150):min(len(content), p+350)]
                print(f"\n--- Snippet at {p} ---")
                print(snippet.strip())

if __name__ == "__main__":
    asyncio.run(main())
