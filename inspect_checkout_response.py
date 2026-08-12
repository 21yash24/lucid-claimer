import asyncio
import os
import sys
import aiohttp

async def main():
    email = "yashjha2004@gmail.com"
    password = "Manjoo#1976"
    
    # 1. Login to get token
    login_url = "https://dash.lucidtrading.com/api/mobile/login"
    login_payload = {
        "email": email,
        "password": password,
        "username": email
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "LucidApp/90.0 (Android; Mobile)"
    }
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(login_url, json=login_payload, headers=headers) as resp:
            if resp.status != 200:
                print(f"❌ Login failed: {resp.status}")
                return
            data = await resp.json()
            token = data.get("token")
            print("🔑 Login successful! Token retrieved.")
            
        # 2. Trigger checkout session with a dummy coupon
        checkout_url = "https://dash.lucidtrading.com/api/stripe/checkout-session"
        checkout_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/"
        }
        checkout_payload = {
            "planId": "50k",
            "couponCode": "DUMMYCOUPON"
        }
        
        print("📡 Sending POST request to /api/stripe/checkout-session...")
        async with session.post(checkout_url, json=checkout_payload, headers=checkout_headers) as resp:
            print(f"Status Code: {resp.status}")
            print(f"Headers: {dict(resp.headers)}")
            try:
                json_data = await resp.json()
                print(f"JSON Payload: {json_data}")
            except Exception:
                text = await resp.text()
                print(f"Text Payload: {text}")

if __name__ == "__main__":
    asyncio.run(main())
