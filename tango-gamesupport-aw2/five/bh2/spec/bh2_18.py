"""BH2 M18 The Door Is Open (Act IV): Black Hole's harbour depot, under attack from the sea. Asuka + Crumb (the forced tag pair) against one Orange Star army under Hachi + Jake. Normal look (a wasteland look would turn the harbour into lava), clear.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The situation: the depot is a harbour: a bay in the south with six ports on its shores (quays), a quay district on the north shore (two rows of warehouse cities with a service road between them) and, on the west arm of the bay,
the walled point: the depot's HQ, its base district and the yard where the crate stands, shut off from the north shore by a pipe wall from the west coast to the bay with two seam gates and a long beach on its south side. Hachi and Jake land from the sea: their Landers stand off the point's south beach, their
Cruiser and Submarine off the east coast, and their beachhead (HQ, bases) holds the north-east shore. The land hangs from the map's top edge: a U round the bay, not an island. Black Hole's own Landers lie in the bay.
- Scripted fight (4b): defend the depot until Crumb, a named unit (an APC called `crumb`), reaches the crate tile `mark_crate`: the crate opens and Black Hole's reserve wakes, four Neotanks on the `mark_neo*` cells in the yard. Crumb starts at the east quay (the reinforcement column) and has to get into the point:
  by a seam gate (the wall's seams break) or across the bay in a Lander.
- Lanes: the north shore road along the warehouse rows to the wall's gates, the bay for the Landers, the long south beach, the east arm's docks.
- Where the fight happens: the wall's gates and the warehouse rows, the bay, then the yard.
- Threats and answers: Hachi's and Jake's Tanks and artillery on the north shore and B Copters -> Black Hole's Anti-Air, Tanks and the Neotanks of the reserve (the defenders start outnumbered: the point's bases and ports build more); their Landers on the south beach -> the point's artillery and Black Hole's Cruiser and Submarine.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, fix_rungs

W, H = 40, 28
NEO = [(5, 15), (7, 19), (11, 15), (11, 19)]     # the reserve's Neotanks, in the yard
CRATE = (9, 16)                                  # the crate tile


def build():
    m = Canvas("bh2_18", W, H, fill="~")
    rnd = random.Random("bh2_18/coast")
    xe = 34
    for y in range(0, 12):
        xe = max(31, min(36, xe + rnd.choice([-1, 0, 1])))
        m.rect(".", 2, y, xe, y)                                       # the land hangs from the top edge: no coast in the north
    for y in range(12, 22):
        xe = max(31, min(36, xe + rnd.choice([-1, 0, 1])))
        m.rect(".", 2, y, 14, y)
        m.rect(".", 25, y, xe - (1 if y >= 20 else 0), y)
    m.rect(".", 2, 21, 14, 21); m.rect("~", 2, 21, 3, 21)
    for y in range(12, 22):                                       # the bay (x15..24) open to the south sea
        m.rect("~", 15, y, 24, y)
    # --- the walled point: a pipe wall from the west coast to the bay (y12) with two seam gates; cliffs and woods inside the point
    m.pipe([(2, 12), (14, 12)]); m.put("Z", 6, 12).put("Z", 10, 12)
    belt(m, "^", [(3, 14), (4, 18)], width=1, seed=1); belt(m, "^", [(12, 14), (13, 17)], width=1, seed=2); belt(m, "f", [(3, 20), (6, 20)], width=1, seed=3); belt(m, "f", [(8, 14), (11, 14)], width=1, seed=4)
    for i, (cx, cy, n, ch) in enumerate([(6, 2, 3, "f"), (15, 3, 3, "^"), (24, 2, 3, "f"), (33, 2, 3, "^"), (18, 5, 3, "f"), (30, 10, 3, "f"), (8, 7, 3, "^")]):
        m.cluster(ch, cx, cy, n, seed=70 + i)
    belt(m, "f", [(18, 4), (24, 5)], width=2, seed=41); belt(m, "^", [(24, 13), (26, 17)], width=1, seed=42); belt(m, "f", [(31, 12), (33, 14)], width=1, seed=43); belt(m, "^", [(9, 8), (12, 10)], width=1, seed=44); belt(m, "f", [(2, 8), (4, 10)], width=1, seed=45)
    belt(m, "^", [(5, 4), (10, 5)], width=1, seed=5); belt(m, "^", [(28, 4), (33, 5)], width=1, seed=6, gaps=[(30, 4)]); belt(m, "^", [(27, 14), (30, 15)], width=1, seed=7); belt(m, "f", [(14, 5), (19, 4)], width=1, seed=8)
    belt(m, "f", [(26, 7), (30, 9)], width=1, seed=9); belt(m, "f", [(31, 15), (33, 19)], width=1, seed=10); belt(m, "^", [(3, 7), (6, 9)], width=1, seed=11); belt(m, "f", [(11, 6), (13, 9)], width=1, seed=12)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M18 The Door Is Open (normal look, clear): Asuka + Crumb (forced pair, Black Hole, HQ 1 (5,17), the walled point on the bay's west arm) against one Orange Star army under Hachi + Jake (HQ 2 (31,6), the north-east beachhead). The pipe wall y12 (x2..14) has seam gates (6,12) and (10,12). "
        "Six ports round the bay, warehouse rows on the north shore (rows 7 and 9). Scripted: Crumb (the named APC `crumb`, at the east quay (27,18)) must reach the crate tile mark_crate (9,16); then the reserve's four Neotanks appear on the mark_neo cells. "
        "Com Tower (20,5), missile silo (22,3). Player: INF2 MECH1 TANK3 MDT1 ART2 AA1 APC1 (crumb) CR1 SUB1 LAN2; Orange Star: INF6 MECH3 TANK5 MDT2 ART3 RECON1 BCO3 CR1 SUB1 LAN2."))
    m.put("1", 5, 17).put("2", 31, 6).put("t", 20, 5).put("M", 22, 3)
    # the quays: ports on the bay's three shores (the north shore's are neutral)
    for (x, y) in [(14, 15), (14, 18), (25, 15), (25, 18), (18, 11), (21, 11)]:
        m.put("P", x, y)
    # warehouse rows: two rows of cities with a service road between, along the north shore
    for x in range(14, 30, 2):
        m.put("C", x, 7).put("C", x, 9)
    m.rect("R", 13, 8, 30, 8)
    route(m, [(30, 8), (30, 11), (29, 14), (28, 18), (27, 18)], seed=1)
    route(m, [(13, 8), (10, 10), (10, 11), (10, 11)], seed=2) if False else route(m, [(13, 8), (11, 9), (10, 11)], seed=2)
    route(m, [(6, 11), (7, 9), (11, 8)], seed=3); route(m, [(6, 13), (7, 16), (5, 17)], seed=4); route(m, [(10, 13), (10, 16), (9, 16)], seed=5); route(m, [(7, 16), (11, 18), (13, 18), (14, 18)], seed=6)
    route(m, [(10, 16), (13, 15), (14, 15)], seed=7); route(m, [(28, 18), (26, 15), (25, 15)], seed=8); route(m, [(27, 18), (25, 18)], seed=9); route(m, [(30, 8), (31, 7)], seed=10); route(m, [(18, 8), (18, 10), (18, 11)], seed=11)
    route(m, [(21, 8), (21, 10), (21, 11)], seed=12); route(m, [(20, 8), (20, 5)], seed=13); route(m, [(22, 8), (22, 4)], seed=14) if False else None
    thin_roads(m); fix_rungs(m)
    for args in [(5, 17, "BBC"), (8, 19, "BC"), (4, 14, "C"), (12, 17, "BC"), (31, 6, "BBBC"), (33, 9, "BC"), (28, 6, "BC"), (28, 12, "BC"), (30, 17, "bc"), (33, 12, "C"), (8, 8, "C"), (6, 6, "c"), (4, 5, "cc"), (3, 2, "c"), (8, 2, "cc"), (20, 2, "cc"), (33, 16, "c"), (16, 4, "c"), (26, 19, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    for (x, y) in [CRATE] + NEO:
        if m.g[y][x] in ".fRc^":
            m.g[y][x] = "R" if (x, y) == CRATE else "."
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 20, 16, 26), dirs="NS"); shore(m, 1, (24, 20, W - 2, 26), dirs="NS")
    for (x, y) in [(15, 15), (15, 18), (24, 15), (24, 18), (18, 12), (21, 12)]:
        m.g[y][x] = "~"
    for (x, y) in [(14, 14), (14, 17), (25, 14), (25, 17), (15, 14)]:
        pass
    m.tidy()
    for (x, y) in [(19, 24), (20, 25), (8, 25), (31, 25), (12, 1), (28, 1), (37, 12), (37, 20)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve([CRATE] + NEO)
    m.spread(1, {INF: 2, MECH: 1, TANK: 3, MDT: 1, ART: 2, AA: 1}, (2, 13, 14, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 6, MECH: 3, TANK: 5, MDT: 2, ART: 3, RECON: 1, BCO: 3}, (14, 3, 34, 11), seed=2, gap=0, avoid=av)
    m.unit(1, APC, 27, 18, name="crumb")
    for k_, (x, y) in zip([LAN, LAN, CR, SUB], m.sea_near(19, 17, 4, box=(15, 13, 24, 21), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([LAN, LAN], m.sea_near(8, 23, 2, box=(2, 22, 14, 26), deep=False)):
        m.unit(2, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(37, 8, 2, box=(35, 2, 39, 14), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 17, "Asuka + Crumb's HQ"); m.note("enemy_hq", 31, 6, "Hachi + Jake's HQ (objective)"); m.note("mark_crate", CRATE[0], CRATE[1], "the crate tile: Crumb arriving here opens the crate")
    for i, (x, y) in enumerate(NEO):
        m.note(f"mark_neo{i + 1}", x, y, "reserve: a Neotank appears here")
    m.note("gate1", 6, 12, "seam gate in the point's wall"); m.note("gate2", 10, 12, "seam gate in the point's wall")
    return m
