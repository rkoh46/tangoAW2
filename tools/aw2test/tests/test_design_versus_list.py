"""The Design Room's maps in Versus: a map built in the editor and saved is on
Versus's Design Maps list (right away from the editor, and after a reboot), can
be played, and stays there through a Dual Strike session; with and without the
pack. Black Hole counts as an army for the editor's "Play OK!" test: Orange Star
against Black Hole alone was "not playable" (the test only looked at the four
armies), so Save wrote it with army count 0 and Versus never listed it. An army
with an HQ and nothing else is not an army for AW2 (Black Hole's included). A
map saved by an older version that way is listed once it is loaded in the
editor and saved again."""

import os
import shutil

from aw2test import campaigns as cp
from aw2test import dscampaign as dc
from aw2test import paths, saves
from aw2test.editor import Editor, HQ
from aw2test.emu import Emu
from aw2test.game import Game, NavError, MAP_TAB, MAP_TAB_DESIGN
from aw2test.harness import test
from aw2test.save import DesignMap, write_design_map

CITY = 0x0A
PLAIN = 0x01
INFANTRY = 1
DESIGN = {1: 5, 2: 6, 3: 7}
DESIGN_ID = {1: 0xB4, 2: 0xB5, 3: 0xB6}


def boot(ctx, save):
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def corners(w, h):
    """Each army's HQ, city and unit cells (the unit and city toward the middle)."""
    return {1: ((0, 0), (2, 0), (1, 1)), 2: ((w - 1, h - 1), (w - 3, h - 1), (w - 2, h - 2)),
            3: ((w - 1, 0), (w - 3, 0), (w - 2, 1)), 4: ((0, h - 1), (2, h - 1), (1, h - 2)),
            5: ((w // 2, h // 2), (w // 2 + 2, h // 2), (w // 2 + 1, h // 2 + 1))}


def build(ed, armies, city=True, unit=True):
    """HQ, a city and an Infantry for each army in `armies`. `city` / `unit`
    False: that army gets neither (an HQ alone, or an HQ and a city). Returns
    {(x, y): (army, type)}."""
    w, h = ed.size()
    cells = corners(w, h)
    units = {}
    for a in armies:
        hq, cty, u = cells[a]
        ed.place(HQ, a, *hq)
        if city is True or (isinstance(city, (set, frozenset)) and a in city):
            ed.place(CITY, a, *cty)
        if unit is True or (isinstance(unit, (set, frozenset)) and a in unit):
            ed.place(PLAIN, None, *u)
            ed.place_unit(a, INFANTRY, *u)
            units[u] = (a, INFANTRY)
    return units


def design_tab_ids(e):
    """From Select Mode's wheel: Versus > New, every tab walked; {tab: ids}."""
    saves.wheel_to(e, saves.VERSUS)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 1)
    e.press("A", 8)
    e.wait(150)
    out = {}
    for _ in range(14):
        t = e.u8(MAP_TAB)
        if t in out:
            break
        n = e.u8(saves.LIST_LAST) + 1
        out[t] = list(e.read(saves.LIST_IDS, n))
        e.press("LEFT", 8)
        e.wait(50)
    return out


def leave_versus(e):
    saves.back_to_select_mode(e)


def play(ctx, e, g, slot, units, label):
    """From Select Mode: Versus > New > Design Maps > the slot's map, the
    Teams screen, the rules, the battle: its map, its units."""
    saves.versus_select_map(g, MAP_TAB_DESIGN, DESIGN_ID[slot])
    saves.versus_start(g, humans=(1,))
    ctx.eq(g.playst()["map"], DESIGN_ID[slot], f"{label}: the battle is on the design map")
    have = {(u["x"], u["y"]): (u["army"], u["type"]) for u in g.units()}
    ctx.eq(have, units, f"{label}: the battle's units are the design's")
    ctx.check(not g.battle_over(), f"{label}: the battle is on")


def save_design(ctx, name, slot, armies, **kw):
    """Boots the base save, builds the design in the editor, saves it in
    `slot` and leaves the editor. Returns (emu, game, editor, units, image)."""
    save = os.path.join(ctx.out, f"{name}.sav")
    shutil.copyfile(paths.base_save(), save)
    e, g = boot(ctx, save)
    ed = Editor(e)
    ed.boot()
    units = build(ed, armies, **kw)
    ed.save(slot)
    img = saves.flash(e, os.path.join(ctx.out, f"{name}_saved"))
    ctx.require(img.slot(DESIGN[slot]) is not None, f"{name}: design slot {slot} written")
    return e, g, ed, units, img


@test()
def design_room_map_is_in_versus_list(ctx):
    """Two armies, saved in slot 2: listed (from the editor, then after a
    reboot), played, still there after a Dual Strike session's saves."""
    e, g, ed, units, img = save_design(ctx, "plain", 2, [1, 2])
    rec = img.slot(DESIGN[2])
    ctx.eq(rec[0x4C3], 2, "the saved record's army count")
    ed.end()
    ids = design_tab_ids(e)
    ctx.check(MAP_TAB_DESIGN in ids and ids[MAP_TAB_DESIGN] == [DESIGN_ID[2]], f"the Design Maps tab lists the map ({ids.get(MAP_TAB_DESIGN)})")
    leave_versus(e)
    play(ctx, e, g, 2, units, "from the editor")
    e.close()

    # A reboot from the written save.
    e, g = boot(ctx, img.path)
    saves.to_select_mode(e)
    ids = design_tab_ids(e)
    ctx.check(ids.get(MAP_TAB_DESIGN) == [DESIGN_ID[2]], f"after a reboot: the Design Maps tab lists the map ({ids.get(MAP_TAB_DESIGN)})")
    leave_versus(e)
    play(ctx, e, g, 2, units, "after a reboot")
    e.close()

    if not ctx.ds:
        return
    # A Dual Strike session writes its own slot and the profile: the design stays.
    e, g = boot(ctx, img.path)
    d = dc.DsCampaign(g)
    saves.to_select_mode(e)
    cp.ds_start(e, d, new=True, from_title=False)
    after = saves.flash(e, os.path.join(ctx.out, "ds_session"))
    ctx.check(after.slot(15) is not None, "the DS Campaign was written")
    ctx.eq(after.slot(DESIGN[2]), rec, "the design's slot untouched by the DS session")
    cp.leave_map(e, d, close=True)
    ids = design_tab_ids(e)
    ctx.check(ids.get(MAP_TAB_DESIGN) == [DESIGN_ID[2]], f"after the DS session: the map is listed ({ids.get(MAP_TAB_DESIGN)})")
    leave_versus(e)
    play(ctx, e, g, 2, units, "after the DS session")
    e.close()


@test()
def design_room_black_hole_against_one_army_is_listed(ctx):
    """Orange Star against Black Hole alone: Play OK, army count 2, listed and
    played, with a reboot between."""
    e, g, ed, units, img = save_design(ctx, "bh1", 1, [1, 5])
    rec = img.slot(DESIGN[1])
    ctx.eq(rec[0x4C4], 5, "the five-army mark")
    ctx.eq(rec[0x4C3], 2, "the saved record's army count (Black Hole's HQ counts)")
    e.close()
    e, g = boot(ctx, img.path)
    saves.to_select_mode(e)
    ids = design_tab_ids(e)
    ctx.check(ids.get(MAP_TAB_DESIGN) == [DESIGN_ID[1]], f"the Design Maps tab lists the map ({ids.get(MAP_TAB_DESIGN)})")
    leave_versus(e)
    play(ctx, e, g, 1, units, "Orange Star against Black Hole")
    e.close()


@test()
def design_room_black_hole_with_two_armies_is_listed(ctx):
    """Black Hole beside Orange Star and Blue Moon (the case that always
    worked): army count 3."""
    e, g, ed, units, img = save_design(ctx, "bh2", 3, [1, 2, 5])
    ctx.eq(img.slot(DESIGN[3])[0x4C3], 3, "the saved record's army count")
    e.close()
    e, g = boot(ctx, img.path)
    saves.to_select_mode(e)
    ids = design_tab_ids(e)
    ctx.check(ids.get(MAP_TAB_DESIGN) == [DESIGN_ID[3]], f"the Design Maps tab lists the map ({ids.get(MAP_TAB_DESIGN)})")
    e.close()


@test()
def design_room_an_hq_alone_is_not_an_army(ctx):
    """AW2's rule: an army needs more than its HQ. Black Hole with an HQ
    only, against a full Orange Star: one army, not playable, army count 0,
    not listed (as Blue Moon with an HQ only is not)."""
    for name, armies in (("bh_hq_only", [1, 5]), ("bm_hq_only", [1, 2])):
        # (the second army gets an HQ and nothing else)
        save = os.path.join(ctx.out, f"{name}.sav")
        shutil.copyfile(paths.base_save(), save)
        e, g = boot(ctx, save)
        ed = Editor(e)
        ed.boot()
        w, h = ed.size()
        cells = corners(w, h)
        a, b = armies
        ed.place(HQ, a, *cells[a][0])
        ed.place(CITY, a, *cells[a][1])
        ed.place(PLAIN, None, *cells[a][2])
        ed.place_unit(a, INFANTRY, *cells[a][2])
        ed.place(HQ, b, *cells[b][0])
        ed.save(1)
        img = saves.flash(e, os.path.join(ctx.out, f"{name}_saved"))
        ctx.eq(img.slot(DESIGN[1])[0x4C3], 0, f"{name}: army count 0")
        e.close()
        e, g = boot(ctx, img.path)
        saves.to_select_mode(e)
        ids = design_tab_ids(e)
        ctx.check(MAP_TAB_DESIGN not in ids, f"{name}: not on the list ({ids.get(MAP_TAB_DESIGN)})")
        e.close()


@test()
def design_room_old_black_hole_map_listed_after_a_new_save(ctx):
    """Orange Star against Black Hole as an older version saved it (army
    count 0, so not listed): loaded in the editor and saved again, it is."""
    m = DesignMap(name="old bh map")
    m.terrain(0, 0, "hq", 1).terrain(29, 19, 0x1B4).terrain(2, 0, "city", 1).terrain(27, 19, 0x1B6)
    m.unit(1, "infantry", 1, 1).unit(5, "infantry", 28, 18)
    m.colours = [5, 1, 2, 3, 4]
    rec = bytearray(m.record())
    rec[0x4C3] = 0
    save = os.path.join(ctx.out, "old.sav")
    with open(paths.base_save(), "rb") as f:
        base = f.read()
    with open(save, "wb") as f:
        f.write(write_design_map(base, bytes(rec), 1))
    e, g = boot(ctx, save)
    saves.to_select_mode(e)
    ids = design_tab_ids(e)
    ctx.check(MAP_TAB_DESIGN not in ids, "the old map is not listed")
    e.close()
    e, g = boot(ctx, save)
    ed = Editor(e)
    ed.boot()
    ed.load(1)
    ed.save(1)
    img = saves.flash(e, os.path.join(ctx.out, "resaved"))
    ctx.eq(img.slot(DESIGN[1])[0x4C3], 2, "saved again: army count 2")
    e.close()
    e, g = boot(ctx, img.path)
    saves.to_select_mode(e)
    ids = design_tab_ids(e)
    ctx.check(ids.get(MAP_TAB_DESIGN) == [DESIGN_ID[1]], f"saved again: listed ({ids.get(MAP_TAB_DESIGN)})")
    e.close()
