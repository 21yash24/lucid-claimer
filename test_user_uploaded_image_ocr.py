"""
test_user_uploaded_image_ocr.py
--------------------------------
Runs OcrSolver on the exact image uploaded by the user:
/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786378589124.jpg
which contains the scribbled red line over 41HOHYPIUQ.
"""

import os
from ocr_solver import OcrSolver

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786378589124.jpg"
    print(f"📸 Testing OcrSolver on scribbled user screenshot: {img_path}")
    
    solver = OcrSolver()
    result = solver.extract_text_from_image(img_path)
    print(f"\n🔍 OCR RESULT EXTRACTED FROM SCRIBBLED IMAGE:\n{result!r}")

if __name__ == "__main__":
    main()
