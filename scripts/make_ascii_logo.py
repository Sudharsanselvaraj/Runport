"""Generate terminal art from a logo image (emblem only).

Usage:
  python scripts/make_ascii_logo.py <image> [--mode braille|solid] [--cols 28] [--aspect 2.1] [--threshold 110]

braille: dotted look (2x4 dots per character). solid: half-block look (crisp fill).
--aspect is terminal cell height / cell width (about 2.0-2.3) and keeps proportions.
Every output line is padded to the same width so Rich can center it without distortion.
"""

import argparse

import numpy as np
from PIL import Image

BITS = {(0, 0): 1, (0, 1): 2, (0, 2): 4, (1, 0): 8, (1, 1): 16, (1, 2): 32, (0, 3): 64, (1, 3): 128}


def emblem_mask(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    opaque = a[..., 3] > 200
    dark_logo = bool(opaque.any() and opaque.mean() < 0.9 and a[opaque][:, :3].mean() < 128)
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255) if dark_logo else (0, 0, 0, 255))
    bg.alpha_composite(im)
    lum = np.array(bg.convert("L"))
    if dark_logo or lum.mean() > 127:
        lum = 255 - lum
    mask = lum > 128
    cols = mask.any(axis=0)
    xs = np.where(cols)[0]
    start = end = xs[0]
    while end + 1 < len(cols) and cols[end + 1 : end + 14].any():
        end += 1  # stop at the first gap wider than 12 px (between emblem and text)
    mask = mask[:, start : end + 1]
    ys = np.where(mask.any(axis=1))[0]
    return Image.fromarray((mask[ys[0] : ys[-1] + 1] * 255).astype("uint8"))


def make(path: str, mode: str = "braille", cols: int = 28, aspect: float = 2.1, thr: int = 110) -> list[str]:
    crop = emblem_mask(path)
    ratio = crop.height / crop.width
    rows: list[str] = []
    if mode == "braille":
        w = cols * 2
        h = (int(round(w * ratio * 2.0 / aspect)) + 3) // 4 * 4
        d = np.array(crop.resize((w, h), Image.LANCZOS)) > thr
        for ry in range(h // 4):
            row = ""
            for cx in range(cols):
                v = sum(b for (dx, dy), b in BITS.items() if d[ry * 4 + dy, cx * 2 + dx])
                row += chr(0x2800 + v) if v else " "
            rows.append(row)
    else:
        w = cols
        h = int(round(w * ratio * 2.0 / aspect))
        h += h % 2
        p = np.array(crop.resize((w, h), Image.LANCZOS)) > thr
        for ry in range(h // 2):
            row = ""
            for cx in range(w):
                t, b = p[ry * 2, cx], p[ry * 2 + 1, cx]
                row += "█" if t and b else "▀" if t else "▄" if b else " "
            rows.append(row)
    width = max(len(r) for r in rows)
    return [r.ljust(width) for r in rows]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--mode", choices=["braille", "solid"], default="braille")
    ap.add_argument("--cols", type=int, default=28)
    ap.add_argument("--aspect", type=float, default=2.1)
    ap.add_argument("--threshold", type=int, default=110)
    a = ap.parse_args()
    print("\n".join(make(a.image, a.mode, a.cols, a.aspect, a.threshold)))
