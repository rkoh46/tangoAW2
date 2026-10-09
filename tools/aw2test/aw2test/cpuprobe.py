"""The CPU audit: every BH Campaign mission entered with the player passive, the enemy's units, properties,
funds and new units snapshotted at each of the player's turn starts (aw2test tests/test_bh_cpuai.py)."""

import json
import os
import shutil

from . import bhact2 as a2
from . import bhcampaign as bh
from . import dscampaign as dc
from . import paths
from .bot import BASE, AIRPORT, PORT, PROPERTIES, CLASSES, ROWS, MAP, PLAYERS_PTR
from .emu import Emu
from .game import Game

S, VB, HK = bh.STURM, bh.VON_BOLT, bh.HAWKE
BONDS = 0x1FF << 12
# number: (roster bits unlocked, CO picks)  (tests/test_bh_review.py's matrix)
M = {
    1: (0b1, []), 2: (0b11, [S]), 3: (0b11, []), 4: (0b11, []), 5: (0b111, [S]), 6: (0b111, [S]), 7: (0b111, []),
    8: (0b111, [S, HK]), 9: (0b111, []), 10: (0b111, []), 11: (0b111, []), 12: (0b111, [S, HK]), 13: (0b1111, [S]),
    14: (0b11111, [S]), 15: (0b11111, [S, HK]), 16: (0b11111, []), 17: (0b11111, [S, HK]), 18: (0b111111, [S]),
    19: (0b111111, [S]), 20: (0b111, [S, HK]), 21: (0b1111111, [S]), 22: (0b111, []), 23: (0x7F | BONDS, [S, HK]),
    24: (0xFF | BONDS, [S, HK]), 25: (0xFF | BONDS, [S, HK]), 26: (0x1FF | BONDS, [S, VB]), 27: (0x1FF | BONDS, []),
    28: (0x3FF | BONDS, [S, bh.CLONE_ANDY]), 29: (0x3FF, [S]), 30: (0x3FF, [bh.CLONE_ANDY]), 31: (0xFFF | BONDS, [S]),
}
FRONT2 = {8, 15, 20, 25}
DAYADDR = 0x03004080
PRODUCES = (BASE, AIRPORT, PORT)


def enter(ctx, n):
    roster, picks = M[n]
    env = None
    mask = (1 << (n - 1)) - 1
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = {n - 1: len(picks)}
    a2.start_at(e, d, mask, roster, n - 1)
    d.wait_world_map()
    if picks:
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}", setup_only=True)
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", ())
        d.wait_control()
    else:
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}")
        stable = 0
        for _ in range(3000):
            stable = stable + 1 if g.current_army() == (5 if n == 28 else 1) and not d.scripts_running() else 0
            if stable >= 5:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        d.wait_control()
        for _ in range(6):
            e.wait(150)
            if d.scripts_running():
                d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def all_units(e, g):
    """Every live unit (g.units() with the review test's slot rule: a five-army battle has 51 slots an army, flagged 1 or 2)."""
    from . import ram
    from .game import parse_unit
    per = 51 if e.u8(0x02030206) in (1, 2) else 64
    raw = e.read(g.units_base, ram.UNIT_SIZE * 256)
    return [parse_unit(uid, raw[ram.UNIT_SIZE * uid:ram.UNIT_SIZE * (uid + 1)], per) for uid in range(256)
            if raw[ram.UNIT_SIZE * uid] != 0 and uid % per != 0]


def snapshot(e, g, me):
    """The state now: units by id (army, type, x, y, hp, role), properties {cell: (kind, owner)}, funds, teams."""
    w, h = e.u16(MAP), e.u16(MAP + 2)
    props = {}
    for y in range(h):
        row = e.u16(ROWS + 2 * y)
        r = e.read(CLASSES + row, w)
        for x in range(w):
            if r[x] & 0x1F in PROPERTIES:
                props[(x, y)] = (r[x] & 0x1F, r[x] >> 5)
    pl = e.u32(PLAYERS_PTR)
    funds = {a: e.u32(pl + 0x3C * a) for a in range(1, 6)}
    team = {a: e.u8(pl + 0x3C * a + 0x2A) for a in range(1, 6)}
    units = {u["id"]: dict(army=u["army"], type=u["type"], x=u["x"], y=u["y"], hp=u["hp"], role=u["raw"][11],
                           on=bool(u["flags"] & 0x08)) for u in all_units(e, g)}
    return dict(day=e.u16(DAYADDR), props=props, funds=funds, team=team, units=units)


def other_front(ctx, e, g, d, n):
    """A snapshot of the other front (Map menu > Front), or None."""
    from . import twofront as tf
    try:
        if not tf.look_at_other_front(e, g):
            return None
        g._units_base = g._players_base = None
        s = snapshot(e, g, 1)
        tf.come_back(e, g)
        g._units_base = g._players_base = None
        return s
    except Exception as ex:
        ctx.log(f"M{n}: the other front could not be read: {ex}")
        try:
            tf.come_back(e, g)
        except Exception:
            pass
        return None


def run(ctx, n, days=6, shots=None):
    """Passive player: snapshots at the player's turn start of days 1..`days`. Returns (emu, game, driver, the player's army,
    the main front's snapshots, the other front's)."""
    e, g, d = enter(ctx, n)
    me = 5 if n == 28 else 1
    snaps = [snapshot(e, g, me)]
    front = [other_front(ctx, e, g, d, n)] if n in FRONT2 else []
    if shots and 1 in shots:
        whole_map(ctx, e, g, d, n, f"m{n}_day1")
    if os.environ.get("AW2TEST_CPUAI_RAW"):
        for u in all_units(e, g)[:60:3]:
            ctx.log(f"raw unit {u['id']} army {u['army']} type {u['type']} at {u['x']},{u['y']}: {u['raw'].hex()}")
    for day in range(2, days + 1):
        if e.u8(dc.LAST_RESULT):
            break
        ok = False
        for attempt in range(6):
            try:
                a2.to_day(e, g, d, day)
                ok = True
                break
            except Exception as ex:       # (a dialogue in the way: A through it and retry; or the mission ended)
                if e.u8(dc.LAST_RESULT):
                    break
                ctx.log(f"M{n}: day {day} attempt {attempt}: {ex}")
                a2.boxes(e, d, 1500)
                try:
                    d.wait_control()
                except Exception:
                    pass
        if not ok:
            ctx.log(f"M{n}: stopped before day {day}")
            break
        if e.u8(dc.LAST_RESULT):
            break
        snaps.append(snapshot(e, g, me))
        if n in FRONT2:
            front.append(other_front(ctx, e, g, d, n))
        if shots and day in shots:
            whole_map(ctx, e, g, d, n, f"m{n}_day{day}")
    return e, g, d, me, snaps, [f for f in front if f]


class _Quiet:
    def __init__(self, c):
        self.c = c

    def __getattr__(self, k):
        return getattr(self.c, k)

    def check(self, ok, msg):
        return None


def whole_map(ctx, e, g, d, n, name):
    """The whole map as one picture (stitch), kept in the test's output and, with AW2TEST_CPUAI_SHOTS, in that folder (2x)."""
    import shutil
    from . import stitch
    w, h = d.size()
    for _ in range(6):
        try:
            g.goto(0, 0)
            break
        except Exception:
            e.wait(150)
    path = stitch.stitch(_Quiet(ctx), g, name, w, h)
    out = os.environ.get("AW2TEST_CPUAI_SHOTS")
    if path and out:
        os.makedirs(out, exist_ok=True)
        try:
            from PIL import Image
            im = Image.open(path)
            im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(out, name + ".png"))
        except ImportError:
            shutil.copy(path, os.path.join(out, name + ".png"))
    return path


def analyse(n, me, snaps):
    """What the enemy did: dict of numbers (units, moved, captures, builds, funds)."""
    s0 = snaps[0]
    foes = {a for a in range(1, 6) if a != me and s0["team"][a] != s0["team"][me]}
    first = {i: u for i, u in s0["units"].items() if u["army"] in foes}
    last = snaps[-1]
    moved3 = set()
    for s in snaps:
        if s["day"] - s0["day"] <= 3:
            moved3 |= {i for i, u in s["units"].items() if i in first and (u["x"], u["y"]) != (first[i]["x"], first[i]["y"])}
    ever = set()
    for s in snaps[1:]:
        ever |= {i for i, u in s["units"].items() if i in first and (u["x"], u["y"]) != (first[i]["x"], first[i]["y"])}
    caps = []
    for a, b in zip(snaps, snaps[1:]):
        for c, (k, o) in b["props"].items():
            if o in foes and a["props"].get(c, (k, o))[1] != o:
                caps.append((b["day"], c, k, a["props"][c][1]))
    builds = []
    seen = set(s0["units"])
    for a, b in zip(snaps, snaps[1:]):
        for i, u in b["units"].items():
            if i not in seen and u["army"] in foes:
                cls = b["props"].get((u["x"], u["y"]))
                builds.append((b["day"], u["army"], u["type"], (u["x"], u["y"]), cls[0] if cls else None))
        seen |= set(b["units"])
    prod = {a: sum(1 for c, (k, o) in s0["props"].items() if o == a and k in PRODUCES) for a in foes}
    roles = {}
    for u in first.values():
        key = (u["type"], u["role"])
        roles[key] = roles.get(key, 0) + 1
    return dict(mission=n, foes=sorted(foes), start_units=len(first), alive_end=sum(1 for i in first if i in last["units"]),
                moved_by_day4=len(moved3), moved_ever=len(ever), captures=caps, builds=builds, producing_tiles=prod,
                funds=[(s["day"], {a: s["funds"][a] for a in foes}) for s in snaps], roles={f"{k[0]}:{k[1]}": v for k, v in sorted(roles.items())},
                props_foes=[(s["day"], sum(1 for k, o in s["props"].values() if o in foes)) for s in snaps],
                days=[s["day"] for s in snaps],
                mine_by_day=[sum(1 for u in s["units"].values() if u["army"] == me) for s in snaps],
                my_props_by_day=[sum(1 for k, o in s["props"].values() if o == me) for s in snaps],
                max_funds={str(a): max(s["funds"][a] for s in snaps) for a in sorted(foes)},
                units0=[[i, u["army"], u["type"], u["x"], u["y"], u["role"], (i in ever), (i in last["units"]), (i in moved3)] for i, u in sorted(first.items())],
                final=[[u["army"], u["type"], u["x"], u["y"]] for i, u in sorted(last["units"].items()) if u["army"] in foes],
                props0=[[c[0], c[1], k, o] for c, (k, o) in sorted(s0["props"].items())],
                props_end=[[c[0], c[1], k, o] for c, (k, o) in sorted(last["props"].items())],
                mine0=[[u["type"], u["x"], u["y"]] for i, u in sorted(s0["units"].items()) if u["army"] == me],
                size=None)


LIMITS = {1: 20, 2: 18, 3: 25, 4: 20, 5: 9, 6: 22, 7: 26, 8: 22, 9: 16, 10: 24, 11: 24, 12: 28, 13: 14, 14: 15, 15: 24, 16: 24,
          17: 22, 18: 12, 19: 28, 20: 24, 21: 26, 22: 24, 23: 22, 24: 14, 25: 24, 26: 30, 27: 20, 28: 36, 29: 32, 30: 34, 31: 11}
# aw2test.bot.Bot options per mission (the cells the mission is won on): the act tests' own
BOT_OPTS = {5: dict(garrison=True, goals=[(19, 3)]), 9: dict(goals=[(26, 7)]), 4: dict(goals=[(21, 9)], finish=12),
            6: dict(goals=[(28, 14)], finish=14), 7: dict(goals=[(25, 19)], finish=14), 8: dict(goals=[(22, 9)], finish=14),
            10: dict(goals=[(14, 3)]), 11: dict(goals=[(25, 3), (25, 17)], finish=16),
            26: dict(goals=[(4, 4), (4, 23), (33, 14)])}


def bot_run(ctx, n, seed=None):
    """The test bot plays the player from the first turn on, up to the day limit + 3. Returns the outcome."""
    from .bot import Bot
    from .dscampaign import LAST_RESULT, DAY
    e, g, d = enter(ctx, n)
    me = 5 if n == 28 else 1
    days = []
    opts = dict(BOT_OPTS.get(n, {}))
    if seed is not None:
        opts["seed"] = seed
    bot = Bot(d, log=lambda s: None, **opts)
    s0 = snapshot(e, g, me)
    foes = {a for a in range(1, 6) if a != me and s0["team"][a] != s0["team"][me]}
    e.w8(LAST_RESULT, 0)
    start = e.u16(DAY)
    last = start
    limit = LIMITS[n] + 3
    t0 = e.frame
    while e.frame - t0 < 2500000:
        if e.u8(LAST_RESULT):
            break
        army = e.u8(0x030033EC)
        pl = d.players()
        human = 1 <= army <= 5 and e.u8(pl + 0x3C * army + 0x1B) == 1
        if d.in_battle() and human and not d.scripts_running():
            day = e.u16(DAY)
            if day != last:
                last = day
                us = all_units(e, g)
                days.append((day, sum(1 for u in us if u["army"] == me), sum(1 for u in us if u["army"] in foes)))
                if day >= start + limit:
                    break
            try:
                bot.play_turn(army)
            except Exception as ex:
                if e.u8(LAST_RESULT):
                    break
                bot.cancel()
            continue
        if d.scripts_running() or not d.in_battle() or d.on_co_select():
            e.press("A", 4)
        e.wait(30)
        day = e.u16(DAY)
        if day != last and d.in_battle():
            last = day
            us = all_units(e, g)
            days.append((day, sum(1 for u in us if u["army"] == me), sum(1 for u in us if u["army"] in foes)))
            if day >= start + limit:
                break
    res = e.u8(LAST_RESULT)
    us = all_units(e, g) if d.in_battle() else []
    out = dict(mission=n, result=res, day=last, limit=LIMITS[n], mine=sum(1 for u in us if u["army"] == me),
               theirs=sum(1 for u in us if u["army"] in foes), days=days)
    return e, out
