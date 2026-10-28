"""BH2 M15 Every Colour (Act IV): the Orange Star border plains. A free pair against one Orange Star army under the tag pair Max + Sami. Normal look, clear weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole's invasion crosses the border into Orange Star's farm plains. The Black Hole column holds the west (HQ and a base district, a port on the south coast); Max and Sami hold the east (HQ, a base district,
a port on the south coast). Two rivers cut the plains: the first rises from a pond in the western hills and bends down to the south coast; the second comes from the north coast and bends down to the south coast. Each has three bridges, so there are
three highways (north, middle, south) and every one of them crosses both rivers. The middle of the plains holds the two Com Towers and the missile silo.
- Lanes: the three highways, the bridgeheads of both rivers, the hills round the pond, the ridge in the east, the coasts' beaches for the fleets.
- Where the fight happens: the first river's bridges and the Com Towers (24,9) and (24,16), then the second river's bridges.
- Properties: a village at each bridgehead, farm towns between, the two HQ districts, a neutral port on the north coast.
- Threats and answers: Max's Tanks and Md Tanks, Sami's foot soldiers -> Black Hole's Md Tanks, Rockets and artillery on the near bank; Orange Star fields no air, so neither army fields Anti-Air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 46, 26


def profile(x0, x1, lo, hi, seed, steps=(-2, -1, 1, 2)):
    rnd = random.Random(f"bh2_15/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice(steps)))
    return out


def build():
    m = Canvas("bh2_15", W, H, fill="~")
    T = profile(0, W - 1, 2, 4, 1); B = profile(0, W - 1, 21, 23, 2)
    for x in (29, 30, 31):
        T[x] = T[30]
    for x in (17, 18, 19, 30, 31, 32):
        B[x] = B[18]
    for x in range(W):
        m.rect(".", x, T[x], x, B[x])
    for dx, k in ((0, 5), (1, 3), (2, 1)):                  # the ends taper: capes at the two map edges
        T[dx] += k; B[dx] -= k; T[W - 1 - dx] += k; B[W - 1 - dx] -= k
        m.rect("~", dx, 0, dx, T[dx] - 1); m.rect("~", dx, B[dx] + 1, dx, H - 1)
        m.rect("~", W - 1 - dx, 0, W - 1 - dx, T[W - 1 - dx] - 1); m.rect("~", W - 1 - dx, B[W - 1 - dx] + 1, W - 1 - dx, H - 1)
    ponds = m.lake(17, 6, 9, seed=1, river_end=(17, 7))
    m.river([(17, 7), (17, 11), (19, 11), (19, 15), (18, 15), (18, B[18])])
    m.river([(30, T[30]), (30, 9), (32, 9), (32, 14), (31, 14), (31, B[31])])
    C = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    belt(m, "^", [(12, 5), (15, 6)], width=1, seed=1); belt(m, "^", [(6, 17), (10, 19)], width=1, seed=2, gaps=[(8, 18)]); belt(m, "^", [(22, 5), (27, 6)], width=1, seed=3, gaps=[(24, 5)])
    belt(m, "^", [(22, 19), (27, 20)], width=1, seed=4); belt(m, "^", [(36, 6), (40, 8)], width=1, seed=5); belt(m, "^", [(35, 17), (39, 19)], width=1, seed=6, gaps=[(37, 18)]); belt(m, "^", [(3, 6), (6, 8)], width=1, seed=7)
    belt(m, "f", [(4, 10), (8, 11)], width=1, seed=8); belt(m, "f", [(12, 14), (15, 16)], width=1, seed=9); belt(m, "f", [(22, 11), (27, 12)], width=1, seed=10); belt(m, "f", [(34, 11), (38, 13)], width=1, seed=11)
    belt(m, "f", [(21, 16), (26, 17)], width=1, seed=12); belt(m, "f", [(40, 14), (43, 16)], width=1, seed=13); belt(m, "f", [(35, 5), (38, 4)], width=1, seed=14); belt(m, "f", [(11, 8), (14, 10)], width=1, seed=15)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M15 Every Colour (normal look, clear): a free pair (Black Hole, HQ 1 (5,12), the west) against one Orange Star army under Max + Sami (HQ 2 (40,12), the east). Two rivers: the first from the pond (17,6) to the south coast, "
        "bridges (17,9), (19,13), (18,18); the second from the north coast to the south coast, bridges (30,7), (32,12), (31,18). Com Towers (24,9) and (24,16), missile silo (25,12). "
        "Player: INF5 MECH2 TANK5 MDT2 ART3 ROCK1 RECON1 APC1 CR1 SUB1; Orange Star: INF6 MECH4 TANK6 MDT2 ART3 ROCK2 RECON1 CR1 SUB1."))
    m.put("1", 5, 12).put("2", 40, 12).put("t", 24, 9).put("t", 24, 16).put("M", 25, 12)
    flatB = lambda a, lo, hi: min((x for x in range(lo, hi) if B[x] == B[x - 1] == B[x + 1] and x not in (17, 18, 19, 30, 31, 32)), key=lambda x: abs(x - a))
    P1, P2 = flatB(8, 3, 15), flatB(38, 34, 43)
    m.put("P", P1, B[P1]).put("P", P2, B[P2]).put("p", 24, T[24]) if T[24] == T[23] == T[25] else m.put("P", P1, B[P1]).put("P", P2, B[P2])
    nh = [(6, 11), C(10, 10), C(14, 9), (15, 9), (17, 9, "="), C(20, 8), C(24, 8), (28, 7), (30, 7, "="), C(33, 7), C(37, 9), (40, 11)]
    mh = [(6, 13), C(10, 13), C(15, 14), (17, 13), (19, 13, "="), (21, 13), C(24, 13), C(28, 12), (30, 12), (32, 12, "="), (34, 12), C(37, 12), (39, 12)]
    sh = [(6, 13), C(8, 16), C(12, 18), (16, 18), (18, 18, "="), (20, 18), C(24, 18), C(27, 19), (29, 18), (31, 18, "="), (33, 18), C(37, 17), C(39, 15), (40, 13)]
    route(m, nh, seed=21, wander=1.3); route(m, mh, seed=22, wander=1.3); route(m, sh, seed=23, wander=1.3)
    route(m, [C(24, 8), (24, 9)], seed=24); route(m, [C(24, 13), (24, 15)], seed=25); route(m, [(P1, B[P1] - 1), C(P1, 16), C(8, 16)], seed=26); route(m, [(P2, B[P2] - 1), C(P2, 17), C(36, 18)], seed=27)
    route(m, [C(24, 8), C(24, T[24] + 2)], seed=28); route(m, [C(8, 9), C(9, 6), C(10, 5)], seed=29); route(m, [C(4, 9), C(4, 5)], seed=30); route(m, [C(14, 9), C(14, 4)], seed=31)
    thin_roads(m)
    k = 0
    for bx, by in [(17, 9), (19, 13), (18, 18), (30, 7), (32, 12), (31, 18)]:
        for dx, kinds in ((-3, "C"), (3, "Cb")):
            k += 1
            try:
                town(m, bx + dx, by, kinds, seed=100 + k, radius=3)
            except ValueError:
                pass
    for args in [(5, 12, "BBC"), (8, 15, "BC"), (4, 9, "C"), (8, 9, "BC"), (6, 19, "C"), (40, 12, "BBC"), (42, 9, "BC"), (38, 15, "BC"), (43, 13, "C"), (40, 19, "C"), (36, 9, "C"),
                 (13, 12, "C"), (22, 12, "bc"), (26, 15, "bc"), (24, 19, "c"), (24, 6, "c"), (12, 20, "c"), (36, 21, "c"), (10, 5, "c"), (4, 5, "cc"), (14, 4, "c"), (44, 7, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for (x, y) in [(18, B[18] + 1), (31, B[31] + 1), (30, T[30] - 1), (P1, B[P1] + 1), (P2, B[P2] + 1), (24, T[24] - 1)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(10, 24), (26, 24), (36, 1), (14, 1)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 5, MDT: 2, ART: 3, ROCK: 1, RECON: 1, APC: 1}, (2, 6, 14, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 6, MECH: 4, TANK: 6, MDT: 2, ART: 3, ROCK: 2, RECON: 1}, (35, 5, 44, 20), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P1, B[P1] + 2, 2, box=(2, B[P1] + 1, 16, H - 1), deep=True)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P2, B[P2] + 2, 2, box=(30, B[P2] + 1, 44, H - 1), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 12, "Black Hole's HQ"); m.note("enemy_hq", 40, 12, "Max + Sami's HQ (objective)"); m.note("silo", 25, 12, "the missile silo of the plains")
    return m
