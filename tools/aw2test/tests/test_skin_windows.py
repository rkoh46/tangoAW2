"""Silver Nova recolours the ARMY only; every window of the game stays AW2's own (`-k skin_windows`, docs/dev/army-packs.md "Windows stay AW2's").

The skin used to patch the colours' window row too (BG palette bank 8, three ROM tables that hold the same row: `0x080D4188`, `0x08183C28`, `0x085AC8BC`), so with the skin on a colour the
dialogue and chat boxes, the map menu, the CO page and the status pages were all drawn olive. A battle with the skin on a host colour is checked against the same battle with that colour and no skin:

  * the window palette (bank 8) is the same on every screen (the map, the map menu, the CO page, the Intel pages, a CO power's dialogue box, the unit menu, the damage forecast: there bank 8 is a rotating
    gradient, so the same set of colours at another phase), and the map menu, the dialogue box and the forecast with its unit box are the same pixels;
  * the army's own palettes are Silver Nova's: the units' rows, the buildings' (the HQ), the funds box's (OBJ bank 7 of the HUD).
The Gauntlet's battle (Silver Nova picked, on the colour its map leaves free) is held to the same: its intro dialogue boxes, the map menu, the CO page and a CO power's box."""

import os

from aw2test import dscampaign as dsc
from aw2test import gauntlet as ga
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
from aw2test.harness import test
from tests.test_army_designs import ANDY, BUILDING_PALETTES, STATE, UNIT_PALETTES, skin_colours
from tests.test_tag import read_bmp

PAL = 0x05000000
WINDOW_BANK, HUD_BANK = 8, 23
# (x0, y0, x1, y1) of the screen's pixels compared exactly (no unit, no blinking cursor in them)
MENU_RECT = (170, 8, 236, 66)
DIALOGUE_RECT = (0, 126, 240, 160)
FORECAST_RECT = (160, 102, 236, 154)     # (the unit and terrain info box under the DAMAGE box, whose flash is animated)


def bank(e, n):
    return bytes(e.read(PAL + 32 * n, 32))


def rect(path, r):
    rows = read_bmp(path)
    x0, y0, x1, y1 = r
    return [rows[y][x0:x1] for y in range(y0, y1)]


def same_rows(a, b):
    """The window rows are the same, or the same colours at another phase of the gradient AW2 cycles through while a target is chosen."""
    return a == b or sorted(a[2:]) == sorted(b[2:])


def moments(ctx, g, tag, power=True, phase=None):
    """Pictures and window banks of the battle's screens (keyed by name) for a game at its first turn, army 1 to move, with army 1's Infantry at (4, 3) and army 2's at (5, 3)."""
    e = g.e
    out = {}

    def snap(name, pic=False):
        e.wait(2)
        out[name] = (bank(e, WINDOW_BANK), ctx.shot(g, f"{tag}_{name}") if pic else None)

    g.wait_for_input()
    e.wait(60)
    snap("map")
    g.open_map_menu()
    e.wait(24)
    snap("menu", pic=True)
    g.choose("CO", g.MAP_MENU)
    e.wait(60)
    snap("co", pic=True)
    for _ in range(2):
        e.press("B", 4)
        e.wait(20)
    g.wait_for_input()
    g.open_map_menu()
    g.choose("Intel", g.MAP_MENU)
    e.wait(40)
    e.press("A", 4)
    e.wait(60)
    snap("intel", pic=True)
    for _ in range(3):
        e.press("B", 4)
        e.wait(20)
    g.wait_for_input()
    g.select(4, 3)
    g.move_to(4, 3)
    snap("unit_menu", pic=True)
    g.choose("Fire", g.ACTION_MENU)
    e.wait(30)
    if phase is not None:      # (the same phase of the gradient: the box's pixels follow it)
        e.wait_until(lambda: bank(e, WINDOW_BANK) == phase, 120, step=1)
    snap("forecast", pic=True)
    g.pick_target(5, 3)
    g.wait_for_input()
    if power:
        g.charge_power(1, "power")
        g.open_map_menu()
        g.choose("Power", g.MAP_MENU)
        e.wait(80)
        snap("dialogue", pic=True)
    return out


def versus(ctx, skin, phase=None):
    m = ctx.map()
    m.unit(1, "infantry", 4, 3)
    m.unit(2, "infantry", 5, 3)
    g = ctx.boot_teams(m)
    e = g.e
    if skin:
        for _ in range(8):
            if e.u8(STATE + 4):
                break
            e.press("R", 4)
            e.wait(10)
        ctx.check(e.u8(STATE + 4) != 0, "the Teams screen put the skin on army 1")
    g.set_teams([ANDY, ANDY], {1})
    g.teams_to_rules()
    g.set_rules(visuals="a")
    g.start_battle()
    colour = g.player(1)["colour"]
    out = moments(ctx, g, "skin" if skin else "plain", phase=phase)
    out["colour"] = colour
    out["unit_row"] = bytes(e.read(UNIT_PALETTES + 32 * (colour - 1), 32))
    out["building_row"] = bytes(e.read(BUILDING_PALETTES + 32 * (colour - 1), 32))
    out["hud"] = bank(e, HUD_BANK)
    out["skin_on"] = e.u8(STATE)
    e.close()
    return out


def compare(ctx, label, a, b, pictures):
    """`a`: the skin's battle, `b`: the same battle with the host colour and no skin."""
    ramp, crest, gold = skin_colours()
    ctx.eq(a["colour"], b["colour"], f"{label}: army 1 wears the same colour (the skin's host)")
    ctx.eq(a["skin_on"], a["colour"], f"{label}: the skin sits on army 1's colour")
    for name in a:
        if name in ("map", "menu", "co", "intel", "unit_menu", "forecast", "dialogue") and name in b:
            ctx.check(same_rows(a[name][0], b[name][0]), f"{label}: the window palette on '{name}' is AW2's ({a[name][0].hex()} against {b[name][0].hex()})")
    for name, r in pictures.items():
        if name in a and name in b:
            pa, pb = rect(a[name][1], r), rect(b[name][1], r)
            diff = sum(x != y for ra, rb in zip(pa, pb) for x, y in zip(ra, rb))
            ctx.eq(diff, 0, f"{label}: '{name}' shows the same pixels as the game without the skin ({diff} differ)")
    row = [int.from_bytes(a["unit_row"][2 * i:2 * i + 2], "little") for i in range(16)]
    ctx.eq(row[2:8], ramp, f"{label}: the units' palette is Silver Nova's ramp")
    ctx.eq(int.from_bytes(a["building_row"][28:30], "little"), gold, f"{label}: the buildings' palette (the HQ) is Silver Nova's")
    ctx.check(a["hud"] != b["hud"], f"{label}: the funds box is the army's own (Silver Nova's), not the colour's")
    ctx.check(a["unit_row"] != b["unit_row"], f"{label}: the units are not the colour's own")


PICTURES = {"menu": MENU_RECT, "dialogue": DIALOGUE_RECT, "forecast": FORECAST_RECT}


@test(name="skin_windows_versus", modes=("ds",))
def versus_windows(ctx):
    b = versus(ctx, False)
    a = versus(ctx, True, phase=b["forecast"][0])
    compare(ctx, "versus", a, b, PICTURES)


def typed_box(ctx, g, name):
    """A shot of the power's dialogue box once its line has typed out: the two runs reach it a few frames apart, so a fixed wait
    catches one mid-line (or, waited long, one already in the power's animation)."""
    e = g.e
    e.wait_until(lambda: any(f == dsc.TEXT_BOX for _, _, f in g.procs()), 120)
    last, path = None, None
    for _ in range(40):
        path = ctx.shot(g, name)
        box = rect(path, DIALOGUE_RECT)
        if box == last:
            break
        last = box
        e.wait(6)
    return path


def gauntlet(ctx, code, tag):
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    boxes = []
    real = d.scripts_running

    def watch():
        running = real()
        if running and any(f == dsc.TEXT_BOX for _, _, f in g.procs()) and len(boxes) < 6:
            e.wait(30)
            boxes.append(bank(e, WINDOW_BANK))
        return running

    d.scripts_running = watch
    d.start(ga.ANDY, colour=code)
    colour = g.player(1)["colour"]
    out = {}
    g.goto(3, 18)
    e.wait(60)
    out["map"] = (bank(e, WINDOW_BANK), None)
    g.open_map_menu()
    e.wait(24)
    out["menu"] = (bank(e, WINDOW_BANK), ctx.shot(g, f"{tag}_menu"))
    g.choose("CO", g.MAP_MENU)
    e.wait(60)
    out["co"] = (bank(e, WINDOW_BANK), ctx.shot(g, f"{tag}_co"))
    for _ in range(2):
        e.press("B", 4)
        e.wait(20)
    g.wait_for_input()
    g.charge_power(1, "power")
    g.open_map_menu()
    g.choose("Power", g.MAP_MENU)
    out["dialogue"] = (bank(e, WINDOW_BANK), typed_box(ctx, g, f"{tag}_dialogue"))
    out["boxes"] = boxes
    out["colour"] = colour
    out["unit_row"] = bytes(e.read(UNIT_PALETTES + 32 * (colour - 1), 32))
    out["building_row"] = bytes(e.read(BUILDING_PALETTES + 32 * (colour - 1), 32))
    out["hud"] = bank(e, HUD_BANK)
    out["skin_on"] = e.u8(ga.HOSTS)
    e.close()
    return out


@test(name="skin_windows_gauntlet", modes=("ds",))
def gauntlet_windows(ctx):
    a = gauntlet(ctx, ga.EMERALD_SUN, "gauntlet_skin")
    b = gauntlet(ctx, ga.ORANGE_STAR, "gauntlet_plain")
    compare(ctx, "gauntlet", a, b, {"dialogue": DIALOGUE_RECT})
    ctx.require(bool(a["boxes"]) and len(a["boxes"]) == len(b["boxes"]), f"gauntlet: both runs show the intro's dialogue boxes ({len(a['boxes'])}, {len(b['boxes'])})")
    for i, (x, y) in enumerate(zip(a["boxes"], b["boxes"])):
        ctx.check(x == y, f"gauntlet: the intro's dialogue box {i} has AW2's window palette ({x.hex()} against {y.hex()})")
