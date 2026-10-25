"""aw2dev art: general art tools (docs/dev/art-repal.md, skill aw2-art-repal).

  art repal apply --palette SRC [--weights luma|rgb|a,b,c] [--dither none] [--keep-index] [--alpha-last] [--opaque] IMAGES... -o DIR
                                        put pictures onto a fixed palette in its slot order: indexed PNGs, transparent = index 0 (or the last)
  art repal extract SRC -o FILE.gpl|FILE.pal       a palette source (picture, .gpl, .pal, co:<id>, skin:<id>, army:os|bm|ge|yc|bh) written as a palette file
  art repal convert PAL -o FILE.gpl|FILE.pal       one palette file format to another
  art repal preview IMAGE --palette SRC [--out PNG] before / after side by side with the palette's slots (default under devkit/work/repal/)
  art repal importsheet [CO ...] [--out DIR]       the CO importer's colour matching compared (`match` = lab, luma, rgb): the large art and mug side by side, and how well the
                                                   dark cells keep their shading (luma error, tones used); `<co>_match.png` under devkit/work/repal/
"""
from pathlib import Path
import numpy as np
from PIL import Image
from .. import cfg, util
from ..artlib import repal


def register(sub):
    p = sub.add_parser("art", help="art tools: palette replacement (docs/dev/art-repal.md)")
    ps = p.add_subparsers(dest="artcmd", required=True)
    r = ps.add_parser("repal", help="put pictures onto a fixed palette (weighted nearest colour, slot order kept)")
    rs = r.add_subparsers(dest="repalcmd", required=True)

    def common(a):
        a.add_argument("--palette", required=True, help=".gpl, .pal, a PNG, co:<id>, skin:<id> or army:os|bm|ge|yc|bh")
        a.add_argument("--weights", default="luma", help="luma (30,59,11, default), rgb (1,1,1) or a,b,c")
        a.add_argument("--dither", choices=["none"], default="none", help="no dithering (the only mode: pixel art keeps flat areas)")
        a.add_argument("--keep-index", action="store_true", help="an indexed picture keeps its indexes: only the palette is swapped")
        a.add_argument("--alpha-last", action="store_true", help="the transparent slot is the palette's last entry (Mugen) instead of index 0")
        a.add_argument("--opaque", action="store_true", help="no transparent slot: every entry may be used")

    a = rs.add_parser("apply", help="pictures -> indexed PNGs on the palette")
    common(a)
    a.add_argument("images", nargs="+")
    a.add_argument("-o", "--out", required=True, help="output directory")
    a.set_defaults(fn=apply)
    a = rs.add_parser("extract", help="a palette source -> .gpl / .pal")
    a.add_argument("source")
    a.add_argument("-o", "--out", required=True)
    a.set_defaults(fn=extract)
    a = rs.add_parser("convert", help="palette file -> .gpl / .pal")
    a.add_argument("source")
    a.add_argument("-o", "--out", required=True)
    a.set_defaults(fn=extract)
    a = rs.add_parser("preview", help="before / after side by side")
    common(a)
    a.add_argument("image")
    a.add_argument("--out")
    a.set_defaults(fn=preview)
    a = rs.add_parser("importsheet", help="the CO importer's `match` rules (lab, luma, rgb) side by side, with dark-area numbers")
    a.add_argument("co", nargs="*", help="CO ids with a pixel-art portrait (default: every one)")
    a.add_argument("--out")
    a.set_defaults(fn=importsheet)


def _setup(args):
    pal = repal.load_palette(args.palette)
    w = repal.weights(args.weights)
    t = repal.transparent_slot(len(pal), args.alpha_last, args.opaque)
    return pal, w, t


def apply(args):
    try:
        pal, w, t = _setup(args)
    except (ValueError, OSError) as e:
        util.die(str(e))
    out = Path(args.out)
    rc = 0
    for f in args.images:
        try:
            img = Image.open(f)
            idx = repal.apply(img, pal, w, args.alpha_last, args.opaque, args.keep_index)
        except (ValueError, OSError) as e:
            print(f"  [FAIL] {f}: {e}")
            rc = 1
            continue
        p = repal.save_png(idx, pal, out / (Path(f).stem + ".png"), t)
        print(f"  {f} -> {p} ({len(set(idx.ravel().tolist()))} of {len(pal)} slots used)")
    return rc


def extract(args):
    try:
        pal = repal.load_palette(args.source)
        p = repal.write_palette(pal, args.out)
    except (ValueError, OSError) as e:
        util.die(str(e))
    print(f"  {args.source}: {len(pal)} entries -> {p}")
    return 0


def preview(args):
    try:
        pal, w, t = _setup(args)
        img = Image.open(args.image)
        idx = repal.apply(img, pal, w, args.alpha_last, args.opaque, args.keep_index)
    except (ValueError, OSError) as e:
        util.die(str(e))
    out = Path(args.out) if args.out else cfg.work("repal", Path(args.image).stem + "_preview.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    repal.preview(img, idx, pal, t, f"{Path(args.image).name} on {args.palette} ({args.weights})").save(out)
    print(f"  {out}")
    return 0


MATCHES = ("lab", "luma", "rgb")


def _luma(c):
    c = np.asarray(c, float)
    return 0.30 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2]


def match_stats(spec, path, imported):
    """How faithfully the importer's large art keeps the picture's cells: over the figure's cells in the frame, and over its dark cells (luma < 90),
    the mean |luma(picture) - luma(art)| (shading), the mean Lab difference (hue and all) and the number of palette tones the dark cells use. -> dict."""
    from ..colib import pixelart as P, importer as I
    img = np.array(Image.open(path).convert("RGB"))
    nat = P.native(img, P.detect_grid(img))
    if spec.get("flip"):
        nat = nat[:, ::-1].copy()
    fg, _ = P.cut_background(nat, spec.get("bg_tolerance", 9.0))
    fg = P.keep_main(fg)
    Q = 64
    nat = np.pad(nat, ((Q, Q), (Q, Q), (0, 0)), mode="edge")
    fg = np.pad(fg, Q, constant_values=False)
    x0, y0 = imported.spec["frame"]
    fr = (slice(y0 + Q, y0 + Q + 80), slice(x0 + Q, x0 + Q + 64))
    src, m = nat[fr], fg[fr]
    art = imported.large[::2, ::2]
    pal = np.array(imported.palette, float)
    m = m & (art != 0) & (art != 15)
    got = pal[art]
    err = np.abs(_luma(src) - _luma(got))
    de = np.sqrt(((I.to_lab(src) - I.to_lab(got)) ** 2).sum(-1))
    dark = m & (_luma(src) < 90)
    mean = lambda a, k: float(a[k].mean()) if k.any() else 0.0
    return {"cells": int(m.sum()), "err": mean(err, m), "de": mean(de, m), "dark": int(dark.sum()), "dark_err": mean(err, dark), "dark_de": mean(de, dark),
            "dark_tones": len(set(art[dark].tolist()))}


def importsheet(args):
    import tomllib
    from PIL import ImageDraw
    from ..colib import importer as I
    cos = cfg.REPO / "tango-gamesupport-aw2" / "cos"
    ids = args.co or sorted(f.stem for f in cos.glob("*.toml") if f.stem != "tags")
    outdir = Path(args.out) if args.out else cfg.work("repal")
    outdir.mkdir(parents=True, exist_ok=True)
    for co in ids:
        d = tomllib.loads((cos / f"{co}.toml").read_text()) if (cos / f"{co}.toml").exists() else {}
        source = d.get("portrait", {}).get("source")
        if not source:
            continue
        side = (cfg.REPO / source).with_suffix(".toml")
        framing = tomllib.loads(side.read_text()) if side.exists() else {}
        if not framing.get("pixelart"):
            print(f"  {co}: not a pixel-art import (the `match` key applies to the pixel-art importer)")
            continue
        S = 2
        tiles, rows = [], []
        try:
            committed, _ = I.read_art(co)
        except OSError:
            committed = {}
        for mt in MATCHES:
            im = I.import_co({"source": source, "match": mt})
            st = match_stats({**framing, "match": mt}, cfg.REPO / source, im)
            tiles.append((mt, I.to_image(im.large, im.palette, S, bg=(24, 40, 88)), I.to_image(im.faces["normal"], im.palette, S * 2, bg=(24, 40, 88)), st, im))
            same = "large" in committed and np.array_equal(committed["large"], im.large)
            st["committed"] = same
            rows.append(f"  {co:8s} {mt:5s} all cells: luma error {st['err']:5.2f}, Lab error {st['de']:5.2f} | dark cells ({st['dark']}): luma error {st['dark_err']:5.2f}, "
                        f"Lab error {st['dark_de']:5.2f}, tones {st['dark_tones']:2d}" + (" | the committed art" if same else "")
                        + ("" if mt == "lab" else f" | cells changed from lab: {int((im.large != tiles[0][4].large).sum() // 4)}"))
        W = sum(t[1].width + t[2].width + 24 for t in tiles) + 12
        H = max(t[1].height for t in tiles) + 60
        sheet = Image.new("RGBA", (W, H), (30, 30, 36, 255))
        dr = ImageDraw.Draw(sheet)
        x = 12
        for mt, large, mug, st, _ in tiles:
            dr.text((x, 6), f"{co}  match = {mt}" + ("  (committed art)" if st["committed"] else ""), fill=(235, 235, 235, 255))
            dr.text((x, 20), f"dark: luma err {st['dark_err']:.1f}, Lab err {st['dark_de']:.1f}; all: Lab err {st['de']:.1f}", fill=(200, 200, 160, 255))
            sheet.paste(large, (x, 40))
            sheet.paste(mug, (x + large.width + 6, 40))
            x += large.width + mug.width + 24
        p = outdir / f"{co}_match.png"
        sheet.save(p)
        print("\n".join(rows))
        print(f"  {p}")
    return 0
