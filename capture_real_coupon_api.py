"""
capture_real_coupon_api.py
--------------------------
Logs in to dash.lucidtrading.com, navigates to the add-account modal,
inputs a dummy coupon, clicks "Apply Coupon", and logs the EXACT request
and response details (URL, headers, body).
"""

import asyncio
import json
import logging
from playwright.async_api import async_playwright

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("CaptureCoupon")

async def main():
    async with async_playwright() as p:
        logger.info("🚀 Launching Chromium browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        # Monitor all requests
        async def on_request(req):
            if "lucidtrading" in req.url and ("/api/" in req.url or "checkout" in req.url or "coupon" in req.url):
                logger.info(f"➡️ REQUEST: {req.method} {req.url}")
                if req.post_data:
                    logger.info(f"   PAYLOAD: {req.post_data}")

        async def on_response(res):
            if "lucidtrading" in res.url and ("/api/" in res.url or "checkout" in res.url or "coupon" in res.url):
                try:
                    text = await res.text()
                except Exception:
                    text = "<binary/error>"
                logger.info(f"⬅️ RESPONSE {res.status}: {res.url}")
                logger.info(f"   BODY: {text[:300]}")

        page.on("request", on_request)
        page.on("response", on_response)

        # 1. Load login page
        logger.info("Loading login page...")
        await page.goto("https://dash.lucidtrading.com/#/login", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 2. Log in
        logger.info("Filling credentials...")
        await page.fill("input[type='email'], input[name='email'], input[placeholder*='Email' i]", EMAIL)
        await page.fill("input[type='password']", PASSWORD)
        await page.click("button[type='submit'], button:has-text('Sign In')")
        logger.info("Submitted login...")
        await page.wait_for_timeout(6000)

        # 3. Go to add-account page
        logger.info("Navigating to add-account page...")
        await page.goto("https://dash.lucidtrading.com/#/add-account", wait_until="networkidle")
        await page.wait_for_timeout(4000)

        # 4. Open 25K plan (first plan modal)
        logger.info("Opening 25K modal...")
        # Look for buttons like "Select" or plan cards
        plan_buttons = [
            "button:has-text('Select')", "button:has-text('Buy')", 
            "button:has-text('25k')", "div:has-text('25K') button",
            "button"
        ]
        modal_opened = False
        for btn_sel in plan_buttons:
            try:
                # Wait up to 2s for visibility
                if await page.is_visible(btn_sel, timeout=2000):
                    await page.click(btn_sel)
                    logger.info(f"Clicked selector: {btn_sel}")
                    await page.wait_for_timeout(2000)
                    modal_opened = True
                    break
            except Exception:
                pass

        if not modal_opened:
            logger.warning("Could not open modal using standard selectors, taking screenshot...")
            await page.screenshot(path="tmp_images/modal_error.png")
            return

        # 5. Fill coupon input
        logger.info("Filling coupon input...")
        coupon_selectors = [
            "input[placeholder*='coupon' i]", "input[placeholder*='code' i]",
            "input[name='coupon']", "input"
        ]
        coupon_filled = False
        for sel in coupon_selectors:
            try:
                # We want to fill the coupon input inside the modal
                if await page.is_visible(sel, timeout=2000):
                    # Clear it first
                    await page.fill(sel, "")
                    await page.fill(sel, "soimwomed")
                    logger.info(f"Filled coupon input using: {sel}")
                    coupon_filled = True
                    break
            except Exception:
                pass

        if not coupon_filled:
            logger.warning("Could not find coupon input, taking screenshot...")
            await page.screenshot(path="tmp_images/coupon_error.png")
            return

        # 6. Click Apply Coupon button
        logger.info("Clicking Apply Coupon button...")
        apply_buttons = [
            "button:has-text('Apply Coupon')", "button:has-text('Apply')",
            "button:has-text('Redeem')"
        ]
        apply_clicked = False
        for btn in apply_buttons:
            try:
                if await page.is_visible(btn, timeout=2000):
                    await page.click(btn)
                    logger.info(f"Clicked apply button: {btn}")
                    await page.wait_for_timeout(3000)
                    apply_clicked = True
                    break
            except Exception:
                pass

        if not apply_clicked:
            logger.warning("Could not click Apply Coupon button, taking screenshot...")
            await page.screenshot(path="tmp_images/apply_error.png")

        await browser.close()
        logger.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
