"""Story presentation of the Emerald Sun Campaign (docs/dev/campaign-scenes.md; `aw2dev campaign trace --campaign es`): the prologue (the card, its song, the world map) and
each mission's flow traced (every few frames the song started, the music player's fade, the dialogue box, the screen's brightness, the sound that came out): music in
every story scene, no silent gaps. `AW2TEST_STORY_MISSIONS=1,2` names the missions (default 1)."""

import os

from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test import paths, story
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test
from tests.test_bh_story import out_dir


@test(modes=("ds",))
def story_trace_es_opening(ctx):
    """EMERALD SUN, New: the prologue card with its narration and song, the world map, mission 1's pick, card, intro and first turn."""
    e = Emu(save=paths.base_save(), ds=True, env=es.ENV)
    g = Game(e, ctx.image)
    d = es.EsCampaign(g)
    d.open_campaign_box()
    d.chooser_row(es.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(1)
    e.wait(30)
    t = story.Tracer(e, d, out_dir(ctx), "es_opening")
    e.press("A", 8)
    t.through(lambda r: r["battle"] and r["frame"] > 600, max_frames=14000)
    t.through(lambda r: r["battle"] and not r["script"] and r["frame"] > 2600 and not r["text"], max_frames=6000)
    t.through(lambda r: False, max_frames=600)
    rows = t.finish()
    ctx.check(len(rows) > 50, f"{len(rows)} samples")
    e.close()


def mission_flow(ctx, n, label):
    """One mission's story, played: its CO screens, mission card and intro scene, the battle's first turn, a forced win, the victory scene, the results,
    the scenes on the world map after it. Every sample goes to <label>.json."""
    e, g, d = es.boot(ctx, n)
    d.wait_world_map()
    t = story.Tracer(e, d, out_dir(ctx), label).attach()
    a2.open_mission(ctx, e, g, d, n - 1, es.PICKS.get(n, []), f"m{n}")
    d.leave_setup()
    for _ in range(3000):
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
    if won:
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
def story_trace_es_missions(ctx):
    wanted = [int(x) for x in os.environ.get("AW2TEST_STORY_MISSIONS", "1").split(",")]
    for n in wanted:
        rows = mission_flow(ctx, n, f"es_m{n:02d}")
        ctx.check(len(rows) > 50, f"M{n}: {len(rows)} samples")
