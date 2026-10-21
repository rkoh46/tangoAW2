"""aw2dev command line. Run `aw2dev --help`; docs/dev/README.md has the quick start, docs/dev/testing.md says what to run for which change."""
import argparse, sys
from . import net, audit, build, check, clean, cfg, harness, install, live, profiles, release, sheet, suite, util


def main(argv=None):
    p = argparse.ArgumentParser(prog="aw2dev", description="tangoAW2 developer CLI: build, test, live-debug, release. Paths come from devkit/config.toml (override: config.local.toml, AW2DEV_* env).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build", help="cargo build (default: release tango; --examples adds the harness examples)")
    s.add_argument("--ios", action="store_true", help="ios/build.sh -> dist/tangoaw2-<ver>-ios.ipa (DEVELOPER_DIR set)")
    s.add_argument("--sim", action="store_true", help="ios/build.sh --sim -> dist/tangoAW2-sim.app")
    s.add_argument("--release", action="store_true", help="release-dist profile (what install-mac and releases use)")
    s.add_argument("--examples", action="store_true", help="also build the tango-gamesupport-aw2 examples (harness, audits)")
    s.add_argument("--all", action="store_true", help="tango + examples")
    s.set_defaults(fn=build.build)

    s = sub.add_parser("test", help="cargo test --lib for the gamesupport, session and match crates")
    s.add_argument("package", nargs="*")
    s.set_defaults(fn=build.test)

    s = sub.add_parser("harness", help="run one offline harness script (aw2_room_teams)")
    s.add_argument("script", nargs="?", help="path or name of a tango-gamesupport-aw2/examples/*.txt script")
    s.add_argument("--seats", type=int, help="override the script's `n N`")
    s.add_argument("--sample", type=int, help="AW2_SAMPLE: sample every K ticks (black-run report)")
    s.add_argument("--dump", action="store_true", help="AW2_DUMP: every sampled frame as BMP")
    s.add_argument("--cam-log", action="store_true", help="AW2_CAM_LOG=1")
    s.add_argument("--leak", action="store_true", help="AW2_LEAK_CHECK=1")
    s.add_argument("--ds", action="store_true", help="load the Dual Strike pack (TANGOAW2_DS_ROM)")
    s.add_argument("--list", action="store_true", help="list the scripts")
    s.set_defaults(fn=lambda a: harness.cmd(a))

    s = sub.add_parser("suite", help="the harness suite (prints failures only, ends `suite done bad=N`)")
    s.add_argument("--jobs", type=int, default=3)
    s.add_argument("--only", nargs="*", help="substrings of scenario names to run")
    s.add_argument("--keep", action="store_true", help="keep the per-script output")
    s.set_defaults(fn=lambda a: suite.run(a.jobs, a.only, a.keep))

    s = sub.add_parser("live", help="live scenario on real app clients (loopback + matchmaking server)")
    s.add_argument("scenario", nargs="?", help="a scenario or flow (see --list), `rejoin` (with the driver name next), or `ios-gate`")
    s.add_argument("pad_or_sub", nargs="?", help="rejoin: the driver (unr-guest, lobby-host, ...)")
    s.add_argument("--players", type=int)
    s.add_argument("--fog", choices=["on", "off"], default="on")
    s.add_argument("--hz", type=int, help="screenshots per second per seat (TANGOAW2_RUN_SHOT_HZ; 60 for walk analysis)")
    s.add_argument("--rounds", type=int, default=2, help="lobby flow: rounds of end-turn")
    s.add_argument("--kill", help="SEATS:WHEN kill -9 (SEATS 1 or 1+2; WHEN eliminated | log:TEXT | armyN | seconds)")
    s.add_argument("--stop", help="SEAT:WHEN:DURATION SIGSTOP a seat, SIGCONT later")
    s.add_argument("--after-kill", type=int, help="seconds to keep running after a kill (default 90)")
    s.add_argument("--max", type=int, dest="max_s", help="run timeout seconds (default 420)")
    s.add_argument("--tag")
    s.add_argument("--profile", action="append", default=[], metavar="SEAT=NAME", help="use another profile for a seat, e.g. 2=guestnp (no pack)")
    s.add_argument("--local", action="store_true", help="local signalling mock, public endpoints blocked (polite; same as `net sim`)")
    s.add_argument("--reveal", action="store_true", help="lobby: shots through the map reveal")
    s.add_argument("--sim", action="store_true", help="lobby: all seats pick at once in private")
    s.add_argument("--entry", choices=["selectmap", "lobby", "title"], default="selectmap", help="solo: where the window starts (offline Versus SELECT MAP, the LOBBY menu, the title)")
    s.add_argument("--pad", default="", help="solo: pad lines separated by ';' (`shot NAME` writes NAME.png into the run dir)")
    s.add_argument("--kinds", help="ios-gate: seats, e.g. mac,iphone (mac | iphone | iphone2 | ipad)")
    s.add_argument("--event", action="append", metavar="AT:ACTION:SEAT[:ARG]", help="ios-gate: kill | relaunch | bg | stop (see devkit/aw2/ios.py)")
    s.add_argument("--picks", help="per-seat map pick, e.g. 0,3,5 (DOWN presses from the first map) or t1:0,0 (tab RIGHT presses : DOWN presses); the draw between different picks is random")
    s.add_argument("--list", action="store_true")
    s.set_defaults(fn=_live)

    s = sub.add_parser("check", help="pass/fail checkers over a live run (writes check.json)")
    s.add_argument("run", nargs="?", help="run dir, name fragment, or `latest`")
    for n in check.ALL:
        s.add_argument(f"--{n}", action="store_true")
    s.add_argument("--colours", action="store_true", help="the harness colour scripts + colour matrix (no run needed)")
    s.add_argument("--seats", help="limit the hash check to these seats (a killed seat), e.g. 0,1")
    s.add_argument("--black-ms", type=int, default=4000)
    s.set_defaults(fn=check.cmd)

    s = sub.add_parser("sheet", help="contact sheets and strips of a live run")
    s.add_argument("run", nargs="?", default="latest")
    s.add_argument("--around", type=int, metavar="N", help="all frames around the N-th act (see --kind)")
    s.add_argument("--kind", default="any", help="act kind for --around (move, attack, power, capture, ...)")
    s.add_argument("--strip", action="store_true", help="with --around: the mover's window over every waiting window, frame by frame")
    s.add_argument("--events", action="store_true", help="one frame set per non-build act on --seat")
    s.add_argument("--seat", type=int)
    s.add_argument("--seats", help="comma list")
    s.add_argument("--pre", type=int, help="ms before the act")
    s.add_argument("--post", type=int, help="ms after the act")
    s.add_argument("--every", type=int, default=1)
    s.add_argument("--t0", type=float, default=0.0)
    s.add_argument("--t1", type=float)
    s.add_argument("--frames", type=int, default=10)
    s.set_defaults(fn=sheet.cmd)

    s = sub.add_parser("audit", help="text audit of the online pages, or the map audit")
    s.add_argument("what", choices=["text", "maps"])
    s.add_argument("--ds", action="store_true", help="with the Dual Strike pack")
    s.add_argument("--md", action="store_true")
    s.add_argument("--sources", action="store_true")
    s.add_argument("--needs-pack", action="store_true")
    s.add_argument("--full", action="store_true")
    s.set_defaults(fn=lambda a: audit.text(a) if a.what == "text" else audit.maps(a))

    s = sub.add_parser("install-mac", help="copy release-dist into /Applications/TangoAW2.app (never closes a running app)")
    s.set_defaults(fn=install.install)

    s = sub.add_parser("release", help="the release checklist; refuses to push without --yes")
    s.add_argument("version")
    s.add_argument("--notes", required=True, help="release notes file (becomes the tag message)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--yes", action="store_true", help="the user approved: allow the push")
    s.add_argument("--force", action="store_true", help="continue despite failed preflight checks")
    s.add_argument("--skip", nargs="*", choices=["build", "tests", "install-mac", "ipa", "watch", "assets"], help="steps to leave out")
    s.set_defaults(fn=release.release)

    s = sub.add_parser("clean", help="free disk (dry run unless --yes); shows df")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--runs", action="store_true", help="old run PNGs")
    s.add_argument("--days", type=int, help="age for --runs (config clean.run_days)")
    s.add_argument("--harness", action="store_true", help="work/harness, suite, audit output")
    s.add_argument("--targets", action="store_true", help="target/ dirs")
    s.add_argument("--other-targets", action="store_true", help="also delete target/ of other worktrees")
    s.add_argument("--keep-targets-too", action="store_true", help="also the kept worktrees' target/")
    s.add_argument("--worktrees", action="store_true", help="list stale worktrees")
    s.add_argument("--remove-worktrees", action="store_true", help="remove them (branches are kept)")
    s.set_defaults(fn=clean.clean)

    s = sub.add_parser("profiles", help="create/reset the test profiles (host, guest, guest2..)")
    s.add_argument("--reset", action="store_true")
    s.add_argument("--n", type=int, default=5)
    s.set_defaults(fn=_profiles)

    s = sub.add_parser("runs", help="list recent live runs")
    s.add_argument("-n", type=int, default=15)
    s.set_defaults(fn=_runs)

    n = sub.add_parser("net", help="online tools: sim, matrix, desync, trace, relays, soak (docs/dev/online-dev.md)")
    ns = n.add_subparsers(dest="netcmd", required=True)
    t = ns.add_parser("sim", help="N local peers under simulated network conditions and scripted kills/freezes/rejoins")
    t.add_argument("scenario", nargs="?", default="moveview")
    t.add_argument("--players", type=int)
    t.add_argument("--fog", choices=["on", "off"], default="on")
    t.add_argument("--rounds", type=int, default=2)
    t.add_argument("--level", choices=list(net.LEVELS), help="named impairment: " + ", ".join(f"{k}={v}" for k, v in net.LEVELS.items()) + " (latency_ms,jitter_ms,loss_pct)")
    t.add_argument("--latency", type=int, help="one-way ms added to what every peer sends")
    t.add_argument("--jitter", type=int)
    t.add_argument("--loss", type=float, help="percent, in-match channel only")
    t.add_argument("--reorder", action="store_true", help="make jitter >= latency so the in-match channel reorders freely")
    t.add_argument("--impair", action="append", metavar="SEAT=LAT,JIT,LOSS", help="per-seat override")
    t.add_argument("--event", action="append", metavar="AT:ACTION:SEAT[:ARG]", help="30:stop:1:10 | t900:kill:2 | 45:relaunch:2 (AT seconds or tN ticks; kill stop cont relaunch)")
    t.add_argument("--relay", action="store_true", help="TANGOAW2_FORCE_RELAY=1 (needs --public)")
    t.add_argument("--public", action="store_true", help="use the real signalling server instead of the local mock")
    t.add_argument("--dump-frame", type=int, help="keep both consoles' RAM at this frame (TANGOAW2_DUMP_FRAME), for net desync")
    t.add_argument("--hz", type=int)
    t.add_argument("--max", type=int, dest="max_s")
    t.add_argument("--tag")
    t.set_defaults(fn=net.cmd_sim)
    t = ns.add_parser("matrix", help="scenario grid -> pass/fail table")
    t.add_argument("--scenario", default="moveview", help="2P cells; bigger rooms run the lobby flow")
    t.add_argument("--players", default="2,3")
    t.add_argument("--fog", default="on,off")
    t.add_argument("--route", default="direct", help="direct[,relay] (relay needs --public)")
    t.add_argument("--levels", default="none,mild")
    t.add_argument("--rounds", type=int, default=1)
    t.add_argument("--public", action="store_true")
    t.add_argument("--keep", action="store_true", help="keep PNGs of passing cells")
    t.add_argument("--hz", type=int)
    t.add_argument("--max", type=int, dest="max_s")
    t.set_defaults(fn=net.cmd_matrix)
    t = ns.add_parser("desync", help="explain a diverged run")
    t.add_argument("run", nargs="?", default="latest")
    t.add_argument("--seats")
    t.add_argument("--window", type=int, default=20, help="ticks around the divergence to show inputs for")
    t.set_defaults(fn=net.cmd_desync)
    t = ns.add_parser("trace", help="merged per-tick timeline of all peers")
    t.add_argument("run", nargs="?", default="latest")
    t.add_argument("--from-tick", type=int)
    t.add_argument("--to-tick", type=int)
    t.add_argument("--kinds", help="comma list of input,act,hash,state,log")
    t.add_argument("--keys", action="store_true", default=True)
    t.add_argument("--state", action="store_true", help="include 10 Hz state lines")
    t.add_argument("--head", type=int, default=80)
    t.set_defaults(fn=net.cmd_trace)
    t = ns.add_parser("relays", help="polite health report of the public endpoints")
    t.add_argument("--turn", action="store_true", help="read one signalling Hello to list the ICE/TURN hosts")
    t.add_argument("--all", action="store_true", help="probe every STUN/Nostr endpoint (default: the app's per-call caps)")
    t.add_argument("--force", action="store_true", help="ignore the fresh/backoff memory")
    t.set_defaults(fn=net.cmd_relays)
    t = ns.add_parser("soak", help="hours of random play; logs desyncs, stalls, crashes")
    t.add_argument("--hours", type=float, default=1.0)
    t.add_argument("--seed", type=int, default=int(__import__("time").time()))
    t.add_argument("--chaos", type=float, default=0.3, help="chance per run of a scripted freeze or kill+rejoin")
    t.add_argument("--pause", type=int, default=10)
    t.add_argument("--hz", type=int, default=1)
    t.add_argument("--max", type=int, dest="max_s", default=420)
    t.set_defaults(fn=net.cmd_soak)

    a = p.parse_args(argv)
    try:
        rc = a.fn(a)
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc or 0)


def _live(a):
    if a.list or not a.scenario:
        print("scenarios:", " ".join(live.all_names()), "rejoin ios-gate")
        return 0
    if a.scenario == "rejoin":
        from . import rejoin
        if not a.pad_or_sub:
            print("rejoin scenarios:", " ".join(rejoin.NAMES))
            return 0
        res = rejoin.run(a.pad_or_sub, a.players, a.local, a.hz, a.max_s, a.tag)
        return 0 if res.get("ok") else 1
    if a.scenario == "ios-gate":
        from . import ios
        return ios.cmd(a)
    po = {}
    for x in a.profile:
        k, v = x.split("=")
        po[int(k)] = v
    spec = live.make_spec(a.scenario, a.fog, a.players, a.rounds, a.tag, a.hz, a.max_s, a.kill, a.stop, a.after_kill, po, a.reveal, a.sim, None, a.entry, a.pad, a.picks)
    spec.local_signal = a.local
    res = live.run(spec)
    return 0 if res.get("ok") else 1


def _profiles(a):
    for k in range(a.n):
        d = profiles.ensure(profiles.NAMES[k], reset=a.reset)
        util.say("profile", d)
    return 0


def _runs(a):
    d = cfg.work("runs")
    if not d.is_dir():
        print("no runs yet")
        return 0
    import json
    for r in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime)[-a.n:]:
        try:
            s = json.loads((r / "summary.json").read_text())
            c = json.loads((r / "check.json").read_text()) if (r / "check.json").exists() else None
            print(f"{r.name:40} ok={s.get('ok')} {s.get('elapsed_s')}s build={s.get('build')} check={'PASS' if c and c['pass'] else ('FAIL' if c else '-')}")
        except Exception:
            print(r.name)
    return 0
