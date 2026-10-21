# Maps: format, pipeline and pools

Scope: tangoAW2's own Versus maps (`tango-gamesupport-aw2/five/maps.txt` -> `src/five_map_data.rs`), how the map lists find and sort maps (online and offline), and how to audit and add a map. Nothing from either game is committed: AW2's maps stay in the ROM; Dual Strike's are read from the pack at run time. `docs/MAPS.md` is the generated per-map table (ids, sources, armies, counts per tab).

## 1. Files

| Path | Role |
|---|---|
| `tango-gamesupport-aw2/five/maps.txt` | Source text of tangoAW2's 20 Versus maps (one `map NAME` block each) |
| `five/map.py <rom.gba>` | Parses `maps.txt`, lays tiles (joins roads, rivers, pipes, coasts, mountains as AW2 draws them), places units, LZ77-packs, writes `src/five_map_data.rs`, then runs `tilecheck.py` over every tile pair; exits 1 on a tile pair the game's own maps never use |
| `five/tilecheck.py <rom.gba>` | Learns from AW2's built-in maps which neighbour tile pairs occur and reports pairs that would look broken (`check_all`, `describe`) |
| `five/design_maps.py` | Draws most of the maps (hand text and shape-built ones) and MERGES them into `maps.txt` (`five/mapsfile.py`): maps it draws are replaced, every other block (Pentagon Atoll, hand-added maps) is kept; it calls `design_ds_maps.draw` and `design_vault_map.draw` |
| `five/map_ids.txt` | `Name = 0xID` for every map; `map.py` reads it, gives a new map the next free id of the pool 0xF2..0xFF (appending it) and writes `IDS` into `five_map_data.rs` |
| `five/test_five.py` | Python tests (`aw2dev test python`): merge keeps every map, a re-draw keeps Pentagon Atoll and hand-made maps, ids unique and from the pool, room in the data area |
| `five/pentagon.py [--print] [--fix <rom>]` | Generates the Pentagon Atoll block (35x35, 5-fold symmetric, rivers as continuous channels, `at` unit lines); prints the block for pasting into `maps.txt`; `--fix` edits cells until no tile violation remains |
| `src/five_map_data.rs` | GENERATED ("Generated from five/maps.txt by five/map.py; do not edit"): `pub const MAPS: &[Map]` with name, armies, tab, colours, `obelisk`, `ds`, `wasteland`, LZ77 tiles, 12-byte unit records |
| `src/five_map.rs` | Installs the maps into the ROM image (`install`), the id table `IDS`, tab/ list patches, `show_maps`, tests |
| `src/online_maps.rs` | Player-count lists (online and offline Versus), audit (`audit`), previews, pre-deployed rule |
| `examples/aw2_map_audit.rs` | CLI audit of the whole pool |
| `tools/maps_doc.py <aw2.gba> <ds.nds>` | Regenerates `docs/MAPS.md` from the audit |
| `five/bhmap.py` + `five/bh/*.txt` | A separate pipeline for the BH Campaign's maps (`src/bh_map_data.rs`); same legend plus `team`, `split`, `owners`, `nohq`, `objective`, `unit` lines and reachability checks. Not in the versus pool |
| `src/ds_versus.rs`, `src/ds_maps.rs`, `src/survival_maps.rs` | Dual Strike's own maps converted from the pack at run time (not committed) |

Fixed: `design_maps.py` used to overwrite all of `maps.txt` (dropping Pentagon Atoll); it now merges (`mapsfile.merge`, tested). A map block of yours that it does not draw is safe; one it draws is replaced by its code.

## 2. `maps.txt` format

Parsed by `map.py: parse`. Blank lines and lines starting with `#` are skipped. Per map:

```
map NAME                     name (< 0x20 bytes; an apostrophe is stored as '~', AW2's font)
armies N TAB C1 C2 ..        N armies, the Versus tab, N start colours (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole)
look wasteland | look pack   optional: Wasteland colours (pack only) / normal colours but pack-only
units ARMY TYPE TYPE ..      forces placed by rule (see below)
at ARMY TYPE X Y             a unit placed exactly there
<rows>                       one row per line, one character per tile, all the same width
```

TAB used by existing maps: 3 = Vs. (2 armies), 5 = 3P Maps, 6 = 4P Maps, 9 = 5P Maps (`CATEGORY`). Check: `armies 2 3 ..`, `armies 3 5 ..`, `armies 4 6 ..`, `armies 5 9 ..` in `maps.txt`.

Limits asserted by `map.py: grid`: width <= 64, height <= 40 (the AI's 40-entry row stack, `sub_080581A4`), width x height <= 1288, every row the same width, exactly one HQ per army (digits `1`..`N`), and `len(colours) == N`.

### Tile legend (docstring of `map.py`)

- `~` sea (coast edge tiles chosen from the game's table at ROM 0x485DC4), `r` reef, `.` plain, `f` wood, `^` mountain
- `R` road (straights, bends, junctions), `I` pipe, `Z` pipe seam (inside a straight run; may end at a base)
- `-` river, `=` bridge (over river or sea; roads join it), `,` shoal
- `t` / `T` Com Tower: neutral / owned by the army whose HQ is nearest
- `1`..`5` HQ of army 1..5; `Q` a second HQ tile of the nearest army (BH Campaign Rail Yard)
- `B C A P` base, city, airport, port of the army whose HQ is nearest; `b c a p` the neutral ones
- Black Hole's inventions, each at its anchor with `#` over the rest of the footprint: `S N W E` minicannon facing down/up/left/right, `L` laser, `v n` Black Cannon facing down/up (3x3), `F` Black Factory (3x4, anchor on the third row), `V` Volcano (4x4, anchor second column, third row), `D` Deathray (3x3), `M` missile silo (one tile)
- `X` Black Crystal (1 tile), `O` Black Obelisk (3x3): tangoAW2's healing structures (Black Hole army's, `obelisk.rs`)

Ownership of `B C A P T Q`: the army whose HQ is nearest by Manhattan distance, ties to the lower army number (`grid: owner`).

### Unit types (`units` and `at`)

1 Infantry, 2 Mech, 3 Md Tank, 5 Tank, 6 Recon, 7 APC, 8 Neotank, 10 Artillery, 11 Rockets, 14 Anti-Air, 15 Missiles, 16 Fighter, 17 Bomber, 19 Battle Copter, 20 Transport Copter, 21 Battleship, 22 Cruiser, 23 Lander, 24 Submarine. Dual Strike's: 4 Megatank, 9 Piperunner, 12 Stealth, 13 Black Bomb, 18 Black Boat, 26 Carrier, 27 Oozium (`DS_UNITS`). Placement by rule (`build`): ships in sea cells beside the army's ports (or, with no port, water of its own ground beside land, nearest the HQ), aircraft on plain/wood within 2 cells of its airports (else free land), Piperunners on its nearest pipe cells `I`, everything else on free plain/wood nearest the HQ. `at` lines are placed first, exactly. A unit that finds no free spot fails the build (`assert spot`).

Unit record written: 12 bytes `x y kind 0 0x64 0x63 0x63 0 0 4 0 0` (HP 100, ammo/fuel 99); each army's list starts with `FE army 00..` and the table ends with `FF 00..`.

### Pack gating (`needs_pack`)

A map is pack-only (`ds: true` in `five_map_data.rs`) when it has `look wasteland` or `look pack`, a Com Tower (`t`/`T`), a Piperunner, or any Dual Strike unit type. A map with `X`/`O` is flagged `obelisk` (needs the pack's art). `five_map::needs_pack(map) = map.ds || map.obelisk`.

## 3. Generating `five_map_data.rs`

```
python3 tango-gamesupport-aw2/five/map.py "<Advance Wars 2.gba>"
cargo test -p tango-gamesupport-aw2 --lib five_map
```

`map.py` prints one line per map (`name: WxH, N bytes, units, properties`). The ROM is only read (sea-edge table, `tilecheck`). The compressor: tiles are stored as literal LZ77 blocks unless `len(raw) + (units+1)*12 > 3000`, then real LZ77 matches (`lz77(raw, compress)`; the VRAM BIOS variant forbids a match displacement of 1).

## 4. Installing into the ROM image (`five_map.rs`)

- AW2's map table (0xC0 entries x 0x5C bytes at 0x085C77A0) is copied to `MAP_TABLE = 0x08650000` with a row for every byte id (`MAP_IDS = 0x100`); 37 literal-pool words and two loops (`TABLE_POINTERS`, `TABLE_LOOPS`) are repointed. The loops stop at id 0xC0 without the pack and 0xFF with it (`show_maps`): ids past 0xC0 are pack content.
- `IDS` (generated into `five_map_data.rs` from `five/map_ids.txt`, in `maps.txt` order; re-exported by `five_map.rs`) gives each map its id. **The id space is the limit, not the data area**: a table row is a byte id and 0..0xF1 are taken (game, Design Room, DS Versus replacements 0xB4..0xB6 moved to 0xC1..0xC3, Survival 0xC9..0xEF in its own table copy, the campaigns' 0xF0, the Vault 0xF1), so `NEW_ID_POOL` = 0xF2..=0xFF gives **14 more maps** (34 in all). More would need ids to be virtualised (not built). Current: Five Seas 0 (dummy entry), Iron Crossing 0xBC, Magma Crown 0xBD, Skyreach 0xBE, The Citadel 0xBF, Obelisk Duel 0xB8, Crystal Isles 0xB9, Obelisk Plains 0xBA, Black Monolith 0xBB, Black Rampart 0xC0, Rust Basin 0xC1, Dune Fork 0xC2, Cinder Flats 0xC3, Black Wastes 0xC4, Coral Strait 0xC5, Trident Isles 0xC6, Harbor Cross 0xC7, Coral Crown 0xC8, The Colonel's Vault 0xF1, Pentagon Atoll 0xC9.
- Per-map data slot: **4 KiB each** (`MAP_DATA_SIZE = 0x1000`) holding the LZ77 tiles then the unit list, in ONE run from `MAP_DATA = 0x09D00000` (past the DS Versus maps; the run is free up to the Normal look at 0x09E00000): room for `MAP_CAPACITY = 64` maps, raise the constant (up to 256) to grow. (They used to be split between 0x08622000 and 0x08656000: exactly 20.) Tests assert the capacity and the neighbours.
- Names: `STRINGS = 0x08622000`, 0x20 bytes per string; text ids `TAB_TEXT = 0x3D72 + 64 + slot` (slot 0 is the tab title "5P Maps", then the maps' names, then two tab titles per player count at slots `1 + MAP_CAPACITY + ...`, `name_tab`), 73 slots. Pointers are read from `0x08620000 + 4*(id - 0x3D72)`, i.e. from `0x08620100` (the roster owns slots 32..56 below it).
- Map header (0x5C bytes, written in `install`): +0x00 and +0x2C tiles, +0x14 name text id, +0x16 = 2, **+0x18 armies = `min(armies, 4)`** (a 5-army map says 4: army 5 is tangoAW2's; `online_maps::armies_of` corrects it via `is_five_map`), +0x1A tab, +0x34 units, +0x40.. colours (first 4).
- Black Hole (army 5) property tiles 0x1B4..0x1B9 are installed too (`ARMY5_TILES`).
- Maps with `ds`/`obelisk` sit on `HIDDEN_TAB = 0x7F` unless the art and pack are on (`show_maps`, run every frame).
- Ids 0xB8..0xBF are made ordinary map ids by the `ORDINARY_IDS` patches (they are Design Room range to the game); do not place a map at 0xB4..0xB7 (Design slots/suspend copy, excluded by the lists).
- Free ids: the code names none. 0xC9..0xEF carry Survival's maps and Champion courses, 0xF0 the campaigns' mission map (comments on `VAULT_ID`), and the `dual_strike_maps_are_the_new_ids` test requires `m.ds == (id > 0xC0)` for every tangoAW2 map and `id <= VAULT_ID`.

Tests in `five_map.rs`: `maps_fit_their_slots` (unique ids, `id < MAP_IDS`, slot sizes, names < 0x20, wasteland implies ds), `dual_strike_maps_are_the_new_ids` (also asserts 4 wasteland maps and the per-army count of ds maps: 2 armies 3, 5 armies 3, others 2; update these constants when adding a ds map), `every_map_has_the_armies_it_is_listed_for` (below).

### `every_map_has_the_armies_it_is_listed_for`

`counted(map)` decompresses the tiles, counts owners of property tiles (neutral 0x1C0.., armies 1..4 in 0x1C5..0x1D8, army 5 in 0x1B4..0x1B8) and owners of placed units, plus HQs and production properties (base +1, airport +3, port +4 in each owner's five tiles). The test asserts: number of owner armies == `m.armies`; `1 <= hqs <= armies`; `colours.len() == armies`; armies in 2..=5.

## 5. Lists and pools (`online_maps.rs`)

- Map tabs in the game's Versus list are header +0x1A values 2..=9 (`TABS`); `HIDE = 0x7E` is a tab no list shows (the game's own hidden tab is 0x7F). The list holds up to `LIST_CAP = 0x6E` (110) maps per tab (`five_map.rs`: the game's builder stopped at 50 and its struct is moved to RAM `LIST = 0x0203DC20` by `patch_list`).
- **Pre-deployed rule** (`Info::predeployed`): `placed > 0 && bases + airports + ports == 0`. Units placed AND no base, airport or port, owned or neutral (kinds 14, 10, 11 of the terrain class table at ROM 0x080C1BC4). Units placed and a base = a plain map. Property kinds counted: 6, 8, 10, 11, 14, 20.
- **Armies of a map**: header +0x18, except tangoAW2's 5-army maps (`is_five_map`) which count as 5 (`armies_of`). Audit counts armies from the data instead: `owners | unit_owners` popcount.
- **Online (a room of n players)** `retab` runs every frame in a room's match: each map's tab becomes 2 (plain) or 4 (pre-deployed) when its army count equals n, else `HIDE`; Design Room ids 0xB4..0xB7 always `HIDE`. Tab titles "nP" and "nP Predeploy" (`tab_titles`; "NP - Predeploy" is too wide for the tab box). `offered(core, id)` validates a private pick.
- **Offline Versus**: eight tabs in game slots 2..9: `count_tab(n, pre) = 2 + 2*(n-2) + pre` ("2P" 2, "2P Predeploy" 3, .. "5P Predeploy" 9). A tab with no map is skipped. L and R together toggle to AW2's original lists (Classic, Vs. Maps, Pre-Deployed, 3P, 4P, War Room, Design, tangoAW2's 5P Maps); the choice is kept for the session (`ORIGINAL_VIEW`). Each map's original tab is saved at `OFF_SHADOW` and restored outside Versus. `TAB_BOUNDS` already raises the game's last tab from 8 to 9 (`five_map.rs`); the session handoff says not to patch past slot 9 (reason not stated in code). Test `each_count_has_a_tab_of_its_own` asserts the eight tabs are distinct and listable.
- **Pool sources** (`audit`/`source_of`): "AW2 Classic" (tab 2), "AW2 Vs. Maps" (3), "AW2 Pre-Deployed" (4), "AW2 3P Maps" (5), "AW2 4P Maps" (6), "AW2 War Room" (7), "DS Versus", "DS War Room", "tangoAW2". Needs-pack: `source` starts with "DS " or a tangoAW2 map with `needs_pack`.
- **Dual Strike maps** (`ds_versus.rs`): with the pack, a separate 0x100-id table `ds_versus::TABLE` puts DS's 138 Versus and 44 War Room maps over AW2's ids; `last_id` is 0xFF then. Online, DS content is offered only when every peer has the pack (the lobby's shared-content bit; see `ds-pack.md`).

## 6. Auditing

```
cargo build --release -p tango-gamesupport-aw2 --example aw2_map_audit
target/release/examples/aw2_map_audit "<aw2.gba>"                 # AW2 + tangoAW2 maps
TANGOAW2_DS_ROM="<ds.nds>" target/release/examples/aw2_map_audit "<aw2.gba>"   # + the pack
... --md | --sources | --needs-pack                                # Markdown tables used by docs/MAPS.md
python3 tools/maps_doc.py "<aw2.gba>" "<ds.nds>"                   # rewrites docs/MAPS.md
```

It boots a 2-player online-match console (600 ticks), calls `online_maps::audit`, sorts by (armies, predeployed, id), prints one line per map (`NP [predeployed] id name source WxH hqs units bases airports ports header N`) and per-count totals on stderr. Exit 1 when any row is a mismatch: `hqs > armies`, armies outside 2..=5, or `armies != header`.

## 7. Adding a map, step by step

1. Decide players (2..5), plain or pre-deployed, and whether it needs the pack (Com Tower, Piperunner, DS unit, `look wasteland|pack`, `X`/`O`).
2. Draw the block in `five/maps.txt` (or in a generator that you also wire into `design_maps.py`, remembering it overwrites the file). `armies N TAB colours` with TAB 3/5/6/9 for N=2/3/4/5. One HQ digit per army; every property tile belongs to the army whose HQ is nearest. For pre-deployed: use `at`/`units` and NO `B b A a P p` anywhere.
3. The id: leave it to `five/map.py` (it takes the next free id of 0xF2..0xFF, appends `Name = 0xID` to `five/map_ids.txt` and marks the map pack content) or write a line in `map_ids.txt` yourself for a pre-pack id (unique, not 0xB4..0xB7). Run `aw2dev test python` and `cargo test -p tango-gamesupport-aw2 --lib five_map`.
4. Run `python3 tango-gamesupport-aw2/five/map.py <aw2.gba>`; fix any `tilecheck` violations (a tile pair the game never places), the size asserts (<= 64 wide, <= 40 tall, <= 1288 tiles), and `assert spot` (not enough free ground for a `units` line).
5. Update the test expectations that count maps (`dual_strike_maps_are_the_new_ids`: ds count per army number and wasteland count) and run `cargo test -p tango-gamesupport-aw2 --lib five_map online_maps`.
6. Audit (section 6) with and without the pack: no MISMATCH; the map appears in the right tab ("NP" vs "NP Predeploy").
7. Regenerate `docs/MAPS.md` with `tools/maps_doc.py`.
8. Show the preview and full-map render for approval before any release (session rule; see the memory notes in the project handoff), and run a live 2-round match on it with fog on and off.

Open items recorded in the session notes (not code): the map-list scroll glitch (a mid-scroll frame of the SELECT MAP list on a waiting window shows garbled rows; check `fog_view` scratch picture and `unranked.rs` box).
