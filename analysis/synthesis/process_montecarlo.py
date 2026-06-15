"""Workstream F processing: Monte Carlo feasibility envelope (Figure 6).

The apparatus geometry and the launch day are unknown, so we sample the plausible
space and report the fraction of worlds in which the flight (a) covers 200 m and
(b) stays controlled, split by tail vs no tail. Launch wind is drawn from the
actual ERA5 SW-sector distribution (Eilmer chose his day), tying this to
Workstream B. Models match Workstream C.

Seeded for reproducibility. Writes:
  data/processed/montecarlo.npz
  analysis/synthesis/metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WIND_CSV = ROOT / "data" / "raw" / "malmesbury_wind_era5.csv"
TERRAIN = ROOT / "analysis" / "terrain" / "metrics.json"
OUT = ROOT / "data" / "processed" / "montecarlo.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

SEED = 42
N = 40000
G_ACCEL, RHO = 9.81, 1.225
TARGET = 200.0
SECTOR = (191.25, 258.75)        # SW launch sector (Workstream B)
WIND_RANGE = (3.0, 16.0)         # launchable SW speeds to sample from
CONTROL_LOSS_MARGIN = 1.0        # depart if time_to_double < flight_time

# sampled plausible ranges (see paper Methods and Table S1)
S_AREA = (5.0, 10.0)             # wing area (m^2)
MASS = (70.0, 90.0)              # all-up mass (kg)
CL = (0.7, 1.1)                  # crude-wing trim CL
LD = (3.0, 7.0)                  # crude-wing glide ratio band
TOWER = (15.0, 25.0)             # launch height (m)
SLOPE = (8.0, 18.0)              # escarpment slope (deg); coarse DEM is a floor
RIDGE_EFF = (0.5, 1.0)           # attached-upslope efficiency
CG = (0.35, 0.55)                # hanging-pilot CG (fraction chord)
AR = (3.0, 5.0)                  # aspect ratio
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
    # max real eigenvalue of [[za,1],[m_a,m_q]]
    tr, det = za + m_q, za * m_q - m_a
    disc = tr * tr - 4 * det
    if disc >= 0:
        return 0.5 * (tr + np.sqrt(disc))
    return 0.5 * tr  # complex pair, real part


def wilson(k, n, z=1.96):
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
    ld = rng.uniform(*LD, N)
    tower = rng.uniform(*TOWER, N)
    slope = rng.uniform(*SLOPE, N)
    eff = rng.uniform(*RIDGE_EFF, N)
    cg = rng.uniform(*CG, N)
    ar = rng.uniform(*AR, N)
    np_tail = NP_NOTAIL + rng.uniform(*TAIL_SHIFT, N)

    V = np.sqrt(2 * mass * G_ACCEL / (RHO * area * cl))
    sin_g = 1 / np.sqrt(1 + ld**2)
    cos_g = ld / np.sqrt(1 + ld**2)
    sink = V * sin_g
    w = eff * u * np.sin(np.radians(slope))
    net = sink - w
    soaring = net <= 0
    R = np.where(soaring, 1000.0, V * cos_g * tower / np.maximum(net, 1e-3))
    R = np.minimum(R, 1000.0)
    reached = R >= TARGET
    flight_time = R / (V * cos_g)

    def departs(x_np, cmq):
        xnp = np.broadcast_to(x_np, (N,))
        rate = np.array([growth_rate(cg[i], xnp[i], cmq, area[i], ar[i], mass[i], V[i])
                         for i in range(N)])
        t2 = np.where(rate > 1e-6, np.log(2) / rate, np.inf)
        return t2 < CONTROL_LOSS_MARGIN * flight_time, rate

    dep_nt, rate_nt = departs(NP_NOTAIL, CMQ_NOTAIL)
    dep_t, rate_t = departs(np_tail, CMQ_TAIL)

    t2_nt = np.where(rate_nt > 1e-6, np.log(2) / rate_nt, np.inf)
    t2_t = np.where(rate_t > 1e-6, np.log(2) / rate_t, np.inf)

    def classes(dep):
        short = ~reached
        reached_dep = reached & dep
        reached_ctrl = reached & ~dep
        return np.array([short.mean(), reached_dep.mean(), reached_ctrl.mean()])

    cls_nt = classes(dep_nt)
    cls_t = classes(dep_t)

    np.savez_compressed(
        OUT, R=R, reached=reached, dep_notail=dep_nt, dep_tail=dep_t,
        u=u, classes_notail=cls_nt, classes_tail=cls_t, target=TARGET, n=N,
        t2_notail=t2_nt, t2_tail=t2_t, flight_time=flight_time,
        sm_notail=cg - NP_NOTAIL, sm_tail=cg - np_tail)

    def ci(frac):
        lo, hi = wilson(int(round(frac * N)), N)
        return [round(frac, 3), round(lo, 3), round(hi, 3)]

    metrics = {
        "n_samples": N, "seed": SEED,
        "wind_source": "ERA5 SW-sector launchable speeds (Workstream B)",
        "p_reach_200m": ci(float(reached.mean())),
        "p_reached_and_departed_no_tail": ci(float((reached & dep_nt).mean())),
        "p_reached_and_controlled_no_tail": ci(float((reached & ~dep_nt).mean())),
        "p_reached_and_controlled_with_tail": ci(float((reached & ~dep_t).mean())),
        "p_departed_given_reached_no_tail": round(float(dep_nt[reached].mean()), 3),
        "p_departed_given_reached_with_tail": round(float(dep_t[reached].mean()), 3),
        "median_range_m": round(float(np.median(R)), 0),
        "median_range_reached_pct": round(100 * float(reached.mean()), 1),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
