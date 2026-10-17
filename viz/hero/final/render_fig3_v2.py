"""Figure 3 v2: path-traced re-render of the apparatus with the ORIGINAL camera and anchors.

Content is that of viz/render_blender.py + viz/compose_apparatus.py: the same camera
(location, aim, 62 mm lens, 3:2 frame), the same pilot posture and the same anchor
points. The wing root chord is the hero value (7 m^2 planform at the 5.29 m span, see
render_hero.CHORD_ROOT_HERO). Only the rendering differs: Cycles on Metal, linen / ash /
leather / wool materials from render_hero.py, soft key + rim + under-wing fill, a soft
contact shadow, denoising.

  .venv-bpy/bin/python viz/hero/final/render_fig3_v2.py [--pct 25] [--samples 64]
Writes viz/hero/final/_work/fig3_v2_render[_pPCT].png and fig3_v2_points.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy  # noqa: I001
import bmesh
from mathutils import Euler, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import render_hero as rh  # noqa: E402
from render_hero import (HALF, HEAD, SWEEP, foot, hand, ln, nd, new_mat, ramp,  # noqa: E402
                         bump, set_in, surf)

WORK = HERE / "_work"
WORK.mkdir(exist_ok=True)

FIG_W, FIG_H = 3600, 2400                 # 2x the original 1800 x 1200, same aspect
CAM = dict(loc=(3.6, -7.4, 5.0), aim=(0, 0.3, -0.15), lens=62)   # render_blender.camera()
ORIG_SUN_EULER = (math.radians(52), math.radians(8), math.radians(40))
CATCHER_Z = -1.45


# ---------------------------------------------------------------- materials

def mat_wool():
    """Undyed oatmeal / grey-brown wool: fulled twill, fibre fuzz, fold cavities, sheen."""
    base = (0.11, 0.092, 0.072)
    m, nt, bsdf, out = new_mat("wool_oatmeal")
    tc = nd(nt, "ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    big = nd(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=5.0, Roughness=0.6)
    ln(nt, obj, big.inputs["Vector"])
    heather = nd(nt, "ShaderNodeTexNoise", Scale=180.0, Detail=3.0)
    ln(nt, obj, heather.inputs["Vector"])
    mix = nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    ln(nt, heather.outputs["Fac"], mix.inputs[0])
    mix.inputs[1].default_value = 0.6
    ln(nt, big.outputs["Fac"], mix.inputs[2])
    col = ramp(nt, mix.outputs[0], [(0.62, tuple(c * 0.80 for c in base)),
                                    (0.92, tuple(c * 1.18 for c in base))])
    # fold cavities darker, ridges lighter (Cycles pointiness + AO)
    geo = nd(nt, "ShaderNodeNewGeometry")
    pr = nd(nt, "ShaderNodeMapRange", **{"From Min": 0.45, "From Max": 0.55,
                                         "To Min": 0.72, "To Max": 1.10})
    ln(nt, geo.outputs["Pointiness"], pr.inputs["Value"])
    cav = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    ln(nt, col.outputs[0], cav.inputs[6])
    ln(nt, pr.outputs[0], cav.inputs[7])
    ao = nd(nt, "ShaderNodeAmbientOcclusion", Distance=0.08, _samples=8)
    ln(nt, cav.outputs[2], ao.inputs["Color"])
    aom = nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=0.7)
    ln(nt, cav.outputs[2], aom.inputs[6])
    ln(nt, ao.outputs["AO"], aom.inputs[7])
    ln(nt, aom.outputs[2], bsdf.inputs["Base Color"])
    fuzz = nd(nt, "ShaderNodeTexNoise", Scale=700.0, Detail=4.0)
    ln(nt, obj, fuzz.inputs["Vector"])
    twill = nd(nt, "ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="DIAGONAL",
               Scale=120.0, Distortion=3.0, Detail=3.0)
    ln(nt, obj, twill.inputs["Vector"])
    b1 = bump(nt, fuzz.outputs["Fac"], 0.08, 0.0008)
    b2 = bump(nt, twill.outputs["Fac"], 0.16, 0.0012, b1.outputs[0])
    ln(nt, b2.outputs[0], bsdf.inputs["Normal"])
    set_in(bsdf, Roughness=0.93, Sheen_Weight=0.35, Sheen_Roughness=0.35,
           Specular_IOR_Level=0.12)
    bsdf.inputs["Sheen Tint"].default_value = (0.95, 0.88, 0.76, 1)
    return m


def mat_skin():
    m, nt, bsdf, out = new_mat("skin_weathered")
    set_in(bsdf, Roughness=0.55, Subsurface_Weight=0.35, Subsurface_Scale=0.006)
    rgb = nd(nt, "ShaderNodeRGB")
    rgb.outputs[0].default_value = (0.19, 0.13, 0.095, 1)
    ao = nd(nt, "ShaderNodeAmbientOcclusion", Distance=0.05, _samples=8)
    ln(nt, rgb.outputs[0], ao.inputs["Color"])
    ln(nt, ao.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.25)
    return m


def tune_linen(m):
    """Brighter, slightly warmer flax with a little more translucency (frame shows through)."""
    nt = m.node_tree
    for n in nt.nodes:
        if n.type == "VALTORGB" and len(n.color_ramp.elements) == 3:
            stops = [(0.66, (0.54, 0.47, 0.35)), (0.84, (0.67, 0.60, 0.47)),
                     (1.0, (0.76, 0.71, 0.58))]
            for e, (p, c) in zip(sorted(n.color_ramp.elements, key=lambda e: e.position), stops):
                e.position, e.color = p, (*c, 1)
        if n.type == "MATH" and n.operation == "MULTIPLY_ADD" and \
                abs(n.inputs[2].default_value - 0.34) < 1e-6:
            n.inputs[1].default_value, n.inputs[2].default_value = -0.25, LINEN_TRANS
        if n.type == "BUMP" and abs(n.inputs["Strength"].default_value - 0.22) < 1e-6:
            n.inputs["Strength"].default_value = 0.32            # cloth wrinkles
    return m


LINEN_TRANS = 0.46


def tune_wood(m):
    """Oiled ash: warm honey with visible long grain, thinner coat (less washed-out)."""
    nt = m.node_tree
    for n in nt.nodes:
        if n.type == "VALTORGB":
            cols = [(0.085, 0.042, 0.016), (0.18, 0.10, 0.04), (0.29, 0.17, 0.075)]
            for e, c in zip(n.color_ramp.elements, cols):
                e.color = (*c, 1)
        if n.type == "BUMP":
            n.inputs["Strength"].default_value = 0.09
    set_in(nt.nodes["Principled BSDF"], Roughness=0.45, Coat_Weight=0.18, Coat_Roughness=0.3)
    return m


def tune_habit(craft):
    """Softer creases on the habit (the fine cloud noise read as lumps at figure scale)."""
    for ob in craft.children_recursive:
        if ob.name == "habit":
            ob.modifiers["crease"].strength = 0.0025
            ob.modifiers["folds"].strength = 0.024


def tune_leather(m):
    """Darker, less saturated, less glossy: lashings read as small dark bindings."""
    nt = m.node_tree
    for n in nt.nodes:
        if n.type == "VALTORGB":
            n.color_ramp.elements[0].color = (0.055, 0.028, 0.013, 1)
            n.color_ramp.elements[-1].color = (0.13, 0.068, 0.032, 1)
    set_in(nt.nodes["Principled BSDF"], Roughness=0.78, Coat_Weight=0.0,
           Specular_IOR_Level=0.3)
    return m


def materials():
    M = rh.materials()
    M["leather"] = tune_leather(M["leather"])
    M["wood"] = tune_wood(M["wood"])
    M["linen"] = tune_linen(M["linen"])
    M["wool"] = mat_wool()
    M["skin"] = mat_skin()
    return M


# ---------------------------------------------------------------- deeper cowl

def build_head(M, root):
    """Head as render_hero, but the cowl is deeper with a forward brim: the face sits in shade."""
    c = Vector(HEAD[0])
    R_, U_, F_ = rh.head_frame()
    rad = (0.098, 0.115, 0.112)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co.normalized()
        jaw = 1.0 - 0.18 * max(0.0, -y) * max(0.0, z)
        p = Vector((x * rad[0] * jaw, y * rad[1], z * rad[2]))
        n = Vector((x / rad[0], y / rad[1], z / rad[2])).normalized()
        p += n * rh.face_offset(x, y, z)
        v.co = c + R_ * p.x + U_ * p.y + F_ * p.z
    face = rh.mesh_obj("head", bm, M["skin"], parent=root)
    face.modifiers.new("sub", "SUBSURF").render_levels = 1

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > HOOD_OPEN], context="VERTS")
    hr = (0.138, 0.150, 0.155)
    hc = c + F_ * HOOD_FWD + U_ * 0.014
    for v in bm.verts:
        x, y, z = v.co
        back = max(0.0, -z)
        front = max(0.0, z)
        p = Vector((x * hr[0] * (1 + 0.08 * back), y * hr[1],
                    z * hr[2] * (1 + 0.55 * back ** 2)))
        p.y -= 0.05 * back ** 2.5
        p.y += 0.012 * max(0.0, y) * back
        p.y += 0.018 * max(0.0, y) * front ** 2      # brim overhangs the brow
        v.co = hc + R_ * p.x + U_ * p.y + F_ * p.z
    hood = rh.mesh_obj("hood", bm, M["wool"], parent=root)
    so = hood.modifiers.new("solid", "SOLIDIFY")
    so.thickness, so.offset = 0.014, -1.0
    tex = bpy.data.textures.new("hoodfolds", "MARBLE")
    tex.marble_type, tex.noise_basis_2 = "SOFT", "SIN"
    tex.noise_scale, tex.turbulence = 0.05, 3.0
    dp = hood.modifiers.new("folds", "DISPLACE")
    dp.texture, dp.strength = tex, 0.013
    hs = hood.modifiers.new("sub", "SUBSURF")
    hs.levels = hs.render_levels = 2


HOOD_OPEN, HOOD_FWD = 0.64, 0.07


# ---------------------------------------------------------------- lighting

def sun_from_euler(eul):
    return (Euler(eul).to_matrix() @ Vector((0, 0, -1))).normalized()   # light travel dir


def craft_only(lamp, craft):
    """Light linking: the lamp lights the craft only, so it casts no shadow on the catcher."""
    coll = bpy.data.collections.new(f"recv_{lamp.name}")
    for ob in [craft] + list(craft.children_recursive):
        coll.objects.link(ob)
    lamp.light_linking.receiver_collection = coll


def lights(L, craft):
    w = bpy.data.worlds.new("studio")
    bpy.context.scene.world = w
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.93, 0.91, 0.87, 1)
    bg.inputs["Strength"].default_value = L["world"]
    d = sun_from_euler(ORIG_SUN_EULER)
    rh.sun("key", -d, L["key"], L["key_angle"], (1.0, 0.95, 0.86))
    # broad overhead softbox: soft top light for the cloth (craft only: no extra floor shadow)
    sb = rh.area("softbox", (-1.0, -2.0, 6.5), (0, 0.3, 0), 6.0, L["softbox"], (1.0, 0.98, 0.95))
    craft_only(sb, craft)
    # cool rim from aft and high: outlines trailing edge, tips and the pilot's back
    rim = rh.area("rim", (1.5, 7.0, 2.6), (0, 0.4, -0.3), 3.0, L["rim"], (0.86, 0.92, 1.0))
    craft_only(rim, craft)
    # warm fill under the wing from the camera side (the pilot is in the wing's shadow)
    pf = rh.area("pilotfill", (2.4, -3.4, -1.0), (0.0, -0.3, -0.5), 1.6, L["pilotfill"],
                 (1.0, 0.92, 0.80))
    craft_only(pf, craft)
    # warm bounce just above the floor, facing up: under-lights the linen (translucent glow)
    bo = rh.area("bounce", (0.3, 0.4, CATCHER_Z + 0.25), (0.3, 0.4, 2.0), 9.0, L["bounce"],
                 (1.0, 0.90, 0.76))
    craft_only(bo, craft)


LIGHT = dict(world=0.32, key=4.0, key_angle=4.0, softbox=140.0, rim=1100.0, pilotfill=130.0,
             bounce=220.0)
LOOK = "AgX - High Contrast"


# ---------------------------------------------------------------- shot

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pct", type=int, default=25)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--anchors-only", action="store_true")
    ap.add_argument("--set", nargs="*", default=[], help="LIGHT overrides k=v")
    ap.add_argument("--fstop", type=float, default=16.0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("X0", "X1", "Y0", "Y1"))
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    for kv in a.set:
        k, v = kv.split("=")
        LIGHT[k] = float(v)

    t0 = time.time()
    rh.reset()
    rh.CROP = None
    sc = rh.setup_render(FIG_W, FIG_H, a.samples, preview=False)
    sc.render.resolution_percentage = a.pct
    sc.cycles.adaptive_threshold = 0.004 if a.pct == 100 else 0.02
    sc.view_settings.look = LOOK
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"

    if a.crop:
        sc.render.use_border, sc.render.use_crop_to_border = True, True
        (sc.render.border_min_x, sc.render.border_max_x,
         sc.render.border_min_y, sc.render.border_max_y) = a.crop
    rh.build_head = build_head
    craft = rh.build_craft(materials())
    tune_habit(craft)
    lights(LIGHT, craft)

    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.3, CATCHER_Z))
    bpy.context.object.is_shadow_catcher = True

    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.05, 200.0
    cd.lens = CAM["lens"]
    cam = rh.link(bpy.data.objects.new("cam", cd))
    cam.location = CAM["loc"]
    rh.look_at(cam, CAM["aim"])
    cd.dof.use_dof = a.fstop > 0
    cd.dof.aperture_fstop = max(a.fstop, 1.0)
    cd.dof.focus_distance = (Vector((0.2, 0.0, -0.1)) - cam.location).length
    sc.camera = cam
    bpy.context.view_layer.update()

    # anchors: the original compose_apparatus points; the cloth tip point follows the
    # (deeper) hero chord at the same chord fraction as the original (y = SWEEP at the tip)
    v_tip = 0.28
    anchors = rh.project(cam, {
        "tipR": tuple(surf(1, v_tip)),
        "tipL": tuple(surf(-1, v_tip)),
        "batten": tuple(surf(-0.5, 0.5) + Vector((0, 0, 0.01))),
        "hand": hand(1)[0],
        "foot": foot(1)[0],
        "head": HEAD[0],
        "tail": (0, 1.95, 0.0),
    })
    anchors["_size"] = [FIG_W, FIG_H]
    (WORK / "fig3_v2_points.json").write_text(json.dumps(anchors, indent=2))
    print("anchors", anchors)
    if a.anchors_only:
        return
    name = "fig3_v2_render" + (f"_p{a.pct}" if a.pct != 100 else "") + a.tag + ".png"
    sc.render.filepath = str(WORK / name)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {name} in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
