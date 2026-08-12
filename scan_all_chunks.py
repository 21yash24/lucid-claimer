"""
scan_all_chunks.py
------------------
Downloads all Angular component chunk files and scans their content for:
- API URLs containing '/api/'
- Keywords like 'guess', 'crack', 'vault', 'rewards', 'active'
to find the exact new Mastermind endpoints.
"""

import asyncio
import aiohttp
import re

CHUNKS = [
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
            
            # Search for '/api/'
            api_calls = re.findall(r'"/api/[^"]+"|\'/api/[^\']+\'', content)
            
            # Search for keywords
            matches = []
            for word in ["guess", "crack", "mastermind", "rewards", "vault"]:
                if word in content.lower():
                    matches.append(word)
                    
            if api_calls or matches:
                print(f"\n📂 CHUNK: {chunk_name} ({len(content)} bytes)")
                if matches:
                    print(f"  ✨ Keywords matched: {matches}")
                if api_calls:
                    print(f"  📡 API Paths found: {list(set(api_calls))}")
                
                # Print class details if it defines active/guess/rewards
                for pattern in [r'apiUrl\s*=\s*[^;]+', r'/api/rewards/[a-zA-Z\-]+']:
                    for m in re.finditer(pattern, content):
                        p = m.start()
                        print(f"  🔍 Snippet around '{m.group(0)}': {content[max(0, p-100):min(len(content), p+200)]!r}")
                        
    except Exception as e:
        print(f"❌ Error scanning {chunk_name}: {e}")

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("🔍 Scanning all Angular chunks...")
        await asyncio.gather(*(scan_chunk(session, c) for c in CHUNKS))

if __name__ == "__main__":
    asyncio.run(main())
