---
name: aw2-add-map
description: Add a custom map (any 2-5 army size, plain or pre-deployed) to tangoAW2's online/offline pool via five/maps.txt.
---

Read docs/dev/maps.md first (format, ids/slots, 4 KiB per map, the data area holds a fixed number of maps).
1. Design the map in `tango-gamesupport-aw2/five/maps.txt` (legend in the docstring of `five/map.py`; `units ARMY TYPE...` lines place forces).
   Pre-deployed = units placed AND no base, airport or port (owned or neutral). Equal forces and distances for every army.
2. Regenerate: `python3 tango-gamesupport-aw2/five/map.py <path to the AW2 rom>` (writes `src/five_map_data.rs`; the ROM is only read).
3. Register id/slot in `five_map.rs` (IDS / MAP_IDS limits); do not patch past tab slot 9; online_maps.rs puts it in its count tab.
4. `./aw2dev build --all`, `./aw2dev audit maps` (armies counted from the data, exit 0), `cargo test -p tango-gamesupport-aw2 --lib five_map`
   (`every_map_has_the_armies_it_is_listed_for`), update docs/MAPS.md (`tools/maps_doc.py` / `aw2_map_audit --md`).
5. Play it: `./aw2dev live <scenario> --players N --local`, 2 rounds with fog on and off; every army can move and attack.
6. Show the SELECT MAP preview and a full-map render to the user; no release before approval. Never commit game-derived art or ROM bytes.
7. `./aw2dev maps lint --source versus --map "<name>"` must have no error (docs/dev/map-lint.md; skill aw2-map-lint); for a BH Campaign map the same with the default source.

## A Gauntlet map (docs/dev/gauntlet-mode.md "Adding a map"; the walk-through is in skill aw2-add-mode)
1. `./aw2dev gauntlet new-map NN "Name" [--apply]` scaffolds `five/gauntlet/spec/gauntlet_NN.py` and the `gauntlet_mode.rs` stub; it refuses a duplicate id and anything past **32 maps** (`gauntlet_ui::MAX_MAPS`; the 33rd needs `MAX_MISSIONS`, the cropped pictures' ROM and more map-table ids first).
2. **Keep a map to about 110 properties** (Neon Row's 150 stalled the computer's turn on day 1, 210 left properties owned after a rout; 108 is clean).
3. **Every enemy CO must be one no other map uses**: `./aw2dev gauntlet cos` lists each map's enemies, flags reuse and lists the COs no map uses yet. The only allowed repeats are the owner's named exceptions in the unit test `no_two_maps_share_an_enemy_co_but_the_named_exceptions` (Von Bolt on 05 and 12, Asuka on 02 and 12, Grit on 02 and 11, Sasha on 04 and 11, Colin on 10 and 11); a new exception needs the owner's word.
4. Then `aw2dev maps gen --campaign gauntlet`, `aw2dev maps lint --source gauntlet`, waves (`aw2dev maps wave`), the registry rows (`aw2test/gauntlet_maps.py`, `SELECTOR_ORDER`/`SELECTOR_TITLES`), `aw2dev gauntlet test`, `aw2dev campaign scene-check`, and look: `aw2dev gauntlet army-sheet --map NN`, `aw2dev gauntlet faces --map NN`, `aw2dev gauntlet maps-pictures`.
