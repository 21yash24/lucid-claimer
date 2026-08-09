import asyncio
import aiohttp
import time
import logging
import ssl
import certifi
import config
from typing import List, Dict


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("LucidClaimer")

# SSL context for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

class MultiAccountClaimer:
    """
    High-performance asynchronous claimer that holds open HTTP connections
    and claims giveaway drops across 2-3+ accounts concurrently.
    """

    def __init__(self, api_url: str, account_tokens: List[str]):
        self.api_url = api_url
        self.account_tokens = account_tokens
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
        logger.info(f"Initialized MultiAccountClaimer with {len(self.account_tokens)} accounts.")


    async def refresh_token(self, account_index: int) -> bool:
        """
        Refreshes a token for an account index using credentials.
        """
        if not config.LUCID_EMAIL or not config.LUCID_PASSWORD:
            return False
            
        url = "https://dash.lucidtrading.com/api/mobile/login"
        payload = {
            "email": config.LUCID_EMAIL,
            "password": config.LUCID_PASSWORD,
            "username": config.LUCID_EMAIL
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)",
            "Accept": "application/json"
        }
        
        logger.info(f"🔄 Token expired or missing. Refreshing token for Account #{account_index + 1}...")
        try:
            # We must create a temp session since connection pool connector might not be initialized
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        new_token = data.get("token")
                        if new_token:
                            auth_val = f"Bearer {new_token}"
                            # Update in memory
                            if account_index < len(self.account_tokens):
                                self.account_tokens[account_index] = auth_val
                            else:
                                self.account_tokens.append(auth_val)
                            logger.info(f"🔑 Token refreshed successfully for Account #{account_index + 1}!")
                            return True
                    logger.error(f"❌ Token refresh failed for Account #{account_index + 1} (HTTP {resp.status})")
        except Exception as e:
            logger.error(f"⚠️ Error during token refresh for Account #{account_index + 1}: {e}")
        return False


    async def claim_for_single_account(self, account_index: int, token: str, code: str) -> Dict:
        """
        Submits the giveaway code for a single account token.
        """
        # If token is empty, try to refresh it first
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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Cookie": config.BROWSER_COOKIE
        }

        payload = {
            "secret": code,
            "code": code,
            "key": code
        }

        try:
            async with self.session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                # Check for token expiration and retry once
                if resp.status in (401, 403):
                    logger.warning(f"⚠️ Account #{account_index + 1} token expired. Refreshing token...")
                    if await self.refresh_token(account_index):
                        token = self.account_tokens[account_index]
                        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
                        headers["Authorization"] = auth_header
                        
                        # Retry the POST request once
                        async with self.session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as retry_resp:
                            elapsed_ms = (time.perf_counter() - start_time) * 1000
                            response_text = await retry_resp.text()
                            if retry_resp.status in (200, 201):
                                logger.info(f"⚡ [Account #{account_index + 1}] CLAIM SUCCESS! ({elapsed_ms:.1f}ms) (Retry) Code: {code}")
                                return {"account": account_index + 1, "success": True, "status": retry_resp.status, "time_ms": elapsed_ms}
                            else:
                                logger.warning(f"❌ [Account #{account_index + 1}] Claim failed after token refresh (HTTP {retry_resp.status}) ({elapsed_ms:.1f}ms): {response_text[:100]}")
                                return {"account": account_index + 1, "success": False, "status": retry_resp.status, "error": response_text}
                
                response_text = await resp.text()
                status = resp.status
                
                if status in (200, 201):
                    logger.info(f"⚡ [Account #{account_index + 1}] CLAIM SUCCESS! ({elapsed_ms:.1f}ms) Code: {code}")
                    return {"account": account_index + 1, "success": True, "status": status, "time_ms": elapsed_ms}
                else:
                    logger.warning(f"❌ [Account #{account_index + 1}] Claim failed (HTTP {status}) ({elapsed_ms:.1f}ms): {response_text[:100]}")
                    return {"account": account_index + 1, "success": False, "status": status, "error": response_text}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"⚠️ [Account #{account_index + 1}] Exception during claim ({elapsed_ms:.1f}ms): {e}")
            return {"account": account_index + 1, "success": False, "error": str(e)}

    async def claim_all_accounts(self, code: str):
        """
        Fires simultaneous claim POST requests across ALL configured accounts using asyncio.gather.
        """
        # Ensure we have a token loaded or refreshed at start
        if not self.account_tokens:
            logger.info("Initializing account tokens list from credentials...")
            self.account_tokens = [None]

        logger.info(f"🔥 DROPPED CODE DETECTED: '{code}' — Triggering claim for {len(self.account_tokens)} accounts simultaneously!")
        start_batch = time.perf_counter()

        tasks = [
            self.claim_for_single_account(idx, token, code)
            for idx, token in enumerate(self.account_tokens)
        ]

        # Execute all accounts in parallel at the exact same millisecond
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_elapsed_ms = (time.perf_counter() - start_batch) * 1000
        logger.info(f"🏁 Batch claim finished in {total_elapsed_ms:.1f}ms for all accounts.")
        return results

    async def close(self):
        if self.session:
            await self.session.close()
