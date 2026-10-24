"""M16 Sol Invictus (Act III finale): Port Aurelium, a citadel city on a cliff above a harbour. Three phases: the harbour and lower town, the three wall rings, the keep."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 36, 30


def build():
    m = Canvas("es16", W, H)
    m.header(armies=3, colours=(BM, OS, YC), team=[1, 2, 2], objective=[1], comment="M16 Sol Invictus (finale, Klaus + partner): capture Varro's HQ '2' (15,8) in the keep. Map 36x30. Armies: 1 player (BH colour), 2 Varro (OS stand-in, the keep, the walls, 4 bases 2 airports 3 quays 6 cities + 4 keep cities), 3 Praetorian Guard (YC stand-in, the east strip: 3 bases 1 airport 1 port 3 cities, HQ '3' (29,21)); six neutral cities in the lower town and a neutral port + city on the Lighthouse islet (28,27)/(30,26). Start forces. PLAYER (41): INF4 MECH4 TANK4 MDT3 NEO2 ART3 ROCK2 MIS2 AA3 RECON2 APC2 FTR2 BMB1 BCO2 CR2 SUB1 LAN1. VARRO (69): NEO4 MEGA2 MDT6 TANK4 RECON2 ART6 ROCK3 MIS2 AA4 INF8 MECH6 APC2 FTR3 BMB3 BCO2 BS2 CR3 SUB2 LAN2; hold: keep INF2 MECH1, gate guns ART6 ROCK3 MIS2 AA4, INF1 at (7,14), MECH1 at (22,14); everything else advances (armour on the south corridors and the lower town, aircraft at the airports (10,3) (19,3), fleet in the NE inlet). PRAETORIAN (31): NEO3 MDT4 TANK3 ART3 INF6 MECH4 AA2 FTR2 BCO1; hold ART3 AA2 INF3 MECH2 at the east gate and harbour, the rest advances. Geography: three phases. (1) Harbour and lower town y17..22 (rows between the moat y=23 and the outer ring), harbour bay x>=32. (2) Walls: mountain rings outer x4..25 y1..16 (gates W (4,13) S (13,16) E (25,9)), middle x8..21 y4..13 (gates W (8,6) S (17,13) E (21,11)), inner x11..18 y6..11 (gates W (11,9) S (12,11) E (18,8)); no two gates line up so every ring is a zigzag along 1-3 cell corridors. (3) Keep (12..17, 7..10) with HQ (15,8) and keep cities (13,7) (16,7) (13,10) (16,10). Moat: river y=23 from the west edge to the sea at (23,23); three single-lane bridges (2,23) west road, (13,23) causeway, (19,23) east. Lanes: west road x=2 to the west gate; causeway road x=13 to the south gate; east bridge to the main street y=20 and the east coast road x=26 to the east gate and Varro's quays; air lane from the NE airfield (29,9) and Varro's airports; sea lane from the player's port (22,26) up the east bay x>=32. Back route: quay road x=26 to the north rim y=0 and west to the west lane. Threat/answer: Neotanks/Megatanks/Md Tanks on the bridges -> the moat is the choke: Md Tanks, Neotanks, Artillery and Rockets behind it, Missiles/AA for the air; walls' Artillery/Rockets/Missiles (hold) -> Recons to find them, Bombers/Fighters from the airport (5,27), Infantry/Mechs over the mountains to the guns, own Artillery range, the three-ring zigzag lets Tanks shoot from outside; Fighters and Bombers from (10,3) (19,3) and (29,9) -> 3 AA + 2 Missiles + 2 Fighters, the player can build AA/Missiles/Fighters at 2 bases and the airport; Battleships/Cruisers shelling the east coast road -> Bombers and Subs, 2 Cruisers + Sub from the player's port, Lander landing at the east beach (shoal x=32 rows 12..18, sand x 27..31) or the islet (shoal x=27 rows 25..27, sand x 28..31) behind the fleet; Subs -> Cruisers; Landers/marines -> Cruisers, Tanks at the beach; Praetorian Neotanks on the east strip -> hold the east bridge, use Missiles/Artillery on the main street.'")
    # ---- sea: the east bay (x>=32), the north-east inlet (Varro's quays) and the south sea beside the player's camp ----
    m.rect("~", 32, 0, 35, 29).rect("~", 27, 0, 35, 5).rect("~", 23, 23, 35, 29)
    # ---- the moat: a river along y=23 from the west edge to the south sea (mouth at (23,23)), three bridges ----
    m.river([(0, 23), (22, 23)])
    m.bridge(2, 23).bridge(13, 23).bridge(19, 23)
    # ---- the three wall rings (mountains); gates are plain/road cells, never in line from ring to ring ----
    m.frame("^", 4, 1, 25, 16).frame("^", 8, 4, 21, 13).frame("^", 11, 6, 18, 11)
    gates = {"outer": [(4, 13), (13, 16), (25, 9)], "middle": [(8, 6), (17, 13), (21, 11)], "inner": [(11, 9), (12, 11), (18, 8)]}
    for g in gates.values():
        for x, y in g:
            m.put("R", x, y)
    # ---- roads ----
    m.line("R", [(2, 29), (2, 24)], over=".").line("R", [(2, 22), (2, 13), (4, 13)], over=".")          # west road to the west gate
    m.line("R", [(13, 29), (13, 24)], over=".").line("R", [(13, 22), (13, 16)], over=".")             # causeway road to the south gate
    m.line("R", [(19, 29), (19, 24)], over=".").line("R", [(19, 22), (19, 20)], over=".")            # east bridge road
    m.line("R", [(2, 20), (30, 20)], over=".")                                                       # the main street of the lower town
    m.line("R", [(26, 20), (26, 12), (25, 9)], over=".").line("R", [(26, 9), (26, 6)], over=".")      # the east coast road to the east gate and the quays
    m.line("R", [(26, 6), (26, 0)], over=".")                                                        # the quay road up to the rim
    m.line("R", [(5, 13), (7, 13), (7, 6), (8, 6)], over=".")                                        # inside the west gate
    m.line("R", [(13, 15), (17, 15), (17, 13)], over=".").line("R", [(17, 12), (12, 12), (12, 11)], over=".")  # zigzag from the south gate
    m.line("R", [(22, 9), (22, 11), (21, 11)], over=".").line("R", [(20, 11), (19, 11), (19, 8), (18, 8)], over=".")  # inside the east gate
    m.line("R", [(9, 6), (9, 9), (11, 9)], over=".")                                                 # inside the west gate of the keep
    m.line("R", [(5, 3), (24, 3)], over=".")                                                         # the rear road behind the wall
    m.line("R", [(4, 0), (25, 0)], over=".")                                                         # the north rim
    # ---- cover ----
    m.puts("f", [(4, 18), (5, 18), (4, 19), (8, 21), (9, 21), (9, 18), (10, 18), (16, 18), (17, 18), (16, 21), (22, 18), (23, 18), (23, 19)])
    m.puts("f", [(7, 25), (8, 25), (16, 25), (17, 25), (20, 27), (4, 27)])
    m.puts("f", [(28, 14), (28, 15), (30, 16), (29, 12)])
    m.puts("f", [(1, 17), (1, 18), (0, 8), (0, 9), (1, 4)])
    # ---- beaches ----
    m.rect(",", 23, 27, 23, 29)                       # player's beach (south camp coast): sand x 18..22 behind
    m.rect(",", 32, 12, 32, 18)                       # landing beach on the east coast: sand x 27..31 behind
    # ---- the Lighthouse islet in the south-east bay (a neutral port and city; a Lander's landing: shoal x=27, sand x 28..31) ----
    m.rect(".", 28, 25, 31, 27).rect(",", 27, 25, 27, 27)
    m.put("p", 28, 27).put("c", 30, 26).put("f", 31, 25).put("f", 31, 27)
    # ---- the player's camp (south, x0..22, y24..29) ----
    m.put("1", 11, 27).puts("B", [(8, 26), (15, 26)]).put("A", 5, 27).put("P", 22, 26)
    m.puts("C", [(3, 25), (17, 28), (9, 29)])
    # ---- the lower town: six neutral cities ----
    m.puts("c", [(5, 21), (8, 18), (11, 21), (16, 19), (21, 21), (22, 18)])
    # ---- Praetorian Guard: the east flank and the harbour ----
    m.put("3", 29, 21)
    m.puts("C", [(28, 11), (27, 19), (25, 22)])
    # ---- Varro: quays on the inlet, bases and airports around the second ring, keep cities ----
    m.put("2", 15, 8).puts("C", [(13, 7), (16, 7), (13, 10), (16, 10)])
    m.puts("P", [(26, 2), (28, 6)])
    m.puts("B", [(5, 7), (24, 6), (24, 12)]).puts("A", [(10, 3)])
    m.puts("C", [(6, 14), (22, 14), (6, 3), (23, 3), (22, 8), (10, 14)])
    # ---- places Varro / units ----
    taken = {(u["x"], u["y"]) for u in m.u}

    def spot(cx, cy, lo, hi, kinds, n=1):
        out = []
        for r in range(0, 16):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    x, y = cx + dx, cy + dy
                    if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and m.inside(x, y) and m.get(x, y) in kinds and (x, y) not in taken:
                        free = sum(1 for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if m.get(a, b) in kinds and (a, b) not in taken)
                        if free >= 1:
                            taken.add((x, y))
                            out.append((x, y))
                            if len(out) == n:
                                return out
        raise RuntimeError(f"no room near {cx},{cy}")

    def put(army, kind, cx, cy, n=1, lo=(0, 0), hi=(99, 99), kinds=".fR", **kw):
        for x, y in spot(cx, cy, lo, hi, kinds, n):
            m.unit(army, kind, x, y, **kw)

    sea = "~"
    # PLAYER (south camp)
    C = dict(lo=(0, 24), hi=(22, 29))
    put(1, TANK, 12, 25, 4, **C); put(1, MDT, 14, 25, 3, **C); put(1, NEO, 11, 25, 2, **C)
    put(1, INF, 4, 25, 3, **C); put(1, MECH, 3, 26, 3, **C)
    put(1, ART, 10, 27, 3, **C); put(1, ROCK, 8, 27, 2, **C); put(1, MIS, 14, 27, 2, **C)
    put(1, AA, 12, 27, 3, **C); put(1, RECON, 17, 25, 2, **C); put(1, APC, 9, 25, 1, **C)
    put(1, FTR, 5, 28, 2, **C); put(1, BMB, 6, 28, 1, **C); put(1, BCO, 4, 28, 1, **C)
    put(1, CR, 24, 25, 2, lo=(23, 24), hi=(28, 29), kinds=sea); put(1, SUB, 25, 27, 1, lo=(23, 24), hi=(28, 29), kinds=sea)
    put(1, LAN, 23, 26, 1, lo=(23, 24), hi=(28, 29), kinds=sea)
    # VARRO: the keep (hold)
    K = dict(lo=(12, 7), hi=(17, 10), hold=True)
    put(2, INF, 13, 8, 2, **K); put(2, MECH, 16, 9, 1, **K)
    # gate guns and walls (hold): artillery and rockets in the corridors behind the rings, missiles near the keep, AA at the gates
    put(2, ART, 6, 12, 1, lo=(5, 11), hi=(7, 14), hold=True); put(2, ART, 22, 12, 1, lo=(22, 10), hi=(24, 14), hold=True)
    pass
    pass
    put(2, ROCK, 7, 10, 1, lo=(6, 8), hi=(7, 12), hold=True)
    put(2, MIS, 14, 12, 1, lo=(10, 12), hi=(17, 12), hold=True); put(2, MIS, 20, 12, 1, lo=(19, 12), hi=(20, 12), hold=True)
    put(2, AA, 5, 14, 1, lo=(5, 12), hi=(7, 15), hold=True); put(2, AA, 13, 15, 1, lo=(12, 14), hi=(14, 15), hold=True)
    put(2, AA, 18, 12, 1, lo=(17, 12), hi=(19, 12), hold=True)
    # the rest of the foot soldiers (hold) behind the gates, the others advance
    pass
    # advancing: infantry and mechs in the lower town, armour on the roads
    put(2, INF, 4, 21, 1, lo=(0, 17), hi=(12, 22)); put(2, MECH, 14, 21, 1, lo=(5, 17), hi=(22, 22)); put(2, INF, 10, 20, 1, lo=(5, 17), hi=(22, 22))
    pass
    put(2, TANK, 2, 17, 1, lo=(0, 14), hi=(3, 22)); put(2, TANK, 14, 18, 1, lo=(10, 17), hi=(22, 22))
    put(2, MDT, 3, 15, 1, lo=(0, 12), hi=(3, 22)); put(2, MDT, 8, 15, 1, lo=(5, 14), hi=(15, 15))
    put(2, NEO, 5, 14, 1, lo=(5, 12), hi=(7, 15)); put(2, NEO, 15, 15, 1, lo=(13, 14), hi=(20, 15))
    put(2, MEGA, 9, 14, 1, lo=(8, 14), hi=(12, 15))
    put(2, RECON, 15, 18, 1, lo=(10, 17), hi=(22, 22))
    put(2, FTR, 10, 2, 1, lo=(8, 2), hi=(21, 3)); put(2, BMB, 19, 2, 1, lo=(8, 2), hi=(21, 3))
    S = dict(kinds=sea, lo=(27, 0), hi=(35, 11))
    put(2, BS, 30, 3, 1, **S); put(2, CR, 29, 1, 2, **S)
    # PRAETORIAN GUARD: gate guns hold at the east gate and the harbour, the strike force advances
    E = dict(lo=(26, 6), hi=(31, 22))
    put(3, ART, 27, 9, 1, hold=True, **E); put(3, ART, 29, 13, 1, hold=True, **E)
    put(3, AA, 28, 8, 1, hold=True, **E); put(3, AA, 30, 14, 1, hold=True, **E)
    put(3, INF, 30, 11, 3, hold=True, **E); put(3, INF, 29, 20, 3, **E)
    put(3, MECH, 27, 15, 2, hold=True, **E); put(3, MECH, 27, 18, 2, **E)
    put(3, NEO, 27, 21, 1, **E); put(3, MDT, 28, 17, 2, **E); put(3, TANK, 26, 14, 2, **E)
    put(3, FTR, 29, 10, 2, lo=(26, 7), hi=(31, 10)); put(3, BCO, 27, 7, 1, lo=(26, 6), hi=(31, 8))
    # ---- notes ----
    m.note("hq1", 11, 27, "the player's HQ").note("hq2", 15, 8, "Varro's HQ in the keep: the victory (capture)").note("hq3", 29, 21, "the Praetorian Guard's HQ (east flank)")
    m.note("player_port", 22, 26, "the player's port on the south bay (sea beside it at x=23)")
    m.note("player_airport", 5, 27, "the player's airport (Fighters, Bombers)")
    for k, (x, y) in enumerate([(3, 24), (12, 24), (15, 24), (20, 24), (7, 24), (18, 27)], 1):
        pass
    m.note("bridge_w", 2, 23, "moat bridge 1, west road (single lane)").note("bridge_c", 13, 23, "moat bridge 2, the causeway to the south gate")
    m.note("bridge_e", 19, 23, "moat bridge 3, east bridge (to the main street and the east coast road)")
    m.note("moat", 0, 23, "river y=23 from x=0 to the south sea at (23,23)")
    for ring, gl in gates.items():
        for i, (x, y) in enumerate(gl, 1):
            m.note(f"gate_{ring}{i}", x, y, f"{ring} ring gate {i}")
    m.note("ring_outer", 4, 1, "outer ring mountains x4..25, y1..16; gates (4,13) west, (13,16) south, (25,9) east")
    m.note("ring_middle", 8, 4, "middle ring x8..21, y4..13; gates (8,6) west, (17,13) south, (21,11) east")
    m.note("ring_inner", 11, 6, "inner ring (the keep wall) x11..18, y6..11; gates (11,9) west, (12,11) south, (18,8) east")
    m.note("phase1_a", 0, 17, "PHASE 1 harbour and lower town rectangle: corners (0,17) and (31,22) (the moat is y=23)")
    m.note("phase1_b", 31, 22, "phase 1 rectangle opposite corner (the east beach is x=32, rows 12..18; the harbour bay x>=32)")
    m.note("phase2_a", 4, 1, "PHASE 2 the walls: rectangle (4,1) to (25,16) (the outer ring)")
    m.note("phase2_b", 25, 16, "phase 2 rectangle opposite corner")
    m.note("phase3_a", 11, 6, "PHASE 3 the keep: rectangle (11,6) to (18,11) (inner ring walls)")
    m.note("phase3_b", 18, 11, "phase 3 rectangle opposite corner")
    m.note("keep_cities", 13, 7, "keep cities (13,7) (16,7) (13,10) (16,10): Varro's repair lane around HQ (15,8)")
    m.note("airport2a", 10, 3, "Varro's airport (north corridor)").note("airport2b", 19, 3, "Varro's second airport")
    m.note("airport3", 29, 9, "the Praetorian airfield (north-east of the east strip)")
    m.note("varro_bases", 5, 7, "Varro's bases (5,7) (5,10) west corridor, (24,6) (24,12) east corridor")
    m.note("varro_ports", 26, 2, "Varro's quays on the inlet: (26,2) (26,4) (28,6); the Praetorian port is (31,11)")
    m.note("praetorian_bases", 27, 13, "Praetorian bases (27,13) (28,16) (30,18)")
    m.note("beach_e", 32, 12, "east landing beach: shoal x=32 rows 12..18, sand x 27..31 behind")
    m.note("islet", 28, 25, "the Lighthouse islet x28..31, y25..27: neutral port (28,27), city (30,26); shoal x=27 rows 25..27; the Landers' landing")
    m.note("beach_s", 23, 27, "player's own beach: shoal x=23 rows 27..29, sand x 18..22 behind")
    m.note("west_road", 2, 22, "west road (a): bridge (2,23), then x=2 north to the west gate (4,13)")
    m.note("east_coast_road", 26, 20, "east coast road (c): main street y=20, then x=26 north to the east gate (25,9) and the quays")
    m.note("rim_route", 26, 0, "back route: quay road x=26 north to the rim road y=0 which runs west to the west lane (x 0..3)")
    for i, (x, y) in enumerate([(5, 0), (7, 0), (9, 0), (11, 0), (13, 0), (15, 0), (17, 0), (19, 0), (21, 0), (23, 0)], 1):
        m.note(f"varro_reinf{i}", x, y, "Varro reinforcement cell (north rim, ground)")
    for i, (x, y) in enumerate([(30, 1), (31, 3), (30, 5)], 1):
        m.note(f"varro_ship{i}", x, y, "Varro reinforcement cell for a ship (inlet sea)")
    for i, (x, y) in enumerate([(7, 25), (9, 24), (17, 26), (16, 25), (6, 29), (18, 29)], 1):
        m.note(f"player_reinf{i}", x, y, "player reinforcement cell (south camp)")
    return m
