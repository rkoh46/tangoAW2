"""M14 Varro's Gambit (Act IV): the legion storms Castra Maxima, the Consul's fortified camp on the Aurean shore; Cassius changes sides on day 4.

Design (docs/dev/map-design.md). The situation: the legion's camp in the west (HQ, two factories, a port on the open south coast); Castra Maxima in the
east behind a moat river and a broken wall of rock, with its gates, two factories, an airfield and a harbour on the open east sea; Cassius's army
on the ridge plateau in the north, hostile until day 4, then the player's.
- Lanes: the ridge track (north, through Cassius's plateau to the north gate), the valley road (centre, along the river to the valley gate) and the
  coast road (south, to the coast gate), joined by the plateau's south pass and a farm road across the valley; the river is crossed every few cells.
- Where the fight happens: the valley villages between the two camps (the contested middle, with the neutral base (24,19)), the moat's bridges and
  the three gates; the plateau's passes while Cassius is still hostile.
- Properties: villages three cells apart in the valley and on the coast plain, the plateau's hamlets (Cassius's), the camp's town (Varro's); a neutral
  base in the middle and the legion's reinforcement road (6..9,14..15) beside its HQ, the Consul's reserve road (40,12..16) inside the camp.
- Threats and answers: Varro's fighter -> AA and the missiles, woods; entrenched guns behind the wall -> recons, tanks through the gates, own artillery
  behind the moat; Md tanks out of the gates -> tanks and Md tanks at the bridges; Cassius's early rush -> hold the plateau's south pass until day 4.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 46, 28
AVOID = "~r=-^IZ#,12345BAPSNWELvnFDXO"
# where the south sea starts in each column (the coast has coves and spits)
COAST = [24, 24, 24, 24, 24, 24, 24, 24, 25, 25, 25, 24, 24, 25, 25, 26, 26, 25, 25, 24, 24, 25, 25, 26, 26, 25, 25, 24, 24, 25,
         25, 25, 25, 25, 25, 25, 24, 24, 25, 25, 24, 24, 24, 24, 24, 24]
# where the east sea starts in each row
EAST = [41, 41, 42, 43, 43, 43, 42, 42, 42, 43, 43, 43, 44, 44, 42, 41, 41, 41, 41, 42, 43, 43, 43, 42, 42, 42, 42, 42]


def build():
    m = Canvas("es14", W, H)
    m.header(armies=3, colours=(BM, OS, YC), team=[1, 2, 3], objective=[1],
             comment="M14 Varro's Gambit (province: the Aurean shore, the Consul's camp Castra Maxima): storm the camp, take Varro's HQ 2 (38,12) or rout his army. "
                     "Three lanes: the coast road (south, over the river's mouth bridge), the river valley (centre road beside the moat river, gate bridge), the ridge track (north, through Cassius's hill camp to the north gate). "
                     "Army 3 (Cassius, Yellow Comet, HQ (21,4) on the ridge plateau) is hostile to both until day 4 (mission code), then fights for the player. "
                     "Start forces: player INF4 MECH3 TANK3 MDT2 RECON1 ART2 AA1 (16), funds 6000; Varro INF5 MECH2 TANK4 MDT3 ART3 ROCK1 AA1 MIS1 FTR1 RECON1 (22, of which INF3 ART3 ROCK1 hold) + reserves on days 5 and 8 at the camp's east road; "
                     "Cassius TANK3 RECON2 MDT1 INF2 (8). Threat/answer: Varro's Fighter -> AA and Missiles in the player's reinforcements and the player's AA on the road, woods cover; "
                     "entrenched Artillery and Rockets behind the wall (range 3..5) -> Recon to find them, Tanks close fast through the gates, own Artillery behind the moat; Md Tank counter-attacks from the gates -> "
                     "own Tanks/MDT, bridges are the choke; Cassius's early tank rush on the ridge track -> hold the ridge pass with Tanks and ART until he changes sides.")
    # --- the sea ---
    for x in range(W):
        m.rect("~", x, COAST[x], x, H - 1)
    for y in range(H):
        m.rect("~", EAST[y], y, W - 1, y)
    # (no coves on the west edge: two- and three-cell inlets there read as ponds in the game's picture)
    # --- the mountains: the ridge in the north, the camp's wall, the sea wall ---
    for i, (cx, cy, rx, ry) in enumerate([(14, 7, 4, 3), (22, 3, 7, 3), (27, 8, 3, 3), (18, 9, 3, 1), (12, 2, 3, 2), (6, 3, 3, 2), (40, 3, 3, 2), (36, 1, 2, 1)], 30):
        m.blob("^", cx, cy, rx, ry, seed=i, wobble=0.3)
    # Cassius's plateau: open ground inside the ridge, a pass on each side
    for i, (cx, cy, rx, ry) in enumerate([(21, 4, 4, 1), (17, 5, 2, 1), (26, 5, 2, 1)]):
        m.blob(".", cx, cy, rx, ry, seed=40 + i, wobble=0.2, only="^")
    m.rect(".", 20, 6, 21, 9)                               # the plateau's south pass to the valley
    m.rect(".", 11, 5, 15, 5)                               # the track enters the ridge
    m.rect(".", 26, 5, 31, 6)                               # ... and leaves it for the north gate
    # the camp's wall: a broken line of mountains along the moat, with the gates open
    for y in (12, 13, 14, 15, 17, 18, 19, 20, 22, 23):
        m.put("^", 33, y)
    for y in (2, 3, 4, 5, 6, 8, 9, 10, 11):
        m.put("^", 32 + (y % 3 == 0), y)
    for i, (cx, cy, n) in enumerate([(41, 21, 7), (41, 10, 6), (38, 24, 4), (35, 10, 3), (36, 19, 3), (38, 5, 3), (41, 15, 2)], 60):
        m.cluster("^", cx, cy, n, seed=i)
    # --- woods: hedgerows, copses, the dunes of the coast ---
    for i, (cx, cy, n) in enumerate([(6, 12, 8), (8, 20, 9), (4, 8, 6), (11, 15, 7), (15, 14, 6), (18, 17, 9), (24, 18, 9), (27, 14, 6), (22, 12, 6), (16, 20, 6),
                                     (20, 22, 7), (26, 22, 6), (35, 7, 7), (38, 18, 6), (36, 22, 5), (35, 14, 5), (10, 24, 4), (12, 6, 6), (1, 14, 4), (1, 19, 4), (21, 15, 4), (28, 20, 4)], 100):
        m.cluster("f", cx, cy, n, seed=i)
    # --- the river: spring in the western hills, along the valley, then the moat down the camp's west side to the south sea ---
    def hriver(y, x0, x1, shifts):
        for x in range(x0, x1 + 1):
            m.put("-", x, y)
            if x in shifts:
                y += shifts[x]
                m.put("-", x, y)
        return y

    def vriver(x, y0, y1, shifts):
        for y in range(y0, y1 + 1):
            m.put("-", x, y)
            if y in shifts:
                x += shifts[y]
                m.put("-", x, y)
        return x
    m.put("^", 12, 11).put("^", 12, 10).put("^", 11, 11)
    yend = hriver(11, 13, 30, {15: 1, 20: 1, 26: 1})
    xend = vriver(30, yend, 24, {19: 1})
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
    # --- roads ---
    rd([(7, 17), (7, 20), (11, 20), (11, 21), (20, 21), (20, 22), (27, 22), (27, 21), (35, 21)], over=".f")      # the coast road
    rd([(6, 14), (9, 15), (14, 15), (14, 17), (22, 17), (24, 16), (35, 16)], over=".f")                           # the valley road
    rd([(7, 11), (8, 8), (11, 5), (21, 4), (27, 5), (29, 6), (35, 7)], over=".f^")                                # the ridge track
    rd([(5, 14), (6, 14)], over=".f")
    rd([(21, 5), (21, 9), (18, 10), (18, 15)], over=".f^")                                                         # down from Cassius's plateau
    rd([(35, 7), (38, 7), (38, 21)], over=".f")
    rd([(35, 16), (38, 16)], over=".f")
    rd([(35, 21), (38, 21)], over=".f")
    rd([(38, 12), (40, 12), (40, 17)], over=".f")
    rd([(24, 16), (24, 9), (27, 5)], over=".f^")                                                                   # the farm road across the valley
    # --- properties ---
    at("1", 5, 14); at("B", 7, 11); at("B", 7, 17); at("P", 9, 24)
    ats("c", [(3, 10), (9, 14), (6, 20), (2, 17)])
    at("3", 21, 4); at("B", 18, 4); at("B", 24, 5)
    ats("c", [(16, 5), (27, 4)])
    ats("c", [(17, 15), (24, 16), (14, 19), (22, 20), (28, 18)])
    at("2", 38, 12); at("B", 36, 9); at("B", 36, 17); at("A", 40, 8); at("P", 40, 17)
    ats("c", [(35, 12), (39, 10), (37, 19), (35, 5), (40, 14), (39, 21)])
    # the valley's and the coast plain's villages, the plateau's hamlets (MD01, MD02), a neutral base in the middle
    for x, y in [(3, 5), (8, 2), (2, 2), (14, 1), (29, 1), (33, 2), (12, 8), (9, 9), (3, 13), (10, 13), (15, 11), (20, 13), (26, 10), (28, 13), (31, 9),
                 (11, 17), (14, 23), (18, 24), (22, 23), (26, 24), (30, 23), (17, 18), (20, 19), (27, 19), (31, 14), (4, 19), (8, 22), (2, 21), (12, 21),
                 (25, 13), (35, 24), (43, 1), (42, 26), (16, 13), (6, 6)]:
        if m.get(x, y) in ".f":
            at("c", x, y)
    at("b", 24, 19)
    # --- units ---
    # (the mission's reinforcement cells stay free: LEGION and RESERVE in es_act4.rs)
    m.reserve([(7, 14), (8, 14), (6, 14), (9, 15), (40, 12), (40, 13), (40, 15), (40, 16)])
    m.spread(1, {INF: 4, MECH: 3, TANK: 3, MDT: 2, RECON: 1, ART: 2, AA: 1}, (2, 9, 10, 20), seed=1, gap=1, avoid=AVOID)
    m.spread(3, {TANK: 3, RECON: 2, MDT: 1, INF: 2}, (16, 2, 27, 6), seed=3, gap=1, avoid=AVOID)
    def stand(army, kind, x, y, **kw):
        taken = {(u["x"], u["y"]) for u in m.u}
        for r in range(0, 5):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (x + dx, y + dy)
                    if m.inside(*c) and m.get(*c) in ".fR" and c not in taken:
                        return m.unit(army, kind, *c, **kw)
        raise ValueError(("no ground", x, y))
    for x, y in [(36, 11), (36, 14), (37, 18)]:
        stand(2, ART, x, y, hold=True)
    stand(2, ROCK, 36, 13, hold=True)
    for x, y in [(34, 7), (34, 16), (34, 21)]:
        stand(2, INF, x, y, hold=True)
    m.spread(2, {INF: 2, MECH: 2, TANK: 4, MDT: 3, AA: 1, MIS: 1, FTR: 1, RECON: 1}, (34, 4, 41, 22), seed=2, gap=1, avoid=AVOID)
    # named places
    m.note("hq1", 5, 14, "the legion's camp HQ"); m.note("hq2", 38, 12, "Varro's HQ in Castra Maxima: the objective"); m.note("hq3", 21, 4, "Cassius's HQ on the ridge plateau")
    m.note("gate_n", 33, 7, "Castra Maxima's north gate (end of the ridge track)"); m.note("gate_c", 33, 16, "the valley gate"); m.note("gate_s", 33, 21, "the coast gate")
    m.note("moat_bridge_c", 30, 16, "valley road bridge over the moat"); m.note("moat_bridge_s", 31, 21, "coast road bridge near the river mouth")
    m.note("pass_w", 12, 5, "the ridge track's west pass"); m.note("pass_s", 21, 8, "Cassius's plateau south pass to the valley")
    m.note("harbour", 40, 17, "Varro's port in the camp harbour"); m.note("airfield", 40, 8, "Varro's airport")
    m.note("reserve1", 40, 12, "Varro's reserve column road (day 5, 8)")
    m.note("port1", 9, 24, "the legion's port on the open south coast")
    m.note("mid_base", 24, 19, "neutral base in the valley")
    m.note("legion_road", 7, 14, "the legion's reinforcements on days 5 and 8 at (6..9,14..15)")
    m.ragged("^", 6, seed=1).ragged("^", 6, seed=2)               # (no drawn wall of mountains: lint DQ12)
    m.lake(12, 11, 9, seed=0, river_end=(13, 11))          # (a river starts in water or at the map edge: AW2 has no source tile)
    return m
