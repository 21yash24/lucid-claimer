"""
dump_plans_response.py
-----------------------
Downloads and saves the full JSON response from dash.lucidtrading.com/api/accounts/plans
so we can inspect the exact dictionary keys and find the product/plan IDs.
"""

import asyncio
import aiohttp
import json

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Login
        async with session.post(
            "https://dash.lucidtrading.com/api/mobile/login",
            json={"email": EMAIL, "password": PASSWORD, "username": EMAIL},
            headers={"Content-Type": "application/json", "User-Agent": "LucidApp/90.0 (Android; Mobile)"}
        ) as resp:
            data = await resp.json(content_type=None)
            token = data.get("token", "")
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/"
        }
        
        url = "https://dash.lucidtrading.com/api/accounts/plans"
        async with session.get(url, headers=headers) as r:
            body = await r.json(content_type=None)
            
        # Write to file
        with open("plans_catalog.json", "w") as f:
            json.dump(body, f, indent=2)
        print("Catalog saved to plans_catalog.json")

if __name__ == "__main__":
    asyncio.run(main())
