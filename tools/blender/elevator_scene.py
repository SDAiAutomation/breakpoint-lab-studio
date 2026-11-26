"""Breakpoint Lab - episode 016 in Blender (Cycles): the cable snaps, does jumping at the last second save you?

Same pipeline as toast_scene.py: the scene is built from code, engine/elevator.html simulates the fall (free fall,
v = sqrt(2 g h); a jump only adds 7 mph upward, Baird 2012), lays out the video and says which pose each frame shows;
this script renders one image per different pose.

  blender -b -P tools/blender/elevator_scene.py -- --poses work/timeline.json --out work/bscene --range 0-17

Realistic version (v2): a Hybrid-III-like crash-test dummy (yellow vinyl, black joints, quadrant targets), a glass-fronted
steel cabin with its sling, guide shoes, hoist ropes and travelling cable, a concrete shaft (formwork joints, stains,
caged work lights, conduit, pit ladder), speed blur on the shaft while the car falls (camera tracks the car), and at the
impact: sparks, debris, a dust burst, cracked glass, the body folding down with a head whiplash.

pose = {zc car floor underside (m), cut rope recoil (m), c crouch 0-1, arm (0 down, 1 up, <0 back), lean 0-1,
        dz rider lift above the car floor (m), s slump 0-1 (folds down to sitting), nod head flexion (deg),
        hit time since the impact (s, <0 before), mb car drop during one video frame (m, speed blur),
        buf buffer length 0-1, cz camera height (m), d camera distance (m)}
The lab base (logo) is the pit floor, buffers on top of it (z = 0.35 when not crushed).
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_set import add_logo_base, _text   # noqa: E402  (the BREAKPOINT LAB base, same in every scene)

SCENE = "BL_elevator"
FLOOR = 0.3048 * 11                    # one floor = 11 ft (165 ft = 15 floors)
BUF, CRUSH = 0.35, 0.15
CAR_W, CAR_D, CAR_H = 1.60, 1.40, 2.30
SHAFT_TOP = 62.0
PITCH = math.radians(4)
FACE = math.radians(-28)               # the rider stands side-on, turned a little towards the camera
G = 9.81

# dummy sizes (m), about a 50th-percentile adult male
SHIN, THIGH, TORSO, UARM, FARM = 0.44, 0.44, 0.52, 0.30, 0.28
ANKLE = 0.08
LEG_Y, SHO_Y = 0.10, 0.20


# ---------------------------------------------------------------- materials
def _set(b, k, v):
    if k in b.inputs:
        b.inputs[k].default_value = v


def mat(name, **kw):
    """Principled material; unknown inputs are skipped (Blender versions differ)"""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        _set(b, k, v)
    return m


def _rough_var(m, lo, hi, scale=8.0, bump=0.0, col=None):
    """roughness never constant: a noise drives it (and optionally a bump and a colour variation)"""
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = lo
    mr.inputs["To Max"].default_value = hi
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Roughness"])
    if bump:
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    if col:
        rp = nt.nodes.new("ShaderNodeValToRGB")
        rp.color_ramp.elements[0].color = col[0]
        rp.color_ramp.elements[1].color = col[1]
        nt.links.new(nz.outputs["Fac"], rp.inputs["Fac"])
        nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    return m


def concrete():
    """cast concrete: formwork panel joints (1.2 x 2.4 m), mottling, vertical water stains, rough bump"""
    m = bpy.data.materials.get("BL_Concrete2")
    if m:
        return m
    m = mat("BL_Concrete2", **{"Roughness": 0.9})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # mottling
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.6
    nz.inputs["Detail"].default_value = 12.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.13, 0.13, 0.13, 1)
    ramp.color_ramp.elements[1].color = (0.27, 0.265, 0.25, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    # vertical stains: noise stretched along z
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6.0, 6.0, 0.15)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    st = nt.nodes.new("ShaderNodeTexNoise")
    st.inputs["Scale"].default_value = 3.0
    st.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], st.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeMapRange")
    sr.inputs["From Min"].default_value = 0.55
    sr.inputs["From Max"].default_value = 0.75
    sr.inputs["To Min"].default_value = 1.0
    sr.inputs["To Max"].default_value = 0.6
    nt.links.new(st.outputs["Fac"], sr.inputs["Value"])
    # formwork joints: thin dark lines from a brick texture with big "bricks"
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.018
    br.inputs["Brick Width"].default_value = 1.2
    br.inputs["Row Height"].default_value = 2.4
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (0.55, 0.55, 0.55, 1)
    mpb = nt.nodes.new("ShaderNodeMapping")
    mpb.inputs["Rotation"].default_value = (math.pi / 2, 0, 0)      # walls stand in XZ / YZ: bricks on the wall plane
    nt.links.new(tc.outputs["Object"], mpb.inputs["Vector"])
    nt.links.new(mpb.outputs["Vector"], br.inputs["Vector"])
    m1 = nt.nodes.new("ShaderNodeVectorMath")
    m1.operation = 'MULTIPLY'
    nt.links.new(ramp.outputs["Color"], m1.inputs[0])
    nt.links.new(br.outputs["Color"], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeVectorMath")
    m2.operation = 'SCALE'
    nt.links.new(m1.outputs["Vector"], m2.inputs[0])
    nt.links.new(sr.outputs["Result"], m2.inputs["Scale"])
    nt.links.new(m2.outputs["Vector"], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.78
    rr.inputs["To Max"].default_value = 0.96
    nt.links.new(nz.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 60.0
    fine.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    nt.links.new(fine.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def target_mat():
    """crash-test target: black and yellow quadrants"""
    m = bpy.data.materials.get("BL_Target")
    if m:
        return m
    m = mat("BL_Target", **{"Roughness": 0.4})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sp.inputs[0])
    mu = nt.nodes.new("ShaderNodeMath")
    mu.operation = 'MULTIPLY'
    nt.links.new(sp.outputs[0], mu.inputs[0])
    nt.links.new(sp.outputs[1], mu.inputs[1])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.0
    nt.links.new(mu.outputs[0], gt.inputs[0])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.interpolation = 'CONSTANT'
    rp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1)
    rp.color_ramp.elements[1].position = 0.5
    rp.color_ramp.elements[1].color = (0.85, 0.66, 0.04, 1)
    nt.links.new(gt.outputs[0], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    return m


def glass_mat():
    """laminated glass; shadow rays pass (lets the lights reach the cabin); cracks appear with the object property 'crack'"""
    m = bpy.data.materials.get("BL_Glass")
    if m:
        return m
    m = mat("BL_Glass", **{"Base Color": (0.93, 0.97, 0.95, 1), "Roughness": 0.02, "IOR": 1.52,
                           "Transmission Weight": 1.0, "Transmission": 1.0})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    outn = nt.nodes["Material Output"]
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mx.inputs[0])
    nt.links.new(b.outputs[0], mx.inputs[1])
    nt.links.new(tr.outputs[0], mx.inputs[2])
    # cracks: voronoi cell edges (radial-ish web), white and rough, only where crack > 0
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = 'DISTANCE_TO_EDGE'
    vo.inputs["Scale"].default_value = 7.0
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    lt = nt.nodes.new("ShaderNodeMath")
    lt.operation = 'LESS_THAN'
    lt.inputs[1].default_value = 0.018
    nt.links.new(vo.outputs["Distance"], lt.inputs[0])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = 'OBJECT'
    at.attribute_name = "crack"
    mu = nt.nodes.new("ShaderNodeMath")
    mu.operation = 'MULTIPLY'
    nt.links.new(lt.outputs[0], mu.inputs[0])
    nt.links.new(at.outputs["Fac"], mu.inputs[1])
    wh = nt.nodes.new("ShaderNodeBsdfDiffuse")
    wh.inputs["Color"].default_value = (0.85, 0.88, 0.88, 1)
    mx2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mu.outputs[0], mx2.inputs[0])
    nt.links.new(mx.outputs[0], mx2.inputs[1])
    nt.links.new(wh.outputs[0], mx2.inputs[2])
    nt.links.new(mx2.outputs[0], outn.inputs["Surface"])
    return m


def dust_mat():
    """concrete dust: a volume whose density follows the object property 'dens', soft at the edges"""
    m = bpy.data.materials.get("BL_Dust")
    if m:
        return m
    m = bpy.data.materials.new("BL_Dust")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    outn = nt.nodes["Material Output"]
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.62, 0.58, 0.52, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    gr = nt.nodes.new("ShaderNodeTexGradient")
    gr.gradient_type = 'SPHERICAL'
    nt.links.new(tc.outputs["Object"], gr.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.5
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = 'MULTIPLY'
    nt.links.new(gr.outputs["Fac"], m1.inputs[0])
    nt.links.new(nz.outputs["Fac"], m1.inputs[1])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = 'OBJECT'
    at.attribute_name = "dens"
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = 'MULTIPLY'
    nt.links.new(m1.outputs[0], m2.inputs[0])
    nt.links.new(at.outputs["Fac"], m2.inputs[1])
    nt.links.new(m2.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], outn.inputs["Volume"])
    return m


# ---------------------------------------------------------------- geometry helpers
def _link(sc, o, name, mv=False):
    o.name = name
    o["bb"] = name
    if mv:
        o["mv"] = 1                            # moves with the car (speed blur keys)
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)
    return o


def box(sc, name, size, loc, m, bevel=0.0, mv=False, seg=2):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)      # object space = metres: textures keep their real scale
    if bevel:
        md = o.modifiers.new("Bevel", 'BEVEL')
        md.width = bevel
        md.segments = seg
        md.limit_method = 'NONE'
    o.data.materials.append(m)
    return _link(sc, o, name, mv)


def cone(sc, name, r1, r2, m, verts=24, mv=True, smooth=True):
    """unit-length tapered cylinder along +Z from 0 (radius r1) to 1 (radius r2), stretched by place()"""
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=1, location=(0, 0, 0.5))
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return _link(sc, o, name, mv)


def ball(sc, name, r, m, sx=1.0, sy=1.0, sz=1.0, mv=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r)
    o = bpy.context.object
    o.scale = (sx, sy, sz)
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return _link(sc, o, name, mv)


def disk(sc, name, r, depth, m, mv=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=depth)
    o = bpy.context.object
    o.data.materials.append(m)
    return _link(sc, o, name, mv)


def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def place(o, a, b):
    """stretch a unit +Z mesh from point a to point b"""
    a, b = Vector(a), Vector(b)
    v = b - a
    o.location = a
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    o.scale = (1.0, 1.0, max(v.length, 1e-4))


def area(sc, name, size, e, col=(1, 1, 1), sy=None, mv=False):
    lt = bpy.data.lights.new(name, 'AREA')
    lt.energy = e
    lt.color = col
    lt.shape = 'RECTANGLE'
    lt.size = size
    lt.size_y = sy or size
    o = bpy.data.objects.new(name, lt)
    sc.collection.objects.link(o)
    o["bb"] = name
    if mv:
        o["mv"] = 1
    return o


def point(sc, name, e, loc, col=(1.0, 0.82, 0.6), r=0.05):
    lt = bpy.data.lights.new(name, 'POINT')
    lt.energy = e
    lt.color = col
    lt.shadow_soft_size = r
    o = bpy.data.objects.new(name, lt)
    o.location = loc
    sc.collection.objects.link(o)
    o["bb"] = name
    return o


# ---------------------------------------------------------------- build
N_SPARK, N_DEBRIS, N_DUST = 36, 26, 4


def build(res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    steel = _rough_var(mat("BL_Steel2", **{"Base Color": (0.62, 0.62, 0.63, 1), "Metallic": 1.0}), 0.28, 0.42, 14)
    brushed = _rough_var(mat("BL_Brushed", **{"Base Color": (0.70, 0.70, 0.71, 1), "Metallic": 1.0, "Anisotropic": 0.7}),
                         0.20, 0.32, 30)
    dark_steel = _rough_var(mat("BL_DarkSteel2", **{"Base Color": (0.20, 0.20, 0.21, 1), "Metallic": 1.0}), 0.45, 0.6, 10)
    frame_paint = _rough_var(mat("BL_FramePaint", **{"Base Color": (0.07, 0.075, 0.08, 1)}), 0.45, 0.7, 6, 0.05)
    laminate = _rough_var(mat("BL_Laminate", **{"Base Color": (0.42, 0.40, 0.37, 1)}), 0.35, 0.5, 4)
    granite = _rough_var(mat("BL_Granite", **{}), 0.25, 0.45, 40, 0.05,
                         ((0.03, 0.03, 0.032, 1), (0.11, 0.11, 0.115, 1)))
    rope = mat("BL_Rope", **{"Base Color": (0.36, 0.36, 0.35, 1), "Metallic": 1.0, "Roughness": 0.42})
    rubber = _rough_var(mat("BL_Rubber", **{"Base Color": (0.025, 0.025, 0.027, 1)}), 0.55, 0.75, 20)
    vinyl = _rough_var(mat("BL_Vinyl", **{"Base Color": (0.85, 0.60, 0.05, 1), "Coat Weight": 0.25, "Coat Roughness": 0.2}),
                       0.30, 0.45, 12, 0.02, ((0.80, 0.55, 0.045, 1), (0.88, 0.63, 0.06, 1)))
    paint = mat("BL_StencilPaint", **{"Base Color": (0.78, 0.76, 0.70, 1), "Roughness": 0.75})
    yellow_paint = _rough_var(mat("BL_YellowPaint", **{"Base Color": (0.80, 0.58, 0.04, 1)}), 0.5, 0.7, 6)
    led = mat("BL_LED", **{"Base Color": (1, 1, 1, 1), "Emission Color": (1.0, 0.97, 0.92, 1), "Emission Strength": 25.0})
    cage_lamp = mat("BL_CageLamp", **{"Base Color": (1, 0.9, 0.7, 1), "Emission Color": (1.0, 0.80, 0.55, 1),
                                      "Emission Strength": 40.0})
    btn = mat("BL_Button", **{"Base Color": (0.9, 0.9, 0.9, 1), "Emission Color": (0.55, 0.75, 1.0, 1),
                              "Emission Strength": 4.0})
    spark = mat("BL_Spark", **{"Base Color": (1, 0.6, 0.2, 1), "Emission Color": (1.0, 0.55, 0.15, 1),
                               "Emission Strength": 60.0})
    conc = concrete()
    glass = glass_mat()
    tgt = target_mat()

    # ---- shaft: back wall, side walls (cast concrete), landings every 11 ft, rails, brackets, conduit, work lights
    box(sc, "BackWall", (3.6, 0.2, SHAFT_TOP + 2), (0, 1.0, SHAFT_TOP / 2 - 1), conc)
    for sx in (-1, 1):
        box(sc, f"SideWall{sx}", (0.25, 2.2, SHAFT_TOP + 2), (sx * 1.85, 0.0, SHAFT_TOP / 2 - 1), conc)
        box(sc, f"Rail{sx}", (0.04, 0.12, SHAFT_TOP), (sx * 1.04, 0.0, SHAFT_TOP / 2), steel)      # T-rail blade
        box(sc, f"RailFoot{sx}", (0.10, 0.012, SHAFT_TOP), (sx * 1.04, 0.06, SHAFT_TOP / 2), steel)
    box(sc, "Conduit", (0.05, 0.05, SHAFT_TOP), (-1.25, 0.87, SHAFT_TOP / 2), dark_steel, bevel=0.02, seg=3)
    for k in range(1, 18):
        z = BUF + (k - 1) * FLOOR
        if k >= 2:                                             # the slab edge of each landing (a slightly darker band)
            box(sc, f"Slab{k}", (3.5, 0.10, 0.30), (0, 0.85, z - 0.15), conc, bevel=0.015)
        for sx in (-1, 1):                                     # rail brackets, bolted to the wall
            box(sc, f"Bracket{k}{sx}", (0.16, 0.80, 0.06), (sx * 1.14, 0.48, z + 1.2), dark_steel, bevel=0.005)
            for bz in (-0.02, 0.02):
                ball(sc, f"Bolt{k}{sx}{bz}", 0.012, steel, mv=False).location = (sx * 1.14, 0.87, z + 1.2 + bz * 3)
        box(sc, f"JBox{k}", (0.14, 0.06, 0.18), (-1.25, 0.84, z + 0.9), dark_steel, bevel=0.01)
        if k <= 16:
            t = _text(sc, f"Num{k}", str(k), 0.40, paint, -1.45, 0.896, z + 1.55)
            t["bb"] = f"Num{k}"
        if k % 2 == 1 and k <= 16:                             # caged work light, alternate walls
            sx = -1 if (k // 2) % 2 == 0 else 1
            lz = z + 2.4
            box(sc, f"LampBase{k}", (0.05, 0.12, 0.12), (sx * 1.70, 0.62, lz), dark_steel, bevel=0.01)
            ball(sc, f"Lamp{k}", 0.05, cage_lamp, mv=False).location = (sx * 1.64, 0.62, lz)
            point(sc, f"LampL{k}", 45, (sx * 1.58, 0.62, lz))
    # pit ladder (left wall)
    for sy in (0.25, 0.65):
        box(sc, f"LadderRail{sy}", (0.035, 0.035, 2.6), (-1.66, sy, 1.3), yellow_paint)
    for i in range(7):
        box(sc, f"Rung{i}", (0.03, 0.40, 0.03), (-1.66, 0.45, 0.35 + i * 0.3), yellow_paint)

    # ---- pit: the lab base is the pit floor (logo on its front face), spring/oil buffers on top
    add_logo_base(sc, width=3.4, height=0.48, depth=2.0, top_z=0.0)
    for sx in (-1, 1):
        cone(sc, f"BufBody{sx}", 0.11, 0.11, dark_steel, mv=False)
        cone(sc, f"BufRod{sx}", 0.05, 0.05, steel, mv=False)
        cone(sc, f"BufPad{sx}", 0.12, 0.12, rubber, mv=False)
    box(sc, "PitFloor", (3.6, 2.4, 0.05), (0, 0.0, -0.53), conc)

    # ---- the car (children of the empty "Car", z = 0 at the floor underside)
    parts = []
    P = lambda o: parts.append(o) or o
    P(box(sc, "CarFloor", (CAR_W, CAR_D, 0.12), (0, 0, 0.06), dark_steel, bevel=0.01))
    P(box(sc, "FloorTop", (CAR_W - 0.12, CAR_D - 0.10, 0.012), (0, 0.02, 0.126), granite))
    P(box(sc, "CarBack", (CAR_W, 0.05, CAR_H), (0, CAR_D / 2 - 0.025, CAR_H / 2), brushed))
    for sx in (-1, 1):
        P(box(sc, f"CarSide{sx}", (0.05, CAR_D, CAR_H), (sx * (CAR_W / 2 - 0.025), 0, CAR_H / 2), laminate))
        P(box(sc, f"Post{sx}", (0.06, 0.06, CAR_H - 0.1), (sx * (CAR_W / 2 - 0.05), -CAR_D / 2 + 0.03, CAR_H / 2 + 0.05),
              brushed, bevel=0.01))
        P(box(sc, f"Stile{sx}", (0.10, 0.16, CAR_H + 0.55), (sx * (CAR_W / 2 + 0.08), 0, (CAR_H + 0.55) / 2 - 0.15),
              frame_paint, bevel=0.008))
        for zz in (CAR_H + 0.28, -0.05):                      # guide shoes on the rails, top and bottom
            P(box(sc, f"Shoe{sx}{zz}", (0.14, 0.14, 0.16), (sx * 0.96, 0, zz), dark_steel, bevel=0.01))
        P(box(sc, f"Rail-brace{sx}", (0.05, 0.05, 1.5), (sx * (CAR_W / 2 + 0.08), 0.2, CAR_H * 0.55), frame_paint))
    P(box(sc, "CarRoof", (CAR_W + 0.02, CAR_D + 0.02, 0.06), (0, 0, CAR_H + 0.03), dark_steel))
    P(box(sc, "Ceiling", (CAR_W - 0.1, CAR_D - 0.1, 0.02), (0, 0, CAR_H - 0.04), brushed))
    for i, (lx, ly) in enumerate(((-0.4, -0.25), (0.4, -0.25), (-0.4, 0.3), (0.4, 0.3))):
        d = P(disk(sc, f"Downlight{i}", 0.06, 0.01, led, mv=False))
        d.location = (lx, ly, CAR_H - 0.055)
    P(box(sc, "Crosshead", (CAR_W + 0.38, 0.22, 0.20), (0, 0, CAR_H + 0.42), frame_paint, bevel=0.01))
    P(box(sc, "HitchPlate", (0.36, 0.14, 0.03), (0, 0, CAR_H + 0.535), dark_steel))
    for i, rx in enumerate((-0.08, 0.0, 0.08)):
        P(cone(sc, f"Shackle{i}", 0.022, 0.016, steel, 12, mv=False)).location = (rx, 0, CAR_H + 0.55)
        P(cone(sc, f"Stub{i}", 0.014, 0.014, rope, 10, mv=False)).location = (rx, 0, CAR_H + 0.65)
    P(box(sc, "Plank", (CAR_W + 0.38, 0.22, 0.16), (0, 0, -0.02), frame_paint, bevel=0.01))
    P(box(sc, "Apron", (CAR_W - 0.1, 0.03, 0.55), (0, -CAR_D / 2 + 0.03, -0.30), dark_steel))   # toe guard
    P(box(sc, "Sill", (CAR_W, 0.10, 0.03), (0, -CAR_D / 2 + 0.05, 0.135), steel))
    P(box(sc, "KickPlate", (CAR_W - 0.12, 0.02, 0.14), (0, -CAR_D / 2 + 0.03, 0.20), brushed))
    P(box(sc, "Transom", (CAR_W - 0.12, 0.04, 0.10), (0, -CAR_D / 2 + 0.03, CAR_H - 0.06), brushed))
    gl = P(box(sc, "Glass", (CAR_W - 0.14, 0.012, CAR_H - 0.40), (0, -CAR_D / 2 + 0.03, 0.27 + (CAR_H - 0.40) / 2), glass))
    gl["crack"] = 0.0
    P(box(sc, "Handrail", (1.2, 0.04, 0.04), (0, CAR_D / 2 - 0.10, 0.95), steel, bevel=0.015, seg=3))
    for hx in (-0.55, 0.55):
        P(box(sc, f"RailPost{hx}", (0.03, 0.06, 0.03), (hx, CAR_D / 2 - 0.07, 0.95), steel))
    P(box(sc, "COP", (0.20, 0.015, 0.55), (0.55, CAR_D / 2 - 0.055, 1.25), brushed, bevel=0.004))   # button panel
    for i in range(8):
        P(disk(sc, f"Btn{i}", 0.014, 0.01, btn, mv=False)).location = (0.51 + (i % 2) * 0.08, CAR_D / 2 - 0.065, 1.08 + (i // 2) * 0.09)
        bpy.context.object.rotation_euler = (math.pi / 2, 0, 0)
    car = bpy.data.objects.new("Car", None)
    car["bb"] = "Car"
    car["mv"] = 1
    sc.collection.objects.link(car)
    for o in parts:
        o.parent = car
        if "mv" in o:
            del o["mv"]
    il = area(sc, "CabinLight", 0.9, 160, (1.0, 0.96, 0.9), sy=0.6)            # the cabin's own ceiling light
    il.parent = car
    il.location = (0, 0, CAR_H - 0.09)
    il.rotation_euler = (0, 0, 0)
    for i, rx in enumerate((-0.08, 0.0, 0.08)):                                # hoist ropes, placed in set_pose
        cone(sc, f"Rope{i}", 0.013, 0.013, rope, 12)
    # travelling cable (flat, black) from under the car to the mid-shaft fixing
    cu = bpy.data.curves.new("TravCable", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.022
    cu.bevel_resolution = 2
    sp = cu.splines.new('NURBS')
    sp.points.add(4)
    sp.order_u = 3
    sp.use_endpoint_u = True
    tco = bpy.data.objects.new("TravCable", cu)
    cu.materials.append(rubber)
    tco["bb"] = "TravCable"
    sc.collection.objects.link(tco)

    # ---- the dummy (Hybrid-III-like): yellow vinyl, black joints, quadrant targets; placed from joints in set_pose
    for side in ("L", "R"):
        cone(sc, f"Thigh{side}", 0.088, 0.062, vinyl)
        cone(sc, f"Shin{side}", 0.060, 0.044, vinyl)
        ball(sc, f"Knee{side}", 0.066, vinyl, 1.0, 1.0, 0.95)
        ball(sc, f"Ankle{side}", 0.045, rubber)
        box(sc, f"Shoe{side}", (0.27, 0.105, 0.09), (0, 0, 0), rubber, bevel=0.035, mv=True, seg=4)
        cone(sc, f"UArm{side}", 0.052, 0.043, vinyl)
        cone(sc, f"FArm{side}", 0.043, 0.034, vinyl)
        ball(sc, f"Shoulder{side}", 0.062, rubber)
        ball(sc, f"Elbow{side}", 0.046, rubber)
        ball(sc, f"Hand{side}", 0.05, vinyl, 0.75, 0.95, 1.5)
    ball(sc, "Pelvis", 0.12, vinyl, 1.0, 1.55, 1.0)
    cone(sc, "Lumbar", 0.075, 0.075, rubber)
    ball(sc, "Chest", 0.20, vinyl, 0.68, 0.95, 1.2)
    ball(sc, "Bib", 0.12, rubber, 0.35, 1.25, 1.0)              # the black chest-jacket front plate
    cone(sc, "NeckCore", 0.017, 0.017, steel, 12)
    for i in range(3):
        cone(sc, f"NeckDisc{i}", 0.05, 0.05, rubber)
    ball(sc, "Head", 0.115, vinyl, 0.92, 0.75, 1.03)
    ball(sc, "Nose", 0.022, vinyl, 1.0, 0.8, 1.3)
    ball(sc, "Chin", 0.055, vinyl, 1.0, 1.1, 0.8)
    for nm in ("THead", "TSho", "THip", "TKnee"):
        disk(sc, nm, 0.034, 0.004, tgt)

    # ---- impact effects (hidden until the hit)
    rnd = random.Random(16)
    for i in range(N_SPARK):
        cone(sc, f"Spark{i}", 0.006, 0.002, spark, 6, mv=False, smooth=False)
    for i in range(N_DEBRIS):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
        o = bpy.context.object
        r = rnd.uniform(0.02, 0.06)
        o.scale = (r * rnd.uniform(0.7, 1.3), r * rnd.uniform(0.6, 1.2), r * rnd.uniform(0.5, 1.0))
        o.data.materials.append(conc if i % 3 else dark_steel)
        _link(sc, o, f"Debris{i}")
    dm = dust_mat()
    for i in range(N_DUST):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1)
        o = bpy.context.object
        o.data.materials.append(dm)
        _link(sc, o, f"Dust{i}")
        o["dens"] = 0.0

    # ---- lights: key from front left and a rim from above follow the car; the pit is lit for the logo
    area(sc, "Key", 3.0, 1500, (1.0, 0.97, 0.93), mv=True)
    area(sc, "Fill", 4.0, 350, (0.85, 0.9, 1.0), mv=True)
    area(sc, "Top", 2.0, 500, (1.0, 0.95, 0.88), mv=True)
    pit = area(sc, "PitLight", 4.0, 900)
    pit.location = (1.5, -7.0, 2.0)
    aim(pit, (0, 0, 0.0))

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 85
    cam.clip_end = 200
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    co["mv"] = 1
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_World") or bpy.data.worlds.new("BL_World")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.60, 0.68, 1)
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.08
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
    sc.cycles.max_bounces = 6
    sc.cycles.transmission_bounces = 4
    sc.cycles.volume_bounces = 0
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass
    set_pose({"zc": BUF + 15 * FLOOR, "cut": 0, "c": 0, "arm": 0, "lean": 0, "dz": 0, "s": 0, "nod": 0, "hit": -1,
              "mb": 0, "buf": 1, "cz": BUF + 15 * FLOOR + 1.3, "d": 20.0}, sc)
    return sc


# ---------------------------------------------------------------- the dummy's skeleton (side view: x forward, z up)
def rider_joints(c, arm, lean, s):
    """joints for crouch c, arm swing, lean, slump s (folds down to sitting on the floor); feet flat at z = 0"""
    ts = (1 - s) * math.radians(60) * c + s * math.radians(-20)          # shin from vertical (+ = knee forward)
    th = (1 - s) * math.radians(70) * c + s * math.radians(132)          # thigh (+ = hip behind the knee)
    tb = (1 - s) * (math.radians(35) * c + math.radians(45) * lean) + s * math.radians(58)
    ank = Vector((0, 0, ANKLE))
    knee = ank + SHIN * Vector((math.sin(ts), 0, math.cos(ts)))
    hip = knee + THIGH * Vector((-math.sin(th), 0, math.cos(th)))
    up = Vector((math.sin(tb), 0, math.cos(tb)))
    sho = hip + TORSO * up
    a = math.radians(170) * arm + tb                           # 0: hangs along the body; + swings forward and up
    ua = Vector((math.sin(a), 0, -math.cos(a)))
    sh = sho - 0.06 * up
    elb = sh + UARM * ua
    fa_ang = a + math.radians(25)
    hand = elb + FARM * Vector((math.sin(fa_ang), 0, -math.cos(fa_ang)))
    return dict(ank=ank, knee=knee, hip=hip, sho=sho, sh=sh, elb=elb, hand=hand, up=up, tb=tb)


# ---------------------------------------------------------------- pose: the one place where motion is defined
def _show(o, on):
    o.hide_render = o.hide_viewport = not on


def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    for o in sc.objects:
        o.animation_data_clear()
    zc = float(p["zc"])
    ob["Car"].location = (0, 0, zc)
    hit = float(p.get("hit", -1))

    # hoist ropes: intact up to the machine room, or cut above the hitch and whipped up by `cut` metres
    top = zc + CAR_H + 0.56
    cut = float(p["cut"])
    for i, rx in enumerate((-0.08, 0.0, 0.08)):
        lo = top + (0.20 + cut * (1.0 + 0.12 * (i - 1)) if cut > 0 else 0.0)
        sway = 0.03 * math.sin(cut * 2.0 + i) if cut > 0 else 0.0
        place(ob[f"Rope{i}"], (rx + sway, 0.0, lo), (rx, 0.0, SHAFT_TOP + 8))
        _show(ob[f"Stub{i}"], cut > 0)
        ob[f"Stub{i}"].scale = (1, 1, 0.16)

    # travelling cable: hangs from under the car in a loop down to its fixing at mid-shaft
    zfix = BUF + 7 * FLOOR
    lb = max(0.12, min(zc, zfix) - 0.7)
    pts = [(0.55, 0.30, zc - 0.05), (0.56, 0.34, (zc + lb) / 2 + 0.2), (0.62, 0.45, lb), (0.78, 0.62, (lb + zfix) / 2),
           (0.95, 0.80, zfix)]
    sp = ob["TravCable"].data.splines[0]
    for k, (x, y, z) in enumerate(pts):
        sp.points[k].co = (x, y, z, 1.0)

    # buffers: body fixed on the base, rod + pad compress with the car
    blen = min(BUF, zc)
    for sx in (-1, 1):
        x = sx * 0.55
        place(ob[f"BufBody{sx}"], (x, 0, 0), (x, 0, 0.16))
        place(ob[f"BufRod{sx}"], (x, 0, 0.16), (x, 0, max(0.17, blen - 0.04)))
        place(ob[f"BufPad{sx}"], (x, 0, max(0.17, blen - 0.04)), (x, 0, blen))
    # toe guard crumples against the pit at the hit
    crush = 0.0 if hit < 0 else min(1.0, hit / 0.06)
    ap = ob["Apron"]
    ap.scale = (1.0, 1.0, 1.0 - 0.45 * crush)
    ap.location = (0, -CAR_D / 2 + 0.03 - 0.05 * crush, -0.30 + 0.12 * crush)
    ap.rotation_euler = (math.radians(-14) * crush, 0, 0)
    ob["Glass"]["crack"] = 1.0 if hit >= 0.02 else 0.0

    # ---- dummy: side-on (faces +x), turned towards the camera, centred in the car
    J = rider_joints(float(p["c"]), float(p["arm"]), float(p["lean"]), float(p.get("s", 0)))
    base = Vector((-0.10, 0.06, zc + 0.132 + float(p["dz"])))
    cf, sf = math.cos(FACE), math.sin(FACE)
    rot = lambda v: Vector((v.x * cf - v.y * sf, v.x * sf + v.y * cf, v.z))
    Wp = lambda v: base + rot(v)
    side_y = {"L": LEG_Y, "R": -LEG_Y}
    for side, yo in side_y.items():
        off = Vector((0, yo, 0))
        place(ob[f"Thigh{side}"], Wp(J["hip"] + off), Wp(J["knee"] + off))
        place(ob[f"Shin{side}"], Wp(J["knee"] + off), Wp(J["ank"] + off))
        ob[f"Knee{side}"].location = Wp(J["knee"] + off + Vector((0.02, 0, 0)))
        ob[f"Ankle{side}"].location = Wp(J["ank"] + off)
        sh = ob[f"Shoe{side}"]
        sh.location = Wp(Vector((0.07, yo, 0.045)))
        sh.rotation_euler = (0, 0, FACE)
        so = Vector((0, SHO_Y if side == "L" else -SHO_Y, 0))
        place(ob[f"UArm{side}"], Wp(J["sh"] + so), Wp(J["elb"] + so))
        place(ob[f"FArm{side}"], Wp(J["elb"] + so), Wp(J["hand"] + so))
        ob[f"Shoulder{side}"].location = Wp(J["sh"] + so)
        ob[f"Elbow{side}"].location = Wp(J["elb"] + so)
        hd = ob[f"Hand{side}"]
        fa = J["hand"] - J["elb"]
        hd.location = Wp(J["hand"] + so + 0.05 * fa.normalized())
        hd.rotation_euler = rot(fa).to_track_quat('Z', 'Y').to_euler()
    tb, up = J["tb"], J["up"]
    fwd = Vector((math.cos(tb), 0, -math.sin(tb)))
    trunk = (0, tb, FACE)
    ob["Pelvis"].location = Wp(J["hip"] + 0.04 * up)
    ob["Pelvis"].rotation_euler = trunk
    place(ob["Lumbar"], Wp(J["hip"] + 0.10 * up), Wp(J["hip"] + 0.24 * up))
    ob["Chest"].location = Wp(J["hip"] + 0.36 * up + 0.01 * fwd)
    ob["Chest"].rotation_euler = trunk
    ob["Bib"].location = Wp(J["hip"] + 0.34 * up + 0.105 * fwd)
    ob["Bib"].rotation_euler = trunk
    # neck + head, the head flexes by `nod` (whiplash at the hit)
    n0 = J["sho"] + 0.01 * up
    hn = tb + math.radians(float(p.get("nod", 0)))
    hup = Vector((math.sin(hn), 0, math.cos(hn)))
    hfw = Vector((math.cos(hn), 0, -math.sin(hn)))
    n1 = n0 + 0.12 * (up + hup).normalized()
    place(ob["NeckCore"], Wp(n0), Wp(n1))
    for i in range(3):
        a = n0 + (n1 - n0) * (0.12 + 0.3 * i)
        place(ob[f"NeckDisc{i}"], Wp(a), Wp(a + (n1 - n0) * 0.18))
    hc = n1 + 0.11 * hup + 0.015 * hfw
    ob["Head"].location = Wp(hc)
    ob["Head"].rotation_euler = (0, hn, FACE)
    ob["Nose"].location = Wp(hc + 0.098 * hfw + 0.005 * hup)
    ob["Nose"].rotation_euler = (0, hn, FACE)
    ob["Chin"].location = Wp(hc + 0.055 * hfw - 0.075 * hup)
    ob["Chin"].rotation_euler = (0, hn, FACE)
    # targets on the side facing the camera (local -y)
    tg = (math.pi / 2, 0, FACE)
    for nm, v in (("THead", hc + Vector((0, -0.088, 0.01))), ("TSho", J["sh"] + Vector((0, -SHO_Y - 0.063, 0))),
                  ("THip", J["hip"] + Vector((0, -0.19, 0))), ("TKnee", J["knee"] + Vector((0.02, -LEG_Y - 0.066, 0)))):
        ob[nm].location = Wp(v)
        ob[nm].rotation_euler = tg

    # ---- impact: sparks off the plank and buffers, debris, dust (all deterministic, from the time since the hit)
    rnd = random.Random(16)
    for i in range(N_SPARK):
        o = ob[f"Spark{i}"]
        sx = rnd.choice((-1, 1))
        p0 = Vector((sx * rnd.uniform(0.45, 1.0), rnd.uniform(-0.6, 0.3), BUF - CRUSH + rnd.uniform(-0.05, 0.05)))
        ang = rnd.uniform(0, 2 * math.pi)
        sp_ = rnd.uniform(3.0, 9.0)
        v0 = Vector((sx * abs(math.cos(ang)) * sp_, -abs(math.sin(ang)) * sp_ * 0.8, rnd.uniform(1.0, 5.0)))
        life = rnd.uniform(0.12, 0.35)
        t0 = rnd.uniform(0.0, 0.03)
        t = hit - t0
        if hit < 0 or t < 0 or t > life:
            _show(o, False)
            continue
        _show(o, True)
        pos = p0 + v0 * t + Vector((0, 0, -0.5 * G * t * t))
        vel = v0 + Vector((0, 0, -G * t))
        ln = max(0.03, vel.length * 0.012)
        place(o, pos - vel.normalized() * ln, pos)
    for i in range(N_DEBRIS):
        o = ob[f"Debris{i}"]
        p0 = Vector((rnd.uniform(-0.9, 0.9), rnd.uniform(-0.7, 0.2), rnd.uniform(0.02, 0.25)))
        v0 = Vector((rnd.uniform(-3.5, 3.5), rnd.uniform(-3.0, 0.5), rnd.uniform(1.5, 6.0)))
        spin = Vector((rnd.uniform(-20, 20), rnd.uniform(-20, 20), rnd.uniform(-20, 20)))
        if hit < 0:
            _show(o, False)
            continue
        _show(o, True)
        t = hit
        pos = p0 + v0 * t + Vector((0, 0, -0.5 * G * t * t))
        tl = (v0.z + math.sqrt(v0.z ** 2 + 2 * G * p0.z)) / G          # lands on the base top (z = 0)
        if t >= tl:
            pos = p0 + v0 * tl
            pos.z = 0.02
            spin_t = tl
        else:
            spin_t = t
        pos.x = max(-1.6, min(1.6, pos.x))                             # stays inside the shaft
        pos.y = max(-0.95, min(0.8, pos.y))
        o.location = pos
        o.rotation_euler = tuple(spin * spin_t)
    for i in range(N_DUST):
        o = ob[f"Dust{i}"]
        if hit < 0:
            _show(o, False)
            continue
        _show(o, True)
        sx = (-1, 1, -0.4, 0.5)[i]
        grow = 1 - math.exp(-hit * 5.0)
        o.location = (sx * (0.5 + 0.6 * grow), -0.35 - 0.3 * grow, 0.15 + 0.35 * grow + 0.15 * i)
        rr = 0.25 + 1.0 * grow
        o.scale = (rr * 1.2, rr * 0.8, rr * 0.7)
        o["dens"] = 4.0 * math.exp(-hit * 1.6) * (0.6 + 0.4 * (1 - grow)) / max(0.6, rr)

    # lights follow the car
    for name, off, tgt_z in (("Key", (-5.0, -7.0, 4.5), 1.2), ("Fill", (6.0, -6.0, 1.5), 1.0), ("Top", (0.4, -1.2, 6.5), 1.2)):
        L = ob[name]
        L.location = (off[0], off[1], zc + off[2])
        aim(L, (0, 0, zc + tgt_z))
    cz, d = float(p["cz"]), float(p["d"])
    cam = ob["Cam"]
    cam.location = (0.0, -d * math.cos(PITCH), cz + d * math.sin(PITCH))
    cam.rotation_euler = (math.pi / 2 - PITCH, 0.0, 0.0)
    speed_blur(sc, float(p.get("mb", 0)))


def speed_blur(sc, mb):
    """the camera tracks the falling car: what moves with it is keyed one frame apart, so the shaft streaks"""
    sc.render.use_motion_blur = mb > 0.01
    if mb <= 0.01:
        return
    sc.render.motion_blur_shutter = 0.5                     # 180 degree shutter
    movers = [o for o in sc.objects if o.get("mv") and o.parent is None]
    for o in movers:
        for f, dz in ((0, mb), (1, 0.0), (2, -mb)):
            o.location.z += dz
            o.keyframe_insert("location", frame=f)
            o.location.z -= dz
        o.keyframe_insert("rotation_euler", frame=1)
        o.keyframe_insert("scale", frame=1)
    sc.frame_set(1)


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
