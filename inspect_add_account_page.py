"""
inspect_add_account_page.py
----------------------------
Logs in and prints all text contents and button elements on the add-account page,
then saves a screenshot.
"""

import asyncio
from playwright.async_api import async_playwright

EMAIL    = "yashjha2004@gmail.com"
PASSWORD = "Manjoo#1976"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Login
        await page.goto("https://dash.lucidtrading.com/#/login", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.fill("input[type='email']", EMAIL)
        await page.fill("input[type='password']", PASSWORD)
        await page.click("button[type='submit']")
        await page.wait_for_timeout(6000)

        # Nav to add-account
        await page.goto("https://dash.lucidtrading.com/#/add-account", wait_until="networkidle")
        await page.wait_for_timeout(4000)

        # Print all buttons
        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons:")
        for idx, btn in enumerate(buttons):
            text = await btn.inner_text()
            html = await btn.evaluate("el => el.outerHTML")
            print(f"  [{idx}] text={text!r} html={html[:150]!r}")

        # Take screenshot
        await page.screenshot(path="tmp_images/add_account_layout.png")
        print("Screenshot saved to tmp_images/add_account_layout.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
