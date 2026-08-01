"""One-off script (not part of the app) that turns the source Navigrad logo
into a proper multi-resolution Windows .ico plus a browser favicon.

The source PNG is 2390x1792, fully opaque with no transparent margin, so a
bbox-based autocrop is a no-op -- this center-crops to the shorter dimension
instead. Run once whenever the source logo changes:

    .venv\\Scripts\\python.exe packaging\\make_icon.py
"""
from pathlib import Path

from PIL import Image

SRC = Path(r"C:\Users\Niljn\OneDrive\Desktop\Job Search App Logo\Soft Logo.png")
PACKAGING_DIR = Path(__file__).resolve().parent
ICO_OUT = PACKAGING_DIR / "icon.ico"
PREVIEW_OUT = PACKAGING_DIR / "icon_preview.png"
FAVICON_OUT = PACKAGING_DIR.parent / "public" / "favicon.ico"

ICON_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    square = img.crop((left, top, left + side, top + side))

    square.save(PREVIEW_OUT, format="PNG")
    square.save(ICO_OUT, format="ICO", sizes=ICON_SIZES)
    square.save(FAVICON_OUT, format="ICO", sizes=ICON_SIZES)

    print(f"Cropped {w}x{h} -> {side}x{side}")
    print(f"Preview: {PREVIEW_OUT}")
    print(f"Icon:    {ICO_OUT}")
    print(f"Favicon: {FAVICON_OUT}")


if __name__ == "__main__":
    main()
