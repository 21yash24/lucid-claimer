import sys
import asyncio
import logging
import ssl
import certifi
import aiohttp
import random

# Fix for macOS Python SSL Certificate verification bug
ssl._create_default_https_context = ssl._create_unverified_context

_orig_tcp_init = aiohttp.TCPConnector.__init__
def _patched_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _patched_tcp_init

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from claimer import MultiAccountClaimer
from x_monitor import XMonitor

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("WawaMonitor")

try:
    import playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Set up claimer instance with tokens and credentials
claimer = MultiAccountClaimer(
    config.REDEMPTION_API_URL,
    config.ACCOUNT_TOKENS,
    config.LUCID_ACCOUNTS
)

claimed_codes = set()
successful_claims = 0
MAX_CLAIMS = 2  # Target 2 successful claims before stopping

async def claim_code_callback(code: str, tweet_text: str = ""):
    global successful_claims
    if successful_claims >= MAX_CLAIMS:
        return
    if code in claimed_codes:
        logger.info(f"🔁 Code '{code}' already processed, skipping.")
        return

    claimed_codes.add(code)
    logger.info(f"⚡ CODE SPOTTED: '{code}' — firing all claim + checkout flows in parallel...")

    # Determine target plans from tweet text
    text_lower = tweet_text.lower() if tweet_text else ""
    if "100k" in text_lower:
        plans_to_try = ["100k"]
    elif "50k" in text_lower and "25k" not in text_lower:
        plans_to_try = ["50k"]
    elif "25k" in text_lower and "50k" not in text_lower:
        plans_to_try = ["25k"]
    else:
        # Try both plans in parallel — covers any ambiguous tweet
        plans_to_try = ["50k", "25k"]

    logger.info(f"🎯 Plans to try: {plans_to_try}")

    # 1. PRIMARY: Direct checkout API — fastest path, runs for ALL plans in parallel
    checkout_tasks = []
    for plan in plans_to_try:
        checkout_tasks.append(asyncio.create_task(claimer.checkout_all_accounts(code, plan)))

    # 2. BACKUP: Secret-code redemption API (in case checkout isn't the right endpoint)
    redemption_task = asyncio.create_task(claimer.claim_all_accounts(code))

    # 3. PLAYWRIGHT: browser-based checkout if available (best-effort)
    if PLAYWRIGHT_AVAILABLE:
        try:
            from checkout_buyer import purchase_evaluation_account
            asyncio.create_task(purchase_evaluation_account(code))
        except Exception as e:
            logger.debug(f"Playwright not available: {e}")

    # Wait for redemption results and update counter
    redemption_results = await redemption_task
    for res in (redemption_results or []):
        if isinstance(res, dict) and res.get("success"):
            successful_claims += 1
            logger.info(f"🎉 REDEMPTION CLAIM SUCCESS ({successful_claims}/{MAX_CLAIMS})!")

    # Also track checkout successes
    for task in checkout_tasks:
        try:
            checkout_results = await task
            for res in (checkout_results or []):
                if isinstance(res, dict) and res.get("success"):
                    successful_claims += 1
                    logger.info(f"🎉 CHECKOUT SUCCESS ({successful_claims}/{MAX_CLAIMS}) — Plan: {res.get('plan', '?')}!")
        except Exception:
            pass

    if successful_claims >= MAX_CLAIMS:
        logger.info("🏆 Target claims reached! Shutting down.")
        sys.exit(0)

async def main():
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors found in .env:")
        for err in errors:
            logger.error(f" - {err}")
        sys.exit(1)

    # Initialize persistent HTTP session pool
    await claimer.initialize()

    # Initialize and launch the X Monitor
    x_monitor = XMonitor(claim_code_callback)
    x_initialized = await x_monitor.initialize()
    if x_initialized:
        logger.info("🐦 X Monitor background loop starting...")
        await x_monitor.poll_timeline()
    else:
        logger.error("❌ X Monitor initialization failed. Please check credentials or cookies.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopping X Monitor...")
    finally:
        # Close HTTP session pool
        asyncio.run(claimer.close())
