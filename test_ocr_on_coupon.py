import os
import pytesseract
from PIL import Image, ImageOps

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786340045947.jpg"
    preprocessed_path = "/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer/tmp_images/test_clean.jpg"

    os.makedirs(os.path.dirname(preprocessed_path), exist_ok=True)

    img = Image.open(img_path).convert("RGB")
    pixels = img.load()
    width, height = img.size

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
    from PIL import ImageChops
    shifted_up = ImageChops.offset(inverted, 0, -1)
    shifted_down = ImageChops.offset(inverted, 0, 1)
    shifted_left = ImageChops.offset(inverted, -1, 0)
    shifted_right = ImageChops.offset(inverted, 1, 0)
    
    temp = ImageChops.darker(inverted, shifted_up)
    temp = ImageChops.darker(temp, shifted_down)
    temp = ImageChops.darker(temp, shifted_left)
    eroded = ImageChops.darker(temp, shifted_right)

    # 5. Resize by 3.0x using BICUBIC for clean anti-aliased larger text
    try:
        resample_mode = Image.Resampling.BICUBIC
    except AttributeError:
        resample_mode = Image.BICUBIC

    resized = eroded.resize((int(width * 3), int(height * 3)), resample_mode)
    resized.save(preprocessed_path)

    # custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    # extracted_text = pytesseract.image_to_string(resized, config=custom_config).strip()

    print(f"--- OCR RESULT ---")
    print("Skipped pytesseract (saved clean image to tmp_images/test_clean.jpg)")
    print(f"------------------")

if __name__ == "__main__":
    main()
