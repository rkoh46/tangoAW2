"""BH2 M11 Cold Wire (Act III): Blue Moon's snowbound border, strung with the Allies' pipe wire. Jugger (forced) against Grit. Snow look, snow weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the Allies' supply wire runs across the border as pipelines. A west wall (x 12, from the north edge to the cliffs at y 21) shuts Black Hole's valley in the west;
an east wall (x 29, from the cliffs at y 8 to the south edge) shuts Grit's ground in the east; a short crossbar (y 15) splits the middle box in two but for a gap beside the cliffs. The way round is the long
zig-zag: from the west valley south round the west wall's end, up the south half of the box, through the gap, then north round the east wall's end along the northern strip. The four seam gates (two in each wall)
are the short cuts, and a broken seam cuts the wire: Grit's guns lose the cover of the box.
- Lanes: the zig-zag, the seam gates, the crossbar's gap, the northern strip (the long open road).
- Where the fight happens: the box with the two Com Towers (20,10) and (20,21), the gap, and the gates in the east wall (29,12) (29,22).
- Properties: Black Hole's valley district (a village chain on the road to the south pass), the box's neutral villages, Grit's capital and a base district behind the east wall.
- Threats and answers: Grit's Artillery, Rockets and Missile-free guns (his indirect fire behind the wall) -> Black Hole's Md Tanks and Recons through the gates, its own Artillery and Rockets; Blue Moon fields no air, so neither army fields Anti-Air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 42, 30


def build():
    m = Canvas("bh2_11", W, H)
    # --- a frozen coast along the north and the south: ragged, with flat runs (the border's shore); the walls end in the sea
    rnd = random.Random("bh2_11/coast")
    T, B, t, b = {}, {}, 3, 27
    for x in range(W):
        if x % 4 == 0:
            t = max(2, min(5, t + rnd.choice([-1, 0, 1]))); b = max(25, min(28, b + rnd.choice([-1, 0, 1])))
        T[x], B[x] = t, b
    T[12], T[11], T[13] = 3, 3, 3
    for x in range(W):
        for y in range(0, T[x]):
            m.g[y][x] = "~"
        for y in range(B[x] + 1, H):
            m.g[y][x] = "~"
    C = lambda x, y: (x, max(T[x] + 1, min(B[x] - 1, y)))
    # --- relief: the cliffs that end the walls, ranges between the lanes, snow woods
    belt(m, "^", [(9, 21), (12, 22), (15, 21)], width=1, seed=1, gaps=[(10, 21)], p=1.0); belt(m, "^", [(27, 8), (29, 7), (32, 8)], width=1, seed=2, p=1.0)
    belt(m, "^", [(23, 14), (23, 16)], width=1, seed=3, p=1.0); belt(m, "^", [(3, 6), (8, 5)], width=1, seed=4); belt(m, "^", [(1, 24), (6, 26)], width=1, seed=5, gaps=[(4, 25)])
    belt(m, "^", [(15, 3), (20, 4), (25, 3)], width=1, seed=6, gaps=[(18, 3), (23, 3)]); belt(m, "^", [(33, 4), (38, 6)], width=1, seed=7); belt(m, "^", [(34, 25), (39, 27)], width=1, seed=8, gaps=[(36, 26)])
    belt(m, "^", [(15, 25), (21, 26), (26, 27)], width=1, seed=9, gaps=[(18, 26), (24, 27)]); belt(m, "^", [(34, 12), (38, 14)], width=1, seed=10, gaps=[(36, 13)])
    belt(m, "f", [(4, 15), (9, 17)], width=2, seed=11); belt(m, "f", [(16, 7), (22, 8)], width=1, seed=12); belt(m, "f", [(14, 18), (19, 19)], width=2, seed=13); belt(m, "f", [(24, 18), (27, 21)], width=1, seed=14)
    belt(m, "f", [(31, 17), (35, 19)], width=2, seed=15); belt(m, "f", [(31, 3), (36, 2)], width=1, seed=16); belt(m, "f", [(2, 10), (6, 9)], width=1, seed=17); belt(m, "f", [(16, 12), (19, 13)], width=1, seed=18)
    belt(m, "f", [(31, 23), (35, 24)], width=1, seed=19); belt(m, "f", [(4, 20), (6, 23)], width=1, seed=20)
    # --- the wire: two walls with their seam gates and the crossbar
    m.pipe([(12, T[12]), (12, 21)]); m.pipe([(29, 8), (29, B[29])]); m.pipe([(15, 15), (22, 15)]); m.put("^", 14, 14).put("^", 14, 15).put("^", 14, 16)
    m.put("Z", 12, 8).put("Z", 12, 17).put("Z", 29, 12).put("Z", 29, 23)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M11 Cold Wire (snow look, snow weather): Jugger (forced, Black Hole, HQ 1 (5,12), the west valley) against Grit (Blue Moon, HQ 2 (36,18), behind the east wall). West wall x12 (y0..21) with seam gates (12,8) and (12,17); "
        "east wall x29 (y8..29) with gates (29,12) and (29,23); crossbar y15 (x15..22). Com Towers (20,10) and (20,21), missile silo (25,15). Player: INF5 MECH2 TANK5 MDT2 ART3 ROCK2 RECON1 APC1; Grit: INF5 MECH3 TANK4 MDT2 ART5 ROCK3 RECON1."))
    m.put("1", 5, 12).put("2", 36, 18).put("t", 20, 10).put("t", 20, 21).put("M", 25, 15)
    # --- roads that follow the land: the zig-zag (south pass, the box, the gap, the northern strip), the gates' approaches, the ring of Grit's capital
    route(m, [C(6, 13), C(8, 17), C(11, 24), C(12, 26)], seed=1); route(m, [C(12, 26), C(17, 24), C(21, 22), C(25, 19), C(26, 15), C(26, 11), C(24, 7), C(24, 4)], seed=2)
    route(m, [C(24, 4), C(30, 4), C(35, 6), C(37, 12), C(36, 17)], seed=3); route(m, [C(6, 12), C(9, 8), C(11, 8)], seed=4); route(m, [C(8, 17), C(11, 17)], seed=5)
    route(m, [C(13, 8), C(17, 8), C(21, 10)], seed=6); route(m, [C(13, 17), C(17, 19), C(20, 21)], seed=7); route(m, [C(28, 12), C(26, 11)], seed=8); route(m, [C(28, 23), C(25, 20)], seed=9)
    route(m, [C(30, 12), C(33, 15), C(36, 17)], seed=10); route(m, [C(30, 23), C(33, 21), C(36, 19)], seed=11); route(m, [C(36, 18), C(39, 22), C(39, 26)], seed=12); route(m, [C(36, 18), C(38, 9)], seed=13)
    route(m, [C(20, 10), C(20, 5)], seed=14); route(m, [C(5, 13), C(3, 17)], seed=15)
    route(m, [C(6, 12), C(4, 8), C(3, 6)], seed=16); route(m, [C(11, 24), C(6, 25), C(3, 25)], seed=17); route(m, [C(35, 6), C(38, 4)], seed=18); route(m, [C(37, 12), C(40, 12)], seed=19)
    thin_roads(m)
    # --- towns
    town(m, 5, 12, "BBC", seed=1); town(m, 9, 8, "BC", seed=2); town(m, 8, 17, "BC", seed=3); town(m, 3, 17, "C", seed=4); town(m, 11, 24, "CC", seed=5); town(m, 14, 26, "C", seed=6)
    town(m, 20, 10, "Cb", seed=7); town(m, 20, 21, "Cb", seed=8); town(m, 25, 19, "Cb", seed=9); town(m, 26, 11, "bc", seed=43); town(m, 17, 8, "C", seed=11); town(m, 17, 19, "C", seed=12); town(m, 20, 5, "C", seed=13)
    town(m, 36, 18, "BBBC", seed=14, radius=3); town(m, 33, 21, "BC", seed=15); town(m, 33, 15, "BC", seed=16); town(m, 38, 9, "BC", seed=17); town(m, 39, 24, "CC", seed=18); town(m, 31, 4, "C", seed=19)
    town(m, 35, 6, "C", seed=20); town(m, 37, 14, "C", seed=21); town(m, 24, 25, "C", seed=22); town(m, 30, 27, "C", seed=23)
    town(m, 3, 6, "cc", seed=31); town(m, 4, 25, "cc", seed=32); town(m, 24, 12, "c", seed=33); town(m, 22, 18, "c", seed=34); town(m, 40, 12, "cc", seed=35); town(m, 38, 4, "cc", seed=36); town(m, 40, 20, "c", seed=37); town(m, 26, 6, "c", seed=38); town(m, 16, 22, "c", seed=39)
    neutralize(m, 13)
    m.tidy()
    # --- units: Black Hole in the west valley, Grit behind the east wall, a picket in the box
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 5, MDT: 2, ART: 3, ROCK: 2, RECON: 1, APC: 1}, (1, 4, 11, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 2, ART: 4, ROCK: 3, RECON: 1}, (30, 9, 40, 28), seed=2, gap=0, avoid=av)
    m.spread(2, {INF: 1, MECH: 1, TANK: 1, ART: 1}, (13, 2, 28, 28), seed=3, gap=2, avoid=av)
    m.note("hq", 5, 12, "Jugger's HQ"); m.note("enemy_hq", 36, 18, "Grit's HQ (objective)"); m.note("gate_w1", 12, 8, "seam gate (west wall)"); m.note("gate_w2", 12, 17, "seam gate (west wall)")
    m.note("gate_e1", 29, 12, "seam gate (east wall)"); m.note("gate_e2", 29, 23, "seam gate (east wall)")
    return m
