"""Breakpoint Lab - episode 016 in Blender (Cycles): the cable snaps, does jumping at the last second save you?

Same pipeline as toast_scene.py: the scene is built from code, engine/elevator.html simulates the fall (free fall,
v = sqrt(2 g h); a jump only adds 7 mph upward, Baird 2012), lays out the video and says which pose each frame shows;
this script renders one image per different pose.

  blender -b -P tools/blender/elevator_scene.py -- --poses work/timeline.json --out work/bscene --range 0-17

pose = {zc car floor underside (m), cut cable recoil (m), c crouch 0-1, arm (0 down, 1 up, <0 back), lean 0-1,
        dz rider lift above the car floor (m), buf buffer length 0-1, cz camera height (m), d camera distance (m)}
A cutaway shaft: the front is open, the camera tracks the car from 18 m with an 85 mm lens. Floors every 11 ft,
painted numbers 1-16; the lab base (logo) is the pit floor, buffers on top of it (z = 0.35 when not crushed).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_set import add_logo_base, _text   # noqa: E402  (the BREAKPOINT LAB base, same in every scene)
from bottle_scene import obj, principled   # noqa: E402  (shared helpers)

SCENE = "BL_elevator"
FLOOR = 0.3048 * 11                    # one floor = 11 ft (165 ft = 15 floors)
BUF, CRUSH = 0.35, 0.15
CAR_W, CAR_D, CAR_H = 1.60, 1.40, 2.30
SHAFT_TOP = 62.0
PITCH = math.radians(4)
FACE = math.radians(-28)               # the rider stands side-on, turned a little towards the camera

# rider (crash-test dummy) sizes, metres
SHIN, THIGH, TORSO, UARM, FARM = 0.44, 0.44, 0.52, 0.30, 0.28
ANKLE = 0.08


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


def _link(sc, o, name):
    o.name = name
    o["bb"] = name
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)
    return o


def cyl(sc, name, r, mat, verts=20):
    """unit-length cylinder along +Z from 0 to 1 (scaled to a segment by place())"""
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=1, depth=1, location=(0, 0, 0.5))
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    o.scale = (r, r, 1)
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return _link(sc, o, name)


def ball(sc, name, r, mat, sx=1.0, sy=1.0, sz=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, radius=r)
    o = bpy.context.object
    o.scale = (sx, sy, sz)
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return _link(sc, o, name)


def concrete():
    m = bpy.data.materials.get("BL_Concrete") or bpy.data.materials.new("BL_Concrete")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if not any(n.type == 'TEX_NOISE' for n in nt.nodes):
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3.0
        noise.inputs["Detail"].default_value = 10.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.20, 0.205, 0.21, 1)
        ramp.color_ramp.elements[1].color = (0.36, 0.36, 0.355, 1)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = 0.75
        rr.inputs["To Max"].default_value = 0.95
        nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.25
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def build(res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    steel = principled("BL_Steel", **{"Base Color": (0.55, 0.56, 0.58, 1), "Metallic": 1.0, "Roughness": 0.38})
    dark_steel = principled("BL_DarkSteel", **{"Base Color": (0.16, 0.16, 0.17, 1), "Metallic": 1.0, "Roughness": 0.5})
    sling = principled("BL_Sling", **{"Base Color": (0.55, 0.20, 0.06, 1), "Roughness": 0.55})       # painted steel frame
    panel = principled("BL_CarPanel", **{"Base Color": (0.62, 0.60, 0.56, 1), "Roughness": 0.42})    # light laminate walls
    rubber = principled("BL_CarFloor", **{"Base Color": (0.09, 0.09, 0.10, 1), "Roughness": 0.8})
    yellow = principled("BL_Dummy", **{"Base Color": (0.82, 0.56, 0.07, 1), "Roughness": 0.42})
    joint = principled("BL_Joint", **{"Base Color": (0.05, 0.05, 0.055, 1), "Roughness": 0.5})
    paint = principled("BL_FloorPaint", **{"Base Color": (0.80, 0.66, 0.20, 1), "Roughness": 0.7})
    lamp = principled("BL_Lamp", **{"Base Color": (1, 0.95, 0.85, 1), "Emission Color": (1, 0.93, 0.80, 1),
                                    "Emission Strength": 6.0})
    conc = concrete()

    # ---- shaft: back wall, side walls, floor slabs every 11 ft with painted numbers, guide rails
    box(sc, "BackWall", (3.6, 0.2, SHAFT_TOP + 2), (0, 1.0, SHAFT_TOP / 2 - 1), conc)
    for sx in (-1, 1):
        box(sc, f"SideWall{sx}", (0.25, 2.2, SHAFT_TOP + 2), (sx * 1.85, 0.0, SHAFT_TOP / 2 - 1), conc)
        box(sc, f"Rail{sx}", (0.06, 0.12, SHAFT_TOP), (sx * 1.02, 0.0, SHAFT_TOP / 2), steel)
    for k in range(1, 18):
        z = BUF + (k - 1) * FLOOR
        if k >= 2:                                             # the slab edge of each landing
            box(sc, f"Slab{k}", (3.5, 0.12, 0.28), (0, 0.86, z - 0.14), conc, bevel=0.01)
        for sx in (-1, 1):                                     # rail brackets
            box(sc, f"Bracket{k}{sx}", (0.18, 0.75, 0.08), (sx * 1.13, 0.5, z + 1.2), dark_steel)
        if k <= 16:
            t = _text(sc, f"Num{k}", str(k), 0.42, paint, -1.42, 0.895, z + 1.55)
            t["bb"] = f"Num{k}"

    # ---- pit: the lab base is the pit floor (logo on its front face), oil buffers on top
    add_logo_base(sc, width=3.4, height=0.48, depth=2.0, top_z=0.0)
    for sx in (-1, 1):
        cyl(sc, f"BufBody{sx}", 0.11, dark_steel)
        cyl(sc, f"BufRod{sx}", 0.05, steel)
        cyl(sc, f"BufPad{sx}", 0.12, rubber)
    box(sc, "PitFloor", (3.6, 2.4, 0.05), (0, 0.0, -0.53), conc)

    # ---- the car: open front (cutaway), red sling frame, cable
    me_parts = []
    me_parts.append(box(sc, "CarFloor", (CAR_W, CAR_D, 0.12), (0, 0, 0.06), rubber, bevel=0.01))
    me_parts.append(box(sc, "CarBack", (CAR_W, 0.06, CAR_H), (0, CAR_D / 2 - 0.03, CAR_H / 2), panel))
    for sx in (-1, 1):
        me_parts.append(box(sc, f"CarSide{sx}", (0.06, CAR_D, CAR_H), (sx * (CAR_W / 2 - 0.03), 0, CAR_H / 2), panel))
        me_parts.append(box(sc, f"Stile{sx}", (0.10, 0.16, CAR_H + 0.45), (sx * (CAR_W / 2 + 0.07), 0, (CAR_H + 0.45) / 2 - 0.12), sling))
        me_parts.append(box(sc, f"Shoe{sx}", (0.10, 0.10, 0.18), (sx * 0.95, 0, CAR_H + 0.1), dark_steel))
    me_parts.append(box(sc, "CarRoof", (CAR_W, CAR_D, 0.08), (0, 0, CAR_H + 0.04), panel))
    me_parts.append(box(sc, "Crosshead", (CAR_W + 0.36, 0.20, 0.18), (0, 0, CAR_H + 0.33), sling, bevel=0.01))
    me_parts.append(box(sc, "Plank", (CAR_W + 0.36, 0.20, 0.14), (0, 0, 0.05), sling, bevel=0.01))
    me_parts.append(box(sc, "Light", (0.9, 0.5, 0.02), (0, 0, CAR_H - 0.01), lamp))
    me_parts.append(box(sc, "Handrail", (1.2, 0.05, 0.05), (0, CAR_D / 2 - 0.12, 0.95), steel))
    me_parts.append(box(sc, "Stub", (0.035, 0.035, 0.35), (0, 0, CAR_H + 0.6), dark_steel))   # what is left of the cable
    car = bpy.data.objects.new("Car", None)
    car["bb"] = "Car"
    sc.collection.objects.link(car)
    for o in me_parts:
        o.parent = car
    cab = box(sc, "Cable", (0.035, 0.035, SHAFT_TOP), (0, 0, 0), dark_steel)   # placed in set_pose

    # ---- the rider: a crash-test dummy, capsules placed from the joint positions in set_pose
    for side in ("L", "R"):
        for seg, r in (("Shin", 0.055), ("Thigh", 0.075), ("UArm", 0.045), ("FArm", 0.04)):
            cyl(sc, f"{seg}{side}", r, yellow)
        for j, r in (("Knee", 0.065), ("Hip", 0.08), ("Shoulder", 0.065), ("Elbow", 0.05), ("Ankle", 0.05)):
            ball(sc, f"{j}{side}", r, joint)
        ball(sc, f"Hand{side}", 0.05, yellow, 1.0, 0.8, 1.3)
        box(sc, f"Foot{side}", (0.26, 0.10, 0.08), (0, 0, 0), yellow, bevel=0.02)
    box(sc, "Torso", (0.24, 0.38, 1.0), (0, 0, 0), yellow, bevel=0.05)
    box(sc, "Pelvis", (0.24, 0.34, 0.16), (0, 0, 0), joint, bevel=0.04)
    cyl(sc, "Neck", 0.045, joint)
    ball(sc, "Head", 0.115, yellow, 0.95, 0.85, 1.12)
    ball(sc, "Target", 0.035, joint, 1.0, 0.3, 1.0)            # the black-and-yellow marker on the side of the head

    # ---- lights: soft key from front left, fill from front right, both follow the car (set_pose)
    def area(name, size, e):
        lt = bpy.data.lights.new(name, 'AREA')
        lt.energy = e
        lt.shape = 'RECTANGLE'
        lt.size = size
        lt.size_y = size
        o = bpy.data.objects.new(name, lt)
        o["bb"] = name
        sc.collection.objects.link(o)
        return o
    area("Key", 3.0, 9000)
    area("Fill", 4.0, 3500)
    area("Top", 2.5, 1500)                                      # from above: a rim on the car and the rider
    pit = area("PitLight", 4.0, 3000)                           # the base and its logo at the bottom
    pit.location = (1.5, -7.0, 2.0)
    aim(pit, (0, 0, 0.0))

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 85
    cam.clip_end = 200
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_World") or bpy.data.worlds.new("BL_World")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.70, 0.73, 0.78, 1)
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.35
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
    set_pose({"zc": BUF + 15 * FLOOR, "cut": 0, "c": 0, "arm": 0, "lean": 0, "dz": 0, "buf": 1,
              "cz": BUF + 15 * FLOOR + 1.3, "d": 18.0}, sc)
    return sc


def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def place(o, a, b):
    """stretch a unit +Z cylinder from point a to point b"""
    a, b = Vector(a), Vector(b)
    v = b - a
    o.location = a
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    o.scale = (o.scale.x, o.scale.y, max(v.length, 1e-4))


def rider_joints(c, arm, lean):
    """side-view joints (x forward, z up) for crouch c, arm swing and lean; feet flat at z = 0"""
    ts = math.radians(60) * c                                  # shin leans forward
    th = math.radians(70) * c                                  # thigh leans back (hips go back)
    tb = math.radians(35) * c + math.radians(50) * lean        # torso leans forward
    ank = Vector((0, 0, ANKLE))
    knee = ank + SHIN * Vector((math.sin(ts), 0, math.cos(ts)))
    hip = knee + THIGH * Vector((-math.sin(th), 0, math.cos(th)))
    up = Vector((math.sin(tb), 0, math.cos(tb)))
    sho = hip + TORSO * up
    head = sho + 0.24 * up
    a = math.radians(170) * arm + tb                           # 0: hangs along the body; + swings forward and up
    ua = Vector((math.sin(a) * 1.0, 0, -math.cos(a)))
    elb = sho + UARM * ua
    fa_ang = a + math.radians(25)
    hand = elb + FARM * Vector((math.sin(fa_ang), 0, -math.cos(fa_ang)))
    return dict(ank=ank, knee=knee, hip=hip, sho=sho, head=head, elb=elb, hand=hand, up=up)


# ---------------------------------------------------------------- pose: the one place where motion is defined
def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    zc = float(p["zc"])
    ob["Car"].location = (0, 0, zc)
    # cable: intact from the crosshead to the top, or cut above the stub and whipped up by `cut` metres
    top = zc + CAR_H + 0.42
    cut = float(p["cut"])
    lo = top + (0.45 + cut if cut > 0 else 0.0)
    cab = ob["Cable"]
    cab.location = (0, 0, (lo + SHAFT_TOP + 8) / 2)
    cab.scale = (0.035, 0.035, max(0.1, SHAFT_TOP + 8 - lo))
    ob["Stub"].hide_render = ob["Stub"].hide_viewport = cut <= 0
    # buffers: body fixed on the base, rod + pad compress with the car
    blen = min(BUF, zc)                                       # the pads touch the car underside
    for sx in (-1, 1):
        x = sx * 0.55
        place(ob[f"BufBody{sx}"], (x, 0, 0), (x, 0, 0.16))
        place(ob[f"BufRod{sx}"], (x, 0, 0.16), (x, 0, max(0.17, blen - 0.04)))
        place(ob[f"BufPad{sx}"], (x, 0, max(0.17, blen - 0.04)), (x, 0, blen))
    # rider: side-on (faces +x), turned towards the camera, centred in the car
    J = rider_joints(float(p["c"]), float(p["arm"]), float(p["lean"]))
    base = Vector((-0.12, 0.05, zc + 0.12 + float(p["dz"])))
    rot = lambda v: Vector((v.x * math.cos(FACE) - v.y * math.sin(FACE), v.x * math.sin(FACE) + v.y * math.cos(FACE), v.z))
    for side, yo in (("L", 0.11), ("R", -0.11)):
        W = lambda k, yy=yo: base + rot(J[k] + Vector((0, yy, 0)))
        place(ob[f"Shin{side}"], W("ank"), W("knee"))
        place(ob[f"Thigh{side}"], W("knee"), W("hip"))
        for j, k in (("Knee", "knee"), ("Hip", "hip"), ("Ankle", "ank")):
            ob[f"{j}{side}"].location = W(k)
        ys = yo * 1.85
        WS = lambda k, yy=ys: base + rot(J[k] + Vector((0, yy, 0)))
        place(ob[f"UArm{side}"], WS("sho"), WS("elb"))
        place(ob[f"FArm{side}"], WS("elb"), WS("hand"))
        ob[f"Shoulder{side}"].location = WS("sho")
        ob[f"Elbow{side}"].location = WS("elb")
        ob[f"Hand{side}"].location = WS("hand")
        f = ob[f"Foot{side}"]
        f.location = base + rot(Vector((0.07, yo, 0.04)))
        f.rotation_euler = (0, 0, FACE)
    tb = math.atan2(J["up"].x, J["up"].z)
    for name, k, off in (("Torso", None, 0.0), ("Pelvis", "hip", 0.0)):
        o = ob[name]
        if name == "Torso":
            mid = (J["hip"] + J["sho"]) / 2
            o.location = base + rot(mid)
            o.scale = (0.24, 0.38, TORSO * 1.05)
        else:
            o.location = base + rot(J["hip"])
        o.rotation_euler = (0, tb, FACE)
    place(ob["Neck"], base + rot(J["sho"]), base + rot(J["sho"] + 0.12 * J["up"]))
    ob["Head"].location = base + rot(J["head"])
    ob["Head"].rotation_euler = (0, tb, FACE)
    ob["Target"].location = base + rot(J["head"] + Vector((0, -0.1, 0.01)))
    ob["Target"].rotation_euler = (0, tb, FACE)
    # lights follow the car
    for name, off, tgt in (("Key", (-5.0, -7.0, 4.5), 1.2), ("Fill", (6.0, -6.0, 1.5), 1.0), ("Top", (0.5, -1.0, 6.0), 1.0)):
        L = ob[name]
        L.location = (off[0], off[1], zc + off[2])
        aim(L, (0, 0, zc + tgt))
    cz, d = float(p["cz"]), float(p["d"])
    cam = ob["Cam"]
    cam.location = (0.0, -d * math.cos(PITCH), cz + d * math.sin(PITCH))
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
