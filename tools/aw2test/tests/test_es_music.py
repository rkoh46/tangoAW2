"""The Emerald Sun COs' own themes (crate::es_music, docs/dev/music-kit.md): each of the five has a song of its own in the sound engine's table, written from a
text file in the repository, played with AW2's own voices (the group is copied from the ROM), on the CO's turn, and it loops.

`run.py -k es_music_render` (opt-in: AW2TEST_MUSIC_SONGS=klaus,livia ...) records the game's audio output of each theme for AW2TEST_MUSIC_SECONDS (default: the intro and
two loops) into $AW2TEST_MUSIC_OUT/<name>.wav; `aw2dev sound render` drives it (and TANGOAW2_ES_MUSIC=<dir> lets a song be edited and heard without a rebuild).
"""

import json
import os
import subprocess

from aw2test import paths
from aw2test.harness import test
from tests.test_co_music import BGM, SONG, channels, header_of, playing, row_song, wait_song

ENV = {"TANGOAW2_ES_VERSUS": "1"}
COS = {"klaus": 86, "aurelia": 87, "cassius": 88, "livia": 89, "varro": 90, "asuka": 92}
FIRST_SONG = 505
STORY = (0x09000000, 0x09C00000)
DS_NEW = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel", "cloneandy"]
AW2_ROM = 0x08000000


def info(dump=None):
    """The compiler's report on every song (the example aw2_es_music; TANGOAW2_ES_MUSIC picks another folder of song files); `dump`: a folder for each track's bytes."""
    r = subprocess.run([paths.runner("aw2_es_music")] + (["--dump", dump] if dump else []), capture_output=True, text=True, env=dict(os.environ))
    if r.returncode != 0:
        raise AssertionError(r.stderr.strip() or "aw2_es_music failed")
    return {j["name"]: j for j in map(json.loads, r.stdout.splitlines())}


def env():
    e = dict(ENV)
    if os.environ.get("TANGOAW2_ES_MUSIC"):
        e["TANGOAW2_ES_MUSIC"] = os.environ["TANGOAW2_ES_MUSIC"]
    return e


def battle(ctx, co, record=False):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    return ctx.start(m, [co, "andy"], humans=(1,), env=env(), record=record)


def trim_from(path, start_s, out):
    """Write the part of a 16-bit WAV from `start_s` seconds on (stdlib only)."""
    import wave
    with wave.open(path, "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        w.setpos(min(n, max(0, int(start_s * rate))))
        data = w.readframes(n)
    with wave.open(out, "wb") as o:
        o.setnchannels(ch)
        o.setsampwidth(2)
        o.setframerate(rate)
        o.writeframes(data)


def rms_windows(path, seconds=1.0):
    """RMS of each `seconds` of a 16-bit stereo WAV (stdlib only)."""
    import array
    import math
    b = open(path, "rb").read()
    i = b.find(b"data")
    rate = int.from_bytes(b[24:28], "little")
    s = array.array("h")
    s.frombytes(b[i + 8:i + 8 + (len(b) - i - 8) // 2 * 2])
    n = int(rate * seconds) * 2
    return [math.sqrt(sum(x * x for x in s[k:k + n]) / max(1, len(s[k:k + n]))) for k in range(0, len(s) - n + 1, n)]


@test(modes=("ds",))
def es_themes_are_registered(ctx):
    """Five songs of their own at the end of the song table, in the story's ROM range, with a voice group filled from AW2's own voices; AW2's and the Dual Strike COs' themes unchanged."""
    dump = os.path.join(ctx.out, "tracks")
    songs = info(dump)
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["andy", "sami"], humans=(1,), env=env())
    e = g.e
    ids = {}
    ranges = []
    for name, co in COS.items():
        s = row_song(e, co)
        ids[name] = s
        h = header_of(e, s)
        ctx.check(STORY[0] <= h < STORY[1], f"{name}: song {s}, header {h:08x} in the story's range")
        ntr = e.u8(h)
        ctx.eq(ntr, len(songs[name]["tracks"]), f"{name}: tracks")
        ctx.eq((e.u8(h + 2), e.u8(h + 3)), (songs[name]["priority"], songs[name]["reverb"]), f"{name}: priority and reverb")
        group = e.u32(h + 4)
        ranges.append((h, h + 8 + 4 * ntr, f"{name} header"))
        ranges.append((group, group + 12 * len(songs[name]["voices"]), f"{name} voices"))
        for slot, (gr, idx) in enumerate(songs[name]["voices"]):
            mine = [e.u8(group + 12 * slot + k) for k in range(12)]
            theirs = [e.u8(gr + 12 * idx + k) for k in range(12)]
            ctx.eq(mine, theirs, f"{name}: voice slot {slot} is AW2's group {gr:08x} program {idx}")
        for t in range(ntr):
            p = e.u32(h + 8 + 4 * t)
            ctx.check(STORY[0] <= p < STORY[1], f"{name}: track {t} at {p:08x}")
            # the loop: the last command is GOTO (0xB2) to the label, inside the track
            end = p + songs[name]["tracks"][t]["bytes"]
            ctx.eq(e.u8(end - 5), 0xB2, f"{name}: track {t} ends in GOTO")
            lab = e.u32(end - 4)
            ctx.eq(lab, p + songs[name]["tracks"][t]["label"], f"{name}: track {t}'s loop label")
            ranges.append((p, end, f"{name} track {t}"))
            # nothing else wrote over it: the game holds the compiler's bytes (but the GOTO's address)
            want = open(os.path.join(dump, f"{name}.{t}.bin"), "rb").read()
            got = bytes(e.u8(p + k) for k in range(len(want) - 4))
            ctx.check(got == want[:-4], f"{name}: track {t}'s {len(want)} bytes are the compiler's")
    ctx.eq(len(set(ids.values())), len(COS), "a different song for each CO (the five Emerald Sun COs and Asuka)")
    # the room: every piece inside the story's range, none over another
    for i, a in enumerate(ranges):
        ctx.check(STORY[0] <= a[0] and a[1] <= STORY[1], f"{a[2]} {a[0]:08x}..{a[1]:08x} is in the story's range")
        for b in ranges[i + 1:]:
            ctx.check(a[1] <= b[0] or b[1] <= a[0], f"{a[2]} and {b[2]} do not overlap")
    ctx.check(all(i >= FIRST_SONG for i in ids.values()), "after AW2's 505")
    # The Dual Strike COs keep songs 505..514, AW2's keep their own.
    ds = sorted(row_song(e, c) for c in DS_NEW)
    ctx.eq(ds, list(range(FIRST_SONG, FIRST_SONG + 10)), "the ten Dual Strike themes keep ids 505..514")
    for s in (1, 200, 219, 412, 503):
        ctx.eq(header_of(e, s), e.u32(0x0824238C + 8 * s), f"song {s} is AW2's")


@test(modes=("ds",))
def es_theme_plays_on_the_cos_turn_and_loops(ctx):
    """Each CO's turn plays its song on the themes' player with AW2's 8 channels, it is not silent, and it is still playing after the intro and a whole loop (so the GOTO loops work)."""
    songs = info()
    out = os.environ.get("AW2TEST_MUSIC_OUT") or ctx.out
    os.makedirs(out, exist_ok=True)
    for name, co in COS.items():
        if name == "varro":
            continue  # the boss is not in Versus' CO lists (co_new::listed), so no battle can start with him; his song is checked by the registered / intact tests
        g = battle(ctx, co)
        e = g.e
        song = row_song(e, co)
        ctx.check(wait_song(e, song, 300) or e.u16(SONG) == song, f"{name}: the turn starts song {song}")
        ctx.check(playing(e, song), f"{name}: song {song} is playing")
        ctx.eq(channels(e), 8, f"{name}: AW2's 8 channels")
        secs = songs[name]["intro_s"] + songs[name]["loop_s"] + 4
        e.audio_start()
        e.wait(int(secs * 59.7275))
        n, rate = e.audio_end(os.path.join(out, f"{name}_check.wav"))
        ctx.check(playing(e, song), f"{name}: still playing after {secs:.0f} s (looped)")
        w = rms_windows(os.path.join(out, f"{name}_check.wav"))
        quiet = [k for k, v in enumerate(w) if v < 200]
        ctx.log(f"{name}: {len(w)} s recorded, quietest second {min(w):.0f}, loudest {max(w):.0f}")
        ctx.check(len(quiet) <= 1, f"{name}: no silent seconds ({quiet})")
        ctx.check(sum(w) / len(w) > 600, f"{name}: audible (mean RMS {sum(w) / len(w):.0f})")
        e.close()


@test(modes=("ds",))
def es_theme_returns_after_a_power_and_other_cos_keep_theirs(ctx):
    """Klaus's Super Power plays the game's power theme (not a theme of ours), the CPU Kanbei's turn plays AW2's Kanbei theme, and Klaus's next turn plays his song again."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, [COS["klaus"], "kanbei"], humans=(1,), visuals="a", env=env())
    e = g.e
    song = row_song(e, COS["klaus"])
    ctx.check(e.u16(SONG) == song or wait_song(e, song, 300), "Klaus's turn plays his theme")
    ctx.power(g, 1, "super")
    ours = {row_song(e, c) for c in COS.values()}
    ctx.check(e.u16(SONG) not in ours, f"the power plays the game's power theme, not one of the five themes ({e.u16(SONG)})")
    kanbei = row_song(e, "kanbei")
    seen = []
    g.end_turn(observe=lambda gg: seen.append(wait_song(gg.e, kanbei, 600)))
    ctx.check(seen == [True], f"the CPU Kanbei's turn plays AW2's Kanbei song {kanbei}")
    ctx.eq(kanbei, row_song(e, "kanbei", 0x085D3DD0), "which is AW2's own row")
    ctx.check(wait_song(e, song, 600) or e.u16(SONG) == song, "Klaus's next turn plays his theme again")
    e.close()


@test(modes=("aw2",))
def es_music_absent_without_the_pack(ctx):
    """Without the Dual Strike pack the song table is AW2's own, 505 songs."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["andy", "sami"], humans=(1,))
    ctx.eq(g.e.u32(0x080704A0), 0x0824238C, "AW2's song table")


@test(modes=("ds",))
def es_music_render(ctx):
    """Opt-in (AW2TEST_MUSIC_SONGS=klaus,aurelia ...): record each theme as the game plays it, from the song's first tick, for AW2TEST_MUSIC_SECONDS (default: the intro and two loops plus 2 s)
    into $AW2TEST_MUSIC_OUT/<name>.wav. The console is recorded from the first frame and the recording cut where the song began (the music player's tick clock says how long ago that was)."""
    want = [s for s in os.environ.get("AW2TEST_MUSIC_SONGS", "").split(",") if s]
    if not want:
        ctx.log("skipped: AW2TEST_MUSIC_SONGS is not set")
        return
    songs = info()
    out = os.environ.get("AW2TEST_MUSIC_OUT") or ctx.out
    os.makedirs(out, exist_ok=True)
    for name in want:
        co = COS.get(name, name)  # an AW2 CO's name: AW2's own theme, the reference
        g = battle(ctx, co, record=True)
        e = g.e
        song = row_song(e, co)
        ctx.check(wait_song(e, song, 300) or e.u16(SONG) == song, f"{name}: song {song} starts")
        j = songs.get(name)
        secs = (j["intro_s"] + 2 * j["loop_s"] + 2) if j else 80.0
        secs = float(os.environ.get("AW2TEST_MUSIC_SECONDS") or secs)
        e.wait(int(secs * 59.7275))
        raw = os.path.join(out, f"{name}.raw.wav")
        n, rate = e.audio_end(raw)
        clock = e.u32(BGM + 0x0C)  # ticks of the song played so far
        ctx.check(playing(e, song), f"{name}: song {song} still playing")
        bpm = j["bpm"] if j else e.u8(BGM + 0x20) or 0
        # the engine plays tempo/150 ticks a frame at 59.7275 frames a second
        tick_s = 150.0 / (59.7275 * (j["bpm"] if j else 120))
        start = n / rate - clock * tick_s if j else (n / rate - secs)
        trim_from(raw, start, os.path.join(out, f"{name}.wav"))
        os.remove(raw)
        ctx.log(f"{name}: {n / rate:.1f} s recorded from boot, the song began at {start:.2f} s ({clock} ticks played); the WAV starts there")
