"""aw2dev audit text|maps: the examples aw2_online_text_audit and aw2_map_audit."""
import re, subprocess, time
from . import cfg, util


def text(args):
    binary = util.example_bin("aw2_online_text_audit")
    util.check_fresh(binary, "aw2_online_text_audit")
    out = cfg.work("audit", "text")
    out.mkdir(parents=True, exist_ok=True)
    env = cfg.env_with_cargo()
    if args.ds:
        env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    r = subprocess.run([str(binary), str(cfg.aw2_rom()), str(out)], env=env, capture_output=True, text=True, cwd=cfg.REPO)
    lines = (r.stdout + r.stderr).splitlines()
    problems = [l for l in lines if l.startswith("PROBLEM")]
    done = next((l for l in lines if l.startswith("done:")), None)
    for l in problems:
        print(l)
    util.say(f"{done or 'no summary line'}; pages rendered to {out} (BMPs; look at them before calling a screen done)")
    return 0 if (r.returncode == 0 and done == "done: 0 problems") else 1


def maps(args):
    binary = util.example_bin("aw2_map_audit")
    util.check_fresh(binary, "aw2_map_audit")
    env = cfg.env_with_cargo()
    if args.ds:
        env["TANGOAW2_DS_ROM"] = str(cfg.ds_rom())
    cmd = [str(binary), str(cfg.aw2_rom())] + (["--md"] if args.md else []) + (["--sources"] if args.sources else []) + (["--needs-pack"] if args.needs_pack else [])
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=cfg.REPO)
    print(r.stdout[-6000:] if not args.full else r.stdout)
    if r.returncode:
        print(r.stderr[-1500:])
    util.say("map audit " + ("PASS" if r.returncode == 0 else "FAIL (a map's data disagrees with its header, or a map has no HQ for an army it has)"))
    return r.returncode
