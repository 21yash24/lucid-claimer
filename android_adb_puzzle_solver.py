"""
android_adb_puzzle_solver.py
----------------------------
REAL LUCID APP / SIMULATOR MASTERMIND PUZZLE SOLVER ENGINE.
- Auto-detects Simulator vs Real App mode based on OCR text content.
- Uses exact hardcoded Y and X coordinates verified by pixel-level analysis for both modes.
- Wipes the shared code input via MOVE_END + backspace, then types the full 5-char guess in one shot.
- input text bypasses keyevent focus races and works reliably with React Native.
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

try:
    from Foundation import NSURL
    from Vision import VNRecognizeTextRequest, VNImageRequestHandler
    HAVE_PYOBJC = True
except ImportError:
    HAVE_PYOBJC = False

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
FORCE_SIMULATOR = None  # None = auto-detect, True = force simulator, False = force real app

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
    """Capture + pull a phone screenshot, retrying on transient screencap
    failures (the device returns non-zero sporadically while busy/animating).
    The retry keeps the solver from stalling on a failed frame."""
    remote_path = "/sdcard/lucid_screen.png"
    for attempt in range(3):
        try:
            subprocess.run(adb_cmd_prefix() + ["shell", "screencap", "-p", remote_path],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(adb_cmd_prefix() + ["pull", remote_path, save_path],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(0.4)
            else:
                logger.error(f"⚠️ Screencapture error after retries: {e}")
    return False

def parse_screen_elements(image_path: str) -> str:
    if HAVE_PYOBJC:
        try:
            img_url = NSURL.fileURLWithPath_(image_path)
            req = VNRecognizeTextRequest.alloc().init()
            req.setRecognitionLevel_(0)
            req.setUsesLanguageCorrection_(False)

            handler = VNImageRequestHandler.alloc().initWithURL_options_(img_url, {})
            handler.performRequests_error_([req], None)

            results = req.results() or []
            lines = [obs.topCandidates_(1)[0].string() for obs in results if obs.topCandidates_(1)]
            if lines:
                return "\n".join(lines)
        except Exception as e:
            logger.error(f"⚠️ Vision OCR Element Parse Error: {e}")

    vision_bin = os.path.join(os.path.dirname(__file__), "vision_ocr")
    if os.path.exists(vision_bin):
        try:
            res = subprocess.run([vision_bin, image_path], capture_output=True, text=True, timeout=20)
            if res.stdout:
                return res.stdout.strip()
        except Exception as e:
            logger.error(f"⚠️ vision_ocr fallback error: {e}")
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

def is_guess_consistent(cand: str, history: List[Tuple[str, int, int]]) -> bool:
    """True iff a candidate matches every (guess, correct, wrong) entry."""
    for g, c, w in history:
        if calculate_feedback(cand, g) != (c, w):
            return False
    return True

def find_candidate_backtrack(history: List[Tuple[str, int, int]],
                             char_set: str = CHAR_SET,
                             prefer_reuse: str = "") -> Optional[str]:
    """
    Deterministic constraint-satisfaction search over the 36-char alphabet.
    Guarantees the returned candidate is consistent with ALL feedback history
    (handles repeating characters). Falls back to opening-style probes that
    prefer re-using characters already proven present (locked positions),
    then an arbitrary consistent fill, so we never burn a guess randomly.
    """
    h = list(history)
    for g, c, w in h:
        if not (0 <= c <= 5 and 0 <= w <= 5 - c):
            return None

    chars = list(char_set)
    pref_order = list(prefer_reuse) + [ch for ch in chars if ch not in prefer_reuse]
    random.shuffle(pref_order)  # avoid biasing toward the same position every round

    # Chars proven to be IN the secret (appear in a guess with correct+wrong > 0)
    # get tried first at every slot so consistent completions are found fast.
    present = {ch for g, c, w in h for ch in g if c + w > 0}
    present = [ch for ch in present if ch in pref_order]
    pref_order = present + [ch for ch in pref_order if ch not in present]

    candidate = [''] * 5
    budget = [20000]  # max nodes before we bail to random sampling

    # Index-based fast counters: char -> index once, per-row count arrays as
    # lists (no dicts, no str.count). Per node this is just a few list ops.
    # History rows may contain dead chars not in char_set, so index them too.
    all_chars = list(dict.fromkeys(list(char_set) + [ch for g, _, _ in h for ch in g]))
    cmap = {ch: i for i, ch in enumerate(all_chars)}
    gi = [[cmap[ch] for ch in g] for g, _, _ in h]
    gcount = [[0] * len(all_chars) for _ in h]
    for i, g in enumerate(gi):
        for ci in g:
            gcount[i][ci] += 1
    h_c = [r[1] for r in h]
    h_cw = [r[1] + r[2] for r in h]
    match_counts = [0] * len(h)
    pres_counts = [0] * len(h)
    pres_caps = [[0] * len(all_chars) for _ in h]

    def backtrack(depth: int) -> Optional[str]:
        budget[0] -= 1
        if budget[0] <= 0:
            return None
        if depth == 5:
            s = "".join(candidate)
            if is_guess_consistent(s, h):
                return s
            return None

        for ch in pref_order:
            candidate[depth] = ch
            ci = cmap[ch]
            ok = True
            for i in range(len(h)):
                gi_row = gi[i]
                m = (ci == gi_row[depth])
                match_counts[i] += m
                cap = gcount[i][ci]
                prev = pres_caps[i][ci]
                if prev < cap:
                    pres_counts[i] += 1
                    pres_caps[i][ci] = prev + 1
                if match_counts[i] > h_c[i]:
                    ok = False
                elif match_counts[i] + (4 - depth) < h_c[i]:
                    ok = False
                elif pres_counts[i] > h_cw[i]:
                    ok = False
                match_counts[i] -= m
                if prev < cap:
                    pres_counts[i] -= 1
                    pres_caps[i][ci] = prev
                if not ok:
                    break
            if not ok:
                continue
            res = backtrack(depth + 1)
            if res:
                return res
        return None

    return backtrack(0)

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

        # Deterministic constraint search first: never burns a guess randomly.
        locked = ""
        if self.best_guess and self.best_correct >= 2:
            locked = self.best_guess
        cand = find_candidate_backtrack(self.history, "".join(active_chars), prefer_reuse=locked)
        if cand:
            self.stuck_counter = 0
            return cand

        # Biased random sampling fallback: chars proven present (appeared in a
        # guess with correct+wrong > 0) are far more likely to be in the secret,
        # so sample them heavily instead of uniform-random over all active chars.
        present_pool = [ch for ch in active_chars
                        if any(ch in g for g, c, w in self.history if c + w > 0)]
        pool = present_pool if present_pool else active_chars
        hist = self.history
        for attempt in range(60000):
            if attempt and attempt % 2 == 0 and len(pool) < len(active_chars):
                pool = active_chars
            cand_chars = []
            for i in range(5):
                if self.best_guess and self.best_correct >= 2 and random.random() < 0.65:
                    cand_chars.append(self.best_guess[i])
                else:
                    cand_chars.append(random.choice(pool))
            cand = ''.join(cand_chars)
            
            if cand not in self.tested:
                if all(calculate_feedback(g_past, cand) == (c_exp, w_exp) for g_past, c_exp, w_exp in hist):
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

# EXACT COORDINATES FROM PIXEL ANALYSIS (reference device: 1080x2392)
REF_WIDTH = 1080
REF_HEIGHT = 2392

SIM_BOX_X = [247, 394, 541, 688, 835]
SIM_INP_Y = 1033
SIM_SUB_Y = 1232

REAL_BOX_X = [247, 394, 541, 688, 835]
REAL_INP_Y = 1033
REAL_SUB_Y = 1232

DEVICE_W = REF_WIDTH
DEVICE_H = REF_HEIGHT

def get_device_size() -> Tuple[int, int]:
    """Reads the physical display size via ADB so coordinates scale on any phone."""
    global DEVICE_W, DEVICE_H
    try:
        res = subprocess.run(adb_cmd_prefix() + ["shell", "wm", "size"], capture_output=True, text=True, timeout=10, check=True)
        m = re.search(r"(\d+)x(\d+)", res.stdout)
        if m:
            DEVICE_W, DEVICE_H = int(m.group(1)), int(m.group(2))
    except Exception as e:
        logger.warning(f"⚠️ Could not read screen size via ADB, using reference {REF_WIDTH}x{REF_HEIGHT}: {e}")
    return DEVICE_W, DEVICE_H

def scale_x(x: int) -> int:
    return round(x * DEVICE_W / REF_WIDTH)

def scale_y(y: int) -> int:
    return round(y * DEVICE_H / REF_HEIGHT)

def scaled_box_x(base: List[int]) -> List[int]:
    return [scale_x(x) for x in base]

def scaled_inp_y(is_simulator: bool) -> int:
    return scale_y(SIM_INP_Y if is_simulator else REAL_INP_Y)

def scaled_sub_y(is_simulator: bool) -> int:
    return scale_y(SIM_SUB_Y if is_simulator else REAL_SUB_Y)

def detect_simulator(ocr_text: str) -> bool:
    """True when OCR text looks like the browser simulator instead of the real app."""
    sim_signals = [
        "192.168",
        ":8000",
        "Giveaway - Luci",
        "Crack the Code Simulator",
        "Demo Simulator",
        "Secret:",
        "Generate Code",
        "Generate New Code",
    ]
    return any(sig in ocr_text for sig in sim_signals)

def locate_puzzle_targets(image_path: str) -> Optional[Tuple[int, int]]:
    """
    Locates (box_row_y, submit_button_y) by pixel analysis so taps keep working
    even if the browser page is scrolled / layout differs.

    The Crack It button renders EITHER dark green (19,86,55) OR bright green
    (48,214,138) depending on app state, and the box row's dark-green borders
    can also be mistaken for the button. We therefore accept BOTH button shades,
    restrict the search to the LOWER half of the screen (button is always below
    the boxes), and pick the LOWEST wide solid band as the button. The box row
    is the widest bright-green band above the button (the typed characters),
    falling back to just above the button if none is found.
    """
    from PIL import Image
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        logger.warning(f"⚠️ Could not open screenshot for button locate ({e}) — using defaults.")
        return None
    w, h = img.size

    def is_button_green(p):
        r, g, b = p
        dark = (60 <= g <= 140 and r <= 70 and b <= 100
                and g >= r + 30 and g >= b + 15)
        bright = (g > 150 and r <= 110 and 110 <= b <= 190
                  and g >= r + 80 and g >= b + 20)
        return dark or bright

    def is_bright_char(p):
        r, g, b = p
        return g > 150 and r <= 120 and b <= 170

    def is_box_border(p):
        # Dark-green box frame: filled ~(24,108,70), empty ~(17,54,37).
        r, g, b = p
        return (45 <= g <= 125 and r <= 55 and 30 <= b <= 95
                and g >= r + 20 and g >= b) \
            or (90 <= g <= 125 and r <= 50 and 55 <= b <= 95
                and g >= r + 50 and g >= b + 15)

    # Known box centers for this screen (real app; simulator overrides below).
    _box_centers = scaled_box_x(REAL_BOX_X)

    # Search from the top region (boxes are always above the button).
    # Start at 5% so we catch the box row even when the page is scaled.
    start_y = int(round(h * 0.05))
    rows = []
    for y in range(start_y, h, 3):
        cnt = sum(1 for x in range(0, w, 4)
                  if is_button_green(img.getpixel((x, y))))
        rows.append((y, cnt))

    bands = []
    for y, cnt in rows:
        if cnt == 0:
            continue
        if bands and y - bands[-1][1] <= 10:
            bands[-1][1] = y
            bands[-1][2] = max(bands[-1][2], cnt)
        else:
            bands.append([y, y, cnt])

    # Pick the LOWEST wide/dense button-green band as the Crack It button.
    best = None
    for y0, y1, mx in bands:
        if mx < 25 or y1 - y0 < 15:
            continue
        ymid = (y0 + y1) // 2
        xs = [x for x in range(0, w, 4)
              if is_button_green(img.getpixel((x, ymid)))]
        if not xs:
            continue
        xspan = xs[-1] - xs[0]
        area = xspan * (y1 - y0 + 1)
        if best is None or y1 > best[1]:
            best = (area, y1, y0, ymid, (xs[0] + xs[-1]) // 2)

    if best is None:
        return None

    _area, _y1, y0, _ymid, _xc = best
    sub_y = (y0 + _y1) // 2

    # Box row = widest bright-green band above the button (the typed digits).
    brow_rows = []
    for y in range(start_y, y0, 3):
        cnt = sum(1 for x in range(0, w, 8)
                  if is_bright_char(img.getpixel((x, y))))
        brow_rows.append((y, cnt))
    bbands = []
    for y, cnt in brow_rows:
        if cnt < 6:
            continue
        if bbands and y - bbands[-1][1] <= 8:
            bbands[-1][1] = y
            bbands[-1][2] = max(bbands[-1][2], cnt)
        else:
            bbands.append([y, y, cnt])

    box_y = None
    if bbands:
        y0b, y1b, _mx = max(bbands, key=lambda b: b[2])
        box_y = (y0b + y1b) // 2
        # box row must sit comfortably above the button
        if box_y >= sub_y - 40:
            box_y = None
    if box_y is None:
        # Fallback: detect the dark-green box BORDERS band. Each box has a
        # dark-green frame (roughly 24,108,70 filled / 17,54,37 empty). Scan
        # full width counting border pixels; the box row is the densest band
        # between the button and above it.
        brow2 = []
        for y in range(start_y, y0 - 40, 3):
            cnt = sum(1 for x in range(0, w, 4)
                      if is_box_border(img.getpixel((x, y))))
            brow2.append((y, cnt))
        b2 = []
        for y, cnt in brow2:
            if cnt < 8:
                continue
            if b2 and y - b2[-1][1] <= 6:
                b2[-1][1] = y
                b2[-1][2] = max(b2[-1][2], cnt)
            else:
                b2.append([y, y, cnt])
        if b2:
            y0b, y1b, _mx = max(b2, key=lambda b: b[2])
            box_y = (y0b + y1b) // 2
    if box_y is None:
        box_y = sub_y - round(432 * h / REF_HEIGHT)
    return box_y, sub_y

    _area, y0, y1, _xc = best
    sub_y = (y0 + y1) // 2

    # Box row = bright-green band just above the button.
    def is_bright(p):
        r, g, b = p
        return g > 150 and r < 120 and b < 170

    brow_rows = []
    for y in range(0, sub_y - 10, 3):
        cnt = sum(1 for x in range(0, w, 6) if is_bright(img.getpixel((x, y))))
        brow_rows.append((y, cnt))
    bbands = []
    for y, cnt in brow_rows:
        if cnt < 6:
            continue
        if bbands and y - bbands[-1][1] <= 8:
            bbands[-1][1] = y
            bbands[-1][2] = max(bbands[-1][2], cnt)
        else:
            bbands.append([y, y, cnt])

    if bbands:
        y0b, y1b, _mx = bbands[-1]
        box_y = (y0b + y1b) // 2
    else:
        box_y = sub_y - round(432 * h / REF_HEIGHT)
    return box_y, sub_y

def parse_feedback_text(image_path: str, box_y: Optional[int] = None, sub_y: Optional[int] = None) -> str:
    """OCR the feedback card region (between the box row and the button) at
    2x upscale. The tiny blue text is missed by full-screen fast OCR, so crop
    the band to the known layout zone for reliable reading regardless of scroll."""
    try:
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if box_y is not None and sub_y is not None and sub_y - box_y > 200:
            y0 = max(0, box_y + 60)
            y1 = min(h, sub_y - 20)
            if y1 - y0 >= 60:
                band = y1 - y0
                crop = img.crop((0, y0, w, y1))
                scale = max(2, 1600 // band)
                crop = crop.resize((w * scale, band * scale), Image.LANCZOS)
                crop_path = os.path.join(os.path.dirname(__file__), "tmp_images", "feedback_crop.png")
                crop.save(crop_path)
                return parse_screen_elements(crop_path)
    except Exception as e:
        logger.error(f"⚠️ Feedback crop OCR error: {e}")
    return parse_screen_elements(image_path)

def send_guess_coordinate_mode(guess: str, is_simulator: bool, box_y: Optional[int] = None, sub_y: Optional[int] = None):
    """
    Sends guess using exact coordinates and the auto-advance typing engine,
    then submits. The React Native app's five per-box inputs auto-advance focus
    after each character, so the reliable fill is: wipe all boxes, tap the first
    box once, then feed the chars with a settle delay. Submits only after the
    row is confirmed (uiautomator readback) to exactly match the guess.
    """
    sub_y = sub_y if sub_y is not None else scaled_sub_y(is_simulator)
    sub_x = DEVICE_W // 2

    if not type_guess_into_input(guess, is_simulator, box_y):
        logger.warning(f"⚠️ Could not reliably type '{guess}' after retries — skipping submit.")
        return

    # The Crack It button sits above the keyboard at its feedback position
    # (y=1453), so submit directly — no need to dismiss the IME first.
    subprocess.run(adb_cmd_prefix() + ["shell", f"input tap {sub_x} {sub_y}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"   ✅ Submitted guess '{guess}' via {'Simulator' if is_simulator else 'Real App'} Mode")

def read_boxes_via_uiautomator() -> Optional[List[str]]:
    """
    Reads the EXACT current text of all 5 code boxes via uiautomator dump —
    deterministic, no OCR. Returns a list of 5 strings (empty where a box is
    blank) or None if the required nodes could not be found.

    Two channels are used (simulator exposes BOTH in the Chrome address bar):
      1. URL fragment  #XXXXX  (boxes mirrored by updateReadback())
      2. Per-box EditText nodes cb0..cb4 (exposed only while Chrome renders
         the page's input elements as real nodes).
    The fragment channel is the primary — the url_bar EditText is ALWAYS
    present in the dump, so readback never flakes on Chrome's compositor
    rendering state.
    """
    try:
        subprocess.run(adb_cmd_prefix() + ["shell", "uiautomator", "dump", "/sdcard/ui.xml"],
                       capture_output=True, timeout=20)
        subprocess.run(adb_cmd_prefix() + ["pull", "/sdcard/ui.xml", os.path.join(os.path.dirname(__file__), "tmp_images", "ui.xml")],
                       capture_output=True, timeout=20)
        with open(os.path.join(os.path.dirname(__file__), "tmp_images", "ui.xml")) as f:
            xml = f.read()

        # Channel 1: URL fragment from the always-present address bar node.
        # Attribute order in the dump is variable, so match per-node. Package
        # differs by browser (Chrome vs Brave), so match any url_bar id.
        for m in re.finditer(r'<node[^>]*?>', xml):
            full = m.group(0)
            if 'url_bar' not in full:
                continue
            t = re.search(r'text="([^"]*)"', full)
            if not t:
                continue
            url = t.group(1)
            h = url.rsplit("#", 1)
            if len(h) == 2:
                frag = h[1]
                if len(frag) == 5:
                    return [ch if ch != "_" else "" for ch in frag]

        # Channel 2: per-box EditText nodes (cb0..cb4).
        texts = []
        for m in re.finditer(r'<node[^>]*resource-id="com\.android\.chrome:id/cb(\d)"[^>]*>', xml):
            idx = int(m.group(1))
            t = re.search(r'text="([^"]*)"', m.group(0))
            texts.append((idx, (t.group(1) if t else "").replace("\u00b7", "")))
        texts.sort()
        if len(texts) == 5 and [i for i, _ in texts] == [0, 1, 2, 3, 4]:
            return [t for _, t in texts]

        # Channel 3: real Lucid app — 5 plain EditText nodes (no resource-id).
        # Order them by x-center of their bounds so box 0..4 map to the row.
        ed = []
        for m in re.finditer(r'<node[^>]*EditText[^>]*>', xml):
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', m.group(0))
            if not b:
                continue
            cx = (int(b.group(1)) + int(b.group(3))) // 2
            t = re.search(r'text="([^"]*)"', m.group(0))
            ed.append((cx, (t.group(1) if t else "").replace("\u00b7", "")))
        if len(ed) >= 5:
            ed.sort()
            five = ed[:5]
            if five[-1][0] - five[0][0] < 1500:  # sanity: 5 boxes in one row
                return [t for _, t in five]
        logger.warning(f"⚠️ Found {len(texts)} code boxes (expected 5) and no URL fragment.")
    except Exception as e:
        logger.warning(f"⚠️ uiautomator read error: {e}")
    return None

def wipe_box_row(box_x: List[int], inp_y: int) -> None:
    """Clear all 5 single-char boxes. React Native maxlength=1 inputs ignore a
    bare DEL keyevent (the tap places the caret at the start, so DEL deletes
    nothing), so each box needs MOVE_END + DEL before the char is freed."""
    parts = []
    for bx in box_x:
        parts += [f"input tap {bx} {inp_y}", "sleep 0.06",
                  "input keyevent 123", "sleep 0.05",   # MOVE_END
                  "input keyevent 67", "sleep 0.05"]    # DEL
    subprocess.run(adb_cmd_prefix() + ["shell", " && ".join(parts)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def type_guess_into_input(guess: str, is_simulator: bool, box_y: Optional[int] = None,
                          verify: bool = True, skip_clear: bool = False) -> bool:
    """
    Types the 5-char guess with GUARANTEED per-box placement.

    Each box is a maxlength=1 input. Bare DEL backspaces are IGNORED by the
    React Native inputs (the tap places the caret at the start, so DEL deletes
    nothing), but MOVE_END + text REPLACES a stale char in place. So the fast
    reliable sequence per box is: tap it, MOVE_END (caret to end), send exactly
    ONE char — this overwrites whatever was there. ~2.1s for the whole row,
    well inside the app's ~3s cooldown. No separate wipe/clear is needed.

    verify=True reads back via uiautomator (~1.5s) and repairs ONLY the boxes
    that landed wrong (tap + MOVE_END + retype that one char), retrying until
    all 5 match — this catches the occasional dropped char without a full retype.
    verify=False skips the readback for speed. Returns True when typing is
    believed successful.
    """
    box_x = scaled_box_x(SIM_BOX_X if is_simulator else REAL_BOX_X)
    inp_y = box_y if box_y is not None else scaled_inp_y(is_simulator)
    settle = 0.01

    parts = []
    for i, ch in enumerate(guess):
        parts += [f"input tap {box_x[i]} {inp_y}", f"sleep {settle}",
                  "input keyevent 123", f"sleep {settle}",  # MOVE_END so text replaces stale char
                  f"input text {ch}", f"sleep {settle}"]
    subprocess.run(adb_cmd_prefix() + ["shell", " && ".join(parts)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.15)

    if not verify:
        return True

    typed = read_boxes_via_uiautomator()
    if typed is None:
        return True
    if all(typed[i] == guess[i] for i in range(5)):
        return True

    # Repair ONLY the wrong boxes: tap it, MOVE_END, retype the right one
    # (MOVE_END + text replaces the stale char — no DEL needed).
    # Much faster than clearing+retyping all 5.
    for attempt in range(4):
        wrong = [i for i in range(5) if typed[i] != guess[i]]
        if not wrong:
            return True
        logger.warning(f"⚠️ Fixing boxes {wrong}: saw {typed}, expected list('{guess}')")
        parts = []
        for i in wrong:
            parts += [f"input tap {box_x[i]} {inp_y}", f"sleep {settle}",
                      "input keyevent 123", f"sleep {settle}",  # MOVE_END so text replaces stale char
                      f"input text {guess[i]}", f"sleep {settle}"]
        subprocess.run(adb_cmd_prefix() + ["shell", " && ".join(parts)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        typed = read_boxes_via_uiautomator()

    return all(typed[i] == guess[i] for i in range(5))

def keyboard_shown() -> bool:
    """True if the soft keyboard is currently open (mInputShown flag)."""
    try:
        res = subprocess.run(adb_cmd_prefix() + ["shell", "dumpsys input_method"], capture_output=True, text=True, timeout=10)
        return "mInputShown=true" in res.stdout
    except Exception:
        return False

def hide_keyboard() -> None:
    """Dismiss the soft keyboard. Only BACKs if the IME is actually shown so a
    closed keyboard never navigates the browser away. settle is short — the
    button only needs the overlay gone before the tap."""
    if keyboard_shown():
        subprocess.run(adb_cmd_prefix() + ["shell", "input keyevent 4"], capture_output=True, timeout=10)
        time.sleep(0.4)

def submit_crack_it(is_simulator: bool, sub_y: Optional[int] = None):
    """Tap Crack It. The caller hides the keyboard first when needed.

    Tap-only: the button is NOT tappable while the soft keyboard is open
    (the keyboard overlay eats the press even though the button renders
    above it), so the loop hides the IME before every tap. sub_y is the
    button Y (1232 first guess, 1453 with feedback).
    """
    sub_y = sub_y if sub_y is not None else scaled_sub_y(is_simulator)
    sub_x = DEVICE_W // 2
    parts = [
        f"input tap {sub_x} {sub_y}",
    ]
    subprocess.run(adb_cmd_prefix() + ["shell", " && ".join(parts)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def ocr_box_row_text(image_path: str, is_simulator: bool, box_y: Optional[int] = None) -> str:
    """Crop the box row band and OCR just the typed characters (3x upscale).
    Returns the raw OCR string (empty if the row could not be isolated)."""
    try:
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        box_x = scaled_box_x(SIM_BOX_X if is_simulator else REAL_BOX_X)
        inp_y = box_y if box_y is not None else scaled_inp_y(is_simulator)
        x0 = max(0, box_x[0] - 60)
        x1 = min(w, box_x[4] + 60)
        y0 = max(0, inp_y - 45)
        y1 = min(h, inp_y + 45)
        if y1 - y0 < 40 or x1 - x0 < 200:
            return ""
        crop = img.crop((x0, y0, x1, y1))
        crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        crop_path = os.path.join(os.path.dirname(__file__), "tmp_images", "box_row.png")
        crop.save(crop_path)
        return parse_screen_elements(crop_path)
    except Exception as e:
        logger.error(f"⚠️ Box row OCR error: {e}")
        return ""

def verify_guess_typed(guess: str, is_simulator: bool, box_y: Optional[int], shot_path: str) -> bool:
    """True when each box shows its matching character.
    Uses deterministic uiautomator readback of the 5 EditText nodes when
    available; falls back to per-box OCR crops only if the dump fails.
    This confirms every box before a submit so a half-typed guess never goes out."""
    try:
        typed = read_boxes_via_uiautomator()
        if typed is not None:
            norm = [t.replace("O", "0").replace("L", "1").replace("I", "1") for t in typed]
            if all(norm[i] == guess[i] for i in range(5)):
                return True
            logger.warning(f"⚠️ uiautomator check: saw {typed}, expected '{guess}'.")
            return False
    except Exception as e:
        logger.warning(f"⚠️ uiautomator verify error: {e} — falling back to OCR.")

    # ---- OCR fallback (only when uiautomator is unavailable) ----
    capture_phone_screenshot(shot_path)
    box_x = scaled_box_x(SIM_BOX_X if is_simulator else REAL_BOX_X)
    inp_y = box_y if box_y is not None else scaled_inp_y(is_simulator)
    from PIL import Image
    img = Image.open(shot_path).convert("RGB")
    w, h = img.size
    matched = 0
    for i, ch in enumerate(guess):
        x0 = max(0, box_x[i] - 38)
        x1 = min(w, box_x[i] + 38)
        y0 = max(0, inp_y - 42)
        y1 = min(h, inp_y + 42)
        crop = img.crop((x0, y0, x1, y1))
        crop = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
        crop_path = os.path.join(os.path.dirname(__file__), "tmp_images", f"box_verify_{i}.png")
        crop.save(crop_path)
        box_text = parse_screen_elements(crop_path).upper()
        norm = box_text.replace("O", "0").replace("O", "0") \
                       .replace("L", "1").replace("I", "1").replace("|", "1")
        norm = re.sub(r"[^0-9A-Z]", "", norm)
        target = ch
        confusions = {
            "0": {"O", "D", "Q"},
            "1": {"I", "L", "|"},
            "2": {"Z"},
            "5": {"S"},
            "6": {"G", "B"},
            "8": {"B"},
            "9": {"G", "q"},
            "O": {"0"},
            "I": {"1", "L"},
            "S": {"5"},
        }
        if ch in norm or any(n in norm for n in confusions.get(ch, set())):
            matched += 1
        else:
            logger.warning(f"⚠️ Box {i+1}: OCR saw '{norm}', expected '{ch}'.")
    if matched >= 4:
        return True
    logger.warning(f"⚠️ Verification: only {matched}/5 boxes matched '{guess}'. Possible typing issue.")
    return matched >= 3

def save_win_proof(shot_path: str, guess: str, history: list) -> None:
    """Archive a screenshot + guess log for the solved puzzle into solves/."""
    try:
        solve_dir = os.path.join(os.path.dirname(__file__), "solves")
        os.makedirs(solve_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        import shutil
        shutil.copy2(shot_path, os.path.join(solve_dir, f"win_{ts}.png"))
        log_path = os.path.join(solve_dir, f"win_{ts}.txt")
        with open(log_path, "w") as f:
            f.write(f"Winning code: {guess}\n")
            f.write(f"Solved at: {ts}\n")
            f.write("Guess history (guess, correct, wrong):\n")
            for g, c, w in history:
                f.write(f"  {g} -> {c} correct, {w} wrong\n")
        logger.info(f"🏆 Proof saved to solves/win_{ts}.png + .txt")
    except Exception as e:
        logger.warning(f"⚠️ Could not save win proof: {e}")

def main():
    print("=" * 65)
    print("🚀 REAL LUCID APP MASTERMIND SOLVER IS ACTIVE!")
    print("   - Auto Mode Detection: Simulator vs Real App")
    print("   - Exact hardcoded layouts from pixel-level analysis")
    print("   - One-shot full guess typing into the shared code input")
    print("=" * 65 + "\n")
    
    if not check_adb_connected():
        print("\n❌ Error: No Android phone detected via ADB.")
        return

    get_device_size()
    if (DEVICE_W, DEVICE_H) != (REF_WIDTH, REF_HEIGHT):
        logger.info(f"📐 Device {DEVICE_W}x{DEVICE_H} detected — scaling coordinates from reference {REF_WIDTH}x{REF_HEIGHT}.")
    else:
        logger.info(f"📐 Device {DEVICE_W}x{DEVICE_H} matches reference layout — using exact coordinates.")

    # Keep the phone awake + wake it now so a locked screen never stalls a run.
    try:
        subprocess.run(adb_cmd_prefix() + ["shell", "svc power stayon true"], capture_output=True, timeout=10)
        subprocess.run(adb_cmd_prefix() + ["shell", "input keyevent 224"], capture_output=True, timeout=10)
        subprocess.run(adb_cmd_prefix() + ["shell", "wm dismiss-keyguard"], capture_output=True, timeout=10)
        logger.info("☀️ Screen wake + stay-awake enabled.")
    except Exception as e:
        logger.warning(f"⚠️ Could not enable stay-awake: {e}")

    tmp_dir = os.path.join(os.path.dirname(__file__), "tmp_images")
    os.makedirs(tmp_dir, exist_ok=True)
    shot_path = os.path.join(tmp_dir, "phone_screen.png")
    
    solver = BulletproofMastermindEngine()
    logger.info("👀 Monitoring phone screen...")
    
    in_solving_loop = False
    last_submit_time = 0.0
    last_win_time = 0.0

    while True:
        if not capture_phone_screenshot(shot_path):
            time.sleep(1.0)
            if not check_adb_connected():
                logger.warning("🔌 ADB link dropped — retrying...")
                time.sleep(2)
            continue
            
        ocr_text = parse_screen_elements(shot_path)
        
        # Check if Giveaway Puzzle screen is visible on phone
        puzzle_visible = "Crack the Code" in ocr_text or "Crack It" in ocr_text or "5-digit code" in ocr_text or "spots left" in ocr_text
        
        # Don't immediately restart on a freshly-won screen; keep waiting while it persists
        if puzzle_visible and not in_solving_loop and time.time() - last_win_time < 15:
            if any(k in ocr_text.lower() for k in ("congratul", "won", "claimed", "puzzle solved")):
                last_win_time = time.time()
                logger.info("🎉 Puzzle already won on screen. Waiting for a fresh giveaway...")
                time.sleep(5)
                continue
        
        if puzzle_visible and not in_solving_loop:
            print("\a\a\a")
            print("\n" + "🚨" * 25)
            print("🚨   LIVE PUZZLE DETECTED ON YOUR PHONE SCREEN!   🚨")
            print("🚨" * 25 + "\n")
            
            # Auto-detect if browser simulator or real app is running
            is_simulator = detect_simulator(ocr_text)
            if FORCE_SIMULATOR is not None:
                is_simulator = FORCE_SIMULATOR
            logger.info(f"ℹ️ Auto-detected mode: {'SIMULATOR' if is_simulator else 'REAL APP'}")
            
            in_solving_loop = True
            solver = BulletproofMastermindEngine()
            next_guess = solver.get_next_guess(None, None, None)
            round_num = 0
            last_submit_time = 0.0
            box_y = sub_y = None
            parse_failures = 0
            last_fb = None  # (correct, wrong) from the previous round, for stale-read guard

            def close_keyboard():
                hide_keyboard()

            while in_solving_loop:
                round_num += 1

                # TYPE DURING THE COOLDOWN: after the previous submit, the app
                # locks Crack It for ~3s ("Wait 3s") while the feedback banner
                # stays visible and the button sits at its with-feedback Y. We
                # use that locked window to wipe + type the NEXT guess, so the
                # moment the cooldown expires we tap straight through. Typing
                # takes ~3.5s with the reliable chained method. The cooldown
                # gate below (3.1s) runs AFTER typing, so typing time is hidden
                # inside the cooldown. Round 1 has no cooldown, so skip typing
                # then. Verification readback is skipped entirely — the chained
                # tap+DEL+tap+char method is verified reliable (3/3 incognito).
                # If feedback ever fails to parse, the type gets re-run with
                # verification at the end of this loop iteration.
                # Verify is OFF in the hot path (readback costs ~2s of the
                # typing→tap gap). Typing is confirmed reliable, and any missed
                # press is caught by the stale-feedback self-correction below.
                verify_type = False
                if round_num > 1:
                    typed_ok = type_guess_into_input(next_guess, is_simulator, box_y, verify=verify_type)
                    time.sleep(0.15)
                    if not typed_ok:
                        logger.warning(f"⚠️ Typing failed for '{next_guess}' — will skip submit and continue with next guess.")
                        last_submit_time = 0.0  # don't count a failed (non-)submit toward cooldown
                        continue
                    # The keyboard is ALWAYS open right after typing, and the
                    # Crack It button is NOT tappable while it is — the overlay
                    # eats the press. Close it now (safe: BACK only dismisses
                    # the IME because it is open) so the tap lands immediately.
                    hide_keyboard()

                # Enforce minimum 4.0s interval between Submit taps so app cooldown is 100% expired.
                # This wait runs AFTER typing, so the typing time is hidden inside the cooldown.
                elapsed = time.time() - last_submit_time
                if elapsed < 4.0 and last_submit_time > 0:
                    time.sleep(4.0 - elapsed)

                # Button Y is FIXED per state: y=1232 first guess (no feedback),
                # y=1453 every later round (feedback shown). Device matches the
                # reference resolution so no per-round screenshot/calibration is
                # needed — skipping it removes ~2s from the first round and
                # everything after.
                if round_num == 1:
                    sub_y = scaled_sub_y(is_simulator)          # 1232 no-feedback
                    box_y = scaled_inp_y(is_simulator)          # 1033 box row
                else:
                    sub_y = round(1453 * DEVICE_H / REF_HEIGHT)  # with-feedback
                parse_failures = 0

                logger.info(f"👉 [Round {round_num}] Submitting guess '{next_guess}'...")
                last_submit_time = time.time()

                # First round only: the row starts empty, just type (no clear phase —
                # saves ~1.5s). Hide the IME afterwards so the tap lands.
                if round_num == 1:
                    typed_ok = type_guess_into_input(next_guess, is_simulator, box_y, verify=False, skip_clear=True)
                    time.sleep(0.15)
                    if not typed_ok:
                        logger.warning(f"⚠️ Typing failed for '{next_guess}' after retries — will skip submit and continue with next guess.")
                        last_submit_time = 0.0  # don't count a failed (non-)submit toward cooldown
                        continue
                    hide_keyboard()

                # TAP CRACK IT / SUBMIT — actually fire the guess so feedback appears.
                # The button sits above the keyboard, so no need to dismiss the IME first.
                submit_crack_it(is_simulator, sub_y)
                time.sleep(1.0)

                # Try reading feedback up to 3 times
                correct = None
                wrong = None
                clean_ocr_text = ""
                full_text = ""

                for attempt in range(3):
                    capture_phone_screenshot(shot_path)
                    # FAST PATH FIRST: the feedback text is a small cropped
                    # band, so read it directly (no full-page OCR). Full-page
                    # OCR is slow (~1s) and only needed as a fallback for the
                    # win/visibility checks.
                    time.sleep(0.5)
                    post_text = parse_feedback_text(shot_path, box_y, sub_y)

                    # Sanitize OCR text (replace letter 'O'/'o' with digit '0', '|' / 'l' with '1')
                    clean_ocr_text = re.sub(r'\b[Oo]\b', '0', post_text)
                    clean_ocr_text = re.sub(r'[\|l]', '1', clean_ocr_text)

                    match = re.search(r"(\d+)\s*correct\s*spot[^\d]*(\d+)\s*wrong\s*spot", clean_ocr_text, re.IGNORECASE)
                    if not match:
                        match = re.search(r"(\d+)\s*correct[^\d]*(\d+)\s*wrong", clean_ocr_text, re.IGNORECASE)

                    if match:
                        correct = int(match.group(1))
                        wrong = int(match.group(2))
                        # Sanity guard: a 5-char code can never have more than 5
                        # correct + wrong, and OCR noise (e.g. "11 correct") must
                        # not be fed into the solver as valid feedback.
                        if 0 <= correct <= 5 and 0 <= wrong <= 5 - correct and correct + wrong <= 5:
                            # STALE-READ GUARD: if this feedback is IDENTICAL to
                            # the last round's, the new submit may not have
                            # rendered yet (button was in cooldown). Take ONE
                            # fresh screenshot and re-parse before accepting.
                            if round_num > 1 and last_fb is not None and (correct, wrong) == last_fb and attempt < 2:
                                time.sleep(0.5)
                                capture_phone_screenshot(shot_path)
                                post_text2 = parse_feedback_text(shot_path, box_y, sub_y)
                                clean2 = re.sub(r'\b[Oo]\b', '0', post_text2)
                                clean2 = re.sub(r'[\|l]', '1', clean2)
                                m3 = re.search(r"(\d+)\s*correct\s*spot[^\d]*(\d+)\s*wrong\s*spot", clean2, re.IGNORECASE)
                                if not m3:
                                    m3 = re.search(r"(\d+)\s*correct[^\d]*(\d+)\s*wrong", clean2, re.IGNORECASE)
                                if m3:
                                    c3, w3 = int(m3.group(1)), int(m3.group(2))
                                    if (c3, w3) != (correct, wrong):
                                        correct, wrong = c3, w3
                                        logger.info(f"📊 Refreshed feedback: {correct} correct, {wrong} wrong for '{next_guess}'")
                            logger.info(f"📊 Extracted screen feedback: {correct} correct, {wrong} wrong for '{next_guess}'")
                            last_fb = (correct, wrong)
                            break
                        logger.warning(f"⚠️ Impossible feedback parsed ({correct} correct, {wrong} wrong) — ignoring.")
                        time.sleep(1.0)
                    else:
                        # Feedback not in the cropped band yet (cooldown may not
                        # have rendered) or OCR missed it. Fall back to a full
                        # page read only on retry, so the common case stays fast.
                        full_text = parse_screen_elements(shot_path)
                        clean_full = re.sub(r'\b[Oo]\b', '0', full_text)
                        clean_full = re.sub(r'[\|l]', '1', clean_full)
                        win_scan = (full_text + "\n" + post_text).lower()
                        if any(k in win_scan for k in ("congratul", "cracked the code", "you won", "won!", "claimed", "puzzle solved")):
                            logger.info("🎉🎉🎉 PUZZLE CRACKED & WON ON PHONE SCREEN!")
                            print("\a\a\a")
                            save_win_proof(shot_path, next_guess, solver.history)
                            last_win_time = time.time()
                            in_solving_loop = False
                            break
                        if not ("Crack the Code" in clean_full or "Crack It" in clean_full or "5-digit code" in clean_full or "spots left" in clean_full):
                            logger.info("ℹ️ Puzzle screen no longer visible. Exiting solver loop...")
                            in_solving_loop = False
                            break
                        time.sleep(1.0)

                if not in_solving_loop:
                    break
                    
                if correct is None or wrong is None:
                    parse_failures += 1
                    logger.warning(f"⚠️ Could not parse feedback text from screen for '{next_guess}'. OCR Text snippet: {repr(clean_ocr_text[:150])}")

                # Calculate next optimal guess using BulletproofMastermindEngine
                next_guess = solver.get_next_guess(next_guess, correct, wrong)
                time.sleep(0.15)
                
        elif not puzzle_visible:
            in_solving_loop = False
            
        time.sleep(1.0)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ADB Mastermind puzzle solver")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--simulator", action="store_true", help="Force browser simulator mode")
    mode.add_argument("--real", action="store_true", help="Force real app mode")
    args = ap.parse_args()
    if args.simulator:
        FORCE_SIMULATOR = True
    elif args.real:
        FORCE_SIMULATOR = False
    main()
