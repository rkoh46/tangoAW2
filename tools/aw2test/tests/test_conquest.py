"""Conquest Run (crate::conquest, docs/dev/conquest.md): the first row of the Gauntlet's map selector, a run of five AW2 Versus maps with the survivors and funds carried over, one loss ends it, a win after
the fifth map records a result. `-k conquest`."""

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


def start(ctx, co=ga.ANDY, colour=None, save=None, env=None):
    """Conquest Run started from Select Mode: (emu, game, driver) with the player in control on day 1 of the first map."""
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    d.begin(co, colour)
    return e, g, d


@test(name="conquest_row_is_first_with_its_title", modes=("ds",))
def conquest_row_is_first_with_its_title(ctx):
    """The selector lists Conquest Run * first (the star: several maps), whatever its count of enemies; the cursor starts on it and A takes it to the army screen."""
    e, g, d = (lambda e: (e, Game(e, ctx.image), None))(Emu(save=paths.base_save(), ds=ctx.ds))
    ctx.games.append(g)
    d = cq.Conquest(g)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq([d.entry_name(i) for i in ids][0], "Conquest Run *", "the first row")
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (0, cq.MISSION), "the cursor starts on it: mission 12")
    ctx.eq(len(ids), len(ga.SELECTOR_ORDER), "every map is listed")
    e.press("A", 6)
    d.wait_army()
    ctx.eq(e.u8(ga.UI_MAP), cq.MISSION, "A took Conquest Run to the army screen")
    free = ga.shown(e)[2]
    ctx.check(cq.BLACK_HOLE not in free, f"the enemy wears Black Hole's colour, so the player's pick leaves it ({free})")
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
    """AW2's DEFEAT ends the run: results, Select Mode on GAUNTLET, the result 2 (lost), nothing recorded and no run saved."""
    e, g, d = start(ctx)
    ctx.eq(d.lose(ctx), 2, "the run is lost")
    ctx.check(d.select_mode_up(), "back on Select Mode")
    ctx.eq(d.results(cq.RECORD_ID), [], "a loss writes no result")
    ctx.eq(e.u8(dc.ACTIVE), 0, "the session is over")
    e.close()


@test(name="conquest_a_full_run_records_a_result", modes=("ds",))
def conquest_a_full_run_records_a_result(ctx):
    """Five maps won in a row (each by the HQ capture) end in VICTORY, and the Gauntlet's top-five table has a row for gauntlet_50 with this run's CO, days and score."""
    e, g, d = start(ctx)
    for k in range(cq.STAGES):
        ctx.eq(cq.stage(e), k, f"on map {k + 1}")
        ctx.eq(d.size(), cq.MAPS[k]["size"], f"{cq.MAPS[k]['name']}")
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

ENEMIES = cq.STATE + 0x10          # crate::conquest: the five drawn COs, then the flag
PLAYER_CO = 0x1D                   # the player record's CO byte


def draw_of(e):
    return list(e.read(ENEMIES, 5)), e.u8(ENEMIES + 5)


def enemy_co(e, g):
    return e.u8(g.players_base + 0x3C * 2 + PLAYER_CO)


@test(name="conquest_enemy_cos_are_drawn_when_the_run_starts", modes=("ds",))
def conquest_enemy_cos_are_drawn_when_the_run_starts(ctx):
    """The run draws one enemy CO a map when it starts: five different ones, never the player's, from the roster's COs that fit the enemy side; each map's army 2 has the map's CO (map 1 from the start,
    the others at each switch); another run, started a moment later, draws other ones."""
    pool = set(range(0, 19)) | set(range(72, 81)) | {92, 93}   # (AW2's 19 COs, Dual Strike's nine, Asuka and Aria; not Clone Andy 81, Crumb 82 or the Silver Nova three 86..88)
    e, g, d = start(ctx, ga.SAMI)
    cos, drawn = draw_of(e)
    ctx.eq(drawn, 1, "a draw is held")
    ctx.eq(len(set(cos)), 5, f"five different enemy COs ({cos})")
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
    ctx.eq(len(set(second)), 5, "five different again")
    ctx.eq(enemy_co(e, g), second[0], "and map 1's enemy is its first")
    e.close()


def resume(ctx, path):
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    d.open(pick=False, box="continue")
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1800, step=10), "GAUNTLET on Select Mode brings the battle back")
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
    ctx.eq(draw_of(e)[0], cos, "the same five enemy COs came back with the run")
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


# -- the kit's commands: `aw2dev conquest start` and `aw2dev conquest sheet` --------------------------------------------------------------------------------------------

_TOOL_CO = int(os.environ.get("AW2TEST_CONQUEST_CO", "0") or 0)
LOOKS = (
    ("aw2", {}),
    ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
    ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1"}),
)


@test(name="conquest_tool_start", modes=("ds",))
def conquest_tool_start(ctx):
    """`aw2dev conquest start [--co N]`: from the title to the run's second map with a picture of each screen on the way: the wheel on GAUNTLET, the selector on Conquest Run, the army screen, map 1's first
    turn, the reward page, the unit page, map 2's first turn (AW2TEST_CONQUEST_CO names the CO, default Andy; AW2TEST_CONQUEST_OUT where the pictures go)."""
    import shutil
    co = _TOOL_CO or ga.ANDY
    out = os.environ.get("AW2TEST_CONQUEST_OUT")
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = cq.Conquest(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, "gauntlet")
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
    """The whole run in the three looks (AW2 graphics, Dual Strike graphics with the tilt, without it): the reward page, the unit page and each of the five maps' first turn, one row a look on one
    contact sheet `conquest_sheet.png` (AW2TEST_SHEET copies it where a person looks)."""
    from PIL import Image, ImageDraw
    rows = []
    for look, env in LOOKS:
        e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = cq.Conquest(g)
        d.begin(ga.ANDY)
        shots = {}
        shots["map1"] = png(ctx, e, f"{look}_map1")
        for k in range(cq.STAGES):
            if k + 1 == cq.STAGES:
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
        order = ["reward", "units"] + [f"map{k + 1}" for k in range(cq.STAGES)]
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
    ctx.check(all(len(r[1]) == 7 for r in rows), "seven pictures a look: the reward page, the units and the five maps")
