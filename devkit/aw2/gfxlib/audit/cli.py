"""`aw2dev gfx audit`: the argument parser and the command (docs/dev/graphics.md, "The audit")."""
import shlex
import sys
import time
from pathlib import Path

from ... import cfg, util


def register(gs):
    a = gs.add_parser("audit", help="sweep every mode's screens in the three looks, run every detector, write report.md / report.json and contact sheets; exit 1 on findings")
    a.add_argument("--modes", help="comma list of modes (default: all; `--list` shows them)")
    a.add_argument("--scenes", help="comma list of scene names")
    a.add_argument("--looks", help="comma list of looks: aw2_nopack, aw2, ds_tilt, ds_flat (default: all of each scene's)")
    a.add_argument("--list", action="store_true", help="list the scenes and the looks each runs in, then stop")
    a.add_argument("-j", "--jobs", type=int, default=4, help="scene runs at a time (each is one emulator; default 4)")
    a.add_argument("--out", help="output folder (default devkit/work/gfx/audit/<time>); pictures, dumps, report and sheets go there")
    a.add_argument("--reuse", metavar="DIR", help="do not run the scenes: judge the pictures an earlier run left in DIR again (after a detector change)")
    a.add_argument("--only", help="comma list of detectors to run (blank, stripes, dark, sprites, palette, text, leftover, seams)")
    a.add_argument("--binary-dir", help="another build's target/release/examples (the scenes run its aw2_script and aw2_online_text_audit)")
    a.add_argument("--timeout", type=int, default=1500, help="seconds a scene run may take")
    a.add_argument("--strict", action="store_true", help="warnings fail the run too")
    a.add_argument("--no-sheets", action="store_true")
    a.set_defaults(fn=audit)


def audit(a):
    from . import runner
    csv = lambda v: [x for x in (v or "").split(",") if x] or None
    if a.list:
        for s in runner.scene_list():
            print(f"{s['mode']:14} {s['scene']:24} {','.join(s['looks']):32} {s['doc']}")
        return 0
    modes, scenes, looks = csv(a.modes), csv(a.scenes), csv(a.looks)
    out = Path(a.reuse or a.out or cfg.work("gfx", "audit", time.strftime("%Y%m%d-%H%M%S")))
    if a.reuse:
        jobs = [(p.parts[-3], p.parts[-2], p.parts[-1]) for p in sorted(out.glob("*/*/*")) if (p / "manifest.json").exists()]
        jobs = [j for j in jobs if (not modes or j[0] in modes) and (not scenes or j[1] in scenes) and (not looks or j[2] in looks)]
    else:
        util.check_fresh(util.example_bin("aw2_script"), "aw2_script") if not a.binary_dir else None
        jobs = runner.plan(modes, scenes, looks)
    if not jobs:
        util.die("no scene matches; `aw2dev gfx audit --list`")
    out.mkdir(parents=True, exist_ok=True)
    util.say(f"audit: {len(jobs)} scene runs -> {out}")
    if not a.reuse:
        runner.sweep(out, jobs, a.jobs, a.binary_dir, a.timeout)
    result = runner.judge(out, jobs, csv(a.only))
    sheets_out = {} if a.no_sheets else runner.make_sheets(out, jobs, result["findings"])
    line = "aw2dev gfx audit " + " ".join(shlex.quote(x) for x in sys.argv[3:]) if len(sys.argv) > 3 else "aw2dev gfx audit"
    fails, warns = runner.write_report(out, jobs, result, sheets_out, line)
    for f in fails[:40]:
        print(f"FAIL {f['detector']:8} {f['mode']}/{f['scene']}/{f['look']} {f.get('shot', '')}: {f['msg']}")
    if len(fails) > 40:
        print(f"... {len(fails) - 40} more failing findings in the report")
    util.say(f"audit done: {len(fails)} failing, {len(warns)} warning(s); report {out / 'report.md'}")
    return 1 if fails or (a.strict and warns) else 0
