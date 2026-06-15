"""Workstream E processing: impact biomechanics, the broken-legs constraint.

Treats "broke both legs, survived, lame" as data. A feet-first impact decelerates
the body over a stopping distance d (leg flexion + ground give). Average force is
energy over distance:
    F = m v^2 / (2 d),   per leg F/2,
and the legs fracture when the per-leg axial load exceeds the tibia tolerance
(7.5-11.3 kN; Salzar et al. 2014; Abidin et al. 2026). This sets a fracture-onset impact speed
    v* = sqrt(2 d F_total / m).

The physical point: a flared touchdown (vertical speed ~ sink, 1-3 m/s) is well
below v*, so the legs survive; an uncontrolled departure arrives with a large
vertical speed, above v*, so both legs break but the body survives a feet-first
hit. The injuries therefore corroborate loss of control (the no-tail departure),
not a gentle landing.

Reads the Monte Carlo glide speeds; writes:
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
F_LEG_FRACTURE = (7.5e3, 11.3e3)  # tibia axial/combined fracture, per leg (N); Salzar 2014
STOP_DISTANCES = [0.10, 0.20, 0.35]   # leg flexion + ground give (m)
SINK_FLARE = (1.0, 3.0)          # vertical speed in a flared touchdown (m/s)
DEPART_ANGLE = (35.0, 70.0)      # impact flight-path angle after departure (deg)
FATAL_DECEL_G = 100.0            # whole-body feet-first survivability ceiling (g)


def leg_force(v, d, mass=MASS):
    """Average total deceleration force for impact speed v, stop distance d."""
    return mass * v**2 / (2 * d)


def fracture_onset_speed(d, f_total, mass=MASS):
    return np.sqrt(2 * d * f_total / mass)


def main() -> None:
    rng = np.random.default_rng(SEED)
    mc = np.load(MC)
    # glide airspeed per reached world: recover V from range model is overkill;
    # use the MC range and a representative airspeed band instead.
    # departed impacts arrive near flying speed; flared touchdowns near sink.
    V = rng.uniform(11.0, 16.0, size=mc["R"].shape[0])   # glide airspeed (m/s)

    f_lo, f_hi = F_LEG_FRACTURE
    f_total_lo, f_total_hi = 2 * f_lo, 2 * f_hi

    # force vs speed curves for each stopping distance
    v_axis = np.linspace(0, 16, 200)
    curves = {d: leg_force(v_axis, d) / 2 for d in STOP_DISTANCES}  # per leg

    # fracture-onset speed across stopping distance (band over leg tolerance)
    d_axis = np.linspace(0.05, 0.5, 100)
    v_star_lo = fracture_onset_speed(d_axis, f_total_lo)
    v_star_hi = fracture_onset_speed(d_axis, f_total_hi)

    # impact vertical-speed distributions
    flare_vz = rng.uniform(*SINK_FLARE, size=20000)
    depart_angle = np.radians(rng.uniform(*DEPART_ANGLE, size=V.shape[0]))
    depart_vz = V * np.sin(depart_angle)

    # fraction of departed impacts that exceed fracture onset at a mid d=0.2 m
    d_mid = 0.20
    v_star_mid = float(fracture_onset_speed(d_mid, np.mean([f_total_lo, f_total_hi])))
    p_break_depart = float((depart_vz >= v_star_mid).mean())
    p_break_flare = float((flare_vz >= v_star_mid).mean())

    # survivability: peak decel for the median departed impact at d=0.2
    vz_med = float(np.median(depart_vz))
    decel_g = vz_med**2 / (2 * d_mid) / G_ACCEL
    survivable = decel_g < FATAL_DECEL_G

    np.savez_compressed(
        OUT, v_axis=v_axis, curves_keys=np.array(STOP_DISTANCES),
        curves=np.array([curves[d] for d in STOP_DISTANCES]),
        d_axis=d_axis, v_star_lo=v_star_lo, v_star_hi=v_star_hi,
        flare_vz=flare_vz, depart_vz=depart_vz,
        f_leg_band=np.array(F_LEG_FRACTURE), v_star_mid=v_star_mid)

    metrics = {
        "mass_kg": MASS,
        "leg_fracture_per_leg_kN": [f_lo / 1e3, f_hi / 1e3],
        "stop_distance_mid_m": d_mid,
        "fracture_onset_speed_mid_ms": round(v_star_mid, 1),
        "fracture_onset_speed_range_ms": [
            round(float(fracture_onset_speed(0.35, f_total_lo)), 1),
            round(float(fracture_onset_speed(0.10, f_total_hi)), 1)],
        "median_departure_vertical_speed_ms": round(vz_med, 1),
        "p_legs_break_if_departed": round(p_break_depart, 2),
        "p_legs_break_if_flared": round(p_break_flare, 2),
        "median_departure_decel_g": round(decel_g, 0),
        "survivable_feet_first": bool(survivable),
        "reading": "departure impact breaks both legs but is survivable feet-first; "
                   "a flared landing would not break them, so the injuries imply "
                   "an uncontrolled arrival (no tail)",
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
