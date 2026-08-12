import easyocr

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786340045947.jpg"
    clean_path = "/Users/yashjha/.gemini/antigravity/scratch/lucid_claimer/tmp_images/test_clean.jpg"

    reader = easyocr.Reader(['en'], gpu=False)
    
    print("--- EASYOCR ON ORIGINAL IMAGE ---")
    results_orig = reader.readtext(img_path, detail=0)
    print(results_orig)
    
    print("--- EASYOCR ON PREPROCESSED IMAGE ---")
    results_clean = reader.readtext(clean_path, detail=0)
    print(results_clean)

if __name__ == "__main__":
    main()
