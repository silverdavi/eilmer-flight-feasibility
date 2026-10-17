"""Compose Figure 3 v3: v2's render and callouts, plus explanatory overlays.

  * what we see: an inset ("seen from below") of the hands lashed to the leading spar and the
    feet tied to the trailing edge; the two attachment callouts point into it
  * what is missing: a dashed ghost of a conventional tail (boom, tailplane, fin), the
    "No tail" callout points at it
  * how it was meant to work: lift at the wing, weight at the pilot's CG, the intended glide
    and the headwind
Callout texts, label positions, colours and the footer are those of the original figure.

  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python viz/hero/final/compose_fig3_v3.py \
      [main.png inset.png out_stem [points.json]]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose_fig3_v2 as v2  # noqa: E402  (loads cairo, brand, metrics)
from compose_fig3_v2 import C, FONT_CSS, M, SPAN, role, text  # noqa: E402

import cairosvg  # noqa: E402
import drawsvg as draw  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

WORK = HERE / "_work"
W, H, OX, OY, DRAWN_W = v2.W, v2.H, v2.OX, v2.OY, v2.DRAWN_W

INSET = dict(x=814, y=742, w=378, h=260, r=14)
BG = C["parchment"]
INSET_FILL = "#f2ece1"
INK = C["ink"]
AIR = C["dustyblue"]
GHOST = role("danger")


def arrow(g, p0, p1, color, width=1.4, head=10.5, dash=None, opacity=0.9):
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    bx, by = x1 - ux * head, y1 - uy * head
    kw = dict(stroke=color, stroke_width=width, stroke_opacity=opacity, fill="none")
    if dash:
        kw["stroke_dasharray"] = dash
    g.append(draw.Line(x0, y0, bx + ux * 1.5, by + uy * 1.5, **kw))
    hw = head * 0.42
    g.append(draw.Lines(x1, y1, bx - uy * hw, by + ux * hw, bx + uy * hw, by - ux * hw,
                        close=True, fill=color, fill_opacity=opacity, stroke="none"))


def label(g, s, x, y, color=INK, anchor="start", size=15, style="italic"):
    g.append(draw.Text(s, size, x, y, fill=color, text_anchor=anchor, font_family=FONT_CSS,
                       font_style=style))


def cg_symbol(g, x, y, r=6.5):
    g.append(draw.Circle(x, y, r, fill="white", stroke=INK, stroke_width=1.2))
    g.append(draw.Path(f"M{x},{y} L{x + r},{y} A{r},{r} 0 0,1 {x},{y + r} Z", fill=INK))
    g.append(draw.Path(f"M{x},{y} L{x - r},{y} A{r},{r} 0 0,1 {x},{y - r} Z", fill=INK))


def callout(g, ax, ay, lx, ly, term, gloss, color, side):
    anchor = {"left": "end", "right": "start", "top": "middle"}[side]
    sx, sy = (lx, ly + (30 if side == "top" else 26))
    g.append(draw.Line(sx, sy, ax, ay, stroke=color, stroke_width=1.4, stroke_opacity=0.9))
    g.append(draw.Circle(ax, ay, 5, fill=color, stroke="white", stroke_width=1.6))
    text(g, term, lx, ly, size=19, fill=color, anchor=anchor, weight="bold")
    text(g, gloss, lx, ly + 21, size=14, fill=C["slate"], anchor=anchor)


def flat_rgba(path, out):
    a = np.asarray(Image.open(path)).astype(np.float32)
    if a.max() > 255:
        a = a / 257.0
    Image.fromarray(a.round().clip(0, 255).astype(np.uint8), "RGBA").save(out, optimize=True)


def main(main_png=WORK / "fig3_v3_main_render.png", inset_png=WORK / "fig3_v3_inset_render.png",
         stem=HERE / "fig_apparatus_v3", points=WORK / "fig3_v3_points.json"):
    P = json.loads(Path(points).read_text())
    A, B = P["main"], P["inset"]
    pw, _ = A.pop("_size")
    iw, ih = B.pop("_size")
    F = DRAWN_W / pw

    def m(k):
        return OX + A[k][0] * F, OY + A[k][1] * F

    def i(k):
        return INSET["x"] + B[k][0] * INSET["w"] / iw, INSET["y"] + B[k][1] * INSET["h"] / ih

    flat = WORK / "_flat_main.png"
    rw, rh = v2.prep_render(main_png, flat)
    iflat = WORK / "_flat_inset.png"
    flat_rgba(inset_png, iflat)

    d = draw.Drawing(W, H, origin=(0, 0))
    d.append(draw.Rectangle(0, 0, W, H, fill=BG))
    d.append(draw.Image(OX, OY, DRAWN_W, DRAWN_W * rh / rw, path=str(flat), embed=True))

    # ---- what is missing: ghost tail where a conventional tail would sit
    g = draw.Group()
    dash = dict(stroke=GHOST, stroke_width=1.2, stroke_dasharray="5,4", stroke_opacity=0.75)
    tp = [m(k) for k in ("tp_le_l", "tp_le_r", "tp_te_r", "tp_te_l")]
    g.append(draw.Lines(*[c for p in tp for c in p], close=True, fill=GHOST, fill_opacity=0.06,
                        **dash))
    fin = [m(k) for k in ("fin0", "fin1", "fin2", "fin3")]
    g.append(draw.Lines(*[c for p in fin for c in p], close=True, fill=GHOST, fill_opacity=0.06,
                        **dash))
    g.append(draw.Line(*m("boom0"), *m("boom1"), **dash))
    d.append(g)

    # ---- how it was meant to work: lift, weight, glide, headwind
    g = draw.Group()
    arrow(g, m("lift0"), m("lift1"), INK)
    lx, ly = m("lift1")
    label(g, "lift", lx + 9, ly + 12)
    cx, cy = m("cg")
    arrow(g, (cx, cy + 7), m("weight1"), INK)
    cg_symbol(g, cx, cy)
    wx, wy = m("weight1")
    label(g, "weight", wx - 10, wy - 2, anchor="end")
    arrow(g, m("glide0"), m("glide1"), INK, width=1.4, dash="6,4")
    gx, gy = m("glide1")
    label(g, "glide", gx - 10, gy + 4, anchor="end")
    for k in range(3):
        arrow(g, m(f"wind{k}a"), m(f"wind{k}b"), AIR, width=1.4, head=9)
    wx, wy = m("wind2a")
    label(g, "wind", wx - 4, wy + 20, color=AIR)
    d.append(g)

    # ---- what we see: the attachments, from below
    x, y, w, h, r = (INSET[k] for k in ("x", "y", "w", "h", "r"))
    clip = draw.ClipPath()
    clip.append(draw.Rectangle(x, y, w, h, rx=r, ry=r))
    d.append(draw.Rectangle(x, y, w, h, rx=r, ry=r, fill=INSET_FILL))
    d.append(draw.Image(x, y, w, h, path=str(iflat), embed=True, clip_path=clip))
    d.append(draw.Rectangle(x, y, w, h, rx=r, ry=r, fill="none", stroke=C["slate"],
                            stroke_width=0.9, stroke_opacity=0.7))
    label(d, "seen from below", x + 12, y + h - 12, color=C["slate"], size=12.5)

    # ---- the original callouts (texts, label positions, colours unchanged)
    g = draw.Group()
    callout(g, *m("tail_c"), 720, 150, "No tail", "as William of Malmesbury records",
            role("danger"), "top")
    callout(g, *m("batten"), 360, 300, "Wooden frame and battens", "bent to camber",
            role("structure"), "left")
    callout(g, *m("head"), 360, 885, "Pilot, prone", "below the wing", role("pilot"), "left")
    callout(g, *m("tipR"), 1205, 430, "Cloth membrane wing",
            f"{M['wing_area_m2']:.0f} m\u00b2, {SPAN:.1f} m span, aspect ratio 4",
            role("membrane"), "right")
    callout(g, *i("hand"), 1205, 650, "Wing fixed to the hands", "leading spar",
            role("pilot"), "right")
    callout(g, *i("foot"), 1205, 820, "Wing fixed to the feet", "trailing edge",
            role("pilot"), "right")
    d.append(g)

    text(d, f"{SPAN:.1f} m span   \u00b7   {M['wing_area_m2']:.0f} m\u00b2   \u00b7   aspect ratio 4   "
            f"\u00b7   {M['mass_kg']:.0f} kg all-up   \u00b7   {M['glide_speed_ms']:.0f} m/s trim airspeed",
         W / 2, H - 30, size=15, fill=INK, weight="bold")

    stem = Path(stem)
    svg = d.as_svg().encode()
    cairosvg.svg2png(bytestring=svg, write_to=str(stem.with_suffix(".png")), scale=v2.SCALE)
    cairosvg.svg2pdf(bytestring=svg, write_to=str(stem.with_suffix(".pdf")))
    flat.unlink()
    iflat.unlink()
    print(f"saved {stem}.png/.pdf")


if __name__ == "__main__":
    args = [Path(p) for p in sys.argv[1:]]
    main(*args) if args else main()
