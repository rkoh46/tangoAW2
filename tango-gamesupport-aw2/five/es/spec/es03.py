"""M3 The Wall (Act I): Aurelia's siege of Javier's walled town of Muro Alto. A ragged outer wall of rock with three gates, an inner keep with one gate, Com Towers inside, a coast road under Drake's battleship."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *
import random

W, H = 32, 24
CX, CY = 16, 12


def ring(m, cx, cy, rx, ry, seed, lo=0.80, jit=0.10, ch="^"):
    """A ragged ring of rock around (cx, cy): the cells of an ellipse's edge band, jittered so it has no straight run."""
    rnd = random.Random(f"{m.name}/ring{seed}")
    cells = []
    for y in range(cy - ry - 2, cy + ry + 3):
        for x in range(cx - rx - 2, cx + rx + 3):
            d = (((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) ** 0.5 + rnd.uniform(-jit, jit)
            if lo <= d <= 1.0 + 0.0 and m.inside(x, y):
                cells.append((x, y))
    for x, y in cells:
        m.put(ch, x, y)
    return cells


def tidy(m):
    """Shoal cells the game has no tile for become plain."""
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
    m = Canvas("es03", W, H)
    m.header(armies=2, colours=(OS, GE), objective=[1], comment=(
        "M3 The Wall (Muro Alto, in the Aurelian march): take HQ 2 (16,12) inside the keep. A ragged outer wall of rock around the town with gates gate1 (16,6) N, gate2 (8,12) W, gate3 (24,12) E; "
        "the keep ring around the HQ, one gate (16,15) S. Vehicles must use the gates, foot soldiers climb the rock. Sea y0..1 north with a shoal y2: Drake's BS (hold) shells the coast road y3 "
        "and the north gate approach. The Muro river rises in the SW hills and runs north to the sea at x5, bridged on the coast road and the west road. "
        "Player funds 2000, start: ART3 ROCK2 RECON2 INF4 MECH2 TANK2 AA1; enemy: INF4 MECH2 TANK3 AA1 ART2 ROCK1 (hold) + BS1. "
        "Threat->answer: BS -> day-2 Bomber from the airport + ART/ROCK on the coast (indirect fire hits ships); Com Towers (+defence for Javier) -> ART/ROCK take the towers, "
        "which stand just inside the wall; enemy ART/ROCK behind the wall -> RECON spotting, fast capture of gates, MECH over the rock; enemy TANK -> player TANK/ART at the gates; enemy AA -> keep the Bomber away from it (it sits at (18,7)); "
        "ground attackers over the wall are INF/MECH only."))
    # sea and beach
    m.rect("~", 0, 0, W - 1, 1)
    m.rect(",", 0, 2, W - 1, 2)
    m.put("~", 9, 2).put("~", 10, 2).put("~", 23, 2).put("~", 24, 2).put("~", 25, 2)   # inlets
    # hills outside the wall
    for cx, cy, n, sd in ((2, 9, 10, 1), (29, 8, 10, 2), (1, 20, 8, 3), (30, 19, 9, 4), (12, 20, 4, 5), (22, 21, 5, 6), (28, 4, 5, 7)):
        m.cluster("^", cx, cy, n, seed=sd)
    # woods and hedgerows
    for cx, cy, n, sd in ((6, 14, 8, 1), (26, 15, 9, 2), (10, 4, 6, 3), (22, 4, 6, 4), (3, 4, 6, 5), (28, 11, 6, 6), (4, 12, 4, 7), (13, 19, 7, 8), (20, 19, 7, 9),
                          (8, 21, 5, 10), (27, 21, 4, 11), (9, 17, 4, 12)):
        m.cluster("f", cx, cy, n, seed=sd)
    # the outer wall: a ragged polygon of rock with a gate on each of three sides
    m.line("^", [(8, 7), (12, 7), (12, 6), (21, 6), (21, 7), (25, 8), (25, 16), (23, 16), (23, 17), (11, 17), (9, 15), (7, 15), (7, 9), (8, 9), (8, 7)], over=".f")
    # the keep ring around the HQ
    m.line("^", [(13, 10), (15, 9), (18, 9), (20, 11), (20, 13), (18, 15), (14, 15), (12, 13), (12, 11), (13, 10)], over=".f")
    for x, y in ((16, 6), (7, 12), (25, 12), (16, 15)):
        m.put(".", x, y)
    # a river from the SW hills north to the sea
    rv = m.path([(3, 17), (3, 10), (4, 10), (4, 5), (5, 5), (5, 2)])
    for x, y in rv:
        m.put("-", x, y)
    m.put("^", 3, 18).put("^", 2, 17).put(".", 4, 2).put(".", 6, 2)
    # roads
    m.road([(0, 3), (10, 3), (10, 4), (22, 4), (22, 3), (31, 3)])
    m.road([(16, 4), (16, 8), (22, 8), (22, 16), (16, 16), (16, 15)])           # the north gate street down to the keep gate
    m.road([(9, 21), (9, 18), (6, 18), (6, 12), (10, 12), (10, 16), (16, 16)])                     # west approach, gate and street
    m.road([(28, 3), (28, 12), (22, 12)])                                         # east approach and gate street
    m.road([(28, 12), (28, 20), (16, 20), (16, 21), (0, 21)])                                         # south road behind the lines
    m.bridge(5, 3)
    # enemy: HQ in the keep, towers, base, a village in the town
    m.put("2", 16, 12).put("T", 10, 9).put("T", 22, 14).put("T", 16, 10).put("B", 20, 7).put("c", 9, 14).put("c", 23, 10)
    # player: HQ, airport, base, cities on the south shore
    m.put("1", 4, 22).put("A", 10, 22).put("B", 15, 22).put("C", 20, 22).put("C", 8, 19).put("C", 27, 21).put("c", 24, 18)
    tidy(m)
    # Aurelia's siege army: guns and rockets behind, recon on the roads, the line in front
    m.spread(1, {ART: 3, ROCK: 2}, (2, 21, 27, 23), seed=1, gap=2)
    m.spread(1, {RECON: 2, TANK: 2}, (3, 18, 28, 21), seed=2, gap=2)
    m.spread(1, {INF: 4, MECH: 2, AA: 1}, (2, 18, 29, 22), seed=3, gap=1)
    # Javier's garrison
    m.units(2, INF, [(16, 7), (8, 12), (24, 12), (16, 14)], hold=True)
    m.units(2, MECH, [(9, 8), (23, 15)], hold=True)
    m.units(2, TANK, [(10, 14), (22, 10), (13, 16)])
    m.unit(2, AA, 18, 7)
    m.units(2, ART, [(14, 11), (17, 13)], hold=True)
    m.unit(2, ROCK, 12, 8, hold=True)
    m.unit(2, BS, 16, 0, hold=True)
    # named places
    m.note("hq", 4, 22, "player HQ"); m.note("enemy_hq", 16, 12, "objective: Javier's HQ in the keep")
    m.note("gate1", 16, 6, "north gate (road from the coast road, in the Battleship's range)")
    m.note("gate2", 7, 12, "west gate (road from the south-west)")
    m.note("gate3", 25, 12, "east gate (road from the east)")
    m.note("keep_gate", 16, 15, "gate of the inner keep ring, from the street y16")
    m.note("tower1", 10, 9, "Com Tower, west quarter"); m.note("tower2", 22, 14, "Com Tower, east quarter"); m.note("tower3", 16, 10, "Com Tower inside the keep")
    m.note("coast_road", 10, 3, "the coast road y3..4 under the Battleship")
    m.note("battleship", 16, 0, "Drake's Battleship (hold)")
    m.note("airport", 10, 22, "player airport"); m.note("bomber_cell", 11, 22, "day-2 Bomber reinforcement cell (free ground beside the airport)")
    m.note("muro_river", 4, 8, "the Muro river, SW hills to the sea at x5, bridge (5,3)")
    return m
