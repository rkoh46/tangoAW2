"""M12 Siege of Iron (Act III, tag mission, snow): the Iron Bastion, Olaf's HQ inside three rings of mountains, Grit's guns in the corridors and his HQ on the east spur."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es12", 24, 17)
    m.header(armies=3, colours=(OS, BM, BM), team=[1, 2, 2], objective=[1],
             comment="M12 Siege of Iron (tag, snow): take Olaf's HQ 2 (9,6) in the heart of three mountain rings (outer x1..17,y0..13; middle x4..14,y3..10; inner x6..12,y5..8). "
                     "Gaps: outer (5,13) (13,13) south and (17,8) east (toward Grit's spur); middle (9,10) south, (4,5) west, (14,8) east; inner (7,8) (11,8) south and (6,6) west. "
                     "The gaps never line up: every ring forces a zigzag along a 1-2 cell corridor under the guns. Grit's HQ 3 (21,7) on the east spur (plain pocket x20..22,y5..9; "
                     "mountain walls, entered from the south at (21,11) or from the outer ring's east gap at (17,8) through (18,8)..(19,8)). The player must reach both HQs (objective). "
                     "Threat/answer: Grit's Artillery and Rockets (hold) in the corridors -> Aurelia's extra range, Recons to find them, Bombers from the airport (12,15) (the Missiles (9,1) and AA (3,11) "
                     "are far from the south corridor: strike the guns there first), Mechs and Infantry over the mountains straight to the guns; Olaf's Tanks and Md Tanks pour out of the gaps -> "
                     "Tanks/Md Tanks and Artillery hold the gaps, Rockets/Artillery fire at the choke; Olaf's AA vs the Bomber -> use Artillery on it or Bombers where it cannot reach. "
                     "Player start: ART3 ROCK2 RECON3 INF4 MECH3 TANK3 MDT2 AA1 BMB1 (21 units), HQ (9,15), base (7,15), airport (12,15), funds 5000. "
                     "Olaf: INF4 + MECH2 hold the inner ring, MDT3 TANK3 AA1 advance, ART1 holds; Grit: ART4 ROCK2 MIS1 hold, INF2 MECH1 hold at the spur (24 units, about 1.3x).")
    # the three rings of mountains
    m.frame("^", 1, 0, 17, 13).frame("^", 4, 3, 14, 10).frame("^", 6, 5, 12, 8)
    m.put(".", 5, 13).put(".", 13, 13).put(".", 17, 8)
    m.put(".", 9, 10).put(".", 4, 5).put(".", 14, 8)
    m.put(".", 7, 8).put(".", 11, 8).put(".", 6, 6)
    # the east spur: walls of mountain around Grit's pocket, entered from the south (21,11) and from the outer ring's gap (the road (18,8)..(19,8))
    m.rect("^", 19, 3, 23, 3).rect("^", 19, 3, 19, 11).rect("^", 23, 3, 23, 11).rect("^", 19, 11, 23, 11)
    m.put(".", 21, 11).put(".", 19, 8)
    # the south field: woods for the player's cover, a ridge on the west
    m.rect("f", 15, 14, 18, 15).rect("f", 2, 14, 3, 15).put("f", 14, 12).put("f", 0, 11)
    # roads: the south field, then the gaps up to the bastion (no road inside the rings, snow)
    m.road([(5, 13), (5, 14)]).road([(13, 13), (13, 14)]).road([(3, 14), (21, 14)]).road([(21, 12), (21, 14)])
    m.road([(17, 8), (19, 8)])
    # properties
    m.put("1", 9, 15).put("B", 7, 15).put("A", 12, 15).put("C", 5, 15).put("C", 15, 13).put("C", 10, 15)
    m.put("c", 1, 15).put("c", 22, 14).put("c", 0, 8).put("c", 19, 14)
    m.put("2", 9, 6).put("B", 8, 2).put("B", 10, 2).put("C", 3, 2).put("C", 15, 2).put("c", 3, 11).put("c", 15, 11).put("C", 9, 9)
    m.put("3", 21, 7).put("C", 20, 5).put("C", 22, 9)
    # make sure the HQs have ground beside them
    taken = set()

    def spot(cx, cy, n, lo, hi, kinds=".f"):
        out = []
        for r in range(0, 14):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and m.inside(x, y) and m.get(x, y) in kinds and (x, y) not in taken and (x, y) not in out:
                        out.append((x, y))
                        if len(out) == n:
                            taken.update(out)
                            return out
        raise RuntimeError(f"no room near {cx},{cy}")

    def put(army, kind, cx, cy, n=1, lo=(0, 0), hi=(99, 99), kinds=".f", **kw):
        for x, y in spot(cx, cy, n, lo, hi, kinds):
            m.unit(army, kind, x, y, **kw)

    S = dict(lo=(0, 14), hi=(23, 16))
    put(1, BMB, 11, 14, **S); put(1, ART, 8, 14, 3, **S); put(1, ROCK, 10, 14, 2, **S)
    put(1, RECON, 6, 16, 3, **S); put(1, INF, 4, 14, 4, **S); put(1, MECH, 14, 15, 3, **S)
    put(1, TANK, 9, 16, 3, **S); put(1, MDT, 13, 16, 2, **S); put(1, AA, 12, 16, **S)
    # Olaf: the inner ring (hold), the corridors (advance), Grit's guns (hold) in the corridors
    I = dict(lo=(7, 6), hi=(11, 7), hold=True)
    put(2, INF, 8, 6, 4, **I); put(2, MECH, 9, 7, 2, **I)
    put(2, MDT, 9, 11, 3, lo=(2, 11), hi=(16, 12)); put(2, TANK, 3, 6, 2, lo=(2, 4), hi=(3, 9)); put(2, TANK, 15, 6, 1, lo=(15, 4), hi=(16, 9))
    put(2, AA, 3, 11, 1, lo=(2, 10), hi=(4, 12)); put(2, ART, 9, 4, 1, lo=(5, 4), hi=(13, 4), hold=True)
    put(3, ART, 3, 4, 1, lo=(2, 3), hi=(3, 5), hold=True); put(3, ART, 15, 4, 1, lo=(15, 3), hi=(16, 5), hold=True)
    put(3, ART, 3, 9, 1, lo=(2, 8), hi=(3, 10), hold=True); put(3, ART, 15, 9, 1, lo=(15, 8), hi=(16, 10), hold=True)
    put(3, ROCK, 6, 12, 1, lo=(4, 11), hi=(8, 12), hold=True); put(3, ROCK, 12, 12, 1, lo=(10, 11), hi=(14, 12), hold=True)
    put(3, MIS, 9, 1, 1, lo=(8, 1), hi=(10, 2), hold=True)
    put(3, INF, 21, 6, 2, lo=(20, 5), hi=(22, 9), hold=True); put(3, MECH, 21, 8, 1, lo=(20, 5), hi=(22, 9), hold=True)

    m.note("hq1", 9, 15, "player HQ; base (7,15), airport (12,15) (BMB production)").note("hq2", 9, 6, "Olaf's HQ in the inner ring: the final objective")
    m.note("hq3", 21, 7, "Grit's HQ on the east spur (a second objective)")
    m.note("ring_outer", 1, 0, "outer ring x1..17,y0..13; gaps (5,13) (13,13) (17,8)")
    m.note("ring_middle", 4, 3, "middle ring x4..14,y3..10; gaps (9,10) (4,5) (14,8)")
    m.note("ring_inner", 6, 5, "inner ring x6..12,y5..8; gaps (7,8) (11,8) (6,6)")
    m.note("spur", 19, 3, "east spur mountains x19..23,y3..11; pocket x20..22,y4..10; entries (21,11) south and (19,8) west")
    m.note("guns", 3, 4, "Grit's guns (hold): ART (3,4)-ish NW, (15,4) NE, (3,9) SW, (15,9) SE corridors; ROCK in the south corridor near (6,12) and (12,12); MIS (9,1) north")
    m.note("airport", 12, 15, "player airport: Bombers")
    return m
