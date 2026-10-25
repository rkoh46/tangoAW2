---
name: aw2-add-co
description: Add a custom CO: its data file, its supplied portrait imported into AW2's CO art (figure, mug, mini, HUD face, expressions, name), balance against AW2's stars, Tag Powers, a look at it in the real game; then the engine side (co_new.rs, es_cos.rs, crumb.rs).
---

Read docs/dev/co-kit.md first. The worked engine example is Crumb (`co_new.rs`, `crumb.rs`, `crumb_art.rs`); the data-and-art-first example is Emerald Sun's four (`tango-gamesupport-aw2/cos/`, `es_cos.rs`).
1. Write `tango-gamesupport-aw2/cos/<id>.toml` (copy `klaus.toml`): name, army, role, `stars`, `[d2d]`, `[cop]`, `[scop]`, quotes, theme, and `[portrait] source = "art-src/cos/<id>_v5.jpg"`
   (the one data line of the picture-to-CO mapping). List the Tag Powers in `cos/tags.toml` (every pair of the army). Compare the stars with AW2's: `aw2dev co check` prints the nearest AW2 COs
   and the name plates; `aw2dev co balance <id>` the averages against Dual Strike's COs. Keep the CO Power 2..5 and the Super Power (in all) 5..10.
2. Portrait: the picture is supplied by the owner (never draw, compose from donors, stylise or recolour AW2's COs: the user rejected all of them). Put it in `art-src/cos/<id>_v5.jpg`; if it is pixel art run
   `aw2dev co portrait grid art-src/cos/<id>_v5.jpg [--flip]` and look at the numbered debug picture, then write the framing file beside it (`<id>_v5.toml`: `pixelart = true`, `flip` (the CO must face right),
   `frame = [x, y]` (optional, the 64 x 80 cell frame), `mug = [x, y]` (a 24 x 24 cell square of the head), `eyes = [x1, y1, x2, y2]`, all in native cells of the mirrored grid), then
   `aw2dev co portrait import <id>`, `aw2dev co portrait lint`, `aw2dev co portrait sheet <id>` and LOOK at it beside the real COs (large figure 1x and 2x, faces, strips) and in the game
   (`aw2dev co portrait ingame <id>`). Credit it in `CREDITS.md` ("portrait art provided by the project owner").
3. Engine: an id in `co_new.rs` (see `ES_FIRST`), its art and texts in a module like `es_cos.rs` (the PNGs become tile data through `crumb_art::body_files` / `Px::to_tiles`), a regression
   test, `ram_map.rs` for new state, `sim_version` when the sim changes. Then `cargo build`, `aw2dev build`, and `aw2dev co portrait ingame <id>`: it photographs the CO on the game's own screens
   through the AI debug channel (CO select, HUD, the Power's dialogue box and cut-in, the CO page) and checks they show the committed art.
4. `aw2dev co check`, `aw2dev co portrait lint`, `aw2dev test` (runs `aw2.colib.test_co`), `aw2dev kit check`.
5. A CO whose picture is a clean illustration (not pixel art): `illustration = true` in `art-src/cos/<id>_v1.toml` (docs/dev/co-kit.md, "The illustration import"); find the frame, the mug and the eyes by looking at `devkit/work` previews, never draw. A CO built from existing pieces (Asuka: Sonja's Dual Strike block + Hawke's power procedures) needs no new engine code beyond `co_new.rs` (id, `all()`, `like`, `is_own`), `co_roster.rs` (`ds_co`, the power words, the stars), `es_cos.rs` (art + texts table), `ds_co_page.rs` (page texts), `sturm_pairs.rs` (pairs), a song in `es_music::SOURCES`, `tools/aw2test/tests/test_asuka.py` as the template for proving every ability with numbers, and a bump of `inspect::SIM_VERSION`.
