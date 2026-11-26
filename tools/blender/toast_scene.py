"""Breakpoint Lab - episode 015 in Blender (Cycles): which side does falling toast land on?

Same pipeline as glass_scene.py: the scene is built from code, engine/toast.html simulates the toast (Matthews 1995:
pivot on the table edge, then constant spin), lays out the video and says which pose each frame shows; this script
renders one image per different pose.

  blender -b -P tools/blender/toast_scene.py -- --poses work/timeline.json --out work/bscene --range 0-17

pose = {H table height (m), px pusher face x, tx tz toast centre (m), ta toast angle (deg, + = front end down),
        cx cz d camera: looks at (cx, 0, cz) from d metres in front}
Table edge at x = 0, table top at z = H, the lab base (floor) top at z = 0.
"""
import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_set import add_logo_base   # noqa: E402  (the BREAKPOINT LAB base, same in every scene)
from bottle_scene import obj, principled   # noqa: E402  (shared helpers)

SCENE = "BL_toast"
A, HT = 0.06, 0.007                    # toast: half length (12 cm), half thickness (14 mm)
WY = 0.052                             # toast: half width
PITCH = math.radians(22)               # camera looks down: the top face (butter or toast) reads, the logo stays in frame
TABLES = (0.75, 3.0)


def toast_outline(n=18):
    """a bread slice seen from above (x = length, y = width): straight sides, rounded corners, a domed crown at -x"""
    pts = []
    r = 0.012
    # right end (+x): two rounded corners
    for k in range(n + 1):
        a = -math.pi / 2 + math.pi / 2 * k / n
        pts.append((A - r + r * math.cos(a), -WY + r + r * math.sin(a)))
    for k in range(n + 1):
        a = math.pi / 2 * k / n
        pts.append((A - r + r * math.cos(a), WY - r + r * math.sin(a)))
    # crown (-x): the domed top of the loaf, a little wider than the slice
    for k in range(2 * n + 1):
        a = math.pi / 2 + math.pi * k / (2 * n)
        pts.append((-A + 0.018 + 0.018 * math.cos(a) * 1.0, (WY + 0.004) * math.sin(a)))
    return pts


def toast_mesh(name, thick, inset=0.0, z0=0.0, side_mat=1):
    pts = toast_outline()
    if inset:
        cx = sum(p[0] for p in pts) / len(pts)
        pts = [(cx + (x - cx) * (1 - inset / A), y * (1 - inset / WY)) for x, y in pts]
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z0 + thick)) for x, y in pts]
    fb = bm.faces.new(list(reversed(bot)))
    ft = bm.faces.new(top)
    n = len(pts)
    sides = [bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i])) for i in range(n)]
    for f in sides:
        f.material_index = side_mat                            # crust (bread) / same material (butter)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if (e.verts[0].co.z == e.verts[1].co.z)], offset=thick * 0.3,
                    segments=3, profile=0.5, affect='EDGES')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:                                                       # flat faces stay flat (no dark smear), bevels smooth
        me.set_sharpness_by_angle(angle=math.radians(35))
    except AttributeError:
        pass
    return me


def bread_material():
    """toasted crumb: golden, darker patches, rough, a fine bump (no flat colour, no constant gloss)"""
    m = bpy.data.materials.get("BL_Toast") or bpy.data.materials.new("BL_Toast")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if not any(n.type == 'TEX_NOISE' for n in nt.nodes):
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 90.0
        noise.inputs["Detail"].default_value = 8.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.30, 0.13, 0.03, 1)
        ramp.color_ramp.elements[1].position = 0.70
        ramp.color_ramp.elements[1].color = (0.62, 0.36, 0.11, 1)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = 0.55
        rr.inputs["To Max"].default_value = 0.85
        nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.35
        bump.inputs["Distance"].default_value = 0.0008
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def butter_material():
    m = bpy.data.materials.get("BL_Butter") or bpy.data.materials.new("BL_Butter")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.98, 0.68, 0.10, 1)   # warm butter (AgX turns pale yellow green)
    b.inputs["Roughness"].default_value = 0.28
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.15
    if not any(n.type == 'TEX_NOISE' for n in nt.nodes):          # melted, spread with a knife: gentle waves
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 30.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.5
        bump.inputs["Distance"].default_value = 0.0006
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def box(sc, name, size, loc, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    o.name = name
    o["bb"] = name
    if bevel:
        bpy.ops.object.modifier_add(type='BEVEL')
        o.modifiers[-1].width = bevel
        o.modifiers[-1].segments = 2
    o.data.materials.append(mat)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)
    return o


def build(res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    wood = principled("BL_Wood", **{"Base Color": (0.30, 0.17, 0.08, 1), "Roughness": 0.45})
    leg = principled("BL_Leg", **{"Base Color": (0.24, 0.13, 0.06, 1), "Roughness": 0.5})
    alu = principled("BL_Alu", **{"Base Color": (0.80, 0.81, 0.83, 1), "Metallic": 1.0, "Roughness": 0.32})
    back = principled("BL_Back", **{"Base Color": (0.50, 0.53, 0.57, 1), "Roughness": 0.9})   # light wall: the brown toast reads
    crust = principled("BL_Crust", **{"Base Color": (0.22, 0.10, 0.03, 1), "Roughness": 0.7})

    # the toast: slice (crumb faces + crust sides) with a layer of butter on top, all one object
    me = toast_mesh("Toast", 2 * HT, z0=-HT)
    me.materials.append(bread_material())
    me.materials.append(crust)
    t = obj(sc, "Toast", me)
    bm_me = toast_mesh("Butter", 0.0022, inset=0.006, z0=HT - 0.0002, side_mat=0)
    bm_me.materials.append(butter_material())
    bt = obj(sc, "Butter", bm_me)
    bt.parent = t

    # tables (kitchen 75 cm and the 3 m one): top 90 x 60 cm, edge at x = 0
    for h in TABLES:
        k = f"T{int(h * 100)}"
        box(sc, k + "_top", (0.90, 0.60, 0.03), (-0.45, 0, h - 0.015), wood, bevel=0.003)
        for lx in (-0.86, -0.04):
            for ly in (-0.26, 0.26):
                box(sc, k + f"_leg{lx}{ly}", (0.04, 0.04, h - 0.03), (lx, ly, (h - 0.03) / 2), leg)
    # the lab pusher: an aluminium paddle on a rod coming from the left
    box(sc, "Paddle", (0.024, 0.13, 0.034), (0, 0, 0), alu, bevel=0.002)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=1.6, rotation=(0, math.radians(90), 0))
    rod = bpy.context.object
    rod.name = "Rod"
    rod["bb"] = "Rod"
    rod.data.materials.append(alu)
    for c in list(rod.users_collection):
        c.objects.unlink(rod)
    sc.collection.objects.link(rod)

    # floor = the lab base (logo on its front face), wall behind
    add_logo_base(sc, width=2.6, height=0.16, depth=0.9, top_z=0.0)
    for o in sc.objects:                                        # centred in the frame (the camera looks at x = 0.32)
        if o.get("bb") in ("LabBase", "Logo"):
            o.location.x += 0.32
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.16))
    pl = bpy.context.object
    pl.name = "Ground"
    pl.data.materials.append(principled("BL_Bench", **{"Base Color": (0.55, 0.57, 0.60, 1), "Roughness": 0.45}))
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 1.6, 4.0), rotation=(math.radians(90), 0, 0))
    bg = bpy.context.object
    bg.name = "Backdrop"
    bg.data.materials.append(back)
    for o in (pl, bg):
        for c in o.users_collection:
            c.objects.unlink(o)
        sc.collection.objects.link(o)

    def area(name, loc, aim, size, e, sy=None):
        lt = bpy.data.lights.new(name, 'AREA')
        lt.energy = e
        lt.shape = 'RECTANGLE'
        lt.size = size
        lt.size_y = sy or size
        o = bpy.data.objects.new(name, lt)
        o.location = loc
        d = [aim[i] - loc[i] for i in range(3)]
        o.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) + math.pi / 2)
        o["bb"] = name
        sc.collection.objects.link(o)
        return o
    area("Key", (-1.6, -2.4, 2.6), (0.2, 0, 0.4), 1.6, 1400)          # soft key from front left, above
    area("Fill", (2.2, -2.0, 1.8), (0.2, 0, 0.4), 2.0, 500)            # soft fill from front right (no light on the wall)
    area("KeyHigh", (-1.6, -2.4, 4.6), (0.2, 0, 2.8), 1.6, 1400)       # same key for the top of the 3 m table

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 85
    cam.clip_end = 100
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_World") or bpy.data.worlds.new("BL_World")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.78, 0.82, 1)
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    sc.world = wd

    r = sc.render
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps = 30
    r.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 64
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    set_pose({"H": 0.75, "px": -0.16, "tx": -0.10, "tz": 0.757, "ta": 0, "cx": 0.32, "cz": 0.33, "d": 6.0}, sc)
    return sc


# ---------------------------------------------------------------- pose: the one place where motion is defined
def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    H = float(p["H"])
    for h in TABLES:
        k = f"T{int(h * 100)}"
        hide = abs(h - H) > 0.01
        for name, o in ob.items():
            if name.startswith(k + "_"):
                o.hide_render = o.hide_viewport = hide
    t = ob["Toast"]
    t.location = (float(p["tx"]), 0.0, float(p["tz"]))
    t.rotation_euler = (0.0, math.radians(float(p["ta"])), 0.0)   # + about Y: the +x (front) end goes down
    px = float(p["px"])
    ob["Paddle"].location = (px - 0.012, 0.0, H + 0.017)
    ob["Rod"].location = (px - 0.024 - 0.8, 0.0, H + 0.017)
    cx, cz, d = float(p["cx"]), float(p["cz"]), float(p["d"])
    cam = ob["Cam"]
    cam.location = (cx, -d * math.cos(PITCH), cz + d * math.sin(PITCH))
    cam.rotation_euler = (math.pi / 2 - PITCH, 0.0, 0.0)


def render_poses(poses, out, rng=None, samples=None, pct=100):
    os.makedirs(out, exist_ok=True)
    sc = build()
    if samples:
        sc.cycles.samples = int(samples)
    sc.render.resolution_percentage = int(pct)
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 92
    lo, hi = rng or (0, len(poses) - 1)
    for p in poses[lo:hi + 1]:
        set_pose(p, sc)
        sc.render.filepath = os.path.join(out, p["key"] + ".jpg")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        print("rendered", p["key"], flush=True)


if __name__ == "__main__" and "--" in sys.argv:
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--poses", required=True)
    ap.add_argument("--out", default="bscene")
    ap.add_argument("--range", default="")
    ap.add_argument("--samples", default=None)
    ap.add_argument("--pct", default=100)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    P = json.load(open(a.poses))
    P = P["poses"] if isinstance(P, dict) else P
    rng = tuple(int(x) for x in a.range.split("-")) if a.range else None
    render_poses(P, a.out, rng, a.samples, a.pct)
