"""Figure 3 v3: the v2 render plus what the explanatory overlays need.

Shots (same scene, same materials and look as render_fig3_v2.py):
  main   the original camera; brighter, pilot-only fill so the figure under the wing reads
  inset  a low side view from the pilot's right, below the wing: hands lashed to the leading
         spar, feet tied to the trailing edge (the main camera cannot see them)
Both write projected 2D points for compose_fig3_v3.py: callout anchors, the ghost-tail outline
(a conventional tailplane on a boom where a tail would sit; drawn dashed, never rendered),
and the lift / weight / glide / wind arrows.

The pilot is built by one function, build_pilot(); pass --pilot path.{blend,obj,glb} to use an
external mesh instead (see import_pilot()).

  gtimeout 600 .venv-bpy/bin/python viz/hero/final/render_fig3_v3.py --shot main|inset|all \
      [--pct 25] [--samples 64] [--anchors-only]
Writes viz/hero/final/_work/fig3_v3_{main,inset}_render[_pPCT].png and fig3_v3_points.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy  # noqa: I001
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import render_hero as rh  # noqa: E402
import render_fig3_v2 as v2  # noqa: E402
from render_hero import HALF, HEAD, foot, hand, leg, le_spar, surf  # noqa: E402

WORK = HERE / "_work"
WORK.mkdir(exist_ok=True)
TAG = "fig3_v3"                      # output prefix (render_fig3_v4.py reuses this script)
POINTS = WORK / f"{TAG}_points.json"

MAIN_W, MAIN_H = 3600, 2400
INSET_W, INSET_H = 1600, 1100
INSET_CAM = dict(loc=(3.55, 0.10, -0.80), aim=(0.42, 0.46, -0.22), lens=44)

# ---------------------------------------------------------------- pilot (swappable)

_HERO_PILOT = rh.build_pilot
PILOT_SOURCE: Path | None = None
PILOT_OBJS: list = []


def import_pilot(path, root):
    """Bring in an external pilot (e.g. the MakeHuman monk) in craft coordinates.

    .blend: appends every object of the collection named 'pilot' (or all objects);
    .obj / .glb / .gltf: the usual importers. The mesh must already be posed and placed in
    the craft frame (x span, -y forward, z up; render_hero.HEAD / hand() / foot() joints).
    """
    path = Path(path)
    before = set(bpy.data.objects)
    if path.suffix == ".blend":
        with bpy.data.libraries.load(str(path)) as (src, dst):
            dst.collections = [c for c in src.collections if c == "pilot"]
            if not dst.collections:
                dst.objects = list(src.objects)
        obs = [o for c in dst.collections for o in c.all_objects] if dst.collections \
            else [o for o in dst.objects if o is not None]
        for o in obs:
            if o.name not in rh.COLL.objects:
                rh.COLL.objects.link(o)
    elif path.suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path), forward_axis="NEGATIVE_Y", up_axis="Z")
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    for o in set(bpy.data.objects) - before:
        if o.parent is None:
            o.parent = root


def build_pilot(M, root):
    """The single place the pilot is made: the hero pilot (v2 cowl) or an imported mesh."""
    before = set(bpy.data.objects)
    if PILOT_SOURCE:
        import_pilot(PILOT_SOURCE, root)
    else:
        rh.build_head = v2.build_head
        _HERO_PILOT(M, root)
    PILOT_OBJS[:] = [o for o in bpy.data.objects if o not in before]


rh.build_pilot = build_pilot


# ---------------------------------------------------------------- lights

def receivers(lamp, obs, name):
    coll = bpy.data.collections.new(name)
    for ob in obs:
        coll.objects.link(ob)
    lamp.light_linking.receiver_collection = coll


def lights(L, craft, shot):
    v2.lights(L, craft)
    pilot = [o for o in PILOT_OBJS if o.type in ("MESH", "CURVE")]
    # pilot-only lifts: they light the figure under the wing and nothing else
    f1 = rh.area("pilot_front", (1.8, -3.0, -0.2), (0.05, -0.1, -0.5), 1.4, L["pilot_front"],
                 (1.0, 0.94, 0.84))
    receivers(f1, pilot, "recv_pilot_front")
    f2 = rh.area("pilot_side", (-2.6, -1.0, -1.4), (0.0, 0.3, -0.5), 1.6, L["pilot_side"],
                 (0.92, 0.95, 1.0))
    receivers(f2, pilot, "recv_pilot_side")
    if shot == "inset":
        # camera-side fill for the low side view, and a cool kicker from aft-below
        rh.area("inset_fill", (3.2, -1.2, -1.6), (0.4, 0.5, -0.3), 2.0, L["inset_fill"],
                (1.0, 0.95, 0.88))
        rh.area("inset_kick", (1.0, 3.6, -1.8), (0.4, 0.6, -0.3), 1.6, L["inset_kick"],
                (0.88, 0.93, 1.0))


LIGHT = dict(v2.LIGHT, pilotfill=200.0, pilot_front=260.0, pilot_side=90.0,
             inset_fill=220.0, inset_kick=300.0)


# ---------------------------------------------------------------- overlay geometry (world)

def overlay_points():
    te0 = surf(0, 1.0)
    tl, tt, hs_le, hs_te, zt = 2.05, 2.42, 0.78, 0.68, te0.z + 0.02
    pts = {
        # ghost tail: boom from the trailing-edge centre, tapered tailplane, small fin
        "boom0": tuple(te0), "boom1": (0, tt + 0.04, zt),
        "tp_le_l": (-hs_le, tl, zt), "tp_le_r": (hs_le, tl, zt),
        "tp_te_r": (hs_te, tt, zt), "tp_te_l": (-hs_te, tt, zt),
        "fin0": (0, tl + 0.06, zt), "fin1": (0, tt, zt), "fin2": (0, tt + 0.02, zt + 0.42),
        "fin3": (0, tl + 0.22, zt + 0.42),
        "tail_c": (0.25, (tl + tt) / 2, zt),
        # lift at the wing's aerodynamic centre (root quarter chord), weight at the pilot's CG
        "lift0": tuple(surf(0, 0.25) + Vector((0, 0, 0.02))),
        "lift1": tuple(surf(0, 0.25) + Vector((0, 0, 1.05))),
        "cg": (0, 0.12, rh.ZC), "weight1": (0, 0.12, rh.ZC - 0.85),
        # intended glide: forward and gently down from the nose
        "glide0": (0, -0.80, rh.ZC + 0.02), "glide1": (0, -1.62, rh.ZC - 0.13),
    }
    # headwind: three short streamlines ahead of the left wing, blowing aft (+y)
    for i, (x, z) in enumerate(((-0.95, 0.30), (-1.30, 0.10), (-1.65, -0.10))):
        pts[f"wind{i}a"] = (x, -1.95, z)
        pts[f"wind{i}b"] = (x, -1.30, z)
    return pts


def anchors_main():
    return {
        "tipR": tuple(surf(1, 0.28)), "tipL": tuple(surf(-1, 0.28)),
        "batten": tuple(surf(-0.5, 0.5) + Vector((0, 0, 0.01))),
        "hand": hand(1)[0], "foot": foot(1)[0], "head": HEAD[0],
        "tail": (0, 1.95, 0.0),
        **overlay_points(),
    }


def anchors_inset():
    sx = Vector(leg(1)[1][1]).x / HALF                 # ankle station on the trailing edge
    return {
        "hand": tuple(le_spar(Vector(hand(1)[0]).x / HALF) + Vector((0, 0.0, -0.03))),
        "grip": hand(1)[0],
        "foot": tuple(surf(sx, 1.0) + Vector((0, -0.01, -0.01))),
        "footpt": foot(1)[0],
    }


# ---------------------------------------------------------------- shots

def camera(loc, aim, lens, fstop, focus):
    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.05, 200.0
    cd.lens = lens
    cam = rh.link(bpy.data.objects.new("cam", cd))
    cam.location = loc
    rh.look_at(cam, aim)
    cd.dof.use_dof = fstop > 0
    cd.dof.aperture_fstop = max(fstop, 1.0)
    cd.dof.focus_distance = (Vector(focus) - cam.location).length
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()
    return cam


def shot(name, a, store):
    t0 = time.time()
    rh.reset()
    rh.CROP = None
    w, h = (MAIN_W, MAIN_H) if name == "main" else (INSET_W, INSET_H)
    sc = rh.setup_render(w, h, a.samples, preview=False)
    sc.render.resolution_percentage = a.pct
    sc.cycles.adaptive_threshold = 0.004 if a.pct == 100 else 0.02
    sc.view_settings.look = v2.LOOK
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    craft = rh.build_craft(v2.materials())
    v2.tune_habit(craft)
    lights(LIGHT, craft, name)
    if name == "main":
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0.3, v2.CATCHER_Z))
        bpy.context.object.is_shadow_catcher = True
        cam = camera(v2.CAM["loc"], v2.CAM["aim"], v2.CAM["lens"], 16.0, (0.2, 0.0, -0.1))
        pts = anchors_main()
    else:
        c = INSET_CAM
        cam = camera(c["loc"], c["aim"], c["lens"], 8.0, c["aim"])
        pts = anchors_inset()
    proj = rh.project(cam, pts)
    proj["_size"] = [w, h]
    store[name] = proj
    if a.anchors_only:
        return
    out = WORK / (f"{TAG}_{name}_render" + (f"_p{a.pct}" if a.pct != 100 else "") + ".png")
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {out.name} in {time.time() - t0:.1f} s", flush=True)


def main(argv=None):
    global PILOT_SOURCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default="all", choices=["main", "inset", "all"])
    ap.add_argument("--pct", type=int, default=25)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--anchors-only", action="store_true")
    ap.add_argument("--pilot", type=Path, default=None)
    ap.add_argument("--set", nargs="*", default=[], help="LIGHT overrides k=v")
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_known_args(argv)[0]
    PILOT_SOURCE = a.pilot
    for kv in a.set:
        k, v = kv.split("=")
        LIGHT[k] = float(v)
    points = WORK / f"{TAG}_points.json"
    store = json.loads(points.read_text()) if points.exists() else {}
    for name in (["main", "inset"] if a.shot == "all" else [a.shot]):
        shot(name, a, store)
        points.write_text(json.dumps(store, indent=1))


if __name__ == "__main__":
    main()
