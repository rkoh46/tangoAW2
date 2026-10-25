"""M10 The Quiet Pass (Act III, snow, fog): climb the Comet Pass and take Kanbei's summit HQ.

Design (docs/dev/map-design.md). The situation: the legion lands on the south plain below a massif; Kanbei holds the summit plateau (HQ, factory,
cities) at the top of three pass roads, Sami watches from a pocket of the east ridge. Snow falls; fog hides the passes.
- Lanes: the Quiet river crosses the south of the map (three bridges, one on each pass road); the west, centre and east pass roads climb the massif
  (x7, x16, x25) and meet on the summit road (y3); a goat track (x1..3, woods and meadow) lets foot soldiers climb the far west unseen.
- Where the fight happens: the bridges and the north bank's foothill hamlets, then the alpine hamlets on the three passes (meadows at y6, y9, y12),
  with the contested middle at the centre pass's foot: a neutral base (15,13) and hamlets round it.
- Properties: villages three cells apart on the south plain (the legion's income), hamlets beside every pass road (cover where the road is the only way
  for vehicles), the summit's town; Sami's pocket has its HQ and a city.
- Threats and answers: ambushes at the pass hamlets in the fog -> recons and copters ahead, infantry in the hamlets; tanks at the pass tops -> mechs on the
  goat track and over the rock, Md tanks and artillery on the road below; the guns on the summit -> recon sight, the B Copter, infantry over the rock;
  Sami's copter -> the AA.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 34, 26

MAP = [r.replace("|", "") for r in [
    "^^^^.f..|^^^.c...|...c.^^^|..^^^^^^|^^",   # 0
    "^^.c..f.|^^......|.c....^^|.f.^^..^|^^",   # 1
    "^..f..^^|^.c.B...|2...C..^|^^.^...^|.^",   # 2
    ".c..^^^R|RRRRRRRR|RRRRRRRR|RRRRRC.3|.^",   # 3
    "..f.^^.R|^^.f..c.|R.f.^^.C|.R^^^.f^|^^",   # 4
    ".f^^^^^R|^^^^^^.^|R^^^^^^^|^R^^^^^^|^^",   # 5
    ".f.^^^cR|c^^^^^.f|Rc^^^^.^|cR^^c^^^|^^",   # 6
    ".f^^^^^R|^^^^^.f.|R.^^^^^^|^R^^^^.^|^^",   # 7
    "..^^^^.R|.^^^^^..|R^^^^^^^|^R^^^^^^|.^",   # 8
    ".f^^^c.R|c^^^^.c.|R.c^^^^c|.R.c^^^^|^^",   # 9
    "..^^^^^R|^^^^^^.^|R^^^^^^^|^R^^^^^^|^^",   # 10
    ".f.^^^^R|^^^^f..^|R^^f^^^^|^R^^^^.^|^^",   # 11
    "..^^c..R|.c^^^...|R..^^^c.|.R.c^^^^|^.",   # 12
    ".f.^^^.R|...^^..b|R.c..^^.|.R..^^^.|..",   # 13
    "..f..c.R|..c...f.|R...c...|.R.c...f|..",   # 14
    "-------=|--......|R..f..c.|.R...f..|..",   # 15
    "..c..f.R|.-------|=----...|.R..c...|..",   # 16
    ".f...c.R|..c..f..|R...----|-=------|--",   # 17
    "..f.c..R|.f..c...|R.c...f.|.R.f..c.|..",   # 18
    ".c.....R|RRRRRRRR|RRRRRRRR|RR..f...|c.",   # 19
    "..f...c.|..f..c..|R..f..c.|...c..f.|..",   # 20
    ".c..f...|.c....f.|R.c.....|.f...c..|f.",   # 21
    "..^..f..|....cB..|R...f..c|..f.....|.c",   # 22
    ".f...c..|..c.....|1..f..c.|..c..^..|..",   # 23
    "..^..f..|.f...C..|..C..f..|.f.^^...|..",   # 24
    ".^^..f..|c.....f.|.c....^^|..f.^^.f|^.",   # 25
]]


def build():
    m = Canvas("es10", W, H)
    m.header(armies=3, colours=(BM, YC, OS), team=[1, 2, 2], objective=[1], comment=(
        "M10 The Quiet Pass (FOG, snow): take Kanbei's summit HQ 2 (16,2). Pass roads x7, x16, x25 from the summit road y3 to the south plain; the goat track x1..3 (foot only). "
        "The Quiet river (0,15)..(33,17) bridged at (7,15), (16,16), (25,17). Sami's HQ 3 (31,3) in the east ridge pocket. Neutral base (15,13) at the centre pass's foot. "
        "Player: INF4 MECH3 TANK2 MDT2 RECON3 ART2 BCO1 TCO1 AA1 APC1, base (13,22), funds 4000. Kanbei: INF4 MECH2 TANK3 MDT2 ART2 ROCK1 AA1; Sami: INF2 RECON2 TANK2 BCO1."))
    m.ascii(MAP)
    # --- the legion on the south plain
    m.unit(1, APC, 16, 21)
    m.spread(1, {INF: 4, MECH: 3}, (3, 18, 28, 24), seed=1, gap=1)
    m.spread(1, {TANK: 2, MDT: 2, ART: 2, AA: 1}, (6, 19, 26, 25), seed=2, gap=1)
    m.spread(1, {RECON: 3}, (4, 18, 30, 21), seed=3, gap=2)
    m.spread(1, {BCO: 1, TCO: 1}, (10, 22, 22, 25), seed=4, gap=1)
    # --- Kanbei on the summit (the guns hold), his patrols on the passes
    HOLD = dict(hold=True)
    m.units(2, MECH, [(15, 3), (17, 3)], **HOLD); m.units(2, ART, [(14, 2), (18, 2)], **HOLD); m.unit(2, ROCK, 16, 4, **HOLD)
    m.unit(2, AA, 19, 4)
    m.units(2, INF, [(8, 4), (6, 6)]); m.unit(2, TANK, 11, 3)
    m.units(2, INF, [(23, 4), (24, 6)]); m.unit(2, MDT, 22, 3)
    m.unit(2, TANK, 16, 7); m.unit(2, TANK, 16, 10); m.unit(2, MDT, 20, 3)
    # --- Sami's pocket
    m.units(3, INF, [(30, 2), (32, 4)], **HOLD)
    m.units(3, TANK, [(30, 3), (28, 3)]); m.unit(3, RECON, 29, 1); m.unit(3, RECON, 26, 3); m.unit(3, BCO, 30, 1)
    m.note("hq1", 16, 23, "player HQ (south)"); m.note("base1", 13, 22, "player base")
    m.note("hq2", 16, 2, "Kanbei's summit HQ: the objective"); m.note("hq3", 31, 3, "Sami's HQ in the east-ridge pocket")
    m.note("bridges", 7, 15, "the Quiet river's bridges (7,15) (16,16) (25,17)")
    m.note("pass_w", 7, 9, "west pass road"); m.note("pass_c", 16, 9, "centre pass road"); m.note("pass_e", 25, 9, "east pass road")
    m.note("goat_track", 1, 9, "goat track (foot only), x1..3")
    m.note("mid_base", 15, 13, "neutral base at the centre pass's foot")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
