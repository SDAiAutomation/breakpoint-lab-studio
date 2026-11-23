"""The Breakpoint Lab set, shared by every Blender scene: the light grey base with the BREAKPOINT LAB logo on its
front face, exactly like the press engine (engine/engine.html: dark "BREAKPOINT", gold "LAB", Poppins Bold).
The logo is the channel's signature: it must be visible, the same way, in every wide shot.

    from lab_set import add_logo_base
    add_logo_base(sc, width=0.40, height=0.06, depth=0.26, top_z=-0.004)
"""
import os

import bpy

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "engine", "fonts", "Poppins-Bold.ttf")
BASE_COL = (0.50, 0.50, 0.49, 1)        # reads like the press base once lit by the bright Blender studio (0.86 burnt to white)
DARK_COL = (0.03, 0.035, 0.04, 1)        # "BREAKPOINT"
GOLD_COL = (0.80, 0.45, 0.02, 1)        # "LAB"


def _mat(name, col, rough=0.5, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
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
    cu.extrude = size * 0.02
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
    base.data.materials.append(_mat("BL_LabBase", BASE_COL, 0.55))
    _link(sc, base, "LabBase")
    # logo: BREAKPOINT + LAB on one line, ~78% of the base width, centred on the front face
    size = height * 0.42
    y = -depth / 2 - 0.0006
    z = top_z - height / 2
    bp = _text(sc, "LogoBreakpoint", "BREAKPOINT", size, _mat("BL_LogoDark", DARK_COL, 0.4), 0, y, z)
    lab = _text(sc, "LogoLab", "LAB", size, _mat("BL_LogoGold", GOLD_COL, 0.35, 0.0), 0, y, z)
    for vl in sc.view_layers:
        vl.update()                                   # real text widths (font metrics), then lay out on one line
    w_bp, w_lab, gap = bp.dimensions.x, lab.dimensions.x, size * 0.35
    k = min(1.0, 0.78 * width / (w_bp + gap + w_lab))  # never wider than 78% of the base
    for o in (bp, lab):
        o.scale = (k, k, k)
    w_bp, w_lab, gap = w_bp * k, w_lab * k, gap * k
    x0 = -(w_bp + gap + w_lab) / 2
    bp.location.x = x0 + w_bp / 2
    lab.location.x = x0 + w_bp + gap + w_lab / 2
    return base
