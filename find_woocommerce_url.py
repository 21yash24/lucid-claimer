"""
find_woocommerce_url.py
------------------------
Downloads chunk-DVYCDZJN.js and searches for woocommerceUrl.
"""

import asyncio
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-DVYCDZJN.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            print("Content around woocommerceUrl:")
            idx = content.find("woocommerceUrl")
            if idx != -1:
                print(content[max(0, idx-100):min(len(content), idx+300)])
            else:
                print("woocommerceUrl not found directly, showing top 1000 chars:")
                print(content[:1000])

if __name__ == "__main__":
    asyncio.run(main())
