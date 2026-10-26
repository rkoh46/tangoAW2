"""Every CO is on every screen where the player picks one freely: Versus' Teams
screen, the War Room's CO screen, Survival's and Champion's (the same screen),
and the tag partner pick (the Teams list). With the Dual Strike pack that is
AW2's 19 (Sturm included) and the 16 new ones (crate::co_new: Dual Strike's nine,
Clone Andy, Crumb, Asuka, the Emerald Sun four), 35; without it AW2's 19. The War Room's records (the best
five of a map, each with its CO's id) are saved and loaded back for a new CO."""

import os

from aw2test import paths, saves, warroom as wr
from aw2test import rom as romlib
from aw2test import saveimg
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

AW2 = list(range(19))
NEW = list(range(72, 83)) + [86, 87, 88, 89, 92]      # (92: Asuka; 86..89 the Emerald Sun four; Varro, 90, is on no list)


def boot(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def check_lists(ctx, e, what):
    groups = wr.lists(e)
    flat = [c for g in groups for c in g]
    ctx.log(f"{what}: {[wr.names(g) for g in groups]}")
    want = AW2 + (NEW if ctx.ds else [])
    ctx.eq(sorted(flat), sorted(want), f"{what}: every CO once ({len(want)})")
    ctx.eq(len(groups), 5, f"{what}: Orange Star, Blue Moon, Green Earth, Yellow Comet, Black Hole")
    ctx.check(10 in flat, f"{what}: Sturm")
    if ctx.ds:
        # each new CO in its country's group, after the CO it takes after (the Teams list's rule)
        at = {c: (k, g.index(c)) for k, g in enumerate(groups) for c in g}
        for co, _, like in co_new_all():
            ctx.eq(at[co][0], at[like][0], f"{what}: {romlib.co_name(co)} in {romlib.co_name(like)}'s group")
            ctx.check(at[co][1] > at[like][1], f"{what}: {romlib.co_name(co)} after {romlib.co_name(like)}")


def co_new_all():
    # (CO id, Dual Strike id, the CO it takes after): crate::co_new::NEW, then Crumb
    like = [11, 13, 12, 10, 18, 17, 16, 15, 15, 13, 13]
    return [(72 + k, 0, like[k]) for k in range(11)] + [(92, 0, 14)]


@test()
def war_room_offers_every_co(ctx):
    """The War Room's CO screen: AW2's 19 without the pack, 31 with it (the
    Teams list's COs), each reachable with the pad."""
    e, g = boot(ctx)
    wr.open_war_room(e)
    check_lists(ctx, e, "War Room")
    e.shot(os.path.join(ctx.out, "war_room_first"))
    for co in ([10] + NEW if ctx.ds else [10]):
        wr.go_to(e, co)
        ctx.eq(wr.highlighted(e)[1], co, f"{romlib.co_name(co)} reachable")
    if ctx.ds:
        # the same COs as Versus' Teams screen offers
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
        t = ctx.boot_teams(m)
        ctx.eq(sorted(t.teams()["co_list"]), sorted(wr.flat(e)), "the Teams list's COs")


@test(modes=("ds",))
def survival_offers_every_co(ctx):
    """Survival's CO screen (the War Room's) offers the same 31, on a basic
    course and on a Champion course (open once a basic course has a record,
    here a Money record by Asuka: a new CO's id is in the record's seven bits and
    its face is drawn on SELECT MAP)."""
    e, g = boot(ctx)
    wr.open_survival(e)
    check_lists(ctx, e, "Survival")
    wr.go_to(e, 82)
    wr.go_to(e, 92)
    wr.go_to(e, 75)
    e.shot(os.path.join(ctx.out, "survival_vonbolt"))
    e.close()
    e, g = boot(ctx)
    recs = {sv.MONEY: (92, 60000), sv.TURN: (10, 20), sv.TIME: (75, 20000)}
    ctx.require(sv.open_survival(e, lambda e: sv.set_records(e, recs)), "Survival's SELECT MAP")
    ctx.eq({k: v[1] for k, v in sv.records(e).items()}, {k: v[0] for k, v in recs.items()}, "the records' COs")
    e.press("R", 8)
    e.wait(20)
    shot = sv.bg0(e)
    e.shot(os.path.join(ctx.out, "survival_records_new_cos"))
    for row, (k, name) in enumerate([(sv.MONEY, "Asuka"), (sv.TURN, "Sturm"), (sv.TIME, "Von Bolt")]):
        ctx.check(sv.text_on(shot, name, 138, 70 + 12 * row), f"{sv.NAMES[k]}'s record names its CO, {name}")
    e.press("B", 8)
    e.wait(30)
    for _ in range(3):
        e.press("DOWN", 8)
        e.wait(30)
    e.wait(60)
    e.press("A", 8)
    ctx.require(e.wait_until(lambda: wr.proc(e) is not None, 900, step=10), "the Champion course's CO screen")
    e.wait(60)
    check_lists(ctx, e, "Champion")
    e.shot(os.path.join(ctx.out, "champion_co_screen"))


def play_and_save(ctx, co, label, save=None):
    """War Room, the first map with `co` (on `save`, a game a past session left),
    won; the records in RAM and in the Flash the game saved; then the save
    booted again: the same records, and the War Room's SELECT MAP drawing them.
    Returns (the saved file, the map's id, the map's record row)."""
    wr.set_ds(ctx.ds)
    e, g = boot(ctx, save)
    before = None
    wr.open_war_room(e)
    before = wr.rows(e)
    wr.go_to(e, co)
    wr.start_battle(e, g)
    ctx.eq(g.player(1)["co"], co, f"{label}: army 1 plays {romlib.co_name(co)}")
    wr.win_map(e, g)
    got = wr.rows(e)
    changed = [k for k in got if got[k] != before.get(k)]
    ctx.eq(len(changed), 1, f"{label}: one map's record changed")
    map_id = changed[0]
    ctx.eq({k: v for k, v in got.items() if k != map_id}, {k: v for k, v in before.items() if k != map_id}, f"{label}: the other maps' records are as they were")
    row = got[map_id]
    cos = [r[0] for r in wr.record_row(e, map_id) if r[1]]
    ctx.check(co in cos, f"{label}: {romlib.co_name(co)}'s id is among the record's COs {cos}")
    mine = next(r for r in wr.record_row(e, map_id) if r[0] == co and r[1])
    ctx.check(mine[1] > 0, f"{label}: the record has a score ({mine[1]})")
    path = os.path.join(ctx.out, f"after_{label}")
    img = saves.flash(e, path)
    ctx.eq(img.problems(), [], f"{label}: the Flash image is one AW2 accepts")
    if ctx.ds:
        # (the pack's rows are at the end of slot 15: tests/test_save_integrity_modes.py)
        from tests.test_save_integrity_modes import ds_war_room_row
        ctx.eq(ds_war_room_row(img, map_id), row, f"{label}: the DS record in Flash holds the row")
    else:
        prof = img.slot(0)
        at = 0x48 + wr.ROW * (map_id - 0x6C)
        ctx.eq(prof[at:at + wr.ROW], row, f"{label}: the profile in Flash holds the row")
        ctx.eq(prof[0x48:0x2A0], e.read(wr.RECORDS, 30 * wr.ROW), f"{label}: all 30 maps' records in Flash are the game's")
    e.shot(os.path.join(ctx.out, f"{label}_select_map"))
    e.close()
    # again from the saved game
    e2, g2 = boot(ctx, save=path + ".sav")
    saves.to_select_mode(e2)
    if not ctx.ds:
        ctx.eq(wr.rows(e2), got, f"{label}: booted from the save, the same records")
    saves.wheel_to(e2, saves.WAR_ROOM)
    e2.press("A", 8)
    e2.wait(60)
    saves.box_row(e2, 1)
    e2.press("A", 8)
    ctx.require(e2.wait_until(lambda: sv.running(e2, sv.SELECT_MAP_PROC), 600, step=10), f"{label}: SELECT MAP after the reload")
    e2.wait(120)
    if ctx.ds:
        ctx.eq(wr.rows(e2), got, f"{label}: booted from the save, the same records")
    e2.shot(os.path.join(ctx.out, f"{label}_select_map_reloaded"))
    e2.press("R", 8)
    e2.wait(90)
    e2.shot(os.path.join(ctx.out, f"{label}_record_reloaded"))
    e2.close()
    return path + ".sav", map_id, row


@test()
def war_room_record_with_new_cos(ctx):
    """A War Room map won with a new CO writes its record (the CO's id in the
    row's first byte, a score), the game saves it, and a console booted from
    that save has it again; the other maps' rows stay empty. Without the pack
    Sturm, who the War Room already offered, is the check. (Dual Strike's COs
    play a battle with their own numbers: tests/test_new_cos.py.)"""
    for co in ([72, 75, 81, 82, 92] if ctx.ds else [10]):
        play_and_save(ctx, co, romlib.co_name(co).lower().replace(" ", "_"))


@test()
def war_room_new_record_joins_an_old_save(ctx):
    """A save with a War Room record by an AW2 CO (Andy) loads as it was; the
    same map won with another CO (Crumb with the pack, Sturm without) adds its
    record beside it, and the first one is unchanged."""
    other = 82 if ctx.ds else 10
    wr.set_ds(ctx.ds)
    path, map_id, first = play_and_save(ctx, 1, "andy")
    e, g = boot(ctx, path)
    wr.open_war_room(e)
    ctx.eq(wr.rows(e), {map_id: first}, "Andy's record, loaded unchanged")
    wr.go_to(e, other)
    wr.start_battle(e, g)
    wr.win_map(e, g)
    row = wr.rows(e)[map_id]
    recs = [r for r in wr.record_row(e, map_id) if r[1]]
    ctx.eq(sorted(r[0] for r in recs), sorted([1, other]), f"two records, Andy's and {romlib.co_name(other)}'s")
    old = bytes(first[:4])
    ctx.check(any(row[k:k + 4] == old for k in range(0, 20, 4)), "Andy's record bytes are as they were")
    img = saves.flash(e, os.path.join(ctx.out, "after_two"))
    ctx.eq(img.problems(), [], "the Flash image is one AW2 accepts")
    if ctx.ds:
        from tests.test_save_integrity_modes import ds_war_room_row
        ctx.eq(ds_war_room_row(img, map_id), row, "the DS record in Flash holds both records")
    else:
        at = 0x48 + wr.ROW * (map_id - 0x6C)
        ctx.eq(img.slot(0)[at:at + wr.ROW], row, "the profile in Flash holds both records")


@test(modes=("ds",))
def war_room_suspend_with_a_new_co(ctx):
    """A War Room map played by Crumb, saved halfway from its map menu,
    rebooted and continued: the same battle, Crumb still army 1's CO."""
    e, g = boot(ctx)
    wr.open_war_room(e)
    wr.go_to(e, 82)
    wr.start_battle(e, g)
    saves.suspend(g)
    snap = saves.snapshot(g)
    img = saves.flash(e, os.path.join(ctx.out, "suspended"))
    ctx.eq(img.problems(), [], "the Flash image is one AW2 accepts")
    ctx.check(img.slot(3) is not None, "the War Room's suspend slot is written")
    e.close()
    e, g = boot(ctx, img.path)
    saves.to_select_mode(e)
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 0)
    e.press("A", 8)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 900, step=10), "Continue brings the map back")
    g._units_base = g._players_base = None
    g.wait_for_input()
    ctx.eq(g.player(1)["co"], 82, "Crumb leads army 1 again")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g), "after a reboot, the War Room's Continue")
