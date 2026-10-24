"""The campaign's missions as data: the Rust report (`aw2_es_report`: armies, funds, spawns, props, boxes) joined with the text maps (start units,
properties by owner). Used by `aw2dev campaign difficulty` and `campaign check`."""
import collections, subprocess, sys
from .. import cfg, util

# AW2's unit prices (Dual Strike's added units too), by unit kind id.
COST = {1: 1000, 2: 3000, 3: 16000, 4: 28000, 5: 7000, 6: 4000, 7: 5000, 8: 22000, 9: 20000, 10: 6000, 11: 15000, 12: 24000, 13: 25000, 14: 8000, 15: 12000,
        16: 20000, 17: 22000, 18: 7500, 19: 9000, 20: 5000, 21: 28000, 22: 18000, 23: 12000, 24: 20000, 26: 30000, 27: 0}
NAMES = {1: "Inf", 2: "Mech", 3: "MdTank", 4: "Mega", 5: "Tank", 6: "Recon", 7: "APC", 8: "Neo", 9: "Pipe", 10: "Art", 11: "Rockets", 12: "Stealth", 13: "BBomb",
         14: "AA", 15: "Missiles", 16: "Fighter", 17: "Bomber", 18: "BBoat", 19: "BCopter", 20: "TCopter", 21: "BShip", 22: "Cruiser", 23: "Lander", 24: "Sub",
         26: "Carrier", 27: "Ooz"}
EARNERS = set("HBCAPQ12345")
BASES = set("B")
CO_NAMES = {86: "Klaus", 87: "Aurelia", 88: "Cassius", 89: "Livia", 90: "Varro", 17: "Jess", 8: "Eagle", 77: "Javier", 76: "Grimm", 18: "Sensei", 78: "Sasha",
            16: "Colin", 9: "Drake", 2: "Max", 79: "Jake", 13: "Adder", 11: "Flak", 6: "Kanbei", 7: "Sonja", 3: "Olaf", 5: "Grit", 74: "Kindle", 12: "Lash", 0: "Nell"}


def run_report():
    exe = util.example_bin("aw2_es_report")
    util.check_fresh(exe, "aw2_es_report")
    r = subprocess.run([str(exe)], capture_output=True, text=True)
    if r.returncode:
        util.die("aw2_es_report failed: " + r.stderr[-300:])
    return [l.split("\t") for l in r.stdout.splitlines()]


def missions():
    """{key: dict} with title, day_limit, fog, objective, armies [{n, colour, team, co, funds}], spawns [{day, army, kind, x, y}], props, boxes, and
    from the map: units {army: Counter(kind)}, owned {army: earning properties}, neutral, size."""
    from ..maplint import load
    out = collections.OrderedDict()
    for row in run_report():
        t, key = row[0], row[1]
        if t == "M":
            out[key] = {"key": key, "title": row[2], "day_limit": int(row[3]), "fog": bool(int(row[4])), "weather": int(row[5]), "n_armies": int(row[6]),
                        "objective": row[7], "armies": [], "spawns": [], "props": [], "boxes": 0}
        elif t == "A":
            out[key]["armies"].append({"n": int(row[2]), "colour": int(row[3]), "team": int(row[4]) or int(row[2]), "co": row[5], "funds": int(row[6])})
        elif t == "S":
            out[key]["spawns"].append({"day": int(row[2]), "army": int(row[3]), "kind": int(row[4]), "x": int(row[5]), "y": int(row[6])})
        elif t == "P":
            out[key]["props"].append({"x": int(row[2]), "y": int(row[3]), "kind": int(row[4]), "owner": int(row[5])})
        elif t == "N":
            out[key]["boxes"] = int(row[2])
    five = cfg.REPO / "tango-gamesupport-aw2" / "five"
    sys.path.insert(0, str(five))
    import map as mappy
    for m in load.es_maps():
        d = out.get(m.name)
        if d is None:
            continue
        meta = m.meta
        W, H, ch, hqs, owner = mappy.grid(meta)
        units = collections.defaultdict(collections.Counter)
        for u in m.units:
            units[u["army"]][u["kind"]] += 1
        owned = collections.Counter()
        bases = collections.Counter()
        neutral = 0
        for y in range(H):
            for x in range(W):
                c = ch(x, y)
                if c in "BCAPQ":
                    owned[owner(x, y)] += 1
                    bases[owner(x, y)] += c in "BAP"
                elif c in "12345":
                    owned[int(c)] += 1
                elif c in "bcap":
                    neutral += 1
        for p in d["props"]:
            if p["owner"]:
                owned[p["owner"]] += 1
        d.update(units=units, owned=owned, production=bases, neutral=neutral, size=(W, H), hold={a: sum(1 for u in m.units if u["army"] == a and u["hold"]) for a in range(1, 6)},
                 blackhole=bool(meta.get("blackhole")))
    return out


def value(counter):
    return sum(COST.get(k, 0) * n for k, n in counter.items())


def spawn_value(d, army, upto=99):
    return sum(COST.get(s["kind"], 0) for s in d["spawns"] if s["army"] == army and s["day"] <= upto)
