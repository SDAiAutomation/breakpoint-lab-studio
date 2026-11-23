"""Breakpoint Lab - episode 013 hero shots in Blender (Cycles): hit the top of a full bottle, the bottom blows out.

Builds the whole scene from code (no .blend to keep in git) and drives every object from one function of time,
like engine/*.html: state(t_ms) gives the pose for a physical time in milliseconds after the strike.

  blender -b -P tools/blender/bottle_scene.py -- --poses work/timeline.json --out work/bscene --range 0-19
  The poses come from engine/bottle.html (render.js timeline): one image per different pose, named <key>.jpg.

Physics shown (Pan, Kiyama et al., PNAS 114, 2017): the strike pushes the bottle down faster than the water can follow,
the pressure at the bottom drops below the vapour pressure, cavitation bubbles grow at the bottom and collapse,
and the collapse shock breaks the bottom off. Timings in ms are illustrative (labelled "Simulated").
"""
import math
import sys

import bmesh
import bpy

SCENE = "BL_bottle"
CUT = 0.028                      # height (m) of the crack ring where the bottom comes off
OUTER = [(0.0, 0.0), (0.026, 0.0), (0.031, 0.003), (0.033, 0.010), (0.033, 0.125), (0.031, 0.150), (0.022, 0.175),
         (0.015, 0.195), (0.0135, 0.205), (0.0135, 0.214), (0.015, 0.216), (0.015, 0.220), (0.011, 0.220)]
INNER = [(0.011, 0.220), (0.0105, 0.214), (0.0105, 0.200), (0.012, 0.192), (0.019, 0.172), (0.028, 0.149),
         (0.0300, 0.126), (0.0300, 0.012), (0.026, 0.006), (0.0, 0.007)]
WATER_TOP = 0.155
N_SHARDS = 9
T_HIT, T_BUBBLE, T_COLLAPSE, T_BREAK = 0.0, 0.4, 2.6, 3.2     # ms


# ---------------------------------------------------------------- helpers
def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def clip_profile(prof, z0, z1):
    """part of a closed (r, z) profile polygon between z0 and z1 (polygon clipping on z)"""
    def clip(poly, keep, zc):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            ia, ib = keep(a[1]), keep(b[1])
            if ia:
                out.append(a)
            if ia != ib:
                k = (zc - a[1]) / (b[1] - a[1])
                out.append((a[0] + k * (b[0] - a[0]), zc))
        return out
    p = clip(prof, lambda z: z >= z0, z0)
    return clip(p, lambda z: z <= z1, z1)


def solid_sweep(name, poly, a0=0.0, a1=2 * math.pi, steps=96):
    """sweep a closed (r, z) polygon around Z between angles a0..a1 (closed caps when it is a sector)"""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((r * math.cos(a0), r * math.sin(a0), z)) for r, z in poly]
    full = abs(a1 - a0 - 2 * math.pi) < 1e-6
    if full:                                               # closed ring: sweep the outline only, no caps
        es = [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
        bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=a1 - a0, steps=steps, use_merge=True)
    else:                                                  # sector: sweep the face, both ends capped
        face = bm.faces.new(vs)
        bmesh.ops.spin(bm, geom=[face] + vs + list(face.edges), cent=(0, 0, 0), axis=(0, 0, 1),
                       angle=a1 - a0, steps=steps, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-5)   # closes the sweep seam (no vertical line)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def obj(sc, name, me, mat=None):
    o = bpy.data.objects.new(name, me)
    o["bb"] = name                                         # lookup key: Blender may rename on a clash (Water.001)
    sc.collection.objects.link(o)
    if mat:
        me.materials.append(mat)
    return o


def principled(name, **kw):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


def water_mesh(fill):
    """water column for a fill level (1 = full to WATER_TOP, 0.5 = half the height of water)"""
    name = f"Water_{int(round(fill * 100))}"
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    top = 0.0072 + (WATER_TOP - 0.0072) * fill
    prof = [(0.0, 0.0068), (0.0262, 0.0061), (0.0302, 0.012)]
    for r, z in [(0.0302, 0.126), (0.0282, 0.149)]:
        if z < top:
            prof.append((r, z))
    r_top = 0.0302 if top <= 0.126 else (0.0282 if top <= 0.149 else 0.0259)
    prof += [(r_top, top), (0.0, top)]
    me = solid_sweep(name, prof)
    for mat in bpy.data.materials:
        if mat.name == "BL_Water":
            me.materials.append(mat)
    return me


# ---------------------------------------------------------------- build
def build(preview=False, res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    glass = principled("BL_Glass", **{"Base Color": (0.30, 0.52, 0.98, 1), "Transmission Weight": 1.0, "Roughness": 0.02, "IOR": 1.5})
    water = principled("BL_Water", **{"Base Color": (0.80, 0.92, 1.0, 1), "Transmission Weight": 1.0, "Roughness": 0.0, "IOR": 1.33})
    vapour = principled("BL_Bubble", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.0, "IOR": 0.752, "Emission Strength": 0.0})
    rubber = principled("BL_Rubber", **{"Base Color": (0.035, 0.035, 0.04, 1), "Roughness": 0.55})
    wood = principled("BL_Wood", **{"Base Color": (0.55, 0.36, 0.18, 1), "Roughness": 0.5})
    steel = principled("BL_Steel", **{"Base Color": (0.85, 0.86, 0.88, 1), "Metallic": 0.0, "Roughness": 0.5})   # light, not mirror: no black blob under the glass
    bench = principled("BL_Bench", **{"Base Color": (0.55, 0.57, 0.60, 1), "Roughness": 0.45})
    back = principled("BL_Back", **{"Base Color": (0.20, 0.23, 0.27, 1), "Roughness": 0.8})
    black = principled("BL_Black", **{"Base Color": (0.005, 0.005, 0.005, 1), "Roughness": 1.0})

    prof = OUTER + INNER
    root = bpy.data.objects.new("BottleRig", None)          # the bottle moves down a little when hit
    root["bb"] = "BottleRig"
    sc.collection.objects.link(root)
    top = obj(sc, "BottleTop", solid_sweep("BottleTop", clip_profile(prof, CUT, 1.0)), glass)
    top.parent = root
    base_poly = clip_profile(prof, -1.0, CUT)
    bse = obj(sc, "Base", solid_sweep("Base", base_poly), glass)   # intact bottom; swapped for the shards at the break
    bse.parent = root
    for i in range(N_SHARDS):                               # the bottom, pre-cut into wedges that fly off at the break
        a0 = 2 * math.pi * i / N_SHARDS
        a1 = a0 + 2 * math.pi / N_SHARDS * 0.985
        s = obj(sc, f"Shard{i}", solid_sweep(f"Shard{i}", base_poly, a0, a1, steps=12), glass)
        s.parent = root
        s["a"] = (a0 + a1) / 2
    w = obj(sc, "Water", water_mesh(1.0), water)
    w.parent = root
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.0, depth=0.0016, location=(0, 0, 0.0008))
    pud = bpy.context.object
    pud.name = "Puddle"
    pud["bb"] = "Puddle"
    for c in pud.users_collection:
        c.objects.unlink(pud)
    sc.collection.objects.link(pud)
    pud.data.materials.append(water)
    bpy.ops.object.shade_smooth()
    # cavitation bubbles: a ring of small vapour pockets on the bottom
    for i in range(60):
        h = (math.sin(i * 12.9898) * 43758.5453) % 1.0
        h2 = (math.sin(i * 78.233) * 12345.678) % 1.0
        r = 0.004 + 0.022 * math.sqrt(h)
        a = i * 2.39996
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=(r * math.cos(a), r * math.sin(a), 0.0085 + 0.004 * h2))
        b = bpy.context.object
        b.name = f"Bubble{i}"
        b["bb"] = f"Bubble{i}"
        for c in b.users_collection:
            c.objects.unlink(b)
        sc.collection.objects.link(b)
        b.data.materials.append(vapour)
        b.parent = root
        b["size"] = 0.0015 + 0.0025 * h2
        b["delay"] = 0.5 * h
    # rubber mallet coming down on the mouth
    mal = bpy.data.objects.new("Mallet", None)
    mal["bb"] = "Mallet"
    sc.collection.objects.link(mal)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.03, depth=0.09, location=(0, 0, 0.0), rotation=(0, math.pi / 2, 0))
    head = bpy.context.object
    head.name = "MalletHead"
    bpy.ops.object.modifier_add(type='BEVEL')
    head.modifiers[-1].width = 0.004
    head.modifiers[-1].segments = 3
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.009, depth=0.30, location=(0.0, 0, 0.15), rotation=(0, 0, 0))
    handle = bpy.context.object
    handle.name = "MalletHandle"
    for part, m in ((head, rubber), (handle, wood)):
        for c in part.users_collection:
            c.objects.unlink(part)
        sc.collection.objects.link(part)
        part.data.materials.append(m)
        part.parent = mal
    # bench, backdrop, steel plate under the bottle
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, -0.004))
    pl = bpy.context.object
    pl.name = "Bench"
    pl.data.materials.append(bench)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.06, depth=0.004, location=(0, 0, -0.002))
    st = bpy.context.object
    st.name = "Plate"
    st.data.materials.append(steel)
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0.6, 1.0), rotation=(math.radians(90), 0, 0))
    bg = bpy.context.object
    bg.name = "Backdrop"
    bg.data.materials.append(back)
    for o in (pl, st, bg):
        for c in o.users_collection:
            c.objects.unlink(o)
        sc.collection.objects.link(o)
    for nm, x in (("FlagL", -0.16), ("FlagR", 0.16)):       # black cards: dark edges on the glass
        me = bpy.data.meshes.new(nm)
        me.from_pydata([(0, -0.12, 0), (0, 0.12, 0), (0, 0.12, 0.45), (0, -0.12, 0.45)], [], [(0, 1, 2, 3)])
        f = obj(sc, nm, me, black)
        f.location = (x, 0.02, 0)
        f.visible_camera = False
        f.hide_render = True

    def area(name, loc, rot, size, e, sy=None):
        l = bpy.data.lights.new(name, 'AREA')
        l.energy = e
        l.shape = 'RECTANGLE'
        l.size = size
        l.size_y = sy or size
        o = bpy.data.objects.new(name, l)
        o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(o)
    area("Key", (-0.35, -0.35, 0.45), (55, 0, -45), 0.5, 35)
    area("RimL", (-0.25, 0.25, 0.15), (90, 0, -145), 0.04, 40, sy=0.5)
    area("RimR", (0.25, 0.25, 0.15), (90, 0, 145), 0.04, 40, sy=0.5)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 85                                          # skill blender-lighting-lookdev: 85-135 mm for products, no distortion
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_World") or bpy.data.worlds.new("BL_World")
    wd.use_nodes = True
    nt = wd.node_tree
    bgn = nt.nodes["Background"]
    if not any(n.type == 'VALTORGB' for n in nt.nodes):   # vertical black -> white gradient: clean edges on glass
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
    r.resolution_percentage = 50 if preview else 100
    r.fps = 30
    if preview:
        r.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    else:
        r.engine = 'CYCLES'                                # skill blender-rendering: Cycles CPU on CI (EEVEE needs a GPU)
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
        sc.view_settings.view_transform = 'AgX'                 # one colour pipeline for every shot
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    r.film_transparent = False
    set_pose({'fill': 1, 'breaks': False, 'raise': 1, 't': -1000, 'cam': 'wide', 'k': 0}, sc)
    return sc


# ---------------------------------------------------------------- pose: the one place where motion is defined
# pose = {fill 0/0.5/1, breaks bool, raise 0..1 (mallet up), t ms after the hit (-1000 = at rest), cam wide|close, k 0..1}
def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    t, fill, brk = float(p["t"]), float(p["fill"]), bool(p["breaks"])
    # mallet: resting on the mouth (top of glass at 0.220 m) when raise = 0, 10 cm higher when raise = 1
    hit = t >= 0
    z = 0.220 + 0.030 + 0.08 * float(p["raise"])
    if hit:
        z += -0.0018 * smooth(0, 0.6, t) + 0.004 * smooth(1.0, 12.0, t) + 0.012 * smooth(20, 400, t)   # small rebound
    ob["Mallet"].location = (0, 0, z)
    # bottle pushed down ~1.5 mm by the hit (the water lags behind: that is the pressure drop)
    push = 0.0015 * smooth(0, 0.6, t) * (1 - smooth(4, 20, t)) if hit else 0.0
    settle = CUT * 0.85 * smooth(T_BREAK + 2, T_BREAK + 60, t) if (brk and hit) else 0.0   # top part drops onto the broken base
    ob["BottleRig"].location = (0, 0, -push)
    ob["BottleTop"].location = (0, 0, -settle)
    # water: hidden when empty; after the break it slumps out into a puddle on the plate
    w = ob["Water"]
    w.hide_render = w.hide_viewport = fill <= 0.01
    if fill > 0.01:
        w.data = water_mesh(fill)
        lag = 0.0012 * smooth(0, 0.6, t) * (1 - smooth(1.5, 3.2, t)) if hit else 0.0
        if brk and hit:
            dt = max(0.0, t - T_BREAK - 0.5) / 1000.0
            fall = 0.5 * 9.81 * dt * dt + 0.8 * dt              # pushed out by the collapse, then gravity
            w.scale = (1, 1, 1)
            w.location = (0, 0, lag - fall)
            w.hide_render = w.hide_viewport = fall > WATER_TOP + 0.01
        else:
            w.scale = (1, 1, 1)
            w.location = (0, 0, lag)
    pd = ob["Puddle"]
    pr = 0.11 * smooth(T_BREAK + 5, T_BREAK + 450, t) if (brk and hit and fill > 0.01) else 0.0
    pd.hide_render = pd.hide_viewport = pr < 0.002
    pd.scale = (max(pr, 1e-4), max(pr, 1e-4), 1)
    # bubbles: only when the bottle breaks (full): grow from T_BUBBLE, collapse at T_COLLAPSE
    for i in range(60):
        b = ob[f"Bubble{i}"]
        d = b["delay"]
        g = smooth(T_BUBBLE + d, T_BUBBLE + d + 1.2, t) * (1 - smooth(T_COLLAPSE + d * 0.3, T_COLLAPSE + d * 0.3 + 0.25, t)) if (brk and hit) else 0.0
        s = max(1e-5, b["size"] * g)
        b.scale = (s, s, s)
        b.hide_render = b.hide_viewport = g < 0.02
    # the bottom comes off in shards that slide out on the plate
    k = max(0.0, t - T_BREAK) if (brk and hit) else 0.0
    broken = brk and hit and t >= T_BREAK
    ob["Base"].hide_render = ob["Base"].hide_viewport = broken
    for i in range(N_SHARDS):
        sh = ob[f"Shard{i}"]
        sh.hide_render = sh.hide_viewport = not broken
        a = sh["a"]
        h = (math.sin(i * 3.7 + 1.1) * 4375.85) % 1.0
        v = (0.6 + 0.8 * h) * min(k, 120) / 1000.0
        sh.location = (math.cos(a) * v, math.sin(a) * v, 0.0)
        tilt = min(1.0, k / 60.0)
        sh.rotation_euler = (0.25 * h * tilt * math.sin(a), 0.25 * h * tilt * math.cos(a), 0.2 * tilt * (h - 0.5))
    # cameras (85 mm). wide: the whole bottle + mallet, bottle in the lower-middle of the frame (text band stays clear);
    # close: the bottom, where the bubbles and the crack are; k = slow push-in
    kk = float(p.get("k", 0))
    if p.get("cam") == "close":
        d, look, elev = 0.78 - 0.06 * kk, (0.0, 0.0, 0.058), 0.09
    else:
        d, look, elev = 1.85, (0.0, 0.0, 0.171), 0.22
    cam = ob["Cam"]
    cam.location = (math.sin(0.30) * d, -math.cos(0.30) * d, elev)
    dx, dy, dz = look[0] - cam.location[0], look[1] - cam.location[1], look[2] - cam.location[2]
    cam.rotation_euler = (math.atan2(math.hypot(dx, dy), -dz), 0, math.atan2(dy, dx) - math.pi / 2)


def render_poses(poses, out, rng=None, samples=None, pct=100):
    import os
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
    ap.add_argument("--poses", required=True, help="JSON list of poses (each with a 'key'), or a timeline.json with 'poses'")
    ap.add_argument("--out", default="bscene")
    ap.add_argument("--range", default="", help="a-b: indexes in the pose list")
    ap.add_argument("--samples", default=None)
    ap.add_argument("--pct", default=100)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    P = json.load(open(a.poses))
    P = P["poses"] if isinstance(P, dict) else P
    rng = tuple(int(x) for x in a.range.split("-")) if a.range else None
    render_poses(P, a.out, rng, a.samples, a.pct)
