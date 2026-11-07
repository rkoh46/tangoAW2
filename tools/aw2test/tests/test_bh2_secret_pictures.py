"""Pictures of the BH2 Campaign's secret mission M32 Through the Door for review (`-k bh2_secret_pictures`; AW2TEST_REVIEW_DIR copies them): per look (AW2, Dual Strike with the tilt, Dual Strike flat)
the day-1 game window and the whole map stitched (the tilt is a host-side overlay, so its stitch is the flat one); the pre-scene's boxes with the Silver Nova faces. Facts of the map go to the log."""

import os
import shutil

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import boxshots, stitch
from aw2test.harness import test
from tests.test_bh_review import Quiet
from tests.test_gauntlet_lines_pictures import LOOKS, settled_png


def keep(ctx, path, name):
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out and path:
        os.makedirs(out, exist_ok=True)
        shutil.copy(path, os.path.join(out, name))


@test(modes=("ds",))
def bh2_secret_pictures_maps(ctx):
    for look, env in LOOKS:
        e, g, d = b2.enter(ctx, 32, env=env)
        d.leave_setup()
        a2.intro(ctx, e, d, "m32", ())
        d.wait_control()
        g._units_base = g._players_base = None
        w, h = d.size()
        if look == "aw2":
            ctx.log(f"M32: map {w} x {h}")
            for a in range(1, 6):
                try:
                    p = g.player(a)
                    ctx.log(f"army {a}: co {p.get('co')} colour {p.get('colour')} funds {p.get('funds')} units {len(g.units(army=a))}")
                except Exception as ex:
                    ctx.log(f"army {a}: {ex}")
        keep(ctx, settled_png(ctx, e, f"{look}_day1"), f"m32_{look}_day1.png")
        if look != "ds_tilt":
            p = stitch.stitch(Quiet(ctx), g, f"{look}_whole", w, h)
            keep(ctx, p, f"m32_{look}_whole_full.png")
        e.close()


@test(modes=("ds",))
def bh2_secret_pictures_scene(ctx):
    e, g, d = b2.boot(ctx, 32)
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, 31, b2.PICKS.get(32, []), "m32", setup_only=True)
    d.leave_setup()
    paths = boxshots.shoot(ctx, e, d, "m32_pre", patience=200, max_boxes=45)
    sheets = boxshots.sheet(ctx, paths, "m32_pre")
    for p in sheets:
        keep(ctx, p, os.path.basename(p))
    ctx.check(len(paths) >= 12, f"{len(paths)} boxes photographed (the scene was tightened to about 17 shown boxes)")
    e.close()


WAVES = ((3, "day3_vanguard", (12, 4)), (5, "day5_siege", (37, 24)), (7, "day7_fleet", (22, 4)))


@test(modes=("ds",))
def bh2_secret_pictures_waves(ctx):
    """Per look (AW2 and Dual Strike with the tilt): the first box of each wave's scene (the wave has landed on the map behind it) and the map on a wave cell once the scene is over."""
    from aw2test import dscampaign as dc
    for look, env in LOOKS[:2]:
        e, g, d = b2.enter(ctx, 32, env=env)
        d.leave_setup()
        a2.intro(ctx, e, d, "m32", ())
        d.wait_control()
        g._units_base = g._players_base = None
        for day, tag, cell in WAVES:
            for _ in range(12):
                if e.u16(0x03004080) >= day:
                    break
                d0 = e.u16(0x03004080)
                a2.end_turn(e, g, d)
                for _ in range(4000):
                    if e.u16(0x03004080) > d0 or e.u8(dc.LAST_RESULT):
                        break
                    if d.scripts_running() and not d.text_shown():
                        e.wait(20)
                    elif d.scripts_running():
                        e.press("A", 4)
                    e.wait(20)
            # (the day's scene: its first box typed out, then the rest)
            first = None
            for _ in range(600):
                if d.text_shown():
                    e.wait(150)
                    first = settled_png(ctx, e, f"{look}_{tag}_box1")
                    break
                e.wait(10)
            keep(ctx, first, f"m32_{look}_{tag}_box1.png")
            a2.boxes(e, d, 3000)
            d.wait_control()
            g._units_base = g._players_base = None
            g.goto(*cell)
            e.wait(60)
            keep(ctx, settled_png(ctx, e, f"{look}_{tag}_map"), f"m32_{look}_{tag}_map.png")
        e.close()


@test(modes=("ds",))
def bh2_secret_lander_cargo(ctx):
    """Day 7's Lander arrives carrying one Infantry and one Neotank (UnitDef::carry), and unloads them on a beach within a few turns."""
    from aw2test import dscampaign as dc
    e, g, d = b2.enter(ctx, 32)
    d.leave_setup()
    a2.intro(ctx, e, d, "m32", ())
    d.wait_control()
    g._units_base = g._players_base = None
    a2.to_day(e, g, d, 7)
    g._units_base = g._players_base = None
    lander = next((u for u in g.units(army=2) if u["type"] == 23), None)
    ctx.require(lander is not None, "day 7's Lander is on the map")
    raw = e.read(g.unit_addr(lander["id"]), 12)
    ids = [b for b in raw[7:9] if b]
    held = sorted(g.unit(i)["type"] for i in ids)
    ctx.log(f"Lander {lander['id']} at {(lander['x'], lander['y'])}: flags {raw[1]:#x}, cargo ids {ids}, types {held}")
    ctx.log("army 2 units near: " + str([(u["id"], u["type"], u["x"], u["y"], hex(u["flags"])) for u in g.units(army=2) if abs(u["x"] - 20) < 6 and u["y"] < 8]))
    ctx.check(held == [1, 8], f"the Lander carries an Infantry and a Neotank (types {held})")
    ctx.check(bool(raw[1] & 0x10), "the transport's has-cargo flag is set")
    unloaded = False
    for _ in range(5):
        try:
            g.end_turn(human=1, max_frames=60000)
            d.wait_control()
        except Exception as ex:
            # (the test player only ends its turns: the computer can win the battle first, back on the world map; a slot emptied before that counts)
            ctx.log(f"turns over: army {g.current_army()} day {e.u16(0x03004080)} in battle {d.in_battle()} scripts {d.scripts_running()} text {d.text_shown()!r}: {ex}")
            e.shot(os.path.join(ctx.out, 'stuck'))
            break
        g._units_base = g._players_base = None
        l = g.unit(lander["id"])
        raw = e.read(g.unit_addr(lander["id"]), 12)
        ctx.log(f"day {e.u16(0x03004080)}: Lander at {(l['x'], l['y'])} cargo {list(raw[7:9])}")
        if list(raw[7:9]) != ids:
            unloaded = True          # (a unit left the hold: the transport unloads; the second may wait for a free beach cell)
            if not any(raw[7:9]):
                break
    ctx.check(unloaded, "the Lander unloaded its cargo on a beach")
    e.close()
