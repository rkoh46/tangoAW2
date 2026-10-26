"""The Emerald Sun themes' kit: `aw2dev sound compose | render | loopcheck | levels | stems | pitchcheck | voices | dump` (docs/dev/music-kit.md). Registered by commands/sound.py."""
import json, os, subprocess, sys
from pathlib import Path
from .. import cfg, util

SONGS = ["klaus", "aurelia", "cassius", "livia", "varro"]
REF = ["kanbei", "sensei", "hawke", "jess", "andy", "olaf", "drake", "colin", "eagle", "grit"]   # AW2's own CO themes, for the level comparison
MUSIC_DIR = cfg.REPO / "tango-gamesupport-aw2" / "music" / "es"
RULES = dict(loop_min=45.0, loop_max=90.0, peak_voices=6, tracks=8, bytes=48 * 1024)


def song_lines(path, rom_for_refs=False):
    """Our song's melodic lines {track: [(tick, key)]} (first pass, drum voices left out), from the compiler's own bytes."""
    import re, tempfile
    from . import m4a
    text = Path(path).read_text()
    name = re.search(r"^\s*song\s+(\w+)", text, re.M).group(1)
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "src", Path(d) / "out"
        src.mkdir()
        (src / f"{name}.m4t").write_text(text)
        rc, songs, err = run_tool(src, ["--dump", str(out)])
        if rc:
            util.die(f"{path}: {err}")
        j = [x for x in songs if x["name"] == name][0]
        lines = {}
        for t, tr in enumerate(j["tracks"]):
            b = bytearray((out / f"{name}.{t}.bin").read_bytes())
            b[-4:] = (0x08000000 + tr["label"]).to_bytes(4, "little")
            ev, *_ = m4a.run(m4a.Rom(bytes(b) + bytes(16)), 0x08000000)
            drum, notes = False, []
            for e in ev:
                if e[1] == "VOICE":
                    drum = j["voices"][e[2]][1] in (120, 127)
                elif e[1] == "NOTE" and not drum:
                    notes.append((e[0], e[2]))
            if notes:
                lines[t + 1] = notes
    return lines


def rom_song_lines(rom, sid):
    """AW2 song `sid`'s melodic lines {track: [(tick, key)]} (first pass; tracks and drum voices as the ROM has them). For comparison only."""
    from . import m4a
    s = rom.song(sid)
    lines = {}
    for t, p in enumerate(s["track_ptrs"]):
        ev, *_ = m4a.run(rom, p)
        drum, notes = False, []
        for e in ev:
            if e[1] == "VOICE":
                drum = rom.voice(s["group"], e[2])["type"] in (0x40, 0x80)
            elif e[1] == "NOTE" and not drum:
                notes.append((e[0], e[2]))
        if notes:
            lines[t] = notes
    return lines


def similar(a):
    from . import m4a, similar as sim
    ours = {t: sim.line(n) for t, n in song_lines(a.file).items()}
    text = Path(a.file).read_text()
    refs = [l for l in text.splitlines() if l.split(";")[0].strip().startswith("rom ")]
    against = {}
    rom = None
    for spec in a.against.split(","):
        kind, _, what = spec.partition(":")
        if kind == "rom":
            rom = rom or m4a.Rom(cfg.aw2_rom().read_bytes())
            against[spec] = {t: sim.line(n) for t, n in rom_song_lines(rom, int(what)).items()}
        elif kind == "m4t":
            against[spec] = {t: sim.line(n) for t, n in song_lines(what).items()}
        else:
            util.die(f"--against {spec}: use rom:<id> or m4t:<file>")
    print(f"{a.file}: {len(ours)} melodic tracks, {len(refs)} `rom` lines" + ("  FAIL: an original song has no rom references" if refs else ""))
    print(f"{'against':9} {'ours':>4} {'theirs':>6}  {'run':>4} {'contour':>7} {'bars':>6}  verdict")
    bad = len(refs)
    worst = {}
    for spec, tracks in against.items():
        w = dict(run=0, contour=0, bars=0.0)
        for t, ln in ours.items():
            for u, other in tracks.items():
                s = sim.compare(ln, other)
                for k in w:
                    w[k] = max(w[k], s[k])
                why = sim.verdict(s)
                if why or s["run"] >= sim.RUN_NOTES - 1:
                    print(f"{spec:9} {t:4} {u:6}  {s['run']:4} {s['contour']:7} {s['bars']:6.0%}  " + ("FAIL: " + "; ".join(why) if why else "ok"))
                bad += bool(why)
        worst[spec] = w
        print(f"{spec:9} worst over all track pairs: longest interval run {w['run']} notes (fails at {sim.RUN_NOTES}), rhythm+contour run {w['contour']} (fails at {sim.CONTOUR_NOTES}), bars matched {w['bars']:.0%} (fails at {sim.BAR_SHARE:.0%})")
    print(f"similar done bad={bad}")
    return 1 if bad else 0


def register(ss):
    a = ss.add_parser("compose", help="compile the Emerald Sun song files and check the rules (docs/dev/music-kit.md)")
    a.add_argument("--song", nargs="*")
    a.add_argument("--dir", help="song files from this folder instead of the repository's")
    a.add_argument("--json", action="store_true")
    a.add_argument("--crowded", type=int, metavar="N", help="list the bars with more than N notes at once, with each track's share")
    a.set_defaults(fn=compose)
    a = ss.add_parser("render", help="record each theme as the game plays it: WAV, loop check, levels, picture")
    a.add_argument("--song", nargs="*")
    a.add_argument("--out", help="folder for the WAVs (default devkit/work/music)")
    a.add_argument("--seconds", type=float, help="how long to record (default: the intro and two loops plus 2 s)")
    a.add_argument("--dir", help="song files from this folder (TANGOAW2_ES_MUSIC): edit and hear without a rebuild")
    a.add_argument("--export", help="also write each WAV here at 44.1 kHz (the recording is 65.5 kHz), to listen to: never commit these")
    a.set_defaults(fn=render)
    a = ss.add_parser("loopcheck", help="the loop seams of a recording")
    a.add_argument("wav")
    a.add_argument("--song")
    a.add_argument("--dir")
    a.set_defaults(fn=loopcheck)
    a = ss.add_parser("levels", help="loudness and balance of recordings next to AW2's own themes")
    a.add_argument("wav", nargs="*")
    a.add_argument("--ref", action="store_true", help="record AW2's reference themes first (cached in devkit/work/music/ref)")
    a.set_defaults(fn=levels)
    a = ss.add_parser("pitchcheck", help="play every instrument the songs use on a scale in the game and check it sounds at the pitch written (the `shift`)")
    a.add_argument("--dir", help="song files from this folder (default: the repository's)")
    a.set_defaults(fn=pitchcheck)
    a = ss.add_parser("stems", help="render a song's tracks one at a time and report each one's loudness in the mix")
    a.add_argument("song")
    a.add_argument("--dir")
    a.add_argument("--seconds", type=float, default=30.0)
    a.set_defaults(fn=stems)
    a = ss.add_parser("voices", help="AW2's voice entries: type, sample, the pitch it sounds at key 60 (the `shift`), a picture sheet")
    a.add_argument("--group", default="A")
    a.add_argument("--program", type=int, nargs="*")
    a.add_argument("--sheet")
    a.set_defaults(fn=voices)
    a = ss.add_parser("similar", help="originality check: compare a song file's melodies (intervals, rhythm, contour) with AW2's songs, read from the ROM for the comparison only")
    a.add_argument("file", help="the .m4t to check")
    a.add_argument("--against", default="rom:212,rom:219", help="comma list of rom:<AW2 song id> (default Sonja's 212 and Sturm's 219) or m4t:<file>")
    a.set_defaults(fn=similar)
    a = ss.add_parser("dump", help="AW2's own song as text")
    a.add_argument("song", type=int)
    a.add_argument("--track", type=int)
    a.set_defaults(fn=dump)


def work_dir(*p):
    d = cfg.work("music", *p)
    d.mkdir(parents=True, exist_ok=True)
    return d


def tool(dirpath=None):
    """The compiler example. With a song folder given the built-in text is not used, so a binary older than the .m4t files is fine."""
    b = util.example_bin("aw2_es_music")
    if dirpath:
        if not b.exists():
            util.die(f"{b} missing: run `aw2dev build --examples`")
    else:
        util.check_fresh(b, "aw2_es_music")
    return b


def rom_args():
    """`--rom FILE`: the player's AW2 cartridge, so a song's `rom` references (stretches of AW2's own songs) are read as the game reads them; without it they are only checked."""
    try:
        return ["--rom", str(cfg.aw2_rom())]
    except SystemExit:
        return []
    except Exception:
        return []


def run_tool(dirpath=None, files=()):
    env = dict(os.environ)
    if dirpath:
        env["TANGOAW2_ES_MUSIC"] = str(Path(dirpath).resolve())
    r = subprocess.run([str(tool(dirpath)), *rom_args(), *files], capture_output=True, text=True, env=env)
    return r.returncode, [json.loads(l) for l in r.stdout.splitlines()], r.stderr.strip()


def broken_rules(j):
    bad = []
    if not RULES["loop_min"] <= j["loop_s"] <= RULES["loop_max"]:
        bad.append(f"the loop is {j['loop_s']:.1f} s (AW2's themes: {RULES['loop_min']:.0f} to {RULES['loop_max']:.0f})")
    if j["peak_voices"] > RULES["peak_voices"]:
        bad.append(f"{j['peak_voices']} notes at once, first at tick {j.get('peak_at')} = bar {j.get('peak_at', 0) // 96 + 1} of 4/4 (AW2 mixes {RULES['peak_voices']} channels)")
    if len(j["tracks"]) > RULES["tracks"]:
        bad.append(f"{len(j['tracks'])} tracks (the CO themes' player has {RULES['tracks']})")
    if j["bytes"] > RULES["bytes"]:
        bad.append(f"{j['bytes']} bytes (room for {RULES['bytes']})")
    return bad


def crowded(j, dirpath, limit):
    """The bars of a song where more than `limit` notes sound at once: [(bar, count, {track: n})], read back from the compiled bytes."""
    import tempfile
    from . import m4a
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ)
        if dirpath:
            env["TANGOAW2_ES_MUSIC"] = str(Path(dirpath).resolve())
        subprocess.run([str(tool(dirpath)), *rom_args(), "--dump", d], capture_output=True, text=True, env=env)
        marks = []
        total = j["intro_ticks"] + j["loop_ticks"]
        for t, tr in enumerate(j["tracks"]):
            b = bytearray((Path(d) / f"{j['name']}.{t}.bin").read_bytes())
            b[-4:] = (0x08000000 + tr["label"]).to_bytes(4, "little")
            rom = m4a.Rom(bytes(b))
            ev, end, lt, tg = m4a.run(rom, 0x08000000)
            for e in ev:
                if e[1] == "NOTE":
                    marks.append((e[0], 1, t + 1))
                    marks.append((e[0] + (e[4] or 48), -1, t + 1))
    marks.sort(key=lambda m: (m[0], m[1]))
    live = {}
    bars = {}
    bt = 96 if j.get("bar_ticks") is None else j["bar_ticks"]
    for tick, d, trk in marks:
        live[trk] = live.get(trk, 0) + d
        n = sum(live.values())
        if n > limit:
            bar = tick // bt + 1
            if bar not in bars or bars[bar][0] < n:
                bars[bar] = (n, dict(live))
    return sorted((b, n, {k: v for k, v in tr.items() if v}) for b, (n, tr) in bars.items())


def compose(a):
    rc, songs, err = run_tool(a.dir)
    if rc:
        print(err, file=sys.stderr)
        return 1
    if a.song:
        songs = [j for j in songs if j["name"] in a.song]
    if a.crowded:
        for j in songs:
            for bar, n, tr in crowded(j, a.dir, a.crowded):
                print(f"{j['name']}: bar {bar}: {n} notes at once {tr}")
        return 0
    if a.json:
        print(json.dumps(songs, indent=1))
        return 0
    bad = 0
    print(f"{'song':9} {'co':>3} {'bpm':>4} {'intro':>6} {'loop':>6} {'notes':>6} {'peak':>4} {'tracks':>6} {'bytes':>6}  voices")
    for j in songs:
        print(f"{j['name']:9} {j['co']:3} {j['bpm']:4} {j['intro_s']:5.1f}s {j['loop_s']:5.1f}s {j['notes']:6} {j['peak_voices']:4} {len(j['tracks']):6} {j['bytes']:6}  "
              + " ".join(f"{'AB'[g == 0x082415C8] if g in (0x08240FB0, 0x082415C8) else hex(g)}.{i}" for g, i in j["voices"]))
        for b in broken_rules(j):
            print(f"   FAIL {j['name']}: {b}")
            bad += 1
    names = {j["name"] for j in songs}
    if not a.song:
        for n in SONGS:
            if n not in names:
                print(f"   FAIL no song {n}")
                bad += 1
    print(f"compose done bad={bad}")
    return 1 if bad else 0


def _runpy(env_extra, keys):
    env = dict(os.environ)
    env.update(env_extra)
    cmd = [sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "--mode", "ds"] + sum((["-k", k] for k in keys), [])
    util.say("$", " ".join(cmd))
    return subprocess.run(cmd, env=env).returncode


def render(a):
    out = Path(a.out) if a.out else work_dir()
    out.mkdir(parents=True, exist_ok=True)
    names = a.song or SONGS
    env = {"AW2TEST_MUSIC_SONGS": ",".join(names), "AW2TEST_MUSIC_OUT": str(out), "AW2TEST_OUT": str(work_dir("run"))}
    if a.seconds:
        env["AW2TEST_MUSIC_SECONDS"] = str(a.seconds)
    if a.dir:
        env["TANGOAW2_ES_MUSIC"] = str(Path(a.dir).resolve())
    if not a.dir:
        util.check_fresh(util.example_bin("aw2_script"), "aw2_script")
    rc = _runpy(env, ["es_music_render"])
    if rc:
        return rc
    rc, songs, err = run_tool(a.dir)
    info = {j["name"]: j for j in songs}
    worst = 0
    for n in names:
        w = out / f"{n}.wav"
        if not w.exists():
            continue
        worst |= analyse(w, info.get(n), out / f"{n}.png")
        if a.export:
            from . import audio
            rate, _, st = audio.load(w)
            Path(a.export).mkdir(parents=True, exist_ok=True)
            audio.write(Path(a.export) / f"{n}.wav", 44100, audio.resample(st, rate, 44100))
            print(f"   exported {Path(a.export) / (n + '.wav')} (44.1 kHz)")
    return worst


def analyse(wav, j, png):
    from . import audio
    rate, x, st = audio.load(wav)
    lv = audio.levels(x, rate, skip=j["intro_s"] if j else 0)
    print(f"{wav.name}: {len(x) / rate:.1f} s  RMS {lv['rms_db']:.1f} dBFS  peak {lv['peak_db']:.1f}{'  CLIPPED ' + str(lv['clipped']) + ' samples' if lv['clipped'] else ''}  spread(1 s) {lv['sec_p10_db']:.1f}/{lv['sec_p50_db']:.1f}/{lv['sec_p90_db']:.1f}  "
          f"low/mid/high {lv['low']:.2f}/{lv['mid']:.2f}/{lv['high']:.2f}  centroid {lv['centroid']:.0f} Hz")
    bad = 0
    marks = []
    if j:
        seams = audio.loop_seams(x, rate, j["intro_s"], j["loop_s"])
        marks = [s["t"] for s in seams["seams"]]
        print(f"   loop: repeat correlation {seams.get('repeat_corr', float('nan')):.3f}, period error {seams.get('period_err_ms', float('nan')):+.0f} ms")
        for k, s in enumerate(seams["seams"]):
            loop = abs(s["t"] - j["intro_s"]) > 0.05 or j["intro_s"] < 0.05
            ok = s["click"] < 3.0 and s["gap"] > 0.3
            bad += (not ok) and loop
            print(f"   {'loop' if loop else 'intro'} seam at {s['t']:6.1f} s: click {s['click']:.2f}x  gap {s['gap']:.2f}x  {'ok' if ok else ('CHECK' if loop else 'quiet (the intro ends)')}")
        audio.seam_picture(x, rate, marks, png.with_name(png.stem + "_seams.png"))
    audio.picture(x, rate, png, marks)
    print(f"   picture {png}")
    return 1 if bad else 0


def loopcheck(a):
    rc, songs, err = run_tool(a.dir)
    info = {j["name"]: j for j in songs}
    name = a.song or Path(a.wav).stem.split("_")[0]
    if name not in info:
        util.die(f"no song {name}: --song NAME")
    return analyse(Path(a.wav), info[name], Path(a.wav).with_suffix(".png"))


def ref_files():
    out = work_dir("ref")
    need = [n for n in REF if not (out / f"{n}.wav").exists()]
    if need:
        env = {"AW2TEST_MUSIC_SONGS": ",".join(need), "AW2TEST_MUSIC_OUT": str(out), "AW2TEST_MUSIC_SECONDS": "60", "AW2TEST_OUT": str(work_dir("run"))}
        if _runpy(env, ["es_music_render"]):
            util.die("could not record AW2's reference themes")
    return [out / f"{n}.wav" for n in REF if (out / f"{n}.wav").exists()]


def levels(a):
    from . import audio
    refs = ref_files() if a.ref or not a.wav else []
    rows = []
    print(f"{'file':14} {'RMS dB':>7} {'peak':>6} {'p10':>6} {'p50':>6} {'p90':>6} {'low':>5} {'mid':>5} {'high':>5} {'centroid':>8}")
    for w in refs + [Path(p) for p in a.wav]:
        rate, x, _ = audio.load(w)
        lv = audio.levels(x, rate, skip=2.0)
        tag = ("ref " if w in refs else "") + w.stem
        rows.append((tag, lv))
        print(f"{tag:14} {lv['rms_db']:7.1f} {lv['peak_db']:6.1f} {lv['sec_p10_db']:6.1f} {lv['sec_p50_db']:6.1f} {lv['sec_p90_db']:6.1f} {lv['low']:5.2f} {lv['mid']:5.2f} {lv['high']:5.2f} {lv['centroid']:8.0f}")
    ref = [lv for t, lv in rows if t.startswith("ref ")]
    if ref and len(rows) > len(ref):
        lo, hi = min(r["rms_db"] for r in ref), max(r["rms_db"] for r in ref)
        bad = 0
        print(f"AW2's own themes: RMS {lo:.1f} to {hi:.1f} dBFS (median {sorted(r['rms_db'] for r in ref)[len(ref) // 2]:.1f})")
        for t, lv in rows:
            if not t.startswith("ref "):
                ok = lo - 1.5 <= lv["rms_db"] <= hi + 1.5
                bad += not ok
                print(f"  {t}: {lv['rms_db']:.1f} dBFS {'within' if ok else 'OUTSIDE'} the range {lo - 1.5:.1f}..{hi + 1.5:.1f}")
        return 1 if bad else 0
    return 0


def voices(a):
    import numpy as np
    from . import m4a, viz
    rom = m4a.Rom(cfg.aw2_rom().read_bytes())
    g = {"A": m4a.GROUP_A, "B": m4a.GROUP_B}.get(a.group, None) or int(a.group, 0)
    items = []
    for i in (a.program or range(128)):
        v = rom.voice(g, i)
        t = v["type"]
        if t in (0, 8) and 0x08000000 <= v["word"] < 0x08800000:
            f, loop, pcm = rom.sample(v["word"])
            x = np.frombuffer(pcm, dtype=np.int8).astype(float)
            hps, ac = m4a.sounding_midi(x, f, loop)
            print(f"{i:3} direct{' fixed' if t == 8 else ''} {len(x) / f:5.2f}s {'loop ' + format(len(x) - loop, 'd') if loop is not None else 'one-shot':12} at key 60: MIDI {hps:5.1f} (spectrum) or {ac:5.1f} (autocorrelation) -> shift {60 - round(hps):+d} or {60 - round(ac):+d}")
            items.append((f"{i} {len(x) / f:.2f}s{' L' if loop is not None else ''}", x[: int(f * 2)], f))
        elif t == 0x80:
            print(f"{i:3} rhythm (drum kit) sub-voices at {v['word']:08x}")
        elif t == 0x40:
            print(f"{i:3} key split at {v['word']:08x}")
        elif t in (1, 2, 3, 4, 9, 10, 11, 12) and v["word"] not in (0, 2):
            print(f"{i:3} game-boy channel type {t}")
    if a.sheet and items:
        viz.sheet(items[:48], cols=4, w=330, hs=80, hw=24).save(a.sheet)
        print("sheet", a.sheet)
    return 0


def dump(a):
    from . import m4a
    rom = m4a.Rom(cfg.aw2_rom().read_bytes())
    s = rom.song(a.song)
    print(f"song {a.song}: header {s['header']:08x} tracks {s['tracks']} priority {s['priority']} reverb {s['reverb']} voice group {s['group']:08x}")
    for i, p in enumerate(s["track_ptrs"]):
        if a.track is not None and i != a.track:
            continue
        print(f"-- track {i} at {p:08x}")
        line = []
        for at, txt in m4a.disasm(rom, p):
            line.append(txt)
            if len(line) >= 12:
                print("  " + " ".join(line))
                line = []
        if line:
            print("  " + " ".join(line))
    return 0


def inst_lines(dirpath=None):
    """Every `inst` line of the songs: name, group, program, shift (first definition of a name wins per group/program)."""
    import re
    seen = {}
    d = Path(dirpath) if dirpath else MUSIC_DIR
    for f in sorted(d.glob("*.m4t")):
        for line in f.read_text().splitlines():
            m = re.match(r"\s*inst\s+(\w+)\s*=\s*(\w+)\.(\d+)(?:\s+shift=(-?\d+))?", line.split(";")[0])
            if m:
                key = (m.group(2), int(m.group(3)))
                seen.setdefault(key, int(m.group(4) or 0))
    return seen


def pitchcheck(a):
    """One song of calibration: each pitched instrument plays C3 G3 C4 G4 C5 (sounding) as half notes, alone; the recording is analysed note by note."""
    import numpy as np
    from . import audio, m4a
    insts = {k: v for k, v in inst_lines(a.dir).items() if k[1] not in (120, 127)}
    names = [f"i{g}{p}" for (g, p) in insts]
    notes = ["C3", "G3", "C4", "G4", "C5"]
    expect = [48, 55, 60, 67, 72]
    lines = ["song klaus", "tempo 120", "meter 4/4"]
    for (g, p), sh in insts.items():
        lines.append(f"inst i{g}{p} = {g}.{p} shift={sh}")
    lines.append("track 1 inst=" + names[0] + " vol=100 vel=110 gate=100")
    sec = []
    for n in names:
        sec.append("{inst " + n + "} | " + " | ".join(f"{k}/1" for k in notes) + " |")
    lines.append(f"section A bars={len(names) * len(notes)}")
    lines.append("  1: " + " ".join(sec))
    lines.append("end")
    lines.append("form loop A")
    d = work_dir("pitch")
    for f in d.glob("*.m4t"):
        f.unlink()
    (d / "klaus.m4t").write_text("\n".join(lines) + "\n")
    total = len(names) * len(notes) * 96 * 150 / (59.7275 * 120)
    env = {"AW2TEST_MUSIC_SONGS": "klaus", "AW2TEST_MUSIC_OUT": str(d), "AW2TEST_MUSIC_SECONDS": str(total + 1), "AW2TEST_OUT": str(work_dir("run")), "TANGOAW2_ES_MUSIC": str(d)}
    if _runpy(env, ["es_music_render"]):
        return 1
    rate, x, _ = audio.load(d / "klaus.wav")
    note_s = 96 * 150 / (59.7275 * 120)
    bad = 0
    print(f"{'inst':8} " + " ".join(f"{k:>8}" for k in notes) + "   loudness (first 0.4 s, RMS dBFS at vol 100, vel 110)")
    for i, ((g, p), sh) in enumerate(insts.items()):
        row, rms = [], []
        for j, e in enumerate(expect):
            t0 = (i * len(notes) + j) * note_s
            seg = x[int((t0 + 0.06) * rate): int((t0 + 0.42) * rate)]
            rms.append(audio.db(np.sqrt(np.mean(seg ** 2))))
            fz, conf = audio.f0(seg, rate)
            midi = 69 + 12 * np.log2(fz / 440) if fz else -99
            err = midi - e
            row.append(err)
        ok = all(abs(r) < 0.35 for r in row)
        mark = "ok" if ok else "OFF"
        bad += not ok
        print(f"{g}.{p:<6} " + " ".join(f"{r:+8.2f}" for r in row) + f"   {max(rms):6.1f}  {mark}")
    print("(semitones away from the written pitch; the percussive and one-shot voices (timpani, plucks that die away) can read wrong when the note is gone before the window)")
    return 0


def solo_text(text, keep):
    """The song's text with the section lines of every track not in `keep` removed."""
    import re
    out, in_sec, skipping = [], False, False
    for line in text.splitlines():
        code = line.split(";")[0]
        if re.match(r"\s*section\b", code):
            in_sec = True
        elif re.match(r"\s*end\s*$", code):
            in_sec = False
            skipping = False
        elif in_sec:
            m = re.match(r"\s*(\d+):", code)
            if m:
                skipping = int(m.group(1)) not in keep
            if skipping:
                continue
        out.append(line)
    return "\n".join(out) + "\n"


def stems(a):
    from . import audio
    rc, songs, err = run_tool(a.dir)
    j = next((s for s in songs if s["name"] == a.song), None)
    if not j:
        util.die(f"no song {a.song}")
    src = (Path(a.dir) if a.dir else MUSIC_DIR) / f"{a.song}.m4t"
    d = work_dir("stems", a.song)
    n = len(j["tracks"])
    import shutil
    for f in d.glob("*"):
        shutil.rmtree(f, ignore_errors=True) if f.is_dir() else f.unlink()
    names = ["all"] + [str(k) for k in range(1, n + 1)]
    for nm in names:
        (d / f"{nm}.m4t").write_text(src.read_text() if nm == "all" else solo_text(src.read_text(), {int(nm)}))
    rows = []
    # one render per variant: the harness takes one folder per run, so each variant goes through as the song's own name
    for nm in names:
        sub = d / f"v{nm}"
        sub.mkdir(exist_ok=True)
        (sub / f"{a.song}.m4t").write_text((d / f"{nm}.m4t").read_text())
        env = {"AW2TEST_MUSIC_SONGS": a.song, "AW2TEST_MUSIC_OUT": str(sub), "AW2TEST_MUSIC_SECONDS": str(j["intro_s"] + a.seconds), "AW2TEST_OUT": str(work_dir("run", "stems_" + a.song)),
               "TANGOAW2_ES_MUSIC": str(sub)}
        if _runpy(env, ["es_music_render"]):
            return 1
        rate, x, _ = audio.load(sub / f"{a.song}.wav")
        seg = x[int((j["intro_s"] + 1) * rate):]
        rows.append((nm, audio.levels(x, rate, skip=j["intro_s"] + 1)["rms_db"], audio.grit(seg, rate), audio.levels(x, rate, skip=j["intro_s"] + 1)["peak_db"]))
    full = rows[0][1]
    print(f"{a.song}: the whole mix {full:.1f} dBFS; each track alone (RMS over {a.seconds:.0f} s of the loop):")
    print("  (grit = harmonic-to-noise ratio of a track's steady notes, to compare one voice with another: AW2's brass 56 reads 20 dB or more, a clean voice 12 to 18; a fuzz voice or a sample played far below its recorded key reads low; a drum kit reads nonsense)")
    for nm, v, g, pk in rows[1:]:
        gs = "no steady pitch" if g is None else f"grit {g:5.1f} dB"
        print(f"  track {nm}: {v:6.1f} dBFS ({v - full:+5.1f} dB against the mix)  peak {pk:5.1f}  {gs}")
    pk = rows[0][3]
    print(f"  the mix peaks at {pk:.1f} dBFS" + ("  CHECK: near full scale, the mixer may clip" if pk > -1.0 else " (headroom ok)"))
    return 0
