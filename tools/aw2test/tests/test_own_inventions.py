"""An army never targets its own or an allied army's Black Hole invention (crate::cpu_inventions::own_not_a_target),
human or computer, in Versus (design maps included), the BH Campaign and the DS Campaign: the unit has no Fire at
it. An enemy army's structures stay targetable. Only with the pack (AW2 has no army that owns inventions beside the
computer's)."""

import os

from aw2test.harness import test
from tests.test_bh_factory import ANCHOR, factory_map, start, to_army
from tests.test_cpu_inventions import AIM, OFF, start_inv

PICS = os.environ.get("AW2TEST_PICS")
CANNON_ANCHOR = 0x187


def bh_army(r):
    e, g = r.e, r.g
    return next(a for a in (1, 2) if e.u8(g.players_base + 0x3C * a + 0x1A) == 5)


def versus_menu(ctx, anchor, shooter, ally=False, off=False):
    # A Tank for each army, neither beside the other.
    m = ctx.map()
    m.colours = [1, 5, 2, 3, 4]
    m.terrain(10, 10, anchor)
    if anchor == CANNON_ANCHOR:
        kind, a2, a1, to = "tank", (12, 14), (9, 14), None
    else:
        # The doors under the factory fill with its spawns on its own turn: Artillery fire without moving.
        kind, a2, a1, to = "artillery", (10, 14), (10, 13), "stay"
    m.unit(2, kind, *a2)
    m.unit(1, kind, *a1)
    r = start(ctx, m, shots=())
    e, g = r.e, r.g
    if off:
        e.w8(OFF, 0xA5)
    owner = bh_army(r)
    mover = owner if shooter == "own" else 3 - owner
    if ally:
        e.w8(g.players_base + 0x3C * mover + 0x2A, e.u8(g.players_base + 0x3C * owner + 0x2A))
    # Which tank belongs to the mover: the one at (12, 14) is army 2's, (10, 14) army 1's.
    at = a2 if mover == 2 else a1
    to_army(g, mover)
    e.wait(30)
    # The entry's corner and aim: the factory's middle bottom row (10, 11); a cannon's (11, 12) from its corner (10, 10).
    inv = 0x02028360
    ix, iy = e.u8(inv), e.u8(inv + 1)
    if anchor == CANNON_ANCHOR:
        tx, ty = ix + 1, iy + 2
    else:
        tx, ty = ix + 1, iy + ((e.u8(inv + 2) >> 3) & 7) - 1
    ctx.log(f"owner {owner} mover {mover} current {g.current_army()} at {at} units {[(u['army'],u['x'],u['y']) for u in g.units()]}")
    g.select(*at)
    names = g.move_to(*(at if to else (tx, ty + 1)))["names"]
    ctx.log(f"anchor {anchor:x} {shooter} ally={ally} off={off}: menu {names}")
    return names


@test(modes=("ds",))
def own_inv_versus_factory(ctx):
    """Versus: the Black Hole army's Tank beside its own Black Factory has no Fire; an enemy's Tank has."""
    ctx.check("Fire" not in versus_menu(ctx, ANCHOR, "own"), "own factory: no Fire")
    ctx.check("Fire" in versus_menu(ctx, ANCHOR, "enemy"), "enemy's factory: Fire")
    ctx.check("Fire" not in versus_menu(ctx, ANCHOR, "enemy", ally=True), "allied army's factory: no Fire")


@test(modes=("ds",))
def own_inv_versus_cannon(ctx):
    """Versus: the same for a Black Cannon."""
    ctx.check("Fire" not in versus_menu(ctx, CANNON_ANCHOR, "own"), "own cannon: no Fire")
    ctx.check("Fire" in versus_menu(ctx, CANNON_ANCHOR, "enemy"), "enemy's cannon: Fire")
    ctx.check("Fire" not in versus_menu(ctx, CANNON_ANCHOR, "enemy", ally=True), "allied army's cannon: no Fire")
    ctx.check("Fire" in versus_menu(ctx, CANNON_ANCHOR, "own", off=True), "development byte off: the game's own rule (Fire at an own cannon)")


# --- The BH Campaign (the player is Black Hole, army 1; the fixture mission of test_cpu_inventions) ------------

MAP = 0x0201E450
ROWS = MAP + 0x417A
UNIT_PLANE = MAP + 0x12
ALL_PLANE = MAP + 0x51A


def shot(ctx, e, g, name, names):
    """A 3x picture of the action menu and, when Fire is on it, of the target selection."""
    from PIL import Image
    os.makedirs(PICS, exist_ok=True)
    def take(tag):
        bmp = e.shot(os.path.join(ctx.out, tag))
        im = Image.open(bmp)
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(PICS, tag + ".png"))
    take(name + "_menu")
    if "Fire" in names:
        g.choose("Fire", g.ACTION_MENU)
        e.wait(40)
        take(name + "_targeting")
        e.press("B", 4)
        e.wait(30)


def place_artillery(e, g, x, y):
    """A full-strength Artillery of army 1 (the player) on (x, y)."""
    per = 51 if e.u8(0x02030206) == 1 else 64
    live = {u["id"] for u in g.units()}
    uid = next(i for i in range(1, per) if i not in live)
    a = g.unit_addr(uid)
    for k in range(12):
        e.w8(a + k, 0)
    e.w8(a, 10)
    e.w8(a + 2, x)
    e.w8(a + 3, y)
    e.w16(a + 4, 100 | (9 << 7))
    e.w8(a + 6, 70)
    row = e.u16(ROWS + 2 * y)
    for plane in (UNIT_PLANE, ALL_PLANE):
        e.w8(plane + row + x, uid)
    count = g.players_base + 0x3C * 1 + 0x3A
    e.w8(count, e.u8(count) + 1)
    return uid


def fire_at_own(ctx, off):
    """The Fire entry of an Artillery two or three squares from each structure of the fixture (the player's own);
    returns {name: names of the menu}."""
    e, g, d = start_inv(ctx, off=off)
    occupied = {(u["x"], u["y"]) for u in g.units()}
    out = {}
    for name, (ax, ay) in AIM.items():
        for dist in (2, 3):
            cands = [(ax + dx, ay + dy) for dx in range(-dist, dist + 1) for dy in range(-dist, dist + 1)
                     if abs(dx) + abs(dy) == dist and 0 <= ax + dx < 26 and 0 <= ay + dy < 16 and (ax + dx, ay + dy) not in occupied]
            # Only a cell the structure's own footprint does not cover: the ground class is not an invention's
            for x, y in cands:
                if g.terrain_class(x, y) & 0x1F not in (1, 2, 3, 4):   # plains, road, wood, mountain
                    continue
                uid = place_artillery(e, g, x, y)
                occupied.add((x, y))
                g.select(x, y)
                try:
                    names = g.move_to(x, y)["names"]
                except Exception as ex:
                    ctx.log(f"{name}: {(x, y)} no menu ({ex})")
                    continue
                ctx.log(f"{name} from {(x, y)}: {names}")
                if PICS and name == "cannon":
                    shot(ctx, e, g, f"campaign_cannon_{'before' if off else 'after'}", names)
                e.press("B", 4)
                e.wait(20)
                e.press("B", 4)
                g.wait_for_input()
                out[name] = names
                break
            if name in out:
                break
    return out


@test(modes=("ds",))
def own_inv_bh_campaign_no_fire_at_own(ctx):
    """BH Campaign: the player's Artillery in range of its own Black Cannon, Obelisk, Crystal, minicannon and Black
    Factory has no Fire; with the development byte off (the game's own rule) it has, for the structures AW2 lets any army hit."""
    on = fire_at_own(ctx, False)
    ctx.check(len(on) >= 4, f"menus read for {sorted(on)}")
    for name, names in on.items():
        ctx.check(not any(n.startswith("Fire") and "greyed" not in n for n in names), f"{name}: no Fire ({names})")
    off = fire_at_own(ctx, True)
    live = [n for n, names in off.items() if "Fire" in names]
    ctx.check(len(live) >= 3, f"development byte off: the game's own rule offers Fire at {live} (off: {off})")
