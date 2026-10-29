"""Story presentation of the BH2 Campaign (docs/dev/bh2-text.md, docs/dev/campaign-scenes.md; `-k story_trace_bh2`, `aw2dev campaign trace --campaign bh2`): the prologue (the pages and the three chained world-map scenes) and one mission per act traced (every few frames the song started, the music player's fade, the dialogue box, the sound that came out): every dialogue scene has its song playing and is heard (no silent
scene), the own songs ("The Door", Aria's) are among them. `AW2TEST_STORY_MISSIONS=1,9` names other missions (default: one a act and the final's Aria scene)."""

import os

from PIL import Image

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
    bmp = e.shot(os.path.join(out_dir(ctx), "bh2_chooser"))      # (row 3: BH2 right after BH, before Emerald Sun)
    ctx.check(os.path.exists(bmp), "the chooser's picture")
    e.close()


@test(modes=("ds",))
def story_trace_bh2_chooser_order(ctx):
    """The Campaign chooser reads AW2, DS, BH, BH2, Emerald Sun: rows 2, 3 and 4 open the BH (source 1), BH2 (source 3) and Emerald Sun (source 2) boxes; the source indices and so the saves are the same as
    before the reorder. A picture of each row (`bh2_chooser_<name>.bmp`)."""
    from aw2test import dscampaign as dc
    from aw2test import escampaign as es
    for row, name, source in ((2, "bh", 1), (3, "bh2", 3), (4, "emerald_sun", 2)):
        e = Emu(save=paths.base_save(), ds=True, env=dict(b2.ENV, **es.ENV))
        g = Game(e, ctx.image)
        d = b2.Bh2Campaign(g)
        d.open_campaign_box()
        d.chooser_row(row)
        e.wait(30)
        e.shot(os.path.join(out_dir(ctx), f"bh2_chooser_{name}"))
        e.press("A", 8)
        e.wait(30)
        ctx.eq((e.u8(dc.MENU_LEVEL), e.u8(b2.SOURCE)), (2, source), f"chooser row {row} ({name}) opens source {source}")
        e.close()


@test(modes=("ds",))
def story_trace_bh2_prologue_frames(ctx):
    """BH2 CAMPAIGN, New: the prologue box by box (`aw2dev bh2 prologue-sheet`): after each box's text has appeared and typed out (`TYPE_FRAMES`) one picture, then A; every page and dialogue box of the
    narration, the castle, the Allies and the Obelisk scenes, up to the world map. `prologue_NNN.bmp` and `prologue.json` (the text and the song of each frame) go to the output folder."""
    import json
    e = Emu(save=paths.base_save(), ds=True, env=b2.ENV)
    g = Game(e, ctx.image)
    d = b2.Bh2Campaign(g)
    d.open_campaign_box()
    d.chooser_row(b2.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(1)
    e.wait(30)
    e.press("A", 8)
    out = out_dir(ctx)
    os.makedirs(out, exist_ok=True)
    rows, kept, dup = [], None, 0
    for _ in range(3000):
        e.press("A", 4)              # (the New confirmation, then every page: A types the next two lines or closes the box)
        e.wait(20)
        # wait until the box is fully typed: the picture stops changing apart from the blinking "next" arrow (a few pixels)
        prev, still = None, 0
        for _ in range(40):
            bmp = e.shot(os.path.join(out, "prologue_cur"))
            cur = Image.open(bmp).convert("RGB")
            still = still + 1 if prev is not None and pixel_diff(prev, cur) <= ARROW_PIXELS else 0
            prev = cur
            if still >= 3:
                break
            e.wait(15)
        t = story.clean(d.text_shown())
        if t and (kept is None or pixel_diff(kept, cur) > ARROW_PIXELS):
            name = f"prologue_{len(rows):03d}.bmp"
            os.replace(bmp, os.path.join(out, name))
            rows.append({"n": len(rows), "text": t, "song": e.u16(story.SONG), "shot": name})
            kept, dup = cur, 0
        else:
            dup += 1
        if d.in_battle() or (rows and dup > 4 and d.world_map_up() and not d.scripts_running()):
            break
    json.dump(rows, open(os.path.join(out, "prologue.json"), "w"), indent=1)
    want = sum(len(crate_rows) for crate_rows in prologue_boxes())
    ctx.eq(len(rows), want, f"one frame per box: {want} boxes in story.txt's prologue scenes")
    e.close()


ARROW_PIXELS = 60          # (the blinking "next" arrow is a few pixels: two shots of one typed box differ by fewer)


def pixel_diff(a, b):
    """The number of pixels in which two pictures differ."""
    from PIL import ImageChops
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v else 0)
    return sum(1 for v in d.getdata() if v)


def prologue_boxes():
    """The rows (boxes) of story.txt's four prologue scenes, one list a scene."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "src", "bh2_text", "story.txt")
    scenes, cur = {}, None
    for l in open(path):
        l = l.rstrip("\n")
        if l.startswith("== "):
            cur = l[3:].split("|")[0].strip()
            scenes[cur] = []
        elif cur and l and not l.startswith(("@", "#")) and ": " in l:
            scenes[cur].append(l)
    return [scenes[k] for k in ("prologue", "prologue_castle", "prologue_allies", "prologue_turn")]


@test(modes=("ds",))
def story_trace_bh_prologue_frames(ctx):
    """BH CAMPAIGN (BH1), New: the prologue box by box, as `story_trace_bh2_prologue_frames` does for BH2 (one typed-out picture a box, up to mission 1's battle). `prologue_NNN.bmp` and
    `prologue.json` go to the output folder; `aw2dev bh2 prologue-sheet --bh1` makes the contact sheet."""
    import json
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
    e.press("A", 8)
    out = out_dir(ctx)
    os.makedirs(out, exist_ok=True)
    rows, kept, dup = [], None, 0
    for _ in range(3000):
        e.press("A", 4)
        e.wait(20)
        prev, still = None, 0
        for _ in range(40):
            bmp = e.shot(os.path.join(out, "prologue_cur"))
            cur = Image.open(bmp).convert("RGB")
            still = still + 1 if prev is not None and pixel_diff(prev, cur) <= ARROW_PIXELS else 0
            prev = cur
            if still >= 3:
                break
            e.wait(15)
        t = story.clean(d.text_shown())
        if t and (kept is None or pixel_diff(kept, cur) > ARROW_PIXELS) and not (rows and rows[-1]["text"] == t):
            name = f"prologue_{len(rows):03d}.bmp"
            os.replace(bmp, os.path.join(out, name))
            rows.append({"n": len(rows), "text": t, "song": e.u16(story.SONG), "shot": name})
            kept, dup = cur, 0
        else:
            dup += 1
        if len(rows) >= 24 or dup > 60:          # (the prologue pages, then mission 1's opening dialogue in the battle)
            break
    json.dump(rows, open(os.path.join(out, "prologue.json"), "w"), indent=1)
    ctx.check(len(rows) >= 10, f"{len(rows)} prologue boxes")
    e.close()
