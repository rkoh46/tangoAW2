"""aw2dev save: look into a cartridge save (docs/dev/save-inspect.md).

  save exp FILE.sav [--set CO=EXP ...] [--out NEW.sav]
                                   every CO's EXP, rank and sets as slot 15 holds them (AW2's 19 COs, the new eleven, Silver Nova's three, Asuka, Aria: 35 slots); with --set (CO id or name),
                                   writes a copy with those EXPs changed (default FILE.exp.sav) to test a rank, the EXP box's rank-up or a CO's skill slots without playing for it.
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
    x = cs.add_parser("exp", help="every CO's EXP, rank and sets in a save; --set CO=EXP writes a copy with some changed")
    x.add_argument("file")
    x.add_argument("--set", action="append", default=[], metavar="CO=EXP", help="a CO (id or name) and its new EXP (up to 100000)")
    x.add_argument("--out", help="the edited copy's path (default FILE.exp.sav)")
    x.set_defaults(fn=exp)


def inspect(a):
    from .. import savelib
    rep = savelib.inspect(a.file)
    print(json.dumps(rep, indent=1, default=lambda b: b.hex()) if a.json else savelib.render(rep))
    return 0


def exp(a):
    from .. import savelib
    names = {n.lower().replace(" ", ""): c for c, n in savelib.CO_NAMES.items()}
    changes = {}
    for item in a.set:
        who, _, v = item.partition("=")
        co = int(who) if who.isdigit() else names.get(who.lower().replace(" ", ""))
        if co is None or not v.isdigit():
            print(f"aw2dev save exp: cannot read --set {item!r} (a CO id or name, =, an EXP)")
            return 2
        try:
            savelib.co_slot(co)
        except ValueError:
            print(f"aw2dev save exp: CO {who} has no skill slot")
            return 2
        changes[co] = int(v)
    if changes:
        out = a.out or a.file.removesuffix(".sav") + ".exp.sav"
        try:
            savelib.set_exp(a.file, out, changes)
        except ValueError as e:
            print(f"aw2dev save exp: {e}")
            return 1
        print(f"wrote {out}")
        a.file = out
    for co, name, exp_, rank, sets in savelib.exp_table(a.file):
        used = [s for s in sets if any(s)]
        print(f"{co:3d} {name:<11} EXP {exp_:6d}  rank {rank:3d}" + (f"  sets {used}" if used else ""))
    return 0
