"""aw2dev armyskin: custom armies as data files on top of AW2's five colours (docs/dev/army-packs.md, skill aw2-add-army-pack).

  armyskin preview [--colour N] [--skin FILE] [--fast] [--out PNG]   the skin's pictures next to AW2's own, at 8x, and its palettes
  armyskin check [--live] [--skin FILE] [--scenario S ...]            the data file, the palette's margins, every unit's recolouring; --live also walks the
                                                                      catalogue of army-coloured screens and fails on any left in the base army's colours
  armyskin catalogue                                                  the screens (scenarios) and what each shows
  armyskin scenario NAME [--ids 6,2] [--ds] [--out DIR]              run one scenario's harness script and keep its shots (for sheets)
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
