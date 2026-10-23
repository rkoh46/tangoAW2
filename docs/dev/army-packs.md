# Army skins: Emerald Sun, and how to add the next army

tangoAW2 has a sixth army, **Emerald Sun**, and a general way to add more: an army is a **skin**, a data file (`tango-gamesupport-aw2/skins/<id>.toml`)
that the game draws on top of one of AW2's five colours. Everything in the file is original work of this repository (GPL-3.0-or-later): colours and
pixel art drawn here, applied at run time to AW2's own graphics, which are read from the player's ROM as always. Nothing from any game (or from AWBW)
is in the repository. Emerald Sun is *inspired by* the Jade Sun army of Advance Wars By Web (AWBW; credited in `CREDITS.md`): its Roman legionaries
with red-crested helmets, its temple and its sun; no AWBW picture was copied or traced (it was looked at, and only in review sheets, never committed).

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
  **`SIM_VERSION` is 27** (the sim's behaviour changed: the byte, the sixth choice and the ROM image's patches).
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
| map units, copy | `0x0810E6E0`, `0x085AD9E8` | unit palette: roles 2..7 the army's ramp, 11..13 trim greys (the helmets' bronze), 14 unused (the skin's crest red) |
| moved units, copy | `0x0810E780`, `0x085ADA88` | the greys of units that have moved (AW2 tints each army's; the skin's is a neutral grey with a breath of its ramp) |
| moving units | `0x0810EA60` | the unit roles at other indices (`MOVE_ROLE`) |
| buildings (two sets) | `0x080D3F04`, `0x080D3E04` | OBJ palettes of the buildings, HQ included (entry 14, magenta and unused in every colour's row, is the skin's gold: `Kind::Building`) |
| CO panel, HUD panels | `0x080D4188`, `0x08183C28`, `0x085A9BBC`, `0x085AC8BC`, `0x08104264`, `0x08106984` | the CO panel, windows and menus, the HUD |
| power colours | `0x084F2BC8` (2 rows a colour), Black Hole's copies `0x085765A0`, `0x085766A0` | the battle scenes' unit palettes and the build menu's pictures |
| battle gauge | `0x0816D498` | the HP gauge of a battle scene |
| turn banner | `0x080A1238` (four colours; Black Hole's is `five::BANNER5`) | NEXT TURN banner |
| emblem | the sprite group 1's art of colour `c` and its palette `0x081018E4` (entries per colour) | the army's logo (Teams screens, results) |
| texts | the text table `0x08610A38`, ids 2269.. (names), 3221.. (`The ... Army has lost!`), 3288, 3311 | "Emerald Sun" wherever the game names an army |
| Dual Strike | `ds_unit_pictures::PALETTES`, the pack's battle figures | the new units' pictures and battle scenes (with the pack) |

A palette that carries the army's colours among others' (buildings, panels) is recoloured by `Skin::hue_row`: the entries that differ between the colours' versions of the table are the army's;
they take the skin's ramp **by brightness rank** (so the skin looks the same on whichever colour it sits).

By **army** (AW2 draws these by the country of the army's CO, `sub_08042DE0`, not by colour; the skin's are handed to the skinned army by traps, `army_skin::traps`):

| Picture | AW2 | The skin |
|---|---|---|
| Infantry and Mech, idle (map) | slot per (country, unit) `u16[5][25]` at `0x08499608`, tiles of the sheet `0x0810BE60` (3 frames), function `sub_080261A4` | trap at `0x080261A6` makes the slot 52 + 2 i (`slot_of`); the pictures are put into VRAM past the sheet every frame (`sync_map_art`); the panel icon (`roster::panel_icon`) reads them through `icon_source` |
| Infantry and Mech, moving | LZ77 sheet per (unit, country) in the table `0x0849CD88`, function `sub_08035B3C` | trap at `0x08035B40` returns the skin's sheet (the country's with the helmet patches laid on the frames: `moving_patches`, found by the helmet's top row) |
| HQ | art per country at `0x080D16C4` / `0x080D1BC4` (snow), loaded by `sub_0803F5E4` | trap at its end (`0x0803F698`) puts the skin's 16x32 art into the army's tiles (and army 5's lab tiles in a five-army game) |

Crumb (CO 82, Dual Strike pack) uses the **first skin's HQ** as a placeholder for one of his own (`hq_skin`).

Still the colour's: the CO's national emblem on the CO page (it is the CO's country, not the army), the terrain.

## 4. The data file (`skins/<id>.toml`)

```toml
id = "emerald_sun"; name = "Emerald Sun"; short = "ES"
[colours]                       # RRGGBB
ramp = [6 colours, light to dark]   # unit roles 2..7, every building, panel and gauge by rank
trim = [3 colours]                  # unit roles 11..13 (tracks, barrels): bronze
crest, gold, gold_dark              # crest red (unit role 14), the sun
moved_tint = 0.5                    # how much of the ramp's hue the grey of a moved unit keeps
moved_dim = 0.78                    # how bright it stays (the skin's own dimmed ramp; still readable)
[infantry] / [mech]
base = 3                            # AW2's picture of this colour's soldier is the start
[[infantry.patch]]  frames = [0,1,2]  x = 0  y = 0  rows = [ ... ]   # `.` keep, `_` clear, hex digit = unit palette index (b c d the bronze trim, e crest, f outline)
  moving = [0,1,2]  anchor = [6,1]   # also on those frames of the moving sheet (0..2 sideways, 3..5 front, 6..8 back), the point `anchor` of `rows`
                                     # lying on the left outline of the helmet's top row (found in the frame); `frames = []` for a moving-only patch
[infantry.moving] crest = true      # (older way) a plain crest over every moving frame's helmet; Emerald Sun draws its galea with patches instead
[hq]       rows = [32 rows of 16]   # `.` clear, hex digits = the building palette's index (1 white, 2..5 the body ramp light to dark, b shadow)
[emblem]   rows = [16 rows of 16]   # 1 white, 2 shadow, a b c = the dark, mid, light entry of the emblem colour the skin sits on (Black Hole has one entry: all three)
```

Register the file in `FILES` (`army_skin.rs`, at most `MAX_SKINS` = 3): its choice code is `SKIN + index`, shown on the army pages and cycled with the five armies.

## 5. Choosing the army

- **Online** (rooms, UNRANKED): the army page (`online_teams.rs`) cycles a seat's colour field through Orange Star, Blue Moon, Yellow Comet, Green Earth, Black Hole and the skins
  (LEFT from Orange Star is the skin); the choices become the game's colours when every seat is READY (`write_choices`, `assign`). The chip is the skin's colour; the app's legend and status bar
  use `tango_library::online::skin_accent`.
- **Offline Versus**: the game's own Teams screen: R / L (or SELECT without the Dual Strike pack) cycle the highlighted army through the six (`pvp::before_tick`, `army_skin::teams_step`);
  on a five-army map the colours are the armies' own and R / L put a skin on the army or take it off. The emblem, the screen's window colours and the army names follow at once (`refresh_palettes`).
- The replaced colour is not offered to another seat while a skin sits on it; a seat that picks it later moves the skin to the next free colour.

## 6. Kit: `aw2dev armyskin`

| Command | What |
|---|---|
| `preview [--colour N] [--fast]` | the skin's pictures (Infantry, Mech, HQ, emblem) next to AW2's at 8x, and its palettes, as one PNG (`--fast` draws the art straight from the data file: no rebuild while drawing) |
| `check [--live] [--scenario S ..] [--ds]` | **static**: the data file's shapes; the palette's margins; every unit 1..24 on every colour is recoloured and its done grey differs from its live colours. **`--live`**: runs the catalogue's scenarios three times (the base army, another colour, the skin) and fails on any screen where a colour only the base army had is still there |
| `sources [--a 1,2 --b 3,4]` | renders the screens with two armies, finds the palette banks that differ, searches the ROM for their colours and prints the **ROM palettes the skin does not patch yet** (the way to find the next table) |
| `catalogue` | the scenarios: `units` (idle, done, HQ, build menu, panel), `parade` (every unit), `battle`, `power`, `capture`, `turn` (hand-off and DAY banners), `results`, `lost3p` ("The Emerald Sun Army has lost!"), `rematch` (the room's next match on the same console has no trace of the skin), `map5p` (the skin with Green Earth and Black Hole on a five-army map), `hqs` (the five HQs on the map, side by side), `dsunits` and `crumb` (with the pack) |
| `scenario NAME [--ids 6,2] [--ds]` | runs one scenario and keeps its shots (for sheets) |

Scenario scripts are generated (`armyskinlib/scenarios.py`; identities are poked into the army page: 1..5 the colours, 6 the first skin) and run by the harness (`aw2_room_teams`, no network). The units a script places with
the test aid appear once the map has been redrawn (it opens and closes the map menu). `aw2dev live ... ` with `AW2DEV_SKIN=1` has seat 0 pick the skin (LEFT on its colour field) in real app clients:
`AW2DEV_SKIN=1 aw2dev live moveview --local`, `AW2DEV_SKIN=1 aw2dev live lobby --players 3 --local` (hashes agree, no leak, no stall). The skin code writes only to the match's console through `plan`/`apply` on the simulation's own tick (peers apply the same writes); `aw2dev net repeat` (2P Unranked, 8 runs, hashes equal on every run) is the regression for a skin that makes peers differ.
Offline: `aw2_skin_offline <rom> <out> [cpu]` walks the game's own Teams screen to the skin (and with `cpu` lets the CPU play it).

Tests: `cargo test -p tango-gamesupport-aw2 --lib army_skin` (+ `-- --ignored` with `TANGOAW2_AW2_ROM` for the plan on the real ROM), `aw2dev test` (the kit's python tests: committed scripts equal their generators, a green skin is refused),
`aw2dev suite` (`static`, `live`, `aw2_skin_units_2p`, `aw2_skin_5p` and the gfx catalogue's `emerald_sun_units` / `emerald_sun_5p`: golden frames made with `aw2dev gfx golden`).

### The palette's margins (`check`, in `armyskinlib/check.py`)

CIE76 delta E between the skin's **body colours** (ramp 1..4) and:

| Against | Needs | Emerald Sun |
|---|---|---|
| each of AW2's five armies' body colours (ramp 2..7 of the unit palette): the closest pair | >= 10 | Orange Star 44.9, Blue Moon 25.5, Green Earth 16.5, Yellow Comet 35.4, Black Hole 13.3 |
| ... and the mean over the four body colours of the distance to that army's nearest colour | >= 16 | 49.6, 38.2, 29.4, 40.2, 16.8 |
| chroma, as a share of Green Earth's body chroma (a stone, not a leaf green) | <= 0.4 | 0.21 (21.0 of 97.5) |
| the greys of units that have moved (all five armies) | >= 9 | 10.0 |
| the terrain's colours in fog (measured with fog on) | >= 9 | 9.7 |
| the skin's own done unit against its live unit (on each of the five colours it can sit on) | >= 10 | 12.6 .. 22.2 |
| the skin's done ramp against the other armies' done greys (still the skin's) | >= 6 | 8.0 .. 22.6 |

Emerald Sun is a pale emerald grey: a stone with a faint jade tint (hue 142, chroma about 20, lightness 94 .. 46 down the ramp), with bronze trim and a red crest. It is lighter and much less saturated than Green Earth,
Black Hole's greys are the nearest colours (its highlights are grey too: the army differs by its purple body, so the mean over its colours is the looser margin), and fog's grey-greens set the floor on
lightness. A skin that is too grey is read as a done unit or as fogged ground; one too saturated is Green Earth. A unit that has moved takes the skin's own dimmed ramp (`moved_tint`, `moved_dim`): the
ramp's hue at 78% of its brightness, not a flat grey.

## 7. Adding an army (skill `aw2-add-army`)

1. `aw2dev armyskin preview --fast` while you draw: write `skins/<id>.toml` (copy Emerald Sun's), start with the ramp and trim.
2. Add the file to `FILES`; `aw2dev build --all`; `aw2dev armyskin check` (palette margins) and `check --live`.
3. Draw the Infantry/Mech patches, the HQ and the emblem; `preview` again; look at the screens (`scenario units`, `parade`, `battle`, `map5p`) in `devkit/work/armyskin/`.
4. `aw2dev armyskin sources` must print nothing; `AW2DEV_SKIN=1 aw2dev live moveview --local` and `lobby --players 3 --local`; `aw2dev suite`.
5. Credits for inspiration go in `CREDITS.md`; the art is yours (never trace another project's pictures; look, then draw).

## 8. Limits

- Battle scenes of Infantry and Mech are AW2's figures in the skin's palette (no helmet, no crest): the figures are OBJ tiles streamed per animation frame and the helmet shares its palette entries with the uniform, so an overlay would need a hook on every tile copy; the idle and moving map pictures, the build menu and the panel icons have the galea.
- Up to three skins at once (slots 52..57, one colour each); more needs more slot room (`slot_of`).
- The Dual Strike graphics preview mode (`ds_graphics`, `ds_tilt`) draws its own pictures from the pack's palettes of the five armies: the skin's colours are not applied there.
