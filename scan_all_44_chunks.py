"""
scan_all_44_chunks.py
---------------------
Downloads and searches all 44 chunks in the Lucid Trading application for
giveaway events endpoints (like "events/", "/events", "active", "submit")
to find the exact mobile giveaway api routes.
"""

import asyncio
import aiohttp
import re

ALL_44_CHUNKS = [
    "chunk-2B3YWJM3.js",
    "chunk-2FBR3C3O.js",
    "chunk-2LJOK2OZ.js",
    "chunk-3C75JY5V.js",
    "chunk-562YHLTF.js",
    "chunk-5C3WQF6R.js",
    "chunk-5QNFT532.js",
    "chunk-6D5PZXRA.js",
    "chunk-76YWB7QV.js",
    "chunk-7FMJRPEQ.js",
    "chunk-B6EVPS3Y.js",
    "chunk-BDBSYBTQ.js",
    "chunk-C6SCLQTE.js",
    "chunk-CLPVIKDL.js",
    "chunk-CP2SNZJK.js",
    "chunk-CZMHWVJ7.js",
    "chunk-DEYB4RMX.js",
    "chunk-DHDXS6CO.js",
    "chunk-E6SY6GSC.js",
    "chunk-EVUBG33A.js",
    "chunk-GUO3MWSO.js",
    "chunk-GZXZDPGI.js",
    "chunk-HVCGLXRO.js",
    "chunk-IYFX2Y2U.js",
    "chunk-KW4MFTJZ.js",
    "chunk-LEU3KDPB.js",
    "chunk-MMSBFUWB.js",
    "chunk-PHSFC5V5.js",
    "chunk-PPRURSHA.js",
    "chunk-Q54ABHMH.js",
    "chunk-S6IOY4QW.js",
    "chunk-SN5ZCYBV.js",
    "chunk-TGAQVISN.js",
    "chunk-UAE6UW5T.js",
    "chunk-UJPPAIWO.js",
    "chunk-VUONRY3T.js",
    "chunk-VXYX7FLX.js",
    "chunk-WTLOLKRB.js",
    "chunk-WWX6BADO.js",
    "chunk-Y2CF354E.js",
    "chunk-YFJUTE5S.js",
    "chunk-YMSOSPLV.js",
    "chunk-ZDG2Z5EI.js",
    "chunk-ZZ4WTL5U.js"
]

async def scan_chunk(session: aiohttp.ClientSession, chunk_name: str):
    url = f"https://dash.lucidtrading.com/{chunk_name}"
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return
            content = await resp.text(errors="replace")
            
            # Find references
            for kw in ["events/active", "events/submit", "/events", "eventId"]:
                pos = [m.start() for m in re.finditer(re.escape(kw), content, re.IGNORECASE)]
                if pos:
                    print(f"\n📂 CHUNK: {chunk_name} | Match for '{kw}'")
                    for p in pos[:3]:
                        snippet = content[max(0, p-120):min(len(content), p+240)]
                        print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Scanning all 44 Angular chunks for events/giveaway API endpoints...")
        await asyncio.gather(*(scan_chunk(session, c) for c in ALL_44_CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
