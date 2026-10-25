"""M9 Grain Ships (Act III, wasteland: the bay is lava): take the Kite Hill air depot and sink the three HOBB barges before day 11.

Design (docs/dev/map-design.md). The situation: Black Hole's freight yards: Kite Hill, a plateau crowned with rock and guarded by minicannons, holds
the air depot (12,4); the HOBB harbour on the east (the barges moored on the lava bay, the HQ, a factory and an airfield on the quay); the walled
freight yard in the south-east with the Black Cannon and the pipe factory. The legion lands in the south-west with an airport, a base and a strong
air wing; the clock is ten days.
- Lanes: the Kite river runs west to east across the map with four bridges (the west road, the farm track, the centre road, the east road); north of it
  three roads climb to the plateau's three gaps (west, south, east) and the harbour road; south of it the south road runs to the freight yard, which
  the HOBB pipeline walls off: its seam (22,19) is the only land gate.
- Where the fight happens: the river crossings and the ruined hamlets between the river and the hill (the contested middle), the hill's gaps under the
  minicannons, the quay.
- Properties: ruins (neutral cities) every few cells on both banks, a neutral base (16,15) south of the river for the infantry the captures need, the
  depot and the harbour; the Black Crystals heal Black Hole's units beside the quay.
- Threats and answers: the minicannons, Black Cannon and Deathray hit ground and sea only -> fighters, bombers and copters; AA tanks and missiles ->
  fighters first, own AA and missiles; tanks and the Piperunner -> rockets, tanks, artillery, bombers; the barges -> bombers, copters, or guns from the shore.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es09", 34, 22)
    m.header(armies=2, colours=(OS, BH), objective=[1], blackhole=True,
             comment="M9 Grain Ships (province: Kite Hill and the HOBB freight yards, Black Hole's harbour): the Aurean legion lands on the south-west road, crosses the Kite river and takes the "
                     "depot airport on the plateau (depot) and sinks the three HOBB barges (barge1..3) moored in the bay by day 10. "
                     "Wasteland look (lava bay). The HOBB pipeline (pipe wall x22, y16..21, seam at (22,19)) walls off the south-east freight yard and the Black Cannon: break the seam (attack it) to open a flank. Two approaches: north over the three bridges and up the hill's gaps, or east along the south road through the freight yard and the Black Cannon's shadow. "
                     "Threat/answer: minicannons (W/E/S on the depot's gaps), Black Cannon and Deathray shoot ground and sea only -> Fighters/Bombers/B Copters ignore them, Artillery outranges the minicannons; "
                     "enemy AA tanks and Missiles -> player Fighters strike first, own AA and Missiles escort, woods and river banks give cover; enemy Fighter/B Copter -> own Fighters and AA; "
                     "enemy Tanks/Md Tank/Piperunner (a strong ground unit that starts on the pipeline and its base builds more) -> Rockets/Tanks/Artillery and Bombers, Mechs at the bridges; Black Crystals heal BH units: kill what stands on them with Bombers. Barges (Landers on the sea): Bombers, Fighters, B Copters, "
                     "or Artillery/Tanks from the shore. "
                     "Player start: FTR3 BMB3 BCO2 AA2 MIS2 ART2 ROCKETS1 TANK3 MECH2 INF3 (23 units), funds 5000. "
                     "Black Hole start: INF5 MECH2 TANK3 MDT1 AA3 MIS2 ART2 FTR1 BCO1 + 3 barges (Landers) + 1 Piperunner on the pipeline = 24 units, about 1.2x the player's ground value. All inventions are Black Hole's.")
    # ---- the bay (east, open sea to the edge) with a lighthouse isle; the coast: first sea column of each row ----
    coast = [24, 24, 24, 25, 25, 25, 25, 25, 25, 25, 26, 26, 27, 27, 27, 27, 28, 28, 28, 28, 28, 28]
    for y, x0 in enumerate(coast):
        m.rect("~", x0, y, 33, y)
    for x, y in ((30, 6), (29, 7), (30, 7), (31, 7), (30, 8)):
        m.put(".", x, y)
    m.put("c", 30, 7)                                                  # the grain isle (a lighthouse city, reachable only by sea)
    # ---- Kite Hill: an irregular crown of mountains with three gaps (W, E, S) around the plateau ----
    m.blob("^", 12, 4, 7, 5, seed=11, wobble=0.2); m.blob(".", 12, 4, 4, 3, seed=12, wobble=0.15)
    m.rect(".", 5, 4, 9, 4, only="^").rect(".", 15, 4, 19, 4, only="^").rect(".", 13, 6, 13, 10, only="^")
    m.cluster("^", 3, 5, 7, seed=13); m.cluster("^", 19, 8, 6, seed=14); m.cluster("^", 7, 8, 5, seed=15)
    # ---- the Kite river: a spring in the western hills, bends, a mouth in the bay ----
    m.cluster("^", 0, 6, 6, seed=20)
    m.river([(0, 9), (6, 9), (6, 11), (12, 11), (12, 13), (19, 13), (19, 14), (26, 14)])
    bw, bs, be = (3, 9), (13, 13), (21, 14)
    # ---- woods and hedgerows ----
    for cx, cy, n, s in ((3, 12, 8, 30), (21, 2, 6, 32), (22, 9, 5, 33), (7, 15, 6, 34), (14, 19, 6, 35), (11, 20, 7, 36), (7, 20, 4, 37),
                         (22, 19, 5, 38), (28, 20, 6, 39), (18, 20, 4, 40), (2, 16, 4, 41), (16, 1, 4, 42), (9, 7, 3, 43), (26, 17, 3, 44), (16, 14, 5, 45)):
        m.cluster("f", cx, cy, n, seed=s)
    # ---- roads ----
    m.road([(5, 17), (9, 17), (9, 16), (17, 16), (17, 17), (21, 17)])      # the south road to the freight yard's pipe
    m.road([(13, 16), (13, 14)]).road([(21, 15), (21, 17)])
    m.road([(5, 17), (3, 17), (3, 10)])
    m.road([(9, 16), (9, 12)]).road([(9, 10), (9, 8)])                    # the farm track over the fourth bridge
    m.put("=", *bw).put("=", *bs).put("=", *be).put("=", 9, 11)
    m.road([(3, 8), (3, 4), (11, 4)])                                    # west bridge -> the hill's west gap
    m.road([(13, 12), (13, 5), (12, 5)])                                  # centre bridge -> south gap -> depot
    m.road([(21, 13), (21, 7)])                                             # east bridge -> harbour
    m.road([(13, 4), (20, 4), (20, 5)])                                   # east gap -> HQ
    m.road([(22, 7), (23, 7), (23, 2)])
    # ---- properties ----
    m.put("A", 12, 4)                                                # Kite Hill's depot airport
    m.put("2", 21, 5).put("B", 21, 8).put("C", 18, 7).put("C", 19, 2).put("C", 10, 6).put("C", 15, 6)
    m.puts("c", [(6, 7), (15, 15), (1, 3), (5, 2), (2, 12), (7, 13), (11, 9), (16, 10), (19, 10), (24, 11), (20, 2), (17, 1),
                 (1, 19), (4, 21), (12, 21), (19, 19), (15, 12), (20, 12), (26, 17), (25, 20), (8, 1)])   # ruined hamlets
    m.put("b", 16, 16)                                               # a neutral base south of the river
    m.put("1", 5, 17).put("A", 8, 19).put("B", 6, 15).put("C", 10, 18).put("C", 3, 15).put("c", 13, 18)
    # ---- Black Hole's inventions (all of them the enemy's: near its HQ and yard) ----
    m.put("W", 8, 5).put("E", 16, 5).put("S", 14, 8)                # minicannons on the depot's west, east and south gaps
    m.put("X", 24, 6).put("X", 24, 11)                               # Black Crystals beside the ports
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            m.put("#", 24 + dx, 19 + dy).put("#", 20 + dx, 1 + dy)
    m.put("n", 24, 19).put("D", 20, 1)                               # the Black Cannon over the bay's south shore, the Deathray on the top edge
    m.beach(22, 0, 31, 21)
    m.put("B", 25, 9).put("A", 25, 4)                                # the HOBB quay: a factory and an airfield (the bay is lava: no ports)
    m.puts("~", [(27, 13), (27, 14), (27, 15)])                         # (the river's mouth: open lava, a straight shore)
    # ---- the pipeline ----
    # the HOBB pipeline: a wall of pipe from the south edge up to the south road, across Black Hole's freight yard; the seam (22,19) is the breakable gate
    m.pipe([(22, 16), (22, 21)]).put("Z", 22, 19).puts("^", [(23, 15), (24, 15)])
    m.put("B", 23, 17)                                               # Black Hole's pipe base: connected to the pipeline, it builds Piperunners

    # ---- units ----
    m.unit(2, PIPER, 22, 17, hold=True)                              # the pipeline's Piperunner
    P = (0, 14, 12, 21)
    m.spread(1, {FTR: 3, BMB: 3}, (3, 17, 12, 21), seed=1, gap=0)
    m.spread(1, {BCO: 2, AA: 2, MIS: 2}, (3, 13, 12, 19), seed=2, gap=1)
    m.spread(1, {ART: 2, ROCK: 1, TANK: 3, MECH: 2, INF: 3}, (3, 12, 16, 18), seed=3, gap=1)
    H = dict(hold=True)
    # garrison of the hill (hold): infantry in the gaps, guns behind
    for kind, x, y in ((INF, 7, 4), (INF, 15, 4), (MECH, 12, 8), (MIS, 11, 5), (ART, 13, 3), (AA, 10, 4), (FTR, 14, 5)):
        m.unit(2, kind, x, y, **H)
    # the harbour guard (a mobile one: it sorties against the landing instead of sitting in its pits)
    for kind, x, y in ((AA, 20, 6), (BCO, 22, 4), (INF, 20, 4), (MIS, 19, 7)):
        m.unit(2, kind, x, y)
    m.unit(2, LAN, 26, 9, hold=True, name="barge1").unit(2, LAN, 27, 7, hold=True, name="barge2").unit(2, LAN, 26, 4, hold=True, name="barge3")
    # the advancing column
    m.spread(2, {TANK: 3, MDT: 1, MECH: 1, INF: 2, ART: 1, AA: 1}, (15, 11, 24, 17), seed=4, gap=1)
    m.note("depot", 12, 4, "Kite Hill air depot (enemy airport, capture it)")
    m.note("barge1", 26, 9, "HOBB barge (Lander, on the sea)").note("barge2", 27, 7, "HOBB barge").note("barge3", 26, 4, "HOBB barge")
    m.note("hq1", 5, 17, "player HQ").note("hq2", 21, 5, "Black Hole HQ (not an objective)")
    m.note("airport1", 8, 19, "player airport (FTR/BMB/BCO)").note("base1", 6, 15, "player base")
    m.note("bridges", bw[0], bw[1], "west bridge (%d,%d), centre (%d,%d), east (%d,%d)" % (bw + bs + be))
    m.note("minicannons", 8, 5, "W (8,5) covers the west gap, E (16,5) the east gap, S (13,8) the south gap")
    m.note("crystals", 23, 4, "Black Crystals (23,4) and (23,9) beside the ports")
    m.note("black_cannon", 24, 19, "Black Cannon facing up over the bay's south shore; the south-east freight yard is Black Hole's")
    m.note("deathray", 20, 1, "Deathray on the top edge (x19..21,y0..2), covers the harbour road; far from the player")
    m.note("isle", 29, 3, "grain isle: neutral city on a lava-locked islet").note("quay", 25, 9, "the quay's factory (25,9) and airfield (25,4): no ports on lava")
    # ---- wasteland (look 3): ruins, rough ground; the bay is lava ----
    m.puts("c", [(16, 19), (10, 13), (17, 9)])                           # more ruins (neutral cities in the wasteland)
    m.put("r", 29, 13).put("r", 30, 14).put("r", 29, 17).put("r", 31, 11)        # reefs (lava rocks) in the bay
    m.desertify(keep=0.3, rocks=13, size=5, seed=9)                  # (the wasteland look: sparse scrub, rock outcrops)
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
