"""Heads for the original portraits (docs/dev/co-kit.md): skull and jaw, neck, ear, drawn features (eyes, brows, nose, mouth in four expressions), hair styles built from locks,
beards and headgear, all drawn here (original art, GPL-3.0-or-later). A head faces right in three-quarter view like AW2's portraits; (cx, cy) is the point between the eyes and
`s` the scale (1.0 = the 48 x 48 mug's head)."""
import math
from .draw import Art

SK = ("sk_h", "sk_m", "sk_s")
HA = ("ha_h", "ha_m", "ha_s")
ST = ("st_h", "st_m", "st_s")
RD = ("rd_h", "rd_m", "rd_s")
JAWS = {
    "square":  [(17, -6), (17.5, 2), (16.5, 9), (14.5, 15), (10, 19.5), (1, 22), (-8, 20.5), (-14, 15), (-17, 7), (-17.5, -4), (-16, -12)],
    "pointed": [(17, -6), (17, 2), (15.5, 9), (12, 15.5), (7, 20.5), (1, 23.5), (-5, 21.5), (-11.5, 15.5), (-16, 7), (-17.5, -4), (-16, -12)],
    "angular": [(17, -6), (17.5, 2), (16.5, 9), (14, 15.5), (9, 20), (2, 22), (-6, 20), (-12.5, 14), (-16.5, 5), (-17.5, -4), (-16, -12)],
    "round":   [(17, -6), (17.5, 2), (16.5, 9.5), (14, 16), (8, 21), (0, 22.5), (-8, 21), (-14, 15.5), (-17.5, 7), (-18, -4), (-16.5, -12)],
}
TOP = [(-14, -17.5), (-6, -21), (4, -21.5), (12, -19), (16, -13)]


class P:
    """Head-relative coordinates to the canvas (x is compressed by `sx`: AW2's faces are long)."""

    def __init__(self, cx, cy, s, sx=0.92):
        self.cx, self.cy, self.s, self.sx = cx, cy, s, sx

    def __call__(self, x, y):
        return (self.cx + x * self.s * self.sx, self.cy + y * self.s)

    def pts(self, pts):
        return [self(x, y) for x, y in pts]

    def i(self, x, y):
        return (int(round(self.cx + x * self.s * self.sx)), int(round(self.cy + y * self.s)))

    def r(self, rx, ry):
        return (rx * self.s * self.sx, ry * self.s)


def ell(art, p, x, y, rx, ry):
    cx, cy = p(x, y)
    a, b = p.r(rx, ry)
    return art.ellipse(cx, cy, a, b)


def skull(art, p, jaw="square"):
    return art.poly(p.pts(TOP + JAWS[jaw]))


def draw_neck(art, p, width=10.5, to=40):
    m = art.poly(p.pts([(-width + 1, 10), (width - 1, 10), (width + 1, to), (-width - 1, to)]))
    art.paint(m, SK, hi=0, lo=3)
    sh = art.poly(p.pts([(-width + 1, 10), (width - 1, 10), (width - 2, 22), (-width + 3, 25)]))
    art.g[sh & m] = "sk_s"
    art.g[art.ring(m)] = "ol"
    return m


def _erode(art, m, l, r, t, b):
    """The mask without its outer l px on the left, r on the right, t on top, b at the bottom (a directional erosion for banded cel shading)."""
    e = m.copy()
    for k in range(1, l + 1):
        e &= art.shift(m, k, 0)
    for k in range(1, r + 1):
        e &= art.shift(m, -k, 0)
    for k in range(1, t + 1):
        e &= art.shift(m, 0, k)
    for k in range(1, b + 1):
        e &= art.shift(m, 0, -k)
    return e


def draw_face(art, p, jaw="square", ear=True, nose=True):
    """AW2's grammar: a lit face whose edges darken in two or three bands (light in the middle, the darkest tone at the contour), a small nose, almost no skin outline."""
    if ear:
        e = ell(art, p, -17.3, 2.5, 3.4, 5)
        art.paint(e, SK, hi=1, lo=1, edge="ol")
        art.dot(*p.i(-17.6, 1.5), "sk_s")
        art.dot(*p.i(-17.6, 3.0), "sk_s")
    face = skull(art, p, jaw)
    s = max(1, round(p.s))
    art.g[face] = "sk_s"
    mid = _erode(art, face, 1 * s, 2 * s, 1, 1 * s) & face
    art.g[mid] = "sk_m"
    hi = _erode(art, face, 3 * s, 3 * s, 2, 3 * s)
    art.g[hi & face] = "sk_h"
    # the temple and the jaw below the ear are a shade darker, the cheek keeps a little light
    art.g[art.poly(p.pts([(-17.5, -4), (-12, -4), (-12.5, 5), (-17.5, 8)])) & face] = "sk_m"
    if nose:
        x0, y0 = p.i(15.5, -1.5)
        for j, (xs, ln) in enumerate([(0, 2), (1, 2), (2, 1), (2, 1)]):
            for i in range(ln):
                art.g[y0 + j, x0 + xs + i] = "sk_m"
            art.g[y0 + j, x0 + xs + ln] = "sk_s"
        art.dot(x0 + 1, y0 + 4, "sk_s"), art.dot(x0 + 2, y0 + 4, "sk_s"), art.dot(x0, y0 + 3, "sk_s")
        art.dot(x0 - 1, y0 + 2, "sk_m"), art.dot(x0 - 1, y0 + 3, "sk_s")
    return face


# --- features --------------------------------------------------------------------------------------------------------------------------------------------------------

def _eye(art, x, y, w, kind):
    """An AW2-style eye, w wide and 4 high: a dark lid, a mostly dark iris with one white corner and a glint, a faint shadow under it."""
    if kind == "happy":
        for i in range(w):
            art.dot(x + i, y + 1 + (0 if 1 <= i < w - 1 else 1), "ol")
        return
    for i in range(w):
        art.dot(x + i, y, "ol")
    art.dot(x - 1, y, "ol") if w >= 6 else None
    for j in (1, 2):
        art.dot(x, y + j, "wh")
        for i in range(1, w - 1):
            art.dot(x + i, y + j, "ey")
        art.dot(x + w - 1, y + j, "ol" if j == 1 else "wh")
    art.dot(x + 1, y + 1, "wh")
    for i in range(1, w - 1):
        art.dot(x + i, y + 3, "sk_s")
    if kind == "sad":
        art.dot(x, y, "sk_m"), art.dot(x + w - 1, y + 1, "ol")
    if kind == "angry":
        art.dot(x + w - 1, y, "ol"), art.dot(x - 1, y + 1, "ol")


def draw_features(art, p, expr="normal", brow="stern", mouth=None, brow_slot="ha_s", smirk=False, wrinkles=False, near=None, far=None, eye_dy=0, half_lid=False, lashes=False):
    """Eyes, brows, mouth. expr: normal, happy, sad, angry. brow: stern, arch, sharp, flat, haughty."""
    near = near or 6
    far = far or 5
    ox, oy = p.i(-12.0, -4 + eye_dy)
    fx, fy = p.i(3.5, -4 + eye_dy)
    kind = expr if expr in ("happy", "sad", "angry") else "normal"
    _eye(art, ox, oy, near, kind)
    _eye(art, fx, fy, far, kind)
    if half_lid and kind == "normal":     # a lazy, arrogant eye: the lid comes down over the top of the eyeball
        for i in range(near):
            art.dot(ox + i, oy + 1, "ol")
        for i in range(far):
            art.dot(fx + i, fy + 1, "ol")
    if lashes and kind != "happy":
        art.dot(ox - 1, oy, "ol"), art.dot(ox - 2, oy - 1, "ol")

    def b(x, y, w, tilt, th=1):
        for i in range(w):
            yy = y + round(tilt * (i / max(1, w - 1)))
            for t in range(th):
                art.dot(x + i, yy + t, brow_slot)
    bk = {"angry": "sharp", "sad": "sadbrow"}.get(expr, brow)
    if bk == "stern":
        b(ox - 1, oy - 3, near + 1, 0, 2), b(fx, oy - 3, far + 1, 0, 2)
    elif bk == "arch":
        b(ox, oy - 4, near, -1), b(fx, oy - 4, far + 1, 1)
    elif bk == "sharp":
        b(ox - 1, oy - 4, near + 1, 2, 2), b(fx, oy - 2, far + 1, -2, 2)
    elif bk == "flat":
        b(ox, oy - 3, near, 0), b(fx, oy - 3, far, 0)
    elif bk == "haughty":
        b(ox, oy - 5, near, -1, 1), b(fx, oy - 3, far + 1, 1, 2)
    elif bk == "sadbrow":
        b(ox - 1, oy - 3, near, -2), b(fx, oy - 4, far, 2)
    mx, my = p.i(-1, 8.5)
    mk = mouth or {"normal": "firm", "happy": "grin", "sad": "down", "angry": "grit"}[expr]
    if mk == "firm":
        for i in range(8):
            art.dot(mx + i, my, "ol")
        art.dot(mx + 8, my - 1 if smirk else my, "ol")
        for i in range(1, 7):
            art.dot(mx + i, my + 1, "lip")
        if wrinkles:
            art.dot(mx - 2, my - 2, "sk_s"), art.dot(mx - 2, my - 1, "sk_s"), art.dot(mx - 3, my, "sk_s")
    elif mk == "smirk":
        for i in range(6):
            art.dot(mx + i, my + (1 if i < 2 else 0), "ol")
        art.dot(mx + 6, my - 1, "ol"), art.dot(mx + 7, my - 2, "ol"), art.dot(mx + 8, my - 2, "sk_s")
        for i in range(2, 6):
            art.dot(mx + i, my + 1, "lip")
    elif mk == "grin":
        for i in range(9):
            art.dot(mx - 1 + i, my - (1 if i in (0, 8) else 0), "ol")
        for i in range(1, 8):
            art.dot(mx - 1 + i, my + 1, "wh")
            art.dot(mx - 1 + i, my + 2, "lip")
        for i in range(2, 7):
            art.dot(mx - 1 + i, my + 3, "ol")
    elif mk == "down":
        for i in range(7):
            art.dot(mx + i, my + (1 if i in (0, 6) else 0), "ol")
        art.dot(mx - 1, my + 2, "ol"), art.dot(mx + 7, my + 2, "ol")
        for i in range(2, 5):
            art.dot(mx + i, my + 1, "lip")
    elif mk == "grit":
        for i in range(8):
            art.dot(mx + i, my, "ol"), art.dot(mx + i, my + 1, "wh" if 1 <= i <= 6 else "ol"), art.dot(mx + i, my + 2, "ol")
        art.dot(mx + 3, my + 1, "ol")
    elif mk == "calm":
        for i in range(7):
            art.dot(mx + i, my, "ol")
        for i in range(1, 6):
            art.dot(mx + i, my + 1, "lip")
        if smirk:
            art.dot(mx + 7, my - 1, "ol")
    elif mk == "pursed":
        for i in range(6):
            art.dot(mx + 1 + i, my, "ol")
        art.dot(mx + 7, my + 1, "ol")
        for i in range(2, 6):
            art.dot(mx + i, my + 1, "lip")


# --- hair: built from locks -----------------------------------------------------------------------------------------------------------------------------------------

def lock(art, p, root, tip, width, ramp=HA, bend=0.0):
    """A leaf-shaped lock of hair from `root` to `tip` (head coordinates), `width` wide at the belly, bent sideways by `bend`."""
    (rx, ry), (tx, ty) = root, tip
    dx, dy = tx - rx, ty - ry
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    pts = []
    n = 6
    for k in range(n + 1):
        t = k / n
        w = width * math.sin(math.pi * min(1, t * 0.9 + 0.1)) * 0.5
        c = bend * math.sin(math.pi * t)
        pts.append((rx + dx * t + nx * (w + c), ry + dy * t + ny * (w + c)))
    for k in range(n, -1, -1):
        t = k / n
        w = width * math.sin(math.pi * min(1, t * 0.9 + 0.1)) * 0.5
        c = bend * math.sin(math.pi * t)
        pts.append((rx + dx * t - nx * (w - c), ry + dy * t - ny * (w - c)))
    m = art.poly(p.pts(pts))
    art.paint(m, ramp, hi=1, lo=1, edge="ol")
    return m


def hair_back(art, p, style, ramp=HA):
    if style in ("bun", "melon", "ringlets"):
        m = ell(art, p, -21, 3 if style != "ringlets" else 9, 7, 8)
        art.paint(m, ramp, hi=2, lo=2)
        for k in range(3):
            art.line([p(-26, -2 + k * 5), p(-17, 0 + k * 5)], ramp[2], 1)
    elif style == "braid_crown":
        m = ell(art, p, -20, 1, 6.5, 8)
        art.paint(m, ramp, hi=2, lo=2)
    elif style == "ponytail":
        for k in range(3):
            lock(art, p, (-17, -12 + k * 3), (-27 - k * 2, 6 + k * 7), 8, ramp, bend=-2)
    elif style == "braid_long":
        for k in range(6):
            m = ell(art, p, -21 + k * 0.4, 6 + k * 6.5, 3.8, 3.6)
            art.paint(m, ramp, hi=1, lo=1)
    elif style == "long":
        m = art.poly(p.pts([(-17, -14), (-24, -2), (-25, 18), (-18, 26), (-12, 16), (-16, 0)]))
        art.paint(m, ramp, hi=2, lo=2)


def hair_front(art, p, style, ramp=HA):
    if style in ("bald", "none"):
        return
    base_outer = [(-18.5, -3), (-19.5, -12), (-15, -19.5), (-7, -24.5), (3, -26), (12, -23.5), (18, -18), (19.5, -11)]
    if style in ("caesar", "crop", "slick", "curls", "ponytail"):
        hl = {"caesar": [(-18, -2), (-14, -8), (-9, -8.5), (-5, -7.5), (-1, -9), (4, -7.5), (9, -9.5), (14, -8.5), (18, -10)],
              "crop": [(-18, -2), (-15, -9), (-9, -10.5), (-3, -11.5), (4, -10.5), (10, -12), (15, -12), (18, -12)],
              "slick": [(-18, -2), (-15, -10), (-8, -13), (-1, -15), (6, -14.5), (12, -13), (18, -13)],
              "curls": [(-18, -3), (-14, -9), (-8, -10), (-2, -11), (4, -10), (10, -11), (18, -11)],
              "ponytail": [(-18, -2), (-15, -9), (-9, -11), (-3, -12), (4, -12.5), (11, -11.5), (18, -11)]}[style]
        m = art.poly(p.pts(base_outer + list(reversed(hl))))
        art.paint(m, ramp, hi=2, lo=2)
        if style == "curls":
            for (x, y) in [(-16, -8), (-12, -15), (-6, -20), (1, -23), (8, -21), (14, -16), (-10, -10), (-3, -14), (4, -16), (11, -12), (16, -12), (-17, -15), (-1, -19)]:
                art.paint(ell(art, p, x, y, 3.8, 3.4), ramp, hi=1, lo=1)
        elif style == "slick":
            for k in range(7):
                art.line([p(15 - k * 4.4, -23 + abs(k - 3) * 0.6), p(9 - k * 4.2, -14 - (k % 2))], ramp[0] if k % 2 == 0 else ramp[2], 1)
        else:
            tips = [(-14, -8), (-9, -9), (-4, -8), (1, -9.5), (6, -8), (11, -9.5), (15, -8.5)] if style == "caesar" else [(-14, -9), (-8, -11), (-2, -12), (4, -11), (10, -12.5), (15, -12)]
            for k, tip in enumerate(tips):
                lock(art, p, (-6 + k * 2.5, -24), (tip[0], tip[1] + 1.5), 7, ramp, bend=(1 if k % 2 else -1))
        art.paint(art.poly(p.pts([(-19, -4), (-15.5, 2), (-16.5, 7), (-18.5, 0)])), ramp, hi=0, lo=0, edge=None)
        # tufts breaking the silhouette
        tufts = {"caesar": [((-4, -25), (-6, -30), 5), ((6, -24), (10, -29), 5)],
                 "crop": [((-3, -25), (-5, -30), 5), ((7, -24), (11, -28), 5)],
                 "slick": [((5, -25), (10, -28), 5)],
                 "ponytail": [((-2, -25), (-4, -29), 5)]}.get(style, [])
        for root, tip, w in tufts:
            lock(art, p, root, tip, w, ramp, bend=1)
        return
    if style in ("bun", "melon", "braid_crown", "ringlets", "braid_long", "long"):
        hl = [(-18, -2), (-15, -8), (-9, -11.5), (-2, -13), (6, -12.5), (12, -11), (18, -11)]
        m = art.poly(p.pts(base_outer + list(reversed(hl))))
        art.paint(m, ramp, hi=2, lo=2)
        if style == "braid_crown":
            for k in range(10):
                a = math.pi * (1 - k / 9)
                art.paint(ell(art, p, -1 + 17.5 * math.cos(a), -11.5 - 12.5 * math.sin(a), 3.6, 3.1), ramp, hi=1, lo=1)
        elif style == "melon":
            for k in range(6):
                x = -14 + k * 5.6
                art.line([p(x, -24), p(x + 1.2, -12.5)], ramp[2], 1)
        else:
            art.line([p(1, -26), p(2, -12.5)], ramp[2], 1)
            for k in range(3):
                art.line([p(-12 + k * 9, -23), p(-10 + k * 9, -14)], ramp[0], 1)
        if style == "ringlets":
            for (x, y) in [(-21, -2), (-22, 5)]:
                art.paint(ell(art, p, x, y, 3.4, 3.4), ramp, hi=1, lo=1)


def beard(art, p, kind, ramp=HA):
    if kind == "full":
        m = art.poly(p.pts([(-17.5, 3), (-16.5, 12), (-10, 20), (0, 25), (9, 22.5), (15, 16.5), (17.5, 9), (15.5, 7), (12, 12.5), (7, 14.5), (0, 15), (-8, 13.5), (-13, 8.5), (-15, 1)]))
        art.paint(m, ramp, hi=2, lo=2)
        art.paint(art.poly(p.pts([(1, 4.5), (9, 4), (16, 5.5), (11, 8), (4, 7.5)])), ramp, hi=1, lo=1)
        for k in range(5):
            art.line([p(-12 + k * 5, 15 + (k % 2)), p(-11 + k * 5, 21 - (k % 2))], ramp[2], 1)
    elif kind == "stubble":
        m = art.poly(p.pts([(-16, 5), (-14, 12), (-8, 18), (0, 21), (8, 19), (13, 14), (16, 8), (12, 9), (8, 14), (0, 16), (-8, 14), (-13, 8)]))
        ys, xs = m.nonzero()
        for y, x in zip(ys, xs):
            if (x + 2 * y) % 3 == 0 and art.g[y, x] in ("sk_m", "sk_s", "sk_h"):
                art.g[y, x] = "sk_s"
    elif kind == "goatee":
        art.paint(art.poly(p.pts([(0, 15), (11, 14), (9, 22), (3, 24)])), ramp, hi=1, lo=1)


def laurel(art, p, leaf=("lf_h", "lf_m"), berry="gd_m", y=-2, width=18.5, rise=19, side="front"):
    """A laurel wreath following the brow: a band of overlapping leaves along a half-ellipse from temple to temple over the head, berries at the front."""
    seen = set()
    for k in range(0, 181, 3):
        a = math.radians(k)
        x, yy = p.i(width * math.cos(a), y - rise * math.sin(a))
        # a leaf: a 3 x 2 diamond pointing along the arc
        dx = 1 if k < 90 else -1
        for (ox, oy, c) in ((0, 0, leaf[0]), (dx, 0, leaf[1]), (-dx, 1, "lf_m"), (0, 1, leaf[1]), (dx, -1, leaf[0]), (0, -1, leaf[1]), (-dx, 0, "lf_m")):
            if (x + ox, yy + oy) not in seen:
                seen.add((x + ox, yy + oy))
                art.dot(x + ox, yy + oy, c)
        if k % 15 == 0:
            art.dot(x, yy + 2, "ol")
    q = p.i(width * 0.97, y - 1)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (0, -2), (1, -2)):
        art.dot(q[0] + dx, q[1] + dy, berry if (dx + dy) % 2 == 0 else "gd_s")


def galea(art, p, steel=ST, crest=RD, trim="gd_m", crest_kind="transverse", crest_h=9, cheek=True):
    """A Roman helmet over the skull: dome, brow band, neck guard behind, cheek plate before the ear, a crest."""
    dome = art.poly(p.pts([(-19.5, -3), (-20, -12), (-15, -20), (-6, -25.5), (5, -26.5), (14, -23), (19.5, -15), (19.5, -8), (17.5, -3.5)]))
    if crest_kind == "transverse":
        c = art.poly(p.pts([(-15, -21), (-9, -23 - crest_h), (-1, -25.5 - crest_h), (8, -25.5 - crest_h), (14, -22 - crest_h * 0.6), (17, -18)]))
        art.paint(c, crest, hi=2, lo=2)
        for k in range(6):
            art.line([p(-12 + k * 5, -22 - crest_h * 0.7), p(-11 + k * 5, -19)], crest[2], 1)
    elif crest_kind == "plume":
        c = art.poly(p.pts([(-4, -25), (-14, -27 - crest_h), (-26, -22 - crest_h * 0.6), (-30, -10), (-24, -8), (-18, -16), (-10, -20)]))
        art.paint(c, crest, hi=2, lo=2)
        for k in range(5):
            art.line([p(-6 - k * 4.5, -26 - crest_h * 0.6 + k), p(-9 - k * 4, -14)], crest[2], 1)
    if cheek:
        g = art.poly(p.pts([(-19.5, -4), (-25, 8), (-20, 13), (-15.5, 2)]))
        art.paint(g, steel, hi=1, lo=2)
    art.paint(dome, steel, hi=3, lo=3)
    art.paint(art.poly(p.pts([(-20, -6.5), (20, -6.7), (19.5, -3.2), (-20, -3.2)])), (trim, trim), hi=0, lo=0)
    art.line([p(-14, -17), p(-8, -22), p(2, -24)], steel[0], 1)
    if cheek:
        c = art.poly(p.pts([(-18, -2), (-17, 10), (-12, 13), (-11, 2)]))
        art.paint(c, steel, hi=1, lo=1)
        art.dot(*p.i(-14, 5), trim)
