"""
live_poll_proof.py
------------------
Simulates exactly what crack_solver.py does while waiting for a giveaway.
Hits the real /api/events/active endpoint 5 times (2s apart) using your
real auth token and prints the exact server response each time.
"""
import asyncio
import aiohttp
import config

ACTIVE_SIGNALS = ["active", "live", "open", "running"]
DEAD_SIGNALS   = ["inactive", "ended", "over", "finished", "not active", "no event", "closed"]

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Step 1: Login to get real token
        login_url = "https://dash.lucidtrading.com/api/mobile/login"
        accounts  = config.LUCID_ACCOUNTS or []
        first     = accounts[0] if accounts else None
        email     = (first["email"]    if isinstance(first, dict) else first[0]) if first else config.LUCID_EMAIL
        password  = (first["password"] if isinstance(first, dict) else first[1]) if first else config.LUCID_PASSWORD

        print(f"🔑 Logging in as {email}...")
        async with session.post(login_url, json={"email": email, "password": password,
                                                  "username": email},
                                headers={"Content-Type": "application/json"}) as resp:
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

        status_url = "https://dash.lucidtrading.com/api/events/active"
        print(f"📡 Polling {status_url} every 2s (5 times)...\n")

        for i in range(1, 6):
            async with session.get(status_url, headers=headers) as resp:
                text = await resp.text()
                raw  = text.lower()

                is_active = any(s in raw for s in ACTIVE_SIGNALS) and \
                            not any(s in raw for s in DEAD_SIGNALS)

                status_emoji = "🚨 GIVEAWAY IS LIVE!" if is_active else "😴 No event yet"
                print(f"  Poll #{i} → HTTP {resp.status} | Response: {text!r}")
                print(f"           → {status_emoji}\n")

            if i < 5:
                await asyncio.sleep(2)

        print("Done. When server returns active=true / status=active,")
        print("crack_solver.py immediately starts solving.")

if __name__ == "__main__":
    asyncio.run(main())
