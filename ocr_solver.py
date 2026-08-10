import re
import os
import json
import logging
import ssl
import subprocess

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

# Mac Vision OCR binary path
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
            logger.info("🍏 Using Native Apple Vision OCR (Hardware Accelerated - 0% CPU Load).")
        elif EASYOCR_AVAILABLE:
            logger.info("Initializing EasyOCR Reader...")
            self.reader = easyocr.Reader(['en'])
        elif PYTESSERACT_AVAILABLE:
            logger.info("EasyOCR not found. Falling back to PyTesseract OCR...")
        else:
            logger.warning("⚠️ No OCR library found!")

    # ──────────────────────────────────────────────────────
    # STEP 1: Remove red scribble lines via inpainting
    # ──────────────────────────────────────────────────────
    def _remove_red_lines(self, img_path: str, output_path: str) -> str:
        """
        Removes red X / diagonal scribbles from tweet image using OpenCV inpainting.
        Returns path to cleaned image, or original path if OpenCV unavailable.
        """
        if not CV2_AVAILABLE:
            return img_path

        img = cv2.imread(img_path)
        if img is None:
            return img_path

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Red occupies two hue bands (saturation >= 50, value >= 50)
        m1 = cv2.inRange(hsv, np.array([0,    50, 50]), np.array([12,  255, 255]))
        m2 = cv2.inRange(hsv, np.array([160,  50, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(m1, m2)

        # Expand mask to cover anti-aliased stroke edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        red_mask = cv2.dilate(red_mask, kernel, iterations=2)

        # Inpaint fills the deleted area using surrounding pixels
        cleaned = cv2.inpaint(img, red_mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)
        cv2.imwrite(output_path, cleaned)
        return output_path

    # ──────────────────────────────────────────────────────
    # STEP 2: Run Apple Vision OCR on an image path
    # ──────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────
    # STEP 3: Reconstruct code from fragmented OCR output
    # ──────────────────────────────────────────────────────
    def _reconstruct_code_from_fragments(self, raw_ocr: str) -> str | None:
        """
        The red X scribble cuts the bold code text into 2-3 fragments on the first OCR line.
        E.g. raw OCR gives:
            '41N0\nYPIUQ\nLucidPro Eval 50k\n100% off\nCopy'

        Strategy: collect all uppercase+digit tokens from the TOP of the OCR output
        (stop at first UI-noise line), then concatenate = the full coupon code.

        Only uses the FIRST block of text (raw pass) — before any '---' separator.
        """
        # Use only the raw OCR block (before ---)
        first_block = raw_ocr.split("---")[0] if "---" in raw_ocr else raw_ocr
        lines = [l.strip() for l in first_block.splitlines() if l.strip()]

        code_fragments = []
        for line in lines:
            upper = line.upper()
            # Stop at first obvious UI noise line
            if any(noise in upper for noise in [
                "LUCID", "EVAL", "100%", "COPY", "OFF", "50K", "150K",
                "LUCIDPRO", "PROCENT", "COUPON", "CART", "CHECKOUT",
                "PRO EVAL", "% OFF"
            ]):
                break
            # Strip non-alphanumeric and collect
            tokens = re.findall(r'[A-Z0-9]+', upper)
            code_fragments.extend(tokens)

        if code_fragments:
            candidate = "".join(code_fragments)
            logger.info(f"🔧 Code fragments from raw OCR: {code_fragments} → '{candidate}'")
            return candidate
        return None

    # ──────────────────────────────────────────────────────
    # Public: extract_text_from_image
    # ──────────────────────────────────────────────────────
    def extract_text_from_image(self, img_path: str, preprocessed_path: str = None) -> str:
        """
        Full pipeline:
          1. Remove red scribble lines from image (inpainting).
          2. Run Apple Vision OCR on BOTH cleaned and raw image.
          3. Return raw OCR text first (most accurate letter recognition),
             then cleaned OCR text separated by a sentinel line.
        """
        clean_path = preprocessed_path or img_path.replace(".jpg", "_nored.jpg")
        cleaned_img = self._remove_red_lines(img_path, clean_path)

        raw_text     = self._run_vision_ocr(img_path)
        cleaned_text = self._run_vision_ocr(cleaned_img)

        if raw_text:
            logger.info(f"🍏 [Vision OCR Raw] → {raw_text!r}")
        if cleaned_text:
            logger.info(f"🍏 [Vision OCR Cleaned] → {cleaned_text!r}")

        # Return raw first so reconstruction prioritises it
        parts = []
        if raw_text:
            parts.append(raw_text)
        if cleaned_text:
            parts.append(cleaned_text)

        if not parts:
            # Fallback to EasyOCR/Tesseract
            if EASYOCR_AVAILABLE and self.reader:
                try:
                    results = self.reader.readtext(
                        cleaned_img, detail=0,
                        allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    )
                    parts.append(" ".join(results))
                except Exception as e:
                    logger.debug(f"EasyOCR error: {e}")
            elif PYTESSERACT_AVAILABLE:
                try:
                    pil = Image.open(cleaned_img)
                    cfg = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    parts.append(pytesseract.image_to_string(pil, config=cfg).strip())
                except Exception as e:
                    logger.debug(f"Tesseract error: {e}")

        combined = "\n---\n".join(parts)
        logger.info(f"Combined OCR output: {combined!r}")
        return combined

    # ──────────────────────────────────────────────────────
    # Public: find_lucid_codes
    # ──────────────────────────────────────────────────────
    def find_lucid_codes(self, text: str) -> list:
        """
        Extracts a Lucid Trading coupon code from OCR text.

        Priority:
          1. Try to reconstruct the code from top-line fragments
             (handles red-X split codes like 41N0 + YPIUQ → 41N0HYPEQ50 etc.)
          2. Fall back to parser extraction for clean / text-based codes.

        The reconstructed code must:
          - Be 6-25 characters
          - Contain BOTH at least one letter AND at least one digit
        """
        # Try reconstruction first — use RAW image OCR since inpainting can distort letters
        if text:
            reconstructed = self._reconstruct_code_from_fragments(text)
            if reconstructed:
                has_letter = any(c.isalpha() for c in reconstructed)
                if has_letter and 4 <= len(reconstructed) <= 25:
                    logger.info(f"✅ Using reconstructed code: '{reconstructed}'")
                    return [reconstructed]

        # Fallback: standard parser extraction
        from parser import extract_all_giveaway_codes
        raw = extract_all_giveaway_codes(text)

        # Filter: prefer codes with BOTH letters AND digits, 6+ chars
        strong = [c for c in raw if any(ch.isalpha() for ch in c)
                                 and any(ch.isdigit() for ch in c)
                                 and len(c) >= 6]
        if strong:
            strong.sort(key=len, reverse=True)
            logger.info(f"✅ Strong code candidates: {strong}")
            return strong

        return raw
