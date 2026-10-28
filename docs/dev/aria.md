# Aria (CO 93)

Nell's sister and Commander of the New Accord, an **Orange Star** CO of tangoAW2's own: the final opponent of the BH2 Campaign (M25), in its Act IV scenes, and Asuka's mirror (what Sonja might have become had
she stayed). Design: `docs/BH2_CAMPAIGN.md` section 9 (branch `bh2design`); this build only adds the CO. Code `tango-gamesupport-aw2/src/aria.rs` (constants, [`bonus`], the funds), the pieces in
`co_new.rs` (`ARIA`, `all()`, `like`, `is_own`, the row's style, the texts), `co_roster.rs` (`stat`, her row's luck, stars, movement charts, CPU settings), `es_co.rs` (`each_unit`: the heal), `es_cos.rs` (her art
and texts), `crumb.rs` (`has_own_quotes`, the `PayForPower` trap calls `aria::power_paid`), `ds_co_page.rs`, `ds_ai.rs`, `sturm_pairs.rs` / `tag.rs` (her pair), `custom_campaign.rs` (`country`: Orange Star).
Data `cos/aria.toml`, `cos/tags.toml`, art `art/cos/aria/`, framing `art-src/cos/aria_v1.toml`.

## What she does (the owner's final numbers)
| | **Common Cause** (day to day) | **Build Anew** (Super Power, 7 stars) |
|---|---|---|
| Attack / defence | +3% / +10% | +20% / +30% on top (and the power's own +10% / +10%) |
| Move | Sturm's: every terrain costs 1 for ground units | +1 on every unit |
| HP | | every unit recovers 3 HP (`RepairUnit(unit, 3, 0)`, free) |
| Funds | | one day's income, once, at once (below) |
| Luck | Nell's: 0..19%, no bad luck | the same |
- **No CO Power**, like AW2's Sturm and Dual Strike's Von Bolt. Her CO row has 0 stars for it (`aria::STARS = (0, 7)`), which is all the game needs: the map menu has no "Power" entry (and "Super" appears at exactly
  7 x 9000, +20% each use), the HUD meter has a mark for the Super Power only, the CO page says she has none (the text is `[cop] text` in her data file, the wording of the page AW2 writes for Sturm), the
  CPU plays her with Von Bolt's profile (`ds_ai::template_of` -> 11) and Sturm's power settings in her row (`co_roster::new_row`): a Super Power as soon as the meter allows, never a CO Power. Her CO Power
  quote slots hold the Super Power's line (nothing reads them). `data.py` lets `stars.cop = 0` without a `[cop]` section's mods or quote.
- **Luck and movement are Asuka's implementation** (`co_roster::build`: `asuka::LUCK` 20 with no bad luck, the three movement charts of Sturm's row `asuka::MOVE_LIKE`), switched on for Aria too.
- **Funds**: defined exactly as an immediate grant equal to one day's income: the Funds rule's value for a property (`FUNDS_PER_PROPERTY`, 1000 by default; the Rules screen) times the properties that
  earn (`co_powers::earners`: the HQ, cities, bases, airports, ports; not labs or towers), added to her funds when the power is paid for (`PayForPower`'s trap, `aria::power_paid`), once, capped at 999999. "Twice
  that day" = the normal day's income at the start of her turn plus this grant. No income mode, no grant.
- **Stars 0 / 7** (the owner's): for comparison Sturm 0 / 10, Kanbei 4 / 7, Eagle 3 / 9. `aw2dev co check` keeps her under Kanbei's caps (day to day +13, Super Power +73 of firepower + defence, against its caps of 40 and 120).
- **Tag**: Nell + Aria, "Sisters' Accord", 115%, 2 stars (`cos/tags.toml`, `sturm_pairs::DUOS`); Aria with anyone else 95% (`sturm_pairs::aria_compatibility`, as Asuka's).
- Orange Star's colours, style and HQ: her row's style byte and colour are Nell's (`new_row`), her battle style 0 (`co_new::build`), her HQ the game's own (`hq = "default"`), the CO page's tab Orange Star's
  (`custom_campaign::country`). In the Teams list and the War Room she follows Nell (`like`).
- **Not in the Emerald Sun Campaign**, reserved for the BH2 Campaign. In every Versus list, the tag partner pick, War Room, Survival, Champion and the DS-style CO select grid.
- **Theme**: a placeholder, `co:nell` (her row's music is Nell's). Her own song, "Last Accord", is on the `bh2music` branch (its file `bh2/aria.m4t` under music) and is being reworked: when it lands,
  set `theme = "own:aria"` and add a row to `es_music::SOURCES` as Asuka's.
- Online: `SIM_VERSION` 32 -> **33** (`pvp.rs` history): the CO table, the Teams order, the texts and the pictures are 93 rows long and `PayForPower` pays the grant.

## Her picture (a direct import, with a baked-in checkerboard)
`art-src/cos/aria_v1.jpg` is 838 x 2000, a full-body figure in pixel art (native cells of 7 px: 118 x 279) whose "transparent" background is a **checkerboard baked into the JPEG** (white and light grey squares
of 13 px). The pixel-art importer (`pixelart.py`) got four options for it, all in `aria_v1.toml`; nothing of her is drawn, despeckled or edited:
- `checker = true`: before the grid is found, every light (Lab L above 80), colourless (chroma under 10) pixel connected to the border through such pixels becomes plain white (`flatten_checker`), so the squares'
  edges do not take part in the grid detection. `checker_seeds` floods a pocket of the checkerboard enclosed by her right arm and coat from points inside it (picture pixels). A white shirt or an eye white is
  never reached: her outline ring separates it.
- `grid_hint = [7.0, 7.1]`: the vertical edge profile's strongest period is a harmonic; the fine search and the line fit start from the true cell (7.002 x 7.138 fitted).
- `fringe = "light"` with `fringe_l = 40`, `fringe_c = 20` removes the pinkish-grey JPEG edge cells between the coat and the background (they were a grey halo and a palette entry of their own); `bg_seeds`
  clears the right-arm pocket before that step (so the pocket's own fringe goes too); `fringe_skip` keeps the cigarette's white paper; `edge_protect` / `face_edge_protect` list the pixels the lint's
  white-halo rule must accept (the paper, a knuckle, the collar). `hole_min` is **not** used: it took her white shirt for background.
- `erase`: the cigarette's smoke wisps (faint grey noise, native cells x 16..25, y 36..52) are dropped; the cigarette stays. `mug_erase` keeps the cigarette's ember out of the mug's lower left corner.
- Palette (`match = "lab"`, hue-aware: `luma` turned her shadowed skin gold): `protect` groups keep the blue irises, the eye whites, the face's skin, the shadowed skin of the leg, the beauty mark under her right
  eye, and the coat's middle and dark orange (the light one comes from the clustering): the coat is a three-shade ramp (ff7b10 / de6308 / c55200), the hair gold plus its shadows, the shirt white and a grey.
- Large art: 128 x 160 cells at 1x (`frame = [-6, -2]`: hat to the coat's hem); the mug is a 48-cell square at 1x (`mug = [33, 11]`): her head is 54 cells wide, so the square keeps the face and cuts a little
  hair at both sides; `eyes` places the mini and HUD windows.
- **Facing**: imported with `flip = false`, as in the source, which is how AW2's COs face (right). In the picture her **body is turned three quarters to the viewer's right** (the coat's open front and her hip face right,
  the cigarette hand on the left) and her **head faces forward, eyes toward the viewer** with the nose and the face's shadow side turned slightly to the right: she reads as facing right, like Kanbei and Asuka.
- Tests: `aw2.colib.test_co.AriaArt` (the committed art equals a fresh import, lint, lightness and fringe lints, the palette keeps blue / white / two skin tones / a three-orange coat, the checker flatten),
  `co portrait lint`, `co portrait ingame aria`, `tests/test_aria_pictures.py` and the review sheet.
- `co portrait ingame` learned CO Powers: with no CO Power it fills the meter past a Super Power's price and picks "Super" in the map menu; the cut-in of a Super Power comes about 6 s after the quote, so it
  photographs 56 frames; the quote frame is the one with the most text typed.

## Verification (what was run)
`aw2dev co verify aria` (`co_verify_*_aria`, the generic scenarios against `cos/aria.toml` through `cospec.py`: attack, defence, luck, counter and meter in 474 + 444 stat checks, move, economy with the Funds rule
at 1000, the heal of 3 and the grant, the meter's 7 stars and the missing Power entry, the Tag Power with Nell, an unlisted pair, the CPU's Super Power, the HQ), `tests/test_aria.py` (the row, luck, Sturm's
movement in clear / rain / snow, the menu, the CPU, the grant at 1000 and 2000 a property), `co_verify`'s `--net` (both peers equal), `aw2dev test`, `aw2dev co check`, `armyskin check --live` and `kit check`.
