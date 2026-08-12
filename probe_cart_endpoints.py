"""
probe_cart_endpoints.py
-----------------------
Probes all possible WooCommerce / custom cart API endpoint patterns
on dash.lucidtrading.com to find which ones return real business responses.
"""
import asyncio
import aiohttp
import ssl
import sys, os

ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Login
        accounts = config.LUCID_ACCOUNTS or []
        first    = accounts[0] if accounts else None
        email    = (first[0] if isinstance(first, tuple) else first.get("email","")) if first else config.LUCID_EMAIL
        password = (first[1] if isinstance(first, tuple) else first.get("password","")) if first else config.LUCID_PASSWORD

        async with session.post(
            "https://dash.lucidtrading.com/api/mobile/login",
            json={"email": email, "password": password, "username": email},
            headers={"Content-Type": "application/json"}
        ) as resp:
            data = await resp.json(content_type=None)
            token = data.get("token")
            print(f"✅ Token: {token[:30]}...\n")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        # WooCommerce standard + custom variations to probe
        endpoints = [
            ("GET",  "https://dash.lucidtrading.com/wp-json/wc/store/v1/cart"),
            ("POST", "https://dash.lucidtrading.com/wp-json/wc/store/v1/cart/add-item", {"id": 32271, "quantity": 1}),
            ("POST", "https://dash.lucidtrading.com/wp-json/wc/v3/cart/apply-coupon", {"code": "TEST"}),
            ("GET",  "https://dash.lucidtrading.com/wp-json/wc/v3/products/32271"),
            ("GET",  "https://dash.lucidtrading.com/wp-json/wc/store/v1/products/32271"),
            ("POST", "https://dash.lucidtrading.com/api/cart", {"product_id": 32271}),
            ("POST", "https://dash.lucidtrading.com/api/cart/items", {"product_id": 32271, "quantity": 1}),
            ("POST", "https://dash.lucidtrading.com/api/order", {"product_id": 32271, "coupon": "TEST"}),
            ("POST", "https://dash.lucidtrading.com/api/orders", {"product_id": 32271}),
            ("POST", "https://dash.lucidtrading.com/api/purchase", {"product_id": 32271, "coupon": "TEST"}),
            ("POST", "https://dash.lucidtrading.com/api/mobile/cart/add", {"product_id": 32271, "quantity": 1}),
            ("POST", "https://dash.lucidtrading.com/api/mobile/purchase", {"product_id": 32271, "coupon": "TEST"}),
            ("POST", "https://dash.lucidtrading.com/api/mobile/order", {"product_id": 32271, "coupon": "TEST"}),
            ("GET",  "https://dash.lucidtrading.com/api/plans"),
            ("GET",  "https://dash.lucidtrading.com/api/mobile/plans"),
            ("GET",  "https://dash.lucidtrading.com/api/products"),
        ]

        print("🔍 Probing all possible cart/checkout endpoints...\n")
        for entry in endpoints:
            method = entry[0]
            url    = entry[1]
            body   = entry[2] if len(entry) > 2 else None
            try:
                if method == "GET":
                    async with session.get(url, headers=headers, timeout=5) as resp:
                        text = await resp.text()
                        marker = "✅ REAL" if resp.status != 204 and text.strip() else "❌ 204/empty"
                        print(f"  {marker} | {method} {url}")
                        if resp.status != 204 and text.strip():
                            print(f"         → HTTP {resp.status}: {text[:150]}")
                else:
                    async with session.post(url, json=body, headers=headers, timeout=5) as resp:
                        text = await resp.text()
                        marker = "✅ REAL" if resp.status != 204 and text.strip() else "❌ 204/empty"
                        print(f"  {marker} | {method} {url}")
                        if resp.status != 204 and text.strip():
                            print(f"         → HTTP {resp.status}: {text[:150]}")
            except Exception as e:
                print(f"  ⚠️ ERROR | {method} {url} → {e}")

if __name__ == "__main__":
    asyncio.run(main())
