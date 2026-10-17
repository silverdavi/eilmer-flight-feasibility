"""Workstream F processing: Monte Carlo feasibility envelope.

The apparatus geometry and the launch day are unknown, so we sample the plausible
parameter space and report the fraction of samples in which a standing launch
from the tower (a) covers 200 m and (b) stays controlled, split by tail vs no
tail, on two flight tracks: into the wind over the valley, and along the SW
slope. Launch wind is drawn from the actual ERA5 SW-sector distribution (Eilmer
chose his day). Glide ratio is not sampled directly; it follows from the sampled
aspect ratio, span efficiency, and zero-lift drag through the drag polar.

Flight model: analysis/aero/flight.py. Seeded for reproducibility. Writes:
  data/processed/montecarlo.npz
  analysis/synthesis/metrics.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "aero"))
from flight import RHO, TRACKS, Site, fly  # noqa: E402

WIND_CSV = ROOT / "data" / "raw" / "malmesbury_wind_era5.csv"
OUT = ROOT / "data" / "processed" / "montecarlo.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

SEED = 42
N = 40000
G_ACCEL = 9.81
TARGET = 200.0
SECTOR = (191.25, 258.75)        # SW launch sector (Workstream B)
WIND_RANGE = (3.0, 16.0)         # launchable SW speeds to sample from
CONTROL_LOSS_MARGIN = 1.0        # depart if time_to_double < flight_time
WILSON_Z = 1.96                  # normal quantile for 95% Wilson score intervals

# sampled plausible ranges (preresearch 01/03); see Table S1
S_AREA = (5.0, 10.0)             # wing area (m^2)
MASS = (70.0, 90.0)              # all-up mass (kg)
CL = (0.7, 1.1)                  # crude-wing trim CL
AR = (3.0, 5.0)                  # aspect ratio
OSWALD = (0.6, 0.8)              # span efficiency
CD0 = (0.05, 0.15)               # zero-lift drag coefficient
TOWER = (15.0, 25.0)             # launch height (m)
SLOPE = (8.0, 18.0)              # escarpment slope (deg); coarse DEM is a floor
RIDGE_EFF = (0.5, 1.0)           # attached-upslope efficiency
CG = (0.35, 0.55)                # hanging-pilot CG (fraction chord)
NP_NOTAIL = 0.25
TAIL_SHIFT = (0.18, 0.32)        # NP aft-shift from a tail; varies with tail size
CMQ_NOTAIL, CMQ_TAIL = -1.5, -10.0


def sample_winds(rng, n):
    df = pd.read_csv(WIND_CSV, usecols=["wind_speed_ms", "wind_dir_deg"]).dropna()
    sw = df[(df.wind_dir_deg >= SECTOR[0]) & (df.wind_dir_deg <= SECTOR[1]) &
            (df.wind_speed_ms >= WIND_RANGE[0]) & (df.wind_speed_ms <= WIND_RANGE[1])]
    return rng.choice(sw.wind_speed_ms.to_numpy(), size=n, replace=True)


def growth_rate(x_cg, x_np, cmq, area, ar, mass, V):
    b = np.sqrt(ar * area)
    c = area / b
    cl_a = 2 * np.pi * ar / (ar + 2)
    qbar = 0.5 * RHO * V**2
    iyy = mass * 0.6**2
    cm_a = cl_a * (x_cg - x_np)
    za = (-qbar * area * cl_a) / (mass * V)
    m_a = qbar * area * c * cm_a / iyy
    m_q = qbar * area * c**2 * cmq / (2 * V * iyy)
    tr, det = za + m_q, za * m_q - m_a
    disc = tr * tr - 4 * det
    return np.where(disc >= 0, 0.5 * (tr + np.sqrt(np.abs(disc))), 0.5 * tr)


def wilson(k, n, z=WILSON_Z):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main() -> None:
    rng = np.random.default_rng(SEED)
    u = sample_winds(rng, N)
    area = rng.uniform(*S_AREA, N)
    mass = rng.uniform(*MASS, N)
    cl = rng.uniform(*CL, N)
    ar = rng.uniform(*AR, N)
    e = rng.uniform(*OSWALD, N)
    cd0 = rng.uniform(*CD0, N)
    tower = rng.uniform(*TOWER, N)
    slope = rng.uniform(*SLOPE, N)
    eff = rng.uniform(*RIDGE_EFF, N)
    cg = rng.uniform(*CG, N)
    np_tail = NP_NOTAIL + rng.uniform(*TAIL_SHIFT, N)

    ld = 0.5 * np.sqrt(np.pi * e * ar / cd0)
    V = np.sqrt(2 * mass * G_ACCEL / (RHO * area * cl))
    w = eff * u * np.sin(np.radians(slope))

    rate_nt = growth_rate(cg, NP_NOTAIL, CMQ_NOTAIL, area, ar, mass, V)
    rate_t = growth_rate(cg, np_tail, CMQ_TAIL, area, ar, mass, V)
    t2_nt = np.where(rate_nt > 1e-6, np.log(2) / rate_nt, np.inf)
    t2_t = np.where(rate_t > 1e-6, np.log(2) / rate_t, np.inf)

    site = Site()
    out, metrics_tracks = {}, {}
    for track in TRACKS:
        R, t_flight, vz = fly(track, tower, u, w, mass, area, cl, ld, site=site)
        reached = R >= TARGET
        dep_nt = t2_nt < CONTROL_LOSS_MARGIN * t_flight
        dep_t = t2_t < CONTROL_LOSS_MARGIN * t_flight
        out[track] = dict(R=R, t_flight=t_flight, vz=vz, reached=reached,
                          dep_nt=dep_nt, dep_t=dep_t)

        def ci(mask):
            k = int(mask.sum())
            lo, hi = wilson(k, N)
            return [round(k / N, 4), round(lo, 4), round(hi, 4)]

        r = reached
        metrics_tracks[track] = {
            "p_reach_200m": ci(r),
            "n_reach_200m": int(r.sum()),
            "median_range_m": round(float(np.median(R)), 0),
            "p90_range_m": round(float(np.percentile(R, 90)), 0),
            "p_reached_and_controlled_no_tail": ci(r & ~dep_nt),
            "p_reached_and_controlled_with_tail": ci(r & ~dep_t),
            "p_departed_given_reached_no_tail": round(float(dep_nt[r].mean()), 3) if r.any() else None,
            "p_departed_given_reached_with_tail": round(float(dep_t[r].mean()), 3) if r.any() else None,
            "median_flight_time_reached_s": round(float(np.median(t_flight[r])), 1) if r.any() else None,
            "median_wind_reached_ms": round(float(np.median(u[r])), 1) if r.any() else None,
            "p10_wind_reached_ms": round(float(np.percentile(u[r], 10)), 1) if r.any() else None,
            "median_ld_reached": round(float(np.median(ld[r])), 1) if r.any() else None,
            "median_ld_all": round(float(np.median(ld)), 1),
            "p_landed_within_50m": round(float((R < 50).mean()), 3),
        }

    slope_reached = out["along_slope"]["reached"]
    np.savez_compressed(
        OUT, target=TARGET, n=N, u=u, ld=ld, V=V,
        t2_notail=t2_nt, t2_tail=t2_t,
        **{f"{k}_{tr}": v for tr, d in out.items() for k, v in d.items()})

    metrics = {
        "n_samples": N, "seed": SEED, "target_m": TARGET, "wilson_z": WILSON_Z,
        "priors": {
            "wind_ms": list(WIND_RANGE), "sector_deg": list(SECTOR),
            "wing_area_m2": list(S_AREA), "mass_kg": list(MASS), "cl": list(CL),
            "aspect_ratio": list(AR), "oswald_e": list(OSWALD), "cd0": list(CD0),
            "tower_m": list(TOWER), "slope_deg": list(SLOPE), "ridge_eff": list(RIDGE_EFF),
            "cg": list(CG), "tail_np_shift": list(TAIL_SHIFT)},
        "wind_source": "ERA5 SW-sector launchable speeds (Workstream B)",
        "flight_model": "standing launch, point mass at fixed trim CL (analysis/aero/flight.py)",
        "tracks": metrics_tracks,
        "ld_from_polar": [round(float(ld.min()), 1), round(float(ld.max()), 1)],
        "notail_t2_median_reached_s": round(float(np.median(t2_nt[slope_reached])), 2),
        "notail_t2_p99_reached_s": round(float(np.percentile(t2_nt[slope_reached], 99)), 2),
        "notail_t2_median_all_s": round(float(np.median(t2_nt)), 2),
        "p_tail_stable_all": round(float(np.mean(~np.isfinite(t2_t) | (rate_t <= 1e-6))), 3),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
