"""Pictures of Asuka's powers for the review sheet (`aw2dev co portrait powers asuka` gathers them into sheets/asuka/asuka_powers.png): the power bar filling, the CO Power's activation (the quote
box, the cut-in, the flash, the units' HP before and after), the Super Power's, the Tag Power with Von Bolt, a battle where Counter Break triggers, the fog view with her vision. Each picture is
a frame of the real game (a 240 x 160 BMP in this test's output folder); the frames chosen are picked by what they show (red cut-in, the cream quote band, the brightest flash) and written
under the names the sheet looks for."""

import os
import shutil

from aw2test import rom as romlib
from aw2test import tag
from aw2test.harness import test
from tests.test_asuka import ASUKA, hp_battle, vision_map
from tests.test_fog import MAP, seen
from tests.test_tag import fill, tag_battle
from tests.test_tag import EXTRAS, TAG_START, screen_at, read_bmp


def stats(path):
    """(red share, mean brightness, share of the bottom band that is the quote box's cream) of a frame."""
    rows = read_bmp(path)
    px = [p for r in rows for p in r]
    red = sum(1 for r, g, b in px if r > 200 and g < 90 and b < 70) / len(px)
    bright = sum(r + g + b for r, g, b in px) / (3 * len(px))
    band = [p for r in rows[124:152] for p in r[70:230]]
    cream = sum(1 for r, g, b in band if min(r, g, b) > 205) / len(band)
    return red, bright, cream


def burst(ctx, g, prefix, frames=70, gap=4):
    """Shots every `gap` frames while a power plays: names <prefix>NN."""
    names = []
    for k in range(frames):
        names.append(ctx.shot(g, f"{prefix}{k:02d}"))
        g.e.wait(gap)
    return names


def pick(ctx, names, prefix):
    """The frames of a power's activation by what they show: the cut-in (the most of the figure's black uniform), the quote box (cream band, no red), the flash (brightest)."""
    st = {n: stats(n) for n in names}
    def dark(n):
        rows = read_bmp(n)
        return sum(1 for r in rows for (x, y, z) in r if max(x, y, z) < 60)
    most = max(dark(n) for n in names)
    cut = [n for n in names if dark(n) >= 0.97 * most][-1]          # (her black uniform on the red or the flames: the last frame with the whole figure in, the power's name typed out by then)
    quote = [n for n in names if st[n][2] > 0.9 and st[n][0] < 0.07]
    flash = max(names, key=lambda n: st[n][1])
    out = {"cutin": cut, "flash": flash}
    if quote:
        out["quote"] = quote[len(quote) // 2]
    d = os.path.dirname(cut)
    for k, n in out.items():
        shutil.copyfile(n, os.path.join(d, f"{prefix}_{k}.bmp"))
    ctx.log(f"{prefix}: " + ", ".join(f"{k} = {os.path.basename(v)} {tuple(round(x, 2) for x in st[v])}" for k, v in out.items()))
    return out


@test(modes=("ds",), )
def asuka_pics_power_bar(ctx):
    """The meter filling, 0 / 25 / 50 / 75 / 100% of the CO Power's price (27000), then the Super Power's price; the HUD's bar and stars as the game draws them."""
    g = hp_battle(ctx, "power", visuals="off")
    p = g.player(1)
    from aw2test import ram
    for k, frac in enumerate((0, 25, 50, 75, 100)):
        g.e.w32(p["addr"] + ram.P_CHARGE, 27000 * frac // 100)
        g.e.wait(30)
        ctx.shot(g, f"bar_{k}")
    g.e.w32(p["addr"] + ram.P_CHARGE, 81000)
    g.e.wait(30)
    ctx.shot(g, "bar_super")
    ctx.check(True, "bar shots taken")


def activation(ctx, which, prefix):
    g = hp_battle(ctx, which, visuals="off")
    ctx.shot(g, f"{prefix}_before")
    g.charge_power(1, which)
    g.e.wait(10)
    g.open_map_menu()
    g.choose("Super" if which == "super" else "Power", g.MAP_MENU)
    shots = burst(ctx, g, f"{prefix}_f", 130, 4)
    pick(ctx, shots, prefix)
    mode = 2 if which == "super" else 1
    ctx.require(g.e.wait_until(lambda: g.player(1)["co_mode"] == mode, 3000, step=10), "the power is on")
    g.wait_for_input()
    ctx.shot(g, f"{prefix}_after")
    ctx.eq(g.unit_at(5, 5)["hp"], 55 if which == "power" else 65, f"{prefix}: the Mech 45 -> {55 if which == 'power' else 65}")


@test(modes=("ds",))
def asuka_pics_cop_activation(ctx):
    activation(ctx, "power", "cop")


@test(modes=("ds",))
def asuka_pics_scop_activation(ctx):
    activation(ctx, "super", "scop")


@test(modes=("ds",))
def asuka_pics_tag_power_with_von_bolt(ctx):
    """The Tag Power's screen (Asuka + Von Bolt, Vault Breakers) sliding in and settled, then the two halves on the map."""
    units = [(1, "tank", 10, 10), (2, "tank", 11, 10), (1, "infantry", 3, 3), (2, "infantry", 25, 14)]
    g = tag_battle(ctx, ["asuka", "olaf"], ["vonbolt", None], units=units)
    e = g.e
    ctx.set_hp(g, 3, 3, 45)
    ctx.set_hp(g, 25, 14, 55)
    fill(g, 1)
    ctx.shot(g, "tag_before")
    g.open_map_menu()
    ctx.shot(g, "tag_menu")
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: e.u8(EXTRAS) == 1, 1200, step=4), "the tag screen shows")
    ctx.require(screen_at(e, 310 - TAG_START), "sliding")
    ctx.shot(g, "tag_screen_slide")
    ctx.require(screen_at(e, 600 - TAG_START), "settled")
    ctx.shot(g, "tag_screen")
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "Asuka's Super Power starts")
    g.wait_for_input()
    ctx.shot(g, "tag_first_half")
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == romlib.co_id("vonbolt") and g.player(1)["co_mode"] == 2, 3000, step=10), "Von Bolt's half")
    g.wait_for_input()
    ctx.shot(g, "tag_second_half")


@test(modes=("ds",))
def asuka_pics_counter_break(ctx):
    """Andy's Tank attacks Asuka's Tank during Event Horizon, the battle scene on (animations "a"): frames through the exchange, and the map after."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 3, 3).unit(2, "infantry", 25, 15)
    g = ctx.start(m, ["asuka", "andy"], humans=(1, 2), visuals="a")
    ctx.power(g, 1, "super")
    g.end_turn(human=2)
    ctx.shot(g, "cb_before")
    e = g.e
    g.select(11, 10)
    g.move_to(11, 10)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(10, 10)
    for k in range(40):
        ctx.shot(g, f"cb_f{k:02d}")
        e.wait(10)
    g.wait_for_input()
    ctx.shot(g, "cb_after")


@test(modes=("ds",))
def asuka_pics_fog_view(ctx):
    """The fog view: Asuka's Tank day to day, in Dark Intel, and Andy's Tank for comparison."""
    for name, co, power in (("fog_andy", "andy", None), ("fog_d2d", "asuka", None), ("fog_cop", "asuka", "power")):
        g = ctx.start(vision_map(ctx), [co, "andy" if co != "andy" else "olaf"], fog=True)
        if power:
            ctx.power(g, 1, power)
            g.wait_for_input()
            g.goto(10, 6)
        g.e.wait(60)
        ctx.shot(g, name)


@test(modes=("ds",))
def asuka_pics_co_select_grid(ctx):
    """The War Room's CO screen in Dual Strike's grid, the cursor on Asuka (the same screen Survival and Champion use), and AW2's own screen beside it."""
    from aw2test import warroom as wr
    from tests.test_ds_coselect import war_room_co_screen, under_cursor
    e, g = war_room_co_screen(ctx, True)
    wr.go_to(e, ASUKA)
    e.wait(60)
    ctx.eq(wr.highlighted(e)[1], ASUKA, "the game's cursor is on Asuka")
    ctx.shot(g, "grid_asuka")
    e.close()
    e, g = war_room_co_screen(ctx, False)
    wr.go_to(e, ASUKA)
    e.wait(60)
    ctx.shot(g, "grid_aw2")
    e.close()


@test(modes=("ds",))
def asuka_pics_hq_follows_the_co(ctx):
    """Her HQ is Black Hole's whichever colour slot she plays in: army 1 (Orange Star's red) is Asuka and the HQ picture (the panel's, and the map's building) is drawn with Black Hole's building picture, the same tiles as Hawke's; Andy's (Orange Star's) and Sonja's differ."""
    tiles = {}
    for co in ("asuka", "hawke", "andy", "sonja", "crumb"):
        m = ctx.map()
        m.unit(1, "tank", 3, 3).unit(2, "tank", 20, 12)
        g = ctx.start(m, [co, "olaf"])
        g.goto(0, 0)
        g.e.wait(60)
        ctx.shot(g, f"hq_{co}")
        from tests.test_tag import read_bmp
        rows = read_bmp(os.path.join(ctx.out, f"hq_{co}.bmp"))
        tiles[co] = [row[2:14] for row in rows[92:112]]      # (the HQ picture in the info panel at the foot of the map's left side)
    ctx.check(tiles["asuka"] == tiles["hawke"], "Asuka's HQ at army 1's corner is drawn exactly as Hawke's (Black Hole's)")
    ctx.check(tiles["asuka"] != tiles["andy"], "and is not Andy's (Orange Star's)")
    ctx.check(tiles["asuka"] != tiles["sonja"], "nor Sonja's (Yellow Comet's)")


@test(modes=("ds",))
def asuka_pics_ammo_and_fuel(ctx):
    """The unit panel (cursor on an enemy Tank and on an enemy Battleship) before and after Dark Intel and Event Horizon: fuel 70 -> 35 and ammo 9 -> 4 on the Tank, fuel 99 -> 49 on the Battleship."""
    for which, tag_ in (("power", "cop"), ("super", "scop")):
        m = ctx.map()
        m.unit(1, "tank", 4, 4).unit(2, "tank", 12, 10).unit(2, "infantry", 14, 10)
        g = ctx.start(m, ["asuka", "andy"])
        a = g.unit_addr(g.unit_at(12, 10)["id"])
        g.e.w8(a + 6, (g.e.u8(a + 6) & 0x80) | 70)
        g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x780) | (9 << 7))
        g.goto(12, 10)
        g.e.wait(40)
        ctx.shot(g, f"af_{tag_}_before")
        g.charge_power(1, which)
        ctx.power(g, 1, which)
        g.goto(12, 10)
        g.e.wait(40)
        ctx.shot(g, f"af_{tag_}_after")
        u = g.unit_at(12, 10)
        ctx.eq((u["fuel"], u["ammo"]), (35, 4), f"{which}: the enemy Tank's fuel 70 -> 35 and ammo 9 -> 4")
