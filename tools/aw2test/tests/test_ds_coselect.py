"""Dual Strike's CO selection screens (`ds_coselect.rs`), with the pack and "Dual Strike map graphics" (development byte
0x0203E3FE) on: Versus' Teams screen (an army card for each army, up to five, with its emblem, portraits and P1 / CPU tab),
the CO screen of the campaigns (army cards over the grid of faces) and of the War Room. The screens are drawn over the
finished frame from the game's state, so what the game does is untouched: the tests check the pictures against Dual
Strike's own art (the `ds_coselect_preview` example draws the same art from the .nds alone, the emblems are compared
pixel for pixel), that five armies fit, and that picking sets the same COs and partners with the setting on and off."""

import os
import subprocess

from aw2test import dscampaign as dc
from aw2test import paths, ram, saves, shots, tag, warroom
from aw2test import rom as romlib
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test

DS_GRAPHICS = 0x0203E3FE
# These tests switch the setting by its byte, so the run's TANGOAW2_DS_GRAPHICS must not force it on.
BYTE_DRIVEN = {"TANGOAW2_DS_GRAPHICS": "0"}
SELECT_MODE_CURSOR = 0x0300591C
VERSUS = 3
MAP_TAB = 0x0300596C
TAB_5P = 9
KEY_ARMY_COLOURS = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}

CARD_Y = 66   # ds_coselect::CARD_Y
TAB_Y = 32    # ds_coselect::TAB_Y


def card_x(n, i):
    gap = 8 if n <= 4 else 0
    total = 48 * n + gap * (n - 1)
    return (240 - total) // 2 + i * (48 + gap)


def reference(ctx):
    """The preview's pictures, drawn from the .nds alone."""
    out = os.path.join(ctx.out, "ref")
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, TANGOAW2_DS_ROM=paths.ds_rom())
    subprocess.run([paths.runner("ds_coselect_preview"), out], env=env, check=True, capture_output=True)
    return out


def emblem(rows, n, i):
    """An army card's emblem (the header's middle two tiles: 16 x 16)."""
    return shots.crop(rows, card_x(n, i) + 16, CARD_Y, 16, 16)


def ref_emblems(ctx):
    rows = shots.read_ppm(os.path.join(reference(ctx), "versus5_plain.ppm"))
    return [emblem(rows, 5, k) for k in range(5)]


def shot(ctx, e, name):
    return shots.read_bmp(e.shot(os.path.join(ctx.out, name)))


def wheel(e, pos):
    for _ in range(10):
        if e.u8(SELECT_MODE_CURSOR) == pos:
            return
        e.press("UP", 8)
        e.wait(60)
    raise NavError(f"Select Mode cursor stuck at {e.u8(SELECT_MODE_CURSOR)}")


def to_five_army_teams(ctx, g):
    e = g.e
    sv.to_select_mode(e)
    wheel(e, VERSUS)
    e.press("A", 8)
    e.wait(150)
    e.press("A", 8)
    e.wait(150)
    saves.show_all_lists(e)
    if not g.press_until("LEFT", lambda: e.u8(MAP_TAB) == TAB_5P, tries=14, hold=8, settle=50):
        raise NavError(f"tab {TAB_5P} not reached ({e.u8(MAP_TAB)})")
    e.wait(30)
    e.press("A", 8)
    ctx.require(e.wait_until(g.on_teams, 400, step=10), "the Teams screen")
    e.wait(60)


def differs(a, b, need=0.2):
    n = shots.diff_count(a, b, tol=4)
    return n >= need * 240 * 160


def blue_title_pixels(rows):
    """The title's glyphs are Dual Strike's blue gradient (no red, a lot of blue) in the top rows."""
    return sum(1 for r in rows[:32] for (R, G, B) in r if B > 180 and R < 90 and G < 140)


@test(modes=("ds",))
def ds_coselect_versus_two_armies(ctx):
    """The Teams screen with two armies: the title, a card for each army with its emblem (the army's colour as the Teams
    record has it: pixel for pixel Dual Strike's), the tab above it (P1, CPU), and the portraits; the setting off leaves
    AW2's own screen."""
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    e = g.e
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    off = shot(ctx, e, "versus2_off")
    e.w8(DS_GRAPHICS, 1)
    for _ in range(2):  # the first army's tab (RIGHT: its partner cell, the next army's CO and partner): the cursor leaves the cards' headers clear
        e.press("RIGHT", 6)
        e.wait(30)
    on = shot(ctx, e, "versus2_on")
    ctx.check(differs(off, on), "the screen is Dual Strike's with the setting on")
    ctx.check(blue_title_pixels(on) > 400 > blue_title_pixels(off), "NORMAL BATTLE's blue title is on it (and not on AW2's)")
    refs = ref_emblems(ctx)
    colours = list(e.read(ram.TEAMS + ram.T_COLOURS, 2))
    for i, c in enumerate(colours):
        ctx.eq(shots.diff_count(emblem(on, 2, i), refs[c - 1], tol=2), 0, f"army {i + 1}'s emblem is {KEY_ARMY_COLOURS[c]}'s")
    # R and L change an army's colour: its card follows, every country's emblem in turn (Blue Moon is the other army's).
    # (one press in a cycle puts the army's skin on, which draws the skin's own emblem: army_skin::teams_step)
    seen = set()
    prev = e.u8(ram.TEAMS + ram.T_COLOURS)
    for _ in range(6):
        e.press("R", 6)
        e.wait(20)
        c = e.u8(ram.TEAMS + ram.T_COLOURS)
        seen.add(c)
        rows = shot(ctx, e, f"versus2_colour{c}")
        if not (prev == 5 and c == 1):   # (after Black Hole comes the skin, on the first free colour)
            ctx.eq(shots.diff_count(emblem(rows, 2, 0), refs[c - 1], tol=2), 0, f"army 1 as {KEY_ARMY_COLOURS[c]}: its emblem")
        prev = c
    ctx.eq(sorted(seen), [1, 3, 4, 5], "R went through the countries the other army has not, Black Hole included")
    # With the setting off again the console runs on as before.
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    again = shot(ctx, e, "versus2_off_again")
    ctx.check(differs(again, on, 0.2), "with the setting off the Dual Strike screen is gone")


@test(modes=("ds",))
def ds_coselect_versus_five_armies(ctx):
    """Five armies: five cards of 48 pixels fill the screen's 240, each its army's emblem (Black Hole the fifth: its grey
    box), the tabs above them."""
    e = Emu(save=paths.base_save(), ds=True, env=BYTE_DRIVEN)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    to_five_army_teams(ctx, g)
    ctx.eq(g.teams()["armies"], 5, "armies on the Teams screen")
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    shot(ctx, e, "versus5_off")
    e.w8(DS_GRAPHICS, 1)
    for _ in range(2):  # the first army's tab (three cells an army: CO, partner, tab; the cursor stands clear of the cards' headers on the third)
        e.press("RIGHT", 6)
        e.wait(30)
    on = shot(ctx, e, "versus5")
    refs = ref_emblems(ctx)
    colours = list(e.read(ram.TEAMS_FIVE + 0x98, 5))
    ctx.eq(colours, [1, 2, 3, 4, 5], "the five armies' colours: Black Hole the fifth")
    for i, c in enumerate(colours):
        ctx.eq(shots.diff_count(emblem(on, 5, i), refs[c - 1], tol=2), 0, f"army {i + 1}: {KEY_ARMY_COLOURS[c]}'s emblem")
    ctx.eq(card_x(5, 0), 0, "the first card starts at the screen's left edge")
    ctx.eq(card_x(5, 4) + 48, 240, "the fifth ends at its right edge")
    # (the cards' foot lines, one army's colour each, run edge to edge)
    foot = on[CARD_Y + 64 + 3]
    ctx.check(len({tuple(p) for p in foot[:48]}) == 1 and len({tuple(p) for p in foot[192:240]}) == 1, "the first and fifth cards' foot lines are whole")
    ctx.check(foot[0] != foot[200], "each army's card has its own colour")


def pick_partners(ctx, on):
    """Boot the Teams screen, set the pairs with the pad (START on a CO stop, DOWN through the COs, START), return what the
    game holds."""
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    e = g.e
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(10)
    for army in range(2):
        e.press("START", 6)
        e.wait(20)
        for _ in range(2 + army):
            e.press("DOWN", 6)
            e.wait(20)
        if army == 0:
            shot(ctx, e, "partner_pick" if on else "partner_pick_off")
        e.press("START", 6)
        e.wait(20)
        if army == 0:
            # (with the setting on the cursor has three cells an army, CO, partner and the P1 / CPU tab: the Teams record is the game's
            # either way, the pad walks to the next army's CO with one more press)
            for _ in range(3 if on else 2):
                e.press("RIGHT", 6)
                e.wait(14)
    for _ in range(3):
        e.press("DOWN", 6)
        e.wait(20)
    return g.teams(), list(e.read(tag.TEAMS_PARTNER, 5)), list(e.read(ram.TEAMS + ram.T_CONTROLLERS, 4))


@test(modes=("ds",))
def ds_coselect_partner_picks_are_the_games(ctx):
    """The same pad presses pick the same COs and partners with the setting on and off (the screen is drawn over the
    game's, never changes it); the partner pick shows its cell under the cursor."""
    off = pick_partners(ctx, False)
    on = pick_partners(ctx, True)
    ctx.eq(on, off, "the Teams record, partners and controllers")
    ctx.check(off[1][0] != 0xFF and off[1][1] != 0xFF, f"both armies picked a partner ({off[1][:2]})")


def to_co_screen(ctx, step):
    e = Emu(save=paths.base_save(), ds=True, env=BYTE_DRIVEN)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=step)
    ctx.require(e.wait_until(lambda: d.on_co_select() and d.co_cursor(), 3000, step=10) or _press_through(e, d), "the CO screen")
    e.wait(90)
    return e, g, d


def _press_through(e, d):
    for _ in range(300):
        if d.on_co_select() and d.co_cursor():
            return True
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    return False


def pick_cos(ctx, on, step, label):
    e, g, d = to_co_screen(ctx, step)
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(30)
    first = shot(ctx, e, f"{label}_{'on' if on else 'off'}")
    data = dc.DsData()
    if True:  # (choose_cos presses AW2's arrows itself)
        picked = d.choose_cos(dc.co_picks(data, dc.ORDER[step]), dc.CO_PREFS)
    cos = [g.player(a)["co"] for a in range(1, 5)]
    return first, picked, cos


def card_colour(rows, x, w=64):
    """The colour a card's header is mostly (its top rows, the white of the lions left out): red, blue, green, yellow or grey."""
    from collections import Counter
    c = Counter(p for r in rows[0:6] for p in r[x:x + w] if min(p) < 200 or max(p) - min(p) > 40)
    (R, G, B), _ = c.most_common(1)[0]
    if R > 200 and G < 90 and B < 90:
        return "red"
    if B > 200 and R < 110:
        return "blue"
    if G > 120 and R < 120 and B < 140:
        return "green"
    if R > 140 and G > 140 and B < 80:
        return "yellow"
    if abs(R - G) < 24 and abs(G - B) < 24:
        return "grey"
    return f"?{(R, G, B)}"


def pick_card_left(n):
    """Where the first of n name cards' tiles start (crate::ds_coselect::card_left): the pictures (56 of the 64 pixels) centred,
    80 apart for two and three cards, closed up to 60 for four."""
    pitch = 80 if n <= 3 else 60
    return (240 - (pitch * (n - 1) + 56)) // 2 - 4


def only_background(rows, x0, x1, y0, y1):
    """Nothing but the ring wallpaper's pale colours in the box (a card's header is saturated or grey, never this light)."""
    return all(min(p) >= 185 for r in rows[y0:y1] for p in r[x0:x1])


@test(modes=("ds",))
def ds_coselect_campaign_pick(ctx):
    """The DS Campaign's CO screen (a mission of three armies, the player picking two COs and their partners: Orange Star's
    and Blue Moon's, Black Hole's fixed): an army card each in its colour, over the grid; the first pick's CO flagged
    in the grid; the CO screen still picks what the setting off picks."""
    first_on, picked_on, cos_on = pick_cos(ctx, True, 10, "campaign_pick")
    first_off, picked_off, cos_off = pick_cos(ctx, False, 10, "campaign_pick")
    ctx.check(differs(first_off, first_on), "the CO screen is Dual Strike's with the setting on")
    ctx.eq(picked_on, picked_off, "the COs picked")
    ctx.eq(cos_on, cos_off, "the armies' COs in the battle")
    ctx.check(len(picked_on) >= 2, f"the mission asked for picks ({picked_on})")
    # Dual Strike's CO screen has a card for each army the player picks for (not the opponents'): here two, centred, 80 pixels apart
    ctx.eq([card_colour(first_on, pick_card_left(2) + 80 * i) for i in range(2)], ["red", "blue"], "two cards: Orange Star, Blue Moon")
    ctx.check(only_background(first_on, pick_card_left(2) + 80 * 2 + 8, 236, 4, 22), "no card for the mission's fixed army")


def ink(rows, x, y, w, h):
    """Dark pixels in a box (a name plate's lettering is dark green with an outline; the faint 1 and 2 are pale)."""
    return sum(1 for r in rows[y:y + h] for p in r[x:x + w] if max(p) < 100)


@test(modes=("ds",))
def ds_coselect_campaign_plates_are_filled(ctx):
    """Before anything is picked every plate of every card shows a name, as Dual Strike's does (Orange Star's Jake and Rachel,
    Blue Moon's Sasha and Colin, Green Earth's Javier and Jess, the pick's own taking the CO under the cursor): none is
    left empty with only its faint 1 or 2. Two cards (the mission picks two armies) and three, all wholly on the screen."""
    # (every card of a mission that picks partners has a partner plate: with three armies the CO screen has room to pick only the
    # first's, the others keep Dual Strike's defaults)
    for step, n, partners, colours in ((10, 2, 2, ["red", "blue"]), (21, 3, 3, ["red", "blue", "green"])):
        e, g, d = to_co_screen(ctx, step)
        e.w8(DS_GRAPHICS, 1)
        e.wait(30)
        rows = shot(ctx, e, f"plates_{n}")
        left = pick_card_left(n)
        ctx.eq([card_colour(rows, left + 80 * i) for i in range(n)], colours, f"{n} cards")
        # (the pictures' own edges: nothing of a card in the 4 clear pixels before the first and after the last)
        ctx.check(only_background(rows, 0, left + 4, 4, 22) and only_background(rows, left + 80 * (n - 1) + 60, 240, 4, 22), f"{n} cards fit the screen")
        for i in range(n):
            for k, plate in enumerate((16, 32)[:2 if i < partners else 1]):
                ctx.check(ink(rows, left + 80 * i + 8, plate, 48, 16) > 30, f"card {i + 1}, plate {k + 1} shows a name")


@test(modes=("ds",))
def ds_coselect_campaign_flags(ctx):
    """After a pick its CO's cell carries the army's flag (a 16 x 16 flag at the cell's right end) and the card's name plate
    shows the CO."""
    e, g, d = to_co_screen(ctx, 10)
    e.w8(DS_GRAPHICS, 1)
    e.wait(30)
    before = shot(ctx, e, "flags_before")
    with tag.aw2_arrows(e):
        co = d.choose_co(None)
    for _ in range(60):
        if d.picked():
            break
        e.wait(10)
    e.wait(60)
    after = shot(ctx, e, "flags_after")
    ctx.check(differs(before, after, 0.01), f"the pick of CO {co} changes the picture")
    # A flag's white outline and red body: red pixels in the panel (the cell flags are the only red there but the frame).
    reds = sum(1 for r in after[72:150] for (R, G, B) in r[12:230] if R > 200 and 40 < G < 120 and 40 < B < 140)
    ctx.check(reds > 40, f"the pick's red flag is in the grid ({reds})")


def war_room_co_screen(ctx, on):
    e = Emu(save=paths.base_save(), ds=True, env=BYTE_DRIVEN)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 1)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), 600, step=10):
        raise NavError("the War Room's SELECT MAP did not open")
    e.wait(90)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.CO_SCREEN_PROC), 1500, step=10):
        raise NavError("the War Room's CO screen did not open")
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(90)
    return e, g


@test(modes=("ds",))
def ds_coselect_war_room(ctx):
    """The War Room's CO screen: a name card (the CO under the cursor, in its country's colours), then the grid of faces
    scrolling on the GBA screen; locked COs are black cells; the cursor's moves are the game's."""
    e, g = war_room_co_screen(ctx, True)
    on = shot(ctx, e, "war_room_on")
    first = e.u8(0x03005944)
    ctx.check(1 <= first <= 5, f"the CO screen's country tabs are read ({first})")
    cursor = [e.u16(p + 0x52) for p in range(0x0200D610, 0x0200E418, 0x6C) if e.u32(p) == 0x08616638]
    e.press("RIGHT", 6)
    e.wait(40)
    cursor2 = [e.u16(p + 0x52) for p in range(0x0200D610, 0x0200E418, 0x6C) if e.u32(p) == 0x08616638]
    second = shot(ctx, e, "war_room_right")
    ctx.check(cursor2 != cursor, f"RIGHT moves the game's cursor ({cursor} -> {cursor2})")
    ctx.check(differs(on, second, 0.01), "and the picture follows")
    e.close()
    e2, g2 = war_room_co_screen(ctx, False)
    off = shot(ctx, e2, "war_room_off")
    ctx.check(differs(on, off), "the screen is Dual Strike's with the setting on")
    e2.close()


CO_SELECT_PROC = 0x08616638
CO_LIST = 0x030058E0
GROUP_SIZES = 0x03005948
CO_TABLE_POOL = 0x08042DDC


def co_screen_proc(e):
    return next(p for p in range(0x0200D610, 0x0200E418, 0x6C) if e.u32(p) == CO_SELECT_PROC)


def under_cursor(e):
    """(tab, place, CO) the CO screen's cursor is on."""
    p = co_screen_proc(e)
    tab, at, off = e.u8(p + 0x58), e.u16(p + 0x52), e.u32(p + 0x5C)
    size = e.u8(GROUP_SIZES + tab)
    return tab, at % size, e.u8(CO_LIST + at % size + off)


def selectable_by_cycling(e):
    """With the setting off: every CO the cursor can reach (RIGHT through a country tab's COs, DOWN to the next tab)."""
    groups = e.u32(0x03005944)
    seen = []
    for _ in range(groups):
        tab, _, co = under_cursor(e)
        first = co
        seen.append(co)
        for _ in range(e.u8(GROUP_SIZES + tab) - 1):
            e.press("RIGHT", 6)
            e.wait(20)
            seen.append(under_cursor(e)[2])
        e.press("DOWN", 6)
        e.wait(30)
    return seen


def universe(e):
    """Every CO the screen draws a cell for, in Dual Strike's way (ds_coselect.rs: by country, then id)."""
    table = e.u32(CO_TABLE_POOL)
    ids = list(range(19)) + list(range(72, 83))
    return sorted(ids, key=lambda c: (e.u8(table + c * 0x104 + 0x15), c))


def cell_is_black(rows, x, y):
    return all(rows[y + dy][x + dx] == (0, 0, 0) for dx in (4, 12, 20, 28) for dy in (4, 8, 11))


@test(modes=("ds",))
def ds_coselect_black_cells_are_unselectable(ctx):
    """A black cell is a CO the CO screen really cannot pick: the COs the cursor reaches with the setting off (RIGHT through a
    country's COs, DOWN to the next country) are exactly the cells that are not black with it on, over the screen's whole
    grid (the War Room's screen, AW2's own single army: Orange Star's colour for the CO under the cursor)."""
    e, g = war_room_co_screen(ctx, False)
    listed = [e.u8(CO_LIST + k) for k in range(sum(e.u8(GROUP_SIZES + t) for t in range(e.u32(0x03005944))))]
    reached = selectable_by_cycling(e)
    ctx.eq(sorted(reached), sorted(listed), "the cursor reaches the COs the screen lists, no others")
    ctx.log(f"selectable ({len(reached)}): {sorted(reached)}")
    uni = universe(e)
    e.close()
    e, g = war_room_co_screen(ctx, True)
    cursor_co = under_cursor(e)[2]
    cur_row = uni.index(cursor_co) // 4
    pitch, start = 16, 56            # one army's card is 40 high: the cells touch, from y 56
    visible = (160 - start) // pitch
    first = max(0, cur_row - (visible - 1))
    first = min(first, max(0, (len(uni) + 3) // 4 - visible))
    rows = shot(ctx, e, "black_cells")
    wrong = []
    for k, co in enumerate(uni):
        r, c = divmod(k, 4)
        if not first <= r < first + visible:
            continue
        black = cell_is_black(rows, 12 + 56 * c, start + pitch * (r - first))
        if black == (co in reached):
            wrong.append((co, "black" if black else "open", "selectable" if co in reached else "locked"))
    ctx.eq(wrong, [], "every visible cell: black exactly when the CO cannot be picked")
    # (the War Room offers every CO, so it normally has no black cell: the campaign test judges black cells)
    ctx.log(f"locked COs on this screen: {[co for co in uni if co not in reached]}")
    e.close()


@test(modes=("ds",))
def ds_coselect_black_cells_campaign(ctx):
    """The same for the DS Campaign's CO screen (a mission that offers five COs): the cells that are not black are exactly the
    COs the cursor reaches with the setting off."""
    e, g, d = to_co_screen(ctx, 10)
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    reached = selectable_by_cycling(e)
    listed = [e.u8(CO_LIST + k) for k in range(sum(e.u8(GROUP_SIZES + t) for t in range(e.u32(0x03005944))))]
    ctx.eq(sorted(reached), sorted(listed), "the cursor reaches the COs the screen lists, no others")
    ctx.log(f"selectable: {sorted(reached)}")
    uni = universe(e)
    e.w8(DS_GRAPHICS, 1)
    e.wait(20)
    cur_row = uni.index(under_cursor(e)[2]) // 4
    start, pitch = 72, 24              # two plates on a card: the panel from 56, the cells 24 apart from 72
    visible = (160 - start) // pitch
    first = min(max(0, cur_row - (visible - 1)), max(0, (len(uni) + 3) // 4 - visible))
    rows = shot(ctx, e, "black_cells_campaign")
    wrong = []
    for k, co in enumerate(uni):
        r, c = divmod(k, 4)
        if first <= r < first + visible:
            black = cell_is_black(rows, 12 + 56 * c, start + pitch * (r - first))
            if black == (co in reached):
                wrong.append(co)
    ctx.eq(wrong, [], "every visible cell is black exactly when the CO cannot be picked")
    e.close()


@test(modes=("ds",))
def ds_coselect_own_cos_name_and_face(ctx):
    """The COs Dual Strike lacks, on the War Room's CO screen: Clone Andy's name card reads the game's own name ("Clone", not
    Dual Strike's Andy), and Crumb's grid strip shows his goggles' lens (the orange disc) and his mask, not just the helmet."""
    e = Emu(save=paths.base_save(), ds=True, env={"TANGOAW2_DS_GRAPHICS": "0", "TANGOAW2_TILT": "0"})
    ctx.games.append(Game(e, ctx.image))
    warroom.open_war_room(e)
    e.w8(DS_GRAPHICS, 1)
    plates = {}
    for co, n in ((1, "andy"), (81, "clone"), (82, "crumb")):
        with tag.aw2_arrows(e):
            warroom.go_to(e, co)
        e.wait(40)
        rows = shot(ctx, e, f"own_{n}")
        plates[n] = [r[60:180] for r in rows[14:36]]
        if n == "crumb":
            # the strip under the cursor: the lens is orange-brown, the helmet blue
            lens = sum(1 for r in rows[95:160] for (R, G, B) in r[30:120] if R > 140 and G < 100 and B < 90 and R - B > 60)
            ctx.check(lens > 15, f"Crumb's strip shows his goggle lens ({lens})")
    ctx.check(plates["clone"] != plates["andy"], "Clone Andy's name card is not Andy's")
