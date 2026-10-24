"""Bodies, garments and props of the original portraits (docs/dev/co-kit.md), drawn here (original art, GPL-3.0-or-later) on the 128 x 160 figure canvas: Roman armour (lorica
segmentata, muscle cuirass, pteruges, cingulum), cloaks (paludamentum, palla) and drapery (toga, stola), arms with bracers and hands, props (gladius hilt, scroll, wax tablet,
compass, abacus, coin purse, scales). Figures face right, turned three-quarters; the shoulders are at about y = 62."""
import math
from .draw import Art
from . import heads

SK = heads.SK
ST = heads.ST
RD = heads.RD
GD = ("gd_h", "gd_m", "gd_s")
CR = ("cr_h", "cr_m", "cr_s")
LT = ("lt_h", "lt_m", "lt_s")
PU = ("pu_h", "pu_m", "pu_s")


def ring_edge(art, m, slot="ol"):
    art.g[art.ring(m)] = slot


def stripes(art, m, pts_list, slot, width=1):
    for pts in pts_list:
        mm = art.thick(pts, width, round_caps=False) & m
        art.g[mm] = slot


def limb(art, pts, width, ramp, edge="ol", hi=2, lo=2):
    m = art.thick(pts, width)
    art.paint(m, ramp, edge=edge, hi=hi, lo=lo)
    return m


def hand(art, x, y, r=4.2, ramp=SK, fist=True):
    m = art.ellipse(x, y, r, r * 0.9)
    art.paint(m, ramp, hi=1, lo=1)
    if fist:
        for k in (-1.5, 0.5, 2.5):
            art.dot(x + k, y - 0.5, "sk_s")
    return m


def bracer(art, p0, p1, width, ramp=LT, studs="gd_m"):
    m = limb(art, [p0, p1], width, ramp, hi=1, lo=1)
    for t in (0.2, 0.5, 0.8):
        art.dot(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, studs)
    return m


def pteruges(art, x0, x1, y0, n, length, ramp=LT, studs="gd_m", slant=0):
    """A skirt of leather strips (pteruges) hanging from y0, n strips between x0 and x1."""
    w = (x1 - x0) / n
    for k in range(n):
        xa = x0 + k * w
        m = art.poly([(xa, y0), (xa + w, y0), (xa + w - 0.5 + slant, y0 + length - 2), (xa + w / 2 + slant, y0 + length), (xa + 0.5 + slant, y0 + length - 2)])
        art.paint(m, ramp, hi=1, lo=1)
        art.dot(xa + w / 2, y0 + 2, studs)


def belt(art, x0, y0, x1, y1, ramp=LT, plates=3, plate="gd_m"):
    m = art.poly([(x0, y0), (x1, y0 - 1), (x1, y1 - 1), (x0, y1)])
    art.paint(m, ramp, hi=1, lo=1)
    for k in range(plates):
        t = (k + 0.5) / plates
        x = x0 + (x1 - x0) * t
        art.paint(art.rect(x - 2, y0 - 1 + (y1 - y0) * 0, x + 2, y1 - 0), (plate, plate), hi=0, lo=0)
    return m


def fibula(art, x, y, r=3.2):
    """A round gold cloak clasp."""
    m = art.ellipse(x, y, r, r)
    art.paint(m, GD, hi=1, lo=1)
    art.dot(x, y, "rd_m")
    return m


def paludamentum(art, pts_back, pts_front=None, ramp=RD, clasp=None):
    """A cloak behind the shoulders (and a drape over one shoulder in front)."""
    m = art.poly(pts_back)
    art.paint(m, ramp, hi=2, lo=3)
    for k in range(4):
        a = pts_back[1 + k % (len(pts_back) - 2)]
    return m


def scroll(art, x, y, length=22, tilt=-0.4, ramp=CR):
    ex, ey = x + length * math.cos(tilt), y + length * math.sin(tilt)
    m = art.thick([(x, y), (ex, ey)], 6)
    art.paint(m, ramp, hi=1, lo=1)
    for (cx, cy) in ((x, y), (ex, ey)):
        art.paint(art.ellipse(cx, cy, 3.3, 3.3), GD, hi=1, lo=1)
    art.line([(x + 3, y), (x + length * 0.5, y + (ey - y) * 0.5 - 1)], "cr_s", 1)
    return m


def tablet(art, x, y, w=14, h=18, ramp=LT):
    m = art.poly([(x, y), (x + w, y - 2), (x + w + 1, y + h - 2), (x + 1, y + h)])
    art.paint(m, ramp, hi=1, lo=1)
    inner = art.poly([(x + 2, y + 2), (x + w - 2, y), (x + w - 1, y + h - 4), (x + 3, y + h - 2)])
    art.paint(inner, ("cr_h", "cr_m"), hi=0, lo=0, edge="lt_s")
    for k in range(4):
        art.line([(x + 4, y + 5 + k * 3.2), (x + w - 3, y + 3.5 + k * 3.2)], "lt_s", 1)
    return m


def hilt(art, x, y, tilt=0.0):
    """A gladius hilt held in a fist: grip, guard, pommel."""
    art.paint(art.thick([(x, y), (x + 2 * math.cos(tilt), y + 12)], 4), LT, hi=1, lo=1)
    art.paint(art.rect(x - 5, y - 4, x + 6, y - 1), GD, hi=1, lo=1)
    art.paint(art.ellipse(x, y + 14, 3, 3), GD, hi=1, lo=1)


def sheath(art, x0, y0, x1, y1, w=7):
    m = art.thick([(x0, y0), (x1, y1)], w, round_caps=False)
    art.paint(m, LT, hi=1, lo=1)
    for t in (0.0, 0.35, 0.7):
        art.paint(art.thick([(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t), (x0 + (x1 - x0) * t + 0.01, y0 + (y1 - y0) * t + 0.01)], w + 1, round_caps=False), GD, hi=0, lo=0)
    return m


def compass(art, x, y, size=18, ramp=GD):
    """A pair of dividers: two legs from a hinge, points down, opened."""
    art.paint(art.thick([(x, y), (x - size * 0.42, y + size)], 3, False), ramp, hi=1, lo=1)
    art.paint(art.thick([(x, y), (x + size * 0.42, y + size * 0.96)], 3, False), ramp, hi=1, lo=1)
    art.paint(art.ellipse(x, y, 3, 3), ramp, hi=1, lo=1)
    art.dot(x, y, "ol")


def abacus(art, x, y, w=24, h=14):
    m = art.poly([(x, y), (x + w, y - 3), (x + w + 1, y + h - 3), (x + 1, y + h)])
    art.paint(m, LT, hi=1, lo=1)
    for k in range(3):
        yy = y + 3 + k * 3.8
        art.line([(x + 2, yy), (x + w - 2, yy - 3 * 0.9)], "lt_s", 1)
        for j in range(4):
            bx = x + 4 + j * 5 + (k % 2) * 2
            art.paint(art.ellipse(bx, yy - (bx - x) * 0.12, 1.6, 1.5), GD, hi=0, lo=0, edge="gd_s")


def purse(art, x, y, r=7):
    m = art.ellipse(x, y, r, r * 1.1)
    art.paint(m, LT, hi=2, lo=2)
    art.paint(art.poly([(x - r * 0.6, y - r * 0.9), (x + r * 0.6, y - r * 0.9), (x + r * 0.5, y - r * 1.5), (x - r * 0.5, y - r * 1.5)]), LT, hi=1, lo=1)
    art.line([(x - r * 0.6, y - r * 0.8), (x + r * 0.6, y - r * 0.8)], "gd_m", 1)
    art.dot(x, y + 1, "gd_m")


def coin(art, x, y, r=3):
    art.paint(art.ellipse(x, y, r, r), GD, hi=1, lo=1)
    art.dot(x, y, "gd_s")


def scales(art, x, y, span=15):
    art.line([(x - span, y), (x + span, y - 1)], "gd_m", 1)
    art.line([(x, y - 6), (x, y + 3)], "gd_m", 1)
    for sx in (-span, span):
        art.line([(x + sx, y), (x + sx - 4, y + 9)], "gd_s", 1), art.line([(x + sx, y), (x + sx + 4, y + 9)], "gd_s", 1)
        art.paint(art.ellipse(x + sx, y + 10, 5, 2.2), GD, hi=1, lo=1)


# --- torsos -------------------------------------------------------------------------------------------------------------------------------------------------------

FEM = False


def base_torso(art, ramp, x0=26, x1=100, ytop=60, ybottom=160, waist=(36, 92)):
    """The body under the clothes: shoulders sloping to a narrower waist (a slighter frame when FEM)."""
    if FEM:
        x0, x1, waist = 33, 94, (42, 88)
    m = art.poly([(x0 + 6, ytop + 4), (52, ytop - 2), (78, ytop - 2), (x1 - 4, ytop + 3), (x1, ytop + 16), (waist[1] + 6, 118), (waist[1] + 4, ybottom), (waist[0] - 4, ybottom), (waist[0] - 4, 118), (x0 - 2, ytop + 16)])
    art.paint(m, ramp, hi=3, lo=6)
    return m


def lorica(art, ramp=ST, strap=LT, gold="gd_m", under=RD):
    """Lorica segmentata: a tunic under it, shoulder guards of three overlapping bands, curved plates across the chest, a leather strap down the front, buckles."""
    torso = base_torso(art, under)
    chest = art.poly([(30, 70), (40, 62), (54, 60), (76, 60), (90, 62), (98, 70), (96, 100), (90, 118), (40, 118), (32, 100)])
    art.paint(chest, ramp, hi=0, lo=0, edge=None)
    for k in range(6):
        y = 68 + k * 8.2
        sag = 3 + (1 if k > 2 else 0)
        band = art.poly([(30 + k * 1.1, y + 1), (46, y + sag), (62, y + sag + 1.6), (80, y + sag), (97 - k * 1.1, y + 1), (96 - k * 1.1, y + 8.4), (80, y + sag + 8.4), (62, y + sag + 9.8), (46, y + sag + 8.4), (31 + k * 1.1, y + 8.4)]) & chest
        art.paint(band, ramp, hi=1, lo=1, edge="ol")
        art.dot(42 + k, y + 3, ramp[0]), art.dot(43 + k, y + 3, ramp[0])
    art.paint(art.poly([(59, 61), (65, 60), (67, 118), (57, 118)]) & chest, strap, hi=1, lo=1)
    for k in range(5):
        art.dot(62, 70 + k * 10, gold), art.dot(61, 70 + k * 10, gold)
    for sx, sgn in ((36, -1), (90, 1)):
        for k in range(3):
            g = art.ellipse(sx + sgn * (3 + k * 1.2), 66 + k * 5.4, 13 - k * 1.2, 7)
            art.paint(g, ramp, hi=1, lo=1)
        art.dot(sx + sgn * 3, 62, ramp[0]), art.dot(sx + sgn * 5, 63, ramp[0])
    return torso


def muscle_cuirass(art, ramp=GD, ol="ol"):
    """A sculpted bronze breastplate: pectorals, a ridge down the middle, abdominal plates, a collar, shoulder straps."""
    m = art.poly([(36, 64), (54, 59), (76, 59), (92, 63), (94, 84), (90, 106), (84, 124), (44, 124), (36, 106), (32, 84)])
    art.paint(m, ramp, hi=2, lo=3)
    for (cx, cy, rx, ry) in ((50, 76, 14, 10), (77, 75, 14, 10)):
        e = art.ellipse(cx, cy, rx, ry) & m
        art.paint(e, ramp, hi=2, lo=2, edge=ramp[2])
    art.line([(63, 62), (63, 122)], ramp[2], 1)
    for k in range(4):
        y = 94 + k * 7.5
        art.paint(art.poly([(48, y), (62, y - 0.5), (62, y + 6), (48, y + 6.5)]) & m, ramp, hi=1, lo=1, edge=ramp[2])
        art.paint(art.poly([(64, y), (78, y - 1), (78, y + 5.5), (64, y + 6)]) & m, ramp, hi=1, lo=1, edge=ramp[2])
    return m


def folds(art, m, ramp, starts, ends, dark=True):
    """Fold lines of cloth: long strokes in the shadow tone with a highlight stroke beside each."""
    for (a, b) in zip(starts, ends):
        mm = art.thick([a, ((a[0] + b[0]) / 2 + 1, (a[1] + b[1]) / 2), b], 1, round_caps=False) & m
        art.g[mm] = ramp[2] if dark else ramp[0]
        mm2 = art.thick([(a[0] + 2, a[1] + 1), ((a[0] + b[0]) / 2 + 3, (a[1] + b[1]) / 2), (b[0] + 2, b[1])], 1, round_caps=False) & m
        art.g[mm2 & (art.g == ramp[1])] = ramp[0]


def tunic(art, ramp=RD, sleeve=True):
    m = base_torso(art, ramp)
    folds(art, m, ramp, [(40 + k * 11, 100 + (k % 2) * 6) for k in range(5)], [(38 + k * 11, 158) for k in range(5)])
    return m


def toga(art, ramp=CR, border=PU):
    """A draped toga: a heavy fold across from the far shoulder to the near hip, hanging pleats, a coloured border along the drape's edge."""
    m = base_torso(art, ramp)
    drape = art.poly([(92, 60), (100, 70), (94, 118), (80, 160), (36, 160), (48, 118), (66, 92), (80, 74)])
    art.paint(drape, ramp, hi=2, lo=3)
    art.line([(79, 73), (66, 92), (48, 118), (36, 158)], border[1], 3)
    art.line([(78, 71), (65, 90), (47, 116)], border[0], 1)
    folds(art, drape, ramp, [(82 - k * 7, 100 + k * 4) for k in range(5)], [(76 - k * 7, 158) for k in range(5)])
    for k in range(3):
        art.line([(60 - k * 6, 96 + k * 8), (52 - k * 7, 126 + k * 3)], ramp[0], 1)
    return m


def stola(art, ramp=CR, border=PU):
    """A long dress belted high with a shoulder drape (palla)."""
    m = base_torso(art, ramp, waist=(38, 90))
    art.line([(48, 82), (80, 79)], border[1], 3)    # the belt under the bust
    folds(art, m, ramp, [(42 + k * 9, 92 + k * 0.6) for k in range(6)], [(40 + k * 9.5, 158) for k in range(6)])
    art.line([(34, 70), (36, 150)], border[1], 3)   # border down the near side
    art.line([(94, 68), (92, 150)], border[1], 3)
    return m


def palla(art, ramp=PU):
    """A shawl over one shoulder, across the back and down the front."""
    m = art.poly([(24, 66), (46, 58), (60, 70), (50, 100), (36, 128), (24, 124), (22, 90)])
    art.paint(m, ramp, hi=2, lo=3)
    for k in range(4):
        art.line([(28 + k * 5, 72 + k * 3), (26 + k * 5, 120)], ramp[2], 1)
    art.line([(46, 60), (58, 71)], ramp[0], 1)
    return m


def gorget(art, cx=64, y=64, ramp=ST, rx=17, ry=5):
    """The collar at the base of the neck: a steel ring, drawn over the neck's foot."""
    m = art.ellipse(cx, y, rx, ry)
    art.paint(m, ramp, hi=1, lo=1)
    art.paint(art.ellipse(cx, y - 1.5, rx - 4, ry - 2.5), ("sk_s", "sk_s"), hi=0, lo=0, edge=None)
    return m


def scale_armour(art, ramp=ST, y0=64, y1=118, x0=30, x1=98):
    """Lorica squamata: rows of small overlapping scales."""
    chest = art.poly([(x0, y0 + 6), (x0 + 10, y0 - 2), (54, y0 - 4), (76, y0 - 4), (x1 - 10, y0 - 2), (x1, y0 + 6), (x1 - 2, y1 - 18), (x1 - 8, y1), (x0 + 10, y1), (x0 + 2, y1 - 18)])
    art.paint(chest, ramp, hi=0, lo=3)
    row = 0
    for y in range(int(y0), int(y1), 5):
        for x in range(int(x0) + (3 if row % 2 else 0), int(x1), 6):
            m = art.ellipse(x, y + 2, 3.4, 3) & chest
            art.paint(m, ramp, hi=1, lo=1, edge=ramp[2])
        row += 1
    return chest


def bare_chest(art, ramp=SK, y0=60):
    """A bare muscular torso: pectorals, a breastbone line and abdominal blocks."""
    m = art.poly([(30, y0 + 6), (42, y0 - 2), (54, y0 - 4), (76, y0 - 4), (88, y0 - 2), (98, y0 + 6), (94, 118), (90, 160), (38, 160), (34, 118)])
    art.paint(m, ramp, hi=2, lo=3)
    for (cx, cy) in ((50, y0 + 16), (78, y0 + 15)):
        art.paint(art.ellipse(cx, cy, 14, 9) & m, ramp, hi=2, lo=2, edge=ramp[2])
    art.line([(64, y0 + 6), (64, 112)], ramp[2], 1)
    for k in range(3):
        y = y0 + 38 + k * 9
        art.paint(art.rect(52, y, 62, y + 6) & m, ramp, hi=1, lo=1, edge=ramp[2])
        art.paint(art.rect(66, y, 76, y + 6) & m, ramp, hi=1, lo=1, edge=ramp[2])
    return m


def harness(art, discs=4):
    """Leather straps crossing the chest from shoulders to waist with gold phalerae (round medals)."""
    for (a, b) in (((40, 64), (84, 112)), ((88, 64), (44, 112))):
        m = art.thick([a, b], 5, round_caps=False)
        art.paint(m, LT, hi=1, lo=1)
        for k in range(discs):
            t = (k + 0.7) / (discs + 0.4)
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            art.paint(art.ellipse(x, y, 3.4, 3.4), GD, hi=1, lo=1)
            art.dot(x, y, "rd_m")


def apron(art, ramp=LT, y0=84):
    m = art.poly([(46, y0), (82, y0 - 2), (88, 160), (42, 160)])
    art.paint(m, ramp, hi=1, lo=2)
    art.line([(46, y0), (40, 66)], ramp[2], 2), art.line([(82, y0 - 2), (90, 66)], ramp[2], 2)
    art.paint(art.rect(52, y0 + 14, 76, y0 + 26) & m, ramp, hi=1, lo=1)
    art.dot(64, y0 + 20, "gd_m")
    return m


def mallet(art, x, y, length=46):
    art.paint(art.thick([(x, y), (x + 10, y - length)], 4, False), LT, hi=1, lo=1)
    art.paint(art.poly([(x + 3, y - length - 4), (x + 22, y - length - 9), (x + 24, y - length + 4), (x + 5, y - length + 9)]), GD, hi=1, lo=1)


def goblet(art, x, y):
    art.paint(art.poly([(x - 5, y - 8), (x + 5, y - 8), (x + 3, y), (x - 3, y)]), GD, hi=1, lo=1)
    art.paint(art.rect(x - 1, y, x + 1, y + 5), GD, hi=0, lo=0)
    art.paint(art.rect(x - 4, y + 5, x + 4, y + 6), GD, hi=0, lo=0)
    art.line([(x - 4, y - 7), (x + 4, y - 7)], "rd_m", 1)


def sash(art, a, b, ramp=RD, width=7):
    m = art.thick([a, b], width, round_caps=False)
    art.paint(m, ramp, hi=1, lo=1)
    return m
