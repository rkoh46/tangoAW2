"""aw2dev maps: map integrity (docs/dev/map-lint.md, skill aw2-map-lint).

  maps gen [--map es01 ..] [--check]  the Emerald Sun Campaign's text maps from their specs (five/es/spec/esNN.py), then es_map_data.rs (bhmap.py --campaign es)
  maps lint [--source bh|es|versus|aw2|ds|all] [--map NAME ...] [--rule ID ...] [--png DIR] [--json]
                                   check maps for unfinished rivers, orphan sea/shoal, broken joins, bad bridges and roads, pipes, units on terrain
                                   they cannot enter, unreachable properties, HQs with no access, tiles drawn as garbage; exit 1 on an error in
                                   bh / versus maps (aw2 and ds are the reference: their hits are only reported)
  maps rules [--md]                every rule with its hits in AW2's own maps, Dual Strike's, tangoAW2's Versus maps and the BH Campaign's (what the games allow)
  maps compare --base REV [--out DIR]   BH maps at git REV against the working tree: changed cells and before/after pictures
  maps boot [--mission N ...]      enter BH missions in the offline harness and photograph them (tools/aw2test bh_review_m*); the real game's map picture
"""
import collections, json, os, subprocess, sys, tempfile
from pathlib import Path
from .. import cfg, util


def register(sub):
    m = sub.add_parser("maps", help="map integrity: lint, rules, compare, boot (docs/dev/map-lint.md)")
    ms = m.add_subparsers(dest="mapscmd", required=True)
    a = ms.add_parser("lint", help="check maps (default: the BH Campaign's) and render an annotated picture per map")
    a.add_argument("--source", default="bh", choices=["bh", "es", "versus", "aw2", "ds", "all"])
    a.add_argument("--map", nargs="*", help="only these map names (bh01, 'Pentagon Atoll', aw2_1F, ds_0B4)")
    a.add_argument("--rule", nargs="*", help="only these rule ids")
    a.add_argument("--png", metavar="DIR", help="write annotated pictures here (default devkit/work/maps/lint/<source>)")
    a.add_argument("--no-png", action="store_true")
    a.add_argument("--json", action="store_true")
    a.add_argument("--warn", action="store_true", help="show warnings too (default: errors only for bh / versus)")
    a.set_defaults(fn=lint)
    a = ms.add_parser("gen", help="write the Emerald Sun text maps (five/es/esNN.txt) from their specs (five/es/spec/esNN.py), then build es_map_data.rs")
    a.add_argument("--map", nargs="*", help="only these (es01 es02 ...)")
    a.add_argument("--no-build", action="store_true", help="only write the text maps")
    a.add_argument("--check", action="store_true", help="fail if a text map differs from what its spec makes (nothing written)")
    a.set_defaults(fn=gen)
    a = ms.add_parser("rules", help="the rules and what the games' own maps do under each")
    a.add_argument("--md", action="store_true")
    a.set_defaults(fn=rules_table)
    a = ms.add_parser("compare", help="BH maps at a git revision against the working tree")
    a.add_argument("--base", required=True)
    a.add_argument("--out", help="folder for the before/after pictures")
    a.set_defaults(fn=compare)
    a = ms.add_parser("boot", help="enter BH missions in the offline harness and keep the map pictures")
    a.add_argument("--mission", nargs="*", type=int)
    a.add_argument("--out")
    a.set_defaults(fn=boot)


def _lib():
    sys.path.insert(0, str(cfg.DEVKIT))
    from ..maplint import load, rules, render
    return load, rules, render


def _maps(load, source, names=None):
    if source == "es" and names:
        # (only the named maps' files: another author's half-written map must not stop yours)
        return load.es_maps(files=[load.FIVE / "es" / f"{n}.txt" for n in names if (load.FIVE / "es" / f"{n}.txt").exists()])
    out = []
    for s in (["bh", "es", "versus", "aw2", "ds"] if source == "all" else [source]):
        out += {"bh": load.bh_maps, "es": load.es_maps, "versus": load.versus_maps, "aw2": load.aw2_maps, "ds": load.ds_maps}[s]()
    return out


def lint(a):
    load, rules, render = _lib()
    maps = _maps(load, a.source, a.map)
    if a.map:
        maps = [m for m in maps if m.name in a.map]
        if not maps:
            util.die("no such map: " + " ".join(a.map))
    out = None if a.no_png else Path(a.png) if a.png else cfg.work("maps", "lint", a.source)
    if out:
        out.mkdir(parents=True, exist_ok=True)
    bad = 0
    report = {}
    for m in maps:
        probs = rules.lint(m, set(a.rule) if a.rule else None)
        shown = [p for p in probs if a.warn or p.level == "error" or m.source in ("aw2", "ds") or (m.source == "es" and p.rule.startswith(("DQ", "SP")))]
        report[m.name] = [str(p) for p in probs]
        if not a.json:
            if probs:
                print(f"{m.name} ({m.source} {m.w}x{m.h}): {sum(p.level == 'error' for p in probs)} errors, {sum(p.level == 'warn' for p in probs)} warnings")
                for p in (probs if a.warn else shown):
                    print("   ", p)
            elif m.source in ("bh", "es", "versus"):
                print(f"{m.name}: clean")
        if m.source in ("bh", "es", "versus"):
            bad += sum(p.level == "error" for p in probs)
        if m.source == "es":
            # (the Emerald Sun maps are held to the design-quality rules too: DQ.. and SP.. findings fail, `--rule` or the map's own comment cannot waive them)
            bad += sum(p.rule.startswith(("DQ", "SP")) for p in probs)
        if out and (probs or m.source in ("bh", "es", "versus")):
            render.draw_map(m, probs).save(out / f"{m.name.replace(' ', '_')}.png")
    if a.json:
        print(json.dumps(report, indent=1))
    else:
        util.say(f"maps lint {a.source}: {len(maps)} maps, {bad} errors in tangoAW2's maps" + (f"; pictures in {out}" if out else ""))
    return 1 if bad else 0


def gen(a):
    """Run the specs, write their text maps, build `src/es_map_data.rs` with bhmap.py --campaign es (tile joins checked as for the BH maps)."""
    sys.path.insert(0, str(cfg.DEVKIT))
    from ..esmaplib import load_spec, specs, ES_DIR
    bad = 0
    for p in specs():
        if a.map and p.stem not in a.map:
            continue
        m = load_spec(p)
        if a.check:
            f = ES_DIR / f"{m.name}.txt"
            if not f.exists() or f.read_text() != m.text():
                print(f"{m.name}: the text map differs from its spec (run aw2dev maps gen)")
                bad += 1
            continue
        m.write()
    if a.check or a.no_build:
        return 1 if bad else 0
    five = cfg.REPO / "tango-gamesupport-aw2" / "five"
    r = subprocess.run([sys.executable, str(five / "bhmap.py"), "--campaign", "es", str(cfg.aw2_rom())], cwd=cfg.REPO)
    return r.returncode


def rules_table(a):
    load, rules, render = _lib()
    srcs = {"aw2": load.aw2_maps(), "ds": load.ds_maps(), "versus": load.versus_maps(), "bh": load.bh_maps(), "es": load.es_maps()}
    hits = {}
    for s, ms in srcs.items():
        c = collections.defaultdict(set)
        for m in ms:
            for p in rules.lint(m):
                c[p.rule].add(m.name)
        hits[s] = c
    if a.md:
        print("| Rule | Level | What | AW2 (%d maps) | DS (%d) | Versus (%d) | BH (%d) | ES (%d) |" % tuple(len(srcs[s]) for s in srcs))
        print("|---|---|---|---|---|---|---|---|")
    for r, (lv, text) in rules.RULES.items():
        cols = [f"{len(hits[s].get(r, ()))}" for s in srcs]
        if a.md:
            print(f"| {r} | {lv} | {text} | " + " | ".join(cols) + " |")
        else:
            print(f"{r:5} {lv:5} " + "  ".join(f"{s}:{c}" for s, c in zip(srcs, cols)) + "   " + text)
    return 0


def _bh_at(rev):
    """The BH maps as they were at git REV (files read with `git show` into a temp folder)."""
    load, rules, render = _lib()
    d = Path(tempfile.mkdtemp(prefix="aw2maps_"))
    names = cfg.git("ls-tree", "--name-only", rev, "tango-gamesupport-aw2/five/bh/").split()
    files = []
    for n in names:
        if Path(n).name.startswith("bh") and n.endswith(".txt"):
            p = d / Path(n).name
            p.write_text(cfg.git("show", f"{rev}:{n}"))
            files.append(p)
    return load.bh_maps(files=sorted(files))


def compare(a):
    from PIL import Image, ImageDraw
    load, rules, render = _lib()
    old = {m.name: m for m in _bh_at(a.base)}
    new = {m.name: m for m in load.bh_maps()}
    out = Path(a.out) if a.out else cfg.work("maps", "compare")
    out.mkdir(parents=True, exist_ok=True)
    changed = 0
    for name, n in new.items():
        o = old.get(name)
        if o is None:
            continue
        cells = [(x, y) for y in range(n.h) for x in range(n.w) if y < o.h and x < o.w and o.tiles[y][x] != n.tiles[y][x]]
        units = [u for u in n.units if u not in o.units] + [u for u in o.units if u not in n.units]
        if not cells and not units and (o.w, o.h) == (n.w, n.h):
            continue
        changed += 1
        po, pn = rules.lint(o), rules.lint(n)
        io, im = render.draw_map(o, po, legend=False, title=f"{name} before: {sum(p.level == 'error' for p in po)} errors"), \
            render.draw_map(n, pn, legend=False, title=f"{name} after: {sum(p.level == 'error' for p in pn)} errors")
        d = ImageDraw.Draw(im)
        for x, y in cells:
            d.rectangle([x * 16 + 1, y * 16 + 22 + 1, x * 16 + 14, y * 16 + 22 + 14], outline=(255, 255, 255), width=1)
        sheet = Image.new("RGB", (io.width + im.width + 8, max(io.height, im.height)), (0, 0, 0))
        sheet.paste(io, (0, 0))
        sheet.paste(im, (io.width + 8, 0))
        sheet.save(out / f"{name}.png")
        print(f"{name}: {len(cells)} tiles changed, errors {sum(p.level == 'error' for p in po)} -> {sum(p.level == 'error' for p in pn)}")
    util.say(f"{changed} maps changed; pictures in {out}")
    return 0


def boot(a):
    tests = cfg.REPO / "tools" / "aw2test" / "run.py"
    out = Path(a.out) if a.out else cfg.work("maps", "boot")
    out.mkdir(parents=True, exist_ok=True)
    _bases()
    env = dict(os.environ, AW2TEST_REVIEW_DIR=str(out))
    rc = 0
    keys = [f"bh_review_m{n}$" for n in a.mission] if a.mission else ["bh_review_m"]
    for k in keys:
        r = subprocess.run([sys.executable, str(tests), "-k", k], env=env, cwd=cfg.REPO)
        rc = rc or r.returncode
    util.say(f"pictures in {out}")
    return rc


def _bases():
    """tools/aw2test wants a base save (read only); use the pinned copy in its out/ folder, never the player's file (made from a checkout's base.sav)."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    out = cfg.REPO / "tools" / "aw2test" / "out"
    if (out / "base-clean.sav").exists():
        return
    for cand in (Path.home() / "tangoAW2" / "tools" / "aw2test" / "out" / "base.sav", Path.home() / "tangoAW2-hires" / "tools" / "aw2test" / "out" / "base.sav"):
        if cand.exists():
            from aw2test import paths
            out.mkdir(parents=True, exist_ok=True)
            (out / "base-clean.sav").write_bytes(paths._profile_only(cand.read_bytes()))
            (out / "base-full.sav").write_bytes(cand.read_bytes())
            return
