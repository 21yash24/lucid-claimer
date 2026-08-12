"""
find_service_class.py
---------------------
Searches chunk-PHSFC5V5.js for method definitions of:
- redeemSecret
- getCrateStatus
- getUserRewards
- openCrate
to find the API endpoint URLs.
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
            
            # Search for "openCrate" or "getCrateStatus" method definitions in the file
            for kw in ["openCrate", "getCrateStatus", "getUserRewards", "redeemSecret"]:
                matches = list(re.finditer(re.escape(kw) + r'\b', content))
                print(f"\nKeyword '{kw}' matches: {len(matches)}")
                for m in matches:
                    p = m.start()
                    snippet = content[max(0, p-150):min(len(content), p+350)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
