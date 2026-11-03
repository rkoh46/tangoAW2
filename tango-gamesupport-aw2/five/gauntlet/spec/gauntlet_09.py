"""Gauntlet 09, Silverpine Ford (docs/dev/gauntlet.md): a river-and-forest gauntlet of two lines, 32 x 22, three armies. The player (army 1, a free CO pick) holds the south-west clearing:
  1. Hachi (Green Earth, army 2) holds the eastern pines from the start: a forest market town, tanks and infantry behind the river.
  2. Sonja (Blue Moon, army 3) arrives in the north-west woods when Hachi falls: recons and artillery in the trees, her HQ behind the Silver Pool's western stream.
No Black Hole inventions.

Design (docs/dev/map-design.md): the Silver Pool (x 15..17, y 9..11) is fed by a river from the north edge (x 15..16) and drains to the south edge (x 15..16), and a stream joins it from the west edge. Together they cut the map into
three: the south-west clearing (the player), the north-west woods (Sonja) and the whole east (Hachi). The crossings are bridges: the river north (15,3) and (16,7), south (16,13) and (15,19), the stream (3,10) and (10,11).
Pine woods fill every bank (cover everywhere: infantry and recons rule), a few ridges, a road along each bridge and a town in each clearing.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads, prune_road_stubs

W, H = 32, 22
HQS = {"1": (3, 18), "2": (26, 10), "3": (6, 4)}
BR = [(15, 3), (16, 7), (16, 13), (15, 19), (3, 10), (10, 11)]


def build():
    m = Canvas("gauntlet_09", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the Silver Pool, the river through it and the stream from the west
    m.rect("~", 15, 9, 17, 11)
    m.river([(15, 0), (15, 5), (16, 5), (16, 8)])
    m.river([(16, 12), (16, 15), (15, 15), (15, 21)])
    m.river([(0, 10), (6, 10), (6, 11), (14, 11)])
    for x, y in BR:
        m.put("=", x, y)
    # --- the pines: dense woods on every bank, ridges between
    for i, (cx, cy, n) in enumerate([(12, 6, 4), (9, 3, 4), (3, 7, 3), (2, 2, 3), (13, 2, 3), (10, 8, 3), (4, 13, 3), (9, 14, 4), (12, 18, 4), (6, 20, 3), (2, 16, 2),
                                    (20, 4, 4), (25, 3, 4), (29, 6, 3), (22, 8, 3), (29, 13, 4), (24, 14, 4), (20, 17, 4), (27, 19, 4), (21, 12, 2), (30, 10, 2), (18, 20, 3), (12, 12, 2), (19, 2, 2)]):
        m.cluster("f", cx, cy, n * 5, seed=10 + i)
    for i, pts in enumerate([[(1, 5), (4, 4)], [(8, 16), (11, 15)], [(21, 6), (25, 7)], [(22, 15), (26, 16)], [(28, 2), (30, 4)], [(10, 20), (13, 21)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=3, colours=(OS, GE, BM), team=(1, 2, 2), objective=[1], hidden=[3], comment=(
        "Gauntlet 09 Silverpine Ford (normal look, no fog, 32 x 22, three armies): the player (army 1, HQ (3,18), the south-west clearing, a free CO) against Hachi (Green Earth, army 2, HQ (26,10), the eastern pines), then Sonja "
        "(Blue Moon, army 3, HQ (6,4), the north-west woods), who comes onto the battlefield when Hachi's line falls. The Silver Pool (x 15..17, y 9..11), the river north and south of it and the west stream; "
        "bridges (15,3) (16,7) (16,13) (15,19) (3,10) (10,11). Com Towers (12,15) (22,5) (9,7). No inventions."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put(".", *HQS["3"])
    for x, y in ((12, 15), (22, 5), (9, 7)):
        m.put("t", x, y)
    # --- roads over the bridges
    route(m, [S(3, 18), S(3, 14), (3, 11), (3, 10, "="), (3, 9), S(5, 6), S(6, 4)], seed=1, wander=0.5)
    route(m, [S(3, 18), S(9, 18), S(13, 19), (14, 19), (15, 19, "="), (16, 19), S(19, 19), S(24, 15), S(26, 10)], seed=2, wander=0.5)
    route(m, [S(9, 16), S(10, 13), (10, 12), (10, 11, "="), (10, 10), S(9, 7), S(6, 4)], seed=3, wander=0.5)
    route(m, [S(6, 4), S(11, 3), (14, 3), (15, 3, "="), (16, 3), S(21, 4), S(26, 10)], seed=4, wander=0.5)
    route(m, [S(9, 7), S(14, 7), (15, 7), (16, 7, "="), (17, 7), S(22, 5)], seed=5, wander=0.4)
    route(m, [S(12, 15), S(14, 13), (15, 13), (16, 13, "="), (17, 13), S(22, 13), S(26, 10)], seed=6, wander=0.5)
    route(m, [S(26, 10), S(28, 15), S(27, 19)], seed=7, wander=0.4)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(3, 18, "BBC"), (7, 20, "BC"), (2, 15, "C"), (8, 18, "BC"), (6, 13, "C"), (12, 19, "c"),
                 (26, 10, "BBBC"), (23, 12, "BC"), (29, 8, "CA"), (24, 7, "BC"), (21, 15, "C"), (28, 16, "CB"), (30, 12, "C"), (22, 19, "C"), (19, 6, "c"), (29, 2, "c"),
                 (6, 4, "bbbc"), (3, 3, "c"), (10, 3, "bc"), (9, 8, "b"), (2, 7, "c"), (13, 5, "c"), (12, 15, "b")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 9)
    prune_road_stubs(m)
    for y in range(13, 22):
        for x in range(0, 14):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 14, 12, 21), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 1, BCO: 1}, (1, 14, 12, 21), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 6, MECH: 3, TANK: 4, MDT: 3, ART: 2, ROCK: 1, RECON: 2, AA: 2, APC: 1}, (19, 4, 31, 16), seed=3, gap=0, avoid=av)
    m.spread(2, {BCO: 1, FTR: 1}, (19, 4, 31, 16), seed=4, gap=1, avoid=av)
    for k, t in {"1": "the player's HQ", "2": "Hachi's HQ (Green Earth): the first line, on the field from the start", "3": "Sonja's HQ (Blue Moon, hidden until Hachi falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
