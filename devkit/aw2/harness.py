"""The offline harness: aw2_room_teams runs N seats on one console, no network (tango-gamesupport-aw2/examples/aw2_room_teams.rs).

Scripts live in tango-gamesupport-aw2/examples/*.txt (first line `n N`); see docs/dev/pad-scripts.md for the command language.
Env switches the example reads (set by the flags below): AW2_SAMPLE, AW2_DUMP, AW2_CAM_LOG, AW2_LEAK_CHECK, AW2_HASH_LOG, TANGOAW2_DS_ROM.
"""
import os, re, subprocess, time
from pathlib import Path
from . import cfg, util

EXAMPLES = cfg.REPO / "tango-gamesupport-aw2" / "examples"


def resolve_script(s):
    p = Path(s)
    for c in (p, EXAMPLES / s, EXAMPLES / (s + ".txt"), EXAMPLES / ("aw2_" + s + ".txt")):
        if c.is_file():
            return c.resolve()
    util.die(f"script {s} not found (looked in {EXAMPLES})")


def list_scripts():
    return sorted(p.stem for p in EXAMPLES.glob("*.txt"))


def script_seats(path):
    for l in Path(path).read_text().splitlines():
        l = l.strip()
        if l and not l.startswith("#"):
            m = re.match(r"n\s+(\d+)", l)
            return int(m.group(1)) if m else None


def run_script(script, out_dir, seats=None, sample=None, dump=None, cam_log=False, leak=False, hash_log=None, ds=False, log=None, timeout=3600, env_extra=None):
    """Run one script; returns (returncode, log path). Output (BMP shots, black-run report) goes to out_dir."""
    binary = util.example_bin("aw2_room_teams")
    util.check_fresh(binary, "aw2_room_teams")
    script = resolve_script(script)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if seats is not None and script_seats(script) != seats:
        lines = script.read_text().splitlines()
        for i, l in enumerate(lines):
            if re.match(r"\s*n\s+\d+", l):
                lines[i] = f"n {seats}"
                break
        tmp = out_dir / f"{script.stem}_n{seats}.txt"
        tmp.write_text("\n".join(lines) + "\n")
        script = tmp
    env = dict(os.environ)
    if sample:
        env["AW2_SAMPLE"] = str(sample)
    if dump:
        env["AW2_DUMP"] = str(dump)
    if cam_log:
        env["AW2_CAM_LOG"] = "1"
    if leak:
        env["AW2_LEAK_CHECK"] = "1"
    if hash_log:
        env["AW2_HASH_LOG"] = str(hash_log)
    if ds:
        env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    env.update(env_extra or {})
    log = Path(log or out_dir / "harness.log")
    with open(log, "w") as f:
        r = subprocess.run([str(binary), str(cfg.aw2_rom()), str(out_dir), str(script)], env=env, stdout=f, stderr=subprocess.STDOUT, cwd=cfg.REPO, timeout=timeout)
    return r.returncode, log


def cmd(args):
    if args.list:
        print("\n".join(list_scripts()))
        return 0
    name = resolve_script(args.script)
    out = cfg.work("harness", f"{name.stem}_{time.strftime('%H%M%S')}")
    dump = out / "dump" if args.dump else None
    t0 = time.time()
    rc, log = run_script(name, out, args.seats, args.sample, dump, args.cam_log, args.leak, ds=args.ds)
    text = log.read_text(errors="ignore")
    tail = "\n".join(text.splitlines()[-12:])
    print(tail)
    (out / "meta.json").write_text(__import__("json").dumps({"kind": "harness", "script": str(name), "rc": rc, "seconds": round(time.time() - t0, 1),
                                                              "sample": args.sample, "dump": bool(dump), "cam_log": args.cam_log}))
    util.say(f"{'PASS' if rc == 0 else 'FAIL'} {name.stem} rc={rc} in {time.time() - t0:.0f}s; out: {out}")
    return 0 if rc == 0 else 1
