"""M12 Siege of Iron (Act III, snow, tag): Klaus and Aurelia take the Iron Bastion's HQ.

Design (docs/dev/map-design.md). The situation: Olaf's bastion stands on the snowfield: a keep of rock with four gates round his HQ, the bastion town
round the keep, and round the town the Iron Wall, a ring of pipeline with five gates and one seam; Andy's guns sit in the corridors and on the east
spur, his HQ in a rock pocket there. The legion comes from the south with a factory, an airfield and Aurelia's long guns.
- Lanes: outside the wall the snowfield is open, with a lateral road (y24); the wall's gates are north, west, east, south-west and south-east; the seam
  (17,20) on the straight south road is the shortcut a siege opens (breaking it saves the walk round to a side gate); inside, the town's ring streets
  lead to the keep's four gates.
- Where the fight happens: the forward neutral bases (12,22) and (22,22) before the south-west and south-east gates (the contested middle with the
  villages round them), then the town between the wall and the keep, then the keep.
- Properties: snowfield villages three cells apart; the bastion town's houses (cover for the infantry in the streets, income to whoever holds them);
  Olaf's two factories in the keep, Andy's on the spur; the silo (28,14) on the east approach.
- Threats and answers: Andy's guns in the corridors -> Aurelia's longer range and Onager, recons and the bomber to find them, the Tag Power; Olaf's
  Md tanks sallying from the gates -> Md tanks, mechs in the villages; the wall -> two side gates and the seam.
"""
import math, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 42, 30
KEEP = (17, 12)


def build():
    m = Canvas("es12", W, H)
    m.header(armies=3, colours=(GE, BM, OS), team=[1, 2, 2], objective=[1], comment=(
        "M12 Siege of Iron (snow): take Olaf's HQ 2 (17,12) in the keep (rock ring, gates (17,8) (12,12) (22,12) (17,16)). The Iron Wall: a pipe ring x8..26, y4..20 with road gates "
        "north (17,4), west (8,12), east (26,12), south-west (11,20), south-east (23,20) and the seam (17,20) on the south road. Andy's HQ 3 (37,12) in the east spur's pocket. "
        "Forward neutral bases (12,22) (22,22); silo (28,14). Player: ART3 ROCK2 RECON3 INF4 MECH3 TANK3 MDT2 AA1 BMB1, HQ (17,27), base (13,27), airport (20,27), funds 5000."))
    # --- the keep: a ring of rock round the HQ
    for y in range(H):
        for x in range(W):
            d = math.hypot((x - KEEP[0]) / 5.0, (y - KEEP[1]) / 3.6)
            if 0.80 <= d <= 1.12:
                m.put("^", x, y)
    # --- Andy's spur: a rock massif with a pocket
    for cx, cy, n, sd in ((34, 8, 12, 1), (39, 8, 10, 2), (34, 16, 12, 3), (39, 16, 10, 4), (33, 12, 4, 5), (40, 12, 3, 6)):
        m.cluster("^", cx, cy, n, seed=sd)
    m.rect(".", 35, 10, 39, 14, only="^")
    # --- snowfield woods and hills
    for cx, cy, n, sd, ch in [(3, 3, 7, 11, "f"), (3, 9, 6, 12, "f"), (3, 17, 6, 13, "f"), (5, 22, 6, 14, "f"), (12, 1, 5, 15, "f"), (22, 1, 5, 16, "f"),
                              (30, 3, 6, 17, "f"), (29, 20, 6, 18, "f"), (35, 22, 6, 19, "f"), (39, 26, 5, 20, "f"), (8, 27, 5, 21, "f"), (26, 27, 5, 22, "f"),
                              (1, 13, 4, 23, "^"), (1, 26, 4, 24, "^"), (31, 26, 4, 25, "^"), (40, 2, 4, 26, "^"), (6, 1, 3, 27, "^"), (28, 9, 4, 28, "f"),
                              (12, 7, 3, 29, "f"), (22, 17, 3, 30, "f"), (11, 17, 3, 31, "f"), (23, 7, 3, 32, "f"), (14, 23, 4, 33, "f"), (20, 23, 4, 34, "f"),
                              (36, 27, 4, 35, "f"), (40, 20, 3, 36, "^"), (3, 29, 3, 37, "f"), (16, 29, 3, 38, "f"), (29, 16, 3, 39, "f"), (6, 15, 3, 40, "^"),
                              (5, 8, 5, 41, "f"), (2, 20, 5, 42, "f"), (7, 18, 4, 43, "^"), (9, 2, 4, 44, "f"), (18, 2, 4, 45, "f"), (25, 2, 4, 46, "^"), (29, 7, 4, 47, "f"),
                              (30, 13, 4, 48, "f"), (28, 18, 4, 49, "^"), (33, 20, 4, 50, "f"), (38, 22, 4, 51, "f"), (41, 25, 3, 52, "^"), (33, 27, 4, 53, "f"), (23, 28, 4, 54, "f"),
                              (11, 25, 3, 55, "f"), (6, 28, 4, 56, "f"), (14, 16, 3, 57, "f"), (20, 16, 3, 58, "f"), (14, 8, 3, 59, "f"), (20, 8, 3, 60, "f"), (10, 15, 3, 61, "f"),
                              (24, 10, 3, 62, "f"), (19, 21, 3, 63, "f"), (15, 21, 3, 64, "f"), (36, 6, 3, 65, "f"), (31, 1, 3, 66, "^"), (2, 5, 3, 67, "^"), (27, 26, 3, 68, "f"),
                              (36, 25, 3, 69, "^"), (4, 26, 3, 70, "f"), (40, 15, 3, 71, "f"), (26, 15, 3, 72, "f"),
                              (13, 3, 4, 73, "f"), (21, 3, 4, 74, "f"), (6, 10, 4, 75, "f"), (29, 4, 4, 76, "^"), (31, 9, 3, 77, "f"), (27, 21, 3, 78, "f"), (8, 21, 3, 79, "f"),
                              (41, 9, 3, 80, "f"), (35, 29, 3, 81, "f"), (19, 25, 3, 82, "f"), (14, 28, 3, 83, "f"), (0, 18, 3, 84, "f"), (3, 14, 3, 85, "f"), (38, 1, 3, 86, "f"),
                              (25, 29, 3, 87, "f"), (12, 14, 3, 88, "f"), (22, 14, 3, 89, "f"),
                              (5, 4, 4, 90, "^"), (39, 4, 4, 91, "f"), (29, 27, 4, 92, "^"), (1, 7, 3, 93, "f"), (9, 26, 3, 94, "^"), (33, 5, 3, 95, "f"), (41, 28, 3, 96, "f"), (25, 22, 3, 97, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # --- the Iron Wall: a ring of pipeline with five road gates and one seam
    m.pipe([(8, 4), (26, 4), (26, 20), (8, 20), (8, 4)])
    # --- roads
    for pts in ([(17, 0), (17, 8)], [(17, 26), (17, 13)], [(0, 12), (12, 12)], [(22, 12), (36, 12)], [(13, 26), (11, 26), (11, 6)],
                [(21, 26), (23, 26), (23, 6)], [(2, 24), (11, 24)], [(18, 23), (32, 23)], [(11, 6), (23, 6)],
                [(32, 23), (32, 19), (37, 19), (37, 15)], [(13, 27), (13, 26)], [(20, 27), (20, 26), (17, 26)]):
        m.road(pts)
    for x, y in ((17, 4), (8, 12), (26, 12), (11, 20), (23, 20)):
        m.put("R", x, y)
    m.put("Z", 17, 20)
    for x, y in ((17, 8), (12, 12), (22, 12), (17, 16)):
        m.put("R", x, y)                                            # the keep's gates
    # --- properties
    m.put("1", 17, 27).put("B", 13, 27).put("A", 20, 27).puts("C", [(10, 28), (24, 28), (15, 25)])
    m.put("2", *KEEP).puts("B", [(15, 11), (19, 13)]).puts("C", [(15, 13), (19, 11)])
    m.put("3", 37, 12).put("B", 36, 14).puts("C", [(36, 10), (38, 14), (39, 11)])
    m.puts("b", [(12, 22), (22, 22)]).put("M", 28, 14)
    m.puts("c", [
        # the bastion town (between the wall and the keep)
        (11, 5), (14, 5), (20, 5), (23, 5), (9, 8), (13, 7), (21, 7), (25, 8), (9, 11), (9, 15), (25, 15), (25, 11), (13, 17), (21, 17), (15, 19), (19, 19),
        (11, 9), (23, 9), (11, 14), (23, 14), (16, 7), (18, 17),
        # the snowfield
        (2, 1), (8, 1), (14, 2), (20, 2), (26, 1), (33, 1), (38, 4), (4, 6), (1, 10), (5, 12), (2, 16), (5, 19), (1, 22), (6, 25), (3, 28), (8, 23),
        (13, 29), (21, 29), (28, 29), (28, 23), (31, 21), (35, 25), (40, 23), (41, 18), (30, 17), (29, 11), (30, 6), (34, 3), (41, 6), (36, 18), (26, 25), (39, 29)])
    m.ragged("^", 8, seed=1)
    # --- the legion in the south
    m.spread(1, {BMB: 1}, (18, 26, 22, 28), seed=1, gap=0)
    m.spread(1, {ART: 3, ROCK: 2, MDT: 2, AA: 1}, (6, 25, 28, 29), seed=2, gap=1)
    m.spread(1, {RECON: 3, TANK: 3}, (4, 22, 30, 26), seed=3, gap=1)
    m.spread(1, {INF: 4, MECH: 3}, (3, 23, 31, 29), seed=4, gap=1)
    # --- Olaf in the keep (hold) and his sally force; Andy's guns (hold) in the corridors and on the spur
    HOLD = dict(hold=True)
    for kind, x, y in ((INF, 15, 10), (INF, 19, 10), (INF, 16, 14), (INF, 18, 14), (MECH, 14, 12), (MECH, 20, 12), (ART, 17, 11)):
        m.unit(2, kind, x, y, **HOLD)
    m.spread(2, {MDT: 3, TANK: 3, AA: 1}, (9, 5, 25, 19), seed=5, gap=2)
    for kind, x, y in ((ART, 9, 19), (ART, 25, 19), (ART, 9, 5), (ART, 25, 5), (ROCK, 14, 18), (ROCK, 20, 18), (MIS, 17, 6), (INF, 36, 11), (INF, 38, 11), (MECH, 37, 13)):
        free = next(c for r in range(6) for c in ((x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1))
                    if m.inside(*c) and m.get(*c) in ".fR" and c not in {(u["x"], u["y"]) for u in m.u})
        m.unit(3, kind, *free, **HOLD)
    m.note("hq1", 17, 27, "player HQ; base (13,27), airport (20,27)").note("hq2", 17, 12, "Olaf's HQ in the keep: the objective").note("hq3", 37, 12, "Andy's HQ on the east spur")
    m.note("iron_wall", 8, 4, "the Iron Wall: pipe ring x8..26, y4..20, gates N (17,4), W (8,12), E (26,12), SW (11,20), SE (23,20)")
    m.note("seam", 17, 20, "the Iron Wall's seam on the south road")
    m.note("fwd", 12, 22, "forward neutral bases (12,22) and (22,22)").note("silo", 28, 14, "neutral missile silo on the east approach")
    return m
