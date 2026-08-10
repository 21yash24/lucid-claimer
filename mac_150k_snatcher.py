"""
mac_150k_snatcher.py
--------------------
EXCLUSIVE MAC SNATCHER FOR CJ WAWA'S 150K ACCOUNT DROP:
1. Polls Twitter/X feed (@cj_wawa) continuously.
2. Monitors macOS Clipboard (pbpaste) — if you copy any code, it instantly snatches it!
3. Accepts manual terminal input — type/paste code and hit Enter to trigger instantly.
4. Fires parallel 150K account checkout via direct API + secret redemption + browser.
"""

import os
import sys
import asyncio
import logging
import subprocess
import certifi
import ssl
import aiohttp

# Bypass SSL verification issues on Mac
ssl._create_default_https_context = ssl._create_unverified_context
_orig_tcp_init = aiohttp.TCPConnector.__init__
def _patched_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _patched_tcp_init

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from claimer import MultiAccountClaimer
from x_monitor import XMonitor
from parser import extract_all_giveaway_codes

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("150kSnatcher")

claimed_codes = set()
claimer = MultiAccountClaimer(
    config.REDEMPTION_API_URL,
    config.ACCOUNT_TOKENS,
    config.LUCID_ACCOUNTS
)

async def snatch_code(code: str, origin: str = "Manual"):
    code = code.strip().upper()
    if not code or code in claimed_codes:
        return

    claimed_codes.add(code)
    print("\a\a\a")
    print("\n" + "🔥" * 30)
    print(f"🚀   SNATCHING 150K ACCOUNT WITH CODE: '{code}' (Origin: {origin})   🚀")
    print("🔥" * 30 + "\n")
    logger.info(f"⚡ [150K SNATCHER] Triggering instant checkout for code: '{code}'...")

    # 1. Trigger Direct API Checkout for 150K Account (Primary Target)
    task_150k = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="150k"))
    
    # 2. Trigger Secret Drop Redemption API (Fallback)
    task_secret = asyncio.create_task(claimer.claim_all_accounts(code))

    # 3. Trigger 50K Account Checkout (Secondary Fallback)
    task_50k = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="50k"))

    # 4. If Playwright is available, launch browser auto-filler
    try:
        from checkout_buyer import purchase_evaluation_account
        asyncio.create_task(purchase_evaluation_account(code))
    except Exception as e:
        logger.debug(f"Playwright launcher error: {e}")

    results_150k = await task_150k
    results_secret = await task_secret
    results_50k = await task_50k

    logger.info("🏁 Snatch attempts complete for code.")

def get_clipboard_text():
    try:
        p = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate()
        return out.decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

async def clipboard_monitor_loop():
    last_clip = ""
    while True:
        try:
            clip = get_clipboard_text()
            if clip and clip != last_clip:
                last_clip = clip
                # Check if clipboard looks like a coupon code (e.g. LBOX..., CJ150, WAWA150, etc.)
                codes = extract_all_giveaway_codes(clip)
                if not codes and len(clip) >= 3 and len(clip) <= 30 and not " " in clip and not "http" in clip:
                    codes = [clip.strip()]
                
                for c in codes:
                    if c not in claimed_codes:
                        logger.info(f"📋 Detected code in macOS Clipboard: '{c}'!")
                        await snatch_code(c, origin="macOS Clipboard")
        except Exception as e:
            logger.debug(f"Clipboard check error: {e}")
        await asyncio.sleep(0.5)

async def x_tweet_callback(codes: list, tweet_text: str = ""):
    logger.info(f"🐦 Tweet detected! Extracted codes: {codes}")
    for c in codes:
        await snatch_code(c, origin="Twitter/X (@cj_wawa)")

async def terminal_input_loop():
    loop = asyncio.get_running_loop()
    print("\n" + "=" * 60)
    print("🎯 MAC EXCLUSIVE 150K ACCOUNT SNATCHER IS ACTIVE!")
    print("   1. Auto-monitoring @cj_wawa Twitter feed.")
    print("   2. Auto-monitoring macOS Clipboard (copy any code to snatch!).")
    print("   3. Or TYPE/PASTE any code below & hit ENTER to claim instantly:")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = await loop.run_in_executor(None, sys.stdin.readline)
            if user_input:
                code_str = user_input.strip()
                if code_str:
                    await snatch_code(code_str, origin="Terminal Input")
        except Exception as e:
            logger.error(f"Terminal input error: {e}")
            await asyncio.sleep(1)

async def main():
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors found in .env:")
        for err in errors:
            logger.error(f" - {err}")
        sys.exit(1)

    await claimer.initialize()

    # Launch X Monitor
    x_mon = XMonitor(x_tweet_callback)
    x_ok = await x_mon.initialize()
    if x_ok:
        logger.info("🐦 Connected to X Monitor for @cj_wawa feed!")
        asyncio.create_task(x_mon.poll_timeline())
    else:
        logger.warning("⚠️ X Monitor initialization failed (will rely on Clipboard + Terminal input).")

    # Launch Clipboard Monitor
    asyncio.create_task(clipboard_monitor_loop())

    # Launch Terminal Input listener
    await terminal_input_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopping 150K Snatcher...")
    finally:
        asyncio.run(claimer.close())
