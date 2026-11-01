# Army skins: Silver Nova, and how to add the next army

tangoAW2 has a sixth army, **Silver Nova** (until 2026-11 it was Silver Nova; the data file keeps the id `emerald_sun`, which the CO data files name), and a general way to add more: an army is a **skin**, a data file (`tango-gamesupport-aw2/skins/<id>.toml`)
that the game draws on top of one of AW2's five colours. The art is the project's own, applied at run time to AW2's own graphics, which are read from the player's ROM as always. Silver Nova's HQ is the project
owner's own pixel art, imported faithfully (`art-src/silver-nova/hq.jpg`, `aw2dev armyskin import-hq`, section 9), its colours come from the owner's city picture (`art-src/silver-nova/city_ref.jpg`: silver and blue-grey with
yellow windows); its soldiers (the owner's mask without the old Roman plume), emblem (the sun, in shaded silver) and palette (bright chrome, the owner's pick of six options) are drawn here. Nothing from any game is in the repository.

Code: `tango-gamesupport-aw2/src/army_skin.rs`. Kit: `aw2dev armyskin ...` (`devkit/aw2/commands/armyskin.py`, `devkit/aw2/armyskinlib/`), skill `aw2-add-army`.

## 1. The idea: a skin on a colour

AW2 draws an army by its **colour** (player block `+0x1A`: 1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole): palette rows in ROM
tables indexed by colour, and a few per-colour pictures. It has no sixth colour and the engine cannot grow one (the army id is in unit ids, the player
table, the turn order). A skin therefore takes over a colour while the match lasts:

- the ROM image *in the console* holds the skin's palette rows and pictures where the game looks for that colour's;
- the army keeps the colour's **number** everywhere the rules look: only what is drawn (and the names tangoAW2 writes) says the skin's;
- colours are distinct, so one skin on one colour is one more army to choose, on any map: with the five armies' colours and the skins there are six
  choices for at most five seats, and **any seat on any map size can be the skin** with any combination of the others. The skin sits on the colour the seat
  would have had when the other seats' choices leave one free (see `assign`), so on a five-army map it stands in for whichever army's colour nobody else chose.

Not changed: rules (every CO is allowed, no army-specific rules), the CPU (it plays the colour's number), the sim's units, the maps.

## 2. State and what makes it online-safe

- **EWRAM** `0x0203C500` (`army_skin::STATE`, registered in `ram_map.rs`, 16 bytes): `+0..+2` the colour (1..5) skin 0..2 sits on (0 none), `+4..+8` each Teams-screen
  army's choice (0: its colour; else a skin's code), `+0xF` set once the Teams screen has reset them. In the shared console, so rollback, replays, rejoin and every peer agree;
  **`SIM_VERSION` is 44** (44: Silver Nova reads as silver metal and the capture box HQ keeps the tower's proportions: palettes and the box picture changed; 43: the COs Tabitha, Lili and Caulder; 42: the sixth army is Silver Nova: its palette, masks without plumes, HQ and orb are what the console's ROM image holds; 41: the skin leaves the windows' palette row alone, so every window, menu and dialogue box is AW2's own; 40: the online army page's directions repeat like AW2's menus; 39: designs follow the CO and a Silver Nova CO in another colour gets the skin's crest only, `army_skin::crest_plan`; 38: the computer defends its HQ when a foot soldier stands on it in the custom campaigns, `crate::cpu_defend`; 37: the skins' chart soldiers only on the CO page's unit chart; 36: the Silver Nova COs' faces frame the whole head; 35: a skin's palette refresh reaches the sprite palettes only, so the Teams screen's windows stay AW2's own; 34: Asuka's kit; 33: Aria, CO 93, `crate::aria`; 32: Crumb's and Clone Andy's own themes, Crumb's HQ Black Hole's again; 31: the choice is taken back when the Versus map list is up, `army_skin::reset_choice`, so a skin chosen and backed out of no longer stays in the menus or on the next Teams screen; 27: the sim's behaviour changed: the byte, the sixth choice and the ROM image's patches; 28: the Dual Strike backups moved below the skins' figures, see §8).
- **The ROM image** is patched by [`sync`] every tick (`pvp::before_tick`, after `five::sync`), from the state alone, idempotently, per console (waiting views run their own consoles). Free ROM at
  `0x09FC0000` (`DATA`) holds a marker word, which skin is patched on each colour, a list of the **originals** of everything patched (one per colour: `restore` puts them back,
  so a rematch, a room's next match or a skin changing colour is exact), and each skin's own pictures (`art_at`). Writes are word-aligned: `raw_write_32` at an odd halfword aligns down (the first
  version of the backup list was corrupted by exactly that).
- **Only in Versus** (`pvp::in_versus`): the other modes' armies are the story's. A match has its skins from the Teams screen on.
- No pack, no download: the skins are compiled into the app (`FILES` in `army_skin.rs`), so every peer on this version has them; peers on another version do not match (`sim_version`).

## 3. What a skin changes (and where AW2 keeps it)

By **colour** (the colour's rows of tables indexed by colour): `army_skin::TABLES`, 32 bytes a row, found with `aw2dev armyskin sources` (below):

| Table | Address | What |
|---|---|---|
| map units, copy | `0x0810E6E0`, `0x085AD9E8` | unit palette: roles 2..7 the army's ramp, 11..13 trim greys (steel), 14 unused (the skin's crest red) |
| moved units, copy | `0x0810E780`, `0x085ADA88` | the greys of units that have moved (AW2 tints each army's; the skin's is a neutral grey with a breath of its ramp) |
| moving units | `0x0810EA60` | the unit roles at other indices (`MOVE_ROLE`) |
| buildings (two sets) | `0x080D3F04`, `0x080D3E04` | OBJ palettes of the buildings, HQ included (entry 14, magenta and unused in every colour's row, is the skin's gold: `Kind::Building`) |
| HUD and picture palettes | `0x08104264` (OBJ bank 7: the funds box and CO header), `0x08106984` (the info box's property pictures), `0x085A9BBC` (BG 9) | the army's own HUD pieces. **Not** `0x080D4188`, `0x08183C28`, `0x085AC8BC` (one row, BG bank 8: every window, menu, dialogue box and page): they stay AW2's own look for the host colour (`skin_windows_versus`, `skin_windows_gauntlet`) |
| power colours | `0x084F2BC8` (2 rows a colour), Black Hole's copies `0x085765A0`, `0x085766A0` | the battle scenes' unit palettes, the unit panel's portrait and the build menu's pictures (`Kind::Power`: as `Hue`, and entries 14 and 15 of the first row, which no soldier uses, are the skin's `crest` and `crest_dark`: the plume's reds) |
| battle gauge | `0x0816D498` | the HP gauge of a battle scene |
| turn banner | `0x080A1238` (four colours; Black Hole's is `five::BANNER5`) | NEXT TURN banner |
| emblem | the sprite group 1's art of colour `c` and its palette `0x081018E4` (entries per colour) | the army's logo (Teams screens, results) |
| texts | the text table `0x08610A38`, ids 2269.. (names), 3221.. (`The ... Army has lost!`), 3288, 3311 | "Silver Nova" wherever the game names an army |
| Dual Strike | `ds_unit_pictures::PALETTES`, the pack's battle figures | the new units' pictures and battle scenes (with the pack) |
| Dual Strike graphics and tilt | the console's own palettes and tiles (the tilt reads them), `ds_hud` panel palette 7, `ds_co_page` unit chart, `ds_coselect` Teams/CO cards | the same tables as the normal map (the tilt draws the console's picture), the skin's Infantry/Mech slot (`army_skin::map_slot`, read by `ds_tilt::ram_units`), and for the screens that draw from the pack's own palettes `army_skin::ds_row` (`Skin::hue_row` on the pack's five rows) and the emblem from the skin file (`emblem_pixels`) |

A palette that carries the army's colours among others' (buildings, panels) is recoloured by `Skin::hue_row`: the entries that differ between the colours' versions of the table are the army's;
they take the skin's ramp **by brightness rank** (so the skin looks the same on whichever colour it sits).

By **army** (AW2 draws these by the country of the army's CO, `sub_08042DE0`, not by colour; the skin's are handed to the skinned army by traps, `army_skin::traps`):

| Picture | AW2 | The skin |
|---|---|---|
| Infantry and Mech, idle (map) | slot per (country, unit) `u16[5][25]` at `0x08499608`, tiles of the sheet `0x0810BE60` (3 frames), function `sub_080261A4` | trap at `0x080261A6` makes the slot 52 + 2 i (`slot_of`); the pictures are put into VRAM past the sheet every frame (`sync_map_art`); the panel icon (`roster::panel_icon`) reads them through `icon_source` |
| Infantry and Mech, moving | LZ77 sheet per (unit, country) in the table `0x0849CD88`, function `sub_08035B3C` | trap at `0x08035B40` returns the skin's sheet (the country's with the helmet patches laid on the frames: `moving_patches`, found by the helmet's top row) |
| Battle-scene Infantry and Mech | LZ77 sheets of 32x32 frames (16 tiles, 1D) per country, `0x085D64A8[5 * type + country]` (15 words; the soldiers are type 1 for both units: words 0 and 4 are the two sheets, the rifle's and the bazooka's), decompressed to a staging buffer and copied to the OBJ tiles; `FIG_LOAD` `0x080568E2` holds the sheet's address in `r0` | trap at `FIG_LOAD`: for a skinned side (`SIDE_COLOURS` `0x03004500`, one BYTE a side, `SIDE_UNITS` `0x03004528`; it was read as halfwords, so the second side always looked like colour 1 and Black Hole's soldiers wore the helmet when the skin sat on colour 1: scenarios `bt_*`, which check no plume colours on the other side for every terrain pair) the sheet becomes the skin's (Green Earth's with the helmet laid on every frame, `patch_figures`, compressed with `lz77_compress` into free ROM; the table of their addresses is read from the ROM image) |
| the unit panel's portrait | one LZ77 32x32 picture per (type, country), `0x0849DC18 + 0x14 + 4 * (15 * type + country)`, loaded by `sub_0803A190` to OBJ tile `0x2E8` | trap at `PORTRAIT_LOAD` `0x0803A1D8`: `r0` becomes the skin's patched portrait (the army is at `*[*0x08090F70] + 8`) |
| the CO page's unit chart (AW2's own page) | `sub_08085950` queues a copy of the sheet's `0x6C` tiles (slots 0..26) to OBJ VRAM `0x06012000` and draws units by slot, so the skin's slots (52+) pointed at empty VRAM | `sync_map_art` also keeps the skin's first idle frames at `0x06012000 + 128 * slot` while the main loop is the CO page's (`CO_PAGE_LOOP`); scenario `copage` |
| the capture box (soldier and building) | `sub_08041128` (soldier: 16x32, four frames, LZ77 by country `0x0849FD6C[country]` to `0x06014940`, OBJ palette bank 4) and `sub_0804103c` (property: 32x64 by terrain class, queued copy to OBJ bank 5): both take their palette from the row `0x081213F4 + 32 * colour` | the row is in `TABLES` ("capture box", `Kind::Hue`): every property and the soldier wear the skin's colours, as the capturer and as the old owner. Traps `CAPTURE_SOLDIER_END` (the skin's Green Earth soldier with the `[capture]` plume of the skin file laid on each frame, the crest in palette entries 2 and 3), `CAPTURE_PROPERTY_COPY` and `CAPTURE_PROPERTY_END` (an HQ owned by a skinned army: the map HQ at twice the size, its gold in entry 13). Art in free ROM at `art_at + 0x600` and `+ 0xA00` (`capture_blobs`). Scenarios `capture`, `capture_from_es_<kind>`, `capture_from_bh_<kind>` |
| HQ | art per country at `0x080D16C4` / `0x080D1BC4` (snow), loaded by `sub_0803F5E4` | trap at its end (`0x0803F698`) puts the skin's 16x32 art into the army's tiles (and army 5's lab tiles in a five-army game) |

Crumb (CO 82, Dual Strike pack) is Black Hole's: Black Hole's HQ tower and units (he used the first skin's HQ as a placeholder until 0.8.10).

Still the colour's: the CO's national emblem on the CO page (it is the CO's country, not the army), the terrain.

## 4. The data file (`skins/<id>.toml`)

```toml
id = "emerald_sun"; name = "Silver Nova"; short = "ES"
[colours]                       # RRGGBB
ramp = [6 colours, light to dark]   # unit roles 2..7, every building, panel and gauge by rank
trim = [3 colours]                  # unit roles 11..13 (tracks, barrels, the cheek plate): steel
building = [4 colours]              # optional: the buildings' own ramp, light to dark (else the units' ramp)
crest, gold, gold_dark              # crest (unit role 14: no picture draws a plume any more), gold: the HQ's lit windows (entry 14 of the building palettes)
emblem_tones = [3 colours]          # optional: the emblem's c, b, a tones (default the ramp's 0, 4, 2): Silver Nova's are darker greys so the sun reads as shaded metal on the Teams card's white
orb = [3 colours]                   # optional: the HQ's orb, light to dark: building palette entries 12, 11 and 8 (`ORB_ENTRIES`, only the HQs' pictures use them; the capture box's HQ gets them too); an HQ row says c, b, 8
moved_tint = 0.5                    # how much of the ramp's hue the grey of a moved unit keeps
moved_dim = 0.64                    # how bright it stays (the skin's own dimmed ramp; still readable)
moved_lift = 0.3                    # the darker entries of a moved unit's greys (6..14) are lifted by this much first: a done unit is not black
[infantry] / [mech]
base = 3                            # AW2's picture of this colour's soldier is the start
[[infantry.patch]]  frames = [0,1,2]  x = 0  y = 0  rows = [ ... ]   # `.` keep, `_` clear, hex digit = unit palette index (b c d the steel trim, e crest, f outline)
  moving = [0,1,2]  anchor = [6,1]   # also on those frames of the moving sheet (0..2 sideways, 3..5 front, 6..8 back), the point `anchor` of `rows`
                                     # lying on the left outline of the helmet's top row (found in the frame); `frames = []` for a moving-only patch
[infantry.moving] crest = true      # (older way) a plain crest over every moving frame's helmet; Silver Nova draws its crest with patches instead
[battle.infantry]  dome = [12, 9]  x = 2  y = -3  rows = [ ... ]   # the helmet at the battle figures' size (see below); also [battle.mech], [portrait.infantry], [portrait.mech]
[hq]       rows = [32 rows of 16]   # `.` clear, hex digits = the building palette's index (1 white, 2..5 the body ramp light to dark, b shadow)
[emblem]   rows = [16 rows of 16]   # 1 white, 2 shadow, a b c = the mid, dark and light tones of the skin's ramp (`ramp[2]`, `ramp[4]`, `ramp[0]`; they go to the three emblem entries of the colour the skin sits on; Black Hole has one entry: all three); used by the game's own emblem
                                    # (Teams screens, results) and drawn from the file for Dual Strike's Teams and CO-pick cards; the pick flags are recoloured from the flag's own tiles (`recolour_entries`)
```

Register the file in `FILES` (`army_skin.rs`, at most `MAX_SKINS` = 3): its choice code is `SKIN + index`, shown on the army pages and cycled with the five armies.

**Battle figures and portraits** (`[battle.infantry]`, `[battle.mech]`, `[portrait.infantry]`, `[portrait.mech]`). The battle scene's soldiers and the unit panel's portrait are 32 x 32 pictures drawn from AW2's
LZ77 sheets, so a skin's helmet is laid on them as data too: `dome = [w, h]` is the size of the helmet block (the soldiers' 12 x 9 army-coloured pixels, palette entries 2..5, above the face: the first row with a skin
tone, entries 8..10), `x`, `y` where `rows` start from that block's top-left corner (they may be negative: the plume rises above it), and `rows` are hex digits (a figure palette entry: 7 the outline, 1 white,
b c d the steel greys, e the skin's `crest`, f its `crest_dark`: entries 14 and 15, free in the soldiers' palette), `.` keep, `_` clear. The engine finds the block on each frame of the soldiers' two sheets (Green Earth's, as
the map pictures' `base`) and lays the rows there; a frame without such a block (a soldier falling over) is left as it is. `[battle.infantry]` and `[battle.mech]` both end up on the same sheets (the Mech uses the soldiers'
frames): the Mech's own is used for the Mech's side, and one copy is kept when they are equal. `crest_dark` is optional in `[colours]` (default: the crest darkened). `armyskin check` compares the engine's frames with the rules
applied in Python (`armyskinlib/figures.py`), (Silver Nova's patches have no plume: only the face mask, so `check --live` no longer looks for the crest's red; the other army's soldiers are still checked for the plume's palette entries.)

## 5. Choosing the army

- **Online** (rooms, UNRANKED): the army page (`online_teams.rs`) cycles a seat's colour field through Orange Star, Blue Moon, Yellow Comet, Green Earth, Black Hole and the skins
  (LEFT from Orange Star is the skin); the choices become the game's colours when every seat is READY (`write_choices`, `assign`). The chip is the skin's colour; the app's legend and status bar
  use `tango_library::online::skin_accent`.
- **Offline Versus**: the game's own Teams screen: R / L (or SELECT without the Dual Strike pack) cycle the highlighted army through the six (`pvp::before_tick`, `army_skin::teams_step`);
  on a five-army map the colours are the armies' own and R / L put a skin on the army or take it off. The emblem and the army names follow at once (`refresh_palettes`: sprite palettes only; AW2 paints this screen's windows in Orange Star's colours whatever the armies, `test_teams_look.py`).
- The replaced colour is not offered to another seat while a skin sits on it; a seat that picks it later moves the skin to the next free colour.

## 6. Kit: `aw2dev armyskin`

| Command | What |
|---|---|
| `preview [--colour N] [--fast]` | the skin's pictures (Infantry, Mech, HQ, emblem) next to AW2's at 8x, and its palettes, as one PNG (`--fast` draws the art straight from the data file: no rebuild while drawing) |
| `check [--live] [--scenario S ..] [--ds]` | **static**: the data file's shapes; the palette's margins; every unit 1..24 on every colour is recoloured and its done grey differs from its live colours. **`--live`**: runs the catalogue's scenarios three times (the base army, another colour, the skin) and fails on any screen where a colour only the base army had is still there |
| `palette-options --dir DIR [--letters ABCDEF] --out PNG` | one comparison sheet of candidate palettes (`DIR/A.toml` ...: `name`, `description`, a `[colours]` table of overrides): per letter the skin file is swapped in for the run (always restored), the harness example rebuilt, and the real game draws the units idle and done (Dual Strike), the property capture boxes, a map crop beside an unowned city, Blue Moon and Black Hole; the HQ and emblem from the file; the static check's distances and the city's distance from the unowned city are under each row |
| `import-hq PICTURE [--write] [--sheet PNG]` | the owner's upscaled HQ picture imported faithfully as the skin's `[hq]` rows (section 9) |
| `sources [--a 1,2 --b 3,4]` | renders the screens with two armies, finds the palette banks that differ, searches the ROM for their colours and prints the **ROM palettes the skin does not patch yet** (the way to find the next table) |
| `options --dir DIR [--letters ACF] [--awbw DIR]` | a sheet of **soldier options**: several complete Infantry + Mech designs (idle side frame) from candidate files `A.toml`, `B.toml` ... in DIR, one row per letter with a description, each at 8x and 1x and on a plain map tile at 2x beside Green Earth's and Black Hole's Infantry (and AWBW's pair on top with `--awbw`, review only). A candidate is a skin fragment: `name`, `description`, optional `[colours]` overrides (`trim`, `crest`, `ramp`) and the skin file's own `[infantry]` / `[mech]` patch tables, so the chosen letter is merged into `skins/<id>.toml` as it is. `armyskinlib/options.py` has `grid_of` (AW2's soldier as a grid), `patch_rows` (draw on a copy and let the difference become the patch) and `toml_for` to author them; candidates stay out of the repository until one is chosen |
| `matrix [--quick] [--armies N ..] [--colours C ..] [--no-ds]` | the skin on **every colour 1..5 in every army count 2..5** with the Dual Strike pack (released 0.8.7 corrupted the game's memory when the skin sat on colour 5 with the pack: the pack's backup of colour 5 lay over the skin's table of battle figures, see §8): per run the harness's `skincheck` (`army_skin::self_check`: the figure table's pointers are LZ77 streams in the skin's room, the backup lists are whole entries) before and after the panel, the build menu and a battle; the plume's red in the unit panel, both build-menu portraits and the three battle shots. Where the map does not give the skin the colour, the test aids `aid colour 1 C` and `aid skincolour C` move it as a campaign mission does. `--quick` (four of the twenty) is in `aw2dev suite` |
| `catalogue` | the scenarios: `units` (idle, done, HQ, build menu, panel), `parade` (every unit), `battle`, `power`, `capture`, `turn` (hand-off and DAY banners), `results`, `lost3p` ("The Silver Nova Army has lost!"), `rematch` (the room's next match on the same console has no trace of the skin), `map5p` (the skin with Green Earth and Black Hole on a five-army map), `hqs` (the five HQs on the map, side by side), `battle_mech` (a Mech against a Tank), `dsunits` and `crumb` (with the pack), `tilt` and `tilt5p` (the Dual Strike tilted map from the real app, with the pack: `check --live --ds` compares its picture the same way) |
| `scenario NAME [--ids 6,2] [--ds]` | runs one scenario and keeps its shots (for sheets) |
| `checkpoint NAME [--scenario S] [--ids ..] [--ds]` and `look NAME [--ds] [--tilt] [--tilt-scale N]` | save a scenario's end state, then boot the real app from it through the AI debug channel and take its own picture (`--tilt`: the Dual Strike tilted map, `--tilt-scale 4` the hi-res picture; it needs the pack and sets `TANGOAW2_TILT_NO_GROUNDCHECK`, see `env-aids.md`) |

Scenario scripts are generated (`armyskinlib/scenarios.py`; identities are poked into the army page: 1..5 the colours, 6 the first skin) and run by the harness (`aw2_room_teams`, no network). The units a script places with
the test aid appear once the map has been redrawn (it opens and closes the map menu). `aw2dev live ... ` with `AW2DEV_SKIN=1` has seat 0 pick the skin (LEFT on its colour field) in real app clients:
`AW2DEV_SKIN=1 aw2dev live moveview --local`, `AW2DEV_SKIN=1 aw2dev live lobby --players 3 --local` (hashes agree, no leak, no stall). The skin code writes only to the match's console through `plan`/`apply` on the simulation's own tick (peers apply the same writes); `aw2dev net repeat` (2P Unranked, 8 runs, hashes equal on every run) is the regression for a skin that makes peers differ.
Offline: `aw2_skin_offline <rom> <out> [cpu]` walks the game's own Teams screen to the skin (and with `cpu` lets the CPU play it).

Tests: `cargo test -p tango-gamesupport-aw2 --lib army_skin` (+ `-- --ignored` with `TANGOAW2_AW2_ROM` for the plan on the real ROM), `aw2dev test` (the kit's python tests: committed scripts equal their generators, a green skin is refused),
`aw2dev suite` (`static`, `live`, `aw2_skin_units_2p`, `aw2_skin_5p` and the gfx catalogue's `emerald_sun_units` / `emerald_sun_5p`: golden frames made with `aw2dev gfx golden`).

### The palette's margins (`check`, in `armyskinlib/check.py`)

CIE76 delta E between the skin's **body colours** (ramp 1..4) and:

| Against | Needs | Silver Nova |
|---|---|---|
| each of AW2's five armies' body colours (ramp 2..7 of the unit palette): the closest pair | >= 10 | Orange Star 48.8, Blue Moon 18.8, Green Earth 32.5, Yellow Comet 43.9, Black Hole 11.4 |
| ... and the mean over the four body colours of the distance to that army's nearest colour | >= 16 | 54.9, 35.7, 40.8, 52.8, 17.9 |
| chroma, as a share of Green Earth's body chroma (a stone, not a leaf green) | <= 0.4 | 0.06 (6.0 of 97.5) |
| the greys of units that have moved (all five armies) | >= 9 | 11.4 |
| the terrain's colours in fog (measured with fog on) | >= 9 | 12.2 |
| the skin's own done unit against its live unit (on each of the five colours it can sit on) | >= 10 | 28.4 .. 35.4 |
| the skin's done ramp against the other armies' done greys (still the skin's) | >= 6 | 9.7 .. 32.9 |

Silver Nova's units are **silver metal** (the owner's rejected the blue-grey as not silver, picked bright chrome, then found it read white on the grass): `F2F2FA BDBDC5 A4A4AC 8C8F98 363A44 16181E`, one near-white specular step, then neutral greys with a faint cool tint, hard contrast, steel trim `C4C7CE 8A8E98 4A4D55`. The 15-bit palette decides what is possible: neutral greys between L 88 and 94 sit within 10 of Black Hole's `DEE6DE`, and the old `F0F2F8` only cleared it by being near white, so the step goes below that band (Black Hole 14.3, done greys 10.5, fog 10.2). A done unit is AW2-like mid grey: `moved_dim` 0.7, `moved_tint` 0.0 (a cool tint put it within 6 of Blue Moon's and Yellow Comet's done greys; neutral keeps 6.6 .. 7.8), `moved_lift` 0.15 (a high lift flattened the done unit: shadows lighter than the body); against the live ramp it is 16.1 .. 25.2. (`check` now reads the candidate file for the palette rows too, not only for the art.) The capture box's HQ: the box draws its 32 x 64 picture at half height, so the tower's rows are doubled and it sits centred at its own width (`hqimport.capture_rows`, `import-hq --capture`); `check` measures its drawn width/height against the map HQ's (0.52 both).
Its buildings have their own chrome ramp (`building`, four tones `FFFFFF BCC1C9 6C717C 444852`: white panels and dark greys, far from an unowned city's pale ones; 11.4 from the unowned city beside it), used for the building palettes only; the HQ's windows are the picture's yellow (`gold`) and its orb has three greens (`orb`). Black Hole's greys are the nearest colours (its highlights
are grey too: the army differs by its purple body, so the mean over its colours is the looser margin), and fog's grey-greens set the floor on lightness. A skin that is too grey is read as a done unit or as fogged ground;
one too saturated is Green Earth. A unit that has moved takes the skin's own dimmed ramp (`moved_tint`, `moved_dim` 0.5): the ramp at half its brightness.

### Originality (`check --awbw-ref DIR`, local only)

Silver Nova no longer has anything of the Jade Sun that inspired it as Silver Nova: its HQ is the owner's own art, its soldiers wear the mask without the Roman plume. The check stays for the next army that is
drawn after a reference (the repository is public and nothing of AWBW's may be in it: look, then draw, never trace). The table below is the old Silver Nova design's, for the scale of the numbers.

`aw2dev armyskin check --awbw-ref DIR` measures it. DIR holds the reference pictures (`jsinfantry.gif`, `jsmech.gif`, `jadesunhq.gif`, `jslogo.gif`; fetched by hand, kept outside the repository, never committed);
the check needs them, so it only runs where they are. What separates a drawing from a copy is how many *pixels* are the same: a hand redraw matches the shapes and rarely the pixels, a copy matches nearly all of them.
So the check counts the share of **our** foreground pixels that sit where the reference has a pixel of the same **colour class** (clear, red, yellow, or one of five brightness steps; the colour itself is ignored), at the best
offset (up to 2 pixels, mirrored too), and fails above **0.78**. The threshold sits above what a close hand redraw reaches (the shared AW2 soldier alone gives about 0.5) and below a copy's (about 0.9 and over).

| Picture | Share in the same place and class | Needs |
|---|---|---|
| Infantry (idle frames 0, 1, 2) | 0.42, 0.36, 0.34 | <= 0.78 |
| Mech (idle frames 0, 1, 2) | 0.53, 0.53, 0.44 | <= 0.78 |
| HQ | 0.63 | <= 0.78 |
| Logo | 0.40 | <= 0.78 |

Sheet 03 prints the score under each pair of pictures.

### The HQ's depth (`check`, `hq_metrics`)

An HQ is 16 x 32 palette indices. AW2's five get their depth from one dominant mid shade (62 to 74 % of the pixels) with a lighter lit shade on the left and top, a few bright accents, a few dark details,
the picture filling from row 1 to 5 down to the bottom, the left columns brighter than the right. The check measures these on the five and the skin's HQ must lie in their range (the allowed band is wider: the skin's HQ has a
dark outline all round, like theirs, and AWBW's own are paler and flatter):

| Measure | AW2's five | Allowed | Silver Nova |
|---|---|---|---|
| pixels filled | 367 to 404 (of 512) | 341 to 444 | 416 |
| shades used | 6 to 9 | 6 to 12 | 8 |
| the commonest shade's share | 0.62 to 0.74 | 0.28 to 0.89 | 0.49 |
| value contrast (std. dev. of brightness) | 25 to 39 | 23 to 69 | 68 |
| first row used | 1 to 5 | at most 5 | 0 |
| left three columns against the right three | brighter on the left | the left brighter | 176 against 154 |

## 7. Adding an army (skill `aw2-add-army`)

1. `aw2dev armyskin preview --fast` while you draw: write `skins/<id>.toml` (copy Silver Nova's), start with the ramp and trim.
2. Add the file to `FILES`; `aw2dev build --all`; `aw2dev armyskin check` (palette margins) and `check --live`.
3. Draw the Infantry/Mech patches, the HQ and the emblem; `preview` again; look at the screens (`scenario units`, `parade`, `battle`, `map5p`) in `devkit/work/armyskin/`.
4. `aw2dev armyskin sources` must print nothing; `AW2DEV_SKIN=1 aw2dev live moveview --local` and `lobby --players 3 --local`; `aw2dev suite`.
5. Credits for inspiration go in `CREDITS.md`; the art is yours (never trace another project's pictures; look, then draw).

## 8. Limits

- The battle-scene soldiers and the portraits have the helmet on every frame that has a helmet block; the falling-over frames (three of each sheet) keep AW2's helmet in the skin's colours. The figures' sheets are patched where the scene loads them rather than on the tile copy, so every frame, terrain and scale has them (the scene has one figure size).
- Free ROM ends at `0x09FE0000` (the console's ROM image): the skins' room for battle pictures is the 36 KB between the backups and the map pictures, 12 KB a skin, which is why the sheets are compressed.
- **The rooms must not overlap each other or any other module's** (0.8.7: the Dual Strike pack's backup of colour 5 sat at `DATA + 0x7000`, over the first skin's table of figures and portraits, so a skin on colour 5 with the pack made the build menu, the unit panel and the battle scene hand the game a pointer into a palette backup, and the game decompressed over its memory). Layout, in `DATA = 0x09FC0000`: header `+0..0x100`, the five colours' backups `+0x100 + 0x1000 (c-1)` (0xF00 each), the five Dual Strike picture-palette backups `+0x5000 + 0x400 (c-1)` (0x3F0 each), the skins' figures `+0x7000 + 0x3000 k`, their pictures and texts `+0x10000 + 0x4000 k`. `cargo test -p tango-gamesupport-aw2 --lib rom_layout` lists every range in the image's free space (`0x08800000..0x0A000000`: the music, Survival, the wheels, the looks, the Dual Strike Campaign, the maps, the graphics, the skins) and fails when two overlap, one leaves the image, or a module names an address there that no listed range covers; `the_rooms_in_free_rom_are_apart` and the compile-time asserts keep the skins' own. The same test found `skills_panel`'s backup inside the fourth look (the Grand Bolt's) and moved it.
- Up to three skins at once (slots 52..57, one colour each); more needs more slot room (`slot_of`).
- The Dual Strike graphics mode and the tilted map (and its hi-res picture) show the skin: the tilt is a host-side overlay of the console's picture, so the palettes, the helmets (the skin's slot instead of the CO's country's), the HQ and the properties are the console's own; the pack's own screens (the CO panel's palette, the CO page's unit chart, the Versus and CO-pick cards with the emblem) take their colours from the skin file. Dual Strike's own pictures of Infantry and Mech are not drawn for the skin (the crested soldiers are AW2-style pixel art: the skin's soldiers keep them in every mode).


## Designs follow the CO, colours only recolour
**The rule (the user's, said more than once):** a CO's unit designs and HQ belong to the CO's own nation; an army colour only recolours them. A skin therefore has two separate things:

| | Decided by | Code |
|---|---|---|
| the **palette** (the army's colours, panels, emblem, texts, the names) | the army's *colour*: the skin sits on a colour (`skin_on`, `skin_installed_on`) | `plan`, `sync` |
| the **designs** (Infantry and Mech on the map, idle and moving, battle figures, the unit panel's portrait, the capture box's soldier and HQ, the HQ on the map, the Dual Strike tilt's unit slots) | the army's *CO* (`design_style`, `design_skin`, `design_on_colour`) | the traps in `traps()`, `map_slot`, `hq_loaded` |

So an Silver Nova CO (Tabitha, Lili, Caulder: the CO data files with `hq = "emerald_sun"`, `nation_skin`) has the skin's plumed soldiers and domed HQ in **whatever colour** its army wears, and every
other CO has its own nation's: AW2 draws those by the CO's country already (Black Hole's own tower and soldiers for Hawke, Lash, Adder, Flak, Sturm, Jugger, Koal, Kindle, Von Bolt, Asuka, Crumb; Orange Star's for Andy and
Aria ...), so the traps simply leave them alone, in the skin's palette when the army wears the skin. Bug of 0.9.0: every trap asked "does this army wear the skin?" (by colour), so Asuka in the Silver Nova colour got the plumes and the domed HQ.

A Silver Nova CO whose army wears another colour has the skin's designs in that colour's palette: `army_skin::sync` installs **the crest only** on that colour (`crest_plan`: the plume's red in the unit rows' entry 14 and the
moving rows', the battle scene's entries 14 and 15, the HQ's gold in the buildings' entry 14 and its orb's greens in entries 12, 11 and 8 (`building_extras`), everything else of the row stays the colour's; `applied_at` holds `0x11 + skin`, `crest_on`). Where a campaign forces the skin on
an army (the Silver Nova Campaign's player, a custom mission's skinned army: `forced_skin`) the army keeps the skin's designs whatever its CO.

Not changed on purpose: the emblem on the Teams screens and the army box is the colour's (the skin's sun, in its palette) wherever the skin sits; the CO cards, results and the HUD are palettes. The cursor's info panel draws its own small HQ icon, which stays the game's.
Test: `python3 tools/aw2test/run.py -k army_designs --mode ds` (a Black Hole CO, a base CO and a Silver Nova CO in the skin's colour, and a Silver Nova CO in a base colour: the pictures compared as shapes, the palette checked).

## The HQ follows the CO (`hq = "<skin id>"` in `cos/<id>.toml`)
An army shows a skin's HQ picture (the domed tower, `[hq] rows` of `skins/<id>.toml`) when its CO's data file says `hq = "<skin id>"` (`army_skin::hq_style`, `hq_skin`, put into OBJ VRAM at the end of the game's HQ loader,
`hq_loaded`) and not merely because the army wears the skin colour (see above). Tabitha, Lili and Caulder have `hq = "emerald_sun"`; `"default"` keeps the game's HQ of the CO's country (Clone Andy). The HQ follows the CO that starts the battle (a Tag pair: the lead).
The picture is indexed in the building palette, so it is drawn in the **army's own building colours** (red for Orange Star, a Black Hole army's purple, the skin's green on the skin's army). Without this the HQ came from the country
of the CO the data was based on (the old Klaus: Kanbei's, Yellow Comet's pale-green tower). `aw2dev co verify` (facet `hq`), `aw2dev campaign check --hq` and `aw2dev co sheet hq` check and show it. Not covered: the cursor's info panel
draws its own small HQ icon, which stays the game's.

## 9. Importing the owner's pictures (`aw2dev armyskin import-hq`)
The user's rule: their art is imported, never drawn or "improved". `aw2dev armyskin import-hq art-src/silver-nova/hq.jpg [--write] [--sheet PNG]` (`armyskinlib/hqimport.py`) finds the pixel grid of an upscaled
pixel-art picture (period and phase of the strongest edges), samples each cell (the median of its middle, so JPEG noise goes), removes the grass the HQ stands on (the cells of the grass family joined to the sprite's
edge), and maps every other cell to the nearest of the picture's own few colours, written as the skin's `[hq]` rows: white 1, the pale panel 2, the body 4, the shade 5 (building ramp tones 1, 3, 4: the skin's
`building` ramp is the owner's city picture's), the yellow windows `e` (`gold`) and the orb's three greens `c`, `b`, `8` (`orb`). `--sheet` writes the picture beside the imported pixels. Nothing is added or smoothed.
Silver Nova's HQ is 416 of 512 cells; the source pictures are in `art-src/silver-nova/`.

The Roman-specific bits that remain after the rename (for the owner to decide): the Roman COs and their data (`hq = "emerald_sun"`, `nation_skin`, bios, dialogue, campaign mission names, music files `music/es/`) belong to the CO branch; in this branch the plumes
(white-silver since the rename, then removed) are gone from every picture; the `crest` / `crest_dark` colours stay in the skin file and are still written to unit palette entries 14 and 15 (nothing draws with them); the sun emblem keeps its shape (silver).
