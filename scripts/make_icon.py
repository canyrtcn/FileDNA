"""Generate a restrained amber FileDNA icon as PNG and Windows multiresolution ICO.

Deterministic oversampled Pillow drawing; no external image assets or network.
Pillow is a build-only dependency, not required by the shipped GUI.
"""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZE = 256
SCALE = 4


def make_icon() -> Image.Image:
    s = SCALE
    px = lambda n: round(n * s)
    image = Image.new("RGBA", (px(SIZE), px(SIZE)), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)

    def rect(box, radius, fill, outline=None, width=1):
        d.rounded_rectangle(tuple(px(n) for n in box), radius=px(radius),
                            fill=fill, outline=outline, width=px(width))

    # A soft grounded shadow, never a neon halo.
    shadow = Image.new("RGBA", image.size)
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((px(42), px(204), px(235), px(251)), fill=(0, 0, 0, 105))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(px(9))))
    d = ImageDraw.Draw(image)

    # Stacked documents with copper borders and gently illuminated corners.
    rect((35, 19, 174, 203), 21, "#392a1b", "#bd842e", 3)
    d.polygon([(px(136), px(20)), (px(174), px(59)), (px(136), px(59))],
              fill="#9f6b27")
    rect((67, 49, 207, 223), 21, "#201c19", "#f6b845", 4)
    d.polygon([(px(168), px(50)), (px(207), px(88)), (px(168), px(88))],
              fill="#d89328")
    d.line([(px(169), px(87)), (px(205), px(87))], fill="#ffdc8d", width=px(2))
    for top, last in [(89, 149), (106, 173), (123, 150)]:
        rect((91, top, last, top + 6), 3, "#a87830")

    # Magnifier: dark graphite lens, amber brass rim and a small glass gleam.
    cx, cy, radius = px(150), px(160), px(58)
    d.ellipse((cx-radius-px(3), cy-radius-px(3),
               cx+radius+px(3), cy+radius+px(3)),
              fill="#8c5a1f", outline="#eeb046", width=px(6))
    d.ellipse((cx-radius+px(5), cy-radius+px(5),
               cx+radius-px(5), cy+radius-px(5)),
              fill="#27201a", outline="#ffcf70", width=px(4))

    # DNA-like opposing strands and three crossbars, kept legible at 16px.
    left, right = [], []
    for k in range(55):
        t = k / 54
        y = 122 + 76 * t
        offset = 17 * math.cos(2 * math.pi * t)
        left.append((px(150 - offset), px(y)))
        right.append((px(150 + offset), px(y)))
    d.line(left, fill="#ffb530", width=px(8), joint="curve")
    d.line(right, fill="#ffe19b", width=px(7), joint="curve")
    for t in (0.22, 0.5, 0.78):
        y = 122 + 76 * t
        offset = abs(17 * math.cos(2 * math.pi * t))
        d.line([(px(150-offset), px(y)), (px(150+offset), px(y))],
               fill="#dd9c37", width=px(5))
    d.arc((px(104), px(111), px(194), px(204)), 213, 255,
          fill="#ffe5aa", width=px(3))

    # Balanced handle: rounded low-gloss black with gold edging.
    d.line([(px(193), px(204)), (px(232), px(243))],
           fill="#8d5b1e", width=px(26), joint="curve")
    d.line([(px(193), px(204)), (px(232), px(243))],
           fill="#211b17", width=px(19), joint="curve")
    d.line([(px(196), px(208)), (px(228), px(239))],
           fill="#f0ac43", width=px(3), joint="curve")

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = make_icon()
    png = ASSETS / "filedna.png"
    ico = ASSETS / "filedna.ico"
    image.save(png, optimize=True)
    image.save(ico, format="ICO", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48),
        (64, 64), (128, 128), (256, 256),
    ])
    print(f"Created {png} and {ico}")


if __name__ == "__main__":
    main()
