"""
android_adb_puzzle_solver.py
----------------------------
EXPLICIT BOX-BY-BOX TAP + HARDWARE KEYEVENT METHOD.

Instead of relying on React Native's auto-advance focus (which is unreliable
with ADB input), this solver:
  1. Taps each of the 5 boxes individually at their exact screen coordinates
  2. Sends a hardware keyevent (KEYCODE_A=29, KEYCODE_0=7, etc.) for each character
  3. Each character goes directly into the focused box — no autocorrect, no auto-advance needed

This is EXACTLY what a human finger does: tap a box, press a key.

All 5 box taps + keyevents are batched into ONE single ADB shell command
for maximum speed (~800ms total for all 5 characters).
"""

import os
import re
import sys
import time
import random
import string
import subprocess
import logging
from typing import List, Tuple, Optional
from Foundation import NSURL
from Vision import VNRecognizeTextRequest, VNImageRequestHandler
from PIL import Image

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ADBPuzzleSolver")

CHAR_SET = string.digits + string.ascii_uppercase  # 0-9 and A-Z

# ─── Android Hardware Keycodes ─────────────────────────────────────────────
# These bypass GBoard autocorrect entirely. Each keycode maps to a physical key.
CHAR_TO_KEYCODE = {}
for _i, _ch in enumerate('0123456789'):
    CHAR_TO_KEYCODE[_ch] = 7 + _i    # KEYCODE_0=7 .. KEYCODE_9=16
for _i, _ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    CHAR_TO_KEYCODE[_ch] = 29 + _i   # KEYCODE_A=29 .. KEYCODE_Z=54

# ─── ADB Setup ────────────────────────────────────────────────────────────
ADB_BIN = "adb"
local_adb = os.path.join(os.path.dirname(__file__), "platform-tools", "adb")
if os.path.exists(local_adb):
    ADB_BIN = local_adb

TARGET_DEVICE = None

def get_adb_device() -> Optional[str]:
    global TARGET_DEVICE
    try:
        res = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, check=True)
        lines = [line.split()[0] for line in res.stdout.strip().split("\n")
                 if line and not line.startswith("List") and "device" in line]
        if lines:
            TARGET_DEVICE = lines[0]
            return TARGET_DEVICE
    except Exception as e:
        logger.error(f"❌ ADB devices error: {e}")
    return None

def check_adb_connected() -> bool:
    dev = get_adb_device()
    if dev:
        logger.info(f"📱 Connected to Android Device via ADB: {dev}")
        return True
    logger.warning("⚠️ No Android device detected via ADB!")
    return False

def adb_cmd_prefix() -> List[str]:
    if TARGET_DEVICE:
        return [ADB_BIN, "-s", TARGET_DEVICE]
    return [ADB_BIN]

def adb_shell(cmd: str):
    """Run a single ADB shell command."""
    subprocess.run(adb_cmd_prefix() + ["shell", cmd],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def capture_phone_screenshot(save_path: str) -> bool:
    try:
        remote = "/sdcard/lucid_screen.png"
        subprocess.run(adb_cmd_prefix() + ["shell", "screencap", "-p", remote],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(adb_cmd_prefix() + ["pull", remote, save_path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"⚠️ Screencapture error: {e}")
        return False

def parse_screen_elements(image_path: str) -> Tuple[str, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    try:
        img = Image.open(image_path)
        w, h = img.size

        img_url = NSURL.fileURLWithPath_(image_path)
        req = VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)
        req.setUsesLanguageCorrection_(False)

        handler = VNImageRequestHandler.alloc().initWithURL_options_(img_url, {})
        handler.performRequests_error_([req], None)

        results = req.results() or []
        lines = []
        input_coords = None
        submit_coords = None

        for obs in results:
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            text = candidates[0].string()
            lines.append(text)

            box = obs.boundingBox()
            px = int((box.origin.x + box.size.width / 2) * w)
            py = int((1 - (box.origin.y + box.size.height / 2)) * h)

            if "Crack" in text or "Submit" in text or "Wait" in text:
                submit_coords = (px, py)
            elif "5-digit" in text or "Enter the" in text:
                input_coords = (px, py + 120)

        return "\n".join(lines), input_coords, submit_coords
    except Exception as e:
        logger.error(f"⚠️ Vision OCR Error: {e}")
        return "", None, None


# ─── Mastermind Feedback ───────────────────────────────────────────────────
def calculate_feedback(cand: str, target: str) -> Tuple[int, int]:
    correct = sum(1 for i in range(5) if cand[i] == target[i])
    c_un = [cand[i] for i in range(5) if cand[i] != target[i]]
    t_un = [target[i] for i in range(5) if cand[i] != target[i]]
    wrong = 0
    for ch in c_un:
        if ch in t_un:
            wrong += 1
            t_un.remove(ch)
    return correct, wrong


class BulletproofMastermindEngine:
    def __init__(self):
        self.openings = ['01234', '56789', 'ABCDE', 'FGHIJ']
        self.opening_idx = 0
        self.history: List[Tuple[str, int, int]] = []
        self.tested: set = set()
        self.dead_chars: set = set()
        self.best_guess: Optional[str] = None
        self.best_correct: int = 0
        self.stuck_counter: int = 0

    def get_next_guess(self, last_guess: Optional[str], c: Optional[int], w: Optional[int]) -> str:
        if last_guess and c is not None and w is not None:
            self.history.append((last_guess, c, w))
            self.tested.add(last_guess)

            if c == 0 and w == 0 and len(self.dead_chars) <= 15:
                for ch in last_guess:
                    self.dead_chars.add(ch)
                logger.info(f"🚫 Dead chars pool: {len(self.dead_chars)} total.")

            if c > self.best_correct:
                self.best_correct = c
                self.best_guess = last_guess
                logger.info(f"🔒 Best pattern: '{last_guess}' ({c} correct)")

        if self.opening_idx < len(self.openings):
            g = self.openings[self.opening_idx]
            self.opening_idx += 1
            return g

        active = [ch for ch in CHAR_SET if ch not in self.dead_chars]
        if len(active) < 5:
            self.dead_chars.clear()
            active = list(CHAR_SET)

        for _ in range(150000):
            cc = []
            for i in range(5):
                if self.best_guess and self.best_correct >= 2 and random.random() < 0.65:
                    cc.append(self.best_guess[i])
                else:
                    cc.append(random.choice(active))
            cand = ''.join(cc)
            if cand not in self.tested:
                if all(calculate_feedback(gp, cand) == (ce, we)
                       for gp, ce, we in self.history):
                    self.stuck_counter = 0
                    return cand

        self.stuck_counter += 1
        logger.warning(f"⚠️ Contradictory history! Dropping oldest (stuck={self.stuck_counter})")
        if self.history:
            self.history.pop(0)
        while True:
            r = ''.join(random.choices(active, k=5))
            if r not in self.tested:
                return r


# ─── EXPLICIT BOX-BY-BOX INPUT ─────────────────────────────────────────────
# This is the core innovation. Instead of relying on React Native's flaky
# auto-advance focus mechanism, we TAP each box individually and type
# ONE character into it using hardware keycodes.

BOX_SPACING = 160  # pixels between adjacent box centers on 1080px-wide screen

def get_box_x_positions(center_x: int) -> List[int]:
    """Returns [box1_x, box2_x, box3_x, box4_x, box5_x] centered at center_x."""
    return [
        center_x - 2 * BOX_SPACING,
        center_x - BOX_SPACING,
        center_x,
        center_x + BOX_SPACING,
        center_x + 2 * BOX_SPACING,
    ]

def send_explicit_box_guess(guess: str, center_x: int, inp_y: int,
                             sub_x: int, sub_y: int):
    """
    EXPLICIT BOX-BY-BOX TAP + HARDWARE KEYEVENT.

    For each of the 5 boxes:
      1. Tap the box at its exact (x, y) coordinate → focus goes to that box
      2. Send KEYCODE_MOVE_END (123) → cursor at end of any existing text
      3. Send KEYCODE_DEL (67) → backspace clears old character
      4. Send hardware keyevent for the new character → typed into this box
      5. Wait 60ms for React Native state to settle

    All 5 box operations are batched into ONE single ADB shell command
    to minimize USB/process overhead. Total typing time: ~800ms.

    Then taps 'Crack It' button.
    """
    box_x = get_box_x_positions(center_x)
    parts = []

    for i, ch in enumerate(guess):
        kc = CHAR_TO_KEYCODE.get(ch.upper())
        if kc is None:
            logger.error(f"❌ No keycode for character '{ch}'! Skipping.")
            continue

        # 1. Tap the specific box
        parts.append(f"input tap {box_x[i]} {inp_y}")
        # 2. Wait for focus
        parts.append("sleep 0.05")
        # 3. MOVE_END + BACKSPACE = clear any existing character
        parts.append("input keyevent 123 67")
        # 4. Small settle
        parts.append("sleep 0.03")
        # 5. Type the character via hardware keyevent
        parts.append(f"input keyevent {kc}")
        # 6. Wait for React Native state update (not needed for last box)
        if i < 4:
            parts.append("sleep 0.06")

    # 7. Final settle before tapping submit
    parts.append("sleep 0.1")
    # 8. Tap Crack It button
    parts.append(f"input tap {sub_x} {sub_y}")

    full_cmd = " && ".join(parts)
    subprocess.run(adb_cmd_prefix() + ["shell", full_cmd],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"   ✅ Typed '{guess}' box-by-box & tapped Crack It @ ({sub_x}, {sub_y})")


def warm_up_keyboard(center_x: int, inp_y: int):
    """
    On the first round, taps Box 1 to open the GBoard keyboard.
    Waits 400ms for the keyboard animation to complete and the layout to settle.
    """
    box1_x = center_x - 2 * BOX_SPACING
    adb_shell(f"input tap {box1_x} {inp_y}")
    time.sleep(0.4)
    logger.info("   ⌨️ Keyboard warm-up: tapped Box 1 to open keyboard")


# ─── Main Loop ─────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("🚀 LUCID APP MASTERMIND SOLVER — EXPLICIT BOX-TAP METHOD")
    print("   ⚡ Taps each box individually + hardware keyevent per char")
    print("   ⚡ NO auto-advance reliance — 100% explicit focus control")
    print("   ⚡ All 5 chars in ONE batched ADB shell command (~800ms)")
    print("   ⚡ 3.1s cooldown lock between submissions")
    print("=" * 65 + "\n")

    if not check_adb_connected():
        print("\n❌ Error: No Android phone detected via ADB.")
        return

    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
    os.makedirs(tmp_dir, exist_ok=True)
    shot_path = os.path.join(tmp_dir, "phone_screen.png")

    solver = BulletproofMastermindEngine()
    logger.info("👀 Monitoring phone screen for 'Crack the Code' / 'Crack It' / '5-digit code'...")

    in_solving_loop = False
    last_submit_time = 0.0

    while True:
        if not capture_phone_screenshot(shot_path):
            time.sleep(0.3)
            continue

        ocr_text, input_coords, submit_coords = parse_screen_elements(shot_path)

        puzzle_visible = ("Crack the Code" in ocr_text or "Crack It" in ocr_text
                          or "5-digit code" in ocr_text or "spots left" in ocr_text)

        if puzzle_visible and not in_solving_loop:
            print("\a\a\a")
            print("\n" + "🚨" * 25)
            print("🚨   LIVE PUZZLE DETECTED ON YOUR PHONE SCREEN!   🚨")
            print("🚨" * 25 + "\n")
            logger.info(f"🎯 Target: Input @ {input_coords}, Submit @ {submit_coords}")
            in_solving_loop = True

            solver = BulletproofMastermindEngine()
            next_guess = solver.get_next_guess(None, None, None)
            round_num = 0
            last_submit_time = 0.0
            keyboard_warmed = False

            while in_solving_loop:
                round_num += 1

                # 3.1s cooldown between submissions
                elapsed = time.time() - last_submit_time
                if elapsed < 3.1 and last_submit_time > 0:
                    time.sleep(3.1 - elapsed)

                logger.info(f"👉 [Round {round_num}] Submitting '{next_guess}'...")
                last_submit_time = time.time()

                # Fresh screenshot for updated coordinates
                capture_phone_screenshot(shot_path)
                ocr_text, input_coords, submit_coords = parse_screen_elements(shot_path)

                center_x = input_coords[0] if input_coords else 540
                inp_y = input_coords[1] if input_coords else 1019
                sub_x = submit_coords[0] if submit_coords else 540
                sub_y = submit_coords[1] if submit_coords else 1220

                # First round: open keyboard and re-detect layout
                if not keyboard_warmed:
                    warm_up_keyboard(center_x, inp_y)
                    keyboard_warmed = True
                    # Re-scan with keyboard now open
                    capture_phone_screenshot(shot_path)
                    _, input_coords, submit_coords = parse_screen_elements(shot_path)
                    if input_coords:
                        center_x = input_coords[0]
                        inp_y = input_coords[1]
                    if submit_coords:
                        sub_x = submit_coords[0]
                        sub_y = submit_coords[1]

                # EXPLICIT BOX-BY-BOX TYPING
                send_explicit_box_guess(next_guess, center_x, inp_y, sub_x, sub_y)

                # Wait 0.7s for feedback animation to settle
                time.sleep(0.7)

                # Read feedback (up to 3 attempts)
                correct = None
                wrong = None
                clean_ocr = ""

                for _ in range(3):
                    capture_phone_screenshot(shot_path)
                    post_text, input_coords, submit_coords = parse_screen_elements(shot_path)

                    clean_ocr = re.sub(r'\b[Oo]\b', '0', post_text)
                    clean_ocr = re.sub(r'[\|l]', '1', clean_ocr)

                    if "Congratulations" in clean_ocr or "WON" in clean_ocr or "claimed" in clean_ocr.lower():
                        logger.info("🎉🎉🎉 PUZZLE CRACKED! YOU WON!")
                        print("\a\a\a")
                        in_solving_loop = False
                        break

                    if not ("Crack the Code" in clean_ocr or "Crack It" in clean_ocr
                            or "5-digit" in clean_ocr or "spots left" in clean_ocr):
                        logger.info("ℹ️ Puzzle screen gone. Exiting.")
                        in_solving_loop = False
                        break

                    m = re.search(r"(\d+)\s*correct\s*spot[^\d]*(\d+)\s*wrong\s*spot",
                                  clean_ocr, re.IGNORECASE)
                    if not m:
                        m = re.search(r"(\d+)\s*correct[^\d]*(\d+)\s*wrong",
                                      clean_ocr, re.IGNORECASE)
                    if m:
                        correct = int(m.group(1))
                        wrong = int(m.group(2))
                        logger.info(f"📊 Feedback: {correct} correct, {wrong} wrong for '{next_guess}'")
                        break
                    time.sleep(0.3)

                if not in_solving_loop:
                    break

                if correct is None or wrong is None:
                    logger.warning(f"⚠️ Could not parse feedback for '{next_guess}'. OCR: {repr(clean_ocr[:120])}")

                next_guess = solver.get_next_guess(next_guess, correct, wrong)
                time.sleep(0.15)

        elif not puzzle_visible:
            in_solving_loop = False

        time.sleep(0.4)


if __name__ == "__main__":
    main()
