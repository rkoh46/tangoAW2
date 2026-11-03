"""Gauntlet 11, Blue Bastion (docs/dev/gauntlet.md): ALL of Blue Moon, one CO after another: four lines of one army (Olaf, Grit, Colin, Sasha) inside one fortress, 36 x 26 = 936 cells, five armies (the player is army 5).
Every line is Blue Moon's colours and Blue Moon's HQ: only the army slot differs (1 Olaf, 2 Grit, 3 Colin, 4 Sasha), so the player cannot wear Blue Moon here. The player (a free CO) camps outside the west wall:
  1. Olaf (army 1) holds the south-west ward from the start: snow-hardened infantry and tanks behind the west gate.
  2. Grit (army 2) arrives in the north-west ward when Olaf falls: artillery and rockets behind the cross wall.
  3. Colin (army 3) arrives in the north-east ward when Grit falls: a rich line of cheap troops and tanks.
  4. Sasha (army 4) arrives in the south-east ward when Colin falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): a fortress, walled on every side with a two-cell wall of mountains (x 13..33, y 1..24), cut into four wards by a cross of inner walls (x 22..23 and y 12..13); a moat (the Blue Moat, a river
from the north edge to the south edge with a bend at each third) runs along the west wall with drawbridges (10,7) and (10,19) to the two west gates (y 6..7 and y 18..19). The inner walls have gates: (18..19, 12..13) between the
south-west and north-west wards, (22..23, 7..8) between the north wards, (22..23, 17..18) between the south wards and (27..28, 12..13) between the east wards. Each ward has its HQ, bases and cities; the Com Towers stand at the
crossing's corners.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clean_river_roads, prune_road_stubs

W, H = 36, 26
# the HQs: army 1 Olaf, 2 Grit, 3 Colin, 4 Sasha, 5 the player
HQS = {"1": (19, 18), "2": (19, 7), "3": (27, 7), "4": (27, 18), "5": (3, 20)}
BR = [(10, 7), (10, 19)]


def build():
    m = Canvas("gauntlet_11", W, H, campaign="gauntlet")
    rnd = random.Random("gauntlet_11/wall")
    # --- the moat: a river along the west wall, a bend at each third
    m.river([(10, 0), (10, 8), (11, 8), (11, 17), (10, 17), (10, 25)])
    for x, y in BR:
        m.put("=", x, y)
    # --- the fortress: an outer wall two cells thick, the cross of inner walls, a gate in each wall
    m.rect("^", 13, 1, 33, 24); m.rect(".", 15, 3, 31, 22)
    m.rect("^", 22, 3, 23, 22); m.rect("^", 15, 12, 31, 13)
    m.rect(".", 13, 6, 14, 7); m.rect(".", 13, 18, 14, 19)                    # (the west wall's two gates)
    m.rect(".", 18, 12, 19, 13); m.rect(".", 27, 12, 28, 13)                  # (the east-west inner wall's gates)
    m.rect(".", 22, 7, 23, 8); m.rect(".", 22, 17, 23, 18)                    # (the north-south inner wall's gates)
    m.rect(".", 26, 1, 27, 2); m.rect(".", 26, 23, 27, 24)                    # (a postern in the north and south walls)
    # (the wall is ragged: a few cells of it have crumbled, a few rubble cells lie outside it, the corners have towers of three)
    for x, y in [(20, 1), (24, 24), (33, 12), (13, 10), (29, 23), (22, 4)]:
        m.put(".", x, y)
    for x0, y0, x1, y1 in ((11, 0, 14, 3), (32, 0, 35, 3), (11, 22, 14, 25), (32, 22, 35, 25)):         # (a tower at each corner of the wall)
        m.rect("^", x0, y0, x1, y1)
    m.rect("^", 20, 10, 25, 15); m.rect(".", 21, 11, 24, 14)                                           # (the keep: a ring of rock round the crossing's courtyard)
    m.rect(".", 22, 10, 23, 10); m.rect(".", 22, 15, 23, 15)
    # --- woods inside the courts and outside the walls
    m.puts("f", [(16, 4), (30, 4), (16, 21), (30, 21), (17, 10), (29, 10), (17, 15), (29, 15), (20, 4), (25, 21), (20, 21), (25, 4)])
    for i, (cx, cy, n) in enumerate([(6, 6, 3), (3, 12, 2), (7, 15, 3), (6, 22, 2), (3, 3, 2), (35, 4, 1), (35, 21, 1), (8, 10, 2), (2, 17, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    for i, pts in enumerate([[(1, 8), (4, 9)], [(5, 24), (8, 25)], [(34, 11), (35, 14)]]):
        belt(m, "^", pts, width=1, seed=20 + i, p=0.95)
    m.header(armies=5, colours=(BM, BM, BM, BM, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 11, 8, 25)], hidden=[2, 3, 4], comment=(
        "Gauntlet 11 Blue Bastion (normal look, no fog, 36 x 26, five armies): the player (army 5, HQ 5 (3,20), outside the west wall, a free CO) against all of Blue Moon inside one fortress: Olaf (army 1, HQ (19,18), the south-west ward), "
        "then Grit (army 2, HQ (19,7), the north-west ward), Colin (army 3, HQ (27,7), the north-east ward) and Sasha (army 4, HQ (27,18), the south-east ward), who come onto the battlefield in turn: every line wears Blue Moon's "
        "colour, only the army slots differ. The Blue Moat (x 10..11) with drawbridges (10,7) (10,19). Com Towers (21,11) (24,14) (21,14) (24,11). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((21, 11), (24, 14), (21, 14), (24, 11)):
        m.put("t", x, y)
    S = lambda x, y: snap(m, x, y)
    # --- roads: from the player's camp over the drawbridges and through every gate to every HQ
    m.line("R", [(3, 20), (5, 19), (9, 19)], over=".fR"); m.line("R", [(9, 19), (12, 19), (19, 19), (19, 18)], over=".fR")
    m.line("R", [(3, 20), (3, 7), (9, 7)], over=".fR"); m.line("R", [(9, 7), (14, 7), (19, 7)], over=".fR")
    m.line("R", [(19, 19), (19, 14), (19, 12), (19, 7)], over=".fR")
    m.line("R", [(19, 7), (21, 7), (24, 7), (27, 7)], over=".fR"); m.line("R", [(19, 18), (21, 18), (24, 18), (27, 18)], over=".fR")
    m.line("R", [(27, 7), (27, 14), (27, 18)], over=".fR"); m.line("R", [(27, 2), (27, 7)], over=".fR"); m.line("R", [(27, 18), (27, 23)], over=".fR")
    m.line("R", [(19, 18), (19, 19)], over=".fR")
    thin_roads(m)
    for args in [(3, 20, "BBC"), (7, 21, "BC"), (2, 17, "C"), (7, 23, "BC"), (6, 17, "C"), (4, 8, "C"), (6, 4, "c"), (8, 12, "c"),
                 (19, 18, "BBC"), (16, 20, "BC"), (21, 20, "C"), (17, 15, "C"), (21, 16, "C"),
                 (19, 7, "BBC"), (16, 5, "bc"), (21, 5, "c"), (17, 10, "c"), (20, 10, "b"),
                 (27, 7, "bbc"), (30, 5, "bc"), (25, 5, "c"), (30, 10, "c"), (25, 10, "ca"),
                 (27, 18, "bbc"), (30, 20, "bc"), (25, 20, "c"), (30, 15, "c"), (25, 15, "ca")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 6)
    prune_road_stubs(m)
    for y in range(14, 26):
        for x in range(0, 10):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 17, 6, 25), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 1, BCO: 1}, (1, 17, 6, 25), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 6, MECH: 3, TANK: 4, MDT: 3, ART: 3, ROCK: 1, RECON: 2, AA: 2, APC: 1}, (16, 14, 21, 22), seed=3, gap=0, avoid=av)
    m.spread(1, {BCO: 1, FTR: 1}, (16, 14, 21, 22), seed=4, gap=1, avoid=av)
    for k, t in {"1": "Olaf's HQ (Blue Moon): the first line, on the field from the start", "2": "Grit's HQ (Blue Moon, hidden until Olaf falls)", "3": "Colin's HQ (Blue Moon, hidden until Grit falls)",
                 "4": "Sasha's HQ (Blue Moon, hidden until Colin falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
