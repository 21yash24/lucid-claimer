"""
verify_events_submit.py
------------------------
Makes live HTTP requests to dash.lucidtrading.com to show the difference
between the real events API endpoint and a fake one, proving the contract
signature is active on the backend.
"""

import asyncio
import aiohttp
import json

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)"
        }
        
        # 1. Test the real event status endpoint
        url_status = "https://dash.lucidtrading.com/api/events/active"
        print(f"📡 Testing real status endpoint: {url_status}")
        async with session.get(url_status, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text!r}\n")
            
        # 2. Test the real guess submission endpoint
        url_submit = "https://dash.lucidtrading.com/api/events/submit"
        payload = {"code": "12345", "eventId": 1}
        print(f"📡 Testing real submit endpoint: {url_submit}")
        async with session.post(url_submit, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text!r}\n")

        # 3. Test a fake endpoint to show the difference
        url_fake = "https://dash.lucidtrading.com/api/events/nonexistent_fake_endpoint"
        print(f"📡 Testing fake endpoint: {url_fake}")
        async with session.post(url_fake, json=payload, headers=headers) as resp:
            text = await resp.text()
            print(f"   Status: {resp.status}")
            print(f"   Response: {text[:150]!r}\n")

if __name__ == "__main__":
    asyncio.run(main())
