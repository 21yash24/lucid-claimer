"""
inspect_checkout_chunk.py
--------------------------
Downloads chunk-DHDXS6CO.js and prints EVERY URL path string matching /api/ or stripe.
Also prints the surrounding code context.
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
            
            print(f"File size: {len(content)} chars.")
            
            # Find all strings like "/api/..."
            api_paths = re.findall(r'"/api/[^"]+"|\'/api/[^\']+\'', content)
            print("API Paths found:", api_paths)
            
            # Search for any endpoint, stripe, coupon or checkout keyword
            for word in ["stripe", "coupon", "checkout", "apply", "validate", "plan"]:
                positions = [m.start() for m in re.finditer(re.escape(word), content, re.IGNORECASE)]
                print(f"\nKeyword '{word}' found at positions: {positions}")
                for p in positions[:5]:
                    snippet = content[max(0, p-120):min(len(content), p+200)]
                    print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
