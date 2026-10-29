# Aria (CO 93)

Nell's sister and Commander of the New Accord, an **Orange Star** CO of tangoAW2's own: the final opponent of the BH2 Campaign (M25), in its Act IV scenes, and Asuka's mirror (what Sonja might have become had
she stayed). Design: `docs/BH2_CAMPAIGN.md` section 9 (branch `bh2design`); this build only adds the CO. Code `tango-gamesupport-aw2/src/aria.rs` (constants, [`bonus`], the funds), the pieces in
`co_new.rs` (`ARIA`, `all()`, `like`, `is_own`, the row's style, the texts), `co_roster.rs` (`stat`, her row's luck, stars, movement charts, CPU settings), `es_co.rs` (`each_unit`: the heal), `es_cos.rs` (her art
and texts), `crumb.rs` (`has_own_quotes`, the `PayForPower` trap calls `aria::power_paid`), `ds_co_page.rs`, `ds_ai.rs`, `sturm_pairs.rs` / `tag.rs` (her pair), `custom_campaign.rs` (`country`: Orange Star).
Data `cos/aria.toml`, `cos/tags.toml`, art `art/cos/aria/`, framing `art-src/cos/aria_v1.toml`.

## What she does (the owner's redesign: two small rules of her own)
| | **Vengeance** (day to day) | **Build Anew** (Super Power, 7 stars) |
|---|---|---|
| Attack and defence | every unit (not an Oozium) +5%, always; and a unit with 8 HP or less (displayed) attacks and defends harder: +25% at 8 HP, 6% more per HP lost to +61% at 2, +85% at 1 (never an Oozium); 9 and 10 HP nothing | every unit +20% attack (and the power's own +10% / +10%) |
| HP | | every unit recovers 3 HP (`RepairUnit(unit, 3, 0)`, free) |
| Luck, movement | the game's own (Asuka keeps Nell's luck and Sturm's movement) | nothing more |
- **Vengeance** is a per-unit term: `aria::vengeance(hp)` (`aria::VENGEANCE` by displayed HP, the unit's HP in tenths rounded up) added to the firepower in `com_tower::side_firepower` with the other terms of a
  battle's base damage (Com Towers, skills) and to the defender's total defence in `co_roster::defence_total` (before AW2's 200 cap), so the forecast, the attack, the counterattack and the defence agree; the HP is
  the unit record's at the time the strike is worked out (a counterattack uses the HP the hit left). `data.py` has no mod for it: `cos/aria.toml` says `vengeance = { hp = 8, percent = [25, .., 85] }` and the test
  calculator adds it to firepower and defence in `Ctx.side` (`damage.aria_vengeance`). Tests: `aria_vengeance_scales_with_hp`, `aria_vengeance_defends_too`.
- **No CO Power**, like AW2's Sturm and Dual Strike's Von Bolt. Her CO row has 0 stars for it (`aria::STARS = (0, 7)`), which is all the game needs: the map menu has no "Power" entry (and "Super" appears at exactly
  7 x 9000, +20% each use), the HUD meter has a mark for the Super Power only, the CO page says she has none (the text is `[cop] text` in her data file, the wording of the page AW2 writes for Sturm), the
  CPU plays her with Von Bolt's profile (`ds_ai::template_of` -> 11) and Sturm's power settings in her row (`co_roster::new_row`): a Super Power as soon as the meter allows, never a CO Power. Her CO Power
  quote slots hold the Super Power's line (nothing reads them). `data.py` lets `stars.cop = 0` without a `[cop]` section's mods or quote.
- **Stars 0 / 7**: for comparison Sturm 0 / 10, Kanbei 4 / 7, Eagle 3 / 9; `aw2dev co balance aria --vs Max Kanbei Sturm` (below).
- **Tag**: Nell + Aria, "Sisters' Accord", 115%, 2 stars (`cos/tags.toml`, `sturm_pairs::DUOS`); Aria with anyone else 95% (`sturm_pairs::aria_compatibility`, as Asuka's).
- Orange Star's colours, style and HQ: her row's style byte and colour are Nell's (`new_row`), her battle style 0 (`co_new::build`), her HQ the game's own (`hq = "default"`), the CO page's tab Orange Star's
  (`custom_campaign::country`). In the Teams list and the War Room she follows Nell (`like`).
- **Not in the Emerald Sun Campaign**, reserved for the BH2 Campaign. In every Versus list, the tag partner pick, War Room, Survival, Champion and the DS-style CO select grid.
- **Theme**: her own song, `music/bh2/aria.m4t` (D minor, 130 bpm, the final O5 version), is a row of `es_music::SOURCES` (CO 93) and `theme = "own:aria"`; her turns play it in Versus and in the BH2 Campaign (without the music pack's
  room her row falls back to Nell's song, `co_new::like`). The same song is the scenes' `@SONG own:aria` (`Track::Own`).
- Online: `SIM_VERSION` 32 -> **33** (`pvp.rs` history): the CO table, the Teams order, the texts and the pictures are 93 rows long and a hurt unit of hers attacks harder. (Earlier drafts of her kit, with +3% / +10%,
  Nell's luck, Sturm's movement, +30% defence, +1 move and a day's income, were dropped before release: those traits stay Asuka's.)

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
- **Facing**: imported with `flip = true` (mirrored at the owner's request: as supplied she looked the way AW2's COs face, but the owner wants her the other way). In the picture her **body is turned three quarters to the viewer's right** (the coat's open front and her hip face right,
  the cigarette hand on the left) and her **head faces forward, eyes toward the viewer** with the nose and the face's shadow side turned slightly to the right: she reads as facing right, like Kanbei and Asuka.
- Tests: `aw2.colib.test_co.AriaArt` (the committed art equals a fresh import, lint, lightness and fringe lints, the palette keeps blue / white / two skin tones / a three-orange coat, the checker flatten),
  `co portrait lint`, `co portrait ingame aria`, `tests/test_aria_pictures.py` and the review sheet.
- `aw2dev co sheet vengeance` (test_aria_compare.py) writes the game's own damage forecasts for 7 matchups at 10 / 8 / 5 HP for Andy, Aria and Aria in Build Anew (the table, cross-checked against the damage formula) and the forecast boxes side by side.
- `co portrait ingame` learned CO Powers: with no CO Power it fills the meter past a Super Power's price and picks "Super" in the map menu; the cut-in of a Super Power comes about 6 s after the quote, so it
  photographs 56 frames; the quote frame is the one with the most text typed.

## The signs (option E: Vengeance shown on the map, the unit window and the damage forecast)
Approved from the mock-ups of `devkit/aw2/colib/vengeance_mockups.py`; the rule is `aria::sign(type, hp)` (her flat 8% plus `vengeance_for`: 8 HP +33%, 7 +39%, 6 +45%, 5 +51%, 4 +57%, 3 +63%, 2 +69%, 1 +93%; 10 and 9 HP nothing; an Oozium never; only with the CO
abilities on), and code `aria_sign.rs` with `ds_hud.rs` (`native_sign`, and the strip in `info_flush`). Nothing changes a number or the shared state of the game; everything is in VRAM, palette RAM, the sprite list and `aria_sign::STATE`
(`ram-map.md`), found again from the unit records every frame, so rollback and save states carry it.
- **Map**: the HP number of her unit with 8 to 1 displayed HP is drawn in `aria::RAMP` (orange 8, 7, 6, 5, 4, 3, 2, dark red 1), the black box round it kept; the low fuel / ammunition icons (BG2, the cell's top right) and the capture and cargo marks are other tiles of the cell and are
  not touched. The game draws the number as BG1 tile `0x2A1 + HP` in the unit's army bank (12..15, 11 once moved, 9 for a moved unit in a five-army game). After the game wrote its tile map (the sprite flush, `branding::flush` -> `aria_sign::map_flush`) the digit cell of each such unit
  (found from the unit record by the plane's arithmetic `ds_tilt` uses: cell = 2 x ((x - camera / 16 + BG3 scroll / 16) & 15) + 1) is pointed at one of our eight tiles, BG tiles `0x340..0x347` (a copy of the game's digit tile with the digit's colour index 1 moved to index HP; the first
  tiles of a screen block nothing uses: they were empty in every battle screen looked at, and are written only while empty or ours), in a BG palette bank that holds the ramp in 1..8 and black in 15. That bank is the first of `BANKS` (below) that no tile map refers to (4..7 are the fog's
  terrain banks, 9 the map menu's and a moved unit's in a five-army game); the game's own 32 bytes of it are kept in `STATE` and put back when a tile map starts referring to it or nothing needs the ramp. A cell is changed only where the tile map holds the digit tile of that unit's HP (so never a
  hidden "?" or a fogged unit), and put back (the bank worked out from the unit record) when the unit stops qualifying (healed, a Tag swap).
- **Unit window** (cursor on such a unit, AW2's own panel or Dual Strike's HUD): a strip the window's width on top of it in its own fill (the window's top shadow byte is lifted 26 rows, the game's byte kept in `STATE` and put back), "Vengeance" and "+NN%" as three sprites (palette 1, mode 1: the
  window words' own) in OBJ tiles 892..911 (the full-screen battle scenes' own: the OBJ-tile survey `AW2TEST_OBJ_SURVEY` over the suite shows the power animations and the map effects keep to 700..890, so a strip never shares tiles with an effect playing under it). The lettering is built at run time (`Strip::new`): the letters e, c, n of the window word "Recon" (ROM `0x08108764`), g of "Bridge" (`0x08107564`) and a of "Tank" (`0x08108664`) are cut out by their connected white pixels, the digits are the window's own
  HP-number digits (OBJ tiles 976..985, or Dual Strike's), and V, "+" and "%" are drawn small bitmaps in `aria_sign.rs` (the window has none of them). Nothing of the game's art is stored. No strip for a unit whose HP the game hides.
- **Damage forecast**: the same strip (the cursor is on the target); the DAMAGE box's frame and digits sprites are moved up by the strip's height. The forecast number is the game's own.
- **Dual Strike's tilted map**: the units there are drawn from their records (`ds_tilt.rs`), so `RamUnit::ramp` (`aria_sign::unit_ramp`) recolours the digit's ink in the 16 x 16 piece; the tilt's own colour expansion makes the picture's colours `(2c + 1) x 255 / 63` of the 5-bit ramp channels.
- **Which BG bank** (`BANKS`, tried in this order, bank 0 never: its colour 0 is the backdrop): 4, 5, 6, 7, 1, 3, 2, 11, 9, 10, 8, the first that no tile map refers to this frame. Fog plus a five-army game refers to 2, 4..7, 12..15 (and 9 for a moved unit): 1 or 3 is
  free; the test `aria_vengeance_signs_worst_case_banks` also draws tiles of 4, 5, 6, 7, 1, 3, 2, 11, 9 and 10 on BG0 and the ramp goes to bank 8. If every one of the 15 banks were referenced at once there would be no room for the ramp (the numbers would stay white): that
  takes the 8 terrain banks, the 6 unit banks and the menu's together, which no screen of the game does (the worst measured is 6 of them). The game's fades are the brightness effect (BLDY on every layer, the palettes untouched: `aria_vengeance_signs_fade`), so a ramp digit fades with the map.
- **Strip tiles** (`place_strip`): a run of 20 OBJ tiles that no sprite of the frame uses (the game's sprites of a unit that has attacked use tiles in 892..911, which an earlier fixed range wrote over: the lettering showed on them), the old content kept in EWRAM `0x0203B000` and put back when the strip goes.
- **Online**: `aw2dev net repeat aria --no-skin --fog off --level bad` (scenario `aria`: both armies Aria by the CO byte of the game's own table, units at 8, 5, 2 and 1 HP, the cursor over them, forecasts open and attacks) ends with equal hashes, and `aria_vengeance_signs_netplay` replays a forecast
  on two rollback peers and compares what the signs own (BG1 map, our tiles, the bank and its buffer, the EWRAM state, the strip's tiles and OAM entries).
- Tests: `tests/test_aria_vengeance_signs.py` (`-k aria_vengeance_signs`; a twin game with Andy for Aria: the HP numbers of her Tanks at 10..1 HP in the ramp and nothing else of the frame changed, the icons of a low-fuel and a no-ammunition one intact, an Oozium and Andy's Tank
  unchanged, the tiles and palette bank, the palette given back when healed; the strip equal to the mock-up composer's on 8, 5, 2 and 1 HP and absent on 10 / 9 HP, the Oozium and Andy; the enemy's forecast strip and the DAMAGE box 26 rows higher). `AW2TEST_VENGEANCE_REVIEW=<dir>` keeps the frames for
  `python3 -m aw2.colib.vengeance_signs_sheet DIR [OUT]` (devkit/), which composes the review sheets from the game's own pictures; `AW2TEST_VENGEANCE_UNIT` / `_ATTACKER` = `megatank` for the Megatank's.

## Verification (what was run)
`aw2dev co verify aria --net` (`co_verify_*_aria`, the generic scenarios against `cos/aria.toml` through `cospec.py`: attack, defence, counter and meter, move, economy, the heal of 3, the meter's 7 stars and the
missing Power entry, the Tag Power with Nell, an unlisted pair, the CPU's Super Power, the HQ, both peers equal), `tests/test_aria.py` (the row, Vengeance at 8 and 9 displayed HP in both levels and as a counterattacker,
the menu, the CPU, Build Anew's heal and nothing else), `aw2dev test`, `aw2dev co check`, `co balance`, `armyskin check --live` and `kit check`.
