from pathlib import Path
from PIL import Image

# 1.
CURRENT_DIR = Path(__file__).resolve().parent
#img_path = CURRENT_DIR / "icons" / "sa.png"
img_path = CURRENT_DIR / "sap.png"
output_path = CURRENT_DIR / "output_64.png"

# 2.
Image.open(img_path).resize((64, 64), Image.Resampling.LANCZOS).save(output_path)
