"""Survival's screens in Dual Strike's look (survival_ui.rs): SELECT MAP with the
pack is Dual Strike's course screen fitted to the GBA (its title font, its
"BASIC COURSE" banner, its wording, the strip of the course's eleven maps, the
map under the cursor), the record page, the budget on the battle map; and the
lists of maps, order and budgets are Dual Strike's. Without the pack none of
it is there.

The picture is read back from VRAM (BG0, tiles and tilemap, palette RAM, as the
PPU reads them) and checked against what the .nds says: the title's pixels from
`ohashi/res_modefont`, the banner's from `ohashi/res_survival`, Dual Strike's
words from overlay 0, AW2's own font for the rest."""

import struct

from aw2test import paths, ram
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import Skip, test

LIST_CURSOR = 0x03005930
OAM = 0x07000000

# survival_ui.rs: the panel's rows, the strip, the map box.
ROW1, ROW2 = sv.PANEL_ROW1, sv.PANEL_ROW2
RIGHT = sv.VALUE_RIGHT
LABEL_X = sv.LABEL_X
BOX_X, BOX_Y = 84, 114
KIND_TITLES = {sv.MONEY: "MONEY*SURVIVAL", sv.TURN: "TURN*SURVIVAL", sv.TIME: "TIME*SURVIVAL"}
LABELS = {sv.MONEY: ("Funds", "Spent"), sv.TURN: ("Turn total", "Turns used"), sv.TIME: ("Total time", "Time used")}
LEFT_LABELS = {sv.MONEY: "Funds left", sv.TURN: "Turns left", sv.TIME: "Time left"}
BUDGET_TEXT = {sv.MONEY: "500000 G", sv.TURN: "99", sv.TIME: "25:00"}


def boot(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def need_pack(ctx):
    if not ctx.ds:
        raise Skip("the pack's screen")


def visible_sprites(e):
    """OAM entries that draw something: not disabled, on the screen."""
    oam = e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, 8 * i)
        if (a0 >> 8) & 3 == 2:
            continue
        if (a0 & 0xFF) >= 160 and (a0 & 0xFF) < 240:
            continue
        out.append(i)
    return out


def check_title(ctx, e, shot, kind, label):
    """The title in Dual Strike's title font: its blue pixels are exactly the
    font's, centred, at the top."""
    glyphs = sv.title_font()
    want = sv.title_blue(KIND_TITLES[kind], glyphs)
    got = sv.blue_pixels(shot, range(0, 32))
    ctx.check(want == got, f"{label}: the title {KIND_TITLES[kind]} is Dual Strike's font "
                           f"({len(want ^ got)} of {len(want)} blue pixels differ)")


def check_banner(ctx, shot, label):
    bx, by = sv.BANNER
    want = {(bx + x, by + y) for x, y in sv.banner_dark()}
    got = {(x, y) for y in range(by, by + 16) for x in range(bx, bx + 128) if sv.dark(shot[y][x])}
    ctx.check(want == got, f"{label}: the BASIC COURSE banner is Dual Strike's ({len(want ^ got)} of {len(want)} dark pixels differ)")


def check_course_panel(ctx, shot, kind, record_text=None, label=""):
    l1, l2 = LABELS[kind]
    ctx.check(sv.text_on(shot, "11", 16, ROW1), f"{label}: 11 ...")
    ctx.check(sv.text_on(shot, "Maps", 16 + sv.text_width("11") + 4, ROW1), f"{label}: ... Maps (Dual Strike's word)")
    ctx.check(sv.text_on(shot, l1, LABEL_X, ROW1), f"{label}: {l1}")
    ctx.check(sv.text_right(shot, BUDGET_TEXT[kind], RIGHT, ROW1), f"{label}: the budget {BUDGET_TEXT[kind]}")
    ctx.check(sv.text_on(shot, l2, LABEL_X, ROW2), f"{label}: {l2}")
    ctx.check(sv.text_right(shot, record_text or "----", RIGHT, ROW2), f"{label}: the best {record_text or '----'}")


@test(modes=("ds",))
def survival_wording_is_dual_strikes(ctx):
    """The words on the course panel are the ones in Dual Strike's overlay."""
    need_pack(ctx)
    w = sv.words()
    for t in ("Funds", "Spent", "Maps", "Total time", "Time used", "Turn total", "Turns used",
              "Funds left", "Turns left", "Time left", "Maps clrd."):
        ctx.check(t in w, f"Dual Strike says {t!r}")


@test(modes=("ds",))
def survival_select_map_look(ctx):
    """SELECT MAP is Dual Strike's course screen: the game's sprites are off, the
    title, banner, panel and strip are Dual Strike's, for each of the three
    courses."""
    need_pack(ctx)
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    for row, kind in enumerate(sv.LIST_ORDER):
        if row:
            e.press("DOWN", 8)
            e.wait(90)
        ctx.eq(e.u8(sv.SHOWN), 1, f"{sv.NAMES[kind]}: the picture is up")
        ctx.eq(visible_sprites(e), [], f"{sv.NAMES[kind]}: none of the game's sprites show")
        shot = sv.bg0(e)
        check_title(ctx, e, shot, kind, sv.NAMES[kind])
        check_banner(ctx, shot, sv.NAMES[kind])
        check_course_panel(ctx, shot, kind, label=sv.NAMES[kind])
        e.shot(f"{ctx.out}/select_{kind}")
    # B still leaves Survival: the game has the pad.
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: e.u8(sv.ON) == 0, 600, step=10), "B leaves Survival")


@test(modes=("ds",))
def survival_browse_the_maps(ctx):
    """LEFT and RIGHT walk the course's eleven maps (the game never sees them);
    the box shows the map's number and Dual Strike's name for it."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    cursor = e.u32(LIST_CURSOR)
    run = data.run(sv.MONEY)
    for stage in (1, 2, 3):
        e.press("RIGHT", 8)
        e.wait(6)
    ctx.eq(e.u8(sv.BROWSE), 3, "three RIGHTs: the fourth map")
    shot = sv.bg0(e)
    name = data.text(data.u16(sv.MAPS + 0xA0 * (run[3] - 1) + 0x2C))
    ctx.check(sv.text_on(shot, f"4. {name}", BOX_X + 8, BOX_Y + 3), f"the box says 4. {name}")
    e.shot(f"{ctx.out}/fourth_map")
    e.press("LEFT", 8)
    e.wait(6)
    e.press("LEFT", 8)
    e.wait(6)
    e.press("LEFT", 8)
    e.wait(6)
    e.press("LEFT", 8)
    e.wait(6)
    ctx.eq(e.u8(sv.BROWSE), 10, "LEFT from the first map: the eleventh")
    shot = sv.bg0(e)
    name = data.text(data.u16(sv.MAPS + 0xA0 * (run[10] - 1) + 0x2C))
    ctx.check(sv.text_on(shot, f"11. {name}", BOX_X + 8, BOX_Y + 3), f"the box says 11. {name}")
    ctx.eq(e.u32(LIST_CURSOR), cursor, "the game's list did not move")
    ctx.eq(e.u8(sv.ON), 1, "still in Survival")
    # Another course starts at its first map again.
    e.press("DOWN", 8)
    e.wait(90)
    ctx.eq(e.u8(sv.BROWSE), 0, "another course: its first map")


@test(modes=("ds",))
def survival_record_page(ctx):
    """R opens the record page (the game's own record view stays shut), B closes
    it without leaving Survival; a saved record shows what the course cost."""
    need_pack(ctx)
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    e.press("R", 8)
    e.wait(20)
    ctx.eq(e.u8(sv.RECORDS), 1, "R opens the record page")
    shot = sv.bg0(e)
    glyphs = sv.title_font()
    want = sv.title_blue("RECORD", glyphs)
    ctx.check(want == sv.blue_pixels(shot, range(0, 32)), "the page's title is RECORD in Dual Strike's font")
    for i, kind in enumerate(sv.LIST_ORDER):
        ctx.check(sv.text_on(shot, sv.NAMES[kind], 18, 74 + 18 * i), f"{sv.NAMES[kind]} is listed")
        ctx.check(sv.text_right(shot, "----", 222, 74 + 18 * i), f"{sv.NAMES[kind]}: nothing used yet")
    e.shot(f"{ctx.out}/records")
    e.press("B", 8)
    e.wait(20)
    ctx.eq(e.u8(sv.RECORDS), 0, "B closes it")
    ctx.eq(e.u8(sv.ON), 1, "and does not leave Survival")
    ctx.check(sv.running(e, sv.SELECT_MAP_PROC), "SELECT MAP still runs")
    shot = sv.bg0(e)
    check_title(ctx, e, shot, sv.MONEY, "back on the course page")


@test(modes=("ds",))
def survival_record_shown(ctx):
    """A cleared run's record: the course page shows what it used (Dual Strike's
    Spent, Turns used, Time used), the record page its rank and CO."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    ctx.require(sv.pick(e, 0), "Money Survival starts")
    g.wait_for_input()
    e.w8(sv.STAGE, 10)
    e.w32(0x020232C0, 123400)
    for a in range(2, 5):
        e.w8(0x020232C0 + 0x3C * (a - 1) + 0x31, 1)
    g.wait_for_input()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.require(sv.to_select_map(e), "back on SELECT MAP")
    ctx.eq(e.u8(sv.PHASE), sv.CLEARED, "the run is cleared")
    shot = sv.bg0(e)
    ctx.check(sv.text_on(shot, "Funds left", 18, 75), "the results say Funds left")
    ctx.check(sv.text_right(shot, "123400 G", 180, 75), "123400 G left")
    e.press("A", 8)
    e.wait(60)
    shot = sv.bg0(e)
    check_course_panel(ctx, shot, sv.MONEY, record_text="376600 G", label="Money Survival's record")
    e.press("R", 8)
    e.wait(20)
    shot = sv.bg0(e)
    ctx.check(sv.text_right(shot, "376600 G", 222, 74), "the record page: 376600 G used")
    ctx.check(sv.text_on(shot, "S", 108, 74), "the record page: rank S")
    e.shot(f"{ctx.out}/records_with_one")


@test(modes=("ds",))
def survival_between_and_results_pages(ctx):
    """Between maps the panel says Dual Strike's Maps clrd. and what is left
    (Funds left, Turns left, Time left); lost runs say GAME OVER in Dual Strike's
    title font."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    e.press("DOWN", 8)
    e.wait(90)
    e.press("DOWN", 8)
    e.wait(90)
    ctx.require(sv.pick(e, 0), "Time Survival starts")
    g.wait_for_input()
    for a in range(2, 5):
        e.w8(0x020232C0 + 0x3C * (a - 1) + 0x31, 1)
    g.wait_for_input()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.require(sv.to_select_map(e), "back on SELECT MAP")
    st = sv.state(e)
    ctx.eq(st["phase"], sv.BETWEEN, "map 2 next")
    shot = sv.bg0(e)
    check_title(ctx, e, shot, sv.TIME, "between maps")
    check_banner(ctx, shot, "between maps")
    ctx.check(sv.text_on(shot, "1", 16, ROW1) and sv.text_on(shot, "Maps clrd.", 16 + sv.text_width("1") + 4, ROW1),
              "1 Maps clrd.")
    ctx.check(sv.text_on(shot, "Time left", LABEL_X, ROW1), "Time left")
    ctx.check(sv.text_right(shot, sv.clock(st["left"]), RIGHT, ROW1), f"{sv.clock(st['left'])} left")
    ctx.check(sv.text_on(shot, "Points", LABEL_X, ROW2), "Points")
    ctx.eq(e.u8(sv.BROWSE), 1, "the box starts on the next map (2)")
    name = data.text(data.u16(sv.MAPS + 0xA0 * (data.run(sv.TIME)[1] - 1) + 0x2C))
    ctx.check(sv.text_on(shot, f"2. {name}", BOX_X + 8, BOX_Y + 3), f"the box says 2. {name}")
    e.shot(f"{ctx.out}/between")


@test(modes=("ds",))
def survival_lost_page(ctx):
    """A lost run: GAME OVER in the title font, Maps clrd. 0 / 11."""
    need_pack(ctx)
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    ctx.require(sv.pick(e, 0), "Money Survival starts")
    g.wait_for_input()
    e.w32(0x020232C0, 0)
    e.wait(80)
    g.wait_for_input()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.require(sv.to_select_map(e), "back on SELECT MAP")
    ctx.eq(e.u8(sv.PHASE), sv.LOST, "the run is lost")
    shot = sv.bg0(e)
    glyphs = sv.title_font()
    ctx.check(sv.title_blue("GAME*OVER", glyphs) == sv.blue_pixels(shot, range(0, 32)), "GAME OVER in Dual Strike's font")
    ctx.check(sv.text_on(shot, "Maps clrd.", 18, 60), "Maps clrd.")
    ctx.check(sv.text_right(shot, "0 / 11", 222, 60), "0 / 11")
    ctx.check(sv.text_on(shot, "Points", 18, 75), "Points")
    e.shot(f"{ctx.out}/lost")


@test(modes=("ds",))
def survival_budget_on_the_map(ctx):
    """The budget at the top of the battle map: the map's number and what is left,
    in Dual Strike's words, in AW2's font outlined (no glyph-sprite debug text)."""
    need_pack(ctx)
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    e.press("DOWN", 8)
    e.wait(90)
    e.press("DOWN", 8)
    e.wait(90)
    ctx.require(sv.pick(e, 0), "Time Survival starts")
    g.wait_for_input()
    e.wait(4)
    st = sv.state(e)
    left = st["left"] - st["time"]
    lines = sv.hud_white(e)
    ctx.eq(sorted(lines), [1, 13], "two lines at the top")
    ctx.eq(lines.get(1), sv.hud_expected("Map 1/11", 1), "line 1: Map 1/11")
    want = f"Time left {sv.clock(left)}"
    ctx.eq(lines.get(13), sv.hud_expected(want, 13), f"line 2: {want}")
    e.shot(f"{ctx.out}/hud_time")


@test(modes=("ds",))
def survival_budget_turn_and_money(ctx):
    """Turns left and Funds left in the same place, in Dual Strike's words."""
    need_pack(ctx)
    for row, kind, label, value in ((0, sv.MONEY, "Funds left", "500000 G"), (1, sv.TURN, "Turns left", "99")):
        e, g = boot(ctx)
        ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
        ctx.require(sv.pick(e, row), f"{sv.NAMES[kind]} starts")
        g.wait_for_input()
        e.wait(4)
        lines = sv.hud_white(e)
        ctx.eq(lines.get(1), sv.hud_expected("Map 1/11", 1), f"{sv.NAMES[kind]}: Map 1/11")
        ctx.eq(lines.get(13), sv.hud_expected(f"{label} {value}", 13), f"{sv.NAMES[kind]}: {label} {value}")
        e.shot(f"{ctx.out}/hud_{kind}")


@test(modes=("ds",))
def survival_lists_are_dual_strikes(ctx):
    """Each course is Dual Strike's: eleven maps, in its order, by its names, on its
    budget; the three together are its 33 (ids 0xBC..0xDC, none more) and the
    Champion courses add no maps (they use the same lists)."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    table = e.u32(0x080196EC)

    def name_of(map_id):
        h = table + 0x5C * map_id
        text = e.u32(0x08610A38 + 4 * e.u16(h + 0x14))
        return e.read(text, 40).split(b"\0")[0].decode()

    ids = set()
    for kind in (sv.MONEY, sv.TURN, sv.TIME):
        run = data.run(kind)
        ctx.eq(len(run), 11, f"{sv.NAMES[kind]}: eleven maps")
        ctx.eq(data.budget(kind), {sv.MONEY: 500000, sv.TURN: 99, sv.TIME: 90000}[kind], f"{sv.NAMES[kind]}: the budget")
        ours = [name_of(sv.MAPS_FROM + data.all_ids().index(i)) for i in run]
        theirs = [data.text(data.u16(sv.MAPS + 0xA0 * (i - 1) + 0x2C)) for i in run]
        ctx.eq(ours, theirs, f"{sv.NAMES[kind]}: the maps, in Dual Strike's order")
        ids |= set(run)
    ctx.eq(sorted(ids), list(range(0xBC, 0xDD)), "33 maps, 0xBC..0xDC")
    # The Champion courses (kinds 3..5) read the same three lists
    # (arm9 0x020EAC50's table, overlay 0x022F64CC/0x22F64E4/0x22F6544).
    for champion, base in ((3, 0x022F64E4), (4, 0x022F6544), (5, 0x022F64CC)):
        mine = [data.u16(base + 2 * k) for k in range(11)]
        ctx.check(mine in [data.run(k) for k in (sv.MONEY, sv.TURN, sv.TIME)], f"Champion course {champion - 2}: the basic course's maps")
    ctx.eq([struct.unpack_from("<I", data.arm9, sv.BUDGETS - 0x02000000 + 4 * k)[0] for k in (3, 4, 5)],
           [108000, 600000, 120], "the Champion budgets (not in tangoAW2: they are a shop unlock)")


@test(modes=("ds",))
def survival_screen_fits_every_map(ctx):
    """Every one of the 33 maps' pages is drawn whole: the picture's tiles fit
    BG0's 512 (with room) and the box names the map, on each course."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    worst = 0
    for row, kind in enumerate(sv.LIST_ORDER):
        if row:
            e.press("DOWN", 8)
            e.wait(90)
        run = data.run(kind)
        for n in range(11):
            if n:
                e.press("RIGHT", 8)
                e.wait(5)
            cnt = e.u16(sv.BG0CNT)
            smap = e.read(0x06000000 + 0x800 * ((cnt >> 8) & 31), 0x800)
            used = {struct.unpack_from("<H", smap, 2 * (32 * y + x))[0] & 0x3FF for y in range(20) for x in range(30)}
            worst = max(worst, len(used))
            name = data.text(data.u16(sv.MAPS + 0xA0 * (run[n] - 1) + 0x2C))
            shot = sv.bg0(e)
            ok = sv.text_on(shot, f"{n + 1}. {name}", BOX_X + 8, BOX_Y + 3)
            ctx.check(ok and len(used) <= 480, f"{sv.NAMES[kind]} map {n + 1} {name}: named, {len(used)} tiles")
    ctx.log(f"most tiles on a page: {worst} of 512")
