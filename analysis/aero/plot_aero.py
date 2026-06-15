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
    band = wx["speed_band_ms"]
    crude = g["crude_band"]
    target = float(g["target"])

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- achievable range band for a crude wing (L/D 3-7) vs wind
    lds = [int(x) for x in g["ld_lines"]]
    r_low = np.clip(g["ranges"][lds.index(3)], 0, 600)   # L/D 3
    r_high = np.clip(g["ranges"][lds.index(7)], 0, 600)  # L/D 7
    r_mid = np.clip(g["ranges"][lds.index(5)], 0, 600)   # L/D 5
    axa.axvspan(band[0], band[1], color=PALETTE["gold"], alpha=0.16)
    axa.fill_between(winds, r_low, r_high, color=PALETTE["moss"], alpha=0.22)
    axa.plot(winds, r_mid, color=PALETTE["moss"], lw=2.2)
    axa.axhline(target, color=PALETTE["terracotta"], lw=1.6, ls="--")
    # mark where the achievable band first clears the target inside the wind band
    cross = winds[np.argmax(r_high >= target)]
    axa.axvspan(max(cross, band[0]), band[1], ymin=target / 600, color=PALETTE["moss"], alpha=0.10)
    axa.annotate("clears 200 m\nin the wind band",
                 (np.mean([max(cross, band[0]), band[1]]), 360), ha="center",
                 fontsize=8, color=PALETTE["moss"], fontweight="bold")
    axa.annotate("still air:\nfalls short", (0.4, 90), fontsize=8, color=PALETTE["slate"])
    axa.text(13.6, r_mid[-1], "L/D 5", color=PALETTE["moss"], fontsize=8, va="center")
    axa.text(13.6, r_high[-1] - 20, "L/D 7", color=PALETTE["moss"], fontsize=7, va="center", alpha=0.8)
    axa.text(13.6, r_low[-1], "L/D 3", color=PALETTE["moss"], fontsize=7, va="center", alpha=0.8)
    axa.text(0.4, target + 10, f"{target:.0f} m target", color=PALETTE["terracotta"], fontsize=8)
    axa.text(np.mean(band), 565, "favourable wind", ha="center", fontsize=8, color=PALETTE["ink"])
    axa.set_xlabel("SW wind speed (m/s)")
    axa.set_ylabel("ground range (m)")
    axa.set_title("A crude wing (L/D 3-7) reaches 200 m only with wind")
    axa.set_xlim(0, 14)
    axa.set_ylim(0, 600)
    panel_label(axa, "a")

    # b -- required L/D vs wind, against the crude-wing band
    axb.axhspan(crude[0], crude[1], color=PALETTE["moss"], alpha=0.16)
    axb.axvspan(band[0], band[1], color=PALETTE["gold"], alpha=0.14)
    axb.plot(winds, g["req_ld"], color=PALETTE["ink"], lw=2.2)
    axb.axhline(m["glide"]["ld_needed_still_air"], color=PALETTE["slate"], lw=1, ls=":")
    axb.text(9.5, m["glide"]["ld_needed_still_air"] + 0.2,
             f"still-air need L/D {m['glide']['ld_needed_still_air']:.1f}",
             fontsize=8, color=PALETTE["slate"])
    axb.text(11.6, np.mean(crude), "crude wing\nL/D 3-7", ha="center", va="center",
             fontsize=8, color=PALETTE["moss"])
    mw = m["glide"]["min_wind_for_crude_wing_ms"]
    axb.axvline(mw, color=PALETTE["terracotta"], lw=1.2, ls="--")
    axb.plot(mw, crude[1], "o", color=PALETTE["terracotta"], ms=6, mec="white")
    axb.annotate(f"feasible above\n{mw:.1f} m/s", (mw, crude[1]),
                 textcoords="offset points", xytext=(8, 14), fontsize=8,
                 color=PALETTE["terracotta"])
    axb.set_xlabel("SW wind speed (m/s)")
    axb.set_ylabel("glide ratio required for 200 m")
    axb.set_title("Required glide performance vs wind")
    axb.set_xlim(0, 14)
    axb.set_ylim(0, 12)
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
    axa.annotate(f"intended flight lasts ~{flight:.0f} s",
                 (xmax, 8), ha="right", va="center", fontsize=8.5, color=PALETTE["ink"],
                 arrowprops=dict(arrowstyle="-|>", color=PALETTE["ink"], lw=1),
                 xytext=(-90, 0), textcoords="offset points")
    axa.set_xlabel("time after gust (s)")
    axa.set_ylabel("pitch attitude (deg)")
    axa.set_title("No tail: departs in under a second")
    axa.set_xlim(0, xmax)
    axa.set_ylim(-20, 110)
    axa.legend(loc="center left", fontsize=9)
    panel_label(axa, "a")

    # b -- divergence timescale across the plausible CG band
    axb.axhspan(0.05, flight, color=PALETTE["terracotta"], alpha=0.06)
    axb.axvspan(cgp[0], cgp[1], color=PALETTE["slate"], alpha=0.18)
    axb.axhline(flight, color=PALETTE["ink"], lw=1, ls="--")
    axb.text(0.205, flight * 1.18, f"flight duration ~{flight:.0f} s", fontsize=8, color=PALETTE["ink"])
    axb.text(0.205, 0.13, "departs before landing", fontsize=8, color=PALETTE["terracotta"])
    nt, lo, hi = s["td_notail"], s["td_notail_lo"], s["td_notail_hi"]
    fin = np.isfinite(nt)
    axb.fill_between(cg[fin], np.clip(lo[fin], 1e-3, 1e3), np.clip(hi[fin], 1e-3, 1e3),
                     color=PALETTE["terracotta"], alpha=0.2)
    axb.plot(cg[fin], nt[fin], color=PALETTE["terracotta"], lw=2.2, label="no tail")
    tt = s["td_tail"]
    ftt = np.isfinite(tt)
    if ftt.any():
        axb.plot(cg[ftt], tt[ftt], color=PALETTE["dustyblue"], lw=2.2, label="with tail")
    axb.text(np.mean(cgp), 0.065, "plausible\nhanging CG", ha="center", fontsize=8, color=PALETTE["ink"])
    axb.text(0.49, 25, "with tail: stable\n(no divergence)", fontsize=8, color=PALETTE["dustyblue"])
    axb.set_yscale("log")
    axb.set_xlabel("centre of gravity (fraction of chord)")
    axb.set_ylabel("time to double pitch error (s)")
    axb.set_title("Tailless craft diverges far faster than it can fly")
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
