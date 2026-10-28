"""Units a BH mission's code places by literal coordinates (`UnitDef::new(army, unit::KIND, x, y)` inside `fn bhNN()` of bh_act*.rs: reinforcements,
paratroopers, scripted columns), so the linter can check them against the map like the map file's own `unit` lines."""
import re
from .. import cfg

SRC = cfg.REPO / "tango-gamesupport-aw2" / "src"
KINDS = {"INFANTRY": 1, "MECH": 2, "MD_TANK": 3, "MEGATANK": 4, "TANK": 5, "RECON": 6, "APC": 7, "NEOTANK": 8, "PIPERUNNER": 9, "ARTILLERY": 10,
         "ROCKETS": 11, "STEALTH": 12, "BLACK_BOMB": 13, "ANTI_AIR": 14, "MISSILES": 15, "FIGHTER": 16, "BOMBER": 17, "BLACK_BOAT": 18,
         "B_COPTER": 19, "T_COPTER": 20, "BATTLESHIP": 21, "CRUISER": 22, "LANDER": 23, "SUB": 24, "CARRIER": 26, "OOZIUM": 27}
FN = re.compile(r"^(?:pub )?fn (\w+)\(", re.M)
MISSION = {"bh": re.compile(r"^bh\d\d$"), "es": re.compile(r"^es\d\d$"), "bh2": re.compile(r"^bh2_\d\d$")}
UD = re.compile(r"UnitDef::new\(\s*(\d+)\s*,\s*unit::([A-Z_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
# `wave(army, unit::KIND, &CELLS[a..b])` (es_campaign::wave: one unit on each cell of a slice of a `const CELLS: [(u8, u8); N]` table of the same file)
WAVE = re.compile(r"wave\(\s*(\d+)\s*,\s*unit::([A-Z_]+)\s*,\s*&([A-Z_][A-Z0-9_]*)(?:\[(\d*)\.\.(\d*)\])?\s*\)")
CELLS = re.compile(r"const ([A-Z_][A-Z0-9_]*): \[\(u8, u8\); \d+\] = \[(.*?)\];", re.S)
PAIR = re.compile(r"\((\d+),\s*(\d+)\)")


def spawns(source="bh"):
    """{map name: [unit dicts like the map file's, plus 'line' and 'spawn': True]}"""
    out = {}
    for f in sorted(SRC.glob(f"{source}_act*.rs")):
        text = f.read_text()
        tables = {c.group(1): [(int(a), int(b)) for a, b in PAIR.findall(c.group(2))] for c in CELLS.finditer(text)}
        fns = list(FN.finditer(text))
        for i, m in enumerate(fns):
            end = fns[i + 1].start() if i + 1 < len(fns) else len(text)
            if not MISSION[source].match(m.group(1)):
                continue
            body = text[m.start():end]
            for u in UD.finditer(body):
                kind = KINDS.get(u.group(2))
                if kind is None:
                    continue
                line = text.count("\n", 0, m.start() + u.start()) + 1
                out.setdefault(m.group(1), []).append(
                    {"army": int(u.group(1)), "kind": kind, "x": int(u.group(3)), "y": int(u.group(4)), "hp": 100, "hold": False, "name": "",
                     "spawn": f"{f.name}:{line}"})
            for w in WAVE.finditer(body):
                kind, cells = KINDS.get(w.group(2)), tables.get(w.group(3))
                if kind is None or cells is None:
                    continue
                lo = int(w.group(4)) if w.group(4) else 0
                hi = int(w.group(5)) if w.group(5) else len(cells)
                line = text.count("\n", 0, m.start() + w.start()) + 1
                if hi > len(cells):
                    out.setdefault(m.group(1), []).append({"army": int(w.group(1)), "kind": kind, "x": 255, "y": 255, "hp": 100, "hold": False, "name": "",
                                                           "spawn": f"{f.name}:{line} ({w.group(3)}[{lo}..{hi}] is past the table's {len(cells)} cells)", "wave": True})
                    continue
                for x, y in cells[lo:hi]:
                    out.setdefault(m.group(1), []).append({"army": int(w.group(1)), "kind": kind, "x": x, "y": y, "hp": 100, "hold": False, "name": "",
                                                           "spawn": f"{f.name}:{line} ({w.group(3)}[{lo}..{hi}])", "wave": True})
    return out
