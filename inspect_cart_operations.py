"""
inspect_cart_operations.py
--------------------------
Downloads chunk-DHDXS6CO.js and prints code context around cart methods:
- addToCart
- addItems
- setAddons
- clearCart
- CartToken / Nonce extraction
"""

import asyncio
import aiohttp

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/chunk-DHDXS6CO.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            
            # Print methods related to cart modification
            for kw in ["add-to-cart", "cart/items", "cart/add", "set-addons", "cartToken", "Nonce", "cart/apply-coupon"]:
                idx = content.find(kw)
                if idx != -1:
                    print(f"\nKeyword '{kw}' found:")
                    print(content[max(0, idx-150):min(len(content), idx+350)])

if __name__ == "__main__":
    asyncio.run(main())
