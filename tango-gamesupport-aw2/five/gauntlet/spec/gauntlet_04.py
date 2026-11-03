"""Gauntlet 04, Brass Canal (docs/dev/gauntlet.md): a canal-town gauntlet of two lines, 30 x 22, three armies. The player (army 1, a free CO pick) holds the south-west quarter:
  1. Sasha (Blue Moon, army 2) holds the north-west quarter from the start: the Brass Works, a cluster of factories behind the west canal, with funds to burn.
  2. Javier (Green Earth, army 3) arrives in the south-east quarter when Sasha falls (her HQ taken or her line routed): tanks and artillery among his Com Towers.
No Black Hole inventions.

Design (docs/dev/map-design.md): four canals meet in a lake at the middle (x 14..16, y 10..12) and cut the map into four quarters: the west arm has bridges (4,11) and (10,12), the east arm
(20,11) and (26,10), the north arm (15,3) and (16,7), the south arm (15,15) and (14,19). Each quarter has a town and its roads; every canal is crossed twice, so no quarter is walled off
and the fight is for the bridgeheads (a base on each bank) and the lake's Com Towers. The player starts in the south-west quarter, Sasha holds the north-west across the west canal and Javier arrives in the
south-east, two canals from Sasha's ruins: the order sends the army round the lake.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads, prune_road_stubs

W, H = 30, 22
HQS = {"1": (3, 18), "2": (5, 4), "3": (25, 17)}
BR = [(4, 11), (10, 12), (20, 11), (26, 10), (15, 3), (16, 7), (15, 15), (14, 19)]


def build():
    m = Canvas("gauntlet_04", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the lake and its four canals
    m.rect("~", 14, 10, 16, 12)
    m.river([(0, 11), (6, 11), (6, 12), (13, 12)]); m.river([(17, 11), (22, 11), (22, 10), (29, 10)]); m.river([(15, 0), (15, 5), (16, 5), (16, 9)]); m.river([(15, 13), (15, 16), (14, 16), (14, 21)])
    for x, y in BR:
        m.put("=", x, y)
    # --- relief: woods along the banks, a few ridges; the quarters differ (works and sheds in the north-west, orchards in the south-east)
    for i, (cx, cy, n) in enumerate([(9, 3, 3), (2, 8, 2), (11, 7, 2), (21, 4, 3), (26, 7, 3), (19, 8, 2), (8, 15, 3), (11, 19, 2), (20, 16, 3), (27, 20, 3), (22, 19, 2), (3, 14, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(1, 1), (3, 2)], [(18, 1), (22, 2)], [(27, 3), (28, 8)], [(1, 20), (5, 21)], [(17, 20), (21, 21)], [(12, 14), (12, 17)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=3, colours=(OS, BM, GE), team=(1, 2, 2), objective=[1], hidden=[3], comment=(
        "Gauntlet 04 Brass Canal (normal look, no fog, 30 x 22, three armies): the player (army 1, HQ (3,18), south-west, a free CO) against Sasha (Blue Moon, army 2, HQ (5,4), the north-west Brass Works), then "
        "Javier (Green Earth, army 3, HQ (25,17), the south-east quarter) who comes onto the battlefield when Sasha's line falls. Four canals meet in a lake (x 14..16, y 10..12); bridges (4,11) (10,12) (20,11) (26,10) "
        "(15,3) (16,7) (15,15) (14,19). Com Towers (8,8) (22,13) (7,14) (23,8). No inventions."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put(".", *HQS["3"])
    for x, y in ((8, 8), (22, 13), (7, 14), (23, 8)):
        m.put("t", x, y)
    # --- roads: each quarter's HQ to its bridges, the bridgeheads joined round the lake
    route(m, [S(3, 18), S(4, 14), (4, 12), (4, 11, "="), (4, 10), S(5, 7), S(5, 4)], seed=1, wander=0.4)
    route(m, [S(3, 18), S(8, 18), S(10, 14), (10, 13), (10, 12, "="), (10, 11), S(9, 7), S(5, 4)], seed=2, wander=0.5)
    route(m, [S(5, 4), S(10, 3), (14, 3), (15, 3, "="), (16, 3), S(20, 4), S(23, 5)], seed=3, wander=0.5)
    route(m, [S(10, 7), (15, 7), (16, 7, "="), (17, 7), S(20, 8), S(23, 8)], seed=4, wander=0.5)
    route(m, [S(23, 8), (26, 9), (26, 10, "="), (26, 11), S(26, 15), S(25, 17)], seed=5, wander=0.5)
    route(m, [S(19, 8), (20, 10), (20, 11, "="), (20, 12), S(21, 14), S(25, 17)], seed=6, wander=0.5)
    route(m, [S(25, 17), S(20, 18), (15, 19), (14, 19, "="), (13, 19), S(9, 19), S(3, 18)], seed=7, wander=0.5)
    route(m, [S(20, 14), (16, 15), (15, 15, "="), (14, 15), S(9, 15), S(5, 15)], seed=8, wander=0.5)
    route(m, [S(23, 5), S(27, 2)], seed=9, wander=0.3)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(3, 18, "BBC"), (7, 20, "BC"), (2, 15, "C"), (8, 17, "BC"), (6, 13, "C"),
                 (5, 4, "BBBC"), (2, 5, "C"), (9, 2, "bc"), (8, 6, "c"), (3, 8, "bc"),
                 (25, 17, "bbac"), (28, 18, "c"), (22, 20, "cb"), (27, 14, "c"), (20, 15, "bc"), (23, 11, "b"),
                 (11, 14, "b"), (19, 12, "b"), (12, 8, "c"), (18, 6, "c"), (22, 2, "ca"), (27, 3, "c"), (12, 20, "c"), (18, 19, "c"), (10, 9, "b"), (4, 12, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 14, 12, 21), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 1, BCO: 1}, (1, 13, 12, 21), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 6, MECH: 2, TANK: 4, MDT: 3, ART: 3, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 1, 13, 9), seed=3, gap=0, avoid=av)
    m.spread(2, {BCO: 1, FTR: 1}, (1, 1, 13, 9), seed=4, gap=1, avoid=av)
    for k, t in {"1": "the player's HQ", "2": "Sasha's HQ (Blue Moon): the first line, on the field from the start", "3": "Javier's HQ (Green Earth, hidden until Sasha falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
