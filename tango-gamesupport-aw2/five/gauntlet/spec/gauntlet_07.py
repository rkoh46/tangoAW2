"""Gauntlet 07, Chrome Meridian (docs/dev/gauntlet.md): a Black Hole line and then the Silver Nova corps inside one walled citadel, four lines, 38 x 26 = 988 cells, five armies (the player is army 5). Every Silver
Nova line wears the skin (docs/dev/army-packs.md) on one host colour (Yellow Comet's: armies 2, 3 and 4 share it, only their slots differ); the Black Hole line keeps Black Hole's colour and the player may wear neither, nor the skin.
  1. Flak (Black Hole, army 1) holds the centre-west from the start: cheap bulk, a reckless advance.
  2. Caulder (Silver Nova, army 2) arrives in the citadel's north ward when Flak falls: the corps' siege engines behind the wall.
  3. Lili (Silver Nova, army 3) arrives in the middle ward when Caulder falls: fast armour and copters.
  4. Tabitha (Silver Nova, army 4) arrives in the south ward when Lili falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): the Meridian, a river that runs from the north edge to the south edge with a bend at each third (x 19, then x 20, then x 19), divides the west (the player's camp and Flak's depot) from
the **citadel**, a walled ring of mountains on the east edge (x 24..37, y 0..25: the wall is two cells thick on every side, the map's edge is part of it). Inside it three wards (y 2..7, 10..15, 18..23) are
separated by inner walls (y 8..9 and 16..17); the Silver Nova HQs and their bases stand inside, one to a ward. Gates: the west wall has a gate in each ward ((24..25, 4..5), (24..25, 12..13), (24..25, 20..21): two cells
wide, reached from the river's bridges (19,3) (19,6) (20,10) (20,15) (19,21) by the road along the wall), and the inner walls have a gate each ((29..30, 8..9) and (31..32, 16..17)) so a line that falls leaves the next ward open.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads, prune_road_stubs

W, H = 38, 26
# the HQs: army 1 Flak, 2 Caulder, 3 Lili, 4 Tabitha, 5 the player
HQS = {"1": (11, 14), "2": (30, 5), "3": (30, 12), "4": (30, 20), "5": (4, 22)}
BR = [(19, 3), (19, 6), (20, 10), (20, 15), (19, 21)]


def build():
    m = Canvas("gauntlet_07", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the Meridian
    m.river([(19, 0), (19, 8), (20, 8), (20, 17), (19, 17), (19, 25)])
    for x, y in BR:
        m.put("=", x, y)
    # --- the citadel: a ring of mountains two cells thick on the east side (x 24..37, y 0..25), three wards inside, a gate in the west wall for each ward and one in each inner wall
    m.rect("^", 24, 0, 37, 25); m.rect(".", 26, 2, 35, 23)
    m.rect("^", 26, 8, 35, 9); m.rect("^", 26, 16, 35, 17)
    m.rect(".", 24, 4, 25, 5); m.rect(".", 24, 12, 25, 13); m.rect(".", 24, 20, 25, 21)       # (the west wall's gates)
    m.rect(".", 29, 8, 30, 9); m.rect(".", 31, 16, 32, 17)                                    # (the inner walls' gates)
    m.puts(".", [(36, y) for y in (3, 7, 11, 14, 19, 22)] + [(x, 1) for x in (28, 32)] + [(x, 24) for x in (27, 33)])      # (the wall is ragged, not a drawn line)
    m.puts("f", [(27, 3), (34, 3), (27, 6), (34, 6), (27, 11), (34, 14), (27, 19), (34, 22), (28, 22)])
    # --- woods and ridges outside the wall (the citadel's inside stays open ground for the wards)
    for i, (cx, cy, n) in enumerate([(15, 11, 3), (7, 12, 2), (14, 19, 3), (8, 18, 3), (15, 4, 3), (22, 8, 1), (22, 18, 1), (2, 15, 2), (17, 15, 2), (6, 5, 3), (11, 6, 2), (10, 23, 2), (22, 23, 1), (22, 1, 1)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(1, 12), (5, 11)], [(14, 22), (17, 24)], [(2, 2), (6, 1)], [(8, 8), (10, 9)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=5, colours=(BH, YC, YC, YC, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 17, 12, 25)], hidden=[2, 3, 4], comment=(
        "Gauntlet 07 Chrome Meridian (normal look, no fog, 38 x 26, five armies): the player (army 5, HQ 5 (4,22), south-west, a free CO) against Flak (Black Hole, army 1, HQ (11,14), the centre-west), then the Silver Nova "
        "corps inside the east citadel: Caulder (army 2, HQ (30,5), the north ward), Lili (army 3, HQ (30,12), the middle ward) and Tabitha (army 4, HQ (30,20), the south ward), who come onto the battlefield in turn. The three Silver Nova "
        "lines wear the skin on Yellow Comet's colour (armies 2..4 share it). The Meridian (x 19..20) has bridges (19,3) (19,6) (20,10) (20,15) (19,21). Com Towers (16,10) (33,12) (22,19). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((16, 10), (33, 12), (22, 19)):
        m.put("t", x, y)
    # --- roads: the player to Flak and to the citadel's gates, the bridges joined by the road along the wall (x 23), a road inside each ward and through the inner gates
    route(m, [S(4, 22), S(5, 17), S(8, 15), S(11, 14)], seed=1, wander=0.5)
    route(m, [S(4, 22), S(10, 22), S(16, 21), (18, 21), (19, 21, "="), (20, 21), S(23, 20), (24, 20), (25, 20), S(28, 20), S(30, 20)], seed=2, wander=0.5)
    route(m, [S(11, 14), S(15, 12), (19, 10), (20, 10, "="), (21, 10), S(23, 12), (24, 12), (25, 12), S(28, 12), S(30, 12)], seed=3, wander=0.5)
    route(m, [S(11, 14), S(15, 16), (19, 15), (20, 15, "="), (21, 15), S(23, 17), S(23, 20)], seed=4, wander=0.5)
    route(m, [S(11, 14), S(10, 9), S(12, 6), S(16, 6), (18, 6), (19, 6, "="), (20, 6), S(23, 6), S(23, 4)], seed=5, wander=0.4)
    route(m, [S(16, 6), (18, 3), (19, 3, "="), (20, 3), S(23, 3), S(23, 4)], seed=6, wander=0.4)
    route(m, [S(23, 4), S(23, 12), S(23, 20)], seed=7, wander=0.3)
    route(m, [S(23, 4), (24, 4), (25, 4), S(28, 4), S(30, 5)], seed=8, wander=0.3)
    route(m, [S(30, 5), S(30, 7), (30, 8), (30, 9), S(30, 10), S(30, 12)], seed=9, wander=0.2)
    route(m, [S(30, 12), S(31, 15), (31, 16), (31, 17), S(31, 18), S(30, 20)], seed=10, wander=0.2)
    thin_roads(m); fix_rungs(m); clean_river_roads(m)
    for args in [(4, 22, "BBC"), (8, 23, "BC"), (2, 19, "C"), (9, 19, "BC"), (6, 14, "C"), (14, 24, "C"),
                 (11, 14, "BBBC"), (14, 16, "BC"), (7, 11, "C"), (15, 12, "BC"), (10, 17, "C"),
                 (8, 5, "c"), (12, 6, "b"), (5, 8, "c"), (16, 3, "c"), (16, 7, "b"), (3, 4, "ca"),
                 (22, 6, "b"), (22, 12, "c"), (22, 17, "b"), (22, 22, "c"),
                 (30, 5, "bbbc"), (28, 3, "bc"), (33, 4, "ca"), (28, 7, "c"), (34, 7, "c"),
                 (30, 12, "bbbc"), (27, 11, "bc"), (33, 13, "ca"), (28, 14, "c"), (34, 10, "c"),
                 (30, 20, "bbac"), (28, 22, "bc"), (34, 21, "c"), (27, 18, "c"), (34, 18, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
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
