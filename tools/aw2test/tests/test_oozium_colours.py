"""The Oozium's eat and its immunity in every army colour (Dual Strike pack):
Orange Star, Blue Moon, Green Earth, Yellow Comet and Black Hole (as army 1
of a two-army map, and as army 5 of a five-army map), by the player and by
the CPU, and each colour as the eaten side. The eater keeps its army's
colours before and after (its map sprite matches another Oozium of its
army that moved without eating), the victim goes with its own destruction,
and a power's effect passes over an Oozium leaving it as it was.
Screenshots: before / during / after of each."""

import os

from aw2test import setting
from aw2test.harness import test

DS = ("ds",)
OOZIUM = 27
COLOURS = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}
DESTROY_SCRIPT = 0x0849FB04  # the unit explosion (sub_0803FF48), then 0x0849FB44 (the destruction)
MAP = 0x0201E450
# Where the map cursor waits for a screenshot: off the units, with them all in view.
PARK = (15, 12)
APPROACH = (8, 7)
# Squares no unit or effect ever uses, in view (3 x 2 from here): the plain's colours.
EMPTY = (7, 5)


def start(ctx, m, cos, **kw):
    """ctx.start; on the tilted map the console also logs where each unit's picture stands on the
    screen (TANGOAW2_TILT_CHECK), which `cell_pixels` reads (the map is not a flat grid then)."""
    if setting.tilt():
        log = os.path.join(ctx.out, "tilt.log")
        if os.path.exists(log):
            os.remove(log)
        kw["env"] = {"TANGOAW2_TILT_CHECK": "1", "TANGOAW2_TILT_LOG": log, "TANGOAW2_TILT_SNAP": "1"}
    return ctx.start(m, cos, **kw)


class Sig:
    """What a unit's picture is drawn in on the tilted map: its main colours with their shares.
    Two are equal when each main colour of one is (within the scaling's blending) among the other's."""

    def __init__(self, hist):
        total = sum(hist.values())
        self.all = list(hist)
        self.main = [c for c, n in hist.items() if n * 12 >= total]

    @staticmethod
    def near(a, b):
        return sum(abs(p - q) for p, q in zip(a, b)) <= 36

    def __eq__(self, other):
        return (bool(self.main) and bool(other.main)
                and all(any(self.near(c, d) for d in other.all) for c in self.main)
                and all(any(self.near(c, d) for d in self.all) for c in other.main))

    def __repr__(self):
        return f"Sig({sorted(self.main)})"


def tilt_boards(ctx):
    """The latest box (left, top, right, bottom) the tilted map drew for each (foot u, foot v) of a
    unit's picture: from the console's check log."""
    boxes = {}
    try:
        lines = open(os.path.join(ctx.out, "tilt.log")).read().splitlines()
    except OSError:
        return boxes
    for line in lines:
        if not line.startswith("ds_tilt: board "):
            continue
        t = line.replace("(", " ").replace(")", " ").replace(",", " ").split()
        # board fu fv WxH at l t to r b
        fu, fv = float(t[2]), float(t[3])
        boxes[(fu, fv)] = tuple(float(v) for v in (t[6], t[7], t[9], t[10]))
    return boxes


def tilt_cell(ctx, im, name, x, y):
    """The colours drawn for the unit on cell (x, y) of the tilted map: the pixels of its picture's
    boxes (the logged ones whose foot is on the cell) that are not the ground's."""
    boxes = tilt_boards(ctx)
    mine = [b for (fu, fv), b in boxes.items() if abs(fu - (x + 0.5)) < 0.01 and y + 0.5 < fv < y + 1.5]
    if not mine:
        ctx.log(f"{name}: no picture logged on square {(x, y)}")
        return None
    box = (min(b[0] for b in mine), min(b[1] for b in mine), max(b[2] for b in mine), max(b[3] for b in mine))
    px = im.load()

    def inside(bx, ex=0):
        return bx[0] - ex <= X < bx[2] + ex and bx[1] - ex <= Y < bx[3] + ex

    ground = set()
    for Y in range(36, 160):
        for X in range(0, 240):
            if not any(inside(b, 3) for b in boxes.values()) and not (X < 110 and Y > 85) and not (X > 170 and Y > 90):
                ground.add(px[X, Y])
    hist = {}
    for Y in range(max(0, int(box[1])), min(160, int(box[3]) + 1)):
        for X in range(max(0, int(box[0])), min(240, int(box[2]) + 1)):
            c = px[X, Y]
            if c not in ground:
                hist[c] = hist.get(c, 0) + 1
    # (a ground shade the sample missed is a few stray pixels: drop colours drawn on under 3)
    hist = {c: n for c, n in hist.items() if n >= 3}
    ctx.log(f"{name}: square {(x, y)} box {tuple(round(v) for v in box)}: {sum(hist.values())} sprite pixels, main colours {Sig(hist).main}")
    return Sig(hist) if sum(hist.values()) >= 15 else None


def cell_pixels(ctx, g, name, x, y):
    """Screenshot `name` (the map cursor out of the way) and return the
    colours drawn on square (x, y) (its 16x16 pixels less the plain's own
    colours, read off empty squares), so the same sprite on different
    squares compares equal."""
    g.wait_idle()
    g.goto(*APPROACH)
    g.goto(*PARK)
    g.e.wait(20)
    path = ctx.shot(g, name)
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if setting.tilt():
        return tilt_cell(ctx, im, name, x, y)
    sx, sy = g.e.u16(MAP + 4), g.e.u16(MAP + 6)

    def cell(cx, cy):
        px, py = cx * 16 - sx, cy * 16 - sy
        if not (0 <= px <= 224 and 0 <= py <= 144):
            return None
        return list(im.crop((px, py, px + 16, py + 16)).getdata())

    here = cell(x, y)
    empty = [cell(EMPTY[0] + dx, EMPTY[1] + dy) for dx in range(3) for dy in range(2)]
    if here is None or None in empty:
        ctx.log(f"{name}: scroll {(sx, sy)}, square {(x, y)} or the plain's out of view")
        return None
    plain = {p for c in empty for p in c}
    drawn = [p for p in here if p not in plain]
    # Its colours (each on at least 3 pixels: a neighbour's sprite may reach
    # a pixel or two into the square).
    out = sorted(c for c in set(drawn) if drawn.count(c) >= 3)
    ctx.log(f"{name}: scroll {(sx, sy)}, square {(x, y)}: {len(drawn)} sprite pixels, colours {out}")
    return out


def wait_destroy(g, max_frames=900):
    """Wait until the game's destruction proc runs (the eat's explosion)."""
    return g.e.wait_until(lambda: any(DESTROY_SCRIPT <= s < DESTROY_SCRIPT + 0x80 for _, s, _ in g.procs()),
                          max_frames, step=2)


def two_army(ctx, eater, victim):
    m = ctx.map()
    m.colours = [0, eater, victim, 3 if 3 not in (eater, victim) else 4, 4 if 4 not in (eater, victim) else 1]
    return m


def five_army(ctx):
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.terrain(15, 15, 0x1B4)
    m.colours = [5, 1, 2, 3, 4]
    return m


def human_eat(ctx, m, army, cos, label):
    """Army `army` (human) eats with its Oozium at (10, 10) the unit at (11, 10);
    its second Oozium at (10, 13) moves to (10, 14) without eating (the control)."""
    g = start(ctx, m, cos, humans=(army,))
    before = cell_pixels(ctx, g, f"{label}_before", 10, 10)
    control0 = cell_pixels(ctx, g, f"{label}_control0", 10, 13)
    ctx.check(before is not None and before == control0, f"{label}: the eater looks like its army's other Oozium before")
    g.select(10, 10)
    g.move_to(11, 10)
    g.choose("Wait", g.ACTION_MENU)
    ctx.check(wait_destroy(g), f"{label}: the victim's destruction runs")
    g.e.wait(8)
    ctx.shot(g, f"{label}_during")
    g.wait_for_input()
    g.select(10, 13)
    g.move_to(10, 14)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    after = cell_pixels(ctx, g, f"{label}_after", 11, 10)
    control1 = cell_pixels(ctx, g, f"{label}_control1", 10, 14)
    ctx.check(after is not None and after == control1, f"{label}: the eater looks like its army's other (moved) Oozium after")
    u = g.unit_at(11, 10)
    ctx.check(u is not None and u["type"] == OOZIUM and u["army"] == army, f"{label}: the Oozium on the victim's square: {u}")
    return g


def make_human(colour):
    def fn(ctx):
        m = two_army(ctx, colour, 1 if colour != 1 else 2)
        m.unit(1, OOZIUM, 10, 10).unit(2, "tank", 11, 10).unit(1, OOZIUM, 10, 13)
        human_eat(ctx, m, 1, ["andy", "max"], "human")
    fn.__name__ = f"oozium_eats_as_{COLOURS[colour].lower().replace(' ', '_')}"
    test(modes=DS)(fn)


def make_victim(colour):
    def fn(ctx):
        m = two_army(ctx, 1 if colour != 1 else 2, colour)
        m.unit(1, OOZIUM, 10, 10).unit(2, "mdtank", 11, 10).unit(1, OOZIUM, 10, 13)
        g = human_eat(ctx, m, 1, ["andy", "max"], "victim")
        ctx.eq([u for u in g.units(2) if u["type"] == 3], [], f"the {COLOURS[colour]} Md Tank is gone")
    fn.__name__ = f"oozium_eats_{COLOURS[colour].lower().replace(' ', '_')}_unit"
    test(modes=DS)(fn)


def make_cpu(colour):
    def fn(ctx):
        m = two_army(ctx, 1 if colour != 1 else 2, colour)
        m.unit(1, "tank", 10, 10).unit(2, OOZIUM, 11, 10).unit(2, OOZIUM, 13, 12)
        g = start(ctx, m, ["andy", "max"], visuals="off")
        before = cell_pixels(ctx, g, "cpu_before", 11, 10)
        control0 = cell_pixels(ctx, g, "cpu_control0", 13, 12)

        def watch(gg):
            ctx.check(wait_destroy(gg, 3000), "the CPU's eat runs the destruction")
            for k in range(4):
                gg.e.wait(6)
                ctx.shot(gg, f"cpu_during{k}")

        g.end_turn(observe=watch)
        u = g.unit_at(10, 10)
        ctx.check(u is not None and u["type"] == OOZIUM and u["army"] == 2, f"the CPU's Oozium ate the Tank: {u}")
        other = [v for v in g.units(2) if v["type"] == OOZIUM and (v["x"], v["y"]) != (10, 10)][0]
        after = cell_pixels(ctx, g, "cpu_after", 10, 10)
        control1 = cell_pixels(ctx, g, "cpu_control1", other["x"], other["y"])
        ctx.check(after is not None and after == control1,
                  f"{COLOURS[colour]} (CPU): the eater looks like its army's other Oozium after")
    fn.__name__ = f"cpu_oozium_eats_as_{COLOURS[colour].lower().replace(' ', '_')}"
    test(modes=DS)(fn)


@test(modes=DS)
def oozium_eats_five_armies_human(ctx):
    """Army 1 (Orange Star) of a five-army game eats Black Hole's Tank; army 5 Black Hole's
    Oozium, played by the CPU, eats back."""
    m = five_army(ctx)
    m.unit(1, OOZIUM, 10, 10).unit(5, "tank", 11, 10).unit(1, OOZIUM, 10, 13)
    m.unit(5, OOZIUM, 20, 10).unit(1, "tank", 21, 10).unit(5, "infantry", 16, 15)
    g = human_eat(ctx, m, 1, None, "five")
    g.goto(17, 12)
    g.goto(24, 12)
    g.e.wait(20)
    ctx.shot(g, "five_cpu_before")

    def watch(gg):
        ctx.check(wait_destroy(gg, 3000), "Black Hole's eat runs the destruction")
        for k in range(3):
            gg.e.wait(6)
            ctx.shot(gg, f"five_cpu_during{k}")

    g.end_turn(observe=watch)
    u = g.unit_at(21, 10)
    ctx.check(u is not None and u["type"] == OOZIUM and u["army"] == 5, f"Black Hole's Oozium (army 5) ate: {u}")
    g.goto(17, 12)
    g.goto(24, 12)
    g.e.wait(20)
    ctx.shot(g, "five_cpu_after")


def make_immune(colour):
    def fn(ctx):
        m = two_army(ctx, 1 if colour != 1 else 2, colour)
        m.unit(1, "tank", 2, 2)
        m.unit(2, OOZIUM, 12, 10).unit(2, "tank", 13, 10).unit(2, OOZIUM, 15, 8)
        g = start(ctx, m, ["vonbolt", "max"], humans=(1, 2))
        before = cell_pixels(ctx, g, "immune_before", 12, 10)
        control0 = cell_pixels(ctx, g, "immune_control0", 15, 8)
        g.charge_power(1, "super")
        g.open_map_menu()
        g.choose("Super", g.MAP_MENU)
        seen = False
        for _ in range(300):
            g.e.wait(4)
            if g.unit_at(13, 10) and g.unit_at(13, 10)["hp"] < 100:
                seen = True
                break
        ctx.shot(g, "immune_during")
        g.wait_for_input()
        after = cell_pixels(ctx, g, "immune_after", 12, 10)
        control1 = cell_pixels(ctx, g, "immune_control1", 15, 8)
        ctx.eq(g.unit_at(12, 10)["hp"], 100, f"{COLOURS[colour]}: the Oozium is untouched by Ex Machina")
        ctx.check(seen, "the strike hit the Tank next to it")
        ctx.check(before is not None and before == control0, f"{COLOURS[colour]}: the Oozium looks like its army's other one before")
        ctx.check(after is not None and after == control1, f"{COLOURS[colour]}: and after (its colours kept)")
    fn.__name__ = f"oozium_immune_as_{COLOURS[colour].lower().replace(' ', '_')}"
    test(modes=DS)(fn)


@test(modes=DS)
def oozium_immune_five_armies(ctx):
    """Black Hole (army 5 of five) is struck by a human Von Bolt: its Oozium is untouched."""
    m = five_army(ctx)
    m.unit(1, "tank", 2, 2)
    m.unit(5, OOZIUM, 12, 10).unit(5, "tank", 13, 10).unit(5, "infantry", 16, 15).unit(5, OOZIUM, 15, 8)
    cos = None
    g = start(ctx, m, cos)
    p = g.player(1)["addr"]
    g.e.w8(p + 0x1D, 75)  # army 1 plays Von Bolt
    g.charge_power(1, "super")
    before = cell_pixels(ctx, g, "five_immune_before", 12, 10)
    control0 = cell_pixels(ctx, g, "five_immune_control0", 15, 8)
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    g.e.wait(200)
    ctx.shot(g, "five_immune_during")
    g.wait_for_input()
    after = cell_pixels(ctx, g, "five_immune_after", 12, 10)
    control1 = cell_pixels(ctx, g, "five_immune_control1", 15, 8)
    ctx.eq(g.unit_at(12, 10)["hp"], 100, "Black Hole's Oozium is untouched")
    ctx.check(before is not None and before == control0 and after == control1, "and keeps its colours (as its other Oozium)")


for _c in COLOURS:
    make_human(_c)
    make_victim(_c)
    make_cpu(_c)
    make_immune(_c)
