"""M8 Hammer and Anvil: Ironhold, a stone fort of mountains on a plain behind a canal. One causeway crosses the canal; flank roads run round the fort to its rear gate."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es08", 22, 16)
    m.header(armies=3, colours=(BH, OS, OS), team=[1, 2, 2], objective=[1], comment=(
        "M8 Hammer and Anvil (tag mission, Klaus + Cassius): rout both Orange Star armies or capture Max's HQ '2' (16, 7). "
        "Start forces: player INF4 MECH3 TANK4 MDT2 RECON2 ART2 AA1 (18 units), 1 base (3, 5), funds 4000; "
        "Max (army 2, in the fort) INF3 (hold) MECH2 (hold) MDT3 TANK2 ART2 AA1 (13), Jake (army 3, south-east plain) INF2 TANK3 RECON2 ROCK1 BCO1 (9). "
        "Threat -> answer: Max's ARTs behind the walls shell the causeway -> Recon spots, the player's two ARTs and Tanks rush the gate, or Cassius's flank takes the rear; "
        "Jake's Rocket / Copter -> the player's AA and Tanks; Md Tanks at the gate -> player Md Tanks + ART + the Tag Power (day 3 lesson). "
        "Forced routes: the canal (x=8) is crossed only by the causeway (8, 7..8); the fort walls (mountains, frame x 12..18, y 4..11) open at the front gate (12, 7) and the rear gate (18, 7)."))
    m.river([(8, 0), (8, 15)])
    m.rect("=", 8, 7, 8, 8)
    # the fort: a ring of mountains with a front gate (west) and a rear gate (east)
    m.frame("^", 12, 4, 18, 11)
    m.rect(".", 12, 7, 12, 7).rect(".", 18, 7, 18, 7)
    # roads: HQ -> causeway -> gate; flank roads north (y 2) and south (y 13) to the east road (x 20)
    m.road([(2, 7), (7, 7)]).road([(9, 7), (12, 7)])
    m.road([(10, 7), (10, 2), (20, 2)]).road([(10, 8), (10, 13), (20, 13)]).road([(20, 2), (20, 13)])
    m.road([(18, 7), (20, 7)])
    # cover: woods north and south of the fort for the flankers, a thicket guarding the south road
    m.rect("f", 14, 1, 16, 1).rect("f", 14, 14, 16, 14).rect("f", 12, 12, 13, 12)
    # properties
    m.put("1", 2, 7).put("B", 3, 5).puts("C", [(2, 10), (2, 4)])
    m.put("2", 16, 7).puts("B", [(14, 6), (14, 9)]).put("C", 16, 10)
    m.put("3", 19, 13).put("B", 17, 13).put("C", 20, 11).put("c", 15, 2).put("c", 15, 13)
    # the player's army (west bank)
    m.units(1, INF, [(4, 5), (4, 6), (4, 8), (4, 9)]).units(1, TANK, [(5, 5), (5, 6), (5, 8), (5, 9)])
    m.units(1, MECH, [(6, 5), (6, 9), (6, 10)]).units(1, MDT, [(5, 7), (6, 6)]).units(1, RECON, [(4, 7), (6, 8)])
    m.units(1, ART, [(3, 6), (3, 9)]).unit(1, AA, 4, 10)
    # Max in Ironhold
    m.units(2, INF, [(12, 6), (13, 7), (12, 9)], hold=True).units(2, MECH, [(13, 6), (13, 9)], hold=True)
    m.units(2, MDT, [(14, 7), (14, 8), (15, 8)]).units(2, TANK, [(15, 6), (15, 9)])
    m.units(2, ART, [(17, 6), (17, 9)]).unit(2, AA, 15, 5)
    # Jake on the south-east plain
    m.units(3, INF, [(18, 13), (20, 12)]).units(3, TANK, [(19, 10), (20, 9), (19, 9)]).units(3, RECON, [(21, 12), (19, 12)])
    m.unit(3, ROCK, 20, 13).unit(3, BCO, 21, 10)
    m.note("causeway", 8, 7, "wide bridge x=8, y 7..8 (the only crossing of the canal)").note("fort_gate", 12, 7, "front gate cell (12, 7), road from the causeway")
    m.note("rear_gate", 18, 7, "rear gate cell (18, 7), road to the east road x=20")
    m.note("hq1", 2, 7).note("hq2", 16, 7, "Max's HQ, inside the fort").note("hq3", 19, 13, "Jake's HQ")
    m.note("flank_n", 10, 2, "north flank road y=2 (x 10..20), Cassius's northern route").note("flank_s", 10, 13, "south flank road y=13 (x 10..20)")
    m.note("flank_n_start", 10, 5, "north flank branch point on the east bank (road x=10)").note("flank_s_start", 10, 10, "south flank branch point")
    return m
