"""M4 The Second Legion (Act I, fog): the river valley. A river across the middle with a bridge and a ford, woods on both banks, a marsh in the centre, two camps."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 18, 16


def mir(x, y):
    return W - 1 - x, H - 1 - y


def build():
    m = Canvas("es04", W, H)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M4 The Second Legion (FOG): take Cassius's camp HQ 2 (15,1) or rout his army. River y8 (x0..17) with two bridges (5,8) west and (13,8) east (the game's tiles allow no shoal ford in a river); "
        "marsh (the woods x7..12 on both banks, the tiles allow no river pools) is slow ground for his vehicles. Camps mirror each other (player HQ (2,14), Cassius HQ (15,1)). "
        "Player start: INF4 MECH2 TANK3 MDT2 RECON2 ART2 AA1 APC1 (about 105000); Cassius: TANK4 RECON3 MDT2 INF3 MECH1 APC1 ART1 (about 95000), 4000 funds each. "
        "Threat->answer: his fast vehicle rush -> woods banks (infantry/mech ambush cover), the two bridge chokes with ART behind; fog -> a RECON on each side; "
        "his ART -> RECONs spot it, tanks cross the ford to hit it. Day 5 scene is mission code."))
    # river across the map, bridge and ford
    m.river([(0, 8), (17, 8)])
    # woods on both banks (cover for ambushes) and the marsh
    for (x0, y0, x1, y1) in ((7, 9, 12, 10), (0, 9, 1, 10), (15, 9, 17, 10)):
        m.rect("f", x0, y0, x1, y1)
        a, b = mir(x0, y0), mir(x1, y1)
        m.rect("f", min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    # roads: from each camp to the bridge and the ford
    m.road([(5, 3), (5, 13)])
    m.road([(5, 3), (15, 3), (15, 1)])
    m.road([(13, 3), (13, 7)])
    m.road([(13, 9), (13, 12), (2, 12), (2, 14)])
    m.bridge(5, 8).bridge(13, 8)
    # properties (player, then Cassius mirrored)
    m.put("1", 2, 14).put("B", 5, 13).put("C", 8, 13).put("C", 10, 11).put("C", 2, 11)
    m.put("2", 15, 1).put("B", 12, 2).put("C", 9, 2).put("C", 7, 4).put("C", 15, 4)
    m.put("c", 6, 6).put("c", 12, 10)
    # player legion
    P = {INF: [(3, 10), (4, 11), (6, 11), (11, 10)], MECH: [(7, 10), (12, 9)], TANK: [(4, 12), (6, 12), (9, 12)], MDT: [(3, 12), (10, 12)],
         RECON: [(5, 10), (13, 11)], ART: [(3, 13), (7, 13)], AA: [(4, 13)], APC: [(6, 14)]}
    for k, cells in P.items():
        m.units(1, k, cells)
    # Cassius's cavalry: vehicles forward, mirrored on the north bank
    E = {TANK: [(13, 5), (11, 5), (8, 5), (10, 3)], RECON: [(12, 6), (4, 5), (3, 4)], MDT: [(13, 3), (8, 3)], INF: [(7, 5), (6, 4), (14, 5)],
         MECH: [(6, 5)], APC: [(11, 2)], ART: [(14, 2)]}
    for k, cells in E.items():
        m.units(2, k, cells)
    m.note("hq", 2, 14, "player HQ"); m.note("enemy_hq", 15, 1, "Cassius's camp HQ")
    m.note("bridge", 5, 8, "the bridge on the west road (x5)"); m.note("ford", 13, 8, "the east crossing (a second bridge: the lint accepts no shoal ford in a river)")
    m.note("marsh", 9, 8, "marsh: the woods x7..12 y6..10 on both banks around the river (centre of the map)")
    m.note("village_w", 6, 6, "neutral village by the bridge (north bank)"); m.note("village_e", 12, 10, "neutral village by the east bridge (south bank)")
    m.note("player_camp", 5, 13, "player base"); m.note("enemy_camp", 12, 2, "Cassius's base")
    return m
