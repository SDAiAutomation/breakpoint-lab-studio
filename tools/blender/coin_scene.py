"""Breakpoint Lab - episode 017 in Blender (Cycles): a penny dropped from the top of the Empire State Building.

Same pipeline as elevator_scene.py: the scene is built from code, engine/coin.html simulates the fall (no air:
v = sqrt(2 g h), 208 mph; real air: terminal speed 25 mph, L. Bloomfield), lays out the video and says which pose each
frame shows; this script renders one image per different pose.

  blender -b -P tools/blender/coin_scene.py -- --poses work/timeline.json --out work/bscene --range 0-17

Set (lab version, like the other tests): a grey studio cyclorama, a drop tower (two aluminium rails with hazard
marks every metre, a clear acrylic guide tube with tick rings every 10 cm), and under it the BREAKPOINT LAB base
carrying a Hybrid-III-like crash-test headform (yellow vinyl, sculpted face, black neck discs, quadrant targets)
looking up at the tube. A US penny (19.05 mm, copper). While the coin falls the camera rides with it (front view,
50 mm, 0.6 m): the rails and the tube's rings streak past; at the end the head rises into the frame and the coin hits
the forehead. Wide studio shot for the titles. The 440 m height is told by the texts and the live readout.

pose = {zc coin centre height (m), cx coin sideways offset (m), tilt (deg, 0 = flat), yaw (deg),
        cz camera height (m), d camera distance (m), wide 1 = street shot, hit time since the contact (s, <0 before),
        mb coin drop during one video frame (m, speed blur)}
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random                                    # noqa: E402

from lab_set import add_logo_base, BASE_COL   # noqa: E402  (the BREAKPOINT LAB base, same in every scene)
import headform                                  # noqa: E402  (the face, shared with the contact computation)

SCENE = "BL_coin"
Z_HIT = 1.609                       # coin centre at the contact (engine/coin.html); headform.top_along_vertical
HEAD_C = (0.0, 0.0, 1.50)           # head centre; tilted back 38 deg, the coin line x = y = 0 meets the upper forehead
HEAD_TILT = math.radians(-38)
TUBE_R, TUBE_BOT = 0.05, Z_HIT + 0.16
EL_LAB, AZ_LAB = math.radians(12), math.radians(16)    # riding camera: front, a little above and to the right
BASE_TOP = 1.10
WALL_Y = 8.0                        # tower facade plane (front face): the coin falls 4 m in front of it
TOWER_TOP = 470.0
EL, AZ = math.radians(84), math.radians(10)   # riding camera: 78 deg down, a little to the right
R_COIN, T_COIN = 0.009525, 0.00152  # US cent: 19.05 mm x 1.52 mm


# ---------------------------------------------------------------- materials
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


def _sock(sockets, name, typ):
    return next(x for x in sockets if x.name == name and x.type == typ)


def mixc(nt, fac, a, b):
    """colour mix (ShaderNodeMix, RGBA): a, b are sockets or RGBA tuples; returns the result socket"""
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = 'RGBA'
    nt.links.new(fac, m.inputs["Factor"])
    for nm, v in (("A", a), ("B", b)):
        so = _sock(m.inputs, nm, 'RGBA')
        if isinstance(v, tuple):
            so.default_value = v
        else:
            nt.links.new(v, so)
    return _sock(m.outputs, "Result", 'RGBA')


def facade_mat():
    """curtain wall: tinted glass panes (each a slightly different tint), aluminium mullions every 1.5 m,
    a stone spandrel band at every floor (3.8 m), a dark granite lobby band up to 4.5 m"""
    m = bpy.data.materials.get("BL_Facade")
    if m:
        return m
    m = mat("BL_Facade")
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    b = nd["Principled BSDF"]
    tc = nd.new("ShaderNodeTexCoord")
    sp = nd.new("ShaderNodeSeparateXYZ")
    ln.new(tc.outputs["Object"], sp.inputs[0])
    nsp = nd.new("ShaderNodeSeparateXYZ")               # box mapping: x on the faces looking along y, y on the others
    ln.new(tc.outputs["Normal"], nsp.inputs[0])
    ax = nd.new("ShaderNodeMath")
    ax.operation = 'ABSOLUTE'
    ln.new(nsp.outputs["Y"], ax.inputs[0])
    ay = nd.new("ShaderNodeMath")
    ay.operation = 'ABSOLUTE'
    ln.new(nsp.outputs["X"], ay.inputs[0])
    ux = nd.new("ShaderNodeMath")
    ux.operation = 'MULTIPLY'
    ln.new(sp.outputs["X"], ux.inputs[0])
    ln.new(ax.outputs[0], ux.inputs[1])
    uy = nd.new("ShaderNodeMath")
    uy.operation = 'MULTIPLY'
    ln.new(sp.outputs["Y"], uy.inputs[0])
    ln.new(ay.outputs[0], uy.inputs[1])
    uu = nd.new("ShaderNodeMath")
    uu.operation = 'ADD'
    ln.new(ux.outputs[0], uu.inputs[0])
    ln.new(uy.outputs[0], uu.inputs[1])
    cb = nd.new("ShaderNodeCombineXYZ")
    ln.new(uu.outputs[0], cb.inputs["X"])
    ln.new(sp.outputs["Z"], cb.inputs["Y"])
    roof = nd.new("ShaderNodeMath")                     # roofs: gravel and plant, grey
    roof.operation = 'GREATER_THAN'
    roof.inputs[1].default_value = 0.5
    ln.new(nsp.outputs["Z"], roof.inputs[0])
    br = nd.new("ShaderNodeTexBrick")                   # mortar = mullions and transoms, brick colour = pane tint
    br.offset = 0.0
    br.squash = 1.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.05
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Brick Width"].default_value = 1.5
    br.inputs["Row Height"].default_value = 3.8 / 2
    br.inputs["Color1"].default_value = (0.22, 0.29, 0.36, 1)       # coated glass: tinted mirror of the sky
    br.inputs["Color2"].default_value = (0.28, 0.34, 0.40, 1)
    br.inputs["Mortar"].default_value = (0.0, 0.0, 0.0, 1)
    ln.new(cb.outputs[0], br.inputs["Vector"])
    # spandrel: the lower 22 % of every floor
    dv = nd.new("ShaderNodeMath")
    dv.operation = 'DIVIDE'
    dv.inputs[1].default_value = 3.8
    ln.new(sp.outputs["Z"], dv.inputs[0])
    fr = nd.new("ShaderNodeMath")
    fr.operation = 'FRACT'
    ln.new(dv.outputs[0], fr.inputs[0])
    lt = nd.new("ShaderNodeMath")
    lt.operation = 'LESS_THAN'
    lt.inputs[1].default_value = 0.22
    ln.new(fr.outputs[0], lt.inputs[0])
    lobby = nd.new("ShaderNodeMath")
    lobby.operation = 'LESS_THAN'
    lobby.inputs[1].default_value = 4.5
    ln.new(sp.outputs["Z"], lobby.inputs[0])
    # colours
    glass_col = br.outputs["Color"]
    c1 = mixc(nt, br.outputs["Fac"], glass_col, (0.50, 0.51, 0.52, 1))      # glass / mullion
    c2 = mixc(nt, lt.outputs[0], c1, (0.42, 0.41, 0.39, 1))                   # + spandrel stone
    c3 = mixc(nt, lobby.outputs[0], c2, (0.05, 0.05, 0.055, 1))               # + lobby granite
    c4 = mixc(nt, roof.outputs[0], c3, (0.30, 0.30, 0.29, 1))                 # + roof
    ln.new(c4, b.inputs["Base Color"])
    # metallic: mullions 1, glass 0 (dielectric, glossy), stone 0
    gm = nd.new("ShaderNodeMath")                       # glass 0.85 (reflective coating), mullion 1
    gm.operation = 'MULTIPLY_ADD'
    ln.new(br.outputs["Fac"], gm.inputs[0])
    gm.inputs[1].default_value = 0.15
    gm.inputs[2].default_value = 0.85
    met = nd.new("ShaderNodeMath")
    met.operation = 'MULTIPLY'
    ln.new(gm.outputs[0], met.inputs[0])
    inv = nd.new("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    lr = nd.new("ShaderNodeMath")
    lr.operation = 'MAXIMUM'
    ln.new(lt.outputs[0], lr.inputs[0])
    ln.new(roof.outputs[0], lr.inputs[1])
    ln.new(lr.outputs[0], inv.inputs[1])
    ln.new(inv.outputs[0], met.inputs[1])
    ln.new(met.outputs[0], b.inputs["Metallic"])
    # roughness: glass 0.03-0.08 (panes never perfectly flat), metal 0.35, stone 0.8
    nz = nd.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.6
    ln.new(cb.outputs[0], nz.inputs["Vector"])
    rg = nd.new("ShaderNodeMapRange")
    rg.inputs["To Min"].default_value = 0.03
    rg.inputs["To Max"].default_value = 0.09
    ln.new(nz.outputs["Fac"], rg.inputs["Value"])
    r1 = nd.new("ShaderNodeMix")
    r1.data_type = 'FLOAT'
    ln.new(br.outputs["Fac"], r1.inputs["Factor"])
    ln.new(rg.outputs["Result"], _sock(r1.inputs, "A", 'VALUE'))
    _sock(r1.inputs, "B", 'VALUE').default_value = 0.35
    r2 = nd.new("ShaderNodeMix")
    r2.data_type = 'FLOAT'
    ln.new(lr.outputs[0], r2.inputs["Factor"])
    ln.new(_sock(r1.outputs, "Result", 'VALUE'), _sock(r2.inputs, "A", 'VALUE'))
    _sock(r2.inputs, "B", 'VALUE').default_value = 0.8
    ln.new(_sock(r2.outputs, "Result", 'VALUE'), b.inputs["Roughness"])
    # depth: mullions stand proud of the glass
    bp = nd.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.05
    ln.new(br.outputs["Fac"], bp.inputs["Height"])
    ln.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def pavement_mat():
    """sidewalk: 1.5 m concrete slabs, joints, light stains"""
    m = bpy.data.materials.get("BL_Pavement")
    if m:
        return m
    m = mat("BL_Pavement")
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    b = nd["Principled BSDF"]
    tc = nd.new("ShaderNodeTexCoord")
    br = nd.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 1.5
    br.inputs["Row Height"].default_value = 1.5
    br.inputs["Color1"].default_value = (0.36, 0.35, 0.33, 1)
    br.inputs["Color2"].default_value = (0.40, 0.39, 0.37, 1)
    br.inputs["Mortar"].default_value = (0.16, 0.16, 0.15, 1)
    ln.new(tc.outputs["Object"], br.inputs["Vector"])
    ln.new(br.outputs["Color"], b.inputs["Base Color"])
    nz = nd.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 10.0
    ln.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nd.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.65
    mr.inputs["To Max"].default_value = 0.9
    ln.new(nz.outputs["Fac"], mr.inputs["Value"])
    ln.new(mr.outputs["Result"], b.inputs["Roughness"])
    bp = nd.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.15
    ln.new(nz.outputs["Fac"], bp.inputs["Height"])
    ln.new(bp.outputs["Normal"], b.inputs["Normal"])
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


def rail_mat():
    """aluminium rail, yellow/black hazard band every metre (the speed you see streaking past)"""
    m = bpy.data.materials.get("BL_Rail")
    if m:
        return m
    m = mat("BL_Rail")
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    b = nd["Principled BSDF"]
    tc = nd.new("ShaderNodeTexCoord")
    sp = nd.new("ShaderNodeSeparateXYZ")
    ln.new(tc.outputs["Object"], sp.inputs[0])
    fr = nd.new("ShaderNodeMath")
    fr.operation = 'FRACT'
    ln.new(sp.outputs["Z"], fr.inputs[0])
    band = nd.new("ShaderNodeMath")
    band.operation = 'LESS_THAN'
    band.inputs[1].default_value = 0.12
    ln.new(fr.outputs[0], band.inputs[0])
    st = nd.new("ShaderNodeMath")                       # stripes inside the band
    st.operation = 'FRACT'
    m10 = nd.new("ShaderNodeMath")
    m10.operation = 'MULTIPLY'
    m10.inputs[1].default_value = 25.0
    ln.new(sp.outputs["Z"], m10.inputs[0])
    ln.new(m10.outputs[0], st.inputs[0])
    st2 = nd.new("ShaderNodeMath")
    st2.operation = 'LESS_THAN'
    st2.inputs[1].default_value = 0.5
    ln.new(st.outputs[0], st2.inputs[0])
    stripe = mixc(nt, st2.outputs[0], (0.85, 0.62, 0.03, 1), (0.02, 0.02, 0.02, 1))
    col = mixc(nt, band.outputs[0], (0.62, 0.63, 0.65, 1), stripe)
    ln.new(col, b.inputs["Base Color"])
    inv = nd.new("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    ln.new(band.outputs[0], inv.inputs[1])
    ln.new(inv.outputs[0], b.inputs["Metallic"])
    b.inputs["Roughness"].default_value = 0.35
    return m


def tube_mat():
    """clear acrylic tube, a thin dark tick ring every 10 cm and a wider one every metre"""
    m = bpy.data.materials.get("BL_Tube")
    if m:
        return m
    m = mat("BL_Tube", **{"Base Color": (0.95, 0.97, 0.98, 1), "Transmission Weight": 1.0, "Roughness": 0.03, "IOR": 1.49})
    nt = m.node_tree
    nd, ln = nt.nodes, nt.links
    b = nd["Principled BSDF"]
    tc = nd.new("ShaderNodeTexCoord")
    sp = nd.new("ShaderNodeSeparateXYZ")
    ln.new(tc.outputs["Object"], sp.inputs[0])
    out = nd["Material Output"]
    ticks = []
    for step, w in ((0.1, 0.03), (1.0, 0.012)):
        dv = nd.new("ShaderNodeMath")
        dv.operation = 'DIVIDE'
        dv.inputs[1].default_value = step
        ln.new(sp.outputs["Z"], dv.inputs[0])
        fr = nd.new("ShaderNodeMath")
        fr.operation = 'FRACT'
        ln.new(dv.outputs[0], fr.inputs[0])
        lt = nd.new("ShaderNodeMath")
        lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = w
        ln.new(fr.outputs[0], lt.inputs[0])
        ticks.append(lt)
    mx = nd.new("ShaderNodeMath")
    mx.operation = 'MAXIMUM'
    ln.new(ticks[0].outputs[0], mx.inputs[0])
    ln.new(ticks[1].outputs[0], mx.inputs[1])
    dark = nd.new("ShaderNodeBsdfPrincipled")
    dark.inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
    dark.inputs["Roughness"].default_value = 0.5
    ms = nd.new("ShaderNodeMixShader")
    ln.new(mx.outputs[0], ms.inputs["Fac"])
    ln.new(b.outputs[0], ms.inputs[1])
    ln.new(dark.outputs[0], ms.inputs[2])
    ln.new(ms.outputs[0], out.inputs["Surface"])
    return m


def copper_mat():
    """a circulated cent: copper, a little tarnish, worn relief (noise bump), roughness never constant"""
    m = bpy.data.materials.get("BL_Copper")
    if m:
        return m
    m = _rough_var(mat("BL_Copper", **{"Metallic": 1.0}), 0.22, 0.42, 900, 0.25,
                   ((0.74, 0.36, 0.22, 1), (0.86, 0.47, 0.30, 1)))
    return m


# ---------------------------------------------------------------- geometry helpers
def _link(sc, o, name, mv=False):
    o.name = name
    o["bb"] = name
    if mv:
        o["mv"] = 1
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


def cone(sc, name, r1, r2, m, verts=24, smooth=True):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=1, location=(0, 0, 0.5))
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=True)
    o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return _link(sc, o, name)


def ball(sc, name, r, m, sx=1.0, sy=1.0, sz=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r)
    o = bpy.context.object
    o.scale = (sx, sy, sz)
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return _link(sc, o, name)


def disk(sc, name, r, depth, m):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=depth)
    o = bpy.context.object
    o.data.materials.append(m)
    return _link(sc, o, name)


def place(o, a, b):
    a, b = Vector(a), Vector(b)
    v = b - a
    o.location = a
    o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()
    o.scale = (1.0, 1.0, max(v.length, 1e-4))


def headform_mesh(sc, name, m):
    """UV sphere pushed out to the headform surface (tools/blender/headform.py): one smooth sculpted head"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=96, radius=1.0)
    o = bpy.context.object
    for v in o.data.vertices:
        v.co = Vector(headform.surface(tuple(v.co)))
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.use_smooth = True
    return _link(sc, o, name)


def head_point(local):
    """a point given in the head's own frame (x right, -y face, z up) -> world"""
    v = Vector(local)
    c, s = math.cos(HEAD_TILT), math.sin(HEAD_TILT)
    y = v.y * c - v.z * s
    z = v.y * s + v.z * c
    return Vector(HEAD_C) + Vector((v.x, y, z))


# ---------------------------------------------------------------- build
def build(res=(1080, 1920)):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window:
        bpy.context.window.scene = sc
    for o in list(sc.collection.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    rubber = _rough_var(mat("BL_Rubber", **{"Base Color": (0.025, 0.025, 0.027, 1)}), 0.55, 0.75, 20)
    steel = _rough_var(mat("BL_Steel", **{"Base Color": (0.62, 0.62, 0.63, 1), "Metallic": 1.0}), 0.28, 0.42, 14)
    vinyl = _rough_var(mat("BL_Vinyl", **{"Base Color": (0.92, 0.62, 0.06, 1), "Coat Weight": 0.3, "Coat Roughness": 0.15,
                                          "Subsurface Weight": 0.05}),
                       0.28, 0.42, 12, 0.02, ((0.90, 0.58, 0.05, 1), (0.95, 0.68, 0.08, 1)))
    stand = _rough_var(mat("BL_Stand", **{"Base Color": BASE_COL}), 0.75, 0.9, 6)
    tgt = target_mat()

    # ---- studio: floor + cyclorama wall (tall: the camera rides up to 442 m)
    cyc = _rough_var(mat("BL_Cyc", **{"Base Color": (0.42, 0.43, 0.45, 1)}), 0.75, 0.9, 0.5)
    box(sc, "Floor", (40.0, 40.0, 0.1), (0, 0, -0.05), cyc)
    box(sc, "Cyc", (40.0, 0.2, TOWER_TOP), (0, 3.2, TOWER_TOP / 2), cyc)
    # ---- drop tower: two rails behind the coin line with hazard marks, a clear guide tube with tick rings
    hz = rail_mat()
    for sx in (-1, 1):
        box(sc, f"Rail{sx}", (0.045, 0.045, TOWER_TOP), (sx * 0.17, 0.12, TUBE_BOT + TOWER_TOP / 2 + 0.05), hz, bevel=0.003)
    box(sc, "RailFoot", (0.42, 0.06, 0.04), (0, 0.12, TUBE_BOT + 0.05), steel, bevel=0.004)
    box(sc, "Release", (0.10, 0.10, 0.06), (0, 0.07, TUBE_BOT + 0.10), steel, bevel=0.006)   # release gate, above the head

    # ---- the BREAKPOINT LAB base on a stand, the headform on its neck
    box(sc, "Stand", (0.76, 0.56, BASE_TOP - 0.16), (0, 0.0, (BASE_TOP - 0.16) / 2), stand, bevel=0.004)
    add_logo_base(sc, width=0.80, height=0.16, depth=0.60, top_z=BASE_TOP)
    box(sc, "Bracket", (0.16, 0.16, 0.03), (0, 0.02, BASE_TOP + 0.015), steel, bevel=0.004)
    n1 = head_point(headform.surface((0, 0.15, -1)))
    n0 = Vector((0, 0.02, BASE_TOP + 0.03))
    nm = n1 + (n0 - n1).normalized() * 0.12               # Hybrid III neck: about 12 cm of rubber discs and plates
    place(cone(sc, "Post", 0.03, 0.03, steel, 24), n0, nm)
    place(cone(sc, "NeckCore", 0.017, 0.017, steel, 12), nm, n1)
    for i in range(4):
        a = nm + (n1 - nm) * (0.02 + 0.245 * i)
        place(cone(sc, f"NeckDisc{i}", 0.052, 0.052, rubber), a, a + (n1 - nm) * 0.17)
        place(cone(sc, f"NeckPlate{i}", 0.056, 0.056, steel, 32), a + (n1 - nm) * 0.17, a + (n1 - nm) * 0.2)
    hd = headform_mesh(sc, "Head", vinyl)
    hd.location = HEAD_C
    hd.rotation_euler = (HEAD_TILT, 0.0, 0.0)
    for sx in (-1, 1):                                   # quadrant targets on both temples
        o = disk(sc, f"THead{sx}", 0.028, 0.003, tgt)
        o.location = head_point(headform.surface((sx, 0.05, 0.12)))
        o.rotation_euler = (Matrix.Rotation(HEAD_TILT, 4, 'X') @ Matrix.Rotation(math.pi / 2, 4, 'Y')).to_euler()

    # ---- the penny: disc + raised rim, copper
    cu = copper_mat()
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=R_COIN, depth=T_COIN)
    coin = bpy.context.object
    md = coin.modifiers.new("Bevel", 'BEVEL')
    md.width = 0.0003
    md.segments = 3
    coin.data.materials.append(cu)
    for p in coin.data.polygons:
        p.use_smooth = True
    _link(sc, coin, "Coin", mv=True)
    for sz in (-1, 1):
        bpy.ops.mesh.primitive_torus_add(major_radius=R_COIN - 0.0006, minor_radius=0.00035,
                                         major_segments=96, minor_segments=8, location=(0, 0, sz * T_COIN / 2))
        rim = bpy.context.object
        rim.data.materials.append(cu)
        for p in rim.data.polygons:
            p.use_smooth = True
        _link(sc, rim, f"Rim{sz}")
        rim.parent = coin

    # ---- light: studio softboxes that ride with the camera (key front left, rim back right, top), the set lit for the logo
    for nm, e, size, off, col in (("Key", 80, 1.2, (-1.4, -1.6, 0.9), (1.0, 0.97, 0.93)),
                                  ("Rim", 90, 0.8, (1.3, 1.6, 0.6), (0.92, 0.95, 1.0)),
                                  ("Top", 70, 1.0, (0.0, -0.2, 1.8), (1.0, 0.98, 0.95))):
        lt = bpy.data.lights.new(nm, 'AREA')
        lt.energy = e
        lt.size = size
        lt.color = col
        lo = bpy.data.objects.new(nm, lt)
        lo["bb"] = nm
        lo["mv"] = 1
        lo["off"] = off
        sc.collection.objects.link(lo)
    lt = bpy.data.lights.new("SetKey", 'AREA')
    lt.energy = 400
    lt.size = 2.5
    lo = bpy.data.objects.new("SetKey", lt)
    lo.location = (-2.2, -3.2, 2.6)
    lo.rotation_euler = (Vector((0, 0, 1.2)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
    lo["bb"] = "SetKey"
    sc.collection.objects.link(lo)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 50
    cam.clip_start = 0.02
    cam.clip_end = 3000
    cam.dof.use_dof = False
    co = bpy.data.objects.new("Cam", cam)
    co["bb"] = "Cam"
    co["mv"] = 1
    sc.collection.objects.link(co)
    sc.camera = co

    wd = bpy.data.worlds.get("BL_LabWorld") or bpy.data.worlds.new("BL_LabWorld")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.57, 0.60, 1)
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
    sc.cycles.adaptive_threshold = 0.04
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4
    sc.cycles.transmission_bounces = 2
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
    except TypeError:
        pass
    sc.view_settings.exposure = 0.0
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass
    set_pose({"zc": Z_HIT + 3, "cx": 0, "tilt": 14, "yaw": 0, "cz": Z_HIT + 3, "d": 0.6, "wide": 0, "hit": -1, "mb": 0}, sc)
    return sc


# ---------------------------------------------------------------- pose
def set_pose(p, sc=None):
    sc = sc or bpy.data.scenes[SCENE]
    ob = {o.get("bb", o.name): o for o in sc.objects}
    for o in sc.objects:
        o.animation_data_clear()
    zc, cx = float(p["zc"]), float(p.get("cx", 0))
    coin = ob["Coin"]
    coin.location = (cx, 0.0, zc)
    coin.rotation_euler = (math.radians(float(p["tilt"])), 0.0, math.radians(float(p["yaw"])))

    wide = int(p.get("wide", 0))
    cz, d = float(p["cz"]), float(p["d"])
    cam = ob["Cam"]
    if wide:                                             # studio shot: base + logo, headform, the drop tower going up
        cam.location = (0.45, -3.6, 1.55)
        look = Vector((0.0, 0.0, 1.62))
        cam.data.lens = 50
    else:                                                # rides with the coin, front view, a little above
        look = Vector((0.0, 0.0, cz))
        cam.location = look + d * Vector((math.sin(AZ_LAB) * math.cos(EL_LAB), -math.cos(AZ_LAB) * math.cos(EL_LAB),
                                          math.sin(EL_LAB)))
        cam.data.lens = 50
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for nm in ("Key", "Rim", "Top"):                     # the softboxes ride with the camera target
        lo = ob[nm]
        lo.location = look + Vector(tuple(lo["off"]))
        lo.rotation_euler = (look - lo.location).to_track_quat('-Z', 'Y').to_euler()
    speed_blur(sc, float(p.get("mb", 0)))


def speed_blur(sc, mb):
    """the camera rides with the coin: the coin and the camera are keyed one frame apart, so the tower streaks"""
    sc.render.use_motion_blur = mb > 0.01
    if mb <= 0.01:
        return
    sc.render.motion_blur_shutter = 0.3
    for o in [o for o in sc.objects if o.get("mv") and o.parent is None]:
        for f, dz in ((0, mb), (1, 0.0), (2, -mb)):
            o.location.z += dz
            o.keyframe_insert("location", frame=f)
            o.location.z -= dz
        o.keyframe_insert("rotation_euler", frame=1)
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
