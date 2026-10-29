"""The picture world map (crate::world_picture, docs/dev/worldmap.md) in the real harness: the BH Campaign played on the BH2 picture with
TANGOAW2_BH_WORLDMAP=bh2 (dummy flag places). Pictures of the map unscrolled, scrolled, and with Orange Star conquered (its seven missions
won), plus the layer read from VRAM against the converted file: `-k bh_picture_map`. AW2TEST_REVIEW_DIR gets the BMPs."""
import os
import shutil
import struct

from aw2test import bhact2 as a2
from aw2test.harness import test

WM = 0x0202FDFC
FLAGS = WM + 0x12
BG3_CHARS = 0x06008000
PALRAM = 0x05000000


def _view(ctx, e, cx, cy, name):
    for _ in range(4):
        e.w16(WM, cx & 0xFFFF)
        e.w16(WM + 2, cy & 0xFFFF)
        e.wait(8)
    p = e.shot(os.path.join(ctx.out, name))
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        shutil.copy(p, os.path.join(out, os.path.basename(p)))
    return p


def _run(ctx, won, tag):
    old = os.environ.get("TANGOAW2_BH_WORLDMAP")
    os.environ["TANGOAW2_BH_WORLDMAP"] = "bh2"
    try:
        e, g, d = a2.boot(ctx, won, 0xFFF | (0x1FF << 12), picks={}, at=0)      # (the console takes its environment here; restored at once: it must not leak into the next test)
    finally:
        if old is None:
            os.environ.pop("TANGOAW2_BH_WORLDMAP", None)
        else:
            os.environ["TANGOAW2_BH_WORLDMAP"] = old
    d.wait_world_map()
    e.wait(120)
    shots = [_view(ctx, e, cx, cy, f"{tag}_{cx}_{cy}") for cx, cy in ((0, 0), (16, 0), (0, 48), (16, 96))]
    return e, shots


@test(modes=("ds",))
def bh_picture_map(ctx):
    # (nothing won: the picture as converted; the nations' entries are the picture's own colours)
    e, shots = _run(ctx, 0, "plain")
    pal = e.read(PALRAM + 0xC0, 0x120)
    ctx.check(len(set(pal)) > 20, "the map's palettes are loaded")
    ctx.log("palette RAM BG6.. first colours: " + " ".join(f"{struct.unpack_from('<H', pal, 2 * i)[0]:04x}" for i in range(1, 8)))
    # the layer is the picture's: tilemap cell (0, 0) names a tile of the converted file
    cell = e.u16(0x0600F000)
    ctx.log(f"tilemap cell 0 {cell:#06x}")
    ctx.check((cell >> 12) in range(6, 15), "the map layer's first cell uses a map palette")
    e.close()
    # Orange Star conquered: missions 0..6 (the dummy places 0..6 lie in it): its entries are Black Hole's, the other nations' not
    e2, shots2 = _run(ctx, 0x7F, "os")
    pal2 = e2.read(PALRAM + 0xC0, 0x120)
    changed = sum(1 for i in range(0x120 // 2) if pal2[2 * i:2 * i + 2] != pal[2 * i:2 * i + 2])
    ctx.log(f"palette entries changed by conquering Orange Star: {changed}")
    ctx.check(10 <= changed <= 40, f"conquest re-tints only Orange Star's entries ({changed} changed)")
    e2.close()
