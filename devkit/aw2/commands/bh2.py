"""aw2dev bh2: the BH2 Campaign's map kit (docs/dev/bh2-maps.md, skill aw2-add-campaign).

  bh2 pictures [--out DIR]    m01.png .. (full map, fog off, units and labels, "MISSION N - Title" burned in), the fog views, act1_sheet.png, worldmap_flags.png
  bh2 sheets [--raw DIR] [--out DIR]  label the game's own pictures (`aw2dev maps boot --campaign bh2`): m0N.png, m01_fog.png, m04_front2.png, act1_game_sheet.png, act2_game_sheet.png
  bh2 scenes [--md]           the scene check: lint (keys used and resolvable) and every scene with its song; a story scene without music fails
  bh2 saves [--no-harness]    the folded BH2 save record: unit tests and the harness round trip (BH + Emerald Sun + BH2)
  bh2 prologue-sheet [--out PNG] [--no-run]  every page and box of the prologue, typed out, one frame each: a contact sheet and prologue_frames/NNN.png
  bh2 integration [--out PNG]  the proof sheet of the harness's frames (chooser, prologue, world map, a scene per act, Aria's CO select)
  bh2 silhouettes             the silhouette check (no two maps alike, no oval blobs; docs/dev/bh2-maps.md)
  bh2 difficulty              the static difficulty score of every mission (M31 must be the hardest by 10%)
  bh2 features                the feature coverage table (properties, terrain, inventions per map) and what no map uses yet
  bh2 check                   the world-map flag check (every mission flag on land inside its nation) and the pipeline checks (specs up to date, lint clean)
Maps: `aw2dev maps gen --campaign bh2`, `aw2dev maps lint --source bh2`.
"""
from .. import cfg, util


def register(sub):
    p = sub.add_parser("bh2", help="BH2 Campaign maps: pictures, feature coverage, flag check (docs/dev/bh2-maps.md)")
    ps = p.add_subparsers(dest="bh2cmd", required=True)
    a = ps.add_parser("pictures", help="review pictures of the BH2 maps and the world map with the flags")
    a.add_argument("--out", help="folder (default devkit/work/bh2/maps)")
    a.add_argument("--act", type=int, help="also write worldmap_flags_act<N>.png (that act's flags only)")
    a.set_defaults(fn=pictures)
    a = ps.add_parser("sheets", help="label the game's own pictures (aw2dev maps boot --campaign bh2): m0N.png, m01_fog.png, m04_front2.png, act1_game_sheet.png, act2_game_sheet.png")
    a.add_argument("--raw", help="the harness's pictures (default devkit/work/campaign/bh2/review_raw)")
    a.add_argument("--act", type=int, nargs="*", help="only these acts' missions (default: every mission with a picture)")
    a.add_argument("--out", help="folder (default devkit/work/bh2/game)")
    a.set_defaults(fn=sheets)
    a = ps.add_parser("scenes", help="every BH2 scene: the dialogue lint (keys used and resolvable) and the scene -> song table; fails on a story scene without music")
    a.add_argument("--md", action="store_true")
    a.set_defaults(fn=scenes)
    a = ps.add_parser("saves", help="the folded BH2 save record: the unit tests (merge/extract) and the harness round trip with BH, Emerald Sun and BH2 progress")
    a.add_argument("--no-harness", action="store_true", help="only the unit tests")
    a.set_defaults(fn=saves)
    a = ps.add_parser("prologue-sheet", help="every page and dialogue box of the prologue, one typed-out frame each (harness), as a contact sheet and a folder of PNGs")
    a.add_argument("--out", help="the PNG (default devkit/work/bh2/prologue_full.png; the frames go in prologue_frames/ beside it)")
    a.add_argument("--no-run", action="store_true", help="use the frames of the last harness run")
    a.set_defaults(fn=prologue_sheet)
    a = ps.add_parser("integration", help="the integration proof sheet of the harness's frames: chooser, prologue, world map, a pre-mission scene per act, Aria's CO select")
    a.add_argument("--out", help="the PNG (default devkit/work/bh2/integration_sheet.png)")
    a.set_defaults(fn=integration)
    a = ps.add_parser("silhouettes", help="the silhouette check: maps too alike or a rounded blob in the sea (approved maps are listed, not failed)")
    a.set_defaults(fn=silhouettes)
    a = ps.add_parser("difficulty", help="the static difficulty score of every BH2 mission; the final mission must lead by 10 percent")
    a.set_defaults(fn=difficulty)
    a = ps.add_parser("features", help="which properties, terrain and inventions each BH2 map uses")
    a.set_defaults(fn=features)
    a = ps.add_parser("check", help="world-map flags inside their nations, on land; looks and weather; with the game's pictures, ground colours of neighbouring missions")
    a.add_argument("--pictures", help="the game's pictures (default devkit/work/campaign/bh2/review_raw, when it exists)")
    a.set_defaults(fn=check)


def pictures(a):
    from ..bh2lib import pictures as pics
    out = a.out or cfg.work("bh2", "maps")
    paths = pics.write_all(out)
    paths.append(pics.world_flags(f"{out}/worldmap_flags.png"))
    for act in ([a.act] if a.act else [2, 3, 4, 5]):
        paths.append(pics.world_flags(f"{out}/worldmap_flags_act{act}.png", act=act))
    for p in paths:
        util.say(f"picture: {p}")
    return 0


def sheets(a):
    from ..bh2lib import pictures as pics
    raw = a.raw or cfg.work("campaign", "bh2", "review_raw")
    paths = pics.game_sheets(raw, a.out or cfg.work("bh2", "game"), acts=a.act)
    for p in paths:
        util.say(f"picture: {p}")
    return 0 if paths else 1


def scenes(a):
    """`bh2 scenes`: tools/bh2text/lint.py (grammar, 176 px boxes, songs, every key the code asks for exists, every scene is asked for) and the example `aw2_campaign_scenes ROM bh2` (the
    scene -> song table). A story scene (prologue, intro, victory, after) with no song fails; so does a scene the code never asks for."""
    import subprocess
    import sys
    from .. import cfg
    r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "bh2text" / "lint.py")], capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
    bad = r.returncode != 0
    for l in r.stdout.splitlines():
        if l.startswith(("ERROR", "warn")):
            print(l)
            bad = bad or l.startswith("warn")
    exe = util.example_bin("aw2_campaign_scenes")
    util.check_fresh(exe, "aw2_campaign_scenes")
    r = subprocess.run([str(exe), str(cfg.aw2_rom()), "bh2"], capture_output=True, text=True, env=dict(__import__("os").environ))
    if r.returncode:
        util.die("aw2_campaign_scenes failed: " + r.stderr[-300:])
    n, silent = 0, []
    for line in r.stdout.splitlines():
        m, kind, boxes, label, song = line.split("\t")
        n += 1
        if a.md:
            print(f"| {m} | {kind} | {boxes} | {label} | {song} |")
        if kind in ("prologue", "intro", "victory", "after") and label == "-":
            silent.append(f"{m} {kind}")
    util.say(f"bh2 scenes: {n} scenes listed, {len(silent)} story scene(s) without a song" + (": " + ", ".join(silent) if silent else ""))
    return 1 if (bad or silent) else 0


def saves(a):
    """`bh2 saves`: the BH2 record is folded into slot 13 after the BH Campaign's (`Source::save_offset`): `ds_campaign::save_tests` and, unless --no-harness, `-k bh2_saves` (BH, Emerald Sun and BH2 progress
    round-trip; an old BH save still loads; slot 10 unused)."""
    import subprocess
    import sys
    from .. import cfg
    env = dict(__import__("os").environ, PATH=f"{__import__('os').path.expanduser('~')}/.rustup/toolchains/stable-aarch64-apple-darwin/bin:" + __import__("os").environ["PATH"])
    r = subprocess.run(["cargo", "test", "-p", "tango-gamesupport-aw2", "--lib", "save_tests"], cwd=cfg.REPO, env=env)
    bad = r.returncode
    if not a.no_harness:
        r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "-k", "bh2_saves"], cwd=cfg.REPO)
        bad = bad or r.returncode
    util.say("bh2 saves: " + ("ok" if not bad else "FAILED"))
    return 1 if bad else 0


def prologue_sheet(a):
    from ..bh2lib import integration as ig
    path, n = ig.prologue_sheet(a.out or cfg.work("bh2", "prologue_full.png"), run=not a.no_run)
    util.say(f"picture: {path} ({n} frames)")
    return 0


def integration(a):
    from ..bh2lib import integration as ig
    util.say("picture:", ig.sheet(a.out or cfg.work("bh2", "integration_sheet.png")))
    return 0


def difficulty(a):
    from ..bh2lib import difficulty as dif
    lines, rs = dif.report()
    for l in lines:
        print(l)
    scores = sorted(((sc, n) for n, t, nm, sc, sp in rs), reverse=True)
    top, second = scores[0], scores[1]
    ok = top[1] == 31 and top[0] >= second[0] * 1.10
    util.say(f"hardest: M{top[1]} ({top[0]}), next M{second[1]} ({second[0]}): " + ("M31 leads by a clear margin" if ok else "M31 is NOT clearly the hardest"))
    return 0 if ok else 1


def silhouettes(a):
    from ..bh2lib import silhouette
    from .. import cfg
    problems, lines = silhouette.check(str(cfg.REPO / "tango-gamesupport-aw2" / "five" / "bh2"))
    for l in lines:
        util.say("note: " + l)
    for p in problems:
        util.say("PROBLEM: " + p)
    util.say("bh2 silhouettes: " + ("varied" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


def features(a):
    from .. import bh2lib
    ms = list(bh2lib.maps().values())
    table, _, missing = bh2lib.features_table(ms)
    print(table)
    return 0


def check(a):
    from .. import bh2lib
    problems = bh2lib.check_flags()
    for p in problems:
        util.say(f"PROBLEM: {p}")
    for n, key, look, weather, fog in bh2lib.looks():
        util.say(f"M{n} {key}: look {look}, weather {weather}{', fog' if fog else ''}")
    from ..bh2lib import silhouette
    sp, _ = silhouette.check(str(cfg.REPO / "tango-gamesupport-aw2" / "five" / "bh2"))
    for p in sp:
        util.say(f"PROBLEM: {p}")
    problems = list(problems) + sp
    warns = bh2lib.check_looks()
    pics = a.pictures or cfg.work("campaign", "bh2", "review_raw")
    from pathlib import Path
    if Path(pics).exists() and any(Path(pics).glob("m*_*.png")):
        lines, pw = bh2lib.check_pictures(pics)
        for l in lines:
            util.say("picture: " + l)
        warns += pw
    for w in warns:
        util.say(f"WARNING: {w}")
    util.say("bh2 check: " + ("flags clean" if not problems else f"{len(problems)} problem(s)") + (f", {len(warns)} look warning(s)" if warns else ", looks vary"))
    return 1 if problems else 0
