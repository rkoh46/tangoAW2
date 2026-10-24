"""aw2dev campaign: scenes and music of a campaign (docs/dev/campaign-scenes.md, skill aw2-add-campaign).

  campaign scenes [--md] [--mission bh05]   every scene of the BH Campaign with its song (role, AW2 song id) and box count: prologue, intro, victory, the scenes on
                                            the world map after a win, mid-battle triggers; scenes with no song are marked `-` (story scenes without one fail)
  campaign menu [--out DIR]                 start the real app offline with the Dual Strike pack through the AI debug channel, open Select Mode > Campaign and
                                            photograph the chooser at each entry (AW2, DS, BH, BH2 and Emerald Sun placeholders) and the "Coming soon" boxes
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
    a.add_argument("--campaign", default="bh", choices=["bh", "es"])
    a.set_defaults(fn=scenes)
    a = cs.add_parser("menu", help="photograph the Campaign sub-menu of the real app")
    a.add_argument("--out")
    a.set_defaults(fn=menu)
    a = cs.add_parser("sheets", help="the Emerald Sun missions' review pictures with MISSION N - Title burned in, and a contact sheet per act")
    a.add_argument("--mission", nargs="*", type=int)
    a.add_argument("--out")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).sheets(a))
    a = cs.add_parser("sim", help="the mission sim: the test player or the computer plays an Emerald Sun mission in the harness")
    a.add_argument("--mission", nargs="+", type=int, required=True)
    a.add_argument("--player", nargs="+", default=["bot"], choices=["bot", "cpu"])
    a.add_argument("--seeds", type=int, default=1)
    a.add_argument("--days", type=int, default=25)
    a.add_argument("-j", "--jobs", type=int, default=0, help="missions played at once (default: half the cores)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).sim(a))
    a = cs.add_parser("difficulty", help="the Emerald Sun missions' difficulty scores (static numbers and the sims' results)")
    a.add_argument("--require-final", action="store_true", help="exit 1 unless M16 is clearly the hardest")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).difficulty_cmd(a))
    a = cs.add_parser("check", help="the Emerald Sun Campaign's static rules (inventions only in the Black Hole missions, unit caps, dialogue)")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).check(a))
    a = cs.add_parser("trace", help="play missions in the harness and trace song / fade / silence")
    a.add_argument("--mission", nargs="*", type=int, default=[1])
    a.add_argument("--out")
    a.set_defaults(fn=trace)


def scene_rows(campaign="bh"):
    exe = util.example_bin("aw2_campaign_scenes")
    util.check_fresh(exe, "aw2_campaign_scenes")
    env = dict(os.environ, TANGOAW2_DS_ROM=str(cfg.ds_rom()))
    r = subprocess.run([str(exe), str(cfg.aw2_rom()), campaign], capture_output=True, text=True, env=env)
    if r.returncode:
        util.die("aw2_campaign_scenes failed: " + r.stderr[-300:])
    return [l.split("\t") for l in r.stdout.splitlines()]


def scenes(a):
    rows = scene_rows(a.campaign)
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


def menu(a):
    """The Campaign chooser of the real app, entry by entry (the placeholders' boxes too); exit 1 if an entry or a box is missing."""
    import json, time, subprocess
    from .. import profiles
    out = Path(a.out) if a.out else cfg.work("campaign", "menu")
    out.mkdir(parents=True, exist_ok=True)
    binary = cfg.REPO / "target" / "release" / "tango"
    util.check_fresh(binary, "tango")
    profiles.ensure("skinds", pack=True)
    cj = profiles.profile_dir("skinds") / "config" / "config.json"
    conf = json.loads(cj.read_text())
    conf.update({"ds_graphics": True, "ds_tilt": False})
    cj.write_text(json.dumps(conf, indent=2))
    app = profiles.test_app(binary)
    env = dict(os.environ, TANGOAW2_PROFILE=str(profiles.profile_dir("skinds")), TANGOAW2_AI_DEBUG="0", AW2DEV_LOOK="1")
    proc = subprocess.Popen([str(app)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cfg.REPO)
    bad = 0
    try:
        addr, t0 = None, time.time()
        while time.time() - t0 < 60 and addr is None:
            line = proc.stdout.readline()
            if not line:
                break
            if "AI_DEBUG_LISTENING" in line:
                addr = line.split()[-1]
        if not addr:
            util.die("the app did not open the AI debug channel")
        sys.path.insert(0, str(cfg.REPO / "tools" / "aidebug"))
        from client import AiDebug
        d = AiDebug.connect(addr)
        for _ in range(40):
            if d.hello().get("session") not in (None, "none"):
                break
            time.sleep(1)
        d.start_offline()
        d.wait_until({"phase": {"in": ["title", "select_mode"]}}, 60)
        time.sleep(1.0)
        d.press_until("START", {"phase": "select_mode"}, timeout=40)
        time.sleep(1.5)
        d.press_until("A", {"screen_info.box_open": True}, timeout=30, gap=1.0)
        time.sleep(1.0)
        d.screenshot(str(out / "chooser_0_aw2.png"))
        names = ["aw2", "ds", "bh", "bh2", "emerald_sun"]
        for k in range(1, 5):
            d.press("DOWN")
            time.sleep(0.8)
            d.screenshot(str(out / f"chooser_{k}_{names[k]}.png"))
        # the Emerald Sun box (the last entry, the cursor is on it)
        d.press("A")
        time.sleep(0.8)
        d.screenshot(str(out / "box_emerald_sun.png"))
        d.press("A")
        time.sleep(0.6)
        d.press("UP")
        time.sleep(0.6)
        d.press("A")
        time.sleep(0.8)
        d.screenshot(str(out / "box_bh2.png"))
        d.press("B")
        time.sleep(0.6)
        d.screenshot(str(out / "chooser_after_box.png"))
    finally:
        proc.kill()
        proc.wait()
        subprocess.run(["pkill", "-9", "-f", str(app)])
    util.say("pictures in", out)
    return bad


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
