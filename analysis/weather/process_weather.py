"""Workstream B processing: wind-launch favourability climatology.

Reads the 20-year ERA5 hourly archive (fetch_wind.py) and writes:
  data/processed/wind_rose.npz     -- direction x speed frequency matrix
  analysis/weather/metrics.json    -- favourability with 95% CIs

Favourable launch = wind from the SW sector (so it climbs the SW-facing
escarpment, confirmed in Workstream A) and within a usable speed band. The CI is
taken across the 20 independent years (t-interval), so the figure shows
interannual spread, not a point estimate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "raw" / "malmesbury_wind_era5.csv"
ROSE = ROOT / "data" / "processed" / "wind_rose.npz"
METRICS = Path(__file__).resolve().parent / "metrics.json"

SECTOR_LO, SECTOR_HI = 191.25, 258.75   # SSW-WSW, climbs the SW escarpment
SPEED_LO, SPEED_HI = 5.0, 12.0          # usable ridge-soaring band (m/s)
STRONG_SW_MS = 8                         # "strong" SW wind threshold quoted in the text (m/s)

N_SECTORS = 16
SPEED_BINS = [0, 2, 4, 6, 8, 10, 1e9]
SPEED_LABELS = ["0-2", "2-4", "4-6", "6-8", "8-10", "10+"]
SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC, parse_dates=["time"]).dropna(subset=["wind_speed_ms", "wind_dir_deg"])
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    return df


def favourable(df: pd.DataFrame) -> pd.Series:
    d, s = df["wind_dir_deg"], df["wind_speed_ms"]
    return (d >= SECTOR_LO) & (d <= SECTOR_HI) & (s >= SPEED_LO) & (s <= SPEED_HI)


def ci95_across_years(per_year: pd.Series) -> tuple[float, float, float]:
    vals = per_year.to_numpy()
    mean = float(vals.mean())
    sem = float(vals.std(ddof=1) / math.sqrt(len(vals)))
    half = 1.96 * sem  # ~normal; n=20
    return mean, mean - half, mean + half


def rose_matrix(df: pd.DataFrame) -> np.ndarray:
    edges = np.linspace(-11.25, 348.75, N_SECTORS + 1)
    d = df["wind_dir_deg"].to_numpy() % 360
    d = np.where(d >= 348.75, d - 360, d)
    sect = (np.digitize(d, edges) - 1) % N_SECTORS
    spd = np.clip(np.digitize(df["wind_speed_ms"].to_numpy(), SPEED_BINS) - 1, 0, len(SPEED_LABELS) - 1)
    mat = np.zeros((N_SECTORS, len(SPEED_LABELS)))
    np.add.at(mat, (sect, spd), 1)
    return 100.0 * mat / len(df)


def strong_sw(df: pd.DataFrame, thresholds=(5, 6, 7, 8, 9, 10, 11, 12)) -> dict:
    """Percent of hours with SW-sector wind at or above each speed, 95% CI across years."""
    sw = (df["wind_dir_deg"] >= SECTOR_LO) & (df["wind_dir_deg"] <= SECTOR_HI)
    out = {}
    for u in thresholds:
        f = sw & (df["wind_speed_ms"] >= u)
        py = 100 * df.assign(f=f).groupby("year")["f"].mean()
        mean, lo, hi = ci95_across_years(py)
        out[str(u)] = {"mean": round(mean, 2), "ci95": [round(lo, 2), round(hi, 2)],
                       "hours_per_year": round(float(df.assign(f=f).groupby("year")["f"].sum().mean()), 0)}
    return out


def main() -> None:
    df = load()
    fav = favourable(df)

    pct_per_year = 100 * df.assign(f=fav).groupby("year")["f"].mean()
    ann_mean, ann_lo, ann_hi = ci95_across_years(pct_per_year)
    hours_per_year = df.assign(f=fav).groupby("year")["f"].sum()

    season = {}
    for name, months in SEASONS.items():
        sub = df[df["month"].isin(months)]
        py = 100 * sub.assign(f=favourable(sub)).groupby("year")["f"].mean()
        mean, lo, hi = ci95_across_years(py)
        season[name] = {"mean": round(mean, 2), "ci95": [round(lo, 2), round(hi, 2)]}

    np.savez_compressed(ROSE, matrix=rose_matrix(df),
                        speed_labels=np.array(SPEED_LABELS),
                        sector_lo=SECTOR_LO, sector_hi=SECTOR_HI)

    metrics = {
        "data_source": "ERA5 hourly 10 m wind via Open-Meteo archive",
        "n_hours": int(len(df)),
        "n_years": int(df["year"].nunique()),
        "sector_deg": [SECTOR_LO, SECTOR_HI],
        "speed_band_ms": [SPEED_LO, SPEED_HI],
        "favourable_pct_annual": {
            "mean": round(ann_mean, 2), "ci95": [round(ann_lo, 2), round(ann_hi, 2)]},
        "favourable_hours_per_year": {
            "mean": round(float(hours_per_year.mean()), 0),
            "min": int(hours_per_year.min()), "max": int(hours_per_year.max())},
        "sw_sector_any_speed_pct": round(
            100 * ((df["wind_dir_deg"] >= SECTOR_LO) & (df["wind_dir_deg"] <= SECTOR_HI)).mean(), 1),
        "favourable_pct_by_season": season,
        "sw_pct_at_or_above_ms": strong_sw(df),
        "strong_sw_threshold_ms": STRONG_SW_MS,
    }
    METRICS.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
