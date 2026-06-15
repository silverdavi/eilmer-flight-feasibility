# Data sources and methodology

All Phase-1 sources are open and keyless. Raw downloads land here and are never
modified; processing writes to `data/processed/`.

| Dataset | Source | Access | Reliability | Used by |
|---------|--------|--------|-------------|---------|
| ERA5 10 m wind, hourly 2004-2023 | ECMWF ERA5 via Open-Meteo archive API | keyless HTTP, `analysis/weather/fetch_wind.py` | high (reanalysis); confirmatory | Workstream B |
| DEM, ~6 m/px | AWS Terrain Tiles (Mapzen/Tilezen terrarium) | keyless S3, `analysis/terrain/fetch_dem.py` | medium (coarse); exploratory for slope | Workstream A, C |

## Phase-2 upgrades (require keys / heavier tooling)

- **ERA5 direct**: Copernicus CDS API (`cdsapi`, `~/.cdsapirc`) for the full
  resolution field and gust statistics.
- **NOAA-CIRES 20CR v3**: multi-century continuity back to ~1806.
- **Environment Agency LIDAR (≤1 m)**: Defra Data Services Platform, to resolve
  the true launch-edge escarpment slope.
- **NAO reconstructions**: Trouet et al. 2009 and Ortega et al. 2015 series for
  the MCA stationarity argument.

## Site

Malmesbury Abbey: 51.5846 N, 2.0997 W.

## Reproducibility

`./run_all.sh` rebuilds every processed table and figure from the raw downloads
in order (fetch, process, plot per workstream). The environment is a `uv` venv
on Python 3.12 (`requirements.txt`); the system Homebrew Python 3.14 has a
broken `pyexpat` and is not used.
