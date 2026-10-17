"""Workstream E processing: impact biomechanics, the broken-legs constraint.

Treats "broke both legs, survived, lame" as data. A feet-first impact decelerates
the body over a stopping distance d (leg flexion + ground give). Average force is
energy over distance:
    F = m v^2 / (2 d),   per leg F/2,
and the legs fracture when the per-leg axial load exceeds the tibia tolerance
(7.5-11.3 kN; preresearch H). This sets a fracture-onset impact speed
    v* = sqrt(2 d F_total / m).

Two arrival modes are compared, both for the Monte Carlo samples that reach
200 m along the slope:
  controlled, no flare: the vertical speed at ground contact from the integrated
      glide (analysis/aero/flight.py), with no flare to reduce it;
  loss of pitch control: the craft arrives near flying speed V on a steep path,
      vertical speed V sin(theta) for impact angle theta.

Reads data/processed/montecarlo.npz; writes:
  data/processed/biomech.npz
  analysis/biomech/metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MC = ROOT / "data" / "processed" / "montecarlo.npz"
OUT = ROOT / "data" / "processed" / "biomech.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

SEED = 7
MASS = 80.0                       # all-up mass (kg)
G_ACCEL = 9.81
F_LEG_FRACTURE = (7.5e3, 11.3e3)  # tibia axial fracture, per leg (N); preresearch
F_TIBIA_AXIAL_SALZAR = 10.3e3     # recommended tibia-only axial threshold (N); Salzar 2014
STOP_DISTANCE_MID = 0.20          # central stopping distance (m)
STOP_DISTANCES = [0.10, STOP_DISTANCE_MID, 0.35]   # leg flexion + ground give (m)
DEPART_ANGLE = (35.0, 70.0)      # impact flight-path angle after loss of control (deg)
FATAL_DECEL_G = 100.0            # whole-body feet-first survivability ceiling (g)
EXERCISE_DIVE_ANGLE = 50.0       # worked path angle for teaching Exercise 7 (deg), within DEPART_ANGLE


def leg_force(v, d, mass=MASS):
    """Average total deceleration force for impact speed v, stop distance d."""
    return mass * v**2 / (2 * d)


def fracture_onset_speed(d, f_total, mass=MASS):
    return np.sqrt(2 * d * f_total / mass)


def main() -> None:
    rng = np.random.default_rng(SEED)
    mc = np.load(MC)
    reached = mc["reached_along_slope"]
    V = mc["V"][reached]                          # trim airspeed of reaching samples
    controlled_vz = mc["vz_along_slope"][reached]  # integrated, unflared arrival

    f_lo, f_hi = F_LEG_FRACTURE
    f_total_lo, f_total_hi = 2 * f_lo, 2 * f_hi

    v_axis = np.linspace(0, 16, 200)
    curves = {d: leg_force(v_axis, d) / 2 for d in STOP_DISTANCES}  # per leg

    d_axis = np.linspace(0.05, 0.5, 100)
    v_star_lo = fracture_onset_speed(d_axis, f_total_lo)
    v_star_hi = fracture_onset_speed(d_axis, f_total_hi)

    depart_angle = np.radians(rng.uniform(*DEPART_ANGLE, size=V.shape[0]))
    depart_vz = V * np.sin(depart_angle)

    d_mid = STOP_DISTANCE_MID
    v_star_mid = float(fracture_onset_speed(d_mid, np.mean([f_total_lo, f_total_hi])))
    v_star_min = float(fracture_onset_speed(STOP_DISTANCES[0], f_total_lo))
    p_break_depart = float((depart_vz >= v_star_mid).mean())
    p_break_controlled = float((controlled_vz >= v_star_mid).mean())
    p_break_controlled_worst = float((controlled_vz >= v_star_min).mean())

    vz_med = float(np.median(depart_vz))
    decel_g = vz_med**2 / (2 * d_mid) / G_ACCEL
    survivable = decel_g < FATAL_DECEL_G

    np.savez_compressed(
        OUT, v_axis=v_axis, curves_keys=np.array(STOP_DISTANCES),
        curves=np.array([curves[d] for d in STOP_DISTANCES]),
        d_axis=d_axis, v_star_lo=v_star_lo, v_star_hi=v_star_hi,
        controlled_vz=controlled_vz, depart_vz=depart_vz,
        f_leg_band=np.array(F_LEG_FRACTURE), v_star_mid=v_star_mid)

    metrics = {
        "mass_kg": MASS,
        "n_reached_samples": int(reached.sum()),
        "leg_fracture_per_leg_kN": [f_lo / 1e3, f_hi / 1e3],
        "tibia_axial_salzar_kN": F_TIBIA_AXIAL_SALZAR / 1e3,
        "stop_distances_m": [STOP_DISTANCES[0], STOP_DISTANCES[-1]],
        "stop_distance_mid_m": d_mid,
        "exercise_dive_angle_deg": EXERCISE_DIVE_ANGLE,
        "fracture_onset_speed_mid_ms": round(v_star_mid, 1),
        "fracture_onset_speed_range_ms": [
            round(v_star_min, 1),
            round(float(fracture_onset_speed(STOP_DISTANCES[-1], f_total_hi)), 1)],
        "controlled_vz_median_ms": round(float(np.median(controlled_vz)), 1),
        "controlled_vz_p99_ms": round(float(np.percentile(controlled_vz, 99)), 1),
        "controlled_vz_max_ms": round(float(np.max(controlled_vz)), 1),
        "median_departure_vertical_speed_ms": round(vz_med, 1),
        "depart_angle_deg": list(DEPART_ANGLE),
        "airspeed_reached_ms": [round(float(V.min()), 1), round(float(V.max()), 1)],
        "p_legs_break_if_departed": round(p_break_depart, 2),
        "p_legs_break_if_controlled_unflared": round(p_break_controlled, 3),
        "p_legs_break_if_controlled_unflared_weakest_legs": round(p_break_controlled_worst, 3),
        "median_departure_decel_g": round(decel_g, 0),
        "survivable_feet_first": bool(survivable),
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
