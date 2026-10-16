"""Workstream B, Figure 3: first-order ridge-lift field over the escarpment.

Linear orographic model (neutral, non-rotating limit): streamline vertical
displacement decays as exp(-k z) above terrain, so the vertical velocity is
  w(x, z) = U * dh/dx * exp(-k z),
with U the incoming SW wind, dh/dx the along-wind surface slope, and k = 2*pi/L
set by the escarpment horizontal scale L. This is the Phase-1 stand-in for the
LES / WAsP solve (Workstream B, layer 3); it is consistent by construction with
the w = U sin(slope) scaling used in Workstream C.

Reads data/processed/terrain_section.npz; writes:
  data/processed/ridge_field.npz
  analysis/weather/ridge_metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SECTION = ROOT / "data" / "processed" / "terrain_section.npz"
OUT = ROOT / "data" / "processed" / "ridge_field.npz"
METRICS = Path(__file__).resolve().parent / "ridge_metrics.json"

U_WIND = 8.0          # incoming SW wind (m/s), favourable-band mean
L_SCALE = 600.0       # escarpment horizontal scale (m); decay k = 2*pi/L
Z_TOP = 150.0         # height above baseline (m)
AERO_METRICS = ROOT / "analysis" / "aero" / "metrics.json"
TERRAIN_METRICS = ROOT / "analysis" / "terrain" / "metrics.json"
SMOOTH_M = 42.0       # along-wind smoothing window for the slope (m)
X_WINDOW = (-700.0, 500.0)   # launch-relevant span around the abbey (m)
SLOPE_CAP = 0.60      # |dh/dx| cap (~31 deg); the coarse DEM spikes are artefacts
WINDWARD = (-450.0, -10.0)   # SW windward face, where launch lift is read


def smooth(y, win):
    k = np.ones(win) / win
    return np.convolve(y, k, mode="same")


def main() -> None:
    sec = np.load(SECTION)
    x_full = sec["t"].astype(float)         # SW(-) to NE(+), abbey at 0
    elev_full = sec["profile"].astype(float)
    sel = (x_full >= X_WINDOW[0]) & (x_full <= X_WINDOW[1])
    x = x_full[sel]
    elev = elev_full[sel]
    dx = float(np.mean(np.diff(x)))
    win = max(3, int(SMOOTH_M / dx))
    elev_s = smooth(elev, win)
    dhdx = np.clip(np.gradient(elev_s, dx), -SLOPE_CAP, SLOPE_CAP)  # wind blows +x
    dhdx[:win] = 0.0    # suppress convolution edge artefacts at the boundaries
    dhdx[-win:] = 0.0

    base = float(elev[0])                    # SW upwind reference level
    terrain_rel = elev - base
    z = np.linspace(0, Z_TOP, 160)
    k = 2 * np.pi / L_SCALE

    W = U_WIND * dhdx[None, :] * np.exp(-k * z[:, None])   # (nz, nx)
    # mask underground
    underground = z[:, None] < terrain_rel[None, :]
    Wm = np.where(underground, np.nan, W)

    # terrain-following streamlines (dz/dx = w/U = dh/dx * exp(-k z))
    starts = [10, 30, 60, 100, 140]
    streams = []
    for z0 in starts:
        zs = np.empty_like(x)
        zz = float(z0)
        for i in range(len(x)):
            zs[i] = zz
            zz = max(zz + dhdx[i] * np.exp(-k * zz) * dx, terrain_rel[i])
        streams.append(zs)
    streams = np.array(streams)

    # best available lift on the windward face vs height
    w_surface = U_WIND * dhdx                 # near-surface w along x
    wind_mask = (x >= WINDWARD[0]) & (x <= WINDWARD[1])
    ix_max = int(np.arange(len(x))[wind_mask][np.argmax(w_surface[wind_mask])])
    w_best_vs_z = U_WIND * dhdx[ix_max] * np.exp(-k * z)

    # still-air sink of the nominal craft at trim, V / sqrt(1 + (L/D)^2), for the
    # best and nominal wings of the drag-polar band (Workstream C)
    aero = json.loads(AERO_METRICS.read_text())
    V = aero["inputs"]["glide_speed_ms"]
    ld_best, ld_nom = aero["drag_polar"]["ld_max_band"][1], aero["drag_polar"]["ld_max_nominal"]
    sink = {"best": V / np.sqrt(1 + ld_best**2), "nominal": V / np.sqrt(1 + ld_nom**2)}
    slope_p90 = json.loads(TERRAIN_METRICS.read_text())["slope_p90_deg"]
    w_slope_formula = U_WIND * np.sin(np.radians(slope_p90))
    w_peak = float(w_surface[ix_max])

    np.savez_compressed(
        OUT, x=x, z=z, W=Wm, elev=elev, terrain_rel=terrain_rel, base=base,
        streams=streams, stream_starts=np.array(starts),
        U=U_WIND, L=L_SCALE, sink_best=sink["best"], sink_nominal=sink["nominal"],
        ld_best=ld_best, ld_nominal=ld_nom, w_slope_formula=w_slope_formula,
        w_best_vs_z=w_best_vs_z, x_max_lift=x[ix_max])

    metrics = {
        "model": "linear orographic, w = U dh/dx exp(-k z); Phase-1 stand-in for LES/WAsP",
        "U_wind_ms": U_WIND,
        "L_scale_m": L_SCALE,
        "max_surface_lift_ms": round(w_peak, 2),
        "x_of_max_lift_m_from_abbey": round(float(x[ix_max]), 0),
        "slope_formula_lift_ms": round(float(w_slope_formula), 2),
        "sink_best_wing_ms": round(float(sink["best"]), 2),
        "sink_nominal_wing_ms": round(float(sink["nominal"]), 2),
        "wind_for_peak_lift_to_match_best_sink_ms": round(float(U_WIND * sink["best"] / w_peak), 1),
        "note": "coarse 6 m DEM under-resolves the escarpment; LIDAR + LES "
                "(Phase 2) expected to raise the slope and the lift",
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
