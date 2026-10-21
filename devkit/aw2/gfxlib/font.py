"""AW2's proportional text font, read from the user's ROM at run time (glyph pointers 0x084C32E4, widths 0x084C36E4; 4bpp rows, 3 blank rows then 14 incl. descenders).
Cached as a pickle under ~/.aw2dev/cache (derived from the ROM: never committed)."""
import hashlib, pickle
from pathlib import Path
from .. import cfg

GLYPHS, WIDTHS = 0x084C32E4, 0x084C36E4
INK = 0xA


def _cache_path(rom):
    h = hashlib.sha1(rom[:0x10000]).hexdigest()[:12]
    d = Path.home() / ".aw2dev" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"font2_{h}.pkl"


def load(rom_bytes=None):
    """{char: (width, [row bitmasks of the ink pixels (14 rows), bit x = pixel x], [row masks of any pixel])}."""
    rom = rom_bytes or cfg.aw2_rom().read_bytes()
    cp = _cache_path(rom)
    if cp.exists():
        return pickle.loads(cp.read_bytes())
    import struct
    out = {}
    for c in range(0x20, 0x7F):
        w = rom[WIDTHS - 0x08000000 + c]
        at = struct.unpack_from("<I", rom, GLYPHS - 0x08000000 + 4 * c)[0]
        if not (0x08000000 <= at < 0x0A000000) or w == 0:
            continue
        off = at - 0x08000000
        stride = (w + 1) // 2
        ink, anyp = [], []
        for r in range(14):
            mi = ma = 0
            for x in range(w):
                b = rom[off + stride * (3 + r) + x // 2]
                v = (b >> (4 * (x & 1))) & 15
                if v:
                    ma |= 1 << x
                if v == INK:
                    mi |= 1 << x
            ink.append(mi)
            anyp.append(ma)
        out[chr(c)] = (w, ink, anyp)
    cp.write_bytes(pickle.dumps(out))
    return out
