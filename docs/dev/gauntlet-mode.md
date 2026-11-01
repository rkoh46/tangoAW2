# The Gauntlet mode: plumbing (`crate::gauntlet`, `crate::mode_menu`)

Select Mode's **GAUNTLET** (with the Dual Strike pack, offline): pick one CO (any CO the game has, no partner), then fight a map's enemy COs one after another in a single battle (the gauntlet engine,
[gauntlet.md](gauntlet.md): hidden lines that arrive when the lines before them fall), AW2's results, back on Select Mode. The maps are the content (`crate::gauntlet_mode`: `def()` returns a
`CampaignDef` whose missions are the maps, `ROSTER` every CO, `SOURCE` 4; Cinder Sea is `gauntlet_01`); this page is how the mode is wired. Code: `gauntlet.rs`, `gauntlet_ui.rs` (the map selector and the colour pick), `mode_menu.rs`, `ds_campaign.rs`
(`start_gauntlet`, `gauntlet_start_script`, `gauntlet_end_script`, `after_map`, `end_of_battle`), `campaign_model.rs` (the source), tests `tools/aw2test/tests/test_gauntlet_mode.py`.

## The flow, screen by screen
1. **Select Mode.** GAUNTLET answers like Battle Maps and Link (A starts it, no Continue/New box). The wheel's mode store stores Campaign's New (1) and `gauntlet::picked` asks for this source
   (`ds_campaign::REQUEST`, `SOURCE` 4); a run saved halfway asks for Continue instead (hold SELECT with A to start a new run over it).
2. The game's own Campaign New handler (`0x0803BA4C`, trapped by `ds_campaign::start`) runs `start_gauntlet`: the record from Flash (kept), the session's flags and wins cleared (every run is a first
   play), `GAME_MODE` campaign, then the **start proc** (`gauntlet_start_script`, a proc of AW2's own script language; labels are found by scanning on and an END stops the scan, so the "round again"
   section is last): fade, then
   - **the map selector** (`gauntlet_ui.rs`, step 1): a screen of ours drawn over the finished picture (`ds_coselect::apply`, like the Teams cards: AW2's windows, font, portraits and emblems
     read from the ROM). It lists `gauntlet_mode::entries()` (one per mission of `def()`: title, enemy COs and colours read from the mission, so a new map lists itself), shows the highlighted map's
     picture, **the enemies you will face** in the order they come (each line's face, army emblem, number and name) and the best result (`gauntlet::best`: score, CO, days). UP/DOWN browse, A takes the
     map (`ds_campaign::choose_gauntlet_map`: the session's mission and its header in the battle's map-table entry), B goes back to Select Mode (`gauntlet::returning`: the wheel stays on GAUNTLET).
     The start proc waits on a flow function (`FLOW_PICK_UP`) that answers 1 while a step is up; `gauntlet_ui::tick` takes the pad meanwhile and says how the step ended (`ANSWER`).
   - **the CO pick:** the CO screen's lists (`FLOW_CO_SETUP`: **all 36 COs**, the roster's unlock bits are not used: `unlocked_cos`), AW2's CO screen (`0x086165C0`). B comes back to the selector
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
- **The record.** Each map's best result, AW2's layout (`CO | days << 8 | score << 20`, `ds_campaign::RECORDS` + 8 * mission), saved as this source's record in Flash **slot 13 at +0x240** (magic
  "AWGA", `campaign_model::Source::save_offset`): slot 13 holds BH (0..0x120) and BH2 (0x120..0x240) already; a record is written by replacing only its own region
  (`merge_record`), so a Gauntlet save leaves theirs byte for byte (test `gauntlet_mode_leaves_the_other_campaigns_saves_byte_identical`) and takes no sector of its own (3 x 0x120 bytes fit one
  sector's 0xFAE-byte payload; Rust test `the_gauntlet_record_sits_after_bh_and_bh2_in_slot_13_and_touches_neither`). `best_score` records a **win only** (AW2 calls it for a loss too, with the
  winner's score). The record is shown on the map selector (best score, CO, days); `Gauntlet.best()` and `saved_record()` read it in the tests.
- **Save in battle.** The map menu's Save works as in the BH campaigns: the shared mid-battle slot 12, the saved mission's top three bits name the source (`suspend::source_tag`: 4 << 5 = 0x80), the
  battle's block and the engine's tail (gauntlet state, stage mark) follow. `Continue` is picking GAUNTLET (`REQUEST` 2, `resume_mid`); a run's end drops the save. Test `gauntlet_mode_save_and_continue`.
- **Online.** Offline only: `mode_menu::tick` is called with `ds && ds_features && mode.is_none()` (as Survival's), the wheel is AW2's own six in a netplay room, and nothing of the battle's
  simulation is changed (no `SIM_VERSION` bump).

## Adding a map
A function in `gauntlet_mode.rs` added to `def()`'s missions (spec `five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`): the selector lists it, with its enemies, and the colour pick
offers what its enemies leave, from the mission alone. **The enemies' colours are the map's data**: each enemy `ArmyDef::new(colour::.., CoSpec::Fixed(co))` in `armies` (index 1 on, in the order they
come) is what the selector shows and what the player may not wear; `Entry::free` computes the offered colours (AW2's five minus those, then Silver Nova while one of the five is free to host it), so a
map that fixes other colours changes the offer with no other edit. The enemy armies need teams of their own (team 2: team 0 is "my own number" and 1 is the player's). A map with later stages lists their enemies too and keeps a plain colour out of the offer if any stage's enemy wears it ([gauntlet.md](gauntlet.md), "Colours and stages"); a five-army map has the player in army 5 (its pick is the CO screen's army-1 pick, army 1 a fixed enemy).

## Aids and tests
`aw2dev gauntlet start [--co N]` boots the harness into the mode with a picture of each screen (wheel, map selector, CO pick, colour pick, Setup, first turn); `aw2dev gauntlet test` runs `-k gauntlet_mode`.
`aw2test/gauntlet.py` is the driver (`Gauntlet.start(co, colour=..)`, `open`, `pick_colour`, `shown` (what the step lists, from `gauntlet_ui::SHOWN`), `capture`, `win`, `lose`, `best`, `saved_record`); wins use the mission's own captures (Drake's HQ, Sensei's, Hawke's) and the game's rout.
