# CO kit: custom COs as data files and imported art (`aw2dev co`)

How a new CO is described, its art made game-ready and checked before (and while) the engine work is done. Code: `devkit/aw2/colib/` (`importer.py` picture to AW2 art, `namefont.py` the name graphic,
`ingame.py` the real app on the game's screens, `sheet.py` the review sheet, `data.py` the data check and balance, `roms.py` / `render.py` readers for the sheets, `test_co.py` tests),
`devkit/aw2/commands/co.py`. Data: `tango-gamesupport-aw2/cos/<id>.toml` (one per CO), `cos/tags.toml` (Tag Powers). Art: `tango-gamesupport-aw2/art/cos/<id>/` (committed, indexed PNGs) from the
supplied picture `art-src/cos/<id>_user.jpg`. Engine side: `src/es_cos.rs` (art, texts, off by default), `co_new.rs` (`ES_FIRST` .. , `is_es`). Skill: `aw2-add-co`. First users: Emerald Sun's four COs
(`docs/ES_CAMPAIGN.md`). How a CO gets its powers and numbers is `co_new.rs`, `crumb.rs` (the worked example); this kit is the front half: the data and the pictures.

## Credits and what is committed
The four portraits are **the project owner's own art** ("portrait art provided by the project owner", `CREDITS.md`), supplied as 784 x 1168 pictures (`art-src/cos/*_user.jpg`) and committed with
their converted game-ready art, like Crumb's large art (`art/crumb/`). Nothing from the games or from AWBW is committed: the sheets show the real AW2 COs beside ours, read from the player's ROM.
Earlier attempts (portraits composed from AW2 / Dual Strike parts, then drawn by us) were rejected by the user and removed.

## The mapping: one data line a CO
`cos/<id>.toml` has `[portrait] source = "art-src/cos/<id>_user.jpg"`. Swapping two COs' pictures is swapping two lines. The framing of a picture (scale, the top crop, the mug's square, the eyes and the mouth,
in the picture's own pixels) is in the `.toml` beside it (`art-src/cos/<id>_user.toml`), so it follows the picture.

## What `co portrait import` / `stylise` does (`importer.py`, `stylise.py`)
The supplied picture is the **design reference** (who the character is: face, hair, armour, colours); the CO's art is **redrawn in AW2's own CO style** from it. A faithful downscale (the first import: dark,
textured, painterly) was rejected: it did not look like an AW2 CO. `co portrait import` (alias `stylise`) now does:
1. **Clean the source:** the dark background is a flood fill from the top edge (tolerance 18), so the JPEG noise and the background's texture go and dark shadows inside the figure stay; specks are dropped.
2. **The CO's own palette, in AW2's layout** (`palette` in the picture's framing file): index 1 white, 2..6 skin (light to dark), 7..14 the CO's eight colours (hair, gold, red, steel, cloth ...), 15 the outline
   (AW2's `201820`). The colours are bright and saturated like AW2's (Kanbei's yellow, Andy's red); a CO has 15 colours + transparent for every picture.
3. **Lift and match:** the picture is area-averaged (premultiplied, so the background does not bleed in), lifted (`lift` = lightness gamma and a chroma gain that leaves greys grey; `contrast`) to AW2's pitch, and each
   pixel goes to the **nearest palette colour** in Lab. **Zones** (`[[zone]]`: polygons in the picture's pixels, `only` = the indexes allowed inside, `exclusive`/`ban` = nobody outside may use them) keep a
   shadow on a face from turning into gold and a gold plate from turning into skin, and keep the hair's darks on the hair.
4. **Flatten:** mode filters make every colour a flat region with hard edges (no texture, no dithering); specks and pinholes in the silhouette go.
5. **Line art:** the outline (index 15) round the figure (not along the cut bottom), a line along each zone's edge (`line`: the jaw, the hairline, the ear), and the face's thin dark features (the mouth line, the
   nose's shadow, the eyelids: `crease`) kept in the dark skin tone.
6. **Eyes:** max-pooling inside each eye's box keeps the whites (index 1) and darks (index 15) and their catchlights, drawn the way AW2 draws them (a dark lid, a mostly dark iris, one white corner).
7. **The small faces are cut again from the source**, not shrunk from the figure: the CO select mug 48 x 48 (`face = [x, y, side]`, a tighter crop than the figure's head so the eyes are as large as AW2's),
   the Teams mini 32 x 24 and the HUD face 32 x 16 are windows of the mug round the eyes.
8. **Expression faces** (normal, happy, sad, angry) edit the mug's eyes, brows and mouth in the same flat style (closed smiling eyes and a grin; brows raised at the nose and a frown; brows lowered, narrowed eyes
   and gritted teeth), filling the old features with the skin just above or below. AW2 uses three faces (normal, happy, sad); the angry one is kept for dialogue.
9. **The name graphic** 48 x 16 is set in our own letters (`namefont.py`); `crop.toml` says where Versus' 24-pixel cell and the grid's 16-row strip start.
Output: `art/cos/<id>/{large,face_normal,face_happy,face_sad,face_angry,mini,hud,name}.png` (4-bit indexed, index 0 transparent) and `crop.toml`; deterministic. `co portrait import --painterly`-style output (the
faithful import) is still available to the sheet (`importer.import_co(spec, painterly=True)`) as the "previous import" column.

## AW2's style as numbers (`style.py`, `co portrait lint --style aw2`)
Measured from AW2's 19 large figures and 19 faces (read from the player's ROM): mean value (brightness) 0.37 to 0.82 (mean 0.61), saturation 0.20 to 0.78 (0.48), luminance contrast 39 to 77 (60), flatness
(pixels whose 4-neighbours share more than one of their colour) 0.53 to 0.83 (0.67), colour regions per 1000 pixels 34 to 124 (75), dark share (outline and deep shadows) 0.15 to 0.72 (0.26), 13 to 15 colours;
faces: value 0.48 to 0.85, saturation 0.25 to 0.69, contrast 61 to 88, flatness 0.39 to 0.61, regions 111 to 218, dark share 0.15 to 0.53; the head (the top of the figure to the chin) 26 to 96 px (mean 60)
with the eye line 11 to 54 px from the top (mean 21) and 0 to 13 rows of margin above. A CO passes when every number is inside AW2's range widened by 15% (a face's region count by 35%: AW2's faces carry the game's
busiest hair). `co portrait stylise` prints the table.

## The data file (`cos/<id>.toml`)
```toml
id = "klaus"; name = "Klaus"; short = "Klaus" (optional: the form for a name plate the full name clips); army = "emerald_sun"; role = "..."; theme = "co:kanbei"; bio = "..."; luck = [10, 10, 10]
stars = { cop = 4, scop = 8 }        # CO Power, Super Power in all (AW2's table: Hawke 5/9, Kanbei 4/7; `aw2dev co check` prints it)
[d2d]  name, text, mods = [{ units = "foot", attack = 10, defence = 10 }]   # units: all foot vehicle direct indirect naval air artillery rockets
[cop]  name, text, mods, rules = ["..."], quote = ["line 1", "line 2"]      # a rule is a sentence the engine work implements (phase 2)
[scop] name, text, mods, heal = 3, tribute = 100, quote
[lines] tag_in, victory, defeat
[portrait] source = "art-src/cos/klaus_user.jpg"
```
`cos/tags.toml`: `[[pair]] a, b, compat (65..130 firepower %), stars (1..3), name, why`; `aw2:<name>` for a partner from the games. The stars follow Sturm's table (`sturm_pairs.rs`):
110 is one, 115 to 120 two, 125 three. Every pair of an army's COs must be listed.

## Commands
| Command | What |
|---|---|
| `aw2dev co portrait import [CO ...] [--check]` | picture -> AW2-style art (above); `--check` only compares with the committed art (exit 1 if different) |
| `aw2dev co portrait stylise [CO ...]` | import, then the lint with the style table (AW2's range beside each number) |
| `aw2dev co portrait lint [CO ...] [--style aw2]` | the committed art: sizes, one shared palette of at most 15 colours + transparent, an outline wherever a coloured pixel meets transparency, no speckle (AW2's own figures have 183 to 562 isolated pixels and faces 102 to 202; the limits are 600 and 220: the check is for a speckled JPEG, not for detail), the name graphic present |
| `aw2dev co portrait sheet [CO ...] [--style]` | the review sheet (`--style`: `co_portraits_aw2style.png`, with the previous import beside the new art): source, large art 1x and 2x beside AW2's own, the four expressions, mini, HUD face, CO select and HUD strips with real COs, the game's own screens |
| `aw2dev co portrait ingame [CO ...]` | the real app (Dual Strike pack, `TANGOAW2_ES_COS=1`) through the AI debug channel: picks the CO on the Normal Battle Teams screen (CO select), starts the battle (the HUD), fills the meter by a poke and uses the Power (the quote's dialogue box and the cut-in with the large figure), opens the CO page; checks each screen shows the committed art (the mug pixel for pixel, the HUD face, the figure's colours) |
| `aw2dev co balance [CO ...] [--vs Kanbei ...]` | each power level's average firepower / defence / move / range over a typical army, the CO next to Dual Strike's own COs (read from the .nds: class stats at record +0xA0 + 0x80 * level, `co_roster.rs`) |
| `aw2dev co check [CO ...]` | the data files: fields, stars against AW2's own table (printed with the nearest AW2 COs), day-to-day and power totals no higher than Kanbei's (40 / 90 / 120 points of firepower plus defence), modifier ranges, quote line lengths, name plates, tag pairs complete and consistent, the picture and its framing file exist |

Pass means exit 0. `aw2dev test` runs `aw2.colib.test_co` (valid files, six pairs, a bad file is caught, the committed art equals a fresh import and passes the lint, the lint catches bad art, the
importer's steps). Rust: `cargo test -p tango-gamesupport-aw2 --lib es_cos` (the PNGs become AW2's tile formats, every text slot exists).

## In the game (`es_cos.rs`, `co_new.rs`)
The four are CO ids 86..89 (`co_new::ES_FIRST`), filled like Clone Andy's row (Andy's numbers) with their own art, name graphic, texts and quotes: **off unless `TANGOAW2_ES_COS=1`** (docs/dev/env-aids.md),
because the tables of the console are built from it (both peers of a match must agree) and their powers are not built yet (phase 2). On: the Teams list, the CO select cards, the HUD, the dialogue
boxes (Power quotes), the power and tag cut-ins, and the CO page show them.

## Name plates
`aw2dev co check` measures each name in AW2's text font against the widest plate (28 px, Von Bolt): Klaus 19, Livia 17, Aurelia 24, Cassius 27, all within. The 48 x 16 name graphic is our own set of letters:
Klaus, Aurelia, Livia fit with room, Cassius fills all 48 columns. No plate needed the short form (`short = "Aurel"` / `"Cass"` in the CO files are for a plate that clips).

## Limits
The supplied pictures are one expression each: the happy, sad and angry faces are edits of the eyes, brows and mouth (readable, but a drawn set would be better; ask the owner). The importer expects a bust on a
flat dark background; a different picture needs its own framing `.toml`: the scale, the mug's square, the eyes, the palette and the zones are decided by looking at the picture (`/tmp`-style overlays of the zones are easy to make: draw the polygons on the picture). The zone polygons are by eye, to a few source pixels. The portrait is palette scheme 0 repeated for the eight colour schemes the game offers (no recolour variants).
