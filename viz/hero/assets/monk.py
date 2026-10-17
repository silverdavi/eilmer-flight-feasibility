"""Eilmer the monk: a MakeHuman body (MPFB2, CC0 assets) posed on the craft, in a
cloth-simulated undyed wool habit with cowl, rope cincture, sandals and leather lashings.

Everything is built in the *craft frame* of viz/hero/render_hero.py (x to starboard, -y
forward/flight direction, z up; wing root at the origin, pilot hang depth ZC = -0.55 m),
so the result drops onto `render_hero.build_craft()` with an identity transform.

Posture (see POSE below): prone, belly down, shoulders and head on the model joints of
render_hero.py (shoulders y=-0.16, z~-0.53; head ahead and raised), legs straight aft at
the hang depth, feet plantar-flexed with the ankles at the trailing edge, both hands
gripping the leading-edge spar. The model's stick figure has 0.96 m arms and a 0.66 m
shoulder-hip segment; a real 1.80 m body has ~0.61 m shoulder-to-palm and ~0.48 m, so the
hands grip the spar where a real arm reaches (|x| = 0.52 m against the stick figure's 0.93 m,
arms nearly straight) and
the hips/feet sit ~0.18 m further forward than the stick figure's.

Variant "prone" (VARIANTS, --variant prone -> monk_prone.blend): the body raised to ~0.33 m
below the root (back ~0.2 m under the sail), so the arms spread out along the spar
(|x| = 0.71 m) instead of reaching straight up, legs rising gently to the trailing-edge ties;
the habit cut slimmer and simulated in flight airflow from ahead and below (gravity weight
0.5), so it lies along the body with the hem, sleeves and rope ends streaming aft.

Build once (slow: cloth simulation) and cache to monk.blend:

    .venv-bpy/bin/python viz/hero/assets/monk.py            # writes viz/hero/assets/monk.blend
    .venv-bpy/bin/python viz/hero/assets/monk.py -- --variant prone --frames 60 \
        --out viz/hero/assets/monk_prone.blend
    .venv-bpy/bin/python viz/hero/assets/monk.py --preview  # + a close-up test render

Use from another bpy script (e.g. render_hero.py), after the craft root exists:

    sys.path.insert(0, "viz/hero/assets"); import monk
    rh.build_pilot = lambda M, root: None        # drop the mannequin pilot
    craft = rh.build_craft(M)
    monk.import_monk(craft)                     # appends the 'monk' collection, parents to craft
    monk.import_monk(craft, path=monk.ASSETS / "monk_prone.blend")   # the prone variant

The monk objects carry their own materials (skin, wool, leather, rope).
"""
from __future__ import annotations

import argparse
import importlib
import math
import os
import random
import sys
import time
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
DL = ASSETS / "_dl"
MH = DL / "mh"
TEX = DL / "tex"
BLEND = ASSETS / "monk.blend"
os.environ.setdefault("BLENDER_USER_RESOURCES", str(ASSETS / "_blender_user"))

import bpy  # noqa: E402,I001
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

sys.path.insert(0, str(ASSETS.parent))
sys.path.insert(0, str(ASSETS.parent.parent))
import render_hero as rh  # noqa: E402

ZC = rh.ZC

# Target joints in the craft frame (from render_hero.py's pilot, see module docstring).
POSE = dict(
    shoulders=Vector((0.0, -0.16, ZC + 0.02)),   # midpoint of the two shoulder joints
    hips_z=ZC - 0.01,                           # hip joints at the model's hip height
    thigh=Vector((0.05, 0.45, 0.03)),           # model hip->knee direction (per side, x signed)
    shin=Vector((0.04, 0.40, 0.02)),            # model knee->ankle direction
    look_down_deg=28.0,                         # gaze below the horizon
    reach=0.985,                                # wrist distance / straight-arm length
)
SKIRT_R = (0.13, 0.03)          # skirt tube radius at the hips, and its growth to the hem
WIND_DIR = Vector((0, 1, 0))    # relative airflow in the craft frame (toward the tail)
GRAVITY_W = 1.0                 # cloth gravity weight
WIND_S = 18000.0                # wind field strength
ROPE_STREAM = (0.7, 1.0)        # belt-end aft sweep and drop, per unit rope length

# "prone": the body raised close under the wing (back ~0.25 m below the sail), so the arms
# spread out along the spar instead of hanging straight up; legs rise gently to the trailing
# edge; the habit is cut slimmer and simulated in flight airflow (from ahead and below, at a
# glide angle of attack), which presses it to the belly and streams the hem and sleeves aft.
VARIANTS = dict(
    prone=dict(
        POSE=dict(shoulders=Vector((0.0, -0.17, ZC + 0.21)), hips_z=ZC + 0.19,
                  thigh=Vector((0.05, 0.45, 0.04)), shin=Vector((0.04, 0.40, 0.06)),
                  look_down_deg=20.0),
        SKIRT_R=(0.112, 0.012),
        WIND_DIR=Vector((0, 1, 0.42)).normalized(),
        GRAVITY_W=0.5,
        WIND_S=30000.0,
        ROPE_STREAM=(1.35, 0.38),
    ),
)


def use_variant(name):
    g = globals()
    for k, v in VARIANTS[name].items():
        if isinstance(v, dict):
            g[k].update(v)
        else:
            g[k] = v


# ---------------------------------------------------------------- MPFB plumbing

def _mpfb():
    import addon_utils
    if not any(m.endswith("mpfb.services.humanservice") for m in sys.modules):
        addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)

    def dyn(p, k):
        for a in list(sys.modules):
            if a.endswith(p):
                return getattr(importlib.import_module(a), k)
        raise ImportError(p)
    return dyn("mpfb.services.humanservice", "HumanService"), \
        dyn("mpfb.services.targetservice", "TargetService")


def link(ob, coll):
    coll.objects.link(ob)
    return ob


def make_body(coll):
    """MakeHuman young adult male, lean; eyes, eyebrows, eyelashes; rig 'default'."""
    HS, TS = _mpfb()
    md = TS.get_default_macro_info_dict()
    md.update(gender=1.0, age=0.5, muscle=0.55, weight=0.42, height=0.55, proportions=0.6)
    md["race"] = {"asian": 0.0, "caucasian": 1.0, "african": 0.0}
    body = HS.create_human(macro_detail_dict=md)
    tdir = Path(TS.target_full_path("nose-scale-vert-incr") or "").parent.parent
    # an individual (not the average) face: longer straight nose, firmer jaw, hollower cheeks
    for t, w in (("nose/nose-scale-vert-incr", 0.35), ("nose/nose-hump-incr", 0.25),
                 ("chin/chin-prominent-incr", 0.3), ("cheek/l-cheek-inner-incr", -0.3),
                 ("cheek/r-cheek-inner-incr", -0.3), ("eyebrows/eyebrows-trans-down", 0.3),
                 ("head/head-age-incr", 0.25)):
        p = tdir / (t + ".target.gz")
        if p.exists():
            TS.load_target(body, str(p), weight=w)
    rig = HS.add_builtin_rig(body, "default")
    extras = []
    for f, kind in ((MH / "eyes/high-poly/high-poly.mhclo", "Eyes"),
                    (MH / "eyebrows/eyebrow007/eyebrow007.mhclo", "Eyebrows"),
                    (MH / "eyelashes/eyelashes02/eyelashes02.mhclo", "Eyelashes")):
        if f.exists():
            extras.append((kind, HS.add_mhclo_asset(str(f), body, asset_type=kind,
                                                    subdiv_levels=0, material_type="MAKESKIN")))
    for ob in [body, rig] + [e for _, e in extras]:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    return body, rig, dict(extras)


def bake_keys(body):
    if body.data.shape_keys:
        body.shape_key_add(name="__mix", from_mix=True)
        kb = body.data.shape_keys.key_blocks
        mix = [list(v.co) for v in kb["__mix"].data]
        body.shape_key_clear()
        for v, c in zip(body.data.vertices, mix):
            v.co = c


def strip_helpers(body):
    """Delete the MakeHuman helper geometry (keep vertex group 'body')."""
    gi = body.vertex_groups["body"].index
    bm = bmesh.new()
    bm.from_mesh(body.data)
    dl = bm.verts.layers.deform.active
    kill = [v for v in bm.verts if gi not in v[dl]]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    for m in list(body.modifiers):
        if m.type == "MASK":
            body.modifiers.remove(m)


# ---------------------------------------------------------------- posing

def _upd():
    bpy.context.view_layer.update()


def _world(rig, v):
    return rig.matrix_world @ v


def _arm_dir(rig, d):
    return (rig.matrix_world.to_3x3().inverted() @ Vector(d)).normalized()


def head_w(rig, name):
    return rig.matrix_world @ rig.pose.bones[name].head


def tail_w(rig, name):
    return rig.matrix_world @ rig.pose.bones[name].tail


def aim(rig, name, target_dir_world):
    """Rotate pose bone (about its head) so its Y axis points along a world direction."""
    pb = rig.pose.bones[name]
    _upd()
    M = pb.matrix.copy()
    cur = M.col[1].xyz.normalized()
    q = cur.rotation_difference(_arm_dir(rig, target_dir_world))
    h = M.translation.copy()
    pb.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ M
    _upd()


def aim_at(rig, name, p_world):
    aim(rig, name, Vector(p_world) - head_w(rig, name))


def rot(rig, name, axis_world, ang):
    pb = rig.pose.bones[name]
    _upd()
    M = pb.matrix.copy()
    h = M.translation.copy()
    R = Matrix.Rotation(ang, 4, _arm_dir(rig, axis_world))
    pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    _upd()


def ydir(rig, name):
    return (tail_w(rig, name) - head_w(rig, name)).normalized()


def place_rig(rig):
    """Rigid placement: prone, head toward -y, shoulders on the model shoulder joint."""
    bones = rig.data.bones
    sh = (bones["upperarm01.L"].head_local + bones["upperarm01.R"].head_local) / 2
    hp = (bones["upperleg01.L"].head_local + bones["upperleg01.R"].head_local) / 2
    L = (sh - hp).length
    S = POSE["shoulders"]
    dz = S.z - POSE["hips_z"]
    H = Vector((0, S.y + math.sqrt(L * L - dz * dz), POSE["hips_z"]))
    up_t = (S - H).normalized()                        # body axis (hips -> shoulders), world
    down_t = up_t.cross(Vector((1, 0, 0))).normalized()  # belly direction
    if down_t.z > 0:
        down_t = -down_t
    up_r = (sh - hp).normalized()
    fwd_r = Vector((0, -1, 0))                         # belly direction at rest
    fwd_r = (fwd_r - up_r * fwd_r.dot(up_r)).normalized()
    Rr = Matrix((up_r.cross(fwd_r), up_r, fwd_r)).transposed()   # columns: right, up, front
    Rt = Matrix((up_t.cross(down_t), up_t, down_t)).transposed()
    R = Rt @ Rr.inverted()
    rig.matrix_world = Matrix.Translation(S - R @ sh) @ R.to_4x4()
    _upd()
    return H


def two_bone(S, W, L1, L2, pole):
    d = W - S
    dist = min(d.length, (L1 + L2) * 0.9995)
    u = d.normalized()
    a = (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)
    a = max(-1.0, min(1.0, a))
    v = (pole - u * pole.dot(u)).normalized()
    return S + L1 * (a * u + math.sqrt(1 - a * a) * v)


def spar_point(s):
    return rh.le_spar(s)


def grip_point(S, reach):
    """Point on the leading spar at distance `reach` from the shoulder joint S (same side)."""
    sgn = 1 if S.x > 0 else -1
    lo, hi = 0.0, 1.0
    if (spar_point(sgn * 0.0) - S).length > reach:
        # unreachable even at the centreline: nearest spar point
        return min((spar_point(sgn * i / 200) for i in range(201)), key=lambda p: (p - S).length)
    for _ in range(50):
        m = (lo + hi) / 2
        if (spar_point(sgn * m) - S).length < reach:
            lo = m
        else:
            hi = m
    return spar_point(sgn * lo)


GRIP = {}


def pose_rig(rig):
    pb = rig.pose.bones
    for p in pb:
        p.rotation_mode = "QUATERNION"
    place_rig(rig)
    X = Vector((1, 0, 0))

    # head: extend the neck so the face looks forward and a little down
    face0 = Vector((0, 0, -1))
    want = Vector((0, -math.cos(math.radians(POSE["look_down_deg"])),
                   -math.sin(math.radians(POSE["look_down_deg"]))))
    total = face0.angle(want)
    for n, f in (("spine01", 0.12), ("neck01", 0.2), ("neck02", 0.3), ("neck03", 0.22),
                 ("head", 0.16)):
        rot(rig, n, X, -total * f)

    for side, sgn in (("L", 1), ("R", -1)):
        # legs: model directions, slight spread, feet plantar-flexed (toes aft, soles up)
        th = Vector((sgn * POSE["thigh"].x, POSE["thigh"].y, POSE["thigh"].z)).normalized()
        sh_ = Vector((sgn * POSE["shin"].x, POSE["shin"].y, POSE["shin"].z)).normalized()
        for n in (f"upperleg01.{side}", f"upperleg02.{side}"):
            aim(rig, n, th)
        for n in (f"lowerleg01.{side}", f"lowerleg02.{side}"):
            aim(rig, n, sh_)
        aim(rig, f"foot.{side}", (sh_ + Vector((0, 0, -0.35))).normalized())

        # shoulder girdle raised and drawn forward, as when reaching overhead
        rot(rig, f"clavicle.{side}", Vector((0, 1, 0)), -sgn * math.radians(16))
        rot(rig, f"shoulder01.{side}", Vector((0, 1, 0)), -sgn * math.radians(10))
        S = head_w(rig, f"upperarm01.{side}")
        E0 = head_w(rig, f"lowerarm01.{side}")
        W0 = head_w(rig, f"wrist.{side}")
        L1, L2 = (E0 - S).length, (W0 - E0).length
        hand_len = 0.085                       # wrist joint -> centre of the grip
        palm_off = 0.040                       # spar axis -> wrist line (palm + spar radius)
        reach = (L1 + L2) * POSE["reach"] + hand_len
        G = grip_point(S, reach)
        # wrist on the line from the grip toward the shoulder, a palm's depth below/behind
        to_s = (S - G).normalized()
        W = G + to_s * hand_len
        W += Vector((0, 0.3, -1)).normalized() * 0.0          # (kept: exact grip on the spar)
        E = two_bone(S, W, L1, L2, Vector((sgn * 1.0, 0.5, -0.6)))
        for n in (f"upperarm01.{side}", f"upperarm02.{side}"):
            aim_at(rig, n, E)
        for n in (f"lowerarm01.{side}", f"lowerarm02.{side}"):
            aim_at(rig, n, W)
        hd = (G - head_w(rig, f"wrist.{side}")).normalized()
        aim(rig, f"wrist.{side}", hd)
        GRIP[side] = dict(grip=G, wrist=head_w(rig, f"wrist.{side}"), elbow=E, shoulder=S)
    _upd()


def curl_fingers(rig, body):
    """Wrap the fingers round the spar: palm toward the spar axis, fingers curled over it."""
    for side, sgn in (("L", 1), ("R", -1)):
        G = GRIP[side]["grip"]
        wr = head_w(rig, f"wrist.{side}")
        hd = (G - wr).normalized()
        # palm normal from the mesh: mean normal of palm skin vertices (weighted to metacarpals)
        n = palm_normal(rig, body, side)
        sax = (spar_point(sgn * min(abs(G.x) / rh.HALF + 0.01, 1)) -
               spar_point(sgn * max(abs(G.x) / rh.HALF - 0.01, 0))).normalized()
        want = sax.cross(hd).normalized()
        # the palm should face forward-up, i.e. toward the side of the spar facing the body
        if want.dot(Vector((0, -0.4, 1))) < 0:
            want = -want
        n_p = (n - hd * n.dot(hd)).normalized()
        w_p = (want - hd * want.dot(hd)).normalized()
        ang = n_p.angle(w_p)
        if n_p.cross(w_p).dot(hd) < 0:
            ang = -ang
        rot(rig, f"wrist.{side}", hd, ang)
        n = palm_normal(rig, body, side)
        for f in range(2, 6):
            for j, a in ((1, 62), (2, 74), (3, 48)):
                b = f"finger{f}-{j}.{side}"
                d = ydir(rig, b)
                rot(rig, b, d.cross(n).normalized(), math.radians(a))
        for j, a in ((1, 25), (2, 30), (3, 35)):
            b = f"finger1-{j}.{side}"
            d = ydir(rig, b)
            rot(rig, b, d.cross(n).normalized(), math.radians(a))


def palm_normal(rig, body, side):
    _upd()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(deps)
    me = ev.to_mesh()
    vg = {g.name: g.index for g in body.vertex_groups}
    ids = {vg.get(f"metacarpal{i}.{side}") for i in (2, 3, 4)} - {None}
    acc = Vector()
    wr = head_w(rig, f"wrist.{side}")
    mc = head_w(rig, f"finger3-1.{side}")
    mid = (wr + mc) / 2
    pts = []
    for v, vo in zip(me.vertices, body.data.vertices):
        if any(g.group in ids and g.weight > 0.5 for g in vo.groups):
            pts.append((body.matrix_world @ v.co, body.matrix_world.to_3x3() @ v.normal))
    # palm vs back of the hand: the side the thumb tip curls toward
    th = tail_w(rig, f"finger1-3.{side}")
    for p, nn in pts:
        acc += nn if nn.dot(th - mid) > 0 else Vector()
    ev.to_mesh_clear()
    if acc.length < 1e-6:
        return Vector((0, 0, 1))
    return acc.normalized()


JOINTS = {}


def record_joints(rig):
    J = JOINTS
    for side in ("L", "R"):
        J[f"shoulder.{side}"] = head_w(rig, f"upperarm01.{side}")
        J[f"elbow.{side}"] = head_w(rig, f"lowerarm01.{side}")
        J[f"wrist.{side}"] = head_w(rig, f"wrist.{side}")
        J[f"hip.{side}"] = head_w(rig, f"upperleg01.{side}")
        J[f"knee.{side}"] = head_w(rig, f"lowerleg01.{side}")
        J[f"ankle.{side}"] = head_w(rig, f"foot.{side}")
        J[f"ball.{side}"] = tail_w(rig, f"foot.{side}")
        J[f"toe.{side}"] = tail_w(rig, f"toe3-3.{side}")
        J[f"eye.{side}"] = head_w(rig, f"eye.{side}")
        J[f"grip.{side}"] = GRIP[side]["grip"]
    J["neck"] = head_w(rig, "neck01")
    J["head0"] = head_w(rig, "head")
    J["crown"] = tail_w(rig, "head")
    J["pelvis"] = head_w(rig, "spine05")
    J["chest"] = head_w(rig, "spine01")
    up = (J["crown"] - J["head0"]).normalized()
    eyes = (J["eye.L"] + J["eye.R"]) / 2
    J["head_c"] = J["head0"] + up * 0.075
    f = eyes - J["head_c"]
    J["face"] = (f - up * f.dot(up)).normalized()
    J["head_up"] = up
    J["axis"] = (J["chest"] - J["pelvis"]).normalized()     # body axis toward the head


def apply_rig(objs, rig):
    for ob in objs:
        bpy.context.view_layer.objects.active = ob
        for m in list(ob.modifiers):
            if m.type == "ARMATURE":
                with bpy.context.temp_override(object=ob, active_object=ob):
                    bpy.ops.object.modifier_apply(modifier=m.name)
        mw = ob.matrix_world.copy()
        ob.parent = None
        ob.data.transform(mw)
        ob.matrix_world = Matrix.Identity(4)


# ---------------------------------------------------------------- materials

def _nd(nt, kind, **kw):
    return rh.nd(nt, kind, **kw)


def _img(nt, path, non_color=False, proj=None):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    if proj:
        n.projection = proj
        n.projection_blend = 0.25
    return n


def mat_skin():
    m, nt, bsdf, out = rh.new_mat("monk_skin")
    tex = _img(nt, MH / "skins/young_caucasian_male/young_lightskinned_male_diffuse.png")
    uv = _nd(nt, "ShaderNodeUVMap")
    rh.ln(nt, uv.outputs[0], tex.inputs[0])
    # weathered outdoor complexion: warm the pale texture, add blotchy redness
    hsv = _nd(nt, "ShaderNodeHueSaturation", Hue=0.5, Saturation=0.92, Value=0.80)
    rh.ln(nt, tex.outputs[0], hsv.inputs["Color"])
    tc = _nd(nt, "ShaderNodeTexCoord")
    blot = _nd(nt, "ShaderNodeTexNoise", Scale=45.0, Detail=6.0)
    rh.ln(nt, tc.outputs["Object"], blot.inputs["Vector"])
    red = rh.ramp(nt, blot.outputs["Fac"], [(0.4, (1.0, 1.0, 1.0)), (0.75, (1.05, 0.88, 0.84))])
    mix = _nd(nt, "ShaderNodeMix", _data_type="RGBA", _blend_type="MULTIPLY", Factor=1.0)
    rh.ln(nt, hsv.outputs[0], mix.inputs[6])
    rh.ln(nt, red.outputs[0], mix.inputs[7])
    rh.ln(nt, mix.outputs[2], bsdf.inputs["Base Color"])
    rh.ln(nt, mix.outputs[2], bsdf.inputs["Subsurface Radius"]) if False else None
    pores = _nd(nt, "ShaderNodeTexVoronoi", Scale=1400.0)
    rh.ln(nt, tc.outputs["Object"], pores.inputs["Vector"])
    fine = _nd(nt, "ShaderNodeTexNoise", Scale=300.0, Detail=8.0)
    rh.ln(nt, tc.outputs["Object"], fine.inputs["Vector"])
    b1 = rh.bump(nt, pores.outputs["Distance"], 0.12, 0.0004)
    b2 = rh.bump(nt, fine.outputs["Fac"], 0.08, 0.0008, b1.outputs[0])
    rh.ln(nt, b2.outputs[0], bsdf.inputs["Normal"])
    rough = rh.ramp(nt, fine.outputs["Fac"], [(0.3, (0.42, 0.42, 0.42)), (0.7, (0.58, 0.58, 0.58))])
    rh.ln(nt, rough.outputs[0], bsdf.inputs["Roughness"])
    rh.set_in(bsdf, Subsurface_Weight=1.0, Subsurface_Scale=0.006, Specular_IOR_Level=0.45,
              Coat_Weight=0.05, Coat_Roughness=0.3)
    bsdf.subsurface_method = "RANDOM_WALK_SKIN"
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.22)
    return m


def mat_eyes():
    m, nt, bsdf, out = rh.new_mat("monk_eyes")
    tex = _img(nt, MH / "eyes/materials/brown_eye.png")
    rh.ln(nt, tex.outputs[0], bsdf.inputs["Base Color"])
    rh.set_in(bsdf, Roughness=0.05, Coat_Weight=1.0, Coat_Roughness=0.02, Subsurface_Weight=0.2,
              Subsurface_Scale=0.002)
    return m


def mat_hair(name, png):
    m, nt, bsdf, out = rh.new_mat(name)
    tex = _img(nt, png)
    rgb = _nd(nt, "ShaderNodeRGB")
    rgb.outputs[0].default_value = (0.035, 0.022, 0.013, 1)
    rh.ln(nt, rgb.outputs[0], bsdf.inputs["Base Color"])
    rh.ln(nt, tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    rh.set_in(bsdf, Roughness=0.55)
    return m


def mat_wool():
    """Undyed fulled wool (oatmeal grey-brown): PH 'caban' maps (CC0) box-projected for the
    fibre/felted texture, recoloured; strong sheen for the fuzz rim; cavity AO in folds."""
    m, nt, bsdf, out = rh.new_mat("monk_wool")
    tc = _nd(nt, "ShaderNodeTexCoord")
    mp = _nd(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (4.0, 4.0, 4.0)      # 0.25 m texture tile
    rh.ln(nt, tc.outputs["Object"], mp.inputs["Vector"])
    dif = _img(nt, TEX / "caban_diff_4k.jpg", proj="BOX")
    nor = _img(nt, TEX / "caban_nor_gl_4k.jpg", non_color=True, proj="BOX")
    rgh = _img(nt, TEX / "caban_rough_4k.jpg", non_color=True, proj="BOX")
    for n in (dif, nor, rgh):
        rh.ln(nt, mp.outputs[0], n.inputs[0])
    bw = _nd(nt, "ShaderNodeRGBToBW")
    rh.ln(nt, dif.outputs[0], bw.inputs[0])
    big = _nd(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=4.0)
    rh.ln(nt, tc.outputs["Object"], big.inputs["Vector"])
    # fleece of mixed grey/brown sheep, hand-spun: luminance from the scan, hue from a ramp
    lum = _nd(nt, "ShaderNodeMath", _operation="MULTIPLY_ADD")
    rh.ln(nt, bw.outputs[0], lum.inputs[0])
    lum.inputs[1].default_value, lum.inputs[2].default_value = 1.6, 0.0
    lum2 = _nd(nt, "ShaderNodeMix", _data_type="FLOAT", Factor=0.35)
    rh.ln(nt, lum.outputs[0], lum2.inputs[2])
    rh.ln(nt, big.outputs["Fac"], lum2.inputs[3])
    col = rh.ramp(nt, lum2.outputs[0], [(0.15, (0.095, 0.066, 0.043)), (0.45, (0.235, 0.172, 0.112)),
                                         (0.8, (0.36, 0.28, 0.19))])
    rh.ln(nt, rh.ao(nt, col.outputs[0], 0.05), bsdf.inputs["Base Color"])
    nm = _nd(nt, "ShaderNodeNormalMap", Strength=0.6)
    rh.ln(nt, nor.outputs[0], nm.inputs["Color"])
    fz = _nd(nt, "ShaderNodeTexNoise", Scale=900.0, Detail=3.0)
    rh.ln(nt, tc.outputs["Object"], fz.inputs["Vector"])
    b = rh.bump(nt, fz.outputs["Fac"], 0.15, 0.0006, nm.outputs[0])
    rh.ln(nt, b.outputs[0], bsdf.inputs["Normal"])
    rr = _nd(nt, "ShaderNodeMapRange", **{"To Min": 0.78, "To Max": 0.98})
    rh.ln(nt, rgh.outputs[0], rr.inputs["Value"])
    rh.ln(nt, rr.outputs[0], bsdf.inputs["Roughness"])
    rh.set_in(bsdf, Sheen_Weight=0.9, Sheen_Roughness=0.35, Specular_IOR_Level=0.2,
              Subsurface_Weight=0.08, Subsurface_Scale=0.004)
    bsdf.inputs["Sheen Tint"].default_value = (0.85, 0.78, 0.68, 1)
    return m


def mat_rope():
    m, nt, bsdf, out = rh.new_mat("monk_rope")
    tc = _nd(nt, "ShaderNodeTexCoord")
    nz = _nd(nt, "ShaderNodeTexNoise", Scale=400.0, Detail=6.0)
    rh.ln(nt, tc.outputs["Object"], nz.inputs["Vector"])
    col = rh.ramp(nt, nz.outputs["Fac"], [(0.3, (0.16, 0.12, 0.07)), (0.7, (0.30, 0.24, 0.15))])
    rh.ln(nt, rh.ao(nt, col.outputs[0], 0.01), bsdf.inputs["Base Color"])
    b = rh.bump(nt, nz.outputs["Fac"], 0.4, 0.0008)
    rh.ln(nt, b.outputs[0], bsdf.inputs["Normal"])
    rh.set_in(bsdf, Roughness=0.9, Sheen_Weight=0.5, Sheen_Roughness=0.4)
    return m


def monk_materials():
    M = {"skin": mat_skin(), "eyes": mat_eyes(), "wool": mat_wool(), "rope": mat_rope(),
         "leather": rh.mat_leather()}
    for m in M.values():
        m.use_fake_user = True          # MPFB purges orphan data while building the body
    return M


def set_mat(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.material_index = 0


# ---------------------------------------------------------------- build

def build_body(coll, M):
    body, rig, extras = make_body(coll)
    pose_rig(rig)
    curl_fingers(rig, body)
    record_joints(rig)
    objs = [body] + list(extras.values())
    for ob in objs:
        bake_keys(ob)
    apply_rig(objs, rig)
    bpy.data.objects.remove(rig)
    strip_helpers(body)
    body.name = "monk_body"
    set_mat(body, M["skin"])
    for kind, ob in extras.items():
        ob.name = f"monk_{kind.lower()}"
        if kind == "Eyes":
            set_mat(ob, M["eyes"])
        else:
            png = next((MH / kind.lower()).glob("*/*.png"))
            name = ob.name.split("_")[1]
            pngs = list((MH / kind.lower()).glob(f"*{'007' if kind == 'Eyebrows' else '02'}/*.png"))
            set_mat(ob, mat_hair(f"monk_{name}", pngs[0] if pngs else png))
    for ob in objs:
        for p in ob.data.polygons:
            p.use_smooth = True
        sub = ob.modifiers.new("sub", "SUBSURF")
        sub.levels, sub.render_levels = 1, 2 if ob is body else 1
    return body, extras


def new_collection(name="monk"):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


# ---------------------------------------------------------------- the habit

def _cone(bm, p1, p2, r1, r2, seg=32):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    M = Matrix.Translation((p1 + p2) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2,
                          depth=d.length, matrix=M)
    rh.add_sphere(bm, p1, r1, seg=seg, rings=12)
    rh.add_sphere(bm, p2, r2, seg=seg, rings=12)


def _mesh(name, bm, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me), coll)


def _apply_all(ob):
    with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
        for m in list(ob.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)


def _remesh(ob, voxel, smooth=0):
    rm = ob.modifiers.new("rm", "REMESH")
    rm.mode, rm.voxel_size, rm.use_smooth_shade = "VOXEL", voxel, True
    if smooth:
        sm = ob.modifiers.new("sm", "SMOOTH")
        sm.factor, sm.iterations = 0.9, smooth
    _apply_all(ob)


HOOD_OPEN_DEG = 40.0


def habit_volume(body, coll):
    """Closed garment volume around the posed body, then cut open at face, cuffs and hem."""
    J = JOINTS
    # 1) the body, blobbed (fingers/toes fused) and offset outward
    shell = body.copy()
    shell.data = body.data.copy()
    shell.modifiers.clear()
    link(shell, coll)
    _remesh(shell, 0.02, smooth=4)
    dp = shell.modifiers.new("off", "DISPLACE")
    dp.direction, dp.mid_level, dp.strength = "NORMAL", 0.0, 1.0
    dp.strength = 0.022
    _apply_all(shell)
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    # 2) wide sleeves (cone from shoulder to wrist, widening)
    for s in ("L", "R"):
        sh, el, wr = J[f"shoulder.{s}"], J[f"elbow.{s}"], J[f"wrist.{s}"]
        _cone(bm, sh, el, 0.085, 0.085)
        _cone(bm, el, wr + (wr - el).normalized() * 0.02, 0.085, 0.12)
    # 3) skirt: one tube round both legs, hips to mid-calf, and the loose body of the tunic
    hipc = (J["hip.L"] + J["hip.R"]) / 2
    for t in [i / 10 for i in range(11)]:
        a = J["hip.L"].lerp(J["knee.L"].lerp(J["ankle.L"], 0.75), t)
        b = J["hip.R"].lerp(J["knee.R"].lerp(J["ankle.R"], 0.75), t)
        r = SKIRT_R[0] + SKIRT_R[1] * t
        _cone(bm, a, b, r, r, seg=24)
    _cone(bm, J["chest"], hipc, 0.17, 0.17)
    # 4) cowl: roomy round the head, drawn out to a point behind the crown
    hc, up, fc = J["head_c"], J["head_up"], J["face"]
    rh.add_sphere(bm, hc - fc * 0.02, 0.15, (1, 1, 1), seg=40, rings=20)
    _cone(bm, hc, hc + fc * 0.085 + up * 0.02, 0.145, 0.13)          # deep brim
    _cone(bm, hc - fc * 0.04, hc - fc * 0.10 + up * 0.07, 0.13, 0.07)
    _cone(bm, J["neck"], hc, 0.11, 0.12)
    shell.data.clear_geometry()
    bm.to_mesh(shell.data)
    bm.free()
    _remesh(shell, 0.013, smooth=6)
    _remesh(shell, 0.013)
    # 5) openings
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    kill = set()
    hem_y = {s: J[f"knee.{s}"].lerp(J[f"ankle.{s}"], 0.62).y for s in "LR"}
    for f in bm.faces:
        c = f.calc_center_median()
        for s in ("L", "R"):
            el, wr = J[f"elbow.{s}"], J[f"wrist.{s}"]
            d = (wr - el).normalized()
            if (c - wr).dot(d) > -0.035 and (c - el).dot(d) > 0:
                kill.add(f)
        if c.y > min(hem_y.values()):
            kill.add(f)
        v = c - hc
        if v.length < 0.30 and v.dot(fc) > 0.09 and \
                v.normalized().dot(fc) > math.cos(math.radians(HOOD_OPEN_DEG)):
            kill.add(f)
    bmesh.ops.delete(bm, geom=list(kill), context="FACES")
    # drop small islands left by the cuts
    bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, isl = [v], []
        seen.add(v)
        while stack:
            u = stack.pop()
            isl.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        islands.append(isl)
    islands.sort(key=len)
    for isl in islands[:-1]:
        bmesh.ops.delete(bm, geom=isl, context="VERTS")
    smooth_boundary(bm, 25)
    bm.to_mesh(shell.data)
    bm.free()
    shell.name = "monk_habit"
    return shell


def smooth_boundary(bm, it):
    """Even out the voxel-stepped edges of the openings (cuffs, hem, face) before simulating."""
    bnd = [v for v in bm.verts if v.is_boundary]
    for _ in range(it):
        new = {}
        for v in bnd:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                new[v] = v.co * 0.4 + (nb[0].co + nb[1].co) * 0.3
        for v, c in new.items():
            v.co = c
    # relax the ring just inside the edge so it follows
    inner = {e.other_vert(v) for v in bnd for e in v.link_edges if not e.other_vert(v).is_boundary}
    for _ in range(4):
        for v in inner:
            nb = [e.other_vert(v) for e in v.link_edges]
            v.co = v.co * 0.5 + sum((u.co for u in nb), Vector()) / len(nb) * 0.5


def body_bvh(body):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(deps)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(body.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    ev.to_mesh_clear()
    return t


BELT_T = 0.40     # belt position along pelvis(0) -> chest(1)


def simulate_habit(habit, body, coll, frames=60, wind=None, quality=10):
    J = JOINTS
    wind = WIND_S if wind is None else wind
    belt_c = J["pelvis"].lerp(J["chest"], BELT_T)
    ax = J["axis"]
    bvh = body_bvh(body)
    pin = habit.vertex_groups.new(name="pin")
    me = habit.data
    ids = []
    for v in me.vertices:
        p = habit.matrix_world @ v.co
        dd = (p - belt_c).dot(ax)
        if abs(dd) < 0.03:
            loc, nrm, idx, dist = bvh.find_nearest(p)
            if loc is not None and dist < 0.2:
                v.co = habit.matrix_world.inverted() @ (loc + (p - loc).normalized() * 0.012)
            ids.append(v.index)
    pin.add(ids, 1.0, "REPLACE")
    # crown of the cowl held lightly on the head (it is pulled forward over the brow)
    soft = []
    for v in me.vertices:
        p = habit.matrix_world @ v.co
        q = p - J["head_c"]
        if q.length < 0.2 and q.normalized().dot(J["head_up"]) > 0.75:
            soft.append(v.index)
    pin.add(soft, 0.35, "REPLACE")

    col = body.modifiers.new("collision", "COLLISION")
    body.collision.thickness_outer = 0.006
    body.collision.thickness_inner = 0.02
    body.collision.cloth_friction = 8.0
    cl = habit.modifiers.new("cloth", "CLOTH")
    cs = cl.settings
    cs.quality = quality
    cs.mass = 0.3
    cs.air_damping = 1.0
    cs.tension_stiffness = cs.compression_stiffness = 25.0
    cs.shear_stiffness = 12.0
    cs.bending_stiffness = 7.0          # heavy fulled wool: big soft folds, no crepe
    cs.tension_damping = cs.compression_damping = 5.0
    cs.vertex_group_mass = "pin"
    cs.pin_stiffness = 2.0
    cc = cl.collision_settings
    cc.use_collision = True
    cc.distance_min = 0.004
    cc.collision_quality = 4
    cc.use_self_collision = True
    cc.self_distance_min = 0.003
    cc.self_friction = 5.0
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    cl.point_cache.frame_start, cl.point_cache.frame_end = 1, frames
    w = bpy.data.objects.new("airflow", None)
    link(w, coll)
    cs.effector_weights.gravity = GRAVITY_W
    w.location = J["head_c"] - WIND_DIR * 1.0
    w.rotation_euler = WIND_DIR.to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.objects.active = w
    with bpy.context.temp_override(object=w, active_object=w):
        bpy.ops.object.forcefield_toggle()
    w.field.type = "WIND"
    w.field.strength = wind
    w.field.flow = 0.6
    w.field.noise = 0.6
    w.field.seed = 3
    t = time.time()
    for f in range(1, frames + 1):
        sc.frame_set(f)
    print(f"cloth: {frames} frames in {time.time() - t:.0f}s")
    with bpy.context.temp_override(object=habit, active_object=habit):
        bpy.ops.object.modifier_apply(modifier=cl.name)
    body.modifiers.remove(body.modifiers["collision"])
    bpy.data.objects.remove(w)
    # take out the sub-centimetre crumple of the solver, keep the drape and folds
    sm = habit.modifiers.new("relax", "CORRECTIVE_SMOOTH")
    sm.factor, sm.iterations, sm.smooth_type = 0.4, 3, "SIMPLE"
    sm.use_only_smooth = True
    sm.rest_source = "ORCO"
    _apply_all(habit)
    sc.frame_set(1)


# ---------------------------------------------------------------- belt, sandals, lashings

def section_loop(ob, point, normal, near=None, radius=0.4):
    """Ordered points of the mesh/plane intersection loop nearest `near` (default: point)."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(deps)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(ob.matrix_world)
    point, normal = Vector(point), Vector(normal).normalized()
    near = Vector(near) if near is not None else point
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co - point).length > radius],
                     context="VERTS")
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                 plane_co=point, plane_no=normal)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    adj = {}
    for e in cut:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    loops, seen = [], set()
    for v0 in adj:
        if v0 in seen:
            continue
        loop, prev, cur = [v0], None, v0
        seen.add(v0)
        while True:
            nxt = [w for w in adj[cur] if w is not prev and w not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        loops.append([v.co.copy() for v in loop])
    bm.free()
    loops = [lp for lp in loops if len(lp) > 8]
    if not loops:
        return []
    return min(loops, key=lambda lp: (sum(lp, Vector()) / len(lp) - near).length)


def resample(pts, step, cyclic=True):
    P = pts + ([pts[0]] if cyclic else [])
    seg = [(P[i + 1] - P[i]).length for i in range(len(P) - 1)]
    L = sum(seg)
    n = max(8, int(L / step))
    out, i, acc = [], 0, 0.0
    for k in range(n + (0 if cyclic else 1)):
        t = L * k / n
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = (t - acc) / seg[i] if seg[i] > 0 else 0
        out.append(P[i].lerp(P[i + 1], min(max(f, 0), 1)))
    return out


def smooth_pts(pts, it=3, cyclic=True):
    for _ in range(it):
        n = len(pts)
        pts = [pts[i] if (not cyclic and i in (0, n - 1)) else
               (pts[i - 1] + pts[i] * 2 + pts[(i + 1) % n]) / 4 for i in range(n)]
    return pts


def curve(name, pts, radius, mat, coll, cyclic=False, res=3, flat=None):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution = radius, res
    cu.use_fill_caps = not cyclic
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1)
    sp.use_cyclic_u = cyclic
    ob = link(bpy.data.objects.new(name, cu), coll)
    cu.materials.append(mat)
    if flat:
        ob_scale_profile(cu, flat)
    return ob


def ob_scale_profile(cu, k):
    for sp in cu.splines:
        for p in sp.points:
            p.radius = 1.0
    cu.bevel_mode = "ROUND"
    cu.offset = 0
    cu.extrude = 0
    cu.bevel_depth *= 1.0
    cu.twist_mode = "MINIMUM"


def rope_strands(path, radius, pitch, cyclic, axis_hint):
    """Three-ply laid rope along a polyline: three helical strands."""
    n = len(path)
    strands = [[], [], []]
    s_acc = 0.0
    for i in range(n):
        a = path[i - 1] if (cyclic or i > 0) else path[i]
        b = path[(i + 1) % n] if (cyclic or i < n - 1) else path[i]
        t = (b - a).normalized()
        if i > 0:
            s_acc += (path[i] - path[i - 1]).length
        h = axis_hint(path[i]) if callable(axis_hint) else Vector(axis_hint)
        nn = (h - t * h.dot(t)).normalized()
        bb = t.cross(nn)
        for k in range(3):
            th = 2 * math.pi * (s_acc / pitch + k / 3)
            strands[k].append(path[i] + radius * (math.cos(th) * nn + math.sin(th) * bb))
    return strands


def add_belt(habit, M, coll):
    J = JOINTS
    belt_c = J["pelvis"].lerp(J["chest"], BELT_T)
    loop = section_loop(habit, belt_c, J["axis"], radius=0.35)
    if not loop:
        return
    c = sum(loop, Vector()) / len(loop)
    loop = [p + (p - c).normalized() * 0.010 for p in loop]
    path = smooth_pts(resample(loop, 0.006), 6)
    strands = rope_strands(path, 0.0045, 0.03, True, lambda p: p - c)
    for k, st in enumerate(strands):
        curve(f"monk_belt{k}", st, 0.0052, M["rope"], coll, cyclic=True, res=2)
    # knot at the left hip, ends hanging down and streaming aft
    side = max(path, key=lambda p: p.x)
    rng = random.Random(5)
    bm = bmesh.new()
    for k in range(4):
        rh.add_sphere(bm, side + Vector((rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012),
                                         rng.uniform(-0.015, 0.005))) + Vector((0.008, 0, -0.01)),
                      0.016, seg=16, rings=8)
    kn = _mesh("monk_knot", bm, coll)
    kn.data.materials.append(M["rope"])
    for p in kn.data.polygons:
        p.use_smooth = True
    for e, (dx, L) in enumerate(((0.0, 0.52), (0.025, 0.42))):
        pts = []
        for i in range(40):
            t = i / 39
            a, dr = ROPE_STREAM
            pts.append(side + Vector((0.02 + dx + 0.03 * math.sin(4 * t + e),
                                      0.10 * t + a * L * t * t,
                                      -0.03 - dr * L * (t - 0.35 * t * t))))
        for k, st in enumerate(rope_strands(pts, 0.0042, 0.03, False, Vector((1, 0, 0)))):
            curve(f"monk_rope_end{e}{k}", st, 0.0048, M["rope"], coll, res=2)
        rh.add_sphere(bm := bmesh.new(), pts[-1], 0.012, (1, 1, 1.4), seg=12, rings=8)
        o = _mesh(f"monk_rope_tuft{e}", bm, coll)
        o.data.materials.append(M["rope"])


def _foot_frame(s):
    J = JOINTS
    fd = (J[f"toe.{s}"] - J[f"ankle.{s}"]).normalized()
    sole = Vector((0, 0, 1))
    sole = (sole - fd * sole.dot(fd)).normalized()
    return fd, sole


def add_sandals(body, M, coll):
    """Carbatina-type sandal: a leather sole moulded to the (upturned) sole, two straps."""
    J = JOINTS
    deps = bpy.context.evaluated_depsgraph_get()
    me = body.data
    for s in ("L", "R"):
        fd, sole = _foot_frame(s)
        an, toe = J[f"ankle.{s}"], J[f"toe.{s}"]
        flen = (toe - an).length
        bm = bmesh.new()
        bm.from_mesh(me)
        keep = set()
        for f in bm.faces:
            c = f.calc_center_median()
            u = (c - an).dot(fd)
            if -0.075 < u < flen + 0.02 and f.normal.dot(sole) > 0.35 and \
                    (c - an).dot(sole) > -0.02 and abs((c - an).x) < 0.09:
                keep.add(f)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context="FACES")
        if not bm.faces:
            bm.free()
            continue
        for v in bm.verts:
            v.co += v.normal * 0.0015
        o = _mesh(f"monk_sole.{s}", bm, coll)
        so = o.modifiers.new("t", "SOLIDIFY")
        so.thickness, so.offset = 0.009, 1.0
        sm = o.modifiers.new("sub", "SUBSURF")
        sm.levels = sm.render_levels = 1
        o.data.materials.append(M["leather"])
        for p in o.data.polygons:
            p.use_smooth = True
        for k, (u, r) in enumerate(((0.62, 0.006), (0.35, 0.006), (-0.01, 0.005))):
            p = an + fd * (u * flen)
            nrm = fd if k < 2 else (J[f"ankle.{s}"] - J[f"knee.{s}"]).normalized()
            lp = section_loop(body, p, nrm, radius=0.12)
            if lp:
                c = sum(lp, Vector()) / len(lp)
                lp = smooth_pts(resample([q + (q - c).normalized() * 0.003 for q in lp], 0.004), 4)
                curve(f"monk_strap.{s}{k}", lp, r, M["leather"], coll, cyclic=True, res=1)


def add_lashings(body, M, coll):
    """Leather cuffs on wrists and ankles; thongs round the spar and up to the trailing edge."""
    J = JOINTS
    for s, sg in (("L", 1), ("R", -1)):
        el, wr = J[f"elbow.{s}"], J[f"wrist.{s}"]
        d = (wr - el).normalized()
        lp = section_loop(body, wr - d * 0.03, d, radius=0.1)
        if lp:
            c = sum(lp, Vector()) / len(lp)
            for k in range(3):
                q = [p + (p - c).normalized() * (0.004) + d * (0.008 * k) for p in lp]
                curve(f"monk_cuff.{s}{k}", smooth_pts(resample(q, 0.004), 4), 0.0045,
                      M["leather"], coll, cyclic=True, res=1)
        G = J[f"grip.{s}"]
        u = abs(G.x) / rh.HALF
        sax = (rh.le_spar(sg * min(u + 0.01, 1)) - rh.le_spar(sg * max(u - 0.01, 0))).normalized()
        for off in (-0.055, 0.06):
            c0 = rh.le_spar(sg * (u + sg * 0 + off / rh.HALF * sg)) if False else \
                rh.le_spar(sg * max(0.0, u + off / rh.HALF))
            curve(f"monk_wrap.{s}{off}", rh.helix(c0, sax, 0.026, 0.045, 5), 0.0034,
                  M["leather"], coll, res=1)
            if lp:
                top = c + (c0 - c).normalized() * 0.03
                mid = top.lerp(c0, 0.5) + Vector((0, 0.004, 0))
                curve(f"monk_thong.{s}{off}", [top, mid, c0 + Vector((0, 0.01, -0.024))], 0.0032,
                      M["leather"], coll, res=1)
        # ankle
        kn, an = J[f"knee.{s}"], J[f"ankle.{s}"]
        d = (an - kn).normalized()
        lp = section_loop(body, an - d * 0.045, d, radius=0.1)
        if not lp:
            continue
        c = sum(lp, Vector()) / len(lp)
        for k in range(2):
            q = [p + (p - c).normalized() * 0.004 + d * (0.01 * k) for p in lp]
            curve(f"monk_anklecuff.{s}{k}", smooth_pts(resample(q, 0.004), 4), 0.005,
                  M["leather"], coll, cyclic=True, res=1)
        tp = rh.surf(sg * abs(an.x) / rh.HALF, 1.0)
        bm = bmesh.new()
        rh.add_sphere(bm, tp + Vector((0, -0.012, 0)), 0.03, (1.0, 1.0, 0.25))
        o = _mesh(f"monk_tab.{s}", bm, coll)
        o.data.materials.append(M["leather"])
        top = max(lp, key=lambda p: p.z)
        for dx in (-0.012, 0.012):
            p0 = top + Vector((dx, 0, 0.004))
            p1 = tp + Vector((dx, -0.012, -0.006))
            curve(f"monk_tie.{s}{dx}", [p0, p0.lerp(p1, 0.5) + Vector((0, -0.006, 0)), p1],
                  0.0035, M["leather"], coll, res=1)


# ---------------------------------------------------------------- top level

def build_monk(frames=50, coll_name="monk"):
    """Build the monk into collection `coll_name` of the current scene, craft frame."""
    coll = new_collection(coll_name)
    M = monk_materials()
    t = time.time()
    body, extras = build_body(coll, M)
    habit = habit_volume(body, coll)
    if frames:
        simulate_habit(habit, body, coll, frames=frames)
    set_mat(habit, M["wool"])
    for p in habit.data.polygons:
        p.use_smooth = True
    so = habit.modifiers.new("thickness", "SOLIDIFY")
    so.thickness, so.offset = 0.004, 1.0
    sub = habit.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1
    add_belt(habit, M, coll)
    add_sandals(body, M, coll)
    add_lashings(body, M, coll)
    for ob in coll.objects:
        ob["eilmer_monk"] = True
    coll["joints"] = {k: list(v) for k, v in JOINTS.items()}
    print(f"monk built in {time.time() - t:.0f}s: {len(coll.objects)} objects")
    return coll


def save_monk(path=BLEND, frames=50):
    rh.reset()
    coll = build_monk(frames)
    for m in bpy.data.materials:
        m.use_fake_user = False
    for ob in list(bpy.context.scene.collection.objects):
        bpy.context.scene.collection.objects.unlink(ob)        # craft-less file: monk only
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    print("saved", path)


def import_monk(parent=None, path=BLEND, coll_name="monk"):
    """Append the cached monk (craft frame) into the current scene; optionally parent all
    its objects to `parent` (e.g. the craft root empty from render_hero.build_craft), so it
    follows the craft's location/rotation. Returns the collection."""
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == coll_name]
    coll = dst.collections[0]
    bpy.context.scene.collection.children.link(coll)
    if parent is not None:
        for ob in coll.objects:
            if ob.parent is None:
                ob.parent = parent
                ob.matrix_parent_inverse = Matrix.Identity(4)
    return coll


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=50)
    ap.add_argument("--out", default=str(BLEND))
    ap.add_argument("--variant", choices=sorted(VARIANTS), default=None)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if a.variant:
        use_variant(a.variant)
    save_monk(Path(a.out), a.frames)


if __name__ == "__main__":
    main()
