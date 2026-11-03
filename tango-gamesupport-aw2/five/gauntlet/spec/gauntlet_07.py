"""Gauntlet 07, Chrome Meridian (docs/dev/gauntlet.md): a Black Hole line and then the Silver Nova corps, four lines, 38 x 26 = 988 cells, five armies (the player is army 5). Every Silver Nova line wears the
skin (docs/dev/army-packs.md) on one host colour (Yellow Comet's: armies 2, 3 and 4 share it, only their slots differ); the Black Hole line keeps Black Hole's colour and the player may wear neither, nor the skin.
  1. Flak (Black Hole, army 1) holds the centre-west from the start: cheap bulk, a reckless advance.
  2. Caulder (Silver Nova, army 2) arrives in the north-west citadel when Flak falls: the corps' siege engines behind a ring of orb towers.
  3. Lili (Silver Nova, army 3) arrives in the north-east when Caulder falls: fast armour and copters across the Meridian.
  4. Tabitha (Silver Nova, army 4) arrives in the south-east when Lili falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): the Meridian, a river that runs from the north edge to the south edge with a bend at each third (x 19, then x 20, then x 19), divides west from east; five bridges (19,3) (19,6) (20,10)
(20,15) (19,21). West of it the player's camp, Flak's depot and the north-west citadel (a ring of mountains with two gates); east of it the open chrome plains, a long road from the north-east to the
south-east and the Com Towers that the corps fights for. The order crosses the Meridian twice: north-west (Caulder), north-east over it (Lili), south-east (Tabitha).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads

W, H = 38, 26
# the HQs: army 1 Flak, 2 Caulder, 3 Lili, 4 Tabitha, 5 the player
HQS = {"1": (11, 14), "2": (7, 5), "3": (31, 5), "4": (32, 20), "5": (4, 22)}
BR = [(19, 3), (19, 6), (20, 10), (20, 15), (19, 21)]


def build():
    m = Canvas("gauntlet_07", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the Meridian
    m.river([(19, 0), (19, 8), (20, 8), (20, 17), (19, 17), (19, 25)])
    for x, y in BR:
        m.put("=", x, y)
    # --- the north-west citadel: a ring of mountains (x 2..13, y 1..9) with two gates (east (13,5) and south (7,9))
    m.rect("^", 2, 1, 13, 9); m.rect(".", 3, 2, 12, 8)
    m.put(".", 13, 5).put(".", 13, 4).put(".", 7, 9).put(".", 8, 9)
    m.puts("f", [(4, 3), (11, 3), (5, 7), (11, 7)])
    m.ragged("^", longest=8, seed=1)
    # --- woods and ridges elsewhere
    for i, (cx, cy, n) in enumerate([(15, 11, 3), (7, 12, 2), (14, 19, 3), (8, 18, 3), (24, 8, 3), (35, 9, 3), (27, 14, 3), (24, 21, 3), (36, 14, 3), (29, 23, 3), (15, 4, 2), (25, 3, 2), (2, 15, 2), (30, 10, 2), (22, 4, 2), (17, 15, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(1, 12), (5, 11)], [(23, 11), (27, 12)], [(30, 15), (35, 16)], [(22, 18), (26, 17)], [(15, 22), (17, 24)], [(33, 1), (36, 3)], [(24, 24), (28, 25)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=5, colours=(BH, YC, YC, YC, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 17, 12, 25)], hidden=[2, 3, 4], comment=(
        "Gauntlet 07 Chrome Meridian (normal look, no fog, 38 x 26, five armies): the player (army 5, HQ 5 (4,22), south-west, a free CO) against Flak (Black Hole, army 1, HQ (11,14), the centre-west), then the Silver Nova "
        "corps: Caulder (army 2, HQ (7,5), the north-west citadel), Lili (army 3, HQ (31,5), the north-east) and Tabitha (army 4, HQ (32,20), the south-east), who come onto the battlefield in turn. The three Silver Nova "
        "lines wear the skin on Yellow Comet's colour (armies 2..4 share it). The Meridian (x 19..20) has bridges (19,3) (19,6) (20,10) (20,15) (19,21). Com Towers (16,10) (25,12) (26,19). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((16, 10), (25, 12), (26, 19)):
        m.put("t", x, y)
    # --- roads
    route(m, [S(4, 22), S(5, 17), S(8, 15), S(11, 14)], seed=1, wander=0.5)
    route(m, [S(4, 22), S(10, 22), S(16, 21), (18, 21), (19, 21, "="), (20, 21), S(26, 20), S(32, 20)], seed=2, wander=0.5)
    route(m, [S(11, 14), S(15, 12), (19, 10), (20, 10, "="), (21, 10), S(25, 12), S(31, 5)], seed=3, wander=0.5)
    route(m, [S(11, 14), S(15, 16), (19, 15), (20, 15, "="), (21, 15), S(26, 17), S(32, 20)], seed=4, wander=0.5)
    route(m, [S(11, 14), S(10, 9), S(8, 7), S(7, 5)], seed=5, wander=0.4)
    route(m, [S(7, 5), S(13, 5), S(16, 6), (18, 6), (19, 6, "="), (20, 6), S(25, 5), S(31, 5)], seed=6, wander=0.4)
    route(m, [S(16, 6), (18, 3), (19, 3, "="), (20, 3), S(24, 2)], seed=7, wander=0.4)
    route(m, [S(31, 5), S(33, 12), S(33, 17), S(32, 20)], seed=8, wander=0.5)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(4, 22, "BBC"), (8, 23, "BC"), (2, 19, "C"), (9, 19, "BC"), (6, 14, "C"), (14, 24, "C"),
                 (11, 14, "BBBC"), (14, 16, "BC"), (7, 11, "C"), (15, 12, "BC"), (10, 17, "C"),
                 (7, 5, "bbbc"), (4, 4, "bc"), (10, 7, "bc"), (11, 3, "ca"), (5, 8, "cb"), (16, 3, "c"), (16, 7, "b"),
                 (31, 5, "bbbc"), (27, 3, "bc"), (35, 3, "ca"), (28, 8, "c"), (35, 7, "bc"), (24, 5, "c"), (33, 12, "c"),
                 (32, 20, "bbac"), (28, 22, "bc"), (35, 23, "ca"), (35, 17, "c"), (29, 16, "bc"), (24, 17, "c"), (22, 23, "c"),
                 (23, 12, "b"), (22, 8, "b"), (16, 19, "b"), (22, 14, "c"), (26, 10, "c"), (37, 11, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    for y in range(17, 26):
        for x in range(0, 15):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 19, 10, 25), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 1, BCO: 1}, (1, 19, 10, 25), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 6, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 2, AA: 2, APC: 1}, (4, 10, 17, 17), seed=3, gap=0, avoid=av)
    m.spread(1, {BCO: 1, FTR: 1}, (4, 10, 17, 17), seed=4, gap=1, avoid=av)
    for k, t in {"1": "Flak's HQ (Black Hole): the first line, on the field from the start", "2": "Caulder's HQ (Silver Nova, hidden until Flak falls)", "3": "Lili's HQ (Silver Nova, hidden until Caulder falls)",
                 "4": "Tabitha's HQ (Silver Nova, hidden until Lili falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
