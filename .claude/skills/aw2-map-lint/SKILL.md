---
name: aw2-map-lint
description: Check and fix the integrity of tangoAW2's maps (BH Campaign, Versus) with aw2dev maps lint: unfinished rivers, puddles, bridges ending in water, broken joins, units on ground they cannot stand on, unreachable properties. Use after drawing or editing any map.
---

Read docs/dev/map-lint.md (rules, what the games allow, how to fix each).
1. `./aw2dev maps lint` (BH maps; `--source versus`, `--map bh19`, `--warn` for the games' own slips too). It prints rule id, cell and text, and writes an annotated picture per map to
   `devkit/work/maps/lint/<source>/` (red = error, amber = warning): LOOK at it. `./aw2dev maps rules` shows what AW2 and Dual Strike do under each rule (the calibration: an error is a rarity
   in their 179 + 256 maps).
2. Fix the text map (`five/bh/bh*.txt`; a road over a river is a bridge `=` and the river runs on to the map edge or the sea, a spring starts at a mountain or the edge; a unit on shoal
   or mountain moves to a cell its kind can enter; `UnitDef::new` spawns in `bh_act*.rs` count too), then `python3 tango-gamesupport-aw2/five/bhmap.py "<aw2.gba>"` and lint again until clean.
3. Compare: `./aw2dev maps compare --base <rev>` writes a before / after picture per changed map (for the user's approval: never commit it).
4. Boot: `./aw2dev build --examples`, then `./aw2dev maps boot --mission N` (the game's own whole-map picture, the proof the mission loads), and `./aw2dev gfx check` for the screens.
5. A new rule or a new check: add it to `devkit/aw2/maplint/rules.py` (RULES entry + check), a planted-map test in `devkit/aw2/maplint/test_maplint.py` (fires on the problem, quiet on the finished map),
   a row in docs/dev/map-lint.md (`aw2dev maps rules --md`), and run `./aw2dev test python`. Calibrate the level on AW2's and DS's own maps (`maps rules`): do they do it? then warn, else error.
6. Emerald Sun maps (`--source es`): they are generated from Python specs (`five/es/spec/esNN.py`, `aw2dev maps gen`), so fix the spec, not the txt; rule ES01 allows Black Hole's inventions only on the two maps
   tagged `blackhole` (M9, M13). See skill aw2-es-campaign.
