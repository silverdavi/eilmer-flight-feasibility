"""Compose Figure 3 v6: v5's renders and overlays on a white page with a neutral grey shadow.

  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python viz/hero/final/compose_fig3_v6.py \
      [--inset-fill #F4F4F4] [main.png inset.png out_stem points.json]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose_fig3_v3 as v3  # noqa: E402

WORK = HERE / "_work"
v3.BG = "#ffffff"
v3.v2.SHADOW_RGB = (65, 65, 65)      # same core contrast against white as v5's umber on parchment

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inset-fill", default="#f4f4f4")
    ap.add_argument("paths", nargs="*", type=Path, default=[
        WORK / "fig3_v5_main_render.png", WORK / "fig3_v5_inset_render.png",
        HERE / "fig_apparatus_v6", WORK / "fig3_v5_points.json"])
    a = ap.parse_args()
    v3.INSET_FILL = a.inset_fill
    v3.main(*a.paths)
