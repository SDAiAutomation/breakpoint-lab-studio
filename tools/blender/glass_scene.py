"""Breakpoint Lab - episode 014 in Blender (Cycles): can a voice break a wine glass?

Same pipeline as bottle_scene.py: the whole scene is built from code, engine/glass.html lays out the video and says
which pose each frame shows, this script renders one image per different pose.

  blender -b -P tools/blender/glass_scene.py -- --poses work/timeline.json --out work/bscene --range 0-17

Physics shown (MythBusters ep. 31, 2005; Scientific American): a voice at the glass's own note (its resonant frequency)
makes the rim flex in its first mode (it goes oval, one way then the other); each cycle adds to the last, the bending
grows until the crystal cracks. The wrong note, even loud, barely moves it. Motion amplitude is exaggerated to be
visible (labelled "Simulated").

pose = {amp 0..1 (rim bend, 1 = breaking point), ph 0..7 (phase of the oval, 1/8 cycle), tb ms after the break
        (-1 = intact), cam wide|close, k 0..1 (camera push-in)}
"""
import math
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_set import add_logo_base   # noqa: E402  (the BREAKPOINT LAB base, same in every scene)
from bottle_scene import clip_profile, solid_sweep, obj, principled, smooth   # noqa: E402  (shared helpers)

SCENE = "BL_glass"
# wine glass (m): foot, stem, bowl; lead crystal walls ~1.3 mm
FOOT = [(0.0, 0.0), (0.036, 0.0), (0.037, 0.0015), (0.034, 0.0035), (0.012, 0.0060), (0.0045, 0.012), (0.0040, 0.080),
        (0.0060, 0.086), (0.0, 0.087)]
BOWL_OUT = [(0.0, 0.084), (0.0070, 0.0845), (0.0160, 0.0890), (0.0300, 0.1020), (0.0395, 0.1200), (0.0425, 0.1400),
            (0.0410, 0.1600), (0.0380, 0.1780), (0.0360, 0.1900)]
WALL = 0.0013
RIM_Z, CUP_Z, BAND_Z = 0.1900, 0.1060, 0.1460     # rim; the lower cup stays on the stem; shards = 2 bands above it
N_SECT = 8
AMP_MAX = 0.0045                                     # rim bend at amp = 1 (m), exaggerated to be seen
DEF = {}                                             # rest coordinates of the bowl, for the oval mode


def densify(pts, n=6):
    """Catmull-Rom through the profile points: a smooth bowl, no flat bands"""
    out = []
    P = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(pts[-1])
    return out


def bowl_profile():
    smooth_out = densify(BOWL_OUT)
    inner = [(max(0.0, r - WALL), z + (WALL if i == 0 else 0)) for i, (r, z) in enumerate(smooth_out)]
    inner[-1] = (smooth_out[-1][0] - WALL, RIM_Z - 0.0004)
    out = list(smooth_out[:-1]) + [(smooth_out[-1][0], RIM_Z - 0.0004), (smooth_out[-1][0] - WALL * 0.5, RIM_Z)]
    return out + list(reversed(inner))


def mode_shape(z):
    """how much a point of the bowl at height z takes part in the oval mode: 0 at the stem, 1 at the rim"""
    u = max(0.0, (z - 0.088) / (RIM_Z - 0.088))
    return u * u


def deform(o, amp, ph):
    """first bending mode (2 lobes): dr = A * w(z) * cos(2 theta) * cos(phase)"""
    import numpy as np
    me = o.data
    key = me.name
    if key not in DEF:
        co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        th = np.arctan2(co[:, 1], co[:, 0])
        r = np.hypot(co[:, 0], co[:, 1])
        w = np.array([mode_shape(z) for z in co[:, 2]], dtype=np.float32)
        DEF[key] = (co.copy(), th, r, w)
    co, th, r, w = DEF[key]
    dr = AMP_MAX * amp * w * np.cos(2 * th) * math.cos(2 * math.pi * ph / 8.0)
    k = np.where(r > 1e-6, (r + dr) / np.maximum(r, 1e-6), 1.0)
    new = co.copy()
    new[:, 0] *= k
    new[:, 1] *= k
    me.vertices.foreach_set("co", new.ravel())
    me.update()


# ---------------------------------------------------------------- build
def build(res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    DEF.clear()

    crystal = principled("BL_Crystal", **{"Base Color": (0.94, 0.97, 1.0, 1), "Transmission Weight": 1.0, "Roughness": 0.0,
                                         "IOR": 1.56})
    shard = principled("BL_Shard", **{"Base Color": (0.80, 0.86, 0.95, 1), "Transmission Weight": 1.0, "Roughness": 0.08,
                                     "IOR": 1.56})     # a touch of tint: broken pieces lying on the white base stay visible
    bench = principled("BL_Bench", **{"Base Color": (0.55, 0.57, 0.60, 1), "Roughness": 0.45})
    back = principled("BL_Back", **{"Base Color": (0.20, 0.23, 0.27, 1), "Roughness": 0.8})
    black = principled("BL_Black", **{"Base Color": (0.01, 0.01, 0.012, 1), "Roughness": 1.0})

    obj(sc, "Foot", solid_sweep("Foot", FOOT, steps=128), crystal)
    prof = bowl_profile()
    obj(sc, "Bowl", solid_sweep("Bowl", prof, steps=160), crystal)              # intact, deformed by the voice
    obj(sc, "Cup", solid_sweep("Cup", clip_profile(prof, -1.0, CUP_Z), steps=160), crystal)   # stays after the break
    bands = [(CUP_Z, BAND_Z), (BAND_Z, RIM_Z + 0.001)]
    for b, (z0, z1) in enumerate(bands):
        poly = clip_profile(prof, z0, z1)
        for i in range(N_SECT):
            off = 0.5 * b                                  # staggered cracks between the two bands
            a0 = 2 * math.pi * (i + off) / N_SECT
            a1 = a0 + 2 * math.pi / N_SECT * 0.97
            s = obj(sc, f"Shard{b}_{i}", solid_sweep(f"Shard{b}_{i}", poly, a0, a1, steps=10), shard)
            s["a"] = (a0 + a1) / 2
            s["band"] = b

    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, -0.064))   # floor under the lab base
    pl = bpy.context.object
    pl.name = "Bench"
    pl.data.materials.append(bench)
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0.6, 1.0), rotation=(math.radians(90), 0, 0))
    bg = bpy.context.object
    bg.name = "Backdrop"
    bg.data.materials.append(back)
    for o in (pl, bg):
        for c in o.users_collection:
            c.objects.unlink(o)
        sc.collection.objects.link(o)
    add_logo_base(sc, width=0.40, height=0.06, depth=0.26, top_z=-0.004)
    for nm, x in (("FlagL", -0.14), ("FlagR", 0.14)):      # black cards seen only in the glass: dark edges on clear crystal
        me = bpy.data.meshes.new(nm)
        me.from_pydata([(0, -0.10, 0), (0, 0.10, 0), (0, 0.10, 0.40), (0, -0.10, 0.40)], [], [(0, 1, 2, 3)])
        f = obj(sc, nm, me, black)
        f.location = (x, 0.05, 0.0)
        f.visible_camera = False
        f.visible_shadow = False

    def area(name, loc, rot, size, e, sy=None):
        lt = bpy.data.lights.new(name, 'AREA')
        lt.energy = e
        lt.shape = 'RECTANGLE'
        lt.size = size
        lt.size_y = sy or size
        o = bpy.data.objects.new(name, lt)
        o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(o)
    area("Key", (-0.35, -0.35, 0.45), (55, 0, -45), 0.5, 35)
    area("RimL", (-0.25, 0.25, 0.15), (90, 0, -145), 0.04, 40, sy=0.5)
    area("RimR", (0.25, 0.25, 0.15), (90, 0, 145), 0.04, 40, sy=0.5)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 85
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_World") or bpy.data.worlds.new("BL_World")
    wd.use_nodes = True
    nt = wd.node_tree
    bgn = nt.nodes["Background"]
    if not any(n.type == 'VALTORGB' for n in nt.nodes):   # same studio gradient as the bottle (one look per channel)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.45
        ramp.color_ramp.elements[0].color = (0.30, 0.31, 0.33, 1)
        ramp.color_ramp.elements[1].position = 0.62
        ramp.color_ramp.elements[1].color = (0.95, 0.97, 1.0, 1)
        mp = nt.nodes.new("ShaderNodeMapRange")
        mp.inputs["From Min"].default_value = -1.0
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], mp.inputs["Value"])
        nt.links.new(mp.outputs["Result"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bgn.inputs["Color"])
    bgn.inputs[1].default_value = 0.6
    sc.world = wd

    r = sc.render
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps = 30
    r.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 256
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    sc.cycles.max_bounces = 12
    sc.cycles.glossy_bounces = 4
    sc.cycles.transmission_bounces = 12
    sc.cycles.sample_clamp_indirect = 8.0
    r.use_persistent_data = False
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    r.film_transparent = False
    set_pose({'amp': 0, 'ph': 0, 'tb': -1, 'cam': 'wide', 'k': 0}, sc)
    return sc


# ---------------------------------------------------------------- pose: the one place where motion is defined
def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    amp, ph, tb = float(p["amp"]), int(p["ph"]), float(p["tb"])
    broken = tb >= 0
    bowl = ob["Bowl"]
    bowl.hide_render = bowl.hide_viewport = broken
    ob["Cup"].hide_render = ob["Cup"].hide_viewport = not broken
    if not broken:
        deform(bowl, amp, ph)
    # shards: thrown out along the oval (fastest where the rim bent most: theta = 0 and pi), then gravity
    for b in range(2):
        for i in range(N_SECT):
            s = ob[f"Shard{b}_{i}"]
            s.hide_render = s.hide_viewport = not broken
            if not broken:
                continue
            a = s["a"]
            h = (math.sin((i + 8 * b) * 3.7 + 1.1) * 4375.85) % 1.0
            dt = min(tb, 260.0) / 1000.0
            v = (0.12 + 0.18 * abs(math.cos(2 * a)) + 0.08 * h) * (1.0 + 0.25 * b)   # m/s: they stay on the base
            rr = min(v * dt, 0.11)
            dx, dy = math.cos(a) * rr, math.sin(a) * rr
            zc = 0.12 + 0.04 * b
            dz = (0.25 + 0.3 * h) * dt - 0.5 * 9.81 * dt * dt
            dz = max(dz, -zc + 0.004)                                                  # lands on the base
            s.location = (dx, dy, dz)
            spin = dt * (6 + 10 * h)
            s.rotation_euler = (spin * math.sin(a), spin * math.cos(a), 0.6 * spin * (h - 0.5))
    # cameras (85 mm): wide = whole glass on the base, glass in the lower-middle (text band clear);
    # close = the bowl and the rim, where the oval is seen; k = slow push-in
    kk = float(p.get("k", 0))
    if p.get("cam") == "closelow":                       # explain: same close-up, glass lower (room for the wave under the text)
        d, look, elev = 0.95, (0.0, 0.0, 0.156), 0.15
    elif p.get("cam") == "close":
        d, look, elev = 0.88 - 0.08 * kk, (0.0, 0.0, 0.130), 0.15
    else:
        d, look, elev = 1.55, (0.0, 0.0, 0.130), 0.21
    cam = ob["Cam"]
    cam.location = (math.sin(0.30) * d, -math.cos(0.30) * d, elev)
    dx, dy, dz = look[0] - cam.location[0], look[1] - cam.location[1], look[2] - cam.location[2]
    cam.rotation_euler = (math.atan2(math.hypot(dx, dy), -dz), 0, math.atan2(dy, dx) - math.pi / 2)


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
