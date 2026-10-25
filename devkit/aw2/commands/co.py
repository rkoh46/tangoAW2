"""aw2dev co: custom COs as data files (docs/dev/co-kit.md, skill aw2-add-co). Data: tango-gamesupport-aw2/cos/<id>.toml, Tag Powers cos/tags.toml, art tango-gamesupport-aw2/art/cos/<id>/.

  co portrait import [CO ...] [--check]    turn the picture a CO's data file names (`[portrait] source`, with its framing file beside it; a `pixelart = true` file, or `--pixelart`, imports a pixel-art picture faithfully on its native grid) into game-ready AW2 art: the 128 x 160 figure,
                                           the four 48 x 48 expression faces, the 32 x 24 mini and the 32 x 16 HUD face, one palette of 15 colours + transparent, outlined, cleaned;
                                           written as indexed PNGs to art/cos/<id>/ (`--check`: only compare with what is committed, exit 1 if different)
  co portrait lint [CO ...]                the committed art: sizes, one shared palette, the outline all round, no speckle
  co portrait grid PICTURE [--out PNG]     pixel-art pictures: the native grid found in the picture (cell size and phase), the figure's box, and a debug PNG with the native cells numbered
  co portrait sheet [CO ...] [--out PNG]   the review sheet: source, large art 1x and 2x beside AW2's own, faces, the CO select and HUD strips with real COs, the game's own screens
  co portrait ingame CO                    start the real app on a boot checkpoint and photograph the CO page, CO select and HUD with the CO (phase 2 wiring needed)
  co balance [CO ...] [--vs Kanbei Hawke ...]   the CO's day-to-day, CO Power and Super Power averaged over a typical army, next to Dual Strike's own COs read from the .nds
  co check [CO ...]                        the CO data files: fields, stars and numbers inside AW2's design space, name plates, tag pairs
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


def _cos(names):
    from ..colib import data
    cos, _ = data.load_all()
    return {k: v for k, v in cos.items() if not names or k in names and v.get("portrait", {}).get("source")}, cos


def pimport(a):
    from pathlib import Path
    import numpy as np
    from ..colib import importer as I
    sel, _ = _cos(a.co)
    bad = 0
    for co, d in sel.items():
        spec = {"source": d["portrait"]["source"]}
        if getattr(a, "pixelart", False):
            spec["pixelart"] = True
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
    bad = 0
    for co in sel:
        d = cfg.work("co", "ingame", co)
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()
        got = ingame.photograph(co, d)
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
