"""
find_rewards_service_class.py
------------------------------
Searches main-TF6I67B4.js for "rewardsService" or "openCrate" or "redeemSecret"
definitions to find the class declaration of the service.
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
            
            # Find the declaration of the service class
            # We look for "openCrate()" method definition or "redeemSecret" inside this main chunk
            matches = list(re.finditer(r'openCrate\s*\(', content))
            print(f"Found {len(matches)} matches for 'openCrate\\s*\\(':")
            for m in matches:
                p = m.start()
                snippet = content[max(0, p-200):min(len(content), p+500)]
                print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
