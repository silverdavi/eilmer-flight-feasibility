"""Cover candidates for EJP: Eilmer of Malmesbury gliding from the abbey tower.

Every pixel is a Cycles path-traced render of 3D geometry (no generated imagery). The
craft is render_hero.build_craft() (span 5.29 m, area 7.0 m^2, AR 4, no tail), unchanged;
the pilot is the MakeHuman monk from viz/hero/assets/monk.blend (see assets/monk.py).
Landscape: scene/landscape.py; tower and nave: scene/tower.py. Sky: Poly Haven HDRIs (CC0).

  .venv-bpy/bin/python viz/hero/scene/render_scene.py --shot A|B|C|all [--preview] [--samples N]

A  launch: evening, Eilmer 10 m off the tower top, seen from the air ahead of the tower
B  backlit: an onlooker on the brow looks up at the glowing linen, the tower below
C  wide: misty morning, high behind the tower, Eilmer over the slope, the Avon valley

Portrait 2480 x 3508 (A4 at 300 dpi); the top ~35% is kept calm for the masthead.
Outputs: viz/hero/scene/cover_<shot>[_preview].png
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "assets"))

import monk  # noqa: E402  (imports bpy, render_hero)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import landscape as ls  # noqa: E402
import tower as tw  # noqa: E402

rh = monk.rh
HDRI = HERE.parent / "assets" / "_dl" / "hdri"
W, H = 2480, 3508

# HDRI sun (from the 1k maps): equirect u, elevation (deg)
SKIES = {
    "kloppenheim_06": dict(file="kloppenheim_06_puresky", u=0.613, elev=4.7),
    "kloofendal_38d": dict(file="kloofendal_38d_partly_cloudy_puresky", u=0.600, elev=37.8),
    "belfast": dict(file="belfast_sunset_puresky", u=0.605, elev=1.9),
    "syferfontein_18d": dict(file="syferfontein_18d_clear_puresky", u=0.600, elev=18.5),
    "kloofendal_43d": dict(file="kloofendal_43d_clear_puresky", u=0.600, elev=43.1),
}


def hdri_az(u):
    # Blender equirect: u = 0.5 - atan2(y, x) / 2pi
    phi = 2 * math.pi * (0.5 - u)
    d = (math.cos(phi), math.sin(phi))
    return math.degrees(math.atan2(d[0], d[1])) % 360


def compass(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


def world_sky(sky, sun_az, strength=1.0, res="8k", clamp=60.0):
    S = SKIES[sky]
    path = HDRI / f"{S['file']}_{res}.hdr"
    if not path.exists():
        path = HDRI / f"{S['file']}_8k.hdr"
    w = bpy.data.worlds.new("sky")
    bpy.context.scene.world = w
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(sun_az - hdri_az(S["u"])))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(path), check_existing=True)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    cl = nt.nodes.new("ShaderNodeVectorMath")
    cl.operation = "MINIMUM"
    cl.inputs[1].default_value = (clamp, clamp, clamp)
    nt.links.new(env.outputs[0], cl.inputs[0])
    nt.links.new(cl.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    return S["elev"]


def add_sun(az, el, energy, color, angle=0.53):
    L = bpy.data.lights.new("sun", "SUN")
    L.energy, L.color, L.angle = energy, color, math.radians(angle)
    ob = bpy.data.objects.new("sun", L)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (-compass(az, el)).to_track_quat("-Z", "Y").to_euler()
    return ob


def volume_box(name, centre, size, density, color=(1, 1, 1), anis=0.55, mist=None):
    import bmesh
    from mathutils import Matrix
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(centre) @
                          Matrix.Diagonal((*size, 1)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    v = nt.nodes.new("ShaderNodeVolumePrincipled")
    v.inputs["Color"].default_value = (*color, 1)
    v.inputs["Anisotropy"].default_value = anis
    if mist is None:
        v.inputs["Density"].default_value = density
    else:
        # ground mist: exponential with height above z0, broken up by noise
        z0, hscale, nscale = mist
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        sub = nt.nodes.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        nt.links.new(sep.outputs["Z"], sub.inputs[0])
        sub.inputs[1].default_value = z0            # vertices are in world space
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(sub.outputs[0], mul.inputs[0])
        mul.inputs[1].default_value = -1.0 / hscale
        ex = nt.nodes.new("ShaderNodeMath")
        ex.operation = "EXPONENT"
        nt.links.new(mul.outputs[0], ex.inputs[0])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.0 / nscale
        nz.inputs["Detail"].default_value = 3.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.35, 0.7
        nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.operation = "MULTIPLY"
        nt.links.new(ex.outputs[0], m1.inputs[0])
        nt.links.new(mr.outputs[0], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath")
        m2.operation = "MULTIPLY"
        nt.links.new(m1.outputs[0], m2.inputs[0])
        m2.inputs[1].default_value = density
        nt.links.new(m2.outputs[0], v.inputs["Density"])
    nt.links.new(v.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    me.materials.append(m)
    ob.visible_shadow = True
    return ob


# ---------------------------------------------------------------- shots

Z0 = None   # tower base (plateau height at the tower)


def roof_z():
    return Z0 + tw.ROOF


SHOTS = {
    # A: standing on the tower roof just behind the parapet, a little to the north,
    # Eilmer 4-5 m out over the edge, wing just above the coping, valley and river beyond
    "A": dict(sky="kloppenheim_06", sun_az=250.0, sun_el=8.0, sun_e=3.4, sky_k=1.0,
              craft=dict(s=10.5, d=0.8, dz=-0.9, pitch=5.0, roll=-6.0, yaw=8.0),
              cam=dict(s=19.0, d=-6.0, dz=-3.9), aim=dict(s=9.0, d=0.2, dz=-1.0), lens=32,
              shift=0.08, fstop=8.0, focus="craft", exposure=0.0, haze=0.00035, mist=0.012),
    # A2: as A, with the prone monk (monk_prone.blend), post-built Saxon halls, the tower's
    # weathered top courses and string course, a WNW midsummer-evening sun banked onto the
    # upper surface so the linen glows, a little more haze toward the valley
    "A2": dict(sky="kloppenheim_06", sun_az=292.0, sun_el=11.0, sun_e=9.0, sky_k=1.0,
               craft=dict(s=10.5, d=0.8, dz=-0.9, pitch=5.0, roll=24.0, yaw=-25.0),
               bank_sun=True, monk="monk_prone.blend", town="saxon", tower_top=True,
               cam=dict(s=19.0, d=-6.0, dz=-3.9), aim=dict(s=9.0, d=0.2, dz=-1.0), lens=35,
               shift=0.08, fstop=8.0, focus="craft", exposure=-0.25, haze=0.0005, mist=0.015),
    # A3: as A2, the camera closer in and a little higher: Eilmer larger in the frame
    "A3": dict(sky="kloppenheim_06", sun_az=292.0, sun_el=11.0, sun_e=9.0, sky_k=1.0,
               craft=dict(s=10.5, d=0.8, dz=-0.9, pitch=5.0, roll=24.0, yaw=-25.0),
               bank_sun=True, monk="monk_prone.blend", town="saxon", tower_top=True,
               cam=dict(s=16.0, d=-4.2, dz=-3.0), aim=dict(s=8.2, d=1.1, dz=-1.0), lens=35,
               frame_y=0.60, fstop=8.0, focus="craft", exposure=-0.25, haze=0.0005, mist=0.015),
    # B: from below and ahead of the craft, on the line to a high sun behind it, so the sun
    # sits just behind the trailing edge and the linen glows; early morning, sun in the NE
    # sun_e / clamp / sun_col measured from the 8k map: the HDRI sun is clamped to the sky
    # around it and the removed 12.3 W/m^2 is returned as the sun lamp
    "B": dict(sky="syferfontein_18d", sun_az=72.0, sun_el=18.5, sun_e=12.3, clamp=5.2,
              sun_col=(1.0, 0.866, 0.535), sky_k=1.0,
              craft=dict(s=48.0, d=0.0, dz=8.0, pitch=7.0, roll=5.0, yaw=-12.0),
              cam=None, cam_dist=13.0, cam_el=31.0, cam_daz=-10.0, lens=35, shift=0.07,
              aim_off=(0.0, -2.0), clear_near=170.0, fstop=5.6,
              focus="craft", exposure=-0.6, haze=0.00025, mist=0.0),
    # C: wide, high above and behind the tower, looking SW down the line of flight on a misty
    # summer morning: tower top and town below, Eilmer out over the slope with his shadow
    # on it, the Avon valley fading into mist and haze (calm top)
    "C": dict(sky="syferfontein_18d", sun_az=80.0, sun_el=18.5, sun_e=12.3, clamp=5.2,
              sun_col=(1.0, 0.866, 0.535), sky_k=1.0,
              craft=dict(s=36.0, d=1.0, dz=14.0, pitch=6.0, roll=-5.0, yaw=0.0),
              cam=dict(s=-14.0, d=13.0, dz=15.0), aim_mix=0.42, lens=28, frame_y=0.56,
              fstop=11.0, focus="craft", exposure=-0.7, haze=0.0005, mist=0.02,
              mist_h=6.0),
}


def place_craft(root, c):
    s, d = c["s"], c["d"]
    x, y = ls.xy(s, d)
    z = roof_z() + c["dz"] if s < 20 else ls.height(x, y) + c["dz"]
    if "abs_z" in c:
        z = c["abs_z"]
    root.location = (x, y, z)
    psi = math.atan2(ls.A.x, -ls.A.y) + math.radians(c.get("yaw", 0.0))
    root.rotation_euler = (math.radians(c["pitch"]), math.radians(c["roll"]), psi)


def clear_sightlines(pts, cam, targets, width=18.0, clear=22.0, near=35.0):
    """Drop trees that would stand in front of the camera: anything within `near` of it, and
    anything inside a `width` corridor whose top (ground + `clear`) reaches the sight line."""
    out = []
    c = Vector(cam)
    segs = [(c, Vector(t)) for t in targets]
    for p in pts:
        q = Vector((p[0], p[1], 0.0))
        if (Vector((c.x, c.y, 0)) - q).length < near:
            continue
        keep = True
        for a, b in segs:
            ab = Vector((b.x - a.x, b.y - a.y, 0))
            L2 = ab.length_squared
            t = max(0.0, min(1.0, (q - Vector((a.x, a.y, 0))).dot(ab) / L2)) if L2 else 0.0
            foot = Vector((a.x, a.y, 0)) + ab * t
            if (q - foot).length < width and a.z + (b.z - a.z) * t < p[2] + clear:
                keep = False
                break
        if keep:
            out.append(p)
    return out


def build_world(shot, preview):
    global Z0
    C = SHOTS[shot]
    rh.reset()
    sc = bpy.context.scene
    coll = sc.collection
    rh.COLL = coll
    Z0 = ls.height(0, 0)
    t = time.time()
    ls.build_terrain(coll, nr=380 if preview else 560, na=720 if preview else 1080)
    ls.build_rivers(coll)
    print(f"terrain {time.time() - t:.0f}s")
    tw.build_tower(coll, Z0, top_detail=C.get("tower_top", False))
    tw.build_nave(coll, Z0)
    # the craft, unchanged, and the monk
    rh.build_pilot = lambda M, root: None
    craft = rh.build_craft(rh.materials())
    monk.import_monk(parent=craft, path=HERE.parent / "assets" / C.get("monk", "monk.blend"))
    place_craft(craft, C["craft"])
    cam, tgt = setup_camera(C, craft, shot)
    if C.get("bank_sun"):
        # bank toward the sun so it lights the upper surface: seen from below, the linen
        # glows by transmission (the underside itself stays out of the direct sun)
        sd_ = compass(C["sun_az"], C["sun_el"])
        best = None
        for rs_ in (-1, 1):
            c1 = dict(C["craft"], roll=rs_ * abs(C["craft"]["roll"]))
            place_craft(craft, c1)
            bpy.context.view_layer.update()
            up = craft.matrix_world.to_3x3() @ Vector((0, 0, 1))
            if best is None or up.dot(sd_) > best[0]:
                best = (up.dot(sd_), c1)
        place_craft(craft, best[1])
        bpy.context.view_layer.update()
        print(f"craft roll {best[1]['roll']}: sun {math.degrees(math.asin(best[0])):.1f} deg "
              f"above the wing plane")
    if C.get("face_cam"):
        # turn/bank so the upper surface of the wing faces the camera (sign search)
        best = None
        c0 = dict(C["craft"])
        for ys in (-1, 1):
            for rs_ in (-1, 1):
                c1 = dict(c0, yaw=ys * abs(c0["yaw"]), roll=rs_ * abs(c0["roll"]))
                place_craft(craft, c1)
                bpy.context.view_layer.update()
                up = craft.matrix_world.to_3x3() @ Vector((0, 0, 1))
                tc = (cam.location - craft.matrix_world.translation).normalized()
                if best is None or up.dot(tc) > best[0]:
                    best = (up.dot(tc), c1)
        place_craft(craft, best[1])
        print(f"craft yaw {best[1]['yaw']}, roll {best[1]['roll']}: upper surface at "
              f"{math.degrees(math.asin(max(-1, min(1, best[0])))):.0f} deg to the view")
        cam, tgt = setup_camera(C, craft, shot)
        for ob in [o for o in bpy.data.objects if o.name.startswith("cam") and o != cam]:
            bpy.data.objects.remove(ob)
    cl = cam.location
    print(f"camera {tuple(round(v, 1) for v in cl)}, {cl.z - ls.height(cl.x, cl.y):.1f} m above "
          f"ground; craft {tuple(round(v, 1) for v in craft.location)}")
    protos = ls.tree_library()
    # the escarpment below the abbey kept as open grazing along the line of flight: no
    # standing trees there (hedges and riverside willows stay)
    def in_corridor(p):
        s_, d_ = ls.sd(p[0], p[1])
        return -10 < s_ < ls.EDGE_S + ls.SLOPE_W + 60 and abs(d_) < 90 and p[3] in (0, 1, 2)
    pts = [p for p in ls.vegetation_points()
           if math.hypot(p[0], p[1]) > 55 and not in_corridor(p)]
    n0 = len(pts)
    pts = clear_sightlines(pts, cl, [tgt, craft.location, Vector((0, 0, Z0 + tw.ROOF))],
                           near=C.get("clear_near", 35.0), width=C.get("clear_w", 18.0))
    if C.get("town") == "saxon":
        town, houses = ls.build_town_saxon(coll, keep_out=[(cl.x, cl.y, C.get("town_keep", 70.0))])
    else:
        town, houses = ls.build_town(coll)
    # garden and orchard trees in the town plots, clear of houses and the line of flight
    import random as _r
    rg = _r.Random(5)
    hxy = [(h[0], h[1]) for h in houses]
    for _ in range(4000):
        s_, d_ = rg.uniform(-420, ls.EDGE_S - 14), rg.uniform(-ls.HALF_W + 25, ls.HALF_W - 25)
        x, y = ls.xy(s_, d_)
        if math.hypot(x - 18, y) < 42 or (s_ > -10 and abs(d_) < 40):
            continue
        if min((x - a) ** 2 + (y - b) ** 2 for a, b in hxy) < 9.0 ** 2:
            continue
        if min((x - a) ** 2 + (y - b) ** 2 for a, b in hxy) > 30.0 ** 2:
            continue
        pts.append((x, y, ls.height(x, y) - 0.2, 6 if rg.random() < 0.7 else 4,
                    rg.uniform(0.8, 1.3), rg.uniform(0, 6.3)))
    ls.scatter(coll, "vegetation", pts, protos)
    print(f"vegetation {len(pts)} instances ({n0 - len(pts)} cleared), {len(houses)} houses, "
          f"{time.time() - t:.0f}s")
    return C, craft


def setup_camera(C, craft, shot):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.05, 60000.0
    cd.lens = C["lens"]
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = 36.0
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    bpy.context.view_layer.update()
    cpos = craft.matrix_world @ Vector((0, 0.3, -0.3))
    if C.get("cam") is None:
        # on the line from the sun through the wing; sun_off (m, right/up in the view) slides
        # the sun disc relative to the craft
        sd_ = compass(C["sun_az"] + C.get("cam_daz", 0.0), C.get("cam_el", C["sun_el"]))
        right = sd_.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(sd_).normalized()
        cam.location = cpos - sd_ * C["cam_dist"]
        ox, oy = C.get("aim_off", (0.0, 0.0))
        tgt = cpos + right * ox + up * oy
    else:
        cc = C["cam"]
        x, y = ls.xy(cc["s"], cc["d"])
        if "abs" in cc:
            z = Z0 + cc["abs"]
        elif "ground" in cc:
            z = ls.height(x, y) + cc["ground"]
        else:
            z = roof_z() + cc["dz"]
        cam.location = (x, y, z)
        if "aim_mix" in C:
            # between the craft and the tower top, so both stay in frame
            L = Vector(cam.location)
            dc = (cpos - L).normalized()
            dt = (Vector((0, 0, roof_z())) - L).normalized()
            tgt = L + dc.lerp(dt, C["aim_mix"]) * 100.0
        else:
            a = C["aim"]
            ax, ay = ls.xy(a["s"], a["d"])
            tgt = Vector((ax, ay, (roof_z() if "dz" in a and a["s"] < 100 else Z0) + a["dz"]))
    rh.look_at(cam, tgt)
    cd.shift_y = C.get("shift", 0.0)
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = C["fstop"]
    cd.dof.focus_distance = (cpos - cam.location).length
    sc.camera = cam
    return cam, tgt


def setup_render(samples, preview, pct):
    sc = bpy.context.scene
    rh.setup_render(W, H, samples, preview)
    sc.render.resolution_percentage = pct or (25 if preview else 100)
    if not preview:
        sc.cycles.adaptive_threshold = 0.01
    sc.cycles.volume_bounces = 1
    sc.cycles.volume_step_rate = 4.0 if preview else 2.0
    sc.cycles.max_bounces = 12
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 4
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    sc.render.film_transparent = False
    return sc


def shot(name, preview, samples, pct, tag=""):
    t0 = time.time()
    C, craft = build_world(name, preview)
    sc = setup_render(samples, preview, pct)
    sc.view_settings.exposure = C["exposure"]
    from bpy_extras.object_utils import world_to_camera_view
    if "frame_y" in C:
        v = world_to_camera_view(sc, sc.camera, craft.location)
        sc.camera.data.shift_y += C["frame_y"] - (1 - v.y)
    for nm, P in (("craft", craft.location), ("tower", Vector((0, 0, roof_z())))):
        v = world_to_camera_view(sc, sc.camera, P)
        print(f"{nm} in frame at x {v.x:.2f}, y-from-top {1 - v.y:.2f}, dist {v.z:.0f} m")
    world_sky(C["sky"], C["sun_az"], C["sky_k"], res="8k" if preview else "16k",
              clamp=C.get("clamp", 60.0))
    warm = (1.0, 0.72, 0.48) if C["sun_el"] < 15 else (1.0, 0.93, 0.85)
    add_sun(C["sun_az"], C["sun_el"], C["sun_e"], C.get("sun_col", warm))
    if C["haze"]:
        volume_box("haze", (0, 0, 180), (24000, 24000, 380), C["haze"], (1, 1, 1), 0.6)
    if C["mist"]:
        mx, my = ls.xy(700, 0)
        volume_box("mist", (mx, my, 12), (2600, 2600, 26), C["mist"], (1, 1, 1), 0.4,
                   mist=(ls.RIVER_Z, C.get("mist_h", 3.0), 90.0))
    out = HERE / f"cover_{name}{tag}{'_preview' if preview else ''}.png"
    sc.render.filepath = str(out)
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {out.name}: build {t1 - t0:.0f}s render {time.time() - t1:.0f}s")
    return time.time() - t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default="all")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--samples", type=int, default=0)
    ap.add_argument("--pct", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    names = list(SHOTS) if a.shot == "all" else a.shot.split(",")
    times = {}
    for n in names:
        times[n] = shot(n, a.preview, a.samples or (64 if a.preview else 1024), a.pct, a.tag)
    print("render times (s):", {k: round(v) for k, v in times.items()})


if __name__ == "__main__":
    main()
