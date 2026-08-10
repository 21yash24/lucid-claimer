import re
import os
import logging
import ssl
import subprocess
from collections import Counter

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("OCRSolver")

_BINARY = None
def _get_binary():
    global _BINARY
    if _BINARY is None:
        _BINARY = os.path.join(os.path.dirname(__file__), "mac_vision_ocr")
    return _BINARY if os.path.exists(_BINARY) else None


class OcrSolver:
    def __init__(self):
        self.reader = None
        if _get_binary():
            logger.info("🍏 Using Native Apple Vision OCR Multi-Pass Engine (Hardware Accelerated - 0% CPU Load).")
        elif EASYOCR_AVAILABLE:
            logger.info("Initializing EasyOCR Reader...")
            self.reader = easyocr.Reader(['en'])
        elif PYTESSERACT_AVAILABLE:
            logger.info("EasyOCR not found. Falling back to PyTesseract OCR...")
        else:
            logger.warning("⚠️ No OCR library found!")

    # ──────────────────────────────────────────────────────
    # 4-PASS ENSEMBLE PREPROCESSING FILTERS
    # ──────────────────────────────────────────────────────
    def generate_ensemble_passes(self, img_path: str, tmp_dir: str) -> list:
        """
        Generates 4 complementary image preprocessed passes to overcome red scribbles:
          Pass 1: Raw un-touched image
          Pass 2: Color Separation Filter (Isolates white text pixels)
          Pass 3: HSV Red Inpainting Filter (Deletes red scribbles via local pixel synthesis)
          Pass 4: High-Contrast Adaptive Threshold Filter
        """
        if not CV2_AVAILABLE:
            return [img_path]

        img = cv2.imread(img_path)
        if img is None:
            return [img_path]

        passes = [img_path]

        try:
            # Pass 2: Color Separation (White text isolation)
            b, g, r = [c.astype(np.int16) for c in cv2.split(img)]
            red_mask = (r - g > 30) & (r - b > 30) & (g < 120) & (b < 120)
            text_mask = ((r + g + b) > 280) & (~red_mask)
            pass2 = np.zeros_like(img)
            pass2[text_mask] = [255, 255, 255]
            p2_path = os.path.join(tmp_dir, "ensemble_p2.jpg")
            cv2.imwrite(p2_path, cv2.bitwise_not(pass2))
            passes.append(p2_path)

            # Pass 3: HSV Red Inpainting
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            m1 = cv2.inRange(hsv, np.array([0, 40, 40]), np.array([15, 255, 255]))
            m2 = cv2.inRange(hsv, np.array([155, 40, 40]), np.array([180, 255, 255]))
            red_hsv = cv2.bitwise_or(m1, m2)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            red_hsv = cv2.dilate(red_hsv, kernel, iterations=2)
            inpainted = cv2.inpaint(img, red_hsv, 3, cv2.INPAINT_TELEA)
            p3_path = os.path.join(tmp_dir, "ensemble_p3.jpg")
            cv2.imwrite(p3_path, inpainted)
            passes.append(p3_path)

            # Pass 4: Adaptive Thresholding with 2x Scaling
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            adap = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)
            p4_path = os.path.join(tmp_dir, "ensemble_p4.jpg")
            cv2.imwrite(p4_path, adap)
            passes.append(p4_path)

        except Exception as e:
            logger.debug(f"Ensemble generation warning: {e}")

        return passes

    def _run_vision_ocr(self, img_path: str) -> str:
        binary = _get_binary()
        if not binary or not os.path.exists(img_path):
            return ""
        try:
            res = subprocess.run(
                [binary, img_path],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as e:
            logger.debug(f"Vision OCR error on {img_path}: {e}")
        return ""

    def _extract_candidates_from_text(self, raw_ocr: str) -> list:
        lines = [l.strip() for l in raw_ocr.splitlines() if l.strip()]
        code_fragments = []
        for line in lines:
            upper = line.upper()
            if any(noise in upper for noise in [
                "LUCID", "EVAL", "100%", "COPY", "OFF", "50K", "150K", "25K",
                "LUCIDPRO", "LUCIDFLEX", "PROCENT", "COUPON", "CART", "CHECKOUT",
                "PRO EVAL", "% OFF"
            ]):
                break
            tokens = re.findall(r'[A-Z0-9]+', upper)
            code_fragments.extend(tokens)

        if code_fragments:
            candidate = "".join(code_fragments)
            if 4 <= len(candidate) <= 25 and any(c.isalpha() for c in candidate):
                return [candidate]
        return []

    # ──────────────────────────────────────────────────────
    # CHARACTER CONSENSUS ALGORITHM
    # ──────────────────────────────────────────────────────
    def reconstruct_ensemble_consensus(self, candidate_list: list) -> list:
        """
        Combines candidates from all 4 OCR passes.
        Performs character-by-character voting and generates smart substitution candidates.
        """
        if not candidate_list:
            return []

        unique_candidates = list(dict.fromkeys(candidate_list))
        logger.info(f"📊 Ensemble OCR Raw Candidates: {unique_candidates}")

        # Find target length from most frequent candidate length
        lengths = [len(c) for c in unique_candidates]
        target_len = Counter(lengths).most_common(1)[0][0]

        valid_length_candidates = [c for c in unique_candidates if len(c) == target_len]
        if not valid_length_candidates:
            valid_length_candidates = unique_candidates

        # Position-by-position character voting
        consensus_chars = []
        for pos in range(target_len):
            pos_chars = [c[pos] for c in valid_length_candidates if pos < len(c)]
            if pos_chars:
                most_common = Counter(pos_chars).most_common(1)[0][0]
                consensus_chars.append(most_common)

        consensus_code = "".join(consensus_chars)
        logger.info(f"🏆 Ensemble Character Consensus: '{consensus_code}'")

        # Generate smart character variations (E<->F, TT<->Y7, S<->5, 0<->O, etc.)
        from parser import generate_code_variations
        final_list = []
        for base in [consensus_code] + unique_candidates:
            for v in generate_code_variations(base):
                if v not in final_list:
                    final_list.append(v)

        return final_list

    # ──────────────────────────────────────────────────────
    # Public: extract_text_from_image
    # ──────────────────────────────────────────────────────
    def extract_text_from_image(self, img_path: str, preprocessed_path: str = None) -> str:
        """
        Full 4-Pass Ensemble OCR Execution Pipeline.
        """
        tmp_dir = os.path.dirname(preprocessed_path) if preprocessed_path else os.path.dirname(img_path)
        ensemble_passes = self.generate_ensemble_passes(img_path, tmp_dir)

        pass_outputs = []
        for p in ensemble_passes:
            t = self._run_vision_ocr(p)
            if t:
                pass_outputs.append(t)

        combined = "\n---\n".join(pass_outputs)
        return combined

    # ──────────────────────────────────────────────────────
    # Public: find_lucid_codes
    # ──────────────────────────────────────────────────────
    def find_lucid_codes(self, text: str) -> list:
        if not text:
            return []

        blocks = text.split("---")
        raw_candidates = []
        for b in blocks:
            cands = self._extract_candidates_from_text(b)
            raw_candidates.extend(cands)

        final_codes = self.reconstruct_ensemble_consensus(raw_candidates)
        if final_codes:
            best_code = final_codes[0]
            logger.info(f"✅ Single Best Predicted Code: '{best_code}'")
            return [best_code]

        from parser import extract_all_giveaway_codes
        raw = extract_all_giveaway_codes(text)
        strong = [c for c in raw if any(ch.isalpha() for ch in c) and len(c) >= 4]
        return [strong[0]] if strong else (raw[:1] if raw else [])
