"""
inspect_login_url.py
---------------------
Visits dash.lucidtrading.com, follows redirects, and prints the final URL
and all form input elements found on the page.
"""

import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("📡 Navigating to dash.lucidtrading.com...")
        response = await page.goto("https://dash.lucidtrading.com/", wait_until="networkidle")
        print(f"📍 Final URL: {page.url}")
        print(f"📍 HTTP Status: {response.status}")
        
        # Print all inputs
        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} inputs:")
        for idx, inp in enumerate(inputs):
            name = await inp.get_attribute("name")
            inp_type = await inp.get_attribute("type")
            placeholder = await inp.get_attribute("placeholder")
            print(f"  [{idx}] type={inp_type!r} name={name!r} placeholder={placeholder!r}")
            
        await page.screenshot(path="tmp_images/login_redirect.png")
        print("Screenshot saved to tmp_images/login_redirect.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
