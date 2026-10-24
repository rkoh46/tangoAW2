# CO kit: custom COs as data files (`aw2dev co`)

How a new CO is described, drawn and checked before any engine code exists. Code: `devkit/aw2/colib/` (`roms.py` readers, `compose.py` composition, `sheets.py` sheets and
checks, `data.py` the data check, `test_co.py` tests), `devkit/aw2/commands/co.py`. Data: `tango-gamesupport-aw2/cos/<id>.toml` (one per CO), `cos/tags.toml` (Tag Powers),
`cos/art/*.toml` (our own overlay pixel art and ramps). Skill: `aw2-add-co`. First users: Emerald Sun's four COs (`docs/ES_CAMPAIGN.md`).
How a CO gets into the game (CO table row, presentation row, texts, powers, Tag data) is `co_new.rs` and `crumb.rs` (the worked example); this kit is the front half: the data and the picture.

## What is committed and what is not
Nothing from the games. The portrait is a **recipe**: a donor CO (`aw2:hawke`, `ds:javier`: any of AW2's 19 or Dual Strike's 27) whose parts the tool reads from the player's ROMs at run
time, recoloured by rules (`ramp`: palette indices onto a named ramp of `art/palette.toml`, by brightness rank) and overlaid with **our own** pixel art (`shape = "laurel"`, `"helmet"`,
`line` for a sash, `motif` = a pixel grid in `art/roman.toml`). The recipe and the overlays are original work of this repository (GPL-3.0-or-later); the donor pixels are never stored.

## The data file (`cos/<id>.toml`)
```toml
id = "klaus"; name = "Klaus"; army = "emerald_sun"; role = "..."; theme = "co:kanbei"; bio = "..."; luck = [10, 10, 10]
stars = { cop = 4, scop = 9 }        # CO Power, Super Power in all (AW2's table: Hawke 5/9, Kanbei 4/7; `aw2dev co check` prints it)
[d2d]  name, text, mods = [{ units = "foot", attack = 10, defence = 10 }]   # units: all foot vehicle direct indirect naval air artillery rockets
[cop]  name, text, mods, rules = ["..."], quote = ["line 1", "line 2"]      # a rule is a sentence the engine work implements (phase 2)
[scop] name, text, mods, heal = 3, tribute = 100, quote
[lines] tag_in, victory, defeat
[[portrait.option]]  letter = "A"; description = "..."; donor = "aw2:hawke"
   ramp = [{ indices = [9, 10], ramp = "sage" }]            # donor palette entries -> a ramp (indices: `aw2dev co portrait palette DONOR`)
   [[portrait.option.place]] shape = "helmet" | "laurel" | line = [x0, y0, x1, y1] + width + colours | motif = "phalera"; anchor = "brow|chin|neck|ear_l|ear_r|centre"; dx dy; target = "body face"
[portrait] chosen = "C"                                      # set when the user has picked
```
`cos/tags.toml`: `[[pair]] a, b, compat (65..130 firepower %), stars (1..3), name, why`; `aw2:<name>` for a partner from the games. The stars follow Sturm's table
(`sturm_pairs.rs`): 110 is one, 115 to 120 two, 125 three. Every pair of an army's COs must be listed (the check fails otherwise).

## Commands
| Command | What |
|---|---|
| `aw2dev co portrait donors [--source aw2\|ds]` | a contact sheet of every donor's figure, face and palette swatches |
| `aw2dev co portrait palette DONOR` | the palette entries with hue / saturation / value / pixel counts (write `ramp` rules from it) |
| `aw2dev co portrait compose CO --option A` | one option: the 128 x 160 figure (CO page, power and tag screens), the three 48 x 48 faces (CO select), the 32 x 24 small face (Teams) and the 32 x 16 HUD face |
| `aw2dev co portrait options CO [--letters ABC] [--out PNG]` | the lettered options of a CO on one sheet, a line about each (the review sheet) |
| `aw2dev co portrait check [CO ...]` | every recipe composes and fits the game's 15 colours + transparent (the composer merges the closest colours; the sheet shows the merged result) |
| `aw2dev co balance [CO ...] [--vs Kanbei ...]` | each power level's average firepower / defence / move / range over a typical army, the CO next to Dual Strike's own COs (read from the .nds: class stats at record +0xA0 + 0x80 * level, `co_roster.rs`) |
| `aw2dev co check [CO ...]` | the data files: fields, stars against AW2's own table (printed with the nearest AW2 COs), day-to-day and power totals no higher than Kanbei's (40 / 90 / 120 points of firepower plus defence), modifier ranges, quote line lengths, tag pairs complete and consistent |

Pass means: exit 0. `aw2dev test` runs `aw2.colib.test_co` (valid files, six Emerald Sun pairs, a bad file is caught, every recipe composes in 15 colours, the donor readers give the game's sizes).
Limits: the overlays are placed from the skin colour of the head (anchors `brow`, `chin`...), so a donor with a hat or very long hair may need a `dy` or no helmet (`target`); the helmet replaces
the hair above the brow, so it suits short hair. The portrait is scheme 0 only (the game has eight colour schemes per CO; the other seven are derived by hue when the CO is built in).
Dual Strike's donors carry a white outline that AW2's do not; it is kept. Names are 48 x 16 pixels in the game (six letters of a name graphic): a seven-letter name needs checking when the CO is built in.
