#!/usr/bin/env python3
"""
Generate MSS/Verto PWA icons from the existing Verto source icon.

Run from the Frappe bench root:

python apps/verto/scripts/generate_mss_pwa_icons.py
"""

from pathlib import Path
from PIL import Image, ImageOps

BENCH_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BENCH_ROOT / "verto"

SOURCE_CANDIDATES = [
    APP_ROOT / "verto" / "public" / "images" / "app-icon.png",
]

OUTPUT_DIR = APP_ROOT / "verto" / "public" / "manifest"

OUTPUTS = [
    ("mss-pwa-192.png", 192, False),
    ("mss-pwa-512.png", 512, False),
    ("mss-pwa-maskable-192.png", 192, True),
    ("mss-pwa-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, False),
]


def find_source_icon() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find a source icon. Checked:\n"
        + "\n".join(str(path) for path in SOURCE_CANDIDATES)
    )


def make_icon(source: Image.Image, size: int, maskable: bool) -> Image.Image:
    canvas_color = (23, 23, 23, 255) if maskable else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (size, size), canvas_color)

    icon = source.convert("RGBA")

    if maskable:
        # Leave safe-area padding for Android adaptive icon masks.
        max_size = int(size * 0.72)
    else:
        max_size = size

    icon.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    x = (size - icon.width) // 2
    y = (size - icon.height) // 2
    canvas.alpha_composite(icon, (x, y))

    return canvas


def main() -> None:
    source_path = find_source_icon()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)

        for filename, size, maskable in OUTPUTS:
            output = make_icon(image, size, maskable)
            output.save(OUTPUT_DIR / filename, "PNG")

    print(f"Generated MSS PWA icons from: {source_path}")
    for filename, _, _ in OUTPUTS:
        print(f" - {OUTPUT_DIR / filename}")


if __name__ == "__main__":
    main()
