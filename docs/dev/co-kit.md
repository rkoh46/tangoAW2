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

## What `co portrait import` does (`importer.py`)
1. **Clean the source:** the dark background is a flood fill from the top edge (tolerance 18 round the picture's own background colour), so the JPEG noise and the texture of the background go and
   dark shadows inside the figure stay; specks not joined to the figure are dropped.
2. **Large figure 128 x 160** (the CO page, power cut-in and tag screens: AW2's six-sprite body): the picture is area-averaged to `scale` (premultiplied, so the background does not bleed into the edges),
   placed `top` rows from the top and centred; what falls below 160 is cut like AW2's own figures.
3. **One palette for the CO** (AW2 gives a CO one 16-colour palette for every picture): the colours of the large figure and the mug are quantised together (k-means in Lab, the faces weighing 6x),
   13 colours + a true white (eyes, teeth, highlights) + the outline in index 15; a mild lift of lightness and chroma brings the painterly, dark pictures to the game's bright pitch (`lift`).
   Colours are snapped to the GBA's 5 bits.
4. **Cleanup:** pinholes and specks in the silhouette, isolated pixels (a pixel no 4-neighbour shares the colour of is replaced when the neighbours agree), then the outline (index 15) on every
   transparent pixel touching the figure inside the picture, not along the cut bottom.
5. **The small faces are cut again from the source**, not shrunk: the CO select mug 48 x 48 (`face = [x, y, side]`), the Teams mini 32 x 24 and the HUD face 32 x 16 are windows of the mug round the eyes.
   The eyes keep their whites and darks by max-pooling inside each eye's box (`feature_pass`), so a 3-pixel catchlight is not averaged away.
6. **Expression faces** (normal, happy, sad, angry): the neutral face is the picture's own; the others edit the eyes, brows and mouth of the mug (closed smiling eyes and a grin; brows raised at the nose and a
   frown; brows lowered, narrowed eyes and gritted teeth), filling the old features with the skin just above or below so the shading runs on. AW2 uses three faces (normal, happy, sad: the defeat face);
   the angry face is kept for dialogue.
7. **The name graphic** 48 x 16 is set in our own letters (`namefont.py`, original art: white fill, outline, shadow, the fixed name palette).
8. `crop.toml` (where Versus' 24-pixel cell and the grid's 16-row strip start so the eyes show).
Output: `art/cos/<id>/{large,face_normal,face_happy,face_sad,face_angry,mini,hud,name}.png` (4-bit indexed, index 0 transparent) and `crop.toml`; deterministic (a test compares them with a fresh import).

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
| `aw2dev co portrait import [CO ...] [--check]` | picture -> art (above); `--check` only compares with the committed art (exit 1 if different) |
| `aw2dev co portrait lint [CO ...]` | the committed art: sizes, one shared palette of at most 15 colours + transparent, an outline wherever a coloured pixel meets transparency, no speckle (AW2's own figures have 183 to 562 isolated pixels and faces 102 to 202; the limits are 600 and 220: the check is for a speckled JPEG, not for detail), the name graphic present |
| `aw2dev co portrait sheet [CO ...]` | the review sheet `co_portraits_user.png`: source, large art 1x and 2x beside AW2's own, the four expressions, mini, HUD face, CO select and HUD strips with real COs, the game's own screens |
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
flat dark background; a different picture needs its own framing `.toml`. The portrait is palette scheme 0 repeated for the eight colour schemes the game offers (no recolour variants).
