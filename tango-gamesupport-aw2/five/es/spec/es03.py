"""M3 The Wall (Act I): Aurelia's siege of Javier's walled town of Muro Alto, in the rain.

Design (docs/dev/map-design.md). The situation: Javier holds a walled town on the coast, an inner keep with the HQ, three Com Towers and a factory; Drake's
battleship lies off the coast road. Aurelia's siege train comes from the south with an airport, a base and a few cities.
- Lanes: the walled town has four gates (north under the battleship, west over the Muro river, east from the vineyards, south from the legion's farms)
  and the keep one (south). Outside the walls a west road and a south road reach three of them; the vineyards on the east and the river farms on the west
  are the flanks. Foot soldiers climb the rock anywhere.
- Where the fight happens: the south farms and the river farms below the wall (villages every few cells, the silo by the west road), then the town's
  streets between the outer wall and the keep, then the keep gate.
- Properties: the town is full of neutral houses (cover, and income to whoever holds the streets), the three towers are Javier's defence, his factory
  feeds the garrison; the farms pay the siege; the silo (3,13) is a one-shot answer to a crowd at the west gate.
- Threats and answers: the battleship -> the day-2 bomber from the airport, rockets on the coast road; the towers -> artillery and rockets take them from
  outside the wall; guns behind the wall -> recons on the roads, mechs over the rock; tanks at the gates -> tanks and artillery; the keep's AA -> keep the
  bomber off it.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 32, 24

# (drawn in four groups of eight columns: 0-7 | 8-15 | 16-23 | 24-31)
MAP = [r.replace("|", "") for r in [
    "~~~~~~~~|~~~~~~~~|~~~~~~~~|~~~~~~~~",   # 0
    "~~~~~~~~|~~~~~~~~|~~~~~~~~|~~~~~~~~",   # 1
    ",,,,.-.,|,~~,,,,,|,,,,,,,,|~~~,,,,,",   # 2
    "RRRRR=RR|RRRR.c..|...c.RRR|RRRRRRRR",   # 3
    ".c.f.-.f|..cRRRRR|RRRRRR.f|..c..f..",   # 4
    "..c..-..|f.^^...c|R.c...^^|..c.f.c.",   # 5
    "..f..-..|.^^^^...|R...^^^^|^..f..c.",   # 6
    ".c...-..|^^..^^^^|R^^^^...|^^.c...f",   # 7
    "..c.f--^|.cRRRRRR|RRRRRRR.|^..c.f..",   # 8
    ".^....-^|.cR..^^^|^^^^..Rc|^^...c..",   # 9
    "..c...-^|.TR.^.c.|T.c.^.RB|.^..c..f",   # 10
    "f.....-^|..R.^...|....^.R.|.^.f...c",   # 11
    "RRRRRR=R|RRR.^c..|2.c.^.RR|RRRRRRRR",   # 12
    "...MR.-^|.cR.^..c|....^cR.|.^.c.f..",   # 13
    ".f..R.-^|..R.^c..|..c.^TR.|.^...c.f",   # 14
    "..c.R.-.|^.R..^^^|R^^^..R.|^.f.c..c",   # 15
    ".f..R--.|^.RRRRRR|RRRRRRR.|^..c.^^.",   # 16
    "..c.R-.c|^^^^^R^^|^^..^^^^|^.f..c..",   # 17
    "^...R-..|.c...R.c|..^^.c.f|..c...^^",   # 18
    ".f.cR-..|C.f.cR..|f..c.f..|c..f.^^.",   # 19
    "..c.R-.f|.f...Rf.|.c....c.|.f.c..^^",   # 20
    "RRRRR=RR|RRRRRRRR|RRRRRRR.|..c...f.",   # 21
    "^.c.1-..|..A...fB|....c..f|..c..c.^",   # 22
    "^^..c-..|..f.....|.f...^^.|..f...^^",   # 23
]]


def build():
    m = Canvas("es03", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M3 The Wall (Muro Alto): take HQ 2 (16,12) inside the keep. Outer wall gates: north (16,6..7), west (7,12), east (25,12), south (13,17); the keep's gate (16,15). "
        "Sea y0..1 with the beach y2; Drake's battleship (hold) off the coast road y3..4. The Muro river from the sea (5,2) to the south edge, bridged at (5,3), (6,12), (5,21). "
        "Neutral silo (3,13) by the west road. Player funds 2000: ART3 ROCK2 RECON2 INF4 MECH2 TANK2 AA1, the day-2 bomber at (11,22) beside the airport (10,22). "
        "Enemy: INF4 MECH2 TANK3 AA1 ART2 ROCK1 (hold) + BS1, towers (9,10) (16,10) (21,14), factory (23,10)."))
    m.ascii(MAP)
    m.tidy()
    # Aurelia's siege train in the south farms
    m.spread(1, {ART: 3, ROCK: 2}, (1, 22, 28, 23), seed=1, gap=2)
    m.spread(1, {RECON: 2, TANK: 2}, (3, 19, 28, 21), seed=2, gap=2)
    m.spread(1, {INF: 4, MECH: 2, AA: 1}, (2, 18, 29, 22), seed=3, gap=1)
    # Javier's garrison
    m.units(2, INF, [(16, 7), (8, 12), (24, 12), (16, 14)], hold=True)
    m.units(2, MECH, [(9, 8), (23, 15)], hold=True)
    m.units(2, TANK, [(10, 14), (22, 10), (13, 16)])
    m.unit(2, AA, 18, 8)
    m.units(2, ART, [(14, 11), (17, 13)], hold=True)
    m.unit(2, ROCK, 12, 8, hold=True)
    m.unit(2, BS, 16, 0, hold=True)
    m.note("hq", 4, 22, "player HQ"); m.note("enemy_hq", 16, 12, "objective: Javier's HQ in the keep")
    m.note("gate_n", 16, 6, "north gate (under the battleship)"); m.note("gate_w", 7, 12, "west gate over the Muro bridge (6,12)")
    m.note("gate_e", 25, 12, "east gate from the vineyards"); m.note("gate_s", 13, 17, "south gate from the legion's farms")
    m.note("keep_gate", 16, 15, "the keep's only gate")
    m.note("silo", 3, 13, "neutral missile silo by the west road")
    m.note("airport", 10, 22, "player airport"); m.note("bomber_cell", 11, 22, "day-2 Bomber cell")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
