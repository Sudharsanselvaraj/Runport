"""Generate Runport's original landing-page artwork procedurally.

Scene: a painterly sky over a meadow, crossed by a receding run of hexagonal
gates ("ports") that echo the Runport emblem. Everything is synthesised from
seeded noise, so the output is reproducible and contains no third-party art.

    uv run python scripts/generate_landing_art.py      # or plain python3

Writes WebP files to web/landing/public/assets/landing/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "assets" / "landing"


@dataclass(frozen=True)
class Palette:
    sky_top: tuple
    sky_mid: tuple
    sky_low: tuple
    cloud_lit: tuple
    cloud_shadow: tuple
    cloud_core: tuple
    haze: tuple
    ground_far: tuple
    ground_near: tuple
    grass_lit: tuple
    gate_lit: tuple
    gate_shade: tuple
    sun: tuple


DAY = Palette(
    sky_top=(46, 96, 128),
    sky_mid=(104, 158, 186),
    sky_low=(226, 196, 168),
    cloud_lit=(250, 206, 176),
    cloud_shadow=(122, 146, 178),
    cloud_core=(246, 236, 226),
    haze=(214, 196, 176),
    ground_far=(150, 146, 84),
    ground_near=(52, 54, 26),
    grass_lit=(206, 178, 96),
    gate_lit=(246, 222, 192),
    gate_shade=(112, 134, 160),
    sun=(255, 214, 168),
)
DUSK = Palette(
    sky_top=(28, 40, 86),
    sky_mid=(92, 96, 156),
    sky_low=(236, 160, 136),
    cloud_lit=(255, 174, 140),
    cloud_shadow=(82, 84, 132),
    cloud_core=(250, 214, 196),
    haze=(206, 150, 140),
    ground_far=(104, 90, 70),
    ground_near=(30, 28, 26),
    grass_lit=(212, 138, 96),
    gate_lit=(244, 190, 160),
    gate_shade=(70, 74, 118),
    sun=(255, 176, 132),
)
DAWN = Palette(
    sky_top=(40, 70, 92),
    sky_mid=(110, 150, 158),
    sky_low=(208, 214, 196),
    cloud_lit=(236, 226, 206),
    cloud_shadow=(106, 126, 136),
    cloud_core=(244, 244, 236),
    haze=(196, 204, 190),
    ground_far=(96, 124, 84),
    ground_near=(26, 40, 26),
    grass_lit=(150, 176, 104),
    gate_lit=(222, 224, 210),
    gate_shade=(90, 112, 122),
    sun=(244, 236, 206),
)


def lerp(a, b, t):
    return a + (b - a) * t


def col(c) -> np.ndarray:
    return np.array(c, dtype=np.float32) / 255.0


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise(rng, h, w, cell, stretch=(1.0, 1.0)):
    gh = max(2, int(h / (cell * stretch[0])) + 2)
    gw = max(2, int(w / (cell * stretch[1])) + 2)
    g = rng.random((gh, gw)).astype(np.float32)
    img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def fbm(rng, h, w, base, octaves=6, stretch=(1.0, 1.0), gain=0.52):
    total = np.zeros((h, w), np.float32)
    amp, norm, cell = 1.0, 0.0, base
    for _ in range(octaves):
        total += amp * value_noise(rng, h, w, cell, stretch)
        norm += amp
        amp *= gain
        cell = max(2.0, cell / 2.0)
    return total / norm


def render(width: int, height: int, pal: Palette, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    H, W = height, width
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    horizon = 0.70
    sun = (0.30, 0.60)

    # --- sky -------------------------------------------------------------
    t = np.clip(y / horizon, 0, 1)
    sky = (
        col(pal.sky_top) * (1 - smoothstep(0.0, 0.55, t))[..., None]
        + col(pal.sky_mid) * (smoothstep(0.0, 0.55, t) * (1 - smoothstep(0.55, 1.0, t)))[..., None]
        + col(pal.sky_low) * smoothstep(0.55, 1.0, t)[..., None]
    )
    sky = np.broadcast_to(sky, (H, W, 3)).copy()
    d_sun = np.sqrt(((x - sun[0]) * 1.6) ** 2 + (y - sun[1]) ** 2)
    sky += col(pal.sun) * (np.exp(-d_sun * 5.0) * 0.35)[..., None]

    # --- clouds: billowing banks rising from both sides, clearer centre -----
    n = fbm(rng, H, W, base=W / 3.2, octaves=6, stretch=(0.6, 1.0), gain=0.5)
    edge = fbm(rng, H, W, base=W / 40, octaves=3)
    side = np.abs(x - 0.5) * 2  # 0 centre -> 1 edges
    shape = (
        0.42 * smoothstep(0.25, 1.0, side) * smoothstep(0.05, 0.75, y / horizon)
        + 0.26 * smoothstep(0.55, 0.98, y / horizon)
        + 0.12 * (1 - smoothstep(0.0, 0.18, y)) * smoothstep(0.3, 1.0, side)
        - 0.22 * (1 - smoothstep(0.06, 0.30, np.abs(x - 0.5))) * (1 - smoothstep(0.75, 1.0, y / horizon))
    )
    field = n + shape + (edge - 0.5) * 0.22
    dens = smoothstep(0.55, 0.78, field)
    dens *= 1 - smoothstep(horizon - 0.05, horizon - 0.005, y)

    # volumetric lighting from a blurred density, sampled toward the sun
    soft = np.asarray(Image.fromarray((dens * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(H * 0.012)), np.float32) / 255
    sy, sx = int(0.02 * H), int(0.03 * W)
    padded = np.pad(soft, ((sy, 0), (0, sx)), mode="edge")
    toward_sun = padded[:H, sx : sx + W]  # sample up-left of each pixel... shifted
    vgrad = np.gradient(soft, axis=0)  # negative where density grows upward
    light = np.clip(0.58 + (soft - toward_sun) * 3.0 - vgrad * H * 0.010 - (soft - 0.5) * 0.30, 0, 1)
    billow = fbm(rng, H, W, base=W / 14, octaves=4)
    light = np.clip(light + (billow - 0.5) * 0.45 * soft, 0, 1) ** 0.85
    warm = np.clip(1.25 - d_sun * 1.25, 0, 1)
    lit_col = col(pal.cloud_lit) * warm[..., None] + col(pal.cloud_core) * (1 - warm)[..., None]
    cloud_col = col(pal.cloud_shadow) * (1 - light)[..., None] + lit_col * light[..., None]
    # silver lining on thin edges facing the sun
    rimc = np.clip((1 - dens) * dens * 4, 0, 1) * warm
    cloud_col += col(pal.sun) * (rimc * 0.25)[..., None]
    strokes = fbm(rng, H, W, base=W / 70, octaves=3, stretch=(0.5, 1.4))
    cloud_col *= (0.97 + strokes * 0.06)[..., None]
    alpha = dens[..., None]
    img = sky * (1 - alpha) + cloud_col * alpha

    # --- ground ----------------------------------------------------------
    g = smoothstep(horizon, 1.0, y)
    ground = col(pal.ground_far) * (1 - g)[..., None] + col(pal.ground_near) * g[..., None]
    ground = np.broadcast_to(ground, (H, W, 3)).copy()
    grass = fbm(rng, H, W, base=W / 160, octaves=4, stretch=(0.5, 1.6))
    patches = fbm(rng, H, W, base=W / 10, octaves=4, stretch=(0.3, 1.2))
    rim = np.exp(-(((y - horizon) * 22) ** 2)) * (1 - np.abs(x - sun[0]) * 0.8)
    ground *= (0.78 + grass * 0.34 + (patches - 0.5) * 0.25)[..., None]
    ground += col(pal.grass_lit) * (np.clip(rim, 0, 1) * 0.5 + np.clip(patches - 0.55, 0, 1) * 0.35 * (1 - g))[..., None]
    gmask = smoothstep(horizon - 0.002, horizon + 0.004, y)[..., None]
    img = img * (1 - gmask) + ground * gmask

    # horizon haze
    haze = np.exp(-(((y - horizon) * 16) ** 2))[..., None]
    img = img * (1 - haze * 0.32) + col(pal.haze) * haze * 0.32

    base = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))

    # painterly pass on the landscape only (gates stay crisp): mode filter at
    # half resolution clusters colours into stroke-like patches
    small = base.resize((W // 2, H // 2), Image.LANCZOS).filter(ImageFilter.ModeFilter(5))
    base = Image.blend(base, small.resize((W, H), Image.BICUBIC), 0.45)
    base = base.filter(ImageFilter.UnsharpMask(radius=3, percent=90, threshold=1))

    # --- gates: a receding run of hexagonal ports --------------------------
    # path from right foreground toward a vanishing point left of centre
    vp = (0.46 * W, horizon * H)
    gates = []
    for i in range(5):
        k = i / 4.0
        depth = 1.0 / (1.0 + i * 1.6)  # perspective scale
        gx = lerp(0.80 * W, vp[0], 1 - depth)
        gy = lerp(0.95 * H, vp[1], 1 - depth)
        r = 0.235 * H * depth
        gates.append((gx, gy, r, depth, k))

    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    for gx, gy, r, depth, _ in gates:
        # cast shadow stretches to the right (sun low on the left)
        sd.polygon([(gx - r * 0.9, gy), (gx + r * 0.9, gy), (gx + r * 3.2, gy + r * 0.10), (gx - r * 0.2, gy + r * 0.12)], fill=int(150 * depth**0.3))
    shadow = shadow.filter(ImageFilter.GaussianBlur(H * 0.006))
    dark = Image.new("RGB", (W, H), tuple(int(c * 0.35) for c in pal.ground_near))
    base = Image.composite(dark, base, shadow)

    for gx, gy, r, depth, _ in reversed(gates):
        draw_gate(over, gx, gy, r, depth, pal, rng)
    base = base.convert("RGBA")
    base.alpha_composite(over)
    base = base.convert("RGB")

    # final grade: subtle grain + vignette
    arr = np.asarray(base, dtype=np.float32) / 255.0
    grain = rng.normal(0, 0.012, (H, W, 1)).astype(np.float32)
    vig = 1 - 0.28 * smoothstep(0.55, 1.15, np.sqrt(((x - 0.5) * 1.2) ** 2 + ((y - 0.48) * 1.0) ** 2))
    arr = np.clip((arr + grain) * vig[..., None], 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))


def hexagon(cx, cy, r, squash=1.0):
    # flat top and bottom, so the gate rests on an edge
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)) * squash) for a in range(0, 360, 60)]


def draw_gate(layer: Image.Image, gx, gy, r, depth, pal: Palette, rng):
    W, H = layer.size
    ss = 2  # supersample for anti-aliasing
    pad = int(r * 1.6)
    box = (int(gx - r * 1.4), int(gy - 2 * r * 0.866 - pad * 0.3), int(gx + r * 1.4), int(gy + pad * 0.1))
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw < 4 or bh < 4:
        return
    tile = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    cx, cy = (gx - box[0]) * ss, (gy - r * 0.866 - box[1]) * ss
    R = r * ss
    thick = 0.17
    fog = 1 - depth**0.7  # atmospheric perspective toward haze
    lit = tuple(int(lerp(c, h, fog * 0.45)) for c, h in zip(pal.gate_lit, pal.haze))
    shade = tuple(int(lerp(c, h, fog * 0.4)) for c, h in zip(pal.gate_shade, pal.haze))
    deep = tuple(int(c * 0.72) for c in shade)
    ex, ey = -R * 0.16, -R * 0.03  # extrusion vector (depth away from viewer)

    outer = hexagon(cx, cy, R)
    inner = hexagon(cx, cy, R * (1 - thick))
    back_outer = [(px + ex, py + ey) for px, py in outer]
    back_inner = [(px + ex, py + ey) for px, py in inner]
    # back ring + side walls (shadowed)
    d.polygon(back_outer, fill=deep + (255,))
    for i in range(6):
        j = (i + 1) % 6
        d.polygon([outer[i], outer[j], back_outer[j], back_outer[i]], fill=shade + (255,))
    # inner tunnel walls: lit on the right side (light from left passes through)
    for i in range(6):
        j = (i + 1) % 6
        mid_x = (inner[i][0] + inner[j][0]) / 2
        wall = lit if mid_x > cx else deep
        d.polygon([inner[i], inner[j], back_inner[j], back_inner[i]], fill=wall + (255,))
    # punch the opening: back opening cleared
    d.polygon(back_inner, fill=(0, 0, 0, 0))
    # front face
    face = Image.new("L", tile.size, 0)
    fd = ImageDraw.Draw(face)
    fd.polygon(outer, fill=255)
    fd.polygon(inner, fill=0)
    # gradient: warm on the sun side, cooler away from it
    gw = np.linspace(0, 1, tile.size[0], dtype=np.float32)[None, :]
    gh = np.linspace(0, 1, tile.size[1], dtype=np.float32)[:, None]
    tmix = np.clip(gw * 0.9 + gh * 0.25, 0, 1)
    tex = rng.random((tile.size[1] // 6 + 2, tile.size[0] // 6 + 2)).astype(np.float32)
    tex = np.asarray(Image.fromarray((tex * 255).astype(np.uint8)).resize(tile.size, Image.BICUBIC), np.float32) / 255
    a, b = col(lit), col(shade)
    rgb = a * (1 - tmix[..., None] * 0.55) + b * (tmix[..., None] * 0.55)
    rgb *= (0.93 + tex * 0.12)[..., None]
    face_img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    face_img.putalpha(face)
    tile.alpha_composite(face_img)
    tile = tile.resize((bw, bh), Image.LANCZOS)
    layer.alpha_composite(tile, (box[0], box[1]))


def save(img: Image.Image, name: str, q=84):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    img.save(path, "WEBP", quality=q, method=6)
    print(f"wrote {path.relative_to(OUT.parent.parent.parent.parent)} {img.size} {path.stat().st_size // 1024} KB")


def main():
    hero = render(2560, 1600, DAY, seed=7)
    save(hero, "runport-hero.webp")
    dusk = render(1600, 1000, DUSK, seed=11)
    save(dusk, "runport-dusk.webp")
    dawn = render(1600, 1000, DAWN, seed=3)
    save(dawn, "runport-dawn.webp")
    # square crop of dusk for the proof card
    s = dusk.crop((560, 120, 1440, 1000)).resize((720, 720), Image.LANCZOS)
    save(s, "runport-proof.webp")


if __name__ == "__main__":
    main()
