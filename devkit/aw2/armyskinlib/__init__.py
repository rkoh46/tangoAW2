"""Rendering and checks for army skins (docs/dev/army-packs.md): a patched ROM view and the pictures of the skin's art."""
import json, struct, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from .. import cfg, util

NAMES = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}
SKIN_DIR = cfg.REPO / "tango-gamesupport-aw2" / "skins"
EXE = lambda: cfg.REPO / "target" / "release" / "examples" / "aw2_skin_dump"


def rgb555(c):
    return (((c & 31) * 255) // 31, (((c >> 5) & 31) * 255) // 31, (((c >> 10) & 31) * 255) // 31)


class Rom:
    """The ROM image the console would hold: the file, plus a skin's writes when `host` is given."""

    def __init__(self, host=0, skin=None):
        self.b = bytearray(cfg.aw2_rom().read_bytes())
        self.info = None
        if host:
            self.info = dump(host, skin)
            for p in self.info["patches"]:
                o = p["addr"] & 0x01FFFFFF
                d = bytes.fromhex(p["hex"])
                if o + len(d) <= len(self.b):
                    self.b[o:o + len(d)] = d

    def u16(self, a):
        o = a & 0x01FFFFFF
        return struct.unpack_from("<H", self.b, o)[0]

    def u32(self, a):
        o = a & 0x01FFFFFF
        return struct.unpack_from("<I", self.b, o)[0]

    def pal(self, a, n=16):
        return [rgb555(self.u16(a + 2 * i)) for i in range(n)]

    def raw(self, a, n):
        o = a & 0x01FFFFFF
        return bytes(self.b[o:o + n])


def dump(host, skin=None):
    exe = EXE()
    if not exe.exists():
        util.die("aw2_skin_dump is not built: aw2dev build --examples")
    cmd = [str(exe), str(cfg.aw2_rom()), str(host)] + ([str(skin)] if skin else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        util.die("aw2_skin_dump: " + r.stderr[-300:])
    return json.loads(r.stdout)


def tile_px(b, off):
    rows = []
    for y in range(8):
        row = []
        for x in range(4):
            v = b[off + y * 4 + x]
            row += [v & 15, v >> 4]
        rows.append(row)
    return rows


def sprite(raw, wt, ht, pal, scale=1):
    im = Image.new("RGBA", (wt * 8, ht * 8), (0, 0, 0, 0))
    for k in range(wt * ht):
        px = tile_px(raw, 32 * k)
        ox, oy = (k % wt) * 8, (k // wt) * 8
        for y in range(8):
            for x in range(8):
                i = px[y][x]
                if i:
                    im.putpixel((ox + x, oy + y), pal[i] + (255,))
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale != 1 else im


# AW2's tables (see src/army_skin.rs)
UNIT_SHEET, FRAME, SLOT_TABLE = 0x0810BE60, 0xD80, 0x08499608
UNIT_PAL, BLD_PAL, HQ_ART, EMB_ROWS, EMB_SIZES = 0x0810E6E0, 0x080D3F04, 0x080D16C4, 0x0848B738, 0x0848B780


def foot(rom, colour, unit, frame, pal, scale=1):
    slot = rom.u16(SLOT_TABLE + 2 * (25 * (colour - 1) + unit))
    return sprite(rom.raw(UNIT_SHEET + FRAME * frame + 128 * slot, 128), 2, 2, pal, scale)


def hq(rom, colour, pal, scale=1, snow=False):
    a = (0x080D1BC4 if snow else HQ_ART) + 0x100 * (colour - 1)
    return sprite(rom.raw(a, 0x100), 2, 4, pal, scale)


def emblem(rom, colour, scale=1):
    row = EMB_ROWS + 12
    base, palp, first = rom.u32(row), rom.u32(row + 4), rom.u32(row + 8) & 0xFFFF
    size = lambda i: rom.raw(EMB_SIZES + 4 * i, 2)
    before = sum(size(i)[0] * size(i)[1] for i in range(first, 0x3D + colour))
    src = base + (before & 0x3FF) * 32
    return sprite(rom.raw(src, 128), 2, 2, rom.pal(palp), scale)


def preview(host, out, skin=None):
    """The skin's art next to AW2's own, at 8x (units, HQ, emblem) and its palettes: one PNG."""
    base = Rom()
    sk = Rom(host, skin)
    S = 8
    cols = [(c, base) for c in (3, 1, 2, 4, 5)]
    W = 16 * S * 6 * 2 + 40
    im = Image.new("RGB", (1400, 1050), (56, 56, 64))
    d = ImageDraw.Draw(im)
    y = 6
    d.text((6, y), f"Skin on colour {host} ({NAMES[host]}'s slot): Infantry/Mech 3 frames, AW2's colours first", fill=(255, 255, 255))
    y += 14
    x = 6
    for unit in (1, 2):
        for c, r in [(c, base) for c in (1, 3, 5)] + [(host, sk)]:
            pal = r.pal(UNIT_PAL + 32 * (c - 1))
            for f in range(3):
                g = foot(r, c, unit, f, pal, S)
                im.paste(g, (x, y), g)
                x += 16 * S + 2
            x += 10
        x = 6
        y += 16 * S + 8
    # HQ and emblems
    d.text((6, y), "HQ (clear, snow) and emblem: AW2's five, then the skin", fill=(255, 255, 255))
    y += 14
    x = 6
    for c in (1, 2, 3, 4, 5):
        g = hq(base, c, base.pal(BLD_PAL + 32 * (c - 1)), 4)
        im.paste(g, (x, y), g)
        x += 16 * 4 + 6
    for snow in (False, True):
        g = hq(sk, host, sk.pal(BLD_PAL + 32 * (host - 1)), 4, snow)
        im.paste(g, (x, y), g)
        x += 16 * 4 + 6
    x += 20
    for c in (1, 2, 3, 4, 5):
        g = emblem(base, c, 4)
        im.paste(g, (x, y), g)
        x += 16 * 4 + 4
    g = emblem(sk, host, 4)
    im.paste(g, (x + 10, y), g)
    g = emblem(sk, host, 8)
    im.paste(g, (x + 90, y), g)
    y += 32 * 4 + 14
    # palettes
    d.text((6, y), "Palettes (map unit, moved, moving, building) of each colour; the skin's last", fill=(255, 255, 255))
    y += 14
    for name, addr in [("unit", UNIT_PAL), ("moved", UNIT_PAL + 0xA0), ("moving", 0x0810EA60), ("building", BLD_PAL)]:
        x = 6
        d.text((x, y + 2), name, fill=(255, 255, 255))
        x = 70
        for c in (1, 2, 3, 4, 5):
            for p in base.pal(addr + 32 * (c - 1)):
                d.rectangle([x, y, x + 9, y + 11], fill=p)
                x += 10
            x += 6
        for p in sk.pal(addr + 32 * (host - 1)):
            d.rectangle([x, y, x + 9, y + 11], fill=p)
            x += 10
        y += 16
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.crop((0, 0, 1400, y + 6)).save(out)
    return out
