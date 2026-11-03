"""Gauntlet 10, Neon Row (docs/dev/gauntlet.md): a city gauntlet of three lines, 32 x 22, four armies. The player (army 1, a free CO pick) holds the south-west blocks:
  1. Colin (Blue Moon, army 2) holds the east-centre blocks from the start: a big bank balance, cheap troops and a city on every corner.
  2. Kindle (Black Hole, army 3) arrives in the north-west blocks when Colin falls: city-fighting infantry, tanks and missiles.
  3. Jugger (Black Hole, army 4) arrives in the north-east blocks when Kindle falls; his HQ is the last: taking it (or routing him) wins.
No Black Hole inventions.

Design (docs/dev/map-design.md): a downtown. Streets run in a grid (rows y 2, 8, 14, 20 and columns x 3, 9, 15, 21, 27) and the blocks between them are built up: a city on most corners and along every street, parks (woods) and rubble (mountains)
in the blocks' hearts, almost no open ground. Every army fights for the street junctions: infantry take the cities, tanks hold the avenues, artillery sits in the blocks. Com Towers stand in the middle blocks.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import thin_roads, neutralize, prune_road_stubs

W, H = 32, 22
HQS = {"1": (4, 16), "2": (22, 9), "3": (4, 3), "4": (28, 3)}
ROWS = (2, 8, 14, 20)
COLS = (3, 9, 15, 21, 27)


def build():
    m = Canvas("gauntlet_10", W, H, campaign="gauntlet")
    rnd = random.Random("gauntlet_10/blocks")
    # --- the street grid
    for y in ROWS:
        m.rect("R", 0, y, W - 1, y)
    for x in COLS:
        m.rect("R", x, 0, x, H - 1)
    # --- the blocks: cities along the streets, parks and rubble inside
    for y in range(H):
        for x in range(W):
            if m.g[y][x] != ".":
                continue
            street = any(m.get(x + a, y + b) == "R" for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            r = rnd.random()
            if street and r < 0.62:
                m.g[y][x] = "C"
            elif not street and r < 0.30:
                m.g[y][x] = "f"
            elif not street and r < 0.52:
                m.g[y][x] = "^"
            elif street and r < 0.72:
                m.g[y][x] = "f"
    m.header(armies=4, colours=(OS, BM, BH, BH), team=(1, 2, 2, 2), objective=[1], hidden=[3, 4], comment=(
        "Gauntlet 10 Neon Row (normal look, no fog, 32 x 22, four armies): the player (army 1, HQ (4,16), the south-west blocks, a free CO) against Colin (Blue Moon, army 2, HQ (22,9), the east-centre blocks), then Kindle (Black Hole, "
        "army 3, HQ (4,3), the north-west blocks) and Jugger (Black Hole, army 4, HQ (28,3), the north-east blocks), who come onto the battlefield in turn: Kindle and Jugger share Black Hole's colour. "
        "Streets: rows y 2, 8, 14, 20; columns x 3, 9, 15, 21, 27. Com Towers (12,11) (18,5) (12,17) (24,17). No inventions."))
    for k, (x, y) in HQS.items():
        m.put("1" if k == "1" else "2" if k == "2" else ".", x, y)
    # --- production: a base beside each HQ, a few more bases, an airport each side
    for x, y, c in ((5, 16, "B"), (5, 17, "B"), (23, 9, "B"), (23, 10, "B"), (5, 3, "b"), (5, 4, "b"), (29, 3, "b"), (29, 4, "b"), (12, 9, "B"), (18, 15, "B"), (12, 4, "b"), (24, 4, "b"),
                    (6, 18, "A"), (24, 11, "A"), (8, 5, "a"), (26, 6, "a")):
        m.put(c, x, y)
    for x, y in ((12, 11), (18, 5), (12, 17), (24, 17)):
        m.put("t", x, y)
    thin_roads(m)
    neutralize(m, 6)
    # (the hidden lines' blocks are neutral city until they arrive: their HQ cells are plain, so nothing near them is owned)
    for k in ("3", "4"):
        x, y = HQS[k]
        m.g[y][x] = "."
    prune_road_stubs(m)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (1, 15, 14, 21), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 1, BCO: 1}, (1, 15, 14, 21), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 7, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (16, 5, 30, 13), seed=3, gap=0, avoid=av)
    m.spread(2, {BCO: 1, FTR: 1}, (16, 5, 30, 13), seed=4, gap=1, avoid=av)
    for k, t in {"1": "the player's HQ", "2": "Colin's HQ (Blue Moon): the first line, on the field from the start", "3": "Kindle's HQ (Black Hole, hidden until Colin falls)",
                 "4": "Jugger's HQ (Black Hole, hidden until Kindle falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    return m
