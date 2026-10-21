"""Map sources for the linter: tangoAW2's BH Campaign text maps, tangoAW2's Versus maps, AW2's own maps (ROM) and Dual Strike's (the .nds).
Everything is read at run time from the user's ROMs; nothing is stored. A map is a `MapData`: name, source, tile rows (AW2 tile ids),
and for BH maps the units and the source text rows."""
import struct, sys
from dataclasses import dataclass, field
from .. import cfg

FIVE = cfg.REPO / "tango-gamesupport-aw2" / "five"


@dataclass
class MapData:
    name: str
    source: str                 # bh | versus | aw2 | ds
    tiles: list                 # rows of tile ids
    units: list = field(default_factory=list)   # BH: dicts army/kind/x/y/hp/hold/name
    text: list = None           # BH / versus: the text rows
    meta: dict = field(default_factory=dict)

    @property
    def w(self): return len(self.tiles[0])
    @property
    def h(self): return len(self.tiles)


def _five():
    if str(FIVE) not in sys.path:
        sys.path.insert(0, str(FIVE))
    import map as mappy, tilecheck, bhmap
    return mappy, tilecheck, bhmap


def lz10(b):
    size = int.from_bytes(b[1:4], "little")
    out, p = bytearray(), 4
    while len(out) < size:
        flags = b[p]; p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                b1, b2 = b[p], b[p + 1]; p += 2
                disp = ((b1 & 15) << 8 | b2) + 1
                for _ in range((b1 >> 4) + 3):
                    out.append(out[-disp])
            else:
                out.append(b[p]); p += 1
    return bytes(out)


def rom_bytes():
    return cfg.aw2_rom().read_bytes()


def aw2_maps(rom=None):
    """AW2's own 0xC0 map-table entries (deduplicated by data pointer)."""
    mappy, tc, _ = _five()
    rom = rom or rom_bytes()
    out, seen = [], set()
    for i in range(tc.GAME_MAP_IDS):
        p = struct.unpack_from("<I", rom, tc.GAME_MAP_TABLE + 0x5C * i)[0]
        if not 0x08000000 <= p < 0x08000000 + len(rom) or p in seen or rom[p - 0x08000000] != 0x10:
            continue
        seen.add(p)
        raw = lz10(rom[p - 0x08000000:])
        w, h = raw[0], raw[1]
        if w == 0 or 2 + 2 * w * h > len(raw):
            continue
        t = struct.unpack_from(f"<{w * h}H", raw, 2)
        out.append(MapData(f"aw2_{i:02X}", "aw2", [list(t[y * w:(y + 1) * w]) for y in range(h)], meta={"id": i}))
    return out


def convert_tile(t):
    """ds_maps.rs convert_tile."""
    if t == 0x1A1:
        return 0x192
    if t in (0x146, 0x147):
        return 0x022
    if 0x1B9 <= t <= 0x1BD:
        return t - 0x1B9 + 0x1D9
    return t


def ds_maps(path=None):
    """Dual Strike's map headers (overlay 0, 0xA0 bytes per id, ids 0..0x10C; docs in ds_maps.rs)."""
    path = path or cfg.ds_rom()
    if not path.exists():
        return []
    nds = path.read_bytes()
    fat_off, _ = struct.unpack_from("<II", nds, 0x48)
    ovt_off, _ = struct.unpack_from("<II", nds, 0x50)
    ram, fid = struct.unpack_from("<I", nds, ovt_off + 4)[0], struct.unpack_from("<I", nds, ovt_off + 0x18)[0]
    off, end = struct.unpack_from("<II", nds, fat_off + 8 * fid)
    data = nds[off:end]
    OV0, HEADERS = 0x022AD560, 0x022DBD28
    out, seen = [], set()
    for i in range(0x10D):
        o = HEADERS - OV0 + 0xA0 * i
        h = data[o:o + 0xA0]
        tp = struct.unpack_from("<I", h, 0x44)[0]
        if not OV0 <= tp < OV0 + len(data) or tp in seen:
            continue
        seen.add(tp)
        try:
            raw = lz10(data[tp - OV0:])
        except Exception:
            continue
        w, hh = raw[0], raw[1]
        if w == 0 or 2 + 2 * w * hh > len(raw):
            continue
        t = struct.unpack_from(f"<{w * hh}H", raw, 2)
        rows = [[convert_tile(v) for v in t[y * w:(y + 1) * w]] for y in range(hh)]
        out.append(MapData(f"ds_{i:03X}", "ds", rows, meta={"id": i, "case": struct.unpack_from("<H", h, 0x26)[0]}))
    return out


def bh_maps(rom=None, files=None):
    """The BH Campaign's maps as bhmap.py builds them: tiles, units, text rows."""
    mappy, tc, bhmap = _five()
    rom = rom or rom_bytes()
    edge = mappy.sea_edges(rom)
    paths = files or sorted(p for p in (FIVE / "bh").glob("bh*.txt"))
    out = []
    for m in bhmap.parse([str(p) for p in paths]):
        rows = mappy.tiles(m, edge)
        out.append(MapData(m["name"], "bh", rows, units=m["units"], text=m["rows"], meta=m))
    return out


def versus_maps(rom=None):
    mappy, tc, _ = _five()
    rom = rom or rom_bytes()
    edge = mappy.sea_edges(rom)
    out = []
    for m in mappy.parse(str(FIVE / "maps.txt")):
        rows = mappy.tiles(m, edge)
        out.append(MapData(m["name"], "versus", rows, text=m["rows"], meta=m))
    return out
