"""Dual Strike tilt: units and cursors beyond the console's window.

The tilted view shows more of the map than the console draws (docs/AW2.md, "Dual Strike
tilt"), so what lies there comes from the game's records (ds_tilt.rs). Each scene is
photographed flat (the console's own picture) and tilted; `TANGOAW2_TILT_CHECK=1` makes the
runner say what it drew from the records and where the records and the console's picture
differ inside the console's window, into the file `TANGOAW2_TILT_LOG` names, which the tests
read. Pictures go to $AW2TEST_TILT_PICS (PNG, three times the console's size) when it names a
folder.

Display only: the tests poke a console's RAM to set a scene up (a unit's fuel, its cargo), never
from the tilt, which only reads.
"""

import os
import re
import struct

from aw2test.harness import test

PICS = os.environ.get("AW2TEST_TILT_PICS")

KINDS = ("tank", "infantry", "apc", "artillery", "tank", "infantry")


# -- helpers --------------------------------------------------------------------------------

def read_log(path):
    try:
        return open(path).read().splitlines()
    except OSError:
        return []


def begin(ctx, name, build, tilt, env=None):
    """Start a battle on the map `build(ctx)` makes: returns (game, log file of the check)."""
    log = os.path.join(ctx.out, f"{name}_{'tilt' if tilt else 'flat'}.log")
    try:
        os.remove(log)
    except OSError:
        pass
    e = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0",
         "TANGOAW2_TILT_CHECK": "1", "TANGOAW2_TILT_LOG": log}
    e.update(env or {})
    m, hook = build(ctx)
    g = ctx.start(m, ["andy", "drake"], env=e)
    g.e.wait(30)
    hook(g)
    return g, log


def warm(ctx, g, n=12):
    """The tilt's camera is display-side state that moves as pictures are made, and the runner
    makes one only for a shot: make some, so it has followed the cursor as it does in the app."""
    for _ in range(n):
        g.e.shot(os.path.join(ctx.out, "warm"))


def snap(ctx, g, name, warm_up=12):
    warm(ctx, g, warm_up)
    p = ctx.shot(g, name)
    if PICS:
        from PIL import Image
        os.makedirs(PICS, exist_ok=True)
        Image.open(p).convert("RGB").resize((720, 480), Image.NEAREST).save(os.path.join(PICS, name + ".png"))
    return p


def pair(ctx, name, build, env=None):
    """The scene flat and tilted: ((game, picture, log), (game, picture, log))."""
    out = []
    for tilt in (False, True):
        g, log = begin(ctx, name, build, tilt, env)
        out.append((g, snap(ctx, g, f"{name}_{'tilt' if tilt else 'flat'}"), log))
    return out


def differing(a, b, rect=None, tol=24):
    """How many pixels differ by more than `tol` (sum of channels) between two pictures."""
    from PIL import Image
    pa, pb = Image.open(a).convert("RGB").load(), Image.open(b).convert("RGB").load()
    x0, y0, x1, y1 = rect or (0, 0, 240, 160)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(240, x1), min(160, y1)
    return sum(
        1 for y in range(y0, y1) for x in range(x0, x1)
        if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > tol
    )


def units_by_cell(g):
    return {(u["x"], u["y"]): u for u in g.units()}


def icons_showing(g):
    """The game blinks the low ammunition / fuel icons (BG2 tiles 0x33D to 0x33F are blank in
    between): true while all three are drawn."""
    return all(any(g.e.read(0x06008000 + 32 * t, 32)) for t in (0x33D, 0x33E, 0x33F))


def wait_icons(ctx, g):
    ctx.require(g.e.wait_until(lambda: icons_showing(g), 200, step=1), "the low ammunition and fuel icons blink on")


def oam_entries(e):
    raw = e.read(0x07000000, 0x400)
    out = {}
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", raw, 8 * i)
        if a0 & 0x300 == 0x200:
            continue
        x, y = a1 & 511, a0 & 255
        out[i] = (x - 512 if x >= 256 else x, y - 256 if y >= 160 else y, a2 & 0x3FF, a2 >> 12, (a2 >> 10) & 3)
    return out


def low_by_rule(g, u):
    """The console's rule (`0x08022618`): ammunition and fuel at most a third of the type's own
    (the unit table's +0x0B and +0x10)."""
    table = g.e.u32(0x080909AC)
    max_ammo, max_fuel = g.e.u8(table + 0x5C * u["type"] + 0xB), g.e.u8(table + 0x5C * u["type"] + 0x10)
    return int(max_ammo != 0 and u["ammo"] <= max_ammo // 3) + 2 * int(max_fuel != 0 and u["fuel"] <= max_fuel // 3)


RECORD_DRAWN = re.compile(r"record-drawn unit \((-?\d+), (-?\d+)\) low (\d) at \((-?\d+), (-?\d+)\) to \((-?\d+), (-?\d+)\)")


def record_drawn(log):
    """{(x, y): (low, (left, top, right, bottom))} of the units the tilt drew from their records."""
    out = {}
    for line in read_log(log):
        m = RECORD_DRAWN.search(line)
        if m:
            x, y, low, l, t, r, b = map(int, m.groups())
            out[(x, y)] = (low, (l, t, r, b))
    return out


# -- 1. status icons beyond the window ---------------------------------------------------------

STATUS_CELLS = [(x, y) for y in (10, 11) for x in range(3, 15)] + [(x, y) for x in (15, 16, 17) for y in range(3, 10)]


def status_scene(statuses):
    """Units in the strips the tilt shows beyond the console's window: the right edge (columns
    15 to 17) and the bottom (rows 10 and 11), with every status on them (or none)."""
    def build(ctx):
        m = ctx.map()
        for x, y in STATUS_CELLS:
            m.unit(1 + (x + y) % 2, KINDS[(x + 2 * y) % 6], x, y)

        def hook(g):
            e = g.e
            if statuses:
                for (x, y), u in units_by_cell(g).items():
                    if (x, y) not in STATUS_CELLS:
                        continue
                    a = g.unit_addr(u["id"])
                    n = x + 3 * y
                    if n % 4 == 0:
                        e.w8(a + 6, 2)                                   # low fuel
                    if n % 4 == 1:
                        e.w16(a + 4, e.u16(a + 4) & ~0x780)              # no ammunition
                    if n % 4 == 2:
                        e.w8(a + 6, 2)
                        e.w16(a + 4, e.u16(a + 4) & ~0x780)              # both
                    if n % 7 == 0:
                        e.w16(a + 4, e.u16(a + 4) | (10 << 11))          # capturing (10 points)
                    if n % 7 == 3:
                        e.w8(a + 7, 5)                                   # carrying
            # (the console draws a unit's cell as it enters its plane: out and back)
            g.goto(29, 1)
            g.goto(1, 1)
            wait_icons(ctx, g)
        return m, hook
    return build


@test(modes=("ds",))
def ds_tilt_beyond_status_icons(ctx):
    """Low ammunition, low fuel, capture and cargo icons on units beyond the console's window."""
    (g_f, flat, _), (g, tilt, log) = pair(ctx, "status", status_scene(True))
    g_p, plain_log = begin(ctx, "status_plain", status_scene(False), True)
    plain = snap(ctx, g_p, "status_plain_tilt")
    drawn = record_drawn(log)
    seen = [c for c in STATUS_CELLS if c in drawn]
    ctx.check(len(seen) >= 20, f"at least 20 of the {len(STATUS_CELLS)} units are drawn from their records beyond the window: {len(seen)}")
    units = units_by_cell(g)
    bad = [c for c in seen if drawn[c][0] != low_by_rule(g, units[c])]
    for c in bad[:6]:
        ctx.log(("mismatch", c, units[c], "python", low_by_rule(g, units[c]), "rust", drawn[c][0], hex(g.e.u32(0x080909AC))))
    ctx.check(not bad, f"the low ammunition / fuel icon each gets is the console's rule on its record ({bad[:5]})")
    ctx.check(any(v[0] for v in drawn.values()), "some of them have low ammunition or fuel")
    # The pictures: the same scene without the statuses differs at each unit that has one.
    flagged = changed = 0
    for c in seen:
        n = c[0] + 3 * c[1]
        l, t, r, b = drawn[c][1]
        if low_by_rule(g, units[c]) == 0 and n % 7 not in (0, 3):
            continue
        if l < 0 or t < 0 or r > 240 or t + 8 > 160:
            continue                                  # (its top half is not in the picture)
        flagged += 1
        d = differing(tilt, plain, drawn[c][1])
        changed += d >= 4
    ctx.check(flagged >= 12 and changed >= flagged - 2,
              f"the tilted picture differs from the plain scene's at {changed} of {flagged} units with a status beyond the window")
    ctx.log(f"flat vs tilted pictures: {differing(flat, tilt)} pixels differ")


# -- 1b. the same in the window: the icons the console loses are put back --------------------

def inside_scene(ctx):
    m = ctx.map()
    for x in range(16, 28):
        m.unit(1 + x % 2, KINDS[x % 6], x, 4)

    def hook(g):
        e = g.e
        for (x, y), u in units_by_cell(g).items():
            if y != 4:
                continue
            a = g.unit_addr(u["id"])
            if x % 3 == 0:
                e.w8(a + 6, 2)
            if x % 3 == 1:
                e.w16(a + 4, e.u16(a + 4) & ~0x780)
            if x % 4 == 0:
                e.w16(a + 4, e.u16(a + 4) | (10 << 11))
            if x % 5 == 0:
                e.w8(a + 7, 5)
        g.goto(10, 5)
        g.goto(21, 4)
        wait_icons(ctx, g)
    return m, hook


@test(modes=("ds",))
def ds_tilt_status_icons_in_the_window(ctx):
    """A row of units half in the console's window, half beyond it: both halves wear their
    icons, and the records agree with the console's picture inside the window."""
    (_, flat, _), (g, tilt, log) = pair(ctx, "inside", inside_scene)
    lines = read_log(log)
    checks = [re.search(r"units check: (\d+) units.*, (\d+) cells", l) for l in lines if "units check:" in l]
    ctx.check(bool(checks), "the check reported")
    if checks:
        n, bad = map(int, checks[-1].groups())
        ctx.check(n >= 4 and bad == 0, f"{n} units in the console's window, {bad} cells where the records and the console differ")
    drawn = record_drawn(log)
    ctx.check(len(drawn) >= 2, f"units beyond the window are drawn from their records ({len(drawn)})")
    units = units_by_cell(g)
    ctx.check(all(v[0] == low_by_rule(g, units[c]) for c, v in drawn.items()), "and with the icons the rule gives")


# -- 2. the moving unit, off the console's picture -------------------------------------------

def move_scene(direction):
    start = 8 if direction > 0 else 12

    def build(ctx):
        m = ctx.map()
        m.unit(1, "fighter", start, 6)

        def hook(g):
            e = g.e
            g.select(start, 6)
            g.goto(start + 9 * direction, 6)
            e.wait(40)
            e.press("A", 4)
            e.wait(14)                               # under way
        return m, hook
    return build


def park_the_sprite(g):
    """Do what the game does when the moving unit is off the console's picture: park the nine
    pieces of its sprite (x 0, y 160)."""
    e = g.e
    n = 0
    for i, (x, y, tile, pal, pri) in oam_entries(e).items():
        if 666 <= tile <= 674 and pal == 4 and (x, y) != (0, -96):
            a0, a1, a2 = struct.unpack("<3H", e.read(0x07000000 + 8 * i, 6))
            e.write(0x07000000 + 8 * i, struct.pack("<3H", (a0 & ~0xFF) | 160, a1 & ~0x1FF, a2))
            n += 1
    return n


@test(modes=("ds",))
def ds_tilt_moving_unit_off_the_window(ctx):
    """A Fighter flying nine cells each way is drawn upright at its place, from the game's
    record of the move, when the console's sprite is parked (as it is where the console's
    picture does not reach), with the facing the console showed (it faces both ways)."""
    for direction in (1, -1):
        name = f"mover_{'right' if direction > 0 else 'left'}"
        results = {}
        for use_record in (True, False):
            env = {} if use_record else {"TANGOAW2_TILT_NO_RAM_MOVER": "1"}
            g, log = begin(ctx, name + ("" if use_record else "_norecord"), move_scene(direction), True, env)
            shown = snap(ctx, g, name + ("_sprite" if use_record else "_norecord_sprite"))
            ctx.log(("pieces", sorted((i, v) for i, v in oam_entries(g.e).items() if 666 <= v[2] <= 674 and v[3] == 4)))
            n = park_the_sprite(g)
            ctx.eq(n, 9, f"{name}: the sprite's nine pieces were parked")
            parked = snap(ctx, g, name + ("_parked" if use_record else "_norecord_parked"), warm_up=1)
            results[use_record] = (shown, parked, log)
        shown, parked, log = results[True]
        d = differing(shown, parked)
        ctx.check(d < 40, f"{name}: parked, the unit is drawn from the record where its sprite was ({d} pixels differ)")
        shown2, parked2, _ = results[False]
        d2 = differing(shown2, parked2)
        ctx.check(d2 > 150, f"{name}: without the record's mover the parked unit is missing ({d2} pixels differ)")
        ctx.check(any("record-drawn moving unit" in l for l in read_log(log)), f"{name}: the check says it drew the moving unit from its record")


# -- 3. the cursor and its markers at the console's edge -------------------------------------

def corner_drop_scene(ctx):
    m = ctx.map()
    m.unit(1, "apc", 29, 10)
    m.unit(1, "infantry", 28, 10)

    def hook(g):
        e = g.e
        g.select(28, 10)
        g.move_to(29, 10)
        g.choose("Load", g.ACTION_MENU)
        g.wait_idle()
        g.select(29, 10)
        g.move_to(29, 10)
        g.choose("Drop", g.ACTION_MENU)
        e.wait(20)
        if g.menu():
            e.press("A", 4)
            e.wait(20)
        for _ in range(8):                          # the cursor cycles through the cells the game offers
            if g.cursor()[0] == 29:
                break
            e.press("RIGHT", 4)
            e.wait(10)
        e.wait(20)
    return m, hook


@test(modes=("ds",))
def ds_tilt_drop_cursor_at_the_edge(ctx):
    """An APC on the map's right edge picks where to drop its Infantry: the cursor's pointer and
    brackets stand at the console's edge, partly past it, and the tilt draws them whole (the
    console's picture ends at its last column, the tilted view shows a little more)."""
    (g_f, flat, _), (g, tilt, log) = pair(ctx, "edge_drop", corner_drop_scene)
    o = oam_entries(g.e)
    marks = [(i, v) for i, v in o.items() if v[2] in (869, 873) and not (v[0] == 0 and v[1] == -96)]
    past = [(i, v) for i, v in marks if v[0] + 8 > 240]
    ctx.log(f"cursor {g.cursor()}: pieces of the cursor past the console's picture: {past}")
    ctx.check(len(marks) >= 3, f"the cursor's pointer and brackets are in the console's OAM ({len(marks)})")
    ctx.check(len(past) >= 1, f"some of them are partly past the console's picture ({len(past)})")
    ctx.check(differing(flat, tilt) > 1000, "flat and tilted pictures differ (the map is redrawn)")


# -- 4. the facing the console drew -------------------------------------------------------------

def facing_scene(ctx):
    m = ctx.map()
    for i, y in enumerate(range(3, 9)):
        m.unit(1 + i % 2, KINDS[i % 6], 1, y)

    def hook(g):
        warm(ctx, g, 4)                                         # the console shows them: remembered
        g.goto(14, 5)                                           # now its window has moved on
    return m, hook


@test(modes=("ds",))
def ds_tilt_facing_kept_beyond_the_window(ctx):
    """Units the console drew, then left behind by its window (still in the tilted view), keep
    the facing the console drew them with."""
    (_, flat, _), (g, tilt, log) = pair(ctx, "facing", facing_scene)
    lines = read_log(log)
    kept = [l for l in lines if "kept the console's" in l]
    differ = [l for l in lines if "by the rule" in l]
    ctx.check(len(kept) >= 4, f"units beyond the window kept the facing the console drew ({len(kept)} draws)")
    ctx.check(not differ, f"the facing the console drew is the rule's ({len(differ)} differ)")
    ctx.check(len(record_drawn(log)) >= 2, "the units beyond the window are drawn from their records")
