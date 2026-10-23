"""The real app on a harness checkpoint, through the AI debug channel (docs/dev/army-packs.md): `checkpoint` plays a scenario's script in the harness and
saves the console's state at its end; `look` starts the app offline from it (with the Dual Strike pack and its graphics, and the tilted map on request) and
takes the app's own picture. How the Dual Strike tilt (a host-side overlay the harness never draws) is seen."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
from .. import cfg, harness, profiles, util
from . import scenarios

CKPT = lambda: cfg.work("armyskin", "checkpoints")


def checkpoint(name, scenario, ids=None, ds=False):
    """Play `scenario` (identities `ids`) in the harness and keep its end state as checkpoint `name`. With `ds` the pack and its graphics are on."""
    out = cfg.work("armyskin", f"ckpt_{name}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.txt").write_text(scenarios.script(scenario, ids, checkpoint=name))
    CKPT().mkdir(parents=True, exist_ok=True)
    env = {"AW2_CKPT_DIR": str(CKPT())}
    if ds:
        env["TANGOAW2_DS_GRAPHICS"] = "1"
    return harness.run_script(out / "script.txt", out, ds=ds, env_extra=env)


def look(name, shot, ds=False, tilt=False, scale=None, wait=60.0):
    """Boot the app from checkpoint `name`, wait for the battle map, save its picture to `shot` and return the armies (the AI debug state)."""
    util.check_fresh(cfg.REPO / "target" / "release" / "tango", "tango")
    ck = CKPT()
    if not (ck / f"{name}.state").exists():
        util.die(f"no checkpoint {name}: `aw2dev armyskin checkpoint {name}` first")
    ds = ds or tilt
    prof = "skinds" if ds else "skin"
    profiles.ensure(prof, pack=ds)
    if ds:
        cj = profiles.profile_dir(prof) / "config" / "config.json"
        conf = json.loads(cj.read_text())
        conf.update({"ds_graphics": True, "ds_tilt": bool(tilt)})
        cj.write_text(json.dumps(conf, indent=2))
    data = profiles.profile_dir(prof) / "data" / "checkpoints"
    data.mkdir(parents=True, exist_ok=True)
    for ext in ("state", "json"):
        shutil.copy2(ck / f"{name}.{ext}", data / f"{name}.{ext}")
    app = profiles.test_app(cfg.REPO / "target" / "release" / "tango")
    env = dict(os.environ, TANGOAW2_PROFILE=str(profiles.profile_dir(prof)), TANGOAW2_AI_DEBUG="0", TANGOAW2_BOOT_CHECKPOINT=name, AW2DEV_LOOK="1")
    if tilt:
        # (the picture of a checkpoint boot: the ground is not the live palette's, so the tilt's ground check would leave it flat; the scale 1
        # keeps the screenshot the size of the console's)
        env["TANGOAW2_TILT"] = "1"
        env["TANGOAW2_TILT_NO_GROUNDCHECK"] = "1"
        env["TANGOAW2_TILT_SCALE"] = str(scale or 1)
    if ds:
        env["TANGOAW2_DS_GRAPHICS"] = "1"
    proc = subprocess.Popen([str(app)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cfg.REPO)
    try:
        addr, t0, line = None, time.time(), ""
        while time.time() - t0 < 60 and addr is None:
            line = proc.stdout.readline()
            if not line:
                break
            if "AI_DEBUG_LISTENING" in line:
                addr = line.split()[-1]
        if not addr:
            util.die("the app did not open the AI debug channel (" + (line or "no output").strip()[:200] + ")")
        sys.path.insert(0, str(cfg.REPO / "tools" / "aidebug"))
        from client import AiDebug
        d = AiDebug.connect(addr)
        d.wait_until({"phase": "battle"}, wait)
        time.sleep(1.5)
        st = d.state(["armies", "map", "day", "active_army"])
        Path(shot).parent.mkdir(parents=True, exist_ok=True)
        d.screenshot(str(shot))
        return st["armies"]
    finally:
        proc.kill()
        proc.wait()
        subprocess.run(["pkill", "-9", "-f", str(app)])   # (the test app starts its own child)
        time.sleep(1.0)
