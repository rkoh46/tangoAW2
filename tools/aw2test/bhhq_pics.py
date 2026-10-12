#!/usr/bin/env python3
"""A development aid: a five-army map with all five HQs, AW2's look | Dual Strike flat | Dual Strike tilt, and the info box on
Black Hole's HQ (usage: bhhq_pics.py OUTDIR; writes OUTDIR/bhhq/*.png at 3x)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
out = sys.argv[1]
os.environ["AW2TEST_OUT"] = out
from PIL import Image
from aw2test.harness import Ctx

dest = os.path.join(out, "bhhq")
os.makedirs(dest, exist_ok=True)
LOOKS = [("aw2", "0", "0"), ("ds_flat", "1", "0"), ("ds_tilt", "1", "1")]
shots = {}
for name, gfx, tilt in LOOKS:
    ctx = Ctx("bhhq_" + name, ds=True)
    m = ctx.map(hq=((1, 4, 4), (2, 6, 4), (3, 8, 4), (4, 10, 4)), spare=False)
    m.terrain(12, 4, 0x1B4)
    for a, x in enumerate((4, 6, 8, 10, 12), 1):
        m.unit(a, "infantry", x, 6)
    m.colours = [5, 1, 2, 3, 4]
    g = ctx.start(m, None, env={"TANGOAW2_DS_GRAPHICS": gfx, "TANGOAW2_TILT": tilt})
    g.goto(8, 4)
    g.e.wait(60)
    shots[name + "_map"] = ctx.shot(g, "map")
    g.goto(12, 4)
    g.e.wait(60)
    shots[name + "_info"] = ctx.shot(g, "info")
    g.e.close()
for k, p in shots.items():
    im = Image.open(p).convert("RGB")
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(dest, k + ".png"))
row = [Image.open(os.path.join(dest, n + "_map.png")) for n, _, _ in LOOKS]
sheet = Image.new("RGB", (sum(i.width for i in row) + 20, row[0].height), (255, 255, 255))
x = 0
for i in row:
    sheet.paste(i, (x, 0)); x += i.width + 10
sheet.save(os.path.join(dest, "five_hqs_aw2_dsflat_dstilt.png"))
print(dest)
