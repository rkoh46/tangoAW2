"""The War Room's (and Survival's) CO screen, for the tests that look at which
COs it offers and play a map with one of them (tests/test_all_cos.py).

The screen (`ProcScr_CoSelect`, 0x08616638): the CO list at 0x030058E0 in the
country groups' order, each group's size at 0x03005948; DOWN steps to the next
country group (proc +0x58, its offset in the list +0x5C), RIGHT to the next CO in it (+0x52)."""

from . import rom as romlib
from . import saves
from . import survival as sv
from .game import NavError

CO_LIST = 0x030058E0
CO_GROUPS = 0x03005944
CO_SIZES = 0x03005948
CO_SELECT = 0x08616638
CO_SELECT_IDLE = 0x0807CE5D
PROCS = (0x0200D610, 0x0200E418)
GAME_MODE = 0x03003FC1
# The War Room's records: 0x0200C078, 0x14 a map (id - 0x6C), five records of
# four bytes: the CO, then a 12-bit score and a 12-bit rank/score field.
RECORDS = 0x0200C078
ROW = 0x14


def lists(e):
    """The CO screen's groups: [[CO ids]] in the order shown."""
    n = e.u32(CO_GROUPS)
    sizes = [e.u8(CO_SIZES + k) for k in range(min(n, 16))]
    ids = list(e.read(CO_LIST, sum(sizes)))
    out, at = [], 0
    for s in sizes:
        out.append(ids[at:at + s])
        at += s
    return out


def flat(e):
    return [c for g in lists(e) for c in g]


def names(cos):
    return [romlib.co_name(c) for c in cos]


def proc(e):
    lo, hi = PROCS
    for p in range(lo, hi, 0x6C):
        if e.u32(p) == CO_SELECT and e.u32(p + 0x10) == CO_SELECT_IDLE:
            return p
    return None


def highlighted(e):
    """(group, CO id) the CO screen is on, or None while it is not at its input."""
    p = proc(e)
    if p is None:
        return None
    group = e.u32(p + 0x58)
    size = max(e.u8(CO_SIZES + min(group, 15)), 1)
    k = e.u16(p + 0x52) % size + e.u32(p + 0x5C)
    return group, e.u8(CO_LIST + min(k, 63))


def open_war_room(e):
    """Boot -> Select Mode -> War Room -> New -> SELECT MAP -> its first map -> the
    CO screen at its input."""
    saves.to_select_mode(e)
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 1)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), 600, step=10):
        raise NavError("the War Room's SELECT MAP did not open")
    e.wait(90)
    e.press("A", 8)
    if not e.wait_until(lambda: proc(e) is not None, 900, step=10):
        raise NavError("the War Room's CO screen did not open")
    e.wait(60)


def open_survival(e):
    """Boot -> Select Mode -> Survival -> its first course -> the CO screen."""
    if not sv.open_survival(e):
        raise NavError("Survival's SELECT MAP did not open")
    e.press("A", 8)
    if not e.wait_until(lambda: proc(e) is not None, 900, step=10):
        raise NavError("Survival's CO screen did not open")
    e.wait(60)


def go_to(e, co):
    """Move the CO screen's highlight to `co`."""
    groups = lists(e)
    want = next((i for i, g in enumerate(groups) if co in g), None)
    if want is None:
        raise NavError(f"CO {co} is not on the CO screen ({[names(g) for g in groups]})")
    for _ in range(len(groups) * 3):
        cur = highlighted(e)
        if cur is not None and cur[0] == want:
            break
        e.press("DOWN", 6)
        e.wait_until(lambda: highlighted(e) is not None and highlighted(e)[0] != (cur or (None,))[0], 120, step=4)
        e.wait(30)
    for _ in range(len(groups[want]) * 3):
        cur = highlighted(e)
        if cur and cur[1] == co:
            e.wait(30)
            return
        e.press("RIGHT", 6)
        e.wait_until(lambda: highlighted(e) is not None and highlighted(e)[1] != (cur or (0, None))[1], 120, step=4)
        e.wait(30)
    raise NavError(f"CO {co} not reached (on {highlighted(e)})")


def start_battle(e, g):
    """A on the CO, A on LET'S GO, until the battle waits for the pad."""
    e.press("A", 8)
    e.wait(100)
    for _ in range(80):
        if e.u32(0x03000000) == 0x08022049:
            break
        e.press("A", 8)
        e.wait(20)
    if not e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=20):
        raise NavError("the battle did not start")
    g._units_base = g._players_base = None
    g.wait_for_input()


def record_row(e, map_id):
    """A map's five War Room records as (CO, score12, rank12) from the profile in RAM."""
    b = e.read(RECORDS + ROW * (map_id - 0x6C), ROW)
    out = []
    for k in range(5):
        v = int.from_bytes(b[4 * k:4 * k + 4], "little")
        out.append((v & 0xFF, (v >> 8) & 0xFFF, v >> 20))
    return out


PLAYERS = 0x08499598
P_YIELD = 0x31


def win_map(e, g):
    """Every computer army yields, End turn: the map is won, then A through the
    results and the War Room's save until SELECT MAP is back."""
    base = e.u32(PLAYERS)
    for a in range(2, 5):
        if e.u8(base + 0x3C * a + 0x1B):
            e.w8(base + 0x3C * a + P_YIELD, 1)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    if not sv.to_select_map(e):
        raise NavError("SELECT MAP did not come back")


def rows(e):
    """Every map's raw record row from the profile in RAM: {map id: 20 bytes} for the played ones."""
    b = e.read(RECORDS, 30 * ROW)
    return {0x6C + k: b[ROW * k:ROW * (k + 1)] for k in range(30) if any(b[ROW * k:ROW * (k + 1)])}
