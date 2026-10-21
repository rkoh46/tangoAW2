# The Dual Strike pack: conversion, gating, mixed rooms

Rule: nothing from either game is committed. AW2's ROM is the console; Dual Strike content is read at run time from the player's own Dual Strike (USA) `.nds`, kept in a "pack" file next to the ROMs. Everything below is in `tango-gamesupport-aw2/src` unless a path says otherwise.

## 1. Building and storing the pack (`ds_pack.rs`, `ds_art.rs`, `tango-library/src/rom.rs`)

| Item | Fact | Where |
|---|---|---|
| Accepted ROM | Dual Strike (USA) only: game code `AWRE` at header 0x0C and header CRC16 `0xB586` at 0x15E | `ds_pack::is_supported_rom`, `HEADER_CRC` |
| Built from the ROM | ARM9 image (at 0x02000000, uncompressed in this ROM), every overlay by id (from the overlay table at header 0x50, file id at entry+0x18, 32-byte entries), every file-system file by path (`bmap/015`, `battle/0dd`, ...) except the `data/` directory; from the 18 MB `data/sound_data.sdat` only the files `ds_music::keep` selects (new COs' themes with instruments/samples, heal sounds, DS Campaign songs, staff roll stream, tag screens' sounds, power themes), stored as `sound/seq/...` etc. | `ds_pack::from_rom`, `SKIPPED_DIRS`, `SOUND_ARCHIVE` |
| In memory | `static PACK: OnceLock<Pack>`; `Pack { arm9, overlays, files }`; accessors `file(path)`, `arm9_at(addr,len)`, `overlay_at(id, base, addr, len)` (DS addresses; overlay 0 loads at 0x022AD560) | `ds_pack.rs` |
| Saved file | `Dual Strike pack.tangoaw2` (`CACHE_NAME`) written next to the ROM by the library scan so the `.nds` is needed only once. Format: magic `TAW2DSPK`, u32 version, u32 entry count, then entries (u16 name length, name, u32 length, data); names `#arm9`, `#ov<i>`, then files sorted by name | `ds_pack::encode/decode`, `tango-library/src/rom.rs: scan_roms` (`storage.write(&to, &data)`) |
| Versions | `VERSION = 7` (3 heal sounds, 4 DS Campaign songs, 5 staff roll stream, 6 tag screens' sounds, 7 power themes); `OLDEST = 3`. An older saved pack is still used (`OLDER`, `ds_pack::outdated()`), what it lacks falls back to AW2's own or is silent; if a `.nds` is in the folder it is rebuilt from it. The scan logs a warning when the pack is outdated and there is no `.nds` | `ds_pack.rs`, `rom.rs` |
| Offering | `ds_art::offer(buf)` is called for every file of the ROMs folder: a saved pack (`Offered::Import`), the 0.2 art file (magic `TAW2DSOB`, `Dual Strike Black Obelisk art.tangoaw2`), or a Dual Strike ROM (`Offered::DsRom{imported}`). `ds_art::art()` and `ds_pack::pack()` also read `TANGOAW2_DS_ROM` when nothing was offered (tests and examples) | `ds_art.rs`, `ds_pack.rs` |
| Art extracted | Black Crystal, Black Obelisk (and a small panel version), Black Cannon facing north, from `bmap/015` (LZ10, 20224 bytes) and palette `bmap/00e` | `ds_art::extract`, `Art` |
| Test | `a_real_rom_builds_a_pack` (ignored; `TANGOAW2_DS_ROM`), `a_pack_round_trips` (always); `tango-library/tests/ds_pack_update.rs` (ignored; needs `TANGOAW2_DS_ROM` and `TANGOAW2_OLD_PACK`) and `ds_pack_update_no_nds.rs` | |

`tango_library::ds_pack_present()` tells the UI whether the pack exists (the tilt setting is offered only then). `tango_library::shared_content_flag()` returns `tango_net_protocol::control::SHARED_CONTENT` (0x80) when `ds_pack::pack().is_some()`.

## 2. The shared-content bit (gating)

Two bits with the same value:

- `tango_net_protocol::control::SHARED_CONTENT = 0x80` (the lobby's name), in the match subtype (`match_type.1`).
- `ds_art::SHARED_ART = 0x80` ("bit 7 of the match subtype: set when both netplay peers have the Dual Strike pack; replays record it").
- `online::ONLINE_MATCH = 0x01`, `UNRANKED_MATCH = 0x02`, `UNRANKED_PICK_GUEST = 0x04` are the other subtype bits (`online.rs`); `ROOM_HOST` is another of `control`.

How the bit gets set (`tango-lobby/src/room.rs`, host side when the match starts): `all_content = params.content && every peer.content`; if true, `match_type.1 |= SHARED_CONTENT`. Each client's `content` comes from `tango_library::shared_content_flag() != 0 && TANGOAW2_NO_CONTENT unset` (`tango/src/app/online.rs`: `lobby_pack`, settings build). The compat check ignores the flag when comparing match types (`tango-lobby/src/compat.rs` test `shared_content_flag_is_not_part_of_the_match_type`). The lobby browser only lists rooms with equal content flag and game version to each other (`tango-lobby/src/browse.rs`). Resuming a saved match whose subtype has the bit refuses a joiner without it: "This match needs the Dual Strike pack." (`room.rs: resume_refusal`).

How the console reads it (`pvp.rs: before_tick`, run every frame on every console):

```
ds_features = ds_art::features(mode)       // mode Some((_, subtype)): subtype & SHARED_ART != 0 ; None (alone): art().is_some()
core.raw_write_8(ds_art::ART_ON /*0x0203FFA5*/, ds_features as u8)
ds = ds_pack::features(mode)               // same rule, with pack().is_some() when alone
```

Every DS module is then called with `ds` (and several with `ds && ds_features && mode.is_none()`, i.e. offline only). So gating is: alone, your own files; in a match or replay, the match's bit. `ART_ON` is a byte of the console, equal on every peer: "the match's bit, not this player's files". The text of the `before_tick` comment: "a mixed room plays the console without it everywhere".

Modules switched per frame in `before_tick` (non-`ds_` prefix, all take `ds`): `survival::tick_tables` (DS unit stats and damage chart with `ds && ds_features`), `five_map::show_maps` (maps with Crystal/Obelisk need `ds_features`; maps with DS content also need `ds`), `roster`, `co_roster`, `co_new`, `co_grid`, `co_powers`, `crumb`, `map_anim`, `unit_actions`, `cpu_tactics`, `tag`, `mode_menu`, `design_bar`, plus the `ds_*` modules below. Online match setup (`online.rs: before`) reads `ds_pack::features(mode)` for the room's lists.

## 3. Mixed rooms (peers with and without the pack)

- The room decides once: if any peer lacks the pack, the bit is not set and EVERY peer runs the console as the no-pack game (same tables, same lists, same maps). A peer that does have the pack keeps it loaded (`pack()` is `Some`) but all gates read the match's bit, so the simulation cannot differ.
- Lists: the room's map lists contain DS maps only when the bit is set (`five_map::show_maps(core, ds_features, ds, ...)`, `online_maps`); see `maps.md`.
- Test: `tools/mixed_pack_check.sh <aw2.gba> <ds.nds> <script.txt> [out-dir]` runs one `aw2_room_teams` script twice (peer WITH the pack in a match that lacks it: `TANGOAW2_DS_ROM` + `AW2_PACK_ONLY=1`; and a peer without the pack), each with `AW2_HASH_LOG`, and compares the per-tick hashes (IWRAM, EWRAM; every 30 ticks ROM, VRAM, palette, OAM). Prints the differing regions and `EQUAL`/`DIFFERENT`; exits 1 if different. In the harness `shared = ds && AW2_PACK_ONLY unset` sets `SHARED_ART` in the match subtype (`aw2_room_teams.rs`).
- Live check: give one client `TANGOAW2_NO_CONTENT=1` (or no pack) in a room and compare `hash` lines in `state_s<k>.jsonl` (`env-aids.md`).
- Without the pack the game runs byte-identical to older versions (`docs/AW2.md`, "The Dual Strike pack"; comparison battery in `CONTRIBUTING.md` / `tools/aw2test` `compat_aw2_byte_identical`, enabled by `AW2TEST_COMPARE_RUNNER`).

## 4. What is read at run time vs what is committed

| Committed in the repo | Read from the user's ROMs at run time |
|---|---|
| Code, tables of ROM addresses/offsets, generated text of OUR maps (`five_map_data.rs`: tangoAW2's own map layouts, not AW2's), generated sprite plans (`ds_plans.rs`, a terrain-tile-to-sprite-parts table made by `tools/aw2test/ds_view_props.py`), the tangoAW2-drawn terrain-panel names (`obelisk_art.py` -> `src/obelisk_art.rs`), the Teams screen's "5P" and "E Team" labels (`five/art.py` -> `five_art.rs`) | AW2 `.gba` (the console itself; patches are applied in memory by `five.rs`, `five_map.rs`, ... after verifying the original instruction at each address); Dual Strike `.nds` (-> the pack file next to the ROMs): maps, units, CO art, music, campaign data, HUD graphics, unit art, Crystal/Obelisk pictures, weather rules, tables |

`tools/aw2test` tests also say it: "Nothing from the games is kept in the repo: tables are read at run time from your ROMs" (`tools/aw2test/README.md`).

## 5. The `ds_*.rs` modules (one line each)

| Module | Role |
|---|---|
| `ds_pack` | Builds, saves, loads the pack; the `features(mode)` gate |
| `ds_art` | Crystal/Obelisk/cannon art import; `offer`, `SHARED_ART`, `ART_ON`, `features`, `active` |
| `ds_ai`, `ds_ai_build`, `ds_ai_move`, `ds_ai_power` | Dual Strike's CPU in AW2's driver: pass structure and driver hooks; production (phase A); power use (B); threat maps and threat-aware moves (C, D). See `docs/AW2.md` "Dual Strike's CPU" |
| `ds_backdrop` | DS battle backgrounds (Piperunner, Wasteland, pipes, Com Towers) |
| `ds_battle` | DS battle animations for the seven new units (muzzle flashes, shells, hits, explosions) |
| `ds_campaign`, `ds_campaign_data`, `ds_campaign_rules` | The DS Campaign: engine integration; converts missions, maps, deployments, event scripts, texts from the ROM at run time; Rust versions of DS's script conditions/actions (via magic stubs) |
| `ds_co_art` | DS CO pictures converted into AW2's CO presentation formats |
| `ds_co_page`, `ds_co_wall` | DS-style CO info page and the wall/crest background behind it (offline, with the graphics setting) |
| `ds_coselect` | DS CO selection screens (Teams screen cards, SELECT CO grid), offline |
| `ds_credits` | The DS Campaign's staff roll after the last mission |
| `ds_cursor` | DS battle-map cursor and target ring for the tilted map |
| `ds_graphics` | "Dual Strike graphics" preview mode (setting; `TANGOAW2_DS_GRAPHICS=1` for tests) |
| `ds_ground` | Battle-map ground drawn from game state (for the look/tilt) |
| `ds_hud` | DS battle HUD (CO panel, terrain/unit panel) with GBA sprite hardware |
| `ds_look` | DS map looks (Wasteland, Desert, Snow) from DS terrain graphics |
| `ds_maps` | Reader for any DS map id (map header table at overlay 0 `0x022DBD28`, 0xA0 bytes per id): look, weather, fog, armies, case, tiles, units, COs, colours, teams |
| `ds_menus` | DS unit command menu and map menu on the GBA screen |
| `ds_music` | New COs' themes, power themes, DS Campaign songs: converts DS sequences to AW2's MP2K engine; chooses what the pack keeps |
| `ds_plans` | GENERATED table: terrain tile id -> sprite parts the console draws for it (for the tilt) |
| `ds_power_art` | DS's map animations for the new COs' powers (OBJ tiles, palettes, frames, BG layers, screen effects) |
| `ds_story_art` | DS narration pictures behind the world map's narration |
| `ds_tilt` | "Dual Strike tilt": display-only 3D-plane look of the battle map; many `TANGOAW2_TILT_*` aids |
| `ds_unit_art` | Map-unit pictures of the seven units AW2 lacks |
| `ds_unit_pictures` | Big unit pictures in the build menu and unit info screens |
| `ds_units` | DS unit stats and damage chart for AW2's own units (cost, movement, ... applied with the pack) |
| `ds_versus` | DS's Versus and War Room maps in a separate 0x100-id map table (`TABLE`), when the pack is on and Survival is not open |
| `ds_weather` | DS weather rules (snow/rain stop slowing units; snow doubles fuel use ...) |
| `ds_worldmap` | The DS Campaign's world map: AW2's `WorldMap*` procs run on DS's Omega Land |

DS-content modules not prefixed `ds_`: `survival.rs`/`survival_maps.rs`/`survival_ui.rs` (Survival and Champion courses), `co_new.rs` + `co_roster.rs` + `co_grid.rs` + `co_powers.rs` + `co_skills.rs` (the new COs, their powers, skills), `crumb.rs`, `tag.rs`/`tag_*.rs` (CO tag pairs), `roster.rs`/`unit_names.rs`/`unit_actions.rs` (the seven new units), `map_anim.rs`, `oozium.rs`, `onyx.rs`, `volcano.rs`, `wasteland.rs`, `sandstorm.rs`, `com_tower.rs`, `grand_bolt.rs`, `two_front.rs`, `setup_phase.rs`, `cpu_tactics.rs`, `cpu_inventions.rs`. Each is switched through `ds` in `before_tick`; open the file header for its own doc.

## 6. Dev workflow

- Use the ROMs in `~/Documents/TangoAW2/roms/` (the default of `tools/aw2test/aw2test/paths.py`): `Advance_wars_2.gba` and `Advance Wars - Dual Strike (USA).nds`. For examples set `TANGOAW2_DS_ROM=<nds>`; unset it to run "without the pack".
- In the app, dropping the `.nds` into the ROMs folder is enough; after the first scan `Dual Strike pack.tangoaw2` appears and the `.nds` can go.
- After changing what the pack keeps, bump `VERSION` in `ds_pack.rs` (older packs are rebuilt from the `.nds` on the next scan).
- Checks: `cargo test -p tango-gamesupport-aw2 --lib`; `TANGOAW2_DS_ROM=<nds> cargo test -p tango-gamesupport-aw2 -- --ignored` (real-ROM tests); `python3 tools/aw2test/run.py` (runs each test in `aw2` and `ds` modes); `tools/mixed_pack_check.sh` for the mixed-room invariant.
