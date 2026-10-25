"""The live driver: real app clients on loopback (real matchmaking server), each driven by a pad script compiled from a scenario.

One engine for every live flow (the old drive.py, drive_unr.py and scen.py): it makes the run dir (pad scripts, poke rules, meta),
holds the live lock, copies the freshly built binary into a private test bundle, starts one client per seat with its own profile,
watches the clients' logs for SCRIPT END / "gave up", optionally kills or freezes a seat, and writes summary.json.

A run dir (devkit/work/runs/<tag>_<fog>_<HHMMSS>/) holds:
  meta.json          how it was started (args, build stamp, git sha)
  pad_s<k>.txt       the pad script of seat k;  poke.txt = TANGOAW2_TEST_POKE rules
  meta_s<k>.json     written by the app: build stamp, start_ms          state_s<k>.jsonl  10 Hz state, act events, hash lines
  shots_s<k>.jsonl   + s<k>_NNNN.png: file, ms, console tick (the sidecar)   tango_s<k>.log  the app log   summary.json
"""
import json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path
from . import cfg, profiles, scenarios, session, util

SIGKILL = signal.SIGKILL


# a relaunched seat (after a scripted kill): take the rejoin box (A) and carry on
REJOIN_PAD = ["until level=12 240", "wait 90", "press A 8", "wait 30", "session", "wait 600", "log SCRIPT END"]


def _last_tick(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 4096))
            for l in reversed(f.read().decode(errors="ignore").splitlines()):
                if l.startswith("{") and '"tick"' in l:
                    return json.loads(l).get("tick", 0)
    except Exception:
        pass
    return 0


class Spec:
    def __init__(self, name, n, fog, pads, pokes=None, kind="scen", tag=None, hz=None, max_s=None, kill=None, stop=None, after_kill=90,
                 kill_delay=2, profile_override=None, extra_env=None, events=None, impair=None, local_signal=False, seat_env=None):
        self.name, self.n, self.fog, self.pads, self.pokes = name, n, fog, pads, pokes or []
        self.kind, self.tag = kind, tag or name
        self.hz = hz or cfg.C["live"]["shot_hz"]
        self.max_s = int(max_s or cfg.C["live"]["max_seconds"])
        self.kill, self.stop, self.after_kill, self.kill_delay = kill, stop, after_kill, kill_delay
        self.profile_override = profile_override or {}
        self.extra_env = extra_env or {}
        self.events = events or []          # [{"at_s": 30} or {"at_tick": 900}, "action": kill|stop|cont|relaunch, "seat": k, "arg": seconds}]
        self.impair = impair or {}          # seat -> "latency_ms,jitter_ms,loss_pct" (TANGOAW2_NET_IMPAIR, applied to what that seat SENDS)
        self.local_signal = local_signal    # run a local signalling mock; no traffic to public services
        self.seat_env = seat_env or {}      # seat -> {env}
        self.boot_lobby = True


def _seat_pid(app_exe, profile_path, fallback):
    """The pid of the seat's game: the app re-executes itself under a crash supervisor, the game is the newest process of the profile."""
    mine = []
    for p in util.pids_for(app_exe):
        env = subprocess.run(["ps", "eww", "-p", str(p)], capture_output=True, text=True).stdout
        if f"TANGOAW2_PROFILE={profile_path} " in env or f"TANGOAW2_PROFILE={profile_path}\n" in env or env.rstrip().endswith(f"TANGOAW2_PROFILE={profile_path}"):
            mine.append(p)
    return mine[-1] if mine else fallback


def run(spec: Spec, quiet=False):
    heavy = spec.kind == "scen"
    with session.Session(spec.tag, spec.n, spec.fog, spec.hz, spec.local_signal, spec.profile_override, spec.extra_env, spec.impair, spec.seat_env, heavy,
                         spec.pokes, spec.kind, spec.name, spec.kill, spec.stop, no_code=(spec.kind in ("unranked", "solo")), boot_lobby=spec.boot_lobby) as ses:
        all_pads = spec.pads(ses.dir) if callable(spec.pads) else spec.pads
        ses.launch_all(all_pads)

        def launch(k, pad_file, suffix=""):
            return ses.launch(k, Path(pad_file).read_text().splitlines(), suffix)
        res = _watch(spec, ses.dir, ses.names, ses.logs, ses.procs, ses.app_exe, ses.t0, launch, ses)
    return ses.finish(res, quiet)


def _watch(spec, run_dir, names, logs, procs, app_exe, t0, launch=None, ses=None):
    n = spec.n
    ended, gave = set(), {}
    deadline = time.time() + spec.max_s
    killed, killed_set, res_kill = False, set(), 0.0
    stopped_pid = t_stop = None
    stop_done = False
    prof = lambda k: str(profiles.profile_dir(names[k]))
    pending = [dict(e, _done=False) for e in spec.events]
    cont_at = []     # (time, pid) SIGCONTs owed to timed stops
    fired = []
    while time.time() < deadline:
        time.sleep(1)
        now = time.time() - t0
        tick = _last_tick(run_dir / "state_s0.jsonl") if any("at_tick" in e for e in pending) else 0
        for e in pending:
            if "at_log" in e and not e["_done"] and not e.get("_seen") and any(e["at_log"] in ses.log_text(k) for k in range(n)):
                # (a marker the pad scripts log: `log AFTER_TURN_<r>` after turn r of the global turn list; `@MARK+15`: 15 s after it)
                e["at_s"] = now + e.get("delay", 0.0)
                e["_seen"] = True
            if e["_done"] or not (("at_s" in e and now >= e["at_s"]) or ("at_tick" in e and tick >= e["at_tick"])):
                continue
            e["_done"] = True
            k, act = int(e["seat"]), e["action"]
            pid = _seat_pid(app_exe, prof(k), procs[k].pid)
            if act == "kill":
                util.kill_pids([pid])
                killed = True
                killed_set.add(k)
                res_kill = now
            elif act == "stop":
                os.kill(pid, signal.SIGSTOP)
                cont_at.append((time.time() + float(e.get("arg") or 10), pid))
            elif act == "cont":
                os.kill(pid, signal.SIGCONT)
            elif act == "relaunch" and launch:
                pf = run_dir / f"pad_s{k}_b.txt"
                pad = REJOIN_PAD if spec.kind != "lobby" else REJOIN_PAD[:-2] + ["wait 200", "press B 8", "wait 30"] + scenarios.resume_turns(f"r{k}", 2)
                pf.write_text("\n".join(pad) + "\n")
                shutil.copy2(logs[k], run_dir / f"tango_s{k}_before.log")
                procs[k] = launch(k, pf, "_b")
                killed_set.discard(k)
            fired.append({"action": act, "seat": k, "at_s": round(now, 1), "tick": tick, "arg": e.get("arg")})
            util.say(f"event {act} seat {k} at {now:.1f}s tick {tick}")
        for t, pid in list(cont_at):
            if time.time() >= t:
                try:
                    os.kill(pid, signal.SIGCONT)
                except Exception:
                    pass
                cont_at.remove((t, pid))
        if pending and all(e["_done"] for e in pending) and not cont_at and not killed:
            killed = True            # the scripted story is told: wind up like a kill run
            res_kill = now
        if spec.stop and not stop_done:
            ss, sw, sd = spec.stop.split(":")
            ss = int(ss)
            if stopped_pid is None and time.time() - t0 > float(sw):
                stopped_pid = _seat_pid(app_exe, prof(ss), procs[ss].pid)
                t_stop = time.time()
                os.kill(stopped_pid, signal.SIGSTOP)
                util.say("SIGSTOP seat", ss, "pid", stopped_pid, "at", round(t_stop - t0, 1))
            elif stopped_pid is not None and time.time() - t_stop >= float(sd):
                os.kill(stopped_pid, signal.SIGCONT)
                stop_done = killed = True
                res_kill = time.time() - t0
                util.say("SIGCONT seat", ss, "at", round(res_kill, 1))
        if spec.kill and not killed:
            ks_s, kw = spec.kill.split(":", 1)
            seats_k = [int(x) for x in ks_s.split("+")]
            ks = seats_k[0]
            hit = False
            if kw == "eliminated":
                hit = any(l.get("what") == "eliminated" and l.get("actor") == ks + 1 for l in util.jsonl(run_dir / "state_s0.jsonl"))
            elif kw.startswith("log:"):
                try:
                    hit = kw[4:] in open(logs[0], errors="ignore").read()
                except Exception:
                    pass
            elif kw.startswith("army"):
                a = int(kw[4:])
                hit = any(l.get("k") == "state" and l.get("army") == a and "mover" in l for l in util.jsonl(run_dir / "state_s0.jsonl"))
            else:
                hit = time.time() - t0 > float(kw)
            if hit:
                time.sleep(spec.kill_delay)
                for kk in seats_k:
                    pid = _seat_pid(app_exe, prof(kk), procs[kk].pid)
                    util.say("killing pid", pid, "seat", kk)
                    util.kill_pids([pid])
                killed = True
                res_kill = time.time() - t0
                killed_set = set(seats_k)
                util.say("killed seat", ks, "at", round(res_kill, 1))
        for k in range(n):
            try:
                txt = open(logs[k], errors="ignore").read()
            except Exception:
                continue
            if "SCRIPT END" in txt:
                ended.add(k)
            m = re.findall(r"pad script: gave up[^\n]*", txt)
            if m and k not in gave:
                gave[k] = m[0]
        if killed and time.time() - t0 > res_kill + spec.after_kill:
            break
        if killed and killed_set and (set(range(n)) - killed_set) <= ended:
            break
        if killed and not killed_set and len(ended) == n:
            break
        if not killed and (len(ended) == n or (gave and not spec.stop)):
            break
    ok = (not gave) and ((set(range(n)) - killed_set) <= ended)
    for p in cont_at:
        try:
            os.kill(p[1], signal.SIGCONT)
        except Exception:
            pass
    return {"events": fired, "elapsed_s": round(time.time() - t0, 1), "ended": sorted(ended), "gave_up": gave, "killed": sorted(killed_set), "ok": ok}


# ---- building specs from CLI names ----
FLOWS = ["lobby", "unranked", "browse", "rules-lobby", "rules-unranked", "solo"]


def all_names():
    return sorted(scenarios.SCEN) + FLOWS


def make_spec(name, fog="on", players=None, rounds=2, tag=None, hz=None, max_s=None, kill=None, stop=None, after_kill=None, profile_override=None,
              reveal=False, sim=False, kill_delay=None, solo_entry="selectmap", solo_pad="", picks=None):
    """name: a scenario of scenarios.SCEN, or a flow: `lobby` (N seats, ROUNDS of end-turn) or `unranked` (matchmaking pair)."""
    kill = kill or os.environ.get("KILL")
    stop = stop or os.environ.get("STOP")
    _ak = after_kill if after_kill is not None else int(os.environ.get("AFTER_KILL", 90))   # (a story with a rejoin needs minutes: AFTER_KILL=300)
    if name in scenarios.SCEN:
        n = players or scenarios.seats_of(name)
        if n != scenarios.seats_of(name):
            util.say(f"warning: scenario {name} is written for {scenarios.seats_of(name)} seats; running with {n}")
        pk = scenarios.parse_picks(picks)
        sp0 = scenarios.Pads(name, fog, "RUN", bool(kill or stop), pk)
        spec = Spec(name, n, fog, lambda rd: scenarios.Pads(name, fog, rd, bool(kill or stop), pk).pads(), sp0.pokes, "scen", tag, hz, max_s, kill, stop,
                    after_kill if after_kill is not None else int(os.environ.get("AFTER_KILL", 90)), kill_delay if kill_delay is not None else 2, profile_override)
        return spec
    if name == "lobby":
        n = players or 3
        return Spec("lobby", n, fog, lambda rd: scenarios.lobby_pads(n, rounds, rd, fog, sim, reveal=reveal, picks=scenarios.parse_picks(picks)), [], "lobby", tag or f"lobby{n}p", hz or 1, max_s,
                    kill, stop, _ak, 2, profile_override)
    if name == "unranked":
        n = players or 2
        return Spec("unranked", n, fog, scenarios.unranked_pads(n), [], "unranked", tag or "unranked", hz or 1, max_s, kill, stop, _ak, 2, profile_override)
    if name == "rules-lobby":
        n = players or 2
        return Spec(name, n, fog, lambda rd: scenarios.rules_lobby_pads(n, rd), [], "lobby", tag or f"rules_lobby{n}p", hz or 1, max_s, kill, stop, _ak, 2, profile_override)
    if name == "rules-unranked":
        n = players or 2
        return Spec(name, n, fog, lambda rd: scenarios.rules_unranked_pads(n, rd), [], "unranked", tag or "rules_unranked", hz or 1, max_s, kill, stop, _ak, 2, profile_override)
    if name == "browse":
        return Spec(name, 2, fog, lambda rd: scenarios.browse_pads(rd), [], "lobby", tag or "browse", hz or 1, max_s or 300, kill, stop, _ak, 2, profile_override)
    if name == "solo":
        spec = Spec(name, 1, fog, lambda rd: scenarios.solo_pads(solo_entry, solo_pad, rd), [], "solo", tag or "solo", hz or 1, max_s or 200, kill, stop, 90, 2, profile_override)
        spec.boot_lobby = solo_entry == "lobby"
        return spec
    util.die(f"unknown scenario {name}; choose from: {' '.join(all_names())}")
