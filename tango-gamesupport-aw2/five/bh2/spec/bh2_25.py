"""BH2 M25 The Last Accord (Act V, the final mission): the Accord's citadel, a very long map, no time limit. Asuka + a free partner against a gauntlet: Nell holds the citadel; when a line breaks the same army goes on under the next commander from a new HQ with fresh troops.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The shape: a rampart corridor 64 columns long and 20 rows high (the largest map the engine allows is 1288 cells): the sea along the north edge (ragged, with harbours), land to the other three edges, and five pipe walls that cross the corridor from the north sea to
the south edge, each with two seam gates, so the map is six rooms in a row:
  room 0 (x 0..15) Black Hole's camp (HQ, bases, a port); wall x16.
  room 1 (x 17..27) Nell's citadel: her HQ (22,12); wall x28.                     -> TakeOver: Olaf (Blue Moon), HQ `Q1` (34,12) in room 2, fresh Blue Moon troops (heavy Md Tanks, Neotanks, Rockets).
  room 2 (x 29..39) Olaf's fort; wall x40.                                         -> TakeOver: Kanbei (Yellow Comet), HQ `Q2` (45,12) in room 3, the elite (Md Tanks, Neotanks, Megatanks, artillery).
  room 3 (x 41..49) Kanbei's hold; wall x50.                                       -> TakeOver: Eagle (Green Earth), HQ `Q3` (54,12) in room 4: the air fleet (Fighters, Bombers, Stealths, B Copters) from three airports.
  room 4 (x 51..57) Eagle's airfield; wall x58.                                    -> TakeOver: Aria (Orange Star's new commander), HQ `Q4` (61,12) in room 5; her HQ taken wins the mission.
  room 5 (x 59..63) Aria's last stand.
The first four HQs are held (their capture defeats nobody, only moves the story on); the walls end in the sea (north) and at the map edge (south): a Lander round a wall's tip is the other way in. The Allies use no Black Hole inventions: their defence is the walls, terrain, numbers and reinforcements.
- Where the fight happens: each wall's gates and the room behind it: the second room is the first real test, the fourth (the air) the hardest.
- Properties: a district of bases and cities in every room, an airport in rooms 4 and 5, Com Towers in rooms 0, 2 and 3, a missile silo in room 1.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 64, 20
WALLS = [16, 28, 40, 50, 58]
HQS = {"2": (22, 12), "Q1": (34, 12), "Q2": (45, 12), "Q3": (54, 12), "Q4": (61, 12)}


def build():
    m = Canvas("bh2_25", W, H, fill="~")
    rnd = random.Random("bh2_25/coast")
    T, t = {}, 4
    for x in range(W):
        if x % 4 == 0:
            t = max(3, min(6, t + rnd.choice([-1, 0, 1])))
        T[x] = t
    for w in WALLS:
        for x in (w - 1, w, w + 1):
            T[x] = T[w]
    for x in range(W):
        m.rect(".", x, T[x], x, H - 1)
    S = lambda x, y: snap(m, x, y)
    # --- the five walls: pipelines from the north sea to the south edge, two seam gates each
    for w in WALLS:
        m.pipe([(w, T[w]), (w, H - 1)]); m.put("Z", w, 9).put("Z", w, 15)
    # --- ridges and woods in each room
    for i, (x0, x1) in enumerate([(1, 14), (18, 26), (30, 38), (42, 48), (52, 56), (60, 63)]):
        belt(m, "^", [(x0, T[x0] + 2), ((x0 + x1) // 2, T[(x0 + x1) // 2] + 3), (x1, T[x1] + 2)], width=1, seed=10 + i, gaps=[((x0 + x1) // 2, T[(x0 + x1) // 2] + 3)])
        belt(m, "^", [(x0, 17), ((x0 + x1) // 2, 16), (x1, 17)], width=1, seed=20 + i, gaps=[((x0 + x1) // 2, 16)])
        belt(m, "f", [(x0 + 1, 8), (x1 - 1, 10)], width=1, seed=30 + i); belt(m, "f", [(x0 + 1, 14), (x1 - 1, 13)], width=1, seed=40 + i)
    for i, (cx, cy, n, ch) in enumerate([(6, 9, 3, "^"), (8, 15, 3, "f"), (12, 10, 3, "f"), (21, 8, 3, "^"), (24, 16, 3, "f"), (33, 9, 3, "^"), (36, 15, 3, "f"), (46, 9, 3, "^"), (44, 15, 3, "f"), (53, 9, 3, "^"), (55, 16, 3, "f"), (62, 8, 3, "^"), (62, 16, 3, "f"), (3, 15, 3, "^"), (26, 12, 3, "f")]):
        m.cluster(ch, cx, cy, n * 3, seed=70 + i)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M25 The Last Accord (normal look, fog, 64 x 20, no time limit): Asuka + a free tag partner (Black Hole, HQ 1 (4,12)) against one Orange Star army: Nell holds the citadel (HQ 2 (22,12)); each broken line is a TakeOver from a new held HQ (Q): Olaf (34,12), Kanbei (45,12), Eagle (54,12) and Aria (61,12), whose HQ is the last. "
        "Five pipe walls at x 16, 28, 40, 50, 58 (seam gates at rows 9 and 15). Com Towers (8,10), (35,15), (47,9); missile silo (23,16). Player: INF6 MECH3 TANK6 MDT3 ART4 ROCK2 RECON1 AA3 APC2 FTR3 BCO2 BS1 CR2 SUB1 LAN3; Nell: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1 AA1 FTR1 CR1."))
    m.put("1", 4, 12).put("2", 22, 12).put("Q", *HQS["Q1"]).put("Q", *HQS["Q2"]).put("Q", *HQS["Q3"]).put("Q", *HQS["Q4"])
    m.put("t", 8, 10).put("t", 35, 15).put("t", 47, 9).put("M", 23, 16)
    PORTS = [snap_coast(m, 5, 5), snap_coast(m, 22, 5), snap_coast(m, 36, 5)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    # roads: a trunk through every room, each room's road meets the wall at its gates
    for k, (x0, x1) in enumerate([(2, 15), (17, 27), (29, 39), (41, 49), (51, 57), (59, 62)]):
        ys = (11, 13)
        if x0 == 2:
            route(m, [S(4, 11), S(8, 11), S(12, 10), (15, 9)], seed=100 + k); route(m, [S(4, 13), S(8, 14), S(12, 15), (15, 15)], seed=110 + k)
        else:
            route(m, [(x0, 9), S(x0 + 3, 10), S((x0 + x1) // 2, 12), S(x1 - 3, 10), (x1, 9) if x1 < 60 else S(x1, 12)], seed=100 + k, wander=0.8) if x1 < 60 else route(m, [(x0, 9), S(x0 + 2, 11), S(61, 12)], seed=100 + k)
            route(m, [(x0, 15), S(x0 + 3, 14), S((x0 + x1) // 2, 13), S(x1 - 3, 14), (x1, 15) if x1 < 60 else S(x1, 14)], seed=110 + k, wander=0.8) if x1 < 60 else None
    for hq, seed in ((HQS["2"], 130), (HQS["Q1"], 131), (HQS["Q2"], 132), (HQS["Q3"], 133), (HQS["Q4"], 134)):
        route(m, [S(hq[0], hq[1] - 1), S(hq[0], 10)], seed=seed) if False else None
    thin_roads(m); fix_rungs(m)
    for args in [(4, 12, "BBC"), (7, 14, "BC"), (6, 9, "BC"), (11, 12, "C"), (13, 16, "C"), (13, 8, "C"), (8, 10, "c"), (3, 17, "c"),
                 (22, 12, "BBBC"), (19, 10, "BC"), (24, 14, "BC"), (26, 10, "C"), (20, 15, "C"), (25, 7, "C"), (23, 16, "c"),
                 (34, 12, "BBC"), (31, 10, "BC"), (37, 13, "BC"), (35, 15, "c"), (33, 7, "C"), (38, 10, "C"),
                 (45, 12, "BBC"), (43, 10, "BC"), (47, 14, "BC"), (47, 9, "c"), (44, 7, "C"),
                 (54, 12, "AAB"), (52, 10, "AB"), (56, 14, "AB"), (55, 8, "C"),
                 (61, 12, "BBAC"), (60, 9, "AB"), (62, 15, "BC"), (61, 6, "C")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 6)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, 10), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    for w in WALLS:
        if m.g[T[w] - 1][w] == ",":
            m.g[T[w] - 1][w] = "~"
    m.tidy()
    for (x, y) in [(10, 1), (20, 2), (30, 1), (42, 1), (52, 2), (60, 1), (14, 2), (46, 2)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 8, 14, 19), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 3, BCO: 2}, (1, 7, 14, 19), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1, AA: 1}, (18, 7, 27, 19), seed=3, gap=0, avoid=av)
    m.spread(2, {FTR: 1}, (18, 7, 27, 19), seed=4, gap=1, avoid=av)
    for k_, (x, y) in zip([BS, CR, CR, SUB, LAN, LAN, LAN], m.sea_near(6, 2, 7, box=(2, 0, 15, 3), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR], m.sea_near(22, 2, 1, box=(17, 0, 27, 3), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 4, 12, "Asuka's HQ"); m.note("enemy_hq", 22, 12, "Nell's HQ (the citadel): the first line")
    for i, (nm, who) in enumerate((("Q1", "Olaf's HQ"), ("Q2", "Kanbei's HQ"), ("Q3", "Eagle's HQ"), ("Q4", "Aria's HQ: the last"))):
        m.note(f"mark_hq{i + 1}", *HQS[nm], who)
    return m
