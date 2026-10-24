"""M10 The Quiet Pass (Act III): Comet Pass in the fog. Three roads and a goat track climb the massif to Kanbei's summit; Sonja watches from the east ridge."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es10", 20, 16)
    m.header(armies=3, colours=(OS, YC, YC), team=[1, 2, 2], objective=[1],
             comment="M10 The Quiet Pass (FOG): cross the gorge (y 11) at the three bridges, climb a pass road (x4 west, x10 centre, x14 east) or the goat track (foot only, x1..2) "
                     "and take Kanbei's summit HQ '2' (10,1); Sonja's HQ '3' (18,3) sits in a pocket of the east ridge. "
                     "Threat/answer: ambushes at the pass mouths in the fog -> Recons (vision 5?) and the B Copter/T Copter scout ahead, the APC and Infantry hold the bridge heads; "
                     "Tanks/Md Tanks at the pass tops (vehicles must use the roads) -> Mechs and Infantry on the goat track flank them, MDT and ART on the road below; "
                     "Artillery + Rockets on the summit (hold) -> Recon sight, B Copter, Infantry/Mech over the mountains out of the roads' line; Sonja's Copter -> own AA. "
                     "Player start: INF4 MECH3 TANK2 MDT2 RECON3 ART2 BCO1 TCO1 AA1 APC1 (19 units), 1 base, funds 4000. "
                     "Kanbei: INF4 MECH2 TANK3 MDT2 ART2 ROCK1 AA1 (15); MECH x2, ART x2 and ROCK hold on the summit. Sonja: INF2 RECON2 TANK2 BCO1 (7), INF hold the pocket. "
                     "Enemy about 1.2x the player's value.")
    # the massif (mountains y 5..9) with three road passes; mountain shoulders on the top edge and the summit crown
    m.rect("^", 0, 5, 19, 9)
    m.rect("^", 0, 0, 19, 0)
    m.rect("^", 6, 1, 7, 1).rect("^", 12, 1, 13, 1).rect("^", 8, 0, 11, 0)
    # the gorge: a river from edge to edge, three bridges at the road feet
    m.river([(0, 11), (19, 11)])
    # forests around the pass mouths, north and south (ambush ground), and rocky shoulders
    m.rect("f", 0, 3, 2, 4).rect("f", 6, 3, 8, 4).rect("f", 11, 2, 13, 4).rect("f", 3, 3, 5, 4)
    m.rect("f", 2, 10, 3, 10).rect("f", 5, 10, 8, 10).rect("f", 11, 10, 13, 10).rect("f", 15, 10, 17, 10)
    m.scatter("f", (0, 12, 19, 15), 0.10, seed=4)
    # the east ridge: Sonja's pocket
    m.rect("^", 15, 1, 19, 5)
    m.rect(".", 16, 2, 18, 4)
    m.rect("^", 15, 6, 19, 6)
    # roads: west pass x4, centre pass x10, east pass x14, joined at the top
    m.road([(4, 13), (4, 4)]).road([(4, 4), (8, 4)])
    m.road([(10, 13), (10, 2)])
    m.road([(14, 13), (14, 3)]).road([(14, 4), (11, 4)]).road([(14, 3), (16, 3)])
    m.road([(4, 13), (14, 13)])
    m.bridge(4, 11).bridge(10, 11).bridge(14, 11)
    # the goat track: foot-only strip of mountain on the far west, a plain landing at each end
    m.puts(".", [(1, 10), (1, 4)])
    m.rect("f", 0, 10, 0, 10)
    # properties
    m.put("1", 10, 14).put("B", 8, 14).put("C", 12, 14).put("C", 6, 13)
    m.put("c", 3, 12).put("c", 16, 12).put("c", 11, 10)
    m.put("2", 10, 1).put("B", 8, 2).put("C", 12, 2).put("C", 5, 2)
    m.put("3", 17, 3).put("C", 16, 2)
    # make sure the summit's neighbours are ground
    m.rect(".", 9, 1, 11, 1, only="^").put("2", 10, 1)
    m.put(".", 9, 2).put(".", 10, 2).put(".", 11, 2)

    taken = set()

    def spot(cx, cy, n, lo, hi, kinds=".fR"):
        out = []
        for r in range(0, 10):
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
        raise RuntimeError("no room")

    def put(army, kind, cx, cy, n=1, lo=(0, 0), hi=(99, 99), kinds=".fR", **kw):
        for x, y in spot(cx, cy, n, lo, hi, kinds):
            m.unit(army, kind, x, y, **kw)

    S = dict(lo=(0, 12), hi=(19, 15))
    put(1, APC, 10, 13, **S); put(1, INF, 9, 13, 4, **S); put(1, MECH, 11, 13, 3, **S)
    put(1, TANK, 7, 12, 2, **S); put(1, MDT, 13, 13, 2, **S); put(1, RECON, 10, 12, 3, **S)
    put(1, ART, 9, 15, 2, **S); put(1, AA, 11, 15, **S); put(1, BCO, 8, 15, **S); put(1, TCO, 12, 15, **S)
    # Kanbei: summit garrison (hold), the three passes' ambushes (advance)
    put(2, MECH, 9, 2, 2, lo=(8, 1), hi=(12, 3), hold=True)
    put(2, ART, 8, 3, 1, lo=(7, 2), hi=(9, 3), hold=True)
    put(2, ROCK, 10, 3, 1, lo=(9, 3), hi=(11, 4), hold=True); put(2, AA, 11, 3, 1, lo=(10, 2), hi=(12, 4))
    put(2, INF, 4, 3, 2, lo=(0, 2), hi=(8, 4)); put(2, INF, 14, 4, 2, lo=(11, 2), hi=(14, 4))
    put(2, TANK, 4, 4, 1, lo=(3, 3), hi=(6, 4)); put(2, TANK, 9, 4, 1, lo=(8, 3), hi=(11, 4))
    put(2, MDT, 12, 3, 1, lo=(11, 2), hi=(14, 4))
    # Sonja
    put(3, INF, 17, 3, 2, lo=(16, 2), hi=(18, 4), hold=True)
    put(3, TANK, 16, 3, 2, lo=(16, 2), hi=(18, 4)); put(3, RECON, 18, 2, 1, lo=(16, 2), hi=(18, 4)); put(3, BCO, 18, 4, 1, lo=(16, 2), hi=(18, 4))

    m.note("hq1", 10, 14, "player HQ (south)").note("base1", 8, 14, "player base")
    m.note("hq2", 10, 1, "Kanbei's summit HQ: the objective").note("hq3", 17, 3, "Sonja's HQ in the east-ridge pocket")
    m.note("gorge", 0, 11, "river along y 11 (x 0..19), bridges at (4,11) west, (10,11) centre, (14,11) east")
    m.note("pass_w", 4, 8, "west pass road x4 (y 12..4), mountains either side").note("pass_c", 9, 8, "centre pass road x10 ").note("pass_e", 14, 8, "east pass road x14, with a spur east to Sonja's pocket at (16,3)")
    m.note("goat_start", 1, 10, "goat track foot start (plain landing north of the gorge, bank (0..1,10))").note("goat_end", 1, 4, "goat track top: plain landing in the north forest, west of Kanbei's ground")
    m.note("scene_day4", 10, 4, "Kanbei's honour scene (day 4): the summit road's top, by the central pass")
    m.note("sonja_ridge", 15, 3, "east ridge mountains x15..19, y1..6; Sonja's pocket x16..18, y2..4")
    return m
