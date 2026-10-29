"""The new COs' own Dual Strike themes (crate::ds_music): with the pack each new
CO's turn plays its song (converted from the .nds, ids from 505), human or CPU,
in two- and five-army games, and it loops; across a power and a battle scene
nothing breaks; AW2's COs keep their music. Recordings of each theme go to the
test's output folder, or to $AW2TEST_MUSIC_OUT."""

import os

from aw2test import rom as romlib
from aw2test.harness import test

NEW = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel", "cloneandy"]
SONG = 0x030005CA  # the song id the game last started (sub_0803B524)
BGM = 0x03005AE0  # the CO themes' music player: song header, status
CO_TABLE = 0x086A0000  # tangoAW2's CO table with the pack (co_roster.rs)
AW2_CO_TABLE = 0x085D3DD0
ROW = 0x104
FIRST_SONG = 505
SONG_TABLE_POOL = 0x080704A0


def row_song(e, co, table=CO_TABLE):
    return e.u16(table + ROW * romlib.co_id(co) + 4)


def header_of(e, song):
    return e.u32(e.u32(SONG_TABLE_POOL) + 8 * song)


def wait_song(e, song, frames=1200):
    for _ in range(frames):
        if e.u16(SONG) == song:
            return True
        e.wait(1)
    return False


def playing(e, song):
    """The music player plays `song` and has live tracks."""
    return e.u32(BGM) == header_of(e, song) and e.u32(BGM + 4) & 0x80000000 == 0 and e.u32(BGM + 4) & 0xFFFF != 0


def channels(e):
    return e.u8(e.u32(0x03007FF0) + 6)


def out_dir(ctx):
    return os.environ.get("AW2TEST_MUSIC_OUT") or ctx.out


def two_armies(ctx, cos, humans, visuals="off"):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    return ctx.start(m, cos, humans=humans, visuals=visuals)


OWN_SONG_COS = ["cloneandy"]          # (Clone Andy, Crumb, Asuka and Aria play songs of ours: music/es/*.m4t, music/bh2/aria.m4t, crate::es_music, after the pack's)


@test(modes=("ds",))
def new_cos_have_their_own_songs(ctx):
    """Nine new COs have a Dual Strike theme (converted, from 505); Clone Andy has a song of ours instead (`Copy Protocol`, crate::es_music: a row after the pack's songs, not Andy's Dual Strike theme)."""
    g = two_armies(ctx, ["andy", "sami"], (1,))
    e = g.e
    songs = [row_song(e, co) for co in NEW]
    ctx.log(f"songs: {dict(zip(NEW, songs))}")
    ds_cos = [c for c in NEW if c not in OWN_SONG_COS]
    ds_songs = [row_song(e, c) for c in ds_cos]
    ctx.eq(sorted(ds_songs), list(range(FIRST_SONG, FIRST_SONG + len(ds_cos))), f"{len(ds_cos)} Dual Strike songs, from 505")
    own = {c: row_song(e, c) for c in OWN_SONG_COS}
    for c, s in own.items():
        ctx.check(s >= FIRST_SONG + len(ds_cos) and s not in ds_songs, f"{c} plays a song of ours ({s}), not one of the Dual Strike themes")
    ctx.eq(len(set(songs)), len(songs), "every new CO has a song of its own")
    for co, s in zip(NEW, songs):
        h = header_of(e, s)
        ctx.check(0x08800000 <= h < 0x0A000000, f"{co}: song {s} header {h:08x} after the cartridge")
        ctx.check(1 <= e.u8(h) <= 8, f"{co}: {e.u8(h)} tracks")
    for co in range(19):
        ctx.eq(row_song(e, co), row_song(e, co, AW2_CO_TABLE), f"{romlib.co_name(co)} keeps AW2's music")
    for s in (1, 200, 219, 412, 503):
        ctx.eq(header_of(e, s), e.u32(0x0824238C + 8 * s), f"song {s} is AW2's")


@test(modes=("ds",))
def crumb_asuka_and_aria_play_their_own_themes(ctx):
    """Crumb ("Marching Off-Step"), Asuka ("Iron Verdict") and Aria (the BH2 final theme) have songs of ours (crate::es_music): rows after the pack's, none is Adder's or Nell's AW2 song."""
    g = two_armies(ctx, ["crumb", "sami"], (1,))
    e = g.e
    adder, nell = row_song(e, "adder", AW2_CO_TABLE), row_song(e, "nell", AW2_CO_TABLE)
    seen = []
    for co in ("crumb", "asuka", "aria"):
        s = row_song(e, co)
        h = header_of(e, s)
        ctx.check(s >= FIRST_SONG + 9, f"{co}: song {s} is one of ours, after the Dual Strike themes")
        ctx.check(s not in (adder, nell), f"{co}: not Adder's or Nell's song")
        ctx.check(0x08800000 <= h < 0x0A000000 and 1 <= e.u8(h) <= 8, f"{co}: header {h:08x} after the cartridge, {e.u8(h)} tracks")
        seen.append(s)
    ctx.eq(len(set(seen)), 3, "three different songs")


@test(modes=("aw2",))
def co_music_without_the_pack(ctx):
    g = two_armies(ctx, ["andy", "sturm"], (1,))
    e = g.e
    ctx.eq(e.u32(SONG_TABLE_POOL), 0x0824238C, "AW2's song table")
    ctx.eq(e.u16(SONG), row_song(e, "andy", AW2_CO_TABLE), "Andy's music")
    ctx.eq(channels(e), 8, "8 channels mixed")


@test(modes=("ds",))
def each_new_co_turn_plays_its_song(ctx):
    """Human on army 2: ending army 1's turn starts the new CO's song; 20 s of
    it are recorded (<co>_tangoaw2.wav; Von Bolt 60 s)."""
    for co in NEW:
        g = two_armies(ctx, ["andy", co], (1, 2))
        e = g.e
        song = row_song(e, co)
        ctx.eq(e.u16(SONG), row_song(e, "andy"), f"{co}: Andy's music first")
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
        ctx.check(wait_song(e, song), f"{co}'s turn starts song {song}")
        e.audio_start()
        e.wait((60 if co == "vonbolt" else 20) * 60)
        n, rate = e.audio_end(os.path.join(out_dir(ctx), f"{co}_tangoaw2.wav"))
        ctx.check(playing(e, song), f"{co}: song {song} playing after 20 s")
        ctx.eq(channels(e), 12, f"{co}: 12 channels while it plays")
        ctx.log(f"{co}: {n / rate:.1f} s recorded")


@test(modes=("ds",))
def cpu_new_cos_play_their_songs(ctx):
    for co in NEW:
        g = two_armies(ctx, ["andy", co], (1,))
        e = g.e
        song = row_song(e, co)
        seen = []
        g.end_turn(observe=lambda gg: seen.append(wait_song(gg.e, song, 600)))
        ctx.check(seen == [True], f"the CPU {co}'s turn plays song {song}")
        ctx.check(wait_song(e, row_song(e, "andy"), 600), f"back to Andy's music after the CPU {co}")
        e.wait(2)
        ctx.eq(channels(e), 8, "8 channels with AW2's music")


@test(modes=("ds",))
def von_bolt_song_loops(ctx):
    """Von Bolt's theme reaches its loop point after about 1:40: after 3
    minutes it still plays."""
    g = two_armies(ctx, ["vonbolt", "andy"], (1,))
    e = g.e
    song = row_song(e, "vonbolt")
    ctx.check(playing(e, song), f"Von Bolt's song {song} plays")
    e.wait(180 * 60)
    ctx.check(playing(e, song), "still playing after 3 minutes (looped)")
    ctx.eq(channels(e), 12, "12 channels")


@test(modes=("ds",))
def von_bolt_power_and_battle(ctx):
    """Von Bolt's Super CO Power (AW2's Black Hole power music), a battle scene,
    then his next turn starts his song again."""
    g = two_armies(ctx, ["vonbolt", "andy"], (1,), visuals="a")
    e = g.e
    song = row_song(e, "vonbolt")
    ctx.check(playing(e, song), "Von Bolt's song")
    ctx.power(g, 1, "super")
    ctx.log(f"after the power: song {e.u16(SONG)}")
    ctx.check(e.u16(SONG) != song, "the power's music")
    ctx.attack(g, (10, 6), (10, 6), (11, 6))
    ctx.log(f"after the battle: song {e.u16(SONG)}")
    g.end_turn()
    ctx.check(wait_song(e, song, 600), "his next turn plays his song again")
    e.wait(2)
    ctx.eq(channels(e), 12, "12 channels")


@test(modes=("ds",))
def von_bolt_five_armies(ctx):
    hq = ((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19))
    m = ctx.map(hq=hq)
    m.terrain(15, 2, 0x1B4)
    for a, x in ((1, 3), (2, 26), (3, 25), (4, 4), (5, 15)):
        m.unit(a, "infantry", x, 10)
    m.colours = [5, 1, 2, 3, 4]
    g = ctx.start(m, None)
    e = g.e
    # Every army a CPU; army 1 (Black Hole) plays Von Bolt from its next turn.
    vb = romlib.co_id("vonbolt")
    e.w8(g.player(1)["addr"] + 0x1D, vb)
    ctx.log(f"armies' COs: {[g.player(a)['co'] for a in range(1, 6)]}")
    ctx.eq(g.player(1)["co"], vb, "army 1 is Von Bolt")
    song = row_song(e, "vonbolt")
    seen = []
    g.end_turn(observe=lambda gg: seen.append(gg.e.u16(SONG)))
    ctx.check(wait_song(e, song, 3000) or e.u16(SONG) == song, f"army 1's turn: Von Bolt's song {song}")
    ctx.log(f"now {e.u16(SONG)}, day's songs {seen}")
    ctx.check(e.u8(0x030033EC) == 1, "army 1's turn")
    ctx.check(not g.battle_over(), "the battle goes on")


STORY_BASE = 0x09000000  # crate::ds_music::STORY_BASE: the DS Campaign's songs, then the tag sounds and the power themes


def loudness(path):
    """(RMS, peak) of a 16-bit WAV."""
    import array
    import math
    b = open(path, "rb").read()
    s = array.array("h", b[44:])
    if not s:
        return 0, 0
    return math.sqrt(sum(x * x for x in s[::7]) / len(s[::7])), max(abs(x) for x in s)


@test(modes=("ds",))
def power_music_is_dual_strikes(ctx):
    """crate::power_music: Andy's CO Power plays Dual Strike's BGM_BREAK_ALLY1, Lash's Super Power
    BGM_SPECIAL_BREAK_ENEMY1 (three songs on: the power themes are converted in POWER_SONGS' order), each on the themes'
    player with 12 channels; the next turn's day-to-day theme comes back. 10 s of each are recorded
    (power_<name>.wav)."""
    g = two_armies(ctx, ["andy", "lash"], (1, 2))
    e = g.e
    andy, lash = row_song(e, "andy"), row_song(e, "lash")
    ctx.power(g, 1, "power")
    cop = e.u16(SONG)
    ctx.log(f"Andy's CO Power: song {cop}, header {header_of(e, cop):08x}")
    ctx.check(cop >= FIRST_SONG and header_of(e, cop) >= STORY_BASE, f"a Dual Strike song plays ({cop}), not AW2's 0x1A4")
    e.wait(30)
    ctx.check(playing(e, cop), "it plays")
    ctx.eq(channels(e), 12, "12 channels while it plays")
    e.audio_start()
    e.wait(600)
    path = os.path.join(out_dir(ctx), "power_ally.wav")
    e.audio_end(path)
    rms, peak = loudness(path)
    ctx.log(f"CO Power (Allied): RMS {rms:.0f}, peak {peak}")
    ctx.check(rms > 300 and peak < 32767, "it is heard, and not clipped flat")
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.check(wait_song(e, lash), "Lash's turn: her theme")
    g.wait_for_input()
    ctx.power(g, 2, "super")
    ctx.eq(e.u16(SONG), cop + 3, "Lash's Super Power: BGM_SPECIAL_BREAK_ENEMY1 (Black Hole)")
    e.wait(30)
    ctx.check(playing(e, cop + 3), "it plays")
    e.audio_start()
    e.wait(600)
    path = os.path.join(out_dir(ctx), "power_bh_super.wav")
    e.audio_end(path)
    rms, peak = loudness(path)
    ctx.log(f"Super (Black Hole): RMS {rms:.0f}, peak {peak}")
    ctx.check(rms > 300 and peak < 32767, "it is heard, and not clipped flat")
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.check(wait_song(e, andy), "Andy's turn: his theme again (the power over)")
    g.wait_for_input()
    e.wait(2)
    ctx.eq(channels(e), 8, "8 channels with AW2's music")


@test(modes=("aw2",))
def power_music_without_the_pack(ctx):
    g = two_armies(ctx, ["andy", "lash"], (1,))
    ctx.power(g, 1, "power")
    ctx.eq(g.e.u16(SONG), 0x1A4, "AW2's CO Power music")
