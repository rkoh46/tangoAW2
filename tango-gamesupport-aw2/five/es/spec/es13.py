"""M13 The Free Port (Act IV, wasteland: the bays are lava): take the Harbour Office and hold it three days while four armies fight everybody.

Design (docs/dev/map-design.md). The situation: the free port of Mercato: the Harbour Office (19,15) stands in an octagonal square in the middle;
the player's quarter is south of it on the south bay, Javier's west, Sonja's east, Kindle's Black Hole dock north with the Black Factory and the
inventions. Nobody is allied. The bays are lava (a wasteland map), so the quays have factories and airfields, not ports.
- Lanes: two rivers (Rio Sale west, Rio Dolce east) cut the side quarters from the square, each crossed by a bridge on the square's road and one on the
  south road; the north road under the minicannons and the two ridge gates lead to Kindle's dock; the square has four streets in.
- Where the fight happens: the square (the Office and four houses at its corners), and the market streets between each quarter and the square, where
  neutral houses stand every three cells: whoever holds the Office must hold the streets round it.
- Properties: about sixty, most of them neutral houses in the market streets and on the quays; each army has its HQ and two or three factories; a neutral
  base on the east quay (25,5) where the free port's port was.
- Threats and answers: three armies' tanks converge on the square -> hold the Office with infantry in the corner houses, artillery behind the south
  streets, tanks at the bridges; Kindle's fighter and copter -> the AA; minicannons over the north road -> the ridge gates; whoever is winning -> let the
  others fight it (they attack everyone).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 38, 33
AVOID = "~r=-^IZ#,12345BAPSNWELvnFDXO"


def build():
    m = Canvas("es13", W, H)
    m.header(armies=4, colours=(OS, GE, YC, BH), team=[1, 2, 3, 4], blackhole=True, objective=[1],
             comment="M13 The Free Port (province: the Free Port of Mercato on the Bay of Salt): capture the Harbour Office (neutral city, centre) and hold it 3 days. Everyone fights everyone. "
                     "Quarters: Kindle's Black Hole dock in the north (bay, Black Factory, crystals, minicannons), Javier's Green Earth west quarter on the sea, Sonja's Yellow Comet east quarter on the sea, "
                     "the player's south quarter on the south bay; two winding rivers (Rio Sale west, Rio Dolce east) cut the quarters from the central square, crossed by bridges. "
                     "Start forces: player INF4 MECH2 TANK3 MDT2 RECON2 ART2 AA1 APC1 (17); Javier and Sonja each INF3 MECH1 TANK3 MDT1 RECON1 ART1 AA1 (11); Kindle the same + FTR1 BCO1 TANK1 (14). The bays are lava: every quay has a factory or an airfield, no ports. "
                     "Threat/answer: tanks and Md Tanks -> own Tanks/MDT/ARTs behind the rivers; Kindle's Fighter and Copter -> AA on the line + the bases; minicannons (17,8) (21,8) cover the north road to "
                     "the square only: go round by the ridge gates or take them with ART; ART -> Recon to see, tanks to close; the quays' factories -> Tanks/ART on the quay.")
    # --- water: the silhouette is drawn row by row (sea spans), so the coast has coves, spits and a bay ---
    SEA = {0: [(0, 37)], 1: [(0, 37)], 2: [(0, 5), (12, 26), (32, 37)], 3: [(0, 2), (12, 26), (35, 37)], 4: [(0, 1), (13, 25)],
           5: [(14, 24)], 6: [(15, 23)], 7: [(16, 22)], 8: [(18, 20)],
           11: [(36, 37)], 12: [(0, 1), (35, 37)], 13: [(0, 2), (35, 37)], 14: [(0, 3), (34, 37)], 15: [(0, 3), (34, 37)], 16: [(0, 4), (35, 37)],
           17: [(0, 3), (33, 37)], 18: [(0, 3), (34, 37)], 19: [(0, 4), (34, 37)], 20: [(0, 3), (35, 37)], 21: [(0, 3), (35, 37)],
           22: [(0, 2), (36, 37)], 23: [(0, 1), (37, 37)], 24: [(0, 1)], 25: [(0, 0)],
           27: [(14, 23)], 28: [(0, 1), (8, 29), (36, 37)], 29: [(0, 3), (6, 32), (35, 37)], 30: [(0, 37)], 31: [(0, 37)], 32: [(0, 37)]}
    for y, spans in SEA.items():
        for x0, x1 in spans:
            m.rect("~", x0, y, x1, y)
    # --- the northern ridge (the rivers' springs) and the patches of wood ---
    m.cluster("^", 11, 11, 16, seed=7)
    m.cluster("^", 6, 10, 8, seed=8)
    m.cluster("^", 14, 10, 6, seed=23)
    m.cluster("^", 27, 11, 16, seed=9)
    m.cluster("^", 33, 10, 9, seed=10)
    m.cluster("^", 24, 10, 6, seed=24)
    m.cluster("f", 4, 6, 9, seed=12)
    m.cluster("f", 34, 6, 8, seed=13)
    m.cluster("f", 8, 14, 6, seed=14)
    m.cluster("f", 30, 15, 6, seed=15)
    m.cluster("f", 15, 22, 7, seed=16)
    m.cluster("f", 22, 21, 7, seed=17)
    m.cluster("f", 6, 24, 7, seed=18)
    m.cluster("f", 32, 24, 7, seed=19)
    m.cluster("f", 19, 10, 5, seed=20)
    m.cluster("^", 4, 15, 4, seed=21)
    m.cluster("^", 33, 17, 4, seed=22)
    m.cluster("f", 17, 26, 4, seed=25)
    m.cluster("f", 20, 4, 0, seed=26)
    # --- the rivers: springs in the ridge, mouths in the south bay (a straight last run, as the game draws a mouth) ---
    def vriver(x, y0, y1, shifts):
        """A north-south river: straight runs with one-cell side steps (the only bends the game's river tiles join cleanly)."""
        for y in range(y0, y1 + 1):
            m.put("-", x, y)
            if y in shifts:
                x += shifts[y]
                m.put("-", x, y)
        return x
    m.put("^", 10, 10).put("^", 27, 10)
    vriver(10, 11, 27, {12: 1, 15: 1, 19: -1, 21: -1})
    vriver(27, 11, 27, {13: -1, 19: 1})
    keep = set("12345BCAPTQbcapt") | INVENTION_CHARS

    def rd(pts, over=None):
        for x, y in m.path(pts):
            c = m.get(x, y)
            if c == "-":
                m.put("=", x, y)
            elif c not in keep and c != "=" and (over is None or c in over):
                m.put("R", x, y)

    def at(ch, x, y):
        if m.get(x, y) in "-=~":
            print("BAD", ch, x, y, m.get(x, y))
        return m.put(ch, x, y)

    def ats(ch, cells):
        for x, y in cells:
            at(ch, x, y)
        return m

    # --- the central square: a ring of streets round the Harbour Office ---
    m.rect("R", 17, 12, 21, 12).rect("R", 17, 18, 21, 18)
    m.rect("R", 16, 13, 16, 17).rect("R", 22, 13, 22, 17)
    m.puts("R", [(17, 13), (21, 17)])
    at("c", 19, 15)
    ats("c", [(17, 13), (21, 13), (17, 17), (21, 17)])
    ats("f", [(18, 16), (20, 14)])
    m.note("office", 19, 15, "Harbour Office: neutral city, the objective (hold 3 days)")
    # --- roads ---
    rd([(19, 22), (19, 18)])
    rd([(15, 23), (23, 23)], over=".f")
    rd([(15, 23), (15, 24)], over=".f")
    rd([(23, 23), (23, 24)], over=".f")
    rd([(16, 23), (16, 20), (17, 18)], over=".f")
    rd([(22, 23), (22, 20), (21, 18)], over=".f")
    # the square west to Javier and east to Sonja (bridges over the rivers)
    rd([(16, 16), (8, 16), (7, 17), (7, 18)], over=".f")
    rd([(22, 16), (30, 16), (31, 17)], over=".f")
    # the south roads
    rd([(15, 24), (8, 24), (7, 22)], over=".f")
    rd([(23, 24), (30, 24), (31, 22)], over=".f")
    # the north road from the square to Kindle's dock (under the minicannons), and to her factory
    rd([(19, 12), (19, 10), (17, 9), (14, 8), (11, 7), (9, 6)], over=".f^")
    rd([(19, 10), (22, 9), (26, 8), (29, 8)], over=".f^")
    # ridge gates: Javier's north gate, Sonja's north gate
    rd([(8, 7), (7, 10), (7, 13), (7, 18)], over=".f^")
    rd([(31, 8), (31, 11), (31, 14), (31, 17)], over=".f^")
    # woods and mountains keep off the river banks (the game draws no join there)
    for y in range(H):
        for x in range(W):
            if m.get(x, y) in "f^" and any(m.get(x + dx, y + dy) in "-=" for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if not (m.get(x, y) == "^" and (x, y) in ((10, 10), (27, 10))):
                    m.put(".", x, y)
    bridges = sorted((x, y) for y in range(H) for x in range(W) if m.get(x, y) == "=")
    # --- properties ---
    # the player's south quarter
    at("1", 19, 21); at("B", 16, 22); at("B", 22, 22); at("B", 18, 26)
    ats("c", [(14, 25), (24, 25), (15, 19), (23, 19)])
    ats("f", [(13, 21), (25, 21)])
    # Javier (west)
    at("2", 6, 18); at("B", 8, 15); at("B", 8, 22); at("B", 4, 17); at("A", 5, 22)
    ats("c", [(7, 12), (9, 19), (6, 26), (5, 14)])
    # Sonja (east)
    at("3", 31, 18); at("B", 29, 14); at("B", 29, 22); at("B", 32, 17); at("A", 33, 21)
    ats("c", [(31, 12), (28, 18), (31, 26), (33, 13)])
    # Kindle's north dock
    at("4", 8, 6); at("B", 5, 5); at("B", 11, 8); at("A", 5, 8); at("A", 13, 5); at("b", 25, 5)
    ats("c", [(10, 3), (15, 8), (27, 7), (33, 4)])
    at("F", 31, 6)                      # Black Factory, footprint (30..32, 4..7)
    for x in range(30, 33):
        for y in range(4, 8):
            if (x, y) != (31, 6):
                m.put("#", x, y)
    m.pipe([(31, 2), (31, 3)])
    at("c", 2, 8)
    at("X", 27, 5); at("X", 10, 9)       # two Black Crystals
    at("S", 17, 9); at("S", 22, 8)       # two minicannons facing the road south
    at("W", 12, 10); at("E", 29, 10)     # flank minicannons on the ridge gates
    # the market streets' neutral houses (MD01, MD02) and their cover
    for x, y in [(12, 13), (14, 16), (12, 19), (14, 22), (24, 13), (25, 16), (25, 19), (24, 22), (19, 10), (16, 10), (22, 11), (9, 12), (3, 12), (3, 20), (5, 24), (9, 27),
                 (13, 28), (25, 28), (29, 27), (33, 24), (35, 19), (34, 15), (29, 10), (35, 8), (31, 2), (2, 4), (16, 2), (24, 1), (13, 30), (20, 25), (27, 20), (11, 22)]:
        if m.get(x, y) in ".f" and (x, y) not in {(u["x"], u["y"]) for u in m.u}:
            m.put("c", x, y)
    for cx, cy, n, sd in ((12, 15, 3, 40), (26, 14, 3, 41), (13, 24, 3, 42), (26, 23, 3, 43), (3, 21, 3, 44), (34, 22, 3, 45), (2, 6, 3, 46), (35, 5, 3, 47),
                          (9, 25, 3, 48), (29, 25, 3, 49), (24, 18, 3, 50), (14, 18, 3, 51), (9, 4, 3, 52), (26, 2, 3, 53), (5, 11, 3, 54), (33, 11, 3, 55),
                          (16, 29, 3, 56), (23, 29, 3, 57), (3, 25, 3, 58), (35, 25, 3, 59)):
        m.cluster("f", cx, cy, n, seed=sd)
    for cx, cy, n, sd in ((15, 27, 3, 82), (23, 27, 3, 83), (7, 13, 3, 86), (31, 14, 3, 87), (2, 27, 3, 88), (36, 27, 3, 89), (11, 1, 3, 90), (27, 1, 3, 91), (4, 9, 3, 84), (34, 9, 3, 85), (4, 3, 4, 60), (34, 3, 4, 61), (2, 15, 3, 62), (36, 13, 3, 63), (6, 28, 4, 64), (32, 28, 4, 65), (13, 2, 3, 66), (28, 6, 3, 67),
                          (21, 24, 3, 68), (17, 24, 3, 69), (5, 20, 3, 70), (33, 19, 3, 71), (8, 10, 3, 72), (30, 12, 3, 73), (12, 27, 3, 74), (26, 27, 3, 75),
                          (14, 11, 3, 76), (24, 9, 3, 77), (11, 18, 3, 78), (26, 17, 3, 79), (7, 1, 3, 80), (30, 1, 3, 81)):
        m.cluster("^" if sd % 2 else "f", cx, cy, n, seed=sd)
    for y in range(H):
        for x in range(W):
            if m.get(x, y) in "f^" and (x, y) not in ((10, 10), (27, 10)) and any(m.get(x + dx, y + dy) in "-=" for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                m.put(".", x, y)
    # --- units ---
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 2, RECON: 2, ART: 2, AA: 1, APC: 1}, (13, 18, 24, 25), seed=1, gap=1, avoid=AVOID)
    for army, box, seed in ((2, (4, 13, 11, 25), 2), (3, (26, 13, 33, 25), 3)):
        m.spread(army, {INF: 3, MECH: 1, TANK: 3, MDT: 1, RECON: 1, ART: 1, AA: 1}, box, seed=seed, gap=1, avoid=AVOID)
    m.spread(4, {INF: 3, MECH: 1, TANK: 3, MDT: 1, RECON: 1, ART: 1, AA: 1, FTR: 1, BCO: 1}, (4, 3, 35, 9), seed=4, gap=1, avoid=AVOID)
    # (no pipeline here: the old west-beach pipe was a stub; Kindle's Piperunner is a Tank now)
    m.spread(4, {TANK: 1}, (1, 3, 12, 10), seed=5, gap=1, avoid=AVOID)
    # named places
    m.note("hq1", 19, 21, "player HQ"); m.note("hq2", 6, 18, "Javier's HQ (Green Earth)"); m.note("hq3", 31, 18, "Sonja's HQ (Yellow Comet)"); m.note("hq4", 8, 6, "Kindle's HQ (Black Hole)")
    m.note("factory", 31, 6, "Black Factory, Kindle's (anchor; footprint 30..32 x 4..7)")
    m.note("crystal1", 27, 5, "Black Crystal by the Factory"); m.note("crystal2", 10, 9, "Black Crystal south of Kindle's HQ")
    m.note("cannon1", 17, 9, "minicannon (facing down) over the north road"); m.note("cannon2", 22, 8, "minicannon (facing down) over the north road")
    m.note("cannon3", 12, 10, "minicannon (facing left) over the west ridge"); m.note("cannon4", 29, 10, "minicannon (facing right) over the east ridge")
    for i, b in enumerate(bridges, 1):
        m.note(f"bridge{i}", b[0], b[1], "river bridge")
    m.note("gate_w", 7, 10, "Javier's north gate (road through the ridge)"); m.note("gate_e", 31, 11, "Sonja's north gate")
    m.note("quay_player", 18, 26, "the player's quay factory on the south bay (lava: no ports)"); m.note("quay_kindle", 13, 5, "Kindle's quay airfield on the north bay"); m.note("quay_free", 25, 5, "neutral base on the east quay")
    m.note("quay_javier", 4, 17, "Javier's quay factory (west)"); m.note("quay_sonja", 32, 17, "Sonja's quay factory (east)")
    m.lake(10, 10, 9, seed=0, river_end=(10, 11))          # (a river starts in water or at the map edge: AW2 has no source tile)
    m.put(".", 27, 11)
    m.puts("r", [(17, 4), (21, 3), (22, 6), (17, 28), (21, 28), (25, 29)])      # reefs in the north and south bays
    m.lake(27, 11, 10, seed=1, river_end=(27, 12))          # (a river starts in water or at the map edge: AW2 has no source tile)
    return m
