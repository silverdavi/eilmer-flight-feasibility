"""Point-mass glide from a standing launch, shared by Workstreams C and F.

Air-relative longitudinal dynamics at a fixed trim lift coefficient (a stable,
tailed glider that holds its trim; the pilot does not fly a dive-and-pullout):

    dV/dt     = g sin(gamma) - D/m
    dgamma/dt = (g cos(gamma) - L/m) / V          gamma > 0 is descending
    dz/dt     = -V sin(gamma) + w

with L = q S C_L, D = L / (L/D), q = rho V^2 / 2, and a uniform updraft w from
ridge lift. The wind is uniform, so it enters only through the release airspeed
and the conversion from air-relative to ground speed:

    into wind (SW, down the escarpment):  ground speed = V cos(gamma) - U
    along the slope (crabbed into wind):  ground speed = sqrt((V cos gamma)^2 - U^2)

The pilot leaves the tower at a walking jump speed, so the release airspeed is
the jump speed plus the headwind (into wind), or their vector sum (along the
slope, jump along the track with the wind on the nose).

The landing surface is the terrain: the measured DEM profile for the into-wind
track, and a contour at mid-slope for the along-slope track (a ridge-soaring
glider follows the slope face). Ridge lift acts only over the slope: on the
into-wind track until the profile flattens onto the valley floor, and on the
along-slope track for the measured length of SW-facing slope. A flight still
airborne at T_MAX is hovering in lift with no ground speed; its range is the
ground it actually covered.

Pure numpy, vectorised over samples. No plotting.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEM = ROOT / "data" / "processed" / "malmesbury_dem.npz"
TERRAIN_METRICS = ROOT / "analysis" / "terrain" / "metrics.json"

G_ACCEL = 9.81
RHO = 1.225
V_JUMP = 2.0             # walking jump off the tower parapet (m/s)
DT = 0.01                # integration step (s)
T_MAX = 120.0            # still airborne after this: hovering in lift
SOARING_RANGE = 1000.0   # display cap on range (m)
INTO_WIND_AZ = 225.0     # SW heading, down the escarpment into the wind
SW_FACE_MIN_SLOPE_DEG = 5.0   # ground at least this steep counts as lift-producing slope
TRACKS = ("into_wind", "along_slope")


def terrain_profile(az_deg: float = INTO_WIND_AZ, s_max: float = 1000.0, step: float = 5.0):
    """Ground elevation relative to the abbey along a straight heading (m)."""
    d = np.load(DEM)
    dem = d["dem"].astype(float)
    nr, nc = dem.shape
    lat_n, lat_s = float(d["lat_n"]), float(d["lat_s"])
    lon_w, lon_e = float(d["lon_w"]), float(d["lon_e"])
    alat, alon = float(d["abbey_lat"]), float(d["abbey_lon"])
    coslat = math.cos(math.radians(alat))

    def elev(e, n):
        r = (lat_n - (alat + n / 110540.0)) / (lat_n - lat_s) * nr
        c = ((alon + e / (111320.0 * coslat)) - lon_w) / (lon_e - lon_w) * nc
        r0, c0 = int(r), int(c)
        fr, fc = r - r0, c - c0
        z = dem[r0:r0 + 2, c0:c0 + 2]
        return float(z[0, 0] * (1 - fr) * (1 - fc) + z[0, 1] * (1 - fr) * fc
                     + z[1, 0] * fr * (1 - fc) + z[1, 1] * fr * fc)

    s = np.arange(0.0, s_max + step, step)
    ux, uy = math.sin(math.radians(az_deg)), math.cos(math.radians(az_deg))
    z0 = elev(0.0, 0.0)
    return s, np.array([elev(si * ux, si * uy) - z0 for si in s])


def along_slope_ground() -> float:
    """Contour followed by an along-slope track: mid-slope, below the abbey (m)."""
    relief = json.loads(TERRAIN_METRICS.read_text())["relief_abbey_above_valley_m"]
    return -0.5 * relief


def into_wind_lift_extent(profile, flat_deg: float = 2.0) -> float:
    """Distance along the SW profile over which the ground still falls (m)."""
    s, z = profile
    grade = np.degrees(np.arctan(-np.gradient(z, s)))
    flat = np.nonzero(grade < flat_deg)[0]
    flat = flat[flat > 0]
    return float(s[flat[0]]) if flat.size else float(s[-1])


def along_slope_lift_extent(min_slope_deg: float = SW_FACE_MIN_SLOPE_DEG, offsets=range(0, 41, 10),
                            endpoints: bool = False):
    """Longest straight NW-SE run of SW-facing slope near the abbey (m).

    Sampled on lines parallel to the escarpment, 0-40 m SW of the abbey, so the
    run lies on the slope face a ridge-soaring track would follow. With
    `endpoints`, also return the run's (east, north) ends relative to the abbey.
    """
    d = np.load(DEM)
    dem = d["dem"].astype(float)
    nr, nc = dem.shape
    lat = np.linspace(float(d["lat_n"]), float(d["lat_s"]), nr)
    lon = np.linspace(float(d["lon_w"]), float(d["lon_e"]), nc)
    alat, alon = float(d["abbey_lat"]), float(d["abbey_lon"])
    dy = (lat[0] - lat[1]) * 110540.0
    dx = (lon[1] - lon[0]) * 111320.0 * math.cos(math.radians(alat))
    gy, gx = np.gradient(dem, dy, dx)
    dzdn, dzde = -gy, gx
    slope = np.degrees(np.arctan(np.hypot(dzdn, dzde)))
    aspect = (np.degrees(np.arctan2(-dzde, -dzdn)) + 360.0) % 360.0
    iy, ix = int(np.argmin(abs(lat - alat))), int(np.argmin(abs(lon - alon)))
    step, best, ends = 6.0, 0.0, None
    for off in offsets:
        e0, n0 = off * math.sin(math.radians(225)), off * math.cos(math.radians(225))
        run, start = 0.0, None
        for s in np.arange(-600.0, 600.0 + step, step):
            e = e0 + s * math.sin(math.radians(315))
            n = n0 + s * math.cos(math.radians(315))
            r, c = int(round(iy - n / dy)), int(round(ix + e / dx))
            ok = slope[r, c] >= min_slope_deg and 191.25 <= aspect[r, c] <= 258.75
            if ok:
                start = (e, n) if run == 0.0 else start
                run += step
            else:
                run = 0.0
            if run > best:
                best, ends = run, (start, (e, n))
    return (best, ends) if endpoints else best


class Site:
    """Terrain inputs for both tracks, computed once from the DEM."""

    def __init__(self):
        self.profile = terrain_profile()
        self.lift_extent = {"into_wind": into_wind_lift_extent(self.profile),
                            "along_slope": along_slope_lift_extent()}
        self.contour = along_slope_ground()


def fly(track, tower, wind, updraft, mass, area, cl, ld, site=None, record=None):
    """Integrate standing launches. All sample arguments broadcast to one shape.

    Returns ground range (m), flight time (s), and impact vertical speed (m/s).
    `record` (an index) returns the trajectory of one sample as (x, z) arrays.
    """
    tower, wind, updraft, mass, area, cl, ld = np.broadcast_arrays(
        *[np.asarray(a, float) for a in (tower, wind, updraft, mass, area, cl, ld)])
    shape = tower.shape
    site = site or Site()
    lift_end = site.lift_extent[track]
    if track == "into_wind":
        s_prof, z_prof = site.profile
        ground = lambda x: np.interp(x, s_prof, z_prof)      # noqa: E731
        va = V_JUMP + wind
    elif track == "along_slope":
        ground = lambda x: np.full_like(x, site.contour)     # noqa: E731
        va = np.hypot(V_JUMP, wind)
    else:
        raise ValueError(track)

    va = va.copy()
    gam = np.zeros(shape)
    z = tower.copy()
    x = np.zeros(shape)
    t_land = np.full(shape, np.inf)
    vz_land = np.zeros(shape)
    alive = np.ones(shape, bool)
    path = [] if record is not None else None
    t = 0.0
    while alive.any() and t < T_MAX:
        q = 0.5 * RHO * va**2 * area
        lift = q * cl
        drag = lift / ld
        vx_air = va * np.cos(gam)
        if track == "into_wind":
            gs = vx_air - wind
        else:
            gs = np.sqrt(np.clip(vx_air**2 - wind**2, 0.0, None))
        vz = -va * np.sin(gam) + np.where(x < lift_end, updraft, 0.0)
        dva = G_ACCEL * np.sin(gam) - drag / mass
        dgam = (G_ACCEL * np.cos(gam) - lift / mass) / np.maximum(va, 0.5)
        x = np.where(alive, x + gs * DT, x)
        z = np.where(alive, z + vz * DT, z)
        va = np.where(alive, va + dva * DT, va)
        gam = np.where(alive, gam + dgam * DT, gam)
        t += DT
        if path is not None:
            path.append((float(x.flat[record]), float(z.flat[record])))
        landed = alive & (z <= ground(x))
        t_land = np.where(landed, t, t_land)
        vz_land = np.where(landed, -vz, vz_land)
        alive &= ~landed
    R = np.clip(x, 0.0, SOARING_RANGE)
    t_flight = np.where(alive, T_MAX, t_land)
    out = (R, t_flight, vz_land)
    if path is not None:
        p = np.array(path)
        return out + (p[:, 0], p[:, 1])
    return out
