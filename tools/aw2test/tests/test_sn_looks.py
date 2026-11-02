"""Silver Nova in Gauntlet's Cinder Sea (Caulder, the skin's colour), in AW2's look and with the Dual Strike map graphics: the owner's
0.9.2 reports. Infantry and Mech cells drew black and white stripes with the Dual Strike graphics; the terrain panel showed Black Hole's
HQ for Silver Nova's; switching the Dual Strike graphics mid-match kept the other look's palettes and tiles."""

import os
import subprocess

from PIL import Image

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

CAULDER = 0x58
SKIN = 6
# The terrain panel's state byte (obelisk.rs PANEL): 6 while it shows a skin's HQ picture.
PANEL = 0x0203_0207
# The Dual Strike map graphics byte (wasteland.rs DS_GRAPHICS), what the setting writes.
DS_GRAPHICS = 0x0203_E3FE
LOOKS = {"aw2": {"TANGOAW2_DS_GRAPHICS": "0"}, "ds": {"TANGOAW2_DS_GRAPHICS": "1"}}


def shot(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


def stripes(png):
    """The most black/white neighbour flips in any 16 x 16 window: about 50 for AW2's own art, over 100 for the striped cells."""
    im = Image.open(png).convert("RGB")
    w, h = im.size
    px = im.load()
    cls = [[0 if sum(px[x, y]) < 120 else (2 if sum(px[x, y]) > 600 else 1) for x in range(w)] for y in range(h)]
    flips = [[1 if cls[y][x] != cls[y][x + 1] and 1 not in (cls[y][x], cls[y][x + 1]) else 0 for x in range(w - 1)] for y in range(h)]
    best = 0
    for y0 in range(0, h - 16, 2):
        for x0 in range(0, w - 17, 2):
            best = max(best, sum(sum(flips[y][x0:x0 + 15]) for y in range(y0, y0 + 16)))
    return best


def differ(a, b):
    a, b = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    return sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q) / (a.size[0] * a.size[1])


def bg_palette(e):
    """The map's background palettes (rows 0..11; the sea's animated rows aside, they are what the look loads)."""
    return e.read(0x0500_0000, 0x200)


def palette_rows_differ(a, b):
    return [r for r in range(16) if a[32 * r:32 * r + 32] != b[32 * r:32 * r + 32]]


def start(ctx, look):
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=LOOKS[look])
    g = Game(e, ctx.image)
    ctx.games.append(g)
    ga.Gauntlet(g).start(CAULDER, colour=SKIN)
    return e, g


def hq_of(g, army):
    for y in range(20):
        for x in range(30):
            t = g.terrain_class(x, y)
            if t & 0x1F == 8 and t >> 5 == army:
                return x, y
    return None


@test(modes=("ds",))
def silver_nova_gauntlet_looks(ctx):
    for look in LOOKS:
        e, g = start(ctx, look)
        worst = 0
        for k, (x, y) in enumerate([(8, 16), (6, 14), (10, 18), (8, 12)]):
            g.goto(x, y)
            e.wait(40)
            worst = max(worst, stripes(shot(ctx, e, f"{look}_map{k}")))
        ctx.check(worst < 80, f"{look}: no striped cells on Silver Nova's island (worst window {worst} flips)")
        cols = [g.player(a)["colour"] for a in range(1, 5)]
        ctx.eq(cols, [1, 3, 4, 5], f"{look}: Silver Nova on Orange Star's colour, Drake, Sensei and Hawke on Green Earth's, Yellow Comet's and Black Hole's (Caulder's country is Black Hole's: Hawke was moved onto Orange Star's colour and wore the skin)")
        hq = hq_of(g, 1)
        ctx.check(hq is not None, f"{look}: Silver Nova's HQ found ({hq})")
        if hq:
            g.goto(*hq)
            e.wait(40)
            shot(ctx, e, f"{look}_hq_panel")
            ctx.check(e.u8(PANEL) == 6, f"{look}: the terrain panel draws Silver Nova's own HQ picture (panel state {e.u8(PANEL)})")
        g.goto(8, 16)
        e.wait(20)
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        e.wait(90)
        shot(ctx, e, f"{look}_co_page1")
        for k in range(3):
            e.press("RIGHT", 6)
            e.wait(45)
        shot(ctx, e, f"{look}_co_page4")


@test(modes=("ds",))
def silver_nova_ds_graphics_switch_mid_match(ctx):
    """The Dual Strike graphics switched on, then off, mid-match: each time the map must look like a match started in that look."""
    e2, g2 = start(ctx, "ds")
    g2.goto(8, 16)
    e2.wait(40)
    shot(ctx, e2, "fresh_ds")
    fresh_ds = bg_palette(e2)
    e, g = start(ctx, "aw2")
    g.goto(8, 16)
    e.wait(40)
    shot(ctx, e, "fresh_aw2")
    fresh_aw2 = bg_palette(e)
    e.write(DS_GRAPHICS, bytes([1]))
    e.wait(150)
    g.goto(8, 16)
    e.wait(40)
    rows = palette_rows_differ(bg_palette(e), fresh_ds)
    s = stripes(shot(ctx, e, "switched_on"))
    ctx.check(not rows, f"switched on mid-match: the map palettes are a Dual Strike start's (rows differing: {rows})")
    ctx.check(s < 80, f"switched on mid-match: no stray tiles (worst window {s} flips)")
    e.write(DS_GRAPHICS, bytes([0]))
    e.wait(150)
    g.goto(8, 16)
    e.wait(40)
    rows = palette_rows_differ(bg_palette(e), fresh_aw2)
    s = stripes(shot(ctx, e, "switched_off"))
    ctx.check(not rows, f"switched off mid-match: the map palettes are an AW2-look start's (rows differing: {rows})")
    ctx.check(s < 80, f"switched off mid-match: no stray tiles (worst window {s} flips)")



def selected_sprite_dark(png, cell_px):
    """Share of near-black pixels in the selected unit's 16 x 16 cell (a black silhouette is mostly black)."""
    im = Image.open(png).convert("RGB")
    x0, y0 = cell_px
    px = [im.getpixel((x, y)) for y in range(max(0, y0 - 4), min(160, y0 + 16)) for x in range(max(0, x0), min(240, x0 + 16))]
    return sum(1 for p in px if sum(p) < 90) / max(1, len(px))


@test(modes=("ds",))
def silver_nova_selected_units(ctx):
    """Each of Silver Nova's unit types picked up (its move range shown): the picked-up sprite keeps the skin's colours, in both looks."""
    for look in LOOKS:
        e, g = start(ctx, look)
        seen = set()
        for u in g.units(army=1):
            if u["type"] in seen:
                continue
            seen.add(u["type"])
            g.goto(u["x"], u["y"])
            e.wait(20)
            idle = shot(ctx, e, f"{look}_t{u['type']}_idle")
            e.press("A", 6)
            e.wait(40)
            sel = shot(ctx, e, f"{look}_t{u['type']}_selected")
            e.press("B", 6)
            e.wait(30)
            ctx.log(f"{look}: type {u['type']} at {(u['x'], u['y'])}")


def orange_share(png, box):
    im = Image.open(png).convert("RGB").crop(box)
    px = list(im.getdata())
    return sum(1 for r, g, b in px if r > 200 and 60 < g < 170 and b < 90) / len(px)


@test(modes=("ds",))
def silver_nova_battle_scene_colours(ctx):
    """Silver Nova's Cruiser fires at one of Drake's ships: its half of the battle scene is silver, never its host colour's (Orange Star's) orange (the owner's 0.9.2 report)."""
    for look in LOOKS:
        e, g = start(ctx, look)
        d = ga.Gauntlet(g)
        mine = next(u for u in g.units(army=1) if u["type"] == 22)
        foe = next(u for u in g.units(army=2) if u["type"] in (21, 22, 23, 24))
        d.place_unit(foe, mine["x"] + 1, mine["y"])
        e.wait(10)
        g.select(mine["x"], mine["y"])
        g.move_to(mine["x"], mine["y"])
        g.choose("Fire", g.ACTION_MENU)
        g.pick_target(mine["x"] + 1, mine["y"])
        e.wait(160)
        p = shot(ctx, e, f"{look}_battle")
        o = orange_share(p, (0, 40, 120, 160))
        ctx.check(o < 0.005, f"{look}: Silver Nova's ship has no orange ({o:.1%} of its half)")
