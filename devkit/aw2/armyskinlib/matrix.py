"""The skin on every colour in every army count (`aw2dev armyskin matrix`, docs/dev/army-packs.md).

A skin is a data file on one of AW2's five colours, and the colour decides which tables of the ROM image are patched and which backups sit in free ROM. Released
0.8.7 put the Dual Strike pack's backup of colour 5 over the first skin's table of battle figures and portraits: a five-army match with the skin on Black Hole's
colour (and the pack) corrupted the game's memory the first time the army opened its build menu. `check --live` only walks colour 1 on the 2P map; this walks
armies 2..5 x colours 1..5 with the pack on and, in each: the skins' rooms in free ROM are sane (`skincheck`), the unit panel and the build menu show the skin's
plume, a battle scene wears its helmet.

Where a map does not give the skin the colour (armies 2..4 never put it on 5, nor a 2P match on 3: the skin takes the lowest colour nobody has), the test aids
move it there as a campaign mission does: `aid colour 1 C` (the army's colour and palette rows) and `aid skincolour C` (the skin's state byte).
"""
import re
from pathlib import Path

from PIL import Image

from . import scenarios
from .check import _colours

COUNTS = (2, 3, 4, 5)
COLOURS = (1, 2, 3, 4, 5)
QUICK = ((2, 5), (3, 3), (4, 4), (5, 5))     # (armies, colour): the ones that stood on the Dual Strike backup of colour 5 and the lowest others
# (the plume's red in a shot: the unit panel and the build menu's panel show it at 32 x 32, a battle scene's soldier at about 80 pixels)
NEED = {"panel": 8, "build": 25, "build_mech": 25, "scene2": 80, "scene3": 80}


def others(n, colour):
    """The colours the other seats pick, none of them `colour`."""
    return [c for c in (2, 3, 4, 5, 1) if c != colour][: n - 1]


def natural(n, colour):
    """The colour the skin gets from the army page when the others pick `others(n, colour)`: the lowest nobody has."""
    taken = set(others(n, colour))
    return min(c for c in COLOURS if c not in taken)


def ids(n, colour):
    return [6] + others(n, colour)


def controller(n, colour):
    """The seat that plays army 1, whose turn it is first: seat 0, the skin's, on every map (a five-army map's armies keep their seats' order; the colours are the picks)."""
    return 0


def probe(n, colour, ds, out):
    """(hq, base, occupied) of army 1 on the n-army map the room gets with these picks: one harness run that prints the army's properties (HQ kind 8, base kind 14) and every unit's cell."""
    from .. import harness
    d = Path(out) / f"probe_{n}p_colour{colour}"
    d.mkdir(parents=True, exist_ok=True)
    script = scenarios.header(ids(n, colour), five=(n == 5)) + "props 1\nunits\n"
    (d / "script.txt").write_text(script)
    rc, log = harness.run_script(d / "script.txt", d, ds=ds)
    text = Path(log).read_text()
    cells = {}
    for kind, x, y in re.findall(r"army 1 kind (\d+) at \((\d+),(\d+)\)", text):
        cells.setdefault(int(kind), []).append((int(x), int(y)))
    if rc or 8 not in cells or 14 not in cells:
        raise RuntimeError(f"{n} armies: no HQ and base of army 1 found (rc {rc}, properties {sorted(cells)}; {log})")
    occupied = {(int(x), int(y)) for x, y in re.findall(r"unit id \d+ army \d+ kind \d+ at \((\d+),(\d+)\)", text)}
    return cells[8][0], cells[14][0], occupied


def script(n, colour, hq, base, occupied=()):
    """The harness script: the room's army page with the skin first, the battle, the skin moved to `colour` if the map did not give it that, then a panel, the build menu
    and a battle scene on army 1 (the skin's, or wearing its colour) next to army 2."""
    ctl = controller(n, colour)
    hx, hy = hq
    # (the Infantry stands on the HQ and the enemy on a free neighbour: the aids place a unit on any cell, so only another unit's cell is out)
    free = [(x, y) for x, y in ((hx + 1, hy), (hx - 1, hy), (hx, hy + 1), (hx, hy - 1)) if (x, y) not in occupied and x >= 0 and y >= 0]
    if (hx, hy) in occupied or not free:
        raise RuntimeError(f"{n} armies: no free cell for the test units beside the HQ {hq}")
    sx, sy = free[0]
    body = ""
    if n == 5:
        # (an army in Black Hole's colour starts its turn with a camera sweep over the map: let it end before the first key)
        body += "wait 700\n"
    elif natural(n, colour) != colour:
        body += f"aid colour 1 {colour}\naid skincolour {colour}\nwait 60\n"
    c = ctl
    body += (
        "skincheck\n"
        f"aid unit 1 inf {hx} {hy}\naid unit 2 inf {sx} {sy}\n"
        f"wait 20\ngoto {c} {hx} {hy}\nwait 10\npress {c} A\nwait 30\npress {c} B\nwait 20\n"
        f"shot panel {c}\nskincheck\n"
        f"goto {c} {base[0]} {base[1]}\nwait 10\npress {c} A\nwait 40\nshot build {c}\npress {c} DOWN\nwait 20\nshot build_mech {c}\npress {c} B\nwait 20\nskincheck\n"
        f"goto {c} {hx} {hy}\nwait 20\npress {c} A\nwait 30\npress {c} A\nwait 30\npress {c} A\nwait 20\npress {c} A\nwait 100\nshot scene2 {c}\nwait 60\nshot scene3 {c}\nskincheck\n"
    )
    return scenarios.header(ids(n, colour), five=(n == 5)) + body


def crest(path):
    return sum(k for c, k in _colours(path).items() if c[0] > 150 and c[1] < 100 and c[2] < 100 and c[0] - c[1] > 80)


def run(pairs=None, ds=True, out=None, keep=False, say=print):
    """Every (armies, colour) in `pairs` (default all): returns (failures, report lines)."""
    from .. import cfg, harness
    out = Path(out or cfg.work("armyskin", "matrix"))
    out.mkdir(parents=True, exist_ok=True)
    pairs = pairs or [(n, c) for n in COUNTS for c in COLOURS]
    fails, rep = [], []
    for n, colour in pairs:
        # (the room's first n-army map is not always the same one: the probe is the same room with the same picks, run first)
        try:
            hq, base, occupied = probe(n, colour, ds, out)
        except RuntimeError as e:
            fails.append(str(e))
            continue
        d = out / f"{n}p_colour{colour}"
        d.mkdir(parents=True, exist_ok=True)
        try:
            (d / "script.txt").write_text(script(n, colour, hq, base, occupied))
        except RuntimeError as e:
            fails.append(str(e))
            continue
        rc, log = harness.run_script(d / "script.txt", d, ds=ds)
        text = Path(log).read_text()
        tag = f"{n} armies, skin on colour {colour}"
        if rc:
            problems = [l.split(": ", 1)[1] for l in text.splitlines() if l.startswith("skincheck @") and "FAIL" not in l and not l.endswith("ok")]
            fails.append(f"{tag}: the harness script failed ({log}){' ' + '; '.join(problems[:2]) if problems else ''}")
            continue
        got = {}
        for shot, need in NEED.items():
            f = d / f"{shot}_s{controller(n, colour)}.bmp"
            if not f.exists():
                fails.append(f"{tag}: shot {shot} was not taken")
                continue
            got[shot] = crest(f)
            if got[shot] < need:
                fails.append(f"{tag}: {shot} shows {got[shot]} pixels of the skin's crest red (needs >= {need})")
        rep.append(f"  {tag}: " + ", ".join(f"{k} {v}" for k, v in got.items()))
    if not keep:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
    return fails, rep
