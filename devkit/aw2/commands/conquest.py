"""aw2dev conquest: Conquest Run, Select Mode's CONQUEST entry (a five-map roguelike run on the Gauntlet's engine), in the offline harness (docs/dev/conquest.md).

  conquest start [--co N] [--out DIR]   boots the harness straight into a run (title, Select Mode, CONQUEST, the one-row selector "Conquest Run *", the army screen with CO N, map 1, the reward page after its
                                        capture, map 2) and leaves a picture of each screen: 1_wheel, 2_map_selector, 3_army_screen, 4_first_turn, 5_reward_page, 6_reward_units, 7_second_map
                                        (PNG, in DIR or a temp folder; fails when one is missing)
  conquest sheet [--out FILE]           one contact sheet in the three looks (AW2 graphics, Dual Strike graphics + tilt, Dual Strike flat): the reward page, the unit page and each of the nine maps' first turn
  conquest maps [--all]                 the nine maps as the ROM has them (size, HQs, distance) against the constants of `crate::conquest::MAPS` (exit 1 on a mismatch); --all lists every two-player
                                        Versus map with its HQ distance and bases (to choose another map for a stage: docs/dev/conquest.md "Adding or changing a map")
  conquest test                         the run's regression tests (`run.py -k conquest --mode ds`)
"""
import os
import subprocess
import sys
import tempfile

from .. import cfg, util

START_PICTURES = ["1_wheel", "2_map_selector", "3_army_screen", "4_first_turn", "5_reward_page", "6_reward_units", "7_second_map"]
CONQUEST_RS = cfg.REPO / "tango-gamesupport-aw2" / "src" / "conquest.rs"


def register(sub):
    g = sub.add_parser("conquest", help="Conquest Run: boot into a run with pictures, the contact sheet, the maps check, its tests (docs/dev/conquest.md)")
    gs = g.add_subparsers(dest="conquestcmd", required=True)
    a = gs.add_parser("start", help="title -> CONQUEST -> army screen -> map 1 -> reward page -> map 2, with a picture of each screen")
    a.add_argument("--co", type=int, default=1, help="AW2 CO id to pick (default 1, Andy)")
    a.add_argument("--out", help="folder for the pictures (default: a temp folder, printed)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=start)
    a = gs.add_parser("sheet", help="the reward page and each map's first turn in the three looks, one contact sheet")
    a.add_argument("--out", help="the sheet's PNG (default: devkit/work/conquest/sheet.png)")
    a.set_defaults(fn=sheet)
    a = gs.add_parser("maps", help="the run's nine maps read from the ROM against the Rust constants; --all lists every 2P Versus map")
    a.add_argument("--all", action="store_true", help="every two-player Versus map with its HQ distance and bases")
    a.set_defaults(fn=maps)
    a = gs.add_parser("test", help="run the Conquest Run tests")
    a.set_defaults(fn=test)


def _run(extra_env, args):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    env = dict(os.environ, **extra_env)
    return subprocess.run([sys.executable, str(run)] + args, env=env, cwd=cfg.REPO, text=True)


def start(a):
    out = a.out or tempfile.mkdtemp(prefix="conquest_start_")
    r = _run({"AW2TEST_CONQUEST_CO": str(a.co), "AW2TEST_CONQUEST_OUT": out}, ["-k", "conquest_tool_start", "--mode", "ds"] + (["-v"] if a.verbose else []))
    names = sorted(os.listdir(out)) if os.path.isdir(out) else []
    util.say("pictures:", out, names)
    missing = [n for n in START_PICTURES if n + ".png" not in names]
    if missing and not r.returncode:
        util.say("MISSING pictures:", missing)
        return 1
    return r.returncode


def sheet(a):
    out = a.out or str(cfg.work("conquest") / "sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = _run({"AW2TEST_SHEET": out}, ["-k", "conquest_pictures", "--mode", "ds"])
    util.say("sheet:", out)
    return r.returncode


def test(a):
    return _run({}, ["-k", "conquest", "--mode", "ds"]).returncode


# -- the maps, from the ROM ----------------------------------------------------------------------------------------------------------------------------------------------

GAME_MAP_TABLE = 0x085C77A0        # AW2's own map table: 0x5C-byte entries, +0x00 the map's LZ77 blob, +0x14 the name's text id
ENTRY = 0x5C
# crate::five::PROPERTY_TILES: [kind][owner] (kinds: HQ, base, city, airport, port, lab; owner 0 neutral, 1..5 the armies)
PROPERTY_TILES = [[0x1C0, 0x1C5, 0x1CA, 0x1CF, 0x1D4, 0x1B4], [0x1C1, 0x1C6, 0x1CB, 0x1D0, 0x1D5, 0x1B5], [0x1C2, 0x1C7, 0x1CC, 0x1D1, 0x1D6, 0x1B6],
                  [0x1C3, 0x1C8, 0x1CD, 0x1D2, 0x1D7, 0x1B7], [0x1C4, 0x1C9, 0x1CE, 0x1D3, 0x1D8, 0x1B8], [0x1D9, 0x1DA, 0x1DB, 0x1DC, 0x1DD, 0x1B9]]
KINDS = ["HQ", "base", "city", "airport", "port", "lab"]
VERSUS_IDS = list(range(0x01, 0x27)) + list(range(0x6C, 0x7C)) + list(range(0x80, 0x8A))


def read_map(data, mid):
    """(width, height, {(kind, owner): [(x, y)]}) of AW2's map `mid`, from the ROM image `data`; None when the entry has no map."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import rom
    ptr = int.from_bytes(data[GAME_MAP_TABLE - 0x08000000 + ENTRY * mid:][:4], "little")
    if not 0x08000000 <= ptr < 0x0A000000:
        return None
    raw = rom.lz10(data[ptr - 0x08000000:ptr - 0x08000000 + 0x3000])
    w, h = raw[0], raw[1]
    where = {}
    index = {t: (k, o) for k, row in enumerate(PROPERTY_TILES) for o, t in enumerate(row)}
    for i in range(w * h):
        t = int.from_bytes(raw[2 + 2 * i:4 + 2 * i], "little")
        if t in index:
            where.setdefault(index[t], []).append((i % w, i // w))
    return w, h, where


def rust_stages():
    """crate::conquest::MAPS read from the source: [{id, name, player, enemy}]."""
    import re
    src = CONQUEST_RS.read_text()
    body = src[src.index("pub const MAPS"):src.index("/// The enemy army's colour")]
    out = []
    for m in re.finditer(r"id: (0x[0-9A-Fa-f]+),\s*name: \"([^\"]+)\",\s*player: \((\d+), (\d+)\),\s*enemy: \((\d+), (\d+)\)", body):
        out.append({"id": int(m.group(1), 16), "name": m.group(2), "player": (int(m.group(3)), int(m.group(4))), "enemy": (int(m.group(5)), int(m.group(6)))})
    return out


def maps(a):
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import paths
    data = open(paths.aw2_rom(), "rb").read()
    bad = 0
    if a.all:
        util.say("id   size    HQs apart  bases (army 1 / 2)  airports  ports")
        for mid in VERSUS_IDS:
            r = read_map(data, mid)
            if not r:
                continue
            w, h, where = r
            p, e = where.get((0, 1)), where.get((0, 2))
            if not p or not e:
                continue
            d = abs(p[0][0] - e[0][0]) + abs(p[0][1] - e[0][1])
            util.say(f"{mid:#04x} {w:>2}x{h:<2}   {d:>3}       {len(where.get((1, 1), [])):>2} / {len(where.get((1, 2), [])):<2}          {len(where.get((3, 1), [])) + len(where.get((3, 2), [])):>2}        {len(where.get((4, 1), [])) + len(where.get((4, 2), [])):>2}")
        return 0
    for s in rust_stages():
        r = read_map(data, s["id"])
        if not r:
            util.say(f"{s['name']}: map {s['id']:#x} is not in the ROM")
            bad += 1
            continue
        w, h, where = r
        p, e = where.get((0, 1), [None])[0], where.get((0, 2), [None])[0]
        ok = p == s["player"] and e == s["enemy"]
        bad += not ok
        d = abs(p[0] - e[0]) + abs(p[1] - e[1]) if p and e else -1
        util.say(f"{'ok ' if ok else 'BAD'} {s['id']:#04x} {s['name']}: {w}x{h}, HQs {p} / {e} ({d} apart); Rust says {s['player']} / {s['enemy']}")
        for army in (1, 2):
            util.say(f"       army {army}: " + ", ".join(f"{len(where.get((k, army), []))} {KINDS[k]}" for k in range(5) if where.get((k, army))))
    util.say(f"conquest maps: {len(rust_stages())} stages, {bad} mismatch(es)")
    return 1 if bad else 0
