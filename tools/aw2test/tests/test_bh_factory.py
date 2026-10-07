"""The Black Factory in Versus (crate::bh_factory).

AW2's factory spawner puts up to three units a turn on the row under the
factory, the types from a table by day. With the Dual Strike pack, in Versus,
a slot also spawns Dual Strike's land units (Megatank, Oozium, a Piperunner
by a pipe) and, when a ship can be placed on a free sea/reef/shoal square next
to the door row, ships. Without the pack, or on a landlocked factory, nothing
of that happens. A harness map has a Black Factory (anchor tile 0x18D at
(10, 10): its doors are (9..11, 12)); both armies are human so the Black Hole
army's own turn-start spawn (the detour in crate::factory) can be observed
before anything moves; each turn's spawns are read and then removed from RAM."""

import os

from aw2test import paths
from aw2test import rom as romlib
from aw2test.harness import Skip, test

MAP = 0x0201E450
ROWS = MAP + 0x417A
UNIT_PLANE = MAP + 0x12
ALL_PLANE = MAP + 0x51A
DAY = 0x03004080
FACTORY_BLUES = 0x00576F23          # the table the design maps use (file offset in the ROM)
ANCHOR = 0x18D
DOORS = [(9, 12), (10, 12), (11, 12)]
SEA, SHOAL, REEF, PIPE = 7, 13, 19, 15
WATER = (SEA, SHOAL, REEF)
SHIPS = {18, 21, 22, 23, 24, 26}
NAVAL_AW2 = {21, 22, 23, 24}
LANDER = 23
MEGATANK, PIPERUNNER, OOZIUM = 4, 9, 27
# The squares a ship may be placed on: the door row, its two ends, the row under it.
NEAR = [(x, 12) for x in range(8, 13)] + [(x, 13) for x in range(9, 12)]
COAST = [(8, 12), (12, 12)] + [(x, 13) for x in range(8, 14)] + [(x, y) for x in range(8, 14) for y in (14, 15)]


def factory_map(ctx, sea=(), shoal=(), reef=(), pipes=(), blockers=()):
    m = ctx.map()
    m.colours = [1, 5, 2, 3, 4]
    m.terrain(10, 10, ANCHOR)
    for x, y in sea:
        m.terrain(x, y, "sea")
    for x, y in shoal:
        m.terrain(x, y, "shoal")
    for x, y in reef:
        m.terrain(x, y, "reef")
    for x, y in pipes:
        m.terrain(x, y, "pipe")
    for kind, x, y in blockers:
        m.unit(2, kind, x, y)
    return m


class Run:
    """Plays the Black Hole army's turns and collects what its factory spawned."""

    def __init__(self, ctx, g, shots=()):
        self.ctx, self.g, self.e = ctx, g, g.e
        self.bh = next(a for a in (1, 2) if self.e.u8(g.players_base + 0x3C * a + 0x1A) == 5)
        self.other = 3 - self.bh
        self.base = {u["id"] for u in g.units()}
        self.spawns = []         # (day, type, x, y, terrain class)
        self.shots = set(shots)  # types to photograph the first time they spawn
        self.taken = set()
        self.harvest()

    def class_at(self, x, y):
        return self.g.terrain_class(x, y) & 0x1F

    def purge(self, u):
        e = self.e
        for k in range(12):
            e.w8(self.g.unit_addr(u["id"]) + k, 0)
        row = e.u16(ROWS + 2 * u["y"])
        for plane in (UNIT_PLANE, ALL_PLANE):
            e.w8(plane + row + u["x"], 0)
        count = self.g.players_base + 0x3C * self.bh + 0x3A
        e.w8(count, e.u8(count) - 1)

    def harvest(self):
        new = [u for u in self.g.units(self.bh) if u["id"] not in self.base]
        day = self.e.u16(DAY)
        for u in sorted(new, key=lambda u: u["id"]):
            self.spawns.append((day, u["type"], u["x"], u["y"], self.class_at(u["x"], u["y"])))
        for u in new:
            if u["type"] in self.shots and u["type"] not in self.taken:
                self.taken.add(u["type"])
                self.g.goto(10, 12)
                self.e.wait(20)
                self.ctx.shot(self.g, f"spawn_{romlib.UNIT_NAMES[u['type']].replace(' ', '_').lower()}_day{day}")
        for u in new:
            self.purge(u)
        self.e.wait(4)

    def days(self, n):
        g = self.g
        for _ in range(n):
            if g.current_army() == self.bh:
                g.end_turn(human=self.other)
            g.end_turn(human=self.bh)
            self.harvest()
        return self.spawns

    def types(self):
        return {s[1] for s in self.spawns}


def start(ctx, m, shots=(MEGATANK, OOZIUM, 22, 23, 26, 18, 21, 24)):
    return Run(ctx, ctx.start(m, ["andy", "vonbolt" if ctx.ds else "drake"], humans=(1, 2)), shots=shots)


def table_unit(rom, day, slot):
    return rom[FACTORY_BLUES + (day & 0x1F) * 3 + slot]


def names(spawns):
    return [(d, romlib.UNIT_NAMES[t], x, y) for d, t, x, y, c in spawns]


@test(modes=("ds",))
def bh_factory_dual_strike_land_units(ctx):
    """On a landlocked factory the pool has the table's units and Megatanks and Ooziums (no ships, no
    Piperunner without a pipe), all on the door tiles, none on water."""
    r = start(ctx, factory_map(ctx))
    spawns = r.days(40)
    ctx.log(f"{len(spawns)} spawns: {names(spawns)}")
    types = r.types()
    ctx.check(MEGATANK in types and OOZIUM in types, f"Megatanks and Ooziums spawn: {sorted(types)}")
    ctx.check(not types & (SHIPS | {PIPERUNNER}), f"no ship and no Piperunner on a landlocked factory: {sorted(types)}")
    ctx.check(any(t not in (MEGATANK, OOZIUM) for _, t, *_ in spawns), "the table's own units still spawn")
    ctx.check(all((x, y) in DOORS for _, _, x, y, _ in spawns), "every spawn is on a door tile")
    ctx.check(all(c not in (SEA, REEF) for *_, c in spawns), "no land unit on water")


@test(modes=("ds",))
def bh_factory_piperunner_by_a_pipe(ctx):
    """A pipe next to the door row gets Piperunners, placed on the pipe."""
    r = start(ctx, factory_map(ctx, pipes=[(12, 12)]))
    spawns = r.days(60)
    pipers = [s for s in spawns if s[1] == PIPERUNNER]
    ctx.log(f"Piperunners: {pipers}")
    ctx.check(pipers, "Piperunners spawn by a pipe")
    ctx.check(all((x, y) == (12, 12) and c == PIPE for _, _, x, y, c in pipers), "each stands on the pipe")
    ctx.check(not r.types() & SHIPS, "still no ship")


@test(modes=("ds",))
def bh_factory_ships_by_the_sea(ctx):
    """A door square next to the sea: ships (AW2's and Dual Strike's) spawn on free water squares next to the
    doors, never on land; land units never on water."""
    r = start(ctx, factory_map(ctx, sea=COAST, shoal=[(11, 13)], reef=[(9, 13)]))
    spawns = r.days(80)
    ships = [s for s in spawns if s[1] in SHIPS]
    ctx.log(f"ships: {names(ships)}")
    ctx.check(len(ships) >= 4, f"ships spawn ({len(ships)})")
    seen = {s[1] for s in ships}
    ctx.check(seen & NAVAL_AW2 and seen & {18, 26}, f"AW2's and Dual Strike's ships both: {sorted(seen)}")
    ctx.check(all((x, y) in NEAR for _, _, x, y, _ in ships), "ships are on the squares next to the doors")
    ctx.check(all(c in WATER for *_, c in ships), "ships are only on sea, shoal or reef")
    land = [s for s in spawns if s[1] not in SHIPS]
    ctx.check(all((x, y) in DOORS and c not in (SEA, REEF) for _, _, x, y, c in land), "land units on door tiles, none on water")
    ctx.check(MEGATANK in r.types() or OOZIUM in r.types(), "land Dual Strike units spawn too")
    ctx.check({s[1] for s in ships if (s[2], s[3]) == (11, 13)} <= {LANDER}, "the shoal takes only a Lander")


@test(modes=("ds",))
def bh_factory_no_ship_when_the_water_is_taken(ctx):
    """Every water square beside the doors held by enemy ships: no ship spawns; land units still do and
    none lands on a taken square."""
    taken = [(8, 12), (12, 12), (9, 13), (10, 13), (11, 13)]
    r = start(ctx, factory_map(ctx, sea=COAST, blockers=[("cruiser", x, y) for x, y in taken]), shots=())
    spawns = r.days(40)
    ctx.log(f"{len(spawns)} spawns, types {sorted(r.types())}")
    ctx.check(not r.types() & SHIPS, f"no ship spawns: {sorted(r.types())}")
    ctx.check(len(spawns) > 5 and all((x, y) in DOORS for _, _, x, y, _ in spawns), "land units spawn on the door tiles")
    ctx.check(all(u["army"] == 2 for u in r.g.units() if (u["x"], u["y"]) in taken), "the blockers are still there")


@test(modes=("ds",))
def bh_factory_doors_in_the_water(ctx):
    """Doors on the sea: only ships spawn (on the sea), never a land unit; the table's land units are dropped."""
    sea = [(x, y) for x in range(7, 14) for y in range(12, 16)]
    r = start(ctx, factory_map(ctx, sea=sea), shots=())
    spawns = r.days(40)
    ctx.log(f"{len(spawns)} spawns: {names(spawns)}")
    ctx.check(spawns, "something spawns")
    ctx.check(all(t in SHIPS for _, t, *_ in spawns), f"only ships: {sorted(r.types())}")
    ctx.check(all(c in WATER for *_, c in spawns), "all on water")


@test(modes=("aw2",))
def bh_factory_aw2_rules_without_the_pack(ctx):
    """Without the pack the factory spawns the table's units on the doors, by day, as AW2 does."""
    rom = open(paths.aw2_rom(), "rb").read()
    r = start(ctx, factory_map(ctx, sea=COAST), shots=())
    spawns = r.days(40)
    ctx.log(f"{len(spawns)} spawns")
    ctx.check(spawns, "something spawns")
    ok = all(t == table_unit(rom, d, x - 9) and (x, y) in DOORS for d, t, x, y, _ in spawns)
    ctx.check(ok, "each spawn is the table's unit for its day and slot, on its door")
    ctx.check(not r.types() & {MEGATANK, OOZIUM, PIPERUNNER, 18, 26}, "none of Dual Strike's units")


@test(modes=("aw2",))
def compat_bh_factory_byte_identical(ctx):
    """A Versus battle with a Black Factory plays the same as an older build without the pack."""
    other = os.environ.get("AW2TEST_COMPARE_RUNNER")
    if not other:
        raise Skip("AW2TEST_COMPARE_RUNNER not set")
    r = start(ctx, factory_map(ctx, sea=COAST), shots=())
    r.days(12)
    g = r.g
    g.e.wait(30)
    script = ctx.script(g, "replay.txt", tail=["dump end", "shot end"])
    save = os.path.join(ctx.out, "map.sav")
    dumps = {}
    for tag, runner in (("this build", paths.runner("aw2_script")), ("other build", other)):
        out = ctx.run_script(runner, script, save)
        ctx.log(f"{tag}: {out.strip().splitlines()[-1] if out.strip() else ''}")
        dumps[tag] = [open(os.path.join(ctx.out, "end" + ext), "rb").read() for ext in (".ewram", ".iwram")]
        for ext in (".ewram", ".iwram", ".bmp"):
            os.replace(os.path.join(ctx.out, "end" + ext), os.path.join(ctx.out, f"end_{tag.split()[0]}{ext}"))
    for i, (name, base) in enumerate((("EWRAM", 0x02000000), ("IWRAM", 0x03000000))):
        a, b = dumps["this build"][i], dumps["other build"][i]
        diff = [base + k for k in range(len(a)) if a[k] != b[k]]
        ctx.check(not diff, f"{name} identical to the other build ({len(diff)} bytes differ: {', '.join(hex(x) for x in diff[:12])})")


@test(modes=("ds",), netplay=True)
def netplay_bh_factory_spawns(ctx):
    """Both rollback peers and the straight replay agree on a coastal factory's spawns."""
    r = start(ctx, factory_map(ctx, sea=COAST), shots=())
    r.days(8)
    ctx.log(f"{len(r.spawns)} spawns: {names(r.spawns)}")
    identical, _, text = ctx.netplay_replay(r.g, [])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: both peers and the straight replay identical")
