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
FIVE_ON = 0x02030206
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

    def __init__(self, ctx, g, shots=(), keep=(), tag=""):
        self.ctx, self.g, self.e = ctx, g, g.e
        self.bh = next(a for a in (1, 2) if self.e.u8(g.players_base + 0x3C * a + 0x1A) == 5)
        self.other = 3 - self.bh
        self.base = {u["id"] for u in g.units()}
        self.spawns = []         # (day, type, x, y, terrain class)
        self.shots = set(shots)  # types to photograph the first time they spawn
        self.taken = set()
        self.tag = tag
        self.keep = set(keep)    # types left standing (the cost rule's one-at-a-time check)
        self.alive_max = {}
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
                pic(self.ctx, self.g, f"{self.tag}spawn_{romlib.UNIT_NAMES[u['type']].replace(' ', '_').lower()}_day{day}")
        for u in new:
            if u["type"] in self.keep:
                self.base.add(u["id"])
            else:
                self.purge(u)
        for t in self.keep:
            n = sum(1 for u in self.g.units(self.bh) if u["type"] == t)
            self.alive_max[t] = max(self.alive_max.get(t, 0), n)
        self.e.wait(4)

    def days(self, n):
        g = self.g
        for _ in range(n):
            if g.current_army() == self.bh:
                g.end_turn(human=self.other)
            g.end_turn(human=self.bh)
            self.harvest()
        return self.spawns

    def days_vs_cpu(self, n):
        """Only Black Hole is human: the other army's turns run on their own."""
        for _ in range(n):
            self.g.end_turn(human=self.bh)
            self.harvest()
        return self.spawns

    def types(self):
        return {s[1] for s in self.spawns}


def start(ctx, m, shots=(MEGATANK, OOZIUM, 22, 23, 26, 18, 21, 24), fog=False, keep=(), tag=""):
    return Run(ctx, ctx.start(m, ["andy", "vonbolt" if ctx.ds else "drake"], humans=(1, 2), fog=fog), shots=shots, keep=keep, tag=tag)


def table_unit(rom, day, slot):
    return rom[FACTORY_BLUES + (day & 0x1F) * 3 + slot]


def names(spawns):
    return [(d, romlib.UNIT_NAMES[t], x, y) for d, t, x, y, c in spawns]


ANTI_AIR, MISSILES, FIGHTER, BOMBER, BCOPTER = 14, 15, 16, 17, 19
SUB, BATTLESHIP, CRUISER = 24, 21, 22
INFANTRY, MECH, RECON, TANK, MD_TANK, NEOTANK, ARTILLERY, ROCKETS = 1, 2, 6, 5, 3, 8, 10, 11
HEAVY = (MEGATANK, BATTLESHIP, 26, OOZIUM)
SEA_FAR = COAST + [(x, y) for x in range(5, 17) for y in range(16, 20)] + [(x, 12) for x in range(5, 8)]
AIR_ARMY = [("bcopter", 14, 4), ("bcopter", 15, 5), ("bcopter", 16, 4), ("fighter", 15, 3), ("fighter", 17, 5), ("bomber", 16, 6)]
GROUND_ARMY = [("infantry", 14, 4), ("tank", 15, 5), ("mech", 16, 4), ("infantry", 15, 3), ("tank", 17, 5), ("artillery", 16, 6)]
INFANTRY_ARMY = [("infantry", 14 + k % 4, 3 + k // 4) for k in range(8)]
SEA_ARMY = [("cruiser", 8, 18), ("battleship", 11, 17), ("sub", 14, 19), ("cruiser", 6, 17)]


def count(spawns, types):
    return sum(1 for s in spawns if s[1] in types)


def smart_log(ctx, r, n=6):
    lines = r.e.decisions()
    ctx.log(f"{len(lines)} decisions; the first {n}:\n" + "\n".join(l[:260] for l in lines[:n]))
    return lines


def place_unit(r, army, kind, x, y):
    """Put a full-strength unit of `army` on (x, y) in the running battle."""
    e, g = r.e, r.g
    live = {u["id"] for u in g.units()}
    per = 51 if e.u8(FIVE_ON) == 1 else 64
    uid = next(i for i in range(per * (army - 1) + 1, per * army) if i not in live)
    a = g.unit_addr(uid)
    t = romlib.unit_id(kind)
    for k in range(12):
        e.w8(a + k, 0)
    e.w8(a, t)
    e.w8(a + 2, x)
    e.w8(a + 3, y)
    e.w16(a + 4, 100 | (9 << 7))
    e.w8(a + 6, 70)
    row = e.u16(ROWS + 2 * y)
    for plane in (UNIT_PLANE, ALL_PLANE):
        e.w8(plane + row + x, uid)
    count = g.players_base + 0x3C * army + 0x3A
    e.w8(count, e.u8(count) + 1)
    r.base.add(uid)


@test(modes=("ds",))
def bh_factory_smart_landlocked(ctx):
    """On a landlocked factory against a ground army the choice is land units only, on the door tiles, none on
    water, of several kinds; the cost rule holds (never dearer than the table's unit, with the floor)."""
    r = start(ctx, factory_map(ctx, blockers=GROUND_ARMY))
    spawns = r.days(40)
    smart_log(ctx, r)
    ctx.log(f"{len(spawns)} spawns: {names(spawns)}")
    ctx.check(len(spawns) > 15, f"spawns ({len(spawns)})")
    ctx.check(not r.types() & (SHIPS | {PIPERUNNER}), f"no ship, no Piperunner: {sorted(r.types())}")
    ctx.check(len(r.types()) >= 4, f"a mix of kinds: {sorted(r.types())}")
    ctx.check(all((x, y) in DOORS for _, _, x, y, _ in spawns), "every spawn is on a door tile")
    ctx.check(all(c not in (SEA, REEF) for *_, c in spawns), "no land unit on water")


@test(modes=("ds",))
def bh_factory_smart_vs_air(ctx):
    """Against an air army in sight Anti-Air and Missiles spawn far more than against a ground army (the same
    squares, the same days)."""
    air = start(ctx, factory_map(ctx, blockers=AIR_ARMY), shots=())
    sa = air.days(40)
    smart_log(ctx, air)
    ground = start(ctx, factory_map(ctx, blockers=GROUND_ARMY), shots=())
    sg = ground.days(40)
    aa, base = count(sa, (ANTI_AIR, MISSILES)), count(sg, (ANTI_AIR, MISSILES))
    ctx.log(f"Anti-Air/Missiles: {aa} of {len(sa)} against air, {base} of {len(sg)} against ground; fighters {count(sa, (FIGHTER,))}")
    ctx.check(aa >= 8 and aa >= base + 6, f"Anti-Air/Missiles answer air ({aa}) more than the baseline ({base})")


@test(modes=("ds",))
def bh_factory_smart_fog_is_fair(ctx):
    """With fog and the air army out of Black Hole's sight, the factory does not answer it: no more Anti-Air
    than against a ground army."""
    g = ctx.start(factory_map(ctx, blockers=AIR_ARMY), ["andy", "vonbolt"], humans=(1,), fog=True)
    r = Run(ctx, g, shots=())
    sp = r.days_vs_cpu(3)
    lines = smart_log(ctx, r, 3)
    n = count(sp, (ANTI_AIR, MISSILES))
    ctx.log(f"Anti-Air/Missiles with fog: {n} of {len(sp)}")
    ctx.check(lines and all(" foes 0 " in l or " foes 1 " in l for l in lines[:3]), "only the spare infantry is counted, not the air army Black Hole cannot see")
    ctx.check(n <= 1, f"the unseen air army is not answered ({n})")


@test(modes=("ds",))
def bh_factory_smart_vs_ships(ctx):
    """An enemy fleet on the sea by the doors: Subs, Battleships and Cruisers spawn on the water; land units
    stay on land."""
    r = start(ctx, factory_map(ctx, sea=SEA_FAR, blockers=SEA_ARMY), shots=(SUB, BATTLESHIP, CRUISER))
    sp = r.days(90)
    smart_log(ctx, r)
    ships = [s for s in sp if s[1] in SHIPS]
    ctx.log(f"ships: {names(ships)}")
    ctx.check(count(sp, (SUB, BATTLESHIP, CRUISER)) >= 4, f"Subs, Battleships and Cruisers answer the fleet ({count(sp, (SUB, BATTLESHIP, CRUISER))})")
    ctx.check(all((x, y) in NEAR and c in WATER for _, t, x, y, c in ships), "ships only on water beside the doors")
    ctx.check(all((x, y) in DOORS and c not in (SEA, REEF) for _, t, x, y, c in sp if t not in SHIPS), "land units on land doors")


@test(modes=("ds",))
def bh_factory_smart_vs_infantry(ctx):
    """An infantry horde: where the slot's table unit is worth 4000 or more (the factory may pick Recon and up) what
    spawns hurts infantry (Recon, Tanks, artillery, Oozium ...), never a Fighter, a ship or Infantry; on a cheaper slot
    the best it can afford (Mech) spawns."""
    rom = open(paths.aw2_rom(), "rb").read()
    r = start(ctx, factory_map(ctx, blockers=INFANTRY_ARMY), shots=())
    sp = r.days(40)
    smart_log(ctx, r)
    right = (RECON, TANK, MD_TANK, NEOTANK, MEGATANK, ARTILLERY, ROCKETS, BCOPTER, BOMBER, OOZIUM, ANTI_AIR)
    price = {1: 1000, 2: 3000, 3: 16000, 5: 7000, 6: 4000, 8: 22000, 10: 6000, 11: 15000, 14: 8000, 15: 12000, 16: 20000, 17: 22000, 19: 9000}
    big = [s for s in sp if price.get(table_unit(rom, s[0], s[2] - 9), 0) >= 4000]
    ctx.log(f"{names(sp)}")
    ctx.check(big and count(big, right) >= 0.9 * len(big), f"counters on the slots that can afford them ({count(big, right)} of {len(big)})")
    ctx.check(not r.types() & (SHIPS | {FIGHTER}), f"no ship or Fighter: {sorted(r.types())}")
    ctx.check(not count(big, (INFANTRY,)), "no Infantry where a counter could be had")


@test(modes=("ds",))
def bh_factory_smart_cost_rule(ctx):
    """The cost rule: a spawn is never dearer than its slot's table unit, but for the heavy units (Megatank,
    Battleship, Carrier, Oozium), which may cost 30% more and of which one at a time stands on Black Hole's side; so the factory spawns no more value than the table would."""
    rom = open(paths.aw2_rom(), "rb").read()
    r = start(ctx, factory_map(ctx, blockers=GROUND_ARMY), shots=(), keep=HEAVY)
    sp = r.days(40)
    smart_log(ctx, r, 2)
    price = {1: 1000, 2: 3000, 3: 16000, 4: 28000, 5: 7000, 6: 4000, 8: 22000, 10: 6000, 11: 15000, 14: 8000, 15: 12000,
             16: 20000, 17: 22000, 19: 9000, 21: 28000, 26: 30000, 27: 18900}
    ctx.log(f"most of one heavy unit standing at once: {r.alive_max}")
    ctx.check(all(v <= 1 for v in r.alive_max.values()), f"one heavy unit of each kind at a time: {r.alive_max}")
    ok = True
    spawned = table = 0
    for d, t, x, y, c in sp:
        slot_price = price.get(table_unit(rom, d, x - 9), 0)
        spawned += price.get(t, 0)
        table += slot_price
        ok &= price.get(t, 0) * 10 <= slot_price * (13 if t in HEAVY else 10)
    ctx.log(f"value spawned {spawned}, the table's units for the same slots {table}")
    ctx.check(ok, "no spawn dearer than its slot's table unit (heavy ones 30% more)")
    ctx.check(spawned <= table * 1.2, f"the value spawned ({spawned}) stays near the table's ({table})")


@test(modes=("ds",))
def bh_factory_smart_follows_the_battle(ctx):
    """The same factory picks differently on different days because the battle changed: the enemy army grows an
    air force, and Anti-Air appears only after it is there."""
    m = factory_map(ctx, blockers=[("infantry", 14, 4), ("tank", 15, 5)])
    r = start(ctx, m, shots=())
    early = list(r.days(12))
    g = r.g
    # Bring air units into the enemy army (Black Hole sees them: fog is off).
    for kind, x, y in [("bcopter", 14, 8), ("bcopter", 15, 8), ("fighter", 16, 8), ("fighter", 13, 8)]:
        place_unit(r, 2, kind, x, y)
    late = r.days(28)[len(early):]
    smart_log(ctx, r, 2)
    ctx.log(f"Anti-Air/Missiles: {count(early, (ANTI_AIR, MISSILES))} of {len(early)} before, {count(late, (ANTI_AIR, MISSILES))} of {len(late)} after")
    ctx.check(count(late, (ANTI_AIR, MISSILES)) >= count(early, (ANTI_AIR, MISSILES)) + 4, "the air force changes what the factory builds")


RNG_AT = 0x03001FD4
SEEDS = [0x00000001, 0x1234ABCD, 0x7FFFFFFF, 0x2468ACE0, 0xDEADBEEF, 0x0BADF00D, 0x31415926, 0xCAFEBABE, 0x13579BDF, 0x55AA55AA]
POOL_PRICE = {1: 1000, 2: 3000, 3: 16000, 4: 28000, 5: 7000, 6: 4000, 8: 22000, 10: 6000, 11: 15000, 14: 8000, 15: 12000,
              16: 20000, 17: 22000, 19: 9000, 21: 28000, 22: 18000, 23: 12000, 24: 20000, 18: 7500, 26: 30000, 27: 18900, 9: 20000}


def one_turn_at(ctx, r, cp, seed, table_only=False, day=19):
    """Back to the checkpoint (the other army to move), the game's RNG set to `seed` (and the day), then Black Hole's
    turn: returns (spawns of that turn, decision lines it logged, the RNG when the turn began)."""
    from aw2test import twofront
    e, g = r.e, r.g
    twofront.back_to(e, g, cp)
    e.w32(RNG_AT, seed)
    e.w16(DAY, day)
    e.w8(0x0203E3FF, 1 if table_only else 0)
    first = len(e.decisions())
    mark = len(r.spawns)
    g.end_turn(human=r.bh)
    r.harvest()
    return r.spawns[mark:], e.decisions()[first:], e.u32(RNG_AT)


def parse_pool(line):
    import re
    m = re.search(r"\| pool (.*?) \| then", line)
    return [(n, int(v), int(w)) for n, v, w in re.findall(r"(.+?) (-?\d+) w(\d+)(?:, |$)", m.group(1))] if m else []


@test(modes=("ds",))
def bh_factory_pick_varies_with_the_rng(ctx):
    """The smart choice is drawn, weighted by score, among the best two or three candidates (within 15% of the best,
    at least 6 points), from the game's RNG state mixed with the day, door, army and square: the same battle on the same
    day picks differently from different RNG states, every pick is one of the allowed top candidates and still
    obeys the cost rule, ships on water and land units on land."""
    from aw2test import twofront
    r = start(ctx, factory_map(ctx, blockers=GROUND_ARMY), shots=())
    g, e = r.g, r.e
    ctx.check(r.bh == 1, "Black Hole is army 1 (the day set at the checkpoint, 19, becomes 20 at its turn)")
    to_army(g, 2)
    cp = twofront.checkpoint(e, ctx, "before_black_holes_turn")
    rows = []
    for seed in SEEDS:
        spawns, lines, _ = one_turn_at(ctx, r, cp, seed)
        rows.append((seed, spawns, lines))
        ctx.log(f"RNG {seed:08X}: {names(spawns)}")
    picks = [tuple((s[1], s[2]) for s in sp) for _, sp, _ in rows]
    # (The Mech Black Hole spawned on day 1 stands on the middle door, which blocks that slot: two spawn.)
    ctx.check(all(len(p) == 2 for p in picks) and all(sp[0][0] == 20 for _, sp, _ in rows), "the table's open slots spawn something on day 20")
    ctx.check(len(set(picks)) >= 4, f"different RNG states give different spawns ({len(set(picks))} different of {len(picks)})")
    for slot in range(2):
        kinds = {p[slot][0] for p in picks}
        ctx.check(len(kinds) >= 2, f"door {slot + 1} does not always spawn the same unit ({sorted(romlib.UNIT_NAMES[k] for k in kinds)})")
    ctx.check(any(p[0][0] != p[1][0] for p in picks) and any(p[0][0] == p[1][0] for p in picks), "the doors neither always pick alike nor always differ")
    rom = open(paths.aw2_rom(), "rb").read()
    pooled = bad = 0
    best_picked = other_picked = 0
    for seed, spawns, lines in rows:
        for line, sp in zip(lines, spawns):
            pool = parse_pool(line)
            name = line.split(" -> ")[1].split(" at (")[0]
            best = pool[0][1]
            pooled += len(pool) > 1
            floor = best - max(6, abs(best) * 15 // 100)
            ok = (name in [p[0] for p in pool] and len(pool) <= 3 and all(p[1] >= floor for p in pool)
                  and all(pool[i][1] >= pool[i + 1][1] for i in range(len(pool) - 1)))
            bad += not ok
            best_picked += name == pool[0][0]
            other_picked += name != pool[0][0]
            d, t, x, y, c = sp
            slot_price = POOL_PRICE.get(table_unit(rom, d, x - 9), 0)
            heavy = t in HEAVY
            ok_cost = POOL_PRICE.get(t, 0) * 10 <= slot_price * (13 if heavy else 10)
            bad += not ok_cost
            if t in SHIPS:
                bad += c not in WATER
            else:
                bad += c in (SEA, REEF)
    ctx.log(f"{pooled} of {sum(len(l) for _, _, l in rows)} decisions had a pool of two or three; best picked {best_picked}, another {other_picked}")
    ctx.check(pooled >= 6, "most decisions have two or three candidates close enough to draw from")
    ctx.check(other_picked >= 3 and best_picked > other_picked, "the best scorer is picked most often, but not always")
    ctx.eq(bad, 0, "every pick is one of the allowed top candidates, within the cost rule and its terrain")


@test(modes=("ds",))
def bh_factory_choice_leaves_the_rng_alone(ctx):
    """The choice only reads the game's RNG: the same turn from the same RNG state with the smart factory and with
    the table's units (the development byte) leaves the same RNG state, so the battle's luck is the game's own."""
    from aw2test import twofront
    r = start(ctx, factory_map(ctx, blockers=GROUND_ARMY), shots=())
    g, e = r.g, r.e
    to_army(g, 2)
    cp = twofront.checkpoint(e, ctx, "before_black_holes_turn")
    for seed in SEEDS[:5]:
        smart, lines, rng_smart = one_turn_at(ctx, r, cp, seed)
        table, _, rng_table = one_turn_at(ctx, r, cp, seed, table_only=True)
        ctx.log(f"RNG {seed:08X}: after the turn smart {rng_smart:08X} table {rng_table:08X}; smart {names(smart)}; table {names(table)}")
        ctx.check(lines and rng_smart == rng_table, f"RNG {seed:08X}: the same state after the turn with the smart choice and with the table")


@test(modes=("ds",))
def bh_factory_never_a_piperunner(ctx):
    """The Black Factory never builds a Piperunner: not by a long pipe to the enemy, not by a short one, over many
    days and several RNG states."""
    from aw2test import twofront
    line = [(12, 12)] + [(12, y) for y in range(13, 20)] + [(x, 19) for x in range(13, 29)]
    for pipes in (line, [(12, 12)]):
        r = start(ctx, factory_map(ctx, pipes=pipes, blockers=[("infantry", 14, 4)]), shots=())
        sp = r.days(40)
        ctx.log(f"{len(sp)} spawns by {len(pipes)} pipe cells: {sorted(r.types())}")
        ctx.check(len(sp) > 10, "the factory spawns")
        ctx.check(PIPERUNNER not in r.types(), f"no Piperunner ({len(pipes)} pipe cells)")
    r = start(ctx, factory_map(ctx, pipes=line, blockers=GROUND_ARMY), shots=())
    to_army(r.g, 2)
    cp = twofront.checkpoint(r.e, ctx, "before_black_holes_turn")
    seen = set()
    for seed in SEEDS[:4]:
        for day in (6, 7, 13, 21, 27):
            sp, _, _ = one_turn_at(ctx, r, cp, seed, day=day)
            seen |= {s[1] for s in sp}
    ctx.log(f"types over 20 seeded turns: {sorted(seen)}")
    ctx.check(seen and PIPERUNNER not in seen, "no Piperunner in 20 seeded turns")


@test(modes=("ds",))
def bh_factory_no_ship_without_sea_at_the_doors(ctx):
    """A factory with sea in the map but none on the squares it spawns onto never builds a naval unit."""
    from aw2test import twofront
    far = [(x, y) for x in range(5, 25) for y in range(16, 20)]
    r = start(ctx, factory_map(ctx, sea=far, blockers=SEA_ARMY), shots=())
    sp = r.days(40)
    ctx.check(len(sp) > 10, "the factory spawns")
    ctx.check(not r.types() & SHIPS, f"no ship: {sorted(r.types())}")
    to_army(r.g, 2)
    cp = twofront.checkpoint(r.e, ctx, "before_black_holes_turn")
    seen = set()
    for seed in SEEDS[:4]:
        for day in (5, 12, 19, 26):
            seen |= {s[1] for s in one_turn_at(ctx, r, cp, seed, day=day)[0]}
    ctx.check(seen and not seen & SHIPS, f"no ship in 16 seeded turns: {sorted(seen)}")


@test(modes=("ds",))
def bh_factory_ships_by_the_sea(ctx):
    """A door square next to the sea, enemy beyond the water: ships spawn only on free water squares next to the
    doors, never on land; land units never on water; a shoal takes only a Lander."""
    r = start(ctx, factory_map(ctx, sea=SEA_FAR, shoal=[(11, 13)], reef=[(9, 13)], blockers=SEA_ARMY))
    spawns = r.days(60)
    ships = [s for s in spawns if s[1] in SHIPS]
    ctx.log(f"ships: {names(ships)}")
    ctx.check(len(ships) >= 4, f"ships spawn ({len(ships)})")
    ctx.check(all((x, y) in NEAR for _, _, x, y, _ in ships), "ships are on the squares next to the doors")
    ctx.check(all(c in WATER for *_, c in ships), "ships are only on sea, shoal or reef")
    land = [s for s in spawns if s[1] not in SHIPS]
    ctx.check(all((x, y) in DOORS and c not in (SEA, REEF) for _, _, x, y, c in land), "land units on door tiles, none on water")
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


# --- Pictures: a properly drawn map, a CPU Black Hole army at the game's own pace ----------------------------

PICS = os.environ.get("AW2TEST_BH_PICS")


def drawn_map(ctx, coast, economy=False):
    """A 30x20 Versus design map drawn with five/map.py's tiles (real sea edges, reefs, shoals, a Black Factory
    with its footprint): Black Hole (a CPU) holds the top left, its factory's doors on (4..6, 5); with
    `coast` the sea washes up to them from the west and south."""
    import importlib.util
    five = os.path.join(paths.REPO, "tango-gamesupport-aw2", "five")
    spec = importlib.util.spec_from_file_location("five_map_py_bh", os.path.join(five, "map.py"))
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    W, H = 30, 20
    g = [["."] * W for _ in range(H)]
    for x, y in [(12, 4), (13, 5), (20, 3), (22, 9), (18, 12), (9, 15), (25, 6), (14, 9)]:
        g[y][x] = "f"
    for x, y in [(11, 11), (12, 11), (23, 14), (24, 14), (8, 12)]:
        g[y][x] = "^"
    for x in range(4, 26):
        g[10][x] = "R"
    for y in range(10, 18):
        g[y][27] = "R"
    for dy, row in enumerate(["###", "###", "#F#", "###"]):
        for dx, c in enumerate(row):
            g[1 + dy][4 + dx] = c
    if coast:
        for x in range(0, 9):
            for y in range(6, 12):
                g[y][x] = "~"
        for y in range(3, 6):
            for x in range(0, 3):
                g[y][x] = "~"
        for x in range(1, 8):
            g[12][x] = ","
        g[5][7] = "~"
        g[8][5] = "r"
        g[8][2] = "r"
    g[3][12] = "1"
    g[17][26] = "2"
    if economy:
        # Each side: two bases and three cities (Black Hole's army also has the factory).
        for (x, y), c in {(10, 2): "B", (14, 2): "B", (16, 4): "C", (10, 7): "C", (15, 7): "C",
                          (24, 18): "B", (28, 16): "B", (22, 17): "C", (26, 13): "C", (20, 15): "C"}.items():
            g[y][x] = c
    m = {"name": "bh pictures", "units": {}, "rows": ["".join(r) for r in g], "armies": 2, "tab": 3, "colours": [1, 5], "wasteland": False}
    rom = open(paths.aw2_rom(), "rb").read()
    tiles = mp.tiles(m, mp.sea_edges(rom))
    d = ctx.map(hq=())
    for y in range(H):
        for x in range(W):
            d.tiles[y * W + x] = tiles[y][x]
    d.terrain(12, 3, "hq", 1).terrain(26, 17, "hq", 2)
    d.colours = [1, 5, 2, 3, 4]
    if economy:
        for k in range(3):
            d.unit(1, "infantry", 13 + k, 3)
            d.unit(2, "infantry", 25 - k, 17)
        return d
    d.unit(1, "infantry", 13, 3)
    for k in range(8):
        d.unit(2, "infantry", 22 + k % 4, 17 + k // 4)
    return d


def pic(ctx, g, name):
    ctx.shot(g, name)
    if PICS:
        os.makedirs(PICS, exist_ok=True)
        g.e.shot(os.path.join(PICS, name))


def play_pictures(ctx, coast, days, want):
    """Army 1 (human) ends its turn each day; the CPU Black Hole army's turn runs at the game's pace; a picture is
    taken the frame its factory has spawned (before its units move away)."""
    g = ctx.start(drawn_map(ctx, coast), ["andy", "vonbolt"], humans=(2,))
    e = g.e
    bh = next(a for a in (1, 2) if e.u8(g.players_base + 0x3C * a + 0x1A) == 5)
    human = 3 - bh
    ctx.eq(e.u8(g.players_base + 0x3C * bh + 0x1B), 2, "Black Hole is the CPU")
    seen = {u["id"] for u in g.units()}
    got, log = set(), []
    for day in range(days):
        if g.current_army() != human:
            g.wait_for_input()
        g.goto(0, 0)
        g.goto(6, 2)  # the cursor (and so the camera) on the factory for the CPU's turn
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
        spawned = []
        for _ in range(1200):
            e.wait(1)
            if g.current_army() == bh:
                spawned = [u for u in g.units(bh) if u["id"] not in seen]
                if spawned:
                    break
        d = e.u16(DAY)
        for u in spawned:
            seen.add(u["id"])
            log.append((d, romlib.UNIT_NAMES[u["type"]], u["x"], u["y"]))
        if spawned:
            kinds = {u["type"] for u in spawned}
            tag = "_".join(sorted(romlib.UNIT_NAMES[t].replace(" ", "").lower() for t in kinds))
            pic(ctx, g, f"{'coast' if coast else 'inland'}_day{d:02d}_{tag}")
            got |= kinds
        if not e.wait_until(lambda: g.current_army() == human, 20000, step=30):
            ctx.log(f"day {d}: the turn did not come back")
            break
        ctx.log(f"day {d}: Black Hole at {[(u['type'], u['x'], u['y']) for u in g.units(bh)]}")
        seen |= {u["id"] for u in g.units()}
        g.wait_for_input()
    ctx.log(f"spawns: {log}")
    return log


@test(modes=("ds",))
def bh_factory_pictures_coast(ctx):
    """Pictures: a CPU Black Hole's factory by the sea, on a properly drawn map: whatever spawns stands on a legal
    square (ships only on water beside the doors, land units on the doors)."""
    log = play_pictures(ctx, True, 24, set())
    kinds = {romlib.UNIT_IDS[n.lower().replace(" ", "").replace("-", "")] for _, n, _, _ in log}
    ctx.check(len(kinds) >= 4, f"a mix of units spawned: {sorted(kinds)}")
    doors = {(4, 5), (5, 5), (6, 5)}
    ctx.check(all((x, y) in doors or romlib.UNIT_IDS[n.lower().replace(" ", "").replace("-", "")] in SHIPS for _, n, x, y in log),
              "land units on the door tiles")


@test(modes=("ds",))
def bh_factory_pictures_inland(ctx):
    """Pictures: the same map without the sea, over several days: land and air units only."""
    log = play_pictures(ctx, False, 12, set())
    kinds = {romlib.UNIT_IDS[n.lower().replace(" ", "").replace("-", "")] for _, n, _, _ in log}
    ctx.check(kinds and not kinds & SHIPS, f"no ship inland: {sorted(kinds)}")


# --- The factory can be destroyed in Versus (crate::factory_hp) -------------------------------------------

INVENTIONS_AT = 0x02028360
FACTORY_KIND = 7
TARGET = (10, 11)   # the middle of the factory's bottom row (its footprint is (9..11, 8..11))


def factory_entry(e):
    for k in range(16):
        a = INVENTIONS_AT + 8 * k
        w = e.u16(a + 2)
        if w & 0x3C0 == 0:
            return None
        if (w >> 6) & 15 == FACTORY_KIND:
            return a
    return None


def factory_hp(e):
    return e.u8(factory_entry(e) + 4)


def to_army(g, army):
    if g.current_army() != army:
        g.end_turn(human=army)


def shoot(g, src, dst, target=TARGET):
    g.select(*src)
    g.move_to(*dst)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(*target)
    g.wait_for_input()


def attack_map(ctx, units):
    return factory_map(ctx, blockers=units)


@test()
def bh_factory_hit_points(ctx):
    """With the pack, in Versus, the factory has 200 hit points (twice a Black Cannon's 99); without it, none, as AW2's
    own."""
    r = start(ctx, factory_map(ctx), shots=())
    ctx.eq(factory_hp(r.e), 200 if ctx.ds else 0, "the factory's hit points")


@test(modes=("aw2",))
def bh_factory_not_attackable_without_the_pack(ctx):
    """Without the pack a unit beside the factory has nothing to Fire at."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    g = r.g
    to_army(g, 2)
    g.select(10, 12)
    names = g.move_to(10, 12)["names"]
    ctx.log(f"menu: {names}")
    ctx.check("Fire" not in names, "no Fire at the factory")
    ctx.eq(factory_hp(r.e), 0, "its hit points stay 0")


@test(modes=("ds",))
def bh_factory_hit_direct(ctx):
    """A Tank beside the factory fires at it: it loses what a Black Cannon would (a Tank's 16), so 200 - 16 = 184 are
    left, the terrain panel shows the three digits, and a Black Cannon takes the same from the same Tank."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    g, e = r.g, r.e
    to_army(g, 2)
    shoot(g, (10, 12), (10, 12))
    hp = factory_hp(e)
    ctx.check(100 < hp < 200, f"the factory took the Tank's shot: 200 -> {hp}")
    g.goto(*TARGET)
    e.wait(20)
    pic(ctx, g, "factory_attacked")
    # The same Tank against a Black Cannon (facing down; its target is the middle of its bottom row).
    m = ctx.map()
    m.terrain(10, 10, 0x187)
    m.unit(2, "tank", 10, 13)
    g2 = ctx.start(m, ["andy", "vonbolt"], humans=(1, 2))
    to_army(g2, 2)
    e2 = g2.e
    cannon = INVENTIONS_AT
    tx, ty = e2.u8(cannon) + 1, e2.u8(cannon + 1) + 2
    chp = e2.u8(cannon + 4)
    g2.select(10, 13)
    g2.move_to(tx, ty + 1)
    g2.choose("Fire", g2.ACTION_MENU)
    g2.pick_target(tx, ty)
    g2.wait_for_input()
    ctx.eq(e2.u8(cannon + 4), chp - (200 - hp), "a Black Cannon takes the same damage")


def refill(g, x, y):
    """The unit at (x, y) back to full strength and ammunition (a Tank has only nine shots)."""
    u = g.unit_at(x, y)
    g.e.w16(g.unit_addr(u["id"]) + 4, 100 | (9 << 7))
    g.e.w8(g.unit_addr(u["id"]) + 6, 70)


@test(modes=("ds",))
def bh_factory_takes_twice_the_hits(ctx):
    """A Tank (at full strength each turn) shoots the factory until it falls: every hit takes the same 16, so the factory
    shows 200, then 184, 168 ... and is destroyed at 0 after 13 hits, where a Black Cannon's 99 hit points take 7
    of the same shots; the panel's three digits are photographed on the way."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    g, e = r.g, r.e
    seen = [factory_hp(e)]
    ctx.eq(seen[0], 200, "a fresh factory has 200 hit points")
    to_army(g, 2)
    for k in range(20):
        if k:
            g.end_turn(human=1)
            g.end_turn(human=2)
            refill(g, 10, 12)
        shoot(g, (10, 12), (10, 12))
        seen.append(factory_hp(e))
        if k in (0, 5):
            g.goto(*TARGET)
            e.wait(20)
            pic(ctx, g, f"factory_hp_{seen[-1]}")
        if seen[-1] == 0 or g.battle_over():
            break
    ctx.log(f"hit points after each hit: {seen}")
    hits = len(seen) - 1
    d = 200 - seen[1]
    ctx.eq(d, 16, "a Tank's hit takes 16, as from a Black Cannon")
    ctx.check(all(a - b == d for a, b in zip(seen[:-2], seen[1:-1])), "every hit takes the same")
    ctx.eq(seen[-1], 0, "destroyed at 0")
    ctx.eq(hits, -(-200 // d), f"{hits} hits destroy it ({200} / {d}); a Black Cannon's 99 take {-(-99 // d)}")
    ctx.check(not g.battle_over(), "the battle goes on")


@test(modes=("ds",))
def bh_factory_panel_shows_three_digits(ctx):
    """The terrain panel draws the factory's hit points in three digits (it draws two for anything else), the heart
    shifted left to make room: photographed at 200, 184, 100 and 99 (two digits, the heart where it always is) and
    10."""
    r = start(ctx, factory_map(ctx), shots=())
    g, e = r.g, r.e
    a = factory_entry(e)
    for hp in (200, 184, 100, 99, 10, 1):
        e.w8(a + 4, hp)
        g.goto(*TARGET)
        e.wait(14)
        pic(ctx, g, f"panel_{hp}")
        e.wait(10)
        pic(ctx, g, f"panel_{hp}_b")
    ctx.eq(factory_hp(e), 1, "(the pictures only)")


@test(modes=("ds",))
def bh_factory_hit_indirect(ctx):
    """An Artillery three squares away fires at the factory without moving."""
    r = start(ctx, factory_map(ctx, blockers=[("artillery", 10, 14)]), shots=())
    g, e = r.g, r.e
    to_army(g, 2)
    shoot(g, (10, 14), (10, 14))
    hp = factory_hp(e)
    ctx.check(hp < 200, f"the factory took the Artillery's shot: 200 -> {hp}")


def destroy(ctx, r, pictures=True):
    """Army 2's Tank at the door finishes a factory brought down to 10 hit points."""
    g, e = r.g, r.e
    to_army(g, 2)
    e.w8(factory_entry(e) + 4, 10)
    g.select(10, 12)
    g.move_to(10, 12)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(*TARGET)
    if pictures:
        for k in range(3):
            e.wait(14)
            pic(ctx, g, f"factory_destroyed_f{k}")
    g.wait_for_input()
    g.goto(*TARGET)
    e.wait(30)
    pic(ctx, g, "factory_ruin")


@test(modes=("ds",))
def bh_factory_destroyed(ctx):
    """At 0 hit points the factory is destroyed (the Black Cannon's explosion and ruin): it spawns nothing any more,
    can not be fired at, and the battle goes on."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    g, e = r.g, r.e
    n0 = len(g.units(r.bh))
    destroy(ctx, r)
    ctx.eq(factory_hp(e), 0, "destroyed")
    ctx.check(not g.battle_over(), "the battle is not over")
    g.end_turn(human=1)
    g.end_turn(human=2)
    g.end_turn(human=1)
    g.end_turn(human=2)
    ctx.eq(len([u for u in g.units(r.bh)]), n0, "Black Hole's doors spawn nothing any more")
    ctx.check(not g.battle_over(), "the battle goes on after Black Hole's turns")
    g.select(10, 12)
    names = g.move_to(10, 12)["names"]
    ctx.check("Fire" not in names, f"nothing left to Fire at ({names})")
    g.e.press("B", 4)
    pic(ctx, g, "factory_ruin_later")


@test(modes=("ds",))
def bh_factory_spawns_until_destroyed(ctx):
    """Control: the same battle with the factory untouched keeps spawning."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    g = r.g
    n0 = len(g.units(r.bh))
    g.end_turn(human=2)
    g.end_turn(human=1)
    g.end_turn(human=2)
    ctx.check(len(g.units(r.bh)) > n0, f"Black Hole's units: {n0} -> {len(g.units(r.bh))}")


def boot_save(ctx, path):
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=path, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


@test(modes=("ds",))
def bh_factory_hit_points_survive_suspend(ctx):
    """Suspended from the map menu, rebooted and continued: a damaged factory has its hit points, a destroyed one
    stays destroyed (and spawns nothing)."""
    from aw2test import saves
    for label, finish in (("damaged", False), ("destroyed", True)):
        r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
        g, e = r.g, r.e
        if finish:
            destroy(ctx, r, pictures=False)
        else:
            to_army(g, 2)
            shoot(g, (10, 12), (10, 12))
        hp = factory_hp(e)
        ctx.check(0 < hp < 200 if not finish else hp == 0, f"{label}: {hp} hit points before the suspend")
        saves.suspend(g)
        img = saves.flash(e, os.path.join(ctx.out, f"suspended_{label}"))
        e.close()
        e2, g2 = boot_save(ctx, img.path)
        saves.to_select_mode(e2)
        saves.versus_continue(g2)
        ctx.eq(factory_hp(e2), hp, f"{label}: the continued battle's factory hit points")
        if finish:
            g2.goto(*TARGET)
            e2.wait(30)
            ctx.check(wreck_tiles_in_place(ctx, e2), "the continued battle draws the wreck from the game's own tiles")
            pic(ctx, g2, "factory_wreck_continued")
        g2.end_turn(human=1) if g2.current_army() == 2 else None
        ctx.check(not g2.battle_over(), f"{label}: the continued battle goes on")
        e2.close()


@test(modes=("ds",), netplay=True)
def netplay_bh_factory_destroyed(ctx):
    """Both rollback peers and the straight replay agree on a battle in which the factory is shot down."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    destroy(ctx, r, pictures=False)
    r.g.end_turn(human=1)
    r.g.end_turn(human=2)
    identical, _, text = ctx.netplay_replay(r.g, [])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: both peers and the straight replay identical")


@test(modes=("ds",))
def bh_factory_cpu_attacks_a_players_factory(ctx):
    """The CPU's Tank beside a human Black Hole army's factory hits it on its turn (with nothing else in range to
    shoot at); the battle goes on."""
    for fog in (False, True):
        cpu_strike(ctx, fog)


def cpu_strike(ctx, fog):
    m = factory_map(ctx, blockers=[("tank", 11, 11)])
    g = ctx.start(m, ["andy", "vonbolt"], humans=(1,), fog=fog)
    e = g.e
    hp0 = factory_hp(e)
    g.end_turn(human=1)
    hp1 = factory_hp(e)
    ctx.log("strikes: " + "; ".join(l for l in e.decisions() if l.startswith("strike")))
    ctx.check(hp1 < hp0, f"fog {fog}: the CPU's Tank hit the factory on its first turn ({hp0} -> {hp1})")
    g.goto(*TARGET)
    e.wait(30)
    pic(ctx, g, "cpu_strike_fog" if fog else "cpu_strike")
    for _ in range(3):
        g.end_turn(human=1)
    ctx.check(not g.battle_over(), "the battle goes on")


# --- Balance: CPU against CPU, the smart factory against the table's (AW2TEST_BH_BALANCE=1) ------------------

BALANCE = os.environ.get("AW2TEST_BH_BALANCE")
BALANCE_DAYS = int(os.environ.get("AW2TEST_BH_BALANCE_DAYS", "30"))
TABLE_ONLY_AT = 0x0203E3FF
UNIT_PRICE = {1: 1000, 2: 3000, 3: 16000, 4: 28000, 5: 7000, 6: 4000, 7: 5000, 8: 22000, 9: 20000, 10: 6000, 11: 15000,
              12: 24000, 13: 25000, 14: 8000, 15: 12000, 16: 20000, 17: 22000, 18: 7500, 19: 9000, 20: 5000,
              21: 28000, 22: 18000, 23: 12000, 24: 20000, 26: 30000, 27: 18900}
PAIRS = [("andy", "kanbei"), ("kanbei", "andy"), ("max", "sami"), ("sami", "max"), ("grit", "drake"), ("drake", "grit")]
HQS = {1: (12, 3), 2: (26, 17)}


def army_value(g, army):
    return sum(UNIT_PRICE.get(u["type"], 0) * ((u["hp"] + 9) // 10) // 10 for u in g.units(army))


def balance_game(ctx, coast, table, pair):
    import json
    from aw2test.emu import Emu
    from aw2test.game import Game
    save = os.path.join(ctx.out, "map.sav")
    drawn_map(ctx, coast, economy=True).write(paths.base_save(), save)
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    g.boot_to_teams()
    g.set_teams(list(pair), set())          # no human: the CPU plays both armies
    g.teams_to_rules()
    g.set_rules(fog=False, weather="clear", power=True, visuals="off")
    g.start_battle()
    if table:
        e.w8(TABLE_ONLY_AT, 1)
    bh = next(a for a in (1, 2) if e.u8(g.players_base + 0x3C * a + 0x1A) == 5)
    other = 3 - bh
    days = []
    last = 0
    over = False
    for _ in range(4000):
        e.wait(240)
        if g.battle_over():
            over = True
            break
        d = e.u16(DAY)
        if d != last:
            last = d
            days.append({"day": d, "bh": army_value(g, bh), "other": army_value(g, other), "bh_units": len(g.units(bh)),
                         "other_units": len(g.units(other))})
        if d > BALANCE_DAYS:
            break
        if not g.units(other) or not g.units(bh):
            over = True        # one army is wiped out: the battle is decided
            break
    hq = {a: (g.terrain_class(*HQS[a]) & 0x1F) == 8 for a in (1, 2)}
    result = {"coast": coast, "table": table, "pair": pair, "bh": bh, "days": days, "over": over, "hq_standing": hq,
              "final_bh": army_value(g, bh), "final_other": army_value(g, other), "spawns": len(e.decisions())}
    if over:
        result["winner"] = bh if (hq[other] is False or not g.units(other)) and hq[bh] else (other if not hq[bh] or not g.units(bh) else None)
    with open(os.path.join(ctx.out, "balance.json"), "w") as f:
        json.dump(result, f)
    with open(os.path.join(ctx.out, "decisions.txt"), "w") as f:
        f.write("\n".join(e.decisions()) + "\n")
    ctx.log(json.dumps({k: v for k, v in result.items() if k != "days"}))
    ctx.log("days: " + " ".join(f"{d['day']}:{d['bh']}/{d['other']}" for d in days))
    return result


def _balance_test(coast, table, k):
    def fn(ctx):
        if not BALANCE:
            raise Skip("AW2TEST_BH_BALANCE not set")
        balance_game(ctx, coast, table, PAIRS[k])
    fn.__name__ = f"bh_balance_{'coast' if coast else 'inland'}_{'table' if table else 'smart'}_{k}"
    test(modes=("ds",))(fn)


for _coast in (True, False):
    for _table in (False, True):
        for _k in range(len(PAIRS)):
            _balance_test(_coast, _table, _k)


# --- The same battle with the table's factory and the smart one (AW2TEST_BH_COMPARE=<dir>) -----------------------

COMPARE = os.environ.get("AW2TEST_BH_COMPARE")
COMPARE_DAYS = 22


def on_factory(g):
    """Units standing on the factory's building squares (its 3x4 footprint, the doors' row excluded)."""
    ent = factory_entry(g.e)
    if ent is None:
        return []
    x0, y0 = g.e.u8(ent), g.e.u8(ent + 1)
    w, h = g.e.u8(ent + 2) & 7, (g.e.u8(ent + 2) >> 3) & 7
    return [u for u in g.units() if x0 <= u["x"] < x0 + w and y0 <= u["y"] < y0 + h and not u["flags"] & 0x08]


class _Shim:
    """What place_unit needs of a Run."""

    def __init__(self, g):
        self.g, self.e, self.base = g, g.e, set()


def photograph(e, out, name, n=8):
    """Pictures over the next frames of the CPU's turn (the camera is the game's own, never moved from here: a moved
    camera draws the units and the building out of step), each with the scroll it was taken at; returns the names and
    scrolls, and the sheet picks the one with the factory best in view."""
    taken = []
    for k in range(n):
        shot = f"{name}_{k}"
        e.shot(os.path.join(out, shot))
        taken.append((shot, e.u16(MAP + 4), e.u16(MAP + 6)))
        e.wait(6)
    return taken


def compare_run(ctx, coast, table):
    """Black Hole is the CPU, the other army a human who only ends its turns; on day 8 the enemy changes: an air force
    appears (inland) or a fleet appears on the sea by the factory (coast). Each day's spawn is photographed (the camera
    on the factory); returns what spawned and Black Hole's army value by day."""
    import json
    g = ctx.start(drawn_map(ctx, coast), ["andy", "vonbolt"], humans=(2,))
    e = g.e
    if table:
        e.w8(TABLE_ONLY_AT, 1)
    bh = next(a for a in (1, 2) if e.u8(g.players_base + 0x3C * a + 0x1A) == 5)
    human = 3 - bh
    shim = _Shim(g)
    seen = {u["id"] for u in g.units()}
    frames, values, day_seen = [], {}, 0
    inside = set()
    injected = False
    for _ in range(COMPARE_DAYS):
        if g.current_army() != human:
            g.wait_for_input()
        d = e.u16(DAY)
        if d >= 7 and not injected:
            injected = True
            if coast:
                for kind, x, y in [("cruiser", 3, 7), ("sub", 5, 9), ("battleship", 2, 10), ("cruiser", 7, 8)]:
                    place_unit(shim, human, kind, x, y)
            else:
                for kind, x, y in [("bcopter", 11, 6), ("bcopter", 12, 7), ("bcopter", 13, 6), ("fighter", 12, 5), ("fighter", 13, 8)]:
                    place_unit(shim, human, kind, x, y)
            seen = {u["id"] for u in g.units()}
        # The enemy's HQ is never taken (a Black Hole unit standing on it is removed) and the enemy army is topped up
        # with Infantry, so the battle lasts the 22 days; the same in both runs.
        shim.bh = bh
        for u in g.units(bh):
            if (u["x"], u["y"]) == HQS[human]:
                Run.purge(shim, u)
        mine = len(g.units(human))
        cells = [(x, y) for y in range(19, 12, -1) for x in range(28, 19, -1)]
        for cell in cells:
            if mine >= 16:
                break
            if not g.unit_at(*cell):
                place_unit(shim, human, "infantry", *cell)
                mine += 1
        seen = {u["id"] for u in g.units()}
        g.goto(0, 0)
        g.goto(6, 2)
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
        spawned = []
        waited = 0
        for _ in range(1200):
            e.wait(1)
            if g.current_army() == bh:
                waited += 1
                spawned = [u for u in g.units(bh) if u["id"] not in seen]
                if spawned:
                    e.wait(8)        # the rest of the turn's spawns
                    spawned = [u for u in g.units(bh) if u["id"] not in seen]
                    taken = photograph(e, ctx.out, f"day{e.u16(DAY):02d}")
                    break
                if waited > 700:     # nothing spawned this turn: a picture all the same
                    taken = photograph(e, ctx.out, f"day{e.u16(DAY):02d}", 1)
                    frames.append({"day": e.u16(DAY), "shots": taken, "spawned": []})
                    break
        d = e.u16(DAY)
        for u in spawned:
            seen.add(u["id"])
        if spawned:
            frames.append({"day": d, "shots": taken, "spawned": [(romlib.UNIT_NAMES[u["type"]], u["x"], u["y"]) for u in spawned]})
        def back():
            for u in on_factory(g):
                inside.add((e.u16(DAY), romlib.UNIT_NAMES[u["type"]], u["army"], u["x"], u["y"]))
            return g.current_army() == human
        if not e.wait_until(back, 20000, step=30):
            ctx.shot(g, "stalled")
            ctx.log(f"day {d}: the human's turn did not come back (army {g.current_army()}, battle over {g.battle_over()}; procs {[(hex(a), hex(f)) for a, _, f in g.procs()]}; units {[(u['type'], u['x'], u['y'], u['flags']) for u in g.units(bh)]})")
            break
        values[d] = army_value(g, bh)
        seen |= {u["id"] for u in g.units()}
        g.wait_for_input()
    lines = e.decisions()
    result = {"coast": coast, "table": table, "frames": frames, "value_by_day": values, "decisions": lines, "on_factory": sorted(inside)}
    ctx.log(f"units standing on the factory's building squares: {sorted(inside)}")
    with open(os.path.join(ctx.out, "compare.json"), "w") as f:
        json.dump(result, f)
    ctx.log(f"spawned: {[(f['day'], [s[0] for s in f['spawned']]) for f in frames]}")
    ctx.log(f"army value by day: {values}")
    return result


def _compare_test(coast, table):
    def fn(ctx):
        if not COMPARE:
            raise Skip("AW2TEST_BH_COMPARE not set")
        compare_run(ctx, coast, table)
    fn.__name__ = f"bh_compare_{'coast' if coast else 'inland'}_{'table' if table else 'smart'}"
    test(modes=("ds",))(fn)


for _coast in (True, False):
    for _table in (True, False):
        _compare_test(_coast, _table)


# --- Pictures of the smart choice (AW2TEST_BH_PICS=<dir>): Black Hole is a human here, so these are a player's factory ----

NEAR_AIR = [("bcopter", 13, 9), ("bcopter", 14, 10), ("bcopter", 15, 9), ("fighter", 13, 11), ("fighter", 14, 12), ("bomber", 15, 11)]
NEAR_HORDE = [("infantry", 13 + k % 4, 9 + k // 4) for k in range(10)]
NEAR_FLEET = [("cruiser", 7, 15), ("battleship", 10, 16), ("sub", 12, 14), ("cruiser", 5, 14)]


@test(modes=("ds",))
def bh_factory_pictures_smart(ctx):
    """Pictures of the factory's choices against what the enemy fields: Anti-Air or Missiles against an air army,
    Subs, Cruisers and Battleships against a fleet, Recon and Tanks against infantry."""
    if not PICS:
        raise Skip("AW2TEST_BH_PICS not set")
    scenarios = [
        ("air_", factory_map(ctx, blockers=NEAR_AIR), (ANTI_AIR, MISSILES)),
        ("fleet_", factory_map(ctx, sea=SEA_FAR, blockers=NEAR_FLEET), (SUB, BATTLESHIP, CRUISER)),
        ("horde_", factory_map(ctx, blockers=NEAR_HORDE), (RECON, TANK, MD_TANK, NEOTANK, ARTILLERY)),
    ]
    for tag, m, shots in scenarios:
        r = start(ctx, m, shots=shots, tag=tag)
        r.days(24)
        lines = r.e.decisions()
        with open(os.path.join(PICS, f"{tag}decisions.txt"), "w") as f:
            f.write("\n".join(lines) + "\n")
        ctx.log(f"{tag}: {names(r.spawns)}")


# --- The wreck, and the building as a wall -------------------------------------------------------------------------

OBJ_VRAM = 0x06010000
WRECK_TILE = 0xC4          # the Black Cannon sheet's first 36 tiles (its wreck), loaded by AW2 on every battle map


def lz77(data):
    """GBA BIOS LZ77 (header 0x10 + size, flag bytes MSB first, 1 = copy 3..18 bytes from 1..4096 back)."""
    size = int.from_bytes(data[1:4], "little")
    out, i = bytearray(), 4
    while len(out) < size:
        flags = data[i]
        i += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if not flags & (1 << bit):
                out.append(data[i])
                i += 1
            else:
                n, back = (data[i] >> 4) + 3, (((data[i] & 15) << 8) | data[i + 1]) + 1
                i += 2
                for _ in range(n):
                    out.append(out[-back])
    return bytes(out)


def wreck_tiles_in_place(ctx, e):
    rom = open(paths.aw2_rom(), "rb").read()
    sheet = lz77(rom[0x0D24E0:0x0D24E0 + 0x2000])[:36 * 32]
    return e.read(OBJ_VRAM + WRECK_TILE * 32, 36 * 32) == sheet


@test(modes=("ds",))
def bh_factory_wreck_is_the_cannons(ctx):
    """On a map with no Black Cannon the wreck's tiles are in VRAM all the same (AW2 loads them on every map) and
    stay as the game's sheet has them while the destroyed factory is drawn as the wreck, in the first frames and later."""
    r = start(ctx, factory_map(ctx, blockers=[("tank", 10, 12)]), shots=())
    ctx.check(wreck_tiles_in_place(ctx, r.e), "the wreck's tiles are in VRAM at the start")
    destroy(ctx, r)
    ctx.check(wreck_tiles_in_place(ctx, r.e), "and after the factory is destroyed")
    r.g.end_turn(human=1)
    r.g.end_turn(human=2)
    r.g.goto(*TARGET)
    r.e.wait(30)
    ctx.check(wreck_tiles_in_place(ctx, r.e), "and two days later")
    pic(ctx, r.g, "factory_wreck_later")


@test(modes=("ds",))
def bh_factory_wreck_in_fog(ctx):
    """With fog on, a factory the CPU brings down is drawn as the wreck, its tiles in place."""
    m = factory_map(ctx, blockers=[("tank", 11, 11)])
    g = ctx.start(m, ["andy", "vonbolt"], humans=(1,), fog=True)
    e = g.e
    e.w8(factory_entry(e) + 4, 10)
    g.end_turn(human=1)
    ctx.eq(factory_hp(e), 0, "the CPU's Tank destroyed the factory in the fog")
    g.goto(*TARGET)
    e.wait(30)
    ctx.check(wreck_tiles_in_place(ctx, e), "the wreck's tiles are in VRAM")
    pic(ctx, g, "factory_wreck_fog")
    ctx.check(not g.battle_over(), "the battle goes on")


@test(modes=("aw2", "ds"))
def bh_factory_building_is_a_wall(ctx):
    """With the pack in Versus every square of the factory's building (3x4) is impassable ground (class 9, the
    factory's own 0x1D), even on a map that carries only the anchor tile; the pipe end at its top included. AW2's rules
    are untouched without the pack."""
    r = start(ctx, factory_map(ctx), shots=())
    g = r.g
    classes = {(x, y): g.terrain_class(x, y) & 0x1F for x in range(9, 12) for y in range(8, 12)}
    ctx.log(f"classes {classes}")
    if ctx.ds:
        ctx.check(all(c in (9, 0x1D) for c in classes.values()), "every building square is a wall")
    else:
        ctx.check(all(c in (1, 0x1D) for c in classes.values()), "without the pack the squares are AW2's own")
    ctx.check(g.terrain_class(9, 12) & 0x1F == 1, "the doors' row is open ground")
    m = drawn_map(ctx, False)
    g2 = ctx.start(m, ["andy", "vonbolt" if ctx.ds else "drake"], humans=(2,))
    top = g2.terrain_class(5, 1) & 0x1F
    ctx.eq(top, 9 if ctx.ds else 0xF, "the pipe end at the factory's top")


@test(modes=("ds",))
def bh_factory_nothing_stands_on_the_building(ctx):
    """A long CPU-against-CPU game on each drawn map (coast and inland): no unit, of either army and of any kind, ever
    stands on a square of the factory's building, and every spawn is on a door."""
    from aw2test.emu import Emu
    from aw2test.game import Game
    for coast in (True, False):
        save = os.path.join(ctx.out, f"map_{coast}.sav")
        drawn_map(ctx, coast, economy=True).write(paths.base_save(), save)
        e = Emu(save=save, ds=ctx.ds)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        g.boot_to_teams()
        g.set_teams(["andy", "kanbei"], set())
        g.teams_to_rules()
        g.set_rules(fog=False, weather="clear", power=True, visuals="off")
        g.start_battle()
        inside, doors, last = set(), set(), 0
        for _ in range(400):
            e.wait(60)
            for u in on_factory(g):
                inside.add((e.u16(DAY), u["army"], romlib.UNIT_NAMES[u["type"]], u["x"], u["y"]))
            d = e.u16(DAY)
            if d != last:
                last = d
            if d >= 24 or not g.units(1) or not g.units(2):
                break
        ctx.log(f"{'coast' if coast else 'inland'}: {last} days, on the building: {sorted(inside)}")
        ctx.check(last >= 10, f"{'coast' if coast else 'inland'}: a long game ({last} days)")
        ctx.check(not inside, f"{'coast' if coast else 'inland'}: nothing stood on the building")
        for line in e.decisions():
            if " -> " in line and " at (" in line:
                pos = line.split(" at (")[1].split(")")[0].split(",")
                doors.add((int(pos[0]), int(pos[1])))
        beside = {(x, 5) for x in range(3, 8)} | {(x, 6) for x in range(4, 7)}
        ctx.check(doors <= beside, f"every spawn on a door square or beside the doors (ships): {sorted(doors)}")
        e.close()


@test(modes=("ds",))
def bh_factory_wreck_in_five_armies(ctx):
    """On a five-army map (Black Hole the fifth army) the destroyed factory is the wreck, its tiles in place, and spawns
    nothing; the battle goes on."""
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.terrain(15, 16, 0x1B4)
    m.colours = [5, 1, 2, 3, 4]
    m.terrain(10, 10, ANCHOR)
    m.unit(5, "infantry", 16, 16)
    m.unit(1, "tank", 10, 12)
    g = ctx.start(m, None, humans=(1, 5))
    e = g.e
    ctx.eq(e.u8(FIVE_ON), 1, "five armies")
    ctx.check(wreck_tiles_in_place(ctx, e), "the wreck's tiles are in VRAM")
    hp0 = factory_hp(e)
    ctx.eq(hp0, 200, "the factory has its hit points")
    e.w8(factory_entry(e) + 4, 10)
    g.select(10, 12)
    g.move_to(10, 12)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(*TARGET)
    g.wait_for_input()
    ctx.eq(factory_hp(e), 0, "destroyed")
    g.goto(*TARGET)
    e.wait(30)
    ctx.check(wreck_tiles_in_place(ctx, e), "the wreck's tiles are still in place")
    pic(ctx, g, "factory_wreck_five_armies")
    n0 = len(g.units(5))
    g.end_turn(human=5)
    g.end_turn(human=1)
    g.end_turn(human=5)
    ctx.eq(len(g.units(5)), n0, "no spawns for Black Hole any more")
