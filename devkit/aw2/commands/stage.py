"""aw2dev stage: inspect and force a mission's stage switch in the harness (docs/dev/stages.md).

  stage next MISSION [--out FILE]   enters BH2 mission MISSION in the offline harness and plays it to its stage switch with real captures (the mission's own triggers: tests/test_stage_tool.py
                                    STAGE_TRIGGERS names them), then prints what the switch did: stage, map, each army's units and funds before and after, the player's units and meter carried over.
                                    Pictures of the moment before and of the new stage's first frame are left in the run's folder. A mission with stages gets a row in STAGE_TRIGGERS.
  stage show FILE.sav               a suspended game's stage mark (and the rest of the save: `aw2dev save inspect`)
"""
import json, os, subprocess, sys, tempfile
from .. import cfg, util


def register(sub):
    c = sub.add_parser("stage", help="inspect / force a mission's stage switch in the harness (docs/dev/stages.md)")
    cs = c.add_subparsers(dest="stagecmd", required=True)
    a = cs.add_parser("next", help="play the mission to its stage switch and report what the switch did")
    a.add_argument("mission", type=int)
    a.add_argument("--out", help="write the report (JSON) here too")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=next_stage)
    a = cs.add_parser("show", help="the stage mark of a suspended game")
    a.add_argument("file")
    a.set_defaults(fn=show)


def next_stage(a):
    out = a.out or tempfile.mktemp(suffix=".json")
    env = dict(os.environ, AW2TEST_STAGE_MISSION=str(a.mission), AW2TEST_STAGE_OUT=out)
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    r = subprocess.run([sys.executable, str(run), "-k", f"stage_tool_m{a.mission}", "--mode", "ds"] + (["-v"] if a.verbose else []), env=env, cwd=cfg.REPO, capture_output=not a.verbose, text=True)
    if not os.path.exists(out):
        print(f"no report: the test did not finish (mission {a.mission} has no row in STAGE_TRIGGERS, or the run failed)")
        print((r.stdout or "")[-800:])
        return 1
    rep = json.load(open(out))
    print(render(rep))
    return r.returncode


def render(rep):
    b, a = rep["before"], rep["after"]
    lines = [f"M{rep['mission']} {rep['title']}: stage switch after {', '.join(rep['triggers'])} captured",
             f"  before: stage {b['stage']}, map {b['map'][0]}x{b['map'][1]}, day {b['day']}, five-army {'yes' if b['five_on'] else 'no'}, units {b['units']}, funds {b['funds']}",
             f"  after:  stage {a['stage']}, map {a['map'][0]}x{a['map'][1]}, day {a['day']}, five-army {'yes' if a['five_on'] else 'no'}, units {a['units']}, funds {a['funds']}",
             f"  the player's units by type before {b['player_types']}, after {rep['carried']}; its power meter {b['player_meter']} -> {a['player_meter']}",
             f"  pictures: {rep['dir']}/before_switch.bmp, after_switch.bmp"]
    return "\n".join(lines)


def show(a):
    from .. import savelib
    rep = savelib.inspect(a.file)
    for s in rep["slots"]:
        st = s["marks"].get("stage_number")
        print(f"slot {s['slot']} ({s['name']}): " + (f"saved on stage {st + 1}" if st is not None else "the mission's own stage (no stage mark)"))
    return 0
