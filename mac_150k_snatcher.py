"""
mac_150k_snatcher.py
--------------------
CLEAN & BULLETPROOF MAC 150K SNATCHER:
1. Polls Twitter/X feed (@cj_wawa & @yashhjhaa) for tweet images containing giveaway codes.
2. Uses Apple Neural Engine Vision OCR + fragment reconstruction to extract codes accurately.
3. Automatically clicks into Chrome's "Apply Coupon Code" input box, pastes the code, clicks "Apply Coupon", and clicks "PROCEED TO PAYMENT".
4. Also accepts manual terminal input.
"""

import os
import sys
import asyncio
import logging
import subprocess
import ctypes
import ssl
import time
import aiohttp

# Bypass SSL verification on Mac
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

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("150kSnatcher")

claimed_codes: set = set()
claimer = MultiAccountClaimer(
    config.REDEMPTION_API_URL,
    config.ACCOUNT_TOKENS,
    config.LUCID_ACCOUNTS
)

# ────────────────────────────────────────────────────────
# Native Mac mouse click (CoreGraphics)
# ────────────────────────────────────────────────────────
def native_mac_click(x: int, y: int) -> bool:
    try:
        cg = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework'
            '/Frameworks/CoreGraphics.framework/CoreGraphics'
        )

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
        cg.CGEventCreateMouseEvent.restype  = ctypes.c_void_p
        cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        cg.CGEventPost.restype  = None

        pt     = CGPoint(float(x), float(y))
        e_down = cg.CGEventCreateMouseEvent(None, 1, pt, 0)
        cg.CGEventPost(0, e_down)
        time.sleep(0.05)
        e_up   = cg.CGEventCreateMouseEvent(None, 2, pt, 0)
        cg.CGEventPost(0, e_up)
        logger.info(f"🖱️ Native CGEvent Clicked at display coords ({x}, {y})")
        return True
    except Exception as e:
        logger.debug(f"Native Mac click error: {e}")
        return False

# ────────────────────────────────────────────────────────
# Live Green Button Location Helper
# ────────────────────────────────────────────────────────
def find_live_green_buttons():
    """
    Takes a live screenshot, scans for green buttons via HSV thresholding,
    and returns (apply_input_x, apply_input_y, apply_btn_x, apply_btn_y, proceed_btn_x, proceed_btn_y).
    """
    try:
        import cv2, numpy as np
        shot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_images", "live_screen.png")
        os.makedirs(os.path.dirname(shot_path), exist_ok=True)
        subprocess.run(['screencapture', '-x', shot_path], capture_output=True)
        
        img = cv2.imread(shot_path)
        if img is None:
            return None

        h, w = img.shape[:2]
        res = subprocess.run(['osascript', '-e', 'tell application "Finder" to get bounds of window of desktop'], capture_output=True, text=True)
        parts = [int(p.strip()) for p in res.stdout.strip().split(',')] if res.stdout.strip() else [0, 0, 1470, 956]
        disp_w = parts[2] - parts[0]
        disp_h = parts[3] - parts[1]
        scale_x = w / float(disp_w)
        scale_y = h / float(disp_h)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([40, 100, 100])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        apply_btn = None
        proceed_btn = None

        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            disp_y = y / scale_y
            disp_bw = bw / scale_x
            disp_bh = bh / scale_y

            # Apply Coupon button is in upper half of screen (y < 450), width between 80 and 200
            if area > 1000 and disp_y < 450 and 70 < disp_bw < 220 and disp_bw > disp_bh:
                apply_btn = (x, y, bw, bh)
            # Proceed to Payment button is wide (width > 300) in lower half of screen (y > 450)
            elif area > 10000 and disp_y > 450 and disp_bw > 300:
                proceed_btn = (x, y, bw, bh)

        if apply_btn:
            bx, by, bw, bh = apply_btn
            apply_x = int((bx + bw // 2) / scale_x)
            apply_y = int((by + bh // 2) / scale_y)
            input_x = int((bx - int(150 * scale_x)) / scale_x)
            input_y = apply_y
        else:
            # Fallback to calculated screen points
            input_x, input_y, apply_x, apply_y = 326, 230, 533, 230

        if proceed_btn:
            px, py, pw, ph = proceed_btn
            proceed_x = int((px + pw // 2) / scale_x)
            proceed_y = int((py + ph // 2) / scale_y)
        else:
            proceed_x, proceed_y = 324, 749

        logger.info(f"🎯 Green UI Target -> Input: ({input_x}, {input_y}), Apply: ({apply_x}, {apply_y}), Proceed: ({proceed_x}, {proceed_y})")
        return input_x, input_y, apply_x, apply_y, proceed_x, proceed_y
    except Exception as e:
        logger.debug(f"Green button detection error: {e}")
        return 326, 230, 533, 230, 324, 749

# ────────────────────────────────────────────────────────
# Chrome Auto-Paste Execution
# ────────────────────────────────────────────────────────
def paste_code_to_chrome(code: str):
    """
    1. Focuses Chrome.
    2. Copies code to clipboard (pbcopy).
    3. Finds live green Apply Coupon and Proceed buttons on screen.
    4. Clicks input box -> Selects All -> Pastes code -> Clicks Apply Coupon.
    5. Waits 2.5s -> Clicks PROCEED TO PAYMENT.
    """
    # 1. Put code in clipboard
    subprocess.run(['pbcopy'], input=code.encode('utf-8'))

    # 2. Focus Chrome
    subprocess.run(['osascript', '-e', 'tell application "Google Chrome" to activate'], capture_output=True)
    time.sleep(0.3)

    # 3. Locate live target positions
    coords = find_live_green_buttons()
    input_x, input_y, apply_x, apply_y, proceed_x, proceed_y = coords

    # 4. Click input box
    native_mac_click(input_x, input_y)
    time.sleep(0.15)

    # 5. Select All (Cmd+A) + Paste (Cmd+V)
    subprocess.run(['osascript', '-e', '''
    tell application "System Events"
        keystroke "a" using {command down}
        delay 0.05
        keystroke "v" using {command down}
    end tell
    '''], capture_output=True)
    time.sleep(0.2)

    # 6. Click Apply Coupon button
    native_mac_click(apply_x, apply_y)
    logger.info(f"🖱️ Step 1 COMPLETE: Clicked input ({input_x}, {input_y}), pasted '{code}', clicked Apply ({apply_x}, {apply_y})!")

    # 7. Wait 2.5s for coupon validation
    time.sleep(2.5)

    # 8. Click PROCEED TO PAYMENT button
    native_mac_click(proceed_x, proceed_y)
    logger.info(f"🖱️ Step 2 COMPLETE: Clicked PROCEED TO PAYMENT ({proceed_x}, {proceed_y})!")

# ────────────────────────────────────────────────────────
# Core Snatch Logic
# ────────────────────────────────────────────────────────
async def snatch_code(code: str, origin: str = "Manual"):
    code = code.strip().upper()
    if not code or code in claimed_codes:
        return

    claimed_codes.add(code)
    print("\a\a\a")
    print("\n" + "🔥" * 30)
    print(f"🚀   SNATCHING 150K ACCOUNT WITH CODE: '{code}' (Origin: {origin})   🚀")
    print("🔥" * 30 + "\n")
    logger.info(f"⚡ Triggering instant checkout for code: '{code}'...")

    # 1. Auto-paste into Chrome
    paste_code_to_chrome(code)

    # 2. Parallel Direct API Checkout
    task_150k   = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="150k"))
    task_secret = asyncio.create_task(claimer.claim_all_accounts(code))
    task_50k    = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="50k"))

    await asyncio.gather(task_150k, task_secret, task_50k, return_exceptions=True)
    logger.info("🏁 Snatch complete for code.")

# ────────────────────────────────────────────────────────
# X Tweet Callback
# ────────────────────────────────────────────────────────
async def x_tweet_callback(codes: list, tweet_text: str = ""):
    logger.info(f"🐦 New tweet! Codes found: {codes}")
    for c in codes:
        await snatch_code(c, origin="Twitter/X")

# ────────────────────────────────────────────────────────
# Terminal Input Loop
# ────────────────────────────────────────────────────────
async def terminal_input_loop():
    loop = asyncio.get_running_loop()
    print("\n" + "=" * 65)
    print("🎯 MAC 150K SNATCHER IS ACTIVE & READY!")
    print("   Monitoring: @cj_wawa & @yashhjhaa Twitter/X feed")
    print("   Manual:     Type/paste a code below and press ENTER")
    print("=" * 65 + "\n")
    while True:
        try:
            user_input = await loop.run_in_executor(None, sys.stdin.readline)
            if user_input and user_input.strip():
                await snatch_code(user_input.strip(), origin="Terminal Input")
        except Exception as e:
            logger.error(f"Terminal input error: {e}")
            await asyncio.sleep(1)

# ────────────────────────────────────────────────────────
# Main Execution
# ────────────────────────────────────────────────────────
async def main():
    errors = config.validate_config()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        sys.exit(1)

    await claimer.initialize()

    # Start X Monitor
    x_mon = XMonitor(x_tweet_callback)
    x_ok  = await x_mon.initialize()
    if x_ok:
        logger.info("🐦 X Monitor connected! Watching @cj_wawa & @yashhjhaa...")
        asyncio.create_task(x_mon.poll_timeline())
    else:
        logger.warning("⚠️ X Monitor failed to connect. Manual terminal input still works.")

    await terminal_input_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Snatcher stopped cleanly.")
    finally:
        try:
            asyncio.run(claimer.close())
        except Exception:
            pass
