"""Each country's HQ with Dual Strike graphics is Dual Strike's picture for that country; Black Hole's is AW2's.

Dual Strike's `bmap/015` holds the HQs as cells 10 to 13 (its Design Room draws the HQ of each
colour: Orange Star the tall tower, Blue Moon the spire, Green Earth the dome, Yellow Comet the
horns). It has no Black Hole HQ: it draws an HQ by terrain id (a Black Hole army's HQ in the Dark
Ambition mission is the fourth army's picture in Black Hole's colours), and terrain 0x1D9, once
read as Black Hole's HQ, is its Lab (cell 9; the Com Tower is cell 8). The game picks the picture
by the country of the army's CO (Andy Orange Star, Olaf Blue Moon, Eagle Green Earth, Sonja
Yellow Comet, Sturm Black Hole). Here the four HQs of a four-army map are photographed from the
console's object memory: each one's 16x32 tiles are the cell for the CO's country, in the colours
`crate::ds_graphics` gives an HQ (the owner shades of `com_tower::SHADES`; the windows Dual
Strike's dark grey, AW2's index 15); Sturm's is AW2's own picture (the same tiles as with the
setting off). Settings off, the same HQs are AW2's own pictures."""

import os
import struct

from aw2test import paths
from aw2test.harness import test
from aw2test.rom import DualStrike
from aw2test.save import DesignMap

# Dual Strike's cell for each country (bmap/015), by the CO's country.
CELLS = {"andy": 10, "olaf": 11, "eagle": 12, "sonja": 13}
# crate::com_tower::SHADES, and the HQs' windows (crate::ds_graphics::HQ_SHADES).
SHADES = [0, 0, 0, 0, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 0]
HQ_SHADES = SHADES[:13] + [15] + SHADES[14:]
OBJ_TILES = 0x06010000
OAM = 0x07000000
SQUAD = (("andy", "olaf", "eagle", "sonja"), ("sturm", "olaf", "eagle", "sonja"))


def expected(sprites, cell):
    """The cell as the 8 GBA tiles (16x32, 1D order) of an HQ."""
    bmp = bytes(HQ_SHADES[b & 15] | HQ_SHADES[b >> 4] << 4 for b in sprites[256 * cell:256 * (cell + 1)])
    out = bytearray()
    for ty in range(4):
        for tx in range(2):
            for y in range(8):
                at = (ty * 8 + y) * 8 + tx * 4
                out += bmp[at:at + 4]
    return bytes(out)


def hq_pictures(ctx, cos, graphics):
    """{army: its HQ's 256 bytes of tiles} read back from the OBJ tiles the OAM names (the 16x32
    sprites in OBJ palettes 9..12, one per army)."""
    m = DesignMap(width=15, height=10, name="dshq", image=ctx.image)
    for army, x in enumerate((2, 5, 8, 11), 1):
        m.terrain(x, 2, "hq", army)
        m.unit(army, "infantry", x, 3)
    g = ctx.start(m, list(cos), env={"TANGOAW2_DS_GRAPHICS": graphics, "TANGOAW2_TILT": "0"})
    g.e.wait(60)
    oam = g.e.read(OAM, 0x400)
    out = {}
    for k in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", oam, 8 * k)
        if a0 & 0x300 == 0x200 or (a0 >> 14, a1 >> 14) != (2, 2):
            continue
        pal = a2 >> 12
        if 9 <= pal <= 12 and (a0 & 255) < 160:
            out[pal - 8] = g.e.read(OBJ_TILES + 32 * (a2 & 0x3FF), 256)
    return out


@test("ds_hq_pictures", modes=("ds",))
def ds_hq_pictures(ctx):
    """Every country's HQ is Dual Strike's cell for it (Black Hole's is AW2's)."""
    ds = DualStrike()
    sprites = ds.file("bmap/015")
    aw2 = hq_pictures(ctx, SQUAD[1], "0")
    for cos in SQUAD:
        shown = hq_pictures(ctx, cos, "1")
        ctx.eq(sorted(shown), [1, 2, 3, 4], f"{cos}: four HQs on screen")
        for army, co in enumerate(cos, 1):
            if co == "sturm":
                ctx.check(shown.get(army) == aw2.get(army),
                          "Sturm's (Black Hole's) HQ is AW2's own picture: Dual Strike has none")
                ctx.check(shown.get(army) not in {expected(sprites, c) for c in range(8, 14)},
                          "Black Hole's HQ is none of Dual Strike's cells 8 to 13 (cell 9 is the Lab)")
            else:
                ctx.check(shown.get(army) == expected(sprites, CELLS[co]),
                          f"army {army} ({co}) draws Dual Strike's HQ cell {CELLS[co]}")
    ctx.check(len({expected(sprites, c) for c in CELLS.values()}) == 4, "the four cells differ")


@test("ds_hq_off_is_aw2", modes=("ds",))
def ds_hq_off_is_aw2(ctx):
    """With the setting off none of the cells is on screen (AW2's own HQ pictures)."""
    ds = DualStrike()
    sprites = ds.file("bmap/015")
    cells = {expected(sprites, c) for c in CELLS.values()}
    shown = hq_pictures(ctx, SQUAD[0], "0")
    ctx.eq(sorted(shown), [1, 2, 3, 4], "four HQs on screen")
    ctx.check(not any(v in cells for v in shown.values()), "no Dual Strike HQ cell with the setting off")
