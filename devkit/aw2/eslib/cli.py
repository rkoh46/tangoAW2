"""aw2dev campaign sheets | sim | difficulty | check for the Emerald Sun Campaign (docs/dev/es-campaign.md)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
from .. import cfg, util
from . import difficulty, report

ES_RUNS = lambda: cfg.work("campaign", "es", "sim.jsonl")


def _tests():
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from ..commands.maps import _bases
    _bases()
    return cfg.REPO / "tools" / "aw2test" / "run.py"


def sheets(a):
    """One picture per mission (the whole map, fog OFF, plus the fogged view of a fog mission) with "MISSION N - Title" burned in, and a contact
    sheet per act."""
    run = _tests()
    raw = cfg.work("campaign", "es", "review_raw")
    raw.mkdir(parents=True, exist_ok=True)
    for f in raw.glob("*.png"):
        # (with --mission only those missions' pictures are taken again: the others stay for the contact sheets)
        if not a.mission or any(f.name.startswith(f"m{n}_") for n in a.mission):
            f.unlink()
    out = Path(a.out) if a.out else cfg.work("campaign", "es", "sheets")
    env = dict(os.environ, AW2TEST_REVIEW_DIR=str(raw))
    keys = [f"es_review_m{n}$" for n in a.mission] if a.mission else ["es_review_m"]
    rc = 0
    for k in keys:
        r = subprocess.run([sys.executable, str(run), "-k", k], env=env, cwd=cfg.REPO)
        rc = rc or r.returncode
    if not a.mission:
        # (the weather pictures for es_weather.png: the field of each weather mission in the game)
        r = subprocess.run([sys.executable, str(run), "-k", "es_weather_m"], env=env, cwd=cfg.REPO)
        rc = rc or r.returncode
    subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "es_sheets.py"), str(raw), str(out)], check=False)
    util.say("sheets in", out)
    return rc


def sim(a):
    """Plays missions in the harness: the test player (bot) or the computer for both sides (cpu), per seed; prints one row each and appends them to
    devkit/work/campaign/es/sim.jsonl (read by `difficulty`)."""
    run = _tests()
    out = ES_RUNS()
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for player in a.player:
        for seed in range(a.seeds):
            # (one harness run for all the named missions: they play in parallel)
            env = dict(os.environ, AW2TEST_ES_SIM=" ".join(map(str, a.mission)), AW2TEST_ES_PLAYER=player, AW2TEST_ES_SEED=str(seed), AW2TEST_ES_DAYS=str(a.days),
                       AW2TEST_ES_OUT=str(out), AW2TEST_ES_SCALE=str(a.scale))
            before = out.read_text().count("\n") if out.exists() else 0
            subprocess.run([sys.executable, str(run), "-k", "es_sim_m"] + (["-j", str(a.jobs)] if a.jobs else []), env=env, cwd=cfg.REPO, capture_output=not a.verbose)
            lines = out.read_text().splitlines()[before:] if out.exists() else []
            for l in sorted((json.loads(l) for l in lines), key=lambda r: r["mission"]):
                rows.append(l)
                print(f"M{l['mission']:<2} {l['title']:<20} {player:3} seed {seed}: {l['result']:4} in {l['days']} days, units {l['units']} funds {l['funds']}")
            got = {json.loads(l)["mission"] for l in lines}
            for n in a.mission:
                if n not in got:
                    print(f"M{n} {player} seed {seed}: no result (the test failed; see tools/aw2test/out/ds/es_sim_m{n}/log.txt)")
    return 0


def _rows(runs=None):
    ms = report.missions()
    runs = difficulty.load_runs(ES_RUNS()) if runs is None else runs
    rows = []
    for i, (key, d) in enumerate(ms.items(), 1):
        n = difficulty.numbers(d)
        st = difficulty.static_score(n)
        dyn = difficulty.dynamic_score(runs.get(i, []))
        rows.append((i, key, d, n, st, dyn))
    return rows


def difficulty_cmd(a):
    rows = _rows()
    print(f"{'#':>2} {'mission':<20} {'player':>8} {'enemy':>8} {'force':>6} {'econ':>6} {'fort':>5} {'press':>5} {'static':>6} {'dynamic':>7} {'score':>6}")
    best = None
    for i, key, d, n, st, dyn in rows:
        score = st if dyn is None else round((st + dyn) / 2, 1)
        print(f"{i:>2} {d['title']:<20} {n['player_value']:>8} {n['enemy_value']:>8} {n['force']:>6.2f} {n['economy']:>6.2f} {n['fortified']:>5} {n['pressure']:>5.2f} {st:>6} "
              f"{'-' if dyn is None else dyn:>7} {score:>6}")
        if best is None or score > best[0]:
            best = (score, i)
    scores = sorted(((st if dyn is None else (st + dyn) / 2), i) for i, key, d, n, st, dyn in rows)
    if len(scores) >= 2:
        top, second = scores[-1], scores[-2]
        ok = top[1] == len(rows) and top[0] >= second[0] * 1.10
        print(f"hardest: M{top[1]} ({top[0]:.1f}), next M{second[1]} ({second[0]:.1f}): {'M16 leads by a clear margin' if ok else 'M16 is NOT clearly the hardest'}")
        return 0 if (ok or len(rows) < 16 or not a.require_final) else 1
    return 0


def asuka_rule(say):
    """The campaign's sources (Rust modules, dialogue texts, maps' data) never mention Asuka: no dialogue line, no roster entry, no mission army CO. -> number of failures."""
    import re
    from .. import cfg
    src = cfg.REPO / "tango-gamesupport-aw2" / "src"
    files = sorted(src.glob("es_*.rs")) + sorted((src / "es_text").glob("*")) + [src / "es_text.rs"]
    pat = re.compile(r"asuka|co_new::ASUKA|ASUKA\b", re.I)
    hits = []
    for f in files:
        if f.name in ("es_cos.rs", "es_music.rs") or not f.is_file():
            continue          # the portraits' and the themes' tables are shared with the Versus COs (keyed by CO id, not the campaign)
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            if pat.search(line):
                hits.append(f"{f.name}:{n}")
    say(not hits, "Asuka is not in the Emerald Sun Campaign" + (f" (found at {', '.join(hits[:6])})" if hits else " (no mention in the campaign's modules, dialogue or rosters)"))
    return 1 if hits else 0


def check(a):
    """The static campaign check: the rules the user set for the Emerald Sun Campaign, failed loudly."""
    rc = 0
    ms = report.missions()
    say = lambda ok, msg: print(("ok   " if ok else "FAIL ") + msg)
    fail = lambda ok, msg: (say(ok, msg), None)[1] or (ok or 1)
    bad = 0
    say(len(ms) == 16, f"{len(ms)} missions (16 wanted)") if True else None
    bad += len(ms) != 16
    bh = [k for k, d in ms.items() if d["blackhole"]]
    say(len(bh) <= 2 and set(bh) <= {"es09", "es13"}, f"missions with Black Hole inventions: {bh} (at most M9 and M13)")
    bad += not (len(bh) <= 2 and set(bh) <= {"es09", "es13"})
    for key, d in ms.items():
        for a, n in ((a, sum(d['units'][a].values())) for a in range(1, d["n_armies"] + 1)):
            if n > 40:
                say(False, f"{key}: army {a} starts with {n} units (40 at most: AW2 stops an army's production and reinforcements at 50 units)")
                bad += 1
        cap = {a["n"]: a for a in d["armies"]}
        if d["boxes"] < 20:
            say(False, f"{key}: only {d['boxes']} dialogue boxes")
            bad += 1
    # Asuka (CO 92) is in Versus, War Room and Survival but NOT in the Emerald Sun Campaign (and reserved for the BH2 Campaign): nothing of the campaign may name her
    bad += asuka_rule(say)
    # no mission but the two has an enemy army of Black Hole's colour
    for key, d in ms.items():
        foes = [a for a in d["armies"] if a["team"] != d["armies"][0]["team"] and a["colour"] == 5]
        if foes and key not in ("es09", "es13"):
            say(False, f"{key}: a Black Hole army (colour 5) is an enemy")
            bad += 1
    # the player is Emerald Sun in every mission: the colour slot its skin sits on is the player's alone (no enemy or ally of the mission wears it)
    names = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}
    slots = []
    for key, d in ms.items():
        arm = sorted(d["armies"], key=lambda a: a["n"])
        pc = arm[0]["colour"]
        clash = [a["n"] for a in arm[1:] if a["colour"] == pc]
        if clash or pc == 5:
            say(False, f"{key}: the player's colour slot {names[pc]} is shared with army {clash} or is Black Hole's")
            bad += 1
        slots.append(f"{key[2:]}:{names[pc][:2].upper()}")
    say(True, "the player (Emerald Sun skin) sits in the slot " + " ".join(slots))
    # every army its own nation (colour), at most one HQ each (the maps: maps lint AR01 / AR02)
    for key, d in ms.items():
        cols = [a["colour"] for a in d["armies"]]
        if len(set(cols)) != len(cols):
            say(False, f"{key}: two armies share a colour {cols}")
            bad += 1
    say(True, "every army of every mission has its own colour")
    # looks and weathers: the campaign's variety (desert and sandstorm, rain, snow) and the answer to every threat under their penalties
    LOOK, WX = {0: "normal", 1: "snow", 2: "desert", 3: "wasteland"}, {0: "clear", 1: "snow", 2: "rain", 3: "sandstorm"}
    say(True, "look/weather: " + " ".join(f"{k[2:]}:{LOOK[d['look']][:3]}/{WX[d['weather']][:4]}" for k, d in ms.items() if d["look"] or d["weather"]))
    deserts = [k for k, d in ms.items() if d["look"] == 2]
    ok = len(deserts) >= 2 and any(d["weather"] == 3 for d in ms.values()) and any(d["weather"] == 2 for d in ms.values()) and sum(d["weather"] == 1 for d in ms.values()) >= 2
    say(ok, f"the variety: {len(deserts)} desert missions, sandstorm {[k for k, d in ms.items() if d['weather'] == 3]}, rain {[k for k, d in ms.items() if d['weather'] == 2]}, snow {[k for k, d in ms.items() if d['weather'] == 1]}")
    bad += not ok
    for key, d in ms.items():
        if d["weather"] == 3:
            # a sandstorm takes a cell off every long gun (never below 2): the player must not depend on long guns alone, and must have direct fire
            mine = d["units"].get(1, {})
            direct = sum(n for kind, n in mine.items() if kind in (1, 2, 3, 4, 5, 6, 8, 14, 16, 17, 19))
            long_guns = sum(n for kind, n in mine.items() if kind in (10, 11, 15, 21))
            good = direct >= 6 and direct > 2 * long_guns
            say(good, f"{key}: under the sandstorm the player has {direct} direct-fire units and {long_guns} long guns")
            bad += not good
    # the map files' colours are the Rust missions' (the maps are linted by them), and Black Hole's inventions belong to an enemy army of Black Hole's colour
    from aw2.maplint import load
    maps = {m.name: m for m in load.es_maps()}
    for key, d in ms.items():
        m = maps.get(key)
        if m is None:
            continue
        rust = [a["colour"] for a in sorted(d["armies"], key=lambda a: a["n"])]
        if list(m.meta.get("colours", []))[:len(rust)] != rust:
            say(False, f"{key}: the map file's colours {m.meta.get('colours')} are not the mission's {rust} (fix the spec's `colours=`)")
            bad += 1
        if m.meta.get("blackhole"):
            owner = [a for a in d["armies"] if a["colour"] == 5 and a["n"] != 1]
            if not owner:
                say(False, f"{key}: Black Hole's inventions have no Black Hole enemy army (colour 5) to own them")
                bad += 1
            else:
                say(True, f"{key}: the inventions belong to army {owner[0]['n']} (Black Hole)")
    # the world map: Omega Land with the sixteen flags in story order, each on land and apart from the others
    from . import worldmap
    pic = worldmap.picture()
    pts = worldmap.nodes()
    wm = worldmap.problems(pts, pic, worldmap.needs())
    for w in wm:
        say(False, "world map: " + w)
    bad += len(wm)
    say(not wm, f"world map: 16 flags on Omega Land{'' if pic is not None else ' (no Dual Strike ROM: the land test is skipped)'}, in story order, each opened by the one before")
    say(bad == 0, f"campaign check: {bad} problems")
    return 1 if bad else 0
