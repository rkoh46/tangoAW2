"""A Gauntlet run screen by screen, for people to look at (docs/dev/gauntlet-mode.md): Select Mode with the wheel turning to GAUNTLET, the map selector (the map, its enemies in order, the best
result), the CO screen (a few COs, then Aria picked), the army colour pick (the colours the enemies leave, Silver Nova taken), the mission card and the intro, day 1, each line's fall and the next CO's arrival, the last HQ, VICTORY, the results and Select Mode again. Frames are kept when the screen changes
(walk_NN.png) and laid out with their step on `walkthrough_sheet_N.png`."""

import hashlib
import os
import subprocess

from aw2test import gauntlet as ga, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
from aw2test.harness import test


class Walk:
    def __init__(self, ctx, e):
        self.ctx, self.e, self.shots, self.last = ctx, e, [], None

    def shot(self, label, force=False):
        p = os.path.join(self.ctx.out, f"walk_{len(self.shots):02d}")
        self.e.shot(p)
        from PIL import Image
        import numpy as np
        a = np.asarray(Image.open(p + ".bmp").convert("RGB"), dtype=int)
        # (kept when more than 6% of the pixels changed since the last kept frame: blinking cursors and the wheel's shimmer are not a new screen)
        if self.last is not None and not force and (np.abs(a - self.last).sum(axis=2) > 40).mean() < 0.06:
            os.remove(p + ".bmp")
            return
        self.last = a
        subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
        os.remove(p + ".bmp")
        self.shots.append((p + ".png", label))

    def watch(self, label, frames, every=20, press=None, until=None):
        """Run `frames`, keeping a frame every `every` when it changed; `press(e)` decides a key (A through scenes)."""
        for _ in range(frames // every):
            self.e.wait(every)
            self.shot(label)
            if press:
                press(self.e)
            if until and until():
                break


@test(modes=("ds",))
def gauntlet_walkthrough_pictures(ctx):
    """The whole Gauntlet flow on Cinder Sea with Aria, frame by frame where the screen changes."""
    from PIL import Image, ImageDraw
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    w = Walk(ctx, e)
    saves.to_select_mode(e)
    w.shot("Select Mode")
    # (GAUNTLET is the entry just below Campaign: one DOWN, the way a player turns it)
    for _ in range(8):
        if e.u8(saves.SELECT_MODE_CURSOR) == saves.position(e, "gauntlet"):
            break
        e.press("DOWN", 8)
        e.wait(14)
        w.shot("Select Mode: DOWN turns the wheel", force=True)
        e.wait(46)
    e.wait(30)
    w.shot("Select Mode: GAUNTLET (between Campaign and Versus)", force=True)
    e.press("A", 8)
    w.watch("GAUNTLET picked: to the map selector", 200, every=15, until=lambda: d.step() == ga.SELECTOR)
    d.wait_step(ga.SELECTOR)
    w.shot("Map selector: Cinder Sea, the enemies you will face", force=True)
    e.press("A", 6)
    w.watch("Map picked: to the CO screen", 200, every=15, until=d.on_co_screen)
    d.wait_co_screen()
    w.shot("CO screen: any of 36 COs", force=True)
    for k in range(3):
        e.press("RIGHT", 6)
        e.wait(40)
        w.shot("CO screen: browsing COs")
    d.choose_co([ga.ARIA])
    w.shot("CO screen: Aria chosen", force=True)
    for _ in range(60):
        if not d.on_co_select():
            break
        d.co_screen_a()
        e.wait(20)
    d.wait_step(ga.COLOURS)
    w.shot("Colour pick: what the enemies leave (Orange Star)", force=True)
    for k in range(2):
        e.press("RIGHT", 4)
        e.wait(14)
        w.shot("Colour pick: browsing the free colours", force=True)
    d.pick_colour(None)
    sc = lambda ee: ee.press("A", 4) if d.scripts_running() else None
    w.watch("Loading the battle: mission card", 1500, every=25, press=None, until=d.in_battle)
    quiet = 0
    for _ in range(120):
        e.wait(40)
        w.shot("Cinder Sea: Drake's opening lines")
        if d.scripts_running():
            quiet = 0
            e.press("A", 4)
        else:
            quiet += 1
            if quiet >= 4:
                break
    d.wait_control()
    g._units_base = g._players_base = None
    g.goto(6, 16)
    e.wait(40)
    w.shot("Day 1: your island and fleet", force=True)
    g.goto(24, 16)
    e.wait(40)
    w.shot("Day 1: Drake's island and fleet", force=True)
    for name, at, who in (("drake", (5, 4), "Sensei"), ("sensei", (26, 4), "Hawke")):
        d.capture(ctx, ga.CINDER[name])
        w.watch(f"{name.capitalize()}'s HQ falls: {who} arrives", 2400, every=40, press=sc, until=lambda: not d.scripts_running() and d.in_battle())
        d.settle()
        g.goto(*at)
        e.wait(60)
        w.shot(f"{who}'s line on the map", force=True)
    d.capture(ctx, ga.CINDER["hawke"])
    w.watch("Hawke's HQ falls: victory", 9000, every=40, press=lambda ee: ee.press("A", 4) if (d.scripts_running() or not d.in_battle()) and not d.select_mode_up() else None,
            until=lambda: d.select_mode_up())
    e.wait(90)
    w.shot("Back on Select Mode", force=True)
    ctx.check(d.select_mode_up(), "the run ended on Select Mode")
    # the curated set: per step at most `keep` frames, evenly spread (the dialogue steps keep more: each box is a line)
    groups = {}
    for p, label in w.shots:
        groups.setdefault(label, []).append(p)
    curated = []
    for label, ps in groups.items():
        keep = 8 if ("lines" in label or "arrives" in label or "victory" in label) else 3
        step = max(1, len(ps) / keep)
        curated += [(ps[int(i * step)], label) for i in range(min(keep, len(ps)))]
    order = {p: i for i, (p, _) in enumerate(w.shots)}
    w.shots = sorted(curated, key=lambda t: order[t[0]])
    # sheets: 12 frames each, 4 across, with the step under each frame
    per = 12
    for s in range(0, len(w.shots), per):
        part = w.shots[s:s + per]
        sheet = Image.new("RGB", (4 * 480, ((len(part) + 3) // 4) * 340), (24, 24, 32))
        dr = ImageDraw.Draw(sheet)
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
        except OSError:
            font = None
        for i, (p, label) in enumerate(part):
            im = Image.open(p).convert("RGB").resize((480, 320), Image.NEAREST)
            x, y = (i % 4) * 480, (i // 4) * 340
            sheet.paste(im, (x, y))
            dr.text((x + 6, y + 322), f"{s + i + 1}. {label}", fill=(240, 220, 120), font=font)
        sheet.save(os.path.join(ctx.out, f"walkthrough_sheet_{s // per + 1}.png"))
    ctx.log(f"{len(w.shots)} frames")
