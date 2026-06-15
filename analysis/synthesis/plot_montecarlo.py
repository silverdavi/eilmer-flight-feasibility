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


def main() -> None:
    set_style()
    d = np.load(MC)
    R = d["R"]
    target = float(d["target"])
    m = json.loads(METRICS.read_text())

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- distribution of achievable ground range
    disp = np.clip(R, 0, 500)
    bins = np.linspace(0, 500, 51)
    axa.hist(disp[disp < target], bins=bins, color=PALETTE["slate"], alpha=0.7)
    axa.hist(disp[disp >= target], bins=bins, color=PALETTE["moss"], alpha=0.85)
    axa.axvline(target, color=PALETTE["terracotta"], lw=1.8, ls="--")
    med = m["median_range_m"]
    axa.axvline(med, color=PALETTE["ink"], lw=1.2, ls=":")
    pr = m["p_reach_200m"]
    axa.text(target + 8, axa.get_ylim()[1] * 0.92,
             f"{pr[0]*100:.0f}% reach 200 m\n[{pr[1]*100:.0f}, {pr[2]*100:.0f}]",
             color=PALETTE["moss"], fontsize=9)
    axa.text(med - 8, axa.get_ylim()[1] * 0.62, f"median {med:.0f} m",
             color=PALETTE["ink"], fontsize=8, ha="right")
    axa.text(target + 8, axa.get_ylim()[1] * 0.52, "200 m target", color=PALETTE["terracotta"], fontsize=8)
    axa.set_xlabel("ground range (m, capped at 500)")
    axa.set_ylabel("sampled worlds")
    axa.set_title("A quarter of plausible worlds reach 200 m")
    axa.set_xlim(0, 500)
    panel_label(axa, "a")

    # b -- why the fate flips: the timescale of pitch divergence vs the flight.
    # Among reached flights, tailless pitch error doubles in a fraction of a
    # second, while the flight must stay controlled for ~20 s; tailed configs are
    # stable (never diverge), shown as an off-scale annotation.
    reached = d["reached"]
    t2_nt = d["t2_notail"][reached]
    ft = d["flight_time"][reached]
    t2_nt = t2_nt[np.isfinite(t2_nt)]
    bins = np.logspace(-1, 2, 40)
    axb.set_xscale("log")
    axb.hist(t2_nt, bins=bins, color=PALETTE["terracotta"], alpha=0.85,
             label="no tail: time to lose pitch control")
    axb.hist(ft, bins=bins, color=PALETTE["moss"], alpha=0.6,
             label="flight duration (time it must stay controlled)")
    med_t2 = float(np.median(t2_nt))
    med_ft = float(np.median(ft))
    axb.axvline(med_t2, color=PALETTE["terracotta"], lw=1.2, ls="--")
    axb.axvline(med_ft, color=PALETTE["moss"], lw=1.2, ls="--")
    ytop = axb.get_ylim()[1]
    axb.annotate("", xy=(med_ft, ytop * 0.82), xytext=(med_t2, ytop * 0.82),
                 arrowprops=dict(arrowstyle="<->", color=PALETTE["ink"], lw=1.1))
    axb.text(np.sqrt(med_t2 * med_ft), ytop * 0.86,
             f"~{med_ft/med_t2:.0f}x too slow\nto react", ha="center", va="bottom",
             fontsize=8.5, color=PALETTE["ink"])
    axb.text(med_t2, ytop * 0.5, f"  median {med_t2:.2f} s\n  (control lost after ~3 m)",
             color=PALETTE["terracotta"], fontsize=8, va="center")
    axb.text(med_ft, ytop * 0.32, f"median {med_ft:.0f} s  ", color=PALETTE["moss"],
             fontsize=8, va="center", ha="right")
    axb.text(0.5, 0.5, "with a tail: every reaching\nconfiguration is stable\n(never diverges)",
             transform=axb.transAxes, ha="center", va="center", fontsize=8,
             color=PALETTE["dustyblue"], fontweight="bold")
    axb.set_xlabel("time (s, log scale)")
    axb.set_ylabel("reached flights")
    axb.set_title("Tailless pitch diverges far faster than the flight lasts")
    axb.set_xlim(0.1, 100)
    axb.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=1, fontsize=8)
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig6_montecarlo")


if __name__ == "__main__":
    main()
