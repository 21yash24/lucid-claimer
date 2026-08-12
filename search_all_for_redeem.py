"""
search_all_for_redeem.py
-------------------------
Downloads all unique chunk JS files and searches them for:
- "redeem"
- "secret"
- "code"
to find the API endpoint and JSON payload key.
"""

import asyncio
import aiohttp
import re

CHUNKS = [
    "polyfills-NNOWO3XQ.js",
    "scripts-SQ7W6IC7.js",
    "main-TF6I67B4.js",
    "chunk-PHSFC5V5.js",
    "chunk-C6SCLQTE.js",
    "chunk-IYFX2Y2U.js",
    "chunk-WTLOLKRB.js",
    "chunk-LEU3KDPB.js",
    "chunk-E6SY6GSC.js",
    "chunk-MMSBFUWB.js",
    "chunk-ZZ4WTL5U.js",
    "chunk-KW4MFTJZ.js",
    "chunk-YFJUTE5S.js",
    "chunk-B6EVPS3Y.js",
    "chunk-CP2SNZJK.js",
    "chunk-PPRURSHA.js",
    "chunk-7FMJRPEQ.js",
    "chunk-6D5PZXRA.js",
    "chunk-2B3YWJM3.js",
    "chunk-SN5ZCYBV.js",
    "chunk-5QNFT532.js",
    "chunk-3C75JY5V.js",
    "chunk-TGAQVISN.js",
    "chunk-DHDXS6CO.js",
    "chunk-5C3WQF6R.js",
    "chunk-YMSOSPLV.js",
    "chunk-BDBSYBTQ.js",
    "chunk-562YHLTF.js"
]

async def scan_chunk(session: aiohttp.ClientSession, chunk_name: str):
    url = f"https://dash.lucidtrading.com/{chunk_name}"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            
            # Find references containing "redeem"
            pos = [m.start() for m in re.finditer(r'redeem', content, re.IGNORECASE)]
            if pos:
                print(f"\n📂 CHUNK: {chunk_name} ({len(content)} bytes) | {len(pos)} matches for 'redeem'")
                for p in pos[:5]:
                    snippet = content[max(0, p-100):min(len(content), p+250)]
                    print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Searching all chunks for 'redeem'...")
        await asyncio.gather(*(scan_chunk(session, c) for c in CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
