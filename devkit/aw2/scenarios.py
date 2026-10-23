"""Live scenarios: pad-op helpers and the turn lists of every scenario (ported from the old scen.py).

A scenario function takes `fog` ("on"/"off") and returns (pokes, turns): pokes are TANGOAW2_TEST_POKE rule lines that put units,
funds and meters on the map; turns is the global turn order, a list of (seat, ops) where ops are pad-script lines the seat plays in
its turn (an empty list ends the turn at once; a trailing "#yield" means the ops end the match, so no end-turn follows).
"""
import os, sys
from . import cfg

# ---- pad op helpers (lists of pad-script lines) ----
def goto(x, y): return [f"goto {x} {y} 40", "wait 10"]
def A(w=30): return ["press A 8", f"wait {w}"]
def Bk(w=20): return ["press B 8", f"wait {w}"]
def dn(k=1): return ["press DOWN 8", "wait 10"] * k
def sel_move(x, y, x2, y2, item=0, tail=90):
    return goto(x, y) + A(30) + goto(x2, y2) + A(60) + dn(item) + A(tail)
def build(x, y, item=0): return goto(x, y) + A(60) + dn(item) + A(60)
def power(cx, cy):
    return goto(cx, cy) + Bk() + A(80) + dn(2) + A(800)
def yield_(cx, cy):
    return (goto(cx, cy) if cx is not None else []) + A(40) + dn(2) + A(40) + dn(1) + A(200) + ["press LEFT 8", "wait 20"] + A(20)
def yield4(cx, cy):
    # Four Corners' Options menu opens on Yield (Delete is above it)
    return goto(cx, cy) + A(40) + dn(2) + A(40) + A(200) + ["press LEFT 8", "wait 20"] + A(20)


def mash(n=30):
    out = []
    for _ in range(n):
        out += ["press A 8", "press START 8", "press DOWN 8", "press SELECT 8", "press B 8"]
    return out


def skin_steps(k, default):
    """AW2DEV_SKIN=1: seat 0 picks Emerald Sun on the army page (its colour field: DOWN, then LEFT once from Orange Star, which wraps to the
    sixth choice, the skin); the others do `default`."""
    if os.environ.get("AW2DEV_SKIN") == "1" and k == 0:
        return ["press DOWN 8", "wait 10", "press LEFT 8", "wait 10"]
    return default


# ---- scenarios: pokes (test-aid lines), turns: list of (seat, ops) in order; fog-specific via function ----
def s_move(fog):
    pokes = [
        "when army=1 day=1 idle do unit 1 inf 5 3",
        "when army=1 day=1 idle do unit 1 inf 2 3",
        "when army=1 day=1 idle do unit 1 cruiser 3 13",
        "when army=1 day=1 idle do unit 2 inf 10 3",
        "when army=1 day=1 idle do unit 2 inf 9 11",
    ]
    turns = [
        (0, sel_move(2, 3, 3, 3) + sel_move(5, 3, 8, 3) + sel_move(3, 13, 9, 13)),
        (1, sel_move(10, 3, 9, 3, 1)),
        (0, sel_move(8, 3, 7, 3) + sel_move(9, 13, 5, 13)),
        (1, []),
    ]
    return pokes, turns


def s_capture(fog):
    pokes = ["when army=1 day=1 idle do unit 1 inf 5 3", "when army=1 day=1 idle do unit 2 inf 12 3"]
    turns = [
        (0, sel_move(5, 3, 5, 4, 0)),   # onto the neutral city, then Capture (the command menu's first item)
        (1, []),
        (0, goto(5, 4) + A(30) + A(60) + A(120)),  # select, confirm in place, then Capture (the command menu's first item)
        (1, []),
    ]
    return pokes, turns


def s_build(fog):
    pokes = ["when army=1 day=1 idle do funds 1 20000", "when army=1 day=1 idle do funds 2 20000"]
    turns = [
        (0, build(1, 6, 0)),
        (1, build(14, 6, 0)),
        (0, sel_move(1, 6, 2, 6, 0, 60) + build(1, 6, 1)),
        (1, []),
    ]
    return pokes, turns


def s_attack(fog):
    pokes = ["when army=1 day=1 idle do unit 1 inf 8 3", "when army=1 day=1 idle do unit 2 inf 10 3",
             "when army=1 day=1 idle do unit 2 inf 10 11"]
    turns = [
        (0, goto(8, 3) + A(30) + goto(9, 3) + A(60) + A(40) + A(300)),  # menu: Fire first, then the target
        (1, []),
        (0, []),
        (1, []),
    ]
    return pokes, turns


def s_power(fog):
    pokes = ["when army=1 day=1 idle do meter 1 100", "when army=2 day=1 idle do meter 2 100"]
    turns = [
        (0, power(8, 5)),
        (1, power(8, 5)),
        (0, []),
        (1, []),
    ]
    return pokes, turns


def s_swap(fog):
    # 2P with Dual Strike tag pairs: army 1 chooses Change (CO SWAP) from the map menu (CO, Intel, Options, Save, Change, End): the swap plays on
    # the mover's window and must show on the waiting window; army 2 does the same on its turn
    pokes = []
    slow = lambda k: ["press DOWN 8", "wait 24"] * k
    chg = goto(8, 5) + A(100) + slow(4) + A(60) + ["wait 500", "#yield"]
    return pokes, [(0, chg), (1, chg)]


def s_tagpower(fog):
    # the Tag Power (both meters full: the menu's Power, Super and Tag): choose Tag
    pokes = ["when army=1 day=1 idle do meter 1 400", "when army=1 day=1 idle do poke 0x0203F404 FFFF0000"]
    slow = lambda k: ["press DOWN 8", "wait 24"] * k
    tag = goto(8, 5) + A(100) + slow(4) + A(60) + ["wait 900", "#yield"]
    return pokes, [(0, tag)]


def s_super(fog):
    # a Super CO Power (meter full: the menu's CO, Intel, Power, Super): choose Super
    pokes = ["when army=1 day=1 idle do meter 1 400", "when army=2 day=1 idle do meter 2 400"]
    slow = lambda k: ["press DOWN 8", "wait 24"] * k
    sup = goto(8, 5) + A(100) + slow(3) + A(60) + ["wait 800"]
    return pokes, [(0, sup), (1, sup)]


def s_load(fog):
    pokes = ["when army=1 day=1 idle do unit 1 apc 6 3", "when army=1 day=1 idle do unit 1 inf 7 3",
             "when army=1 day=1 idle do unit 2 inf 10 3"]
    turns = [
        (0, sel_move(7, 3, 6, 3, 0)),                      # the infantry boards the APC (Load)
        (1, []),
        (0, sel_move(6, 3, 8, 3, 0, 60) + goto(7, 3) + A(60)),  # the APC drives, then Drop
        (1, []),
    ]
    return pokes, turns


def s_yield(fog):
    pokes = []
    turns = [(0, yield_(8, 5))]
    return pokes, turns


def s_mash(fog):
    pokes, turns = s_move(fog)
    return pokes, turns


def s_moveview(fog):
    pokes = [
        "when army=1 day=1 idle do unit 1 inf 5 3",
        "when army=1 day=1 idle do unit 1 inf 2 3",
        "when army=1 day=1 idle do unit 1 cruiser 3 13",
        "when army=1 day=1 idle do unit 2 inf 7 4",
        "when army=1 day=1 idle do unit 2 inf 4 5",
        "when army=1 day=1 idle do unit 2 copter 5 11",
        "when army=1 day=1 idle do unit 2 copter 9 11",
    ]
    turns = [
        (0, sel_move(5, 3, 8, 3) + sel_move(3, 13, 9, 13)),
        (1, []),
        (0, sel_move(8, 3, 6, 3) + sel_move(9, 13, 5, 13)),
        (1, []),
    ]
    return pokes, turns


def s_hq3(fog):
    # Pyramid Cape (3P): HQs army 1 (10,2), army 2 (2,14), army 3 (18,14). Army 2's infantry takes army 3's HQ over two turns,
    # then army 1 yields: army 2 wins.
    pokes = ["when army=1 day=1 idle do unit 2 inf 17 14"]
    turns = [
        (0, []),
        (1, sel_move(17, 14, 18, 14, 0)),
        (2, []),
        (0, []),
        (1, goto(18, 14) + A(30) + A(60) + A(120)),
        (0, yield_(8, 5)),
    ]
    return pokes, turns


def s_hq3k(fog):
    pokes = ["when army=1 day=1 idle do unit 2 inf 17 14"]
    turns = [
        (0, []), (1, sel_move(17, 14, 18, 14, 0)), (2, []), (0, []),
        (1, goto(18, 14) + A(30) + A(60) + A(120)),
        (0, []), (1, []), (0, []), (1, []), (0, []),
        (1, yield_(8, 5)),
    ]
    return pokes, turns


def s_hq3p(fog):
    # hq3 plus a CO power by army 1 on the first turn
    pokes = ["when army=1 day=1 idle do unit 2 inf 17 14", "when army=1 day=1 idle do meter 1 100"]
    turns = [
        (0, power(8, 5)),
        (1, sel_move(17, 14, 18, 14, 0)),
        (2, []),
        (0, []),
        (1, goto(18, 14) + A(30) + A(60) + A(120)),
        (0, yield_(8, 5)),
    ]
    return pokes, turns


def s_hq3h(fog):
    # Pyramid Cape (3P): army 2's infantry takes army 1's (the HOST's) HQ at (10,2) over two turns; then the room goes on
    # without army 1 (a host migration when seat 0 is killed): armies 3 and 2 play a round and army 3 yields, army 2 wins
    pokes = ["when army=1 day=1 idle do unit 2 inf 10 3"]
    turns = [
        (0, []), (1, sel_move(10, 3, 10, 2, 0)), (2, []), (0, []),
        (1, goto(10, 2) + A(30) + A(60) + A(120)),
        (2, []), (1, []), (2, []), (1, []), (2, yield_(8, 5)),
    ]
    return pokes, turns


def s_hq5h(fog):
    # 5P free-for-all: the HOST (army 1) yields on its first turn (out of the match); killed after that, armies 2-5 go on under
    # the new host for two rounds, then armies 2, 3 and 4 yield: army 5 wins
    y = yield_(None, None) + ["#yield"]
    turns = [(0, y), (1, []), (2, []), (3, []), (4, []), (1, []), (2, []), (3, []), (4, []),
             (1, y), (2, y), (3, y)]
    return [], turns


def s_hq3l(fog):
    # 3P, nobody eliminated: the HOST (army 1, alive) is killed; after the 60 s window the room goes on without it (host
    # migration, its army yielded by the console); armies 2 and 3 play on and army 3 yields: army 2 wins
    turns = [(0, []), (0, []), (1, []), (2, []), (1, []), (2, []), (1, []), (2, []), (1, []), (2, []), (1, []), (2, yield_(8, 5) + ["#yield"])]
    return [], turns


def capq(x, y, down=0):
    return goto(x, y) + A(30) + A(60) + dn(down) + A(400)


def s_hq4(fog):
    # Four Corners (4P), free for all: army 1's infantry takes army 3's HQ and army 2's takes army 4's, the cells read from the map in the ROM
    # (romtools.hq_cells; no cell is written down here). The capture points are poked to 15 so one turn takes it. Armies 3 and 4 are out before
    # their turns, so seats 2 and 3 have none; armies 1 and 2 play a second round.
    from . import romtools
    cells = romtools.hq_cells(romtools.map_id("Four Corners", 4))
    (x3, y3), (x4, y4) = cells[3], cells[4]
    pokes = [f"when army=1 day=1 idle do unit 1 inf {x3} {y3}", f"when army=1 day=1 idle do capture {x3} {y3} 15",
             f"when army=2 day=1 idle do unit 2 inf {x4} {y4}", f"when army=2 day=1 idle do capture {x4} {y4} 15"]
    turns = [(0, capq(x3, y3)), (1, capq(x4, y4)), (0, []), (1, [])]
    return pokes, turns


def s_dropb(fog):
    # the host waits for the box, looks at it, presses B (Disconnect); the guest idles until it is killed
    return [], [(0, ["until reconnect 120", "wait 120", "shot RUN/box_a.png", "wait 240", "shot RUN/box_b.png", "press B 8", "wait 120", "shot RUN/box_after.png", "log SCRIPT END"]), (1, [])]


def s_hq5(fog):
    pokes = ["when army=1 day=1 idle tick>=2300 do unit 1 inf 9 10", "when army=1 day=1 idle tick>=2300 do capture 9 10 15",
             "when army=3 day=1 idle do unit 3 inf 9 37", "when army=3 day=1 idle do capture 9 37 15",
             "when army=1 day=2 idle do unit 1 inf 9 29", "when army=1 day=2 idle do capture 9 29 15"]
    # (every army takes its turn in order; army 3 taking army 4's HQ at (9,37) eliminates army 4 (seen live). Army 1's capture at (9,10) of army 2's HQ has not been seen to eliminate it)
    turns = [(0, capq(9, 10, 1)), (1, []), (2, capq(9, 37, 1)), (4, []), (0, capq(9, 29, 1)), (1, []), (4, [])]   # (seat 3's army is out after army 3's capture: no turn for it; seat 2 has none in round 2: army 1's capture at (9,29) takes army 3's HQ, seen live)
    return pokes, turns


def s_big5(fog):
    # Pentagon Atoll (5P pre-deployed, the pack's): proposed by every seat (the room's `5P Predeploy` tab), then two rounds of end-turn. This is the regression
    # for the 5P Predeploy tab (a list-loop bound of 0xFF once made the pre-deployed tab unreachable). `big5attack` has each army's tank attack a neighbour.
    return [], [(k, []) for k in range(5)] * 2


def s_big5attack(fog):
    # Pentagon Atoll (5P predeployed): each army's first tank attacks a neighbour's infantry poked in beside it
    sys.path.insert(0, str(cfg.REPO / "tango-gamesupport-aw2" / "five"))
    import map as mappy
    rom = cfg.aw2_rom().read_bytes()
    mp = [m for m in mappy.parse(str(cfg.REPO / "tango-gamesupport-aw2" / "five" / "maps.txt")) if m["name"] == "Pentagon Atoll"][0]
    lz, units, (W, H), counts = mappy.build(mp, mappy.sea_edges(rom))
    army, mine, taken = 0, {}, set()
    for i in range(0, len(units), 12):
        r = units[i:i + 12]
        if r[0] == 0xFE: army = r[1]
        elif r[0] != 0xFF:
            mine.setdefault(army, []).append((r[0], r[1], r[2])); taken.add((r[0], r[1]))
    rows = mp["rows"]
    pokes, turns, spots = [], [], {}
    for a in range(1, 6):
        tx, ty = [(x, y) for (x, y, k) in mine[a] if k == 5][0]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            e = (tx + dx, ty + dy)
            if rows[e[1]][e[0]] in ".f" and e not in taken:
                break
        taken.add(e); spots[a] = ((tx, ty), e)
        foe = a % 5 + 1
        pokes.append(f"when army=1 day=1 idle do unit {foe} inf {e[0]} {e[1]}")
    for a in range(1, 6):
        (tx, ty), e = spots[a]
        turns.append((a - 1, goto(tx, ty) + A(30) + goto(*e) + A(60) + A(40) + A(300)))
    for a in range(1, 6):
        turns.append((a - 1, []))
    return pokes, turns


def s_hq3m(fog):
    # 3P (Pyramid Cape): as hq3h, the HOST's HQ is taken (it is out and is killed: host migration), the match plays to a
    # result (army 3 yields, army 2 wins); then the two that are left (seat 1 hosts) play a SECOND match from the same room
    pokes = ["when army=1 day=1 idle do unit 2 inf 10 3"]
    turns = [
        (0, []), (1, sel_move(10, 3, 10, 2, 0)), (2, []), (0, []),
        (1, goto(10, 2) + A(30) + A(60) + A(120)),
        (2, []), (1, []), (2, []), (1, []), (2, yield_(8, 5) + ["#yield"]),
    ]
    return pokes, turns


# second match of hq3m, by compact seat (0 the host, seat 1): armies 1 and 2; army 2 yields on its second turn
TURNS2 = {"hq3m": [(0, []), (1, []), (0, []), (1, yield_(8, 5) + ["#yield"]), (0, [])]}


def s_g4k(fog):
    # 4P (Four Corners), nobody out: seat 2 (army 3, alive) is killed -9 when its turn comes. After the 60 s window its army
    # yields (the console plays it) and the others go on; army 4 and army 2 yield: army 1 (the host) wins
    y = yield4(3, 3) + ["#yield"]
    turns = [(0, []), (1, []), (2, []), (3, []),
             (0, []), (1, []), (3, []),
             (0, []), (1, y), (3, y), (0, [])]
    return [], turns


def s_g2k(fog):
    # 2P: the guest (army 2, alive) is killed -9 when its turn comes: after 60 s its army yields and the host wins
    return [], [(0, []), (1, []), (0, []), (0, [])]


def s_g2i(fog):
    # 2P lobby: the host (army 1) idles in its own turn (never ends it) while the guest is killed -9: after 60 s the guest's army must
    # yield by itself, whoever holds the turn, and the host gets VICTORY!
    return [], [(0, ["wait 7000", "#yield"])]


def s_g2iv(fog):
    post = ["wait 90", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 600", "press A 8", "wait 600", "press A 8", "wait 900"]
    return [], [(0, ["until over 9000"] + post + ["#yield"])]


def s_g2hv(fog):
    post = ["wait 90", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 150", "press A 8", "wait 600", "press A 8", "wait 600", "press A 8", "wait 900"]
    return [], [(0, []), (1, ["until over 9000"] + post + ["#yield"])]


def s_g2h(fog):
    # 2P lobby: the HOST is killed -9 on the guest's turn: after 60 s the host's army yields and the guest (alone, it hosts) wins
    return [], [(0, []), (1, ["wait 7000", "#yield"])]


def s_g4s(fog):
    # 4P, nobody killed: seat 2 freezes for a while (STOP) and comes back: unchanged, the match goes on; seat 3 and 1 yield, army 1 wins
    y = yield4(3, 3) + ["#yield"]
    turns = [(0, []), (1, []), (2, []), (3, []),
             (0, []), (1, []), (2, []), (3, []),
             (0, []), (1, y), (2, y), (3, y), (0, [])]
    return [], turns


def s_p4k(fog):
    # 4P: seat 2 is killed -9 on the army page (before any battle). After 60 s it is gone from the room: the game is backed out to
    # SELECT MAP, the maps are proposed again by the three left (seats 0, 1, 3), then army select, rules and a 3P battle; armies 2 and 3 yield
    return [], [(0, []), (1, []), (2, []), (0, []), (1, yield_(8, 5) + ["#yield"]), (2, yield_(8, 5) + ["#yield"]), (0, [])]


TURNS2["p4k"] = [(0, []), (1, []), (2, []), (0, []), (1, yield_(8, 5) + ["#yield"]), (2, yield4(8, 5) + ["#yield"]), (0, [])]


def s_p2k(fog):
    # 2P: the guest is killed -9 on the army page: after 60 s the host is alone, and goes back to the lobby with the message
    return [], [(0, [])]


SCEN = {"swap": s_swap, "tagpower": s_tagpower, "super": s_super, "g2i": s_g2i, "g2iv": s_g2iv, "g2hv": s_g2hv, "g2h": s_g2h, "p4k": s_p4k, "p2k": s_p2k, "hq3m": s_hq3m, "g4k": s_g4k, "g2k": s_g2k, "g4s": s_g4s, "hq3p": s_hq3p, "dropb": s_dropb, "big5": s_big5, "big5attack": s_big5attack, "hq4": s_hq4, "hq5": s_hq5, "hq3k": s_hq3k, "hq3h": s_hq3h, "hq3l": s_hq3l, "hq5h": s_hq5h, "hq3": s_hq3, "moveview": s_moveview, "move": s_move, "capture": s_capture, "build": s_build, "attack": s_attack, "power": s_power,
        "load": s_load, "yield": s_yield, "mash": s_mash}



MAP_BY_NAME = {"hq4": ("Four Corners", 4)}   # scenarios written for one of the game's own maps: the pick walks to its row
BIG5_TAB = 1   # a 5P room has two tabs with the pack: "5P" and "5P Predeploy"; RIGHT once from the first shows the latter, whose first (only) map is Pentagon Atoll
BIG5_DOWN = 0


def parse_picks(s):
    """'0,3,5' -> [(0,0),(0,3),(0,5)] (DOWN presses from the first map); 't1:2' = one RIGHT (next tab), then two DOWN. None if s is empty."""
    if not s:
        return None
    out = []
    for p in s.split(","):
        tab, _, d = p.partition(":") if ":" in p else ("t0", ":", p)
        out.append((int(tab.lstrip("t") or 0), int(d or 0)))   # (a negative DOWN count presses UP: -1 = the last row)
    return out


WAIT_BOX = "until !reconnect 300"


def freeze_safe(lines):
    """Let a script ride out a frozen or dropped peer: the reconnect box (AW2's own hold box, cond `reconnect`) is up on the other seats, which must
    neither time out nor press into it. The app's macros (`endturn`, `onbanner`, `intro`) have short timeouts of their own, so they are expanded here
    (same steps as debug_aids.rs `expand_macros`, longer limits), and before every step that waits for the game or presses a key we wait until the
    box is gone (immediate when it is not there). Scripts that wait for the box themselves (`until reconnect`) are left alone."""
    out, n = [], 0

    def step(l):
        w = l.split()
        if w and w[0] in ("until", "seek", "press", "hold", "goto") and "reconnect" not in l and (not out or out[-1] != WAIT_BOX):
            out.append(WAIT_BOX)
        out.append(l)

    for l in lines:
        t = l.strip()
        if t == "endturn":
            n += 1
            for x in ["press B 6", "press B 6", "until acting 10"]:
                step(x)
            for _ in range(3):
                for x in ["until acting 30", "press A 8", "wait 20", "seek DOWN onend 30", "press A 8", "until !myturn 30", f"jumpif !myturn fet{n}", "press B 6", "press B 6", "press B 6"]:
                    step(x)
            out.append(f"label fet{n}")
        elif t == "onbanner":
            step("until banner 30")
            step("seek A !banner 30")
        elif t == "intro":
            n += 1
            for _ in range(15):
                out.append(f"jumpif mapup|over fin{n}")
                step("press A 8")
                out.append("wait 50")
            out.append(f"label fin{n}")
        else:
            step(l)
    return out


SEATS = {"p4k": 4, "p2k": 2, "hq3m": 3, "g4k": 4, "g4s": 4, "g2k": 2, "hq3p": 3, "hq3": 3, "hq3k": 3, "hq3h": 3, "hq3l": 3, "hq5h": 5, "hq4": 4,
         "hq5": 5, "big5": 5, "big5attack": 5}


def seats_of(name):
    return SEATS.get(name, 2)


# scenarios whose cue "KILL" is part of their story: a longer wait for each turn
class Pads:
    """The per-seat pad scripts of a scenario: the lobby prefix (create/join room, pick map in turn, teams, rules), the turn list, the tail."""

    def __init__(self, name, fog, run, killing=False, picks=None):
        self.picks = picks      # per-seat (tab presses, DOWN presses); None = the scenario's default
        self.name, self.fog, self.run = name, fog, str(run)
        self.n = seats_of(name)
        self.pokes, self.turns = SCEN[name](fog)
        self.mashing = name == "mash"
        self.part_steps = ["press DOWN 8", "wait 10", "press DOWN 8", "wait 10", "press RIGHT 8", "wait 10"] if name in ("swap", "tagpower") else None
        self.wait_turn = 170 if killing else 90
        # AW2DEV_SKIN=1: seat 0 picks Emerald Sun on the army page (the colour field, LEFT once from Orange Star wraps to the sixth choice)
        self.skin = os.environ.get("AW2DEV_SKIN") == "1"

    def teams_steps(self, k, default):
        if self.skin and k == 0 and not self.part_steps:
            return ["press DOWN 8", "wait 10", "press LEFT 8", "wait 10"]
        return self.part_steps or default

    def pick(self, k):
        # every seat picks at the same time, in private: its own SELECT MAP (each browses its own way), A when it has settled
        # (the draw between the seats' picks is random: scenarios coordinate on one map, so every seat proposes the same one, the first of the
        #  2P tab; big5 proposes the first 5P map from the 5P tab)
        if not self.picks and self.name in MAP_BY_NAME:
            from . import romtools
            nm, nn = MAP_BY_NAME[self.name]
            self.picks = [(0, romtools.pick_index(nm, nn))]    # (the room's list order differs with the pack: look the row up)
        tab, downs = (self.picks[k % len(self.picks)] if self.picks else ((BIG5_TAB, BIG5_DOWN) if self.name in ("big5", "big5attack") else (0, int(os.environ.get("AW2DEV_PICK_DOWN", "0")))))
        s = ["until selectmap 40", "until mypick 60", "wait 30"]
        s += ["press RIGHT 8", "wait 40"] * tab
        s += (["press DOWN 8", "wait 20"] * downs) if downs >= 0 else (["press UP 8", "wait 20"] * -downs)   # (the list does not wrap)
        s += ["press A 8", "until chosen 300", "wait 75"]
        return s

    def prefix(self, k, ready_only=False):
        n, fog = self.n, self.fog
        if k == 0:
            s = ["until level=1 30", "seek UP cursor=0 10", "press A 8", "until level=13 10", "press A 8", "until level=5 10", "press A 8", "until level=2 10",
                 f"until players={n} 40", f"until ready={n-1} 40", "press START 8", "session", *self.pick(0),
                 "until teams 60", "wait 40", *self.teams_steps(0, ["press RIGHT 8", "wait 10"]), "press A 8"]
            if ready_only:
                return s
            s += ["until rules 120", "wait 30"]
            if fog == "off":
                s += ["press DOWN 8", "wait 10"]
            s += ["press A 8", "until mapup 120"]
            return s
        return ["until level=1 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 10", "wait 30", "press A 8",
                "until level=5 15", "wait 20", "press A 8", "until status=3 40", "wait 30", "press A 8", "wait 30", "session",
                *self.pick(k), "until teams 60", "wait 40", *self.teams_steps(k, ["press LEFT 8", "wait 10"]), "press A 8"] + ([] if ready_only else ["until mapup 120"])

    def play(self, k, turns_, pre, done):
        """k's turns of a match: wait for each, take it (compact seat k)."""
        s = []
        for r, (seat, ops) in enumerate(turns_):
            if seat == k:
                s += [f"until banner|acting|over {self.wait_turn}", f"jumpif over {done}", f"jumpif !banner {pre}b{k}_{r}", "onbanner", f"label {pre}b{k}_{r}",
                      "until acting 30", "wait 30"] + (ops[:-1] if ops and ops[-1] == "#yield" else ops + ([] if self.n == 5 else goto(8, 5)) + ["endturn", f"log AFTER_TURN_{r}"])
            elif self.mashing and ops is not None:
                s += mash(12)   # the waiting seat leans on every key while the other seat plays its turn
        return s

    def second(self, k, order=(1, 2), first="seek A selectmap 200"):
        """The room's next match: the seats still there (`order`, the host first) from the result (or the back-out) to the next result."""
        c = list(order).index(k)
        s = [first, "wait 30", "until mypick 120", "wait 30", "press DOWN 8", "wait 20", "press A 8"]
        s += ["until chosen 200", "wait 75", "until teams 120", "wait 40", "press RIGHT 8" if c == 0 else "press LEFT 8", "wait 10", "press A 8"]
        if c == 0:
            s += ["until rules 120", "wait 30"] + (["press DOWN 8", "wait 10"] if self.fog == "off" else []) + ["press A 8"]
        s += ["until mapup 150"]
        s += self.play(c, TURNS2[self.name], "n2", f"done2_{k}")
        s += [f"label done2_{k}", "wait 200", "log SCRIPT END"]
        return s

    def body(self, k):
        name = self.name
        if name == "p4k" and k == 2:
            return self.prefix(k, True) + ["wait 3000"]
        if name == "p4k":
            return self.prefix(k, True) + self.second(k, (0, 1, 3), "until selectmap 200")
        if name == "p2k":
            return self.prefix(k, True) + ["wait 12000", "log SCRIPT END"]
        s = self.play(k, self.turns, "nb", f"done{k}")
        s += [f"label done{k}"]
        if name in TURNS2 and k in (1, 2):
            s += self.second(k)
        elif name in ("g4k", "g2k", "g4s"):
            # the results pages, then the room's next SELECT MAP (or the way back to the lobby when it fell to one player)
            s += ["seek A selectmap 90", "wait 900", "log SCRIPT END"]
        else:
            s += ["wait 120", "log SCRIPT END"]
        return s

    def pads(self):
        name = self.name
        if name == "dropb":
            return {0: self.prefix(0) + [l.replace("RUN", self.run) for l in self.turns[0][1]], 1: self.prefix(1) + ["wait 6000"]}   # (waits for the box itself)
        return {k: freeze_safe(self.body(k) if name in ("p4k", "p2k") else self.prefix(k) + self.body(k)) for k in range(self.n)}


# ---- the plain lobby flow (the old drive.py): N seats, ROUNDS of end-turn, the map picked in turn ----
MOVES = {0: ["DOWN"] * 3, 1: ["RIGHT", "DOWN"], 2: ["LEFT"] + ["DOWN"] * 5, 3: ["RIGHT", "DOWN"], 4: ["DOWN"] * 2}


def lobby_pads(n, rounds, run, fog="on", sim=False, pick_down=0, tab=0, no_pick=None, reveal=False, picks=None):
    run = str(run)

    def pick(k):
        if sim:
            # every seat picks at the same time, in private: shots of it before and after A
            s = ["until selectmap 40", "until mypick 60", "wait 40", f"shot {run}/priv_a_s{k}.png"]
            for m in (["DOWN"] * (k + 1) if k < 3 else ["RIGHT", "DOWN"]):
                s += [f"press {m} 8", "wait 14"]
            s += ["wait 30", f"shot {run}/priv_b_s{k}.png", "wait " + str(60 * k + 30), "press A 8", "wait 40", f"shot {run}/priv_c_s{k}.png", "until chosen 400", "wait 75", f"shot {run}/map_s{k}_chosen.png"]
            return s
        if picks:
            return private_pick(picks[k % len(picks)][1], picks[k % len(picks)][0])
        s = ["until selectmap 40"]
        for j in range(n):
            mv = MOVES[j] if rounds == 0 else ["DOWN"] * (j + 1)
            if pick_down:
                mv = ["DOWN"] * pick_down
            if tab:
                mv = ["RIGHT"] if (k == 0 and j == 0) else []
            if j == k:
                s += [f"until pickturn={j} 200", "wait 20"]
                for m in mv:
                    s += [f"press {m} {3 if pick_down else 8}", f"wait {2 if pick_down else 12}"]
                s += ["wait 20", f"shot {run}/map_s{k}_t{j}.png"]
                if str(k) != (str(no_pick) if no_pick is not None else ""):
                    s += ["press A 8"]
            else:
                s += [f"until pickturn={j} 300", f"wait {20 + (5 if pick_down else 20) * len(mv) + 10}", f"shot {run}/map_s{k}_t{j}.png"]
        if reveal:
            s += ["until chosen 200"]
            for i, w in enumerate([40, 50, 60, 60, 60, 150, 150]):
                s += [f"wait {w}", f"shot {run}/rv{i}_s{k}.png"]
            s += ["wait 75"]
        else:
            s += ["until chosen 200", "wait 75", f"shot {run}/map_s{k}_chosen.png"]
        return s

    def turns(k):
        s = []
        for r in range(rounds):
            s += ["until banner|acting|over 60", f"jumpif over done{k}", f"jumpif !banner nb{k}_{r}", "onbanner", f"label nb{k}_{r}", "until acting 20", "endturn"]
        s += [f"label done{k}", "log SCRIPT END"]
        return s

    host = ["until level=1 30", "seek UP cursor=0 10", "press A 8", "until level=13 10", "press A 8", "until level=5 10", "press A 8", "until level=2 10",
            f"until players={n} 40", f"until ready={n-1} 40", "press START 8", "session", *pick(0), "until teams 60", "wait 40", *skin_steps(0, ["press RIGHT 8", "wait 10"]), "press A 8", "intro"] + turns(0)

    def guest(k):
        return ["until level=1 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 10", "wait 30", "press A 8", "until level=5 15", "wait 20", "press A 8",
                "until status=3 40", "wait 30", "press A 8", "wait 30", "session", *pick(k), "until teams 60", "wait 40", *skin_steps(k, ["press LEFT 8", "wait 10"]), "press A 8"] + turns(k)
    return {0: freeze_safe(host), **{k: freeze_safe(guest(k)) for k in range(1, n)}}


# ---- UNRANKED: two seats find each other by matchmaking, each proposes in turn, army select, rules, two end-turns ----
UNR_PAD = ["until level=1 120", "wait 100", "press B 8", "until level=0 20", "seek UP cursor=0 10", "press A 8", "log searching for an opponent", "session",
           "until mypick 300", "wait 20", "press A 8", "until chosen 300", "wait 75", "until teams 120", "wait 90", "press A 8", "wait 120", "press A 8", "wait 120",
           "press A 8", "wait 200", "intro",
           "until banner|acting|over 60", "jumpif over d0", "jumpif !banner n0", "onbanner", "label n0", "until acting 20", "endturn",
           "until banner|acting|over 60", "jumpif over d0", "jumpif !banner n1", "onbanner", "label n1", "until acting 20", "endturn", "label d0", "log SCRIPT END"]


def unranked_pads(n):
    return {k: freeze_safe(UNR_PAD) for k in range(n)}


# ---- more flows (ported from the old rules_lobby.py, rules_unranked.py, browse_names.py, offline.py, lobbyentry.py) ----
def private_pick(downs=0, tab=0):
    """The private map pick (every seat at once): `tab` RIGHT presses, then `downs` DOWN presses, then A."""
    s = ["until selectmap 40", "until mypick 60", "wait 40"]
    s += ["press RIGHT 8", "wait 40"] * tab
    s += (["press DOWN 8", "wait 20"] * downs) if downs >= 0 else (["press UP 8", "wait 20"] * -downs)
    return s + ["press A 8", "until chosen 400", "wait 75"]


def lobby_prefix(n, k, pick):
    """Create (k = 0) or join the lobby room, wait for everyone, pick a map, teams page. Ends after the teams page's A."""
    if k == 0:
        return ["until level=1 30", "seek UP cursor=0 10", "press A 8", "until level=13 10", "press A 8", "until level=5 10", "press A 8", "until level=2 10",
                f"until players={n} 40", f"until ready={n-1} 40", "press START 8", "session", *pick, "until teams 60", "wait 40", *skin_steps(0, ["press RIGHT 8", "wait 10"]), "press A 8"]
    return ["until level=1 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 10", "wait 30", "press A 8", "until level=5 15", "wait 20", "press A 8",
            "until status=3 40", "wait 30", "press A 8", "wait 30", "session", *pick, "until teams 60", "wait 40", *skin_steps(k, ["press LEFT 8", "wait 10"]), "press A 8"]


def rules_lobby_pads(n, run):
    """The rules page in a lobby room: the host must be able to set the rules, the guest sees them read-only; nothing may skip the page."""
    def part(role):
        s = ["until rules 60", "log RULES UP", f"shot {run}/rules_{role}_a.png", "wait 200", f"shot {run}/rules_{role}_b.png", "jumpif !rules skipped" + role,
             "log RULES STILL UP AFTER 5 SECONDS"]
        if role == "host":
            s += ["press DOWN 8", "wait 30", f"shot {run}/rules_host_changed.png", "wait 120", "press A 8", "until battle 60", "log RULES CONFIRMED BY HOST"]
        else:
            s += ["wait 150", f"shot {run}/rules_guest_changed.png", "until battle 60", "log RULES CONFIRMED BY HOST"]
        return s + ["jump end" + role, "label skipped" + role, "log RULES SKIPPED", "label end" + role, "wait 120", "log SCRIPT END"]
    return {k: freeze_safe(lobby_prefix(n, k, private_pick()) + part("host" if k == 0 else "guest")) for k in range(n)}


def rules_unranked_pads(n, run):
    """UNRANKED: the standard rules page stays up and the match goes on by itself."""
    pad = ["until level=1 120", "wait 100", "press B 8", "until level=0 20", "seek UP cursor=0 10", "press A 8", "log searching for an opponent", "session",
           "until mypick 300", "wait 20", "press A 8", "until chosen 300", "wait 75", "until teams 120", "wait 90", "press A 8", "until rules 300", "log RULES UP",
           f"shot {run}/ur_0.png", "wait 50", f"shot {run}/ur_1.png", "wait 60", f"shot {run}/ur_2.png", "wait 60", f"shot {run}/ur_3.png", "wait 60", f"shot {run}/ur_4.png",
           "until battle 120", "log RULES AUTO-STARTED", "wait 200", "log SCRIPT END"]
    return {k: freeze_safe(pad) for k in range(n)}


def browse_pads(run, room="BIG_PENT_ROOM"):
    """Two clients: the HOST makes a room with a typed name (spaces in it), the GUEST sets a gamertag with a space and browses LOBBY > JOIN: the room is
    listed by its name; R refreshes (Refreshing..., Updated), a second R within five seconds shows the note without asking the relays again.
    Needs the PUBLIC lobby relays (Nostr): run it without --local, sparingly."""
    host = ["until level=1 120", "wait 60", "seek UP cursor=0 10", "press A 8", "until level=13 20", "wait 30", f"shot {run}/name_empty.png", f"type {room}", "wait 30",
            f"shot {run}/name_typed.png", "press A 8", "until level=5 20", "wait 20", "press A 8", "until level=2 20", "wait 60", f"shot {run}/room_page.png", "wait 3000", "log SCRIPT END"]
    guest = ["until level=1 120", "wait 60", "press SELECT 8", "until level=9 20", "wait 20", "type ANN_LEE", "wait 20", f"shot {run}/tag_typed.png", "press START 8",
             "until level=1 20", "wait 30", "seek DOWN cursor=1 10", "press A 8", "until level=7 20", "wait 600", f"shot {run}/browse_1.png", "press R 8", "wait 20",
             f"shot {run}/refreshing.png", "wait 150", f"shot {run}/updated.png", "press R 8", "wait 6", "press R 8", "wait 20", f"shot {run}/refreshing_again.png", "wait 200",
             f"shot {run}/updated_again.png", "wait 400", "press R 8", "wait 20", f"shot {run}/refreshing_late.png", "wait 200", f"shot {run}/updated_late.png", "wait 120",
             f"shot {run}/browse_end.png", "log SCRIPT END"]
    return {0: host, 1: guest}


SOLO_ENTRY = {
    "selectmap": ["wait 600", "press START 8", "wait 240", "press A 8", "wait 120", "press DOWN 8", "wait 40", "press A 8", "wait 120", "press A 8", "until selectmap 30", "wait 60"],
    "lobby": ["until level=1 120", "wait 150", "until cursor=1 5", "press A 8", "wait 60", "press A 8", "wait 40"],
    "title": [],
}


def solo_pads(entry, body, run):
    """One real window offline: get to `entry` (selectmap = offline Versus SELECT MAP, lobby = the LOBBY menu, title), then `body` (pad lines or a `;`-separated
    string; `shot NAME` writes <run>/NAME.png)."""
    lines = body.replace(";", "\n").split("\n") if isinstance(body, str) else list(body)
    pad = list(SOLO_ENTRY[entry]) + [("shot " + run + "/" + l.strip()[5:] + ".png") if l.strip().startswith("shot ") and "/" not in l else l.strip() for l in lines if l.strip()]
    return {0: pad + ["log SCRIPT END"]}
