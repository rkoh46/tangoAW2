"""aw2dev armyskin: custom armies as data files on top of AW2's five colours (docs/dev/army-packs.md, skill aw2-add-army-pack).

  armyskin preview [--colour N] [--skin FILE] [--fast] [--out PNG]   the skin's pictures next to AW2's own, at 8x, and its palettes
  armyskin check [--live] [--skin FILE] [--scenario S ...]            the data file, the palette's margins, every unit's recolouring; --live also walks the
                                                                      catalogue of army-coloured screens and fails on any left in the base army's colours
  armyskin matrix [--quick] [--armies 2 3] [--colours 5] [--no-ds]    the skin on every colour in every army count (2..5): the skins' rooms in free ROM, the panel, the build menu, a battle
  armyskin catalogue                                                  the screens (scenarios) and what each shows
  armyskin options --dir DIR [--letters ACF] [--awbw DIR]            a sheet of soldier options (candidate files A.toml ...) to choose from
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
    a.add_argument("--awbw-ref", metavar="DIR", help="a directory with the reference pictures (jsinfantry.gif, jsmech.gif, jslogo.gif; local only, never committed): fails if our helmet or logo is too like them")
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
    a.add_argument("--ds", action="store_true", help="with the Dual Strike pack and its graphics (the checkpoint made with --ds)")
    a.add_argument("--tilt", action="store_true", help="and the Dual Strike tilted map (implies --ds)")
    a.add_argument("--tilt-scale", type=int, help="the tilt's picture scale (the hi-res picture), 1..8")
    a.set_defaults(fn=run_look)
    a = ps.add_parser("sheet", help="review sheets (pictures from the scenarios, one row per unit, the palette, the art at 4x) into a directory")
    a.add_argument("--out", required=True)
    a.add_argument("--awbw", help="a directory with another project's reference pictures to show beside ours (review only, never committed)")
    a.add_argument("--ds", action="store_true", help="also the Dual Strike pack's sheet")
    a.add_argument("--prev", action="append", default=[], metavar="LABEL=FILE", help="an earlier data file (v1=/path/x.toml): its helmet and HQ are drawn beside the new ones (sheet 03); repeat for each")
    a.set_defaults(fn=run_sheet)
    a = ps.add_parser("options", help="a sheet of soldier options (Infantry + Mech designs from candidate files A.toml, B.toml ...) to choose from")
    a.add_argument("--dir", required=True, help="the candidate files (see armyskinlib/options.py for their format)")
    a.add_argument("--letters", help="only these (e.g. ACF)")
    a.add_argument("--awbw", help="a directory with another project's reference pictures to show on top (review only, never committed)")
    a.add_argument("--skin")
    a.add_argument("--out", help="the PNG (default devkit/work/armyskin/options.png)")
    a.add_argument("--no-tile", action="store_true", help="do not run the harness for a real plain map tile (a flat colour instead)")
    a.set_defaults(fn=run_options)
    a = ps.add_parser("matrix", help="the skin on every colour (1..5) in every army count (2..5), with the Dual Strike pack: free-ROM rooms, panel, build menu, battle")
    a.add_argument("--quick", action="store_true", help="four of the twenty (the skin on colour 5 in 2P and 5P, the others' lowest): for the suite")
    a.add_argument("--armies", type=int, nargs="*", help="only these army counts")
    a.add_argument("--colours", type=int, nargs="*", help="only these colours")
    a.add_argument("--no-ds", action="store_true", help="without the Dual Strike pack (its backups are not written then)")
    a.add_argument("--keep", action="store_true")
    a.set_defaults(fn=run_matrix)
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
    if a.awbw_ref:
        f3, r3 = chk.originality(a.awbw_ref, skin_path=a.skin)
        print("\n".join(r3))
        fails += f3
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


def run_matrix(a):
    from ..armyskinlib import matrix
    util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
    pairs = list(matrix.QUICK) if a.quick else [(n, c) for n in (a.armies or matrix.COUNTS) for c in (a.colours or matrix.COLOURS)]
    fails, rep = matrix.run(pairs, ds=not a.no_ds, keep=a.keep)
    print("\n".join(rep))
    for f in fails:
        print("FAIL", f)
    print(f"armyskin matrix done {len(pairs)} runs bad={len(fails)}")
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
    from ..armyskinlib import look as lk
    ids = [int(x) for x in a.ids.split(",")] if a.ids else None
    rc, log = lk.checkpoint(a.name, a.scenario, ids, a.ds)
    util.say(("saved" if rc == 0 else "FAILED") + f" checkpoint {a.name} in {CKPT()} (scenario {a.scenario}; log {log})")
    return rc


def run_look(a):
    from ..armyskinlib import look as lk
    shot = Path(a.shot or cfg.work("armyskin", f"look_{a.name}.png"))
    armies = lk.look(a.name, shot, ds=a.ds, tilt=a.tilt, scale=a.tilt_scale, wait=a.wait)
    for ar in armies:
        print(f"army {ar['army']}: colour {ar['colour']} ({ar.get('colour_name')}) co {ar['co_name'] or ar['co']} units {ar['units']} properties {ar['properties']}")
    util.say("screenshot", shot)
    return 0


def run_options(a):
    from ..armyskinlib import options as op, sheet as sh
    tile = None
    if not a.no_tile:
        try:
            util.check_fresh(util.example_bin("aw2_room_teams"), "aw2_room_teams")
            work = cfg.work("armyskin", "options")
            dirs = sh.run_scenarios(["units"], work)
            tile = op.plain_tile(dirs["units"] / "units_s0.bmp")
        except SystemExit:
            tile = None
    out = Path(a.out or cfg.work("armyskin", "options.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    op.sheet(a.dir, list(a.letters) if a.letters else None, tile=tile, awbw_dir=a.awbw, skin_path=a.skin).save(out)
    util.say("wrote", out)
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
    names = ["units", "battle", "battle_mech", "power", "capture", "turn", "results", "lost3p", "map5p", "rematch", "hqs"]
    dirs = sh.run_scenarios(names, work)
    ds_dirs = sh.run_scenarios(["dsunits", "crumb"], work / "ds", ds=True) if a.ds else {}
    host = 1
    sh.unit_rows(host).save(out / "02_every_unit.png")
    prev = [tuple(x.split("=", 1)) for x in a.prev]
    tilt_pics = []
    if a.ds:
        from ..armyskinlib import look as lk
        from PIL import Image as _Image
        for scen, title in (("tilt", "2 armies: Emerald Sun (idle and done units, properties, the HQ at the left) against Blue Moon"),
                            ("tilt5p", "5 armies: Emerald Sun beside Green Earth and Black Hole")):
            rc, log = lk.checkpoint(f"sheet_{scen}", scen, None, True)
            png = work / f"{scen}.png"
            if rc == 0:
                lk.look(f"sheet_{scen}", png, tilt=True, scale=4)
                tilt_pics.append((title, _Image.open(png).convert("RGB")))
    sh.compare_strip(host, a.awbw, prev=prev, tilt_shot=(tilt_pics[0][1] if tilt_pics else None), map_shot=[sh.shot(dirs, "hqs", n) for n in ("hq_os", "hq_es", "hq_bh", "hq_ge", "hq_yc")]).save(out / "03_art_4x.png")
    sh.swatches(host).save(out / "04_palette.png")
    from ..armyskinlib import figures as fg
    fg.battle_sheet(host).save(out / "10_battle_portrait.png")
    m5 = [("5 armies: Emerald Sun (stands in for Blue Moon's colour), Orange Star, Green Earth, Yellow Comet, Black Hole", sh.shot(dirs, "map5p", "map5")), ("same map, far side", sh.shot(dirs, "map5p", "map5_far"))]
    sh.grid(m5, 2, 3).save(out / "01_five_armies.png")
    screens = [("idle units", sh.shot(dirs, "units", "units")), ("done units", sh.shot(dirs, "units", "done")), ("HQ", sh.shot(dirs, "units", "hq")), ("build menu", sh.shot(dirs, "units", "build")),
               ("unit panel", sh.shot(dirs, "units", "panel")), ("build menu: Mech portrait", sh.shot(dirs, "units", "build_mech")), ("battle: Infantry", sh.shot(dirs, "battle", "scene2")), ("battle: Mech against a Tank", sh.shot(dirs, "battle_mech", "scene3")), ("power menu", sh.shot(dirs, "power", "power_menu")),
               ("power dialogue", sh.shot(dirs, "power", "power_say")), ("capturing", sh.shot(dirs, "capture", "capture2")), ("NEXT TURN", sh.shot(dirs, "turn", "nextturn")),
               ("DAY banner", sh.shot(dirs, "turn", "day")), ("end-turn menu", sh.shot(dirs, "turn", "endturn")), ("DEFEAT", sh.shot(dirs, "results", "defeat")),
               ("VICTORY (other seat)", sh.shot(dirs, "results", "victory", 1)), ("The Emerald Sun Army has lost!", sh.shot(dirs, "lost3p", "lost_msg", 1)),
               ("next match, no trace", sh.shot(dirs, "rematch", "rematch"))]
    sh.grid(screens, 4, 3, caption="Emerald Sun on Orange Star's colour against Blue Moon (2 armies; harness frames of the game, 240x160 at 3x)").save(out / "05_screens.png")
    if ds_dirs:
        ds = [("DS units on the map", sh.shot(ds_dirs, "dsunits", "ds_parade")), ("build menu: Megatank", sh.shot(ds_dirs, "dsunits", "ds_build")),
              ("battle scene: Megatank", sh.shot(ds_dirs, "dsunits", "ds_scene2")), ("Crumb leads: his HQ (placeholder)", sh.shot(ds_dirs, "crumb", "crumb_hq"))]
        sh.grid(ds, 2, 3, caption="With the Dual Strike pack").save(out / "06_dual_strike.png")
        if tilt_pics:
            sh.tilt_sheet(tilt_pics).save(out / "07_tilt.png")
    util.say("sheets in", out)
    return 0
