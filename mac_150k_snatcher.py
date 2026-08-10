"""
mac_150k_snatcher.py
--------------------
CLEAN VERSION — Only 2 triggers:
  1. X Monitor: Polls @cj_wawa & @yashhjhaa for NEW tweets with coupon codes.
  2. Terminal Input: Manually type/paste a code and press ENTER.

NO clipboard snooping. NO screen OCR. NO random code triggering.
"""

import os
import sys
import asyncio
import logging
import subprocess
import ctypes
import ssl
import aiohttp

# Bypass SSL on Mac
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
        import time; time.sleep(0.05)
        e_up   = cg.CGEventCreateMouseEvent(None, 2, pt, 0)
        cg.CGEventPost(0, e_up)
        logger.info(f"🖱️ Native CGEvent Clicked at ({x}, {y})")
        return True
    except Exception as e:
        logger.debug(f"Native Mac click error: {e}")
        return False

# ────────────────────────────────────────────────────────
# Screen helpers: find coupon input + Apply Coupon button
# ────────────────────────────────────────────────────────
def _get_display_scale():
    """Return (display_w, display_h, img_w, img_h, scale_x, scale_y)."""
    import cv2
    shot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_images", "screen_shot.png")
    os.makedirs(os.path.dirname(shot_path), exist_ok=True)
    subprocess.run(['screencapture', '-x', shot_path], capture_output=True)
    img = cv2.imread(shot_path)
    if img is None:
        raise RuntimeError("screencapture failed")
    img_h, img_w = img.shape[:2]
    res = subprocess.run(
        ['osascript', '-e', 'tell application "Finder" to get bounds of window of desktop'],
        capture_output=True, text=True
    )
    parts = [int(p.strip()) for p in res.stdout.strip().split(',')] if res.stdout.strip() else [0, 0, 1470, 956]
    disp_w = parts[2] - parts[0]
    disp_h = parts[3] - parts[1]
    return img, img_w, img_h, disp_w, disp_h, img_w / float(disp_w), img_h / float(disp_h)


def find_coupon_input_coords():
    """
    Returns (input_x, input_y, btn_x, btn_y) in display points
    by looking for the small green 'Apply Coupon' button (top half of screen).
    """
    try:
        import cv2, numpy as np
        img, img_w, img_h, disp_w, disp_h, scale_x, scale_y = _get_display_scale()

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        buttons = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            y_disp = y / scale_y
            w_disp = w / scale_x
            if area > 300 * (scale_x * scale_y) and w > h and y_disp < 450 and w_disp < 220:
                buttons.append((x, y, w, h))

        if not buttons:
            logger.warning("⚠️ Apply Coupon button not found in top half of modal!")
            return None

        buttons.sort(key=lambda b: b[1])
        bx, by, bw, bh = buttons[0]

        # Input box is ~150px to the left of the button (in screen pixels)
        ix_px = max(10, bx - int(150 * scale_x))
        iy_px = by + bh // 2

        return (
            int(ix_px / scale_x),          # input display x
            int(iy_px / scale_y),           # input display y
            int((bx + bw // 2) / scale_x), # button display x
            int((by + bh // 2) / scale_y), # button display y
        )
    except Exception as e:
        logger.debug(f"Coupon field detection error: {e}")
        return None


def find_and_click_proceed_button():
    """
    Looks for the wide green PROCEED TO PAYMENT button (bottom half of modal)
    and clicks it.
    """
    try:
        import cv2, numpy as np
        img, img_w, img_h, disp_w, disp_h, scale_x, scale_y = _get_display_scale()

        hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([85, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area  = cv2.contourArea(c)
            y_disp = y / scale_y
            w_disp = w / scale_x
            # Wide button in bottom half of screen
            if area > 1000 * (scale_x * scale_y) and w > h * 3 and y_disp > 450 and w_disp > 200:
                candidates.append((x, y, w, h))

        if not candidates:
            logger.warning("⚠️ PROCEED TO PAYMENT button not found (no wide green region)!")
            return False

        candidates.sort(key=lambda b: b[1])
        bx, by, bw, bh = candidates[0]
        cx = int((bx + bw // 2) / scale_x)
        cy = int((by + bh // 2) / scale_y)
        logger.info(f"🎯 Found PROCEED TO PAYMENT at display coords ({cx}, {cy})")
        return native_mac_click(cx, cy)
    except Exception as e:
        logger.debug(f"PROCEED button detection error: {e}")
        return False


# ────────────────────────────────────────────────────────
# Chrome auto-paste
# ────────────────────────────────────────────────────────
def paste_code_to_chrome(code: str):
    """
    Pastes code into the Lucid Trading checkout coupon field and clicks Apply Coupon.
    Uses fixed hardcoded display coordinates confirmed working on this Mac:
      - Coupon input box:    (325, 220)
      - Apply Coupon button: (532, 220)
      - PROCEED TO PAYMENT:  (323, 760)
    """
    import time

    # Put code in clipboard
    subprocess.run(['pbcopy'], input=code.encode('utf-8'))

    # 1. Focus Chrome
    subprocess.run(
        ['osascript', '-e', 'tell application "Google Chrome" to activate'],
        capture_output=True
    )
    time.sleep(0.3)

    # 2. Click coupon input box at fixed coord
    native_mac_click(325, 220)
    time.sleep(0.15)

    # 3. Select all existing text + paste new code
    subprocess.run(['osascript', '-e', '''
    tell application "System Events"
        keystroke "a" using {command down}
        delay 0.05
        keystroke "v" using {command down}
    end tell
    '''], capture_output=True)
    time.sleep(0.15)

    # 4. Click Apply Coupon button at fixed coord
    native_mac_click(532, 220)
    logger.info(f"🖱️ Clicked input (325,220), pasted '{code}', clicked Apply Coupon (532,220)!")

    # 5. Wait for coupon validation
    time.sleep(2.5)

    # 6. Click PROCEED TO PAYMENT at fixed coord
    native_mac_click(323, 760)
    logger.info(f"🖱️ Clicked PROCEED TO PAYMENT (323,760)!")




# ────────────────────────────────────────────────────────
# Core snatch logic — called ONCE per unique code
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

    # 1. Auto-paste into Chrome (runs synchronously so it happens first)
    paste_code_to_chrome(code)

    # 2. Background: Direct API + Secret API checkout
    task_150k  = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="150k"))
    task_secret= asyncio.create_task(claimer.claim_all_accounts(code))
    task_50k   = asyncio.create_task(claimer.checkout_all_accounts(code, plan_id="50k"))

    await asyncio.gather(task_150k, task_secret, task_50k, return_exceptions=True)
    logger.info("🏁 Snatch complete for code.")


# ────────────────────────────────────────────────────────
# X Tweet callback
# ────────────────────────────────────────────────────────
async def x_tweet_callback(codes: list, tweet_text: str = ""):
    logger.info(f"🐦 New tweet! Codes found: {codes}")
    for c in codes:
        await snatch_code(c, origin="Twitter/X")


# ────────────────────────────────────────────────────────
# Terminal input — manual override
# ────────────────────────────────────────────────────────
async def terminal_input_loop():
    loop = asyncio.get_running_loop()
    print("\n" + "=" * 65)
    print("🎯 MAC 150K SNATCHER IS ACTIVE!")
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
# Main
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

    # Block on terminal input (clean exit with Ctrl+C)
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
