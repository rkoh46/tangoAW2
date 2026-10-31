"""The Gauntlet's second map (crate::gauntlet_mode: Iron Crown, then Asuka's Keep; docs/dev/gauntlet.md): a five-army land gauntlet (the player, Emerald Sun, is the fifth army) whose four lines
(Grit, Jess, Kanbei, Rachel) each come when the line before falls, then the stage switch to Asuka's Keep, where taking her HQ wins. `-k gauntlet_map2`. Map 2 is started with
`TANGOAW2_GAUNTLET_MAP=1` (until Select Mode has a map choice)."""

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
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=dict(ga.MAP2_ENV, **(env or {})))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(co)
    to_player_turn(e, g, d)
    return e, g, d


def to_player_turn(e, g, d, frames=24000):
    """The fifth army moves last: A through the scripts until it is the player's turn with nothing running (Grit's turn goes by)."""
    for _ in range(frames // 20):
        if d.scripts_running():
            e.press("A", 4)
        elif g.current_army() == 5 and d.in_battle():
            e.wait(30)
            if g.current_army() == 5 and not d.scripts_running():
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
        ctx.check(len(g.units(army=army)) > 0 or d.owner(ga.IRON[key]) == 5, f"{who}'s survivors stay on the map")
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    ctx.eq(stage(e), 1, "Rachel's fall moves the battle to stage two")
    e.close()


@test(name="gauntlet_map2_stage_two_carries_the_survivors_and_asuka_wins", modes=("ds",))
def gauntlet_map2_stage_two_carries_the_survivors_and_asuka_wins(ctx):
    """The switch: the player's survivors land on Asuka's Keep, funds capped, the Emerald Sun skin sits on Orange Star's colour and Asuka is Black Hole's; taking her HQ wins."""
    e, g, d = start(ctx)
    for key, army, who, nxt in ga.IRON_ORDER[:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
    mine = sorted((u["type"], u["hp"]) for u in g.units(army=5))
    p = g.player(5)["raw"]
    skin_before = e.u8(ga.SKIN_STATE)
    colour_before = e.u8(g.players_base + 0x3C * 5 + 0x1A)
    ctx.eq((skin_before, colour_before), (5, 5), "stage one: the Emerald Sun skin sits on the fifth army's colour (Black Hole's)")
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(e.u8(FIVE_ON), 0, "stage two is a two-army game")
    ctx.eq((e.u16(dc.MAP), e.u16(dc.MAP + 2)), (30, 22), "Asuka's Keep is 30 x 22")
    after = sorted((u["type"], u["hp"]) for u in g.units(army=1))
    ctx.check(len(after) >= 0.8 * len(mine), f"the survivors came along ({len(after)} of {len(mine)})")
    ctx.check(funds(g, 1) <= CARRY_CAP, f"funds carried with a cap ({funds(g, 1)} <= {CARRY_CAP})")
    asuka = g.units(army=2)
    ctx.check(len(asuka) >= 25, f"Asuka's fresh army is on the keep ({len(asuka)})")
    ctx.eq(funds(g, 2) >= 60000, True, "Asuka holds her fortress with funds")
    cols = [e.u8(g.players_base + 0x3C * a + 0x1A) for a in (1, 2)]
    ctx.eq(cols, [1, 5], "the player is Orange Star's colour (with the Emerald Sun skin), Asuka Black Hole's")
    ctx.eq(e.u8(ga.SKIN_STATE), 1, "the Emerald Sun skin moved to the player's new colour")
    png(ctx, e, "keep_first_turn")
    ctx.eq(d.owner(ga.KEEP_ASUKA), 2, "Asuka's HQ is on the map")
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    ctx.eq(d.through_results(), 1, "taking Asuka's HQ wins the gauntlet")
    e.close()


@test(name="gauntlet_map2_suspend_and_resume", modes=("ds",))
def gauntlet_map2_suspend_and_resume(ctx):
    """Saved after Grit's fall (Jess's line on the field) and on Asuka's Keep, then continued from Select Mode: byte for byte as saved, five-army again for the first, and the stage number back for the second."""
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
    ctx.eq(e.u8(FIVE_ON), 2, "resumed: the five-army mission is on")
    compare_whole(ctx, before, whole_battle(g), "after Grit's fall, resumed")
    for key, army, who, nxt in ga.IRON_ORDER[1:3]:
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
    d.capture(ctx, ga.IRON["rachel"], army=5)
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    before = whole_battle(g)
    ctx.eq(stage(e), 1, "on stage two")
    saves.suspend(g)
    saved = saves.flash(e, os.path.join(ctx.out, "saved2"))
    ctx.check(not saved.problems(), f"stage two: every slot passes its check ({saved.problems()})")
    e.close()
    e, g, d = resume(ctx, saved.path)
    ctx.eq(stage(e), 1, "resumed on stage two")
    compare_whole(ctx, before, whole_battle(g), "on Asuka's Keep, resumed")
    ctx.eq(e.u8(ga.SKIN_STATE), 1, "the skin is on the player's colour after the resume")
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    ctx.eq(d.through_results(), 1, "the resumed stage is won")
    e.close()


def resume(ctx, path):
    e = Emu(save=path, ds=ctx.ds, env=dict(ga.MAP2_ENV))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open()
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
