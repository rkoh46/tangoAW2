"""Tile id -> terrain character. Classes come from the ROM's terrain-class table (0x080C1BC4, low 5 bits) for tiles below 0x1B4; property tiles
and the Black Hole inventions are ranges (five/map.py PROPS / INVENTIONS)."""
import functools
from .load import _five

CLASS_TABLE = 0x0C1BC4
# class -> character
CLASS_CH = {1: ".", 2: "-", 3: "^", 4: "f", 5: "R", 7: "~", 12: "=", 13: ",", 15: "I", 16: "Z", 19: "r", 17: "M"}
PROP_KIND = {}


def _props():
    if not PROP_KIND:
        mappy, _, _ = _five()
        for ch, tiles in mappy.PROPS.items():
            for i, t in enumerate(tiles):
                PROP_KIND[t] = (ch, i)         # i: 0 neutral, 1..4 armies, 5 Black Hole
    return PROP_KIND


class Terrain:
    def __init__(self, rom):
        self.rom = rom
        _props()

    def cls(self, t):
        return self.rom[CLASS_TABLE + t] & 0x1F if t < 0x1B4 else 0

    def ch(self, t):
        """'.' plain, 'f' wood, '^' mountain, 'R' road, '-' river, '=' bridge, '~' sea, ',' shoal, 'r' reef, 'I' pipe, 'Z' seam, 'M' silo,
        'H B C A P T' properties (HQ base city airport port tower), '#' structure/underlay, '?' tile no map uses."""
        if t in PROP_KIND:
            return PROP_KIND[t][0]
        if t >= 0x1B4:
            return "#" if t <= 0x1DD else "?"
        return CLASS_CH.get(self.cls(t), "#" if 0x180 <= t < 0x1B4 else "?")

    def owner(self, t):
        return PROP_KIND[t][1] if t in PROP_KIND else None


@functools.lru_cache(maxsize=1)
def terrain():
    from .load import rom_bytes
    return Terrain(rom_bytes())
