"""The Black Factory spawner for a computer Black Hole army on a map with no
factory (crate::factory): it must do nothing, in a custom campaign's mission
and on a second front."""

import os

from aw2test.harness import test
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import bhcampaign as bh
from aw2test import twofront as tf
from aw2test import paths

DAY = 0x03004080


def shot(ctx, e, name):
    e.shot(os.path.join(ctx.out, name))
FEATURE_PICKS = {0: 0, 1: 2}


def boot_features(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=bh.FEATURES)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = FEATURE_PICKS
    return e, g, d

@test(modes=("ds",))
def bh_campaign_computer_black_hole_without_a_factory(ctx):
    """A computer Black Hole army on a map with no Black Factory: the
    factory spawner (run for it at each turn setup) finds none and does
    nothing; the game plays 12 days with no reset."""
    e, g, d = boot_features(ctx)
    d.picks = {10: 0}
    d.start_at(won_mask=0x3FF & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 10, "mission 11")
    for day in range(2, 14):
        d.end_turn()
        for _ in range(900):
            if e.u16(DAY) == day and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        try:
            d.wait_control()
        except Exception:
            ctx.log(f"result {d.last_result()} main {e.u32(0x03000004):#x} callback {e.u32(0x03000000):#x} day {e.u16(DAY)}")
            raise
        ctx.eq(e.u16(DAY), day, f"day {day} reached")
        ctx.log(f"day {day}: units {[(u['army'], u['type'], u['x'], u['y'], u['hp']) for u in g.units()]} funds {[e.u32(g.player(a)['addr']) for a in (1, 2)]}")
    ctx.check(d.in_battle(), "still in the battle (no reset)")


@test(modes=("ds",))
def bh_campaign_second_front_black_hole_computer_plays_days(ctx):
    """On two fronts the player's Black Hole army on the other front is the
    computer's (Auto CO): the factory spawner runs for it at each turn setup
    on a front with no Black Factory and does nothing; twelve rounds pass
    with no reset and no hang."""
    from aw2test import twofront as tf
    e, g, d = boot_features(ctx)
    d.picks = {11: 0}
    d.start_at(won_mask=0x7FF & ~(1 << 5), unlocked_mask=0b101)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 11, "mission 12")
    for rnd in range(12):
        seen = tf.end_round(e, d)
        ctx.require(d.in_battle() and not d.last_result()["result"], f"round {rnd + 1}: back on the main front, no reset ({d.last_result()})")
        ctx.log(f"round {rnd + 1}: {seen[-3:]} day {e.u16(DAY)} inventions {tf.inventions(e) if hasattr(tf, 'inventions') else ''}")
    ctx.check(e.u16(DAY) >= 12, f"day {e.u16(DAY)}")


@test(modes=("ds",))
def bh_campaign_factory_counters_the_enemy(ctx):
    """The player's Black Factory in a campaign mission picks what the battle
    needs (crate::bh_smart, the Versus pack's smart spawner), the table's
    schedule and cost caps kept: on day 8 (Neotank / Rockets / Infantry slots)
    against six Bombers it builds anti-air (Anti-Air, Missiles or a Fighter),
    against six Md Tanks not Anti-Air or Missiles but a ground answer."""
    AIR_ANSWER = {14, 15, 16}
    for mission, key, want_air in ((12, "air-heavy", True), (13, "armour-heavy", False)):
        e, g, d = boot_features(ctx)
        d.picks = {mission: 0}
        d.start_at(won_mask=((1 << mission) - 1) & ~(1 << 5), unlocked_mask=1)
        d.pick_mission()
        d.wait_map()
        ctx.eq(d.mission(), mission, f"mission {mission + 1}")
        e.w16(DAY, 7)
        d.end_turn()
        for _ in range(600):
            if e.u16(DAY) == 8 and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        d.wait_control()
        e.wait(60)
        built = [u for u in g.units(1) if u["type"] not in (3, 1)]
        log = e.decisions()
        ctx.log(f"{key}: built {[(u['type'], u['x'], u['y']) for u in built]}; decisions {log[-3:]}")
        ctx.require(built, f"{key}: the factory built units on day 8")
        types = {u["type"] for u in built}
        if want_air:
            ctx.check(types & AIR_ANSWER, f"{key}: an anti-air answer among {sorted(types)}")
        else:
            ctx.check(not (types & {14, 15}), f"{key}: no anti-air among {sorted(types)}")
        e.close()


@test(modes=("ds",))
def bh_campaign_human_black_hole_laser_and_minicannon_fire(ctx):
    """A human Black Hole army's Laser (every enemy in its row and column) and
    minicannon (a line to the right) fire at the start of the player's turn:
    AW2 gave them to the computer alone."""
    e, g, d = boot_features(ctx)
    d.picks = {14: 0}
    d.start_at(won_mask=0x3FFF & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 14, "mission 15")
    before = {u["id"]: u["hp"] for u in g.units(2)}
    ctx.log(f"before {before} {[(u['id'], u['x'], u['y']) for u in g.units(2)]}")
    d.end_turn()
    for _ in range(900):
        if e.u16(DAY) == 2 and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    d.wait_control()
    after = {u["id"]: u["hp"] for u in g.units(2)}
    ctx.log(f"after {after} {[(u['id'], u['x'], u['y']) for u in g.units(2)]}")
    tanks = [i for i in before if i in after and g.unit_type(i) == 5] if hasattr(g, "unit_type") else list(before)[:3]
    hurt = [i for i in before if after.get(i, 0) < before[i]]
    ctx.eq(sorted(hurt), sorted(list(before)[:3]), f"the Laser (its row and column) and the minicannon (its line) hit three of the four Tanks at the start of the player's turn; the fourth, out of every line, is untouched ({[(before[i], after.get(i)) for i in before]})")
    shot(ctx, e, "cannons") if False else None


@test(modes=("ds",))
def bh_campaign_volcano_hazard(ctx):
    """A mission's volcano (MissionDef::volcano): from day 3, every second day,
    three cells erupt for 3 HP on every army's units there (never below 1 HP);
    the cells are marked the day before; nothing on the days between."""
    e, g, d = boot_features(ctx)
    d.picks = {15: 0}
    d.start_at(won_mask=0x7FFF & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 15, "mission 16")
    start = {u["id"]: (u["army"], u["hp"]) for u in g.units()}
    ctx.log(f"start {start}")

    def hp_now():
        return {u["id"]: u["hp"] for u in g.units()}

    def next_day(day):
        d.end_turn()
        for _ in range(900):
            if e.u16(DAY) == day and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        for _ in range(60):
            if not d.scripts_running():
                break
            e.press("A", 4)
            e.wait(10)
        e.wait(500)               # (the volcano's own eruption show at the turn's start)
        from aw2test import ram
        e.w8(ram.CURSOR_X, 0)     # (the show leaves the cursor wherever it last looked)
        e.w8(ram.CURSOR_Y, 0)
        d.wait_control()
        e.wait(60)

    e.wait(600)
    next_day(2)
    ctx.eq(hp_now(), {i: v[1] for i, v in start.items()}, "day 2: nothing erupted (the first eruption is day 3)")
    shot(ctx, e, "volcano_marked")
    ctx.log(f"cursor {g.cursor()} size {d.size()} units {[(u['id'], u['x'], u['y']) for u in g.units()]}")
    next_day(3)
    shot(ctx, e, "volcano_erupted")
    now = hp_now()
    ctx.log(f"day 3 {now}")
    ids = sorted(start)
    mine, e1, e2, e3, e4 = ids[0], ids[1], ids[2], ids[3], ids[4]
    ctx.eq(now[e1], start[e1][1] - 30, "an own Tank on an erupting cell: 3 HP")
    ctx.eq(now[e2], start[e2][1] - 30, "an enemy Tank on an erupting cell: 3 HP")
    ctx.eq(now[e3], 1, "a Tank with 2 HP on a cell: 1 (internal; the game keeps it alive), never destroyed")
    ctx.eq(now[e4], start[e4][1], "a Tank beside the cells: untouched")
    next_day(4)
    ctx.eq(hp_now(), now, "day 4: nothing erupted")


@test(modes=("ds",))
def bh_campaign_pair_pick_matches_every_partner(ctx):
    """On the CO screen with a pair pick (the whole roster unlocked) the
    second pick is the CO asked for, for every possible partner: picked with
    the pad, the battle's pair (army 1's CO and its tag partner) is what was
    picked."""
    from aw2test import tag
    roster = bh.ROSTER
    # (Sonja is a Yellow Comet CO among Black Hole's: every roster CO is a partner of Sturm,
    # and Sonja, Von Bolt and Clone Andy lead with each of the others)
    pairs = [(bh.STURM, p) for p in roster[1:]] + [(lead, p) for lead in (bh.SONJA, bh.CLONE_ANDY) for p in roster if p != lead]
    for lead_co, partner in pairs:
        e, g, d = boot_features(ctx)
        d.picks = {16: 2}
        d.start_at(won_mask=0xFFFF & ~(1 << 5) & ~(1 << 16), unlocked_mask=0x7FF)
        d.pick_mission()
        picks = d.choose_cos(2, prefs=[lead_co, partner])
        g._units_base = g._players_base = None
        d.wait_control()
        lead = g.player(1)["co"]
        got = e.u8(tag.rec(1) + tag.P_CO)
        ctx.log(f"asked {lead_co} + {partner}: picks {picks}, battle lead {lead}, partner {got}")
        # (a Yellow Comet CO picked first, Sonja, does not lead a Black Hole army: the pair is the same, the other leads)
        want = (partner, lead_co) if lead_co == bh.SONJA else (lead_co, partner)
        ctx.eq((picks, (lead, got)), ([lead_co, partner], want), f"CO {lead_co} + CO {partner}")
        e.close()


@test(modes=("ds",))
def bh_campaign_second_front_has_its_own_rules(ctx):
    """A second front's own triggers (MissionDef::front2_triggers) run while it
    is on the screen, on its own named units: the named unit (a Tank of the
    second front) destroyed there plays a scene and wins the second front
    (`UnitGone` with a name: the "unit destroyed" condition); the main front's
    units of the same slots do not trip it."""
    from aw2test import twofront as tf
    e, g, d = boot_features(ctx)
    d.picks = {11: 0}
    d.start_at(won_mask=0x7FF & ~(1 << 5), unlocked_mask=0b101)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 11, "mission 12")
    state = {"killed": False}
    seen = []

    def each():
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
        if e.u8(tf.LIVE) == 1 and not e.u8(tf.BUSY) and not state["killed"]:
            tank = next((u for u in g.units() if u["army"] == 2 and u["type"] == 3 and (u["x"], u["y"]) == (5, 1)), None)
            if tank:
                e.w8(g.unit_addr(tank["id"]), 0)         # destroyed (test aid)
                e.w8(d.layer_cell(tank["x"], tank["y"]), 0)
                state["killed"] = True
        if state["killed"] and state.setdefault("n", 0) < 6:
            state["n"] += 1
            ctx.log(f"latch {e.u32(0x0203FD18):#x} live {e.u8(tf.LIVE)} cb {e.u32(0x03000000):#x} scripts {d.scripts_running()}")
    tf.end_round(e, d, each=each)
    ctx.check(state["killed"], "the second front's named unit was destroyed there")
    ctx.check("The carrier is down." in seen, f"the second front's scene ({seen})")
    ctx.eq(e.u8(tf.SECOND), 2, "the second front is won")


@test(modes=("ds",))
def bh_campaign_second_front_named_unit_alive_at_the_start(ctx):
    """The swap of the fronts empties the unit slots for a moment: the second
    front's named unit is not told dead then (its rules wait for a real death)."""
    from aw2test import twofront as tf
    e, g, d = boot_features(ctx)
    d.picks = {11: 0}
    d.start_at(won_mask=0x7FF & ~(1 << 5), unlocked_mask=0b101)
    d.pick_mission()
    d.wait_map()
    seen = []

    def each():
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
    tf.end_round(e, d, each=each)
    ctx.check("The carrier is down." not in seen, f"no victory scene without a death ({seen})")
    ctx.check(e.u8(tf.SECOND) in (1, 2), "the second front was fought (it may be won by AW2's own rout, without the scene)")
