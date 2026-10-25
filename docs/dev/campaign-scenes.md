# Campaign scenes and music: `aw2dev campaign`, `aw2dev sound`

How the BH Campaign presents its story the way AW2's Normal campaign does, and the tools to list, trace and extend it. Code: `src/campaign_music.rs` (tracks), `src/custom_campaign.rs`
(`Scene`, `SceneEnd`, `scene_cmds`), `src/bh_text.rs` (`@SONG`, `chain`), `src/ds_campaign.rs` (`start_new_proc_script`, `prologue_pool`), `tools/aw2test/aw2test/story.py` (tracer),
`devkit/aw2/commands/campaign.py`, `sound.py`. Skills: `aw2-add-campaign`, `aw2-add-music`.

## How AW2's Normal campaign presents it (traced with `aw2dev campaign trace`, ROM event scripts scanned for op 0x41)
- New: fade in on the **PROLOGUE card** (teal Black Hole map, title top left, dialogue box at the bottom) with song **425**; Sturm and Hawke talk (script `0x084A0D58`, speakers 10 and 14); the music
  fades out with the screen, ~120 frames of black; then the **CAMPAIGN / ORANGE STAR card** over the blue world map with song **413** and the allies' scene; fade; the world map with song **424**.
- A mission: world map (424) -> mission panel -> a scene on the map backdrop with the speakers' song (Black Hole officers **411**, allies **413**, Sturm's citadel **220**, a nation's scenes
  **421** Green Earth / **422** Yellow Comet / **423** Blue Moon, a CO's own scene that CO's theme: Hawke 402, Hachi 302) -> diagonal wipe -> **mission card** (404) -> black -> the CO's battle theme.
- Every script scene is `41 <song>` (op 0x41: the music proc fades the old song out, the new starts), `17 open`, `38 19` pairs, `42` (fade the music out) **before** `18` (close), `04`.
  Songs used by AW2's 121 `0x41` calls: 411 x42, 413 x18, 423 x14, 422 x13, 421 x12, 25 x12 (crisis), 220 x5, and single uses of 56, 302, 402, 409, 420 (`aw2dev sound list --source aw2`).
- Dual Strike's scripts name the same roles (BGM_ENEMY_EVENT1/2, ALLY_EVENT1/2, EVENT_PINCH1, HAGEVOLT_EVENT1 = Von Bolt, OPENING1, GMAP1..3, NML_ENDING1/2); `ds_campaign_data::aw2_song` already maps them to 411 / 413 / 220.

## What the BH Campaign does
- **Prologue**: a new campaign runs AW2's own prologue proc (`0x08616FD4`: the PROLOGUE card, song 425, the fades) with the campaign's narration as its event script (the pool word `0x0808A880`,
  `ds_campaign::prologue_pool`; the proc is started by `start_new_proc` when nothing is won and the flag `0x9E` is unset), then the world map (424, the same song the game plays on every return).
- **Every story scene has a song**: `== key` then `@SONG name` in `bh_text/*.txt`. Names: `aw2dev sound list` (roles `opening enemy1 enemy2 ally1 ally2 entry pinch hagevolt red blue sturm doom final
  ending1 ending2`, `aw2:<id>`, `co:<name>` = that CO's theme; the Emerald Sun COs' own themes are `co:klaus`, `co:aurelia`, `co:cassius`, `co:livia`, `co:varro`: docs/dev/music-kit.md). `tools/bhtext/lint.py` and the Rust test `every_story_scene_has_a_song` fail a pre / post / map / warroom / sturm / ... scene without one.
  The mid-battle day scenes keep the battle's music on purpose.
- Fades: a scene on a battle map starts its song with op 0x41 and ends with 0x42 (the CO's theme returns with the turn); a scene on the world map ends with 0x41 of the map's song; scenes chained
  with `bh_text::chain(&["m03_map", "m03_warroom", "m03_sturm"])` hand over from song to song with 0x41 (`Scene::then`).
- **Sturm's scenes** (`bh_text/sturm.txt`, `mNN_sturm`): after 25 wins (not M21, M27 to M31, whose map scenes already carry the story), last of the scenes on the map: Sturm and the officers
  recruited by then on the result and the next mission. Each names only COs recruited before the mission it follows (M6/M7, M18/M19, M24/M25 may be played in either order).
- Music by role: Black Hole briefing `enemy1`/`enemy2`, Von Bolt's scenes `hagevolt`, Sturm `sturm`, Accord councils `ally1`, crises `pinch`, a recruit's victory his own theme, endings `ending1`/`ending2`.

## Commands
| Command | What |
|---|---|
| `aw2dev campaign scenes [--md] [--mission bh05]` | every scene with its role, AW2 song id and box count (needs `aw2dev build --examples`); exit 1 for a story scene without a song |
| `aw2dev campaign trace [--mission N ...]` | plays missions in the harness (CO screen, card, intro, forced win, victory, results, map scenes), samples every 20 frames (song id, fade fields, text, brightness, loudness of the recorded sound) into `devkit/work/campaign/trace/bh_mNN.json` + screenshots and prints scene -> song with silent samples; exit 1 on a silent dialogue (naval / air missions: the win aid cannot place a gunner, only the intro is traced) |
| `aw2dev campaign menu [--out DIR]` | starts the real app offline with the Dual Strike pack through the AI debug channel, opens Select Mode > Campaign and photographs the chooser at each entry (AW2, DS, BH, then the placeholders BH2 and Emerald Sun, `campaign_menu::COMING`) and their "Coming soon" boxes (`campaign_menu::draw_notice`); a campaign that becomes playable moves from `COMING` to `campaign_model::SOURCES` |
| `aw2dev sound list [--source roles\|aw2\|ds]` | the roles a scene may name; AW2's song ids with CO themes, event-script uses and known roles; Dual Strike's sequences by name from the .nds' archive |

Tests: `tools/bhtext/lint.py` (songs known, story scenes have one), Rust `bh_text` / `campaign_music` tests (`aw2dev test`), `tools/aw2test` `story_trace_bh_*` (`-k story_trace`), the suite's `campaign_scenes` check.
Limits: a trace follows one CO path; the text-id budget is 3,072 (`-k bh_text_budget`: 2,941 used after the Sturm scenes, 100 kept free).
