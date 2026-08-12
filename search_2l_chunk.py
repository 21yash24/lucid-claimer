"""
search_2l_chunk.py
------------------
Audits chunk-2LJOK2OZ.js for any occurrences of "events" or "submit" or "active"
to find any event game endpoints.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-2LJOK2OZ.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Find references
            for kw in ["events", "submit", "active"]:
                pos = [m.start() for m in re.finditer(re.escape(kw), content, re.IGNORECASE)]
                print(f"Matches for '{kw}': {len(pos)}")
                for p in pos[:3]:
                    snippet = content[max(0, p-120):min(len(content), p+240)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
