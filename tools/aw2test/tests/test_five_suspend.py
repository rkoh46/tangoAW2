"""A five-army battle saved from the map menu and continued (crate::suspend's five-army record after AW2's block, crate::five::saved_state).

AW2's own block holds four armies read at 64-unit strides, so for a five-army battle it is not the battle: the record that follows it holds the player table (six slots), army
5's picks, the Teams record and every live unit. Versus on a 5P map here; the campaign's five-army missions are in test_bh2_progression.py and test_bh_act5.py."""

import os
import struct

from aw2test import saveimg, saves
from aw2test.harness import test
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.ram import FIVE_ON
from tests.test_five_unit_palettes import five_map, end_turn


def five_snapshot(g):
    """Everything a five-army battle keeps that the player can see: day, army, every army's player block (funds, CO, meters, takeover counts) and every live unit."""
    e = g.e
    players = []
    for a in range(1, 6):
        b = bytearray(g.player(a)["raw"])
        b[0x10] = 0          # AW2's Lab count, recounted on Continue
        players.append(bytes(b))
    units = sorted((u["army"], u["type"], u["x"], u["y"], u["hp"], u["ammo"], u["fuel"], u["flags"]) for u in g.units())
    return {"day": e.u16(saves.DAY), "army": g.current_army(), "five": e.u8(FIVE_ON), "players": players, "units": units}


def compare(ctx, a, b, label):
    for k in ("day", "army", "five"):
        ctx.eq(b[k], a[k], f"{label}: {k}")
    for i in range(5):
        d = [(hex(s), a["players"][i][s:t].hex(), b["players"][i][s:t].hex()) for s, t in saveimg.ranges(a["players"][i], b["players"][i])]
        ctx.check(not d, f"{label}: army {i + 1}'s player block the same {d}")
    missing = [u for u in a["units"] if u not in b["units"]]
    extra = [u for u in b["units"] if u not in a["units"]]
    ctx.check(not missing and not extra, f"{label}: all {len(a['units'])} units the same (lost {missing}, new {extra})")
    for army in range(1, 6):
        ctx.eq(sum(1 for u in b["units"] if u[0] == army), sum(1 for u in a["units"] if u[0] == army), f"{label}: army {army}'s unit count")


def boot(ctx, path):
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


@test(name="five_versus_suspend_and_resume")
def five_versus_suspend_and_resume(ctx):
    """Versus on a 5P map: a Tank moves and the turn passes once (so funds, the day and the units differ from the start), the map menu's Save, a reboot, Continue: every army's units,
    funds, CO and meters come back, the battle is five-army again (nothing left of AW2's four-army reading) and a day is played on."""
    m = five_map(ctx)
    g = ctx.start(m, None, humans=(1,))
    e = g.e
    g.select(2, 5)
    g.move_to(2, 7)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    end_turn(g)
    ctx.check(g.wait_until_turn(1, 30000) if hasattr(g, "wait_until_turn") else True, "back to army 1")
    g.wait_for_input()
    names = saves.suspend(g)
    ctx.check("Save" in names, f"Save is on a five-army battle's map menu ({names})")
    snap = five_snapshot(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved"))
    ctx.check(not saved.problems(), f"every slot AW2 lists passes its check ({saved.problems()})")
    ctx.log(f"slot 4 holds {len(saved.slot(4) or b'')} bytes; sectors listed {saved.problems()}")
    e.close()
    e2, g2 = boot(ctx, saved.path)
    saves.to_select_mode(e2)
    saves.versus_continue(g2)
    ctx.eq(e2.u8(FIVE_ON), 1, "the five-army game is on after Continue")
    compare(ctx, snap, five_snapshot(g2), "after Continue")
    ctx.shot(g2, "resumed")
    g2.end_turn(human=snap["army"])
    ctx.check(not g2.battle_over(), "the resumed battle goes on (a day played)")


# -- M31's gauntlet (the campaign's five-army mission) ---------------------------------------
import importlib.util
from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import harness

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]


def whole_battle(g):
    """The battle byte for byte where it can be compared: the unit table (ids 0..254), the six player slots, every cell's owner, the day and the army."""
    e = g.e
    w, h = e.u16(dc.MAP), e.u16(dc.MAP + 2)
    owners = [bp.owner(e, x, y) for y in range(h) for x in range(w)]
    return {"units": bytes(e.read(g.units_base, 12 * 255)), "players": bytes(e.read(g.players_base, 0x3C * 6)), "owners": owners,
            "day": e.u16(saves.DAY), "army": g.current_army(), "five": e.u8(FIVE_ON),
            "gmap": bytes(e.read(dc.MAP, 0x4300)), "hooks": e.u16(0x08026F5C), "iwram": bytes(e.read(0x03003000, 0x1100))}


def compare_whole(ctx, a, b, label):
    for k in ("day", "army", "five", "owners"):
        ctx.check(a[k] == b[k], f"{label}: {k} the same")
    ctx.log(f"{label}: patches in ROM {a['hooks']:04x} -> {b['hooks']:04x}")
    ctx.log(f"{label}: IWRAM differs at " + ", ".join(f"{0x03003000 + s:#x}: {a['iwram'][s:t].hex()} -> {b['iwram'][s:t].hex()}" for s, t in saveimg.ranges(a["iwram"], b["iwram"])[:60]))
    d = saveimg.ranges(a["gmap"], b["gmap"])
    ctx.log(f"{label}: gMap differs at " + ", ".join(f"{s:#x}..{t:#x}" for s, t in d[:40]))
    for k, size in (("units", 12), ("players", 0x3C)):
        if k == "units":
            # (a dead unit's record keeps whatever bytes it had: the game does not read them)
            def live(t):
                return b"".join(t[i:i + 12] if t[i] else bytes(12) for i in range(0, len(t), 12))
            a, b = dict(a, units=live(a["units"])), dict(b, units=live(b["units"]))
        diff = [i // size for i in range(len(a[k])) if a[k][i] != b[k][i]]
        ctx.check(not diff, f"{label}: the {k} table byte for byte (records differing {sorted(set(diff))[:12]})")
        for r in sorted(set(diff))[:6]:
            ctx.log(f"  {k} record {r}: saved {a[k][r * size:(r + 1) * size].hex()} resumed {b[k][r * size:(r + 1) * size].hex()}")


def m31_continue(ctx, e, path):
    e.close()
    e = Emu(save=path, ds=ctx.ds, env=dict(b2.ENV))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = b2.Bh2Campaign(g)
    d.open_campaign_box()
    d.chooser_row(b2.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(0)
    e.press("A", 8)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=10), "Continue: the battle")
    g._units_base = g._players_base = None
    g.wait_for_input()
    return e, g, d


@test(name="bh2_m31_gauntlet_suspend_and_resume", modes=("ds",))
def bh2_m31_gauntlet_suspend_and_resume(ctx):
    """M31's five-army gauntlet saved after each of the first three takeovers (Nell's HQ, then mid-Olaf, then mid-Eagle after Kanbei's) and continued each time: the unit table, the six player slots (funds, CO,
    meters), every cell's owner and the day come back byte for byte, the game is five-army again, and the mission goes on to the stage switch."""
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    bp.home(g, e)
    e.wait(60)
    sizes = []
    for k, (name, cell, army, nation) in enumerate(bp.HQS):
        try:
            bp.capture(ctx, e, g, d, cell, 5)
        except Exception:
            ctx.shot(g, f"capture_failed{k}")
            raise
        if k == len(bp.HQS) - 1:
            break
        bp.settle(e, g, d)
        if k > 2:
            continue
        before = whole_battle(g)
        saves.suspend(g)
        saved = saves.flash(e, os.path.join(ctx.out, f"saved{k}"))
        ctx.check(not saved.problems(), f"after {name}'s fall: every slot passes its check ({saved.problems()})")
        sizes.append(len(saved.slot(12) or saved.slot(14) or b""))
        e, g, d = m31_continue(ctx, e, saved.path)
        ctx.eq(e.u8(FIVE_ON), 2, f"after {name}'s fall, resumed: the five-army mission is on")
        compare_whole(ctx, before, whole_battle(g), f"after {name}'s fall, resumed")
        ctx.shot(g, f"resumed{k}")
    ctx.log(f"saved record sizes {sizes}")
    bp.wait_stage(ctx, e, g, d, 1)
    ctx.eq(bp.stage_of(e), 1, "Eagle's fall still ends the gauntlet: the battle is on stage 2")
    e.close()


# -- BH Campaign M28 (five armies; the player is army 5) ---------------------------------------
from aw2test import bhact5b as a5
from aw2test import bhcampaign as bh
from tests import test_bh_act5b as t5b_helpers  # noqa: E402  (its MISSIONS/won_mask)


@test(name="bh_m28_suspend_and_resume", modes=("ds",))
def bh_m28_suspend_and_resume(ctx):
    """BH Campaign M28 (Home Is Where The Black Is: five armies, the computer's four turns pass first and the player, army 5, moves last): a unit moves, the map menu's Save, a reboot, Continue: the unit table, the six player
    slots, every cell's owner and the day come back byte for byte, the game is five-army again and the day goes on."""
    n = 28
    title, won, picks, fog, size = t5b_helpers.MISSIONS[n]
    e, g, d = a5.boot(ctx, t5b_helpers.won_mask(n), t5b_helpers.ROSTER_AT[n] | t5b_helpers.BONDS, picks={a5.M[n]: len(picks)}, at=a5.M[n], env={"TANGOAW2_BH_STILL": "1"})
    a5.open_mission(ctx, e, g, d, a5.M[n], picks, "m28")
    stable = 0
    for _ in range(3000):
        stable = stable + 1 if g.current_army() == 5 and not d.scripts_running() else 0
        if stable >= 5:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(e.u8(FIVE_ON) in (1, 2), True, "a five-army game")
    mine = [u for u in g.units(army=5) if u["type"] in (1, 2, 3, 4, 5) and not u["flags"] & 0x08]
    ctx.require(bool(mine), "the player has a ground unit")
    u = mine[0]
    g.select(u["x"], u["y"])
    g.move_to(u["x"], u["y"])
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    before = whole_battle(g)
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved"))
    ctx.check(not saved.problems(), f"every slot passes its check ({saved.problems()})")
    e.close()
    e = Emu(save=saved.path, ds=ctx.ds, env={"TANGOAW2_BH_STILL": "1"})
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.open_campaign_box()
    d.chooser_row(bh.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(0)
    e.press("A", 8)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=10), "Continue: the battle")
    g._units_base = g._players_base = None
    g.wait_for_input()
    compare_whole(ctx, before, whole_battle(g), "M28 resumed")
    ctx.shot(g, "resumed")
    e.close()


@test(name="five_record_never_leaks_into_another_battle")
def five_record_never_leaks_into_another_battle(ctx):
    """A five-army battle's record left in the staging buffer (a normal game's slot is shorter than the record's place, so the buffer keeps what was there) is never applied to another battle: a two-army
    Versus game is saved, the five-army record (taken from a five-army save) is put in the buffer where it would be read, and Continue brings back the two-army game untouched (its hash does not match)."""
    # the five-army save, for its record
    g = ctx.start(five_map(ctx), None, humans=(1,))
    saves.suspend(g)
    five = saves.flash(g.e, os.path.join(ctx.out, "five"))
    rec = bytes(five.slot(4))[0xE28:]
    ctx.check(rec[:4] == b"FIV5", "the five-army save carries a record after AW2's block")
    g.e.close()
    # a normal game saved
    from tests.test_save_integrity import tank_map
    g = ctx.start(tank_map(ctx, 2), None, humans=(1,))
    g.wait_for_input()
    saves.suspend(g)
    snap = saves.snapshot(g)
    normal = saves.flash(g.e, os.path.join(ctx.out, "normal"))
    ctx.eq(len(normal.slot(4)), 0xE28, "the normal game's slot ends where the record would begin")
    g.e.close()
    e2, g2 = boot(ctx, normal.path)
    saves.to_select_mode(e2)
    # (the buffer is poked after the menus have used it, right before Continue's own read)
    saves.wheel_to(e2, saves.VERSUS)
    e2.press("A", 8)
    e2.wait(60)
    saves.box_row(e2, 0)
    e2.write(0x0200_0000 + 0xE28, rec)
    e2.press("A", 8)
    ctx.require(e2.wait_until(lambda: e2.u32(saves.ram.MAIN_CALLBACK) == 0x08022049, 900, step=10), "Continue brought the map back")
    g2._units_base = g2._players_base = None
    g2.wait_for_input()
    ctx.eq(e2.u8(FIVE_ON), 0, "no five-army game came back with the normal one")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g2), "the normal game after Continue")
