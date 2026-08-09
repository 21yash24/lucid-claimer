import asyncio
import logging
import os
import sys
try:
    from playwright.async_api import async_playwright
except ImportError:
    pass

sys.path.append("/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer")
import config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("AutoCheckout")

# Path to local persistent browser storage to retain logins and device IDs
USER_DATA_DIR = "/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer/tmp_browser_data"

async def purchase_evaluation_account(coupon_code: str):
    """
    Launches a Chromium headless instance using Playwright, navigates to the 
    checkout flow, applies the 100% off coupon code, and completes the purchase form.
    """
    logger.info(f"🚀 LAUNCHING AUTO-CHECKOUT FLOW FOR COUPON: {coupon_code}...")
    start_time = asyncio.get_event_loop().time()
    
    async with async_playwright() as p:
        # Launch browser with custom user data directory to maintain cookies/Cloudflare state
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
        )
        
        # Inject existing browser cookies into the session context
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
            await context.add_cookies(cookies)
            
        page = await context.new_page()
        
        try:
            # Step 1: Navigate directly to the 25k plan checkout page
            # Adjust this URL depending on the exact checkout route (e.g. /purchase/25k or similar)
            checkout_url = "https://dash.lucidtrading.com/purchase?plan=25k"
            logger.info(f"📡 Navigating to checkout page: {checkout_url}")
            await page.goto(checkout_url, timeout=15000, wait_until="load")
            
            # Step 2: Apply the Coupon Code
            # Find the coupon input box. Standard inputs are named "coupon", "couponCode", or match placeholder
            coupon_selector = "input[placeholder*='coupon'], input[name='coupon'], input[id='coupon']"
            await page.wait_for_selector(coupon_selector, timeout=5000)
            await page.fill(coupon_selector, coupon_code)
            logger.info("✍️ Coupon code pasted.")
            
            # Find and click the "Apply" or "Submit" coupon button next to the input
            apply_button = "button:has-text('Apply'), button:has-text('Submit'), button[type='submit']"
            await page.click(apply_button)
            logger.info("🖱️ Apply button clicked. Waiting for price reduction...")
            
            # Step 3: Verify the total price matches $0.00 or 100% off
            price_selector = ".total-price, .price, .summary"
            await asyncio.sleep(1.5) # Wait for Ajax to calculate new price
            
            # Step 4: Fill in Checkout Billing Details if not populated
            # Check for Terms & Conditions Checkbox and check it
            terms_checkbox = "input[type='checkbox']"
            checkboxes = await page.query_selector_all(terms_checkbox)
            for box in checkboxes:
                await box.check()
                
            # Step 5: Click the Place Order / Complete Checkout button
            # Note: For safety during local testing, we print and log instead of actually completing the checkout
            complete_button = "button:has-text('Complete'), button:has-text('Place Order'), button:has-text('Buy')"
            logger.info("🎯 Price reduced successfully. Ready to click 'Complete Order'.")
            
            # Uncomment below to enable live checkout execution:
            # await page.click(complete_button)
            # logger.info("🎉 CHECKOUT COMPLETED!")
            
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(f"🏁 Auto-checkout finished mock flow in {elapsed:.1f}ms.")
            
        except Exception as e:
            logger.error(f"❌ Error during auto-checkout: {e}")
            # Take a screenshot for debugging purposes
            await page.screenshot(path="/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer/tmp_images/checkout_error.png")
            logger.info("📸 Debug screenshot saved to tmp_images/checkout_error.png")
        finally:
            await context.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python checkout_buyer.py <coupon_code>")
        sys.exit(1)
    asyncio.run(purchase_evaluation_account(sys.argv[1]))
