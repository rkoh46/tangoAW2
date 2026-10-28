"""BH2 M3 Iron Ledger (Act I): Black Hole seizes an old Accord foundry in Green Earth's south.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole holds the south-west corner: its HQ, a port on the south shore and the
old Accord foundry, a Black Factory that is Black Hole's from the first turn. One Green Earth army under the tag pair Javier (the Accord's engineer) and Jess holds the north-east plateau behind a
pipe wall (HQ, two airports, a ring of bases) and the east (her command post, a base). The map is big because the factory's output is huge and the enemy needs room to answer it: they
get real production (bases, cities, airports), funds and strong units.
- Lanes: three trunk roads that follow the land (north, middle, south), each bridged over the river at a chosen crossing, with branches to the towns and the Com Towers. The pipe wall (x27, from the
  north edge to the mountain massif) shuts the plateau: the north road meets its seam (27,5) like a gate. Break the seam (Black Hole's artillery or tanks)
  or go round the massif on the east side.
- Where the fight happens: the two Com Towers (20,9) and (20,19) on spurs off the centre road: whoever holds them hits harder; the middle road's bridge; then the
  plateau gate and the east road.
- Properties: the foundry's two side buildings (neutral villages beside it), bases for the player; the enemy's bases ring the plateau and the east; villages every
  three cells on the roads; neutral bases in the centre.
- Threats and answers: the army's Fighters and Copter -> the player's Anti-Air (the factory builds it), its Tanks and Rockets -> Md Tanks and artillery of the factory.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 30


def build():
    m = Canvas("bh2_03", W, H)
    m.rect("~", 0, 27, 39, 29)
    # --- the river first: source at the north edge, five bends, mouth in the south sea; the roads cross it at three chosen bridges
    m.river([(17, 0), (17, 6), (18, 6), (18, 11), (16, 11), (16, 17), (14, 17), (14, 26)])
    # --- relief: ranges and forest belts that make the lanes (plain left open round the river and the Com Towers)
    m.blob("^", 28, 11, 3, 2, seed=1, wobble=0.25, only=".")                                  # the massif that ends the pipe wall
    belt(m, "^", [(1, 2), (6, 4), (11, 2)], width=2, seed=2, gaps=[(7, 4)])                  # the north-west range, a pass for the north road
    belt(m, "^", [(20, 1), (24, 2), (26, 1)], width=1, seed=3)
    belt(m, "^", [(36, 8), (37, 14)], width=1, seed=4); belt(m, "^", [(33, 1), (37, 3)], width=1, seed=5)
    belt(m, "^", [(1, 13), (3, 19)], width=1, seed=6)
    belt(m, "^", [(19, 24), (24, 25), (28, 23)], width=1, seed=7, gaps=[(22, 24)])
    belt(m, "^", [(30, 26), (37, 24)], width=1, seed=8, gaps=[(33, 25)])
    belt(m, "^", [(9, 11), (12, 13)], width=1, seed=9)
    belt(m, "f", [(3, 8), (9, 9)], width=1, seed=10); belt(m, "f", [(19, 3), (21, 8)], width=2, seed=11)
    belt(m, "f", [(21, 15), (24, 17)], width=2, seed=12, gaps=[(23, 16)]); belt(m, "f", [(26, 7), (25, 11)], width=1, seed=13)
    belt(m, "f", [(29, 16), (31, 20)], width=2, seed=14); belt(m, "f", [(6, 14), (7, 18)], width=1, seed=15)
    belt(m, "f", [(13, 3), (15, 7)], width=1, seed=16); belt(m, "f", [(34, 10), (36, 12)], width=1, seed=17)
    belt(m, "f", [(10, 25), (13, 26)], width=1, seed=18); belt(m, "f", [(33, 18), (36, 19)], width=1, seed=19)
    for i, (cx, cy, n) in enumerate([(23, 20, 4), (2, 5, 4), (31, 8, 3), (24, 12, 4), (8, 20, 3), (35, 23, 4), (21, 4, 3)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    # --- Mount Ember in the middle: a volcano (4 x 4 footprint x21..24, y12..15); its eruptions hit the ring of lane cells (19..26, 10..17) round it
    m.stamp("V", 22, 14)
    # --- the pipe wall with its seam (the north road's gate), ending in the massif
    m.pipe([(27, 0), (27, 9)]); m.put("Z", 27, 5)
    # --- the foundry (Black Hole's Black Factory) with its supply pipe
    m.stamp("F", 11, 20).put("I", 11, 17)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M3 Iron Ledger: Black Hole (HQ 1 (4,21)) holds the old Accord foundry, a Black Factory at (11,20) on its side. The enemy is one Green Earth army 2 led by the tag pair Javier + Jess (HQ 2 (32,4), plateau behind a pipe wall x27 with the seam (27,5); Jess's command post, a base, in the east at (34,20)). "
        "Com Towers (20,9) and (20,19). Player: a free CO pick. Player: INF5 MECH3 TANK4 MDT1 ART2 RECON1 AA2 APC1; the enemy army (46 units): INF12 MECH6 TANK9 MDT3 ART5 ROCKETS2 AA3 RECON3 FTR2 BCO1."))
    m.put("1", 4, 21).put("2", 32, 4).put("B", 34, 20).put("P", 6, 26).put("t", 20, 9).put("t", 20, 19)
    # --- roads that follow the land, bridges at (18,9), (16,14), (14,22); the north road ends at the seam (26,5) and goes on at (28,5)
    route(m, [(4, 22), (8, 23), (11, 22), (13, 22), (14, 22, "="), (16, 22), (20, 22), (25, 22), (30, 23), (34, 21)], seed=1)         # the south trunk
    route(m, [(8, 23), (7, 18), (9, 14), (15, 14), (16, 14, "="), (19, 14), (19, 11), (20, 10)], seed=2)                       # the middle trunk to the ring road
    route(m, [(20, 10), (25, 10), (26, 11), (27, 14), (26, 16), (25, 17), (20, 17), (19, 16), (19, 14)], seed=30)              # the ring road round Mount Ember: every lane of the middle passes its eruptions
    route(m, [(27, 14), (30, 14), (35, 14)], seed=31)                                                                              # the middle trunk, east of the ring
    route(m, [(7, 18), (4, 11), (8, 7), (14, 5), (17, 4, "="), (19, 4), (24, 5), (26, 5)], seed=3)                                    # the north trunk to the gate
    route(m, [(28, 5), (31, 5), (32, 5)], seed=4); route(m, [(32, 5), (36, 3)], seed=5); route(m, [(32, 5), (33, 9), (34, 14)], seed=6)
    route(m, [(22, 10), (21, 9)], seed=7); route(m, [(20, 22), (20, 20)], seed=8)                                              # the Com Towers' spurs
    route(m, [(30, 14), (33, 17), (34, 21)], seed=9); route(m, [(30, 23), (28, 19), (26, 16)], seed=10); route(m, [(35, 14), (37, 18), (36, 24)], seed=11)
    route(m, [(14, 5), (15, 8), (18, 8, "="), (21, 8), (22, 6)], seed=14); route(m, [(4, 11), (3, 6), (2, 3)], seed=15); town(m, 2, 3, "CC", seed=28)
    route(m, [(14, 5), (12, 3), (11, 1)], seed=16); town(m, 11, 1, "CC", seed=29)
    route(m, [(12, 22), (11, 22)], seed=12); route(m, [(6, 24), (6, 25)], seed=13)
    thin_roads(m)
    m.desertify(keep=0.45, rocks=0, seed=3)                       # the desert look: sparse scrub (the Desert tileset draws the rest)
    # --- the towns: Black Hole's district and the foundry's two side buildings, the Com Tower towns, the bridgeheads, the plateau's districts, Jess's east
    town(m, 5, 22, "BBC", seed=1); town(m, 6, 24, "BC", seed=2); town(m, 9, 22, "CC", seed=3); town(m, 13, 24, "C", seed=4)
    town(m, 8, 18, "CC", seed=5); town(m, 9, 14, "Cb", seed=6); town(m, 14, 14, "CC", seed=7)
    town(m, 19, 12, "CCb", seed=8); town(m, 27, 12, "C", seed=9); town(m, 21, 21, "CCb", seed=10); town(m, 17, 22, "C", seed=11)
    town(m, 16, 5, "CC", seed=12); town(m, 8, 8, "CCb", seed=13); town(m, 4, 11, "CC", seed=14); town(m, 22, 5, "CC", seed=15)
    town(m, 30, 5, "BC", seed=16); town(m, 31, 2, "AAB", seed=17, radius=3); town(m, 34, 4, "BBC", seed=18, radius=3); town(m, 33, 8, "BCC", seed=19, radius=3); town(m, 36, 3, "C", seed=20)
    town(m, 33, 16, "BCC", seed=21, radius=3); town(m, 36, 22, "BC", seed=22); town(m, 30, 22, "BCC", seed=23, radius=3); town(m, 27, 16, "Cb", seed=24)
    town(m, 26, 17, "C", seed=25); town(m, 36, 14, "C", seed=26); town(m, 22, 26, "CC", seed=27, roadside=False)
    neutralize(m, 15)
    m.tidy()
    shore(m, 1, (0, 27, 5, 27)); shore(m, 1, (7, 27, 13, 27)); shore(m, 1, (15, 27, 39, 27))      # the south shore: a long beach, the port's cove and the river mouth left open
    # --- units
    m.spread(1, {INF: 5, MECH: 3, TANK: 4, MDT: 1, ART: 2, RECON: 1, AA: 2, APC: 1}, (2, 15, 14, 26), seed=1, gap=0, avoid="~r=-^IZ#X12345QBCPTbcpt")
    m.spread(2, {INF: 6, MECH: 3, TANK: 4, MDT: 2, ART: 3, AA: 2, RECON: 1, FTR: 2, BCO: 1}, (28, 0, 38, 12), seed=2, gap=0, avoid="~r=-^IZ#X12345QBCPTbcpt")
    m.spread(2, {INF: 6, MECH: 3, TANK: 5, MDT: 1, ART: 2, ROCK: 2, RECON: 2, AA: 1}, (28, 15, 38, 26), seed=3, gap=0, avoid="~r=-^IZ#X12345QBCPTbcpt")
    m.note("hq", 4, 21, "Black Hole's HQ")
    m.note("enemy_hq", 32, 4, "the enemy's HQ (objective): Javier's, on the plateau"); m.note("jess_post", 34, 20, "Jess's command post (a base) in the east")
    m.note("foundry", 11, 20, "the old Accord foundry: Black Hole's Black Factory")
    m.note("gate", 27, 5, "pipe seam: the plateau's gate")
    return m
