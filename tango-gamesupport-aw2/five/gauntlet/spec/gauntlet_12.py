"""Gauntlet 12, Last Eclipse (docs/dev/gauntlet.md): a Black Hole stronghold on blasted ground (the Wasteland look, `MissionDef::look` 3), four lines, 44 x 26 = 1144 cells, five armies (the player is army 5). Sturm, Von Bolt and Asuka
are Black Hole (three armies of Black Hole's colour, the same HQ look; only the slots differ); Aria is Orange Star's. The player (a free CO) may wear neither colour. The lines, in order:
  1. Sturm (Black Hole, army 1) holds the outer works east of the player's field from the start: cheap tanks and infantry behind the first pipe wall.
  2. Von Bolt (Black Hole, army 2) arrives in the north chamber when Sturm falls: armour, missiles and a Neo Tank.
  3. Aria (Orange Star, army 3) arrives in the south chamber, a captured Orange Star camp inside the fortress, when Von Bolt falls: tangoAW2's own CO, fast tanks and artillery.
  4. Asuka (Black Hole, army 4) arrives in the Eclipse Citadel at the far east end when Aria falls; her HQ is the last: taking it (or routing her) wins.
Black Hole's minicannons guard the seams (inventions, as Asuka's Keep has them).

Design (docs/dev/map-design.md): blasted ground (plains and rock, almost no wood) cut into sealed chambers by pipe walls. Three pipe walls run from the north edge to the south edge (x 13, 24 and 34); a fourth, short wall (y 13, x 26..32,
rock at each end) divides the chambers between x 25 and 33. **No wall has an open gate: every way through is a pipe seam**, a breakable plasma gap: the seam (13,12) leads from the player's field into Sturm's works (x 14..23), the seam
(24,5) from the works into Von Bolt's north chamber (x 25..33, y 0..12), the seam (29,13) from there into Aria's south chamber (x 25..33, y 14..25), and the seams (34,19) and (34,6) from the chambers into the Eclipse Citadel (x 35..43, y 4..21), Asuka's yard,
walled by pipes on three sides (wall C, and pipe walls at y 3 and 22) and the map's edge on the fourth. Minicannons stand behind the seams of walls A, B, D and C and fire down the lane in front of each. Each chamber has its own HQ, bases and cities, roads between them and rubble.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, town, thin_roads, neutralize, prune_road_stubs, snap

W, H = 44, 26
# the HQs: army 1 Sturm, 2 Von Bolt, 3 Aria, 4 Asuka, 5 the player
HQS = {"1": (19, 13), "2": (29, 6), "3": (29, 20), "4": (39, 13), "5": (3, 13)}
SEAMS = [(13, 12), (24, 5), (29, 13), (34, 19), (34, 6)]


def build():
    m = Canvas("gauntlet_12", W, H, campaign="gauntlet")
    # --- blasted ground: rough rock clusters over the whole map and a belt of rock on the north and south edges of every chamber
    for i, (cx, cy, n) in enumerate([(4, 4, 4), (8, 8, 3), (3, 19, 4), (9, 22, 3), (6, 15, 2), (1, 9, 2), (16, 4, 4), (21, 8, 3), (16, 21, 4), (21, 18, 3), (18, 11, 2), (21, 15, 2),
                                    (27, 3, 3), (31, 9, 3), (26, 10, 2), (27, 22, 3), (31, 17, 3), (26, 16, 2), (37, 3, 4), (41, 9, 3), (37, 22, 4), (41, 17, 3), (36, 11, 2), (40, 15, 2)]):
        m.cluster("^", cx, cy, n * 3, seed=10 + i)
    m.scatter("^", (0, 0, W - 1, H - 1), 0.10, seed=77)
    for x0, x1 in ((0, 12), (14, 23), (25, 33), (35, 43)):
        m.scatter("^", (x0, 0, x1, 1), 0.5, seed=x0); m.scatter("^", (x0, 24, x1, 25), 0.5, seed=x0 + 1)
    # --- the pipe walls (each from the north edge to the south edge), the chambers' short wall (rock at both ends) and the seams
    for x in (13, 24, 34):
        m.rect("I", x, 0, x, H - 1)
    m.rect("I", 26, 13, 32, 13)
    m.put("^", 25, 13).put("^", 33, 13)
    for x, y in SEAMS:
        m.put("Z", x, y)
    # --- the Eclipse Citadel: Asuka's yard (x 35..43, y 4..21) closed by the pipe wall on its west, pipe walls on its north and south (y 3 and 22, rock where they meet wall C) and the map's east edge; rock outside them
    m.rect("^", 35, 0, 43, 2); m.rect("^", 35, 23, 43, 25)
    m.rect("I", 36, 3, 43, 3); m.rect("I", 36, 22, 43, 22)
    m.put("^", 35, 3).put("^", 35, 22)
    m.rect(".", 35, 4, 43, 21, only="^")
    for i, (cx, cy, n) in enumerate([(38, 7, 3), (41, 17, 3), (37, 12, 2), (42, 8, 2), (37, 18, 2)]):
        m.cluster("^", cx, cy, n * 3, seed=40 + i)
    m.header(armies=5, colours=(BH, BH, OS, BH, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 11, 8, 25)], hidden=[2, 3, 4], blackhole=True, comment=(
        "Gauntlet 12 Last Eclipse (Wasteland look, no fog, 44 x 26, five armies): the player (army 5, HQ 5 (3,13), the west field, a free CO) against Sturm (Black Hole, army 1, HQ (19,13), the outer works), then Von Bolt (Black Hole, "
        "army 2, HQ (29,6), the north chamber), Aria (Orange Star, army 3, HQ (29,20), the south chamber) and Asuka (Black Hole, army 4, HQ (39,13), the Eclipse Citadel), who come onto the battlefield in turn. Sturm, Von Bolt and Asuka "
        "share Black Hole's colour. Pipe walls x 13, 24, 34 and y 13 (x 26..32); the only gates are the seams (13,12) (24,5) (29,13) (34,19) (34,6). Minicannons behind the seams. Com Towers (21,7) (28,9) (28,17). No other inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((21, 7), (28, 9), (28, 17)):
        m.put("t", x, y)
    # --- Black Hole's minicannons: each fires four cells down the lane behind a seam (W: left, N: up, S: down)
    for x, y in ((17, 12), (28, 5), (29, 16), (38, 19)):
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if m.g[y + dy][x + dx] in "^f":
                    m.g[y + dy][x + dx] = "."
    m.put("W", 17, 12).put("W", 28, 5).put("N", 29, 16).put("W", 38, 19)
    S = lambda x, y: snap(m, x, y)
    # --- the camps: a base and cities by each seam so the roads that reach it end at a property
    for x, y, c in ((12, 11, "C"), (22, 4, "C"), (22, 6, "C"), (26, 4, "c"), (26, 6, "c"), (30, 12, "c"), (30, 14, "c"), (35, 19, "c"), (35, 18, "c"), (33, 19, "c")):
        m.put(c, x, y)
    # --- roads inside the chambers: every road runs between properties
    route(m, [S(3, 13), S(8, 12), S(12, 12)], seed=1, wander=0.4)
    route(m, [S(19, 13), S(21, 10), S(22, 5)], seed=2, wander=0.4)
    route(m, [S(19, 13), S(17, 12), S(14, 11)], seed=3, wander=0.3)
    route(m, [S(19, 13), S(21, 20), S(16, 21)], seed=4, wander=0.5)
    route(m, [S(29, 6), S(26, 5), S(26, 4)], seed=5, wander=0.3)
    route(m, [S(29, 6), S(30, 9), S(30, 12)], seed=6, wander=0.4)
    route(m, [S(29, 20), S(30, 16), S(30, 14)], seed=7, wander=0.4)
    route(m, [S(29, 20), S(32, 19), S(33, 19)], seed=8, wander=0.3)
    route(m, [S(39, 13), S(37, 16), S(35, 18)], seed=9, wander=0.4)
    route(m, [S(39, 13), S(40, 9), S(42, 5)], seed=10, wander=0.5)
    thin_roads(m)
    for args in [(3, 13, "BBC"), (6, 15, "BC"), (2, 10, "C"), (6, 10, "C"), (7, 17, "C"), (4, 20, "c"), (4, 6, "c"),
                 (19, 13, "BBBC"), (21, 11, "BC"), (17, 16, "BC"), (16, 9, "C"), (21, 17, "C"), (16, 5, "c"), (20, 22, "c"), (15, 13, "b"),
                 (29, 6, "bbbc"), (27, 8, "bc"), (31, 3, "cb"), (31, 10, "c"), (27, 2, "c"),
                 (29, 20, "bbbc"), (27, 18, "bc"), (31, 23, "cb"), (31, 17, "c"), (27, 22, "c"), (30, 18, "b"),
                 (39, 13, "bbbc"), (39, 10, "bc"), (41, 16, "bc"), (37, 16, "c"), (38, 5, "c"), (40, 20, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
    for x, y in ((17, 12), (28, 5), (29, 16), (38, 19)):          # (nothing joins a minicannon's tile but plain ground)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if m.g[y + dy][x + dx] in "BCAPTbcaptR":
                m.g[y + dy][x + dx] = "."
    prune_road_stubs(m)
    for y in range(0, 26):
        for x in range(0, 13):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcptSNWELvn"
    m.spread(5, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 8, 6, 18), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 1, BCO: 1}, (1, 8, 6, 18), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 6, MECH: 3, TANK: 5, MDT: 2, ART: 3, ROCK: 1, AA: 2, APC: 1}, (17, 3, 23, 22), seed=3, gap=0, avoid=av)
    m.spread(1, {BCO: 1, FTR: 1, RECON: 1}, (18, 3, 23, 22), seed=4, gap=1, avoid=av)
    n = clear_fire_lines(m)
    for k, t in {"1": "Sturm's HQ (Black Hole): the first line, on the field from the start", "2": "Von Bolt's HQ (Black Hole, hidden until Sturm falls)", "3": "Aria's HQ (Orange Star, hidden until Von Bolt falls)",
                 "4": "Asuka's HQ (Black Hole, hidden until Aria falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
