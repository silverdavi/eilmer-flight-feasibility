"""Path-traced hero renders of the nominal model configuration (Blender Cycles, Metal GPU).

Same geometry as viz/render_blender.py: the wing planform constants are imported from
it and the pilot joints are copied verbatim, so span, chord, camber, sweep, dihedral,
pilot size and posture are unchanged. No tail. What is new is the rendering: physically
based linen (slubbed weave, sheen, translucency), oiled-ash frame, leather lashings,
a woollen habit, soft area/sun lighting, depth of field, denoised path tracing.

Shots:
  figure  transparent studio render + projected anchors, composed by compose_hero.py
  cover   portrait A4 (2480x3508) launch from a plain stone parapet, golden-hour sky

  .venv-bpy/bin/python viz/hero/render_hero.py --shot figure|cover|all [--preview]

Outputs go to viz/hero/ only.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import bpy  # noqa: I001  (bpy must be imported before bmesh/mathutils)
import bmesh
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from render_blender import CAMBER, DIHEDRAL, HALF, ROOT_X, SWEEP, TAPER  # noqa: E402

ZC = -0.55  # pilot hang depth below the wing root (render_blender.pilot)

# render_blender.py's CHORD_ROOT = 1.55 gives a planform area of only ~6.36 m^2 at the
# 5.29 m span, but the paper's nominal wing is 7 m^2 at aspect ratio 4 (span = sqrt(4*7)).
# Keep span, taper, sweep, camber and dihedral, and scale the root chord so that
# S = 2*HALF*c_root*(1 - TAPER/2) = 7 m^2 exactly.
AREA_M2 = 7.0
CHORD_ROOT_HERO = AREA_M2 / (2 * HALF * (1 - TAPER / 2))

# Pilot joints, verbatim from render_blender.pilot(): (centre, radius, scale) / (p1, p2, r).
TORSO = ((0, 0.02, ZC), 0.16, (1.0, 2.6, 0.72))
HIPS = ((0, 0.42, ZC - 0.01), 0.15, (1.0, 1.3, 0.8))
NECK = ((0, -0.30, ZC + 0.02), (0, -0.44, ZC + 0.06), 0.05)
HEAD = ((0, -0.52, ZC + 0.07), 0.105, (1.0, 1.15, 1.05))


def arm(s):
    return [((s * 0.13, -0.16, ZC + 0.02), (s * 0.5, -0.15, -0.16), 0.04),
            ((s * 0.5, -0.15, -0.16), (s * 0.9, -0.08, 0.0), 0.03)]


def hand(s):
    return (s * 0.93, -0.06, 0.01), 0.05


def leg(s):
    return [((s * 0.11, 0.5, ZC), (s * 0.16, 0.95, ZC + 0.03), 0.05),
            ((s * 0.16, 0.95, ZC + 0.03), (s * 0.2, 1.35, ZC + 0.05), 0.036)]


def foot(s):
    return (s * 0.21, 1.42, ZC + 0.04), 0.06, (1, 1.5, 0.7)


# ---------------------------------------------------------------- wing surface

def chord(u):
    return CHORD_ROOT_HERO * (1 - TAPER * u)


def surf(s, v):
    """Wing surface point; s in [-1, 1] spanwise (signed), v in [0, 1] LE->TE."""
    u = abs(s)
    c = chord(u)
    x = math.copysign(ROOT_X + u * HALF, s) if s else 0.0
    y = (v - 0.28) * c + u * SWEEP
    z = CAMBER * c * math.sin(math.pi * v) + DIHEDRAL * u ** 1.6
    return Vector((x, y, z))


def le_spar(s):
    return surf(s, 0.0) + Vector((0, 0, 0.02))


# ---------------------------------------------------------------- node helpers

def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"], nt.nodes["Material Output"]


def nd(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        if k.startswith("_"):
            setattr(n, k[1:], v)
        else:
            n.inputs[k.replace("_", " ")].default_value = v
    return n


def ln(nt, a, b):
    nt.links.new(a, b)


def set_in(bsdf, **kw):
    for k, v in kw.items():
        bsdf.inputs[k.replace("_", " ")].default_value = v


def ramp(nt, fac, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
    els[1].position, els[1].color = stops[-1][0], (*stops[-1][1], 1)
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = (*c, 1)
    ln(nt, fac, r.inputs["Fac"])
    return r


def bump(nt, height, strength, distance, normal=None):
    b = nd(nt, "ShaderNodeBump", Strength=strength, Distance=distance)
    ln(nt, height, b.inputs["Height"])
    if normal is not None:
        ln(nt, normal, b.inputs["Normal"])
    return b


# ---------------------------------------------------------------- materials

def mat_linen():
    m, nt, bsdf, out = new_mat("linen")
    tc = nd(nt, "ShaderNodeTexCoord")
    uv = tc.outputs["UV"]                      # UV = planform metres (x, y)
    sep = nd(nt, "ShaderNodeSeparateXYZ")
    ln(nt, uv, sep.inputs[0])

    # hand-spun slubs: noise stretched along the weft (spanwise)
    slub_map = nd(nt, "ShaderNodeMapping")
    slub_map.inputs["Scale"].default_value = (5.0, 140.0, 1.0)
    ln(nt, uv, slub_map.inputs["Vector"])
    slub = nd(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=6.0, Roughness=0.6)
    ln(nt, slub_map.outputs[0], slub.inputs["Vector"])
    # warp slubs (chordwise), weaker
    warp_map = nd(nt, "ShaderNodeMapping")
    warp_map.inputs["Scale"].default_value = (110.0, 4.0, 1.0)
    ln(nt, uv, warp_map.inputs["Vector"])
    warp = nd(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=4.0)
    ln(nt, warp_map.outputs[0], warp.inputs["Vector"])
    # large-scale tonal variation of undyed flax
    big = nd(nt, "ShaderNodeTexNoise", Scale=1.2, Detail=3.0)
    ln(nt, uv, big.inputs["Vector"])

    mixf = nd(nt, "ShaderNodeMath", _operation="ADD")
    ln(nt, slub.outputs["Fac"], mixf.inputs[0])
    ln(nt, warp.outputs["Fac"], mixf.inputs[1])
    mixf2 = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, mixf.outputs[0], mixf2.inputs[0])
    mixf2.inputs[1].default_value = 0.35
    ln(nt, big.outputs["Fac"], mixf2.inputs[2])
    col = ramp(nt, mixf2.outputs[0], [(0.45, (0.50, 0.42, 0.29)), (0.70, (0.66, 0.58, 0.43)),
                                      (0.95, (0.74, 0.68, 0.54))])

    # sewn seams between loom-width panels (chordwise, every 0.66 m)
    P = 0.66
    a = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, sep.outputs["X"], a.inputs[0])
    a.inputs[1].default_value, a.inputs[2].default_value = 1 / P, 0.5
    fr = nd(nt, "ShaderNodeMath", _operation="FRACT")
    ln(nt, a.outputs[0], fr.inputs[0])
    sb = nd(nt, "ShaderNodeMath", _operation="SUBTRACT")
    ln(nt, fr.outputs[0], sb.inputs[0])
    sb.inputs[1].default_value = 0.5
    ab = nd(nt, "ShaderNodeMath", _operation="ABSOLUTE")
    ln(nt, sb.outputs[0], ab.inputs[0])
    dist = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    ln(nt, ab.outputs[0], dist.inputs[0])
    dist.inputs[1].default_value = P
    seam = nd(nt, "ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP")
    ln(nt, dist.outputs[0], seam.inputs["Value"])
    seam.inputs["From Min"].default_value, seam.inputs["From Max"].default_value = 0.004, 0.011
    seam.inputs["To Min"].default_value, seam.inputs["To Max"].default_value = 1.0, 0.0

    seam_col = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    ln(nt, seam.outputs[0], seam_col.inputs["Factor"])
    ln(nt, col.outputs[0], seam_col.inputs[6])
    seam_col.inputs[7].default_value = (0.82, 0.78, 0.70, 1)
    ln(nt, seam_col.outputs[2], bsdf.inputs["Base Color"])

    # plain weave (~1.6 mm thread pitch) + wrinkles + seam ridge
    w1 = nd(nt, "ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", Scale=390.0,
            Distortion=1.5, Detail=1.0)
    w2 = nd(nt, "ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="Y", Scale=390.0,
            Distortion=1.5, Detail=1.0)
    ln(nt, uv, w1.inputs["Vector"])
    ln(nt, uv, w2.inputs["Vector"])
    weave = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    ln(nt, w1.outputs["Fac"], weave.inputs[0])
    ln(nt, w2.outputs["Fac"], weave.inputs[1])
    wr = nd(nt, "ShaderNodeTexNoise", Scale=2.2, Detail=5.0, Roughness=0.55, Distortion=0.4)
    ln(nt, tc.outputs["Object"], wr.inputs["Vector"])
    b1 = bump(nt, weave.outputs[0], 0.12, 0.0015)
    b2 = bump(nt, wr.outputs["Fac"], 0.22, 0.02, b1.outputs[0])
    b3 = bump(nt, seam.outputs[0], 0.35, 0.002, b2.outputs[0])
    b4 = bump(nt, slub.outputs["Fac"], 0.15, 0.002, b3.outputs[0])
    ln(nt, b4.outputs[0], bsdf.inputs["Normal"])

    set_in(bsdf, Roughness=0.86, Sheen_Weight=0.55, Sheen_Roughness=0.45,
           Specular_IOR_Level=0.35)
    bsdf.inputs["Sheen Tint"].default_value = (1.0, 0.96, 0.88, 1)

    # thin-sheet translucency; doubled cloth at the seams lets less light through
    tr = nd(nt, "ShaderNodeBsdfTranslucent")
    tcol = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY")
    tcol.inputs["Factor"].default_value = 1.0
    ln(nt, col.outputs[0], tcol.inputs[6])
    tcol.inputs[7].default_value = (1.0, 0.86, 0.62, 1)
    ln(nt, tcol.outputs[2], tr.inputs["Color"])
    ln(nt, b4.outputs[0], tr.inputs["Normal"])
    fac = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, seam.outputs[0], fac.inputs[0])
    fac.inputs[1].default_value, fac.inputs[2].default_value = -0.22, 0.34
    mix = nd(nt, "ShaderNodeMixShader")
    ln(nt, fac.outputs[0], mix.inputs[0])
    ln(nt, bsdf.outputs[0], mix.inputs[1])
    ln(nt, tr.outputs[0], mix.inputs[2])
    ln(nt, mix.outputs[0], out.inputs["Surface"])
    return m


def mat_wood():
    m, nt, bsdf, out = new_mat("oiled_ash")
    tc = nd(nt, "ShaderNodeTexCoord")
    mp = nd(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (2.5, 70.0, 70.0)    # long grain along the spar
    ln(nt, tc.outputs["Object"], mp.inputs["Vector"])
    grain = nd(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=6.0, Roughness=0.55)
    ln(nt, mp.outputs[0], grain.inputs["Vector"])
    nz = nd(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=3.0)
    ln(nt, tc.outputs["Object"], nz.inputs["Vector"])
    mx = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, grain.outputs["Fac"], mx.inputs[0])
    mx.inputs[1].default_value = 0.6
    ln(nt, nz.outputs["Fac"], mx.inputs[2])
    mx2 = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    ln(nt, mx.outputs[0], mx2.inputs[0])
    mx2.inputs[1].default_value = 0.62
    col = ramp(nt, mx2.outputs[0], [(0.4, (0.20, 0.11, 0.045)), (0.55, (0.33, 0.20, 0.09)),
                                    (0.7, (0.42, 0.28, 0.13))])
    ln(nt, col.outputs[0], bsdf.inputs["Base Color"])
    b = bump(nt, grain.outputs["Fac"], 0.04, 0.001)
    ln(nt, b.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.38, Coat_Weight=0.4, Coat_Roughness=0.22)
    return m


def mat_leather():
    m, nt, bsdf, out = new_mat("leather")
    tc = nd(nt, "ShaderNodeTexCoord")
    nz = nd(nt, "ShaderNodeTexNoise", Scale=300.0, Detail=6.0)
    ln(nt, tc.outputs["Object"], nz.inputs["Vector"])
    vo = nd(nt, "ShaderNodeTexVoronoi", Scale=180.0)
    ln(nt, tc.outputs["Object"], vo.inputs["Vector"])
    col = ramp(nt, nz.outputs["Fac"], [(0.3, (0.07, 0.03, 0.012)), (0.7, (0.17, 0.075, 0.03))])
    ln(nt, col.outputs[0], bsdf.inputs["Base Color"])
    b = bump(nt, vo.outputs["Distance"], 0.25, 0.001)
    ln(nt, b.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.5, Coat_Weight=0.15, Coat_Roughness=0.4)
    return m


def ao(nt, color_socket, distance):
    n = nd(nt, "ShaderNodeAmbientOcclusion", Distance=distance, _samples=8)
    ln(nt, color_socket, n.inputs["Color"])
    return n.outputs["Color"]


def mat_wool(base=(0.13, 0.102, 0.076)):
    """Undyed grey-brown (oatmeal) wool: fulled twill, fibre fuzz, sheen, cavity AO."""
    m, nt, bsdf, out = new_mat("wool_habit")
    tc = nd(nt, "ShaderNodeTexCoord")
    nz = nd(nt, "ShaderNodeTexNoise", Scale=600.0, Detail=4.0)
    ln(nt, tc.outputs["Object"], nz.inputs["Vector"])
    big = nd(nt, "ShaderNodeTexNoise", Scale=5.0, Detail=4.0)
    ln(nt, tc.outputs["Object"], big.inputs["Vector"])
    col = ramp(nt, big.outputs["Fac"], [(0.3, tuple(c * 0.8 for c in base)),
                                        (0.7, tuple(c * 1.15 for c in base))])
    ln(nt, ao(nt, col.outputs[0], 0.06), bsdf.inputs["Base Color"])
    w1 = nd(nt, "ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="DIAGONAL",
            Scale=220.0, Distortion=2.0)
    ln(nt, tc.outputs["Object"], w1.inputs["Vector"])
    b1 = bump(nt, nz.outputs["Fac"], 0.25, 0.0015)
    b2 = bump(nt, w1.outputs["Fac"], 0.10, 0.0015, b1.outputs[0])
    ln(nt, b2.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.92, Sheen_Weight=0.3, Sheen_Roughness=0.5,
           Specular_IOR_Level=0.15)
    bsdf.inputs["Sheen Tint"].default_value = (0.70, 0.60, 0.48, 1)
    return m


def mat_skin():
    m, nt, bsdf, out = new_mat("skin")
    set_in(bsdf, Roughness=0.48, Subsurface_Weight=0.5, Subsurface_Scale=0.008)
    rgb = nd(nt, "ShaderNodeRGB")
    rgb.outputs[0].default_value = (0.40, 0.235, 0.16, 1)
    ln(nt, ao(nt, rgb.outputs[0], 0.03), bsdf.inputs["Base Color"])
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    return m


def mat_stone():
    m, nt, bsdf, out = new_mat("limestone")
    tc = nd(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Generated"]
    co = tc.outputs["Object"]
    nz = nd(nt, "ShaderNodeTexNoise", Scale=2.5, Detail=10.0, Roughness=0.62)
    ln(nt, co, nz.inputs["Vector"])
    fine = nd(nt, "ShaderNodeTexNoise", Scale=40.0, Detail=10.0, Roughness=0.7)
    ln(nt, co, fine.inputs["Vector"])
    pits = nd(nt, "ShaderNodeTexVoronoi", Scale=30.0, _feature="F1")
    ln(nt, co, pits.inputs["Vector"])
    lich = nd(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=6.0)
    ln(nt, co, lich.inputs["Vector"])
    att = nd(nt, "ShaderNodeVertexColor", _layer_name="tone")
    sepa = nd(nt, "ShaderNodeSeparateColor")
    ln(nt, att.outputs["Color"], sepa.inputs[0])
    blend = nd(nt, "ShaderNodeMix", _data_type="FLOAT", Factor=0.3)
    ln(nt, nz.outputs["Fac"], blend.inputs[2])
    ln(nt, sepa.outputs[0], blend.inputs[3])
    col = ramp(nt, blend.outputs[0], [(0.25, (0.20, 0.18, 0.145)), (0.5, (0.30, 0.27, 0.215)),
                                      (0.75, (0.37, 0.34, 0.28))])
    lm = ramp(nt, lich.outputs["Fac"], [(0.62, (0, 0, 0)), (0.72, (0.6, 0.6, 0.6))])
    mixc = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    ln(nt, lm.outputs[0], mixc.inputs["Factor"])
    ln(nt, col.outputs[0], mixc.inputs[6])
    mixc.inputs[7].default_value = (0.24, 0.25, 0.17, 1)
    smp = nd(nt, "ShaderNodeMapping")
    smp.inputs["Scale"].default_value = (7.0, 7.0, 0.35)
    ln(nt, co, smp.inputs["Vector"])
    streak = nd(nt, "ShaderNodeTexNoise", Scale=1.0, Detail=5.0)
    ln(nt, smp.outputs[0], streak.inputs["Vector"])
    sk = ramp(nt, streak.outputs["Fac"], [(0.35, (1, 1, 1)), (0.7, (0.62, 0.6, 0.58))])
    dirty = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    ln(nt, mixc.outputs[2], dirty.inputs[6])
    ln(nt, sk.outputs[0], dirty.inputs[7])
    ln(nt, dirty.outputs[2], bsdf.inputs["Base Color"])
    b0 = bump(nt, nz.outputs["Fac"], 0.5, 0.03)
    b1 = bump(nt, fine.outputs["Fac"], 0.45, 0.01, b0.outputs[0])
    b2 = bump(nt, pits.outputs["Distance"], 0.25, 0.006, b1.outputs[0])
    ln(nt, b2.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.9)
    return m


def mat_mortar():
    m, nt, bsdf, out = new_mat("mortar")
    bsdf.inputs["Base Color"].default_value = (0.12, 0.105, 0.085, 1)
    set_in(bsdf, Roughness=0.95)
    return m


def mat_ground():
    """Distant English countryside, with aerial perspective by view distance."""
    m, nt, bsdf, out = new_mat("ground")
    tc = nd(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    fields = nd(nt, "ShaderNodeTexVoronoi", Scale=1 / 160, Randomness=0.85)
    ln(nt, co, fields.inputs["Vector"])
    sep = nd(nt, "ShaderNodeSeparateColor")
    ln(nt, fields.outputs["Color"], sep.inputs[0])
    fcol = ramp(nt, sep.outputs[0], [(0.0, (0.05, 0.13, 0.025)), (0.4, (0.09, 0.20, 0.04)),
                                      (0.7, (0.15, 0.23, 0.06)), (0.85, (0.32, 0.27, 0.11)),
                                      (1.0, (0.20, 0.21, 0.08))])
    edges = nd(nt, "ShaderNodeTexVoronoi", Scale=1 / 160, Randomness=0.85,
               _feature="DISTANCE_TO_EDGE")
    ln(nt, co, edges.inputs["Vector"])
    hedge = nd(nt, "ShaderNodeMapRange", **{"From Min": 0.0, "From Max": 0.025,
                                           "To Min": 1.0, "To Max": 0.0})
    ln(nt, edges.outputs["Distance"], hedge.inputs["Value"])
    woods = nd(nt, "ShaderNodeTexNoise", Scale=1 / 500, Detail=6.0)
    ln(nt, co, woods.inputs["Vector"])
    wm = ramp(nt, woods.outputs["Fac"], [(0.58, (0, 0, 0)), (0.62, (1, 1, 1))])
    dark = (0.02, 0.035, 0.012, 1)
    m1 = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    ln(nt, hedge.outputs[0], m1.inputs["Factor"])
    ln(nt, fcol.outputs[0], m1.inputs[6])
    m1.inputs[7].default_value = dark
    m2 = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    ln(nt, wm.outputs[0], m2.inputs["Factor"])
    ln(nt, m1.outputs[2], m2.inputs[6])
    m2.inputs[7].default_value = dark
    grass = nd(nt, "ShaderNodeTexNoise", Scale=1 / 14, Detail=8.0, Roughness=0.6)
    ln(nt, co, grass.inputs["Vector"])
    gv = ramp(nt, grass.outputs["Fac"], [(0.3, (0.7, 0.72, 0.6)), (0.7, (1.15, 1.12, 1.05))])
    m3 = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    ln(nt, m2.outputs[2], m3.inputs[6])
    ln(nt, gv.outputs[0], m3.inputs[7])
    ln(nt, m3.outputs[2], bsdf.inputs["Base Color"])
    set_in(bsdf, Roughness=0.95)
    cam = nd(nt, "ShaderNodeCameraData")
    hz = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    ln(nt, cam.outputs["View Distance"], hz.inputs[0])
    hz.inputs[1].default_value = -1 / HAZE_DIST
    ex = nd(nt, "ShaderNodeMath", _operation="EXPONENT")
    ln(nt, hz.outputs[0], ex.inputs[0])
    inv = nd(nt, "ShaderNodeMath", _operation="SUBTRACT", **{})
    inv.inputs[0].default_value = 1.0
    ln(nt, ex.outputs[0], inv.inputs[1])
    em = nd(nt, "ShaderNodeEmission", Strength=HAZE_K)
    em.inputs["Color"].default_value = (*HAZE, 1)
    mix = nd(nt, "ShaderNodeMixShader")
    ln(nt, inv.outputs[0], mix.inputs[0])
    ln(nt, bsdf.outputs[0], mix.inputs[1])
    ln(nt, em.outputs[0], mix.inputs[2])
    ln(nt, mix.outputs[0], out.inputs["Surface"])
    return m


HAZE = (0.95, 0.68, 0.45)
HAZE_K, HAZE_DIST = 0.6, 6000.0


# ---------------------------------------------------------------- geometry helpers

COLL = None


def link(ob, parent=None):
    COLL.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def mesh_obj(name, bm, material, smooth=True, parent=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    me.materials.append(material)
    return link(ob, parent)


def curve_obj(name, pts, radius, material, parent=None, resolution=4, cyclic=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = resolution
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    sp.use_cyclic_u = cyclic
    sp.use_smooth = True
    ob = bpy.data.objects.new(name, cu)
    cu.materials.append(material)
    return link(ob, parent)


def basis(axis):
    t = Vector(axis).normalized()
    a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
    n = t.cross(a).normalized()
    b = t.cross(n).normalized()
    return t, n, b


def helix(centre, axis, radius, length, turns, n=24):
    t, nn, b = basis(axis)
    c = Vector(centre)
    pts = []
    m = int(turns * n)
    for i in range(m + 1):
        f = i / m
        ang = 2 * math.pi * turns * f
        pts.append(c + t * (length * (f - 0.5)) + radius * (math.cos(ang) * nn + math.sin(ang) * b))
    return pts


def ring(centre, axis, radius, n=40):
    t, nn, b = basis(axis)
    c = Vector(centre)
    return [c + radius * (math.cos(2 * math.pi * i / n) * nn + math.sin(2 * math.pi * i / n) * b)
            for i in range(n)]


def add_sphere(bm, c, r, scale=(1, 1, 1), seg=32, rings=16):
    M = Matrix.Translation(c) @ Matrix.Diagonal((*scale, 1))
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r, matrix=M)


def add_capsule(bm, p1, p2, r, seg=24):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    M = Matrix.Translation((p1 + p2) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r,
                          depth=d.length, matrix=M)
    add_sphere(bm, p1, r, seg=seg, rings=12)
    add_sphere(bm, p2, r, seg=seg, rings=12)


def lerp(a, b, f):
    return Vector(a).lerp(Vector(b), f)


# ---------------------------------------------------------------- the craft

WING_STATS = {}


def planform_area(ob):
    """Area of the wing mesh projected on the horizontal (planform) and its true surface."""
    me = ob.data
    plan = 0.0
    for p in me.polygons:
        vs = [me.vertices[i].co for i in p.vertices]
        a = 0.0
        for i in range(len(vs)):
            x1, y1 = vs[i].x, vs[i].y
            x2, y2 = vs[(i + 1) % len(vs)].x, vs[(i + 1) % len(vs)].y
            a += x1 * y2 - x2 * y1
        plan += abs(a) / 2
    return {"planform_m2": plan, "surface_m2": sum(p.area for p in me.polygons)}


def build_craft(M):
    root = bpy.data.objects.new("craft", None)
    link(root)

    # cloth wing: one sheet, both halves, UV = planform metres
    ns, nv = 181, 61
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = {}
    for i in range(ns):
        s = -1 + 2 * i / (ns - 1)
        for j in range(nv):
            grid[i, j] = bm.verts.new(surf(s, j / (nv - 1)))
    for i in range(ns - 1):
        for j in range(nv - 1):
            f = bm.faces.new([grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]])
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.x, lp.vert.co.y)
    wing = mesh_obj("wing", bm, M["linen"], parent=root)
    WING_STATS.update(planform_area(wing), span=2 * HALF)

    # rolled hem along the trailing edge and tips
    te = [surf(-1 + 2 * i / 200, 1.0) for i in range(201)]
    curve_obj("hem_te", te, 0.0055, M["linen"], parent=root, resolution=2)
    for sgn in (1, -1):
        tip = [surf(sgn, j / 40) for j in range(41)]
        curve_obj(f"hem_tip{sgn}", tip, 0.0055, M["linen"], parent=root, resolution=2)

    # wooden frame: leading-edge spar and three battens per side (as render_blender)
    curve_obj("spar_LE", [le_spar(-1 + 2 * i / 120) for i in range(121)], 0.022, M["wood"],
              parent=root)
    stations = (0.18, 0.5, 0.82)
    for sgn in (1, -1):
        for u in stations:
            pts = [surf(sgn * u, j / 30) + Vector((0, 0, 0.01)) for j in range(31)]
            curve_obj(f"batten_{sgn}_{u}", pts, 0.012, M["wood"], parent=root)

    # leather lashings: batten roots and the spar apex
    def spar_axis(s):
        return (le_spar(min(s + 0.01, 1)) - le_spar(max(s - 0.01, -1))).normalized()

    for s in [0.0] + [sg * u for sg in (1, -1) for u in stations]:
        if s == 0.0:
            for side in (1, -1):
                c = le_spar(side * 0.025)
                curve_obj(f"lash_apex{side}", helix(c, spar_axis(side * 0.025), 0.0262, 0.06, 7),
                          0.0036, M["leather"], parent=root, resolution=2)
        else:
            c = le_spar(s)
            curve_obj(f"lash_{s}", helix(c, spar_axis(s), 0.0262, 0.07, 8), 0.0036,
                      M["leather"], parent=root, resolution=2)
        # batten tip sewn into a leather cap at the trailing edge
        if s:
            add = bmesh.new()
            add_sphere(add, surf(s, 1.0) + Vector((0, -0.01, 0.01)), 0.018, (1.0, 1.8, 0.7))
            mesh_obj(f"cap_{s}", add, M["leather"], parent=root)

    build_pilot(M, root)
    return root


def add_skirt(bm, n=28, m=14):
    """Closed tube of the habit's skirt round both thighs, hips to just past the knees."""
    rings = []
    (l1, l2, rt), _ = leg(-1)
    (r1, r2, _), _ = leg(1)
    for k in range(m):
        t = -0.15 + 1.2 * k / (m - 1)
        L, R = lerp(l1, l2, t), lerp(r1, r2, t)
        c = (L + R) / 2
        hw = (R - L).length / 2 + rt * 1.35 + 0.012 * t
        hh = rt * 1.25
        sag = 0.025 * max(t, 0) ** 1.5
        ring_v = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            z = hh * sa - (sag * (-sa) if sa < 0 else 0)
            ring_v.append(bm.verts.new(c + Vector((hw * ca, 0, z))))
        rings.append(ring_v)
    for k in range(m - 1):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def head_frame():
    """Local head axes: r (right), u (crown), f (face). Prone, looking ahead and a bit down."""
    f = Vector((0, -1, -0.55)).normalized()
    r = Vector((1, 0, 0))
    u = f.cross(r).normalized() * -1
    if u.z < 0:
        u = -u
    return r, u, f


def face_offset(x, y, df):
    """Sculpted relief (m) on the front of the head; x, y are unit-sphere coords."""
    if df <= 0:
        return 0.0
    g = math.exp
    o = 0.024 * g(-(x / 0.10) ** 2 - ((y + 0.08) / 0.20) ** 2)            # nose
    o -= 0.013 * g(-((abs(x) - 0.33) / 0.13) ** 2 - ((y - 0.12) / 0.10) ** 2)  # eye sockets
    o += 0.007 * g(-((y - 0.27) / 0.08) ** 2) * (abs(x) < 0.65)          # brow ridge
    o += 0.006 * g(-((abs(x) - 0.42) / 0.15) ** 2 - ((y + 0.15) / 0.12) ** 2)  # cheekbones
    o -= 0.004 * g(-(x / 0.25) ** 2 - ((y + 0.40) / 0.04) ** 2)           # mouth line
    o += 0.010 * g(-(x / 0.22) ** 2 - ((y + 0.62) / 0.12) ** 2)           # chin
    return o * min(1.0, df * 2.5)


def build_head(M, root):
    c = Vector(HEAD[0])
    R_, U_, F_ = head_frame()
    rad = (0.098, 0.115, 0.112)                 # r, u, f half-axes (render_blender head size)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    for v in bm.verts:
        d = v.co.normalized()                   # local (x=r, y=u, z=f)
        x, y, z = d
        jaw = 1.0 - 0.18 * max(0.0, -y) * max(0.0, z)
        p = Vector((x * rad[0] * jaw, y * rad[1], z * rad[2]))
        n = Vector((x / rad[0], y / rad[1], z / rad[2])).normalized()
        p += n * face_offset(x, y, z)
        v.co = c + R_ * p.x + U_ * p.y + F_ * p.z
    face = mesh_obj("head", bm, M["skin"], parent=root)
    sub = face.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1

    # deep cowl: opening framing the face, brim ahead of the face so it sits in shade,
    # the back drawn out and draped toward the shoulders
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=72, v_segments=36, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.5], context="VERTS")
    hr = (0.135, 0.150, 0.150)
    hc = c + F_ * 0.055 + U_ * 0.012
    for v in bm.verts:
        x, y, z = v.co
        back = max(0.0, -z)
        p = Vector((x * hr[0] * (1 + 0.08 * back), y * hr[1], z * hr[2] * (1 + 0.55 * back ** 2)))
        p.y -= 0.05 * back ** 2.5               # drape down onto the back
        p.y += 0.012 * max(0.0, y) * back      # slight peak at the crown
        v.co = hc + R_ * p.x + U_ * p.y + F_ * p.z
    hood = mesh_obj("hood", bm, M["wool"], parent=root)
    so = hood.modifiers.new("solid", "SOLIDIFY")
    so.thickness, so.offset = 0.012, -1.0
    tex = bpy.data.textures.new("hoodfolds", "CLOUDS")
    tex.noise_scale = 0.05
    dp = hood.modifiers.new("folds", "DISPLACE")
    dp.texture, dp.strength = tex, 0.006
    hs = hood.modifiers.new("sub", "SUBSURF")
    hs.levels = hs.render_levels = 2


def build_hand(M, root, s):
    (a1, a2, ra), (f1, f2, rf) = arm(s)
    hc, hr = hand(s)
    hc = Vector(hc)
    fa = (Vector(f2) - Vector(f1)).normalized()
    up = (Vector((0, 0, 1)) - fa * fa.z).normalized()       # palm faces the wing
    side = fa.cross(up).normalized()
    bm = bmesh.new()
    add_capsule(bm, lerp(f1, f2, 0.7), f2, rf)               # bare wrist
    M_ = Matrix((side, fa, up)).transposed().to_4x4()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0,
                              matrix=Matrix.Translation(hc - fa * 0.012) @ M_ @
                              Matrix.Diagonal((0.040, 0.046, 0.017, 1)))
    for i, off in enumerate((-0.027, -0.009, 0.009, 0.027)):
        L = 1.0 - 0.12 * abs(i - 1.5)
        p0 = hc + fa * 0.026 + side * off + up * 0.004
        p1 = p0 + fa * 0.03 * L + up * 0.012
        p2 = p1 + up * 0.022 * L - fa * 0.006
        add_capsule(bm, p0, p1, 0.0085, seg=12)
        add_capsule(bm, p1, p2, 0.0078, seg=12)
    t0 = hc - fa * 0.01 + side * (-0.036 * s) + up * 0.004
    add_capsule(bm, t0, t0 + fa * 0.03 + up * 0.016 + side * (0.008 * s), 0.0095, seg=12)
    ob = mesh_obj(f"hand{s}", bm, M["skin"], parent=root)
    rm = ob.modifiers.new("remesh", "REMESH")
    rm.mode, rm.voxel_size = "VOXEL", 0.0025
    sm = ob.modifiers.new("smooth", "SMOOTH")
    sm.factor, sm.iterations = 0.8, 4


def build_foot(M, root, s):
    """Bare foot in a sandal; prone with toes pointed aft, sole facing up."""
    (t1, t2, rt), (h1, h2, rh) = leg(s)
    fc, fr, fs = foot(s)
    fc = Vector(fc)
    ax = (fc - Vector(h2)).normalized()
    up = (Vector((0, 0, 1)) - ax * ax.z).normalized()
    side = ax.cross(up).normalized()
    M_ = Matrix((side, ax, up)).transposed().to_4x4()
    bm = bmesh.new()
    add_capsule(bm, lerp(h1, h2, 0.84), h2, rh * 0.95)       # bare ankle
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0,
                              matrix=Matrix.Translation(fc) @ M_ @
                              Matrix.Diagonal((0.040, 0.092, 0.032, 1)))
    add_sphere(bm, Vector(h2) + ax * 0.005 + up * 0.012, 0.034)   # heel
    for i, off in enumerate((-0.022, -0.009, 0.003, 0.014, 0.024)):
        tr = 0.012 if i == 0 else 0.008
        add_sphere(bm, fc + ax * (0.085 - 0.006 * i) + side * off * s - up * 0.004, tr)
    ob = mesh_obj(f"foot{s}", bm, M["skin"], parent=root)
    rm = ob.modifiers.new("remesh", "REMESH")
    rm.mode, rm.voxel_size = "VOXEL", 0.003
    sm = ob.modifiers.new("smooth", "SMOOTH")
    sm.factor, sm.iterations = 0.8, 4
    # sandal: leather sole under the (upturned) sole of the foot, two straps
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=12, radius=1.0,
                              matrix=Matrix.Translation(fc + up * 0.033 - ax * 0.012) @ M_ @
                              Matrix.Diagonal((0.046, 0.115, 0.007, 1)))
    mesh_obj(f"sole{s}", bm, M["leather"], parent=root)
    for t in (-0.035, 0.035):
        curve_obj(f"strap{s}{t}", ring(fc + ax * t + up * 0.006, ax, 0.035), 0.0035,
                  M["leather"], parent=root, cyclic=True, resolution=2)


def build_pilot(M, root):
    # undyed woollen habit: torso, hips, sleeves, skirt, legs fused by voxel remesh,
    # with large wind-streamed drapes and finer creases
    bm = bmesh.new()
    c, r, sc = TORSO
    add_sphere(bm, c, r * 1.04, sc, seg=48, rings=24)
    c, r, sc = HIPS
    add_sphere(bm, c, r * 1.04, sc, seg=48, rings=24)
    add_capsule(bm, NECK[0], lerp(NECK[0], NECK[1], 0.5), NECK[2] * 1.2)
    for s in (1, -1):
        (a1, a2, ra), (f1, f2, rf) = arm(s)
        add_capsule(bm, a1, a2, ra * 1.5)
        add_capsule(bm, f1, lerp(f1, f2, 0.78), rf * 1.9)
        (t1, t2, rt), (h1, h2, rh) = leg(s)
        add_capsule(bm, t1, t2, rt * 1.12)
        add_capsule(bm, h1, lerp(h1, h2, 0.84), rh * 1.25)
    add_skirt(bm)
    habit = mesh_obj("habit", bm, M["wool"], parent=root)
    rm = habit.modifiers.new("remesh", "REMESH")
    rm.mode, rm.voxel_size = "VOXEL", 0.006
    sm = habit.modifiers.new("smooth", "SMOOTH")
    sm.factor, sm.iterations = 1.0, 10
    flow = bpy.data.objects.new("fold_space", None)
    link(flow, root)
    flow.scale = (1.0, 2.5, 1.0)
    # marble bands vary along x: long folds down the body, compression rings on sleeves
    folds = bpy.data.textures.new("folds", "MARBLE")
    folds.marble_type, folds.noise_basis_2 = "SOFT", "SIN"
    folds.noise_scale, folds.turbulence, folds.noise_depth = 0.09, 4.0, 2
    dp = habit.modifiers.new("folds", "DISPLACE")
    dp.texture, dp.texture_coords, dp.texture_coords_object = folds, "OBJECT", flow
    dp.strength, dp.mid_level = 0.034, 0.5
    crease = bpy.data.textures.new("crease", "CLOUDS")
    crease.noise_scale, crease.noise_depth = 0.1, 2
    dp = habit.modifiers.new("crease", "DISPLACE")
    dp.texture, dp.texture_coords, dp.texture_coords_object = crease, "OBJECT", flow
    dp.strength, dp.mid_level = 0.006, 0.5
    sub = habit.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1

    build_head(M, root)
    for s in (1, -1):
        (a1, a2, ra), (f1, f2, rf) = arm(s)
        build_hand(M, root, s)
        # leather cuff on the wrist, thongs up to the spar, wrapped round it
        wrist = lerp(f1, f2, 0.9)
        axis = Vector(f2) - Vector(f1)
        curve_obj(f"cuff{s}", ring(wrist, axis, rf + 0.007), 0.0055, M["leather"], parent=root,
                  cyclic=True, resolution=2)
        sx = Vector(f2).x / HALF
        sp = le_spar(sx)
        sax = (le_spar(sx + 0.01) - le_spar(sx - 0.01)).normalized()
        curve_obj(f"wrap{s}", helix(sp, sax, 0.0262, 0.05, 5), 0.0036, M["leather"],
                  parent=root, resolution=2)
        for dx in (-0.012, 0.012):
            p0 = Vector(wrist) + Vector((dx, 0, rf + 0.006))
            p1 = sp + Vector((dx, 0.0, -0.024))
            curve_obj(f"thong{s}{dx}", [p0, lerp(p0, p1, 0.5) + Vector((0, 0.004, 0)), p1],
                      0.0035, M["leather"], parent=root, resolution=2)

        build_foot(M, root, s)
        # ankle cuff tied to the trailing edge
        (t1, t2, rt), (h1, h2, rh) = leg(s)
        ankle = lerp(h1, h2, 0.9)
        curve_obj(f"anklecuff{s}", ring(ankle, Vector(h2) - Vector(h1), rh + 0.006), 0.0055,
                  M["leather"], parent=root, cyclic=True, resolution=2)
        sx = Vector(h2).x / HALF
        tp = surf(s * abs(sx), 1.0)
        bm = bmesh.new()
        add_sphere(bm, tp + Vector((0, -0.012, 0)), 0.03, (1.0, 1.0, 0.25))
        mesh_obj(f"tab{s}", bm, M["leather"], parent=root)
        for dx in (-0.01, 0.01):
            p0 = Vector(ankle) + Vector((dx, 0, rh + 0.005))
            p1 = tp + Vector((dx, -0.012, -0.006))
            curve_obj(f"tie{s}{dx}", [p0, lerp(p0, p1, 0.5) + Vector((0, -0.006, 0)), p1],
                      0.0035, M["leather"], parent=root, resolution=2)


# ---------------------------------------------------------------- scene setup

def setup_render(w, h, samples, preview):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.006 if not preview else 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    sc.cycles.denoising_use_gpu = True
    sc.cycles.max_bounces = 16
    sc.cycles.diffuse_bounces = 6
    sc.cycles.transmission_bounces = 12
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.sample_clamp_indirect = 8.0
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 25 if preview else 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    if CROP:
        sc.render.resolution_percentage = 100
        sc.render.use_border, sc.render.use_crop_to_border = True, True
        (sc.render.border_min_x, sc.render.border_max_x,
         sc.render.border_min_y, sc.render.border_max_y) = CROP
    return sc


CROP = None


def look_at(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def area(name, loc, target, size, energy, color=(1, 1, 1), size_y=None):
    L = bpy.data.lights.new(name, "AREA")
    L.energy, L.color = energy, color
    if size_y:
        L.shape, L.size, L.size_y = "RECTANGLE", size, size_y
    else:
        L.shape, L.size = "DISK", size
    ob = link(bpy.data.objects.new(name, L))
    ob.location = loc
    look_at(ob, target)
    return ob


def sun(name, direction, energy, angle_deg, color=(1, 1, 1)):
    L = bpy.data.lights.new(name, "SUN")
    L.energy, L.angle, L.color = energy, math.radians(angle_deg), color
    ob = link(bpy.data.objects.new(name, L))
    ob.rotation_euler = (-Vector(direction)).to_track_quat("-Z", "Y").to_euler()
    return ob


def sky_world(elev_deg, rot_deg, strength, disc=True, aerosol=1.0, air=1.0, clouds=None):
    w = bpy.data.worlds.new("sky")
    bpy.context.scene.world = w
    nt = w.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(elev_deg)
    sky.sun_rotation = math.radians(rot_deg)
    sky.sun_disc = disc
    sky.sun_size = math.radians(1.5)
    sky.aerosol_density = aerosol
    sky.air_density = air
    sky.altitude = 120.0
    bg.inputs["Strength"].default_value = strength
    if not clouds:
        nt.links.new(sky.outputs[0], bg.inputs[0])
        return w
    # broken cloud deck: noise on the sky-plane projection (x/z, y/z), faded at the horizon,
    # sunlit gold toward the sun and cool grey away from it
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    zc = nd(nt, "ShaderNodeMath", _operation="MAXIMUM")
    nt.links.new(sep.outputs["Z"], zc.inputs[0])
    zc.inputs[1].default_value = 0.03
    px = nd(nt, "ShaderNodeMath", _operation="DIVIDE")
    py = nd(nt, "ShaderNodeMath", _operation="DIVIDE")
    nt.links.new(sep.outputs["X"], px.inputs[0])
    nt.links.new(sep.outputs["Y"], py.inputs[0])
    nt.links.new(zc.outputs[0], px.inputs[1])
    nt.links.new(zc.outputs[0], py.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(px.outputs[0], comb.inputs[0])
    nt.links.new(py.outputs[0], comb.inputs[1])
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.6, 1.0)
    mp.inputs["Location"].default_value = (3.1, 1.7, 0.4)
    nt.links.new(comb.outputs[0], mp.inputs["Vector"])
    nz = nd(nt, "ShaderNodeTexNoise", Scale=0.75, Detail=10.0, Roughness=0.6, Distortion=0.35)
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    c0, c1, gain_k = clouds
    dens = ramp(nt, nz.outputs["Fac"], [(c0, (0, 0, 0)), (c1, (1, 1, 1))])
    fade = nd(nt, "ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP",
              **{"From Min": 0.04, "From Max": 0.35})
    nt.links.new(sep.outputs["Z"], fade.inputs["Value"])
    cov = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    nt.links.new(dens.outputs[0], cov.inputs[0])
    nt.links.new(fade.outputs[0], cov.inputs[1])
    cov2 = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    nt.links.new(cov.outputs[0], cov2.inputs[0])
    cov2.inputs[1].default_value = 0.92
    sd = sun_dir(elev_deg, rot_deg)
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(tc.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = tuple(sd)
    glow = ramp(nt, dot.outputs["Value"], [(-0.2, (1.0, 0.90, 0.88)), (0.45, (1.25, 1.02, 0.88)),
                                           (0.85, (1.9, 1.3, 0.85)), (1.0, (3.5, 2.1, 1.0))])
    # self-shadowed cloud bases: darker where the noise is densest
    core = ramp(nt, nz.outputs["Fac"], [(0.58, (1.15, 1.1, 1.05)), (0.8, (0.62, 0.6, 0.66))])
    cc = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    nt.links.new(glow.outputs[0], cc.inputs[6])
    nt.links.new(core.outputs[0], cc.inputs[7])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(sky.outputs[0], bw.inputs[0])
    gain = nd(nt, "ShaderNodeMath", _operation="MULTIPLY")
    nt.links.new(bw.outputs[0], gain.inputs[0])
    gain.inputs[1].default_value = gain_k
    cc_s = nd(nt, "ShaderNodeVectorMath", _operation="SCALE")
    nt.links.new(cc.outputs[2], cc_s.inputs[0])
    nt.links.new(gain.outputs[0], cc_s.inputs["Scale"])
    mix = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    nt.links.new(cov2.outputs[0], mix.inputs["Factor"])
    nt.links.new(sky.outputs[0], mix.inputs[6])
    nt.links.new(cc_s.outputs[0], mix.inputs[7])
    below = nd(nt, "ShaderNodeMapRange", _interpolation_type="SMOOTHSTEP",
               **{"From Min": -0.02, "From Max": 0.0, "To Min": 1.0, "To Max": 0.0})
    nt.links.new(sep.outputs["Z"], below.inputs["Value"])
    hz = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    nt.links.new(below.outputs[0], hz.inputs["Factor"])
    nt.links.new(mix.outputs[2], hz.inputs[6])
    hz.inputs[7].default_value = (*(c * HAZE_K / max(strength, 1e-3) for c in HAZE), 1)
    nt.links.new(hz.outputs[2], bg.inputs[0])
    return w


def sun_dir(elev_deg, rot_deg):
    e, r = math.radians(elev_deg), math.radians(rot_deg)
    return Vector((-math.sin(r) * math.cos(e), math.cos(r) * math.cos(e), math.sin(e)))


def project(cam, pts):
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    out = {}
    for k, p in pts.items():
        co = world_to_camera_view(sc, cam, Vector(p))
        out[k] = [round(co.x * rx, 1), round((1 - co.y) * ry, 1)]
    return out


def materials():
    return {"linen": mat_linen(), "wood": mat_wood(), "leather": mat_leather(),
            "wool": mat_wool(), "skin": mat_skin()}


def reset():
    global COLL
    bpy.ops.wm.read_factory_settings(use_empty=True)
    COLL = bpy.context.scene.collection


# ---------------------------------------------------------------- shots

FIG_W, FIG_H = 3600, 2400


# "above" is the camera of render_blender.py (same framing as the current figure);
# "below" is a low three-quarter view that shows the hand and foot attachments.
FIG_VIEWS = {
    "above": dict(cam=(3.6, -7.4, 5.0), aim=(0, 0.3, -0.15), lens=56, catcher=True),
    "below": dict(cam=(5.9, -5.4, -2.6), aim=(0.5, 0.45, -0.12), lens=50, catcher=False),
    "studio": dict(cam=(5.9, -5.4, -2.6), aim=(0.5, 0.45, -0.12), lens=50, catcher=False),
}


def shot_figure(preview, samples, view):
    V = FIG_VIEWS[view]
    reset()
    sc = setup_render(FIG_W, FIG_H, samples, preview)
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    build_craft(materials())

    w = bpy.data.worlds.new("studio")
    sc.world = w
    bg = w.node_tree.nodes["Background"]
    if view == "studio":
        # dramatic three-point: hard-ish warm key high front-left, strong cool rim from
        # behind, dim fill from camera side; dark warm surround for contrast
        bg.inputs["Color"].default_value = (0.35, 0.31, 0.27, 1)
        bg.inputs["Strength"].default_value = 0.18
        area("key", (-3.5, -3.0, 4.5), (0.2, 0.3, -0.3), 1.6, 2100, (1.0, 0.86, 0.68))
        area("rim", (-1.0, 6.5, 2.2), (0.2, 0.5, -0.3), 2.0, 3200, (0.80, 0.88, 1.0))
        area("rim2", (5.0, 5.0, -2.5), (0.2, 0.6, -0.5), 1.5, 1300, (0.85, 0.9, 1.0))
        area("fill", (6.5, -6.0, -3.0), (0.3, 0.4, -0.3), 5.0, 260, (1.0, 0.95, 0.9))
        area("under", (0.5, -0.5, -4.0), (0, 0.3, -0.4), 6.0, 90, (1.0, 0.85, 0.65))
    else:
        # soft warm key (upper front-left), big overhead softbox, cool rim from aft,
        # warm bounce from below (as off a pale floor)
        bg.inputs["Color"].default_value = (0.92, 0.90, 0.86, 1)
        bg.inputs["Strength"].default_value = 0.45
        sun("key", (-0.45, -0.55, 0.70), KEY[view], 6.0, (1.0, 0.95, 0.87))
        area("softbox", (0.6, -1.0, 6.0), (0, 0.3, 0), 6.0, 0.25 * KEY[view] * 900 / 0.85,
             (1.0, 0.98, 0.95))
        area("rim", (-1.5, 6.5, 1.0), (0, 0.4, -0.2), 4.0, 1400, (0.88, 0.93, 1.0))
        area("bounce", (0.5, -0.5, -4.0), (0, 0.3, -0.4), 7.0, BOUNCE[view], (1.0, 0.92, 0.80))
    if view == "below":
        # kicker from low behind-right for a rim on the figure, low front-left modelling light
        area("kicker", (5.5, 4.5, -2.2), (0.2, 0.6, -0.5), 2.5, KICK, (0.92, 0.95, 1.0))
        area("model", (-3.5, -4.5, -3.0), (0.1, 0.3, -0.5), 3.0, MODEL, (1.0, 0.94, 0.86))

    if V["catcher"]:
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.3, -1.45))
        bpy.context.object.is_shadow_catcher = True

    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.05, 60000.0
    cd.lens = V["lens"]
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 11.0
    cam = link(bpy.data.objects.new("cam", cd))
    cam.location = V["cam"]
    tgt = Vector(V["aim"])
    look_at(cam, tgt)
    cd.dof.focus_distance = (Vector(hand(1)[0]) - cam.location).length * 0.5 + \
        (tgt - cam.location).length * 0.5
    sc.camera = cam
    bpy.context.view_layer.update()

    (h1, h2, rh) = leg(1)[1]
    anchors = project(cam, {
        "tipR": tuple(surf(1, 0.5)),
        "tipL": tuple(surf(-1, 0.5)),
        "batten": tuple(surf(-0.5, 0.5) + Vector((0, 0, 0.01))),
        "hand": hand(1)[0],
        "foot": tuple(lerp(h1, h2, 0.9)),
        "head": HEAD[0],
        "tail": TAIL[view],
        "lash": tuple(le_spar(0.5)),
        "batten_near": tuple(surf(0.5, 0.62) + Vector((0, 0, 0.01))),
        "te_centre": tuple(surf(0, 1.0)),
        # schematic ghost of a conventional tail (for an optional dashed outline only)
        "boom0": tuple(surf(0, 1.0)), "boom1": (0, 2.15, 0.02),
        "gh0": (-0.65, 2.15, 0.02), "gh1": (0.65, 2.15, 0.02),
        "gh2": (0.65, 2.6, 0.02), "gh3": (-0.65, 2.6, 0.02), "gh_c": (0, 2.38, 0.02),
    })
    anchors["_size"] = [FIG_W, FIG_H]
    (HERE / f"hero_figure_{view}_points.json").write_text(json.dumps(anchors, indent=2))
    if ANCHORS_ONLY:
        return
    sc.render.filepath = str(HERE / (f"hero_figure_{view}_render"
                                     + ("_preview" if preview else "") + ".png"))
    bpy.ops.render.render(write_still=True)


TOWER_X0, TOWER_X1, TOWER_D, TOWER_BASE = -1.0, 5.0, 6.0, -18.0


def tone(bm, verts, rng):
    """Per-block tone in a colour attribute (each stone weathers differently)."""
    lay = bm.loops.layers.color.get("tone") or bm.loops.layers.color.new("tone")
    t = rng.random()
    faces = {f for v in verts for f in v.link_faces}
    for f in faces:
        for lp in f.loops:
            lp[lay] = (t, rng.random() * 0.15 + t * 0.85, 0, 1)


def ashlar(bm, rng, along, a, b, t0, t1, z0, z1, gap=0.012):
    """Coursed ashlar blocks in a wall running along 'x' or 'y' from a to b."""
    z = z0
    k = 0
    while z < z1 - 0.05:
        ch = min(rng.uniform(0.26, 0.34), z1 - z)
        p = a
        first = True
        while p < b:
            L = min(rng.uniform(0.45, 0.9) * (0.55 if first and k % 2 else 1.0), b - p)
            first = False
            if L > 0.05:
                c = p + L / 2
                th = (t1 - t0) - rng.uniform(0, 0.02)
                tm = (t0 + t1) / 2 - rng.uniform(0, 0.018)
                ctr = (c, tm, z + ch / 2) if along == "x" else (tm, c, z + ch / 2)
                dims = (L - gap, th, ch - gap) if along == "x" else (th, L - gap, ch - gap)
                M = Matrix.Translation(ctr) @ Matrix.Rotation(rng.uniform(-0.012, 0.012), 4, "Z") \
                    @ Matrix.Rotation(rng.uniform(-0.01, 0.01), 4, "X") \
                    @ Matrix.Diagonal((*dims, 1))
                tone(bm, bmesh.ops.create_cube(bm, size=1.0, matrix=M)["verts"], rng)
            p += L
        z += ch
        k += 1


def build_tower(stone):
    """A plain ashlar tower top with a parapet: generic, no claimed architecture."""
    rng = random.Random(7)
    x0, x1, D, zb = TOWER_X0, TOWER_X1, TOWER_D, TOWER_BASE
    th, top = 0.55, 1.05
    bm = bmesh.new()
    ashlar(bm, rng, "x", x0, x1, 0.0, 0.35, zb, 0.0)          # front face (faces -y)
    ashlar(bm, rng, "y", 0.0, D, x0, x0 + 0.35, zb, 0.0)      # side face (faces -x)
    ashlar(bm, rng, "x", x0, x1, 0.0, th, 0.0, top)           # parapets
    ashlar(bm, rng, "y", th, D, x0, x0 + th, 0.0, top)
    for along, a, b in (("x", x0, x1), ("y", th, D)):         # coping
        p = a
        while p < b:
            L = min(rng.uniform(0.7, 1.1), b - p)
            c = p + L / 2
            ctr = (c, th / 2, top + 0.06) if along == "x" else (x0 + th / 2, c, top + 0.06)
            dims = (L - 0.014, th + 0.08, 0.12) if along == "x" else (th + 0.08, L - 0.014, 0.12)
            tone(bm, bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(ctr) @
                                           Matrix.Rotation(rng.uniform(-0.01, 0.01), 4, "Z") @
                                           Matrix.Diagonal((*dims, 1)))["verts"], rng)
            p += L
    ob = mesh_obj("tower_blocks", bm, stone, smooth=False)
    bv = ob.modifiers.new("bevel", "BEVEL")
    bv.width, bv.segments, bv.limit_method = 0.022, 3, "ANGLE"
    # mortar/rubble core behind the ashlar, and the roof
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(
        ((x0 + x1) / 2 + 0.01, D / 2 + 0.01, (zb - 12 + top - 0.02) / 2)) @
        Matrix.Diagonal((x1 - x0 - 0.02, D - 0.02, top - 0.02 - zb + 12, 1)))
    mesh_obj("core", bm, mat_mortar(), smooth=False)


def ground_height(x, y):
    """Hilltop site: flat near the tower, a valley falling away ahead (-y), hills beyond."""
    from mathutils import noise
    r = math.hypot(x, y)
    ahead = max(0.0, -y)
    z = -20.0
    z -= 28.0 * smooth(60, 900, ahead)                          # valley below the escarpment
    z += 70.0 * smooth(1800, 5000, r) - 40.0 * smooth(9000, 30000, r)   # far hills
    w = smooth(150, 1200, r)
    z += w * 30.0 * noise.fractal(Vector((x / 1600, y / 1600, 0.3)), 0.5, 2.0, 4)
    z += w * 4.0 * noise.fractal(Vector((x / 220, y / 220, 1.7)), 0.6, 2.0, 3)
    return z


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def build_ground(mat, rmax=30000.0, nr=260, na=360):
    """Polar grid centred on the tower: dense nearby, coarse at the horizon."""
    bm = bmesh.new()
    rings = []
    for i in range(nr):
        r = 8.0 * (rmax / 8.0) ** (i / (nr - 1))
        ring_v = []
        for j in range(na):
            a = 2 * math.pi * j / na
            x, y = r * math.cos(a), r * math.sin(a)
            ring_v.append(bm.verts.new((x, y, ground_height(x, y))))
        rings.append(ring_v)
    for i in range(nr - 1):
        for j in range(na):
            k = (j + 1) % na
            bm.faces.new([rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]])
    bm.faces.new(rings[0])
    mesh_obj("ground", bm, mat)


def mat_rubble():
    """Weathered rubble stone: per-stone tone, pitted surface, lichen on top faces, AO."""
    m, nt, bsdf, out = new_mat("rubble")
    tc = nd(nt, "ShaderNodeTexCoord")
    co = tc.outputs["Object"]
    att = nd(nt, "ShaderNodeVertexColor", _layer_name="tone")
    sepa = nd(nt, "ShaderNodeSeparateColor")
    ln(nt, att.outputs["Color"], sepa.inputs[0])
    nz = nd(nt, "ShaderNodeTexNoise", Scale=9.0, Detail=12.0, Roughness=0.65)
    ln(nt, co, nz.inputs["Vector"])
    blend = nd(nt, "ShaderNodeMix", _data_type="FLOAT", Factor=0.45)
    ln(nt, nz.outputs["Fac"], blend.inputs[2])
    ln(nt, sepa.outputs[0], blend.inputs[3])
    col = ramp(nt, blend.outputs[0], [(0.2, (0.13, 0.115, 0.09)), (0.45, (0.24, 0.21, 0.165)),
                                      (0.7, (0.34, 0.30, 0.235)), (0.9, (0.40, 0.36, 0.29))])
    # lichen: crusty yellow-grey and grey-green patches, favouring upward faces
    geo = nd(nt, "ShaderNodeNewGeometry")
    sepn = nd(nt, "ShaderNodeSeparateXYZ")
    ln(nt, geo.outputs["Normal"], sepn.inputs[0])
    lich = nd(nt, "ShaderNodeTexNoise", Scale=6.0, Detail=10.0, Roughness=0.7)
    ln(nt, co, lich.inputs["Vector"])
    up = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, sepn.outputs["Z"], up.inputs[0])
    up.inputs[1].default_value, up.inputs[2].default_value = 0.18, 0.0
    lf = nd(nt, "ShaderNodeMath", _operation="ADD")
    ln(nt, lich.outputs["Fac"], lf.inputs[0])
    ln(nt, up.outputs[0], lf.inputs[1])
    lm = ramp(nt, lf.outputs[0], [(0.60, (0, 0, 0)), (0.66, (1, 1, 1))])
    lcol = ramp(nt, nz.outputs["Fac"], [(0.4, (0.26, 0.25, 0.12)), (0.6, (0.30, 0.31, 0.20))])
    mixc = nd(nt, "ShaderNodeMix", _data_type="RGBA")
    ln(nt, lm.outputs[0], mixc.inputs["Factor"])
    ln(nt, col.outputs[0], mixc.inputs[6])
    ln(nt, lcol.outputs[0], mixc.inputs[7])
    ln(nt, ao(nt, mixc.outputs[2], 0.08), bsdf.inputs["Base Color"])
    fine = nd(nt, "ShaderNodeTexNoise", Scale=60.0, Detail=10.0, Roughness=0.7)
    ln(nt, co, fine.inputs["Vector"])
    pits = nd(nt, "ShaderNodeTexVoronoi", Scale=45.0)
    ln(nt, co, pits.inputs["Vector"])
    b1 = bump(nt, fine.outputs["Fac"], 0.6, 0.006)
    b2 = bump(nt, pits.outputs["Distance"], 0.35, 0.004, b1.outputs[0])
    b3 = bump(nt, lm.outputs[0], 0.3, 0.002, b2.outputs[0])
    ln(nt, b3.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.92)
    return m


def mat_lime():
    m, nt, bsdf, out = new_mat("lime_mortar")
    tc = nd(nt, "ShaderNodeTexCoord")
    nz = nd(nt, "ShaderNodeTexNoise", Scale=30.0, Detail=8.0)
    ln(nt, tc.outputs["Object"], nz.inputs["Vector"])
    col = ramp(nt, nz.outputs["Fac"], [(0.35, (0.17, 0.155, 0.13)), (0.7, (0.30, 0.28, 0.24))])
    ln(nt, ao(nt, col.outputs[0], 0.05), bsdf.inputs["Base Color"])
    b = bump(nt, nz.outputs["Fac"], 0.5, 0.004)
    ln(nt, b.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.97)
    return m


def build_rubble(x0, x1, top=1.05, th=0.6, seed=3):
    """A weathered rubble-stone parapet (outer face at y=0), with lime mortar and coping."""
    rng = random.Random(seed)
    bm = bmesh.new()

    def stone(c, dims, rot=0.05):
        M = (Matrix.Translation(c) @ Matrix.Rotation(rng.uniform(-rot, rot), 4, "X") @
             Matrix.Rotation(rng.uniform(-rot, rot), 4, "Y") @
             Matrix.Rotation(rng.uniform(-rot, rot), 4, "Z") @ Matrix.Diagonal((*dims, 1)))
        n0 = len(bm.verts)
        r = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
        edges = list({e for v in r["verts"] for e in v.link_edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=3, use_grid_fill=True)
        bm.verts.ensure_lookup_table()
        tone(bm, [v for v in bm.verts[n0:] if v.is_valid], rng)

    for face_y, sgn in ((0.0, 1), (th, -1)):
        z = 0.0
        while z < top - 0.12:
            h = min(rng.uniform(0.12, 0.26), top - 0.06 - z)
            x = x0 + rng.uniform(-0.2, 0)
            while x < x1:
                L = rng.uniform(0.16, 0.48)
                dep = rng.uniform(0.18, 0.3)
                stick = rng.uniform(-0.03, 0.01)
                stone((x + L / 2, face_y + sgn * (dep / 2 + stick), z + h / 2),
                      (L - rng.uniform(0.02, 0.05), dep, h - rng.uniform(0.02, 0.04)))
                x += L
            z += h
    x = x0
    while x < x1:                                   # rough coping slabs
        L = rng.uniform(0.35, 0.7)
        stone((x + L / 2, th / 2 + rng.uniform(-0.03, 0.03), top + 0.04),
              (L - 0.03, th + rng.uniform(0.0, 0.1), rng.uniform(0.09, 0.14)), rot=0.04)
        x += L
    ob = mesh_obj("rubble", bm, mat_rubble())
    tex = bpy.data.textures.new("rubble_rough", "CLOUDS")
    tex.noise_scale, tex.noise_depth = 0.07, 3
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1
    dp = ob.modifiers.new("rough", "DISPLACE")
    dp.texture, dp.strength, dp.texture_coords = tex, 0.035, "GLOBAL"
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, th / 2, (top - 0.02) / 2))
                          @ Matrix.Diagonal((x1 - x0, th - 0.12, top - 0.02, 1)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, th + 3.0, -0.05))
                          @ Matrix.Diagonal((x1 - x0 + 4, 6.0, 0.1, 1)))
    mesh_obj("mortar", bm, mat_lime(), smooth=False)
    # the tower face below the parapet, out of view except at the edge
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, 3.0, -10.0))
                          @ Matrix.Diagonal((x1 - x0 + 4, 6.0, 20.0, 1)))
    mesh_obj("towerbody", bm, mat_lime(), smooth=False)


def build_volume(density, color, anis, size=(600, 600, 120), centre=(0, -250, 30)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(centre) @
                          Matrix.Diagonal((*size, 1)))
    m = bpy.data.materials.new("haze")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    v = nd(nt, "ShaderNodeVolumePrincipled", Density=density, Anisotropy=anis)
    v.inputs["Color"].default_value = (*color, 1)
    ln(nt, v.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    mesh_obj("haze", bm, m, smooth=False)


COVER_W, COVER_H = 2480, 3508

# Each cover: camera, craft pose, sun, sky, scenery. Craft heads toward -y; tower roof z=0,
# parapet outer face at y=0, ground about 20 m below.
COVERS = {
    # v1 (first pass): worm's-eye of the craft over a plain ashlar tower
    "v1_tower": dict(
        cam=(-2.6, -7.4, -2.9), aim=(0.65, -2.0, 2.4), lens=31, fstop=4.0,
        craft=((0.6, -2.6, 1.55), (4, -6, -12)), sun=(6.0, 119.0, 6.5, (1.0, 0.62, 0.36), 2.5),
        sky=0.17, clouds=(0.50, 0.60, 1.8), exposure=0.2, scenery=("tower",),
        haze=(0.95, 0.68, 0.45)),
    # (a) over a rubble parapet whose end sits in the lower-left corner: the craft glides out
    # over the valley, seen three-quarter from above and behind
    "a_parapet": dict(
        cam=(2.7, 1.0, 1.45), aim=(-0.9, -8.0, -0.3), lens=36, fstop=4.0, rubble=(-6.0, 1.7),
        craft=((-0.9, -6.6, -1.3), (-8, 5, 14)), sun=(11.0, 150.0, 5.0, (1.0, 0.70, 0.46), 2.0),
        sky=0.22, clouds=(0.46, 0.60, 1.6), exposure=0.0, scenery=("rubble", "ground"),
        haze=(0.78, 0.74, 0.70), haze_k=0.55, haze_dist=11000.0, focus=(0.0, 0.3, -0.3)),
    # (b) underneath and ahead of the craft, sun behind and above it: the linen glows and
    # the battens and pilot silhouette
    "b_backlit": dict(
        cam=(3.0, -14.5, -9.0), aim=(-0.6, -8.4, -1.9), lens=35, fstop=4.0,
        craft=((-0.3, -9.0, -1.0), (6, -4, 25)), sun=(22.0, 33.0, 7.0, (1.0, 0.74, 0.50), 1.0),
        sky=0.20, clouds=(0.55, 0.66, 1.4), exposure=0.0, scenery=("ground",),
        haze=(0.85, 0.78, 0.68), haze_k=0.6, haze_dist=11000.0, focus=(0.0, 0.3, -0.2)),
    # (c) dusk side light; thin volumetric haze lies in the valley below the tower
    "c_dusk": dict(
        cam=(5.5, -3.0, 1.6), aim=(-0.5, -11.0, -0.4), lens=40, fstop=5.0,
        craft=((-0.8, -10.5, -0.4), (-4, -10, 6)), sun=(3.5, 95.0, 7.0, (1.0, 0.52, 0.26), 1.0),
        sky=0.15, clouds=(0.46, 0.60, 1.5), exposure=0.3, scenery=("rubble", "ground", "volume"),
        haze=(0.85, 0.62, 0.46), haze_k=0.35, haze_dist=9000.0, focus=(0.0, 0.3, -0.3),
        volume=(0.0006, (1.0, 0.92, 0.84), 0.7, (2400, 2400, 50), (0, -1000, -38))),
}


def shot_cover(preview, samples, name):
    C = COVERS[name]
    global HAZE, HAZE_K, HAZE_DIST
    HAZE = C["haze"]
    HAZE_K, HAZE_DIST = C.get("haze_k", 0.6), C.get("haze_dist", 6000.0)
    reset()
    sc = setup_render(COVER_W, COVER_H, samples, preview)
    sc.view_settings.look = "AgX - Base Contrast"
    sc.view_settings.exposure = C["exposure"]
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = "RGB"
    sc.cycles.volume_bounces = 2
    M = materials()
    craft = build_craft(M)
    loc, rot = C["craft"]
    craft.location = loc
    craft.rotation_euler = tuple(math.radians(a) for a in rot)

    if "tower" in C["scenery"]:
        build_tower(mat_stone())
        build_ground_old(mat_ground())
    if "rubble" in C["scenery"]:
        build_rubble(*C.get("rubble", (-2.5, 4.0)))
    if "ground" in C["scenery"]:
        build_ground(mat_ground())
    if "volume" in C["scenery"]:
        build_volume(*C["volume"])

    elev, srot, energy, color, ang = C["sun"]
    sky_world(elev, srot, C["sky"], disc=False, aerosol=2.5, air=1.0, clouds=C["clouds"])
    sun("sun", sun_dir(elev, srot), energy, ang, color)

    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.05, 60000.0
    cd.lens = C["lens"]
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = C["fstop"]
    cam = link(bpy.data.objects.new("cam", cd))
    cam.location = C["cam"]
    look_at(cam, C["aim"])
    bpy.context.view_layer.update()
    focus = craft.matrix_world @ Vector(C.get("focus", (0.4, 0.1, -0.3)))
    cd.dof.focus_distance = (focus - cam.location).length
    sc.camera = cam
    sc.render.filepath = str(HERE / (f"hero_cover_{name}" + ("_preview" if preview else "")
                                     + ".png"))
    bpy.ops.render.render(write_still=True)


def build_ground_old(mat):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=400, y_subdivisions=400, size=12000,
                                    location=(0, -4000, -24.0))
    g = bpy.context.object
    g.data.materials.append(mat)


BOUNCE = {"above": 260, "below": 140, "studio": 0}
KEY = {"above": 2.8, "below": 3.4, "studio": 0}
KICK, MODEL = 700, 260
# empty space where a tail would be: on the centreline aft of the trailing edge
TAIL = {"above": (0, 1.95, 0.0), "below": (0, 2.8, 0.0), "studio": (0, 2.8, 0.0)}
ANCHORS_ONLY = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default="all", choices=["figure", "cover", "all"])
    ap.add_argument("--view", default="all", choices=["above", "below", "studio", "all"])
    ap.add_argument("--cover", default="all", help="comma list of COVERS keys, or all")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--anchors-only", action="store_true",
                    help="write the projected callout anchors without rendering")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("X0", "X1", "Y0", "Y1"),
                    help="full-res border render of a region (fractions, y from bottom)")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    global CROP, ANCHORS_ONLY
    CROP = a.crop
    ANCHORS_ONLY = a.anchors_only
    times = {}
    if a.shot in ("figure", "all"):
        for view in (FIG_VIEWS if a.view == "all" else [a.view]):
            t = time.time()
            shot_figure(a.preview, a.samples or (48 if a.preview else 512), view)
            times[f"figure_{view}"] = time.time() - t
    if a.shot in ("cover", "all"):
        for name in (COVERS if a.cover == "all" else a.cover.split(",")):
            t = time.time()
            shot_cover(a.preview, a.samples or (48 if a.preview else 768), name)
            times[f"cover_{name}"] = time.time() - t
    print("render times (s):", {k: round(v, 1) for k, v in times.items()})


if __name__ == "__main__":
    main()
