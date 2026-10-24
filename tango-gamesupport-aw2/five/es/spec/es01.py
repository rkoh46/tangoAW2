"""M1 Landfall (Act I): Klaus's legion lands on the Cape Astra shore. The fleet's sandbar in the south, a wide jagged beach with coves, the Astra river valley, the coast road, the fort on its ridge."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 30, 27
COAST = [16, 16, 17, 17, 15, 14, 14, 14, 15, 16, 17, 18, 18, 18, 19, 18, 18, 17, 16, 15, 14, 14, 14, 15, 16, 17, 17, 16, 15, 15]


def tidy(m):
    """Shoal cells the game has no tile for (a lone ford, shoal with land all round) become plain."""
    import map as mappy
    for _ in range(30):
        bad = False
        for y in range(m.h):
            for x in range(m.w):
                if m.g[y][x] == ",":
                    look = [m.get(a, b) if m.inside(a, b) else "," for a, b in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))]
                    try:
                        mappy.water_tile(",", look)
                    except AssertionError:
                        m.g[y][x] = "."
                        bad = True
        if not bad:
            break


def build():
    m = Canvas("es01", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M1 Landfall (province of Cape Astra): land from the fleet's sandbar (south), cross the beaches, take the fort's HQ 2 (15,4) on the ridge (north). "
        "Two coves (x5..8 and x20..23) and a shoal strip along the whole coast; the Astra river (spring in the NE hills) runs to the sea at x25; coast road y13 with a bridge. "
        "Player: Klaus, LAN4 INF4 MECH2 APC2 RECON1 ART1 CR1, day-3 AA+TANK2. Enemy (Jess): INF4 MECH2 TANK3 ART2 RECON1 CR2 + TANK reserve. "
        "Threat->answer: Jess's cruisers (sea) -> own CR and the Landers hug the sandbar until it is dealt with; tanks on the beach -> Klaus's tanks day 3, ART, MECH; "
        "enemy ART in the fort -> RECON + push over the road."))
    # --- land and sea
    m.rect("~", 0, 0, W - 1, H - 1)
    for x in range(W):
        m.rect(".", x, 0, x, COAST[x] - 1)
    # the fleet's sandbar (south), ragged
    for y, (x0, x1) in {23: (9, 20), 24: (7, 22), 25: (6, 23), 26: (6, 24)}.items():
        m.rect(".", x0, y, x1, y)
    m.put("~", 8, 26).put("~", 9, 25).put("~", 20, 24).put("~", 21, 26).put("~", 13, 23).put("~", 16, 23)
    # --- ridge and hills
    for cx, cy, n, sd in ((6, 2, 16, 1), (11, 1, 10, 2), (19, 1, 14, 3), (27, 3, 12, 4), (2, 8, 9, 5), (21, 7, 9, 6), (9, 7, 8, 7), (13, 8, 4, 8)):
        m.cluster("^", cx, cy, n, seed=sd)
    # woods: hedgerows and copses
    for cx, cy, n, sd in ((4, 11, 11, 10), (12, 10, 9, 11), (18, 11, 11, 12), (28, 9, 9, 13), (8, 4, 8, 14), (23, 4, 7, 15), (14, 13, 6, 16),
                          (3, 5, 8, 17), (16, 10, 6, 18), (26, 14, 5, 19), (10, 14, 6, 20), (20, 3, 5, 21), (7, 9, 5, 22), (1, 12, 5, 23)):
        m.cluster("f", cx, cy, n, seed=sd)
    # --- the Astra river: spring in the hills, to the sea
    rv = m.path([(24, 5), (24, 7), (26, 7), (26, 10), (25, 10), (25, 12), (24, 12), (24, 15)])
    m.put("^", 24, 4).put("^", 23, 5)
    for x, y in rv:
        m.put("-", x, y)
    # --- coast road with junctions to the fort
    m.road([(1, 13), (6, 13), (6, 12), (11, 12), (11, 13), (17, 13), (17, 12), (22, 12), (22, 13), (28, 13)])
    m.road([(15, 5), (15, 8), (14, 8), (14, 11), (14, 12)])
    m.road([(14, 8), (9, 8), (9, 6)])
    m.road([(15, 8), (20, 8), (20, 10), (22, 10), (22, 12)])
    m.road([(3, 13), (3, 12)])
    m.road([(28, 13), (28, 15)])
    m.bridge(24, 13)
    # --- the fort and the villages
    m.put("2", 15, 4)
    m.put("C", 12, 5).put("C", 18, 5).put("C", 15, 7).put("C", 9, 6)
    m.put("c", 3, 11).put("c", 28, 12).put("b", 11, 11).put("c", 20, 10).put("a", 18, 9)
    m.put("p", 27, 15)
    # --- the fleet's ports and HQ
    m.put("P", 10, 23).put("P", 19, 23).put("1", 14, 25)
    m.beach(0, 0, W - 1, H - 1)
    ex, ey = rv[-1]   # the river's mouth: land either side of its last cell
    m.put(".", ex - 1, ey).put(".", ex + 1, ey)
    tidy(m)
    # --- Klaus's legion on the sandbar: Landers at its north shore, the rest ashore in a loose order
    m.units(1, LAN, [(11, 22), (14, 22), (18, 22), (21, 22)])
    m.unit(1, CR, 15, 20)
    m.units(1, INF, [(9, 24), (12, 24), (17, 25), (20, 25)])
    m.units(1, MECH, [(11, 25), (19, 24)])
    m.units(1, APC, [(13, 24), (16, 24)])
    m.unit(1, RECON, 8, 25)
    m.unit(1, ART, 15, 24)
    # --- Jess's wardens: the fort's garrison, the beach picket, the two villages, cruisers offshore
    m.units(2, INF, [(13, 4), (17, 4), (11, 11), (20, 10)], hold=True)
    m.units(2, MECH, [(12, 6), (18, 7)], hold=True)
    m.units(2, ART, [(14, 6), (16, 6)], hold=True)
    m.units(2, TANK, [(8, 12), (15, 14), (22, 11)])
    m.unit(2, RECON, 26, 12)
    m.unit(2, CR, 5, 20).unit(2, CR, 24, 20)
    m.note("hq", 14, 25, "the legion's HQ on the fleet's sandbar")
    m.note("enemy_hq", 15, 4, "Fort Astra's HQ on the ridge (objective)")
    m.note("cove_w", 6, 16, "west cove"); m.note("cove_e", 21, 16, "east cove")
    m.note("river", 25, 10, "the Astra river, to the sea at the east cove")
    m.lake(24, 4, 9, seed=0, river_end=(24, 5))          # (a river starts in water or at the map edge: AW2 has no source tile)
    return m
