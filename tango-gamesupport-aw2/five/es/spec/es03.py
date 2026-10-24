"""M3 The Wall (Act I): Aurelia's siege of Javier's tower-fortress. Outer ring wall with three gates, an inner keep, Com Towers inside, a coast road under Drake's battleship."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es03", 22, 16)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M3 The Wall: take HQ 2 (10,9) inside the keep. Outer ring wall x3..18 y5..13 with gates gate1 (10,5) N, gate2 (3,9) W, gate3 (18,9) E; "
        "keep ring x7..14 y7..11, one gate (10,11) S. Vehicles must use the gates, foot soldiers climb mountains. Sea y0..1 north, shoal y2: Drake's BS (hold) shells the coast road y3 "
        "and the north gate approach. Player funds 2000, start: ART3 ROCK2 RECON2 INF4 MECH2 TANK2 AA1 (about 90000 value); "
        "enemy: INF4 MECH2 TANK3 AA1 ART2 ROCK1 (hold) + BS1 (about 100000 value). "
        "Threat->answer: BS -> day-2 Bomber from the airport + ART/ROCK on the coast (indirect fire hits ships); Com Towers (+defence for Javier) -> ART/ROCK take the towers, "
        "which stand just inside the wall; enemy ART/ROCK behind the wall -> RECON spotting, fast capture of gates, MECH over the mountains; enemy TANK -> player TANK/ART at the gates; enemy AA -> keep the Bomber away from it (it sits at (12,6)); "
        "ground attackers over the wall are INF/MECH only."))
    # sea and beach
    m.rect("~", 0, 0, 21, 1).rect(",", 0, 2, 21, 2)
    # outer wall and keep ring (gates are plain)
    m.frame("^", 3, 5, 18, 13)
    m.frame("^", 7, 7, 14, 11)
    for x, y in ((10, 5), (3, 9), (18, 9), (10, 11)):
        m.put(".", x, y)
    # approach lane: woods give the west gate approach cover
    m.rect("f", 0, 7, 1, 11, only=".")
    m.rect("f", 20, 14, 21, 15, only=".")
    # roads: coast road, lanes, south road, gates, inner loop
    m.road([(1, 3), (20, 3)])
    m.road([(1, 3), (1, 14)])
    m.road([(20, 3), (20, 14)])
    m.road([(1, 14), (20, 14)])
    m.road([(10, 3), (10, 5)])
    m.road([(1, 9), (5, 9)])
    m.road([(20, 9), (17, 9), (17, 12)])
    m.road([(10, 5), (10, 6), (5, 6), (5, 12)])
    m.road([(5, 12), (17, 12)])
    m.road([(10, 11), (10, 12)])
    # enemy: HQ in the keep, towers, base
    m.put("2", 10, 9).put("T", 5, 8).put("T", 16, 8).put("T", 12, 8).put("B", 16, 6)
    # player: HQ, airport, base, cities on the south shore
    m.put("1", 4, 15).put("A", 8, 15).put("B", 12, 15).put("C", 16, 15).put("C", 6, 14)
    m.road([(1, 14), (20, 14)])
    # player army
    m.units(1, ART, [(3, 14), (8, 14), (12, 14)])
    m.units(1, ROCK, [(9, 14), (13, 14)])
    m.units(1, RECON, [(2, 14), (18, 14)])
    m.units(1, INF, [(5, 14), (7, 14), (15, 14), (17, 14)])
    m.units(1, MECH, [(4, 14), (16, 14)])
    m.units(1, TANK, [(10, 14), (11, 14)])
    m.unit(1, AA, 14, 14)
    # Javier's garrison
    m.units(2, INF, [(9, 6), (11, 6), (4, 10), (17, 10)], hold=True)
    m.units(2, MECH, [(3, 7), (18, 11)], hold=True)
    m.units(2, TANK, [(6, 12), (13, 12), (10, 12)])
    m.unit(2, AA, 12, 6)
    m.units(2, ART, [(9, 8), (11, 8)], hold=True)
    m.unit(2, ROCK, 8, 6, hold=True)
    m.unit(2, BS, 11, 0, hold=True)
    # named places
    m.note("hq", 4, 15, "player HQ"); m.note("enemy_hq", 10, 9, "objective: Javier's HQ in the keep")
    m.note("gate1", 10, 5, "north gate (road from the coast road, in the Battleship's range)")
    m.note("gate2", 3, 9, "west gate (road from the west lane)")
    m.note("gate3", 18, 9, "east gate (road from the east lane)")
    m.note("keep_gate", 10, 11, "gate of the inner keep ring, from the south road y12")
    m.note("tower1", 5, 8, "Com Tower, west pocket"); m.note("tower2", 16, 8, "Com Tower, east pocket"); m.note("tower3", 12, 8, "Com Tower inside the keep")
    m.note("coast_road", 10, 3, "the coast road y3 (x1..20) under the Battleship")
    m.note("battleship", 11, 0, "Drake's Battleship (hold)")
    m.note("airport", 8, 15, "player airport"); m.note("bomber_cell", 9, 15, "day-2 Bomber reinforcement cell (free ground beside the airport)")
    return m
