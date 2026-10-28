"""BH2 M3 Iron Ledger and M14 Thirty Years of Iron (development build, crate::bh2_campaign): Black Hole's Black Factory spawns and is smart, and the volcano erupts (`-k bh2_m3_`, `-k bh2_m14_`).

The mission is entered through its CO screen (Asuka), the test player (aw2test.bot) plays Black Hole's army for AW2TEST_BH2_DAYS days (default 8) with the factory's full decision log on
(TANGOAW2_BH_LOG_ALL); every spawn is written to `factory_spawn_log.txt` (in the test's folder and, with AW2TEST_REVIEW_DIR, there) with the reason the field gives for it, and the test fails when
the factory never spawns or a pick breaks the rules the owner set:
- Anti-Air and the air units only while the field shows air (the log's `air N%` > 0);
- foot soldiers (Infantry, Mech) only to capture (a target property to reach) or to block (an enemy beside the factory);
- indirect fire (Artillery, Rockets, Missiles) only with a safe backline (no foe near the factory, none adjacent);
- a varied mix (at least three types in six or more spawns, no type more than 60% of them);
- never a Piperunner or an Oozium (nor Black Boat, Carrier, ships on this landlocked factory).
The volcano's eruptions are read from the hazard cells' RAM (`hazard.rs`, 0x0203F708: the cells the eruption takes now, 0xFFFF ends the list): the first eruption is day 3, one each day after."""

import os
import re
import shutil

from aw2test import bh2campaign as b2
from aw2test import paths
from aw2test.harness import test

DAYS = int(os.environ.get("AW2TEST_BH2_DAYS", "8"))
CELLS = 0x0203F708
NAMES = ["-", "Infantry", "Mech", "Md Tank", "Megatank", "Tank", "Recon", "APC", "Neotank", "Piperunner", "Artillery", "Rockets", "Stealth", "Black Bomb", "Anti-Air", "Missiles", "Fighter", "Bomber",
         "Black Boat", "B Copter", "T Copter", "Battleship", "Cruiser", "Lander", "Sub", "-", "Carrier", "Oozium"]
AIR = {"Fighter", "Bomber", "B Copter", "T Copter", "Stealth", "Black Bomb"}
FOOT = {"Infantry", "Mech"}
INDIRECT = {"Artillery", "Rockets", "Missiles"}
NEVER = {"Piperunner", "Oozium", "Black Boat", "Carrier", "Battleship", "Cruiser", "Lander", "Sub"}
LINE = re.compile(r"day (\d+) army (\d+) slot (\d+) table (.+?) -> (.+?) at \((\d+),(\d+)\) score (-?\d+) \| (.*?) \| pool (.*?) \| then (.*?) \| (foes .*?) \| \d+ us")
FIELD = re.compile(r"foes (\d+) \(\+(\d+) unseen\) near (\S+) threat (\S+) air (\d+)% armour (\d+)% reach (\S+) adj (\d+) \| own (.*?) \| to target (.*?) / foe (.*)")


def parse(lines):
    spawns = []
    for l in lines:
        m = LINE.match(l)
        if not m:
            continue
        day, army, slot, table, unit, x, y, score, why, pool, then, field = m.groups()
        f = FIELD.match(field)
        spawns.append({"day": int(day), "army": int(army), "slot": int(slot), "table": table, "unit": unit, "at": (int(x), int(y)), "score": int(score), "why": why, "pool": pool, "field": field,
                       "foes": int(f.group(1)) if f else 0, "threat": f.group(4) if f else "?", "air": int(f.group(5)) if f else 0, "adj": int(f.group(8)) if f else 0,
                       "to_target": f.group(10) if f else "?"})
    return spawns


def verdict(s):
    """(ok, reason) for one spawn: the field's reason for the pick, or the rule it breaks."""
    u = s["unit"]
    air_seen = s["air"] > 0
    if u in NEVER:
        return False, f"{u} is never built by this factory"
    if u == "Anti-Air":
        return (air_seen, f"Anti-Air: the enemy shows {s['air']}% air" if air_seen else "Anti-Air with no air in sight")
    if u in AIR:
        return (air_seen, f"{u}: the enemy shows {s['air']}% air" if air_seen else f"{u} with no air in sight")
    if u in FOOT:
        capture = s["to_target"] not in ("None", "?")
        block = s["adj"] > 0
        return (capture or block, f"{u}: " + ("a property to capture (to target " + s["to_target"] + ")" if capture else "blocks the enemy beside the factory") if (capture or block) else f"{u} with nothing to capture or block")
    if u in INDIRECT:
        safe = s["adj"] == 0 and s["threat"] in ("0", "0.0")
        return (safe, f"{u}: a safe backline (threat {s['threat']}, adjacent {s['adj']})" if safe else f"{u} with the enemy at the factory (threat {s['threat']}, adjacent {s['adj']})")
    return True, f"{u}: the best counter / traveller of the field ({s['why'].split(';')[0]})"


def factory_and_volcano(ctx, n, title):
    save = os.path.join(ctx.out, f"m{n}.sav")
    shutil.copy(paths.base_save(), save)
    e, g, d = b2.enter(ctx, n, env={"TANGOAW2_BH_LOG_ALL": "1"}, save=save)
    erupted = {}

    def log(msg):
        ctx.log(msg)
        m = re.match(r"day (\d+):", msg)
        if m:
            day = int(m.group(1))
            first = e.u16(CELLS)
            erupted[day] = [(e.u16(CELLS + 4 * k), e.u16(CELLS + 4 * k + 2)) for k in range(12) if e.u16(CELLS + 4 * k) != 0xFFFF][:12] if first != 0xFFFF else []

    r = d.play(max_days=DAYS, log=log)
    ctx.log(f"M{n} played: {r}")
    spawns = [s for s in parse(e.decisions()) if s["army"] == 1]
    out = [f"Black Factory (M{n} {title}): every spawn, with the field's reason", ""]
    bad = []
    for s in spawns:
        ok, why = verdict(s)
        out.append(f"day {s['day']:>2} slot {s['slot']} table {s['table']:<10} -> {s['unit']:<10} at {s['at']}  {'ok ' if ok else 'BAD'}  {why}")
        out.append(f"        field: {s['field']}")
        if not ok:
            bad.append((s, why))
    types = [s["unit"] for s in spawns]
    out += ["", f"{len(spawns)} spawns, types: " + ", ".join(f"{t} x{types.count(t)}" for t in sorted(set(types)))]
    out += ["", f"M{n}'s volcano: eruptions (the hazard cells written at each day's start): " + "; ".join(f"day {k}: {len(v)} cells" for k, v in sorted(erupted.items()))]
    text = "\n".join(out)
    open(os.path.join(ctx.out, "factory_spawn_log.txt"), "w").write(text)
    rv = os.environ.get("AW2TEST_REVIEW_DIR")
    if rv:
        os.makedirs(rv, exist_ok=True)
        shutil.copy(os.path.join(ctx.out, "factory_spawn_log.txt"), os.path.join(rv, f"factory_spawn_log_m{n}.txt" if n != 3 else "factory_spawn_log.txt"))
    ctx.log(text)
    ctx.check(len(spawns) >= 3, f"the Black Factory spawns ({len(spawns)} spawns in {DAYS} days)")
    ctx.check(not bad, f"every pick has a reason the field gives: {[(s['day'], s['unit'], w) for s, w in bad]}")
    if len(spawns) >= 6:
        ctx.check(len(set(types)) >= 3, f"a varied mix ({sorted(set(types))})")
        ctx.check(max(types.count(t) for t in set(types)) <= 0.6 * len(types), "no type is more than 60% of the spawns")
    ctx.check(all(erupted.get(k) for k in erupted if 4 <= k <= DAYS) and any(erupted.get(k) for k in erupted), f"the volcano erupts (cells by day: { {k: len(v) for k, v in erupted.items()} })")
    e.close()


@test(name="bh2_m3_factory_and_volcano", modes=("ds",))
def bh2_m3_factory_and_volcano(ctx):
    factory_and_volcano(ctx, 3, "Iron Ledger")


@test(name="bh2_m14_factory_and_volcano", modes=("ds",))
def bh2_m14_factory_and_volcano(ctx):
    factory_and_volcano(ctx, 14, "Thirty Years of Iron")
