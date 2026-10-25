"""M15 Pax Romana (Act IV, tag): break the Accord's blockade of the Strait of Elms: sink the flagship and take the Strait Fort's harbour.

Design (docs/dev/map-design.md). The situation: the legion holds the west shore (HQ, factories, an airport, two ports on the strait); Drake's fleet
bars the strait in front of the Strait Fort on the east shore (his HQ, the harbour (39,13), factories); Sensei's air wing sits on Elm Isle in the middle
of the strait (her HQ and airfield). Salt Isle (south-west) and Reed Isle (north-east) each have a neutral port and a hamlet.
- Lanes: the north and the south channels round Elm Isle (reefs narrow them) and the open water in front of the harbour; for the land army, landings on
  Elm Isle and on the fort shore's beaches north and south of the harbour.
- Where the fight happens: Elm Isle (the contested middle: Sensei's field and the hamlets round it), the two channels, then the harbour mouth.
- Properties: villages three cells apart on both shores and the isles (each landing has something to take and cover), the two isles' neutral ports
  (a ship factory for whoever lands there), the fort's town on the east shore.
- Threats and answers: Sensei's fighters, bombers and copters -> cruisers, the AA and missiles, fighters from the legion's airport; the flagship and the
  subs -> the legion's battleship, sub and bombers, cruisers against the subs; the fort's garrison -> landers on the beaches with mechs and tanks.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import map as fivemap          # (five/map.py: the tile joins the game draws)

W, H = 46, 27
# the west shore (the legion's landfall): land is x <= WEST[y]; the east shore (the Strait Fort): land is x >= EAST[y]
WEST = [8, 8, 9, 9, 10, 10, 9, 9, 10, 11, 11, 10, 9, 9, 10, 11, 11, 10, 10, 9, 9, 10, 9, 8, 8, 8, 7]
EAST = [39, 38, 38, 37, 37, 36, 37, 37, 36, 35, 35, 35, 35, 35, 35, 35, 36, 37, 36, 36, 37, 38, 38, 39, 39, 40, 40]
AVOID = "~r=-^IZ#,12345BAPSNWELvnFDXO"


def build():
    m = Canvas("es15", W, H, fill="~")
    m.header(armies=3, colours=(BM, GE, YC), team=[1, 2, 2], objective=[1],
             comment="M15 Pax Romana (tag; province: the Strait of Elms, the Accord's Strait Fort): break the blockade: sink the flagship (Drake's Battleship, named 'flagship', at the harbour mouth (34,13)) and take the Strait Fort's harbour port (39,13). "
                     "Army 2 = Drake (Green Earth: ships + the fort's garrison, HQ (43,13)); army 3 = Sensei (Yellow Comet: the air wing on Elm Isle, HQ (23,13)); the two are allied. The player (army 1, west shore, HQ (3,13)) picks a free tag pair. "
                     "Start forces: player CR3 BS1 SUB1 LAN2 TCO1 BCO2 FTR2 BMB1 INF3 MECH2 AA1 (18), funds 10000; Drake BS2 CR3 SUB2 LAN2 INF3 MECH2 TANK2 ART2 AA1 (19); Sensei FTR3 BMB2 BCO2 INF2 AA1 MIS1 (11). "
                     "Threat/answer: Sensei's Fighters and Bombers -> the Cruisers' AA, own Fighters, AA and the Missiles from the airport; Sensei's Copters -> Fighters and AA; Drake's Battleships -> Bombers (the airport (4,7)), Submarines "
                     "and own Battleship; Submarines -> Cruisers; the fort's Artillery and AA cover the harbour -> land from the beach (shoal x=39..40 on rows 7..9 and 17..20) or sink the fleet first, Bombers on the Artillery; Landers -> beaches and ports on both shores and Salt Isle.")
    # --- the shores ---
    for y in range(H):
        m.rect(".", 0, y, WEST[y], y)
        m.rect(".", EAST[y], y, W - 1, y)
    # the Strait Fort's harbour: an inlet cut into the east shore
    for x, ys in ((38, (13, 13)), (37, (12, 14)), (36, (11, 15)), (35, (11, 15))):
        m.rect("~", x, ys[0], x, ys[1])
    # Elm Isle (Sensei's air base), Salt Isle (south-west islet), Reed Isle (north islet)
    m.blob(".", 23, 13, 6, 4, seed=1, wobble=0.3)
    m.blob(".", 15, 21, 4, 2, seed=2, wobble=0.3)
    m.blob(".", 30, 6, 3, 2, seed=3, wobble=0.3)
    # reefs in the shallows
    for x, y in ((12, 15), (13, 16), (12, 9), (31, 11), (32, 10), (31, 19), (30, 20), (18, 18), (27, 1), (20, 5), (16, 8)):
        m.put("r", x, y)
    # --- mountains and woods ---
    for i, (cx, cy, n) in enumerate([(3, 3, 10), (6, 22, 9), (2, 18, 6), (23, 10, 5), (25, 15, 5), (41, 5, 12), (43, 21, 11), (38, 24, 6), (37, 7, 7), (44, 14, 5), (22, 10, 6), (27, 15, 6), (14, 21, 3), (3, 8, 5), (12, 1, 4)], 10):
        m.cluster("^", cx, cy, n, seed=i)
    for i, (cx, cy, n) in enumerate([(6, 8, 9), (4, 15, 5), (7, 17, 6), (3, 23, 8), (21, 14, 7), (26, 12, 7), (15, 20, 4), (29, 3, 3), (40, 11, 6), (41, 18, 6),
                                     (44, 9, 8), (44, 24, 6), (8, 2, 7), (10, 12, 4), (36, 22, 5), (20, 16, 5), (24, 9, 5), (38, 3, 5), (1, 12, 5), (9, 20, 4), (44, 17, 5)], 40):
        m.cluster("f", cx, cy, n, seed=i)
    keep = set("12345BCAPTQbcapt") | INVENTION_CHARS

    def rd(pts, over=None):
        for x, y in m.path(pts):
            c = m.get(x, y)
            if c not in keep and c != "=" and c not in "~r,^" and (over is None or c in over):
                m.put("R", x, y)

    def at(ch, x, y):
        if m.get(x, y) in "-=~r,":
            print("BAD", ch, x, y, m.get(x, y))
        return m.put(ch, x, y)

    def ats(ch, cells):
        for x, y in cells:
            at(ch, x, y)
        return m
    def coast_port(ch, x, y, radius=5):
        """A port on the land cell nearest (x, y) that has open sea (not shoal) beside it."""
        best = None
        for py in range(max(0, y - radius), min(H, y + radius + 1)):
            for px in range(max(0, x - radius), min(W, x + radius + 1)):
                if m.get(px, py) in ".f" and sum(m.get(px + dx, py + dy) == "~" for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)) if m.inside(px + dx, py + dy)) >= 1 \
                        and 0 < px < W - 1 and 0 < py < H - 1:
                    d = abs(px - x) + abs(py - y)
                    if best is None or d < best[0]:
                        best = (d, px, py)
        assert best, ("no coast for a port", x, y)
        m.put(ch, best[1], best[2])
        return best[1], best[2]
    # --- the west shore: the legion's camp ---
    at("1", 3, 13); at("A", 4, 7); at("B", 4, 10); at("B", 4, 17)
    pw1 = coast_port("P", 8, 5); pw2 = coast_port("P", 8, 19)
    ats("c", [(2, 9), (2, 16), (8, 12), (3, 21)])
    rd([(3, 13), (7, 13), (7, 12)]); rd([(3, 13), (3, 10), (4, 10)]); rd([(3, 13), (3, 17), (4, 17)]); rd([(4, 10), (4, 7)]); rd([(4, 7), (6, 6), pw1])
    rd([(4, 17), (7, 18), pw2])
    # --- Elm Isle: Sensei's air base ---
    at("3", 23, 13); at("A", 21, 11); at("B", 25, 14)
    ats("c", [(22, 15), (24, 11)])
    rd([(23, 13), (23, 11), (21, 11)]); rd([(23, 13), (24, 14), (25, 14)]); rd([(23, 13), (22, 15)])
    # --- Salt Isle and Reed Isle: neutral ports and a city each ---
    ps = coast_port("p", 15, 20, 4); pr = coast_port("p", 29, 5, 4)
    at("c", 14, 22); at("c", 31, 6)
    rd([ps, (14, 22)]); rd([pr, (31, 6)])
    # --- the Strait Fort: Drake's shore ---
    at("2", 43, 13); at("B", 41, 9); at("B", 41, 17); at("P", 39, 13)
    pe1 = coast_port("P", 40, 5); pe2 = coast_port("P", 40, 21)
    ats("c", [(42, 11), (42, 15), (38, 9), (38, 19), (44, 5)])
    # villages three cells apart on both shores and the isles (MD01, MD02)
    for x, y in [(5, 1), (1, 3), (6, 5), (1, 11), (5, 10), (5, 15), (1, 19), (6, 18), (2, 24), (6, 22), (7, 25), (9, 20),
                 (41, 1), (44, 2), (40, 6), (44, 9), (39, 16), (44, 17), (41, 21), (44, 23), (42, 25), (37, 23), (40, 3),
                 (20, 14), (26, 12), (23, 9), (25, 16), (12, 24), (17, 23), (28, 3), (33, 4)]:
        if m.get(x, y) in ".f":
            at("c", x, y)
    rd([(39, 13), (43, 13)]); rd([(43, 13), (43, 9), (41, 9)]); rd([(43, 13), (43, 17), (41, 17)]); rd([(41, 9), (41, 6), pe1])
    rd([(41, 17), (41, 19), pe2]); rd([(38, 9), (40, 9)]); rd([(38, 19), (41, 19)])
    # beaches: shoal strips where Landers and the Fort's attackers go ashore (the ports' neighbours stay open sea)
    for y in range(8, 18):
        m.put(",", WEST[y] + 1, y)
    for y in list(range(21, 26)) + [1, 2, 3]:
        m.put(",", WEST[y] + 1, y)
    for y in list(range(6, 10)) + list(range(16, 21)):
        m.put(",", EAST[y] - 1, y)
    ports = [(x, y) for y in range(H) for x in range(W) if m.get(x, y) in "Pp"]
    wet = {(px + dx, py + dy) for px, py in ports for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)) if m.get(px + dx, py + dy) == "~"}
    m.beach(11, 19, 19, 24); m.beach(20, 8, 28, 19); m.beach(26, 3, 34, 9)
    for x, y in wet:
        m.put("~", x, y)
    # a shoal cell must touch the sea (else the game has no tile for it): the stray ones become sand
    for _ in range(4):
        for y in range(H):
            for x in range(W):
                if m.get(x, y) == ",":
                    around = [m.get(x + dx, y + dy) if m.inside(x + dx, y + dy) else "~" for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))]
                    try:
                        fivemap.water_tile(",", around)
                    except AssertionError:
                        m.put(".", x, y)
    def sea_near(x, y, deep=True):
        taken = {(u["x"], u["y"]) for u in m.u}
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (x + dx, y + dy)
                    if m.inside(*c) and m.get(*c) == "~" and c not in taken and all(m.get(c[0] + a, c[1] + b) in "~," for a in (-1, 0, 1) for b in (-1, 0, 1) if m.inside(c[0] + a, c[1] + b)):
                        return c
        raise ValueError(("no sea", x, y))

    def ship(army, kind, x, y, **kw):
        m.unit(army, kind, *sea_near(x, y), **kw)
    # --- units ---
    for x, y in [(WEST[6] + 4, 6), (WEST[11] + 4, 11), (WEST[15] + 4, 16)]:
        ship(1, CR, x, y)
    ship(1, BS, WEST[10] + 6, 13); ship(1, SUB, 12, 22)
    for x, y in [(WEST[10] + 2, 10), (WEST[16] + 2, 16)]:
        ship(1, LAN, x, y)
    m.unit(1, TCO, 5, 12).units(1, BCO, [(5, 8), (5, 18)]).units(1, FTR, [(5, 6), (6, 9)]).unit(1, BMB, 5, 7)
    m.spread(1, {INF: 3, MECH: 2, AA: 1}, (2, 8, 8, 18), seed=1, gap=1, avoid=AVOID)
    # Drake: the fleet in the strait, the fort's garrison
    m.unit(2, BS, 34, 13, name="flagship")
    ship(2, BS, 33, 18)
    for x, y in [(32, 10), (33, 16), (30, 13)]:
        ship(2, CR, x, y)
    for x, y in [(31, 15), (31, 11)]:
        ship(2, SUB, x, y)
    for x, y in [(EAST[7] - 2, 7), (EAST[18] - 2, 18)]:
        ship(2, LAN, x, y)
    m.units(2, ART, [(41, 12), (41, 15)], hold=True)
    m.units(2, INF, [(40, 8), (40, 18)], hold=True)
    m.unit(2, AA, 42, 10, hold=True)
    m.spread(2, {INF: 1, MECH: 2, TANK: 2}, (38, 6, 44, 20), seed=2, gap=1, avoid=AVOID)
    # Sensei: the air wing on Elm Isle
    m.spread(3, {FTR: 3, BMB: 2, BCO: 2, INF: 2, AA: 1, MIS: 1}, (19, 9, 27, 17), seed=3, gap=0, avoid=AVOID)
    for u in m.u:
        if u["kind"] in (BS, CR, SUB, LAN) and m.get(u["x"], u["y"]) not in "~,":
            print("BAD ship", u)
    # places
    m.note("hq1", 3, 13, "the legion's HQ"); m.note("hq2", 43, 13, "Drake's HQ in the Strait Fort"); m.note("hq3", 23, 13, "Sensei's HQ on Elm Isle")
    m.note("harbour", 39, 13, "the Strait Fort's harbour (port): take it")
    m.note("flagship", 34, 13, "Drake's flagship (Battleship named flagship) at the harbour mouth")
    m.note("airfield", 21, 11, "Sensei's airport on Elm Isle"); m.note("airport1", 4, 7, "the legion's airport")
    m.note("beach_w", WEST[8] + 1, 8, "west beach: shoal on rows 8..17, ports at the ends"); m.note("beach_e", EAST[6] - 1, 6, "east beaches: shoal x 35..37 rows 6..9 and 16..20")
    m.note("salt_isle", 15, 20, "Salt Isle: neutral port (15,20), city (14,22)"); m.note("reed_isle", 29, 5, "Reed Isle: neutral port (29,5), city (31,6)")
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
