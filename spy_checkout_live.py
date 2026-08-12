"""
spy_checkout_live.py  (v2)
--------------------------
Fixed: targets dash.lucidtrading.com SPA with hash-based routing.
Logs in, navigates to purchase flow, captures every API call made.
"""

import asyncio
import json
import logging
from playwright.async_api import async_playwright

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"
COUPON   = "LIPE50100"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("LiveSpy")

captured = []

async def main():
    async with async_playwright() as p:
        logger.info("🚀 Launching Chromium...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )

        # ── Intercept every network request ────────────────────────────────
        async def on_request(req):
            if "lucidtrading" in req.url or "/api/" in req.url:
                entry = {"method": req.method, "url": req.url, "post_data": req.post_data}
                captured.append(entry)
                if req.post_data or req.method == "POST":
                    logger.info(f"\n➡️  {req.method} {req.url}")
                    logger.info(f"   PAYLOAD: {req.post_data}")

        async def on_response(res):
            if "lucidtrading" in res.url and res.request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = await res.text()
                except Exception:
                    body = "<binary>"
                logger.info(f"⬅️  {res.status} {res.url}")
                if body.strip():
                    logger.info(f"   BODY: {body[:500]}")

        page = await ctx.new_page()
        page.on("request",  on_request)
        page.on("response", on_response)

        # ── STEP 1: Load the dashboard SPA (hash routing) ────────────────
        logger.info("\n── STEP 1: Loading Lucid Dashboard SPA ─────────────────")
        await page.goto("https://dash.lucidtrading.com/#/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        body_preview = await page.inner_text("body")
        logger.info(f"📄 Page preview: {body_preview[:300]}")

        # ── STEP 2: Fill login form ───────────────────────────────────────
        logger.info("\n── STEP 2: Logging in ───────────────────────────────────")
        try:
            # Wait for an email input to appear (SPA may lazy-load)
            await page.wait_for_selector("input", timeout=8000)
            inputs = await page.query_selector_all("input")
            logger.info(f"Found {len(inputs)} input(s) on page")
            for inp in inputs:
                inp_type  = await inp.get_attribute("type")  or ""
                inp_name  = await inp.get_attribute("name")  or ""
                inp_placeholder = await inp.get_attribute("placeholder") or ""
                logger.info(f"  Input: type={inp_type!r} name={inp_name!r} placeholder={inp_placeholder!r}")

            # Fill email
            email_sel = "input[type='email'], input[name='email'], input[placeholder*='Email' i], input[placeholder*='username' i]"
            await page.fill(email_sel, EMAIL)

            # Fill password
            pass_sel = "input[type='password'], input[name='password'], input[placeholder*='Password' i]"
            await page.fill(pass_sel, PASSWORD)

            # Submit
            await page.click("button[type='submit'], button:has-text('Sign In'), button:has-text('Login')")
            logger.info("✅ Login submitted — waiting for redirect...")
            await page.wait_for_timeout(6000)

        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            await page.screenshot(path="tmp_images/login_error.png")

        current_url = page.url
        body_preview = await page.inner_text("body")
        logger.info(f"📍 After login URL: {current_url}")
        logger.info(f"📄 After login preview: {body_preview[:300]}")

        # ── STEP 3: Navigate to Add Account / Purchase ────────────────────
        logger.info("\n── STEP 3: Navigating to purchase page ──────────────────")
        purchase_urls = [
            "https://dash.lucidtrading.com/#/add-account",
            "https://dash.lucidtrading.com/#/purchase",
            "https://dash.lucidtrading.com/#/checkout",
        ]
        for pu in purchase_urls:
            await page.goto(pu, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            pg_text = await page.inner_text("body")
            logger.info(f"\n🔗 {pu}")
            logger.info(f"   Preview: {pg_text[:250]}")
            if any(k in pg_text.lower() for k in ["50k", "25k", "evaluation", "plan", "select", "purchase", "add"]):
                logger.info("   ✅ This looks like the purchase page!")
                break

        # ── STEP 4: Click plan + enter coupon ────────────────────────────
        logger.info("\n── STEP 4: Looking for plan/coupon UI ───────────────────")
        await page.screenshot(path="tmp_images/purchase_page.png")
        logger.info("📸 Screenshot saved: tmp_images/purchase_page.png")

        # Try clicking any 50k plan selector
        plan_selectors = [
            "button:has-text('50k')", "button:has-text('50K')",
            "[data-plan='50k']", "div:has-text('50k') button",
            "label:has-text('50k')", "li:has-text('50k')"
        ]
        for sel in plan_selectors:
            try:
                if await page.is_visible(sel, timeout=2000):
                    await page.click(sel)
                    logger.info(f"✅ Clicked plan: {sel}")
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # Coupon input
        coupon_selectors = [
            "input[placeholder*='coupon' i]", "input[placeholder*='promo' i]",
            "input[placeholder*='code' i]",   "input[name*='coupon' i]",
            "input[id*='coupon' i]",
        ]
        coupon_found = False
        for sel in coupon_selectors:
            try:
                if await page.is_visible(sel, timeout=2000):
                    await page.fill(sel, COUPON)
                    logger.info(f"✅ Coupon entered in: {sel}")
                    coupon_found = True
                    # Click Apply
                    for apply_sel in ["button:has-text('Apply')", "button:has-text('Redeem')"]:
                        try:
                            if await page.is_visible(apply_sel, timeout=2000):
                                await page.click(apply_sel)
                                logger.info(f"✅ Apply clicked: {apply_sel}")
                                await page.wait_for_timeout(3000)
                                break
                        except Exception:
                            pass
                    break
            except Exception:
                pass

        if not coupon_found:
            logger.warning("❌ No coupon input found")

        # ── STEP 5: Click Pay / Complete ────────────────────────────────
        logger.info("\n── STEP 5: Attempting Pay/Complete ─────────────────────")
        for pay_sel in ["button:has-text('Pay')", "button:has-text('Complete')", "button:has-text('Checkout')"]:
            try:
                if await page.is_visible(pay_sel, timeout=2000):
                    await page.click(pay_sel)
                    logger.info(f"✅ Pay clicked: {pay_sel}")
                    await page.wait_for_timeout(5000)
                    break
            except Exception:
                pass

        # ── Summary ──────────────────────────────────────────────────────
        post_calls = [r for r in captured if r["method"] == "POST"]
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 Total POST requests captured: {len(post_calls)}")
        logger.info(f"{'='*60}")
        for i, r in enumerate(post_calls, 1):
            logger.info(f"\n[{i}] POST {r['url']}")
            if r["post_data"]:
                logger.info(f"     {r['post_data']}")

        with open("captured_api_calls.json", "w") as f:
            json.dump(captured, f, indent=2)
        logger.info("\n💾 Saved to captured_api_calls.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
