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
aw2_yield_3p_nofog aw2_proxy_yield_3p aw2_proxy_yield_3p_nofog aw2_proxy_yield_5p aw2_banner_5p aw2_roster_3p aw2_roster_setup_3p aw2_skin_units_2p aw2_skin_5p aw2_skin_battle_2p""".split()
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

    def gfx(name):
        from .commands import gfx as g
        fs = g.run_screen(g.load_catalogue()[name], out / "gfx", quiet=True)
        return [f"FAIL gfx {name}: {f['detector']} {f['shot']}: {f['msg']}" for f in fs if f["severity"] == "fail"][:4]

    def gfx_names():
        from .commands import gfx as g
        return list(g.load_catalogue())

    def aidebug_rom(_):
        # the AI debug channel being on must not change the console (skipped without a ROM)
        r = subprocess.run(["sh", str(TOOLS / "aidebug" / "rom_tests.sh")], capture_output=True, text=True)
        return [r.stdout.strip() or "FAIL aidebug rom_tests"] if r.returncode else []

    def armyskin(what):
        # Emerald Sun: the data file and palette margins, every colour the skin can sit on, then the live walk of the army-coloured screens
        # (docs/dev/army-packs.md); skipped without the AW2 ROM or the built dump example
        from .armyskinlib import check as chk
        if not cfg.aw2_rom().exists() or not util.example_bin("aw2_skin_dump").exists():
            return []
        if what == "static":
            fails, _ = chk.static()
            return [f"FAIL armyskin: {f}" for f in fails]
        fails, _ = chk.live(["units", "battle", "turn", "capture", "results"])
        return [f"FAIL armyskin live: {f}" for f in fails]

    def maps_lint(_):
        # the BH Campaign's maps have no map-integrity error (docs/dev/map-lint.md); skipped without the AW2 ROM
        if not cfg.aw2_rom().exists():
            return []
        r = subprocess.run([sys.executable, str(cfg.DEVKIT / "aw2dev"), "maps", "lint", "--no-png"], capture_output=True, text=True)
        return [f"FAIL maps lint\n" + "\n".join(l for l in r.stdout.splitlines() if "error" in l)[:600]] if r.returncode else []

    def campaign_scenes(_):
        # every BH story scene names a song (docs/dev/campaign-scenes.md); needs the harness examples and the ROMs
        if not cfg.aw2_rom().exists() or not util.example_bin("aw2_campaign_scenes").exists():
            return []
        r = subprocess.run([sys.executable, str(cfg.DEVKIT / "aw2dev"), "campaign", "scenes"], capture_output=True, text=True)
        lint = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "bhtext" / "lint.py")], capture_output=True, text=True)
        return ([f"FAIL campaign scenes\n{r.stderr[-400:]}"] if r.returncode else []) + ([f"FAIL bhtext lint\n{lint.stdout[-400:]}"] if lint.returncode else [])

    work = [(campaign_scenes, "campaign_scenes"), (maps_lint, "maps_lint"), (aidebug_rom, "aidebug_rom"), (armyskin, "static"), (armyskin, "live")] + [(plain, s) for s in PLAIN] + [(leak, s) for s in LEAK] + [(cam, s) for s in CAM] + [(pic, n) for n in (2, 3, 4, 5)] + [(lambda _: hud(), None)] + [(gfx, n) for n in gfx_names()]   # (graphics catalogue: text, tile, palette and golden checks of key screens; golden images are optional)
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
