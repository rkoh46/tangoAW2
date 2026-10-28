"""BH2 M29 The Gate of Colours (Act V): Orange Star's outer capital, on a desert delta. A free pair against Andy (Orange Star) and Max + Sami (a second army, Blue Moon's colours), allied: three armies. Desert look, clear weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: a river delta: land off the top, west and east edges with a ragged south coast on the desert sea; three rivers come down from the north edge side by side and reach the sea in three mouths, with a sandbar islet between the first two mouths.
The situation: Black Hole's column holds the west bank (HQ, a base district, a port); Andy holds the middle between the first and second rivers (HQ, bases, the outer capital's cities and a port: the gate of the capital's road); Max + Sami (the second Allied army, allied with Andy) hold the east (HQ, bases, a port). Black Hole must cross
the first river against Andy, then the second and third against Max and Sami; each river has two bridges (a north and a south bridge).
- Lanes: the north highway (three bridges), the south highway (three bridges), the cross roads inside each bank, the three river mouths' beaches for the fleets.
- Where the fight happens: the first river's bridges (12,4) and (13,14), Andy's capital, then the second river (22,5) and (21,16).
- Properties: Andy's capital cities, villages at every bridgehead, a Com Tower in each of the middle banks, a missile silo on a sandbar islet.
- Threats and answers: the two Allied armies' Tanks, Md Tanks and artillery -> Black Hole's Md Tanks, Rockets and artillery on the near bank; their fleets -> Black Hole's own; the Allies field no air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 44, 28


def build():
    m = Canvas("bh2_29", W, H, fill="~")
    rnd = random.Random("bh2_24/coast")
    B, b = {}, 22
    for x in range(W):
        if x % 4 == 0:
            b = max(17, min(19, b + rnd.choice([-1, 0, 1])))
        B[x] = b
    for r in (12, 21, 31):                                       # the mouths stand on straight shores
        for x in range(r - 2, r + 3):
            B[x] = B[r + 1]
    for x in range(W):
        m.rect(".", x, 0, x, B[x])
    m.rect("~", 0, 18, 0, H - 1); m.rect("~", W - 1, 18, W - 1, H - 1)
    # the south island, : a hooked crescent round a lagoon (a V-shaped inlet from the north: a Lander's beach and the island's port), two arms with the silos at their tips
    for y, spans in {23: ((14, 17), (22, 27)), 24: ((12, 19), (21, 28)), 25: ((11, 17), (23, 29)), 26: ((12, 28),), 27: ((13, 16), (19, 26))}.items():
        for x0, x1 in spans:
            m.rect(".", x0, y, x1, y)
    m.river([(12, 0), (12, 8), (13, 8), (13, B[13])]); m.river([(22, 0), (22, 10), (21, 10), (21, B[21])]); m.river([(32, 0), (32, 7), (31, 7), (31, B[31])])
    S = lambda x, y: snap(m, x, y)
    belt(m, "^", [(3, 4), (8, 5)], width=1, seed=1); belt(m, "^", [(3, 17), (8, 16)], width=1, seed=2); belt(m, "^", [(15, 10), (19, 11)], width=1, seed=3); belt(m, "^", [(15, 17), (19, 15)], width=1, seed=4)
    belt(m, "^", [(24, 3), (29, 4)], width=1, seed=5); belt(m, "^", [(25, 14), (29, 17)], width=1, seed=6); belt(m, "^", [(34, 10), (38, 9)], width=1, seed=7); belt(m, "^", [(34, 16), (40, 17)], width=1, seed=8)
    belt(m, "f", [(3, 9), (9, 11)], width=1, seed=9); belt(m, "f", [(15, 5), (19, 4)], width=1, seed=10); belt(m, "f", [(24, 9), (29, 11)], width=1, seed=11); belt(m, "f", [(36, 4), (40, 6)], width=1, seed=12); belt(m, "f", [(34, 19), (39, 19)], width=1, seed=13)
    for i, (cx, cy, n, ch) in enumerate([(6, 7, 3, "f"), (9, 18, 3, "^"), (25, 11, 3, "^"), (26, 19, 3, "f"), (36, 11, 3, "f"), (38, 19, 3, "^"), (16, 3, 3, "^"), (30, 3, 3, "f"), (2, 9, 3, "^"), (41, 12, 3, "^")]):
        m.cluster(ch, cx, cy, n * 3, seed=60 + i)
    m.header(armies=3, colours=(BH, OS, BM), team=(1, 2, 2), objective=[1], comment=(
        "M29 The Gate of Colours (desert look, clear): a free pair (Black Hole, HQ 1 (5,12), the west bank) against Andy (Orange Star army 2, HQ 2 (17,12), the middle bank with the outer capital) and Max + Sami (army 3 in Blue Moon's colours, HQ 3 (38,12), the east): the two enemy armies are allied. "
        "Three rivers (x 12, 22, 31) from the north edge to the desert sea; bridges (12,4) (13,14) (22,5) (21,16) (32,4) (31,15). Com Towers (26,8) and (27,16); the south island (x 11..29, rows 23..27, joined to nothing: ships and Landers only) holds four missile silos (13,24) (16,26) (23,24) (27,26), a neutral airport (25,25), a neutral port (19,24) on its lagoon and cities (14,25) and (27,24). "
        "Player: INF5 MECH2 TANK4 MDT2 ART3 ROCK1 RECON1 CR1 SUB1; Andy: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1 CR1 SUB1; Max + Sami: INF5 MECH3 TANK5 MDT2 ART3 ROCK2 RECON1 CR1 SUB1."))
    m.put("1", 5, 12).put("2", 17, 13).put("3", 38, 12).put("t", 26, 8).put("t", 27, 16).put("M", 13, 24).put("M", 16, 26).put("M", 23, 24).put("M", 27, 26).put("p", 19, 24).put("a", 25, 25).put("c", 14, 25).put("c", 27, 24)
    PORTS = [snap_coast(m, 6, 17), snap_coast(m, 17, 18), snap_coast(m, 37, 18)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    route(m, [S(6, 11), S(9, 8), (10, 4), (12, 4, "="), (14, 4), S(17, 6), S(20, 5), (22, 5, "="), (24, 5), S(27, 6), S(30, 5), (32, 4, "="), (34, 4), S(36, 7), S(38, 11)], seed=21, wander=0.8)
    route(m, [S(6, 13), S(9, 15), S(11, 15), (13, 14, "="), (15, 14), S(17, 15), S(19, 16), (21, 16, "="), (23, 16), S(27, 16), S(29, 15), (31, 15, "="), (33, 15), S(36, 14), S(38, 13)], seed=22, wander=0.8)
    route(m, [S(17, 12), S(15, 9), S(15, 5)], seed=23) if False else route(m, [S(17, 12), S(16, 9), (14, 4)], seed=23); route(m, [S(17, 14), (17, 15)], seed=24); route(m, [S(25, 6), S(25, 12), S(26, 16)], seed=25); route(m, [S(36, 7), S(36, 12), S(36, 14)], seed=26)
    for i, p in enumerate(PORTS):
        route(m, [S(p[0], p[1] - 1), S(p[0], p[1] - 4)], seed=30 + i)
    route(m, [S(6, 14), S(PORTS[0][0], PORTS[0][1] - 4)], seed=34); route(m, [S(17, 15), S(PORTS[1][0], PORTS[1][1] - 4)], seed=35); route(m, [S(36, 14), S(PORTS[2][0], PORTS[2][1] - 4)], seed=36)
    route(m, [S(26, 8), S(25, 8)], seed=37) if False else None
    route(m, [S(28, 11), S(30, 11), (31, 11, "="), (33, 11), S(35, 11)], seed=50); route(m, [S(18, 13), S(20, 13), (21, 13, "="), (23, 13), S(25, 12)], seed=51)
    thin_roads(m); fix_rungs(m)
    for c in [(14, 17), (15, 17), (14, 19), (15, 19)]:                       # (road stubs that end at the first river: no crossing there)
        if m.get(*c) in "R": m.put(".", *c)
    for args in [(5, 12, "BBC"), (8, 15, "BC"), (7, 9, "BC"), (3, 13, "C"), (10, 4, "C"), (11, 15, "C"), (17, 13, "BBC"), (14, 4, "C"), (16, 9, "CC"), (17, 15, "BC"), (15, 14, "C"), (20, 5, "CC"), (19, 16, "C"), (24, 5, "bc"), (23, 16, "bc"), (26, 8, "c"), (27, 16, "c"),
                 (38, 12, "BBC"), (34, 4, "BC"), (33, 15, "BC"), (36, 7, "C"), (36, 14, "C"), (30, 5, "bc"), (29, 15, "bc"), (27, 6, "c"), (27, 16, "c"), (41, 8, "c"), (41, 16, "c"), (4, 4, "cc"), (40, 3, "cc"), (10, 19, "c"), (26, 21, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 14)
    m.desertify(keep=0.6, rocks=3, size=5, seed=24)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS + [(13, B[13]), (21, B[21]), (31, B[31])]:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0), (0, 1)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    for (x, y) in [(10, 26), (22, 26), (34, 26), (6, 25), (40, 25), (14, 24), (36, 24)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 1}, (1, 5, 10, 16), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1}, (14, 5, 21, 16), seed=2, gap=0, avoid=av)
    m.spread(3, {INF: 5, MECH: 3, TANK: 5, MDT: 2, ART: 3, ROCK: 2, RECON: 1}, (33, 5, 42, 16), seed=3, gap=0, avoid=av)
    for army, p, box in ((1, PORTS[0], (2, 20, 10, 27)), (2, PORTS[1], (13, 20, 22, 22)), (3, PORTS[2], (32, 20, 42, 27))):
        for k_, (x, y) in zip([CR, SUB], m.sea_near(p[0], p[1] + 2, 2, box=box, deep=False)):
            m.unit(army, k_, x, y)
    m.unit(1, LAN, 9, 23)                                      # (a Lander at the island's west shore: the player's way to the silos)
    m.note("hq", 5, 12, "Black Hole's HQ"); m.note("enemy_hq", 17, 13, "Andy's HQ (objective)"); m.note("enemy_hq3", 38, 12, "Max + Sami's HQ (objective)")
    return m
