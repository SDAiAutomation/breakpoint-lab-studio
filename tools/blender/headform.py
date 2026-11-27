"""Crash-test headform shape (Hybrid-III-like), shared by the Blender scene and by the contact computation.

Local frame: x to the head's right, -y = the face, z up, origin at the head centre (metres).
radius(d) gives the surface distance along the unit direction d: an ellipsoid (155 mm wide, 196 mm long,
230 mm high with the jaw) with a nose, a brow ridge, eye sockets, cheekbones, a chin and flat ears.
No bpy here: pure math.
"""
import math

RX, RY, RZ = 0.0775, 0.098, 0.112


def _g(d, c, s):
    """gaussian bump on the sphere of directions: centre c (unit), angular width s (rad, can be (sx, sz))"""
    dot = max(-1.0, min(1.0, d[0] * c[0] + d[1] * c[1] + d[2] * c[2]))
    a = math.acos(dot)
    return math.exp(-(a / s) ** 2)


def _n(v):
    m = math.sqrt(sum(x * x for x in v))
    return tuple(x / m for x in v)


NOSE = _n((0.0, -0.97, -0.08))
NOSE_TIP = _n((0.0, -0.95, -0.22))
BROW_L, BROW_R = _n((-0.32, -0.88, 0.30)), _n((0.32, -0.88, 0.30))
EYE_L, EYE_R = _n((-0.36, -0.88, 0.12)), _n((0.36, -0.88, 0.12))
CHEEK_L, CHEEK_R = _n((-0.55, -0.75, -0.10)), _n((0.55, -0.75, -0.10))
CHIN = _n((0.0, -0.80, -0.60))
EAR_L, EAR_R = (-1.0, 0.05, 0.0), (1.0, 0.05, 0.0)


def radius(d):
    x, y, z = d
    # ellipsoid
    r = 1.0 / math.sqrt((x / RX) ** 2 + (y / RY) ** 2 + (z / RZ) ** 2)
    # flatter face plane, fuller back of the skull
    if y < 0:
        r *= 1.0 - 0.06 * (-y) ** 3
    # the jaw: narrower towards the bottom and the back, the chin forward
    if z < -0.2:
        k = min(1.0, (-z - 0.2) / 0.6)
        r *= 1.0 - 0.18 * k * (0.6 + 0.4 * max(0.0, y))
    r += 0.011 * _g(d, CHIN, 0.22)
    # nose ridge and tip, brow ridge, eye sockets, cheekbones, ears
    r += 0.010 * _g(d, NOSE, 0.10) + 0.012 * _g(d, NOSE_TIP, 0.075)
    r += 0.005 * (_g(d, BROW_L, 0.16) + _g(d, BROW_R, 0.16))
    r -= 0.008 * (_g(d, EYE_L, 0.10) + _g(d, EYE_R, 0.10))
    r += 0.004 * (_g(d, CHEEK_L, 0.18) + _g(d, CHEEK_R, 0.18))
    r += 0.006 * (_g(d, EAR_L, 0.14) + _g(d, EAR_R, 0.14))
    return r


def surface(d):
    d = _n(d)
    r = radius(d)
    return (d[0] * r, d[1] * r, d[2] * r)


def rot_x(v, ang):
    """rotate a local vector about x (Blender rotation_euler.x = ang)"""
    c, s = math.cos(ang), math.sin(ang)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)


def top_along_vertical(center, tilt, x=0.0, y=0.0, n=400):
    """highest point of the tilted head on the vertical line (x, y): the coin's contact height"""
    best = None
    for i in range(n):
        th = math.pi * i / (n - 1)
        for j in range(2 * n):
            ph = 2 * math.pi * j / (2 * n)
            d = (math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))
            p = rot_x(surface(d), tilt)
            wx, wy, wz = center[0] + p[0], center[1] + p[1], center[2] + p[2]
            if abs(wx - x) < 0.0015 and abs(wy - y) < 0.0015 and (best is None or wz > best[0]):
                best = (wz, d)
    return best
