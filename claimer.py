"""
claimer.py
----------
High-performance asynchronous claimer for Lucid Trading giveaways.
- Uses Mobile App API headers (LucidApp/90.0) to bypass Cloudflare desktop browser WAF challenges (HTTP 429).
- Stops retrying an account after HTTP 429 and temporarily skips that account.
- Executes parallel claims across accounts when they are not rate limited.
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

ssl_context = ssl.create_default_context(cafile=certifi.where())


class MultiAccountClaimer:
    """Asynchronous claimer that tracks per-account rate-limit cooldowns."""

    def __init__(self, api_url: str, account_tokens: List[str] = None, credentials: List[Tuple[str, str]] = None):
        self.api_url = api_url
        self.account_tokens = account_tokens or []
        self.credentials = credentials or []
        self.session: aiohttp.ClientSession = None
        # account index -> monotonic timestamp until which claims are skipped
        self.rate_limited_until: Dict[int, float] = {}

    def is_rate_limited(self, account_index: int) -> bool:
        """Return True while this account is in its HTTP 429 cooldown window."""
        return time.monotonic() < self.rate_limited_until.get(account_index, 0.0)

    def mark_rate_limited(self, account_index: int, retry_after: float = None) -> float:
        """Put an account on cooldown after HTTP 429 and return the cooldown seconds."""
        cooldown = retry_after if retry_after and retry_after > 0 else config.RATE_LIMIT_COOLDOWN
        self.rate_limited_until[account_index] = time.monotonic() + cooldown
        return cooldown

    async def initialize(self):
        """Creates a persistent aiohttp ClientSession with TCP connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=100,
            ttl_dns_cache=300,
            keepalive_timeout=60,
            ssl=False
        )

        self.session = aiohttp.ClientSession(connector=connector)

        while len(self.account_tokens) < len(self.credentials):
            self.account_tokens.append(None)

        for idx, token in enumerate(self.account_tokens):
            if not token and idx < len(self.credentials):
                await self.refresh_token(idx)

        logger.info(f"Initialized MultiAccountClaimer with {len(self.account_tokens)} account(s).")

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def refresh_token(self, account_index: int) -> bool:
        """Refreshes a token for an account index using the mobile login endpoint."""
        if account_index >= len(self.credentials):
            logger.error(f"❌ Cannot refresh token: No credentials configured for Account #{account_index + 1}")
            return False

        email, password = self.credentials[account_index]
        url = "https://dash.lucidtrading.com/api/mobile/login"
        payload = {"email": email, "password": password, "username": email}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }

        logger.info(f"🔄 Refreshing authentication token for Account #{account_index + 1} ({email})...")
        try:
            sess = self.session if (self.session and not self.session.closed) else aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
            try:
                async with sess.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
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

    async def claim_for_single_account(self, account_index: int, token: str, code: str) -> Dict:
        """Submits a giveaway code for one account, without retrying HTTP 429."""
        if self.is_rate_limited(account_index):
            remaining = max(0.0, self.rate_limited_until[account_index] - time.monotonic())
            logger.info(f"⏭️ [Account #{account_index + 1}] Still rate limited; skipping claim for '{code}' ({remaining:.1f}s left).")
            return {
                "account": account_index + 1,
                "success": False,
                "status": 429,
                "error": "Account temporarily rate limited"
            }

        if not token:
            if await self.refresh_token(account_index):
                token = self.account_tokens[account_index]
            else:
                return {"account": account_index + 1, "success": False, "error": "No token available"}

        start_time = time.perf_counter()
        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }
        payload = {"secretCode": code}

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    response_text = await resp.text()
                    status = resp.status

                    # HTTP 429 is a hard stop for this account. Do NOT retry the same request.
                    if status == 429:
                        retry_after = None
                        retry_header = resp.headers.get("Retry-After")
                        if retry_header:
                            try:
                                retry_after = float(retry_header)
                            except ValueError:
                                pass
                        cooldown = self.mark_rate_limited(account_index, retry_after)
                        logger.warning(
                            f"⚠️ [Account #{account_index + 1}] Rate Limited (HTTP 429) at {elapsed_ms:.1f}ms. "
                            f"Stopping retries for this account for {cooldown:.1f}s."
                        )
                        return {
                            "account": account_index + 1,
                            "success": False,
                            "status": 429,
                            "error": response_text,
                            "rate_limited": True,
                            "cooldown": cooldown
                        }

                    # 401/403 expiration handler
                    if status in (401, 403):
                        logger.warning(f"⚠️ Account #{account_index + 1} token expired. Refreshing token...")
                        if await self.refresh_token(account_index):
                            token = self.account_tokens[account_index]
                            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
                            continue

                    # 5xx server errors can still be retried once.
                    if status >= 500 and attempt < max_attempts:
                        logger.warning(f"⚠️ [Attempt {attempt}/{max_attempts}] Account #{account_index + 1} server error (HTTP {status}) at {elapsed_ms:.1f}ms. Retrying...")
                        await asyncio.sleep(0.1)
                        continue

                    if status in (200, 201):
                        logger.info(f"⚡ [Account #{account_index + 1}] CLAIM SUCCESS! ({elapsed_ms:.1f}ms) Code: {code}")
                        return {"account": account_index + 1, "success": True, "status": status, "time_ms": elapsed_ms, "response": response_text}

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

    async def claim_all_accounts(self, code: str):
        """Claims concurrently across accounts that are not currently rate limited."""
        if not self.account_tokens and not self.credentials:
            logger.error("No account tokens or login credentials configured to claim drops!")
            return []

        available_accounts = [
            (idx, token)
            for idx, token in enumerate(self.account_tokens)
            if not self.is_rate_limited(idx)
        ]

        if not available_accounts:
            logger.info(f"⏭️ All accounts are rate limited; skipping code '{code}' without making another API request.")
            return []

        logger.info(f"🔥 DROPPED CODE DETECTED: '{code}' — Claiming across {len(available_accounts)} available account(s)...")
        start_batch = time.perf_counter()

        tasks = [
            self.claim_for_single_account(idx, token, code)
            for idx, token in available_accounts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_elapsed_ms = (time.perf_counter() - start_batch) * 1000
        logger.info(f"🏁 Claim finished in {total_elapsed_ms:.1f}ms for available accounts.")
        return results
