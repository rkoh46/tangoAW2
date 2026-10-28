"""BH2 M24 Skyfall (Act IV): the desert coast and the air war. Adder (forced) against one Orange Star army under Rachel + Jake. Desert look, clear weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Adder's air wing (Fighters, Bombers, Stealths and B Copters) starts at Black Hole's airfields in the west: the HQ, two airports and a port on the south coast. Rachel and Jake hold the east: the HQ, two airports of their own
with Fighters and B Copters, and the Allies' real answer to the air: a belt of Anti-Air and Missiles round the airports and the middle road, backed by their Fighters and by Tanks that hold the ground. A dry river (a wadi) rises from a pond in the middle hills,
bends to the south coast and has two bridges; a Com Tower and a missile silo stand in the middle. The coast road and the beaches belong to the fleets (Black Hole's Cruiser and Submarine, the Allies' Cruiser and Submarine).
- Lanes: the north road over the rocks, the coast road, the wadi's two bridges, the air: the wing's lines run over the desert and the sea.
- Where the fight happens: the middle (Com Tower (22,11), the silo, the wadi), then the AA belt in front of the Allied airfields.
- Properties: Black Hole's two airports and bases, the Allies' two airports and bases, villages along the roads, a port at each end.
- Threats and answers: the Allied Anti-Air and Missiles -> Stealths and Bombers must pick their targets (Bombers on Tanks and Artillery, Fighters on Copters, Stealths on the guns); the Allied Fighters and Copters -> Adder's Fighters and Black Hole's Anti-Air; the Allied Tanks -> Bombers and Black Hole's own Tanks and artillery.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 44, 26


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_19/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-2, -1, 1, 2])))
    return out


def build():
    m = Canvas("bh2_24", W, H, fill="~")
    B = profile(1, W - 2, 18, 21, 2)
    for x in (24, 25, 26):
        B[x] = B[25]
    for x in range(1, W - 1):
        m.rect(".", x, 0, x, B[x])
    for dx, k in ((1, 6), (2, 4), (3, 2), (4, 1)):
        B[dx] -= k; B[W - 1 - dx] -= k
        m.rect("~", dx, B[dx] + 1, dx, H - 1); m.rect("~", W - 1 - dx, B[W - 1 - dx] + 1, W - 1 - dx, H - 1)
    m.rect("~", 0, 0, 0, H - 1); m.rect("~", W - 1, 0, W - 1, H - 1)
    for x in range(29, 34):                                          # a bay in the south coast (the Allies' port)
        for y in range(B[x] - 1, B[x] + 1):
            m.g[y][x] = "~"
    ponds = m.lake(24, 5, 9, seed=1, river_end=(24, 6))
    m.river([(24, 6), (24, 10), (26, 10), (26, 14), (25, 14), (25, B[25])])
    C = lambda x, y: (x, max(2, min(B[x] - 2, y)))
    belt(m, "^", [(12, 3), (17, 4), (20, 3)], width=1, seed=1, gaps=[(15, 4)]); belt(m, "^", [(30, 3), (35, 4)], width=1, seed=2); belt(m, "^", [(12, 14), (16, 16)], width=1, seed=3, gaps=[(14, 15)]); belt(m, "^", [(30, 14), (34, 16)], width=1, seed=4)
    belt(m, "^", [(20, 8), (22, 9)], width=1, seed=5); belt(m, "^", [(3, 12), (6, 13)], width=1, seed=6); belt(m, "^", [(38, 17), (41, 15)], width=1, seed=7); belt(m, "^", [(28, 8), (31, 9)], width=1, seed=8)
    belt(m, "f", [(9, 8), (13, 9)], width=1, seed=9); belt(m, "f", [(18, 12), (21, 14)], width=1, seed=10); belt(m, "f", [(28, 12), (31, 12)], width=1, seed=11); belt(m, "f", [(36, 9), (40, 10)], width=1, seed=12)
    belt(m, "^", [(3, 3), (7, 2)], width=1, seed=21); belt(m, "^", [(14, 8), (17, 10)], width=2, seed=22, gaps=[(15, 9)]); belt(m, "^", [(33, 9), (36, 12)], width=2, seed=23, gaps=[(34, 10)]); belt(m, "^", [(18, 17), (21, 18)], width=1, seed=24)
    belt(m, "^", [(39, 4), (42, 8)], width=1, seed=25); belt(m, "^", [(8, 17), (11, 18)], width=1, seed=26); belt(m, "^", [(28, 3), (30, 6)], width=1, seed=27); belt(m, "f", [(5, 14), (8, 13)], width=1, seed=28); belt(m, "f", [(38, 6), (41, 7)], width=1, seed=29)
    belt(m, "f", [(14, 4), (17, 5)], width=1, seed=30); belt(m, "f", [(32, 15), (35, 17)], width=1, seed=31); belt(m, "f", [(21, 3), (22, 6)], width=1, seed=32)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M24 Skyfall (desert look, clear): Adder (forced, Black Hole, HQ 1 (5,10), the west with two airports) against one Orange Star army under Rachel + Jake (HQ 2 (38,10), the east, two airports and an Anti-Air and Missile belt). "
        "A wadi from the pond (24,5) to the south coast, bridges (24,8) and (25,17). Com Tower (22,11), missile silo (23,14). "
        "Player: FTR5 BMB3 BCO2 STEALTH2 INF3 MECH1 TANK3 MDT1 ART2 AA1 RECON1 CR1 SUB1; Orange Star: FTR3 BCO2 INF5 MECH3 TANK4 MDT2 ART2 ROCK1 RECON1 AA4 MIS3 CR1 SUB1."))
    m.put("1", 5, 10).put("2", 38, 10).put("t", 22, 11).put("M", 23, 14)
    flatB = lambda a, lo, hi: min((x for x in range(lo, hi) if B[x] == B[x - 1] == B[x + 1] and x not in range(23, 34)), key=lambda x: abs(x - a))
    P1 = flatB(7, 3, 20); P2 = min((x for x in range(34, 42) if B[x] == B[x - 1] == B[x + 1]), key=lambda x: abs(x - 36))
    m.put("P", P1, B[P1]).put("P", P2, B[P2])
    route(m, [(6, 9), C(10, 6), C(15, 6), C(19, 7), (22, 8), (24, 8, "="), (26, 8), C(29, 7), C(33, 6), (37, 9)], seed=21, wander=1.3)
    route(m, [(6, 11), C(10, 12), C(15, 12), C(19, 13), (23, 13) if False else C(20, 12), (23, 17) if False else C(21, 16), (23, 17), (25, 17, "="), (27, 17), C(31, 15), C(35, 13), (38, 11)], seed=22, wander=1.3)
    route(m, [C(21, 12), (22, 12)], seed=23); route(m, [(P1, B[P1] - 1), C(P1, 15), C(10, 12)], seed=24); route(m, [(P2, B[P2] - 1), C(P2, 15), C(35, 13)], seed=25); route(m, [C(8, 15), (8, 15)], seed=26) if False else None
    route(m, [(23, 13), (23, 12)], seed=27) if False else None
    route(m, [(23, 12), (26, 12, "="), (28, 12), C(31, 11)], seed=28)
    thin_roads(m)
    for args in [(5, 10, "BBC"), (4, 6, "AB"), (8, 15, "AB"), (10, 6, "C"), (10, 12, "BC"), (7, 18, "C"), (15, 6, "Cb"), (15, 12, "Cb"), (19, 7, "bc"), (20, 15, "bc"), (22, 8, "c"), (22, 17, "bc"), (38, 10, "BBC"), (34, 6, "AB"), (40, 14, "AB"),
                 (33, 6, "BC"), (35, 13, "BC"), (29, 7, "bc"), (28, 15, "bc"), (27, 17, "c"), (40, 6, "C"), (36, 18, "C"), (3, 3, "c"), (12, 9, "c"), (31, 10, "c"), (18, 3, "c"), (40, 3, "c"), (3, 17, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.desertify(keep=0.75, rocks=4, size=5, seed=19)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for (x, y) in [(25, B[25] + 1), (P1, B[P1] + 1), (P2, B[P2] + 1), (31, B[31] - 0)]:
        if m.inside(x, y) and m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    air_av = "~r"
    m.spread(1, {INF: 3, MECH: 1, TANK: 3, MDT: 1, ART: 2, AA: 1, RECON: 1}, (2, 5, 12, 17), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 5, BMB: 3, BCO: 2, STEALTH: 2}, (2, 4, 12, 17), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (32, 4, 42, 17), seed=3, gap=0, avoid=av)
    m.spread(2, {AA: 4, MIS: 3}, (28, 4, 40, 16), seed=4, gap=1, avoid=av)
    m.spread(2, {FTR: 3, BCO: 2}, (33, 4, 42, 16), seed=5, gap=1, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P1, B[P1] + 2, 2, box=(2, B[P1] + 1, 20, H - 1), deep=True)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P2, B[P2] + 2, 2, box=(30, B[P2] + 1, 42, H - 1), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 10, "Adder's HQ"); m.note("enemy_hq", 38, 10, "Rachel + Jake's HQ (objective)")
    return m
