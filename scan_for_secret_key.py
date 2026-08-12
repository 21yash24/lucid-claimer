"""
scan_for_secret_key.py
-----------------------
Downloads chunk-PHSFC5V5.js (the LucidVault/UserPromoComponent)
and prints any occurrences of "redeem" or "secret" or "code" to find the exact endpoint
and payload fields used to submit the secret key.
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
            
            # Find references to endpoints containing redeem
            # Or HTTP POST calls
            pos = [m.start() for m in re.finditer(r'redeem', content, re.IGNORECASE)]
            print(f"\nFound {len(pos)} matches for 'redeem':")
            for p in pos:
                snippet = content[max(0, p-120):min(len(content), p+240)]
                print(f"  - {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
