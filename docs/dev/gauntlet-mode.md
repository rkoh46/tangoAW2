# The Gauntlet mode: plumbing (`crate::gauntlet`, `crate::mode_menu`)

Select Mode's **GAUNTLET** (with the Dual Strike pack, offline): pick one CO (any CO the game has, no partner), then fight a map's enemy COs one after another in a single battle (the gauntlet engine,
[gauntlet.md](gauntlet.md): hidden lines that arrive when the lines before them fall), AW2's results, back on Select Mode. The maps are the content (`crate::gauntlet_mode`: `def()` returns a
`CampaignDef` whose missions are the maps, `ROSTER` every CO, `SOURCE` 4; Cinder Sea is `gauntlet_01`, seven maps today: the table in gauntlet.md); this page is how the mode is wired. Code: `gauntlet.rs`, `gauntlet_ui.rs` (the map selector and the colour pick), `mode_menu.rs`, `ds_campaign.rs`
(`start_gauntlet`, `gauntlet_start_script`, `gauntlet_end_script`, `after_map`, `end_of_battle`), `campaign_model.rs` (the source), tests `tools/aw2test/tests/test_gauntlet_mode.py`.

## The flow, screen by screen
1. **Select Mode.** GAUNTLET answers like Battle Maps and Link (A starts it, no Continue/New box). The wheel's mode store stores Campaign's New (1) and `gauntlet::picked` asks for this source
   (`ds_campaign::REQUEST`, `SOURCE` 4); a run saved halfway asks for Continue instead (hold SELECT with A to start a new run over it).
2. The game's own Campaign New handler (`0x0803BA4C`, trapped by `ds_campaign::start`) runs `start_gauntlet`: the record from Flash (kept), the session's flags and wins cleared (every run is a first
   play), `GAME_MODE` campaign, then the **start proc** (`gauntlet_start_script`, a proc of AW2's own script language; labels are found by scanning on and an END stops the scan, so the "round again"
   section is last): fade, then
   - **the map selector** (`gauntlet_ui.rs`, step 1) is **the game's own War Room map-select screen** (`ProcScr_PreviewMap`, `0x08616C54`: the "SELECT MAP" title and wallpaper, the map list, the
     map's picture, the faces of the enemies, the R record box), run as a blocking child of the start proc exactly as the War Room's flow runs it (`06 1 SELECT_MAP`; after it the script calls
     `FLOW_PICK_CHOSEN`). Nothing is drawn by us. What makes the game list our maps: one **map-table entry per mission** (`gauntlet_ui::id_of`: ids `0xF6..0xFD`, **in the selector's order**: the list shows the ids in order and the maps are sorted by the number of enemy COs, fewest first, `gauntlet_mode::order`; a map's identity everywhere else is its mission index, past Survival's `0xC9..0xEF`, the
     campaign's battle entry `0xF0` and the vault `0xF1`; the table is Survival's larger copy, `five_map::table`) holding the mission's compiled header (`ds_campaign::mission_header`: name, tiles for the
     picture) with the list's tab (`survival::TAB`, the War Room's tab byte `0x08090EF2`) while the screen is up and a tab no list shows otherwise, the player's CO slot `0xFF` and the **first three enemy
     COs in the order they come** in the CO bytes (+0x3C..: the screen draws a face for each; a map with more lines, as Iron Crown with Asuka's stage, shows the first three). While it is up the play
     state's game mode is the War Room's (the list builder lists a tab for Versus and the War Room only; `SAVED_MODE` keeps the campaign's, put back by `chosen`). The **record box** reads War Room
     record rows (five records of four bytes): the five `RECORD_POOLS` words are pointed at Survival's block of zeroed rows (`survival::ROWS`; the two modes are never open together) whose rows are the maps' **top five** (one row a map, by list position, built each frame from the records table, `gauntlet_ui::rows`; a result is one word `CO | days << 8 |
     score << 20`): the box shows 1st..5th with CO face, days and points, as the War Room's own box does. Two things the game's screen assumed of a War Room list (always dozens of maps) are patched for a list
     of two: `DrawMapList` draws only the rows there are (`survival::draw_map_list`, shared with Survival) and the scroll bar's track is at most its own length (`gauntlet_ui::scroll_track`, a trap at
     `0x0808731A`: a track of a hundred sprites overflowed the sprite buffer into the BG0 control shadow and garbled the screen). The game's own handler takes the pad: UP/DOWN browse, **A writes the
     map's id into the play state's map id, B zeroes it**; `chosen` reads which (as the War Room's flow does with `0x0803BD6D`), takes the mission (`ds_campaign::choose_gauntlet_map`: the session's mission and its header in
     the battle's map-table entry, the play state's map id back to `0xF0`) or, on B, goes back to Select Mode (`gauntlet::returning`: the wheel stays on GAUNTLET). A map bigger than the picture area (32 x 22 cells; Iron Crown is 40 x 26, Harvest Run 36 x 24, Chrome Meridian 38 x 26) is shown by its middle part: header +0x2C (the picture; the battle reads +0x00) points at a cropped LZ77 copy in free ROM (`PREVIEW_ROM` 0x08E20000, 0x800 a mission), so the picture never runs over the list (the property counters at the top count the part shown). The cursor row is read from the game's
     list each frame (`MAP_CURSOR`, `SHOWN` for the tests). Coming back from the colour pick's B the step stays 0 and the script skips the selector (`28 SKIP FLOW_PICK_UP`).
   - **the CO pick:** the CO screen's lists (`FLOW_CO_SETUP`: **all 35 COs**, the roster's unlock bits are not used: `unlocked_cos`), AW2's CO screen (`0x086165C0`). B comes back to the selector
     (`FLOW_PICK_AGAIN` starts the proc again).
   - **the army colour pick** (step 2): the colours the map's enemies do not wear as emblems in a row (`Entry::free`), the chosen one framed, its name under them; the player's CO and the enemies
     are shown. LEFT/RIGHT, A takes it, B goes back to the CO screen (`BACK_TO_CO`: the proc comes round again and skips the selector). A map with one free colour has nothing to pick; the cursor starts
     on the colour last worn on that map (`gauntlet_ui::LAST`, per session). The pick is kept in the mode's progress record (`ds_campaign::gauntlet_choice`: byte +7) and saved (`FLOW_SAVE`) before the
     battle, so a run saved halfway continues in it.
   - BG0 emptied, `ResetRulesAfterCampaignMap`, AW2's mission proc (`0x0849EBFC`: **the mission card** "MISSION 1 / Cinder Sea" (the map's name under it), the intro scene, the Setup phase if the mission
     has one, the battle). The card is AW2's campaign card, drawn by the mission proc itself with the mission's number; the War Room has no card at all (its battle starts at once), so
     there is no "War Room card" to borrow, and dropping the card would mean cutting AW2's mission proc apart.
3. The player's army wears the colour it picked (`gauntlet::keep_colour`, at the map's start): AW2's CO screen gives an army the colour of its CO's country, which would make a Drake pick Green Earth
   like the enemy's Drake. A pick of **Silver Nova** (a skin: `army_skin::SKIN + i`) sits on the lowest AW2 colour no army has (`army_skin::assign`; Cinder Sea: Orange Star's) from the pick on
   (`gauntlet::player_skin`, read by `army_skin::sync`: the ROM's palettes must hold it before the map's graphics load, a palette the game has loaded keeps the colours it was loaded with). The
   skin only recolours: the designs (Infantry, Mech, HQ, battle figures) stay the CO's nation's (`army_skin::design_*`; Silver Nova's designs are for the Silver Nova COs).
4. **The end.** AW2's VICTORY / DEFEAT and results screen, then `end_of_battle` (no progress, no world-map reveal) and, where AW2 starts its world map after a mission (`0x0803BADC`, `after_map`),
   the **end proc** (`gauntlet_end_script`): the record saved (`FLOW_SAVE`), fade, a jump to `ProcScr_MainMenu` (`0x0849E7F8`, as the War Room's flow leaves: the wheel keeps its remembered
   position; `gauntlet::returning` keeps it on GAUNTLET against AW2's campaign end, which puts it back on Campaign). `ds_campaign::tick` ends the session when the menu is up (`SOURCE` back to 0).
   Retrying is picking GAUNTLET again.

## The wheel (`mode_menu.rs`)
Eight entries with the pack: position 0 Battle Maps, 1 Online, 2 Design Room, 3 Versus, **4 Gauntlet** (directly above Versus on the screen, which lists positions from the top down, highest first),
5 Campaign, 6 War Room, 7 Survival; item table `[5, 8, 2, 4, 3, 1, 9, 0]` read at `(position + 2) % 8`. `DivRem(x, 6)` sites become 8, the position wraps 7, the help and options tables are
re-ordered by position (the harness resolves a position by name: `saves.position(e, "gauntlet")`, `saves.wheel_to`). An entry is an `Extra`: item id, its data in the ROM image
(palette, highlight, big label, small label), its OBJ palette and the first OBJ tile of its small label. Free on this screen (an OBJ survey, `gauntlet_mode_wheel_obj_resources_are_free`: no sprite
of AW2's own wheel or boxes draws palette 13 or 14 or tiles 0x2E0..0x33F, and the game never writes them): palette 13 and tiles 0x320.. (Survival), palette 14 and tiles 0x2E0.. (Gauntlet);
the Campaign chooser uses 8 and 10..12 and tiles 0x340..0x387, the badge 0x3E0. ROM data `0x08E40000..0x08E41FFF` (`rom_layout`). Labels are composed at run time from the letters of the
game's own labels (BIG_LETTERS / small cells), the palette is a blend of two of the game's (Versus red and Battle Maps gold = orange); nothing is committed.

## Records and saves
- **The record: the top five of each map, as the War Room keeps them.** AW2's War Room keeps five records per map, each one word (`CO | days << 8 | score << 20`: CO, days, points; no rank letter is stored or
  shown) and sorts them in `InsertBestScoreRecord` (`0x08017760`): a new result goes before the first record it beats, **more score first, then fewer days**; the same score in the same days goes after
  the older one; the fifth falls off, a result below all five is dropped. `gauntlet::insert` / `place` do the same on the Gauntlet's table (the harness has its own copy, `ga.war_room_insert`, written
  from the disassembly). **A win only** inserts (`best_score` is called for a loss too, with the winner's score; a loss writes nothing).
- **Keyed by the map's id, not its place in the list.** `gauntlet::record_id(key)`: `gauntlet_NN` is NN (1..255; the stage keys such as `gauntlet_02b` are not maps; a test checks every listed map has a
  distinct id). Re-ordering or adding maps never moves a record. The table has 16 slots (`SLOTS`), one per map with a record, a free slot has id 0.
- **Where it lives.** Flash slot 13 at +0x240, magic "AWGA", **format version 2** (the progress record's byte +5): `+0x00` the progress (0x20 bytes), `+0x20` the table, 16 slots of 0x18 bytes (`+0` the
  map id, `+1..3` 0, `+4..` five result words, best first): `RECORD_LEN` 0x1A0, ending at +0x3E0 (the sector's payload is 0xFAE bytes; BH's 0..0x120 and BH2's 0x120..0x240 are never touched, a record is
  written by replacing only its own region, `merge_record`; tests `gauntlet_mode_leaves_the_other_campaigns_saves_byte_identical` and, in Rust, `the_gauntlet_record_sits_after_bh_and_bh2_in_slot_13_and_touches_neither`).
  In RAM the table is the end of Survival's block of rows (`survival::ROWS` + 0x150, `gauntlet::TABLE`; the selector's record rows are the first 16 rows of the block, so a map list of up to 16 fits;
  `ram_map` has no separate region: Survival and the Gauntlet are never open together and the Gauntlet reloads the table from Flash whenever it starts). `ds_campaign::start_gauntlet` loads it
  (`gauntlet::load_record`), `stage_custom` saves it (`gauntlet::region`). `ds_campaign::RECORDS` (by list position) still holds each map's first place, rebuilt by `gauntlet::mirror`: `battle_points` reads
  it as the best before a battle and `Gauntlet.best()` reads it in the tests.
- **Migration from 0.9.4.** Version 0 (0.9.4: one word per list position, 8 bytes each from +0x20; Cinder Sea 0, Iron Crown 1) is converted on load: each position's best becomes the first place of its map's
  id (`gauntlet::migrate`, `LEGACY` is that list: it never changes) and the next save writes version 2. Test `gauntlet_mode_a_094_record_is_converted_to_the_top_five`.
- **No `SIM_VERSION` bump.** Records are offline Gauntlet state outside the simulation (netplay never runs the mode; `battle_points` still sees the same best score), so the sim stays 47.
- **Save in battle.** The map menu's Save works as in the BH campaigns: the shared mid-battle slot 12, the saved mission's top three bits name the source (`suspend::source_tag`: 4 << 5 = 0x80), the
  battle's block and the engine's tail (gauntlet state, stage mark) follow. `Continue` is picking GAUNTLET (`REQUEST` 2, `resume_mid`); a run's end drops the save. Test `gauntlet_mode_save_and_continue`.
- **Online.** Offline only: `mode_menu::tick` is called with `ds && ds_features && mode.is_none()` (as Survival's), the wheel is AW2's own six in a netplay room, and nothing of the battle's
  simulation is changed (no `SIM_VERSION` bump).

## The rout rule
Capturing a line's HQ routes that army at once (all its units destroyed by AW2's own `DefeatArmy`, every property it owns neutral), then the next line comes; the last line's HQ wins as before. It is the shared engine's, so every map has it by default: list every line but the last in `cut_off` ([gauntlet.md](gauntlet.md), "The rout"). Tests `-k gauntlet_rout`.

## Adding a map
The selector sorts the maps itself (fewest enemy COs first, ties in `def()`'s order): add the mission to `def()` and it lands in its place; nothing is keyed by the list position. Use `wire`, `arrival` and `chest` (gauntlet.md, "How to add a map") and the harness registry `aw2test/gauntlet_maps.py`.
A function in `gauntlet_mode.rs` added to `def()`'s missions (its key `gauntlet_NN` is its record id: records follow the key, not the list position) (every line but the last in `cut_off`: that is the rout rule) (spec `five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`): the selector lists it, with its enemies, and the colour pick
offers what its enemies leave, from the mission alone. **The enemies' colours are the map's data**: each enemy `ArmyDef::new(colour::.., CoSpec::Fixed(co))` in `armies` (index 1 on, in the order they
come) is what the selector shows and what the player may not wear; `Entry::free` computes the offered colours (AW2's five minus those, then Silver Nova while one of the five is free to host it), so a
map that fixes other colours changes the offer with no other edit. The enemy armies need teams of their own (team 2: team 0 is "my own number" and 1 is the player's). A map with later stages lists their enemies too and keeps a plain colour out of the offer if any stage's enemy wears it ([gauntlet.md](gauntlet.md), "Colours and stages"); a five-army map has the player in army 5 (its pick is the CO screen's army-1 pick, army 1 a fixed enemy).

## Aids and tests
`aw2dev gauntlet start [--co N]` boots the harness into the mode with a picture of each screen (wheel, map selector, CO pick, colour pick, Setup, first turn); `aw2dev gauntlet test` runs `-k gauntlet_mode`. The selector takes the pad only once the game's list is in (`Gauntlet.wait_select_map`: its fade-in and list take about a hundred frames; after UP/DOWN wait ~40 frames before A: the cursor's move blocks input). `selector_ids`, `entry_name`, `entry_cos`, `entry_tab` and `record_rows` read what the game's screen reads. `-k gauntlet_pictures_selector` takes the selector (the seven maps in their order) and the colour pick in the three looks (AW2 graphics, DS map graphics with the tilt, without it) into `selector_sheet.png` (`AW2TEST_SHEET` copies it).
`aw2test/gauntlet.py` is the driver (`Gauntlet.start(co, colour=..)`, `open`, `pick_colour`, `shown` (what the step lists, from `gauntlet_ui::SHOWN`), `capture`, `win`, `lose`, `best`, `results`, `saved_record`); wins use the mission's own captures (Drake's HQ, Sensei's, Hawke's) and the game's rout.
