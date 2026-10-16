"""Workstream C figures: glide feasibility (Figure 4) and tail verdict (Figure 5).

Reads processed arrays + metrics.json; numbers on the canvas come from the JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "config"))
from plot_utils import PALETTE, SEQUENTIAL, panel_label, save_fig, set_style  # noqa: E402

GLIDE = ROOT / "data" / "processed" / "glide_curves.npz"
STAB = ROOT / "data" / "processed" / "stability_sim.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"
WEATHER = ROOT / "analysis" / "weather" / "metrics.json"


def fig_feasibility(m, wx):
    set_style()
    g = np.load(GLIDE)
    winds = g["winds"]
    target = float(g["target"])
    lds = [float(x) for x in g["ld_lines"]]
    ymax = 400

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- range of a standing launch vs wind, both tracks, three glide ratios
    shades = [PALETTE["slate"], PALETTE["moss"], PALETTE["dustyblue"]]
    axa.fill_between(winds, np.clip(g["tower_lo"], 0, ymax), np.clip(g["tower_hi"], 0, ymax),
                     color=shades[2], alpha=0.15, lw=0)
    for ld, rs, ri, c in zip(lds, g["ranges_slope"], g["ranges_into"], shades):
        axa.plot(winds, np.clip(rs, 0, ymax), color=c, lw=2.2, label=f"along slope, L/D {ld:.1f}")
        axa.plot(winds, np.clip(ri, 0, ymax), color=c, lw=1.6, ls="--",
                 label=f"into wind, L/D {ld:.1f}")
    axa.axhline(target, color=PALETTE["terracotta"], lw=1.4, ls=":")
    axa.text(0.3, target + 6, f"{target:.0f} m", color=PALETTE["terracotta"], fontsize=8)
    axa.set_xlabel("SW wind speed at launch (m/s)")
    axa.set_ylabel("ground range (m)")
    axa.set_title("Range of a standing launch from the tower")
    axa.set_xlim(0, 14)
    axa.set_ylim(0, ymax)
    axa.legend(loc="upper left", fontsize=7.5, ncol=2)
    panel_label(axa, "a")

    # b -- trajectories: the launch dive, along the slope, best wing
    best = lds[-1]
    contour = float(g["contour"])
    axb.axhline(contour, color=PALETTE["ink"], lw=1.2)
    axb.text(2, contour - 1.6, "landing contour (mid-slope)", fontsize=8, color=PALETTE["ink"])
    axb.axhline(0, color=PALETTE["slate"], lw=0.8, ls=":")
    axb.text(2, 0.6, "abbey ground level", fontsize=8, color=PALETTE["slate"])
    axb.plot(g["still_x"], g["still_z"], color=PALETTE["slate"], lw=2, label="still air")
    ramp = [PALETTE["gold"], PALETTE["moss"], PALETTE["dustyblue"]]
    for u, xs, zs, c in zip(g["example_winds"], g["example_x"], g["example_z"], ramp):
        ok = np.isfinite(xs)
        axb.plot(xs[ok], zs[ok], color=c, lw=2, label=f"{u:.0f} m/s")
    axb.axvline(target, color=PALETTE["terracotta"], lw=1.4, ls=":")
    axb.axvline(float(g["lift_extent_slope"]), color=PALETTE["slate"], lw=0.8, ls="--")
    axb.text(float(g["lift_extent_slope"]) - 3, 27, "end of\nSW-facing slope", fontsize=7.5,
             color=PALETTE["slate"], ha="right")
    axb.set_xlabel("ground distance along the slope (m)")
    axb.set_ylabel("height above abbey ground (m)")
    axb.set_title(f"Standing launch, L/D {best:.1f}, along the slope")
    axb.set_xlim(0, 320)
    axb.set_ylim(contour - 3, 32)
    axb.legend(loc="upper right", fontsize=8, title="launch wind", title_fontsize=8)
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig4_glide_envelope")


def fig_tail(m):
    set_style()
    s = np.load(STAB)
    t = s["t"]
    flight = float(s["flight_time"])
    loss = float(s["control_loss_deg"])
    cg = s["cg"]
    cgp = s["cg_plausible"]

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- pitch response to a gust (zoomed to the first seconds, where it happens)
    xmax = 5.0
    axa.axhspan(loss, 110, color=PALETTE["terracotta"], alpha=0.08)
    axa.axhline(loss, color=PALETTE["terracotta"], lw=0.9, ls=":")
    axa.plot(t, s["theta_notail"], color=PALETTE["terracotta"], lw=2.4, label="no tail")
    axa.plot(t, s["theta_tail"], color=PALETTE["dustyblue"], lw=2.4, label="with tail")
    tl = m["stability"]["notail_time_to_control_loss_s"]
    axa.axvline(tl, color=PALETTE["terracotta"], lw=0.9, ls="--")
    axa.annotate(f"control lost at {tl:.2f} s", (tl, loss),
                 textcoords="offset points", xytext=(20, -22), fontsize=8.5,
                 color=PALETTE["terracotta"], fontweight="bold",
                 arrowprops=dict(arrowstyle="-|>", color=PALETTE["terracotta"], lw=1))
    axa.text(xmax * 0.98, loss + 4, f"loss-of-control attitude ({loss:.0f} deg)",
             ha="right", fontsize=8, color=PALETTE["terracotta"])
    axa.set_xlabel("time after gust (s)")
    axa.set_ylabel("pitch attitude (deg)")
    axa.set_title("Pitch response to an 8 deg gust")
    axa.set_xlim(0, xmax)
    axa.set_ylim(-20, 110)
    axa.legend(loc="center left", fontsize=9)
    panel_label(axa, "a")

    # b -- divergence timescale across the CG band, against flight time and reaction time
    rt = s["reaction_time"]
    axb.axvspan(cgp[0], cgp[1], color=PALETTE["slate"], alpha=0.18)
    axb.axhspan(rt[0], rt[1], color=PALETTE["gold"], alpha=0.25)
    axb.text(0.205, rt[1] * 1.08, f"human reaction time {rt[0]:.2f}-{rt[1]:.1f} s",
             fontsize=8, color=PALETTE["ink"])
    axb.axhline(flight, color=PALETTE["ink"], lw=1, ls="--")
    axb.text(0.205, flight * 1.18, f"200 m flight lasts {flight:.0f} s", fontsize=8, color=PALETTE["ink"])
    axb.axvline(float(s["np_notail"]), color=PALETTE["terracotta"], lw=0.8, ls=":")
    axb.text(float(s["np_notail"]) + 0.005, 60, "tailless\nneutral point", fontsize=7.5,
             color=PALETTE["terracotta"])
    nt, lo, hi = s["td_notail"], s["td_notail_lo"], s["td_notail_hi"]
    fin = np.isfinite(nt)
    axb.fill_between(cg[fin], np.clip(lo[fin], 1e-3, 1e3), np.clip(hi[fin], 1e-3, 1e3),
                     color=PALETTE["terracotta"], alpha=0.2)
    axb.plot(cg[fin], nt[fin], color=PALETTE["terracotta"], lw=2.2, label="no tail")
    tt = s["td_tail"]
    ftt = np.isfinite(tt)
    if ftt.any():
        axb.plot(cg[ftt], tt[ftt], color=PALETTE["dustyblue"], lw=2.2, label="with tail")
    axb.text(np.mean(cgp), 0.065, "pilot CG range", ha="center", fontsize=8, color=PALETTE["ink"])
    axb.text(0.49, 25, "with tail: stable\n(no divergence)", fontsize=8, color=PALETTE["dustyblue"])
    axb.set_yscale("log")
    axb.set_xlabel("centre of gravity (fraction of chord)")
    axb.set_ylabel("time to double pitch error (s)")
    axb.set_title("Pitch divergence time vs centre of gravity")
    axb.set_xlim(cg.min(), cg.max())
    axb.set_ylim(0.05, 100)
    axb.legend(loc="upper right", fontsize=8)
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig5_stability")


def main() -> None:
    m = json.loads(METRICS.read_text())
    wx = json.loads(WEATHER.read_text())
    fig_feasibility(m, wx)
    fig_tail(m)


if __name__ == "__main__":
    main()
