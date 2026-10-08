"""Survival's Champion courses (survival.rs, survival_ui.rs): Dual Strike's
endless courses on the same three lists of eleven maps, on a larger budget
(30:00, 600,000 G, 120 days), in its "CHAMPION COURSE" panel. Dual Strike
sells them in its shop once the basic course is cleared; tangoAW2 has no shop,
so a Champion course opens when its basic course has been cleared (a record of
it exists). A Champion run ends when the budget is out or a map is lost; its
record is the maps cleared, its rank goes by that count (S 20, A 15, B 10, else
C) and its bonus is 5 + 10 + .. + 5n. The record lives with the basic ones in
eleven bytes of the profile (0x0200C435..0x0200C43F). Without the pack none of
it is there (survival_hidden_without_pack in test_survival.py).

Everything here is checked against Dual Strike's .nds read directly: the
budgets (arm9 0x02168D04, kinds 3..5), the lists (overlay 0x022F64E4 and
neighbours), the rank and bonus (sub_020EAD98, sub_020EB024), the banner
(res_survival's blocks 4..7)."""

import os

from aw2test import paths, ram
from aw2test import survival as sv
from aw2test import saveimg, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import Skip, test

PLAYERS = 0x020232C0
P_FUNDS, P_YIELD = 0x00, 0x31
ROW1, ROW2 = sv.PANEL_ROW1, sv.PANEL_ROW2
RIGHT = sv.VALUE_RIGHT
LABEL_X = sv.LABEL_X
BOX_X, BOX_Y = 84, 114
TITLES = {sv.MONEY: "MONEY*SURVIVAL", sv.TURN: "TURN*SURVIVAL", sv.TIME: "TIME*SURVIVAL"}
LABELS = {sv.MONEY: "Funds", sv.TURN: "Turn total", sv.TIME: "Total time"}
LEFT_LABELS = {sv.MONEY: "Funds left", sv.TURN: "Turns left", sv.TIME: "Time left"}
BUDGET_TEXT = {sv.MONEY: "600000 G", sv.TURN: "120", sv.TIME: "30:00"}
# list rows: the three basic courses, then (once open) the Champion courses
ROWS = {(k, False): i for i, k in enumerate(sv.LIST_ORDER)}
ROWS.update({(k, True): 3 + i for i, k in enumerate(sv.LIST_ORDER)})
SURVIVAL_RECORDS = saves.c420(0x15, 11)


def player(army):
    return PLAYERS + 0x3C * (army - 1)


def need_pack(ctx):
    if not ctx.ds:
        raise Skip("the pack's mode")


def boot(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def open_with(ctx, basic=None, champion=None, v1=False, save=None):
    """Survival's SELECT MAP, with the records a past session left (written
    into the profile in RAM, as the game loaded them)."""
    e, g = boot(ctx, save)
    before = None
    if basic is not None or champion is not None:
        before = lambda e: sv.set_records(e, basic or {}, champion, v1=v1)
    ctx.require(sv.open_survival(e, before), "Survival's SELECT MAP")
    return e, g


def to_row(e, row):
    """The list's cursor on `row` (from the top)."""
    for _ in range(6):
        e.press("UP", 8)
        e.wait(10)
    for _ in range(row):
        e.press("DOWN", 8)
        e.wait(30)
    e.wait(60)


def start(ctx, e, kind, co_steps=0):
    to_row(e, ROWS[(kind, True)])
    ctx.require(sv.pick(e, 0, co_steps), f"{sv.CHAMPION_NAMES[kind]} starts")


def end_turn(g):
    g.wait_for_input()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)


def finish_map(ctx, e, g, armies):
    """Every computer army yields; ending the turn wins the map."""
    for a in range(2, armies + 1):
        e.w8(player(a) + P_YIELD, 1)
    end_turn(g)
    ctx.require(sv.to_select_map(e), "back on SELECT MAP")


def lose(ctx, e, g, kind):
    """Running out of the budget loses the run."""
    g.wait_for_input()
    if kind == sv.MONEY:
        e.w32(player(1) + P_FUNDS, 0)
    elif kind == sv.TURN:
        e.w32(sv.LEFT, 0)
    else:
        e.w32(sv.LEFT, e.u32(sv.FRAMES) + 60)
    e.wait(80)
    g.wait_for_input()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.require(sv.to_select_map(e), "back on SELECT MAP")
    ctx.eq(e.u8(sv.PHASE), sv.LOST, "the run is lost")


def banner_pixels(shot, champion, by=sv.BANNER[1]):
    bx = sv.BANNER[0]
    want = {(bx + x, by + y) for x, y in sv.banner_dark(champion=champion)}
    got = {(x, y) for y in range(by, by + 16) for x in range(bx, bx + 128) if sv.dark(shot[y][x])}
    return want, got


def text_gray(shot, s, x, y, need=0.97):
    """Caption text (survival_ui's GRAY_INK: grey on white)."""
    ink = sv.font_ink(s, x, y)
    got = sum(1 for (px, py) in ink if sum(shot[py][px]) < 560)
    return bool(ink) and got >= need * len(ink)


def blue_in(shot, x0, y0, x1, y1):
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if shot[y][x][2] - shot[y][x][0] >= 100)


# --- what Dual Strike has ----------------------------------------------------------


@test(modes=("ds",))
def survival_champion_is_dual_strikes(ctx):
    """The Champion courses as the .nds has them: the same lists, a larger
    budget each, rank and bonus by the maps cleared."""
    need_pack(ctx)
    data = sv.Survival()
    lists = {sv.TIME: 0x022F64E4, sv.MONEY: 0x022F6544, sv.TURN: 0x022F64CC}
    for kind, at in lists.items():
        ctx.eq([data.u16(at + 2 * k) for k in range(11)], data.run(kind), f"{sv.CHAMPION_NAMES[kind]}: the basic course's maps")
        ctx.eq(data.budget(kind, champion=True), sv.CHAMPION_BUDGETS[kind], f"{sv.CHAMPION_NAMES[kind]}: the budget")
    # sub_020EAD98 for kinds 3..5: S from 20, A from 15, B from 10 (0x14, 0xF, 0xA).
    arm9 = data.arm9
    base = 0x020EAE44 - 0x02000000
    import struct
    ins = [struct.unpack_from("<I", arm9, base + 4 * i)[0] for i in range(0, 12)]
    ctx.eq([ins[0] & 0xFFF, ins[3] & 0xFFF, ins[6] & 0xFFF], [0x14, 0xF, 0xA], "ranks S 20, A 15, B 10 (sub_020EAD98)")
    for n, want in ((0, 2), (9, 2), (10, 3), (14, 3), (15, 4), (19, 4), (20, 5), (50, 5)):
        ctx.eq(sv.champion_rank(n), want, f"{n} maps: rank {want}")
    # sub_020EB024: 5 + 10 + .. + 5n, capped at 9999 (0x270F in its pool).
    ctx.eq(struct.unpack_from("<I", arm9, 0x020EB0E8 - 0x02000000)[0], 9999, "the points cap")
    ctx.eq([sv.champion_bonus(n) for n in (0, 1, 2, 11, 255)], [0, 5, 15, 330, 9999], "the bonus")
    # The shop item Dual Strike unlocks them with: bought bits 0x2F..0x31 after
    # the basic course's clear bits 0x2C..0x2E (arm9 0x02101E6C..).
    for at, bought, cleared in ((0x02101EF4, 0x2F, 0x2C), (0x02101EB0, 0x30, 0x2D), (0x02101E6C, 0x31, 0x2E)):
        o = at - 0x02000000
        # mov r0, #bought ... mov r0, #cleared
        ctx.eq(struct.unpack_from("<I", arm9, o + 8)[0] & 0xFF, bought, f"the shop's bought bit {bought:#x}")
        ctx.eq(struct.unpack_from("<I", arm9, o + 0x24)[0] & 0xFF, cleared, f"... offered once bit {cleared:#x} (basic cleared) is set")


# --- locked, then open --------------------------------------------------------------


@test(modes=("ds",))
def survival_champion_locked_at_first(ctx):
    """Before any basic course is cleared SELECT MAP lists the three basic
    courses only, and DOWN stops at the third."""
    need_pack(ctx)
    e, g = open_with(ctx)
    ctx.eq(sv.listed(e), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER], "Money, Turn and Time Survival listed")
    for _ in range(5):
        e.press("DOWN", 8)
        e.wait(30)
    ctx.eq(sv.listed(e), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER], "still the three")
    e.wait(60)
    shot = sv.bg0(e)
    ctx.check(sv.text_on(shot, "Time used", LABEL_X, ROW2), "the cursor is on Time Survival: its basic panel")
    got, want = banner_pixels(shot, False)[1], banner_pixels(shot, False)[0]
    ctx.check(want == got, "BASIC COURSE banner")
    ctx.eq(sv.champion_records(e), {}, "no Champion record")


@test(modes=("ds",))
def survival_champion_opens_with_the_basic_clear(ctx):
    """Clearing Money Survival's basic course opens Money Champion (not the
    others): the list gains it after the three basic ones, in the same
    boot."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = open_with(ctx)
    ctx.require(sv.pick(e, 0), "Money Survival starts")
    g.wait_for_input()
    e.w8(sv.STAGE, 10)
    e.w32(player(1) + P_FUNDS, 123400)
    finish_map(ctx, e, g, data.map(data.run(sv.MONEY)[0])["armies"])
    ctx.eq(e.u8(sv.PHASE), sv.CLEARED, "the basic course is cleared")
    e.press("A", 8)
    e.wait(40)
    ctx.eq(sv.listed(e), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER] + [sv.CHAMPION_IDS[sv.MONEY]],
           "Money Champion is listed after the basic courses (Turn's and Time's are not)")
    ctx.eq(sv.champion_records(e), {}, "nothing played on it yet")
    to_row(e, 3)
    shot = sv.bg0(e)
    want, got = banner_pixels(shot, True)
    ctx.check(want == got, f"Money Champion: the CHAMPION COURSE banner ({len(want ^ got)} pixels differ)")
    e.shot(f"{ctx.out}/opened")


# --- the course screen --------------------------------------------------------------


def check_panel(ctx, shot, kind, record_text=None, label=""):
    ctx.check(sv.text_on(shot, "Infinite", 16, ROW1), f"{label}: Infinite (Dual Strike's word for the maps)")
    ctx.check(sv.text_on(shot, LABELS[kind], LABEL_X, ROW1), f"{label}: {LABELS[kind]}")
    ctx.check(sv.text_right(shot, BUDGET_TEXT[kind], RIGHT, ROW1), f"{label}: the budget {BUDGET_TEXT[kind]}")
    ctx.check(sv.text_on(shot, "Maps clrd.", LABEL_X, ROW2), f"{label}: Maps clrd.")
    if record_text is None:
        ctx.check(sv.text_right(shot, "----", RIGHT, ROW2), f"{label}: no best yet")
    else:
        ctx.check(sv.text_right(shot, record_text, RIGHT - 15, ROW2), f"{label}: the best {record_text}")


@test(modes=("ds",))
def survival_champion_course_screen(ctx):
    """The Champion course's panel as Dual Strike has it, for each kind: its
    title, the CHAMPION COURSE banner, Infinite, the larger budget, Maps
    clrd. and ---- before a run."""
    need_pack(ctx)
    e, g = open_with(ctx, basic={sv.MONEY: (1, 100000), sv.TURN: (2, 20), sv.TIME: (3, 600)})
    glyphs = sv.title_font()
    for kind in sv.LIST_ORDER:
        to_row(e, ROWS[(kind, True)])
        ctx.eq(e.u8(sv.SHOWN), 1, f"{sv.CHAMPION_NAMES[kind]}: the picture is up")
        shot = sv.bg0(e)
        want = sv.title_blue(TITLES[kind], glyphs)
        ctx.check(want == sv.blue_pixels(shot, range(0, 32)), f"{sv.CHAMPION_NAMES[kind]}: the title {TITLES[kind]}")
        a, b = banner_pixels(shot, True)
        ctx.check(a == b, f"{sv.CHAMPION_NAMES[kind]}: CHAMPION COURSE banner ({len(a ^ b)} pixels differ)")
        check_panel(ctx, shot, kind, label=sv.CHAMPION_NAMES[kind])
        e.shot(f"{ctx.out}/champion_{kind}")
    # B still leaves Survival.
    e.press("B", 8)
    ctx.require(e.wait_until(lambda: e.u8(sv.ON) == 0, 600, step=10), "B leaves Survival")


@test(modes=("ds",))
def survival_champion_course_screen_with_a_best(ctx):
    """A best run of 14 maps: Maps clrd. shows 14 Maps with its rank in a box
    (B: 10 to 14); the strip shows the first round's maps dark."""
    need_pack(ctx)
    e, g = open_with(ctx, basic={sv.MONEY: (1, 100000)}, champion={sv.MONEY: 14})
    to_row(e, 3)
    shot = sv.bg0(e)
    check_panel(ctx, shot, sv.MONEY, record_text="14 Maps", label="Money Champion with a best of 14")
    ctx.check(blue_in(shot, 213, 64, 224, 76) >= 100, "the rank's box")
    ctx.eq(sv.champion_records(e), {sv.MONEY: 14}, "the record in the profile")
    e.shot(f"{ctx.out}/champion_best")
    # Turn's course is still locked and its Champion not listed.
    ctx.eq(sv.listed(e), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER] + [sv.CHAMPION_IDS[sv.MONEY]], "only Money's is open")


@test(modes=("ds",))
def survival_champion_record_page(ctx):
    """R lists the six courses: the three basic ones, then the Champion ones
    with their best, Locked until their basic course is cleared."""
    need_pack(ctx)
    e, g = open_with(ctx, basic={sv.MONEY: (1, 100000)}, champion={sv.MONEY: 22})
    e.press("R", 8)
    e.wait(20)
    ctx.eq(e.u8(sv.RECORDS), 1, "R opens the record page")
    shot = sv.bg0(e)
    names = [sv.NAMES[k] for k in sv.LIST_ORDER] + [sv.CHAMPION_NAMES[k] for k in sv.LIST_ORDER]
    for i, name in enumerate(names):
        ctx.check(sv.text_on(shot, name, 18, 70 + 12 * i), f"{name} is listed")
    ctx.check(sv.text_right(shot, "22 Maps", 222, 70 + 12 * 3), "Money Champion: 22 Maps")
    ctx.check(sv.text_on(shot, "S", 108, 70 + 12 * 3), "Money Champion: rank S (20 or more)")
    ctx.check(sv.text_right(shot, "Locked", 222, 70 + 12 * 4), "Turn Champion: Locked")
    ctx.check(sv.text_right(shot, "Locked", 222, 70 + 12 * 5), "Time Champion: Locked")
    e.shot(f"{ctx.out}/champion_records")
    e.press("B", 8)
    e.wait(20)
    ctx.eq(e.u8(sv.RECORDS), 0, "B closes it")


# --- playing them ----------------------------------------------------------------------


def _budget(kind):
    def fn(ctx):
        """Each Champion course starts on its kind's first map with Dual
        Strike's larger budget (30:00, 600,000 G, 120 days), shown at the top
        of the map ("Map 1", no last map)."""
        need_pack(ctx)
        data = sv.Survival()
        e, g = open_with(ctx, basic={kind: (1, sv.UNIT[kind] * 3)})
        start(ctx, e, kind)
        st = sv.state(e)
        ctx.eq((st["kind"], st["champion"], st["stage"], st["phase"]), (kind, 1, 0, sv.PLAYING), "a Champion run")
        ctx.eq(st["left"], sv.CHAMPION_BUDGETS[kind], "the Champion budget")
        ctx.eq(st["left"], data.budget(kind, champion=True), "... Dual Strike's")
        ctx.eq(e.u8(ram.VS_MAP), sv.CHAMPION_IDS[kind], "the Champion entry")
        g.wait_for_input()
        if kind == sv.MONEY:
            ctx.eq(e.u32(player(1) + P_FUNDS), 600000, "Money: the funds are the budget")
            ctx.eq(e.u32(ram.FUNDS_PER_PROPERTY), 0, "Money: no income")
        e.wait(4)
        now = sv.state(e)
        value = {sv.MONEY: "600000 G", sv.TURN: "120", sv.TIME: sv.clock(now["left"] - now["time"])}[kind]
        if kind == sv.TIME:
            ctx.check(108000 - 900 <= now["left"] - now["time"] <= 108000, f"Time: a few seconds into 30:00 ({value})")
        lines = sv.hud_white(e)
        ctx.eq(sorted(lines), [1, 13], "two lines at the top")
        ctx.eq(lines.get(1), sv.hud_expected("Map 1", 1), "line 1: Map 1")
        ctx.eq(lines.get(13), sv.hud_expected(f"{LEFT_LABELS[kind]} {value}", 13), f"line 2: {LEFT_LABELS[kind]} {value}")
        e.shot(f"{ctx.out}/hud_{kind}")
    fn.__name__ = "survival_champion_budget_" + sv.NAMES[kind].split()[0].lower()
    test(modes=("ds",))(fn)


for _k in (sv.MONEY, sv.TURN, sv.TIME):
    _budget(_k)


@test(modes=("ds",))
def survival_champion_goes_round_again(ctx):
    """The eleventh map cleared does not end a Champion run: the list starts
    over (map 12 is the first again, in wave 2), the budget carried on."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = open_with(ctx, basic={sv.TURN: (1, 10)})
    start(ctx, e, sv.TURN)
    g.wait_for_input()
    armies = data.map(data.run(sv.TURN)[0])["armies"]
    e.w8(sv.STAGE, 10)            # the run is on its eleventh map
    finish_map(ctx, e, g, armies)
    st = sv.state(e)
    ctx.eq((st["phase"], st["stage"]), (sv.BETWEEN, 11), "map 12 next, the run goes on (not cleared)")
    ctx.eq(st["left"], 120 - (e.u16(sv.DAY) - 1), "the day the map was won on, less one, is spent")
    ctx.eq(sv.listed(e), [data.map_id(sv.TURN, 11, champion=True)], "only map 12 is listed")
    ctx.eq(data.map_id(sv.TURN, 11, champion=True), sv.MAPS_FROM + data.all_ids().index(data.run(sv.TURN)[0]),
           "... the course's first map again")
    shot = sv.bg0(e)
    ctx.check(sv.text_on(shot, "11", 16, ROW1) and sv.text_on(shot, "Maps clrd.", 16 + sv.text_width("11") + 4, ROW1),
              "11 Maps clrd.")
    ctx.check(sv.text_on(shot, "Wave 2", 16, ROW2), "Wave 2")
    ctx.check(sv.text_on(shot, "Turns left", LABEL_X, ROW1), "Turns left")
    ctx.eq(e.u8(sv.BROWSE), 0, "the strip is the new round's: map 1")
    got, want = banner_pixels(shot, True)[1], banner_pixels(shot, True)[0]
    ctx.check(want == got, "the CHAMPION COURSE banner between maps")
    e.shot(f"{ctx.out}/round_again")
    ctx.require(sv.pick(e, 0), "map 12 starts")
    g.wait_for_input()
    ctx.eq(e.u8(ram.VS_MAP), data.map_id(sv.TURN, 11, champion=True), "the first map of the course again")
    e.wait(4)
    lines = sv.hud_white(e)
    ctx.eq(lines.get(1), sv.hud_expected("Map 12", 1), "line 1: Map 12")
    # And once more round: map 13 is the second.
    e.w8(sv.STAGE, 11)
    finish_map(ctx, e, g, data.map(data.run(sv.TURN)[0])["armies"])
    ctx.eq(sv.listed(e), [data.map_id(sv.TURN, 12, champion=True)], "map 13")
    ctx.eq(data.map_id(sv.TURN, 12, champion=True), sv.MAPS_FROM + data.all_ids().index(data.run(sv.TURN)[1]), "... the second map")


def _lose_at(kind, stage_before_loss):
    """A Champion run lost with `stage_before_loss` maps cleared: back on
    SELECT MAP with the results."""
    def go(ctx, e, g):
        start(ctx, e, kind)
        g.wait_for_input()
        e.w8(sv.STAGE, stage_before_loss)
        lose(ctx, e, g, kind)
    return go


@test(modes=("ds",))
def survival_champion_records_and_results(ctx):
    """Lost with 7 maps cleared: GAME OVER with the maps cleared, the bonus
    5 + 10 + .. + 35 = 140, rank C; the record is 7. A better run (12:
    rank B) replaces it, a worse one (5) does not; the basic records are
    untouched."""
    need_pack(ctx)
    basic = {sv.MONEY: (9, 123400)}
    e, g = open_with(ctx, basic=basic)
    kind = sv.MONEY
    _lose_at(kind, 7)(ctx, e, g)
    st = sv.state(e)
    ctx.eq((st["bonus"], st["rank"]), (sv.champion_bonus(7), 2), "bonus 140, rank C")
    ctx.eq(sv.champion_records(e), {kind: 7}, "the record: 7 maps")
    ctx.eq(sv.records(e), {sv.MONEY: (5, 9, 123400)}, "the basic record is as it was")
    shot = sv.bg0(e)
    ctx.check(sv.title_blue("GAME*OVER", sv.title_font()) == sv.blue_pixels(shot, range(0, 32)), "GAME OVER in Dual Strike's font")
    a, b = banner_pixels(shot, True, by=39)
    ctx.check(a == b, "the CHAMPION COURSE banner on the results")
    ctx.check(sv.text_on(shot, "Maps clrd.", 18, 60), "Maps clrd.")
    ctx.check(sv.text_right(shot, "7", 180, 60), "7 (no 'of')")
    ctx.check(sv.text_on(shot, "Bonus", 18, 75), "Bonus")
    ctx.check(sv.text_right(shot, "140", 180, 75), "140")
    ctx.check(sv.text_on(shot, "Points", 18, 90), "Points")
    ctx.check(text_gray(shot, "Money Champion", 18, 129), "the course's name")
    ctx.check(blue_in(shot, 190, 76, 232, 110) > 40, "the rank in the title font")
    e.shot(f"{ctx.out}/champion_lost")
    e.press("A", 8)
    e.wait(40)
    ctx.eq(sv.state(e)["phase"], sv.CHOOSING, "A closes the results")
    # The course screen now says 7 Maps (rank C).
    to_row(e, 3)
    shot = sv.bg0(e)
    check_panel(ctx, shot, kind, record_text="7 Maps", label="after 7 maps")
    # A better run.
    _lose_at(kind, 12)(ctx, e, g)
    st = sv.state(e)
    ctx.eq((st["bonus"], st["rank"]), (sv.champion_bonus(12), 3), "12 maps: rank B")
    ctx.eq(sv.champion_records(e), {kind: 12}, "the record is now 12")
    e.press("A", 8)
    e.wait(40)
    # A worse one.
    _lose_at(kind, 5)(ctx, e, g)
    ctx.eq(sv.champion_records(e), {kind: 12}, "5 maps do not replace 12")
    ctx.eq(sv.state(e)["rank"], 2, "that run's own rank is C")
    ctx.eq(sv.records(e), {sv.MONEY: (5, 9, 123400)}, "the basic record is as it was")


@test(modes=("ds",))
def survival_champion_run_out_of_budget(ctx):
    """The budget runs out as on a basic course: the army yields and the run
    is over, whatever the number of maps (Turn: the day passes what is left,
    Time: the player's own clock does)."""
    need_pack(ctx)
    for kind in (sv.TURN, sv.TIME):
        e, g = open_with(ctx, basic={kind: (1, sv.UNIT[kind] * 2)})
        start(ctx, e, kind)
        g.wait_for_input()
        if kind == sv.TURN:
            e.w32(sv.LEFT, 0)
        else:
            e.w32(sv.LEFT, e.u32(sv.FRAMES) + 60)
        e.wait(80)
        ctx.eq(e.u8(player(1) + P_YIELD), 1, f"{sv.CHAMPION_NAMES[kind]}: out of budget, the army yields")
        end_turn(g)
        ctx.require(sv.to_select_map(e), "back on SELECT MAP")
        ctx.eq(e.u8(sv.PHASE), sv.LOST, f"{sv.CHAMPION_NAMES[kind]}: lost")
        ctx.eq(sv.champion_records(e), {}, "no map cleared: no record (a record needs one)")


# --- the save ------------------------------------------------------------------------------


@test(modes=("ds",))
def survival_champion_saved_and_after_reboot(ctx):
    """A real basic clear, then a Champion run lost at 12 maps: both are in
    the profile as saved (the eleven bytes, nothing else of Survival's
    changed), and after a reboot the course is open with its best."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = open_with(ctx)
    before = saves.flash(e, os.path.join(ctx.out, "before"))
    ctx.require(sv.pick(e, 0), "Money Survival starts")
    g.wait_for_input()
    e.w8(sv.STAGE, 10)
    e.w32(player(1) + P_FUNDS, 123400)
    finish_map(ctx, e, g, data.map(data.run(sv.MONEY)[0])["armies"])
    ctx.eq(e.u8(sv.PHASE), sv.CLEARED, "the basic course is cleared")
    co = sv.state(e)["co"]
    e.press("A", 8)
    e.wait(40)
    mid = saves.flash(e, os.path.join(ctx.out, "basic"))
    rec = mid.slot(0)[SURVIVAL_RECORDS[0]:SURVIVAL_RECORDS[1]]
    ctx.eq(rec[0], sv.RECORD_MAGIC, "the records' mark")
    ctx.eq(sv.decode_records(rec), ({sv.MONEY: (5, co, 123400)}, {}), "the basic clear, saved")
    _lose_at(sv.MONEY, 12)(ctx, e, g)
    e.press("A", 8)
    e.wait(40)
    after = saves.flash(e, os.path.join(ctx.out, "champion"))
    rec = after.slot(0)[SURVIVAL_RECORDS[0]:SURVIVAL_RECORDS[1]]
    ctx.eq(sv.decode_records(rec), ({sv.MONEY: (5, co, 123400)}, {sv.MONEY: 12}), "both records, saved")
    # Only the record's eleven bytes (and the usual save bookkeeping) differ
    # from the save after the basic clear.
    saves.expect_slots(ctx, mid, after, [], "the Champion run, saved",
                       profile_allow=[SURVIVAL_RECORDS] + [saves.c420(0x00, 4), saves.c420(0x04, 4)] + list(saves.OPTIONS) + [saves.MODE_BYTE])
    e.close()
    e2, g2 = boot(ctx, after.path)
    ctx.require(sv.open_survival(e2), "Survival after a reboot")
    ctx.eq(sv.records(e2).get(sv.MONEY), (5, co, 123400), "the basic record after a reboot")
    ctx.eq(sv.champion_records(e2), {sv.MONEY: 12}, "the Champion record after a reboot")
    ctx.eq(sv.listed(e2), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER] + [sv.CHAMPION_IDS[sv.MONEY]], "Money Champion is open")
    to_row(e2, 3)
    shot = sv.bg0(e2)
    check_panel(ctx, shot, sv.MONEY, record_text="12 Maps", label="after a reboot")
    e2.shot(f"{ctx.out}/champion_after_reboot")


@test(modes=("ds",))
def survival_champion_over_the_first_layout(ctx):
    """A save from 0.5.0..0.5.2 (records as three bytes a kind, mark 0xD5) is
    read as ever, opens the Champion courses of the kinds it has, and is
    rewritten in the new layout when a Champion record is saved, the basic
    records as they were."""
    need_pack(ctx)
    basic = {sv.TIME: (73, 600 * 60 // 60 * 60), sv.MONEY: (9, 345600), sv.TURN: (127, 31)}
    e, g = open_with(ctx, basic=basic, v1=True)
    raw = e.read(sv.PROFILE_RECORDS, 11)
    ctx.eq(raw[0], sv.RECORD_MAGIC_V1, "the first layout is in the profile")
    want = {k: (sv.rank(k, left), co, left) for k, (co, left) in basic.items()}
    ctx.eq(sv.records(e), want, "its records read")
    ctx.eq(sv.listed(e), [sv.ENTRY_IDS[k] for k in sv.LIST_ORDER] + [sv.CHAMPION_IDS[k] for k in sv.LIST_ORDER],
           "all three Champion courses are open")
    shot = sv.bg0(e)
    ctx.check(sv.text_on(shot, "Spent", LABEL_X, ROW2), "Money Survival's panel")
    ctx.check(sv.text_right(shot, "154400 G", RIGHT, ROW2), "... what its record used (500,000 - 345,600)")
    _lose_at(sv.TURN, 4)(ctx, e, g)
    e.press("A", 8)
    e.wait(40)
    now = e.read(sv.PROFILE_RECORDS, 11)
    ctx.eq(now[0], sv.RECORD_MAGIC, "the new layout now")
    ctx.eq(sv.decode_records(now), (want, {sv.TURN: 4}), "the basic records as they were, the Champion one added")


@test(modes=("ds",))
def survival_record_bytes_stay_in_their_eleven(ctx):
    """The records never write outside 0x0200C435..0x0200C43F in the profile's
    options block: the byte before and the bytes after are as they were."""
    need_pack(ctx)
    e, g = open_with(ctx, basic={sv.MONEY: (1, 100000)})
    around = e.read(0x0200C420, 0x40)
    _lose_at(sv.MONEY, 3)(ctx, e, g)
    e.press("A", 8)
    e.wait(40)
    now = e.read(0x0200C420, 0x40)
    lo, hi = sv.PROFILE_RECORDS - 0x0200C420, sv.PROFILE_RECORDS - 0x0200C420 + 11
    same = [i for i in range(0x40) if not lo <= i < hi and around[i] != now[i]]
    # the game's own counters in the block (points, save count, marks) may move
    ctx.check(all(i < 0x15 or i >= 0x20 for i in same), f"only the record's bytes in 0x15..0x1F changed ({same})")
    ctx.eq(sv.champion_records(e), {sv.MONEY: 3}, "the record")


@test(modes=("ds",))
def survival_champion_screen_fits_every_map(ctx):
    """Every Champion course's page, on each of its eleven maps, fits BG0's 512
    tiles with room (the picture shares equal tiles) and names the map; so do
    the record page with all six courses and a Champion results page."""
    need_pack(ctx)
    data = sv.Survival()
    e, g = open_with(ctx, basic={sv.MONEY: (1, 100000), sv.TURN: (2, 20), sv.TIME: (3, 600)},
                     champion={sv.MONEY: 22, sv.TURN: 12, sv.TIME: 7})
    worst = 0

    def tiles():
        cnt = e.u16(sv.BG0CNT)
        smap = e.read(0x06000000 + 0x800 * ((cnt >> 8) & 31), 0x800)
        import struct
        return len({struct.unpack_from("<H", smap, 2 * (32 * y + x))[0] & 0x3FF for y in range(20) for x in range(30)})
    for kind in sv.LIST_ORDER:
        to_row(e, ROWS[(kind, True)])
        run = data.run(kind)
        for n in range(11):
            if n:
                e.press("RIGHT", 8)
                e.wait(5)
            used = tiles()
            worst = max(worst, used)
            name = data.text(data.u16(sv.MAPS + 0xA0 * (run[n] - 1) + 0x2C))
            ok = sv.text_on(sv.bg0(e), f"{n + 1}. {name}", BOX_X + 8, BOX_Y + 3)
            ctx.check(ok and used <= 480, f"{sv.CHAMPION_NAMES[kind]} map {n + 1} {name}: named, {used} tiles")
    e.press("R", 8)
    e.wait(20)
    used = tiles()
    worst = max(worst, used)
    ctx.check(used <= 480, f"the record page: {used} tiles")
    ctx.log(f"most tiles on a page: {worst} of 512")
