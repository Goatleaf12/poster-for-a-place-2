#!/usr/bin/env python3
"""VELORA — a travel poster for a place that isn't there.
An island where the aurora touches the sea.
Procedurally generated with PIL + numpy. Writes /output/entry.png.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SEED = 20261121
rng = random.Random(SEED)
np.random.seed(SEED)

W, H = 832, 1024
HORIZON = int(H * 0.64)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky_gradient(w, h):
    top = np.array([8, 10, 38], dtype=np.float64)       # deep indigo
    mid = np.array([13, 32, 66], dtype=np.float64)      # night blue
    low = np.array([10, 66, 84], dtype=np.float64)      # deep teal
    arr = np.zeros((h, w, 3), dtype=np.float64)
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.55:
            c = top + (mid - top) * (t / 0.55)
        else:
            c = mid + (low - mid) * ((t - 0.55) / 0.45)
        arr[y, :, :] = c
    return arr


def add_stars(arr):
    h, w, _ = arr.shape
    for _ in range(650):
        x = rng.uniform(0, w - 1)
        y = rng.uniform(0, HORIZON * 0.92)
        fade = 1.0 - (y / HORIZON) * 0.55
        b = rng.uniform(30, 165) * fade
        r = rng.choice([0, 0, 0, 1])
        xi, yi = int(x), int(y)
        arr[yi, xi] += b * np.array([0.9, 0.95, 1.0])
        if r == 1:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = xi + dx, yi + dy
                if 0 <= xx < w and 0 <= yy < h:
                    arr[yy, xx] += b * 0.35 * np.array([0.9, 0.95, 1.0])
    return arr


def aurora_layer(w, h):
    """Additive aurora ribbons, returned as float array."""
    layer = np.zeros((h, w, 3), dtype=np.float64)
    xs = np.arange(w, dtype=np.float64)
    ribbons = [
        # (base_y, amp, wavelength, phase, thickness, strength)
        (0.16, 46, 0.0035, 0.4, 120, 0.95),
        (0.24, 60, 0.0028, 2.1, 90, 0.75),
        (0.10, 34, 0.0045, 4.0, 70, 0.55),
    ]
    green = np.array([46, 230, 150], dtype=np.float64)
    teal = np.array([30, 190, 200], dtype=np.float64)
    violet = np.array([150, 90, 230], dtype=np.float64)
    for base_f, amp, wl, phase, thick, strength in ribbons:
        base = base_f * h
        # diagonal sweep: ribbon rises toward the right
        centre = base + amp * np.sin(xs * wl * 2 * math.pi / 10.0 + phase) \
            - (xs / w) * h * 0.10
        for y in range(h):
            d = (y - centre) / thick
            fall = np.exp(-(d ** 2))
            if fall.max() < 0.004:
                continue
            # colour shifts green at lower edge -> violet at upper edge
            tt = np.clip(0.5 - d * 0.5, 0.0, 1.0)
            col = np.zeros((w, 3))
            for i in range(3):
                col[:, i] = np.where(
                    tt < 0.5,
                    green[i] + (teal[i] - green[i]) * (tt / 0.5),
                    teal[i] + (violet[i] - teal[i]) * ((tt - 0.5) / 0.5),
                )
            # vertical ray streaks
            rays = 0.75 + 0.25 * np.sin(xs * 0.11 + phase * 3.0) * np.sin(xs * 0.031 + 1.0)
            layer[y] += col * (fall * strength * 0.5 * rays)[:, None]
    return layer


def radial_glow(size, colour, peak):
    g = Image.new("L", (size, size), 0)
    gd = ImageDraw.Draw(g)
    steps = 40
    for i in range(steps, 0, -1):
        r = size / 2 * i / steps
        v = int(peak * (1 - i / steps) ** 2)
        gd.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=v)
    g = g.filter(ImageFilter.GaussianBlur(size / 8))
    glow = Image.new("RGB", (size, size), colour)
    return glow, g


def main():
    arr = sky_gradient(W, HORIZON + 2)
    # extend to full height for now; sea drawn later
    full = np.zeros((H, W, 3), dtype=np.float64)
    full[:HORIZON + 2] = arr
    full = add_stars(full)

    aur = aurora_layer(W, H)
    full = full + aur
    img = Image.fromarray(np.clip(full, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    # ---- crescent moon (left sky, clear of the lettering) ----
    mx, my, mr = int(W * 0.07), int(H * 0.30), 24
    moon_col = (238, 240, 220)
    glow, mask = radial_glow(180, (200, 205, 190), 60)
    img.paste(glow, (mx - 90, my - 90), mask)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=moon_col + (255,))
    # bite out of the circle with sky-ish dark disc
    draw.ellipse([mx - mr + 22, my - mr - 8, mx + mr + 22, my + mr - 8],
                 fill=(16, 22, 52, 255))
    # re-add a few stars over the bite
    for _ in range(10):
        x = rng.uniform(mx + 2, mx + mr + 14)
        y = rng.uniform(my - mr, my + mr)
        draw.point((x, y), fill=(200, 210, 235, 200))

    # ---- sea ----
    sea_top = np.array([9, 52, 68], dtype=np.float64)
    sea_bot = np.array([4, 16, 30], dtype=np.float64)
    sea = np.zeros((H - HORIZON, W, 3), dtype=np.float64)
    for i in range(H - HORIZON):
        t = i / max(1, H - HORIZON - 1)
        sea[i, :, :] = sea_top + (sea_bot - sea_top) * t
    # aurora reflection: flipped, squashed aurora colours shimmering on water
    refl_src = aur[:HORIZON][::-1]
    band = refl_src[int(HORIZON * 0.55):]
    band_img = Image.fromarray(np.clip(band, 0, 255).astype(np.uint8), "RGB")
    band_img = band_img.resize((W, H - HORIZON))
    # horizontal smear -> reads as water, kills any grid pattern
    band_img = band_img.resize((W // 5, H - HORIZON)).resize((W, H - HORIZON), Image.BILINEAR)
    band_arr = np.asarray(band_img).astype(np.float64)
    rows = np.arange(H - HORIZON, dtype=np.float64)
    rowmod = (0.82 + 0.18 * np.sin(rows * 0.55) * np.sin(rows * 0.043 + 2.0))[:, None, None]
    sea += band_arr * 0.30 * rowmod
    sea_img = Image.fromarray(np.clip(sea, 0, 255).astype(np.uint8), "RGB")
    img.paste(sea_img, (0, HORIZON))
    draw = ImageDraw.Draw(img, "RGBA")
    # horizon line glow
    draw.line([(0, HORIZON), (W, HORIZON)], fill=(120, 220, 205, 70), width=2)

    # ---- distant islets on the horizon (right side) ----
    for (x0, x1, hh) in [(0.56, 0.70, 13), (0.74, 0.86, 9), (0.90, 0.99, 15)]:
        xa, xb = int(W * x0), int(W * x1)
        pts = [(xa, HORIZON + 2)]
        for x in range(xa, xb, 8):
            t = (x - xa) / max(1, xb - xa)
            pts.append((x, HORIZON + 2 - hh * math.sin(math.pi * t) - rng.uniform(0, 2)))
        pts.append((xb, HORIZON + 2))
        draw.polygon(pts, fill=(5, 14, 26, 255))

    # ---- rocky cliff (lower left) ----
    cliff = [(0, H), (0, int(H * 0.83)), (55, int(H * 0.775)), (125, int(H * 0.74)),
             (180, int(H * 0.75)), (215, int(H * 0.80)), (232, int(H * 0.88)),
             (238, H)]
    draw.polygon(cliff, fill=(6, 10, 18, 255))
    # rock highlights
    for _ in range(46):
        x = rng.uniform(6, 225)
        y = rng.uniform(H * 0.76, H * 0.97)
        if x < 250 - (y - H * 0.75) * 0.9:
            draw.point((x, y), fill=(52, 66, 84, 160))
    # foam strokes along the cliff's water edge
    for i in range(26):
        t = i / 26
        x = 224 + t * 14 + rng.uniform(-3, 3)
        y = H * 0.86 + t * (H * 0.135)
        draw.line([(x, y), (x + rng.uniform(6, 14), y)], fill=(170, 220, 215, rng.randint(40, 90)), width=2)

    # ---- lighthouse (the one landmark) ----
    lx = 118           # base centre x
    base_y = int(H * 0.748)
    top_y = int(H * 0.545)
    bw, tw = 30, 19    # half-widths base/top
    # warm glow behind lamp first
    glow, mask = radial_glow(240, (255, 176, 92), 130)
    img.paste(glow, (lx - 120, top_y - 128), mask)
    draw = ImageDraw.Draw(img, "RGBA")
    # light beam toward the aurora (upper right), translucent cone
    beam = [(lx + 8, top_y + 6), (int(W * 0.86), int(H * 0.235)),
            (int(W * 0.90), int(H * 0.315))]
    beam_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam_img)
    bd.polygon(beam, fill=(255, 205, 120, 52))
    beam_img = beam_img.filter(ImageFilter.GaussianBlur(10))
    img.paste(Image.alpha_composite(img.convert("RGBA"), beam_img).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    # tower: white with two dark bands
    draw.polygon([(lx - bw, base_y), (lx - tw, top_y + 26), (lx + tw, top_y + 26),
                  (lx + bw, base_y)], fill=(232, 230, 220, 255))
    for fy in (0.36, 0.66):
        y0 = base_y - (base_y - top_y - 26) * fy
        hw = bw + (tw - bw) * fy
        draw.polygon([(lx - hw, y0), (lx + hw, y0), (lx + hw * 0.97, y0 - 20),
                      (lx - hw * 0.97, y0 - 20)], fill=(38, 44, 66, 255))
    # gallery + lamp room
    draw.rectangle([lx - tw - 7, top_y + 18, lx + tw + 7, top_y + 28], fill=(24, 26, 40, 255))
    draw.rectangle([lx - 11, top_y - 6, lx + 11, top_y + 18], fill=(255, 190, 96, 255))
    draw.polygon([(lx - 16, top_y - 6), (lx + 16, top_y - 6), (lx, top_y - 26)],
                 fill=(20, 22, 36, 255))
    # door + window
    draw.rectangle([lx - 5, base_y - 26, lx + 5, base_y], fill=(24, 26, 40, 255))
    draw.rectangle([lx - 3, int(H * 0.63), lx + 3, int(H * 0.63) + 9], fill=(255, 196, 110, 255))

    # lamp reflection on the sea: shimmering warm column
    refl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(refl)
    for i, y in enumerate(range(HORIZON + 8, H - 6, 5)):
        t = (y - HORIZON) / (H - HORIZON)
        wdt = 3 + t * 15 + rng.uniform(0, 5)
        cx = lx + 128 + math.sin(y * 0.05) * 4
        a = int(85 * (1 - t) + 8)
        rd.line([(cx - wdt, y), (cx + wdt, y)], fill=(255, 180, 96, a), width=2)
    refl = refl.filter(ImageFilter.GaussianBlur(3.0))
    img.paste(Image.alpha_composite(img.convert("RGBA"), refl).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    # ---- typography: VELORA, set into the top of the scene ----
    word = "VELORA"
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
    size = 118
    font = ImageFont.truetype(font_path, size)
    spacing = 26
    widths = []
    for ch in word:
        bb = draw.textbbox((0, 0), ch, font=font)
        widths.append(bb[2] - bb[0])
    total = sum(widths) + spacing * (len(word) - 1)
    x = (W - total) / 2
    ty = int(H * 0.055)
    ivory = (246, 238, 216)
    # soft warm glow behind the letters
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gx = x
    for ch, wd in zip(word, widths):
        gd.text((gx, ty), ch, font=font, fill=(255, 214, 150, 150))
        gx += wd + spacing
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(9))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow_layer).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    xx = x
    for ch, wd in zip(word, widths):
        draw.text((xx + 2, ty + 3), ch, font=font, fill=(10, 14, 30, 160))
        draw.text((xx, ty), ch, font=font, fill=ivory + (255,))
        xx += wd + spacing

    # ---- vignette + grain (rich colour count, print texture) ----
    arrf = np.asarray(img).astype(np.float64)
    yy, xx2 = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx2 - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2)
    vig = np.clip(1.0 - 0.26 * np.clip(dist - 0.55, 0, None) ** 2, 0.72, 1.0)
    arrf *= vig[:, :, None]
    noise = np.random.normal(0, 2.7, (H, W, 1))
    arrf += noise
    img = Image.fromarray(np.clip(arrf, 0, 255).astype(np.uint8), "RGB")

    out_dir = "/output" if os.path.isdir("/output") else "."
    out = os.path.join(out_dir, "entry.png")
    img.save(out, optimize=True)
    sz = os.path.getsize(out)
    if sz > 1_048_576:  # safety: gentle quantise-free fallback, slight resize
        img = img.resize((768, 960), Image.LANCZOS)
        img.save(out, optimize=True)
        sz = os.path.getsize(out)
    print(f"wrote {out} size={sz} dims={img.size}")


if __name__ == "__main__":
    main()
