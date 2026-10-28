"""BH2 M2 The Quartermaster's Crate (Act I): Black Hole's depot convoy on its home island.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Asuka and Crumb hold the depot in the west with its HQ and two bases; the crate
truck (a named APC, `crate`) stands in the yard. It must reach the quay's port (26,19) in the south-east before the day limit. Jess's raiders come down from
the north-east (her HQ and bases) and hold the east road.
- Lanes: three roads that follow the land, each with its own bridge over the river: the north road (bridge (15,5)), the middle road (the halfway bridge (15,9)) and
  the south road (bridge (16,16)). The south road is the escape route: longer, through woods and hills, and it joins the quay road below Jess's reach.
- Where the fight happens: the halfway bridge and the Com Tower in the central massif (20,12), reached by a spur road: whoever holds it hits harder; then the
  east road x26 down to the quay.
- Properties: the depot's bases build the escorts; villages every few cells on the three roads; the quay's port is neutral: the objective, not a prize.
- Threats and answers: Jess has no ships or aircraft (so no Anti-Air for anyone): her Tanks and Recon rush the truck -> Black Hole's Tanks, Mechs and artillery
  in the middle, Infantry screens on the bridges; she can bring Tanks by the north road -> the escort has a second line on the south road.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 30, 22


def build():
    m = Canvas("bh2_02", W, H)
    m.rect("~", 0, 20, 29, 21)
    # --- the river first (roads are routed around it and over it at three chosen bridges): source at the north edge, two bends, mouth in the south sea
    m.river([(14, 0), (14, 4), (15, 4), (15, 12), (16, 12), (16, 19)])
    # --- relief: ranges and belts that shape the lanes, plain left open between them
    m.blob("^", 20, 12, 3, 2, seed=3, wobble=0.25, only=".")                                  # the central massif around the Com Tower
    belt(m, "^", [(19, 1), (23, 2), (28, 3)], width=1, seed=1, gaps=[(26, 2)])               # Jess's northern ridge
    belt(m, "^", [(28, 4), (28, 8)], width=1, seed=2)
    belt(m, "^", [(1, 2), (5, 3), (9, 1)], width=2, seed=3, gaps=[(5, 3)])                   # the north-west range, a pass at (5,3)
    belt(m, "^", [(2, 19), (7, 18), (12, 19)], width=1, seed=4, gaps=[(8, 18)])              # the southern hills below the south road
    belt(m, "^", [(18, 18), (22, 19), (27, 18)], width=1, seed=5, gaps=[(23, 19)])
    belt(m, "f", [(1, 6), (6, 6), (11, 7)], width=1, seed=6)                                   # the forest belt between the depot and the north road
    belt(m, "f", [(17, 2), (18, 6)], width=2, seed=7)                                          # the east-bank forest
    belt(m, "f", [(23, 16), (28, 13)], width=1, seed=8)
    belt(m, "f", [(11, 12), (12, 18)], width=1, seed=9, gaps=[(12, 16)])
    belt(m, "f", [(2, 15), (4, 17)], width=1, seed=10)
    for i, (cx, cy, n) in enumerate([(9, 11, 3), (21, 6, 4), (14, 14, 3), (25, 12, 4), (6, 3, 3), (14, 19, 3)]):
        m.cluster("f", cx, cy, n, seed=20 + i)
    # --- the towns: the depot (Black Hole), the bridgeheads, the east towns, the quay, Jess's fort
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M2 The Quartermaster's Crate: the crate truck (named APC `crate`, (6,12)) must reach the quay's port (26,19) in the south-east; a day limit is allowed (escort). Black Hole's HQ 1 (3,12) in the depot, "
        "Jess's HQ 2 (25,3). Three roads that follow the land: north (bridge (15,5)), middle (the halfway bridge (15,9)), south (bridge (16,16), the escape route); the east road to the quay. Com Tower (20,12) in the central massif. "
        "Player: Asuka + Crumb (forced tag), INF4 MECH2 TANK3 ART1 RECON1 APC(crate). Enemy (Jess): INF6 MECH3 TANK4 RECON2 ART2."))
    m.put("1", 3, 12).put("2", 25, 3).put("t", 20, 12).put("p", 26, 19)
    m.puts("B", [(5, 10), (5, 14)]).puts("C", [(4, 9), (4, 15), (2, 11)])                        # the depot's district
    m.puts("B", [(23, 4), (27, 5)]).puts("C", [(24, 2), (27, 3), (22, 3)])                       # Jess's fort
    # --- roads that follow the land (each leg bends round mountains and woods), bridges at (15,5), (15,9) and (16,16)
    route(m, [(6, 12), (8, 12), (9, 9), (13, 9), (15, 9, "="), (17, 9), (21, 9), (26, 9)], seed=1)          # the middle road: the halfway bridge
    route(m, [(8, 12), (9, 15), (14, 16), (16, 16, "="), (18, 16), (23, 16), (26, 16)], seed=2)             # the south road: the escape route
    route(m, [(9, 9), (10, 5), (14, 5), (15, 5, "="), (17, 5), (24, 5), (25, 4)], seed=3)                   # the north road to Jess's fort
    route(m, [(25, 4), (26, 7), (26, 9), (26, 14), (26, 18)], seed=4)                                         # the east road to the quay
    route(m, [(10, 5), (6, 4), (3, 6)], seed=11); town(m, 3, 6, "CC", seed=12)
    route(m, [(20, 9), (20, 11)], seed=5)                                                                       # the spur up to the Com Tower
    route(m, [(4, 12), (6, 12)], seed=6); route(m, [(4, 10), (5, 12)], seed=7)
    thin_roads(m)
    # towns at the junctions and bridgeheads
    town(m, 10, 9, "CC", seed=1); town(m, 10, 15, "CB", seed=2); town(m, 13, 9, "C", seed=3); town(m, 17, 9, "CC", seed=4)
    town(m, 22, 9, "CCb", seed=5); town(m, 22, 16, "CC", seed=6); town(m, 26, 12, "C", seed=7); town(m, 26, 17, "CC", seed=8)
    town(m, 17, 5, "C", seed=9); town(m, 12, 5, "C", seed=10); town(m, 18, 16, "C", seed=11)
    neutralize(m, 13)
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
