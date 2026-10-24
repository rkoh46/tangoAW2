"""M9 Grain Ships (Act III): the HOBB freight yards at Kite Hill. Capture the depot (airport on the plateau) and sink the three barges in the harbour basin by day 10."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es09", 22, 16)
    m.header(armies=2, colours=(OS, BH), objective=[1], blackhole=True,
             comment="M9 Grain Ships: take the depot airport on Kite Hill and sink the three barges (harbour basin, NE) before day 11. "
                     "Threat/answer: minicannons + Black Cannon + Deathray shoot ground and sea only -> Fighters/Bombers/B Copters ignore them, Artillery outranges the minicannons; "
                     "enemy AA tanks and Missiles -> player Fighters strike first, own AA and Missiles escort, woods and the river banks give cover; enemy Fighter/B Copter -> own Fighters and AA; "
                     "enemy Tanks/Md Tank -> Missiles are no help, use Tanks/Artillery/Mechs at the bridges; Black Crystals heal BH units: kill what stands on them with Bombers. "
                     "Player start: FTR3 BMB3 BCO2 AA2 MIS2 ART2 TANK3 MECH2 INF3 (22 units), funds 5000. "
                     "Black Hole start: INF4 MECH2 TANK3 MDT1 AA3 MIS2 ART2 FTR1 BCO1 + 3 barges (Landers) = 22 units, about 1.2x the player's ground value.")
    # the ridge on the top edge and the harbour basin (sea, shoal strip along the west coast, east edge open sea)
    m.rect("~", 16, 0, 21, 9)
    m.rect(",", 15, 0, 15, 9)
    m.rect("~", 15, 2, 15, 2).rect("~", 15, 8, 15, 8)       # sea beside the two ports
    # Kite Hill: a ring of mountains with three gaps (S, W, E)
    m.frame("^", 5, 1, 11, 7)
    m.put(".", 8, 7).put(".", 5, 4).put(".", 11, 4)
    # the river, bank to bank, with three bridges
    m.river([(0, 9), (14, 9)])
    # the grain isle (a lighthouse city the barges moor at; reachable only from the sea)
    m.rect(".", 19, 2, 20, 3).put("c", 20, 2).rect(",", 19, 4, 20, 4)
    # woods: cover for the west flank and the player's AA line
    m.rect("f", 6, 10, 7, 11).put("f", 5, 11).put("f", 9, 11).put("f", 9, 10)
    m.rect("f", 0, 5, 1, 7).put("f", 2, 6).put("f", 13, 7).put("f", 14, 6)
    m.rect("f", 15, 13, 16, 14).put("f", 14, 12)
    # roads
    m.road([(3, 4), (3, 8)]).road([(3, 4), (5, 4)])                  # west gap -> west bridge
    m.road([(3, 10), (3, 11)])
    m.road([(8, 12), (8, 5)])                                         # main road: south bridge -> gap -> depot
    m.road([(3, 12), (8, 12)])
    m.road([(11, 4), (12, 4)]).road([(12, 4), (12, 8)])               # east gap -> harbour road -> east bridge
    m.road([(12, 10), (12, 13)]).road([(12, 13), (17, 13)])
    m.bridge(3, 9).bridge(8, 9).bridge(12, 9)
    # Kite Hill's depot and the freight yard
    m.put("A", 8, 4)
    m.put("B", 8, 2).put("C", 7, 2).put("C", 9, 2)
    m.put("2", 13, 6).put("B", 13, 4).put("C", 14, 5).put("C", 13, 8).put("P", 14, 2).put("P", 14, 8)
    m.put("C", 4, 4).put("c", 1, 4)
    m.put("B", 17, 14).put("C", 18, 14).put("C", 16, 12)
    # Black Hole's inventions: three minicannons on the depot's gaps, a crystal pair at the basin, a Black Cannon over the basin, the Deathray on the top edge
    m.put("W", 6, 5).put("E", 10, 3).put("S", 9, 6)
    m.put("X", 14, 4).put("X", 14, 7)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            m.put("#", 19 + dx, 11 + dy).put("#", 2 + dx, 1 + dy)
    m.put("n", 19, 11).put("D", 2, 1)
    # the player's side
    m.put("1", 1, 13).put("A", 3, 13).put("B", 5, 13).put("C", 6, 12).put("C", 1, 11).put("c", 10, 13).put("c", 4, 15)

    taken = set()

    def free(x, y, air=False):
        return (m.inside(x, y) and m.get(x, y) in ".f" and (x, y) not in taken
                and not any(u["x"] == x and u["y"] == y for u in m.u))

    def spot(cx, cy, n=1, kinds=".f", lo=(0, 0), hi=(99, 99)):
        out = []
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and free(x, y) and m.get(x, y) in kinds and (x, y) not in out:
                        out.append((x, y))
                        if len(out) == n:
                            for c in out:
                                taken.add(c)
                            return out
        raise RuntimeError("no room")

    def put(army, kind, cx, cy, n=1, **kw):
        for x, y in spot(cx, cy, n, lo=kw.pop("lo", (0, 0)), hi=kw.pop("hi", (99, 99))):
            m.unit(army, kind, x, y, **kw)

    # player (plain only on the aircraft: parked by the airport; everything south of the river)
    P = dict(lo=(0, 10), hi=(9, 15))
    put(1, FTR, 3, 13, 3, **P); put(1, BMB, 4, 14, 3, **P); put(1, BCO, 2, 12, 2, **P)
    put(1, AA, 7, 11, 2, **P); put(1, MIS, 8, 13, 2, **P); put(1, ART, 5, 11, 2, **P)
    put(1, TANK, 8, 11, 3, **P); put(1, MECH, 4, 11, 2, **P); put(1, INF, 7, 14, 3, **P)
    # Black Hole: the garrison on Kite Hill (hold), the harbour guard (hold), the advancing column
    H = dict(hold=True)
    m.unit(2, INF, 7, 4, **H); m.unit(2, INF, 9, 4, **H); m.unit(2, MECH, 8, 6, **H); m.unit(2, MIS, 7, 3, **H)
    m.unit(2, ART, 9, 5, **H); m.unit(2, AA, 7, 5, **H); m.unit(2, FTR, 9, 3, hold=True)
    m.unit(2, AA, 13, 5, **H); m.unit(2, BCO, 13, 7)
    m.unit(2, LAN, 17, 2, hold=True, name="barge1").unit(2, LAN, 18, 5, hold=True, name="barge2").unit(2, LAN, 17, 8, hold=True, name="barge3")
    m.unit(2, TANK, 12, 7).unit(2, TANK, 11, 10).unit(2, MDT, 13, 10)
    m.unit(2, INF, 13, 3).unit(2, INF, 9, 8).unit(2, MECH, 14, 10)
    m.unit(2, ART, 11, 12)
    # notes for the mission code
    m.note("depot", 8, 4, "Kite Hill air depot (enemy airport, capture it)")
    m.note("barge1", 17, 2, "HOBB barge (Lander, on the sea)").note("barge2", 18, 5, "HOBB barge").note("barge3", 17, 8, "HOBB barge")
    m.note("hq1", 1, 13, "player HQ").note("hq2", 13, 6, "Black Hole HQ (not an objective)")
    m.note("airport1", 3, 13, "player airport (FTR/BMB/BCO)").note("base1", 5, 13, "player base")
    m.note("gap_s", 8, 7, "Kite Hill south gap (main road)").note("gap_w", 5, 4, "west gap").note("gap_e", 11, 4, "east gap")
    m.note("bridges", 3, 9, "west bridge (3,9), south bridge (8,9), east bridge (12,9)")
    m.note("minicannons", 6, 5, "W (6,5) covers the west gap, E (10,3) the east gap, S (9,6) the south gap")
    m.note("crystals", 14, 4, "Black Crystals (14,4) and (14,7) beside the ports")
    m.note("black_cannon", 19, 11, "Black Cannon facing up, covers the basin's south shore and the river mouth; the south-east freight yard (16..21, 10..15) is Black Hole's")
    m.note("deathray", 2, 1, "Deathray on the top edge (x1..3,y0..2), covers the west road; far from the player's start")
    m.note("isle", 20, 2, "grain isle: neutral city on a sea-only islet, beach (19..20,4)").note("ports", 14, 2, "ports (14,2) and (14,8), sea beside each at (15,2) and (15,8)")
    return m
