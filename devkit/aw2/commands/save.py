"""aw2dev save: look into a cartridge save (docs/dev/save-inspect.md).

  save inspect FILE.sav [--json]   every suspended game in the save: its slot and size, AW2's block (day, map), tangoAW2's marks after it (the pairs, a later stage, two fronts), and a five-army
                                   battle's record: its place, FIVE_ON, each army's funds / colour / control / CO and unit count, and whether its hash matches the block (a record that does not is never applied);
                                   the Flash sectors used and free. `tools/aw2test/out/<mode>/<test>/saved.sav` is where the harness leaves its saves.
"""
import json


def register(sub):
    c = sub.add_parser("save", help="look into a cartridge save: suspended games, the five-army record (docs/dev/save-inspect.md)")
    cs = c.add_subparsers(dest="savecmd", required=True)
    a = cs.add_parser("inspect", help="the suspended games of a save and the five-army record")
    a.add_argument("file")
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=inspect)


def inspect(a):
    from .. import savelib
    rep = savelib.inspect(a.file)
    print(json.dumps(rep, indent=1, default=lambda b: b.hex()) if a.json else savelib.render(rep))
    return 0
