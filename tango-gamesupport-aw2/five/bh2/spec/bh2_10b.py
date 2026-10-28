"""BH2 M10 Two Tides (Act II), front 2: Grimm's isles on the same blasted ground (the Wasteland look, fog). A free CO pick (the player's second front) against Grimm. (Front 1 is bh2_10.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4; the second front of a two-front mission is a map of its own, as BH2 M4's). The situation: a small island pinched at the waist by a tide of lava from the west and one from the
east: Black Hole lands in the south (HQ, a base district, the road along the south coast), Grimm holds the north (HQ, a base and a ridge of mountains and ash woods in front of it). The waist between the tides is the whole
front: a belt twelve cells wide with a Com Tower on it. A lava-locked isle off the west tide (a missile silo and a village) hangs on a long bridge. No sea here (lava): no port, no ship, and no air.
- Lanes: the belt's two roads, the ridge's passes in front of Grimm's HQ, the south coast road, the long bridge to the silo.
- Where the fight happens: the belt's Com Tower, then the ridge.
- Threats and answers: Grimm's Tanks and Rockets -> Md Tanks, artillery and Rockets; Black Hole fields no aircraft, so Grimm fields no Anti-Air.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 32, 26


def build():
    m = Canvas("bh2_10b", W, H, fill="~")
    XW = [9, 5, 3, 2, 3, 5, 6, 4, 2, 2, 3, 5, 3, 2, 2, 3, 4, 6, 8, 11, 12, 13]
    XE = [24, 28, 29, 30, 30, 28, 27, 28, 29, 30, 30, 29, 29, 30, 30, 29, 27, 26, 25, 22, 20, 19]
    for y in range(1, 23):
        m.rect(".", XW[y - 1], y, XE[y - 1], y)
    land_rows(m, {y: (x0, x1) for y, (x0, x1) in {8: (0, 4), 9: (0, 6), 10: (0, 9), 11: (0, 9), 12: (0, 10), 13: (0, 9), 14: (0, 8), 15: (0, 6), 16: (0, 4)}.items()}, ch="~")   # the west tide
    land_rows(m, {y: (x0, x1) for y, (x0, x1) in {8: (28, 31), 9: (26, 31), 10: (24, 31), 11: (23, 31), 12: (22, 31), 13: (23, 31), 14: (24, 31), 15: (26, 31), 16: (28, 31)}.items()}, ch="~")  # the east tide
    land_rows(m, {10: (2, 4), 11: (1, 5), 12: (2, 4)})                                                                                                 # the silo isle in the west tide
    # --- relief
    belt(m, "^", [(11, 7), (16, 8), (21, 7)], width=1, seed=1, gaps=[(14, 8), (18, 8)]); belt(m, "^", [(4, 5), (8, 4)], width=1, seed=2); belt(m, "^", [(23, 4), (28, 6)], width=1, seed=3, gaps=[(26, 5)])
    belt(m, "^", [(5, 19), (9, 18)], width=1, seed=4); belt(m, "^", [(22, 18), (26, 19)], width=1, seed=5, gaps=[(24, 18)]); belt(m, "^", [(12, 16), (14, 15)], width=1, seed=6)
    belt(m, "f", [(8, 6), (11, 5)], width=1, seed=7); belt(m, "f", [(18, 5), (21, 4)], width=1, seed=8); belt(m, "f", [(11, 12), (13, 11)], width=1, seed=9); belt(m, "f", [(19, 14), (21, 15)], width=1, seed=10)
    belt(m, "f", [(9, 20), (13, 19)], width=1, seed=11); belt(m, "^", [(25, 13), (28, 14)], width=1, seed=13); belt(m, "f", [(3, 17), (6, 18)], width=1, seed=14); belt(m, "f", [(25, 11), (27, 11)], width=1, seed=15); belt(m, "^", [(3, 14), (5, 16)], width=1, seed=16); belt(m, "f", [(18, 21), (21, 20)], width=1, seed=12)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M10 Two Tides, front 2 (Wasteland look, fog, no sea: the water is lava): a free CO pick (Black Hole, HQ 1 (15,19), the south) against Grimm (Yellow Comet, HQ 2 (16,4), the north). The waist between the tides (x 10..21, y 8..16) carries the Com Tower (16,12); "
        "the silo isle (3,11) hangs on a long bridge off the west tide. Player: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1; Grimm: INF3 MECH2 TANK4 MDT2 ART2 ROCK1."))
    m.put("1", 15, 19).put("2", 16, 4).put("t", 16, 12).put("M", 3, 11)
    m.bridge(6, 11, 9, 11)
    C = lambda x, y: (max(XW[y - 1] + 1, min(XE[y - 1] - 1, x)), y)
    route(m, [C(15, 18), C(14, 14), C(15, 11), C(16, 8), C(16, 5)], seed=1); route(m, [C(11, 19), C(9, 15), C(11, 8), C(13, 5)], seed=2); route(m, [C(17, 18), C(20, 14), C(21, 9), C(19, 5)], seed=3)
    route(m, [C(15, 19), C(10, 20), C(6, 21)], seed=4); route(m, [C(16, 4), C(22, 3), C(26, 5)], seed=5); route(m, [C(10, 11), C(10, 11)], seed=6) if False else None
    route(m, [(10, 11), (9, 11)], seed=7); route(m, [C(15, 19), C(20, 20), C(24, 20)], seed=8)
    route(m, [C(13, 5), C(9, 4), C(5, 5), C(4, 7)], seed=9); route(m, [C(7, 20), C(5, 19)], seed=10)
    thin_roads(m)
    town(m, 15, 19, "BBC", seed=1); town(m, 12, 20, "BC", seed=2); town(m, 18, 20, "BC", seed=3); town(m, 7, 20, "C", seed=4); town(m, 24, 20, "C", seed=5)
    town(m, 16, 4, "BBC", seed=6); town(m, 13, 5, "BC", seed=7); town(m, 19, 5, "C", seed=8); town(m, 25, 5, "C", seed=9); town(m, 9, 4, "C", seed=10)
    town(m, 13, 12, "Cb", seed=11); town(m, 19, 12, "Cb", seed=12); town(m, 10, 10, "c", seed=13); town(m, 3, 11, "c", seed=14); town(m, 22, 8, "C", seed=15); town(m, 4, 5, "cc", seed=16)
    neutralize(m, 12)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (3, 15, 27, 21), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 3, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1}, (4, 2, 28, 7), seed=2, gap=0, avoid=av)
    m.note("hq", 15, 19, "the second front's Black Hole HQ"); m.note("enemy_hq", 16, 4, "Grimm's HQ (objective)"); m.note("belt", 16, 12, "the waist's Com Tower")
    return m
