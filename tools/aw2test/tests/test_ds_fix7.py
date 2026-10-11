"""Fixes found in the final picture sheets review (Dual Strike look)."""

import os

from aw2test.harness import test


def picture(ctx, name, cursor, snap=False):
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}
    if snap:
        env["TANGOAW2_TILT_SNAP"] = "1"
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 6, 4).unit(2, "tank", 22, 5)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.goto(*cursor)
    g.e.wait(50)
    return ctx.shot(g, name)


@test(modes=("ds",))
def ds_tilt_camera_settles_without_pictures(ctx):
    """The tilted camera glides on console frames, not on pictures: waiting 50 frames and then taking one
    picture shows the cursor's area, the same as a camera that snapped (it used to take one 30% step)."""
    from PIL import Image
    a = Image.open(picture(ctx, "glide", (22, 5))).convert("RGB").load()
    b = Image.open(picture(ctx, "snap", (22, 5), snap=True)).convert("RGB").load()
    diff = sum(1 for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    ctx.log(f"{diff} pixels differ from the snapped camera")
    ctx.check(diff < 400, f"after 50 frames the camera is where it settles ({diff} pixels differ)")


def menu_dialogue_picture(ctx, tilt):
    from aw2test import campaigns as cp
    from aw2test import dscampaign as dc
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    os.environ.update({"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_SNAP": "1"})
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    cp.aw2_new(e, d, True)
    if d.scripts_running():
        d.wait_control()
    g._units_base = g._players_base = None
    m = g.open_map_menu()
    for _ in range(len(m["names"]) + 2):
        if e.u8(m["cursor_addr"]) == len(m["names"]) - 1:
            break
        e.press("DOWN", 4)
        e.wait(8)
    e.press("A", 4)
    ctx.require(e.wait_until(d.scripts_running, 300, step=5), "the tutorial dialogue comes up over the map menu")
    e.wait(120)
    for _ in range(12):
        e.shot(os.path.join(ctx.out, "warm"))
    return e.shot(os.path.join(ctx.out, f"menu_box_{'tilt' if tilt else 'flat'}"))


@test(modes=("ds",))
def ds_tilt_under_the_bottom_dialogue_box(ctx):
    """The dialogue box at the bottom with the map menu open (a handler that switches the registers at the box's
    line): the box's rows keep the console's picture and the map above them stays tilted (it fell back to flat)."""
    from PIL import Image
    a = Image.open(menu_dialogue_picture(ctx, False)).convert("RGB").load()
    b = Image.open(menu_dialogue_picture(ctx, True)).convert("RGB").load()
    top = sum(1 for y in range(0, 100) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    box = sum(1 for y in range(116, 160) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    ctx.log(f"{top} pixels differ above the box, {box} inside it")
    ctx.check(top > 3000, f"the map above the box is tilted ({top} pixels differ from the flat one)")
    ctx.check(box < 200, f"the box keeps the console's picture ({box} pixels differ)")


def front_view_picture(ctx, tilt):
    from aw2test import dscampaign as dc, twofront as tf, paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    os.environ.update({"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_SNAP": "1"})
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=dc.ORDER.index(8))
    d.wait_map()
    d.through_dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    g.wait_for_input()
    g.open_map_menu()
    g.choose("Front", g.MAP_MENU)
    e.wait(200)
    for _ in range(10):
        e.shot(os.path.join(ctx.out, "warm"))
    return e.shot(os.path.join(ctx.out, f"front_{'tilt' if tilt else 'flat'}"))


@test(modes=("ds",))
def ds_two_front_view_has_dual_strikes_cursor_with_the_tilt(ctx):
    """The other front's view is not the battle map (the tilt leaves it as drawn): with the tilt on it shows Dual
    Strike's cursor as the flat map does, not AW2's yellow brackets."""
    from PIL import Image
    a = Image.open(front_view_picture(ctx, False)).convert("RGB").load()
    b = Image.open(front_view_picture(ctx, True)).convert("RGB").load()
    diff = sum(1 for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    ctx.log(f"{diff} pixels differ from the flat picture")
    ctx.check(diff < 150, f"the view is the same with the tilt on ({diff} pixels differ)")
