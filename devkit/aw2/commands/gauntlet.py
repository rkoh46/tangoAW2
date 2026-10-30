"""aw2dev gauntlet: the Gauntlet game mode in the offline harness (docs/dev/gauntlet-mode.md).

  gauntlet start [--co N] [--out DIR]   boots the harness straight into the mode (title, Select Mode, GAUNTLET, the CO pick of CO N, the battle) and leaves a picture of each screen on the way:
                                        1_wheel, 2_co_screen, 3_setup, 4_first_turn (PNG, in DIR or the run's folder); N is an AW2 CO id (default 1 Andy; 93 Aria, 92 Asuka)
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
    return _run({}, ["-k", "gauntlet_mode", "--mode", "ds"]).returncode
