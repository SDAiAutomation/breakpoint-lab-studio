"""The Breakpoint Lab set, shared by every Blender scene: the light grey base with the BREAKPOINT LAB logo on its
front face, exactly like the press engine (engine/engine.html: dark "BREAKPOINT", gold "LAB", Poppins Bold).
The logo is the channel's signature: it must be visible, the same way, in every wide shot.

    from lab_set import add_logo_base
    add_logo_base(sc, width=0.40, height=0.06, depth=0.26, top_z=-0.004)
"""
import os

import bpy

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "engine", "fonts", "Poppins-Bold.ttf")
BASE_COL = (0.28, 0.28, 0.275, 1)        # reads like the press base once lit by the bright Blender studio (0.86 burnt to white)
DARK_COL = (0.008, 0.009, 0.011, 1)        # "BREAKPOINT"
GOLD_COL = (0.42, 0.17, 0.0, 1)        # "LAB"


def _mat(name, col, rough=0.5, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.15   # matte print: the bright studio must not wash the logo out
    return m


def _link(sc, o, key):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    sc.collection.objects.link(o)
    o["bb"] = key
    return o


def _text(sc, key, body, size, mat, x, y, z):
    cu = bpy.data.curves.new(key, type='FONT')
    cu.body = body
    cu.size = size
    cu.extrude = size * 0.015
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    try:
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    except RuntimeError:
        pass                                  # fallback: Blender's own font
    o = bpy.data.objects.new(key, cu)
    o.data.materials.append(mat)
    o.location = (x, y, z)
    o.rotation_euler = (1.5708, 0, 0)          # stand the text up on the front face (facing -Y, towards the camera)
    return _link(sc, o, key)


def add_logo_base(sc, width=0.40, height=0.06, depth=0.26, top_z=0.0):
    """base block (top at top_z) + logo on its front face; returns the base object"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, top_z - height / 2))
    base = bpy.context.object
    base.scale = (width, depth, height)
    base.name = "LabBase"
    bpy.ops.object.modifier_add(type='BEVEL')
    base.modifiers[-1].width = 0.003
    base.modifiers[-1].segments = 3
    base.data.materials.append(_mat("BL_LabBase", BASE_COL, 0.85))
    _link(sc, base, "LabBase")
    # logo: one text object "BREAKPOINT LAB" (dark + gold per character), centred by Blender itself,
    # never wider than 88% of the base
    size = height * 0.55
    lg = _text(sc, "Logo", "BREAKPOINT LAB", size, _mat("BL_LogoDark", DARK_COL, 0.9), 0, -depth / 2 - 0.0006, top_z - height / 2)
    lg.data.materials.append(_mat("BL_LogoGold", GOLD_COL, 0.8, 0.0))
    for i in range(len("BREAKPOINT "), len("BREAKPOINT LAB")):
        lg.data.body_format[i].material_index = 1
    for vl in sc.view_layers:
        vl.update()
    k = min(1.0, 0.88 * width / max(lg.dimensions.x, 1e-6))
    lg.scale = (k, k, k)
    return base
