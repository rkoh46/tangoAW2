"""The Gauntlet mode (crate::gauntlet, crate::mode_menu; docs/dev/gauntlet-mode.md): a wheel entry directly above Versus, the army screen's free pick of one CO and a colour, one battle against the map's COs in turn,
AW2's results, back to Select Mode; its record in Flash slot 13 after the BH and BH2 records; a run saved halfway and continued. `-k gauntlet_mode`."""

import os
import shutil
import subprocess

from aw2test import bh2campaign as b2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test import gauntlet as ga
from aw2test import paths, saves
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

OBJ_VRAM = 0x06010000
GAUNTLET_SMALL_TILES = (0x2E0, 32)         # crate::mode_menu::EXTRAS: the Gauntlet's small label tiles and OBJ palette
SURVIVAL_SMALL_TILES = (0x320, 32)
GAUNTLET_PALETTE, SURVIVAL_PALETTE = 14, 13
# Battle Maps points (C420 +0x00 spendable, +0x04 the most ever held): every won battle earns them (AW2's campaign, the War Room, Survival, a DS mission, the Gauntlet)
POINTS = (saves.c420(0x00, 4), saves.c420(0x04, 4))
CHOOSER_ENTRIES = 5                        # AW2 CAMPAIGN, DS, BH, BH2 and Silver Nova's: the Gauntlet is not one of them


def png(path_bmp):
    """A BMP picture next to itself as a PNG (for people to look at)."""
    out = path_bmp[:-4] + ".png"
    subprocess.run(["sips", "-s", "format", "png", path_bmp, "--out", out], capture_output=True)
    return out


def boot(ctx, save=None, driver=ga.Gauntlet, env=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, driver(g)


def pic(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    return p + ".bmp"


@test()
def gauntlet_mode_wheel_has_eight_entries_with_the_pack_and_six_without(ctx):
    """The pack's Select Mode wheel turns eight entries and the Gauntlet is directly above Versus (position 4, Versus 3, Campaign 5); without the pack it is AW2's own six."""
    e, g, d = boot(ctx)
    saves.to_select_mode(e)
    seen, pictures = [], {}
    for _ in range(10):
        c = e.u8(saves.SELECT_MODE_CURSOR)
        if c not in seen:
            seen.append(c)
            pictures[c] = pic(ctx, e, f"wheel_{c}")
        e.press("UP", 8)
        e.wait(60)
    if not ctx.ds:
        ctx.eq(sorted(seen), list(range(6)), "six wheel positions without the pack")
        ctx.eq(e.u32(ga.ITEM_TABLE_POOL), ga.GAME_TABLE, "the wheel reads AW2's own item table")
        ctx.eq(ga.wheel_items(e), [2, 4, 3, 1, 0, 5], "AW2's wheel: Battle Maps, Link, Design Room, Versus, Campaign, War Room")
        ctx.eq(e.u8(dc.ACTIVE), 0, "no Gauntlet session")
        # nothing of the Gauntlet's is drawn: its small label's tiles and palette are untouched
        ctx.check(all(b == 0 for b in e.read(OBJ_VRAM + 32 * GAUNTLET_SMALL_TILES[0], 32 * GAUNTLET_SMALL_TILES[1])), "the Gauntlet's OBJ tiles stay empty")
        return
    ctx.eq(sorted(seen), list(range(8)), "eight wheel positions with the pack")
    ctx.eq(e.u32(ga.ITEM_TABLE_POOL), ga.PACK_TABLE, "the wheel reads tangoAW2's eight-item table")
    items = ga.wheel_items(e)
    ctx.eq(items, [2, 4, 3, 1, 9, 0, 5, 8], "positions 0..7: Battle Maps, Online, Design Room, Versus, GAUNTLET, Campaign, War Room, Survival")
    ctx.eq((items[saves.position(e, "versus")], items[saves.position(e, "gauntlet")], items[saves.position(e, "campaign")]), (1, 9, 0), "Gauntlet sits between Versus and Campaign")
    # On the screen the wheel lists positions from the top down, highest first: the picture with Gauntlet in the centre has Campaign above it and Versus below it.
    ctx.log(f"pictures: {[png(p) for p in pictures.values()]}")
    for name in ("gauntlet", "versus", "campaign", "survival"):
        saves.wheel_to(e, name)
        e.wait(30)
        png(pic(ctx, e, f"wheel_at_{name}"))


@test(modes=("ds",))
def gauntlet_mode_wheel_with_the_pack_on_online_play_is_unchanged(ctx):
    """The Gauntlet is an offline entry: its wheel patches are only applied while no netplay mode is on (crate::pvp's `mode.is_none()`), and nothing of the simulation is touched. The wheel's code
    reads a word of the new table only through crate::mode_menu::tick."""
    e, g, d = boot(ctx)
    saves.to_select_mode(e)
    ctx.eq(e.u32(ga.ITEM_TABLE_POOL), ga.PACK_TABLE, "offline: the eight-entry wheel")
    ctx.eq(e.u8(ga.PICKED), 0, "nothing picked")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_pick_reaches_the_army_screen_with_every_co_and_b_goes_back(ctx):
    """GAUNTLET on Select Mode starts at once (no box, no world map) on the map selector; A takes the map and the one army screen follows (no CO screen): UP and DOWN walk every CO the game has (35,
    one pick, no partner) and round again; B on it goes back to the selector, B on the selector back to Select Mode, on GAUNTLET."""
    e, g, d = boot(ctx)
    d.open()
    d.wait_army()
    ctx.check(not d.on_co_select(), "no CO screen: the army screen is the only screen after the selector")
    seen = [e.u8(ga.UI_CO)]
    for _ in range(ga.EVERY_CO - 1):
        e.press("DOWN", 4)
        e.wait(8)
        seen.append(e.u8(ga.UI_CO))
    ctx.eq(len(seen), ga.EVERY_CO, "the pick walks 35 COs")
    ctx.eq(len(set(seen)), len(seen), "each once")
    for must in (ga.ANDY, ga.ARIA, ga.ASUKA, ga.TABITHA, ga.CLONE_ANDY, ga.JAVIER):
        ctx.check(must in seen, f"CO {must} is offered")
    e.press("DOWN", 4)
    e.wait(8)
    ctx.eq(e.u8(ga.UI_CO), seen[0], "DOWN from the last CO comes round to the first")
    e.press("UP", 4)
    e.wait(8)
    ctx.eq(e.u8(ga.UI_CO), seen[-1], "UP from the first goes to the last")
    ctx.eq(d.session()["source"], ga.GAUNTLET, "the Gauntlet's source is the session's")
    ctx.eq(e.u8(dc.MAP_ID), 0xF0, "the campaign engine's map id")
    ctx.check(not d.world_map_up(), "no world map")
    png(pic(ctx, e, "army_screen"))
    e.press("B", 8)
    d.wait_step(ga.SELECTOR)
    ctx.eq(d.step(), ga.SELECTOR, "B on the army screen: back on the map selector")
    png(pic(ctx, e, "selector_again"))
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B on the selector: back on Select Mode, the session over")
    e.wait(60)
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), saves.position(e, "gauntlet"), "the wheel is on GAUNTLET")
    ctx.eq(e.u8(ga.SOURCE), 0, "the Campaign sub-menu's source is back to the DS Campaign")
    png(pic(ctx, e, "back_on_select_mode"))
    e.close()


def pick_battle(ctx, co, label):
    """A fresh console: GAUNTLET, `co` picked, the battle on day 1. Returns (emu, game, driver)."""
    e, g, d = boot(ctx)
    picked = d.start(co)
    ctx.eq(picked, co, f"{label}: the CO screen picked {co}")
    s = d.session()
    ctx.eq((s["active"] != 0, s["source"], s["mission"], s["map_id"]), (True, ga.GAUNTLET, 0, 0xF0), f"{label}: the Gauntlet's first map is on")
    ctx.eq(g.player(1)["co"], co, f"{label}: the player's army has CO {co}")
    ctx.eq(d.controllers(), [1, 2, 0, 0], f"{label}: the player, Drake's army, and the two hidden lines (no turn)")
    ctx.eq((g.player(2)["co"], g.player(3)["co"], g.player(4)["co"]), (9, 18, 14), f"{label}: Drake, Sensei and Hawke are the enemy COs")
    n = d.counts()
    ctx.check(n[1] >= 10 and n[2] >= 10 and n[3] == 0 and n[4] == 0, f"{label}: the player's and Drake's armies are on the field, the later lines are not ({n})")
    ctx.eq([d.owner(ga.CINDER[k]) for k in ("player", "drake", "sensei", "hawke")], [1, 2, 0, 0], f"{label}: only the first two HQs are on the map")
    ctx.check(not d.world_map_up(), f"{label}: no world map")
    return e, g, d


@test(modes=("ds",))
def gauntlet_mode_free_pick_aw2_cos(ctx):
    """Any AW2 CO can be picked, one at a time: Andy, Kanbei and Sami lead the player's army on Cinder Sea."""
    for co in (ga.ANDY, ga.KANBEI, ga.SAMI):
        e, g, d = pick_battle(ctx, co, f"CO {co}")
        png(pic(ctx, e, f"first_turn_co{co}"))
        e.close()


@test(modes=("ds",))
def gauntlet_mode_free_pick_tangoaw2_cos(ctx):
    """tangoAW2's own COs too: Aria (93), Asuka (92), Tabitha (86) and Javier (77) lead the player's army."""
    for co in (ga.ARIA, ga.ASUKA, ga.TABITHA, ga.JAVIER):
        e, g, d = pick_battle(ctx, co, f"CO {co}")
        png(pic(ctx, e, f"first_turn_co{co}"))
        e.close()


def flash_after(ctx, e, name):
    return saves.flash(e, os.path.join(ctx.out, name))


@test(modes=("ds",))
def gauntlet_mode_win_returns_to_select_mode_and_writes_the_record(ctx):
    """The three lines taken (each fall brings the next CO), the last unit destroyed: AW2's VICTORY and results, then Select Mode (no world map, no prologue, no staff roll, no next mission), the wheel on
    GAUNTLET; the best result (CO, days, score) is the mission's record in slot 13 after BH's and BH2's, and the only slot written besides the profile."""
    e, g, d = boot(ctx)
    base = flash_after(ctx, e, "base")
    d.start(ga.ANDY)
    shots = []
    seen = d.play_to_the_last_line(ctx)
    for name, counts, ctrl in seen:
        ctx.log(f"after {name}'s HQ: units {counts}, controllers {ctrl}")
    ctx.eq([s[2] for s in seen], [[1, 2, 2, 0], [1, 2, 2, 2], [1, 2, 2, 2]], "each fall brings the next line (controllers: Sensei's, then Hawke's turn)")
    ctx.check(seen[0][1][3] == 12 and seen[1][1][4] == 12, f"Sensei's wave (12) and Hawke's wave (12) landed ({seen[0][1]}, {seen[1][1]})")
    ctx.eq((seen[2][1][2], seen[2][1][3]), (0, 0), f"Drake's and Sensei's lines were routed by their HQs' capture: none of their units is left when Hawke's HQ falls ({seen[2][1]})")
    worlds = []
    result = None
    tick = 0
    for _ in range(600):
        if d.world_map_up():
            worlds.append(e.frame)
        if d.select_mode_up() and e.u8(dc.ACTIVE) == 0:
            break
        if (d.scripts_running() or not d.in_battle()) and not d.select_mode_up():
            e.press("A", 4)
        e.wait(14)
        if e.u8(dc.LAST_RESULT) and not d.select_mode_up():
            tick += 1
            if tick % 3 == 1 and len(shots) < 12:
                shots.append(png(pic(ctx, e, f"results_{len(shots)}")))
    result = e.u8(dc.LAST_RESULT)
    ctx.eq(result, 1, "the run is won")
    ctx.check(not worlds, "the world map never came up")
    ctx.require(d.select_mode_up(), "back on Select Mode")
    e.wait(90)
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), saves.position(e, "gauntlet"), "the wheel is on GAUNTLET again")
    ctx.eq(e.u8(ga.SOURCE), 0, "the session is over: the source is back to 0")
    png(pic(ctx, e, "select_mode_after_the_win"))
    best = d.best(0)
    ctx.check(best is not None and best[0] == ga.ANDY and best[2] > 0, f"the session's record has the run: (CO, days, score) {best}")
    img = flash_after(ctx, e, "after_win")
    rec = ga.saved_record(img)
    ctx.require(rec is not None, "the Gauntlet's record 'AWGA' is in slot 13 at +0x240")
    ctx.eq(ga.record_best(rec), best, "the saved record is the run's best (CO, days, score)")
    ctx.eq((rec[5], ga.record_results(rec)), (2, [best]), "the record is in the top-five format (version 2) and holds the run alone, under Cinder Sea's id 1")
    saves.expect_slots(ctx, base, img, [13], "a Gauntlet win", profile_allow=list(POINTS) + list(saves.OPTIONS) + [saves.MODE_BYTE])
    ctx.eq(sorted(img.tags()), [0, 13], "only the profile and slot 13 are in the image")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_a_loss_returns_to_select_mode_and_writes_no_record(ctx):
    """The player's army destroyed: DEFEAT, then Select Mode on GAUNTLET; no result is recorded (a loss has no score) and the session is over."""
    e, g, d = boot(ctx)
    d.start(ga.MAX)
    result = d.lose(ctx)
    ctx.eq(result, 2, "the run is lost")
    ctx.require(d.select_mode_up(), "back on Select Mode")
    e.wait(90)
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), saves.position(e, "gauntlet"), "the wheel is on GAUNTLET")
    ctx.eq((e.u8(dc.ACTIVE), e.u8(ga.SOURCE)), (0, 0), "the session is over")
    ctx.eq(d.best(0), None, "no best result")
    png(pic(ctx, e, "select_mode_after_the_loss"))
    img = flash_after(ctx, e, "after_loss")
    rec = ga.saved_record(img)
    ctx.check(rec is None or ga.record_best(rec) is None, "no result in the saved record")
    # retrying is picking GAUNTLET again: the army screen comes up again
    d.open(from_title=False)
    d.wait_army()
    ctx.eq(d.step(), ga.ARMY, "GAUNTLET again: the army screen")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_is_not_in_the_campaign_menu(ctx):
    """The Campaign sub-menu lists AW2 CAMPAIGN, DS, BH, BH2 and Silver Nova's: five entries, no GAUNTLET, and the sources' indices are as before (DS 0, BH 1, ES 2, BH2 3, Gauntlet 4)."""
    e, g, d = boot(ctx)
    d.open_campaign_box()
    e.wait(30)
    ctx.eq(e.u8(dc.MENU_LEVEL), 0, "the chooser")
    seen = []
    for _ in range(8):
        seen.append(e.u8(dc.MENU_CHOICE))
        e.press("DOWN", 6)
        e.wait(14)
    wraps = seen.index(0, 1) if 0 in seen[1:] else None
    ctx.eq(wraps, CHOOSER_ENTRIES, f"the chooser wraps after {CHOOSER_ENTRIES} entries ({seen})")
    # each real entry opens its own source; the Gauntlet's index is never offered
    sources = []
    for row in range(CHOOSER_ENTRIES):
        d.chooser_row(row)
        e.press("A", 8)
        e.wait(30)
        if e.u8(dc.MENU_LEVEL) in (1, 2):
            sources.append(e.u8(ga.SOURCE))
            e.press("B", 8)
            e.wait(30)
        else:
            sources.append(None)
            e.press("A", 8)
            e.wait(20)
    ctx.check(ga.GAUNTLET not in sources, f"no chooser entry is the Gauntlet's source ({sources})")
    png(pic(ctx, e, "chooser"))
    e.close()


def seed_campaigns(ctx):
    """A save with the BH, BH2, Silver Nova and DS campaigns' records (each one New), chained on the pinned base save. Returns its path."""
    path = paths.base_save()
    for name, driver, env, start in (
        ("bh", bh.BhCampaign, {}, lambda d: d.start_bh(new=True, pick=False)),
        ("bh2", b2.Bh2Campaign, b2.ENV, lambda d: d.start_bh2(new=True, pick=False)),
        ("es", es.EsCampaign, es.ENV, lambda d: d.start_es(new=True, pick=False)),
        ("ds", dc.DsCampaign, {}, lambda d: d.start(new=True, pick=False)),
    ):
        e = Emu(save=path, ds=True, env=env)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = driver(g)
        start(d)
        d.wait_world_map()
        img = flash_after(ctx, e, f"seed_{name}")
        e.close()
        path = img.path
    return path


@test(modes=("ds",))
def gauntlet_mode_leaves_the_other_campaigns_saves_byte_identical(ctx):
    """With the DS, BH, BH2 and Silver Nova campaigns each started, a whole Gauntlet run (win) changes slot 13 only in the Gauntlet's region (+0x240..): the BH (0..0x120) and BH2 (0x120..0x240) records,
    Silver Nova's slot 11 and the DS Campaign's slot 15 are byte for byte what they were, and every sector passes AW2's own check."""
    seeded = seed_campaigns(ctx)
    e, g, d = boot(ctx, save=seeded)
    before = flash_after(ctx, e, "before_run")
    tags = sorted(before.tags())
    ctx.check(13 in tags and 11 in tags and 15 in tags, f"the seed has slots 11, 13 and 15 ({tags})")
    s13 = bytes(before.slot(13))
    ctx.eq((s13[:4], s13[0x120:0x124]), (b"AWBC", b"AWB2"), "BH's and BH2's records are in slot 13")
    ctx.check(ga.saved_record(before) is None, "no Gauntlet record yet")
    d.start(ga.ANDY)
    d.win(ctx)
    ctx.require(d.select_mode_up(), "back on Select Mode")
    e.wait(60)
    after = flash_after(ctx, e, "after_run")
    ctx.check(not after.problems(), f"every sector passes AW2's check ({after.problems()})")
    a13 = bytes(after.slot(13))
    ctx.eq(a13[:ga.OFFSET], s13[:ga.OFFSET], "slot 13: the BH and BH2 records are byte for byte as before")
    ctx.eq(a13[ga.OFFSET:ga.OFFSET + 4], b"AWGA", "the Gauntlet's record follows them")
    for slot in (11, 15):
        ctx.eq(bytes(after.slot(slot)), bytes(before.slot(slot)), f"slot {slot} is byte for byte as before")
    ctx.eq(sorted(after.tags()), tags, "no slot appeared or went")
    e.close()
    # and the campaigns still load their records after it
    e, g, d = boot(ctx, save=after.path, driver=bh.BhCampaign)
    d.start_bh(new=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "BH Campaign's Continue still brings its progress")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_save_and_continue(ctx):
    """The map menu's Save writes the run in the shared mid-battle slot 12 (the saved mission's top three bits name the Gauntlet: 4 << 5); GAUNTLET on Select Mode then continues it (no CO screen)
    as saved (the same battle, byte for byte as the harness snapshots it: the first line fallen, the second line's wave on the field); finishing the run drops the save."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    d.capture(ctx, ga.CINDER["drake"])
    d.settle()
    names = saves.suspend(g)
    ctx.check("Save" in names, f"Save is on the map menu ({names})")
    snap = saves.snapshot(g)
    saved = flash_after(ctx, e, "saved")
    mid = saved.slot(ga.MID_SLOT)
    ctx.check(mid is not None, "the run is saved in slot 12")
    e.close()
    e2 = Emu(save=saved.path, ds=True)
    g2 = Game(e2, ctx.image)
    ctx.games.append(g2)
    d2 = ga.Gauntlet(g2)
    d2.open(pick=False, box="continue")
    ctx.require(e2.wait_until(lambda: e2.u32(0x03000000) == 0x08022049, 1800, step=10), "GAUNTLET on Select Mode brings the battle back (no selector, no CO screen)")
    ctx.eq(e2.u8(ga.CONTINUING), 1, "the pick asked to continue")
    g2._units_base = g2._players_base = None
    g2.wait_for_input()
    s = d2.session()
    ctx.eq((s["source"], s["mission"], s["map_id"]), (ga.GAUNTLET, 0, 0xF0), "the Gauntlet's session, its map")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g2), "after a reboot")
    ctx.eq(d2.controllers(), [1, 2, 2, 0], "Sensei's line is on (Drake's fell)")
    png(pic(ctx, e2, "continued"))
    # finishing it (the rest of the lines, the last blow) drops the save
    d2.capture(ctx, ga.CINDER["sensei"])
    d2.settle()
    d2.capture(ctx, ga.CINDER["hawke"])
    ctx.eq(d2.through_results(), 1, "the continued run is won")
    e2.wait(60)
    done = saves.flash(e2, os.path.join(ctx.out, "finished"))
    ctx.check(ga.MID_SLOT not in done.tags(), f"the finished run's save is dropped ({sorted(done.tags())})")
    ctx.check(ga.saved_record(done) is not None, "its record is written")
    e2.close()


def region_pixels(path_bmp, box):
    """The RGB pixels of a BMP's box (x0, y0, x1, y1) as a list."""
    from PIL import Image
    return list(Image.open(path_bmp).convert("RGB").crop(box).getdata())


def hue_share(px, want):
    """The share of the pixels `want(r, g, b)` accepts."""
    return sum(1 for r, g, b in px if want(r, g, b)) / max(1, len(px))


@test(modes=("ds",))
def gauntlet_mode_selector_is_the_war_rooms_own_screen_listing_the_gauntlet_maps(ctx):
    """GAUNTLET opens the game's own map-select screen (the War Room's SELECT MAP: list, map picture, the enemies' faces, the record box on R), not a CO screen. The list holds each Gauntlet
    map (map-table ids ga.list_ids() with their names), the highlighted map's entry holds its enemies in the order they come (the game draws their faces from it) and the record rows hold the best
    result. UP and DOWN move the list's cursor (the mirror of the mission follows it); A takes the map and the army screen follows with the map the session's mission; B goes back to Select Mode."""
    e, g, d = boot(ctx)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    ctx.check(sv.running(e, sv.SELECT_MAP_PROC), "the screen is the game's SELECT MAP proc")
    ctx.eq(e.u8(ga.PLAY_ST + 1), 2, "the game mode is the War Room's while it is up (its list builder lists a tab for Versus and the War Room only)")
    ids, row = d.selector_ids()
    ctx.eq(ids, ga.list_ids(), "the list is the Gauntlet's maps, one entry a row")
    ctx.eq([d.entry_name(i) for i in ids], ga.SELECTOR_TITLES, "the list is ordered by the number of enemy COs, fewest first (ties in the Gauntlet's own order)")
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (0, ga.SELECTOR_ORDER[0]), "the cursor is on the first row: the mission under it is that row's map")
    ctx.eq(d.step(), ga.SELECTOR, "the selector is the first screen")
    first = d.entry_cos(ids[0])
    ctx.eq(first[:4], [0xFF, 73, 12, 0], "Dustwind Basin's two enemies in order (the player picks; Koal, Lash): the faces the screen draws")
    maps, enemies, _ = ga.shown(e)
    ctx.eq((maps, [c for c, _ in enemies]), (len(ga.SELECTOR_ORDER), [73, 12]), "the mirror of the highlighted map: its enemies in order")
    png(pic(ctx, e, "selector"))
    def go(row):
        cur = d.selector_ids()[1]
        for _ in range(abs(row - cur)):
            e.press("DOWN" if row > cur else "UP", 4)
            e.wait(40)
        return d.selector_ids()
    cinder_row, iron_row = ga.row_of(0), ga.row_of(1)
    ids, row = go(cinder_row)
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (cinder_row, 0), "DOWN moves the cursor to mission 0, Cinder Sea (three enemies: after the maps with two)")
    cinder = d.entry_cos(ids[cinder_row])
    ctx.eq(cinder[:4], [0xFF, 9, 18, 14], "Cinder Sea's enemies in order (the player picks; Drake, Sensei, Hawke): the faces the screen draws")
    ctx.eq(ga.shown(e)[1], [(9, ga.GREEN_EARTH), (18, ga.YELLOW_COMET), (14, ga.BLACK_HOLE)], "Cinder Sea's enemies in order, each in the map's fixed colour")
    ids, row = go(iron_row)
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (len(ga.SELECTOR_ORDER) - 1, 1), "the last row is mission 1, Iron Crown (five enemies: the most, so the bottom; the list has scrolled to it)")
    iron = d.entry_cos(ids[iron_row])
    ctx.eq(iron[:4], [0xFF, 5, 17, 6], "Iron Crown's entry names its first three lines in order (the screen draws three faces: the player's slot, then Grit, Jess, Kanbei)")
    ctx.eq(ga.shown(e)[1], [(5, ga.BLUE_MOON), (17, ga.GREEN_EARTH), (6, ga.YELLOW_COMET), (80, ga.ORANGE_STAR), (92, ga.BLACK_HOLE)], "Iron Crown lists all five enemies in order, Asuka of stage two last")
    ctx.eq(ga.shown(e)[2], [ga.EMERALD_SUN], "Iron Crown offers Silver Nova only (every plain colour is an enemy's in some stage)")
    png(pic(ctx, e, "selector_iron_crown"))
    # (the colours each map's pick offers, from the bottom of the list up: Chrome Meridian has the Silver Nova corps on the enemy side, so no skin and neither Black Hole's nor Yellow Comet's (the skin's host) colour;
    # Harvest Run is all of Orange Star and Blue Bastion all of Blue Moon, so never that colour; Last Eclipse wears Black Hole's and Orange Star's; the others as their enemies' colours say)
    P = [ga.ORANGE_STAR, ga.BLUE_MOON, ga.YELLOW_COMET, ga.GREEN_EARTH, ga.BLACK_HOLE]          # (the Teams screen's order)
    offer = {11: [c for c in P if c not in (ga.BLACK_HOLE, ga.ORANGE_STAR)] + [ga.EMERALD_SUN],
             10: [c for c in P if c != ga.BLUE_MOON] + [ga.EMERALD_SUN],
             6: [ga.ORANGE_STAR, ga.BLUE_MOON, ga.GREEN_EARTH],
             5: [ga.BLUE_MOON, ga.YELLOW_COMET, ga.GREEN_EARTH, ga.BLACK_HOLE, ga.EMERALD_SUN],
             9: [c for c in P if c not in (ga.BLUE_MOON, ga.BLACK_HOLE)] + [ga.EMERALD_SUN],
             8: [c for c in P if c not in (ga.GREEN_EARTH, ga.BLUE_MOON)] + [ga.EMERALD_SUN],
             7: [c for c in P if c not in (ga.GREEN_EARTH, ga.BLACK_HOLE)] + [ga.EMERALD_SUN]}
    for mission in (11, 10, 6, 5, 9, 8, 7):
        row = ga.row_of(mission)
        go(row)
        ctx.eq((d.selector_ids()[1], ga.shown(e)[2]), (row, offer[mission]), f"{ga.SELECTOR_TITLES[row]} (row {row}) offers {offer[mission]}")
    go(cinder_row)
    ctx.eq(d.selector_ids()[1], cinder_row, "UP walks back up to Cinder Sea")
    go(0)
    ctx.eq(d.selector_ids()[1], 0, "UP goes back to the first")
    e.press("A", 6)
    d.wait_army()
    ctx.eq(e.u8(ga.UI_MAP), ga.SELECTOR_ORDER[0], "A took the first row's map, Dustwind Basin (mission 2)")
    ctx.eq((d.session()["mission"], d.session()["map_id"]), (ga.SELECTOR_ORDER[0], 0xF0), "the map is the session's mission, the battle's map id the campaign engine's")
    ctx.eq(e.u8(ga.PLAY_ST + 1), 1, "the game mode is the campaign's again")
    ctx.eq(e.u8(ga.UI_STEP), ga.ARMY, "the selector's step is over: the army screen's is up")
    ctx.eq(d.entry_tab(ga.list_ids()[0]), 0x7F, "the Gauntlet's entries are on no list any more")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_a_long_list_borrows_survivals_map_entries_and_gives_them_back(ctx):
    """The list of a full house (the test aid TANGOAW2_GAUNTLET_SLOTS=32 lays the ids out for 32 maps, so today's twelve take ids 0xDC.., Survival's entries): the selector lists every map in order with its own
    name, scrolls to the last row, the record box reads the rows of those ids, and when the selector is left every borrowed entry is Survival's again, byte for byte (crate::survival::restore_entry)."""
    _long_list(ctx)


def _long_list(ctx):
    e, g, d = boot(ctx, env={"TANGOAW2_GAUNTLET_SLOTS": "32"})
    saves.to_select_mode(e)
    borrowed =list(range(ga.SLOT_IDS[-ga.MAX_MAPS], 0xF0))
    entry = lambda i: bytes(e.read(0x08E0_0000 + 0x5C * i, 0x5C))      # (crate::survival::TABLE)
    before = {i: entry(i) for i in borrowed}
    ctx.check(any(before[i][0x14:0x16] != b"\0\0" for i in borrowed), "Survival's entries are in the table before the Gauntlet opens")
    d.open(pick=False, from_title=False)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq(ids, ga.list_ids(32), "the list is the twelve maps on the borrowed ids")
    ctx.check(ids[0] < 0xE0, f"the first map's id is a Survival entry's ({ids[0]:#x})")
    ctx.eq([d.entry_name(i) for i in ids], ga.SELECTOR_TITLES, "every map has its own name, in the order of the enemy counts")
    for _ in range(len(ids) - 1):
        e.press("DOWN", 4)
        e.wait(40)
    ids, row = d.selector_ids()
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (len(ids) - 1, 1), "DOWN scrolls the list to the last map, Iron Crown")
    d.put_results(2, [(ga.MAX, 20, 400)])
    e.wait(10)
    ctx.eq(d.record_rows(32)[-1][0], (ga.MAX, 20 | 400 << 12), "the box's row of the last id holds Iron Crown's best")
    e.press("B", 6)
    e.wait(120)
    after = {i: entry(i) for i in borrowed}
    ctx.eq([hex(i) for i in borrowed if after[i] != before[i]], [], "every borrowed entry is Survival's again")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_selector_shows_the_top_five_in_the_record_box(ctx):
    """The screen's record box (R) reads War Room rows: here each map's five results (CO, days, score; 1st..5th, best first), as the War Room's own box shows its five; a map with none has an empty
    row. The box is drawn by the game (a picture of it is taken; the three looks are in test_gauntlet_pictures)."""
    e, g, d = boot(ctx)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    five = [(ga.ANDY, 12, 345), (ga.MAX, 14, 310), (ga.SAMI, 9, 280), (ga.KANBEI, 20, 250), (ga.JAVIER, 31, 120)]
    d.put_results(1, five)
    e.wait(10)
    rows = d.record_rows()
    cinder, iron = ga.SELECTOR_ORDER.index(0), ga.SELECTOR_ORDER.index(1)       # (the game reads the row of the id it lists a map by: the selector's row)
    ctx.eq(rows[cinder], [(co, days | score << 12) for co, days, score in five], "Cinder Sea's row (the third in the selector) holds the five results, best first")
    ctx.eq(rows[iron], [(0, 0)] * 5, "Iron Crown has no record yet")
    ctx.eq([r for k, r in enumerate(rows[:len(ga.SELECTOR_ORDER)]) if k != cinder], [[(0, 0)] * 5] * (len(ga.SELECTOR_ORDER) - 1), "no other map shows Cinder Sea's results")
    e.press("R", 6)
    e.wait(60)
    png(pic(ctx, e, "selector_records"))
    e.close()


@test(modes=("ds",))
def gauntlet_mode_records_are_kept_by_the_maps_id_not_its_place_in_the_list(ctx):
    """A record region with results under map ids 2 and 1 (Iron Crown's and Cinder Sea's) shows each on its own row whatever order the region lists them; an id no map has is kept untouched."""
    save = ga.with_record(paths.base_save(), os.path.join(ctx.out, "ids.sav"), ga.region_bytes({
        2: [(ga.MAX, 20, 400), (ga.ANDY, 22, 300)], 1: [(ga.SAMI, 9, 280)], 40: [(ga.KANBEI, 5, 500)]}))
    e, g, d = boot(ctx, save=save)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    e.wait(10)
    rows = d.record_rows()
    ctx.eq(rows[ga.row_of(0)][:2], [(ga.SAMI, 9 | 280 << 12), (0, 0)], "Cinder Sea (id 1) shows its own result")
    ctx.eq(rows[ga.row_of(1)][:3], [(ga.MAX, 20 | 400 << 12), (ga.ANDY, 22 | 300 << 12), (0, 0)], "Iron Crown (id 2) shows its two")
    ctx.eq(d.results(40), [(ga.KANBEI, 5, 500)], "the record of an id no map has now is loaded and kept")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_a_094_record_is_converted_to_the_top_five(ctx):
    """0.9.4 kept one best word per list position (Cinder Sea, Iron Crown). Its save loads as each map's first place under the map's id, the region is rewritten in the new format on the next save
    (version 2), and BH's and BH2's regions are as they were."""
    base = paths.base_save()
    old = ga.region_bytes({}, legacy=[(ga.ANDY, 12, 345), (ga.CAULDER, 40, 222)])
    save = ga.with_record(base, os.path.join(ctx.out, "legacy.sav"), old)
    e, g, d = boot(ctx, save=save)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    e.wait(10)
    ctx.eq(d.results(1), [(ga.ANDY, 12, 345)], "Cinder Sea: the old best is first place")
    ctx.eq(d.results(2), [(ga.CAULDER, 40, 222)], "Iron Crown: the old best is first place")
    ctx.eq(d.best(0), (ga.ANDY, 12, 345), "the session's best word is the same")
    rows = d.record_rows()
    cinder, iron = rows[ga.row_of(0)], rows[ga.row_of(1)]
    ctx.eq((cinder[0], cinder[1], iron[0]), ((ga.ANDY, 12 | 345 << 12), (0, 0), (ga.CAULDER, 40 | 222 << 12)), "the box shows them as 1st")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_wins_keep_the_top_five_sorted_like_the_war_room(ctx):
    """Real wins on Cinder Sea (the lines' HQs captured), the record in Flash each time: the first win is first place; a second equal result goes after it (the War Room's tie rule: the same score in
    the same days is placed after the older); a win better than the fifth of a full row pushes it out and takes its place; one worse than all five changes nothing; a loss writes nothing."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    ctx.eq(d.win(ctx), 1, "win 1")
    e.wait(60)
    first = d.results(1)
    ctx.eq(len(first), 1, f"one result after the first win ({first})")
    r1 = first[0]
    img = flash_after(ctx, e, "win1")
    ctx.eq(ga.record_results(ga.saved_record(img)), first, "saved after the first win")
    # a second win with the same play: the same result, after the first
    d.start(ga.ANDY, from_title=False)
    ctx.eq(d.win(ctx), 1, "win 2")
    e.wait(60)
    second = d.results(1)
    ctx.eq(len(second), 2, "two results after the second win")
    ctx.eq(ga.war_room_insert([r1], second[1] if second[0] == r1 else second[0]), second, "sorted as the War Room sorts")
    ctx.check(second[1][2] == r1[2] and second[1][1] == r1[1], f"the same play is the same result ({second})")
    img = flash_after(ctx, e, "win2")
    ctx.eq(ga.record_results(ga.saved_record(img)), second, "saved after the second win")
    e.close()
    s, days = r1[2], r1[1]
    # (a full row whose fifth is a worse result than a win: the win comes in at 5th and pushes the old fifth out)
    worse = s - 10 if s >= 10 else 0
    full = [(ga.MAX, 5, s + 40), (ga.SAMI, 6, s + 30), (ga.KANBEI, 7, s + 20), (ga.JAVIER, 8, s + 10), (ga.CRUMB, 9, worse)]
    save = ga.with_record(img.path, os.path.join(ctx.out, "full.sav"), ga.region_bytes({1: full}))
    e, g, d = boot(ctx, save=save)
    d.start(ga.ANDY)
    ctx.eq(d.win(ctx), 1, "win 3")
    e.wait(60)
    got = d.results(1)
    want = ga.war_room_insert(full, (ga.ANDY, r1[1], r1[2]))
    ctx.eq(got, want, "the win took its place and the old fifth fell off")
    ctx.eq(got[:4], full[:4], "the four better results are as they were")
    ctx.eq(got[4][0], ga.ANDY, "the win is fifth")
    img = flash_after(ctx, e, "win3")
    ctx.eq(ga.record_results(ga.saved_record(img)), want, "saved")
    e.close()
    # (a full row of results that all beat the win: it ranks sixth and nothing changes in the record, the loss writes nothing either)
    better = [(ga.MAX, 5, s + 50), (ga.SAMI, 6, s + 40), (ga.KANBEI, 7, s + 30), (ga.JAVIER, 8, s + 20), (ga.CRUMB, 9, s + 10)]
    save = ga.with_record(img.path, os.path.join(ctx.out, "better.sav"), ga.region_bytes({1: better}))
    e, g, d = boot(ctx, save=save)
    d.start(ga.ANDY)
    ctx.eq(d.win(ctx), 1, "win 4")
    e.wait(60)
    ctx.eq(d.results(1), better, "a sixth place is dropped: the five are as they were")
    d.start(ga.MAX, from_title=False)
    ctx.eq(d.lose(ctx), 2, "a loss")
    e.wait(60)
    ctx.eq(d.results(1), better, "a loss writes nothing")
    img = flash_after(ctx, e, "after_loss")
    ctx.eq(ga.record_results(ga.saved_record(img)), better, "saved: the same five")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_b_on_the_selector_goes_back_to_select_mode_and_a_second_visit_works(ctx):
    """B on the selector leaves the game's screen as the War Room's does (the map id is 0): Select Mode on GAUNTLET, the game mode and the War Room's tab as they were, the Gauntlet's
    entries on no list; GAUNTLET again opens the selector as the first time."""
    e, g, d = boot(ctx)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode, the session over")
    e.wait(60)
    ctx.eq(e.u8(saves.SELECT_MODE_CURSOR), saves.position(e, "gauntlet"), "the wheel is on GAUNTLET")
    ctx.eq(e.u8(ga.UI_STEP), 0, "the selector's step is over")
    ctx.check(e.u8(ga.PLAY_ST + 1) != 2, "the War Room's game mode is not left behind")
    ctx.eq(e.u8(0x0809_0EF2), 7, "the War Room's own tab is back (Survival's and ours are not left on it)")
    ctx.eq(d.entry_tab(ga.list_ids()[0]), 0x7F, "the Gauntlet's entries are on no list")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq((ids, row), (ga.list_ids(), 0), "the second visit lists the maps again")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_army_screen_offers_only_the_colours_the_enemies_do_not_wear(ctx):
    """On the army screen R offers exactly Orange Star, Blue Moon and Silver Nova on Cinder Sea (AW2's five minus the enemies' Green Earth, Yellow Comet and Black Hole, plus the 6th army) and L goes
    back round them; the colour starts on the first, or on the one last worn on the map; a map with one colour free shows it and R changes nothing; the enemies' cards are what the map says."""
    e, g, d = boot(ctx)
    d.open(map=0)
    d.wait_army()
    _, enemies, free = ga.shown(e)
    ctx.eq(free, ga.CINDER_FREE, "Orange Star, Blue Moon, Silver Nova")
    ctx.check(not set(free) & {c for _, c in enemies}, f"no enemy colour is offered ({free} against {enemies})")
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 0, "the cursor starts on the first")
    png(pic(ctx, e, "army_default"))
    seen = []
    for _ in range(4):
        e.press("R", 4)
        e.wait(10)
        seen.append(e.u8(ga.UI_COLOUR_CURSOR))
    ctx.eq(seen, [1, 2, 0, 1], "R walks round the three and wraps")
    e.press("L", 4)
    e.wait(10)
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 0, "L goes back")
    e.press("L", 4)
    e.wait(10)
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 2, "L from the first comes round to the last (Silver Nova)")
    png(pic(ctx, e, "army_silver_nova"))
    e.press("B", 6)
    d.wait_step(ga.SELECTOR)
    ctx.eq(e.u8(ga.UI_STEP), ga.SELECTOR, "B on the army screen: the map selector is back")
    e.close()
    # the colour last worn on a map is where the cursor starts (the harness puts one in the table the screen keeps it in: Cinder Sea, Blue Moon)
    e, g, d = boot(ctx)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    e.w8(ga.UI + 0x40 + 0, ga.BLUE_MOON)
    for _ in range(len(ga.SELECTOR_ORDER) + 2):
        if e.u8(ga.UI_MAP_CURSOR) == 0:
            break
        e.press("DOWN", 4)
        e.wait(40)
    e.press("A", 6)
    d.wait_army()
    ctx.eq(e.u8(ga.UI_MAP), 0, "Cinder Sea was taken")
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 1, "the cursor starts on Blue Moon, the colour last worn on the map")
    e.close()
    # a map with one colour free (Iron Crown: only Silver Nova): shown, and R does nothing
    e, g, d = boot(ctx)
    d.open(map=1)
    d.wait_army()
    ctx.eq(ga.shown(e)[2], [ga.EMERALD_SUN], "Iron Crown offers Silver Nova only")
    e.press("R", 4)
    e.wait(10)
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 0, "R has nothing to change")
    png(pic(ctx, e, "army_iron_crown"))
    e.close()


@test(modes=("ds",))
def gauntlet_mode_the_enemies_on_the_army_screen_cannot_be_edited(ctx):
    """The enemies' cards are the map's: LEFT and RIGHT (the player's card's arrows) walk only the player's CO, never the colour or the enemies shown, and the screen stays up; A then
    starts the battle with the CO and colour of the player's card, the enemies' COs and colours as the map has them."""
    e, g, d = boot(ctx)
    d.open(map=0)
    d.wait_army()
    before = (e.u8(ga.UI_CO), e.u8(ga.UI_CO_CURSOR), e.u8(ga.UI_COLOUR_CURSOR), ga.shown(e))
    for key in ("RIGHT", "LEFT", "RIGHT", "RIGHT", "LEFT"):
        e.press(key, 4)
        e.wait(10)
    after = (e.u8(ga.UI_CO), e.u8(ga.UI_CO_CURSOR), e.u8(ga.UI_COLOUR_CURSOR), ga.shown(e))
    ctx.eq(after[2:], before[2:], "LEFT and RIGHT leave the colour and the enemies")
    ctx.check(after[1] != before[1], f"three RIGHTs and two LEFTs: one CO on ({before[1]} -> {after[1]})")
    ctx.eq(e.u8(ga.UI_STEP), ga.ARMY, "the army screen is still up")
    ctx.eq(before[3][1], [(9, ga.GREEN_EARTH), (18, ga.YELLOW_COMET), (14, ga.BLACK_HOLE)], "the enemies shown are Cinder Sea's, in the order they come")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_the_co_reaches_a_five_army_map(ctx):
    """The army screen's CO leads the player's army on a five-army map too (Iron Crown's four lines are armies 1..4, the player's is the fifth): Aria picked on Iron Crown leads army 5."""
    e, g, d = boot(ctx)
    d.start(ga.ARIA, map=1)
    ctx.eq(g.player(5)["co"], ga.ARIA, "the player's army (the fifth) has the CO picked")
    ctx.eq((g.player(1)["co"], g.player(2)["co"]), (5, 17), "the lines keep their own COs (Grit, Jess)")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_battle_uses_the_picked_army_colour(ctx):
    """The battle's army colour is the pick: Orange Star, Blue Moon, and Silver Nova (the skin sits on the lowest colour no enemy has, Orange Star's; its designs stay the CO's: an Orange Star CO's
    soldiers). The player's colour byte, the skin's host, the enemies' fixed colours and the player's HQ on the map (a picture of it) are checked for each."""
    heads = {}
    for code, label, host, skin in ((ga.ORANGE_STAR, "orange_star", 1, 0), (ga.BLUE_MOON, "blue_moon", 2, 0), (ga.EMERALD_SUN, "emerald_sun", 1, 1)):
        e, g, d = boot(ctx)
        d.start(ga.ANDY, colour=code)
        ctx.eq(g.player(1)["colour"], host, f"{label}: the player's army colour byte")
        ctx.eq([g.player(a)["colour"] for a in (2, 3, 4)], ga.CINDER_ENEMY_COLOURS, f"{label}: the enemies keep Green Earth, Yellow Comet and Black Hole")
        ctx.eq(e.u8(ga.HOSTS), skin * host, f"{label}: the skin sits on colour {host}" if skin else f"{label}: no skin")
        ctx.eq(g.player(1)["co"], ga.ANDY, f"{label}: the CO is the pick")
        g.goto(3, 18)
        e.wait(60)
        p = pic(ctx, e, f"battle_{label}")
        png(p)
        heads[label] = region_pixels(p, (60, 30, 180, 130))
        e.close()
    mean = lambda px: tuple(sum(c[i] for c in px) / len(px) for i in range(3))
    m = {k: mean(v) for k, v in heads.items()}
    ctx.check(len({tuple(round(x / 8) for x in v) for v in m.values()}) == 3, f"the three maps are painted differently ({m})")
    # Orange Star's HQ and units are red, Blue Moon's blue
    red_os = hue_share(heads["orange_star"], lambda r, g_, b: r > 200 and g_ < 110 and b < 90)
    blue_bm = hue_share(heads["blue_moon"], lambda r, g_, b: b > 170 and r < 90 and g_ < 130)
    red_bm = hue_share(heads["blue_moon"], lambda r, g_, b: r > 200 and g_ < 110 and b < 90)
    ctx.check(red_os > 0.01 and red_bm < red_os / 3, f"Orange Star's army is red, Blue Moon's is not ({red_os}, {red_bm})")
    ctx.check(blue_bm > 0.01, f"Blue Moon's army is blue ({blue_bm})")
    red_es = hue_share(heads["emerald_sun"], lambda r, g_, b: r > 200 and g_ < 110 and b < 90)
    ctx.check(red_es < red_os / 3, f"Silver Nova is not Orange Star's red ({red_es} against {red_os})")


@test(modes=("ds",))
def gauntlet_mode_emerald_sun_survives_save_and_continue(ctx):
    """A run saved halfway in Silver Nova continues in it (the pick is kept in the mode's progress record and the skin comes back with the battle)."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY, colour=ga.EMERALD_SUN)
    ctx.eq(e.u8(ga.HOSTS), 1, "Silver Nova is on colour 1")
    saves.suspend(g)
    saved = flash_after(ctx, e, "saved")
    e.close()
    e2 = Emu(save=saved.path, ds=True)
    g2 = Game(e2, ctx.image)
    ctx.games.append(g2)
    d2 = ga.Gauntlet(g2)
    d2.open(pick=False, box="continue")
    ctx.require(e2.wait_until(lambda: e2.u32(0x03000000) == 0x08022049, 1800, step=10), "GAUNTLET continues the run")
    g2._units_base = g2._players_base = None
    g2.wait_for_input()
    e2.wait(30)
    ctx.eq(g2.player(1)["colour"], 1, "the player's colour byte")
    ctx.eq(e2.u8(ga.HOSTS), 1, "Silver Nova is on again")
    png(pic(ctx, e2, "continued_emerald_sun"))
    e2.close()


OAM_SIZES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}


def oam_survey(e, uses):
    """Adds to `uses` every OBJ palette bank (0..15) and tile the visible sprites draw with now: {palette: set(tiles)}."""
    import struct
    oam = e.read(0x07000000, 0x400)
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", oam, 8 * i)
        if (a0 >> 8) & 3 == 2 or (a0 & 0xFF) >= 160 and (a0 & 0xFF) < 240:
            continue
        w, h = OAM_SIZES.get((a0 >> 14, a1 >> 14), (1, 1))
        t, pal = a2 & 0x3FF, a2 >> 12
        uses.setdefault(pal, set()).update(range(t, t + w * h))


def saved_run(ctx, name="saved"):
    """A Gauntlet run saved halfway (the map menu's Save): the Flash image after it."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    saves.suspend(g)
    saved = flash_after(ctx, e, name)
    ctx.check(ga.MID_SLOT in saved.tags(), "the run is saved in slot 12")
    e.close()
    return saved


def boot_select_mode(ctx, path):
    """A console on this Flash image, on Select Mode with the wheel at GAUNTLET."""
    e = Emu(save=path, ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, "gauntlet")
    return e, g, d


def text_of(e, text_id):
    """A text id's string, through the game's text table (0x08610A38)."""
    at = e.u32(0x08610A38 + 4 * text_id)
    out = bytearray()
    while len(out) < 80 and e.u8(at + len(out)):
        out.append(e.u8(at + len(out)))
    return out.decode("latin-1")


@test(modes=("ds",))
def gauntlet_mode_a_saved_run_makes_the_wheel_offer_continue_and_new(ctx):
    """With a run saved halfway, A on GAUNTLET opens AW2's own item box (the one Campaign's wheel entry opens): Continue on the top row, New on the bottom, the help line under it saying what each does
    (Continue the saved run; New drops it). The cursor starts on Continue; B closes the box and leaves the wheel. With no save A starts the mode at once (the selector), no box. Pictures: the box with each
    row under the cursor."""
    saved = saved_run(ctx)
    e, g, d = boot_select_mode(ctx, saved.path)
    e.press("A", 8)
    ctx.require(e.wait_until(d.box_open, 120, step=4), "A on GAUNTLET opens an item box (a run is saved)")
    e.wait(100)
    ctx.eq(d.box_cursor(), 0, "the cursor starts on Continue")
    ctx.eq(d.step(), 0, "the selector has not opened")
    png(pic(ctx, e, "box_continue"))
    e.press("DOWN", 6)
    e.wait(100)
    ctx.eq(d.box_cursor(), 1, "DOWN: New")
    png(pic(ctx, e, "box_new"))
    # the help lines the box shows are the Gauntlet's own
    from_ptr = e.u32(0x080846C0)  # (the options pool word: crate::mode_menu::OPTIONS_POOL)
    ctx.eq(from_ptr, 0x08E40080, "the wheel reads tangoAW2's choice lines")
    lines = [text_of(e, e.u16(0x08E40080 + 2 * (8 + k))) for k in (0, 1)]
    ctx.eq(lines, ["Continue your saved Gauntlet run.", "Start a new run. The saved run is dropped."], "the box's help lines")
    e.press("B", 8)
    e.wait(40)
    ctx.check(not d.box_open(), "B closes the box")
    ctx.check(d.select_mode_up(), "still on Select Mode")
    ctx.eq(ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)], 9, "on GAUNTLET")
    e.close()
    # no save: the Gauntlet answers at once, no box
    e, g, d = boot_select_mode(ctx, paths.base_save())
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "no save: no box, the selector")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_continue_in_the_box_resumes_the_saved_run_byte_for_byte(ctx):
    """Continue in the box (the first row, A): the saved battle comes back with no selector and no army screen, the snapshot of it equal to the one taken when it was saved, and a second reboot from the
    same Flash still offers Continue (the save is not used up by resuming); the run's end drops it."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    d.capture(ctx, ga.CINDER["drake"])
    d.settle()
    saves.suspend(g)
    snap = saves.snapshot(g)
    saved = flash_after(ctx, e, "saved")
    e.close()
    e2, g2, d2 = boot_select_mode(ctx, saved.path)
    e2.press("A", 8)
    d2.choose_in_box("continue")
    ctx.require(e2.wait_until(lambda: e2.u32(0x03000000) == 0x08022049, 1800, step=10), "Continue brings the battle back (no selector, no CO screen)")
    ctx.eq(e2.u8(ga.CONTINUING), 1, "the pick asked to continue")
    g2._units_base = g2._players_base = None
    g2.wait_for_input()
    saves.compare_snapshots(ctx, snap, saves.snapshot(g2), "after Continue in the box")
    ctx.eq(d2.controllers(), [1, 2, 2, 0], "the first line has fallen as saved")
    e2.close()
    e3, g3, d3 = boot_select_mode(ctx, saved.path)
    e3.press("A", 8)
    ctx.check(e3.wait_until(d3.box_open, 120, step=4), "the same Flash offers Continue again: resuming does not use the save up")
    e3.close()


@test(modes=("ds",))
def gauntlet_mode_new_in_the_box_starts_at_the_selector_and_drops_the_save_when_the_run_starts(ctx):
    """New in the box (the second row) goes to the map selector and the army screen as a new run does; backing out (B, B) to Select Mode keeps the save (the box offers Continue again); only the army
    screen's A, the new run's real start, drops it (the game's directory at once): back on Select Mode after that run, GAUNTLET goes to the selector at once."""
    saved = saved_run(ctx)
    e, g, d = boot_select_mode(ctx, saved.path)
    e.press("A", 8)
    d.choose_in_box("new")
    d.wait_step(ga.SELECTOR)
    e.press("A", 6)
    d.wait_army()
    ctx.eq(e.u8(ga.CONTINUING), 0, "a new run was asked for")
    ctx.check(e.u32(0x03000000) != 0x08022049, "no battle was resumed")
    png(pic(ctx, e, "new_run_over_a_save"))
    ctx.check(mid_in_directory(e), "on the army screen the save is still there")
    e.press("B", 8)
    d.wait_step(ga.SELECTOR)
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B, B: back on Select Mode")
    e.wait(60)
    ctx.check(mid_in_directory(e), "backing out kept the save")
    # (AW2's own way back from a mode: the wheel returns with the item box still open on the row last taken, as Campaign's does)
    ctx.check(d.box_open(), "the box offers Continue again, open on the row last taken")
    ctx.eq(d.box_cursor(), 1, "on New")
    png(pic(ctx, e, "box_back_from_the_selector"))
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    e.press("A", 6)
    d.pick_army(ga.ANDY)
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.in_battle(), "the new run's battle loads")
    ctx.check(not mid_in_directory(e), "the army screen's A started the run: the save is dropped from the game's directory")
    e.close()


def mid_in_directory(e):
    """Slot 12 is in the game's save directory (crate::suspend::DIRECTORY, 16 sector slots)."""
    return ga.MID_SLOT in list(e.read(0x0200CC38, 16))


@test(modes=("ds",))
def gauntlet_mode_a_bh_save_in_the_shared_slot_is_neither_offered_nor_dropped(ctx):
    """Slot 12 is shared by the BH Campaigns and the Gauntlet (a saved mission's top bits name its campaign). With a BH mission saved halfway there: GAUNTLET offers no Continue (no box), a new Gauntlet run
    started over it leaves the BH save in the directory, and the Gauntlet's own Save then replaces it (one halfway save at a time, as the BH Campaigns replace each other's): BH CAMPAIGN has no Continue after that."""
    e, g, d = boot(ctx, driver=bh.BhCampaign)
    d.start_bh(new=True, pick=False)
    d.wait_world_map()
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    saves.suspend(g)
    bh_saved = flash_after(ctx, e, "bh_saved")
    ctx.check(ga.MID_SLOT in bh_saved.tags(), "the BH mission is saved in slot 12")
    ctx.eq(bh_saved.slot(ga.MID_SLOT) is not None, True, "slot 12 has its block")
    e.close()
    e, g, d = boot_select_mode(ctx, bh_saved.path)
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ctx.check(not d.box_open(), "a BH save is no Gauntlet save: no Continue, the selector at once")
    e.press("A", 6)
    d.pick_army(ga.ANDY)
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.in_battle(), "the new Gauntlet run's battle loads")
    ctx.check(mid_in_directory(e), "the BH save is still in the directory: a new Gauntlet run does not drop another campaign's save")
    d.leave_setup()
    d.wait_control()
    g._units_base = g._players_base = None
    saves.suspend(g)
    both = flash_after(ctx, e, "gauntlet_over_bh")
    e.close()
    ctx.check(ga.MID_SLOT in both.tags(), "slot 12 holds the Gauntlet's run now")
    e, g, d = boot_select_mode(ctx, both.path)
    e.press("A", 8)
    ctx.check(e.wait_until(d.box_open, 120, step=4), "GAUNTLET offers Continue for it")
    e.close()
    ctx.check(bytes(both.slot(ga.MID_SLOT)) != bytes(bh_saved.slot(ga.MID_SLOT)), "and it is the Gauntlet's block, no longer the BH mission's (one halfway save at a time)")


@test()
def gauntlet_mode_wheel_obj_resources_are_free(ctx):
    """The wheel's two extra entries use OBJ palettes 13 (Survival) and 14 (Gauntlet) and OBJ tiles 0x320..0x33F and 0x2E0..0x2FF (crate::mode_menu::EXTRAS). Every position of the wheel is visited (the
    pad frame by frame while it turns) and each item that has a box (Design Room, Versus, Campaign, War Room: not Battle Maps and Link, which start their mode) is opened. Without the pack, with markers
    written to those tiles, no sprite ever draws with palette 13 or 14 or with those tiles and the markers are never overwritten (the game never writes them); with the pack, the only sprites that draw
    with 13 and 14 are the entries' own (their small label tiles, or the centre tiles on the way to the centre), and the tiles hold exactly their art."""
    e, g, d = boot(ctx)
    saves.to_select_mode(e)
    marker = bytes([0x77]) * 32
    mine = set(range(GAUNTLET_SMALL_TILES[0], GAUNTLET_SMALL_TILES[0] + 32)) | set(range(SURVIVAL_SMALL_TILES[0], SURVIVAL_SMALL_TILES[0] + 32))
    if not ctx.ds:
        for first, n in (GAUNTLET_SMALL_TILES, SURVIVAL_SMALL_TILES):
            e.write(OBJ_VRAM + 32 * first, marker * n)
    uses = {}
    n = 8 if ctx.ds else 6
    for _ in range(n + 1):
        for _ in range(12):
            e.wait(6)
            oam_survey(e, uses)
        if d.box_open():          # (never opened here: a box is opened below)
            e.press("B", 8)
        # an item with a box: A opens it, sampled, B closes it (the box opens at once with AW2's own wheel)
        item = ga.wheel_items(e)[e.u8(saves.SELECT_MODE_CURSOR)]
        if item in (0, 1, 3, 5):
            e.press("A", 8)
            for _ in range(10):
                e.wait(6)
                oam_survey(e, uses)
            ctx.check(d.select_mode_up(), f"item {item}: still on Select Mode with its box open")
            e.press("B", 8)
            e.wait(40)
        e.press("UP", 8)
    ctx.log(f"OBJ palettes seen: { {p: (min(t), max(t)) for p, t in uses.items()} }")
    ctx.require(d.select_mode_up(), "still on Select Mode")
    if not ctx.ds:
        ctx.check(13 not in uses and 14 not in uses, f"no sprite draws with palette 13 or 14 ({sorted(uses)})")
        ctx.check(not any(t in mine for ts in uses.values() for t in ts), "no sprite draws with the entries' small label tiles")
        for first, nn in (GAUNTLET_SMALL_TILES, SURVIVAL_SMALL_TILES):
            ctx.check(e.read(OBJ_VRAM + 32 * first, 32 * nn) == marker * nn, f"tiles {first:#x}..{first + nn - 1:#x}: the game never wrote them")
    else:
        for pal, small in ((GAUNTLET_PALETTE, GAUNTLET_SMALL_TILES), (SURVIVAL_PALETTE, SURVIVAL_SMALL_TILES)):
            tiles = uses.get(pal, set())
            ctx.check(tiles, f"palette {pal} is drawn with (the entry's sprites)")
            ctx.check(all(small[0] <= t < small[0] + small[1] or 0x198 <= t < 0x1D8 for t in tiles), f"palette {pal} draws only the entry's own small label and centre tiles ({sorted(tiles)[:4]}..)")
        for pal in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15):
            ctx.check(not (uses.get(pal, set()) & mine), f"palette {pal}'s sprites never draw the entries' small label tiles")
    e.close()


# --- aids for aw2dev gauntlet ------------------------------------------------------------------------------------
_TOOL_CO = int(os.environ.get("AW2TEST_GAUNTLET_CO", "0") or 0)


@test(name="gauntlet_tool_start", modes=("ds",))
def gauntlet_tool_start(ctx):
    """`aw2dev gauntlet start [--co N]`: from the title to the Gauntlet's first turn with pictures of each screen on the way: the wheel on GAUNTLET, the map selector, the army screen, the Setup phase, day 1
    (AW2TEST_GAUNTLET_CO names the CO, default Andy; AW2TEST_GAUNTLET_OUT where the pictures go)."""
    co = _TOOL_CO or ga.ANDY
    out = os.environ.get("AW2TEST_GAUNTLET_OUT")
    e, g, d = boot(ctx)
    saves.to_select_mode(e)
    saves.wheel_to(e, "gauntlet")
    e.wait(40)
    png(pic(ctx, e, "1_wheel"))
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    png(pic(ctx, e, "2_map_selector"))
    e.press("A", 6)
    d.wait_army()
    png(pic(ctx, e, "3_army_screen"))
    d.pick_co(co)
    e.wait(20)
    png(pic(ctx, e, "4_army_screen_co"))
    picked = d.pick_army(None, None)
    for k in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    for _ in range(100):
        if d.in_setup():
            break
        e.wait(10)
    png(pic(ctx, e, "5_setup"))
    d.leave_setup()
    d.wait_control()
    g._units_base = g._players_base = None
    png(pic(ctx, e, "6_first_turn"))
    ctx.eq(g.player(1)["co"], co, "the pick leads the player's army")
    ctx.log(f"picked {picked}; pictures in {ctx.out}")
    if out:
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(ctx.out)):
            if f[:1].isdigit() and f.endswith(".png"):
                shutil.copy(os.path.join(ctx.out, f), os.path.join(out, f))
    e.close()


@test(modes=("ds",))
def gauntlet_win_gives_the_co_exp(ctx):
    """A Gauntlet win gives the player's CO EXP as a campaign mission does (crate::battle_points: the points x2 for a lone CO, the map's
    best before taken off), so its rank grows and the Set Skills screen shows it; a second win that does not beat the first gives none."""
    from tests.test_co_skills import co_exp
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    before = co_exp(e, ga.ANDY)
    ctx.eq(d.win(ctx), 1, "won")
    e.wait(60)
    won = co_exp(e, ga.ANDY)
    score = d.results(1)[0][2]
    ctx.eq(won - before, 2 * score, f"Andy's EXP: + the score x2 ({before} -> {won}, score {score})")
    d.start(ga.ANDY, from_title=False)
    ctx.eq(d.win(ctx), 1, "won again")
    e.wait(60)
    ctx.eq(co_exp(e, ga.ANDY) - won, 2 * max(0, d.results(1)[0][2] - score), "the same result again: only what beats the best")
