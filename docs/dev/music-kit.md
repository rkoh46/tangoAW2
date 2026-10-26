# Music kit: our own songs for AW2's sound engine (`aw2dev sound compose | render | loopcheck | levels | stems | pitchcheck | voices | dump`)

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
| Asuka (92, Versus for everyone) | `asuka.m4t` "Bassline Protocol" | A Phrygian-minor, 120 bpm, 36 bars, 72 s | chopped pick bass 36 (the star), low brass 111 (answers), lead brass 56 (below the bass), plucked clock 117 (a few ticks), timpani 47, kit 120 | a bass-and-timpani groove built from a study of Sturm's theme: a two-bar sixteenth-grid bass riff with rests and accents, kick on the beats and snare on 2 and 4, a two-bar brass hook repeated then varied, a rising second phrase, a breakdown of bass and timpani only, the full return, a step up and home; low band 0.56 (Sturm 0.55) |
| Varro (90, boss only) | `varro.m4t` "Imperium Tenebrarum" | C minor, 84 bpm, 24 bars, 69 s | horns 111, trumpet 56, strings 48, bass 34, timpani 47, pad 26, kit 120 | slow and dark: low horns over a pedal and a heartbeat, a flat second, a long dominant, a trumpet's answer |

All five are original (no existing tune); the voices are AW2's own, so they sound like AW2's themes (same reverb 173, priority 0, the CO themes' music player with 8 tracks and 8 mixed channels).

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

## The commands
| Command | What |
|---|---|
| `aw2dev sound compose [--song N] [--dir D]` | compile the files, print each song's length, notes, **most notes at once** (AW2's own CO themes never sound more than 6 at once, measured on all 19, which leaves the 8 mixed channels two for sound effects; ours keep to 6 and `compose` fails above), tracks, bytes; the rules: loop 45..90 s, at most 8 tracks, 48 KiB |
| `aw2dev sound render [--song N] [--out D] [--dir D] [--seconds S]` | plays each theme in the game (a Versus battle, the CO's turn; the console is recorded from its first frame and cut where the **song** began, read from the music player's tick clock) and writes `<out>/<name>.wav` (default `devkit/work/music/`), then `loopcheck` and `levels`, a picture `<name>.png` (waveform + spectrogram, the seams marked) and `<name>_seams.png` (the signal 0.8 s round each seam). An AW2 CO's name (`kanbei`) records AW2's own theme |
| `aw2dev sound loopcheck WAV [--song N]` | the seams: the period error (ms), the **click** (the largest sample step within 30 ms of the seam over the 99.9th percentile elsewhere: far above 1 is a click), the **gap** (the quietest 20 ms next to it over the 10th percentile of such dips elsewhere: far below 1 is a silence), how alike the passes are (envelope correlation) |
| `aw2dev sound levels [WAV ..] [--ref]` | RMS, peak, the one-second spread and the band balance of recordings next to **AW2's own themes** (ten of them, recorded once into `devkit/work/music/ref`); a theme more than 1.5 dB outside their range fails |
| `aw2dev sound stems SONG` | renders each track alone and prints its loudness against the mix: the lead must lead; tune with `gain=` |
| `aw2dev sound pitchcheck` | one calibration song of every instrument the songs use on C3 G3 C4 G4 C5, played in the game and measured: the `shift` of an instrument is right when the error is under 0.35 semitone |
| `aw2dev sound voices [--group A\|B] [--program N ..] [--sheet PNG]` | AW2's voice entries: type, sample length, loop, two guesses at the `shift` (spectrum and autocorrelation; `pitchcheck` decides), a picture sheet |
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
