from pathlib import Path
from PIL import Image
import sys


def image_to_ico(image_path: str):

    image_path = Path(image_path)

    # Check file exists
    if not image_path.exists():
        print(f"❌ File not found: {image_path}")
        sys.exit(1)

    # Supported formats
    supported = [".jpg", ".jpeg", ".png"]

    if image_path.suffix.lower() not in supported:
        print("❌ Supported formats: JPG, JPEG, PNG")
        sys.exit(1)

    # Output path
    ico_path = image_path.with_suffix(".ico")

    # Open image
    img = Image.open(image_path).convert("RGBA")

    # Create square canvas if image is not square
    width, height = img.size
    max_size = max(width, height)

    square_img = Image.new(
        "RGBA",
        (max_size, max_size),
        (0, 0, 0, 0)
    )

    # Center image
    x = (max_size - width) // 2
    y = (max_size - height) // 2

    square_img.paste(img, (x, y))

    # Resize master image to 1024x1024
    master = square_img.resize((1024, 1024), Image.LANCZOS)

    # Save ICO with multiple sizes
    master.save(
        ico_path,
        format="ICO",
        sizes=[
            (256, 256),
            (128, 128),
            (64, 64),
            (48, 48),
            (32, 32),
            (24, 24),
            (16, 16)
        ]
    )

    print(f"✅ ICO created: {ico_path}")

    # Verify sizes
    ico = Image.open(ico_path)

    try:
        print("✅ Embedded sizes:", ico.ico.sizes())
    except Exception:
        print("⚠️ Could not verify icon sizes")


if __name__ == "__main__":

    # Example:
    # python script.py icon.png

    if len(sys.argv) < 2:
        print("Usage:")
        print("python script.py <image_file>")
        sys.exit(1)

    image_to_ico(sys.argv[1])