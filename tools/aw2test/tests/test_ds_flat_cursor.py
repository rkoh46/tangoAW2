"""Dual Strike's cursor on the flat map ("Dual Strike map graphics" on, tilt off): the same
bmap/027 arrow and dots as the tilted map (ds_cursor.rs), drawn flat over the console's picture,
and AW2's own pointer and corner brackets (tiles 869 and 873) are taken out of it."""

import os
import shutil
import struct

from aw2test.harness import test

OUT = os.environ.get("AW2TEST_FIXES", "")


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


def scene(ctx, name, cursor, hook=None, ds=True):
    env = {"TANGOAW2_DS_GRAPHICS": "1" if ds else "0", "TANGOAW2_TILT": "0"}
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 6, 4).unit(1, "apc", 29, 10).unit(1, "infantry", 28, 10)
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
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(p, os.path.join(OUT, f"flat_{name}.png"))
    return g, p


def boxes(g):
    """The screen boxes of the game's pointer (16 x 16, tile 869) and bracket pieces (8 x 8, tile 873)."""
    raw = g.e.read(0x07000000, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", raw, 8 * i)
        t = a2 & 0x3FF
        if a0 & 0x300 == 0x200 or t not in (869, 873):
            continue
        n = 16 if t == 869 else 8
        x, y = a1 & 511, a0 & 255
        x, y = (x - 512 if x >= 240 else x), (y - 256 if y >= 160 else y)
        out.append((x, y, n))
    return out


def cursor_pixels(ctx, g, a, name):
    """`a` is the picture with Dual Strike's cursor. Parking the game's pointer and brackets afterwards leaves
    the console's last picture (theirs, no overlay: the overlay sees them parked) as the same shot's second
    half: what AW2's pieces look like. Returns the sprite count, the pixels that changed, and the AW2 pixels
    (their steel-blue outline, which Dual Strike's pictures do not use) that remain."""
    from PIL import Image
    boxes_now = boxes(g)
    n = park_cursor(g)
    g.e.shot(os.path.join(ctx.out, "warm"))
    b = ctx.shot(g, name + "_aw2")
    pa, pb = Image.open(a).convert("RGB").load(), Image.open(b).convert("RGB").load()
    inside = lambda x, y: any(bx <= x < bx + bn and by <= y < by + bn for bx, by, bn in boxes_now)
    diff = [(x, y, pa[x, y]) for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 24]
    dark = lambda c: c[0] < 80 and 80 < c[1] < 120 and 120 < c[2] < 180        # AW2's steel-blue outline
    ds_colours = {c for _, _, c in diff}
    aw2 = {pb[x, y] for y in range(160) for x in range(240) if inside(x, y) and dark(pb[x, y]) and pa[x, y] != pb[x, y]} - ds_colours
    left = [(x, y) for y in range(160) for x in range(240) if inside(x, y) and pa[x, y] in aw2]
    return n, diff, left


@test(modes=("ds",))
def ds_flat_cursor_scenes(ctx):
    """Dual Strike's cursor (blue dots, red arrow) on the flat map at the corner, the edges and the middle:
    drawn, with none of AW2's black pointer or bracket pixels."""
    for name, cur in (("c_corner", (0, 0)), ("c_mid", (7, 5)), ("c_right_edge", (14, 5)), ("c_bottom_right", (29, 19)), ("c_bottom", (10, 19))):
        g, p = scene(ctx, name, cur)
        n, diff, left = cursor_pixels(ctx, g, p, name)
        red = [d for d in diff if d[2][0] > d[2][2] + 80 and d[2][1] < 140]
        ctx.check(n >= 3, f"{name}: the game shows its pointer and brackets ({n} sprites)")
        ctx.check(len(diff) >= 12 and len(red) >= 6, f"{name}: Dual Strike's dots and red arrow are drawn ({len(diff)} changed, {len(red)} red pixels)")
        ctx.check(not left, f"{name}: none of AW2's bracket or pointer pixels stays with it ({len(left)})")


@test(modes=("ds",))
def ds_flat_cursor_cases(ctx):
    """The attack crosshair, the drop cursor, the unit menu and the map menu: Dual Strike's cursor
    is drawn each time and AW2's brackets are not."""
    def unit_menu(g):
        g.select(4, 4)
        g.move_to(4, 4)
        g.e.wait(20)

    def map_menu(g):
        g.goto(12, 8)
        g.open_map_menu()
        g.e.wait(20)

    for name, hook in (("k_attack", attack_hook), ("k_drop", drop_hook), ("k_unit_menu", unit_menu), ("k_map_menu", map_menu)):
        g, p = scene(ctx, name, None, hook=hook)
        n, diff, left = cursor_pixels(ctx, g, p, name)
        ctx.log(f"{name}: {n} game sprites, {len(diff)} cursor pixels")
        # (as on the tilted map: the game has no pointer or brackets on screen for the attack crosshair, which is
        # its own picture, nor under the menus; there Dual Strike's cursor is not drawn either)
        ctx.check((n > 0) == (len(diff) >= 12), f"{name}: Dual Strike's cursor is drawn when the game has its own ({n} sprites, {len(diff)} pixels)")
        if name == "k_drop":
            ctx.check(n >= 3, "the drop cursor is the game's pointer and brackets")
        ctx.check(not left, f"{name}: none of AW2's bracket or pointer pixels stays ({len(left)})")


@test(modes=("ds",))
def ds_flat_cursor_off_is_aw2s(ctx):
    """With the map graphics off the game's yellow brackets and pointer are untouched."""
    g, p = scene(ctx, "off", (7, 5), ds=False)
    n, diff, left = cursor_pixels(ctx, g, p, "off")
    ctx.check(n >= 3, f"the game shows its pointer and brackets ({n} sprites)")
    ctx.check(not diff, f"and they are the picture's own, nothing is redrawn ({len(diff)} pixels differ)")
