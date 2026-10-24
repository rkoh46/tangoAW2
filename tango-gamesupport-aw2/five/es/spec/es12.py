"""M12 Siege of Iron (Act III, tag mission, snow): the Iron Bastion of the Blue Moon marches, Olaf's HQ inside three rings of mountain walls, Grit's guns in the corridors and his HQ on the east spur."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es12", 42, 30)
    m.header(armies=3, colours=(OS, BM, BM), team=[1, 2, 2], objective=[1],
             comment="M12 Siege of Iron (tag, snow; province: the Iron Bastion, Blue Moon's fortress on the Frost March): the Aurean legion crosses the snowfield and takes Olaf's HQ 2 (17,13) in the heart of three rings of mountain walls "
                     "(outer about x4..30,y3..23; middle x9..25,y7..19; inner x12..22,y10..16); Grit's HQ 3 (37,13) sits on the east spur. "
                     "Gaps: outer SW (10,23) SE (24,23) and E (30,13); middle S (17,19) W (9,13) E (25,10); inner SW (13,16) SE (21,16) and N (17,10). "
                     "The gaps never line up: every ring forces a zigzag along a 3-4 cell corridor under the guns. "
                     "Threat/answer: Grit's Artillery and Rockets (hold) in the corridors -> Aurelia's extra range, Recons to find them, Bombers from the airport (20,27) (the Missiles (17,5) and AA are far from the south corridor: "
                     "strike the guns there first), Mechs and Infantry over the mountains straight to the guns; Olaf's Tanks and Md Tanks pour out of the gaps -> "
                     "Tanks/Md Tanks and Artillery hold the gaps, Rockets/Artillery fire at the choke; Olaf's AA vs the Bomber -> use Artillery on it or Bombers where it cannot reach. "
                     "Player start: ART3 ROCK2 RECON3 INF4 MECH3 TANK3 MDT2 AA1 BMB1 (22 units), HQ (17,27), base (13,27), airport (20,27), funds 5000. "
                     "Olaf: INF4 + MECH2 hold the inner ring, MDT3 TANK3 AA1 advance, ART1 holds; Grit: ART4 ROCK2 MIS1 hold, INF2 MECH1 hold at the spur (24 units, about 1.3x).")
    cx, cy = 17, 12
    import math, random

    def ring(rx, ry, seed, thick):
        """A wall of mountain round (cx, cy): an ellipse whose radius wanders smoothly with the angle, `thick` cells wide."""
        rnd = random.Random(f"es12/ring{seed}")
        ph = [rnd.random() * 6.28 for _ in range(3)]
        amp = (0.05, 0.04, 0.03)
        t = thick / ((rx + ry) / 2)
        for y in range(cy - ry - 3, cy + ry + 4):
            for x in range(cx - rx - 3, cx + rx + 4):
                if not m.inside(x, y):
                    continue
                d = math.hypot((x - cx) / rx, (y - cy) / ry)
                th = math.atan2(y - cy, x - cx)
                r = 1 + sum(a_ * math.sin(k * th + p_) for a_, k, p_ in zip(amp, (2, 3, 5), ph))
                if abs(d - r) <= t / 2:
                    m.put("^", x, y)
    ring(14, 11, 1, 2); ring(9, 8, 2, 2); ring(5, 4, 3, 1.4)
    # the gaps (never in line): outer SW / SE / E, middle S / W / E, inner SW / SE / N
    for x0, y0, x1, y1 in ((10, 21, 11, 25), (23, 21, 24, 25), (29, 12, 34, 13), (17, 18, 18, 21), (4, 12, 9, 13), (25, 9, 29, 10),
                           (13, 15, 14, 19), (20, 15, 21, 19), (17, 6, 18, 10)):
        m.rect(".", x0, y0, x1, y1, only="^")
    # the east spur: walls of mountain around Grit's pocket
    m.blob("^", 37, 12, 5, 6, seed=7, wobble=0.15); m.blob(".", 37, 12, 3, 4, seed=8, wobble=0.1)
    m.rect(".", 31, 12, 35, 13, only="^").rect(".", 37, 16, 37, 20, only="^")
    # the snowfield: drifts of wood and rocky outcrops
    for cx2, cy2, n, s in ((4, 27, 7, 10), (28, 28, 8, 11), (9, 28, 5, 12), (36, 26, 7, 13), (2, 19, 6, 14), (3, 7, 7, 15), (14, 0, 6, 16), (24, 1, 7, 17), (33, 3, 6, 18), (39, 22, 5, 19), (31, 18, 6, 26), (33, 21, 5, 27)):
        m.cluster("f", cx2, cy2, n, seed=s)
    for cx2, cy2, n, s in ((6, 24, 5, 20), (31, 25, 5, 21), (38, 2, 5, 22), (1, 2, 5, 23), (21, 29, 4, 24), (40, 28, 4, 25)):
        m.cluster("^", cx2, cy2, n, seed=s)
    # ---- roads ----
    m.road([(5, 26), (10, 26), (14, 26), (14, 24), (20, 24), (20, 26), (31, 26), (36, 26), (37, 21)])   # the south field's road
    m.road([(10, 26), (10, 22), (24, 22), (24, 26)])                           # through both outer south gaps along the first corridor
    m.road([(17, 22), (17, 19), (21, 19), (21, 15)]).road([(17, 19), (14, 19), (14, 15)])
    m.road([(10, 22), (6, 22), (6, 13), (10, 13)])                             # the west corridor
    m.road([(6, 13), (6, 8), (13, 8), (17, 8), (17, 6)])                       # the north corridor, up to the inner N gap
    m.road([(27, 10), (27, 12), (31, 12), (35, 12)]).road([(27, 12), (27, 18), (24, 22)])
    m.road([(27, 10), (22, 10) if False else (25, 10)])
    # ---- properties ----
    m.put("1", 17, 28).put("B", 13, 27).put("A", 21, 28).put("C", 9, 27).put("C", 26, 27).put("C", 17, 25).put("c", 3, 25).put("c", 33, 27).put("c", 4, 14).put("c", 38, 23)
    m.put("2", 17, 12).put("B", 15, 11).put("B", 19, 13).put("C", 10, 9).put("C", 24, 17).put("c", 6, 6).put("c", 28, 8).put("C", 12, 19).put("C", 22, 6)
    m.put("3", 37, 12).put("C", 36, 10).put("C", 38, 14)
    m.rect(".", 35, 10, 39, 14, only="^").put("3", 37, 12)
    # ---- units ----
    H = dict(hold=True)
    m.spread(1, {BMB: 1}, (18, 26, 22, 28), seed=1, gap=0)
    m.spread(1, {ART: 3, ROCK: 2, MDT: 2, AA: 1}, (8, 25, 26, 28), seed=2, gap=1)
    m.spread(1, {RECON: 3, TANK: 3}, (5, 23, 30, 26), seed=3, gap=1)
    m.spread(1, {INF: 4, MECH: 3}, (4, 24, 30, 28), seed=4, gap=1)
    # Olaf: the inner ring (hold), the corridors (advance); Grit's guns (hold) in the corridors
    for kind, x, y in ((INF, 15, 11), (INF, 19, 11), (INF, 16, 15), (INF, 19, 15), (MECH, 14, 13), (MECH, 20, 12), (ART, 17, 12)):
        m.unit(2, kind, x, y, **H)
    m.spread(2, {MDT: 3, TANK: 3, AA: 1}, (6, 8, 28, 21), seed=5, gap=2)
    def near(x, y):
        occ = {(u["x"], u["y"]) for u in m.u}
        for r in range(0, 6):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (x + dx, y + dy)
                    if max(abs(dx), abs(dy)) == r and m.inside(*c) and m.get(*c) in ".f" and c not in occ:
                        return c
    for kind, x, y in ((ART, 7, 20), (ART, 27, 19), (ART, 6, 9), (ART, 26, 7), (ROCK, 13, 21), (ROCK, 22, 21), (MIS, 17, 6), (INF, 36, 11), (INF, 38, 11), (MECH, 37, 14)):
        m.unit(3, kind, *near(x, y), **H)
    m.note("hq1", 17, 27, "player HQ; base (13,27), airport (20,27) (BMB production)").note("hq2", 17, 13, "Olaf's HQ in the inner ring: the final objective")
    m.note("hq3", 37, 13, "Grit's HQ on the east spur (a second objective)")
    m.note("ring_outer", 4, 3, "outer ring about x4..30,y3..23; gaps (10,23) (24,23) (30,13)")
    m.note("ring_middle", 9, 7, "middle ring about x9..25,y7..19; gaps (17,19) (9,13) (25,10)")
    m.note("ring_inner", 12, 10, "inner ring about x12..22,y10..16; gaps (13,16) (21,16) (17,10)")
    m.note("spur", 32, 8, "east spur mountains about x32..42,y7..19; pocket around (37,13); entries (37,19) south and (32,13) west")
    m.note("guns", 7, 20, "Grit's guns (hold): ART (7,20) SW, (27,20) SE, (6,9) NW, (26,8) NE corridors; ROCK in the south corridor near (13,21) and (22,21); MIS (17,6) north")
    m.note("airport", 20, 27, "player airport: Bombers")
    return m
