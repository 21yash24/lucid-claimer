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

    def _preprocess_pil(self, img_path: str, scale: float):
        from PIL import ImageOps, ImageChops
        img = Image.open(img_path).convert("RGB")
        width, height = img.size
        pixels = img.load()
        
        # 1. Clear red pixels (be careful not to clean white text)
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                # Red is high, Green and Blue are low, and red is clearly dominant
                if r > 55 and g < 75 and b < 75 and (r - g) > 25 and (r - b) > 25:
                    pixels[x, y] = (15, 15, 15)  # Replace with background dark gray
                    
        # 2. Convert to grayscale
        gray = img.convert("L")
        
        # 3. Apply thresholding (make text white, background black)
        thresh = gray.point(lambda p: 255 if p > 100 else 0)
        
        # 4. Invert (Tesseract prefers black text on white background)
        inverted = ImageOps.invert(thresh)
        
        # 4b. Vertical & Horizontal dilation to bridge gaps (1x3 vertical, 1x2 horizontal min-filter)
        shifted_up = ImageChops.offset(inverted, 0, -1)
        shifted_down = ImageChops.offset(inverted, 0, 1)
        shifted_left = ImageChops.offset(inverted, -1, 0)
        shifted_right = ImageChops.offset(inverted, 1, 0)
        
        temp = ImageChops.darker(inverted, shifted_up)
        temp = ImageChops.darker(temp, shifted_down)
        temp = ImageChops.darker(temp, shifted_left)
        eroded = ImageChops.darker(temp, shifted_right)
        
        # 5. Resize using BICUBIC for clean anti-aliased larger text
        try:
            resample_mode = Image.Resampling.BICUBIC
        except AttributeError:
            resample_mode = Image.BICUBIC
            
        resized = eroded.resize((int(width * scale), int(height * scale)), resample_mode)
        return resized

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
                
                # Try OCR at different scaling factors to capture both large and small coupon text perfectly!
                text_runs = []
                
                # Save the 3.0x preprocessed debug image to the debug path
                processed_3x = self._preprocess_pil(img_path, 3.0)
                if preprocessed_path:
                    try:
                        processed_3x.save(preprocessed_path)
                    except Exception:
                        pass
                
                # Run OCR on scales 1.0x (best for large text) and 3.0x (best for small text)
                for scale in [1.0, 3.0]:
                    try:
                        processed_img = self._preprocess_pil(img_path, scale)
                        if PYTESSERACT_AVAILABLE:
                            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                            run_text = pytesseract.image_to_string(processed_img, config=custom_config).strip()
                            text_runs.append(run_text)
                        elif EASYOCR_AVAILABLE and self.reader:
                            # Save temporary file for easyocr
                            temp_path = f"tmp_images/temp_scale_{scale}.jpg"
                            processed_img.save(temp_path)
                            results = self.reader.readtext(temp_path, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                            text_runs.append(" ".join(results))
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                    except Exception as run_error:
                        logger.error(f"⚠️ Scale {scale}x run failed: {run_error}")
                
                # Combine the text from all scale runs
                extracted_text = "\n".join([t for t in text_runs if t])
                
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
