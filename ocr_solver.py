import cv2
import numpy as np
import easyocr
import re
import os
import logging
import ssl

# Bypass SSL verification globally for urllib model downloads on macOS
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("OCRSolver")

class OcrSolver:
    def __init__(self):
        # Initialize EasyOCR reader (cached/downloaded automatically on first load)
        logger.info("Initializing EasyOCR Reader...")
        self.reader = easyocr.Reader(['en'])
        
    def filter_red_scribbles(self, img_path: str, output_path: str = None) -> np.ndarray:
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
        Removes red scribbles, performs OCR on the processed image, and returns all extracted text.
        """
        try:
            # Preprocess the image
            processed_img = self.filter_red_scribbles(img_path, preprocessed_path)
            
            # EasyOCR can read from numpy arrays directly. We use uppercase alphanumeric allowlist
            results = self.reader.readtext(processed_img, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            extracted_text = " ".join(results)
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
        # Look for uppercase alphanumeric strings of length 6 to 12
        potential_codes = re.findall(r'\b[A-Z0-9]{6,12}\b', text.upper())
        
        valid_codes = []
        for code in potential_codes:
            # Exclude strings that are purely numeric (like timestamps) or purely letters (like standard English words)
            if not code.isdigit() and not code.isalpha():
                valid_codes.append(code)
            # Standard custom codes like "WAWA" (pure letters) should be included if explicitly whitelisted
            elif code in ["WAWA", "LUCID"]:
                valid_codes.append(code)
                
        return list(set(valid_codes))
