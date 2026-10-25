---
name: aw2-es-campaign
description: Build, check and balance the Emerald Sun Campaign (16 missions): maps from specs, mission logic, dialogue lint, review sheets, the mission sim and the difficulty score. Use for any change to an Emerald Sun mission, map, scene or CO.
---

Read docs/dev/es-campaign.md and docs/ES_CAMPAIGN.md. Standing rules: one battlefield (no two-front), Black Hole inventions only in M9 and M13, M16 clearly the hardest, no army above 56 start units, nothing pushed or released without the user.
1. **Map**: edit `tango-gamesupport-aw2/five/es/spec/es01.py (one a mission, es01 .. es16)` (never the generated txt), `./aw2dev maps gen --no-build --map esNN`, `./aw2dev maps lint --source es --map esNN --warn` and LOOK at `devkit/work/maps/lint/es/ (one picture a map)`; then `./aw2dev maps gen` (builds `src/es_map_data.rs`).
2. **Mission**: `src/es_act1.rs` .. `es_act4.rs` (`MissionDef`s; `on_day`, `after`, `deployment` helpers in `es_campaign.rs`); dialogue `src/es_text/act1.txt` .. `act4.txt` (`python3 tools/estext/lint.py`), a new key must be asked for by the code and defined in a file.
3. `./aw2dev build --examples`, then `python3 tools/aw2test/run.py -k es_boot_m` (every mission boots), `./aw2dev campaign scenes --campaign es` (every story scene has a song).
4. Look: `./aw2dev campaign sheets` -> `devkit/work/campaign/es/sheets/` (MISSION N - Title, fog off and fogged, a contact sheet per act).
5. Balance: `./aw2dev campaign sim --mission N --player bot cpu --seeds 3` then `./aw2dev campaign difficulty --require-final` (M16 must lead by 10%); the numbers go in the hand-back.
6. `./aw2dev campaign check`, `./aw2dev test python`, `cargo test --release -p tango-gamesupport-aw2 --lib es_`, `./aw2dev suite`.
7. **World map** (Dual Strike's Omega Land, docs/dev/es-campaign.md "The world map"): a mission's flag is `m.flag = region::ACTn[k]` in `es_campaign.rs` (map pixels on the 480 x 240 map), on land and 16 px from the others; `./aw2dev campaign check` reads the picture from the .nds and fails a flag in the sea. Look: `./aw2dev campaign worldmap` runs `-k es_world_map` and `-k es_progression` (every mission won in turn, flags, cursor, record and Continue asserted) and writes `devkit/work/campaign/es/worldmap/es_world_map.png`.
