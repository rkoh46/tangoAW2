"""M6 Tribute (Act II): Livia's race for the market city of Aurelhaven: own twenty-two properties at once by day 16.

Design (docs/dev/map-design.md). The situation: Livia holds the market square in the middle of the city with a little army and two factories; Colin's
guild holds the Guildhall quarter in the north-west, Hachi's the Counting House in the south-east, each with factories and an airfield; between them
is a city of neutral houses, about one every three cells. It is a capture race against two allied rivals, not a siege.
- Lanes: four avenues leave the square (north, west to the docks, east to the gardens, south over the Mill Water canal); the dock street, the mill street
  and the east streets cross the canal on their own bridges (seven in all), and the north-east road joins the Guildhall to the gardens. Every quarter has
  two ways in.
- Where the fight happens: in the quarters between the square and the two guilds (the north market, the docks, the gardens, the mill quarter and Salt
  Row across the canal), each a cluster of houses round a crossing; the neutral bases at the docks (8,20) and in the gardens (31,13) are forward
  factories for whoever takes them.
- Properties: 73 in all, 54 of them neutral (after the 12% cut of neutral cities): the race is real for both guilds too (the computer captures). Livia's two bases and airport build the
  infantry for it; the guilds' airfields send copters at her capturers.
- Threats and answers: the guilds' tanks at the capturers -> Livia's tanks and artillery on the avenues' crossings, mechs in the houses; copters -> keep
  the capturers under the tank screen; losing houses back -> hold the quarters next to the square first, then reach out.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 40, 32


def build():
    m = Canvas("es06", W, H)
    m.header(armies=3, colours=(GE, BM, OS), team=[1, 2, 2], objective=[1], comment=(
        "M6 Tribute (Aurelhaven): own 22 properties at once by the end of day 16 (capture only). Player (Livia) HQ 1 (20,16) in the square, bases (18,14) (22,18), airport (18,19); "
        "Colin HQ 2 (4,3) in the Guildhall quarter; Hachi HQ 3 (35,28) in the Counting House quarter. The harbour on the west edge (ports (3,9) Colin's, (3,19) neutral); "
        "the Mill Water canal from the harbour (3,22) to the east edge (39,24), bridged at x6, 12, 20, 24, 31, 36. Neutral forward bases (8,20) (31,13). "
        "Player INF4 MECH2 TANK2 RECON1 MDT1 ART2; Colin INF3 TANK2 RECON1 ART1; Hachi the same."))
    # --- the harbour (west) with its beach
    m.rect("~", 0, 5, 2, 31)
    m.puts("~", [(3, 26), (3, 27), (3, 28), (4, 27), (0, 4), (1, 4), (0, 3)])
    # --- parks, hills and gardens
    for cx, cy, n, sd in ((13, 8, 6, 1), (9, 12, 5, 2), (26, 5, 6, 3), (33, 4, 6, 4), (28, 11, 5, 5), (35, 12, 5, 6), (12, 18, 5, 7), (25, 20, 5, 8), (8, 26, 6, 9),
                          (16, 27, 6, 10), (29, 29, 5, 11), (37, 20, 5, 12), (14, 2, 4, 13), (2, 13, 3, 14), (22, 7, 4, 15), (17, 22, 4, 16), (33, 18, 4, 17),
                          (5, 30, 4, 18), (24, 30, 4, 19), (38, 5, 4, 20), (9, 5, 3, 21),
                          (17, 4, 7, 22), (23, 10, 6, 23), (10, 17, 6, 24), (4, 23, 5, 25), (9, 23, 6, 26), (15, 29, 6, 27), (27, 26, 6, 28), (33, 22, 6, 29),
                          (37, 25, 5, 30), (30, 18, 6, 40), (35, 7, 5, 41), (29, 3, 5, 42), (4, 7, 4, 43), (10, 27, 5, 44), (19, 25, 5, 45), (22, 30, 4, 46),
                          (13, 15, 4, 47), (26, 15, 4, 48), (38, 13, 4, 49), (33, 30, 4, 50), (1, 18, 3, 51),
                          (8, 14, 4, 52), (15, 7, 4, 53), (25, 1, 4, 54), (32, 15, 4, 55), (28, 21, 4, 56), (14, 24, 4, 57), (3, 29, 3, 58), (38, 30, 3, 59),
                          (21, 6, 4, 60), (10, 10, 3, 61), (34, 12, 3, 62), (26, 31, 3, 63), (11, 2, 3, 64), (38, 18, 3, 65)):
        m.cluster("f", cx, cy, n, seed=sd)
    for cx, cy, n, sd in ((30, 1, 6, 31), (37, 1, 5, 32), (24, 2, 4, 33), (36, 9, 4, 34), (11, 30, 4, 35), (21, 29, 3, 36), (27, 17, 3, 37), (1, 1, 3, 38), (16, 6, 3, 39), (33, 17, 4, 70), (9, 31, 3, 71), (39, 11, 3, 72)):
        m.cluster("^", cx, cy, n, seed=sd)
    # --- the Mill Water canal: harbour to the east edge, stepping south twice
    m.river([(3, 22), (14, 22), (14, 23), (27, 23), (27, 24), (39, 24)])
    # --- streets
    for pts in ([(16, 12), (24, 12), (24, 20), (16, 20), (16, 12)],                     # the square's ring
                [(20, 12), (20, 3), (5, 3)], [(16, 16), (4, 16)], [(24, 16), (39, 16)], [(20, 20), (20, 28), (34, 28)],
                [(6, 4), (6, 30)], [(12, 16), (12, 30)], [(31, 8), (31, 30)], [(36, 16), (36, 27)], [(20, 8), (31, 8)], [(31, 8), (38, 8)],
                [(6, 9), (4, 9)], [(6, 19), (4, 19)], [(12, 9), (6, 9)], [(24, 12), (28, 12), (28, 8)], [(12, 26), (6, 26)], [(31, 21), (36, 21)],
                [(12, 11), (16, 11)], [(25, 26), (31, 26)]):
        m.road(pts)
    for x in (6, 12, 20, 24, 31, 36):
        y = 22 if x < 14 else 23 if x < 27 else 24
        m.put("=", x, y)
    m.road([(24, 20), (24, 22)]).road([(24, 24), (24, 26)])
    # --- properties
    m.put("1", 20, 16).puts("B", [(18, 14), (22, 18)]).put("A", 18, 19).puts("C", [(22, 14), (18, 17)])
    m.put("2", 4, 3).puts("B", [(8, 4), (10, 2)]).put("A", 13, 4).puts("C", [(3, 6), (7, 7)]).put("P", 3, 9)
    m.put("3", 35, 28).puts("B", [(32, 26), (37, 30)]).put("A", 28, 27).puts("C", [(34, 25), (38, 27)])
    m.puts("b", [(8, 20), (31, 13)]).put("p", 3, 19).put("M", 15, 10)
    m.puts("c", [
        # the north market (between the square and the Guildhall)
        (17, 2), (22, 4), (18, 6), (21, 10), (17, 9), (13, 12), (10, 8), (14, 5), (8, 11), (4, 12), (10, 14),
        # the docks
        (5, 14), (8, 17), (4, 21), (7, 23), (10, 20),
        # Salt Row and the mill quarter (across the canal)
        (4, 25), (8, 28), (5, 31), (10, 25), (14, 25), (13, 28), (15, 31), (17, 25), (19, 30), (22, 26), (18, 22),
        # the gardens (east) and the north-east road
        (26, 14), (29, 15), (33, 14), (37, 13), (27, 10), (33, 10), (38, 10), (34, 6), (25, 7), (29, 5), (35, 2), (27, 2), (39, 2), (22, 1),
        # between the square and the Counting House
        (26, 18), (29, 20), (33, 20), (38, 18), (26, 21), (29, 21), (34, 23), (38, 22), (26, 28), (23, 30), (29, 31), (33, 31),
        # round the square
        (14, 14), (14, 19), (25, 10), (15, 21), (22, 21)])
    m.tidy()
    # --- the armies
    m.spread(1, {INF: 4, MECH: 2, TANK: 2, RECON: 1, MDT: 1, ART: 2}, (14, 11, 26, 21), seed=1, gap=1)
    m.spread(2, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (3, 1, 13, 9), seed=2, gap=1)
    m.spread(3, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (29, 24, 39, 31), seed=3, gap=1)
    m.note("square", 20, 16, "the market square: Livia's HQ")
    m.note("hq2", 4, 3, "Colin's HQ (the Guildhall)").note("hq3", 35, 28, "Hachi's HQ (the Counting House)")
    m.note("canal", 3, 22, "the Mill Water, harbour to the east edge, seven bridges")
    m.note("salt_row", 8, 28, "Salt Row across the canal").note("gardens", 31, 13, "the gardens' neutral base")
    m.note("docks", 8, 20, "the docks' neutral base").note("silo", 15, 10, "neutral silo in the north market")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
