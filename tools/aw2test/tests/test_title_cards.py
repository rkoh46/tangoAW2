"""The mission title card ("MISSION n" over the name in the big font, over the world map and the seal; title_card.rs): every
Black Hole Campaign mission's card, played in the game, must keep every pixel of its name's glyphs on the screen and inside
an 8 px margin on both sides (a long name is set on two lines). `-k title_card` runs them (one test per mission, so they
run in parallel); pictures: `AW2TEST_TITLE_DIR` gets title_bh_NN.png (the settled card) for a contact sheet.

The Dual Strike Campaign's names are checked for width by `title_card_ds_names_fit` (they are all one line)."""

import os
import re
import struct

from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.harness import test

MISSION_TITLE = 0x086165B0       # the mission card's proc (MissionTitle_*)
FONT_TABLE = 0x08616194          # the title font: (character, glyph ptr, width) x 12 bytes
MARGIN = 8
SCREEN_W, SCREEN_H = 240, 160
TITLE_Y = (24, 54)               # a glyph row's sprite y: one line, or the second of two
OAM, OBJ_VRAM, OBJ_PAL = 0x07000000, 0x06010000, 0x05000200
BH_MISSIONS = 31


def procs(e):
    return {e.u32(p) for p in range(0x0200D610, 0x0200E418, 0x6C)}


def font_widths():
    rom = open(paths.aw2_rom(), "rb").read()
    t = FONT_TABLE - 0x08000000
    out = {}
    for i in range(64):
        c = rom[t + 12 * i]
        if c:
            out[chr(c)] = struct.unpack_from("<I", rom, t + 12 * i + 8)[0]
    return out


def title_pixels(e):
    """The pixels of the card's name glyphs: [(x, y)] of every opaque pixel of the glyph sprites (16x32, tiles 128 up, the
    name's rows), x as drawn (negative left of the screen, past 239 right of it, so a clipped glyph shows)."""
    oam = e.read(OAM, 0x400)
    vram = e.read(OBJ_VRAM, 0x8000)
    pix = []
    for k in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, 8 * k)
        shape, size, mode = a0 >> 14, a1 >> 14, (a0 >> 8) & 3
        y, x, tile = a0 & 255, a1 & 511, a2 & 1023
        if mode == 2 or (shape, size) != (2, 2) or tile < 128 or tile % 8 or y not in TITLE_Y:
            continue
        x = x - 512 if x >= 256 else x
        for ty in range(4):
            for tx in range(2):
                base = (tile + ty * 2 + tx) * 32
                for py in range(8):
                    for px in range(8):
                        b = vram[base + py * 4 + px // 2]
                        if (b >> (4 * (px & 1))) & 15:
                            pix.append((x + tx * 8 + px, y + ty * 8 + py))
    return pix


# The missions whose CO screen asks for two picks that must differ (M12 and M15: the lead and the partner).
PAIRS = {11: [bh.STURM, bh.HAWKE], 14: [bh.STURM, bh.HAWKE]}


def settle(e, d, k):
    """Plays the mission pick up to the card and until its name has typed out."""
    d.pick_mission()
    if k in PAIRS:
        picked = []
        for _ in range(2):
            for _ in range(200):
                if d.on_co_select() and d.co_cursor():
                    break
                e.wait(10)
            e.wait(60)
            picked.append(d.choose_co([c for c in PAIRS[k] if c not in picked]))
            e.wait(60)
            for _ in range(40):
                if not d.on_co_select():
                    break
                e.wait(10)
    for _ in range(3000):
        if MISSION_TITLE in procs(e):
            break
        e.press("A", 4)          # (the CO screens, one or two to pick, and any scene before the card)
        e.wait(14)
    else:
        return False
    e.wait(420)
    return True


def card_check(ctx, k, label):
    e, g, d = a2.boot(ctx, (1 << 30) - 1, 0xFFF | (0x1FF << 12), picks={}, at=k)
    if not ctx.check(settle(e, d, k), f"{label}: the mission card came up"):
        return
    pix = title_pixels(e)
    ctx.require(pix, f"{label}: the name's glyphs are on the card")
    xs, ys = [p[0] for p in pix], [p[1] for p in pix]
    ctx.log(f"{label}: name pixels x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}")
    ctx.check(min(xs) >= MARGIN, f"{label}: the name keeps {MARGIN} px at the left (starts at x={min(xs)})")
    ctx.check(max(xs) <= SCREEN_W - 1 - MARGIN, f"{label}: the name keeps {MARGIN} px at the right (ends at x={max(xs)})")
    ctx.check(min(ys) >= 0 and max(ys) < SCREEN_H, f"{label}: the name is on the screen vertically (y {min(ys)}..{max(ys)})")
    out = os.environ.get("AW2TEST_TITLE_DIR")
    e.shot(os.path.join(ctx.out, "card"))
    if out:
        os.makedirs(out, exist_ok=True)
        from PIL import Image
        Image.open(os.path.join(ctx.out, "card.bmp")).convert("RGB").save(os.path.join(out, f"title_bh_{k + 1:02d}.png"))
    e.close()


def _bh(k):
    def run(ctx):
        card_check(ctx, k, f"BH mission {k + 1}")
    return run


for _k in range(BH_MISSIONS):
    test(name=f"title_card_bh_{_k + 1:02d}", modes=("ds",))(_bh(_k))


@test(modes=("ds",))
def title_card_ds_names_fit(ctx):
    """Every Dual Strike Campaign name, in the big font, fits the card on one line (it is right-aligned at x=224)."""
    widths = font_widths()
    data = dc.DsData()
    n = 0
    for i in range(60):
        try:
            name = data.mission(i)["name"]
        except Exception:  # noqa: BLE001 (past the last record)
            break
        n += 1
        w = sum(widths[c] + 1 for c in name if c in widths)
        ctx.check(w <= 224 - MARGIN, f"DS mission {i} {name!r}: {w} px of {224 - MARGIN}")
    ctx.check(n >= 28, f"{n} Dual Strike names read")
