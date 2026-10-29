"""aw2dev campaign: scenes and music of a campaign (docs/dev/campaign-scenes.md, skill aw2-add-campaign).

  campaign scenes [--md] [--mission bh05]   every scene of the BH Campaign with its song (role, AW2 song id) and box count: prologue, intro, victory, the scenes on
                                            the world map after a win, mid-battle triggers; scenes with no song are marked `-` (story scenes without one fail)
  campaign menu [--out DIR]                 start the real app offline with the Dual Strike pack through the AI debug channel, open Select Mode > Campaign and
                                            photograph the chooser at each entry (AW2, DS, BH, Emerald Sun and BH2)
  campaign sheets | sim | difficulty | check | dialogue   the Emerald Sun Campaign (docs/dev/es-campaign.md): review pictures, the mission sim, the difficulty score,
                                            the static rules, the dialogue as one Markdown file; `scenes` and `trace` take `--campaign es`
  campaign playthrough bh2 N [--player cpu|bot] [--days D]   a BH2 mission played to its end in the harness (the computer on every side, or the test player for the player's army), with a report (days, outcome,
                                            takeovers and stage switches, units and funds by day, stalls) and a contact sheet of the key moments (docs/dev/playthrough.md)
  campaign worldmap [--out PNG] [--no-run]  the world-map tests with pictures, then es_world_map.png: the map at three stages with the nodes labelled, the flag states, the unlock moments
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
    a.add_argument("--campaign", default="bh", choices=["bh", "es", "bh2"])
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
    a.add_argument("--scale", type=int, default=100, help="the enemy's strength in percent (a handicap run: its units thinned and its funds scaled)")
    a.add_argument("-j", "--jobs", type=int, default=0, help="missions played at once (default: half the cores)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).sim(a))
    a = cs.add_parser("playthrough", help="play a BH2 mission to the end in the harness (the computer on every side, or the test player for the player's army), day by day, with a report and a contact sheet")
    a.add_argument("campaign", choices=["bh2"])
    a.add_argument("mission", type=int)
    a.add_argument("--player", default="cpu", choices=["cpu", "bot"], help="cpu: the game's computer plays the player's army too; bot: the test player (aw2test.bot) through the pad, going for the HQs")
    a.add_argument("--days", type=int, default=60, help="the day limit over all stages")
    a.add_argument("--god", action="store_true", help="the player's units are healed to full every half second: the player cannot lose, so every wave and stage can be watched")
    a.add_argument("--advance", type=int, default=0, help="with --player bot: an HQ of the stage still not the player's N days after the last one fell is captured for it (to see every wave and stage; says nothing about difficulty)")
    a.add_argument("--waves", action="store_true", help="a whole-map picture at the start and each time an army lands a wave (on the player's next turn; needs --player bot), with every army's units by type and funds (waves.png)")
    a.add_argument("--out", help="the folder for report.md, report.json and contact.png (default devkit/work/campaign/playthrough/<campaign>-m<N>)")
    a.set_defaults(fn=playthrough)
    a = cs.add_parser("difficulty", help="the Emerald Sun missions' difficulty scores (static numbers and the sims' results)")
    a.add_argument("--require-final", action="store_true", help="exit 1 unless M16 is clearly the hardest")
    a.set_defaults(fn=lambda a: __import__("aw2.eslib.cli", fromlist=["x"]).difficulty_cmd(a))
    a = cs.add_parser("dialogue", help="the Emerald Sun dialogue as one readable Markdown file")
    a.add_argument("--out")
    a.set_defaults(fn=lambda a: subprocess.run([sys.executable, str(cfg.REPO / "tools" / "estext" / "render.py")] + ([a.out] if a.out else [])).returncode)
    a = cs.add_parser("check", help="the Emerald Sun Campaign's static rules (inventions only in the Black Hole missions, unit caps, dialogue)")
    a.add_argument("--hq", action="store_true", help="also boot every mission and compare the drawn HQ pictures with the Emerald Sun HQ art (the `co_verify_hq_m*` scenarios; needs the ROMs and the built examples)")
    a.set_defaults(fn=check_with_hq)
    a = cs.add_parser("worldmap", help="the Emerald Sun world map on Omega Land: runs the map and progression tests with pictures and writes es_world_map.png (the map at three stages with the nodes labelled, the flag states, the unlock moments)")
    a.add_argument("--out")
    a.add_argument("--no-run", action="store_true", help="only compose the sheet from the last run's pictures")
    a.set_defaults(fn=worldmap)
    a = cs.add_parser("trace", help="play missions in the harness and trace song / fade / silence")
    a.add_argument("--mission", nargs="*", type=int, default=[1])
    a.add_argument("--out")
    a.add_argument("--campaign", default="bh", choices=["bh", "es", "bh2"])
    a.set_defaults(fn=trace)


def playthrough(a):
    """tests/test_playthrough.py in a harness run; then Markdown and a contact sheet from its JSON (docs/dev/playthrough.md)."""
    from .. import playlib
    out = Path(a.out) if a.out else cfg.REPO / "devkit" / "work" / "campaign" / "playthrough" / (f"{a.campaign}-m{a.mission}-{a.player}" + ("-god" if a.god else ""))
    out.mkdir(parents=True, exist_ok=True)
    js = out / "report.json"
    js.unlink(missing_ok=True)
    env = dict(os.environ, AW2TEST_PLAY_MISSION=str(a.mission), AW2TEST_PLAY_PLAYER=a.player, AW2TEST_PLAY_DAYS=str(a.days), AW2TEST_PLAY_OUT=str(js), AW2TEST_PLAY_GOD="1" if a.god else "0", AW2TEST_PLAY_WAVE_MAPS="1" if a.waves else "0", AW2TEST_PLAY_ADVANCE=str(a.advance))
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    subprocess.run([sys.executable, str(run), "-k", f"playthrough_m{a.mission}", "--mode", "ds"], env=env, cwd=cfg.REPO)
    if not js.exists():
        print("no report: the run did not finish")
        return 1
    rep = json.loads(js.read_text())
    (out / "report.md").write_text(playlib.markdown(rep))
    sheet = playlib.contact_sheet(rep, str(out / "contact.png"))
    if rep.get("waves"):
        print("waves sheet", playlib.wave_sheet(rep, str(out / "waves.png")))
    print(playlib.markdown(rep))
    print(f"report {out / 'report.md'}" + (f", contact sheet {sheet}" if sheet else ""))
    return 0


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
    """The Campaign chooser of the real app, entry by entry (AW2, DS, BH, BH2, Emerald Sun); exit 1 if an entry is missing."""
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
        names = ["aw2", "ds", "bh", "bh2", "emerald_sun"]   # (campaign_menu::DISPLAY_ORDER)
        def entry():
            got = d.peek(0x0203FD14, 1)
            return int(str(got.get("hex", got)), 16) if isinstance(got, dict) else -1
        for k in range(1, 5):
            # (a loaded machine can take a press twice: press until the chooser is on the entry, and say how many presses it took)
            presses = 0
            while entry() != k and presses < 8:
                d.press("DOWN")
                time.sleep(0.8)
                presses += 1
            d.screenshot(str(out / f"chooser_{k}_{names[k]}.png"))
            util.say(f"entry {k} ({names[k]}): {'reached' if entry() == k else 'NOT reached'} in {presses} press(es)")
            bad += entry() != k
        # (no "Coming soon" box is left: Emerald Sun and the BH2 Campaign are both campaigns of the chooser)
        d.press("B")
        time.sleep(0.6)
        d.screenshot(str(out / "chooser_after_box.png"))
    finally:
        proc.kill()
        proc.wait()
        subprocess.run(["pkill", "-9", "-f", str(app)])
    util.say("pictures in", out)
    return bad


def worldmap(a):
    """aw2dev campaign worldmap: the world-map tests (`-k es_world_map`, `-k es_progression`) with AW2TEST_REVIEW_DIR set, then the sheet."""
    from ..eslib import worldmap as wm
    review = cfg.work("campaign", "es", "worldmap")
    if not a.no_run:
        import shutil
        shutil.rmtree(review, ignore_errors=True)
        review.mkdir(parents=True)
        run = cfg.REPO / "tools" / "aw2test" / "run.py"
        sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
        from .maps import _bases
        _bases()
        for k in ("es_world_map_stages", "es_progression"):
            rc = subprocess.run([sys.executable, str(run), "--mode", "ds", "-k", k], env={**os.environ, "AW2TEST_REVIEW_DIR": str(review)}).returncode
            if rc:
                util.die(f"{k} failed")
    out = Path(a.out) if a.out else review / "es_world_map.png"
    wm.sheet(review, cfg.REPO / "tools" / "aw2test" / "out" / "ds", out)
    util.say("wrote", out)
    return 0


def trace(a):
    out = Path(a.out) if a.out else cfg.work("campaign", "trace")
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from .maps import _bases
    _bases()
    env = dict(os.environ, AW2TEST_STORY_DIR=str(out), AW2TEST_STORY_MISSIONS=",".join(map(str, a.mission)))
    r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "-k", f"story_trace_{a.campaign}_missions"], env=env, cwd=cfg.REPO)
    from aw2test import story
    bad = 0
    for n in a.mission:
        f = out / f"{a.campaign}_m{n:02d}.json"
        if not f.exists():
            continue
        print(f"--- M{n}")
        for s in story.scenes(json.loads(f.read_text())):
            gap = s["kind"] == "dialogue" and s["silent"] > 2
            bad += gap
            print(f"{s['start']:6}-{s['end']:6} song {s['song']:5} {s['kind']:9} silent {s['silent']}/{s['samples']} {'SILENT DIALOGUE' if gap else ''} {(s['text'] or '')[:40]}")
    return 1 if (r.returncode or bad) else 0


def check_with_hq(a):
    """`campaign check`: the static rules; with `--hq` also the live HQ check of every mission (fails when an army that should show the Emerald Sun HQ does not)."""
    rc = __import__("aw2.eslib.cli", fromlist=["x"]).check(a)
    if getattr(a, "hq", False):
        import subprocess
        r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "--mode", "ds", "-j", "4", "-k", "co_verify_hq_m"], capture_output=True, text=True)
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("PASS", "FAIL")) or l.strip().startswith("-") or "passed" in l))
        rc = rc or r.returncode
    return rc
