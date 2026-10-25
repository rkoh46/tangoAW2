"""M2 Testudo (Act I): the legion holds the Dune Road ridges until Aurelia's causeway is open (day 9).

Design (docs/dev/map-design.md). The situation: Klaus has a small force on the southern ridges with the HQ in the south-west; Jess and Eagle come from
the north-east with factories, an airfield and waves from the north edge (x11..13) and the east edge (27,3..4). The player wins by not losing.
- Lanes: two roads come south from Jess's yard (the centre road at x11 then x9, the east road at x23 then x17), the north ridge has five gaps and the
  legion's ridge (y12) four; a farm track (y11) runs behind the line so the testudo can shift west or east. The east flank is the Dune hills (woods and
  rock along x25..27) with the east road under them, so the flank can be turned but not rushed.
- Where the fight happens: the farmland between the two ridges (y7..y11): villages every three cells, a neutral base (13,9) in the middle that either
  side may take, cities behind the legion's ridge that are its income.
- Properties: Jess's yard (HQ, two bases, an airport, a city) builds the waves; the villages north of the line are what the enemy takes to pay for
  more, so the legion's sorties to hold them matter; the cities and the base behind the legion's ridge pay for the defence.
- Threats and answers: Eagle's fighter and bomber -> the day-3 Anti-Air pair and Missiles behind the HQ; tanks and Md tanks down the roads -> the ridge
  gaps covered by artillery and mechs on the hills; the east flank under the Dune hills -> the tanks held back at the east road's town; recon -> own recon.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 28, 19

MAP = [
    # 0         1         2
    # 0123456789012345678901234567
    "^^.f..c..f.R....^^..c.f..^^^",   # 0
    "^.c...^^..cR..c...^^.RRRRR.^",   # 1
    "..f..f..^.fR.f...^B..B.f.2..",   # 2
    ".c..^^..c..RRRRRRRRRRRRR.R..",   # 3
    "...f..^f.c.R..f..C..f..R.A.f",   # 4
    ".f..c..f...R.c...f.c...R.f..",   # 5
    "^^^^..^^^..R.^^^...^^^.R.^^^",   # 6
    ".c..f.c.f..R..f.c..f.c.R..c.",   # 7
    "..f..^...RRR..c..f..^..R.f..",   # 8
    ".c..ff..cR.f.b...RRRRRRR.c.f",   # 9
    "^..c..f..R.f...c.R..c..f..f.",   # 10
    "RRRRRRRRRR.c..f..R.c..f..^^.",   # 11
    "^^..^^^..R..^^^..R.^^^...^f.",   # 12
    ".f.c..f.cR.f..c..R.f..c...fc",   # 13
    "..^..f...RRRRRRRRR..f..f..f.",   # 14
    "...RRRRRRR.C..f..c..C....f..",   # 15
    "^..1.f.B..C...c..RRRRRRRRRRR",   # 16
    "^^......c..f..C...f..c..f.^c",   # 17
    "^^^..f...^^..f...^^..^..f^^.",   # 18
]


def build():
    m = Canvas("es02", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M2 Testudo (the Dune Road ridges): survive to day 9; lose if HQ 1 (3,16) falls. Enemy HQ 2 (25,2) far NE (not an objective). North ridge y6 (gaps at x4..5, 9..12, 16..18, 22..24), "
        "the legion's ridge y12 (gaps x2..3, 7..11, 15..18, 22..24); the farm track y11 behind it; the Dune hills on the east flank (x25..27) over the east road y16. "
        "Neutral base (13,9) in the middle. Waves: north edge (11..13,0), east edge (27,3..4); the player's day-3 AA/Missiles at (3..5,17). "
        "Player: INF4 MECH2 TANK3 MDT1 ART2 RECON1; enemy: INF4 TANK3 MDT1 RECON1 ART1 FTR1 BMB1."))
    m.ascii(MAP)
    # --- the legion on its ridge
    m.units(1, INF, [(7, 12), (11, 12), (16, 12), (22, 12)])
    m.units(1, MECH, [(5, 13), (13, 13)])
    m.units(1, TANK, [(9, 13), (17, 13), (12, 14)])
    m.unit(1, MDT, 7, 15)
    m.units(1, ART, [(6, 14), (13, 15)])
    m.unit(1, RECON, 18, 14)
    # --- Jess's column and Eagle's wing in the yard
    m.units(2, INF, [(20, 2), (16, 2), (24, 3), (19, 5)])
    m.units(2, TANK, [(12, 3), (14, 3), (22, 3)])
    m.unit(2, MDT, 11, 2)
    m.unit(2, RECON, 10, 4)
    m.unit(2, ART, 16, 1)
    m.unit(2, FTR, 23, 2)
    m.unit(2, BMB, 22, 1)
    m.note("hq", 3, 16, "the legion's HQ: lose it and the mission is lost")
    m.note("enemy_hq", 25, 2, "Green Earth HQ, far NE; reachable by land, not an objective")
    m.note("mid_base", 13, 9, "neutral base between the ridges: the contested middle")
    m.note("dune_hills", 26, 13, "the Dune hills over the east road")
    m.note("waves", 12, 0, "enemy waves at (11..13,0) and (27,3..4)")
    return m
