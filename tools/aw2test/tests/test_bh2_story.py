"""Story presentation of the BH2 Campaign (docs/dev/bh2-text.md, docs/dev/campaign-scenes.md; `-k story_trace_bh2`, `aw2dev campaign trace --campaign bh2`): the prologue (the pages and the three chained world-map scenes) and one mission per act traced (every few frames the song started, the music player's fade, the dialogue box, the sound that came out): every dialogue scene has its song playing and is heard (no silent
scene), the own songs ("The Door", Aria's) are among them. `AW2TEST_STORY_MISSIONS=1,9` names other missions (default: one a act and the final's Aria scene)."""

import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import paths, story
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test
from tests.test_bh_story import out_dir

# one mission per act (I: the opening, II: Sensei, III: Lash and the Blue Moon pair, IV: Clone Andy, V: Asuka + Hawke), the final mission's Aria and the secret M32
ACT_MISSIONS = [1, 9, 17, 22, 26, 30, 31, 32]
QUIET = 60                 # (story.scenes: a sample under this RMS is silent)


def music_in_every_dialogue_scene(ctx, rows, label):
    """Every run of dialogue samples has its song playing and is heard: at most a fifth of its samples silent (fades into and out of a scene)."""
    scenes = [s for s in story.scenes(rows, QUIET) if s["kind"] == "dialogue"]
    ctx.require(scenes, f"{label}: dialogue was traced")
    for s in scenes:
        ctx.log(f"{label}: song {s['song']} frames {s['start']}..{s['end']} rms {s['rms_min']}..{s['rms_max']} silent {s['silent']}/{s['samples']} {str(s['text'])[:50]!r}")
        if s["samples"] >= 5:
            ctx.check(s["silent"] * 5 <= s["samples"], f"{label}: the scene at frame {s['start']} (song {s['song']}) is heard ({s['silent']} of {s['samples']} samples silent)")
        ctx.check(s["song"] != 0, f"{label}: the scene at frame {s['start']} has a song")


def mission_flow(ctx, n, label):
    """Mission n entered through its CO screens (the traced flow: card, pre scene, the battle's first turn) and, when the aid can place a gunner, a forced win, the post scene and the map scenes."""
    e, g, d = b2.boot(ctx, n)
    d.wait_world_map()
    t = story.Tracer(e, d, out_dir(ctx), label).attach()
    a2.open_mission(ctx, e, g, d, n - 1, b2.PICKS.get(n, []), f"m{n}")
    d.leave_setup()
    if n == 31:                  # (the finale: its opening scene, then the four nations' computer turns, then the player's)
        e.wait(120)
        b2.to_player_turn(e, g, d)
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
def story_trace_bh2_opening(ctx):
    """BH2 CAMPAIGN, New: the prologue card with its narration and song, the three chained world-map scenes (the castle, the Allies, the turn), mission 1's pick, card and intro."""
    e = Emu(save=paths.base_save(), ds=True, env=b2.ENV)
    g = Game(e, ctx.image)
    d = b2.Bh2Campaign(g)
    d.open_campaign_box()
    d.chooser_row(b2.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(1)
    e.wait(30)
    t = story.Tracer(e, d, out_dir(ctx), "bh2_opening")
    e.press("A", 8)
    t.through(lambda r: r["battle"] and r["frame"] > 600, max_frames=30000)
    t.through(lambda r: False, max_frames=300)
    rows = t.finish()
    ctx.check(len(rows) > 50, f"{len(rows)} samples")
    music_in_every_dialogue_scene(ctx, rows, "opening")
    e.close()


@test(modes=("ds",))
def story_trace_bh2_missions(ctx):
    wanted = [int(x) for x in os.environ.get("AW2TEST_STORY_MISSIONS", ",".join(map(str, ACT_MISSIONS))).split(",")]
    for n in wanted:
        rows = mission_flow(ctx, n, f"bh2_m{n:02d}")
        ctx.check(len(rows) > 50, f"M{n}: {len(rows)} samples")
        music_in_every_dialogue_scene(ctx, rows, f"M{n}")


@test(modes=("ds",))
def story_trace_bh2_chooser(ctx):
    """The Campaign chooser with BH2 CAMPAIGN listed (and the cursor on it): the picture `bh2_chooser.bmp` for `aw2dev bh2 integration`."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    d = b2.Bh2Campaign(g)
    d.open_campaign_box()
    d.chooser_row(b2.CHOOSER_ROW)
    e.wait(30)
    bmp = e.shot(os.path.join(out_dir(ctx), "bh2_chooser"))
    ctx.check(os.path.exists(bmp), "the chooser's picture")
    e.close()
