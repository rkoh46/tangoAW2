"""aw2dev build: the right toolchain for each target."""
import json, os, subprocess, sys, time
from . import cfg, util


def cargo(*args, profile_env=None):
    env = cfg.env_with_cargo(profile_env)
    util.run(["cargo", *args], env=env, cwd=cfg.REPO)


def build(args):
    t0 = time.time()
    if args.ios or args.sim:
        dev = str(cfg.path("paths", "developer_dir"))
        env = dict(os.environ, DEVELOPER_DIR=dev)
        env["PATH"] = str(cfg.path("paths", "cargo_bin")) + os.pathsep + env["PATH"]
        util.run(["./ios/build.sh"] + (["--sim"] if args.sim else []), env=env, cwd=cfg.REPO)
        util.say(f"iOS build done in {time.time() - t0:.0f}s: {cfg.REPO / 'dist'}")
        return 0
    if args.release:
        cargo("build", "--profile", "release-dist", "--bin", "tango")
        binary = util.release_bin("release-dist")
    else:
        cargo("build", "--release", "-p", "tango")
        binary = util.release_bin("release")
    if args.examples or args.all:
        cargo("build", "--release", "-p", "tango-gamesupport-aw2", "--examples")
    stamp = util.build_stamp(binary)
    cfg.work().mkdir(parents=True, exist_ok=True)
    (cfg.work() / "build_stamp.json").write_text(json.dumps({"stamp": stamp, "binary": str(binary), "time": time.strftime("%F %T"), "release_dist": bool(args.release)}))
    util.say(f"built {binary} stamp {stamp} in {time.time() - t0:.0f}s")
    return 0


def test(args):
    env = cfg.env_with_cargo()
    rc = 0
    if not args.package or "python" in args.package:
        # the map pipeline's tests (no ROM needed): mapsfile merge keeps every map, ids unique and from the pool, room in the data area
        r = util.run([sys.executable, "-m", "unittest", "test_five", "-v"], cwd=cfg.REPO / "tango-gamesupport-aw2" / "five", check=False)
        rc |= r.returncode
        # the map linter's tests (planted rivers, bridges, units, roads; the BH Campaign's maps clean): needs the AW2 ROM
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.maplint.test_maplint"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the design study and the principle rules MD01..MD08 (AWBW ids, the measures, a planted map per rule; no ROM needed)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.maplint.test_study"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the army-skin kit's tests (generated scripts, scenario shots, the palette margins refusing a green skin)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.armyskinlib.test_armyskin"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the CO kit's tests (data files, tag pairs, every portrait recipe composes and fits 15 colours)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.colib.test_co"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # `aw2dev art repal`'s tests (palette files round trip, slot order, luma vs rgb nearest, the transparent slot, a CO palette, the importer's match hook)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.artlib.test_repal"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # recolour-based COs in `co portrait import` (Clone Andy: no picture, his recolour checked on Andy's palette)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.colib.test_recolour"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # `aw2dev co verify`'s tests (the specification read from the data files, the table builder, the net scenarios of every power and pair)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.colib.test_verify"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the Emerald Sun kit's tests (the map generator and its rules, the difficulty score and the campaign check)
        for mod in ("aw2.esmaplib.test_esmaplib", "aw2.eslib.test_eslib", "aw2.bh2lib.test_bh2"):
            r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", mod], cwd=cfg.DEVKIT, check=False)
            rc |= r.returncode
        # the picture world map kit's tests (conversion stable, budgets, regions cover the land, conquest tint, no ROM needed)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.worldmaplib.test_worldmap"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the music kit's tests (the M4A reader, the song compiler's bytes read back by it, pitch / loop-seam / level analysis, the rules)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.musiclib.test_musiclib"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # the online tools' tests (`net desync` tells a stack-only timing skew from a real state desync; `net repeat` is registered)
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.test_net"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        # `aw2dev ci`'s reader of the checks workflow, the workspace conventions it holds, tango-library's feature gates
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.test_ci"], cwd=cfg.DEVKIT, check=False)
        rc |= r.returncode
        r = util.run([sys.executable, "-W", "ignore", "-m", "unittest", "aw2.test_wait"], cwd=cfg.DEVKIT, check=False)   # `aw2dev wait`
        rc |= r.returncode
        from .commands import kit as _kit
        import argparse as _ap
        rc |= _kit.check(_ap.Namespace(strict=False))      # docs, skills and tests must not point at missing commands or files
        if args.package == ["python"]:
            return 1 if rc else 0
    args.package = [p for p in (args.package or []) if p != "python"]
    for pkg in (["tango-gamesupport-aw2", "tango-session", "tango-match"] if not args.package else args.package):
        r = util.run(["cargo", "test", "--release", "-p", pkg, "--lib"], env=env, cwd=cfg.REPO, check=False)
        rc |= r.returncode
        if getattr(args, "debug", False):
            # (release builds do not check integer overflow: a test that overflows only fails here)
            r = util.run(["cargo", "test", "-p", pkg, "--lib"], env=env, cwd=cfg.REPO, check=False)
            rc |= r.returncode
    return 1 if rc else 0
