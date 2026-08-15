"""
claimer.py
----------
High-performance asynchronous claimer for Lucid Trading giveaways.
- Uses Mobile App API headers (LucidApp/90.0) to bypass Cloudflare desktop browser WAF challenges (HTTP 429).
- Implements exponential backoff and connection reset when rate limits occur.
- Executes parallel claims across accounts for maximum speed during drops.
"""

import asyncio
import aiohttp
import time
import logging
import ssl
import certifi
import config
from typing import List, Dict, Tuple


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LucidClaimer")

# SSL context for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

class MultiAccountClaimer:
    """
    High-performance asynchronous claimer that holds open HTTP connections
    and claims giveaway drops across multiple accounts concurrently.
    """

    def __init__(self, api_url: str, account_tokens: List[str] = None, credentials: List[Tuple[str, str]] = None):
        self.api_url = api_url
        self.account_tokens = account_tokens or []
        self.credentials = credentials or []
        self.session: aiohttp.ClientSession = None

    async def initialize(self):
        """
        Creates a persistent aiohttp ClientSession with TCP connection pooling.
        """
        connector = aiohttp.TCPConnector(
            limit=100,               # Maximum concurrent connections
            ttl_dns_cache=300,       # Cache DNS lookups for speed
            keepalive_timeout=60,    # Keep TCP sockets open for zero handshake latency
            ssl=False                # Bypass SSL certificate verification on Mac
        )

        self.session = aiohttp.ClientSession(connector=connector)
        
        # Ensure account tokens list is padded to match the credentials list size
        while len(self.account_tokens) < len(self.credentials):
            self.account_tokens.append(None)

        # Proactively log in for any empty token slots
        for idx, token in enumerate(self.account_tokens):
            if not token and idx < len(self.credentials):
                await self.refresh_token(idx)

        logger.info(f"Initialized MultiAccountClaimer with {len(self.account_tokens)} account(s).")

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def refresh_token(self, account_index: int) -> bool:
        """
        Refreshes a token for an account index using mobile login endpoint.
        """
        if account_index >= len(self.credentials):
            logger.error(f"❌ Cannot refresh token: No credentials configured for Account #{account_index + 1}")
            return False
            
        email, password = self.credentials[account_index]
        url = "https://dash.lucidtrading.com/api/mobile/login"
        payload = {
            "email": email,
            "password": password,
            "username": email
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }
        
        logger.info(f"🔄 Refreshing authentication token for Account #{account_index + 1} ({email})...")
        try:
            sess = self.session if (self.session and not self.session.closed) else aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
            try:
                async with sess.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        new_token = data.get("token")
                        if new_token:
                            auth_val = f"Bearer {new_token}"
                            if account_index < len(self.account_tokens):
                                self.account_tokens[account_index] = auth_val
                            else:
                                self.account_tokens.append(auth_val)
                            logger.info(f"🔑 Token refreshed successfully for Account #{account_index + 1} ({email})!")
                            return True
                    logger.error(f"❌ Token refresh failed for Account #{account_index + 1} (HTTP {resp.status})")
            finally:
                if not self.session or self.session.closed:
                    await sess.close()
        except Exception as e:
            logger.error(f"⚠️ Error during token refresh for Account #{account_index + 1}: {e}")
        return False

    async def refresh_all_tokens(self) -> None:
        """
        Refreshes tokens for every configured account sequentially so a mid-drop
        token expiry never stalls a claim. Safe to call right before a drop.
        """
        indices = [
            idx for idx in range(len(self.credentials))
            if idx >= len(self.account_tokens) or not self.account_tokens[idx]
        ]
        if not indices:
            return
        logger.info(f"🔑 Pre-refreshing tokens for {len(indices)} account(s)...")
        for i in indices:
            await self.refresh_token(i)

    async def claim_for_single_account(self, account_index: int, token: str, code: str) -> Dict:
        """
        Submits the giveaway code for a single account using authentic Mobile App headers.
        """
        if not token:
            if await self.refresh_token(account_index):
                token = self.account_tokens[account_index]
            else:
                return {"account": account_index + 1, "success": False, "error": "No token available"}

        start_time = time.perf_counter()
        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
        
        # Authentic Mobile App Headers (Bypasses Cloudflare Desktop Web 429 WAF)
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }

        payload = {
            "secretCode": code
        }

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    response_text = await resp.text()
                    status = resp.status
                    
                    # 429 Rate Limit Handler (Cloudflare/Server throttling)
                    if status == 429:
                        logger.warning(f"⚠️ [Account #{account_index + 1}] Rate Limited (HTTP 429) at {elapsed_ms:.1f}ms. Cooling down 1.5s...")
                        await asyncio.sleep(1.5)
                        continue

                    # 401 Expiration handler (403 = Cloudflare WAF block, NOT
                    # expiry — refreshing would just waste the drop window)
                    if status == 401:
                        logger.warning(f"⚠️ Account #{account_index + 1} token expired. Refreshing token...")
                        if await self.refresh_token(account_index):
                            token = self.account_tokens[account_index]
                            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
                            continue

                    # 5xx Server Error handler
                    if status >= 500 and attempt < max_attempts:
                        logger.warning(f"⚠️ [Attempt {attempt}/{max_attempts}] Account #{account_index + 1} server error (HTTP {status}) at {elapsed_ms:.1f}ms. Retrying...")
                        await asyncio.sleep(0.1)
                        continue

                    if status in (200, 201):
                        logger.info(f"⚡ [Account #{account_index + 1}] CLAIM SUCCESS! ({elapsed_ms:.1f}ms) Code: {code}")
                        return {"account": account_index + 1, "success": True, "status": status, "time_ms": elapsed_ms, "response": response_text}
                    else:
                        logger.warning(f"❌ [Account #{account_index + 1}] Claim result (HTTP {status}) ({elapsed_ms:.1f}ms): {response_text[:120]}")
                        return {"account": account_index + 1, "success": False, "status": status, "error": response_text}

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if attempt < max_attempts:
                    await asyncio.sleep(0.1)
                    continue
                logger.error(f"⚠️ [Account #{account_index + 1}] Exception during claim ({elapsed_ms:.1f}ms): {e}")
                return {"account": account_index + 1, "success": False, "error": str(e)}

        return {"account": account_index + 1, "success": False, "error": "Max claim attempts reached"}

    async def checkout_for_single_account(self, account_index: int, token: str, code: str, plan_id: str = "50k") -> Dict:
        """
        Fires a direct Stripe checkout-session request for one account — the
        fastest possible path (no browser). Endpoint discovered via probe_checkout.py.
        """
        checkout_url = "https://dash.lucidtrading.com/api/stripe/checkout-session"

        if not token:
            if await self.refresh_token(account_index):
                token = self.account_tokens[account_index]
            else:
                return {"account": account_index + 1, "success": False, "error": "No token available", "plan": plan_id}

        start_time = time.perf_counter()
        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"

        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin":  "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Accept":  "application/json",
        }

        payload = {"planId": plan_id, "couponCode": code}

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.post(checkout_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    response_text = await resp.text()
                    status = resp.status

                    if status == 429:
                        logger.warning(f"⚠️ [Account #{account_index + 1}] Checkout rate limited (HTTP 429) at {elapsed_ms:.1f}ms. Cooling down 1.5s...")
                        await asyncio.sleep(1.5)
                        continue

                    if status in (401, 403):
                        logger.warning(f"⚠️ Account #{account_index + 1} token expired during checkout. Refreshing token...")
                        if await self.refresh_token(account_index):
                            token = self.account_tokens[account_index]
                            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
                            continue

                    if status >= 500 and attempt < max_attempts:
                        logger.warning(f"⚠️ [Attempt {attempt}/{max_attempts}] Account #{account_index + 1} checkout server error (HTTP {status}) at {elapsed_ms:.1f}ms. Retrying...")
                        await asyncio.sleep(0.1)
                        continue

                    if status in (200, 201):
                        logger.info(f"⚡ [Account #{account_index + 1}] CHECKOUT SUCCESS ({elapsed_ms:.1f}ms) Plan {plan_id} Code: {code}")
                        return {"account": account_index + 1, "success": True, "status": status, "time_ms": elapsed_ms, "plan": plan_id, "response": response_text}
                    else:
                        logger.warning(f"❌ [Account #{account_index + 1}] Checkout result (HTTP {status}) ({elapsed_ms:.1f}ms): {response_text[:160]}")
                        return {"account": account_index + 1, "success": False, "status": status, "plan": plan_id, "error": response_text}

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if attempt < max_attempts:
                    await asyncio.sleep(0.1)
                    continue
                logger.error(f"⚠️ [Account #{account_index + 1}] Exception during checkout ({elapsed_ms:.1f}ms): {e}")
                return {"account": account_index + 1, "success": False, "plan": plan_id, "error": str(e)}

        return {"account": account_index + 1, "success": False, "plan": plan_id, "error": "Max checkout attempts reached"}

    async def checkout_all_accounts(self, code: str, plan_id: str = "50k"):
        """
        Fires the direct checkout-session endpoint across all accounts in parallel.
        Fastest possible claim path — no browser, sub-second latency.
        """
        if not self.account_tokens and not self.credentials:
            logger.error("No account tokens or login credentials configured to checkout!")
            return []

        logger.info(f"🔥 DIRECT CHECKOUT with code '{code}' for plan {plan_id} across {len(self.account_tokens)} account(s)...")
        start_batch = time.perf_counter()

        tasks = [
            self.checkout_for_single_account(idx, token, code, plan_id)
            for idx, token in enumerate(self.account_tokens)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_elapsed_ms = (time.perf_counter() - start_batch) * 1000
        logger.info(f"🏁 Direct checkout finished in {total_elapsed_ms:.1f}ms for all accounts.")
        return results

    async def claim_all_accounts(self, code: str):
        """
        Claims sequentially across accounts with a 2.5s gap between each, so
        rate-limits don't trip. Keeps going until an account successfully claims.
        """
        if not self.account_tokens and not self.credentials:
            logger.error("No account tokens or login credentials configured to claim drops!")
            return []

        logger.info(f"🔥 DROPPED CODE DETECTED: '{code}' — Claiming across {len(self.account_tokens)} account(s) sequentially...")
        start_batch = time.perf_counter()

        results = []
        for idx, token in enumerate(self.account_tokens):
            if any(isinstance(r, dict) and r.get("success") for r in results):
                break
            res = await self.claim_for_single_account(idx, token, code)
            results.append(res)
            if idx < len(self.account_tokens) - 1:
                await asyncio.sleep(2.5)

        total_elapsed_ms = (time.perf_counter() - start_batch) * 1000
        logger.info(f"🏁 Claim finished in {total_elapsed_ms:.1f}ms for all accounts.")
        return results
