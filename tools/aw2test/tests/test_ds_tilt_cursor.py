"""Dual Strike's cursor on the tilted map (ds_cursor.rs) after the merge with the off-window markers:
it stands where the game's cursor is whatever the camera shows, and AW2's own pointer and corner
brackets (tile 873) never show with it. Scratch scenes first; checks follow the pictures."""

import os
import struct

from aw2test.harness import test

OUT = os.environ.get("AW2TEST_FIXES", "")


def scene(ctx, name, cursor, build=None, hook=None, tilt=True):
    log = os.path.join(ctx.out, f"{name}.log")
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_SNAP": "1",
           "TANGOAW2_TILT_CHECK": "1", "TANGOAW2_TILT_LOG": log}
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 6, 4).unit(1, "apc", 29, 10).unit(1, "infantry", 28, 10)
    if build:
        build(m)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    if hook:
        hook(g)
    else:
        g.goto(*cursor)
    g.e.wait(30)
    for _ in range(12):
        g.e.shot(os.path.join(ctx.out, "warm"))
    p = ctx.shot(g, name)
    if OUT:
        import shutil
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(p, os.path.join(OUT, f"fix2_{name}.png"))
    return g, p


def park_cursor(g):
    """Park the game's pointer and brackets (tiles 869, 873) the way it hides them."""
    e = g.e
    raw = e.read(0x07000000, 0x400)
    n = 0
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", raw, 8 * i)
        if a0 & 0x300 != 0x200 and (a2 & 0x3FF) in (869, 873) and not (a0 & 255 == 160 and a1 & 511 == 0):
            e.write(0x07000000 + 8 * i, struct.pack("<3H", (a0 & ~0xFF) | 160, a1 & ~0x1FF, a2))
            n += 1
    return n


def cursor_pixels(ctx, g, a, name):
    """The pixels Dual Strike's cursor adds: the picture against the same one with the game's
    cursor sprites parked (the cursor then is not drawn at all)."""
    from PIL import Image
    n = park_cursor(g)
    g.e.shot(os.path.join(ctx.out, "warm"))
    b = ctx.shot(g, name + "_nocursor")
    pa, pb = Image.open(a).convert("RGB").load(), Image.open(b).convert("RGB").load()
    diff = [(x, y, pa[x, y]) for y in range(160) for x in range(240)
            if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 24]
    return n, diff


@test(modes=("ds",))
def ds_tilt_cursor_scenes(ctx):
    """Dual Strike's cursor (blue dots, red arrow) at the corner, the window's edge, beyond it and
    the map's bottom: drawn, and none of AW2's pointer or bracket pixels (their outline is black)
    comes with it."""
    for name, cur in (("c_corner", (0, 0)), ("c_right_edge", (14, 5)), ("c_beyond", (20, 5)), ("c_bottom_right", (29, 19)), ("c_bottom", (10, 19))):
        g, p = scene(ctx, name, cur)
        n, diff = cursor_pixels(ctx, g, p, name)
        black = [d for d in diff if max(d[2]) < 48]
        ctx.check(n >= 3, f"{name}: the game shows its pointer and brackets ({n} sprites)")
        ctx.check(len(diff) >= 12, f"{name}: Dual Strike's cursor is drawn ({len(diff)} pixels)")
        ctx.check(not black, f"{name}: no black bracket or pointer pixel stays with it ({len(black)})")


def move_hook(to):
    def hook(g):
        g.select(4, 4)
        g.goto(*to)
    return hook


def attack_hook(g):
    g.select(4, 4)
    g.move_to(5, 4)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(20)


def drop_hook(g):
    e = g.e
    g.select(28, 10)
    g.move_to(29, 10)
    g.choose("Load", g.ACTION_MENU)
    g.wait_idle()
    g.select(29, 10)
    g.move_to(29, 10)
    g.choose("Drop", g.ACTION_MENU)
    e.wait(20)
    if g.menu():
        e.press("A", 4)
        e.wait(20)
    for _ in range(8):
        if g.cursor()[0] == 29:
            break
        e.press("RIGHT", 4)
        e.wait(10)
    e.wait(20)


@test(modes=("ds",))
def ds_tilt_cursor_moves(ctx):
    """The move path, the drop cursor and the attack crosshair on the tilted map. The crosshair
    runs through six frames of tiles (886 to 906); each is the target's marker on the ground
    (it used to stay where the flat picture has it for the frames past 895)."""
    from PIL import Image
    scene(ctx, "m_move_far", None, hook=move_hook((11, 4)))
    scene(ctx, "m_move_edge", None, hook=move_hook((11, 8)))
    scene(ctx, "m_drop", None, hook=drop_hook)
    ring = []
    for frame in range(6):
        def hook(g, frame=frame):
            attack_hook(g)
            g.e.wait(frame * 6)
        _, tilt = scene(ctx, f"m_attack{frame}", None, hook=hook)
        _, flat = scene(ctx, f"f_attack{frame}", None, hook=hook, tilt=False)
        pt, pf = Image.open(tilt).convert("RGB").load(), Image.open(flat).convert("RGB").load()
        white = [(x, y) for y in range(160) for x in range(240) if min(pf[x, y]) > 225 and 52 <= y < 92 and 80 <= x < 125]
        same = sum(1 for x, y in white if min(pt[x, y]) > 225)
        ring.append((len(white), same))
    ctx.log(("ring pixels flat/same in tilt", ring))
    ctx.check(all(n >= 20 and same * 10 < n * 6 for n, same in ring), f"the crosshair is on the ground in every frame ({ring})")


@test(modes=("ds",))
def ds_tilt_units_wear_dual_strikes_pictures(ctx):
    """On the tilted map every unit is Dual Strike's own 32 x 32 picture (drawn at half size, as its 3D
    engine scales it), in the window and from the records beyond it, not the 16 x 16 conversion."""
    def build(m):
        for i, k in enumerate(("tank", "infantry", "bcopter", "artillery", "apc", "fighter")):
            m.unit(1 + i % 2, k, 3 + 2 * i, 4)
            m.unit(1 + i % 2, k, 3 + 2 * i, 14)
    g, p = scene(ctx, "u_art", (6, 4), build=build)
    lines = open(os.path.join(ctx.out, "u_art.log")).read().splitlines()
    inside = [l for l in lines if "unit art" in l and "record" not in l]
    beyond = [l for l in lines if "unit art" in l and "record" in l]
    ctx.log(f"{len(inside)} in the window, {len(beyond)} from records")
    ctx.check(len(inside) >= 6, f"units in the window are Dual Strike's pictures ({len(inside)} draws)")
    ctx.check(len(beyond) >= 6, f"and so are the ones beyond it ({len(beyond)} draws)")
