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
WON = list(range(1, 31))
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


GMAP = 0x0201E450
CURSOR = 0x030033E4


def focus_on(e, x, y, w=43, h=29):
    """The camera and the cursor on cell (x, y) (the game moves them on its own during the computer's turn; poked each frame)."""
    e.w16(GMAP + 4, max(0, min(w * 16 - 240, x * 16 - 120)))
    e.w16(GMAP + 6, max(0, min(h * 16 - 160, y * 16 - 80)))
    e.w16(CURSOR, x)
    e.w16(CURSOR + 2, y)


def truck_on_dock(g):
    g._units_base = g._players_base = None
    return next((u for u in g.units() if u["army"] == 2 and u["type"] == APC and DOCK[0] <= u["x"] <= 40 and 11 <= u["y"] <= 13), None)


def dock_pre(name):
    """The frame before DEFEAT: the camera on the dock, the truck on its tile with the info window (its HP) up."""
    return (name, truck_on_dock, lambda u: (u["x"], u["y"]))


def banner_picture(ctx, e, g, d, name, frames=60000, scene=False, pre=None):
    """Runs the end of the mission (A through its boxes) and photographs the DEFEAT or VICTORY banner when it is up. Returns the
    mission's result (1 won, 2 lost)."""
    n, shot, pre_done = 0, False, pre is None
    while n < frames:
        if not pre_done and (n % 4 == 0 or (len(pre) > 3 and pre[3])):
            what = pre[1](g)
            if what:
                x, y = pre[2](what)
                for _ in range(0 if len(pre) > 3 else 24):
                    focus_on(e, x, y)
                    e.wait(2)
                a5.pic(ctx, e, pre[0])
                pre_done = True
        if not shot and any(f == dc.MATCH_END_BANNER for _, _, f in g.procs()):
            e.wait(40)
            a5.pic(ctx, e, name)
            shot = True
        if scene and not shot and d.text_shown():
            e.wait(60)
            a5.pic(ctx, e, name)             # (a victory goes straight to the world map: the victory scene's first box is the proof on the battle screen)
            shot = True
        if not shot and e.u8(dc.LAST_RESULT) == 1:
            e.wait(30)
            a5.pic(ctx, e, name)             # (the victory's own screen: the banner proc differs)
            shot = True
        if shot and (d.world_map_up() or e.u8(dc.LAST_RESULT)) and n > 0:
            break
        if d.scripts_running() or d.text_shown() or n % 120 == 0:
            e.press("A", 4)               # (the scene's boxes)
        e.wait(1)
        n += 2
    if not shot:
        a5.pic(ctx, e, name)
    return e.u8(dc.LAST_RESULT)


def to_day(e, g, d, day):
    a5.to_day(e, g, d, day)
    g._units_base = g._players_base = None


def dock(ctx, e, g, d, t, near):
    """The truck is put a few cells from the dock on its own road (a test aid); the engine's march then drives it onto the
    dock tile on Sonja's turn, a real move by the game's own march (the mission is lost when the player's turn starts)."""
    d.place_unit(t, *near)
    g._units_base = g._players_base = None
    scout = next(u for u in g.units() if u["army"] == 1 and u["type"] == 6)        # a Black Hole Recon watches the dock (fog: else the truck is not seen)
    d.place_unit(scout, 35, 12)
    a5.end_turn(e, g, d)


def case(n, fn):
    def run(ctx):
        e, g, d = start(ctx)
        fn(ctx, e, g, d)
        e.close()
    run.__name__ = f"bh_m31_lose_test_{n}"
    test(modes=("ds",))(run)


def lose1a(ctx, e, g, d):
    t = trucks(g)[0]                                   # truck A
    dock(ctx, e, g, d, t, (37, 9))
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose1a", pre=dock_pre("m31_lose1a_pre")), 2, "truck A marches onto a dock tile: the mission is lost")


def lose1b(ctx, e, g, d):
    t = trucks(g)[1]                                   # truck B
    dock(ctx, e, g, d, t, (37, 15))
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose1b", pre=dock_pre("m31_lose1b_pre")), 2, "truck B marches onto a dock tile: the mission is lost")


def lose1c(ctx, e, g, d):
    to_day(e, g, d, 3)                                 # truck C is spawned on day 3
    ts = trucks(g)
    ctx.eq(len(ts), 3, "three trucks from day 3")
    c = next(u for u in ts if (u["x"], u["y"]) == (24, 11))
    dock(ctx, e, g, d, c, (37, 15))
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose1c", pre=dock_pre("m31_lose1c_pre")), 2, "truck C marches onto a dock tile: the mission is lost")


def lose2(ctx, e, g, d):
    # a damaged truck with an escort beside it, and one on 1 HP
    t = trucks(g)[0]
    a = g.unit_addr(t["id"]) + 4
    e.w16(a, (e.u16(a) & ~0x7F) | 10)                  # 1 HP
    esc = next(u for u in g.units() if u["army"] == 2 and u["type"] == 1)
    d.place_unit(esc, 36, 9)                           # an escort beside it
    dock(ctx, e, g, d, t, (37, 9))
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose2", pre=dock_pre("m31_lose2_pre")), 2, "a 1 HP truck with an escort marches onto a dock tile: the mission is lost")


def lose3(ctx, e, g, d):
    to_day(e, g, d, 3)
    ts = trucks(g)
    ctx.eq(len(ts), 3, "three trucks")
    d.remove_unit(ts[0]); d.remove_unit(ts[1])         # two destroyed (a test aid)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "two trucks gone and one alive: nothing is decided yet (no partial win)")
    dock(ctx, e, g, d, ts[2], (37, 15))
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose3", pre=dock_pre("m31_lose3_pre")), 2, "two trucks destroyed, the third docks: still a loss")


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
    e.wait(120)                                        # (the engine sees it alive for a few frames)
    d.remove_unit(ts[0])
    e.wait(120)
    mine = next(u for u in g.units() if u["army"] == 1 and u["type"] == 1)
    move(e, g, d, (mine["x"], mine["y"]), (mine["x"], mine["y"]))
    r = banner_picture(ctx, e, g, d, "m31_win4", scene=True)
    ctx.eq(r, 1, "all three trucks destroyed: victory")


STARTS = {65: (19, 5), 68: (19, 20), 104: (24, 11)}   # (the trucks' start cells, by unit id)


def lose5(ctx, e, g, d):
    # The trucks are put back on their start cells every turn (a test aid), so none marches to the dock before day 12 ends it.
    while e.u16(0x03004080) < 11:
        for t in trucks(g):
            if t["id"] in STARTS:
                d.place_unit(t, *STARTS[t["id"]])
        d0 = e.u16(0x03004080)
        a5.end_turn(e, g, d)
        for _ in range(4000):
            if e.u16(0x03004080) > d0 or e.u8(dc.LAST_RESULT):
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        a5.boxes(e, d, 3000)
        d.wait_control()
        g._units_base = g._players_base = None
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "day 11 started: still on")
    e.wait(60)
    a5.pic(ctx, e, "m31_lose5_pre")                        # (the day counter: "1 Day(s) Left")
    for t in trucks(g):
        if t["id"] in STARTS:
            d.place_unit(t, *STARTS[t["id"]])
    a5.end_turn(e, g, d)                                   # Black Hole ends day 11; Sonja's turn; day 12 starts
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose5"), 2, "day 12 starts: defeat")


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
    ctx.eq(banner_picture(ctx, e, g, d, "m31_lose6"), 2, "Black Hole's HQ captured: defeat")


for _n, _fn in [("1a", lose1a), ("1b", lose1b), ("1c", lose1c), ("2", lose2), ("3", lose3), ("4", win4), ("5", lose5), ("6", lose6)]:
    case(_n, _fn)


# --- difficulty (AW2TEST_ACT5B_BALANCE=1): a do-nothing run, the CPU as Black Hole, and chase bots (aw2test.bot) -------------------
BALANCE = os.environ.get("AW2TEST_ACT5B_BALANCE")


def _difficulty(how, seed=None):
    def fn(ctx):
        import json
        from aw2test.harness import Skip
        if not BALANCE:
            raise Skip("AW2TEST_ACT5B_BALANCE not set")
        if how == "cpu":
            mask = sum(1 << a5.M[k] for k in WON)
            e, g, d = a5.boot(ctx, mask, ROSTER, picks={a5.M[31]: 1}, at=a5.M[31])
            d.pick_mission()
            d.choose_cos(1, prefs=[bh.STURM])
            g._units_base = g._players_base = None
        else:
            e, g, d = start(ctx)
        seen = {}                                           # unit id -> [first day, last day, last cell]
        bhn = {}
        fast = {}
        adv = {}
        days = []

        def sample(msg=None):
            g._units_base = g._players_base = None
            day = e.u16(0x03004080)
            for u in g.units():
                if u["army"] == 2 and u["type"] == APC:
                    s = seen.setdefault(u["id"], [day, day, (u["x"], u["y"])])
                    s[1], s[2] = day, (u["x"], u["y"])
            bhn[day] = sum(1 for u in g.units() if u["army"] == 1)      # (the last look of the day)
            fast[day] = sorted((u["type"], u["x"], u["y"], u["hp"]) for u in g.units() if u["army"] == 1 and u["type"] in (6, 5, 19, 3, 8))
            adv[day] = sorted((u["type"], u["x"], u["y"]) for u in g.units() if u["army"] == 2 and u["type"] in (8, 5))
            days.append(msg)
        if how == "nothing":
            for _ in range(14):
                sample()
                d0 = e.u16(0x03004080)
                if e.u8(dc.LAST_RESULT):
                    break
                try:
                    a5.end_turn(e, g, d)
                    for _ in range(4000):
                        if e.u16(0x03004080) > d0 or e.u8(dc.LAST_RESULT):
                            break
                        if d.scripts_running():
                            e.press("A", 4)
                        e.wait(20)
                    a5.boxes(e, d, 3000)
                    d.wait_control()
                except Exception:
                    break
            r = {"result": e.u8(dc.LAST_RESULT), "day": e.u16(0x03004080)}
        else:
            from aw2test import bot as botmod

            class ChaseBot(botmod.Bot):
                """Every Black Hole unit makes for the nearest Vault Truck (the focused chase)."""
                def goals_for(self, u, army):
                    cells = [(t["x"], t["y"]) for t in self.g.units() if t["army"] == 2 and t["type"] == APC]
                    return cells or super().goals_for(u, army)
            opts = {"stance": "attack", "seed": seed}
            if how == "chase":
                botmod.Bot = ChaseBot
            r = d.autoplay(14, log=sample) if how == "cpu" else d.play(14, log=sample, **opts)
        r["trucks"] = {k: {"first_day": v[0], "last_day": v[1], "last_cell": v[2], "docked": 38 <= v[2][0] <= 40 and 11 <= v[2][1] <= 13} for k, v in seen.items()}
        r["bh_units_by_day"] = bhn
        r["sonja_advancers"] = {k: v for k, v in adv.items() if k in (1, 3, 5, 8)}
        r["bh_fast_units"] = {k: v for k, v in fast.items() if k in (2, 4, 6, 8)}
        ctx.log("DIFFICULTY " + how + " " + json.dumps(r, default=str))
        e.close()
    fn.__name__ = f"bh_m31_difficulty_{how}" + (f"_seed{seed}" if seed is not None else "")
    test(modes=("ds",))(fn)


for _how in ("nothing", "cpu", "chase"):
    _difficulty(_how)
_difficulty("chase", 1)
