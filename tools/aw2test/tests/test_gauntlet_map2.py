"""The Gauntlet's second map (crate::gauntlet_mode: Iron Crown, then Asuka's Keep; docs/dev/gauntlet.md): a five-army land gauntlet (the player, Silver Nova, is the fifth army) whose four lines
(Grit, Jess, Kanbei, Rachel) each come when the line before falls, then the stage switch to Asuka's Keep, where taking her HQ wins. `-k gauntlet_map2`. Map 2 is started from
the selector's second entry."""

import os
import subprocess

from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import paths, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

FIVE_ON = 0x0203_0206
WAVES = {2: 14, 3: 15, 4: 16}         # the wave lists of crate::gauntlet_mode (JESS_WAVE, KANBEI_WAVE, RACHEL_WAVE)
CHEST = {2: (20000, 1000), 3: (20000, 1500), 4: (25000, 2000)}
CARRY_CAP = 40000


def png(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


def start(ctx, co=ga.ANDY, save=None, env=None):
    """The Gauntlet's map 2 started from Select Mode: (emu, game, driver) with the player in control on day 1."""
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(co, map=ga.MAP2)
    to_player_turn(e, g, d)
    return e, g, d


def to_player_turn(e, g, d, frames=24000, army=5):
    """The fifth army moves last: A through the scripts until it is the player's turn with nothing running (Grit's turn goes by)."""
    for _ in range(frames // 20):
        if d.scripts_running():
            e.press("A", 4)
        elif g.current_army() == army and d.in_battle():
            e.wait(30)
            if g.current_army() == army and not d.scripts_running():
                break
        e.wait(16)
    d.wait_control()
    g._units_base = g._players_base = None


def funds(g, army):
    return g.player(army)["funds"] if "funds" in g.player(army) else int.from_bytes(g.player(army)["raw"][0:4], "little")


def stage(e):
    return e.u8(ga.STAGE_AT)


def wait_stage(ctx, e, g, d, k, frames=4000):
    """Through the scenes and the swap's fades until the battle is on stage k and the cursor answers."""
    for _ in range(frames // 20):
        if stage(e) != k and d.scripts_running():
            e.press("A", 4)
        e.wait(15)
        if stage(e) == k and e.u8(ga.STAGE_AT + 1) == 0 and d.in_battle():
            break
    g._units_base = g._players_base = None


def to_stage_two(ctx, co=ga.ANDY, pics=None):
    """Map 2 played through its four captures to the stage switch: (emu, game, driver) on stage two, its opening scene still to read."""
    e, g, d = start(ctx, co)
    for key, army, who, nxt in ga.IRON_ORDER:
        d.capture(ctx, ga.IRON[key], army=5)
        if nxt:
            d.settle()
    wait_stage(ctx, e, g, d, 1)
    return e, g, d


@test(name="gauntlet_map2_each_fall_reveals_the_next_line", modes=("ds",))
def gauntlet_map2_each_fall_reveals_the_next_line(ctx):
    """Iron Crown: Jess, Kanbei and Rachel are off the battlefield (no units, no funds, no turn) at the start; each fall (Grit's HQ, Jess's, Kanbei's) brings the next line with its whole wave and its
    war chest and its HQ, and the line that fell stays on the map; Rachel's fall moves the battle to stage two."""
    e, g, d = start(ctx)
    ctx.eq(e.u8(FIVE_ON), 2, "a five-army mission")
    ctx.check(len(g.units(army=1)) >= 20, f"Grit is on the field ({len(g.units(army=1))} units)")
    for a in (2, 3, 4):
        ctx.eq(len(g.units(army=a)), 0, f"army {a} is not on the battlefield at the start")
        ctx.eq(funds(g, a), 0, f"army {a} has no funds at the start")
    ctx.eq([d.owner(ga.IRON[k]) for k in ("grit", "jess", "kanbei", "rachel")], [1, 0, 0, 0], "only Grit's HQ is on the map")
    day = e.u16(saves.DAY)
    for key, army, who, nxt in ga.IRON_ORDER[:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
        base, rate = CHEST[nxt]
        nxt_key, _, nxt_who, _ = ga.IRON_ORDER[nxt - 1]
        ctx.eq(d.owner(ga.IRON[key]), 5, f"{who}'s HQ is the player's")
        ctx.check(len(g.units(army=nxt)) >= WAVES[nxt] - 1, f"{nxt_who}'s wave is on the field ({len(g.units(army=nxt))} of {WAVES[nxt]})")
        ctx.eq(d.owner(ga.IRON[nxt_key]), nxt, f"{nxt_who}'s HQ is built")
        ctx.check(funds(g, nxt) >= base, f"{nxt_who}'s war chest is paid ({funds(g, nxt)} >= {base})")
        ctx.eq(len(g.units(army=army)), 0, f"{who}'s line is routed by the capture (no survivors stay)")
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    ctx.eq(stage(e), 1, "Rachel's fall moves the battle to stage two")
    e.close()


@test(name="gauntlet_map2_stage_two_carries_the_survivors_and_asuka_wins", modes=("ds",))
def gauntlet_map2_stage_two_carries_the_survivors_and_asuka_wins(ctx):
    """The switch: the player's survivors land on Asuka's Keep, funds capped, the Silver Nova skin sits on Orange Star's colour and Asuka is Black Hole's; taking her HQ wins."""
    e, g, d = start(ctx)
    for key, army, who, nxt in ga.IRON_ORDER[:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
    mine = sorted((u["type"], u["hp"]) for u in g.units(army=5))
    p = g.player(5)["raw"]
    skin_before = e.u8(ga.SKIN_STATE)
    colour_before = e.u8(g.players_base + 0x3C * 5 + 0x1A)
    ctx.eq((skin_before, colour_before), (5, 5), "stage one: the Silver Nova skin sits on the fifth army's colour (Black Hole's)")
    # (a unit that moved this turn is greyed: it must be fresh on the new stage's first turn)
    tank = next(u for u in g.units(army=5) if u["type"] == 5 and not u["flags"] & 0x08)
    g.select(tank["x"], tank["y"])
    g.move_to(tank["x"], tank["y"])
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    ctx.check(any(u["flags"] & 1 for u in g.units(army=5)), "a unit has waited before the switch")
    e.w32(g.players_base + 0x3C * 5, 200000)       # (a player who hoarded: the cap applies)
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.check(not any(u["flags"] & 1 for u in g.units(army=1)), "no survivor arrives greyed out (every unit can act on stage two's first turn)")
    ctx.eq(e.u8(FIVE_ON), 0, "stage two is a two-army game")
    ctx.eq((e.u16(dc.MAP), e.u16(dc.MAP + 2)), (30, 22), "Asuka's Keep is 30 x 22")
    after = sorted((u["type"], u["hp"]) for u in g.units(army=1))
    ctx.check(len(after) >= 0.8 * len(mine), f"the survivors came along ({len(after)} of {len(mine)})")
    ctx.eq(funds(g, 1), CARRY_CAP, "a player who hoarded 200,000 brings the cap")
    asuka = g.units(army=2)
    ctx.check(len(asuka) >= 25, f"Asuka's fresh army is on the keep ({len(asuka)})")
    ctx.eq(funds(g, 2) >= 60000, True, "Asuka holds her fortress with funds")
    cols = [e.u8(g.players_base + 0x3C * a + 0x1A) for a in (1, 2)]
    ctx.eq(cols, [1, 5], "the player is Orange Star's colour (with the Silver Nova skin), Asuka Black Hole's")
    ctx.eq(e.u8(ga.SKIN_STATE), 1, "the Silver Nova skin moved to the player's new colour")
    png(ctx, e, "keep_first_turn")
    ctx.eq(d.owner(ga.KEEP_ASUKA), 2, "Asuka's HQ is on the map")
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    ctx.eq(d.through_results(), 1, "taking Asuka's HQ wins the gauntlet")
    e.close()


@test(name="gauntlet_map2_suspend_and_resume", modes=("ds",))
def gauntlet_map2_suspend_and_resume(ctx):
    """Saved after Grit's fall (Jess's line on the field) and continued from Select Mode: byte for byte as saved, five-army again, the saved map (Iron Crown, not the selector's first) with its rules:
    the next fall still reveals the next line."""
    from tests.test_five_suspend import whole_battle, compare_whole
    e, g, d = start(ctx)
    d.capture(ctx, ga.IRON["grit"], army=5)
    d.settle()
    before = whole_battle(g)
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved1"))
    ctx.check(not saved.problems(), f"every slot passes its check ({saved.problems()})")
    e.close()
    e, g, d = resume(ctx, saved.path)
    ctx.eq(d.session()["mission"], ga.MAP2, "the run continues on the map it was saved on")
    ctx.eq(e.u8(FIVE_ON), 2, "resumed: the five-army mission is on")
    compare_whole(ctx, before, whole_battle(g), "after Grit's fall, resumed")
    for key, army, who, nxt in ga.IRON_ORDER[1:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
        ctx.check(len(g.units(army=nxt)) >= WAVES[nxt] - 1, f"{who}'s fall still brings the next line after a resume ({len(g.units(army=nxt))} units)")
    # the switch after a resume: the player keeps control of the new stage's turn (it once ended by itself ~700 frames in: the resume's mission reset wiped the engine's latches)
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    to_player_turn(e, g, d, army=1)
    ctx.eq(stage(e), 1, "the resumed run reached Asuka's Keep")
    ctx.eq([e.u8(g.players_base + 0x3C * a + 0x1B) for a in (1, 2)], [1, 2], "the player is human, Asuka the computer's")
    seen = set()
    for _ in range(30):
        e.wait(100)
        seen.add((g.current_army(), d.scripts_running() and 0))
    ctx.eq({a for a, _ in seen}, {1}, "3000 frames later it is still the player's turn (nothing ended it)")
    ctx.eq(len(g.units(army=1)) >= 30, True, "the survivors are on the keep")
    e.close()


@test(name="gauntlet_map2_stage_two_suspend_and_resume", modes=("ds",))
def gauntlet_map2_stage_two_suspend_and_resume(ctx):
    """Saved on Asuka's Keep (map menu > Save) and continued from Select Mode: the stage number, the two-army game, the survivors, Asuka's army and the skin's colour come back byte for byte, and
    taking her HQ still wins."""
    from tests.test_five_suspend import whole_battle, compare_whole
    e, g, d = to_stage_two(ctx)
    to_player_turn(e, g, d, army=1)
    before = whole_battle(g)
    ctx.eq(stage(e), 1, "on stage two")
    # (the map menu is opened on an empty cell: the nearest ones to the landing, not the first in the fogged plateau)
    cells = g.empty_cells
    g.empty_cells = lambda: sorted(cells(), key=lambda c: abs(c[0] - 3) + abs(c[1] - 18))
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved2"))
    ctx.check(not saved.problems(), f"stage two: every slot passes its check ({saved.problems()})")
    e.close()
    e, g, d = resume(ctx, saved.path)
    ctx.eq(stage(e), 1, "resumed on stage two")
    after = whole_battle(g)
    # (the player table of a two-army game is the neutral record and armies 1..4: records 0..2 are state (funds, COs, power meters, controllers) and compared byte for byte; the absent armies 3 and 4 are
    # zero but for the byte AW2's resume marks them with (+0x2D = 0x80, a derived property-count byte); "record 5" is whatever RAM follows the table, not a record)
    keep = lambda b: dict(b, players=b["players"][:0x3C * 3])
    compare_whole(ctx, keep(before), keep(after), "on Asuka's Keep, resumed")
    for a in (3, 4):
        was, now = bytearray(before["players"][0x3C * a:0x3C * a + 0x3C]), bytearray(after["players"][0x3C * a:0x3C * a + 0x3C])
        ctx.check(not any(was) and not any(now[:0x2D]) and not any(now[0x2E:]), f"army {a} is absent before and after the resume (only the derived byte +0x2D differs: {was[0x2D]:#x} -> {now[0x2D]:#x})")
    ctx.eq(e.u8(ga.SKIN_STATE), 1, "the skin is on the player's colour after the resume")
    ctx.eq([e.u8(g.players_base + 0x3C * a + 0x1A) for a in (1, 2)], [1, 5], "the colours: the player's Orange Star with the skin, Asuka's Black Hole")
    ctx.eq(d.owner(ga.KEEP_ASUKA), 2, "Asuka's HQ is on the resumed map")
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    ctx.eq(d.through_results(), 1, "the resumed stage is won: Asuka's HQ ends the battle with VICTORY")
    e.wait(60)
    done = saves.flash(e, os.path.join(ctx.out, "finished"))
    rec = ga.saved_record(done)
    ctx.check(rec is not None and ga.record_best(rec, ga.MAP2) is not None, "the win wrote the map's record")
    e.close()


def resume(ctx, path):
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open(pick=False)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1800, step=10), "GAUNTLET on Select Mode brings the battle back")
    g._units_base = g._players_base = None
    g.wait_for_input()
    return e, g, d


@test(name="gauntlet_map2_lines_fit_their_boxes", modes=("ds",))
def gauntlet_map2_lines_fit_their_boxes(ctx):
    """Every line of Iron Crown and Asuka's Keep is one box (two lines of 176 px: tools/bh2text/lint.py's `px`), and the COs who never use contractions do not."""
    import re
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bh2text"))
    import lint
    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "src", "gauntlet_mode.rs")).read()
    src = src[src.index("fn iron_intro"):]
    n = 0
    for who, text in re.findall(r'Line::(?:say|feel)\(([^,]+),(?: Mood::\w+,)? "(.*)"\)', src):
        cur, lines = "", []
        for w in text.split(" "):
            t = (cur + " " + w).strip()
            if lint.px(t) <= lint.LIMIT:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        ctx.check(len(lines) <= 2, f"two lines or fewer: {text}")
        if who.strip() in ("co::KANBEI", "crate::co_new::ASUKA"):
            ctx.check(not lint.CONTRACTION.search(text), f"no contractions for {who}: {text}")
        n += 1
    ctx.check(n >= 20, f"{n} lines checked")
