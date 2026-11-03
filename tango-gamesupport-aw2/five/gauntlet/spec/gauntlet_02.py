"""Gauntlet 02, Iron Crown, stage one (the Gauntlet mode's second map: docs/dev/gauntlet.md): a LAND gauntlet in five armies (the engine's five-army mode, as BH2's M31), 40 x 26 = 1040 cells. The player
(army 5, wearing the Emerald Sun skin on Black Hole's colour; a free CO) holds the south-west camp; four COs come one after another, each hidden (no HQ, no units, no turn) until the line before falls:
  1. Grit (Blue Moon, army 1) on the field from the start: the hills and river line of the west-centre, artillery and rockets behind the Aube.
  2. Jess (Green Earth, army 2): the forests and plains of the north, behind the Brenne (a river with two bridges).
  3. Kanbei (Yellow Comet, army 3): a walled highland keep in the east: a ring of mountains with two passes round a plateau.
  4. Rachel (Orange Star, army 4): the south-east lowlands, open plains and airfields behind the lake river; her HQ is the last of stage one, then the stage switch to Black Hole's keep (gauntlet_02b).
No Black Hole inventions here (the player's colour is Black Hole's: they would be the player's).

Design (docs/dev/map-design.md): a lake in the middle (x 16..18, y 12..16) is the knot of three rivers: the Aube (y 16) cuts the camp from the west-centre (bridges (4,16) and (10,16)); the Brenne (x 17) cuts the west-centre
from the north (bridges (17,4) and (17,9)); the Marle (x 17, south) cuts the camp from the lowlands (bridges (17,21) and (17,24)). East of the lake the Heath (y 12..15) is open ground joining the north, the highlands and the lowlands.
The order zigzags: north-west across the Aube (Grit), north over the Brenne (Jess), east to the keep (Kanbei), south over the Heath to the lowlands (Rachel).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 40, 26
# the HQs: army 1 Grit, 2 Jess, 3 Kanbei, 4 Rachel, 5 the player
HQS = {"1": (8, 9), "2": (24, 5), "3": (34, 6), "4": (30, 20), "5": (4, 22)}


def build():
    m = Canvas("gauntlet_02", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- water: the lake and its three rivers
    m.rect("~", 16, 12, 18, 16)
    m.river([(0, 16), (15, 16)])                                  # the Aube
    m.river([(17, 0), (17, 6), (18, 6), (18, 11)])                                  # the Brenne
    m.river([(17, 17), (17, 20), (18, 20), (18, 25)])                                 # the Marle
    for x, y in ((4, 16), (10, 16), (17, 4), (18, 9), (18, 21), (18, 24)):
        m.put("=", x, y)
    m.blob("~", 25, 24, 2, 1, seed=3, wobble=0.3)                 # a tarn in the lowlands
    m.blob("~", 6, 3, 2, 1, seed=4, wobble=0.3)                   # a tarn in Grit's north
    # --- Grit's hills and woods (west-centre): a ridge north of his keep, hills on the river bank
    for i, pts in enumerate([[(2, 3), (7, 2)], [(10, 3), (14, 4)], [(2, 12), (5, 13)], [(11, 12), (14, 13)], [(13, 7), (14, 10)]]):
        belt(m, "^", pts, width=1, seed=10 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(4, 7, 3), (12, 8, 3), (7, 13, 3)]):
        m.cluster("f", cx, cy, n * 3, seed=20 + i)
    # --- Jess's forests (north): big woods and a few ridges
    for i, (cx, cy, n) in enumerate([(21, 3, 5), (27, 3, 5), (22, 9, 4), (28, 8, 5), (20, 6, 3)]):
        m.cluster("f", cx, cy, n * 3, seed=30 + i)
    belt(m, "f", [(19, 1), (26, 1)], width=1, seed=36); belt(m, "^", [(21, 12), (25, 12)], width=1, seed=37, p=0.9)
    # --- Kanbei's keep: a ring of mountains with two passes, ridges outside
    m.rect("^", 30, 2, 38, 10); m.rect(".", 31, 3, 37, 9)
    m.put(".", 30, 5).put(".", 36, 10).put("f", 33, 8).put("f", 32, 4).put("f", 36, 3)
    m.put(".", 30, 2).put(".", 38, 2).put(".", 38, 10).put("f", 30, 10)
    belt(m, "^", [(39, 12), (35, 13)], width=1, seed=40, p=0.9); belt(m, "^", [(29, 11), (27, 13)], width=1, seed=41, p=0.9)
    # --- Rachel's lowlands: open, a few tree lines and rocks
    for i, (cx, cy, n) in enumerate([(23, 18, 3), (35, 17, 3), (26, 22, 2), (36, 23, 3)]):
        m.cluster("f", cx, cy, n * 2, seed=50 + i)
    for i, (cx, cy, n) in enumerate([(33, 15, 2), (21, 20, 2), (28, 15, 2)]):
        m.cluster("^", cx, cy, n * 2, seed=60 + i)
    # --- the camp's trees and rocks
    belt(m, "f", [(1, 19), (6, 19)], width=1, seed=70); belt(m, "^", [(12, 19), (14, 22)], width=1, seed=71); belt(m, "f", [(2, 24), (8, 25)], width=1, seed=72)
    m.header(armies=5, colours=(BM, GE, YC, OS, BH), team=(2, 2, 2, 2, 1), objective=[5], zones=[(5, 0, 17, 10, 25)], hidden=[2, 3, 4], comment=(
        "Gauntlet 02 Iron Crown, stage one (normal look, no fog, 40 x 26, five armies): the player (army 5, Black Hole's colour wearing the Emerald Sun skin, HQ 5 (4,22), south-west, a free CO) against Grit (Blue Moon, army 1, HQ (8,9), "
        "the west-centre), then Jess (Green Earth, army 2, HQ (24,5), the north), Kanbei (Yellow Comet, army 3, HQ (34,6), the highland keep) and Rachel (Orange Star, army 4, HQ (30,20), the south-east lowlands), "
        "who come onto the battlefield in turn (their HQ cells are plain until then; their zones' neutral towns become theirs). Rivers: the Aube (y 16, bridges (4,16) (10,16)), the Brenne (x 17, bridges (17,4) (18,9)), "
        "the Marle (x 17, bridges (18,21) (18,24)), round a lake (x 16..18, y 12..16). Com Towers (11,6), (23,10) and (27,19). No inventions."))
    m.put(".", *HQS["2"]).put(".", *HQS["3"]).put(".", *HQS["4"]).put("1", *HQS["1"]).put("5", *HQS["5"])
    m.put("t", 11, 6).put("t", 23, 10).put("t", 27, 19)
    # --- roads
    route(m, [S(4, 21), (4, 17), (4, 16, "="), (4, 15), S(6, 12), S(8, 10)], seed=1, wander=0.6)
    route(m, [S(9, 21), S(10, 18), (10, 17), (10, 16, "="), (10, 15), S(11, 12), S(9, 10)], seed=2, wander=0.6)
    route(m, [S(8, 9), S(12, 9), (17, 9), (18, 9, "="), (19, 9), S(21, 8), S(24, 6)], seed=3, wander=0.6)
    route(m, [S(11, 4), (16, 4), (17, 4, "="), (18, 4), S(22, 4), S(24, 5)], seed=4, wander=0.6)
    route(m, [S(8, 9), S(8, 5), S(11, 4)], seed=5, wander=0.5)
    route(m, [S(24, 5), S(28, 5), (29, 5), (30, 5), (31, 5), S(33, 6), S(34, 6)], seed=6, wander=0.4)
    route(m, [S(34, 6), S(36, 8), (36, 9), (36, 10), (36, 11), S(35, 14), S(32, 18), S(30, 20)], seed=7, wander=0.6)
    route(m, [S(24, 6), S(23, 10), S(24, 13), S(26, 15), S(28, 17), S(30, 20)], seed=8, wander=0.7)
    route(m, [S(10, 22), (17, 21), (18, 21, "="), (19, 21), S(24, 21), S(30, 20)], seed=9, wander=0.6)
    route(m, [S(9, 24), (17, 24), (18, 24, "="), (19, 24), S(24, 23), S(30, 22)], seed=10, wander=0.6)
    route(m, [S(30, 20), S(36, 20), S(37, 23)], seed=11); route(m, [S(30, 20), S(26, 18), S(22, 18)], seed=12)
    route(m, [S(10, 22), S(4, 22)], seed=13)
    thin_roads(m); fix_rungs(m)
    # --- properties: Grit's keep and the camp are owned (capitals); the zones of the three sleepers and the field are neutral
    for args in [(4, 22, "BBC"), (8, 20, "BC"), (6, 24, "C"), (2, 20, "BC"), (12, 23, "C"),
                 (8, 9, "BBBC"), (5, 11, "BC"), (11, 11, "BC"), (7, 5, "C"), (12, 5, "C"), (3, 8, "C"),
                 (13, 14, "c"), (3, 14, "c"), (7, 15, "c"),
                 (24, 5, "bbc"), (20, 8, "c"), (28, 7, "cb"), (22, 2, "c"), (27, 2, "c"), (26, 10, "cb"), (19, 11, "c"),
                 (34, 6, "bbbc"), (32, 4, "bc"), (36, 8, "bc"), (31, 8, "c"), (37, 5, "c"), (35, 13, "c"), (31, 12, "c"),
                 (30, 20, "bbac"), (34, 18, "ab"), (34, 22, "ab"), (26, 20, "c"), (28, 23, "cb"), (22, 17, "c"), (22, 22, "c"), (37, 21, "c"), (24, 14, "c"), (21, 24, "c"), (38, 18, "a"),
                 (14, 18, "c"), (15, 22, "c"), (20, 14, "b")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    for y in range(17, 26):
        for x in range(0, 14):
            if m.g[y][x] in "bcap":
                m.g[y][x] = m.g[y][x].upper()
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 19, 12, 25), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 3, BCO: 2}, (1, 19, 12, 25), seed=2, gap=1, avoid=av)
    # Grit: infantry and mech on the keep and the banks, tanks, artillery and rockets behind the Aube and the ridge
    m.spread(1, {INF: 6, MECH: 3, TANK: 5, MDT: 3, ART: 4, ROCK: 3, RECON: 1, AA: 2}, (2, 3, 15, 11), seed=3, gap=0, avoid=av)
    m.note("hq1", *HQS["1"], "Grit's HQ (Blue Moon): the first line, on the field from the start")
    m.note("hq2", *HQS["2"], "Jess's HQ (Green Earth, hidden until Grit falls)")
    m.note("hq3", *HQS["3"], "Kanbei's HQ (Yellow Comet, hidden until Jess falls)")
    m.note("hq4", *HQS["4"], "Rachel's HQ (Orange Star, hidden until Kanbei falls): the last of stage one")
    m.note("hq5", *HQS["5"], "the player's HQ")
    from aw2.esmaplib import prune_road_stubs
    prune_road_stubs(m)          # (lint RD03: a road that leads nowhere goes: the only change to the map's layout since it was drawn)
    return m
