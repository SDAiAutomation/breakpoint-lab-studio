"""Breakpoint Lab - episode 013 hero shots in Blender (Cycles): hit the top of a full bottle, the bottom blows out.

Builds the whole scene from code (no .blend to keep in git) and drives every object from one function of time,
like engine/*.html: state(t_ms) gives the pose for a physical time in milliseconds after the strike.

  blender -b -P tools/blender/bottle_scene.py -- --shot strike --out frames/ --frames 0-71 [--preview]
  (inside a running Blender: exec(open(path).read()); build(); set_physical_time(1.5))

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
OUTER = [(0.0005, 0.0), (0.026, 0.0), (0.031, 0.003), (0.033, 0.010), (0.033, 0.125), (0.031, 0.150), (0.022, 0.175),
         (0.015, 0.195), (0.0135, 0.205), (0.0135, 0.214), (0.015, 0.216), (0.015, 0.220), (0.011, 0.220)]
INNER = [(0.011, 0.220), (0.0105, 0.214), (0.0105, 0.200), (0.012, 0.192), (0.019, 0.172), (0.028, 0.149),
         (0.0300, 0.126), (0.0300, 0.012), (0.026, 0.006), (0.0005, 0.007)]
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
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
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


# ---------------------------------------------------------------- build
def build(preview=False, res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    glass = principled("BL_Glass", **{"Base Color": (0.86, 0.95, 0.90, 1), "Transmission Weight": 1.0, "Roughness": 0.02, "IOR": 1.5})
    water = principled("BL_Water", **{"Base Color": (0.80, 0.92, 1.0, 1), "Transmission Weight": 1.0, "Roughness": 0.0, "IOR": 1.33})
    vapour = principled("BL_Bubble", **{"Base Color": (1, 1, 1, 1), "Transmission Weight": 0.5, "Roughness": 0.15, "IOR": 1.0, "Emission Color": (0.85, 0.92, 1.0, 1), "Emission Strength": 0.6})
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
    for i in range(N_SHARDS):                               # the bottom, pre-cut into wedges that fly off at the break
        a0 = 2 * math.pi * i / N_SHARDS
        a1 = a0 + 2 * math.pi / N_SHARDS * 0.985
        s = obj(sc, f"Shard{i}", solid_sweep(f"Shard{i}", base_poly, a0, a1, steps=12), glass)
        s.parent = root
        s["a"] = (a0 + a1) / 2
    wprof = [(0.0005, 0.0072), (0.0258, 0.0065), (0.0298, 0.012), (0.0298, 0.126), (0.0278, 0.149), (0.0255, WATER_TOP),
             (0.0005, WATER_TOP)]
    w = obj(sc, "Water", solid_sweep("Water", wprof), water)
    w.parent = root
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
        b["size"] = 0.0007 + 0.0016 * h2
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
        ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.025, 1)
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
        r.use_persistent_data = True
    try:
        sc.view_settings.view_transform = 'AgX'                 # one colour pipeline for every shot
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    r.film_transparent = False
    set_physical_time(-30.0, sc)
    return sc


# ---------------------------------------------------------------- state(t_ms): the one place where motion is defined
def set_physical_time(t, sc=None, cam_k=0.0):
    """t = physical time in ms after the strike (negative: mallet still coming down)"""
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    # mallet: falls onto the mouth (top of glass at 0.220 m), rebounds a little after the hit
    if t < 0:
        z = 0.220 + 0.03 + 0.0012 * (-t) ** 1.0
    else:
        z = 0.220 + 0.03 - 0.0018 * smooth(0, 0.6, t) + 0.004 * smooth(1.0, 12.0, t)
    ob["Mallet"].location = (0, 0, z)
    # bottle pushed down ~1.5 mm by the strike (the water lags behind: that is the pressure drop)
    push = 0.0015 * smooth(0, 0.6, t)
    ob["BottleRig"].location = (0, 0, -push * (1 - smooth(4, 20, t)))
    lag = 0.0012 * smooth(0, 0.6, t) * (1 - smooth(1.5, 3.2, t))
    wdrop = 0.5 * 9.81 * (k_w := max(0.0, t - T_BREAK - 0.5) / 1000.0) ** 2 + 0.9 * k_w   # water plug pushed out of the hole
    ob["Water"].location = (0, 0, lag - wdrop)
    # bubbles: grow from T_BUBBLE, collapse at T_COLLAPSE (+ small random delay)
    for i in range(60):
        b = ob[f"Bubble{i}"]
        d = b["delay"]
        g = smooth(T_BUBBLE + d, T_BUBBLE + d + 1.2, t) * (1 - smooth(T_COLLAPSE + d * 0.3, T_COLLAPSE + d * 0.3 + 0.25, t))
        s = max(1e-5, b["size"] * g)
        b.scale = (s, s, s * 0.8)
        b.hide_render = g < 0.02
        b.hide_viewport = b.hide_render
    # the bottom comes off in shards after the collapse
    k = max(0.0, t - T_BREAK)
    for i in range(N_SHARDS):
        s = ob[f"Shard{i}"]
        a = s["a"]
        h = (math.sin(i * 3.7 + 1.1) * 4375.85) % 1.0
        v = (0.8 + 1.0 * h) * k / 1000.0                     # m/s * ms -> m
        drop = 0.5 * 9.81 * (k / 1000.0) ** 2 + 1.2 * k / 1000.0
        s.location = (math.cos(a) * v, math.sin(a) * v, -drop)
        s.rotation_euler = (0.08 * h * k * math.sin(a), 0.08 * h * k * math.cos(a), 0.03 * k * (h - 0.5))
    # camera: low, slightly below the bottom to see the base, slow push-in on cam_k (0..1)
    cam = ob["Cam"]
    d = 1.30 - 0.10 * cam_k                               # 85 mm: further back, same framing
    cam.location = (math.sin(0.35) * d, -math.cos(0.35) * d, 0.10)
    look = (0.0, 0.0, 0.125)
    dx, dy, dz = look[0] - cam.location[0], look[1] - cam.location[1], look[2] - cam.location[2]
    cam.rotation_euler = (math.atan2(math.hypot(dx, dy), -dz), 0, math.atan2(dy, dx) - math.pi / 2)


# ---------------------------------------------------------------- shots
# a shot maps video frames to physical time: strike = slow motion of the hit (-2 ms .. 12 ms over 2.4 s)
SHOTS = {   # piecewise map: video fraction u -> physical ms (very slow around the bubbles, faster for the fall)
    "strike": {"frames": 90, "map": [(0.0, -2.0), (0.15, 0.0), (0.62, 4.0), (1.0, 60.0)]},
    "hook": {"frames": 66, "map": [(0.0, -1.0), (0.5, 3.0), (1.0, 30.0)]},
}


def shot_time(S, u):
    m = S["map"]
    for (u0, t0), (u1, t1) in zip(m, m[1:]):
        if u <= u1:
            return t0 + (t1 - t0) * (u - u0) / (u1 - u0)
    return m[-1][1]


def render_shot(shot, out, frames=None, preview=False):
    sc = build(preview=preview)
    S = SHOTS[shot]
    n = S["frames"]
    lo, hi = (0, n - 1) if not frames else frames
    for f in range(lo, hi + 1):
        u = f / max(1, n - 1)
        set_physical_time(shot_time(S, u), sc, cam_k=u)
        sc.render.filepath = f"{out}/{shot}_{f:04d}.png"
        bpy.ops.render.render(write_still=True, scene=sc.name)


if __name__ == "__main__" and "--" in sys.argv:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default="strike")
    ap.add_argument("--out", default="frames")
    ap.add_argument("--frames", default="")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    fr = tuple(int(x) for x in a.frames.split("-")) if a.frames else None
    render_shot(a.shot, a.out, fr, a.preview)
