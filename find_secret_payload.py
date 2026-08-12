"""
find_secret_payload.py
----------------------
Downloads chunk-UJPPAIWO.js and searches it for:
- redeemSecret
- redeem-secret
- secretCode
to find the exact JSON payload key used to submit the secret key.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-UJPPAIWO.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Search for keyword matches case-insensitively
            for keyword in ["redeem-secret", "secretCode", "secret_code", "secret"]:
                matches = list(re.finditer(re.escape(keyword), content, re.IGNORECASE))
                print(f"\nKeyword '{keyword}' matches: {len(matches)}")
                for m in matches[:5]:
                    p = m.start()
                    snippet = content[max(0, p-120):min(len(content), p+240)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
