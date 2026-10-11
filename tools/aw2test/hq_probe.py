#!/usr/bin/env python3
"""Photograph every property kind of every owner in one console picture each (a development aid for
the Dual Strike building art): hq_probe.py OUTDIR [gfx 0|1] [tilt 0|1] [weather clear|snow]."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
out = sys.argv[1]
gfx, tilt, weather = (sys.argv + ["1", "1", "clear"][len(sys.argv) - 2:])[2:5] if len(sys.argv) > 2 else ("1", "1", "clear")
os.environ.setdefault("AW2TEST_OUT", out)
os.environ["TANGOAW2_DS_GRAPHICS"] = gfx
os.environ["TANGOAW2_TILT"] = tilt
from aw2test.harness import Ctx
from aw2test.save import DesignMap
from aw2test import paths

KINDS = ["hq", "base", "city", "airport", "port", "lab"]


def photograph(kind, name, owners=range(0, 6)):
    ctx = Ctx("hqprobe_" + name, ds=True)
    m = DesignMap(width=15, height=10, name="hq" + kind[:6], image=ctx.image)
    hq = [o for o in owners if kind == "hq"]
    cos = ["andy", "drake"]
    if kind == "hq" and len(hq) == 4:
        cos = ["andy", "olaf", "eagle", "sonja"]
    if os.environ.get("HQ_COLOURS"):
        m.colours = [int(c) for c in os.environ["HQ_COLOURS"].split(",")]
    if os.environ.get("HQ_COS"):
        cos = os.environ["HQ_COS"].split(",")
    if kind != "hq":
        m.terrain(0, 0, "hq", 1); m.unit(1, "infantry", 1, 1)
        m.terrain(14, 9, "hq", 2); m.unit(2, "infantry", 13, 8)
    else:
        for n, o in enumerate(hq):
            m.unit(1 + n % len(cos), "infantry", 1, 1 + n)
    for n, o in enumerate(owners):
        x = 1 + 2 * n
        if kind == "lab":
            m.terrain(x, 5, ctx.image.tile_for("lab"))
        else:
            m.terrain(x, 5, 0x1C0 + {"hq": 0, "base": 1, "city": 2, "airport": 3, "port": 4}[kind] + 5 * o)
    g = ctx.start(m, cos, weather=weather)
    for _ in range(14):
        g.e.shot(os.path.join(ctx.out, "warm"))
    p = ctx.shot(g, name)
    g.e.close()
    return p


if __name__ == "__main__":
    tag = f"g{gfx}t{tilt}{weather[0]}"
    for k in (sys.argv[5].split(",") if len(sys.argv) > 5 else KINDS):
        if k == "hq":
            print(photograph(k, f"hq_{tag}", (1, 2, 3, 4)))
        else:
            print(photograph(k, f"{k}_{tag}"))
