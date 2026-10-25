# CO kit: custom COs as data files and imported art (`aw2dev co`)

How a new CO is described, its art made game-ready and checked before (and while) the engine work is done. Code: `devkit/aw2/colib/` (`importer.py` picture to AW2 art, `namefont.py` the name graphic,
`ingame.py` the real app on the game's screens, `sheet.py` the review sheet, `data.py` the data check and balance, `roms.py` / `render.py` readers for the sheets, `test_co.py` tests),
`devkit/aw2/commands/co.py`. Data: `tango-gamesupport-aw2/cos/<id>.toml` (one per CO), `cos/tags.toml` (Tag Powers). Art: `tango-gamesupport-aw2/art/cos/<id>/` (committed, indexed PNGs) from the
supplied picture `art-src/cos/<id>_v5.jpg`. Engine side: `src/es_cos.rs` (art, texts, off by default), `co_new.rs` (`ES_FIRST` .. , `is_es`). Skill: `aw2-add-co`. First users: Emerald Sun's four COs
(`docs/ES_CAMPAIGN.md`). How a CO gets its powers and numbers is `co_new.rs`, `crumb.rs` (the worked example); this kit is the front half: the data and the pictures.

## Credits and what is committed
The four portraits are **the project owner's own art** ("portrait art provided by the project owner", `CREDITS.md`), supplied as 784 x 1168 pictures of full-body figures, already pixel art (`art-src/cos/*_v5.jpg`) and committed with
their converted game-ready art, like Crumb's large art (`art/crumb/`). Nothing from the games or from AWBW is committed: the sheets show the real AW2 COs beside ours, read from the player's ROM.
Earlier attempts (portraits composed from AW2 / Dual Strike parts, drawn by us, a painterly downscale and a cel-shaded redraw of the owner's first busts) were rejected by the user and removed.

## The mapping: one data line a CO
`cos/<id>.toml` has `[portrait] source = "art-src/cos/<id>_v5.jpg"`. Swapping two COs' pictures is swapping two lines. The framing of a picture (scale, the top crop, the mug's square, the eyes and the mouth,
in the picture's own pixels) is in the `.toml` beside it (`art-src/cos/<id>_v5.toml`), so it follows the picture.

## The pixel-art import (`pixelart.py`, `co portrait import --pixelart` or `pixelart = true` in the framing file)
The owner's pictures are already pixel art, upscaled by a (fractional) factor and saved as JPEGs: they are imported **faithfully**, cell for cell, never stylised or resampled blurrily.
1. **Native grid** (`detect_grid`): the cell size and the first edge per axis from the picture's edge profile (an FFT for the period, a comb search around it, then a weighted line fitted through the
   edges), so a 4.08 px or 5.33 px cell is found as well as 4.0. `aw2dev co portrait grid <picture> [--flip]` prints it and writes a debug picture with every tenth native cell numbered (the coordinates
   of the framing file are these cells, of the mirrored grid when `flip`). Aurelia and Livia are 4 px cells (196 x 292), Cassius and Klaus 5.33 px cells (147 x 219).
2. **Resample on the cell centres** (`native`): each cell is the mean of its middle half, so the JPEG's ringing at the cell edges does not count. The result is the original pixel art.
3. **Background cut** (`cut_background`): a flood fill from the border over cells within `bg_tolerance` (9) of the background colour, on the native cells. A near-black uniform (Cassius) is a few levels
   lighter than the background, so it stays; dark pockets not connected to the border stay; specks go. The figure's own dark contour is not needed: the importer draws AW2's outline (index 15) one cell wide round the figure.
4. **Palette**: at most 15 colours + transparent from the native cells of the figure frame and the mug (the mug weighs 3x), weighted k-means in Lab (JPEG near-duplicates merge), snapped to 5 bits per channel,
   lightest first, index 15 the outline `201820`. The gold, red and white ramps come out as 2 to 3 clean steps each. No dithering: every cell goes to its nearest colour.
5. **The large art** 128 x 160 is a 64 x 80 cell frame (`frame = [x, y]`, or automatic: the head's top two rows from the top, centred on the upper body) scaled **2x by whole cells** (no resampling): head, shoulders
   and chest as AW2 frames its COs (waist-up, head 45 to 65 px, the cut at the waist or the hips). `flip = true` mirrors the grid so the CO faces right like AW2's (Cassius and Klaus are drawn facing left).
6. **The mug** 48 x 48 is a 24 x 24 cell square of the head (`mug = [x, y]`) scaled 2x; the mini (a 48 x 16 strip of the whole mug width, 12 tiles: the left 32 x 16 in rows of four, the right 16 x 16 in rows of two; what the battle scene's header draws) and the HUD face 32 x 16 are windows of it round the eyes (`eyes = [x1, y1, x2, y2]`).
7. **Expressions**: nothing is drawn or edited (the owner rejected the edited faces). Every expression slot the game uses (happy, sad, angry) shows the neutral mug, the picture's own. If the owner
   supplies real expression pictures, `art-src/cos/<id>_<expression>.jpg|png` (`happy`, `sad`, `angry`; same grid, size and framing as `<id>_v5.jpg`) are picked up by the importer: the mug is cut from them with
   the CO's palette. `eyes = [x1, y1, x2, y2]` is only used to place the Teams mini and the HUD face.
8. **The name graphic** 48 x 16 is set in our own letters (`namefont.py`); `crop.toml` says where Versus' 24-pixel cell and the grid's 16-row strip start.
Output: `art/cos/<id>/{large,face_normal,face_happy,face_sad,face_angry,mini,hud,name}.png` (4-bit indexed, index 0 transparent) and `crop.toml`; deterministic. The AW2 figures are 1:1 pixels and ours are 2x
cells, so ours look chunkier beside Hawke's 1-px detail; that is the picture's own pixel size. The older painterly import (`importer.import_co` without `pixelart`) remains for pictures that are not pixel art.

## The illustration import (`illustration.py`, `co portrait import --illustration` or `illustration = true` in the framing file)
For a **clean drawing** that is not upscaled pixel art (Asuka's `art-src/cos/asuka_v1.jpg`, 1136 x 1744, a full-body anime illustration on white; framing file `art-src/cos/asuka_v1.toml`). Nothing is drawn, stylised or retouched:
1. **Background cut**: a flood fill from the border over pixels within `bg_tolerance` (42, an RGB distance from the border's median colour; wide enough to take the JPEG's pale fringe); gaps of the pure background colour
   (`hole_tolerance` 12, at least `hole_min` 25 pixels) enclosed by the figure (between an arm and the body, between the hair and the neck) are background too, with their fringe; the off-white of an eye or a highlight is not that pure and stays.
2. **Downscale**: coverage by area average (silhouette opaque from 0.5), colour by Lanczos over the figure's own pixels only (the mask eroded `halo` pixels; the figure's colours extended outwards so the kernel never reads the white), area average at the edges where Lanczos overshoots.
3. **Frame**: `scale` output pixels per source pixel (0.22: the head 63 px, waist-up like AW2's), `frame = [x, y]` the source pixel of the output's top left, `mug = [x, y, size]` the source square of the head for the 48 x 48 faces, `eyes = [x1, y1, x2, y2]` for the 48 x 16 mini strip and the 32 x 16 HUD window (cut from the mug at the same scale: nothing resampled twice). `flip` mirrors (she already looks right).
4. **One palette** (<= 15 + transparent, index 15 the outline `201820`): k-means in Lab with `dark_colours` (3) of the 14 kept for the dark pixels (black cloth and hair would otherwise merge into one brown), the pixels weighted against the big flat colours (`rare`), snapped to 5 bits, lightest first, no dithering; isolated pixels removed; outline one pixel wide.
5. Expressions: the neutral face in every slot. `aw2dev co portrait lint --style aw2` will say a black-clad figure is darker and less saturated than AW2's range (her figure value 0.26, dark share 0.83): that is the picture's own colouring, kept.
6. **Edges** (compared with Kanbei's): a hard silhouette (coverage at one half, spikes off), an outline one pixel wide and unbroken in 8-connectivity, the uniform's black on its own dark ramp above the outline, a one-pixel seam in the darker material's shadow tone where two big materials meet (not on the faces). `co portrait lint` checks illustration imports for outline gaps, a second layer, outline colour inside the figure and tones blending into the outline (`importer.outline_problems`).
Tests: `aw2.colib.test_co.Illustration` and `OutlineLint` (the cut, enclosed gaps, no white bleed, sizes, outline, determinism, flip, the committed art equals a fresh import, the outline checks).

## AW2's style as numbers (`style.py`, `co portrait lint --style aw2`)
Measured from AW2's 19 large figures and 19 faces (read from the player's ROM): mean value (brightness) 0.37 to 0.82 (mean 0.61), saturation 0.20 to 0.78 (0.48), luminance contrast 39 to 77 (60), flatness
(pixels whose 4-neighbours share more than one of their colour) 0.53 to 0.83 (0.67), colour regions per 1000 pixels 34 to 124 (75), dark share (outline and deep shadows) 0.15 to 0.72 (0.26), 13 to 15 colours;
faces: value 0.48 to 0.85, saturation 0.25 to 0.69, contrast 61 to 88, flatness 0.39 to 0.61, regions 111 to 218, dark share 0.15 to 0.53; the head (the top of the figure to the chin) 26 to 96 px (mean 60)
with the eye line 11 to 54 px from the top (mean 21) and 0 to 13 rows of margin above. A CO passes when every number is inside AW2's range widened by 15% (a face's region count by 35%: AW2's faces carry the game's
busiest hair). `co portrait lint --style aw2` prints the table; it is a report, not the judge: look at the sheet beside the real COs.

## The data file (`cos/<id>.toml`)
```toml
id = "klaus"; name = "Klaus"; short = "Klaus" (optional: the form for a name plate the full name clips); army = "emerald_sun"; role = "..."; theme = "co:kanbei"; bio = "..."; luck = [10, 10, 10]
stars = { cop = 4, scop = 8 }        # CO Power, Super Power in all (AW2's table: Hawke 5/9, Kanbei 4/7; `aw2dev co check` prints it)
[d2d]  name, text, mods = [{ units = "foot", attack = 10, defence = 10 }]   # units: all foot vehicle direct indirect naval air artillery rockets
[cop]  name, text, mods, rules = ["..."], quote = ["line 1", "line 2"]      # a rule is a sentence the engine work implements (phase 2)
[scop] name, text, mods, heal = 3, tribute = 100, quote
[lines] tag_in, victory, defeat
[portrait] source = "art-src/cos/klaus_v5.jpg"
```
`cos/tags.toml`: `[[pair]] a, b, compat (65..130 firepower %), stars (1..3), name, why`; `aw2:<name>` for a partner from the games. The stars follow Sturm's table (`sturm_pairs.rs`):
110 is one, 115 to 120 two, 125 three. Every pair of an army's COs must be listed.

## Commands
| Command | What |
|---|---|
| `aw2dev co portrait import [CO ...] [--check] [--pixelart]` | picture -> AW2 art (above); `--check` only compares with the committed art (exit 1 if different) |
| `aw2dev co portrait grid PICTURE [--flip]` | a pixel-art picture's native grid, the figure's box and a numbered debug picture |
| `aw2dev co portrait lint [CO ...] [--style aw2]` | the committed art: sizes, one shared palette of at most 15 colours + transparent, an outline wherever a coloured pixel meets transparency, no speckle (AW2's own figures have 183 to 562 isolated pixels and faces 102 to 202; the limits are 600 and 220: the check is for a speckled JPEG, not for detail), the name graphic present |
| `aw2dev co portrait sheet [CO ...]` | the review sheet: source, large art 1x and 2x beside AW2's own, the four expressions, mini, HUD face, CO select and HUD strips with real COs, the game's own screens |
| `aw2dev co portrait ingame [CO ...]` | the real app (Dual Strike pack, `TANGOAW2_ES_VERSUS=1`) through the AI debug channel: picks the CO on the Normal Battle Teams screen (CO select), starts the battle (the HUD), fills the meter by a poke and uses the Power (the quote's dialogue box and the cut-in with the large figure), opens the CO page; checks each screen shows the committed art (the mug pixel for pixel, the HUD face, the figure's colours) |
| `aw2dev co balance [CO ...] [--vs Kanbei ...]` | each power level's average firepower / defence / move / range over a typical army, the CO next to Dual Strike's own COs (read from the .nds: class stats at record +0xA0 + 0x80 * level, `co_roster.rs`) |
| `aw2dev co verify sonja [--build-baseline]` | Sonja is exactly as in the v0.8.7 build: `tests/test_sonja_untouched.py` (run on the reference build's example binaries and on this tree's) writes her CO row, presentation pictures, HUD face, texts, battle numbers in her three levels as attacker and defender, fog vision, place in the Teams list, Tag page and Tag Power numbers and the frames of her screens (hashes only) to `sonja.json`; any difference fails; the reference is built once from the tag (`devkit/work/baseline`) |
| `aw2dev co check [CO ...]` | the data files: fields, stars against AW2's own table (printed with the nearest AW2 COs), day-to-day and power totals no higher than Kanbei's (40 / 90 / 120 points of firepower plus defence), modifier ranges, quote line lengths, name plates, tag pairs complete and consistent, the picture and its framing file exist |

Pass means exit 0. `aw2dev test` runs `aw2.colib.test_co` (valid files, six pairs, a bad file is caught, the committed art equals a fresh import and passes the lint, the lint catches bad art, the
importer's steps). Rust: `cargo test -p tango-gamesupport-aw2 --lib es_cos` (the PNGs become AW2's tile formats, every text slot exists).

## In the game (`es_cos.rs`, `co_new.rs`)
The four are CO ids 86..89 (`co_new::ES_FIRST`), filled like Clone Andy's row (Andy's numbers) with their own art, name graphic, texts and quotes: **in the campaign always, in Versus only with `TANGOAW2_ES_VERSUS=1`** (docs/dev/env-aids.md),
because the tables of the console are built from it (both peers of a match must agree) and their powers' rules are engine hooks (`es_co.rs`) that both peers must run alike. On: the Teams list, the CO select cards, the HUD, the dialogue
boxes (Power quotes), the power and tag cut-ins, and the CO page show them.

## Name plates
`aw2dev co check` measures each name in AW2's text font against the widest plate (28 px, Von Bolt): Klaus 19, Livia 17, Aurelia 24, Cassius 27, all within. The 48 x 16 name graphic is our own set of letters:
Klaus, Aurelia, Livia fit with room, Cassius fills all 48 columns. No plate needed the short form (`short = "Aurel"` / `"Cass"` in the CO files are for a plate that clips).

## Asuka
CO 92 (`crate::asuka`, docs/dev/asuka.md): the first CO of the kit that is in **every** Versus list (no playtest flag), a Black Hole CO whose numbers are Sonja's, whose powers add Hawke's HP swing and Drake's halving, and whose picture is the owner's illustration (imported by the illustration mode above). Her data file carries the optional keys `vision`, `hidden_hp`, `terrain_cut`, `strike_first`, `hp_own`, `hp_enemy` (checked by `co check`; the numbers themselves live in the game's tables).

## Limits
The supplied pictures are one expression each: the happy, sad and angry slots show the neutral face (edited faces were rejected; real expression pictures from the owner are picked up as `art-src/cos/<id>_<expression>.*`). The importer expects a bust on a
flat dark background; a different picture needs its own framing `.toml`: the scale, the mug's square, the eyes, the palette and the zones are decided by looking at the picture (`/tmp`-style overlays of the zones are easy to make: draw the polygons on the picture). The zone polygons are by eye, to a few source pixels. The portrait is palette scheme 0 repeated for the eight colour schemes the game offers (no recolour variants).
