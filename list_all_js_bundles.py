"""
list_all_js_bundles.py
-----------------------
Downloads index.html from dash.lucidtrading.com and extracts all script tags
to verify the full list of compiled JS chunk files.
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/"
        async with session.get(url) as resp:
            html = await resp.text()
            
            # Find all script src
            scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
            print("📜 Found scripts in index.html:")
            for s in scripts:
                print(f"  - {s}")
                
            # Also find preloaded modules or chunks
            preloads = re.findall(r'<link[^>]+href=["\']([^"\']+\.js)["\']', html)
            if preloads:
                print("\n📦 Found preloaded module chunks:")
                for p in preloads:
                    print(f"  - {p}")

if __name__ == "__main__":
    asyncio.run(main())
