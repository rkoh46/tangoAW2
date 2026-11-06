"""Silver Nova's moved (done) units, battle scenes and CO page emblem must never be the host colour's (`tests/test_sn_done.py`; docs/dev/army-packs.md "Skin lifetime").

A skin is patched into the ROM image of its host colour (army_skin.rs), and the game copies what it needs into palette RAM and OBJ VRAM when it loads a map, a screen or a
sprite. Anything the game loaded before the skin went on, or while it was briefly off (a battle scene clears the map's main loop), keeps the host's own colours. These helpers read
that state back: the done palette (BG bank 11), the skin's installed byte and the emblem's tiles in OBJ VRAM, against the clean ROM."""
import os
import struct
import subprocess

from PIL import Image

from . import paths

PAL = 0x0500_0000
MOVED_TABLE = 0x0810_E780          # the moved units' greys, a row of 32 bytes per colour (army_skin::TABLES "moved units")
MOVED_BANK = 11                    # the BG palette bank the game loads them into
SKIN_APPLIED = 0x09FC_0010         # + colour: the skin (index + 1) patched on it
SKIN_HOST = 0x0203_C500            # army_skin::STATE: the colour the first skin sits on
LOOKS = {
    "aw2": {"TANGOAW2_DS_GRAPHICS": "0"},
    "dstilt": {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"},
    "dsflat": {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0"},
}

_rom = None


def clean_rom():
    global _rom
    if _rom is None:
        _rom = open(paths.aw2_rom(), "rb").read()
    return _rom


def moved_rows(e, colour):
    """(the ROM image's moved row for `colour`, the clean ROM's), entries 1..11 (the ones that tint)."""
    a = MOVED_TABLE + 32 * (colour - 1)
    return e.read(a, 32)[2:24], clean_rom()[a - 0x0800_0000:][2:24]


def done_palette(e, colour):
    """What the done units are drawn in now: 'skin', 'host' or 'other' (bank 11 against the skin's row and the colour's own)."""
    skin, host = moved_rows(e, colour)
    now = e.read(PAL + 32 * MOVED_BANK, 32)[2:24]
    return "skin" if now == skin else "host" if now == host else "other"


def skin_state(e, colour):
    """(the skin patched on `colour`, the colour the skin sits on): (1, colour) while it is on."""
    return e.u8(SKIN_APPLIED + colour), e.u8(SKIN_HOST)


def emblem_source(colour):
    rom = clean_rom()
    u32 = lambda a: struct.unpack("<I", rom[a - 0x0800_0000:][:4])[0]
    row = 0x0848_B738 + 12
    base, first = u32(row), u32(row + 8) & 0xFFFF
    tiles = lambda i: rom[0x0848_B780 - 0x0800_0000 + 4 * i] * rom[0x0848_B780 - 0x0800_0000 + 4 * i + 1]
    return base + (sum(tiles(i) for i in range(first, 0x3D + colour)) & 0x3FF) * 32


def emblem_in_vram(e, colour):
    """(the colour's own emblem tiles are in OBJ VRAM, the skin's are): the CO page's header emblem is a sprite whose tiles the game copied when the page's sprite was made."""
    src = emblem_source(colour)
    host = clean_rom()[src - 0x0800_0000:][:128]
    skin = e.read(src, 128)
    vram = e.read(0x0601_0000, 0x8000)
    has = lambda b: any(vram[i:i + 128] == b for i in range(0, len(vram) - 127, 32))
    return has(host), has(skin) and skin != host


def png(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


def host_share(path, box=(0, 40, 120, 160)):
    """The share of red / orange pixels in `box` (Orange Star's units and figures; the skin's palette has only its small crest in red)."""
    im = Image.open(path).convert("RGB").crop(box)
    px = list(im.getdata())
    return sum(1 for r, g, b in px if r > 150 and r > 1.6 * max(g, b) + 20) / len(px)
