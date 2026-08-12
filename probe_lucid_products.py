"""
probe_lucid_products.py
-----------------------
Scans Lucid Trading JS bundles to find the correct product IDs
for LucidFlex 150K TDV/NT visible in the user's screenshot.
"""
import asyncio
import aiohttp
import ssl
import re

ssl._create_default_https_context = ssl._create_unverified_context

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Fetch the main bundle
        print("🔍 Scanning Lucid JS bundles for product IDs...")
        async with session.get("https://dash.lucidtrading.com/main-TF6I67B4.js", timeout=10) as resp:
            text = await resp.text()
            
        # Look for product ID patterns near 150k, flex, etc.
        matches = re.findall(r'(?:product[_-]?id|productId|pid)["\s:=]+(\d{4,6})', text, re.IGNORECASE)
        print(f"\nProduct IDs found in main bundle: {list(set(matches))}")
        
        # Search for "150" context
        idx = 0
        found_150 = []
        while True:
            idx = text.find("150", idx)
            if idx == -1:
                break
            snippet = text[max(0, idx-60):idx+80]
            if any(x in snippet.lower() for x in ["product", "plan", "id", "price"]):
                found_150.append(snippet.strip())
            idx += 3
        
        print(f"\n🎯 Snippets near '150' with product/plan/id context:")
        seen = set()
        for s in found_150[:30]:
            key = s[:50]
            if key not in seen:
                seen.add(key)
                print(f"  ...{s}...")

if __name__ == "__main__":
    asyncio.run(main())
