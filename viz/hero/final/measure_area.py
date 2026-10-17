"""Planform area of the wing meshes: render_blender.py (original Fig. 3) vs the hero geometry.

  .venv-bpy/bin/python viz/hero/final/measure_area.py
"""
import sys
from pathlib import Path

import bpy  # noqa: F401

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))
import render_blender as rb  # noqa: E402


def planform(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    tot = 0.0
    for p in me.polygons:
        vs = [me.vertices[i].co for i in p.vertices]
        a = sum(vs[i].x * vs[(i + 1) % len(vs)].y - vs[(i + 1) % len(vs)].x * vs[i].y
                for i in range(len(vs)))
        tot += abs(a) / 2
    xs = [v.co.x for v in me.vertices]
    return tot, max(xs) - min(xs)


bpy.ops.wm.read_factory_settings(use_empty=True)
w = rb.wing()
w.modifiers["sol"].show_viewport = False        # single sheet: count the planform once
bpy.context.view_layer.update()
a_eval, span_eval = planform(w)
for m in list(w.modifiers):
    m.show_viewport = m.name == "mir"
bpy.context.view_layer.update()
a_cage, span_cage = planform(w)
analytic = 2 * rb.HALF * rb.CHORD_ROOT * (1 - rb.TAPER / 2)
print(f"ORIGINAL cage (mirror only): {a_cage:.3f} m2, span {span_cage:.3f} m")
print(f"ORIGINAL rendered (mirror+subsurf): {a_eval:.3f} m2, span {span_eval:.3f} m")
print(f"ORIGINAL analytic trapezoid: {analytic:.3f} m2")

import render_hero as rh  # noqa: E402
rh.reset()
M = rh.materials()
rh.build_craft(M)
print(f"HERO chord_root {rh.CHORD_ROOT_HERO:.4f} m: planform {rh.WING_STATS['planform_m2']:.3f} m2, "
      f"surface {rh.WING_STATS['surface_m2']:.3f} m2, span {rh.WING_STATS['span']:.3f} m, "
      f"AR {rh.WING_STATS['span']**2 / rh.WING_STATS['planform_m2']:.3f}")
