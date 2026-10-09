"""M31 The Colonel's Vault: its end conditions in a real game (tango-gamesupport-aw2/src/bh_secret.rs). Sonja's army is played from
the pad too (a test aid: army 2's controller byte set to 1), so a truck's last step onto a dock tile is a real move. Each case
photographs the result (the DEFEAT or VICTORY banner)."""

import os

from aw2test import bhact5b as a5
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import ram
from aw2test.harness import test

APC = 7
DOCK = (38, 12)            # a dock tile (the dock's land is x 38..39, y 11..13)
BH_HQ = (3, 20)
WON = [22, 23, 24, 25, 26, 27, 28]
ROSTER = 0xFFF | (0x1FF << 12)


def start(ctx):
    mask = sum(1 << a5.M[k] for k in WON)
    e, g, d = a5.boot(ctx, mask, ROSTER, picks={a5.M[31]: 1}, at=a5.M[31])
    a5.open_mission(ctx, e, g, d, a5.M[31], [bh.STURM], "m31")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def trucks(g):
    g._units_base = g._players_base = None
    return [u for u in g.units() if u["army"] == 2 and u["type"] == APC]


def sonja_from_the_pad(e, g):
    e.w8(g.players_base + ram.PLAYER_SIZE * 2 + 0x1B, 1)


def to_sonjas_turn(e, g, d):
    a5.end_turn(e, g, d)
    for _ in range(400):
        if g.current_army() == 2 and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    d.wait_control()
    g._units_base = g._players_base = None


def move(e, g, d, frm, to, want="wait"):
    g.select(*frm)
    g.move_to(*to)
    names = g.menu()["names"]
    g.choose(next(n for n in names if n.lower().startswith(want)), g.ACTION_MENU)
    e.wait(20)


def result(e, d=None, frames=3000):
    for _ in range(frames // 20):
        if e.u8(dc.LAST_RESULT):
            break
        if d is not None and d.scripts_running():
            e.press("A", 4)          # (a scene on the way: the first truck's destruction, the end's own)
        e.wait(20)
    return e.u8(dc.LAST_RESULT)


def banner_picture(ctx, e, g, d, name, frames=40000):
    """The end banner (DEFEAT or VICTORY) photographed once it is up."""
    n = 0
    while n < frames:
        if any(f == dc.MATCH_END_BANNER for _, _, f in g.procs()):
            e.wait(40)
            a5.pic(ctx, e, name)
            return True
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
        n += 14
        if d.world_map_up():
            break
    a5.pic(ctx, e, name)
    return False


def to_day(e, g, d, day):
    a5.to_day(e, g, d, day)
    g._units_base = g._players_base = None


def dock(ctx, e, g, d, t, expect=2):
    """The truck is put one step from the dock (a test aid); its last step is a real move."""
    d.place_unit(t, DOCK[0] - 1, DOCK[1])
    move(e, g, d, (DOCK[0] - 1, DOCK[1]), DOCK)
    return result(e, d)


def case(n, fn):
    def run(ctx):
        e, g, d = start(ctx)
        fn(ctx, e, g, d)
        e.close()
    run.__name__ = f"bh_m31_lose_test_{n}"
    test(modes=("ds",))(run)


def lose1a(ctx, e, g, d):
    t = trucks(g)[0]                                   # truck A
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    r = dock(ctx, e, g, d, t)
    ctx.eq(r, 2, "truck A on a dock tile: the mission is lost")
    banner_picture(ctx, e, g, d, "m31_lose1a")


def lose1b(ctx, e, g, d):
    t = trucks(g)[1]                                   # truck B
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    ctx.eq(dock(ctx, e, g, d, t), 2, "truck B on a dock tile: the mission is lost")
    banner_picture(ctx, e, g, d, "m31_lose1b")


def lose1c(ctx, e, g, d):
    to_day(e, g, d, 3)                                 # truck C is spawned on day 3
    ts = trucks(g)
    ctx.eq(len(ts), 3, "three trucks from day 3")
    c = next(u for u in ts if (u["x"], u["y"]) == (24, 11))
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    ctx.eq(dock(ctx, e, g, d, c), 2, "truck C on a dock tile: the mission is lost")
    banner_picture(ctx, e, g, d, "m31_lose1c")


def lose2(ctx, e, g, d):
    # a damaged truck with an escort beside it, and one on 1 HP
    t = trucks(g)[0]
    a = g.unit_addr(t["id"]) + 4
    e.w16(a, (e.u16(a) & ~0x7F) | 10)                  # 1 HP
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    esc = next(u for u in g.units() if u["army"] == 2 and u["type"] == 1)
    d.place_unit(esc, DOCK[0] - 2, DOCK[1])            # an escort beside it
    ctx.eq(dock(ctx, e, g, d, t), 2, "a 1 HP truck with an escort on a dock tile: the mission is lost")
    banner_picture(ctx, e, g, d, "m31_lose2")


def lose3(ctx, e, g, d):
    to_day(e, g, d, 3)
    ts = trucks(g)
    ctx.eq(len(ts), 3, "three trucks")
    d.remove_unit(ts[0]); d.remove_unit(ts[1])         # two destroyed (a test aid)
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "two trucks gone and one alive: nothing is decided yet (no partial win)")
    ctx.eq(dock(ctx, e, g, d, ts[2]), 2, "two trucks destroyed, the third docks: still a loss")
    banner_picture(ctx, e, g, d, "m31_lose3")


def win4(ctx, e, g, d):
    # before truck C exists, killing A and B is not a win
    ts = trucks(g)
    d.remove_unit(ts[0]); d.remove_unit(ts[1])
    mine = next(u for u in g.units() if u["army"] == 1 and u["type"] == 1)
    move(e, g, d, (mine["x"], mine["y"]), (mine["x"], mine["y"]))      # an action: the rules look
    for _ in range(100):                                   # (the first truck's scene: A through it)
        if not d.scripts_running():
            break
        e.press("A", 4); e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "A and B destroyed on day 1: no victory before truck C has appeared")
    to_day(e, g, d, 3)
    ts = trucks(g)
    ctx.eq(len(ts), 1, "truck C appears on day 3")
    d.remove_unit(ts[0])
    mine = next(u for u in g.units() if u["army"] == 1 and u["type"] == 1)
    move(e, g, d, (mine["x"], mine["y"]), (mine["x"], mine["y"]))
    r = result(e, d)
    g._units_base = g._players_base = None
    ctx.log(f"after the last truck: result {r}, day {e.u16(0x03004080)}, enemy APCs {[(u['x'], u['y']) for u in g.units() if u['army'] == 2 and u['type'] == 7]}, scripts {d.scripts_running()}, procs {[hex(f) for _, _, f in g.procs()]}")
    ctx.eq(r, 1, "all three trucks destroyed: victory")
    banner_picture(ctx, e, g, d, "m31_win4")


def lose5(ctx, e, g, d):
    try:
        to_day(e, g, d, 12)
    except Exception:
        pass                                               # (the mission ends as day 12 starts)
    ctx.eq(result(e, d), 2, "day 12 starts: defeat")
    banner_picture(ctx, e, g, d, "m31_lose5")


def lose6(ctx, e, g, d):
    # a Yellow Comet Infantry captures Black Hole's HQ (two turns of capture)
    inf = next(u for u in g.units() if u["army"] == 2 and u["type"] == 1)
    sonja_from_the_pad(e, g)
    to_sonjas_turn(e, g, d)
    d.place_unit(inf, *BH_HQ)
    move(e, g, d, BH_HQ, BH_HQ, want="capt")
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "one turn of capture: not yet")
    a5.next_turn(e, g, d)
    to_sonjas_turn(e, g, d)
    move(e, g, d, BH_HQ, BH_HQ, want="capt")
    ctx.eq(result(e, d), 2, "Black Hole's HQ captured: defeat")
    banner_picture(ctx, e, g, d, "m31_lose6")


for _n, _fn in [("1a", lose1a), ("1b", lose1b), ("1c", lose1c), ("2", lose2), ("3", lose3), ("4", win4), ("5", lose5), ("6", lose6)]:
    case(_n, _fn)
