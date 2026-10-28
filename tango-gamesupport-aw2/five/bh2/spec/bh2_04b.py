"""BH2 M4 Talons (Act I), front 2: the sky. Hawke's wing against Eagle's.

Design (docs/dev/map-design.md; BH1's sky-front rule, bh15b / bh_act3.rs M20): open sky and the pre-deployed air units, nothing else: no HQ, no property, no airport, no
B Copter, no ground unit and no Anti-Air or Missiles (there is no ground to put them on). The front is won (and lost) by AW2's rout rule: every unit of one side destroyed.
- Room: 22 x 16 cells, the two wings in loose formations 12 columns apart (not blocks): Fighters in front, Bombers behind them, the Stealths on the flanks.
- Threats and answers: Fighters answer Bombers and Stealths, Stealths answer Fighters' fuel and Bombers' escorts; Bombers hit nothing in the air, so each wing needs its Fighters as
  a screen: both wings are built that way. Eagle's wing is one Fighter and one Bomber stronger (the owner's wish: a hard fight for Hawke, who is forced).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 22, 16


def build():
    m = Canvas("bh2_04b", W, H)
    m.header(armies=2, colours=(BH, GE), objective=[1], nohq=True, comment=(
        "M4 Talons, front 2 (sky): Hawke (Black Hole, west) against Eagle (Green Earth, east); no HQ, no property, no ground. Hawke: FTR6 BMB3 STEALTH2; Eagle: FTR7 BMB4 STEALTH2."))
    # Hawke's wing, west: Fighters in an arc in front, Bombers behind, Stealths on the flanks
    m.units(1, FTR, [(6, 4), (7, 6), (7, 9), (6, 11), (5, 7), (5, 8)]).units(1, BMB, [(3, 5), (3, 8), (3, 11)]).units(1, STEALTH, [(5, 2), (5, 13)])
    # Eagle's wing, east
    m.units(2, FTR, [(15, 4), (14, 6), (14, 9), (15, 11), (16, 7), (16, 8), (14, 7)]).units(2, BMB, [(18, 5), (18, 8), (18, 11), (19, 7)]).units(2, STEALTH, [(16, 2), (16, 13)])
    m.note("wing_w", 5, 8, "Hawke's wing"); m.note("wing_e", 16, 8, "Eagle's wing")
    return m
