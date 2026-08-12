"""
scan_for_rewards_service.py
----------------------------
Finds the implementation of rewardsService.redeemSecret inside chunk-PHSFC5V5.js
to inspect the exact API URL path and request payload format.
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
            
            # Find the word "redeemSecret" inside the file
            # Let's print snippets of ALL matches to find where the service method is defined
            matches = list(re.finditer(r'redeemSecret\b', content))
            print(f"Found {len(matches)} exact matches for 'redeemSecret\\b':")
            for idx, m in enumerate(matches):
                p = m.start()
                snippet = content[max(0, p-150):min(len(content), p+350)]
                print(f"\n[{idx}] Position {p}:")
                print(snippet.strip())

if __name__ == "__main__":
    asyncio.run(main())
