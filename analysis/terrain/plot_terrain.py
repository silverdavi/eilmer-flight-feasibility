"""Workstream A figure: site and launch geometry (Figure 1).

Reads the DEM, the cross-section, and metrics.json; produces figures/fig1_site.
Numbers shown on the canvas are read from metrics.json, not recomputed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "config"))
from plot_utils import PALETTE, panel_label, save_fig, set_style  # noqa: E402

DEM = ROOT / "data" / "processed" / "malmesbury_dem.npz"
SECTION = ROOT / "data" / "processed" / "terrain_section.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

TOWER_M = 18.0  # anchor launch-tower height (White 1961); band 15-25 m


def main() -> None:
    set_style()
    d = np.load(DEM)
    dem = d["dem"].astype(float)
    sec = np.load(SECTION)
    m = json.loads(METRICS.read_text())
    mx, my = m["m_per_px"]

    fig, (axm, axp) = plt.subplots(1, 2, figsize=(12, 5.2))

    # a -- hillshade with launch geometry
    ls = LightSource(azdeg=315, altdeg=45)
    rgb = ls.shade(dem, cmap=plt.cm.terrain, blend_mode="soft",
                   vert_exag=3, dx=mx, dy=my)
    extent = [float(d["lon_w"]), float(d["lon_e"]), float(d["lat_s"]), float(d["lat_n"])]
    axm.imshow(rgb, extent=extent, origin="upper", aspect="auto")
    axm.plot(sec["lon_line"], sec["lat_line"], "--", color=PALETTE["ink"], lw=1.4)
    axm.plot(float(d["abbey_lon"]), float(d["abbey_lat"]), "*",
             color=PALETTE["terracotta"], ms=17, mec="white", mew=1.2)
    axm.set_xlabel("longitude (deg)")
    axm.set_ylabel("latitude (deg)")
    axm.set_title("Malmesbury terrain, hillshade")
    axm.annotate("abbey", (float(d["abbey_lon"]), float(d["abbey_lat"])),
                 textcoords="offset points", xytext=(10, 7), color=PALETTE["terracotta"])
    axm.annotate("SW-NE section", (sec["lon_line"][20], sec["lat_line"][20]),
                 textcoords="offset points", xytext=(-72, -2), color=PALETTE["ink"], fontsize=8)
    panel_label(axm, "a", dx=-0.08)

    # b -- cross-section through the abbey
    t, prof = sec["t"], sec["profile"]
    base = prof.min() - 5
    axp.fill_between(t, prof, base, color=PALETTE["shade"])
    axp.plot(t, prof, color=PALETTE["ink"], lw=1.8)
    abbey_elev = m["abbey_elev_m"]
    axp.plot([0, 0], [abbey_elev, abbey_elev + TOWER_M], color=PALETTE["terracotta"], lw=2.2)
    axp.fill_betweenx([abbey_elev + 15, abbey_elev + 25], -18, 18,
                      color=PALETTE["terracotta"], alpha=0.15)
    axp.plot(0, abbey_elev + TOWER_M, "v", color=PALETTE["terracotta"], ms=8)
    axp.plot(0, abbey_elev, "*", color=PALETTE["terracotta"], ms=15, mec="white")
    axp.set_xlabel("distance along SW-NE section (m)")
    axp.set_ylabel("elevation (m)")
    axp.set_title("Cross-section through abbey")
    axp.set_ylim(base, abbey_elev + 32)
    axp.annotate(f"tower 18 m\n(15-25 m band)", (0, abbey_elev + TOWER_M),
                 textcoords="offset points", xytext=(12, 2), fontsize=8, color=PALETTE["terracotta"])
    axp.annotate(f"slope p90 {m['slope_p90_deg']:.1f} deg, faces {m['aspect_compass']}",
                 (-1150, abbey_elev + 22), fontsize=8, color=PALETTE["slate"])
    panel_label(axp, "b")

    fig.tight_layout()
    save_fig(fig, "fig1_site")


if __name__ == "__main__":
    main()
