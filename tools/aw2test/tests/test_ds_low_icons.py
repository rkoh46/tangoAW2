"""Low ammunition / low fuel icons with "Dual Strike map graphics" on and the tilt off.

The game draws them on BG2 (tiles 0x33D to 0x33F, palette 10, the top-right tile of the unit's
cell, blinking in VRAM). With the Dual Strike map graphics BG2 also holds the terrain's upper
parts, which `wasteland::restore_front` puts back every frame: it used to put the icons' entries
back to blank too, so the icons never showed on a flat map. The tilted map draws them from the
records (test_ds_tilt_beyond.py)."""

import os
import struct

from aw2test.harness import test

BG2_MAP = 0x06007800
OUT = os.environ.get("AW2TEST_FIXES", "")


def rule(g, u):
    """The console's rule (`0x08022618`): ammunition and fuel at most a third of the type's own."""
    table = g.e.u32(0x080909AC)
    max_ammo, max_fuel = g.e.u8(table + 0x5C * u["type"] + 0xB), g.e.u8(table + 0x5C * u["type"] + 0x10)
    return int(max_ammo != 0 and u["ammo"] <= max_ammo // 3) + 2 * int(max_fuel != 0 and u["fuel"] <= max_fuel // 3)


def icons_showing(g):
    return all(any(g.e.read(0x06008000 + 32 * t, 32)) for t in (0x33D, 0x33E, 0x33F))


@test(modes=("ds",))
def ds_flat_low_icons(ctx):
    """Units in the console's window with low ammunition, low fuel, both and neither: with the map
    graphics on and the tilt off BG2 keeps the game's icon in each cell's top-right tile, and the
    picture shows it."""
    m = ctx.map()
    kinds = ("tank", "infantry", "apc", "artillery")
    for x in range(1, 13):
        m.unit(1 + x % 2, kinds[x % 4], x, 4)
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0"}
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    e = g.e
    units = {(u["x"], u["y"]): u for u in g.units()}
    for (x, y), u in units.items():
        a = g.unit_addr(u["id"])
        if x % 3 == 0:
            e.w8(a + 6, 2)                                       # low fuel
        if x % 3 == 1:
            e.w16(a + 4, e.u16(a + 4) & ~0x780)                  # no ammunition
        if x % 6 == 0:
            e.w16(a + 4, e.u16(a + 4) & ~0x780)                  # both
    # (the console draws a unit's cell as it enters its plane: out and back)
    g.goto(29, 19)
    g.goto(0, 0)
    ctx.require(e.wait_until(lambda: icons_showing(g), 300, step=1), "the low ammunition and fuel icons blink on")
    units = {(u["x"], u["y"]): u for u in g.units()}
    raw = e.read(BG2_MAP, 0x800)
    entry = lambda cx, cy: struct.unpack_from("<H", raw, 2 * (32 * (2 * (cy % 16)) + 2 * (cx % 16) + 1))[0]
    bad, shown = [], 0
    for (x, y), u in units.items():
        if x >= 15 or y >= 10:
            continue
        want = rule(g, u)
        got = entry(x, y) & 0x3FF
        if want:
            shown += 1
            if got != 0x33C + want:
                bad.append(((x, y), want, hex(entry(x, y))))
        elif 0x33D <= got <= 0x33F:
            bad.append(((x, y), want, hex(entry(x, y))))
    ctx.check(shown >= 6, f"{shown} of the units have low ammunition or fuel")
    ctx.check(not bad, f"each cell's BG2 entry is the console's icon for its unit ({bad[:4]})")
    # The picture: a unit with an icon differs from the same scene without.
    p = ctx.shot(g, "flat_icons")
    if OUT:
        import shutil
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(p, os.path.join(OUT, "fix1_flat_icons.png"))
    from PIL import Image
    pic = Image.open(p).convert("RGB").load()
    pal = e.read(0x05000000 + 32 * 10, 32)
    seen = 0
    for (x, y), u in units.items():
        want = rule(g, u)
        if want == 0 or x >= 15 or y >= 10:
            continue
        tile = e.read(0x06008000 + 32 * (0x33C + want), 32)
        n = hit = 0
        for py in range(8):
            for px in range(8):
                c = (tile[py * 4 + px // 2] >> (4 * (px & 1))) & 15
                if c == 0:
                    continue
                rgb = struct.unpack_from("<H", pal, 2 * c)[0]
                exp = ((rgb & 31) * 255 // 31, ((rgb >> 5) & 31) * 255 // 31, ((rgb >> 10) & 31) * 255 // 31)
                n += 1
                hit += all(abs(a - b) <= 10 for a, b in zip(pic[16 * x + 8 + px, 16 * y + py], exp))
        seen += n >= 8 and hit * 10 >= n * 7
    ctx.check(seen >= 5, f"the picture shows the icon's own pixels in {seen} of {shown} cells")
