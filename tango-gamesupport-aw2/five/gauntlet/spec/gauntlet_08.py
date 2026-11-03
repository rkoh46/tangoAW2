"""Gauntlet 08, Tidewater Atoll (docs/dev/gauntlet.md): an island and naval gauntlet of two lines, 30 x 20, three armies. The player (army 1, a free CO pick) holds the western island:
  1. Eagle (Green Earth, army 2) holds the north-east island and the water round it from the start: airfields, a port, a few troops, fighters.
  2. Adder (Black Hole, army 3) arrives on the south-east island when Eagle's line falls (his HQ taken or his army routed): a fleet in its harbour, bombers and troops.
No Black Hole inventions.

Design (docs/dev/map-design.md): the sea is the terrain. Three big islands (west, north-east, south-east) and four islets between them (north-west, the middle one, the south one and a reef cay) are the whole land; every island has
a beach (shoals, `,`) on the side its enemies come from and a port, so a Lander or a Black Boat can always land troops (lint RC05); reefs in the straits hide Subs. The middle islet's two cities and Com Tower are the stepping
stone every army fights for. The order sends the player's fleet north-east to Eagle, then south over the middle islets to Adder's harbour.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import shore, prune_road_stubs, land_rows

W, H = 30, 20
HQS = {"1": (3, 14), "2": (25, 4), "3": (25, 15)}


def build():
    m = Canvas("gauntlet_08", W, H, fill="~", campaign="gauntlet")
    # --- the three big islands and the islets (a coastline written row by row: straight east and west faces for the ports, north and south faces for the beaches)
    big = {0: (3, 7), 1: (2, 8), 2: (1, 9), 3: (1, 9), 4: (1, 9), 5: (1, 9), 6: (2, 8), 7: (3, 7)}
    land_rows(m, {10 + y: r for y, r in big.items()})                                                   # the player's island (west, y 10..17)
    land_rows(m, {1 + y: (r[0] + 19, r[1] + 19) for y, r in big.items()})                               # Eagle's island (north-east, x 20..28, y 1..8)
    land_rows(m, {11 + y: (r[0] + 19, r[1] + 19) for y, r in big.items() if y < 7})                     # Adder's island (south-east, x 20..28, y 11..17)
    land_rows(m, {2: (6, 9), 3: (5, 10), 4: (5, 10), 5: (6, 9)})                                       # the north-west islet
    land_rows(m, {8: (14, 16), 9: (13, 17), 10: (13, 17), 11: (13, 17), 12: (14, 16)})                 # the middle islet
    land_rows(m, {16: (13, 15), 17: (12, 16), 18: (13, 15)})                                           # the south islet
    # --- relief on the islands (cover for landing troops)
    m.puts("f", [(2, 12), (7, 16), (22, 3), (27, 5), (26, 16), (22, 13), (7, 3), (15, 9), (4, 11), (24, 7), (21, 12)])
    m.puts("^", [(6, 12), (23, 6), (27, 3), (22, 15), (26, 13), (8, 4), (8, 15), (24, 2)])
    for x, y in ((11, 12), (9, 19), (18, 7), (18, 13), (18, 18), (17, 3), (12, 6), (11, 8), (28, 9), (3, 8)):
        m.put("r", x, y)                                          # reefs in the straits
    for i, box in enumerate(((1, 10, 9, 17), (20, 1, 28, 8), (20, 11, 28, 17), (5, 2, 10, 5), (13, 8, 17, 12), (12, 16, 16, 18))):
        m.scatter("f", box, 0.22, seed=10 + i); m.scatter("^", box, 0.12, seed=20 + i)
    m.header(armies=3, colours=(OS, GE, BH), team=(1, 2, 2), objective=[1], hidden=[3], comment=(
        "Gauntlet 08 Tidewater Atoll (normal look, no fog, 30 x 20, three armies): the player (army 1, HQ (3,14), the west island, a free CO) against Eagle (Green Earth, army 2, HQ (25,4), the north-east island), then Adder "
        "(Black Hole, army 3, HQ (25,15), the south-east island), who comes onto the battlefield when Eagle's line falls. Islets: north-west (7,4), middle (15,10), south (14,17). Com Tower (16,10). No inventions."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put(".", *HQS["3"])
    # --- properties: each island has a base, an airport, a port and cities (the sleeper's neutral: lower case)
    m.put("B", 5, 14).put("A", 4, 11).put("P", 9, 14).put("C", 2, 15).put("C", 6, 16).put("C", 3, 12)
    m.put("A", 22, 4).put("B", 24, 3).put("P", 20, 4).put("C", 23, 5).put("C", 26, 2).put("A", 25, 7).put("P", 28, 4)
    m.put("b", 24, 15).put("a", 22, 13).put("p", 20, 15).put("p", 28, 14).put("c", 25, 17).put("c", 26, 13).put("c", 22, 16)
    m.put("c", 7, 3).put("a", 9, 4).put("c", 15, 9).put("t", 15, 10).put("c", 14, 11).put("c", 14, 17).put("p", 5, 4)
    # --- short island roads from each HQ to its town
    m.line("R", [(3, 14), (9, 14)]).line("R", [(20, 4), (25, 4), (25, 7)]).line("R", [(24, 3), (24, 4)]).line("R", [(20, 15), (25, 15), (25, 17)]).line("R", [(5, 14), (5, 12), (4, 12)])
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    # --- units: the player's task force and Eagle's air wing and fleet (Adder's wave lands when he arrives: crate::gauntlet_mode)
    m.units(1, INF, [(3, 13), (6, 15), (4, 15)]).unit(1, MECH, 2, 14).unit(1, AA, 6, 14).unit(1, BCO, 5, 13).unit(1, BCO, 3, 16).unit(1, FTR, 7, 15).unit(1, TCO, 4, 14)
    for kind, (x, y) in zip((LAN, CR, SUB), m.sea_near(11, 14, 3)):
        m.unit(1, kind, x, y)
    m.units(2, INF, [(25, 3), (24, 5), (26, 4)]).unit(2, AA, 23, 4).unit(2, BCO, 26, 3).unit(2, FTR, 24, 2).unit(2, FTR, 25, 5).unit(2, BMB, 27, 5).unit(2, MECH, 22, 5).unit(2, TANK, 26, 5).unit(2, ART, 22, 6).unit(2, ROCK, 27, 6)
    for kind, (x, y) in zip((BS, CR, CR, SUB, LAN), m.sea_near(20, 5, 5)):
        m.unit(2, kind, x, y)
    for k, t in {"1": "the player's HQ", "2": "Eagle's HQ (Green Earth): the first line", "3": "Adder's HQ (Black Hole, hidden until Eagle falls): the last"}.items():
        m.note(f"hq{k}", *HQS[k], t)
    prune_road_stubs(m)
    return m
