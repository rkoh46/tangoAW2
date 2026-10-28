"""BH2 M23 Where the Map Ends (Act V): the Obelisk in the west, held against the Allied strike force. Asuka + Crumb (forced pair) against one army under Drake + Grit. Wasteland look, a sandstorm for the storm. Hold for nine days.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: a canyon: a zigzag chasm of lava (three cells wide: it steps from the north-east to the south-west in two jogs) runs from the top edge down to the bottom edge and splits the land edge to edge into a west wing and an east wing; three bridges
(rows 5, 12 and 19) are the only crossings. The situation: Black Hole holds the west wing: its HQ, a ring of bases, two Com Towers and the Black Obelisk (the door's frame) on the high ground; Drake and Grit's strike force (their HQ and a base district in the east wing) must cross to reach it.
The mission is to hold for nine days: from day 2 a wave of reinforcements lands on the east wing's edge cells (the `mark_wave*` notes) every second day, and they come over the bridges and by air. The storm is a sandstorm over the wasteland (long guns lose a cell of range).
- Lanes: the three bridges, the ridge in the west wing that shelters the Obelisk, the air: the strike force has Fighters, Bombers and Copters, so Black Hole's Anti-Air and its own wing hold the sky.
- Where the fight happens: the west bridgeheads (rows 5, 12, 19), then the ring of the Obelisk.
- Properties: the west wing's bases build the garrison; villages on the bridgeheads' roads; the east wing's bases feed the strike force.
- Threats and answers: the waves' Neotanks and Md Tanks -> Black Hole's Md Tanks, artillery on the ridge and the bridges' chokes; their Fighters and Bombers -> Anti-Air and Fighters; no ships (the water is lava).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 44, 26
WAVES = [(42, 5), (42, 9), (42, 13), (42, 17), (41, 7), (41, 11), (41, 15), (41, 19), (42, 3), (42, 21), (41, 4), (41, 22)]       # the east edge's cells where the waves land
CROWS = {5: 28, 12: 22, 19: 16}                              # the canyon's centre column at each bridge row (it is straight for five rows round each, a jog between)


def CY(y):
    return 28 if y <= 8 else 22 if 10 <= y <= 14 else 16 if y >= 16 else None


def build():
    m = Canvas("bh2_23", W, H)
    for y in range(H):
        c = CY(y)
        lo, hi = (c - 1, c + 1) if c is not None else ((21, 29) if y == 9 else (15, 23))
        for x in range(lo, hi + 1):
            m.g[y][x] = "~"
    S = lambda x, y: snap(m, x, y)
    # --- three bridges across the canyon (rows 5, 12, 19), straight approaches either side
    for by in (5, 12, 19):
        c = CY(by)
        for x in range(c - 1, c + 2):
            m.g[by][x] = "="
    belt(m, "^", [(3, 4), (8, 3), (14, 4)], width=1, seed=1, gaps=[(6, 3), (11, 4)]); belt(m, "^", [(2, 21), (8, 22), (12, 21)], width=1, seed=2, gaps=[(6, 22)]); belt(m, "^", [(10, 8), (13, 10)], width=1, seed=3); belt(m, "^", [(10, 15), (13, 17)], width=1, seed=4)
    belt(m, "^", [(30, 3), (36, 4), (41, 3)], width=1, seed=5, gaps=[(34, 3), (38, 4)]); belt(m, "^", [(25, 21), (31, 22), (38, 21)], width=1, seed=6, gaps=[(28, 22), (35, 21)]); belt(m, "^", [(32, 8), (35, 10)], width=1, seed=7); belt(m, "^", [(32, 16), (35, 18)], width=1, seed=8)
    belt(m, "f", [(3, 9), (7, 8)], width=1, seed=9); belt(m, "f", [(3, 17), (7, 18)], width=1, seed=10); belt(m, "f", [(14, 12), (16, 14)], width=1, seed=11); belt(m, "f", [(28, 6), (31, 8)], width=1, seed=12)
    belt(m, "f", [(28, 15), (31, 17)], width=1, seed=13); belt(m, "f", [(38, 8), (41, 9)], width=1, seed=14); belt(m, "f", [(38, 17), (41, 18)], width=1, seed=15); belt(m, "f", [(6, 5), (10, 6)], width=1, seed=16)
    for i, (cx, cy, n, ch) in enumerate([(9, 11, 3, "^"), (9, 14, 3, "f"), (19, 9, 3, "^"), (19, 16, 3, "f"), (24, 8, 3, "f"), (25, 16, 3, "^"), (27, 12, 3, "^"), (35, 6, 3, "f"), (36, 20, 3, "f"), (22, 22, 3, "^"), (20, 3, 3, "^"), (4, 6, 3, "f"), (3, 24, 3, "^"),
                                          (30, 12, 3, "f"), (39, 11, 3, "^"), (39, 16, 3, "^"), (14, 24, 3, "f"), (15, 2, 3, "f"), (33, 22, 3, "^"), (28, 2, 3, "f")]):
        m.cluster(ch, cx, cy, n * 3, seed=60 + i)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M23 Where the Map Ends (Wasteland look, sandstorm): Asuka + Crumb (forced pair, Black Hole, HQ 1 (7,13), the west wing) against one army under Drake + Grit (HQ 2 (40,13), the east wing). A lava zigzag canyon (three cells wide: centre column 28, then 22, then 16, with a jog between) with bridges at rows 5, 12 and 19. "
        "The Black Obelisk (O) at (12,13) in the west wing, between the HQ and the canyon; Com Towers (16,7) and (16,19). Hold nine days: the mission is won on day 10; waves land on the mark_wave cells. Player: INF4 MECH2 TANK3 MDT1 ART2 RECON1 AA2 BCO3 FTR3; Drake + Grit: INF4 MECH2 TANK3 MDT1 ART2 AA1 FTR3 BMB2 BCO3 STEALTH2."))
    m.put("1", 7, 13).put("2", 40, 13).put("t", 16, 7).put("t", 16, 19)
    m.stamp("O", 12, 13)
    for by in (5, 12, 19):
        c = CY(by)
        route(m, [S(7, 13), S(c - 6, by), (c - 2, by)], seed=by, wander=0.6) if by != 12 else route(m, [S(8, 13), S(c - 6, by), (c - 2, by)], seed=by, wander=0.6)
        route(m, [(c + 2, by), S(c + 6, by), S(34, 12 if by == 12 else by), S(38, 13), S(40, 13)] if False else [(c + 2, by), S(c + 6, by), S(36, 13), S(40, 13)], seed=by + 10, wander=0.8)
    route(m, [S(16, 7), S(14, 6), S(10, 6)], seed=30) if False else route(m, [S(16, 7), S(15, 8)], seed=30); route(m, [S(16, 19), S(15, 18)], seed=31)
    route(m, [S(34, 14), S(36, 20), S(41, 20)], seed=40); route(m, [S(30, 18), S(34, 22), S(38, 22)], seed=41); route(m, [S(30, 8), S(34, 4), S(38, 5)], seed=42); route(m, [S(20, 19), S(23, 21)], seed=43); route(m, [S(19, 5), S(21, 3)], seed=44)
    thin_roads(m); fix_rungs(m)
    for args in [(7, 13, "BBC"), (9, 10, "BC"), (9, 16, "BC"), (12, 13, "C"), (5, 8, "C"), (5, 19, "C"), (16, 7, "c"), (16, 19, "c"), (19, 5, "Cb"), (13, 12, "Cb"), (13, 19, "Cb"), (4, 4, "c"), (3, 23, "c"), (10, 4, "c"), (10, 22, "c"),
                 (40, 13, "BBC"), (37, 10, "BC"), (37, 16, "BC"), (34, 12, "C"), (34, 14, "C"), (25, 5, "bc"), (23, 12, "bc"), (21, 19, "bc"), (38, 5, "c"), (38, 22, "c"), (30, 8, "c"), (30, 18, "c"), (41, 1, "c"), (41, 24, "c"), (42, 20, "cc"), (36, 21, "c"), (23, 21, "cc"), (21, 3, "cc"), (2, 1, "cc"), (14, 8, "cc"), (14, 17, "cc"), (27, 9, "c"), (27, 16, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    for (x, y) in WAVES:
        if m.g[y][x] in "^fBCcbR":
            m.g[y][x] = "."
    for (x, y) in ((31, 1), (43, 0), (0, 0)):
        if m.g[y][x] in ".f^":
            m.g[y][x] = "c"
    neutralize(m, 14)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve(WAVES)
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, RECON: 1, AA: 2}, (1, 3, 15, 22), seed=1, gap=0, avoid=av)
    m.spread(1, {BCO: 3, FTR: 3}, (1, 3, 14, 22), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, AA: 1}, (32, 5, 42, 20), seed=3, gap=0, avoid=av)
    m.spread(2, {FTR: 3, BMB: 2, BCO: 3, STEALTH: 2}, (32, 3, 42, 22), seed=4, gap=1, avoid=av)
    m.note("hq", 7, 13, "Asuka + Crumb's HQ"); m.note("enemy_hq", 40, 13, "Drake + Grit's HQ"); m.note("obelisk", 12, 13, "Black Hole's Black Obelisk: hold it nine days")
    for i, (x, y) in enumerate(WAVES):
        m.note(f"mark_wave{i + 1}", x, y, "reinforcement wave lands here")
    return m
