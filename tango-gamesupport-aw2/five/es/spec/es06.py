"""M6 Tribute: a market town. The player holds the central square; Colin's guild holds the north-west corner, Sasha's the south-east; the harbour is on the west edge."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es06", 18, 18)
    m.header(armies=3, colours=(BH, BM, BM), team=[1, 2, 2], objective=[1], comment=(
        "M6 Tribute: own 14 properties at the end of a day, or hold the square HQ '1' (9, 9) through the 16-day audit (HQ falls = defeat). "
        "Properties by owner (cells): player HQ(9,9) B(7,11) B(11,7) A(9,12) P(2,8) P(2,11) C(9,6) C(6,9) = 8 with the HQ; "
        "Colin (army 2) HQ(1,1) B(3,3) B(5,3) B(2,5) A(4,5) = 5; Sasha (army 3) HQ(16,16) B(14,14) B(12,14) B(15,12) A(14,12) = 5; "
        "neutral c(14,3) c(15,5) NE and c(3,14) c(2,12) SW = 4 (22 in all; 14 wins). "
        "Start forces: player INF4 MECH2 TANK2 RECON1 ART1 (10 units), 2 bases + 1 airport + 2 ports; "
        "Colin INF3 TANK2 RECON1 ART1 (7), Sasha the same (7), advancing, 3 bases + 1 airport each (the mission gives them the production). "
        "Threat -> answer: two allied armies out-producing the player -> the cross roads x=9 / y=9 are choke points (ART on the square, Tanks in the woods at (5..6,6..7) and (11..12,10..11)); "
        "enemy air from the two airports -> the player's own airport (Fighters) and AA from the bases; ART duels -> Recon to find them, Tanks to close; "
        "the race is won by taking the four neutral corner cities first."))
    # the harbour on the west edge
    m.rect("~", 0, 7, 1, 12)
    # roads: the market square's cross, the two guild lanes (y=4 north, y=13 south) with their HQ stubs, the harbour road
    m.road([(9, 2), (9, 16)])
    m.road([(2, 9), (16, 9)])
    m.road([(1, 2), (1, 4), (15, 4)])
    m.road([(16, 15), (16, 13), (2, 13)])
    m.road([(2, 9), (2, 13)])
    # parks (cover) either side of the square along the diagonals
    m.rect("f", 5, 6, 6, 7).rect("f", 11, 10, 12, 11)
    # properties
    m.put("1", 9, 9)
    m.puts("B", [(7, 11), (11, 7)]).put("A", 9, 12).puts("P", [(2, 8), (2, 11)]).puts("C", [(9, 6), (6, 9)])
    m.put("2", 1, 1).puts("B", [(3, 3), (5, 3), (2, 5)]).put("A", 4, 5)
    m.put("3", 16, 16).puts("B", [(14, 14), (12, 14), (15, 12)]).put("A", 14, 12)
    m.puts("c", [(14, 3), (15, 5), (3, 14), (2, 12)])
    # the player's garrison
    m.units(1, INF, [(8, 8), (10, 8), (8, 10), (10, 10)])
    m.units(1, MECH, [(9, 8), (9, 10)])
    m.units(1, TANK, [(8, 9), (10, 9)])
    m.unit(1, RECON, 7, 9)
    m.unit(1, ART, 9, 7)
    # Colin (north-west) and Sasha (south-east)
    m.units(2, INF, [(2, 2), (2, 3), (3, 2)]).units(2, TANK, [(4, 3), (3, 4)]).unit(2, RECON, 5, 4).unit(2, ART, 2, 4)
    m.units(3, INF, [(15, 15), (15, 14), (14, 15)]).units(3, TANK, [(13, 14), (14, 13)]).unit(3, RECON, 12, 13).unit(3, ART, 15, 13)
    m.note("square", 9, 9, "the market square: the player's HQ, must not fall")
    m.note("hq2", 1, 1, "Colin's HQ").note("hq3", 16, 16, "Sasha's HQ")
    m.note("harbour", 1, 9, "sea of the harbour (west edge, y 7..12); ports (2,8) and (2,11)")
    m.note("port1", 2, 8).note("port2", 2, 11)
    m.note("neutral_ne", 14, 3, "neutral cities (14,3) and (15,5)").note("neutral_sw", 3, 14, "neutral cities (3,14) and (2,12)")
    return m
