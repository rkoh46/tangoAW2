#!/usr/bin/env python3
"""A development aid: the BH Campaign's first mission with Dual Strike graphics (usage: hq_bh.py OUTDIR [gfx] [tilt])."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
out = sys.argv[1]
os.environ["AW2TEST_OUT"] = out
os.environ["TANGOAW2_DS_GRAPHICS"] = sys.argv[2] if len(sys.argv) > 2 else "1"
os.environ["TANGOAW2_TILT"] = sys.argv[3] if len(sys.argv) > 3 else "0"
from aw2test.harness import Ctx
from aw2test.bhcampaign import BhCampaign
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
ctx = Ctx("hqbh", ds=True)
e = Emu(save=paths.base_save(), ds=True)
g = Game(e, ctx.image); ctx.games.append(g)
d = BhCampaign(g); d.start_bh(new=True)
d.wait_map(); d.through_dialogue(); d.wait_control()
for _ in range(14): e.shot(os.path.join(ctx.out, "warm"))
print(ctx.shot(g, "bh_start"))
g.goto(3, 13); e.wait(30)
for _ in range(14): e.shot(os.path.join(ctx.out, "warm"))
print(ctx.shot(g, "bh_hq"))
import struct
raw = e.read(0x05000200, 0x200)
for p in range(8, 16):
    print("pal", p, " ".join("%04x" % c for c in struct.unpack_from("<16H", raw, 32 * p)))
e.close()
