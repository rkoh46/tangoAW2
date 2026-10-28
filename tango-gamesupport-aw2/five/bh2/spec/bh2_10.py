"""BH2 M10 Comet Highway (Act II): a road race across the chain of river bridges of Yellow Comet's long island (desert look, sandstorm). The forced tag pair Koal + Kindle against one Yellow Comet
army under the pair Grimm + Sensei.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the long island runs west to east. Black Hole lands on its western end (HQ, a base district, a port on the south
coast); Yellow Comet holds the eastern end (HQ, two airports for Sensei's B Copters, a port). Four rivers cross the island from coast to coast, each with a mouth on both shores and two
bridges (a north and a south bridge, the bridge row stepped by the river's jog), so the island is five reaches strung together by eight bridges. The highway Koal's army races along runs bridge to bridge.
- Lanes: the north highway and the south highway (each crosses every river on its own bridge), the cross roads that join them in the middle of each reach, the two coasts' beaches
  and the seas north and south of the island for the fleets (no Landers: the island is one landmass, a Lander would have nowhere to take an army that cannot walk). The central reach holds the two Com Towers and the missile silo.
- Where the fight happens: the bridgeheads of the second and third rivers and the central reach: whoever holds the Com Towers and the silo shapes the race.
- Properties: a town on each bridgehead (the race is for the bridges), the central reach's neutral airport and port, Yellow Comet's two airports, a port at each end.
- Threats and answers: Sensei's B Copters -> Black Hole's Anti-Air and Tanks; Grimm's Tanks and Rockets -> Md Tanks and artillery; the ships of both sides -> Cruisers and Submarines, Rockets and artillery on the beaches.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 48, 26
RIVERS = [10, 19, 29, 38]            # x of each river's north part; its south part (after the jog at y 12) is one cell east
NR, SR, MID = 8, 17, 12              # the north highway's bridge row, the south highway's, the jog


def profile(x0, x1, lo, hi, seed):
    """A coast as a staircase: runs of 3 to 6 columns at one height, stepping 1 or 2 rows (capes and bays with flat runs for the beaches)."""
    rnd = random.Random(f"bh2_07/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-2, -1, 1, 2])))
    return out


def build():
    m = Canvas("bh2_10", W, H, fill="~")
    T = profile(2, 45, 3, 6, 1)          # the north coast
    B = profile(2, 45, 20, 23, 2)        # the south coast
    for xr in RIVERS:                    # the mouths stand on straight shores: flat for three columns round each river's end
        for x in (xr - 1, xr, xr + 1):
            T[x] = T[xr]
        for x in (xr, xr + 1, xr + 2):
            B[x] = B[xr + 1]
    for dx, k in ((2, 4), (3, 2), (4, 1)):       # the island's ends taper in
        T[dx] += k; B[dx] -= k; T[47 - dx] += k; B[47 - dx] -= k
    for x in range(2, 46):
        m.rect(".", x, T[x], x, B[x])
    for xr in RIVERS:
        m.river([(xr, T[xr]), (xr, MID), (xr + 1, MID), (xr + 1, B[xr + 1])])
    L = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))        # (a waypoint kept on land: two cells inside the coast)
    # --- relief: the ranges between the rivers and the scrub belts (the desert look draws rock walls and canyon)
    belt(m, "^", [(4, 5), (8, 6)], width=1, seed=1); belt(m, "^", [(13, 20), (17, 19)], width=1, seed=2, gaps=[(15, 20)]); belt(m, "^", [(22, 5), (27, 6)], width=1, seed=3, gaps=[(24, 5)])
    belt(m, "^", [(22, 20), (27, 19)], width=1, seed=4); belt(m, "^", [(32, 5), (36, 6)], width=1, seed=5, gaps=[(34, 5)]); belt(m, "^", [(32, 20), (36, 19)], width=1, seed=6, gaps=[(34, 20)])
    belt(m, "^", [(40, 20), (44, 19)], width=1, seed=7); belt(m, "^", [(12, 4), (17, 5)], width=1, seed=8); belt(m, "^", [(13, 12), (16, 13)], width=1, seed=18)
    belt(m, "f", [(4, 18), (8, 17)], width=1, seed=9); belt(m, "f", [(12, 10), (17, 11)], width=1, seed=10); belt(m, "f", [(21, 10), (27, 11)], width=1, seed=11)
    belt(m, "f", [(31, 11), (36, 12)], width=1, seed=12); belt(m, "f", [(40, 6), (44, 7)], width=1, seed=13); belt(m, "f", [(3, 8), (5, 11)], width=1, seed=14)
    belt(m, "f", [(31, 15), (36, 16)], width=1, seed=15); belt(m, "f", [(22, 14), (26, 15)], width=1, seed=16)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M10 Comet Highway (desert look, sandstorm): Black Hole (forced pair Koal + Kindle, HQ 1 (6,12), the western end) against one Yellow Comet army under the pair Grimm + Sensei (HQ 2 (42,12), the eastern end). "
        "Four rivers (x 10, 19, 29, 38) cross the island coast to coast, each with a north bridge (row 8) and a south bridge (row 17); Com Towers (23,8) and (26,17), missile silo (25,13). "
        "Player: INF6 MECH2 TANK4 MDT1 ART2 ROCK1 RECON2 AA2 APC2 CR2 SUB1; Yellow Comet: INF6 MECH3 TANK5 MDT2 ART2 ROCK1 RECON1 BCO4 CR2 SUB1."))
    m.put("1", 6, 12).put("2", 42, 12).put("t", 23, 8).put("t", 26, 17).put("M", 25, 13)
    # --- ports on flat stretches of the south coast, a neutral port on the north coast of the middle reach
    for x in (6, 33, 41):
        m.put("P", x, B[x])
    m.put("p", 24, T[24])
    # --- the highways (each crosses every river on its own bridge: the roads reach the bridge in line) and the cross roads
    north = [(6, 11)]
    for xr in RIVERS:
        north += [(xr - 3, NR), (xr, NR, "="), (xr + 3, NR)]
    south = [(6, 13)]
    for xr in RIVERS:
        south += [(xr - 2, SR), (xr + 1, SR, "="), (xr + 4, SR)]
    route(m, [(6, 11), L(8, 9)] + north[1:] + [L(42, 9), (42, 11)], seed=1)
    route(m, [(7, 13), L(8, 16)] + south[1:] + [L(41, 16), (42, 13)], seed=2)
    route(m, [L(7, NR), (7, 11), L(8, SR)], seed=3); route(m, [L(15, NR), (15, 12), L(15, SR)], seed=4); route(m, [L(24, NR), (24, 12), L(24, SR)], seed=5); route(m, [L(34, NR), (34, 12), L(34, SR)], seed=6)
    route(m, [L(42, NR), (42, 12), L(42, SR)], seed=7)
    route(m, [(6, 13), (6, B[6] - 1)], seed=8); route(m, [L(33, SR), (33, B[33] - 1)], seed=9); route(m, [L(41, SR), (41, B[41] - 1)], seed=10); route(m, [(24, NR), (24, T[24] + 1)], seed=11)
    thin_roads(m)
    # --- towns: the bridgeheads (the race is for the bridges), the districts of the two HQs, the middle reach's airport, Yellow Comet's two airports
    town(m, 6, 12, "BBC", seed=1); town(m, 8, 16, "BC", seed=2); town(m, 4, 9, "C", seed=3); town(m, 7, 8, "CC", seed=4); town(m, 7, 19, "C", seed=5)
    town(m, 8, 8, "C", seed=6); town(m, 13, 8, "CC", seed=7); town(m, 12, 17, "C", seed=8); town(m, 15, 17, "Cb", seed=9)
    town(m, 17, 8, "C", seed=10); town(m, 21, 8, "Cb", seed=11, radius=3); town(m, 21, 17, "C", seed=12); town(m, 24, 15, "bc", seed=13)
    town(m, 25, 11, "ba", seed=14, radius=3); town(m, 31, 8, "Cb", seed=15); town(m, 32, 17, "C", seed=16)
    town(m, 35, 8, "BC", seed=17); town(m, 36, 17, "BC", seed=18); town(m, 40, 8, "C", seed=19); town(m, 41, 17, "C", seed=20)
    town(m, 42, 12, "BBC", seed=21); town(m, 44, 8, "AB", seed=22, radius=3); town(m, 44, 16, "AB", seed=23, radius=3); town(m, 40, 14, "C", seed=24); town(m, 41, 10, "C", seed=25)
    town(m, 34, 12, "C", seed=26); town(m, 15, 12, "C", seed=27)
    neutralize(m, 13)
    m.desertify(keep=0.4, rocks=0, seed=7)
    m.tidy()
    shore(m, 1, (1, 1, 46, 24), dirs="NS")
    for xr in RIVERS:                    # (the river's mouth and the ports' doors stay open water)
        m.g[T[xr] - 1][xr] = "~"; m.g[B[xr + 1] + 1][xr + 1] = "~"
    for x in (6, 33, 41):
        m.g[B[x] + 1][x] = "~"
    m.g[T[24] - 1][24] = "~"
    # --- units: the two armies and their fleets in the straits of sea
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 6, MECH: 2, TANK: 4, MDT: 1, ART: 2, ROCK: 1, RECON: 2, AA: 2, APC: 2}, (2, 5, 9, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 1, ROCK: 1, RECON: 1}, (39, 5, 45, 20), seed=2, gap=0, avoid=av)
    m.spread(2, {INF: 2, MECH: 1, TANK: 2, MDT: 1, ART: 1}, (30, 5, 37, 20), seed=3, gap=1, avoid=av)
    m.spread(2, {BCO: 4}, (39, 5, 45, 20), seed=4, gap=1, avoid=av)
    for k, (x, y) in zip([CR, CR, SUB], m.sea_near(6, B[6] + 2, 3, box=(2, B[6] + 2, 14, 25), deep=True)):
        m.unit(1, k, x, y)
    for k, (x, y) in zip([CR, CR, SUB], m.sea_near(41, B[41] + 2, 3, box=(33, B[41] + 2, 46, 25), deep=True)):
        m.unit(2, k, x, y)
    m.note("hq", 6, 12, "Black Hole's HQ"); m.note("enemy_hq", 42, 12, "Yellow Comet's HQ (objective)"); m.note("silo", 25, 13, "the missile silo of the middle reach")
    return m
