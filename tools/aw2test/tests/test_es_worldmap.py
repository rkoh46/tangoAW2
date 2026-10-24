"""The Emerald Sun Campaign's world map with its 16 flags, stitched from real screenshots (AW2TEST_REVIEW_DIR gets world_map_es16.png): `-k es_world_map`."""
import os

from aw2test import escampaign as es
from aw2test import stitch
from aw2test.harness import test

WM = 0x0202FDFC


@test(modes=("ds",))
def es_world_map_all16(ctx):
    from PIL import Image
    import numpy as np
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    # (M1..M15 won: M16 is the open flag)
    e, g, d = es.boot(ctx, 16)
    d.wait_world_map()
    e.wait(120)
    flags = d.map_flags()
    ctx.log(f"flags {flags}")
    ctx.eq(sum(1 for f in flags[:16] if f & 1), 16, "all 16 flags are on the map")
    shots = {}
    for cy in (-40, 0, 32, 64, 96):
        for cx in (-120, 0, 48, 96, 144, 192):
            for _ in range(4):
                e.w16(WM, cx & 0xFFFF)
                e.w16(WM + 2, cy & 0xFFFF)
                e.w16(WM + 4, 700)
                e.w16(WM + 6, 700)
                e.wait(8)
                stitch.hide_hud(e)
            shots[(cx, cy)] = e.shot(os.path.join(ctx.out, f"wm_{cx}_{cy}"))
    stack = [[[] for _ in range(432)] for _ in range(256)]
    for (cx, cy), p in shots.items():
        im = np.asarray(Image.open(p).convert("RGB"))
        for y in range(160):
            for x in range(240):
                if 0 <= cy + y < 256 and 0 <= cx + x < 432:
                    stack[cy + y][cx + x].append(im[y, x])
    arr = np.zeros((256, 432, 3), dtype=np.uint8)
    for y in range(256):
        for x in range(432):
            arr[y, x] = np.median(np.array(stack[y][x]), axis=0)
    full = Image.fromarray(arr)
    full.save(os.path.join(ctx.out, "world_map_es16.png"))
    if out:
        os.makedirs(out, exist_ok=True)
        full.save(os.path.join(out, "world_map_es16.png"))
    e.close()
