"""M13 The Free Port (Act III): four armies fight over the Harbour Office on the isthmus between the north bay and the south sea."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 25, 22


def mx(x):
    return W - 1 - x


def build():
    m = Canvas("es13", W, H)
    m.header(armies=4, colours=(OS, GE, YC, BH), team=[1, 2, 3, 4], blackhole=True, objective=[1],
             comment="M13 The Free Port: capture the Harbour Office (neutral city) and hold it 3 days. Everyone fights everyone. "
                     "Start forces: player INF4 MECH2 TANK3 MDT2 RECON2 ART2 AA1 APC1 (17); Javier and Sonja each INF3 MECH1 TANK3 MDT1 RECON1 ART1 AA1 (11); "
                     "Kindle the same + FTR1 BCO1 (13). Threat/answer: tanks and Md Tanks -> own Tanks/MDT/ARTs behind the canals; Kindle's Fighter and Copter -> "
                     "AA on the line + bases; minicannons (6,6) (8,6) cover the north road only: go round by the bridges or take them with ART; "
                     "ART -> Recon to see, tanks to close; Landers/ships (ports on the bay and sea) -> Tanks/ART on the quay.")
    # the sea in the north, the bay, the south bay, the side seas
    m.rect("~", 0, 0, W - 1, 1)
    m.rect("~", 10, 2, 14, 6)
    m.rect("~", 10, 18, 14, 21)
    m.rect("~", 0, 10, 0, 18).rect("~", W - 1, 10, W - 1, 18)
    # the canals (rivers) cut the quarters from the central square: sources at the ridge, mouths on the south bay
    m.rect("^", 1, 8, 2, 8).rect("^", 5, 8, 7, 8).put("^", 8, 7)
    m.rect("^", mx(2), 8, mx(1), 8).rect("^", mx(7), 8, mx(5), 8).put("^", 16, 7)
    m.river([(8, 8), (8, 21)])
    m.river([(16, 8), (16, 21)])
    # the central square: ring of streets, the office, warehouses
    m.rect("R", 10, 8, 14, 12)
    m.rect(".", 11, 9, 13, 11)
    m.line("R", [(12, 8), (12, 12)]).line("R", [(9, 10), (15, 10)])
    m.put("c", 12, 10)
    m.puts("c", [(11, 9), (13, 9), (11, 11), (13, 11)])
    m.note("office", 12, 10, "Harbour Office: neutral city, the objective (hold 3 days)")
    # bridges, roads into the quarters
    for y in (10, 16):
        m.bridge(8, y).bridge(16, y)
    m.line("R", [(4, 8), (4, 10), (7, 10)], over=".f")
    m.line("R", [(mx(4), 8), (mx(4), 10), (mx(7), 10)], over=".f")
    m.line("R", [(6, 10), (6, 16), (7, 16)]).line("R", [(mx(6), 10), (mx(6), 16), (mx(7), 16)])
    m.line("R", [(9, 16), (15, 16)])
    m.line("R", [(12, 12), (12, 14)])
    m.line("R", [(12, 4), (12, 4)]) if False else None
    # Kindle's north: roads from her HQ and from the east shore down to the square
    m.line("R", [(7, 4), (9, 4), (9, 8)], over=".f")
    m.line("R", [(15, 3), (15, 8)], over=".f")
    m.line("R", [(15, 5), (16, 5)], over=".f")
    # --- properties ---
    # player's south quarter
    m.put("1", 12, 15).put("B", 10, 15).put("B", 14, 15).put("P", 12, 17)
    m.puts("f", [(9, 17), (15, 17), (9, 14), (15, 14)])
    # Javier west / Sonja east
    for f in (lambda x: x, mx):
        m.put("B", f(3), 12).put("B", f(3), 16).put("P", f(1), 14)
        m.puts("c", [(f(6), 12), (f(2), 19), (f(5), 18)])
        m.puts("f", [(f(5), 11), (f(2), 11), (f(3), 14), (f(2), 17), (f(5), 20)])
    m.put("2", 4, 14).put("3", mx(4), 14)
    # Kindle's north dock
    m.put("4", 7, 4).put("B", 5, 3).put("B", 5, 5).put("A", 3, 4).put("P", 9, 3).put("p", 15, 3)
    m.puts("c", [(11, 7), (13, 7), (16, 3)])
    m.put("F", 18, 6)                     # Black Factory, footprint (17..19, 4..7)
    for x in range(17, 20):
        for y in range(4, 8):
            if (x, y) != (18, 6):
                m.put("#", x, y)
    m.pipe([(18, 2), (18, 3)])            # the Factory's supply pipe above its top tile
    m.put("X", 20, 5).put("X", 7, 6)      # two Black Crystals
    m.put("S", 6, 6).put("S", 8, 6)       # two minicannons facing the road south
    m.puts("f", [(2, 3), (3, 2), (2, 6), (4, 6), (21, 7), (22, 7), (23, 3)])
    # --- units ---
    # player
    m.units(1, INF, [(10, 13), (11, 13), (13, 13), (14, 13)])
    m.units(1, MECH, [(9, 13), (15, 13)])
    m.units(1, TANK, [(11, 14), (13, 14), (12, 13)])
    m.units(1, MDT, [(10, 16), (14, 16)])
    m.units(1, RECON, [(9, 15), (15, 15)])
    m.units(1, ART, [(11, 16), (13, 16)])
    m.unit(1, AA, 12, 16).unit(1, APC, 11, 17)
    # Javier (army 2) and Sonja (army 3, mirrored)
    for army, f in ((2, lambda x: x), (3, mx)):
        m.units(army, INF, [(f(3), 10), (f(5), 12), (f(6), 13)])
        m.unit(army, MECH, f(2), 13)
        m.units(army, TANK, [(f(5), 13), (f(5), 15), (f(6), 11)])
        m.unit(army, MDT, f(6), 15).unit(army, RECON, f(7), 12).unit(army, ART, f(3), 15).unit(army, AA, f(5), 16)
    # Kindle (army 4)
    m.units(4, INF, [(10, 7), (12, 7), (14, 7)])
    m.unit(4, MECH, 9, 6)
    m.units(4, TANK, [(9, 7), (15, 7), (15, 6)])
    m.unit(4, MDT, 8, 5).unit(4, RECON, 16, 6).unit(4, ART, 8, 3).unit(4, AA, 6, 5)
    m.unit(4, FTR, 2, 4).unit(4, BCO, 3, 3)
    # named places
    m.note("hq1", 12, 15, "player HQ"); m.note("hq2", 4, 14, "Javier's HQ (Green Earth)"); m.note("hq3", mx(4), 14, "Sonja's HQ (Yellow Comet)"); m.note("hq4", 7, 4, "Kindle's HQ (Black Hole)")
    m.note("factory", 18, 6, "Black Factory (anchor; footprint 17..19 x 4..7)")
    m.note("crystal1", 20, 5, "Black Crystal beside the Factory"); m.note("crystal2", 7, 6, "Black Crystal south of Kindle's HQ")
    m.note("cannon1", 6, 6, "minicannon (facing down)"); m.note("cannon2", 8, 6, "minicannon (facing down)")
    m.note("bridge_w1", 8, 10, "west canal bridge to the square"); m.note("bridge_w2", 8, 16, "west canal bridge by the player's quarter")
    m.note("bridge_e1", 16, 10, "east canal bridge"); m.note("bridge_e2", 16, 16, "east canal bridge")
    m.note("gate_w", 4, 8, "Javier's north gate (road through the ridge)"); m.note("gate_e", mx(4), 8, "Sonja's north gate")
    m.note("port_player", 12, 17, "player's port on the south bay"); m.note("port_kindle", 9, 3, "Kindle's port on the bay"); m.note("port_free", 15, 3, "neutral port on the bay (east shore)")
    return m
