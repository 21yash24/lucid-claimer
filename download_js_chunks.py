"""
download_js_chunks.py
---------------------
Downloads chunk-DHDXS6CO.js and searches it for checkout, stripe, couponCode, 
and HTTP POST/GET endpoint mappings.
"""

import asyncio
import aiohttp
import re
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("ChunkScanner")

CHUNKS = [
    "chunk-DHDXS6CO.js",   # MobileCheckoutComponent
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
    "chunk-VUONRY3T.js",
    "chunk-HVCGLXRO.js",
    "chunk-2FBR3C3O.js",
    "chunk-VXYX7FLX.js",
    "chunk-UJPPAIWO.js",
    "chunk-WWX6BADO.js",
    "chunk-BDBSYBTQ.js"
]

async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://dash.lucidtrading.com/"
    }
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        for chunk in CHUNKS:
            url = f"https://dash.lucidtrading.com/{chunk}"
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        content = await resp.text(errors="replace")
                        logger.info(f"\n📦 Scanned {chunk} ({len(content)} chars):")
                        
                        # Search for API, checkout, coupon, stripe endpoints
                        # Let's search for matches of /api/ or stripe or checkout
                        for pattern in [r'/api/[a-zA-Z0-9_\-/]+', r'stripe', r'coupon', r'checkout']:
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            if matches:
                                logger.info(f"  ✨ Found matches for {pattern}: {list(set(matches))[:10]}")
                                
                            # Search for occurrences and print context
                            for kw in ["/api/", "checkout", "coupon", "stripe"]:
                                idx = content.lower().find(kw)
                                while idx != -1:
                                    snippet = content[max(0, idx-100):min(len(content), idx+200)]
                                    logger.info(f"    Context [{kw}]: {snippet.strip()!r}")
                                    idx = content.lower().find(kw, idx + 1)
                                    # Limit context prints
                                    break
            except Exception as e:
                logger.error(f"Error downloading {chunk}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
