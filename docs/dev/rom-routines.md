# ROM routines, procs, data tables and hooks (AW2 USA cartridge `AW2E`)

Every address below is a constant or a comment in the tree at branch `devkit` (file in the last column, under
`tango-gamesupport-aw2/src/` unless a path is given). **An address in a hook table is the trap/hook site the code uses; it is often inside a function (after its prologue, or at a return), not the function entry.** Where the code names the function, the decomp or `sub_` name is given. Names `sub_08xxxxxx` are the raw addresses of functions; names like `StartArmyTurn`
are the **aw2bhr decompilation's** names as quoted in the code comments. All code is **Thumb**: function pointers carry bit 0 (`0x080363D1` is
the function at `0x080363D0`). No ROM bytes are included here, only addresses and symbolic names. Dual Strike (NDS) addresses
(`0x02xx_xxxx` in `ds_*`, `co_*` files) are not GBA and are omitted. RAM is in `ram-map.md`.

## 1. How routines and procs are identified

1. **Procs.** AW2 runs gameplay as "procs" (coroutine-like records; pool `0x0200D610..0x0200E418`, `0x6C` bytes each; also IWRAM records from `0x03000C00`). A proc is named by its script pointer (data, `0x0840_0000..0x0870_0000`) and/or its Thumb callback. `fog_view::procs(core)` scans IWRAM `0x03000C00..+0x1300` and EWRAM `0x0200C000..+0x2000` for records of two ROM script pointers followed by a Thumb function and returns the function list (skipping event slots `0x0200C510..0x0200C528 + 10*0x18` and the background procs `0x08034F8D`, `0x08003891`). The callback is the "proc id" used throughout `fog_view.rs`. `result_view::procs` and `survival::running` instead scan the pool at `0x0200D610` for a script pointer (`PROCS`, `PROC_SIZE 0x6C`).
2. **Logging which procs are running.**
   - `AW2_PROC_LOG=1`: `fog_view::phase` prints `procs [...] moving B main loop XXXXXXXX menu N` whenever the set changes (map phase, waiting view).
   - `AW2_CONSOLE_PROCS=1`: `pvp.rs before_tick` logs `consoleprocs [...] loop .. menu .. chosen .. ended ..` for the real console whenever its proc set changes.
   - `AW2_BUSY_LOG=1`: `fog_view::log_busy` prints each distinct proc set that makes the phase Busy, once.
   - `TANGOAW2_INPUT_LOG=1`: `fog-phase: turn_ended .. menu_state .. procs ..`, `scene: loop .. attacker/defender record ..`, `input-drop:` lines (`online.rs`).
   - `AW2_TRAP_LOG=1`: `pvp.rs SharedGame::traps` adds logging traps on the candidate camera routines `0x08000E0A, 0x08024A42, 0x08028D52, 0x08037AA6, 0x0806A94A, 0x08029038` (prints scratch flag, r0..r3, lr).
   - `AW2_MENU_LOG` (menu navigation log) and `AW2_LEAK_CHECK=1` (every tick, no watching seat may show the console's picture) are read by the harness example `aw2_room_teams.rs`.
3. **Main loop callback** (`0x03000000`): `0x08022049` = the map is the only thing running; `0x08043591` = full-screen CO page; `0` = a screen between screens (wipes, battle scene, results).
4. **Finding a routine's callers/literals.** Patching modules locate the game's literal-pool words by a full ROM scan and list the pool addresses as constants (`ds_music.rs` `SONG_POOL` "a full scan finds these six", `five_map.rs` `LIST_IDS_LITERALS`, `roster.rs` `TABLE_POINTERS` (120 words), `survival.rs` `RECORD_POOLS`, `co_new.rs` `LIST_POOL`, `five/patches.txt` checked by `five/gen.py`). Probing aids: `tango-backend-mgba/examples/gba_probe.rs` (presses, screenshots, RAM dumps, pokes; `CONTRIBUTING.md`), `tools/aw2test/`, and the harness env vars in `architecture-online.md` section 15.

## 2. How hooks are made

- **Traps.** `SharedGame::traps() -> Vec<(addr, Box<dyn Fn(&mut Core)>)>` (`tango-backend-mgba/src/shared.rs`), installed once at boot with `set_traps` (also on a resumed console). A handler runs **before the instruction at `addr`**, with the CPU registers in hand (`core.gba_mut().cpu_mut()`: `gpr/set_gpr`, `set_thumb_pc`): it may change registers, write RAM, or redirect the PC. Must be a pure function of console state (rollback re-runs it). Aggregated in `factory.rs` `traps()`; test `trap_tests::no_two_traps_share_an_address` fails the build if two traps share an address (the second would silently replace the first). Traps also fire on a scratch console (`shared::in_scratch()`), so handlers that note state for tools must check it.
- **Call-and-return on the emulated CPU.** To call a game function from a hook: set r0/r1.., set `lr = RETURN | 1` where RETURN is **alignment padding that the game never executes** and which is itself trapped, then `set_thumb_pc(f)`; the trap at RETURN continues the program. Used by `fog_view` (`RETURN 0x08020EDA`, registers saved at EWRAM `0x0203DF00`, `call_program` for lists of calls, also used by `result_view`), `unranked.rs` (`PLAY_SOUND` returning to `LIST_FRAME`), `oozium.rs` (`EAT_NEXT 0x0802C8E2`), `unit_actions.rs` (`EXPLODE_DONE 0x0802D0B2`), `two_front.rs` (`AFTER_BACK 0x080743AA`), `tag_extras.rs` (`WAIT_QUOTE_DONE 0x08039928`), `power_anim.rs` (`DRAW_METEOR_END 0x0804498D`).
- **Dead-code landings.** `0x0803CC5E` (`campaign_model.rs LANDING`, "magic stub" id in r3, trapped by `ds_campaign`) and `0x0803CC5A` (`tag.rs LANDING`) are dead code in `sub_0803CC3C` used as jump targets for stubs written into free ROM.
- **ROM image patches.** The ROM image lives in memory, so modules write words/halfwords into it (`raw_write_*`): literal-pool pointers repointed to moved tables, hook halfwords (`five.rs` writes `TRAP = 0xBEEF` over each hook site and removes it again; its patch lists are `five_patches::{HALVES, WORDS, HOOKS}` (generated by `five/gen.py` from `five/patches.txt`); they are switched on only while a five-army map or the Design Room's editor is active, `five::patches_on`), and new code/data in free ROM (section 8). Patches that depend on the match must be keyed on console state (RAM), not on host files, or peers diverge (`ds_art::features`, `ds_pack::features` use the match's subtype bit).
- **Text ids beyond the table.** The text table at `0x08610A38 + 4*id` is read without a bound, so ids above AW2's read pointers from free ROM: `0x3D72 + k` -> `0x08620000 + 4k` (`five_map.rs`), new CO texts from `0x6D72` -> `0x0862C000`, Survival `0x7172` -> `0x0862D000`, DS Campaign `0x7400..0x7FFF` -> `0x0862DA38..0x08630A37`, DS Versus `0x7200..0x72FF` -> `0x0862D238`, two-front `0x7FFD/0x7FFE`, setup phase `0x7FFC` (`docs/AW2.md` "Free ROM used"; `online_menu.rs`, `roster.rs`, `survival.rs`).

## 3. Procs (callbacks/scripts) the waiting view and result view key on

| Address | Name / meaning | Source |
|---|---|---|
| `0x080363D1` | **Unit walk proc** (`WALK_PROC`): a selected unit walking to its chosen cell. Alone in the proc list = shown to every window; it stays under the command menu. Pixel x/y at proc `+0x3E/+0x40` | `fog_view.rs` `walking`, `walker_pixels` |
| `0x080228D9` | Unit/cell selection (`UI_PROCS`) | `fog_view.rs` |
| `0x08035E25` | Command (unit action) menu | `fog_view.rs` |
| `0x08019D0D`, `0x08019DED` | Menus' frame/items procs | `fog_view.rs` (also: absent test for "power chosen") |
| `0x0802DA19`, `0x0803A441` | Build menu | `fog_view.rs` |
| `0x08046D31`, `0x08047079` | Terrain info page (R on the map) | `fog_view.rs` |
| `0x0803A69D`, `0x0803A5B9` | Unit info page | `fog_view.rs` |
| `0x08014401`, `0x080195F9` | Text box proc / Save question proc | `fog_view.rs` (`0x080195F9` marks the Save question) |
| `0x0802C391`, `0x0802C3D1`, `0x080375D5` | Map overview (START) | `fog_view.rs` |
| `0x080466DD` | Intel table | `fog_view.rs` |
| `0x08013FF1` | **Dialogue/narration message box over the map** ("The Green Earth Army has lost!"). Shown to every window as narration; if a map-menu item 0..5 is chosen (Yield, Save, End turn, Power) it is the mover's question and is never shown | `fog_view.rs` `DIALOG_PROC`, `dialog_for` |
| `0x08040C89`, `0x08040AFD` | Capture card (shown to seats that see the cell) | `fog_view.rs` `CAPTURE_PROCS` |
| `0x0802A509`, `0x08027DD9`, `0x08027905`, `0x0802788D`, `0x08029FE5`, `0x0802A3FD` | Animation procs of the turn (walking, capturing, build, attack result): `ANIMATION_PROCS` | `fog_view.rs` |
| `0x080111AD`, `0x0802C451` | Wipe/fade procs of pages (CO page, overview): never shown (`WIPE_PROCS`) | `fog_view.rs` |
| `0x080501DD` | Battle scene procs (many, main loop callback `0`): `SCENE_PROC` -> `Phase::Scene` | `fog_view.rs` |
| `0x0806D000..0x0806E000`, `0x08065961` | Rules page and its wipes (`rules_proc`) | `fog_view.rs` |
| `0x08064E5D` | Versus Teams screen **task** (in the task table `0x03001500..0x03001A00` only while it is up) | `pvp.rs` `TEAMS_TASK` |
| `0x08022049` / `0x08022048` | Map main-loop callback; `onyx.rs MAP_FRAME` traps `0x08022048` to run its real-time list each frame | `fog_view.rs`, `onyx.rs` |
| `0x08043591` | CO page main loop | `pvp.rs`, `fog_view.rs` |
| `0x08037F80` -> `0x08037FD0` | Match-end proc (script `0x0849D56C`): checks alive armies, starts `0x08037FB4` (DEFEAT) or `0x08037F94` (`StartVictory`) | `result_view.rs` doc, `docs/AW2.md` |
| `0x08615CB0..0x08615E08` | VICTORY! script and children (banner, quote). `0x08615CC8` = its first wait (`MASTER_WAIT`, `result_view::marked`); `0x08615E08` fades it out; `0x08615FB4` WIN!/LOSE page | `result_view.rs` |
| `0x08049F08` | `StartDefeat(army, parent)` | `result_view.rs` |
| `0x0801C9EC` | `EndProc(proc)` | `result_view.rs` |
| `0x0801237C`, `0x08012358` | Screen-register clears made before VICTORY!/DEFEAT | `result_view.rs` |
| `0x0801C8F4` | `Proc_Start` | `tag_extras.rs` |
| `0x0801CBC8` | `Proc_Goto(proc, label)` | `ds_campaign.rs` |
| `0x08078540` | `StartBlockingEventScript(script, proc)` | `ds_campaign.rs` |

Proc scripts (data) that mark screens:

| Address | Meaning | Source |
|---|---|---|
| `0x08581CF8` | `ProcScr_TitleScreen` ("PRESS START!") | `branding.rs` |
| `0x0849E818` | `ProcScr_MainMenu` (Select Mode) | `branding.rs`, `campaign_menu.rs` |
| `0x08616990` | `ProcScr_MainMenuC1`, the wheel's proc (running while Select Mode is up); wheel scripts `0x08616A08`, `0x08616A40`; input loop `MainMenuCarouselWheel_InputLoop` `0x08081D30`/`0x08081D31`; wheel labels `0x08616AC0` | `survival.rs`, `campaign_menu.rs`, `mode_menu.rs` |
| `0x08616C54` | Versus/War Room SELECT MAP proc (`PreviewMap`; idle callback `0x08085F91` for Survival) | `ds_versus.rs`, `survival.rs`, `survival_ui.rs` |
| `0x08616CF4` | The SELECT MAP list proc online.rs reads (`LIST_PROC`; cursor row at `+0x58`) | `online.rs` |
| `0x086165C0`, `0x08616638` | CO select screen scripts (`WarRoomMapSelected`, `ProcScr_CoSelect`) | `ds_campaign.rs` |
| `0x08616BE4` | CO page proc (army at `+0x66`) | `ds_co_page.rs` |
| `0x0849BC50` | The link-cable (ONLINE) screen's menu proc (cursor at `+0x36`: 0 Single-Pak, 1 Multi-Pak, 2 Trade Maps; relabelled UNRANKED / LOBBY / STATS) | `online_menu.rs`, `docs/AW2.md` |
| `0x0861485C` | World map script entered from the menu; `0x0849EB7C` the campaign proc that opens it; `0x08614614` its main loop | `ds_campaign.rs` |
| `0x0849FEF8` | Battle scene proc script | `ds_battle.rs` |
| `0x0849FE78`, `0x0849FB04`, `0x0849FADC` | Structure hit scripts | `factory_hp.rs` |
| `0x084A0858` | Meteor strike script (Sturm's), 15 commands, 4th picks the target (`sub_080448E4`) | `onyx.rs` |
| `0x0858096C` | A Rules-row object's script | `versus_rules.rs` |

## 4. Menus, screens, messages

| Address | Name | Meaning | Source |
|---|---|---|---|
| `0x0849AAC0` | map menu table (CO, Intel, Power, Super, Options, Save, End); `0x0802D49C` = `OpenMapMenu`'s literal-pool word naming it; `0x0802D484` its `CreateRootMenuWithSfx(table, x, y, 1)` call | `two_front.rs MAP_MENU`, `tag.rs MENU_POOL`, `ds_menus.rs`, `tag.rs MENU_Y` |
| `0x0849ABC0` | Intel menu table (Status, Terms, Unit, Rules); opener `0x0802D504` | `two_front.rs INTEL_MENU` |
| `0x0849AE28` | Unit command menu table (13 commands, a flag byte each) | `unit_actions.rs LAUNCH_HIDE` |
| `0x0849AB64` | Map menu Save item entry (hide test `0x0802C644`/`0x0802C646` `savingEnabled`) | `ds_campaign.rs`, `survival.rs` |
| `0x0802CEFC` | `MapMenu_SuperPower` | `tag.rs` |
| `0x0802D158` | Supply command on-select (`SUPPLY_SELECTED`) | `unit_actions.rs` |
| `0x0802CFFC` / `0x0802C8BC` | Wait on-select / Wait show test | `oozium.rs`, `two_front.rs` |
| `0x0802CC98` | `CanShowSubMenuItem` (Dive) | `unit_actions.rs` |
| `0x0802E4B4` | `HandleMapCursorA(x, y)` and the map menu's opening | `setup_phase.rs` |
| `0x08027654` | per-frame cursor routine (keeps CO panel state at `0x03003130`) | `fog_view.rs` doc |
| `0x08019C40` / `0x0801A444` / `0x0801A0C6` | menu items draw / frame draw / calls skipped while a menu is Dual Strike's | `ds_menus.rs` |
| `0x080436DC` | `DrawArmyCoPanel(x, y, army)` | `tag.rs DRAW_PANEL` |
| `0x0801A548`, `0x0801A57C` | CO panel load, army's grey unit palette load at turn start (BG 9 for five armies) | `fog_view.rs CALLS`, `docs/AW2.md` |
| `0x08043834` | CO panel header with the funds | `fog_view.rs CALLS`, `pvp.rs` |
| `0x08066D74`/`0x08066D7E` | `MatchSetupHandleRulesStageInput` (Rules stage input, every frame) | `versus_rules.rs` |
| `0x08066B8C`, `0x08066D6A`, `0x08066F8A` | `RuleOption_DrawArrows`, rule highlight end, `MatchSetupShowHelpText` | `versus_rules.rs` |
| `0x08064739, 0x08064775, 0x080647BD, 0x0806486D, 0x08064919, 0x080649D1` | Rules-row item functions (`ITEM_FNS`; value at item `+0x48`, fn at `+0x4C`); `sub_08064774` draws the Weather row's word (site `0x080647A6`) | `unranked.rs`, `sandstorm.rs` |
| `0x0803C1D4`/`0x0803C26A`, `0x0803BFBC`/`0x0803C034` | Rules -> gPlaySt / gPlaySt -> Rules copies | `sandstorm.rs` |
| `0x0803BCD0` | `SetMapId(map)` (map picked from the list: starts/ends a five-army game; two-front setup) | `five.rs MAP_PICKED`, `ds_versus.rs SET_MAP_ID` |
| `0x08037448` | Versus list builder (sorts by header tab `+0x1A`; stops at 50 maps unless patched, `LIST_BUILDER_STOP 0x080374AA`); `0x080375A4` `BuildMapListForMode` | `docs/AW2.md`, `five_map.rs`, `ds_versus.rs` |
| `0x0803CA54` | list's "may this map be shown" test | `five_map.rs` |
| `0x08086A58` / `0x08086A6E` | `DrawMapList(first, count, top)` / site past its `ClearBg0Tilemap` | `survival.rs`, `ds_versus.rs` |
| `0x0808606C`/`0x08086070` | SELECT MAP list proc's per-frame function (`push {r4, lr}; adds r4, r0, #0`; r0..r3 free after) | `unranked.rs LIST_FRAME` |
| `0x08084C90`, `0x080852A8` | CO page input / page draw (`[0x03005940]`) | `tag_extras.rs` |
| `0x0807F57C` | War Room/Survival CO screen builder (country groups table `0x086166F0`, pool word `0x0807F608`) | `docs/AW2.md`, `co_new.rs` |
| `0x0803CAB8` | `sub_0803CAB8(co)` CO unlocked | `co_new.rs` |
| `0x08033AE4` | pointer to the link screen's label sheet (`0x081D8A54`) | `online_art.rs` |
| `0x08610A38` | **Text table**: pointer per text id. Known ids: `0x9C2/0x9C3` campaign help, `0x9CE` LINK help ("Play online with friends."), `0x9DC` "Choose a CO.", `0x9DD`, `0xCBE..0xCC0` online help lines | `online_menu.rs`, `five.rs`, `campaign_menu.rs` |
| `0x084C32E4` / `0x084C36E4` | Proportional font: glyph pointers (16 rows of 4-bit pixels) / widths | `online.rs`, `two_front.rs` |
| `0x08616194` | Title font table (12-byte entries: char, glyph data, width) ; `0x081CC038` title font glyph data | `title_card.rs`, `online_art.rs` |

## 5. Gameplay functions the code hooks (decomp names where quoted)

| Address | Name / what | Source |
|---|---|---|
| `0x080258CC` | **Map refresh**: vision planes of every army, then terrain and unit layers redrawn (waiting view for fog) | `fog_view.rs REFRESH` |
| `0x08020984` | picks which armies' vision the next refresh builds (viewers from current army and controller) | `fog_view.rs CALLS` |
| `0x08020EDA` | alignment padding; the fog view's return trap | `fog_view.rs RETURN` |
| `0x080267AC`, `0x08026810` | `StartArmyTurn`; start of turn just after the per-player turn-start call returns (`TURN_START`) | `tag.rs`, `factory.rs` |
| `0x08034F7C`/`0x08034F8C` | map busy counter inc/dec | `onyx.rs MAP_BUSY` doc |
| `0x08034AF8` / `0x08034DCC` / `0x08034EF0` | `MapState_TurnHandoverPrompt` (state 3) / `MapState_TurnStart` (5) / `MapState_EndOfGame` (0x12) | `two_front.rs`, `setup_phase.rs` |
| `0x0803832C` | `EndOfGame_Finish` | `survival.rs` |
| `0x08038488` | `EndOfGame_FinishCampaignMap` | `ds_campaign.rs` |
| `0x08028894` (and `0x08028874`) | `DefeatArmy(army, code)`: HQ code 2, no units 1 / 0x10; `0x08028AEC` is the rules check that calls `0x08028874(army, 8)` for yielded armies | `history.rs`, `proxy_seat.rs` |
| `0x08042650` / `0x0804281E` / `0x08042822` | `ApplyCaptureProgress`; capture completes (previous owner `killOnEndTurn`); HQ branch | `history.rs`, `com_tower.rs` |
| `0x08025CC8` | `CreateUnitAt(x, y, type)` | `custom_campaign.rs`, `ds_campaign_rules.rs` |
| `0x08025E52` | `BuyUnit` past its checks | `history.rs` |
| `0x08026F18`, `0x08026C6C` | `AddPlayerIncomeToFunds`; per-kind daily income | `co_powers.rs`, `com_tower.rs` |
| `0x08029AF8`, `0x08029978`, `0x08029A48` | `RepairUnit(unit, hp, pay)`; ammo to full; fuel to full | `co_powers.rs`, `crumb.rs` |
| `0x080253B0` / `0x08025434` / `0x08025B80` | daily fuel burn / fuel in r5 / `SubtractFuel` | `ds_weather.rs` |
| `0x080251BC`, `0x08024ABC`, `0x08024C58`, `0x08024DDC` | battle work-out; `CalcDamage`; defence store; apply a hit | `co_powers.rs`, `co_roster.rs` |
| `0x08024DDE` | `sub_08024DDC(target, attacker)` just after its push: a strike's damage applied; Testudo cuts the counterattack's `+0x0C`/`+0x14` to 75% | `es_co.rs` |
| `0x08042532` | `sub_080424FC` (the selected unit's action ends) at the `orrs` that sets done (r1 = 1; the return address at `[sp + 4]`): Triumph leaves a vehicle not done after a battle (return addresses `0x08041A01`, `0x08041E05`, `0x08041E55`, `0x08040977`) | `es_co.rs` |
| `0x0802CA78`, `0x0802CB20` | the command menu's two Fire rows' show tests (r0 = 1 hides): hidden for a unit that has used Triumph's extra move | `es_co.rs` |
| `0x08043070`, `0x080433F8` | CO-scaled damage chart read / raw chart read | `roster.rs` |
| `0x08042CF8`, `0x08042D42`, `0x08042DA6`, `0x08042D76`, `0x08042CC0`, `0x08042E64`, `0x08043050` | Trap sites in `GetUnitDefenceWithCoBonus` (entry), `GetUnitMovementWithCoBonus` (at its return), `GetUnitVisionWithCoBonus` (after the CO's vision is added), `GetUnitFiringRangeWithCoBonus` (max range in r4), `GetCoPriceMultiplier`, `GetPlayerCoLuckBonus` (entry/return), `GetPlayerSpecialAbilities` (entry/return) | `co_skills.rs`, `co_roster.rs`, `sandstorm.rs` |
| `0x08044B28` | `ActivateCoPower(army, mode, proc)` | `co_powers.rs`, `online_stats.rs` |
| `0x0804438C` | `PayForPower(army, mode)` entry (starts the quote `sub_08039634`) | `crumb.rs` |
| `0x080440E0` | power-meter charge `(army, amount)` | `co_skills.rs` |
| `0x08044854`, `0x080448E4`, `0x08044968`, `0x08044F24` | strike square hit; strike pick step; strike draw (meteor); mass damage per unit | `co_powers.rs`, `power_anim.rs` |
| `0x08043DAC`, `0x08043DF4`, `0x08043E18`, `0x08044BA0` | power music picks (AW2 songs `0x1A3/0x1A4/0x199/0x19A`) | `power_music.rs` |
| `0x08035144` | power weather (`sub_08035144(weather)`) | `ds_weather.rs` |
| `0x08035020` / `0x080351F0` / `0x08035170` / `0x08035490` | map colours for weather / turn weather compare / next-turn weather draw / `CalcRandomWeatherChances` | `sandstorm.rs` |
| `0x0803550C` | the frame's effects pass (weather in r0; `EFFECTS 0x08035514`) | `cpu_tactics.rs`, `sandstorm.rs` |
| `0x0801F4B4`, `0x0801F6F0`, `0x0802E724`, `0x0802E7C8` | flood-fill start / step; may a unit end on (x, y); move walk trap check | `oozium.rs` |
| `0x080202A4`, `0x08058224` | move range flood / CPU usable movement | `ds_weather.rs` |
| `0x0801F91E` | `CacheUnitMovementCosts` done (costs at `*0x084999C8`) | `co_skills.rs` |
| `0x08016D30` / `0x08016D88` / `0x08016DB8` / `0x08016DCC` / `0x08016DD0` / `0x08016F38` / `0x08017208` / `0x08017688` | Save (`SaveGame` path) / after capture / Continue / after slot read / after apply / `CaptureBattleSaveState` / apply / resume | `suspend.rs`, `five.rs RESUME 0x08017658` |
| `0x08016C70` / `0x08016B2C` / `0x08016BA0` / `0x08016C9C` | `SaveGame(kind)` (2 = campaign); profile serializer; site at its end; `sub_08016C9C(kind)` suspend-mark function (2 campaign, 3 War Room) | `ds_campaign.rs`, `ds_worldmap.rs`, `suspend.rs` |
| `0x0801A7D8`, `0x0801ABF8`, `0x0801B2FC`, `0x0801B09C` | flash slot writer; slot delete; sector directory; sector check | `docs/AW2.md` Saves, `ds_campaign.rs` |
| `0x08017720`, `0x0801774A`, `0x080176A8` | `InsertBestScoreRecord` (+ War Room branch), `IncrementDayCount` | `ds_campaign.rs`, `history.rs` |
| `0x0805D438` (`0x0805D4A6`, `0x0805D496`) | CPU per-unit turn function and its sites | `custom_campaign.rs`, `unit_actions.rs` |
| `0x080606D0`, `0x080610D0`, `0x080607E8`, `0x08060856`, `0x08061178`, `0x080611D8` | CPU production: build driver, buy, spawner, create call, role roll, factory pick | `ds_ai_build.rs`, `factory.rs`, `bh_factory.rs` |
| `0x08061788`, `0x0806184E`, `0x08061AC4`, `0x08061ACE`, `0x08061900` | CPU record copy for its turn; copied; CPU turn-end step; `EndCurrentArmyTurn` call; `AiBeginTurn` Black Factory call | `unit_actions.rs`, `map_anim.rs`, `tag.rs` |
| `0x0805DB70`, `0x0805DBCC`, `0x0805F4CC`, `0x0805ED2A` | `AiDeliberateCoPower` and its Super payment; role move; goal find | `tag.rs`, `ally_posture.rs`, `cpu_inventions.rs` |
| `0x0803DE94` | `GetInventionAt(x, y)` | `ds_campaign_rules.rs` |
| `0x0803FD80` | structure graphics loader (`LoadInventionGraphics`) | `volcano.rs`, `factory_hp.rs` |
| `0x08042634` | "attack the structure at (x, y)" (pipe seam) | `factory_hp.rs` |
| `0x08040818`, `0x0804026C`, `0x0803FD54` | structure hit/destroy branch; cannon destroyed; factory sprite call | `factory_hp.rs` |
| `0x0804001E`, `0x080401BC` | explosion proc; a unit's destruction | `map_anim.rs` |
| `0x0803ED60`, `0x0803EE9C`, `0x0803ECE8`/`0x0803ED12` | turn-start structure firing loop; per entry; a structure shot hits a unit | `obelisk.rs`, `co_skills.rs` |
| `0x0803E764` | Volcano eruption (`ERUPTION_CALL 0x0803EE3C`) | `ds_campaign_rules.rs` |
| `0x0804B744`, `0x0804B7B8`, `0x0804B850` | battle backgrounds pick / layers / load | `ds_backdrop.rs` |
| `0x08041978`, `0x08041CF4`, `0x08041CCA` | battle chosen (scene or map-only by the Visuals option in r2) / rows filled / defender charged | `ds_battle.rs`, `co_powers.rs` |
| `0x08057164`, `0x08057BDC`, `0x08054500` | figure records; HP drain; direct shot figure hit | `ds_battle.rs` |
| `0x0803D238`, `0x0803D28C`, `0x0803CFA4`, `0x0803CF54`, `0x0803D2F8` | design-map loader / save / record | `design5.rs`, `wasteland.rs` |
| `0x0803B83C` | Select Mode start | `ds_campaign.rs` |
| `0x0803BA4C`, `0x0803B904`, `0x0803BA00`, `0x0803BC7C` | Campaign New/Continue handlers; Survival's Continue (`MainMenuWarRoom_Continue`); `StartWarRoom`; `GetCampaignSaveFlag` | `ds_campaign.rs`, `suspend.rs`, `campaign_menu.rs` |
| `0x08081498`, `0x08081E94`, `0x08081EEE`, `0x08081EF6` | wheel: item 8 answers as Link; mode store `0x030033FC` | `mode_menu.rs` |
| `0x0803CBA0` | AW2 campaign flag set/test (`SET_FLAG`) | `ds_campaign.rs` |
| `0x08074484` | `RunEventList(list, unit, arg)` (`StartEventScript` `0x08019348`; `0x08019260` scripts ended) | `onyx.rs`, `two_front.rs` |
| `0x080743E8`, `0x08074384`, `0x080743AA` | `RunMapEventsAfterUnitAction`; `UnitSelectedEvent_Init`; return trap padding | `two_front.rs` |
| `0x08018FB4` | `EventOp_DefeatOtherTeamsAndEndMatch` (script op 0x40) | `ds_campaign.rs` |

## 6. Sound

Calls: `sub_0803B4DC(song)` = **sound effect** call (keeps the game's sound setting; `0x0803B4DD` = same with Thumb bit, `heal_effect.rs PLAY_SE`); `sub_0803B4EC(song)` = **music** call (a song already playing goes on); `PlayMusicOrSfx2` is the decomp name of the SE path in `versus_rules.rs`. To play one from a hook: `r0 = id`, `lr = returnpoint|1`, `set_thumb_pc(0x0803B4DC)` (`unranked.rs play_requested`, `power_anim.rs draw_meteor`, `versus_rules.rs rules_sound`, `tag_extras.rs`).

| Id | Meaning | Source |
|---|---|---|
| `0x64` | cursor tick on the Rules screen (`PlayMusicOrSfx2(0x64)`); also the sound asked for before `MatchSetupHandleRulesStageInput` body | `versus_rules.rs CURSOR_SOUND` |
| `0x67` | SELECT MAP list tick (the cursor plays it by moving; the roulette's cycling steps) | `unranked.rs` comment at `SE_REVEAL` |
| `0x75` | "CO power meter charged" arpeggio (two tracks); the roulette's reveal chime `SE_REVEAL` | `unranked.rs` |
| `0xC5` | meteor strike sound (Ex Machina / Covering Fire / Onyx laser, played after `sub_08044968`) | `power_anim.rs METEOR_SOUND` |
| song `0x1A3`/`0x1A4` | AW2 CO Power music (Black Hole's via `sub_08044BA0` / the other COs) | `power_music.rs` |
| song `0x199`/`0x19A` | AW2 Super CO Power music | `power_music.rs` |
| song 304 / 416 | staff roll music op `0x1B` / the roll's setup song (`0x0806BC84` replaced in a session) | `ds_credits.rs` |
| song 457 | a cannon's shot, played on player 2 (priority 10) by the turn-start invention loop; heal sounds use the same path (Dual Strike SE 175 Crystal / 176 Obelisk mapped in `ds_music.rs`) | `ds_music.rs SE_PLAYER`, `heal_effect.rs` |
| tag SEs | Dual Strike ids `[234, 235, 236, 187, 189, 81]` (thunder, meter up, count, letter, burst, CO SWAP) mapped to AW2 sounds | `ds_music.rs tag_se_ids` |
| `SongTable` | `0x0824238C`: 505 entries of (header, player, player); the six pool words that name it: `0x080704A0, 0x080704D4, 0x08070520, 0x08070574, 0x080705A8, 0x08072B9C`; `SoundInfo` at `0x03007FF0` (`+6` channels mixed, `+0x50` 12 channels x 0x40; AW2 mixes 8) | `ds_music.rs` |
| range | Converted Dual Strike music is appended past the 8 MB image from `0x08800000` and `0x09000000..0x09BFFFFF` | `ds_music.rs`, `docs/AW2.md` |

AW2 sound ids not listed here have not been catalogued in the code; to find one, trap `0x0803B4DC` and log r0 (pattern in `AW2_TRAP_LOG`).

## 7. ROM data tables

| Address | Table | Source |
|---|---|---|
| `0x085D5ABC` | Unit table: 25 records of `0x5C` (tangoAW2's copy in free ROM has 28; fuel at `+0x10`, vision/others per `roster.rs`); 120 ROM words point at it (`TABLE_POINTERS`). `0x08499594` is the word naming gUnits (RAM) | `roster.rs`, `ds_campaign_rules.rs`, `fog_view.rs` |
| `0x085D511C` | Movement charts (7 variants x 7 rows; two rows added for pipes and Oozium) | `roster.rs` |
| `0x085C77A0` | Map table: `0xC0` entries of `0x5C` bytes; header `+0x18` army count, `+0x1A` list tab, `+0x3C`/`+0x40` pointers. Moved by `five_map` to `0x08650000` with room for more ids | `five_map.rs`, `online_maps.rs` |
| `0x080C1BC4` | Tile id -> class byte (class low 5 bits, owner `<<5`) | `design.rs`, `online_maps.rs` |
| `0x08499598` / `0x08499594` | Words: gPlayers pointer (moved to `0x02030000` for 5 armies) / gUnits pointer | `five.rs`, `unit_actions.rs` |
| `0x084995FE`, `0x08499608`, `0x084999C8` | army-base table (five-army ids); unit sprite slot table `u16[5][25]`; movement-cost pointer | `docs/AW2.md`, `roster.rs`, `co_skills.rs` |
| `0x08580934` | Teams record pointer (moved to `0x02030300` for five armies) | `docs/AW2.md` |
| `0x085766E0` | CPU record (`+4 + 12*type` behaviour rows) | `unit_actions.rs` |
| `0x0810E6E0` | Palettes: buildings by colour (1..5), Black Hole units, moved greys `(colour+4)*32` | `pvp.rs`, `five.rs` |
| `0x080D3F04`, `0x080D3E84` | Unit palettes per colour 1..4 / Black Hole | `pvp.rs` |
| `0x080D4188`, `0x08104264` | CO panel palettes by colour (`0x08104264` = army colours for panel palette 7 each turn) | `pvp.rs`, `ds_hud.rs` |
| `0x080A1238` | Turn banner colours (by colour; AW2 has none for Black Hole) | `five.rs` |
| `0x0848B780`, `0x0848B738` | Sprite sizes (4 bytes/id) and sprite graphic rows | `pvp.rs` |
| `0x0849A2C8` | Terrain-name palette entries | `design_bar.rs` |
| `0x084A06F0` | Power effect table (pictures LZ77 + palette per unit effect) | `co_new.rs` |
| `0x08555850`, `0x085521DC` | Battle background table (0x18 each, `+2` layer type); figures by HP `[2][11][5]` | `ds_backdrop.rs`, `ds_battle.rs` |
| `0x0849E398` | Information screen rows (16 text ids per unit); `0x081BA068` rows, `0x081BA054` build menu order | `roster.rs` |
| `0x086166F0` | War Room CO groups table | `docs/AW2.md` |
| `0x0849F728` | Volcano eruption cells `[0x0849F728 + 4*(day&1)]` | `ds_campaign_rules.rs` |
| `0x08499CE4` | Map list tab titles (text id per tab) | `five_map.rs` |
| `0x08616FB4` | Select Mode item options lines | `mode_menu.rs` |

## 8. Free ROM claimed by tangoAW2 (in-memory image; mGBA grows the image past 8 MB when written)

| Range | Owner | Source |
|---|---|---|
| `0x08620000..0x086204FF` | text pointers for ids `0x3D72+k`: roster slots 32..56, five_map's slots from `0x08620100` (`TAB_TEXT = 0x3D72 + 64`) | `five_map.rs`, `roster.rs` |
| `0x08620500..` | the roster's strings; five_map's strings are at `0x08622000` (73 x 0x20) | `roster.rs`, `five_map.rs` |
| `0x08618000..` | five-army tables (`ROM_DATA`) | `five.rs` |
| `0x08650000..0x08655FFF` | the moved map table (0x100 ids x 0x5C) | `five_map.rs` |
| `0x09D00000..0x09D3FFFF` | tangoAW2's map data, 4 KiB per map, room for 64 (`MAP_CAPACITY`) | `five_map.rs` |
| `0x0862C000..`, `0x0862D000..`, `0x0862DA38..0x08630A37` | text ids: new COs (`0x6D72+`), Survival (`0x7172+`), DS Campaign (`0x7400..0x7FFF`) | `docs/AW2.md` |
| `0x08640000..0x08672FFF` | obelisk (`0x08640000`; wreck def `0x08648000`), sandstorm (`0x08670000`), wasteland names (`0x08671000`), Com Towers (`0x08672000`) | `obelisk.rs`, `sandstorm.rs`, `wasteland.rs`, `com_tower.rs` |
| `0x08660000` | design-map owner table | `design5.rs` |
| `0x08680000..0x08691FFF` | units (`roster.rs DATA`) | `roster.rs` |
| `0x086A0000..0x086AFFFF` | CO table (96 rows; `ROOM rows: to +0x6180`) | `co_roster.rs` |
| `0x08740000..0x0877FFFF` | CO pictures/texts/powers' code/heal wait (`co_new 0x08740000`, `co_powers 0x08749600`, `heal_effect 0x08749A00`, `crumb 0x08749C00`) | respective files |
| `0x08780000..0x0878FFFF`; `0x08790000..0x087A042F` | tag map menu, stubs, strings, Rules help lines; what the tag screens cover | `tag.rs`, `tag_screens.rs` |
| `0x087C0000..0x087C0FFF`, `0x087C1000..0x087C3FFF` | power animations, map animations | `power_anim.rs`, `map_anim.rs` |
| `0x087D0000..0x087DFFFF` | unit pictures | `ds_unit_pictures.rs` |
| `0x087F0000..0x087F4FFF` | CO screen grid | `co_grid.rs` |
| `0x08800000..0x08DFFFFF` | music (past the 8 MB cartridge) | `ds_music.rs` |
| `0x08E00000..0x08E4FFFF` | Survival (map table copy for `0x100` ids, `0x08E08000` maps), wheel data (`0x08E40000`) | `survival.rs`, `mode_menu.rs` |
| `0x08E50000..0x08E5FFFF` | online menu data (texts `0x08E50000`, wheel labels `0x08E50400`, `0x08E50E00`, sheet `0x08E51400`) | `online_menu.rs` |
| `0x08E70000..0x08E73FFF`, `0x08E74000..0x08E743FF`, `0x08E75000..0x08E753FF` | two fronts, setup phase, Black Onyx | `two_front.rs`, `setup_phase.rs`, `onyx.rs` |
| `0x08E80000..0x08EFFFFF` | Dual Strike looks (0x20000 each) | `docs/AW2.md` |
| `0x08EF0000..` | what the Set Skills panel covers while it shows | `docs/AW2.md` (CO skills) |
| `0x08F00000..0x08FFFFFF` | DS Campaign data (~360 KB) | `docs/AW2.md` |
| `0x09000000..0x09BFFFFF`, `0x09C00000..0x09CFFFFF`, `0x09E00000` | DS story songs/power themes, then the Emerald Sun themes (voice groups, tracks, headers: about 30 KB, after the power themes; their song-table rows are the table's last five); DS Versus and War Room maps; DS Normal look | `ds_music.rs`, `es_music.rs`, `ds_versus.rs`, `docs/AW2.md` |

## 9. Notes for new work

- Never trap two routines at one address; `factory::traps()` is the one place that lists every module's traps (add `traps.extend(crate::your_module::traps())`).
- Anything a hook writes is console state: keep it in EWRAM (registered in `ram_map.rs`), and bump `sim_version` (`pvp.rs`) because peers must patch alike.
- The scratch console runs `before_tick` (and its traps) too; guard host-side effects with `tango_backend_mgba::shared::in_scratch()`.
- For a new waiting-view rule, find the proc with `AW2_PROC_LOG=1` on a harness script (`aw2_room_teams ... script`), then add it to `UI_PROCS` (mover's own UI, closed with B on the scratch), `ANIMATION_PROCS` (turn animations, shown when no fog) or the narration/capture lists in `fog_view.rs`; anything unlisted falls to `Phase::Moving` (the window holds its last clean picture), which is the safe default.

## Army skins (docs/dev/army-packs.md)

| Address | What | Used by |
|---|---|---|
| `0x080261A4` (trap at `0x080261A6`, load at `0x080261BA`) | `sub_080261A4(army, type)`: a map unit's sprite slot by the country of the army's CO (`sub_08042DE0`); the skin's Infantry and Mech take their own slot | `army_skin::unit_slot` |
| `0x08035B3C` (trap `0x08035B40`, load `0x08035B5C`) | `sub_08035B3C(unit)`: the moving unit's sheet by (type, country) from the table `0x0849CD88` (9 words a type: five countries' sheets, the animation, 3 words) | `army_skin::moving_sheet` |
| `0x0803F5E4` (trap at its end `0x0803F698`) | `sub_0803F5E4(weather, base)`: loads the building sheet and each army's HQ art (by country) into OBJ VRAM at tiles `base + 0x5C + 8 (army - 1)` | `army_skin::hq_loaded` |
| `0x080135F4`, `0x08013618` | palette loaders (r0 source, r1 byte offset in the palette buffer `0x030020C0`, r2 size); `0x080135A4` copies the buffer to palette RAM | `AW2_PAL_LOG=1` logs the loaders' calls (`army_skin::traps`) |
| `0x0802BA9C`, `0x0800289C` | the unit panel's and the unit bar's copy of a unit's four tiles from the sheet (r0 the source) | `roster::panel_icon` -> `army_skin::icon_source` |
| `0x08610A38` | text table (word per id); army names 2269.. (by colour), "The ... Army has lost!" 3221.., lists 3288 and 3311 (order OS, BM, YC, GE, BH) | `army_skin::text_plan` |
| `0x0816D498` | battle gauge palettes by colour; `0x08183C28` HUD panel BG 8; `0x085A9BBC`, `0x085AC8BC` BG 9 / BG 8 tables; `0x080D3E04` the second building set; `0x084F2BC8` (2 rows a colour) the battle scenes' unit palettes, Black Hole's `0x085765A0`, `0x085766A0` | `army_skin::TABLES` |

Traps run **after** the displaced instruction (`mgba-rs` trapper) and panic on a second trap at one address; the registers an instruction would have written are not reliably visible to the handler, so read the arguments the function was called with (r0, r1) and set what the function's next instruction needs.

## Battle-scene figures and portraits (`army_skin.rs`)

| Address | What |
|---|---|
| `0x0805_68E2` | the scene's figure loader, just before it decompresses a side's sheet to the staging buffer (`0x0200FC50` left, `0x02013050` right): `r0` the LZ77 sheet, `sp + 0x20` the side; trap `fig_sheet` |
| `0x085D_64A8` | the figure records `[5 * type + country]` (15 words each: words 0..3 the first sheet, 4..5 the second, then descriptors): Infantry and Mech both use type 1; a sheet is 14 or 16 frames of 512 bytes (32x32, 16 tiles in rows of four) |
| `0x0300_4528`, `0x0300_4500` | the scene's two sides' unit records (first byte the unit type) and colours (0..4) |
| `0x0849_DC18 + 0x14` | the portraits `[15 * type + country]` (LZ77, 512 bytes); `sub_0803A190` loads one to OBJ tile `0x2E8` (bank 3); trap `portrait_blob` at `0x0803_A1D8` (`r8` the type byte; the army at `*[*0x08090F70] + 8`) |
| `0x0855_5D30` | the panel's palette pointers `[(type - 1) * 5 + colour]` into `0x084F2BC8` rows (two rows of 16 colours: the figures', then another) |
| `0x0801_1FF0`, `0x0200_B3B4` | the deferred copy queue drained at VBlank (12 bytes an entry: source, destination, size, kind), by which a frame's 512 bytes go from the staging buffer to the figure's tiles |
