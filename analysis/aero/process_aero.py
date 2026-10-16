"""Workstream C processing: glide feasibility and the tail/control verdict.

Writes processed arrays + metrics.json for three figures:

Glide-ratio band: the crude-wing L/D band follows from the parabolic drag polar,
L/D_max = (1/2) sqrt(pi e AR / C_D0), over the plausible aspect ratio, span
efficiency, and zero-lift drag of a cloth hand-and-foot wing with a prone pilot.

Glide feasibility: a standing launch from the tower, integrated as a point mass
(analysis/aero/flight.py) on two tracks, into the wind over the valley and along
the SW slope. Range vs wind for several L/D, the minimum wind for a 200 m flight,
and example trajectories that show the launch dive.

Tail verdict: a tailless hand/foot wing is statically unstable in pitch across
the CG a hanging pilot can reach. We integrate the pitch response to a gust and
compare the divergence timescale with the flight duration and with human
corrective reaction time; a tail damps it.

Sources for constants in aero_overview.md / preresearch/. No plotting here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from flight import G_ACCEL, RHO, TRACKS, V_JUMP, Site, fly

ROOT = Path(__file__).resolve().parents[2]
TERRAIN_METRICS = ROOT / "analysis" / "terrain" / "metrics.json"
WEATHER_METRICS = ROOT / "analysis" / "weather" / "metrics.json"
GLIDE = ROOT / "data" / "processed" / "glide_curves.npz"
STAB = ROOT / "data" / "processed" / "stability_sim.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

# --- environment / apparatus (sources in preresearch 03 + aero_overview) ---
MASS = 80.0              # pilot + apparatus (kg)
WING_AREA = 7.0          # nominal (m^2); sweep 5-10 in Workstream F
CL_TRIM = 0.8            # glide trim lift coefficient
LAUNCH_H = 18.0          # tower height (m); White 1961, band 15-25
TARGET_RANGE = 200.0     # "more than a furlong" (m)
EXAMPLE_WINDS = [5.0, 8.0, 11.0]   # trajectories shown in the glide figure

# --- drag polar for the glide-ratio band ---
AR_BAND = (3.0, 5.0)             # span^2/area of a hand-and-foot wing
OSWALD_BAND = (0.6, 0.8)         # span efficiency, crude membrane wing
CD0_BAND = (0.05, 0.15)          # zero-lift drag: pilot, frame, slack cloth

# --- stability model ---
ASPECT_RATIO = 4.0
XAC_WING = 0.25                  # tailless neutral point (fraction chord)
TAIL_NP_SHIFT = 0.28             # (a_t/a_w) V_H (1 - de/da) -> NP to 0.53 c
CMQ_NOTAIL, CMQ_TAIL = -1.5, -10.0
IYY = 30.0                       # pitch inertia (kg m^2), m k^2, k ~ 0.6 m
IYY_BAND = (0.5, 2.0)            # sensitivity multiplier on inertia
CG_PLAUSIBLE = (0.35, 0.55)      # hanging-pilot CG range (fraction chord)
GUST_ALPHA0 = np.deg2rad(8.0)    # initial AoA perturbation from a gust
CONTROL_LOSS_DEG = 60.0          # pitch attitude beyond which recovery is hopeless
REACTION_TIME = (0.15, 0.3)      # human corrective delay (s); McRuer & Jex 1967


def glide_speed(area=WING_AREA, cl=CL_TRIM):
    return float(np.sqrt(2 * MASS * G_ACCEL / (RHO * area * cl)))


def ld_max(ar, e, cd0):
    return 0.5 * np.sqrt(np.pi * e * ar / cd0)


def ridge_updraft(wind, slope_deg):
    return wind * np.sin(np.radians(slope_deg))


def sp_matrix(x_cg, x_np, cmq, iyy, V):
    b = np.sqrt(ASPECT_RATIO * WING_AREA)
    c = WING_AREA / b
    cl_a = 2 * np.pi * ASPECT_RATIO / (ASPECT_RATIO + 2)
    qbar = 0.5 * RHO * V**2
    cm_a = cl_a * (x_cg - x_np)
    za = (-qbar * WING_AREA * cl_a) / (MASS * V)
    m_a = qbar * WING_AREA * c * cm_a / iyy
    m_q = qbar * WING_AREA * c**2 * cmq / (2 * V * iyy)
    return np.array([[za, 1.0], [m_a, m_q]]), c


def simulate_pitch(x_cg, x_np, cmq, iyy, V, t_end=15.0, dt=0.01):
    """Integrate [alpha, q, theta] from a gust; return t, theta(deg)."""
    A, _ = sp_matrix(x_cg, x_np, cmq, iyy, V)
    n = int(t_end / dt)
    t = np.arange(n) * dt
    state = np.array([GUST_ALPHA0, 0.0, 0.0])  # alpha, q, theta
    theta = np.empty(n)

    def deriv(s):
        a, q, _ = s
        ad, qd = A @ np.array([a, q])
        return np.array([ad, qd, q])

    for i in range(n):
        theta[i] = state[2]
        k1 = deriv(state)
        k2 = deriv(state + 0.5 * dt * k1)
        k3 = deriv(state + 0.5 * dt * k2)
        k4 = deriv(state + dt * k3)
        state = state + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        if abs(state[2]) > np.deg2rad(150):  # clamp runaway for plotting
            theta[i:] = np.sign(state[2]) * np.deg2rad(150)
            break
    return t, np.rad2deg(theta)


def growth_rate(x_cg, x_np, cmq, iyy, V):
    A, _ = sp_matrix(x_cg, x_np, cmq, iyy, V)
    return float(np.max(np.linalg.eigvals(A).real))


def time_to_double(rate):
    return np.log(2) / rate if rate > 1e-6 else np.inf


def min_wind_for_target(winds, ranges):
    ok = ranges >= TARGET_RANGE
    return float(winds[np.argmax(ok)]) if ok.any() else None


def main() -> None:
    slope = json.loads(TERRAIN_METRICS.read_text())["slope_p90_deg"]
    V = glide_speed()
    np_nt, np_t = XAC_WING, XAC_WING + TAIL_NP_SHIFT
    site = Site()

    # --- glide-ratio band from the drag polar ---
    ld_lo = float(ld_max(AR_BAND[0], OSWALD_BAND[0], CD0_BAND[1]))
    ld_hi = float(ld_max(AR_BAND[1], OSWALD_BAND[1], CD0_BAND[0]))
    ld_nom = float(ld_max(np.mean(AR_BAND), np.mean(OSWALD_BAND), np.mean(CD0_BAND)))
    ld_lines = [round(ld_lo, 1), round(ld_nom, 1), round(ld_hi, 1)]
    best = ld_lines[-1]

    # --- glide feasibility: standing launch on both tracks ---
    winds = np.linspace(0.0, 14.0, 141)
    ranges, tflight = {}, {}
    for track in TRACKS:
        for ld in ld_lines:
            R, t, _ = fly(track, LAUNCH_H, winds, ridge_updraft(winds, slope),
                          MASS, WING_AREA, CL_TRIM, ld, site=site)
            ranges[(track, ld)] = R
            tflight[(track, ld)] = t
    tower_lo = fly("along_slope", 15.0, winds, ridge_updraft(winds, slope),
                   MASS, WING_AREA, CL_TRIM, best, site=site)[0]
    tower_hi = fly("along_slope", 25.0, winds, ridge_updraft(winds, slope),
                   MASS, WING_AREA, CL_TRIM, best, site=site)[0]

    # example trajectories (along-slope, best wing) and still air, to show the dive
    examples = {}
    for u in EXAMPLE_WINDS:
        *_, xs, zs = fly("along_slope", LAUNCH_H, u, ridge_updraft(u, slope),
                         MASS, WING_AREA, CL_TRIM, best, site=site, record=0)
        examples[u] = (xs, zs)
    *_, xs0, zs0 = fly("along_slope", LAUNCH_H, 0.0, 0.0, MASS, WING_AREA, CL_TRIM, best,
                       site=site, record=0)
    # height lost before reaching trim airspeed in still air: V^2/2g energy bound
    h_to_trim = (V**2 - V_JUMP**2) / (2 * G_ACCEL)
    # steady-glide (no launch transient) still-air range from the tower, for contrast
    still_steady = float(LAUNCH_H * best)

    np.savez_compressed(
        GLIDE, winds=winds, ld_lines=np.array(ld_lines),
        ranges_into=np.array([ranges[("into_wind", ld)] for ld in ld_lines]),
        ranges_slope=np.array([ranges[("along_slope", ld)] for ld in ld_lines]),
        tower_lo=tower_lo, tower_hi=tower_hi, target=TARGET_RANGE, slope=slope,
        example_winds=np.array(EXAMPLE_WINDS),
        example_x=np.array([np.pad(examples[u][0], (0, 20000 - len(examples[u][0])),
                                   constant_values=np.nan) for u in EXAMPLE_WINDS]),
        example_z=np.array([np.pad(examples[u][1], (0, 20000 - len(examples[u][1])),
                                   constant_values=np.nan) for u in EXAMPLE_WINDS]),
        still_x=xs0, still_z=zs0, contour=site.contour,
        lift_extent_slope=site.lift_extent["along_slope"],
        crude_band=np.array([ld_lo, ld_hi]))

    def tag(ld):
        return {ld_lines[0]: "low", ld_lines[1]: "nominal", ld_lines[2]: "high"}[ld]

    min_wind = {f"{tr}_{tag(ld)}": min_wind_for_target(winds, ranges[(tr, ld)])
                for tr in TRACKS for ld in ld_lines}
    max_range_into = float(max(np.max(ranges[("into_wind", ld)]) for ld in ld_lines))
    i8 = int(np.argmin(abs(winds - 8.0)))

    # --- tail verdict ---
    flight_time = float(tflight[("along_slope", best)][int(np.argmax(
        ranges[("along_slope", best)] >= TARGET_RANGE))])
    x_rep = float(np.mean(CG_PLAUSIBLE))
    t, th_nt = simulate_pitch(x_rep, np_nt, CMQ_NOTAIL, IYY, V)
    _, th_t = simulate_pitch(x_rep, np_t, CMQ_TAIL, IYY, V)
    over = np.where(np.abs(th_nt) >= CONTROL_LOSS_DEG)[0]
    t_loss = float(t[over[0]]) if over.size else None

    cg = np.linspace(0.20, 0.60, 120)

    def td_curve(x_np_, cmq_, iyy_):
        return np.array([time_to_double(growth_rate(x, x_np_, cmq_, iyy_, V)) for x in cg])
    td_nt = td_curve(np_nt, CMQ_NOTAIL, IYY)
    td_nt_lo = td_curve(np_nt, CMQ_NOTAIL, IYY * IYY_BAND[0])
    td_nt_hi = td_curve(np_nt, CMQ_NOTAIL, IYY * IYY_BAND[1])
    td_t = td_curve(np_t, CMQ_TAIL, IYY)
    td_band = td_nt[(cg >= CG_PLAUSIBLE[0]) & (cg <= CG_PLAUSIBLE[1])]
    td_band_lo = td_nt_lo[(cg >= CG_PLAUSIBLE[0]) & (cg <= CG_PLAUSIBLE[1])]
    td_band_hi = td_nt_hi[(cg >= CG_PLAUSIBLE[0]) & (cg <= CG_PLAUSIBLE[1])]

    np.savez_compressed(
        STAB, t=t, theta_notail=th_nt, theta_tail=th_t,
        cg=cg, td_notail=td_nt, td_notail_lo=td_nt_lo, td_notail_hi=td_nt_hi,
        td_tail=td_t, cg_plausible=np.array(CG_PLAUSIBLE),
        flight_time=flight_time, control_loss_deg=CONTROL_LOSS_DEG,
        np_notail=np_nt, np_tail=np_t, reaction_time=np.array(REACTION_TIME))

    metrics = {
        "inputs": {
            "mass_kg": MASS, "wing_area_m2": WING_AREA, "launch_h_m": LAUNCH_H,
            "cl_trim": CL_TRIM, "jump_speed_ms": V_JUMP,
            "glide_speed_ms": round(V, 1), "escarpment_slope_deg_p90": slope},
        "drag_polar": {
            "aspect_ratio": list(AR_BAND), "oswald_e": list(OSWALD_BAND),
            "cd0": list(CD0_BAND),
            "ld_max_band": [ld_lines[0], ld_lines[2]],
            "ld_max_nominal": ld_lines[1]},
        "site": {
            "lift_extent_into_wind_m": site.lift_extent["into_wind"],
            "lift_extent_along_slope_m": site.lift_extent["along_slope"],
            "along_slope_contour_m": site.contour,
            "valley_drop_sw_m": round(float(-np.min(site.profile[1][site.profile[0] <= 300])), 1)},
        "glide": {
            "ld_needed_still_air_steady": round(TARGET_RANGE / LAUNCH_H, 1),
            "height_to_trim_speed_still_air_m": round(float(h_to_trim), 1),
            "still_air_range_best_m": round(float(np.nanmax(xs0)), 0),
            "still_air_range_best_steady_m": round(still_steady, 0),
            "max_range_into_wind_m": round(max_range_into, 0),
            "min_wind_for_200m_ms": {k: (round(v, 1) if v is not None else None)
                                     for k, v in min_wind.items()},
            "range_at_8ms_along_slope_m": {
                tag(ld): round(float(ranges[("along_slope", ld)][i8]), 0) for ld in ld_lines},
            "range_at_8ms_into_wind_m": {
                tag(ld): round(float(ranges[("into_wind", ld)][i8]), 0) for ld in ld_lines},
            "min_wind_best_tower15_ms": round(min_wind_for_target(winds, tower_lo), 1),
            "min_wind_best_tower25_ms": round(min_wind_for_target(winds, tower_hi), 1)},
        "stability": {
            "np_notail": np_nt, "np_tail": np_t,
            "cg_plausible": list(CG_PLAUSIBLE), "representative_cg": round(x_rep, 2),
            "flight_time_s": round(flight_time, 1),
            "control_loss_deg": CONTROL_LOSS_DEG,
            "notail_time_to_control_loss_s": round(t_loss, 2) if t_loss else None,
            "notail_time_to_double_s": round(float(time_to_double(
                growth_rate(x_rep, np_nt, CMQ_NOTAIL, IYY, V))), 2),
            "notail_time_to_double_band_s": [round(float(np.min(td_band_lo)), 2),
                                             round(float(np.max(td_band_hi)), 2)],
            "notail_time_to_double_nominal_band_s": [round(float(np.min(td_band)), 2),
                                                     round(float(np.max(td_band)), 2)],
            "reaction_time_s": list(REACTION_TIME),
            "cg_divergence_onset": round(float(cg[np.argmax(np.isfinite(td_nt))]), 2),
            "notail_time_to_double_at_cg_fwd_s": round(float(np.interp(
                CG_PLAUSIBLE[0], cg, np.where(np.isfinite(td_nt), td_nt, 1e3))), 2),
            "notail_time_to_double_at_cg_aft_s": round(float(np.interp(
                CG_PLAUSIBLE[1], cg, np.where(np.isfinite(td_nt), td_nt, 1e3))), 2),
            "tail_stable_at_rep_cg": bool(growth_rate(x_rep, np_t, CMQ_TAIL, IYY, V) <= 1e-6)},
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
