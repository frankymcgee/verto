#!/usr/bin/env python3
"""Generate PWA icons for Verto from the existing Verto icon.

Run from the Frappe bench root, for example:

python apps/verto/scripts/generate_verto_pwa_icons.py
"""

from pathlib import Path
from PIL import Image, ImageOps

BENCH_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BENCH_ROOT / "apps" / "verto"

SOURCE_CANDIDATES = [
    APP_ROOT / "verto" / "public" / "images" / "verto-icon.png",
    APP_ROOT / "verto" / "public" / "verto-mobile" / "favicon.png",
]

OUTPUT_DIR = APP_ROOT / "verto" / "public" / "manifest"

SIZES = {
    "verto-pwa-192.png": 192,
    "verto-pwa-512.png": 512,
    "verto-pwa-maskable-192.png": 192,
    "verto-pwa-maskable-512.png": 512,
    "apple-touch-icon.png": 180,
}


def find_source_icon() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate

    searched = "\n".join(str(path) for path in SOURCE_CANDIDATES)
    raise FileNotFoundError(
        "Could not find a Verto source icon. Checked:\n" + searched
    )


def make_square_icon(source: Image.Image, size: int, maskable: bool = False) -> Image.Image:
    image = source.convert("RGBA")
    image.thumbnail((size, size), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (15, 23, 42, 255) if maskable else (0, 0, 0, 0))

    if maskable:
        # Maskable icons need safe padding so the icon is not cropped by Android launchers.
        padded_size = int(size * 0.74)
        padded = source.convert("RGBA")
        padded.thumbnail((padded_size, padded_size), Image.LANCZOS)
        x = (size - padded.width) // 2
        y = (size - padded.height) // 2
        canvas.alpha_composite(padded, (x, y))
        return canvas

    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def main() -> None:
    source_path = find_source_icon()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as source:
        source = ImageOps.exif_transpose(source)

        for filename, size in SIZES.items():
            maskable = "maskable" in filename
            output = make_square_icon(source, size, maskable=maskable)
            output.save(OUTPUT_DIR / filename, "PNG")

    print(f"Generated PWA icons from: {source_path}")
    print(f"Output directory: {OUTPUT_DIR}")
    for filename in SIZES:
        print(f" - {OUTPUT_DIR / filename}")


if __name__ == "__main__":
    main()
