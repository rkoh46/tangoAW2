"""M14 Varro's Gambit (Act III): hold the quay HQ against the Praetorians and Cassius, then break out along the causeway to the east docks."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 30, 18


def build():
    m = Canvas("es14", W, H)
    m.header(armies=3, colours=(BH, OS, YC), team=[1, 2, 3], objective=[1],
             comment="M14 Varro's Gambit: phase 1 hold the quay HQ (1), phase 2 take dock1 and dock2 (ports on the east bank) before the ships leave. "
                     "Army 3 (Cassius) is hostile to both until day 4 (mission code). Start forces: player INF4 MECH3 TANK3 MDT2 RECON1 ART2 AA1 (16), funds 4000; "
                     "Varro INF4 MECH2 TANK3 MDT3 ART2 ROCK1 AA1 FTR1 (17, of which INF2 MDT2 ROCK1 hold the docks); Cassius TANK3 RECON2 MDT1 INF2 (8). "
                     "Threat/answer: marine tanks and Md Tanks on the causeway -> the two bridges (8,9) (8,12) are the pocket's only gates besides the north gap (4,7): "
                     "hold them with Tanks/MDT, ARTs behind the river; marine ART and Rockets on the east bank hit the causeway (range 4) -> Recon sees them, the mountain nest (17,6..8) "
                     "gives cover, ART answers; the Fighter -> the AA and the quay's roads; Cassius's tank rush down the gap (4,7) -> ridge choke with ART behind.")
    # sea: south of the quay, the channel across the whole map, the east sea
    m.rect("~", 0, 15, 22, 17)
    m.rect("~", 19, 0, 22, 17)
    m.rect("~", 28, 0, 29, 17)
    # ridge between Cassius's plain and the quay pocket, gap at x=4; river along the pocket's east side
    m.rect("^", 0, 7, 3, 7).rect("^", 5, 7, 8, 7)
    m.river([(8, 8), (8, 14)])
    # camp ridge (Varro's) with its gate at x 13, and the mountain nest at the causeway head
    m.rect("^", 10, 6, 12, 6).rect("^", 14, 6, 18, 6)
    m.rect("^", 17, 7, 18, 8)
    # --- roads ---
    m.line("R", [(4, 4), (4, 9), (7, 9)])
    m.line("R", [(9, 9), (18, 9)])
    m.line("R", [(23, 9), (26, 9)])
    m.bridge(8, 9).bridge(19, 9, 22, 9)
    m.line("R", [(5, 12), (7, 12)]).bridge(8, 12).line("R", [(9, 12), (13, 12), (13, 9)])
    m.line("R", [(13, 6), (13, 9)])
    m.line("R", [(1, 14), (7, 14)])
    m.line("R", [(4, 9), (4, 14)])
    # --- the player's quay ---
    m.put("1", 3, 13).put("B", 5, 13).put("P", 6, 14)
    m.puts("c", [(2, 10), (10, 13)])
    m.puts("f", [(1, 9), (6, 10), (2, 12), (7, 14), (0, 12)])
    # --- Cassius's NW plain ---
    m.put("3", 3, 3).put("B", 5, 3)
    m.puts("f", [(1, 2), (2, 5), (6, 5), (7, 3), (0, 4)])
    m.puts("c", [(6, 1)])
    # --- Varro's camp, north ---
    m.put("2", 15, 2).put("B", 12, 2).put("B", 17, 2).put("A", 15, 4)
    m.line("R", [(13, 2), (13, 6)], over=".f")
    m.line("R", [(14, 4), (14, 4)]) if False else None
    m.puts("c", [(12, 4), (17, 4)])
    # the city in the middle
    m.puts("c", [(13, 8), (11, 8), (15, 8), (11, 10), (15, 10)])
    m.puts("f", [(10, 11), (16, 11), (12, 11), (14, 11), (9, 7)])
    m.note("city", 13, 8, "the contested city (five neutral cities 11..15 x 8..10)")
    # --- the east bank and the docks ---
    m.put("P", 27, 5).put("P", 27, 12)
    m.rect(",", 28, 3, 28, 14)
    m.line("R", [(26, 5), (26, 13)])
    m.line("R", [(23, 3), (23, 9)])
    m.bridge(19, 3, 22, 3)
    m.line("R", [(17, 3), (18, 3)], over=".fc")
    m.puts("f", [(24, 6), (24, 12), (25, 2), (24, 15)])
    # --- units: player (pocket) ---
    m.units(1, INF, [(2, 11), (5, 10), (3, 14), (6, 13)])
    m.units(1, MECH, [(4, 11), (3, 9), (6, 11)])
    m.units(1, TANK, [(5, 9), (7, 11), (7, 13)])
    m.units(1, MDT, [(3, 10), (5, 11)])
    m.unit(1, RECON, 2, 13)
    m.units(1, ART, [(4, 12), (6, 12)])
    m.unit(1, AA, 4, 13)
    # Varro: camp and city advance, docks hold
    m.units(2, INF, [(14, 5), (12, 5)])
    m.units(2, INF, [(25, 5), (25, 13)], hold=True)
    m.units(2, MECH, [(13, 3), (16, 5)])
    m.units(2, TANK, [(14, 3), (13, 5), (15, 5)])
    m.unit(2, MDT, 16, 3)
    m.units(2, MDT, [(25, 7), (25, 11)], hold=True)
    m.units(2, ART, [(11, 3), (16, 4)])
    m.unit(2, ROCK, 25, 9, hold=True)
    m.unit(2, AA, 12, 3).unit(2, FTR, 14, 4)
    # Cassius
    m.units(3, TANK, [(4, 2), (4, 5), (5, 5)])
    m.units(3, RECON, [(2, 3), (3, 5)])
    m.unit(3, MDT, 3, 4)
    m.units(3, INF, [(5, 4), (2, 4)])
    # named places
    m.note("hq1", 3, 13, "the quay HQ (must not fall in phase 1)"); m.note("hq2", 15, 2, "Varro's HQ"); m.note("hq3", 3, 3, "Cassius's HQ")
    m.note("dock1", 27, 5, "east dock, north (Varro's port): breakout target"); m.note("dock2", 27, 12, "east dock, south: breakout target")
    m.note("causeway", 19, 9, "causeway bridge x 19..22 on row 9 (4 cells, one lane); the north bridge x 19..22 on row 3 is the second crossing")
    m.note("bridge_w1", 8, 9, "pocket gate bridge (river x=8)"); m.note("bridge_w2", 8, 12, "pocket gate bridge (south)")
    m.note("gap_n", 4, 7, "the one gap in the ridge between Cassius's plain and the quay pocket")
    m.note("camp_gate", 13, 6, "gate of Varro's camp ridge")
    m.note("airport", 15, 4, "Varro's airport")
    m.note("nest", 17, 7, "mountain nest at the causeway head (17..18 x 7..8)")
    return m
