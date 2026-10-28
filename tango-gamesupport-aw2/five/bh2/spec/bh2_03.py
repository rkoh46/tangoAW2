"""BH2 M3 Iron Ledger (Act I): Black Hole seizes an old Accord foundry in Green Earth's south.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole holds the south-west corner: its HQ, a port on the south shore and the
old Accord foundry, a Black Factory that is Black Hole's from the first turn. Javier (the Accord's engineer) holds the north-east plateau behind a pipe wall with
his HQ, two airports and a ring of bases; Jess holds the east. The map is big because the factory's output is huge and the enemy needs room to answer it: they
get real production (bases, cities, airports), funds and strong units.
- Lanes: three east-west roads (north y5, middle y14, south y23) each bridged over the river; three north-south roads (x8, x24, x33). The pipe wall (x27, from the
  north edge to the mountain massif) shuts the plateau: the north road meets its seam (27,5) like a gate. Break the seam (Black Hole's artillery or tanks)
  or go round the massif on the east side.
- Where the fight happens: the two Com Towers (20,9) and (20,19) on spurs off the centre road: whoever holds them hits harder; the middle road's bridge; then the
  plateau gate and the east road.
- Properties: the foundry's two side buildings (neutral villages beside it), bases for the player; the enemy's bases ring the plateau and the east; villages every
  three cells on the roads; neutral bases in the centre.
- Threats and answers: Javier's Fighters and Copter -> the player's Anti-Air (the factory builds it), Jess's Tanks and Rockets -> Md Tanks and artillery of the factory.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 40, 30


def build():
    m = Canvas("bh2_03", W, H)
    m.rect("~", 0, 27, 39, 29)
    # --- roads
    m.road([(2, 23), (37, 23)]); m.road([(1, 14), (38, 14)]); m.road([(6, 5), (26, 5)]); m.road([(28, 5), (38, 5)])
    m.road([(8, 5), (8, 23)]); m.road([(24, 3), (24, 23)]); m.road([(33, 5), (33, 23)])
    m.road([(4, 21), (4, 23)]); m.road([(21, 9), (24, 9)]); m.road([(21, 19), (24, 19)]); m.road([(8, 20), (9, 20)])
    m.road([(12, 23), (12, 22)])                      # the foundry's gate on the south road
    m.road([(30, 5), (30, 9)]); m.road([(36, 14), (36, 20)]); m.road([(24, 10), (30, 10)]) if False else None
    # --- relief
    m.blob("^", 28, 11, 3, 2, seed=1, wobble=0.25, only=".")                          # the massif that ends the pipe wall
    m.cluster("^", 3, 3, 14, seed=2); m.cluster("^", 11, 9, 10, seed=3); m.cluster("^", 19, 2, 12, seed=4); m.cluster("^", 36, 2, 10, seed=5)
    m.cluster("^", 37, 11, 8, seed=6); m.cluster("^", 20, 25, 10, seed=7); m.cluster("^", 29, 25, 9, seed=8); m.cluster("^", 3, 12, 8, seed=9)
    m.cluster("^", 17, 17, 6, seed=10); m.cluster("^", 28, 20, 8, seed=11); m.cluster("^", 1, 26, 6, seed=12)
    for i, (cx, cy, n) in enumerate([(5, 8, 9), (14, 3, 8), (22, 4, 9), (35, 8, 9), (12, 17, 8), (18, 12, 8), (22, 15, 7), (28, 16, 9), (36, 17, 8), (34, 26, 8),
                                     (6, 25, 7), (14, 25, 8), (26, 7, 6), (31, 2, 6), (2, 18, 7), (21, 21, 6), (31, 12, 5), (10, 12, 6), (38, 21, 5), (16, 22, 5),
                                     (26, 21, 6), (5, 15, 5), (20, 11, 5), (37, 6, 5), (9, 2, 6)]):
        m.cluster("f", cx, cy, n, seed=30 + i)
    m.scatter("f", (0, 0, 39, 26), 0.04, seed=4)
    # --- the river: source at the north edge, three bends, mouth in the south sea
    m.river([(17, 0), (17, 9), (15, 9), (15, 26)])
    m.bridge(17, 5).bridge(15, 14).bridge(15, 23)
    # --- the pipe wall with its seam (the north road's gate), ending in the massif
    m.pipe([(27, 0), (27, 9)]); m.put("Z", 27, 5)
    # --- the foundry (Black Hole's Black Factory) with its supply pipe
    m.stamp("F", 11, 20).put("I", 11, 17)
    m.header(armies=3, colours=(BH, GE, BM), team=[1, 2, 2], objective=[1], comment=(
        "M3 Iron Ledger: Black Hole (HQ 1 (4,21)) holds the old Accord foundry, a Black Factory at (11,20) on its side. Javier (HQ 2 (32,4), Green Earth, plateau behind a pipe wall x27 with the seam (27,5)) and "
        "Jess (HQ 3 (34,20), Blue Moon colour, the east) are allies. Com Towers (20,9) and (20,19). Player: a free CO pick. Player: INF5 MECH3 TANK4 MDT1 ART2 RECON1 AA2 APC1; Javier INF6 MECH3 TANK4 MDT2 ART3 AA2 RECON1 FTR2 BCO1; "
        "Jess INF6 MECH3 TANK5 MDT1 ART2 ROCKETS2 RECON2 AA1."))
    m.put("1", 4, 21).put("2", 32, 4).put("3", 34, 20)
    m.put("P", 6, 26)
    m.puts("c", [(9, 17), (13, 24)]).put("t", 20, 9).put("t", 20, 19)
    m.place("B", 3, (1, 17, 14, 25), seed=1, gap=3).place("C", 5, (1, 15, 14, 25), seed=2, gap=2, reach=3)
    m.place("A", 2, (28, 0, 38, 8), seed=3, gap=4).place("B", 4, (28, 0, 38, 9), seed=4).place("C", 7, (28, 0, 38, 9), seed=5, gap=2, reach=3)
    m.place("B", 3, (28, 16, 38, 25), seed=6).place("C", 6, (28, 16, 38, 25), seed=7, gap=2, reach=3)
    m.place("b", 3, (16, 8, 26, 22), seed=8, gap=4)
    m.place("c", 4, (0, 0, 14, 13), seed=9, gap=2, reach=3).place("c", 4, (15, 0, 26, 13), seed=10, gap=2, reach=3).place("c", 5, (15, 14, 27, 26), seed=11, gap=2, reach=3)
    m.place("c", 3, (34, 9, 39, 14), seed=12, gap=2, reach=3).place("c", 3, (0, 15, 14, 26), seed=13, gap=2, reach=3)
    m.put("c", 2, 2).put("c", 3, 8).put("c", 19, 1)
    shore(m, 1, (0, 27, 5, 27)); shore(m, 1, (7, 27, 14, 27)); shore(m, 1, (16, 27, 39, 27))      # the south shore: a long beach, the port's cove and the river mouth left open
    m.tidy()
    # --- units
    m.spread(1, {INF: 5, MECH: 3, TANK: 4, MDT: 1, ART: 2, RECON: 1, AA: 2, APC: 1}, (2, 15, 14, 26), seed=1, gap=0)
    m.spread(2, {INF: 6, MECH: 3, TANK: 4, MDT: 2, ART: 3, AA: 2, RECON: 1, FTR: 2, BCO: 1}, (28, 0, 38, 12), seed=2, gap=0)
    m.spread(3, {INF: 6, MECH: 3, TANK: 5, MDT: 1, ART: 2, ROCK: 2, RECON: 2, AA: 1}, (28, 15, 38, 26), seed=3, gap=0)
    m.note("hq", 4, 21, "Black Hole's HQ")
    m.note("enemy_hq", 32, 4, "Javier's HQ (objective)"); m.note("enemy_hq2", 34, 20, "Jess's HQ (objective)")
    m.note("foundry", 11, 20, "the old Accord foundry: Black Hole's Black Factory")
    m.note("gate", 27, 5, "pipe seam: the plateau's gate")
    return m
