"""
find_rewards_service_definition.py
----------------------------------
Searches chunk-PHSFC5V5.js for the rewardsService class injection to find
how it makes HTTP requests.
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
            
            # Find the word "rewardsService" inside the file
            matches = list(re.finditer(r'rewardsService', content, re.IGNORECASE))
            print(f"Found {len(matches)} matches for 'rewardsService':")
            for m in matches:
                p = m.start()
                snippet = content[max(0, p-150):min(len(content), p+250)]
                print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
