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
    and claims giveaway drops across multiple accounts concurrently with auto-login refresh.
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


    async def refresh_token(self, account_index: int) -> bool:
        """
        Refreshes a token for an account index using credentials.
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
        
        logger.info(f"🔄 Token expired or missing. Refreshing token for Account #{account_index + 1} ({email})...")
        try:
            # Check if self.session is active, else use a temporary session
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
        """
        Submits the giveaway code for a single account token with auto-retry and auto-refresh.
        """
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
            "secretCode": code
        }

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    # 401/403 Expiration handler
                    if resp.status in (401, 403):
                        logger.warning(f"⚠️ Account #{account_index + 1} token expired. Refreshing token...")
                        if await self.refresh_token(account_index):
                            token = self.account_tokens[account_index]
                            auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
                            headers["Authorization"] = auth_header
                            continue
                    
                    # 5xx Server Error handler (retry immediately)
                    if resp.status >= 500 and attempt < max_attempts:
                        logger.warning(f"⚠️ [Attempt {attempt}/{max_attempts}] Account #{account_index + 1} server error (HTTP {resp.status}) at {elapsed_ms:.1f}ms. Retrying immediately...")
                        await asyncio.sleep(0.01)  # 10ms micro-pause
                        continue

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
                if attempt < max_attempts:
                    logger.warning(f"⚠️ [Attempt {attempt}/{max_attempts}] Exception during claim ({elapsed_ms:.1f}ms): {e}. Retrying immediately...")
                    await asyncio.sleep(0.01)
                    continue
                logger.error(f"⚠️ [Account #{account_index + 1}] Exception during claim ({elapsed_ms:.1f}ms): {e}")
                return {"account": account_index + 1, "success": False, "error": str(e)}

        return {"account": account_index + 1, "success": False, "error": "Max claim attempts reached"}


    async def claim_all_accounts(self, code: str):
        """
        Fires simultaneous claim POST requests across ALL configured accounts using asyncio.gather.
        """
        if not self.account_tokens and not self.credentials:
            logger.error("No account tokens or login credentials configured to claim drops!")
            return []

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

    async def checkout_all_accounts(self, code: str, plan_id: str = "50k"):
        """
        Performs direct API checkout utilizing 100% off coupon code for all accounts in parallel.
        """
        if not self.account_tokens and not self.credentials:
            logger.error("No account tokens or login credentials configured to checkout plans!")
            return []

        logger.info(f"🛒 Direct API Checkout triggered for plan '{plan_id}' using coupon '{code}'...")
        start_batch = time.perf_counter()

        tasks = [
            self.checkout_single_account(idx, token, code, plan_id)
            for idx, token in enumerate(self.account_tokens)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_elapsed_ms = (time.perf_counter() - start_batch) * 1000
        logger.info(f"🏁 Batch checkout finished in {total_elapsed_ms:.1f}ms for all accounts.")
        return results

    async def checkout_single_account(self, account_index: int, token: str, code: str, plan_id: str) -> Dict:
        """
        Submits coupon using WooCommerce Cart API flow:
          1. POST /cart/add-item (puts product in cart)
          2. POST /cart/apply-coupon (applies discount code)
          3. POST /checkout (completes transaction)
        Supports auto-refresh on 401 and handles Cart-Token propagation.
        """
        if not token:
            if await self.refresh_token(account_index):
                token = self.account_tokens[account_index]
            else:
                return {"account": account_index + 1, "success": False, "error": "No token available"}

        # Map plan labels to WooCommerce Product IDs
        PLAN_PRODUCT_MAP = {
            "25k": 56546,
            "50k": 32272,
            "100k": 32273,
            "150k": 32271
        }
        
        normalized_plan = str(plan_id).lower().replace(" ", "").strip()
        product_id = PLAN_PRODUCT_MAP.get(normalized_plan)
        if not product_id:
            logger.error(f"❌ Invalid plan label: '{plan_id}'. Supported: 25k, 50k, 100k, 150k")
            return {"account": account_index + 1, "success": False, "error": f"Invalid plan: {plan_id}"}

        # Billing details payload for WooCommerce checkout
        billing_payload = {
            "billing_address": {
                "first_name": "Lucid",
                "last_name": "Trader",
                "email": self.credentials[account_index][0] if account_index < len(self.credentials) else "trader@lucidtrading.com",
                "country": "US",
                "state": "TX",
                "city": "Austin",
                "address_1": "123 Main St",
                "postcode": "78701",
                "phone": "5125550199"
            },
            "payment_method": "",
            "payment_data": []
        }

        base_url = "https://lucidtrading.com/wp-json/wc/store/v1"
        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
        
        headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Android; Mobile) LucidApp/90.0",
            "Origin": "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/"
        }

        cart_token = None

        try:
            # ── STEP 1: Add item to cart ──────────────────────────────────
            add_url = f"{base_url}/cart/add-item"
            add_payload = {"id": product_id, "quantity": 1}
            
            logger.info(f"🛒 [Account #{account_index + 1}] Adding Product {product_id} ({normalized_plan}) to cart...")
            async with self.session.post(add_url, json=add_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                text = await resp.text()
                
                # Check for token expiry
                if resp.status in (401, 403):
                    logger.warning(f"🔐 [Account #{account_index + 1}] Auth expired on Cart-Add. Refreshing...")
                    if await self.refresh_token(account_index):
                        token = self.account_tokens[account_index]
                        auth_header = token if token.startswith("Bearer ") else f"Bearer {token}"
                        headers["Authorization"] = auth_header
                        # Retry once
                        async with self.session.post(add_url, json=add_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as r2:
                            text = await r2.text()
                            resp = r2
                    else:
                        return {"account": account_index + 1, "success": False, "error": "Auth refresh failed"}

                if resp.status not in (200, 201):
                    logger.error(f"❌ [Account #{account_index + 1}] Add-to-cart failed (HTTP {resp.status}): {text[:150]}")
                    return {"account": account_index + 1, "success": False, "error": f"Cart add failed: {resp.status}"}

                # Capture Cart-Token from response header
                cart_token = resp.headers.get("Cart-Token") or resp.headers.get("cart-token")
                if cart_token:
                    headers["Cart-Token"] = cart_token
                    logger.debug(f"🔑 Captured Cart-Token: {cart_token[:15]}...")

            # ── STEP 2: Apply Coupon ──────────────────────────────────────
            coupon_url = f"{base_url}/cart/apply-coupon"
            coupon_payload = {"code": code}
            
            logger.info(f"🎟️ [Account #{account_index + 1}] Applying coupon '{code}'...")
            async with self.session.post(coupon_url, json=coupon_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                text = await resp.text()
                
                # Update Cart-Token if sent
                ct = resp.headers.get("Cart-Token") or resp.headers.get("cart-token")
                if ct:
                    cart_token = ct
                    headers["Cart-Token"] = ct

                if resp.status not in (200, 201):
                    # Coupon invalid or expired
                    logger.warning(f"⚠️ [Account #{account_index + 1}] Coupon application rejected (HTTP {resp.status}): {text[:150]}")
                    return {"account": account_index + 1, "success": False, "error": f"Coupon rejected: {resp.status}"}

                logger.info(f"✅ [Account #{account_index + 1}] Coupon '{code}' applied successfully!")

            # ── STEP 3: Complete free order checkout ──────────────────────
            checkout_url = f"{base_url}/checkout"
            
            logger.info(f"🚀 [Account #{account_index + 1}] Completing checkout order...")
            async with self.session.post(checkout_url, json=billing_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                text = await resp.text()
                
                try:
                    resp_json = json.loads(text) if text.strip() else {}
                except Exception:
                    resp_json = {"_raw": text}

                if resp.status in (200, 201):
                    order_id = resp_json.get("order_id") or resp_json.get("id")
                    logger.info(f"🎉🎉 [Account #{account_index + 1}] CHECKOUT SUCCESS! Created Order ID: {order_id}")
                    return {"account": account_index + 1, "success": True, "status": resp.status, "plan": plan_id, "order_id": order_id}
                else:
                    logger.error(f"❌ [Account #{account_index + 1}] Final checkout failed (HTTP {resp.status}): {text[:200]}")
                    return {"account": account_index + 1, "success": False, "status": resp.status, "error": text[:150]}

        except Exception as e:
            logger.error(f"💥 [Account #{account_index + 1}] WooCommerce checkout exception: {e}")
            return {"account": account_index + 1, "success": False, "error": str(e)}

    async def close(self):
        if self.session:
            await self.session.close()
