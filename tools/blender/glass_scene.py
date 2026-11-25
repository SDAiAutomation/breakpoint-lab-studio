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
from mathutils import Quaternion, Vector

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
RIM_Z = 0.1900
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



# ---------------------------------------------------------------- fracture: irregular curved shards, jagged remnant
GROUND = -0.004          # top of the lab base
N_CHIPS = 36


def _bm_from_me(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    return bm


def _cut(bm, co, no):
    """split a closed solid in two along a plane, both halves closed again (the crack faces)"""
    halves = []
    for keep_inner in (True, False):
        h = bm.copy()
        geom = h.verts[:] + h.edges[:] + h.faces[:]
        res = bmesh.ops.bisect_plane(h, geom=geom, plane_co=co, plane_no=no, dist=1e-7,
                                     clear_outer=keep_inner, clear_inner=not keep_inner)
        cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if cut_edges:
            bmesh.ops.holes_fill(h, edges=cut_edges, sides=0)
        if len(h.verts) >= 4 and len(h.faces) >= 4:
            halves.append(h)
        else:
            h.free()
    return halves


def _split_loose(bm):
    """a plane through a ring can leave two separate arcs on one side: one piece each"""
    out = []
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack, group = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            group.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        out.append(group)
    if len(out) == 1:
        return [bm]
    parts = []
    for group in out:
        keep = set(group)
        h = bm.copy()
        h.faces.index_update()                    # same order as bm: same indices
        idx = {f.index for f in keep}
        bmesh.ops.delete(h, geom=[f for f in h.faces if f.index not in idx], context='FACES')
        bmesh.ops.delete(h, geom=[v for v in h.verts if not v.link_faces], context='VERTS')
        if len(h.verts) >= 4:
            parts.append(h)
        else:
            h.free()
    bm.free()
    return parts


def _size(bm):
    xs = [v.co for v in bm.verts]
    return max(max(c[k] for c in xs) - min(c[k] for c in xs) for k in range(3))


def _centroid(bm):
    n = len(bm.verts)
    return Vector([sum(v.co[k] for v in bm.verts) / n for k in range(3)])


def fracture(prof):
    """the bowl broken like crystal: straight cracks (planes) in every direction, pieces of all sizes, curved like the
    wall they came from; the bottom of the bowl stays on the stem with a pointed, jagged top. Fixed seed: every
    machine of the render builds exactly the same pieces."""
    import random
    rnd = random.Random(14)
    me = solid_sweep("BowlFrac", prof, steps=160)
    bm = _bm_from_me(me)
    bpy.data.meshes.remove(me)
    pieces = [bm]
    # 1) three tilted cracks low on the bowl: they give the remnant its jagged top
    for k in range(3):
        a = 2 * math.pi * k / 3 + rnd.uniform(-0.4, 0.4)
        tilt = rnd.uniform(0.20, 0.40)
        no = Vector((math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt), math.cos(tilt)))
        co = Vector((0, 0, rnd.uniform(0.108, 0.122)))
        nxt = []
        for p in pieces:
            nxt += _cut(p, co, no)
            p.free()
        pieces = nxt
        nxt = []
        for p in pieces:
            p.faces.index_update()
            nxt += _split_loose(p)
        pieces = nxt
    low = min(range(len(pieces)), key=lambda i: min(v.co.z for v in pieces[i].verts))
    remnant = pieces.pop(low)
    # 2) the rest cracks again and again: always the biggest piece first (no big half-bowl left), then a few extra
    #    cracks at random for small splinters (sizes vary)
    def crack(p):
        c = _centroid(p) + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.004
        ang = rnd.uniform(0, 2 * math.pi)
        el = rnd.uniform(-0.9, 0.9)
        no = Vector((math.cos(ang) * math.cos(el), math.sin(ang) * math.cos(el), math.sin(el)))
        halves = _cut(p, c, no)
        p.free()
        out = []
        for h in halves:
            h.faces.index_update()
            out += _split_loose(h)
        return out
    done = pieces
    while len(done) < 48:
        done.sort(key=_size)
        if _size(done[-1]) < 0.024:
            break
        done += crack(done.pop())
    for _ in range(10):
        done.sort(key=_size)
        done += crack(done.pop(rnd.randrange(len(done) // 3, len(done))))
    out = []
    for i, p in enumerate([remnant] + done):
        bmesh.ops.recalc_face_normals(p, faces=p.faces)
        m = bpy.data.meshes.new("Cup" if i == 0 else f"ShardMe_{i}")
        p.to_mesh(m)
        p.free()
        for f in m.polygons:
            f.use_smooth = True
        try:                                          # curved wall smooth, crack faces sharp
            m.set_sharpness_by_angle(angle=math.radians(35))
        except AttributeError:
            pass
        out.append(m)
    return out


def _chip_mesh(name, i):
    """a tiny flat irregular splinter (1.5-4 mm), placed on the bowl wall where it comes from"""
    import random
    rnd = random.Random(1400 + i)
    a = rnd.uniform(0, 2 * math.pi)
    z = rnd.uniform(0.125, RIM_Z - 0.003)
    rr = 0.040
    base = Vector((rr * math.cos(a), rr * math.sin(a), z))
    t = Vector((-math.sin(a), math.cos(a), 0))
    up = Vector((0, 0, 1))
    nrm = Vector((math.cos(a), math.sin(a), 0)) * WALL
    sz = rnd.uniform(0.0015, 0.004)
    pts = [base + t * (math.cos(k * 2.1 + rnd.uniform(-.4, .4)) * sz) + up * (math.sin(k * 2.1 + rnd.uniform(-.4, .4)) * sz)
           for k in range(3)]
    vs = pts + [p + nrm for p in pts]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
    me.update()
    return me


def _center_piece(s):
    """origin at the piece's own centre (it spins on itself); keeps where it was on the glass"""
    me = s.data
    n = len(me.vertices)
    c = [sum(v.co[k] for v in me.vertices) / n for k in range(3)]
    for v in me.vertices:
        v.co.x -= c[0]; v.co.y -= c[1]; v.co.z -= c[2]
    s["c"] = c
    s["a"] = math.atan2(c[1], c[0])
    s["sz"] = max(max(v.co[k] for v in me.vertices) - min(v.co[k] for v in me.vertices) for k in range(3))
    s.rotation_mode = 'QUATERNION'


def throw(s, dt):
    """one piece dt seconds after the break: outward along the oval + up, gravity, lands on the base and stays
    there in a random attitude (on its back, on its side...), small pieces go further"""
    import random
    rnd = random.Random(s.name)
    c = Vector(s["c"])
    a = s["a"] + rnd.uniform(-0.35, 0.35)
    small = 1.0 - min(1.0, s["sz"] / 0.05)
    v = (0.10 + 0.10 * abs(math.cos(2 * s["a"])) + rnd.uniform(0.0, 0.08)) * (1.0 + 0.8 * small)
    vz = rnd.uniform(0.12, 0.45)
    # final attitude: a curved piece of wall ends up lying flat (on its outer or inner face), a few tilted
    radial = Vector((math.cos(s["a"]), math.sin(s["a"]), 0.0))
    down = Vector((0, 0, -1)) if rnd.random() < 0.6 else Vector((0, 0, 1))
    wob = Quaternion(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized() if True else (1, 0, 0),
                     rnd.uniform(0.0, 0.35) if rnd.random() < 0.8 else rnd.uniform(0.6, 1.2))
    yaw = rnd.uniform(-math.pi, math.pi)
    q_end = Quaternion((0, 0, 1), yaw) @ wob @ radial.rotation_difference(down)
    me = s.data
    rest = GROUND - min((q_end @ v.co).z for v in me.vertices) + 0.0002
    t_land = (vz + math.sqrt(vz * vz + 2 * 9.81 * max(0.0, c.z - rest))) / 9.81
    tf = min(dt, t_land)
    slide = 0.0
    if dt > t_land:                                   # after landing: a short slide, then still
        slide = min(dt - t_land, 0.06) * v * 0.5
    rr = min(v * tf + slide, 0.055 + 0.06 * small + rnd.uniform(0, 0.04))   # spread out, not a heap
    z = c.z + vz * tf - 0.5 * 9.81 * tf * tf if dt < t_land else rest
    x, y = c.x + math.cos(a) * rr, c.y + math.sin(a) * rr
    r = math.hypot(x, y)
    if r > 0.115:                                     # stays on the base (front edge at 0.13)
        x, y = x * 0.115 / r, y * 0.115 / r
    s.location = (x, y, max(z, rest))
    land = min(1.0, tf / t_land)
    s.rotation_quaternion = Quaternion().slerp(q_end, land)


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
    shard = principled("BL_Shard", **{"Base Color": (0.66, 0.76, 0.90, 1), "Transmission Weight": 1.0, "Roughness": 0.12,
                                     "IOR": 1.56})     # a touch of tint: broken pieces lying on the white base stay visible
    bench = principled("BL_Bench", **{"Base Color": (0.55, 0.57, 0.60, 1), "Roughness": 0.45})
    back = principled("BL_Back", **{"Base Color": (0.20, 0.23, 0.27, 1), "Roughness": 0.8})
    black = principled("BL_Black", **{"Base Color": (0.01, 0.01, 0.012, 1), "Roughness": 1.0})

    obj(sc, "Foot", solid_sweep("Foot", FOOT, steps=128), crystal)
    prof = bowl_profile()
    obj(sc, "Bowl", solid_sweep("Bowl", prof, steps=160), crystal)              # intact, deformed by the voice
    pieces = fracture(prof)
    remnant = pieces.pop(0)
    obj(sc, "Cup", remnant, crystal)                                            # jagged bottom of the bowl, stays on the stem
    for i, me in enumerate(pieces):
        s = obj(sc, f"Shard_{i}", me, shard)
        _center_piece(s)
    for i in range(N_CHIPS):                                                    # glitter: tiny chips thrown further
        s = obj(sc, f"Chip_{i}", _chip_mesh(f"Chip_{i}", i), shard)
        _center_piece(s)

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
    for s in sc.objects:
        if "c" not in s:
            continue
        s.hide_render = s.hide_viewport = not broken
        if broken:
            throw(s, min(tb, 260.0) / 1000.0)
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
