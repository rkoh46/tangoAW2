"""M5 Dust and Wheels: Cassius's cavalry race east across the Comet Road. A river runs north-south with three bridges; each carries a signal-post city on the far bank."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es05", 26, 14)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M5 Dust and Wheels: own all three signal posts (post1..3) by the end of day 9; the bridges are blown on day 10. "
        "Start forces: player RECON3 TANK3 MDT2 APC2 MECH3 AA2 (15 units), 1 base, funds 3000; "
        "Yellow Comet INF4 MECH2 TANK2 RECON1 ART2 ROCK1 BCO2 TCO1 AA1 (16 units), 2 bases + 1 airport. "
        "Threat -> answer: Copters (BCO/TCO) -> the player's 2 AA and Tanks/Recon; ART + ROCK shelling the bridges -> no player ART at all, the answer is speed "
        "(Recons and Tanks cross first and reach the guns); enemy AA -> Tanks/Md Tanks (AA is weak against vehicles' mass, Recon avoids it)."))
    # the river, edge to edge, with three bridges
    m.river([(12, 0), (12, 13)])
    # banks: woods on the west bank give cover to the approach, a wood belt guards each post
    m.rect("f", 9, 3, 10, 4).rect("f", 9, 8, 10, 9)
    m.rect("f", 14, 3, 15, 3).rect("f", 14, 8, 15, 8).rect("f", 16, 10, 16, 11)
    # the three bridges
    for y in (2, 6, 11):
        m.bridge(12, y)
    # property cells
    m.put("1", 2, 6).put("B", 3, 4)
    m.put("c", 15, 2).put("c", 15, 6).put("c", 15, 11)
    m.put("2", 23, 6).put("B", 21, 5).put("B", 21, 7).put("A", 22, 8)
    m.put("C", 20, 2).put("C", 20, 11)
    # roads: HQ -> bridges, bridges -> posts, the Comet Road on to the enemy HQ
    m.road([(2, 6), (11, 6)])
    m.road([(3, 6), (3, 2), (11, 2)])
    m.road([(3, 6), (3, 11), (11, 11)])
    m.road([(13, 2), (19, 2)]).road([(13, 6), (22, 6)]).road([(13, 11), (19, 11)])
    m.road([(19, 2), (19, 6)]).road([(19, 6), (19, 11)])
    m.road([(22, 6), (22, 7)])
    # hills the enemy guns sit behind
    m.rect("^", 17, 3, 17, 4).rect("^", 17, 9, 17, 10)
    # player: the column at its HQ
    m.units(1, RECON, [(4, 5), (4, 6), (4, 7)])
    m.units(1, TANK, [(5, 5), (5, 6), (5, 7)])
    m.units(1, MDT, [(6, 5), (6, 7)])
    m.units(1, APC, [(3, 7), (3, 5)])
    m.units(1, MECH, [(2, 5), (2, 7), (3, 8)])
    m.units(1, AA, [(6, 6), (4, 8)])
    # Yellow Comet: the border guard
    m.units(2, INF, [(15, 3), (15, 7), (15, 10), (16, 6)], hold=True)
    m.units(2, MECH, [(16, 2), (16, 11)], hold=True)
    m.units(2, TANK, [(17, 5)])
    m.unit(2, RECON, 18, 6)
    m.units(2, ART, [(18, 4)], hold=True)
    m.unit(2, ROCK, 19, 6, hold=True)
    m.units(2, BCO, [(22, 11)])
    m.unit(2, TCO, 22, 9)
    m.unit(2, AA, 22, 7, hold=True)
    m.note("hq1", 2, 6, "player HQ (west)").note("hq2", 23, 6, "Yellow Comet HQ (far east)")
    m.note("bridge1", 12, 2, "north bridge").note("bridge2", 12, 6, "middle bridge").note("bridge3", 12, 11, "south bridge")
    m.note("post1", 15, 2, "signal post beyond the north bridge").note("post2", 15, 6, "signal post beyond the middle bridge").note("post3", 15, 11, "signal post beyond the south bridge")
    m.note("base1", 3, 4, "player's only base")
    m.note("river_x", 12, 0, "the river is the column x=12, y 0..13")
    return m
