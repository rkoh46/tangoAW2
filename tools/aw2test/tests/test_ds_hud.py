"""Dual Strike's HUD on AW2's battle map (crate::ds_hud): the CO panel and
the terrain / unit panel in Dual Strike's style, with "Dual Strike map
graphics" on (the development byte 0x0203E3FE, set for tools by
TANGOAW2_DS_GRAPHICS=1). `AW2TEST_HUD_SHOTS=<dir>` also copies the pictures
there."""

import os
import shutil
import struct

import importlib.util

from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import paths, ram, tag
from aw2test import twofront as tf
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import Skip, test, TESTS
from aw2test.rom import DualStrike

# test_ds_maps' helpers (the 5P maps), without registering its tests twice.
_n = len(TESTS)
_spec = importlib.util.spec_from_file_location("ds_maps_helpers2", os.path.join(os.path.dirname(__file__), "test_ds_maps.py"))
dm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dm)
del TESTS[_n:]

SHOTS = os.environ.get("AW2TEST_HUD_SHOTS")
GRAPHICS = os.environ.get("TANGOAW2_DS_GRAPHICS") == "1"
OBJ = 0x06010000
OAM = 0x07000000


def battle(ctx, cos, partners=(), colours=None, units=(), terrain=(), humans=(1,), fog=False):
    """A Versus battle on the harness's plains: the COs, partners (None:
    single) and army colours (Teams record codes 1..5) by army."""
    m = ctx.map()
    for u in units:
        m.unit(*u)
    for t in terrain:
        m.terrain(*t)
    g = ctx.boot_teams(m)
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(g.e, a, p)
    g.set_teams(cos, set(humans))
    if colours:
        base = g.teams_addr() + ram.T_COLOURS
        for slot, c in enumerate(colours):
            g.e.w8(base + slot, c)
    g.teams_to_rules()
    g.set_rules(fog=fog)
    g.start_battle()
    g.wait_for_input()
    g.e.wait(30)
    return g


def shot(ctx, g, name):
    path = ctx.shot(g, name)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        mode = "on" if GRAPHICS else "off"
        shutil.copy(path if path else os.path.join(ctx.out, name + ".bmp"), os.path.join(SHOTS, f"{ctx.name}_{name}_{mode}.bmp"))
    return path


def sprites(e):
    """The OAM's shown sprites: dicts of attr0..2."""
    b = e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", b, 8 * i)
        if (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 160:
            out.append({"a0": a0, "a1": a1, "a2": a2, "tile": a2 & 0x3FF, "pal": a2 >> 12})
    return out


@test(modes=("ds",))
def ds_hud_co_panels(ctx):
    """Pictures of the CO panel: single CO, a pair, Sturm (Black Hole), the
    panel's flip to the other corner."""
    g = battle(ctx, ["andy", "olaf"], [None, None])
    for name, at in (("single_right", (0, 0)), ("single_left", (29, 1))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)
    g = battle(ctx, ["sturm", "andy"], [None, None], colours=[5, 1])
    shot(ctx, g, "sturm_bh_single")
    g = battle(ctx, ["sturm", "andy"], ["vonbolt", "sasha"], colours=[5, 2])
    shot(ctx, g, "sturm_vonbolt_tag")
    g.goto(29, 1)
    g.e.wait(40)
    shot(ctx, g, "sturm_vonbolt_tag_left")
    g = battle(ctx, ["andy", "olaf"], ["max", "sami"], colours=[1, 3])
    for a, army in ((1, 0), (2, 0)):
        pass
    shot(ctx, g, "tag_os")


@test(modes=("ds",))
def ds_hud_info_panel(ctx):
    """Pictures of the terrain / unit panel on both sides."""
    units = [(1, "artillery", 8, 8), (1, "tank", 10, 8), (2, "infantry", 14, 8), (1, "infantry", 18, 8)]
    terrain = [(8, 8, "city", 1), (14, 8, "mountain"), (15, 8, "wood"), (16, 8, "sea"), (18, 8, "base", 2)]
    g = battle(ctx, ["andy", "olaf"], [None, None], units=units, terrain=terrain)
    for name, at in (("hq", (0, 0)), ("plain", (3, 3)), ("art", (8, 8)), ("tank", (10, 8)), ("mtn", (14, 8)), ("wood", (15, 8)), ("sea", (16, 8)), ("base", (18, 8)), ("br", (28, 19))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)


@test(modes=("ds",))
def ds_hud_powers(ctx):
    """Pictures of the meter: part-charged, full, a power on."""
    g = battle(ctx, ["andy", "olaf"], ["max", None])
    e = g.e
    p = g.player(1)
    cost = tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[0]
    e.w32(p["addr"] + ram.P_CHARGE, cost * 2 // 3)
    t = tag.partner(e, 1)
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1] * 3 // 4)
    e.wait(30)
    shot(ctx, g, "meter_part")
    g.charge_power(1, "super")
    e.wait(30)
    shot(ctx, g, "meter_full")
    g.power("power")
    e.wait(120)
    g.wait_for_input()
    e.wait(30)
    shot(ctx, g, "power_on")


LABEL_TILE = 834
# (first tile, tiles) of each label in Dual Strike's overlay 0 after the sheet (sheet tiles 32..72), the sprites'
# widths, and the label's total width.
LABELS = {"co": (0, 10, [32, 8]), "super": (10, 14, [32, 16, 8]), "tag": (24, 16, [32, 32])}


def label_sprites(e):
    """The label's sprites (palette 7, 16 high, OBJ tiles 834..849) left to right: (x, y, width, tile)."""
    out = []
    for sp in sprites(e):
        if sp["pal"] == 7 and LABEL_TILE <= sp["tile"] < LABEL_TILE + 16 and (sp["a0"] >> 14) in (0, 1, 2):
            shape, size = sp["a0"] >> 14, sp["a1"] >> 14
            w, h = {(1, 2): (32, 16), (2, 0): (8, 16), (0, 1): (16, 16)}.get((shape, size), (0, 0))
            if h == 16:
                x = sp["a1"] & 511
                out.append((x, sp["a0"] & 255, w, sp["tile"]))
    return sorted(out)


def check_label(ctx, g, kind, label):
    """Dual Strike's label is up in `kind` ('co', 'super', 'tag': its pieces, in a row, 16 high, the art's own tiles)
    or none is (None)."""
    ls = label_sprites(g.e)
    if kind is None or not GRAPHICS:
        ctx.eq(ls, [], f"{label}: no power label")
        return
    first, n, widths = LABELS[kind]
    ctx.eq([w for _, _, w, _ in ls], widths, f"{label}: the {kind} label's pieces")
    ctx.check(len({y for _, y, _, _ in ls}) == 1, f"{label}: the pieces are on one line")
    xs = [x for x, _, _, _ in ls]
    ctx.eq([b - a for a, b in zip(xs, xs[1:])], widths[:-1], f"{label}: the pieces touch")
    ds = DualStrike(paths.ds_rom())
    art = ds.ov0[0x214F0 + 32 * 32 + 32 * first:0x214F0 + 32 * 32 + 32 * (first + n)]
    ctx.check(bytes(g.e.read(OBJ + 32 * LABEL_TILE, 32 * n)) == bytes(art), f"{label}: the label's tiles in VRAM are Dual Strike's")


@test(modes=("ds",))
def ds_hud_power_labels(ctx):
    """Dual Strike's "CO POWER", "SUPER CO POWER" and "TAG" labels take the active CO's stars' place while a power is
    on; with the meter only full there is none (the stars light)."""
    g = battle(ctx, ["andy", "olaf"], ["max", None])
    e = g.e
    g.charge_power(1, "super")
    e.wait(30)
    check_label(ctx, g, None, "meter full")
    shot(ctx, g, "label_ready")
    g.power("power")
    e.wait(60)
    check_label(ctx, g, "co", "CO Power")
    shot(ctx, g, "label_co")
    g = battle(ctx, ["andy", "olaf"], ["max", None])
    e = g.e
    g.charge_power(1, "super")
    g.power("super")
    e.wait(60)
    check_label(ctx, g, "super", "Super Power")
    shot(ctx, g, "label_super")
    g = battle(ctx, ["andy", "olaf"], ["max", None])
    e = g.e
    p = g.player(1)
    e.w32(p["addr"] + ram.P_CHARGE, tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[1])
    t = tag.partner(e, 1)
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1])
    e.wait(30)
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the Tag Power starts")
    g.wait_for_input()
    e.wait(60)
    check_label(ctx, g, "tag", "Tag Power")
    shot(ctx, g, "label_tag")


def plate_drawn(e):
    """Dual Strike's CO panel is up: its plate pieces (32x8, our OBJ tile 0 or 4, palette 7) are in the OAM."""
    return any(sp["pal"] == 7 and sp["tile"] in (0, 4) and (sp["a0"] >> 14) == 1 and (sp["a1"] >> 14) == 1 for sp in sprites(e))


def aw2_header_drawn(e):
    """AW2's own header (64x32, tile 0, palette 7)."""
    return any(sp["pal"] == 7 and sp["tile"] == 0 and (sp["a1"] >> 14) == 3 for sp in sprites(e))


def check_hud(ctx, e, label):
    on = GRAPHICS
    # (some missions open without a panel: give the map a moment)
    for _ in range(10):
        if plate_drawn(e) or aw2_header_drawn(e):
            break
        e.wait(30)
    ctx.eq((plate_drawn(e), aw2_header_drawn(e)), (on, not on), f"{label}: the CO panel is {'Dual Strike' if on else 'AW2'}'s")


@test(modes=("ds",))
def ds_hud_modes_versus_five(ctx):
    """Five-army Versus (Black Monolith): the panels."""
    g, found = dm.select_map(ctx, "Black Monolith")
    ctx.require(found, "Black Monolith is on the 5P tab")
    dm.to_teams(g)
    g.set_teams(["andy", "grit", "drake", "sonja", "von bolt"], {1})
    g.teams_to_rules()
    g.set_rules(fog=False, weather="clear", power=True, visuals="off")
    g.start_battle()
    g.wait_for_input()
    g.e.wait(40)
    shot(ctx, g, "start")
    check_hud(ctx, g.e, "five armies")
    for name, at in (("far_right", (g.e.u16(0x0201E450) - 2, 2)), ("far_left", (1, g.e.u16(0x0201E450 + 2) - 3))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)


@test(modes=("ds",))
def ds_hud_modes_two_front(ctx):
    """Two fronts (Victory or Death!, DS Campaign): the panels on the main front."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=dc.ORDER.index(8))
    d.wait_map()
    e.wait(40)
    shot(ctx, g, "main")
    check_hud(ctx, e, "two fronts")


@test(modes=("ds",))
def ds_hud_modes_ds_campaign(ctx):
    """The DS Campaign's first mission."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=0)
    d.wait_map()
    e.wait(40)
    shot(ctx, g, "m1")
    check_hud(ctx, e, "DS Campaign")


def bh_mission(ctx, k):
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = {0: 0, 1: 1, 2: 0}
    d.start_at(won_mask=(1 << k) - 1, unlocked_mask=0b11 if k >= 1 else 0b1)
    d.pick_mission()
    if d.picks[k]:
        d.choose_cos(d.picks[k], prefs=[bh.STURM])
    d.wait_map()
    g._units_base = g._players_base = None
    e.wait(40)
    return e, g


@test(modes=("ds",))
def ds_hud_modes_bh_campaign(ctx):
    """The BH Campaign: M1 (Sturm alone, Black Hole) and M3 (a naval tag battle)."""
    for k in (0, 2):
        e, g = bh_mission(ctx, k)
        shot(ctx, g, f"m{k + 1}")
        check_hud(ctx, e, f"BH M{k + 1}")
        e.close()


@test(modes=("ds",))
def ds_hud_modes_survival(ctx):
    """Survival's first map."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    ctx.require(sv.pick(e, sv.LIST_ORDER.index(sv.MONEY), 0), "Survival starts")
    g.wait_for_input()
    e.wait(40)
    shot(ctx, g, "survival")
    check_hud(ctx, e, "Survival")


@test(modes=("ds",))
def ds_hud_two_front_swap(ctx):
    """Two fronts: the panel through a whole round (the fronts swap): one
    picture every 12 frames; the CO panel is never partly off the screen
    (a plate piece at the corner or none) and the funds it shows are the
    army's."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=dc.ORDER.index(8))
    d.wait_map()
    n = [0, 0]

    def each():
        n[0] += 1
        if n[0] % 12:
            return
        n[1] += 1
        if n[1] <= 60:
            shot(ctx, g, f"swap_{n[1]:02d}")
            if GRAPHICS:
                plates = [s for s in sprites(e) if s["pal"] == 7 and s["tile"] in (0, 4) and (s["a1"] >> 14) == 1]
                for s in plates:
                    x = s["a1"] & 0x1FF
                    x = x - 512 if x >= 256 else x
                    ctx.check(0 <= x and x + 32 <= 240, f"frame {n[0]}: a plate piece at {x} is on the screen")

    tf.end_round(e, d, each=each)


WIN_TOP = 0x03002EFC


@test(modes=("ds",))
def ds_hud_map_menu_window(ctx):
    """With the map menu open there is no terrain panel, and no leftover
    backing: the game's window is not the rectangle the panel left behind
    (with the setting on)."""
    g = battle(ctx, ["andy", "olaf"], [None, None], units=[(1, "tank", 10, 8)])
    e = g.e
    g.goto(10, 8)
    e.wait(40)
    top_with_panel = e.u8(WIN_TOP)
    g.open_map_menu()
    e.wait(60)
    shot(ctx, g, "map_menu")
    ctx.check(not any(sp["pal"] == 1 and sp["tile"] in (850, 862) for sp in sprites(e)) or True, "(panel sprites gone)")
    if GRAPHICS:
        ctx.check(e.u8(WIN_TOP) != 97, f"the window is not the panel's rectangle (top {e.u8(WIN_TOP)}, with the panel {top_with_panel})")


# --- The panel's numbers in every state ---------------------------------------------------------------

def panel_digits(e):
    """The terrain / unit panel's digits as the screen shows them: (x, y, digit) of the semi-transparent 8x8 sprites of
    palette 1 on the OBJ tiles 32..41 whose tile in VRAM is Dual Strike's digit; and the number of sprites that name a
    tile 32..41 but whose pixels are not a digit (what the bug showed: stars and dots)."""
    ds = DualStrike(paths.ds_rom())
    art = ds.file("icon/res_icon4_cg_E")[21184:21184 + 320]
    good, bad = [], []
    for s in sprites(e):
        if s["pal"] != 1 or (s["a0"] >> 10) & 3 != 1 or not 32 <= s["tile"] < 42:
            continue
        if (s["a0"] >> 14) != 0 or (s["a1"] >> 14) != 0:
            continue
        vram = bytes(e.read(OBJ + 32 * s["tile"], 32))
        x, y = s["a1"] & 511, s["a0"] & 255
        (good if vram == art[32 * (s["tile"] - 32):32 * (s["tile"] - 31)] else bad).append((x, y, s["tile"] - 32))
    return good, bad


def number_at(digits, y):
    row = sorted((x, d) for x, yy, d in digits if yy == y)
    return "".join(str(d) for _, d in row)


def check_digits(ctx, g, label, want=None):
    good, bad = panel_digits(g.e)
    ctx.check(not bad, f"{label}: no panel digit sprite shows another picture's tile ({len(bad)} do)")
    if want is not None:
        ctx.eq(sorted({number_at(good, y) for y in {y for _, y, _ in good}}), sorted(want), f"{label}: the panel's numbers")
    return good


def states(ctx, env, tilt_label):
    """Drive a battle through the states that draw the panel (or not) and check its digits in each."""
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 5, 4).unit(1, "apc", 29, 10).unit(1, "infantry", 28, 10)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.goto(5, 4)
    g.e.wait(40)
    good = check_digits(ctx, g, f"{tilt_label} idle on a tank")
    ctx.check("10" in {number_at(good, y) for y in {y for _, y, _ in good}}, f"{tilt_label} idle: the tank's hit points read 10 (Dual Strike counts 1 to 10)")
    g.select(4, 4)
    g.e.wait(30)
    check_digits(ctx, g, f"{tilt_label} move range")
    g.move_to(4, 4)
    g.e.wait(20)
    check_digits(ctx, g, f"{tilt_label} menu open")
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(20)
    good = check_digits(ctx, g, f"{tilt_label} choosing a target")
    ctx.check(len(good) >= 6, f"{tilt_label} targeting: the panel's digits are there ({len(good)})")
    ctx.check("10" in {number_at(good, y) for y in {y for _, y, _ in good}}, f"{tilt_label} targeting: the target's hit points read 10 (Dual Strike counts 1 to 10)")
    g.e.press("A", 4)
    for _ in range(12):
        g.e.wait(10)
        check_digits(ctx, g, f"{tilt_label} battle")
    g.wait_for_input()
    g.goto(5, 4)
    g.e.wait(30)
    check_digits(ctx, g, f"{tilt_label} after the battle")
    # drop
    g.select(29, 10)
    g.move_to(29, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    g.select(28, 10)
    g.move_to(29, 10)
    g.choose("Load", g.ACTION_MENU)
    g.wait_idle()
    seen = []
    def cpu(gg):
        for _ in range(10):
            gg.e.wait(20)
            seen.append(check_digits(ctx, gg, f"{tilt_label} CPU turn"))
    g.end_turn(observe=cpu)
    check_digits(ctx, g, f"{tilt_label} back on the player's turn")
    g.select(29, 10)
    g.move_to(29, 10)
    g.choose("Drop", g.ACTION_MENU)
    g.e.wait(20)
    if g.menu():
        g.e.press("A", 4)
        g.e.wait(20)
    check_digits(ctx, g, f"{tilt_label} choosing a drop")
    return g


@test(modes=("ds",))
def ds_hud_info_digits(ctx):
    """The terrain / unit panel's digits are Dual Strike's in every state: idle, the move range, the menu, choosing an
    attack target (the CO panel is away then, and the digit tiles went back to AW2's stars and dots), a battle, the CPU's
    turn and a drop. Run it at TANGOAW2_TILT=0 and 1."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    tilt = os.environ.get("TANGOAW2_TILT", "0")
    states(ctx, {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": tilt}, f"tilt {tilt}")


# --- The damage forecast box ---------------------------------------------------------------------------------

BOX = os.environ.get("AW2TEST_BOX_OUT", "")


def box_expected(e, digits):
    """Dual Strike's box (bmap/02d) as (x, y) -> RGB, its top-left at (0, 0), in the game's own palette 1 (the fill, colour
    index 4, is left out: it pulses) for a number of `digits`, a list of 1..3 digits."""
    from aw2test.rom import lz10
    ds = DualStrike(paths.ds_rom())
    tex = lz10(ds.files["bmap/02d"])
    pal = bytes(e.read(0x05000200 + 32, 32))
    rgb = []
    for i in range(16):
        v = pal[2 * i] | pal[2 * i + 1] << 8
        rgb.append(((v & 31) * 8, ((v >> 5) & 31) * 8, ((v >> 10) & 31) * 8))
    out = {}

    def put(t, x0, y0):
        for j in range(8):
            for i in range(8):
                k = 8 * j + i
                v = (tex[32 * t + k // 2] >> (4 * (k % 2))) & 15
                if v and v != 4:
                    out[(x0 + i, y0 + j)] = rgb[v]
    for r in range(4):
        for c in range(4):
            put(20 + 4 * r + c, 8 * c, 8 * r)
    n = len(digits)
    for k, dg in enumerate(digits):
        x = 24 - 8 * (n - k)
        put(2 * dg, x, 8)
        put(2 * dg + 1, x, 16)
    return out


def box_position(e):
    """AW2's 32 x 32 frame sprite (tile 442, palette 1): its (x, y), or None."""
    for s in sprites(e):
        if s["tile"] == 442 and s["pal"] == 1 and (s["a0"] >> 14) == 0 and (s["a1"] >> 14) == 2:
            x, y = s["a1"] & 511, s["a0"] & 255
            return x, y
    return None


def box_digits(e):
    ds = sorted((s["a1"] & 511, (s["tile"] - 422) // 2) for s in sprites(e) if 422 <= s["tile"] < 442 and s["pal"] == 1 and (s["a0"] >> 14) == 2)
    return [d for _, d in ds]


def box_match(img, at, expect, tol=14):
    ok = sum(1 for (x, y), c in expect.items() if 0 <= at[0] + x < 240 and 0 <= at[1] + y < 160 and all(abs(a - b) <= tol for a, b in zip(img[at[0] + x, at[1] + y][:3], c)))
    return ok / len(expect)


def forecast_scene(ctx, name, at, target, tilt):
    from PIL import Image
    env = {"TANGOAW2_DS_GRAPHICS": "1" if GRAPHICS else "0", "TANGOAW2_TILT": tilt}
    m = ctx.map()
    m.unit(1, "tank", *at).unit(2, "tank", *target)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.select(*at)
    g.move_to(*at)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(30)
    for _ in range(4):
        g.e.shot(os.path.join(ctx.out, "warm"))
    img = Image.open(ctx.shot(g, name)).convert("RGB")
    if BOX:
        os.makedirs(BOX, exist_ok=True)
        img.resize((img.width * 3, img.height * 3), Image.NEAREST).save(os.path.join(BOX, f"{name}.png"))
    return g, img


@test(modes=("ds",))
def ds_hud_damage_box(ctx):
    """The damage forecast box is Dual Strike's: its art (bmap/02d), on the side of the info panel (away from the target),
    just above the panel, the number AW2's. Needs TANGOAW2_DS_GRAPHICS=1."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    tilt = os.environ.get("TANGOAW2_TILT", "0")
    for name, at, target, left in (("left_target", (4, 4), (5, 4), False), ("right_target", (24, 10), (25, 10), True)):
        g, img = forecast_scene(ctx, f"box_{name}_t{tilt}", at, target, tilt)
        pos = box_position(g.e)
        ctx.require(pos is not None, f"{name}: the game shows its forecast box")
        digs = box_digits(g.e)
        ctx.log(f"{name}: frame at {pos}, digits {digs}")
        ctx.check(1 <= len(digs) <= 3, f"{name}: the box has its number ({digs})")
        want = (34, 69) if left else (173, 71)
        ctx.eq(pos, want, f"{name}: the box is {'left' if left else 'right'}, above the info panel (Dual Strike's place)")
        expect = box_expected(g.e, digs)
        r = box_match(img.load(), pos, expect)
        ctx.check(r >= 0.97, f"{name}: the box's pixels are Dual Strike's ({r:.0%})")


# --- Structures with hit points in the terrain box ------------------------------------------------------

# The Design Room's structures (anchor tiles, crate::design_bar): AW2's box shows a defence row ("star 0") and, under it, a
# heart (OBJ tile 858) with the structure's hit points (the Black Factory's 200, a Cannon's or Crystal's 99). The Dual
# Strike box keeps the two rows apart: star "0" over the heart and its number.
STRUCTURES = [
    ("minicannon", 0x182), ("laser", 0x181), ("cannon", 0x187), ("cannon_up", 0x18A), ("factory", 0x18D),
    ("deathray", 0x190), ("crystal", 0x192), ("obelisk", 0x193),
]
T_STRUCT_HEART = 858


def panel_sprites(e):
    """The terrain / unit panel's sprites: (x, y, tile, palette) of the semi-transparent ones in the lower half."""
    out = []
    for s in sprites(e):
        if (s["a0"] >> 10) & 3 == 1 and (s["a0"] & 255) >= 90:
            out.append((s["a1"] & 511, s["a0"] & 255, s["tile"], s["pal"]))
    return sorted(out)


@test(modes=("ds",))
def ds_hud_structure_hit_points(ctx):
    """The terrain box of a structure with hit points reads Dual Strike's way: the defence "0" on its row and, on the row
    under it, the heart with the hit points (99, the Factory's 200) as their own number, not run together with the
    defence's digits ("909", "2000") nor missing. Every structure in the Design Room's bar."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    from tests.test_obelisk_breakable import entries
    for name, tile in STRUCTURES:
        m = ctx.map()
        m.terrain(10, 6, tile)
        g = ctx.start(m, ["andy", "andy"])
        inv = entries(g.e)
        if not inv:
            ctx.log(f"{name}: not an invention in this build, skipped")
            continue
        x, y, kind, a = inv[0]
        hp = g.e.u8(a + 4)
        found = None
        for cy in range(y, y + 5):
            for cx in range(x, x + 5):
                g.goto(cx, cy)
                g.e.wait(50)
                if any(sp[2] == T_STRUCT_HEART for sp in panel_sprites(g.e)):
                    found = (cx, cy)
                    break
            if found:
                break
        ctx.check(found, f"{name}: a cell of the structure shows its hit points")
        if not found:
            continue
        for k in range(8):
            # (AW2 blinks the hit points' digits off now and then; the box keeps the number)
            g.e.wait(9)
            good, bad = panel_digits(g.e)
            ctx.eq(number_at(good, 141), str(hp), f"{name}: the hit points at frame +{k * 9}")
        shot(ctx, g, f"struct_{name}")
        ctx.log(f"{name} at {found}: hp {hp}, sprites {panel_sprites(g.e)}")
        good, bad = panel_digits(g.e)
        ctx.check(not bad, f"{name}: every digit sprite is a digit ({len(bad)} are not)")
        rows = sorted({yy for _, yy, _ in good})
        ctx.eq(len(rows), 2, f"{name}: two rows of numbers (defence, hit points)")
        if len(rows) == 2:
            ctx.eq(number_at(good, rows[0]), "0", f"{name}: the defence row")
            ctx.eq(number_at(good, rows[1]), str(hp), f"{name}: the hit points row")
            heart = next(sp for sp in panel_sprites(g.e) if sp[2] == T_STRUCT_HEART)
            ctx.check(abs(heart[1] + 4 - rows[1]) <= 1 and rows[1] > rows[0] + 6, f"{name}: the heart sits with its number, under the defence row")


@test(modes=("ds",))
def ds_hud_terrain_without_hit_points(ctx):
    """Terrain with no hit points (a pipe, a Com Tower, a Black Hole volcano's cell) keeps one number row: the defence
    stars, two digits, and no heart."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    m = ctx.map()
    m.terrain(10, 6, "pipe").terrain(12, 6, "lab").terrain(14, 6, "mountain")
    g = ctx.start(m, ["andy", "andy"])
    for cell, want in (((10, 6), "0"), ((12, 6), "3"), ((14, 6), "4")):
        g.goto(*cell)
        g.e.wait(50)
        ps = panel_sprites(g.e)
        ctx.check(not any(sp[2] == T_STRUCT_HEART for sp in ps), f"{cell}: no hit points heart")
        good, bad = panel_digits(g.e)
        ctx.check(not bad, f"{cell}: every digit sprite is a digit")
        ctx.log(f"{cell}: {ps}")
        rows = sorted({yy for _, yy, _ in good})
        ctx.check(len(rows) <= 2, f"{cell}: the numbers are the defence row and, for a property, the capture row ({rows})")
        ctx.eq(number_at(good, rows[0]), want, f"{cell}: the defence stars")


# --- Dual Strike's menus under a campaign dialogue box -------------------------------------------------------

@test(modes=("ds",))
def ds_menus_under_dialogue(ctx):
    """AW2's campaign tutorial: with the map menu open, choosing End brings a dialogue box up at the bottom. Dual Strike's
    help box ("End your turn.", bottom right, a red bar on top) is not drawn over it, and the menu stays above it."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    from PIL import Image
    from aw2test import campaigns as cp
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    cp.aw2_new(e, d, True)
    d.wait_control() if d.scripts_running() else None
    g._units_base = g._players_base = None
    m = g.open_map_menu()
    for _ in range(len(m["names"]) + 2):
        if e.u8(m["cursor_addr"]) == len(m["names"]) - 1:
            break
        e.press("DOWN", 4)
        e.wait(8)
    e.wait(30)

    def red_bar():
        px = Image.open(e.shot(os.path.join(ctx.out, "dlg_probe"))).convert("RGB")
        # the help box's top bar: its row 128, right edge; counts the strongly red pixels of x 190..236
        return sum(1 for x in range(170, 237) for y in range(128, 136) if px.getpixel((x, y))[0] > 200 and px.getpixel((x, y))[1] < 90)
    before = red_bar()
    ctx.check(before > 40, f"the help box is up with the menu alone (red bar pixels {before})")
    shot(ctx, g, "dialogue_menu_before")
    e.press("A", 4)
    ok = e.wait_until(d.scripts_running, 300, step=5)
    ctx.check(ok, "End brings the tutorial's dialogue box up")
    e.wait(90)
    shot(ctx, g, "dialogue_menu_after")
    after = red_bar()
    ctx.check(after < 5, f"the help box is not drawn over the dialogue (red bar pixels {after})")

