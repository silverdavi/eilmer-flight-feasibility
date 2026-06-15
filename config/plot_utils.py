"""Shared figure style for the Eilmer feasibility study.

One source of truth for palette, fonts, and saving. Figure scripts import from
here and never set rcParams or hex inline (Rules/FIGURES.md). Canvas carries
data only; interpretation lives in captions and overview docs.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

from brand import COLORS, FONT_STACK, SEQUENTIAL  # central source of truth

ROOT = Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "figures"

# Palette for figure scripts (keys preserved for backward compatibility).
PALETTE = COLORS


def set_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FONT_STACK,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "figure.dpi": 110,
        "savefig.bbox": "tight",
    })


def panel_label(ax, letter: str, dx: float = -0.02, dy: float = 1.04) -> None:
    """Bold lower-case panel label, top-left, Nature style."""
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=13,
            fontweight="bold", va="bottom", ha="right")


def save_fig(fig, name: str) -> None:
    """Write both manuscript PDF and 300-dpi review PNG."""
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.pdf")
    fig.savefig(FIGDIR / f"{name}.png", dpi=300)
    print(f"saved figures/{name}.pdf and .png")
