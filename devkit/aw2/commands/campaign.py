"""aw2dev campaign: scenes and music of a campaign (docs/dev/campaign-scenes.md, skill aw2-add-campaign).

  campaign scenes [--md] [--mission bh05]   every scene of the BH Campaign with its song (role, AW2 song id) and box count: prologue, intro, victory, the scenes on
                                            the world map after a win, mid-battle triggers; scenes with no song are marked `-` (story scenes without one fail)
  campaign trace [--mission N ...]          play the missions in the offline harness (CO screen, card, intro, forced win, victory, results, map scenes) and
                                            sample every 20 frames: song, fade, text, screen, the sound's loudness; prints scene -> song and flags silent gaps
"""
import json, os, re, subprocess, sys
from pathlib import Path
from .. import cfg, util

NEEDS = re.compile(r"(prologue|intro|victory|after)")


def register(sub):
    c = sub.add_parser("campaign", help="scenes and music of the BH Campaign: scenes, trace (docs/dev/campaign-scenes.md)")
    cs = c.add_subparsers(dest="campcmd", required=True)
    a = cs.add_parser("scenes", help="every scene with its song")
    a.add_argument("--md", action="store_true")
    a.add_argument("--mission")
    a.set_defaults(fn=scenes)
    a = cs.add_parser("trace", help="play missions in the harness and trace song / fade / silence")
    a.add_argument("--mission", nargs="*", type=int, default=[1])
    a.add_argument("--out")
    a.set_defaults(fn=trace)


def scene_rows():
    exe = util.example_bin("aw2_campaign_scenes")
    util.check_fresh(exe, "aw2_campaign_scenes")
    env = dict(os.environ, TANGOAW2_DS_ROM=str(cfg.ds_rom()))
    r = subprocess.run([str(exe), str(cfg.aw2_rom())], capture_output=True, text=True, env=env)
    if r.returncode:
        util.die("aw2_campaign_scenes failed: " + r.stderr[-300:])
    return [l.split("\t") for l in r.stdout.splitlines()]


def scenes(a):
    rows = scene_rows()
    if a.mission:
        rows = [r for r in rows if r[0] == a.mission]
    bad = [r for r in rows if r[1] != "trigger" and r[3] == "-"]
    if a.md:
        print("| Mission | Scene | Boxes | Track | AW2 song |\n|---|---|---|---|---|")
    for m, kind, n, label, sid in rows:
        print(f"| {m} | {kind} | {n} | {label} | {sid} |" if a.md else f"{m:9} {kind:9} {n:>3} boxes  {label:12} {sid}")
    for r in bad:
        print("NO SONG:", r[0], r[1], file=sys.stderr)
    return 1 if bad else 0


def trace(a):
    out = Path(a.out) if a.out else cfg.work("campaign", "trace")
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from .maps import _bases
    _bases()
    env = dict(os.environ, AW2TEST_STORY_DIR=str(out), AW2TEST_STORY_MISSIONS=",".join(map(str, a.mission)))
    r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "-k", "story_trace_bh_missions"], env=env, cwd=cfg.REPO)
    from aw2test import story
    bad = 0
    for n in a.mission:
        f = out / f"bh_m{n:02d}.json"
        if not f.exists():
            continue
        print(f"--- M{n}")
        for s in story.scenes(json.loads(f.read_text())):
            gap = s["kind"] == "dialogue" and s["silent"] > 2
            bad += gap
            print(f"{s['start']:6}-{s['end']:6} song {s['song']:5} {s['kind']:9} silent {s['silent']}/{s['samples']} {'SILENT DIALOGUE' if gap else ''} {(s['text'] or '')[:40]}")
    return 1 if (r.returncode or bad) else 0
