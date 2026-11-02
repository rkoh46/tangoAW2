"""No CPU unit idles on a production tile (docs/dev/cpu-unit-use.md, "Tests"): with the player passive for several CPU turns, a unit of a computer army that
could move must not stand on a base, port or airport of its own team on the same cell in two snapshots in a row. A unit built on a turn is in the first snapshot
after it (it cannot move on the turn it is built): it counts from the next pair, so it has to leave by its second turn. A production tile its owner (or an ally)
keeps occupied like that cannot build either, which is what the player saw (a naval port blocked by a Black Boat).

`check(snaps, ...)` is the rule on a list of snapshots (`snapshot`: the player's turn starts); the `run_*` helpers play a mission or map with the player passive and
return the snapshots; tests/test_cpu_port_idle.py makes one test per mission and map from the real lists.

What is exempt (each unit is listed with its reason in the test's log):
- a unit that cannot move: no fuel, or every cell it could step to (the game's own movement chart, its CO's, with the move points it has) is taken by a unit
  (detected from the snapshot, never a hand-written list);
- a unit riding in a transport (it is off the map);
- a unit on a tile that is not its team's in both snapshots (a soldier capturing the base is on its way to owning it);
- a damaged unit that the property healed over the turn (hit points below 100 and up since the snapshot before): the CPU leaves a unit on a property to be
  repaired, which ends when it is whole (five turns at most), so it is a stay with a reason, not an idle unit;
- with `scripted=True` (the campaigns' missions): a unit that was on the map in the first snapshot with role byte 0, a mission's scripted hold (the deployment's AI byte 0,
  `UnitDef::stand` / `freeze`: the designer's garrisons and camps, tests/test_bh_cpuai.py's DESIGNED_CAMPS): the engine never moves it by design. A unit built or
  spawned later with role 0 is not exempt."""

from . import bot
from . import cpuprobe as cp
from . import dscampaign as dc
from . import rom as romlib
from .game import NavError

PRODUCTION = {0x0A: "airport", 0x0B: "port", 0x0E: "base"}    # terrain classes (class & 0x1F)
DAY = 0x03004080
FIVE_ON = 0x02030206      # crate::five: 1 in a five-army Versus battle, 2 in a custom campaign's (the players' table then holds five armies)
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def unit_table(ctx):
    """Where the unit records are in emulated memory: tangoAW2's table with the pack, AW2's own without."""
    return bot.UNIT_TABLE if ctx.ds else romlib.UNIT_TABLE


def snapshot(ctx, e, g):
    """cpuprobe.snapshot plus what the movability test needs: the controllers, every cell's class, each army's movement chart and each unit type's move and movement type."""
    s = cp.snapshot(e, g, 1)
    pl = e.u32(bot.PLAYERS_PTR)
    five = e.u8(FIVE_ON)
    s["five"] = five
    s["ctrl"] = {a: e.u8(pl + 0x3C * a + 0x1B) for a in range(1, 6 if five in (1, 2) else 5)}
    w, h = e.u16(bot.MAP), e.u16(bot.MAP + 2)
    s["size"] = (w, h)
    s["grid"] = [bytes(e.read(bot.CLASSES + e.u16(bot.ROWS + 2 * y), w)) for y in range(h)]
    pool = e.u32(bot.CO_TABLE_POOL)
    charts = {}
    s["charts"] = {}
    for a in s["ctrl"]:
        if s["ctrl"][a]:
            co = e.u8(pl + 0x3C * a + 0x1D)
            if co not in charts:
                p = e.u32(pool + 0x104 * co + 0x38 + 0x18)
                charts[co] = [x - 256 if x > 127 else x for x in e.read(p, 32 * 16)]
            s["charts"][a] = charts[co]
    table = unit_table(ctx)
    s["stats"] = {t: (e.u8(table + bot.UNIT_RECORD * t + 0x0A), e.u8(table + bot.UNIT_RECORD * t + 0x19))
                  for t in {u["type"] for u in s["units"].values()}}
    return s


def can_move(s, u):
    """The unit can step to some free cell now: fuel left and a cell reached by the game's own movement chart (its army's CO), enemy units blocking it, friends not."""
    if u["fuel"] <= 0:
        return False
    import heapq
    move, mt = s["stats"][u["type"]]
    move = min(move, u["fuel"])
    chart = s["charts"].get(u["army"])
    if chart is None or move <= 0:
        return False
    w, h = s["size"]
    team = s["team"]
    occ = {(v["x"], v["y"]): v for v in s["units"].values() if not v["on"]}
    start = (u["x"], u["y"])
    best = {start: 0}
    q = [(0, start)]
    while q:
        c, (x, y) = heapq.heappop(q)
        if c > best[(x, y)]:
            continue
        for dx, dy in STEPS:
            n = (x + dx, y + dy)
            if not (0 <= n[0] < w and 0 <= n[1] < h):
                continue
            step = chart[mt * 32 + (s["grid"][n[1]][n[0]] & 0x1F)]
            if step <= 0 or c + step > move:
                continue
            o = occ.get(n)
            if o is not None and team[o["army"]] != team[u["army"]]:
                continue
            if c + step < best.get(n, 99):
                best[n] = c + step
                heapq.heappush(q, (c + step, n))
                if o is None:
                    return True
    return False


def cpu_armies(s):
    """The computer's armies (the controller byte 2)."""
    return {a for a, c in s["ctrl"].items() if c == 2}


def check(snaps, scripted=False):
    """The rule on the player's turn-start snapshots: (violations, exempt). Each is a list of dicts (day, army, type, cell, kind, role, why)."""
    bad, exempt = [], []
    pairs = 0
    for a, b in zip(snaps, snaps[1:]):
        cpu = cpu_armies(a) & cpu_armies(b)
        for i, u in b["units"].items():
            v = a["units"].get(i)
            if v is None or u["on"] or v["on"] or u["army"] not in cpu or v["army"] != u["army"] or v["type"] != u["type"]:
                continue
            cell = (u["x"], u["y"])
            if cell != (v["x"], v["y"]):
                continue
            pairs += 1
            ka, kb = a["props"].get(cell), b["props"].get(cell)
            if not ka or not kb or ka[0] not in PRODUCTION or kb[0] != ka[0]:
                continue
            ours = lambda s, k: k[1] and s["team"][k[1]] == s["team"][u["army"]]
            if not (ours(a, ka) and ours(b, kb)):
                continue
            rec = dict(day=b["day"], army=u["army"], type=romlib.UNIT_NAMES.get(u["type"], u["type"]), id=i, cell=cell,
                       kind=PRODUCTION[ka[0]], role=u["role"], hp=u["hp"])
            first = snaps[0]["units"].get(i)
            if scripted and u["role"] == 0 and first is not None and first["type"] == u["type"] and first["army"] == u["army"]:
                exempt.append(dict(rec, why="the mission's own scripted hold (a unit deployed with role 0)"))
            elif v["hp"] < 100 and u["hp"] > v["hp"]:
                exempt.append(dict(rec, why="being repaired (damaged, and the property healed it this turn)"))
            elif not (can_move(a, v) and can_move(b, u)):
                exempt.append(dict(rec, why="cannot move (no fuel or boxed in)"))
            else:
                bad.append(rec)
    return bad, exempt


def describe(r):
    return f"day {r['day']}: army {r['army']} {r['type']} #{r['id']} (role {r['role']}, {r['hp']} hp) stays on a {r['kind']} at {r['cell']}"


def report(ctx, label, snaps, scripted=False, min_snaps=2):
    """The test's checks and log lines for a list of snapshots. Returns the violations."""
    bad, exempt = check(snaps, scripted)
    cpu = sorted(set().union(*[cpu_armies(s) for s in snaps])) if snaps else []
    on_tiles = sum(1 for s in snaps for u in s["units"].values()
                   if u["army"] in cpu and not u["on"] and s["props"].get((u["x"], u["y"]), (0, 0))[0] in PRODUCTION)
    ctx.log(f"{label}: {len(snaps)} snapshots (days {[s['day'] for s in snaps]}), computer armies {cpu}, {on_tiles} unit-snapshots on production tiles, "
            f"{len(exempt)} exempt, {len(bad)} violations")
    seen = {}
    for r in exempt:
        seen.setdefault((r["id"], r["type"], r["cell"], r["why"]), []).append(r["day"])
    for (i, t, cell, why), ds_ in seen.items():
        ctx.log(f"  exempt: {t} #{i} on a production tile at {cell}, days {ds_}: {why}")
    for r in bad:
        ctx.log(f"  VIOLATION: {describe(r)}")
    ctx.check(len(snaps) >= min_snaps, f"{label}: the game ran long enough to compare turns ({len(snaps)} snapshots)")
    ctx.check(not bad, f"{label}: no computer unit that could move idles on a base, port or airport ({len(bad)}: {[describe(r) for r in bad[:4]]})")
    return bad


# --- playing passively ------------------------------------------------------------------------------------------------
def humans(e):
    pl = e.u32(bot.PLAYERS_PTR)
    return [a for a in range(1, 6) if e.u8(pl + 0x3C * a + 0x1B) == 1]


def passive(ctx, e, g, d, label, days, snap, front=None, over=None, end=None):
    """The player(s) end every turn without acting: `snap()` at the start of each of the first human army's turns, `days` snapshots at most (fewer when the mission ends).
    `front()` (optional): a snapshot of the other front taken right after each; `over()` (optional): the battle has ended (Versus has no mission result); `end(e, g, d)` (optional): how a turn is ended. Returns (snapshots, fronts)."""
    from . import bhact2 as a2
    snaps, fronts = [snap()], []
    if front:
        fronts.append(front())
    me = humans(e)
    while len(snaps) < days:
        d0 = e.u16(DAY)
        ok = False
        fails = 0
        for _ in range(400):
            if e.u8(dc.LAST_RESULT) or (over and over()):
                break
            army = e.u8(bot.CURRENT_ARMY)
            if e.u16(DAY) > d0 and army in me and d.in_battle() and not d.scripts_running():
                try:
                    d.wait_control()
                except NavError:
                    break
                ok = True
                break
            if e.u16(DAY) == d0 and army in me and d.in_battle() and not d.scripts_running():
                try:
                    (end or a2.end_turn)(e, g, d)
                except NavError as ex:
                    ctx.log(f"{label}: end turn day {d0}: {ex}")
                    fails += 1
                    if fails >= 4:
                        break
                    for _ in range(3):             # (back out of whatever the failed End left open: a selection, a menu)
                        e.press("B", 4)
                        e.wait(30)
                    a2.boxes(e, d, 600)
                e.wait(40)
                continue
            if d.scripts_running() or not d.in_battle():
                e.press("A", 4)
            e.wait(40)
        if not ok:
            ctx.log(f"{label}: stopped before snapshot {len(snaps) + 1} (day {e.u16(DAY)}, result {e.u8(dc.LAST_RESULT)})")
            break
        g._units_base = g._players_base = None
        snaps.append(snap())
        if front:
            fronts.append(front())
    return snaps, [f for f in fronts if f]


def snap_fn(ctx, e, g):
    return lambda: snapshot(ctx, e, g)


# --- the modes ----------------------------------------------------------------------------------------------------
DAYS = 7           # snapshots: six CPU turns


def run_bh(ctx, n, days=DAYS):
    """BH Campaign mission n (cpuprobe.enter: its CO screens, its opening played): snapshots of the main front and, for the two-front missions, of the other."""
    e, g, d = cp.enter(ctx, n)
    label = f"BH M{n}"
    front = (lambda: other_front(ctx, e, g, n)) if n in cp.FRONT2 else None
    return e, g, passive(ctx, e, g, d, label, days, snap_fn(ctx, e, g), front)


def other_front(ctx, e, g, n):
    """A snapshot of the other front (Map menu > Front) with `snapshot`'s extras, or None (cpuprobe.other_front on this module's snapshot)."""
    from . import twofront as tf
    try:
        if not tf.look_at_other_front(e, g):
            return None
        g._units_base = g._players_base = None
        s = snapshot(ctx, e, g)
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


def start_campaign(ctx, mod, n):
    """BH2 / Silver Nova mission n entered (`mod.enter`), its Setup left and its opening played."""
    from . import bhact2 as a2
    e, g, d = mod.enter(ctx, n)
    if d.in_setup():
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", ())
        d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def run_driver(ctx, label, e, g, d, days=DAYS):
    return e, g, passive(ctx, e, g, d, label, days, snap_fn(ctx, e, g))


def run_bh2(ctx, n, days=DAYS):
    from . import bh2campaign as b2
    e, g, d = start_campaign(ctx, b2, n)
    front = (lambda: other_front(ctx, e, g, n)) if n in b2.FRONT2 else None
    return e, g, passive(ctx, e, g, d, f"BH2 M{n}", days, snap_fn(ctx, e, g), front)


def run_es(ctx, n, days=DAYS):
    from . import escampaign as es
    e, g, d = start_campaign(ctx, es, n)
    return e, g, passive(ctx, e, g, d, f"Silver Nova M{n}", days, snap_fn(ctx, e, g))


def run_dsc(ctx, step, days=DAYS):
    """Dual Strike Campaign mission `step` (the campaign's order, dscampaign.ORDER): picked on the world map, its CO screens answered, Setup left."""
    from . import paths
    from .emu import Emu
    from .game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    data = dc.DsData()
    index = dc.ORDER[step]
    opts = dc.plan(data, index)
    d.start(step=step)
    d.choose_cos(dc.co_picks(data, index), opts.get("cos"))
    if not e.wait_until(lambda: d.in_battle() and d.players() != 0, 20000, step=2):
        raise NavError("the battle did not load")
    d.leave_setup()
    d.wait_control()
    g._units_base = g._players_base = None
    name = data.mission(index)["name"]
    front = (lambda: other_front(ctx, e, g, index)) if index in TWO_FRONT else None
    return e, g, passive(ctx, e, g, d, f"DS {index} {name}", days, snap_fn(ctx, e, g), front)


TWO_FRONT = {8, 10, 14, 21, 24}      # Dual Strike's two-front missions (tests/test_ds_campaign.py)


def run_versus(ctx, tab, row, mid, days=6):
    """Versus map `mid` (SELECT MAP tab `tab`, row `row`) with army 1 the passive player and every other army the computer."""
    from . import versusmaps as vm
    g = vm.select(ctx, tab, row, mid)
    e = g.e
    g.set_teams(None, {1})
    g.teams_to_rules()
    g.set_rules(fog=False, weather="clear", power=True, visuals="off")
    g.start_battle()
    g.wait_for_input()
    d = dc.DsCampaign(g)
    return e, g, passive(ctx, e, g, d, f"Versus map {mid:#x}", days, snap_fn(ctx, e, g), over=g.battle_over)


def run_design(ctx, m, cos, days=DAYS):
    """A Design Room map `m` (a save.DesignMap) in Versus with army 1 the passive player."""
    g = ctx.start(m, cos)
    d = dc.DsCampaign(g)
    return g.e, g, passive(ctx, g.e, g, d, "design map", days, snap_fn(ctx, g.e, g), over=g.battle_over)


def run_gauntlet(ctx, map=0, days=DAYS):
    """The Gauntlet's map `map` (the selector's entry: 0 Cinder Sea, 1 Iron Crown) with the player passive."""
    from . import gauntlet as ga
    from . import paths
    from .emu import Emu
    from .game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    if map:
        from tests.test_gauntlet_map2 import to_player_turn
        d.start(ga.ANDY, map=map)
        to_player_turn(e, g, d)
    else:
        d.start(ga.ANDY)
    g._units_base = g._players_base = None
    return e, g, passive(ctx, e, g, d, f"Gauntlet map {map}", days, snap_fn(ctx, e, g))


AW2_CAMPAIGN_MISSIONS = 20      # AW2's mission table (0x08615194): maps 0x8A..0x9D, the order the world map opens them in


def run_aw2_campaign(ctx, k, days=DAYS):
    """AW2's own campaign (AW2 CAMPAIGN, New): missions 0..k-1 won in order (a test aid: `force_win`), then mission k played with the player passive. AW2's own CPU plays."""
    from . import campaigns as cmp
    from . import paths
    from .emu import Emu
    from .game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    cmp.aw2_new(e, d, ctx.ds)
    for _ in range(k):
        cmp.win_here(e, d)
        cmp.through_to_map(e, d)
        cmp.aw2_next_mission(e, d)
    g._units_base = g._players_base = None
    return e, g, passive(ctx, e, g, d, f"AW2 campaign mission {k + 1}", days, snap_fn(ctx, e, g), end=end_turn_aw2)


def end_turn_aw2(e, g, d):
    """End turn in AW2's own campaign, whose first missions answer End with "Things will only get worse if you select End now. Please give orders to all your units": then
    every unit of the army is given Wait and End is chosen again."""
    from . import bhact2 as a2
    army = g.current_army()
    a2.end_turn(e, g, d)
    e.wait(150)
    t = d.text_shown() or ""
    if "give orders" in t or "select End" in t:
        for _ in range(20):
            if (d.text_shown() or "") == "":
                break
            e.press("A", 4)
            e.wait(40)
        for _ in range(4):               # (an A after the box has closed opens the map menu: B closes it)
            if g.menu():
                e.press("B", 4)
                e.wait(30)
        g.wait_for_input()
        for u in g.units(army=army):
            try:
                g.wait_unit(u["x"], u["y"])
            except NavError:
                e.press("B", 4)
                e.wait(20)
        a2.end_turn(e, g, d)


def run_warroom(ctx, row, days=DAYS):
    """The War Room's map in list row `row` (New, SELECT MAP, the row, the first CO the CO screen offers, LET'S GO) with the player passive. AW2's own CPU plays."""
    from . import paths
    from . import saves
    from . import survival as sv
    from . import warroom as wr
    from .emu import Emu
    from .game import Game
    wr.set_ds(ctx.ds)
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 1)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), 600, step=10):
        raise NavError("the War Room's SELECT MAP did not open")
    e.wait(90)
    for _ in range(row):
        e.press("DOWN", 8)
        e.wait(30)
    e.wait(30)
    e.press("A", 8)
    if not e.wait_until(lambda: wr.proc(e) is not None, 900, step=10):
        raise NavError("the War Room's CO screen did not open")
    e.wait(60)
    wr.start_battle(e, g)
    d = dc.DsCampaign(g)
    return e, g, passive(ctx, e, g, d, f"War Room row {row}", days, snap_fn(ctx, e, g), over=g.battle_over)


def run_survival(ctx, kind, days=DAYS):
    """Survival's first map of run `kind` (survival.MONEY / TURN / TIME: SELECT MAP lists them in survival.LIST_ORDER) with the player passive. AW2's own CPU plays. The later stages
    of a run only open after the earlier ones are won (not played here)."""
    from . import paths
    from . import survival as sv
    from .emu import Emu
    from .game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    if not sv.open_survival(e):
        raise NavError("Survival's SELECT MAP did not open")
    if not sv.pick(e, sv.LIST_ORDER.index(kind)):
        raise NavError("the Survival battle did not start")
    g._units_base = g._players_base = None
    g.wait_for_input()
    d = dc.DsCampaign(g)
    return e, g, passive(ctx, e, g, d, f"Survival {sv.NAMES[kind]}", days, snap_fn(ctx, e, g), over=g.battle_over)
