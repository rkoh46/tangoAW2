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
| `aw2dev gfx golden [--from COMMIT] [--tag T]` | reference frames + VRAM dumps from a known-good build (a commit is built in a temporary worktree under `devkit/work/gfx_wt`, target `devkit/work/gfx_target`) |
| `aw2dev gfx explain SHOT.bmp [--region x,y,w,h] [--bank N]` | decode the shot's `.vram` dump: DISPCNT/BGxCNT, OAM entries (tile, VRAM address, palette) touching the region, BG tiles under it, and images (palette swatches, BG charblocks, OBJ tile sheet) in `devkit/work/gfx/explain_*` |
| `aw2dev gfx blame --screen S --dump NAME [--binary-dir DIR]` | binary search over ticks (`AW2_RAM_DUMP`) for the first tick a guarded VRAM range differs from golden, then the procs logged around it (`AW2_PROC_LOG`) |
| `aw2dev gfx bisect --screen S --good C --bad C` | builds commits in worktrees and finds the first one whose screen check fails (slow: one examples build per step; needs the screen's script/tokens to exist in those commits) |
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
| `frames` | black frames and runs of identical frames in a shot sequence | `frames = [{sequence}]` |
A failing exit code of the harness script is always a finding (`harness`). Decoders: `gfxlib/vram.py` (`Dump`: palette, 4bpp tiles, DISPCNT/BGxCNT, BG map cells, OAM).
Limits: OCR reads the proportional font (lists, boxes), not the banner's 8x8 bitmap font (guarded by tiles + same + golden instead); the write-watch ("which routine wrote
it") is tick bisection plus `AW2_PROC_LOG`, not a hardware watchpoint (mGBA hooks are not exposed through the harness).

## Past bugs: cause, and the detector that catches it
| Bug | Cause (fix) | Catalogue screen / detector | Reproduced |
|---|---|---|---|
| NEXT TURN / PRESS A banner garbled ("NE RN / ORA TAR / RESS A BUTTO") with the pack | the north Black Cannon art was written into OBJ tiles 989..1022, the game's font, for the whole battle (`2b4e12a20`, `obelisk::north_swap`) | `banner_5p`: `same` plain vs pack, `tiles` (font OBJ tiles), `golden`, harness exit | yes: fix neutralised in a worktree: 12 findings (32 font tiles overwritten, 3.3-3.9% of pixels differ, harness exit 1); current build passes |
| SELECT MAP list garbled mid-scroll ("erChannel Ci") | the text-tile cache started over at every redraw / overflowed into the preview tiles past ~31 names (`fb91e6d98`, `44a18b6a0`, `ds_versus::list_drawn`) | `maplist_scroll`: `text` (every row must be a known map name, no unknown glyph) | yes: fix reverted: garbled rows flagged ("?ourg?ass ?", "Rail St? -it"); current passes |
| units recoloured into the waiting player's palette | only BG palette bank 11 restored after the waiting view's refresh; ships use banks 8..15 (`a69b1a9ac`, `fog_view::UNIT_BANKS`) | `colours_ship_5p`: `palette` (the script's `unitcolours`), harness exit | yes: `--env AW2_RESTORE_BANKS=11` (the old behaviour) fails; current passes |
| stray tile fragments beside the SELECT*MAP logo during the roulette | tile data left in the plate's area | `mapsel_logo`: `stray` (region beside the plate must be sea) | screen catalogued; the original bug was not reproduced |
| HUD header in the wrong army colour | the waiting view's CO panel called for the wrong army (`c54fa8a49`) | `aw2dev check RUN --hud` (live), `tools/hud_check.py` in the suite; palette banks via `palette` once a screen is catalogued | covered by existing checks |
| black / blank / frozen frames | hand-off, banner or window never redrawn | `aw2dev check RUN --black --gfx`, `frames` | covered |
| second-front title pink/purple after the CO page (`013dfd8dd`), artifacts on reopening the CO menu | palette / tiles left from the CO page | add a catalogue screen for it (`aw2_coselect_preview`-style script) with `golden` + `palette` | not catalogued |
| wrong / garbled portraits (Sturm, Von Bolt mugs, the partner icon palette) | art or palette bank mix-up | same: a screen with `golden` + `palette` banks | not catalogued |
| move-arrow OBJ tile clash | an OBJ tile range used by two features | `tiles` guard on the arrow's tiles + `explain` | not catalogued |
| map name plate left over the results | plate not cleared on the next screen (`1ab6c1d05`) | `stray` on the results screen | not catalogued |

## Workflow
1. A graphics report: reproduce with the harness (or a live run + `aw2dev sheet`), look at the picture.
2. `aw2dev gfx explain <shot.bmp> --region ...` shows which sprites / BG tiles / palettes draw it; `gfx blame` finds the tick the tiles change.
3. Fix; add the screen (or a check to one) to `catalogue.toml` so it cannot come back: a script (`tango-gamesupport-aw2/examples/*.txt` or aw2_offline_tabs tokens),
   variants, and the detector config; prove it fails on the broken build (`--binary-dir` of a worktree with the fix reverted, or `--env`) and passes on the fixed one.
4. `aw2dev gfx golden` after an INTENDED visual change, from a build you looked at.
Remember false passes: a golden made from a broken build blesses the bug; look at the frames the detector reports.
