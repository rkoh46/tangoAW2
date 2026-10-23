"""aw2dev armyskin: custom armies as data files on top of AW2's five colours (docs/dev/army-packs.md, skill aw2-add-army-pack).

  armyskin preview [--colour N] [--skin FILE] [--fast] [--out PNG]   the skin's pictures next to AW2's own, at 8x, and its palettes
  armyskin check [--live] [--skin FILE] [--scenario S ...]            the data file, the palette's margins, every unit's recolouring; --live also walks the
                                                                      catalogue of army-coloured screens and fails on any left in the base army's colours
  armyskin catalogue                                                  the screens (scenarios) and what each shows
  armyskin scenario NAME [--ids 6,2] [--ds] [--out DIR]              run one scenario's harness script and keep its shots (for sheets)
  armyskin sheet --out DIR [--awbw DIR] [--ds]                        review sheets: screens from the scenarios, one row per unit, the palette, the art at 4x
  armyskin checkpoint NAME [--scenario S] [--ids ..]                  play a scenario in the harness and save the console's state at its end as a checkpoint
  armyskin look NAME [--shot PNG]                                     start the app offline from that checkpoint with the AI debug channel on, print the armies
                                                                      (colour_name, colour, units) and take a screenshot, then stop it (only our own app)
"""
from pathlib import Path
from .. import cfg, harness, util
from ..armyskinlib import preview, scenarios, check as chk


def register(sub):
    p = sub.add_parser("armyskin", help="army skins: preview, check, catalogue, scenario (docs/dev/army-packs.md)")
    ps = p.add_subparsers(dest="skincmd", required=True)
    a = ps.add_parser("preview", help="render the skin's art and palettes next to AW2's own")
    a.add_argument("--colour", type=int, default=3, help="the colour (1..5) the skin sits on")
    a.add_argument("--skin")
    a.add_argument("--out")
    a.add_argument("--fast", action="store_true", help="draw the art straight from the data file (no rebuild of the examples)")
    a.set_defaults(fn=run_preview)
    a = ps.add_parser("check", help="the data file, the palette's margins, the coverage of every unit; --live walks the screens")
    a.add_argument("--skin")
    a.add_argument("--live", action="store_true", help="run the catalogue's scenarios and fail on base-army colours left")
    a.add_argument("--scenario", nargs="*")
    a.add_argument("--ds", action="store_true", help="with the Dual Strike pack (its units too)")
    a.add_argument("--keep", action="store_true")
    a.set_defaults(fn=run_check)
    a = ps.add_parser("sources", help="find ROM palettes an army's colours come from that the skin does not patch")
    a.add_argument("--scenario", nargs="*")
    a.add_argument("--ds", action="store_true")
    a.add_argument("--a", default="1,2", help="the first run's two armies (default 1,2: Orange Star and Blue Moon)")
    a.add_argument("--b", default="3,4", help="the second run's (default Green Earth and Yellow Comet); use 5,1 against 3,4 to see Black Hole's")
    a.set_defaults(fn=run_sources)
    a = ps.add_parser("checkpoint", help="save a harness scenario's end state as a checkpoint (devkit/work/armyskin/checkpoints)")
    a.add_argument("name")
    a.add_argument("--scenario", default="units")
    a.add_argument("--ids")
    a.add_argument("--ds", action="store_true")
    a.set_defaults(fn=run_checkpoint)
    a = ps.add_parser("look", help="boot the real app from a checkpoint through the AI debug channel: state and screenshot")
    a.add_argument("name")
    a.add_argument("--shot", help="PNG path for the app's own picture (default devkit/work/armyskin/look_<name>.png)")
    a.add_argument("--wait", type=float, default=60.0)
    a.set_defaults(fn=run_look)
    a = ps.add_parser("sheet", help="review sheets (pictures from the scenarios, one row per unit, the palette, the art at 4x) into a directory")
    a.add_argument("--out", required=True)
    a.add_argument("--awbw", help="a directory with another project's reference pictures to show beside ours (review only, never committed)")
    a.add_argument("--ds", action="store_true", help="also the Dual Strike pack's sheet")
    a.add_argument("--v1-toml", help="an earlier data file: its HQ is drawn beside the new one (sheet 03)")
    a.set_defaults(fn=run_sheet)
    a = ps.add_parser("catalogue", help="list the scenarios")
    a.set_defaults(fn=run_catalogue)
    a = ps.add_parser("scenario", help="run one scenario's script, keep the shots")
    a.add_argument("name")
    a.add_argument("--ids", help="seat identities, e.g. 6,2 (1 OS, 2 BM, 3 GE, 4 YC, 5 BH, 6 the skin)")
    a.add_argument("--ds", action="store_true")
    a.add_argument("--out")
    a.set_defaults(fn=run_scenario)


def run_preview(a):
    out = a.out or str(cfg.work("armyskin", f"preview_{a.colour}.png"))
    preview(a.colour, out, a.skin, fast=a.fast)
    util.say("wrote", out)
    return 0


def run_check(a):
    fails, rep = chk.static(a.skin)
    print("\n".join(rep))
    if a.live:
        util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
        f2, r2 = chk.live(a.scenario, ds=a.ds, keep=a.keep)
        print("live (the skin's shot against the base army's colours):")
        print("\n".join(r2))
        fails += f2
    for f in fails:
        print("FAIL", f)
    print(f"armyskin check done bad={len(fails)}")
    return 1 if fails else 0


def run_sources(a):
    from ..armyskinlib import sources
    util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
    names = a.scenario or [n for n, sc in scenarios.SCENARIOS.items() if not sc["five"]]
    rep = sources.run(names, ids_a=tuple(int(x) for x in a.a.split(',')), ids_b=tuple(int(x) for x in a.b.split(',')), ds=a.ds)
    print("\n".join(rep) or "  every palette that differs between two armies in these screens is patched")
    return 1 if rep else 0


CKPT = lambda: cfg.work("armyskin", "checkpoints")


def run_checkpoint(a):
    ids = [int(x) for x in a.ids.split(",")] if a.ids else None
    out = cfg.work("armyskin", f"ckpt_{a.name}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.txt").write_text(scenarios.script(a.scenario, ids, checkpoint=a.name))
    CKPT().mkdir(parents=True, exist_ok=True)
    rc, log = harness.run_script(out / "script.txt", out, ds=a.ds, env_extra={"AW2_CKPT_DIR": str(CKPT())})
    util.say(("saved" if rc == 0 else "FAILED") + f" checkpoint {a.name} in {CKPT()} (scenario {a.scenario}; log {log})")
    return rc


def run_look(a):
    import json, os, shutil, subprocess, sys, time
    from .. import profiles
    util.check_fresh(cfg.REPO / "target" / "release" / "tango", "tango")
    ck = CKPT()
    if not (ck / f"{a.name}.state").exists():
        util.die(f"no checkpoint {a.name}: `aw2dev armyskin checkpoint {a.name}` first")
    profiles.ensure("skin", pack=False)
    data = profiles.profile_dir("skin") / "data" / "checkpoints"
    data.mkdir(parents=True, exist_ok=True)
    for ext in ("state", "json"):
        shutil.copy2(ck / f"{a.name}.{ext}", data / f"{a.name}.{ext}")
    app = profiles.test_app(cfg.REPO / "target" / "release" / "tango")
    env = dict(os.environ, TANGOAW2_PROFILE=str(profiles.profile_dir("skin")), TANGOAW2_AI_DEBUG="0", TANGOAW2_BOOT_CHECKPOINT=a.name, AW2DEV_LOOK="1")
    proc = subprocess.Popen([str(app)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cfg.REPO)
    try:
        addr, t0 = None, time.time()
        while time.time() - t0 < 60 and addr is None:
            line = proc.stdout.readline()
            if not line:
                break
            if "AI_DEBUG_LISTENING" in line:
                addr = line.split()[-1]
        if not addr:
            util.die("the app did not open the AI debug channel")
        sys.path.insert(0, str(cfg.REPO / "tools" / "aidebug"))
        from client import AiDebug
        d = AiDebug.connect(addr)
        d.wait_until({"phase": "battle"}, a.wait)
        time.sleep(1.0)
        st = d.state(["armies", "map", "day", "active_army"])
        for ar in st["armies"]:
            print(f"army {ar['army']}: colour {ar['colour']} ({ar.get('colour_name')}) co {ar['co_name'] or ar['co']} units {ar['units']} properties {ar['properties']}")
        shot = Path(a.shot or cfg.work("armyskin", f"look_{a.name}.png"))
        shot.parent.mkdir(parents=True, exist_ok=True)
        d.screenshot(str(shot))
        util.say("screenshot", shot)
    finally:
        proc.terminate()
    return 0


def run_catalogue(a):
    for n, sc in scenarios.SCENARIOS.items():
        print(f"{n:9s} seats {len(sc['ids'])} ids {sc['ids']}  shots {', '.join(sc['shots'])}\n          {sc['what']}")
    return 0


def run_scenario(a):
    if a.name not in scenarios.SCENARIOS:
        util.die(f"no scenario {a.name}; see `aw2dev armyskin catalogue`")
    ids = [int(x) for x in a.ids.split(",")] if a.ids else None
    out = Path(a.out or cfg.work("armyskin", f"scenario_{a.name}"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.txt").write_text(scenarios.script(a.name, ids))
    rc, log = harness.run_script(out / "script.txt", out, ds=a.ds)
    util.say(("PASS" if rc == 0 else "FAIL") + f" {a.name}: shots in {out}")
    return rc


def run_sheet(a):
    """The review sheets: game pictures from the catalogue's scenarios, one row per unit, the palette, the art at 4x (and another project's beside it)."""
    from ..armyskinlib import sheet as sh
    from PIL import Image
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
    work = cfg.work("armyskin", "sheet")
    names = ["units", "battle", "power", "capture", "turn", "results", "lost3p", "map5p", "rematch", "hqs"]
    dirs = sh.run_scenarios(names, work)
    ds_dirs = sh.run_scenarios(["dsunits", "crumb"], work / "ds", ds=True) if a.ds else {}
    host = 1
    sh.unit_rows(host).save(out / "02_every_unit.png")
    v1 = getattr(a, "v1_toml", None)
    sh.compare_strip(host, a.awbw, v1_toml=v1, map_shot=[sh.shot(dirs, "hqs", n) for n in ("hq_os", "hq_es", "hq_bh", "hq_ge", "hq_yc")]).save(out / "03_art_4x.png")
    sh.swatches(host).save(out / "04_palette.png")
    m5 = [("5 armies: Emerald Sun (stands in for Blue Moon's colour), Orange Star, Green Earth, Yellow Comet, Black Hole", sh.shot(dirs, "map5p", "map5")), ("same map, far side", sh.shot(dirs, "map5p", "map5_far"))]
    sh.grid(m5, 2, 3).save(out / "01_five_armies.png")
    screens = [("idle units", sh.shot(dirs, "units", "units")), ("done units", sh.shot(dirs, "units", "done")), ("HQ", sh.shot(dirs, "units", "hq")), ("build menu", sh.shot(dirs, "units", "build")),
               ("unit panel", sh.shot(dirs, "units", "panel")), ("battle", sh.shot(dirs, "battle", "scene2")), ("power menu", sh.shot(dirs, "power", "power_menu")),
               ("power dialogue", sh.shot(dirs, "power", "power_say")), ("capturing", sh.shot(dirs, "capture", "capture2")), ("NEXT TURN", sh.shot(dirs, "turn", "nextturn")),
               ("DAY banner", sh.shot(dirs, "turn", "day")), ("end-turn menu", sh.shot(dirs, "turn", "endturn")), ("DEFEAT", sh.shot(dirs, "results", "defeat")),
               ("VICTORY (other seat)", sh.shot(dirs, "results", "victory", 1)), ("The Emerald Sun Army has lost!", sh.shot(dirs, "lost3p", "lost_msg", 1)),
               ("next match, no trace", sh.shot(dirs, "rematch", "rematch"))]
    sh.grid(screens, 4, 3, caption="Emerald Sun on Orange Star's colour against Blue Moon (2 armies; harness frames of the game, 240x160 at 3x)").save(out / "05_screens.png")
    if ds_dirs:
        ds = [("DS units on the map", sh.shot(ds_dirs, "dsunits", "ds_parade")), ("build menu: Megatank", sh.shot(ds_dirs, "dsunits", "ds_build")),
              ("battle scene: Megatank", sh.shot(ds_dirs, "dsunits", "ds_scene2")), ("Crumb leads: his HQ (placeholder)", sh.shot(ds_dirs, "crumb", "crumb_hq"))]
        sh.grid(ds, 2, 3, caption="With the Dual Strike pack").save(out / "06_dual_strike.png")
    util.say("sheets in", out)
    return 0
