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
sys.path.insert(0, str(ROOT / "analysis" / "aero"))
from plot_utils import PALETTE, panel_label, save_fig, set_style  # noqa: E402
from flight import INTO_WIND_AZ, along_slope_lift_extent  # noqa: E402

ZOOM_M = 300.0  # half-width of the launch-site panel (m)

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

    fig, (axm, axz, axp) = plt.subplots(1, 3, figsize=(15, 5.0),
                                        gridspec_kw={"width_ratios": [1.0, 1.0, 1.15]})

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

    # b -- launch site: SW-facing slope and the two flight tracks, local metres
    alat, alon = float(d["abbey_lat"]), float(d["abbey_lon"])
    nr, nc = dem.shape
    lat = np.linspace(float(d["lat_n"]), float(d["lat_s"]), nr)
    lon = np.linspace(float(d["lon_w"]), float(d["lon_e"]), nc)
    n_m = (lat - alat) * 110540.0
    e_m = (lon - alon) * 111320.0 * np.cos(np.radians(alat))
    rows = np.nonzero(np.abs(n_m) <= ZOOM_M)[0]
    cols = np.nonzero(np.abs(e_m) <= ZOOM_M)[0]
    sub = dem[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    gy, gx = np.gradient(sub, my, mx)
    dzdn, dzde = -gy, gx
    slope = np.degrees(np.arctan(np.hypot(dzdn, dzde)))
    aspect = (np.degrees(np.arctan2(-dzde, -dzdn)) + 360) % 360
    sw_face = (slope >= 5) & (aspect >= 191.25) & (aspect <= 258.75)
    zext = [e_m[cols[0]], e_m[cols[-1]], n_m[rows[-1]], n_m[rows[0]]]
    axz.imshow(ls.hillshade(sub, vert_exag=3, dx=mx, dy=my), cmap="gray", extent=zext,
               origin="upper", alpha=0.55)
    axz.imshow(np.ma.masked_where(~sw_face, sw_face), cmap="Oranges", vmin=0, vmax=1.6,
               extent=zext, origin="upper", alpha=0.55)
    axz.contour(e_m[cols], n_m[rows], sub, levels=np.arange(60, 100, 2.5),
                colors=PALETTE["slate"], linewidths=0.4, alpha=0.7)
    run, (p0, p1) = along_slope_lift_extent(endpoints=True)
    axz.plot([p0[0], p1[0]], [p0[1], p1[1]], color=PALETTE["moss"], lw=3,
             label=f"along slope ({run:.0f} m of SW-facing slope)")
    ux, uy = np.sin(np.radians(INTO_WIND_AZ)), np.cos(np.radians(INTO_WIND_AZ))
    axz.annotate("", xy=(200 * ux, 200 * uy), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="-|>", color=PALETTE["slate"], lw=2.4))
    axz.plot([], [], color=PALETTE["slate"], lw=2.4, label="into wind (200 m SW)")
    axz.plot(0, 0, "*", color=PALETTE["terracotta"], ms=15, mec="white", mew=1.2)
    axz.annotate("", xy=(ZOOM_M * 0.85, -ZOOM_M * 0.45), xytext=(ZOOM_M * 0.55, -ZOOM_M * 0.75),
                 arrowprops=dict(arrowstyle="-|>", color=PALETTE["ink"], lw=1.4))
    axz.text(ZOOM_M * 0.52, -ZOOM_M * 0.62, "SW wind", fontsize=8, color=PALETTE["ink"], ha="right")
    axz.set_xlim(-ZOOM_M, ZOOM_M)
    axz.set_ylim(-ZOOM_M, ZOOM_M)
    axz.set_aspect("equal")
    axz.set_xlabel("east of abbey (m)")
    axz.set_ylabel("north of abbey (m)")
    axz.set_title("Launch site: SW-facing slope (orange)")
    axz.legend(loc="upper left", fontsize=7.5)
    panel_label(axz, "b", dx=-0.1)

    # c -- cross-section through the abbey
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
    panel_label(axp, "c")

    fig.tight_layout()
    save_fig(fig, "fig1_site")


if __name__ == "__main__":
    main()
