"""M16 Sol Invictus (Act IV, the finale): break Stormhold, Eagle's and Hachi's stronghold on its plateau; Mount Sol smokes beside the west gate.

Design (docs/dev/map-design.md). The situation: the legion's beachhead in the south-west (HQ, two factories, an airport, a port on the cove); the
city on the plateau in the north-east behind an escarpment with three gates (west, north, south), Hachi's town and harbour district inside it,
Eagle's airfield and his own HQ beyond the north gate. Mount Sol (a volcano, Dual Strike's rules as the BH Campaign has them) stands in the valley
below the west gate: from day 3 it erupts every day on three cells of the ring round its rock (19..26, 10..17), hurting whoever is there, the legion or the city's sally.
- Lanes: the Salt Road along the south coast (two bridges) to the harbour district and the south gate; the Weir Valley (the Stormwater river, bridged
  three times) past Mount Sol to the west gate; the Needle Pass over the northern mountains to Eagle's airfield and the north gate; farm tracks join
  them so a column can switch lanes.
- Where the fight happens: the valley villages and the neutral bases (16,19) and (24,8) in the middle, the volcano's ring before the west gate, the
  three gates, then the city.
- Properties: villages three cells apart on the plain and in the valley (money for the legion's waves and cover for its infantry), the city's houses
  (Hachi's), the airfield (Eagle's); the neutral port on the south coast for a second fleet.
- Threats and answers: Eagle's fighters, bombers and copters and the day-6 air wing -> anti-air, missiles and fighters with the column; Hachi's Md
  tanks and neotanks out of the gates -> Md tanks, neotanks, artillery behind the river; the guns in the walls -> recons, bombers, infantry over the rock;
  cruisers in the inlet and the harbour -> bombers and missiles on the quay; the volcano -> do not stand in its ring on an eruption day.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 44, 28


def build():
    m = Canvas("es16", W, H)
    m.header(armies=3, colours=(BM, GE, OS), team=[1, 2, 2], objective=[1],
             comment="M16 Sol Invictus (finale, Klaus + partner): break Stormhold, 44x28, daylight, no fog. Armies: 1 the legion (Emerald Sun skin on Blue Moon's colour), 2 Eagle (Green Earth: the north airfield, "
                     "airports, a base, a port in the north-east inlet; HQ '2' (31,2)), 3 Hachi (Orange Star: the city and the harbour district, bases, a port, cities; HQ '3' (34,10)); they are allies. "
                     "Win: take both HQs or rout both armies. Lanes: (a) the coast road along the south shore to the harbour district and the south gate (35,15); (b) the river valley (the Stormwater, a winding river with "
                     "two bridges) to the west gate (26,9); (c) the high pass over the northern mountains to the north airfield and the north gate (31,4). Threat/answer: Eagle's Fighters, Bombers and B Copters -> the legion "
                     "has 3 Anti-Air, 2 Missiles, 2 Fighters and builds more at 2 bases and the airport; Hachi's Md Tanks and Neotank on the roads -> own Md Tanks, Neotanks, Artillery behind the river, Rockets; Hachi's Artillery "
                     "and Rockets in the walls -> Recons to find them, Fighters and Bombers, Infantry over the mountains; Eagle's Cruisers in the harbour -> Bombers, Missiles on the quay, Artillery on the coast road; "
                     "the day-6 air wing and Hachi's reserve waves -> keep Anti-Air with the column and hold the river line.")
    # ---- the sea: the south coast (a cove for the landing, a headland, the river mouth, a small bay), the harbour bay, the east coast, the north-east inlet ----
    first_sea = [25, 25, 25, 25, 24, 23, 23, 22, 22, 22, 22, 23, 24, 25, 25, 25, 25, 25, 24, 24, 24, 24, 24, 24, 24, 24, 24, 23, 23, 23, 22, 22, 21, 21, 21, 21, 21, 21, 21, 20, 20, 19, 18, 17]
    for x, y0 in enumerate(first_sea):
        m.rect("~", x, y0, x, H - 1)
    m.rect("~", 39, 17, 43, 27).rect("~", 41, 8, 43, 17).blob("~", 40, 4, 4, 4, seed=5).rect("~", 41, 0, 43, 8)
    m.beach(0, 18, 31, 27)
    # ---- the northern mountains (the high pass) ----
    for i, (cx, cy, n) in enumerate([(4, 2, 30), (12, 3, 34), (20, 1, 22), (3, 10, 16), (22, 6, 22), (9, 8, 12)]):
        m.cluster("^", cx, cy, n, seed=10 + i)
    # ---- the plateau's escarpment: wall arcs of mountain, gates left open for the roads (west (26,9), north (31,4), south (35,15)) ----
    m.meander("^", (27, 4), (26, 13), seed=30, amp=1)
    m.meander("^", (27, 14), (38, 15), seed=31, amp=1)
    m.meander("^", (28, 4), (38, 4), seed=32, amp=1)
    m.cluster("^", 38, 12, 7, seed=33)
    m.cluster("^", 27, 7, 5, seed=34)
    m.cluster("^", 32, 15, 5, seed=35)
    m.cluster("^", 34, 4, 4, seed=36)
    m.cluster("^", 36, 11, 5, seed=20)          # a hill in the city
    # ---- the Stormwater: from a spring in the northern mountains, a winding valley, mouth on the south coast ----
    m.put("^", 15, 9)
    river = m.path([(15, 10), (15, 14), (17, 14), (17, 17), (21, 17), (21, 23)])
    for x, y in river:
        m.put("-", x, y)
    # ---- woods: hedgerows and orchards ----
    for i, (cx, cy, n) in enumerate([(11, 17, 9), (15, 12, 8), (8, 13, 7), (30, 20, 8), (24, 17, 7), (4, 15, 6), (14, 21, 6), (33, 7, 6), (22, 10, 6), (27, 21, 5), (39, 8, 4), (12, 9, 5), (35, 14, 4)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    # ---- roads ----
    # the coast road (a): from the camp east along the shore, over the river by a bridge, to the harbour district and the south gate
    m.line("R", [(6, 21), (10, 21), (10, 22), (17, 22), (17, 21), (24, 21), (24, 20), (32, 20), (34, 19), (35, 19), (35, 15)], over=".f^")
    # the valley road (b): from the camp north into the valley, up beside the river, over a bridge, to the west gate
    m.line("R", [(6, 18), (8, 18), (8, 14), (13, 14), (13, 12), (19, 12), (19, 10), (24, 10), (26, 9)], over=".f^")
    # the high pass (c): from the camp's north over the mountains to the airfield and the north gate
    m.line("R", [(5, 16), (5, 11), (9, 11), (9, 7), (24, 7), (24, 3), (29, 2), (31, 2)], over=".f^")
    m.line("R", [(31, 2), (31, 9)], over=".f^")
    # the city's streets
    m.line("R", [(26, 9), (30, 9), (34, 9), (34, 12), (35, 13), (35, 15)], over=".f^")
    m.line("R", [(34, 12), (38, 12), (38, 18)], over=".f^")
    m.line("R", [(27, 13), (30, 13), (30, 9)], over=".f^")
    # the lanes' bridges: a river cell a road meets from both sides, the water running across it
    for (x, y) in list(river):
        if m.get(x, y) != "-":
            continue
        n, e, so, w = m.get(x, y - 1), m.get(x + 1, y), m.get(x, y + 1), m.get(x - 1, y)
        if e in "R" and w in "R" and n in "-=" and so in "-=":
            m.put("=", x, y)
        elif n in "R" and so in "R" and e in "-=~" and w in "-=~":
            m.put("=", x, y)
    # ---- Mount Sol: a volcano (4x4: anchor V on the second column, third row) below the west gate; its ring is erupted from day 3 (es_act4.rs)
    m.frame("^", 20, 11, 25, 16)                                                      # (the cone's rock: the game draws a volcano among mountains)
    for y in range(12, 16):
        for x in range(21, 25):
            m.put("#", x, y)
    m.put("V", 22, 14)
    m.road([(14, 15), (16, 15)]).road([(18, 15), (19, 15), (19, 16)]).road([(19, 18), (19, 20)])   # the weir track across the valley (two bridges)
    m.put("=", 17, 15).put("=", 19, 17)
    m.road([(24, 10), (24, 8)])
    # ---- properties ----
    # the valley's and the plain's villages (MD01, MD02), two neutral bases in the middle
    for x, y in [(2, 13), (6, 9), (2, 6), (7, 3), (12, 6), (17, 5), (14, 10), (11, 13), (7, 15), (2, 23), (12, 19), (14, 23), (19, 14), (18, 9), (22, 18),
                 (26, 17), (26, 23), (30, 17), (33, 18), (27, 15), (22, 3), (26, 1), (38, 6), (40, 14), (36, 17), (32, 23), (29, 22), (10, 1), (19, 21)]:
        if m.get(x, y) in ".f":
            m.put("c", x, y)
    m.puts("b", [(16, 19), (24, 8)])
    # the legion: HQ, two bases, an airport, a port on the cove, cities
    m.put("1", 4, 20).puts("B", [(7, 19), (3, 17)]).put("A", 9, 20).put("P", 8, 24).puts("C", [(5, 22), (11, 16)])
    # neutral provinces along the lanes
    m.puts("c", [(13, 15), (20, 9), (17, 20), (23, 19), (28, 21), (9, 12), (16, 3)])
    m.put("p", 25, 23)
    # Hachi: the city and the harbour district
    m.put("3", 34, 10).puts("B", [(31, 11), (37, 11), (33, 6)]).puts("P", [(38, 18), (35, 20)])
    m.puts("C", [(30, 10), (35, 13), (38, 9), (31, 14), (36, 20), (29, 12)])
    # Eagle: the north airfield and a base, a port in the inlet
    m.put("2", 31, 2).puts("A", [(28, 1), (35, 1)]).put("B", 33, 2).put("P", 40, 3).puts("C", [(36, 6), (29, 6)])
    # ---- units ----
    # (the mission's reinforcement cells stay free: AIRFIELD, SOUTH_GATE, WEST_GATE and CAMP in es_act4.rs)
    m.reserve([(x, 0) for x in range(27, 35)] + [(32, 1), (33, 1)] + [(33, 13), (34, 13), (36, 13), (36, 14), (35, 15)]
              + [(27, 9), (28, 9), (26, 10), (28, 10), (27, 11), (28, 11)] + [(2, 19), (3, 19), (4, 19), (2, 20), (3, 20), (2, 21)])
    LAND_AVOID = "~r=-^IZ#"
    SEA_ONLY = ".fR^-=,IZ#HBCAPTbcap12345"
    # the legion's beachhead camp (south-west): foot at the front, armour on the roads, artillery and AA behind, the air wing at the airport
    m.spread(1, {INF: 3, MECH: 1}, (4, 13, 13, 20), seed=1, gap=0)
    m.spread(1, {TANK: 5, MDT: 3, NEO: 2}, (5, 15, 15, 22), seed=2, gap=0)
    m.spread(1, {RECON: 1}, (10, 17, 14, 21), seed=3, gap=1)
    m.spread(1, {ART: 2, ROCK: 2, MIS: 2, AA: 3}, (1, 15, 9, 22), seed=4, gap=0)
    m.spread(1, {INF: 2, MECH: 1}, (0, 13, 7, 19), seed=5, gap=0)
    m.spread(1, {FTR: 1, BCO: 1}, (6, 16, 14, 22), seed=6, gap=0, avoid=LAND_AVOID)
    # Eagle: the north airfield (air wing and its guards) and the pass
    m.spread(2, {FTR: 4, BMB: 2, BCO: 3}, (27, 0, 36, 3), seed=7, gap=0, avoid=LAND_AVOID)
    m.spread(2, {AA: 3, MIS: 2, INF: 3, MECH: 1}, (27, 1, 37, 7), seed=8, gap=0, prefer="fRC", hold=True)
    m.spread(2, {TANK: 3, MDT: 2, INF: 2, MECH: 1, ART: 1, RECON: 1}, (18, 3, 30, 10), seed=9, gap=0)
    m.spread(2, {CR: 2}, (39, 0, 43, 6), seed=10, gap=1, avoid=SEA_ONLY)
    # Hachi: the city (garrison), the river line and the coast road
    m.spread(3, {INF: 4, ART: 2, ROCK: 1, MIS: 1, AA: 1}, (28, 7, 38, 14), seed=11, gap=0, hold=True)
    m.spread(3, {INF: 4, MECH: 1, TANK: 3, MDT: 2, RECON: 1}, (19, 7, 27, 16), seed=12, gap=0)
    m.spread(3, {TANK: 2, MDT: 1, NEO: 1, INF: 4, MECH: 2, ART: 1, RECON: 1, AA: 1, ROCK: 1, APC: 1}, (20, 16, 36, 21), seed=13, gap=0)
    # ---- notes ----
    m.note("hq1", 4, 20, "the legion's HQ").note("hq2", 31, 2, "Eagle's HQ (north airfield)").note("hq3", 34, 10, "Hachi's HQ (the city)")
    m.note("gate_w", 26, 9, "the west gate (the valley road)").note("gate_n", 31, 4, "the north gate (the pass)").note("gate_s", 35, 15, "the south gate (the coast road)")
    m.note("camp", 8, 19, "the legion's beachhead camp; reinforcement cells at the cove").note("airfield", 31, 1, "Eagle's air wing reserve cells along y=0..1 x 27..36")
    m.note("volcano", 22, 14, "Mount Sol (x21..24, y12..15, its rock x20..25, y11..16): erupts on the ring (19..26, 10..17) from day 3")
    m.note("fwd", 16, 19, "neutral bases (16,19) by the weir track and (24,8) below the west gate")
    m.lake(15, 9, 9, seed=0, river_end=(15, 10))          # (a river starts in water or at the map edge: AW2 has no source tile)
    # (the user's rule, Oct 2026: 12% fewer neutral cities, the ones that add least; the middle, the objectives and MD01/MD02 kept)
    m.thinned = m.thin_neutral_cities(0.12, keep=())
    return m
