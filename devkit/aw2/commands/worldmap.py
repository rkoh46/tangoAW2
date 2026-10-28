"""aw2dev worldmap: the picture-based campaign world map (docs/dev/worldmap.md, skill aw2-add-campaign).

  worldmap convert <source>                       the picture -> GBA tiles, palettes, regions; writes the checked-in art/worldmap/<source>.bin
  worldmap preview <source> [--conquered 1,3|all] [--out PNG]
                                                  the map as the GBA draws it (from the checked-in .bin), next to the resampled picture, with
                                                  conquered regions in Black Hole's colours and the camera's corner views
  worldmap check <source>                         budgets (tiles, palettes), regions cover the land, flag places inside their nation, the
                                                  conversion is stable (the .bin is what convert makes now); exit 1 on a problem
"""
from .. import util
from ..worldmaplib import tool


def register(sub):
    p = sub.add_parser("worldmap", help="picture world map: convert / preview / check (docs/dev/worldmap.md)")
    ps = p.add_subparsers(dest="wmcmd", required=True)
    a = ps.add_parser("convert", help="convert art-src/worldmap/<source>_world.jpg to the checked-in .bin")
    a.add_argument("source", help="e.g. bh2")
    a.set_defaults(fn=convert)
    a = ps.add_parser("preview", help="render the converted map (and conquered states) to a PNG")
    a.add_argument("source")
    a.add_argument("--conquered", help="comma-separated region numbers (1 Orange Star .. 5 Ashen Shelf) or 'all': one extra panel; default shows four states")
    a.add_argument("--out", help="PNG path (default devkit/work/worldmap/<source>_preview.png)")
    a.set_defaults(fn=preview)
    a = ps.add_parser("check", help="budgets, region coverage and stability")
    a.add_argument("source")
    a.set_defaults(fn=check)


def convert(args):
    m, p = tool.do_convert(args.source)
    util.say(f"{p}: {len(p.read_bytes())} bytes, PSNR {m.stats['psnr']:.1f} dB, {m.stats['unique_before_folding']} distinct tiles, {m.stats['folded']} folded")
    for line in tool.stats(m):
        util.say(line)
    return 0


def preview(args):
    sets = None
    if args.conquered:
        sets = [()] + [tuple(range(1, 6)) if args.conquered == "all" else tuple(int(x) for x in args.conquered.split(","))]
    out, m = tool.preview(args.source, sets, out=args.out)
    for line in tool.stats(m):
        util.say(line)
    util.say(f"preview: {out}")
    return 0


def check(args):
    problems = tool.check(args.source)
    for p in problems:
        util.say(f"PROBLEM: {p}")
    util.say("worldmap check: " + ("clean" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0
