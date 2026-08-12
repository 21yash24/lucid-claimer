"""
find_all_chunks_in_main.py
--------------------------
Downloads main-TF6I67B4.js and extracts all lazy-loaded chunk IDs and names
referenced by Angular's dynamic bundle loader.
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
            
            # Look for matches like chunk-XYZ.js or chunk-XYZ
            chunks = set(re.findall(r'chunk-[A-Za-z0-9]+\.js', content))
            print(f"Found {len(chunks)} chunks referenced inside main bundle:")
            for c in sorted(chunks):
                print(f"  - {c}")

if __name__ == "__main__":
    asyncio.run(main())
