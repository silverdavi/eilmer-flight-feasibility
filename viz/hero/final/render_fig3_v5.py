"""Figure 3 v5: v4 with the prone monk (viz/hero/assets/monk_prone.blend by default).

The prone variant lies flat, parallel to the chord, ~0.33 m under the wing root, hands on the
leading spar at |x| = 0.71 m and ankles tied to the trailing edge. Anchors, the CG mark and the
glide arrow follow its recorded joints (render_fig3_v4.py); only the inset aim is re-centred.

  gtimeout 900 .venv-bpy/bin/python viz/hero/final/render_fig3_v5.py --shot main|inset|all \
      [--pct 25] [--samples 64] [--monk viz/hero/assets/monk_prone.blend]
Writes viz/hero/final/_work/fig3_v5_{main,inset}_render[_pPCT].png and fig3_v5_points.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_fig3_v4 as v4  # noqa: E402

MONK = HERE.parent / "assets" / "monk_prone.blend"
v4.v3.INSET_CAM.update(loc=(3.55, 0.10, -0.62), aim=(0.42, 0.44, -0.10), lens=50)
v4.v3.LIGHT.update(pilot_front=30.0)

if __name__ == "__main__":
    v4.main(src=MONK, tag="fig3_v5")
