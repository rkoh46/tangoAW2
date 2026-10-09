"""Draws Crumb's three versions into tango-gamesupport-aw2/art/crumb/<A|B|C>/.

    python3 tools/crumb_art/build.py [out_dir]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from draw import *
from bodies import FIGURES

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tango-gamesupport-aw2", "art", "crumb")

FACE_S, FACE_C = 0.58, (24, 25)
MINI_S, MINI_C = 0.5, (16, 2)


def face(expr, look=0.0):
    c = Canvas(48, 48)
    head(c, FACE_C[0], FACE_C[1], FACE_S, expr, look)
    c.clean()
    return c


def mini(expr):
    c = Canvas(32, 24)
    head(c, MINI_C[0], MINI_C[1], MINI_S, expr)
    c.clean()
    return c


def hud(expr):
    f = face(expr)
    c = Canvas(32, 16)
    c.a[:, :] = f.a[30:46, 8:40]
    return c


def save(c, path):
    im = c.image()
    pal = []
    for col in PAL:
        pal += list(q5(col))
    im.putpalette(pal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, transparency=0, bits=4, optimize=True)


def build(version, expr):
    d = os.path.join(OUT, version)
    save(FIGURES[version](expr), os.path.join(d, "body.png"))
    for e in ("normal", "happy", "sad"):
        save(face(e), os.path.join(d, f"face_{e}.png"))
    save(mini(expr), os.path.join(d, "mini.png"))
    save(hud(expr), os.path.join(d, "hud.png"))


if __name__ == "__main__":
    for v, e in (("A", "normal"), ("B", "normal"), ("C", "happy")):
        build(v, e)
    print("written to", os.path.abspath(OUT))
