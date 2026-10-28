"""BH2 M30 The Last Accord (Act V, the final mission, part one): the Accord's four nations across the land, no pipes, no walls: the defences are rivers, mountains and chokepoints. 46 x 28 = 1288 cells (the engine's limit). Asuka + a free partner (Black Hole, army 5) against the Accord, in five armies
(the engine's five-army mode): Nell's Orange Star (army 1) holds the west; Olaf's Blue Moon (2), Kanbei's Yellow Comet (3) and Eagle's Green Earth (4) are present but dormant in their zones (a few holding units, no property but the HQ: they cannot build) until the stage before them falls, when their stage's troops land.
Part two (Aria's citadel) is bh2_31.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The shape: a continent crossed by two rivers. The Marne runs from the north edge down the west (x 15) and turns west along y 15 to the edge: Nell's plateau lies inside its bend, behind the river on the east and the south and a mountain wall on the north, reached by three bridges, two on the south, one on the east.
The Sere runs the whole map's height at x 31 with four bridges and divides the lake country (centre, Olaf) and the south-centre marsh from the mountains (Kanbei, north-east) and the plains (Eagle, south-east).
  Black Hole's camp (south-west, x 1..12, y 19..26): HQ 5 (4,23), a base district, three Black Crystals (the player's own inventions; no unit stands in a firing zone: there is no cannon here).
  Zone 1, Nell's river plateau (west, x 1..14, y 1..14): the keep's HQ 1 at (8,8), a fortified town cluster (cities and bases in blocks among woods and hills), a Com Tower, a missile silo; the Marne's three bridges are the gates.
  Zone 2, Olaf's lake country (north-centre, x 16..30, y 1..13): an irregular big lake with Olaf's HQ 2 on its island (24,6), two land causeways, small lakes and reef shoals; the lakes are the moat.
  Zone 3, Kanbei's highlands (north-east, x 32..45, y 1..13): a ring of mountains with two passes (west (35,6) and south (39,10)) round a plateau with Kanbei's HQ 3 at (39,6); switchback roads; ridges and cliffs outside.
  Zone 4, Eagle's plains (south-east, x 32..45, y 14..26): open plains, three airports and long runways behind the Sere, Eagle's HQ 4 at (38,20); few trees: the sky is the terrain.
  The marsh (south-centre, x 13..30, y 16..26): two irregular lakes and causeways: the road from the camp to the east.
Every HQ but the last is held (its capture defeats nobody, only moves the story on); the Allies use no Black Hole inventions: their defence is water, hills, numbers and the reinforcements each stage brings.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 46, 28
HQS = {"1": (8, 8), "2": (24, 6), "3": (39, 6), "4": (38, 20)}


def build():
    m = Canvas("bh2_30", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the lake country (Olaf): overlapping lobes, an arm, small lakes of three sizes, an island for the HQ and two causeways
    m.blob("~", 22, 6, 5, 4, seed=11, wobble=0.35); m.blob("~", 26, 8, 3, 3, seed=12, wobble=0.4); m.blob("~", 19, 3, 2, 2, seed=13, wobble=0.4); m.blob("~", 26, 3, 2, 2, seed=14, wobble=0.4)
    m.blob(".", 24, 6, 2, 2, seed=2, wobble=0.1); m.rect(".", 24, 1, 24, 4); m.rect(".", 24, 8, 24, 11)
    m.blob("~", 27, 13, 2, 1, seed=4, wobble=0.3)
    # --- the marsh: two irregular lakes with a causeway between (the road east)
    m.blob("~", 18, 22, 3, 3, seed=12, wobble=0.35); m.blob("~", 26, 21, 3, 3, seed=27, wobble=0.4)
    # --- the rivers
    m.river([(15, 0), (15, 15), (0, 15)])                                    # the Marne: Nell's moat
    m.river([(31, 0), (31, 27)])                                             # the Sere
    for x, y in ((15, 8), (31, 4), (31, 11), (31, 18), (31, 24), (4, 15), (10, 15), (15, 12)):
        m.put("=", x, y)
    # --- Nell's plateau: a mountain wall on the north, hills and woods inside
    for i, pts in enumerate([[(1, 1), (6, 1)], [(8, 1), (13, 2)], [(1, 2), (5, 3)], [(10, 3), (13, 4)]]):
        belt(m, "^", pts, width=1, seed=10 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(4, 5, 3), (12, 5, 3), (11, 12, 3), (3, 12, 3)]):
        m.cluster("^", cx, cy, n * 2, seed=40 + i)
    belt(m, "f", [(2, 7), (6, 6)], width=1, seed=20); belt(m, "f", [(9, 12), (13, 13)], width=1, seed=21); belt(m, "f", [(2, 10), (5, 13)], width=1, seed=22); belt(m, "f", [(11, 6), (13, 9)], width=1, seed=23)
    # --- Kanbei's highlands: a ring of mountains with two passes, ridges and cliffs outside
    m.rect("^", 35, 2, 43, 10); m.rect(".", 36, 3, 42, 9); m.put(".", 35, 6).put(".", 39, 10); m.put("f", 43, 4).put(".", 43, 8).put("f", 38, 2).put("f", 41, 10)
    for i, pts in enumerate([[(32, 1), (35, 1)], [(44, 1), (45, 4), (44, 6), (45, 9)], [(33, 4), (34, 7), (33, 9), (34, 11)], [(36, 12), (40, 13), (44, 12)], [(40, 11), (42, 13)], [(32, 12), (34, 13), (36, 13)]]):
        belt(m, "^", pts, width=1, seed=30 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(33, 8, 3), (44, 6, 3), (38, 13, 3), (33, 2, 2)]):
        m.cluster("^", cx, cy, n * 2, seed=60 + i)
    belt(m, "f", [(37, 4), (41, 8)], width=1, seed=36)
    # --- Eagle's plains: a few rocks and tree lines
    for i, (cx, cy, n) in enumerate([(33, 16, 2), (44, 25, 3), (33, 25, 3), (44, 15, 2)]):
        m.cluster("^", cx, cy, n * 2, seed=70 + i)
    belt(m, "f", [(36, 16), (41, 16)], width=1, seed=40); belt(m, "f", [(36, 25), (42, 25)], width=1, seed=41)
    # --- the camp and the marsh's shores
    belt(m, "^", [(1, 19), (5, 18)], width=1, seed=54); belt(m, "f", [(6, 22), (10, 24)], width=1, seed=55); belt(m, "f", [(2, 25), (7, 26)], width=1, seed=57)
    belt(m, "f", [(14, 17), (18, 18)], width=1, seed=50); belt(m, "^", [(28, 17), (30, 19)], width=1, seed=51); belt(m, "f", [(14, 25), (17, 26)], width=1, seed=52)
    belt(m, "^", [(17, 10), (17, 13)], width=1, seed=58); belt(m, "f", [(17, 1), (20, 1)], width=1, seed=59)
    m.header(armies=5, colours=(OS, BM, YC, GE, BH), team=(1, 1, 1, 1, 2), objective=[5], comment=(
        "M30 The Last Accord, part one (normal look, no fog, 46 x 28 = 1288 cells, no time limit, five armies): Asuka + a free tag partner (Black Hole, army 5, HQ 5 (4,23), south-west) against the Accord: Nell's Orange Star (army 1, HQ 1 (8,8), the river plateau); Olaf's Blue Moon (2, HQ 2 (24,6), the lake island), "
        "Kanbei's Yellow Comet (3, HQ 3 (39,6), the highlands) and Eagle's Green Earth (4, HQ 4 (38,20), the plains) are dormant until their stage (a few holding units, no properties but the HQ). Rivers: the Marne (x 15, then y 15) with bridges (15,8) (4,15) (10,15); the Sere (x 31) with bridges (31,4) (31,11) (31,18) (31,24). "
        "Com Tower (6,6), (28,15) and (33,21); missile silo (11,11); Black Crystals by Black Hole's HQ. Player: INF6 MECH3 TANK6 MDT3 ART4 ROCK2 RECON1 AA3 APC2 FTR3 BCO2; Nell: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1 AA1 FTR1."))
    m.put("5", 4, 23).put("1", *HQS["1"]).put("2", *HQS["2"]).put("3", *HQS["3"]).put("4", *HQS["4"])
    m.put("t", 6, 6).put("t", 28, 15).put("t", 33, 21).put("M", 11, 11)
    m.stamp("X", 2, 22).stamp("X", 7, 21).stamp("X", 5, 25)
    for (x, y) in [(20, 5), (27, 7), (21, 8), (26, 4), (19, 10), (20, 22), (25, 21)]:
        if m.inside(x, y) and all(m.get(a, b) in "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    PORTS = []
    # --- roads: the trunk from the camp over the Marne and round the zones; the bridges are the gates
    route(m, [S(4, 22), S(4, 18), (4, 16), (4, 15, "="), (4, 14), S(6, 11), S(8, 9)], seed=1, wander=0.6)
    route(m, [S(7, 21), S(10, 18), (10, 16), (10, 15, "="), (10, 14), S(9, 11)], seed=2, wander=0.6)
    route(m, [S(8, 8), S(12, 8), (14, 8), (15, 8, "="), (16, 8), S(18, 9), S(22, 11), (24, 11)], seed=3, wander=0.6)
    route(m, [S(11, 12), (14, 12), (15, 12, "="), (16, 12), S(18, 13)], seed=4)
    route(m, [S(24, 11), (24, 10)], seed=8); route(m, [(24, 2), S(24, 1), S(19, 1), S(17, 2), S(17, 8)], seed=9, wander=0.7)
    route(m, [S(24, 11), S(28, 11), S(30, 11), (31, 11, "="), (32, 11), S(34, 11), S(36, 11)], seed=6, wander=0.7)
    route(m, [S(30, 4), (31, 4, "="), (32, 4), S(34, 5), (35, 6), S(37, 6), S(39, 6)], seed=10, wander=0.5)
    route(m, [S(36, 11), S(39, 12), (39, 10), S(39, 8)], seed=11)
    route(m, [S(38, 12), S(38, 15), S(38, 19)], seed=14, wander=0.7)
    route(m, [S(33, 18), S(38, 20), S(43, 20)], seed=16); route(m, [S(33, 24), S(38, 22), S(43, 24)], seed=17)
    route(m, [S(30, 18), (31, 18, "="), (32, 18), S(33, 18)], seed=18); route(m, [S(30, 24), (31, 24, "="), (32, 24), S(33, 24)], seed=19)
    route(m, [S(9, 21), S(13, 20), S(16, 19), S(23, 18), S(28, 18), S(30, 18)], seed=22, wander=0.7)
    route(m, [S(10, 24), S(15, 25), S(23, 27), S(28, 25), S(30, 24)], seed=23, wander=0.7)
    route(m, [S(17, 8), S(17, 15), S(17, 17)], seed=24); route(m, [S(24, 11), S(24, 13), S(23, 15), S(23, 18)], seed=25)
    thin_roads(m); fix_rungs(m)
    # (Nell's zone and the camp are owned: capital letters; every other nation's zone is neutral: lowercase)
    for args in [(5, 23, "BBC"), (8, 21, "BC"), (6, 19, "BC"), (11, 24, "C"), (3, 26, "c"),
                 (8, 9, "BBBC"), (5, 6, "BC"), (11, 5, "BC"), (4, 11, "BC"), (12, 11, "BC"), (9, 4, "C"), (7, 12, "C"),
                 (24, 6, "bbc"), (17, 6, "c"), (20, 13, "cb"), (24, 11, "cb"), (17, 9, "c"), (28, 10, "c"), (22, 2, "cc"), (27, 2, "c"),
                 (39, 6, "bbbc"), (37, 5, "bc"), (41, 7, "bc"), (34, 3, "c"), (34, 10, "c"), (44, 4, "c"), (40, 12, "bc"), (43, 12, "c"),
                 (38, 20, "bbac"), (34, 17, "ab"), (42, 17, "ab"), (34, 24, "ab"), (42, 24, "a"), (33, 21, "c"), (40, 15, "c"), (44, 20, "c"), (36, 26, "c"),
                 (22, 17, "cb"), (28, 19, "c"), (14, 21, "c"), (16, 24, "c"), (24, 24, "cb"), (17, 14, "c"), (21, 15, "a")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(5, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 16, 14, 26), seed=1, gap=0, avoid=av)
    m.spread(5, {FTR: 3, BCO: 2}, (1, 16, 14, 26), seed=2, gap=1, avoid=av)
    m.spread(1, {INF: 6, MECH: 4, TANK: 5, MDT: 5, NEO: 3, ART: 4, ROCK: 3, MIS: 2, RECON: 1, AA: 2}, (3, 3, 13, 14), seed=3, gap=0, avoid=av)
    m.spread(1, {FTR: 2, BMB: 1}, (3, 3, 13, 14), seed=4, gap=1, avoid=av)
    # the dormant nations: a few holding units round each HQ (they never move; the stage's troops are what fights)
    for army, kinds, box, sd in ((2, {INF: 2, MDT: 1, ART: 1}, (22, 4, 26, 8), 5), (3, {INF: 2, MDT: 1, ART: 1}, (37, 4, 41, 8), 6), (4, {INF: 2, MDT: 1, AA: 1}, (36, 18, 40, 22), 7)):
        before = len(m.u)
        m.spread(army, kinds, box, seed=sd, gap=0, avoid=av)
        for u in m.u[before:]:
            u["hold"] = True
    m.note("hq", 4, 23, "Asuka's HQ"); m.note("enemy_hq", *HQS["1"], "Nell's HQ (Orange Star): the first line")
    for i, (nm, who) in enumerate((("2", "Olaf's HQ (Blue Moon)"), ("3", "Kanbei's HQ (Yellow Comet)"), ("4", "Eagle's HQ (Green Earth): the last of part one"))):
        m.note(f"mark_hq{i + 2}", *HQS[nm], who)
    return m
