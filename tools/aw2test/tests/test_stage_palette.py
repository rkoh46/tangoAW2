"""A stage switch keeps the dialogue window's colours (crate::stage): M31's switch to the Last Citadel (the Snow look) reloads the map's graphics; the window's BG palette banks must be the same as before
the switch, and the stage's opening scene is photographed (`m31b_scene.bmp`). Logs which BG/OBJ banks changed."""

import importlib.util
import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import harness
from aw2test.harness import test

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers5", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]

PAL = 0x0500_0000


def banks(e):
    raw = e.read(PAL, 0x400)
    return [raw[32 * k:32 * k + 32] for k in range(32)]


@test(name="stage_switch_keeps_the_window_colours", modes=("ds",))
def stage_switch_keeps_the_window_colours(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    bp.to_player_turn(e, g, d)
    d.wait_control()
    before = banks(e)
    for k, (name, cell, army, nation) in enumerate(bp.HQS):
        bp.capture(ctx, e, g, d, cell, 5)
        if k < len(bp.HQS) - 1:
            bp.settle(e, g, d)
    bp.wait_stage(ctx, e, g, d, 1)
    for _ in range(400):
        if d.text_shown():
            break
        e.wait(10)
    e.wait(90)
    after = banks(e)
    a2.pic(ctx, e, "m31b_scene")
    ctx.log("BG banks changed: " + str([k for k in range(16) if before[k] != after[k]]))
    ctx.log("OBJ banks changed: " + str([k - 16 for k in range(16, 32) if before[k] != after[k]]))
    ctx.check(all(after[k] == before[k] for k in (8, 13)), "the window's banks (BG 8 and 13) are as before the switch (OBJ 12 has a cycling colour)")
    for k in range(32):
        ctx.log(f"bank {k:2d} before {before[k].hex()}")
        ctx.log(f"bank {k:2d} after  {after[k].hex()}")
    e.close()


@test(name="stage_palette_probe_m15_window", modes=("ds",))
def stage_palette_probe_m15_window(ctx):
    """(Probe) M15, a Snow mission from its start: the BG/OBJ banks while its first dialogue box shows."""
    e, g, d = b2.enter(ctx, 15)
    d.leave_setup()
    for _ in range(600):
        if d.text_shown():
            break
        e.press("A", 4) if not d.scripts_running() else None
        e.wait(10)
    e.wait(90)
    for k, b in enumerate(banks(e)):
        ctx.log(f"bank {k:2d} m15 {b.hex()}")
    a2.pic(ctx, e, "m15_scene")
    e.close()
