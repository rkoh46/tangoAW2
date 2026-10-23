# RAM map (AW2 USA cartridge `AW2E`, CRC32 5AD0E571, plus tangoAW2's own state)

Addresses are GBA addresses as the emulated console sees them. Everything cited is a constant or comment in the tree at branch
`devkit`; file names are under `tango-gamesupport-aw2/src/` unless a path is given. Sizes in brackets are what the code or its
comment states; "?" = not stated in code. Addresses at `0x0213_xxxx..0x023x_xxxx` in the sources (`ds_*`, `co_roster`, `co_new`, `design_random`,
`grand_bolt`, ...) are **Dual Strike (NDS) ARM9 / overlay addresses**, not GBA RAM, and are left out. `0x08xx_xxxx` are in `rom-routines.md`.

Original sources of AW2's layout: Xenesis' RAM notes (Wars World News), the CodeBreaker list, the aw2bhr decompilation, probing with
`gba_probe` (`pvp.rs` header). Names such as `gPlaySt`, `gMap` follow the decomp.

## 1. Registration rule for tangoAW2's own EWRAM (`ram_map.rs`)

- tangoAW2 keeps feature state in **emulated EWRAM, not Rust statics**, so rollback, netplay, savestates, replays and rejoin carry it. Presentation-only state (what the window shows, scratch pictures) may be a static (see `fog_view.rs` `VISION`, `result_view.rs` `STATE`, `tango-gamesupport/src/{hold,private}.rs`).
- The top of EWRAM is unwritten by AW2 (found by filling it and playing every screen; `ram_map.rs` header). **Room: `0x0203C000..0x0203DFFF` (8 KB)** was found unwritten through the title, battles on land/sea/air, Dual Strike scenes, enemy turns, two-front swaps; new state goes there first. `0x0203E000..0x0203F73F` was found unwritten in AW2 and DS battles (docs/AW2.md "Free RAM used"); `0x0203F740..0x0203FFFF` is claimed by earlier features (table 5). `0x02030000..0x02034C00` is taken by the five-army moves (`five.rs`, table 4).
- Each feature claims a region in `REGIONS: &[(&str, Region)]` (`Region = (start, length)`). Two regions may overlap only if listed in `TIME_SHARED: &[(&str, &str, &str)]` (name A, name B, why they are never live together). Tests in the same file:
  - `regions_do_not_overlap`: fails the build on any overlap not in `TIME_SHARED`;
  - `regions_match_the_modules`: asserts that the module constants equal the region table entries (e.g. `ds_battle::MAP_PALS`, `co_skills::DATA`, `two_front::STORE_END`, `tag::STATE/STATE_END`, `ds_campaign::RECORDS`, `survival::STATE`, `tag_thunder`, `power_music::ARMY`, `battle_points`, `history`, `history_ui`, `ds_versus::STATE/ROWS/ROWS_LEN`).
- Procedure to add state: pick a free span in table 5, add the constant in your module, add a `(name, (start, len))` row to `REGIONS`, add to `TIME_SHARED` only with a written reason, run `cargo test -p tango-gamesupport-aw2 --lib regions`. State read by the simulation changes behaviour -> bump `sim_version` (see `architecture-online.md` section 12).
- Alignment: the console reads whole words / halfwords at aligned addresses; u16/u32 state sits on even/4-aligned addresses (comments in `proxy_seat.rs`, `unranked.rs`, `tag.rs`).
- Registered since (no real overlaps were found when they were added): `army_skin::STATE` `0x0203C500`+0x10 (the colour each army skin sits on, the Teams screen's choices; see army-packs.md), `five.rs` blocks (player table `0x02030000` x 6 x 0x3C, army-5 picks `0x02030200`+8, Teams record `0x02030300`+0xE0, threat maps `0x02031000`+5x0xC00 = ends `0x02034C00`), `ds_campaign_rules` `0x0203F700`+0x40, `co_skills::ACTIVE` `0x0203F7E0`+0x20 (test `regions_are_in_ewram` also checks every region lies in EWRAM). Still only inside a broad row: the many single bytes in `0x0203FF80..0x0203FFFF` (table 5) belong to "design list, joypad and invention picks".

## 2. IWRAM (`0x0300_xxxx`): AW2 variables tangoAW2 reads or writes

### 2.1 Match state

| Address | Size | Meaning | Source |
|---|---|---|---|
| `0x03000000` | u32 | Main-loop callback. `0x08022049` = map on screen (`MAP_LOOP`); `0x08043591` = full-screen CO page; `0` = between screens (wipes, scene) | `pvp.rs` `MAIN_LOOP`, `fog_view.rs` |
| `0x03000004` | 7 x u32 | Battle-scene function table; non-zero while a battle is loaded, zero in menus/results/save prompts | `pvp.rs` `BATTLE_SCENE` |
| `0x030033EC` | u8 | Current army 1..5 (left over after a battle) | `pvp.rs` `CURRENT_PLAYER` (and ~25 copies) |
| `0x03004080` | u16 | Day | `bh_factory.rs` `DAY`, `ds_ai.rs` |
| `0x030033FC` | u8 | Title-menu mode: 1 Campaign, 3 Versus (New), 5 War Room, 8 Design Room; Versus Continue 2 / War Room Continue 4 (`ds_versus` `TITLE_MODE`) | `pvp.rs` `GAME_MODE`, `design.rs`, `ds_versus.rs` |
| `0x03003FC0` | 0x48 | `gPlaySt` (play state): +0x01 game mode (`0x03003FC1`: 3 Versus, 1 Campaign), +0x02 map id (`0x03003FC2`; design maps `0xB4..0xB7`), +0x07 powers on (`0x03003FC7`), +0x08 CO abilities on (`0x03003FC8`), +0x0D fog (`0x03003FCD`), +0x28 property funds, +0x2C weather now (`0x03003FEC`: 0 clear, 1 snow, 2 rain), +0x2D weather mode (`0x03003FED`), +0x2E next weather, +0x2F default weather, +0x30 turn limit, +0x33 army colours (`0x03003FF3`; slot 0 byte doubles as the five-army mark in design saves), +0x38 controllers, +0x3D COs, +0x42 teams | `two_front.rs` `PLAY_ST` doc, `survival.rs`, `pvp.rs`, `design5.rs` `MARK` |
| `0x03003FCD` | u8 | Fog of war on | `pvp.rs` `FOG` |
| `0x030032D8` | u8 | Map state machine: 0 idle, 3 turn hand-over prompt, 5 turn start, 0xC a turn by its controller, 0xD the player's cursor, 0x12 match end | `two_front.rs` `MAP_STATE` |
| `0x030033E4`/`E6` | u16 x2 | Map cursor cell (x, y); `0x030033E0` cursor pixel position (halfword pairs) | `fog_view.rs` `CURSOR`, `CURSOR_PX` |
| `0x030040D8` | ptr | Selected unit (pointer to its 12-byte record) / the CPU's unit in hand | `unit_actions.rs`, `fog_view.rs` `SELECTED_UNIT` |
| `0x03003100` | s16 x2 | Destination cell of the moving unit; also the capture cell (`com_tower` `CAPTURE_CELL`) | `unit_actions.rs`, `oozium.rs`, `history.rs` |
| `0x03003F2C` | u32 | Current army's first unit index (`StartArmyTurn`; 64 ids/army, 51 in five-army games) | `tag.rs` `ARMY_FIRST_UNIT` |
| `0x03003F38` / `0x03003F24` | | Selected unit id / origin (CPU invention code) | `factory_hp.rs` |
| `0x030013D0` / `0x030013B0` | | Battle records (`BattleUnit`) of attacker / defender; +8 HP left after the battle (s16) | `battle_points.rs` |
| `0x03003338` | ptr | Structure-shot hit list (first entry: unit 0, the shooter's kind at +2) | `co_skills.rs` `HIT_LIST` |
| `0x03001FD4` | u32 | AW2's RNG state (read, never advanced by tangoAW2 modules except as noted) | `bh_factory.rs`, `ds_ai.rs`, `sandstorm.rs` |
| `0x03004008` | u32 | `gGameClock` frame counter | `design_random.rs`, `heal_effect.rs` |
| `0x03004490` | 8+ | Weather block: [0] change marker, [1] rain chance, [2] snow chance, [3] tangoAW2 (sandstorm one-day flag/biome bits), [4+army] day counters; saved by AW2 itself in suspend | `sandstorm.rs` `WEATHER_BLOCK`, `suspend.rs` |
| `0x03004480` | u16 | Army whose movement costs are being cached (flood fill) | `co_skills.rs` `FLOOD_ARMY` |
| `0x03004494` | | Weather day counts | `ds_weather.rs` `DAY_COUNTS` |
| `0x03003150` | 92 x ? | `gProperty` (class, x, y; at most 92) | `com_tower.rs` `KEY_PROPERTY` doc |
| `0x030033F4` | | Mission-local flags 0..0x1F (bank 0) | `ds_campaign_rules.rs` |
| `0x03003F30` | | Campaign save flag array (`GetCampaignSaveFlag`) | `campaign_menu.rs` |
| `0x030046B4` | ptr | Spawn table pointer used by the Black Factory spawner | `factory.rs` |
| `0x030046C0` / `0x03004780` / `0x03004784` / `0x03004770` | | AI action struct / AI driver state (5 while production runs; 0 begin..4 end) / CPU behaviour row / power pass | `ds_ai_build.rs`, `tag.rs`, `unit_actions.rs`, `ds_ai_power.rs` |
| `0x03004500` / `0x03004520` / `0x03004528` / `0x03004580` | | Battle scene: side colours, battle weather, side units (pointers to unit records), rows (16 bytes, `[0]` colour `[1]` scene id `[2]` weapon) | `ds_battle.rs`, `ds_backdrop.rs` |

### 2.2 Menus and screens

| Address | Size | Meaning | Source |
|---|---|---|---|
| `0x03001470` | slot array | Menu proc slots (`CreateMenu` hands out of it): +0x20 table, +0x31 shown entries, +0x42 cursor | `ds_menus.rs`, `two_front.rs` |
| `0x030014A1` | 8 | Map-menu item ids, one byte per row, led by `0xFF` at `0x030014A0`: 0 CO, 1 Intel, 2 Power, 3 Super, 4 Options, 5 Save, 6 End, ends `0xFF` (Options sub-menu: 1 Yield, 8 Exit Map) | `pvp.rs` `MAP_MENU_ITEMS`, `proxy_seat.rs` |
| `0x030014E2` | u8 | Map-menu state (4 open/used, 5 an item chosen) | `pvp.rs` `MAP_MENU_STATE` |
| `0x030014F0` | u8 | Map-menu cursor row | `pvp.rs` `MAP_MENU_CURSOR` |
| `0x03001500..0x03001A00` (`0x03001F00` in unranked) | | Task table; the Teams screen's task `0x08064E5D` is present only while it is up | `pvp.rs` `TASK_TABLE`, `unranked.rs` `PROCS` |
| `0x03000C00..` (0x1300) | | IWRAM proc area scanned by `fog_view::procs` (records: script ptr, next command, Thumb callback) | `fog_view.rs` |
| `0x03003130` | | CO panel state: +0 side (1 right, 0 left), +4 x (word) | `fog_view.rs` `PANEL_STATE` |
| `0x03005900` / `0x03005930` | | SELECT MAP list: first row shown / cursor row (ids follow) | `survival.rs` |
| `0x03005980` / `0x03005990` / `0x0300596C` | | Versus list row / list top (also per-tab row memory, a byte each) / tab cursor (u16) | `ds_versus.rs`, `online_maps.rs` `TAB_VAR`, `TAB_ROWS` |
| `0x0300591C` / `0x03005924` / `0x03005934` | | Select Mode wheel position (Link 1, Versus 3) / row / position | `online.rs` `WHEEL_CURSOR`, `survival.rs` |
| `0x03005940` | u32 | CO page / CO screen page (0..3 texts, 4 grid, 5 second grid) | `co_grid.rs`, `ds_co_page.rs`, `tag_extras.rs` |
| `0x030058D4` / `0x030058E0` / `0x03005944` / `0x03005948` / `0x03005958` / `0x03005910` / `0x030059C0` | | CO screen: picks, CO list, group ids, group sizes, group country, countries locked, per-pick "locks country" words | `ds_coselect.rs`, `ds_campaign.rs`, `tag.rs` |
| `0x030030F0` / `0x030030F2` | | Map busy counter / main-menu lock | `onyx.rs`, `ds_campaign.rs` |
| `0x03000268` / `0x03000278` | | Sprite lists: flush-area descriptor (source, destination, halfword pairs at +0xA) / the frame's sprite list (128 entries) | `branding.rs`, `fog_view.rs` `SPRITE_LIST`, `heal_effect.rs` |
| `0x03002F2C` / `0x0300141C` / `0x03002F30` | | Next sprite slot / OAM next / deferred copy queue length | `branding.rs`, `heal_effect.rs`, `ds_battle.rs` |
| `0x030020C0` (0x400) | | Palette buffer (copied to PAL RAM `0x05000000` each frame). BG row 8 CO panel, 9 turn banner/power portrait, 10 windows, 11+n army n units/ moved grey; OBJ row 8+n army units | `pvp.rs` `PAL_BUFFER`, `docs/AW2.md` |
| `0x030030CC` | | `DISPCNT` shadow; `0x030030E0` BLDCNT, `0x03002020` EVA, `0x03002B28` EVB, `0x03001FFC` BLDY, `0x03002B6C` BG0CNT, `0x03001FF8` BG0HOFS, `0x03001418` BG0VOFS, `0x030030D0`/`0x03002B20` scroll shift x/y, `0x03002F00` BG flush, `0x03001FE8` BG1CNT shadow, `0x03002B40/4C/EFC/B44` window 0 shadows | `tag_screens.rs`, `power_anim.rs`, `ds_hud.rs`, `ds_worldmap.rs` |
| `0x03002B80` | | Text tile cache (`gUnknown_03002B80`) | `ds_versus.rs` `TEXT_CACHE` |
| `0x03007FF0` / `0x03005AE0` | | `SoundInfo` pointer / music player the CO themes play on | `ds_music.rs` |
| `0x03007B00..0x03007F00` | | The user/system stack (SP starts at `0x03007F00`, grows down; AW2 reaches about `0x03007BFC`). Everything below the current SP is dead data. Not game state; sits in the 4 KB hash block 7 | `net desync` (docs/dev/architecture-online.md 6.1) |
| `0x03007F00..0x03007FA0` | | The IRQ stack (top `0x03007FA0`, grows down). `0x03007F9C` is the `lr` of the last interrupt (the PC it interrupted + 4): differs between two consoles that ran a few cycles apart | same |
| `0x03007FA0..0x03007FE0` | | The SVC (BIOS call) stack, top `0x03007FE0` | same |
| `0x03007FE0..0x03008000` | | BIOS variables: `0x03007FF8` the interrupt flags the BIOS waits on, `0x03007FFC` the IRQ handler pointer (and `0x03007FF0` above) | |

## 3. EWRAM (`0x02xx_xxxx`): AW2's own structures

| Address | Size | Meaning | Source |
|---|---|---|---|
| `0x02000000` | 0x2000 | Save/suspend staging buffer; the suspend block `CaptureBattleSaveState` fills is 0xE28 bytes; tangoAW2's tail starts at +0xDAC ("TAW2"), tag pairs at +0xE28 ("TAG2") | `suspend.rs`, `docs/AW2.md` |
| `0x0200B000` / `0x0200B0B0` | | Design Room editor state block / pointer to it | `design.rs` |
| `0x0200B3B4` | | Battle scene copy queue | `ds_battle.rs` `QUEUE` |
| `0x0200C078` | | War Room record table (5 rows a map, 0x14 bytes per `id - 0x6C` row) | `ds_versus.rs` `RECORDS`, `docs/AW2.md` |
| `0x0200C2D0` | | Campaign mission results (`gUnknown_0200C2D0`: per mission a word Normal, one Hard: CO, days<<8, score<<20) | `ds_campaign.rs` `RECORDS` doc |
| `0x0200C420` | | Profile options block (points, save count, suspend marks, options, results); `0x0200C429` campaign-suspend mark, `0x0200C42A` War Room mark, `0x0200C435..0x0200C43F` Survival records (11 bytes) | `suspend.rs`, `survival.rs`, `docs/AW2.md` Saves |
| `0x0200C42E` | u8 | One of the three copies of the **Visuals rule**, logged by the state hash (`visuals`) | `run_dump.rs` (commit 64338f8b4); exact field not documented elsewhere |
| `0x0200C510..0x0200C528 + 10*0x18` | | Event slots, skipped by `procs()` | `fog_view.rs` `EVENT_SLOTS` |
| `0x0200CC2C` / `0x0200CC38` | | Pointer to the staging buffer / sector directory in RAM (+0x00 slots, +0x10 next directory) | `ds_campaign.rs`, `suspend.rs` |
| `0x0200D510` | 0x10/layer | Sprite-layer lists (next, oam1, oam0, oam2, object) | `versus_rules.rs` |
| `0x0200D610..0x0200E418` | 0x6C each | **Proc pool** (`sProcArray`). As the code reads a record: +0 script pointer (non-zero = in use); `fog_view::procs` identifies a live record as words +0 and +4 both ROM script pointers (`0x08400000..0x08700000`) and +8 a Thumb callback; `result_view::marked` compares the word at +8 with a script position (`0x08615CC8`) for the VICTORY! proc, so +8 is not a plain callback in every state (layout not fully resolved); `+0x14` parent (root = number up to 7); the walking-unit proc `0x080363D1` has pixel x/y at `+0x3E`/`+0x40`; `+0x64` kind (u16, structure-hit proc); `+0x66` army (CO page proc); SELECT MAP list proc (script `0x08616CF4`, `online::list_cursor`): cursor row at `+0x58`; Select Mode wheel proc (`MainMenuCarouselWheel_InputLoop`, `survival.rs`): `+0x4E` moving, `+0x52` position, `+0x66` box row, `+0x6A` picked; CO screen proc (`ds_coselect.rs`): `+0x52` position, `+0x58` group, `+0x5C` group first, `+0x64` index | `result_view.rs` `PROCS`, `fog_view.rs` `walker_pixels`, `battle_points.rs`, `ds_co_page.rs` |
| `0x0200F920 + 0x88*g` | 0x88 | Sprite groups: VRAM base, palette slot, count, (tile, id) pairs; group 1 = army emblems, ids `0x3E..=0x42`; `0x0200F9A8` = group 1; `0x0200FBC8` = group 5 (word group) | `pvp.rs` `SPRITE_GROUPS`, `five.rs`, `sandstorm.rs` |
| `0x02017C50` | | **Versus Teams/Rules record**: +0x08 armies, +0x09 controllers (1 human, 2 computer), +0x0D colours, +0x11 per-army team byte, +0x1C per-army CO index, +0x30 stage, +0x32 cursor (two stops per army), +0x33 rules cursor, +0x54 rule objects. `0x02017C58` armies (reused in battle scenes). Five-army games use the moved copy `0x02030300` (per-army arrays from +0x90, team +0xA0, CO +0xA8). `0x02017C52` / `0x02017CDA` (the other two Visuals copies hashed by `run_dump.rs`) lie inside this record's range (+0x02, +0x8A); which field they are is not stated in code | `pvp.rs`, `docs/AW2.md`, `versus_rules.rs`, `online_teams.rs`, `skills_panel.rs`, `run_dump.rs` |
| `0x0201E450` | | **gMap**: +0 width, +2 height (halfwords), +4/+6 scroll px (refresh copies to +8/+0xA), +0xC/+0xE camera origin, **+0x12 unit-id plane (units the player sees)**, **+0x51A unit-id plane (all units)**, +0xA22 tile ids (u16), **+0x1432 terrain class plane** (class low 5 bits, owner `>>5`), +0x234A displayed vision plane, **+0x417A row-offset table (u16 per row)**, +0x4233 armies on the map | `fog_view.rs` `MAP`, `wasteland.rs`, `unit_actions.rs`, `five.rs` `ARMIES_ON_MAP` |
| `0x02020CA2` | | Reach table of the selected unit (byte per cell, `0xFF` out of reach) | `ds_tilt.rs` `REACH` |
| `0x02022684` | 12 x ids | **gUnits**: 12-byte unit records, indexed by unit id (army = id>>6, 64 ids/army, 50 used; five-army: 51/army). A pointer word at ROM `0x08499594` names the table | `unit_actions.rs`, `obelisk.rs` `UNITS`, `five.rs` `army_of_index` |
| `0x02023284` | 0x3C each | **Player table** (slot 0 neutral, 1..4). Slot n at `0x02023284 + 0x3C*n`; army 1 = `0x020232C0` (`PLAYER_BLOCK`). Moved to `0x02030000` for five-army games (pointer word ROM `0x08499598`; `five::players(core)` tells which) | `pvp.rs` `PLAYER_BLOCK`, `five.rs` |
| `0x020233B0` | | Terrain RAM (obelisk) | `obelisk.rs` `TERRAIN_RAM` |
| `0x02027DE8` / `0x02027F74` | | Sand particles / old SELECT MAP list struct | `sandstorm.rs`, `five_map.rs` |
| `0x02028030..` | | **Unlock block** saved to Flash: `0x02028030` bit 0 Hard Campaign (flag 0x20), `0x02028031` bit 0 Sound Room (flag 0x28), `0x02028038` flag 0x60 Hard being played, `0x02028040..0x02028059` Battle Maps bought (13 halfwords), `0x0202805A..0x0202805F` COs available (16 bits) then CO colour edits (32 bits). tangoAW2 forces these on every tick | `pvp.rs` `before_tick`, `battle_points.rs` |
| `0x020280C0` | 0x1C/slot | Design-map list cache; +0x14 saved marker byte (5 = five-army map) | `pvp.rs` `DESIGN_CACHE` |
| `0x02028360` | 16 x 8 | Inventions list (kind in bits 6..9 of halfword +2) | `factory.rs` `INVENTIONS` |
| `0x020288A0` | 16 | AW2 Teams list the game builds (moved to `0x0203FE80`) | `co_new.rs` |
| `0x02029ED8` | | AW2's AI threat maps (moved to `0x02031000`) | `docs/AW2.md` |
| `0x020296B0 +0x18`, `0x020298E0 +0x16`, `0x02029A10`, `0x02029B78`/`7C` | | Battle-scene shots per side, figure hits, figure records (per side 0xB4, five of 0x24), HP shown / after (u16, HP x10) | `ds_battle.rs` |
| `0x0202FDFC` | 0xFC | AW2 world-map state (camera, cursor, mission, flags, markers) | `ds_worldmap.rs` |

### 3.1 Player block (0x3C bytes; `pvp.rs`, `result_view.rs`, `survival.rs`, `online_stats.rs`)

| Offset | Meaning |
|---|---|
| +0x00 u32 | funds |
| +0x04 u32 | funds spent |
| +0x13 u8 | defeat reason (8 = yielded; written by `proxy_seat::force_yield`; the game's `DefeatArmy` codes: 2 HQ captured, 1 / 0x10 no units left, per `history.rs`) |
| +0x14 u16 | defeated: the day the army was beaten on (non-zero = out) |
| +0x1A u8 | army colour: 1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole |
| +0x1B u8 | controller: 0 none, 1 human, 2 computer (`result_view::alive` = controller != 0 and +0x14 == 0) |
| +0x1D u8 | CO |
| +0x26 | (AW2 sets Colin's funds/300 there; the Com Tower/firepower sum adds it) |
| +0x2A u8 | team (allies share it; a free-for-all has one each) |
| +0x31 u8 | yielded |
| +0x32 u8 | `killOnEndTurn` (set on the previous owner when an HQ/Lab is captured) |
| +0x38 u16? | total score (survival) |
| +0x3A / +0x3B | units built (counting the map's starting units) / units lost (AW2 end-of-battle counters; CO power meter fields are elsewhere in the block, offsets not recorded in these files) |

### 3.2 Unit record (12 bytes; `unit_actions.rs`, `fog_view.rs`, `ds_backdrop.rs`, `crumb.rs`)

+0 type (0 = free), +1 flags, +2 x, +3 y, +4 u16 HP in the low 7 bits (`HP_BITS 0x7F`, 100 = full; shown HP = value/10 rounded up; bit 0x80 of the byte at +4 is a flag Crumb preserves), +7/+8 an APC's cargo, +0x0B CPU role (`ally_posture.rs`). Unit id 0 is empty; the unit-id planes in gMap hold ids.

## 4. Five-army block (`five.rs`, outside `REGIONS`)

| Address | Size | Meaning |
|---|---|---|
| `0x02030000` | 6 x 0x3C | Moved player table (slot 0 neutral, 1..5) |
| `0x02030200` | u8 | Army 5's controller picked on Teams (1 human, 2 computer) |
| `0x02030201` | u8 | Army 5's CO + 1 (0 not picked) |
| `0x02030202` | u8 | Army 5's team + 1 |
| `0x02030204` | u8 | Label pending |
| `0x02030205` | u8 | Vision detour for army 5 running |
| `0x02030206` | u8 | `FIVE_ON`: 1 Five Seas/five-army map picked in Versus, 2 a custom campaign's five-army mission; written at `MAP_PICKED`; patches in ROM are switched from it every frame |
| `0x02030300` | | Moved Teams record (room for five armies) |
| `0x02031000` | 5 x 0xC00 | Moved AI threat maps (armies 1..5) |

## 5. tangoAW2 EWRAM, by address

"R" = row in `ram_map.rs::REGIONS`. Single bytes inside a region are listed under it.

| Address | Size | Owner / meaning | Source | R |
|---|---|---|---|---|
| `0x0203C000` | 0x150 | Battle scenes' copy of the map's OBJ palettes: +0 held flag, rows of 32 bytes from +0x10 (ten) | `ds_battle.rs` `MAP_PALS`, `ram_map.rs` | R |
| `0x0203C150` | 10 | Smart Black Factory: two armies' last four picks (4 bytes each), then their savings (byte each, `BANK = +8`) | `bh_factory.rs` | R |
| `0x0203C160` | 1 | CO screen: picks seen when the cursor was last put on an unpicked CO, +1 | `ds_coselect.rs` | R |
| `0x0203C170` | 0x20 | Battle points: per army 1..4 five bytes (Black Cannons, minicannons, pipe seams, Oozium, Black Crystals), then last bonus (u16) | `battle_points.rs` | R |
| `0x0203C190` | 0x1A4 | History record (magic word + counters); screen state `0x0203C340` (0x60: tab, top, row, column, signature, saved bank 2 at +0x20) | `history.rs`, `history_ui.rs` | R |
| `0x0203C400` | 0x100 | **Lobby browser rows**: 9 rows x 28 bytes: code (6), players, seats, flags (1 padlock), name from +9 (zero-terminated) | `online_browse.rs` `ROWS` | R |
| `0x0203C600` | 1 | Tag Power thunder: what it covers is copied aside (state) | `tag_thunder.rs` | R |
| `0x0203C601` | 1 | Power music: army `sub_08043DAC` was last called for | `power_music.rs` | R |
| `0x0203C610` | 5 | Map-menu tracking: +0 End row + 1 (0 none yet), +1 item the cursor was last on, +2/+3 last map cell x,y (attack target when its scene starts), +4 the main menu's own item | `pvp.rs` `END_ROW`, `LAST_CELL`, `MAIN_ITEM`, `track_menu` | R |
| `0x0203C620` | 0x20 | **Proxy seats**: +0 seats under YIELD (bit each), +1 host seat, +2 held keys of the tap (u16), +4 tap age, +5 hand-off wait ticks, +6 stuck ticks, +8 confirm ticks, +12 signature, +0x10 roster size m (0 = whole room), +0x11 order[8], +0x19 applied, +0x1A physical seats, +0x1C note frames (u16), +0x1E note seat, +0x1F back-out ticks | `proxy_seat.rs` | R |
| `0x0203C700` | 0x100 | Dual Strike CPU: turn's build list, +0xB0 profile rolls, +0xC0 behaviours, +0xD0 goal (flag, x, y, unit word), +0xF0 development switches (bit0 DS CPU off, bit1 production off, bit2 powers off) | `ds_ai.rs`, `ds_ai_move.rs` | R |
| `0x0203C800` | 0x20 | Second front's end: what each army brings (4 x 8) | `two_front.rs` | R |
| `0x0203C820` | 10 | Kindle's High Society: 1 + bonus per army 1..5 (u16) | `co_powers.rs` | R |
| `0x0203C830` | 1 | Olaf's power snow waiting for its second day | `ds_weather.rs` | R |
| `0x0203C840` | 8 | Covering Fire / Ex Machina strike site: power, army, missiles picked, set, x, y | `co_powers.rs` | R |
| `0x0203C900` | 0x20 | Dual Strike Versus / War Room maps: +0 flag, +1 rows state (bit0 loaded, bit1 unsaved), +2 two-front allowed, +3 marked 2P map, +4 fronts (0 none/Versus/War Room), +5 main id, +6 second id, +7 redraw, +8 list args | `ds_versus.rs` `STATE` | R |
| `0x0203CA00` | 0x100 | **Online lobby / match state** (`online::STATE`): +0 level (0 ONLINE, 1 LOBBY, 2 room made, 3 typing code, 4 room joined, 5 typing password, 6 UNRANKED, 7 browser, 8 RESUME, 9 gamertag, 10 STATS, 11 Connection, 12 rejoin box, 13 room name), +1 grid cursor, +2 code length, +3 notice frames, +4 code (6), +0x0C request (`online::mailbox::read_request`: 1 make a room, 2 join, 4 ready, 5 not ready, 6 start, 7 UNRANKED, 8 resume saved #`+0x6B`, 9 delete saved #`+0x6B`, 10 gamertag changed, 11 rejoin, 12 give up; anything else = leave), +0x0D serial, +0x10 status (0 none, 1 waiting, 2 connecting, 3 connected, 4 failed, 5 back), +0x12 room code, +0x1C name buf, +0x29 name len, +0x38 typed chars (+0x48 count), +0x50..0x55 nav walk (goal 1 lobby / 2 SELECT MAP, step 0xFF done, t, total), +0x56 MATCH (1 once a netplay match started), +0x57 OVER, +0x58 entry, +0x59 password len, +0x5A password, +0x5E previous keys, +0x60..0x68 SELECT MAP skip walk, +0x64 BATTLE (1 for a whole battle), +0x65 out ticks, +0x6A/6B RESUME cursor/arg, +0x6C ENDER (army whose End is up), +0x80 players (5 x 0x10: ready, flags PRESENT 1 / HOST 2 / YOU, name 12, rtt ms at +14, link kind at +15), +0xD0 message (0x30) | `online.rs` | R |
| `0x0203CB00` | 0x100 | **Army page**: +0 init, +1 DONE, +2 players, +3 pulse, +4 note frames, +5 off frames, +0x10 + 0x10*seat seat blocks: +0 CO, +1 colour, +2 partner (0xFF none), +3 field, +4 READY, +5 TEAM, +6 prev keys (u16), +8 held frames, +9 held dir, +10 team target (host) | `online_teams.rs` | R |
| `0x0203CC00` | 0x401 | Font tiles kept aside while the Black Cannon (north-facing) picture is in OBJ 989..1004 / 1007..1022; byte `+0x400` = kept | `obelisk.rs` `FONT_KEPT` | R |
| `0x0203D100` | 0x340 | **Saved matches list** (app writes): byte 0 count, +4 REJOIN state (0 none, 1 offered, 2 rejoining, 3 offered and put off), +0x10 lobby note (0x70, zero-terminated), +0x80 rows (6 x 0x70: who, map `0x1C`, day/date) | `online.rs` `SAVED`, `REJOIN` | R |
| `0x0203D440` | 0xC0 | Connection page: +0 state (0 unchecked, 1 Online, 2 Limited, 3 Offline), +2 count, +8 lines (5 x 0x24, "T|label<TAB>value") | `online_conn.rs` | R |
| `0x0203D500` | 0x100 | **Lobby browser state**: +1 cursor, +2 top, +3 net (0 looking, 1 ok, 2 offline), +4 from, +5 refresh counter, +6 selected code, +0x0C version, +0x18 note (0/1 Refreshing/2 Updated), +0x1A own room name (18), +0x30 room name | `online_browse.rs` | R |
| `0x0203D600` | 0x100 | **Map picks / roulette**: +0 UNRANKED flag, +1 PICK, +2 PHASE, +3 CHOSEN, +4 PICKS, +6 walk frames (u16), +9 BATTLED, +0x0A settled, +0x0B changed rules bits, +0x0C PROPOSE (1 in every online match), +0x0E draw counter (u16), +0x10 seats (5 x 8: +0 map id, +2 prev keys), +0x40 CYC_T (u16), +0x42 HOLD_T (u16), +0x44 SKIP (host A), +0x45 STEP_DIR, +0x46 PICK_T (u16), +0x48 SOUND_REQ, +0x4C PICKED (mask), +0x4D ROUND, +0x4E LOCAL_PICKED, +0x50 HALF (first halves, +1), +0xE0 RULES_T (u16) | `unranked.rs` | R |
| `0x0203D700` | 0x400 | **Gamertag / STATS**: +0 gamertag (10), +0x0C SYNCED, +0x0D ASKED, +0x0E FROM, +0x10 tag buf (+0x1C len), +0x20 scroll, +0x21 line count, +0x30 powers used by army 1..5, +0x38 battle number, +0x100 lines (24 x 32: label, tab, value) | `online_stats.rs` | R |
| `0x0203DB00` | 0x110 | Offline Versus map tabs: +0 on, +4 table the copy was taken from, +8 prev keys (u16), +0x0A LR, +0x0B combo, +0x0C LR key, +0x0D tap, +0x10 shadow (each map's own tab, by id) | `online_maps.rs` `OFF` | R |
| `0x0203DC20` | 8+0x6E | SELECT MAP list struct (moved, enlarged): 4 bytes, `LIST_CAP 0x6E` ids, cursor row, last row | `five_map.rs` `LIST` | R |
| `0x0203DF00` | 0x58 | **Fog-view scratch call**: +0 state (0 none, 1 asked, 2 running, 3 done), +1 step, +2 hide-cursor flag, +3 hide-fogged-sprites flag, +4 saved r0..r12, lr, pc; +0x40 camera pin byte, +0x42/+0x44 pinned px/py; +0x46 FAKE byte, +0x48/+0x4A fake cell | `fog_view.rs` `CALL`, `PIN`, `FAKE` (scratch console only, but registered) | R |
| `0x0203E000` | 0x3C6 | CO skills data: magic word, then per CO 32 bytes (EXP u32, Campaign set, Survival set, War Room set, four Versus sets) x 30; dirty flag at `DATA + DATA_LEN`, Versus "Skills" rule at `+1` | `co_skills.rs` `DATA` | R |
| `0x0203E3C8` | 0x24 | Grand Bolt's borrowed palette 15: flag + 32 bytes | `grand_bolt.rs` | R |
| `0x0203E3F0` | 0x0E | Skills panel: +1 col, +2 CO, +3 which set, +4 ids, +8 on Teams, +9 row, +10 backed, +12 saved DISPCNT | `skills_panel.rs` | R |
| `0x0203E3FE` | 1 | **Development byte**: non-zero turns the Dual Strike graphics preview on (also driven by `ds_graphics::tick`; env `TANGOAW2_DS_GRAPHICS=1`) | `wasteland.rs` `DS_GRAPHICS`, `ds_graphics.rs` | R (2 bytes) |
| `0x0203E3FF` | 1 | **Development byte**: non-zero makes the smart Black Factory use AW2's table (balance runs) | `bh_factory.rs` `TABLE_ONLY` | R |
| `0x0203E400` | 0x100 | Two fronts state (second front phase, store kind, swap, view, banner, queue; `+0x18` panel, `+0xC0` sky front state) | `two_front.rs` `STATE` | R |
| `0x0203E500` | 0xE97 | Two fronts: the front off the screen (store: 0xE28 block then extras). **Time-shared** with War Room records (`ds_versus::ROWS`, 0x474), Teams borrowed tiles, Rules/Versus label tiles | `two_front.rs` `STORE`, `ds_versus.rs` | R |
| `0x0203E600` | 0x200 | Versus rules: the labels' OBJ tiles as they were (16 tiles) (time-shared) | `versus_rules.rs` | R |
| `0x0203E800` | 0x8A0 | Teams screen: tiles borrowed while partners show (80 tiles + 6 OBJ palettes) (time-shared) | `tag_ui.rs` `SAVED` | R |
| `0x0203F100` | 0x200 | Rules screen borrowed label tiles | | R |
| `0x0203F3A0` | 0x60 | BH Campaign side table (+24 kind, +48 march, +80 frozen units, 8 pairs) | `custom_campaign.rs` `SIDE` | R |
| `0x0203F400` | 0x100 | **Tag pairs** state: +0xA0 TEAMS_PARTNER (armies 1..5, CO id, 0xFF none), +0xA9 battle has a pair, +0xAC CO panel (x i16, y i16, army, drawn), +0xB4 pending pairs, +0xC0 Teams bookkeeping, +0xE0 arrows state (+8 `INJECTED` keys u16 at `0x0203F4E8`), +0xF0 CHANGE_ENDED. `0x0203F4D0..0x0203F4D2` Crumb's Tag Power rule and the power being paid for | `tag.rs`, `tag_ui.rs` | R |
| `0x0203F500` | 0xD8 | Tag screens / CO page TAG box: +1 army, +2 frame, +4 pending, +5 TAG page, +0x0A stars borrowed, +0x0B/+0x0C swap from/to, +0x0D page CO, +0x0E/0F screen kept, +0x10 partner view, +0x11 view army, +0x12 LEFT pending, +0x70 saved stars (2 x 32), +0xB0 saved star palette, +0xD0 screen up, +0xD4 CPU change | `tag_extras.rs` | R |
| `0x0203F5D8` | 0x28 | Crumb's healed units: a bit per unit slot | `crumb.rs` `MOVE_BITS` | R |
| `0x0203F600` | 0x100 | DS Campaign mission records (AW2 layout, saved with progress) | `ds_campaign.rs` `RECORDS` | R |
| `0x0203F700` | 0x10 + | **Mission state** (not in R): +0 Means to an End told, +4 Ring of Fire volcano stilled, +5 crystals shattered (bits), +6 setup phase (`setup_phase.rs` `SETUP = 0x0203F706`), `0x0203F708..0x0203F73B` Volcano eruption cells, `0x0203F73C` barrier HP (4) | `ds_campaign_rules.rs`, `setup_phase.rs`, `hazard.rs` | - |
| `0x0203F740` | 0x60 | Map animations: +0 bomb noted, +4 going / unit being destroyed, +8 CPU context, +9 planned, +0x0A queue len, +0x0B index, +0x0C step, +0x0D timer, +0x0E labels, +0x10 last scroll, +0x14 label at, +0x20 queue | `map_anim.rs` | R |
| `0x0203F7A0` | 0x40 | Power animations: +0 kind (1 Ex Machina, 2 Covering Fire, 3 Onyx laser), +1/+2 target, +3 frame loaded, +4 frames, +6/+8 camera, +0x0A saved shadows, +0x1E bolt shown, +0x20 saved palette | `power_anim.rs` | R |
| `0x0203F7E0` | 0x20 | **CO skills active in this battle** (per army 1..5 a 6-byte bitmap), `0x0203F7FE` luck army, `0x0203F7FF` special army | `co_skills.rs` `ACTIVE` | - (not in R) |
| `0x0203F800` | 0x200 | Battle scenes: per-side state (+0), effects in flight (`FX 0x0203F880`, 12 x 16 bytes per side) | `ds_battle.rs` | R |
| `0x0203FA00` | 0x310 | Survival: +0 on, +1 kind, +2 stage, +3 phase, +4 left, +8 budget, +0x0C points, +0x10 time, +0x14 funds cap, +0x18 CO, +0x19 menu picked, +0x1C bonus, +0x20 rank, +0x21 Champion, +0x22 last score, +0x24 out set, +0x34 partner, +0x35 suspended, +0x36 continue step, +0x37 saving, +0x40 rows | `survival.rs`, `survival_ui.rs` | R |
| `0x0203FD10` | 0x50 | DS Campaign: +0 active, +1 request, +2 mission, +3/+4 menu level/choice, +5 mission set, +6 BG1 hidden, +7 credits, +8 countdown, +0x0C last result, `0x0203FD20` flags (16), `0x0203FD30` progress record (0x20, "AWDC"), `0x0203FD50` last condition, `0x0203FD56` chooser top, `0x0203FD57` source (campaign index), `0x0203FD58` win cause, `0x0203FD5E` Hard request, `0x0203FD5F` difficulty row | `ds_campaign.rs`, `campaign_menu.rs`, `ds_worldmap.rs` | R |
| `0x0203FD60` | 0x1A0 | CPU tactics, heal effect, Oozium, stun, battle distance, Teams list: `0x0203FD60` pending bombs (4 records), `FD70` called, `FD74` saved r0, `FD78` bombs done, `FD79` prev army; `0x0203FD7C..0x0203FD7E` BH mission variables (fall day, duel done, first turn done); `0x0203FD80` heal effect (start clock u32, kind, x, y, sounded, saved palette 32, last scroll, `0x0203FDAC` pending SE); `0x0203FDC8` Oozium (0x34: return, value, killer, step, CPU eater/victim, flood); `0x0203FE00` stun pending (40), `FE28` active (40), `FE50` prev army; `0x0203FE51` battle distance; `0x0203FE54` defender index; `0x0203FE58` CPU inventions (goal `+0x10`, sent `+0x14`, army `+0x15`, **dev byte `+0x16` = `0x0203FE6E`: `0xA5` switches the CPU's invention play off**, goal unit `+0x18`); `0x0203FE80` Teams list (128) | `cpu_tactics.rs`, `bh_act5.rs`, `heal_effect.rs`, `oozium.rs`, `co_powers.rs`, `co_roster.rs`, `cpu_inventions.rs`, `co_new.rs` | R |
| `0x0203FF00` | 0x100 | Design list and misc: `FF00` the bar's list (31 entries of word+tile), `FF7C` terrain word last picked, `FF80` saved palette 15 (Volcano borrow) | `design_bar.rs`, `design.rs`, `invention_art.rs` | R |
| `0x0203FFA0..0x0203FFE4` | bytes | `FFA0` invention art flag; `FFA2` Volcano moved tile+1; **`FFA5` `ART_ON`** (Crystal/Obelisk art in this match, set each frame from the match bit); `FFA6` `DS_ON` (Dual Strike features on); `FFA7` rules fog flag while rain forces fog (1 + flag); `FFA8` sandstorm word shown; `FFA9` sand colours shown; `FFAB` bars side; `FFAC` editor players moved; `FFAD` DS mission saving; `FFB0` tower counts (per army); `FFB8` scaled value; `FFBA` defence side; `FFBB` defence type; `FFC0`/`FFC4` bomb and its return; `FFC8..FFE3` Onyx satellite state (+0 on, +1 hits, +2 phase, +3 frames, +6 charge, +8 countdown, +9 army, +0x10 silo, +0x14 strike, +0x15 side, +0x16 box off, +0x17 last shot day, +0x18 offline, +0x19 offline now) | `invention_art.rs`, `volcano.rs`, `ds_art.rs`, `ds_weather.rs`, `sandstorm.rs`, `com_tower.rs`, `design5.rs`, `suspend.rs`, `roster.rs`, `co_roster.rs`, `unit_actions.rs`, `onyx.rs` | R (inside the row above) |
| `0x0203FFF0` | u16 | `PREV_KEYS`: previous joypad word | `pvp.rs` | R |
| `0x0203FFF5` | u8 | `DESIGN_PRESET_DONE`: this match's Teams screen seen | `pvp.rs` | R |
| `0x0203FFF6` | u16 | `CLAIMED_KEYS`: buttons tangoAW2 took on press, hidden while held | `pvp.rs` | R |
| `0x0203FFF8` | 4 | `ORIGINAL_COLOURS`: each army's colour when the Teams screen opened | `pvp.rs` | R |
| `0x0203FFFC` | u8 | Factory detour in flight | `factory.rs` `DETOUR` | R |
| `0x0203FFFE` | u8 | Invention icon being loaded | `design_bar.rs` `ICON_PENDING` | R |

### 5.1 Time-shared pairs (`ram_map.rs::TIME_SHARED`)

- two fronts' front store `0x0203E500..` with Teams borrowed tiles, Rules borrowed tiles, Versus saved label tiles (those screens are before a battle);
- Teams borrowed tiles with Versus saved label tiles (two screens never together);
- War Room records `ds_versus::ROWS` (`0x0203E500`, 0x474) with the two-front store, Teams tiles and Versus label tiles (records live only on War Room screens and at battle ends; they are given up during a two-front battle and re-read from Flash).

### 5.2 Test-only / development bytes

| Address | Effect |
|---|---|
| `0x0203E3FE` | Dual Strike graphics preview switch (see above) |
| `0x0203E3FF` | smart Black Factory off (AW2 table) |
| `0x0203FE6E` | `0xA5` = CPU inventions off |
| `0x0203F4E0` | Dual Strike arrows: `+0` = 1 gives AW2's own arrows on Teams/CO screens although DS graphics are on (`tag.rs` `ARROWS`) |
| `0x0203C700+0xF0` | `ds_ai::SWITCHES` (bit 0 DS CPU off, 1 production, 2 powers) |

## 6. Where the online/netplay state is (quick index)

| What | Address | Module |
|---|---|---|
| Lobby/match mailbox, BATTLE byte, ENDER | `0x0203CA00` | `online.rs` |
| Army page seat blocks | `0x0203CB00` | `online_teams.rs` |
| Map picks, roulette, rules timer | `0x0203D600` | `unranked.rs` |
| Proxy seats, roster, host seat (`0x0203C621`) | `0x0203C620` | `proxy_seat.rs` |
| Lobby browser | `0x0203D500`, rows `0x0203C400` | `online_browse.rs` |
| Saved matches, rejoin offer | `0x0203D100` (+4) | `online.rs` |
| Gamertag, STATS | `0x0203D700` | `online_stats.rs` |
| Connection page | `0x0203D440` | `online_conn.rs` |
| Map-menu tracking (End row, last cell) | `0x0203C610` | `pvp.rs` |
| Offline map tabs | `0x0203DB00` | `online_maps.rs` |
| Waiting-view scratch call | `0x0203DF00` | `fog_view.rs` |
| Pack on/off bit for this match | `0x0203FFA5` (`ART_ON`), `0x0203FFA6` (`DS_ON`) | `ds_art.rs`, `ds_weather.rs` |
| Previous keys / claimed keys | `0x0203FFF0`, `0x0203FFF6` | `pvp.rs` |
| Visuals rule copies (hashed) | `0x0200C42E`, `0x02017C52`, `0x02017CDA` | `run_dump.rs` |
| Team of an army | player block `+0x2A` (`0x020232C0 + 0x3C*(army-1) + 0x2A`) | `result_view.rs` |

Probing from tools: `tango_match::Link::peek/poke` (`Console::peek/poke`), `AW2_MEMSCAN=a-b` (dump RAM per tick, harness), `TANGOAW2_DUMP_FRAME=<n>` (+`TANGOAW2_RUN_DIR`, `TANGOAW2_RUN_SEAT`) writes `ram_s<seat>_<frame>_{i,e}.bin`, `TANGOAW2_HASH_PARTS=1` adds a hash per 4 KB.
