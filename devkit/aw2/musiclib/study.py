"""Style statistics of AW2's own songs (`aw2dev sound study IDS`, docs/dev/music-kit.md "AW2 CO theme style").

Reads each song from the player's ROM FOR MEASUREMENT ONLY and prints numbers, never notes: tempo, intro and loop, each track's voices, role, note
density, rhythm (how much is off the beat), the typical bar pattern of the bass and the drum kit, range, volume and pan, phrase lengths, the chord
roots (scale degrees against the tonic) and key windows. Nothing here is a melody, and nothing is written to the repository by the tool.
"""
import statistics
from collections import Counter

BAR = 96
MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _corr(a, b):
    ma, mb = sum(a) / 12, sum(b) / 12
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0


def key_of(pcs):
    """(tonic pitch class, 'maj'/'min', score) by the Krumhansl profiles from a 12-bin weight list."""
    best = None
    for t in range(12):
        rot = [pcs[(t + i) % 12] for i in range(12)]
        for name, prof in (("maj", MAJ), ("min", MIN)):
            c = _corr(rot, prof)
            if best is None or c > best[2]:
                best = (t, name, c)
    return best


def song_data(rom, sid):
    from . import m4a
    s = rom.song(sid)
    tracks, tempo, end, loop_tick = [], None, 0, None
    for t, p in enumerate(s["track_ptrs"]):
        ev, e, lt, _ = m4a.run(rom, p)
        end = max(end, e)
        if lt is not None:
            loop_tick = lt if loop_tick is None else min(loop_tick, lt)
        voice, notes, voices, vols, pans, changes = None, [], Counter(), [], [], 0
        for x in ev:
            if x[1] == "VOICE":
                if voice is not None and x[2] != voice:
                    changes += 1
                voice = x[2]
            elif x[1] == "TEMPO":
                tempo = tempo or x[2] * 2
            elif x[1] == "VOL":
                vols.append(x[2])
            elif x[1] == "PAN":
                pans.append(x[2])
            elif x[1] == "NOTE":
                vt = rom.voice(s["group"], voice)["type"] if voice is not None else 0
                notes.append(dict(t=x[0], key=x[2], vel=x[3], len=x[4], voice=voice, kit=vt == 0x80))
                voices[voice] += 1
        tracks.append(dict(idx=t, notes=notes, voices=voices, vols=vols, pans=pans, changes=changes))
    loop_tick = loop_tick or 0
    return dict(id=sid, tempo=tempo or 0, end=end, loop=loop_tick, tracks=tracks)


def _poly(notes):
    live, best = [], 1
    for n in sorted(notes, key=lambda n: n["t"]):
        live = [e for e in live if e > n["t"]]
        live.append(n["t"] + (n["len"] or 24))
        best = max(best, len(live))
    return best


def track_stats(tr, loop, end):
    ns = [n for n in tr["notes"] if loop <= n["t"] < end]
    kit = bool(ns) and sum(n["kit"] for n in ns) > len(ns) / 2
    bars = max((end - loop) / BAR, 1)
    out = dict(idx=tr["idx"], n=len(ns), kit=kit, voices=dict(tr["voices"]), changes=tr["changes"], dens=len(ns) / bars)
    if not ns:
        return out
    keys = sorted(n["key"] for n in ns)
    out.update(mean=sum(keys) / len(keys), lo=keys[len(keys) // 20], hi=keys[-1 - len(keys) // 20], poly=_poly(ns),
               off4=sum(n["t"] % 24 != 0 for n in ns) / len(ns), off8=sum(n["t"] % 12 != 0 for n in ns) / len(ns),
               short=sum(1 for n in ns if n["len"] and n["len"] <= 12) / len(ns),
               vol=(min(tr["vols"]), max(tr["vols"])) if tr["vols"] else None, pan=sum(tr["pans"]) / len(tr["pans"]) if tr["pans"] else None)
    # the bar patterns on the sixteenth grid (6 ticks)
    pats = Counter()
    for b in range(int((end - loop) // BAR)):
        sl = ["."] * 16
        for n in ns:
            if loop + b * BAR <= n["t"] < loop + (b + 1) * BAR:
                sl[(n["t"] - loop - b * BAR) // 6] = "x"
        pats["".join(sl)] += 1
    top, c = pats.most_common(1)[0]
    out["pattern"], out["pattern_share"] = top, c / sum(pats.values())
    if kit:
        k = Counter()
        slots = {}
        for n in ns:
            slots.setdefault(n["key"], Counter())[((n["t"] - loop) % BAR) // 6] += 1
        out["kit_keys"] = {key: dict(sorted(c.items())) for key, c in slots.items() if sum(c.values()) >= bars}
    return out


def intervals_of(ns, loop, end):
    """Melodic interval profile of a line (onset order, top note): shares of repeats, steps (1-2), thirds (3-4), leaps (5+), chromatic steps (1), tritones (6), rests of a beat or more between notes."""
    ln = {}
    for n in ns:
        if loop <= n["t"] < end and (n["t"] not in ln or n["key"] > ln[n["t"]]["key"]):
            ln[n["t"]] = n
    ln = [ln[t] for t in sorted(ln)]
    if len(ln) < 3:
        return {}
    iv = [abs(b["key"] - a["key"]) for a, b in zip(ln, ln[1:])]
    gaps = [b["t"] - (a["t"] + (a["len"] or 12)) for a, b in zip(ln, ln[1:])]
    n = len(iv)
    return dict(same=sum(i == 0 for i in iv) / n, step=sum(1 <= i <= 2 for i in iv) / n, third=sum(3 <= i <= 4 for i in iv) / n,
                leap=sum(i >= 5 for i in iv) / n, chrom=sum(i == 1 for i in iv) / n, tritone=sum(i == 6 for i in iv) / n,
                rests=sum(g >= 24 for g in gaps) / n, notes_per_phrase=len(ln))


def phrases(ns, loop, end, gap=24):
    ns = sorted((n for n in ns if loop <= n["t"] < end), key=lambda n: n["t"])
    out, start, last = [], None, None
    for n in ns:
        if start is None:
            start = n["t"]
        elif n["t"] - last > gap:
            out.append((last - start) / BAR)
            start = n["t"]
        last = n["t"] + (n["len"] or 12)
    if start is not None:
        out.append((last - start) / BAR)
    return out


def harmony(sd):
    loop, end = sd["loop"], sd["end"]
    pcs = [0.0] * 12
    pitched = [t for t in sd["tracks"] if t["notes"] and not all(n["kit"] for n in t["notes"])]
    for t in pitched:
        for n in t["notes"]:
            if loop <= n["t"] < end and not n["kit"]:
                pcs[n["key"] % 12] += n["len"] or 24
    ton, mode, _ = key_of(pcs)
    # chord roots: the lowest pitched track's lowest sounding note of each bar
    low = min(pitched, key=lambda t: statistics.mean(n["key"] for n in t["notes"] if not n["kit"]))
    roots = []
    for b in range(int((end - loop) // BAR)):
        c = Counter()
        for n in low["notes"]:
            if loop + b * BAR <= n["t"] < loop + (b + 1) * BAR:
                c[(n["key"] - ton) % 12] += n["len"] or 24
        roots.append(c.most_common(1)[0][0] if c else None)
    # key windows of 8 bars
    wins = []
    for w in range(0, int((end - loop) // BAR), 8):
        p = [0.0] * 12
        for t in pitched:
            for n in t["notes"]:
                if loop + w * BAR <= n["t"] < loop + (w + 8) * BAR and not n["kit"]:
                    p[n["key"] % 12] += n["len"] or 24
        wins.append(key_of(p)[:2] if sum(p) else None)
    return dict(tonic=ton, mode=mode, roots=roots, windows=wins, low_track=low["idx"])


def study(rom, sid):
    sd = song_data(rom, sid)
    end = sd["end"]
    sd["stats"] = [track_stats(t, sd["loop"], end) for t in sd["tracks"]]
    pitched = [s for s in sd["stats"] if s["n"] and not s["kit"]]
    sd["harmony"] = harmony(sd)
    mel = [s for s in pitched if s["poly"] <= 2 and s["n"] >= 20]
    sd["lead"] = max(mel, key=lambda s: s["mean"])["idx"] if mel else None
    sd["phrases"] = phrases(sd["tracks"][sd["lead"]]["notes"], sd["loop"], end) if sd["lead"] is not None else []
    sd["lead_ivl"] = intervals_of(sd["tracks"][sd["lead"]]["notes"], sd["loop"], end) if sd["lead"] is not None else {}
    return sd


def report(sd):
    L = []
    bars = (sd["end"] - sd["loop"]) / BAR
    L.append(f"song {sd['id']}: {sd['tempo']} bpm, intro {sd['loop'] / BAR:.0f} bars, loop {bars:.0f} bars = {bars * 4 * 60 / sd['tempo']:.0f} s, {len(sd['tracks'])} tracks")
    h = sd["harmony"]
    N = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    L.append(f"  key {N[h['tonic']]} {h['mode']}; 8-bar windows {[(N[w[0]] + w[1]) if w else None for w in h['windows']]}; bass-root degrees by bar {h['roots']}")
    for s in sd["stats"]:
        if not s["n"]:
            continue
        role = "KIT" if s["kit"] else ("LEAD" if s["idx"] == sd["lead"] else ("bass" if s["idx"] == h["low_track"] else ""))
        vo = ",".join(f"{v}x{c}" for v, c in sorted(s["voices"].items(), key=lambda x: -x[1])[:3])
        if s["kit"]:
            L.append(f"  t{s['idx']} {role}: {s['dens']:.0f} hits/bar, voice {vo}, vol {s['vol']}, pan {s['pan']}")
            for key, c in sorted(s.get("kit_keys", {}).items()):
                L.append(f"      key {key}: slots {''.join(str(min(c.get(i, 0), 9)) for i in range(16))}")
        else:
            L.append(f"  t{s['idx']} {role:4}: {s['dens']:.1f} notes/bar, poly {s['poly']}, mean key {s['mean']:.0f} ({s['lo']}..{s['hi']}), off-beat {s['off4']:.0%}, off-8th {s['off8']:.0%}, short {s['short']:.0%}, "
                     f"voices {vo}, changes {s['changes']}, vol {s['vol']}, pan {s['pan'] if s['pan'] is None else round(s['pan'])}, top bar {s['pattern']} ({s['pattern_share']:.0%})")
    if sd["phrases"]:
        L.append(f"  lead phrases (bars): {[round(p, 1) for p in sd['phrases']]}")
    iv = sd.get("lead_ivl")
    if iv:
        L.append("  lead intervals: " + ", ".join(f"{k} {v:.0%}" for k, v in iv.items() if k != "notes_per_phrase"))
    return "\n".join(L)


def averages(all_sd):
    def avg(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else float("nan")
    rows = []
    for sd in all_sd:
        st = sd["stats"]
        lead = next((s for s in st if s["idx"] == sd["lead"]), None)
        bass = next((s for s in st if s["idx"] == sd["harmony"]["low_track"]), None)
        kit = [s for s in st if s["kit"]]
        rows.append(dict(bpm=sd["tempo"], loop=(sd["end"] - sd["loop"]) / BAR, intro=sd["loop"] / BAR, tracks=len(sd["tracks"]),
                         lead_dens=lead["dens"] if lead else None, lead_lo=lead["lo"] if lead else None, lead_hi=lead["hi"] if lead else None,
                         lead_off=lead["off4"] if lead else None, lead_changes=lead["changes"] if lead else None,
                         bass_dens=bass["dens"] if bass else None, bass_off=bass["off4"] if bass else None, bass_mean=bass["mean"] if bass else None,
                         bass_short=bass["short"] if bass else None, kit_dens=sum(k["dens"] for k in kit) if kit else None,
                         phrase=statistics.median(sd["phrases"]) if sd["phrases"] else None, minor=sd["harmony"]["mode"] == "min",
                         lead_step=sd.get("lead_ivl", {}).get("step"), lead_leap=sd.get("lead_ivl", {}).get("leap"), lead_chrom=sd.get("lead_ivl", {}).get("chrom"),
                         lead_tritone=sd.get("lead_ivl", {}).get("tritone"), lead_same=sd.get("lead_ivl", {}).get("same"), lead_rests=sd.get("lead_ivl", {}).get("rests")))
    return {k: avg([r[k] for r in rows]) for k in rows[0]}, rows


def song_data_compiled(dirpath, name, kit_tracks, lead=None, bass=None):
    """The same numbers for one of OUR songs (a folder of .m4t files read with TANGOAW2_ES_MUSIC): the compiled track bytes are played back with the
    ROM reader. `kit_tracks`: the 0-based track numbers that play the drum kit."""
    import json, os, subprocess, tempfile
    from pathlib import Path
    from . import m4a, tools
    env = dict(os.environ)
    env["TANGOAW2_ES_MUSIC"] = str(Path(dirpath).resolve())
    exe = str(tools.tool(dirpath))
    j = [json.loads(l) for l in subprocess.run([exe, *tools.rom_args()], capture_output=True, text=True, env=env).stdout.splitlines()]
    j = [x for x in j if x["name"] == name][0]
    tracks, tempo, end, loop_tick = [], j["bpm"], 0, j["intro_ticks"]
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([exe, *tools.rom_args(), "--dump", d], capture_output=True, text=True, env=env)
        for t, tr in enumerate(j["tracks"]):
            b = bytearray((Path(d) / f"{name}.{t}.bin").read_bytes())
            b[-4:] = (0x08000000 + tr["label"]).to_bytes(4, "little")
            ev, e, lt, _ = m4a.run(m4a.Rom(bytes(b)), 0x08000000)
            end = max(end, e)
            voice, notes, voices, vols, pans, changes = None, [], Counter(), [], [], 0
            for x in ev:
                if x[1] == "VOICE":
                    if voice is not None and x[2] != voice:
                        changes += 1
                    voice = x[2]
                elif x[1] == "VOL":
                    vols.append(x[2])
                elif x[1] == "PAN":
                    pans.append(x[2])
                elif x[1] == "NOTE":
                    notes.append(dict(t=x[0], key=x[2], vel=x[3], len=x[4], voice=voice, kit=t in kit_tracks))
                    voices[voice] += 1
            tracks.append(dict(idx=t, notes=notes, voices=voices, vols=vols, pans=pans, changes=changes))
    sd = dict(id=name, tempo=tempo, end=end, loop=loop_tick, tracks=tracks)
    sd["stats"] = [track_stats(t, sd["loop"], end) for t in sd["tracks"]]
    sd["harmony"] = harmony(sd)
    mel = [s for s in sd["stats"] if s["n"] and not s["kit"] and s["poly"] <= 2 and s["n"] >= 20]
    sd["lead"] = lead if lead is not None else (max(mel, key=lambda s: s["mean"])["idx"] if mel else None)
    if bass is not None:
        sd["harmony"]["low_track"] = bass
    sd["phrases"] = phrases(sd["tracks"][sd["lead"]]["notes"], sd["loop"], end) if sd["lead"] is not None else []
    sd["lead_ivl"] = intervals_of(sd["tracks"][sd["lead"]]["notes"], sd["loop"], end) if sd["lead"] is not None else {}
    return sd
