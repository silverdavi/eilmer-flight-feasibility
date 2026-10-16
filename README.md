# Eilmer of Malmesbury: a flight-feasibility study

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20706321.svg)](https://doi.org/10.5281/zenodo.20706321)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Analysis code and LaTeX manuscript for a study of the eleventh-century flight of
Eilmer of Malmesbury, reported by William of Malmesbury in the *Gesta Regum
Anglorum*: a monk who fixed wings to his hands and feet, launched from a tower,
travelled "more than a furlong" (about 200 m), broke both legs, and blamed the fall
on having no tail. The study tests whether that account is consistent with
elementary flight physics, and sets each step as a student exercise.

![Malmesbury Abbey from the southwest](figures/fig_abbey_photo.jpg)

*Malmesbury Abbey from the water meadows southwest of the abbey. Photograph: Dr
Duncan Pepper, 2012, via Geograph and Wikimedia Commons, CC BY-SA 2.0.*

## Version 1.1.0: corrected glide model

Version 1.0.0 contained an error in the glide model: the ground range used the
airspeed instead of the airspeed minus the headwind, which overstated the range of
a craft flying into the wind by about a factor of two. It also assumed the craft
left the tower already at gliding speed. Version 1.1.0 corrects both, and the
results below supersede those of 1.0.0.

The glide is now integrated in time from a standing launch (`analysis/aero/flight.py`),
with the wind subtracted from the ground speed, ridge lift confined to the measured
extent of the slope, and the craft landing on the terrain. Two tracks are flown:
straight out over the valley into the wind, and along the southwest-facing slope in
ridge lift. The glide ratio is derived from a drag polar with bounded aspect ratio,
span efficiency, and zero-lift drag, instead of being sampled directly.

## What the study finds

- **Launch.** Leaving the tower at walking pace, the craft must lose about 11.5 m of
  height to reach its 15.1 m/s flying speed, so a long flight needs a strong wind.
- **Into the wind.** None of 40,000 sampled apparatus and launch-day cases reaches
  200 m flying straight out over the valley.
- **Along the slope.** 6.9% of cases reach 200 m in ridge lift (95% CI 6.6–7.1%),
  with a median launch wind of 7.6 m/s and the better wings (median L/D 5.8).
- **Stability.** Without a tail the wing diverges in pitch, with a median doubling
  time of 0.29 s, comparable to human reaction time, during a flight of about 24 s.
  A tail removes the divergence.
- **Injury.** A controlled glide that hits the ground without a flare arrives at no
  more than 4.1 m/s vertically, below the lowest leg-fracture speed (6.1 m/s). The
  broken legs need a fast, steep arrival, which a loss of pitch control provides.

The account is physically possible but marginal, and the missing tail is a
sufficient cause of the fall.

## Repository layout

```
analysis/          one folder per workstream; process_*.py writes metrics.json,
  terrain/           plot_*.py reads it and draws the figure, fetch_*.py downloads
  weather/           the public input data
  aero/              flight.py: the shared standing-launch glide integrator
  synthesis/         Monte Carlo over the unknown apparatus and launch day
  biomech/           impact and leg fracture
  export_numbers.py  metrics.json -> paper_source_iop/numbers.tex (every number in the text)
config/            shared plotting style
data/raw/          wind data, the abbey photograph (photos/SOURCE.md), data notes
data/processed/    derived datasets (.npz) behind each figure
figures/           generated figures (PDF and PNG)
paper_source_iop/  LaTeX manuscript: main.tex, supplementary.tex, sections/, main.pdf
run_all.sh         rebuild every dataset, figure, and number, then compile the paper
```

## Reproduce

Requires Python 3.12. Using [uv](https://docs.astral.sh/uv/):

```bash
uv venv && uv pip install -r requirements.txt
./run_all.sh
```

Or with pip:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./run_all.sh
```

`run_all.sh` fetches the input data, regenerates every `.npz`, figure, and
`numbers.tex`, and compiles the manuscript if `latexmk` and a TeX distribution are
present. The fetch steps need network access on the first run. The nominal-apparatus
render (`figures/fig_apparatus.png`) is a static asset; its 3D rendering pipeline is
not part of this repository.

## Data sources

- **Wind:** ECMWF ERA5 reanalysis via the [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
- **Terrain:** [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) (about 6 m grid).
- **Photograph:** Wikimedia Commons, CC BY-SA 2.0 (see `data/raw/photos/SOURCE.md`).

See `data/raw/DATA_SOURCES_AND_METHODOLOGY.md`. Site: Malmesbury Abbey, 51.5846° N,
2.0997° W.

## Citation

Please cite the paper (see `CITATION.cff`).

## License

Code is released under the MIT License (see `LICENSE`). The manuscript text and
figures are © 2026 David H. Silver; reuse of the figures is permitted with
attribution. The abbey photograph is © Dr Duncan Pepper, CC BY-SA 2.0.
