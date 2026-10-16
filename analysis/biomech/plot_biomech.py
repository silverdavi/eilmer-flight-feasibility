"""Workstream E figure: impact biomechanics, the broken-legs constraint (Figure 7).

Reads biomech.npz + metrics.json; writes figures/fig7_biomech.
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

DATA = ROOT / "data" / "processed" / "biomech.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"


def main() -> None:
    set_style()
    d = np.load(DATA)
    m = json.loads(METRICS.read_text())
    f_lo, f_hi = d["f_leg_band"] / 1e3   # kN per leg

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12, 5.0))

    # a -- per-leg force vs impact speed, for stopping distances
    v = d["v_axis"]
    dists = d["curves_keys"]
    curves = d["curves"] / 1e3   # kN per leg
    shades = [PALETTE["dustyblue"], PALETTE["moss"], PALETTE["gold"]]
    for di, (dd, c) in enumerate(zip(dists, curves)):
        axa.plot(v, c, color=shades[di], lw=2, label=f"stop {dd*100:.0f} cm")
    axa.axhspan(f_lo, f_hi, color=PALETTE["terracotta"], alpha=0.18)
    axa.axhline(f_lo, color=PALETTE["terracotta"], lw=1, ls="--")
    axa.text(13.2, (f_lo + f_hi) / 2, "tibia fracture\n7.5-11.3 kN", color=PALETTE["terracotta"],
             fontsize=8, va="center", ha="center")
    axa.set_xlabel("impact vertical speed (m/s)")
    axa.set_ylabel("average force per leg (kN)")
    axa.set_title("Feet-first impact force per leg")
    axa.set_xlim(0, 15)
    axa.set_ylim(0, 22)
    axa.legend(loc="center left", fontsize=8)
    panel_label(axa, "a")

    # b -- impact-speed distributions vs fracture-onset band
    controlled = d["controlled_vz"]
    depart = d["depart_vz"]
    bins = np.linspace(0, 18, 46)
    axb.hist(controlled, bins=bins, color=PALETTE["moss"], alpha=0.75, density=True,
             label="controlled glide, no flare")
    axb.hist(depart, bins=bins, color=PALETTE["terracotta"], alpha=0.7, density=True,
             label="loss of pitch control")
    # fracture-onset band across plausible stopping distance
    vstar_lo = float(np.min(d["v_star_lo"][(d["d_axis"] >= 0.1) & (d["d_axis"] <= 0.35)]))
    vstar_hi = float(np.max(d["v_star_hi"][(d["d_axis"] >= 0.1) & (d["d_axis"] <= 0.35)]))
    axb.axvspan(vstar_lo, vstar_hi, color=PALETTE["ink"], alpha=0.12)
    axb.axvline(m["fracture_onset_speed_mid_ms"], color=PALETTE["ink"], lw=1.4, ls="--")
    ymax = axb.get_ylim()[1]
    axb.text(m["fracture_onset_speed_mid_ms"] - 0.3, ymax * 0.78,
             "fracture onset\n(legs break\nto the right)", color=PALETTE["ink"], fontsize=8,
             ha="right")
    pb = m["p_legs_break_if_departed"]
    axb.text(13.5, ymax * 0.45, f"{pb*100:.0f}% exceed\nfracture onset",
             color=PALETTE["terracotta"], fontsize=8, ha="center")
    axb.set_xlabel("impact vertical speed (m/s)")
    axb.set_ylabel("probability density")
    axb.set_title(f"Arrival speeds of the {m['n_reached_samples']:,} flights reaching 200 m")
    axb.set_xlim(0, 18)
    axb.legend(loc="upper right", fontsize=8)
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig7_biomech")


if __name__ == "__main__":
    main()
