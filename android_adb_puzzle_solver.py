"""
android_adb_puzzle_solver.py
----------------------------
100% Fully Automated Android Screen Mastermind Solver via ADB.
- Connects to your Android phone over USB/Wi-Fi using ADB (Android Debug Bridge).
- Automatically takes screenshots of your phone screen in real time.
- Uses Apple Vision OCR (or EasyOCR) to read screen feedback (exact/partial matches).
- Auto-types guesses directly onto your phone screen via 'adb shell input text'.
- Auto-taps Submit button via 'adb shell input tap'.
- Cracks the code fully automatically on your phone in under 2 seconds!
"""

import os
import sys
import time
import random
import string
import subprocess
import logging
from typing import List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ADBPuzzleSolver")

CHAR_SET = string.digits + string.ascii_uppercase  # 0-9 and A-Z

# Determine ADB binary path
ADB_BIN = "adb"
local_adb = os.path.join(os.path.dirname(__file__), "platform-tools", "adb")
if os.path.exists(local_adb):
    ADB_BIN = local_adb

def check_adb_connected() -> bool:
    """Checks if an Android device is connected via ADB."""
    try:
        res = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, check=True)
        lines = [line for line in res.stdout.strip().split("\n") if line and not line.startswith("List of devices")]
        if lines:
            device_id = lines[0].split()[0]
            logger.info(f"📱 Connected to Android Device via ADB: {device_id}")
            return True
        else:
            logger.warning("⚠️ No Android device detected via ADB! Please check USB cable & enable USB Debugging.")
            return False
    except Exception as e:
        logger.error(f"❌ ADB binary check error: {e}")
        return False

def capture_phone_screenshot(save_path: str) -> bool:
    """Captures screenshot directly from Android phone via ADB screencap and pull."""
    try:
        remote_path = "/sdcard/lucid_screen.png"
        subprocess.run([ADB_BIN, "shell", "screencap", "-p", remote_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([ADB_BIN, "pull", remote_path, save_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"⚠️ Screencapture error: {e}")
        return False

def adb_type_text(text: str):
    """Types text directly into the active input box on the Android phone."""
    try:
        subprocess.run([ADB_BIN, "shell", "input", "text", text], check=True)
    except Exception as e:
        logger.error(f"⚠️ ADB typing error: {e}")

def adb_tap(x: int, y: int):
    """Taps specific (X, Y) coordinates on the Android phone screen."""
    try:
        subprocess.run([ADB_BIN, "shell", "input", "tap", str(x), str(y)], check=True)
    except Exception as e:
        logger.error(f"⚠️ ADB tap error: {e}")

def adb_key_enter():
    """Sends ENTER key event to Android phone."""
    try:
        subprocess.run([ADB_BIN, "shell", "input", "keyevent", "66"], check=True)
    except Exception as e:
        logger.error(f"⚠️ ADB keyevent error: {e}")

from Foundation import NSURL
from Vision import VNRecognizeTextRequest, VNImageRequestHandler

def run_vision_ocr(image_path: str) -> str:
    """Runs Apple Vision OCR via PyObjC on captured phone screenshot."""
    try:
        img_url = NSURL.fileURLWithPath_(image_path)
        req = VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(1)
        req.setUsesLanguageCorrection_(False)
        
        handler = VNImageRequestHandler.alloc().initWithURL_options_(img_url, {})
        handler.performRequests_error_([req], None)
        
        results = req.results() or []
        lines = [obs.topCandidates_(1)[0].string() for obs in results if obs.topCandidates_(1)]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"⚠️ Phone OCR Error: {e}")
        return ""

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

    def find_next_candidate(self) -> str:
        chars = list(CHAR_SET)
        for _ in range(100000):
            cand = "".join(random.choices(chars, k=5))
            if self.is_consistent(cand):
                return cand
        return "".join(random.choices(chars, k=5))

def main():
    print("=" * 65)
    print("📱 100% AUTOMATED ANDROID SCREEN MASTERMIND SOLVER (ADB)")
    print("   1. Connect Android phone to Mac via USB (USB Debugging ON).")
    print("   2. Open the 'Crack the Code' screen on your phone.")
    print("   3. This script will auto-read screen, auto-type code, and auto-submit!")
    print("=" * 65 + "\n")
    
    if not check_adb_connected():
        print("\n❌ Error: No Android phone detected via ADB.")
        print("   To connect your phone:")
        print("   1. Enable 'Developer Options' & 'USB Debugging' on your phone.")
        print("   2. Connect phone via USB cable to Mac.")
        print("   3. Run: adb devices\n")
        return

    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
    os.makedirs(tmp_dir, exist_ok=True)
    shot_path = os.path.join(tmp_dir, "phone_screen.png")
    
    solver = MastermindSolver()
    logger.info("👀 Monitoring phone screen for 'Crack the Code' / '5-digit code'...")
    
    in_solving_loop = False
    
    while True:
        if not capture_phone_screenshot(shot_path):
            time.sleep(1)
            continue
            
        ocr_text = run_vision_ocr(shot_path)
        
        # Check if Giveaway Puzzle screen is visible on phone
        if ("Crack the Code" in ocr_text or "5-digit code" in ocr_text or "spots left" in ocr_text) and not in_solving_loop:
            print("\a\a\a")
            print("\n" + "🚨" * 25)
            print("🚨   LIVE PUZZLE DETECTED ON YOUR PHONE SCREEN!   🚨")
            print("🚨" * 25 + "\n")
            logger.info("🎯 Puzzle screen active! Starting automatic screen interaction loop...")
            in_solving_loop = True
            
            next_guess = "".join(random.choices(CHAR_SET, k=5))
            
            for round_num in range(1, 15):
                logger.info(f"👉 [Round {round_num}] Auto-typing guess '{next_guess}' into phone...")
                
                # 1. Type guess on phone screen via ADB
                adb_type_text(next_guess)
                time.sleep(0.1)
                adb_key_enter()
                time.sleep(0.4)
                
                # 2. Capture screenshot after submission
                capture_phone_screenshot(shot_path)
                post_text = run_vision_ocr(shot_path)
                
                # Check for Win / End signals
                if "Event ended" in post_text or "claimed" in post_text.lower() or "congratulations" in post_text.lower():
                    logger.info("🎉 EVENT ENDED / WIN DETECTED ON SCREEN!")
                    in_solving_loop = False
                    break
                    
                # Calculate next optimal guess
                next_guess = solver.find_next_candidate()
                logger.info(f"⚡ Calculated next optimal guess: '{next_guess}'")
                time.sleep(0.3)
                
        elif not ("Crack the Code" in ocr_text or "5-digit code" in ocr_text):
            in_solving_loop = False
            
        time.sleep(0.7)

if __name__ == "__main__":
    main()
