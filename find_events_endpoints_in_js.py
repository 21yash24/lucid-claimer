"""
find_events_endpoints_in_js.py
------------------------------
Searches chunk-C6SCLQTE.js, chunk-MMSBFUWB.js, and main-TF6I67B4.js for
any endpoint strings containing "events/" or "/events" to prove the active status
and guess submission endpoint signatures.
"""

import asyncio
import aiohttp
import re

FILES = [
    "chunk-C6SCLQTE.js",
    "chunk-MMSBFUWB.js",
    "main-TF6I67B4.js"
]

async def scan_file(session: aiohttp.ClientSession, filename: str):
    url = f"https://dash.lucidtrading.com/{filename}"
    try:
        async with session.get(url, timeout=12) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            
            # Look for segments of endpoints containing "events"
            pos = [m.start() for m in re.finditer(r'events/', content, re.IGNORECASE)]
            if pos:
                print(f"\n📂 FILE: {filename} | {len(pos)} matches for 'events/'")
                for p in pos:
                    snippet = content[max(0, p-150):min(len(content), p+250)]
                    print(f"  [{p}]: {snippet.strip()!r}")
            else:
                # Try "/events"
                pos = [m.start() for m in re.finditer(r'/events', content, re.IGNORECASE)]
                if pos:
                    print(f"\n📂 FILE: {filename} | {len(pos)} matches for '/events'")
                    for p in pos[:3]:
                        snippet = content[max(0, p-150):min(len(content), p+250)]
                        print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        print(f"Error scanning {filename}: {e}")

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Searching for events API paths in the bundle files...")
        await asyncio.gather(*(scan_file(session, f) for f in FILES))

if __name__ == "__main__":
    asyncio.run(main())
