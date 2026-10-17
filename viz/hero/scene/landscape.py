"""Cotswold-edge landscape round a hilltop town on a spur (Malmesbury-like, not a survey):
terrain, two rivers joining below the spur's south-west tip, a patchwork of hedged fields,
water meadows, woods, riverside trees, and a town of thatched timber houses on the spur.

World frame: metres, +x east, +y north, z up. The church tower stands at the origin on the
plateau (z = PLATEAU). The spur's axis points along FLIGHT_AZ (compass degrees), which is
also Eilmer's heading; the valley floor is ~28 m below the plateau.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).resolve().parent
CACHE = HERE / "_cache"
CACHE.mkdir(exist_ok=True)

PLATEAU = 30.0          # town plateau above the river (m)
RIVER_Z = 0.4           # water surface
FLIGHT_AZ = 235.0       # heading, compass degrees (WSW, along the spur axis)
A = Vector((math.sin(math.radians(FLIGHT_AZ)), math.cos(math.radians(FLIGHT_AZ)), 0))
B = Vector((-A.y, A.x, 0)) * -1          # right of the heading (to the NNW)
EDGE_S = 60.0           # plateau edge ahead of the tower, along A (the abbey is near the brow)
SLOPE_W = 130.0         # horizontal length of the escarpment
HALF_W = 200.0          # plateau half-width across the spur
DOMAIN = 8000.0         # field-map square (m), centred on the tower
FIELD_PX = 2048


def sd(x, y):
    return x * A.x + y * A.y, x * B.x + y * B.y


def xy(s, d):
    p = A * s + B * d
    return p.x, p.y


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- rivers (spur frame s, d)

_SOUTH = [(-2500, 420), (-1800, 380), (-1200, 410), (-700, 360), (-300, 385), (0, 360),
          (200, 330), (360, 260), (470, 150), (540, 40)]
_NORTH = [(-2500, -430), (-1700, -400), (-1100, -380), (-600, -400), (-200, -370), (100, -360),
          (300, -300), (440, -180), (520, -60), (540, 40)]
_MAIN = [(540, 40), (640, 90), (760, 40), (900, -60), (1050, -20), (1200, 110), (1400, 150),
         (1650, 60), (1900, 120), (2300, 260), (2800, 180), (3400, 300), (4200, 240), (5200, 420)]


def _dense(poly, step=6.0):
    pts = []
    P = [Vector((*xy(s, d), 0)) for s, d in poly]
    # Catmull-Rom through the control points
    for i in range(len(P) - 1):
        p0, p1, p2 = P[max(i - 1, 0)], P[i], P[i + 1]
        p3 = P[min(i + 2, len(P) - 1)]
        n = max(2, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    pts.append(P[-1])
    return pts


RIVERS = [(_dense(_SOUTH), 9.0), (_dense(_NORTH), 8.0), (_dense(_MAIN), 13.0)]
_RIV_PTS = np.array([[p.x, p.y, w] for pts, w in RIVERS for p in pts])


def river_dist(x, y):
    d = np.hypot(_RIV_PTS[:, 0] - x, _RIV_PTS[:, 1] - y)
    i = int(np.argmin(d))
    return float(d[i]), float(_RIV_PTS[i, 2])


# ---------------------------------------------------------------- height field

def height(x, y):
    s, d = sd(x, y)
    w = HALF_W + 35 * noise.noise(Vector((s / 260, 0.3, 1.1)))
    ds = max(0.0, s - EDGE_S - 25 * noise.noise(Vector((d / 180, 2.1, 0.4))))
    dd = max(0.0, abs(d) - w)
    q = math.hypot(ds, dd)
    plateau = 1 - smooth(0, SLOPE_W, q)
    z = 1.2 + (PLATEAU - 1.2) * plateau
    # gentle relief on the plateau and the valley floor
    z += 1.5 * plateau * noise.fractal(Vector((x / 220, y / 220, 0.7)), 0.5, 2.0, 3)
    z += 0.8 * (1 - plateau) * noise.fractal(Vector((x / 160, y / 160, 3.1)), 0.5, 2.0, 3)
    # rising ground beyond the valley (the other side) and rolling hills to the horizon
    r = math.hypot(x, y)
    across = max(0.0, s - 650) + max(0.0, abs(d) - 650) * 0.6
    z += 26 * smooth(0, 1500, across)
    w2 = smooth(700, 3000, r)
    z += w2 * 34 * (0.55 + noise.fractal(Vector((x / 2600, y / 2600, 0.3)), 0.55, 2.0, 4))
    z += w2 * 7 * noise.fractal(Vector((x / 520, y / 520, 1.7)), 0.6, 2.0, 3)
    z += 40 * smooth(4000, 14000, r) - 70 * smooth(16000, 40000, r)
    # river channels and their flood plain
    rd, rw = river_dist(x, y)
    if rd < 140:
        bed = RIVER_Z - 1.2
        plain = RIVER_Z + 0.9
        z = min(z, plain + (z - plain) * smooth(rw, rw + 120, rd)) if z > plain else z
        z = bed + (z - bed) * smooth(rw * 0.9, rw * 1.9, rd)
    return z


# ---------------------------------------------------------------- materials helpers

def _mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"], nt.nodes["Material Output"]


def _n(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        if k.startswith("_"):
            setattr(n, k[1:], v)
        else:
            n.inputs[k.replace("_", " ")].default_value = v
    return n


def _l(nt, a, b):
    nt.links.new(a, b)


def _ramp(nt, fac, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = (*c, 1)
    _l(nt, fac, r.inputs["Fac"])
    return r


# ---------------------------------------------------------------- field map

def field_map(seed=11):
    """Jittered-grid Voronoi fields rasterised to FIELD_PX^2 over DOMAIN: per-pixel field id,
    colour image (linear RGB) and a hedge mask. Cached in _cache/."""
    f_npz = CACHE / f"fields_{seed}_{FIELD_PX}_e{int(EDGE_S)}b.npz"
    if f_npz.exists():
        z = np.load(f_npz)
        return z["rgb"], z["hedge"], z["kind"]
    rng = np.random.default_rng(seed)
    N = FIELD_PX
    px = DOMAIN / N
    xs = (np.arange(N) + 0.5) * px - DOMAIN / 2
    X, Y = np.meshgrid(xs, xs)                       # row = y, col = x
    # rotate into a frame aligned with the spur so the field grain follows the land
    ang = math.radians(90 - FLIGHT_AZ)
    U = X * math.cos(ang) + Y * math.sin(ang)
    V = -X * math.sin(ang) + Y * math.cos(ang)
    cell = 150.0
    gu, gv = np.floor(U / cell).astype(np.int64), np.floor(V / (cell * 0.8)).astype(np.int64)
    best = np.full(U.shape, 1e18)
    bid = np.zeros(U.shape, np.int64)

    def h(i, j, k):
        return ((i * 73856093) ^ (j * 19349663) ^ (k * 83492791)) & 0xFFFFFF

    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ci, cj = gu + di, gv + dj
            jx = (h(ci, cj, 1) / 0xFFFFFF) * 0.9 + 0.05
            jy = (h(ci, cj, 2) / 0xFFFFFF) * 0.9 + 0.05
            su, sv = (ci + jx) * cell, (cj + jy) * cell * 0.8
            dist = (U - su) ** 2 + ((V - sv) * 1.15) ** 2
            m = dist < best
            best[m] = dist[m]
            bid[m] = (ci * 100003 + cj)[m]
    # hedges: id changes between neighbouring pixels (some boundaries left open)
    edge = np.zeros(U.shape, bool)
    edge[:, 1:] |= bid[:, 1:] != bid[:, :-1]
    edge[1:, :] |= bid[1:, :] != bid[:-1, :]
    pair_open = (h(bid, np.roll(bid, 1, 1), 7) % 100) < 18
    edge &= ~pair_open
    # per-field kind: 0 pasture, 1 hay, 2 stubble, 3 ploughed, 4 strips (open field), 5 wood
    r = (h(bid, bid * 7, 3) % 1000) / 1000.0
    kind = np.select([r < 0.46, r < 0.62, r < 0.74, r < 0.80, r < 0.93], [0, 1, 2, 3, 4], 5)
    pal = {0: [(0.050, 0.105, 0.026), (0.065, 0.125, 0.030), (0.045, 0.092, 0.024)],
           1: [(0.105, 0.125, 0.045), (0.12, 0.13, 0.05)],
           2: [(0.25, 0.19, 0.085), (0.22, 0.17, 0.08)],
           3: [(0.10, 0.068, 0.042)],
           4: [(0.09, 0.12, 0.035)],
           5: [(0.020, 0.040, 0.012)]}
    rgb = np.zeros((*U.shape, 3), np.float32)
    pick = h(bid, bid * 3, 5) % 3
    for k, cols in pal.items():
        for i, c in enumerate(cols):
            m = (kind == k) & ((pick % len(cols)) == i)
            rgb[m] = c
    # open-field strips: alternating ridges ~10 m across, direction per furlong
    th = (h(bid, bid, 9) % 180) * math.pi / 180
    stripe = 0.5 + 0.5 * np.sin((U * np.cos(th) + V * np.sin(th)) * (math.pi / 5.0))
    sm = kind == 4
    alt = (np.floor((U * np.cos(th) + V * np.sin(th)) / 10.0).astype(np.int64) * 31 + bid) % 4
    stripcol = np.array([(0.10, 0.13, 0.04), (0.20, 0.16, 0.07), (0.07, 0.11, 0.03),
                         (0.14, 0.14, 0.05)], np.float32)
    rgb[sm] = stripcol[alt[sm]] * (0.85 + 0.15 * stripe[sm])[:, None]
    # tonal variation inside fields
    vary = (h(bid, bid, 4) % 1000) / 1000.0 * 0.35 + 0.82
    rgb *= vary[..., None]
    # town plateau, water meadows, river banks
    S = X * A.x + Y * A.y
    D = X * B.x + Y * B.y
    # escarpment and spur flanks: rough grazing, not arable
    slope = (S > EDGE_S - 10) & (S < EDGE_S + SLOPE_W + 20) & (np.abs(D) < HALF_W + 60) & (kind != 5)
    rough = np.array([(0.055, 0.10, 0.028), (0.075, 0.11, 0.035), (0.06, 0.09, 0.03)], np.float32)
    rgb[slope] = rough[(h(bid, bid, 13) % 3)[slope]] * vary[slope][:, None]
    kind = np.where(slope, 0, kind)
    town = (S < EDGE_S - 10) & (np.abs(D) < HALF_W - 15) & (S > -1300)
    rgb[town] = (0.075, 0.095, 0.035)
    kind = np.where(town, 9, kind)
    edge &= ~town
    q = 4
    Xq, Yq = X[::q, ::q], Y[::q, ::q]
    riv = np.full(Xq.shape, 1e12)
    for (pts, w) in RIVERS:
        for p in pts[::2]:
            riv = np.minimum(riv, (Xq - p.x) ** 2 + (Yq - p.y) ** 2)
    riv = np.repeat(np.repeat(np.sqrt(riv), q, 0), q, 1)[:N, :N]
    meadow = riv < 110
    rgb[meadow] = rgb[meadow] * 0.35 + np.array((0.06, 0.13, 0.03), np.float32) * 0.65
    kind = np.where(meadow & (kind != 9), 8, kind)
    edge &= ~(riv < 25)
    hedge = edge.astype(np.float32)
    np.savez_compressed(f_npz, rgb=rgb, hedge=hedge, kind=kind.astype(np.int16))
    return rgb, hedge, kind.astype(np.int16)


def field_image():
    name = "field_map"
    if name in bpy.data.images:
        return bpy.data.images[name]
    rgb, hedge, kind = field_map()
    N = rgb.shape[0]
    # darken under hedges (their shadowed bases), keep the image linear
    col = rgb * (1 - 0.55 * hedge[..., None])
    img = bpy.data.images.new(name, N, N, alpha=True, float_buffer=True)
    rgba = np.concatenate([col, hedge[..., None]], -1).astype(np.float32)
    img.colorspace_settings.name = "Linear Rec.709"     # before the pixels: it regenerates
    img.pixels.foreach_set(rgba.ravel())
    img.update()
    return img


# ---------------------------------------------------------------- terrain mesh + material

def mat_terrain():
    m, nt, bsdf, out = _mat("terrain")
    tc = _n(nt, "ShaderNodeTexCoord")
    sep = _n(nt, "ShaderNodeSeparateXYZ")
    _l(nt, tc.outputs["Object"], sep.inputs[0])
    # map world xy over the field-map domain
    u = _n(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    _l(nt, sep.outputs["X"], u.inputs[0])
    u.inputs[1].default_value, u.inputs[2].default_value = 1 / DOMAIN, 0.5
    v = _n(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    _l(nt, sep.outputs["Y"], v.inputs[0])
    v.inputs[1].default_value, v.inputs[2].default_value = 1 / DOMAIN, 0.5
    cmb = _n(nt, "ShaderNodeCombineXYZ")
    _l(nt, u.outputs[0], cmb.inputs[0])
    _l(nt, v.outputs[0], cmb.inputs[1])
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = field_image()
    img.extension = "EXTEND"
    img.interpolation = "Cubic"
    _l(nt, cmb.outputs[0], img.inputs[0])
    # outside the map: a procedural patchwork fading in
    far = _n(nt, "ShaderNodeTexVoronoi", Scale=1 / 170, Randomness=0.9)
    _l(nt, tc.outputs["Object"], far.inputs["Vector"])
    fsep = _n(nt, "ShaderNodeSeparateColor")
    _l(nt, far.outputs["Color"], fsep.inputs[0])
    fcol = _ramp(nt, fsep.outputs[0], [(0.0, (0.045, 0.095, 0.024)), (0.5, (0.07, 0.12, 0.03)),
                                       (0.75, (0.11, 0.12, 0.045)), (0.9, (0.22, 0.17, 0.08))])
    r = _n(nt, "ShaderNodeVectorMath", _operation="LENGTH")
    cen = _n(nt, "ShaderNodeCombineXYZ")
    _l(nt, sep.outputs["X"], cen.inputs[0])
    _l(nt, sep.outputs["Y"], cen.inputs[1])
    _l(nt, cen.outputs[0], r.inputs[0])
    fade = _n(nt, "ShaderNodeMapRange", **{"From Min": DOMAIN * 0.42, "From Max": DOMAIN * 0.5})
    _l(nt, r.outputs["Value"], fade.inputs["Value"])
    mix = _n(nt, "ShaderNodeMix", _data_type="RGBA")
    _l(nt, fade.outputs[0], mix.inputs["Factor"])
    _l(nt, img.outputs["Color"], mix.inputs[6])
    _l(nt, fcol.outputs[0], mix.inputs[7])
    # grass detail: tussocks and mown/grazed patches
    g1 = _n(nt, "ShaderNodeTexNoise", Scale=1 / 3.0, Detail=10.0, Roughness=0.65)
    _l(nt, tc.outputs["Object"], g1.inputs["Vector"])
    g2 = _n(nt, "ShaderNodeTexNoise", Scale=1 / 25.0, Detail=4.0)
    _l(nt, tc.outputs["Object"], g2.inputs["Vector"])
    gm = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
    _l(nt, g1.outputs["Fac"], gm.inputs[0])
    _l(nt, g2.outputs["Fac"], gm.inputs[1])
    gv = _ramp(nt, gm.outputs[0], [(0.12, (0.72, 0.74, 0.66)), (0.35, (1.12, 1.1, 1.0))])
    # sward mottling: yellower and bluer patches at tens of metres
    g3 = _n(nt, "ShaderNodeTexNoise", Scale=1 / 45.0, Detail=5.0, Roughness=0.6)
    _l(nt, tc.outputs["Object"], g3.inputs["Vector"])
    g3c = _ramp(nt, g3.outputs["Fac"], [(0.32, (0.80, 0.92, 0.85)), (0.5, (1.0, 1.0, 1.0)),
                                        (0.68, (1.25, 1.12, 0.80))])
    gv2 = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=0.8)
    _l(nt, gv.outputs[0], gv2.inputs[6])
    _l(nt, g3c.outputs[0], gv2.inputs[7])
    mul = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    _l(nt, mix.outputs[2], mul.inputs[6])
    _l(nt, gv2.outputs[2], mul.inputs[7])
    # steep ground: rougher, yellower grass with bare earth
    geo = _n(nt, "ShaderNodeNewGeometry")
    nsep = _n(nt, "ShaderNodeSeparateXYZ")
    _l(nt, geo.outputs["Normal"], nsep.inputs[0])
    steep = _n(nt, "ShaderNodeMapRange", **{"From Min": 0.97, "From Max": 0.85})
    _l(nt, nsep.outputs["Z"], steep.inputs["Value"])
    sm = _n(nt, "ShaderNodeMix", _data_type="RGBA")
    _l(nt, steep.outputs[0], sm.inputs["Factor"])
    _l(nt, mul.outputs[2], sm.inputs[6])
    sm.inputs[7].default_value = (0.11, 0.105, 0.045, 1)
    _l(nt, sm.outputs[2], bsdf.inputs["Base Color"])
    b = _n(nt, "ShaderNodeBump", Strength=0.35, Distance=0.3)
    _l(nt, g1.outputs["Fac"], b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.93
    bsdf.inputs["Specular IOR Level"].default_value = 0.25
    bsdf.inputs["Sheen Weight"].default_value = 0.08
    bsdf.inputs["Sheen Roughness"].default_value = 0.5
    bsdf.inputs["Sheen Tint"].default_value = (0.45, 0.6, 0.3, 1)
    return m


def build_terrain(coll, rmax=40000.0, nr=560, na=1080, r0=2.0):
    bm = bmesh.new()
    rings = []
    for i in range(nr):
        r = r0 * (rmax / r0) ** (i / (nr - 1))
        ring = []
        for j in range(na):
            a = 2 * math.pi * j / na
            x, y = r * math.cos(a), r * math.sin(a)
            ring.append(bm.verts.new((x, y, height(x, y))))
        rings.append(ring)
    for i in range(nr - 1):
        for j in range(na):
            k = (j + 1) % na
            bm.faces.new([rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]])
    bm.faces.new(rings[0])
    me = bpy.data.meshes.new("terrain")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("terrain", me)
    coll.objects.link(ob)
    me.materials.append(mat_terrain())
    return ob


# ---------------------------------------------------------------- water

def mat_water():
    m, nt, bsdf, out = _mat("river")
    tc = _n(nt, "ShaderNodeTexCoord")
    nz = _n(nt, "ShaderNodeTexNoise", Scale=1 / 1.5, Detail=6.0)
    _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
    b = _n(nt, "ShaderNodeBump", Strength=0.08, Distance=0.05)
    _l(nt, nz.outputs["Fac"], b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Base Color"].default_value = (0.012, 0.018, 0.012, 1)
    bsdf.inputs["Roughness"].default_value = 0.07
    bsdf.inputs["IOR"].default_value = 1.333
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    return m


def build_rivers(coll):
    bm = bmesh.new()
    for pts, w in RIVERS:
        prev = None
        for i, p in enumerate(pts):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, len(pts) - 1)]
            t = (b - a).normalized()
            nrm = Vector((-t.y, t.x, 0))
            ww = w * (1 + 0.15 * noise.noise(Vector((p.x / 80, p.y / 80, 0.5))))
            l_ = bm.verts.new((p.x + nrm.x * ww, p.y + nrm.y * ww, RIVER_Z))
            r_ = bm.verts.new((p.x - nrm.x * ww, p.y - nrm.y * ww, RIVER_Z))
            if prev:
                bm.faces.new([prev[0], prev[1], r_, l_])
            prev = (l_, r_)
    me = bpy.data.meshes.new("rivers")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("rivers", me)
    coll.objects.link(ob)
    me.materials.append(mat_water())
    return ob


# ---------------------------------------------------------------- vegetation

def mat_leaves(name="leaves", base=(0.035, 0.065, 0.018)):
    m, nt, bsdf, out = _mat(name)
    tc = _n(nt, "ShaderNodeTexCoord")
    oi = _n(nt, "ShaderNodeObjectInfo")
    vo = _n(nt, "ShaderNodeTexVoronoi", Scale=6.0)
    _l(nt, tc.outputs["Object"], vo.inputs["Vector"])
    nz = _n(nt, "ShaderNodeTexNoise", Scale=1.2, Detail=4.0)
    _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
    mixf = _n(nt, "ShaderNodeMath", _operation="ADD")
    _l(nt, nz.outputs["Fac"], mixf.inputs[0])
    _l(nt, oi.outputs["Random"], mixf.inputs[1])
    col = _ramp(nt, mixf.outputs[0], [(0.4, tuple(c * 0.75 for c in base)), (0.9, base),
                                      (1.4, (base[0] * 1.5, base[1] * 1.3, base[2] * 1.0))])
    ao = _n(nt, "ShaderNodeAmbientOcclusion", Distance=1.5, _samples=4)
    _l(nt, col.outputs[0], ao.inputs["Color"])
    _l(nt, ao.outputs["Color"], bsdf.inputs["Base Color"])
    b = _n(nt, "ShaderNodeBump", Strength=0.8, Distance=0.15)
    _l(nt, vo.outputs["Distance"], b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.65
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    tr = _n(nt, "ShaderNodeBsdfTranslucent")
    tcl = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    _l(nt, col.outputs[0], tcl.inputs[6])
    tcl.inputs[7].default_value = (1.4, 1.8, 0.6, 1)
    _l(nt, tcl.outputs[2], tr.inputs["Color"])
    _l(nt, b.outputs[0], tr.inputs["Normal"])
    mx = _n(nt, "ShaderNodeMixShader", Fac=0.25)
    _l(nt, bsdf.outputs[0], mx.inputs[1])
    _l(nt, tr.outputs[0], mx.inputs[2])
    _l(nt, mx.outputs[0], out.inputs["Surface"])
    return m


def mat_bark():
    m, nt, bsdf, out = _mat("bark")
    bsdf.inputs["Base Color"].default_value = (0.04, 0.032, 0.025, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    return m


def _blob_tree(name, coll, rng, crown_r, crown_h, trunk_h, trunk_r, n_lobes, leaves, bark,
               squash=1.0):
    bm = bmesh.new()
    lobes = []
    for k in range(n_lobes):
        th = rng.uniform(0, 2 * math.pi)
        ph = math.acos(rng.uniform(-0.6, 1.0))
        rr = crown_r * rng.uniform(0.35, 0.85)
        c = Vector((rr * math.sin(ph) * math.cos(th), rr * math.sin(ph) * math.sin(th),
                    trunk_h + crown_h * 0.5 + crown_h * 0.45 * math.cos(ph) * squash))
        lr = crown_r * rng.uniform(0.38, 0.6)
        lobes.append((c, lr))
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=lr * 0.92,
                                   matrix=Matrix.Translation(c) @ Matrix.Diagonal((1, 1, 0.85, 1)))
    # leaf clumps over the outer shell of the lobes break the silhouette up into sprays
    cen = Vector((0, 0, trunk_h + crown_h * 0.5))
    n_cl = int(320 + 200 * min(1.0, crown_r / 5.0))
    for k in range(n_cl):
        c, lr = lobes[rng.randrange(len(lobes))]
        d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1) * 0.8 + 0.25)).normalized()
        if d.dot((c - cen).normalized() if (c - cen).length > 1e-3 else d) < -0.2:
            d = -d
        p = c + d * lr * rng.uniform(0.80, 0.98)
        r = crown_r * rng.uniform(0.055, 0.11)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r,
                                   matrix=Matrix.Translation(p) @ Matrix.Diagonal((1, 1, 0.8, 1)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    crown = bpy.data.objects.new(name, me)
    coll.objects.link(crown)
    tex = bpy.data.textures.new(name + "_d", "VORONOI")
    tex.noise_scale = crown_r * 0.18
    dp = crown.modifiers.new("d", "DISPLACE")
    dp.texture, dp.strength, dp.mid_level = tex, crown_r * 0.12, 0.6
    tex2 = bpy.data.textures.new(name + "_c", "CLOUDS")
    tex2.noise_scale = crown_r * 0.5
    dp2 = crown.modifiers.new("d2", "DISPLACE")
    dp2.texture, dp2.strength = tex2, crown_r * 0.25
    with bpy.context.temp_override(object=crown, active_object=crown):
        for mname in ("d", "d2"):
            bpy.ops.object.modifier_apply(modifier=mname)
    me.materials.append(leaves)
    for p in me.polygons:
        p.use_smooth = True
    if trunk_h > 0:
        # trunk appended to the crown mesh (material slot 1)
        me.materials.append(bark)
        bm = bmesh.new()
        bm.from_mesh(me)
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=trunk_r,
                                  radius2=trunk_r * 0.6, depth=trunk_h + crown_h * 0.4,
                                  matrix=Matrix.Translation((0, 0, (trunk_h + crown_h * 0.4) / 2 - 0.3)))
        vs = set(r["verts"])
        for f in bm.faces:
            if all(v in vs for v in f.verts):
                f.material_index = 1
                f.smooth = True
        bm.to_mesh(me)
        bm.free()
    return crown


def tree_library():
    """Instance prototypes: 0-2 broadleaf standards (oak/ash/elm-like), 3 willow/alder,
    4-5 hedge bushes, 6 orchard/garden tree."""
    coll = bpy.data.collections.new("tree_protos")
    rng = random.Random(4)
    lv = [mat_leaves("leaves_oak", (0.040, 0.075, 0.020)),
          mat_leaves("leaves_ash", (0.052, 0.090, 0.026)),
          mat_leaves("leaves_willow", (0.070, 0.095, 0.045)),
          mat_leaves("leaves_hedge", (0.042, 0.078, 0.022))]
    bark = mat_bark()
    specs = [("oak", 5.5, 8.0, 3.5, 0.35, 22, lv[0]), ("ash", 4.5, 9.0, 4.5, 0.3, 18, lv[1]),
             ("elm", 4.0, 11.0, 4.0, 0.3, 18, lv[0]), ("willow", 3.8, 5.5, 2.2, 0.35, 16, lv[2]),
             ("hedge_a", 1.6, 2.4, 0.0, 0.0, 6, lv[3]), ("hedge_b", 1.9, 2.8, 0.0, 0.0, 7, lv[3]),
             ("apple", 2.6, 3.0, 1.3, 0.15, 10, lv[1])]
    for i, (nm, cr, ch, th, trr, nl, lmat) in enumerate(specs):
        ob = _blob_tree(f"{i}_{nm}", coll, rng, cr, ch, th, trr, nl, lmat, bark)
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    return coll


def scatter_node_group(protos):
    ng = bpy.data.node_groups.new("scatter", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = protos
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    ci.transform_space = "ORIGINAL"
    iop = N.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    k = N.new("GeometryNodeInputNamedAttribute")
    k.data_type, k.inputs["Name"].default_value = "INT", "kind"
    sc = N.new("GeometryNodeInputNamedAttribute")
    sc.data_type, sc.inputs["Name"].default_value = "FLOAT", "scale"
    ro = N.new("GeometryNodeInputNamedAttribute")
    ro.data_type, ro.inputs["Name"].default_value = "FLOAT", "rot"
    cx = N.new("ShaderNodeCombineXYZ")
    L = ng.links
    L.new(ro.outputs["Attribute"], cx.inputs["Z"])
    L.new(gi.outputs[0], m2p.inputs["Mesh"])
    L.new(m2p.outputs[0], iop.inputs["Points"])
    L.new(ci.outputs[0], iop.inputs["Instance"])
    L.new(k.outputs["Attribute"], iop.inputs["Instance Index"])
    L.new(sc.outputs["Attribute"], iop.inputs["Scale"])
    L.new(cx.outputs[0], iop.inputs["Rotation"])
    L.new(iop.outputs[0], go.inputs[0])
    return ng


def scatter(coll, name, pts, protos):
    """pts: list of (x, y, z, kind, scale, rot)."""
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pts))
    me.vertices.foreach_set("co", [c for p in pts for c in p[:3]])
    for an, typ, idx in (("kind", "INT", 3), ("scale", "FLOAT", 4), ("rot", "FLOAT", 5)):
        a = me.attributes.new(an, typ, "POINT")
        a.data.foreach_set("value", [p[idx] for p in pts])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    md = ob.modifiers.new("scatter", "NODES")
    md.node_group = scatter_node_group(protos)
    return ob


def vegetation_points(seed=2, near=4200.0):
    rng = random.Random(seed)
    rgb, hedge, kind = field_map()
    N = hedge.shape[0]
    px = DOMAIN / N
    pts = []
    ys, xs = np.nonzero(hedge > 0.5)
    for iy, ix in zip(ys, xs):
        x = (ix + 0.5) * px - DOMAIN / 2 + rng.uniform(-1, 1)
        y = (iy + 0.5) * px - DOMAIN / 2 + rng.uniform(-1, 1)
        r = math.hypot(x, y)
        if r > near or r < 60:
            continue
        # bushes every ~2.5 m (2 per px), hedgerow standards every ~40 m
        for _ in range(2 if r < 1500 else 1):
            xx, yy = x + rng.uniform(-px / 2, px / 2), y + rng.uniform(-px / 2, px / 2)
            pts.append((xx, yy, height(xx, yy) - 0.3, 4 + rng.randrange(2),
                        rng.uniform(0.75, 1.25) * (1.0 if r < 1500 else 1.3), rng.uniform(0, 6.3)))
        if rng.random() < 0.075:
            pts.append((x, y, height(x, y) - 0.4, rng.choice((0, 0, 1, 2)), rng.uniform(0.8, 1.25),
                        rng.uniform(0, 6.3)))
    # woods: fill fields of kind 5 with trees
    wy, wx = np.nonzero(kind == 5)
    for iy, ix in zip(wy[::2], wx[::2]):
        x = (ix + 0.5) * px - DOMAIN / 2 + rng.uniform(-2, 2)
        y = (iy + 0.5) * px - DOMAIN / 2 + rng.uniform(-2, 2)
        if math.hypot(x, y) > near:
            continue
        pts.append((x, y, height(x, y) - 0.4, rng.choice((0, 1, 1, 2)), rng.uniform(0.75, 1.2),
                    rng.uniform(0, 6.3)))
    # riverside willows and alders
    for rpts, w in RIVERS:
        for p in rpts[::2]:
            if rng.random() < 0.55:
                side = rng.choice((-1, 1))
                off = w + rng.uniform(2, 8)
                i = rpts.index(p)
                t = (rpts[min(i + 1, len(rpts) - 1)] - rpts[max(i - 1, 0)]).normalized()
                nx, ny = -t.y * side, t.x * side
                x, y = p.x + nx * off, p.y + ny * off
                if math.hypot(x, y) < near:
                    pts.append((x, y, height(x, y) - 0.3, 3, rng.uniform(0.8, 1.3), rng.uniform(0, 6.3)))
    return pts


# ---------------------------------------------------------------- the town

def mat_thatch():
    m, nt, bsdf, out = _mat("thatch")
    tc = _n(nt, "ShaderNodeTexCoord")
    mp = _n(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (30.0, 30.0, 3.0)
    _l(nt, tc.outputs["Object"], mp.inputs["Vector"])
    st = _n(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=8.0, Roughness=0.7)
    _l(nt, mp.outputs[0], st.inputs["Vector"])
    big = _n(nt, "ShaderNodeTexNoise", Scale=0.4, Detail=4.0)
    _l(nt, tc.outputs["Object"], big.inputs["Vector"])
    oi = _n(nt, "ShaderNodeObjectInfo")
    add = _n(nt, "ShaderNodeMath", _operation="ADD")
    _l(nt, big.outputs["Fac"], add.inputs[0])
    att = _n(nt, "ShaderNodeAttribute", _attribute_name="age")
    _l(nt, att.outputs["Fac"], add.inputs[1])
    # weathered (greyed) straw, darker where older; moss/algae patches
    col = _ramp(nt, add.outputs[0], [(0.4, (0.28, 0.225, 0.15)), (0.8, (0.19, 0.155, 0.105)),
                                     (1.3, (0.11, 0.095, 0.07))])
    moss = _n(nt, "ShaderNodeTexNoise", Scale=1.3, Detail=5.0, Roughness=0.65)
    _l(nt, tc.outputs["Object"], moss.inputs["Vector"])
    mf = _ramp(nt, moss.outputs["Fac"], [(0.58, (0, 0, 0)), (0.7, (0.55, 0.55, 0.55))])
    mix = _n(nt, "ShaderNodeMix", _data_type="RGBA")
    _l(nt, mf.outputs[0], mix.inputs["Factor"])
    _l(nt, col.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (0.07, 0.08, 0.04, 1)
    ao = _n(nt, "ShaderNodeAmbientOcclusion", Distance=0.6, _samples=4)
    _l(nt, mix.outputs[2], ao.inputs["Color"])
    _l(nt, ao.outputs["Color"], bsdf.inputs["Base Color"])
    # thatching courses: horizontal bands ~0.35 m apart, wavy, plus the straw streaks
    wv = _n(nt, "ShaderNodeTexWave", Scale=1.8, Distortion=2.0, Detail=3.0)
    wv.bands_direction = "Z"
    _l(nt, tc.outputs["Object"], wv.inputs["Vector"])
    hb = _n(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    _l(nt, wv.outputs["Fac"], hb.inputs[0])
    hb.inputs[1].default_value = 0.6
    _l(nt, st.outputs["Fac"], hb.inputs[2])
    b = _n(nt, "ShaderNodeBump", Strength=0.6, Distance=0.05)
    _l(nt, hb.outputs[0], b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.95
    bsdf.inputs["Specular IOR Level"].default_value = 0.2
    bsdf.inputs["Sheen Weight"].default_value = 0.08
    bsdf.inputs["Sheen Tint"].default_value = (0.9, 0.75, 0.5, 1)
    return m


def mat_daub():
    m, nt, bsdf, out = _mat("daub")
    tc = _n(nt, "ShaderNodeTexCoord")
    nz = _n(nt, "ShaderNodeTexNoise", Scale=1.5, Detail=8.0)
    _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
    att = _n(nt, "ShaderNodeAttribute", _attribute_name="age")
    add = _n(nt, "ShaderNodeMath", _operation="ADD")
    _l(nt, nz.outputs["Fac"], add.inputs[0])
    _l(nt, att.outputs["Fac"], add.inputs[1])
    col = _ramp(nt, add.outputs[0], [(0.4, (0.25, 0.21, 0.15)), (0.9, (0.18, 0.145, 0.10)),
                                     (1.3, (0.11, 0.085, 0.06))])
    _l(nt, col.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.95
    return m


def mat_timber():
    m, nt, bsdf, out = _mat("timber")
    bsdf.inputs["Base Color"].default_value = (0.05, 0.035, 0.022, 1)
    bsdf.inputs["Roughness"].default_value = 0.85
    return m


def _house(bm, age_l, c, ang, L, W, eave, pitch_deg=52, over=0.45):
    """Rectangular post-and-wattle house with a steep thatched gable roof (hipped if odd)."""
    R = Matrix.Rotation(ang, 4, "Z")
    T = Matrix.Translation(c)
    ridge = eave + (W / 2 + over) * math.tan(math.radians(pitch_deg))
    walls = bmesh.ops.create_cube(bm, size=1.0, matrix=T @ R @ Matrix.Translation((0, 0, eave / 2 - 0.3))
                                  @ Matrix.Diagonal((L, W, eave + 0.6, 1)))["verts"]
    # roof: prism with overhang, thick
    hw, hl = W / 2 + over, L / 2 + over * 0.6
    th = 0.35
    vs = [(-hl, -hw, eave - 0.1), (hl, -hw, eave - 0.1), (hl, hw, eave - 0.1), (-hl, hw, eave - 0.1),
          (-hl + 0.0, 0, ridge), (hl, 0, ridge)]
    M = T @ R
    v = [bm.verts.new(M @ Vector(p)) for p in vs]
    vi = [bm.verts.new(M @ (Vector(p) + Vector((0, 0, -th)))) for p in vs[:4]]
    faces = [(v[0], v[1], v[5], v[4]), (v[2], v[3], v[4], v[5]), (v[0], v[4], v[3]),
             (v[1], v[2], v[5]), (vi[0], vi[3], vi[2], vi[1]),
             (v[0], vi[0], vi[1], v[1]), (v[2], vi[2], vi[3], v[3]),
             (v[1], vi[1], vi[2], v[2]), (v[3], vi[3], vi[0], v[0])]
    roof = []
    for f in faces:
        try:
            roof.append(bm.faces.new(f))
        except ValueError:
            pass
    return walls, roof


def _box(bm, M, c, size):
    bmesh.ops.create_cube(bm, size=1.0, matrix=M @ Matrix.Translation(c) @
                          Matrix.Diagonal((size[0], size[1], size[2], 1)))


def _thatch_roof(bm, M, hl, hw, z_eave, H, rng, th=0.42, core_k=0.62, p=5.0, e=0.05,
                 nr=12, nt=72, soff=(0.86, 0.72, 0.15)):
    """Thick hipped thatch with a rounded ridge and rounded hips, as a closed shell.

    Rings of constant 'level' r (1 at the eaves drip, 0 at the ridge) are superellipses of
    semi-axes (core + r*(hl-core), r*hw); height falls from the ridge with a rounded crown.
    Below the drip ring a vertical skirt shows the thatch thickness; the soffit closes it.
    """
    core = hl - hw * core_k
    ph = rng.uniform(0, 6.3)
    f1 = math.sqrt(1 + e * e) - e

    def pt(r, th_):
        c, s = math.cos(th_), math.sin(th_)
        ex = math.copysign(abs(c) ** (2 / p), c)
        ey = math.copysign(abs(s) ** (2 / p), s)
        x = ex * (core + r * (hl - core))
        y = ey * r * hw
        z = z_eave + H * (math.sqrt(1 + e * e) - math.sqrt(r * r + e * e)) / f1
        # lumpy, sagging old thatch: low-frequency waves, a slightly wavy drip line
        z += 0.06 * math.sin(3 * th_ + ph) * r + 0.04 * math.sin(7 * th_ + 2 * ph) * r
        z -= 0.10 * (1 - abs(ex)) * (1 - r) * (1 - r)          # ridge sags between the hips
        return Vector((x, y, z))

    rings = []
    levels = [1.0 - (i / nr) ** 1.15 * 0.985 for i in range(nr + 1)]
    for r in levels:
        rings.append([bm.verts.new(M @ pt(r, 2 * math.pi * k / nt)) for k in range(nt)])
    # eaves skirt (thickness) and soffit
    drip = []
    for k in range(nt):
        q = pt(1.0, 2 * math.pi * k / nt)
        q2 = Vector((q.x * 0.985, q.y * 0.96, q.z - th))
        drip.append(bm.verts.new(M @ q2))
    sof = []
    for k in range(nt):
        q = pt(1.0, 2 * math.pi * k / nt)
        sof.append(bm.verts.new(M @ Vector((q.x * soff[0], q.y * soff[1], z_eave + soff[2]))))
    faces = []
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(nt):
            faces.append((a[k], a[(k + 1) % nt], b[(k + 1) % nt], b[k]))
    for k in range(nt):
        faces.append((drip[k], drip[(k + 1) % nt], rings[0][(k + 1) % nt], rings[0][k]))
        faces.append((sof[k], sof[(k + 1) % nt], drip[(k + 1) % nt], drip[k]))
    out = []
    for f in faces:
        try:
            out.append(bm.faces.new(f))
        except ValueError:
            pass
    out.append(bm.faces.new(list(reversed(rings[-1]))))
    out.append(bm.faces.new(sof))
    return out


def _saxon_house(bms, c, ang, L, W, eave, rng):
    """Late-Saxon post-built hall: low wattle-and-daub walls between earth-fast oak posts, a
    wall plate, a plank door; a deep, thick hipped thatch with a rounded ridge oversailing the
    walls by ~0.7 m, its drip low (~1.5 m) over the walls."""
    walls, timber, thatch = bms
    M = Matrix.Translation(c) @ Matrix.Rotation(ang, 4, "Z")
    hl, hw = L / 2, W / 2
    zb = -0.6                                       # sunk into the ground on slopes
    _box(walls, M, (0, 0, (eave + zb) / 2), (L - 0.1, W - 0.1, eave - zb))
    # earth-fast posts along the long walls and at the corners; plate on top
    n = max(3, int(round(L / 1.3)))
    for i in range(n + 1):
        x = -hl + L * i / n
        for y in (-hw, hw):
            _box(timber, M, (x, y, (eave + zb) / 2), (0.2, 0.2, eave - zb))
    for y in (-hw / 3, hw / 3):
        for x in (-hl, hl):
            _box(timber, M, (x, y, (eave + zb) / 2), (0.2, 0.2, eave - zb))
    for y in (-hw, hw):
        _box(timber, M, (0, y, eave - 0.06), (L + 0.2, 0.22, 0.16))
    # plank door (dark) in one long wall, with its frame posts
    dx = rng.uniform(-hl * 0.4, hl * 0.4)
    side = rng.choice((-1, 1))
    _box(timber, M, (dx, side * (hw + 0.02), 0.85), (0.95, 0.06, 1.7))
    # the roof
    over = rng.uniform(0.6, 0.8)
    pitch = math.radians(rng.uniform(50, 55))
    rw = hw + over
    H = rw * math.tan(pitch)
    rl = hl + over * 0.9
    thatch_faces = _thatch_roof(thatch, M, rl, rw, eave - 0.35, H, rng,
                                soff=(hl / rl, hw / rw, 0.30))
    return thatch_faces, H


def _smoke(coll, x, y, z, rng, h=7.0):
    """A thin column of hearth smoke from the roof (a tall noise-shaped volume)."""
    me = bpy.data.meshes.new("smoke")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("smoke", me)
    coll.objects.link(ob)
    drift = rng.uniform(0.6, 1.0)
    ob.location = (x + 1.5 * drift, y + 1.5 * drift, z + h / 2)
    ob.scale = (h * 0.45, h * 0.45, h / 2)
    m = bpy.data.materials.get("smoke")
    if m is None:
        m = bpy.data.materials.new("smoke")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.remove(nt.nodes["Principled BSDF"])
        out = nt.nodes["Material Output"]
        tc = _n(nt, "ShaderNodeTexCoord")
        # column: radius growing with height, leaning downwind, broken up by noise
        sep = _n(nt, "ShaderNodeSeparateXYZ")
        _l(nt, tc.outputs["Generated"], sep.inputs[0])
        fz = sep.outputs["Z"]
        lean = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
        _l(nt, fz, lean.inputs[0])
        lean.inputs[1].default_value = 0.32
        cx = _n(nt, "ShaderNodeMath", _operation="SUBTRACT")
        _l(nt, sep.outputs["X"], cx.inputs[0])
        cx.inputs[1].default_value = 0.5
        cy = _n(nt, "ShaderNodeMath", _operation="SUBTRACT")
        _l(nt, sep.outputs["Y"], cy.inputs[0])
        cy.inputs[1].default_value = 0.5
        cx2 = _n(nt, "ShaderNodeMath", _operation="ADD")
        _l(nt, cx.outputs[0], cx2.inputs[0])
        _l(nt, lean.outputs[0], cx2.inputs[1])
        cy2 = _n(nt, "ShaderNodeMath", _operation="ADD")
        _l(nt, cy.outputs[0], cy2.inputs[0])
        _l(nt, lean.outputs[0], cy2.inputs[1])
        comb = _n(nt, "ShaderNodeCombineXYZ")
        _l(nt, cx2.outputs[0], comb.inputs[0])
        _l(nt, cy2.outputs[0], comb.inputs[1])
        rad = _n(nt, "ShaderNodeVectorMath", _operation="LENGTH")
        _l(nt, comb.outputs[0], rad.inputs[0])
        rmax = _n(nt, "ShaderNodeMapRange")
        _l(nt, fz, rmax.inputs["Value"])
        rmax.inputs["To Min"].default_value = 0.03
        rmax.inputs["To Max"].default_value = 0.17
        div = _n(nt, "ShaderNodeMath", _operation="DIVIDE")
        _l(nt, rad.outputs["Value"], div.inputs[0])
        _l(nt, rmax.outputs["Result"], div.inputs[1])
        prof = _n(nt, "ShaderNodeMapRange", _clamp=True)
        _l(nt, div.outputs[0], prof.inputs["Value"])
        prof.inputs["To Min"].default_value = 1.0
        prof.inputs["To Max"].default_value = 0.0
        nz = _n(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=6.0, Roughness=0.6)
        _l(nt, tc.outputs["Object"], nz.inputs["Vector"])
        fade = _n(nt, "ShaderNodeMapRange", _clamp=True)
        _l(nt, fz, fade.inputs["Value"])
        fade.inputs["To Min"].default_value = 1.0
        fade.inputs["To Max"].default_value = 0.0
        m1 = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
        _l(nt, prof.outputs["Result"], m1.inputs[0])
        _l(nt, nz.outputs["Fac"], m1.inputs[1])
        m2 = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
        _l(nt, m1.outputs[0], m2.inputs[0])
        _l(nt, fade.outputs["Result"], m2.inputs[1])
        m3 = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
        _l(nt, m2.outputs[0], m3.inputs[0])
        m3.inputs[1].default_value = 0.9
        vol = _n(nt, "ShaderNodeVolumePrincipled")
        vol.inputs["Color"].default_value = (0.62, 0.62, 0.64, 1)
        vol.inputs["Anisotropy"].default_value = 0.45
        _l(nt, m3.outputs[0], vol.inputs["Density"])
        _l(nt, vol.outputs[0], out.inputs["Volume"])
    me.materials.append(m)
    return ob


def build_town_saxon(coll, seed=8, keep_out=(), skip=0.55, smoke=3):
    """Fewer, smaller post-built halls with thick hipped thatch (see _saxon_house)."""
    rng = random.Random(seed)
    houses = []
    streets = [(-60.0, (-1150, 120)), (75.0, (-1100, 125)), (-150.0, (-900, 60)),
               (32.0, (-520, 40))]
    for dline, (s0, s1) in streets:
        s = s0
        while s < s1:
            for side in (-1, 1):
                if rng.random() < skip:
                    continue
                L, W = rng.uniform(6.5, 10.0), rng.uniform(4.2, 5.2)
                d = dline + side * (W / 2 + rng.uniform(5, 9))
                ss = s + rng.uniform(-3, 3)
                x, y = xy(ss, d)
                if math.hypot(x - 18, y) < 45:
                    continue
                if abs(d) > HALF_W - 25 or ss > EDGE_S - 18:
                    continue
                if any(math.hypot(x - kx, y - ky) < kr for kx, ky, kr in keep_out):
                    continue
                houses.append((x, y, math.radians(90 - FLIGHT_AZ) + rng.uniform(-0.12, 0.12),
                               L, W, rng.uniform(1.75, 2.05)))
                if rng.random() < 0.25:
                    d2 = d + side * rng.uniform(16, 26)
                    x2, y2 = xy(ss + rng.uniform(-4, 4), d2)
                    if abs(d2) < HALF_W - 25 and math.hypot(x2 - 18, y2) > 45 and \
                            not any(math.hypot(x2 - kx, y2 - ky) < kr for kx, ky, kr in keep_out):
                        houses.append((x2, y2, math.radians(90 - FLIGHT_AZ) + math.pi / 2 +
                                       rng.uniform(-0.15, 0.15), rng.uniform(4.5, 6.5),
                                       rng.uniform(3.4, 4.2), rng.uniform(1.6, 1.9)))
            s += rng.uniform(14, 22)
    bms = [bmesh.new(), bmesh.new(), bmesh.new()]
    ages, ridges = [[], [], []], []
    for (x, y, ang, L, W, eave) in houses:
        z = min(height(x + dx, y + dy) for dx in (-4, 4) for dy in (-4, 4))
        n0 = [len(b.verts) for b in bms]
        _, H = _saxon_house(bms, Vector((x, y, z)), ang, L, W, eave, rng)
        a = rng.uniform(0.0, 0.5)
        for i, b in enumerate(bms):
            ages[i] += [a] * (len(b.verts) - n0[i])
        ridges.append((x, y, z + eave - 0.35 + H))
    obs = []
    for nm, bm, mat, ag in zip(("town_walls", "town_timber", "town_thatch"), bms,
                               (mat_daub(), mat_timber(), mat_thatch()), ages):
        me = bpy.data.meshes.new(nm)
        bm.to_mesh(me)
        bm.free()
        at = me.attributes.new("age", "FLOAT", "POINT")
        at.data.foreach_set("value", ag)
        for p in me.polygons:
            p.use_smooth = nm == "town_thatch"
        me.materials.append(mat)
        ob = bpy.data.objects.new(nm, me)
        coll.objects.link(ob)
        obs.append(ob)
    # hearth smoke seeps through the thatch of a few houses
    for (x, y, zr) in rng.sample(ridges, min(smoke, len(ridges))):
        _smoke(coll, x, y, zr - 0.3, rng)
    return obs[2], houses


def build_town(coll, seed=8):
    rng = random.Random(seed)
    lay_bm = bmesh.new()
    roof_bm = bmesh.new()
    houses = []
    # street lines along the spur, plots either side; a cross street; the abbey precinct clear
    streets = [(-60.0, (-1150, 120)), (75.0, (-1100, 125)), (-150.0, (-900, 60)),
               (32.0, (-520, 40))]
    for dline, (s0, s1) in streets:
        s = s0
        while s < s1:
            for side in (-1, 1):
                if rng.random() < 0.22:
                    continue
                L, W = rng.uniform(7, 12), rng.uniform(4.5, 6.0)
                d = dline + side * (W / 2 + rng.uniform(4, 7))
                ss = s + rng.uniform(-2, 2)
                x, y = xy(ss, d)
                if math.hypot(x - 18, y) < 45:          # church and precinct
                    continue
                if abs(d) > HALF_W - 25 or ss > EDGE_S - 18:
                    continue
                houses.append((x, y, math.radians(90 - FLIGHT_AZ) + rng.uniform(-0.06, 0.06),
                               L, W, rng.uniform(2.2, 2.8)))
                # back buildings in the plots
                if rng.random() < 0.35:
                    d2 = d + side * rng.uniform(14, 24)
                    if abs(d2) < HALF_W - 25:
                        x2, y2 = xy(ss + rng.uniform(-3, 3), d2)
                        if math.hypot(x2 - 18, y2) > 45:
                            houses.append((x2, y2, math.radians(90 - FLIGHT_AZ) + math.pi / 2 +
                                           rng.uniform(-0.1, 0.1), rng.uniform(5, 8),
                                           rng.uniform(3.5, 4.5), rng.uniform(2.0, 2.4)))
            s += rng.uniform(11, 17)
    for (x, y, ang, L, W, eave) in houses:
        z = min(height(x + dx, y + dy) for dx in (-4, 4) for dy in (-4, 4))
        _house(roof_bm, None, Vector((x, y, z)), ang, L, W, eave)
    # split walls vs roofs by face normal / height into two materials
    me = bpy.data.meshes.new("town")
    roof_bm.to_mesh(me)
    roof_bm.free()
    lay_bm.free()
    ob = bpy.data.objects.new("town", me)
    coll.objects.link(ob)
    me.materials.append(mat_daub())
    me.materials.append(mat_thatch())
    # roofs are the faces not belonging to the wall cubes: tag by vertex count order
    # (each house = 8 cube verts then 10 roof verts)
    per = 18
    age = me.attributes.new("age", "FLOAT", "POINT")
    vals = []
    for i in range(len(me.vertices)):
        vals.append(random.Random(i // per).uniform(0.0, 0.5))
    age.data.foreach_set("value", vals)
    for p in me.polygons:
        if (p.vertices[0] % per) >= 8:
            p.material_index = 1
    return ob, houses
