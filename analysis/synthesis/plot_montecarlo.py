"""Workstream F figure: Monte Carlo feasibility envelope (Figure 6).

Reads montecarlo.npz + metrics.json; writes figures/fig6_montecarlo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "config"))
from plot_utils import PALETTE, panel_label, save_fig, set_style  # noqa: E402

MC = ROOT / "data" / "processed" / "montecarlo.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"
AERO = ROOT / "analysis" / "aero" / "metrics.json"


def main() -> None:
    set_style()
    d = np.load(MC)
    target = float(d["target"])
    m = json.loads(METRICS.read_text())
    rt = json.loads(AERO.read_text())["stability"]["reaction_time_s"]

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- distribution of ground range, both tracks
    bins = np.linspace(0, 400, 41)
    Rs = np.clip(d["R_along_slope"], 0, 400)
    Ri = np.clip(d["R_into_wind"], 0, 400)
    axa.hist(Ri, bins=bins, color=PALETTE["slate"], alpha=0.55, label="into wind")
    axa.hist(Rs, bins=bins, color=PALETTE["moss"], alpha=0.6, label="along slope")
    axa.axvline(target, color=PALETTE["terracotta"], lw=1.6, ls=":")
    top = axa.get_ylim()[1]
    for key, col, y in (("along_slope", PALETTE["moss"], 0.9), ("into_wind", PALETTE["slate"], 0.74)):
        p = m["tracks"][key]["p_reach_200m"]
        n_reach = m["tracks"][key]["n_reach_200m"]
        label = (f"{p[0]*100:.1f}% reach 200 m\n[{p[1]*100:.1f}, {p[2]*100:.1f}]" if n_reach
                 else f"none of {m['n_samples']:,}\nreach 200 m")
        axa.text(target + 8, top * y, label, color=col, fontsize=8.5)
    axa.set_xlabel("ground range (m, capped at 400)")
    axa.set_ylabel(f"samples (of {int(d['n']):,})")
    axa.set_title("Ground range over the sampled designs and days")
    axa.set_xlim(0, 400)
    axa.legend(loc="center right", fontsize=8.5)
    panel_label(axa, "a")

    # b -- tailless pitch doubling time vs flight duration, flights that reach 200 m
    reached = d["reached_along_slope"]
    t2 = d["t2_notail"][reached]
    t2 = t2[np.isfinite(t2)]
    ft = d["t_flight_along_slope"][reached]
    bins = np.logspace(-1.3, 2.2, 45)
    axb.set_xscale("log")
    axb.axvspan(rt[0], rt[1], color=PALETTE["gold"], alpha=0.25, lw=0)
    axb.hist(t2, bins=bins, color=PALETTE["terracotta"], alpha=0.85,
             label="no tail: time to double pitch error")
    axb.hist(ft, bins=bins, color=PALETTE["moss"], alpha=0.6, label="flight duration")
    ytop = axb.get_ylim()[1]
    axb.text(np.sqrt(rt[0] * rt[1]), ytop * 0.95, "human\nreaction\ntime", ha="center",
             va="top", fontsize=7.5, color=PALETTE["ink"])
    med_t2 = m["notail_t2_median_reached_s"]
    med_ft = m["tracks"]["along_slope"]["median_flight_time_reached_s"]
    axb.axvline(med_t2, color=PALETTE["terracotta"], lw=1.1, ls="--")
    axb.axvline(med_ft, color=PALETTE["moss"], lw=1.1, ls="--")
    axb.text(med_t2 * 1.08, ytop * 0.55, f"median {med_t2:.2f} s", color=PALETTE["terracotta"], fontsize=8)
    axb.text(med_ft * 0.93, ytop * 0.55, f"median {med_ft:.0f} s", color=PALETTE["moss"],
             fontsize=8, ha="right")
    axb.set_xlabel("time (s, log scale)")
    axb.set_ylabel("flights reaching 200 m along the slope")
    axb.set_title("Pitch doubling time and flight duration")
    axb.set_xlim(10**-1.3, 10**2.2)
    axb.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8)
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig6_montecarlo")


if __name__ == "__main__":
    main()
