from PIL import Image

def main():
    img_path = "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786340045947.jpg"
    img = Image.open(img_path).convert("RGB")
    width, height = img.size
    
    # Let us sample colors of pixels that have high red content
    red_pixels = []
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            # If it is strongly red
            if r > 100 and g < 100 and b < 100:
                red_pixels.append((x, y, r, g, b))
                
    print(f"Total strong red pixels: {len(red_pixels)}")
    if red_pixels:
        print("Sample red pixel values:")
        for p in red_pixels[:30]:
            print(f"Pos: ({p[0]}, {p[1]}), RGB: ({p[2]}, {p[3]}, {p[4]})")

if __name__ == "__main__":
    main()
