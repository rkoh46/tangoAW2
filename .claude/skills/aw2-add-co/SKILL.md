---
name: aw2-add-co
description: Add a custom CO: its data file, lettered portrait options composed from the ROMs' parts plus our overlays, balance against AW2's stars, Tag Powers; then the engine side (co_new.rs, crumb.rs).
---

Read docs/dev/co-kit.md first. The worked engine example is Crumb (`co_new.rs`, `crumb.rs`, `crumb_art.rs`); the data-first example is Emerald Sun's four (`tango-gamesupport-aw2/cos/`).
1. Write `tango-gamesupport-aw2/cos/<id>.toml` (copy `klaus.toml`): name, army, role, `stars`, `[d2d]`, `[cop]`, `[scop]`, quotes, theme; list the Tag Powers in `cos/tags.toml` (every pair of the army).
   Compare the stars with AW2's own: `aw2dev co check` prints the nearest AW2 COs; keep the CO Power 2..5 and the Super Power (in all) 5..10.
2. Portrait (original art, the way to go): write designs in `colib/designs.py` (heads and bodies from `heads.py` / `bodies.py`, new garments or props go in `bodies.py`), `aw2dev co portrait draw|layers|lint|sheet`; the lint fails a design too like any one AW2 / Dual Strike CO or over 15 colours. LOOK at the sheet (it has the real COs beside). The older donor-recipe route below was rejected by the user as "just a recolour".
   Old route: `aw2dev co portrait donors` and `aw2dev co portrait palette aw2:<donor>` to choose bases and indices, write 4 to 6 `[[portrait.option]]` (letters A..F) with `ramp` and overlays,
   then `aw2dev co portrait options <id> --out <sheet.png>` and LOOK at it (large figure, faces, small face, HUD face). Show the sheet to the user; set `[portrait] chosen = "C"` only when they pick.
   New overlay art goes in `cos/art/*.toml` (original pixel art only; never copy a picture from another game or from AWBW).
3. `aw2dev co check`, `aw2dev co portrait check`, `aw2dev test` (runs `aw2.colib.test_co`), `aw2dev kit check`.
4. Engine work after the data is approved (not part of the data kit): a CO id after `co_new::CRUMB`, its presentation row from the chosen recipe (`crumb_art.rs` shows how a composed figure becomes the
   128 x 160 body, the 48 x 48 faces, the mini and the HUD face), texts, powers' effect on each unit (`crumb.rs` `each_unit`, `bonus`), its CO table row (`co_roster.rs`), Tag data (`sturm_pairs.rs`),
   a regression test in `tools/aw2test/tests/test_all_cos.py`, `ram_map.rs` for new state, `sim_version` when the sim changes.
