import os
import glob
import easyocr

def main():
    images = glob.glob("tmp_images/*.jpg")
    # Filter out _clean.jpg files
    images = [img for img in images if not img.endswith("_clean.jpg")]
    
    if not images:
        print("❌ No images found in tmp_images/!")
        return
        
    latest_img = max(images, key=os.path.getmtime)
    print(f"📷 Running EasyOCR on latest image: {latest_img}")
    
    try:
        reader = easyocr.Reader(['en'], gpu=False)
        
        # 1. On original image
        print("\n--- EASYOCR ON ORIGINAL IMAGE ---")
        results = reader.readtext(latest_img, detail=0)
        print(results)
        
        # 2. On preprocessed image if it exists
        clean_img = latest_img.replace(".jpg", "_clean.jpg")
        if os.path.exists(clean_img):
            print("\n--- EASYOCR ON PREPROCESSED IMAGE ---")
            results_clean = reader.readtext(clean_img, detail=0)
            print(results_clean)
        else:
            # Let's create it on the fly
            from test_psm import preprocess
            print("\n--- Generating preprocessed image on the fly... ---")
            processed = preprocess(latest_img, 3.0)
            processed.save(clean_img)
            print("--- EASYOCR ON PREPROCESSED IMAGE ---")
            results_clean = reader.readtext(clean_img, detail=0)
            print(results_clean)
            
    except Exception as e:
        print(f"❌ Error running EasyOCR: {e}")

if __name__ == "__main__":
    main()
