# Asuka (CO 92)

Black Hole's intelligence chief, tangoAW2's own CO. **Lore** (the CO page says it without naming her old self): once an Allied intelligence officer, she took the name Asuka on joining Black Hole, and with it a power
far beyond her old self. (Developer note: she is Sonja after she defects; "Asuka" is Sonja's Japanese name. The CO page and quotes never name Sonja, players are left to work it out, and the BH2 story is not spoiled.)
Code `tango-gamesupport-aw2/src/asuka.rs` (constants and the design in its header), the pieces in `co_new.rs` (`ASUKA`, `all()`, `like`, `is_own`, the texts, her presentation row), `co_roster.rs` (`ds_co`, `stat`:
the +5%, the stars), `co_powers.rs` (`asuka_fn`, the ammo halving in `mass_unit`), `es_cos.rs` (her art and texts, the table of the Emerald Sun portraits), `ds_co_page.rs` (CO page), `sturm_pairs.rs` (her pairs), `es_music.rs` (`SOURCES`: her theme),
`ds_ai.rs` (the CPU plays her with Hawke's profile). Data `cos/asuka.toml`, `cos/tags.toml`, art `art/cos/asuka/`, song `music/es/asuka.m4t`.

## Her theme
`music/es/asuka.m4t`, **"Cipher Command"** (the fourth take: the first, "Cold Reckoning", was cold and slow, the three sinister remixes "Umbra Protocol", "Singularity" and "Black Ledger" were rejected as too slow, moody and ambient: "Sturm's track was a banger, make a banger").
D minor with the harmonic-minor raised seventh (the C# in the A chord), **152 bpm**, 2 intro bars + 40 bars (**63 s loop**), 6 notes at most. A brass-led anthem: AW2's pick bass (36) runs a relentless eighth-note ostinato (an octave jump on the third eighth, a sixteenth pickup into every bar),
a bright brass (56) sings a four-bar hook that is repeated and climbs, power-chord stabs (rich brass 111) answer it on the second half of the bar, and her clock is a fast plucked (117) sixteenth-note arpeggio that ticks through everything.
Form: intro hit (2 bars), **A** (the hook twice, Dm | Bb | Gm | A), **B** (call and response over a rising bass: the lead's half bar, the stabs' half bar, strings chopping the offbeats), **BR** (the breakdown: strings pad, the clock reduced to a single ticking A, a timpani heartbeat, a snare build into 16th stabs),
**R** (the big return: the hook with the stabs, then with the strings doubling it an octave down and the timpani), **C** (the whole hook a whole step up in E minor, then a B turn and the A chord that drops it back into the loop). Drums: a breakbeat in sixteenths with a double kick, snare on 2 and 4, a tom fill every fourth bar and a snare roll every eighth.
Levels RMS -19.6 dBFS (Sturm -19.6), peak -3.7, seams click 0.60x to 0.87x / gap 1.6x to 2.3x; `pitchcheck` within 0.3 semitone (every instrument it uses; the timpani reads right below C4 only, as written in music-kit.md).
**Two other takes of the same brief were made and kept out of the build** (swapping is one file; the WAVs were rendered for the project owner): **E "Clockwork Chase"** (E Phrygian, 158 bpm, 61 s: a sawtooth-string (48) lead chases a sixteenth hook over a sixteenth bass gallop, the clock is a tick-tock of the tonic jumping an octave, a brass fanfare climbs B)
and **F "Event Drive"** (C Phrygian-minor, 148 bpm, 65 s: a drum-and-bass breakbeat with ghost snares under a syncopated two-bar bass riff, a brass hook with the flat second, B is the riff in unison with the brass climbing a semitone every two bars).
The three earlier remixes of the old theme are not kept.

### What makes Sturm's theme (AW2 song 219) a banger, and what her theme takes from it
Studied with `aw2dev sound dump 219`, `sound voices`, a recording (`sound render --song sturm`, RMS -19.6 dBFS, peak -4.6, band split low/mid/high 0.55 / 0.37 / 0.08, centroid 833 Hz) and the other Black Hole themes (`sound dump 217 .. 220`: tempo values 63, 80, 60, 60 = 126, 160, 120, 120 bpm).
- **Tempo and grid**: 120 bpm (MP2K `TEMPO 60`), but nearly all of it sits on a **sixteenth grid** (6 ticks): the ear hears 240 pulses a minute. Black Hole's song 218 is 160 bpm. Hers goes 148 to 158 bpm on the same grid.
- **A bass ostinato that never stops**: track 3 is a looping bass-synth sample (voice 97) on E, chopped into one-tick stabs on the sixteenth grid with a chromatic neighbour (D# and F around the E): a gated, rhythmic, minor-second-flavoured drive; a second low voice (96) nails the root and fifth on the bar lines. The tune is in what the bass *does*, not in a chord progression.
- **Drums**: two percussion tracks. A kit track (120) with short hits in sixteenth and eighth pairs (hats and a rim/snare voice with the accents on a half-beat grid) and a second track of toms and **timpani (47) in eighth-note rolls of changing velocity** that build into the sections; fills close the phrases.
- **The lead**: a rich brass (112) with a scoop (`BEND`) into long notes (a bar or two each) in a narrow range around C4 to G4, a second track with a one-shot swell (89) and **pan sweeps from one ear to the other over two bars**; the melody is slow and low, the energy is underneath it.
- **Structure**: a long intro with the bass entering alone, then the sections reuse short patterns (`PATT`) many times, so the ear learns the cells quickly; the timpani rolls and a rising velocity mark the build; the loop is the whole song coming back.
- **Mix**: six tracks, never more than 6 notes at once; bass and percussion carry the level, the low band is more than half the energy (hers is 0.33 low / 0.46 mid, brighter, because of the hats and the clock).
What "Cipher Command" takes: a bass that is the engine (eighth notes with a sixteenth pickup, always moving), drums on the sixteenth grid with fills every fourth bar, a **short, repeated, climbing hook** (a faster, higher and more singable hook than Sturm's slow lead) (a pickup `D D F A` cell, bars 1 and 3 syncopated, bars 2 and 4 four eighths and a half note, the second pass higher), brass answering brass (the stabs on the half bar the lead does not use),
a **breakdown that thins to the clock and a heartbeat and builds with a snare roll** into a return with everything, and a last pass **a whole step higher** that a B-major turn drops back into D minor. Not taken: any of Sturm's notes, rhythms, bass line, chords, or its voices' roles (her bass is the pick bass 36 with her own pattern, her hook is her own).

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
