"""A live session: a run dir, the live lock, the test app, per-seat profiles, an optional local signalling mock, and helpers to launch,
find, freeze and kill each seat's client. live.run (scenarios) and the driver state machines (rejoin.py, ios.py, drivers.py) are built on it."""
import json, os, shutil, signal, subprocess, time
from . import cfg, profiles, util


class Session:
    def __init__(self, tag, n, fog="on", hz=2, local_signal=False, profile_override=None, extra_env=None, impair=None, seat_env=None,
                 heavy=False, pokes=None, flow="scen", scenario=None, kill=None, stop=None, no_code=False, binary=None, boot_lobby=True):
        self.tag, self.n, self.fog, self.hz = tag, n, fog, hz
        self.local_signal, self.extra_env, self.impair, self.seat_env = local_signal, extra_env or {}, impair or {}, seat_env or {}
        self.heavy, self.pokes, self.flow, self.scenario, self.no_code = heavy, pokes or [], flow, scenario or tag, no_code
        self.boot_lobby = boot_lobby
        self.binary = binary or util.release_bin("release")
        self.names = [(profile_override or {}).get(k, profiles.NAMES[k]) for k in range(n)]
        self.lock = util.LiveLock()
        self.mock = None
        self.procs, self.env = {}, {}
        self.lock_wait = 0.0
        self.t0 = None
        self.meta_extra = {"kill": kill, "stop": stop}

    # ---- life cycle ----
    def __enter__(self):
        util.check_fresh(self.binary, "tango")
        self.stamp = util.build_stamp(self.binary)
        self.dir = cfg.work("runs", f"{self.tag}_{self.fog}_{time.strftime('%H%M%S')}")
        self.dir.mkdir(parents=True, exist_ok=False)
        for nm in self.names:
            profiles.ensure(nm, pack=not nm.endswith("np"))
        (self.dir / "poke.txt").write_text("\n".join(self.pokes) + "\n")
        (self.dir / "meta.json").write_text(json.dumps({
            "kind": "live", "scenario": self.scenario, "flow": self.flow, "n": self.n, "fog": self.fog, "build": self.stamp, "git": cfg.git("rev-parse", "HEAD"),
            "dirty": bool(cfg.git("status", "--porcelain", "--untracked-files=no")), "hz": self.hz, "profiles": self.names, "started": time.strftime("%F %T"),
            **self.meta_extra}, indent=1))
        t = time.time()
        self.lock.acquire()
        self.lock_wait = round(time.time() - t, 1)
        self.app_exe = str(profiles.test_app(self.binary))
        util.kill_pids(util.pids_for(self.app_exe))
        self.logs = {k: profiles.reset_live_state(self.names[k]) for k in range(self.n)}
        endpoint, self.net_env = "wss://matchmaking.tango.n1gp.net", {}
        if self.local_signal:
            from . import signal_mock, endpoints
            self.mock = signal_mock.Server(0)
            endpoint = self.mock.start_thread()
            self.net_env = endpoints.block_env()
            util.say("local signalling mock at", endpoint, "(public endpoints blocked for this run)")
        for nm in set(self.names):
            cj = profiles.profile_dir(nm) / "config" / "config.json"
            c = json.loads(cj.read_text())
            c["matchmaking_endpoint"] = endpoint
            cj.write_text(json.dumps(c, indent=2))
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.copy_logs()
        util.kill_pids(util.pids_for(self.app_exe))
        self.lock.release()

    def elapsed(self):
        return time.time() - self.t0

    # ---- seats ----
    def profile_path(self, k):
        return str(profiles.profile_dir(self.names[k]))

    def launch(self, k, pad, suffix="", first=True):
        """Start seat k's client with the pad script `pad` (a list of lines). suffix "_b" marks a relaunch (no room code is typed again)."""
        pf = self.dir / f"pad_s{k}{suffix}.txt"
        if self.names[k].endswith("np") and not suffix:
            pad = ["wait 900"] + list(pad)
        pf.write_text("\n".join(pad) + "\n")
        env = dict(os.environ)
        env.update({"TANGOAW2_PROFILE": self.profile_path(k), "TANGOAW2_AUTOSTART": "offline", "TANGOAW2_PAD_SCRIPT": str(pf),
                    "TANGOAW2_ONLINE_LOG": "1", "TANGOAW2_INPUT_LOG": "1", "RUST_LOG": "info", "TANGOAW2_RUN_DIR": str(self.dir), "TANGOAW2_RUN_SEAT": str(k),
                    "TANGOAW2_RUN_SHOT_HZ": str(self.hz), "TANGOAW2_BUILD": self.stamp, "TANGOAW2_HASH_PARTS": "1"})
        if self.heavy:
            env.update({"TANGOAW2_TEST_POKE": str(self.dir / "poke.txt"), "AW2_CAM_LOG": "1", "TANGOAW2_ROSTER_LOG": "1",
                        "TANGOAW2_DUMP_FRAME": os.environ.get("DUMPF", "7260"), "AW2_CONSOLE_PROCS": "1", "AW2_VIEW_DEBUG": "1"})
        if self.boot_lobby:
            env["TANGOAW2_BOOT_LOBBY"] = "1"
        env.update(self.net_env)
        env.update(self.extra_env)
        env.update(self.seat_env.get(k, {}))
        if k in self.impair:
            env["TANGOAW2_NET_IMPAIR"] = self.impair[k]
        if self.flow not in ("unranked",) and not self.no_code and not suffix:
            env["TANGOAW2_ONLINE_CODE" if k == 0 else "TANGOAW2_TYPE_CODE"] = cfg.C["live"]["room_code"]
        self.env[k] = env
        self.procs[k] = subprocess.Popen(["perl", "-e", "alarm 900; exec @ARGV", self.app_exe], env=env, stdout=open(self.dir / f"stdout_s{k}{suffix}.log", "w"), stderr=subprocess.STDOUT)
        return self.procs[k]

    def launch_all(self, pads, stagger=(3, 1)):
        for k in range(self.n):
            self.launch(k, pads[k])
            time.sleep(stagger[0] if k == 0 else stagger[1])

    def pid(self, k):
        """The game's pid for seat k (the app re-executes itself under a crash supervisor: the game is the newest process of the profile)."""
        prof = self.profile_path(k)
        mine = []
        for p in util.pids_for(self.app_exe):
            env = subprocess.run(["ps", "eww", "-p", str(p)], capture_output=True, text=True).stdout
            if f"TANGOAW2_PROFILE={prof} " in env or f"TANGOAW2_PROFILE={prof}\n" in env or env.rstrip().endswith(f"TANGOAW2_PROFILE={prof}"):
                mine.append(p)
        return mine[-1] if mine else (self.procs[k].pid if k in self.procs else None)

    def kill(self, k):
        pids = [p for p in util.pids_for(self.app_exe) if self._is_seat(p, k)] or [self.pid(k)]
        util.kill_pids([p for p in pids if p])

    def _is_seat(self, p, k):
        env = subprocess.run(["ps", "eww", "-p", str(p)], capture_output=True, text=True).stdout
        prof = self.profile_path(k)
        return f"TANGOAW2_PROFILE={prof} " in env or f"TANGOAW2_PROFILE={prof}\n" in env or env.rstrip().endswith(f"TANGOAW2_PROFILE={prof}")

    def stop(self, k):
        os.kill(self.pid(k), signal.SIGSTOP)

    def cont(self, k):
        os.kill(self.pid(k), signal.SIGCONT)

    def log_text(self, k):
        try:
            return open(self.logs[k], errors="ignore").read()
        except Exception:
            return ""

    def copy_logs(self):
        for k in range(self.n):
            try:
                shutil.copy2(self.logs[k], self.dir / f"tango_s{k}.log")
            except Exception:
                pass
            d = self.logs[k].parent
            for f in d.glob("tango.log.*"):
                try:
                    shutil.copy2(f, self.dir / f"tango_s{k}_{f.name.split('.')[-1]}.log")
                except Exception:
                    pass

    def finish(self, res, quiet=False):
        res.update({"t0_epoch_ms": int(self.t0 * 1000), "run": str(self.dir), "scenario": self.scenario, "fog": self.fog, "build": self.stamp, "lock_wait_s": self.lock_wait})
        if self.mock:
            res["signal_pairs"] = self.mock.pairs
        (self.dir / "summary.json").write_text(json.dumps(res, indent=1))
        if not quiet:
            print(json.dumps(res))
        return res
