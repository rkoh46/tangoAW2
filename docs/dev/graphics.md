# Graphics integrity (`aw2dev gfx`)

Garbled graphics (a clobbered font, a text-tile cache overflowing, a recoloured unit) was fixed many times by eye. `aw2dev gfx` renders key screens fast with the
offline harness, then DETECTS the damage and helps find its cause. Code: `devkit/aw2/commands/gfx.py` (commands), `devkit/aw2/gfxlib/` (decoders, OCR, detectors,
renderer), catalogue `devkit/gfx/catalogue.toml`. Nothing from the game is committed: the font is read from your ROM at run time (cached under
`~/.aw2dev/cache`), golden frames are rendered locally (`~/.aw2dev/golden`).

## Commands
| Command | What |
|---|---|
| `aw2dev gfx catalogue` | the screens, variants and checks |
| `aw2dev gfx check [--screen S ...] [--env K=V] [--binary-dir DIR]` | render the screens (harness, a few seconds each), run the detectors, print findings, heat-maps / diffs as PNGs; exit 1 on a failure. `--binary-dir` checks another build's examples; `--env` reproduces a bug that has an env switch |
| `aw2dev gfx golden [--from COMMIT] [--tag T]` | reference frames + VRAM dumps from a known-good build (a commit is built in a temporary worktree under `devkit/work/gfx_wt`; EVERY worktree build gets its own target dir `devkit/work/gfx_target/<commit>`, a clone of this tree's `target/` (cargo still rebuilds the crates whose build scripts embed the path, e.g. mgba-sys: a few minutes per new commit): cargo keys workspace crates by path, so a shared target dir reuses another tree's example binaries by mistake) |
| `aw2dev gfx explain SHOT.bmp [--region x,y,w,h] [--bank N]` | decode the shot's `.vram` dump: DISPCNT/BGxCNT, OAM entries (tile, VRAM address, palette) touching the region, BG tiles under it, and images (palette swatches, BG charblocks, OBJ tile sheet) in `devkit/work/gfx/explain_*` |
| `aw2dev gfx blame --screen S --dump NAME [--binary-dir DIR]` | binary search over ticks (`AW2_RAM_DUMP`) for the first tick a guarded VRAM range differs from golden, then the procs logged around it (`AW2_PROC_LOG`) |
| `aw2dev gfx regress [--bug N ...]` | reintroduce each catalogued past bug and require it to be flagged (see below) |
| `aw2dev gfx audit [--modes M,..] [--scenes S,..] [--looks L,..] [-j N] [--out DIR] [--reuse DIR] [--only DET,..] [--binary-dir DIR] [--strict]` | the sweep of EVERY mode in the three looks (below): scenes, detectors, `report.md` + `report.json`, contact sheets; exit 1 on a failing finding |
| `aw2dev gfx check --revert C ...` | check a build of this tree with those fix commits reverted (`src/` conflicts stop with the files named) |
| `aw2dev gfx bisect --screen S --good C --bad C` | builds commits in worktrees (own target dirs; proven on a branch with a planted bad commit: it found it in 2 builds of 5 commits) and finds the first one whose screen check fails; the screen's script/tokens and the harness commands it uses must exist in those commits |
| `aw2dev check RUN --gfx` | frozen windows (identical pictures while the game moves on) and black runs in a live run |
| `aw2dev suite` | runs every catalogued screen too (`FAIL gfx <screen>`); without golden images the golden/tile checks only warn |

First time on a machine: `aw2dev build --examples` then `aw2dev gfx golden` (from a build you trust) then `aw2dev gfx check`.

## Detectors (`devkit/aw2/gfxlib/detectors/`, one module each, auto-discovered; add a module with `NAME` and `run(ctx)`)
| Detector | Checks | Needs |
|---|---|---|
| `text` | OCR of AW2-font strings (glyph shapes matched against the ROM's own font, `gfxlib/font.py`, `ocr.py`) in a region: unknown glyphs, expected strings, every row in a name set (`in_set = "maps"`, names from `aw2_map_audit`) | `text = [{region, ink, in_set / expect, max_unknown}]` |
| `same` | a region is pixel-identical across variants (with / without the Dual Strike pack) | `same = [{variants, region}]` |
| `golden` | each shot against the golden frame, tolerance + heat-map (`golden = {ignore = [[x,y,w,h]]}` skips an animated region) | a golden set |
| `tiles` | tile guard: byte ranges of VRAM (font, UI) equal the golden dump; lists the overwritten tiles and the OAM entries drawing them | `vram = true`, `guard = [{dump, range}]`, golden |
| `palette` | palette banks equal golden; and the harness's own colour check (`unitcolours` exit code) | `palette = {rc, banks}` |
| `stray` | a region that must be empty (one plain colour within `dist`) | `stray = [{region, dist, tolerance}]` |
| `external` | a command whose exit code is a finding (`tools/hud_check.py`, aw2test tests): `external = [{cmd = [...], what}]`, `{dump}` `{out}` `{repo}` substituted | the command |
| `frames` | black frames and runs of identical frames in a shot sequence | `frames = [{sequence}]` |
A failing exit code of the harness script is always a finding (`harness`). Catalogue extras: `runner = "example"` runs any example that writes BMP/PPM pictures (`exe`, `args`); `script_edit = {insert_before = [{match, lines}], append = [...]}` adds shot lines to a harness script without copying it; `{out}` in an env value is the render dir. Decoders: `gfxlib/vram.py` (`Dump`: palette, 4bpp tiles, DISPCNT/BGxCNT, BG map cells, OAM).
Limits: OCR reads the proportional font (lists, boxes), not the banner's 8x8 bitmap font (guarded by tiles + same + golden instead); the write-watch ("which routine wrote
it") is tick bisection plus `AW2_PROC_LOG`, not a hardware watchpoint (mGBA hooks are not exposed through the harness).

## Past bugs: cause, detector, proof
`aw2dev gfx regress` brings each catalogued bug back (a patch of `src/` in `devkit/gfx/regressions/` applied to a worktree of HEAD with its OWN cargo target dir, or an env switch)
and requires the named screens to produce a failing finding: DETECTED / MISSED. It is the regression test of the detectors themselves (slow: one build per patch). Add a bug: write
the patch (`git revert --no-commit <fix>` in a worktree, keep only `src/`, or edit by hand, then `git diff -- tango-gamesupport-aw2/src > devkit/gfx/regressions/NAME.patch`) and a
`[[bug]]` block (name, what, patch or env, screens).
| Bug | Cause (fix) | Screen / detector | Proof |
|---|---|---|---|
| NEXT TURN / PRESS A banner garbled ("NE RN / ORA TAR / RESS A BUTTO") with the pack | the north Black Cannon art written into the game's font OBJ tiles 989..1022 for the whole battle (`2b4e12a20`, `obelisk::north_swap`; a second case `2266660f9`) | `banner_5p`: `same` plain vs pack, `tiles` guard, `golden`, harness exit | DETECTED (`banner_font_clobber`) |
| SELECT MAP list garbled mid-scroll ("erChannel Ci") | the names' text-tile cache restarted at each redraw / overflowed into the preview tiles (`fb91e6d98`, `44a18b6a0`) | `maplist_scroll`: `text` (OCR: every row a known name, no unknown glyph) | DETECTED (`maplist_text_cache`) |
| units recoloured into the waiting player's palette | only BG palette bank 11 restored; ships use banks 8..15 (`a69b1a9ac`) | `colours_ship_5p`: `palette` (script's `unitcolours`) | DETECTED (`unit_recolour`, env) |
| HUD header in the wrong army colour (fog off) | CO panel called for the wrong army (`1802d5b35`) | `hud_header_2p`: `external` (`tools/hud_check.py` on every tick) | DETECTED (`hud_header`) |
| wrong portraits: Sturm's mug, Von Bolt's mug (the old man in his machine), partner icons on the army page | art crop / palette (`1da361796`, `1e06733a4`, `f686ededb`) | `armysel_faces` (`aw2_armysel_preview`: army page for 2..5 seats, every CO's face): `golden` | DETECTED (`armysel_sturm`, `armysel_von_bolt`) |
| the Rules map-name plate left over the army page / results | plate drawn while the army page finishes (`1ab6c1d05`) | `roulette_5p`: `golden` on the army-page frames `ap1..ap5` | DETECTED (`rules_plate_on_armypage`) |
| stray tile fragments beside the SELECT*MAP logo during the roulette | the roulette's mask left the map picture's pink round the logo (`1ce9534f9`) | `roulette_5p` golden frames `rl1..rl8`, `mapsel_logo` `stray` | NOT reproducible any more: the roulette was redesigned (the plate replaces the title), so reverting only that fix changes nothing; the screens guard the current look |
| a five-army battle's moved-unit grey over the dialogue faces (every face in the player's colour) | `five::moved_palette` wrote BG palette bank 9 while a scene's box was up (`c7104cf5e`) | audit `gauntlet/five_army_arrival`: `palette` (bank 9 is one hue while a box is up) | DETECTED (`five_army_face_palette`, revert) |
| an arrival scene's first box garbled, the later speakers' lines missing | the scene's box opened in the map's window area without the empty box first (`4fae416ef`) | audit `gauntlet/cinder_sea_run`: `text` (glyph cells of the box that are none of the game's glyphs) | DETECTED (`arrival_first_box`, revert) |
| Silver Nova's Infantry/Mech cells striped black and white with the Dual Strike map graphics | the skin's frames were matched against AW2's sheet, never the converted one (`c1fcf2106`) | audit `gauntlet/cinder_sea_run` ds looks: `stripes` | DETECTED (`silver_nova_ds_stripes`, revert; 108 flips against a limit of 100, healthy art measures about 50) |
| the terrain panel on Silver Nova's HQ drawing Black Hole's HQ; CO page tabs of its COs showing Black Hole's box | the panel took the CO's country's HQ, the tabs the CO's country's icon (`c1fcf2106`) | audit `gauntlet/cinder_sea_run`, `cos/pages_and_chart`: `facts` (panel state byte; tab pictures against Black Hole's own COs on the Black Hole colour) | DETECTED (`black_hole_emblem_on_silver_nova`, revert) |
| the game's "has lost" box mixed with a Gauntlet arrival scene's first box after a rout | two dialogue boxes drawing into the same text tiles (fix: the message is left out and the scene opens with its text in a narration box) | audit `gauntlet/cinder_sea_run`, `five_army_arrival`: `text` on the capture frames | DETECTED (`rout_message_over_scene`, revert) |
| Gauntlet's mission card saying MISSION n / MISSION START (the mode has no missions) | AW2's campaign card runs for the Gauntlet too; `gauntlet_card.rs` repaints the word, blanks the number and re-stamps the seal's band | audit `gauntlet/mission_card` (all three looks) next to `bh_campaign/mission_card`; tests `gauntlet_card_*` compare the card's video art with a campaign's | covered by pictures and tests (the campaign cards must stay byte for byte AW2's) |
| volcano eruptions: warning marks before, a plume or boulders missing in a look, the Volcano's own tiles or palette changed | the warning markers (removed, `e90112a6d`), the show's list (`a5ec1f0f0`) | audit `gauntlet/cinder_sea_volcano`, `bh_campaign/ashfall_volcano` (a Tank of each army parked on the day's cells, the show every 6 frames, the landing every 15): pictures to look at; `volcano_art_survives_*` tests guard the tiles and palette | covered by pictures; in the tilt look a volcano on a map's top row (Cinder Sea) has its plume above the screen, the boulders still show |
| black / blank / frozen frames | hand-off, banner or window never redrawn | `aw2dev check RUN --black --gfx`, `frames` detector | covered by checks, not a patch |
| second-front title pink/purple after the CO page (`013dfd8dd`), artifacts on reopening the CO menu | OBJ palette 0 loaded by the CO page | needs a two-front battle: only `tools/aw2test` can build that state (python); a `golden` + `palette` screen there is the way | NOT catalogued |
| move-arrow OBJ tile clash on a second front / Crystal Calamity (`d8f67239f`) | the title and the satellite drew into OBJ tiles inside AW2's effect tiles 0x1CA..0x259 | `tiles` guard on OBJ tiles 0x1CA..0x259 in a two-front battle | NOT catalogued (same reason) |

## Workflow
1. A graphics report: reproduce with the harness (or a live run + `aw2dev sheet`), look at the picture.
2. `aw2dev gfx explain <shot.bmp> --region ...` shows which sprites / BG tiles / palettes draw it; `gfx blame` finds the tick the tiles change.
3. Fix; add the screen (or a check to one) to `catalogue.toml` so it cannot come back: a script (`tango-gamesupport-aw2/examples/*.txt` or aw2_offline_tabs tokens),
   variants, and the detector config; prove it fails on the broken build (`--binary-dir` of a worktree with the fix reverted, or `--env`) and passes on the fixed one.
4. `aw2dev gfx golden` after an INTENDED visual change, from a build you looked at.
Remember false passes: a golden made from a broken build blesses the bug; look at the frames the detector reports.

## The audit (`aw2dev gfx audit`)
The catalogue above guards screens a past bug taught us about. The audit is the other direction: it goes through EVERY mode the way a player does, photographs the screens in each look and runs all the detectors over what it finds,
so a bug nobody has met yet shows up as a finding and a red-framed cell on a contact sheet. Code: scenes in `tools/aw2test/aw2test/audit_scenes.py` (framework `audit.py`, one worker process per scene and look,
`tools/aw2test/audit_worker.py`: they reuse the aw2test drivers of the campaigns, Gauntlet, War Room, Survival, Versus), detectors in `devkit/aw2/gfxlib/audit/detectors.py`, runner, report and sheets beside it, test `devkit/aw2/test_gfx_audit.py`
(`aw2dev test python`).

Looks (the owner's rule: every visual in all three): `aw2` (AW2 graphics, the Dual Strike pack loaded), `ds_tilt` (Dual Strike map graphics with the tilt), `ds_flat` (Dual Strike map graphics, no tilt) and `aw2_nopack` (AW2 alone, for the modes that exist without the pack).
`aw2dev gfx audit --list` prints every scene and the looks it runs in.

| Mode | Scenes (pictures per look in the report) |
|---|---|
| `menus` | title screen (three moments), Select Mode's wheel at every entry |
| `versus` | Teams + Rules, SELECT MAP tabs, `asuka_stars` (the terrain panel's defence number under Asuka's terrain cut: day to day, CO Power, Super Power), battle (terrain, every unit, properties, ships, map menu, CO page 1..4), CO Power and Super Power, battle animations, capture box, fog, rain / snow / sandstorm, Com Towers, five-army map, Silver Nova (units, HQ and its terrain box, battle) |
| `war_room`, `survival` | selector, R records box, CO screen, battle, map menu |
| `aw2_campaign`, `ds_campaign`, `bh_campaign`, `bh2_campaign` (+ the secret M32 and its three waves), `sn_campaign` | world map, mission card, CO screens, Setup phase, intro / arrival / victory boxes (the first box twice: as it starts typing and typed out), first turn, stage switches, win and back on the map |
| `gauntlet` | selector, R records box, army screen (CO and colour), a run on Cinder Sea with Silver Nova: Setup, capture box, rout, arrival scenes |
| `cos` | Asuka, Aria, Caulder, Lili, Tabitha, Clone Andy, Crumb: Teams card, CO page and its chart pages |
| `online` | every in-game ONLINE page (lobby, browser, room, army screen, Unranked, colour pick, stats, waiting view, messages) from `aw2_online_text_audit`, which also does the cut-off-text audit of `aw2dev audit text` (its PROBLEM lines become failing findings) |

Detectors (`DETECTORS` in `detectors.py`; each says what it catches in its docstring; thresholds are named constants at the top):
| Detector | Catches | Needs |
|---|---|---|
| `blank` | a picture of one plain colour (a screen or window that never drew) | the picture; tag `fade` / `blank_ok` excuses |
| `stripes` | black/white stripes in a 16 x 16 window: BG cells drawn from the wrong tiles or palette (the striped Silver Nova Infantry of the Dual Strike look) | the picture |
| `dark` | an enclosed patch of pure black on a map: a black building or unit | the picture, tag `map` |
| `sprites` | an all-zero OAM entry drawing tile 0 at the top-left corner (stray sprite), a scanline over the 1210 OBJ cycles (sprite budget overflow: sprites dropped) | the video dump |
| `palette` | a palette bank the screen draws with that is grey (the moved-unit grey over the dialogue faces' BG bank 9) or has one colour under a face | the video dump |
| `text` | a dialogue-box glyph cell that is none of the game's glyphs: two strings drawn into the same tiles (the garbled first box); ink at the box edge | the picture, tag `dialogue` |
| `copage` | the Dual Strike CO page whose body has no text (the "Existing skills" page with no skills on is empty for EVERY CO, Andy and Sturm too: a warning, so it stays a decision) | `ds_tilt`/`ds_flat` pictures tagged `copage` |
| `leftover` | detailed blocks identical to the previous picture while the rest of a menu screen changed completely (tiles left from the last screen); a warning | consecutive pictures |
| `seams` | tilt only: 1 px dark/bright lines across the tilted map where the plane's tiles do not meet | the picture |
| `tilt` | the tilt's own per-frame logs (`tiltall`): frames left flat, blends showing the flat map, camera checks that failed | `ds_tilt` scenes |
| `facts` | checks a scene makes from the game's memory (the terrain panel on Silver Nova's HQ draws its own HQ picture; Black Hole's CO page tab stays Black Hole's, Silver Nova's shows its sun) | the scene |
| `scene` | the scene itself stopped (a driver could not reach the screen: that screen is NOT covered, the report says which) | |

The report (`<out>/report.md`, `report.json`) has the coverage table (pictures and scene runs per mode and look), every finding with its picture, and the sheet list; sheets are `<out>/sheets/<mode>__<look>_NN.png` (3 x 3 at 2x, the online pages 4 x 6 at 1x),
a failing picture framed red. Exit 0: no failing finding. `--reuse DIR` judges the pictures of an earlier run again after a detector change (seconds). `--binary-dir` runs the scenes on another build's examples (how a regress entry reproduces an old bug).
LOOK at the sheets after every run: the detectors are heuristics, a picture nobody looked at is not covered.

Animated screens: `rec.snap_stable(e, name, tags, region=...)` waits until the region has stopped changing (the world map's CAMPAIGN title flies in letter by letter for about a second: a picture taken in it reads "CAMp" and is no bug) and records a failed fact if it never does. Use it for every screen that animates in.

Adding a screen: write a scene in `audit_scenes.py` (`@scene(mode, name, looks=..., nopack=True)`, drive the game with the aw2test helpers, `rec.snap(e, name, tags)` for each picture, `rec.fact(ok, msg)` for a memory check), run
`aw2dev gfx audit --scenes NAME`, look at the sheet, and keep it if it adds a screen no other scene shows. Adding a detector: a function in `detectors.py` registered in `DETECTORS`, a made-up-picture case in `test_gfx_audit.py`.

Past bugs the audit must catch again (`aw2dev gfx regress` reverts the fix in a worktree and runs the named audit scenes on that build, MISSED if no failing finding): see the `audit = [...]` entries of the `[[bug]]` blocks.
