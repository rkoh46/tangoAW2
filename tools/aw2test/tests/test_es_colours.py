"""Emerald Sun Campaign, every mission: each army wears its own country's colours, and the Emerald Sun skin only the player's (`-k es_colours_m`).
In the real game, after the mission is entered: the colour byte of every army is the mission's (the Rust spec, `ArmyDef::new(colour::X ..)`), the skin is
installed on the player's colour alone, and each army's unit palette row on the screen (less the entries the game redraws every frame) is that colour's palette in the ROM (Black Hole's own copy for 5):
an army drawn in another's colours (the bug of M9 and M13: the player picked a CO, the game gave the player Black Hole's colour) fails here."""
import os
import re

from aw2test import escampaign as es
from aw2test.harness import test

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "src")
NAMES = {"ORANGE_STAR": 1, "BLUE_MOON": 2, "GREEN_EARTH": 3, "YELLOW_COMET": 4, "BLACK_HOLE": 5}
PLAYERS, SKIN_APPLIED = 0x0849_9598, 0x09FC_0010
UNIT_PALETTES, BH_UNIT_PALETTE, PAL_RAM = 0x080D_3F04, 0x080D_3E84, 0x0500_0000


def spec_colours(n):
    """The colours of mission n's armies, from es_act*.rs."""
    key = f"es{n:02d}"
    for f in sorted(os.listdir(SRC)):
        if re.fullmatch(r"es_act\d\.rs", f):
            text = open(os.path.join(SRC, f)).read()
            m = re.search(rf"fn {key}\(\).*?\n\}}\n", text, re.S)
            if m:
                return [NAMES[c] for c in re.findall(r"ArmyDef::new\(colour::([A-Z_]+)", m.group(0))]
    raise KeyError(key)


def keep(row):
    """The army's own colours: the entries the game redraws every frame (6, and the outline ones 13..15) left out."""
    return bytes(b for i, b in enumerate(row) if i // 2 not in (0, 6, 13, 14, 15))


def check(ctx, n):
    e, g, d = es.enter(ctx, n)
    want = spec_colours(n)
    base = e.u32(PLAYERS)
    have = [e.u8(base + 0x3C * a + 0x1A) for a in range(1, len(want) + 1)]
    ctx.eq(have, want, f"M{n}: the armies' colours are the mission's")
    skinned = [c for c in range(1, 6) if e.u8(SKIN_APPLIED + c)]
    ctx.eq(skinned, [want[0]], f"M{n}: the Emerald Sun skin is on the player's colour alone")
    e.wait(30)
    for slot, c in enumerate(want):
        rom = BH_UNIT_PALETTE if c == 5 else UNIT_PALETTES + 0x20 * (c - 1)
        ctx.eq(keep(e.read(PAL_RAM + (25 + slot) * 32, 32)), keep(e.read(rom, 32)), f"M{n}: army {slot + 1}'s unit palette is colour {c}'s")
    e.close()


def _make(n):
    def fn(ctx):
        check(ctx, n)
    fn.__name__ = f"es_colours_m{n}"
    test(modes=("ds",))(fn)


for _n in range(1, 17):
    _make(_n)
