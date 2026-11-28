"""Explainer series (Instagram, Breakpoint Lab · Explainers): the forces on a crate on an incline, played by characters.

Each force is a toy-like capsule character with a fixed colour (the same in every episode):
  yellow = applied force F (pulls the rope up the slope), red = friction f (pulls down the slope),
  blue = normal force N (the surface pushing back, perpendicular to the slope, squeezed under the crate),
  green = weight mg (hangs straight down, vertically, below the plank).
Physics is drawn right: N is perpendicular to the slope, mg vertical, F and f along the slope.

    blender -b -P tools/blender/explainer_incline.py -- --out work/stills --shots wide,crate,faces --samples 96
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

TH = math.radians(30)                         # slope angle
U = Vector((math.cos(TH), 0, math.sin(TH)))   # up the slope
N = Vector((-math.sin(TH), 0, math.cos(TH)))  # out of the slope
PLANK_T = 0.28
CRATE = 0.78
BLUE_T = 0.32                                  # the squeezed blue character between plank and crate

COLS = {
    "yellow": (0.90, 0.55, 0.02, 1),
    "red": (0.72, 0.05, 0.03, 1),
    "blue": (0.03, 0.18, 0.75, 1),
    "green": (0.07, 0.42, 0.07, 1),
}


# ---------------------------------------------------------------- helpers
def _set(b, k, v):
    if k in b.inputs:
        b.inputs[k].default_value = v


def mat(name, **kw):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        _set(b, k, v)
    return m


def toy(name, col):
    """glossy vinyl toy, slight roughness variation so the shine is never constant"""
    m = mat(name, **{"Base Color": col, "Roughness": 0.32, "Coat Weight": 0.35, "Coat Roughness": 0.12,
                     "Subsurface Weight": 0.08, "Subsurface Radius": Vector((0.2, 0.1, 0.05))})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 6.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.26
    mr.inputs["To Max"].default_value = 0.40
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    return m


def wood_mat():
    m = mat("Wood", **{"Roughness": 0.62})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.inputs["Scale"].default_value = 3.0
    wv.inputs["Distortion"].default_value = 5.0
    wv.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.46, 0.28, 0.12, 1)
    ramp.color_ramp.elements[1].color = (0.55, 0.35, 0.17, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def _fin(o, m, smooth=True):
    o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return o


def ball(loc, r, m, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r, location=loc)
    o = bpy.context.object
    o.scale = scale
    return _fin(o, m)


def seg(a, b, r, m, caps=True):
    """a limb / rope: a cylinder from a to b with round ends"""
    a, b = Vector(a), Vector(b)
    v = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=v.length, location=(a + b) / 2)
    o = bpy.context.object
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    _fin(o, m)
    if caps:
        ball(a, r, m)
        ball(b, r, m)
    return o


def box(loc, size, m, rot=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        md = o.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = 3
    return _fin(o, m, smooth=False)


def capsule(center, axis, length, r, m, flat=1.0):
    """smooth body: a UV sphere whose two halves are pulled apart along the axis"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=r)
    o = bpy.context.object
    for v in o.data.vertices:
        v.co.z += (length / 2) * (1 if v.co.z > 0 else -1)
        v.co.y *= flat
    o.location = center
    o.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    md = o.modifiers.new("Sub", 'SUBSURF')
    md.levels = md.render_levels = 1
    return _fin(o, m)


# ---------------------------------------------------------------- characters
def face(c, up, fwd, side, r, mood, mats, gaze=0.0, lid=None):
    """eyes, pupils, brows and mouth on the front of a body (fwd = towards the camera);
    gaze < 0 looks towards -side, > 0 towards +side; mood "strain" = eyes squeezed shut (effort)"""
    up, fwd, side = Vector(up).normalized(), Vector(fwd).normalized(), Vector(side).normalized()
    look = {"angry": -0.25, "tired": -0.5, "worried": 0.3, "strain": 0.0}[mood]
    for s in (-1, 1):
        e = c + up * r * 0.25 + fwd * r * 0.90 + side * s * r * 0.38
        if mood == "strain":                                # squinting with effort
            ball(e, r * 0.30, mats["eye"], scale=(1, 0.6, 0.5))
            ball(e + fwd * r * 0.14 + side * gaze * r * 0.13, r * 0.10, mats["pupil"], scale=(1, 1, 0.8))
        else:
            ball(e, r * 0.30, mats["eye"], scale=(1, 0.6, 1.15))
            ball(e + fwd * r * 0.14 + up * r * look * 0.12 + side * gaze * r * 0.13, r * 0.13, mats["pupil"])
        if lid is not None and mood in ("angry", "strain", "tired"):   # upper lid, body colour: a frown, not stuck-on eyes
            drop = {"angry": 0.10, "strain": 0.06, "tired": 0.02}[mood]
            ball(e + up * r * (0.20 - drop) + fwd * r * 0.03, r * 0.33, lid, scale=(1.08, 0.66, 0.55))
        # brows: angry = inner end down, tired/worried = inner end up
        tilt = {"angry": -1.6, "tired": 0.8, "worried": 1.2, "strain": -1.2}[mood] * s
        bc = e + up * r * 0.44 + fwd * r * 0.06
        a = bc - side * r * 0.20 + up * tilt * r * 0.12
        b = bc + side * r * 0.20 - up * tilt * r * 0.12
        if s < 0:
            a, b = b, a
        seg(a, b, r * 0.075, mats["pupil"])
    mc = c - up * r * 0.30 + fwd * r * 0.97
    if mood in ("angry", "strain"):                         # gritted teeth
        ball(mc, r * 0.28, mats["mouth"], scale=(1.0, 0.45, 0.5))
        ball(mc + fwd * r * 0.06, r * 0.22, mats["eye"], scale=(1.0, 0.35, 0.25))
    elif mood == "worried":
        ball(mc, r * 0.14, mats["mouth"], scale=(1.0, 0.45, 1.3))
    else:
        seg(mc - side * r * 0.16 - up * r * 0.03, mc + side * r * 0.16 - up * r * 0.03, r * 0.05, mats["mouth"])


def character(col, feet, lean, hands, mood, mats, height=0.36, r=0.17, flat=1.0, gaze=0.0):
    """feet: two points on the ground; lean: body axis (world); hands: two world points"""
    m = mats[col]
    up = Vector(lean).normalized()
    fc = (Vector(feet[0]) + Vector(feet[1])) / 2
    hip = fc + up * 0.20
    c = hip + up * (height / 2 + r * 0.6)
    capsule(c, up, height, r, m, flat)
    side = Vector((1, 0, 0))
    side = (side - up * side.dot(up)).normalized()
    fwd = up.cross(side).normalized()
    if fwd.y > 0:
        fwd = -fwd
    pull = Vector((up.x, up.y, 0))                  # knees bend against the lean (towards the load)
    knee_dir = -pull.normalized() if pull.length > 0.05 else fwd
    for s, f in zip((-1, 1), feet):
        h = hip + side * s * r * 0.45
        k = (h + Vector(f)) / 2 + knee_dir * r * 0.45
        seg(h, k, r * 0.24, m)
        seg(k, f, r * 0.24, m)
        ball(Vector(f) + fwd * r * 0.12, r * 0.30, m, scale=(1.1, 1.4, 0.7))
    for s, hd in zip((-1, 1), hands):
        sh = c + up * height * 0.18 + side * s * r * 0.85
        el = (sh + Vector(hd)) / 2 - up * r * 0.35 + fwd * r * 0.15 * s
        seg(sh, el, r * 0.20, m)
        seg(el, hd, r * 0.20, m)
        ball(hd, r * 0.30, m)
    face(c + up * height * 0.12, up, fwd, side, r, mood, mats, gaze, lid=m)
    return c


FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "engine", "fonts", "Poppins-Bold.ttf")


def _group(objs, loc):
    """an upright empty that carries a label and its vector mark: moved as one, never tilted"""
    e = bpy.data.objects.new("grp", None)
    e.location = loc
    bpy.context.scene.collection.objects.link(e)
    bpy.context.view_layer.update()
    for o in objs:
        o.parent = e
        o.matrix_parent_inverse = e.matrix_world.inverted()
    return e


def label(text, loc, m, size=0.38, vec=False, font=None):
    """a name facing the camera (+ the vector arrow over it); returns the upright group"""
    cu = bpy.data.curves.new(text, type='FONT')
    cu.body = text
    cu.size = size
    cu.extrude = 0.03
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    try:
        cu.font = bpy.data.fonts.load(font or FONT, check_existing=True)
    except RuntimeError:
        pass
    o = bpy.data.objects.new(text, cu)
    col = m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[:]
    lm = mat("L_" + m.name, **{"Base Color": col, "Emission Color": col, "Emission Strength": 0.9, "Roughness": 0.5})
    o.data.materials.append(lm)
    o.location = loc
    o.rotation_euler = (math.pi / 2, 0, 0)     # faces the camera (-y)
    bpy.context.scene.collection.objects.link(o)
    parts = [o]
    if vec:                                     # the vector arrow over the letter
        a = Vector(loc) + Vector((-size * 0.22, -0.02, size * 0.46))
        b = a + Vector((size * 0.40, 0, 0))
        parts.append(seg(a, b, size * 0.035, lm, caps=False))
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=size * 0.09, radius2=0, depth=size * 0.2,
                                        location=b + Vector((size * 0.08, 0, 0)), rotation=(0, math.pi / 2, 0))
        parts.append(_fin(bpy.context.object, lm))
    return _group(parts, loc)


def arrow(start, d, length, m, r=0.035):
    """force arrow: shaft + head; returns its objects and its tip"""
    d = Vector(d).normalized()
    tip = start + d * length
    objs = [seg(start, tip - d * 0.20, r, m, caps=False)]
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.10, radius2=0.0, depth=0.24, location=tip - d * 0.12)
    o = bpy.context.object
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    objs.append(_fin(o, m))
    return objs, tip


def logo_on_plank(s_mid, size, front_y):
    """BREAKPOINT (dark) LAB (gold) on the plank's front face, along the slope: the channel's logo in every shot"""
    cu = bpy.data.curves.new("logo", type='FONT')
    cu.body = "BREAKPOINT LAB"
    cu.size = size
    cu.extrude = 0.004
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    try:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError:
        pass
    dark = mat("LogoDark", **{"Base Color": (0.02, 0.02, 0.025, 1), "Roughness": 0.6})
    gold = mat("LogoGold", **{"Base Color": (0.80, 0.52, 0.02, 1), "Roughness": 0.5})
    o = bpy.data.objects.new("logo", cu)
    o.data.materials.append(dark)
    o.data.materials.append(gold)
    for k in range(len("BREAKPOINT "), len("BREAKPOINT LAB")):
        cu.body_format[k].material_index = 1
    o.location = U * s_mid + Vector((0, front_y, 0))
    o.rotation_euler = (Matrix.Rotation(-TH, 4, 'Y') @ Matrix.Rotation(math.pi / 2, 4, 'X')).to_euler()
    bpy.context.scene.collection.objects.link(o)
    return o


# ---------------------------------------------------------------- scene
def on_plank(s, h=0.0):
    return U * s + N * (PLANK_T / 2 + h)


S = {}          # what set_pose needs: pivot, crate centre, labels to keep upright, materials, dynamic objects


def build(res=(1080, 1920)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    mats = {k: toy(k, v) for k, v in COLS.items()}
    mats["eye"] = mat("Eye", **{"Base Color": (0.92, 0.92, 0.90, 1), "Roughness": 0.15, "Coat Weight": 0.5})
    mats["pupil"] = mat("Pupil", **{"Base Color": (0.02, 0.02, 0.025, 1), "Roughness": 0.1})
    mats["mouth"] = mat("Mouth", **{"Base Color": (0.10, 0.02, 0.02, 1), "Roughness": 0.4})
    mats["ink"] = mat("Ink", **{"Base Color": (0.06, 0.07, 0.09, 1), "Roughness": 0.5})
    grey = mat("Plank", **{"Base Color": (0.62, 0.63, 0.65, 1), "Roughness": 0.55})
    studio = mat("Studio", **{"Base Color": (0.55, 0.56, 0.58, 1), "Roughness": 0.8})
    rope = mat("Rope", **{"Base Color": (0.55, 0.42, 0.25, 1), "Roughness": 0.85})
    wood = wood_mat()
    cc = on_plank(0.0, BLUE_T + CRATE / 2)

    # floor + backdrop (fixed)
    box((0, 3, -2.50), (40, 40, 0.1), studio)
    box((0, 4.5, 6), (40, 0.1, 16), studio)

    before = set(bpy.data.objects)
    # ---- everything tied to the ramp (turns with it, around the crate's centre)
    box((0, 0, 0), (6.0, 1.1, PLANK_T), grey, rot=(0, -TH, 0), bevel=0.02)
    logo_on_plank(1.05, 0.15, -0.553)
    bc = on_plank(0.0, BLUE_T / 2)
    capsule(bc, U, 0.50, BLUE_T / 2, mats["blue"])
    for s in (-0.30, 0.30):
        hand = bc + U * s * 1.05 + N * (BLUE_T / 2 - 0.02) + Vector((0, -0.17, 0))
        seg(bc + U * s * 0.8 + Vector((0, -0.08, 0)), hand, 0.04, mats["blue"])
        ball(hand, 0.06, mats["blue"], scale=(1.3, 1.3, 0.6))
    face(bc, N, Vector((0, -1, 0)), U, BLUE_T / 2, "tired", mats, lid=mats["blue"])
    box(cc, (CRATE, CRATE, CRATE), wood, rot=(0, -TH, 0), bevel=0.015)
    fy = -CRATE / 2 - 0.02
    for a, b in (((-1, -1), (1, -1)), ((-1, 1), (1, 1)), ((-1, -1), (-1, 1)), ((1, -1), (1, 1)), ((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
        pa = cc + U * a[0] * CRATE * 0.44 + N * a[1] * CRATE * 0.44 + Vector((0, fy, 0))
        pb = cc + U * b[0] * CRATE * 0.44 + N * b[1] * CRATE * 0.44 + Vector((0, fy, 0))
        v = pb - pa
        o = box((pa + pb) / 2, (0.075, 0.03, v.length), wood)
        o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    fy1, fy2 = on_plank(1.30), on_plank(1.50)
    lean_y = (U * 0.55 + Vector((0, 0, 1))).normalized()
    hy = (on_plank(1.17, 0.60), on_plank(1.21, 0.63))
    character("yellow", (fy1 + Vector((0, -0.12, 0)), fy2 + Vector((0, 0.12, 0))), lean_y,
              (hy[0] + Vector((0, -0.07, 0)), hy[1] + Vector((0, 0.07, 0))), "angry", mats, gaze=-1.0)
    seg(cc + U * CRATE / 2, (hy[0] + hy[1]) / 2 + U * 0.25, 0.018, rope, caps=False)
    fr1, fr2 = on_plank(-1.40), on_plank(-1.24)
    lean_r = (-U * 0.55 + Vector((0, 0, 1))).normalized()
    base = cc - U * (CRATE / 2 + 0.03) - N * (CRATE / 2 - 0.12)
    character("red", (fr1 + Vector((0, -0.12, 0)), fr2 + Vector((0, 0.12, 0))), lean_r,
              (base + Vector((0, -0.16, 0)), base + Vector((0, 0.10, 0)) + N * 0.06), "strain", mats, gaze=1.0)
    ay = Vector((0, -0.62, 0))
    _, tF = arrow(cc + ay, U, 1.05, mats["yellow"])
    _, tf = arrow(cc + ay, -U, 0.62, mats["red"])
    tilted = set(bpy.data.objects) - before

    pivot = bpy.data.objects.new("pivot", None)
    pivot.location = cc
    sc.collection.objects.link(pivot)
    bpy.context.view_layer.update()
    for o in tilted:
        if o.parent is None:
            o.parent = pivot
            o.matrix_parent_inverse = pivot.matrix_world.inverted()

    # names of F and f: upright, follow their arrow tips
    lF = label("F", tF + U * 0.16 + N * 0.16, mats["yellow"], vec=True)
    lf = label("f", tf - U * 0.16 + N * 0.22, mats["red"], vec=True)
    S["follow"] = [(lF, lF.location - cc), (lf, lf.location - cc)]

    # ---- fixed: gravity does not turn. Green hangs from the weight arrow, well below the plank at any angle
    top = Vector((cc.x, -0.62, cc.z))
    bot = Vector((cc.x, -0.62, cc.z - 2.60))
    seg(top, bot, 0.04, mats["green"], caps=False)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.11, radius2=0.0, depth=0.26, location=bot - Vector((0, 0, 0.13)),
                                    rotation=(math.pi, 0, 0))
    _fin(bpy.context.object, mats["green"])
    gh = Vector((cc.x, -0.62, cc.z - 1.45))
    gc = gh - Vector((0, 0, 0.55))
    character("green", (gc + Vector((-0.10, 0, -0.45)), gc + Vector((0.12, 0, -0.43))), (0, 0, 1),
              (gh + Vector((-0.04, -0.03, 0.06)), gh + Vector((0.04, -0.03, -0.04))), "worried", mats)
    label("mg", bot + Vector((0.34, -0.05, -0.10)), mats["green"])
    S["lN"] = label("N", cc, mats["blue"], vec=True)
    S["lth"] = label("θ", cc, mats["ink"], size=0.30, font=FONT.replace("Poppins-Bold", "DejaVuSans-Bold"))
    S.update(pivot=pivot, cc=cc, mats=mats, dyn=[])

    # lights
    for nm, loc, e, size in (("Key", (-3.0, -5.0, 5.0), 700, 2.0), ("Fill", (5.0, -4.0, 2.0), 150, 4.0),
                             ("Rim", (2.0, 3.0, 4.0), 600, 1.5)):
        ld = bpy.data.lights.new(nm, 'AREA')
        ld.energy = e
        ld.size = size
        lo = bpy.data.objects.new(nm, ld)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.5)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(lo)

    wd = bpy.data.worlds.new("W")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.86, 0.88, 1)
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.25
    sc.world = wd

    cam = bpy.data.cameras.new("Cam")
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    shot(sc, "wide")

    r = sc.render
    r.resolution_x, r.resolution_y = res
    r.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 96
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    sc.view_settings.exposure = -0.3
    r.image_settings.file_format = 'JPEG'
    r.image_settings.quality = 92
    set_pose({"th": 30})
    return sc


def _drop_dyn():
    for o in S["dyn"]:
        bpy.data.objects.remove(o, do_unlink=True)
    S["dyn"] = []


def set_pose(p):
    """p["th"] = ramp angle (deg). The ramp and everything on it turn around the crate's centre; the weight stays vertical;
    N stays perpendicular to the ramp and its length is mg cos(theta) (1.2 m for mg); the angle between mg and the
    dashed -N line is theta (the same angle as the ramp)."""
    th = math.radians(float(p["th"]))
    cc, mats = S["cc"], S["mats"]
    R = Matrix.Rotation(-(th - TH), 3, 'Y')
    S["pivot"].rotation_euler = (0, -(th - TH), 0)
    for g, rel in S["follow"]:
        g.location = cc + R @ rel
    _drop_dyn()
    ay = Vector((0, -0.62, 0))
    n = Vector((-math.sin(th), 0, math.cos(th)))
    objs, tN = arrow(cc + ay, n, 1.2 * math.cos(th), mats["blue"])
    S["dyn"] += objs
    S["lN"].location = tN + n * 0.20 + Vector((-0.06, 0, 0.04))
    # dashed -N (the line the weight makes the angle with) and the theta arc between it and mg
    for k in range(5):
        a = cc + ay + Vector((0, -0.005, 0)) - n * (0.12 + 0.17 * k)
        S["dyn"].append(seg(a, a - n * 0.10, 0.014, mats["ink"], caps=False))
    pts = []
    for k in range(25):
        ang = -math.pi / 2 + th * k / 24                      # from straight down towards -N
        pts.append(cc + ay + Vector((0.55 * math.cos(ang), -0.01, 0.55 * math.sin(ang))))
    for a, b in zip(pts, pts[1:]):
        S["dyn"].append(seg(a, b, 0.016, mats["ink"], caps=False))
    mid = -math.pi / 2 + th / 2
    S["lth"].location = cc + ay + Vector((0.80 * math.cos(mid), -0.02, 0.80 * math.sin(mid)))


SHOTS = {                       # camera position, look-at target, lens
    "wide": (lambda cc: (Vector((cc.x + 0.50, -9.0, cc.z + 1.0)), Vector((cc.x + 0.50, 0, cc.z - 0.55)), 45)),
    "crate": (lambda cc: (Vector((cc.x - 0.6, -5.5, cc.z + 0.8)), Vector((cc.x, 0, cc.z - 0.2)), 50)),
    "faces": (lambda cc: (Vector((cc.x - 0.4, -4.6, cc.z + 0.7)), Vector((cc.x - 0.4, 0, cc.z + 0.05)), 50)),
}


def shot(sc, name):
    pos, look, lens = SHOTS[name](S["cc"])
    sc.camera.location = pos
    sc.camera.rotation_euler = (look - pos).to_track_quat('-Z', 'Y').to_euler()
    sc.camera.data.lens = lens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="work/stills")
    ap.add_argument("--shots", default="wide")
    ap.add_argument("--angles", default="30")
    ap.add_argument("--poses", default="")
    ap.add_argument("--range", default="")
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--pct", type=int, default=100)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    sc = build()
    sc.cycles.samples = a.samples
    sc.render.resolution_percentage = a.pct
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    if a.poses:                                   # render.yml: one image per pose of the timeline, named by its key
        import json
        P = json.load(open(a.poses))
        P = P["poses"] if isinstance(P, dict) else P
        lo, hi = (int(x) for x in a.range.split("-")) if a.range else (0, len(P) - 1)
        for p in P[lo:hi + 1]:
            set_pose(p)
            sc.render.filepath = os.path.join(out, p["key"] + ".jpg")
            bpy.ops.render.render(write_still=True)
            print("rendered", p["key"], flush=True)
        return
    for th in a.angles.split(","):               # style checks: a few angles and shots
        set_pose({"th": float(th)})
        for name in a.shots.split(","):
            shot(sc, name)
            sc.render.filepath = os.path.join(out, f"{name}_{th}.jpg")
            bpy.ops.render.render(write_still=True)
            print("rendered", name, th, flush=True)


if __name__ == "__main__" and "--" in sys.argv:
    main()
