"""
AIDA ilova ikonasini yaratadi.
DNK spirali + ko'k→binafsha gradient (tema ranglariga mos).

Ishlatish:
    python packaging/make_icon.py
Natija:
    app/assets/icon.png   (1024x1024)
    app/assets/icon.icns  (macOS .app uchun)
"""

from __future__ import annotations

import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
ASSETS = os.path.join(os.path.dirname(__file__), "..", "app", "assets")
ASSETS = os.path.abspath(ASSETS)


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient(size: int, c1: str, c2: str) -> Image.Image:
    """Diagonal gradient (yuqori-chap -> past-o'ng)."""
    a = np.array(_hex(c1), dtype=float)
    b = np.array(_hex(c2), dtype=float)
    y, x = np.mgrid[0:size, 0:size]
    t = ((x + y) / (2 * size))[..., None]
    arr = (a * (1 - t) + b * t).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def draw_dna(draw: ImageDraw.ImageDraw, cx: int, top: int, bottom: int,
             amp: int, turns: float, width: int):
    """Ikki spiral ip + ular orasidagi 'zinapoyalar'."""
    n = 240
    strand1, strand2 = [], []
    for i in range(n + 1):
        f = i / n
        y = top + f * (bottom - top)
        phase = f * turns * 2 * math.pi
        strand1.append((cx + amp * math.sin(phase), y))
        strand2.append((cx + amp * math.sin(phase + math.pi), y))

    # zinapoyalar
    for i in range(0, n + 1, 12):
        x1, y1 = strand1[i]
        x2, y2 = strand2[i]
        # markazga yaqin joyda ingichka, chetda qalinroq — chuqurlik hissi
        alpha = 210
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255, alpha), width=max(6, width // 3))

    # iplar (oq, yumshoq)
    draw.line(strand1, fill=(255, 255, 255, 255), width=width, joint="curve")
    draw.line(strand2, fill=(226, 232, 240, 255), width=width, joint="curve")


def main():
    os.makedirs(ASSETS, exist_ok=True)

    base = gradient(SIZE, "#3b82f6", "#8b5cf6").convert("RGBA")

    # yumshoq yorug'lik dog'i (yuqori-chapda)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -300, 700, 500], fill=(255, 255, 255, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    base = Image.alpha_composite(base, glow)

    # DNK — 2x supersampling silliqlik uchun
    ss = 2
    layer = Image.new("RGBA", (SIZE * ss, SIZE * ss), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    draw_dna(ld, cx=SIZE * ss // 2, top=int(SIZE * ss * 0.18),
             bottom=int(SIZE * ss * 0.82), amp=int(SIZE * ss * 0.17),
             turns=2.5, width=int(SIZE * ss * 0.028))
    layer = layer.resize((SIZE, SIZE), Image.LANCZOS)
    base = Image.alpha_composite(base, layer)

    # yumaloq burchak (macOS squircle uslubiga yaqin)
    mask = rounded_mask(SIZE, radius=int(SIZE * 0.225))
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(base, (0, 0), mask)

    png_path = os.path.join(ASSETS, "icon.png")
    icon.save(png_path)
    print("PNG:", png_path)

    # .icns yaratish (iconutil orqali)
    iconset = os.path.join(ASSETS, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    specs = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for px, name in specs:
        icon.resize((px, px), Image.LANCZOS).save(
            os.path.join(iconset, f"icon_{name}.png"))

    icns_path = os.path.join(ASSETS, "icon.icns")
    try:
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)
        print("ICNS:", icns_path)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("iconutil ishlamadi (macOS emasmi?):", e)


if __name__ == "__main__":
    main()
