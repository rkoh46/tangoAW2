"""`aw2dev co verify sonja`: Sonja must be exactly as she was in a reference build (v0.8.7). `tools/aw2test/tests/test_sonja_untouched.py` writes everything of hers the console shows or computes (her CO row,
presentation pictures, HUD face, texts, battle numbers in her three levels as attacker and defender, fog vision, her place in the Teams list, her Tag page and Tag Power numbers, the frames of her screens) to
`sonja.json`; this runs it once on the reference build's example binaries (`AW2TEST_RUNNER_DIR`) and once on this tree's, and prints every difference (exit 1 on any). The reference is built, once, from the
tag in a worktree of its own under `devkit/work/baseline` (`--build-baseline`); nothing of it is committed."""
import json, os, subprocess, sys
from .. import cfg, util

BASE = cfg.work("baseline")
REF_TAG = "v0.8.7"


def baseline_examples():
    return BASE / "target" / "release" / "examples"


def build_baseline():
    src = BASE / "src"
    BASE.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        util.run(["git", "worktree", "add", "--detach", str(src), REF_TAG], cwd=cfg.REPO)
    env = cfg.env_with_cargo({"CARGO_TARGET_DIR": str(BASE / "target")})
    util.run(["cargo", "build", "--release", "-p", "tango-gamesupport-aw2", "--examples"], env=env, cwd=src)


def run_once(label, examples_dir):
    env = dict(os.environ)
    if examples_dir:
        env["AW2TEST_RUNNER_DIR"] = str(examples_dir)
    r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "--mode", "ds", "-k", "sonja_untouched"], cwd=cfg.REPO, env=env, capture_output=True, text=True)
    path = cfg.REPO / "tools" / "aw2test" / "out" / "ds" / "sonja_untouched" / "sonja.json"
    if not path.exists():
        util.die(f"{label}: the observation test did not run:\n{r.stdout[-1500:]}")
    data = json.loads(path.read_text())
    if os.environ.get("AW2TEST_KEEP_FRAMES"):
        import shutil
        keep = BASE / f"frames_{label}"
        shutil.rmtree(keep, ignore_errors=True)
        keep.mkdir(parents=True)
        for f in path.parent.glob("s_*.bmp"):
            shutil.copy(f, keep / f.name)
    dst = BASE / f"sonja_{label}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, indent=1, sort_keys=True))
    return data


def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'reference' if k in a else 'this build'}")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
    elif a != b:
        out.append(f"{path}: reference {str(a)[:80]} != this build {str(b)[:80]}")
    return out


def verify_sonja(a):
    if a.build_baseline or not baseline_examples().exists():
        if not a.build_baseline:
            util.die(f"no reference build at {baseline_examples()}: run with --build-baseline (builds {REF_TAG} once)")
        build_baseline()
    ref = run_once("reference", baseline_examples())
    now = run_once("current", None)
    d = diff(ref, now)
    groups = sorted(ref)
    for g in groups:
        bad = [x for x in d if x.startswith(f"/{g}")]
        print(f"{'FAIL' if bad else 'ok  '} {g}" + (f": {len(bad)} difference(s)" if bad else ""))
    for x in d[:40]:
        print("  ", x)
    print("co verify sonja:", "FAIL: Sonja differs from " + REF_TAG if d else f"ok: Sonja is exactly as in {REF_TAG} ({len(groups)} groups compared)")
    return 1 if d else 0
