"""aw2dev bh2: the BH2 Campaign's map kit (docs/dev/bh2-maps.md, skill aw2-add-campaign).

  bh2 pictures [--out DIR]    m01.png .. (full map, fog off, units and labels, "MISSION N - Title" burned in), the fog views, act1_sheet.png, worldmap_flags.png
  bh2 sheets [--raw DIR] [--out DIR]  label the game's own pictures (`aw2dev maps boot --campaign bh2`): m0N.png, m01_fog.png, m04_front2.png, act1_game_sheet.png, act2_game_sheet.png
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
