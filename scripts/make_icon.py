"""Generate matching PNG and multi-resolution Windows ICO for FileDNA.

Run from project root: python scripts/make_icon.py
Build dependency: Pillow. This script is not needed at runtime.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZE = 256
SCALE = 4


def make_icon() -> Image.Image:
    sz = SIZE * SCALE
    image = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    S = lambda n: int(n * SCALE)

    def roundrect(box, radius, fill, outline=None, width=1):
        d.rounded_rectangle(tuple(S(x) for x in box), radius=S(radius),
                            fill=fill, outline=outline, width=S(width))

    # Two offset document silhouettes with a folded-corner detail.
    roundrect((37, 21, 177, 204), 20, "#264464", "#5f7892", 3)
    d.polygon([(S(139), S(21)), (S(177), S(59)), (S(139), S(59))],
              fill="#3e6587")
    roundrect((70, 51, 209, 226), 20, "#142740", "#65a6de", 4)
    d.polygon([(S(174), S(51)), (S(209), S(86)), (S(174), S(86))],
              fill="#34719e")
    for y, right in ((89, 154), (107, 175), (125, 154)):
        roundrect((93, y, right, y + 6), 3, "#5b81a5")

    # Searching for a match: a clean magnifier with two paired identity curves.
    cx, cy, r = S(151), S(160), S(58)
    d.ellipse((cx-r-1, cy-r-1, cx+r+1, cy+r+1),
              fill="#102034", outline="#b4d5eb", width=S(7))
    d.arc((S(118), S(122), S(172), S(200)), 65, 280, fill="#4b97ed", width=S(8))
    d.arc((S(136), S(122), S(190), S(200)), 245, 460, fill="#72d0cc", width=S(8))
    for y, x0, x1 in ((141, 145, 166), (159, 130, 159), (177, 144, 165)):
        d.line((S(x0), S(y), S(x1), S(y)), fill="#c9e6f6", width=S(5))
    d.line((S(195), S(203), S(233), S(242)), fill="#11263f", width=S(25))
    d.line((S(195), S(203), S(233), S(242)), fill="#a4cde9", width=S(13))
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = make_icon()
    png = ASSETS / "filedna.png"
    ico = ASSETS / "filedna.ico"
    image.save(png, optimize=True)
    image.save(ico, format="ICO",
               sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                      (64, 64), (128, 128), (256, 256)])
    print(f"Created {png} and {ico}")


if __name__ == "__main__":
    main()
