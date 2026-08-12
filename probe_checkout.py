"""
probe_checkout.py
------------------
Logs in fresh, then fires the checkout-session endpoint with many different 
payload variations to find the one that actually creates a real order.
Watch for HTTP status != 204 (should get 200/201 with an order body, or an
error message that tells us exactly what field names the server expects).
"""

import asyncio
import aiohttp
import logging

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

CHECKOUT_URL = "https://dash.lucidtrading.com/api/stripe/checkout-session"
LOGIN_URL    = "https://dash.lucidtrading.com/api/mobile/login"
TEST_COUPON  = "LIPE50100"   # use a real coupon you already tested

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("CheckoutProbe")


async def login(session: aiohttp.ClientSession) -> str:
    async with session.post(
        LOGIN_URL,
        json={"email": EMAIL, "password": PASSWORD, "username": EMAIL},
        headers={"Content-Type": "application/json", "User-Agent": "LucidApp/90.0 (Android; Mobile)"}
    ) as resp:
        data = await resp.json(content_type=None)
        token = data.get("token", "")
        logger.info(f"🔑 Login status={resp.status}  token={'✅ got one' if token else '❌ none'}")
        return token


async def try_payload(session: aiohttp.ClientSession, headers: dict, label: str, payload: dict):
    try:
        async with session.post(CHECKOUT_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            text = await resp.text()
            logger.info(f"  [{label}]  status={resp.status}  body={text[:200]!r}")
    except Exception as e:
        logger.error(f"  [{label}]  ERROR: {e}")


async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        token = await login(session)
        auth  = f"Bearer {token}"
        headers = {
            "Authorization": auth,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin":  "https://dash.lucidtrading.com",
            "Referer": "https://dash.lucidtrading.com/",
            "Accept":  "application/json",
        }

        logger.info(f"\n{'='*60}")
        logger.info(f"Probing checkout endpoint with coupon: {TEST_COUPON}")
        logger.info(f"{'='*60}\n")

        # ── Variation 1: Current bot payload ──────────────────────────────
        await try_payload(session, headers, "planId+couponCode / 50k", {
            "planId": "50k", "couponCode": TEST_COUPON
        })
        await try_payload(session, headers, "planId+couponCode / 25k", {
            "planId": "25k", "couponCode": TEST_COUPON
        })

        # ── Variation 2: Different field names ────────────────────────────
        await try_payload(session, headers, "plan+coupon / 50k", {
            "plan": "50k", "coupon": TEST_COUPON
        })
        await try_payload(session, headers, "plan+couponCode / 50k", {
            "plan": "50k", "couponCode": TEST_COUPON
        })
        await try_payload(session, headers, "planId+code / 50k", {
            "planId": "50k", "code": TEST_COUPON
        })

        # ── Variation 3: Numeric / slug plan IDs ─────────────────────────
        await try_payload(session, headers, "planId=50000+couponCode", {
            "planId": "50000", "couponCode": TEST_COUPON
        })
        await try_payload(session, headers, "planId=LUCIDPRO50K+couponCode", {
            "planId": "LUCIDPRO50K", "couponCode": TEST_COUPON
        })
        await try_payload(session, headers, "planId=lucidpro-50k+couponCode", {
            "planId": "lucidpro-50k", "couponCode": TEST_COUPON
        })
        await try_payload(session, headers, "planId=LucidFlex50K_NT_TDV+couponCode", {
            "planId": "LucidFlex50K_NT_TDV", "couponCode": TEST_COUPON
        })

        # ── Variation 4: productId instead of planId ─────────────────────
        await try_payload(session, headers, "productId+couponCode / 50k", {
            "productId": "50k", "couponCode": TEST_COUPON
        })

        # ── Variation 5: no planId, just coupon ───────────────────────────
        await try_payload(session, headers, "couponCode only", {
            "couponCode": TEST_COUPON
        })

        logger.info("\n✅ Probe complete. Look for a status != 204 above to find the correct payload.")


if __name__ == "__main__":
    asyncio.run(main())
