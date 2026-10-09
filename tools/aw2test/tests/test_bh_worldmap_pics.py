"""The BH Campaign's world map with all 31 flags, stitched from real screenshots (AW2TEST_REVIEW_DIR gets world_map_raw_<x>_<y>.png
and world_map_all31.png): `-k bh_world_map_all31`."""
import os

from aw2test import bhact2 as a2
from aw2test.harness import test

WM = 0x0202FDFC
FLAGS = WM + 0x12


@test(modes=("ds",))
def bh_world_map_all31(ctx):
    from PIL import Image
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    # (M1..M30 won: the campaign is over and Free Play offers every mission, M31 (open with M28) included)
    e, g, d = a2.boot(ctx, (1 << 30) - 1, 0xFFF | (0x1FF << 12), picks={}, at=30)
    d.wait_world_map()
    e.wait(120)
    ctx.log(f"flags {d.map_flags()}")
    from aw2test import stitch
    shots = {}
    for cy in (-40, 0, 32, 64, 96):
        for cx in (-120, 0, 48, 96, 144, 192):
            for _ in range(4):
                e.w16(WM, cx & 0xFFFF)
                e.w16(WM + 2, cy & 0xFFFF)
                e.w16(WM + 4, 700)       # (the cursor off the screen)
                e.w16(WM + 6, 700)
                e.wait(8)
                stitch.hide_hud(e)
            if (cx, cy) == (0, 0):
                import struct
                b = e.read(0x03002520, 0x400)
                ctx.log("OAM " + str([(k,) + struct.unpack_from("<HHH", b, 8 * k) for k in range(128) if (struct.unpack_from("<HHH", b, 8 * k)[0] & 255) < 100 and (struct.unpack_from("<HHH", b, 8 * k)[0] >> 8) & 3 != 2 and struct.unpack_from("<HHH", b, 8 * k)[1] & 511 < 150]))
                ctx.log(f"bg {e.u16(0x04000008):#x} {e.u16(0x0400000A):#x} {e.u16(0x0400000C):#x} dispcnt {e.u16(0x04000000):#x}")
            p = e.shot(os.path.join(ctx.out, f"wm_{cx}_{cy}"))
            shots[(cx, cy)] = p
    import numpy as np
    # (the panels and the cross-hair are fixed on the screen: the median over the views that cover a pixel drops them)
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
    # The map draws 30 flags at most: in Free Play (every mission offered) M31's, the 31st, is left out. Its flag is
    # taken from the map with M1..M29 won (M30 and M31 open), where it is drawn (a white pennant), and pasted in.
    e.close()
    e, g, d = a2.boot(ctx, (1 << 29) - 1, 0xFFF | (0x1FF << 12), picks={}, at=30)
    d.wait_world_map()
    e.wait(120)
    ctx.log(f"flags with M1..M29 won {d.map_flags()}")
    X0, Y0, X1, Y1 = 182, 28, 200, 54
    best, bestn = None, -1
    for _ in range(12):
        e.w16(WM, 0)
        e.w16(WM + 2, 0)
        e.w16(WM + 4, 700)             # (the cross-hair's cursor off the screen)
        e.w16(WM + 6, 700)
        e.wait(7)
        stitch.hide_hud(e)
        im = np.asarray(Image.open(e.shot(os.path.join(ctx.out, "wm_open"))).convert("RGB"))
        patch = im[Y0:Y1, X0:X1].copy()
        n = int((patch.min(axis=2) > 235).sum())
        if n > bestn:
            best, bestn = patch, n
    ctx.log(f"M31's flag: {bestn} white pixels in the best frame")
    arr[Y0:Y1, X0:X1] = best
    full = Image.fromarray(arr)
    full.save(os.path.join(ctx.out, "world_map_all31.png"))
    if out:
        os.makedirs(out, exist_ok=True)
        full.save(os.path.join(out, "world_map_all31.png"))
    e.close()
