"""
inspect_promo_chunk.py
-----------------------
Downloads chunk-PHSFC5V5.js (the UserPromoComponent/LucidVault code)
and searches it for:
- /api/
- guess
- crack
- mastermind
- active
- status
Prints matching lines and full surrounding code block contexts to discover
the mastermind endpoints.
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
            
            # Search for keyword matches
            for word in ["guess", "crack", "mastermind", "active", "status", "/api/", "vault", "code"]:
                positions = [m.start() for m in re.finditer(re.escape(word), content, re.IGNORECASE)]
                print(f"\nKeyword '{word}' found at positions: {positions}")
                for p in positions[:10]:
                    snippet = content[max(0, p-120):min(len(content), p+200)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
