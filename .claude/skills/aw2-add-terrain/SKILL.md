---
name: aw2-add-terrain
description: Add or change a terrain or structure (Black Obelisk, volcano, pipe seam, Com Tower) in tangoAW2; no dedicated aw2dev tool yet, so this lists the code, tests and checks to use (planned kit command)
---

Status: **planned kit**. There is no the planned terrain kit command command yet; the first real terrain feature adds it (devkit/CONTRIBUTING-KIT.md). Until then:
1. Models: the Black Crystal / Obelisk that heal and can be destroyed (`obelisk.rs`, `obelisk_art.rs`, tests `test_obelisk_breakable.py`, `test_ds_structures.py`); the Com Tower (`com_tower.rs`, `test_com_tower.py`); the volcano and its damage (`volcano.rs`, `test_volcano_damage.py`, `test_ds_volcano_colours.py`); pipe seams (`test_pipe_seams.py`). Each rides on one of AW2's own tile/invention slots, so find a free slot, prove it free, and patch only after verifying the original instruction (docs/dev/rom-routines.md, docs/dev/ram-map.md for any new EWRAM).
2. Art: composed from AW2/DS tiles read from the ROMs at runtime; panel names are drawn by script (`obelisk_art.py` -> `obelisk_art.rs`), never committed game data. Check the three graphics modes (AW2, DS + tilt, DS flat): `tools/aw2test/ds_view_props.py` makes the terrain-to-sprite plans.
3. Maps: the tile needs a legend letter in `five/map.py` / `esmaplib`, a lint rule if it has placement rules (docs/dev/map-lint.md, `aw2dev maps lint`), and a look at the map in the real app (`aw2dev maps boot`).
4. The CPU must know it (`cpu_inventions.rs`) and the test player must not stall on it (`python3 tools/aw2test/run.py -k cpu_inventions`).
5. Checks: `./aw2dev test`, `-k <the terrain's test>`, `./aw2dev audit maps`, pictures in all three looks.
6. Grow the kit: add the planned terrain kit command (a placement sheet in the three looks) and rewrite this skill around it.
