"""Workstream A processing: escarpment geometry at Malmesbury Abbey.

Reads the DEM (fetch_dem.py) and writes:
  data/processed/terrain_section.npz   -- SW-NE elevation profile
  analysis/terrain/metrics.json        -- slope/aspect/relief scalars

No plotting here (Rules/CODE.md). The load-bearing number is the slope the
prevailing SW wind climbs: that sets the available ridge lift in Workstream B/C.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEM = ROOT / "data" / "processed" / "malmesbury_dem.npz"
SECTION = ROOT / "data" / "processed" / "terrain_section.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
SLOPE_RADIUS_M = 400.0   # neighbourhood for the escarpment slope distribution
SECTION_HALFLEN_M = 1200.0
SECTION_AZIMUTH_DEG = 45.0  # NE; negative arclength runs SW
SITE_PANEL_HALFWIDTH_M = 300.0  # half-width of the launch-site panel in Figure 1b


def latlon_to_px(lat, lon, d):
    nrows, ncols = d["dem"].shape
    col = (lon - d["lon_w"]) / (d["lon_e"] - d["lon_w"]) * ncols
    row = (d["lat_n"] - lat) / (d["lat_n"] - d["lat_s"]) * nrows
    return int(round(row)), int(round(col))


def main() -> None:
    d = np.load(DEM)
    dem = d["dem"].astype(float)
    nrows, ncols = dem.shape
    lat_mid = (float(d["lat_n"]) + float(d["lat_s"])) / 2
    mx = (float(d["lon_e"]) - float(d["lon_w"])) / ncols * 111320 * math.cos(math.radians(lat_mid))
    my = (float(d["lat_n"]) - float(d["lat_s"])) / nrows * 110540

    ar, ac = latlon_to_px(float(d["abbey_lat"]), float(d["abbey_lon"]), d)

    # Full-grid slope and aspect.
    dz_drow, dz_dcol = np.gradient(dem, my, mx)
    dz_north, dz_east = -dz_drow, dz_dcol
    slope = np.degrees(np.arctan(np.hypot(dz_north, dz_east)))

    # Slope distribution within SLOPE_RADIUS_M of the abbey.
    rr, cc = np.meshgrid(np.arange(nrows), np.arange(ncols), indexing="ij")
    dist_m = np.hypot((rr - ar) * my, (cc - ac) * mx)
    near = dist_m <= SLOPE_RADIUS_M
    slope_near = slope[near]

    # Aspect from a smoothed local gradient (~250 m window).
    win = int(round(250 / mx))
    patch_n = dz_north[ar - win:ar + win, ac - win:ac + win].mean()
    patch_e = dz_east[ar - win:ar + win, ac - win:ac + win].mean()
    aspect = math.degrees(math.atan2(-patch_e, -patch_n)) % 360
    aspect_name = COMPASS[int(((aspect + 22.5) % 360) // 45)]

    # SW-NE cross-section through the abbey.
    t = np.linspace(-SECTION_HALFLEN_M, SECTION_HALFLEN_M, 400)
    az = math.radians(SECTION_AZIMUTH_DEG)
    lat_line = float(d["abbey_lat"]) + (t * math.cos(az)) / 110540
    lon_line = float(d["abbey_lon"]) + (t * math.sin(az)) / (111320 * math.cos(math.radians(lat_mid)))
    prof = np.array([
        dem[min(max(latlon_to_px(la, lo, d)[0], 0), nrows - 1),
            min(max(latlon_to_px(la, lo, d)[1], 0), ncols - 1)]
        for la, lo in zip(lat_line, lon_line)
    ])

    np.savez_compressed(SECTION, t=t, profile=prof,
                        lat_line=lat_line, lon_line=lon_line)

    abbey_elev = float(dem[ar, ac])
    metrics = {
        "data_source": "AWS Terrain Tiles (terrarium), zoom 14, ~6 m/px",
        "m_per_px": [round(mx, 2), round(my, 2)],
        "abbey_elev_m": round(abbey_elev, 1),
        "section_valley_min_m": round(float(prof.min()), 1),
        "relief_abbey_above_valley_m": round(abbey_elev - float(prof.min()), 1),
        "slope_radius_m": SLOPE_RADIUS_M,
        "site_panel_halfwidth_m": SITE_PANEL_HALFWIDTH_M,
        "slope_mean_deg": round(float(slope_near.mean()), 2),
        "slope_p90_deg": round(float(np.percentile(slope_near, 90)), 2),
        "slope_max_deg": round(float(slope_near.max()), 2),
        "aspect_deg": round(aspect, 1),
        "aspect_compass": aspect_name,
        "sw_windward": aspect_name in {"SW", "S", "W"},
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
