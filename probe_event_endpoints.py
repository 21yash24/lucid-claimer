"""
probe_event_endpoints.py
-------------------------
Authenticates using the mobile login API to get a fresh JWT, then probes
various guess and status endpoint combinations to see which ones are real (status != 404/405).
"""

import asyncio
import aiohttp
import sys

sys.path.insert(0, '.')
import config
from crack_solver import MastermindSolver

CANDIDATES = [
    # Event group (based on /api/events/active)
    "https://dash.lucidtrading.com/api/events/guess",
    "https://dash.lucidtrading.com/api/events/submit",
    "https://dash.lucidtrading.com/api/events/crack",
    "https://dash.lucidtrading.com/api/events/claim",
    "https://dash.lucidtrading.com/api/events/check",
    "https://dash.lucidtrading.com/api/events/verify",
    "https://dash.lucidtrading.com/api/events/play",
    
    # Mobile group
    "https://dash.lucidtrading.com/api/mobile/guess",
    "https://dash.lucidtrading.com/api/mobile/submit",
    "https://dash.lucidtrading.com/api/mobile/crack",
    "https://dash.lucidtrading.com/api/mobile/events/guess",
    "https://dash.lucidtrading.com/api/mobile/events/active",
    "https://dash.lucidtrading.com/api/mobile/v1/events/guess",
    
    # Rewards / Mastermind group
    "https://dash.lucidtrading.com/api/rewards/guess",
    "https://dash.lucidtrading.com/api/rewards/crack",
    "https://dash.lucidtrading.com/api/rewards/submit",
    "https://dash.lucidtrading.com/api/rewards/crate",
    "https://dash.lucidtrading.com/api/rewards/crate-status",
    
    # Giveaway group
    "https://dash.lucidtrading.com/api/giveaway/guess",
    "https://dash.lucidtrading.com/api/giveaway/submit",
    "https://dash.lucidtrading.com/api/giveaway/crack"
]

async def test_endpoint(session: aiohttp.ClientSession, url: str, headers: dict):
    # Try GET
    try:
        async with session.get(url, headers=headers, timeout=5) as r:
            body = await r.text()
            print(f"[GET]  Status {r.status} for {url} | body={body[:100].strip()}")
    except Exception as e:
        print(f"[GET]  Error for {url}: {e}")
        
    # Try POST
    try:
        # standard 5-digit mastermind guess payload
        payload = {"code": "12345", "guess": "12345"}
        async with session.post(url, json=payload, headers=headers, timeout=5) as r:
            body = await r.text()
            print(f"[POST] Status {r.status} for {url} | body={body[:100].strip()}")
    except Exception as e:
        print(f"[POST] Error for {url}: {e}")

async def main():
    solver = MastermindSolver(
        token=None,
        cookie=config.BROWSER_COOKIE,
        email=config.LUCID_EMAIL or "yashjha2004@gmail.com",
        password=config.LUCID_PASSWORD or "Manjoo#1976"
    )
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        success = await solver.refresh_token(session)
        if not success:
            print("❌ Login failed. Cannot probe.")
            return
            
        print("🔍 Probing candidate endpoints with active JWT...")
        for url in CANDIDATES:
            await test_endpoint(session, url, solver.headers)
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
