"""The Gauntlet mode's maps added after Cinder Sea and Iron Crown, as the generic live tests (`tests/test_gauntlet_lines.py`, `-k gauntlet_lines`) and the cpu tests see them: per map the
mission (its index in crate::gauntlet_mode::def, its identity: the selector's position is another thing, crate::gauntlet_mode::order), the player's army, and per line (in the order it comes)
the CO, its army slot, its HQ, the size of its wave and its war chest (crate::gauntlet_mode). Add a map here with its Rust."""

from dataclasses import dataclass, field

from . import gauntlet as ga


@dataclass
class Line:
    name: str
    co: int
    army: int
    hq: tuple
    wave: int = 0                 # the number of units of its wave (0: on the field from the start)
    chest: tuple = (0, 0)         # (base, rate) of its war chest


@dataclass
class MapInfo:
    mission: int
    key: str
    title: str
    player: int                    # the player's army slot (1, or 5 on a five-army map)
    player_hq: tuple
    lines: list = field(default_factory=list)
    skin_enemies: bool = False     # an enemy line wears Silver Nova (the skin is no choice for the player)
    sealed: bool = False           # the first line starts in a chamber sealed by pipe seams: its units cannot leave it until a seam is broken

    @property
    def five(self):
        return self.player == 5

    @property
    def armies(self):
        return tuple(l.army for l in self.lines)


CO = {"koal": 73, "lash": 12}

MAPS = {}


def add(info):
    MAPS[info.mission] = info
    return info


add(MapInfo(2, "gauntlet_03", "Dustwind Basin", 1, (3, 16), [
    Line("koal", 73, 2, (25, 10)),
    Line("lash", 12, 3, (6, 3), wave=18, chest=(15000, 1000)),
]))
add(MapInfo(3, "gauntlet_04", "Brass Canal", 1, (3, 18), [
    Line("sasha", 78, 2, (5, 4)),
    Line("javier", 77, 3, (25, 17), wave=20, chest=(15000, 1000)),
]))
add(MapInfo(4, "gauntlet_05", "Granite Spine", 1, (3, 18), [
    Line("jake", 79, 2, (28, 12)),
    Line("grimm", 76, 3, (6, 4), wave=17, chest=(15000, 1000)),
    Line("von_bolt", 75, 4, (27, 4), wave=17, chest=(20000, 1500)),
]))
add(MapInfo(5, "gauntlet_06", "Harvest Run", 5, (4, 20), [
    Line("andy", 0, 1, (11, 8)),
    Line("max", 2, 2, (29, 5), wave=20, chest=(15000, 1000)),
    Line("sami", 1, 3, (30, 19), wave=22, chest=(20000, 1500)),
    Line("nell", 0, 4, (6, 4), wave=20, chest=(25000, 2000)),
]))
add(MapInfo(6, "gauntlet_07", "Chrome Meridian", 5, (4, 22), [
    Line("flak", 11, 1, (11, 14)),
    Line("caulder", 88, 2, (30, 5), wave=19, chest=(15000, 1000)),
    Line("lili", 87, 3, (30, 12), wave=20, chest=(20000, 1500)),
    Line("tabitha", 86, 4, (30, 20), wave=20, chest=(25000, 2000)),
], skin_enemies=True))

add(MapInfo(7, "gauntlet_08", "Tidewater Atoll", 1, (3, 14), [
    Line("eagle", 8, 2, (25, 4)),
    Line("adder", 13, 3, (25, 15), wave=18, chest=(15000, 1000)),
]))
add(MapInfo(8, "gauntlet_09", "Silverpine Ford", 1, (3, 18), [
    Line("hachi", 15, 2, (26, 10)),
    Line("sonja", 7, 3, (6, 4), wave=19, chest=(15000, 1000)),
]))
add(MapInfo(9, "gauntlet_10", "Neon Row", 1, (4, 16), [
    Line("colin", 16, 2, (22, 9)),
    Line("kindle", 74, 3, (4, 3), wave=19, chest=(15000, 1000)),
    Line("jugger", 72, 4, (28, 3), wave=20, chest=(20000, 1500)),
]))
add(MapInfo(10, "gauntlet_11", "Blue Bastion", 5, (3, 22), [
    Line("olaf", 3, 1, (16, 21)),
    Line("grit", 5, 2, (20, 15), wave=17, chest=(15000, 1000)),
    Line("colin", 16, 3, (32, 15), wave=19, chest=(20000, 1500)),
    Line("sasha", 78, 4, (26, 13), wave=20, chest=(25000, 2000)),
]))
add(MapInfo(11, "gauntlet_12", "Last Eclipse", 5, (3, 13), [
    Line("sturm", 10, 1, (19, 13)),
    Line("von_bolt", 75, 2, (29, 6), wave=19, chest=(15000, 1000)),
    Line("aria", 93, 3, (29, 20), wave=20, chest=(20000, 1500)),
    Line("asuka", 92, 4, (39, 13), wave=23, chest=(25000, 2000)),
], sealed=True))


def player_army(mission):
    """The player's army slot on the Gauntlet map of this mission: 1 (Cinder Sea, the maps of two and three armies), 5 on a five-army map (Iron Crown and the maps added here)."""
    return MAPS[mission].player if mission in MAPS else 5 if mission == 1 else 1


def enemy_armies(mission):
    """The armies of the map's lines in the order they come (Cinder Sea's three, Iron Crown's four)."""
    return MAPS[mission].armies if mission in MAPS else (1, 2, 3, 4) if mission == 1 else (2, 3, 4)
