"""
find_m_definition.py
---------------------
Downloads chunk-DHDXS6CO.js and prints where the variable M is defined or initialized.
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
            
            # Look for variable definitions around "from" imports or "apiUrl" or "M = "
            for line in content.split(";"):
                if "M=" in line or "const M" in line or "let M" in line or "var M" in line:
                    print("Found definition:", line.strip())
                    
            # Let's print the top import statements
            print("\nTop 500 chars of file:")
            print(content[:500])

if __name__ == "__main__":
    asyncio.run(main())
