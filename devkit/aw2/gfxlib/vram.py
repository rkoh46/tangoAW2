"""Decode a console dump: VRAM (96 KB), palette (1 KB), OAM (1 KB), I/O registers (0x60) as images and tables.

File formats: `NAME.vram` from the harness command `vram` (VRAM + PAL + OAM [+ IO]) or the offline_tabs token `V` (vram.bin, pal.bin, oam.bin, io.bin)."""
import struct
from pathlib import Path
from PIL import Image

VRAM, PAL, OAM, IO = 0x18000, 0x400, 0x400, 0x60


class Dump:
    def __init__(self, vram, pal, oam, io=None):
        self.vram, self.pal, self.oam, self.io = vram, pal, oam, io or b"\0" * IO

    @classmethod
    def load(cls, path):
        p = Path(path)
        if p.is_dir():
            return cls(*(((p / f"{n}.bin").read_bytes()) for n in ("vram", "pal", "oam")), (p / "io.bin").read_bytes() if (p / "io.bin").exists() else None)
        b = p.read_bytes()
        io = b[VRAM + PAL + OAM:VRAM + PAL + OAM + IO] if len(b) >= VRAM + PAL + OAM + IO else None
        return cls(b[:VRAM], b[VRAM:VRAM + PAL], b[VRAM + PAL:VRAM + PAL + OAM], io)

    # ---- palette ----
    def colour(self, i, obj=False):
        v = struct.unpack_from("<H", self.pal, (512 if obj else 0) + 2 * i)[0]
        return ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31)

    def bank(self, n, obj=False):
        return [self.colour(16 * n + i, obj) for i in range(16)]

    def palette_image(self, cell=12):
        im = Image.new("RGB", (16 * cell, 32 * cell + 4))
        for obj in (False, True):
            for n in range(16):
                for i in range(16):
                    c = self.colour(16 * n + i, obj)
                    for y in range(cell):
                        for x in range(cell):
                            im.putpixel((i * cell + x, (n + 16 * obj) * cell + y + 4 * obj), c)
        return im

    # ---- tiles ----
    def tile(self, n, base=0, bank=0, obj=False):
        """A 4bpp 8x8 tile (n counted from `base` bytes) as RGB pixels through palette bank `bank`; index 0 is transparent magenta."""
        pal = self.bank(bank, obj)
        off = base + 32 * n
        im = Image.new("RGB", (8, 8))
        for y in range(8):
            for x in range(4):
                b = self.vram[off + 4 * y + x] if off + 4 * y + x < len(self.vram) else 0
                for k, v in enumerate((b & 15, b >> 4)):
                    im.putpixel((2 * x + k, y), (255, 0, 255) if v == 0 else pal[v])
        return im

    def tile_sheet(self, base=0, count=512, bank=0, cols=32, obj=False, scale=2):
        rows = (count + cols - 1) // cols
        im = Image.new("RGB", (cols * 8, rows * 8))
        for n in range(count):
            im.paste(self.tile(n, base, bank, obj), ((n % cols) * 8, (n // cols) * 8))
        return im.resize((im.width * scale, im.height * scale), Image.NEAREST)

    def tile_bytes(self, n, base=0):
        return self.vram[base + 32 * n: base + 32 * n + 32]

    # ---- registers ----
    def reg(self, off):
        return struct.unpack_from("<H", self.io, off)[0]

    def dispcnt(self):
        v = self.reg(0)
        return {"mode": v & 7, "obj_1d": bool(v >> 6 & 1), "bg_on": [bool(v >> (8 + i) & 1) for i in range(4)], "obj_on": bool(v >> 12 & 1), "raw": v}

    def bgcnt(self, i):
        v = self.reg(8 + 2 * i)
        return {"prio": v & 3, "char_base": (v >> 2 & 3) * 0x4000, "bpp8": bool(v >> 7 & 1), "screen_base": (v >> 8 & 31) * 0x800, "size": v >> 14 & 3,
                "hofs": self.reg(0x10 + 4 * i) & 0x1FF, "vofs": self.reg(0x12 + 4 * i) & 0x1FF}

    def bg_cells(self, i):
        """The BG's 32x32 (first screenblock) map entries: [(tile, hflip, vflip, palbank)] row-major."""
        c = self.bgcnt(i)
        out = []
        for k in range(32 * 32):
            e = struct.unpack_from("<H", self.vram, c["screen_base"] + 2 * k)[0]
            out.append((e & 0x3FF, bool(e >> 10 & 1), bool(e >> 11 & 1), e >> 12))
        return out

    def bg_cell_at(self, i, px, py):
        """The map entry under screen pixel (px, py) of BG i (scroll applied, first 32x32 screenblock)."""
        c = self.bgcnt(i)
        x, y = (px + c["hofs"]) & 255, (py + c["vofs"]) & 255
        return self.bg_cells(i)[(y // 8) * 32 + x // 8], (x // 8, y // 8)

    # ---- OAM ----
    def sprites(self):
        out = []
        for k in range(128):
            a0, a1, a2 = struct.unpack_from("<HHH", self.oam, 8 * k)
            if a0 >> 8 & 3 == 2:
                continue   # disabled
            shape, size = a0 >> 14 & 3, a1 >> 14 & 3
            w, h = {0: [(8, 8), (16, 16), (32, 32), (64, 64)], 1: [(16, 8), (32, 8), (32, 16), (64, 32)], 2: [(8, 16), (8, 32), (16, 32), (32, 64)]}.get(shape, [(8, 8)] * 4)[size]
            x = a1 & 0x1FF
            x -= 512 if x >= 256 else 0
            y = a0 & 0xFF
            y -= 256 if y >= 160 else 0
            out.append({"index": k, "x": x, "y": y, "w": w, "h": h, "tile": a2 & 0x3FF, "pal": a2 >> 12, "prio": a2 >> 10 & 3, "bpp8": bool(a0 >> 13 & 1),
                        "hflip": bool(a1 >> 12 & 1), "vflip": bool(a1 >> 13 & 1)})
        return out
