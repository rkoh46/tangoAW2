"""M11 The Treasure Train (Act III): Livia's four APCs run from the harbour along the long road east to the Senate's relay camp, across a wide march; a forest, the ford and a ruin and two marauder camps stand between."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *


def build():
    m = Canvas("es11", 40, 22)
    m.header(armies=3, colours=(OS, YC, GE), team=[1, 2, 2], objective=[1],
             comment="M11 The Treasure Train (escort; province: the Marrow Road, a Yellow Comet borderland): the four APCs apc1..apc4 start at the harbour (6,9)..(6,12) and must reach the relay camp rectangle (35,9)-(38,11) at the east end; "
                     "the camp's city c (37,10) is neutral on the map and the mission gives it to the player. The road winds east across the Pinewood (x10..19), a hamlet, the Marrow river at ONE bridge (the ford, (23,9)) "
                     "and a ruin (x27..33). Lash's HQ 2 (37,3) is the NE camp, Flak's HQ 3 (37,18) the SE camp. "
                     "Threat/answer: marauder Tanks and Md Tanks at the ford -> own Md Tanks/Tanks and Artillery hit them from the west bank (the river keeps vehicles off), Missiles are not needed; "
                     "Rockets and Artillery covering the ford and ruin (hold) -> Recon sees them, Tanks rush inside their minimum range, Artillery duels from the forest cover; "
                     "Infantry and Mechs wade the river (foot units cross it) to flank the ford; Anti-Air only for the AA tank the player owns (no enemy aircraft on this map). "
                     "Player start: APC4 RECON3 TANK3 MDT2 ART2 MECH2 INF2 AA1 (19 units), funds 3000, one base. Lash: INF3 TANK3 RECON2 ART1 MECH2 (11); Flak: MDT2 TANK2 INF3 ROCK1 (8). "
                     "THE PIPELINE (the Marrow Pipe, y14, x11..20): runs beside the road's Pinewood stretch and shields the convoy's south flank; the south track (15,13)-(15,16)-(24,17) leaves the road through it at the SEAM (15,14): "
                     "an escort unit (Tank, Recon, Md Tank, Mech, any direct fire) attacks the seam from (15,13) and the track opens: a SIDE ROUTE to a second, south bridge over the Marrow (25,17) and on by the south road (26,17)-(30,17)-(30,15)-(35,15) to the camp, "
                     "avoiding the ford holders but passing Flak's camp; the main road is never blocked. "
                     "SANDSTORM: indirect guns lose a cell (Artillery 2-3 becomes 2-2, Rockets 3-5 becomes 3-4): the player's answers are direct fire (Tanks, Md Tanks, Recons, Mechs) that close with the holders; the single AA only has to watch the camp. "
                     "OASIS: pond (30,19) and ruined walls (28..32, 8..13). "
                     "Marauders advance; Flak's Md Tanks (24,8),(24,10), Rockets (26,11) and Lash's Artillery (25,7) hold the ford.")
    # ---- the western harbour: sea, a shoaled coast with bays, two ports ----
    coast = [3, 3, 3, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 3, 3, 3, 3, 3, 3]
    for y, x1 in enumerate(coast):
        m.rect("~", 0, y, x1, y)
    # ---- ridges and bluffs: the hills north and south of the march ----
    for cx, cy, n, s in ((11, 1, 12, 1), (18, 2, 10, 2), (4, 0, 4, 3), (26, 2, 8, 4), (30, 5, 6, 5), (14, 20, 12, 6), (21, 19, 9, 7), (30, 20, 8, 8), (10, 18, 5, 9), (33, 14, 6, 10)):
        m.cluster("^", cx, cy, n, seed=s)
    # ---- the Pinewood and hedgerow woods ----
    for cx, cy, n, s in ((12, 9, 14, 20), (16, 12, 14, 21), (14, 6, 10, 22), (18, 8, 8, 23), (11, 13, 8, 24), (8, 3, 6, 25), (7, 17, 6, 26),
                         (22, 15, 7, 27), (21, 4, 6, 28), (29, 10, 3, 29), (32, 8, 4, 30), (31, 15, 4, 31), (26, 18, 5, 32), (35, 6, 4, 33), (35, 14, 4, 34), (4, 12, 5, 35), (9, 20, 6, 36), (26, 6, 6, 37), (39, 10, 5, 38), (24, 20, 5, 39), (5, 5, 5, 40), (28, 16, 5, 41), (33, 2, 5, 42)):
        m.cluster("f", cx, cy, n, seed=s)
    # ---- the Marrow river: a spring on the top edge, falling east in steps, the mouth off the bottom edge ----
    m.river([(21, 0), (21, 6), (23, 6), (23, 14), (25, 14), (25, 21)])
    # ---- the ruin: broken walls of wood and stone around a roofless hall ----
    for x, y in ((28, 8), (29, 8), (31, 8), (32, 9), (32, 11), (31, 13), (29, 13), (28, 12), (27, 10), (30, 9), (30, 12)):
        m.put("f" if (x + y) % 2 else "^", x, y)
    # ---- the road: a long bend across the march ----
    m.road([(7, 11), (10, 11), (10, 13), (15, 13), (15, 10), (19, 10), (19, 8), (21, 8), (21, 10), (28, 10), (28, 13), (31, 13), (31, 10), (35, 10)])
    m.road([(8, 9), (8, 5), (13, 5), (13, 7), (19, 7), (19, 8)])                # the hamlet road north of the Pinewood
    m.road([(35, 10), (36, 10)])
    m.road([(35, 10), (35, 6), (37, 6), (37, 4)]).road([(35, 10), (35, 15), (37, 15), (37, 17)])   # the branch roads to the two camps
    m.bridge(23, 10)                                                          # the ford
    # ---- the side route: a south track through the Marrow Pipe's seam, a south bridge, a road to the camp road ----
    m.road([(15, 13), (15, 17), (24, 17)])
    m.bridge(25, 17)
    m.road([(26, 17), (30, 17), (30, 15), (35, 15)])
    m.pipe([(11, 14), (14, 14)]).pipe([(16, 14), (20, 14)])
    m.put("Z", 15, 14)
    m.puts("~", [(30, 19), (31, 19), (30, 20)]).puts(",", [(29, 19), (32, 19), (29, 20), (31, 20), (30, 18), (31, 18)])
    # ---- properties ----
    m.put("1", 7, 9).put("B", 8, 11).put("C", 8, 7).put("C", 8, 14).put("C", 6, 16)
    m.put("c", 12, 5).put("c", 17, 7).put("c", 16, 16).put("c", 20, 12).put("c", 21, 8)      # hamlets along the road
    m.put("c", 30, 11)                                                          # the ruin's hall
    m.put("c", 37, 10)                                                          # the relay camp (the mission hands it to the player)
    m.put("2", 37, 3).put("B", 35, 5).put("C", 36, 7).put("C", 33, 4)
    m.put("3", 37, 18).put("B", 35, 16).put("C", 36, 14).put("C", 33, 18)
    m.beach(0, 0, 4, 21)
    m.put("P", 3, 8).put("P", 3, 15)
    # ---- units ----
    for i, (x, y) in enumerate(((6, 10), (6, 11), (6, 12), (7, 12))):
        m.unit(1, APC, x, y, name=f"apc{i + 1}")
    m.spread(1, {RECON: 3}, (9, 7, 14, 15), seed=1, gap=2)
    m.spread(1, {TANK: 3, MDT: 2, ART: 2}, (5, 6, 12, 16), seed=2, gap=1)
    m.spread(1, {MECH: 2, INF: 2, AA: 1}, (5, 6, 12, 16), seed=3, gap=1)
    # Flak and Lash hold the ford; the rest advance from the camps and the ruin
    m.unit(3, MDT, 24, 9, hold=True).unit(3, MDT, 24, 11, hold=True).unit(3, ROCK, 26, 12, hold=True).unit(2, ART, 25, 8, hold=True)
    m.spread(2, {INF: 3, TANK: 2, MECH: 1}, (28, 2, 38, 8), seed=4, gap=1)
    m.spread(2, {RECON: 2, TANK: 1, MECH: 1}, (26, 7, 34, 14), seed=5, gap=1)
    m.spread(3, {INF: 3, TANK: 2}, (28, 14, 38, 20), seed=6, gap=1)
    m.note("apc1", 6, 10, "convoy APC 1 (also apc2 (6,11), apc3 (6,12), apc4 (7,12)); must arrive in `camp`")
    m.note("hq1", 7, 9, "player HQ at the harbour, base (8,11), ports (3,8) and (3,15)")
    m.note("ford", 23, 10, "the only bridge over the river x23 (vehicles cross only here; foot units can wade)")
    m.note("camp_nw", 35, 9, "camp rectangle top-left").note("camp_se", 38, 11, "camp rectangle bottom-right; city c (37,10) neutral, give it to the player at start")
    m.note("ruin", 30, 11, "ruin: plain with a ring of rubble x27..32, y8..13 round a roofless hall (neutral city (30,11))")
    m.note("forest", 12, 9, "the Pinewood x10..19, y5..14 around the road")
    m.note("hq2", 37, 3, "Lash's HQ (NE camp), branch road (35,6)-(37,4)").note("hq3", 37, 18, "Flak's HQ (SE camp), branch road (35,15)-(37,17)")
    m.note("road", 7, 11, "the road from (7,11) bends through the Pinewood, the hamlet (21,8), the ford (23,10) and the ruin to the camp (35,10)")
    m.note("ford_holders", 24, 9, "enemy holds: Flak MDT (24,9),(24,11), Flak ROCK (26,12), Lash ART (25,8)")
    m.desertify(keep=0.45, rocks=11, size=6, seed=11)                      # (the desert look: sparse scrub, rock outcrops, canyon walls)
    return m
