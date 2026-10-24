"""M2 Testudo (Act I): the legion holds the Dune Road ridge until Aurelia's causeway is finished. Three curving ridges, gaps with roads, the HQ behind the last."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
import random

W, H = 28, 19


def ridge(m, pts, gaps, seed, thick=0.45, wood=0.15):
    """A curving ridge of mountains along a polyline, one or two cells thick, with a few woods; `gaps` = x columns left open (the passes)."""
    rnd = random.Random(f"{m.name}/ridge{seed}")
    cells = m.path(pts)
    band = set()
    for x, y in cells:
        band.add((x, y))
        if rnd.random() < thick:
            band.add((x, y + rnd.choice((-1, 1))))
    for x, y in sorted(band):
        if x in gaps or not m.inside(x, y):
            continue
        m.put("f" if rnd.random() < wood else "^", x, y)
    return band


def build():
    m = Canvas("es02", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M2 Testudo (Dune Road ridge, province of the Marches): survive to day 9; lose if HQ 1 (3,16) falls. Enemy HQ 2 (25,2) is far NE (reachable, not an objective). "
        "Three curving ridges with passes: ridge1 passes x4 (TRAP: a walled pocket x0..6 y7..8, no way on south), x13, x22; ridge2 passes x9, x19; ridge3 passes x6, x15. "
        "The Dune river rises in the east hills and runs south to the map edge, bridged on the east road (25,12). "
        "Player start: INF4 MECH2 TANK3 MDT1 ART2 RECON1; enemy: INF4 TANK3 MDT1 RECON1 ART1 FTR1 BMB1 (air included), waves on days 3, 5, 7 from the north edge (x6..14,y0) and the east edge (27,8..10). "
        "Threat->answer: Eagle's FTR/BMB -> reinforcement AA x2 + MIS x1 (day 3), ART/MECH on ridge cover; tanks/MDT -> ridge gaps (roads) covered by ART behind "
        "and mountain infantry; enemy RECON -> own RECON; enemy ART -> RECON spotting + tanks sortie."))
    # --- hills, woods and the dunes' scrub
    rnd = random.Random("es02/world")
    # ridge1 (north, the enemy's side): passes at x4, x13, x22
    ridge(m, [(0, 7), (5, 8), (9, 6), (14, 5), (19, 7), (23, 6), (27, 7)], {4, 13, 22}, 1)
    # ridge2 (the line the legion holds)
    ridge(m, [(0, 11), (6, 10), (10, 11), (15, 10), (20, 11), (24, 10), (27, 11)], {9, 19}, 2)
    # ridge3 (the last ridge before the HQ)
    ridge(m, [(0, 14), (5, 14), (9, 13), (13, 14), (18, 14), (23, 13), (27, 14)], {6, 15}, 3)
    # the trap: a pocket behind ridge1's west pass, walled by rock on the east and south
    m.rect("^", 7, 8, 7, 9).rect("^", 0, 9, 6, 9, only=".f")
    m.rect("^", 7, 7, 7, 8)
    # mountains: massifs at the edges
    for cx, cy, n, sd in ((24, 1, 14, 1), (15, 1, 9, 2), (2, 1, 9, 3), (26, 8, 9, 4), (1, 17, 6, 5), (11, 17, 6, 6), (21, 17, 7, 7)):
        m.cluster("^", cx, cy, n, seed=sd)
    # woods behind the passes and in the fields
    for cx, cy, n, sd in ((8, 12, 7, 1), (12, 8, 8, 2), (17, 9, 6, 3), (4, 12, 5, 4), (21, 12, 6, 5), (9, 3, 7, 6), (19, 3, 7, 7), (3, 4, 6, 8), (13, 16, 6, 9),
                          (7, 16, 5, 10), (25, 16, 5, 11), (16, 12, 4, 12), (22, 4, 4, 13)):
        m.cluster("f", cx, cy, n, seed=sd)
    # --- the Dune river: from the east hills to the south edge
    rv = m.path([(26, 8), (26, 10), (25, 10), (25, 15), (24, 15), (24, 18)])
    m.put("^", 26, 7).put("^", 27, 8)
    for x, y in rv:
        m.put("-", x, y)
    # --- roads: three routes south from the enemy side, each through a pass; a lateral road behind the front
    m.road([(27, 2), (22, 2), (22, 5), (22, 8), (19, 8), (19, 12), (15, 12), (15, 15), (15, 16)])        # east route
    m.road([(13, 2), (13, 8), (9, 8), (9, 12), (6, 12), (6, 16), (3, 16)])                             # centre route to the HQ
    m.road([(0, 4), (4, 4), (4, 7), (3, 7)])                                                           # west track into the trap
    m.road([(15, 15), (9, 15), (9, 16), (6, 16)])
    m.road([(15, 16), (21, 16), (21, 12), (27, 12)])
    m.bridge(25, 12)
    # --- enemy: HQ, bases, the airport (Eagle's field)
    m.put("2", 25, 2).put("B", 21, 2).put("B", 17, 3).put("A", 24, 5).put("C", 13, 4)
    # --- player: HQ, causeway cities, a base
    m.put("1", 3, 16).put("B", 7, 17).put("C", 11, 16).put("C", 18, 16).put("C", 9, 12).put("c", 21, 8).put("c", 15, 8)
    # --- the legion on the ridges
    m.units(1, INF, [(8, 11), (11, 10), (18, 10), (21, 11)])
    m.units(1, MECH, [(5, 13), (14, 13)])
    m.units(1, TANK, [(9, 12), (19, 12), (13, 12)])
    m.unit(1, MDT, 7, 15)
    m.units(1, ART, [(6, 15), (12, 15)])
    m.unit(1, RECON, 16, 13)
    # Eagle's wing and Jess's column
    m.units(2, INF, [(21, 3), (16, 2), (24, 3), (19, 5)])
    m.units(2, TANK, [(12, 3), (14, 3), (20, 2)])
    m.units(2, MDT, [(11, 2)])
    m.unit(2, RECON, 10, 4)
    m.unit(2, ART, 18, 2)
    m.unit(2, FTR, 23, 3)
    m.unit(2, BMB, 22, 1)
    for u in m.u:
        if m.get(u['x'], u['y']) in "^-" and not (u['kind'] in (INF, MECH) and m.get(u['x'], u['y']) == "^"):
            m.put(".", u['x'], u['y'])
    # --- named places
    m.note("hq", 3, 16, "the legion's HQ: lose it and the mission is lost")
    m.note("enemy_hq", 25, 2, "Green Earth HQ, far NE; reachable by land, not an objective")
    m.note("trap_gap", 4, 7, "ridge1 west pass: leads into the pocket x0..6 y7..8, closed by rock")
    m.note("pass1b", 13, 7, "ridge1 centre pass"); m.note("pass1c", 22, 7, "ridge1 east pass")
    m.note("pass2a", 9, 11, "ridge2 west-centre pass"); m.note("pass2b", 19, 11, "ridge2 east pass")
    m.note("pass3a", 6, 14, "ridge3 west pass (road to the HQ)"); m.note("pass3b", 15, 14, "ridge3 east pass")
    m.note("dune_river", 25, 14, "the Dune river, bridged at (25,12)")
    m.lake(26, 7, 9, seed=0, river_end=(26, 8))          # (a river starts in water or at the map edge: AW2 has no source tile)
    return m
