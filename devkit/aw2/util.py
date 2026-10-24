"""Small shared helpers: process running, the live lock, binary freshness, build stamps, disk."""
import json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
from . import cfg


def say(*a):
    print("aw2dev:", *a, flush=True)


def die(msg, code=1):
    print("aw2dev: error:", msg, file=sys.stderr, flush=True)
    sys.exit(code)


def run(cmd, check=True, **kw):
    """Run a command, streaming output. cmd is a list or a shell string."""
    say("$", cmd if isinstance(cmd, str) else " ".join(map(str, cmd)))
    r = subprocess.run(cmd, shell=isinstance(cmd, str), **kw)
    if check and r.returncode:
        die(f"command failed ({r.returncode})", r.returncode)
    return r


def human(n):
    for u in ("B", "K", "M", "G", "T"):
        if n < 1024 or u == "T":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024


def du(p):
    r = subprocess.run(["du", "-sk", str(p)], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0]) * 1024
    except Exception:
        return 0


def df():
    r = subprocess.run(["df", "-h", os.path.expanduser("~")], capture_output=True, text=True)
    return r.stdout.strip()


# ---- the binaries ----
def release_bin(profile="release"):
    return cfg.REPO / "target" / profile / "tango"


def example_bin(name):
    return cfg.REPO / "target" / "release" / "examples" / name


def newest_source_mtime():
    """mtime of the newest source file (rs, toml, m4t song files: tracked or new; not Cargo.lock, which any cargo command touches), to catch stale binaries."""
    files = [f for f in cfg.git("ls-files", "*.rs", "*.toml", "*.m4t").splitlines() + cfg.git("ls-files", "--others", "--exclude-standard", "*.rs", "*.toml", "*.m4t").splitlines()
             if not f.startswith(("devkit/", ".claude/", "docs/"))]
    m = 0.0
    for f in files:
        try:
            m = max(m, (cfg.REPO / f).stat().st_mtime)
        except OSError:
            pass
    return m


def check_fresh(binary, what="binary", fatal=True):
    """A binary older than the newest source is a stale build (a whole regression once ran on one)."""
    b = Path(binary)
    if not b.exists():
        die(f"{what} {b} missing: run `aw2dev build`" + (" (examples: `aw2dev build --examples`)" if "examples" in str(b) else ""))
    if b.stat().st_mtime + 1 < newest_source_mtime():
        msg = f"{what} {b} is older than the sources: run `aw2dev build` first"
        if fatal and not os.environ.get("AW2DEV_ALLOW_STALE"):
            die(msg + " (AW2DEV_ALLOW_STALE=1 to run anyway)")
        say("WARNING:", msg)


def build_stamp(binary):
    """git short sha (+dirty) and a binary hash prefix: identical across all seats of a run, logged by the app (TANGOAW2_BUILD)."""
    import hashlib
    sha = cfg.git("rev-parse", "--short=9", "HEAD")
    dirty = "+dirty" if cfg.git("status", "--porcelain", "--untracked-files=no") else ""
    h = hashlib.sha1(Path(binary).read_bytes()).hexdigest()[:8]
    return f"{sha}{dirty}-{h}"


# ---- the live lock: one live run at a time on this Mac (clients open windows; two runs at once distort each other) ----
class LiveLock:
    def __init__(self, wait=1800):
        self.dir = cfg.path("paths", "lock_dir") / "live.lock"
        self.wait = wait
        self.held = False

    def _owner(self):
        try:
            return int((self.dir / "pid").read_text())
        except Exception:
            return None

    def acquire(self):
        self.dir.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        told = False
        while True:
            try:
                self.dir.mkdir()
                (self.dir / "pid").write_text(str(os.getpid()))
                (self.dir / "since").write_text(time.strftime("%F %T"))
                (self.dir / "repo").write_text(str(cfg.REPO))
                self.held = True
                return time.time() - t0
            except FileExistsError:
                o = self._owner()
                alive = False
                if o:
                    try:
                        os.kill(o, 0)
                        alive = True
                    except ProcessLookupError:
                        alive = False
                    except PermissionError:
                        alive = True
                if not alive:
                    shutil.rmtree(self.dir, ignore_errors=True)
                    continue
                if not told:
                    say(f"live lock held by pid {o} ({(self.dir / 'repo').read_text() if (self.dir / 'repo').exists() else '?'}); waiting")
                    told = True
                if time.time() - t0 > self.wait:
                    die("live lock wait timed out")
                time.sleep(3)

    def release(self):
        if self.held:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.held = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *a):
        self.release()


def pids_for(path_fragment):
    out = subprocess.run(["pgrep", "-f", path_fragment], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out if int(x) != os.getpid()]


def kill_pids(pids, sig=signal.SIGKILL):
    for p in pids:
        try:
            os.kill(p, sig)
        except Exception:
            pass


def jsonl(path):
    out = []
    try:
        for l in open(path, errors="ignore"):
            l = l.strip()
            if l.startswith("{"):
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out
