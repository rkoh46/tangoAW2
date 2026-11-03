"""Gauntlet 05, Granite Spine (docs/dev/gauntlet.md): a highland gauntlet of three lines, 32 x 22, four armies. The player (army 1, a free CO pick) holds the south-west foothills:
  1. Jake (Orange Star, army 2) holds the east slopes from the start: fast offroad troops and a forward base at every pass.
  2. Grimm (Yellow Comet, army 3) arrives on the north-west shelf when Jake falls: heavy tanks and artillery on the high ground above the camp.
  3. Von Bolt (Black Hole, army 4) arrives in the north-east fortress valley when Grimm falls; his HQ is the last: taking it (or routing him) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): a spine of mountains runs north to south through the middle (x 14..17) with three passes (y 4..5, 10..11, 16..17): a road through each, and a base on each side of it, so the
front is three lanes with a mountain between each pair (never walled: each pass is two cells wide and the foothills on both sides are open). A tarn in the north-west shelf and one in the south-east valley keep
the highlands from being a plain with hills on it. The order zigzags over the spine: east (Jake), then back over it to the north-west shelf (Grimm), then the north-east valley (Von Bolt).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads, prune_road_stubs

W, H = 32, 22
HQS = {"1": (3, 18), "2": (28, 12), "3": (6, 4), "4": (27, 4)}


def build():
    m = Canvas("gauntlet_05", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the spine: one unbroken ridge of mountains, 2 to 3 cells wide, from the north edge to the south edge (x 13..17, a wobble of one cell a row), cut by three passes two cells wide
    # (y 4..5, 10..11, 16..17): a wall at a glance, with the roads through its gaps
    import random
    rnd = random.Random("gauntlet_05/ridge")
    x0 = 14
    for y in range(H):
        if y in (4, 5, 10, 11, 16, 17):
            continue
        x0 = max(13, min(15, x0 + rnd.choice((-1, 0, 1))))
        w = 2 + (y % 3 == 0)
        for x in range(x0, x0 + w + 1):
            m.put("^", x, y)
    # the ridge's slopes: forest on both flanks of every stretch
    for y in range(H):
        for x in (11, 12, 18, 19, 20):
            if m.get(x, y) == "." and (y not in (4, 5, 10, 11, 16, 17)) and rnd.random() < 0.55:
                m.put("f", x, y)
    # --- tarns and a creek (the highlands' water): north-west shelf, south-east valley
    m.rect("~", 9, 1, 11, 2)
    m.blob("~", 23, 18, 2, 2, seed=5, wobble=0.3)
    # --- woods and outcrops
    for i, (cx, cy, n) in enumerate([(3, 8, 3), (9, 8, 3), (11, 14, 2), (6, 14, 2), (21, 8, 3), (25, 8, 2), (28, 16, 3), (20, 13, 2), (22, 3, 3), (3, 3, 2), (9, 19, 2), (29, 8, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(1, 12), (6, 12)], [(19, 6), (24, 6)], [(19, 20), (23, 21)], [(25, 14), (29, 14)], [(1, 5), (3, 6)], [(8, 11), (12, 12)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=4, colours=(BM, OS, YC, BH), team=(1, 2, 2, 2), objective=[1], hidden=[3, 4], comment=(
        "Gauntlet 05 Granite Spine (normal look, no fog, 32 x 22, four armies): the player (army 1, HQ (3,18), south-west, a free CO) against Jake (Orange Star, army 2, HQ (28,12), the east slopes), then Grimm "
        "(Yellow Comet, army 3, HQ (6,4), the north-west shelf) and Von Bolt (Black Hole, army 4, HQ (27,4), the north-east valley), who come onto the battlefield in turn. A spine of mountains (x 14..17) has "
        "passes at y 4..5, 10..11, 16..17. Com Towers (12,8) (20,15) (21,6). No inventions."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((12, 8), (20, 15), (21, 6)):
        m.put("t", x, y)
    # --- roads: through each pass, from each HQ
    route(m, [S(3, 18), S(8, 17), (13, 17), (15, 17), (18, 17), S(22, 16), S(26, 14), S(28, 12)], seed=1, wander=0.4)
    route(m, [S(3, 18), S(5, 13), S(10, 11), (13, 11), (15, 11), (18, 11), S(22, 11), S(28, 12)], seed=2, wander=0.4)
    route(m, [S(6, 4), S(10, 5), (13, 5), (15, 5), (18, 5), S(22, 5), S(27, 4)], seed=3, wander=0.4)
    route(m, [S(6, 4), S(5, 9), S(4, 14), S(3, 18)], seed=4, wander=0.5)
    route(m, [S(27, 4), S(26, 8), S(28, 12)], seed=5, wander=0.4)
    route(m, [S(25, 12), S(24, 15), S(23, 16)], seed=6, wander=0.4)
    route(m, [S(10, 11), S(10, 17)], seed=7, wander=0.3)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(3, 18, "BBC"), (7, 20, "BC"), (2, 15, "C"), (8, 15, "BC"), (6, 9, "C"),
                 (28, 12, "BBC"), (30, 9, "C"), (25, 12, "BC"), (28, 15, "AC"), (22, 8, "C"),
                 (6, 4, "bbc"), (2, 4, "c"), (10, 6, "ca"), (4, 8, "cb"), (9, 3, "c"),
                 (27, 4, "bbc"), (30, 2, "c"), (23, 4, "cb"), (30, 6, "ca"), (21, 3, "c"),
                 (12, 5, "b"), (19, 5, "b"), (12, 11, "b"), (19, 11, "b"), (12, 17, "b"), (19, 17, "b"), (11, 8, "c"), (20, 14, "c"), (23, 20, "c"), (12, 20, "c"), (26, 19, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 13, 12, 21), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 1, BCO: 1}, (1, 13, 12, 21), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 6, MECH: 4, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 3, AA: 2, APC: 1}, (19, 7, 30, 18), seed=3, gap=0, avoid=av)
    m.spread(2, {BCO: 2, FTR: 1}, (19, 7, 30, 18), seed=4, gap=1, avoid=av)
    for k, t in {"1": "the player's HQ", "2": "Jake's HQ (Orange Star): the first line, on the field from the start", "3": "Grimm's HQ (Yellow Comet, hidden until Jake falls)", "4": "Von Bolt's HQ (Black Hole, hidden until Grimm falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
