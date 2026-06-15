"""Workstream B figure: wind feasibility (Figure 2).

Reads wind_rose.npz and metrics.json; produces figures/fig2_wind.
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

ROSE = ROOT / "data" / "processed" / "wind_rose.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]


def main() -> None:
    set_style()
    r = np.load(ROSE, allow_pickle=True)
    mat = r["matrix"]
    labels = [str(x) for x in r["speed_labels"]]
    sec_lo, sec_hi = float(r["sector_lo"]), float(r["sector_hi"])
    m = json.loads(METRICS.read_text())

    fig = plt.figure(figsize=(12, 5.4))

    # a -- wind rose
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    n = mat.shape[0]
    theta = np.deg2rad(np.arange(0, 360, 360 / n))
    width = 2 * np.pi / n * 0.92
    colors = plt.get_cmap(SEQUENTIAL)(np.linspace(0.1, 0.95, len(labels)))
    bottom = np.zeros(n)
    for j, lab in enumerate(labels):
        ax.bar(theta, mat[:, j], width=width, bottom=bottom, color=colors[j],
               edgecolor="white", linewidth=0.3, label=f"{lab} m/s")
        bottom += mat[:, j]
    sw_mid = np.deg2rad((sec_lo + sec_hi) / 2)
    ax.bar(sw_mid, bottom.max() * 1.03, width=np.deg2rad(sec_hi - sec_lo),
           bottom=0, color=PALETTE["terracotta"], alpha=0.12, zorder=0)
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)))
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    ax.set_rlabel_position(112)
    ax.set_title("Wind rose, frequency (%)", pad=14)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, fontsize=8)
    panel_label(ax, "a", dx=-0.06, dy=1.08)

    # b -- seasonal favourability with interannual 95% CI
    ax2 = fig.add_subplot(1, 2, 2)
    means = [m["favourable_pct_by_season"][s]["mean"] for s in SEASON_ORDER]
    los = [m["favourable_pct_by_season"][s]["ci95"][0] for s in SEASON_ORDER]
    his = [m["favourable_pct_by_season"][s]["ci95"][1] for s in SEASON_ORDER]
    err = [np.array(means) - np.array(los), np.array(his) - np.array(means)]
    x = np.arange(len(SEASON_ORDER))
    ax2.bar(x, means, color=PALETTE["dustyblue"], width=0.62)
    ax2.errorbar(x, means, yerr=err, fmt="none", ecolor=PALETTE["ink"], capsize=4, lw=1.2)
    ann = m["favourable_pct_annual"]
    ax2.axhline(ann["mean"], color=PALETTE["terracotta"], lw=1.4, ls="--")
    ax2.text(3.45, ann["mean"], f"annual {ann['mean']:.1f}%\n[{ann['ci95'][0]:.1f}, {ann['ci95'][1]:.1f}]",
             va="center", ha="left", fontsize=8, color=PALETTE["terracotta"])
    for xi, mu in zip(x, means):
        ax2.text(xi, mu + 0.4, f"{mu:.1f}", ha="center", fontsize=9, color=PALETTE["ink"])
    ax2.set_xticks(x)
    ax2.set_xticklabels(SEASON_ORDER)
    ax2.set_xlabel("season")
    ax2.set_ylabel("favourable hours (% of season)")
    ax2.set_title("Favourable launch conditions by season")
    ax2.set_xlim(-0.6, 4.4)
    ax2.set_ylim(0, max(his) * 1.2)
    panel_label(ax2, "b")

    fig.tight_layout()
    save_fig(fig, "fig2_wind")


if __name__ == "__main__":
    main()
