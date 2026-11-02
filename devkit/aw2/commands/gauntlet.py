"""aw2dev gauntlet: the Gauntlet game mode in the offline harness (docs/dev/gauntlet-mode.md).

  gauntlet start [--co N] [--out DIR]   boots the harness straight into the mode (title, Select Mode, GAUNTLET, the CO pick of CO N, the battle) and leaves a picture of each screen on the way:
                                        1_wheel, 2_co_screen, 3_setup, 4_first_turn (PNG, in DIR or the run's folder); N is an AW2 CO id (default 1 Andy; 93 Aria, 92 Asuka)
  gauntlet rout-sheet [--out FILE]      Cinder Sea's first rout (before, during, after) in the real app in the three looks (AW2 graphics, Dual Strike graphics, the tilted map): `gauntlet_rout_pictures`
                                        saves three console checkpoints, the app boots each (needs `cargo build --release -p tango`) and a sheet is composed (rows: looks, columns: moments)
  gauntlet test                         the Gauntlet's regression tests (`run.py -k gauntlet_mode --mode ds`)
"""
import os, subprocess, sys, tempfile
from .. import cfg, util


def register(sub):
    g = sub.add_parser("gauntlet", help="the Gauntlet mode: boot into it with pictures, run its tests (docs/dev/gauntlet-mode.md)")
    gs = g.add_subparsers(dest="gauntletcmd", required=True)
    a = gs.add_parser("start", help="title -> GAUNTLET -> CO pick -> the battle, with a picture of each screen")
    a.add_argument("--co", type=int, default=1, help="AW2 CO id to pick (default 1, Andy; 93 Aria, 92 Asuka)")
    a.add_argument("--out", help="folder for the pictures (default: the run's own folder, printed)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=start)
    a = gs.add_parser("test", help="run the Gauntlet mode's tests")
    a.set_defaults(fn=test)
    a = gs.add_parser("rout-sheet", help="the rout's before/during/after in the real app, in all three looks, as one sheet")
    a.add_argument("--out", help="the sheet's PNG (default: devkit/work/gauntlet/rout_sheet.png)")
    a.set_defaults(fn=rout_sheet)


def _run(extra_env, args):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    env = dict(os.environ, **extra_env)
    return subprocess.run([sys.executable, str(run)] + args, env=env, cwd=cfg.REPO, text=True)


def start(a):
    out = a.out or tempfile.mkdtemp(prefix="gauntlet_start_")
    r = _run({"AW2TEST_GAUNTLET_CO": str(a.co), "AW2TEST_GAUNTLET_OUT": out}, ["-k", "gauntlet_tool_start", "--mode", "ds"] + (["-v"] if a.verbose else []))
    names = sorted(f for f in os.listdir(out)) if os.path.isdir(out) else []
    util.say("pictures:", out, names)
    return r.returncode


def test(a):
    return _run({}, ["-k", "gauntlet", "--mode", "ds"]).returncode


LOOKS = [("AW2 graphics", dict(ds=True, graphics=False)), ("DS graphics, no tilt", dict(ds=True, graphics=True)), ("DS graphics + tilt", dict(ds=True, graphics=True, tilt=True))]
MOMENTS = [("before the capture", "rout_before"), ("while the units go", "rout_during"), ("after", "rout_after")]


def rout_sheet(a):
    """The rout in the real app's own pictures (never the full screen: the app's screenshot is its game window)."""
    from PIL import Image, ImageDraw
    from ..armyskinlib import look as lk
    work = cfg.work("gauntlet")
    work.mkdir(parents=True, exist_ok=True)
    ck = lk.CKPT()
    ck.mkdir(parents=True, exist_ok=True)
    r = _run({"AW2TEST_ROUT_CKPT": str(ck)}, ["-k", "gauntlet_rout_pictures", "--mode", "ds"])
    if r.returncode:
        return r.returncode
    rows = []
    for title, kw in LOOKS:
        row = []
        for _, name in MOMENTS:
            shot = work / f"{name}_{title.split()[0].lower()}_{'tilt' if kw.get('tilt') else 'flat'}.png"
            lk.look(name, str(shot), scale=1 if kw.get("tilt") else None, **kw)
            row.append(Image.open(shot).convert("RGB"))
        rows.append((title, row))
    w, h = rows[0][1][0].size
    k = 2
    pad, head = 6, 22
    sheet = Image.new("RGB", (pad + 3 * (w * k + pad), head + len(rows) * (h * k + head + pad)), (24, 24, 32))
    dr = ImageDraw.Draw(sheet)
    for j, (m, _) in enumerate(MOMENTS):
        dr.text((pad + j * (w * k + pad), 4), m, fill=(255, 255, 255))
    for i, (title, row) in enumerate(rows):
        y = head + i * (h * k + head + pad)
        dr.text((pad, y), title, fill=(255, 220, 80))
        for j, im in enumerate(row):
            sheet.paste(im.resize((w * k, h * k), Image.NEAREST), (pad + j * (w * k + pad), y + 14))
    out = a.out or str(work / "rout_sheet.png")
    sheet.save(out)
    util.say("sheet:", out)
    return 0
