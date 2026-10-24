"""M6 Tribute: the market town of Aurelhaven in Blue Moon's border province. The player takes the central market square; Colin's guild holds the north-west quarter (Guildhall), Sasha's the south-east
(Counting House); the harbour is on the west edge and the Mill Water canal runs from the harbour to the south edge, cutting off the south-west quarter (Salt Row)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es06", 30, 26)
    road = lambda pts: m.line("R", pts, over=".fR")
    m.header(armies=3, colours=(OS, BM, BM), team=[1, 2, 2], objective=[1], comment=(
        "M6 Tribute (Aurelhaven): own 14 properties at once by the end of day 16 (a day-17 loss when not; HQ falls = defeat). "
        "Properties (26 in all): player HQ(15,13) B(13,15) B(17,11) A(15,16) P(3,11) P(3,14) C(15,10) C(12,13) = 8; "
        "Colin (army 2, NW Guildhall) HQ(2,2) B(5,2) B(2,5) B(6,5) A(8,3) = 5; Sasha (army 3, SE Counting House) HQ(27,23) B(24,23) B(27,20) B(22,21) A(24,18) = 5; "
        "neutral c x8: (14,2) (25,3) (27,8) (27,14) (21,16) (8,9) in the open town, (3,22) (7,23) in Salt Row across the Mill Water. 14 means six more than the start: the race is for the neutrals and the guild outposts. "
        "Start forces: player INF4 MECH2 TANK2 RECON1 MDT1 ART2 (12 units), 2 bases + 1 airport + 2 ports; Colin INF3 TANK2 RECON1 ART1 (7), Sasha the same (7), advancing. "
        "Threat -> answer: two allied armies out-producing the player -> the avenues meet at the square (ART on the square, Tanks in the parks); "
        "enemy air from the two airports -> the player's own airport (Fighters) and AA from the bases; ART duels -> Recon to find them, Tanks to close; "
        "the race is won by taking the neutral towns first."))
    # the harbour on the west edge: a ragged bay with an inlet for the two ports
    m.rect("~", 0, 6, 1, 19).rect("~", 2, 8, 2, 16).rect("~", 0, 4, 0, 5).rect("~", 3, 12, 3, 13).rect("~", 0, 20, 0, 21)
    # the Mill Water: from the harbour south-east to the south edge, two bridges
    m.river([(2, 18), (6, 18), (6, 20), (10, 20), (10, 25)])
    b1, b2 = (4, 18), (10, 22)
    m.put("=", *b1).put("=", *b2)
    # properties
    m.put("1", 15, 13).puts("B", [(13, 15), (17, 11)]).put("A", 15, 16).puts("P", [(3, 11), (3, 14)]).puts("C", [(15, 10), (12, 13)])
    m.put("2", 2, 2).puts("B", [(5, 2), (2, 5), (6, 5)]).put("A", 8, 3)
    m.put("3", 27, 23).puts("B", [(24, 23), (27, 20), (22, 21)]).put("A", 24, 18)
    m.puts("c", [(14, 2), (25, 3), (27, 8), (27, 14), (21, 16), (8, 9), (3, 22), (7, 23)])
    # roads
    road([(14, 2), (14, 6), (15, 6), (15, 13)])                      # north avenue
    road([(15, 13), (15, 19), (14, 19), (14, 22), (11, 22)])         # south avenue to the Mill Water bridge
    road([(9, 22), (7, 22), (7, 23)])
    road([(4, 19), (4, 22), (3, 22)])                                  # Salt Row
    road([(4, 11), (9, 11), (9, 13), (12, 13)])                       # harbour road
    road([(4, 11), (4, 14), (4, 17)])
    road([(8, 9), (9, 9), (9, 11)])
    road([(15, 13), (21, 13), (27, 13), (27, 14)])
    road([(17, 11), (21, 11), (21, 8), (27, 8)])
    road([(21, 13), (21, 16), (22, 16), (22, 21)])
    road([(14, 6), (20, 6), (20, 3), (25, 3)])
    road([(2, 2), (8, 2), (8, 5), (6, 5), (6, 7), (11, 7), (11, 6), (14, 6)])
    road([(5, 2), (5, 5), (2, 5)])
    road([(8, 5), (8, 9)])
    road([(27, 23), (22, 23), (22, 21)])
    road([(27, 23), (27, 20), (24, 20), (24, 18)])
    road([(24, 23), (24, 20)])
    road([(27, 20), (27, 14)])
    # terrain on what is left: the town's parks and hedgerows, a ridge in the north-east, a hill in Salt Row
    for cx, cy, n, sd, ch in [(11, 9, 10, 1, "f"), (19, 16, 10, 2, "f"), (11, 16, 9, 3, "f"), (19, 9, 8, 4, "f"), (24, 11, 9, 5, "f"), (6, 13, 7, 6, "f"), (18, 3, 7, 7, "f"),
                              (12, 20, 8, 8, "f"), (25, 21, 7, 9, "f"), (28, 4, 6, 10, "f"), (3, 8, 5, 11, "f"), (10, 3, 5, 12, "f"), (17, 23, 8, 13, "f"), (1, 24, 6, 14, "f"),
                              (23, 6, 9, 15, "^"), (28, 17, 8, 16, "^"), (5, 24, 7, 17, "^"), (11, 2, 5, 18, "^"), (13, 24, 6, 19, "^"), (0, 12, 4, 20, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # the garrison of the square, a screen to the east and west, guns behind the parks
    m.spread(1, {INF: 4, MECH: 2, TANK: 2, RECON: 1, MDT: 1, ART: 2}, (10, 9, 20, 17), seed=1, gap=1)
    m.spread(2, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (1, 1, 9, 8), seed=2, gap=1)
    m.spread(3, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (21, 17, 28, 24), seed=3, gap=1)
    m.note("square", 15, 13, "the market square: the player's HQ, must not fall")
    m.note("hq2", 2, 2, "Colin's HQ (Guildhall)").note("hq3", 27, 23, "Sasha's HQ (Counting House)")
    m.note("harbour", 1, 12, "sea of the harbour (west edge); ports (3, 11) and (3, 14)")
    m.note("canal", 2, 17, "the Mill Water, harbour to south edge, bridges (4, 18) and (10, 22)")
    m.note("salt_row", 5, 23, "Salt Row: the south-west quarter across the Mill Water, neutral cities (3, 22) and (7, 23)")
    m.note("neutral_ne", 25, 3, "neutral cities (25, 3) and (27, 8)").note("neutral_e", 27, 14, "neutral cities (27, 14) and (21, 16)")
    m.note("neutral_n", 14, 2, "neutral city (14, 2)").note("neutral_w", 8, 9, "neutral city (8, 9)")
    return m
