"""M1 Landfall (Act I): Klaus's legion lands on Cape Astra.

Design (docs/dev/map-design.md). The situation: the legion sits on the fleet's sandbar in the south with its Landers, no funds and no factory; Jess's
coast wardens hold the cape, the fort and its HQ on the northern ridge. The player must cross the strait, take a beachhead and climb to the fort.
- Lanes: three beaches (the west cove, the central strand below Astra town, the east cove at the river mouth), each with a road inland; on the cape
  the west road, the town road and the river road climb to the fort, with lateral farm tracks between them (2 to 4 roads cross the middle).
- Where the fight happens: Astra town on the central strand (the contested middle: cities and a neutral base right above the beach), then the
  farmland villages between the beaches and the ridge, then the fort's three approaches.
- Properties: the beach towns give the player income and two forward bases (a neutral base above the west cove and one in Astra town) so the
  landing turns into an army; the villages every three cells are cover and money for whoever holds them; the fort's cities and HQ are Jess's. Ports on
  the sandbar build the next Landers.
- Threats and answers: Jess's two cruisers in the strait -> the player's cruiser, and Landers that cross at the far beaches; her tanks on the strand ->
  the day-3 Anti-Air and Tanks, the artillery from the beach, mechs in the town; her artillery in the fort -> the recon on the river road and the
  approach through the woods of the east farms; the river (bridged twice, open sea at its mouth) never walls a beach off.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 30, 27

MAP = [
    # 0         1         2
    # 012345678901234567890123456789
    "^^^.f..^^^^..f...^^^.f.f-..^^^",   # 0
    "^^.c.ff..^^..C.C..^^.c.f-.c.^^",   # 1
    "^..f..^...^.RRRRR.^..f..-...f^",   # 2
    "..c..f..C.RR..^..RRC....-.c...",   # 3
    ".f..RRRRRRR..C2C..RRRRRR=RR..f",   # 4
    "...cR..f.^^..f.f..^^.f..-..R.c",   # 5
    "f...R.c....c.RRR.c...c.--.fR..",   # 6
    "^.f.R.f...f..fR..f..f.f-..c.R.",   # 7
    "..RRRRRRc..RRRRRRRRc..f-.f..R.",   # 8
    ".c..f..R..fR..f...R..c.-..RRRc",   # 9
    "..f^f..R.c.R.^.fc.R.f..-.f.R.f",   # 10
    ".f.c..fR...R.f..c.RRRRR=RRRR.f",   # 11
    "..^.b.RR.c.RRRbRRRR.f.c-..c.R.",   # 12
    ".,.....R..f.c..R..c.f..-.f..R.",   # 13
    "~,,,.c.R..,,.c.R.c.,,f.-.,,,R,",   # 14
    "~~~~,,.R.,~~,,.R.,,~~..-.~~~,~",   # 15
    "~~~~~~,,,~~~~~,,,~~~~~~~~~~~~~",   # 16
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",   # 17
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",   # 18
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",   # 19
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",   # 20
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",   # 21
    "~~~~~~~~,,,,,~~,,,,,,~~~~~~~~~",   # 22
    "~~~~~~,,.P...,,..C.P.,~~~~~~~~",   # 23
    "~~~~~,..f...f.....f...,,~~~~~~",   # 24
    "~~~~,..C..f..1..c..f..^.,~~~~~",   # 25
    "~~~~,..................c....,~",   # 26
]


def build():
    m = Canvas("es01", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M1 Landfall (Cape Astra): land from the fleet's sandbar (south) and take Fort Astra's HQ 2 (14,4) on the ridge. Beaches: west cove x1..6, Astra strand x9..19 (the town), "
        "east cove x24..29 at the Astra river's mouth. Forward neutral bases: (4,12) above the west cove and (14,12) in Astra town. The Astra river runs from the north edge to the sea, "
        "bridged on the fort road (24,4) and the coast road (23,11). Player: Klaus, LAN4 CR1 INF4 MECH2 APC2 RECON1 ART1, day-3 AA+TANK2. Enemy (Jess): INF4 MECH2 TANK3 ART2 RECON1 CR2."))
    m.ascii(MAP)
    m.tidy()
    # --- Klaus's legion on the sandbar: Landers along its north shore, the rest ashore in a loose order
    m.units(1, LAN, [(8, 21), (12, 21), (17, 21), (22, 21)])
    m.unit(1, CR, 15, 19)
    m.units(1, INF, [(8, 25), (11, 23), (16, 24), (20, 24)])
    m.units(1, MECH, [(10, 25), (19, 25)])
    m.units(1, APC, [(13, 24), (15, 23)])
    m.unit(1, RECON, 6, 25)
    m.unit(1, ART, 14, 26)
    # --- Jess's wardens: the fort's garrison, the strand picket, the farms, cruisers in the strait
    m.units(2, INF, [(13, 3), (16, 3), (9, 9), (21, 9)], hold=True)
    m.units(2, MECH, [(11, 5), (17, 5)], hold=True)
    m.units(2, ART, [(14, 6), (16, 5)], hold=True)
    m.units(2, TANK, [(6, 11), (15, 10), (25, 9)])
    m.unit(2, RECON, 27, 7)
    m.unit(2, CR, 4, 19).unit(2, CR, 26, 19)
    m.note("hq", 13, 25, "the legion's HQ on the fleet's sandbar")
    m.note("enemy_hq", 14, 4, "Fort Astra's HQ on the ridge (objective)")
    m.note("cove_w", 3, 15, "west cove"); m.note("strand", 14, 15, "Astra strand below the town"); m.note("cove_e", 26, 15, "east cove at the river mouth")
    m.note("town", 14, 13, "Astra town: the contested middle, a neutral base (14,12)")
    m.note("reinforce", 15, 26, "day-3 AA and tanks land at (12,26) (15,26) (18,26)")
    return m
