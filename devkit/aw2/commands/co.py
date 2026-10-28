"""aw2dev co: custom COs as data files (docs/dev/co-kit.md, skill aw2-add-co). Data: tango-gamesupport-aw2/cos/<id>.toml, Tag Powers cos/tags.toml, art tango-gamesupport-aw2/art/cos/<id>/.

  co portrait import [CO ...] [--check]    turn the picture a CO's data file names (`[portrait] source`, with its framing file beside it; a `pixelart = true` file, or `--pixelart`, imports a pixel-art picture faithfully on its native grid) into game-ready AW2 art: the 128 x 160 figure,
                                           the four 48 x 48 expression faces, the 32 x 24 mini and the 32 x 16 HUD face, one palette of 15 colours + transparent, outlined, cleaned;
                                           written as indexed PNGs to art/cos/<id>/ (`--check`: only compare with what is committed, exit 1 if different)
  co portrait lint [CO ...]                the committed art: sizes, one shared palette, the outline all round, no speckle
  co portrait grid PICTURE [--out PNG]     pixel-art pictures: the native grid found in the picture (cell size and phase), the figure's box, and a debug PNG with the native cells numbered
  co portrait powers CO [--out PNG]        the contact sheet of the CO's powers working in the real game: screens, power bar, activations, HP before / after, the Tag Power, Counter Break, fog
  co portrait sheet [CO ...] [--out PNG]   the review sheet: source, large art 1x and 2x beside AW2's own, faces, the CO select and HUD strips with real COs, the game's own screens
  co portrait ingame CO                    start the real app on a boot checkpoint and photograph the CO page, CO select and HUD with the CO (phase 2 wiring needed)
  co balance [CO ...] [--vs Kanbei Hawke ...]   the CO's day-to-day, CO Power and Super Power averaged over a typical army, next to Dual Strike's own COs read from the .nds
  co verify sonja [--build-baseline]       Sonja's rows, pictures, texts, numbers, Tag page and screens against the v0.8.7 build: any difference fails
  co check [CO ...]                        the CO data files: fields, stars and numbers inside AW2's design space, name plates, tag pairs
  co verify [CO ...] [--quick] [--list] [-j N]   every ability of the custom COs (Klaus, Aurelia, Cassius, Livia, Crumb, Varro, Clone Andy, Asuka, Aria) in real battles against the specification: day to day,
                                           CO Power, Super Power (attack, defence, move, range, cost, income, funds, heal, the special rules), meters and star costs, Tag Powers, CPU use;
                                           prints the pass / fail table (docs/dev/co-verify.md); with `--net` also plays each power through `net repeat`
  co sheet hq                              the HQ of the Roman COs on the map: Versus, the tilted map (the real app), the missions (`hq_check.png`)
  co sheet powers [CO ...] [--out DIR]     real-game pictures of each CO's powers (select card, CO page, HUD, activations, tag powers, effects) as `<co>_powers.png` and `all_cos_overview.png`
"""
import sys
from pathlib import Path
from .. import cfg, util


def register(sub):
    p = sub.add_parser("co", help="custom COs: portrait compose/options, data check (docs/dev/co-kit.md)")
    ps = p.add_subparsers(dest="cocmd", required=True)
    pp = ps.add_parser("portrait", help="portraits imported from the supplied pictures")
    pq = pp.add_subparsers(dest="pcmd", required=True)
    a = pq.add_parser("import", help="picture -> AW2 CO art")
    a.add_argument("co", nargs="*")
    a.add_argument("--check", action="store_true")
    a.add_argument("--pixelart", action="store_true", help="the pictures are pixel art upscaled by a factor: find the native grid and import it faithfully (also set by `pixelart = true` in the framing file)")
    a.add_argument("--illustration", action="store_true", help="the pictures are clean illustrations (not pixel art): cut the flat background, downscale with Lanczos / area averaging and quantise to one palette (also set by `illustration = true` in the framing file)")
    a.set_defaults(fn=pimport)
    a = pq.add_parser("grid", help="pixel-art picture: the native grid, the figure's box and a numbered debug picture")
    a.add_argument("picture")
    a.add_argument("--flip", action="store_true")
    a.add_argument("--out")
    a.set_defaults(fn=pgrid)
    a = pq.add_parser("lint", help="lint the committed art")
    a.add_argument("co", nargs="*")
    a.add_argument("--style", choices=["aw2"], help="also measure the art against AW2's own range (brightness, saturation, contrast, flatness, regions, head)")
    a.set_defaults(fn=plint)
    a = pq.add_parser("ingame", help="photograph the CO in the real app: CO select, HUD, CO page, power cut-in, dialogue")
    a.add_argument("co", nargs="*")
    a.set_defaults(fn=pingame)
    a = pq.add_parser("powers", help="the contact sheet of a CO's powers working in the real game (needs `co portrait ingame CO` first)")
    a.add_argument("co")
    a.add_argument("--out")
    a.add_argument("--no-run", action="store_true", help="do not run the scripted picture tests, use the frames of the last run")
    a.set_defaults(fn=ppowers)
    a = pq.add_parser("sheet", help="the review sheet")
    a.add_argument("co", nargs="*")
    a.add_argument("--out")
    a.set_defaults(fn=psheet)
    b = ps.add_parser("balance", help="average firepower / defence / move / range per power level against Dual Strike's COs")
    b.add_argument("co", nargs="*")
    b.add_argument("--vs", nargs="*", help="Dual Strike CO names to compare with")
    b.set_defaults(fn=balance)
    c = ps.add_parser("check", help="the CO data files")
    c.add_argument("co", nargs="*")
    c.set_defaults(fn=datacheck)
    v = ps.add_parser("verify", help="every ability of the custom COs in real battles against the specification (pass / fail table)")
    v.add_argument("co", nargs="*", help="klaus aurelia cassius livia crumb varro cloneandy asuka aria (default: all); `verify sonja` compares Sonja with the v0.8.7 build instead")
    v.add_argument("--build-baseline", action="store_true", help="(verify sonja) build the reference (v0.8.7) examples into devkit/work/baseline first (once)")
    v.add_argument("--quick", action="store_true", help="one scenario per facet (the suite's smoke run)")
    v.add_argument("--list", action="store_true", help="only list the scenarios")
    v.add_argument("-j", "--jobs", type=int, default=4)
    v.add_argument("--net", action="store_true", help="also run the online-determinism scenarios (`net repeat`, several minutes each)")
    v.add_argument("--net-runs", type=int, default=3)
    v.set_defaults(fn=verify)
    sh = ps.add_parser("sheet", help="contact sheets of real-game pictures")
    shs = sh.add_subparsers(dest="shcmd", required=True)
    sp = shs.add_parser("powers", help="each CO's powers in the real game: `<co>_powers.png` per CO and `all_cos_overview.png`")
    sp.add_argument("co", nargs="*")
    sp.add_argument("--out")
    sp.add_argument("--only", nargs="*", help="parts: page hud cop scop effect tag")
    sp.add_argument("-j", "--jobs", type=int, default=3)
    sp.set_defaults(fn=sheet_powers)
    sq = shs.add_parser("hq", help="the HQ of the Roman COs on the map (Versus, the tilted map, the missions): `hq_check.png`")
    sq.add_argument("--out")
    sq.set_defaults(fn=sheet_hq)


def _cos(names):
    from ..colib import data
    cos, _ = data.load_all()
    # (only COs with a picture of their own: a recolour-based CO (`portrait.base`) or a placeholder has no committed art to import, lint or show)
    return {k: v for k, v in cos.items() if (not names or k in names) and v.get("portrait", {}).get("source")}, cos


def pimport(a):
    from pathlib import Path
    import numpy as np
    from ..colib import importer as I
    from ..colib import recolour
    sel, cos = _cos(a.co)
    bad = 0
    # a recolour-based CO has no picture: its recolour is checked instead (the table, and its output on the donor's palette)
    for co, d in cos.items():
        if recolour.is_recolour(d) and (not a.co or co in a.co):
            probs, summary = recolour.check(co, d)
            util.say(f"{co}: {summary}" + ("; PROBLEMS " + "; ".join(probs) if probs else "") + " (nothing to import or compare: no committed art)")
            bad += bool(probs)
    for co, d in sel.items():
        spec = {"source": d["portrait"]["source"]}
        if getattr(a, "pixelart", False):
            spec["pixelart"] = True
        if getattr(a, "illustration", False):
            spec["illustration"] = True
        im = I.import_co(spec)
        I.all_expressions(im, im.spec)
        if a.check:
            old, _pal = I.read_art(co)
            same = all(np.array_equal(old[n], v) for n, v in I.pictures(im).items())
            util.say(f"{co}: {'the committed art is what the picture gives' if same else 'DIFFERENT from the committed art'}")
            bad += not same
        else:
            out = I.write_art(co, im, name=d["name"])
            probs = I.lint_art(co)
            util.say(f"{co}: wrote {out.relative_to(cfg.REPO)} ({len(im.palette) - 1} colours)" + ("; PROBLEMS " + "; ".join(probs) if probs else ""))
            bad += bool(probs)
    return 1 if bad else 0


def pingame(a):
    from ..colib import ingame
    sel, _ = _cos(a.co)
    if "cloneandy" in (a.co or []):
        sel = dict(sel, cloneandy={})
    bad = 0
    for co in sel:
        d = cfg.work("co", "ingame", co)
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()
        got = ingame.photograph(co, d)
        if co == "cloneandy":
            util.say(f"{co}: photographed in the game ({got}); pictures in {d} (recolour of Andy's art: look at them)")
            continue
        res = ingame.verify(co, d)
        for k, v in res.items():
            util.say(f"{co}: {k}: {'ok' if v else 'NOT SEEN'}")
        util.say(f"{co}: photographed in the game ({got}); pictures in {d}")
        bad += not all(res.values())
    return 1 if bad else 0


def plint(a):
    from ..colib import importer as I, style
    sel, _ = _cos(a.co)
    bad = 0
    ranges = style.aw2_ranges()[0] if getattr(a, "style", None) else None
    for co in sel:
        probs = I.lint_art(co)
        if ranges:
            pics, pal = I.read_art(co)
            rows, sp = style.lint(pics, pal, ranges)
            probs = probs + sp
        print(f"{'FAIL' if probs else 'PASS'} {co}: " + ("; ".join(probs) if probs else "sizes, one palette, outline and noise are right" + (", and the style is AW2's" if ranges else "")))
        if ranges:
            for name, v, lo, hi, mean, ok in rows:
                print(f"    {name:24s} {v:8.2f}   AW2 range {lo:7.2f} .. {hi:7.2f} (mean {mean:6.2f})  {'ok' if ok else 'OUT'}")
        bad += bool(probs)
    return 1 if bad else 0


def psheet(a):
    from pathlib import Path
    from ..colib import sheet as S
    sel, _ = _cos(a.co)
    out = Path(a.out or cfg.work("co", "co_portraits.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    S.sheet(list(sel), sel).save(out)
    util.say("wrote", out)
    return 0


def ppowers(a):
    from ..colib import powers_sheet as P
    if not a.no_run:
        ok, tail = P.run_tests(a.co)
        if not ok:
            util.say("the picture tests failed:\n" + tail)
            return 1
    out = Path(a.out or cfg.work("co", f"{a.co}_powers.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    P.sheet(a.co).save(out)
    util.say("wrote", out)
    return 0


def pgrid(a):
    from ..colib import pixelart
    out = Path(a.out or cfg.work("co", Path(a.picture).stem + "_grid.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    info = pixelart.describe(Path(a.picture), flip=a.flip, out=out)
    util.say(info)
    util.say("wrote", out)
    return 0


def balance(a):
    from ..colib import data
    return data.balance(a)


def datacheck(a):
    from ..colib import data
    return data.check(a)


def verify(a):
    if a.co == ["sonja"]:
        from ..colib import verify_sonja
        return verify_sonja.verify_sonja(a)
    from ..colib import verify as V
    rc = 0
    if a.net:
        from ..colib import verify_net as N
        rc = N.run(a)
    return V.verify(a) or rc


def sheet_powers(a):
    from ..colib import powersheet
    import subprocess
    cos = a.co or ["klaus", "aurelia", "cassius", "livia", "crumb", "varro", "cloneandy"]
    out = Path(a.out) if a.out else cfg.work("co_sheets")
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    procs = []
    code = (
        "import sys; sys.path.insert(0, %r); from aw2test import copics; copics.capture(sys.argv[1], %r, tuple(sys.argv[2:]) or ('page', 'hud', 'cop', 'scop', 'effect', 'tag'))"
        % (str(cfg.REPO / "tools" / "aw2test"), str(raw)))
    pending = list(cos)
    running = []
    while pending or running:
        while pending and len(running) < a.jobs:
            co = pending.pop(0)
            util.say(f"pictures: {co}")
            running.append((co, subprocess.Popen([sys.executable, "-c", code, co] + (a.only or []), cwd=cfg.REPO)))
        for co, p in list(running):
            if p.poll() is not None:
                running.remove((co, p))
                if p.returncode:
                    util.say(f"pictures of {co} failed ({p.returncode})")
        import time
        time.sleep(2)
    for co in cos:
        if (raw / co / "captions.json").exists():
            powersheet.sheet(co, raw / co, out / f"{co}_powers.png")
            util.say("wrote", out / f"{co}_powers.png")
    powersheet.overview(raw, out / "all_cos_overview.png", cos)
    util.say("wrote", out / "all_cos_overview.png")
    return 0


def sheet_hq(a):
    from ..colib import powersheet, ingame
    import subprocess
    out = Path(a.out) if a.out else cfg.work("co_sheets")
    raw = out / "hqraw"
    raw.mkdir(parents=True, exist_ok=True)
    code = "import sys; sys.path.insert(0, %r); from aw2test import copics; copics.capture_hq(%r)" % (str(cfg.REPO / "tools" / "aw2test"), str(raw))
    subprocess.run([sys.executable, "-c", code], cwd=cfg.REPO, check=True)
    for co in ("klaus", "aurelia", "cassius", "livia", "varro", "andy"):
        ingame.photograph_hq(co, raw)
    powersheet.hq_sheet(raw, out / "hq_check.png")
    util.say("wrote", out / "hq_check.png")
    return 0
