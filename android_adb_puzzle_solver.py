"""
android_adb_puzzle_solver.py
----------------------------
REAL LUCID APP / SIMULATOR MASTERMIND PUZZLE SOLVER ENGINE.
- Auto-detects Simulator vs Real App mode based on OCR text content.
- Uses exact hardcoded Y and X coordinates verified by pixel-level analysis for both modes.
- Batch box-by-box input with 80ms settle delay to ensure 100% browser/app focus.
- Wipes simulator inputs instantly via ESCAPE key (keycode 111).
- Wipes real app inputs via backward-backspace clearing.
- 3.1s Cooldown Lock ensures 100% accepted submissions.
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

# Android Hardware Keycodes mapping
CHAR_TO_KEYCODE = {}
for i, ch in enumerate('0123456789'):
    CHAR_TO_KEYCODE[ch] = 7 + i
for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    CHAR_TO_KEYCODE[ch] = 29 + i

ADB_BIN = "adb"
local_adb = os.path.join(os.path.dirname(__file__), "platform-tools", "adb")
if os.path.exists(local_adb):
    ADB_BIN = local_adb

TARGET_DEVICE = None

def get_adb_device() -> Optional[str]:
    global TARGET_DEVICE
    try:
        res = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, check=True)
        lines = [line.split()[0] for line in res.stdout.strip().split("\n") if line and not line.startswith("List of devices") and "device" in line]
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
    return False

def adb_cmd_prefix() -> List[str]:
    if TARGET_DEVICE:
        return [ADB_BIN, "-s", TARGET_DEVICE]
    return [ADB_BIN]

def capture_phone_screenshot(save_path: str) -> bool:
    try:
        remote_path = "/sdcard/lucid_screen.png"
        subprocess.run(adb_cmd_prefix() + ["shell", "screencap", "-p", remote_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(adb_cmd_prefix() + ["pull", remote_path, save_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"⚠️ Screencapture error: {e}")
        return False

def parse_screen_elements(image_path: str) -> str:
    try:
        img_url = NSURL.fileURLWithPath_(image_path)
        req = VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)
        req.setUsesLanguageCorrection_(False)
        
        handler = VNImageRequestHandler.alloc().initWithURL_options_(img_url, {})
        handler.performRequests_error_([req], None)
        
        results = req.results() or []
        lines = [obs.topCandidates_(1)[0].string() for obs in results if obs.topCandidates_(1)]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"⚠️ Vision OCR Element Parse Error: {e}")
        return ""

def calculate_feedback(cand: str, target: str) -> Tuple[int, int]:
    correct = sum(1 for i in range(5) if cand[i] == target[i])
    c_unmatched = [cand[i] for i in range(5) if cand[i] != target[i]]
    t_unmatched = [target[i] for i in range(5) if cand[i] != target[i]]
    wrong = 0
    for char in c_unmatched:
        if char in t_unmatched:
            wrong += 1
            t_unmatched.remove(char)
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
            
            if c == 0 and w == 0:
                if len(self.dead_chars) <= 15:
                    for char in last_guess:
                        self.dead_chars.add(char)
                    logger.info(f"🚫 Eliminated dead characters: {set(last_guess)}. Total: {len(self.dead_chars)}")
            
            if c > self.best_correct:
                self.best_correct = c
                self.best_guess = last_guess
                logger.info(f"🔒 Locked new best matching pattern: '{last_guess}' ({c} correct)")

        if self.opening_idx < len(self.openings):
            g = self.openings[self.opening_idx]
            self.opening_idx += 1
            return g

        active_chars = [ch for ch in CHAR_SET if ch not in self.dead_chars]
        if len(active_chars) < 5:
            self.dead_chars.clear()
            active_chars = list(CHAR_SET)

        for attempt in range(150000):
            cand_chars = []
            for i in range(5):
                if self.best_guess and self.best_correct >= 2 and random.random() < 0.65:
                    cand_chars.append(self.best_guess[i])
                else:
                    cand_chars.append(random.choice(active_chars))
            cand = ''.join(cand_chars)
            
            if cand not in self.tested:
                if all(calculate_feedback(g_past, cand) == (c_exp, w_exp) for g_past, c_exp, w_exp in self.history):
                    self.stuck_counter = 0
                    return cand

        self.stuck_counter += 1
        logger.warning(f"⚠️ Contradictory history! Dropping oldest feedback.")
        if self.history:
            self.history.pop(0)
            
        while True:
            r = ''.join(random.choices(active_chars, k=5))
            if r not in self.tested:
                return r

# EXACT COORDINATES FROM PIXEL ANALYSIS
SIM_BOX_X = [172, 356, 540, 724, 908]
SIM_INP_Y = 1295
SIM_SUB_Y = 1417

REAL_BOX_X = [162, 308, 452, 596, 742]
REAL_INP_Y = 1019
REAL_SUB_Y = 1200

def send_guess_coordinate_mode(guess: str, is_simulator: bool):
    """
    Sends guess using exact coordinates and hardware keyevents.
    - Types box-by-box with 80ms focus settle delay to guarantee focus.
    """
    box_x = SIM_BOX_X if is_simulator else REAL_BOX_X
    inp_y = SIM_INP_Y if is_simulator else REAL_INP_Y
    sub_y = SIM_SUB_Y if is_simulator else REAL_SUB_Y
    sub_x = 540
    
    parts = []
    
    # Step 1: Wipe all boxes
    if is_simulator:
        # Simulator instant clear via ESC key
        parts.append("input keyevent 111")
        parts.append("sleep 0.1")
    else:
        # Real app reverse backspace clear (tap Box 5, backspace 6 times, tap Box 1, backspace 1 time)
        parts.append(f"input tap {box_x[4]} {inp_y}")
        parts.append("sleep 0.05")
        parts.append("input keyevent 67 67 67 67 67")
        parts.append("sleep 0.05")
        parts.append(f"input tap {box_x[0]} {inp_y}")
        parts.append("sleep 0.05")
        parts.append("input keyevent 67")
        parts.append("sleep 0.08")
        
    # Step 2: Input box-by-box with 80ms focus delay
    for i, ch in enumerate(guess):
        kc = CHAR_TO_KEYCODE.get(ch.upper())
        if kc is not None:
            parts.append(f"input tap {box_x[i]} {inp_y}")
            parts.append("sleep 0.08")
            parts.append("input keyevent 123 67")  # MOVE_END + BACKSPACE
            parts.append("sleep 0.03")
            parts.append(f"input keyevent {kc}")
            if i < 4:
                parts.append("sleep 0.08")
                
    # Step 3: Tap Crack It
    parts.append("sleep 0.15")
    parts.append(f"input tap {sub_x} {sub_y}")
    
    full_cmd = " && ".join(parts)
    subprocess.run(adb_cmd_prefix() + ["shell", full_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"   ✅ Submitted guess '{guess}' via {'Simulator' if is_simulator else 'Real App'} Mode")

def main():
    print("=" * 65)
    print("🚀 REAL LUCID APP MASTERMIND SOLVER IS ACTIVE!")
    print("   - Auto Mode Detection: Simulator vs Real App")
    print("   - Exact hardcoded layouts from pixel-level analysis")
    print("   - Batch box-by-box typing with 80ms settle delay")
    print("   - Wipes simulator inputs instantly via ESCAPE key (keycode 111)")
    print("=" * 65 + "\n")
    
    if not check_adb_connected():
        print("\n❌ Error: No Android phone detected via ADB.")
        return

    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
    os.makedirs(tmp_dir, exist_ok=True)
    shot_path = os.path.join(tmp_dir, "phone_screen.png")
    
    solver = BulletproofMastermindEngine()
    logger.info("👀 Monitoring phone screen...")
    
    in_solving_loop = False
    last_submit_time = 0.0
    
    while True:
        if not capture_phone_screenshot(shot_path):
            time.sleep(0.3)
            continue
            
        ocr_text = parse_screen_elements(shot_path)
        
        # Check if Giveaway Puzzle screen is visible on phone
        puzzle_visible = "Crack the Code" in ocr_text or "Crack It" in ocr_text or "5-digit code" in ocr_text or "spots left" in ocr_text
        
        if puzzle_visible and not in_solving_loop:
            print("\a\a\a")
            print("\n" + "🚨" * 25)
            print("🚨   LIVE PUZZLE DETECTED ON YOUR PHONE SCREEN!   🚨")
            print("🚨" * 25 + "\n")
            
            # Auto-detect if browser simulator or real app is running
            is_simulator = "192.168" in ocr_text or "8000" in ocr_text or "Giveaway - Luci" in ocr_text
            logger.info(f"ℹ️ Auto-detected mode: {'SIMULATOR' if is_simulator else 'REAL APP'}")
            
            in_solving_loop = True
            solver = BulletproofMastermindEngine()
            next_guess = solver.get_next_guess(None, None, None)
            round_num = 0
            last_submit_time = 0.0
            
            # Warm up keyboard on first round
            box_x = SIM_BOX_X if is_simulator else REAL_BOX_X
            inp_y = SIM_INP_Y if is_simulator else REAL_INP_Y
            subprocess.run(adb_cmd_prefix() + ["shell", f"input tap {box_x[0]} {inp_y}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.4)
            
            while in_solving_loop:
                round_num += 1
                
                # Enforce minimum 3.1s interval between Submit taps so app cooldown is 100% expired!
                elapsed = time.time() - last_submit_time
                if elapsed < 3.1 and last_submit_time > 0:
                    time.sleep(3.1 - elapsed)
                
                logger.info(f"👉 [Round {round_num}] Submitting guess '{next_guess}'...")
                last_submit_time = time.time()
                
                # Submit the guess using the coordinate-based tap method
                send_guess_coordinate_mode(next_guess, is_simulator)
                
                # Wait 0.65s for feedback animation to settle completely on screen
                time.sleep(0.65)
                
                # Try reading feedback up to 3 times
                correct = None
                wrong = None
                clean_ocr_text = ""
                
                for attempt in range(3):
                    capture_phone_screenshot(shot_path)
                    post_text = parse_screen_elements(shot_path)
                    
                    # Sanitize OCR text (replace letter 'O'/'o' with digit '0', '|' / 'l' with '1')
                    clean_ocr_text = re.sub(r'\b[Oo]\b', '0', post_text)
                    clean_ocr_text = re.sub(r'[\|l]', '1', clean_ocr_text)
                    
                    # Check for Win / End signals or screen navigation away
                    if "Congratulations" in clean_ocr_text or "WON" in clean_ocr_text or "claimed" in clean_ocr_text.lower():
                        logger.info("🎉🎉🎉 PUZZLE CRACKED & WON ON PHONE SCREEN!")
                        print("\a\a\a")
                        in_solving_loop = False
                        break
                        
                    if not ("Crack the Code" in clean_ocr_text or "Crack It" in clean_ocr_text or "5-digit code" in clean_ocr_text or "spots left" in clean_ocr_text):
                        logger.info("ℹ️ Puzzle screen no longer visible. Exiting solver loop...")
                        in_solving_loop = False
                        break
                        
                    match = re.search(r"(\d+)\s*correct\s*spot[^\d]*(\d+)\s*wrong\s*spot", clean_ocr_text, re.IGNORECASE)
                    if not match:
                        match = re.search(r"(\d+)\s*correct[^\d]*(\d+)\s*wrong", clean_ocr_text, re.IGNORECASE)
                        
                    if match:
                        correct = int(match.group(1))
                        wrong = int(match.group(2))
                        logger.info(f"📊 Extracted screen feedback: {correct} correct, {wrong} wrong for '{next_guess}'")
                        break
                    else:
                        time.sleep(0.3)
                        
                if not in_solving_loop:
                    break
                    
                if correct is None or wrong is None:
                    logger.warning(f"⚠️ Could not parse feedback text from screen for '{next_guess}'. OCR Text snippet: {repr(clean_ocr_text[:150])}")
                    
                # Calculate next optimal guess using BulletproofMastermindEngine
                next_guess = solver.get_next_guess(next_guess, correct, wrong)
                time.sleep(0.15)
                
        elif not puzzle_visible:
            in_solving_loop = False
            
        time.sleep(0.4)

if __name__ == "__main__":
    main()
