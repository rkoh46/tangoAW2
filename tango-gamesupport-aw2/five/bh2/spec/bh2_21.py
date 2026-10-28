"""BH2 M21 The Second Folder (Act V): Black Hole's eastern HQ, in the snow. Asuka + Hawke (the forced tag pair) against one Orange Star army under Max + Sami. Snow look, clear weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge with two frozen lakes in the middle, side by side, with an isthmus between them (the third Com Tower is its heart): no coast at all. The situation: Black Hole's eastern HQ is a fortress on the lake's east shore (HQ, a base district, a port on the east lake and the
Com Tower with the folder's papers); Max and Sami hold the west shore (HQ, bases, a port of their own). The lake holds the fleets (a Cruiser and a Submarine each) and two highways run round it, the north one under a range, the south one through woods.
- Lanes: the north highway under the range, the south highway, the lakes for the ships each army may build.
- Where the fight happens: the isthmus and the Com Towers (14,6) and (28,21), then the shores.
- Properties: a village at every bend of the highways, the two HQ districts, a port on each shore of the lake, a missile silo north of the lake.
- Threats and answers: Max's Tanks and Sami's foot soldiers -> Md Tanks and artillery on the shore; each army has a lake of its own to build ships on (the two lakes meet only at the isthmus); Orange Star fields no air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 42, 28


def build():
    m = Canvas("bh2_21", W, H)
    # --- the frozen lake in the middle: two lobes joined by a neck (a bridge crosses it)
    m.blob("~", 14, 14, 6, 5, seed=1, wobble=0.25); m.blob("~", 28, 13, 6, 4, seed=2, wobble=0.25)
    m.rect("~", 18, 12, 24, 14)
    for (x, y) in [(21, 12), (21, 13), (21, 14)]:
        m.g[y][x] = "~"
    S = lambda x, y: snap(m, x, y)
    for i, (cx, cy, n, ch) in enumerate([(16, 24, 4, "f"), (22, 25, 4, "f"), (30, 4, 4, "f"), (5, 3, 4, "f"), (38, 9, 3, "^"), (3, 21, 3, "^"), (24, 4, 3, "^"), (12, 24, 3, "^"), (33, 16, 4, "f"), (9, 17, 3, "f"), (31, 11, 3, "^"), (11, 10, 3, "^"), (36, 26, 3, "^"), (20, 3, 3, "^"), (26, 25, 3, "^"), (3, 25, 3, "^"), (28, 9, 3, "^"), (12, 17, 3, "f"), (30, 17, 3, "f"), (8, 8, 4, "f"), (34, 22, 4, "f"), (8, 22, 4, "^"), (34, 6, 4, "^"), (24, 8, 3, "f"), (18, 21, 3, "^"), (3, 11, 3, "^"), (39, 18, 3, "f"), (12, 3, 3, "f"), (30, 25, 3, "f"), (6, 6, 3, "^"), (37, 24, 3, "^"), (17, 6, 3, "^"), (25, 22, 3, "^")]):
        m.cluster(ch, cx, cy, n * 3, seed=70 + i)
    belt(m, "^", [(3, 4), (10, 3), (18, 4), (26, 3), (36, 4)], width=1, seed=1, gaps=[(7, 3), (14, 4), (17, 4), (22, 4), (31, 3)], p=0.7); belt(m, "^", [(5, 24), (13, 25), (22, 24), (31, 25), (38, 24)], width=1, seed=2, gaps=[(9, 25), (17, 24), (26, 25), (35, 24)])
    belt(m, "f", [(2, 9), (6, 10)], width=1, seed=3); belt(m, "f", [(2, 18), (6, 17)], width=1, seed=4); belt(m, "f", [(35, 9), (39, 10)], width=1, seed=5); belt(m, "f", [(35, 18), (39, 17)], width=1, seed=6)
    belt(m, "f", [(10, 21), (16, 22)], width=2, seed=7); belt(m, "f", [(24, 21), (30, 22)], width=2, seed=8); belt(m, "f", [(10, 7), (14, 8)], width=1, seed=9); belt(m, "f", [(28, 6), (32, 7)], width=1, seed=10)
    belt(m, "^", [(1, 13), (3, 16)], width=1, seed=11); belt(m, "^", [(38, 12), (40, 15)], width=1, seed=12)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M21 The Second Folder (snow look, clear): Asuka + Hawke (forced pair, Black Hole, HQ 1 (35,14), the lake's east shore) against one Orange Star army under Max + Sami (HQ 2 (6,14), the west shore). Two frozen lakes with the isthmus (x 19..23) between. "
        "Com Towers (14,6) and (28,21), missile silo (21,5); the isthmus's Com Tower (21,13). Player: INF4 MECH2 TANK5 MDT3 ART3 ROCK1 RECON1; Orange Star: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1."))
    m.put("1", 35, 14).put("2", 6, 14).put("t", 14, 6).put("t", 28, 21).put("M", 21, 5)
    m.rect(".", 20, 13, 22, 13); m.put("t", 21, 13)                              # the isthmus's Com Tower
    PORTS = [snap_coast(m, 30, 12), snap_coast(m, 12, 15), snap_coast(m, 33, 17), snap_coast(m, 10, 10)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    route(m, [S(35, 13), S(32, 8), S(26, 6), S(20, 7), S(14, 8), S(8, 12), S(6, 13)], seed=1, wander=1.1)
    route(m, [S(35, 15), S(31, 19), S(26, 21), S(20, 20), S(14, 20), S(9, 17), S(6, 15)], seed=2, wander=1.1)
    route(m, [S(20, 8), (21, 9)], seed=3) if False else None
    route(m, [S(21, 8), S(21, 10)], seed=4) if False else None
    route(m, [S(PORTS[0][0], PORTS[0][1] - 1), S(31, 9)], seed=5); route(m, [S(PORTS[1][0] + 1, PORTS[1][1]), S(9, 17)], seed=6); route(m, [S(PORTS[2][0], PORTS[2][1] + 1), S(31, 19)], seed=7); route(m, [S(PORTS[3][0], PORTS[3][1] - 1), S(8, 12)], seed=8)
    route(m, [S(14, 8), S(14, 6)], seed=9); route(m, [S(28, 20), S(28, 21)], seed=10) if False else route(m, [S(26, 21), S(28, 20)], seed=10); route(m, [S(26, 6), S(21, 6), S(21, 5)], seed=11) if False else route(m, [S(26, 6), S(22, 6)], seed=11)
    route(m, [S(35, 13), S(37, 12)], seed=12)
    thin_roads(m); fix_rungs(m)
    for args in [(35, 14, "BBC"), (32, 8, "BC"), (31, 19, "BC"), (38, 14, "C"), (26, 6, "Cb"), (26, 21, "Cb"), (20, 7, "Cb"), (20, 20, "Cb"), (14, 8, "Cc"), (14, 20, "Cc"), (14, 6, "c"), (28, 21, "c"),
                 (6, 14, "BBC"), (8, 12, "BC"), (9, 17, "BC"), (3, 14, "C"), (4, 8, "C"), (4, 20, "C"), (10, 3, "c"), (31, 3, "c"), (38, 24, "c"), (4, 25, "c"), (21, 22, "c"), (21, 6, "c"), (40, 6, "c"), (36, 3, "cc"), (39, 3, "c"), (2, 4, "c"), (40, 21, "c"), (1, 11, "c"), (17, 24, "cc"), (25, 3, "cc"), (8, 24, "c"), (34, 25, "c"), (12, 1, "c"), (1, 18, "c"), (40, 9, "c"), (3, 24, "cc"), (37, 26, "cc")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    for (x, y) in ((40, 2), (1, 1), (1, 26), (40, 26)):
        if m.g[y][x] in ".f^":
            m.g[y][x] = "c"
    neutralize(m, 14)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    for (x, y) in [(14, 13), (28, 13), (10, 14), (32, 14), (17, 16), (25, 10), (20, 17), (22, 9)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 5, MDT: 3, ART: 3, ROCK: 1, RECON: 1}, (30, 3, 40, 24), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1}, (1, 3, 11, 24), seed=2, gap=0, avoid=av)
    m.note("hq", 35, 14, "Black Hole's eastern HQ"); m.note("enemy_hq", 6, 14, "Max + Sami's HQ (objective)"); m.note("isthmus", 21, 13, "the isthmus between the lakes: the third Com Tower")
    return m
