"""BH2 M26 Through the Door (secret mission, Act V): the Emerald Sun legion lands on Black Hole's own island. A free pair against one army under Klaus + Aurelia (Emerald Sun). Normal look, clear.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The shape: a diagonal strip: the home island is a band of land from the north-west corner to the south-east corner, a dozen cells wide, with the sea in the other two corners, so both coasts are long staircases with beaches.
The situation: Black Hole holds the north-west end: its HQ, a base district, two ports on the south-west coast. Klaus's first landing holds the south-east end (his HQ, a beachhead of bases) and a long north-east coast where the legion comes ashore in waves (spawns marked on the map):
  day 3: Cassius's cavalry (Recons and Tanks) on the north-east beach cells `mark_cav*`;
  day 5: Aurelia's siege (Artillery, Rockets and Md Tanks) on the south-east beach cells `mark_siege*`;
  day 7: Livia's fleet (Battleship, Cruisers, a Submarine and Landers) at sea off the north-east coast, the `mark_fleet*` cells.
The Emerald Sun skin belongs to the enemy army (the engine applies the skin to the player's army in an Emerald Sun battle only; for BH2's enemy it is a hook: see docs/dev/bh2-maps.md).
- Lanes: the island's spine road from the north-west to the south-east, a coast road on each side, the beaches on both coasts for the ships and Landers.
- Where the fight happens: the middle of the strip (the Com Tower (20,14) and the missile silo (22,12)), then the depot.
- Threats and answers: the cavalry's speed -> Black Hole's Tanks and Rockets behind the wall; the siege's range -> Recons and Fighters-free strikes by Tanks; Livia's Battleship -> Black Hole's Cruisers and Submarine and artillery on the beach.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 40, 28
CAV = [(12, 4), (15, 6), (18, 8), (20, 11)]                      # Cassius's landing cells (day 3)
SIEGE = [(37, 24), (35, 25), (38, 22), (33, 26)]                 # Aurelia's (day 5)
FLEET = [(22, 4), (25, 6), (27, 9), (30, 11), (20, 2)]            # Livia's ships (day 7), at sea off the north-east coast


def build():
    m = Canvas("bh2_26", W, H, fill="~")
    for y in range(H):
        for x in range(W):
            if abs(x - y * 40 / 28) <= 8.5 + (1 if (x * 7 + y * 13) % 5 == 0 else 0) - (1 if (x * 11 + y * 3) % 7 == 0 else 0):
                m.g[y][x] = "."
    S = lambda x, y: snap(m, x, y)
    belt(m, "^", [(4, 2), (9, 4)], width=1, seed=1); belt(m, "^", [(12, 10), (16, 8)], width=1, seed=2); belt(m, "^", [(24, 18), (28, 16)], width=1, seed=3); belt(m, "^", [(30, 22), (35, 22)], width=1, seed=4); belt(m, "^", [(3, 12), (7, 14)], width=1, seed=5)
    belt(m, "f", [(8, 8), (13, 12)], width=1, seed=6); belt(m, "f", [(16, 15), (20, 19)], width=1, seed=7); belt(m, "f", [(27, 10), (31, 13)], width=1, seed=8); belt(m, "f", [(25, 22), (29, 24)], width=1, seed=9); belt(m, "f", [(14, 4), (17, 6)], width=1, seed=10)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M26 Through the Door (secret; normal look, clear): a free pair (Black Hole, HQ 1 (7,6), the north-west of its own island) against one army under Klaus + Aurelia (the Emerald Sun legion, HQ 2 (32,21), the south-east end). The island is a diagonal strip. "
        "Waves: day 3 cavalry on mark_cav cells, day 5 siege on mark_siege cells, day 7 Livia's fleet on mark_fleet cells. Com Tower (20,14), missile silo (22,12). "
        "Player: INF3 MECH1 TANK3 MDT1 ART2 RECON1 AA1 CR1 SUB1; Klaus: INF5 MECH3 TANK4 MDT2 ART2 ROCK1 RECON1 CR1 SUB1."))
    m.put("1", 7, 6).put("2", 32, 21).put("t", 20, 14).put("M", 22, 12)
    PORTS = [snap_coast(m, 6, 12), snap_coast(m, 12, 20)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    route(m, [S(7, 7), S(11, 9), S(16, 11), S(20, 14), S(24, 16), S(29, 19), S(32, 20)], seed=1, wander=0.9)
    route(m, [S(8, 5), S(14, 5), S(20, 8), S(26, 11), S(31, 15), S(33, 19)], seed=2, wander=0.9); route(m, [S(6, 8), S(9, 14), S(14, 18), S(20, 21), S(27, 23), S(31, 22)], seed=3, wander=0.9)
    route(m, [S(PORTS[0][0], PORTS[0][1] - 1), S(9, 10)], seed=4); route(m, [S(PORTS[1][0], PORTS[1][1] - 1), S(14, 18)], seed=5); route(m, [S(20, 14), S(22, 12)], seed=6) if False else route(m, [S(21, 13), S(22, 13)], seed=6)
    route(m, [S(32, 20), S(35, 23)], seed=7)
    thin_roads(m); fix_rungs(m)
    for args in [(7, 6, "BBC"), (10, 8, "BC"), (5, 10, "BC"), (8, 12, "C"), (12, 10, "C"), (16, 11, "Cb"), (14, 5, "C"), (9, 14, "C"), (14, 18, "Cb"), (20, 14, "c"), (20, 21, "Cb"), (20, 8, "Cb"), (26, 11, "bc"), (24, 16, "bc"), (27, 23, "bc"),
                 (32, 21, "BBBC"), (34, 18, "BC"), (29, 19, "BC"), (31, 15, "C"), (35, 23, "C"), (31, 22, "C"), (26, 6, "c"), (36, 13, "c"), (3, 3, "c"), (3, 17, "c"), (37, 27, "c"), (20, 4, "c"), (24, 24, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    for (x, y) in CAV + SIEGE:
        if m.g[y][x] in "^fBCcbR":
            m.g[y][x] = "."
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    for (x, y) in CAV + SIEGE:
        pass
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve(CAV + SIEGE + FLEET)
    m.spread(1, {INF: 3, MECH: 1, TANK: 3, MDT: 1, ART: 2, RECON: 1, AA: 1}, (1, 1, 16, 14), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (26, 14, 39, 27), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PORTS[0][0], PORTS[0][1], 2, box=(0, 8, 12, 20), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(36, 12, 2, box=(30, 6, 39, 16), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 7, 6, "Black Hole's HQ"); m.note("enemy_hq", 32, 21, "Klaus + Aurelia's HQ (objective)")
    for i, (x, y) in enumerate(CAV):
        m.note(f"mark_cav{i + 1}", x, y, "day 3: Cassius's cavalry lands here")
    for i, (x, y) in enumerate(SIEGE):
        m.note(f"mark_siege{i + 1}", x, y, "day 5: Aurelia's siege lands here")
    for i, (x, y) in enumerate(FLEET):
        m.note(f"mark_fleet{i + 1}", x, y, "day 7: Livia's ship arrives here")
    return m
