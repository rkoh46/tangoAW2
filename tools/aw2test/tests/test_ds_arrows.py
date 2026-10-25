"""Dual Strike's arrows on its CO screens (`ds_coselect.rs` / `tag_ui.rs`), offline with "Dual Strike map graphics" on.

Versus' Teams screen: LEFT and RIGHT go cell to cell as clean Dual Strike's NORMAL BATTLE does (an army's CO, its partner,
the next army's CO ..., then the P1 / CPU tabs, round again), UP and DOWN change what the cell holds; the game's own cursor does
the walking, so the Teams record, partners and controllers are what AW2's own controls make. The CO screen (War Room,
campaigns): the arrows move one cell of the drawn grid (four to a row, by country), the game's cursor is walked to that CO, so
A picks the CO the picture shows; a locked cell takes the cursor but not the pick."""

from aw2test import paths, ram, saves, tag
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

from tests.test_ds_coselect import (BYTE_DRIVEN, CO_LIST, CO_TABLE_POOL, DS_GRAPHICS, GROUP_SIZES, shot, to_co_screen,
                                    to_five_army_teams, under_cursor, war_room_co_screen)

PICKS = 0x030058D4
WALK = 220  # frames a walk of the game's cursor to any CO may take (a step takes ~9 frames, a pulse every other one: a wrap from the last country to the first and to a place in it takes about 150)


def record_state(g, five):
    e = g.e
    n = 5 if five else 4
    ctl = ram.TEAMS_FIVE + ram.T5_CONTROLLERS if five else ram.TEAMS + ram.T_CONTROLLERS
    return g.teams(), list(e.read(tag.TEAMS_PARTNER, 5)), list(e.read(ctl, n))


def tap(e, key, wait=30):
    e.press(key, 6)
    e.wait(wait)


def cursor(e, five):
    return e.u8((ram.TEAMS_FIVE if five else ram.TEAMS) + 0x32)


def editing(e):
    return e.u8(tag.UI)


# What each pick does: ("D", n) n times DOWN, ("U", n) UP. Each army: the CO moves, then its partner moves.
def versus_picks(armies):
    return [(1 + a % 3, 2 + a) for a in range(armies)]  # (CO downs, partner downs)


def aw2_controls(e, armies, picks):
    """The same picks with AW2's own controls (START opens the partner pick, RIGHT RIGHT moves to the next army), the setting off."""
    for a, (cos, partner) in enumerate(picks):
        for _ in range(cos):
            tap(e, "DOWN", 20)
        tap(e, "START", 20)
        for _ in range(partner):
            tap(e, "DOWN", 20)
        tap(e, "START", 20)
        if a < armies - 1:
            tap(e, "RIGHT", 14)
            tap(e, "RIGHT", 14)
    # the last army's controller: its tab stop, DOWN
    tap(e, "RIGHT", 14)
    tap(e, "DOWN", 20)


def ds_controls(e, armies, picks, ctx=None):
    """The picks with Dual Strike's arrows: RIGHT to the partner cell, UP/DOWN there, RIGHT to the next army ...; then to the
    first army's tab: RIGHT (over the last partner) and DOWN."""
    for a, (cos, partner) in enumerate(picks):
        for _ in range(cos):
            tap(e, "DOWN", 20)
        tap(e, "RIGHT")
        if ctx:
            ctx.check(editing(e) == a, f"army {a + 1}: the partner cell is open (editing {editing(e)})")
        for _ in range(partner):
            tap(e, "DOWN", 20)
        if a < armies - 1:
            tap(e, "RIGHT")  # its tab
            tap(e, "RIGHT")
            if ctx:
                ctx.check(editing(e) == 0xFF, f"army {a + 2}: its CO cell")
    # from the last army's partner cell: RIGHT is its tab
    tap(e, "RIGHT")
    tap(e, "DOWN", 20)


def run_versus(ctx, on, armies):
    if armies == 2:
        g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
        e = g.e
    else:
        e = Emu(save=paths.base_save(), ds=True, env=BYTE_DRIVEN)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        to_five_army_teams(ctx, g)
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(10)
    picks = versus_picks(armies)
    if on:
        ds_controls(e, armies, picks, ctx)
    else:
        aw2_controls(e, armies, picks)
    e.wait(WALK)
    if on:
        shot(ctx, e, f"arrows{armies}_end")
    return record_state(g, armies == 5)


def versus_case(ctx, armies):
    off = run_versus(ctx, False, armies)
    on = run_versus(ctx, True, armies)
    ctx.eq(on, off, f"{armies} armies: the Teams record, partners and controllers equal AW2's controls'")
    ctx.check(all(p != 0xFF for p in off[1][:armies]), f"every army picked a partner ({off[1][:armies]})")


@test(modes=("ds",))
def ds_coselect_arrows_versus_two(ctx):
    """Two armies: RIGHT to the partner cell, UP/DOWN to pick a partner, RIGHT to army 2, and so on, equal the picks made
    with AW2's own controls with the setting off."""
    versus_case(ctx, 2)


@test(modes=("ds",))
def ds_coselect_arrows_versus_five(ctx):
    """The same with five armies."""
    versus_case(ctx, 5)


@test(modes=("ds",))
def ds_coselect_arrows_versus_wrap(ctx):
    """The order of the cells, army by army (the players' choice; Dual Strike visits the tabs after all the cards): CO, partner,
    tab, the next army's CO ... the last army's tab, then the first army's CO again; LEFT the other way round."""
    for armies in (2, 5):
        if armies == 2:
            g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
            e = g.e
        else:
            e = Emu(save=paths.base_save(), ds=True, env=BYTE_DRIVEN)
            g = Game(e, ctx.image)
            ctx.games.append(g)
            to_five_army_teams(ctx, g)
        e.w8(DS_GRAPHICS, 1)
        e.wait(10)
        five = armies == 5

        def cell():
            c = cursor(e, five)
            return ("tab", c // 2) if c % 2 else (("partner" if editing(e) == c // 2 else "co"), c // 2)

        order = [(k, a) for a in range(armies) for k in ("co", "partner", "tab")]
        seen = [cell()]
        for _ in range(len(order)):
            tap(e, "RIGHT")
            seen.append(cell())
        ctx.eq(seen, order + [order[0]], f"{armies} armies: RIGHT goes through every cell and wraps")
        back = [cell()]
        for _ in range(len(order)):
            tap(e, "LEFT")
            back.append(cell())
        ctx.eq(back, [order[0]] + order[::-1], f"{armies} armies: LEFT goes the other way and wraps")
    shot(ctx, e, "arrows_wrap")


@test(modes=("ds",))
def ds_coselect_arrows_off_and_online_keep_aw2(ctx):
    """With the setting off, RIGHT is AW2's: army 1's CO to its tab (and no partner opens)."""
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    e = g.e
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    tap(e, "RIGHT", 20)
    ctx.eq((cursor(e, False), editing(e)), (1, 0xFF), "AW2's RIGHT (the army's tab, no partner cell)")


# --- The CO screen's grid ----------------------------------------------------------------------------------

COLUMNS = 4
NEW_COS = list(range(72, 83)) + [92]  # tangoAW2's new COs (crate::co_new): in the grid even where the screen does not offer them


def country(e, co):
    table = e.u32(CO_TABLE_POOL)
    return min(e.u8(table + co * 0x104 + 0x15), 4)


def grid_of(e):
    from tests.test_ds_coselect import co_screen_proc
    groups = e.u32(0x03005944)
    sizes = [e.u8(GROUP_SIZES + k) for k in range(groups)]
    offered = list(e.read(CO_LIST, sum(sizes)))
    all_cos = sorted(set(range(19)) | set(NEW_COS) | set(offered), key=lambda c: (country(e, c), c))
    return offered, all_cos


def step(n, cell, dx, dy):
    r, c = divmod(cell, COLUMNS)
    rows = -(-n // COLUMNS)
    if dx:
        ln = min(COLUMNS, n - r * COLUMNS)
        return r * COLUMNS + (c + dx) % ln
    for _ in range(rows):
        r = (r + dy) % rows
        if r * COLUMNS + c < n:
            return r * COLUMNS + c
    return cell


def walk_grid(ctx, e, label):
    offered, all_cos = grid_of(e)
    n = len(all_cos)
    ctx.log(f"{label}: {n} cells, {len(offered)} offered")
    cell = all_cos.index(under_cursor(e)[2])
    locked_cell = None
    moves = {"RIGHT": (1, 0), "LEFT": (-1, 0), "DOWN": (0, 1), "UP": (0, -1)}
    path = ["RIGHT"] * 5 + ["DOWN"] * 8 + ["LEFT"] * 5 + ["UP"] * 9
    for i in range(1, 6):
        path += ["DOWN"] * i + ["RIGHT"] * (i % 4 + 1) + ["UP"] * (i + 1) + ["LEFT"] * 2
    for k in path:
        cell = step(n, cell, *moves[k])
        e.press(k, 6)
        e.wait(WALK)
        co = all_cos[cell]
        if co in offered:
            ctx.check(under_cursor(e)[2] == co, f"{label}: {k} -> cell {cell}: CO {co} under the game's cursor ({under_cursor(e)[2]})")
        else:
            ctx.log(f"{label}: {k} -> cell {cell}: locked (CO {co})")
            locked_cell = cell
    return offered, all_cos


@test(modes=("ds",))
def ds_coselect_arrows_war_room_grid(ctx):
    """The War Room's grid: each arrow moves the cursor to the drawn neighbour (UP/DOWN a row, LEFT/RIGHT a column, wrapping),
    and the game's cursor is on that CO."""
    e, g = war_room_co_screen(ctx, True)
    e.w8(DS_GRAPHICS, 1)
    e.wait(30)
    shot(ctx, e, "grid_0")
    walk_grid(ctx, e, "war room")
    for name, keys in (("right", ["RIGHT"]), ("down", ["DOWN"]), ("left", ["LEFT", "LEFT"]), ("up", ["UP"] * 2)):
        for k in keys:
            e.press(k, 6)
            e.wait(WALK)
        shot(ctx, e, f"grid_{name}")


@test(modes=("ds",))
def ds_coselect_arrows_war_room_picks(ctx):
    """A picks exactly the CO under the drawn cursor: one CO of each country, reached with the arrows."""
    for want_country in range(5):
        e, g = war_room_co_screen(ctx, True)
        e.w8(DS_GRAPHICS, 1)
        e.wait(30)
        offered, all_cos = grid_of(e)
        n = len(all_cos)
        cell = all_cos.index(under_cursor(e)[2])
        # the last CO of the country (so the walk is long), by whole rows then columns
        goal = max(i for i, c in enumerate(all_cos) if country(e, c) == want_country and c in offered)
        for _ in range(60):
            if cell == goal:
                break
            (gr, gc), (cr, cc) = divmod(goal, COLUMNS), divmod(cell, COLUMNS)
            k, d = ("DOWN", (0, 1)) if gr != cr else ("RIGHT", (1, 0))
            e.press(k, 6)
            e.wait(WALK)
            cell = step(n, cell, *d)
        ctx.eq(cell, goal, f"country {want_country}: reached by the arrows")
        co = all_cos[goal]
        ctx.eq(under_cursor(e)[2], co, f"country {want_country}: the game's cursor is on CO {co}")
        e.press("A", 6)
        e.wait(120)
        ctx.eq(e.u8(PICKS), co, f"country {want_country}: A picked CO {co}, the one under the drawn cursor")
        e.close()


@test(modes=("ds",))
def ds_coselect_arrows_locked_cells(ctx):
    """The campaign's CO screen (some COs not offered): the arrows walk the whole grid, a locked cell takes the cursor, and A
    on it picks nothing."""
    e, g, d = to_co_screen(ctx, 10)
    e.w8(DS_GRAPHICS, 1)
    e.wait(30)
    offered, all_cos = grid_of(e)
    locked = [i for i, c in enumerate(all_cos) if c not in offered]
    ctx.log(f"{len(all_cos)} cells, locked {locked}")
    ctx.check(locked, "the campaign's screen has locked cells")
    walk_grid(ctx, e, "campaign")
    # to a locked cell, then A
    n = len(all_cos)
    cell = all_cos.index(under_cursor(e)[2])
    goal = locked[0]
    for _ in range(60):
        if cell == goal:
            break
        (gr, gc), (cr, cc) = divmod(goal, COLUMNS), divmod(cell, COLUMNS)
        k, dd = ("DOWN", (0, 1)) if gr != cr else ("RIGHT", (1, 0))
        e.press(k, 6)
        e.wait(WALK)
        cell = step(n, cell, *dd)
    ctx.eq(cell, goal, "the arrows reach a locked cell")
    shot(ctx, e, "grid_locked")
    before = e.u8(PICKS), e.u16(0x0200D610 + 0)  # (just the first pick)
    e.press("A", 6)
    e.wait(60)
    ctx.eq(e.u8(PICKS), before[0], "A on a locked cell picks nothing")


@test(modes=("ds",))
def ds_coselect_arrows_fast_presses_are_kept(ctx):
    """Arrows pressed while the game's cursor is still walking go on from where the picture's cursor already is."""
    e, g = war_room_co_screen(ctx, True)
    e.w8(DS_GRAPHICS, 1)
    e.wait(30)
    offered, all_cos = grid_of(e)
    cell = all_cos.index(under_cursor(e)[2])
    for k, d in (("RIGHT", (1, 0)), ("DOWN", (0, 1)), ("DOWN", (0, 1)), ("RIGHT", (1, 0)), ("UP", (0, -1))):
        e.press(k, 2)
        e.wait(3)
        cell = step(len(all_cos), cell, *d)
    e.wait(2 * WALK)
    ctx.eq(under_cursor(e)[2], all_cos[cell], f"five quick arrows end on cell {cell}")


def versus_cells(e, five=False):
    c = cursor(e, five)
    return ("tab", c // 2) if c % 2 else (("partner" if editing(e) == c // 2 else "co"), c // 2)


def virtual_cell(e, armies, five=False):
    """The Versus cell number (CO, partner, CO ... tabs) the cursor is on."""
    c = cursor(e, five)
    return 3 * (c // 2) + 2 if c % 2 else 3 * (c // 2) + (editing(e) == c // 2)


def fresh_versus(ctx):
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    g.e.w8(DS_GRAPHICS, 1)
    g.e.wait(10)
    return g.e


@test(modes=("ds",))
def ds_coselect_arrows_versus_press_edges(ctx):
    """As the app delivers input (a key held for as many frames as the player holds it): one cell a press whether it lasts 8,
    15 or 60 frames' worth of a held key's repeats (Dual Strike's: the first step on the press, then one after 12 frames and
    one every 4 after that, measured in melonDS), three presses 10 frames apart are three cells, and the pulses that walk the
    game's cursor are not read back as presses."""
    # (frames held, cells): the press, then 12, 16, 20 ... 56 for the 60 frames (13 cells; the ring has 6)
    for frames, cells in ((2, 1), (8, 1), (11, 1), (13, 2), (15, 2), (60, 13)):
        e = fresh_versus(ctx)
        e.hold("RIGHT", frames)
        e.wait(120)
        ctx.eq(virtual_cell(e, 2), cells % 6, f"RIGHT held {frames} frames: {cells} cells")
        ctx.eq(e.u8(tag.ARROWS + 1), 0, f"RIGHT held {frames} frames: the walk is over")
    for gap in (10, 6):
        e = fresh_versus(ctx)
        for _ in range(3):
            e.hold("RIGHT", 4)
            e.wait(gap - 4)
        e.wait(120)
        ctx.eq(virtual_cell(e, 2), 3, f"RIGHT three times, {gap} frames apart")
    e = fresh_versus(ctx)
    for _ in range(3):
        e.hold("RIGHT", 8)
        e.wait(3)
    e.hold("LEFT", 8)
    e.wait(120)
    ctx.eq(virtual_cell(e, 2), 2, "RIGHT three times, LEFT once, in a hurry")


@test(modes=("ds",))
def ds_coselect_arrows_war_room_press_edges(ctx):
    """The War Room's grid takes presses the same way: one cell for a short press, a held key repeats after 12 frames."""
    for frames, cells in ((8, 1), (15, 2)):
        e, g = war_room_co_screen(ctx, True)
        e.w8(DS_GRAPHICS, 1)
        e.wait(30)
        offered, all_cos = grid_of(e)
        cell = all_cos.index(under_cursor(e)[2])
        for _ in range(cells):
            cell = step(len(all_cos), cell, 1, 0)
        e.hold("RIGHT", frames)
        e.wait(3 * WALK)
        ctx.eq(under_cursor(e)[2], all_cos[cell], f"RIGHT held {frames} frames: {cells} cells")
        e.close()


@test(modes=("ds",))
def ds_coselect_arrows_survive_the_rules_screen(ctx):
    """To the Rules screen (its row cursor and flags live in neighbouring state bytes) and back with B: the Teams screen's arrows
    are still Dual Strike's, one cell a press."""
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    e = g.e
    e.w8(DS_GRAPHICS, 1)
    e.wait(10)
    g.teams_to_rules()
    for _ in range(3):
        e.press("DOWN", 8)
        e.wait(20)
    e.press("B", 8)
    ctx.require(e.wait_until(g.on_teams, 400, step=10), "back on the Teams screen")
    e.wait(60)
    start = virtual_cell(e, 2)
    e.hold("RIGHT", 8)
    e.wait(80)
    ctx.eq(virtual_cell(e, 2), (start + 1) % 6, "RIGHT: one Dual Strike cell")
