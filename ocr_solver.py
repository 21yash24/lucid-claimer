try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

import re
import os
import logging
import ssl

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

# Bypass SSL verification globally for urllib model downloads on macOS
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("OCRSolver")

class OcrSolver:
    def __init__(self):
        self.reader = None
        if EASYOCR_AVAILABLE:
            logger.info("Initializing EasyOCR Reader...")
            self.reader = easyocr.Reader(['en'])
        elif PYTESSERACT_AVAILABLE:
            logger.info("EasyOCR not found. Falling back to PyTesseract OCR...")
        else:
            logger.warning("⚠️ No OCR library (easyocr or pytesseract) found! Image OCR will be disabled.")
        
    def filter_red_scribbles(self, img_path: str, output_path: str = None) -> "np.ndarray":
        """
        Loads the image, detects red color regions (scribbles), and masks them out by replacing
        them with the surrounding background color or white to expose the black text underneath.
        """
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"Could not load image from: {img_path}")
            
        # Convert to HSV color space for robust color detection
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Red has two ranges in HSV space
        lower_red_1 = np.array([0, 50, 50])
        upper_red_1 = np.array([10, 255, 255])
        lower_red_2 = np.array([170, 50, 50])
        upper_red_2 = np.array([180, 255, 255])
        
        mask_1 = cv2.inRange(hsv, lower_red_1, upper_red_1)
        mask_2 = cv2.inRange(hsv, lower_red_2, upper_red_2)
        red_mask = mask_1 | mask_2
        
        # Dilate mask slightly to capture borders/anti-aliasing of the red lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        red_mask = cv2.dilate(red_mask, kernel, iterations=1)
        
        # Replace red pixels with dark gray/black (since background is dark/black)
        result = img.copy()
        result[red_mask > 0] = [15, 15, 15]
        
        # Convert to grayscale and apply adaptive thresholding for high OCR accuracy
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        
        # Invert the grayscale image (makes background white, text black)
        gray_inverted = cv2.bitwise_not(gray)
        
        # Threshold to binary for crisp edges
        _, thresh = cv2.threshold(gray_inverted, 120, 255, cv2.THRESH_BINARY)
        
        # Apply vertical erosion to connect vertical strokes cut by horizontal red lines
        kernel_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 2))
        eroded = cv2.erode(thresh, kernel_vert, iterations=1)
        
        # Resize image for better OCR readability of small fonts
        gray_resized = cv2.resize(eroded, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        
        if output_path:
            cv2.imwrite(output_path, gray_resized)
            logger.info(f"Processed image saved to: {output_path}")
            
        return gray_resized

    def extract_text_from_image(self, img_path: str, preprocessed_path: str = None) -> str:
        """
        Removes red scribbles (if opencv is available), performs OCR on the image, and returns all extracted text.
        """
        try:
            if CV2_AVAILABLE:
                # Preprocess the image with OpenCV filters
                processed_img = self.filter_red_scribbles(img_path, preprocessed_path)
                
                # EasyOCR can read from numpy arrays directly. We use uppercase alphanumeric allowlist
                if EASYOCR_AVAILABLE and self.reader:
                    results = self.reader.readtext(processed_img, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                    extracted_text = " ".join(results)
                elif PYTESSERACT_AVAILABLE:
                    pil_img = Image.fromarray(processed_img)
                    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    extracted_text = pytesseract.image_to_string(pil_img, config=custom_config).strip()
                else:
                    logger.error("❌ No OCR library (easyocr or pytesseract) available for extraction!")
                    extracted_text = ""
            else:
                logger.warning("⚠️ OpenCV (cv2) not available. Falling back to PIL-based red scribble removal...")
                target_path = img_path
                if preprocessed_path:
                    try:
                        img = Image.open(img_path).convert("RGB")
                        pixels = img.load()
                        width, height = img.size
                        # Simple PIL-based red channel filter
                        for y in range(height):
                            for x in range(width):
                                r, g, b = pixels[x, y]
                                # If the pixel is red (high red, low green/blue)
                                if r > 100 and r - g > 30 and r - b > 30:
                                    pixels[x, y] = (15, 15, 15)  # Replace with dark background
                        img.save(preprocessed_path)
                        target_path = preprocessed_path
                        logger.info(f"🎨 PIL preprocessed image saved to: {preprocessed_path}")
                    except Exception as pe:
                        logger.error(f"⚠️ PIL preprocessing failed: {pe}. Using raw image.")
                        
                if PYTESSERACT_AVAILABLE:
                    pil_img = Image.open(target_path)
                    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    extracted_text = pytesseract.image_to_string(pil_img, config=custom_config).strip()
                elif EASYOCR_AVAILABLE and self.reader:
                    # EasyOCR can also read direct file paths
                    results = self.reader.readtext(target_path, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                    extracted_text = " ".join(results)
                else:
                    logger.error("❌ No OCR library (easyocr or pytesseract) available for raw extraction!")
                    extracted_text = ""
                
            logger.info(f"Raw OCR Output: {extracted_text}")
            return extracted_text
        except Exception as e:
            logger.error(f"Error during OCR extraction: {e}")
            return ""

    def find_lucid_codes(self, text: str) -> list:
        """
        Uses regex to search for possible Lucid Trading claim codes (alphanumeric, 6-12 chars, usually caps).
        Typically matches words that have both letters and numbers, excluding standard words.
        """
        # Remove URLs (like http://... or https://... or t.co/...) to prevent matching letters inside links
        clean_text = re.sub(r'https?://\S+|t\.co/\S+', '', text, flags=re.IGNORECASE)
        
        # Look for uppercase alphanumeric strings of length 6 to 12
        potential_codes = re.findall(r'\b[A-Z0-9]{6,12}\b', clean_text.upper())
        
        valid_codes = []
        for code in potential_codes:
            # Exclude strings that are purely numeric (like timestamps) or purely letters (like standard English words)
            if not code.isdigit() and not code.isalpha():
                valid_codes.append(code)
            # Standard custom codes like "WAWA" (pure letters) should be included if explicitly whitelisted
            elif code in ["WAWA", "LUCID"]:
                valid_codes.append(code)
                
        return list(set(valid_codes))
