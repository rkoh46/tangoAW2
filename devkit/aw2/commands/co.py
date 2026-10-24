"""aw2dev co: custom COs as data files (docs/dev/co-kit.md, skill aw2-add-co). Data: tango-gamesupport-aw2/cos/<id>.toml, motifs: cos/art/*.toml.

  co portrait donors [--source aw2|ds] [--out PNG]       every donor CO's figure and faces from the ROMs, with the palette's swatches (to choose a base and see which palette entries are what)
  co portrait palette DONOR                             a donor's 15 palette entries with hue, saturation, value and how many pixels use each (to write a recipe's `ramp` rules)
  co portrait compose CO [--option A] [--scale N] [--out PNG]   one option of a CO's recipe composed and drawn (figure, three faces, small face, HUD face)
  co portrait options CO [--letters ABC] [--out PNG]     the lettered options of a CO on one sheet: large portrait, small faces, a line about each
  co portrait check [CO ...]                            every recipe composes, fits the game's 15 colours (+ transparent) and uses only motifs that exist
  co balance [CO ...] [--vs Kanbei Hawke ...]           the CO's day-to-day, CO Power and Super Power averaged over a typical army, next to Dual Strike's own COs read from the .nds
  co check [CO ...]                                     the CO data files: fields, stars and numbers inside AW2's design space
"""
import sys
from pathlib import Path
from .. import cfg, util


def register(sub):
    p = sub.add_parser("co", help="custom COs: portrait compose/options, data check (docs/dev/co-kit.md)")
    ps = p.add_subparsers(dest="cocmd", required=True)
    pp = ps.add_parser("portrait", help="portraits composed from the ROMs' parts and our own overlays")
    pq = pp.add_subparsers(dest="pcmd", required=True)
    a = pq.add_parser("donors", help="a sheet of every donor CO")
    a.add_argument("--source", default="aw2", choices=["aw2", "ds"])
    a.add_argument("--out")
    a.set_defaults(fn=donors)
    a = pq.add_parser("palette", help="a donor's palette entries")
    a.add_argument("donor", help="aw2:name or ds:name")
    a.set_defaults(fn=palette)
    a = pq.add_parser("compose", help="one option, drawn")
    a.add_argument("co")
    a.add_argument("--option", default="A")
    a.add_argument("--scale", type=int, default=3)
    a.add_argument("--out")
    a.set_defaults(fn=compose_one)
    a = pq.add_parser("options", help="the lettered options of a CO on one sheet")
    a.add_argument("co")
    a.add_argument("--letters")
    a.add_argument("--out")
    a.set_defaults(fn=options)
    a = pq.add_parser("check", help="every recipe composes and fits")
    a.add_argument("co", nargs="*")
    a.set_defaults(fn=pcheck)
    b = ps.add_parser("balance", help="average firepower / defence / move / range per power level against Dual Strike's COs")
    b.add_argument("co", nargs="*")
    b.add_argument("--vs", nargs="*", help="Dual Strike CO names to compare with")
    b.set_defaults(fn=balance)
    c = ps.add_parser("check", help="the CO data files")
    c.add_argument("co", nargs="*")
    c.set_defaults(fn=datacheck)


def _lib():
    from ..colib import compose, render, roms, sheets
    return compose, render, roms, sheets


def donors(a):
    compose, render, roms, sheets = _lib()
    return sheets.donors(a)


def palette(a):
    compose, render, roms, sheets = _lib()
    d = compose.donor(a.donor)
    for i, c, h, s_, v, n in compose.palette_report(d):
        print(f"{i:2d}  #{c[0]:02X}{c[1]:02X}{c[2]:02X}  hue {h:3d}  sat {s_:.2f}  val {v:.2f}  pixels {n}")
    return 0


def compose_one(a):
    compose, render, roms, sheets = _lib()
    return sheets.compose_one(a)


def options(a):
    compose, render, roms, sheets = _lib()
    return sheets.options(a)


def pcheck(a):
    compose, render, roms, sheets = _lib()
    return sheets.pcheck(a)


def datacheck(a):
    from ..colib import data
    return data.check(a)


def balance(a):
    from ..colib import data
    return data.balance(a)
