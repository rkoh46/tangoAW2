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
7. Design quality (docs/dev/map-lint.md, "Design quality"): `DQ01`..`DQ11` and `SP01` ask whether a map looks machine-made or is too cramped (straight rivers, rectangle patches, stripes, sparse land, big empty fields,
   unit blobs, pointless properties, HQ pockets, beaches, density and frontage). Emerald Sun maps must pass them (the lint fails on a finding); the BH Campaign's and Versus maps only report. Fix a finding by changing
   the terrain (bend the river, round the patch, mix the kinds, cluster and vary), never by raising `design.LIMITS`; a limit moves only with new calibration on the games' maps.
8. Rivers (RV05): both ends of every river must reach the map edge, the sea, a shoal or a lake, never a mountain or any land (AW2 has no source tile). Give a river a source with `Canvas.lake(cx, cy, n, seed, river_end=(x, y))`
   (the cell beyond the river's last cell; the lake's shore must be straight where the river enters) or run it to the edge. `bh10` and `bh31` break it and are in `rules.KNOWN` (not to be changed without the user's approval).
9. Look at every rebuilt map at 2x in the game's own picture (`aw2dev campaign sheets`, then `aw2dev maps render-check`): the lint was green once while rivers still ended mid-land and mountain lines still marched.
10. Design principles (docs/dev/map-design.md): `./aw2dev maps study <awbw-folder> --source es --rows` measures our maps against AWBW's Hall of Fame (properties per 100 land cells, the farthest
   ground from a property, approach roads, corridors, base safety, the middle, plain share, river runs, roads to properties). The rules MD01..MD08 fail an Emerald Sun map: add properties
   (neutral cities in the middle, forward bases), break open fields with small woods and hills, bridge long rivers, give every fortress two or more gates. AWBW grids and pictures stay in a scratchpad.
11. BH2 maps (`--source bh2`, specs `five/bh2/spec/`, `aw2dev maps gen --campaign bh2`): held to the same rules as Emerald Sun, plus IV01 (inventions only on Black Hole's side). Beaches: AW2 draws them one cell wide, long only on north- and south-facing coasts (`shore(.., dirs="NS")`). `aw2dev bh2 pictures` for the review pictures, `aw2dev maps features --campaign bh2` for coverage. See docs/dev/bh2-maps.md.
