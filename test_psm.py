import os
import glob
import pytesseract
from PIL import Image, ImageOps, ImageChops

def preprocess(img_path, scale):
    img = Image.open(img_path).convert("RGB")
    width, height = img.size
    pixels = img.load()
    
    # 1. Clear red pixels
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > 55 and g < 75 and b < 75 and (r - g) > 25 and (r - b) > 25:
                pixels[x, y] = (15, 15, 15)
                
    # 2. Convert to grayscale
    gray = img.convert("L")
    
    # 3. Apply thresholding
    thresh = gray.point(lambda p: 255 if p > 100 else 0)
    
    # 4. Invert
    inverted = ImageOps.invert(thresh)
    
    # 4b. Dilation
    shifted_up = ImageChops.offset(inverted, 0, -1)
    shifted_down = ImageChops.offset(inverted, 0, 1)
    shifted_left = ImageChops.offset(inverted, -1, 0)
    shifted_right = ImageChops.offset(inverted, 1, 0)
    
    temp = ImageChops.darker(inverted, shifted_up)
    temp = ImageChops.darker(temp, shifted_down)
    temp = ImageChops.darker(temp, shifted_left)
    eroded = ImageChops.darker(temp, shifted_right)
    
    # 5. Resize
    try:
        resample_mode = Image.Resampling.BICUBIC
    except AttributeError:
        resample_mode = Image.BICUBIC
        
    resized = eroded.resize((int(width * scale), int(height * scale)), resample_mode)
    return resized

def main():
    # Find latest image in tmp_images
    images = glob.glob("tmp_images/*.jpg")
    if not images:
        print("❌ No images found in tmp_images/ directory!")
        return
        
    # Get the latest modified image
    latest_img = max(images, key=os.path.getmtime)
    print(f"📷 Testing latest image: {latest_img}")
    
    scales = [1.0, 1.5, 2.0, 3.0]
    psms = [3, 6, 11, 12]
    
    for scale in scales:
        print(f"\n🚀 --- SCALE: {scale}x ---")
        try:
            processed = preprocess(latest_img, scale)
        except Exception as e:
            print(f"Error preprocessing at scale {scale}: {e}")
            continue
            
        for psm in psms:
            config_str = f'--oem 3 --psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            try:
                text = pytesseract.image_to_string(processed, config=config_str).strip()
                # Clean up empty lines
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                print(f"  PSM {psm:2d} -> OCR Results: {lines}")
            except Exception as e:
                print(f"  PSM {psm:2d} -> Error: {e}")

if __name__ == "__main__":
    main()
