"""Readers for CO portrait parts in the player's ROMs (never stored): Advance Wars 2's presentation table and Dual Strike's appearance records
(the formats are documented in tango-gamesupport-aw2/src/ds_co_art.rs and crumb_art.rs). Pictures are palette-index arrays (0 transparent)."""
import struct
from functools import lru_cache
from .. import cfg

AW2_PRESENTATION, ROW = 0x084A0090, 0x44
AW2_HUD = 0x08102F64
DS_APPEARANCE, DS_APPEARANCE_LEN, DS_CO_RECORD, DS_CO_RECORD_LEN = 0x02152B8C, 0x54, 0x0215360C, 0x220
AW2_NAMES = ["Nell", "Andy", "Max", "Olaf", "Sami", "Grit", "Kanbei", "Sonja", "Eagle", "Drake", "Sturm", "Flak", "Lash", "Adder", "Hawke", "Hachi", "Colin", "Jess", "Sensei"]
DS_NAMES = {1: "Andy", 2: "Andy", 3: "Max", 4: "Olaf", 5: "Sami", 6: "Grit", 7: "Kanbei", 8: "Sonja", 9: "Eagle", 10: "Drake", 11: "Von Bolt", 12: "Jugger", 13: "Lash",
            14: "Koal", 15: "Hawke", 16: "Hachi", 17: "Colin", 18: "Jess", 19: "Sensei", 20: "Jake", 21: "Rachel", 22: "Sasha", 23: "Javier", 24: "Grimm", 25: "Kindle", 26: "Flak", 27: "Adder"}


def lz10(b):
    if b[0] != 0x10:
        raise ValueError("not LZ77")
    n = b[1] | b[2] << 8 | b[3] << 16
    out, p = bytearray(), 4
    while len(out) < n:
        f = b[p]
        p += 1
        for bit in range(8):
            if len(out) >= n:
                break
            if f & (0x80 >> bit):
                a, c = b[p], b[p + 1]
                p += 2
                ln, d = (a >> 4) + 3, ((a & 15) << 8 | c) + 1
                for _ in range(ln):
                    out.append(out[-d])
            else:
                out.append(b[p])
                p += 1
    return bytes(out)


def tiles(raw, w, h, order=None):
    """A picture of w x h pixels from 4bpp tiles in rows (or `order`: tile k -> (column, row)); a list of rows of palette indices."""
    tw = w // 8
    g = [[0] * w for _ in range(h)]
    for k in range(tw * (h // 8)):
        cx, cy = order(k) if order else (k % tw, k // tw)
        for y in range(8):
            for x in range(8):
                v = raw[32 * k + 4 * y + x // 2]
                g[8 * cy + y][8 * cx + x] = (v >> (4 * (x & 1))) & 15
    return g


def blit(dst, src, x0, y0):
    for y, r in enumerate(src):
        for x, v in enumerate(r):
            dst[y0 + y][x0 + x] = v


def bgr(c):
    return (((c & 31) * 255) // 31, (((c >> 5) & 31) * 255) // 31, (((c >> 10) & 31) * 255) // 31)


def to555(rgb):
    return (rgb[0] * 31 + 127) // 255 | ((rgb[1] * 31 + 127) // 255) << 5 | ((rgb[2] * 31 + 127) // 255) << 10


class Portrait:
    """One CO's parts: body (128 x 160), faces (3 of 48 x 48), mini (32 x 24), hud (32 x 16), eight palettes of 16 BGR555 colours."""

    def __init__(self, source, name, body, faces, mini, hud, palettes):
        self.source, self.name, self.body, self.faces, self.mini, self.hud, self.palettes = source, name, body, faces, mini, hud, palettes

    def copy(self):
        c = lambda g: [r[:] for r in g]
        return Portrait(self.source, self.name, c(self.body), [c(f) for f in self.faces], c(self.mini), c(self.hud), [p[:] for p in self.palettes])


def _mini(raw):
    # 12 tiles in rows of four (checked by drawing AW2's own: the picture reads as one face; the Rust notes describe the same data as two 16x24 sprites)
    return tiles(raw[:384], 32, 24)


@lru_cache(maxsize=1)
def _aw2():
    return cfg.aw2_rom().read_bytes()


def aw2_portrait(co):
    """AW2's own CO `co` (0 Nell .. 18 Sensei; 19..23 are the troopers' faces)."""
    rom = _aw2()
    u32 = lambda a: struct.unpack_from("<I", rom, a & 0x1FFFFFF)[0]
    row = AW2_PRESENTATION + ROW * co
    pair = u32(row)
    top, bot = lz10(rom[u32(pair) & 0x1FFFFFF:]), lz10(rom[u32(pair + 4) & 0x1FFFFFF:])
    body = [[0] * 128 for _ in range(160)]
    blit(body, tiles(top[:2048], 64, 64), 0, 0)
    blit(body, tiles(top[2048:4096], 64, 64), 64, 0)
    blit(body, tiles(bot[:2048], 64, 64), 0, 64)
    blit(body, tiles(bot[2048:4096], 64, 64), 64, 64)
    blit(body, tiles(bot[4096:5120], 64, 32), 0, 128)
    blit(body, tiles(bot[5120:6144], 64, 32), 64, 128)
    faces = [tiles(lz10(rom[u32(row + 0x0C + 4 * k) & 0x1FFFFFF:]), 48, 48) for k in range(3)]
    mini = _mini(rom[u32(row + 0x18) & 0x1FFFFFF:][:384])
    hraw = rom[(AW2_HUD + 0x100 * co) & 0x1FFFFFF:][:256]
    pal = rom[u32(row + 8) & 0x1FFFFFF:][:256]
    palettes = [list(struct.unpack_from("<16H", pal, 32 * s)) for s in range(8)]
    return Portrait("aw2", AW2_NAMES[co], body, faces, mini, tiles(hraw, 32, 16), palettes)


class Nds:
    def __init__(self, data):
        self.d = data
        u32 = lambda o: struct.unpack_from("<I", data, o)[0]
        self.arm9_off, self.arm9_load, self.arm9_size = u32(0x20), u32(0x28), u32(0x2C)
        fnt, fat = u32(0x40), u32(0x48)
        self.files = {}

        def walk(dir_id, prefix):
            base = fnt + 8 * (dir_id & 0xFFF)
            sub, first = u32(base), struct.unpack_from("<H", data, base + 4)[0]
            p, fid = fnt + sub, first
            while True:
                t = data[p]
                p += 1
                if t == 0:
                    break
                n, isdir = t & 0x7F, t & 0x80
                name = data[p:p + n].decode("latin-1")
                p += n
                if isdir:
                    walk(struct.unpack_from("<H", data, p)[0], prefix + name + "/")
                    p += 2
                else:
                    s, e = u32(fat + 8 * fid), u32(fat + 8 * fid + 4)
                    self.files[prefix + name] = (s, e)
                    fid += 1
        walk(0xF000, "")

    def arm9(self, addr, n):
        o = self.arm9_off + addr - self.arm9_load
        return self.d[o:o + n]

    def file(self, path):
        s, e = self.files[path]
        return self.d[s:e]


@lru_cache(maxsize=1)
def _nds():
    return Nds(cfg.ds_rom().read_bytes())


def ds_portrait(co):
    """Dual Strike's CO `co` (1..27, DS ids): the same parts. Its mugs are the same size as AW2's; the body is cut to AW2's 128 x 160."""
    nds = _nds()
    rec = nds.arm9(DS_APPEARANCE + DS_APPEARANCE_LEN * (co - 1), DS_APPEARANCE_LEN)
    w = lambda i: struct.unpack_from("<I", rec, 4 * i)[0]

    def fl(i):
        nm = nds.arm9(w(i), 3).decode()
        return lz10(nds.file("syogun/" + nm))
    body_raw = fl(0)
    B = 2048  # a 64 x 64 block of 64 tiles
    body = [[0] * 128 for _ in range(160)]
    for r in range(2):
        for c in range(2):
            blit(body, tiles(body_raw[(2 * r + c) * B:(2 * r + c + 1) * B], 64, 64), 64 * c, 64 * r)
    for c in range(2):  # the third block row: only its top half (32 rows) is kept
        blit(body, tiles(body_raw[(4 + c) * B:(5 + c) * B], 64, 64)[:32], 64 * c, 128)
    faces = [tiles(fl(i)[:36 * 32], 48, 48) for i in (4, 5, 6)]
    mini = _mini(nds.arm9(w(16), 384))
    hud = tiles(nds.arm9(w(17), 256), 32, 16)
    pal = nds.arm9(w(20), 256)
    palettes = [list(struct.unpack_from("<16H", pal, 32 * s)) for s in range(8)]
    return Portrait("ds", DS_NAMES[co], body, faces, mini, hud, palettes)


DS_NO_STAT = 0x0216E03C
CLASSES = ["foot", "direct vehicle", "indirect vehicle", "plane", "copter", "navy", "(oozium)", "direct (not foot)", "indirect", "transport", "black bomb"]


def ds_class_stats(co, mode):
    """Dual Strike CO `co`'s eleven class stats at power level `mode` (0 day to day, 1 CO Power, 2 Super Power): [[firepower %, defence %, move, range]] (see co_roster.rs `class_stat`)."""
    nds = _nds()
    rec = nds.arm9(DS_CO_RECORD + DS_CO_RECORD_LEN * co, DS_CO_RECORD_LEN)
    b = rec[0xA0 + 0x80 * mode:0xA0 + 0x80 * mode + 0x80]
    out = []
    for k in range(11):
        p = struct.unpack_from("<I", b, 0x54 + 4 * k)[0]
        out.append([0, 0, 0, 0] if p == DS_NO_STAT else list(struct.unpack_from("<4h", nds.arm9(p, 8))))
    return out


def ds_extras(co, mode):
    """Dual Strike CO `co`'s non-class numbers at power level `mode`: {vision, luck, bad_luck, terrain_cut, skills (the block's first byte)}."""
    nds = _nds()
    rec = nds.arm9(DS_CO_RECORD + DS_CO_RECORD_LEN * co, DS_CO_RECORD_LEN)
    b = rec[0xA0 + 0x80 * mode:0xA0 + 0x80 * mode + 0x80]
    i16 = lambda o: struct.unpack_from("<h", b, o)[0]
    return {"vision": i16(0x18), "luck": i16(0x1C), "bad_luck": i16(0x1E), "terrain_cut": max(0, i16(0x2A)), "skills": b[8]}


# The HP every unit gains / the enemy's lose in a power (AW2's and tangoAW2's own mass-HP powers), per level (d2d, CO Power, Super Power): Hawke's Black Wave and Black Storm.
HP_EFFECTS = {"Hawke": [(0, 0), (1, 1), (2, 2)], "Drake": [(0, 0), (0, 1), (0, 2)]}
HALVES = {"Drake"}      # powers that halve the enemy's fuel (Tsunami, Typhoon)

DS_NAMES_REV = {}
for _k, _v in DS_NAMES.items():
    DS_NAMES_REV[_v] = _k
DS_NAMES_REV["Andy"] = 2
DS_NAMES_REV["Nell"] = 1          # (DS_NAMES names id 1 "Andy" too: Dual Strike's record 1 is Nell, 2 Andy)
