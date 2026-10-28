"""BH2 M8 Fuel Line (Act I): a long convoy road across Green Earth's heartland, fuel depots along it. Koal (forced, Black Hole) against Jess (Green Earth): the road builder against the tanks. Normal look, sandstorm.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge, a long east-west valley closed by a mountain band along the north edge and a broken one along the south, with the highway down its middle and a river across the centre (two bridges).
The situation: Koal (the highway's master) starts in the west with his HQ and a district of bases; Jess holds the east, her tanks massed on the plains behind the river. Five fuel depots (cities) stand along the highway: one near each HQ, three round the river; whoever holds them keeps the road open and the other's tanks dry.
- Lanes: the highway and its parallel side roads through the valley, the three bridges, the broken southern ridge with two passes, the north band's one pass.
- Where the fight happens: the bridges and the depots round them, then the east plain.
- Properties: a district of bases at each HQ, the five depots, villages on the side roads.
- Threats and answers: Jess's tanks across the open plains -> Koal's Rockets and Md Tanks from the ridges; his artillery behind the river.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 40, 28


def build():
    m = Canvas("bh2_08", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the valley: a mountain band along the north, a broken ridge along the south
    belt(m, "^", [(0, 3), (8, 4), (15, 2), (23, 4), (31, 2), (39, 4)], width=2, seed=1, gaps=[(12, 3), (27, 3)], p=0.86)
    belt(m, "^", [(0, 24), (7, 23), (14, 25), (21, 23), (30, 25), (39, 23)], width=1, seed=2, gaps=[(10, 24), (25, 24), (35, 24)], p=0.88)
    belt(m, "^", [(3, 1), (12, 1)], width=1, seed=3, p=0.9); belt(m, "^", [(25, 1), (29, 0), (33, 1), (36, 0)], width=1, seed=4, p=0.9)
    m.cluster("^", 6, 26, 5, seed=5); m.cluster("^", 32, 26, 5, seed=6); m.cluster("^", 19, 7, 4, seed=7)
    # --- the river across the centre, two bridges
    m.river([(20, 0), (20, 10), (21, 10), (21, 17), (20, 17), (20, 27)])
    belt(m, "f", [(9, 9), (14, 12)], width=1, seed=8); belt(m, "f", [(25, 16), (30, 18)], width=1, seed=9); belt(m, "f", [(4, 18), (9, 21)], width=1, seed=10); belt(m, "f", [(30, 8), (35, 10)], width=1, seed=11)
    belt(m, "f", [(12, 19), (16, 17)], width=1, seed=12); belt(m, "f", [(24, 9), (27, 12)], width=1, seed=13)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M8 Fuel Line (normal look, sandstorm): Koal (forced, Black Hole, HQ 1 (4,14), west) against Jess (Green Earth, HQ 2 (35,14), east). A river across the centre (x 20..21) with bridges (21,14), (20,8) and (20,21); five fuel depots (cities) along the highway: (11,14), (16,14), (24,14), (28,13), (20,10). "
        "Player: INF5 MECH3 TANK4 MDT2 ART2 ROCK2 RECON1 AA1 APC1; Jess: INF4 MECH2 TANK7 MDT3 ART2 ROCK1 RECON2 AA1."))
    m.put("1", 4, 14).put("2", 35, 14)
    # (the bridges: the highway (21,14), the north road (20,8) and the south road (20,21), each with a straight approach)
    m.put("=", 21, 14); m.put("=", 20, 8); m.put("=", 20, 21)
    route(m, [S(4, 14), S(11, 14), (18, 14), (19, 14), (20, 14), (21, 14, "="), (22, 14), (23, 14), S(25, 14), S(29, 14), S(35, 14)], seed=1, wander=0.3)
    route(m, [S(5, 17), S(10, 20), (17, 21), (18, 21), (19, 21), (20, 21, "="), (21, 21), (22, 21), S(26, 20), S(31, 18), S(35, 15)], seed=2, wander=0.6)
    route(m, [S(4, 13), S(8, 9), S(13, 7), (17, 8), (18, 8), (19, 8), (20, 8, "="), (21, 8), (22, 8), S(25, 8), S(30, 9), S(34, 12)], seed=3, wander=0.6)
    route(m, [S(11, 14), S(12, 4)], seed=4) if False else None
    route(m, [S(28, 13), S(27, 3)], seed=5, wander=0.4); route(m, [S(10, 20), S(10, 24)], seed=6); route(m, [S(31, 18), S(35, 24)], seed=7)
    thin_roads(m); fix_rungs(m)
    for args in [(4, 14, "BBC"), (6, 11, "BC"), (6, 17, "BC"), (2, 12, "C"), (35, 14, "BBC"), (33, 11, "BC"), (33, 17, "BC"), (37, 12, "C"),
                 (11, 14, "C"), (16, 14, "C"), (24, 14, "C"), (28, 13, "C"), (20, 10, "C"), (9, 20, "c"), (14, 9, "c"), (30, 20, "c"), (26, 8, "c"), (16, 21, "c"), (24, 20, "c"), (8, 6, "c"), (32, 7, "c"), (3, 20, "c"), (37, 20, "c"), (12, 27, "c"), (27, 26, "c"), (2, 2, "c"), (14, 5, "c"), (22, 5, "c"), (38, 3, "c"), (8, 14, "c"), (31, 22, "c"), (17, 25, "c"), (38, 26, "c"), (13, 16, "c"), (27, 11, "c"), (22, 18, "c"), (34, 5, "c"), (37, 25, "c"), (17, 2, "c"), (22, 2, "c"), (2, 26, "cc"), (24, 24, "cc"), (14, 22, "c"), (30, 3, "cc"), (6, 3, "cc"), (36, 17, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    m.put("f", 27, 1).put("f", 30, 1).put(".", 26, 2).put("f", 1, 2).put(".", 4, 3).put("f", 7, 3).put("f", 29, 2).put(".", 32, 3).put("f", 35, 2).put(".", 22, 3)
    neutralize(m, 6)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, ROCK: 2, RECON: 1, AA: 1, APC: 1}, (1, 8, 14, 19), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 7, MDT: 3, ART: 2, ROCK: 1, RECON: 2, AA: 1}, (26, 8, 38, 20), seed=2, gap=0, avoid=av)
    m.note("hq", 4, 14, "Koal's HQ"); m.note("enemy_hq", 35, 14, "Jess's HQ (objective)")
    return m
