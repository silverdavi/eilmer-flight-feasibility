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

if [ "${RENDER_FIG3:-0}" = 1 ]; then
  echo "== Figure 3: Blender Cycles render of the nominal apparatus, then labels =="
  # needs .venv-bpy (pip install bpy==5.0.1), the CC0 assets (viz/hero/assets/fetch_assets.sh),
  # viz/hero/assets/monk_prone.blend, GNU timeout (brew install coreutils) and the cairo library
  gtimeout 900 .venv-bpy/bin/python viz/hero/final/render_fig3_v5.py --shot main --pct 100 --samples 1024
  gtimeout 600 .venv-bpy/bin/python viz/hero/final/render_fig3_v5.py --shot inset --pct 100 --samples 768
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib gtimeout 300 $PY viz/hero/final/compose_fig3_v6.py \
    viz/hero/final/_work/fig3_v5_main_render.png viz/hero/final/_work/fig3_v5_inset_render.png \
    viz/hero/final/fig_apparatus_v6 viz/hero/final/_work/fig3_v5_points.json
  cp viz/hero/final/fig_apparatus_v6.png figures/fig_apparatus.png
else
  echo "== Figure 3: using the committed figures/fig_apparatus.png (RENDER_FIG3=1 to re-render) =="
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
