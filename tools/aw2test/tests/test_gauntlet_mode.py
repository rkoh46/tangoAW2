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
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

OBJ_VRAM = 0x06010000
GAUNTLET_SMALL_TILES = (0x2E0, 32)         # crate::mode_menu::EXTRAS: the Gauntlet's small label tiles and OBJ palette
SURVIVAL_SMALL_TILES = (0x320, 32)
GAUNTLET_PALETTE, SURVIVAL_PALETTE = 14, 13
# Battle Maps points (C420 +0x00 spendable, +0x04 the most ever held): every won battle earns them (AW2's campaign, the War Room, Survival, a DS mission, the Gauntlet)
POINTS = (saves.c420(0x00, 4), saves.c420(0x04, 4))
CHOOSER_ENTRIES = 5                        # AW2 CAMPAIGN, DS, BH, BH2 and Emerald Sun's: the Gauntlet is not one of them


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
    """GAUNTLET on Select Mode starts at once (no box, no world map): AW2's CO screen with every CO the game has (one pick, no partner); B goes back to Select Mode, on GAUNTLET."""
    e, g, d = boot(ctx)
    d.open()
    d.wait_co_screen()
    c = d.co_cursor()
    ctx.check(c is not None, "the CO screen's cursor is found")
    cos = c["cos"]
    ctx.eq(len(cos), ga.EVERY_CO, "the pick offers all 36 COs")
    ctx.eq(len(set(cos)), len(cos), "each once")
    for must in (ga.ANDY, ga.ARIA, ga.ASUKA, ga.KLAUS, ga.CLONE_ANDY, ga.JAVIER):
        ctx.check(must in cos, f"CO {must} is offered")
    ctx.eq(d.session()["source"], ga.GAUNTLET, "the Gauntlet's source is the session's")
    ctx.eq(e.u8(dc.MAP_ID), 0xF0, "the campaign engine's map id")
    ctx.check(not d.world_map_up(), "no world map")
    png(pic(ctx, e, "co_screen"))
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: d.select_mode_up() and e.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode, the session over")
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
    """tangoAW2's own COs too: Aria (93), Asuka (92), Klaus (86) and Javier (77) lead the player's army."""
    for co in (ga.ARIA, ga.ASUKA, ga.KLAUS, ga.JAVIER):
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
    ctx.check(seen[2][1][2] > 0 or seen[2][1][3] > 0, f"Drake's and Sensei's survivors are still on the field when Hawke's HQ falls ({seen[2][1]}): the win does not need them hunted")
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
    """The Campaign sub-menu lists AW2 CAMPAIGN, DS, BH, BH2 and Emerald Sun's: five entries, no GAUNTLET, and the sources' indices are as before (DS 0, BH 1, ES 2, BH2 3, Gauntlet 4)."""
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
    """A save with the BH, BH2, Emerald Sun and DS campaigns' records (each one New), chained on the pinned base save. Returns its path."""
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
    """With the DS, BH, BH2 and Emerald Sun campaigns each started, a whole Gauntlet run (win) changes slot 13 only in the Gauntlet's region (+0x240..): the BH (0..0x120) and BH2 (0x120..0x240) records,
    Emerald Sun's slot 11 and the DS Campaign's slot 15 are byte for byte what they were, and every sector passes AW2's own check."""
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
    d2.open()
    ctx.require(e2.wait_until(lambda: e2.u32(0x03000000) == 0x08022049, 1800, step=10), "GAUNTLET on Select Mode brings the battle back (no CO screen)")
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
    d2.wait_co_screen()
    ctx.eq(e2.u8(ga.CONTINUING), 0, "a new run was asked for")
    ctx.check(e2.u32(0x03000000) != 0x08022049, "no battle was resumed: the CO screen is up")
    png(pic(ctx, e2, "new_run_over_a_save"))
    # (the drop is in the game's directory now and reaches Flash with its next write, as every campaign's New over a save does)
    e2.press("B", 8)
    ctx.require(e2.wait_until(lambda: d2.select_mode_up() and e2.u8(dc.ACTIVE) == 0, 900, step=10), "B: back on Select Mode")
    e2.wait(60)
    e2.press("A", 8)
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
    d.wait_co_screen()
    png(pic(ctx, e, "2_co_screen"))
    picked = d.choose_cos(1, prefs=[co])
    for k in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    for _ in range(100):
        if d.in_setup():
            break
        e.wait(10)
    png(pic(ctx, e, "3_setup"))
    d.leave_setup()
    d.wait_control()
    g._units_base = g._players_base = None
    png(pic(ctx, e, "4_first_turn"))
    ctx.eq(g.player(1)["co"], co, "the pick leads the player's army")
    ctx.log(f"picked {picked}; pictures in {ctx.out}")
    if out:
        os.makedirs(out, exist_ok=True)
        for f in sorted(os.listdir(ctx.out)):
            if f[:1].isdigit() and f.endswith(".png"):
                shutil.copy(os.path.join(ctx.out, f), os.path.join(out, f))
    e.close()
