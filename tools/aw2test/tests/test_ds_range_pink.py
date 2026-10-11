"""Dual Strike shows the cells a selected unit can attack beyond its move range in pink, next to the white move
cells (flat and tilted: TANGOAW2_TILT=1; needs TANGOAW2_DS_GRAPHICS=1)."""

import os
import struct

from aw2test.harness import Skip, test

GRAPHICS = os.environ.get("TANGOAW2_DS_GRAPHICS") == "1"


def bmp_pixels(path):
    d = open(path, "rb").read()
    off, w, h = struct.unpack_from("<I", d, 10)[0], struct.unpack_from("<i", d, 18)[0], struct.unpack_from("<i", d, 22)[0]
    bpp = struct.unpack_from("<H", d, 28)[0] // 8
    row = (w * bpp + 3) & ~3
    out = []
    for y in range(abs(h)):
        base = off + y * row
        for x in range(w):
            b, g, r = d[base + x * bpp], d[base + x * bpp + 1], d[base + x * bpp + 2]
            out.append((r, g, b))
    return out


def pink(px):
    return sum(1 for r, g, b in px if r > 200 and r - g > 25 and b - g > 8 and g > 90)


def scene(ctx, kind, at, name):
    m = ctx.map()
    m.unit(1, kind, *at)
    g = ctx.start(m, ["andy", "olaf"])
    g.e.wait(30)
    base = pink(bmp_pixels(ctx.shot(g, name + "_idle")))
    g.select(*at)
    g.e.wait(40)
    shot = ctx.shot(g, name)
    return base, pink(bmp_pixels(shot))


@test(modes=("ds",))
def ds_range_attack_cells_are_pink(ctx):
    """A selected tank: pink cells ring its move range; an artillery (it cannot move and fire): pink cells
    from its minimum range out."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    for kind, name in (("tank", "tank"), ("artillery", "artillery")):
        before, after = scene(ctx, kind, (10, 8), name)
        ctx.check(after > before + 100, f"{name}: the attackable cells are pink ({before} -> {after} pink pixels)")
