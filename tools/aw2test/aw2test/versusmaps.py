"""The Versus map list as the game shows it (SELECT MAP's tabs, with the Dual Strike pack): `lists()` reads every tab's map ids from the game's own list buffer
(crate::five_map::LIST_IDS) once and keeps them in out/versus_map_list.json (renewed when the runner or a ROM changes), so tests can be made from the real list;
`select(ctx, tab, row)` opens Versus > New > that tab and row like a player and stops on the Teams screen."""

import json
import os

from . import gauntlet as ga
from . import paths
from .ram import VS_MAP
from .emu import Emu
from .game import MAP_TAB, SELECT_MODE_CURSOR, SELECT_MODE_VERSUS, Game, NavError


def _open_tabs(e):
    """Boot, Versus > New > SELECT MAP with the game's own tabs (L and R together, as game.boot_to_teams)."""
    e.wait(700)
    e.press("START", 8)
    e.wait(300)
    e.press("A", 8)
    e.wait(150)
    for _ in range(8):
        cur = e.u8(SELECT_MODE_CURSOR)
        if cur == SELECT_MODE_VERSUS:
            break
        e.press("UP" if cur < SELECT_MODE_VERSUS else "DOWN", 8)
        e.wait(50)
    if e.u8(SELECT_MODE_CURSOR) != SELECT_MODE_VERSUS:
        raise NavError("Select Mode's cursor did not reach Versus")
    e.press("A", 8)
    e.wait(150)
    e.press("A", 8)
    e.wait(150)
    e.press("L+R", 12)
    e.wait(120)


def _stamp():
    parts = [paths.runner("aw2_script"), paths.ds_rom(), paths.aw2_rom()]
    return [os.path.getmtime(p) if os.path.exists(p) else 0 for p in parts]


def scan():
    """{tab: [map ids]} for every tab the offline Versus list has, by LEFT presses until the first tab comes round again."""
    e = Emu(save=paths.base_save(), ds=True)
    try:
        _open_tabs(e)
        out = {}
        for _ in range(16):
            tab = e.u8(MAP_TAB)
            if tab in out:
                break
            out[tab] = list(e.read(ga.LIST_IDS, e.u8(ga.LIST_LAST) + 1))
            e.press("LEFT", 8)
            e.wait(80)
        return out
    finally:
        e.close()


def lists():
    """The tabs and their map ids (cached). Empty without the Dual Strike ROM or the runner."""
    if not (os.path.exists(paths.ds_rom()) and os.path.exists(paths.runner("aw2_script"))):
        return {}
    cache = os.path.join(paths.out_dir(), "versus_map_list.json")
    try:
        with open(cache) as f:
            c = json.load(f)
        if c.get("stamp") == _stamp():
            return {int(k): v for k, v in c["tabs"].items()}
    except (OSError, ValueError, KeyError):
        pass
    tabs = scan()
    tmp = cache + f".{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump({"stamp": _stamp(), "tabs": tabs}, f)
    os.replace(tmp, cache)
    return tabs


def entries():
    """[(tab, row, map id)] of every listed map."""
    return [(tab, row, mid) for tab, ids in sorted(lists().items()) for row, mid in enumerate(ids)]


def select(ctx, tab, row, want):
    """A Game on the Teams screen of the map at (tab, row), which must be map id `want`."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    _open_tabs(e)
    if not g.press_until("LEFT", lambda: e.u8(MAP_TAB) == tab, tries=16, hold=8, settle=50):
        raise NavError(f"tab {tab} not reached (tab {e.u8(MAP_TAB)})")
    e.wait(30)
    for _ in range(row):
        e.press("DOWN", 8)
        e.wait(24)
    e.wait(60)
    e.press("A", 8)
    if not e.wait_until(g.on_teams, 400, step=10):
        raise NavError("Teams screen did not open")
    e.wait(40)
    if e.u8(VS_MAP) != want:
        raise NavError(f"the Teams screen is for map {e.u8(VS_MAP):#x}, not {want:#x}")
    return g


def _selector(e):
    last = e.u8(ga.LIST_LAST)
    ids = list(e.read(ga.LIST_IDS, last + 1))
    return ids, e.u32(ga.LIST_FIRST) + e.u32(ga.LIST_CURSOR_ROW)
