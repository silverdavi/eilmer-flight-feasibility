"""Render a 3D hero illustration of Eilmer's apparatus with Blender (bpy, Cycles).

Procedural, to scale from the model geometry: a tapered cambered membrane wing
(~5.3 m span, ~1.3 m mean chord), willow leading-edge spars and battens, and a
prone pilot gripping the spars with wings on the hands and feet. No tail.

Run with the dedicated render venv (Python 3.11):
  .venv-bpy/bin/python viz/render_blender.py
Writes viz/figures/apparatus_3d.png (transparent) and apparatus_points.json
(2D projected anchor points for compositing labels).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

HALF = 2.646          # half span (m)
CHORD_ROOT = 1.55
TAPER = 0.45          # tip chord = root * (1 - TAPER)
SWEEP = 0.55          # aft sweep at tip (m)
CAMBER = 0.10         # camber as fraction of local chord
DIHEDRAL = 0.16       # tip rise (m)
ROOT_X = 0.0          # wing root offset from centreline (welded at centre)


def mat(name, rgb, rough=0.7, sheen=0.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
    if transmission and "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = transmission
    return m


def wing():
    nu, nv = 26, 12
    bm = bmesh.new()
    grid = {}
    for iu in range(nu):
        u = iu / (nu - 1)
        chord = CHORD_ROOT * (1 - TAPER * u)
        xroot = ROOT_X + u * HALF
        for iv in range(nv):
            v = iv / (nv - 1)
            y = (v - 0.28) * chord + u * SWEEP
            z = CAMBER * chord * math.sin(math.pi * v) + DIHEDRAL * u ** 1.6
            grid[(iu, iv)] = bm.verts.new((xroot, y, z))
    bm.verts.ensure_lookup_table()
    for iu in range(nu - 1):
        for iv in range(nv - 1):
            bm.faces.new([grid[(iu, iv)], grid[(iu + 1, iv)],
                          grid[(iu + 1, iv + 1)], grid[(iu, iv + 1)]])
    me = bpy.data.meshes.new("wing")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Wing", me)
    bpy.context.collection.objects.link(ob)
    mir = ob.modifiers.new("mir", "MIRROR")
    mir.use_mirror_merge = True
    mir.merge_threshold = 0.06
    s = ob.modifiers.new("sub", "SUBSURF")
    s.levels = s.render_levels = 2
    sol = ob.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.012
    ob.data.materials.append(mat("cloth", (0.90, 0.83, 0.70), rough=0.82, sheen=0.45))
    return ob


def spar_curve(points, depth, material, name):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = depth
    cu.bevel_resolution = 3
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        sp.points[i].co = (x, y, z, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.modifiers.new("mir", "MIRROR")
    ob.data.materials.append(material)
    return ob


def willow():
    wood = mat("willow", (0.42, 0.30, 0.18), rough=0.6)
    # leading edge
    le = []
    for iu in range(20):
        u = iu / 19
        chord = CHORD_ROOT * (1 - TAPER * u)
        x = ROOT_X + u * HALF
        y = (0 - 0.28) * chord + u * SWEEP
        z = DIHEDRAL * u ** 1.6 + 0.02
        le.append((x, y, z))
    spar_curve(le, 0.022, wood, "spar_LE")
    # a couple of battens (ribs) at constant span stations
    for u in (0.18, 0.5, 0.82):
        chord = CHORD_ROOT * (1 - TAPER * u)
        x = ROOT_X + u * HALF
        pts = []
        for iv in range(8):
            v = iv / 7
            y = (v - 0.28) * chord + u * SWEEP
            z = CAMBER * chord * math.sin(math.pi * v) + DIHEDRAL * u ** 1.6 + 0.01
            pts.append((x, y, z))
        spar_curve(pts, 0.012, wood, f"batten_{u}")


def cyl_between(p1, p2, r, material, name):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length,
                                        location=(p1 + p2) / 2)
    ob = bpy.context.object
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    ob.name = name
    ob.data.materials.append(material)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def ball(loc, r, scale, material, name):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=32, ring_count=16)
    ob = bpy.context.object
    ob.scale = scale
    ob.name = name
    ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


def pilot():
    skin = mat("tunic", (0.46, 0.33, 0.25), rough=0.8)
    zc = -0.55                       # hang depth below the wing root
    # torso + hips, prone along -Y (head forward)
    ball((0, 0.02, zc), 0.16, (1.0, 2.6, 0.72), skin, "torso")
    ball((0, 0.42, zc - 0.01), 0.15, (1.0, 1.3, 0.8), skin, "hips")
    # neck + head forward
    cyl_between((0, -0.30, zc + 0.02), (0, -0.44, zc + 0.06), 0.05, skin, "neck")
    ball((0, -0.52, zc + 0.07), 0.105, (1.0, 1.15, 1.05), skin, "head")
    # arms up-out to grip the spar (~0.9 m out; the frame continues to the tip)
    for s in (1, -1):
        cyl_between((s * 0.13, -0.16, zc + 0.02), (s * 0.5, -0.15, -0.16), 0.04, skin, f"arm{s}")
        cyl_between((s * 0.5, -0.15, -0.16), (s * 0.9, -0.08, 0.0), 0.03, skin, f"fore{s}")
        ball((s * 0.93, -0.06, 0.01), 0.05, (1, 1, 1), skin, f"hand{s}")
    # legs aft to the foot wings, with feet
    for s in (1, -1):
        cyl_between((s * 0.11, 0.5, zc), (s * 0.16, 0.95, zc + 0.03), 0.05, skin, f"thigh{s}")
        cyl_between((s * 0.16, 0.95, zc + 0.03), (s * 0.2, 1.35, zc + 0.05), 0.036, skin, f"shin{s}")
        ball((s * 0.21, 1.42, zc + 0.04), 0.06, (1, 1.5, 0.7), skin, f"foot{s}")
    return skin


def lights_world():
    w = bpy.context.scene.world
    if w is None:
        w = bpy.data.worlds.new("World")
        bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.86, 0.87, 0.9, 1)
    bg.inputs["Strength"].default_value = 0.5

    sun = bpy.data.lights.new("key", "SUN")
    sun.energy = 3.2
    sun.angle = math.radians(3)
    so = bpy.data.objects.new("key", sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), math.radians(8), math.radians(40))

    area = bpy.data.lights.new("fill", "AREA")
    area.energy = 220
    area.size = 6
    ao = bpy.data.objects.new("fill", area)
    bpy.context.collection.objects.link(ao)
    ao.location = (-4, -5, 3)
    ao.rotation_euler = (math.radians(60), 0, math.radians(-35))


def camera():
    target = bpy.data.objects.new("aim", None)
    bpy.context.collection.objects.link(target)
    target.location = (0, 0.3, -0.15)
    bpy.ops.object.camera_add(location=(3.6, -7.4, 5.0))
    cam = bpy.context.object
    cam.data.lens = 62
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    bpy.context.scene.camera = cam
    return cam


def project_points(cam, names_pts):
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    out = {}
    for name, p in names_pts.items():
        co = world_to_camera_view(scene, cam, Vector(p))
        out[name] = [round(co.x * rx, 1), round((1 - co.y) * ry, 1)]
    return out


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 160
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.film_transparent = True
    sc.render.resolution_x = 1800
    sc.render.resolution_y = 1200
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"

    wing()
    willow()
    pilot()
    lights_world()
    cam = camera()

    # soft contact shadow on transparent film
    bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0.3, -1.45))
    bpy.context.object.is_shadow_catcher = True

    bpy.context.view_layer.update()      # evaluate the camera track constraint
    anchors = project_points(cam, {
        "tipR": (HALF, SWEEP, DIHEDRAL),
        "tipL": (-HALF, SWEEP, DIHEDRAL),
        "batten": (-1.3, 0.54, 0.17),
        "hand": (0.93, -0.06, 0.01),
        "foot": (0.21, 1.42, -0.51),
        "head": (0, -0.52, -0.48),
        "tail": (0, 1.95, 0.0),
    })
    (OUT / "apparatus_points.json").write_text(json.dumps(anchors, indent=2))

    sc.render.filepath = str(OUT / "apparatus_3d.png")
    bpy.ops.render.render(write_still=True)
    print("rendered apparatus_3d.png", anchors)


if __name__ == "__main__":
    main()
