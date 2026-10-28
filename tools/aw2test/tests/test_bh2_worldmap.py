"""The BH2 Campaign's picture world map in the game (development build, TANGOAW2_BH2_CAMPAIGN): every drawn flag lies where `world_picture::BH2_FLAGS` puts it, and a nation is conquered exactly when all of its
missions are won (`-k bh2_worldmap`). The flags are read from the OAM (AW2's cleared flag is OBJ tile 40, the open mission's pennant tile 24, 16 x 16, drawn at the flag's place + (-5, -5) minus the camera);
the conquest from the palette byte `ds_worldmap::CONQUEST_MARK` (bit n: nation n is Black Hole's). With AW2TEST_SHOWCASE=<folder> the map is also photographed in its four camera views and stitched
(pasted in the reverse order (16,96), (0,96), (16,0), (0,0), so the CAMPAIGN banner covers as little as possible) into ingame_all.png and ingame_acts1to3.png."""

import os
import struct
import sys

from aw2test import bh2campaign as b2
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "devkit"))
CONQUEST_MARK = 0x08FC_0000 + 0xB90C
CLEARED_TILE, OPEN_TILE = 40, 24
VIEWS = ((0, 0), (16, 0), (0, 96), (16, 96))


def flag_sprites(e, cam):
    """{(x, y): tile} of the flags drawn now, in world coordinates."""
    oam = e.read(0x07000000, 0x400)
    out = {}
    for k in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", oam, 8 * k)
        if a0 & 0x300 == 0x200 or a0 >> 14 == 3:
            continue
        tile = a2 & 0x3FF
        if tile not in (CLEARED_TILE, OPEN_TILE):
            continue
        sx, sy = a1 & 0x1FF, a0 & 0xFF
        sx = sx - 512 if sx >= 256 else sx
        sy = sy - 256 if sy >= 160 else sy
        if sy < -16 or sy >= 160 or sx < -16 or sx >= 240:
            continue
        out[(sx + cam[0] + 5, sy + cam[1] + 5)] = tile
    return out


def stitch(shots, path):
    from PIL import Image
    big = Image.new("RGB", (256, 256))
    for cam in ((16, 96), (0, 96), (16, 0), (0, 0)):
        big.paste(Image.open(shots[cam]).convert("RGB"), cam)
    big.resize((256 * 3, 256 * 3), Image.NEAREST).save(path)


def check(ctx, n_won, tag):
    from aw2.bh2lib import flags
    fl = flags()                                  # (mission, region, x, y)
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=dict(b2.ENV))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = b2.Bh2Campaign(g)
    d.start_at((1 << n_won) - 1, b2.ROSTER_BITS)
    d.wait_world_map()
    e.wait(120)
    seen, shots = {}, {}
    out = os.environ.get("AW2TEST_SHOWCASE")
    for cam in VIEWS:
        e.w16(dc.WM_STATE, cam[0])
        e.w16(dc.WM_STATE + 2, cam[1])
        e.wait(30)
        seen.update(flag_sprites(e, cam))
        shots[cam] = e.shot(os.path.join(ctx.out, f"wm_{tag}_{cam[0]}_{cam[1]}"))
    where = {(x, y): m for m, _, x, y in fl}
    ctx.log(f"{tag}: {len(seen)} flags drawn: " + ", ".join(f"M{where.get(p, '?')} {'cleared' if t == CLEARED_TILE else 'open'}" for p, t in sorted(seen.items(), key=lambda kv: where.get(kv[0], 0))) if False else f"{tag}: {len(seen)} flags drawn, open pennants for " + str(sorted(where[p] for p, t in seen.items() if t == OPEN_TILE and p in where)))
    stray = [p for p in seen if p not in where]
    ctx.check(not stray, f"{tag}: every drawn flag is a BH2_FLAGS place (stray: {stray})")
    cleared = {where[p] for p, t in seen.items() if p in where and t == CLEARED_TILE}
    want = {m for m, *_ in fl if m <= n_won and m != 26}
    ctx.check(cleared == want, f"{tag}: the cleared flags are the won missions' (drawn {sorted(cleared)}, won {sorted(want)})")
    # nations conquered: every mission of the nation won (Black Hole's island always)
    won = lambda m: m <= n_won
    expect = 0
    for r in range(1, 6):
        ms = [m for m, reg, *_ in fl if reg == r]
        if r == 5 or (ms and all(won(m) for m in ms)):
            expect |= 1 << r
    got = e.u8(CONQUEST_MARK)
    ctx.eq(got, expect, f"{tag}: the conquered nations (bits) match the won missions")
    if out:
        os.makedirs(out, exist_ok=True)
        stitch(shots, os.path.join(out, f"ingame_{tag}.png"))
    e.close()


@test(name="bh2_worldmap_flags", modes=("ds",))
def bh2_worldmap_flags(ctx):
    check(ctx, 24, "all")
    check(ctx, 14, "acts1to3")
    check(ctx, 1, "m1")
