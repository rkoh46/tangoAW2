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
def bh_campaign_second_front_view_has_no_junk_units(ctx):
    """The second front looked at (Map menu > Front) for the first time: its
    unit table holds only its own units (none of the text the front's start
    decoded: boxes of letters on the map) and every cell of its unit plane
    names a unit standing there."""
    from aw2test import twofront as tf
    e, g, d = boot_features(ctx)
    d.picks = {11: 0}
    d.start_at(won_mask=0x7FF & ~(1 << 5), unlocked_mask=0b101)
    d.pick_mission()
    d.wait_map()
    ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
    g._units_base = g._players_base = None
    M = 0x0201E450
    w, h = e.u16(M), e.u16(M + 2)
    r = e.read(g.units_base, 12 * 256)
    at = {}
    for y in range(h):
        row = e.u16(M + 0x417A + 2 * y)
        for x in range(w):
            pid = e.u8(M + 0x12 + row + x)
            if pid:
                at[pid] = (x, y)
    live = {u: (r[12 * u + 2], r[12 * u + 3]) for u in range(256) if r[12 * u]}
    ctx.eq(live, at, "the unit table's units are the plane's (no junk record, no stale id)")
    ctx.check(all(r[12 * u + 4] <= 100 for u in live), "every unit's HP is sane")
    ctx.eq(len(live), 3, "the second front's three units")
    e.close()


@test(modes=("ds",))
def bh_campaign_pair_pick_with_a_partial_roster(ctx):
    """Only Sturm and Sonja unlocked (Sonja is the one Yellow Comet CO among
    Black Hole's): either leads and the other is reachable for the second pick
    (the Black Hole tab is open after Sonja)."""
    for lead_co, partner in ((bh.SONJA, bh.STURM), (bh.STURM, bh.SONJA)):
        e, g, d = boot_features(ctx)
        d.picks = {16: 2}
        d.start_at(won_mask=0xFFFF & ~(1 << 5) & ~(1 << 16), unlocked_mask=1 | (1 << 10))
        d.pick_mission()
        picks = d.choose_cos(2, prefs=[lead_co, partner])
        ctx.eq(sorted(picks), sorted([lead_co, partner]), f"both picked ({picks})")
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


@test(modes=("ds",))
def bh_campaign_own_cannons_spare_the_players_units(ctx):
    """Black Hole's minicannons and Laser owned by the player (army 1 in a
    two-army mission, army 5 in a five-army one) never hurt the player's own
    units: over three days no unit of the player's army loses HP (a Tank with
    no ammo of each computer army stands still, so nothing else hurts them).
    (The Laser hits every unit on its row and column, the owner's too, by design: the
    player's units stand off its lines.)"""
    for mission, five in ((17, False), (18, True), (19, True)):  # (missions 18-20: f18, f19, f20 the fortress)
        e, g, d = boot_features(ctx)
        d.picks = {mission: 0}
        d.start_at(won_mask=((1 << mission) - 1) & ~(1 << 5), unlocked_mask=1)
        d.pick_mission()
        d.wait_map()
        g._units_base = g._players_base = None
        ctx.eq(d.mission(), mission, f"mission {mission + 1}")
        per = 51 if five else 64
        raw = lambda: e.read(g.units_base, 12 * 256)

        def mine():
            r = raw()
            out = {}
            for uid in range(256):
                rec = r[12 * uid:12 * uid + 12]
                if rec[0] and uid % per and uid // per + 1 == (5 if five else 1):
                    out[uid] = (rec[4] | rec[5] << 8) & 0x7F
            return out
        before = mine()
        ctx.require(before, "the player's units")
        if five:
            # (the allies' four turns come first: day 1)
            for _ in range(900):
                if e.u16(DAY) == 1 and e.u16(0x030033EC) == 5 and not d.scripts_running():
                    break
                if d.scripts_running():
                    e.press("A", 4)
                e.wait(10)
            d.wait_control()
            ctx.eq({k: v for k, v in mine().items() if v < before.get(k, 0)}, {}, f"mission {mission + 1}, day 1: no unit of the player lost HP ({mine()} from {before})")
        if mission == 19:
            # The fortress (the player's Onyx, silos with the allies' foot
            # soldiers): their first turns bring no launch before day 3, so
            # the satellite is whole and the debris has not fallen on anyone.
            for _ in range(130):
                if d.scripts_running():
                    e.press("A", 4)
                e.wait(30)
            ctx.eq(e.u8(0x0203FFC9), 4, "the Onyx has all its hits on day 1")
            ctx.eq({k: v for k, v in mine().items() if v < before.get(k, 0)}, {}, "no unit of the fortress lost HP on day 1")
            e.close()
            continue
        for day in range(2, 5):
            e.press("B", 4)
            d.end_turn()
            for _ in range(900):
                if e.u16(DAY) == day and not d.scripts_running() and e.u16(0x030033EC) == (5 if five else 1):
                    break
                if d.scripts_running():
                    e.press("A", 4)
                e.wait(10)
            e.w8(0x0200D4A0, e.u8(0x0200D4A0))
            d.wait_control()
            ctx.eq({k: v for k, v in mine().items() if v < before.get(k, 0)}, {}, f"mission {mission + 1}, day {day}: no unit of the player lost HP ({mine()} from {before})")
        e.close()


@test(modes=("ds",))
def bh_campaign_march_named_spawn_and_jammed_cannon(ctx):
    """MissionDef::marches: a named unit goes two cells a day along its path
    on its own army's turn and stops at an occupied cell, retrying the next
    day; a unit spawned with a name (Action::Spawn) is found by it and marches
    at its full speed (move points, real terrain costs); MissionDef::jams: a minicannon fires no shot until its condition
    holds (day 4), then fires."""
    e, g, d = boot_features(ctx)
    d.picks = {20: 0}
    d.start_at(won_mask=0xFFFFF & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 20, "mission 21")

    def cells(army, t):
        return sorted((u["x"], u["y"]) for u in g.units(army) if u["type"] == t)

    tank_hp = lambda: [u["hp"] for u in g.units(2) if (u["x"], u["y"]) == (3, 2)]
    ctx.eq(cells(2, 5), [(3, 2), (4, 0)], "the Tanks (the walker, the target) start in place")
    hist = {}
    for day in range(2, 7):
        d.end_turn()
        for _ in range(900):
            if e.u16(DAY) == day and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        d.wait_control()
        for u in g.units(2):
            ctx.eq(bytes(e.read(g.unit_addr(u["id"]) + 7, 2)), b"\0\0", f"day {day}: a {u['type']} at {u['x']},{u['y']} has no phantom cargo (its APC cargo bytes +7, +8 are free)")
        hist[day] = (cells(2, 5), cells(2, 7), tank_hp(), cells(2, 6), min(e.u8(g.unit_addr(u['id']) + 6) for u in g.units(2) if u['type'] in (1, 2)))
        ctx.log(f"day {day} all: {[(u['army'], u['type'], u['x'], u['y'], u['hp']) for u in g.units()]}")
        ctx.log(f"day {day} inventions: {[e.read(0x02028360 + 8 * k, 8).hex() for k in range(3)]}")
        ctx.log(f"day {day}: tanks {hist[day][0]} APCs {hist[day][1]} target hp {hist[day][2]}")
        if day == 3:
            # the blocker leaves (test aid): the walker goes on the next day
            b = next(u for u in g.units(2) if u["type"] == 1 and (u["x"], u["y"]) == (7, 0))
            e.w8(g.unit_addr(b["id"]), 0)
            e.w8(d.layer_cell(7, 0), 0)
    walker = lambda day: [c for c in hist[day][0] if c[1] == 0]
    ctx.eq(walker(2), [(6, 0)], "day 2: the walker went two cells and stopped before the blocker")
    ctx.eq(walker(3), [(6, 0)], "day 3: still blocked")
    ctx.eq(walker(4), [(8, 0)], "day 4: the blocker gone, two cells on")
    ctx.eq(walker(5), [(10, 0)], "day 5: two cells on")
    ctx.eq(hist[2][1], [(4, 1)], "day 2: the truck is spawned (named)")
    ctx.eq(hist[3][1], [(9, 1)], "day 3: six move points on its army's turn: four plains and a forest (two)")
    ctx.eq(hist[4][1], [(11, 1)], "day 4: the path's end")
    ctx.eq(hist[4][2], [100], "the jammed minicannon had not fired by day 4")
    ctx.eq(hist[4][3], [(11, 3)], "the driven march: the computer's own movement took the Recon to the path's end by day 4")
    ctx.eq(cells(2, 2), [(6, 3)], "the Mech (role 0) did not walk off to the neutral city (it stays all days)")
    ctx.eq([c for c in cells(2, 1) if c[1] == 3], [(7, 3)], "the spawned standing Infantry stays beside the neutral city")
    ctx.eq(hist[3][4], 70, "the held foot soldiers have their full fuel back (a Mech holds 70)")
    ctx.eq(hist[3][2], [100], "the jammed minicannon had not fired by day 3")
    ctx.check(hist[6][2] and hist[6][2][0] < 100, f"restored on day 4, it has fired by day 6 ({hist[6][2]})")
    e.close()


@test(modes=("ds",))
def bh_campaign_five_army_player_picks_a_pair(ctx):
    """A five-army mission whose player (army 5) is a PickPair: the CO screen
    picks the lead and the partner, army 5 gets them, and army 1 (an ally) keeps
    its fixed CO and is the computer's."""
    from aw2test import tag
    for lead_co, partner in ((bh.STURM, bh.HAWKE), (bh.HAWKE, bh.STURM)):
        e, g, d = boot_features(ctx)
        d.picks = {21: 2}
        d.start_at(won_mask=0x3FFFFF & ~(1 << 5) & ~(1 << 21), unlocked_mask=0x7FF)
        d.pick_mission()
        try:
            picks = d.choose_cos(2, prefs=[lead_co, partner])
        except Exception:
            e.shot(ctx.out + "/five_pick_fail")
            raise
        g._units_base = g._players_base = None
        d.wait_control()
        ctx.eq(d.mission(), 21, "mission 22")
        ctx.eq(picks, [lead_co, partner], "the picks")
        ctx.eq(g.player(5)["co"], lead_co, "army 5 has the lead pick")
        ctx.eq(e.u8(tag.rec(5) + tag.P_CO), partner, "army 5's partner is the second pick")
        ctx.eq(g.player(1)["co"], bh.ANDY, "army 1 keeps its fixed CO (Andy)")
        ctx.eq(e.u8(g.player(1)["addr"] + 0x1B), 2, "army 1 is the computer's")
        e.close()


@test(modes=("ds",))
def bh_campaign_factory_and_volcano_on_one_map(ctx):
    """A Black Factory and a Volcano on one map (AW2's graphics loader has one
    picture slot for them, the Volcano's winning): the Factory's picture is put
    in OBJ tiles 0x176.. and its sprites drawn from there, so it is not drawn
    from the Volcano's tiles."""
    from aw2test.rom import lz10
    e, g, d = boot_features(ctx)
    d.picks = {22: 0}
    d.start_at(won_mask=0xFFFFFF & ~(1 << 5) & ~(1 << 22), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    ctx.eq(d.mission(), 22, "mission 23")
    e.wait(60)
    pic = lz10(bytes(e.read(0x080D22C4, 0x700)))
    have = bytes(e.read(0x06010000 + 0x176 * 32, 48 * 32))
    ctx.check(have == bytes(pic[:48 * 32]), "the Factory's picture is in OBJ tiles 0x176..0x1A5")
    oam = e.read(0x07000000, 0x400)
    tiles = {(oam[8 * i + 4] | oam[8 * i + 5] << 8) & 0x3FF for i in range(128) if (oam[8 * i + 1] >> 1) & 0x7F != 0 or True}
    ctx.check({0x176, 0x196, 0x19E} <= tiles, f"its three sprites draw from there ({sorted(t for t in tiles if t > 0x100)})")
    e.close()


@test(modes=("ds",))
def bh_campaign_five_army_pick_reaches_every_co_and_tags(ctx):
    """The five-army pair pick (f22) reaches the whole recruited roster, Sonja
    (a Yellow Comet CO among Black Hole's) and Clone Andy included: army 5 gets
    the pair picked, and its Tag Power works (offered with both meters full: the
    active CO's Super Power, then the partner's)."""
    from aw2test import tag, ram
    pairs = [(bh.SONJA, bh.CLONE_ANDY), (bh.CLONE_ANDY, bh.SONJA), (bh.KOAL, bh.VON_BOLT), (bh.STURM, bh.CLONE_ANDY)]
    for n, (lead_co, partner) in enumerate(pairs):
        e, g, d = boot_features(ctx)
        d.picks = {21: 2}
        d.start_at(won_mask=0x3FFFFF & ~(1 << 5) & ~(1 << 21), unlocked_mask=0x7FF)
        d.pick_mission()
        picks = d.choose_cos(2, prefs=[lead_co, partner])
        g._units_base = g._players_base = None
        d.wait_control()
        ctx.eq(picks, [lead_co, partner], "the picks")
        # (Sonja picked first does not lead a Black Hole army: the same pair, the other leads)
        if lead_co == bh.SONJA:
            lead_co, partner = partner, lead_co
        ctx.eq((g.player(5)["co"], e.u8(tag.rec(5) + tag.P_CO)), (lead_co, partner), f"army 5 has {lead_co} + {partner}")
        ctx.eq(g.player(1)["co"], bh.ANDY, "army 1 keeps its fixed CO")
        if n != 0 and n != 3:
            e.close()
            continue
        # (army 5 plays last: the four allies' turns first)
        ctx.require(e.wait_until(lambda: g.current_army() == 5, 30000, step=30), "army 5's turn comes")
        g.wait_for_input()
        p = g.player(5)
        e.w32(p["addr"] + ram.P_CHARGE, tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[1])
        t = tag.partner(e, 5)
        e.w32(tag.rec(5) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1])
        names = g.open_map_menu()["names"]
        ctx.check("Tag" in names, f"Tag Power offered ({names})")
        g.choose("Tag", g.MAP_MENU)
        ctx.require(e.wait_until(lambda: g.player(5)["co_mode"] == 2, 3000, step=10), "the first Super Power starts")
        g.wait_for_input()
        p = g.player(5)
        ctx.eq((p["co"], p["co_mode"], tag.partner(e, 5)["phase"]), (lead_co, 2, 1), "the lead's Super Power, the first half")
        g.open_map_menu()
        g.choose("Change", g.MAP_MENU)
        ctx.require(e.wait_until(lambda: g.player(5)["co"] == partner and g.player(5)["co_mode"] == 2, 3000, step=10),
                    "the second half: the partner's Super Power")
        e.close()
