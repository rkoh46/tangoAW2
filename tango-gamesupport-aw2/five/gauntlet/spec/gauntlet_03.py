"""Gauntlet 03, Dustwind Basin (docs/dev/gauntlet.md): a desert gauntlet of two lines on a 30 x 20 map, three armies. The player (army 1, a free CO pick) holds the south-west camp:
  1. Koal (Yellow Comet, army 2) holds the east mesa from the start: highways and fast tanks, a pair of rocket batteries on the rim.
  2. Lash (Black Hole, army 3) arrives in the north-west dunes when Koal falls (his HQ taken or his line routed): artillery, Md Tanks and foot soldiers who live off the broken ground.
No Black Hole inventions.

Design (docs/dev/map-design.md): a dry river (the Wadi, x 14, mouth to mouth from the north edge to the south edge) divides the camp from the east: three bridges (14,5), (15,10), (14,16). West of it the
camp's dunes and the north-west badlands; east of it the open basin and Koal's mesa (a plateau ringed by rock with two ramps). The middle (the bridges) is a Com Tower and two cities to fight over,
a forward base on each bank. The order zigzags: east over the Wadi (Koal), then north-west through the badlands (Lash), so the player must swing the whole army across the map.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads

W, H = 30, 20
HQS = {"1": (3, 16), "2": (25, 10), "3": (6, 3)}
BR = [(14, 5), (15, 10), (14, 16)]      # the Wadi's bridges


def build():
    m = Canvas("gauntlet_03", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the Wadi: a dry river from edge to edge, three bridges
    m.river([(14, 0), (14, 7), (15, 7), (15, 13), (14, 13), (14, 19)])
    for x, y in BR:
        m.put("=", x, y)
    # --- Koal's mesa: a plateau (x 22..28, y 6..14) ringed by rock with two ramps (west (21,10) and south (25,15)), woods inside
    m.rect("^", 21, 6, 28, 15); m.rect(".", 22, 7, 27, 14)
    m.put("f", 28, 10).put(".", 21, 10).put(".", 25, 15).put(".", 21, 9).put(".", 24, 15)
    m.puts("f", [(23, 8), (26, 8), (24, 13), (27, 12)])
    # --- rock outcrops and scrub: the badlands of the north-west, dunes (woods) in the camp, ridges in the basin
    for i, pts in enumerate([[(1, 6), (5, 7)], [(9, 1), (12, 3)], [(2, 10), (4, 12)], [(16, 2), (19, 3)], [(17, 17), (20, 18)], [(10, 11), (12, 13)], [(17, 11), (19, 13)]]):
        belt(m, "^", pts, width=1, seed=10 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(8, 7, 2), (4, 4, 2), (11, 8, 2), (7, 13, 2), (17, 7, 2), (18, 15, 2), (10, 17, 2)]):
        m.cluster("f", cx, cy, n * 2, seed=20 + i)
    for i, (cx, cy, n) in enumerate([(25, 2, 3), (21, 17, 2), (28, 17, 2), (1, 18, 2)]):
        m.cluster("^" if i % 2 == 0 else "f", cx, cy, n * 3, seed=40 + i)
    m.header(armies=3, colours=(OS, YC, BH), team=(1, 2, 2), objective=[1], hidden=[3], comment=(
        "Gauntlet 03 Dustwind Basin (normal look, no fog, 30 x 20, three armies): the player (army 1, HQ (3,16), south-west, a free CO) against Koal (Yellow Comet, army 2, HQ (25,10), the east mesa), then Lash "
        "(Black Hole, army 3, HQ (6,3), the north-west badlands) who comes onto the battlefield when Koal's line falls. The Wadi (x 14) has bridges at (14,5), (15,10), (14,16). Com Tower (13,9). No inventions."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put(".", *HQS["3"])
    m.put("t", 13, 9)
    # --- roads
    route(m, [S(3, 16), S(5, 16), (13, 16), (14, 16, "="), (15, 16), S(19, 14), S(21, 10)], seed=1, wander=0.5)
    route(m, [S(3, 16), S(5, 11), S(10, 10), (14, 10), (15, 10, "="), (16, 10), S(20, 10), S(25, 10)], seed=2, wander=0.5)
    route(m, [S(6, 3), S(10, 5), (13, 5), (14, 5, "="), (15, 5), S(19, 7), S(21, 9)], seed=3, wander=0.5)
    route(m, [S(6, 3), S(5, 8), S(4, 12), S(3, 16)], seed=4, wander=0.6)
    route(m, [S(25, 10), S(25, 15), S(24, 18)], seed=5, wander=0.4)
    route(m, [S(15, 10), S(17, 6), S(21, 4), S(26, 3)], seed=6, wander=0.5)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(3, 16, "BBC"), (6, 17, "C"), (2, 13, "C"), (8, 14, "BC"),
                 (25, 10, "BBC"), (23, 12, "C"), (27, 8, "C"), (25, 17, "AC"), (19, 17, "C"),
                 (6, 3, "bbc"), (3, 5, "c"), (9, 5, "ca"), (4, 8, "c"), (9, 9, "cb"),
                 (12, 14, "b"), (16, 14, "b"), (12, 6, "c"), (16, 6, "c"), (18, 10, "c"), (11, 11, "c"), (22, 3, "c"), (20, 6, "c"), (7, 18, "c"), (26, 3, "ca")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 12, 9, 19), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 1, BCO: 1}, (1, 12, 9, 19), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 5, MECH: 2, TANK: 5, MDT: 2, ART: 2, ROCK: 2, RECON: 3, AA: 1}, (22, 7, 27, 14), seed=3, gap=0, avoid=av)
    m.spread(2, {BCO: 1}, (17, 5, 26, 12), seed=4, gap=1, avoid=av)
    for k, t in {"1": "the player's HQ", "2": "Koal's HQ (Yellow Comet): the first line, on the field from the start", "3": "Lash's HQ (Black Hole, hidden until Koal falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
