"""
test_mobile_events.py
---------------------
Tests both /api/events/ and /api/mobile/events/ variants
to find which one the phone app actually uses for the giveaway.
"""
import asyncio
import aiohttp
import config

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Login
        accounts = config.LUCID_ACCOUNTS or []
        first    = accounts[0] if accounts else None
        email    = (first[0] if isinstance(first, tuple) else first["email"]) if first else config.LUCID_EMAIL
        password = (first[1] if isinstance(first, tuple) else first["password"]) if first else config.LUCID_PASSWORD

        print(f"🔑 Logging in as {email}...")
        async with session.post(
            "https://dash.lucidtrading.com/api/mobile/login",
            json={"email": email, "password": password, "username": email},
            headers={"Content-Type": "application/json"}
        ) as resp:
            data  = await resp.json(content_type=None)
            token = data.get("token")
            if not token:
                print("❌ Login failed"); return
            print("✅ Token obtained!\n")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "User-Agent":    "LucidApp/90.0 (Android; Mobile)"
        }

        # All possible event endpoint variants to test
        endpoints_to_test = [
            ("GET",  "https://dash.lucidtrading.com/api/events/active"),
            ("GET",  "https://dash.lucidtrading.com/api/mobile/events/active"),
            ("GET",  "https://dash.lucidtrading.com/api/mobile/events"),
            ("GET",  "https://dash.lucidtrading.com/api/mobile/giveaway"),
            ("GET",  "https://dash.lucidtrading.com/api/mobile/giveaway/active"),
            ("POST", "https://dash.lucidtrading.com/api/mobile/events/submit"),
            ("POST", "https://dash.lucidtrading.com/api/mobile/giveaway/submit"),
        ]

        print("🔍 Testing all possible mobile giveaway endpoints...\n")
        for method, url in endpoints_to_test:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers, timeout=5) as resp:
                        text = await resp.text()
                        print(f"  {method} {url}")
                        print(f"       → HTTP {resp.status} | {text[:120]!r}\n")
                else:
                    async with session.post(url, json={"code": "TEST", "eventId": 1},
                                            headers=headers, timeout=5) as resp:
                        text = await resp.text()
                        print(f"  {method} {url}")
                        print(f"       → HTTP {resp.status} | {text[:120]!r}\n")
            except Exception as e:
                print(f"  {method} {url} → ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
