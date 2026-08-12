"""
search_rewards_in_chunk.py
--------------------------
Downloads chunk-UAE6UW5T.js and prints every line or snippet containing "rewards"
to see how it is written in the minified JavaScript.
"""

import asyncio
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-UAE6UW5T.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            
            idx = content.lower().find("rewards")
            while idx != -1:
                print(f"\n--- Found 'rewards' at {idx} ---")
                print(content[max(0, idx-100):min(len(content), idx+500)])
                idx = content.lower().find("rewards", idx + 1)

if __name__ == "__main__":
    asyncio.run(main())
