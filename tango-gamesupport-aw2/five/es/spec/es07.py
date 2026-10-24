"""M7 Mare Nostrum: the Emerald Sun's fleet crosses open sea from the home island, past two atolls, to Isle Verdant, the fortress island of Green Earth."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es07", 22, 16, fill="~")
    m.header(armies=3, colours=(BH, GE, GE), team=[1, 2, 2], objective=[1], comment=(
        "M7 Mare Nostrum: sink the Warden flagship (Battleship 'flagship') and capture the harbour port (15, 8) of Isle Verdant. "
        "Start forces: player LAN2 CR2 BS1 SUB1 TCO2 BCO2 INF3 MECH2 (15 units), 2 ports + 1 airport + 1 base, funds 6000; "
        "Green Earth Drake (army 2) BS1 (flagship) CR2 SUB2 LAN1 INF2 (hold) (8) + Eagle (army 3) FTR3 BCO2 (5), ports + airport to build. "
        "Threat -> answer: Eagle's Fighters and Copters -> the two Cruisers (AA) and Fighters built at the player's airport (5, 8); "
        "Drake's Battleship -> the player's Battleship and Sub, Bombers from the airport; Subs -> Cruisers (the only ships that see and hit them); "
        "landing: shoal beaches on the home island (x=7), the atolls and the whole west coast of Isle Verdant (x=14, y 5..11) with sand (x 15..18) behind."))
    # home island (west): cut corners, ports on the north and south coasts, a shoal beach on the east coast
    m.rect(".", 0, 4, 6, 11).rect(".", 1, 3, 6, 3).rect(".", 1, 12, 6, 12).rect(".", 2, 2, 5, 2).rect(".", 2, 13, 5, 13)
    m.rect(",", 7, 4, 7, 11)
    # two atolls with their own shoal ring
    m.rect(".", 10, 2, 12, 3).beach(9, 1, 13, 4)
    m.rect(".", 10, 12, 12, 13).beach(9, 11, 13, 14)
    # Isle Verdant (east): fortress ridge, harbour notch on the west coast
    m.rect(".", 15, 5, 21, 11).rect(".", 18, 3, 20, 3).rect(".", 17, 4, 21, 4).rect(".", 17, 12, 21, 12).rect(".", 18, 13, 20, 13)
    m.rect(",", 14, 5, 14, 7).rect(",", 14, 9, 14, 11)
    m.rect("^", 20, 6, 21, 7)
    m.rect("f", 16, 11, 17, 12)
    # properties
    m.put("1", 3, 8).put("B", 3, 6).put("A", 5, 8).put("P", 3, 2).put("P", 3, 13).put("C", 2, 10)
    m.put("2", 20, 10).put("3", 19, 4).put("P", 15, 8).put("P", 19, 13).put("A", 17, 5).puts("C", [(18, 9), (20, 8), (17, 11)])
    # roads: the home island's spine, the fortress's spine
    m.road([(3, 3), (3, 12)]).road([(3, 8), (4, 8)])
    m.road([(16, 8), (19, 8)]).road([(19, 5), (19, 10)]).road([(19, 10), (19, 12)])
    # player
    m.units(1, LAN, [(7, 6), (7, 9)]).units(1, CR, [(8, 5), (8, 11)]).unit(1, BS, 8, 8).unit(1, SUB, 3, 14)
    m.units(1, TCO, [(4, 6), (4, 10)]).units(1, BCO, [(2, 6), (2, 12)])
    m.units(1, INF, [(6, 7), (5, 6), (5, 10)]).units(1, MECH, [(6, 9), (5, 11)])
    # Green Earth: Drake's ships off the west coast, Eagle's wing around the airport
    m.unit(2, BS, 12, 8, name="flagship").units(2, CR, [(12, 6), (12, 10)]).units(2, SUB, [(13, 7), (13, 9)])
    m.unit(2, LAN, 14, 6).units(2, INF, [(16, 8), (16, 9)], hold=True)
    m.units(3, FTR, [(16, 5), (16, 6), (17, 6)]).units(3, BCO, [(18, 6), (18, 5)])
    m.note("flagship", 12, 8, "the Warden flagship (Battleship, named flagship)").note("harbour", 15, 8, "the port to capture (west coast notch of Isle Verdant)")
    m.note("hq1", 3, 8).note("hq2", 20, 10, "Drake's HQ").note("hq3", 19, 4, "Eagle's HQ")
    m.note("port_n", 3, 2, "player port, sea at (3, 1)").note("port_s", 3, 13, "player port, sea at (3, 14)").note("airport", 5, 8, "player airport")
    m.note("beach_home", 7, 4, "home shoal strip x=7, y 4..11 (Lander load / unload)")
    m.note("atoll_n", 10, 2, "north atoll land x 10..12, y 2..3").note("atoll_s", 10, 12, "south atoll land x 10..12, y 12..13")
    m.note("beach_verdant", 14, 5, "Isle Verdant shoal strip x=14, y 5..7 and 9..11; sand x 15..18 behind")
    m.note("eagle_airport", 17, 5, "Eagle's airport")
    return m
