"""
test_pil_red_remover.py
-----------------------
Filters out red scribbles using pure PIL and runs EasyOCR/PyTesseract
to extract the exact code 41HOHYPIUQ from the user's uploaded image.
"""

from PIL import Image, ImageEnhance
import os
import easyocr

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786378589124.jpg"
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    pixels = img.load()

    # Create mask: replace red scribble pixels with dark background
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if r > 80 and g < 80 and b < 80 and (r - g) > 30:
                pixels[x, y] = (15, 15, 15)

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    enhanced = enhancer.enhance(2.0)

    out_path = "tmp_images/clean_pil_scribble.png"
    enhanced.save(out_path)
    print(f"Saved cleaned image to {out_path}")

    reader = easyocr.Reader(['en'])
    results = reader.readtext(out_path, detail=0)
    print(f"\n✨ OCR RESULT FROM CLEANED SCRIBBLE IMAGE:\n{results}")

if __name__ == "__main__":
    main()
