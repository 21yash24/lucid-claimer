"""
find_events_in_new_chunks.py
----------------------------
Downloads all the fresh preloaded chunks and searches for "/events/" or "/api/events"
to find the exact service definition for the mobile giveaway active status
and guess submission endpoints.
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
    "chunk-DEYB4RMX.js",
    "main-TF6I67B4.js"
]

async def scan_chunk(session: aiohttp.ClientSession, chunk_name: str):
    url = f"https://dash.lucidtrading.com/{chunk_name}"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            
            # Find references to "events/" or "/events"
            for kw in ["events/", "/events", "api/events"]:
                pos = [m.start() for m in re.finditer(re.escape(kw), content, re.IGNORECASE)]
                if pos:
                    print(f"\n📂 CHUNK: {chunk_name} | {len(pos)} matches for '{kw}'")
                    for p in pos[:3]:
                        snippet = content[max(0, p-150):min(len(content), p+250)]
                        print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Searching all new chunks for events API paths...")
        await asyncio.gather(*(scan_chunk(session, c) for c in NEW_CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
