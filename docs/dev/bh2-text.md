# BH2 Campaign dialogue: `bh2_text`, `tools/bh2text/lint.py`

The BH2 Campaign's story is written and wired into `bh2_campaign.rs` (docs/dev/bh2-maps.md "BH2 in the game"; only the M30 takeover scenes and `m30_map` wait for the map-switch merge). It is the BH Campaign's text system ([`bh_text`](../AW2.md), `src/bh_text/README.txt`) copied for the sequel.

| What | Where |
|---|---|
| Parser (a copy of `bh_text.rs` with the BH2 cast, `own:` songs, `credits()`) | `tango-gamesupport-aw2/src/bh2_text.rs` (registered by one line in `lib.rs`) |
| The text | `tango-gamesupport-aw2/src/bh2_text/{story,act1..act5,ending,credits}.txt`, format `README.txt` there |
| Lint (grammar, 176 px boxes, voices, songs; `--ids` counts text ids, `--counts` boxes per scene) | `python3 tools/bh2text/lint.py` |
| Tests | `cargo test -p tango-gamesupport-aw2 --lib bh2_text` (songs, parse, credits fit the roll, text ids inside 3,072 with 150 spare) |

## Voices and rules the text follows
Asuka is cold, exact and dry; Sturm never shouts, never contracts and never shows warmth; Hawke, Koal, Kanbei, Sasha, Javier, Jugger (in capitals), Klaus and Livia never contract; Aria is fiery and personal. Mid-battle scenes (`mNN_dayN`, `mNN_front2_*`) keep the battle's music; every other scene names a song. No dates or ages. Free-pick scenes name the pool (Asuka, Crumb, Hawke, Koal, Kindle, Jugger, Flak, Lash, Adder, Von Bolt, Clone Andy; **Sturm is a pick nowhere**) and give each officer a line in an `@IF` block; pair missions add an `@PARTNER` block.

## Songs
`own:door` (crate, door, Obelisk and Lab 7 binder scenes), `own:credits` (not used by a scene: the staff roll's song), `own:aria` (Aria's scenes). They are `music/bh2/*.m4t`, rows of `es_music::SOURCES`; `bh2_text.rs` `OWN_SONGS` maps each name to
`Track::Own(slot)`. `co:asuka` is Asuka's "Iron Verdict".

## Wiring (scene keys use the final numbering: mission `bh2_NN` plays `mNN_*`)
Per mission: `mNN_pre` the intro; `mNN_post` the victory; `mNN_map` the scene on the world map afterwards; `mNN_dayK` a trigger at the start of day K (move the day if the mission changes); `mNN_front2_post` / `mNN_front2_lost` the second front won / lost (M4, M13, M25).

| Key(s) | Where | Notes |
|---|---|---|
| `prologue` (pages), then `prologue_castle`, `prologue_allies`, `prologue_turn` | `CampaignDef::prologue` + chained scenes on the world map | `prologue_song` = `prologue` |
| `m08_warroom`, `m13_warroom`, `m19_warroom`, `m25_warroom`, `m29_warroom` | chained after the act's last `_map` | Allied war rooms close Acts I-V |
| `m08_staff`, `m13_staff`, `m19_staff`, `m25_staff` | chained after the war room | the next act's briefing (Sturm and the officers) |
| `m06_takeover` | M6, Javier's last Com Tower falls: `TakeOver` Javier -> Eagle (held second HQ) | |
| `m12_airlift` | M12, Kanbei at half strength: `Spawn` B Copters + Infantry | `m12_post` is the father-daughter scene (victory) |
| `m13_stand` | M13 front 1, Kanbei's last bridge | |
| `m16_wire` | M16, when a seam is cut | |
| `m20_split` | M20, day 5 | the Allied band |
| `m21_freed` | M21, commandos reach the tower | Nell leaves |
| `m22_binder` | M22, Clone Andy reaches the archive | project 17 |
| `m23_crate`, `m23_journal`, `m23_reserve` | M23, Crumb reaches the crate tile; then `Spawn` the Neotank reserve | one chain |
| `m26_folders` | M26, around day 5 | |
| `m27_vault_empty` then `m27_sale` | M27, funds reach 0; Jess then retreats (win) | |
| `m28_door` | M28, Crumb at the door tile; `m28_day6` and `m28_post` bracket the nine days | |
| `m30_pre`, `m30_day5`, `m30_post`, `m30_map` | M30 The Orange Line (free pair vs Rachel + Sami) | pick blocks as elsewhere |
| `m31_pre` (the gauntlet's opening), `m31_day5`, `m31_takeover_olaf`, `m31_takeover_kanbei`, `m31_takeover_eagle` | M31 stage 1: `TakeOver` Nell -> Olaf -> Kanbei -> Eagle | |
| `m31_switch` (Eagle's fall), then `m31_stage2` (Aria's entrance, the approved draft) | the mid-battle map switch to Aria's citadel | play both at the switch |
| `m31_day6`, `m31_day9`, `m31_day12`, `m31_post` | M31 stage 2 and the victory | Hawke speaks as a fixed radio voice |
| `epilogue`, `epilogue_toasts` | after M31, chained; then `bh2_text::credits()` | |
| `m32_pre`, `m32_day3` (Cassius), `m32_day5` (Aurelia), `m32_day7` (Livia), `m32_post`, `m32_epilogue` | secret M32 (unlocked by M29); `m32_epilogue` then the `secret` credits pages | |

Wired (see bh2_campaign.rs); needs from the campaign data: the roster pools above; Asuka forced in M1, M2 (+Crumb), M12, M13 front 1, M23 (+Crumb), M26 (+Hawke), M28 (+Crumb), M31 (+ a free partner); Sturm + Asuka in M5 only; credits from `bh2_text::credits()` (`secret` pages show after M32); `final_mission` M31; a test like `bh_campaign::every_dialogue_scene_is_used` (`bh2_text::keys()` against `keys_used()`); `tools/bh2text/lint.py` checks the same once `bh2_campaign.rs` asks for scenes with `bh2_text::scene("...")`.
