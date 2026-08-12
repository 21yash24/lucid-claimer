"""
deep_scan_promo_chunk.py
-------------------------
Downloads the full chunk-PHSFC5V5.js file and searches it deep for:
1. All API routes (like "/api/...")
2. All property fields related to mastermind or guess or code
3. All HTTP request calls (e.g. this.http.post, this.http.get)
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
            
            # Print all API URLs
            api_calls = re.findall(r'"/api/[^"]+"|\'/api/[^\']+\'', content)
            print(f"\n📡 Found {len(api_calls)} API paths:")
            for path in sorted(list(set(api_calls))):
                print(f"  - {path}")
                
            # Search for keyword matches case-insensitively
            for keyword in ["guess", "crack", "mastermind", "code", "vault", "rewards", "event", "active", "submit", "status"]:
                matches = list(re.finditer(re.escape(keyword), content, re.IGNORECASE))
                if matches:
                    print(f"\n✨ Keyword '{keyword}' found {len(matches)} times. First 5 snippets:")
                    for m in matches[:5]:
                        p = m.start()
                        snippet = content[max(0, p-80):min(len(content), p+180)]
                        print(f"  [{p}]: {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
