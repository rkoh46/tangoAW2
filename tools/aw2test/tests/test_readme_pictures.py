"""Pictures for the README (opt-in: `AW2TEST_README_DIR=<dir> python3 tools/aw2test/run.py -k readme_pictures`): the title screen with the version badge, and a
picture of every fully typed box of an Emerald Sun mission's intro (`AW2TEST_README_MISSION`, default 1) for choosing the story scene. 240x160 BMPs, plus 3x
nearest-neighbour PNGs (720x480, the README's size) when PIL is there."""

import os

from aw2test import bhact2 as a2
from aw2test import escampaign as es
from aw2test import paths
from aw2test.emu import Emu
from aw2test.harness import test
from aw2test.story import clean


def _save(e, out, name):
    p = e.shot(os.path.join(out, name))
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(out, name + ".png"))
    except ImportError:
        pass


@test(modes=("ds",))
def readme_pictures(ctx):
    out = os.environ.get("AW2TEST_README_DIR")
    if not out:
        return
    os.makedirs(out, exist_ok=True)
    e = Emu(save=paths.base_save(), ds=True, env=es.ENV)
    e.wait(700)
    e.press("START", 8)
    for k in range(6):          # (the title screen after the intro is skipped; the badge and its version are drawn on it)
        e.wait(60)
        _save(e, out, f"title{k}")
    e.close()
    n = int(os.environ.get("AW2TEST_README_MISSION", "1"))
    e, g, d = es.boot(ctx, n)
    d.wait_world_map()
    d.pick_mission()
    picks = es.PICKS.get(n, [])
    if picks:
        d.choose_cos(len(picks), prefs=list(picks))
    k = 0

    def boxes(frames, forced=False):
        """A picture of each box once its text has been typed out (the screen stops changing), A through them; returns when `frames` have passed."""
        nonlocal k
        last, stable, spent, saved = None, 0, 0, None
        while spent < frames:
            if d.in_setup():
                d.deploy()
            t = d.text_shown()
            stable = stable + 1 if t and t == last else 0
            last = t
            if t and stable == 6 and "Save current data" not in t and t != saved:
                prev = None
                for _ in range(40):         # (until two shots 12 frames apart are the same picture: typed out, no fade)
                    cur = open(e.shot(os.path.join(out, "cur")), "rb").read()
                    if cur == prev:
                        break
                    prev = cur
                    e.wait(12)
                k += 1
                saved = t
                _save(e, out, f"m{n}_{'win' if forced else 'box'}{k:03d}")
                with open(os.path.join(out, f"m{n}_boxes.txt"), "a") as f:
                    f.write(f"{k:03d} {clean(t)}\n")
            if d.scripts_running() and stable >= 20:
                e.press("A", 4)
                stable = 0
            e.wait(4)
            spent += 4

    boxes(int(os.environ.get("AW2TEST_README_FRAMES", "6000")))
    if os.environ.get("AW2TEST_README_WIN"):
        d.wait_control()
        g._units_base = g._players_base = None
        d.force_win()
        boxes(6000, forced=True)
    e.close()
