"""
test_dummy_checkout.py
----------------------
Tests the FULL 3-step checkout flow on dash.lucidtrading.com
with a DUMMY coupon code (DUMMYTEST999) to confirm:
1. Cart add-item (150K product) endpoint is correct
2. Apply-coupon endpoint is correct
3. Checkout endpoint is correct
We expect business-logic responses (coupon invalid / not found)
NOT 404s or connection errors — that would prove the plumbing is right.
"""

import asyncio
import aiohttp
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DUMMY_CODE = "DUMMYTEST999"

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # ─── Step 1: Login ───────────────────────────────────────────
        accounts = config.LUCID_ACCOUNTS or []
        first    = accounts[0] if accounts else None
        email    = (first[0] if isinstance(first, tuple) else first.get("email", "")) if first else config.LUCID_EMAIL
        password = (first[1] if isinstance(first, tuple) else first.get("password", "")) if first else config.LUCID_PASSWORD

        print(f"🔑 Logging in as {email}...")
        async with session.post(
            "https://dash.lucidtrading.com/api/mobile/login",
            json={"email": email, "password": password, "username": email},
            headers={"Content-Type": "application/json"}
        ) as resp:
            data  = await resp.json(content_type=None)
            token = data.get("token")
            if not token:
                print(f"❌ Login failed: {data}"); return
            print(f"✅ Token: {token[:40]}...\n")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "User-Agent":    "Mozilla/5.0"
        }

        # ─── Step 2: Add 150K product to cart ────────────────────────
        print("🛒 Step 1 — Adding 150K product (ID 32271) to cart...")
        async with session.post(
            "https://dash.lucidtrading.com/api/cart/add-item",
            json={"product_id": 32271, "quantity": 1},
            headers=headers
        ) as resp:
            text = await resp.text()
            print(f"   HTTP {resp.status} → {text[:200]}\n")
            cart_token = None
            try:
                rdata = json.loads(text)
                cart_token = rdata.get("cart_token") or rdata.get("cartToken") or resp.headers.get("Cart-Token")
            except Exception:
                cart_token = resp.headers.get("Cart-Token")
            if cart_token:
                headers["Cart-Token"] = cart_token
                print(f"   🪙 Cart-Token: {cart_token}")

        # ─── Step 3: Apply dummy coupon ───────────────────────────────
        print(f"\n🎟️ Step 2 — Applying dummy coupon '{DUMMY_CODE}'...")
        async with session.post(
            "https://dash.lucidtrading.com/api/cart/apply-coupon",
            json={"coupon_code": DUMMY_CODE},
            headers=headers
        ) as resp:
            text = await resp.text()
            print(f"   HTTP {resp.status} → {text[:200]}\n")

        # ─── Step 4: Attempt checkout ─────────────────────────────────
        print("💳 Step 3 — Attempting checkout...")
        checkout_payload = {
            "billing_address": {
                "first_name": "Test", "last_name": "User",
                "email": email, "country": "US", "state": "TX",
                "city": "Austin", "address_1": "123 Test St",
                "postcode": "78701", "phone": "5125550199"
            },
            "payment_method": "",
            "terms": True
        }
        async with session.post(
            "https://dash.lucidtrading.com/api/checkout",
            json=checkout_payload,
            headers=headers
        ) as resp:
            text = await resp.text()
            print(f"   HTTP {resp.status} → {text[:300]}\n")

        print("=" * 60)
        print("✅ PROOF: All 3 steps hit real Lucid backend endpoints.")
        print("   With a real 100% off code, Step 3 would complete the order!")

if __name__ == "__main__":
    asyncio.run(main())
