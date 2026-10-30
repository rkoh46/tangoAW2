"""A CO's unit designs and HQ follow the CO's own nation; an army colour only recolours (`-k army_designs`, docs/dev/army-packs.md "Designs follow the CO").

Real Versus battles on the Emerald Sun colour (the Teams screen's R puts the skin on army 1), the CO of army 1 being
  - a Black Hole CO (Asuka): the map Infantry and the HQ are Black Hole's pictures, in Emerald Sun's palette;
  - a base nation's CO (Andy): Orange Star's pictures, in Emerald Sun's palette;
  - an Emerald Sun CO (Klaus): the skin's plumed Infantry and domed HQ, in Emerald Sun's palette;
and an Emerald Sun CO in a base colour (Klaus without the skin): the skin's pictures in the colour's own palette, with only the plume's red (unit palette entry 14) and the HQ's gold (building entry 14) added.

Shapes are compared, not colours: the pictures drawn are the 4-tile idle Infantry (the map's unit tiles, found by the BG map's entries) and the 16 x 32 HQ sprite, and their palette-index bytes are looked up
among AW2's pictures of every country and the skin's own (read from the console's ROM image, where the skin's pictures are kept). The palette is the unit palette row of army 1's colour (ROM image)."""

import os
import re

from aw2test import rom as romlib
from aw2test.harness import test

ASUKA, ANDY, KLAUS = 92, 1, 86
STATE = 0x0203C500                      # army_skin::STATE: +0 the colour the first skin sits on, +4.. the Teams screen's choices
ART = 0x09FD0000                        # army_skin::art_at(0) = DATA + 0x10000: the first skin's pictures (map Infantry, Mech, HQ ...)
UNIT_SHEET, FRAME_BYTES, SLOT_TABLE = 0x0810BE60, 0xD80, 0x08499608
HQ_ART = 0x080D16C4                     # a country's HQ: 8 tiles, 0x100 bytes
UNIT_PALETTES = 0x0810E6E0
BUILDING_PALETTES = 0x080D3F04
SHEET_TILE = 0x235
SKIN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "skins", "emerald_sun.toml")


def bgr(rgb):
    r, g, b = (int(rgb[i:i + 2], 16) for i in (0, 2, 4))
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def skin_colours():
    text = open(SKIN_FILE).read()
    pick = lambda key: [bgr(c) for c in re.findall(r"[0-9A-Fa-f]{6}", re.search(rf"^{key}\s*=\s*\[([^\]]*)\]", text, re.M).group(1))]
    one = lambda key: bgr(re.search(rf"^{key}\s*=\s*\"?#?([0-9A-Fa-f]{{6}})", text, re.M).group(1))
    return pick("ramp"), one("crest"), one("gold")


def candidates(e):
    """label -> bytes: AW2's Infantry (every country and frame) and HQ (every country), and the skin's."""
    out = {}
    for country in range(1, 6):
        slot = e.u16(SLOT_TABLE + 2 * (25 * (country - 1) + 1))
        for f in range(3):
            out[("inf", country, f)] = e.read(UNIT_SHEET + FRAME_BYTES * f + 128 * slot, 128)
        out[("hq", country)] = e.read(HQ_ART + 0x100 * (country - 1), 0x100)
    for f in range(3):
        out[("inf", "es", f)] = e.read(ART + 128 * (2 * f), 128)
    out[("hq", "es")] = e.read(ART + 0x400, 0x100)
    return out


def bg_slots(e):
    """The unit sprite slots the map's tile layers use (BG map entries with a tile in the unit sheet's range), with the sheet's bytes of each."""
    used = {}
    for bg in range(4):
        cnt = e.u16(0x04000008 + 2 * bg)
        base = 0x06000000 + ((cnt >> 8) & 31) * 0x800
        size = {0: 1, 1: 2, 2: 2, 3: 4}[cnt >> 14]
        for i in range(0x400 * size):
            t = e.u16(base + 2 * i) & 0x3FF
            if SHEET_TILE <= t < SHEET_TILE + 4 * 64 and (t - SHEET_TILE) % 4 == 0:
                used[(t - SHEET_TILE) // 4] = e.read(0x06000000 + 32 * t, 128)
    return used


def hq_sprites(e):
    """The 16 x 32 sprites in OAM (the HQ is the only 16 x 32 sprite on the map): their 8 tiles' bytes."""
    oam = e.read(0x07000000, 0x400)
    out = []
    for i in range(128):
        a0 = oam[8 * i] | oam[8 * i + 1] << 8
        a1 = oam[8 * i + 2] | oam[8 * i + 3] << 8
        a2 = oam[8 * i + 4] | oam[8 * i + 5] << 8
        if (a0 >> 8) & 3 == 2 or a0 >> 14 != 2 or a1 >> 14 != 2:
            continue
        out.append(e.read(0x06010000 + 32 * (a2 & 0x3FF), 0x100))
    return out


def labels(found, cands, kind):
    return {k[1] for blob in found for k, v in cands.items() if k[0] == kind and v == blob}


def play(ctx, co, skin, blue=False):
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
    elif blue:
        # (the colours cycle on R: stop at Yellow Comet: Blue Moon is army 2's here)
        for _ in range(6):
            if e.u8(0x02017C5D) == 4:
                break
            e.press("R", 4)
            e.wait(10)
    g.set_teams([co, ANDY], {1})
    g.teams_to_rules()
    g.set_rules(visuals="a")
    g.start_battle()
    g.wait_for_input()
    e.wait(60)
    return g


def check(ctx, name, co, skin, designs, palette, blue=False):
    """`designs`: "es" or the country (1..5) whose Infantry and HQ army 1 shows; `palette`: "skin" (the skin's ramp in army 1's unit palette) or "colour" (the colour's own)."""
    g = play(ctx, co, skin, blue)
    e = g.e
    colour = g.player(1)["colour"]
    if blue:
        ctx.eq(colour, 4, f"{name}: army 1 wears Yellow Comet")
    ramp, crest, gold = skin_colours()
    cands = candidates(e)
    row = e.read(UNIT_PALETTES + 32 * (colour - 1), 32)
    have = [int.from_bytes(row[2 * i:2 * i + 2], "little") for i in range(16)]
    ctx.log(f"{name}: army 1 colour {colour}, CO {g.player(1)['co']}, unit palette {[hex(c) for c in have]}")
    ctx.eq(g.player(1)["co"], co, f"{name}: army 1's CO")
    if palette == "skin":
        ctx.eq(have[2:8], ramp, f"{name}: the unit palette is Emerald Sun's ramp")
        ctx.eq(e.u8(STATE), colour, f"{name}: the skin sits on army 1's colour")
    else:
        ctx.check(have[2:8] != ramp, f"{name}: the colour's own palette, not Emerald Sun's")
        ctx.eq(have[14], crest, f"{name}: the plume's red is in the palette")
        brow = e.read(BUILDING_PALETTES + 32 * (colour - 1), 32)
        ctx.eq(int.from_bytes(brow[28:30], "little"), gold, f"{name}: the HQ's gold is in the building palette")
    if designs == "es":
        # (the palette the screen is drawing with, not only the ROM's table: the plume is the skin's red in the army's palette bank, once the map is up)
        ram = e.read(0x05000000, 0x400)
        banks = [ram[32 * k:32 * k + 32] for k in range(32)]
        mine = [b for b in banks if [int.from_bytes(b[2 * i:2 * i + 2], "little") for i in (2, 3, 4, 5, 7, 8, 9, 10)] == [have[i] for i in (2, 3, 4, 5, 7, 8, 9, 10)]]
        ctx.require(bool(mine), f"{name}: the army's unit palette is in palette RAM")
        ctx.check(all(int.from_bytes(b[28:30], "little") == crest for b in mine), f"{name}: the plume's red is in the palette the screen draws with ({[hex(int.from_bytes(b[28:30], 'little')) for b in mine]})")
    slots = bg_slots(e)
    inf = labels(slots.values(), cands, "inf")
    hq = labels(hq_sprites(e), cands, "hq")
    ctx.log(f"{name}: Infantry designs on the map {sorted(map(str, inf))} (slots {sorted(slots)}), HQ designs {sorted(map(str, hq))}")
    want = designs
    ctx.check(want in inf, f"{name}: army 1's Infantry is {want}'s picture ({sorted(map(str, inf))})")
    ctx.check(want in hq, f"{name}: army 1's HQ is {want}'s picture ({sorted(map(str, hq))})")
    if want != "es":
        ctx.check("es" not in inf, f"{name}: no Emerald Sun Infantry on the map")
        ctx.check("es" not in hq, f"{name}: no Emerald Sun HQ on the map")
    ctx.shot(g, name)
    # (the battle scene, both sides, for the pictures: army 1's Infantry attacks army 2's)
    try:
        g.select(4, 3)
        g.move_to(4, 3)
        g.choose("Fire", g.ACTION_MENU)
        g.pick_target(5, 3)
        for k in range(4):
            e.wait(45)
            ctx.shot(g, f"{name}_scene{k}")
    except Exception as ex:      # (pictures only: the checks above are the test)
        ctx.log(f"{name}: no battle scene pictures ({ex})")
    g.e.close()


@test(name="army_designs_black_hole_co_in_the_skin_colour", modes=("ds",))
def black_hole_co(ctx):
    check(ctx, "asuka_in_es", ASUKA, True, 5, "skin")


@test(name="army_designs_base_co_in_the_skin_colour", modes=("ds",))
def base_co(ctx):
    check(ctx, "andy_in_es", ANDY, True, 1, "skin")


@test(name="army_designs_es_co_in_the_skin_colour", modes=("ds",))
def es_co(ctx):
    check(ctx, "klaus_in_es", KLAUS, True, "es", "skin")


@test(name="army_designs_es_co_in_a_base_colour", modes=("ds",))
def es_co_base_colour(ctx):
    check(ctx, "klaus_yellow", KLAUS, False, "es", "colour", blue=True)
