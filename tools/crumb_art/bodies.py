"""Crumb's three figures (128 x 160): A salutes with the flag on his shoulder,
B has his arms crossed and the flag on his back, C gives a thumbs-up with
Gerald peeking out of his pocket. Used by build.py."""
from draw import *

CX, CY, S = 62, 36, 0.72  # the head's dome centre and scale in the figure


def limb(d, pts, w):
    """Tapered segments (the width falls a quarter along the arm) with round joints."""
    import math
    n = len(pts) - 1
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        w0, w1 = w * (1 - 0.25 * i / n), w * (1 - 0.25 * (i + 1) / n)
        L = math.hypot(x1 - x0, y1 - y0) or 1
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        d.polygon([(x0 + nx * w0 / 2, y0 + ny * w0 / 2), (x1 + nx * w1 / 2, y1 + ny * w1 / 2),
                   (x1 - nx * w1 / 2, y1 - ny * w1 / 2), (x0 - nx * w0 / 2, y0 - ny * w0 / 2)])
        for (x, y, ww) in ((x0, y0, w0), (x1, y1, w1)):
            d.ellipse((x - ww / 2, y - ww / 2, x + ww / 2, y + ww / 2))


def torso(c, lean=0):
    """Shoulders and chest to the bottom edge."""
    body = [(26, 160), (25, 120), (28, 98), (42, 85), (62, 81), (82, 85), (96, 98), (99, 120), (98, 160)]
    m = c.part(lambda d: d.polygon(body), US, None, U, sh=(4, 4), hl=(3, 3))
    # a lighter chest panel and the seams
    c.paint(lambda d: d.polygon([(38, 100), (86, 100), (84, 160), (40, 160)]), U, clip=m)
    c.paint(lambda d: d.polygon([(38, 100), (86, 100), (86, 103), (38, 103)]), UL, clip=m)
    c.paint(lambda d: [d.line((38, 100, 40, 160), fill=OUT), d.line((86, 100, 84, 160), fill=OUT)], OUT, clip=m)
    # shoulder epaulettes in Black Hole's purple
    for x in (26, 82):
        c.part(lambda d, x=x: d.polygon([(x, 90), (x + 16, 84), (x + 18, 92), (x + 2, 100)]), FP, None, WH if False else None, sh=(2, 2))


def collar(c):
    # the neck under the chin strap, and the jacket's collar piped purple
    c.part(lambda d: d.polygon([(40, 82), (52, 76), (62, 92), (72, 76), (84, 82), (78, 100), (62, 108), (46, 100)]), US, None, UL, sh=(2, 2), hl=(1, 1))
    c.paint(lambda d: [d.line((44, 84, 62, 104), fill=FP), d.line((80, 84, 62, 104), fill=FP)], FP)


def belt(c, y=140):
    c.part(lambda d: d.polygon([(26, y), (98, y), (98, y + 9), (26, y + 9)]), US, OUT, UL, sh=(2, 2), hl=(1, 1))
    c.part(lambda d: d.rectangle((56, y - 1, 68, y + 10)), BG, BS, None, sh=(1, 1))
    c.paint(lambda d: d.rectangle((60, y + 2, 64, y + 7)), BS)
    for x in (34, 80):
        c.part(lambda d, x=x: d.rectangle((x, y + 9, x + 12, y + 20)), U, US, UL, sh=(2, 2), hl=(1, 1))
        c.paint(lambda d, x=x: d.rectangle((x + 5, y + 10, x + 7, y + 13)), BG)


def strap(c):
    """A bandolier from the left shoulder to the right hip, with a buckle."""
    c.part(lambda d: d.polygon([(36, 88), (46, 86), (98, 148), (98, 158), (88, 158)]), US, OUT, U, sh=(2, 2), hl=(1, 1))
    for (x, y) in ((50, 100), (64, 116), (78, 132)):
        c.part(lambda d, x=x, y=y: d.rectangle((x, y, x + 5, y + 6)), BG, BS, None, sh=(1, 1))


def pocket(c, x, y, big=False):
    """A breast pocket with Gerald, a biscuit with a face, peeking out."""
    w, h = (24, 19) if big else (20, 16)
    r = 8.5 if big else 7.5
    gx, gy = x + w / 2, y - 1
    c.part(lambda d: d.ellipse((gx - r, gy - r, gx + r, gy + r)), BG, BS, None, sh=(2, 2), hl=(1, 1))
    c.paint(lambda d: [d.point((gx - 2.5, gy - 3)), d.point((gx + 2, gy - 3))], OUT)
    c.paint(lambda d: d.arc((gx - 3, gy - 3, gx + 3, gy + 1.5), 20, 160, fill=OUT, width=1), OUT)
    c.paint(lambda d: [d.point((gx - 5, gy - 1)), d.point((gx + 4, gy + 1))], BS)
    c.part(lambda d: d.polygon([(x, y), (x + w, y), (x + w, y + h - 3), (x + w / 2, y + h), (x, y + h - 3)]), U, US, UL, sh=(2, 2))
    c.paint(lambda d: d.line((x + 1, y + 3, x + w - 1, y + 3), fill=OUT), OUT)
    c.paint(lambda d: d.rectangle((x + w / 2 - 1, y + 4, x + w / 2 + 1, y + 6)), BG)


def rank_patch(c, x, y):
    c.part(lambda d: d.rectangle((x, y, x + 10, y + 10)), US, OUT, None, sh=(1, 1))
    c.paint(lambda d: [d.line((x + 1, y + 3, x + 5, y + 1), fill=BG), d.line((x + 5, y + 1, x + 9, y + 3), fill=BG),
                       d.line((x + 1, y + 6, x + 5, y + 4), fill=BG), d.line((x + 5, y + 4, x + 9, y + 6), fill=BG)], BG)


def sleeve(c, pts, w):
    """An arm: a sleeve through the points; a purple cuff at the last."""
    c.part(lambda d: limb(d, pts, w), U, US, UL, sh=(3, 3), hl=(2, 2))
    if len(pts) > 2:
        ex, ey = pts[1]
        c.paint(lambda d: [d.line((ex - 3, ey + 1, ex + 2, ey + 4), fill=OUT), d.line((ex - 2, ey - 3, ex + 3, ey)), ], OUT)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    import math
    n = math.hypot(x1 - x0, y1 - y0) or 1
    ux, uy = (x1 - x0) / n, (y1 - y0) / n
    cx, cy = x1 - ux * 3, y1 - uy * 3
    px, py = -uy * (w / 2), ux * (w / 2)
    c.paint(lambda d: d.line((cx + px, cy + py, cx - px, cy - py), width=3), FP)


def glove(c, x, y, r=5.5):
    c.part(lambda d: d.ellipse((x - r, y - r, x + r, y + r)), H, HS, HL, sh=(2, 2), hl=(1, 1))
    c.paint(lambda d: [d.line((x - r * .5, y + 1, x + r * .5, y + 1), fill=OUT), d.line((x - r * .5, y + 3, x + r * .5, y + 3), fill=OUT)], OUT)


def flag(c, x0, y0, w=30, h=34, wave=3):
    """A Black Hole flag: black, a purple hole with a white ring, a ragged edge."""
    pts = [(x0, y0)]
    n = 6
    for i in range(1, n + 1):
        pts.append((x0 + w * i / n, y0 + (wave if i % 2 else -wave * 0.4)))
    for i in range(n, -1, -1):
        pts.append((x0 + w * i / n, y0 + h + (wave if i % 2 == 0 else -wave * 0.4)))
    c.part(lambda d: d.polygon(pts), HS, OUT, H, sh=(2, 2), hl=(1, 1))
    cx, cy = x0 + w * 0.52, y0 + h * 0.5
    c.part(lambda d: d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8)), FP, None, None, sh=(2, 2), outline=False)
    c.paint(lambda d: d.ellipse((cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5)), OUT)
    c.paint(lambda d: d.arc((cx - 8, cy - 8, cx + 8, cy + 8), 30, 330, fill=WH, width=1), WH)


def pole(c, x0, y0, x1, y1, w=3):
    c.part(lambda d: d.line((x0, y0, x1, y1), width=w), BS, None, None, outline=True)
    c.paint(lambda d: d.line((x0, y0, x1, y1), width=1), BG)


def figure_A(expr="normal"):
    c = Canvas(128, 160)
    pole(c, 108, 2, 110, 160)
    flag(c, 108, 5, w=19, h=30)
    torso(c)
    collar(c)
    belt(c)
    strap(c)
    pocket(c, 66, 100)
    # right arm (viewer's right) at his side, the fist round the pole
    sleeve(c, [(94, 98), (103, 128)], 15)
    glove(c, 106, 130)
    # left arm saluting: the elbow out, the glove at the brim
    sleeve(c, [(31, 100), (14, 114), (26, 64)], 14)
    rank_patch(c, 15, 98)
    head(c, CX, CY, S, expr)
    glove(c, 31, 50, 6)
    c.clean()
    return c


def figure_B(expr="normal"):
    c = Canvas(128, 160)
    pole(c, 54, 158, 104, 8)
    flag(c, 102, 6, w=22, h=28)
    torso(c)
    collar(c)
    pocket(c, 68, 96)
    sleeve(c, [(95, 100), (96, 124), (52, 130)], 14)
    sleeve(c, [(30, 100), (28, 124), (72, 136)], 14)
    glove(c, 49, 130)
    glove(c, 75, 136)
    rank_patch(c, 14, 104)
    head(c, CX, CY, S, expr)
    c.clean()
    return c


def figure_C(expr="happy"):
    c = Canvas(128, 160)
    pole(c, 18, 156, 24, 8)
    flag(c, 24, 8, w=22, h=28)
    torso(c)
    collar(c)
    belt(c)
    strap(c)
    pocket(c, 36, 100, big=True)
    sleeve(c, [(31, 98), (22, 130)], 13)
    glove(c, 22, 135)
    # right arm: the fist up with the thumb up
    sleeve(c, [(94, 96), (104, 116), (92, 100)], 12)
    c.part(lambda d: d.ellipse((84, 86, 100, 102)), H, HS, HL, sh=(2, 2), hl=(1, 1))
    c.part(lambda d: d.rounded_rectangle((89, 70, 96, 90), radius=3), H, HS, HL, sh=(2, 2), hl=(1, 1))
    head(c, CX, CY, S, expr)
    c.clean()
    return c


FIGURES = {"A": figure_A, "B": figure_B, "C": figure_C}
