"""
find_rewards_endpoints.py
-------------------------
Downloads chunk-UJPPAIWO.js and prints the full context containing `/api/rewards`
to list all endpoints for mastermind guesses, active status, crates, and reward claims.
"""

import asyncio
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-UJPPAIWO.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Print around '/api/rewards'
            idx = content.find("/api/rewards")
            while idx != -1:
                print("\n--- Found /api/rewards context ---")
                print(content[max(0, idx-300):min(len(content), idx+1500)])
                idx = content.find("/api/rewards", idx + 1)

if __name__ == "__main__":
    asyncio.run(main())
