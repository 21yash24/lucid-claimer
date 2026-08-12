import asyncio
import logging
import sys
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("NetworkSpy")

async def main():
    email = "yashjha2004@gmail.com"
    password = "Manjoo#1976"
    
    async with async_playwright() as p:
        logger.info("🚀 Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Monitor all API requests
        async def handle_request(request):
            if "api/" in request.url or "stripe" in request.url:
                logger.info(f"➡️ REQUEST: {request.method} {request.url}")
                if request.post_data:
                    logger.info(f"   Payload: {request.post_data}")
                    
        async def handle_response(response):
            if "api/" in response.url or "stripe" in response.url:
                logger.info(f"⬅️ RESPONSE: {response.status} {response.url}")
                try:
                    text = await response.text()
                    logger.info(f"   Body: {text[:250]}")
                except Exception:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # 1. Go to login page
        logger.info("📡 Navigating to dashboard...")
        await page.goto("https://dash.lucidtrading.com/#/login", wait_until="networkidle")
        
        # 2. Fill login form
        logger.info("✍️ Logging in...")
        await page.fill("input[placeholder*='Email']", email)
        await page.fill("input[placeholder*='Password']", password)
        await page.click("button:has-text('Login'), button:has-text('Sign In'), button[type='submit']")
        await page.wait_for_timeout(5000)
        
        # 3. Go to checkout page (Add Account)
        logger.info("📡 Navigating to checkout...")
        await page.goto("https://dash.lucidtrading.com/#/purchase?plan=50k", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # 4. Try applying a coupon code
        logger.info("✍️ Entering coupon...")
        coupon_selectors = ["input[placeholder*='coupon']", "input[name='coupon']", "input[placeholder*='Coupon']"]
        coupon_input = None
        for sel in coupon_selectors:
            try:
                if await page.is_visible(sel):
                    coupon_input = sel
                    break
            except Exception:
                pass
                
        if coupon_input:
            await page.fill(coupon_input, "LIPE50100")
            logger.info("🖱️ Clicking Apply...")
            apply_button = "button:has-text('Apply'), button:has-text('Submit')"
            await page.click(apply_button)
            await page.wait_for_timeout(4000)
            
            # Click checkout/buy
            logger.info("🖱️ Clicking Checkout/Buy...")
            pay_button = "button:has-text('Pay'), button:has-text('Complete'), button:has-text('Checkout')"
            try:
                await page.click(pay_button)
                await page.wait_for_timeout(4000)
            except Exception as e:
                logger.warning(f"Could not click pay button: {e}")
        else:
            logger.warning("❌ Coupon input field not found on page! Dumping HTML body:")
            body_html = await page.content()
            print(body_html[:1000])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
