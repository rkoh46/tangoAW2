"""The harness suite (port of flash/suite.sh): every waiting-view script, the leak scripts, the camera/picture/HUD checkers.

Prints failures only, then `suite done bad=N`. Run it after ANY change to fog_view.rs / pvp.rs / result_view.rs; do not rebuild the
examples while it runs. Scripts are independent, so they run `--jobs` at a time (default 3; the old serial run took ~10 minutes).
"""
import shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import cfg, harness, util

PLAIN = """aw2_waiting_pages aw2_waiting_pages_fog aw2_waiting_pages_2p_nofog aw2_waiting_scene_5p aw2_waiting_scene_5p_nofog aw2_waiting_scene_4p
aw2_waiting_power_5p aw2_waiting_power_5p_nofog aw2_waiting_power_2p aw2_waiting_power_2p_nofog aw2_waiting_power_4p aw2_waiting_cruiser_5p_nofog
aw2_waiting_colours_ship_5p aw2_waiting_colours_2p aw2_waiting_colours_2p_nofog aw2_waiting_hostcam_5p aw2_waiting_round_5p aw2_waiting_long_5p
aw2_waiting_long_4p aw2_waiting_pests_2p aw2_waiting_pests_3p aw2_waiting_pests_4p aw2_waiting_pests_5p aw2_yield_2p aw2_yield_2p_nofog aw2_yield_3p
aw2_yield_3p_nofog aw2_proxy_yield_3p aw2_proxy_yield_3p_nofog aw2_proxy_yield_5p aw2_banner_5p aw2_roster_3p aw2_roster_setup_3p""".split()
LEAK = "aw2_waiting_leak_2p aw2_waiting_leak_3p aw2_waiting_leak_4p aw2_waiting_leak_5p aw2_waiting_leak_2p_nofog aw2_waiting_leak_3p_nofog aw2_waiting_leak_4p_nofog aw2_waiting_leak_5p_nofog".split()
CAM = "aw2_waiting_cam_2p aw2_waiting_cam_3p aw2_waiting_cam_4p aw2_waiting_cam_5p aw2_waiting_hostcam_5p".split()
TOOLS = cfg.REPO / "tools"


def _py(*a):
    r = subprocess.run([sys.executable, *map(str, a)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run(jobs=3, only=None, keep=False):
    out = cfg.work("suite", time.strftime("%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
    tasks = []   # (label, callable -> list of failure strings)

    def plain(sc):
        rc, log = harness.run_script(sc, out / sc, sample=10, log=out / f"{sc}.log")
        return [f"FAIL {sc}"] if rc else []

    def leak(sc):
        rc, log = harness.run_script(sc, out / sc, sample=10, leak=True, log=out / f"{sc}.log")
        return [f"FAIL leak {sc}"] if rc else []

    def cam(sc):
        res = []
        rc, log = harness.run_script(sc, out / sc, sample=2, cam_log=True, log=out / f"{sc}.log")
        if rc:
            res.append(f"FAIL {sc}")
        crc, txt = _py(TOOLS / "cam_check.py", log)
        if crc:
            res.append(f"FAIL camera {sc}\n" + "\n".join(txt.splitlines()[:3]))
        return res

    def pic(n):
        d = out / f"dump_cam{n}"
        harness.run_script("aw2_waiting_cam_%dp" % n, out / f"pic{n}", sample=1, dump=d, log=out / f"pic{n}.log")
        crc, txt = _py(TOOLS / "pic_check.py", d, ",".join(str(k) for k in range(1, n)))
        res = [f"FAIL picture {n}p\n" + "\n".join(txt.splitlines()[:4])] if crc else []
        shutil.rmtree(d, ignore_errors=True)
        return res

    def hud():
        d = out / "dump_hud"
        harness.run_script("aw2_waiting_hud_2p_nofog", out / "hud", sample=1, dump=d, log=out / "hud.log")
        res = []
        for seat, colour in ((1, "red"), (0, "blue")):
            crc, txt = _py(TOOLS / "hud_check.py", d, seat, colour, 945)
            if crc:
                res.append(f"FAIL hud seat {seat}\n" + "\n".join(txt.splitlines()[:3]))
        shutil.rmtree(d, ignore_errors=True)
        return res

    work = [(plain, s) for s in PLAIN] + [(leak, s) for s in LEAK] + [(cam, s) for s in CAM] + [(pic, n) for n in (2, 3, 4, 5)] + [(lambda _: hud(), None)]
    if only:
        work = [w for w in work if any(o in str(w[1]) for o in only)]
    bad = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for res in ex.map(lambda w: w[0](w[1]), work):
            for line in res:
                print(line, flush=True)
                bad += 1
    util.say(f"{len(work)} checks in {time.time() - t0:.0f}s; logs in {out}")
    print(f"suite done bad={bad}", flush=True)
    if not keep:
        for p in out.iterdir():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    return 1 if bad else 0
