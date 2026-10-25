"""M4 The Second Legion (Act I, fog): the Verna valley, legion against legion.

Design (docs/dev/map-design.md). The situation: two Aurean legions of equal funds (4000 each) meet in a foggy valley: Klaus's (or Aurelia's) camp in the
south-west, Cassius's in the north-east, the Verna river winding north to south between them. It is the campaign's one even fight, so the valley is
laid out point-symmetric (every village, base, wood and hill has its twin turned half round the centre); only the river's line differs.
- Lanes: three crossings: the north bridge (15,3) on the north road, the marsh bridge (15,10) on the valley road, the south bridge (16,18) on the south
  road; each camp's road ring reaches two of them directly. The marsh woods around the middle bridge hide infantry in the fog.
- Where the fight happens: the forward bases (11,7) and (20,14) on each bank, and the villages along the river (the contested middle).
- Properties: each camp has its HQ, a base and three cities; 26 neutral villages and two neutral bases, three cells apart, pay whoever pushes out.
- Threats and answers: Cassius's fast vehicles -> woods on the banks (infantry ambush cover), artillery behind the bridges; fog -> a recon each side and the
  villages as vision; his artillery -> recons find it, tanks cross at the far bridge.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 32, 22


def twin(cells):
    """The cells and their twins turned half round the valley's centre."""
    return list(cells) + [(W - 1 - x, H - 1 - y) for x, y in cells]


def build():
    m = Canvas("es04", W, H)
    m.header(armies=2, colours=(BM, OS), objective=[1], comment=(
        "M4 The Second Legion (FOG, the Verna valley): take Cassius's camp HQ 2 (28,3) or rout his army. Point-symmetric valley; the Verna river winds north to south, "
        "bridged at (15,3), (15,10), (16,18). Forward neutral bases (11,7) and (20,14). Player start: INF4 MECH2 TANK3 MDT2 RECON2 ART2 AA1 APC1; "
        "Cassius: TANK4 RECON3 MDT2 INF3 MECH1 APC1 ART1; 4000 funds each."))
    # --- hills and woods (each with its twin)
    hills = [(0, 0), (1, 0), (0, 1), (2, 0), (5, 0), (6, 0), (6, 1), (0, 4), (0, 5), (1, 5), (9, 2), (10, 2), (3, 9), (4, 9), (3, 10), (13, 5), (14, 6),
             (8, 13), (9, 12), (0, 16), (1, 16), (0, 17), (10, 21), (11, 21), (11, 20)]
    woods = [(3, 1), (4, 1), (8, 4), (8, 5), (7, 5), (3, 7), (4, 6), (13, 1), (12, 2), (11, 10), (12, 10), (12, 11), (13, 11), (13, 9), (14, 8), (14, 12),
             (6, 11), (7, 12), (2, 11), (1, 12), (10, 15), (11, 16), (6, 14), (5, 13), (14, 15), (14, 16), (2, 19), (3, 20), (8, 20), (9, 19), (13, 18), (12, 19),
             # the marsh (west bank of the middle), the copses between the villages, the hedges along the roads
             (13, 12), (14, 13), (13, 14), (12, 14), (11, 12), (14, 9), (13, 7), (12, 6), (9, 7), (9, 8), (7, 8), (6, 9), (2, 8), (2, 3), (3, 3), (6, 4), (7, 3),
             (9, 1), (12, 4), (13, 3), (1, 14), (0, 13), (3, 15), (6, 16), (7, 16), (9, 17), (10, 18), (12, 17), (5, 20), (1, 21), (9, 21), (14, 20), (8, 11),
             (2, 17), (6, 19), (11, 14)]
    for x, y in twin(hills):
        m.put("^", x, y)
    for x, y in twin(woods):
        m.put("f", x, y)
    # --- roads: each camp's ring (its own column road and the road across the top or bottom), and the valley road
    for pts in ([(4, 17), (4, 3), (27, 3)], [(27, 4), (27, 18), (4, 18)], [(4, 11), (10, 11), (10, 10), (21, 10), (21, 9), (26, 9)],
                [(5, 15), (5, 16)], [(26, 6), (26, 5)], [(7, 19), (7, 18)], [(24, 2), (24, 3)], [(11, 7), (11, 3)], [(20, 14), (20, 18)]):
        m.road(pts)
    # --- the Verna river: north to south, three bridges
    for x, y in m.path([(15, 0), (15, 6), (16, 6), (16, 9), (15, 9), (15, 12), (16, 12), (16, 21)]):
        m.put("-", x, y)
    m.bridge(15, 3).bridge(15, 10).bridge(16, 18)
    # --- properties
    m.put("1", 3, 18).put("2", 28, 3)
    for x, y in twin([(7, 19), (11, 7)]):
        m.put("B" if (x, y) in ((7, 19), (24, 2)) else "b", x, y)
    for x, y in twin([(5, 15), (2, 13), (8, 17)]):
        m.put("C", x, y)
    for x, y in twin([(7, 2), (10, 0), (2, 6), (6, 7), (10, 5), (12, 8), (8, 9), (1, 9), (12, 13), (9, 14), (13, 16), (11, 19), (13, 21), (3, 4), (5, 10), (9, 16), (14, 1)]):
        m.put("c", x, y)
    # --- the legions
    m.spread(1, {MDT: 2, ART: 2, AA: 1, APC: 1}, (1, 14, 9, 20), seed=1, gap=1)
    m.spread(1, {TANK: 3, RECON: 2}, (3, 9, 12, 19), seed=2, gap=2)
    m.spread(1, {INF: 4, MECH: 2}, (2, 10, 12, 18), seed=3, gap=1)
    m.spread(2, {MDT: 2, ART: 1, APC: 1}, (22, 1, 30, 7), seed=4, gap=1)
    m.spread(2, {TANK: 4, RECON: 3}, (19, 2, 28, 12), seed=5, gap=2)
    m.spread(2, {INF: 3, MECH: 1}, (19, 1, 29, 10), seed=6, gap=1)
    m.note("hq", 3, 18, "player HQ"); m.note("enemy_hq", 28, 3, "Cassius's camp HQ")
    m.note("bridge_n", 15, 3, "the north bridge"); m.note("bridge_c", 15, 10, "the marsh bridge"); m.note("bridge_s", 16, 18, "the south bridge")
    m.note("fwd_w", 11, 7, "neutral forward base, west bank"); m.note("fwd_e", 20, 14, "neutral forward base, east bank")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
