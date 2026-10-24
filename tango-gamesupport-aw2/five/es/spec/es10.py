"""M10 The Quiet Pass (Act III): Comet Pass in the fog, a Yellow Comet province. Three winding roads and a goat track climb the massif to Kanbei's summit; Sonja watches from the east ridge."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es10", 34, 26)
    m.header(armies=3, colours=(OS, YC, YC), team=[1, 2, 2], objective=[1],
             comment="M10 The Quiet Pass (FOG; province: Comet Pass, Yellow Comet's mountain march): the Aurean legion lands on the south plain, crosses the Quiet river at three bridges, "
                     "climbs a pass road (west x7, centre x16, east x28) or the goat track (foot only, far west x1..3) through the massif (y5..13) and takes Kanbei's summit HQ '2' (16,2); "
                     "Sonja's HQ '3' (31,3) sits in a pocket of the east ridge, off the east pass road. "
                     "Threat/answer: ambushes at the pass tops in the fog -> Recons (vision) and the B Copter/T Copter scout ahead, the APC and Infantry hold the bridge heads; "
                     "Tanks/Md Tanks at the pass tops (vehicles must use the roads) -> Mechs and Infantry on the goat track and over the mountains flank them, MDT and ART on the road below; "
                     "Artillery + Rockets on the summit (hold) -> Recon sight, B Copter, Infantry/Mech over the mountains out of the roads' line; Sonja's Copter -> own AA. "
                     "Player start: INF4 MECH3 TANK2 MDT2 RECON3 ART2 BCO1 TCO1 AA1 APC1 (19 units), 1 base, funds 4000. "
                     "Kanbei: INF4 MECH2 TANK3 MDT2 ART2 ROCK1 AA1 (15); MECH x2, ART x2 and ROCK hold on the summit. Sonja: INF2 RECON2 TANK2 BCO1 (7), INF hold the pocket. "
                     "Enemy about 1.2x the player's value.")
    # ---- the massif (y 5..13): blobs of mountain joined into a range with ragged edges ----
    for cx, cy, rx, ry, s in ((3, 9, 3, 5, 1), (10, 8, 3, 4, 2), (11, 12, 3, 2, 3), (20, 8, 4, 4, 4), (21, 12, 3, 2, 5), (30, 9, 3, 5, 6), (6, 12, 2, 2, 7), (15, 7, 2, 2, 8), (25, 7, 2, 3, 9), (13, 9, 2, 2, 14), (29, 13, 3, 2, 15)):
        m.blob("^", cx, cy, rx, ry, seed=s, wobble=0.3)
    # valleys inside the range: a meadow, a wooded dell
    m.blob(".", 12, 10, 1, 1, seed=16, wobble=0.1); m.blob("f", 4, 8, 1, 2, seed=17, only="^"); m.blob(".", 22, 9, 2, 1, seed=18, wobble=0.2); m.blob("f", 28, 8, 1, 2, seed=19, only="^")
    # the summit crown and the east ridge (Sonja's pocket)
    m.blob("^", 16, 1, 6, 2, seed=10, wobble=0.25); m.blob(".", 16, 2, 4, 1, seed=11, wobble=0.1)
    m.blob("^", 31, 3, 4, 4, seed=12, wobble=0.2); m.blob(".", 31, 3, 2, 2, seed=13, wobble=0.1)
    m.rect(".", 26, 3, 29, 3, only="^")
    # ---- the Quiet river: a spring in the west hills, falling east in steps, the mouth off the map edge ----
    m.cluster("^", 0, 14, 5, seed=20)
    m.river([(0, 15), (10, 15), (10, 17), (24, 17), (24, 19), (33, 19)])
    bw, bc, be = (7, 15), (16, 17), (28, 19)
    # ---- woods around the pass mouths (ambush ground), hedgerows on the plain ----
    for cx, cy, n, s in ((5, 14, 7, 30), (11, 13, 5, 31), (13, 16, 5, 32), (20, 14, 6, 33), (25, 15, 6, 34), (31, 14, 5, 35), (3, 4, 6, 36), (10, 3, 5, 37),
                         (22, 3, 5, 38), (6, 21, 6, 39), (21, 21, 6, 40), (27, 23, 5, 41), (11, 24, 4, 42), (1, 19, 4, 43), (31, 22, 5, 44), (19, 18, 3, 45), (4, 24, 3, 46)):
        m.cluster("f", cx, cy, n, seed=s)
    # ---- roads ----
    m.road([(7, 14), (7, 12), (9, 12), (9, 8), (7, 8), (7, 5), (7, 4), (13, 4)])             # west pass (up from the bridge at (7,15))
    m.road([(7, 16), (7, 21), (4, 21)])
    m.road([(16, 16), (16, 13), (15, 13), (15, 9), (17, 9), (17, 5), (16, 4)])               # centre pass
    m.road([(16, 18), (16, 22)])
    m.road([(28, 18), (28, 22), (22, 22)])
    m.road([(28, 18), (28, 13), (26, 13), (26, 8), (24, 8), (24, 5), (24, 4), (19, 4)])      # east pass
    m.road([(24, 5), (27, 5), (27, 3), (29, 3)])                                              # the spur to Sonja's pocket
    m.road([(4, 21), (22, 22)]) if False else m.road([(7, 21), (16, 21), (16, 22)])
    m.put("=", *bw).put("=", *bc).put("=", *be)
    # the goat track: a foot-only strip of mountain far west, with a plain landing at each end
    m.road([(2, 17), (2, 16)]) if False else None
    for x, y in ((1, 14), (1, 13), (2, 13), (2, 12), (2, 11), (2, 10), (1, 10), (1, 9), (2, 8), (2, 7), (2, 6), (3, 6), (3, 5)):
        m.put("^", x, y)
    m.rect(".", 3, 3, 5, 4).put(".", 1, 14).put(".", 0, 14)
    # ---- properties ----
    m.put("1", 16, 23).put("B", 13, 22).put("C", 19, 22).put("C", 9, 20).put("C", 24, 21).put("c", 4, 20).put("c", 12, 18).put("c", 30, 17)
    m.put("2", 16, 2).put("B", 13, 3).put("C", 19, 3).put("C", 9, 4).put("C", 22, 5).put("c", 11, 8).put("c", 14, 7).put("c", 26, 11)
    m.put("3", 31, 3).put("C", 29, 5)
    # make sure the summit and the pocket have ground beside them
    m.rect(".", 14, 2, 18, 3, only="^").put("2", 16, 2).put("B", 13, 3).put("C", 19, 3)
    m.rect(".", 30, 2, 32, 4, only="^").put("3", 31, 3)
    # ---- units ----
    H = dict(hold=True)
    # the player: the column at the bridge heads, the guns behind, scouts out in front
    m.unit(1, APC, 16, 22)
    m.spread(1, {INF: 4, MECH: 3}, (6, 18, 26, 24), seed=1, gap=1)
    m.spread(1, {TANK: 2, MDT: 2, ART: 2, AA: 1}, (8, 19, 24, 25), seed=2, gap=1)
    m.spread(1, {RECON: 3}, (6, 18, 28, 21), seed=3, gap=2)
    m.spread(1, {BCO: 1, TCO: 1}, (12, 22, 20, 25), seed=4, gap=1)
    # Kanbei: the summit's garrison (hold), the three passes' ambushes (advance)
    m.units(2, MECH, [(15, 3), (17, 3)], **H); m.units(2, ART, [(14, 2), (18, 2)], **H); m.unit(2, ROCK, 16, 4, **H)
    m.unit(2, AA, 19, 4)
    m.units(2, INF, [(8, 4), (9, 5)]); m.unit(2, TANK, 11, 4)
    m.units(2, INF, [(23, 5), (24, 7)]); m.unit(2, MDT, 22, 4)
    m.unit(2, TANK, 17, 7); m.unit(2, TANK, 15, 10); m.unit(2, MDT, 18, 4)
    # Sonja
    m.units(3, INF, [(31, 2), (32, 4)], **H)
    m.units(3, TANK, [(30, 4), (29, 3)]); m.unit(3, RECON, 31, 5); m.unit(3, RECON, 27, 5); m.unit(3, BCO, 30, 2)
    m.note("hq1", 16, 23, "player HQ (south)").note("base1", 13, 22, "player base")
    m.note("hq2", 16, 2, "Kanbei's summit HQ: the objective").note("hq3", 31, 3, "Sonja's HQ in the east-ridge pocket")
    m.note("gorge", 0, 15, "river falling east: (0..10,15), (10..24,17), (24..33,19); bridges at (7,15) west, (16,17) centre, (28,19) east")
    m.note("pass_w", 7, 10, "west pass road (bridge (7,15) -> (7,4)), mountains either side").note("pass_c", 15, 9, "centre pass road (bridge (16,17) -> (16,4))")
    m.note("pass_e", 26, 9, "east pass road (bridge (28,19) -> (24,4)), with a spur east to Sonja's pocket at (29,3)")
    m.note("goat_start", 1, 15, "goat track foot start (plain landing north of the gorge)").note("goat_end", 3, 4, "goat track top: plain landing in the north forest, west of Kanbei's ground")
    m.note("scene_day4", 17, 5, "Kanbei's honour scene (day 4): the summit road's top, by the central pass")
    m.note("sonja_ridge", 31, 3, "east ridge mountains around Sonja's pocket x30..32, y2..4")
    return m
