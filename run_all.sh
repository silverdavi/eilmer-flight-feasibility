#!/usr/bin/env bash
# Rebuild every processed table and figure from raw data, in order.
# Usage: ./run_all.sh   (uses the project uv venv at .venv)
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

echo "== Workstream A: terrain =="
$PY analysis/terrain/fetch_dem.py        # comment out after first run (cached)
$PY analysis/terrain/process_terrain.py
$PY analysis/terrain/plot_terrain.py

echo "== Workstream B: weather =="
$PY analysis/weather/fetch_wind.py       # comment out after first run (cached)
$PY analysis/weather/process_weather.py
$PY analysis/weather/plot_weather.py
$PY analysis/weather/process_ridge.py    # Fig 3 (needs terrain_section.npz)
$PY analysis/weather/plot_ridge.py

echo "== Workstream C: aerodynamics =="
$PY analysis/aero/process_aero.py
$PY analysis/aero/plot_aero.py

echo "== Workstream F: Monte Carlo synthesis =="
$PY analysis/synthesis/process_montecarlo.py
$PY analysis/synthesis/plot_montecarlo.py

echo "== Workstream E: impact biomechanics =="
$PY analysis/biomech/process_biomech.py  # Fig 7 (needs montecarlo.npz)
$PY analysis/biomech/plot_biomech.py

echo "== Manuscript: compile LaTeX (needs TeX Live + biber) =="
if command -v latexmk >/dev/null 2>&1; then
  (cd paper_source && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex)
else
  echo "latexmk not found; skipping paper build"
fi

echo "== done: see figures/ and paper_source/main.pdf =="
