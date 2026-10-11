"""Dual Strike map graphics: which way units face.

Dual Strike (the clean game, read with a melonDS that dumps its ITCM and lists the 3D polygons of
a frame) draws a unit mirrored (facing right) when its own army is the first or the third and
as stored (facing left) when it is the second or the fourth. The routine that draws a unit
takes the army from the unit's record number (`id & 0xC0`) and flips the picture for 0 and 0x80;
the army's team, colour, side of the map, controller, the turn and whether the unit has moved do not
enter (docs/AW2.md, "Dual Strike tilt"). With four armies that is AW2's own rule, so the console's
picture and the rule agree for every unit that has not moved; a unit that has moved is drawn by AW2
as the army whose turn it is, which the tilted view does not copy (Dual Strike keeps the unit's own
army). A fifth army (Black Hole beside four) goes on alternating.

The tilted view (`TANGOAW2_TILT_CHECK=1`, log in `TANGOAW2_TILT_LOG`) says which way it draws
every unit, in the console's window and beyond it, and where the console's own picture faces the
other way. The tests read that against the rule for two to five armies, for units that have moved,
and for a Tag battle."""

import os
import re

from aw2test.harness import test



def read_log(path):
    try:
        return open(path).read().splitlines()
    except OSError:
        return []


def warm(ctx, g, n=12):
    """The tilt's camera is display-side state that moves as pictures are made, and the runner
    makes one only for a shot: make some, so it has followed the cursor as it does in the app."""
    for _ in range(n):
        g.e.shot(os.path.join(ctx.out, "warm"))

KINDS = ("tank", "infantry", "apc", "artillery", "tank", "infantry")

FACES = re.compile(r"unit (\d+) \(army (\d+)\) (?:in the window|at \((-?\d+), (-?\d+)\) beyond the window) faces by the rule: (mirrored|as stored)")
DIFFERS = re.compile(r"unit (\d+) drawn (mirrored|as stored) by the console, (mirrored|as stored) by the rule")

HQS = {
    2: ((1, 0, 0), (2, 29, 19)),
    3: ((1, 0, 0), (2, 29, 19), (3, 29, 0)),
    4: ((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)),
}


def rule(army):
    """Dual Strike's: the first and third armies are drawn mirrored."""
    return "mirrored" if army % 2 == 1 else "as stored"


def armies_map(ctx, n):
    """`n` armies (five: Black Hole beside four), each with Tanks and an Infantry in its own column
    inside the console's window, and one further Tank far to the right (beyond the window)."""
    m = ctx.map(hq=HQS[min(n, 4)])
    if n == 5:
        m.terrain(15, 15, 0x1B4)
        m.colours = [5, 1, 2, 3, 4]
    for a in range(1, n + 1):
        m.unit(a, "tank", 1 + a, 3).unit(a, "tank", 1 + a, 5).unit(a, "infantry", 1 + a, 4)
        m.unit(a, "tank", 18 + a, 8)
    return m


def facing_lines(log):
    out = []
    for line in read_log(log):
        m = FACES.search(line)
        if m:
            uid, army, x, y, face = m.groups()
            out.append((int(uid), int(army), face, x is not None))
    return out


def run_armies(ctx, n, tilt):
    m = armies_map(ctx, n)
    log = os.path.join(ctx.out, f"facing{n}_{'tilt' if tilt else 'flat'}.log")
    try:
        os.remove(log)
    except OSError:
        pass
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_CHECK": "1", "TANGOAW2_TILT_LOG": log}
    g = ctx.start(m, None, humans=(1,), env=env)
    g.e.wait(30)
    warm(ctx, g, 12)
    ctx.shot(g, f"facing{n}_{'tilt' if tilt else 'flat'}")
    return g, log


def check_rule(ctx, n, log, what):
    seen = facing_lines(log)
    armies = {a for _, a, _, _ in seen}
    ctx.check(armies >= set(range(1, n + 1)), f"{what}: every army's units were drawn ({sorted(armies)})")
    wrong = [(u, a, f) for u, a, f, _ in seen if f != rule(a)]
    ctx.check(not wrong, f"{what}: {len(seen)} draws, all as Dual Strike's rule has them ({wrong[:4]} differ)")
    # (the console's own picture is the rule's for every unit that has not moved)
    differ = [l for l in read_log(log) if DIFFERS.search(l)]
    ctx.check(not differ, f"{what}: the console's picture faces as the rule has it ({len(differ)} units differ)")
    return seen


@test(modes=("ds",))
def ds_facing_two_armies(ctx):
    _, log = run_armies(ctx, 2, True)
    check_rule(ctx, 2, log, "two armies")


@test(modes=("ds",))
def ds_facing_three_armies(ctx):
    _, log = run_armies(ctx, 3, True)
    check_rule(ctx, 3, log, "three armies")


@test(modes=("ds",))
def ds_facing_four_armies(ctx):
    _, log = run_armies(ctx, 4, True)
    seen = check_rule(ctx, 4, log, "four armies")
    ctx.check(len({u for u, a, f, _ in seen if a % 2 == 1 and f == "mirrored"}) >= 4, "the first and third armies' units are drawn mirrored")
    ctx.check(len({u for u, a, f, _ in seen if a % 2 == 0 and f == "as stored"}) >= 4, "the second and fourth armies' units are drawn as stored")


@test(modes=("ds",))
def ds_facing_five_armies(ctx):
    _, log = run_armies(ctx, 5, True)
    check_rule(ctx, 5, log, "five armies")


@test(modes=("ds",))
def ds_facing_beyond_the_window(ctx):
    """Units the console does not draw (beyond its window) face by the rule, from their records."""
    g, log = run_armies(ctx, 4, True)
    g.goto(14, 5)
    warm(ctx, g, 12)
    far = [(u, a, f) for u, a, f, beyond in facing_lines(log) if beyond]
    ctx.check(len(far) >= 4, f"units beyond the window were drawn from their records ({len(far)})")
    ctx.check(all(f == rule(a) for _, a, f in far), f"all of them face by the rule ({far[:4]})")


@test(modes=("ds",))
def ds_facing_moved_units_keep_their_army(ctx):
    """Dual Strike draws a unit that has moved (greyed) facing as its own army does; AW2's console
    draws it as the army whose turn it is. Army 2's Tank, set as moved on army 1's turn, is drawn
    as stored in the tilted view whatever the console shows."""
    g, log = run_armies(ctx, 4, True)
    tank = g.unit_at(3, 3)
    ctx.require(tank and tank["army"] == 2, f"army 2's Tank is at (3, 3): {tank}")
    a = g.unit_addr(tank["id"]) + 1
    g.e.w8(a, g.e.u8(a) | 1)
    mark = len(read_log(log))
    g.e.wait(20)
    warm(ctx, g, 12)
    fresh = read_log(log)[mark:]
    mine = [FACES.search(l) for l in fresh]
    mine = [m for m in mine if m and int(m.group(1)) == tank["id"]]
    ctx.check(mine and all(m.group(5) == "as stored" for m in mine), f"the moved unit of the second army faces as stored ({len(mine)} draws)")
    d = [m for m in (DIFFERS.search(l) for l in fresh) if m and int(m.group(1)) == tank["id"]]
    ctx.log(f"where the console's own picture of it differs: {[m.group(0) for m in d][:2]}")
    # And the others' facing is unchanged.
    others = [(u, a, f) for u, a, f, _ in facing_lines(log) if u != tank["id"] and f != rule(a)]
    ctx.check(not others, f"no other unit faces against the rule ({others[:3]})")


@test(modes=("ds",))
def ds_facing_flat_is_the_consoles(ctx):
    """With the tilt off the console's own picture is kept: its units face by AW2's rule, which for
    units that have not moved is Dual Strike's (the tilted view above reads the two against each
    other); the picture is made and the game runs."""
    g, log = run_armies(ctx, 4, False)
    ctx.check(g.units(), "the battle runs with the tilt off")
