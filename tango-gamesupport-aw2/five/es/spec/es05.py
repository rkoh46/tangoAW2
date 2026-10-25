"""M5 Dust and Wheels: the Comet Marches. Cassius's cavalry rides east out of the Orange Star border town of Dunmere across a winding river (the Sable) over three bridges; beyond them lie
Yellow Comet's border posts: Highwatch (north), Crossways (middle) and Lowmere (south), then the road on to Fort Amberlea, the Comet HQ."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

POSTS = [(27, 5), (27, 12), (27, 21)]


def build():
    m = Canvas("es05", 42, 24)
    road = lambda pts: m.line("R", pts, over=".fR")
    m.header(armies=2, colours=(OS, YC), objective=[1], comment=(
        "M5 Dust and Wheels (the Comet Marches): own all three signal posts (post1 Highwatch, post2 Crossways, post3 Lowmere) by the end of day 9; the bridges are blown on day 10. "
        "Start forces: player RECON3 TANK3 MDT2 APC2 MECH3 AA2 (15 units), 1 base, funds 3000; "
        "Yellow Comet INF4 MECH2 TANK2 RECON1 ART2 ROCK1 BCO2 TCO1 AA1 (16 units), 2 bases + 1 airport. "
        "Threat -> answer: Copters (BCO/TCO) -> the player's 2 AA and Tanks/Recon; ART + ROCK shelling the bridges -> no player ART at all, the answer is speed "
        "(Recons and Tanks cross first and reach the guns); enemy AA -> Tanks/Md Tanks (Recon avoids it). "
        "THE PIPELINE (the Comet Pipe, x25, y0..23): a pipe wall between the Sable and the posts with two road gates (north (25,4)-(25,5), south (25,20)-(25,21)) and ONE seam (25,12) on the Crossways road: "
        "attack the seam with any direct-fire unit from (24,12) (Tank, Recon, Md Tank, Mech) and the middle road opens, the shortcut from the middle bridge straight to Crossways (27,12) and the Comet Road. "
        "THE MIDDLE RUINS (x21..24, y8..14): grey cities (22,10) (24,10) (22,14) and the neutral missile SILO M (23,8), a foot soldier on it fires it (3 HP to everything within its blast); "
        "it is a few turns from the north bridge for the player and from Highwatch for Yellow Comet. "
        "SANDSTORM: indirect guns lose a cell (Artillery 2-3 becomes 2-2, Rockets 3-5 becomes 3-4, Missiles likewise), so the Comet guns cannot reach far; the player's answers are all DIRECT fire: "
        "Tanks and Md Tanks (vs Tanks, Mechs, guns), Recons (vs Infantry, guns, copters' escorts), Mechs (vs Tanks), the 2 AA (vs Copters), MDT on the seam. "
        "OASES: (4,19) and (36,19)."))
    # hills and woods first (the river and roads cut through them)
    for cx, cy, n, sd, ch in [(10, 2, 12, 1, "^"), (5, 20, 10, 2, "^"), (33, 8, 14, 3, "^"), (32, 18, 13, 4, "^"), (39, 3, 9, 5, "^"), (39, 21, 8, 6, "^"), (29, 1, 8, 20, "^"),
                              (8, 6, 12, 7, "f"), (14, 17, 16, 8, "f"), (14, 10, 7, 9, "f"), (5, 13, 6, 10, "f"), (2, 5, 6, 21, "f"),
                              (30, 10, 8, 11, "f"), (30, 15, 9, 12, "f"), (36, 12, 8, 13, "f"), (35, 3, 9, 14, "f"), (35, 21, 9, 15, "f"),
                              (25, 8, 6, 16, "f"), (25, 16, 7, 17, "f"), (18, 22, 6, 18, "f"), (13, 3, 6, 19, "f"), (21, 2, 7, 22, "f"), (23, 11, 5, 23, "f"), (20, 19, 5, 24, "f"),
                              (6, 17, 6, 25, "f"), (29, 22, 6, 26, "f"), (23, 6, 4, 27, "f")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # the Sable: spring at the north edge, mouth at the south edge, three bridges on straight stretches
    m.river([(16, 0), (16, 3), (17, 3), (17, 6), (19, 6), (19, 9), (20, 9), (20, 15), (22, 15), (22, 18), (23, 18), (23, 23)])
    b1, b2, b3 = (17, 5), (20, 12), (23, 21)
    for bx, by in (b1, b2, b3):
        m.put("=", bx, by)
    # the Comet Pipe: a wall between the river and the posts; two road gates, one seam on the middle road
    m.put("M", 23, 8)
    # properties
    m.put("1", 3, 12).put("B", 12, 11)
    m.puts("c", [(10, 3), (8, 16), (14, 20), (13, 10)])
    m.puts("c", POSTS)
    m.put("2", 38, 12).puts("B", [(35, 8), (35, 16)]).put("A", 36, 13)
    m.puts("C", [(32, 4), (33, 20), (31, 12), (39, 7)])
    # roads: the home hub, three bending legs to the bridges, the posts, the Comet Road
    road([(3, 12), (8, 12)])
    road([(8, 12), (8, 8), (10, 8), (10, 5), (b1[0] - 1, 5)])
    road([(10, 5), (10, 3)])
    road([(8, 12), (12, 12), (12, 13), (16, 13), (16, 12), (b2[0] - 1, 12)])
    road([(12, 12), (12, 11)])
    road([(8, 12), (8, 16), (11, 16), (11, 21), (b3[0] - 1, 21)])
    road([(11, 16), (14, 16), (14, 20)])
    road([(12, 11), (12, 10), (13, 10)])
    road([(b1[0] + 1, 5), (24, 5), (24, 4), (27, 4), (27, 5)])
    road([(b2[0] + 1, 12), (27, 12), (31, 12), (31, 13), (35, 13), (36, 13)])
    road([(b3[0] + 1, 21), (27, 21), (27, 20), (29, 20), (29, 19), (33, 19), (33, 20)])
    road([(31, 12), (31, 10), (35, 10), (35, 8)])
    road([(35, 13), (35, 16)])
    road([(35, 10), (37, 10), (37, 7), (39, 7)])
    road([(36, 13), (38, 13), (38, 12)])
    road([(27, 5), (29, 5), (29, 4), (32, 4)])
    road([(33, 19), (35, 19), (35, 16)])
    # the middle ruins: a road to the silo, rubble of a walled town
    road([(21, 12), (24, 12)])
    road([(23, 12), (23, 9)])
    m.puts("c", [(22, 10), (24, 10), (22, 14)])
    m.puts("^", [(21, 9), (22, 9), (24, 8), (21, 11), (24, 13), (23, 14), (21, 14)])
    m.puts(".", [(22, 8), (24, 9)])
    m.put("f", 21, 8)
    # the Comet Pipe at x25: caps at the ends of each run, the seam on the Crossways road
    m.pipe([(25, 0), (25, 3)]).pipe([(25, 6), (25, 11)]).pipe([(25, 13), (25, 19)]).pipe([(25, 22), (25, 23)])
    m.put("Z", 25, 12)
    # two oases (a pond, shoals, scrub)
    m.puts("~", [(4, 19), (5, 19), (4, 20)]).puts(",", [(3, 19), (6, 19), (3, 20), (5, 20), (4, 18), (5, 18), (4, 21)])
    m.puts("f", [(2, 18), (6, 18), (6, 21), (7, 19)])
    m.puts("~", [(36, 19), (37, 19), (36, 20)]).puts(",", [(35, 19), (38, 19), (35, 20), (37, 20), (36, 18), (37, 18), (36, 21)])
    m.puts("f", [(34, 18), (38, 18), (38, 21), (34, 21)])
    # player: the column has already left Dunmere and forms up on the road to the bridges (the HQ and the one base stay behind)
    m.spread(1, {MECH: 3}, (8, 6, 13, 18), seed=1, gap=1)
    m.spread(1, {RECON: 3, TANK: 3, MDT: 2, APC: 2, AA: 2}, (8, 6, 15, 18), seed=2, gap=1)
    # Yellow Comet's border guard: pickets at the posts, guns on the hills, copters at the airfield
    m.units(2, INF, [(26, 5), (28, 13), (26, 21)], hold=True)
    m.unit(2, INF, 26, 11, hold=True)
    m.units(2, MECH, [(28, 4), (28, 22)], hold=True)
    m.unit(2, TANK, 28, 10).unit(2, TANK, 29, 14)
    m.unit(2, RECON, 31, 11)
    m.units(2, ART, [(32, 11), (30, 17)], hold=True)
    m.unit(2, ROCK, 33, 14, hold=True)
    m.units(2, BCO, [(36, 15), (36, 9)])
    m.unit(2, TCO, 37, 11)
    m.unit(2, AA, 37, 13, hold=True)
    m.note("hq1", 3, 12, "player HQ (Dunmere, west)").note("hq2", 38, 12, "Yellow Comet HQ (Fort Amberlea, far east)")
    m.note("bridge1", b1[0], b1[1], "north bridge").note("bridge2", b2[0], b2[1], "middle bridge").note("bridge3", b3[0], b3[1], "south bridge")
    m.note("post1", 27, 5, "signal post Highwatch beyond the north bridge").note("post2", 27, 12, "signal post Crossways beyond the middle bridge").note("post3", 27, 21, "signal post Lowmere beyond the south bridge")
    m.note("base1", 12, 11, "player's only base: the forward depot at the Dunmere crossroads")
    m.note("river", 16, 0, "the Sable, spring at the north edge, mouth at the south edge (23, 23)")
    m.desertify(keep=0.6, rocks=14, size=6, seed=5)                      # (the desert look: sparse scrub, rock outcrops, canyon walls)
    return m
