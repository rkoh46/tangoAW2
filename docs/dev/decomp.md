# Using the Dual Strike decompilation for rules and tables

Location: `~/advance-wars-dual-strike-decomp` (a separate checkout, not part of this repo). It is a matching decompilation of Advance Wars: Dual Strike, US/AUS cartridge (game code `AWRE`), licensed CC0 1.0 (`LICENSE`). `PROGRESS.md` reports 100% of code decompiled and linked (8571 / 8571 functions). Its `README.md`, `CLAUDE.md`, `TENETS.md`, `docs/` explain the build; you do not need to build it to read rules.

## 1. What it contains and what it does not

- Contains: C for every function (readable comments on many), headers with struct layouts and enums, symbol tables with addresses, and the tools that read the ROM.
- Does NOT contain game data. Numeric tables (unit stats, damage charts, CO power blocks, terrain stats, map tiles) are written as `#include "data/<module>/<symbol>.inc.c"` inside initializers; those `.inc.c` files are generated from a ROM by `tools/data_inc.py` at build time into `extracted/AWRE/data/...` (`extracted/README.md`). In this checkout `extracted/` holds only its README and there is no `orig/` or `build/`, so the VALUES are not on disk. Get values from the Dual Strike ROM or from the pack (section 5), and use the decomp for what the values MEAN (field names, units, formulas, order of operations).
- Example: `src/game/ov000/unit_info_panel/unit_info_panel_draw_page_marker.c` defines `UnitStats Ov000_gUnitStats[UNIT_TYPE_COUNT] = { #include "data/ov000/Ov000_gUnitStats.inc.c" };`.

## 2. Directory map

| Path | What |
|---|---|
| `src/game/main/` | The game's resident code (1749 files), grouped in subdirectories (below) |
| `src/game/itcm/` | Fast-RAM routines: range maps (`range_map/fill_attack_range.c`, `load_move_costs.c`, `fill_unit_moves.c`), `map3d/` |
| `src/game/dtcm/` | Small data |
| `src/game/ov000/` | Overlay 0: loaded for menus and battles; map data (`map/map_headers.c`, `map_tiles.c`, `map_units.c`), unit stats table (`Ov000_gUnitStats`), second-screen terrain/unit info panels, CO panel |
| `src/game/ov001/` | Overlay 1: map event scripts (`MapScript`, `EventTrigger`, `docs/maps.md`) |
| `src/game/ov002/` | Battle scene animation (`battle_*`: cells, sprites, hit lists) |
| `src/game/ov003/`, `ov004/` | ov003 not characterised here (its first files are `func_ov003_*`); ov004 graphics helpers (`ov004_blend_*`, `ov004_blit_*`, affine) |
| `src/game/ov005/` | Menu UI: CO list/grid/palette buttons, state screens |
| `src/game/ov006/` | Design Room and its random map generator (`Ov006_GenerateRandomMap`, tool-placement checks) |
| `src/sdk/`, `src/arm7/` | Library code and the second CPU (sound etc.) |
| `include/game/*.h` | Structs and enums: `unit_stats.h` (`UnitType`, `UnitStats` 0x6C bytes), `co_data.h` (`CoId`, `CoPowerState`, `UnitClass`, `CoPowerBlock` 0x80, `CoRecord` 0x220, `CoStatRow`), `terrain.h` (`TerrainId`), `combatant.h`, `map_unit.h`, `player.h`, `map_header.h`, `predeployed_unit.h`, `Unk_02080440.h` (the battle state), `power_damage.h` |
| `config/AWRE/arm9/symbols.txt` | Address -> name (`MarketCrash kind:function(arm,size=0x1ac) addr:0x020e1d2c`); per-overlay symbols are under `config/AWRE/arm9/overlays/` |
| `config/AWRE/names-provenance.csv` | Where a name came from (`MarketCrash,main,0x020e1d2c,rh890:...`: RadioTails' romhacking.net document 890) |
| `docs/maps.md`, `docs/map-terrain.md` | Map header/tiles/units layout and tile codes; `docs/awre-facts.md` ROM facts and module addresses |
| `assets/maps/` | `maps.txt`, `tiles.txt`, `units.txt`, `legend.yaml`: how to read map data (no data) |

Subdirectories of `src/game/main/` that matter for rules: `combat/` (33 files), `co_stats/` (CO modifiers), `copowers/` (148: CO/Super powers and their effects), `power_meter/`, `skills/` (Dual Strike's skill system), `units/`, `weather/`, `map/` (turn flow, battle setup, scoring, Design Room), `ai/` (445), `silo/`, `campaign/`, `script/`, `event_queue/`, `text/`, `menus/`, `link/`, `rng/`, `math/`, `sound/`.

## 3. Finding a rule

Function names are descriptive and files are one function each, named in snake_case (`combat/scale_chart_damage.c` defines `ScaleChartDamage`). Search the file names first, then bodies.

| To find | Look in | Notes (verified by reading the C) |
|---|---|---|
| Damage chart lookup | `combat/scale_chart_damage.c`, `units/unit_type_get_chart_damage.c`, `combat/damage_chart_get_column.c`, `combat/unit_get_chart_damage.c` | `damage = chart[weapon][column] * firepower / 100`; a weapon that can hit always deals at least 1 |
| Full damage with luck | `combat/combatant_calc_damage.c` (`Combatant_CalcDamage`) | `defense += terrainDefense * shownHp / 10` (cap 200); counter attacks scale by `Combatant_GetCounterBonus`; then `+ rand % goodLuck - rand % badLuck`; luck rolls only when `rollLuck` or `luckOnRequestOnly == 0` |
| Damage preview vs a target kind | `combat/combat_calc_damage_to_target.c` | no luck; `damage * shownHp / 10`; primary weapon when ammo, else secondary |
| Shown HP | `combat_calc_damage_to_target.c` macro `SHOWN_HP`: `(hp - 1) / 10 + 1`, 0 when hp 0 | |
| Defense | `combat/unit_get_defense.c`, `co_stats/player_get_defense_bonus.c`, `co_stats/player_get_co_defense.c` | `100 + owner's defense bonus` |
| Terrain stars | `skills/unit_get_terrain_stars.c` | stars*10 minus the enemies' front CO's `terrainStarCut` x10, floor 0; air units 0 |
| Firepower | `co_stats/player_get_co_firepower.c`, `player_get_firepower_bonus.c`, `player_get_tag_firepower.c`, `skills/firepower_increase.c`, `skills/terrain_firepower.c`, `skills/tower_firepower.c` | CO bonus = skills + Com Tower firepower + `statRows[unitClass]` (+ the combat-class row for non-foot) |
| Luck | `co_stats/player_get_good_luck.c`, `player_get_bad_luck.c`, `skills/luck_damage.c`, `bad_luck_damage.c` | |
| Counter bonus | `combat/combatant_get_counter_bonus.c`, `skills/counter_first.c` | |
| CO power / Super / Tag | `copowers/can_use_co_power.c`, `can_use_super_power.c`, `can_use_tag_power.c`, `activate_power.c`, `co_power_cost.c`, one file per effect (`black_wave.c`, `black_storm.c`, `blizzard.c`, `covering_fire.c`, `ex_machina.c`, `market_crash.c`, `gold_rush.c`, `money_multiplier.c`, `airborne_assault.c`, `copter_command.c`, ...) | `CoPowerCost` = CO star charge x `CoRecord.powerStars`. `BlackWave` = `StartPowerDamage(.., 10, 10, ..)`: 1 HP to enemies, 1 HP back to own |
| Power meter charge | `combat/unit_get_charge_for_hp_lost.c`, `player_get_charge_per_hp.c`, `power_meter/` | charge = HP lost x per-HP charge of the unit type (`UnitStats.chargePerHp`) |
| Unit stats | `include/game/unit_stats.h` (struct), table in `Ov000_gUnitStats` | cost/10, ammo, movement, vision, min/max range, fuel, `unitClass`, `moveType`, `chartDamage[2][32]`, `repairTerrain`, `dailyFuel` |
| CO table | `include/game/co_data.h`, `gCoTable` | per CO: three `CoPowerBlock`s (day-to-day, CO Power, Super) with luck, counter bonus, cost percent, capture rate, tower bonuses, terrain star cut, movement charts, `statRows[unitClass]` |
| Fuel/weather | `co_stats/player_get_fuel_rate.c`, `units/unit_get_fuel_used.c`, `unit_get_move_points.c`, `unit_subtract_move_fuel.c`, `weather/` | fuel rate 2 in snow, else 1; Olaf's army 1 with CO effects on |
| Income | `current_player_collect_income.c`, `co_stats/player_*` | adds `players[cur].unk_08` from day 1 on |
| Repair | `co_stats/player_get_repair_hp.c`, `player_get_daily_repair_hp.c`, `co_get_capture_percent.c`, `player_get_capture_rate.c` | `UnitStats.repairTerrain[terrain]` says where a type is repaired |
| Terrain ids | `include/game/terrain.h` | PLAIN 1, RIVER 2, MOUNTAIN 3, WOOD 4, ROAD 5, CITY 6, SEA 7, HQ 8, AIRPORT 10, PORT 11, BRIDGE 12, SHOAL 13, BASE 14, PIPE 15, ... LAB 20 (same kind numbers `online_maps.rs: info` reads from AW2's table: 6, 8, 10, 11, 14, 20) |
| Map data layout | `docs/maps.md`, `include/game/map_header.h` | Header table `Ov000_gMapHeaders`, 0x10D entries x 0xA0 bytes at ov000 0x022DBD28 (matches `ds_maps.rs`) |
| AI | `src/game/main/ai/` (445 files: `ai_build_*`, `ai_unit_*`, `ai_black_bomb_*`, `ai_foot_*`) | used for `ds_ai*.rs` |

## 4. Search patterns

`rg` and `grep -rn` both work; run from the decomp root.

```
rg -n "ScaleChartDamage"                       # who calls / defines a function
rg -ln "luck"  src/game/main                   # files that mention luck
ls src/game/main/copowers | rg -i "storm|wave|rush|crash"
rg -n "addr:0x020e1d2c" config/AWRE/arm9/symbols.txt        # address -> name (from a Rust comment)
rg -n "0x020e1d2c|020e1d2c" src config                       # also names-provenance.csv, relocs
rg -n "UNIT_CLASS_" include src/game/main/co_stats           # how a CO row is picked
rg -n "powerState|POWER_SUPER" src/game/main/co_stats        # per-power modifiers
rg -n "case CO_" src/game/main/copowers                      # per-CO special cases
rg -n "gCoTable\[" src                                       # every reader of the CO table
rg -n "Ov000_gUnitStats\[" src                               # every reader of unit stats
rg -n "struct\s+CoPowerBlock|typedef struct CoRecord" include
rg -n "WEATHER_" src/game/main                               # weather rules
```

Naming conventions: functions `Subject_Verb` in C (`Player_GetFuelRate`, `Unit_GetTerrainStars`), files the snake_case of the name; overlay functions `Ov00N_...` or `func_ov00N_<addr>`; unnamed main functions `func_<addr>`; data `data_<addr>` or `data_ov00N_<addr>`; structs without a known name `Unk_<addr>`. The game state is `data_027c027c->unk_48[data_027c0284]` (`Unk_02080440_48`: players, day, weather, current player, flags like `coEffectsOn`, `luckOnRequestOnly`); the macros `STATE` and `MAP_UNIT_OWNER` hide it.

## 5. Cross-checking against the ROM and against this repo

1. Addresses: Dual Strike's ARM9 loads at 0x02000000 and overlay 0 at 0x022AD560 (`ds_maps.rs`, `ds_pack.rs`). Comments in `tango-gamesupport-aw2/src` cite Dual Strike addresses (e.g. `co_powers.rs`: "Dual Strike's 0x020E1D2C" = `MarketCrash`; `ds_weather.rs`: `Player_GetFuelRate`, `Unit_GetFuelUsed`, `Unit_GetMovePoints`, `SubtractFuel`). Look the address up in `symbols.txt`, then read the C. Overlays 1,2,3,5,6 all load at 0x02350560 (docs/awre-facts.md), so an overlay address is ambiguous without the overlay id: use the `ov00N` symbol names.
2. Tables: read them from the pack, as the app does. `Pack::overlay_at(0, 0x022A_D560, 0x022A_D560 + 0x47A58 + 0x6C*id, 0x6C)` is unit `id`'s `UnitStats` record (0x022F4FB8 = 0x022AD560 + 0x47A58; matches `unit_stats.h` "in ov000 at 0x022f4fb8", 0x6C bytes). `ds_units.rs` documents the field offsets used: cost/10 u32 at +0x0C, move +0x10, ammo +0x11, vision +0x12, range +0x14/+0x15 ... (read the header for the full list). The decomp's `UnitStats` struct is the field-name key; keep `ds_units.rs` and `unit_stats.h` in step if one changes.
3. `cargo run --release -p tango-gamesupport-aw2 --example ds_balance -- <aw2.gba>` with `TANGOAW2_DS_ROM=<nds>` prints every AW2 unit's cost, move, ammo, vision, range, fuel and each damage-chart cell changed by the pack, using the AW2 table (`ds_units::UNITS`, record 0x5C bytes) and the DS table above. Use it to sanity-check a unit-stat claim you took from the decomp (the decomp gives names; this gives numbers).
4. CO rules: `co_powers.rs` implements what is not a number (Ex Machina, Covering Fire, Urban Blight, Kindle's High Society, Sasha, Javier, Eagle). The decomp's `copowers/` and `co_stats/` files are the reference behaviour; `co_new.rs`/`co_roster.rs`/`co_grid.rs` carry the CO tables. When you change one, state the decomp function it mirrors in a comment (existing pattern in `ds_weather.rs`).
5. In-game proof: `tools/aw2test` (`README.md`) runs real battles on the console, e.g. `ctx.attack` checks base damage and weapon the game used against its calculator and both HP losses within the luck range, and the power meters. Run `python3 tools/aw2test/run.py -k <name>` in `ds` mode to check a decomp-derived claim against the pack's rules running inside AW2.
6. Names that tangoAW2 code uses for AW2 (not DS) functions (`Ov006_GenerateRandomMap`, `WorldMap*`, `sub_08044D70`) come from a separate AW2 decompilation ("aw2bhr", credited in `bh_campaign.rs`); it is not the DS decomp and not checked out here.

## 6. Caveats

- DS is not AW2. Unit ids agree for the shared units (`ds_units.rs`: "Dual Strike numbers its units like AW2 (Infantry 1 ... Sub 24)"), but the end of the list differs: the decomp's `UnitType` has Carrier 25 and Oozium 26 (`UNIT_TYPE_COUNT` 27, record 0x6C), while on the AW2 side id 25 is the dived Sub (`ds_balance.rs` `NAMES`, damage rows 26 wide, record 0x5C) and `five/map.py` numbers Carrier and Oozium 26 and 27 (`DS_UNITS`). The DS-only units are Megatank 4, Piperunner 9, Stealth 12, Black Bomb 13, Black Boat 18, Carrier and Oozium. Check `unit_stats.h` before mapping an id from the decomp to tangoAW2 code.
- The decomp is a machine-written matching decompilation: "SLOP" by its own README. Many functions keep placeholder names (`func_XXXXXXXX`), comments can be wrong or hedged ("guess", "probably"), and C is shaped to match bytes ("needed to match" comments). Unconfirmed names are tracked in `docs/issues/0005-names-to-confirm.md` and `0018-rh890-names-to-confirm.md`. Treat a name as a hint and the code body as evidence; when it matters, confirm on the ROM or in-game.
- Fields marked `unk_` or "guess" in headers (for example `UnitStats.ammoCost`, `unk_17`, `CoPowerBlock.unk_0a`) are not understood.
- Several CO effects are not in numbers: they are function pointers in `CoPowerBlock` (`activate`, `affectsUnit`, `unitBonus`, `calcBonus`). Read the pointed-to function, not just the table.
- Skill-system code (`skills/`) is Dual Strike's equipped-skill mechanic (Set Skills); AW2 has no equivalent. tangoAW2 implements its own (`co_skills.rs`, `skills_panel.rs`).
- Rule results depend on game flags in the state (`coEffectsOn`, `luckOnRequestOnly`, map rules, campaign map ids that cut damage to 1: `Mission_HasPendingEvent`). A formula read from one function may be bypassed by those; check the callers.
- Do not copy code or tables from the decomp into this repo's committed files as data. The decomp is CC0, but the tables are the game's data and come from the user's ROM at run time (repo rule: nothing from the games is committed).
- The decomp checkout is on branch state `49036f5` ("Name the ov001 scripts that map headers point to") at the time of writing; names and file paths may move.
