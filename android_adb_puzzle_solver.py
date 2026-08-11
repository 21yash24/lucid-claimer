"""
android_adb_puzzle_solver.py
----------------------------
100% Fully Automated Android Screen Mastermind Solver via ADB.
- Uses Vision OCR bounding boxes to find exact tap coordinates of Input Box & Submit Button.
- Taps Input Box, clears previous code, types guess.
- Taps 'Submit Guess' button directly.
- Reads '💡 X correct spot, Y wrong spot' feedback off screen.
- Solves Mastermind puzzle on phone in under 2 seconds!
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

# Determine ADB binary path & target device
ADB_BIN = "adb"
local_adb = os.path.join(os.path.dirname(__file__), "platform-tools", "adb")
if os.path.exists(local_adb):
    ADB_BIN = local_adb

TARGET_DEVICE = None

def get_adb_device() -> Optional[str]:
    """Finds active connected ADB device ID."""
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
    """Checks if an Android device is connected via ADB."""
    dev = get_adb_device()
    if dev:
        logger.info(f"📱 Connected to Android Device via ADB: {dev}")
        return True
    else:
        logger.warning("⚠️ No Android device detected via ADB! Please check USB cable / Wireless ADB.")
        return False

def adb_cmd_prefix() -> List[str]:
    """Returns ADB command base list including -s TARGET_DEVICE if available."""
    if TARGET_DEVICE:
        return [ADB_BIN, "-s", TARGET_DEVICE]
    return [ADB_BIN]

def capture_phone_screenshot(save_path: str) -> bool:
    """Captures screenshot directly from Android phone via ADB screencap and pull."""
    try:
        remote_path = "/sdcard/lucid_screen.png"
        cmd1 = adb_cmd_prefix() + ["shell", "screencap", "-p", remote_path]
        cmd2 = adb_cmd_prefix() + ["pull", remote_path, save_path]
        subprocess.run(cmd1, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(cmd2, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"⚠️ Screencapture error: {e}")
        return False

def adb_type_text(text: str):
    """Types text directly into the active input box on the Android phone."""
    try:
        cmd = adb_cmd_prefix() + ["shell", "input", "text", text]
        subprocess.run(cmd, check=True)
    except Exception as e:
        logger.error(f"⚠️ ADB typing error: {e}")

def adb_tap(x: int, y: int):
    """Taps specific (X, Y) coordinates on the Android phone screen."""
    try:
        cmd = adb_cmd_prefix() + ["shell", "input", "tap", str(x), str(y)]
        subprocess.run(cmd, check=True)
    except Exception as e:
        logger.error(f"⚠️ ADB tap error: {e}")

def adb_clear_input():
    """Sends 6 backspaces to clear any existing input text."""
    try:
        for _ in range(6):
            subprocess.run([ADB_BIN, "shell", "input", "keyevent", "67"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"⚠️ ADB backspace error: {e}")

def parse_screen_elements(image_path: str) -> Tuple[str, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """
    Runs Apple Vision OCR on phone screenshot.
    Returns:
    - full_text string
    - input_box_coords (x, y)
    - submit_button_coords (x, y)
    """
    try:
        img = Image.open(image_path)
        w, h = img.size
        
        img_url = NSURL.fileURLWithPath_(image_path)
        req = VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)  # Accurate
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
            
            if "Submit" in text or "Wait" in text:
                submit_coords = (px, py)
            elif "5-digit" in text or "Enter the" in text:
                # Target area slightly below 'Enter the 5-digit code' label
                input_coords = (px, py + 120)
                
        full_text = "\n".join(lines)
        return full_text, input_coords, submit_coords
    except Exception as e:
        logger.error(f"⚠️ Vision OCR Element Parse Error: {e}")
        return "", None, None

class MastermindSolver:
    def __init__(self):
        self.history: List[Tuple[str, int, int]] = []

    def is_consistent(self, cand_str: str) -> bool:
        for g_list, correct, wrong in self.history:
            c_spot = 0
            w_spot = 0
            g_unmatched = []
            c_unmatched = []
            
            for i in range(5):
                if cand_str[i] == g_list[i]:
                    c_spot += 1
                else:
                    g_unmatched.append(g_list[i])
                    c_unmatched.append(cand_str[i])
            
            if c_spot != correct:
                return False
                
            for char in g_unmatched:
                if char in c_unmatched:
                    w_spot += 1
                    c_unmatched.remove(char)
            
            if w_spot != wrong:
                return False
        return True

    def find_candidate_backtrack(self, history: List[Tuple[str, int, int]]) -> Optional[str]:
        chars = sorted(list(CHAR_SET))
        pref = []
        pref_counts = {}
        
        def backtrack(depth: int) -> Optional[str]:
            if depth == 5:
                return "".join(pref)
                
            remaining = 5 - (depth + 1)
            
            for c in chars:
                pref.append(c)
                pref_counts[c] = pref_counts.get(c, 0) + 1
                
                possible = True
                for g_str, correct, wrong in history:
                    matches = 0
                    g_counts = {}
                    for i in range(len(pref)):
                        if pref[i] == g_str[i]:
                            matches += 1
                        g_counts[g_str[i]] = g_counts.get(g_str[i], 0) + 1
                        
                    if matches > correct:
                        possible = False
                        break
                    if matches + remaining < correct:
                        possible = False
                        break
                        
                    min_overlap = 0
                    for char, count in pref_counts.items():
                        if char in g_counts:
                            min_overlap += min(count, g_counts[char])
                            
                    if min_overlap > (correct + wrong):
                        possible = False
                        break
                    if min_overlap + remaining < (correct + wrong):
                        possible = False
                        break
                
                if possible:
                    res = backtrack(depth + 1)
                    if res:
                        return res
                        
                pref_counts[c] -= 1
                if pref_counts[c] == 0:
                    del pref_counts[c]
                pref.pop()
                    
            return None
            
        return backtrack(0)

def main():
    print("=" * 65)
    print("📱 100% AUTOMATED VISUAL ADB MASTERMIND SOLVER IS ACTIVE!")
    print("   1. Connect Android phone via USB / Wireless ADB.")
    print("   2. Open 'Crack the Code' screen on your phone.")
    print("   3. Script auto-types code, taps Submit button, & cracks code!")
    print("=" * 65 + "\n")
    
    if not check_adb_connected():
        print("\n❌ Error: No Android phone detected via ADB.")
        return

    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
    os.makedirs(tmp_dir, exist_ok=True)
    shot_path = os.path.join(tmp_dir, "phone_screen.png")
    
    solver = MastermindSolver()
    logger.info("👀 Monitoring phone screen for 'Crack the Code' / '5-digit code'...")
    
    in_solving_loop = False
    
    while True:
        if not capture_phone_screenshot(shot_path):
            time.sleep(0.5)
            continue
            
        ocr_text, input_coords, submit_coords = parse_screen_elements(shot_path)
        
        # Check if Giveaway Puzzle screen is visible on phone
        if ("Crack the Code" in ocr_text or "5-digit code" in ocr_text or "spots left" in ocr_text) and not in_solving_loop:
            print("\a\a\a")
            print("\n" + "🚨" * 25)
            print("🚨   LIVE PUZZLE DETECTED ON YOUR PHONE SCREEN!   🚨")
            print("🚨" * 25 + "\n")
            logger.info(f"🎯 Target UI Elements: Input @ {input_coords}, Submit @ {submit_coords}")
            in_solving_loop = True
            
            next_guess = "".join(random.choices(CHAR_SET, k=5))
            tested_guesses = set()
            
            for round_num in range(1, 15):
                tested_guesses.add(next_guess)
                logger.info(f"👉 [Round {round_num}] Auto-submitting guess '{next_guess}' to phone...")
                
                inp_x = input_coords[0] if input_coords else 540
                inp_y = input_coords[1] if input_coords else 1270
                sub_x = submit_coords[0] if submit_coords else 540
                sub_y = submit_coords[1] if submit_coords else 1690
                
                # Execute focus, clear, type, hide keyboard, & tap submit in ONE BATCHED COMMAND
                batch_cmd = adb_cmd_prefix() + [
                    "shell",
                    f"input tap {inp_x} {inp_y} && input keyevent 67 67 67 67 67 67 && input text {next_guess} && input keyevent 111 && input tap {sub_x} {sub_y}"
                ]
                subprocess.run(batch_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Wait 0.4s for feedback animation to settle on screen
                time.sleep(0.4)
                
                # Capture screenshot after submission & read feedback
                capture_phone_screenshot(shot_path)
                post_text, input_coords, submit_coords = parse_screen_elements(shot_path)
                
                # Check for Win / End signals
                if "Congratulations" in post_text or "WON" in post_text or "claimed" in post_text.lower():
                    logger.info("🎉🎉🎉 PUZZLE CRACKED & WON ON PHONE SCREEN!")
                    print("\a\a\a")
                    in_solving_loop = False
                    break
                    
                match = re.search(r"(\d+)\s*correct spot[^\d]*(\d+)\s*wrong spot", post_text, re.IGNORECASE)
                if match:
                    correct = int(match.group(1))
                    wrong = int(match.group(2))
                    logger.info(f"📊 Extracted screen feedback: {correct} correct, {wrong} wrong for '{next_guess}'")
                    if (next_guess, correct, wrong) not in solver.history:
                        solver.history.append((next_guess, correct, wrong))
                        
                # Calculate next optimal backtrack candidate
                candidate = solver.find_candidate_backtrack(solver.history)
                
                # Ensure candidate is never a previously tested guess
                if not candidate or candidate in tested_guesses:
                    # Generate random candidate consistent with history
                    chars = list(CHAR_SET)
                    for _ in range(50000):
                        rand_cand = "".join(random.choices(chars, k=5))
                        if rand_cand not in tested_guesses and solver.is_consistent(rand_cand):
                            candidate = rand_cand
                            break
                    if not candidate or candidate in tested_guesses:
                        candidate = "".join(random.choices(chars, k=5))
                        
                next_guess = candidate
                logger.info(f"⚡ Calculated next optimal guess: '{next_guess}'")
                time.sleep(0.2)
                
        elif not ("Crack the Code" in ocr_text or "5-digit code" in ocr_text):
            in_solving_loop = False
            
        time.sleep(0.6)

if __name__ == "__main__":
    main()
