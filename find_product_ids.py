"""
find_product_ids.py
--------------------
Downloads chunk-DHDXS6CO.js and searches for product IDs, 25k, 50k, 100k,
or mapping structures that determine the product ID based on plan selection.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-DHDXS6CO.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            
            # Print any references to numbers that look like WooCommerce product IDs
            # Usually product IDs are 4-5 digit numbers, e.g. 56570 or similar
            # Look for context containing "25k" or "50k" or "100k"
            for kw in ["25k", "50k", "100k", "product", "id:"]:
                idx = content.lower().find(kw)
                while idx != -1:
                    snippet = content[max(0, idx-100):min(len(content), idx+200)]
                    print(f"Context [{kw}]:")
                    print(repr(snippet.strip()))
                    idx = content.lower().find(kw, idx + 1)
                    # Limit output to first 5
                    break

if __name__ == "__main__":
    asyncio.run(main())
