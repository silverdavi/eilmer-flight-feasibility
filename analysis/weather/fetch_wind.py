"""Phase-1 weather: pull ERA5 reanalysis wind for Malmesbury (keyless).

Uses the Open-Meteo ERA5 historical archive API, which serves ECMWF ERA5
hourly 10 m wind without an API key. This is the Phase-1 stand-in for a direct
CDS ERA5 pull (Workstream B, layer 1).

Output: data/raw/malmesbury_wind_era5.csv
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

# Malmesbury Abbey
LAT, LON = 51.5846, -2.0997

START = "2004-01-01"
END = "2023-12-31"  # 20 years of ERA5 hourly

API = "https://archive-api.open-meteo.com/v1/archive"

OUT = Path(__file__).resolve().parents[2] / "data" / "raw" / "malmesbury_wind_era5.csv"


def fetch() -> pd.DataFrame:
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": START,
        "end_date": END,
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "format": "csv",
    }
    print(f"Requesting ERA5 {START}..{END} at ({LAT}, {LON}) ...", file=sys.stderr)
    r = requests.get(API, params=params, timeout=120)
    r.raise_for_status()
    # Open-Meteo CSV: a few metadata lines, then a header row starting with "time".
    text = r.text
    lines = text.splitlines()
    hdr = next(i for i, ln in enumerate(lines) if ln.startswith("time"))
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])))
    df.columns = ["time", "wind_speed_ms", "wind_dir_deg", "wind_gust_ms"]
    df["time"] = pd.to_datetime(df["time"])
    return df


def main() -> None:
    df = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    n = len(df)
    yrs = df["time"].dt.year.nunique()
    print(f"Saved {n:,} hourly records ({yrs} years) -> {OUT}")
    print(df.describe(include="all").T[["count", "mean", "min", "max"]])


if __name__ == "__main__":
    main()
