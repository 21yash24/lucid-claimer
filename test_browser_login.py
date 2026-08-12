"""
test_browser_login.py
---------------------
Executes the Playwright browser login step and takes screenshots of the result
to see why the login fails.
"""

import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, '.')
import config

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_browser_data")

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("📡 Navigating to dashboard SPA...")
        await page.goto("https://dash.lucidtrading.com/#/add-account", timeout=25000, wait_until="load")
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        await page.screenshot(path="tmp_images/login_step_1.png")
        
        # Check login elements
        username_visible = await page.is_visible("input[type='text']:visible, input[placeholder*='Username' i], input[placeholder*='Email' i]")
        password_visible = await page.is_visible("input[type='password']:visible")
        print(f"Username field visible: {username_visible}")
        print(f"Password field visible: {password_visible}")
        
        if username_visible and password_visible:
            print("Filling credentials...")
            await page.fill("input[type='text']:visible, input[placeholder*='Username' i], input[placeholder*='Email' i]", EMAIL)
            await page.fill("input[type='password']:visible", PASSWORD)
            await page.screenshot(path="tmp_images/login_step_2_filled.png")
            
            print("Clicking submit...")
            await page.click("button[type='submit'], button:has-text('Sign In')")
            await page.wait_for_timeout(8000)
            
            print(f"URL after submit: {page.url}")
            await page.screenshot(path="tmp_images/login_step_3_result.png")
            
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
