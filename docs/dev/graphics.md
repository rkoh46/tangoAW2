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
| `golden` | each shot against the golden frame, tolerance + heat-map | a golden set |
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
