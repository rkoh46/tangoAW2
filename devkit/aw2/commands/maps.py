"""aw2dev maps: map integrity (docs/dev/map-lint.md, skill aw2-map-lint).

  maps gen [--map es01 ..] [--check]  the Emerald Sun Campaign's text maps from their specs (five/es/spec/esNN.py), then es_map_data.rs (bhmap.py --campaign es)
  maps lint [--source bh|es|versus|aw2|ds|all] [--map NAME ...] [--rule ID ...] [--png DIR] [--json]
                                   check maps for unfinished rivers, orphan sea/shoal, broken joins, bad bridges and roads, pipes, units on terrain
                                   they cannot enter, unreachable properties, HQs with no access, tiles drawn as garbage; exit 1 on an error in
                                   bh / versus maps (aw2 and ds are the reference: their hits are only reported)
  maps rules [--md]                every rule with its hits in AW2's own maps, Dual Strike's, tangoAW2's Versus maps and the BH Campaign's (what the games allow)
  maps compare --base REV [--out DIR]   BH maps at git REV against the working tree: changed cells and before/after pictures
  maps boot [--mission N ...]      enter BH missions in the offline harness and photograph them (tools/aw2test bh_review_m*); the real game's map picture
  maps study [DIR] [--source es bh aw2 ds versus] [--png DIR] [--json FILE]
                                   design statistics (docs/dev/map-design.md): AWBW grids in DIR (never committed) and/or our own maps; per map and per set
"""
import collections, json, os, re, subprocess, sys, tempfile
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
    a.add_argument("--principles", action="store_true", help="print each map's design measures and MD findings (docs/dev/map-design.md; no ROM needed)")
    a.set_defaults(fn=gen)
    a = ms.add_parser("rules", help="the rules and what the games' own maps do under each")
    a.add_argument("--md", action="store_true")
    a.set_defaults(fn=rules_table)
    a = ms.add_parser("compare", help="BH (or Emerald Sun) maps at a git revision against the working tree")
    a.add_argument("--base", required=True)
    a.add_argument("--source", default="bh", choices=["bh", "es"])
    a.add_argument("--out", help="folder for the before/after pictures")
    a.add_argument("--sheet", metavar="FILE", help="also one sheet of every changed map, before beside after, half size")
    a.set_defaults(fn=compare)
    a = ms.add_parser("ports", help="every port of the maps (map, army, cell, the sea beside it) with its status (PT01): a table")
    a.add_argument("--source", default="all", choices=["bh", "es", "versus", "all"])
    a.set_defaults(fn=ports_table)
    a = ms.add_parser("render-check", help="the game's own pictures of maps against the drawings the games use for river, shoal, bridge and coast tiles (RN01)")
    a.add_argument("--source", default="es", choices=["es", "bh", "versus"], help="the maps to check (their pictures: --pictures)")
    a.add_argument("--pictures", metavar="DIR", help="the folder of m<N>_full.png pictures of the maps to check (default: es devkit/work/campaign/es/review_raw, bh devkit/work/maps/boot)")
    a.add_argument("--corpus", metavar="DIR", nargs="*", help="the reference pictures (default: devkit/work/maps/boot, the BH Campaign's, and the other maps of the check itself)")
    a.set_defaults(fn=render_check)
    a = ms.add_parser("study", help="design statistics per map and per set: AWBW grids from a folder and/or our maps (docs/dev/map-design.md)")
    a.add_argument("dir", nargs="?", help="a folder of AWBW study files (`# <id> players=N size=WxH ...` + CSV rows of AWBW terrain ids)")
    a.add_argument("--source", nargs="*", default=[], choices=["es", "bh", "aw2", "ds", "versus"], help="our maps to study too")
    a.add_argument("--map", nargs="*", help="only these map names")
    a.add_argument("--png", metavar="DIR", help="a picture of each map (our colours) here: keep AWBW pictures in a scratchpad")
    a.add_argument("--json", metavar="FILE", help="write every row and the summaries as JSON")
    a.add_argument("--rows", action="store_true", help="print one line per map (default: the summaries only)")
    a.set_defaults(fn=study)
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
        shown = [p for p in probs if a.warn or p.level == "error" or m.source in ("aw2", "ds") or (m.source == "es" and (p.rule.startswith(("DQ", "SP", "MD")) or p.rule in ("PP03", "PP04")))]
        report[m.name] = [str(p) for p in probs]
        if not a.json:
            if probs:
                print(f"{m.name} ({m.source} {m.w}x{m.h}): {sum(p.level == 'error' for p in probs)} errors, {sum(p.level == 'warn' for p in probs)} warnings")
                for p in (probs if a.warn else shown):
                    print("   ", p)
            elif m.source in ("bh", "es", "versus"):
                print(f"{m.name}: clean")
        if m.source in ("bh", "es", "versus"):
            known = dict(rules.KNOWN.get(m.name, {})) if m.source != "es" else {}
            for p in probs:
                if p.level != "error":
                    continue
                if known.get(p.rule, 0) > 0:
                    known[p.rule] -= 1          # (a finding the user has not approved changing: reported below, not failing)
                    continue
                bad += 1
        if m.source == "es":
            # (the Emerald Sun maps are held to the design-quality rules too: DQ.. and SP.. findings fail, `--rule` or the map's own comment cannot waive them)
            bad += sum(p.rule.startswith(("DQ", "SP", "MD")) or p.rule in ("PP03", "PP04") for p in probs)
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
        if a.principles:
            from ..maplint import study as st
            r = st.measure(m.study())
            print(f"   {m.name}: {r['props']} properties, {r['props_per100_land']} per 100 land, farthest ground {r['prop_gap']}, plain {r['t_plain']:.0%} wood {r['t_wood']:.0%} "
                  f"mountain {r['t_mountain']:.0%} road {r['t_road']:.0%}, river run {r['river_run']}, approach roads {r.get('road_lanes')}, middle {r.get('contested_centre')}")
            for p in m.principles():
                print("   ", p)
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


def _bh_at(rev, source="bh"):
    """The BH (or Emerald Sun) maps as they were at git REV (files read with `git show` into a temp folder)."""
    load, rules, render = _lib()
    d = Path(tempfile.mkdtemp(prefix="aw2maps_"))
    names = cfg.git("ls-tree", "--name-only", rev, f"tango-gamesupport-aw2/five/{source}/").split()
    files = []
    for n in names:
        if Path(n).name.startswith(source) and n.endswith(".txt"):
            p = d / Path(n).name
            p.write_text(cfg.git("show", f"{rev}:{n}"))
            files.append(p)
    return (load.es_maps if source == "es" else load.bh_maps)(files=sorted(files))


def compare(a):
    from PIL import Image, ImageDraw
    load, rules, render = _lib()
    old = {m.name: m for m in _bh_at(a.base, a.source)}
    new = {m.name: m for m in (load.es_maps() if a.source == "es" else load.bh_maps())}
    sheets = []
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
        def label(m, ps, when):
            md = sum(p.rule.startswith("MD") for p in ps)
            from ..maplint import study as st
            r = st.measure(st.from_mapdata(m))
            return (f"{name} {when}: {sum(p.level == 'error' for p in ps)} errors, {md} MD; {r['props']} props ({r['props_per100_land']}/100 land), "
                    f"gap {r['prop_gap']}, plain {r['t_plain']:.0%}")
        io, im = render.draw_map(o, po, legend=False, title=label(o, po, "before")), render.draw_map(n, pn, legend=False, title=label(n, pn, "after"))
        d = ImageDraw.Draw(im)
        for x, y in cells:
            d.rectangle([x * 16 + 1, y * 16 + 22 + 1, x * 16 + 14, y * 16 + 22 + 14], outline=(255, 255, 255), width=1)
        sheet = Image.new("RGB", (io.width + im.width + 8, max(io.height, im.height)), (0, 0, 0))
        sheet.paste(io, (0, 0))
        sheet.paste(im, (io.width + 8, 0))
        sheet.save(out / f"{name}.png")
        sheets.append(sheet)
        print(f"{name}: {len(cells)} tiles changed, errors {sum(p.level == 'error' for p in po)} -> {sum(p.level == 'error' for p in pn)}")
    if a.sheet and sheets:
        small = [s_.resize((s_.width // 2, s_.height // 2)) for s_ in sheets]
        big = Image.new("RGB", (max(s_.width for s_ in small), sum(s_.height + 6 for s_ in small)), (0, 0, 0))
        y = 0
        for s_ in small:
            big.paste(s_, (0, y))
            y += s_.height + 6
        big.save(a.sheet)
    util.say(f"{changed} maps changed; pictures in {out}" + (f"; the sheet {a.sheet}" if a.sheet else ""))
    return 0


def ports_table(a):
    """The port audit: one row per port of the ES, BH and Versus maps: map, owner (army digit, N neutral), cell, the sea body beside it, and OK or the PT01 finding."""
    load, rules, render = _lib()
    rows, bad = [], 0
    for s in (["bh", "es", "versus"] if a.source == "all" else [a.source]):
        for m in _maps(load, s):
            G = rules.Grid(m)
            hits = {(p.x, p.y): p.msg for p in rules.lint(m, {"PT01"})}
            lava = load.look_of(m.name) == 3
            for x, y in G.cells("Pp"):
                owner = G.T.owner(G.t[y][x])
                rows.append((s, m.name, "N" if not owner else str(owner), (x, y), "lava" if lava else "sea", hits.get((x, y))))
    print(f"{'src':7}{'map':16}{'army':5}{'cell':10}{'water':6}status")
    for s, n, o, c, w, h in rows:
        print(f"{s:7}{n:16}{o:5}{str(c):10}{w:6}{'OK' if not h else 'FIX: ' + h}")
        bad += bool(h)
    util.say(f"maps ports: {len(rows)} ports, {bad} lead nowhere")
    return 0


def render_check(a):
    """RN01: see maplint/render_check.py."""
    sys.path.insert(0, str(cfg.DEVKIT))
    from ..maplint import load, render_check as rc
    maps = {"es": load.es_maps, "bh": load.bh_maps, "versus": load.versus_maps}[a.source]()
    check_dir = a.pictures or str(cfg.work("campaign", "es", "review_raw") if a.source == "es" else cfg.work("maps", "boot"))
    corpus_dirs = a.corpus or [str(cfg.work("maps", "boot"))]
    bh = [(m, rc.picture_for(corpus_dirs, m.name)) for m in load.bh_maps() if not re.search(r"[a-z]$", m.name)]
    bh = [(m, p) for m, p in bh if p]
    todo = [(m, rc.picture_for([check_dir], m.name)) for m in maps]
    todo = [(m, p) for m, p in todo if p]
    if not todo:
        util.die(f"no pictures of the {a.source} maps in {check_dir} (aw2dev campaign sheets / maps boot)")
    bad = 0
    for m, p in todo:
        # (the reference is the corpus minus the map itself: a map is never its own witness)
        ref = rc.learn([(mm, pp) for mm, pp in bh + [x for x in todo if a.source == "es"] if mm.name != m.name])
        probs = rc.check(m, p, ref)
        if probs is None:
            print(f"{m.name}: the picture {p.name} is not {m.w * 16}x{m.h * 16}: skipped")
            continue
        for x, y, t in probs:
            print(f"{m.name} RN01 error ({x},{y}) {t}")
        bad += len(probs)
        if not probs:
            print(f"{m.name}: clean")
    util.say(f"maps render-check {a.source}: {len(todo)} pictures, {bad} drawings no game picture shows")
    return 1 if bad and a.source == "es" else 0


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


STUDY_COLS = [("props_per100", "prop/100"), ("prop_spacing", "spc"), ("funds_day1", "funds"), ("funds_sym", "sym"), ("hq_dist", "hqd"), ("base_dist", "based"),
              ("base_inf_days", "infd"), ("lanes", "lanes"), ("road_lanes", "roads"), ("front_width", "front"), ("choke", "choke"), ("mid_cover", "cover"), ("forward_bases", "fwdB"),
              ("t_plain", "plain"), ("t_wood", "wood"), ("t_mountain", "mtn"), ("t_road", "road"), ("t_sea", "sea"), ("beach_share", "beach"), ("dead_share", "dead"),
              ("contested_centre", "ctr")]


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "y" if v else "n"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:.0f}"
    return str(v)


def study(a):
    """The design study (maplint/study.py): measure each map, print the sets' medians and spreads, optionally pictures and JSON."""
    load, rules, render = _lib()
    from ..maplint import study as st
    sets = {}
    if a.dir:
        d = Path(a.dir)
        if not d.is_dir():
            util.die(f"no such folder: {d}")
        sms = st.load_dir(d)
        for sm in sms:
            n = sm.meta.get("players", 2)
            sets.setdefault("awbw_2p" if n == 2 else f"awbw_{n}p", []).append(sm)
    for s in a.source:
        sets[s] = [st.from_mapdata(m) for m in _maps(load, s)]
    if not sets:
        util.die("nothing to study: give a folder of AWBW grids and/or --source")
    if a.map:
        sets = {k: [sm for sm in v if sm.name in a.map or sm.meta.get("title") in a.map] for k, v in sets.items()}
    out = Path(a.png) if a.png else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    rows, summ = {}, {}
    for k, sms in sets.items():
        rows[k] = []
        for sm in sms:
            r = st.measure(sm)
            r["name"], r["title"] = sm.name, sm.meta.get("title", sm.name)
            rows[k].append(r)
            if out:
                notes = [f"{r['title']}"] + [f"{lab}: {_fmt(r.get(key))}" for key, lab in STUDY_COLS]
                st.draw(sm, title=f"{r['title']} ({sm.name}) {sm.w}x{sm.h}", notes=notes).save(out / f"{k}_{sm.name}.png")
        summ[k] = st.summary(rows[k])
    if a.rows:
        print(f"{'set':8}{'map':24}" + "".join(f"{lab:>7}" for _, lab in STUDY_COLS))
        for k, rs in rows.items():
            for r in rs:
                print(f"{k[:8]:8}{r['title'][:23]:24}" + "".join(f"{_fmt(r.get(key)):>7}" for key, _ in STUDY_COLS))
    keys = st.KEYS + st.FLAGS + ["has_tower", "has_silo", "has_pipe", "has_airport", "has_port", "has_river", "has_lab", "flank_lanes", "forward_base"]
    print(f"\n{'measure (p10 / median / p90; flags: share of maps)':28}" + "".join(f"{k + f' ({len(rows[k])})':>22}" for k in rows))
    for key in keys:
        cells = []
        for k in rows:
            v = summ[k].get(key)
            cells.append("-" if v is None else (" / ".join(_fmt(x) for x in v) if isinstance(v, tuple) else _fmt(v)))
        print(f"{key:28}" + "".join(f"{c:>22}" for c in cells))
    # the design-principle rules (maplint/principles.py) on every set: how many maps trip each
    from ..maplint import principles
    hits = {k: collections.Counter() for k in rows}
    for k, sms in sets.items():
        for sm in sms:
            for r in sorted({p.rule for p in principles.check_study(sm)}):
                hits[k][r] += 1
    print(f"\n{'rule (maps that trip it)':28}" + "".join(f"{k + f' ({len(rows[k])})':>22}" for k in rows))
    for r in sorted(rules.RULES):
        if r.startswith("MD"):
            print(f"{r:28}" + "".join(f"{hits[k][r]:>22}" for k in rows))
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "summary": summ, "md_hits": hits}, indent=1, default=str))
    util.say(f"maps study: {sum(len(v) for v in rows.values())} maps" + (f"; pictures in {out}" if out else ""))
    return 0


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
