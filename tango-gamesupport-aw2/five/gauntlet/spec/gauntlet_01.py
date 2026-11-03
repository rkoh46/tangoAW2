"""Gauntlet 01, Cinder Sea (the Gauntlet mode's first map: docs/dev/gauntlet.md): a naval and air battle across an island sea. The player (Orange Star, army 1, a free CO pick) holds the south-west
island; three COs come one after another (the gauntlet engine: a later line is off the battlefield, no HQ, no units, no turn, until the line before it falls):
  1. Drake (Green Earth, army 2) holds the south-east island and the sea between from the start: a fleet, a few troops, two ports.
  2. Sensei (Yellow Comet, army 3) arrives on the north-west island when Drake's HQ falls (or his army is routed): copters and airborne infantry from two airports.
  3. Hawke (Black Hole, army 4) arrives on the volcano island in the north-east when Sensei's line falls: bombers, a Stealth, a carrier group. His HQ is the last: taking it (or routing him) wins.
Black Hole inventions: only the volcano (Hawke's island; it erupts on the ring of cells round its mountain wall: crate::gauntlet_mode). No pipes, no cannons.

Design (docs/dev/map-design.md): the sea is the terrain. Every HQ stands on an island; the only way to an HQ is a Lander, a T Copter or a Black Boat crossing the straits, so every line
falls to a combined push: ships and planes clear the way, the transports land the infantry. Reefs in the straits hide Subs and slow the push; three neutral islets in the middle (cities, a Com Tower)
are the stepping stones and the money. Each army's island has a port; the air armies (Sensei, Hawke) have airports; the player has an airport, a port and one base (infantry to capture with).
The order zigzags (south-east, north-west, north-east) so the player's fleet and air force must cross the middle sea each time.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import shore

W, H = 32, 22
HQS = {"1": (3, 18), "2": (27, 18), "3": (3, 3), "4": (29, 3)}


def build():
    m = Canvas("gauntlet_01", W, H, fill="~", campaign="gauntlet")
    # --- the four islands
    m.blob(".", 5, 17, 4, 3, seed=1, wobble=0.25)              # the player's (south-west)
    m.blob(".", 26, 17, 4, 3, seed=2, wobble=0.25)             # Drake's (south-east)
    m.blob(".", 5, 4, 4, 3, seed=3, wobble=0.25)               # Sensei's (north-west)
    m.blob(".", 25, 4, 5, 4, seed=4, wobble=0.15)              # Hawke's volcano island (north-east)
    m.rect(".", 21, 1, 30, 7)
    m.rect("~", 0, 0, W - 1, 0); m.rect("~", 0, H - 1, W - 1, H - 1)   # (open sea on the edge rows)
    # --- the middle: three islets (stepping stones) and reefs in the straits
    m.rect(".", 13, 9, 17, 11).put("~", 13, 11).put("~", 17, 9)   # the middle islet: a city, a Com Tower, a wood
    m.rect(".", 14, 2, 16, 3)                                    # the north islet
    m.rect(".", 15, 17, 17, 19).put("~", 17, 19)                 # the south islet
    # beaches (RC05, the owner's rule: a Lander can land on every island): shoal on the sea lanes' side of each islet, one for each army's approach
    m.puts(",", [(13, 2), (17, 3), (13, 11), (17, 9), (15, 8), (15, 12), (14, 18), (18, 18), (17, 19), (16, 16)])
    for x, y in ((11, 7), (19, 7), (11, 14), (20, 14), (9, 10), (22, 10), (13, 16), (18, 5), (26, 11), (5, 10)):
        m.put("r", x, y)
    # --- relief: woods and hills on the islands (cover for the landing troops)
    m.puts("f", [(2, 15), (7, 19), (24, 16), (28, 19), (25, 19), (6, 3), (2, 6), (8, 5), (16, 10)])
    m.puts("^", [(5, 15), (6, 19), (25, 15), (3, 5), (7, 3)])
    # --- Hawke's volcano: a 4 x 4 footprint (x 23..26, y 2..5) in a wall of mountains (x 22..27, y 1..6)
    m.stamp("V", 24, 4)
    # --- HQs: the player's and Drake's; Sensei's (3,3) and Hawke's (29,3) cells stay plain until they arrive (the header's `hidden 3 4`)
    m.put("1", *HQS["1"]).put("2", *HQS["2"])
    # --- properties: the player's island (a base, an airport, a port, cities), Drake's (two ports, a base, cities), the sleepers' (neutral until they arrive: their zones), the islets
    m.put("B", 5, 18).put("A", 4, 16).put("P", 8, 18).put("C", 2, 17).put("C", 7, 16)
    m.put("P", 22, 17).put("P", 29, 15).put("B", 26, 19).put("C", 27, 16).put("C", 24, 18)
    m.put("a", 6, 2).put("a", 7, 6).put("p", 9, 4).put("c", 2, 4).put("b", 4, 6)
    m.put("a", 21, 7).put("p", 30, 7).put("c", 29, 5).put("c", 28, 1).put("b", 29, 7)
    m.put("c", 14, 10).put("t", 16, 11).put("c", 15, 3).put("c", 16, 18)
    # --- short island roads from each HQ cell to its town (the islands are small: the sea is the road)
    m.line("R", [(3, 17), (6, 17)]).line("R", [(24, 17), (27, 17)]).line("R", [(3, 4), (8, 4)]).line("R", [(28, 2), (28, 6)])
    m.tidy()
    for box in ((1, 13, 10, 21), (21, 13, 31, 21), (0, 0, 11, 9), (19, 0, 31, 9)):
        shore(m, 1, box, dirs="NS")
    m.put("~", 29, 14).put("~", 30, 15)                          # (open water off Drake's east port: a ship built there can launch)
    m.header(armies=4, colours=(OS, GE, YC, BH), team=(1, 2, 2, 2), objective=[1], blackhole=True, hidden=[3, 4], comment=(
        "Gauntlet 01 Cinder Sea (normal look, no fog, 32 x 22): the player (Orange Star, army 1, HQ (3,18), a free CO) against Drake (Green Earth, army 2, HQ (27,18)), then Sensei (Yellow Comet, army 3, "
        "HQ (3,3), the north-west island) and Hawke (Black Hole, army 4, HQ (29,3), the volcano island), who come onto the battlefield in turn. Inventions: Hawke's volcano only."))
    # --- units: the player's task force and Drake's fleet (Sensei's and Hawke's waves land when they arrive: crate::gauntlet_mode)
    m.units(1, INF, [(3, 17), (6, 18), (4, 19)]).unit(1, MECH, 2, 18).unit(1, AA, 6, 17).unit(1, BCO, 5, 16).unit(1, BCO, 3, 15).unit(1, FTR, 7, 17).unit(1, TCO, 4, 18)
    for kind, (x, y) in zip((LAN, CR, SUB), m.sea_near(9, 18, 3)):
        m.unit(1, kind, x, y)
    m.units(2, INF, [(27, 17), (26, 18), (28, 18)]).unit(2, AA, 25, 17).unit(2, BCO, 28, 17).unit(2, FTR, 26, 16)
    for kind, (x, y) in zip((BS, CR, CR, SUB, SUB, LAN), m.sea_near(20, 16, 6)):
        m.unit(2, kind, x, y)
    for k, (x, y) in HQS.items():
        m.note(f"hq{k}", x, y, {"1": "the player's HQ", "2": "Drake's HQ: the first line", "3": "Sensei's HQ (hidden until Drake falls)", "4": "Hawke's HQ (hidden until Sensei falls): the last"}[k])
    m.note("volcano", 24, 4, "Hawke's volcano (anchor; footprint x 23..26, y 2..5)")
    from aw2.esmaplib import prune_road_stubs
    prune_road_stubs(m)          # (lint RD03: a road that leads nowhere goes: the only change to the map's layout since it was drawn)
    return m
