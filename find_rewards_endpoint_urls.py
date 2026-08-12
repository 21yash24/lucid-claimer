"""
find_rewards_endpoint_urls.py
-----------------------------
Downloads and searches main-TF6I67B4.js for the endpoints under:
- "/rewards"
- "/crate"
- "/events"
to prove exactly where the API calls go.
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
            
            # Look for segments of endpoints like "/rewards"
            for segment in ["/rewards/", "/crate", "/events/"]:
                pos = [m.start() for m in re.finditer(re.escape(segment), content, re.IGNORECASE)]
                print(f"\nFound {len(pos)} matches for segment '{segment}':")
                for p in pos[:10]:
                    snippet = content[max(0, p-150):min(len(content), p+250)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
