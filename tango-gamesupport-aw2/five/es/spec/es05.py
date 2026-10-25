"""M5 Dust and Wheels (Act II, desert, sandstorm): Cassius's cavalry races for the three Comet signal posts before the bridges are blown (day 10).

Design (docs/dev/map-design.md). The situation: Cassius rides east out of Dunmere (west) with an all-vehicle column; the Sable river (four bridges) and
the Comet Pipe (a border fence with two road gates and a seam on the middle road) lie between him and the posts Highwatch (27,5), Crossways (27,12)
and Lowmere (27,21); Grimm and Sensei hold Fort Amberlea in the east with two factories and an airfield.
- Lanes: three canyon roads fan out from Dunmere, each to its bridge and its post, separated by mesas (rock) with passes between them; a farm track
  crosses the Sable at a fourth bridge (18,16) to the south ruins. The pipe has gates on the north and south roads; the seam (25,12) on the middle road
  is the shortcut a tank can open.
- Where the fight happens: between the bridges and the posts: the forward neutral bases (22,6) and (22,17), the ruins and the silo (22,11) in the
  middle, the posts themselves.
- Properties: oasis villages on both sides (every few cells; sand towns as cover for the mechs), the posts (neutral, picketed), two forward bases the
  player can take to build infantry for the captures, Fort Amberlea's factories and airfield.
- Threats and answers: copters -> the two AA and the tanks; the guns behind the posts (short in the sandstorm) -> speed: recons and tanks cross first and
  hit them; tanks at the posts -> Md tanks and mechs; the clock -> three roads to three posts, and the seam for the middle one.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 42, 24
POSTS = [(27, 5), (27, 12), (27, 21)]


def build():
    m = Canvas("es05", W, H)
    m.header(armies=2, colours=(OS, YC), objective=[1], comment=(
        "M5 Dust and Wheels (the Comet Marches): own the three signal posts (27,5) (27,12) (27,21) by the end of day 9. The Sable river bridged at (16,5) (17,12) (18,16) (19,21); "
        "the Comet Pipe x25 with road gates (25,4..5) and (25,20..21) and the seam (25,12) on the Crossways road. Forward neutral bases (22,6) (22,17), silo (22,11). "
        "Player: RECON3 TANK3 MDT2 APC2 MECH3 AA2, funds 3000, base (12,11); Yellow Comet: INF4 MECH2 TANK2 RECON1 ART2 ROCK1 BCO2 TCO1 AA1, bases (35,8) (35,16), airport (34,4). "
        "Sandstorm: long guns lose a cell of range; the player's answers are direct fire."))
    # --- the mesas (rock) and the scrub, placed so that each road runs in its own canyon with passes between
    for cx, cy, n, sd in ((5, 4, 9, 1), (10, 9, 8, 2), (6, 16, 8, 3), (12, 19, 7, 4), (13, 2, 6, 5), (2, 19, 6, 6), (20, 4, 7, 7), (21, 8, 5, 8), (20, 15, 6, 9),
                          (22, 20, 6, 10), (29, 2, 8, 11), (30, 8, 8, 12), (29, 17, 8, 13), (31, 22, 5, 14), (37, 4, 7, 15), (39, 9, 5, 16), (37, 18, 7, 17),
                          (33, 14, 5, 18), (40, 22, 4, 19), (9, 22, 4, 20), (1, 9, 4, 21), (14, 14, 4, 22),
                          (4, 1, 4, 23), (10, 13, 4, 24), (16, 20, 4, 25), (24, 8, 4, 26), (23, 18, 4, 27), (27, 8, 3, 28), (39, 1, 4, 29), (41, 11, 3, 30), (33, 17, 4, 60), (1, 13, 3, 61)):
        m.cluster("^", cx, cy, n, seed=sd)
    for cx, cy, n, sd in ((3, 8, 5, 31), (8, 2, 4, 32), (13, 10, 4, 33), (5, 13, 4, 34), (10, 15, 4, 35), (4, 21, 4, 36), (14, 22, 4, 37), (19, 10, 4, 38),
                          (23, 3, 3, 39), (24, 15, 3, 40), (20, 22, 3, 41), (28, 10, 4, 42), (29, 14, 3, 43), (33, 2, 4, 44), (34, 11, 3, 45), (38, 15, 4, 46),
                          (36, 22, 3, 47), (40, 5, 3, 48), (27, 18, 3, 49), (12, 6, 3, 50), (2, 1, 3, 51), (17, 1, 3, 52), (31, 19, 3, 53),
                          (7, 18, 3, 54), (15, 11, 3, 55), (18, 3, 3, 56), (26, 15, 3, 57), (36, 6, 3, 58), (40, 20, 3, 59), (3, 23, 3, 62), (26, 1, 3, 63),
                          (9, 10, 3, 64), (30, 15, 3, 65), (38, 8, 3, 66), (16, 9, 3, 67), (13, 17, 3, 68), (24, 10, 3, 69)):
        m.cluster("f", cx, cy, n, seed=sd)
    # --- the Sable: from the north edge to the south edge, stepping east; four bridges
    m.river([(15, 0), (15, 3), (16, 3), (16, 8), (17, 8), (17, 14), (18, 14), (18, 18), (19, 18), (19, 23)])
    # --- roads: Dunmere's hub, the three canyon roads to the posts, the farm track, the Comet roads behind the pipe
    for pts in ([(3, 12), (8, 12)], [(8, 12), (8, 8), (11, 8), (11, 5), (24, 5)], [(26, 5), (31, 5), (31, 4), (33, 4)], [(8, 12), (24, 12)], [(26, 12), (37, 12)],
                [(8, 12), (8, 16), (11, 16), (11, 21), (24, 21)], [(26, 21), (32, 21), (32, 19), (35, 19), (35, 16)], [(11, 16), (22, 16)],
                [(31, 5), (31, 12)], [(35, 12), (35, 8)], [(35, 12), (35, 16)], [(12, 12), (12, 11)], [(22, 5), (22, 6)], [(22, 16), (22, 17)]):
        m.road(pts)
    for bx, by in ((16, 5), (17, 12), (18, 16), (19, 21)):
        m.put("=", bx, by)
    # --- the Comet Pipe: a fence from edge to edge at x25, road gates north and south, the seam on the Crossways road
    m.pipe([(25, 0), (25, 3)]).pipe([(25, 6), (25, 11)]).pipe([(25, 13), (25, 19)]).pipe([(25, 22), (25, 23)])
    m.put("Z", 25, 12).puts(".", [(25, 4), (25, 20)]).puts("R", [(25, 5), (25, 21)])
    # --- two oases (a pond with sand round it)
    m.puts("~", [(5, 19), (6, 19), (5, 20)]).puts(",", [(4, 19), (7, 19), (4, 20), (6, 20), (5, 18), (6, 18), (5, 21)])
    m.puts("~", [(37, 20), (38, 20), (37, 21)]).puts(",", [(36, 20), (39, 20), (36, 21), (38, 21), (37, 19), (38, 19), (37, 22)])
    # --- properties
    m.put("1", 3, 12).put("B", 12, 11).puts("C", [(2, 10), (5, 14), (6, 10)])
    m.puts("c", [(3, 3), (7, 1), (11, 2), (13, 7), (2, 6), (6, 6), (1, 16), (3, 17), (8, 22), (2, 22), (10, 19), (13, 14), (14, 9), (14, 19), (12, 23), (9, 4)])
    m.puts("c", POSTS)
    m.puts("b", [(22, 6), (22, 17)]).put("M", 22, 11)
    m.puts("c", [(19, 2), (23, 1), (20, 9), (23, 9), (20, 13), (23, 14), (20, 19), (23, 22), (28, 2), (29, 7), (28, 16), (29, 23), (29, 10), (21, 23)])
    m.put("2", 38, 12).puts("B", [(35, 8), (35, 16)]).put("A", 34, 4).puts("C", [(39, 7), (33, 20), (40, 14), (37, 2), (36, 10)])
    m.puts("c", [(40, 1), (33, 10), (34, 23), (40, 18), (33, 7)])
    m.tidy()
    # --- Cassius's column on the roads out of Dunmere
    m.spread(1, {MECH: 3}, (6, 7, 12, 17), seed=1, gap=1)
    m.spread(1, {RECON: 3, TANK: 3, MDT: 2, APC: 2, AA: 2}, (4, 7, 14, 17), seed=2, gap=1)
    # --- the Comet border guard: pickets at the posts, guns behind, copters at the field
    m.units(2, INF, [(26, 5), (28, 13), (26, 21), (26, 11)], hold=True)
    m.units(2, MECH, [(28, 4), (28, 22)], hold=True)
    m.unit(2, TANK, 28, 11).unit(2, TANK, 30, 13)
    m.unit(2, RECON, 31, 9)
    m.units(2, ART, [(32, 13), (30, 20)], hold=True)
    m.unit(2, ROCK, 34, 13, hold=True)
    m.units(2, BCO, [(36, 15), (36, 9)])
    m.unit(2, TCO, 37, 11)
    m.unit(2, AA, 37, 13, hold=True)
    m.note("hq1", 3, 12, "player HQ (Dunmere)").note("hq2", 38, 12, "Yellow Comet HQ (Fort Amberlea)")
    m.note("post1", 27, 5, "Highwatch").note("post2", 27, 12, "Crossways (behind the seam)").note("post3", 27, 21, "Lowmere")
    m.note("seam", 25, 12, "the Comet Pipe's seam on the Crossways road")
    m.note("fwd_n", 22, 6, "neutral forward base by the north road").note("fwd_s", 22, 17, "neutral forward base by the farm track")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=POSTS)
    return m
