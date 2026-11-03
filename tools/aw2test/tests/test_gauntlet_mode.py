"""The Gauntlet mode (crate::gauntlet, crate::mode_menu; docs/dev/gauntlet-mode.md): a wheel entry directly above Versus, a free pick of one CO, one battle against the map's COs in turn,
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
def gauntlet_mode_pick_reaches_the_co_pick_with_every_co_and_b_goes_back(ctx):
    """GAUNTLET on Select Mode starts at once (no box, no world map) on the map selector; A takes the map and AW2's CO screen follows with every CO the game has (one pick, no partner);
    B on it goes back to the selector, B on the selector back to Select Mode, on GAUNTLET."""
    e, g, d = boot(ctx)
    d.open()
    d.wait_co_screen()
    c = d.co_cursor()
    ctx.check(c is not None, "the CO screen's cursor is found")
    cos = c["cos"]
    ctx.eq(len(cos), ga.EVERY_CO, "the pick offers all 35 COs")
    ctx.eq(len(set(cos)), len(cos), "each once")
    for must in (ga.ANDY, ga.ARIA, ga.ASUKA, ga.TABITHA, ga.CLONE_ANDY, ga.JAVIER):
        ctx.check(must in cos, f"CO {must} is offered")
    ctx.eq(d.session()["source"], ga.GAUNTLET, "the Gauntlet's source is the session's")
    ctx.eq(e.u8(dc.MAP_ID), 0xF0, "the campaign engine's map id")
    ctx.check(not d.world_map_up(), "no world map")
    png(pic(ctx, e, "co_screen"))
    e.press("B", 8)
    d.wait_step(ga.SELECTOR)
    ctx.eq(e.u8(ga.UI_MAP), 0, "B on the CO screen: back on the map selector")
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
    # retrying is picking GAUNTLET again: the CO screen comes up again
    d.open(from_title=False)
    d.wait_co_screen()
    ctx.check(d.co_cursor() is not None, "GAUNTLET again: the CO screen")
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
    d2.open(pick=False)
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
    """GAUNTLET opens the game's own map-select screen (the War Room's SELECT MAP: list, map picture, the enemies' faces, the record box on R), not the CO screen. The list holds each Gauntlet
    map (map-table ids 0xF6.. with their names), the highlighted map's entry holds its enemies in the order they come (the game draws their faces from it) and the record rows hold the best
    result. UP and DOWN move the list's cursor (the mirror of the mission follows it); A takes the map and the CO screen follows with the map the session's mission; B goes back to Select Mode."""
    e, g, d = boot(ctx)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    ctx.check(sv.running(e, sv.SELECT_MAP_PROC), "the screen is the game's SELECT MAP proc")
    ctx.eq(e.u8(ga.PLAY_ST + 1), 2, "the game mode is the War Room's while it is up (its list builder lists a tab for Versus and the War Room only)")
    ids, row = d.selector_ids()
    ctx.eq(ids, [ga.FIRST_ID, ga.FIRST_ID + 1], "the list is the Gauntlet's two maps, in the order of the Gauntlet's missions")
    ctx.eq(d.entry_name(ids[0]), "Cinder Sea", "the first entry is named Cinder Sea")
    ctx.eq(d.entry_name(ids[1]), "Iron Crown", "the second entry is named Iron Crown")
    ctx.check(not d.on_co_screen(), "no CO screen yet: the selector is the first screen")
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (0, 0), "the cursor is on the first row")
    cinder = d.entry_cos(ids[0])
    ctx.eq(cinder[:4], [0xFF, 9, 18, 14], "Cinder Sea's enemies in order (the player picks; Drake, Sensei, Hawke): the faces the screen draws")
    maps, enemies, _ = ga.shown(e)
    ctx.eq((maps, enemies), (2, [(9, ga.GREEN_EARTH), (18, ga.YELLOW_COMET), (14, ga.BLACK_HOLE)]), "the mirror of the highlighted map: its enemies in order, each in the map's fixed colour")
    png(pic(ctx, e, "selector"))
    e.press("DOWN", 4)
    e.wait(40)
    ids, row = d.selector_ids()
    ctx.eq((row, e.u8(ga.UI_MAP_CURSOR)), (1, 1), "DOWN moves to the second map")
    iron = d.entry_cos(ids[1])
    ctx.eq(iron[:4], [0xFF, 5, 17, 6], "Iron Crown's entry names its first three lines in order (the screen draws three faces: the player's slot, then Grit, Jess, Kanbei)")
    ctx.eq(ga.shown(e)[1], [(5, ga.BLUE_MOON), (17, ga.GREEN_EARTH), (6, ga.YELLOW_COMET), (80, ga.ORANGE_STAR), (92, ga.BLACK_HOLE)], "Iron Crown lists all five enemies in order, Asuka of stage two last")
    ctx.eq(ga.shown(e)[2], [ga.EMERALD_SUN], "Iron Crown offers Silver Nova only (every plain colour is an enemy's in some stage)")
    iron_pic = pic(ctx, e, "selector_iron_crown")
    png(iron_pic)
    # (Iron Crown is bigger than the picture area: its picture is the middle part, and the list panel's lower right, below the two names, is as empty as with Cinder Sea's)
    box = (50, 80, 100, 135)
    ctx.eq(region_pixels(iron_pic, box), region_pixels(os.path.join(ctx.out, "selector.bmp"), box), "the big map's picture stays off the list panel (the panel's pixels match the other map's)")
    e.press("UP", 4)
    e.wait(40)
    ctx.eq(d.selector_ids()[1], 0, "UP goes back to the first")
    e.press("A", 6)
    d.wait_co_screen()
    ctx.eq(e.u8(ga.UI_MAP), 0, "A took Cinder Sea")
    ctx.eq((d.session()["mission"], d.session()["map_id"]), (0, 0xF0), "the map is the session's mission, the battle's map id the campaign engine's")
    ctx.eq(e.u8(ga.PLAY_ST + 1), 1, "the game mode is the campaign's again")
    ctx.eq(e.u8(ga.UI_STEP), 0, "the selector's step is over")
    ctx.eq(d.entry_tab(ga.FIRST_ID), 0x7F, "the Gauntlet's entries are on no list any more")
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
    ctx.eq(rows[0], [(co, days | score << 12) for co, days, score in five], "Cinder Sea's row holds the five results, best first")
    ctx.eq(rows[1], [(0, 0)] * 5, "Iron Crown has no record yet")
    e.press("R", 6)
    e.wait(60)
    png(pic(ctx, e, "selector_records"))
    e.close()


@test(modes=("ds",))
def gauntlet_mode_records_are_kept_by_the_maps_id_not_its_place_in_the_list(ctx):
    """A record region with results under map ids 2 and 1 (Iron Crown's and Cinder Sea's) shows each on its own row whatever order the region lists them; an id no map has is kept untouched."""
    save = ga.with_record(paths.base_save(), os.path.join(ctx.out, "ids.sav"), ga.region_bytes({
        2: [(ga.MAX, 20, 400), (ga.ANDY, 22, 300)], 1: [(ga.SAMI, 9, 280)], 9: [(ga.KANBEI, 5, 500)]}))
    e, g, d = boot(ctx, save=save)
    d.open(pick=False)
    d.wait_step(ga.SELECTOR)
    e.wait(10)
    rows = d.record_rows()
    ctx.eq(rows[0][:2], [(ga.SAMI, 9 | 280 << 12), (0, 0)], "Cinder Sea (id 1) shows its own result")
    ctx.eq(rows[1][:3], [(ga.MAX, 20 | 400 << 12), (ga.ANDY, 22 | 300 << 12), (0, 0)], "Iron Crown (id 2) shows its two")
    ctx.eq(d.results(9), [(ga.KANBEI, 5, 500)], "the record of an id no map has now is loaded and kept")
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
    ctx.eq((rows[0][0], rows[0][1], rows[1][0]), ((ga.ANDY, 12 | 345 << 12), (0, 0), (ga.CAULDER, 40 | 222 << 12)), "the box shows them as 1st")
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
    ctx.eq(d.entry_tab(ga.FIRST_ID), 0x7F, "the Gauntlet's entries are on no list")
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    ids, row = d.selector_ids()
    ctx.eq((ids, row), ([ga.FIRST_ID, ga.FIRST_ID + 1], 0), "the second visit lists the maps again")
    e.close()


@test(modes=("ds",))
def gauntlet_mode_colour_pick_offers_only_the_colours_the_enemies_do_not_wear(ctx):
    """After the CO pick the colour pick offers exactly Orange Star, Blue Moon and Silver Nova on Cinder Sea (AW2's five minus the enemies' Green Earth, Yellow Comet and Black Hole, plus the 6th
    army); LEFT and RIGHT move round them; B goes back to the CO screen."""
    e, g, d = boot(ctx)
    d.open()
    d.wait_co_screen()
    d.choose_cos(1, prefs=[ga.ANDY])
    d.wait_step(ga.COLOURS)
    _, enemies, free = ga.shown(e)
    ctx.eq(free, ga.CINDER_FREE, "Orange Star, Blue Moon, Silver Nova")
    ctx.check(not set(free) & {c for _, c in enemies}, f"no enemy colour is offered ({free} against {enemies})")
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 0, "the cursor starts on the first")
    png(pic(ctx, e, "colour_pick_1"))
    seen = []
    for _ in range(4):
        e.press("RIGHT", 4)
        e.wait(10)
        seen.append(e.u8(ga.UI_COLOUR_CURSOR))
    ctx.eq(seen, [1, 2, 0, 1], "RIGHT walks round the three and wraps")
    e.press("LEFT", 4)
    e.wait(10)
    ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), 0, "LEFT goes back")
    e.press("LEFT", 4)
    e.wait(10)
    png(pic(ctx, e, "colour_pick_emerald_sun"))
    e.press("B", 6)
    d.wait_co_screen()
    ctx.eq(e.u8(ga.UI_STEP), 0, "B on the colour pick: the CO screen is back")
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
    d2.open(pick=False)
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


@test(modes=("ds",))
def gauntlet_mode_select_with_a_starts_a_new_run_over_a_saved_one(ctx):
    """With a run saved halfway, GAUNTLET continues it; SELECT held with A starts a new run instead (the CO screen) and drops the save (from the game's directory at once, from Flash with the next write)."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    saves.suspend(g)
    saved = flash_after(ctx, e, "saved")
    ctx.check(ga.MID_SLOT in saved.tags(), "the run is saved in slot 12")
    e.close()
    e2 = Emu(save=saved.path, ds=True)
    g2 = Game(e2, ctx.image)
    ctx.games.append(g2)
    d2 = ga.Gauntlet(g2)
    saves.to_select_mode(e2)
    saves.wheel_to(e2, "gauntlet")
    e2.press("A+SELECT", 8)
    d2.wait_step(ga.SELECTOR)
    e2.press("A", 6)
    d2.wait_co_screen()
    ctx.eq(e2.u8(ga.CONTINUING), 0, "a new run was asked for")
    ctx.check(e2.u32(0x03000000) != 0x08022049, "no battle was resumed: the selector and the CO screen come up")
    png(pic(ctx, e2, "new_run_over_a_save"))
    # (the drop is in the game's directory now and reaches Flash with its next write, as every campaign's New over a save does)
    e2.press("B", 8)
    d2.wait_step(ga.SELECTOR)
    e2.press("B", 8)
    ctx.require(e2.wait_until(lambda: d2.select_mode_up() and e2.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e2.wait(60)
    e2.press("A", 8)
    d2.wait_step(ga.SELECTOR)
    e2.press("A", 6)
    d2.wait_co_screen()
    ctx.eq(e2.u8(ga.CONTINUING), 0, "the save is gone: GAUNTLET alone starts a new run now")
    e2.close()


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
    """`aw2dev gauntlet start [--co N]`: from the title to the Gauntlet's first turn with pictures of each screen on the way: the wheel on GAUNTLET, the CO pick, the Setup phase, day 1
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
    d.wait_co_screen()
    png(pic(ctx, e, "3_co_screen"))
    picked = d.choose_cos(1, prefs=[co])
    d.wait_step(ga.COLOURS)
    png(pic(ctx, e, "4_colour_pick"))
    d.pick_colour(None)
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
