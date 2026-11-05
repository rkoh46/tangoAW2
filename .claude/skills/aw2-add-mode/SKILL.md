---
name: aw2-add-mode
description: Add a custom game mode to tangoAW2 (a Select Mode wheel entry, a gauntlet map, staged battles, a new rule set); start from the engine pieces the campaigns already use
---

The first mode built this way is the Gauntlet (docs/dev/gauntlet-mode.md: read it first). Build a new mode on the engine pieces that already exist instead of mission-specific code, and grow the kit as you go (docs/dev entry, aw2dev tool, harness test, this skill).

## A new map for the Gauntlet
1. Spec and map: `five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`, `aw2dev maps lint --campaign gauntlet` (docs/dev/map-lint.md). Enemy armies on team 2 (the player's team is its own army number, 1; a team of 1 made the enemies the player's allies).
2. A mission function in `tango-gamesupport-aw2/src/gauntlet_mode.rs` added to `def()` (copy `cinder_sea`): the player's army `CoSpec::Pick`, the enemy COs fixed, hidden lines (`MissionDef::hidden`, `sleepers`, `cut_off`, `held_hq`/`held_more`) and `arrive(..)` triggers, `rank_days`. Its key is `gauntlet_NN`.
3. Nothing else lists it: the map selector (`gauntlet_ui.rs`: the game's own War Room SELECT MAP, one map-table entry per mission, ids from `FIRST_ID`, 8 at most) lists every mission of `def()` with its name and picture and the faces of its first three enemies (`ArmyDef` index 1 on: `CoSpec::Fixed` CO and the **colour the map fixes**) and the best result in its record box, and the colour
   pick offers the colours those enemies do not wear (`gauntlet_mode::Entry::free`: AW2's five minus the enemies', plus Silver Nova). Fix every enemy's colour in the mission (never leave it to the player's pick); check the new map in
   `the_free_colours_are_the_five_minus_the_enemies_plus_the_skins`-style tests and the audit page (`aw2_online_text_audit.rs`, `gauntlet`: the colour pick) with its longest names; look at the selector in the three looks (`-k gauntlet_pictures_selector`).
4. Tests (the rout test too, see the Gauntlet bullet below): a row for the map in `tests/test_gauntlet_mode.py` / `aw2test/gauntlet.py` (`CINDER`: its HQs, `CINDER_FREE`), and run `aw2dev gauntlet test`, `aw2dev audit text`. Pictures: `aw2dev gauntlet start --co N`, the `gauntlet_walkthrough_pictures` sheets.

## A new wheel entry (a mode of its own on Select Mode)
1. `mode_menu.rs`: a new item id (10, ...), an `Extra` (its OBJ palette, its small-label tiles, its data page in ROM: `GAUNTLET_AT` + 0x1000 steps below `SENTINEL`), `TABLE` and `N` (one more entry), the DivRem/wrap
   patches in `HALVES` for the new count (N - 1 wraps; `(i + N - 2)`; the help table's Sound Room / Hard Campaign lines at N and N + 1; Campaign's table index N - 1), `help` / `options` lists in
   `install` in position order, the labels from the game's letters (`BIG_LETTERS`/small cells) and a palette blend. Decide the position on the screen (higher position = higher on the screen) and fix the
   tests' positions (`saves.PACK_WHEEL`).
2. Prove the palette and tiles free: `gauntlet_mode_wheel_obj_resources_are_free` (extend it with the new entry); `cargo test --lib mode_menu rom_layout ram_map`.
3. What A starts: `picked` / `mode_store` in `mode_menu.rs` (the mode number the game's dispatcher runs: 1 Campaign New, 5 War Room New, ...); the mode itself in a module of its own (`gauntlet.rs` is the model).
4. A campaign-engine mode: a `campaign_model::SOURCES` entry (index = the next, keep `DISPLAY_ORDER` of the Campaign menu without it; its Flash region in an existing slot's free tail, `save_offset`, a `source_tag` for the mid-battle slot), the per-source arrays (`ds_campaign::BUILT`, `custom_campaign::RULES`), `start()` branching to your start function, `end_of_battle` and the proc scripts.
5. Offline only: wheel patches are applied with `mode.is_none()`; never touch the battle's simulation (else bump `inspect::SIM_VERSION`).

## Engine pieces to reuse (all data on a `MissionDef`, mission-agnostic)
- **Gauntlet** (docs/dev/gauntlet.md): armies off the battlefield until the line before falls. `MissionDef::hidden` (army, HQ cell, zone), `sleepers`, `cut_off`, `Cond::LineFallen`, `Action::Reveal`; put the wave (`Action::Spawn`) and its funds in the same trigger as the reveal. Worked examples: `bh2_campaign::bh2_31`, `gauntlet_mode::cinder_sea`.
  **The rout rule (permanent, every gauntlet map):** capturing a line's HQ routes its army at once (all units destroyed, every property neutral, then the next line comes). It is the engine's: list every line but the last in `cut_off` (army, HQ) and `held_hq`/`held_more` (the last line's HQ in `held_more` only: its capture wins). Add a rout test for the new map (`tests/test_gauntlet_rout.py`, helpers `aw2test/rout.py`: plant DS-only, loaded, dived and hidden units, capture, check 0 units, 0 owned cells, next line in, control kept). Docs: docs/dev/gauntlet.md "The rout".
- **Stages** (docs/dev/stages.md): the same battle moves on to another map (`Action::NextStage`, `MissionDef::stages`), with carry-over and suspend.
- **Five-army suspend** (docs/dev/five-suspend.md): battles with five armies save and continue.
- Triggers, scenes, spawns and held HQs: docs/dev/bh2-maps.md, docs/dev/campaign-scenes.md.

Checks every mode needs (copy `tests/test_gauntlet_mode.py`): the wheel (positions, pictures, the pack off = AW2's own), a free pick, the win and the loss back on Select Mode, the record and that other saves are byte-identical, Save and Continue, hidden armies absent and turnless and each reveal (the M31 tests in tools/aw2test/tests/test_bh2_*.py), online untouched. Pictures: `aw2dev gauntlet start`, `aw2dev campaign playthrough ... --waves` (docs/dev/playthrough.md).

Rules: compose any art from AW2/DS assets read from the ROMs at runtime (never draw it, never commit game data), keep the engine data-driven, and ask the user before inventing a format or the mode's menu entry.

## Worked example: how the Gauntlet was built (repeat it step by step)
1. **Plan the engine, not the mission.** Hidden lines and the rout rule are mission-agnostic data (docs/dev/gauntlet.md); the mode is a campaign source (`SOURCE` 4 in `campaign_model.rs`, `crate::gauntlet_mode::def()` = the maps as `MissionDef`s). Files: `gauntlet.rs` (the mode's state, records, `picked`), `gauntlet_mode.rs` (the maps and `ROSTER`), `gauntlet_ui.rs` (the map selector and the single army screen), `mode_menu.rs` (the Select Mode wheel entry), `ds_campaign.rs` (`start_gauntlet`, `gauntlet_start_script`, `gauntlet_end_script`, `after_map`, `end_of_battle`).
2. **Wheel entry:** `mode_menu.rs` item and palette; prove the palette and tiles free (`-k gauntlet_mode_wheel_obj_resources_are_free`), `cargo test --lib mode_menu rom_layout ram_map`. Aid: `./aw2dev gauntlet start` photographs wheel -> selector -> army screen -> Setup -> day 1.
3. **Map selector = the game's own War Room screen** (`ProcScr_PreviewMap` `0x08616C54`): one map-table entry per mission, ids from `FIRST_ID`, list sorted by enemy count (`gauntlet_mode::order`; `./aw2dev gauntlet order`). Test `-k gauntlet_pictures_selector` (three looks).
4. **Army screen** = Versus' Teams page (`army_cards::teams_frame`) with one army-1 card and the enemies as cards: `./aw2dev gauntlet army-sheet`, `./aw2dev gauntlet faces`; tests `gauntlet_mode`, `faces_vs_army_screen`.
5. **Start and end:** `ds_campaign::start_gauntlet` (record kept, flags cleared, start proc), results and back to Select Mode (`gauntlet_end_script`, `after_map`); records in Flash by mission key (`gauntlet.rs`; saves must stay byte-identical elsewhere: `test_save_integrity_modes.py`). Tests `-k gauntlet_mode` (`./aw2dev gauntlet test`).
6. **Maps:** `./aw2dev gauntlet new-map`, specs, `aw2dev maps gen/lint --campaign gauntlet`, `./aw2dev gauntlet cos` (unique enemy COs).
7. **Rout rule:** every line but the last in `cut_off`; `tests/test_gauntlet_rout.py`, pictures `./aw2dev gauntlet rout-sheet`.
8. **Scenes:** arrival boxes and face palettes: `./aw2dev campaign scene-check` (docs/dev/campaign-scenes.md); text: `./aw2dev campaign text-lint`.
9. **The mission card:** a mode that runs through AW2's campaign mission proc opens on AW2's "MISSION n" card with the "MISSION START" seal; if the mode has no missions, repaint it the way `gauntlet_card.rs` does (word sprites, number tiles, the seal's band, all gated on the mode's session; docs/dev/gauntlet-mode.md) and prove with `aw2dev gfx audit --scenes mission_card` and `-k gauntlet_card` that the real campaigns' cards stay AW2's.
10. **Close:** `./aw2dev kit check`, `./aw2dev test`, `python3 tools/aw2test/run.py -k gauntlet --mode ds -j 4`, `-k cpu_port_idle_gauntlet`, `-k cpu_progress`; every command above has a docs/dev entry (gauntlet-mode.md "Kit commands").
