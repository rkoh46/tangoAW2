"""M11 The Treasure Train (Act III, desert, sandstorm): bring Livia's four APCs from the harbour to the Senate's relay camp in 14 days.

Design (docs/dev/map-design.md). The situation: the convoy (apc1..apc4) and its escort start at the harbour town on the west coast (an HQ, a factory,
two airfields where the ports were); the relay camp (35..38, 9..11) lies at the east end; Lash's marauders camp in the north-east, Flak's in the
south-east, both with factories, and they hold the Marrow river's crossings.
- Lanes: three roads run east: the north road (Lash's), the Marrow road through the Pinewood in the middle, the south road (Flak's); each crosses the
  Marrow river on its own bridge, and the camp road (x34) joins all three beside the camp, so the convoy can switch roads before or after the river.
- Where the fight happens: the three bridges (the contested middle: hamlets and the ford town at the Marrow road's bridge), the ruin beyond (a neutral
  base (27,12) to build a screen near the camp), then the camp road where both marauder camps can reach.
- Properties: hamlets three cells apart along the roads (cover for the escort, money for whoever holds them), the harbour town, two marauder camps,
  forward neutral bases (15,18) on the south road and (27,12) at the ruin.
- Threats and answers: tanks and Md tanks at the bridges -> the escort's Md tanks and tanks, artillery from the west bank (short in the sandstorm: direct
  fire is the answer); rockets in the ruin -> recons see them, tanks close inside their range; marauders on the camp road -> pick the road away from them;
  no enemy aircraft: the AA watches the camp.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 40, 22
CAMP = (35, 9, 38, 11)


def build():
    m = Canvas("es11", W, H)
    m.header(armies=3, colours=(OS, YC, GE), team=[1, 2, 2], objective=[1], comment=(
        "M11 The Treasure Train (the Marrow Road): bring apc1..apc4 into the relay camp (35,9)-(38,11) by day 14; the camp's city (37,10) is the player's (mission prop). "
        "Roads: north (y4, Lash's), the Marrow road (y8..10 through the Pinewood), south (y17, Flak's), the camp road x34. The Marrow river (22,0)..(24,21) bridged at (23,4), (23,10), (24,17). "
        "Player: APC4 RECON3 TANK3 MDT2 ART2 MECH2 INF2 AA1, HQ (7,9), base (8,12), airfields (4,6) (4,15), funds 3000. Lash (37,3): INF3 TANK3 RECON2 ART1 MECH2; "
        "Flak (37,18): MDT2 TANK2 INF3 ROCK1. Sandstorm: long guns lose a cell of range."))
    # --- the coast (west): sea and a long beach
    m.rect("~", 0, 0, 1, H - 1)
    m.rect(",", 2, 0, 2, H - 1)
    # --- the Pinewood (scrub woods in the desert), rock outcrops, the ruin's walls
    for cx, cy, n, sd, ch in [(11, 6, 6, 1, "f"), (15, 7, 6, 2, "f"), (11, 12, 6, 3, "f"), (16, 12, 6, 4, "f"), (19, 6, 4, 5, "f"), (14, 15, 4, 6, "f"),
                              (5, 2, 5, 7, "^"), (12, 1, 5, 8, "^"), (19, 1, 4, 9, "^"), (7, 20, 5, 10, "^"), (17, 20, 5, 11, "^"), (27, 1, 5, 12, "^"),
                              (31, 2, 4, 13, "^"), (27, 20, 5, 14, "^"), (32, 21, 4, 15, "^"), (20, 14, 4, 16, "^"), (5, 13, 4, 17, "f"), (9, 17, 4, 18, "f"),
                              (25, 6, 4, 19, "f"), (31, 6, 4, 20, "f"), (26, 15, 4, 21, "f"), (31, 15, 4, 22, "f"), (38, 13, 3, 23, "f"), (38, 7, 3, 24, "^"),
                              (20, 10, 3, 25, "f"), (14, 3, 3, 26, "f"), (3, 19, 3, 27, "f"), (36, 20, 3, 28, "f"), (35, 1, 3, 29, "f"), (9, 3, 3, 30, "f"),
                              (13, 11, 5, 31, "f"), (17, 5, 4, 32, "f"), (10, 15, 4, 33, "f"), (4, 1, 3, 34, "^"), (15, 1, 3, 35, "^"), (12, 20, 4, 36, "^"),
                              (21, 7, 4, 37, "^"), (28, 7, 4, 38, "f"), (35, 7, 3, 39, "f"), (29, 14, 4, 40, "f"), (35, 13, 3, 41, "f"), (22, 20, 4, 42, "^"),
                              (27, 18, 3, 43, "f"), (32, 5, 3, 44, "f"), (38, 2, 3, 45, "^"), (3, 12, 3, 46, "f"), (9, 21, 3, 47, "f"), (19, 16, 4, 48, "f"),
                              (25, 2, 3, 49, "f"), (33, 15, 3, 50, "^"), (30, 21, 3, 51, "f"), (8, 6, 3, 52, "f"), (18, 12, 3, 53, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    m.puts("^", [(29, 9), (28, 10), (32, 10), (31, 13), (29, 13)])           # the ruin's broken walls
    # --- the Marrow river, north edge to south edge, three bridges
    m.river([(22, 0), (22, 2), (23, 2), (23, 13), (24, 13), (24, 21)])
    # --- roads
    for pts in ([(6, 4), (22, 4)], [(24, 4), (36, 4), (36, 3)], [(6, 4), (6, 17)], [(6, 9), (12, 9), (12, 8), (18, 8), (18, 10), (22, 10)],
                [(24, 10), (37, 10)], [(6, 17), (23, 17)], [(25, 17), (36, 17), (36, 18)], [(34, 4), (34, 17)], [(8, 9), (8, 12)], [(4, 6), (6, 6)],
                [(4, 15), (6, 15)], [(27, 10), (27, 12)], [(15, 17), (15, 18)]):
        m.road(pts)
    for x, y in ((23, 4), (23, 10), (24, 17)):
        m.put("=", x, y)
    # --- properties
    m.put("1", 7, 9).put("B", 8, 12).puts("A", [(4, 6), (4, 15)]).puts("C", [(5, 11), (9, 7), (4, 9)])
    m.put("2", 37, 3).put("B", 33, 2).puts("C", [(38, 6), (30, 3)])
    m.put("3", 37, 18).put("B", 33, 19).puts("C", [(38, 15), (30, 19)])
    m.puts("c", [(37, 10)])                                        # the relay camp's city (the mission makes it the player's)
    m.puts("b", [(15, 18), (27, 12)])
    m.puts("c", [(3, 1), (9, 1), (16, 2), (20, 6), (11, 4), (3, 4), (8, 14), (4, 18), (10, 19), (13, 16), (15, 10), (13, 6), (17, 14), (20, 12), (20, 19), (19, 2),
                 (26, 2), (30, 6), (26, 8), (30, 11), (26, 14), (29, 16), (25, 20), (31, 8), (32, 13), (37, 7), (37, 13), (39, 1), (39, 20), (36, 15), (28, 4), (21, 15)])
    m.tidy()
    # --- the convoy and its escort at the harbour
    for i, (x, y) in enumerate([(7, 10), (6, 11), (7, 11), (7, 12)]):
        m.unit(1, APC, x, y, name=f"apc{i + 1}")
    m.spread(1, {RECON: 3}, (9, 6, 14, 15), seed=1, gap=2)
    m.spread(1, {TANK: 3, MDT: 2, ART: 2}, (3, 5, 12, 16), seed=2, gap=1)
    m.spread(1, {MECH: 2, INF: 2, AA: 1}, (3, 5, 12, 16), seed=3, gap=1)
    # --- the marauders: the bridge holders, the camps' columns
    m.unit(3, MDT, 24, 9, hold=True).unit(3, MDT, 24, 11, hold=True).unit(3, ROCK, 26, 11, hold=True).unit(2, ART, 25, 5, hold=True)
    m.spread(2, {INF: 3, TANK: 2, MECH: 1}, (28, 1, 39, 7), seed=4, gap=1)
    m.spread(2, {RECON: 2, TANK: 1, MECH: 1}, (25, 6, 33, 13), seed=5, gap=1)
    m.spread(3, {INF: 3, TANK: 2}, (28, 14, 39, 21), seed=6, gap=1)
    m.note("apc1", 7, 10, "convoy APCs apc1..apc4 start at the harbour")
    m.note("hq1", 7, 9, "player HQ at the harbour"); m.note("camp_nw", 35, 9, "relay camp rectangle top-left"); m.note("camp_se", 38, 11, "relay camp bottom-right")
    m.note("ford", 23, 10, "the Marrow road's bridge (the ford town)"); m.note("bridge_n", 23, 4, "the north road's bridge"); m.note("bridge_s", 24, 17, "the south road's bridge")
    m.note("ruin", 30, 11, "the ruin and its neutral base (27,12)"); m.note("hq2", 37, 3, "Lash's camp"); m.note("hq3", 37, 18, "Flak's camp")
    return m
