"""BH2 M25 The Last Accord (Act V, the final mission): the Accord's citadel, as big as the engine allows (46 x 28 = 1288 cells), no time limit. Asuka + a free partner against a gauntlet: Nell holds the citadel; when a line breaks the same army goes on under the next commander from a new HQ with fresh troops.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The engine's limits for a custom map are 0x508 = 1288 cells and 40 rows (see docs/dev/bh2-maps.md): this is a 46 x 28 map, the largest rectangle that fits, and the zones are drawn to be five different places, not five copies of one box. They unlock in the story's order
round a ring, but nothing stops a player walking where he likes: a stage's HQ only moves the story on once the one before it has fallen.
  Black Hole's camp (south-west, x 1..12, y 19..26): HQ 1 (4,23), a base district, three Black Crystals (the player's own inventions; no unit stands in a firing zone: there is no cannon here).
  Zone 1, Nell's walled citadel (west, x 1..15, y 4..16): a square of pipe wall with three seam gates and a gatehouse on the west, the keep's HQ 2 at (8,10), bases and cities in rows, a Com Tower; open parade grounds.
  Zone 2, Olaf's frozen riverland (north-centre, x 16..31, y 1..13): a field of lakes and reef shoals with causeways, Olaf's HQ `Q1` on an island in the biggest lake (24,6) reached by two bridges, ports on the lake shores: terrain does the work of snow (the look is one for the whole map).
  Zone 3, Kanbei's fortress hills (north-east, x 32..45, y 1..13): a massif of ridges and cliffs cut by switchback roads, the fortress on its plateau: a pipe wall with seam gates, Kanbei's HQ `Q2` at (39,6).
  Zone 4, Eagle's airfields (south-east, x 31..45, y 14..26): open plains, three airports and long runways, Eagle's HQ `Q3` at (38,20); few trees: the sky is the terrain.
  Zone 5, Aria's moated keep (south-centre, x 13..30, y 14..26): an island in a moat reached by two bridges, a ring road round the keep, Aria's HQ `Q4` at (22,21): its capture wins.
The first four HQs are held (their capture defeats nobody, only moves the story on); the Allies use no Black Hole inventions: their defence is walls, water, hills, numbers and the reinforcements each stage brings.
- Threats and answers: Nell's walls and artillery -> the Crystals' healing line and Black Hole's Rockets and Md Tanks; Olaf's heavy tanks and rockets over the causeways -> Black Hole's own artillery across the water; Kanbei's elite on the heights -> Md Tanks, Rockets and the player's air; Eagle's Fighters, Bombers and Stealths -> Anti-Air (3 start) and Fighters;
  Aria's mixed keep -> everything that is left.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 46, 28
HQS = {"2": (8, 10), "Q1": (24, 6), "Q2": (39, 6), "Q3": (38, 20), "Q4": (22, 21)}


def build():
    m = Canvas("bh2_25", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- zone 2: the frozen riverland: a big lake with Olaf's island, smaller lakes, reef shoals
    # (the big lake is four overlapping lobes, a long bay to the south-east and a narrow arm to the north-west; the small lakes are three different sizes)
    m.blob("~", 23, 6, 6, 4, seed=11, wobble=0.35); m.blob("~", 28, 8, 4, 3, seed=12, wobble=0.4); m.blob("~", 20, 3, 3, 2, seed=13, wobble=0.4); m.blob("~", 27, 3, 2, 2, seed=14, wobble=0.4)
    m.blob(".", 24, 6, 2, 2, seed=2, wobble=0.1); m.rect(".", 24, 1, 24, 4); m.rect(".", 24, 8, 24, 11)       # (Olaf's island: a causeway north and south)
    m.blob("~", 18, 11, 4, 2, seed=3, wobble=0.35); m.blob("~", 30, 12, 2, 1, seed=4, wobble=0.3); m.blob("~", 16, 3, 1, 3, seed=5, wobble=0.3)
    # --- zone 5: the moat round Aria's keep
    # (an irregular moat: a main pool, a wide eastern bay, a western inlet and a southern lobe)
    m.blob("~", 22, 21, 6, 5, seed=6, wobble=0.3); m.blob("~", 27, 19, 3, 3, seed=21, wobble=0.4); m.blob("~", 17, 22, 3, 3, seed=22, wobble=0.4); m.blob("~", 24, 25, 3, 2, seed=23, wobble=0.4); m.blob("~", 20, 16, 2, 1, seed=24, wobble=0.3)
    m.blob(".", 22, 21, 2, 2, seed=7, wobble=0.1); m.rect(".", 22, 15, 22, 19); m.rect(".", 22, 23, 22, 26)     # (the keep: a causeway north and south)
    # --- zone 1: Nell's wall: a square with a gatehouse on the west side and three seam gates
    m.pipe([(2, 9), (2, 5), (14, 5), (14, 15), (2, 15), (2, 12)]); m.put("Z", 8, 5).put("Z", 14, 10).put("Z", 8, 15)
    m.put("C", 2, 10).put("C", 2, 11)
    # --- zone 3: Kanbei's fortress on the plateau: a pipe wall with a gatehouse on the west
    m.pipe([(35, 7), (35, 3), (43, 3), (43, 9), (35, 9)]); m.put("Z", 39, 3).put("Z", 43, 6).put("Z", 39, 9)
    m.put("C", 35, 8).put("C", 34, 9)
    # --- relief by zone
    for i, pts in enumerate([[(2, 18), (8, 17)], [(18, 14), (22, 15)], [(10, 2), (14, 2)]]):
        belt(m, "f", pts, width=1, seed=10 + i)
    belt(m, "f", [(3, 7), (7, 7)], width=1, seed=20); belt(m, "f", [(9, 12), (13, 13)], width=1, seed=21); belt(m, "f", [(3, 13), (6, 14)], width=1, seed=22)
    # the hills: ridges and cliffs (zone 3)
    for i, pts in enumerate([[(32, 2), (35, 1)], [(44, 2), (45, 8)], [(32, 5), (34, 10)], [(36, 11), (44, 12)], [(32, 12), (38, 13)], [(40, 10), (42, 8)], [(37, 5), (38, 8)], [(41, 4), (42, 7)], [(45, 10), (44, 13)]]):
        belt(m, "^", pts, width=1, seed=30 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(33, 7, 4), (44, 5, 4), (36, 12, 4), (41, 12, 4), (33, 3, 3)]):
        m.cluster("^", cx, cy, n * 3, seed=60 + i)
    # the airfields (zone 4): open plains, a few rocks
    for i, (cx, cy, n) in enumerate([(33, 16, 3), (44, 25, 3), (33, 25, 3), (44, 15, 3)]):
        m.cluster("^", cx, cy, n * 2, seed=70 + i)
    belt(m, "f", [(36, 15), (40, 15)], width=1, seed=40); belt(m, "f", [(36, 25), (42, 25)], width=1, seed=41)
    # the keep's grounds (zone 5) and the camp (south-west)
    belt(m, "^", [(14, 15), (17, 17)], width=1, seed=50); belt(m, "^", [(28, 16), (30, 18)], width=1, seed=51); belt(m, "f", [(14, 24), (18, 26)], width=1, seed=52); belt(m, "f", [(26, 25), (30, 24)], width=1, seed=53)
    belt(m, "^", [(1, 19), (5, 18)], width=1, seed=54); belt(m, "f", [(6, 22), (10, 24)], width=1, seed=55); belt(m, "f", [(2, 25), (7, 26)], width=1, seed=57)
    belt(m, "^", [(16, 8), (17, 13)], width=1, seed=58); belt(m, "^", [(30, 6), (31, 13)], width=1, seed=59)
    m.header(armies=2, colours=(BH, OS), objective=[1], zones=[(2, 13, 14, 45, 27), (2, 16, 0, 45, 13)], comment=(
        "M25 The Last Accord (normal look, no fog, 46 x 28 = 1288 cells, no time limit): Asuka + a free tag partner (Black Hole, HQ 1 (4,23), south-west) against one Orange Star army: Nell holds the walled citadel (HQ 2 (8,10)); each broken line is a TakeOver from a new held HQ (Q): Olaf (24,6) on an island in the riverland, "
        "Kanbei (39,6) in the fortress hills, Eagle (38,20) among the airfields and Aria (22,21) in the moated keep, whose HQ is the last. Com Tower (7,8), (28,14) and (33,21); missile silo (6,13); Black Crystals by Black Hole's HQ. "
        "Player: INF6 MECH3 TANK6 MDT3 ART4 ROCK2 RECON1 AA3 APC2 FTR3 BCO2; Nell: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1 AA1 FTR1."))
    m.put("1", 4, 23).put("2", *HQS["2"]).put("Q", *HQS["Q1"]).put("Q", *HQS["Q2"]).put("Q", *HQS["Q3"]).put("Q", *HQS["Q4"])
    m.put("t", 7, 8).put("t", 28, 14).put("t", 33, 21).put("M", 6, 13)
    m.stamp("X", 2, 22).stamp("X", 7, 21).stamp("X", 5, 25)
    # reefs in the riverland
    for (x, y) in [(20, 5), (28, 7), (21, 8), (27, 4), (19, 10)]:
        if m.inside(x, y) and all(m.get(a, b) in "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    PORTS = [snap_coast(m, 18, 6), snap_coast(m, 30, 6)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    # --- roads: the trunk from the camp round the ring of zones, the gates, the causeways and bridges
    route(m, [S(4, 22), S(8, 18), (8, 16)], seed=1, wander=0.8); route(m, [S(3, 20), S(1, 15), S(1, 11), (2, 10)], seed=2, wander=0.7)
    route(m, [S(8, 14), S(8, 11)], seed=3) if False else route(m, [(8, 14), S(8, 12)], seed=3); route(m, [(8, 6), S(8, 9)], seed=4); route(m, [(13, 10), S(11, 10), S(9, 10)], seed=5)
    route(m, [(15, 10), S(16, 10), S(17, 12), S(22, 12), S(26, 11), S(31, 11)], seed=6, wander=0.8)
    route(m, [S(20, 12), S(21, 10), (24, 10)], seed=7) if False else None
    route(m, [S(24, 11), (24, 10)], seed=8); route(m, [(24, 2), S(24, 1), S(18, 1), S(16, 4), S(16, 9)], seed=9, wander=0.8)
    route(m, [S(31, 11), S(33, 11), S(36, 10), (34, 8)], seed=10, wander=0.7) if False else route(m, [S(31, 11), S(34, 11), S(36, 10)], seed=10)
    route(m, [(34, 8), S(33, 8), S(33, 5)], seed=11); route(m, [(36, 8), S(37, 6), S(39, 5)], seed=12); route(m, [S(41, 4), S(41, 8)], seed=13)
    route(m, [S(40, 10), S(40, 13), S(38, 16), S(38, 19)], seed=14, wander=0.8); route(m, [(39, 8), (39, 10)], seed=15)
    route(m, [S(33, 20), S(38, 20), S(43, 20)], seed=16); route(m, [S(34, 17), S(38, 20), S(42, 17)], seed=17) if False else None
    route(m, [S(31, 21), S(28, 21), S(26, 21)], seed=18); route(m, [S(22, 16), (22, 17)], seed=19); route(m, [(22, 25), S(22, 26)], seed=20); route(m, [S(15, 19), S(17, 21), S(18, 21)], seed=21)
    route(m, [S(9, 19), S(14, 19), S(18, 17), S(22, 16)], seed=22, wander=0.8)
    route(m, [S(PORTS[0][0], PORTS[0][1]), S(21, 4)], seed=23) if False else None
    thin_roads(m); fix_rungs(m)

    for args in [(4, 23, "BBC"), (8, 21, "BC"), (6, 19, "BC"), (11, 24, "C"), (3, 26, "c"),
                 (8, 10, "BBBC"), (5, 8, "BC"), (11, 8, "BC"), (5, 13, "C"), (11, 13, "C"), (9, 7, "C"), (12, 12, "C"), (3, 6, "c"), (4, 17, "c"),
                 (24, 6, "BBC"), (16, 6, "C"), (20, 12, "Cb"), (24, 11, "Cb"), (17, 8, "c"), (28, 9, "c"), (26, 12, "c"), (22, 2, "cc"), (27, 2, "c"),
                 (39, 6, "BBBC"), (37, 5, "BC"), (41, 7, "BC"), (33, 4, "c"), (33, 9, "c"), (44, 4, "c"), (36, 11, "bc"), (42, 12, "c"),
                 (38, 20, "BBAC"), (34, 17, "AB"), (42, 17, "AB"), (34, 24, "AB"), (42, 24, "A"), (31, 22, "C"), (40, 15, "C"), (44, 20, "c"), (36, 26, "c"),
                 (22, 21, "BBAC"), (19, 21, "BC"), (25, 21, "BC"), (22, 19, "C"), (22, 23, "C"), (17, 17, "c"), (28, 17, "c"), (15, 24, "c"), (29, 25, "c"), (17, 13, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    for (x, y) in ((44, 8),):
        if m.g[y][x] in "Bb":
            m.g[y][x] = "."
    neutralize(m, 5)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 16, 14, 26), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 3, BCO: 2}, (1, 16, 14, 26), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1, AA: 1}, (3, 6, 13, 14), seed=3, gap=0, avoid=av)
    m.spread(2, {FTR: 1}, (3, 6, 13, 14), seed=4, gap=1, avoid=av)
    m.note("hq", 4, 23, "Asuka's HQ"); m.note("enemy_hq", *HQS["2"], "Nell's HQ (the citadel): the first line")
    for i, (nm, who) in enumerate((("Q1", "Olaf's HQ"), ("Q2", "Kanbei's HQ"), ("Q3", "Eagle's HQ"), ("Q4", "Aria's HQ: the last"))):
        m.note(f"mark_hq{i + 1}", *HQS[nm], who)
    return m
