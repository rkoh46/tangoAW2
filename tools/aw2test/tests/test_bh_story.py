"""Story presentation of the BH Campaign against AW2's own campaign (docs/dev/campaign-scenes.md): traces of the flows (every few frames the song
started, the music player's fade, the dialogue box, the screen's brightness, the sound that came out) and the checks the BH presentation must meet:
music in every story scene, no silent gaps, fades into the battle music.

`-k story_trace_aw2` traces AW2's Normal campaign from New to its first battle (the reference), `-k bh_story` checks the BH Campaign.
Output: <AW2TEST_STORY_DIR or the test's out folder>/<label>.json (+ .wav, screenshots); the table: `aw2dev campaign trace`."""

import os

from aw2test import campaigns as cp
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test import story
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test


def out_dir(ctx):
    return os.environ.get("AW2TEST_STORY_DIR") or ctx.out


@test(modes=("aw2",))
def story_trace_aw2_opening(ctx):
    """AW2's New: the story, the world map, mission 1's card, briefing and first turn."""
    e = Emu(save=paths.base_save(), ds=False)
    g = Game(e)
    d = dc.DsCampaign(g)
    d.open_campaign_box()
    d.box_row(1)
    e.wait(30)
    t = story.Tracer(e, d, out_dir(ctx), "aw2_opening")
    e.press("A", 8)
    t.through(lambda r: r["battle"] and not r["script"] and r["frame"] > 600, max_frames=12000)
    rows = t.finish()
    ctx.check(len(rows) > 50, f"{len(rows)} samples")
    e.close()


@test(modes=("ds",))
def story_trace_bh_opening(ctx):
    """BH CAMPAIGN, New: the prologue, the world map, mission 1's pick, card, intro and first turn."""
    from aw2test import bhcampaign as bh
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    d = bh.BhCampaign(g)
    d.open_campaign_box()
    d.chooser_row(bh.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(1)
    e.wait(30)
    t = story.Tracer(e, d, out_dir(ctx), "bh_opening")
    e.press("A", 8)
    t.through(lambda r: r["battle"] and r["frame"] > 600, max_frames=14000)
    # (the intro in the battle, to the player's control)
    t.through(lambda r: r["battle"] and not r["script"] and r["frame"] > 2600 and not r["text"], max_frames=6000)
    t.through(lambda r: False, max_frames=600)
    rows = t.finish()
    ctx.check(len(rows) > 50, f"{len(rows)} samples")
    e.close()


@test(modes=("ds",))
def story_trace_bh_m1_win(ctx):
    """M1's win: the victory scene, the results, the scene on the world map after it, the map with the next mission."""
    from aw2test import bhcampaign as bh
    from aw2test import bhact2 as a2
    e, g, d = a2.boot(ctx, 0, 1, picks={}, at=0)
    d.pick_mission()
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    d.leave_setup()
    for _ in range(3000):
        if not d.scripts_running():
            e.wait(30)
            if not d.scripts_running():
                break
        e.press("A", 4)
        e.wait(10)
    d.wait_control()
    t = story.Tracer(e, d, out_dir(ctx), "bh_m1_win")
    t.sample("battle, control")
    ctx.require(d.force_win(), "M1: a forced win")
    t.through(lambda r: r["map"] and not r["script"] and r["frame"] > 400, max_frames=14000)
    t.through(lambda r: False, max_frames=600)
    rows = t.finish()
    ctx.check(len(rows) > 20, f"{len(rows)} samples")
    e.close()


def mission_flow(ctx, n, label):
    """One BH mission's story, played: its CO screen, mission card and intro scene, the battle's first turn, a forced win, the victory scene, the results,
    the scenes on the world map after it. Every sample (song, fade, text, screen) goes to <label>.json."""
    import test_bh_review as r
    title, roster, picks, fog, front = r.M[n]
    mask = (1 << (n - 1)) - 1
    env = {"TANGOAW2_BH_STILL": "1"} if n == 28 else None
    e, g, d = r.boot(ctx, mask, roster, {n - 1: len(picks)}, n - 1, env)
    d.wait_world_map()
    t = story.Tracer(e, d, out_dir(ctx), label).attach()
    from aw2test import bhact2 as a2
    a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}")
    d.leave_setup()
    for _ in range(3000):                       # (the opening scenes of the battle, to the player's control)
        if not d.scripts_running():
            e.wait(30)
            if not d.scripts_running():
                break
        e.press("A", 4)
        e.wait(10)
    d.wait_control()
    t.sample("control")
    g._units_base = g._players_base = None
    try:
        won = d.force_win()
    except Exception as ex:      # (a naval or air mission: the aid cannot place a gunner; only the intro is traced)
        ctx.log(f"M{n}: no forced win ({ex})")
        won = False
    if not won:
        rows = t.finish()
        t.detach()
        e.close()
        return rows
    # (the victory scene, the results, the save prompt, the scenes on the map)
    for _ in range(4000):
        if d.world_map_up() and not d.scripts_running():
            e.wait(60)
            if d.world_map_up() and not d.scripts_running():
                break
        e.press("A", 4)
        e.wait(10)
    t.sample("map")
    e.wait(200)
    rows = t.finish()
    t.detach()
    e.close()
    return rows


@test(modes=("ds",))
def story_trace_bh_missions(ctx):
    """`AW2TEST_STORY_MISSIONS=1,2,3` (default 1): each mission's flow traced (aw2dev campaign trace)."""
    wanted = [int(x) for x in os.environ.get("AW2TEST_STORY_MISSIONS", "1").split(",")]
    for n in wanted:
        rows = mission_flow(ctx, n, f"bh_m{n:02d}")
        ctx.check(len(rows) > 50, f"M{n}: {len(rows)} samples")
