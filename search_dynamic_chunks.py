"""
search_dynamic_chunks.py
-------------------------
Downloads chunk-VUONRY3T.js and chunk-HVCGLXRO.js to check if the events/active
or events/submit endpoint declarations are located inside them.
"""

import asyncio
import aiohttp
import re

FILES = [
    "chunk-VUONRY3T.js",
    "chunk-HVCGLXRO.js"
]

async def scan_file(session: aiohttp.ClientSession, filename: str):
    url = f"https://dash.lucidtrading.com/{filename}"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            print(f"\n📂 FILE: {filename} ({len(content)} bytes)")
            
            # Find references
            for kw in ["events", "active", "submit"]:
                pos = [m.start() for m in re.finditer(re.escape(kw), content, re.IGNORECASE)]
                if pos:
                    print(f"  Match for '{kw}': {len(pos)} matches")
                    for p in pos[:3]:
                        snippet = content[max(0, p-120):min(len(content), p+240)]
                        print(f"    [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Scanning dynamic chunks for events endpoints...")
        await asyncio.gather(*(scan_file(session, f) for f in FILES))

if __name__ == "__main__":
    asyncio.run(main())
