"""Compose Figure 3 v2: the path-traced render with the ORIGINAL callouts of compose_apparatus.py.

Identical canvas (1560 x 1190 units), render placement (60, 130, scale 0.8 of 1800 px),
callout labels / positions / wording / colours, leader lines and footer. Anchors come from
render_fig3_v2.py's projection of the original anchor points. The only compositing change
is that the shadow-catcher shadow is tinted warm umber instead of neutral grey.
Exported at 2x (3120 x 2380 px) plus a PDF with vector text.

  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python viz/hero/final/compose_fig3_v2.py \
      [render.png] [out_stem]
"""
from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path

for _p in ("/opt/homebrew/lib/libcairo.2.dylib", "/usr/local/lib/libcairo.2.dylib"):
    try:
        ctypes.CDLL(_p, mode=ctypes.RTLD_GLOBAL)
        break
    except OSError:
        continue

import cairosvg  # noqa: E402
import drawsvg as draw  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = HERE / "_work"
sys.path.insert(0, str(ROOT / "config"))
from brand import COLORS as C, FONT_CSS, role  # noqa: E402

M = json.loads((ROOT / "analysis" / "aero" / "metrics.json").read_text())["inputs"]
SPAN = (M["wing_area_m2"] * 4) ** 0.5

W, H = 1560, 1190
OX, OY, DRAWN_W = 60, 130, 1800 * 0.80
SCALE = 2
SHADOW_RGB = (74, 60, 46)            # warm umber, reads as a soft shadow on parchment
SHADOW_GAIN = 0.85


def text(g, s, x, y, size=16, fill=C["ink"], anchor="middle", weight="normal"):
    g.append(draw.Text(s, size, x, y, fill=fill, text_anchor=anchor,
                       font_family=FONT_CSS, font_weight=weight))


def callout(g, A, F, lx, ly, name, term, gloss, color, side):
    ax, ay = OX + A[name][0] * F, OY + A[name][1] * F
    anchor = {"left": "end", "right": "start", "top": "middle"}[side]
    sx, sy = (lx, ly + (30 if side == "top" else 26))
    g.append(draw.Line(sx, sy, ax, ay, stroke=color, stroke_width=1.4, stroke_opacity=0.9))
    g.append(draw.Circle(ax, ay, 5, fill=color, stroke="white", stroke_width=1.6))
    text(g, term, lx, ly, size=19, fill=color, anchor=anchor, weight="bold")
    text(g, gloss, lx, ly + 21, size=14, fill=C["slate"], anchor=anchor)


def prep_render(path, flat):
    """16-bit RGBA -> 8-bit; tint the shadow-catcher pixels (black, partial alpha) warm."""
    a = np.asarray(Image.open(path)).astype(np.float32)
    if a.max() > 255:
        a = a / 257.0
    rgb, al = a[..., :3], a[..., 3:4] / 255.0
    lum = rgb.mean(-1, keepdims=True) / 255.0
    w = np.clip(1 - lum / 0.06, 0, 1) * np.clip((0.995 - al) / 0.05, 0, 1)
    rgb = rgb * (1 - w) + np.array(SHADOW_RGB, np.float32) * w
    al = al * (1 - w * (1 - SHADOW_GAIN))
    h, wd = a.shape[:2]
    m = 0.06
    fx = np.clip(np.minimum(np.arange(wd), wd - 1 - np.arange(wd)) / (m * wd), 0, 1)
    fy = np.clip(np.minimum(np.arange(h), h - 1 - np.arange(h)) / (m * h), 0, 1)
    fade = np.outer(fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx))[..., None]
    al = al * (1 - w * (1 - fade))                   # fade only the shadow toward the frame
    out = np.concatenate([rgb, al * 255.0], -1).round().clip(0, 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(flat, optimize=True)
    return wd, h


def main(render=WORK / "fig3_v2_render.png", stem=HERE / "fig_apparatus_v2"):
    A = json.loads((WORK / "fig3_v2_points.json").read_text())
    pw, ph = A.pop("_size")
    flat = WORK / "_flat.png"
    rw, rh = prep_render(render, flat)
    F = DRAWN_W / pw                                 # anchors are in full-res pixels

    d = draw.Drawing(W, H, origin=(0, 0))
    d.append(draw.Rectangle(0, 0, W, H, fill=C["parchment"]))
    d.append(draw.Image(OX, OY, DRAWN_W, DRAWN_W * rh / rw, path=str(flat), embed=True))

    g = draw.Group()
    callout(g, A, F, 720, 150, "tail", "No tail",
            "as William of Malmesbury records", role("danger"), "top")
    callout(g, A, F, 360, 300, "batten", "Wooden frame and battens",
            "bent to camber", role("structure"), "left")
    callout(g, A, F, 360, 885, "head", "Pilot, prone",
            "below the wing", role("pilot"), "left")
    callout(g, A, F, 1205, 430, "tipR", "Cloth membrane wing",
            f"{M['wing_area_m2']:.0f} m\u00b2, {SPAN:.1f} m span, aspect ratio 4",
            role("membrane"), "right")
    callout(g, A, F, 1205, 650, "hand", "Wing fixed to the hands",
            "leading spar", role("pilot"), "right")
    callout(g, A, F, 1205, 820, "foot", "Wing fixed to the feet",
            "trailing edge", role("pilot"), "right")
    d.append(g)

    text(d, f"{SPAN:.1f} m span   \u00b7   {M['wing_area_m2']:.0f} m\u00b2   \u00b7   aspect ratio 4   "
            f"\u00b7   {M['mass_kg']:.0f} kg all-up   \u00b7   {M['glide_speed_ms']:.0f} m/s trim airspeed",
         W / 2, H - 30, size=15, fill=C["ink"], weight="bold")

    stem = Path(stem)
    svg = d.as_svg().encode()
    cairosvg.svg2png(bytestring=svg, write_to=str(stem.with_suffix(".png")), scale=SCALE)
    cairosvg.svg2pdf(bytestring=svg, write_to=str(stem.with_suffix(".pdf")))
    flat.unlink()
    print(f"saved {stem}.png/.pdf")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(*(Path(p) for p in args)) if args else main()
