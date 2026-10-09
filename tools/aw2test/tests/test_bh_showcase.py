"""Clean in-game frames of the BH Campaign for the README (`-k bh_showcase`): raw 240x160 BMPs in the folder named by
AW2TEST_SHOWCASE_DIR (scaled 3x nearest to 720x480 PNGs by the caller, as docs/screenshots/ds-world-map.png is)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test import stitch
from aw2test.harness import test

OUT = os.environ.get("AW2TEST_SHOWCASE_DIR")
BONDS = 0x1FF << 12


def keep(ctx, e, name, hide=False):
    if hide:
        stitch.hide_hud(e)
    p = e.shot(os.path.join(ctx.out, name))
    if OUT:
        import shutil
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(p, os.path.join(OUT, name + ".bmp"))
    return p


@test(modes=("ds",))
def bh_showcase_world_map(ctx):
    # M1..M11 won, six bonds earned: the legend with its gold star
    e, g, d = a2.boot(ctx, (1 << 11) - 1, 0x7F | (0x3F << 12), picks={}, at=11)
    d.wait_world_map()
    e.wait(240)
    keep(ctx, e, "bh-world-map")
    e.close()


@test(modes=("ds",))
def bh_showcase_story(ctx):
    import test_bh_review as r
    e, g, d = r.enter(ctx, 1)
    ctx.require(d.force_win(), "M1: a forced win")
    seen = False
    for i in range(3000):
        t = d.text_shown()
        if t and "ledger" in t:
            e.wait(150)
            keep(ctx, e, "bh-story")
            seen = True
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    ctx.require(seen, "Sturm's ledger line shown")
    e.close()


@test(modes=("ds",))
def bh_showcase_crumb(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["crumb", "jugger"])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(200)
    keep(ctx, g.e, "bh-crumb")
    g.e.close()


@test(modes=("ds",))
def bh_showcase_fortress(ctx):
    import test_bh_review as r
    e, g, d = r.enter(ctx, 28)
    d.leave_setup()
    a2.intro(ctx, e, d, "m28", shots=())
    stable = 0
    for _ in range(3000):
        stable = stable + 1 if g.current_army() == 5 and not d.scripts_running() else 0
        if stable >= 5:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    d.wait_control()
    g._units_base = g._players_base = None
    for k, (x, y) in enumerate(((8, 13), (9, 14), (8, 15), (10, 12), (7, 13))):
        for _ in range(4):
            try:
                g.goto(x, y)
                break
            except Exception:
                e.wait(150)
        e.wait(20)
        keep(ctx, e, f"bh-fortress-{k}", hide=True)
    e.close()


@test(modes=("ds",))
def bh_showcase_vault(ctx):
    import test_bh_review as r
    e, g, d = r.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    shot = False
    for turn in range(6):
        a2.end_turn(e, g, d)
        for i in range(400):
            t = d.text_shown()
            if t and ("Awake" in t or "NINE COLUMNS" in t or "Black Cannons" in t):
                e.wait(150)
                keep(ctx, e, "bh-vault")
                shot = True
                for _ in range(300):                 # (the scene out, then the camera on the north cannon)
                    if d.scripts_running():
                        e.press("A", 4)
                    e.wait(10)
                d.wait_control()
                g._units_base = g._players_base = None
                for k, (x, y) in enumerate(((27, 4), (26, 5), (25, 3))):
                    for _ in range(4):
                        try:
                            g.goto(x, y)
                            break
                        except Exception:
                            e.wait(150)
                    e.wait(30)
                    keep(ctx, e, f"bh-vault-cannon{k}", hide=True)
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
            if e.u16(0x03004080) >= 5:
                break
        if shot or e.u8(bh.dc.LAST_RESULT):
            break
    ctx.require(shot, "the day-4 cannon scene was shown")
    e.close()


@test(modes=("ds",))
def bh_showcase_takeover(ctx):
    """M30's stage-two takeover: the existing proof test's frames, taken with the cursor and the info panels hidden."""
    import test_bh_act5 as t5
    orig = t5.a5.pic

    def clean(c, e, name, *a, **k):
        stitch.hide_hud(e)
        return orig(c, e, name + "_clean", *a, **k)
    t5.a5.pic = clean
    try:
        t5.bh_act5_m30_takeover_proof(ctx)
    finally:
        t5.a5.pic = orig
