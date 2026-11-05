"""The Gauntlet's score and rank (`-k gauntlet_score`; crate::gauntlet `POWER_SUM`, `carry_score_out/in`, crate::gauntlet_mode `par_days`; aw2test/gauntlet_score.py is the formula): AW2's Speed, Power and Technique
judged a run of several lines as one map's battle. Speed: the map's par is now days per line. Power: the enemy's builds are divided by the lines. Technique and Power on Iron Crown: the counters the stage
switch used to reset come along. Each test sets the counters a typical run would have, takes the last HQ, and compares the results screen's score with the formula (and the run's record with that score).

Run the same test against an older build (`AW2TEST_RUNNER_DIR=<folder with its aw2_script>`) to see what that build gave: its checks fail and the log lines show the scores it measured."""

import struct

from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import gauntlet_score as gs
from aw2test import paths, ram
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

DAY = 0x0300_4080
P_RANK, P_SPEED, P_POWER, P_TECH, P_TOTAL, P_KILLS, P_BUILT, P_LOST = 0x33, 0x34, 0x35, 0x36, 0x38, 0x18, 0x3A, 0x3B


def boot(ctx):
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, ga.Gauntlet(g)


def player(e, g, army):
    p = g.players_base + ram.PLAYER_SIZE * army
    b = e.read(p, ram.PLAYER_SIZE)
    return dict(rank=b[P_RANK], speed=b[P_SPEED], power=b[P_POWER], tech=b[P_TECH], total=struct.unpack_from("<H", b, P_TOTAL)[0], kills=struct.unpack_from("<H", b, P_KILLS)[0], built=b[P_BUILT], lost=b[P_LOST])


def set_counters(e, g, army, built=None, lost=None, kills=None):
    p = g.players_base + ram.PLAYER_SIZE * army
    if built is not None:
        e.w8(p + P_BUILT, built)
    if lost is not None:
        e.w8(p + P_LOST, lost)
    if kills is not None:
        e.w16(p + P_KILLS, kills)


def results(d, e, g, army, frames=8000):
    """A through the scenes, VICTORY and the results until Select Mode is up; the player's army's score fields as the last read while the battle's records lived."""
    last = None
    n = 0
    while n < frames:
        if d.select_mode_up() and e.u8(dc.ACTIVE) == 0:
            break
        if (d.scripts_running() or not d.in_battle()) and not d.select_mode_up():
            e.press("A", 4)
        e.wait(14)
        n += 18
        if d.in_battle() and not d.select_mode_up():
            f = player(e, g, army)
            if f["total"]:
                last = f
    return last


def inject_and_win_cinder(ctx, run):
    """Cinder Sea to Hawke's last line, the counters of `run` set, Hawke's HQ taken: the player's score fields and the record."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    d.capture(ctx, ga.CINDER["drake"])
    d.settle()
    d.capture(ctx, ga.CINDER["sensei"])
    d.settle()
    set_counters(e, g, 1, built=run["built"], lost=run["lost"], kills=run["kills"])
    per = run["enemy"] // 3
    for a in (2, 3, 4):
        set_counters(e, g, a, built=per)
    e.w16(DAY, run["day"])
    d.capture(ctx, ga.CINDER["hawke"])
    got = results(d, e, g, 1)
    best = d.best(0)
    e.close()
    return got, best


@test(modes=("ds",))
def gauntlet_score_cinder_sea_is_judged_per_line(ctx):
    """Cinder Sea (three lines, par 36): a quick, a steady and a slow run score what the formula says (Speed against the par of the run, Power against an average line's builds), the rank is the formula's, and
    the record holds that score and the day."""
    par = gs.par("gauntlet_01")
    ctx.eq(par, 36, "Cinder Sea's par is 12 days a line")
    for name, mk in gs.SCENARIOS.items():
        run = mk(3)
        want = gs.score(run, par, 3)
        old = gs.score(run, gs.OLD_PAR["gauntlet_01"], 1)
        got, best = inject_and_win_cinder(ctx, run)
        ctx.require(got is not None, f"{name}: the results screen had a score")
        ctx.log(f"{name}: run {run}; measured speed {got['speed']} power {got['power']} tech {got['tech']} total {got['total']} rank {gs.RANKS.get(got['rank'])}; the formula now {want}, before the rework {old}")
        ctx.eq((got["speed"], got["power"], got["tech"], got["total"]), (want["speed"], want["power"], want["tech"], want["total"]), f"{name}: Speed, Power, Technique and total")
        ctx.eq(gs.RANKS[got["rank"]], want["rank"], f"{name}: the rank")
        ctx.check(best is not None and best[1] == run["day"] and best[2] == want["total"], f"{name}: the record is (day {run['day']}, score {want['total']}): {best}")


def iron_crown_to_stage_two(ctx):
    from tests.test_gauntlet_map2 import start as start_map2, wait_stage
    e, g, d = start_map2(ctx)
    return e, g, d, wait_stage


@test(modes=("ds",))
def gauntlet_score_iron_crown_counts_both_maps(ctx):
    """Iron Crown (four lines, then Asuka's Keep, par 60): the stage switch used to reset the player's units built and lost, the most kills in a turn and the enemy's builds, so the score judged stage two alone
    (nothing built there: Technique 0). Now the counters come along: after the switch the player's record holds stage one's, Asuka's builds are added to the four lines', and the score of taking Asuka's HQ is the
    formula's over the whole run."""
    e, g, d, wait_stage = iron_crown_to_stage_two(ctx)
    for key, army, who, nxt in ga.IRON_ORDER[:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
    before = {a: player(e, g, a) for a in (1, 2, 3, 4, 5)}
    ctx.log(f"stage one at the switch: {before}")
    set_counters(e, g, 5, built=70, lost=12, kills=2)
    enemy_one = sum(before[a]["built"] for a in (1, 2, 3, 4))
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    mine, asuka = player(e, g, 1), player(e, g, 2)
    ctx.log(f"stage two's start: player {mine}, Asuka {asuka}")
    ctx.eq((mine["built"], mine["lost"], mine["kills"]), (70, 12, 2), "the player's built, lost and most kills come along")
    ctx.check(asuka["built"] >= min(255, enemy_one + 20), f"Asuka's builds include the four lines' ({asuka['built']} >= {enemy_one} + her own)")
    e.w16(DAY, 33)
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    got = results(d, e, g, 1)
    ctx.require(got is not None, "the results screen had a score")
    run = dict(day=33, kills=2, enemy=asuka["built"], built=70, lost=12)
    want = gs.score(run, gs.par("gauntlet_02"), 5)
    ctx.log(f"measured {got}; the formula {want} (enemy builds {asuka['built']}, 5 lines, par {gs.par('gauntlet_02')})")
    ctx.eq((got["speed"], got["tech"]), (want["speed"], want["tech"]), "Speed against Iron Crown's par and Technique over the whole run")
    ctx.eq(got["power"], want["power"], "Power: the most kills over the enemy's builds per line")
    ctx.eq((got["total"], gs.RANKS[got["rank"]]), (want["total"], want["rank"]), "the total and the rank")
    best = d.best(1)
    ctx.check(best is not None and best[2] == want["total"], f"the record is the score {want['total']}: {best}")
    e.close()


@test(modes=("ds",))
def gauntlet_score_pars_are_in_the_maps_headers(ctx):
    """Every Gauntlet map's par days (crate::gauntlet_mode `par_days`) is what AW2's Speed reads: a run finished on the par day has Speed 100; further days cost the formula's
    `100 - 100 * (day - par) / (3 * par)` (Cinder Sea, par 36: day 40 -> 97, day 72 -> 67)."""
    par = gs.par("gauntlet_01")
    for day, want in ((par, 100), (par + 4, 97), (2 * par, 67)):
        run = dict(day=day, kills=4, enemy=60, built=50, lost=5)
        got, _ = inject_and_win_cinder(ctx, run)
        ctx.require(got is not None, f"day {day}: a score")
        ctx.eq(got["speed"], want, f"day {day}: Speed")
