# The Gauntlet mode: plumbing (`crate::gauntlet`, `crate::mode_menu`)

Select Mode's **GAUNTLET** (with the Dual Strike pack, offline): pick a map, then one army screen (any CO the game has, no partner, and an army colour the map leaves free), then fight a map's enemy COs one after another in a single battle (the gauntlet engine,
[gauntlet.md](gauntlet.md): hidden lines that arrive when the lines before them fall), AW2's results, back on Select Mode. The maps are the content (`crate::gauntlet_mode`: `def()` returns a
`CampaignDef` whose missions are the maps, `ROSTER` every CO, `SOURCE` 4; Cinder Sea is `gauntlet_01`, twelve maps today, room for 32: the table in gauntlet.md); this page is how the mode is wired. Code: `gauntlet.rs`, `gauntlet_ui.rs` (the map selector and the army screen), `mode_menu.rs`, `ds_campaign.rs`
(`start_gauntlet`, `gauntlet_start_script`, `gauntlet_end_script`, `after_map`, `end_of_battle`), `campaign_model.rs` (the source), tests `tools/aw2test/tests/test_gauntlet_mode.py`.

## The flow, screen by screen
1. **Select Mode.** With **no run saved**, GAUNTLET answers like Battle Maps and Link (A starts it, no box): the wheel's mode store stores Campaign's New (1) and `gauntlet::picked(core, false)` asks for this source
   (`ds_campaign::REQUEST`, `SOURCE` 4). With **a run saved halfway** (`gauntlet::saved`: slot 12, the save's source tag 4), A opens AW2's own item box, as Campaign's entry does: **CONTINUE** (top row) and
   **NEW** (bottom row), the help line under the wheel saying "Continue your saved Gauntlet run." / "Start a new run. The saved run is dropped." (text slots 41 and 42 of Survival's block, the wheel's options
   table at position 4). The `cmp r0, #4` traps answer 4 for GAUNTLET only without a save (`mode_menu::direct`); with one the game opens the box itself (cursor on Continue; the wheel also comes back from a mode
   with the box open on the row last taken, as AW2's does). The box's commit has no case for item 9, so a trap at `0x08082352` (`box_commit`) stores Campaign's New (1) and `picked(core, cursor is the top row)`
   (REQUEST 2 = Continue, 1 = New). The rows' sprites are drawn by a chain on the item at `0x08083B26..`: a trap at its `cmp r0, #5` makes the Gauntlet the War Room (CONTINUE / NEW labels, `GetWarRoomSaveFlag`
   `0x0803BC94` answered true for it so Continue is never dimmed), and `remap` (the sprite flush) puts the War Room's palette-7 row into the Gauntlet's OBJ palette 14. **Continue** resumes the battle (no selector,
   no army screen). **New** goes to the selector and the army screen; **the save is dropped only when the new run really starts** (`gauntlet_ui::apply`, the army screen's A: from the game's directory at once, from
   Flash with the next write), so B, B back to Select Mode keeps it (the wheel is back with the box open on New). Slot 12 is shared with the BH Campaigns (saves are told apart by the source tag): a BH save is
   neither offered as Continue nor dropped by a new Gauntlet run; the Gauntlet's own Save replaces whatever halfway save the slot holds (one at a time, as the BH Campaigns replace each other's).
   Tests: `-k gauntlet_mode_a_saved_run` (the box and its two lines), `gauntlet_mode_continue_in_the_box` (byte for byte), `gauntlet_mode_new_in_the_box` (the drop timing), `gauntlet_mode_a_bh_save` (shared slot);
   the audit scene `aw2dev gfx audit --scenes wheel_box` shows the box in AW2, DS + tilt and DS flat. The test driver: `Gauntlet.open(box="continue"|"new")`, `choose_in_box`.
2. The game's own Campaign New handler (`0x0803BA4C`, trapped by `ds_campaign::start`) runs `start_gauntlet`: the record from Flash (kept), the session's flags and wins cleared (every run is a first
   play), `GAME_MODE` campaign, then the **start proc** (`gauntlet_start_script`, a proc of AW2's own script language; labels are found by scanning on and an END stops the scan, so the "round again"
   section is last): fade, then
   - **the map selector** (`gauntlet_ui.rs`, step 1) is **the game's own War Room map-select screen** (`ProcScr_PreviewMap`, `0x08616C54`: the "SELECT MAP" title and wallpaper, the map list, the
     map's picture, the faces of the enemies, the R record box), run as a blocking child of the start proc exactly as the War Room's flow runs it (`06 1 SELECT_MAP`; after it the script calls
     `FLOW_PICK_CHOSEN`). Nothing is drawn by us. What makes the game list our maps: one **map-table entry per mission** (`gauntlet_ui::id_of`: the last n of `gauntlet_ui::SLOT_IDS` (0xC9..=0xEF, 0xF2..=0xFD), **in the selector's order**: the list shows the ids in order and the maps are sorted by the number of enemy COs, fewest first, `gauntlet_mode::order`; a map's identity everywhere else is its mission index, an id is a slot in the list, never the map's identity; the
     campaign's battle entry `0xF0` and the vault `0xF1`; the table is Survival's larger copy, `five_map::table`) holding the mission's compiled header (`ds_campaign::mission_header`: name, tiles for the
     picture) with the list's tab (`survival::TAB`, the War Room's tab byte `0x08090EF2`) while the screen is up and a tab no list shows otherwise, the player's CO slot `0xFF` and the **first three enemy
     COs in the order they come** in the CO bytes (+0x3C..: the screen draws a face for each; a map with more lines, as Iron Crown with Asuka's stage, shows the first three). While it is up the play
     state's game mode is the War Room's (the list builder lists a tab for Versus and the War Room only; `SAVED_MODE` keeps the campaign's, put back by `chosen`). The **record box** reads War Room
     record rows (five records of four bytes): the five `RECORD_POOLS` words are pointed at the Gauntlet's own record block (`gauntlet::BLOCK`, see "Records and saves") whose rows are the maps' **top five** (one row a map, by its map-table id, built each frame from the records table, `gauntlet_ui::rows`; a result is one word `CO | days << 8 |
     score << 20`): the box shows 1st..5th with CO face, days and points, as the War Room's own box does. Two things the game's screen assumed of a War Room list (always dozens of maps) are patched for a list
     of two: `DrawMapList` draws only the rows there are (`survival::draw_map_list`, shared with Survival) and the scroll bar's track is at most its own length (`gauntlet_ui::scroll_track`, a trap at
     `0x0808731A`: a track of a hundred sprites overflowed the sprite buffer into the BG0 control shadow and garbled the screen). The game's own handler takes the pad: UP/DOWN browse, **A writes the
     map's id into the play state's map id, B zeroes it**; `chosen` reads which (as the War Room's flow does with `0x0803BD6D`), takes the mission (`ds_campaign::choose_gauntlet_map`: the session's mission and its header in
     the battle's map-table entry, the play state's map id back to `0xF0`) or, on B, goes back to Select Mode (`gauntlet::returning`: the wheel stays on GAUNTLET). A map bigger than the picture area (32 x 22 cells; Iron Crown is 40 x 26, Harvest Run 36 x 24, Chrome Meridian 38 x 26) is shown by its middle part: header +0x2C (the picture; the battle reads +0x00) points at a cropped LZ77 copy in free ROM (`PREVIEW_ROM` 0x08E20000, a 0x800 slot each, `previews()`), so the picture never runs over the list (the property counters at the top count the part shown). The cursor row is read from the game's
     list each frame (`MAP_CURSOR`, `SHOWN` for the tests).
   - **the army screen** (step 2, one screen for the CO and the colour; the game's CO screen is not used): Versus' Teams screen laid out for one player against the map's CPUs, drawn by us over
     the finished frame (`gauntlet_ui::draw`) from the pieces the Teams screens use, nothing new of our own: `army_cards::draw`, the cards, windows and pink help plate of AW2's Teams
     screen, the page online rooms and offline Versus share (with the pack Versus' Teams screen is this page in every look, DS map graphics or not, so the Gauntlet's is too: Dual Strike's
     NORMAL BATTLE cards, `ds_coselect::draw_versus`, are only drawn when that page is not, which never happens with the pack). The frame is the Teams screen's own, drawn by `army_cards::teams_frame` from the
     cartridge (read once): the ground (BG3, the world map: tiles `0x0822FEF0`, map `0x0822F9AC`, palettes `0x082344AC`, the screen's scroll) and the title banner, which is the title font
     (`online_art::TitleFont`, the mission card's letters, banner palette `0x080F6164`) so it says GAUNTLET where Versus' says TEAMS; the map's name leads the help plate. The cards carry the
     game's own 1P and CP tag sprites (ids 74 and 78, `Seat::tag`; Versus' are sampled from the game's frame). A screen with tagged seats also centres three cards and shows every CO name
     whole: with arrows when they fit, else without, on two lines on a narrow card (Clone Andy on five cards). `aw2dev audit text` (with the Dual Strike ROM, which it uses when it is there)
     paints the screen at two to four enemies with the six widest names of the roster and reports a name that does not fit (`audit::cut`). The first card is the player's (tag 1P, the window cream),
     then the map's enemies in the order they come, as CPU cards with their CO and the colour the map gives them (a line that wears Silver Nova shows its sun, `Entry::shown_colour`; at most four: the screen has five cards, so Iron Crown's Asuka stage is not shown).
     **Keys:** SELECT opens Set Skills (below); UP / DOWN choose the CO (all 35 of `gauntlet_mode::ROSTER`, round again, a held key repeating as AW2's cursors do; the cursor keeps its place between visits), R / L the colour
     (round the colours the map leaves free, `Entry::free`, Silver Nova among them where the map allows it; a map with one free colour shows it and R changes nothing; the cursor starts
     on the colour last worn on the map, `gauntlet_ui::LAST`, per session), A starts, B goes back to the selector (the proc comes round again: `FLOW_PICK_AGAIN`). **The enemies are not
     editable:** LEFT and RIGHT do nothing (there is no other army to move to). A saves the colour in the mode's progress record (`ds_campaign::gauntlet_choice`: byte +7) and the proc
     saves (`FLOW_SAVE`) before the battle, so a run saved halfway continues in it. The CO goes to the armies as AW2's CO screen gives its picks: `gauntlet_ui::apply` calls
     `SetArmyCoIdsFromList` with the list the CO screen reads (`0x030058D4`), after `tag::set_cos` (a jump to the function runs none of the traps on it) which moves a five-army map's pick to the
     player's fifth army; `gauntlet_ui::keep_pick` puts it back after `mission_start`, which sets army 5's CO to the mission's own, none.
     **SELECT opens Set Skills** (`skills_panel`, source `FROM_GAUNTLET`: `skills_panel::tick` runs before `gauntlet_ui::tick`, takes every key while it is up and `ds_coselect::apply` draws nothing over it) for the CO picked,
     editing the **Campaign** set: the Gauntlet is a `ds_campaign` session, and `co_skills::ids_for` gives the player's army that set (the EXP a win earns goes to the same CO). B or SELECT closes it back to the army screen with the CO, colour
     and cursors as they were. The panel clears DISPCNT's window enables with the layers (this screen leaves them on, which cut the board out of a white screen) and puts them back. Help line: "Left Right: CO  R: Colour  SELECT: Skills".
     Test `-k gauntlet_mode_army_screen_select`, picture `aw2dev gfx audit --scenes army_skills`.
   - BG0 emptied, `ResetRulesAfterCampaignMap`, AW2's mission proc (`0x0849EBFC`: **the mission card** "MISSION 1 / Cinder Sea" (the map's name under it), the intro scene, the Setup phase if the mission
     has one, the battle). The card is AW2's campaign card, drawn by the mission proc itself; the War Room has no card at all (its battle starts at once), so
     there is no "War Room card" to borrow, and dropping the card would mean cutting AW2's mission proc apart. **The Gauntlet's card says GAUNTLET** (`gauntlet_card.rs`, only while `gauntlet::session`): the word
     above the name (OBJ tiles 0..23, three 32x16 sprites) is repainted as GAUNTLET from the title font's letters (columns as they are, rows area-averaged to 15) and drawn 18 px right (traps at the two
     template draw calls, `0x0807C362` / `0x0807C47A`), the number's digit tiles (28..67) are blanked (the number was the map's place in the definition, meaningless in the selector's order), and the seal's
     band ("MISSION START", BG2 affine 8 bit tiles, rows 74..85) is cleared and set as GAUNTLET in the stamp's own red ramp (12 rows). The art is made from the ROM's font when the card runs (a trap at
     each frame routine `0x0807C034`/`0x0807C2D4`/`0x0807C46C` writes it when VRAM does not have it yet: the card's own loads are not at a fixed point); nothing is stored. The seal is only edited when every
     band cell's tile is used by that cell alone, else the stamp keeps its words. Every real campaign's card is untouched. Pictures: `aw2dev gfx audit --scenes mission_card` (`gauntlet/mission_card` and
     `bh_campaign/mission_card`, three looks); tests `gauntlet_card_says_gauntlet`, `gauntlet_card_campaigns_keep_mission` (`-k gauntlet_card`). No `SIM_VERSION` bump: offline only, VRAM only.
3. The player's army wears the colour it picked (`gauntlet::keep_colour`, at the map's start): AW2's rules give an army the colour of its CO's country, which would make a Drake pick Green Earth
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
  distinct id). Re-ordering or adding maps never moves a record. The table has 32 slots (`SLOTS`), one per map with a record, a free slot has id 0.
- **Where it lives.** Flash slot 13 at +0x240, magic "AWGA", **format version 2** (the progress record's byte +5): `+0x00` the progress (0x20 bytes), `+0x20` the table, 32 slots of 0x18 bytes (`+0` the
  map id, `+1..3` 0, `+4..` five result words, best first): `RECORD_LEN` 0x320, ending at +0x560 (a record saved by the first top-five build, 16 slots and 0x1A0 bytes, is a prefix of it: it loads whole and the other slots are free, so no version bump) (the sector's payload is 0xFAE bytes; BH's 0..0x120 and BH2's 0x120..0x240 are never touched, a record is
  written by replacing only its own region, `merge_record`; tests `gauntlet_mode_leaves_the_other_campaigns_saves_byte_identical` and, in Rust, `the_gauntlet_record_sits_after_bh_and_bh2_in_slot_13_and_touches_neither`).
  In RAM the Gauntlet has a block of its own (`gauntlet::BLOCK` = 0x0203E800, `ram_map`): the selector's record rows (one 0x14-byte row per map-table id from `gauntlet_ui::ROW_BASE` 0xDC to 0xFD: 34 rows), then the table (`gauntlet::TABLE`, 32 slots). Its bytes are time-shared with the Teams screen's borrowed tiles, the two-front store and the War Room's rows on Dual Strike's maps (listed in `ram_map::TIME_SHARED` with the reasons: a Versus screen, a two-front battle and the DS table's War Room are never part of the Gauntlet's flow). Survival's block of rows is no longer used by the Gauntlet. `ds_campaign::start_gauntlet` loads it
  (`gauntlet::load_record`), `stage_custom` saves it (`gauntlet::region`). `ds_campaign::RECORDS` (by list position) still holds each map's first place, rebuilt by `gauntlet::mirror`: `battle_points` reads
  it as the best before a battle and `Gauntlet.best()` reads it in the tests.
- **Migration from 0.9.4.** Version 0 (0.9.4: one word per list position, 8 bytes each from +0x20; Cinder Sea 0, Iron Crown 1) is converted on load: each position's best becomes the first place of its map's
  id (`gauntlet::migrate`, `LEGACY` is that list: it never changes) and the next save writes version 2. Test `gauntlet_mode_a_094_record_is_converted_to_the_top_five`.
- **No `SIM_VERSION` bump.** Records are offline Gauntlet state outside the simulation (netplay never runs the mode; `battle_points` still sees the same best score), so the sim stays 47.
- **Save in battle.** The map menu's Save works as in the BH campaigns: the shared mid-battle slot 12, the saved mission's top three bits name the source (`suspend::source_tag`: 4 << 5 = 0x80), the
  battle's block and the engine's tail (gauntlet state, stage mark) follow. `Continue` is picking GAUNTLET (`REQUEST` 2, `resume_mid`); a run's end drops the save. Test `gauntlet_mode_save_and_continue`.
- **Online.** Offline only: `mode_menu::tick` is called with `ds && ds_features && mode.is_none()` (as Survival's), the wheel is AW2's own six in a netplay room, and nothing of the battle's
  simulation is changed (no `SIM_VERSION` bump).

## The map list's room (how many maps, and what limits it)
The list takes **up to 32 maps** (`gauntlet_ui::MAX_MAPS`). Three things set that number, and all three allow 32:
- **Missions:** each map is a mission of the Gauntlet's campaign; the campaign engine allows 32 (`campaign_model::MAX_MISSIONS`: the record words by mission in `ds_campaign::RECORDS`, one 0x800-byte cropped picture each, and one more for each later stage of a two-map run (SELECT's picture), in free ROM at `PREVIEW_ROM` 0x08E20000..0x08E30000: 32 slots in all).
- **Map-table ids:** the game's list walks ids 0..=0xFD (0xFE is the Dual Strike battle's, the walk's counter is a byte). `gauntlet_ui::SLOT_IDS` has 51 ids, ascending: Survival's entries 0xC9..=0xEF, then the free 0xF2..=0xFD (0xF0 is the campaigns' battle entry, 0xF1 the Colonel's Vault). A list of n maps takes the **last n** of them, so the first twelve maps use only
  0xF2..0xFD and never touch Survival; map 13 and on borrow Survival's entries from the top down (0xEF, 0xEE, ...) and give them back **whole** when the selector closes (`survival::restore_entry`, which rewrites the header of the build; Survival's per-frame list is held off while the selector is up). Survival and the Gauntlet are never open together.
  The ids move when a map is added (the list is sorted by enemy count), so an id means nothing outside the selector; a map's identity is its mission and its record key `gauntlet_NN`.
- **Records:** 32 slots in Flash and RAM (see above), rows for 34 ids.
To go past 32: raise `MAX_MISSIONS` (and `RECORDS` / the `ds_campaign` regions that depend on it), `PREVIEW_ROM`'s room, `gauntlet::SLOTS`, `gauntlet_ui::MAX_MAPS` and `ram_map`'s block, and find more ids (there are none left below 0xFD without taking the Vault's or Versus' pool).
The unit tests `a_full_list_has_ids_rows_records_and_order_that_work` (32 maps' ids, rows, records and order) and, in the harness, `-k gauntlet_mode_a_long_list` (the aid `TANGOAW2_GAUNTLET_SLOTS=32` lays the ids out for a full house, so today's twelve borrow Survival's entries: every map is listed with its name, the list scrolls to the last, the record box reads the borrowed ids' rows, Survival's entries come back byte for byte) cover it.

## Music under the dialogue (`gauntlet_mode::add_music`, `OPENING`)
Every Gauntlet scene plays a song, as AW2's campaign does under each story scene (op 0x41 starts it, op 0x42 fades it out before the box closes; `custom_campaign::Compiler::one_scene`; the battle's CO theme returns at the next turn change).
`def()` runs `add_music` over every mission, so a new map is never silent:
- the opening speech: the role named for the map in `OPENING` (`(mission key, campaign_music::NAMED role)`; a map without a row gets `DEFAULT_OPENING`, `enemy1`);
- every other scene (a line falls and the next CO arrives, a day scene, the stage switch, the victory): the theme of the CO who speaks last in it (`Track::Co`), that is the arriving CO's own song.
A scene that already has a `song` keeps it (set `.with_song(...)` on it for a special one). To give a new map its own opening, add one row to `OPENING`.
List them: `./aw2dev campaign scenes --campaign gauntlet` (every scene, its role and AW2 song id; exit 1 for a scene without a song; needs `aw2dev build --examples`).
Test: `-k gauntlet_music` (per map: the song the game has started while the opening's boxes are up and while the first fall's arrival boxes are up is the listed one, and the player's CO theme is back after the next turn).
Offline script data only (Gauntlet never runs online or in Versus): no `SIM_VERSION`.

## Arrival scenes: one box per speaker, opened fresh (`Compiler::one_scene`, `battle_scene`)
A scene a trigger plays in the middle of a battle (`Action::Scene`: a line arriving after a capture or a rout; BH2's M31 and the BH campaigns' triggers too) used to be compiled as AW2's own scenes are: `0x17` open with the first face, then `0x38` (a speaker) and `0x19` (a text) for each line,
`0x18` close. In a box opened that way in the middle of a battle two things were wrong, on every Gauntlet map (Cinder Sea and Iron Crown too, as released) and found by the pictures: the **first box's text was drawn over by other pictures** (the box stood at the bottom of the screen, where the
map's windows are, and some of its text tiles were also tiles of the face beside it), and **no box after the first speaker's ever showed** (the departing CO's line was all the player saw: `0x38` alone changed nothing visible there). Now such a scene opens with an empty box that closes at once, and every
change of speaker closes the box and opens one for the new face; the boxes then stand at the top of the screen with their own tiles and every speaker's lines show, in all three looks. Scenes elsewhere (the intro, the winning scene, the stage and world-map scenes) are compiled as before.
It is script data of the offline campaigns (no netplay, no `SIM_VERSION`). Test `-k arrival_boxes_are_all_shown` (every map's arrival scenes, Cinder Sea and Iron Crown included): at least two boxes are shown for a departing and an arriving CO, and no text tile of a box is a tile of the face
beside it (the garbled box shared 38 of them); it fails without the change. `settled_png` in `test_gauntlet_lines_pictures.py` waits out the white flashes of a reveal so a sheet never holds a blank capture.

## The "has lost" message and the arrival scene (`rout_message_hook`)
The game's own message after a rout ("The Green Earth Army has lost!", `sub_08019818(text id)`: it starts an event script with a dialogue box) opened its box before the arrival scene's, and both drew into the same text tiles: the two texts came out mixed for a second after every line's fall (found by the audit's `text` detector, `aw2dev gfx audit`). Now `defeat_army` marks a line routed by its HQ's capture whose fall plays a scene (`campaign_model::scene_cut`), `rout_message_hook` leaves that one message out and points the mission's `lost_text` table entry at the game's own text for the army, and the scene opens with a narration box (no face) that shows it, then the speakers. The final line's fall and every other defeat keep the game's message. Offline script and text data only (no `SIM_VERSION`). Regress: `rout_message_over_scene`.

## Faces in the boxes of a five-army battle (`five::moved_palette`)
A speaker's face is drawn with BG palette 9, and in a five-army battle (every map whose player is army 5: Harvest Run, Chrome Meridian, Blue Bastion, Last Eclipse, Iron Crown, BH2's five-army missions) the same bank holds the current army's moved-unit grey
(`five::moved_palette` writes it before every moved unit is drawn: the fifth army needed a bank for it). Written over the face's palette on every frame, it turned each face of a scene to the washed-out colour of the player's army (Von Bolt, Aria and Asuka blue, Andy and Max
in the player's blue, green or yellow). The grey now waits while an event script runs or the dialogue box's proc (`0x08014401`) is up, and is put back at the next moved unit drawn once the scene is over. Tests (`-k gauntlet_lines`): `arrival_boxes_are_all_shown_and_clean` also asks that the first
box's face palette is the departing CO's own (its presentation row's palette, one of its eight schemes: row `+0x08` of the table at the pool word `0x08039B7C`), the last box's the arriving CO's and every box's one of the two, on every map; `intro_and_victory_faces_have_their_own_palette` the same for the intro and
the winning scene (those scenes were not hit: the grey is written only while moved units are drawn). The arrival test fails without the change on Harvest Run and Last Eclipse (every box 'WRONG'). Not simulation state a released build has (the palette buffer of an unreleased build): `SIM_VERSION` stays 48.

## The rout rule
Capturing a line's HQ routes that army at once (all its units destroyed by AW2's own `DefeatArmy`, every property it owns neutral), then the next line comes; the last line's HQ wins as before. It is the shared engine's, so every map has it by default: list every line but the last in `cut_off` ([gauntlet.md](gauntlet.md), "The rout"). Tests `-k gauntlet_rout`.

## Scoring (the rank and points of a run of several lines)
AW2's end-of-battle score is Speed + Power + Technique (each 0..100); the rank is C up to 199, B to 249, A to 279, S above. It was written for one map against one army, and a Gauntlet is N lines in one battle,
so each part is judged per line here (the rules are the ROM's, `aw2test/gauntlet_score.py` writes them out; the part of the ROM: `0x080263A4` Speed, `0x08026424` Power, `0x080264BC` Technique):
- **Speed** = 100 up to the map's **par days**, then 100 - 100 x (day - par) / (3 x par), 0 at four times par. The par is the map header's (`MissionDef::rank_days`) and is data per map: `gauntlet_mode::par_days` =
  `PAR_PER_LINE` (12) days for each enemy line (`line_count`: every fixed CO of the map and its stages; Iron Crown's four lines and Asuka are five: 60), unless the map is in `PAR_OVERRIDES` (Blue Bastion and Last Eclipse, the two
  biggest, 52). No map's par got stricter than it was (22..44 before). A new map needs nothing: its par follows its lines; add an override only for a map that costs more days a line.
- **Power** = min(100, 1000 x the most units the player destroyed in one turn / the units the enemy armies built). Every line's wave and production counts in that sum, so a four-line run scored a quarter of what the same
  turn scored on one map. `gauntlet::power_sum` (a trap in the middle of AW2's Power, `POWER_SUM`) divides the sum by the map's lines (`lines_of`, rounded up) in a Gauntlet session.
- **Technique** (campaign: 120 - 100 x units lost / units built, 0 when nothing was built) is a ratio and needs no change on one stage. Iron Crown's **stage switch** used to reset the player's records (units built and lost,
  most kills, the enemy's builds) so the score judged Asuka's Keep alone (Technique 0 unless the player built something there). `gauntlet::carry_score_out` (at the survivors' snapshot, `stage::snapshot`) keeps them in
  `stage::SCORE_CARRY` and `carry_score_in` (at the arrival) adds them to the new records: the whole run is scored. (The game's counters are bytes that stop at 255.)
- **The record and EXP** are read from the same total (`InsertBestScoreRecord`'s score), so the top five, the days and `battle_points::results` (EXP: the mission's previous best taken off) follow the new score. Results saved
  before the rework keep their old scores in the top five (they were lower: a new run replaces them in place).
- Real campaigns, the War Room and Versus are untouched: every trap here begins with `gauntlet::session`, and nothing it changes is simulation state of a Versus battle (no `SIM_VERSION` bump).
- Tools: `aw2dev gauntlet score [--markdown]` (par per map, a quick/steady/slow run's score before and now), tests `-k gauntlet_score` (the real ROM's fields on Cinder Sea and Iron Crown against the formula; run against an older build
  with `AW2TEST_RUNNER_DIR` to see its numbers), cargo `par_days_grow_with_the_lines_of_the_run`.

## Units on offer
AW2's build menu asks `sub_080261E8` (`0x0802D6CA`) before it lists the Neotank, and in campaign mode that function says yes only when the army's colour has its story flag (0x65..0x68, Black Hole's colour never): a Gauntlet run is
a campaign session with no story, so bases offered no Neotank (the factory read Recon, Tank, Md Tank, Megatank...). `gauntlet::neotank_open` (`NEOTANK_OPEN`) answers yes in a Gauntlet session, so every map offers what a Versus
map with the pack offers (airports and ports never had the gate; the computer's armies buy by the pack's production, not by this menu). Test `-k gauntlet_build_menu` (every map's base, airport and port against a Versus battle's).

## A run of several maps (Iron Crown)
A mission with stages (`MissionDef::stages`) is several maps in one run. The selector's list shows such a mission under `MissionDef::list_title` ("Iron Crown *": the star, which the AW2 font has, marks a map with a hidden second one; a second text id, `Built::list_names`,
`ds_campaign::list_name`, put in the map-table entry's name by `gauntlet_ui::entries_in_table`; the mission card keeps the title) and the army screen's help plate names the maps (`stage_titles`: "Iron Crown + Asuka's Keep: 2 maps").

**SELECT on the selector shows the second map** (`gauntlet_ui::flip`, generic: any entry with `stage_titles`; `Entry::stage_lines` / `stage_maps` carry each later stage's enemy lines and built map). The cursor's entry is rewritten with the stage shown
(`STAGE_SHOWN`, `UI_STAGE` in the harness): the picture pointer (+0x2C: a blob of that map in the next free 0x800 slot of `PREVIEW_ROM`, `previews()`: slots go to the cropped first maps and the later stages' pictures in order, 32 in all) and
the faces (+0x3D..: that stage's enemy lines, three at most; +0x18, the player count the screen draws faces from: lines + 1). The game does not redraw from a changed entry by itself: SELECT does what the game does on a cursor move
(found in `ProcScr_PreviewMap`'s list proc, script `0x08616CF4`, whose input handler at `0x08086132` calls `0x08087B60(list index)` for the faces and sets +0x4E to -1 and +0x4C to 0, which starts the 28-frame change of the
picture that loads it from the entry at frame 12, `0x08086EB0`): `fog_view::start_program` runs `0x08087B60` at the next sprite flush and the proc's two halfwords are set. A map-table entry other than the cursor's is always the first map's,
the cursor moving resets to the first map (the game draws the new entry itself), SELECT on a one-map entry does nothing, and `leave` resets it. The selector has no help line of its own, so the hint is the star alone. Tests
`-k gauntlet_mode_select_flips`, picture `aw2dev gfx audit --scenes iron_crown_map2`. No `SIM_VERSION`: offline UI state in EWRAM only.

Pictures of the two-map run's army screen: `aw2dev gauntlet two-maps`, `-k gauntlet_two_maps`.

## Adding a map
The steps to add `gauntlet_NN` (NN = the next number; its record key, never reused):
1. Spec `five/gauntlet/spec/gauntlet_NN.py`; `aw2dev maps gen --campaign gauntlet` (writes `five/gauntlet/gauntlet_NN.txt` and `gauntlet_map_data.rs`); `aw2dev maps lint --source gauntlet` clean. Keep a map to about 110 properties (Neon Row with 150 stalled the computer's turn on day 1, with 210 some properties stayed owned after a rout; 108 is clean).
2. Waves: `aw2dev maps wave gauntlet_NN --zone x0,y0,x1,y1 --kinds ...` (ships and landers on a sea map by hand: the tool does not know water).
3. A mission function in `gauntlet_mode.rs` (`wire`, `arrival`, `chest`) and its name in `def()`'s missions (the next mission index; a map's mission index is its identity for the colour memory and the records' mirror). Its enemy COs must be ones no other map uses (the test `no_two_maps_share_an_enemy_co_but_the_named_exceptions`).
4. `text_of` in the Rust tests, `aw2test/gauntlet_maps.py` (mission, lines, HQs, waves, chests) and `SELECTOR_ORDER` / `SELECTOR_TITLES` in `aw2test/gauntlet.py` (the order is by enemy count, ties by mission).
5. Check `-k gauntlet`, `cpu_port_idle_gauntlet`, `cpu_progress`, and look at the pictures (`aw2dev gauntlet maps-pictures`).
**The limit is 32 maps** (see "The map list's room"): the 33rd needs `MAX_MISSIONS`, the cropped pictures' ROM and more map-table ids first. Nothing else is keyed by the map's place in the list.

(Older notes:)
The selector sorts the maps itself (fewest enemy COs first, ties in `def()`'s order): add the mission to `def()` and it lands in its place; nothing is keyed by the list position. Use `wire`, `arrival` and `chest` (gauntlet.md, "How to add a map") and the harness registry `aw2test/gauntlet_maps.py`.
A function in `gauntlet_mode.rs` added to `def()`'s missions (its key `gauntlet_NN` is its record id: records follow the key, not the list position) (every line but the last in `cut_off`: that is the rout rule) (spec `five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`): the selector lists it, with its enemies, and the colour pick
offers what its enemies leave, from the mission alone. **The enemies' colours are the map's data**: each enemy `ArmyDef::new(colour::.., CoSpec::Fixed(co))` in `armies` (index 1 on, in the order they
come) is what the selector shows and what the player may not wear; `Entry::free` computes the offered colours (AW2's five minus those, then Silver Nova while one of the five is free to host it), so a
map that fixes other colours changes the offer with no other edit. The enemy armies need teams of their own (team 2: team 0 is "my own number" and 1 is the player's). A map with later stages lists their enemies too and keeps a plain colour out of the offer if any stage's enemy wears it ([gauntlet.md](gauntlet.md), "Colours and stages"); a five-army map has the player in army 5 (its pick is the CO screen's army-1 pick, army 1 a fixed enemy).

## Kit commands (the tools of a map's whole life)
- `aw2dev gauntlet new-map NN "Name" [--apply]`: scaffolds `five/gauntlet/spec/gauntlet_NN.py` and prints (with `--apply` inserts) the `gauntlet_mode.rs` stub and its place in `def()`; refuses a duplicate id (spec file or mission) and a map past `gauntlet_ui::MAX_MAPS` (32). Code: `devkit/aw2/commands/gauntlet.py` (`plan_new_map`, `read_maps`).
- `aw2dev gauntlet cos`: every map's enemy COs in order, read from `gauntlet_mode.rs` (`CoSpec::Fixed`), the reused ones next to the `allowed` list of the unit test `no_two_maps_share_an_enemy_co_but_the_named_exceptions` (fails on an unnamed repeat), and the COs of `ROSTER` no map uses yet.
- `aw2dev gauntlet army-sheet [--map NN ...]`: the army screen (as it opens, CO changed, R pressed) of the chosen maps in the three looks as one sheet (`-k gauntlet_army_pictures`, env `AW2TEST_ARMY_MISSIONS`).
- `aw2dev gauntlet faces [--map NN ...]`: each CO's dialogue-box face beside the same CO on the army screen (`-k gauntlet_faces_vs_army_screen` + `tools/aw2test/compose_faces.py`, env `AW2TEST_FACES_MAPS`).
- `aw2dev gauntlet score [--markdown]`: every map's par days and a quick, a steady and a slow run's total and rank before the rework and now (`aw2test/gauntlet_score.py`; "Scoring").
- `aw2dev gauntlet two-maps [--out FILE]`: Iron Crown's selector (as it opens, 2 and 4 seconds later) and army screen in the three looks as one sheet (`-k gauntlet_two_maps`; "A run of several maps").
- `aw2dev campaign scene-check`: the arrival-box and face-palette tests of every map and BH2 M31, per map (docs/dev/campaign-scenes.md). Run it after any scene or dialogue work.

## Aids and tests
`aw2dev gauntlet start [--co N]` boots the harness into the mode with a picture of each screen (`1_wheel`, `2_map_selector`, `3_army_screen`, `4_army_screen_co`, `5_setup`, `6_first_turn`; the command fails if one is missing); `aw2dev gauntlet test` runs `-k gauntlet_mode`. The selector takes the pad only once the game's list is in (`Gauntlet.wait_select_map`: its fade-in and list take about a hundred frames; after UP/DOWN wait ~40 frames before A: the cursor's move blocks input). `selector_ids`, `entry_name`, `entry_cos`, `entry_tab` and `record_rows` read what the game's screen reads. `-k gauntlet_pictures_selector` takes the selector (the seven maps in their order) and the army screen in the three looks (AW2 graphics, DS map graphics with the tilt, without it) into `selector_sheet.png` (`AW2TEST_SHEET` copies it).
`aw2test/gauntlet.py` is the driver (`Gauntlet.start(co, colour=..)`, `open`, `pick_colour`, `shown` (what the step lists, from `gauntlet_ui::SHOWN`), `capture`, `win`, `lose`, `best`, `results`, `saved_record`); wins use the mission's own captures (Drake's HQ, Sensei's, Hawke's) and the game's rout.
