"""BH2 M1 Black Insight (Act I): Asuka's first landing, on Drake's Halyard Isle. Fog.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole's home island lies in the south with its HQ, two ports and the Landers;
Drake's marines hold Halyard Isle in the north, his HQ in the fort on the ridge, a port in the headland, his cruisers in the strait. In the fog the player
cannot see a thing: Asuka's intel (a Recon, the Cruisers' sight) is the lesson.
- Lanes: two long beaches on the isle's south coast (the west strand x 3..10 and the east strand x 17..26, two to three cells deep: Landers load and unload on
  any cell of them), a mid-strait islet with a village between the west and east channels, a road inland from each strand (west, headland, east), two lateral
  roads between them, the river bridged where the roads cross.
- Where the fight happens: the strands and the farms above them (villages and a neutral base each side), the headland town, then the fort's three approaches.
- Threats and answers: Drake's two Cruisers and Submarine -> the player's Cruisers and the Battleships the home ports build; his tanks on the strands ->
  Tanks of the second Lander trip, Mechs and artillery; the fort's artillery -> the river-road approach through the woods. Drake has no airfield, so the player
  needs no Anti-Air.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 30, 28

# every row is three groups of ten columns (x 0..9, 10..19, 20..29), joined; properties and units are put below
G = [
    "~~~~~^^f.. f.^^^f.... ..-.^^~~~~",   # 0
    "~~~^^^f... ^^^^^^^^^f f.-..f^^~~",   # 1
    "~~^^f..... ^.......^f .f-..f.^^~",   # 2
    "~^^......R R.......RR RR=RR.f.^~",   # 3
    "~^^.f....R ^^.....^^f ff-.R.f.^~",   # 4
    "~^.f....fR ^^^.R.^^^. f.-.R..f^~",   # 5
    "~..f.....R ..f.R.f... ..-.R.f.f~",   # 6
    "~^^.f....R .f..R..f.. ..-.R.f.^~",   # 7
    "~.fRRRRRRR RRRRRRRRRR RR=RR...f~",   # 8
    "~..f.R..f. f..fR.f... ..-.R..f.~",   # 9
    "~^.f.R..ff f.f.R.f... ..-.R..f.~",   # 10
    "~f..fRRRRR RRRRRRRRRR RR=RR.f..~",   # 11
    "~~.f.R..f. f.f.R.f... ..-.R..f~~",   # 12
    "~~~.fR.f.. ..f.R...f. ..-.R.f~~~",   # 13
    "~~~~~~~~~~ ~~~~~~~~~~ ~~~~~~~~~~",   # 14
    "~~~~~~~~~~ ~~~~~~~~~~ ~~~~~~~~~~",   # 15
    "~~~~~~~~~~ ~~~~~~~~~~ ~~~~~~~~~~",   # 16
    "~~~~~~~~~~ ~~~.f.~~~~ ~~~~~~~~~~",   # 17
    "~~~~~~~~~~ ~~~...~~~~ ~~~~~~~~~~",   # 18
    "~~~~~~~~~~ ~~~...~~~~ ~~~~~~~~~~",   # 19
    "~~~~~~~~~~ ~~~~~~~~~~ ~~~~~~~~~~",   # 20
    "~~~~~.f~.. f..fR..f.. ..~..~~~~~",   # 21
    "~~~f..f... f..fR..f.. ....f..~~~",   # 22
    "~~^^f..RRR RRRRRRRRRR RRR..f^^~~",   # 23
    "~~^^f..... ..f.R.f... ....f.^^~~",   # 24
    "~~^f...... ..f.R.f... ...f..^^~~",   # 25
    "~~~^..f... f..fR..f.. ..f...f~~~",   # 26
    "~~~~~..f.. f...R..f.. f..f.~~~~~",   # 27
]


def build():
    m = Canvas("bh2_01", W, H, fill="~")
    m.ascii(["".join(r.split(" ")) for r in G])
    # the river bends west at row 5 (rivers wander): x22 down to row 5, then x21 to the east strand; its two bridges follow
    for y in range(6, 14):
        m.g[y][22] = "R" if m.g[y][22] == "=" else "."
        m.g[y][21] = "=" if y in (8, 11) else "-"
    m.g[5][21] = "-"
    # the beaches: long, two to three cells deep (Landers load and unload on any cell of them)
    shore(m, 1, (3, 14, 11, 17)); shore(m, 1, (19, 14, 27, 17))
    shore(m, 1, (12, 16, 16, 20)); shore(m, 1, (9, 20, 19, 20))
    m.rect("~", 13, 16, 15, 16)          # (no beach on the islet's north side: the strait stays open water for the ships)
    m.put("r", 9, 18).put("r", 10, 18).put("r", 10, 19).put("r", 19, 18).put("r", 20, 18).put("r", 19, 19)     # reefs off the islet
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M1 Black Insight (fog): Black Hole's home island (south) against Drake on Halyard Isle (north). Take Drake's HQ 2 (14,3) in the fort. Beaches: the west strand x3..11 and "
        "the east strand x19..27 (rows 14..17, shoal strip one cell wide and long, AW2 draws no wider), the islet strand around (14,18). Roads: west x5, headland x14, east x24 (bridges over the river x22). Neutral port (15,13), "
        "neutral base (6,10) and (23,10), missile silo (26,6). Player: Asuka (forced), LAN4 CR2 INF4 MECH2 TANK2 RECON1 APC1 ART1. Enemy (Drake): INF8 MECH2 TANK3 ART2 RECON1 CR2 SUB1."))
    # --- properties
    m.put("2", 14, 3)
    m.puts("C", [(12, 2), (16, 2), (9, 6), (19, 6)]).put("B", 14, 4)
    m.puts("c", [(4, 6), (8, 10), (3, 12), (13, 12), (16, 12), (26, 5), (25, 3), (3, 9), (20, 10), (26, 12), (14, 18), (10, 3)]).puts("b", [(6, 10), (23, 10)]).put("p", 15, 13)
    m.put("M", 26, 8)
    m.put("1", 14, 24).puts("P", [(7, 22), (22, 22)]).puts("B", [(11, 24), (17, 24)]).puts("C", [(6, 24), (21, 24), (10, 26), (18, 26), (13, 22), (4, 25), (25, 25)])
    m.tidy()
    # --- Black Hole: the Landers wait in the two harbours and off the home beach, the ground army ashore beside them
    m.units(1, LAN, [(7, 21), (22, 21), (8, 20), (21, 20)]).units(1, CR, [(9, 19), (20, 19)] if False else [(11, 19), (17, 19)])
    m.units(1, INF, [(6, 22), (8, 22), (21, 22), (23, 22)]).units(1, MECH, [(9, 22), (20, 22)]).units(1, TANK, [(11, 22), (18, 22)])
    m.unit(1, RECON, 13, 23).unit(1, APC, 15, 23).unit(1, ART, 12, 24)
    # --- Drake: the fort's garrison (holds), the farms, the strands' pickets, the cruisers and a submarine in the strait
    m.units(2, INF, [(12, 3), (16, 3), (13, 5), (15, 5)], hold=True).units(2, ART, [(13, 4), (15, 4)], hold=True).unit(2, MECH, 11, 3, hold=True)
    m.units(2, INF, [(7, 8), (21, 8), (4, 10), (25, 11)]).units(2, TANK, [(5, 12), (24, 12), (14, 10)]).unit(2, MECH, 18, 9).unit(2, RECON, 8, 6)
    m.units(2, CR, [(6, 18), (22, 17)]).unit(2, SUB, 11, 18)
    m.note("hq", 14, 24, "Black Hole's HQ on the home island")
    m.note("enemy_hq", 14, 3, "Drake's HQ in the fort (objective)")
    m.note("strand_w", 6, 15, "west strand"); m.note("strand_e", 23, 15, "east strand"); m.note("islet", 14, 18, "the islet village between the channels")
    return m
