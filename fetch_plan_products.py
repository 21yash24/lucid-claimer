"""
fetch_plan_products.py
-----------------------
Logs in and fetches the plans / products catalog from dash.lucidtrading.com's API
to find the exact product IDs for 25k, 50k, and 100k accounts.
"""

import asyncio
import aiohttp
import json
import logging

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("CatalogFetcher")

# Common product/plan endpoints on WooCommerce / dashboard
ENDPOINTS = [
    "https://dash.lucidtrading.com/api/products",
    "https://dash.lucidtrading.com/api/plans",
    "https://dash.lucidtrading.com/api/mobile/products",
    "https://dash.lucidtrading.com/api/mobile/v1/products",
    "https://dash.lucidtrading.com/api/accounts/plans",
    "https://dash.lucidtrading.com/api/stripe/products",
    "https://lucidtrading.com/wp-json/wc/store/v1/products",
]

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Login to get fresh JWT token
        async with session.post(
            "https://dash.lucidtrading.com/api/mobile/login",
            json={"email": EMAIL, "password": PASSWORD, "username": EMAIL},
            headers={"Content-Type": "application/json", "User-Agent": "LucidApp/90.0 (Android; Mobile)"}
        ) as resp:
            data = await resp.json(content_type=None)
            token = data.get("token", "")
            
        logger.info(f"🔑 Auth token acquired: {'✅ Yes' if token else '❌ No'}")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/"
        }
        
        for url in ENDPOINTS:
            logger.info(f"📡 Querying: {url} ...")
            try:
                async with session.get(url, headers=headers, timeout=10) as r:
                    text = await r.text()
                    logger.info(f"   Status: {r.status}")
                    if r.status == 200:
                        try:
                            body = json.loads(text)
                            logger.info(f"   SUCCESS! Found {len(body)} items. Preview:")
                            # If it's a list
                            if isinstance(body, list):
                                for item in body[:10]:
                                    p_id = item.get("id") or item.get("productId") or item.get("id")
                                    name = item.get("name") or item.get("name") or item.get("title")
                                    price = item.get("price") or item.get("prices", {}).get("price")
                                    logger.info(f"     👉 ID: {p_id} | Name: {name} | Price: {price}")
                            # If it's a dict
                            elif isinstance(body, dict):
                                logger.info(f"     Keys: {list(body.keys())}")
                                # Print first few keys
                                for k, v in list(body.items())[:3]:
                                    logger.info(f"     Key {k}: {str(v)[:200]}")
                        except Exception as parse_err:
                            logger.info(f"   Failed to parse JSON, body preview: {text[:200]!r}")
            except Exception as e:
                logger.error(f"   Error: {e}")
                
if __name__ == "__main__":
    asyncio.run(main())
