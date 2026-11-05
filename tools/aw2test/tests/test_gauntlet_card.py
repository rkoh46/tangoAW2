"""Gauntlet's mission card (gauntlet_card.rs; `-k gauntlet_card`): AW2's card says "MISSION n" above the map's name and the seal says "MISSION START". In the
Gauntlet the word is GAUNTLET (the number is gone, the seal's band says GAUNTLET), in every real campaign the card is AW2's own, untouched.

The card's art in video memory: the word (three 32x16 sprites, OBJ tiles 0..23, drawn at x = 104), the number's digit tiles (28..67) and the seal's band (BG2, an
affine picture of 8 bit tiles; rows 74..85 between the rules). A Gauntlet card must differ from a campaign's in all three; two campaigns' cards must be equal.
`AW2TEST_TITLE_DIR` saves the cards (gauntlet_card.png, campaign_bh_card.png, campaign_aw2_card.png, campaign_ds_card.png) for the audit's before/after sheets."""

import os
import struct

from aw2test import bhact2 as a2
from aw2test import campaigns as cm
from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test
from tests.test_title_cards import MISSION_TITLE, card_number, procs, settle

OBJ_VRAM, OAM = 0x06010000, 0x07000000
SEAL_MAP, SEAL_TILES = 0x06007800, 0x06008000
WORD_X = 0x68
GAUNTLET_SHIFT = 18


def card_art(e):
    """What the card's word, number and stamp are made of: (word tile bytes, digit tile bytes, the band's pixels (rows 74..85, x 26..132), the word sprites' x)."""
    word = bytes(e.read(OBJ_VRAM, 24 * 32))
    digits = bytes(e.read(OBJ_VRAM + 28 * 32, 40 * 32))
    amap = e.read(SEAL_MAP, 1024)
    tiles = e.read(SEAL_TILES, 256 * 64)
    band = bytes(tiles[amap[(y >> 3) * 32 + (x >> 3)] * 64 + (y & 7) * 8 + (x & 7)] for y in range(74, 86) for x in range(26, 133))
    oam = e.read(OAM, 0x400)
    xs = [struct.unpack_from("<HHH", oam, 8 * k)[1] & 511 for k in range(128)
          if struct.unpack_from("<HHH", oam, 8 * k)[2] & 1023 == 0 and struct.unpack_from("<HHH", oam, 8 * k)[0] & 255 == 8]
    return word, digits, band, (xs or [None])[0]


def word_runs(word):
    """The word's letters as runs of ink columns of its 96 x 16 picture (tiles 1D mapped: a sprite is 4 x 2 tiles in a row)."""
    ink = [False] * 96
    for x in range(96):
        for y in range(16):
            t = (x // 32) * 8 + (y // 8) * 4 + (x % 32) // 8
            b = word[t * 32 + (y % 8) * 4 + (x % 8) // 2]
            if (b >> (4 * (x & 1))) & 15:
                ink[x] = True
    runs, prev = 0, False
    for v in ink:
        runs += v and not prev
        prev = v
    return runs, sum(ink)


def save_png(e, ctx, name):
    out = os.environ.get("AW2TEST_TITLE_DIR")
    e.shot(os.path.join(ctx.out, "card"))
    if out:
        os.makedirs(out, exist_ok=True)
        from PIL import Image
        Image.open(os.path.join(ctx.out, "card.bmp")).convert("RGB").save(os.path.join(out, name))


def gauntlet_card(ctx):
    """The Gauntlet's card on Dustwind Basin (mission 3 of the definition): settled."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open(True, map=2)
    d.wait_army()
    e.press("A", 6)
    for _ in range(3000):
        if MISSION_TITLE in procs(e):
            break
        e.wait(14)
    else:
        return e, None
    e.wait(420)
    return e, card_art(e)


def bh_card(ctx):
    e, g, d = a2.boot(ctx, (1 << 30) - 1, 0xFFF | (0x1FF << 12), picks={}, at=0)
    if not settle(e, d, 0):
        return e, None
    return e, card_art(e)


def aw2_card(ctx):
    """AW2's own campaign, New: mission 1's card."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    cm.aw2_box(e, d, ctx.ds, from_title=True)
    d.box_row(1)
    e.wait(30)
    e.press("A", 8)
    for _ in range(3000):
        if MISSION_TITLE in procs(e):
            break
        e.press("A", 4)
        e.wait(14)
    else:
        return e, None
    e.wait(420)
    return e, card_art(e)


def ds_card(ctx):
    """The Dual Strike Campaign's first card."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=0, pick=False)
    d.wait_world_map()
    d.pick_mission()
    for _ in range(3000):
        if MISSION_TITLE in procs(e):
            break
        e.press("A", 4)
        e.wait(14)
    else:
        return e, None
    e.wait(420)
    return e, card_art(e)


@test(modes=("ds",))
def gauntlet_card_says_gauntlet(ctx):
    """The Gauntlet's card: the word is eight letters of ink (GAUNTLET), drawn 18 px right of AW2's, the number's tiles are blank, the seal's band is not the campaign's."""
    e, art = gauntlet_card(ctx)
    if not ctx.check(art is not None, "the Gauntlet's mission card came up"):
        return
    word, digits, band, x = art
    save_png(e, ctx, "gauntlet_card.png")
    e.close()
    runs, ink = word_runs(word)
    ctx.eq(runs, 8, f"the word's picture has eight letters (runs of ink columns), {ink} ink columns")
    ctx.eq(x, WORD_X + GAUNTLET_SHIFT, "the word is drawn 18 px right of AW2's")
    ctx.check(not any(digits), "the number's digit tiles are blank (no MISSION n)")
    ctx.check(any(band), "the seal's band has a stamped word")
    e2, ref = bh_card(ctx)
    if not ctx.check(ref is not None, "a campaign card for comparison came up"):
        return
    save_png(e2, ctx, "campaign_bh_card.png")
    e2.close()
    ctx.check(word != ref[0], "the Gauntlet's word is not AW2's MISSION")
    ctx.check(band != ref[2], "the Gauntlet's stamp is not AW2's MISSION START")


@test(modes=("ds",))
def gauntlet_card_campaigns_keep_mission(ctx):
    """The real campaigns' cards (BH, AW2's own, Dual Strike's) are one and the same art: MISSION n (digits drawn), MISSION START, the word at x = 104."""
    arts = {}
    for name, fn in (("bh", bh_card), ("aw2", aw2_card), ("ds", ds_card)):
        e, art = fn(ctx)
        if ctx.check(art is not None, f"{name}: the campaign's card came up"):
            arts[name] = art
            save_png(e, ctx, f"campaign_{name}_card.png")
        e.close()
    for name, (word, digits, band, x) in arts.items():
        ctx.eq(x, WORD_X, f"{name}: the word sits at x = 104")
        ctx.check(any(digits), f"{name}: the number's tiles have ink (MISSION n)")
        ctx.check(any(band), f"{name}: the stamp has its words")
    names = list(arts)
    for other in names[1:]:
        ctx.check(arts[other][0] == arts[names[0]][0], f"{other}: the word's tiles are {names[0]}'s (AW2's MISSION)")
        ctx.check(arts[other][2] == arts[names[0]][2], f"{other}: the stamp is {names[0]}'s (AW2's MISSION START)")
    if "bh" in arts:
        e, g, d = a2.boot(ctx, (1 << 30) - 1, 0xFFF | (0x1FF << 12), picks={}, at=0)
        ctx.check(settle(e, d, 0), "BH mission 1's card again")
        ctx.eq(card_number(e), 1, "it says MISSION 1")
        e.close()
