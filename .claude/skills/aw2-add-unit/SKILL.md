---
name: aw2-add-unit
description: Add or change a unit (stats, damage rows, art, rules like the Oozium's eating) in tangoAW2; no dedicated aw2dev tool yet, so this lists the code, the tests and the checks to use (planned kit command)
---

Status: **planned kit**. There is no the planned unit kit command command yet; the first real unit feature adds it (devkit/CONTRIBUTING-KIT.md). Until then:
1. Stats and damage rows: AW2's units are numbered Infantry 1 .. Sub 24; with the Dual Strike pack each takes Dual Strike's cost, move, ammo, vision, range, fuel and its two damage rows as one set (`ds_units.rs`, docs/dev/ds-pack.md); names in `unit_names.rs`; commands in `unit_actions.rs`. Never edit one number alone: the damage chart is a matched set.
2. Art: `ds_unit_art.rs` / `ds_unit_pictures.rs` (read from the Dual Strike pack at run time, never committed); army colours of a unit go through the five-army palettes (`-k five_unit_palettes`) and the army skins (skill aw2-add-army).
3. Rules that are not numbers (the Oozium eats instead of fires: `oozium.rs`; the CPU's use of transports: `cpu_units.rs`, docs/dev/cpu-unit-use.md) get a module of their own, a regression test in `tools/aw2test/tests/` (`test_oozium*.py`, `test_cpu_unit_use.py` are the models) and a `sim_version` bump (`inspect::SIM_VERSION`) when both peers must agree.
4. Checks: `./aw2dev test`, `python3 tools/aw2test/run.py -k units`, `-k unit_audit`, `-k unit_pictures --mode ds`; look at the pictures. `./aw2dev audit text` for new names.
5. Grow the kit: add the the planned unit kit command command (stats table vs Dual Strike's, pictures in the five armies) and rewrite this skill around it.
