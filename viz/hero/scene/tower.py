"""A modest pre-Conquest church tower top and nave in local oolitic limestone.

Coursed rubble walling (Poly Haven 'castle_wall_varriation', CC0, true displacement) with
dressed quoins at the corners, a plain parapet with rough coping slabs, a stone-flag roof
and one plain round-headed belfry opening per face. No ornament is invented: the Anglo-Saxon
tower at Malmesbury does not survive, so this is a generic, minimal form.

Local frame: tower centred on the origin, faces aligned with the world axes (church
oriented east-west, nave to the east). z = 0 at the plateau; ROOF is the roof surface.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

TEX = Path(__file__).resolve().parent.parent / "assets" / "_dl" / "tex"

SIDE = 7.6          # external width (m)
HEIGHT = 17.0       # plateau to roof surface
WALL = 1.0
PARAPET = 1.05      # above the roof surface (top of coping)
PAR_T = 0.6
ROOF = HEIGHT


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


def _img(nt, name, non_color=False, proj="BOX"):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(str(TEX / name), check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    n.projection = proj
    n.projection_blend = 0.2
    return n


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


def weathering(nt, base_col, co, z_top, lichen_amt=1.0, up_w=0.16, top_grime=0.0):
    """Rain streaks below ledges, sooty grime, lichen crusts (grey-green, yellow Xanthoria,
    white), moss and algae near the ground. Returns (colour socket, lichen mask socket)."""
    sep = _n(nt, "ShaderNodeSeparateXYZ")
    _l(nt, co, sep.inputs[0])
    smp = _n(nt, "ShaderNodeMapping")
    smp.inputs["Scale"].default_value = (2.2, 2.2, 0.12)
    _l(nt, co, smp.inputs["Vector"])
    streak = _n(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=6.0, Roughness=0.6)
    _l(nt, smp.outputs[0], streak.inputs["Vector"])
    sk = _ramp(nt, streak.outputs["Fac"], [(0.38, (1, 1, 1)), (0.68, (0.62, 0.60, 0.58))])
    dirty = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    _l(nt, base_col, dirty.inputs[6])
    _l(nt, sk.outputs[0], dirty.inputs[7])
    # lichen: favour upward-facing and near-top surfaces
    geo = _n(nt, "ShaderNodeNewGeometry")
    ns = _n(nt, "ShaderNodeSeparateXYZ")
    _l(nt, geo.outputs["Normal"], ns.inputs[0])
    l1 = _n(nt, "ShaderNodeTexNoise", Scale=3.5, Detail=12.0, Roughness=0.72)
    _l(nt, co, l1.inputs["Vector"])
    l2 = _n(nt, "ShaderNodeTexVoronoi", Scale=9.0)
    _l(nt, co, l2.inputs["Vector"])
    hi = _n(nt, "ShaderNodeMapRange", **{"From Min": z_top - 6.0, "From Max": z_top})
    _l(nt, sep.outputs["Z"], hi.inputs["Value"])
    up = _n(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    _l(nt, ns.outputs["Z"], up.inputs[0])
    up.inputs[1].default_value, up.inputs[2].default_value = up_w, 0.0
    acc = _n(nt, "ShaderNodeMath", _operation="ADD")
    _l(nt, l1.outputs["Fac"], acc.inputs[0])
    _l(nt, up.outputs[0], acc.inputs[1])
    acc2 = _n(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    _l(nt, hi.outputs[0], acc2.inputs[0])
    acc2.inputs[1].default_value = 0.08 * lichen_amt
    _l(nt, acc.outputs[0], acc2.inputs[2])
    lm = _ramp(nt, acc2.outputs[0], [(0.60, (0, 0, 0)), (0.64, (1, 1, 1))])
    # lichen species by a second noise: grey-green crust / yellow-orange / pale grey
    sp = _n(nt, "ShaderNodeTexNoise", Scale=1.3, Detail=2.0)
    _l(nt, co, sp.inputs["Vector"])
    lc = _ramp(nt, sp.outputs["Fac"], [(0.35, (0.30, 0.31, 0.22)), (0.5, (0.42, 0.42, 0.36)),
                                       (0.62, (0.50, 0.33, 0.07)), (0.7, (0.42, 0.40, 0.33))])
    spots = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
    _l(nt, lm.outputs[0], spots.inputs[0])
    sr = _ramp(nt, l2.outputs["Distance"], [(0.15, (1, 1, 1)), (0.5, (0.55, 0.55, 0.55))])
    _l(nt, sr.outputs[0], spots.inputs[1])
    mixl = _n(nt, "ShaderNodeMix", _data_type="RGBA")
    _l(nt, spots.outputs[0], mixl.inputs["Factor"])
    _l(nt, dirty.outputs[2], mixl.inputs[6])
    _l(nt, lc.outputs[0], mixl.inputs[7])
    # green algae / moss toward the ground
    lo = _n(nt, "ShaderNodeMapRange", **{"From Min": 2.5, "From Max": 0.0})
    _l(nt, sep.outputs["Z"], lo.inputs["Value"])
    mg = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    _l(nt, lo.outputs[0], mg.inputs["Factor"])
    _l(nt, mixl.outputs[2], mg.inputs[6])
    mg.inputs[7].default_value = (0.55, 0.65, 0.38, 1)
    if not top_grime:
        return mg.outputs[2], spots.outputs[0]
    # the exposed top courses: rain run-off from the coping, darker and greener, in
    # vertical streaks that fade down the wall
    tg = _n(nt, "ShaderNodeMapRange", **{"From Min": z_top - 2.6, "From Max": z_top - 0.2})
    _l(nt, sep.outputs["Z"], tg.inputs["Value"])
    smp2 = _n(nt, "ShaderNodeMapping")
    smp2.inputs["Scale"].default_value = (5.0, 5.0, 0.35)
    _l(nt, co, smp2.inputs["Vector"])
    st2 = _n(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=5.0, Roughness=0.6)
    _l(nt, smp2.outputs[0], st2.inputs["Vector"])
    st2r = _ramp(nt, st2.outputs["Fac"], [(0.35, (0.25, 0.25, 0.25)), (0.65, (1, 1, 1))])
    f = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
    _l(nt, tg.outputs[0], f.inputs[0])
    _l(nt, st2r.outputs[0], f.inputs[1])
    f2 = _n(nt, "ShaderNodeMath", _operation="MULTIPLY")
    _l(nt, f.outputs[0], f2.inputs[0])
    f2.inputs[1].default_value = top_grime
    gm = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    _l(nt, f2.outputs[0], gm.inputs["Factor"])
    _l(nt, mg.outputs[2], gm.inputs[6])
    gm.inputs[7].default_value = (0.52, 0.53, 0.44, 1)
    return gm.outputs[2], spots.outputs[0]


def mat_rubble_wall(z_top, top_grime=0.0):
    m, nt, bsdf, out = _mat("rubble_wall")
    tc = _n(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    mp = _n(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)          # texture spans 2 m
    _l(nt, co, mp.inputs["Vector"])
    dif = _img(nt, "castle_wall_varriation_diff_4k.jpg")
    nor = _img(nt, "castle_wall_varriation_nor_gl_4k.jpg", True)
    rgh = _img(nt, "castle_wall_varriation_rough_4k.jpg", True)
    dsp = _img(nt, "castle_wall_varriation_disp_4k.jpg", True)
    for i in (dif, nor, rgh, dsp):
        _l(nt, mp.outputs[0], i.inputs[0])
    # Cotswold oolite: warm honey-grey; per-stone variation from a voronoi on the same scale
    hsv = _n(nt, "ShaderNodeHueSaturation", Hue=0.51, Saturation=0.95, Value=1.12)
    _l(nt, dif.outputs[0], hsv.inputs["Color"])
    tint = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    _l(nt, hsv.outputs[0], tint.inputs[6])
    # broad tonal drift between lifts of walling hides the 2 m texture repeat
    big = _n(nt, "ShaderNodeTexNoise", Scale=0.35, Detail=3.0)
    _l(nt, co, big.inputs["Vector"])
    bigc = _ramp(nt, big.outputs["Fac"], [(0.3, (0.82, 0.80, 0.76)), (0.5, (1.0, 0.96, 0.88)),
                                          (0.7, (1.1, 1.0, 0.86))])
    _l(nt, bigc.outputs[0], tint.inputs[7])
    col, lich = weathering(nt, tint.outputs[2], co, z_top, top_grime=top_grime)
    ao = _n(nt, "ShaderNodeAmbientOcclusion", Distance=0.12, _samples=8)
    _l(nt, col, ao.inputs["Color"])
    _l(nt, ao.outputs["Color"], bsdf.inputs["Base Color"])
    nm = _n(nt, "ShaderNodeNormalMap", Strength=1.0)
    _l(nt, nor.outputs[0], nm.inputs["Color"])
    lb = _n(nt, "ShaderNodeBump", Strength=0.4, Distance=0.002)
    _l(nt, lich, lb.inputs["Height"])
    _l(nt, nm.outputs[0], lb.inputs["Normal"])
    _l(nt, lb.outputs[0], bsdf.inputs["Normal"])
    _l(nt, rgh.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    d = _n(nt, "ShaderNodeDisplacement", Scale=0.06, Midlevel=0.5)
    _l(nt, dsp.outputs[0], d.inputs["Height"])
    _l(nt, d.outputs[0], out.inputs["Displacement"])
    m.displacement_method = "BOTH"
    return m


def mat_ashlar(z_top, name="ashlar", lichen=1.3, up_w=0.16, top_grime=0.0):
    """Dressed oolitic limestone (quoins, coping): fine tooled, pitted, weathered, lichened."""
    m, nt, bsdf, out = _mat(name)
    tc = _n(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    att = _n(nt, "ShaderNodeAttribute", _attribute_name="tone")
    nz = _n(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=10.0, Roughness=0.62)
    _l(nt, co, nz.inputs["Vector"])
    fine = _n(nt, "ShaderNodeTexNoise", Scale=60.0, Detail=10.0, Roughness=0.7)
    _l(nt, co, fine.inputs["Vector"])
    pits = _n(nt, "ShaderNodeTexVoronoi", Scale=55.0)
    _l(nt, co, pits.inputs["Vector"])
    bl = _n(nt, "ShaderNodeMix", _data_type="FLOAT", Factor=0.5)
    _l(nt, nz.outputs["Fac"], bl.inputs[2])
    _l(nt, att.outputs["Fac"], bl.inputs[3])
    col = _ramp(nt, bl.outputs[0], [(0.25, (0.26, 0.215, 0.15)), (0.5, (0.40, 0.34, 0.25)),
                                    (0.8, (0.50, 0.44, 0.33))])
    c2, lich = weathering(nt, col.outputs[0], co, z_top, lichen, up_w, top_grime)
    ao = _n(nt, "ShaderNodeAmbientOcclusion", Distance=0.05, _samples=8)
    _l(nt, c2, ao.inputs["Color"])
    _l(nt, ao.outputs["Color"], bsdf.inputs["Base Color"])
    b0 = _n(nt, "ShaderNodeBump", Strength=0.35, Distance=0.01)
    _l(nt, nz.outputs["Fac"], b0.inputs["Height"])
    b1 = _n(nt, "ShaderNodeBump", Strength=0.45, Distance=0.004)
    _l(nt, fine.outputs["Fac"], b1.inputs["Height"])
    _l(nt, b0.outputs[0], b1.inputs["Normal"])
    b2 = _n(nt, "ShaderNodeBump", Strength=0.3, Distance=0.003)
    _l(nt, pits.outputs["Distance"], b2.inputs["Height"])
    _l(nt, b1.outputs[0], b2.inputs["Normal"])
    b3 = _n(nt, "ShaderNodeBump", Strength=0.4, Distance=0.002)
    _l(nt, lich, b3.inputs["Height"])
    _l(nt, b2.outputs[0], b3.inputs["Normal"])
    _l(nt, b3.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    return m


def mat_flags(z_top):
    return mat_ashlar(z_top, "roof_flags", lichen=0.4, up_w=0.02)


def mat_mortar():
    m, nt, bsdf, out = _mat("mortar")
    nz = _n(nt, "ShaderNodeTexNoise", Scale=8.0, Detail=6.0)
    r = _ramp(nt, nz.outputs["Fac"], [(0.3, (0.16, 0.14, 0.11)), (0.7, (0.26, 0.23, 0.18))])
    _l(nt, r.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    return m


def mat_dark():
    m, nt, bsdf, out = _mat("void")
    bsdf.inputs["Base Color"].default_value = (0.01, 0.009, 0.008, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    return m


def mat_slates():
    """Stone-slate roof of the nave (diminishing courses of grey-brown limestone slates)."""
    m, nt, bsdf, out = _mat("stone_slates")
    tc = _n(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    br = _n(nt, "ShaderNodeTexBrick", Scale=1.0, Mortar_Size=0.004, Bias=0.0,
            Brick_Width=0.45, Row_Height=0.16, _offset=0.5)
    br.inputs["Color1"].default_value = (0.20, 0.18, 0.14, 1)
    br.inputs["Color2"].default_value = (0.13, 0.12, 0.10, 1)
    br.inputs["Mortar"].default_value = (0.04, 0.035, 0.03, 1)
    mp = _n(nt, "ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    _l(nt, co, mp.inputs["Vector"])
    _l(nt, mp.outputs[0], br.inputs["Vector"])
    nz = _n(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=8.0)
    _l(nt, co, nz.inputs["Vector"])
    mul = _n(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=0.6)
    _l(nt, br.outputs["Color"], mul.inputs[6])
    _l(nt, nz.outputs["Color"], mul.inputs[7])
    _l(nt, mul.outputs[2], bsdf.inputs["Base Color"])
    b = _n(nt, "ShaderNodeBump", Strength=0.6, Distance=0.02)
    _l(nt, br.outputs["Fac"], b.inputs["Height"])
    _l(nt, b.outputs[0], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return m


# ---------------------------------------------------------------- geometry

def _tone(bm, faces_or_verts, rng):
    lay = bm.verts.layers.float.get("tone") or bm.verts.layers.float.new("tone")
    t = rng.random()
    for v in faces_or_verts:
        v[lay] = t


def _block(bm, rng, c, dims, rough=0.012, rot=0.012, cuts=2):
    if not bm.verts.layers.float.get("tone"):
        bm.verts.layers.float.new("tone")
    M = (Matrix.Translation(c) @ Matrix.Rotation(rng.uniform(-rot, rot), 4, "X") @
         Matrix.Rotation(rng.uniform(-rot, rot), 4, "Y") @
         Matrix.Rotation(rng.uniform(-rot, rot), 4, "Z") @ Matrix.Diagonal((*dims, 1)))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    vs = r["verts"]
    edges = list({e for v in vs for e in v.link_edges})
    res = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    allv = {v for v in set(vs) | {g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)}
            if v.is_valid}
    cen = Vector(c)
    for v in allv:
        v.co += (v.co - cen).normalized() * rng.uniform(-rough, rough * 0.4)
    _tone(bm, allv, rng)
    return allv


def _panel(bm, origin, u_dir, v_dir, w, h, uv_off=(0, 0)):
    """A flat wall face (quads ~1 m) with UVs in metres."""
    nu, nv = max(1, int(w)), max(1, int(h))
    o, U, V = Vector(origin), Vector(u_dir), Vector(v_dir)
    grid = [[bm.verts.new(o + U * (w * i / nu) + V * (h * j / nv)) for j in range(nv + 1)]
            for i in range(nu + 1)]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])


def build_tower(coll, base_z, seed=7, top_detail=False):
    """Returns the root empty; children are positioned with z relative to the plateau.

    top_detail: weathered top courses (rain-run grime below the coping, worn and uneven
    coping), a projecting string course marking the roof line, and two stone spouts."""
    rng = random.Random(seed)
    root = bpy.data.objects.new("tower", None)
    coll.objects.link(root)
    root.location = (0, 0, base_z)
    zt = base_z + ROOF + PARAPET
    tgw = 1.0 if top_detail else 0.0
    rub = mat_rubble_wall(zt, tgw)
    ash = mat_ashlar(zt, top_grime=tgw)
    h = SIDE / 2
    top = ROOF + PARAPET - 0.14
    bot = -2.0
    q = 0.32                                    # quoin return on each face

    def obj(name, bm, mat, smooth=False):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = smooth
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.parent = root
        me.materials.append(mat)
        return ob

    # outer rubble faces between the quoins, full height; inner parapet faces
    bm = bmesh.new()
    for (o, u) in (((-h + q, -h, bot), (1, 0, 0)), ((h, -h + q, bot), (0, 1, 0)),
                   ((h - q, h, bot), (-1, 0, 0)), ((-h, h - q, bot), (0, -1, 0))):
        _panel(bm, o, u, (0, 0, 1), SIDE - 2 * q, top - bot)
    hi = h - PAR_T
    for (o, u) in (((hi, -hi, ROOF - 0.05), (-1, 0, 0)), ((hi, hi, ROOF - 0.05), (0, -1, 0)),
                   ((-hi, hi, ROOF - 0.05), (1, 0, 0)), ((-hi, -hi, ROOF - 0.05), (0, 1, 0))):
        _panel(bm, o, u, (0, 0, 1), 2 * hi, top - ROOF + 0.05)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    walls = obj("tower_rubble", bm, rub)
    sub = walls.modifiers.new("adaptive", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.use_adaptive_subdivision = True
    sub.adaptive_space = "PIXEL"
    sub.adaptive_pixel_size = 1.5
    # quoins: long-and-short is too specific; plain alternating side-and-return blocks
    bm = bmesh.new()
    for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        z = bot
        k = 0
        while z < top - 0.05:
            hgt = min(rng.uniform(0.28, 0.42), top - z)
            la, lb = rng.uniform(0.55, 0.85), q + rng.uniform(0.0, 0.12)
            if k % 2:
                la, lb = lb, la
            # block occupying the corner: la along x-face, lb along y-face
            sx, sy = la, lb
            c = (cx * (h - sx / 2) + cx * 0.015, cy * (h - sy / 2) + cy * 0.015, z + hgt / 2)
            _block(bm, rng, c, (sx - 0.012, sy - 0.012, hgt - 0.014), rough=0.006, rot=0.006)
            z += hgt
            k += 1
    obj("tower_quoins", bm, ash)
    # coping slabs on the parapet
    bm = bmesh.new()
    for side in range(4):
        L = SIDE + 0.08
        p = -L / 2
        while p < L / 2 - 0.05:
            ln = min(rng.uniform(0.6, 1.05), L / 2 - p)
            dz = rng.uniform(-0.03, 0.02) if top_detail else 0.0
            c = Vector((p + ln / 2, -h + PAR_T / 2, top + 0.075 + dz))
            R = Matrix.Rotation(side * math.pi / 2, 3, "Z")
            hz = 0.15 + (rng.uniform(-0.025, 0.015) if top_detail else 0.0)
            _block(bm, rng, R @ c, None or tuple(abs(x) for x in R @ Vector((ln - 0.015, PAR_T + 0.06,
                                                                             hz))),
                   rough=0.03 if top_detail else 0.014, rot=0.03 if top_detail else 0.012,
                   cuts=3)
            p += ln
    obj("tower_coping", bm, ash, smooth=False)
    if top_detail:
        # string course at the roof line: a chamfered, worn band of dressed stone
        bm = bmesh.new()
        zc_ = ROOF - 0.2
        for side in range(4):
            R = Matrix.Rotation(side * math.pi / 2, 3, "Z")
            L = SIDE + 0.16
            p = -L / 2
            while p < L / 2 - 0.05:
                ln = min(rng.uniform(0.5, 0.9), L / 2 - p)
                c = Vector((p + ln / 2, -h - 0.02, zc_ + rng.uniform(-0.01, 0.01)))
                dims = R @ Vector((ln - 0.012, 0.2, 0.2))
                _block(bm, rng, R @ c, tuple(abs(x) for x in dims), rough=0.02, rot=0.015, cuts=2)
                p += ln
        obj("tower_string", bm, ash)
        # two plain stone spouts throwing roof water clear of the walls
        bm = bmesh.new()
        for side, off in ((0, 1.3), (1, -1.6)):
            R = Matrix.Rotation(side * math.pi / 2, 3, "Z")
            c = Vector((off, -h - 0.3, ROOF + 0.02))
            _block(bm, rng, R @ c, tuple(abs(x) for x in R @ Vector((0.24, 0.75, 0.2))),
                   rough=0.015, rot=0.02, cuts=2)
        obj("tower_spouts", bm, ash)
    # roof flags inside the parapet
    bm = bmesh.new()
    y = -hi
    while y < hi - 0.02:
        w = min(rng.uniform(0.45, 0.8), hi - y)
        x = -hi
        while x < hi - 0.02:
            ln = min(rng.uniform(0.5, 1.1), hi - x)
            _block(bm, rng, (x + ln / 2, y + w / 2, ROOF - 0.05), (ln - 0.02, w - 0.02, 0.1),
                   rough=0.008, rot=0.006, cuts=1)
            x += ln
        y += w
    obj("tower_flags", bm, mat_flags(zt))
    # timber hatch to the stair
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((hi - 0.9, hi - 0.8, ROOF + 0.04))
                          @ Matrix.Diagonal((1.0, 0.8, 0.08, 1)))
    hm = bpy.data.materials.get("timber") or bpy.data.materials.new("timber")
    obj("tower_hatch", bm, hm)
    # core (hidden inside) so nothing shows through
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, (bot + ROOF - 0.1) / 2)) @
                          Matrix.Diagonal((SIDE - 0.1, SIDE - 0.1, ROOF - 0.1 - bot, 1)))
    obj("tower_core", bm, mat_mortar())
    # belfry openings: dark round-headed recesses on each face, below the parapet
    bm = bmesh.new()
    for ang in range(4):
        R = Matrix.Rotation(ang * math.pi / 2, 4, "Z")
        w_, hh = 0.55, 1.45
        zc = ROOF - 2.3
        pts = []
        for i in range(13):
            a = math.pi * i / 12
            pts.append((w_ / 2 * math.cos(a), zc + hh / 2 + w_ / 2 * math.sin(a)))
        pts = [(w_ / 2, zc - hh / 2)] + pts + [(-w_ / 2, zc - hh / 2)]
        vs = [bm.verts.new(R @ Vector((x, -h - 0.075, z))) for x, z in pts]
        bm.faces.new(vs)
    obj("tower_openings", bm, mat_dark())
    return root


def build_nave(coll, base_z, seed=9):
    """Plain aisleless nave east of the tower, rubble walls, stone-slate roof."""
    rng = random.Random(seed)
    L, W, Hw = 24.0, 8.4, 8.0
    x0 = SIDE / 2
    rub = bpy.data.materials.get("rubble_wall")
    bm = bmesh.new()
    for (o, u, w) in (((x0, -W / 2, -2), (1, 0, 0), L), ((x0 + L, W / 2, -2), (-1, 0, 0), L),
                      ((x0 + L, -W / 2, -2), (0, 1, 0), W)):
        _panel(bm, o, u, (0, 0, 1), w, Hw + 2)
    # gable
    gv = [bm.verts.new((x0 + L, -W / 2, Hw)), bm.verts.new((x0 + L, W / 2, Hw)),
          bm.verts.new((x0 + L, 0, Hw + W / 2 * 1.2))]
    bm.faces.new(gv)
    me = bpy.data.meshes.new("nave_walls")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("nave_walls", me)
    ob.location = (0, 0, base_z)
    coll.objects.link(ob)
    me.materials.append(rub)
    bm = bmesh.new()
    over = 0.35
    rz = Hw + W / 2 * 1.2
    vs = [(x0 - 0.2, -W / 2 - over, Hw - 0.25), (x0 + L + over, -W / 2 - over, Hw - 0.25),
          (x0 + L + over, 0, rz + 0.2), (x0 - 0.2, 0, rz + 0.2),
          (x0 + L + over, W / 2 + over, Hw - 0.25), (x0 - 0.2, W / 2 + over, Hw - 0.25)]
    v = [bm.verts.new(p) for p in vs]
    bm.faces.new([v[0], v[1], v[2], v[3]])
    bm.faces.new([v[3], v[2], v[4], v[5]])
    me = bpy.data.meshes.new("nave_roof")
    bm.to_mesh(me)
    bm.free()
    ro = bpy.data.objects.new("nave_roof", me)
    ro.location = (0, 0, base_z)
    coll.objects.link(ro)
    me.materials.append(mat_slates())
    so = ro.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.25
    return ob
