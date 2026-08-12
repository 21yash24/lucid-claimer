"""
find_rewards_api_definition.py
------------------------------
Downloads all unique chunk JS files and searches them for the literal segments:
- "redeem-secret"
- "rewards/redeem"
- "api/rewards"
- "redeemSecret"
to find exactly how and where the API call is constructed.
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
            
            # Find references
            for kw in ["redeem-secret", "rewards/redeem", "api/rewards", "redeemSecret"]:
                matches = list(re.finditer(re.escape(kw), content, re.IGNORECASE))
                if matches:
                    print(f"\n📂 CHUNK: {chunk_name} | Match for '{kw}'")
                    for m in matches[:3]:
                        p = m.start()
                        snippet = content[max(0, p-150):min(len(content), p+250)]
                        print(f"  [{p}]: {snippet.strip()!r}")
    except Exception as e:
        pass

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Searching all chunks for rewards API strings...")
        await asyncio.gather(*(scan_chunk(session, c) for c in CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
