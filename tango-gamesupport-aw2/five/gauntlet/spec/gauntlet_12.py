"""Gauntlet 12, Last Eclipse (docs/dev/gauntlet.md): a Black Hole stronghold, four lines, 40 x 26 = 1040 cells, five armies (the player is army 5). Sturm, Von Bolt and Asuka are Black Hole (three armies of Black Hole's colour,
the same HQ look; only the slots differ); Aria is Orange Star's. The player (a free CO) may wear neither colour. The lines, in order:
  1. Sturm (Black Hole, army 1) holds the outer works east of the player's field from the start: cheap tanks and infantry behind the first pipe wall.
  2. Von Bolt (Black Hole, army 2) arrives in the north chamber when Sturm falls: armour, missiles and a Neo Tank.
  3. Aria (Orange Star, army 3) arrives in the south chamber when Von Bolt falls: tangoAW2's own CO, her line of fast tanks and artillery.
  4. Asuka (Black Hole, army 4) arrives in the Eclipse Citadel at the far east end when Aria falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions: the fortress is its pipes.

Design (docs/dev/map-design.md): the stronghold is a row of chambers cut off by three pipe walls that run from the north edge to the south edge (x 9, 19 and 29). Each wall has gates (3 cells wide) at its own place so the way zigzags: the
player's field to Sturm's works by the gate in the middle (9, 11..12), from the works to the north chamber (19, 3..4) and the south chamber (19, 21..22), between the chambers by the gate in their dividing pipe wall (24, 12),
and out to the lane in front of the citadel (x 30) by the gates (29, 5..6) and (29, 19..20); the lane leads to the Citadel's west gate (31..32, 12..14), a walled ring of rock round Asuka's yard (x 33..38, y 8..18). Com Towers in the north and south chambers and in the works.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import town, thin_roads, neutralize, prune_road_stubs

W, H = 40, 26
# the HQs: army 1 Sturm, 2 Von Bolt, 3 Aria, 4 Asuka, 5 the player
HQS = {"1": (14, 14), "2": (24, 5), "3": (24, 20), "4": (35, 13), "5": (3, 13)}


def build():
    m = Canvas("gauntlet_12", W, H, campaign="gauntlet")
    rnd = random.Random("gauntlet_12/rubble")
    # --- rock rims on the map's edge rows and columns far from the walls, and rubble in every chamber
    for x0, y0, x1, y1 in ((0, 0, 8, 1), (0, 24, 8, 25), (10, 0, 18, 1), (10, 24, 18, 25), (20, 0, 28, 1), (20, 24, 28, 25), (30, 0, 39, 1), (30, 24, 39, 25)):
        m.scatter("^", (x0, y0, x1, y1), 0.55, seed=x0 + 7 * y0)
    for i, (cx, cy, n) in enumerate([(5, 5, 3), (5, 21, 3), (2, 9, 2), (2, 17, 2), (13, 8, 3), (6, 12, 2), (11, 12, 2), (17, 12, 2), (16, 18, 3), (12, 20, 2), (22, 8, 2), (27, 9, 2), (22, 17, 2), (27, 22, 2), (33, 3, 3), (36, 22, 3), (31, 3, 1), (31, 22, 1)]):
        m.cluster("f" if i % 3 == 0 else "^", cx, cy, n * 3, seed=10 + i)
    # --- the pipe walls (each from the north edge to the south edge) and the chambers' dividing wall
    for x in (9, 19, 29):
        m.rect("I", x, 0, x, H - 1)
    m.rect("I", 21, 12, 27, 12)
    m.put("^", 20, 12).put("^", 28, 12)                                      # (the dividing wall stops at a rock at each end)
    # gates: three cells wide, the wall resumes on the far side
    m.rect(".", 9, 11, 9, 12).rect(".", 19, 3, 19, 4).rect(".", 19, 21, 19, 22).rect(".", 29, 5, 29, 6).rect(".", 29, 19, 29, 20).put(".", 24, 12)
    # --- the Eclipse Citadel: a ring of rock (x 31..39, y 6..20) round Asuka's yard (x 33..38, y 8..18), a west gate (31..32, 12..14)
    m.rect("^", 31, 6, 39, 20); m.rect(".", 33, 8, 38, 18); m.rect(".", 31, 12, 32, 14)
    m.puts(".", [(36, 6), (34, 20), (39, 11), (39, 16), (31, 9), (31, 17)])
    m.puts("f", [(34, 9), (37, 9), (34, 17), (37, 17)])
    m.header(armies=5, colours=(BH, BH, OS, BH, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 8, 8, 25)], hidden=[2, 3, 4], comment=(
        "Gauntlet 12 Last Eclipse (normal look, no fog, 40 x 26, five armies): the player (army 5, HQ 5 (3,13), the west field, a free CO) against Sturm (Black Hole, army 1, HQ (14,14), the outer works), then Von Bolt (Black Hole, "
        "army 2, HQ (24,5), the north chamber), Aria (Orange Star, army 3, HQ (24,20), the south chamber) and Asuka (Black Hole, army 4, HQ (35,13), the Eclipse Citadel), who come onto the battlefield in turn. Sturm, Von Bolt and Asuka "
        "share Black Hole's colour. Pipe walls x 9, 19, 29 (gates (9,11..13) (19,3..5) (19,20..22) (29,5..7) (29,18..20)), the chambers' wall y 12 (gate x 24). Com Towers (14,8) (24,9) (24,16). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((14, 8), (24, 9), (24, 16)):
        m.put("t", x, y)
    # --- roads through the gates
    R = lambda pts: m.line("R", pts, over=".f^R")
    R([(3, 13), (3, 12), (14, 12), (14, 14)])
    R([(14, 12), (14, 4), (19, 4), (24, 4), (24, 5)])
    R([(14, 14), (14, 21), (19, 21), (24, 21), (24, 20)])
    R([(25, 6), (25, 19)]); R([(24, 5), (25, 5), (25, 6)]); R([(24, 20), (25, 20), (25, 19)])
    R([(25, 6), (30, 6)]); R([(25, 19), (30, 19)]); R([(30, 6), (30, 19)]); R([(30, 13), (36, 13)])
    thin_roads(m)
    for args in [(3, 13, "BBC"), (6, 15, "BC"), (2, 10, "C"), (6, 10, "C"), (7, 17, "C"), (4, 20, "c"), (4, 6, "c"),
                 (14, 14, "BBBC"), (12, 10, "BC"), (16, 17, "BC"), (12, 18, "C"), (16, 9, "C"), (15, 4, "c"), (15, 21, "c"),
                 (24, 5, "bbbc"), (22, 7, "bc"), (27, 3, "ca"), (27, 8, "c"), (22, 3, "c"), (27, 10, "b"),
                 (24, 20, "bbbc"), (22, 17, "bc"), (27, 22, "ca"), (27, 16, "c"), (22, 23, "c"), (27, 14, "b"),
                 (35, 13, "bbbc"), (35, 10, "bc"), (37, 16, "ba"), (33, 16, "c"), (34, 3, "c"), (36, 22, "c"), (32, 4, "b"), (32, 22, "b")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
    for y in range(0, 26):
        for x in range(0, 9):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 9, 5, 17), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 1, BCO: 1}, (1, 9, 5, 17), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 6, MECH: 3, TANK: 5, MDT: 2, ART: 3, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (15, 6, 18, 21), seed=3, gap=0, avoid=av)
    m.spread(1, {BCO: 1, FTR: 1}, (15, 6, 18, 21), seed=4, gap=1, avoid=av)
    for k, t in {"1": "Sturm's HQ (Black Hole): the first line, on the field from the start", "2": "Von Bolt's HQ (Black Hole, hidden until Sturm falls)", "3": "Aria's HQ (Orange Star, hidden until Von Bolt falls)",
                 "4": "Asuka's HQ (Black Hole, hidden until Aria falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
