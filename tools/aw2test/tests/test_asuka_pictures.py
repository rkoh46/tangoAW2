"""Pictures of Asuka's powers for the review sheet (`aw2dev co portrait powers asuka` gathers them into sheets/asuka/asuka_powers.png): the power bar filling, the CO Power's activation (the quote
box, the cut-in, the flash, the units' HP before and after), the Super Power's, the Tag Power with Von Bolt, a battle where Counter Break triggers, the fog view with her vision. Each picture is
a frame of the real game (a 240 x 160 BMP in this test's output folder); the frames chosen are picked by what they show (red cut-in, the cream quote band, the brightest flash) and written
under the names the sheet looks for."""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "devkit"))

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
    def name_extent(n):
        """The width of the power's name on show: its blue outline's leftmost to rightmost column (the letters are typed in one by one, so the widest frame has the whole name)."""
        rows = read_bmp(n)
        xs = [x for r in rows[30:120] for x, (a, b, c) in enumerate(r[:160]) if c > a + 60 and c > b + 20]
        return (max(xs) - min(xs)) if xs else 0
    darks = {n: dark(n) for n in names}
    most = max(darks.values())
    figure_in = [n for n in names if darks[n] >= 0.8 * most]          # her whole figure in (most of her black uniform)

    def name_mask(n):
        rows = read_bmp(n)
        return tuple((x, y) for y in range(30, 120) for x, (a, b, c) in enumerate(rows[y][:160]) if c > a + 60 and c > b + 20)
    masks = {n: name_mask(n) for n in figure_in}
    # the name's row: where most of the blue outline sits over all frames; the frame with the most of it inside that row has the whole name on one line (a falling letter or a sliding bar is outside it)
    from collections import Counter
    rows_seen = Counter(y for m in masks.values() for (x, y) in m)
    row = rows_seen.most_common(1)[0][0]
    inband = {n: sum(1 for (x, y) in m if row - 9 <= y <= row + 9) for n, m in masks.items()}
    # (a bar of blue wiping across the screen as the name leaves is a row of 200 blue pixels or more: those frames are not the name held still)
    def barred(n):
        rows = read_bmp(n)
        return any(sum(1 for (a, b, c) in r if c > a + 60 and c > b + 20) >= 200 for r in rows)
    first_bar = next((n for n in figure_in if barred(n)), None)          # (the name is typed in before its bars wipe it out)
    clear = figure_in[:figure_in.index(first_bar)] if first_bar else figure_in
    clear = clear or figure_in
    best = max(inband[n] for n in clear)
    cut = [n for n in clear if inband[n] >= 0.99 * best][0]
    quote = [n for n in names if st[n][2] > 0.9 and st[n][0] < 0.07]
    # the power's flash (AW2's, the same length for Hawke, Sonja and Kanbei: the screen goes white for about 14 emulated frames, twice): the frames just before and just after the first white
    # run are the steps to show, never the white itself
    means = [st[n][1] for n in names]
    white = [k for k, m in enumerate(means) if m >= 250]
    if white:
        k0 = white[0]
        k1 = k0
        while k1 + 1 < len(means) and means[k1 + 1] >= 250:
            k1 += 1
        pre = [k for k in range(k0) if means[k] <= 200]
        post = [k for k in range(k1 + 1, len(names)) if means[k] <= 200]
        before, after = names[pre[-1] if pre else max(0, k0 - 1)], names[post[0] if post else min(len(names) - 1, k1 + 1)]
    else:
        peak = max(range(len(names)), key=lambda k: means[k])          # (no white: the brightest frame, a wash of light)
        before, after = names[max(0, peak - 6)], names[peak]
    flash = after
    out = {"cutin": cut, "preflash": before, "postflash": after, "quotes": quote}
    ctx.log(f"{prefix}: the white run is {len(white)} frames of {len(names)} (2 emulated frames apart each)")
    if quote:
        out["quote"] = quote[-1]          # (the last frame the box is up: the text is typed out by then)
    d = os.path.dirname(cut)
    for k, n in out.items():
        if k != "quotes":
            shutil.copyfile(n, os.path.join(d, f"{prefix}_{k}.bmp"))
    ctx.log(f"{prefix}: " + ", ".join(f"{k} = {os.path.basename(v)} {tuple(round(x, 2) for x in st[v])}" for k, v in out.items() if k != "quotes"))
    return out


@test(modes=("ds",), )
def asuka_pics_power_bar(ctx):
    """The meter filling, 0 / 25 / 50 / 75 / 100% of the CO Power's price (36000), then the Super Power's price; the HUD's bar and stars as the game draws them."""
    g = hp_battle(ctx, "power", visuals="off")
    p = g.player(1)
    from aw2test import ram
    for k, frac in enumerate((0, 25, 50, 75, 100)):
        g.e.w32(p["addr"] + ram.P_CHARGE, 36000 * frac // 100)
        g.e.wait(30)
        ctx.shot(g, f"bar_{k}")
    g.e.w32(p["addr"] + ram.P_CHARGE, 72000)
    g.e.wait(30)
    ctx.shot(g, "bar_super")
    ctx.check(True, "bar shots taken")


def quote_extent(path):
    """The pixel width of each of the dialogue box's text lines in a frame (dark pixels of the box's text rows, the lines told apart by their rows): [w1, w2]."""
    rows = read_bmp(path)
    lines, cur, last = [], None, -9
    for y in range(124, 158):
        xs = [x for x in range(52, 236) if sum(rows[y][x]) < 230]
        if not xs:
            continue
        if cur and y - last <= 2:
            cur = (cur[0], y, min(cur[2], xs[0]), max(cur[3], xs[-1]))
        else:
            if cur:
                lines.append(cur)
            cur = (y, y, xs[0], xs[-1])
        last = y
    if cur:
        lines.append(cur)
    return [(b[3] - b[2] + 1) for b in lines if b[1] - b[0] >= 4]


def expected_quote(which):
    import tomllib
    from aw2.gfxlib import font
    d = tomllib.loads(open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "cos", "asuka.toml")).read())
    f = font.load()
    lines = d["scop" if which == "super" else "cop"]["quote"]
    return lines, [sum(f[c][0] for c in l if c in f) + len(l) - 1 for l in lines]


def activation(ctx, which, prefix):
    g = hp_battle(ctx, which, visuals="off")
    ctx.shot(g, f"{prefix}_before")
    g.charge_power(1, which)
    g.e.wait(10)
    g.open_map_menu()
    g.choose("Super" if which == "super" else "Power", g.MAP_MENU)
    shots = burst(ctx, g, f"{prefix}_f", 300, 2)
    out = pick(ctx, shots, prefix)
    lines, widths = expected_quote(which)
    # the last frame whose box shows both lines (the box closes into the next scene on the frames after the text)
    full = [q for q in out["quotes"] if len(quote_extent(q)) == 2]
    if full:
        out["quote"] = full[-1]
        shutil.copyfile(full[-1], os.path.join(os.path.dirname(full[-1]), f"{prefix}_quote.bmp"))
    got = quote_extent(out["quote"])
    ctx.log(f"{prefix}: the typed-out quote box {out['quote']}: line widths {got}, the text {lines} is {widths} px in AW2's font")
    ctx.check(len(got) == len(lines) and all(abs(a - b) <= 3 for a, b in zip(got, widths)), f"{prefix}: both quote lines are typed out in full and are the power's own ({lines}): {got} vs {widths}")
    mode = 2 if which == "super" else 1
    ctx.require(g.e.wait_until(lambda: g.player(1)["co_mode"] == mode, 3000, step=10), "the power is on")
    g.wait_for_input()
    ctx.shot(g, f"{prefix}_after")
    ctx.eq(g.unit_at(5, 5)["hp"], 45, f"{prefix}: her Mech stays at 45 (no HP effect on her side)")


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
    from tests.test_asuka import no_rain
    no_rain(g)
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
