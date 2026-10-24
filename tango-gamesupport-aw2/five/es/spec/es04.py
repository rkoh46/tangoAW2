"""M4 The Second Legion (Act I, fog): the Verna valley. A winding river across the middle with three bridges, marshy woods on both banks around the middle one, two camps."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 32, 22


def build():
    m = Canvas("es04", W, H)
    m.header(armies=2, colours=(BM, OS), objective=[1], comment=(
        "M4 The Second Legion (FOG, the Verna valley): take Cassius's camp HQ 2 (28,3) or rout his army. The Verna river winds north to south across the middle, "
        "with three bridges: bridge_n (15,3), bridge_c (15,12) and bridge_s (16,17). The marsh (dense woods on both banks around the central bridge, x11..20, y9..15) slows his vehicles. "
        "The camps sit in opposite corners (player HQ (3,18) south-west, Cassius HQ (28,3) north-east). "
        "Player start: INF4 MECH2 TANK3 MDT2 RECON2 ART2 AA1 APC1 ; Cassius: TANK4 RECON3 MDT2 INF3 MECH1 APC1 ART1, 4000 funds each. "
        "Threat->answer: his fast vehicle rush -> woods banks (infantry/mech ambush cover), the three bridge chokes with ART behind; fog -> a RECON on each side; "
        "his ART -> RECONs spot it, tanks cross the bridges to hit it. Day 5 scene is mission code."))
    # hills and ridges
    for cx, cy, n, sd in ((2, 3, 12, 1), (9, 1, 8, 2), (7, 9, 6, 3), (30, 11, 8, 4), (24, 15, 8, 5), (20, 20, 8, 6), (29, 20, 7, 7), (21, 1, 7, 8), (1, 12, 6, 9), (12, 20, 5, 10)):
        m.cluster("^", cx, cy, n, seed=sd)
    # woods: copses and the marsh around the central bridge
    for cx, cy, n, sd in ((13, 11, 14, 1), (18, 13, 14, 2), (6, 15, 8, 3), (26, 10, 8, 4), (11, 5, 7, 5), (23, 5, 6, 6), (5, 20, 5, 7), (27, 18, 6, 8), (9, 12, 5, 9),
                          (21, 9, 5, 10), (4, 8, 5, 11), (24, 12, 5, 12), (18, 5, 5, 13), (11, 17, 5, 14)):
        m.cluster("f", cx, cy, n, seed=sd)
    # the Verna river: north to south, stepping a cell sideways between long runs
    rv = m.path([(15, 0), (15, 5), (16, 5), (16, 9), (15, 9), (15, 14), (16, 14), (16, 18), (17, 18), (17, 21)])
    for x, y in rv:
        m.put("-", x, y)
    m.put("^", 14, 0).put("^", 16, 0)
    # roads: from the camps to the three bridges
    m.road([(4, 18), (9, 18), (9, 3), (21, 3), (21, 4), (24, 4)])           # west road north over the north bridge to Cassius's camp
    m.road([(7, 18), (7, 12), (21, 12), (21, 8), (26, 8), (26, 7)])           # centre route over the marsh bridge
    m.road([(11, 18), (11, 17), (24, 17), (24, 13)])                  # south route over the south bridge
    m.bridge(15, 3).bridge(15, 12).bridge(16, 17)
    # properties: player, Cassius, neutral villages by the bridges
    m.put("1", 3, 18).put("B", 7, 19).put("C", 5, 15).put("C", 12, 18).put("C", 2, 13)
    m.put("2", 28, 3).put("B", 24, 5).put("C", 26, 6).put("C", 21, 6).put("C", 29, 7)
    m.put("c", 12, 4).put("c", 22, 14).put("c", 18, 8).put("c", 12, 14)
    # player legion: spread over the west bank
    m.spread(1, {MDT: 2, ART: 2, AA: 1, APC: 1}, (2, 14, 10, 20), seed=1, gap=1)
    m.spread(1, {TANK: 3, RECON: 2}, (5, 8, 13, 19), seed=2, gap=2)
    m.spread(1, {INF: 4, MECH: 2}, (3, 11, 12, 18), seed=3, gap=1)
    # Cassius's cavalry on the east bank
    m.spread(2, {MDT: 2, ART: 1, APC: 1}, (22, 1, 30, 7), seed=4, gap=1)
    m.spread(2, {TANK: 4, RECON: 3}, (18, 2, 28, 13), seed=5, gap=2)
    m.spread(2, {INF: 3, MECH: 1}, (18, 1, 27, 9), seed=6, gap=1)
    m.note("hq", 3, 18, "player HQ"); m.note("enemy_hq", 28, 3, "Cassius's camp HQ")
    m.note("bridge_n", 15, 3, "the north bridge (road to Cassius's camp)"); m.note("bridge_c", 15, 12, "the central bridge in the marsh")
    m.note("bridge_s", 16, 17, "the south bridge")
    m.note("marsh", 15, 11, "marsh: dense woods on both banks around the central bridge (x11..20, y9..15)")
    m.note("village_n", 12, 4, "neutral village by the north road (west bank)"); m.note("village_e", 22, 14, "neutral village on the east bank")
    m.note("player_camp", 7, 19, "player base"); m.note("enemy_camp", 24, 5, "Cassius's base")
    return m
