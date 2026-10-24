"""M1 Landfall (Act I): Klaus's legion lands at Cape Astra. The fleet's sandbar in the south, a wide beach, a sea-wall of ridge, the fort with its gate."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es01", 18, 15)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment="M1 Landfall: land from the sandbar (south), cross the beach, take the fort HQ (north).")
    # the ridge behind the fort and the fort's walls (a gate on the road at x 8..9)
    m.rect("^", 0, 0, 17, 1)
    m.frame("^", 4, 2, 13, 6)
    m.rect(".", 8, 6, 9, 6)
    # a sea-wall of ridge across the beach head, open at the road and at the west and east flanks
    m.rect("^", 0, 7, 3, 7).rect("^", 14, 7, 17, 7)
    m.rect("f", 1, 3, 3, 5, only=".").rect("f", 14, 3, 16, 5, only=".")
    # the road from the gate to the beach
    m.road([(8, 2), (8, 8)])
    m.road([(9, 2), (9, 8)])
    m.road([(4, 8), (13, 8)])
    # the beach: sand (rows 7..8), shoal (rows 9..10) in the middle, surf
    m.rect("~", 0, 10, 17, 14)
    m.rect(",", 0, 9, 17, 9)
    # the fleet's sandbar in the south
    m.rect(".", 3, 13, 14, 14)
    m.rect(",", 3, 12, 14, 12)
    m.put("P", 3, 13).put("P", 14, 13)
    m.put("1", 8, 14)
    # the fort: the enemy HQ, its city and a base; a neutral city on the west shoulder of the beach
    m.put("2", 9, 3).put("C", 6, 4).put("C", 11, 4)
    m.put("c", 2, 8).put("c", 15, 8)
    m.scatter("f", (4, 7, 13, 8), 0.08, seed=3)
    m.put(".", 8, 7).put(".", 9, 7)
    # Klaus's legion on the sandbar, four Landers at its north shore (a Cruiser to answer Green Earth's)
    m.units(1, LAN, [(5, 12), (7, 12), (10, 12), (12, 12)])
    m.units(1, INF, [(5, 13), (6, 13), (10, 13), (11, 13)])
    m.units(1, MECH, [(7, 13), (12, 13)])
    m.units(1, APC, [(8, 13), (9, 13)])
    m.units(1, RECON, [(6, 14)]).units(1, ART, [(10, 14)])
    m.unit(1, CR, 8, 11)
    # Jess's wardens: the fort, the sea-wall, two cruisers offshore (Drake's)
    m.units(2, INF, [(7, 3), (10, 3), (5, 8), (12, 8)], hold=True)
    m.units(2, MECH, [(7, 5), (12, 5)], hold=True)
    m.units(2, TANK, [(8, 7), (9, 7), (6, 8)])
    m.units(2, ART, [(6, 5), (11, 5)], hold=True)
    m.unit(2, RECON, 13, 8)
    m.unit(2, CR, 1, 11).unit(2, CR, 16, 11)
    return m
