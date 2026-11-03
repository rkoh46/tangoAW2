"""Gauntlet 11, Blue Bastion (docs/dev/gauntlet.md): ALL of Blue Moon, one CO after another: four lines of one army (Olaf, Grit, Colin, Sasha) inside one castle, 46 x 28 = 1288 cells, five armies (the player is army 5).
Every line is Blue Moon's colours and Blue Moon's HQ: only the army slot differs (1 Olaf, 2 Grit, 3 Colin, 4 Sasha), so the player cannot wear Blue Moon here. The player (a free CO) camps outside the moat:
  1. Olaf (army 1) holds the outer bailey from the start: infantry and tanks behind the outer wall.
  2. Grit (army 2) arrives in the west ward of the inner castle when Olaf falls: artillery and rockets behind the second wall.
  3. Colin (army 3) arrives in the east ward when Grit falls: a rich line of cheap troops and tanks.
  4. Sasha (army 4) arrives in the keep, the middle of the castle, when Colin falls; her HQ is the last: taking it (or routing her) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): one closed castle, three nested rings. The **moat** is a closed ring of water: four rivers (north y 1, south y 26, west x 9, east x 43) each running from a corner lake to the next (the lakes are 3 x 3 at
the four corners), so no river ends dry. The **outer wall** is a continuous rectangle of mountains two cells thick (x 11..41, y 3..24, a tower at each corner) with two gates in its west face, (11..12, 8..9) and (11..12, 19..20), each
reached by a drawbridge over the west moat ((9,8), (9,9), (9,19), (9,20)); the ring road of the **outer bailey** (Olaf) runs round inside it. The **second wall** (x 16..36, y 8..19, two thick) has a gate in each side, (16..17, 13..14) and
(35..36, 13..14); inside it the **middle ring** is cut by the **keep** (x 22..30, y 10..17, one cell thick, gates (22, 13..14) and (30, 13..14)) into the west ward (Grit) and the east ward (Colin). The keep's courtyard (x 23..29, y 11..16)
holds Sasha's HQ at its middle. Com Towers in the two wards.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import town, thin_roads, neutralize, prune_road_stubs

W, H = 46, 28
# the HQs: army 1 Olaf, 2 Grit, 3 Colin, 4 Sasha, 5 the player
HQS = {"1": (16, 21), "2": (20, 15), "3": (32, 15), "4": (26, 13), "5": (3, 22)}
BR = [(9, 8), (9, 9), (9, 19), (9, 20)]


def build():
    m = Canvas("gauntlet_11", W, H, campaign="gauntlet")
    # --- the moat: four corner lakes and the four rivers between them (a closed ring: every river ends in a lake)
    for cx, cy in ((9, 1), (43, 1), (9, 26), (43, 26)):
        m.rect("~", cx - 1, cy - 1, cx + 1, cy + 1)
    m.river([(11, 1), (41, 1)]); m.river([(11, 26), (41, 26)]); m.river([(9, 3), (9, 24)]); m.river([(43, 3), (43, 24)])
    for x, y in BR:
        m.put("=", x, y)
    # --- the outer wall: two cells of mountains all round, a tower of 3 x 3 at each corner, two gates in the west face
    m.rect("^", 11, 3, 41, 24); m.rect(".", 13, 5, 39, 22)
    for x0, y0 in ((11, 3), (39, 3), (11, 22), (39, 22)):
        m.rect("^", x0, y0, x0 + 2, y0 + 2)
    m.rect(".", 11, 8, 12, 9); m.rect(".", 11, 19, 12, 20)
    # --- the second wall (two thick) with a gate in its west and east faces, the keep (one thick) with a gate each side
    m.rect("^", 16, 8, 36, 19); m.rect(".", 18, 10, 34, 17)
    m.rect(".", 16, 13, 17, 14); m.rect(".", 35, 13, 36, 14)
    m.rect("^", 22, 10, 30, 17); m.rect(".", 23, 11, 29, 16)
    m.rect(".", 22, 13, 22, 14); m.rect(".", 30, 13, 30, 14)
    # --- a few woods inside the courts and orchards outside the moat
    m.puts("f", [(14, 7), (38, 7), (14, 20), (38, 20), (24, 6), (26, 6), (24, 22), (26, 22), (28, 6), (22, 22)])
    for i, (cx, cy, n) in enumerate([(5, 5, 3), (3, 12, 2), (6, 15, 2), (5, 25, 2), (2, 2, 2), (45, 6, 1), (45, 22, 1), (4, 9, 2), (2, 18, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=10 + i)
    m.header(armies=5, colours=(BM, BM, BM, BM, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 7, 8, 27)], hidden=[2, 3, 4], comment=(
        "Gauntlet 11 Blue Bastion (normal look, no fog, 46 x 28, five armies): the player (army 5, HQ 5 (3,22), outside the moat, a free CO) against all of Blue Moon inside one castle: Olaf (army 1, HQ (16,21), the outer bailey), "
        "then Grit (army 2, HQ (20,15), the west ward), Colin (army 3, HQ (32,15), the east ward) and Sasha (army 4, HQ (26,13), the keep), who come onto the battlefield in turn: every line wears Blue Moon's "
        "colour, only the army slots differ. The moat is a closed ring of four rivers and four corner lakes; drawbridges (9,8) (9,9) (9,19) (9,20). Com Towers (20,12) (32,12) (24,12) (28,15). No inventions."))
    m.put("1", *HQS["1"]).put("5", *HQS["5"]).put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"])
    for x, y in ((20, 12), (32, 12), (24, 12), (28, 15)):
        m.put("t", x, y)
    # --- roads: the player's camp over the drawbridges and through the gates, the bailey's ring road, the road through the wards and the keep
    R = lambda pts: m.line("R", pts, over=".fR")
    R([(3, 22), (3, 9), (14, 9)]); R([(3, 20), (14, 20)])
    R([(14, 6), (38, 6), (38, 21), (14, 21), (14, 6)])
    R([(14, 13), (38, 13)])
    thin_roads(m)
    for args in [(3, 22, "BBC"), (7, 23, "BC"), (2, 17, "C"), (7, 25, "BC"), (6, 17, "C"), (4, 7, "C"), (6, 4, "c"), (7, 12, "c"),
                 (16, 21, "BBC"), (14, 18, "BC"), (20, 21, "C"), (14, 10, "C"), (22, 21, "C"), (30, 21, "C"),
                 (20, 15, "BC"), (32, 15, "bc"), (26, 13, "bc"),
                 (24, 7, "bc"), (18, 6, "c"), (34, 6, "c"), (38, 10, "bc"), (38, 17, "c"), (28, 21, "c"), (14, 14, "c"),
                 (22, 6, "c"), (30, 6, "c"), (38, 7, "c"), (38, 14, "c"), (38, 20, "c"), (34, 21, "c"), (18, 21, "c"), (26, 21, "c"), (14, 8, "c"), (14, 17, "c"),
                 (19, 11, "c"), (20, 17, "c"), (33, 11, "c"), (33, 17, "c"), (24, 15, "c"), (28, 12, "c"), (10, 14, "c"), (6, 10, "c"), (5, 20, "bc")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 7)
    prune_road_stubs(m)
    for y in range(12, 28):
        for x in range(0, 9):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 15, 5, 26), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 1, BCO: 1}, (1, 15, 5, 26), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 3, MECH: 2, TANK: 2, MDT: 2, ART: 2, AA: 1}, (13, 6, 15, 20), seed=3, gap=0, avoid=av)
    m.spread(1, {INF: 3, MECH: 1, TANK: 2, MDT: 1, ART: 1, ROCK: 1, AA: 1, APC: 1, BCO: 1, FTR: 1}, (17, 20, 37, 22), seed=4, gap=0, avoid=av)
    for k, t in {"1": "Olaf's HQ (Blue Moon): the first line, on the field from the start", "2": "Grit's HQ (Blue Moon, hidden until Olaf falls)", "3": "Colin's HQ (Blue Moon, hidden until Grit falls)",
                 "4": "Sasha's HQ (Blue Moon, hidden until Colin falls): the last", "5": "the player's HQ"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
