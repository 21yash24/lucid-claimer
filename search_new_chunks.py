"""
search_new_chunks.py
--------------------
Downloads the fresh set of preloaded module chunks from the live site
and searches them for the API endpoint URLs or method names to verify
the rewards/redeem-secret endpoint.
"""

import asyncio
import aiohttp
import re

NEW_CHUNKS = [
    "chunk-UAE6UW5T.js",
    "chunk-2LJOK2OZ.js",
    "chunk-CZMHWVJ7.js",
    "chunk-EVUBG33A.js",
    "chunk-ZDG2Z5EI.js",
    "chunk-S6IOY4QW.js",
    "chunk-GZXZDPGI.js",
    "chunk-Q54ABHMH.js",
    "chunk-Y2CF354E.js",
    "chunk-DEYB4RMX.js"
]

async def scan_chunk(session: aiohttp.ClientSession, chunk_name: str):
    url = f"https://dash.lucidtrading.com/{chunk_name}"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            
            # Search for keyword matches
            for kw in ["rewards", "redeemSecret", "redeem-secret", "events/active", "events/submit"]:
                pos = [m.start() for m in re.finditer(re.escape(kw), content, re.IGNORECASE)]
                if pos:
                    print(f"\n📂 NEW CHUNK: {chunk_name} | {len(pos)} matches for '{kw}'")
                    for p in pos[:3]:
                        snippet = content[max(0, p-120):min(len(content), p+280)]
                        print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Searching the newly built chunks for the API URLs...")
        await asyncio.gather(*(scan_chunk(session, c) for c in NEW_CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
