"""M8 Hammer and Anvil: Ironhold, an Orange Star border fort in a ring of crags on the Marches plain, behind the Brimwater canal. One wide causeway crosses the canal; flank roads run round the crags to the
fort's rear gate. Klaus holds the front (the hammer), Cassius rides the flank (the anvil); Jake's relief column camps on the south-east plain."""
import math
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es08", 38, 24)
    road = lambda pts: m.line("R", pts, over=".fR")
    m.header(armies=3, colours=(BM, OS, OS), team=[1, 2, 2], objective=[1], comment=(
        "M8 Hammer and Anvil (tag mission, Klaus + Cassius): rout both Orange Star armies or capture Max's HQ '2' (26, 10). "
        "Start forces: player INF4 MECH3 TANK4 MDT2 RECON2 ART2 AA1 (18 units), 1 base (4, 8), funds 4000; "
        "Max (army 2, in the fort) INF3 (hold) MECH2 (hold) MDT2 TANK1 ART2 AA1 (11), Jake (army 3, south-east plain) INF2 TANK2 RECON2 ROCK1 (7). "
        "Threat -> answer: Max's ARTs behind the crags shell the causeway -> Recon spots, the player's two ARTs and Tanks rush the gate, or Cassius's flank takes the rear; "
        "Jake's Rocket -> the player's Tanks and AA; Md Tanks at the gate -> player Md Tanks + ART + the Tag Power (day 3 lesson). "
        "Forced routes: the Brimwater canal is crossed only by the causeway (15, 8..9); the crags ring (centre (26, 10)) opens at the front gate (19..21, 9..10) and the rear gate (32..35, 10)."))
    # the fort: an organic ring of crags (an ellipse eaten by noise) with a front gate west and a rear gate east
    cx, cy, rx, ry = 26.0, 10.0, 7.6, 6.2
    ph1, ph2 = 0.9, 2.1
    for y in range(24):
        for x in range(38):
            ang = math.atan2((y - cy) / ry, (x - cx) / rx)
            d = math.hypot((x - cx) / rx, (y - cy) / ry)
            wob = 0.07 * math.sin(3 * ang + ph1) + 0.05 * math.sin(5 * ang + ph2)
            if 0.74 + wob <= d <= 1.0 + wob:
                m.put("^", x, y)
    # gates and a postern of woods
    for gx in range(17, 23):
        for gy in (9, 10):
            m.put(".", gx, gy)
    for gx in range(31, 37):
        m.put(".", gx, 10)
    # the Brimwater canal, three reaches, spring at the north edge, mouth at the south edge; the causeway is two lanes wide
    m.river([(13, 0), (13, 5), (15, 5), (15, 12), (16, 12), (16, 23)])
    m.put("=", 15, 8).put("=", 15, 9)
    # properties
    m.put("1", 3, 11).put("B", 4, 8).puts("C", [(3, 15), (3, 6)]).puts("c", [(8, 4), (9, 18)])
    m.put("2", 26, 10).puts("B", [(23, 8), (23, 12)]).put("C", 28, 14).put("c", 24, 2)
    m.put("3", 34, 20).put("B", 31, 20).put("C", 36, 17).put("c", 22, 19)
    # roads
    road([(3, 11), (6, 11), (6, 9), (10, 9), (10, 8), (14, 8)])
    road([(4, 8), (4, 9), (6, 9)])
    road([(6, 11), (6, 15), (3, 15)])
    road([(8, 8), (8, 5), (8, 4)])
    road([(4, 11), (4, 6), (3, 6)])
    road([(6, 15), (6, 18), (9, 18)])
    road([(16, 8), (18, 8), (18, 10), (22, 10), (23, 10), (24, 10), (26, 10)])
    road([(18, 8), (18, 4), (22, 4), (22, 2), (24, 2)])
    road([(24, 2), (30, 2), (30, 3), (35, 3), (35, 10)])
    road([(18, 10), (18, 17), (22, 17), (22, 19), (28, 19), (28, 17), (35, 17)])
    road([(26, 10), (32, 10), (35, 10)])
    road([(35, 10), (36, 10)])
    road([(23, 8), (23, 12)])
    road([(28, 14), (28, 12), (26, 12), (26, 10)])
    road([(35, 17), (35, 20), (34, 20)])
    road([(31, 20), (31, 19), (28, 19)])
    road([(35, 17), (36, 17)])
    # cover: hedgerow woods on the plain, thickets along the flank roads, a copse inside the fort
    for cx0, cy0, n, sd, ch in [(11, 5, 9, 1, "f"), (11, 14, 10, 2, "f"), (7, 13, 7, 3, "f"), (19, 6, 6, 4, "f"), (19, 14, 6, 5, "f"), (26, 3, 8, 6, "f"), (27, 18, 8, 7, "f"),
                                (33, 6, 7, 8, "f"), (33, 14, 7, 9, "f"), (25, 12, 5, 10, "f"), (14, 20, 8, 11, "f"), (2, 20, 8, 12, "f"), (8, 22, 6, 13, "f"), (36, 5, 6, 14, "f"),
                                (3, 2, 6, 15, "^"), (13, 17, 4, 16, "^"), (10, 1, 4, 17, "^"), (37, 12, 4, 18, "^"), (21, 22, 5, 19, "^"), (30, 22, 5, 20, "f"), (1, 12, 4, 21, "f")]:
        m.cluster(ch, cx0, cy0, n, seed=sd)

    # the player's army on the west bank: guns behind, armour and infantry nearer the causeway
    m.spread(1, {ART: 2, AA: 1}, (2, 7, 6, 15), seed=1, gap=1)
    m.spread(1, {MDT: 2, TANK: 4, RECON: 2}, (6, 6, 12, 16), seed=2, gap=1)
    m.spread(1, {INF: 4, MECH: 3}, (4, 5, 12, 17), seed=3, gap=1)
    # Max in Ironhold: pickets at the gate, guns and armour behind the crags
    m.units(2, INF, [(22, 9), (21, 11), (24, 8)], hold=True).units(2, MECH, [(23, 13), (25, 9)], hold=True)
    m.units(2, MDT, [(24, 10), (27, 9)]).unit(2, TANK, 27, 12)
    m.units(2, ART, [(29, 8), (29, 12)], hold=True).unit(2, AA, 26, 7)
    # Jake on the south-east plain
    m.units(3, INF, [(33, 19), (35, 18)]).units(3, TANK, [(30, 18), (33, 21)]).units(3, RECON, [(31, 17), (36, 20)]).unit(3, ROCK, 35, 21)
    m.note("causeway", 15, 8, "wide bridge x=15, y 8..9 (the only crossing of the canal)").note("fort_gate", 20, 9, "front gate (x 17..22, y 9..10), road from the causeway")
    m.note("rear_gate", 32, 10, "rear gate (x 31..36, y 10), road to the east road x=35")
    m.note("hq1", 3, 11).note("hq2", 26, 10, "Max's HQ, inside the fort").note("hq3", 34, 20, "Jake's HQ")
    m.note("flank_n", 18, 4, "north flank road (y 2..4, x 18..35), Cassius's northern route").note("flank_s", 18, 17, "south flank road (y 17..19, x 18..35)")
    m.note("flank_n_start", 18, 8, "north flank branch point on the east bank (road x=18)").note("flank_s_start", 18, 10, "south flank branch point")
    return m
