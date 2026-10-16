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

if [ -d viz ]; then
  echo "== Visualization: 3D web app scene and the apparatus render =="
  $PY viz/export_scene.py                 # needs data/processed/malmesbury_dem.npz
  $PY viz/preview_scene.py
  # needs viz/figures/apparatus_3d.png (render_blender.py) and the cairo library (Homebrew)
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib $PY viz/compose_apparatus.py
  cp viz/figures/apparatus_hero.png figures/fig_apparatus.png
else
  echo "== viz/ not present: using the committed figures/fig_apparatus.png =="
fi
cp data/raw/photos/water_meadows.jpg figures/fig_abbey_photo.jpg   # CC BY-SA 2.0, see SOURCE.md

echo "== Manuscript numbers: metrics.json -> paper_source_iop/numbers.tex =="
$PY analysis/export_numbers.py

echo "== Manuscript: compile LaTeX (needs TeX Live + biber) =="
if command -v latexmk >/dev/null 2>&1; then
  # main.tex and supplementary.tex cross-reference each other (xr-hyper): main, supplement, main
  (cd paper_source_iop && for t in main supplementary main main_anon; do
     latexmk -pdf -interaction=nonstopmode -halt-on-error -g $t.tex || exit 1; done)
else
  echo "latexmk not found; skipping paper build"
fi

echo "== done: see figures/ and paper_source_iop/main.pdf, supplementary.pdf, main_anon.pdf =="
