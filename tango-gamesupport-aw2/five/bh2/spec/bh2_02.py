"""BH2 M2 The Quartermaster's Crate (Act I): Black Hole's depot convoy on its home island.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Asuka and Crumb hold the depot in the west with its HQ and two bases; the crate
truck (a named APC, `crate`) stands in the yard. It must reach the quay's port (26,19) in the south-east before the day limit. Jess's raiders come down from
the north-east (her HQ and bases) and hold the east road.
- Lanes: three east-west roads, each with its own bridge over the river: the north road (y5, bridge (15,5)), the middle road (y9, the halfway bridge (15,9)) and
  the south road (y16, bridge (16,16)). The south road is the escape route: longer, through woods and hills, and it joins the quay road below Jess's reach.
- Where the fight happens: the halfway bridge and the Com Tower in the central massif (20,12), reached by a spur road: whoever holds it hits harder; then the
  east road x26 down to the quay.
- Properties: the depot's bases build the escorts; villages every few cells on the three roads; the quay's port is neutral: the objective, not a prize.
- Threats and answers: Jess has no ships or aircraft (so no Anti-Air for anyone): her Tanks and Recon rush the truck -> Black Hole's Tanks, Mechs and artillery
  in the middle, Infantry screens on the bridges; she can bring Tanks by the north road -> the escort has a second line on the south road.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 30, 22


def build():
    m = Canvas("bh2_02", W, H)
    m.rect("~", 0, 20, 29, 21)
    # --- roads first (the river and the bridges are laid over them)
    m.road([(2, 12), (8, 12)])
    m.road([(8, 9), (8, 12), (8, 16)])
    m.road([(8, 9), (26, 9)])                       # the middle road
    m.road([(8, 16), (26, 16)])                     # the south road: the escape route
    m.road([(26, 3), (26, 19)])                     # the east road to the quay
    m.road([(5, 5), (26, 5)])                       # the north road
    m.road([(5, 5), (5, 9)])
    m.road([(20, 9), (20, 11)])                     # the spur up to the Com Tower
    m.road([(12, 12), (12, 16)]); m.road([(8, 12), (12, 12)])    # a link between the middle and south roads west of the river
    m.road([(22, 9), (22, 16)])                     # a link east of the massif
    # --- terrain
    m.cluster("^", 24, 2, 14, seed=1); m.cluster("^", 28, 1, 6, seed=2)             # Jess's fortress ridges
    m.blob("^", 20, 12, 3, 2, seed=3, wobble=0.25, only=".")                           # the central massif around the Com Tower
    m.cluster("^", 3, 2, 12, seed=4); m.cluster("^", 11, 19, 9, seed=5); m.cluster("^", 3, 19, 8, seed=6)
    m.cluster("^", 18, 18, 10, seed=7); m.cluster("^", 12, 7, 6, seed=8); m.cluster("^", 24, 18, 6, seed=9)
    for i, (cx, cy, n) in enumerate([(10, 3, 8), (18, 3, 8), (22, 7, 7), (4, 8, 6), (10, 10, 7), (17, 14, 8), (24, 13, 8), (5, 16, 8), (14, 18, 7), (28, 12, 6),
                                     (2, 5, 5), (13, 14, 5), (19, 7, 5), (6, 12, 4), (28, 18, 5), (9, 18, 5), (1, 9, 4)]):
        m.cluster("f", cx, cy, n, seed=20 + i)
    m.scatter("f", (0, 0, 29, 19), 0.05, seed=3)
    # --- the river: source at the north edge, two bends, mouth in the south sea; bridges where the roads cross
    m.river([(14, 0), (14, 4), (15, 4), (15, 12), (16, 12), (16, 19)])
    m.bridge(15, 5).bridge(15, 9).bridge(16, 16)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M2 The Quartermaster's Crate: the crate truck (named APC `crate`, (6,12)) must reach the quay's port (26,19) in the south-east; a day limit is allowed (escort). Black Hole's HQ 1 (3,12) in the depot, "
        "Jess's HQ 2 (25,3). Roads: north y5 (bridge (15,5)), middle y9 (the halfway bridge (15,9)), south y16 (bridge (16,16), the escape route); the east road x26 to the quay. Com Tower (20,12) in the central massif. "
        "Player: Asuka + Crumb (forced tag), INF4 MECH2 TANK3 ART1 RECON1 APC(crate). Enemy (Jess): INF6 MECH3 TANK4 RECON2 ART2."))
    m.put("1", 3, 12).puts("B", [(6, 10), (6, 14)]).puts("C", [(4, 10), (4, 14), (9, 10), (10, 14), (2, 16)])
    m.put("2", 25, 3).puts("B", [(23, 4), (27, 6)]).puts("C", [(23, 2), (27, 3), (24, 7), (27, 9), (21, 4)])
    m.puts("c", [(11, 8), (12, 14), (17, 8), (18, 6), (23, 9), (23, 13), (19, 15), (13, 17), (10, 5), (6, 7), (18, 3), (24, 17), (27, 15), (22, 18)]).puts("b", [(22, 13), (12, 12)])
    m.put("t", 20, 12).put("p", 26, 19).put("c", 2, 2)
    m.unit(1, APC, 6, 12, name="crate")
    m.units(1, INF, [(5, 11), (5, 13), (7, 10), (7, 14)]).units(1, MECH, [(9, 9), (9, 16)]).units(1, TANK, [(9, 12), (10, 10), (10, 14)])
    m.unit(1, ART, 4, 12).unit(1, RECON, 11, 12)
    m.units(2, INF, [(24, 4), (26, 4)], hold=True).units(2, INF, [(23, 7), (27, 9), (21, 6), (25, 10)]).units(2, MECH, [(21, 8), (24, 9), (27, 12)])
    m.units(2, TANK, [(22, 10), (25, 12), (23, 14), (21, 5)]).units(2, RECON, [(27, 14), (20, 7)]).units(2, ART, [(24, 5), (26, 7)], hold=True)
    m.note("hq", 3, 12, "Black Hole's HQ in the depot")
    m.note("enemy_hq", 25, 3, "Jess's HQ (objective if the crate is lost)")
    m.note("crate", 6, 12, "the crate truck (APC, named crate) starts here")
    m.note("quay", 26, 19, "the quay's port: the crate's destination")
    m.note("halfway", 15, 9, "the halfway bridge on the middle road")
    m.note("escape", 16, 16, "the south road's bridge: the escape route")
    m.tidy()
    return m
