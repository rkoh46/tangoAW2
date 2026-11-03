"""Gauntlet 02, stage two: Asuka's Keep (the Gauntlet mode's second map, docs/dev/gauntlet.md), a brand-new 30 x 22 map the battle moves to in place when Rachel's line has fallen (`Action::NextStage`: the player's survivors land
on this map's army-1 cells, the deployment of the map). Asuka (Black Hole, army 2), a fresh full-strength army, holds a Black Hole fortress on high ground in the north-east; the player (Emerald Sun, army 1, on Orange Star's colour) lands in the south-west.
Black Hole's inventions are all here (the first map has none): two Black Cannons on the plateau's south wall cover the south gate and the two east bridges, two minicannons flank the gate, two on the west rim cover the moor, a Laser in the moor's heart
(row 9 and column 11), three Black Crystals heal her troops on the plateau. Nobody starts in a firing zone and the landing is outside every one (IV02).

Design (docs/dev/map-design.md): a river, the Styx (y 12..13, four bridges), runs the map's width between the landing and the keep: the west bridge (4,12) and the middle bridge (14,13) lead to the moor and the west pass (14..15,5), guarded by the Laser and
the rim's minicannons; the two east bridges (21,13) and (26,13) lead straight to the south gate (22,9..10) under the Black Cannons' fire. Com Towers (12,5) and (9,16). The player's survivors choose between a slow, long way round the moor and a fast road under the guns.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs, clear_fire_lines

W, H = 30, 22
HQS = {"1": (3, 18), "2": (22, 5)}


def build():
    m = Canvas("gauntlet_02b", W, H, campaign="gauntlet")
    S = lambda x, y: snap(m, x, y)
    # --- the keep: a massif with a plateau, a west pass (14..15,5) and a south gate (22,9..10)
    m.rect("^", 14, 1, 28, 10); m.rect(".", 16, 2, 26, 8)
    for x, y in ((14, 5), (15, 5), (22, 9), (22, 10)):
        m.put(".", x, y)
    for x, y in ((14, 2), (28, 10), (28, 1), (14, 10), (27, 10), (18, 1), (23, 1), (26, 1)):
        m.put("f" if (x, y) != (28, 10) else ".", x, y)
    m.cluster("f", 19, 7, 5, seed=3); m.cluster("f", 24, 4, 4, seed=4)
    # --- the Styx, with four bridges
    m.river([(0, 12), (10, 12), (10, 13), (29, 13)])
    for x, y in ((4, 12), (14, 13), (21, 13), (26, 13)):
        m.put("=", x, y)
    m.blob("~", 6, 4, 2, 1, seed=5, wobble=0.3)                   # a tarn on the moor
    # --- the moor and the landing's relief
    for i, pts in enumerate([[(1, 8), (6, 9)], [(1, 2), (5, 1)], [(8, 6), (10, 8)], [(12, 10), (13, 11)]]):
        belt(m, "^", pts, width=1, seed=10 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(4, 6, 3), (9, 3, 3), (12, 8, 2), (24, 16, 3), (18, 18, 3), (27, 19, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=20 + i)
    belt(m, "^", [(15, 17), (19, 16)], width=1, seed=30, p=0.9); belt(m, "^", [(22, 20), (27, 21)], width=1, seed=31, p=0.9); belt(m, "f", [(1, 14), (5, 15)], width=1, seed=32)
    m.header(armies=2, colours=(OS, BH), objective=[1], blackhole=True, zones=[(1, 0, 13, 9, 21)], comment=(
        "Gauntlet 02 stage two, Asuka's Keep (normal look, 30 x 22): the player's survivors (Emerald Sun, army 1 on Orange Star's colour, HQ 1 (3,18), the south-west landing) against Asuka (Black Hole, army 2, HQ 2 (22,5), the plateau). "
        "Black Cannons (19,9) and (25,9), minicannons S (21,10) (23,10) and W (15,3) (15,7), Laser (11,9), Black Crystals (18,5) (24,3) (25,7). The Styx (y 12..13) with bridges (4,12) (14,13) (21,13) (26,13); pass west (14..15,5), gate south (22,9..10). Com Towers (12,5) and (9,16)."))
    m.put("1", *HQS["1"]).put("2", *HQS["2"]).put("t", 12, 5).put("t", 9, 16)
    # --- inventions (Black Hole's): the cannons in the wall's south face, minicannons at the gate and on the west rim, the Laser on the moor, crystals on the plateau
    for x, y in ((21, 10), (23, 10), (15, 3), (15, 7)):
        m.put(".", x, y)
    m.stamp("v", 19, 9).stamp("v", 25, 9).put("S", 21, 10).put("S", 23, 10).put("W", 15, 3).put("W", 15, 7).stamp("L", 11, 9)
    m.put("X", 18, 5).put("X", 24, 3).put("X", 25, 7)
    # --- roads
    route(m, [S(3, 17), (4, 14), (4, 13), (4, 12, "="), (4, 11), S(6, 7), S(10, 5), (12, 5), (13, 5), (14, 5), (15, 5), (16, 5), S(20, 5), S(22, 5)], seed=1, wander=0.5)
    route(m, [S(7, 17), (14, 15), (14, 14), (14, 13, "="), (14, 12), (14, 11), S(13, 8), S(12, 6)], seed=2, wander=0.5)
    route(m, [S(7, 19), S(15, 19), (21, 16), (21, 15), (21, 14), (21, 13, "="), (21, 12), (21, 11), (22, 11), (22, 10), (22, 9), S(22, 7), S(22, 5)], seed=3, wander=0.5)
    route(m, [S(21, 16), S(26, 16), (26, 14), (26, 13, "="), (26, 12), (26, 11), S(27, 10)], seed=4, wander=0.4)
    route(m, [S(16, 5), S(20, 3), S(24, 3), S(26, 6), S(22, 7)], seed=5, wander=0.3)
    thin_roads(m); fix_rungs(m)
    for args in [(3, 18, "BBC"), (7, 17, "BC"), (2, 15, "C"), (6, 20, "C"), (9, 18, "C"),
                 (22, 5, "BBBC"), (18, 4, "BC"), (25, 5, "BA"), (19, 7, "AC"), (24, 7, "BC"), (21, 3, "C"), (26, 3, "C"),
                 (8, 8, "c"), (3, 4, "c"), (9, 4, "c"), (13, 15, "c"), (19, 16, "cb"), (24, 15, "c"), (28, 17, "ca"), (12, 19, "c"), (22, 19, "c"), (27, 20, "c"), (16, 12, "c"), (1, 10, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 5)
    m.tidy()
    av = "~r=-^IZ#X12QBCPTbcptSNWELvn"
    # the player's landing (their cells deploy the survivors) and Asuka's fresh army: the plateau and the moor
    m.spread(1, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 14, 8, 21), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 3, BCO: 2}, (1, 14, 8, 21), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 4, MECH: 3, MDT: 4, NEO: 4, TANK: 3, ART: 3, ROCK: 2, MIS: 2, AA: 2, RECON: 1}, (16, 2, 26, 8), seed=3, gap=0, avoid=av)
    m.spread(2, {FTR: 2, BMB: 2, BCO: 1}, (16, 2, 26, 8), seed=4, gap=1, avoid=av)
    n = clear_fire_lines(m)
    m.note("hq1", *HQS["1"], "the player's HQ (the landing)"); m.note("hq2", *HQS["2"], "Asuka's HQ (the objective; held: the Win trigger ends the battle)")
    from aw2.esmaplib import prune_road_stubs
    prune_road_stubs(m)          # (lint RD03: a road that leads nowhere goes: the only change to the map's layout since it was drawn)
    return m
