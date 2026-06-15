"""Phase-1 terrain: fetch a DEM around Malmesbury (keyless).

Uses AWS open Terrain Tiles (Mapzen/Tilezen 'terrarium' PNGs) on S3 -- no API
key. This is the Phase-1 stand-in for Environment Agency LIDAR (Workstream A).

Output:
  data/processed/malmesbury_dem.npz  (elevation grid + lon/lat extent)
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "malmesbury_dem.npz"

LAT, LON = 51.5846, -2.0997  # Malmesbury Abbey
Z = 14                       # ~6 m/px at this latitude
N_TILES = 3                  # (2*N+1)^2 grid -> ~7x7 km
TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def deg2tile(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile2deg(x, y, z):
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def fetch_tile(z, x, y) -> np.ndarray:
    r = requests.get(TILE.format(z=z, x=x, y=y), timeout=60)
    r.raise_for_status()
    img = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=np.float64)
    # terrarium decode
    return img[..., 0] * 256.0 + img[..., 1] + img[..., 2] / 256.0 - 32768.0


def main() -> None:
    xf, yf = deg2tile(LAT, LON, Z)
    xc, yc = int(xf), int(yf)
    rows = []
    for dy in range(-N_TILES, N_TILES + 1):
        cols = [fetch_tile(Z, xc + dx, yc + dy) for dx in range(-N_TILES, N_TILES + 1)]
        rows.append(np.hstack(cols))
        print(f"fetched tile row {dy + N_TILES + 1}/{2 * N_TILES + 1}")
    dem = np.vstack(rows)

    lat_n, lon_w = tile2deg(xc - N_TILES, yc - N_TILES, Z)
    lat_s, lon_e = tile2deg(xc + N_TILES + 1, yc + N_TILES + 1, Z)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT, dem=dem.astype(np.float32),
        lat_n=lat_n, lat_s=lat_s, lon_w=lon_w, lon_e=lon_e,
        abbey_lat=LAT, abbey_lon=LON, zoom=Z,
    )
    print(f"DEM {dem.shape}, elev {dem.min():.0f}..{dem.max():.0f} m -> {OUT}")
    print(f"extent lat {lat_s:.4f}..{lat_n:.4f}  lon {lon_w:.4f}..{lon_e:.4f}")


if __name__ == "__main__":
    main()
