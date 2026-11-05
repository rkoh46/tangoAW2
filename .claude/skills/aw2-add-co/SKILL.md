---
name: aw2-add-co
description: Add a custom CO: its data file, its supplied portrait imported into AW2's CO art (figure, mug, mini, HUD face, expressions, name), balance against AW2's stars, Tag Powers, a look at it in the real game; then the engine side (co_new.rs, es_cos.rs, crumb.rs).
---

Read docs/dev/co-kit.md first. The worked engine example is Crumb (`co_new.rs`, `crumb.rs`, `crumb_art.rs`); the data-and-art-first examples are Silver Nova's three (`tango-gamesupport-aw2/cos/`, `es_cos.rs`; Tabitha has only a Super Power, Lili only a CO Power: `stars = { cop = 0 | scop = 0 }`).
1. Write `tango-gamesupport-aw2/cos/<id>.toml` (copy `tabitha.toml`): name, army, role, `stars`, `[d2d]`, `[cop]`, `[scop]`, quotes, theme, and `[portrait] source = "art-src/cos/<id>_v1.jpg"`
   (the one data line of the picture-to-CO mapping). List the Tag Powers in `cos/tags.toml` (every pair of the army). Compare the stars with AW2's: `aw2dev co check` prints the nearest AW2 COs
   and the name plates; `aw2dev co balance <id>` the averages against Dual Strike's COs. Keep the CO Power 2..5 and the Super Power (in all) 5..10.
2. Portrait: the picture is supplied by the owner (never draw, compose from donors, stylise or recolour AW2's COs: the user rejected all of them). Put it in `art-src/cos/<id>_v1.jpg`; if it is pixel art run
   `aw2dev co portrait grid art-src/cos/<id>_v1.jpg [--flip]` and look at the numbered debug picture, then write the framing file beside it (`<id>_v1.toml`: `pixelart = true`, `flip` (the CO must face right),
   `frame = [x, y]` (optional, the 64 x 80 cell frame), `mug = [x, y]` (a 24 x 24 cell square of the head), `eyes = [x1, y1, x2, y2]`, all in native cells of the mirrored grid), then
   `aw2dev co portrait import <id>`, `aw2dev co portrait lint`, `aw2dev co portrait sheet <id>` and LOOK at it beside the real COs (large figure 1x and 2x, faces, strips) and in the game
   (`aw2dev co portrait ingame <id>`). Credit it in `CREDITS.md` ("portrait art provided by the project owner").
3. Engine: an id in `co_new.rs` (see `ES_FIRST`), its art and texts in a module like `es_cos.rs` (the PNGs become tile data through `crumb_art::body_files` / `Px::to_tiles`), a regression
   test, `ram_map.rs` for new state, `sim_version` when the sim changes. Then `cargo build`, `aw2dev build`, and `aw2dev co portrait ingame <id>`: it photographs the CO on the game's own screens
   through the AI debug channel (CO select, HUD, the Power's dialogue box and cut-in, the CO page) and checks they show the committed art.
4. `aw2dev co check`, `aw2dev co portrait lint`, `aw2dev test` (runs `aw2.colib.test_co`), `aw2dev kit check`.
5. Verify every ability in real battles: add the CO's numbers to `tools/aw2test/aw2test/cospec.py` (the specification, from the data file), its name to `COS` in `devkit/aw2/colib/verify.py` and `NAMES` in `tools/aw2test/tests/test_co_verify.py` (a CO with only a Super Power goes in `NO_COP`, one with only a CO Power in `NO_SCOP`; a power with a special rule needs a `hook_*` scenario in `coverify.py`, like `hook_firestorm` or `hook_enigma_*`, and a determinism run in `test_es_powers.py`),
   then `aw2dev co verify <id>` (attack, defence, move, range, cost, income, funds, heal, the special rules, meters, Tag Powers, CPU use; `--net` plays each power on two real clients) and fix what the table says FAILs.
   `aw2dev co sheet powers <id>` makes the real-game pictures (select card, CO page, HUD, each power and Tag Power, the effect): look at every one. docs/dev/co-verify.md.
6. A CO whose picture is a clean illustration (not pixel art): `illustration = true` in `art-src/cos/<id>_v1.toml` (docs/dev/co-kit.md, "The illustration import"); find the frame, the mug and the eyes by looking at `devkit/work` previews, never draw. A CO with a terrain cut (Sonja's block, Asuka) needs nothing for the terrain panel: it prints the stars after the cut (`co_roster::panel_stars`), test `asuka_terrain_panel_shows_the_cut_stars` is the template. A CO built from existing pieces (Asuka: Sonja's Dual Strike block + Hawke's power procedures) needs no new engine code beyond `co_new.rs` (id, `all()`, `like`, `is_own`), `co_roster.rs` (`ds_co`, the power words, the stars), `es_cos.rs` (art + texts table), `ds_co_page.rs` (page texts), `sturm_pairs.rs` (pairs), a song in `es_music::SOURCES`, `tools/aw2test/tests/test_asuka.py` as the template for proving every ability with numbers, and a bump of `inspect::SIM_VERSION`. A CO with only a Super Power and an Orange Star look (Aria, docs/dev/aria.md): `stars.cop = 0`, her row copies Nell's style bytes and Sturm's CPU settings, `ds_ai::template_of` Von Bolt's profile, and a picture on a baked-in checkerboard background needs the pixel-art mode's `checker` options.
7. A rule players cannot see (Aria's Vengeance) gets a sign: docs/dev/aria.md "The signs" (`aria_sign.rs`: a ramp on the map's HP numbers in a borrowed BG palette bank and BG tiles, a strip on the unit window and above the damage forecast from the window's own letters), proved by `tests/test_aria_vengeance_signs.py` against a twin game (the same scene with another CO) and the review sheets of `python3 -m aw2.colib.vengeance_signs_sheet` (look at them before showing anyone).

## Writing a CO's voice
The owner provides the reference personalities (`tools/estext/BIBLE.md` holds Caulder, Lili and Tabitha's; add the new CO's there when the owner gives it). Read it before writing any line. Write original lines in that voice; use a signature quote rarely (a CO who says it every scene is a parody). Then `./aw2dev campaign text-lint all`.

## Worked example: Caulder, start to finish (docs/dev/co-kit.md "Worked example")
1. `cos/caulder.toml` from `tabitha.toml`; the owner's picture `art-src/cos/caulder_v1.jpg` with `caulder_v1.toml` (fields: `flip` = mirror so the CO faces right, `mug` = the 24 x 24 head square, `eyes` = the four-number eye box, `keep_off` = cells the importer must not clean; `pixelart` / `illustration` mode).
2. `./aw2dev co portrait import caulder` -> `lint` -> `sheet`; if the figure faces the wrong way set `flip` and re-import (the faces mirror with it: that was the mirroring fix).
3. Engine ids and texts (`co_new.rs` / `es_co.rs`, `es_cos.rs`, `ds_co_page.rs`, music slot), `./aw2dev co check`, `./aw2dev co verify caulder`.
4. In the game: `./aw2dev co portrait ingame caulder`, then `./aw2dev co consistency caulder` (one sheet: art + CO select, HUD, CO page, dialogue; a CO that leans opposite ways is mirrored on one picture only).

## Checklist (ends with the face checks)
- [ ] data file, picture imported, lint clean, sheet looked at beside real COs
- [ ] powers verified (`co verify`), page texts, music slot
- [ ] `./aw2dev co consistency <co>` looked at: same direction on every screen
- [ ] `./aw2dev gauntlet faces --map NN` (the dialogue-box face beside the army screen) when a Gauntlet map uses the CO
- [ ] `./aw2dev campaign scene-check` (the face keeps its own palette in scenes) and `./aw2dev campaign text-lint all`
- [ ] `./aw2dev kit check`, `./aw2dev test`
