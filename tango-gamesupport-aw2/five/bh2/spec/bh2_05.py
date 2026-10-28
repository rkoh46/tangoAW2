"""BH2 M5 Evergreen in Exile (Act I): the Allied exile capital, a big map. Sturm and Asuka (the forced pair "Perfect Intel") against Eagle and Javier.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole lands in the south-west (HQ, two ports, a ring of bases, two Black Crystals that
heal its army); the Allies hold the north-east: Javier's capital HQ behind a pipe wall, and, behind it, the airport district with a second HQ (`Q`, as BH1's M30 has one):
when the capital's HQ falls, Eagle takes command from there with a fresh air-heavy army. One Allied army (army 2); the second HQ is held (it defeats nobody).
The Allied side is built big for the strong pair: 8 bases, 4 airports, many cities, 42 units pre-deployed.
- Lanes: three east-west roads (north y8, middle y16, south y24) and three north-south roads (x8, x23, x37) over the river, with a bridge each; a river with four bends from
  the north edge to the south sea. The capital's pipe wall (x25 from the mountains to y13, then y13 to the massif) has two seam gates: the north road's (25,8) and the south road's
  (29,13); the open way is the long road x37 up the east edge to the capital's south-east gate (34..39, 13).
- Where the fight happens: the two Com Towers (17,12) and (25,20) either side of the river, the neutral airport and bases in the centre, the bridges, then the two gates.
- Threats and answers: the Allies' Fighters, Bombers and Copters -> Anti-Air and Missiles in Black Hole's army and the ones its bases build; their Tanks and Rockets -> Md Tanks,
  Neotank and artillery.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 40, 32


def build():
    m = Canvas("bh2_05", W, H)
    m.rect("~", 0, 29, 39, 31)
    # --- roads (the river, bridges and pipes are laid over them)
    m.road([(2, 24), (37, 24)]); m.road([(2, 16), (38, 16)]); m.road([(3, 8), (24, 8)]); m.road([(26, 8), (38, 8)])
    m.road([(8, 4), (8, 24)]); m.road([(23, 3), (23, 24)]); m.road([(37, 8), (37, 24)]); m.road([(29, 14), (29, 24)]); m.road([(29, 2), (29, 12)])
    m.road([(8, 12), (17, 12)]); m.road([(23, 20), (25, 20)]); m.road([(30, 4), (38, 4)]); m.road([(33, 4), (33, 8)]); m.road([(5, 20), (5, 24)])
    m.road([(14, 16), (14, 12)]); m.road([(31, 16), (31, 20)])
    # --- relief
    m.cluster("^", 25, 1, 7, seed=1); m.cluster("^", 33, 13, 8, seed=2); m.cluster("^", 3, 4, 14, seed=3); m.cluster("^", 12, 3, 10, seed=4); m.cluster("^", 36, 11, 8, seed=5)
    m.cluster("^", 12, 20, 10, seed=6); m.cluster("^", 28, 27, 9, seed=7); m.cluster("^", 3, 12, 8, seed=8); m.cluster("^", 17, 24, 6, seed=9); m.cluster("^", 33, 20, 8, seed=10)
    m.cluster("^", 16, 5, 7, seed=11); m.cluster("^", 38, 28, 4, seed=12); m.cluster("^", 6, 1, 6, seed=14); m.cluster("^", 38, 22, 5, seed=15); m.cluster("^", 27, 12, 5, seed=13)
    for i, (cx, cy, n) in enumerate([(6, 6, 9), (15, 9, 8), (11, 14, 8), (26, 5, 8), (31, 6, 8), (36, 2, 6), (17, 17, 8), (27, 17, 8), (22, 14, 6), (35, 17, 7), (6, 18, 8),
                                     (14, 27, 7), (4, 27, 6), (33, 26, 8), (38, 20, 6), (20, 27, 6), (10, 9, 5), (31, 22, 6), (20, 3, 6), (9, 22, 6), (26, 22, 6), (2, 21, 5), (2, 1, 6), (9, 1, 5), (14, 1, 4), (38, 14, 6), (35, 23, 6), (33, 28, 5), (9, 26, 5), (26, 26, 5), (38, 8, 4), (24, 11, 4)]):
        m.cluster("f", cx, cy, n, seed=30 + i)
    m.scatter("f", (0, 0, 39, 28), 0.035, seed=5)
    # --- the river: source at the north edge, four bends, mouth in the south sea
    m.river([(18, 0), (18, 6), (19, 6), (19, 18), (21, 18), (21, 28)])
    m.bridge(19, 8).bridge(19, 16).bridge(21, 24)
    # --- the capital's pipe wall: x25 from the mountains down to y13, then y13 east to the massif; the seams are the gates on the north and south roads
    m.rect("^", 24, 2, 26, 2)
    m.pipe([(25, 3), (25, 13)]); m.pipe([(25, 13), (32, 13)]); m.put("Z", 25, 8); m.put("Z", 29, 13)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M5 Evergreen in Exile: Black Hole (HQ 1 (5,24), the forced pair Sturm + Asuka) against the Allied army 2 (Javier's HQ 2 (30,10); Eagle takes over from the second HQ Q (36,3) in the airport district when it falls: "
        "a held second HQ as in BH1's M30). Com Towers (17,12) and (25,20). Pipe wall with seams (25,8) and (29,13); the open way is the east road x37. Black Crystals by Black Hole's HQ. "
        "Player: INF7 MECH4 TANK5 MDT2 NEO1 ART3 ROCK1 AA2 MIS1 RECON1 APC2; Allies: INF8 MECH4 TANK6 MDT3 ART4 ROCK2 AA3 MIS2 RECON2 APC1 FTR3 BMB2 BCO2."))
    m.put("1", 5, 24).put("2", 30, 10).put("Q", 36, 3)
    m.puts("P", [(7, 28), (14, 28)]).puts("t", [(17, 12), (25, 20)])
    m.place("B", 4, (1, 17, 14, 27), seed=1, gap=3).place("C", 7, (1, 14, 14, 27), seed=2, gap=2, reach=3)
    m.stamp("X", 3, 22).stamp("X", 7, 22)
    m.place("A", 4, (30, 0, 39, 7), seed=3, gap=3, reach=3).place("B", 3, (30, 0, 39, 7), seed=4, gap=2, reach=3).place("B", 4, (26, 6, 38, 12), seed=5, gap=3, reach=3)
    m.place("C", 8, (26, 0, 39, 12), seed=6, gap=2, reach=3)
    m.place("a", 1, (14, 10, 24, 22), seed=7, gap=4, reach=3).place("b", 4, (12, 6, 26, 26), seed=8, gap=4)
    m.place("c", 6, (0, 0, 14, 13), seed=9, gap=3, reach=3).place("c", 4, (14, 0, 24, 14), seed=10, gap=3, reach=3).place("c", 6, (14, 14, 26, 27), seed=11, gap=3, reach=3)
    m.place("c", 5, (26, 14, 39, 28), seed=12, gap=3, reach=3).place("c", 2, (0, 14, 14, 20), seed=13, gap=2, reach=3)
    m.put("c", 2, 2)
    m.tidy()
    shore(m, 1, (0, 29, 6, 29), dirs="NS"); shore(m, 1, (8, 29, 13, 29), dirs="NS"); shore(m, 1, (15, 29, 20, 29), dirs="NS"); shore(m, 1, (22, 29, 38, 29), dirs="NS")
    # --- units
    m.spread(1, {INF: 7, MECH: 4, TANK: 5, MDT: 2, NEO: 1, ART: 3, ROCK: 1, AA: 2, MIS: 1, RECON: 1, APC: 2}, (2, 17, 14, 27), seed=1, gap=0, avoid="~r=-^IZ#X")
    m.spread(2, {INF: 8, MECH: 4, TANK: 6, MDT: 3, ART: 4, ROCK: 2, AA: 3, MIS: 2, RECON: 2, APC: 1}, (26, 0, 39, 12), seed=2, gap=0, hold=False, avoid="~r=-^IZ#X12345QBCPTbcpt")
    m.spread(2, {FTR: 3, BMB: 2, BCO: 2}, (30, 0, 39, 7), seed=3, gap=0, avoid="~r=-^IZ#X12345QBCPTbcpt")
    m.note("hq", 5, 24, "Black Hole's HQ"); m.note("enemy_hq", 30, 10, "the capital's HQ (objective 1)")
    m.note("mark_hq2", 36, 3, "second HQ: Eagle takes over here")
    m.note("gate_n", 25, 8, "seam gate (north road)"); m.note("gate_s", 29, 13, "seam gate (south road)")
    return m
