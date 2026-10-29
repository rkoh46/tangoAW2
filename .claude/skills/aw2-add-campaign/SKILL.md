---
name: aw2-add-campaign
description: Add or extend a custom campaign (missions, scenes, songs, prologue) on the BH Campaign's data-driven engine; list and trace scenes and music with aw2dev campaign.
---

Read docs/dev/campaign-scenes.md and docs/AW2.md "BH Campaign".
1. Missions are `MissionDef`s (`bh_act*.rs`), maps `five/bh/*.txt` (`aw2dev maps lint`, skill aw2-map-lint), dialogue `src/bh_text/*.txt` (`tools/bhtext/lint.py`).
2. Every story scene (intro, victory, scenes on the map after a win, prologue) names a song: `@SONG role` (`aw2dev sound list`); chain scenes with `bh_text::chain`. A scene between missions is `mNN_sturm`-style: last in the `after` chain.
3. `./aw2dev build --examples`, `./aw2dev campaign scenes` (every scene with its song), `./aw2dev campaign trace --mission N` (no silent dialogue; fades), `./aw2dev gfx check`.
4. `aw2dev test`, `tools/aw2test` `-k bh_text_budget` (3,072 text ids), `./aw2dev suite`. Show the scene table and the new lines to the user before any release.
5. A second campaign (the Emerald Sun, `src/es_*.rs`, `five/es/`, `src/es_text/`) is the worked example: skill aw2-es-campaign, docs/dev/es-campaign.md.

## A picture world map (BH2)
1. Put the owner's picture in `art-src/worldmap/<name>_world.jpg` with a `<name>_world.toml` (crop, size, nation seeds, palette plan, tint) like `bh2_world.toml`.
2. `./aw2dev worldmap convert <name>` writes `tango-gamesupport-aw2/art/worldmap/<name>_world.bin`; `./aw2dev worldmap preview <name>` and LOOK at it; `./aw2dev worldmap check <name>` must be clean.
3. A source uses it with `art: WorldArt::Picture(&world_picture::BH2)`; until then `TANGOAW2_BH_WORLDMAP=bh2` plays the BH Campaign on it, and `python3 tools/aw2test/run.py --mode ds -k bh_picture_map` photographs it. Details: docs/dev/worldmap.md.


BH2 maps (docs/dev/bh2-maps.md): specs in `five/bh2/spec/`, `aw2dev maps gen --campaign bh2`, `aw2dev maps lint --source bh2`, `aw2dev bh2 pictures` (look at them: MISSION N - Title is burned in, fog off plus the fogged view), `aw2dev bh2 features` (coverage), `aw2dev bh2 check` (world-map flags on land inside their nation; `world_picture::BH2_FLAGS`).

## A mission in stages (a map switch inside one battle)
Read docs/dev/stages.md. A mission declares `MissionDef::stages` (`StageDef`: map, armies with the player's `CoSpec::Keep`, units, deploy cells, `Carry`, look, weather, triggers, intro) and a trigger ends a stage with `Action::NextStage` (put its scene before it). The survivors, funds and CO meters carry over; five-army and four-army stages both work; a battle saved on a later (four-army) stage resumes on it. Prove it like BH2's M31: harness `bh2_m31_progression`, `bh2_m31_stage_two_suspend_and_resume`, `bh2_m31_switch_is_deterministic` (`tools/aw2test/tests/test_bh2_progression.py`).
