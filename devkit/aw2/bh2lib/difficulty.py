"""The BH2 Campaign's difficulty score: how hard each mission is to beat, from numbers a designer can read (the Emerald Sun kit's static score, `eslib/difficulty.py`, applied to BH2's missions).

For each mission the score takes, from the BH2 maps and `bh2_campaign.rs`:
- force: the enemy's start units plus its scripted reinforcements (spawns, waves, takeover troops: `unit::` kinds in the mission's spawn lists) against the player's start units, at the games' unit prices (both fronts of a two-front mission are summed);
- economy: the enemy's funds (start funds plus the funds a takeover adds) plus ten days of its properties' income against the player's;
- fortified: the share of pipe-wall cells (a wall is a line the enemy holds: 60 cells is a fully walled map);
- pressure: how many of ground, air and sea the enemy fields (start and spawns) over three.
`score = 100 * (0.35 force + 0.20 economy + 0.10 fortified + 0.10 pressure) / 0.75` with each ratio mapped by r / (1 + r) (the Emerald Sun formula). `aw2dev bh2 difficulty` prints the table; the final mission must lead by 10%.
Static only (no sims): the harness cannot yet play whole BH2 missions."""
import collections
import re

from .. import cfg
from ..eslib import difficulty as esd
from ..eslib.report import COST

UNIT_ID = {"INFANTRY": 1, "MECH": 2, "MD_TANK": 3, "MEGATANK": 4, "TANK": 5, "RECON": 6, "APC": 7, "NEOTANK": 8, "PIPERUNNER": 9, "ARTILLERY": 10, "ROCKETS": 11, "STEALTH": 12, "BLACK_BOMB": 13, "ANTI_AIR": 14,
           "MISSILES": 15, "FIGHTER": 16, "BOMBER": 17, "BLACK_BOAT": 18, "B_COPTER": 19, "T_COPTER": 20, "BATTLESHIP": 21, "CRUISER": 22, "LANDER": 23, "SUB": 24, "CARRIER": 26}
SRC = cfg.REPO / "tango-gamesupport-aw2" / "src" / "bh2_campaign.rs"


def _bodies():
    text = SRC.read_text()
    consts = {m.group(1): m.group(0) for m in re.finditer(r"const ([A-Z0-9_]+): \[\(u8, \(u8, u8\)\); \d+\] = \[.*?\n\];", text, re.S)}
    out = {}
    fns = list(re.finditer(r"^fn (bh2_\d\d)\(\) -> MissionDef \{", text, re.M))
    for i, f in enumerate(fns):
        end = text.index("\n}\n", f.start()) + 3
        out[f.group(1)] = text[f.start(): end]
    return out, consts, text


def spawn_kinds(body, consts):
    """[kind id] of the enemy's scripted reinforcements in a mission's code: units in its spawn calls (`UnitDef::new(2, unit::X`, `w(k, unit::X)`, `at(unit::X`, `wave(2, unit::X, &[cells])`) and in the stage lists it names (the `*_WAVE` constants of M30)."""
    kinds = []
    for n in re.findall(r"UnitDef::new\(2, unit::([A-Z_]+)", body):
        kinds += [UNIT_ID[n]] * (4 if "M12_AIR" in body and n == "B_COPTER" else 5 if "M12_INF" in body and n == "INFANTRY" else 1)
    for n in re.findall(r"\bw\(\d+, unit::([A-Z_]+)\)", body) + re.findall(r"\bat\(unit::([A-Z_]+),", body):
        kinds.append(UNIT_ID[n])
    for n, cells in re.findall(r"wave\(2, unit::([A-Z_]+), &\[(.*?)\]", body):
        kinds += [UNIT_ID[n]] * cells.count("(")
    for name, block in consts.items():
        if name.endswith("_WAVE") and re.search(rf"\b{name}\b", body) and name.split("_")[0] in ("OLAF", "KANBEI", "EAGLE", "ARIA"):
            kinds += [UNIT_ID[n] for n in re.findall(r"\(unit::([A-Z_]+),", block) if n in UNIT_ID]
    return kinds


def funds_of(body):
    """(player funds, enemy funds) from the ArmyDefs, plus the funds takeovers add to the enemy."""
    f = [int(x) for x in re.findall(r"\.funds\((\d+)\)", body)]
    add = sum(int(x) for x in re.findall(r"takeover\([A-Z0-9_]+, [A-Za-z:_0-9]+, (\d+),", body)) + sum(int(x) for x in re.findall(r"AddFunds \{\s*army: 2,\s*funds: (\d+)", body))
    add += sum(int(x) for x in re.findall(r"wake\([A-Z0-9_]+, &\[[^\]]*\], \d, (\d+),", body))
    if len(f) == 5:                                   # (a five-army mission: the player is the fifth)
        return f[4], sum(f[:4]) + add
    return f[0] if f else 0, sum(f[1:]) + add


def maps_numbers():
    """{map name: (units {army: Counter}, owned {army: n}, pipe cells)} of every BH2 map."""
    import sys
    from ..maplint import load
    five = cfg.REPO / "tango-gamesupport-aw2" / "five"
    sys.path.insert(0, str(five))
    import map as mappy
    out = {}
    for m in load.bh2_maps():
        W, H, ch, hqs, owner = mappy.grid(m.meta)
        units = collections.defaultdict(collections.Counter)
        for u in m.units:
            units[u["army"]][u["kind"]] += 1
        owned = collections.Counter()
        pipes = 0
        for y in range(H):
            for x in range(W):
                c = ch(x, y)
                if c in "BCAPQ":
                    owned[owner(x, y)] += 1
                elif c in "12345":
                    owned[int(c)] += 1
                elif c == "I":
                    pipes += 1
        out[m.name] = (units, owned, pipes, m.meta.get("armies", 2))
    return out


def rows():
    """[(mission number, title, numbers, score)] for every BH2 mission."""
    from . import MISSIONS, FRONT2
    bodies, consts, _ = _bodies()
    nums = maps_numbers()
    out = []
    for n, (name, title) in sorted(MISSIONS.items()):
        maps = [name] + ([FRONT2[n]] if n in FRONT2 else [])
        pv = ev = 0
        owned_p = owned_e = pipes = 0
        kinds = set()
        for mp in maps:
            units, owned, pp, n_armies = nums[mp]
            if not units:
                continue
            me = 5 if n_armies == 5 else 1                    # (a five-army mission's player is the fifth army)
            pv += sum(COST.get(k, 0) * c for k, c in units.get(me, {}).items())
            for a in [a for a in range(1, n_armies + 1) if a != me and (n_armies == 5 or a != 1)]:
                ev += sum(COST.get(k, 0) * c for k, c in units.get(a, {}).items())
                for k in units.get(a, {}):
                    kinds.add("air" if k in (16, 17, 19, 20) else "sea" if k in (21, 22, 23, 24, 26) else "ground")
            owned_p += owned.get(me, 0)
            owned_e += sum(owned.get(a, 0) for a in range(1, n_armies + 1) if a != me and (n_armies == 5 or a != 1))
            pipes += pp
        body = bodies.get(name, "")
        sk = spawn_kinds(body, consts)
        ev += sum(COST.get(k, 0) for k in sk)
        for k in sk:
            kinds.add("air" if k in (16, 17, 19, 20) else "sea" if k in (21, 22, 23, 24, 26) else "ground")
        pf, ef = funds_of(body)
        pe, ee = pf + 10 * owned_p * 1000, ef + 10 * owned_e * 1000
        nm = {"player_value": pv, "enemy_value": ev, "force": ev / max(pv, 1), "economy": ee / max(pe, 1), "fortified": round(min(1.0, pipes / 60), 2), "pressure": len(kinds) / 3.0}
        nm.update({"pe": pe, "ee": ee, "kinds": kinds})
        out.append((n, title, nm, esd.static_score(nm), len(sk)))
    # the final mission is both maps (M30 part one and M31 part two) together: its row replaces M30's, summing the two maps' forces, funds and fields
    one = next(r for r in out if r[0] == 30)
    two = next(r for r in out if r[0] == 31)
    a, b = one[2], two[2]
    kinds = a["kinds"] | b["kinds"]
    nm = {"player_value": a["player_value"] + b["player_value"], "enemy_value": a["enemy_value"] + b["enemy_value"], "pe": a["pe"] + b["pe"], "ee": a["ee"] + b["ee"], "fortified": max(a["fortified"], b["fortified"]), "pressure": len(kinds) / 3.0}
    nm["force"] = nm["enemy_value"] / max(nm["player_value"], 1)
    nm["economy"] = nm["ee"] / max(nm["pe"], 1)
    out = [r for r in out if r[0] != 30]
    out.append((30, "The Last Accord (both maps)", nm, esd.static_score(nm), one[4] + two[4]))
    return sorted(out, key=lambda r: r[0])


def report():
    lines = [f"{'#':>2} {'mission':<26} {'player':>8} {'enemy':>8} {'force':>6} {'econ':>6} {'fort':>5} {'press':>5} {'score':>6}  spawned"]
    rs = rows()
    for n, title, nm, sc, sp in rs:
        lines.append(f"{n:>2} {title:<26} {nm['player_value']:>8} {nm['enemy_value']:>8} {nm['force']:>6.2f} {nm['economy']:>6.2f} {nm['fortified']:>5} {nm['pressure']:>5.2f} {sc:>6}  {sp}")
    return lines, rs
