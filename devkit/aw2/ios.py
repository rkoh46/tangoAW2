"""The iOS gate: iPhone / iPad Simulator peers against Mac peers in one room (port of the old ios_gate.py).

  aw2dev build --sim                                   # dist/tangoAW2-sim.app (needs Xcode)
  aw2dev live ios-gate --kinds mac,iphone --rounds 2   # seat 0 = Mac host, seat 1 = an iPhone Simulator guest
  kinds: mac | iphone | iphone2 (a second, different iPhone) | ipad ; at most one seat per Simulator device
  --event AT:ACTION:SEAT[:ARG]   actions: kill (Mac: kill -9; Simulator: simctl terminate), relaunch (rejoin box A), bg (send the app to the background for ARG s,
                                 launching Settings over it, then back: iOS suspends a backgrounded game), stop (Mac only: SIGSTOP for ARG s)

The Simulator shares the Mac's loopback: the local signalling mock (default here) works for both. Simulators are booted if needed and LEFT as they were
(only this app is terminated); the player's own Simulators and apps are not touched. Screenshots through `simctl io` land in the run dir (final_s<k>.png).
Needs DEVELOPER_DIR for Xcode (set from config paths.developer_dir).
"""
import json, os, plistlib, re, shutil, subprocess, time
from pathlib import Path
from . import cfg, profiles, scenarios, session, util

SIM_APP = lambda: cfg.REPO / "dist" / "tangoAW2-sim.app"


def xc_env():
    e = dict(os.environ)
    e["DEVELOPER_DIR"] = str(cfg.path("paths", "developer_dir"))
    return e


def simctl(*a, check=False):
    return subprocess.run(["xcrun", "simctl", *a], env=xc_env(), capture_output=True, text=True)


def devices():
    out = json.loads(simctl("list", "devices", "available", "-j").stdout or "{}")
    ds = []
    for rt, lst in out.get("devices", {}).items():
        if "iOS" in rt:
            ds += [d for d in lst if d.get("isAvailable", True)]
    return ds


def pick_devices(kinds):
    ds = devices()
    used, out = set(), {}
    want = os.environ.get
    for k, kind in enumerate(kinds):
        if kind == "mac":
            continue
        pref = "iPad" if kind == "ipad" else "iPhone"
        env = want(f"AW2DEV_IOS_{kind.upper()}")
        cands = [d for d in ds if d["name"].startswith(pref) and d["udid"] not in used]
        if env:
            cands = [d for d in ds if env in (d["udid"], d["name"])]
        cands.sort(key=lambda d: d["state"] != "Booted")     # a booted one first: no boot wait
        if not cands:
            util.die(f"no available {pref} Simulator for seat {k} (xcrun simctl list devices)")
        used.add(cands[0]["udid"])
        out[k] = cands[0]
    return out


class IosSession(session.Session):
    def __init__(self, kinds, *a, **kw):
        super().__init__(*a, **kw)
        self.kinds = kinds
        self.devs = pick_devices(kinds)
        self.docs = {}
        self.bid = None

    def __enter__(self):
        app = SIM_APP()
        if not app.is_dir():
            util.die(f"{app} missing: run `aw2dev build --sim`")
        self.bid = plistlib.loads((app / "Info.plist").read_bytes())["CFBundleIdentifier"]
        super().__enter__()
        for k, d in self.devs.items():
            u = d["udid"]
            if d["state"] != "Booted":
                util.say("booting", d["name"])
                simctl("boot", u)
                simctl("bootstatus", u, "-b")
            simctl("terminate", u, self.bid)
            simctl("install", u, str(app))
            doc = simctl("get_app_container", u, self.bid, "data").stdout.strip()
            shutil.rmtree(doc + "/Documents/logs", ignore_errors=True)
            prof = doc + "/Documents/prof"
            shutil.rmtree(prof, ignore_errors=True)
            src = profiles.profile_dir(self.names[k])
            shutil.copytree(src, prof, ignore=shutil.ignore_patterns("logs", "replays", "suspended", "cache"))
            cj = Path(prof) / "config" / "config.json"
            c = json.loads(cj.read_text())
            c["data_path"] = prof + "/data"
            c["matchmaking_endpoint"] = self.endpoint
            cj.write_text(json.dumps(c, indent=2))
            os.makedirs(prof + "/data/logs", exist_ok=True)
            self.docs[k] = doc
            self.logs[k] = Path(doc + "/Documents/logs")
        return self

    @property
    def endpoint(self):
        return f"ws://127.0.0.1:{self.mock.port}" if self.mock else "wss://matchmaking.tango.n1gp.net"

    def _newest_log(self, k):
        d = self.logs[k]
        if d.is_dir():
            fs = sorted(d.glob("tangoaw2-*.log"), key=lambda p: p.stat().st_mtime) or sorted(d.glob("*.log"), key=lambda p: p.stat().st_mtime)
            return fs[-1] if fs else None
        return d if d.exists() else None

    def log_text(self, k):
        if self.kinds[k] == "mac":
            return super().log_text(k)
        p = self._newest_log(k)
        try:
            return open(p, errors="ignore").read() if p else ""
        except Exception:
            return ""

    def launch(self, k, pad, suffix="", first=True):
        if self.kinds[k] == "mac":
            return super().launch(k, pad, suffix, first)
        pf = self.dir / f"pad_s{k}{suffix}.txt"
        pf.write_text("\n".join(pad) + "\n")
        shutil.copy2(pf, self.docs[k] + f"/Documents/pad{suffix}.txt")
        env = {"TANGOAW2_PROFILE": self.docs[k] + "/Documents/prof", "TANGOAW2_AUTOSTART": "offline", "TANGOAW2_BOOT_LOBBY": "1",
               "TANGOAW2_PAD_SCRIPT": self.docs[k] + f"/Documents/pad{suffix}.txt", "TANGOAW2_ONLINE_LOG": "1", "TANGOAW2_INPUT_LOG": "1", "RUST_LOG": "info",
               "TANGOAW2_RUN_DIR": str(self.dir), "TANGOAW2_RUN_SEAT": str(k), "TANGOAW2_RUN_SHOT_HZ": "1", "TANGOAW2_HASH_PARTS": "1", "TANGOAW2_BUILD": self.stamp}
        if not suffix:
            env["TANGOAW2_ONLINE_CODE" if k == 0 else "TANGOAW2_TYPE_CODE"] = cfg.C["live"]["room_code"]
        env.update(self.net_env)
        e2 = xc_env()
        for a, b in env.items():
            e2["SIMCTL_CHILD_" + a] = b
        subprocess.run(["xcrun", "simctl", "launch", "--terminate-running-process", self.devs[k]["udid"], self.bid], env=e2,
                       stdout=open(self.dir / f"stdout_s{k}{suffix}.log", "w"), stderr=subprocess.STDOUT)
        return None

    def kill(self, k):
        if self.kinds[k] == "mac":
            return super().kill(k)
        simctl("terminate", self.devs[k]["udid"], self.bid)

    def screenshot(self, k, name):
        simctl("io", self.devs[k]["udid"], "screenshot", str(self.dir / name))

    def background(self, k):
        simctl("launch", self.devs[k]["udid"], "com.apple.Preferences")

    def foreground(self, k):
        simctl("launch", self.devs[k]["udid"], self.bid)

    def copy_logs(self):
        for k in range(self.n):
            try:
                if self.kinds[k] == "mac":
                    shutil.copy2(self.logs[k], self.dir / f"tango_s{k}.log")
                else:
                    p = self._newest_log(k)
                    if p:
                        shutil.copy2(p, self.dir / f"tango_s{k}.log")
            except Exception:
                pass

    def __exit__(self, *a):
        for k in self.devs:
            self.screenshot(k, f"final_s{k}.png")
            simctl("terminate", self.devs[k]["udid"], self.bid)
        super().__exit__(*a)


def cmd(a):
    kinds = [x for x in (a.kinds or "mac,iphone").split(",") if x]
    n = len(kinds)
    events = []
    for e in a.event or []:
        p = e.split(":")
        events.append({"at": float(p[0]), "action": p[1], "seat": int(p[2]), "arg": float(p[3]) if len(p) > 3 else None, "done": False})
    pads = scenarios.lobby_pads(n, a.rounds, "RUN", a.fog, picks=scenarios.parse_picks(a.picks))
    hz = a.hz or 1
    max_s = int(a.max_s or os.environ.get("DRIVE_MAX", "420"))
    with IosSession(kinds, a.tag or "ios_" + "_".join(kinds), n, a.fog, hz, local_signal=not getattr(a, "public", False) and True, flow="lobby", scenario="ios-gate") as ses:
        rd = str(ses.dir)
        ses.launch_all({k: [l.replace("RUN", rd) for l in pads[k]] for k in range(n)})
        ended, gave, res = set(), {}, {"kinds": kinds}
        bg_until = {}
        deadline = time.time() + max_s
        while time.time() < deadline:
            time.sleep(1)
            el = ses.elapsed()
            for e in events:
                if e["done"] or el < e["at"]:
                    continue
                e["done"], k = True, e["seat"]
                util.say(f"event {e['action']} seat {k} at {el:.0f}s")
                if e["action"] == "kill":
                    ses.kill(k)
                elif e["action"] == "relaunch":
                    ses.launch(k, ["until level=12 240", "wait 90", "press A 8", "wait 30", "session", "wait 600", "log SCRIPT END"], "_b")
                elif e["action"] == "bg" and kinds[k] != "mac":
                    ses.background(k)
                    bg_until[k] = time.time() + (e["arg"] or 10)
                elif e["action"] == "stop" and kinds[k] == "mac":
                    ses.stop(k)
                    bg_until[("mac", k)] = time.time() + (e["arg"] or 5)
            for key, t in list(bg_until.items()):
                if time.time() >= t:
                    if isinstance(key, tuple):
                        ses.cont(key[1])
                    else:
                        ses.foreground(key)
                    bg_until.pop(key)
            for k in range(n):
                txt = ses.log_text(k)
                if "SCRIPT END" in txt:
                    ended.add(k)
                m = re.findall(r"pad script: gave up[^\n]*", txt)
                if m and k not in gave:
                    gave[k] = m[0]
            if len(ended) == n or (gave and not events):
                break
        res.update({"elapsed_s": round(ses.elapsed(), 1), "ended": sorted(ended), "gave_up": gave, "ok": len(ended) == n and not gave})
    ses.copy_logs()
    from .runlib import Run
    from . import check
    try:
        h = check.c_hash(Run(ses.dir))
        res["hash"] = {k: h.get(k) for k in ("pass", "equal", "common_frames")}
        res["ok"] = res["ok"] and bool(h.get("pass"))
    except Exception as e:
        res["hash"] = repr(e)
    return 0 if ses.finish(res).get("ok") else 1
