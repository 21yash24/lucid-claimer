"""
test_events_submit.py
---------------------
Logs in programmatically to get a fresh mobile auth token, then queries
the active status and guess submission event endpoints to verify their
validity on the live server.
"""

import asyncio
import aiohttp
import json
import config

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: Programmatic Login
        login_url = "https://dash.lucidtrading.com/api/mobile/login"
        login_payload = {
            "email": config.LUCID_EMAIL or "yashjha2004@gmail.com",
            "password": config.LUCID_PASSWORD or "Manjoo#1976",
            "username": config.LUCID_EMAIL or "yashjha2004@gmail.com"
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }
        
        print("🔑 Logging in to fetch auth token...")
        async with session.post(login_url, json=login_payload, headers=headers) as resp:
            if resp.status != 200:
                print(f"❌ Login failed: HTTP {resp.status}")
                return
            res_data = await resp.json()
            token = res_data.get("token")
            if not token:
                print("❌ No token returned in login response")
                return
            print("✅ Token obtained successfully!")
            
        # Add Authorization header
        headers["Authorization"] = f"Bearer {token}"
        
        # Step 2: Test real event status endpoint
        url_status = "https://dash.lucidtrading.com/api/events/active"
        print(f"\n📡 Testing real status endpoint: {url_status}")
        async with session.get(url_status, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text!r}")
            
        # Step 3: Test real guess submission endpoint
        url_submit = "https://dash.lucidtrading.com/api/events/submit"
        payload = {"code": "12345", "eventId": 1}
        print(f"\n📡 Testing real submit endpoint: {url_submit}")
        async with session.post(url_submit, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text!r}")

        # Step 4: Test a fake endpoint to show the difference
        url_fake = "https://dash.lucidtrading.com/api/events/nonexistent_fake_endpoint"
        print(f"\n📡 Testing fake endpoint: {url_fake}")
        async with session.post(url_fake, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text[:150]!r}")

if __name__ == "__main__":
    asyncio.run(main())
