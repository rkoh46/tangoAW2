"""The BH Campaign's conquest of AW2's own world map (bh_conquest.rs, docs/dev/worldmap.md "AW2's own map"): the land of won missions turns Black
Hole's colours. `-k bh_conquest`; AW2TEST_REVIEW_DIR gets the pictures (the whole map read back from VRAM and palette RAM per state, and the screen)."""
import collections
import os
import shutil

from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import paths, rom as romlib, stitch
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

WM = 0x0202FDFC
BG3_MAP = 0x0600F000
BG3_CHARS = 0x06008000
PALRAM = 0x05000000
ROM_TILES, ROM_MAP, ROM_PAL = 0x081CC5F0, 0x081D0BAC, 0x081D1504
# the mission points of the BH Campaign by nation (the indexes of its mission table)
BH_ISLAND = (0, 1, 2, 27, 30)
GREEN = tuple(range(3, 11))
YELLOW = tuple(range(11, 16))
BLUE = tuple(range(16, 22))
ORANGE = (22, 23, 24, 25, 26, 28, 29)
BANK_OF = {"orange": 11, "blue": 12, "yellow": 13, "green": 14}


def bits(ms):
    return sum(1 << m for m in ms)


def vram_map(e):
    b = e.read(BG3_MAP, 0x1000)
    return [b[i] | b[i + 1] << 8 for i in range(0, 0x1000, 2)]


def palette(e):
    b = e.read(PALRAM + 0xC0, 320)
    return [b[i] | b[i + 1] << 8 for i in range(0, 320, 2)]


def rom_art(e):
    tiles = romlib.lz10(bytes(e.read(ROM_TILES, 0x8000)))
    m = romlib.lz10(bytes(e.read(ROM_MAP, 0x2000)))
    pal = [m2 for m2 in (bytes(e.read(ROM_PAL, 320)))]
    pal = [pal[i] | pal[i + 1] << 8 for i in range(0, 320, 2)]
    ents = [m[i] | m[i + 1] << 8 for i in range(0, 0x1000, 2)]
    return tiles, ents, pal


def render(tiles, ents, pal):
    """The map layer as the hardware draws it: 512 x 256 RGB."""
    from PIL import Image
    img = Image.new("RGB", (512, 256))
    px = img.load()
    col = lambda c: ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)
    for ci, en in enumerate(ents):
        scr, within = divmod(ci, 1024)
        X, Y = scr * 256 + within % 32 * 8, within // 32 * 8
        t, hf, vf, bank = en & 0x3FF, en >> 10 & 1, en >> 11 & 1, en >> 12
        for y in range(8):
            for x in range(8):
                yy, xx = (7 - y if vf else y), (7 - x if hf else x)
                v = tiles[t * 32 + yy * 4 + xx // 2]
                v = v >> 4 if xx & 1 else v & 15
                px[X + x, Y + y] = (0, 0, 0) if bank < 6 else col(pal[(bank - 6) * 16 + v])
    return img


def _boot_bh(ctx, won, at=0):
    e, g, d = a2.boot(ctx, won, 0xFFF | (0x1FF << 12), picks={}, at=at)
    d.wait_world_map()
    e.wait(120)
    return e, g, d


def _save(ctx, img, name):
    p = os.path.join(ctx.out, name)
    img.save(p)
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        shutil.copy(p, os.path.join(out, name))


def _screen(ctx, e, name):
    for _ in range(4):
        e.w16(WM, 0)
        e.w16(WM + 2, 0)
        e.w16(WM + 4, 700)
        e.w16(WM + 6, 700)
        e.wait(8)
        stitch.hide_hud(e)
    p = e.shot(os.path.join(ctx.out, name))
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        shutil.copy(p, os.path.join(out, os.path.basename(p)))


def _banks(m):
    return collections.Counter(x >> 12 for x in m)


@test(modes=("ds",))
def bh_conquest(ctx):
    states = [
        ("start", 0),
        ("some", bits((22, 23, 3, 4, 16))),
        ("green", bits(GREEN)),
        ("green_orange", bits(GREEN + ORANGE)),
        ("end", (1 << 30) - 1),
    ]
    ref = None
    seen = {}
    for name, won in states:
        e, g, d = _boot_bh(ctx, won)
        tiles, ents, pal = rom_art(e)
        m, p = vram_map(e), palette(e)
        ref = ref or (tiles, ents, pal)
        seen[name] = (m, p)
        _save(ctx, render(tiles, m, p), f"bh_conquest_{name}.png")
        if name in ("start", "some", "green_orange"):
            _screen(ctx, e, f"bh_conquest_{name}_screen")
        e.close()
    tiles, ents, pal = ref
    # (the start) Black Hole's island is Black Hole's from the start; the nations' land is AW2's own
    m, p = seen["start"]
    ctx.check(m == ents, "start: the tilemap is AW2's own (no cell is dark)")
    ctx.check(all(p[4 * 16 + k] != pal[4 * 16 + k] for k in range(1, 10)), "start: Black Hole's island (bank 10) is drawn in Black Hole's colours")
    ctx.check(p[5 * 16:10 * 16] != [0] * 80 and [p[(5 + i) * 16 + k] for i in range(4) for k in range(16)] == [pal[(5 + i) * 16 + k] for i in range(4) for k in range(16)],
              "start: the four nations keep AW2's colours")
    # (some) a few missions: some of Orange Star's and Green Earth's cells dark, not all
    m, p = seen["some"]
    b = _banks(m)
    ctx.check(0 < b[6] < _banks(ents)[11], f"some: part of Orange Star's land is dark ({b[6]} of {_banks(ents)[11]} cells)")
    ctx.check(0 < b[9] < _banks(ents)[14], f"some: part of Green Earth's land is dark ({b[9]} of {_banks(ents)[14]} cells)")
    ctx.check(0 < b[7] < _banks(ents)[12], f"some: part of Blue Moon's land is dark ({b[7]} cells)")
    ctx.check(b[8] == 0, "some: Yellow Comet's land untouched")
    # (a whole nation) Green Earth won: every one of its cells; the others as before
    m, p = seen["green"]
    b0, b = _banks(ents), _banks(m)
    ctx.eq(b[14] + b[9], b0[14], "green: Green Earth's cells are all in bank 9 or 14 (none lost)")
    ok = [i for i in range(2048) if ents[i] >> 12 == 14 and m[i] >> 12 == 9]
    ctx.check(len(ok) > 100, f"green: Green Earth's land is dark ({len(ok)} cells)")
    ctx.check(all(m[i] == ents[i] for i in range(2048) if ents[i] >> 12 in (11, 12, 13)), "green: the other nations' cells are unchanged")
    ctx.check(all(p[(3) * 16 + k] != pal[8 * 16 + k] for k in range(1, 10)) and p[3 * 16 + 10:3 * 16 + 15] == pal[8 * 16 + 10:8 * 16 + 15],
              "green: the twin palette is Green Earth's tinted, its sea and labels as before")
    # (the end) every land cell of every nation is dark
    m, p = seen["end"]
    for bank in (11, 12, 13, 14):
        land_cells = [i for i in range(2048) if ents[i] >> 12 == bank and land_cell(tiles, ents[i])]
        dark = [i for i in land_cells if m[i] >> 12 == bank - 5]
        ctx.eq(len(dark), len(land_cells), f"end: all {len(land_cells)} land cells of bank {bank} are dark")


def land_cell(tiles, en):
    t = en & 0x3FF
    n = sum(1 for b in tiles[t * 32:t * 32 + 32] for v in (b & 15, b >> 4) if 1 <= v <= 9)
    return n >= 6


@test(modes=("ds",))
def bh_conquest_leaves_aw2_campaign_alone(ctx):
    """AW2's own campaign's world map (Continue, pack on) is AW2's tilemap and palettes, whatever the BH Campaign did before in the same boot."""
    e = Emu(save=dc.aw2_campaign_save(ctx.out), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.open_campaign_box()
    d.box_row(0)
    e.wait(30)
    e.press("A", 8)
    for _ in range(3000):
        if d.world_map_up() and not d.scripts_running():
            break
        e.press("A", 4)
        e.wait(10)
    e.wait(60)
    tiles, ents, pal = rom_art(e)
    m, p = vram_map(e), palette(e)
    ctx.eq(e.u8(dc.ACTIVE), 0, "no campaign session")
    # (AW2 paints a won mission's part of the land itself, in its vivid banks 6..9, same tiles; nothing of ours)
    changed = [i for i in range(2048) if m[i] != ents[i]]
    ctx.check(all(m[i] & 0xFFF == ents[i] & 0xFFF and 6 <= m[i] >> 12 <= 9 for i in changed), f"AW2's map: only AW2's own repaint differs ({len(changed)} cells, banks 6..9)")
    ctx.check(p[:144] == pal[:144], "AW2's map: banks 6..14 are the ROM's palettes (no Black Hole tint)")
    ctx.eq([e.u32(a) for a in (0x08076AD0, 0x08076B14, 0x08076BB4, 0x08075C94, 0x08075E08, 0x080769BC)],
           [ROM_MAP] * 3 + [ROM_PAL] * 3, "AW2's map: the screen reads AW2's own tilemap and palette")
    e.close()
