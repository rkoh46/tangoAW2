---
name: aw2-add-army
description: Add a custom army (a skin on one of AW2's five colours, like Emerald Sun) to tangoAW2 as a data file, check it and show it
---

An army is a **skin**: `tango-gamesupport-aw2/skins/<id>.toml` (colours, Infantry/Mech patches, HQ, emblem), compiled into the app and drawn over one of AW2's colours
(docs/dev/army-packs.md has the engine, the tables and the margins). The art must be your own: look at other projects' armies, then draw; never trace or commit their pictures.

1. Copy `skins/emerald_sun.toml` to `skins/<id>.toml` and edit `id`, `name`, `short`, the `[colours]` ramp (light to dark, six), `trim`, `crest`.
2. Add `include_str!("../skins/<id>.toml")` to `FILES` in `tango-gamesupport-aw2/src/army_skin.rs` (at most `MAX_SKINS`; its choice code is `SKIN` + its index).
3. `aw2dev build --all`, then `aw2dev armyskin check`: the palette must keep its margins from AW2's five armies, the done greys and the fog's terrain (thresholds in docs/dev/army-packs.md). Fix the ramp, not the thresholds.
4. Draw while you look: `aw2dev armyskin preview --colour 3 --fast` (art straight from the file, no rebuild); Infantry and Mech patches (`.` keep, `_` clear, hex digit = unit palette index, `e` crest), the HQ (32x16, building palette indices), the emblem (16x16).
5. See it in the game: `aw2dev armyskin scenario units` (and `parade`, `battle`, `power`, `capture`, `turn`, `results`, `lost3p`, `map5p`; `--ds` for `dsunits` and `crumb`); pictures are in `devkit/work/armyskin/scenario_<name>/*.bmp`. LOOK at them.
6. `aw2dev armyskin check --live` must end `bad=0`; `aw2dev armyskin sources` must print nothing (it prints the ROM palettes the skin still leaves in the old army's colours: add them to `TABLES`).
7. Online: `AW2DEV_SKIN=1 aw2dev live moveview --local --fog off` then `aw2dev check latest`; `AW2DEV_SKIN=1 aw2dev live lobby --players 3 --local`. Offline: `target/release/examples/aw2_skin_offline <rom> <out> [cpu]`.
8. Bump nothing by hand: `sim_version` was raised for the feature; a *change of behaviour* of the skin engine raises it again (docs/dev/architecture-online.md).
9. `aw2dev suite` (adds `static` and `live` armyskin checks and the catalogue's golden screens: `aw2dev gfx golden` after an intended look change), `aw2dev test`, `aw2dev kit check`; credit the inspiration in `CREDITS.md`.
