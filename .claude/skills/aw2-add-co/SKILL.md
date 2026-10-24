---
name: aw2-add-co
description: Add a custom CO: its data file, its supplied portrait imported into AW2's CO art (figure, mug, mini, HUD face, expressions, name), balance against AW2's stars, Tag Powers, a look at it in the real game; then the engine side (co_new.rs, es_cos.rs, crumb.rs).
---

Read docs/dev/co-kit.md first. The worked engine example is Crumb (`co_new.rs`, `crumb.rs`, `crumb_art.rs`); the data-and-art-first example is Emerald Sun's four (`tango-gamesupport-aw2/cos/`, `es_cos.rs`).
1. Write `tango-gamesupport-aw2/cos/<id>.toml` (copy `klaus.toml`): name, army, role, `stars`, `[d2d]`, `[cop]`, `[scop]`, quotes, theme, and `[portrait] source = "art-src/cos/<id>_user.jpg"`
   (the one data line of the picture-to-CO mapping). List the Tag Powers in `cos/tags.toml` (every pair of the army). Compare the stars with AW2's: `aw2dev co check` prints the nearest AW2 COs
   and the name plates; `aw2dev co balance <id>` the averages against Dual Strike's COs. Keep the CO Power 2..5 and the Super Power (in all) 5..10.
2. Portrait: the picture is supplied by the owner (never draw, compose from donors or recolour AW2's COs: the user rejected all three). Put it in `art-src/cos/`, write its framing file beside it
   (`<id>_user.toml`: scale, crop_top, top, face = [x, y, side], eyes = [x1 y1 x2 y2], mouth = [x y] in the picture's pixels; `palette` = 15 hex colours in AW2's layout (1 white, 2..6 skin, 7..14 the CO's, 15 outline), `lift`, `contrast`, and `[[zone]]` polygons that keep the skin tones on the skin and the hair's on the hair: look at the picture with a grid, draw the polygons, check with an overlay), (current route: `[[material]]` rules + `[[region]]` polygons + `[variant.A/B/C]` palettes, see docs/dev/co-kit.md "The cel route"; `aw2dev co portrait options <id>` shows the choices, `import --variant X` writes one) then `aw2dev co portrait stylise <id>` (AW2-style redraw: the palette, the lift and the zones in that file decide how it looks), `aw2dev co portrait lint --style aw2`,
   `aw2dev co portrait sheet --style` and LOOK at it beside the real COs (large figure 1x and 2x, faces, strips). Credit it in `CREDITS.md` ("portrait art provided by the project owner").
3. Engine: an id in `co_new.rs` (see `ES_FIRST`), its art and texts in a module like `es_cos.rs` (the PNGs become tile data through `crumb_art::body_files` / `Px::to_tiles`), a regression
   test, `ram_map.rs` for new state, `sim_version` when the sim changes. Then `cargo build`, `aw2dev build`, and `aw2dev co portrait ingame <id>`: it photographs the CO on the game's own screens
   through the AI debug channel (CO select, HUD, the Power's dialogue box and cut-in, the CO page) and checks they show the committed art.
4. `aw2dev co check`, `aw2dev co portrait lint`, `aw2dev test` (runs `aw2.colib.test_co`), `aw2dev kit check`.
