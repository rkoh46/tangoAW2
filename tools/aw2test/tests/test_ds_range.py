"""Dual Strike's range look (ds_tilt.rs `range_look`), flat and tilted: with a unit selected the ground outside
its range is dimmed to 3/4 (what Dual Strike's frames show, measured on a range shown and the same picture
with it off), and the cells inside are lit (brighter than without the range, no AW2 stripes)."""

import os

from aw2test.harness import test


def shots(ctx, tilt):
    from PIL import Image
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_SNAP": "1"}
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 12, 10)
    g = ctx.start(m, ["andy", "drake"], env=env)
    e = g.e
    e.wait(40)
    g.goto(10, 10)
    e.wait(30)
    for _ in range(8):
        e.shot(os.path.join(ctx.out, "warm"))
    idle = Image.open(ctx.shot(g, f"idle_{int(tilt)}")).convert("RGB")
    g.select(10, 10)
    e.wait(25)
    for _ in range(8):
        e.shot(os.path.join(ctx.out, "warm"))
    rng = Image.open(ctx.shot(g, f"range_{int(tilt)}")).convert("RGB")
    return idle, rng


@test(modes=("ds",))
def ds_range_look(ctx):
    for tilt in (False, True):
        idle, rng = shots(ctx, tilt)
        pi, pr = idle.load(), rng.load()
        # Far from the range (the map's left and top, clear of the HUD boxes): dimmed to 3/4.
        far = [(x, y) for x in (10, 25, 40, 55) for y in (50, 70, 85)]
        ratios = []
        for x, y in far:
            for c in range(3):
                if pi[x, y][c] > 40:
                    ratios.append(pr[x, y][c] / pi[x, y][c])
        lo, hi = (0.62, 0.84) if tilt else (0.72, 0.77)   # (the tilted map's clouds drift between the two pictures)
        ratios.sort()
        med = ratios[len(ratios) // 2] if ratios else 0
        bad = [] if lo <= med <= hi else ratios
        ctx.check(bool(ratios) and not bad,
                  f"tilt={int(tilt)}: the ground outside the range is dimmed to 3/4 (median {med:.3f}, want {lo}..{hi})")
        # Inside: lit cells, a good number of pixels brighter than without the range, none dimmed.
        lit = dim = 0
        for y in range(40, 160):
            for x in range(0, 240):
                d = [pr[x, y][c] - pi[x, y][c] for c in range(3)]
                if min(d) >= -4 and sum(d) > 30:
                    lit += 1
                elif max(d) < -20 and abs(x - 112) < 14 and abs(y - 100) < 10 and pi[x, y][1] > 180 and pi[x, y][2] < 140:
                    dim += 1
        ctx.check(lit > 1500, f"tilt={int(tilt)}: the cells in range are lit ({lit} lit pixels)")
        ctx.check(dim < 150, f"tilt={int(tilt)}: none of the ground near the unit is dimmed ({dim} dimmed pixels)")
