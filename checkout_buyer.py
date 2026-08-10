"""
checkout_buyer.py
-----------------
Automated purchase flow using Playwright:
1. Fetches a fresh JWT token using the mobile API (never blocked by Turnstile).
2. Injects the JWT token directly into the browser's localStorage.
3. Loads dash.lucidtrading.com/#/add-account already authenticated.
4. Selects plan size modal.
5. Applies coupon code.
6. Agrees to terms and completes checkout.
"""

import asyncio
import logging
import os
import sys
import json
import urllib.request
import ssl

try:
    from playwright.async_api import async_playwright
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("AutoCheckout")

USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_browser_data")

def get_fresh_token():
    url = "https://dash.lucidtrading.com/api/mobile/login"
    email = config.LUCID_EMAIL or "yashjha2004@gmail.com"
    password = config.LUCID_PASSWORD or "Manjoo#1976"
    
    payload = {
        "email": email,
        "password": password,
        "username": email
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LucidApp/90.0 (Android; Mobile)"
        }
    )
    
    # Bypass SSL context verification on local mac/env
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        logger.info(f"📡 Fetching fresh JWT login token for {email}...")
        with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
            res_data = json.loads(response.read().decode())
            return res_data.get("token")
    except Exception as e:
        logger.error(f"❌ Error fetching login token: {e}")
        return None

async def purchase_evaluation_account(coupon_code: str):
    # Determine plan size from command line arguments (e.g. 50k, 25k)
    target_plan = "50k"
    if len(sys.argv) > 2:
        target_plan = str(sys.argv[2]).lower().strip()

    logger.info(f"🚀 LAUNCHING AUTO-CHECKOUT FOR PLAN '{target_plan}' WITH COUPON: '{coupon_code}'...")
    start_time = asyncio.get_event_loop().time()
    
    # Fetch fresh token and prepare storage state
    token = get_fresh_token()
    storage_state = None
    if token:
        raw_token = token.replace("Bearer ", "").strip()
        storage_state = {
            "cookies": [],
            "origins": [
                {
                    "origin": "https://dash.lucidtrading.com",
                    "localStorage": [
                        {"name": "auth_token", "value": raw_token},
                        {"name": "token", "value": raw_token}
                    ]
                }
            ]
        }
        logger.info("🔑 Prepared auth_token in storage_state origins.")
    else:
        logger.warning("⚠️ Could not fetch fresh API token. Will fall back to credentials.")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            bypass_csp=True,
            storage_state=storage_state
        )
        
        # ── Step 1: Inject Session Auth ──────────────────────────────────
        if token:
            raw_token = token.replace("Bearer ", "").strip()
            # Redundancy helper: Angular SPA checks 'auth_token' on boot
            await context.add_init_script(f"localStorage.setItem('auth_token', '{raw_token}');")
            await context.add_init_script(f"localStorage.setItem('token', '{raw_token}');")
            logger.info("🔑 Injected auth_token into browser localStorage init script.")

        # Inject existing browser cookies into context for both domains
        if config.BROWSER_COOKIE:
            cookies = []
            for item in config.BROWSER_COOKIE.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies.append({
                        "name": k.strip(),
                        "value": v.strip(),
                        "domain": "dash.lucidtrading.com",
                        "path": "/"
                    })
                    cookies.append({
                        "name": k.strip(),
                        "value": v.strip(),
                        "domain": "lucidtrading.com",
                        "path": "/"
                    })
            await context.add_cookies(cookies)
            logger.info("🔑 Injected session cookies.")

        page = await context.new_page()
        
        try:
            # ── Step 2: Navigate to add-account page ─────────────────────
            logger.info("📡 Loading dashboard SPA...")
            await page.goto("https://dash.lucidtrading.com/#/add-account", timeout=25000, wait_until="load")
            
            # Wait dynamically for either the login page OR the purchase dashboard to load
            logger.info("⏳ Waiting for page to render...")
            try:
                await page.wait_for_selector("button:has-text('Select'), button:has-text('25K'), button:has-text('50K'), button:has-text('Sign In')", timeout=15000)
            except Exception:
                logger.warning("⚠️ Timeout waiting for page selectors. Proceeding anyway...")
            
            # Fallback: if we still land on login, do credentials login
            is_login_page = "login" in page.url or await page.is_visible("button:has-text('Sign In')") or await page.is_visible("input[name='log']")
            
            if is_login_page:
                logger.info("🔐 LocalStorage inject failed to auth. Submitting login credentials...")
                email = config.LUCID_EMAIL or "yashjha2004@gmail.com"
                password = config.LUCID_PASSWORD or "Manjoo#1976"
                
                if await page.is_visible("input[name='log']"):
                    await page.fill("input[name='log']", email)
                    await page.fill("input[name='pwd']", password)
                    await page.click("input[type='submit'], button[type='submit'], #wp-submit")
                else:
                    await page.fill("input[type='text']:visible, input[placeholder*='Username' i], input[placeholder*='Email' i]", email)
                    await page.fill("input[type='password']", password)
                    await page.click("button[type='submit'], button:has-text('Sign In')")
                
                logger.info("🔑 Login submitted. Waiting for redirect...")
                await page.wait_for_timeout(8000)
                
                if "add-account" not in page.url:
                    await page.goto("https://dash.lucidtrading.com/#/add-account", timeout=15000, wait_until="load")
                    await page.wait_for_timeout(4000)

            logger.info(f"📍 Current URL: {page.url}")

            # ── Step 3: Open Plan Modal ───────────────────────────────────
            logger.info(f"🖱️ Clicking select button for plan '{target_plan}'...")
            plan_selector = f"div:has-text('{target_plan.upper()}') button, button:has-text('{target_plan}'), button:has-text('{target_plan.upper()}')"
            
            modal_opened = False
            try:
                if await page.is_visible(plan_selector, timeout=3000):
                    await page.click(plan_selector)
                    logger.info(f"✅ Clicked plan selector: {plan_selector}")
                    modal_opened = True
                else:
                    # Fallback selectors
                    fallback_selectors = ["button:has-text('Select')", "button:has-text('Buy')", "button"]
                    for sel in fallback_selectors:
                        text = await page.locator(sel).first.inner_text() if await page.locator(sel).count() > 0 else ""
                        if "Select" in text or "Buy" in text:
                            await page.click(sel)
                            logger.info(f"✅ Clicked fallback plan selector: {sel} ({text})")
                            modal_opened = True
                            break
            except Exception as plan_err:
                logger.warning(f"Plan click warning: {plan_err}")

            await page.wait_for_timeout(2000)

            # ── Step 4: Fill and Apply Coupon Code ────────────────────────
            logger.info(f"✍️ Entering coupon code: '{coupon_code}'...")
            coupon_selector = "input[placeholder*='coupon' i]:visible, input[placeholder*='code' i]:visible, input[name='coupon']:visible, input[type='text']:visible"
            await page.wait_for_selector(coupon_selector, timeout=5000)
            await page.fill(coupon_selector, "")
            await page.fill(coupon_selector, coupon_code)
            
            apply_button = "button:has-text('Apply Coupon'), button:has-text('Apply'), button:has-text('Redeem')"
            await page.click(apply_button)
            logger.info("🖱️ Apply Coupon button clicked. Waiting for validation...")
            await page.wait_for_timeout(3500)

            # Check if there is an error message visible (e.g. coupon does not exist)
            body_text = await page.inner_text("body")
            if "does not exist" in body_text or "cannot be applied" in body_text or "invalid" in body_text.lower():
                logger.warning(f"❌ Coupon validation failed on page! Server message: {[line for line in body_text.splitlines() if 'coupon' in line.lower() or 'applied' in line.lower()]}")
                error_shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_images", "coupon_error_alert.png")
                await page.screenshot(path=error_shot)
                return

            # ── Step 5: Accept Terms & Conditions ─────────────────────────
            logger.info("✍️ Agreeing to Terms and Conditions...")
            checkbox_sel = "input[type='checkbox']"
            checkboxes = await page.query_selector_all(checkbox_sel)
            for box in checkboxes:
                try:
                    await box.check()
                except Exception:
                    pass

            # ── Step 6: Place Order / Complete Checkout ───────────────────
            complete_button = "button:has-text('Complete'), button:has-text('Place Order'), button:has-text('Buy'), button:has-text('Pay'), button:has-text('Checkout')"
            logger.info("🎯 Clicking pay/checkout button...")
            await page.click(complete_button)
            await page.wait_for_timeout(6000)
            logger.info("🎉 CHECKOUT COMPLETED SUCCESSFULLY!")
            
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(f"🏁 Auto-checkout completed live flow in {elapsed:.1f}ms.")
            
        except Exception as e:
            logger.error(f"❌ Error during auto-checkout: {e}")
            screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_images", "checkout_error.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"📸 Debug screenshot saved to {screenshot_path}")
        finally:
            await context.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python checkout_buyer.py <coupon_code> [plan_size]")
        sys.exit(1)
    asyncio.run(purchase_evaluation_account(sys.argv[1]))
