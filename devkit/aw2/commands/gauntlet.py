"""aw2dev gauntlet: the Gauntlet game mode in the offline harness (docs/dev/gauntlet-mode.md).

  gauntlet start [--co N] [--out DIR]   boots the harness straight into the mode (title, Select Mode, GAUNTLET, the map selector, the single army screen with CO N, the battle) and leaves a picture of each screen on the way:
                                        1_wheel, 2_map_selector, 3_army_screen, 4_army_screen_co, 5_setup, 6_first_turn (PNG, in DIR or the run's folder; the command fails when one is missing);
                                        N is an AW2 CO id (default 1 Andy; 93 Aria, 92 Asuka)
  gauntlet army-sheet [--map NN ...]    the army screen of the chosen maps (default: six) in three states (as it opens, CO changed, R pressed) in the three looks, one sheet `army_screen_sheet.png` (`gauntlet_army_pictures`)
  gauntlet faces [--map NN ...]         each CO's dialogue-box face next to the same CO on the army screen, one sheet `faces_vs_army_screen.png` (`gauntlet_faces_vs_army_screen` + tools/aw2test/compose_faces.py)
  gauntlet new-map NN "Name" [--apply]  scaffolds `five/gauntlet/spec/gauntlet_NN.py` and prints (or with --apply inserts) the `gauntlet_mode.rs` mission stub; refuses a duplicate id or a map past the limit of 32
  gauntlet cos                          every map's enemy COs in order, the reused ones with the allowed exceptions (fails on an unnamed repeat), the COs no map uses yet
  gauntlet rout-sheet [--out FILE]      Cinder Sea's first rout (before, during, after) in the real app in the three looks (AW2 graphics, Dual Strike graphics, the tilted map): `gauntlet_rout_pictures`
                                        saves three console checkpoints, the app boots each (needs `cargo build --release -p tango`) and a sheet is composed (rows: looks, columns: moments)
  gauntlet maps-pictures [--out DIR]    every map added after Cinder Sea and Iron Crown played with real captures, per look (AW2, DS + tilt, DS flat): `gauntlet_lines_pictures` sheets in DIR
  gauntlet order                        the maps in the selector's order (fewest enemy COs first), from `aw2test/gauntlet_maps.py` and `crate::gauntlet_mode::order`
  gauntlet score [--markdown]           every map's par days (days per line, `crate::gauntlet_mode::par_days`) and what a quick, a steady and a slow run score before the rework and now (total and rank): AW2's
                                        Speed against the par, Power against an average line's builds (`aw2test/gauntlet_score.py`: the ROM's formulas; the real check is `-k gauntlet_score`)
  gauntlet test                         the Gauntlet's regression tests (`run.py -k gauntlet_mode --mode ds`)
"""
import os, subprocess, sys, tempfile
from .. import cfg, util


def register(sub):
    g = sub.add_parser("gauntlet", help="the Gauntlet mode: boot into it with pictures, run its tests (docs/dev/gauntlet-mode.md)")
    gs = g.add_subparsers(dest="gauntletcmd", required=True)
    a = gs.add_parser("start", help="title -> GAUNTLET -> map selector -> army screen -> the battle, with a picture of each screen (fails if one is missing)")
    a.add_argument("--co", type=int, default=1, help="AW2 CO id to pick (default 1, Andy; 93 Aria, 92 Asuka)")
    a.add_argument("--out", help="folder for the pictures (default: the run's own folder, printed)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=start)
    a = gs.add_parser("test", help="run the Gauntlet mode's tests")
    a.set_defaults(fn=test)
    a = gs.add_parser("maps-pictures", help="the new maps' picture sheets in the three looks")
    a.add_argument("--out", help="folder for the sheets (default: devkit/work/gauntlet/maps)")
    a.set_defaults(fn=maps_pictures)
    a = gs.add_parser("army-sheet", help="the army screen of chosen maps in three states and three looks, as one sheet")
    a.add_argument("--map", nargs="*", metavar="NN", help="map numbers (gauntlet_NN); default the six of the picture test")
    a.add_argument("--out", help="folder (default devkit/work/gauntlet/army)")
    a.set_defaults(fn=army_sheet)
    a = gs.add_parser("faces", help="the dialogue-box face of each CO beside that CO on the army screen, as one sheet")
    a.add_argument("--map", nargs="*", metavar="NN", help="map numbers (gauntlet_NN); default every registered map")
    a.add_argument("--out", help="folder (default devkit/work/gauntlet/faces)")
    a.set_defaults(fn=faces)
    a = gs.add_parser("new-map", help="scaffold the next map: its spec file and the gauntlet_mode.rs stub (refuses a duplicate id or past 32 maps)")
    a.add_argument("nn", metavar="NN", help="the map number (the next free one; key gauntlet_NN)")
    a.add_argument("name")
    a.add_argument("--apply", action="store_true", help="insert the mission stub into gauntlet_mode.rs and its name into def() (default: print it)")
    a.set_defaults(fn=new_map)
    a = gs.add_parser("cos", help="the enemy COs of every map, reused ones with the allowed exceptions, and the COs no map uses")
    a.set_defaults(fn=cos)
    a = gs.add_parser("score", help="par days and example scores per map (the Gauntlet's scoring rework)")
    a.add_argument("--markdown", action="store_true", help="print the table as Markdown")
    a.set_defaults(fn=score)
    a = gs.add_parser("order", help="the maps in the selector's order")
    a.set_defaults(fn=order)
    a = gs.add_parser("rout-sheet", help="the rout's before/during/after in the real app, in all three looks, as one sheet")
    a.add_argument("--out", help="the sheet's PNG (default: devkit/work/gauntlet/rout_sheet.png)")
    a.set_defaults(fn=rout_sheet)


START_PICTURES = ["1_wheel", "2_map_selector", "3_army_screen", "4_army_screen_co", "5_setup", "6_first_turn"]
MODE_RS = cfg.REPO / "tango-gamesupport-aw2" / "src" / "gauntlet_mode.rs"
UI_RS = cfg.REPO / "tango-gamesupport-aw2" / "src" / "gauntlet_ui.rs"
SPEC_DIR = cfg.REPO / "tango-gamesupport-aw2" / "five" / "gauntlet" / "spec"


def _run(extra_env, args):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    env = dict(os.environ, **extra_env)
    return subprocess.run([sys.executable, str(run)] + args, env=env, cwd=cfg.REPO, text=True)


def start(a):
    out = a.out or tempfile.mkdtemp(prefix="gauntlet_start_")
    r = _run({"AW2TEST_GAUNTLET_CO": str(a.co), "AW2TEST_GAUNTLET_OUT": out}, ["-k", "gauntlet_tool_start", "--mode", "ds"] + (["-v"] if a.verbose else []))
    names = sorted(f for f in os.listdir(out)) if os.path.isdir(out) else []
    util.say("pictures:", out, names)
    missing = [n for n in START_PICTURES if n + ".png" not in names]
    if missing and not r.returncode:
        util.say("MISSING pictures:", missing)
        return 1
    return r.returncode


def maps_pictures(a):
    out = a.out or str(cfg.work("gauntlet") / "maps")
    os.makedirs(out, exist_ok=True)
    r = _run({"AW2TEST_REVIEW_DIR": out}, ["-k", "gauntlet_lines_pictures", "--mode", "ds", "-j", "4"])
    util.say("sheets:", out)
    return r.returncode


def order(a):
    """The selector's order: by the number of enemy COs (a later stage's too), ties in the missions' order: the keys of the text maps and the harness registry tell it."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import gauntlet as ga
    for row, title in enumerate(ga.SELECTOR_TITLES):
        util.say(f"{row + 1}. {title}: mission {ga.SELECTOR_ORDER[row]}, {ga.SELECTOR_ENEMIES[row]} enemy COs")
    return 0


def test(a):
    return _run({}, ["-k", "gauntlet", "--mode", "ds"]).returncode


def score(a):
    """The par days and the example runs' scores (aw2test/gauntlet_score.py, written from the ROM's score code; `crate::gauntlet_mode::PAR_PER_LINE` and `PAR_OVERRIDES` are read from the source)."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import gauntlet_score as gs
    per, over = gs.par_rules()
    util.say(f"par = {per} days a line (overrides {over}); Speed 100 up to par, 0 at 4 x par; Power's enemy builds divided by the lines; Technique and rank as AW2's")
    util.say("runs (days, most kills in a turn, enemy builds, units built/lost): " + "; ".join(f"{n} on N lines: {gs.SCENARIOS[n](1)} per line" for n in gs.SCENARIOS))
    if a.markdown:
        util.say("| map | lines | par before | par now | " + " | ".join(gs.SCENARIOS) + " |")
        util.say("|---|---|---|---|" + "---|" * len(gs.SCENARIOS))
        for key, title, n, old, new, res in gs.table():
            util.say(f"| {title} | {n} | {old} | {new} | " + " | ".join(f"{gs.fmt(res[s][0])} -> {gs.fmt(res[s][1])}" for s in gs.SCENARIOS) + " |")
    else:
        for line in gs.lines():
            util.say(line)
    return 0



LOOKS = [("AW2 graphics", dict(ds=True, graphics=False)), ("DS graphics, no tilt", dict(ds=True, graphics=True)), ("DS graphics + tilt", dict(ds=True, graphics=True, tilt=True))]
MOMENTS = [("before the capture", "rout_before"), ("while the units go", "rout_during"), ("after", "rout_after")]


def rout_sheet(a):
    """The rout in the real app's own pictures (never the full screen: the app's screenshot is its game window)."""
    from PIL import Image, ImageDraw
    from ..armyskinlib import look as lk
    work = cfg.work("gauntlet")
    work.mkdir(parents=True, exist_ok=True)
    ck = lk.CKPT()
    ck.mkdir(parents=True, exist_ok=True)
    r = _run({"AW2TEST_ROUT_CKPT": str(ck)}, ["-k", "gauntlet_rout_pictures", "--mode", "ds"])
    if r.returncode:
        return r.returncode
    rows = []
    for title, kw in LOOKS:
        row = []
        for _, name in MOMENTS:
            shot = work / f"{name}_{title.split()[0].lower()}_{'tilt' if kw.get('tilt') else 'flat'}.png"
            lk.look(name, str(shot), scale=1 if kw.get("tilt") else None, **kw)
            row.append(Image.open(shot).convert("RGB"))
        rows.append((title, row))
    w, h = rows[0][1][0].size
    k = 2
    pad, head = 6, 22
    sheet = Image.new("RGB", (pad + 3 * (w * k + pad), head + len(rows) * (h * k + head + pad)), (24, 24, 32))
    dr = ImageDraw.Draw(sheet)
    for j, (m, _) in enumerate(MOMENTS):
        dr.text((pad + j * (w * k + pad), 4), m, fill=(255, 255, 255))
    for i, (title, row) in enumerate(rows):
        y = head + i * (h * k + head + pad)
        dr.text((pad, y), title, fill=(255, 220, 80))
        for j, im in enumerate(row):
            sheet.paste(im.resize((w * k, h * k), Image.NEAREST), (pad + j * (w * k + pad), y + 14))
    out = a.out or str(work / "rout_sheet.png")
    sheet.save(out)
    util.say("sheet:", out)
    return 0


# --- the map list as the Rust source gives it (no build needed) ---------------------------------------------------------------------

def _last(path):
    """`crate::co_new::ASUKA` -> ASUKA."""
    return path.split("::")[-1].strip()


def read_maps(text):
    """[(fn name, key, title, [enemy CO names in order])] of the missions of `def()`, from gauntlet_mode.rs's text."""
    import re
    m = re.search(r"let mut missions = vec!\[(.*?)\];", text, re.S)
    out = []
    for fn in re.findall(r"(\w+)\(\)", m.group(1) if m else ""):
        b = re.search(r"\nfn " + fn + r"\(\) -> MissionDef \{(.*?)\n\}\n", text, re.S)
        if not b:
            continue
        k = re.search(r'MissionDef::new\("(gauntlet_\w+)", "([^"]+)"', b.group(1))
        out.append((fn, k.group(1), k.group(2), [_last(c) for c in re.findall(r"CoSpec::Fixed\(([\w:]+)\)", b.group(1))]))
    return out


def read_exceptions(text):
    """{CO name: [keys]}: the repeats the unit test `no_two_maps_share_an_enemy_co_but_the_named_exceptions` allows."""
    import re
    m = re.search(r"let allowed: &\[\(u8, &\[&str\]\)\] = &\[(.*?)\n        \];", text, re.S)
    return {_last(c): re.findall(r'"(gauntlet_\w+)"', ks) for c, ks in re.findall(r"\(([\w:]+), &\[(.*?)\]\)", m.group(1) if m else "", re.S)}


def read_roster(text):
    import re
    m = re.search(r"pub const ROSTER: \[\(u8, bool\); \d+\] = \[(.*?)\n\];", text, re.S)
    return [_last(c) for c in re.findall(r"\(([\w:]+), (?:true|false)\)", m.group(1) if m else "")]


def max_maps():
    import re
    return int(re.search(r"pub const MAX_MAPS: usize = (\d+);", UI_RS.read_text()).group(1))


def cos_report(maps, exceptions, roster):
    """(lines, bad): the per-map CO lists, the reuse table and the unused COs."""
    lines, seen = [], {}
    for _, key, title, enemies in maps:
        lines.append(f"{key} {title}: " + ", ".join(enemies))
        for c in enemies:
            seen.setdefault(c, []).append(key)
    bad = []
    for c, keys in sorted(seen.items()):
        if len(keys) > 1:
            ok = exceptions.get(c) == keys
            lines.append(f"reused: {c} on {', '.join(keys)} ({'allowed exception' if ok else 'NOT an allowed exception'})")
            if not ok:
                bad.append(c)
    for c, keys in exceptions.items():
        if c not in seen or len(seen[c]) < 2:
            lines.append(f"stale exception: {c} is named for {keys} but is not reused there")
    unused = [c for c in roster if c not in seen]
    lines.append(f"{len(unused)} of {len(roster)} COs fight on no map yet: " + ", ".join(unused))
    return lines, bad


def cos(a):
    text = MODE_RS.read_text()
    maps = read_maps(text)
    lines, bad = cos_report(maps, read_exceptions(text), read_roster(text))
    for l in lines:
        util.say(l)
    util.say(f"{len(maps)} maps (room for {max_maps()}): " + ("every repeat is a named exception" if not bad else f"unnamed repeats: {bad}"))
    return 1 if bad else 0


SPEC_TEMPLATE = '''"""Gauntlet {nn}, {name} (docs/dev/gauntlet.md, docs/dev/gauntlet-mode.md "Adding a map"): TODO the idea in two lines, the lines (enemy COs) in the order they come, the armies.
Keep to about 110 properties (Neon Row's 150 stalled the computer's turn on day 1; 108 is clean). Every enemy CO must be one no other map uses (`aw2dev gauntlet cos`)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *

W, H = 40, 24      # TODO (at most 46 x 28)
# the HQs: army 1.. the lines in the order they come, the player's army last (TODO)
HQS = {{"1": (30, 12), "2": (3, 12)}}


def build():
    m = Canvas("gauntlet_{nn}", W, H, campaign="gauntlet")
    # TODO terrain, then m.header(armies=.., colours=.., team=(2, .., 1), objective=[..], zones=[..], hidden=[..], comment=".."),
    # HQs, properties, units (m.spread(..)); copy the nearest existing spec (gauntlet_08.py is a small sea map, gauntlet_12.py a five-army one).
    raise NotImplementedError("gauntlet_{nn}: fill the spec in")
'''

RUST_TEMPLATE = '''
/// {name}: TODO one line.
fn {fn}() -> MissionDef {{
    let mut m = MissionDef::new("gauntlet_{nn}", "{name}");
    m.objective = "TODO";
    m.map = MapSrc::Built("gauntlet_{nn}");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::ANDY)).team(2).funds(9000), // TODO the first line's CO: one no other map uses (`aw2dev gauntlet cos`)
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::OLAF)).team(2).funds(0),   // TODO the next line
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(20000),
    ];
    m.units = crate::bh_ai::built_units("gauntlet_{nn}");
    m.rank_days = 30;
    let lines = [
        Wire {{ army: 1, hq: (0, 0), zone: Rect::new(0, 0, 1, 1) }}, // TODO the HQ cell and the zone each line is hidden in
        Wire {{ army: 2, hq: (0, 0), zone: Rect::new(0, 0, 1, 1) }},
    ];
    wire(&mut m, &lines, vec![arrival(&lines, 1, chest::<2, 15000, 1000>, &[], Scene::new(vec![Line::say(co::ANDY, "TODO")]))]);
    m
}}
'''


def nn_of(nn):
    if not str(nn).isdigit() or not 1 <= int(nn) <= 99:
        raise ValueError(f"{nn!r} is not a map number (1..{max_maps()})")
    return f"{int(nn):02d}"


def plan_new_map(nn, name, text, spec_exists, limit):
    """(spec text, fn name, rust stub, new rust text) or raises ValueError for a duplicate id or past the limit."""
    import re
    nn = nn_of(nn)
    maps = read_maps(text)
    if int(nn) > limit:
        raise ValueError(f"gauntlet_{nn}: past the limit of {limit} maps (gauntlet_ui::MAX_MAPS; see docs/dev/gauntlet-mode.md \"The map list's room\")")
    if len(maps) >= limit:
        raise ValueError(f"already {len(maps)} maps: the limit is {limit}")
    if spec_exists or any(k == f"gauntlet_{nn}" for _, k, _, _ in maps):
        raise ValueError(f"gauntlet_{nn} exists already (its spec file or its mission): ids are never reused")
    fn = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not fn or fn[0].isdigit() or any(f == fn for f, _, _, _ in maps):
        raise ValueError(f"the name {name!r} gives the function name {fn!r}, which is unusable or taken")
    stub = RUST_TEMPLATE.format(nn=nn, name=name, fn=fn)
    i = text.index("pub fn def() -> CampaignDef")
    while text[:i].rstrip("\n").rsplit("\n", 1)[-1].startswith("///"):          # (the doc comment above def() stays with it)
        i = text[:i].rstrip("\n").rfind("\n") + 1
    new = text[:i].rstrip("\n") + "\n" + stub + "\n" + text[i:]
    new = re.sub(r"(let mut missions = vec!\[[^\]]*?\w+\(\))\]", lambda m: m.group(1) + f", {fn}()]", new, count=1)
    return SPEC_TEMPLATE.format(nn=nn, name=name), fn, stub, new


def new_map(a):
    try:
        nn = nn_of(a.nn)
        spec, fn, stub, new = plan_new_map(nn, a.name, MODE_RS.read_text(), (SPEC_DIR / f"gauntlet_{nn}.py").exists(), max_maps())
    except ValueError as e:
        util.say("refused:", e)
        return 1
    sp = SPEC_DIR / f"gauntlet_{nn}.py"
    sp.write_text(spec)
    util.say("created", sp.relative_to(cfg.REPO))
    if a.apply:
        MODE_RS.write_text(new)
        util.say(f"inserted `fn {fn}()` and added it to def()'s missions in tango-gamesupport-aw2/src/gauntlet_mode.rs")
    else:
        print(f"Add to tango-gamesupport-aw2/src/gauntlet_mode.rs (before `pub fn def()`), or run again with --apply on a clean checkout:\n{stub}")
        print(f"and add `{fn}()` to the missions vec in `def()`.")
    print(f"""Then, in order (docs/dev/gauntlet-mode.md "Adding a map"):
  1. fill the spec; `aw2dev maps gen --campaign gauntlet`; `aw2dev maps lint --source gauntlet`; about 110 properties, no more
  2. waves: `aw2dev maps wave gauntlet_{nn} --zone x0,y0,x1,y1 --kinds ...` (ships on a sea map by hand)
  3. fill the mission: enemy COs no other map uses (`aw2dev gauntlet cos`; a named exception needs the owner and a line in the `allowed` list of the unit test), wire/arrival/chest, scenes
  4. `text_of` in the Rust tests, `aw2test/gauntlet_maps.py`, `SELECTOR_ORDER` / `SELECTOR_TITLES` in `aw2test/gauntlet.py` (the order is by enemy count)
  5. `aw2dev gauntlet test`, `-k gauntlet_lines`, `aw2dev campaign scene-check`, then the pictures: `aw2dev gauntlet army-sheet --map {nn}`, `aw2dev gauntlet faces --map {nn}`, `aw2dev gauntlet maps-pictures`""")
    return 0


def _mission_of(nn):
    maps = read_maps(MODE_RS.read_text())
    keys = [k for _, k, _, _ in maps]
    return keys.index(f"gauntlet_{nn_of(nn)}")


def army_sheet(a):
    out = a.out or str(cfg.work("gauntlet") / "army")
    os.makedirs(out, exist_ok=True)
    env = {"AW2TEST_ARMY_PICS": out}
    if a.map:
        try:
            env["AW2TEST_ARMY_MISSIONS"] = ",".join(str(_mission_of(n)) for n in a.map)
        except ValueError:
            util.say("no such map in gauntlet_mode.rs:", a.map)
            return 1
    r = _run(env, ["-k", "gauntlet_army_pictures", "--mode", "ds"])
    util.say("sheet:", os.path.join(out, "army_screen_sheet.png"))
    return r.returncode


def faces(a):
    out = a.out or str(cfg.work("gauntlet") / "faces")
    os.makedirs(out, exist_ok=True)
    env = {"AW2TEST_FACES": out}
    if a.map:
        env["AW2TEST_FACES_MAPS"] = ",".join(f"gauntlet_{nn_of(n)}" for n in a.map)
    r = _run(env, ["-k", "gauntlet_faces_vs_army_screen", "--mode", "ds"])
    if r.returncode:
        return r.returncode
    sheet = os.path.join(out, "faces_vs_army_screen.png")
    r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "compose_faces.py"), out, sheet], cwd=cfg.REPO)
    util.say("sheet:", sheet)
    return r.returncode
