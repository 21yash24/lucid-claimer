"""
find_secret_redeem_js.py
-------------------------
Downloads chunk-PHSFC5V5.js and prints the TypeScript logic/methods surrounding
the secret key submission button (secret-redeem__btn) to find the API request payload key.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-PHSFC5V5.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print(f"File size: {len(content)} chars.")
            
            # Look for button action mapping or submit form
            # Angular click events usually look like click:function(){ ... }
            btn_clicks = [m.start() for m in re.finditer(r'secretCode|redeem', content, re.IGNORECASE)]
            print(f"Matches found: {btn_clicks}")
            for p in btn_clicks:
                snippet = content[max(0, p-120):min(len(content), p+240)]
                print(f"  Snippet at {p}: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
