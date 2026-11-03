"""Gauntlet 06, Harvest Run (docs/dev/gauntlet.md): ALL of Orange Star, one CO after another: four lines of one army (Andy, Max, Sami, Nell), 36 x 24 = 864 cells, five armies (the engine's five-army mode: the
player is army 5). Every line is Orange Star's colours and Orange Star's HQ: only the army slot differs (1 Andy, 2 Max, 3 Sami, 4 Nell), so the player cannot wear Orange Star here. The player (a free CO) holds the
south-west farm:
  1. Andy (army 1) holds the central farmland west of the brook from the start: infantry, tanks and plenty of repair.
  2. Max (army 2) arrives in the north-east orchards when Andy falls: heavy direct-fire tanks and recons on the high road.
  3. Sami (army 3) arrives in the south-east fields when Max falls: foot soldiers and transports, her HQ behind the lake.
  4. Nell (army 4) arrives in the north-west meadows when Sami falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): farmland. A brook (the Harvest Brook) runs from the north edge into a lake in the middle (x 17..19, y 10..13) and out to the south edge; a tributary joins the lake from the west
(the Mill Race, y 13). Bridges: the brook north (18,4) and (19,8), south (18,17) and (19,21), the Mill Race (3,13) and (11,14). Orchards (woods) in clusters, a ridge here and there, a farm town (cities and a base) in
every quarter and a road grid. The order is round the lake: centre-west (Andy), north-east (Max), south-east (Sami), north-west (Nell).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads

W, H = 36, 24
# the HQs: army 1 Andy, 2 Max, 3 Sami, 4 Nell, 5 the player
HQS = {"1": (11, 8), "2": (29, 5), "3": (30, 19), "4": (6, 4), "5": (4, 20)}
BR = [(18, 4), (19, 8), (18, 17), (19, 21), (3, 13), (11, 14)]


def build():
    m = Canvas("gauntlet_06", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the brook, the lake and the Mill Race
    m.rect("~", 17, 10, 19, 14)
    m.river([(18, 0), (18, 6), (19, 6), (19, 9)])
    m.river([(18, 15), (18, 18), (19, 18), (19, 23)])
    m.river([(0, 13), (6, 13), (6, 14), (16, 14)])
    for x, y in BR:
        m.put("=", x, y)
    # --- orchards (woods) in clusters, ridges and a pond
    for i, (cx, cy, n) in enumerate([(14, 7, 3), (8, 7, 3), (3, 9, 2), (24, 8, 3), (33, 9, 3), (23, 3, 3), (13, 18, 3), (8, 17, 3), (25, 16, 3), (32, 15, 3), (23, 21, 3), (3, 3, 2), (12, 3, 3), (30, 22, 2), (16, 21, 2), (28, 12, 2), (21, 6, 2), (30, 13, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(2, 17), (6, 17)], [(21, 13), (25, 13)], [(27, 11), (32, 12)], [(12, 12), (15, 11)], [(21, 19), (24, 19)], [(1, 7), (4, 6)], [(14, 1), (17, 2)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.blob("~", 27, 21, 1, 1, seed=3, wobble=0.3)
    m.header(armies=5, colours=(OS, OS, OS, OS, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 16, 12, 23)], hidden=[2, 3, 4], comment=(
        "Gauntlet 06 Harvest Run (normal look, no fog, 36 x 24, five armies): the player (army 5, HQ 5 (4,20), south-west, a free CO) against all of Orange Star: Andy (army 1, HQ (11,8), the centre-west farmland), "
        "then Max (army 2, HQ (29,5), the north-east orchards), Sami (army 3, HQ (30,19), the south-east fields) and Nell (army 4, HQ (6,4), the north-west meadows), who come onto the battlefield in turn: every line wears "
        "Orange Star's colour, only the army slots differ. The brook (x 18..19) and the Mill Race (y 13..14) meet in a lake (x 17..19, y 10..14); bridges (18,4) (19,8) (18,17) (19,21) (3,13) (11,14). Com Towers (14,10) (24,12) (12,20). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((14, 10), (24, 12), (12, 20)):
        m.put("t", x, y)
    # --- roads: a grid of farm roads over the bridges
    route(m, [S(4, 20), S(3, 16), (3, 14), (3, 13, "="), (3, 12), S(7, 10), S(11, 8)], seed=1, wander=0.5)
    route(m, [S(4, 20), S(9, 19), S(11, 16), (11, 15), (11, 14, "="), (11, 13), (11, 12), S(11, 8)], seed=2, wander=0.5)
    route(m, [S(11, 8), S(14, 9), S(17, 8), (18, 8), (19, 8, "="), (20, 8), S(24, 6), S(29, 5)], seed=3, wander=0.5)
    route(m, [S(6, 4), S(12, 4), (17, 4), (18, 4, "="), (19, 4), S(24, 4), S(29, 5)], seed=4, wander=0.5)
    route(m, [S(6, 4), S(7, 6), S(11, 8)], seed=5, wander=0.5)
    route(m, [S(29, 5), S(28, 10), S(25, 13), S(29, 17), S(30, 19)], seed=6, wander=0.6)
    route(m, [S(9, 19), S(14, 18), (17, 17), (18, 17, "="), (19, 17), S(24, 18), S(30, 19)], seed=7, wander=0.5)
    route(m, [S(12, 20), (17, 21), (18, 21), (19, 21, "="), (20, 21), S(25, 21), S(30, 19)], seed=8, wander=0.5)
    route(m, [S(30, 19), S(34, 20), S(34, 15)], seed=9, wander=0.4)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(4, 20, "BBC"), (8, 21, "BC"), (2, 17, "C"), (9, 17, "BC"), (6, 22, "C"), (13, 21, "C"),
                 (11, 8, "BBBC"), (7, 11, "BC"), (14, 7, "BC"), (14, 12, "C"), (4, 9, "C"),
                 (29, 5, "bbbc"), (25, 7, "bc"), (33, 3, "c"), (22, 2, "ca"), (31, 9, "cb"), (26, 11, "c"),
                 (30, 19, "bbac"), (26, 18, "bc"), (33, 17, "c"), (27, 22, "c"), (22, 22, "cb"), (33, 21, "ca"), (24, 15, "c"),
                 (6, 4, "bbc"), (2, 6, "c"), (10, 3, "bc"), (13, 5, "c"), (3, 1, "ca"), (22, 8, "b"), (21, 17, "b"), (15, 17, "b"), (16, 6, "b"), (34, 12, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    for y in range(16, 24):
        for x in range(0, 14):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 6, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 19, 10, 23), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 2, BCO: 2}, (1, 19, 10, 23), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 7, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 2, AA: 2, APC: 1}, (3, 3, 16, 9), seed=3, gap=0, avoid=av)
    m.spread(1, {BCO: 2, FTR: 1}, (3, 3, 16, 9), seed=4, gap=1, avoid=av)
    for k, t in {"1": "Andy's HQ (Orange Star): the first line, on the field from the start", "2": "Max's HQ (Orange Star, hidden until Andy falls)", "3": "Sami's HQ (Orange Star, hidden until Max falls)",
                 "4": "Nell's HQ (Orange Star, hidden until Sami falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
