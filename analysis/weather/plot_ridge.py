"""Workstream B, Figure 3: ridge-lift field over the escarpment.

Reads ridge_field.npz + ridge_metrics.json; writes figures/fig3_ridge_lift.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "config"))
from plot_utils import PALETTE, panel_label, save_fig, set_style  # noqa: E402

FIELD = ROOT / "data" / "processed" / "ridge_field.npz"
METRICS = Path(__file__).resolve().parent / "ridge_metrics.json"

# diverging map: descending air (blue) - neutral (white) - rising air (terracotta)
LIFT_CMAP = LinearSegmentedColormap.from_list(
    "lift", [PALETTE["dustyblue"], "#f4eee4", PALETTE["terracotta"]])


def main() -> None:
    set_style()
    f = np.load(FIELD)
    x, z, W = f["x"], f["z"], f["W"]
    terrain = f["terrain_rel"]
    U = float(f["U"]); sink_band = f["sink_band"]
    m = json.loads(METRICS.read_text())

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.5, 4.8),
                                   gridspec_kw={"width_ratios": [2.4, 1]})

    # a -- vertical-velocity field
    norm = TwoSlopeNorm(vmin=-2, vcenter=0, vmax=2)
    pcm = axa.contourf(x, z, W, levels=np.linspace(-2, 2, 21), cmap=LIFT_CMAP,
                       norm=norm, extend="both")
    # soarable boundary: w == optimistic sink
    cs = axa.contour(x, z, W, levels=[sink_band[0]], colors=[PALETTE["ink"]],
                     linewidths=1.2, linestyles="--")
    axa.clabel(cs, fmt=f"w = {sink_band[0]:.2f} m/s", fontsize=7)
    # terrain body
    axa.fill_between(x, terrain.min() - 5, terrain, color=PALETTE["shade"], zorder=3)
    axa.plot(x, terrain, color=PALETTE["ink"], lw=1.2, zorder=4)
    # streamlines
    for zs in f["streams"]:
        axa.plot(x, zs, color=PALETTE["slate"], lw=0.7, alpha=0.7, zorder=3.5)
    # launch tower at abbey (x = 0)
    t0 = float(np.interp(0, x, terrain))
    axa.plot([0, 0], [t0, t0 + 18], color=PALETTE["moss"], lw=2.5, zorder=5)
    axa.plot(0, t0 + 18, "v", color=PALETTE["moss"], ms=8, zorder=5)
    axa.annotate("launch", (0, t0 + 18), textcoords="offset points", xytext=(6, 2),
                 fontsize=8, color=PALETTE["moss"], zorder=5)
    axa.annotate("", xy=(x.min() + 270, 132), xytext=(x.min() + 40, 132),
                 arrowprops=dict(arrowstyle="-|>", color=PALETTE["ink"], lw=1.4))
    axa.text(x.min() + 40, 137, "SW wind", fontsize=9, color=PALETTE["ink"])
    axa.set_xlabel("distance along SW-NE section (m)")
    axa.set_ylabel("height above SW baseline (m)")
    axa.set_title("SW wind lifts air over the windward face")
    axa.set_xlim(x.min(), x.max())
    axa.set_ylim(terrain.min() - 5, z.max())
    cb = fig.colorbar(pcm, ax=axa, pad=0.02)
    cb.set_label("vertical air velocity w (m/s)")
    cb.ax.tick_params(labelsize=8)
    panel_label(axa, "a", dx=-0.04)

    # b -- best lift vs height against the crude-glider sink band
    axb.axvspan(sink_band[0], sink_band[1], color=PALETTE["slate"], alpha=0.18)
    axb.plot(f["w_best_vs_z"], z, color=PALETTE["terracotta"], lw=2.4)
    depth = m["soarable_layer_depth_m_at_sink1"]
    axb.axhline(depth, color=PALETTE["ink"], lw=1, ls=":")
    axb.text(0.05, depth + 4, f"working band ~{depth:.0f} m", fontsize=8, color=PALETTE["ink"])
    axb.text(np.mean(sink_band), z.max() * 0.86, "crude-glider\nsink 0.75-2 m/s",
             ha="center", fontsize=8, color=PALETTE["ink"])
    axb.set_xlabel("vertical velocity w (m/s)")
    axb.set_ylabel("height above baseline (m)")
    axb.set_title("Lift vs height on the\nwindward face")
    axb.set_ylim(0, z.max())
    axb.set_xlim(0, max(2.2, float(np.nanmax(f["w_best_vs_z"])) * 1.1))
    panel_label(axb, "b")

    fig.tight_layout()
    save_fig(fig, "fig3_ridge_lift")


if __name__ == "__main__":
    main()
