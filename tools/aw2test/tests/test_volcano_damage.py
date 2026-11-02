"""The custom volcano hazard really hurts: on every map of ours that has one (crate::hazard, `VolcanoDef`), units of every army are parked on the cells of the next
eruption, the day is ended, and each loses the configured HP (never below 1). The cells are the Rust's own (`VolcanoDef::cells_on`: aw2test.volcano). BH Campaign M16
(the test map) is `bh_campaign_volcano_hazard`."""

from aw2test import bhact2 as a2
from aw2test import bh2campaign as b2
from aw2test import escampaign as es
from aw2test import gauntlet as ga
from aw2test import volcano as vo
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
from aw2test.harness import test


def entered(ctx, module, n):
    e, g, d = module.enter(ctx, n)
    if d.in_setup():
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", ())
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def gauntlet(ctx, colour, label):
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.CAULDER, colour=colour)
    vo.check(ctx, e, g, d, vo.ring(21, 0, 28, 7), 3, 1, 3, 3, label)
    e.close()


@test(modes=("ds",))
def volcano_damage_gauntlet_cinder_sea_orange_star(ctx):
    """Cinder Sea (Hawke's volcano island): ring (21,0)-(28,7), 3 cells a day from day 3, 3 HP."""
    gauntlet(ctx, None, "Cinder Sea (Orange Star)")


@test(modes=("ds",))
def volcano_damage_gauntlet_cinder_sea_silver_nova(ctx):
    """The same with the player in the Silver Nova skin."""
    gauntlet(ctx, ga.EMERALD_SUN, "Cinder Sea (Silver Nova)")


@test(modes=("ds",))
def volcano_damage_bh2_m3_iron_ledger(ctx):
    e, g, d = entered(ctx, b2, 3)
    vo.check(ctx, e, g, d, vo.ring(19, 10, 26, 17), 3, 1, 5, 3, "BH2 M3")
    e.close()


@test(modes=("ds",))
def volcano_damage_bh2_m19_thirty_years_of_iron(ctx):
    e, g, d = entered(ctx, b2, 19)
    vo.check(ctx, e, g, d, vo.ring(20, 10, 27, 17), 3, 1, 5, 3, "BH2 M19")
    e.close()


@test(modes=("ds",))
def volcano_damage_silver_nova_m16_mount_sol(ctx):
    e, g, d = entered(ctx, es, 16)
    vo.check(ctx, e, g, d, vo.ring(19, 10, 26, 17), 3, 1, 4, 3, "Silver Nova M16")
    e.close()


def bh_mission(ctx, n, won, unlocked, picks):
    from aw2test import bhcampaign as bh
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = {n - 1: len(picks)}
    d.start_at(won, unlocked)
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


@test(modes=("ds",))
def volcano_damage_bh_m11_ashfall_pass(ctx):
    e, g, d = bh_mission(ctx, 11, (1 << 10) - 1, 0xFFF, [])
    vo.check(ctx, e, g, d, vo.ring(11, 6, 18, 13), 3, 1, 5, 3, "BH M11")
    e.close()



def art_check(ctx, env, label):
    """The Volcano structure's picture (OBJ tiles 0x130..0x16F) and its palette (sprite palette 2) are what a fresh start has after the days, the eruptions and
    the computer's battles (the lava's own animation excluded: the tiles that move between two looks at the same moment)."""
    e = Emu(save=paths.base_save(), ds=True, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.CAULDER, colour=ga.EMERALD_SUN)

    def snap():
        g.goto(24, 3)
        e.wait(90)
        tiles = e.read(0x0601_0000 + 32 * 0x130, 32 * 64)
        pal = e.read(0x0500_0000 + 0x200 + 64, 32)
        return [tiles[32 * i:32 * i + 32] for i in range(64)], pal

    base = snap()
    moving = set()
    for k in range(60):                        # (the lava's frames: every tile that moves in a second)
        e.wait(5)
        t = e.read(0x0601_0000 + 32 * 0x130, 32 * 64)
        moving |= {i for i in range(64) if t[32 * i:32 * i + 32] != base[0][i]}
    ctx.log(f"{label}: animated tiles {sorted(moving)}")
    for n in (3, 5):
        while e.u16(0x03004080) < n:
            day = e.u16(0x03004080)
            d.end_turn()
            for _ in range(900):
                if e.u16(0x03004080) == day + 1 and not d.scripts_running():
                    break
                if d.scripts_running():
                    e.press("A", 4)
                e.wait(10)
            e.wait(1200)
            d.settle()
        tiles, pal = snap()
        bad = [i for i in range(64) if i not in moving and tiles[i] != base[0][i]]
        ctx.check(not bad, f"{label}: day {n}: the Volcano's picture tiles are as at the start (differing: {bad})")
        ctx.check(pal == base[1], f"{label}: day {n}: the Volcano's palette is as at the start")
    e.close()


@test(modes=("ds",))
def volcano_art_survives_days_and_eruptions_aw2_graphics(ctx):
    art_check(ctx, {}, "AW2 graphics")


@test(modes=("ds",))
def volcano_art_survives_days_and_eruptions_ds_graphics(ctx):
    art_check(ctx, {"TANGOAW2_DS_GRAPHICS": "1"}, "DS graphics")


@test(modes=("ds",))
def volcano_art_survives_days_and_eruptions_ds_tilt(ctx):
    art_check(ctx, {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SCALE": "2"}, "DS graphics and tilt")
