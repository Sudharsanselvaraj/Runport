"""Generate terminal art from a logo image (light shape on a dark background).

Usage:
  python make_ascii_logo.py logo.png [--mode braille|solid] [--cols 60] [--aspect 2.1] [--threshold 110]

  braille  dotted look (2x4 dots per character), the style used by OpenSRE-like CLIs
  solid    half-block look (one pixel = half a character), crisp solid fill
--aspect is terminal cell height divided by cell width (about 2.0-2.3); it keeps the
logo's proportions. Every output line is padded to the same width so Rich can center it.
"""

import argparse

import numpy as np
from PIL import Image

BITS = {(0, 0): 1, (0, 1): 2, (0, 2): 4, (1, 0): 8, (1, 1): 16, (1, 2): 32, (0, 3): 64, (1, 3): 128}


def _shape(path: str) -> Image.Image:
    raw = Image.open(path)
    if raw.mode == "RGBA":
        bg = Image.new("RGB", raw.size, (0, 0, 0))
        bg.paste(raw, mask=raw.split()[3])
        mask = np.array(bg.convert("L")) > 128
    else:
        mask = np.array(raw.convert("L")) > 128
    ys, xs = np.where(mask)
    return Image.fromarray((mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1] * 255).astype("uint8"))


def make(path: str, mode: str = "braille", cols: int = 60, aspect: float = 2.1, thr: int = 110) -> list[str]:
    crop = _shape(path)
    ratio = crop.height / crop.width
    if mode == "braille":
        w = cols * 2
        h = (int(round(w * ratio * 2.0 / aspect)) + 3) // 4 * 4
        dots = np.array(crop.resize((w, h), Image.LANCZOS)) > thr
        rows = []
        for ry in range(h // 4):
            row = ""
            for cx in range(cols):
                v = sum(b for (dx, dy), b in BITS.items() if dots[ry * 4 + dy, cx * 2 + dx])
                row += chr(0x2800 + v) if v else " "
            rows.append(row)
    else:
        w = cols
        h = int(round(w * ratio * 2.0 / aspect))
        h += h % 2
        px = np.array(crop.resize((w, h), Image.LANCZOS)) > thr
        rows = []
        for ry in range(h // 2):
            row = ""
            for cx in range(w):
                top, bot = px[ry * 2, cx], px[ry * 2 + 1, cx]
                row += "█" if top and bot else "▀" if top else "▄" if bot else " "
            rows.append(row)
    width = max(len(r) for r in rows)
    return [r.ljust(width) for r in rows]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--mode", choices=["braille", "solid"], default="braille")
    p.add_argument("--cols", type=int, default=60)
    p.add_argument("--aspect", type=float, default=2.1)
    p.add_argument("--threshold", type=int, default=110)
    a = p.parse_args()
    print("\n".join(make(a.image, a.mode, a.cols, a.aspect, a.threshold)))
