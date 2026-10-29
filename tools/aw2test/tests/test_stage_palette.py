"""A stage switch keeps the dialogue window's colours (crate::stage::arrive writes the stage armies' colours and COs into their records: colour 0 drew the windows in garbage, a pink striped band):
M31's switch to the Last Citadel; the narration box (`m31b_scene.bmp`) and Aria's portrait box at the win (`aria_box.bmp`) draw in the window's colours (BG 8). Logs which banks changed."""

import importlib.util
import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import harness
from aw2test.harness import test

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers5", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]

PAL = 0x0500_0000


def banks(e):
    raw = e.read(PAL, 0x400)
    return [raw[32 * k:32 * k + 32] for k in range(32)]


@test(name="stage_switch_keeps_the_window_colours", modes=("ds",))
def stage_switch_keeps_the_window_colours(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    bp.to_player_turn(e, g, d)
    d.wait_control()
    before = banks(e)
    for k, (name, cell, army, nation) in enumerate(bp.HQS):
        bp.capture(ctx, e, g, d, cell, 5)
        if k < len(bp.HQS) - 1:
            bp.settle(e, g, d)
    bp.wait_stage(ctx, e, g, d, 1)
    for _ in range(400):
        if d.text_shown():
            break
        e.wait(10)
    e.wait(90)
    after = banks(e)
    a2.pic(ctx, e, "m31b_scene")
    ctx.log("BG banks changed: " + str([k for k in range(16) if before[k] != after[k]]))
    ctx.log("OBJ banks changed: " + str([k - 16 for k in range(16, 32) if before[k] != after[k]]))
    ctx.check(after[8] == before[8], "the window's bank (BG 8, drawn in the player's colour) is as before the switch")
    ctx.check(after[13] != before[13], "army 2's unit bank (BG 13) is the stage's own: Aria's Orange Star, not Olaf's Blue Moon")
    for k in range(32):
        ctx.log(f"bank {k:2d} before {before[k].hex()}")
        ctx.log(f"bank {k:2d} after  {after[k].hex()}")
    e.close()



def box_banks(e):
    """The palette banks the tiles of the screen's top 6 rows use, per BG (BGxCNT: screen base; text mode, 32-wide entries)."""
    out = {}
    disp = e.u16(0x0400_0000)
    for bg in range(4):
        if not disp & (0x100 << bg):
            continue
        cnt = e.u16(0x0400_0008 + 2 * bg)
        base = 0x0600_0000 + ((cnt >> 8) & 0x1F) * 0x800
        sx = e.u16(0x0400_0010 + 4 * bg) // 8
        sy = e.u16(0x0400_0012 + 4 * bg) // 8
        used = set()
        for ty in range(6):
            for tx in range(30):
                x, y = (tx + sx) % 32, (ty + sy) % 32
                ent = e.u16(base + 2 * (y * 32 + x))
                if ent & 0x3FF:
                    used.add(ent >> 12)
        out[bg] = sorted(used)
    return out


@test(name="stage_switch_portrait_box_colours", modes=("ds",))
def stage_switch_portrait_box_colours(ctx):
    """The banks M31's boxes use: a portrait box on stage 1 (the opening), the narration box and a portrait box (Aria's last scene) on the Citadel."""
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    for _ in range(600):
        if d.text_shown():
            break
        e.press("A", 4)
        e.wait(10)
    e.wait(60)
    ctx.log(f"stage 1 box banks {box_banks(e)}")
    before_hex = e.read(0x0300_21C0, 32).hex()
    a2.intro(ctx, e, d, "m31", (0,))
    bp.to_player_turn(e, g, d)
    d.wait_control()
    for k, (name, cell, army, nation) in enumerate(bp.HQS):
        prev = e.read(0x0300_21C0, 32)
        bp.capture(ctx, e, g, d, cell, 5)
        for f in range(3000):
            e.wait(1)
            now = e.read(0x0300_21C0, 32)
            if now != prev:
                ctx.log(f"{name} frame {f}: bank 8 -> {now.hex()} procs {[(hex(a), hex(fn)) for a, _, fn in g.procs()]}")
                prev = now
            if d.text_shown() and f > 100:
                ctx.log(f"{name}: box at frame {f}, bank 8 {now.hex()}")
                break
        if k < len(bp.HQS) - 1:
            bp.settle(e, g, d)
    bp.wait_stage(ctx, e, g, d, 1)
    for _ in range(400):
        if d.text_shown():
            break
        e.wait(10)
    e.wait(60)
    ctx.log(f"stage 2 narration box banks {box_banks(e)}")
    bp.settle(e, g, d)
    d.wait_control()
    prev = e.read(0x0300_21C0, 32)
    ctx.log(f"bank 8 before Aria's capture {prev.hex()}")
    def b8(tag):
        g._units_base = g._players_base = None
        ctx.log(f"raw1 {e.read(g.players_base + 0x3C, 0x3C).hex()} raw2 {e.read(g.players_base + 0x78, 0x3C).hex()}")
        ctx.log(f"step {tag}: players {g.players_base:#x} bank 8 {e.read(0x0300_21C0, 32).hex()[:16]} army {g.current_army()} colour {e.u8(g.players_base + 0x3C * g.current_army() + 0x1A)} colours {[e.u8(g.players_base + 0x3C * a + 0x1A) for a in range(1, 6)]}")
    g._units_base = g._players_base = None
    inf = next(u for u in g.units(army=1) if u["type"] == 1 and not u["flags"] & 0x08)
    occ = g.unit_at(33, 5)
    if occ is not None:
        d.remove_unit(occ)
    d.place_unit(inf, 33, 5)
    a_ = g.unit_addr(inf["id"])
    e.w8(a_ + 5, (e.u8(a_ + 5) & 7) | (19 << 3))
    e.wait(4)
    b8("placed")
    g.select(33, 5)
    e.wait(8)
    b8("selected")
    d.dialogue()
    menu = g.move_to(33, 5)
    b8("menu")
    d.dialogue()
    g.choose("Capt", g.ACTION_MENU)
    b8("chosen")
    e.wait(120)
    b8("after 120")
    allp = e.read(0x0300_20C0, 0x400)
    for f in range(6000):
        e.wait(1)
        now_all = e.read(0x0300_20C0, 0x400)
        if now_all != allp:
            ch = [k for k in range(32) if now_all[32 * k:32 * k + 32] != allp[32 * k:32 * k + 32]]
            ctx.log(f"stage 2 frame {f}: banks changed {ch} (16+ OBJ)")
            allp = now_all
        now = e.read(0x0300_21C0, 32)
        if now != prev:
            ctx.log(f"frame {f}: bank 8 -> {now.hex()} procs {[(hex(a), hex(fn)) for a, _, fn in g.procs()]}")
            prev = now
        if d.text_shown() and f > 100:
            break
    e.wait(60)
    ctx.log(f"stage 2 portrait box banks {box_banks(e)}")
    ctx.eq(e.read(0x0300_21C0, 32).hex(), before_hex, "Aria's portrait box at the win draws in the window's colours (BG 8)")
    pink = banks(e)[8][2:20]
    for lo, n in ((0x0200_0000, 0x40000), (0x0300_0000, 0x8000)):
        mem = e.read(lo, n)
        i = mem.find(pink)
        while i >= 0:
            ctx.log(f"bank 8's colours also at {lo + i - 2:#x}")
            i = mem.find(pink, i + 1)
    for k, b in enumerate(banks(e)):
        ctx.log(f"bank {k:2d} at the box {b.hex()}")
    for bg in range(4):
        cnt = e.u16(0x0400_0008 + 2 * bg)
        base = 0x0600_0000 + ((cnt >> 8) & 0x1F) * 0x800
        sx, sy = e.u16(0x0400_0010 + 4 * bg) // 8, e.u16(0x0400_0012 + 4 * bg) // 8
        hist = {}
        for ty in range(6):
            for tx in range(30):
                ent = e.u16(base + 2 * (((ty + sy) % 32) * 32 + (tx + sx) % 32))
                hist[(ent >> 12, ent & 0x3FF)] = hist.get((ent >> 12, ent & 0x3FF), 0) + 1
        ctx.log(f"BG{bg} cnt {cnt:#x} prio {cnt & 3} entries (bank, tile): {sorted(hist.items(), key=lambda kv: -kv[1])[:8]}")
    a2.pic(ctx, e, "aria_box")
    e.close()



@test(name="hq_capture_win_box_colours_m30", modes=("ds",))
def hq_capture_win_box_colours_m30(ctx):
    """An ordinary two-army mission won by its HQ's capture (M30, Rachel's HQ (39,13)): the victory scene's first box and its window bank (BG 8) against the battle's."""
    e, g, d = b2.enter(ctx, 30)
    d.leave_setup()
    a2.intro(ctx, e, d, "m30", (0,))
    bp.to_player_turn(e, g, d, army=1) if hasattr(bp, "to_player_turn") and False else None
    d.wait_control()
    g._units_base = g._players_base = None
    before = e.read(0x0300_21C0, 32)
    ctx.log(f"m30 players {g.players_base:#x} colours {[e.u8(g.players_base + 0x3C * a + 0x1A) for a in range(1, 6)]} raw1 {e.read(g.players_base + 0x3C, 0x3C).hex()}")
    bp.capture(ctx, e, g, d, (39, 13), 1)
    prev = before
    allp = e.read(0x0300_20C0, 0x400)
    for f in range(3000):
        e.wait(1)
        now_all = e.read(0x0300_20C0, 0x400)
        if now_all != allp:
            ch = [k for k in range(32) if now_all[32 * k:32 * k + 32] != allp[32 * k:32 * k + 32]]
            ctx.log(f"frame {f}: banks changed {ch} (16+ OBJ)")
            allp = now_all
        now = e.read(0x0300_21C0, 32)
        if now != prev:
            ctx.log(f"frame {f}: bank 8 -> {now.hex()[:24]} procs {[(hex(a), hex(fn)) for a, _, fn in g.procs()]}")
            prev = now
        if d.text_shown() and f > 100:
            break
    e.wait(60)
    after = e.read(0x0300_21C0, 32)
    a2.pic(ctx, e, "m30_win_box")
    ctx.log(f"bank 8 battle {before.hex()} at the win box {after.hex()}")
    ctx.check(after == before, "the victory box draws in the window's colours")
    e.close()
