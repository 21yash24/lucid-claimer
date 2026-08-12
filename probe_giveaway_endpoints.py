"""
probe_giveaway_endpoints.py
----------------------------
Probes every plausible giveaway endpoint with a fresh login token
to discover which ones actually respond with real data vs. 204 noise.
"""
import asyncio
import aiohttp
import logging

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("EndpointProbe")

CANDIDATES = [
    # Status endpoints
    ("GET",  "https://dash.lucidtrading.com/api/giveaway/status"),
    ("GET",  "https://dash.lucidtrading.com/api/rewards/status"),
    ("GET",  "https://dash.lucidtrading.com/api/rewards"),
    ("GET",  "https://dash.lucidtrading.com/api/rewards/event"),
    ("GET",  "https://dash.lucidtrading.com/api/rewards/active"),
    ("GET",  "https://dash.lucidtrading.com/api/giveaway"),
    ("GET",  "https://dash.lucidtrading.com/api/giveaway/active"),
    ("GET",  "https://dash.lucidtrading.com/api/giveaway/event"),
    ("GET",  "https://dash.lucidtrading.com/api/mobile/giveaway"),
    ("GET",  "https://dash.lucidtrading.com/api/mobile/giveaway/status"),
    ("GET",  "https://dash.lucidtrading.com/api/mobile/v1/giveaway/status"),
    ("GET",  "https://dash.lucidtrading.com/api/mobile/rewards"),
    ("GET",  "https://dash.lucidtrading.com/api/events"),
    ("GET",  "https://dash.lucidtrading.com/api/events/active"),
    ("GET",  "https://dash.lucidtrading.com/api/game"),
    ("GET",  "https://dash.lucidtrading.com/api/game/status"),
    ("GET",  "https://dash.lucidtrading.com/api/mastermind"),
    ("GET",  "https://dash.lucidtrading.com/api/mastermind/status"),
    # Guess submission endpoints
    ("POST", "https://dash.lucidtrading.com/api/rewards/guess"),
    ("POST", "https://dash.lucidtrading.com/api/giveaway/guess"),
    ("POST", "https://dash.lucidtrading.com/api/rewards/crack-code"),
    ("POST", "https://dash.lucidtrading.com/api/mobile/giveaway/guess"),
    ("POST", "https://dash.lucidtrading.com/api/mobile/v1/giveaway/guess"),
    ("POST", "https://dash.lucidtrading.com/api/game/guess"),
    ("POST", "https://dash.lucidtrading.com/api/mastermind/guess"),
]

GUESS_PAYLOAD = {"code": "A1B2C", "guess": "A1B2C"}

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
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Origin":  "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
        }
        logger.info(f"🔑 Login token: {'✅ got one' if token else '❌ none'}\n")

        logger.info(f"{'METHOD':<6} {'STATUS':<7} {'BODY PREVIEW':<60}  URL")
        logger.info("-"*130)

        for method, url in CANDIDATES:
            try:
                if method == "GET":
                    cm = session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5))
                else:
                    cm = session.post(url, json=GUESS_PAYLOAD, headers=headers, timeout=aiohttp.ClientTimeout(total=5))

                async with cm as resp:
                    text = await resp.text()
                    body_preview = text[:60].replace("\n", " ").strip() if text.strip() else "<empty>"
                    flag = "  ⭐ NON-EMPTY!" if text.strip() and resp.status != 404 else ""
                    logger.info(f"{method:<6} {resp.status:<7} {body_preview:<60}  {url}{flag}")
            except Exception as e:
                logger.info(f"{method:<6} {'ERR':<7} {str(e)[:60]:<60}  {url}")
            
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
