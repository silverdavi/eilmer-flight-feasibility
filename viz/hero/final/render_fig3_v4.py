"""Figure 3 v4: v3 (camera, inset, overlays, 7 m^2 wing) with the MakeHuman monk as the pilot.

The monk (viz/hero/assets/monk.py, cached monk.blend) is built in the craft frame against
render_hero.surf() / le_spar(), i.e. on this same 1.707 m-root-chord wing, so it is imported
with an identity transform; its own lashings reach the spar and the trailing edge. Anchors
that point at the pilot use the monk's recorded joints (its hands grip the spar at
|x| = 0.52 m, not the stick figure's 0.93 m).

monk.blend may be rebuilt by another job: each run copies it to _work/monk_snapshot.blend
first and records its mtime in the points file.

  gtimeout 900 .venv-bpy/bin/python viz/hero/final/render_fig3_v4.py --shot main|inset|all \
      [--pct 25] [--samples 64] [--anchors-only] [--set k=v ...] [--monk path.blend]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy  # noqa: F401,I001
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "assets"))
import render_fig3_v3 as v3  # noqa: E402
import monk  # noqa: E402

rh = v3.rh
SNAP = v3.WORK / "monk_snapshot.blend"
JOINTS: dict = {}

v3.TAG = "fig3_v4"
v3.LIGHT.update(pilot_front=60.0, pilot_side=170.0, pilotfill=110.0)


def build_pilot(M, root):
    """The single pilot hook: the cached MakeHuman monk, parented to the craft root."""
    before = set(bpy.data.objects)
    coll = monk.import_monk(root, path=SNAP)
    snap_dir, assets = str(SNAP.parent.resolve()), str(monk.ASSETS.resolve())
    for img in bpy.data.images:          # textures are relative to monk.blend, not the snapshot
        fp = bpy.path.abspath(img.filepath, library=img.library)
        if fp.startswith("//"):
            fp = assets + "/" + fp[2:]
        fp = str(Path(fp).resolve())
        if fp.startswith(snap_dir):
            fp = assets + fp[len(snap_dir):]
        if fp != img.filepath:
            img.filepath = fp
            img.reload()
        missing = img.source == "FILE" and not Path(bpy.path.abspath(img.filepath)).exists()
        if missing:
            print("MISSING TEXTURE", img.name, img.filepath, flush=True)
    tint_habit([o for o in coll.objects if o.name.startswith("monk_habit")])
    JOINTS.clear()
    JOINTS.update({k: Vector(v) for k, v in coll["joints"].items()})
    v3.PILOT_OBJS[:] = [o for o in bpy.data.objects if o not in before]


HABIT_TINT = (0.70, 0.66, 0.60, 1.0)     # toward v2's grey-brown oatmeal, apart from the linen


def tint_habit(obs):
    """Multiply the habit's base colour (render-side only; the asset is not modified)."""
    done = set()
    for ob in obs:
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            nt = m.node_tree
            for b in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
                sock = b.inputs["Base Color"]
                mix = nt.nodes.new("ShaderNodeMix")
                mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
                mix.inputs["Factor"].default_value = 1.0
                mix.inputs[7].default_value = HABIT_TINT
                if sock.is_linked:
                    nt.links.new(sock.links[0].from_socket, mix.inputs[6])
                else:
                    mix.inputs[6].default_value = sock.default_value
                nt.links.new(mix.outputs[2], sock)


rh.build_pilot = build_pilot
v3.INSET_CAM.update(aim=(0.38, 0.40, -0.26))
_overlay = v3.overlay_points


def tie_point(side):
    an = JOINTS[f"ankle.{side}"]
    sg = 1 if side == "L" else -1
    return tuple(rh.surf(sg * abs(an.x) / rh.HALF, 1.0) + Vector((0, -0.012, 0.0)))


def overlay_points():
    pts = _overlay()
    hc = JOINTS["head_c"]
    pts["glide0"] = (0, hc.y - 0.30, hc.z - 0.06)
    pts["glide1"] = (0, hc.y - 1.12, hc.z - 0.21)
    pelvis, chest = JOINTS["pelvis"], JOINTS["chest"]
    cg = pelvis.lerp(chest, 0.5)
    pts["cg"], pts["weight1"] = tuple(cg), tuple(cg + Vector((0, 0, -0.85)))
    return pts


def anchors_main():
    return {
        "tipR": tuple(rh.surf(1, 0.28)), "tipL": tuple(rh.surf(-1, 0.28)),
        "batten": tuple(rh.surf(-0.5, 0.5) + Vector((0, 0, 0.01))),
        "hand": tuple(JOINTS["grip.L"]), "foot": tuple(JOINTS["ankle.L"]),
        "head": tuple(JOINTS["head_c"]), "tail": (0, 1.95, 0.0),
        **overlay_points(),
    }


def anchors_inset():
    # the inset camera sits on +x: the monk's left side (MakeHuman .L is +x, prone, -y fwd)
    return {"hand": tuple(JOINTS["grip.L"]), "foot": tie_point("L"),
            "wrist": tuple(JOINTS["wrist.L"]), "ankle": tuple(JOINTS["ankle.L"])}


v3.overlay_points = overlay_points
v3.anchors_main = anchors_main
v3.anchors_inset = anchors_inset


def main(src=None, tag=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--monk", type=Path, default=src or HERE.parent / "assets" / "monk.blend")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    src = ap.parse_known_args(argv)[0].monk.resolve()
    if tag:
        v3.TAG = tag
    shutil.copy2(src, SNAP)
    print("monk asset", src, flush=True)
    v3.main([x for i, x in enumerate(argv) if x != "--monk" and (i == 0 or argv[i - 1] != "--monk")])
    pts = v3.WORK / f"{v3.TAG}_points.json"
    d = json.loads(pts.read_text())
    d["_monk_mtime"] = src.stat().st_mtime
    pts.write_text(json.dumps(d, indent=1))


if __name__ == "__main__":
    main()
