"""
find_lazy_routes.py
-------------------
Downloads and searches main-TF6I67B4.js for routing paths like "events"
to find the lazy-loaded chunk filename containing the mobile giveaway logic.
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
            
            # Search for occurrences of events in routes
            matches = list(re.finditer(r'events|loadChildren|import\b', content, re.IGNORECASE))
            print(f"Found {len(matches)} matches:")
            for m in matches[:10]:
                p = m.start()
                snippet = content[max(0, p-120):min(len(content), p+240)]
                print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
