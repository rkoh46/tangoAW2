"""M2 Testudo (Act I): the legion holds the Dune Road ridge until Aurelia's causeway is finished. Three ridges, gaps with roads, the HQ behind the last."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es02", 20, 14)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M2 Testudo: survive to day 9; lose if HQ 1 (4,12) falls. Enemy HQ 2 (17,1) is far NE. Three ridges (y 4, 7, 10) with road gaps: "
        "ridge1 x2 (TRAP: leads into a walled pocket x0..5, y5..6 with no way on south), x10, x17; ridge2 x9, x16; ridge3 x5, x12. "
        "Player start: INF4 MECH2 TANK3 MDT1 ART2 RECON1 (63000 value); enemy: INF4 TANK4 MDT2 RECON2 ART2 FTR2 BMB1 (146000, air included). "
        "Threat->answer: Eagle's FTR/BMB -> reinforcement AA x2 + MIS x1 (day 3), ART/MECH on ridge cover; tanks/MDT -> ridge gaps (roads) covered by ART behind "
        "and mountain infantry; enemy RECON -> own RECON; enemy ART -> RECON spotting + tanks sortie."))
    # three ridges across the map
    for y, gaps in ((4, (2, 10, 17)), (7, (9, 16)), (10, (5, 12))):
        m.rect("^", 0, y, 19, y)
        for g in gaps:
            m.put(".", g, y)
    # the ridge shoulders: a second row of rock on the ridge the legion holds, so it is a real wall
    m.rect("^", 0, 8, 4, 8).rect("^", 17, 8, 19, 8)
    # trap pocket: walled off from the corridor, enemy vehicles that take the west gap are stuck
    m.rect("^", 6, 5, 6, 6)
    # cover: woods behind the gaps (defenders) and the pocket's inside
    m.rect("f", 8, 8, 8, 9).rect("f", 10, 8, 10, 9).rect("f", 15, 8, 15, 8).rect("f", 17, 9, 18, 9)
    m.rect("f", 4, 11, 4, 11).rect("f", 6, 11, 6, 11).rect("f", 11, 11, 11, 11).rect("f", 13, 11, 13, 11)
    m.rect("f", 3, 5, 4, 6)
    # roads
    m.road([(19, 3), (2, 3), (2, 6)])
    m.road([(17, 2), (17, 6), (16, 6), (16, 9), (12, 9), (12, 12)])
    m.road([(10, 3), (10, 6), (9, 6), (9, 9), (5, 9), (5, 12)])
    m.road([(12, 12), (3, 12)])
    # enemy: HQ, two bases, the airport
    m.put("2", 17, 1).put("B", 14, 2).put("B", 19, 2).put("A", 12, 1)
    # player: HQ, two causeway cities, a base
    m.put("1", 4, 12).put("B", 7, 12).put("C", 9, 12).put("C", 14, 12)
    # the legion
    m.units(1, INF, [(8, 7), (10, 7), (15, 7), (17, 7)])
    m.units(1, MECH, [(4, 10), (13, 10)])
    m.units(1, TANK, [(9, 9), (16, 9), (12, 9)])
    m.unit(1, MDT, 5, 9)
    m.units(1, ART, [(6, 11), (11, 11)])
    m.unit(1, RECON, 13, 11)
    # Eagle's wing and Jess's column
    m.units(2, INF, [(12, 2), (13, 3), (16, 3), (18, 3)])
    m.units(2, TANK, [(9, 3), (11, 3), (15, 3)])
    m.units(2, MDT, [(10, 2)])
    m.units(2, RECON, [(8, 3)])
    m.units(2, ART, [(14, 1)])
    m.units(2, FTR, [(11, 1)])
    m.unit(2, BMB, 11, 0)
    # named places
    m.note("hq", 4, 12, "the legion's HQ: lose it and the mission is lost")
    m.note("enemy_hq", 17, 1, "Green Earth HQ, far NE; reachable by land, not an objective")
    m.note("trap_gap", 2, 4, "ridge1 west gap: leads into the pocket x0..5 y5..6, closed by rock at x6 and ridge2")
    m.note("choke1a", 10, 4, "ridge1 centre gap"); m.note("choke1b", 17, 4, "ridge1 east gap")
    m.note("choke2a", 9, 7, "ridge2 west-centre gap"); m.note("choke2b", 16, 7, "ridge2 east gap")
    m.note("choke3a", 5, 10, "ridge3 west gap (road to HQ)"); m.note("choke3b", 12, 10, "ridge3 east gap")
    for k, (x, y) in enumerate([(3, 13), (5, 13), (2, 12)], 1):
        m.note(f"reinf{k}", x, y, "day 3: player AA/AA/MIS (free ground behind the HQ)")
    for k, (x, y) in enumerate([(4, 0), (6, 0), (8, 0), (19, 8), (19, 9), (19, 5)], 1):
        m.note(f"wave{k}", x, y, "enemy wave cell (day 3, 5, 7)")
    return m
