"""M6 Tribute: the market town of Aurelhaven and its fields, in Blue Moon's border province. The player (Green Earth colour, Livia) holds the central market square; Colin's guild (Blue Moon)
holds the north-west quarter (Guildhall), Hachi's (Orange Star) the south-east (Counting House); the harbour is on the west edge and the Mill Water canal runs from the harbour to the south edge, cutting off the
south-west quarter (Salt Row). Fifteen neutral properties lie between: the race is for them."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 40, 32


def build():
    m = Canvas("es06", W, H)
    road = lambda pts: m.line("R", pts, over=".fR")
    m.header(armies=3, colours=(GE, BM, OS), team=[1, 2, 2], objective=[1], comment=(
        "M6 Tribute (Aurelhaven): own 16 properties at once by the end of day 16 (a day-17 loss when not; HQ falls = defeat). "
        "Properties (33 in all): player HQ(20,16) B(17,19) B(23,13) A(20,20) P(3,14) P(3,18) C(16,16) C(20,12) = 8; "
        "Colin (army 2, NW Guildhall) HQ(3,3) B(7,3) B(3,7) B(8,7) A(11,4) = 5; Hachi (army 3, SE Counting House) HQ(36,28) B(32,28) B(36,24) B(30,26) A(32,22) = 5; "
        "neutral c x12: (17,2) (30,3) (26,8) (36,9) (37,16) (28,19) (10,12) (13,22) (24,28) (7,21) in the open town and fields, (5,28) (8,29) in Salt Row across the Mill Water; "
        "neutral b x2: (28,12) (12,17); neutral a x1: (24,23); neutral missile silo M (15,11) on the avenue between the square and the Guildhall. "
        "16 means eight more than the start: about half of the 15 neutrals, or fewer with a guild outpost taken. "
        "Start forces: player INF4 MECH2 TANK2 RECON1 MDT1 ART2 (12 units), 2 bases + 1 airport + 2 ports; Colin INF3 TANK2 RECON1 ART1 (7), Hachi the same (7), advancing. "
        "Threat -> answer: two allied armies out-producing the player -> the avenues meet at the square (ART on the square, Tanks in the parks); "
        "enemy air from the two airports (and the neutral one) -> the player's own airport (Fighters) and AA from the bases; ART duels -> Recon to find them, Tanks to close; "
        "the missile silo (3 HP to everything within 3 cells) can be fired by anyone with a foot soldier on it; "
        "the race is won by taking the neutral towns first."))
    # the harbour on the west edge: a ragged bay with an inlet for the two ports
    m.rect("~", 0, 6, 1, 27).rect("~", 2, 9, 2, 23).rect("~", 0, 4, 0, 5).rect("~", 3, 15, 3, 17).rect("~", 0, 28, 0, 29).rect("~", 2, 7, 2, 8).rect("~", 2, 24, 2, 25)
    # the Mill Water: from the harbour east, then south to the south edge, two bridges
    m.river([(2, 24), (8, 24), (8, 26), (11, 26), (11, 31)])
    m.put("=", 4, 24).put("=", 11, 29)
    # properties
    m.put("1", 20, 16).puts("B", [(17, 19), (23, 13)]).put("A", 20, 20).puts("P", [(3, 14), (3, 18)]).puts("C", [(16, 16), (20, 12)])
    m.put("2", 3, 3).puts("B", [(7, 3), (3, 7), (8, 7)]).put("A", 11, 4)
    m.put("3", 36, 28).puts("B", [(32, 28), (36, 24), (30, 26)]).put("A", 32, 22)
    m.puts("c", [(17, 2), (30, 3), (26, 8), (36, 9), (37, 16), (28, 19), (10, 12), (13, 22), (24, 28), (7, 21), (5, 28), (8, 29)])
    m.puts("b", [(28, 12), (12, 17)]).put("a", 24, 23)
    m.put("M", 15, 11)
    # roads
    road([(3, 3), (17, 3), (17, 5), (20, 5), (20, 12)])                 # Colin's north road and the north avenue
    road([(17, 3), (17, 2)])
    road([(3, 3), (3, 7), (8, 7), (8, 12), (10, 12)])                   # the Guildhall to the western city
    road([(8, 7), (8, 3)])
    road([(11, 3), (11, 4)])
    road([(10, 12), (15, 12), (20, 12)])                                # the contested avenue past the silo
    road([(10, 12), (10, 16), (20, 16)])                                # the west avenue into the square
    road([(12, 17), (12, 16)])
    road([(20, 12), (20, 16), (20, 26), (13, 26), (13, 22)])            # north and south avenues
    road([(13, 26), (12, 26), (12, 29), (9, 29), (8, 29)])              # over the Mill Water bridge into Salt Row
    road([(17, 19), (17, 16)])
    road([(20, 26), (20, 28), (24, 28)])
    road([(3, 14), (4, 14), (4, 28), (5, 28)])                          # harbour road and Salt Row
    road([(3, 18), (4, 18)])
    road([(4, 16), (10, 16)])
    road([(4, 21), (7, 21)])
    road([(5, 28), (8, 28), (8, 29)])
    road([(20, 8), (26, 8), (26, 3), (30, 3)])                          # north-east
    road([(26, 8), (32, 8), (36, 8), (36, 9), (36, 16), (37, 16)])
    road([(20, 16), (23, 16), (23, 13)])
    road([(23, 16), (28, 16), (28, 12)])
    road([(28, 16), (28, 19), (28, 22), (32, 22), (32, 24), (36, 24), (36, 28), (30, 28), (30, 26)])   # the Counting House
    road([(32, 28), (32, 24)])
    road([(28, 22), (25, 22), (25, 26), (30, 26)])
    road([(25, 22), (25, 23)])
    # terrain on what is left: the town's parks and hedgerows, ridges, a hill in Salt Row
    for cx, cy, n, sd, ch in [(14, 8, 10, 1, "f"), (24, 20, 10, 2, "f"), (15, 21, 9, 3, "f"), (24, 5, 8, 4, "f"), (32, 15, 9, 5, "f"), (7, 14, 7, 6, "f"), (23, 2, 7, 7, "f"),
                              (17, 29, 8, 8, "f"), (33, 26, 7, 9, "f"), (38, 4, 6, 10, "f"), (6, 10, 5, 11, "f"), (13, 1, 5, 12, "f"), (22, 30, 8, 13, "f"), (2, 30, 6, 14, "f"),
                              (31, 7, 9, 15, "^"), (34, 20, 8, 16, "^"), (6, 30, 7, 17, "^"), (14, 7, 5, 18, "^"), (17, 23, 6, 19, "^"), (27, 28, 6, 20, "f"), (38, 22, 6, 21, "^"),
                              (18, 9, 6, 22, "^"), (38, 31, 5, 23, "f"), (6, 18, 4, 24, "f"), (30, 12, 6, 25, "f"), (9, 19, 5, 26, "f"), (22, 17, 5, 27, "f"), (28, 24, 5, 28, "f"),
                              (33, 11, 9, 29, "f"), (22, 24, 8, 30, "f"), (9, 24, 6, 31, "^"), (16, 12, 6, 32, "f"), (34, 3, 9, 33, "f"), (12, 14, 8, 34, "f"), (7, 5, 7, 35, "f"),
                              (26, 12, 7, 36, "f"), (30, 30, 8, 37, "^"), (19, 26, 8, 38, "f"), (35, 18, 7, 39, "f"), (21, 8, 9, 40, "f"), (5, 22, 7, 41, "^"), (11, 10, 6, 42, "f"),
                              (27, 3, 9, 43, "f"), (38, 12, 7, 44, "^"), (14, 28, 7, 45, "f"), (31, 19, 6, 46, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # the garrison of the square, a screen to the east and west, guns behind the parks
    m.spread(1, {INF: 4, MECH: 2, TANK: 2, RECON: 1, MDT: 1, ART: 2}, (14, 12, 26, 21), seed=1, gap=1)
    m.spread(2, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (1, 1, 11, 9), seed=2, gap=1)
    m.spread(3, {INF: 3, TANK: 2, RECON: 1, ART: 1}, (29, 22, 38, 30), seed=3, gap=1)
    m.note("square", 20, 16, "the market square: the player's HQ, must not fall")
    m.note("hq2", 3, 3, "Colin's HQ (Guildhall)").note("hq3", 36, 28, "Hachi's HQ (Counting House)")
    m.note("silo", 15, 11, "neutral missile silo beside the contested avenue (15,12) between the square and the Guildhall")
    m.note("harbour", 1, 16, "sea of the harbour (west edge); ports (3, 14) and (3, 18)")
    m.note("canal", 2, 24, "the Mill Water, harbour to south edge, bridges (4, 24) and (11, 29)")
    m.note("salt_row", 6, 28, "Salt Row: the south-west quarter across the Mill Water, neutral cities (5, 28) and (8, 29)")
    m.note("neutral_ne", 30, 3, "neutral cities (30, 3) and (26, 8) and (36, 9)").note("neutral_e", 37, 16, "neutral cities (37, 16), (28, 19), bases (28, 12)")
    m.note("neutral_n", 17, 2, "neutral city (17, 2)").note("neutral_w", 10, 12, "neutral cities (10, 12), (7, 21), base (12, 17)")
    m.note("neutral_s", 24, 28, "neutral cities (24, 28), (13, 22), airport (24, 23)")
    return m
