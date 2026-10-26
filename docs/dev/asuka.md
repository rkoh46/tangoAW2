# Asuka (CO 92)

Black Hole's intelligence chief, tangoAW2's own CO. **Lore** (the CO page says it without naming her old self): once an Allied intelligence officer, she took the name Asuka on joining Black Hole, and with it a power
far beyond her old self. (Developer note: she is Sonja after she defects; "Asuka" is Sonja's Japanese name. The CO page and quotes never name Sonja, players are left to work it out, and the BH2 story is not spoiled.)
Code `tango-gamesupport-aw2/src/asuka.rs` (constants and the design in its header), the pieces in `co_new.rs` (`ASUKA`, `all()`, `like`, `is_own`, the texts, her presentation row), `co_roster.rs` (`ds_co`, `stat`:
the +5%, the stars), `co_powers.rs` (`asuka_fn`, the ammo halving in `mass_unit`), `es_cos.rs` (her art and texts, the table of the Emerald Sun portraits), `ds_co_page.rs` (CO page), `sturm_pairs.rs` (her pairs), `es_music.rs` (`SOURCES`: her theme),
`ds_ai.rs` (the CPU plays her with Hawke's profile). Data `cos/asuka.toml`, `cos/tags.toml`, art `art/cos/asuka/`, song `music/es/asuka.m4t`.

## Her theme
`music/es/asuka.m4t` is now **"Fingers of Fate" with Sonja's theme quoted from the ROM** (the final theme, below; "Cold Iron Fingers", the K + N combination, was the one before it); the text in this paragraph describes the sixth take **"Bassline Protocol"**, which it replaced. Round 1 ("Cold Reckoning" and the three remixes at 72-112 bpm) was rejected as slow, moody and ambient ("Sturm's track was a banger, make a banger"); round 2 ("Cipher Command" at 152 bpm, "Clockwork Chase", "Event Drive" at 148-158) was rejected for a tempo "way too fast"; the user also said it must not be slow. **Round-3 lessons: tempo matters more than intensity** (stay at 112-132 bpm, Sturm is 120, and drive from the sixteenth grid, not from a fast tempo), and **the bass carries Sturm**: low band 0.55 of its energy against 0.33 in the round-2 takes. Make the bass the loudest track, a chopped syncopated ostinato where the rests and accents are the groove, answered by a low brass, with timpani hits and rolls; keep the lead *below* the bass in the mix; measure `sound render`'s low/mid/high split (low is under 250 Hz) and aim at 0.5-0.56.
A Phrygian-minor (the Bb), **120 bpm**, 2 intro bars + 36 bars (**72 s loop**), 5 notes at most (6 tracks). The pick bass (36, gain 2.2, the loudest stem at -25.2 dBFS with timpani -24.5) runs a two-bar riff of sixteenths with rests (A, the flat second Bb, C, E, a drop to G): that riff is the tune. A low brass (111) answers on the off beats, the lead brass (56, -30.4 dBFS, 5 dB under the bass) plays a two-bar hook (`A A C Bb A . E` / `A A C E D C`), repeated, then varied, her clock is a few plucked (117) ticks on E6.
Form: intro (2 bars: bass and timpani), **A** (hook repeated, varied; kick on the beats, snare on 2 and 4, a tom fill every fourth bar), **B** (a rising second phrase over a bass climbing a minor third then a fourth), **BR** (4 bars, bass and timpani roll only, a tom run into the return), **R** (the full return, the low brass doubling the hook an octave down), **C** (a whole step up for six bars, then home).
Levels RMS -19.8 dBFS (Sturm -19.6), peak -3.7, **low/mid/high 0.56 / 0.36 / 0.09** (Sturm 0.55 / 0.37 / 0.08), seams click 1.14x / gap 1.2x-1.3x, passes alike 0.97; `pitchcheck` within 0.3 semitone (the bass was also checked on G1 to A2: right pitch, 2nd harmonic strong).
**Two other takes were made and kept out of the build** (swapping is one file): **H "Brass Directive"** (G Phrygian-minor, 124 bpm, 70 s: a long-note brass hook with a low brass doubling, low band 0.48) and **I "Pulse Engine"** (B Phrygian-minor, 130 bpm, 67 s: an upbeat, busier sixteenth bass that never stops, double kicks and ghost snares, low band 0.52). The earlier rejected rounds are not kept.

### What makes Sturm's theme (AW2 song 219) a banger, and what her theme takes from it
Studied with `aw2dev sound dump 219`, `sound voices`, a recording (`sound render --song sturm`, RMS -19.6 dBFS, peak -4.6, band split low/mid/high 0.55 / 0.37 / 0.08, centroid 833 Hz) and the other Black Hole themes (`sound dump 217 .. 220`: tempo values 63, 80, 60, 60 = 126, 160, 120, 120 bpm).
- **Tempo and grid**: 120 bpm (MP2K `TEMPO 60`), but nearly all of it sits on a **sixteenth grid** (6 ticks): the ear hears 240 pulses a minute. Black Hole's song 218 is 160 bpm. Hers goes 148 to 158 bpm on the same grid.
- **A bass ostinato that never stops**: track 3 is a looping bass-synth sample (voice 97) on E, chopped into one-tick stabs on the sixteenth grid with a chromatic neighbour (D# and F around the E): a gated, rhythmic, minor-second-flavoured drive; a second low voice (96) nails the root and fifth on the bar lines. The tune is in what the bass *does*, not in a chord progression.
- **Drums**: two percussion tracks. A kit track (120) with short hits in sixteenth and eighth pairs (hats and a rim/snare voice with the accents on a half-beat grid) and a second track of toms and **timpani (47) in eighth-note rolls of changing velocity** that build into the sections; fills close the phrases.
- **The lead**: a rich brass (112) with a scoop (`BEND`) into long notes (a bar or two each) in a narrow range around C4 to G4, a second track with a one-shot swell (89) and **pan sweeps from one ear to the other over two bars**; the melody is slow and low, the energy is underneath it.
- **Structure**: a long intro with the bass entering alone, then the sections reuse short patterns (`PATT`) many times, so the ear learns the cells quickly; the timpani rolls and a rising velocity mark the build; the loop is the whole song coming back.
- **Mix**: six tracks, never more than 6 notes at once; bass and percussion carry the level, the low band is more than half the energy (hers is 0.33 low / 0.46 mid, brighter, because of the hats and the clock).
What the round-2 "Cipher Command" took (the round-3 theme keeps the bass, the grid and the form, drops the tempo): a bass that is the engine (eighth notes with a sixteenth pickup, always moving), drums on the sixteenth grid with fills every fourth bar, a **short, repeated, climbing hook** (a faster, higher and more singable hook than Sturm's slow lead) (a pickup `D D F A` cell, bars 1 and 3 syncopated, bars 2 and 4 four eighths and a half note, the second pass higher), brass answering brass (the stabs on the half bar the lead does not use),
a **breakdown that thins to the clock and a heartbeat and builds with a snare roll** into a return with everything, and a last pass **a whole step higher** that a B-major turn drops back into D minor. Not taken: any of Sturm's notes, rhythms, bass line, chords, or its voices' roles (her bass is the pick bass 36 with her own pattern, her hook is her own).

### Round 4 study (listening to the hits with the tools, then ten sketches)
After three rejected rounds (nine full takes) the study below looked at the themes players call bangers instead of at Sturm alone: AW2's CO themes Sturm (219), Hawke (402), Lash (301), Max (210), Drake (202), Eagle (201), Jess (414), Kanbei (211) and the four power themes (409, 410, 419, 420). The CO themes were recorded in the game (`sound render --song <name>`, band split of the real output); the power themes could only be read as song data (`sound dump`, expanded with `m4a.run`: PEND with an empty call stack falls through, as in the engine). Counts are per bar over one pass of the track, "pitches" is the number of distinct keys the lead plays, "range" its span in semitones, "hook" the shortest cycle in bars (up to 16) that at least 40% of the bars repeat. The leads are picked by hand (the track that sings the tune).
| Theme | bpm | low / mid / high | Lead: voice, notes a bar, pitches, range | Bass: notes a bar, pitches | Hook | Programs used | Who carries the tune |
|---|---|---|---|---|---|---|---|
| Sturm 219 | 120 | 0.55 / 0.37 / 0.08 | brass 112 (with a 89 swell), 4.5, 6, 7 | synth 97: 7.3, 5 | bass cell 2 bars (73% of the bars); lead none | 11 | the bass cell and the kit (8.5 hits a bar); the lead is narrow and slow |
| Hawke 402 | 130 | 0.67 / 0.27 / 0.07 | seven short voices switched inside one track, 6.5, 8, 11 | 34/36/96: 5.9, 9 | bass 2 bars; lead through-composed | 18 | lead line and bass riff together, a new timbre every few notes |
| Lash 301 | 136 | 0.20 / 0.73 / 0.07 | two reeds (22) in unison, 6.3, 14, 31 | none (kit 6.7) | 8 bars | 8 | the lead alone |
| Max 210 | 96 | 0.62 / 0.33 / 0.04 | 30 (23 pitches, 36 semitones) and 31 (15 pitches), 4.5 and 3.6 | 34: 5.9, 9 | 8 bars | 6 | the leads, wide arcs |
| Drake 202 | 120 | 0.51 / 0.39 / 0.10 | pluck 27 runs: 7.9, 19, 29; brass 56: 1.4 | 36: 4.3, 9 | none within 16 bars | 6 | the pluck run over a pick-bass riff |
| Eagle 201 | 98 | 0.78 / 0.17 / 0.05 | 30: 5.0, 10, 23 | 34: 4.9, 4 | bass 1 bar | 5 | the bass cell |
| Jess 414 | 110 | 0.74 / 0.19 / 0.06 | mixed: 5.2, 10 | 36: 5.4, 12 | none | 15 | bass and a changing top line |
| Kanbei 211 | 104 | 0.43 / 0.42 / 0.16 | koto 117: 5.4, 9, 26; brass 2.6 | none | none | 7 | the koto line with brass answers |
| CO / Super powers 409, 410, 419, 420 | 124, 124, 118, 130 | not rendered | 3.0 to 9.6, 3 to 9 pitches (one 19 pitches over 30 semitones) | 34/36: 3.0 to 8.6, 5 to 8 | 2 to 4 bars | 10 to 17 | a short stabbing cell, repeated every 2 to 4 bars, over a bass of 6 to 9 notes a bar |
| take A / B / C (round 1) | 100 / 72 / 104 | 0.30 / 0.29 / 0.21 | horns 2.3, 13, 13 / clarinet 2.7, 14, 20 / reed 3.2, 17, 18 | 3.5 / 1.7 / 12 | none (A, C: 16 bars) | 8 / 7 / 7 | the slow lead |
| take D / E / F (round 2) | 152 / 158 / 148 | 0.33 / 0.25 / 0.30 | brass 3.7, 13, 13 / strings 8.0, 25, 27 / brass 5.3, 19, 20 | 8.1 / 12.9 / 7.7 | lead none; kit 4 bars | 7 | the lead over a busy pick-bass |
| take G / H / I (round 3) | 120 / 124 / 130 | 0.57 / 0.49 / 0.53 | brass 56: 5.3, 14, 17 / 4.4, 13, 13 / 5.4, 14, 13 | 10 / 8.5 / 15.5 | bass 2 bars | 6 | the pick bass |

What this says, and what it does not:
- **Tempo and density were not the gap in rounds 2-3.** The hits sit at 96-136 bpm (110-136 for the Black Hole themes) and play 4.5 to 9.6 notes a bar in the lead; G, H and I (4.4 to 5.4) are inside that, D-F were faster than any of them. The bass-heavy low band (0.49 to 0.57) is Sturm's, Hawke's, Max's, Eagle's and Jess's, but Lash's and Kanbei's are 0.20 and 0.43: **a bass-heavy mix is one way to a banger, not the only one.**
- **Sturm's lead is not a wide melody**: 6 pitches in 7 semitones, 4.5 notes a bar, under a bass cell of 5 pitches. If the user hears a "tune" in Sturm it is that cell and its synth voice, or the interplay of the kit; our G-I rebuilt the cell with another instrument (the pick bass 36) and a different line.
- **What our nine took lacked, as far as the numbers can say**: (1) **timbre**: every take plays the hook on the same bright brass (56) or a string, and the bass on the pick bass; the hits put the tune on a reed pair (Lash), a plucked run (Drake), a koto (Kanbei), key-split voices (Max, Eagle) or switch voices inside the line (Hawke 18 programs, Jess 15, the powers 10 to 17; ours 6 to 8). Sturm's own bass is the synth voice 97, which none of our takes used. (2) **Range**: the hits' leads span 23 to 36 semitones over 10 to 23 pitches (Max, Lash, Drake); G-I lead 13 to 17 semitones over 13 to 14 pitches, a 2-bar cell. (3) **A longer arc**: Lash, Max and Kanbei's lines run 4 to 8 bars before they repeat; our hooks were 2 bars. (4) **Texture**: the hits keep three to five pitched voices answering each other (Hawke, Jess, Drake), ours kept one lead, one doubling and one bass.
- **What cannot be told from the data**: why the user rejects a take is a matter of taste (a melody, a sound or a feel); the numbers above do not isolate it. The ten sketches below vary exactly these things (sound, range, arc, groove, mood) at a mid tempo so the pick answers it. Nothing is copied: the notes are ours, only the statistics were read.
- Method note: no third-party tool, only `aw2dev sound render|levels|dump` and a script over `m4a.run` (not committed: it is an analysis of three dozen lines). The power themes' band split would need `ctx.power` in the recorder; not done.

### The ten sketches (J to S)
Each is 12 bars of one section (22 to 26 s, one pass, intro hit to a cadence), in the same format and with AW2's own voices, `pitchcheck` within 0.3 semitone (A.47 timpani stays in its written C1 to C4 range), at most 6 notes at once, levels -19.3 to -21.8 dBFS RMS (AW2's reference themes -23.3 to -18.8), the lead from 3.5 dB under the bass (L) to the loudest track (M, N, Q), measured with `sound stems` and tuned with `gain=`. They are **not** in the build: `asuka.m4t` is unchanged; the files live outside the repository (a sketch becomes a full theme only after the user picks one). The 12-bar loop is shorter than the kit's 45 s rule, so `sound compose` reports that one rule for them.
| | Name | bpm | Key | Lead | What it is |
|---|---|---|---|---|---|
| J | Iron Banner | 112 | D minor | bright brass 56 + horns 111 | a heroic-villain march: dotted-rhythm brass tune over a snare march, timpani on 1 and 3, a climbing last phrase |
| K | Cold Iron Riff | 118 | E minor | pick bass 36 and plucked guitar 27 in unison, brass 56 on top | a dark rock riff (E, G, a chromatic drop B-Bb-A), then a brass tune over it, tutti, a hit |
| L | Velvet Dossier | 112 | C minor | muted trumpet (56, soft and short) | a spy-thriller groove: walking bass, harp stabs on the off-beat, rim clicks, a swaggering tune with a B natural over the dominant |
| M | Anthem of Ash | 110 | G minor | brass 56 doubled an octave down by 111 | a militaristic anthem: proud dotted tune, strings on fifths, timpani with a roll, a snare march |
| N | Fingers of Fate | 124 | E harmonic minor | plucked guitar 27 in sixteenths | a fast-fingered lead over a steady rock beat: arpeggio sequences, falling and rising cells, a chromatic run |
| O | Throne of Cinders | 110 | C minor | strings 48 (the call), brass 111 (the answer) | an epic orchestral villain: call and response, then both together, toms and a snare roll into a crash |
| P | Event Pulse | 128 | B minor | staccato brass 56 | a Black Hole power-theme style: stabbing hook, chord stabs on the off-beats, an eighth-note bass with octave jumps, sixteenth hats |
| Q | Cold Calculus | 110 | D dorian | reed 110 (the synth-like voice) | a cool strategist: syncopated reed hook over a sixteenth funk bass, muted guitar chops, a funk kit |
| R | Fallen Aria | 110 | A minor | flute 77, then low brass 111 | a heroine turned villain: a sad flute tune over a harp, the same tune with a leading tone, a tritone and a flat second, then the low brass has it over a heartbeat and a bass |
| S | Midnight Tango | 120 | F# minor | clarinet 71 | a dark tango: marcato strings on the 3+3+2 pattern, a bass walking every beat, harp runs at the phrase ends, a dominant arpeggio into the final chord |
The WAVs (`asuka_sketch_J.wav` to `_S.wav`, 44.1 kHz) and the `.m4t` beside each are in the working scratchpad; render a sketch from its `.m4t` by copying it to `<dir>/asuka.m4t` and `aw2dev sound render --song asuka --dir <dir>`.

## Final theme: N with Sonja's theme quoted from the ROM
The user chose **N "Fingers of Fate"** (124 bpm, E harmonic minor: a plucked-guitar 27 sixteenth lead with arpeggio sequences and a chromatic run over a steady rock beat, a contrasting section in G with a brass tune), then asked for it to be **mixed with Sonja's official theme** ("without touching sonja's original track since this is for asuka only"): Asuka is Sonja after she defected, so her theme quotes her old self.
Sonja's theme is Nintendo's and Intelligent Systems': **not one of its notes is in the repository** (nor in this document). `asuka.m4t` holds only our own notes (N's) and `rom` lines (docs/dev/music-kit.md, "Quoting AW2's songs") that name stretches of AW2's song **212** (Sonja's CO theme; track 0 is her tune; 190 bpm, a major key with a flat seventh) by track and bars, with a transposition, a voice and "lower G# and C#". The game reads those events out of the ROM it is running when it builds the song (`ds_music::install_quotes`: the same ROM on every peer, so every peer writes the same bytes); the tools read the same ROM (`aw2dev sound compose` passes `--rom`). Without a ROM (CI) a reference only has to parse. Sonja's own row, song data and voices are only *read*: `co verify sonja` compares her music (and Sturm's) with v0.8.7 (`test_sonja_untouched.py`, group `music`).
**Tempo, key, form** (NS): 124 bpm, E harmonic minor, intro 4 bars (7.8 s) + a **32 bar loop (62.2 s)**, 5 tracks, at most 6 notes at once, RMS -19.5 dBFS (AW2's themes -23.3 to -18.8), peak -3.9, low/mid/high 0.22 / 0.61 / 0.17, seams click 1.2x and gap 1.2x to 1.6x (ok; the intro's end 0.5x, the bar of rests before the beat), passes alike 0.935. The quotes' `peak=` puts the first 3.7 dB under the fingered lead and the stack 4.8 dB under it (her own volumes are 45 to 68 of 127, too quiet on a brass).
| Section | Bars | N's material | Sonja's (song 212, track 0) |
|---|---|---|---|
| I | 4 | the intro arpeggios, crash, kit | none |
| A | 8 | the hook over pads, bass and kit | none |
| A2 | 8 | bass, kit, pads; the lead rests for four bars and then **answers** with its runs | **her bars 7-10** on brass 56 at its original octave minus one, G# and C# lowered to G and C (a darkened, minor-colour version of her phrase), over N's bass and drums |
| B | 8 | the contrasting section in G, brass tune | none |
| A3 | 8 | the return: the whole fingered lead | **her bars 7-14** two octaves down on horn 111 under the lead (a stack) |
Her phrase is played at **our** tempo (the ticks are copied; `tempo=` is not used): her 190 bpm tune becomes a slower, darker 124 bpm one whose bars line up with ours. Checked in the game (f0 of the solo track): the pitches are the source's moved by the written transposition, with no G# left in the lowered quote.
**Alternates** (same rules, in `tango-gamesupport-aw2/music/es/alt/`, not in the build; `aw2dev sound render --song asuka --dir tango-gamesupport-aw2/music/es/alt/ss` plays one, or copy it over `asuka.m4t`): **NS2** (`alt/ns2/asuka.m4t`, the subtle one) quotes her tune **once**, in section B: her bars 7-10 at the sounding octave of the brass tune, replacing its second half, over the chords C G B B; 124 bpm, loop 62.2 s, RMS -19.3 dBFS. **SS** (`alt/ss/asuka.m4t`, Sturm and Sonja) is **Sturm's engine with her tune over it**: his bass (voice 97, track 3), root-and-fifth (track 4), kit (2), toms (5) and rhythm lead (0, whose voices change note by note, so `raw` brings them along) are `raw` references to song **219** at his 120 bpm (intro: his bars 1-4; loop: his bars 5-12, 13-20 and 21-28, 24 bars, 48.2 s), with her bars 7-10 over the first section, her bars 11-14 over the second and her bars 7-14 two octaves down on horn under his full lead in the third; **his lead answers her** in the second half of the first two sections. RMS -20.0 dBFS, low/mid/high 0.46 / 0.47 / 0.07, seams click 1.6x gap 1.4x to 2.4x, passes alike 0.904.
Earlier take, kept for history: **"Cold Iron Fingers"** combined K and N at 120 bpm (K: 118 bpm, E minor, a pick-bass and guitar riff in unison with a chromatic drop and a brass tune).

## Art, HQ
**The project owner's own picture** (`art-src/cos/asuka_v1.jpg`, framing `asuka_v1.toml`): a clean illustration, imported by the illustration mode of `aw2dev co portrait import` (docs/dev/co-kit.md, "The illustration
import"): white background cut (also the gaps between arm and body), Lanczos / area downscale from the figure's own pixels, one palette of 15 colours + transparent (three of the 14 kept for the black cloth and hair), AW2's
outline; the 128 x 160 figure is framed waist-up at 0.22 (head 63 px), she already faces right; the mug, the 32 x 16 HUD face and the 48 x 16 mini are cut from the head at that scale; every expression is the neutral face.
Credit: portrait art provided by the project owner (`CREDITS.md`).
*What the first in-game look got wrong (and was not the art):* (1) the **battle-scene header face** read as noise: the header draws the CO's **mini**, and the mini is not 32 x 24 but a **48 x 16 strip of the face**
(12 tiles: the left 32 x 16 in rows of four, the right 16 x 16 in rows of two; found by poking each of a CO's 12 mini tiles with a colour of its own and reading the header, and checked on AW2's Sonja). The importer
made it a 32 x 24 window in the wrong tile order, for the four Emerald Sun COs too; now `importer.mini_strip` cuts the strip and `es_cos.rs` lays the tiles out so, and all five headers read as faces (the Teams-page
sprites are the same two blocks: a 32 x 16 and a 16 x 16). (2) the **Power cut-ins** looked cropped or empty on the sheet because the captured frame was caught while the figure slid in (Dark Intel) or before it appeared
(Event Horizon's cut-in comes after the flames); both cut-ins show the whole figure; `test_asuka_pictures.py` now picks the frame with the most of her black uniform and bursts long enough for both.
**Edges** (the user compared her with Kanbei): the illustration importer cuts the silhouette hard (coverage at one half, spikes and fringe pixels off), draws the outline one pixel wide and unbroken in 8-connectivity (corners included), lifts the uniform's black into its own dark ramp (three tones at least 6.5 Lab lightness above the outline's, so the outline reads against the cloth and hair as it does on Hawke's coat), and puts a one-pixel seam in the darker material's shadow tone where two big materials meet (skin / collar, neckerchief / uniform, hand / sleeve, book edge); the faces get the same silhouette and outline, no seams (the eyes are their lines). `co portrait lint` checks all of it for illustration imports (`importer.outline_problems`, tests `OutlineLint`): no gap, one pixel wide, outline colour only, hardly any outline colour inside, and no tone of the palette within 8 Lab of the outline.
**Her HQ is Black Hole's whatever colour slot she plays in**: the game draws an army's HQ by the CO's country (her row's property style, 4, like Hawke's and Lash's); `asuka_pics_hq_follows_the_co` checks the HQ picture of
army 1 (Orange Star's slot) is drawn exactly as Hawke's and not as Andy's or Sonja's.
**Sonja is untouched**: Asuka has her own id, picture words, palette, name graphic, texts, power words and theme; every table she is added to is a copy with her row appended (`co_new::build`, `co_roster::build`);
`aw2dev co verify sonja` compares Sonja's rows, texts, pictures, numbers and tag page with the v0.8.7 build (docs/dev/co-kit.md).

## Where she is
In **this build, for everyone** (no playtest flag, unlike the Emerald Sun five): Versus' Teams list (after Hawke, Black Hole's group), the tag partner pick, the War Room and Survival / Champion CO screens, the DS-style
CO select grid (Versus' grid no longer draws black cells for Emerald Sun COs the roster does not list), the CO pages, the HUD, the power and tag cut-ins, the dialogue boxes. **Not in the Emerald Sun Campaign**:
`aw2dev campaign check` fails if any campaign module, dialogue file or roster names her (`eslib/cli.py asuka_rule`; test `eslib/test_eslib.py AsukaRule`). **Not in the BH Campaign yet**: reserved for the BH2 Campaign.

## What she does
| | **Black Insight** (day to day) | **Dark Intel** (CO Power, 3 stars) | **Event Horizon** (Super Power, 9 stars in all) |
|---|---|---|---|
| Attack and defence | +5% / +5% | +5% / +5% on top of the power's own +10% firepower and defence | the same |
| Vision in fog | +1 | +2, sees into woods and reefs | +2, sees into hiding places |
| Enemy terrain stars lost | 1 | 2 | 3 |
| Hit points | hidden from the enemy | her units +1 HP, enemy units -1 HP (to 100, never below 1) | her units +2, enemy -2; her units strike first when attacked (Counter Break) |
| Enemy ammo and fuel | | halved, rounded down | halved, rounded down |
| Luck | 0..19% (Nell's), no bad luck | same (Nell's powers raise it to 60 and 100: Asuka's do not stack that) | same |
| Movement | every terrain costs 1 for ground units (Sturm's) | same | same |
- **Sonja's numbers** are her Dual Strike block (`co_roster::ds_co(92) = 8`): vision, skills 0x01 / 0x09 / 0x0D, the enemy's terrain cut.
- **Nell's luck** (the user's choice, replacing Sonja's bad-luck quirk): maximum roll 20 (read from AW2's table: Nell 20 / 60 / 100 by level) in all three levels, bad luck 0. Her powers keep 20 rather than stacking Nell's 60 and 100: with Hawke's HP swing and Drake's halving on top, that would be too much. Ten sampled hits stay inside 0..19 and exceed what luck 10 reaches.
- **Sturm's movement**: her row's three movement charts per level are Sturm's (every terrain costs 1 for ground units; impassable terrain stays impassable: a Tank still cannot climb a mountain, as Sturm's cannot). In the Dual Strike pack rain and snow no longer slow anyone and AW2's weather charts are all the clear one (`co_roster::build`), so Sturm's and hers are the same in every weather; checked equal to Sturm's in clear, rain and snow.
- **Hawke's Black Wave and Black Storm** are AW2's own mass-HP procedure (`sub_08044D70`); her two power functions (`co_powers::asuka_fn`) call it as Hawke's do (damage and healing 1 or 2) with **Drake's fuel flag on**
  (his Tsunami and Typhoon pass 1: every enemy unit's fuel halved, `fuel / 2` rounded down, 99 -> 49, 21 -> 10, 1 -> 0). The **ammo** is halved the same way in `co_powers::mass_unit` (9 -> 4, 6 -> 3, 3 -> 1, 1 -> 0;
  Infantry, Recon and APC have no ammo stat, 0, and stay). Her own units and her team's keep theirs. **No rain** (Drake's weather argument stays -1: unchanged). The cut-in and sparkle are Hawke's.
- The CPU plays her with Hawke's profile (`ds_ai::template_of`): a power as soon as the meter allows.
- Black Hole's colours and emblem by default like Hawke and Lash (row style 4, colour 5); her CO page's tab is Black Hole's.

## The star costs
**3 / 9, Eagle's** (the user's order: Black Insight is now Sonja's vision, hidden HP and cover cut, +5%, Nell's luck and Sturm's movement) (the meter of AW2's Eagle and Dual Strike's: read from both tables, `aw2dev co balance asuka --vs Eagle Sonja Hawke`; Sonja 3 / 5, Hawke 5 / 9, Drake 4 / 7, Kanbei 4 / 7). Her powers are stronger than any
of theirs (Hawke's HP swing, Drake's halving of fuel and ammo, Sonja's vision, cover cut and strike first, +5%), so the cheap CO Power and the dear Super Power of the one CO of the roster with a flat 3 / 9 fit best:
CO Power at 27000 meter points (9000 a star), Super Power at 81000, each further use +20%. The yardstick of `co balance asuka --vs Sturm Hawke Kanbei Eagle Nell Sonja Drake` (firepower + defence + 10 per HP moved + 10 for halving + 10 for every terrain costing 1 + (luck - bad luck - 10) / 2): Asuka d2d +25, CO Power +65, Super Power +85 at 3 / 9;
Hawke +10 / +40 / +60 at 5 / 9, Kanbei +40 / +80 / +110 at 4 / 7, Sturm +10 flat, Drake +2 / +32 / +42, Sonja -2 / +8 / +8, Eagle +1 / -24 / +11. She lands above Hawke at every level for two to four fewer stars and under Kanbei's raw numbers, with the meter of Eagle's.

## Names and words (final)
Day to day **Black Insight**, CO Power **Dark Intel**, Super Power **Event Horizon**. Quotes: "I have read your every move. Observe." / "Event Horizon. Nothing escapes it. Not even you." / tag-in "Updating the file." /
victory "As projected. Black Hole advances." Tag Powers (`cos/tags.toml`, `sturm_pairs.rs`):
| Pair | Tag Power | Compatibility | Stars |
|---|---|---|---|
| Asuka + Von Bolt | Vault Breakers (the BH2 seed pair; Sonja's Campaign-prize pair has the same name) | 115 | 2 |
| Asuka + Hawke | Black Eclipse | 120 | 2 |
| Asuka + Sturm | Perfect Intel | 118 | 2 |
| Asuka + Lash | Grand Design | 115 | 2 |
| Asuka + Flak | Dead Reckoning | 110 | 1 |
| Asuka + Adder | Quiet Knife | 110 | 1 |
| Asuka + anyone else | none | 95 | none |

## Online
`inspect::SIM_VERSION` 27 -> **28** (`pvp.rs` history): the CO table, the Teams order, the power procedures in ROM, the unit hooks and the text tables are all part of the shared console. Both peers must run the same
build. Another branch that also bumps to 28 must take the next free number when merging.

## Verification (what was run; `tools/aw2test/tests/test_asuka.py`, `test_asuka_pictures.py`)
Her row (3 / 9 stars, vision, luck, skills, power words, texts), fog vision at exact distances, the enemy's terrain cut as the record's defence number, luck (20, 0), the hidden-HP question mark
(`TANGOAW2_DS_GRAPHICS=1`), +5% attack and defence in exact base-damage and defence numbers for Tank / Artillery / Infantry pairs day to day and in both powers, the HP effects on units at 45, 95, 100, 5, 91, 55, 11, 10 ...,
the halving of ammo and fuel on twelve units (before / after), the costs 27000 / 81000 and +20%, the CPU using each power, Counter Break's exact order of the two strikes, Tag Powers with Von Bolt and Hawke, both peers
agreeing over netplay; `test_all_cos.py` (every list), `test_all_powers.py`, `aw2dev co check`, `co balance`, `co portrait ingame asuka`, `aw2dev test`, `aw2dev suite`, `aw2dev net repeat asuka --no-skin`
(scenario `s_asuka`: both armies Asuka, units of every HP, her CO Power on day 1 and Super Power on day 2; 8 runs, equal hashes). `aw2dev co portrait powers asuka` makes the picture sheet.
(`co verify` of branch cotest is not merged here: `co verify sonja` is this branch's own, the tests above are the equivalent for Asuka.)
Known limits, all present before Asuka (checked with the base build, `AW2TEST_RUNNER_DIR`): the straight-replay comparison of every netplay test (`all identical`) fails (peers agree with each other: the check the Asuka netplay
test makes); the War Room record tests (`war_room_record_with_new_cos`, `save_war_room_score_saved`), the five-army tests and `ds_coselect_versus_*` fail. `aw2dev suite` bad=2: the two `gfx armysel_faces` goldens (the army page's face cards now show Asuka after Hawke: intended; the golden set in `~/.aw2dev/golden` is shared by all worktrees:
refresh it with `aw2dev gfx golden` when this line is merged).

## The quote boxes and the flash (checked in the game)
- The cut-off quote lines on the first sheets were the sheet's frame timing (the text still being typed); the boxes finish both lines ("I have read your / every move. Observe.", "Event Horizon. Nothing / escapes it. Not even you."). `asuka_pics_*_activation` measures each line's pixel width in the typed-out frame against AW2's font width of the toml's line (within 3 px), so a truncated or wrong line fails.
- The Super Power showed the CO Power's line because AW2 (and Dual Strike) write six quotes for every CO and pick **one of the six at random for any power** (`sub_080398D0`): the six lines are not a CO Power / Super Power split. That is AW2's design for its own COs, left alone. For tangoAW2's own COs (Crumb, the Emerald Sun five, Asuka) the pick is now the power's own (`crumb::quote_pick`, extended: slots CO Power, Super Power, Tag Power twice), so Event Horizon says its own line.
- The white frame: AW2's own flash. The screen goes white for about 14 emulated frames, twice in a Super Power (Hawke's, Sonja's and Kanbei's are the same length, measured on all four with the same burst) and returns to the map normally; nothing lingers. The sheet shows the frames just before and after, never the white. A CO Power has a wash of light instead, no white.
