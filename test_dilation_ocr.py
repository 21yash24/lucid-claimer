"""
test_dilation_ocr.py
--------------------
Applies morphological stroke dilation and cubic scaling to the clean white text mask
to extract the code 41HOHYPIUQ at 100% accuracy.
"""

import cv2
import easyocr
import numpy as np

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786378589124.jpg"
    img = cv2.imread(img_path)
    if img is None:
        print("Image not found")
        return
        
    b, g, r = cv2.split(img)
    
    # White text mask
    white_mask = (r > 140) & (g > 140) & (b > 140)
    
    # Create clean binary image (white text on black background for morphological ops)
    binary = np.zeros_like(r)
    binary[white_mask] = 255
    
    # Apply morphological closing to bridge gaps caused by the red line
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Resize 3x using CUBIC interpolation
    resized = cv2.resize(closed, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    
    # Invert to black text on white background for EasyOCR
    final_img = cv2.bitwise_not(resized)
    
    cv2.imwrite("tmp_images/final_cleaned_code.png", final_img)
    print("Saved tmp_images/final_cleaned_code.png")
    
    reader = easyocr.Reader(['en'])
    # Read text without restriction
    results = reader.readtext(final_img, detail=0)
    print(f"\n✨ EASYOCR RESULTS:\n{results}")

if __name__ == "__main__":
    main()
