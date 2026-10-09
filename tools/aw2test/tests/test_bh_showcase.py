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


def hide_panels(e):
    """stitch.hide_hud, and the semi-transparent info window too (a sprite in OBJ mode 1)."""
    import struct
    b = bytearray(e.read(stitch.OAM_BUFFER, 0x400))
    for k in range(128):
        a0, _, a2 = struct.unpack_from("<HHH", b, 8 * k)
        if ((a2 >> 10) & 3) < 3 or (a0 >> 10) & 3 in (1, 2):
            struct.pack_into("<H", b, 8 * k, 0x0200 | 160)
    e.write(stitch.OAM_BUFFER, bytes(b))
    e.wait(1)


def keep(ctx, e, name, hide=False):
    if hide:
        hide_panels(e)
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
    """M31: a Vault Truck on the North Road with an escort, seen by a Black Hole Recon, under the north-east Black Cannon (fog on)."""
    import test_bh_review as r
    e, g, d = r.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    truck = next(u for u in g.units(2) if u["type"] == 7)
    escort = [u for u in g.units(2) if u["type"] in (1, 2, 5) and u["id"] != truck["id"]]
    mine = next(u for u in g.units(1) if u["type"] in (6, 5, 3, 1))
    cells = [(26, 6), (25, 6), (27, 6), (24, 6)]
    for u, c in zip([truck] + escort[:1] + [mine], [cells[0], cells[2], cells[3]]):
        if g.unit_at(*c):
            d.remove_unit(g.unit_at(*c))
        d.place_unit(u, *c)
    e.wait(20)
    g.open_map_menu()          # (the map redraws its fog once the menu has opened and closed)
    e.wait(20)
    e.press("B", 4)
    e.wait(60)
    g._units_base = g._players_base = None
    for _ in range(4):
        try:
            g.goto(27, 0)
            break
        except Exception:
            e.wait(150)
    e.wait(30)
    keep(ctx, e, "bh-vault-quiet", hide=True)
    for k, (x, y) in enumerate(((30, 3), (30, 7), (24, 4), (28, 7))):     # (raw frames: the cursor on empty ground, its terrain window)
        try:
            g.goto(x, y)
        except Exception:
            continue
        e.wait(40)
        keep(ctx, e, f"bh-vault-raw{k}")
    # the day-2 scene over the same view: its box takes the info window's place
    a2.end_turn(e, g, d)
    got = 0
    for i in range(600):
        t = d.text_shown()
        if t:
            e.wait(150)
            got += 1
            keep(ctx, e, f"bh-vault-scene{got}")
            if got >= 3:
                break
            e.press("A", 4)
            e.wait(30)
        elif d.scripts_running():
            e.press("A", 4)
        e.wait(10)
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


@test(modes=("ds",))
def bh_showcase_cannon_days(ctx):
    """M31's north-east Black Cannon in fog on day 1 and day 5 (crops for the release notes)."""
    import test_bh_review as r
    e, g, d = r.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    for day in (1, 5):
        while e.u16(0x03004080) < day:
            a2.end_turn(e, g, d)
            for i in range(400):
                if d.scripts_running():
                    e.press("A", 4)
                e.wait(10)
                if not d.scripts_running() and g.current_army() == 1 and i > 5:
                    break
            d.wait_control()
        for _ in range(4):
            try:
                g.goto(27, 4)
                break
            except Exception:
                e.wait(150)
        e.wait(40)
        keep(ctx, e, f"cannon-day{day}", hide=True)
    e.close()
