import re
import os
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
    # STEP 1: White-Only Text Extraction Filter
    # ──────────────────────────────────────────────────────
    def extract_white_text_image(self, img_path: str, output_path: str) -> str:
        """
        Extracts only bright white text pixels (R>160, G>160, B>160).
        Since coupon codes on card drops are bold bright white text, this filter
        completely strips out red/colored scribbles and dark background graphics,
        leaving crisp, unbroken black text on a clean white canvas for OCR.
        """
        if not CV2_AVAILABLE:
            return img_path

        img = cv2.imread(img_path)
        if img is None:
            return img_path

        b, g, r = cv2.split(img)
        white_mask = (r > 160) & (g > 160) & (b > 160)

        # Create crisp binary image: white text on black background
        result = np.zeros_like(img)
        result[white_mask] = [255, 255, 255]

        # Invert to black text on white background (optimal for Vision framework)
        inverted = cv2.bitwise_not(result)
        cv2.imwrite(output_path, inverted)
        return output_path

    # ──────────────────────────────────────────────────────
    # STEP 2: Run Apple Vision OCR
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
    # STEP 3: Reconstruct code from OCR passes
    # ──────────────────────────────────────────────────────
    def _reconstruct_code_from_fragments(self, raw_ocr: str) -> str | None:
        """
        Collects code tokens from top of OCR lines before UI noise (Lucid/100%/Copy/Eval).
        """
        lines = [l.strip() for l in raw_ocr.splitlines() if l.strip()]

        code_fragments = []
        for line in lines:
            upper = line.upper()
            if any(noise in upper for noise in [
                "LUCID", "EVAL", "100%", "COPY", "OFF", "50K", "150K",
                "LUCIDPRO", "PROCENT", "COUPON", "CART", "CHECKOUT",
                "PRO EVAL", "% OFF"
            ]):
                break
            tokens = re.findall(r'[A-Z0-9]+', upper)
            code_fragments.extend(tokens)

        if code_fragments:
            candidate = "".join(code_fragments)
            logger.info(f"🔧 Extracted code candidate: {code_fragments} → '{candidate}'")
            return candidate
        return None

    # ──────────────────────────────────────────────────────
    # Public: extract_text_from_image
    # ──────────────────────────────────────────────────────
    def extract_text_from_image(self, img_path: str, preprocessed_path: str = None) -> str:
        """
        Full OCR Pipeline:
          1. Apply White-Only Text Filter (strips all red scribbles instantly).
          2. Run Apple Vision OCR on white-only filter image.
          3. Also run raw pass as backup.
        """
        clean_path = preprocessed_path or img_path.replace(".jpg", "_whiteonly.jpg")
        cleaned_img = self.extract_white_text_image(img_path, clean_path)

        white_text = self._run_vision_ocr(cleaned_img)
        raw_text   = self._run_vision_ocr(img_path)

        if white_text:
            logger.info(f"🍏 [Vision OCR White-Filter] → {white_text!r}")
        if raw_text:
            logger.info(f"🍏 [Vision OCR Raw] → {raw_text!r}")

        parts = []
        if white_text:
            parts.append(white_text)
        if raw_text:
            parts.append(raw_text)

        combined = "\n---\n".join(parts)
        logger.info(f"Combined OCR output: {combined!r}")
        return combined

    # ──────────────────────────────────────────────────────
    # Public: find_lucid_codes
    # ──────────────────────────────────────────────────────
    def find_lucid_codes(self, text: str) -> list:
        """
        Extracts valid coupon code from OCR output.
        Prioritizes the White-Filter OCR pass first.
        """
        if text:
            first_block = text.split("---")[0] if "---" in text else text
            reconstructed = self._reconstruct_code_from_fragments(first_block)
            if reconstructed:
                has_letter = any(c.isalpha() for c in reconstructed)
                if has_letter and 4 <= len(reconstructed) <= 25:
                    logger.info(f"✅ Extracted code: '{reconstructed}'")
                    return [reconstructed]

        from parser import extract_all_giveaway_codes
        raw = extract_all_giveaway_codes(text)
        strong = [c for c in raw if any(ch.isalpha() for ch in c) and len(c) >= 4]
        if strong:
            strong.sort(key=len, reverse=True)
            logger.info(f"✅ Fallback code candidate: {strong[0]}")
            return [strong[0]]

        return raw
