"""
find_checkout_in_js.py
-----------------------
Downloads the Lucid Trading dashboard's JS bundle and searches for
the exact API call and payload used during checkout.
"""

import asyncio
import aiohttp
import re
import logging
import gzip

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("JSHunter")

BASE = "https://dash.lucidtrading.com"
SEARCH_TERMS = [
    "checkout-session", "checkout", "couponCode", "coupon",
    "planId", "stripe", "purchase", "evaluation"
]

async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Encoding": "identity"
    }
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        
        # 1. Load the index page to get JS bundle links
        logger.info("📡 Loading index page...")
        async with session.get(BASE, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            html = await resp.text()
        
        # Find JS bundle filenames
        js_files = re.findall(r'src="(/[^"]*\.js)"', html)
        js_files += re.findall(r"src='(/[^']*\.js)'", html)
        js_files += re.findall(r'"(/js/[^"]*\.js)"', html)
        js_files = list(set(js_files))
        logger.info(f"📦 Found {len(js_files)} JS files: {js_files[:10]}")
        
        if not js_files:
            # Try common vite/webpack chunk patterns
            logger.info("Trying common chunk patterns...")
            js_files = [
                "/js/app.js", "/js/chunk-vendors.js",
                "/assets/index.js", "/static/js/main.js",
                "/app.js"
            ]
        
        # 2. Download each JS file and search for checkout patterns
        for js_path in js_files[:20]:
            url = BASE + js_path
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.text(errors="replace")
                    
                    # Search for checkout-related code
                    for term in SEARCH_TERMS:
                        positions = [m.start() for m in re.finditer(re.escape(term), content)]
                        for pos in positions[:3]:  # Show up to 3 occurrences per term
                            snippet = content[max(0, pos-100):pos+200]
                            if any(api_hint in snippet for api_hint in ["/api/", "post(", "Post(", "axios", "fetch("]):
                                logger.info(f"\n🎯 Found '{term}' in {js_path}:")
                                logger.info(f"   ...{snippet}...")
                                
            except Exception as e:
                logger.debug(f"  {js_path}: {e}")
        
        # 3. Also check the network for XHR intercepting
        logger.info("\n🔍 Done scanning JS bundles.")

if __name__ == "__main__":
    asyncio.run(main())
