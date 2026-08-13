"""
Safe checkout DOM inspector.

Purpose: inspect the real checkout DOM and produce selector evidence before
any checkout automation is written. This script NEVER clicks payment,
checkout, Buy, Pay Now, or other purchase-confirmation controls.

Usage:
    python checkout_dom_inspector.py --url 'https://dash.lucidtrading.com/#/add-account'

Authentication:
    Set PLAYWRIGHT_STATE to a local Playwright storage-state JSON file, or
    use an existing persistent browser profile via BROWSER_USER_DATA_DIR.

Output:
    checkout_dom_report.json
    checkout_dom_snapshot.html
    checkout_dom_inspector.png
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "checkout_dom_report.json"
HTML = ROOT / "checkout_dom_snapshot.html"
SCREENSHOT = ROOT / "checkout_dom_inspector.png"

# Text which is intentionally never clicked by this inspector.
DANGEROUS_TEXT = (
    "pay now", "place order", "complete purchase", "buy now", "purchase",
    "submit order", "checkout", "complete order"
)


async def inspect(url: str, mobile: bool) -> None:
    state = os.getenv("PLAYWRIGHT_STATE", "").strip()
    user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", "").strip()

    async with async_playwright() as p:
        if user_data_dir:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900},
                is_mobile=mobile,
                has_touch=mobile,
            )
        else:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(ROOT / "tmp_dom_inspector_profile"),
                headless=True,
                viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900},
                is_mobile=mobile,
                has_touch=mobile,
                storage_state=state if state and Path(state).exists() else None,
            )

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            body_text = await page.locator("body").inner_text()
            await page.locator("body").screenshot(path=str(SCREENSHOT))
            HTML.write_text(await page.content(), encoding="utf-8")

            elements = await page.locator("button, input, select, textarea, [role='button'], [role='checkbox'], label").evaluate_all(
                """
                els => els.map((el, i) => ({
                    index: i,
                    tag: el.tagName,
                    text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 200),
                    aria: el.getAttribute('aria-label'),
                    role: el.getAttribute('role'),
                    name: el.getAttribute('name'),
                    id: el.id || null,
                    placeholder: el.getAttribute('placeholder'),
                    type: el.getAttribute('type'),
                    value: el.value || null,
                    checked: typeof el.checked === 'boolean' ? el.checked : null,
                    disabled: !!el.disabled,
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                    html: el.outerHTML.slice(0, 800)
                }))
                """
            )

            # Flag, but never interact with, purchase-like controls.
            for item in elements:
                combined = " ".join(str(item.get(k) or "") for k in ("text", "aria", "name", "id"))
                item["purchase_like"] = any(x in combined.lower() for x in DANGEROUS_TEXT)

            report = {
                "url": page.url,
                "title": await page.title(),
                "mobile": mobile,
                "body_text": body_text[:30000],
                "elements": elements,
                "notes": [
                    "This report is for DOM inspection only.",
                    "Purchase-like controls are reported but never clicked.",
                    "Selectors must be validated against this report before automation is implemented."
                ],
            }
            REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Saved: {REPORT}")
            print(f"Saved: {HTML}")
            print(f"Saved: {SCREENSHOT}")
            print(f"Discovered {len(elements)} interactive/label elements")
            for item in elements:
                if item["visible"]:
                    print(
                        f"[{item['index']}] {item['tag']} text={item['text']!r} "
                        f"aria={item['aria']!r} id={item['id']!r} "
                        f"name={item['name']!r} placeholder={item['placeholder']!r} "
                        f"purchase_like={item['purchase_like']}"
                    )
        finally:
            await context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--mobile", action="store_true")
    args = parser.parse_args()
    asyncio.run(inspect(args.url, args.mobile))


if __name__ == "__main__":
    main()
