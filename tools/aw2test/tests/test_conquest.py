"""Conquest (crate::conquest, docs/dev/conquest.md): Select Mode's CONQUEST entry (a game mode of its own on the Gauntlet's engine), runs of AW2 Versus maps with the survivors and funds carried
over, one loss ends it, a win after the last map records a result under the run's own key; the wheel entry, its selector (a row a run) and its Continue / New box apart from the Gauntlet's. Run 1 is
Conquest Run (9 maps); run 2, "Harbor Run", nine more maps on the same engine. `-k conquest`."""

import os
import subprocess

from aw2test import conquest as cq
from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import paths, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test


def png(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


def start(ctx, co=ga.ANDY, colour=None, save=None, env=None, run=0):
    """Run `run` (0-based) of CONQUEST started from Select Mode: (emu, game, driver) with the player in control on day 1 of the first map."""
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g, run=run)
    d.begin(co, colour)
    return e, g, d


def preview_size(e, d, id_):
    """The picture a map-table entry shows (header +0x2C: its LZ77 tiles in the ROM): the (width, height) in cells, or None when it points into the game's own maps."""
    from aw2test import rom
    ptr = e.u32(d.table() + 0x5C * id_ + 0x2C)
    raw = rom.lz10(bytes(e.read(ptr, 0x800)))
    return raw[0], raw[1]


def record_row(e, id_):
    """The War Room record row the selector's record box reads for map-table id `id_`: five words (CO byte, score above)."""
    b = bytes(e.read(ga.ROWS + 0x14 * (id_ - ga.ROW_BASE), 0x14))
    return [int.from_bytes(b[4 * k:4 * k + 4], "little") for k in range(5)]


@test(name="conquest_selector_has_a_row_for_each_run", modes=("ds",))
def conquest_selector_has_a_row_for_each_run(ctx):
    """CONQUEST's map selector (the War Room's own screen) lists a row a run, "Conquest Run *" then "Harbor Run *" (the star: several maps), each on its own map-table id, the cursor on the first and
    DOWN / UP between them; SELECT flips through the highlighted run's own maps' pictures (cropped from the ROM into the shared slots); each row's record box shows its own run's results; A takes
    the highlighted run to the army screen. The Gauntlet's list never has them."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq([d.entry_name(i) for i in ids], ga.CONQUEST_TITLES, "one row a run")
    ctx.eq(ids, ga.conquest_ids(), "on their own map-table ids")
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (0, cq.RUNS[0]["mission"]), "the cursor is on the first: mission 12")
    ctx.eq(ga.shown(e)[0], len(cq.RUNS), "the screen's mirror lists the runs")
    png(ctx, e, "selector_run1")
    # (each run's rows hold only its own results: the record box reads the row of its id)
    d.put_results(51, [(ga.ANDY, 70, 400)])
    d.put_results(52, [(ga.SAMI, 90, 300), (ga.MAX, 95, 200)])
    e.wait(20)
    rows = [record_row(e, i) for i in ga.conquest_ids()]
    ctx.eq([w & 0xFF for w in rows[0][:2]], [ga.ANDY, 0], "run 1's row holds run 1's result")
    ctx.eq([w & 0xFF for w in rows[1][:2]], [ga.SAMI, ga.MAX], "run 2's row holds run 2's two results")
    ctx.eq(preview_size(e, d, ga.conquest_id(run=0)), cq.RUNS[0]["maps"][0]["size"], "run 1's picture is Sabre Range's")
    e.press("DOWN", 4)
    e.wait(60)
    ctx.eq((d.selector_ids()[1], e.u8(ga.UI_MAP_CURSOR)), (1, cq.RUNS[1]["mission"]), "DOWN moves to the second run: mission 13")
    png(ctx, e, "selector_run2")
    # SELECT flips through run 2's nine maps (the cursor's row only), the picture the size of the map's crop, and round to the first again
    maps = cq.RUNS[1]["maps"]
    for k in range(1, len(maps) + 1):
        d.flip(90)
        want = k % len(maps)
        ctx.eq(e.u8(ga.UI_STAGE), want, f"SELECT: map {want + 1} of the run")
        w, h = maps[want]["size"]
        if want > 0:
            ctx.eq(preview_size(e, d, ga.conquest_id(run=1)), (min(w, 32), min(h, 22)), f"the picture is {maps[want]['name']}'s, cropped to the picture area")
        if want in (1, len(maps) - 1):
            png(ctx, e, f"selector_run2_map{want + 1}")
    e.press("UP", 4)
    e.wait(60)
    ctx.eq((d.selector_ids()[1], e.u8(ga.UI_MAP_CURSOR), e.u8(ga.UI_STAGE)), (0, cq.RUNS[0]["mission"], 0), "UP is the first run, on its first map")
    e.press("DOWN", 4)
    e.wait(40)
    e.press("DOWN", 4)
    e.wait(40)
    ctx.eq((d.selector_ids()[1], e.u8(ga.UI_MAP_CURSOR)), (1, cq.RUNS[1]["mission"]), "DOWN has nowhere further to go")
    e.press("UP", 4)
    e.wait(40)
    e.press("A", 6)
    d.wait_army()
    ctx.eq(e.u8(ga.UI_MAP), cq.RUNS[0]["mission"], "A took Conquest Run to the army screen")
    free = ga.shown(e)[2]
    ctx.check(cq.BLACK_HOLE not in free, f"the enemy wears Black Hole's colour, so the player's pick leaves it ({free})")
    png(ctx, e, "army_screen")
    e.close()


@test(name="conquest_second_run_is_picked_on_its_row", modes=("ds",))
def conquest_second_run_is_picked_on_its_row(ctx):
    """A on the second row takes "Harbor Run" (mission 13) to its own army screen (its title and map count are in the picture) and starts it on its first map; B on the selector goes back to the wheel on
    CONQUEST."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g, run=1)
    d.open()
    d.wait_army()
    ctx.eq(e.u8(ga.UI_MAP), cq.RUNS[1]["mission"], "A took Harbor Run to the army screen")
    png(ctx, e, "army_screen_run2")
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.eq((d.session()["mission"], d.session()["source"]), (cq.RUNS[1]["mission"], ga.GAUNTLET), "the run is the Gauntlet's mission 13")
    ctx.eq(cq.stage(e), 0, "stage 0")
    e.close()


@test(name="conquest_gauntlet_selector_does_not_list_it", modes=("ds",))
def conquest_gauntlet_selector_does_not_list_it(ctx):
    """The Gauntlet's own selector lists its twelve maps and not the Conquest runs (their map-table entries are hidden, Survival's borrowed entries given back whole); Conquest's pick afterwards lists
    the runs' rows again, the Gauntlet's the twelve."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq([d.entry_name(i) for i in ids], ga.SELECTOR_TITLES, "the Gauntlet's twelve maps")
    ctx.check(not set(ga.CONQUEST_TITLES) & {d.entry_name(i) for i in ids}, "no Conquest run among them")
    ctx.eq(ga.shown(e)[0], len(ga.SELECTOR_ORDER), "the mirror lists twelve maps")
    ctx.eq(e.u8(ga.UI_MAP_CURSOR), ga.SELECTOR_ORDER[0], "the cursor is on the first row's map")
    # B, B back to Select Mode on GAUNTLET, then CONQUEST: the one row
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e.wait(60)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 9, "the wheel is on GAUNTLET")
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ids, _ = d.selector_ids()
    ctx.eq([d.entry_name(i) for i in ids], ga.CONQUEST_TITLES, "CONQUEST lists the runs, not the Gauntlet's maps")
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e.wait(60)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "B on the selector: the wheel stays on CONQUEST")
    e.close()


@test(name="conquest_run_starts_on_the_first_map", modes=("ds",))
def conquest_run_starts_on_the_first_map(ctx):
    """A run starts on Sabre Range (an AW2 Versus map read from the ROM): the player is army 1 with its starting force and funds, the enemy army 2 Black Hole's with its own."""
    e, g, d = start(ctx)
    m = cq.MAPS[0]
    ctx.eq((d.session()["mission"], d.session()["source"]), (cq.MISSION, ga.GAUNTLET), "the run is the Gauntlet's mission 12")
    ctx.eq(cq.stage(e), 0, "stage 0")
    ctx.eq(d.size(), m["size"], "Sabre Range is 15 x 11")
    ctx.eq((len(g.units(army=1)), len(g.units(army=2))), (m["mine"], m["force"]), "the starting forces")
    ctx.eq(d.owner(m["player"]), 1, "the player's HQ")
    ctx.eq(d.owner(m["enemy"]), 2, "the enemy's HQ")
    ctx.eq([e.u8(g.players_base + 0x3C * a + 0x1B) for a in (1, 2)], [1, 2], "the player is human, the enemy the computer's")
    ctx.eq(e.u8(g.players_base + 0x3C * 2 + 0x1A), cq.BLACK_HOLE, "the enemy wears Black Hole's colour")
    ctx.check(d.funds(1) >= 7000, f"the player's funds ({d.funds(1)})")
    png(ctx, e, "first_turn")
    e.close()


@test(name="conquest_winning_a_map_carries_survivors_and_funds", modes=("ds",))
def conquest_winning_a_map_carries_survivors_and_funds(ctx):
    """Taking the enemy HQ on map 1 moves the battle, in place, to map 2: the survivors (count, type, HP) and the funds come along, the enemy has its own force and funds on Switchback."""
    e, g, d = start(ctx)
    hurt = g.units(army=1)[0]
    g._units_base = g._players_base = None
    e.w32(g.players_base + 0x3C * 1, 12345)
    d.capture_enemy_hq(ctx)
    before = d.units_by_type()
    funds = d.funds(1)
    d.wait_stage(1)
    m = cq.MAPS[1]
    ctx.eq(cq.stage(e), 1, "map 2")
    ctx.eq(d.size(), m["size"], "Switchback is 21 x 15")
    after = d.units_by_type()
    ctx.check(len(after) >= len(before) - 1 and len(after) >= 3, f"the survivors came along ({len(after)} of {len(before)})")
    ctx.eq(sorted(t for t, _ in after)[:3], sorted(t for t, _ in before)[:3], "the same kinds")
    ctx.check(abs(d.funds(1) - funds) <= 12000, f"the funds came along (was {funds}, now {d.funds(1)})")
    ctx.check(d.funds(1) >= 12345 - 200, f"the player still has what it held ({d.funds(1)})")
    ctx.eq(len(g.units(army=2)), m["force"], "the enemy's force on map 2")
    ctx.check(d.funds(2) >= m["funds"], f"the enemy's funds on map 2 ({d.funds(2)})")
    ctx.eq([d.owner(m["player"]), d.owner(m["enemy"])], [1, 2], "both HQs on the new map")
    ctx.eq(e.u8(g.players_base + 0x3C * 2 + 0x1A), cq.BLACK_HOLE, "the enemy is still Black Hole's colour")
    png(ctx, e, "map2_first_turn")
    e.close()


@test(name="conquest_destroying_every_enemy_unit_also_wins_a_map", modes=("ds",))
def conquest_destroying_every_enemy_unit_also_wins_a_map(ctx):
    """The engine's own defeat of an army with no units would end the whole run in VICTORY on map 1: it is held off, and the map's trigger moves the run on to map 2 instead."""
    e, g, d = start(ctx)
    for u in g.units(army=2):
        d.remove_unit(u)
    e.wait(30)
    inf = next(u for u in g.units(army=1) if u["type"] == 1)
    g.select(inf["x"], inf["y"])
    g.move_to(inf["x"], inf["y"])
    g.choose("Wait", g.ACTION_MENU)
    d.wait_reward()
    ctx.eq(cq.stage(e), 0, "the reward page opens over map 1 (the map's trigger, not AW2's victory)")
    d.wait_stage(1)
    ctx.eq(cq.stage(e), 1, "with the enemy gone the run is on map 2, not over")
    ctx.check(d.in_battle() and not d.select_mode_up(), "the battle goes on")
    e.close()


@test(name="conquest_a_defeat_ends_the_run", modes=("ds",))
def conquest_a_defeat_ends_the_run(ctx):
    """AW2's DEFEAT ends the run: results, Select Mode on CONQUEST, the result 2 (lost), nothing recorded and no run saved."""
    e, g, d = start(ctx)
    ctx.eq(d.lose(ctx), 2, "the run is lost")
    ctx.check(d.select_mode_up(), "back on Select Mode")
    e.wait(60)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "the wheel is on CONQUEST, not GAUNTLET")
    png(ctx, e, "wheel_after_the_run")
    ctx.eq(d.results(cq.RECORD_ID), [], "a loss writes no result")
    ctx.eq(e.u8(dc.ACTIVE), 0, "the session is over")
    e.close()


@test(name="conquest_a_full_run_records_a_result", modes=("ds",))
def conquest_a_full_run_records_a_result(ctx):
    """Nine maps won in a row (each by the HQ capture) end in VICTORY, and the Gauntlet's top-five table has a row for gauntlet_51 with this run's CO, days and score."""
    e, g, d = start(ctx)
    for k in range(cq.STAGES):
        ctx.eq(cq.stage(e), k, f"on map {k + 1}")
        ctx.eq(d.size(), cq.MAPS[k]["size"], f"{cq.MAPS[k]['name']}")
        g._units_base = g._players_base = None
        ctx.eq(len(g.units(army=2)), cq.MAPS[k]["force"], f"{cq.MAPS[k]['name']}: the enemy's starting force")
        ctx.eq([d.owner(cq.MAPS[k]["player"]), d.owner(cq.MAPS[k]["enemy"])], [1, 2], f"{cq.MAPS[k]['name']}: both HQs")
        if k + 1 < cq.STAGES:
            d.win_map(ctx, k)
        else:
            d.capture_enemy_hq(ctx, k)
    ctx.eq(d.through_results(), 1, "taking the last HQ wins the run")
    e.wait(60)
    got = d.results(cq.RECORD_ID)
    ctx.eq(len(got), 1, f"one result under the run's key ({got})")
    co, days, score = got[0]
    ctx.eq(co, ga.ANDY, "Andy's run")
    ctx.check(days >= 1 and score > 0, f"days {days}, score {score}")
    done = saves.flash(e, os.path.join(ctx.out, "finished"))
    rec = ga.saved_record(done)
    ctx.check(rec is not None and ga.record_best(rec, cq.RECORD_ID) is not None, "the win was written to Flash slot 13")
    ctx.check(d.select_mode_up(), "back on Select Mode")
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "the wheel is on CONQUEST after the won run too")
    e.close()


# -- the reward between maps -------------------------------------------------------------------------------------------------------------------------------------------

def unit_stats(e, g, army=1):
    """Every unit of the army: (type, hp 0..100, ammo, fuel) as the unit record holds them (+4: hp 7 bits, ammo 4 bits at 7; +6 fuel)."""
    out = []
    for u in g.units(army=army):
        a = g.unit_addr(u["id"])
        w = e.u16(a + 4)
        out.append((u["type"], w & 0x7F, (w >> 7) & 0xF, e.u8(a + 6)))
    return sorted(out)


def rom_max(e, kind):
    """(ammo, fuel) a type holds: AW2's unit table (+0x0B, +0x10)."""
    t = 0x085D5ABC + 0x5C * kind
    return e.u8(t + 0x0B), e.u8(t + 0x10)


CARRY = 0x0203DCC0               # crate::stage::CARRY: the survivors' 12-byte records (count at crate::ram_map::STAGE + 3)


def carry(e):
    """The survivors waiting in the stage engine's carry buffer: [{type, hp, ammo, fuel}]."""
    out = []
    for k in range(e.u8(ga.STAGE_AT + 3)):
        b = bytes(e.read(CARRY + 12 * k, 12))
        w = b[4] | b[5] << 8
        out.append({"type": b[0], "hp": w & 0x7F, "ammo": (w >> 7) & 0xF, "fuel": b[6]})
    return out


def hurt(e, g, n=3):
    """The first `n` units of the player's army worn down: 30 HP, 1 ammo, 5 fuel. Returns their ids."""
    ids = []
    for u in g.units(army=1)[:n]:
        a = g.unit_addr(u["id"])
        e.w16(a + 4, (e.u16(a + 4) & ~0x7F & ~0x780) | 30 | (1 << 7))
        e.w8(a + 6, 5)
        ids.append(u["id"])
    return ids


def to_reward(ctx, co=ga.ANDY, wear=False):
    e, g, d = start(ctx, co)
    if wear:
        hurt(e, g)
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    return e, g, d


@test(name="conquest_reward_page_opens_over_the_map_just_won", modes=("ds",))
def conquest_reward_page_opens_over_the_map_just_won(ctx):
    """A won map does not switch at once: the page of three rewards opens over it (page 1, cursor on the war chest), the battle waits on map 1, the pad belongs to the page (a cursor move does not move the
    map's cursor), and A on the war chest closes it and brings map 2 with the funds."""
    e, g, d = to_reward(ctx)
    ctx.eq((e.u8(cq.PAGE), e.u8(cq.CURSOR), e.u8(cq.WON)), (1, 0, 0), "page 1, the war chest under the cursor, map 1 won")
    ctx.eq(cq.stage(e), 0, "the battle is still on map 1")
    map_cursor = (e.u16(0x030033E4), e.u16(0x030033E6))
    png(ctx, e, "reward_page")
    e.press("RIGHT", 4)
    e.wait(20)
    ctx.eq(e.u8(cq.CURSOR), 1, "RIGHT moves the page's cursor")
    ctx.eq((e.u16(0x030033E4), e.u16(0x030033E6)), map_cursor, "the map's own cursor did not move")
    e.press("RIGHT", 4)
    e.wait(10)
    e.press("RIGHT", 4)
    e.wait(10)
    ctx.eq(e.u8(cq.CURSOR), 0, "RIGHT from the last card comes round to the first")
    e.press("LEFT", 4)
    e.wait(10)
    ctx.eq(e.u8(cq.CURSOR), 2, "LEFT from the first goes to the last")
    png(ctx, e, "reward_page_repair")
    e.press("RIGHT", 4)
    e.wait(10)
    ctx.eq(e.u8(cq.CURSOR), 0, "back on the war chest")
    e.press("A", 4)
    for _ in range(300):
        if cq.stage(e) == 1 and e.u8(cq.STAGE_BUSY) == 0 and d.in_battle():
            break
        e.wait(20)
    ctx.eq(cq.stage(e), 1, "map 2")
    e.close()


@test(name="conquest_reward_war_chest_adds_funds", modes=("ds",))
def conquest_reward_war_chest_adds_funds(ctx):
    """The war chest adds 10,000 funds after the first map (15,000 after the second, ...) to what is carried."""
    e, g, d = start(ctx)
    d.wait_control()
    held = d.funds(1)
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    before = d.funds(1)
    d.choose_reward(cq.CHEST)
    for _ in range(300):
        if cq.stage(e) == 1 and e.u8(cq.STAGE_BUSY) == 0 and d.in_battle():
            break
        e.wait(20)
    g._units_base = g._players_base = None
    d.wait_control()
    ctx.eq(cq.stage(e), 1, "map 2")
    ctx.eq(d.funds(1), before + cq.CHEST_FUNDS[0], f"funds {before} + 10,000 on map 2")
    # the second map's war chest is bigger
    d.win_map(ctx, 1, reward=cq.CHEST)
    ctx.eq(cq.stage(e), 2, "map 3")
    e.close()


@test(name="conquest_reward_free_unit_joins_the_next_map", modes=("ds",))
def conquest_reward_free_unit_joins_the_next_map(ctx):
    """Reinforce opens the three units on offer (Tank, Md Tank, B Copter after map 1); B goes back to the rewards; the unit taken (the second: Md Tank) is on map 2 at full HP, fuel and ammo, in addition to
    the survivors."""
    e, g, d = start(ctx)
    d.capture_enemy_hq(ctx)
    before = d.units_by_type()
    d.wait_reward()
    for _ in range(3):
        if e.u8(cq.CURSOR) == cq.REINFORCE:
            break
        e.press("RIGHT", 4)
        e.wait(8)
    e.press("A", 4)
    e.wait(20)
    ctx.eq(e.u8(cq.PAGE), 2, "the units page")
    ctx.eq(list(e.read(cq.OFFER, 3)), cq.OFFERED[0], "the three units on offer after map 1: Tank, Md Tank, B Copter")
    png(ctx, e, "reward_units")
    e.press("B", 4)
    e.wait(20)
    ctx.eq((e.u8(cq.PAGE), e.u8(cq.CURSOR)), (1, 1), "B goes back to the rewards, cursor on Reinforce")
    e.press("A", 4)
    e.wait(20)
    e.press("RIGHT", 4)
    e.wait(10)
    ctx.eq(e.u8(cq.CURSOR), 1, "the cursor is on the second unit")
    e.press("A", 4)
    for _ in range(300):
        if cq.stage(e) == 1 and e.u8(cq.STAGE_BUSY) == 0 and d.in_battle():
            break
        e.wait(20)
    g._units_base = g._players_base = None
    d.wait_control()
    after = d.units_by_type()
    ctx.eq(len(after), len(before) + 1, f"one more unit on map 2 ({len(before)} -> {len(after)})")
    new = list(after)
    for u in before:
        new.remove(u)
    ctx.eq([t for t, _ in new], [3], "the extra unit is a Md Tank")
    stats = unit_stats(e, g)
    ammo, fuel = rom_max(e, 3)
    md = [s for s in stats if s[0] == 3]
    ctx.eq((md[0][1], md[0][2], md[0][3]), (100, ammo, fuel), "full HP, ammo and fuel")
    png(ctx, e, "map2_with_the_free_unit")
    e.close()


@test(name="conquest_reward_field_repair_restores_every_survivor", modes=("ds",))
def conquest_reward_field_repair_restores_every_survivor(ctx):
    """Field repair: units worn down to 30 HP, 1 ammo and 5 fuel on map 1 arrive on map 2 at 10 HP with a full tank and magazine of their type; the war chest leaves them as they were."""
    e, g, d = start(ctx)
    worn = hurt(e, g, 3)
    ctx.eq(sum(1 for s in unit_stats(e, g) if s[1] == 30), 3, "three units worn down")
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    d.choose_reward(cq.REPAIR)
    for _ in range(300):
        if cq.stage(e) == 1 and e.u8(cq.STAGE_BUSY) == 0 and d.in_battle():
            break
        e.wait(20)
    g._units_base = g._players_base = None
    d.wait_control()
    stats = unit_stats(e, g)
    for t, hp, ammo, fuel in stats:
        am, fu = rom_max(e, t)
        ctx.eq((hp, ammo, fuel), (100, am, fu), f"type {t}: 10 HP, full ammo and fuel")
    e.close()
    # the war chest instead leaves the worn units worn (read from the stage engine's carry buffer the moment the reward is taken: on the new map the properties heal and resupply what stands on them)
    e, g, d = start(ctx)
    hurt(e, g, 3)
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    e.press("A", 4)
    e.wait(4)
    recs = carry(e)
    ctx.eq(sum(1 for r in recs if r["hp"] == 30), 3, f"the war chest does not heal ({[(r['type'], r['hp']) for r in recs]})")
    e.close()


# -- the run's enemies and Save / Continue -----------------------------------------------------------------------------------------------------------------------------

ENEMIES = cq.STATE + 0x08          # crate::conquest: the nine drawn COs (the flag is at +0x15)
PLAYER_CO = 0x1D                   # the player record's CO byte


def draw_of(e, n=cq.STAGES):
    """The run's draw: its `n` enemy COs and the flag (the draw's bytes are +0x08..+0x13, up to twelve)."""
    return list(e.read(ENEMIES, n)), e.u8(cq.STATE + 0x15)


def enemy_co(e, g):
    return e.u8(g.players_base + 0x3C * 2 + PLAYER_CO)


@test(name="conquest_enemy_cos_are_drawn_when_the_run_starts", modes=("ds",))
def conquest_enemy_cos_are_drawn_when_the_run_starts(ctx):
    """The run draws one enemy CO a map when it starts: nine different ones, never the player's, from the roster's COs that fit the enemy side; each map's army 2 has the map's CO (map 1 from the start,
    the others at each switch); another run, started a moment later, draws other ones."""
    pool = set(range(0, 19)) | set(range(72, 81)) | {92, 93}   # (AW2's 19 COs, Dual Strike's nine, Asuka and Aria; not Clone Andy 81, Crumb 82 or the Silver Nova three 86..88)
    e, g, d = start(ctx, ga.SAMI)
    cos, drawn = draw_of(e)
    ctx.eq(drawn, 1, "a draw is held")
    ctx.eq(len(set(cos)), cq.STAGES, f"nine different enemy COs ({cos})")
    ctx.check(ga.SAMI not in cos, "never the player's CO")
    ctx.check(all(c in pool for c in cos), f"all from the roster's usable COs ({cos})")
    ctx.eq(e.u8(g.players_base + 0x3C + PLAYER_CO), ga.SAMI, "the player is Sami")
    ctx.eq(enemy_co(e, g), cos[0], "map 1's enemy is the draw's first")
    for k in range(1, cq.STAGES):
        d.win_map(ctx, k - 1)
        ctx.eq(enemy_co(e, g), cos[k], f"map {k + 1}'s enemy is the draw's number {k + 1}")
        ctx.eq(draw_of(e)[0], cos, "the draw stays as it was")
    first = cos
    e.close()
    # another run, with a different wait on the army screen: another draw
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    d.open(map=cq.MISSION)
    d.wait_army()
    e.wait(97)
    d.pick_army(ga.SAMI)
    d.into_battle()
    second, _ = draw_of(e)
    ctx.check(second != first, f"a second run draws other enemies ({first} then {second})")
    ctx.eq(len(set(second)), cq.STAGES, "nine different again")
    ctx.eq(enemy_co(e, g), second[0], "and map 1's enemy is its first")
    e.close()


def resume(ctx, path, run=0):
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g, run=run)
    d.open(pick=False, box="continue")
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1800, step=10), "Continue in CONQUEST's box brings the battle back")
    g._units_base = g._players_base = None
    g.wait_for_input()
    return e, g, d


@test(name="conquest_save_and_continue_on_map_three_keeps_the_run", modes=("ds",))
def conquest_save_and_continue_on_map_three_keeps_the_run(ctx):
    """A run saved from the map menu on map 3 (Piston Dam) and continued from Select Mode: the same enemy draw (the later maps' COs too), the same map, survivors, funds and enemy army; the win of map
    3 brings map 4 with the draw's fourth CO."""
    e, g, d = start(ctx, 5)
    cos, _ = draw_of(e)
    d.win_map(ctx, 0, reward=cq.CHEST)
    d.win_map(ctx, 1, reward=cq.REINFORCE, unit=1)
    ctx.eq(cq.stage(e), 2, "on map 3")
    d.wait_control()
    g._units_base = g._players_base = None
    mine, theirs, money = d.units_by_type(1), d.units_by_type(2), (d.funds(1), d.funds(2))
    ctx.eq(enemy_co(e, g), cos[2], "map 3's enemy")
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 8) + abs(c[1] - 6))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved"))
    ctx.check(not saved.problems(), f"every slot passes its check ({saved.problems()})")
    e.close()
    e, g, d = resume(ctx, saved.path)
    ctx.eq(cq.stage(e), 2, "continued on map 3")
    ctx.eq(d.session()["mission"], cq.MISSION, "the run's mission")
    ctx.eq(d.size(), cq.MAPS[2]["size"], "Piston Dam")
    ctx.eq(draw_of(e)[0], cos, "the same nine enemy COs came back with the run")
    ctx.eq(enemy_co(e, g), cos[2], "the enemy on the field is still map 3's")
    ctx.eq((d.units_by_type(1), d.units_by_type(2)), (mine, theirs), "both armies as saved")
    ctx.eq((d.funds(1), d.funds(2)), money, "the funds as saved")
    d.win_map(ctx, 2, reward=cq.CHEST)
    ctx.eq(cq.stage(e), 3, "map 4 after the continue")
    ctx.eq(enemy_co(e, g), cos[3], "map 4's enemy is the draw's fourth CO, drawn before the save")
    e.close()


@test(name="conquest_save_and_continue_on_the_first_map_keeps_the_draw", modes=("ds",))
def conquest_save_and_continue_on_the_first_map_keeps_the_draw(ctx):
    """Saved on map 1 and continued: the draw comes back too (the later maps' COs are not re-drawn), and map 2 has the draw's second."""
    e, g, d = start(ctx, 0)
    cos, _ = draw_of(e)
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 4) + abs(c[1] - 4))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved1"))
    e.close()
    e, g, d = resume(ctx, saved.path)
    ctx.eq(cq.stage(e), 0, "continued on map 1")
    ctx.eq(draw_of(e)[0], cos, "the same draw")
    d.win_map(ctx, 0, reward=cq.CHEST)
    ctx.eq(enemy_co(e, g), cos[1], "map 2's enemy is the draw's second")
    e.close()


# -- the second run: the several-runs path (Harbor Run) --------------------------------------------------------------------------------------------------

def run_two(ctx, co=ga.ANDY):
    return start(ctx, co, run=1)


@test(name="conquest_run_two_starts_on_its_first_map", modes=("ds",))
def conquest_run_two_starts_on_its_first_map(ctx):
    """Run 2 ("Harbor Run *", mission 13) started from its row: its own first map (Pay Dirt, 16 x 12, read from the ROM), the player's starting force, the enemy's force and funds, Black Hole's colour
    for the enemy; a draw of nine enemy COs is held; the first win brings its own second map (Pivot Isle) with the draw's second CO and the reward page's war chest."""
    e, g, d = run_two(ctx, ga.SAMI)
    m = cq.RUNS[1]["maps"][0]
    ctx.eq((d.session()["mission"], d.session()["source"]), (13, ga.GAUNTLET), "the run is the Gauntlet's mission 13")
    ctx.eq(cq.stage(e), 0, "stage 0")
    ctx.eq(d.size(), m["size"], f"{m['name']}")
    ctx.eq((len(g.units(army=1)), len(g.units(army=2))), (m["mine"], m["force"]), "the starting forces")
    ctx.eq([d.owner(m["player"]), d.owner(m["enemy"])], [1, 2], "both HQs")
    ctx.eq(e.u8(g.players_base + 0x3C * 2 + 0x1A), cq.BLACK_HOLE, "the enemy wears Black Hole's colour")
    cos, drawn = draw_of(e)
    ctx.eq((drawn, len(set(cos))), (1, 9), f"nine different enemy COs are drawn ({cos})")
    ctx.check(ga.SAMI not in cos, "never the player's CO")
    ctx.eq(list(e.read(ENEMIES + 9, 3)), [0, 0, 0], "a nine-map run leaves the draw's other bytes 0")
    ctx.eq(enemy_co(e, g), cos[0], "map 1's enemy is the draw's first")
    png(ctx, e, "run2_first_turn")
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    ctx.eq((d.reward_page(), e.u8(cq.WON)), (1, 0), "the reward page opens over map 1")
    funds = d.funds(1)
    d.choose_reward(cq.CHEST)
    d.wait_stage(1, reward=cq.CHEST)
    n = cq.RUNS[1]["maps"][1]
    ctx.eq(d.size(), n["size"], f"{n['name']} is run 2's second map")
    ctx.eq(len(g.units(army=2)), n["force"], "its enemy force")
    ctx.eq(enemy_co(e, g), cos[1], "the draw's second CO")
    ctx.check(d.funds(1) >= cq.CHEST_FUNDS[0], f"the war chest came along ({funds} -> {d.funds(1)})")
    e.close()


@test(name="conquest_run_two_full_run_records_under_its_own_key", modes=("ds",))
def conquest_run_two_full_run_records_under_its_own_key(ctx):
    """Run 2's nine maps won in a row end in VICTORY; the Gauntlet's top-five table has a row for gauntlet_52 (the run's own key) with this run's CO, days and score, and none for run 1's gauntlet_51; back on
    the wheel on CONQUEST."""
    e, g, d = run_two(ctx)
    maps = cq.RUNS[1]["maps"]
    for k in range(len(maps)):
        ctx.eq(cq.stage(e), k, f"on map {k + 1}")
        ctx.eq(d.size(), maps[k]["size"], maps[k]["name"])
        g._units_base = g._players_base = None
        ctx.eq(len(g.units(army=2)), maps[k]["force"], f"{maps[k]['name']}: the enemy's starting force")
        ctx.eq([d.owner(maps[k]["player"]), d.owner(maps[k]["enemy"])], [1, 2], f"{maps[k]['name']}: both HQs")
        if k + 1 < len(maps):
            d.win_map(ctx, k)
        else:
            d.capture_enemy_hq(ctx, k)
    ctx.eq(d.through_results(), 1, "taking the last HQ wins the run")
    e.wait(60)
    got = d.results(cq.RUNS[1]["record"])
    ctx.eq(len(got), 1, f"one result under run 2's key ({got})")
    ctx.eq(d.results(cq.RUNS[0]["record"]), [], "none under run 1's")
    co, days, score = got[0]
    ctx.eq(co, ga.ANDY, "Andy's run")
    ctx.check(days >= 1 and score > 0, f"days {days}, score {score}")
    done = saves.flash(e, os.path.join(ctx.out, "finished2"))
    rec = ga.saved_record(done)
    ctx.check(rec is not None and ga.record_best(rec, 52) is not None and ga.record_best(rec, 51) is None, "the win was written to Flash slot 13 under id 52 only")
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "the wheel is on CONQUEST after the run")
    e.close()


@test(name="conquest_run_two_save_and_continue_on_map_three_keeps_its_draw", modes=("ds",))
def conquest_run_two_save_and_continue_on_map_three_keeps_its_draw(ctx):
    """Run 2 saved from the map menu on map 3 (Sole Harbor) and continued from CONQUEST's box: it is run 2 again (mission 13, its own maps), with the same enemy draw, armies and funds; the win of map 3 brings
    map 4 (Twin Isle) with the draw's fourth CO."""
    e, g, d = run_two(ctx, 5)
    cos, _ = draw_of(e)
    d.win_map(ctx, 0, reward=cq.CHEST)
    d.win_map(ctx, 1, reward=cq.REINFORCE, unit=1)
    ctx.eq(cq.stage(e), 2, "on map 3")
    d.wait_control()
    g._units_base = g._players_base = None
    mine, theirs, money = d.units_by_type(1), d.units_by_type(2), (d.funds(1), d.funds(2))
    ctx.eq(enemy_co(e, g), cos[2], "map 3's enemy")
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 6) + abs(c[1] - 6))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved2"))
    ctx.check(not saved.problems(), f"every slot passes its check ({saved.problems()})")
    e.close()
    e, g, d = resume(ctx, saved.path, run=1)
    maps = cq.RUNS[1]["maps"]
    ctx.eq(cq.stage(e), 2, "continued on map 3")
    ctx.eq(d.session()["mission"], 13, "run 2's mission")
    ctx.eq(d.size(), maps[2]["size"], maps[2]["name"])
    ctx.eq(draw_of(e)[0], cos, "the same enemy draw came back with the run")
    ctx.eq(enemy_co(e, g), cos[2], "the enemy on the field is still map 3's")
    ctx.eq((d.units_by_type(1), d.units_by_type(2)), (mine, theirs), "both armies as saved")
    ctx.eq((d.funds(1), d.funds(2)), money, "the funds as saved")
    d.win_map(ctx, 2, reward=cq.CHEST)
    ctx.eq(cq.stage(e), 3, "map 4 after the continue")
    ctx.eq(d.size(), maps[3]["size"], maps[3]["name"])
    ctx.eq(enemy_co(e, g), cos[3], "map 4's enemy is the draw's fourth CO, drawn before the save")
    e.close()


@test(name="conquest_run_two_box_and_isolation", modes=("ds",))
def conquest_run_two_box_and_isolation(ctx):
    """The box isolation holds with the second run: CONQUEST's box offers Continue over a run 2 save (and Continue is run 2); GAUNTLET goes straight to its selector over it, the save untouched; a new run
    of run 1 drops it; a new run of run 2 keeps a Gauntlet save and drops only Conquest's."""
    two = saved_run_of(ctx, lambda g: cq.Conquest(g, run=1), "conquest2_saved")
    e, g = select_mode_on(ctx, two.path)
    d = cq.Conquest(g)
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    ctx.require(e.wait_until(d.box_open, 120, step=4), "CONQUEST opens its box over a run 2 save")
    e.wait(45)
    png(ctx, e, "box_run2")
    e.press("B", 8)
    e.wait(40)
    saves.wheel_to(e, "gauntlet")
    e.press("A", 8)
    gd = ga.Gauntlet(g)
    gd.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "GAUNTLET goes to its selector at once over a Conquest run 2 save")
    ctx.check(mid_in_directory(e), "the run 2 save is still there")
    e.close()
    # Continue in CONQUEST's box is run 2
    e, g, d = resume(ctx, two.path, run=1)
    ctx.eq(d.session()["mission"], 13, "Continue in CONQUEST's box is run 2")
    e.close()
    # a new run of run 1 over the run 2 save drops it
    e, g = select_mode_on(ctx, two.path)
    d = cq.Conquest(g)
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.choose_in_box("new")
    d.wait_step(ga.SELECTOR)
    e.press("A", 6)
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.eq(d.session()["mission"], 12, "a new run of run 1")
    ctx.check(not mid_in_directory(e), "it dropped the run 2 save")
    e.close()
    # a new run 2 over a Gauntlet save keeps it
    ga_save = saved_run_of(ctx, ga.Gauntlet, "gauntlet_saved")
    e, g = select_mode_on(ctx, ga_save.path)
    d = cq.Conquest(g, run=1)
    d.open(from_title=False)
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.eq(d.session()["mission"], 13, "a run 2 started over the Gauntlet save")
    ctx.check(mid_in_directory(e), "the Gauntlet save is kept by the new run 2")
    e.close()


@test(name="conquest_an_old_cqr9_save_continues_as_run_one", modes=("ds",))
def conquest_an_old_cqr9_save_continues_as_run_one(ctx):
    """A run saved before runs had a table (tail mark CQR9: nine COs and the flag, mission 12) still continues: as run 1, with its draw. The old record is made from a new one by rewriting the tail's mark
    and length."""
    from aw2test import saveimg
    e, g, d = start(ctx, 0)
    cos, _ = draw_of(e)
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 4) + abs(c[1] - 4))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved_new"))
    e.close()

    def old_format(payload):
        i = payload.find(b"CQRM")
        assert i >= 0, "the new format's mark is in the save"
        return payload[:i] + b"CQR9" + payload[i + 4:i + 13] + payload[i + 16:i + 17] + payload[i + 17:]

    old = saveimg.rewrite_slot(saved.path, os.path.join(ctx.out, "saved_old.sav"), ga.MID_SLOT, old_format)
    chk = saveimg.Image(old).slot(ga.MID_SLOT)
    ctx.check(b"CQR9" in chk and b"CQRM" not in chk, "the save now has the old mark")
    e, g, d = resume(ctx, old, run=0)
    ctx.eq((d.session()["mission"], cq.stage(e)), (12, 0), "continued as run 1, on map 1")
    ctx.eq(draw_of(e), (cos, 1), "the old save's draw came back")
    d.win_map(ctx, 0, reward=cq.CHEST)
    ctx.eq(enemy_co(e, g), cos[1], "map 2's enemy is the draw's second")
    ctx.eq(d.size(), cq.RUNS[0]["maps"][1]["size"], "Asphalt Maze")
    e.close()


# -- the wheel entry and its box --------------------------------------------------------------------------------------------------------------------------------------------

OPTIONS, HELP = 0x08E40080, 0x08E40010      # crate::mode_menu: the open item's two lines a position, the help line a position (text ids; the wheel's own copies of AW2's tables)
TEXT_TABLE = 0x08610A38


def text_of(e, text_id):
    at = e.u32(TEXT_TABLE + 4 * text_id)
    out = bytearray()
    while len(out) < 80 and e.u8(at + len(out)):
        out.append(e.u8(at + len(out)))
    return out.decode("latin-1")


def mid_in_directory(e):
    """Slot 12 is in the game's save directory (crate::suspend::DIRECTORY, 16 sector slots)."""
    return ga.MID_SLOT in list(e.read(0x0200CC38, 16))


@test(name="conquest_wheel_entry_has_its_label_and_help_line", modes=("ds",))
def conquest_wheel_entry_has_its_label_and_help_line(ctx):
    """CONQUEST is the wheel's position 5 (item 10), directly above GAUNTLET: its help line says what the mode is, the label is on the screen (pictures of the wheel on it, and on GAUNTLET under it); no
    Continue / New box opens with no run saved (A goes to the selector at once)."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    saves.to_select_mode(e)
    ctx.eq(ga.wheel_items(e), [2, 4, 3, 1, 9, 10, 0, 5, 8], "the nine entries: Conquest above Gauntlet")
    ctx.eq(saves.position(e, "conquest"), 5, "position 5")
    pos = saves.position(e, "conquest")
    ctx.eq(text_of(e, e.u16(HELP + 2 * pos)), "Win every map in a row. One loss ends the run.", "the help line")
    ctx.eq([text_of(e, e.u16(OPTIONS + 2 * (2 * pos + k))) for k in (0, 1)], ["Continue your saved Conquest run.", "Start a new run. The saved run is dropped."], "the box's two lines")
    ctx.eq(text_of(e, e.u16(HELP + 2 * saves.position(e, "gauntlet"))), "Beat a map's COs one after another.", "the Gauntlet's help line is its own")
    saves.wheel_to(e, "conquest")
    e.wait(40)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "the cursor is on CONQUEST")
    png(ctx, e, "wheel_on_conquest")
    saves.wheel_to(e, "gauntlet")
    e.wait(40)
    png(ctx, e, "wheel_on_gauntlet")
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "with no run saved A goes to the selector, no box")
    ctx.eq(e.u8(ga.CONTINUING), 0, "a new run")
    e.close()


def saved_run_of(ctx, driver, name):
    """A run of `driver` (Conquest or Gauntlet) saved halfway from the map menu: the Flash image after it."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = driver(g)
    d.begin(ga.ANDY) if hasattr(d, "begin") else d.start(ga.ANDY)
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, name))
    ctx.check(ga.MID_SLOT in saved.tags(), f"{name}: the run is saved in slot 12")
    e.close()
    return saved


def select_mode_on(ctx, path):
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    return e, g


@test(name="conquest_box_is_offered_for_a_conquest_save_only", modes=("ds",))
def conquest_box_is_offered_for_a_conquest_save_only(ctx):
    """The shared mid-battle slot holds one run. With a Conquest run saved, CONQUEST opens the Continue / New box (its own two lines under the wheel) and GAUNTLET starts at its selector at once (no
    box, the save untouched); with a Gauntlet run saved it is the other way round. Pictures of the box."""
    cq_save = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    e, g = select_mode_on(ctx, cq_save.path)
    d = cq.Conquest(g)
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    ctx.require(e.wait_until(d.box_open, 120, step=4), "CONQUEST opens its box over a Conquest save")
    e.wait(45)
    png(ctx, e, "box_conquest")
    pos = saves.position(e, "conquest")
    ctx.check(d.box_open(), "the box is open")
    e.press("B", 8)
    e.wait(40)
    saves.wheel_to(e, "gauntlet")
    e.press("A", 8)
    gd = ga.Gauntlet(g)
    gd.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "GAUNTLET goes to its selector at once over a Conquest save")
    ids, _ = gd.selector_ids()
    ctx.eq([gd.entry_name(i) for i in ids], ga.SELECTOR_TITLES, "the Gauntlet's own maps")
    ctx.check(mid_in_directory(e), "the Conquest save is still there")
    e.close()
    ga_save = saved_run_of(ctx, ga.Gauntlet, "gauntlet_saved")
    e, g = select_mode_on(ctx, ga_save.path)
    d = cq.Conquest(g)
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "CONQUEST goes to its selector at once over a Gauntlet save")
    ids, _ = d.selector_ids()
    ctx.eq([d.entry_name(i) for i in ids], ga.CONQUEST_TITLES, "the runs' rows")
    ctx.check(mid_in_directory(e), "the Gauntlet save is still there")
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e.wait(60)
    saves.wheel_to(e, "gauntlet")
    e.press("A", 8)
    ctx.require(e.wait_until(d.box_open, 120, step=4), "GAUNTLET opens its box over its own save")
    e.wait(45)
    png(ctx, e, "box_gauntlet")
    e.close()


@test(name="conquest_new_run_drops_only_its_own_save", modes=("ds",))
def conquest_new_run_drops_only_its_own_save(ctx):
    """A new Gauntlet run over a Conquest save leaves it in the slot (and the other way round): only the mode's own save is dropped when its new run really starts. And Continue in CONQUEST's box
    brings its run back (the Conquest mission, not the Gauntlet's)."""
    cq_save = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    e, g = select_mode_on(ctx, cq_save.path)
    gd = ga.Gauntlet(g)
    gd.open(from_title=False, map=0)
    gd.pick_army(ga.ANDY)
    gd.into_battle()
    ctx.eq(gd.session()["mission"], 0, "a Gauntlet run (Cinder Sea) started over the Conquest save")
    ctx.check(mid_in_directory(e), "the Conquest save is kept by the Gauntlet's new run")
    e.close()
    e, g = select_mode_on(ctx, cq_save.path)
    d = cq.Conquest(g)
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.choose_in_box("new")
    d.wait_step(ga.SELECTOR)
    e.press("A", 6)
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.check(not mid_in_directory(e), "a new Conquest run drops the Conquest save")
    e.close()
    e, g, d = resume(ctx, cq_save.path)
    ctx.eq(d.session()["mission"], cq.MISSION, "Continue in CONQUEST's box is the Conquest run")
    e.close()
    ga_save = saved_run_of(ctx, ga.Gauntlet, "gauntlet_saved")
    e, g = select_mode_on(ctx, ga_save.path)
    d = cq.Conquest(g)
    d.open(from_title=False)
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.eq(d.session()["mission"], cq.MISSION, "a Conquest run started over the Gauntlet save")
    ctx.check(mid_in_directory(e), "the Gauntlet save is kept by the new Conquest run")
    e.close()


# -- CONTINUE: the wheel's tenth entry, on it only while a Conquest run is saved halfway (crate::mode_menu::TABLE_SAVED) ------------------------------------------------------------------

CONTINUE_AT = 0x08E43000            # crate::mode_menu::CONTINUE_AT: its palette (32 bytes), highlight, big label (+0xC0), small label (+0x8C0)
CONTINUE_TILES = (0x304, 0x30C, 0x314, 0x3D0)   # crate::mode_menu::CONTINUE_SMALL_TILES: its four small-label sprites (eight tiles each)
CONTINUE_LENT = ((2, 9), (3, 10), (5, 11), (15, 12))   # crate::mode_menu::CONTINUE_LENT: its colours in bank 15
OBJ_VRAM, OBJ_PALETTES = 0x06010000, 0x05000200
NINE = [2, 4, 3, 1, 9, 10, 0, 5, 8]
TEN = [2, 4, 3, 1, 9, 10, 11, 0, 5, 8]
CONTINUE_HELP = "Continue your saved Conquest run."


def on_wheel(ctx, e, items, what):
    ctx.eq(ga.wheel_items(e), items, what)
    ctx.eq(saves.wheel_size(e), len(items), "the harness knows the wheel's size")


def wheel_round(ctx, e, n):
    """Every position of the wheel is reached in turn (UP from 0 to n-1, as the harness turns it) and one more UP from the last wraps to 0: the wheel has exactly n positions."""
    for p in range(n):
        saves.wheel_to(e, p)
        ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), p, f"position {p} reached")
    e.press("UP", 8)
    e.wait(80)
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), 0, f"UP from position {n - 1} wraps to 0")


def saved_on_map_three(ctx, run=0, name="saved_three"):
    """Run `run` (0-based) played to map 3 and saved from the map menu: (the Flash image, the draw, both armies, the funds, the enemy CO on the field)."""
    e, g, d = start(ctx, 5, run=run)
    cos, _ = draw_of(e)
    d.win_map(ctx, 0, reward=cq.CHEST)
    d.win_map(ctx, 1, reward=cq.REINFORCE, unit=1)
    ctx.eq(cq.stage(e), 2, "on map 3")
    d.wait_control()
    g._units_base = g._players_base = None
    mine, theirs, money = d.units_by_type(1), d.units_by_type(2), (d.funds(1), d.funds(2))
    enemy = enemy_co(e, g)
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 6) + abs(c[1] - 6))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, name))
    ctx.check(not saved.problems(), f"every slot passes its check ({saved.problems()})")
    e.close()
    return saved, cos, mine, theirs, money, enemy


@test(name="conquest_continue_is_not_on_the_wheel_without_a_save", modes=("ds",))
def conquest_continue_is_not_on_the_wheel_without_a_save(ctx):
    """With no Conquest run saved the wheel is exactly the nine entries it was: no CONTINUE in the item table, the help or box tables, the wraps are the nine-entry ones and the cursor goes round in nine UP steps (CONQUEST is position 5, Campaign 6). Pictures of the wheel on CONQUEST and on Campaign."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    on_wheel(ctx, e, NINE, "the nine entries")
    ctx.check(not saves.with_continue(e), "no CONTINUE")
    try:
        saves.position(e, "continue")
        ctx.check(False, "the harness finds no CONTINUE position")
    except Exception:
        pass
    ctx.eq([saves.position(e, n) for n in ("gauntlet", "conquest", "campaign", "war_room", "survival")], [4, 5, 6, 7, 8], "the entries' positions")
    ctx.eq(e.u16(0x08080F7E), 0x2908, "the position bound is the nine-entry one")
    ctx.eq(e.u16(0x08081DF0), 0x2808, "UP wraps 8 -> 0")
    ctx.eq(e.u8(0x08080F6A), 0x09, "DivRem(x, 9) in SetMainMenuCarouselPosition")
    ctx.check(text_of(e, e.u16(HELP + 2 * 6)) != CONTINUE_HELP, "position 6's help line is Campaign's")
    ctx.eq((e.u8(saves.SELECT_MODE_CURSOR), ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)]), (6, 0), "the wheel opens on Campaign (position 6) as it always did")
    wheel_round(ctx, e, 9)
    saves.wheel_to(e, "conquest")
    e.wait(40)
    png(ctx, e, "wheel_nosave_conquest")
    saves.wheel_to(e, "campaign")
    e.wait(40)
    png(ctx, e, "wheel_nosave_campaign")
    e.close()


@test(name="conquest_continue_is_on_the_wheel_over_a_conquest_save", modes=("ds",))
def conquest_continue_is_on_the_wheel_over_a_conquest_save(ctx):
    """With a Conquest run saved halfway the wheel has ten entries: CONTINUE (item 11) at position 6, directly above CONQUEST (5); Campaign, War Room and Survival are one higher; its help line is 'Continue your
    saved Conquest run.', its label is in the OBJ tiles and the bank-15 colours the game draws it with, and CONQUEST's box is still there (A on CONQUEST opens Continue / New). Ten UP steps go once round."""
    saved = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    e, g = select_mode_on(ctx, saved.path)
    d = cq.Conquest(g)
    on_wheel(ctx, e, TEN, "ten entries: CONTINUE directly above CONQUEST")
    ctx.eq([saves.position(e, n) for n in ("gauntlet", "conquest", "continue", "campaign", "war_room", "survival")], [4, 5, 6, 7, 8, 9], "the entries' positions")
    ctx.eq((e.u8(saves.SELECT_MODE_CURSOR), ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)]), (7, 0), "the wheel opens on Campaign, which is position 7 with CONTINUE below it")
    ctx.eq(text_of(e, e.u16(HELP + 2 * 6)), CONTINUE_HELP, "CONTINUE's help line")
    ctx.eq(text_of(e, e.u16(HELP + 2 * 5)), "Win every map in a row. One loss ends the run.", "CONQUEST's is still its own")
    ctx.eq([text_of(e, e.u16(OPTIONS + 2 * (2 * 5 + k))) for k in (0, 1)], ["Continue your saved Conquest run.", "Start a new run. The saved run is dropped."], "CONQUEST's box lines")
    ctx.eq([e.u16(OPTIONS + 2 * (2 * 6 + k)) for k in (0, 1)], [0, 0], "CONTINUE has no box")
    wheel_round(ctx, e, 10)
    # the label: on the wheel the small label's sprites hold CONTINUE's art, the bank holds its colours beside CONQUEST's
    saves.wheel_to(e, "continue")
    e.wait(40)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 11, "the cursor is on CONTINUE")
    art = e.read(CONTINUE_AT + 0x8C0, 1024)
    for k, first in enumerate(CONTINUE_TILES):
        ctx.check(e.read(OBJ_VRAM + 32 * first, 256) == art[256 * k:256 * k + 256], f"small label sprite {k} is in tiles {first:#x}..")
    pal = e.read(CONTINUE_AT, 32)
    bank = e.read(OBJ_PALETTES + 32 * 15, 32)
    for frm, to in CONTINUE_LENT:
        ctx.eq(bank[2 * to:2 * to + 2], pal[2 * frm:2 * frm + 2], f"bank 15 colour {to} is CONTINUE's {frm}")
    conquest_pal = e.read(0x08E42000, 32)
    for i in (1, 2, 3, 5, 15):
        ctx.eq(bank[2 * i:2 * i + 2], conquest_pal[2 * i:2 * i + 2], f"bank 15 colour {i} is still CONQUEST's")
    png(ctx, e, "wheel_on_continue")
    saves.wheel_to(e, "conquest")
    e.wait(40)
    png(ctx, e, "wheel_on_conquest_with_a_save")
    e.press("A", 8)
    ctx.require(e.wait_until(d.box_open, 120, step=4), "A on CONQUEST still opens its Continue / New box")
    e.wait(45)
    png(ctx, e, "box_conquest_beside_continue")
    e.close()


def resume_by_continue(ctx, path, run=0):
    """The saved run brought back by CONTINUE on the wheel (no box): the battle is on again."""
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g, run=run)
    d.open_continue()
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1800, step=10), "CONTINUE brings the battle back at once")
    ctx.check(not d.box_open(), "no box")
    g._units_base = g._players_base = None
    g.wait_for_input()
    return e, g, d


def continue_resumes(ctx, run, name):
    saved, cos, mine, theirs, money, enemy = saved_on_map_three(ctx, run, name)
    e, g, d = resume_by_continue(ctx, saved.path, run)
    maps = cq.RUNS[run]["maps"]
    ctx.eq(cq.stage(e), 2, "continued on map 3")
    ctx.eq(d.session()["mission"], cq.RUNS[run]["mission"], f"run {run + 1}'s mission")
    ctx.eq(d.size(), maps[2]["size"], maps[2]["name"])
    ctx.eq(draw_of(e)[0], cos, "the same enemy draw came back with the run")
    ctx.eq(enemy_co(e, g), enemy, "the enemy on the field is still map 3's")
    ctx.eq((d.units_by_type(1), d.units_by_type(2)), (mine, theirs), "both armies as saved")
    ctx.eq((d.funds(1), d.funds(2)), money, "the funds as saved")
    d.win_map(ctx, 2, reward=cq.CHEST)
    ctx.eq(cq.stage(e), 3, "map 4 after the continue")
    ctx.eq(enemy_co(e, g), cos[3], "map 4's enemy is the draw's fourth CO")
    e.close()


@test(name="conquest_continue_resumes_run_one_on_a_later_map", modes=("ds",))
def conquest_continue_resumes_run_one_on_a_later_map(ctx):
    """CONTINUE on the wheel over a Conquest Run saved on map 3: A goes straight back into the battle (no box): map 3, the enemy draw, both armies, the funds; the win of map 3 brings map 4 with the draw's fourth CO."""
    continue_resumes(ctx, 0, "saved_three")


@test(name="conquest_continue_resumes_run_two_on_a_later_map", modes=("ds",))
def conquest_continue_resumes_run_two_on_a_later_map(ctx):
    """The same over a Harbor Run (run 2) saved on map 3: it is run 2 again (mission 13, its maps), CONTINUE is the same entry for both runs."""
    continue_resumes(ctx, 1, "saved_three_run2")


@test(name="conquest_continue_is_not_on_the_wheel_over_a_gauntlet_save", modes=("ds",))
def conquest_continue_is_not_on_the_wheel_over_a_gauntlet_save(ctx):
    """The shared slot holds a Gauntlet run: that is not a Conquest save, so the wheel is the nine entries (CONQUEST goes straight to its selector, GAUNTLET offers its own box)."""
    ga_save = saved_run_of(ctx, ga.Gauntlet, "gauntlet_saved")
    e, g = select_mode_on(ctx, ga_save.path)
    on_wheel(ctx, e, NINE, "no CONTINUE over a Gauntlet save")
    ctx.eq(saves.position(e, "campaign"), 6, "Campaign is where it is without a save")
    png(ctx, e, "wheel_gauntlet_save")
    e.close()


@test(name="conquest_continue_is_gone_after_a_new_run_drops_the_save", modes=("ds",))
def conquest_continue_is_gone_after_a_new_run_drops_the_save(ctx):
    """Over a Conquest save CONQUEST's box -> New starts a new run, which drops the save: in the same session, when the run ends and Select Mode comes back, the wheel is the nine entries again (no reboot),
    CONQUEST is selected (the wheel's remembered position follows the run), and Campaign is position 6."""
    saved = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    e, g = select_mode_on(ctx, saved.path)
    d = cq.Conquest(g)
    on_wheel(ctx, e, TEN, "CONTINUE is there before the new run")
    saves.wheel_to(e, "conquest")
    e.press("A", 8)
    d.choose_in_box("new")
    d.wait_step(ga.SELECTOR)
    e.press("A", 6)
    d.pick_army(ga.ANDY)
    d.into_battle()
    ctx.check(not mid_in_directory(e), "the new run dropped the save")
    d.wait_control()
    ctx.eq(d.lose(ctx), 2, "the run is lost")
    ctx.check(d.select_mode_up(), "back on Select Mode in the same session")
    e.wait(60)
    on_wheel(ctx, e, NINE, "CONTINUE is gone in the same session")
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 10, "the wheel is on CONQUEST")
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), 5, "position 5")
    png(ctx, e, "wheel_after_the_save_went")
    e.close()


@test(name="conquest_the_wheel_keeps_its_position_through_a_run_with_a_save", modes=("ds",))
def conquest_the_wheel_keeps_its_position_through_a_run_with_a_save(ctx):
    """The remembered position with and without CONTINUE. Over a Conquest save the wheel opens on the entry last left (CONTINUE at 6, Campaign at 7 in its ten); B from CONQUEST's selector goes back to
    CONQUEST (5). A run resumed with CONTINUE and then lost comes back to Select Mode on CONQUEST (5) with the nine-entry wheel; Campaign is 6 again, not 7."""
    saved = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    # B from the selector over the save is not possible (CONQUEST opens its box first): on Campaign, then the Gauntlet selector and back on the wheel
    e, g = select_mode_on(ctx, saved.path)
    saves.wheel_to(e, "gauntlet")
    e.press("A", 8)
    gd = ga.Gauntlet(g)
    gd.wait_step(ga.SELECTOR)
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: gd.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e.wait(60)
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 9, "back on GAUNTLET (position 4)")
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), 4, "position 4 with CONTINUE on the wheel")
    ctx.check(saves.with_continue(e), "CONTINUE is still on the wheel")
    e.close()
    # the wheel on CAMPAIGN (7) with CONTINUE, a trip to Gauntlet's selector is not needed: the remembered position is kept by the layout
    e, g, d = resume_by_continue(ctx, saved.path)
    d.wait_control()
    ctx.eq(d.lose(ctx), 2, "the resumed run is lost")
    ctx.check(d.select_mode_up(), "back on Select Mode")
    e.wait(60)
    on_wheel(ctx, e, NINE, "the run ended: the save is gone, nine entries")
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), 5, "the wheel is on CONQUEST, position 5")
    ctx.eq(saves.position(e, "campaign"), 6, "Campaign is 6 again")
    e.close()


@test(name="conquest_continue_follows_the_save_within_one_session", modes=("ds",))
def conquest_continue_follows_the_save_within_one_session(ctx):
    """No reboot between: a Conquest run saved from the map menu puts CONTINUE on the wheel at once (the layout follows the save while the wheel is not up; the wheel's remembered position keeps its entry:
    Campaign 6 becomes 7), and when the run ends (the save dropped) it is gone again, the wheel back on CONQUEST with nine entries."""
    e, g, d = start(ctx)
    on_wheel(ctx, e, NINE, "no CONTINUE while no run is saved")
    e.w32(ga.WHEEL_LAST, 6)
    d.wait_control()
    g._units_base = g._players_base = None
    saves.suspend(g)
    on_wheel(ctx, e, TEN, "CONTINUE is on the wheel right after the save")
    ctx.eq(e.u32(ga.WHEEL_LAST), 7, "the remembered Campaign (6) is 7 with CONTINUE below it")
    e.w32(ga.WHEEL_LAST, 6)
    ctx.eq(d.lose(ctx), 2, "the run is lost (its save dropped)")
    ctx.check(d.select_mode_up(), "back on Select Mode in the same session")
    e.wait(60)
    on_wheel(ctx, e, NINE, "CONTINUE is gone with the save")
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), 5, "the wheel is on CONQUEST")
    e.close()


@test(name="conquest_continue_goes_when_a_gauntlet_save_takes_the_slot", modes=("ds",))
def conquest_continue_goes_when_a_gauntlet_save_takes_the_slot(ctx):
    """Over a Conquest save (CONTINUE on the wheel) a new Gauntlet run is started and saved from the map menu: the slot is the Gauntlet's now, so CONTINUE is gone in the same session and after the run's
    end the wheel has nine entries."""
    saved = saved_run_of(ctx, cq.Conquest, "conquest_saved")
    e, g = select_mode_on(ctx, saved.path)
    on_wheel(ctx, e, TEN, "CONTINUE over the Conquest save")
    gd = ga.Gauntlet(g)
    gd.open(from_title=False, map=0)
    gd.pick_army(ga.ANDY)
    gd.into_battle()
    gd.wait_control()
    on_wheel(ctx, e, TEN, "a Gauntlet run in play does not take the slot yet")
    g._units_base = g._players_base = None
    saves.suspend(g)
    on_wheel(ctx, e, NINE, "the Gauntlet's save replaced the Conquest save: no CONTINUE")
    e.close()


# -- the kit's commands: `aw2dev conquest start` and `aw2dev conquest sheet` --------------------------------------------------------------------------------------------

_TOOL_CO = int(os.environ.get("AW2TEST_CONQUEST_CO", "0") or 0)
LOOKS = (
    ("aw2", {}),
    ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
    ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1"}),
)


@test(name="conquest_tool_start", modes=("ds",))
def conquest_tool_start(ctx):
    """`aw2dev conquest start [--co N]`: from the title to the run's second map with a picture of each screen on the way: the wheel on CONQUEST, the one-row selector, the army screen, map 1's first
    turn, the reward page, the unit page, map 2's first turn (AW2TEST_CONQUEST_CO names the CO, default Andy; AW2TEST_CONQUEST_OUT where the pictures go)."""
    import shutil
    co = _TOOL_CO or ga.ANDY
    out = os.environ.get("AW2TEST_CONQUEST_OUT")
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, "conquest")
    e.wait(40)
    png(ctx, e, "1_wheel")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    png(ctx, e, "2_map_selector")
    e.press("A", 6)
    d.wait_army()
    png(ctx, e, "3_army_screen")
    d.pick_army(co)
    d.into_battle()
    png(ctx, e, "4_first_turn")
    ctx.eq(g.player(1)["co"], co, "the pick leads the player's army")
    d.capture_enemy_hq(ctx)
    d.wait_reward()
    png(ctx, e, "5_reward_page")
    e.press("RIGHT", 4)
    e.wait(10)
    e.press("A", 4)
    e.wait(20)
    png(ctx, e, "6_reward_units")
    e.press("A", 4)
    for _ in range(300):
        if cq.stage(e) == 1 and e.u8(cq.STAGE_BUSY) == 0 and d.in_battle():
            break
        e.wait(20)
    g._units_base = g._players_base = None
    d.wait_control()
    png(ctx, e, "7_second_map")
    ctx.log(f"pictures in {ctx.out}")
    if out:
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(ctx.out)):
            if f[:1].isdigit() and f.endswith(".png"):
                shutil.copy(os.path.join(ctx.out, f), os.path.join(out, f))
    e.close()


@test(name="conquest_pictures", modes=("ds",))
def conquest_pictures(ctx):
    """The whole run in the three looks (AW2 graphics, Dual Strike graphics with the tilt, without it): the reward page, the unit page and each of the nine maps' first turn, one row a look on one
    contact sheet `conquest_sheet.png` (AW2TEST_SHEET copies it where a person looks). AW2TEST_CONQUEST_RUN (1-based, default 1) picks the run: `aw2dev conquest sheet --run 2`."""
    from PIL import Image, ImageDraw
    run = max(1, int(os.environ.get("AW2TEST_CONQUEST_RUN", "1") or 1)) - 1
    stages = len(cq.RUNS[run]["maps"])
    rows = []
    for look, env in LOOKS:
        e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = cq.Conquest(g, run=run)
        d.begin(ga.ANDY)
        shots = {}
        shots["map1"] = png(ctx, e, f"{look}_map1")
        for k in range(stages):
            if k + 1 == stages:
                break
            d.capture_enemy_hq(ctx, k)
            d.wait_reward()
            if k == 0:
                shots["reward"] = png(ctx, e, f"{look}_reward")
                e.press("RIGHT", 4)
                e.wait(10)
                e.press("A", 4)
                e.wait(24)
                shots["units"] = png(ctx, e, f"{look}_units")
                e.press("B", 4)
                e.wait(10)
                e.press("LEFT", 4)
                e.wait(10)
            d.wait_stage(k + 1, reward=cq.CHEST)
            shots[f"map{k + 2}"] = png(ctx, e, f"{look}_map{k + 2}")
        order = ["reward", "units"] + [f"map{k + 1}" for k in range(stages)]
        rows.append((look, [Image.open(shots[n]).convert("RGB") for n in order if n in shots]))
        e.close()
    w, h = rows[0][1][0].size
    cols = max(len(r[1]) for r in rows)
    sheet = Image.new("RGB", (cols * (w + 4) + 4, len(rows) * (h + 4) + 4), (40, 40, 40))
    for r, (look, imgs) in enumerate(rows):
        for c, im in enumerate(imgs):
            sheet.paste(im, (4 + c * (w + 4), 4 + r * (h + 4)))
    p = os.path.join(ctx.out, "conquest_sheet.png")
    sheet.save(p)
    dest = os.environ.get("AW2TEST_SHEET")
    if dest:
        import shutil
        shutil.copy(p, dest)
    ctx.log(f"sheet {p}: rows {[r[0] for r in rows]}")
    ctx.check(all(len(r[1]) == stages + 2 for r in rows), "the reward page, the units and every map: a picture each in every look")
