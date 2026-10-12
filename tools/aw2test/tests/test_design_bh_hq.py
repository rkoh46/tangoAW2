"""Black Hole's HQ is a building of its own (terrain id 0x1B4, class HQ, owner 5): the Design Room's
terrain bar offers it (the HQ entry with the army stepped to Black Hole), it is saved with a
five-army design and loaded back, and in a five-army Versus battle on the design it is Black Hole's
HQ: capturing it defeats Black Hole (its units go, the others play on), exactly as the capture of a
country's HQ does (the control test)."""

import os
import shutil

from aw2test import paths
from aw2test.editor import Editor, HQ, TERRAIN_ARMY
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

PLAIN = 0x01
INFANTRY = 1
BH_HQ_TILE = 0x1B4
BH_HQ_CLASS = HQ | 5 << 5
DESIGN_SLOT_TAG = 5


def boot(ctx, save):
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def corners(w, h):
    return {1: ((0, 0), (1, 1)), 2: ((w - 1, h - 1), (w - 2, h - 2)), 3: ((w - 1, 0), (w - 2, 1)),
            4: ((0, h - 1), (1, h - 2)), 5: ((w // 2, h // 2), (w // 2 + 1, h // 2 + 1))}


@test()
def design_bh_hq_placed_saved_and_captured(ctx):
    run(ctx, 5)


@test()
def design_bh_hq_control_blue_moon(ctx):
    """The same five-army battle with Yellow Comet's HQ captured: what AW2 does for a country's HQ is
    what it does for Black Hole's."""
    run(ctx, 4)


def run(ctx, target):
    save = os.path.join(ctx.out, "bhhq.sav")
    shutil.copyfile(paths.base_save(), save)
    e, g0 = boot(ctx, save)
    ed = Editor(e)
    ed.boot()
    w, h = ed.size()
    cells = corners(w, h)
    cx, cy = cells[5][0]
    units = {}
    for a in range(1, 5):
        ed.place(HQ, a, *cells[a][0])
    # Black Hole's HQ from the bar: the entry shows it, with its own tile.
    ed.to_entry(HQ)
    ed.set_army(5)
    ctx.eq(e.u8(TERRAIN_ARMY), 5, "the bar's army is Black Hole")
    ctx.eq(ed.highlighted(), (BH_HQ_CLASS, BH_HQ_TILE), "the HQ entry for Black Hole: its class and tile")
    ctx.eq(ed.highlighted_shown(), BH_HQ_CLASS, "the HQ entry as the bar shows it")
    ctx.shot(g0, "bar_bh_hq")
    ed.pick()
    ed.stamp(cx, cy)
    ctx.eq(ed.tile(cx, cy), BH_HQ_TILE, "placed: tile 0x1B4")
    ctx.eq(ed.terrain_class(cx, cy), BH_HQ_CLASS, "placed: class HQ of owner 5")
    for a in range(1, 6):
        u = cells[a][1]
        ed.place(PLAIN, None, *u)
        ed.place_unit(a, INFANTRY, *u)
        units[u] = (a, INFANTRY)
    tx, ty = cells[target][0]
    spare = (tx, ty)                       # an Orange Star Infantry standing on the HQ
    ed.place_unit(1, INFANTRY, *spare)
    units[spare] = (1, INFANTRY)
    ed.goto(cx, cy)
    e.wait(20)
    ctx.shot(g0, "editor")
    # Placing a second Black Hole HQ moves the first (one HQ an army).
    ed.place(HQ, 5, cx + 3, cy)
    ctx.eq(ed.tile(cx + 3, cy), BH_HQ_TILE, "a second Black Hole HQ placed")
    ctx.check(ed.tile(cx, cy) != BH_HQ_TILE, "the first Black Hole HQ was removed (one HQ per army)")
    ed.place(HQ, 5, cx, cy)
    ctx.check(ed.tile(cx + 3, cy) != BH_HQ_TILE and ed.tile(cx, cy) == BH_HQ_TILE, "and back")
    ed.save(1)
    sav = e.save(os.path.join(ctx.out, "saved"))
    e.close()

    # Reloaded in a fresh editor.
    e, g1 = boot(ctx, sav)
    ed = Editor(e)
    ed.boot()
    ed.load(1)
    ctx.eq(ed.tile(cx, cy), BH_HQ_TILE, "loaded: tile 0x1B4")
    ctx.eq(ed.terrain_class(cx, cy), BH_HQ_CLASS, "loaded: class HQ of owner 5")
    ed.save(1)
    sav2 = e.save(os.path.join(ctx.out, "saved2"))
    e.close()

    # Played: five armies, the HQ is Black Hole's.
    e, g = boot(ctx, sav2)
    g.setup(None, humans=(1,))
    ctx.eq(g.playst()["map"], 0xB4, "Versus on design 1")
    ctx.eq(g.terrain_class(cx, cy), BH_HQ_CLASS, "the battle's tile: HQ of owner 5")
    ctx.eq({a for a in (u["army"] for u in g.units())}, {1, 2, 3, 4, 5}, "five armies in the battle")
    g.goto(cx, cy)
    e.wait(40)
    ctx.shot(g, "battle_bh_hq")
    g0class = g.terrain_class(tx, ty)
    inf = g.unit_at(*spare)
    ctx.require(inf is not None, "Orange Star's spare Infantry is there")
    # A turn of capture already done (a test aid: the capture points, bits 11..15 of the record's +4 word, are 10).
    at = g.unit_addr(inf["id"]) + 4
    e.w16(at, (e.u16(at) & 0x07FF) | (10 << 11))
    g.select(tx, ty)
    g.goto(tx, ty)
    e.press("A", 6)
    g.wait_menu(g.ACTION_MENU)
    g.choose("Capt", g.ACTION_MENU)
    e.wait(240)
    ctx.shot(g, "captured")
    ctx.eq(g.terrain_class(tx, ty), 0x06 | 1 << 5, "the captured HQ is Orange Star's city now")
    ctx.check(not g.battle_over(), "the battle goes on for the other four armies")
    left = {u["army"] for u in g.units()}
    ctx.check(target not in left, f"Army {target} is defeated: none of its units are left (armies left {sorted(left)})")
    ctx.check({1, 2, 3, 4, 5} - {target} <= left, "the other four armies still have their units")
    ctx.log(f"tile after capture {g.terrain_class(tx, ty):#x}")
    e.close()


@test()
def design_bh_hq_cpu_captures_it(ctx):
    """The computer treats Black Hole's HQ as an HQ: a Blue Moon CPU Infantry beside it captures it (the
    battle goes on for the others, Black Hole's units are gone)."""
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)), spare=False)
    m.terrain(15, 10, 0x1B4)
    m.unit(1, "infantry", 1, 1).unit(3, "infantry", 28, 1).unit(4, "infantry", 1, 18)
    m.unit(2, "infantry", 15, 9)
    m.unit(5, "infantry", 29, 10)
    m.colours = [5, 1, 2, 3, 4]
    g = ctx.start(m, None)
    for day in range(4):
        if g.terrain_class(15, 10) != 0xA8 or g.battle_over():
            break
        g.end_turn(human=1)
    ctx.eq(g.terrain_class(15, 10), 0x06 | 2 << 5, "Black Hole's HQ is Blue Moon's city now (captured by the CPU)")
    ctx.check(not any(u["army"] == 5 for u in g.units()), "Black Hole is defeated")
