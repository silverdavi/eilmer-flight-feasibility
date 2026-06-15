"""Central brand for the Eilmer study: fonts and colours, one source of truth.

Pure Python (no matplotlib) so both the paper figures (via plot_utils) and the
SVG/3D viz compositions can import it cheaply. Change a colour or the font here
and every figure follows.
"""
from __future__ import annotations

# --- type ---
FONT_STACK = ["TeX Gyre Heros", "Helvetica Neue", "Arial", "IBM Plex Sans", "DejaVu Sans"]
FONT_CSS = ", ".join(FONT_STACK + ["sans-serif"])

# --- palette (warm archival, light background). Colour encodes meaning. ---
COLORS = {
    "ink": "#2b2b2b",
    "slate": "#6b6b6b",
    "parchment": "#faf6ee",
    "terracotta": "#b5553a",
    "dustyblue": "#5b7fa6",
    "moss": "#6f8a4f",
    "gold": "#cf9b3f",
    "shade": "#e7dfd2",
    "willow": "#8a6d4f",   # wood frame
    "cloth": "#cdb6a4",    # membrane
}

# --- semantic roles map to palette names, so meaning stays consistent ---
ROLES = {
    "structure": "willow",
    "membrane": "slate",
    "pilot": "moss",
    "danger": "terracotta",   # the missing tail, the crash
    "stable": "dustyblue",    # the tailed counterfactual
    "accent": "gold",
}

SEQUENTIAL = "cividis"        # ordered strata; colour-blind safe


def c(name: str) -> str:
    """Colour by palette name."""
    return COLORS[name]


def role(name: str) -> str:
    """Colour by semantic role."""
    return COLORS[ROLES[name]]
