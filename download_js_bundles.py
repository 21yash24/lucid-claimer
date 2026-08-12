"""
download_js_bundles.py
-----------------------
Bypasses Cloudflare to download dash.lucidtrading.com's compiled JS files
and searches them for API endpoints, specifically coupon, checkout, and stripe.
"""

import asyncio
import aiohttp
import re
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("JSDownloader")

async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://dash.lucidtrading.com/"
    }
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        logger.info("📡 Loading index page html to parse script tags...")
        async with session.get("https://dash.lucidtrading.com/", timeout=10) as resp:
            html = await resp.text()
            logger.info(f"Loaded index: status={resp.status}")

        # Find JS bundles in the HTML
        bundles = re.findall(r'src="([^"]+\.js)"', html)
        bundles += re.findall(r"src='([^']+\.js)'", html)
        logger.info(f"Found scripts: {bundles}")

        for script in bundles:
            if script.startswith("http"):
                url = script
            else:
                url = f"https://dash.lucidtrading.com/{script.lstrip('/')}"
            logger.info(f"📥 Downloading: {url} ...")
            try:
                async with session.get(url, timeout=15) as r:
                    if r.status == 200:
                        content = await r.text(errors="replace")
                        logger.info(f"  Downloaded {len(content)} chars.")
                        
                        # Search for coupons / checkouts / stripe
                        matches = []
                        for word in ["coupon", "stripe/checkout", "checkout-session", "checkout", "redeem"]:
                            pos = [m.start() for m in re.finditer(re.escape(word), content)]
                            if pos:
                                logger.info(f"  ✨ Found word '{word}' at positions: {pos[:5]}")
                                for p in pos[:3]:
                                    snippet = content[max(0, p-80):min(len(content), p+120)]
                                    logger.info(f"    Snippet: {snippet.strip()!r}")
            except Exception as e:
                logger.error(f"  Error on {url}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
