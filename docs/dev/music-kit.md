# Music kit: our own songs for AW2's sound engine (`aw2dev sound compose | render | loopcheck | levels | stems | pitchcheck | similar | voices | dump`)

How the Emerald Sun COs got **themes of their own**: songs written as text in this repository, compiled to song data for AW2's own sound engine (MP2K, "Sappy"), played with AW2's own
instruments. Nothing from the game is stored: the instruments (voice entries and their samples) are read from the player's ROM at run time. Skill: `aw2-add-music`.
Code: `tango-gamesupport-aw2/src/es_music.rs` (parser + compiler), `src/ds_music.rs` (placement and the table), `music/es/*.m4t` (the songs), `devkit/aw2/musiclib/` (`tools.py` the commands; `m4a.py` the reader, `audio.py` / `pitch.py` / `viz.py` the analysis)
(the tools), `examples/aw2_es_music.rs` (the compiler as a tool), `tools/aw2test/tests/test_es_music.py` (the game-side tests and the recorder).

| CO | Song | Key, tempo, loop | Instruments (AW2 voice group A) | What it is |
|---|---|---|---|---|
| Klaus (86) | `klaus.m4t` "Legio Aeterna" | D minor, 108 bpm, 32 bars, 71 s | trumpet 56, brass 111, strings 48, bass 34, timpani 47, kit 120 | a stately legion march: fanfare, theme, theme with a second brass, a trio for the strings in F, the theme with everything |
| Aurelia (87) | `aurelia.m4t` "Opus Machinae" | A minor, 128 bpm, 32 bars, 60 s | brass 56/111, plucked ostinato 27, koto 117, pick bass 36, strings 48, kit 120 | an engine: a tresillo ostinato of sixteenths under punchy brass, a bridge for strings and a high pluck, a climbing push with snare rolls |
| Cassius (88) | `cassius.m4t` "Equitatus" | G, 144 bpm, 32 bars, 54 s | horns 56/111, strings 48, bass 34, timpani 47, flute 77, kit 120 | a cavalry gallop (an eighth and two sixteenths every beat), a bugle call, swaggering horns, the charge |
| Livia (89) | `livia.m4t` "Aerarium" | B minor / D, 3/4, 104 bpm, 32 bars, 56 s | flute 23, clarinet 71, harp 117, bass 34, strings 48, small pluck 29, kit 120 | an elegant waltz: harp turns, a refined flute line, a clarinet answer, drums that only count the beat, a chromatic step for the intrigue |
| Asuka (92, Versus for everyone) | `asuka.m4t` "Iron Verdict" | E minor with the flat second, 120 bpm, 4 bar intro + 36 bar loop, 72 s | distortion guitar B.10 (power chords), palm-muted guitar B.11 (chugs), overdriven lead A.38, plucked guitar 27, fuzz bass 97, brass 56 (stabs), timpani 47, kit 120 | an original guitar rock song: a chugging riff in unison with the fuzz bass and a chromatic drop, a lead-guitar hook, a breakdown, a guitar solo with bends and arpeggio sweeps, the hook with everything, a chromatic turnaround into the loop; RMS -19.0 dBFS, peak -3.4; no `rom` lines, `sound similar`: longest run 5 and 0 notes |
| Varro (90, boss only) | `varro.m4t` "Imperium Tenebrarum" | C minor, 84 bpm, 24 bars, 69 s | horns 111, trumpet 56, strings 48, bass 34, timpani 47, pad 26, kit 120 | slow and dark: low horns over a pedal and a heartbeat, a flat second, a long dominant, a trumpet's answer |

Every theme is original (no existing tune, no `rom` reference; `aw2dev sound similar` checks it, "Originality", below). Asuka's was once a mix with Sonja's and Sturm's songs read from the ROM; those mixes stay in `music/es/alt/` as examples of the `rom` feature (docs/dev/asuka.md); the voices are AW2's own, so they sound like AW2's themes (same reverb 173, priority 0, the CO themes' music player with 8 tracks and 8 mixed channels).

## The pipeline
1. **Text song** (`music/es/<name>.m4t`) -> `es_music::compile` (parse, expand patterns, check every bar adds up and every track fills its section, write the loop) -> **MP2K track bytes** (one stream a track:
   state block, intro, label, the state again, loop body, `GOTO label`; a state block at the label makes every pass start alike) + a header (tracks, priority 0, reverb 173) + a **voice group**.
2. `ds_music::build` (the same function that places the Dual Strike pack's converted music) puts each song in the music's free ROM, **after the power themes** in the story's range
   (`0x09000000..0x09BFFFFF`, `STORY_BASE`), and gives it the **last rows of the song table** (so every earlier id keeps its number: the ten Dual Strike themes are 505..514, the Emerald Sun themes 545..549 with the pack).
3. `ds_music::install` (on the first tick, like everything else the pack writes) copies each song's voice group from the ROM: slot n of the song is entry `index` of AW2's group `A` (`0x08240FB0`, Kanbei's and Sensei's) or `B`
   (`0x082415C8`, Hawke's and Jess's). The 12-byte entries keep the ROM's sample, key-split and drum-kit pointers, so the samples are never copied.
4. `co_roster::new_row` writes `ds_music::song(co)` into the CO's row (`+4`): the CO's turn plays it wherever AW2 plays a CO's theme (battle turns; the CO select screen has one song, 400, for every CO and the CO page none).
   Campaign scenes name it with `@SONG co:klaus` (`campaign_music::Track::Co`, resolved through `ds_music::song`).
Powers: the game's own power themes (with the pack, Dual Strike's converted ones) play as for every CO; nothing per CO.

## The song format (`es_music.rs` header has the full reference)
```
song klaus                       tempo 108      meter 4/4      reverb 173      priority 0
inst trumpet = A.56 shift=-12    ; slot: group A/B or 0x08xxxxxx, program, shift
hit kick=36 snare=40 hat=44      ; names for a drum kit's keys
track 1 inst=trumpet vol=84 pan=0 vel=108 gate=88 gain=1.45     ; also bendr= mod= lfos= lfodl= trans=
def thA:  | D5/4. C5/8 D5/4 A4/4 | ...   end                       ; a pattern: @thA, @thA+2 (transposed), @thA*2 (twice)
section A bars=8                                                  ; the order in `form`; every track's line must fill the section
  1: {vol 84} @thA
  6: @mA*7 @roll
end
form intro loop A A2 B A3        ; `loop` marks where the repeat starts
```
Notes are written at the **sounding pitch** (`C4` = middle C); `shift` turns that into the key the sample needs, because AW2's samples are recorded at different octaves. `/4 /8 /16 /4. /8t /2+8 /#30`
are durations (24 ticks a beat, MP2K's), `[C3 G3]/2` a chord, `kick/8` a drum hit, `r/4` a rest, `'` staccato, `_` legato, `>` accent, `!90` velocity, `{vol 60>100/48}` a ramp, `{pan -20}` `{inst x}` `{bend 8}`
`{mod 6}` `{gate 70}` `{tempo 120}` (first track), `|` a bar line (**checked**: a bar of the wrong length is an error with its place). `gain=` on a track scales every volume of it: **the mix is one number a track**.

## The instruments (from `aw2dev sound voices`, checked by `aw2dev sound pitchcheck`)
AW2's voices have no release (envelope 255,0,255,0): a note ends when its length does, and a sample without a loop dies away by itself. Verified in the game (a scale on each, measured by autocorrelation; all within 0.3 semitone):
| Program | Sounds like (by spectrum and by what AW2's themes use it for) | `shift` |
|---|---|---|
| A.56 | bright brass, the lead of AW2's marches (Olaf, Drake, Sensei) | -12 |
| A.111 | rich brass, a pad in Kanbei's theme | -12 |
| A.110, A.77, A.23 | pure, breathy reeds and flutes (23 has its own vibrato) | -12 |
| A.71 | clarinet (odd harmonics) | -12 |
| A.48 | string ensemble (sawtooth with chorus) | 0 |
| A.26 | slow swelling pad | 0 |
| A.27, A.25 | plucked strings (guitar, banjo) | +12 |
| A.117 | koto / harp pluck | 0 |
| A.29 | small bright pluck | 0 |
| A.34, A.36 | bass (34 an electric bass, 36 a pick bass; the fundamental is weak: the second harmonic is the strong one) | +24 |
| A.47 | timpani (a one-shot; reads right from about C1 to C4) | +24 |
| A.120 | the drum kit: kick 36, side stick 37, clap 39, snare 40, tom 43/45/48/50, closed hat 44, open hat 46, crash 49/57 | (keys) |
The sound is chosen by the numbers (spectrum, envelope, pitch) and by the role AW2 gives the program in its own themes (`aw2dev sound dump 211` prints Kanbei's tracks): **the choice has not been heard by an ear**;
an instrument is one `inst` line, so swapping it is a one-line change. `aw2dev sound voices --sheet out.png` draws every sample's waveform and spectrogram.

## Guitar voices (measured in the game, `aw2dev sound render` of one voice on E2/E3/E4 and of 16th chugs; Asuka's "Iron Verdict" is built from them)
Group B is Hawke's (the rock voices); a song may use slots of both groups (`inst rg = B.10 shift=20`).
| Voice | Sounds like (measured) | `shift` | Use |
|---|---|---|---|
| B.10 | **distortion guitar**: a loop sampled at E2 (the low string); weak fundamental, strong 3rd to 4th harmonics, 76% of a chopped note's energy above 2 kHz (fizz); quiet (-28 dBFS at vol 100 / vel 110: use vol 127) | +20 | sustained power chords (2 notes), never chopped (a cut note is all fizz). `pitchcheck` reads C5 an octave low (the analysis, not the voice); keep it E2 to B3 |
| B.11 | **palm-muted guitar**: one-shot at E2 that dies away by itself; 65% of its energy under 250 Hz, loud (-20 dBFS on 16th chugs) | +20 | the 16th chugs, at gate 100 and vol about 60% of B.10's |
| A.38 | **overdriven lead guitar**: sustained loop, 3rd and 4th harmonics strongest, almost nothing above 2 kHz, loud (-21 dBFS) | +12 | the lead: bends, scoops, vibrato; clean from B3 to C5 (grit 13 to 22 dB) |
| A.27 | plucked guitar (decays), the arpeggios of sketch N | +12 | sixteenth arpeggios, an octave doubling |
| A.97 | fuzz bass (grit by design 0 to -2 dB) | +24 | locked with the rhythm guitar |
Not chosen: A.24 / A.59 (sustained saw-like synths), B.57 (a sync lead, pitch unreliable above C5), B.12 / B.0 / B.2 (noise), A.25 (banjo), the rest are one-shot effects. Pitch bends work: `bendr=12` on the track, then `{bend 0>-63/94}` (a dive of an octave over a note), `{bend -10>0/10}` (a scoop), `{bend 10>0/12}` (a released pre-bend); vibrato needs `lfos=40 lfodl=12` and `{mod 14}` (about 0.5 semitone; the default `lfos` is 0, no vibrato). A note ends the instant its length does (no release): palm mutes are short gates on B.11, never on B.10.

## Quoting AW2's songs (`rom`): nothing of them in the repository (a kit feature; no shipped song uses it)
The game's themes do not quote anything any more (`no_shipped_theme_references_aw2_songs`; `install_quotes` only runs for a song with `rom` lines, so for none that ships); the examples in `music/es/alt/{ns,ns2,ss,ss3}/` do. AW2's own songs are Nintendo's and Intelligent Systems' music. **Their notes must never be written into this repository** (no transcription into an `.m4t`, no copied note table, no note names of a melody in a document or a test, no WAV: it is public). A song of ours can still quote one the way the game does everything else of AW2's: it names the stretch and the game reads it from the player's ROM when it builds the song.
```
rom hook song=212 track=0 bars=7-10 transpose=-12 srcshift=-12 lower=G#,C# peak=84 inst=low   ; a name and its parameters
section A2 bars=8
  5: @rom:hook @rs*4          ; plays it here: (b - a + 1) bars of the source (96 ticks each)
```
| Option | Meaning |
|---|---|
| `song=` `track=` `bars=a-b` | AW2's song id (0..504; `aw2dev sound list --source aw2`), its track (0-based, `sound dump N`), the source bars to copy (1-based; `barticks=` if a bar is not 96 ticks) |
| `transpose=` `srcshift=` | semitones to move the **sounding** pitch; the `shift` of the source's voice (`sound voices`) so its sounding pitch is known; the target voice's own `shift` is added |
| `lower=G#,C#` | lower those pitch classes by a semitone after transposing (a major tune made minor: a "darkened" quote) |
| `inst=` | play it on one of our `inst`s and then go back to the track's voice; without it, the track's current voice |
| `gain=` `peak=` | a factor on the source's own volumes; `peak=84` first brings the loudest of them to 84 (the quote is as loud as we say, before the track's `gain=`) |
| `tempo=` | the source's tempo, to keep its real speed (ticks scaled by ours / it; must give whole bars); left out, ticks are copied and the quote plays at **our** tempo |
| `raw` | keys, volumes, pans and the source's own voices unchanged (a drum kit or a bass of AW2's, as it is) |
The reference starts on a bar line and is a whole number of our bars. The game copies the notes (tied notes get their length), the volume, bend and vibrato commands and, with `raw`, pan and voice; the source's patterns and repeats are expanded as the sound engine does (`src/es_rom.rs`), and only its first pass is read.
**Build**: `ds_music::build` lays the song out with room for it (`REF_TRACK_CAP`, 4 KiB a quoting track, and 40 voice slots; a track that does not fit is an error), and `install_quotes` compiles it again with the ROM the game is running (`es_music::compile_with`) and writes the bytes (loop labels, the voice entries from AW2's groups) on the first tick of the music. **Without a ROM** (`es_music::compile`, the CI tests, `sound compose` without a ROM) a reference is only checked and plays silence of the right length.
**Determinism**: the ROM is the same on every peer (the game already relies on that) and the reader and compiler are pure functions of it, so peers build identical bytes. Tests: the `es_music` unit tests (a made-up ROM: the transposed, lowered notes; the same bytes twice; `raw`; the errors), `the_real_rom_builds_every_quoting_song_the_same_twice` (`-- --ignored`, the real ROM) and `es_themes_are_registered` (the running game holds the compiler's bytes, built with the ROM).
**The source is only read.** Asuka's song has its own table row and data at the end of the table; AW2's rows and bytes (Sonja's 212, Sturm's 219) are never written. `aw2dev co verify sonja` (group `music` of `test_sonja_untouched.py`) compares the song table row, header, voice group and every track's bytes of both with v0.8.7's.

## Grit and headroom (a mix that sounds "a little distorted")
Measured on the game's own output while finding why Asuka's Sturm + Sonja mix (alt SS) sounded distorted; `sound stems` and `sound levels` now report both.
- **Headroom**: the mix peaks at -4.6 dBFS (Sturm's own song: the same); no sample reaches 0.99 of full scale (`levels` prints `CLIPPED n samples` if one does); the sum of the six solo stems differs from the mix by a steady -24 dB (the mixer's rounding), with no burst a stolen note would leave. So the GBA mixer was not saturating and no note was stolen.
- **Grit**: a sample played far below its recorded key is crunchy (the mixer repeats samples instead of interpolating them). `audio.grit` is the median harmonic-to-noise ratio of the steady notes. A calibration (one whole note each on E1 .. B4, the game's output): brass **56** 20 to 23 dB from E1 to B4; strings 48 10 to 18 dB; horn **111** 15 to 17 dB from E2 to B3 but **7 dB on E1 and B1** (34 to 44 semitones under its recorded key). Rule: keep a low stack on 56, or on 111 no lower than E2; a fuzz voice such as Sturm's bass 97 reads 3 dB by design, a drum kit reads nonsense.
- **Harmony**: a quote must agree with the backing's chords. Check a chroma (pitch classes per half second) of the quote's solo stem against the others before lowering notes ("darkening") a tune: Sturm's lead holds an E major chord (E G# B), so a quote lowered to G natural sat a sustained semitone from his G#.

## Originality (`aw2dev sound similar`)
A song of ours must not be a copy of one of AW2's. `similar FILE.m4t --against rom:212,rom:219` compiles the file, takes each pitched track's melodic line (the top note of a chord; drum voices left out) and the same for every track of the named AW2 songs
(read from the player's ROM **for the comparison only**: nothing is written down), and scores every pair of tracks (`devkit/aw2/musiclib/similar.py`):
- **run**: the longest run of notes with exactly the same intervals (transposition does not matter). Only runs with 3 or more distinct pitches count (a repeated note is in every song). Fails at **6 notes**.
- **contour**: the longest run with the same gaps between onsets (6-tick steps) and the same up / down / same steps, with two kinds of gap and two kinds of step. Fails at **8 notes**.
- **bars**: the share of our bars (4 or more notes) with the same onset pattern (Jaccard 0.9 on the sixteenth grid) and the same intervals as one of their bars. Fails at **20%**.
A file with a `rom` line fails by itself. Default `--against` is Sonja's 212 and Sturm's 219; `m4t:FILE` compares with another of our songs. Checked: the old SS3 mix fails (a 61-note run, 100% of the bars), the old NS theme fails on its quote (9 and 19 notes); the shipped Asuka passes
(longest run 5 and 0 notes, contour 0, bars 0%). A short bass figure can match by chance (a root, a third, a fifth): the tool names the pair and the fix is to change the figure. Tests: `test_musiclib.py` `Similar` (made-up melodies), and the shipped files in the suite's music group.

## The commands
| Command | What |
|---|---|
| `aw2dev sound compose [--song N] [--dir D]` | compile the files (with the ROM, so `rom` references are read), print each song's length, notes, **most notes at once** (AW2's own CO themes never sound more than 6 at once, measured on all 19, which leaves the 8 mixed channels two for sound effects; ours keep to 6 and `compose` fails above), tracks, bytes; the rules: loop 45..90 s, at most 8 tracks, 48 KiB |
| `aw2dev sound render [--song N] [--out D] [--dir D] [--seconds S]` | plays each theme in the game (a Versus battle, the CO's turn; the console is recorded from its first frame and cut where the **song** began, read from the music player's tick clock) and writes `<out>/<name>.wav` (default `devkit/work/music/`), then `loopcheck` and `levels`, a picture `<name>.png` (waveform + spectrogram, the seams marked) and `<name>_seams.png` (the signal 0.8 s round each seam). An AW2 CO's name (`kanbei`) records AW2's own theme |
| `aw2dev sound loopcheck WAV [--song N]` | the seams: the period error (ms), the **click** (the largest sample step within 30 ms of the seam over the 99.9th percentile elsewhere: far above 1 is a click), the **gap** (the quietest 20 ms next to it over the 10th percentile of such dips elsewhere: far below 1 is a silence), how alike the passes are (envelope correlation) |
| `aw2dev sound levels [WAV ..] [--ref]` | RMS, peak, the one-second spread and the band balance of recordings next to **AW2's own themes** (ten of them, recorded once into `devkit/work/music/ref`); a theme more than 1.5 dB outside their range fails |
| `aw2dev sound stems SONG` | renders each track alone and prints its loudness against the mix: the lead must lead; tune with `gain=`; also each track's **grit** (harmonic-to-noise ratio of its steady notes; to compare one voice with another) and the mix's peak against full scale (see "Grit and headroom") |
| `aw2dev sound pitchcheck` | one calibration song of every instrument the songs use on C3 G3 C4 G4 C5, played in the game and measured: the `shift` of an instrument is right when the error is under 0.35 semitone |
| `aw2dev sound voices [--group A\|B] [--program N ..] [--sheet PNG]` | AW2's voice entries: type, sample length, loop, two guesses at the `shift` (spectrum and autocorrelation; `pitchcheck` decides), a picture sheet |
| `aw2dev sound similar FILE.m4t [--against rom:212,rom:219]` | the originality check (below) |
| `aw2dev sound dump SONG_ID [--track N]` | AW2's own song as text: how its themes are written |
Edit a song and hear it **without a rebuild**: `TANGOAW2_ES_MUSIC=<dir>` (or `--dir`) makes the game read `<dir>/<name>.m4t` (a development aid, `env-aids.md`; the built-in text is what ships).

## Verification (what was measured, `aw2dev sound render` on the committed songs; WAVs and pictures are made on demand and never committed)
- Pitch: `pitchcheck` puts every instrument the songs use within 0.3 semitone of the written pitch on C3 .. C5 (the timpani from C1 to C4: it is a one-shot, an octave off above); the pitch classes of each recording (chromagram) are the written key's.
- Polyphony: at most 6 notes at once in every song, like AW2's own CO themes (measured on all 19: 4 to 6), so the sound effects always have their channels.
- Loops: every loop seam (the end of each pass) has no click (the biggest step is 0.4x to 1.35x the 99.9th percentile elsewhere) and no silence (the quietest 20 ms next to it is 1.1x to 1.8x a typical dip); the intro's end is quiet only where the music is (Cassius, Livia, Varro: 0.34 to 0.49x, a held note or a harp before the theme enters);
  passes repeat with envelope correlation 0.875 to 0.955 and a period within 30 to 40 ms of the written one (a frame of the GBA's 59.73 Hz is 16.7 ms).
- Levels (RMS of the game's output, after the intro): klaus -21.6, aurelia -21.5, cassius -20.9, livia -21.0, varro -19.8 dBFS; peaks -3.2 to -5.2 dBFS. AW2's ten reference themes: -23.3 to -18.8 (median -21.2) and peaks -3.4 to -8.1.
  Each song's lead is 2.6 to 4.7 dB above its next track (`sound stems`; Livia's flute and clarinet alternate and sit within 0.4 dB of each other).
- Registered: `es_themes_are_registered` reads the song table, the headers, the voice groups, every track's bytes and the loops' labels back **from the running game**, and checks that no piece lies over another or outside the story's range (the same kind of check as the army skin's rooms:
  a Dual Strike backup once lay over a skin's table). `ds_music::pack_tests::es_themes_fit` (ignored without the Dual Strike ROM: `cargo test -p tango-gamesupport-aw2 ds_music -- --ignored`) does it for the blob; `cargo test es_music` for the compiler.
- Plays: `es_theme_plays_on_the_cos_turn_and_loops` plays each theme through its intro and a whole loop (still playing, no silent second, AW2's 8 channels); `es_theme_returns_after_a_power_and_other_cos_keep_theirs`: the game's power theme in a power,
  AW2's own Kanbei song on the CPU Kanbei's turn, the theme again on the next turn. In the campaign: `aw2dev campaign trace --campaign es --mission 1 3 6` plays M1 (Klaus's 545), M3 (Aurelia's 546) and M6 (Livia's 548) with no silent sample in their scenes.

## Determinism
The songs, their bytes and their addresses are a pure function of the text files and the pack (`music()` builds once; `the_same_text_gives_the_same_bytes`); the voice groups are copied from the ROM, which is the same on both peers; the
song table is only changed with the pack on (like the rest of the Dual Strike music), so a room without the pack plays AW2's. The development variable `TANGOAW2_ES_MUSIC` must not differ between peers (like the other `TANGOAW2_ES_*` aids).
Check: `aw2dev net repeat` (8 runs, equal hashes) with the build that carries the songs. The themes of unreleased COs change no shared state in a match without them; **the release that lists the Emerald Sun COs in Versus bumps `sim_version`** (their themes, powers and numbers all change the shared console).

## Adding or changing a song
1. Write `music/es/<name>.m4t` (copy a neighbour). `aw2dev sound compose --dir tango-gamesupport-aw2/music/es` until it compiles and keeps the rules.
2. `aw2dev sound render --song <name> --dir tango-gamesupport-aw2/music/es`: listen to the WAV, look at the pictures, read the levels; `sound stems` and `gain=` for the mix; `sound pitchcheck` if you use a new instrument.
3. A new CO's song: add it to `es_music::SOURCES` (the CO id), the test's `COS`, the suite's `es_music` entry takes it from there; a campaign scene uses `@SONG co:<name>` (`es_text.rs co_by_name`).
4. `aw2dev build --all`, `aw2dev test`, `aw2dev suite --only es_music`.
Not committed, never: WAVs, pictures, anything from the ROMs.
