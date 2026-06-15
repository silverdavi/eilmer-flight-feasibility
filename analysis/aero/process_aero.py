"""Workstream C processing: glide feasibility and the tail/control verdict.

Writes processed arrays + metrics.json for two figures:

Figure 4 (feasibility): with ridge lift over the SW escarpment, what glide ratio
does a 200 m flight demand, and does that fall within what a crude cambered wing
can deliver? Answered as range vs wind for several L/D, and required-L/D vs wind
against the hang-glider-class L/D band from the soaring literature.

Figure 5 (the tail verdict): a tailless hand/foot wing is statically unstable in
pitch across the CG a hanging pilot can reach. We integrate the pitch response to
a gust and show it departs in under a second, against a ~15 s flight; a tail
damps it. The divergence timescale is shown across the whole plausible CG band
with a sensitivity band on pitch inertia, so the claim does not rest on one
guessed constant.

Sources for constants in aero_overview.md and the paper. No plotting here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TERRAIN_METRICS = ROOT / "analysis" / "terrain" / "metrics.json"
GLIDE = ROOT / "data" / "processed" / "glide_curves.npz"
STAB = ROOT / "data" / "processed" / "stability_sim.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

# --- environment / apparatus (sources in aero_overview.md) ---
G_ACCEL = 9.81
RHO = 1.225
MASS = 80.0              # pilot + apparatus (kg)
WING_AREA = 7.0          # nominal (m^2); sweep 5-10 in Workstream F
CL_TRIM = 0.8            # glide trim lift coefficient
LAUNCH_H = 18.0          # tower height (m); White 1961, band 15-25
TOWER_BAND = (15.0, 25.0)
TARGET_RANGE = 200.0     # "more than a furlong" (m)
# ridge lift w = U sin(slope), first-order attached upslope (FAA; ERAU)
# crude cambered cloth wing: hang-glider class, L/D < 10, sink 0.75-2 m/s
CRUDE_LD_BAND = (3.0, 7.0)
LD_LINES = [3, 4, 5, 6, 7]

# --- stability model ---
ASPECT_RATIO = 4.0
XAC_WING = 0.25                  # tailless neutral point (fraction chord)
TAIL_NP_SHIFT = 0.28            # (a_t/a_w) V_H (1 - de/da) -> NP to 0.53 c
CMQ_NOTAIL, CMQ_TAIL = -1.5, -10.0
IYY = 30.0                      # pitch inertia (kg m^2), m k^2, k ~ 0.6 m
IYY_BAND = (0.5, 2.0)          # sensitivity multiplier on inertia
CG_PLAUSIBLE = (0.35, 0.55)    # hanging-pilot CG range (fraction chord)
GUST_ALPHA0 = np.deg2rad(8.0)   # initial AoA perturbation from a gust
CONTROL_LOSS_DEG = 60.0        # pitch attitude beyond which recovery is hopeless


def glide_speed(area=WING_AREA, cl=CL_TRIM):
    return float(np.sqrt(2 * MASS * G_ACCEL / (RHO * area * cl)))


def ground_range(ld, wind, slope_deg, h=LAUNCH_H, V=None):
    V = V or glide_speed()
    sin_g = 1.0 / np.sqrt(1.0 + ld**2)
    cos_g = ld / np.sqrt(1.0 + ld**2)
    sink = V * sin_g
    w = wind * np.sin(np.radians(slope_deg))
    net = sink - w
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(net > 0, V * cos_g * h / net, np.inf)


def required_ld(wind, slope_deg, h=LAUNCH_H):
    lds = np.linspace(1.5, 14, 600)
    out = np.full_like(wind, np.nan, dtype=float)
    for i, u in enumerate(wind):
        R = ground_range(lds, u, slope_deg, h)
        ok = R >= TARGET_RANGE
        out[i] = lds[np.argmax(ok)] if ok.any() else np.nan
    return out


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


def main() -> None:
    slope = json.loads(TERRAIN_METRICS.read_text())["slope_p90_deg"]
    V = glide_speed()
    np_nt, np_t = XAC_WING, XAC_WING + TAIL_NP_SHIFT

    # --- Figure 4 data ---
    winds = np.linspace(0, 14, 200)
    range_by_ld = {ld: ground_range(ld, winds, slope) for ld in LD_LINES}
    req_ld = required_ld(winds, slope)
    # tower-height uncertainty band on a representative L/D = 5
    r_lo = ground_range(5, winds, slope, h=TOWER_BAND[0])
    r_hi = ground_range(5, winds, slope, h=TOWER_BAND[1])
    # minimum wind that brings required L/D within the crude-wing band
    feas = req_ld <= CRUDE_LD_BAND[1]
    min_feasible_wind = float(winds[np.argmax(feas)]) if feas.any() else None

    np.savez_compressed(
        GLIDE, winds=winds, req_ld=req_ld, r_lo=r_lo, r_hi=r_hi,
        ld_lines=np.array(LD_LINES),
        ranges=np.array([range_by_ld[ld] for ld in LD_LINES]),
        crude_band=np.array(CRUDE_LD_BAND), target=TARGET_RANGE, slope=slope)

    # --- Figure 5 data ---
    flight_time = TARGET_RANGE / (V * 8 / np.sqrt(1 + 8**2))  # L/D~8 groundspeed
    x_rep = float(np.mean(CG_PLAUSIBLE))
    t, th_nt = simulate_pitch(x_rep, np_nt, CMQ_NOTAIL, IYY, V)
    _, th_t = simulate_pitch(x_rep, np_t, CMQ_TAIL, IYY, V)
    # time for no-tail to cross control-loss attitude
    over = np.where(np.abs(th_nt) >= CONTROL_LOSS_DEG)[0]
    t_loss = float(t[over[0]]) if over.size else None

    # divergence timescale vs CG, with inertia sensitivity band
    cg = np.linspace(0.20, 0.60, 120)
    def td_curve(x_np_, cmq_, iyy_):
        return np.array([time_to_double(growth_rate(x, x_np_, cmq_, iyy_, V)) for x in cg])
    td_nt = td_curve(np_nt, CMQ_NOTAIL, IYY)
    td_nt_lo = td_curve(np_nt, CMQ_NOTAIL, IYY * IYY_BAND[0])
    td_nt_hi = td_curve(np_nt, CMQ_NOTAIL, IYY * IYY_BAND[1])
    td_t = td_curve(np_t, CMQ_TAIL, IYY)

    np.savez_compressed(
        STAB, t=t, theta_notail=th_nt, theta_tail=th_t,
        cg=cg, td_notail=td_nt, td_notail_lo=td_nt_lo, td_notail_hi=td_nt_hi,
        td_tail=td_t, cg_plausible=np.array(CG_PLAUSIBLE),
        flight_time=flight_time, control_loss_deg=CONTROL_LOSS_DEG,
        np_notail=np_nt, np_tail=np_t)

    metrics = {
        "inputs": {
            "mass_kg": MASS, "wing_area_m2": WING_AREA, "launch_h_m": LAUNCH_H,
            "glide_speed_ms": round(V, 1), "escarpment_slope_deg_p90": slope,
            "crude_ld_band": list(CRUDE_LD_BAND)},
        "glide": {
            "ld_needed_still_air": round(TARGET_RANGE / LAUNCH_H, 1),
            "ld_needed_at_8ms": round(float(np.interp(8, winds, req_ld)), 1),
            "min_wind_for_crude_wing_ms": round(min_feasible_wind, 1) if min_feasible_wind else None},
        "stability": {
            "np_notail": np_nt, "np_tail": np_t,
            "cg_plausible": list(CG_PLAUSIBLE), "representative_cg": round(x_rep, 2),
            "flight_time_s": round(float(flight_time), 1),
            "control_loss_deg": CONTROL_LOSS_DEG,
            "notail_time_to_control_loss_s": round(t_loss, 2) if t_loss else None,
            "notail_time_to_double_s": round(float(time_to_double(growth_rate(x_rep, np_nt, CMQ_NOTAIL, IYY, V))), 2),
            "tail_stable_at_rep_cg": bool(growth_rate(x_rep, np_t, CMQ_TAIL, IYY, V) <= 1e-6)},
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
