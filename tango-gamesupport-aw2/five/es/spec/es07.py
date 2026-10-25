"""M7 Mare Nostrum: the Emerald Sun's fleet crosses open sea from the home island (Cape Fidelis), past two atolls (the Twin Sisters), to Isle Verdant, the fortress island of Green Earth,
and storms its harbour (Verdant Roads)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

HARBOUR = (34, 12)

HOME = ["~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~.....~~~~~~", "~~.........~~~", "~...........,~", "............,~", "..........f,,~", "...........,~~", "..........,,,~", "...........,~~",
        "..........f,,~", "............,~", "...........,,~", "............,~", "..........f,,~", "...........,~~", "............,~", "..........,,~~", "~.........,~~~", "~~........~~~~",
        "~~~......~~~~~", "~~~~..~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~"]
MID = ["~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~,,~~~~~~", "~,.f.,~~~~~", "~,..^.,~~~~", "~~,...,~~~~", "~~~,,,~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~",
       "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~,,~~~~~", "~~~,..f,~~~", "~~,..^..,~~", "~~~,...,~~~",
       "~~~~,,,~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~", "~~~~~~~~~~~"]
EAST = ["~~~~~~~~~~~~~", "~~~~~~~~~~~~~", "~~~~~~~~~~~~~", "~~~~~~~~..~~~", "~~~~~~~,....~", "~~~~~~,......", "~~~~~,,......", "~~~~~,.......", "~~~~,,.......", "~~~~,........",
        "~~~,,,,,,,...", "~~~,~~~~~,...", "~~~~~~~~~....", "~~~,~~~~~,...", "~~~,,,,,,,...", "~~~~,,,......", "~~~~~,,......", "~~~~~,.......", "~~~~~~,,.....", "~~~~~~~,,....",
        "~~~~~~~~,,...", "~~~~~~~~~..~~", "~~~~~~~~~~~~~", "~~~~~~~~~~~~~"]


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
    m = Canvas("es07", 38, 24, fill="~")
    rows = [(h + a + b).replace(",", "~") for h, a, b in zip(HOME, MID, EAST)]
    m.set_rows(rows)
    # the Twin Sisters: two bigger atolls in the middle of the sea, each with a neutral airport; the northern one also holds a missile silo
    m.rect("~", 14, 0, 24, 23)
    m.blob("." , 19, 5, 4, 3, seed=21, wobble=0.25).blob(".", 17, 6, 2, 2, seed=22, wobble=0.2).blob(".", 22, 4, 2, 2, seed=23, wobble=0.2)
    m.blob(".", 19, 18, 4, 3, seed=24, wobble=0.25).blob(".", 21, 17, 2, 2, seed=25, wobble=0.2).blob(".", 17, 19, 2, 2, seed=26, wobble=0.2)
    m.beach(8, 2, 14, 20).beach(14, 0, 24, 10).beach(14, 13, 24, 23).beach(26, 2, 34, 20)
    road = lambda pts: m.line("R", pts, over=".fR")
    m.header(armies=3, colours=(OS, GE, YC), team=[1, 2, 2], objective=[1], comment=(
        "M7 Mare Nostrum: sink the Warden flagship (Battleship 'flagship') and capture the harbour port (34, 12) of Isle Verdant (Verdant Roads). "
        "Start forces: player LAN2 CR2 BS1 SUB1 TCO2 BCO2 INF3 MECH2 (15 units), 2 ports + 1 airport + 1 base, funds 8000; "
        "Green Earth Drake (army 2) BS1 (flagship) CR2 SUB2 LAN1 INF2 (hold) (8) + Sensei (army 3, Yellow Comet) FTR3 BCO2 (5), ports + airport to build. "
        "The Twin Sisters (the two middle atolls, each ~9x7 cells with woods and a hill) each hold a NEUTRAL airport: north atoll airport (19,5) and the missile silo M (21,4); south atoll airport (19,18). "
        "A one-cell spit of sand joins the north atoll to the home island (row 6, x 12..15: the player's infantry walk to it) and the south atoll to Isle Verdant (row 17, x 23..31: the enemy's walk to it); "
        "each side must reach the other's atoll by Lander, Copter or Transport (lint AR03 wants a foot route from some HQ; RC04 wants Landers to have land their army cannot walk to). "
        "Reefs (r) in clusters of 3 in the channels: (16,10) (17,10) (17,11); (21,13) (22,12) (22,13); (26,2) (27,2) (26,3); (25,19) (26,19) (26,20); (12,21) (13,21) (13,22); the open channel y 10..13 stays clear. "
        "Threat -> answer: Sensei's Fighters and Copters -> the two Cruisers (AA) and Fighters built at the player's airport (6, 12); "
        "Drake's Battleship -> the player's Battleship and Sub, Bombers from the airport; Subs -> Cruisers (the only ships that see and hit them); "
        "landing: shoal beaches on the home island's east coast (x 11..13), the Twin Sisters atolls (shoal ring, 6+ cells) and the whole west coast of Isle Verdant (x 28..34) with sand behind."))
    # sandbars: the Twin Sisters join both coasts at low tide by a one-cell spit of sand (row 6 from the home island to the north atoll, row 17 from Isle Verdant to the south atoll), so foot soldiers can walk to
    # the airports and the silo (lint AR03): the player's on foot to the north atoll, the enemy's to the south one; each side must LAND on the other's atoll (Landers, Copters); the open sea between the atolls (y 10..13) stays clear for ships
    for y, xa, xb in [(6, 12, 15), (17, 23, 31)]:
        for x in range(xa, xb + 1):
            if m.get(x, y) in "~,":
                m.put(".", x, y)
    tidy(m)
    # terrain
    for cx, cy, n, sd, ch in [(18, 3, 5, 31, "f"), (21, 7, 4, 32, "^"), (20, 20, 5, 33, "f"), (17, 17, 4, 34, "^"), (16, 3, 3, 35, "f"), (22, 17, 3, 36, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    m.put("a", 19, 5).put("a", 19, 18).put("M", 21, 4)
    m.line("R", [(17, 7), (17, 5), (19, 5)], over=".f").line("R", [(19, 5), (21, 5), (21, 4)], over=".f").line("R", [(21, 17), (21, 18), (19, 18)], over=".f").line("R", [(19, 18), (19, 16)], over=".f")
    m.puts("r", [(16, 10), (17, 10), (17, 11), (21, 13), (22, 12), (22, 13), (26, 2), (27, 2), (26, 3), (25, 19), (26, 19), (26, 20), (12, 21), (13, 21), (13, 22)])
    for cx, cy, n, sd, ch in [(5, 6, 9, 1, "f"), (7, 16, 8, 2, "f"), (3, 15, 6, 3, "f"), (8, 3, 5, 4, "^"), (2, 9, 5, 5, "^"), (9, 12, 4, 6, "f"),
                              (36, 8, 10, 7, "^"), (35, 17, 9, 8, "^"), (33, 6, 6, 9, "f"), (31, 18, 6, 10, "f"), (36, 13, 5, 11, "f"), (32, 9, 4, 12, "f"),
                              (6, 9, 7, 13, "f"), (7, 14, 6, 14, "f"), (3, 17, 5, 15, "f"), (9, 4, 5, 16, "f"), (5, 4, 4, 17, "^"), (6, 19, 4, 18, "f"), (3, 12, 4, 19, "^"),
                              (34, 14, 5, 20, "f"), (31, 12, 4, 21, "^"), (35, 2, 4, 22, "^"), (36, 20, 4, 23, "f"), (33, 19, 5, 24, "f"), (31, 6, 5, 25, "^"), (32, 3, 4, 26, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # properties
    m.put("1", 4, 11).put("B", 4, 8).put("A", 6, 12).put("P", 2, 3).put("P", 3, 20).puts("C", [(3, 6), (7, 17), (8, 7)])
    # villages on every island, about three cells apart (MD01, MD02)
    m.puts("c", [(6, 2), (11, 4), (1, 7), (7, 8), (2, 13), (9, 10), (6, 15), (9, 16), (2, 17), (6, 20), (8, 19),
                 (20, 3), (16, 7), (22, 7), (23, 3), (22, 16), (16, 18), (17, 20), (22, 19),
                 (34, 3), (37, 6), (31, 9), (37, 11), (33, 15), (28, 17), (37, 19), (35, 21)])
    m.put("b", 8, 5)
    m.put("2", 36, 16).put("3", 35, 5).put("P", *HARBOUR).put("P", 34, 21).put("A", 33, 7).puts("C", [(35, 10), (33, 17), (36, 12), (32, 4)])
    m.put("~", 1, 3).put("~", 2, 20).put("~", 33, 12).put("~", 33, 21).put("~", 34, 11).put("~", 34, 13)
    # roads: the home island's spine, the fortress's lanes
    road([(3, 3), (3, 6), (4, 6), (4, 11), (5, 11), (6, 11), (6, 12)])
    road([(4, 11), (4, 14), (5, 14), (5, 17), (7, 17)])
    road([(5, 17), (5, 19), (3, 19), (3, 20)])
    road([(4, 6), (8, 6), (8, 7)])
    road([(2, 3), (3, 3)])
    road([(34, 12), (35, 12), (36, 12), (36, 16)])
    road([(35, 12), (35, 10)])
    road([(36, 12), (36, 10), (34, 10), (34, 8), (33, 7), (33, 5), (35, 5)])
    road([(33, 5), (32, 5), (32, 4)])
    road([(36, 16), (35, 16), (35, 17), (33, 17)])
    road([(35, 17), (35, 19), (34, 19), (34, 21)])
    # player
    m.units(1, LAN, [(12, 4), (11, 15)]).units(1, CR, [(13, 9), (13, 13)]).unit(1, BS, 14, 11).unit(1, SUB, 12, 18)
    m.units(1, TCO, [(5, 9), (5, 13)]).units(1, BCO, [(2, 10), (3, 13)])
    m.units(1, INF, [(9, 8), (9, 14), (8, 11)]).units(1, MECH, [(8, 9), (8, 14)])
    # Green Earth: Drake's ships off the west coast of Verdant, Sensei's wing around the airport
    m.unit(2, BS, 26, 10, name="flagship").units(2, CR, [(26, 7), (27, 14)]).units(2, SUB, [(24, 12), (23, 8)])
    m.unit(2, LAN, 29, 12).units(2, INF, [(35, 14), (35, 13)], hold=True)
    m.units(3, FTR, [(34, 6), (32, 8), (35, 8)]).units(3, BCO, [(33, 15), (35, 18)])
    m.note("flagship", 26, 10, "the Warden flagship (Battleship, named flagship)").note("harbour", 34, 12, "the port to capture (west coast bay of Isle Verdant, sea channel at y=12)")
    m.note("hq1", 4, 11).note("hq2", 36, 16, "Drake's HQ").note("hq3", 35, 5, "Sensei's HQ")
    m.note("port_n", 2, 3, "player port, sea at (1, 3)").note("port_s", 3, 20, "player port, sea at (2, 20)").note("airport", 6, 12, "player airport")
    m.note("beach_home", 11, 5, "home shoal strip x 11..13, y 4..17 (Lander load / unload)")
    m.note("atoll_n", 16, 4, "Twin Sisters, north atoll x 15..23, y 2..8: neutral airport (19, 5), missile silo (21, 4)").note("atoll_s", 17, 17, "Twin Sisters, south atoll x 15..23, y 15..21: neutral airport (19, 18)")
    m.note("beach_verdant", 30, 5, "Isle Verdant shoal strip along the west coast x 28..32, y 5..9 and 15..19")
    m.note("atoll_airport_n", 19, 5, "neutral airport on the north atoll").note("atoll_airport_s", 19, 18, "neutral airport on the south atoll").note("silo", 21, 4, "neutral missile silo on the north atoll")
    m.note("eagle_airport", 33, 7, "Sensei's airport")
    return m
