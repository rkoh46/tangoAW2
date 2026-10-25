"""In-game pictures of Versus maps, for before / after sheets (aw2dev maps sheet): each map is selected in Offline Versus' game tabs, started and swept
(aw2test.stitch), the whole map as one picture `<name>_full.png` in the test's folder and in $AW2TEST_MAP_IMAGES. Runs only with
AW2TEST_MAP_SHEET=<names, comma separated> set (the registry's other map tests check them; these only take pictures)."""

import os

from aw2test.harness import Skip, test
from aw2test.stitch import stitch
from tests import test_ds_maps as dm

# maps outside test_ds_maps' tables
EXTRA = {"Pentagon Atoll": (0xC9, 9)}


def select_on_aw2_table(ctx, name):
    import shutil, struct
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game, NavError
    mid, tab = dm.ALL[name]
    _, w, h, tiles, _ = dm.built(name)
    save = os.path.join(ctx.out, "map.sav")
    shutil.copy(paths.base_save(), save)
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    e.wait(700)
    e.press("START", 8)
    e.wait(300)
    e.press("A", 8)
    e.wait(150)
    for _ in range(8):
        cur = e.u8(dm.SELECT_MODE_CURSOR)
        if cur == dm.SELECT_MODE_VERSUS:
            break
        e.press("UP" if cur < dm.SELECT_MODE_VERSUS else "DOWN", 8)
        e.wait(50)
    e.press("A", 8)
    e.wait(150)
    e.w8(0x0203C900, 1)
    e.press("A", 8)
    e.wait(150)
    e.press("L+R", 12)
    e.wait(120)
    if not g.press_until("LEFT", lambda: e.u8(dm.MAP_TAB) == tab, tries=12, hold=8, settle=50):
        raise NavError(f"tab {tab} not reached (tab {e.u8(dm.MAP_TAB)})")
    e.wait(30)

    def previewed():
        b = e.read(dm.PREVIEW, 2 + 2 * w * h)
        return b[0] == w and b[1] == h and list(struct.unpack_from(f"<{w * h}H", b, 2)) == tiles

    found = False
    for _ in range(40):
        if previewed():
            found = True
            break
        e.press("DOWN", 8)
        e.wait(24)
    return g, found or e.wait_until(previewed, 400, step=10)


def sheet(ctx, name):
    want = [n.strip() for n in os.environ.get("AW2TEST_MAP_SHEET", "").split(",") if n.strip()]
    if name not in want:
        raise Skip("AW2TEST_MAP_SHEET does not name it")
    dm.ALL.update(EXTRA)
    if name in dm.REPLACED:
        # (Dual Strike's table has its own maps at these ids: ds_versus::TABLE_FLAG = 1 before the list is built has Offline Versus use AW2's table, as a game
        # continued from a save made on it does; the same maps online are these)
        g, found = select_on_aw2_table(ctx, name)
    else:
        g, found = dm.select_map(ctx, name)
    ctx.log(f"found {found}")
    ctx.require(found, f"{name} is on its tab with its preview")
    dm.to_teams(g)
    ctx.log("on teams")
    dm.start(ctx, g, humans=(1,))
    ctx.log("started")
    g.wait_for_input()
    ctx.log("control")
    m, w, h, _, _ = dm.built(name)
    stitch(ctx, g, name, w, h)


def _make(name):
    def fn(ctx):
        sheet(ctx, name)
    fn.__name__ = "map_sheet_" + name.lower().replace(" ", "_")
    test(modes=("ds",))(fn)


for _name in ("Crystal Isles", "Dune Fork", "Cinder Flats", "Black Wastes", "Pentagon Atoll"):
    _make(_name)
