"""
list_all_chunks.py
------------------
Downloads main-TF6I67B4.js and extracts all route paths and their corresponding
chunk files (e.g. chunk-XXXX.js).
"""

import asyncio
import aiohttp
import re

async def main():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        url = "https://dash.lucidtrading.com/main-TF6I67B4.js"
        async with session.get(url) as resp:
            content = await resp.text(errors="replace")
            
            # Find routes like: {path:"...",loadComponent:...}
            # Or chunk imports: import("./chunk-...")
            chunk_imports = re.findall(r'import\("\./(chunk-[a-zA-Z0-9]+\.js)"\)', content)
            print(f"Total chunk imports found: {len(chunk_imports)}")
            print("Unique imports:", list(set(chunk_imports)))
            
            # Print the routes mapping context in main-TF6I67B4.js
            # Let's search for "path:" and print the matching context lines
            pos = [m.start() for m in re.finditer(r'path:"', content)]
            print(f"\nFound {len(pos)} path definitions:")
            for p in pos:
                snippet = content[max(0, p-40):min(len(content), p+240)]
                print(f"  - {snippet.strip()!r}")

if __name__ == "__main__":
    asyncio.run(main())
