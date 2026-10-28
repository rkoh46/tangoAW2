"""BH2 M5 Evergreen in Exile (Act I): the Allied exile capital on blasted ground (the Wasteland look). Sturm and Asuka (the forced pair "Perfect Intel") against Eagle and Javier.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole breaks out of the south-west ruins (HQ, a ring of bases, two Black Crystals that heal its army). The Allies hold
the blasted heart of the map: Javier's capital HQ on a plateau ringed by cliffs, and behind it, in the north-east corner, Eagle's airport district: a pocket walled by two pipelines with a seam
gate each, with a second HQ (`Q`, as BH1's M30 has one): when the capital's HQ falls, Eagle takes command from there with a fresh air-heavy army. One Allied army (army 2); the second HQ is held (it defeats nobody).
The Allied side is built big for the strong pair: bases, four airports, 42 units pre-deployed. The map is all land (the wasteland's water is lava: no sea, no ports, no river).
- Lanes: the ruined approach (a broken highway along a canyon: two cliff ranges with passes, the valley between them the direct road to the capital's south gate), the north-west route over the old
  ruins to the capital's west gate, the south-east route round the canyon's end through the ruined works to the airport district's south seam gate (34,9).
- Where the fight happens: the two Com Towers (9,12) in the north-west ruins and (31,22) in the south-east works, the canyon's passes, the capital's two gates, then the pocket's seam gates (30,5) and (34,9).
- Threats and answers: the Allies' Fighters, Bombers and Copters (the pocket's airports build more) -> Anti-Air and Missiles in Black Hole's army and the ones its bases build; their Tanks and Rockets
  -> Md Tanks, Neotank and artillery; the pocket's walls are pipelines: Black Hole's artillery and tanks break a seam.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, clear_fire_lines

W, H = 40, 32


def build():
    m = Canvas("bh2_05", W, H)
    # --- the canyon: two cliff ranges with passes, the valley between them the ruined approach; the capital's cliff ring; the cliffs round the pocket
    belt(m, "^", [(7, 20), (12, 17), (18, 13), (21, 10)], width=1, seed=1, gaps=[(12, 17), (17, 14)], p=1.0)
    belt(m, "^", [(11, 27), (17, 24), (24, 19), (28, 15)], width=1, seed=2, gaps=[(16, 25), (23, 20)], p=1.0)
    belt(m, "^", [(21, 4), (30, 4)], width=1, seed=3, gaps=[(25, 4)], p=1.0); belt(m, "^", [(21, 5), (21, 12)], width=1, seed=4, gaps=[(21, 9)], p=1.0)
    belt(m, "^", [(21, 13), (30, 13)], width=1, seed=5, gaps=[(26, 13)], p=1.0); belt(m, "^", [(30, 10), (30, 13)], width=1, seed=6, p=1.0)
    belt(m, "^", [(31, 11), (38, 12)], width=1, seed=7, gaps=[(36, 12)]); belt(m, "^", [(2, 12), (3, 18)], width=1, seed=8); belt(m, "^", [(1, 4), (6, 2)], width=2, seed=9, gaps=[(4, 3)])
    belt(m, "^", [(12, 2), (18, 3)], width=1, seed=10); belt(m, "^", [(26, 21), (33, 20)], width=1, seed=11, gaps=[(29, 20)]); belt(m, "^", [(34, 26), (38, 22)], width=1, seed=12)
    belt(m, "^", [(18, 29), (26, 30)], width=1, seed=13); belt(m, "^", [(14, 9), (17, 8)], width=1, seed=14)
    for i, (cx, cy, n) in enumerate([(12, 12, 3), (24, 24, 3), (8, 8, 3), (35, 16, 3), (16, 28, 2)]):
        m.cluster("f", cx, cy, n, seed=40 + i)                              # (dead trees: the wasteland look draws few)
    for i, (cx, cy, n) in enumerate([(9, 16, 7), (16, 10, 6), (24, 23, 7), (14, 14, 5), (33, 16, 7), (10, 5, 6), (28, 28, 6), (2, 28, 4), (36, 28, 6), (20, 27, 5), (5, 17, 5),
                                     (18, 21, 5), (36, 21, 5), (13, 30, 4), (27, 17, 4), (16, 3, 4), (8, 23, 3)]):
        m.cluster("^", cx, cy, n, seed=60 + i)                              # (rubble heaps and slag: the wasteland's broken ground)
    for i, (cx, cy, n) in enumerate([(7, 10, 4), (22, 19, 4), (31, 27, 4), (4, 21, 3), (15, 26, 3), (33, 12, 3), (11, 9, 3), (38, 17, 3), (26, 4, 2)]):
        m.cluster("f", cx, cy, n, seed=80 + i)
    # --- the pocket's pipe walls: x30 from the north edge to y9, then y9 east to the map edge; the seams (30,5) and (34,9) are its gates
    m.pipe([(30, 0), (30, 9)]); m.pipe([(30, 9), (39, 9)]); m.put("Z", 30, 5); m.put("Z", 34, 9)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M5 Evergreen in Exile (Wasteland look, no sea): Black Hole (HQ 1 (5,27), the forced pair Sturm + Asuka) against the Allied army 2 (Javier's HQ 2 (25,9) in the cliff-ringed capital; Eagle takes over from the second HQ Q (36,3) "
        "in the airport district, a pocket walled by pipelines with seam gates (30,5) and (34,9), when it falls: a held second HQ as in BH1's M30). Com Towers (9,12) and (31,22). The ruined approach: the canyon valley's highway "
        "to the capital's south gate (26,13). Black Crystals by Black Hole's HQ. Player: INF7 MECH4 TANK5 MDT2 NEO1 ART3 ROCK1 AA2 MIS1 RECON1 APC2; Allies: INF8 MECH4 TANK6 MDT3 ART4 ROCK2 AA3 MIS2 RECON2 APC1 FTR3 BMB2 BCO2."))
    m.put("1", 5, 27).put("2", 25, 9).put("Q", 36, 3).puts("t", [(9, 12), (31, 22)])
    m.stamp("X", 3, 25).stamp("X", 8, 25)
    # --- roads: the broken highway up the canyon, the north-west route over the ruins, the south-east route to the pocket's south gate, the capital's streets and the pocket's
    route(m, [(7, 27), (10, 24), (14, 21), (18, 18), (22, 15), (26, 14), (26, 12)], seed=1)
    route(m, [(5, 25), (4, 19), (5, 13), (8, 8), (14, 6), (20, 7), (21, 9), (24, 9)], seed=2)
    route(m, [(8, 28), (17, 29), (25, 27), (32, 25), (36, 19), (36, 14), (36, 12), (34, 10)], seed=3)
    route(m, [(26, 12), (26, 9), (25, 8)], seed=4); route(m, [(25, 9), (28, 8), (29, 5)], seed=5); route(m, [(34, 8), (36, 5), (36, 4), (38, 4)], seed=6); route(m, [(31, 5), (34, 5), (36, 4)], seed=7)
    route(m, [(5, 13), (8, 12), (9, 13)], seed=8); route(m, [(32, 25), (31, 23)], seed=9); route(m, [(14, 21), (10, 17), (8, 14), (8, 12)], seed=10)
    route(m, [(18, 29), (18, 31)], seed=11); route(m, [(26, 14), (30, 16), (32, 18), (34, 22), (32, 25)], seed=12)
    thin_roads(m)
    # --- towns: Black Hole's ruins district, the ruined villages (neutral), the capital, the airport district
    town(m, 6, 26, "BBC", seed=1); town(m, 4, 24, "BC", seed=2); town(m, 8, 27, "BC", seed=3); town(m, 7, 22, "Ca", seed=4, radius=3)
    town(m, 9, 12, "CCb", seed=5, radius=3); town(m, 5, 13, "CC", seed=6); town(m, 8, 8, "CC", seed=7); town(m, 14, 6, "CCb", seed=8); town(m, 18, 6, "C", seed=9)
    town(m, 14, 21, "CC", seed=10); town(m, 19, 17, "Cb", seed=11); town(m, 24, 15, "CC", seed=12); town(m, 10, 24, "C", seed=13); town(m, 17, 29, "CC", seed=14)
    town(m, 24, 9, "BCC", seed=15, radius=3); town(m, 27, 7, "BC", seed=16); town(m, 27, 11, "BC", seed=17); town(m, 23, 6, "C", seed=18); town(m, 28, 9, "C", seed=19)
    town(m, 34, 3, "AAB", seed=20, radius=3); town(m, 37, 6, "AAB", seed=21, radius=3); town(m, 33, 7, "CC", seed=22); town(m, 36, 1, "C", seed=23)
    town(m, 31, 22, "CCb", seed=24, radius=3); town(m, 36, 17, "CC", seed=25); town(m, 33, 25, "BC", seed=26); town(m, 25, 27, "CC", seed=27); town(m, 36, 13, "C", seed=28)
    route(m, [(36, 19), (38, 24), (37, 29)], seed=14); town(m, 37, 27, "CC", seed=30)
    route(m, [(5, 13), (4, 8), (4, 4)], seed=13); town(m, 4, 5, "CC", seed=29)
    neutralize(m, 13)
    m.tidy()
    # --- units
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 7, MECH: 4, TANK: 5, MDT: 2, NEO: 1, ART: 3, ROCK: 1, AA: 2, MIS: 1, RECON: 1, APC: 2}, (2, 21, 13, 30), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 2, ART: 3, AA: 2, MIS: 1, RECON: 1}, (22, 5, 29, 12), seed=2, gap=0, avoid=av)          # the capital
    m.spread(2, {INF: 3, MECH: 1, TANK: 2, ROCK: 1, RECON: 1}, (12, 3, 20, 10), seed=4, gap=1, avoid=av)                                  # the north-west ruins
    m.spread(2, {INF: 1, MECH: 1, TANK: 1, MDT: 1, ART: 1, AA: 1, MIS: 1, ROCK: 1, APC: 1}, (20, 14, 33, 22), seed=5, gap=1, avoid=av)    # the canyon's head
    m.spread(2, {FTR: 3, BMB: 2, BCO: 2}, (31, 0, 39, 8), seed=3, gap=0, avoid=av)
    m.note("hq", 5, 27, "Black Hole's HQ"); m.note("enemy_hq", 25, 9, "the capital's HQ (objective 1)")
    m.note("mark_hq2", 36, 3, "second HQ: Eagle takes over here")
    m.note("gate_w", 30, 5, "seam gate (the pocket's west wall)"); m.note("gate_s", 34, 9, "seam gate (the pocket's south wall)")
    return m
