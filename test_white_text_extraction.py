"""
test_white_text_extraction.py
------------------------------
Isolates pure white text (R>180, G>180, B>180) from red scribbles (high R, low G/B)
on the exact image uploaded by the user to extract 41HOHYPIUQ cleanly.
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
    
    # White text mask: R, G, B all > 150 (White/light gray text)
    # Red line mask: R > 150, but G < 100, B < 100
    white_mask = (r > 150) & (g > 150) & (b > 150)
    
    # Create clean binary image: white text = 0 (black), background = 255 (white)
    clean_img = np.ones_like(r) * 255
    clean_img[white_mask] = 0
    
    # Save preprocessed debug image
    out_path = "tmp_images/clean_white_text.png"
    cv2.imwrite(out_path, clean_img)
    print(f"Saved processed white text mask to: {out_path}")
    
    # Run EasyOCR
    reader = easyocr.Reader(['en'])
    results = reader.readtext(clean_img, detail=0)
    print(f"\n✨ EASYOCR RESULT ON CLEANED WHITE TEXT:\n{results}")

if __name__ == "__main__":
    main()
