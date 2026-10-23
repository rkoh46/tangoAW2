"""aw2dev armyskin: custom armies as data files on top of AW2's five colours (docs/dev/army-packs.md, skill aw2-add-army-pack).

  armyskin preview [--colour N] [--skin FILE] [--out PNG]   the skin's pictures next to AW2's own, at 8x, and its palettes
"""
from .. import cfg, util
from ..armyskinlib import preview


def register(sub):
    p = sub.add_parser("armyskin", help="army skins: preview, check (docs/dev/army-packs.md)")
    ps = p.add_subparsers(dest="skincmd", required=True)
    a = ps.add_parser("preview", help="render the skin's art and palettes next to AW2's own")
    a.add_argument("--colour", type=int, default=3, help="the colour (1..5) the skin sits on")
    a.add_argument("--skin")
    a.add_argument("--out")
    a.set_defaults(fn=run_preview)


def run_preview(a):
    out = a.out or str(cfg.work("armyskin", f"preview_{a.colour}.png"))
    preview(a.colour, out, a.skin)
    util.say("wrote", out)
    return 0
