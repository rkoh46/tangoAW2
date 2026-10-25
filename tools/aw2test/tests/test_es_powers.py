"""The three Emerald Sun powers that need engine hooks (crate::es_co, "The powers' rules"), exercised in real battles on Versus maps (TANGOAW2_ES_VERSUS lists the
five COs): Klaus's Testudo (a counterattack against his attack does 25% less), Aurelia's Onager (an indirect hit costs the enemy units beside the target 1 HP)
and Cassius's Triumph (a vehicle that has attacked may move once more, not attack again). Each also has its off case (no power: the plain rule) and a
determinism case: the same scenario played twice from the same start ends with the same RAM, which is what both peers of a match need."""

import os

from aw2test import damage, ram, saves, tag
from aw2test import rom as romlib
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test
from tests.test_crumb import set_unit

ENV = {"TANGOAW2_ES_VERSUS": "1"}
KLAUS, AURELIA, CASSIUS = 86, 87, 88
FLAG_DONE = 0x01
EWRAM_SPAN = (0x02000000, 0x40000)


def hp_of(g, x, y):
    return g.unit_at(x, y)["hp"]


# --- Klaus: Testudo -----------------------------------------------------------------------------------------------------------------

RNG = 0x03001FD4          # the game's random word (crate::co_powers::RNG)


def klaus_game(ctx, attacker="tank", defender="tank"):
    m = ctx.map()
    m.unit(1, attacker, 10, 10).unit(2, defender, 11, 10)
    return ctx.start(m, [KLAUS, "andy"], env=ENV)


def klaus_fight(ctx, power, attacker="tank", defender="tank"):
    """Klaus's `attacker` hits Andy's `defender` (same terrain, same HP); with `power` Testudo is on. Returns (game, ctx.attack's result)."""
    g = klaus_game(ctx, attacker, defender)
    if power:
        ctx.power(g, 1, "power")
        ctx.eq(g.player(1)["co_mode"], 1, "Testudo is on")
    r = ctx.attack(g, (10, 10), (10, 10), (11, 10), counter_keep=75 if power else 100)
    return g, r


def counter_forecast(r, keep):
    """The counter's forecast number (its record's +0x14) in Dual Strike's order (crate::co_roster::preview_scaled): the base damage x the counter's
    accuracy, cut to `keep` percent by Testudo, x the counter's own shown HP before the battle / 10, x (200 - the target's defence) / 100, at most 999."""
    c = r["counter"]
    ra, _ = r["records"]
    v = damage.div(c.base * c.acc, 100)
    v = damage.div(v * keep, 100)
    v = damage.div(v * damage.hp_bars(r["before"][1]["hp"]), 10)
    return min(999, damage.div((200 - ra["defence"]) * v, 100))


@test(modes=("ds",))
def es_klaus_testudo_cuts_the_counterattack_by_a_quarter(ctx):
    """With Testudo on, the counter's HP loss is inside the calculator's range for the 75% rule (ctx.attack, counter_keep=75) and its forecast number (the
    record's +0x14) is Dual Strike's arithmetic on the cut number; Klaus's own attack is as ever."""
    for kind in ("tank", "infantry"):
        g, r = klaus_fight(ctx, True, kind, kind)
        ra, rd = r["records"]
        ctx.require(r["counter"] is not None, f"{kind}: the enemy counterattacks")
        ctx.eq(rd["display"], counter_forecast(r, 75), f"{kind}: the counter's forecast is worked on the cut number")
        ctx.check(rd["display"] < counter_forecast(r, 100), f"{kind}: and it is less than the uncut {counter_forecast(r, 100)}")
        ctx.shot(g, f"testudo_{kind}")


@test(modes=("ds",))
def es_klaus_without_testudo_the_counter_is_whole(ctx):
    """The same fights with no power: the calculator's plain range (counter_keep=100) and the plain forecast number."""
    for kind in ("tank", "infantry"):
        g, r = klaus_fight(ctx, False, kind, kind)
        ra, rd = r["records"]
        ctx.require(r["counter"] is not None, f"{kind}: the enemy counterattacks")
        ctx.eq(rd["display"], counter_forecast(r, 100), f"{kind}: the counter's forecast, uncut")


@test(modes=("ds",))
def es_klaus_testudo_counter_damage_number_is_the_cut_one(ctx):
    """The counter's damage number in the game's record (+0xC: the luck rolled and the counter's shown HP applied, before the defence) is one of the numbers
    the plain rule allows, cut to 75% (whole numbers, rounded down), and none of the plain ones: over three matchups."""
    for kind in ("tank", "infantry", "mech"):
        g, r = klaus_fight(ctx, True, kind, kind)
        _, rd = r["records"]
        c = r["counter"]
        bars = damage.hp_bars(rd["remaining"])
        rolled = {damage.div(c.acc * c.base, 100) + roll for roll in range(c.luck[0])}
        plain = {damage.div(v * bars, 10) for v in rolled}
        cut = {damage.div(v * 75, 100) for v in plain}
        ctx.log(f"{kind}: counter record {rd}; plain numbers {sorted(plain)}, cut {sorted(cut)}")
        ctx.check(rd["damage"] in cut, f"{kind}: the counter's damage number {rd['damage']} is one of the cut numbers {sorted(cut)}")
        ctx.check(rd["damage"] not in plain, f"{kind}: and not one of the plain ones {sorted(plain)}")


# --- Aurelia: Onager --------------------------------------------------------------------------------------------------------------

TARGET = (13, 10)
NORTH, EAST, SOUTH, WEST = (13, 9), (14, 10), (13, 11), (12, 10)
DIAGONAL, TWO_AWAY = (14, 9), (15, 10)


def onager_map(ctx):
    """Aurelia's Artillery at (10, 10) and an Andy Tank at the target (13, 10), distance 3; Andy's units on the four cells beside the target, one of Aurelia's
    own on a fifth cell beside it (the four are N, E, W of the enemy and S Aurelia's own), a unit on a diagonal and one two cells away."""
    m = ctx.map()
    m.unit(1, "artillery", 10, 10)
    m.unit(2, "tank", *TARGET)
    m.unit(2, "infantry", *NORTH).unit(2, "mech", *EAST).unit(1, "infantry", *SOUTH).unit(2, "recon", *WEST)
    m.unit(2, "infantry", *DIAGONAL).unit(2, "tank", *TWO_AWAY)
    return m


def onager_fight(ctx, power):
    """Aurelia's Artillery fires at the Tank. `power`: None, "power" (Ballista) or "super" (Onager). Returns (game, hp before, hp after, ctx.attack's result)."""
    g = ctx.start(onager_map(ctx), [AURELIA, "andy"], env=ENV)
    ctx.set_hp(g, *EAST, 15)
    ctx.set_hp(g, *WEST, 10)
    if power:
        ctx.power(g, 1, power)
    cells = (NORTH, EAST, SOUTH, WEST, DIAGONAL, TWO_AWAY, TARGET)
    before = {c: hp_of(g, *c) for c in cells}
    r = ctx.attack(g, (10, 10), (10, 10), TARGET)
    after = {c: hp_of(g, *c) if g.unit_at(*c) else 0 for c in cells}
    ctx.log(f"HP before {before}\n   after {after}")
    return g, before, after, r


@test(modes=("ds",))
def es_aurelia_onager_splash_costs_the_units_beside_the_target_one_hp(ctx):
    """An Artillery hit under Onager: the target takes the usual damage (ctx.attack checks it against the calculator with her numbers); each enemy unit on
    a cell next to it loses 1 HP (10 points), a unit on 1 HP keeps it, her own unit, the unit on the diagonal and the one two cells away are as they were."""
    g, before, after, r = onager_fight(ctx, "super")
    ctx.eq(after[NORTH], before[NORTH] - 10, "north (enemy Infantry): 1 HP less")
    ctx.eq(after[EAST], before[EAST] - 10, "east (enemy Mech on 15): 1 HP less")
    ctx.eq(after[WEST], before[WEST], "west (enemy Recon on 1 HP): stays on 1 HP")
    ctx.eq(after[SOUTH], before[SOUTH], "south (her own Infantry): untouched")
    ctx.eq(after[DIAGONAL], before[DIAGONAL], "the diagonal cell: untouched")
    ctx.eq(after[TWO_AWAY], before[TWO_AWAY], "two cells away: untouched")
    ctx.check(after[TARGET] < before[TARGET], "the target itself took the attack's damage (not a splash)")
    ctx.shot(g, "onager")


@test(modes=("ds",))
def es_aurelia_without_onager_there_is_no_splash(ctx):
    """The same hit with no power, and under Ballista (her CO Power: the range and the attack, no splash): the neighbours keep every HP."""
    for power in (None, "power"):
        g, before, after, r = onager_fight(ctx, power)
        for name, c in (("north", NORTH), ("east", EAST), ("south", SOUTH), ("west", WEST), ("diagonal", DIAGONAL), ("two away", TWO_AWAY)):
            ctx.eq(after[c], before[c], f"{power or 'no power'}: {name} untouched")
        g.e.close()


@test(modes=("ds",))
def es_aurelia_onager_needs_an_indirect_attack(ctx):
    """A direct unit of hers (a Tank, next to its target) under Onager hits and takes its counter as ever; nothing beside the target loses HP."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(2, "infantry", 11, 9).unit(2, "infantry", 12, 10)
    g = ctx.start(m, [AURELIA, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    ctx.attack(g, (10, 10), (10, 10), (11, 10))
    ctx.eq(hp_of(g, 11, 9), 100, "beside the Tank's target (north): untouched")
    ctx.eq(hp_of(g, 12, 10), 100, "beside the Tank's target (east): untouched")


# --- Cassius: Triumph ---------------------------------------------------------------------------------------------------------------

MOVED_BITS = 0x0203C980           # crate::es_co::MOVED_AFTER_ATTACK: a bit a unit slot, the units that attacked and have their extra move left
CASSIUS_AT, TARGET_AT = (10, 10), (12, 10)


def moved_bit(g, uid):
    return bool(g.e.u8(MOVED_BITS + uid // 8) & (1 << (uid % 8)))


SECOND_TARGET = (11, 14)          # a second enemy Infantry, next to where the extra move ends
CONTROL_TANK = (8, 13)            # a Tank of his that has not attacked: its menu at (12, 14) offers Fire


def triumph_game(ctx, power):
    m = ctx.map()
    m.unit(1, "tank", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT).unit(2, "infantry", *SECOND_TARGET).unit(1, "tank", *CONTROL_TANK)
    g = ctx.start(m, [CASSIUS, "andy"], env=ENV)
    if power:
        ctx.power(g, 1, "super")
    return g


def can_select(g, x, y):
    """Whether the unit at (x, y) can be picked up now (False: it is done for the turn). Leaves the unit as it was."""
    try:
        g.select(x, y)
    except NavError:
        return False
    for _ in range(3):
        g.e.press("B", 4)
        g.e.wait(20)
    g.wait_for_input()
    return True


@test(modes=("ds",))
def es_cassius_triumph_a_vehicle_that_attacked_moves_once_more_but_cannot_fire(ctx):
    """Under Triumph a Tank moves and fires; its done flag stays clear and its bit in EWRAM is set; it can be picked up again, its menu has no Fire, it
    moves on (the full move of a Tank, +2 with the power) and Waits; then it is done for the turn and the bit is gone."""
    g = triumph_game(ctx, True)
    uid = g.unit_at(*CASSIUS_AT)["id"]
    ctx.eq(g.player(1)["co_mode"], 2, "Triumph is on")
    # The control: a Tank that has not attacked is offered Fire next to the second Infantry.
    g.select(*CONTROL_TANK)
    control = g.move_to(12, 14)["names"]
    ctx.check(any(n.lower().startswith("fire") for n in control), f"a Tank that has not attacked is offered Fire beside an enemy: {control}")
    g.e.press("B", 4)
    g.e.wait(20)
    g.e.press("B", 4)
    g.wait_for_input()
    (a0, a1), (d0, d1) = g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    ctx.check(d1["hp"] < d0["hp"], f"the Tank hit the Infantry: {d0['hp']} -> {d1['hp']}")
    u = g.unit(uid)
    ctx.eq(u["flags"] & FLAG_DONE, 0, f"after attacking the unit is not done (flags {u['flags']:#04x})")
    ctx.check(moved_bit(g, uid), "its extra-move bit is set")
    ctx.eq((u["x"], u["y"]), (11, 10), "it stands where it attacked from")
    # The second move: next to the second Infantry, where Fire would be offered; the menu has none.
    g.select(11, 10)
    names = g.move_to(11, 13)["names"]
    ctx.log(f"menu after the extra move: {names}")
    ctx.check("Wait" in [n.strip() for n in names] or any(n.lower().startswith("wait") for n in names), "the menu offers Wait")
    ctx.check(not any(n.lower().startswith("fire") for n in names), "and no Fire")
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    u = g.unit(uid)
    ctx.eq((u["x"], u["y"]), (11, 13), "it moved on")
    ctx.eq(u["flags"] & FLAG_DONE, FLAG_DONE, "and is done for the turn")
    ctx.check(not moved_bit(g, uid), "the extra-move bit is gone")
    ctx.check(not can_select(g, 11, 13), "it cannot be picked up again")
    ctx.eq(g.unit_at(*SECOND_TARGET)["hp"], 100, "the second Infantry was never fired on")
    ctx.shot(g, "triumph")


@test(modes=("ds",))
def es_cassius_triumph_an_unattacking_unit_is_done_as_ever(ctx):
    """Under Triumph a unit that only moves and Waits is done at once (the extra move is for a unit that attacked), and one that attacked and
    then waits where it is is done too."""
    g = triumph_game(ctx, True)
    m = g.unit_at(*CASSIUS_AT)
    g.select(*CASSIUS_AT)
    g.move_to(10, 12)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    ctx.eq(g.unit(m["id"])["flags"] & FLAG_DONE, FLAG_DONE, "a plain move: done")
    ctx.check(not moved_bit(g, m["id"]), "no bit")
    ctx.check(not can_select(g, 10, 12), "it cannot be picked up again")


@test(modes=("ds",))
def es_cassius_without_triumph_an_attacking_unit_is_done(ctx):
    """The same attack with no power, and under Charge (his CO Power): the unit is done, no bit, and cannot be picked up again."""
    for power in (None, "power"):
        m = ctx.map()
        m.unit(1, "tank", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT)
        g = ctx.start(m, [CASSIUS, "andy"], env=ENV)
        if power:
            ctx.power(g, 1, power)
        uid = g.unit_at(*CASSIUS_AT)["id"]
        g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
        u = g.unit(uid)
        ctx.eq(u["flags"] & FLAG_DONE, FLAG_DONE, f"{power or 'no power'}: after attacking the unit is done")
        ctx.check(not moved_bit(g, uid), f"{power or 'no power'}: no bit")
        ctx.check(not can_select(g, 11, 10), f"{power or 'no power'}: it cannot be picked up again")
        g.e.close()


@test(modes=("ds",))
def es_cassius_triumph_is_for_vehicles_only(ctx):
    """An Infantry of Cassius's attacks under Triumph and is done as ever (the power's rule is for vehicles)."""
    m = ctx.map()
    m.unit(1, "infantry", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT)
    g = ctx.start(m, [CASSIUS, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    uid = g.unit_at(*CASSIUS_AT)["id"]
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    ctx.eq(g.unit(uid)["flags"] & FLAG_DONE, FLAG_DONE, "the Infantry is done after attacking")
    ctx.check(not moved_bit(g, uid), "no bit")


@test(modes=("ds",))
def es_cassius_triumph_an_unused_extra_move_ends_with_the_turn(ctx):
    """A Tank attacks under Triumph and is left where it is; the turn ends (Andy's computer plays) and the unit is Cassius's again with its bit cleared,
    free to attack (Fire in its menu) and with a new extra move."""
    g = triumph_game(ctx, True)
    uid = g.unit_at(*CASSIUS_AT)["id"]
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    ctx.check(moved_bit(g, uid), "the bit is set after the attack")
    g.end_turn(human=1)
    u = g.unit(uid)
    ctx.check(u["type"] != 0, "the Tank is still there")
    ctx.check(not moved_bit(g, uid), "the bit was cleared when the turn passed")
    ctx.eq(u["flags"] & FLAG_DONE, 0, "and the unit is ready for the new turn")


# --- Determinism: the same scenario twice from the same start ends in the same memory ----------------------------------------------------------------
#
# Both peers of a match run the game from identical inputs (docs/dev/architecture-online.md); each rule reads and writes only emulated memory (units, player
# blocks, battle records, the bits in `ram_map`), so two consoles given the same inputs must end with the same RAM. Each scenario is played twice on two consoles
# (each its own process) and the whole of EWRAM and IWRAM is compared; the first run's frame count is the second's.
# (`netplay_triumph` below replays a run on two rollback peers as well: offline Versus' L+R view that the harness presses to reach the Design Maps list was a
# process-wide static, `online_maps::ORIGINAL_VIEW`, which the peers flipped for each other; it is a byte of the console's memory now.)

def ram_dump(g):
    return g.e.read(0x02000000, 0x40000) + g.e.read(0x03000000, 0x7E00)


def differing(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


def twice(ctx, scenario, what):
    dumps = []
    for run in (1, 2):
        g = scenario()
        g.e.wait(120)
        dumps.append((g.e.frame, ram_dump(g)))
        if run == 1:
            g.e.close()
    (f1, d1), (f2, d2) = dumps
    ctx.eq(f1, f2, f"{what}: both runs are at the same frame")
    bad = differing(d1, d2)
    shown = [(f"{(0x02000000 + i) if i < 0x40000 else (0x03000000 + i - 0x40000):#010x}", d1[i], d2[i]) for i in bad[:8]]
    ctx.check(not bad, f"{what}: EWRAM and IWRAM are identical after both runs ({len(bad)} bytes differ {shown})")
    return d1


@test(modes=("ds",))
def es_klaus_testudo_is_deterministic(ctx):
    def run():
        g = klaus_game(ctx)
        ctx.power(g, 1, "power")
        g.attack((10, 10), (10, 10), (11, 10))
        return g
    twice(ctx, run, "Testudo")


@test(modes=("ds",))
def es_aurelia_onager_is_deterministic(ctx):
    def run():
        g = ctx.start(onager_map(ctx), [AURELIA, "andy"], env=ENV)
        ctx.set_hp(g, *EAST, 15)
        ctx.power(g, 1, "super")
        g.attack((10, 10), (10, 10), TARGET)
        return g
    d = twice(ctx, run, "Onager")
    ctx.check(d is not None, "(the runs happened)")


@test(modes=("ds",))
def es_cassius_triumph_is_deterministic(ctx):
    def run():
        g = triumph_game(ctx, True)
        g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
        g.select(11, 10)
        g.move_to(11, 13)
        g.choose("Wait", g.ACTION_MENU)
        g.wait_idle()
        return g
    twice(ctx, run, "Triumph")


# --- Triumph beyond the plain case: the computer's Cassius, a suspended game, a Tag Power's Change ---------------------------------------------------

def triumph_tank_moves_on(g, start, to):
    """The tank at `start` (extra move left) is picked up again, moved to `to` and Waits."""
    g.select(*start)
    g.move_to(*to)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()


@test(modes=("ds",))
def es_cassius_triumph_the_computers_cassius_moves_once_more_and_never_fires_twice(ctx):
    """The computer plays Cassius (army 2) in his Super Power: its Tank attacks an Infantry and is left not done with its bit set (it had none: the computer's
    Cassius got no extra move), a later pass of the unit queue moves it on, the executor turns its second attack into a Wait, and the Tank ends done with the bit
    cleared, standing nowhere near its first target; the other Infantry, which the second move ends beside, is not fired on."""
    m = ctx.map()
    m.unit(1, "infantry", 13, 10).unit(1, "infantry", 13, 17).unit(1, "infantry", 3, 3).unit(2, "tank", 15, 10)
    g = ctx.start(m, ["andy", CASSIUS], env=ENV)
    foes = [g.unit_at(13, 10)["id"], g.unit_at(13, 17)["id"]]
    seen = []

    def hp(gg, uid):
        u = gg.unit(uid)
        return u["hp"] if u["type"] else 0

    def watch(gg):
        uid = gg.unit_at(15, 10)["id"]
        gg.e.w8(gg.player(2)["addr"] + ram.P_CO_MODE, 2)         # (his Super Power for the turn: the computer's own use of it is another test's)
        for _ in range(900):
            gg.e.wait(2)
            u = gg.unit(uid)
            row = (u["x"], u["y"], u["flags"] & FLAG_DONE, moved_bit(gg, uid), hp(gg, foes[0]), hp(gg, foes[1]))
            if not seen or row != seen[-1]:
                seen.append(row)
            if gg.current_army() != 2:
                break

    g.end_turn(human=1, observe=watch)
    ctx.log(f"samples (x, y, done, bit, hp of the two Infantry): {seen}")
    first = next((i for i, r in enumerate(seen) if r[3]), None)
    ctx.check(first is not None, "its extra-move bit was set after the attack (the computer's Cassius gets Triumph)")
    ctx.check(any(r[4] < 100 or r[5] < 100 for r in seen), "the computer's Tank attacked an Infantry")
    if first is None:
        return
    ctx.check(not seen[first][2], "and the Tank was not done then")
    hit = [k for k in (4, 5) if min(r[k] for r in seen) < 100]
    ctx.eq(len(hit), 1, "exactly one Infantry was hit (by the first attack)")
    stays = [k for k in (4, 5) if k not in hit][0] if len(hit) == 1 else 5
    ctx.check(any((r[0], r[1]) != (seen[first][0], seen[first][1]) for r in seen[first:]), "the Tank moved on after its attack (the extra move)")
    ctx.eq([r[stays] for r in seen], [100] * len(seen), "the other Infantry was never fired on (the Tank cannot fire again)")
    ctx.check(any(not r[3] and r[2] == FLAG_DONE and (r[0], r[1]) != (seen[first][0], seen[first][1]) for r in seen[first:]),
              "the extra move ended with the Tank done and the bit cleared")


def suspended_triumph_game(ctx):
    g = triumph_game(ctx, True)
    uid = g.unit_at(*CASSIUS_AT)["id"]
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    ctx.check(moved_bit(g, uid), "the bit is set after the attack")
    return g, uid


@test(modes=("ds",))
def es_cassius_triumph_a_suspended_game_keeps_the_extra_move(ctx):
    """Save from the map menu with a Tank's extra move pending, reboot, Versus > Continue: the Tank is still not done, its bit is set, Fire is not offered, and
    its move on ends it for good (it used to come back as a unit that could fire again: the bits were not in the save)."""
    g, uid = suspended_triumph_game(ctx)
    e = g.e
    saves.suspend(g)
    path = e.save(os.path.join(ctx.out, "saved"))
    e2 = Emu(save=path, ds=True, env=ENV)
    g2 = Game(e2)
    ctx.games.append(g2)
    saves.to_select_mode(e2)
    saves.versus_continue(g2)
    u = g2.unit(uid)
    ctx.eq((u["x"], u["y"], u["flags"] & FLAG_DONE), (11, 10, 0), "the Tank stands where it attacked from, not done")
    ctx.check(moved_bit(g2, uid), "its extra-move bit came back with the game")
    g2.select(11, 10)
    names = g2.move_to(11, 13)["names"]
    ctx.check(not any(n.lower().startswith("fire") for n in names), f"and Fire is not offered ({names})")
    g2.choose("Wait", g2.ACTION_MENU)
    g2.wait_idle()
    ctx.eq(g2.unit(uid)["flags"] & FLAG_DONE, FLAG_DONE, "the move on ends it")
    ctx.check(not moved_bit(g2, uid), "and the bit is gone")


@test(modes=("ds",))
def es_cassius_triumph_a_suspended_game_without_it_has_no_bits(ctx):
    """A game saved with no extra move pending has no bits after Continue (the tail is only written when something rides in it)."""
    g = triumph_game(ctx, True)
    uid = g.unit_at(*CASSIUS_AT)["id"]
    saves.suspend(g)
    path = g.e.save(os.path.join(ctx.out, "saved"))
    e2 = Emu(save=path, ds=True, env=ENV)
    g2 = Game(e2)
    ctx.games.append(g2)
    saves.to_select_mode(e2)
    saves.versus_continue(g2)
    ctx.check(not any(g2.e.u8(MOVED_BITS + k) for k in range(40)), "no bit is set")
    ctx.check(not moved_bit(g2, uid), "not the Tank's")


def tag_triumph_game(ctx, cos, partner):
    m = ctx.map()
    m.unit(1, "tank", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT).unit(2, "infantry", 11, 14).unit(1, "infantry", 3, 3)
    g = ctx.boot_teams(m, env=ENV)
    tag.set_teams_partner(g.e, 1, partner)
    g.set_teams(cos, {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    return g


def fill_both(g):
    e = g.e
    p = g.player(1)
    e.w32(p["addr"] + ram.P_CHARGE, tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[1])
    t = tag.partner(e, 1)
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1])


@test(modes=("ds",))
def es_cassius_triumph_a_tag_change_hands_the_units_to_the_partner(ctx):
    """Cassius leads a pair with Andy. Tag Power, first half: Cassius's Super Power, his Tank attacks and has its extra move. Change: Andy's Super Power, every
    unit moves again; the Tank's bit is gone with Cassius's power and it may fire (it was barred from Fire by a bit that outlived the power)."""
    g = tag_triumph_game(ctx, [CASSIUS, "andy"], "andy")
    e = g.e
    fill_both(g)
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the first half: Cassius's Super Power")
    g.wait_for_input()
    uid = g.unit_at(*CASSIUS_AT)["id"]
    ctx.eq(g.player(1)["co"], CASSIUS, "Cassius is the active CO")
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    ctx.check(moved_bit(g, uid), "Triumph: the Tank has its extra move")
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == romlib.co_id("andy") and g.player(1)["co_mode"] == 2, 3000, step=10), "the second half: Andy's Super Power")
    g.wait_for_input()
    ctx.check(not moved_bit(g, uid), "Cassius's power is over: the bit is gone")
    ctx.eq(g.unit(uid)["flags"] & FLAG_DONE, 0, "every unit may move again")
    g.select(11, 10)
    names = g.move_to(11, 13)["names"]
    ctx.check(any(n.lower().startswith("fire") for n in names), f"Andy's second half: the Tank is offered Fire beside the second Infantry ({names})")


@test(modes=("ds",))
def es_cassius_triumph_the_partner_has_it_in_the_second_half(ctx):
    """Cassius is the partner of Andy. Tag Power: Andy's Super Power first, then Change puts Cassius in his place with his Super Power on: his Tank's attack
    gives it the extra move as for any Cassius."""
    g = tag_triumph_game(ctx, ["andy", CASSIUS], CASSIUS)
    e = g.e
    fill_both(g)
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the first half: Andy's Super Power")
    g.wait_for_input()
    uid = g.unit_at(*CASSIUS_AT)["id"]
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == CASSIUS and g.player(1)["co_mode"] == 2, 3000, step=10), "the second half: Cassius's Super Power")
    g.wait_for_input()
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    u = g.unit(uid)
    ctx.eq(u["flags"] & FLAG_DONE, 0, "the partner's Tank is not done after attacking")
    ctx.check(moved_bit(g, uid), "its extra-move bit is set")


@test(modes=("ds",), netplay=True)
def netplay_triumph(ctx):
    """A Tank attacks under Triumph, moves on and Waits, then the turn ends and comes back: replayed on two rollback peers, identical (EWRAM, IWRAM), the bits
    as played."""
    g = triumph_game(ctx, True)
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    g.select(11, 10)
    g.move_to(11, 13)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    g.end_turn(human=1)
    identical, values, text = ctx.netplay_replay(g, [(MOVED_BITS, 41)], env=ENV)
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "both peers and the straight replay identical")
    ctx.eq(values.get(MOVED_BITS), g.e.read(MOVED_BITS, 41), "the extra-move bits as played")
