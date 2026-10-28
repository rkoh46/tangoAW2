"""BH2 M14 The Long Border (Act III opener): the border between Green Earth and Blue Moon, a river with a handful of bridges. A free pair (Black Hole) against Javier (Green Earth) and Grit (Blue Moon), two allied armies, normal look, sandstorm.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge, a river that steps across the whole map from the west edge to the east edge in four long reaches; the north bank is Blue Moon's, the south bank Green Earth's.
The situation: Black Hole stands on the south bank's west end (HQ 1, a base district); Javier holds the south bank's east end (HQ 2); Grit holds the north bank (HQ 3), his army across the river from both. Six bridges join the banks (x 5, 15, 22, 25, 34, 37); two ridges on the north bank and a wood on the south shelter the crossings.
- Lanes: the south bank's road to Javier, the four bridges, the north bank's road to Grit and the ridge passes.
- Where the fight happens: the centre bridges (15, 25) and the villages by them; whoever takes the middle splits the allies.
- Properties: a district of bases at each HQ, a village at each bridgehead.
- Threats and answers: Javier's tanks along the south road -> Rockets and Md Tanks from the wood; Grit's Neotanks over the bridges -> artillery on the south bank.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 44, 26


def build():
    m = Canvas("bh2_14", W, H)
    S = lambda x, y: snap(m, x, y)
    m.river([(0, 12), (10, 12), (10, 13), (20, 13), (20, 11), (30, 11), (30, 13), (43, 13)])
    for x, y in ((5, 12), (15, 13), (22, 11), (25, 11), (34, 13), (37, 13)):
        m.put("=", x, y)
    # --- relief: the north bank's two ridges with passes, the south bank's wood, hills at the ends
    belt(m, "^", [(6, 6), (12, 4), (18, 7)], width=1, seed=1, gaps=[(12, 4)]); belt(m, "^", [(24, 8), (31, 7), (38, 9)], width=1, seed=2, gaps=[(31, 7)]); belt(m, "^", [(1, 2), (5, 1)], width=1, seed=3)
    belt(m, "f", [(8, 16), (14, 18), (19, 16)], width=1, seed=4); belt(m, "f", [(24, 17), (28, 19), (33, 18)], width=1, seed=5); belt(m, "f", [(2, 8), (7, 9)], width=1, seed=6); belt(m, "f", [(35, 3), (41, 5)], width=1, seed=7)
    belt(m, "^", [(40, 17), (42, 22)], width=1, seed=8); belt(m, "^", [(1, 22), (4, 24)], width=1, seed=9)
    for i, (cx, cy, n) in enumerate([(22, 4, 3), (12, 21, 3), (30, 22, 3), (40, 8, 3), (3, 15, 2)]):
        m.cluster("f", cx, cy, n * 2, seed=40 + i)
    belt(m, "f", [(22, 15), (24, 21), (21, 24)], width=1, seed=11); belt(m, "^", [(33, 14), (36, 17)], width=1, seed=12); belt(m, "^", [(8, 14), (12, 16)], width=1, seed=13, gaps=[(10, 15)]); belt(m, "f", [(17, 2), (21, 4)], width=1, seed=14)
    belt(m, "^", [(10, 9), (14, 11)], width=1, seed=15); belt(m, "f", [(28, 14), (31, 16)], width=1, seed=16); belt(m, "f", [(37, 6), (41, 7)], width=1, seed=17); belt(m, "^", [(18, 17), (21, 18)], width=1, seed=18)
    for i, (cx, cy, n) in enumerate([(9, 3, 3), (26, 24, 3), (14, 8, 3), (35, 10, 3)]):
        m.cluster("f", cx, cy, n * 2, seed=60 + i)
    m.header(armies=3, colours=(BH, GE, BM), team=(1, 2, 2), objective=[1], comment=(
        "M14 The Long Border (normal look, sandstorm): a free pair (Black Hole, HQ 1 (6,19), south bank west) against Javier (Green Earth, HQ 2 (37,20), south bank east) and Grit (Blue Moon, HQ 3 (30,4), the north bank), allied. "
        "A river steps across the map (y 11..13) with six bridges (5,12) (15,13) (22,11) (25,11) (34,13) (37,13). Player: INF5 MECH3 TANK4 MDT2 ART2 ROCK1 RECON1 AA1 APC1; Javier: INF4 MECH2 TANK4 MDT2 ART2 AA1 RECON1; Grit: INF4 MECH2 TANK3 MDT2 NEO1 ART2 ROCK1 AA1."))
    m.put("1", 6, 19).put("2", 37, 20).put("3", 30, 4).put("t", 20, 7).put("t", 20, 19)
    # --- roads: each bridge with a straight approach; the south road, the north road
    for x, y in ((5, 12), (15, 13), (25, 11), (37, 13)):
        pass
    route(m, [S(6, 19), S(5, 17), (5, 15), (5, 14), (5, 13), (5, 12, "="), (5, 11), (5, 10), (5, 9), S(9, 7), S(14, 6), S(20, 5), S(26, 4), S(30, 4)], seed=1, wander=0.5)
    route(m, [S(6, 20), S(10, 20), (15, 17), (15, 16), (15, 15), (15, 14), (15, 13, "="), (15, 12), (15, 11), (15, 10), S(20, 8), S(25, 7), (25, 8), (25, 9), (25, 10), (25, 11, "="), (25, 12), (25, 13), (25, 14), S(26, 18), S(31, 20), S(37, 20)], seed=2, wander=0.5)
    route(m, [S(37, 20), (37, 17), (37, 16), (37, 15), (37, 14), (37, 13, "="), (37, 12), (37, 11), (37, 10), S(34, 7), S(31, 5)], seed=3, wander=0.4)
    route(m, [S(20, 19), S(20, 16)], seed=4) if False else None
    route(m, [S(10, 20), S(14, 23), S(22, 22), S(30, 23), S(36, 22)], seed=5, wander=0.6); route(m, [S(30, 4), S(36, 3), S(41, 4)], seed=6); route(m, [S(30, 4), S(25, 2), S(19, 2), S(10, 3)], seed=7, wander=0.5)
    route(m, [S(22, 16), (22, 14), (22, 13), (22, 12), (22, 11, "="), (22, 10), (22, 9), S(22, 7)], seed=8, wander=0.2); route(m, [S(34, 17), (34, 15), (34, 14), (34, 13, "="), (34, 12), (34, 11), (34, 10), S(34, 8)], seed=9, wander=0.2)
    thin_roads(m); fix_rungs(m)
    for args in [(6, 19, "BBC"), (4, 22, "BC"), (9, 18, "BC"), (3, 17, "C"), (37, 20, "BBC"), (40, 22, "BC"), (34, 18, "BC"), (41, 18, "C"), (30, 4, "BBC"), (33, 6, "BC"), (27, 3, "BC"), (35, 2, "C"),
                 (15, 15, "C"), (25, 13, "C"), (5, 14, "C"), (37, 15, "C"), (15, 9, "C"), (25, 9, "C"), (20, 7, "cb"), (20, 19, "cb"), (11, 9, "c"), (28, 21, "c"), (2, 5, "c"), (42, 8, "c"), (18, 24, "c"), (22, 14, "c"), (9, 1, "c"), (35, 9, "c"), (13, 13, "c"), (28, 15, "c"), (39, 11, "c"), (22, 23, "c"), (8, 8, "c"), (18, 4, "cc"), (33, 4, "c"), (12, 24, "c"), (30, 24, "c"), (24, 16, "c"), (40, 24, "c"), (2, 20, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 7)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 1, APC: 1}, (1, 16, 14, 24), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 4, MDT: 2, ART: 2, AA: 1, RECON: 1}, (30, 15, 42, 24), seed=2, gap=0, avoid=av)
    m.spread(3, {INF: 4, MECH: 2, TANK: 3, MDT: 2, NEO: 1, ART: 2, ROCK: 1, AA: 1}, (23, 1, 40, 9), seed=3, gap=0, avoid=av)
    m.note("hq", 6, 19, "Black Hole's HQ"); m.note("enemy_hq", 37, 20, "Javier's HQ (objective)"); m.note("enemy_hq3", 30, 4, "Grit's HQ (objective)")
    return m
