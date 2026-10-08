"""The Black Factory spawner for a computer Black Hole army on a map with no
factory (crate::factory): it must do nothing, in a custom campaign's mission
and on a second front."""

from aw2test.harness import test
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import bhcampaign as bh
from aw2test import twofront as tf
from aw2test import paths

DAY = 0x03004080
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
