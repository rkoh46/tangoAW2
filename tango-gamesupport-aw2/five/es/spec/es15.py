"""M15 Pax Romana (Act III, tag mission): a strait with a stepping-stone island between the player's west shore and Varro's flagship island."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 32, 20


def build():
    m = Canvas("es15", W, H, fill="~")
    m.header(armies=3, colours=(GE, OS, BM), team=[1, 2, 1], objective=[1],
             comment="M15 Pax Romana (tag): rout Varro's fleet and take flagship_port (23,10) on the east island. Army 3 (the Accord) has NO units at the start and joins on day 6. "
                     "Start forces: player CR3 BS1 SUB1 LAN2 TCO1 BCO2 FTR2 BMB1 INF3 MECH2 AA1 (18), funds 8000; Varro BS2 CR3 SUB2 LAN2 FTR3 BMB2 BCO2 INF3 MECH2 TANK2 (21), builds at 3 ports and the airport. "
                     "Threat/answer: Fighters and Bombers -> the three Cruisers (AA screen at x 8), the AA on the beach, own Fighters; Battleships -> Bombers and Submarines (the strait is open sea: "
                     "a Sub can dive and hunt them); Submarines -> Cruisers; Landers/ground -> beaches: shoal x=22 rows 3..8 and 12..16 on the east island, x=7 rows 3..10 on the west shore, "
                     "x=11 / x=19 rows 8..12 on the middle island.")
    # --- the player's west shore (x 0..6, rows 0..12) ---
    m.rect(".", 0, 0, 6, 12)
    m.rect(",", 7, 3, 7, 10)                       # the beach strip, sand behind it x 3..6
    m.put("1", 2, 6).put("A", 3, 2).put("B", 3, 9).put("P", 6, 2).put("P", 6, 11)
    m.puts("c", [(1, 4), (1, 8), (2, 11)])
    m.line("R", [(2, 6), (2, 2)], over=".").line("R", [(2, 6), (2, 9), (3, 9)], over=".")
    m.line("R", [(3, 2), (6, 2)], over=".").line("R", [(2, 11), (6, 11)], over=".")
    m.line("R", [(2, 6), (6, 6)], over=".")
    m.puts("f", [(0, 0), (1, 0), (0, 1), (0, 12), (1, 12), (5, 0), (5, 12)])
    # --- the Accord's islet (south-west) ---
    m.rect(".", 1, 16, 6, 19)
    m.rect(",", 1, 15, 6, 15).rect(",", 7, 18, 7, 19)
    m.put("3", 3, 18).put("P", 6, 17)
    m.puts("f", [(1, 16), (1, 19), (5, 19)])
    # --- the stepping-stone island (middle) ---
    m.rect(".", 12, 7, 18, 13)
    m.rect("~", 12, 7, 12, 7).rect("~", 18, 7, 18, 7).rect("~", 12, 13, 12, 13).rect("~", 18, 13, 18, 13)
    m.rect(",", 11, 8, 11, 12).rect(",", 19, 8, 19, 12)
    m.put("p", 15, 7).put("p", 15, 13)
    m.puts("c", [(13, 10), (17, 10), (14, 8), (16, 12)])
    m.put("^", 15, 10)
    m.puts("f", [(14, 12), (16, 8), (14, 11), (16, 9)])
    m.line("R", [(15, 7), (15, 9)]).line("R", [(15, 11), (15, 13)])
    m.line("R", [(13, 10), (14, 10)]).line("R", [(16, 10), (17, 10)])
    # --- Varro's flagship island (east, x 23..31, rows 2..17) ---
    m.rect(".", 23, 2, 31, 17)
    m.rect(",", 22, 3, 22, 8).rect(",", 22, 12, 22, 16)
    m.put("2", 28, 10).put("A", 28, 4).put("B", 26, 6).put("B", 26, 14)
    m.put("P", 23, 2).put("P", 23, 10).put("P", 23, 17)
    m.puts("c", [(30, 7), (30, 13), (26, 10)])
    m.line("R", [(23, 10), (28, 10)]).line("R", [(26, 6), (26, 14)]).line("R", [(28, 4), (28, 10)])
    m.line("R", [(23, 2), (26, 2), (26, 6)]).line("R", [(23, 17), (26, 17), (26, 14)])
    m.puts("f", [(30, 3), (30, 16), (31, 10), (29, 15), (29, 2)])
    m.rect("^", 30, 9, 31, 9).rect("^", 30, 11, 31, 11)
    # --- player's units ---
    m.units(1, CR, [(8, 4), (8, 6), (8, 8)])
    m.unit(1, BS, 9, 6).unit(1, SUB, 8, 10)
    m.units(1, LAN, [(7, 5), (7, 8)])
    m.unit(1, TCO, 4, 4).units(1, BCO, [(4, 3), (5, 3)]).units(1, FTR, [(4, 2), (5, 2)]).unit(1, BMB, 3, 3)
    m.units(1, INF, [(4, 5), (4, 7), (5, 8)])
    m.units(1, MECH, [(5, 5), (5, 7)])
    m.unit(1, AA, 4, 6)
    # --- Varro's units ---
    m.units(2, BS, [(21, 6), (21, 13)])
    m.units(2, CR, [(20, 4), (20, 10), (20, 15)])
    m.units(2, SUB, [(19, 6), (19, 14)])
    m.units(2, LAN, [(22, 10), (22, 2)])
    m.units(2, FTR, [(27, 3), (29, 3), (27, 5)])
    m.units(2, BMB, [(29, 5), (28, 6)])
    m.units(2, BCO, [(26, 4), (30, 4)])
    m.units(2, INF, [(24, 6), (24, 14), (25, 10)])
    m.units(2, MECH, [(24, 8), (24, 12)])
    m.units(2, TANK, [(25, 8), (25, 12)])
    # --- places ---
    m.note("hq1", 2, 6, "the player's HQ"); m.note("hq2", 28, 10, "Varro's HQ"); m.note("hq3", 3, 18, "the Accord's HQ (islet, no units until day 6)")
    m.note("flagship_port", 23, 10, "Varro's flagship harbour: the objective (capture)")
    m.note("airport2", 28, 4, "Varro's airport")
    for i, (x, y) in enumerate([(2, 17), (4, 17), (1, 18), (5, 18), (2, 19), (4, 19)], 1):
        m.note(f"accord{i}", x, y, "ground cell for an Accord aircraft")
    for i, (x, y) in enumerate([(8, 17), (8, 18), (8, 19), (9, 18)], 7):
        m.note(f"accord{i}", x, y, "sea cell for an Accord ship")
    m.note("accord_port", 6, 17, "the Accord's port")
    m.note("beach_w", 7, 3, "player's beach: shoal x=7 rows 3..10, sand x 3..6")
    m.note("beach_mid_w", 11, 8, "middle island beach west (x=11 rows 8..12), east beach x=19")
    m.note("beach_e", 22, 3, "east island beach: shoal x=22 rows 3..8 and 12..16, sand x 23..26")
    m.note("mid_ports", 15, 7, "neutral ports (15,7) and (15,13) on the middle island")
    return m
