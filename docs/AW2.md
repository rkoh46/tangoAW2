# Advance Wars 2 support: how it works

## Shared console

Tango's original games link two emulated GBAs with a cable. Advance
Wars 2's multiplayer is hot-seat: players take turns on one console. So
tangoAW2 runs one console, and both peers simulate it identically.

`tango-backend-mgba/src/shared.rs` implements Tango's `Link` seam over one
mGBA core. Each tick it takes both players' inputs from the rollback
engine and asks the game (`SharedGame`) for:

- `merge`: the joypad word the console sees this tick.
- `before_tick`: runtime memory writes, applied before every frame
  (including during rollback re-simulation, so they stay deterministic).
- `conceal`: whether a seat's picture is blacked out. Presentation only.

The session's save and ROM are seat 0's, identical on both peers. Solo
play and replays use the same console and the same patches.

## Advance Wars 2 rules (`tango-gamesupport-aw2/src/pvp.rs`)

USA cartridge `AW2E`, CRC32 `5AD0E571`, 64 KiB Flash save.

| Address | Meaning |
| --- | --- |
| `0x030033EC` | Current army, 1 to 4. Stays set after a battle. |
| `0x03000004` | Battle scene function table. Nonzero only while a battle is loaded. |
| `0x030014E2` / `0x030014F0` | Map menu state (5 = item chosen) and cursor (4 = End). Both together mark the "Next turn" hand-off screen. |
| `0x03003FCD` | Fog of war, nonzero when on. |
| `0x02017C50` | Versus Teams record: `+0x08` army count, `+0x09` controllers (1 human, 2 computer), `+0x0D` army colours, `+0x32` cursor (two stops per army). The battle's player blocks are built from it. |
| task `0x08064E5D` in `0x03001500..0x03001A00` | Present only while the Teams screen is up. |
| `0x0200F920 + 0x88*g` | Sprite group `g`: VRAM base, palette slot, count, (tile, id) pairs. Group 1 is the emblems, ids `0x3E..=0x42`; the Teams screen loads only four. |
| `0x0203FFF0..` | tangoAW2's own state (previous joypad word, claimed buttons, invention pick, Teams-screen bookkeeping), in EWRAM the game never touches. |
| `0x03003FC2` | The Versus map being played; design maps are `0xB4..0xB7`. |
| `0x030033FC` | Title-menu mode: 1 Campaign, 3 Versus, 5 War Room. Kept through the mode's menus and battles. |
| `0x03000000` | Main-loop callback; `0x08043591` while the full-screen CO page is open (the battle scene is unloaded then). |
| `0x020232C0 + 0x3C*n` | Player block for army n+1. Colour byte at `+0x1A`: 1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole. |
| `0x02028030`.. | AW2's campaign flags 0x20.. (a bit each; `IsCampaignCompletionFlagSet`): 0x20 Hard Campaign, 0x28 the Sound Room, 0x21 the campaign won, 0x23..0x26 set by its missions; 0x60.. from `0x02028038`. |
| `0x02028040`..`0x02028059` | Battle Maps bought. |
| `0x0202805A`..`0x0202805F` | COs available, then CO colour edits. |

Input: in a battle, outside the hand-off screen, only the seat owning the
current army (odd armies seat 0, even armies seat 1) reaches the pad.
Elsewhere both seats' buttons are ORed.

Unlocks: every frame the unlock block is set. The game saves that block,
so an in-game save keeps it. Hard Campaign and the Sound Room are campaign
flags 0x20 and 0x28, bit 0 of `0x02028030` and `0x02028031`: only those bits
are set, the bytes' other flags (0x21 the campaign won, 0x23..0x26 its
missions', ...) are kept (until 0.4.0 the whole bytes were written as 1,
and those flags were lost at every save; `save_keeps_aw2_completion_flags`).

Armies: picked on Versus' Teams screen. R moves the highlighted
army (cursor / 2) to the next colour no other army has, L to the previous
one (without the Dual Strike pack SELECT does as R, as in 0.4.0; with it
SELECT opens the Set Skills panel); the game then builds the battle's
armies from the Teams record, so nothing is forced during play and
Campaign and War Room are untouched.
Black Hole's emblem (sprite `0x42`) is not
loaded on that screen, so while an army is Black Hole its emblem is drawn
into the tiles of a standard emblem no army uses, and all standard
emblems are restored from ROM every frame.

Concealment: with fog on, during a battle, the seat that does not own the
current army sees a dark screen, except on the hand-off screen. Netplay
only: solo play (`SharedLink::solo_side`, what Play offline and
`aw2_script` show) has one screen for whoever moves and is never
concealed. Until the five-army fog check it was, by seat: every turn of
armies 2 and 4, the computer's too, came up as the dark picture.

Sources: Xenesis' RAM notes and hacking threads on Wars World News, the
libretro CodeBreaker list, the aw2bhr decompilation, and probing with
`gba_probe`. `aw2_rollback_sim` checks the whole flow under rollback.

## Design Room (`tango-gamesupport-aw2/src/design.rs`, offline only)

Mode 8 with sub-mode 5 (`0x03003FC1`) is the map editor; its state block
is at `0x0200B000` (tool bar open at `+0x04 == 2`, bar type `+0x07`,
cursor `+0x08/+0x0A`, terrain tool `+0x2A`, colour slots `+0x2E/+0x2F`,
first visible bar entry `+0x36/+0x38`, bar entries at `0x0200B224`, moved
by tangoAW2 to `0x0203FF00`, see below). The
editor map is at `0x0201E450` (size, camera at `+4/+6`, tiles `+0xA22`,
classes `+0x1432`, units `+0x12`, row offsets `+0x417A`); tile classes come
from the ROM table `0x080C1BC4`.

- Black Hole is a fifth army in the editor (`design5.rs`), with five's
  player table (`0x02030000`, see Five armies) and its patches on while
  the editor runs. On entry the editor's four player blocks are copied
  there and player 5 is set up as colour 5 with Flak, so its units and HQ
  have Black Hole's designs (`0x08042DE0`: CO -> country). The bars' army
  cycle goes to 5 (`0x08006C10/32`, `0x08006CC0/E2`), properties of owner
  5 take classes `0xA6..0xAE` (tiles `0x1B4..0x1B8`, `GetDefaultTileForTerrain`
  at `0x080012DC`, owner table repointed to `0x08660000`), units take ids
  `205..254` (`0x0800894E`, `0x08008B8A`), and saving writes army 5's
  units as `0xE0 | type` (`0x0803D09C`), read back at `0x0803D28C`.
  A map with army-5 content carries the five-army mark (5) in its spare
  colour byte `0x03003FF3[0]` (saved at record `+0x4C4`); the save's army
  count (`+0x4C3`) stays 4 for the Versus list and the property totals
  are put right (`0x0803CF7A`). The HQ panel draws the four armies'
  emblems as an X around Black Hole's (OBJ tiles 532..535, the lanes'
  palette 4; the lanes are double-size affine sprites, drawn 8 pixels in).
  A plain's look comes from the cell to its left (`sub_08001704`, jump
  table for classes `0x03..0x8E`); owner-5 classes are looked up as owner
  4's (`0x08001750`), so Black Hole's buildings cast the same shadow.
  Maps saved by older versions with Black Hole in slot 4 (mark 4) still
  start that army as Black Hole on the Teams screen.
  Whether a map is listed in Versus depends on the editor's "Play OK!" test
  (`sub_0800C9E8`, also the flag Save gives the record writer: playable
  -> army count = HQs placed, else 0, and Versus lists no design map with
  count 0). It looks at the four armies only: an army with an HQ and
  a base, city, airport, port or unit counts, an HQ alone (or with only a Lab)
  makes the map not playable, and fewer than two armies counted do too.
  Black Hole did not count, so Orange Star against Black Hole alone was
  never playable, saved with count 0 and never listed (the pack off too:
  Black Hole's editor is not part of the pack). `design5::playable_count`
  (trap `0x0800CA8E`, the `cmp r5, #1`) counts Black Hole as one more army
  when it has an HQ and a base, city, airport, port or unit. A map
  saved that way by an older version is listed once loaded in the editor and
  saved again. Tests: `design_room_*` (`test_design_versus_list.py`).
- In a tool bar SELECT only swapped bars, like L/R; tangoAW2 turns a SELECT
  press into UP (next army, Black Hole included).
- Inventions in the terrain bar (`design_bar.rs`): the bar's list is built
  from the template `0x08488810` by `sub_080078E4` into 17 (terrain) or 20
  (units) 4-byte entries (type or unit word, tile placed) at `0x0200B224`,
  and the HBlank buffer follows at `0x0200B274`. tangoAW2 repoints the nine
  literal-pool words for the list (`0x08001CFC`, `0x08001D58`,
  `0x08001D88`, `0x080062B8`, `0x08006340`, `0x08007750`, `0x08007844`,
  `0x080078D0`, `0x08007918`) to `0x0203FF00`, patches the terrain list's
  length 17/16/0x44 to 27/26/0x6C, or 29/28/0x74 with the Crystal and
  Obelisk, where the editor wraps it (`0x08000CEA`,
  `0x08001D4E`, `0x0800626E/72`, `0x080062E6`, `0x08006460/68`,
  `0x08006562`, `0x08007798/9C/9E`), all in the ROM image in memory, and a
  trap at the builder's exit (`0x080079B2`) inserts the ten inventions
  (types `0x15..0x1E` with their anchor tiles) and the Black Crystal and
  Black Obelisk (words `0x115` and `0x11A`: a minicannon's and a Black
  Cannon's type plus bit 8, which the editor's own code masks off) after
  the Silo. The editor keeps only the picked class (`+0x2A`), so the word
  picked last is kept at `0x0203FF7C` to tell a Crystal from a minicannon.
  The bar's icon call (`0x080027A6`) still has the whole word in r6 and its
  name call returns at `0x08002998` with it in r3; traps there give the two
  their own picture and name. Icons: the
  bar's sprite loader `sub_0803F6BC` already loads a type's terrain-panel
  picture (`0x08104464 + 0x100*(type-1)`) for types it has no case for;
  traps at its entry and exit (`0x0803F7FE`, r4 kind, r5 dest) remap the
  colours from the panel palette (`0x08106864`, entry 13; the base under
  every icon, entry 2) to the palette the icon is drawn with, which a trap
  on the palette lookup's return (`0x08001D20`) picks (the Volcano's is the
  editor's mountain palette, 7). Names are the game's own. A on the map
  with an invention picked places its footprint.
- Inventions drawn in the editor (`invention_art.rs`): in battle they are
  only sprites (their map tiles draw as plain; the metatile table
  `0x080BFBC4` maps them to grass), placed each frame with Black Hole's unit
  palette `0x080D3E84` at priority 3. The sources: minicannons and laser
  raw at `0x080D02C4..0x080D07C4` (16x32, one tile above the cell); Black
  Cannons LZ77 at `0x080D24E0` (down, tiles 36..71) and `0x080D2AE8` (up,
  0..35; the Deathray uses it too), 48x48 from four sprites; Black Factory
  `0x080D22C4` (48x64, three sprites); Volcano `0x080D3268` (one 64x64,
  palette `0x080D3EC4`); the Crystal and Obelisk are tangoAW2's own art.
  In the editor tangoAW2 loads them into OBJ tiles 289..535 (the editor
  uses 536 up) and palette 2 (never used by the editor) and appends each placed
  invention's sprites at the game's VBlank sprite flush (`0x0801BBC4`; the
  frame's list at `[0x03002F2C]` inside the area described at
  `0x03000268`). Everything does not fit in those tiles, but a map has
  either the Black Factory or the Volcano, so only that one is loaded. On a
  Volcano map the Volcano borrows palette 15 (used by the editor only on
  its save and load screens; the game's own is put back off the map), so
  palette 2 stays Black Hole's.
- The aw2bhr decompilation (`src/design.c`) names most of the editor's
  drawing: `sub_08002844` (unit icon: `sub_080261A4(slot, kind)`, CO-country
  based) and `sub_0800272C` (terrain icon; HQs via `sub_0803F6BC(8, army)`).
- Buttons tangoAW2 takes are hidden from the game for as long as they
  stay held (`0x0203FFF6`), so a held press never reaches the editor as a
  new one.

## Inventions in battle (`tango-gamesupport-aw2/src/factory.rs`)

- Inventions list: `0x02028360`, 8 bytes each (x, y, tile, HP, ...,
  counter). The Deathray's counter (byte 6) counts 7..1 and it fires on
  Black Hole's turn when it wraps; its area (`0x0801FCE0`) is columns
  x..x+2 from row y+3 to the map's bottom edge, enemies only. The laser
  hits every unit in its row and column.
- Units: 12-byte records, army n (1-based) at `0x02022390 + 0x300*n`
  (type, state, x, y, HP|flags, ammo, fuel, ...). Create-unit is
  `0x08025C5C` (x, y, type), wrapped by `0x08025CC8`. Player blocks are
  `0x02023284 + 0x3C*army` (colour +0x1A, 1 human / 2 AI at +0x1B, unit
  count +0x3A).
- The factory spawner `0x080607E8` finds the factory (`0x0803E354(7)`)
  and, for each of the three tiles on the row y+4 that is empty, creates
  the unit type at `table[(day & 0x1F)*3 + i]` (0 = none), the table
  pointer being `[0x030046B4]`. Only the AI turn setup calls it
  (`0x08061900`, colour 5), after storing the map header's table pointer
  (`0x08615194 + (map-0x8A)*0x30 + 0x24`, hard `+0x28`). Design maps have
  no header entry: the computer got garbage types, a human got nothing.
- tangoAW2 traps `0x080618AE` (right after that store) to give design maps
  Factory Blues' table (`0x08576F23`), and `0x08026810` in start-of-turn
  (after the per-player turn-start call, scratch registers dead) to detour
  a human Black Hole army's turn through the spawner once; `0x0203FFFC`
  marks the detour so the return passes. A trap handler runs before its
  instruction.
- **Versus with the pack** (`bh_factory.rs`, `bh_smart.rs`): a trap at the
  spawner's create-unit call (`0x08060856`, r0 x, r1 y, r2 type; r5 holds
  the type for the AI-group call after it) changes what a slot spawns, never
  whether or how many (the table's zeros and a blocked door tile stay), for
  a CPU army's turn and a human one's (the detour above) alike: it decides
  for the army moving now, from that army's own side of the fog. The RNG
  the spawner draws for the unit's AI group is untouched, and the choice
  reads emulated RAM and ROM only (no host state, no randomness: rollback,
  both netplay peers and replays agree; about 0.1-0.3 ms a decision). It
  runs again for every spawn, so the same factory picks differently as the
  battle changes (`TANGOAW2_BH_LOG=<file>` on the console logs each
  decision with its top reasons, the runner-up and what it saw; the aw2test
  harness sets it per console, `Emu.decisions()`).
  - *Where*: a unit is placed only where its movement chart
    (`oozium::move_cost`) lets it in and the square is empty: ships on a
    door tile or the squares beside the doors (door row x-1..x+3, the row
    under the doors), so sea, reef or shoal as that ship allows (the one
    nearest an enemy first); land and air units on their own door tile,
    never on sea or reef (the table's own unit there is dropped, the loop
    skipped to the next slot); a Piperunner on a pipe square beside the doors.
    With no candidate the table's unit spawns.
  - *The schedule* (Factory Blues' table, `0x08576F23`, which design maps use; the
    spawner reads row `day & 0x1F`, so day 32 is row 0 and day 33 is row 1; slots are
    the doors left to right). The smart factory keeps these days, doors and counts: a
    "none" stays none, a blocked door still blocks its slot, and only the *type*
    spawned changes (within the cost rule).

    | day | door 1 | door 2 | door 3 | day | door 1 | door 2 | door 3 |
    |---|---|---|---|---|---|---|---|
    | 0 (=32) | Tank | none | Tank | 16 | Infantry | none | Missiles |
    | 1 | none | Mech | none | 17 | none | Tank | none |
    | 2 | Recon | Recon | Recon | 18 | Mech | Infantry | Tank |
    | 3 | none | none | none | 19 | none | none | none |
    | 4 | none | Tank | Artillery | 20 | Neotank | Md Tank | Neotank |
    | 5 | Mech | Anti-Air | Md Tank | 21 | none | none | none |
    | 6 | none | none | none | 22 | none | none | Mech |
    | 7 | none | none | Infantry | 23 | Tank | Anti-Air | none |
    | 8 | Neotank | Rockets | Infantry | 24 | Infantry | Md Tank | Artillery |
    | 9 | none | none | none | 25 | none | none | Md Tank |
    | 10 | none | Md Tank | none | 26 | Infantry | Neotank | none |
    | 11 | Anti-Air | none | Mech | 27 | Mech | none | Tank |
    | 12 | Artillery | Mech | none | 28 | none | Tank | Infantry |
    | 13 | none | none | Missiles | 29 | Anti-Air | Anti-Air | none |
    | 14 | Rockets | Artillery | none | 30 | none | none | Tank |
    | 15 | none | Md Tank | none | 31 | Tank | Infantry | Mech |

  - *Candidates*: Infantry, Mech, Md Tank, Megatank, Tank, Recon, Neotank,
    Piperunner, Artillery, Rockets, Anti-Air, Missiles, Oozium, Fighter,
    Bomber, B Copter, and the ships (Lander, Cruiser, Battleship, Sub, Black
    Boat, Carrier).
  - *Cost rule* (the factory is not a free army): a spawn costs at most the
    table's unit for that day and slot, so over any stretch of days the
    factory spawns no more value than AW2's table would (the table's
    Infantry slot can only be a cheaper unit, its Neotank slot anything up
    to a Neotank's price). The one exception: Megatank, Battleship, Carrier
    and Oozium (the heavy ones) may cost up to 30% more than the slot's
    unit (so only a big slot can bring one: a Neotank's, a Md Tank's for
    the Oozium), and only one of each may stand on Black Hole's side at a
    time (a loss is replaced by a later spawn); they also score -20.
  - *The pick* (so a human cannot read the factory's next move): the candidates are scored
    as below, then one is drawn, weighted by score, from the best two or three whose
    score is within 15% of the best (at least 6 points); a candidate's weight is its score
    above that floor plus one, so the best weighs most. The draw's seed is a hash of AW2's RNG
    state (`0x03001FD4`, a 32-bit word the game's own draws advance; the factory only
    *reads* it, so the battle's luck, and the spawner's own draw for the unit's AI group
    after the create call, are unchanged: `bh_factory_choice_leaves_the_rng_alone` plays
    the same turn with the smart factory and with the table's units and finds the same RNG
    afterwards) with the day, door, army, door position and map; so the three doors differ
    and the same situation on another RNG state can pick another unit. The seed is a pure
    function of emulated memory (rollback, both netplay peers and replays draw the same).
    Every candidate in the pool has passed the cost rule, the heavy units' one-at-a-time
    limit and the terrain rules before it is scored, so any pick is fair
    (`bh_factory_pick_varies_with_the_rng`: ten RNG states on one day give different spawns,
    each one in the logged pool, within the margin, the cost rule and its terrain). The
    log line shows the pool (`pool Neotank 89 w14, Megatank 88 w13`).
  - *Scoring* (each candidate's score; the pick above draws among the best):
    *counter*: what the candidate does to the enemy units Black Hole sees
    minus 0.6 of what they do to it, by Dual Strike's own damage chart
    (`roster::chart`, an Oozium eats ground units for 100), each enemy
    weighted by price x HP bars x nearness (so air answers Anti-Air and
    Missiles, a fleet Subs, Battleships and Cruisers, infantry Recon, Tanks,
    Artillery and so on), x1.5 while enemies are within 6 of the factory;
    *travel*: -5 a turn (up to 10) to get within reach of the nearest enemy
    unit or enemy/neutral property by the unit's own movement chart over the
    real map (Dijkstra: rivers, mountains and woods stop treads, the sea
    stops all but ships and air, a pipe line takes a Piperunner), -45 where
    it cannot get there; none of it while the factory is threatened, which
    instead adds price/1500 for sturdiness, +25 for an Oozium at the door and
    -20 for indirect fire with an enemy at its feet; *army*: -7 for each unit of
    the type Black Hole already has, -3 for each of the same role, +10 for
    indirect fire when it has none, +8..16 for Infantry and Mech while
    properties wait to be captured; *specialists*: -30 Anti-Air with no air
    in sight, -15 a Sub with no ship in sight, -10 a copter and -25 a
    Fighter or Bomber for their fuel, a Lander +30 only with land to ferry
    troops to (else -40), a Black Boat +25 only with two hurt units; *size*:
    price/2500. An enemy counts only if Black Hole sees it (its units' and
    properties' vision from the unit table; adjacent only for units in woods,
    on reefs, dived or hidden; all with fog off). Terrain and properties are
    always known.
  - *Destroying it* (`factory_hp.rs`): AW2 keeps the factory in its
    invention list (kind 7, HP 0) beside the Black Cannons (kinds 3 and 5,
    HP 99). With the pack, in Versus, a trap before the registration call
    (`0x0803E348`) gives it 200 HP (twice a Black Cannon's: the HP byte holds up to 255 and
    the game's hit takes the same damage from it as from a Cannon's 99, so a Tank's 16 leaves
    184 and it takes 13 such hits, not 7), and one at `sub_0803DFE0` (the position
    units aim at, 0 for a kind that cannot be attacked) makes it a target at
    the middle of its bottom row, as a Black Cannon is: the attack menu, the
    targeting from adjacent squares and range, the damage (the game's own for
    a structure, the attacker's chart against a Md Tank-class defender, the
    CO's modifiers, so the same shot takes the same from a Black Cannon),
    the hit animation are the game's; the terrain panel's HP row draws two digits
    (`sub_0802BAFC`, ones and tens, a tens digit of 10 or more is a letter glyph), so from 100
    up two traps (`factory_hp::panel_heart`, `panel_number`, at the heart's sprite call
    `0x0802B23A` and the number's call `0x0802B266`) draw three: the heart 3 pixels left (the
    panel's edge), the digits 2 right (where the star row's number ends), the three digits one
    `sub_0802BAFC` call each, re-entering the trap on return with the digits' state in a small
    frame under the stack (nothing in RAM or ROM changes). The panel is 30 pixels wide: 200,
    184 and 100 fit with no overlap; under 100 the game's own two digits.
    At 0
    HP the hit step's destroy branch (`0x08040818`, no case for kind 7)
    runs a Black Cannon's destruction (the explosion), the entry keeps 0 HP
    (the game saves it with the battle, so suspend and continue keep the
    factory's HP and its destruction) and it is drawn as the Black Cannon's
    wreck over its whole footprint (the sprite call at `0x0803FD54`; AW2 loads the
    cannon sheet, whose first 36 tiles are the wreck, at OBJ tile `0xC4` on every map,
    cannons or not, so nothing is loaded or changed here and nothing else's tiles or
    palette are touched; our sprite definition at `0x08648000` draws the 3x3 wreck
    twice, on the lower three rows and behind it on the upper three, for the 3x4
    footprint. The tiles are checked against the sheet's decoded data each frame; if a
    screen has borrowed them the factory is drawn in a neutral building's grey instead.
    The wreck's grey boulder with a broken purple/teal rim is AW2's own art: a
    destroyed Black Cannon looks the same without the pack); its doors spawn nothing
    for the rest of the battle (the create trap), and the battle does not
    end. The campaigns keep their factory and its pipe seam (nothing here
    runs outside Versus).
  - *The building is a wall* (`factory_hp::tick`, every frame): every square of the
    factory's 3x4 footprint (the doors' row below it excluded) is terrain class 9 (the
    invention underlay: no unit enters it, air and Oozium and Piperunner included)
    or the factory's own `0x1D`, as AW2's maps and the Design Room's footprint make
    them; a map that carries only the anchor tile, and the pipe end (class 15) at the
    factory's top, which a Piperunner would ride into, are made walls too. Spawns
    stand on the door squares (ships on the squares beside the doors), never on
    the building. `test_bh_factory.py` plays CPU against CPU on a coast and an
    inland map and checks that no unit ever stands on the building.
  - *The CPU* (`cpu_tactics::cpu_unit`, `factory_hp::cpu_strikers`): an
    army's CPU unit (not on Black Hole's team) with the factory's aimed
    square in range from where it stands, a weapon that harms a structure
    and no enemy unit in range hits it at its turn's start through the
    game's own structure attack (`sub_08042634`, what the CPU runs for a
    pipe seam), one hit at a time; otherwise AW2's CPU plays as before. A
    Black Hole CPU's defence of its factory is its spawns: enemies near
    the factory make the choice sturdy (above).
  - Outside Versus (`GAME_MODE` `0x030033FC` is 3), without the pack and in
    the DS Campaign nothing changes (`test_bh_factory.py`). RAM `0x0203E3FF`
    non-zero is a development hook for balance runs: the table's units
    spawn, as AW2's (`AW2TEST_BH_BALANCE=1 run.py -k bh_balance`: CPU against
    CPU on a coast and an inland map, smart against table).
- The battle loads the Volcano's colours (`0x080D3FC4`) into sprite
  palette 12 (`0x0803FE0A`), the fourth army's buildings' palette: fine in
  the campaign, but a Versus map with a Volcano and Yellow Comet drew
  Yellow Comet's buildings in them. In Versus `volcano.rs` sends them to
  palette 2 (unused by the battle map) and recolours the Volcano's sprite
  at the sprite flush.
- `aw2_script` can trace this kind of thing: `AW2_TRACE=<file>` traps
  listed addresses and logs registers, `stepuntil8 ADDR` single-steps
  until a byte changes and prints the last instructions, `steplog N`
  prints every function entry for N instructions.

### The computer attacks a human's inventions (`cpu_inventions.rs`)

AW2's CPU knows nothing of an invention: its attack check looks at units (and pipe seams), its role moves
at HQs, properties and units. Black Hole's inventions belong to the army in Black Hole's colour, which in AW2's
campaign and in Dual Strike's is the computer, so nothing needed to attack them. `cpu_inventions::owner` is
that army where a **human** has it, and only in two places: the **BH Campaign** (the campaign source is
tangoAW2's, the player is Black Hole) and **Versus with the pack** when a human army is in Black Hole's colour.
Everywhere else (`owner` is `None`: AW2's campaign, the DS Campaign, Survival, the War Room, Versus without the
pack, Versus where Black Hole is a computer) the module does nothing, writes no RAM, and the factory's older
strike (`factory_hp::cpu_strikers`, a computer's factory hit by a unit already in range) is as it was. RAM
`0x0203FE6E` = `0xA5` (a development byte, `OFF`) switches it off too, for before/after runs.

- **Targets** (`targets`): the invention list's entries with hit points that the game lets a unit attack
  (`sub_0803DFE0`: kinds 1, 3, 4, 5, and the factory's 7 where it can be destroyed), told apart as the Black Cannon (3),
  the Obelisk (a kind 3 on tangoAW2's tile `0x193`), the minicannon (4), the Crystal (a 4 on tile `0x192`), the Laser (1)
  and the Deathray (5); the Grand Bolt's weak points and the Volcano are not. The square units aim at is the game's
  (`x + 1, y + 2` for a 3x3, the entry's corner for a 1x1, the middle of the factory's bottom row).
- **The Black Factory in the BH Campaign** now has 200 hit points as in Versus (`factory_hp::in_scope` takes in the BH
  Campaign), so the computer can destroy it: the game's hit and destroy steps, the wreck, doors that spawn nothing
  after. The player's own units cannot hit it (`target_position` gives the factory no square on the player's team's turn;
  AW2 lets any army hit a Black Cannon, Crystal or Obelisk, as in Versus, and this is unchanged).
- **Worth** (`worth`, funds): Black Cannon 16000, Deathray 24000, Laser 14000, Obelisk 11000, Factory 13000,
  minicannon 6000, Crystal 5000, plus half the price (by bars) of every computer unit in the firing zone of
  a firing one, plus, for each hurt Black Hole unit within reach of an Obelisk (4) or a Crystal (2), the share of its price that the
  hit points it would heal are (up to 20), plus half of the share of the invention's hit points already lost (low: sooner gone). A hit is worth
  its share of the invention's hit points of that, and when it destroys it a third more (`gain_of`).
- **Firing zones** (`zone`, the game's `sub_0801FAC4` cone, checked by `cpu_inv_firing_zones_are_the_games`): a Black
  Cannon fires a cone of ten rows widening by one cell a side from the middle of its facing edge (facing down: from
  `(x + 1, y + 2)`), a minicannon one of four from the cell in front of it, a Laser along its row and column, the
  Deathray in the three columns below it; a cannon hits some units in it (about five of ten bars) at the start of Black Hole's turn.
- **Strikes** (`plan`, at the start of a computer army's turn, from `cpu_tactics::cpu_unit`): a unit with a target's square
  in its range from where it stands (its weapon's range: a Tank beside it, an Artillery 2 or 3 squares off) and a weapon that harms a
  structure (the game's damage chart column 3, the secondary weapon without ammunition) hits the best target in reach through the game's own
  structure attack (`sub_08042634`, as for a pipe seam) when the hit is worth at least what its best unit target in range is worth (and
  always when it has none); at most eight a turn (the second half of the queue is `EXTRA`, RAM `0x0203FE58`), the strongest hitters first,
  never more hits than a target has hit points for. The damage is the chart's value by the unit's hit points (Artillery 45, Tank 15).
- **Goals** (`role_move`, through `AiRunRoleMove`, `0x0805F4CC`, shared with `ally_posture`): a unit whose role (record +0x0B, the
  deployment's AI byte or what the CPU's production gave it) advances, 1 to 6 (not 0, which holds, and 7, by the HQ), with no
  capture under way and a weapon that harms a structure, is moved by AW2's own "go to a place": the role 1 code, tail-called, whose
  place (`sub_08058F90`, the enemy HQ) is replaced by the goal (`GOAL_HOOK`, `0x0805ED2A`, writing the two halfwords at `r4`). The goal is
  the best square to attack a target from (inside the weapon's range of the target's square: artillery and rockets stop in range,
  tanks and infantry beside it) by `gain` / (1 + 0.6 turns), the path a Dijkstra over AW2's own movement costs
  (`oozium::move_cost`: the CO's chart, the weather) with other teams' units in the way, the inventions' walls out, eight turns at most.
  A square in the line of a firing invention (the target's own too) costs the unit 60% of its worth for each (it is hit at Black
  Hole's next turn and again after), so tanks do not walk into a Black Cannon's cone for nothing and come in from its side or
  back to the others, while artillery and rockets set up outside it; a unit already where it can attack holds. At most half of
  the army's advancing units are sent a turn (`SENT`).
- Deterministic: only emulated RAM is read (the invention list, the units, the players, the map), ties broken by position;
  the queue and three bytes are the module's state. `test_cpu_inventions.py`.

## CO panel on design maps

- The CO panel's palettes are loaded at the start of each turn from the
  army's colour: BG row 8 from `0x080D4188 + (colour-1)*32` (`0x0801A548` ->
  `0x0802D5CC`) and OBJ row 7 (palette row 23, the header with the funds)
  from `0x08104264 + (colour-1)*32` (`0x08043834`). On a design map the
  first turn's are loaded before the colours are held to the Teams pick,
  so the current army's rows are swapped from its map colour to its pick
  where they still hold the map colour's.

## Title and menu badge (`tango-gamesupport-aw2/src/branding.rs`)

- A "tangoAW2" badge, with the app's version on a plate under it (read
  from `tango/Cargo.toml` at build time), drawn by the game's sprite hardware while
  `ProcScr_TitleScreen` (`0x08581CF8`) or `ProcScr_MainMenu` (`0x0849E818`)
  is running (the process pool is `sProcArray`, `0x0200D610`, 0x6C bytes
  each, script pointer first; names from aw2bhr): its tiles in unused OBJ
  tiles 928.. (title) and 992.. (menu), its colours in OBJ palette 15, its
  64x32 sprites appended at the VBlank sprite flush like the Design Room's
  inventions.

## Five armies (`five.rs`, `five_map.rs`, `five/`)

Advance Wars 2 has room for four armies. For the 5P maps tangoAW2 adds a
fifth, Black Hole, by patching the ROM image in memory while a 5P map is
played (and restoring it otherwise, so every other game runs the game's own
code). The patch list is `five/patches.txt`; `five/gen.py` checks every
original instruction against the ROM and writes `src/five_patches.rs`.

- **Unit ids.** One byte, army = `id >> 6` (64 per army, 50 used). For five
  armies army a owns ids `(a-1)*51 + 1..50`; about 150 places that encode
  or decode the army (shifts, masks, `(p - gUnits)` pointer chains, 64-id
  walks, the AI's `(t*128 + u)*4` pointers, the army-base table
  `0x084995FE`) are patched. Hooks are emulator breakpoints whose handler
  sets the register and skips the instruction.
- **Moved to free RAM with a fifth slot.** The player table (pointer word
  `0x08499598` -> `0x02030000`), the AI's threat maps (`0x02029ED8` ->
  `0x02031000`), the Teams screen's record (`0x08580934` -> `0x02030300`,
  its per-army arrays at +0x90..).
- **Loops and tables.** About 80 army-count bounds, the turn wrap, vision
  (an unrolled 1..4 call gets a detour for 5), capture tiles (six owners per
  kind; Black Hole's property tiles `0x1B4..0x1B9`), owner bits, building
  sprites (army 5 on OBJ palette 13; fogged buildings use the neutral
  palette), army 5's units on BG palette 11, the Black Hole HQ art in the building sheet's lab slot.
- **Unit colours.** The map draws army n's units with BG palette 11 + n and
  moved units with BG 11 (icon palette entry 0), where `sub_0801A57C`
  loads the current army's grey (`0x0810E6E0 + (colour + 4) * 32`) at each
  turn start and after a power's portrait or the battle scene. Every BG
  palette is in use on the map (0-7 terrain and its fog shades, 8 the CO
  panel, 9 the turn banner and power portrait, 10 windows), so with five
  armies the grey goes to BG 9 (the banner shows before any unit has moved;
  the power portrait covers the map, and the game reloads the grey after
  it), Black Hole's colours go back in 11 after each grey load, and a moved
  unit's draw puts the grey back in 9 if the banner left its colours there.
  Before (0.3.4) Black Hole's units took the current army's grey: Green
  Earth's tint on Green Earth's turn, red-brown at Orange Star's, and moved
  units took Black Hole's colours. Colour 15 (the outline, pulsing while a
  CO power is on) is set every frame by `sub_08024720` for armies 1..4;
  army 5 is added (row 11). The CO power dialog and portrait load the CO's
  face colours into BG 9 and bring the map back without redrawing it, so
  the grey goes back when their proc (`0x0848A3EC`) ends. The turn banner's
  colours (`0x080A1238`) exist for four colours only (colour 5 read past
  the table: a near-black stripe); Black Hole's turn gets a purple one in
  the same layout (`five.rs` `BANNER5`). Tests:
  `tests/test_five_unit_palettes.py`.
- **Screens.** The Teams screen (five 48-px columns, `5P`, `E Team`), CO
  screen, Intel, results, capture-limit panel. The map menu hides Save (the
  suspend block holds four armies).
- **Maps.** Map-table entry 0 and ids `0xB8..0xBF` (design ids only
  multi-cartridge link uses; the game's design range is narrowed to
  `0xB4..0xB7` and the rest made ordinary by edits and a helper in dead
  code). Each map's header carries its own tab and armies, so the same
  ids also hold the 2-, 3- and 4-army obelisk maps; the 5-army ones are in
  category 9, the 5P tab. `five/design_maps.py` draws them,
  `five/map.py` builds them (sea edges from the Design Room's table
  `0x08485DC4`). The AI keeps a row pointer per map row in a 40-entry stack
  array, so maps are at most 40 rows.
- **More map ids.** The game's map table (`0x085C77A0`, 0xC0 entries of
  0x5C bytes) is copied to `0x08650000` with room for more; its 37
  literal-pool pointers (the table, and +0x3C/+0x40 of entry 0) are
  repointed, and the two loops that walk it (`sub_080206B0`, find a map by
  its tiles; the map list builder at `0x08037482`) go up to 0xC0 instead
  of 0xBF, and to 0xF1 while the Dual Strike maps can be listed (eight more
  ids to walk shift the menus' timing by a frame, so without the pack the
  loops stay as they were). Black Rampart is id 0xC0, the Dual Strike maps 0xC1..0xC8 (see
  below). A tab lists its maps by id, so new maps come last. Each map's
  tiles and units take 4 KiB: the first ten at `0x08622000`, the rest at
  `0x08656000` (after the moved table, which now holds 0xF2 entries).
- **Terrain in `five/map.py`.** Roads, pipes and pipe seams pick their
  tile from which neighbours connect, as the game's own maps do (learned
  from every built-in map): roads have straights, bends, T-junctions,
  crossroads and shaded variants; pipes have straights, bends and end caps
  (no junctions). Rivers (`-`), bridges (`=`) and shoals (`,`) take the tile
  the game's own maps use most for the same neighbours (sea, shoal, river,
  bridge or road on each side); roads join bridges.
- **Switching.** A RAM flag set when a 5P map is picked (trap on
  `sub_0803BCD0`) decides; each frame the ROM is switched to match, so
  rollback (which restores RAM, not ROM) stays deterministic. Resuming a
  suspended game switches the patches off first.
- **Fog** (checked 0.4.x, `tests/test_five_fog.py`): Black Monolith, Black
  Wastes and Coral Crown in fog, Sonja as Yellow Comet and Von Bolt as
  Black Hole, three days with their powers fired: on every sample the
  terrain follows the drawn vision plane (gMap +0x234A; AW2's fog colours,
  Dual Strike's on Wasteland), no other army's unit is drawn in fog, a
  fogged property is drawn in the neutral palette and a seen one in its
  owner's (Black Hole 13), Sonja's units hide their HP from Orange Star.
  AW2's own: the full vision refresh marks every invention's footprint
  seen and the computer's refresh does not, so a row the camera scrolls
  in during a computer's turn draws a cannon's or Crystal's cells in
  either state (two-army AW2 without the pack does it too). During a
  computer's turn start the current army (`0x030033EC`) runs through the
  armies, and between two computers' turns it reads 1 for some frames.

## The Dual Strike maps (`five/design_ds_maps.py`)

Eight Versus maps for the Dual Strike pack, drawn by `five/design_ds_maps.py`
(called from `design_maps.py`) into `five/maps.txt`, built like the others by
`five/map.py`. Every Com Tower on them starts neutral.

| Id | Map | Armies, size | Tab | Look | What is on it |
|---|---|---|---|---|---|
| 0xC1 | Rust Basin | 2P, 25x17 | Vs. | Wasteland | a river with three bridges down the middle, a sea ring joining the two bays, beaches, a pipe along each coast, 2 Com Towers, 2 Black Crystals |
| 0xC2 | Dune Fork | 3P, 29x22 | 3P | Wasteland | a river forking between the three armies, bridges, three bays joined by a sea ring, pipes, 3 Com Towers (one between each pair of armies), 3 Crystals |
| 0xC3 | Cinder Flats | 4P, 29x29 | 4P | Wasteland | four corners inside a sea ring, rivers from four bays to a Black Obelisk ringed by 4 Crystals and 4 Com Towers, pipes |
| 0xC4 | Black Wastes | 5P, 29x29 | 5P | Wasteland | four corners round Black Hole's fortress: a Black Cannon facing north and one facing south, 2 Lasers, 4 minicannons, 4 Crystals; rivers, lakes (no ports: they would not reach each other), pipes, 4 Com Towers on the axes |
| 0xC5 | Coral Strait | 2P, 27x17 | Vs. | AW2 | two islands across a strait inside a sea ring, bridged to a middle isle with 2 Com Towers (and one on each island); each side's two bases sit on a pipe that runs through the sea to the middle isle |
| 0xC6 | Trident Isles | 3P, 29x20 | 3P | AW2 | three home islands round a middle isle with 3 Com Towers and a beach north and south, a pipe from a base on each island to it |
| 0xC7 | Harbor Cross | 4P, 29x29 | 4P | AW2 | four corner islands inside a sea ring, a pipe from each one's base across the channel to the middle isle, its 4 Com Towers and 4 beaches |
| 0xC8 | Coral Crown | 5P, 29x29 | 5P | AW2 | four corner islands and Black Hole's middle island, a Com Tower on each of the four islets between them, reached by the corner islands' pipes |

- **Fair.** The 2P maps turn about their centre, the 3P maps are mirrored
  left to right with army 3 on the middle line (the three HQs about as far
  from each other), the 4P and 5P maps are mirrored both ways (Black Hole,
  army 5, in the middle of the 5P ones). On a map every army but Black
  Hole starts with the same properties (HQ, two bases, an airport, ports,
  cities) and units (two Infantry, a Mech, a Recon, a Piperunner on its
  pipe, and on the Wasteland maps a Tank and Artillery, on the sea maps a
  Lander and a Cruiser); Black Hole's middle holds fewer, with its fortress
  or its ports, and a Piperunner base too.
- **Everyone gets everywhere.** Checked with the game's own movement chart
  (`tools/aw2test/aw2test/traverse.py`): foot, treads and tires reach every
  enemy HQ and Com Tower overland or by Lander (beach or port to beach or
  port; foot every property too), ships reach every enemy port (bridges
  stop ships, so the seas meet round a ring of sea where needed), no base
  or port is boxed in, and every Piperunner has something in range on its
  pipe.
- **Beaches where they matter.** On the sea maps beach stretches are placed
  by hand (`beach` in `design_ds_maps.py`, mirrored with the map): landings
  facing each neighbour's island, the Com Tower isles and the middle isle,
  and near each HQ, with cliff coast between so a beach is worth holding.
  The test checks that the armies the symmetry maps onto each other get as
  many beaches and an enemy beach as far from their HQ (`beach_balance`;
  a 3P map's army 3, on the mirror line, is matched to the other two by
  hand; Black Hole in the middle of a 5P map is left out).
- **Five Seas' beaches** (`design_maps.py`, the first map; listed with or
  without the pack). Every army's island has beaches (shoals, `,` in
  `maps.txt`) where a Lander loads and unloads: the four outer
  armies five each (three or two along the coast facing a neighbour, the
  rest on the other coasts), Black Hole's island six on its west, east and
  south coasts, and each of the eight small islands one. Every island's
  beaches are reached overland from its HQ and bases and sailed to from
  every other army's. Shoals are tiles `five/map.py` draws as AW2 does (the
  coast opens round them; `tilecheck.py` passes). Tests:
  `five_seas_every_army_has_beaches`, and `five_seas_lander_unloads_on_every_beach`,
  which plays all five armies to sail a Lander onto a beach, board an
  Infantry and drop it. The map changes the tiles of a map the game sends in
  netplay by id, so both players need the same version, as always.
- **Piperunner bases behind seams.** Each army's Piperunner base touches
  its pipe only through a pipe seam (in `five/map.py` a seam's straight
  run may end at a base: `B Z I I`). A base offers the Piperunner only
  while a pipe or an intact seam is next to it: the build menu
  (`sub_0802D5E8`, trap at `0x0802D65E` in `cpu_tactics.rs`: the pipe
  domain bit is dropped from the base's mask) as the CPU's buying already
  did. A broken seam is rubble (walked on like plain, never a pipe), so
  breaking the seam ends that base's Piperunners, and no Piperunner
  crosses it.
- **With the pack only.** Com Towers, Piperunners and the Wasteland look
  are the pack's, so these maps (`ds` in `five_map_data.rs`) are listed
  only when the pack is on (for a match, when both players have it) and the
  Crystal's art too; otherwise they sit on the hidden tab like the obelisk
  maps without their art (`five_map::show_maps`), so without the pack every
  map list is as before.
- **The Wasteland look** (`wasteland: true`): at every map start
  (`wasteland::map_start`) a tangoAW2 Wasteland map sets the biome to
  Wasteland, any other map that is not a design map (0xB4..0xB7) to Normal.
- The Crystals on the 2P-4P maps heal a Black Hole army (a player who picks
  Black Hole on the Teams screen); by default no army is Black Hole there,
  and they are only obstacles to shoot at.
- `factory.rs` gives these maps Factory Blues' factory table too (the map
  header table the computer's turn reads has no entry for them).
- Tests: `tools/aw2test/tests/test_ds_maps.py` opens each map from its tab
  (the list's preview checked tile by tile), checks every tile, owner and
  unit against `five/map.py`'s build and the traversal check on the map in
  play (and on the build, `ds_maps_traversal_static`), photographs the whole
  map (screenshots stitched as the cursor sweeps it), plays six all-CPU days
  on each (two in netplay), and checks the maps are not listed without the
  pack; `test_pipe_seams.py` checks the build menu and the CPU against intact
  and broken seams.

## Dual Strike's looks (`wasteland.rs`, `ds_look.rs`)

Dual Strike draws a map in one of four looks: Normal, Snow, Desert and
Wasteland. With the pack, Wasteland is a per-map setting of design maps (the
Design Room's Waste entry) and the look of tangoAW2's Wasteland Versus maps;
Survival's maps and the DS Campaign's missions bring their own look (Dual
Strike's look byte, `wasteland::set_ds_look`). Normal stays AW2's own; Snow,
Desert and Wasteland are drawn with Dual Strike's own terrain graphics,
converted from the .nds at run time.

- **Dual Strike's terrain.** Two tilesets of 736 tiles: `bmap/000` (Normal,
  Snow) and `bmap/001` (Desert, Wasteland), coloured by the look's palette
  file (`bmap/006` Normal, `00a` Snow, `008` Desert, `009` Wasteland; arm9
  `0x02167DD4` names them per look): 9 sub-palettes, 0-4 terrain, 5 one grey
  ramp all fog uses, 6-8 buildings (with per-look building colours,
  `0x02147F40`..). The metatile table (arm9 `0x02143F40`) is laid out as
  AW2's (AW2's tile ids, four quadrants each); a second table (`0x02145F40`)
  holds what reaches into the cell above (mountain peaks, treetops, roofs),
  drawn on a second layer (`0x020F6E74`). Every mountain cell is drawn as one
  of three mountains by position (`0x020`, `0x146`, `0x147`: table
  `0x02169E58` at `(x + x/4 + 2y + y/8) & 15`, `0x020F6F34`); woods are
  `0x086`/`0x087`. The tile layout is AW2's: `0x100..0x1FF` the sea's,
  `0x200..0x25F` the river's; the Normal tileset's frames are `bmap/004`
  (4 sea frames) and `bmap/005` (8 river frames), laid out as AW2's own
  (`0x080C1FC4`, `0x080C9FC4`). The `bmap/001` looks have no frames of their
  own in the ROM.
- **Conversion** (`ds_look::build`, once per look at the first frame with the
  pack). Per AW2 metatile: cells AW2 draws as plain under a building's sprite
  (every metatile with plain's quadrants; the Black Crystal's and Obelisk's
  `0x192`/`0x193`; army 5's properties `0x1B4..0x1B9`) get Dual Strike's
  plain; mountains get Dual Strike's mountain for the cell's position, woods
  its two woods by id parity; AW2's bridges `0x13`/`0x14`/`0x36`, which Dual
  Strike lacks, its bridges `0x15`/`0x16`, and AW2's plains with the peak or
  treetops of the cell below drawn in (`0x03`, `0x43`, `0x106`, `0x107`,
  `0x126`, `0x127`) its plain (the peak comes from Dual Strike's upper part
  instead, below); everything else Dual Strike has (sea, shoals, reefs,
  rivers, roads, pipes, seams, ...) its own metatile. What it lacks (89
  metatiles: some road corners, the class-0 strips `0x200..0x245`, `0x280`,
  `0x282`) keeps AW2's tiles, each AW2 colour taking the look's colour it
  most often lands on where both games draw a metatile; these are static
  (they live in the tiles never animated). The volcano rim's upper part
  (`0x1A5`) is not drawn (AW2 draws the volcano as a sprite).
- **Peaks and treetops.** A mountain's upper part (its bottom 4 rows) and a
  wood's (2 rows) are drawn over the bottom half of the cell above, as Dual
  Strike's second layer does, whatever that cell is (plain, road, another
  mountain, a wood, sea...), and not past the map's top edge. AW2 has one map
  layer, so tangoAW2 draws the cells itself while a Dual Strike look is on:
  traps at `BlitMapRow` (`0x08023BAC`) and `BlitMapColumn` (`0x08023A4C`)
  draw the row or column the game asked for into BG3's tilemap buffer and
  return (the game's own code otherwise). A cell under which a mountain or
  wood stands gets composite tiles: its bottom quadrant with the upper part
  over it, in the palette of the 4 that draws it best (`Look::composite`).
  Composites go into the tiles no metatile uses (about 230 per look): one
  already there is used again, else the first one no tilemap entry uses; all
  the bookkeeping is VRAM and the tilemap buffer, so it is the same on every
  console and after a rollback. A sea or river quadrant under a peak keeps
  its first frame.
- **Animation.** The Snow look uses `bmap/004`/`005` as they are. Desert and
  Wasteland derive theirs: each pixel of the look's tile equal to the Normal
  tileset's frame-0 pixel follows the Normal frames, the rest (shores and
  banks in the look's own shapes) stays. AW2's own timing plays them
  (`UpdateTerrainAnimation`).
- **Colours.** AW2 has 4 terrain palettes (BG 0-3; 4-7 the same darkened for
  fog); Dual Strike's terrain uses 5. They are grouped into 4 by trying every
  partition and keeping the one with the least mean colour error per tile
  (frames and upper parts included), each group cut to 15 colours by folding
  together the two closest colours (the less used goes into the other: the
  colours stay Dual Strike's own, and one unlike the rest, a wood's green,
  stays). Mean colour error per pixel is under 1.5 (squared, 5-bit
  channels) on every metatile. BG palettes 8-15 are untouched.
- **Fog and weather, as Dual Strike's screen has them** (melonDS: Verdant
  Hills in fog, Crystal Calamity with its weather poked to rain and snow,
  Healing Touch in a sandstorm, Dark Ambition in snow). A fogged cell's
  terrain (sub-palettes 0-4) is drawn with the look's sub-palette 5, index
  for index (the dark violet greys of its fog), whatever the weather; rain
  (which brings fog), snow and sandstorm change no colour (only their
  particles fall or blow). So AW2's fog palettes 4-7 are Dual Strike's fog
  colours: each colour of palettes 0-3 takes the fog colour of the Dual
  Strike colours folded into it, by their pixels (`Look::fog`; AW2's own
  fog relation only for a colour no Dual Strike tile has), worst mean error
  per metatile 4.7 (Snow); the rain, snow and sandstorm sets are the clear
  set (they were AW2's colour relations and a sand tint until checked). An
  upper part over a cell takes that cell's fog, not its own cell's: one
  palette per tile.
- **Roads.** Dual Strike's Wasteland and Desert roads are faint tracks;
  `ds_look::ROAD_SHADE` (0: Dual Strike's own) draws every road this many
  5-bit steps darker (the darker colours go into the palettes with the
  rest), and the tests follow it.
- **Drawing.** Each look's data goes in the ROM image's free space
  (`0x08E80000 + 0x20000 * (look - 1)`: metatiles, the tiles as LZ77, sea
  frames, river frames, the clear, rain, snow and sandstorm sets). The game
  reads its terrain through nine literal-pool words (the tiles
  `LoadGameplayGraphics` decompresses, `0x080234D8`; the metatiles
  `BlitMapColumn`/`BlitMapRow` draw from, `0x08023B08`, `0x08023C6C` and
  their `+6` words `0x08023B1C`, `0x08023BA8`, `0x08023C80`, `0x08023D10`;
  the frames `LoadSeaAnimFrame`/`LoadRiverAnimFrame` copy, `0x08021D94`,
  `0x08021DCC`). `wasteland::sync` points them at the look's data while one
  is drawn and at AW2's otherwise, from RAM alone, at each reader's entry
  (traps `0x08023360`, `0x08023A4C`, `0x08023BAC`, `0x08021D64`,
  `0x08021DA0`) and every frame. With the pack off nothing is written and
  the game draws its own map. `sub_08035020`'s trap (`sandstorm.rs`) gives
  the look's colour set for the weather.
- **Means to an End.** Dual Strike draws this one map (its 0xF8) with its own
  palette, `bmap/00b` (arm9 `0x020F92E4`: map 0xF8 takes `"00b"` at
  `0x0216A1DC` in place of its look's file), not its look's (Wasteland,
  `bmap/009`): Desert's colours (green woods, brown mountains) but for
  terrain palette 2, the Grand Bolt's greys. It has a look of its own here
  (`wasteland::GRAND_BOLT_LOOK`, tileset `bmap/001` with `bmap/00b`), set by
  `ds_campaign::map_start`; checked against melonDS frames of the mission.
  Dual Strike's drifting darker sand on its 3D map (it moves from frame to
  frame: an effect over the map, not terrain) is not drawn.
- **The Design Room.** A on the map with the Waste entry switches Normal and
  Wasteland: the next frame the colours, the terrain tiles in VRAM and the
  map's tilemap (`RenderMap` done in Rust) are the new look's.
- **Kept AW2's.** Buildings and structures (sprites in AW2; Dual Strike draws
  them in its map layers), the battle backgrounds of Desert and Snow
  (Wasteland's are Dual Strike's, `ds_backdrop.rs`), the terrain panel's
  pictures, the mini maps.
- Tests: `tools/aw2test/aw2test/looks.py` renders Dual Strike's own drawing
  from the .nds (lower layer, upper layer into the cell above, the mountain
  by position, the frame on screen, the weather's and fog's colours) and
  compares the terrain layer read back from VRAM (BG3's tilemap, tiles,
  palette RAM: no units, cursor or windows) cell by cell, within the colour
  reduction's tolerance (mean squared error 6 per pixel). `test_biome.py`
  (each look's data metatile by metatile; the screen in clear, rain with fog,
  snow and sandstorm, at several animation frames; the Design Room's switch
  and scrolling), and whole maps swept with the cursor and checked at every
  view: tangoAW2's four Wasteland Versus maps (`test_ds_maps.py`) and every
  Survival map in a Dual Strike look (`test_survival.py`); every DS Campaign
  mission's first view (`test_ds_campaign.py`).
- **Checked against Dual Strike's screen.** Dual Strike draws its map in
  3D, tilted (about 13 to 16.6 pixels a cell from top to bottom). Missions
  were started in melonDS (`ds_script`) from its campaign map with the
  mission record id the map hands on (`0x02183CC0`) poked, the cursor swept
  over every cell with the bottom screen's 3D layer alone on (BG0,
  `BLDCNT` off), each camera's view fitted to the reference's drawing (a
  homography per camera position) and flattened back onto the 16-pixel grid
  (each pixel the brighter of several frames: Dual Strike's cloud shadows
  drift over the map). Snow (Frozen Fortress, Dark Ambition in snow) and
  Wasteland (Crystal Calamity, Healing Touch) match the reference colour for
  colour (median distance to the nearest colour of the cell under 1 on a
  5-bit scale; tangoAW2's screen the same), tiles and shapes too (woods,
  three mountains by position, peaks over the cell above, roads, rivers,
  sea and shores, pipes, bridges, lava); fog and weather did not (above).
  `tests/test_ds_frames.py` compares such captures (kept outside the repo:
  `$AW2TEST_DS_FRAMES`, a manifest of flattened pictures) with the
  reference. Dual Strike's map palette function (`0x020F92B8`) has one
  special case, Means to an End's map (0xF8); the look picks the rest.
  Which cells are lit in fog is the game's rules, not the look.

## Black Crystal and Black Obelisk (`obelisk.rs`, `five/obelisk_art.py`)

Dual Strike's healing structures, built on two of the game's inventions so
the game registers, targets and destroys them: the Crystal is a
minicannon (class `0x15`, invention kind 4) and the Obelisk a Black Cannon
(class `0x1A`, kind 3, 3x3 over `0x1A4` underlay). Each has its own map
tile, `0x192` and `0x193` (unused by the game; tangoAW2 sets their classes
in the ROM table `0x080C1BC4` and its RAM copy `0x020233B0`, and their
metatiles to plain grass), and every trap tells them apart by that tile,
so real minicannons and Black Cannons run the game's code unchanged.

- **Sprites.** `sub_0803F908(x, y, def, army, fog)` places a building's or
  invention's sprite; called from `0x0803FB92` (minicannons) or
  `0x0803FD08` (Black Cannons, defs `0x0849FA08`/`0x0849FA22`) on our
  tiles it gets tangoAW2's definitions at `0x08640000` (ROM image free
  space): the Obelisk is a 32x64 sprite over the middle of its 3x3 rect and
  two 8x32 strips for its platform's sides, the Crystal one 16x32. Their 48
  tiles go to OBJ tiles `0x176..0x1A5` after the building sheet loads
  (`0x0803F6A0`); nothing in battle uses those.
- **Art: from the player's Dual Strike ROM** (`ds_art.rs`). tangoAW2 ships
  none of it. The library scan offers every file in the ROMs folder; a
  Dual Strike (USA, AWRE) ROM gives `bmap/015` of its file system (LZ77;
  4bpp bitmaps, rows of pixels: the Crystal 16x32 at 0x1600, the Obelisk
  64x64 at 0x3F00 with its footprint at x 8..56, y 0..48) and sub-palette
  12 of `bmap/00e` (Dual Strike's Black Hole palette, each colour mapped to
  the nearest of AW2's `0x080D3E84`). The scan saves the result next to
  the ROMs (`Dual Strike Black Obelisk art.tangoaw2`, 1672 bytes) and
  loads that on later scans, so the `.nds` is needed once.
- **Hidden without the art.** `ds_art::features(mode)`: played alone, when
  this player has the art; for a netplay match or its replay, as the
  match says: each player sets bit 7 of their match subtype when they
  have it (`SHARED_CONTENT`, tango-net-protocol), the lobby ignores the
  bit when comparing match types, and the terms keep it only when both
  set it, so both peers and every replay agree. Off, the four maps sit on
  a tab no list shows (`five_map::show_maps`) and the Design
  Room's bar is 27 entries long instead of 29 (`design_bar::patch_rom`).
  A console without the art in a match that has it (someone else's
  replay) draws the structures as nothing; the sprite layout is the same
  either way, so nothing in RAM differs.
- **No firing.** The turn-start loop over the invention list
  (`0x02028360`, 16 entries of 8 bytes: x, y, kind in bits 6..9 of the
  halfword at +2, HP at +4) is trapped per entry at `0x0803ED7A` (r2) and
  skips ours (`0x0803EEAC`); the range display (`sub_0803E9F8`, entry r5)
  skips to `0x0803EAC4`.
- **Healing.** A trap at `sub_0803EAD0` (turn start, before inventions
  act): if the army moving now has colour 5 (Black Hole), each of its
  units within 2 of a live Crystal or 4 of a live Obelisk's footprint gets
  +20 (of 100) HP, as in Dual Strike, capped at 100, and full ammo and fuel from the
  unit table `0x085D5ABC` (+0x0B, +0x10). Only that army's own unit ids are
  walked, so enemies and allies are never healed.
- **Heal animation and sound** (`heal_effect.rs`, with the pack). Dual
  Strike's animation (arm9 `0x0213E078` / `0x0213E2A0`) is drawn as
  sprites in tiles the map leaves free and in OBJ palette 15 (saved and put
  back). Not palette 8: building sprites use OBJ palette 8 + owner, so 8 is
  the neutral (and fogged) buildings' palette, and the effect's colours
  there turned those buildings dark while it played. It starts two frames
  after the turn-start loop reaches the structure, once the camera has
  stopped (the camera sets off a frame later). With its first frame comes
  Dual Strike's sound: its animation start (`0x020D84B8`) plays sequence
  175 `SE_BLACKSTONE` (Crystal, `mov r0, #0xAF` at `0x020D85D8`) or 176
  `SE_BLACKCRYSTAL` (Obelisk, `0x020D86E0`) through `0x0200B76C`, one note
  that plays its whole sample (1.9 s, 3.1 s). `ds_music.rs` converts them
  as songs 514 and 515 (after the themes) for player 2 (the player AW2's
  turn-start cannon shot, song 457, uses), priority 10, no reverb; the
  note without a length gets its sample's length (a `TIE`, then `EOT` and
  `FINE` after it), and the sequence its default tempo (120). The draw
  marks the song pending in RAM (`0x0203FDAC`); the turn's wait function
  (called by the game each frame while it waits) plays it with AW2's own
  sound-effect call `sub_0803B4DC`, so the game's sound flag
  (`0x030005CC`) applies, and the music is untouched. A Crystal's sound
  is cut short (by about 0.15 s) when the next structure's starts on the
  same player. Tests: `tools/aw2test/tests/test_heal_sound.py` (2, 4 and 5
  armies, human and CPU, fog on and off, normal and Wasteland looks: each
  sound starts on the effect's first frame, the music plays on, and no
  colour or sprite tile but the effect's changes while it plays, beyond
  what the game animates itself).
- **Panel.** The terrain panel (`sub_0802A8DC`, cell in r8/r5) gets the
  name picture at `0x0802A914` and the picture at `0x0802A982`.

## The Dual Strike pack (0.3.0)

With a Dual Strike (USA) ROM imported (`ds_pack.rs`: its ARM9, overlays and
files, saved next to the ROMs), Dual Strike's content is added to AW2. Nothing
from either game is in the repository; everything is read from the player's
ROMs at run time. Without the pack the game runs byte-identical to 0.2.2 (the
comparison battery in CONTRIBUTING.md), and online it is on only when both
players have it (the match's `SHARED_ART` flag, kept in replays).

Every change is switched every frame from ROM and RAM state (`pvp.rs`
`before_tick`), so both peers and every replay agree: tables are copied to free
ROM and their literal-pool words pointed at the copies, and code is changed by
traps (a trap runs before the instruction it replaces; setting the PC skips it).

| Part | Module | What it changes |
|---|---|---|
| Units | `roster.rs`, `ds_units.rs`, `unit_actions.rs`, `oozium.rs`, `unit_names.rs`, `ds_unit_art.rs`, `ds_unit_pictures.rs`, `ds_battle.rs`, `ds_backdrop.rs`, `map_anim.rs` | Unit table grown to 64 rows (0x08680000), 7 new units (ids 4, 9, 12, 13, 18, 26, 27), Dual Strike's stats and damage chart, their actions (Hide, Explode, Repair, Carrier; the Oozium eats: no weapon, moving onto a unit of another team next to it destroys that unit with the game's own destruction, and no CO, power, silo or Black Bomb touches it), map art, their own information pictures (build menu panel, R on a unit) in each army's colours, every unit in the Intel unit list, battle scenes with Dual Strike's figures, effects and volleys, Dual Strike's battle backgrounds (a Piperunner on its pipe; every battle on a Wasteland map; a Com Tower's city), and Dual Strike's map animations played through AW2's own map effects (a Black Bomb's explosion, a Stealth hiding and appearing, a Black Boat's REPAIR label, Oozium's death in its army's colours; for the CPU at its turn's end, before the turn passes) |
| COs | `co_roster.rs`, `co_new.rs`, `co_powers.rs`, `crumb.rs`, `crumb_art.rs`, `ds_co_art.rs`, `ds_power_art.rs`, `power_anim.rs` | CO table grown to 96 rows (0x086A0000), Dual Strike's numbers for AW2's COs (and its 200% defence cap), 11 new COs at ids 72..82 (Dual Strike's nine, Clone Andy and Crumb, "Clone Andy" and "Crumb" below; face ids stay unambiguous), their pictures, texts, powers and Dual Strike's power animations (Ex Machina, Covering Fire, Urban Blight), and Dual Strike's choice of power effect on their units |
| CO screen | `co_grid.rs` | The unit grid (map menu > CO, its last page) gets a second page: ground units, then air and naval units, in the build menus' order, every unit with its icon in the viewed army's colours (the new units in the map sheet's slots for other countries' Infantry and Mech) and its firepower bar (Dual Strike's bonuses take the nearest of AW2's 13 bars) and move / range change |
| CPU | `cpu_tactics.rs`, `cpu_inventions.rs` | The CPU buys every new unit (Carrier, Oozium and Piperunner in place of a like AW2 unit at its three `BuyUnit` calls), explodes Black Bombs, hides Stealths, repairs with Black Boats, eats with Ooziums (and moves them towards enemies), and leaves Ooziums out when it aims a silo or a strike (on Crystal Calamity's map its Launch is Dual Strike's: no missile, Black Hole's line and the mission lost, `onyx.rs`); a base builds Piperunners (for the CPU and in the build menu) only by a pipe or an intact seam |
| Terrain | `com_tower.rs`, `wasteland.rs`, `ds_look.rs`, `sandstorm.rs` | Com Tower (the Versus Lab), Dual Strike's Wasteland, Desert and Snow looks drawn with its own terrain (below), the Sandstorm weather (Dual Strike's sand, `bmap/0b2`) |
| Structures | `obelisk.rs`, `heal_effect.rs` | Black Crystal / Obelisk heal with Dual Strike's own animation and sound for each (arm9 0x0213E078 / 0x0213E2A0; SE 175 / 176), the camera visiting each |
| Music | `ds_music.rs` | The nine new COs' own map themes, Dual Strike's, converted to AW2's sound engine (below) |
| Maps | `five_map.rs`, `five/design_ds_maps.py` | Eight Versus maps (2P to 5P, a Wasteland set and a sea set) with Com Towers, Piperunner pipes and Black Hole's structures (above) |
| Survival | `survival.rs`, `survival_maps.rs`, `survival_ui.rs`, `mode_menu.rs` | Dual Strike's Survival mode (Money, Turn, Time) on its own 33 maps, a seventh entry on Select Mode (below) |
| DS Campaign | `ds_campaign.rs`, `ds_campaign_data.rs`, `ds_campaign_rules.rs`, `campaign_menu.rs` | Dual Strike's story campaign in AW2's campaign engine, behind a Campaign sub-menu (below) |
| BH Campaign | `bh_campaign.rs`, `custom_campaign.rs` | A campaign defined as data (Black Hole's thirty missions: two placeholders so far; Free Play, a reversed Black Onyx, Sonja), in the same engine, on AW2's own world map, with its own record and unlockable COs (below) |

Free ROM used: 0x08620000.. (text slots), 0x0862C000.. (new CO text ids 0x6D72..),
0x08640000..0x08672FFF (earlier features, the Black Factory's wreck sprite definition at 0x08648000; the map table and the maps past the tenth at
0x08650000..0x0865EFFF), 0x08680000..0x08691FFF (units),
0x086A0000..0x086AFFFF (CO table), 0x08740000..0x0877FFFF (CO pictures, texts,
powers' code, heal wait), 0x087C0000..0x087C0FFF (power animations),
0x087C1000..0x087C3FFF (map animations), 0x087D0000..0x087DFFFF (unit pictures),
0x087F0000..0x087F4FFF (CO screen grid: the map sheet per country, the page lists),
0x08800000..0x08DFFFFF (music, past the 8 MB cartridge: mGBA grows the image when it is written; the ten new COs' themes, Clone Andy's Andy theme included, end at about 0x08DA4400),
0x09000000.. (the DS Campaign's story songs, their own range so the music above never runs into the
Survival and campaign data),
0x0862D000..0x0862D0FF (Survival's text ids 0x7172..), 0x08E00000..0x08E4FFFF (Survival: the map
table with room for 0x100 ids, its maps, strings, the Select Mode wheel's data),
0x0862DA38..0x08630A37 (the DS Campaign's text ids 0x7400..0x7FFF),
0x08F00000..0x08FFFFFF (the DS Campaign, about 360 KB used),
0x08E80000..0x08EFFFFF (Dual Strike's looks: 0x20000 each for Wasteland, Desert, Snow and Means to an End's),
0x08E70000..0x08E73FFF (two fronts: stubs, swap scripts, the menus' copies, labels; text ids 0x7FFD, 0x7FFE),
0x08E74000..0x08E743FF (the DS Campaign's Setup phase: stubs, script, menu, label; text id 0x7FFC),
0x08E75000..0x08E753FF (Crystal Calamity's Black Onyx: `onyx.rs`; its RAM 0x0203FFC8..0x0203FFE3).
Free RAM used: 0x0203FD57 (the chosen campaign, `ds_campaign::SOURCE`), 0x0203E3F0..0x0203E3FD (the skills panel; the skill data now ends at 0x0203E3C5 with Crumb's slot, the Grand Bolt's borrowed palette follows at 0x0203E3C8..0x0203E3EB), 0x0203F4D0..0x0203F4D2 (Crumb's Tag Power rule and the power being paid for) and 0x0203F5D8..0x0203F5FF (the units it healed: a bit a unit slot), 0x0203E400..0x0203F3FF (two fronts: their state, the front off the screen), 0x0203FA00..0x0203FD0F (Survival), 0x0203FD10..0x0203FD5F (DS Campaign), 0x0203F600..0x0203F6FF (the DS
Campaign's records; 0x0203E000..0x0203F73F was found unwritten at the title, Select Mode, in AW2 and DS battles), 0x0203F740..0x0203F79F
(map animations), 0x0203F7A0..0x0203F7DF (power animations), 0x0203F800..0x0203F9FF (battle
scenes), 0x0203FD60..0x0203FEFF (CPU tactics, heal effect, the Oozium's eat
0x0203FDC8..0x0203FDFB, stun, battle distance, Teams list),
0x0203E800..0x0203F09F (the Teams screen's borrowed tiles while partners show), 0x0203F100..0x0203F2FF
(the Rules screen's borrowed label tiles), 0x0203F400..0x0203F4FF (tag pairs), 0x0203F500..0x0203F5D7 (the tag screens, the CO page's TAG box), 0x0203FF00.. (earlier
features). Free ROM: 0x08780000..0x0878FFFF (the tag map menu, its stubs and strings, the Rules rows' help
lines), 0x08790000..0x087A042F (what the tag screens cover, while they show). `factory.rs` has a test that no two traps share
an address.

The new COs' music (`ds_music.rs`): each new CO's turn plays its own Dual
Strike theme, converted at run time for AW2's sound engine (MP2K, "Sappy").

- **Which theme.** Dual Strike's CO record (arm9 `0x0215360C + 0x220*id`)
  names the CO's map music at `+0x14`, a sequence of `data/sound_data.sdat`
  (whose symbols confirm it: Jugger `BGM_ZIPO1` 36, Koal `BGM_CHAKKA1` 39,
  Kindle `BGM_CANDLE1` 27, Von Bolt `BGM_HAGEVOLT1` 38, Grimm `BGM_KOUZOU1`
  34, Javier `BGM_BITTMANN1` 40, Sasha `BGM_SASHA1` 37, Jake `BGM_JOHN` 5,
  Rachel `BGM_RACHEL1` 24; no two share one). The pack keeps those
  sequences (SSEQ), their banks (SBNK) and sample archives (SWAR) as
  `sound/seq/<id>`, `sound/bank/<id>`, `sound/wave/<id>` (about 4 MB;
  with the Crystal's and Obelisk's heal sounds, 175 and 176, nothing else
  of the 18 MB archive), and the DS Campaign's 15 story songs
  (`STORY_SONGS`), the staff roll's stream (`sound/strm/0`) and the tag
  screens' six sounds (`TAG_SE_CALLS`, after the roll in the story's range).
  The pack's version is 6 (3: the heal sounds, 4: the story songs, 5: the
  stream, 6: the tag sounds). A saved pack of an older version is rebuilt
  from the .nds by the scan when the .nds is in the ROMs folder (every
  start's first scan reads it, so a player updating needs to do nothing:
  `tango-library/tests/ds_pack_update.rs`, 0.5.0's version 5 pack to 6, the
  tag sounds there). Without the .nds a pack older than 3 is ignored; one
  of 3 or later still loads (what it lacks stood in for by AW2's like
  sounds, or silent: the tag screens), and the Play tab says it is out of
  date and to put the .nds back (`ds_pack::outdated`,
  `tests/ds_pack_update_no_nds.rs`). Power music stays AW2's
  (Dual Strike's is shared too).
- **Sequence.** Each SSEQ track is walked (calls inlined, loops and jumps
  followed; the jump back is the loop) into timed notes and controls, and
  written as an MP2K track that plays the intro, then the loop, then GOTOs
  back. Dual Strike counts 48 ticks a beat, MP2K 24: the song's TEMPO byte is
  the full beat count (not half), so every tick is kept (tempo accurate to
  0.2%). Volume, expression and the sequence's volume are Dual Strike's
  squared curves made linear (`VOL`), velocities likewise; pan, pitch bend
  (halved to MP2K's range), modulation carry over; notes longer than `N96`
  are `TIE`d and ended by `EOT`. The themes' music player (`0x03005AE0`,
  songs with player 1) has 8 tracks: songs with 9 to 11 tracks (Jugger,
  Koal, Kindle, Von Bolt, Grimm, Sasha, Rachel) have the tracks that sound
  together least merged (VOICE/VOL/PAN switched before the other track's
  notes).
- **Instruments.** Each program played is an MP2K rhythm voice (type
  `0x80`, 128 sub-voices) so every key plays its own region's sample at its
  own root (sub-voice key `60 + key - root`); region pan is a forced pan.
  Dual Strike's PSG square and noise (Kindle's theme) play made-up
  DirectSound samples (a square of the region's duty, an LFSR noise), so
  the themes never use the GB sound channels AW2's sound effects share.
  Samples (IMA-ADPCM, 22 kHz) are decoded, low-passed and resampled to AW2's
  mixing rate (13379 Hz; a loop keeps a whole number of samples and the
  rate follows it) and stored 8-bit; one copy per sample. Envelopes: Dual
  Strike steps every 5.2 ms in decibels, MP2K once a frame in linear
  amplitude: decay and release become the per-frame factor for the same
  dB fall, sustain the squared level, attack the step that reaches full in
  the same time.
- **Where.** From `0x08800000`: a mark, AW2's song table (`0x0824238C`, 505
  entries) copied with the nine new songs after it (ids 505..513, player 1),
  then voice groups, samples and tracks (about 5 MB). The table's six
  literal-pool words (`0x080704A0`, `0x080704D4`, `0x08070520`,
  `0x08070574`, `0x080705A8`, `0x08072B9C`) are switched while the pack is
  on, and the new COs' rows name their song (row `+0x04`). The game starts
  a CO's music with `sub_0803B524(id)` (id at `0x030005CA`).
- **Channels.** Dual Strike plays up to 16 notes at once; AW2 mixes 8
  DirectSound channels (SoundInfo `[0x03007FF0]+6`) of the 12 the engine
  has (the other 4 sit unused before the PCM buffer at `0x03004AE0`). While
  one of the new themes is the music (player `0x03005AE0`'s song), 12 are
  mixed, 8 otherwise (the extra 4 stopped when it goes back).
- **Compromises.** Notes past 12 at once are cut by MP2K's channel
  stealing; merged tracks share one volume and pan at a time; the samples
  are 8-bit at 13 kHz; Dual Strike's portamento, tie mode, sweep and
  per-track envelope changes (none used by these nine) are not converted;
  each loop sets its tracks' state in full where it starts, so its first
  pass starts from the state later passes have;
  the per-song level is Dual Strike's, scaled once (`GAIN`) to sit with
  AW2's themes.
- Tests: `tools/aw2test/tests/test_co_music.py` (every new CO's turn, human
  and CPU, starts its song; Von Bolt's loops, survives his power and a
  battle scene, and plays in a five-army game; AW2's COs and songs
  unchanged; without the pack nothing changes). `aw2_script`'s `audio` /
  `audioend FILE` record the console's sound (`Emu.audio_start/audio_end`).

Com Towers (`com_tower.rs`, `design_bar.rs`): a Lab is a Com Tower in Versus
and in the Design Room. In battle its sprite comes from `gProperty`
(0x03003150, the buildings `RecountArmyProperties` lists; `sub_0803F990` draws
them), so the tower stays in that list; only in the editor, which tangoAW2
draws the towers in itself (OBJ tiles 524..531) and where the towers skip the
editor's property bookkeeping, is a Lab left out of it (trap `0x08021C4C`;
0.3.0 and 0.3.1 left it out in battle too, and no tower was drawn on the
battle map). Capturing one never ends the battle (`0x0804281E`). In the
terrain bar the Tower entry (word `0x14 | owner << 5`, tiles `0x1D9..0x1DD`,
Black Hole's `0x1B9`) is one of the editor's properties: the editor's "is a
property" (`sub_0800C7E8`) answers 1 for a Lab to the bar's and the Feature
panel's twelve calls (checked by return address; its map-cell callers
`sub_0800C840`/`sub_0800C608` are left alone), so UP, DOWN and SELECT change
the bar's army on it (neutral, the four armies, Black Hole) and it is redrawn
in that army's colours. The army change is committed by `sub_080077EC`
(`0x0800701A`), which rewrites the list's five property entries (9..13) and
then places them among the shown entries (`0x0200B0D0`, 0x1C each, word at
+4) by the highlighted word's kind; a trap after the list is rewritten
(`0x0800782A`) gives the tower's list entry the new army too, and with the
tower highlighted writes only its shown entry and returns (`0x080078C2`),
since the game's placement has no case for a Lab. The list builder's trap
(`0x080079B2`) builds the tower for the builder's army (r5). A on the map
places the picked tool's army (`0x0200B02A`, class | owner << 5). 0.3.1 kept
its own army for the tower entry, which the shown entry, the picked tool and
the placed tile did not follow: the bar showed and placed the army it was
opened with.

In a five-army battle the Lab's tiles hold Black Hole's HQ, so the tower is
drawn from the Crystal's battle tiles (OBJ 0x19A..0x1A1; the Obelisk's
0x176.. with a Crystal on the map; `com_tower::after_sheet`, after the sheet
loads and every frame). A five-army game is on from the moment its map is
picked, and on the Teams screen tiles 400..435 are the first column's face:
0.3.0 to 0.4.0 wrote the tower over 410..417 there (a band across the face's
eyes, with the pack, on 5P maps and five-army design maps). The tiles are now
taken only while they hold what `obelisk::load_tiles` put there (the
editor's 524.. as before). Tests: `tools/aw2test/tests/test_teams_faces.py`
(each column's face tiles against its CO's face in the ROM image, every CO
of the list in the first and fifth columns, 2 and 5 armies, straight from
the title and after Survival and the Campaign box; and the five-army
battle's tower picture).

The Oozium (`oozium.rs`, the Dual Strike rule): it has no weapon (no Fire, no
counter-attack). Its move takes in the squares next to it holding a unit of
another team, any unit (air units and ships in port too) on a square it can
enter; moving onto one and choosing Wait destroys that unit with the game's
destruction (`sub_0804018C`: explosion, units lost, rout), charges both power
meters as a battle in which the victim lost all its HP, and counts a unit
destroyed for the eater's army. A hidden unit on that square is eaten too
(no Trap!). The CPU eats with its Ooziums as its turn starts (the most
valuable unit next to one) and moves the others a square towards the enemy.
Nothing from a CO changes an Oozium, as in Dual Strike, whose CO stat
functions (arm9 0x020E5678, 0x020E57AC, 0x020E5A58, 0x020E5C40, 0x020E5D8C)
return 0 for its unit class (6) before the power's +10 defence (player +0x28)
is added, and whose CO blocks' unit filters (block +0x34: 0x020E25E8,
0x020E2610) leave class 6 out: no CO stats (not even a power's +10 defence,
nor Com Towers' or Javier's), no power's damage, stun or fuel loss, no
repair, move-again or resupply; a Missile Silo's and a Black Bomb's blasts
spare it, and the CPU's silo and strike scoring leave it out.

`tools/aw2test` plays real battles in both modes and checks them against its
own damage calculator (Dual Strike's numbers read from the .nds in `ds` mode),
fires every CO's COP and SCOP, and replays netplay runs on two rollback peers.

## Survival (`survival.rs`, `survival_maps.rs`, `survival_ui.rs`, `mode_menu.rs`)

Dual Strike's Survival mode, with the Dual Strike pack, offline. Everything
below about Dual Strike was read from its code and data (the USA ROM; overlay
0 is loaded at `0x022AD560`, the survival state is `0x022A7B80`).

**Dual Strike's Survival, as found.** Three kinds (the state's kind byte, +7):
Time (0), Money (1), Turn (2); 3..5 are the Champion courses of the same three.
Each basic run is eleven maps fought in a row against the computer, the same
eleven every time, from a list per kind (u16 map ids, overlay 0 `0x022F64FC`
Time, `0x022F652C` Money, `0x022F6514` Turn; `sub_020EAC50` picks the list):

| # | Money (500,000 G) | Turn (99 days) | Time (25 minutes) |
|---|---|---|---|
| 1 | Silo Sweep | Convoy Cape | Red Heart |
| 2 | Bad Pangaea | Cannon Land | Frozen Pipes |
| 3 | Chokepoint | Mr. Fix-It | Cape Splinter |
| 4 | Cold Shoulder | Aircraft Hunt | Lake Fever |
| 5 | Crowded Plain | Rain of Pain | Open Road |
| 6 | Narrow Road | Lone Wolf | The Middleman |
| 7 | Triple Threat | Fenced In | Stealth Fight |
| 8 | The Gooping | River Raid | Tactical Decoy |
| 9 | Single File Isle | Crystal Field | Last Stand |
| 10 | The Swarm | Five Mile Isle | Pursuit Plains |
| 11 | Grit's Gambit | Forest Frenzy | Fog Hunter |

- **Budgets** (arm9 `0x02168D04`, a word per kind): 90000 frames, 500000 G,
  99 days; Champion 108000, 600000, 120.
- **Which maps there are** (checked by `survival_lists_are_dual_strikes`):
  these 33, Dual Strike's map ids 0xBC..0xDC and no others. The Champion
  courses add none (below).
- **The Champion courses, as found** (kinds 3..5 of the state's kind byte;
  the .nds read statically and played in melonDS with `ds_script`, the
  unlock bits poked into the save RAM, `0x022A7F50`'s bits, to see them):
  - *Maps*: the same three lists (`sub_020EAC50` returns overlay
    `0x022F64E4` for Time, `0x022F6544` for Money, `0x022F64CC` for Turn:
    each byte for byte the basic course's list), but **endless**: the map
    of index n is `list[n mod 11]` (`sub_020EAAD8` takes the remainder of
    the hardware divider), the run never counts as cleared, and the
    results come only when it is lost. The info page calls each pass of
    the list a wave ("2 Wave").
  - *Budgets* (arm9 `0x02168D04`, words 3..5): Time 108000 frames (30:00),
    Money 600,000 G, Turn 120 days. Nothing else differs: every rule that
    tests the kind (`sub_020EA944` running out, the Money no-income rules at
    `0x020C0DB8`, `0x020C4F64`, `0x020C8414`, Turn's `0x020B973C`) takes 3
    with 0, 4 with 1 and 5 with 2; the enemy's funds, strength and COs are
    the map's own (the same maps).
  - *Record and rank*: the record is the number of maps cleared (the map
    index `state + 6`), kept when larger (`sub_020EAE84`'s second half, 8
    bytes a kind from `0x02291554`: the CO pair and the count) and saved when
    the run is **lost** (`0x020D6010`; a win on a Champion map saves
    nothing: `0x020D5F5C`). The rank goes by that count alone
    (`sub_020EAD98`'s last branch): S from 20 maps, A from 15, B from 10,
    else C. The bonus (`sub_020EB024`) is 5 + 10 + .. + 5n for n maps
    cleared, at most 9999, added to the points; the budget left counts for
    nothing.
  - *How they open*: Dual Strike's **shop** sells each for 1000 medals (item
    records at `0x0216CC78`.., text ids 406..408 "Time/Turn/Money Champion",
    the purchase's text "You can now play the Champion Course in ..."). An
    item shows once its basic course has been cleared (its availability
    function, `0x02101EF4`/`EB0`/`E6C`, reads the clear bit 0x2C Time, 0x2D
    Turn, 0x2E Money, set by `0x020D5F2C`.. when the last map of a basic
    course is won) and the course opens once bought (bit 0x2F Time, 0x30 Turn,
    0x31 Money, tested by `0x02047960`). Before that the course screen
    shows the BASIC COURSE panel only.
  - *How they look*: the course screen gets a second panel under the BASIC
    COURSE one, headed by the CHAMPION COURSE banner (`ohashi/res_survival`'s
    stream 0, blocks 4..7 after the basic course's 0..3): "Infinite" for
    the maps, the budget under its label (Funds, Turn total, Total time),
    and "Maps clrd." with the best count, the two COs of that run, and a
    rank badge; the INFO page's strip shows as many map boxes as the best run
    cleared (at most 11, then "2 Wave" and so on). A on the panel goes
    straight to the CO screen.
- **Running out** (`sub_020EA944`, every frame of a battle): Money, the
  player's funds reach 0; Turn, the day passes what is left; Time, the
  player's own clock (it only runs on the player's turns) reaches what is
  left. Then the run is over.
- **What a cleared map costs** (`sub_020EA87C`): Money, the funds spent;
  Turn, the day it was won on less one; Time, the player's time in whole
  seconds. Money has no income at all: properties, joined units' extra HP,
  Colin's and Sasha's powers earn nothing.
- **Points**: each map's battle score added up (at most 9999); a cleared run
  adds a bonus for what is left (`sub_020EB024`): a point per 2 seconds, 10
  per day, 1 per 200 G. **Rank** (`sub_020EAD98`) by what is left: S from 9
  minutes / 50,000 G / 25 days, A from 6 / 25,000 / 15, B from 3 / 10,000 / 5,
  else C. **Records** (`sub_020EAE84`): per kind, the best leftover with the
  run's two COs.
- **COs**: picked once for the run (a tag pair in Dual Strike: the survival
  state's +0/+1, copied into the player at every map start, `sub_020EACC4`).
- **Maps**: Dual Strike's own Survival maps, in AW2's map format (Dual Strike
  grew AW2's map header to 0xA0 bytes, overlay 0 `0x022DBDB0`, id n at n - 1;
  tiles are AW2's LZ77 blob of AW2 tile ids; units 13-byte records). Each
  brings its fog (+0x34), weather (+0x33: clear, snow, rain, sandstorm), look
  (+0x32: normal, snow, desert, wasteland), the computer's COs (+0x70 army 2,
  +0x72 army 3) and its pre-deployed units.

**In tangoAW2.**

- **Select Mode** (`mode_menu.rs`): a seventh entry on the wheel, SURVIVAL,
  between War Room and Battle Maps, with labels built at run time from the
  game's own label art (the letters of DESIGN ROOM, VERSUS, BATTLEMAPS,
  CAMPAIGN and LINK, in a teal of Campaign's and Link's colours) and a help
  line (Dual Strike's own, its text 1224). Hook points (for merging other Select Mode work): every `DivRem(x, 6)`
  of the wheel's code (`movs r1, #6` before `bl 0x0808AAB0` in
  `0x08080F00..0x08084C00`, found by scanning) becomes 7; the position wraps
  `0x08081DF0`, `0x08081E2C`, `0x0808280C`, `0x08082830`;
  `SetMainMenuCarouselPosition` `0x08080F68` ((i + 5) % 7) and `0x08080F7E`;
  the 34 words pointing at the item table `0x0861696C` point at a 7-entry copy
  `[5, 8, 2, 4, 3, 1, 0]` (item 8 is Survival); help lines: the table
  `0x08616FA4` (pool `0x08084680`) and the choices' table `0x08616FB4` (pool
  `0x080846C0`) are copied with Survival at line index 6 (Sound Room 7, Hard
  Campaign 8: `0x08084630`, `0x0808464E`; Campaign's index `0x0808464A`).
  Traps: `0x080845A8` (centre label), `0x08084858`, `0x08084864`,
  `0x0808488C` (tile complete, palettes), `0x08081498` and `0x08081E94`
  (item 8 goes like Link: A starts it), `0x08081EEE` (picked) and `0x08081EF6`
  (the mode store: War Room New, 5). The small label sits in OBJ tiles
  0x320.. with OBJ palette 13; `remap` (at the sprite flush) points the game's
  item-8 sprites (tile `0x1D8 + 32 * 8`, palette 10) at them. The wheel is the
  game's own with the pack off (every patch put back, nothing traps). One more
  entry would need its own OBJ palette and tiles and the table, wraps and
  `DivRem` sites for eight.
- **Screens.** Picking it opens the War Room's own SELECT MAP on Survival's
  maps (its list: Money, Turn and Time Survival), then the War Room's CO
  screen, LET'S GO, the battle, the War Room's results and its save prompt.
  Back on SELECT MAP only the run's next map is listed, until the run is
  cleared or lost. SELECT MAP itself is drawn as Dual Strike's course screen
  (`survival_ui.rs`, below); from the second map on, the CO screen offers
  only the run's CO (one group with that CO, as the campaign's restricted
  CO screens build theirs: trap `0x0807C588`). B on SELECT MAP leaves
  Survival (a run in progress is given up).
- **SELECT MAP in Dual Strike's look** (`survival_ui.rs`). Dual Strike's
  course screen (its title, the BASIC COURSE panel with the number of maps,
  the budget and the best, the strip of the course's eleven maps, the map
  under the cursor, its RECORD box) fitted to 240x160. Converted at run time
  from the pack: the title font (`ohashi/res_modefont`: glyphs of 16x32
  pixels, A..Z, the star, the dash; palette in the file's last 64 bytes),
  the banner (`ohashi/res_survival`: the first LZ stream, four blocks of 4x2
  tiles side by side = 128x16; palette in the last 770 bytes), the ring
  wallpaper (`ohashi/res_wall_base`: tiles and the first 32x32 of its map in
  the first two LZ streams, palette in the last 32 bytes). Its words are the
  overlay's (`0x0230E718..`: Funds, Spent, Maps, Turn total, Turns used,
  Total time, Time used, Funds left, Turns left, Time left, Maps clrd.), the
  rest is AW2's own proportional font (`0x084C32E4`, widths `0x084C36E4`)
  and window colours (red above, blue below, as Dual Strike's and AW2's own
  windows). The map's picture is drawn from the converted tiles with the
  game's own terrain classes (`0x080C1BC4`), a pixel or more per tile in its
  own palette bank. Pages: the course (the panel, the strip with the cursor's
  corner brackets on the browsed map, the map's number, name, computer CO and
  conditions; between maps the cleared ones are dark, the next yellow and the
  panel says Maps clrd. and what is left), the results (CLEAR or GAME OVER in
  the title font, maps cleared, what is left, bonus, points, rank in the
  title font) and the records (R: each course's rank, CO and what it used).
  How: BG0 (char block and screen as the screen has them, 0 and 14) is
  written once the list takes the pad (the proc's callback `0x08085F91`)
  and again when what it shows changes (a hash of the run's state, the
  browsed map and the record bytes); every colour is index 1..15 of two
  palette banks (0: the screen, 1: the map picture on 8x5 cells), so the
  picture is opaque over the other layers; the game's sprites are switched
  off in the frame's sprite list at the flush; the DISPCNT shadow's window
  bits are cleared while it is up (the cursor's move turns WIN1 on, which
  would cut the picture); LEFT and RIGHT browse the maps, R opens the
  records, B closes them (the game sees none of them), UP and DOWN change
  the course and A starts it, as the game's own list does. Nothing is put
  back when the screen goes: the next screen loads its own BG0. The state is
  `0x0203FA26..0x0203FA33` (shown, browsed map, records open, context,
  signature; the 32-bit ones on words).
- **Maps** (`survival_maps.rs`): the 33 maps are read from the pack and
  converted at the first frame with the pack: ids 0xC9..0xCB are the three
  runs' entries (each the run's first map, named after its kind), 0xCC..0xEC
  the maps in Dual Strike's id order. Tiles are AW2's own ids except Dual
  Strike's Black Crystal (0x1A1 -> tangoAW2's 0x192), Com Towers (0x1B9..0x1BD
  -> the Labs 0x1D9..0x1DD) and its other two mountains (0x146, 0x147 ->
  AW2's mountain 0x022, as the DS Campaign's maps: Dual Strike draws every
  mountain cell as one of 0x020, 0x146, 0x147 by position). Their 4x4 structures (Convoy Cape, Lone Wolf,
  Silo Sweep) are AW2's own tiles, as on AW2's T Minus 15 and Sea Fortress,
  and are drawn as a sprite whose picture the map header names
  (`tileGraphic4x4`, +0x10, loaded by `LoadInventionGraphics`
  `0x0803FD80`): Dual Strike's header names its picture at +0x24, a `bmap`
  file ("0a5" the missile pad, "0a6" the fortress), byte for byte AW2's
  `0x080D2DA8` and `0x080D38AC`, which the converted header names. (The
  first Survival left +0x10 empty, and those three maps showed whatever OBJ
  VRAM held there, a CO portrait among it.)
  Units: Carrier and Oozium become tangoAW2's 26 and 27; every unit gets the
  AI byte tangoAW2's Versus maps use (4). Headers: AW2's 0x5C bytes, with the
  map's fog, armies, colours, computer COs (Dual Strike's ids to tangoAW2's),
  speed rank day limit, on a tab of their own (0x0A).
- **Map table.** With the pack the game reads tangoAW2's copy of the map table
  with room for 0x100 ids (`0x08E00000`; the 37 words of
  `five_map.rs` switch to it, and five_map
  writes its tabs into whichever table is in use); the map list's loops walk
  to 0xEC while Survival is on. The War Room lists tab 0x0A instead of 7 while
  Survival is on (`BuildMapListForMode`'s table, `0x08090EF2`), and its map list
  draws only the rows the list has (`DrawMapList` trap `0x08086A58`; the War
  Room never had fewer than seven maps).
- **Rules per map** (at every map start, `sandstorm.rs`'s trap `0x08035490`):
  the weather as fixed weather (sandstorm as tangoAW2's fixed sandstorm), the
  map's look (Snow, Desert and Wasteland drawn with Dual Strike's own terrain,
  `wasteland::set_ds_look`; Normal is AW2's), the run's CO, and for Money the funds (the
  pool) with no income (`propertyFunds` 0, and any funds gained are taken
  back every frame), and the map's fog (the War Room sets gPlaySt's fog from
  the header of the map it opened with, `sub_080346FC`, before one is
  picked).
- **The budget in battle**: two lines centred at the top of the battle
  map, "Map 3/11" and Dual Strike's "Funds left 412000 G", "Turns left 87"
  or "Time left 21:10" (what is left now: funds, days left today included, or
  the time), in AW2's proportional font, white outlined in black as the
  second front's title is, 8x16 sprites in the OBJ tiles the map leaves
  free (`two_front::free_tile_pairs`; not while a structure's heal plays in
  them).   Out of budget, the player's army yields (`unk31`, as the map menu's Yield
  does) and loses at the game's next rules check.
- **End of a map** (`EndOfGame_Finish`, trap `0x0803832C`): won, the map's
  cost is taken off, its score added, the next map listed; the last map
  cleared works out the bonus, rank and record. Lost, the run is over.
  The War Room keeps its records by `id - 0x6C`: while Survival is on its
  record readers and writer (pools `0x0808759C`, `0x08087664`, `0x08087B18`,
  `0x08087C6C`, `0x080177E4`) read a zeroed block of ours; `SetMapPlayed`
  (`0x0803CA28`) skips Survival's ids (its bits stop at 0xBF). The map menu
  hides Save on a Survival map (`0x0802C646`): a suspended map would come back
  without its run. The War Room's end of a map asks its save question with
  the War Room's suspend slot (`sub_0803D73C(3, ..)`), which clears the
  profile's "War Room game saved" flag and deletes slot 3 when it saves; a
  Survival map asks with slot 6 instead (the prompt's "profile only", as
  `sub_0803D960` uses it; trap `0x0803D746`), so a War Room game saved
  halfway survives a Survival run (until this, the first Survival map ended
  took it away; `save_survival_keeps_war_room_suspend`).
- **Records** in the profile the game saves (so the save's own checksum covers
  them): `0x0200C435..=0x0200C43F`, the eleven bytes between
  `0x0200C420`'s +0x14 and +0x20 that no code of the game reads or writes
  (`PackProfileRecord` saves 0xE0 bytes from `0x0200C420`; a test checked the
  bytes stay untouched through boot and battles): each basic course's best
  (kept when a run is cleared with more left than the record) and each
  Champion course's most maps cleared; the layout is under "Where the
  records live" below.
- **RAM**: `0x0203FA00..0x0203FA3F` (the run: on, kind, maps cleared, phase,
  left, budget, points, the map's time, the funds cap, CO, the menu's pick,
  bonus, rank, `+0x21` the Champion course flag), `0x0203FA40..0x0203FD0F` (the War Room record rows Survival
  reads). **ROM**: `0x08E00000..0x08E05BFF` (map table), `0x08E08000..`
  (map data, 0x800 per map), `0x08E30000..` (strings), `0x08E40000..0x08E40FFF`
  (the wheel's data and labels); text ids 0x7172.. (pointers at `0x0862D000`).
- **The Champion courses** (kind byte unchanged, a Champion byte at
  `0x0203FA21`; Dual Strike's kinds 3..5). Each is a list entry of its own
  after the three basic courses, ids `0xED..0xEF` (Money, Turn, Time; the
  header is the course's first map's, named "Money Champion" and so on, text
  ids 0x7172 + 38..40), shown only once open; the list loops walk to 0xEF.
  **Unlock: tangoAW2 has no shop, so a Champion course opens when its basic
  course has been cleared** (Dual Strike: cleared, then bought for 1000
  medals); a basic course's record exists exactly then, so the unlock needs
  no bit of its own, and a profile with basic records already (0.5.x) has
  the courses open. Played as Dual Strike has them (above): the larger
  budget, the list round again after the eleventh map (the HUD reads "Map
  14", no "/11"), lost when the budget runs out or a map is lost. The lost
  run's page is GAME OVER with the maps cleared, the bonus and the rank in
  the title font; the record is the maps cleared. The course screen is the
  basic one with the CHAMPION COURSE banner, Infinite, the Champion budget,
  Maps clrd. (the best, "14 Maps", with a rank box) and the strip's maps
  dark up to the best (the strip stays eleven maps so every map can still
  be browsed); between maps the panel says "Wave n" under the count. R's
  page lists the six courses, a Champion course Locked until its basic
  course is cleared.
- **Where the records live** (the profile the game saves, so its own
  checksum covers them; `survival.rs`'s `Records`): the eleven bytes
  `0x0200C435..=0x0200C43F` of the options block, which no code of the
  game reads or writes (`PackProfileRecord` saves 0xE0 bytes from
  `0x0200C420`; a test checks the neighbours stay untouched). Layout 2,
  written since 0.5.3: `0xD6`, then 76 bits, least significant first: per
  basic course (Time, Money, Turn) the best clear's CO (7 bits, 0 for none)
  and what was left (11 bits of seconds, 13 of hundreds of G, 7 of days:
  each field is the budget's own limit); then each Champion course's maps
  cleared (8 bits, 0 for none). The rank is worked out from what was left.
  Layout 1 (0.5.0..0.5.2: `0xD5`, three bytes a kind: rank 3 bits, CO 7,
  left 14) is still read, and replaced by layout 2 at the next record, the
  basic records as they were. The profile has no room for a Champion CO
  (the 88 bits are 8 for the mark, 52 for the basic courses, 24 for the
  counts), so a Champion record is the count alone where Dual Strike keeps
  the CO pair too. (Flag bits in AW2's unlock block `0x02028030` are no
  safer: its campaign flags are rewritten by a new campaign.)

**Compromises.**

- AW2 has no tag battles: the run keeps one CO (the one picked for the first
  map) where Dual Strike keeps a pair; the record keeps that CO.
- A run cannot be suspended mid-map, and turning the console off loses a run
  in progress (Dual Strike saves its survival state); records are saved.
- The War Room's CO screen colours the player's army by its CO's country and
  moves a computer army off that colour, as it does for its own maps; two
  armies Dual Strike gives one colour (Single File Isle's allies) get two.
- Points are AW2's War Room scores (its Speed, Power and Technique), not Dual
  Strike's.
- Records are the best of each course (what it used, with the rank and the
  CO), not Dual Strike's best per map: the profile has eleven free bytes, not
  room for 33 more records. The RECORD box of Dual Strike's map page shows
  the map's name and its computer CO here (labelled MAP), where Dual Strike
  shows that map's best.
- The Champion courses open when their basic course is cleared, not
  bought in a shop for medals; their record is the maps cleared without the
  CO pair; the strip stays the course's eleven maps (Dual Strike's shows
  the maps the best run reached, with its wave count).
- Dual Strike's course screen spreads over two screens (lion crests, the
  enemy CO's portrait, a BACK button); the crests and the portrait are left
  out and the CO's name is written instead.

Tests: `tools/aw2test/tests/test_survival_screens.py` (the screen read back
from VRAM against the .nds: the title's pixels from `res_modefont`, the
banner's from `res_survival`, Dual Strike's words, AW2's font for the rest,
the game's sprites off, every one of the 33 maps' pages whole and named, the
browse and record keys unseen by the game, the between-maps and results
pages, the budget's two lines on the map in each kind, and the lists, order
and budgets of Dual Strike's 33 maps), and
`tools/aw2test/tests/test_survival.py` (Select Mode with and without
the pack, each kind's first map checked tile by tile, unit by unit and for
fog, weather, look and colours against the .nds directly
(`aw2test/survival.py`), every one of the 33 maps likewise in battle with its
structure's picture named in its header and loaded into OBJ VRAM, the budget carried to map 2 and the CO kept, losing
each kind by running out, a cleared run's rank, bonus and record, saved and
read back after a reboot, every army a CPU for days on six maps, nothing of it
without the pack). `tests/test_survival_champion.py`: the Champion courses as
the .nds has them (lists, budgets, rank and bonus code, the shop's bits),
locked at first and open after a real basic clear (only that kind's), each
course screen against the .nds's banner, the budgets and the HUD, the list
going round after the eleventh map, the results (maps cleared, bonus, rank),
records that only improve, the six-course record page, the eleven profile
bytes saved (nothing else of Survival's changed) and read after a reboot, and
a save from 0.5.2 read and rewritten.

## DS Campaign (`ds_campaign.rs`, `ds_campaign_data.rs`, `ds_campaign_rules.rs`, `campaign_menu.rs`)

**The campaign model** (`campaign_model.rs`). The engine (`ds_campaign.rs`:
sessions, the map table entry, flags, saves, the world map's flow, the
mission end, the staff roll's flow, Hard and records) plays a `Model`, not
Dual Strike: the missions compiled for AW2 (`Built`: map headers, maps,
deployments, AW2 event scripts and trigger lists, texts, magic stubs, per
mission its `MissionInfo`), how many missions there are (at most 32), the
play order, the side missions with the flag that opens each, the last
mission, the story (prologue, scenes after wins), the staff roll, the
narration pictures, and the rules (`Source::rules`: what the scripts' magic
functions answer). A `Source` (label, available, load, rules) loads its
campaign into a model; `SOURCES` lists them, and the Campaign sub-menu
lists AW2's own campaign and then each source whose campaign is there, any
number of them (two rows show at a time; UP and DOWN go through them all,
wrapping, the window following the cursor). Dual Strike's is today's only
source (`ds_campaign_data::load`, with `ds_worldmap.rs`, `ds_story_art.rs`,
`ds_credits.rs`, `ds_music.rs`). A custom campaign is another source: its
missions laid out with `Built::add`/`Built::add_magic` in AW2's event
format, its order and rules its own (it shares the engine's flows: the
save, the world map, the staff roll, Hard, records).

Dual Strike's story campaign, played in AW2's own campaign engine, with the
Dual Strike pack, offline. Everything of Dual Strike's is read from the
player's .nds and converted at run time; none of it is in the repository.
Names of AW2's functions and data below are the aw2bhr decompilation's
(`github.com/Mad-Man-Dan/aw2bhr`; it has no licence, so it was read as a
reference only: no code, tables or text of it are copied).

**Dual Strike's campaign, as found** (USA ROM; overlay 0 at `0x022AD560`,
overlay 1, the campaign's code, at `0x02350560`).

- **Missions.** Map records of 0xA0 bytes at `0x022DBD28 + 0xA0 * id`; the
  campaign is ids 0xE0..0xFB, 28 missions, then 0xFC..0x100, five second
  fronts. A record: +0x00 the event header (six trigger lists), +0x04 the
  objective script, +0x10 the second front's id, +0x14 the name (text bank
  0xC0), +0x20 the CO pool the player picks from (an ARM9 list), +0x24 the
  armies, +0x0C the 4x4 structure's picture (a `bmap` name: "0a5" missile
  pad, "0a6" fortress), +0x1A/+0x1B/+0x1C look, weather, fog,
  +0x2C/+0x30 rank days and day limits (normal, hard), +0x41 the
  mission's number, +0x44/+0x48 the map (normal, hard: AW2's LZ77 blob of
  AW2 tile ids), +0x4C/+0x50 the units (13-byte records, FE army, FF end),
  +0x56 (CO, tag CO) per army (0x1C: the player picks), +0x88 colours, +0x8D
  teams.
- **The 25 story missions**: Jake's Trial, The New Black, Max Attacks,
  Reclaim the Skies, Neverending War, The Ocean Blue, Fog Rolls In, Tag
  Battle, Victory or Death!, Black Boats Ahoy!, Lightning Strikes, Frozen
  Fortress, Verdant Hills, Snow Hunters, Omens and Signs, Into the Woods,
  Muck Amok!, Healing Touch, Crystal Calamity, Dark Ambition, Pincer Strike,
  Ring of Fire, Surrounded!, For the Future!, Means to an End; and three
  research-lab missions, The Long March, Lash's Test, Spiral Garden, each
  opened by capturing the city that hides its lab's map in the mission
  before (Black Boats Ahoy!, Frozen Fortress, Snow Hunters: their scripts set
  campaign flags 0x60..0x62; tangoAW2 keeps them at 0x90..0x92, since 0x60
  is AW2's Hard Campaign flag and with it set every mission used its hard
  deployment, as 0.4.0 did; a 0.4.0 record's flags move as it loads). Second fronts: Victory or Death!, Lightning
  Strikes, Omens and Signs, Ring of Fire, Means to an End (played on both
  fronts: "Two fronts" below).
- **Events** are AW2's, grown. Trigger records are 8 bytes, op = 3 * AW2's
  op + the front (0 main, 1 second, 2 either), 0x15/0x16 open a block for
  normal/hard only, 0x1A ends a list. Scripts are AW2's 16-byte commands
  with ops renumbered (Dual Strike's handler table at ARM9 `0x021585C0`,
  0x5D ops); conditions and actions are calls into overlay 1 (about 40
  conditions: units moved, out of fuel, a type gone, a property owned, a
  structure destroyed, a day; actions: weather, unlocks, spawns). Dialogue
  is text by reference (bank << 24 | index; the banks table at
  `0x022F6BF0`, mission banks 0x21..0x40), ASCII with `\r`, `\x0e` (pause),
  `\x0f` (end of box); faces are `co | expression << 8`.

**In tangoAW2.**

- **Select Mode** (`campaign_menu.rs`): Campaign opens a small sub-menu in
  the box Campaign's Continue / New use, AW2 CAMPAIGN, DS CAMPAIGN and BH CAMPAIGN (80x16
  labels in the game's style, OBJ tiles 832..903, palettes 8 and 10, put in
  place of the box's own label sprites at the sprite flush). AW2 CAMPAIGN
  then shows AW2's own Continue / New, unchanged; DS CAMPAIGN shows them for
  the DS Campaign (Continue when a DS Campaign is saved); BH CAMPAIGN's are the BH
Campaign's ("BH Campaign" below); B goes back. It
  works on both wheel procs (`0x08616A08` on entering Select Mode,
  `0x08616A40` when coming back from a mode) and on Survival's seven-entry
  wheel (`mode_menu::item` reads the item at a position). Without the pack
  the box is AW2's own.
- **Start**: the DS box sets a request (`0x0203FD11`); the game's own
  Campaign New / Continue (`sub_0803BA4C` / `sub_0803BA88`, trapped) then
  starts the DS session instead: campaign mode, map id 0xF0 (the mission's
  header written into that entry of Survival's 0x100-id map table), and a
  proc of ours: save the progress, AW2's CO select (`0x086165C0`) with Dual
  Strike's pool grouped by country when the mission has a player-picked CO,
  BG0 emptied (AW2's own campaign reaches its mission card through screens
  that clear it), `ResetRulesAfterCampaignMap`, then AW2's mission proc
  (`0x0849EBFC`: mission card, battle).
- **Conversion** (`ds_campaign_data.rs`, at the first frame with the pack,
  into ROM `0x08F00000..`, about 360 KB): every mission's map, deployment
  (AI behaviours 0, 1 and 5 kept, others hold), header, trigger lists and
  every script reachable from them, and 1,700 texts (text ids 0x7400..,
  pointers in the text table's free tail), Dual Strike's lines re-wrapped
  for AW2's two-line boxes (a box that needs more is spread evenly). Script
  ops: text, faces (Dual Strike's ids to AW2's and tangoAW2's new COs;
  soldiers to AW2's troopers), window frames, cursor, camera, waits, jumps,
  "unless CO", flags, wins and losses become AW2's; conditions and actions
  become magic stubs (Thumb: `ldr r3, =id; ldr r2, =0x0803CC5E; bx r2`, the
  landing trapped) run in Rust (`ds_campaign_rules.rs`, one entry per Dual
  Strike function, read from its code).
- **Mission end**: AW2's best-score record (`InsertBestScoreRecord`
  `0x08017720`) is skipped for map id 0xF0: its slot would land on the event
  script slots (`0x0200C600`) and stall the save prompt. Com Towers capture
  as in Versus (the battle goes on), except a lab mission's lab cells, which
  end it as Dual Strike's labs do.
- **Maps**: Dual Strike's tiles are AW2's but for Com Towers (the Lab
  tiles), Black Crystals (0x192), its Black Obelisks (a 3x3 whose middle
  row is 0x18C..0x18E, AW2's Black Factory tiles without the factory's
  fourth row: tangoAW2's Obelisk on AW2's Black Cannon footprint), Ring of
  Fire's Volcano (below) and the Grand Bolt (below).
- **Structures** are Dual Strike's, kind for kind and cell for cell
  (`test_ds_structures.py`, against the battle structure list melonDS
  shows at `0x02183B08 + 0x48DC`, built by `0x020DA650` from each cell's
  terrain class: 0x15 minicannon (kind 4), 0x17 Black Crystal (9), 0x18
  Grand Bolt part (0xB + n), 0x1A Black Cannon (3), 0x1C Volcano (2), 0x1D
  Black Obelisk (0xA), 0x1F a 4x4 picture (8)). Crystal Calamity's
  structure at the top, (9, 1), is Dual Strike's Black Cannon facing down
  (tiles 0x186..0x188, class 0x1A: 99 HP, 5 HP a shot, every day; its
  entry `0901db0463010132`, byte for byte AW2's), AW2's own Black Cannon
  here; the centre holds the mission's one Black Obelisk. (The Black Onyx
  of its dialogue is a satellite on Dual Strike's top screen, not on the
  map; see "Crystal Calamity: the Black Onyx" below.) Surrounded!'s four 4x4 pictures are
  two missile pads and two fortresses: AW2 loads only the header's picture
  (`LoadInventionGraphics`, `0x0803FD80`, OBJ tiles 0x130..), so on a map
  whose inventions are all 4x4 pictures the other one goes into the
  invention sheet's first 64 tiles (0xC4, none of its sprites drawn
  there) and those structures are drawn from it (`crate::obelisk`).
- **Rules per mission**: the header names AW2's picture of a 4x4
  structure (+0x10, the same bytes as Dual Strike's) and the fog; at each
  mission start (`crate::sandstorm`'s map-start trap `0x08035490`) the fog,
  the weather as fixed weather (sandstorm as tangoAW2's) and the look are set
  (Snow, Desert and Wasteland drawn with Dual Strike's own terrain,
  `wasteland::set_ds_look`).
- **Fog** is the record's +0x1C: Dual Strike's battle setup (ARM9
  `0x020D3BC0`, `0x020E9374`) reads `0x022DBD44 + 0xA0 * map id` and sets
  its battle's fog when it is nonzero (melonDS: Jake's Trial with the byte
  poked to 1 starts in fog). One byte for Normal and Hard; each second
  front has its own record. Fog Rolls In, Verdant Hills, Into the Woods
  and The Long March have it; no second front does. `tests/test_ds_campaign_fog.py`
  plays a round of every mission, Normal and Hard (second fronts
  included), and checks the fog against the .nds's byte all through.
- **Means to an End: the Grand Bolt** (`grand_bolt.rs`). Dual Strike draws
  its battle map in 3D, a 16x16 texture per cell; its map stores the Grand
  Bolt as a picture (cell (x, y) holds `8 + 0x20 * y + x`), which only Means
  to an End (map 0xF8) reads through its own table (arm9 `0x02157F84`,
  every other map `0x02157BC4`: per terrain id a texture and two flips,
  0x4000 left-right, 0x8000 top-bottom). The Grand Bolt is one quarter
  drawn four times: textures 0x78..0xA7 (16x16, 4 bits a pixel, one after
  another) in `bmap/024` (`025`/`026` the same with other edges), coloured
  by its terrain palette 2 (the cells' class 0x1B picks it, arm9
  `0x02157AE4`) from `bmap/00b` +0x40, as Dual Strike's screen shows it (read
  back from its texture palettes in melonDS). Here its cells are AW2's underlay (a structure's
  footprint: no unit enters; the terrain panel reads Dual Strike's
  "Blocked"), drawn by the Wasteland look's painter (`wasteland.rs`) with
  its own tiles: one per texture quadrant, mirrored by the tilemap's flips
  (172 tiles), put in the look's pool of free tiles, then in static
  terrain tiles no other cell of the map draws with (one already there
  used again), in BG palette 7 (the fogged copy of palette 3: the mission
  has no fog), set each frame; the texture's ground around the dome
  (its sand 7..11 and dots 12) takes the colours of the map's plain as
  drawn. Its three
  weak points ((3, 9), (9, 11), (15, 9), where Dual Strike's code tests its
  structure kinds 0xB..0xD) are minicannons on tile `0x194` (unused by
  AW2): no sprite (the picture draws its discs), no fire, no heal, "Bolt"
  and their hit points in the terrain panel. No Black Obelisk stands in
  the mission; Black Obelisks and Crystals keep their hit points nowhere
  (`obelisk.rs` has no such path). On Black Hole's turn of every sixth day
  each standing weak point destroys the unit below it and spawns an Oozium
  there (AW2's `CreateUnitAt`); destroying all three wins. Each is
  shielded (no target, a hit undone) until the Black Crystal guarding it is
  shattered on the mission's second front (below, "Two fronts").
  Tests: `ds_campaign_grand_bolt`, `ds_campaign_grand_bolt_blocks`,
  `test_obelisk_breakable.py` (Obelisks breakable on a Versus design map
  and in Crystal Calamity and For the Future!; in Means to an End only the
  closed weak points resist).
- **Flags**: AW2 keeps its campaign progress in campaign flags 0x20..;
  during a session the game's flag get/set (`0x0803CBD8` / `0x0803CBA0`,
  trapped) use the DS Campaign's own (`0x0203FD20`, 16 bytes).
- **World map** (`ds_worldmap.rs`): New and Continue open AW2's own
  campaign map screen (its `WorldMap*` procs: cursor, scrolling, flags,
  mission panel, reveal, music and sounds) on Dual Strike's Omega Land: its
  touch-screen map (`ohashi/res_gmap_map1`/`_map2`, LZ77 4bpp tiles and a
  32x32 tilemap each, ten palettes at `res_gmap` +0x3B08), fitted at the
  first DS session into 768 map tiles (AW2's 704 and the block of BG1's
  tilemap, `0x0600D800`, put back each frame on the DS map since the
  screen's setup writes BG1's tilemap there; BG1 is off on the DS map) and
  nine palettes (BG 6..14; tile 0 blank): flips folded, the most alike
  tiles of a palette folded together (shade weighted 4x over detail), the
  kept tiles refined (4 rounds); 31.4 dB against Dual Strike's picture,
  colour jumps across tile edges +1.6 over its own (the first fit: 29.3 dB,
  +3.2; `ds_campaign_world_map_picture`), with Dual Strike's mission points (ARM9 `0x0215BA04`). AW2's
  mission table (`0x08615194`) and reveal table (`0x0861500C`) get DS copies
  (ROM `0x08FC0000..`), and while a session is on, the literal-pool words
  that point at AW2's art and tables point at the copies. New shows Jake's
  Trial's flag alone; a mission's flag appears once it opens (the next
  story mission after a win, a lab mission once its map is found) and stays,
  cleared, once won (`ds_campaign_win_*` check every flag after each win
  and after Continue). Beside LEVEL under the cursor are AW2's difficulty
  stars (the table's +3 Normal, +4 Hard): Dual Strike has no difficulty
  value (none in its mission records or map points, none on its map), so
  they follow the mission's place in the campaign over AW2's ranges:
  Normal 1 + step x 7 / 28 (1..7), Hard Normal + 1 + step x 3 / 28 (2..10)
  (`ds_worldmap::stars`, `ds_campaign_world_map_stars`). Open missions have
  AW2's flag; A opens the mission's panel (its objective, AW2's info window),
  A again starts it (the CO screen when the player picks). Back on the map
  after a win the mission is cleared and the missions it opens are revealed
  as AW2 reveals its own; a won mission's point keeps AW2's starred flag
  (OBJ tiles 40..43, added at the sprite flush: AW2 paints a won mission's
  part of its continent instead). AW2's story steps on the way (nation
  panel, scenes after missions, bonus and alternative missions, the switch
  in `WorldMapReturn_Init` on its own mission ids, the save prompt) are
  skipped in a session, AW2's sea-and-grid layer (BG1) is held off on the
  DS map, and AW2's map state (`0x0202FDFC`, 0xFC bytes, part of its
  campaign save) is put aside and restored when the session ends.
- **The story outside the battles** (`ds_campaign_data::Story`): Dual
  Strike plays its story inside the missions (the turn-start lists' scenes,
  the match-end lists' victory and defeat scenes: converted with the rest)
  and, from overlay 5, the scenes its game flow starts after certain wins
  (ARM9 `0x020D63B0`, by map record id): the narration after Victory or
  Death! (0xE8: bank 0x21 text 3, over pictures), the victory party after
  Crystal Calamity (0xF2: overlay 5's proc script `0x023682E0`, scripts
  `0x023683C8`, `0x023686E8`, `0x023684E8`) and the ending after Means to an
  End (0xF8: proc script `0x02368AF8`, scripts `0x02369180`, `0x02368CA0`,
  `0x02368E40`, `0x02368FE0`, `0x02368B60`), and the prologue before the
  first map (bank 0x21 texts 0..2). Overlay 5's scripts are Dual Strike's
  event format and are converted as the battles' are (their calls are its
  picture screen's, left out), each one's end a jump to the next; the
  narration is AW2's speaker-less text (`ShowTextOnBg0`, op 0x1A) over
  the picture Dual Strike shows with it (`ds_story_art.rs`: its
  `rikiishi/` files, LZ77 tiles at 4 or 8 bits a pixel, an LZ77 map, a
  256-colour palette; 240x160 of the 256x192 picture with a light box
  where the text goes, put into the map layer's form: nine palettes by
  k-means over its cells, flips folded), put on the map's layer by a magic
  call before the text (BG3's tiles, tilemap and palettes 6..14, its
  scroll, the map's sprites off) and the map put back after. AW2
  plays a mission record's +0x18 on its map after the mission is won
  (`StartWorldMapAfterMissionScript`): the DS records of those three
  missions hold the scenes. The prologue: the session's copy of AW2's world
  map script from the menu (`0x0861485C`; the words pointing at it,
  `0x0807814C`, `0x0807817C`, `0x080781E4`, `0x0849EB90`, `0x08614750`,
  point at the copy during a session) calls a magic stub before the map
  takes the pad, which starts the prologue (`StartBlockingEventScript`) on
  a new campaign once (flag 0x9E of the record, saved right after).
- **Means to an End's choice**: its victory scene asks the player (a text
  ending in Dual Strike's choice code 0x16, then a jump on its answer,
  `0x020199A4`): the text ends in AW2's choice code (0x0E 0x17, as AW2's
  "Do you really yield?") and the jump asks AW2's answer
  (`IsTwoOptionChoiceFirst`, `0x080457BD`): Yes, Jake destroys the chair;
  No, Hawke does.
- **End of a mission** (`EndOfGame_FinishCampaignMap`, trapped past its
  prologue at `0x08038488`): the outcome is recorded (a loss leaves the
  flags as they were), the missions the win opens are written for the
  reveal, and the function's own tail runs (`ResetRulesAfterCampaignMap`,
  `StartCampaignAfterMap`: AW2's return to the map). After Means to an End
  the map stays up with every mission cleared. The mission card's number (`GetCampaignResultCountPlusOne`
  `0x0803840C`, trapped) counts DS missions won.
- **Music**: the maps play their COs' themes as AW2 does (the new COs'
  Dual Strike themes, `ds_music.rs`). Dual Strike's event songs (SDAT
  sequences 0x16, 0x17, 0x19, 0x1A, 0x23, 0x2C, 0x2D, 0x3D, 0x3E), its
  opening (`BGM_OPENING1` 0x29, the prologue), world map (GMAP1 0x06) and
  ending (`NML_ENDING1` 0x36) are converted as the CO themes are
  (`STORY_SONGS`, written from `0x09000000`) and played by the session's
  scripts; with a version 3 pack AW2's like songs stand in (allies' scenes
  and crises 413, Black Hole's 411, Von Bolt's 220). The songs sit
  after AW2's 505 in the song table but only the converted DS scripts name
  them (`aw2_song`), so AW2's own scripts never play one. Test: `ds_campaign_story_music`.
- **Credits** (`ds_credits.rs`): after Means to an End's ending scenes the
  map is left as its "Return to Select Mode" leaves it (the cursor loop,
  trapped at `0x0807703C`, calls `Proc_Goto(map, 6)` with the answer
  `0x030030F2` = 0, Yes; the menu's start `0x0803B83C`, trapped, starts the
  session's ending proc instead, which runs the roll and then starts the
  menu). The roll is AW2's staff roll (proc script `0x08581AC8`) from a
  session copy without AW2's epilogue (its "War is over" paper, its last
  mission's recap) and without its "Campaign Clear" and campaign rank,
  reading Dual Strike's pages: Dual Strike's 28 sections (overlay 5,
  `0x0236A418`: words 0 blank, 1 name, 2/3 heading, then the time) as AW2
  pages (six (kind, text) slots and the time; AW2's list `0x0858265C`, its
  four pool words switched during a session), headings between stars and in
  two lines when wide, a section with more lines than a page over two. The
  music is Dual Strike's `STRM_STAFF_ROLL1`, a stream (IMA-ADPCM, stereo,
  22767 Hz, 106 s) kept in the pack (version 5) and converted as one
  sample at the mixing rate, mono, played as one held note
  (`ds_music::staff_roll_song`; the roll's `PlaySong(416)` at `0x0806BC84`
  gets it in a session). Dual Strike's top-screen pictures during its roll
  are not shown. Test: `ds_campaign_credits` (every name of Dual Strike's
  roll, read from the .nds, in order; every heading; the music; Select
  Mode after with the session over and AW2's pages back).
- **Hard Campaign**: once a Normal campaign has been cleared (Means to
  an End won: the record's clears byte, kept by New), DS CAMPAIGN's New asks
  Normal or Hard in the chooser's style (`campaign_menu` level 3: two
  labels, A takes the choice and goes on with New, B goes back to the box;
  the box's help lines, text ids 0x9C2/0x9C3, are the choice's while it
  shows); before that New starts Normal directly. Continue resumes the
  saved difficulty. Hard is AW2's own Hard Campaign flag (0x60) in the
  session's flags, set from the record's difficulty byte (the record's
  flags never keep it: a 0.4.0 record kept a lab flag there): AW2's code
  reads it for a mission's hard map and deployment (the converted header's
  +0x30/+0x38, Dual Strike's +0x48/+0x50) and for the results' Normal/Hard
  record. Dual Strike's normal-only (0x15) and hard-only (0x16) trigger
  records are both converted, each testing the difficulty first (AW2 kinds
  6/5 on a pseudo predicate, `HARD_CAMPAIGN`). AW2 CAMPAIGN's own SELECT for
  Hard is untouched. Tests: `ds_campaign_hard_locked`, `ds_campaign_hard`.
- **Records**: a won mission's result goes to the DS Campaign's own table
  (`0x0203F600`, AW2's layout of `gUnknown_0200C2D0`: per mission a Normal
  and a Hard word of CO, days << 8, score << 20; `InsertBestScoreRecord`
  `0x08017720`, trapped, writes it in a session), which the map panel's
  results word (`0x0807758C`) points at in a session. No rank is drawn on
  the map: Dual Strike's map shows none (its map graphics, `res_gmap` and
  `res_gmap_lang_E`, have no rank letters; its ranks are on the results
  screen). Saved with the progress. Test: `ds_campaign_records`.
- **Save**: the progress (`0x0203FD30`, 0x20 bytes: "AWDC", next step,
  campaign over, difficulty, campaigns cleared, missions won (bits), flags
  0x20..0x9F) and the records (0xE0 bytes) are written at each
  mission start through AW2's own save writer (`sub_0801A7D8`) into Flash
  slot 15 (AW2: 0 profile, 2..4 suspends, 5..7 design maps, 8 the design
  map a suspended Versus game is on), so AW2's
  profile and its checksum are untouched; read back from the newest slot-15
  sector.
- **A mission saved halfway** (Dual Strike's campaign has the map menu's
  Save: "Save over Mission / Day data"): the map menu's Save is AW2's in a
  DS mission too, and saves it in Flash slot 14, not AW2's campaign slot 2,
  so an AW2 mission saved halfway and its mark in the profile
  (`0x0200C429`) stay (`crate::suspend`: `sub_08016D30` trapped past its
  prologue, `0x08016D3A`, and at its writer call, `0x08016D8E`: the slot made
  14 and AW2's mark put back before the profile is serialized). The block's
  tail carries the session (after "DS" at +0xE04: the mission, the op 0x5A
  countdown, the flags 0x20..0x9F with Hard's 0x60, Means to an End's state). DS CAMPAIGN's Continue, with slot 14 in
  AW2's sector directory, sets the session up as for the world map (the
  cursor and the map table's entry on the saved mission) and then resumes
  it with AW2's own `sub_08017688(14)`. Slot 14 leaves the directory (as
  AW2's delete, `sub_0801ABF8`, without its write: the next save writes
  it) when the mission ends, won or lost, and on a new DS Campaign; turned
  off before any save after a loss, Continue resumes the saved mission, as
  AW2's own does. Until this the item was hidden in a DS mission (the stub
  at `0x0849AB64`, put back to AW2's test now): a suspended mission would
  have come back as an AW2 one, in AW2's slot. Tests:
  `save_ds_campaign_mission_suspend`,
  `save_ds_campaign_new_drops_mission_suspend`.
- **Hook points** (for merging other work): traps `0x08016BA0` (the profile
  serializer's end), `0x0807703C`, `0x0803B83C`, `0x0806BC84` (the credits),
  `0x0803BA4C`,
  `0x0803BA88`, `0x08038484`, `0x0803CBA0`, `0x0803CBD8`, `0x0803BC7C`
  (`GetCampaignSaveFlag`: the DS box's Continue), `0x0803840C`, `0x0803CC5E`
  (the stubs' landing); `SetMapPlayed` (`0x0803CA28`, Survival's trap) also
  skips map id 0xF0 in a session; `crate::suspend`'s `0x08016D3A`,
  `0x08016D8E`, `0x08016D88`, `0x08016DD0` (a mission saved halfway; its
  hooks in `ds_campaign.rs`: `start`'s Continue, `end_of_battle`,
  `new_progress`). RAM `0x0203FD10..0x0203FD5F` (`0x0203FFAD`: a DS
  mission being saved, `crate::suspend`); ROM `0x08F00000..0x08FFFFFF`;
  text ids 0x7400..0x7FFF; map id 0xF0; Flash slots 15 and 14.

**Compromises.**

- The five two-front missions are played on both fronts ("Two fronts"
  below), with that section's compromises; their single-front
  compromises of 0.4.x (Means to an End's crystals on its main map, its
  36-day limit and the texts changed to say so, the second fronts'
  records dropped) are gone: every limit, record and text is Dual
  Strike's own (`day_limits_are_dual_strikes`,
  `two_fronts_are_dual_strikes`).
- AW2 armies have one CO: a tag pair is its first CO, the "CO pair" tests
  check that CO only, and there are no tag or Dual Strike powers. CO skills
  are tangoAW2's (below); the computer's Hard skill lists of Dual Strike's
  records (+0x60) are empty in the missions read and are not used.
- The world map is Dual Strike's bottom screen only (no top-screen
  displays); a won mission is not played again (its flag stays, starred).
- The player's CO is picked on AW2's CO screen from Dual Strike's pool for
  the mission.
- Results are AW2's results screen (AW2's scoring and ranks).
- Dual Strike's sound effects, screen effects and top-screen displays in
  scripts (ops 0x20, 0x21, 0x2D, 0x2E, 0x46, 0x4B, 0x59) are left out, as
  are its waits on a scene's proc script (ops 0x55, 0x57: `0x0201D298` /
  `0x0201D158` with the script as operand) and its presentation-only
  functions: camera pans (`0x02351334`, `0x02351538`), sounds, flashes and
  fades (`0x023517D4`, `0x023517E4`, `0x02351D50`..`0x02351E20`,
  `0x02003F8C`), the second front's eruption scene (`0x02351A4C`,
  `0x02351AF0`), the scene-skip handler (`0x0201993C`, `0x02019950`).
  `the_campaign_converts` (an ignored test) lists any function not
  handled; `ds_campaign_rules::KNOWN` names those handled or left out.
- **Rule functions with an effect** (`ds_campaign_rules::call`):
  - Victory or Death!'s Black Arc (`0x02350D44`, Dual Strike's
    `0x020EEE1C(13, 5, 100, 0)`, on each of Black Hole's turns while its
    trigger holds): every unit within 2 spaces of (13, 5), but Black
    Hole's team's, Ooziums and loaded units, is left with 1 HP (no
    explosion drawn; Missile Guard takes 10 off, as Dual Strike's 0x2A).
    The trigger is a main-front record (Black Hole's turn, the battle's
    flag 2 clear) and (13, 5) is the main map's centre base ("The Black
    Arc's bombs will keep the allies from making use of the center
    factory"): the bomb falls on the main front, from the Black Arc on
    the second front, until the second front's winning record sets flag 2
    (the fronts share the battle's flags, "Two fronts").
  - Ring of Fire's Volcano: Dual Strike's structure kind 2 (4x4, anchor
    0x1A2 on its third row, at (8, 8)) becomes AW2's own Volcano (anchor
    0x1A7, rim 0x1A5; invention kind 2). It erupts as AW2's does (the
    turn-start loop, once a day from day 3, `sub_0803E764(cells, 50)`),
    but on Dual Strike's cells: the trap `ds_campaign_rules::eruption` at
    `0x0803EE3C` hands it Dual Strike's list for the main map (ARM9
    `0x02167E98`, lists by the volcano's owner; list 1, twelve cells round
    the map's edge), copied to `0x0203F708` in AW2's format. Taking Black
    Hole's four cities round it (`0x02351804`, cities, not Com Towers)
    runs `0x02351988`, which clears the volcano's owner in Dual Strike
    (`0x020DA938`): here `0x0203F704` is set and `crate::obelisk`'s
    turn-start trap skips the Volcano. The second front's win
    (`0x023518CC`, its match-end record on the second front) does the
    same. The second front's own Volcano erupts on its own cells (Dual
    Strike's list 2, `ds_campaign_rules::eruption` by the front on the
    screen) and is never stilled.
  - Means to an End's choice: `0x02351D3C` / `0x02351D28` set / clear
    campaign flag 0x3C (Dual Strike's `0x021017F4(0x3C, 1 / 0)`).
  - Muck Amok!'s (14, 1) (`0x02351640`) is army 3's HQ; its capture
    routing army 3 (`0x023516A4`) is AW2's own HQ capture.
  - Spiral Garden's "Whoever captures 15 properties wins" is not a script
    but the record's +0x34 (Normal) / +0x36 (Hard), tested by Dual
    Strike's engine. `ds_campaign_data::property_win` adds trigger records
    to the after-action list (3), one per army: the pseudo predicate
    `PROPERTY_COUNT | army << 8 | n` (the army owns n properties or more:
    HQs, cities, bases, airports, ports, Com Towers and labs alike) fires a
    script ending the match with that army's win (op 0x40). As Dual
    Strike's code has it: the battle's setup copies +0x34/+0x36 to its state
    (+0x81, `0x020E9400`); `0x020C4498` counts each player's properties
    from the map (classes 6, 8, 10, 11, 14, 20, 22 by the table at
    `0x022F45B8`) and `0x020CEDF4` returns the first player 1..4 with that
    many or more, whose team then wins (`0x02019A6C`): the computer's
    armies too.
  - Crystal Calamity's Black Onyx: "Crystal Calamity: the Black Onyx"
    below (`0x0235172C`, `0x02351738`, `0x02351708`, `0x023516C8`,
    `0x020F216C`, `0x020F2134`; ops 0x5A / 0x5B).

**Crystal Calamity: the Black Onyx** (`onyx.rs`, with the pack).

*Dual Strike* (its code, checked in melonDS: frames in the scratchpad's
`onyxtimer/ds_evidence`). The Black Onyx is a satellite on the top screen
("more than 22,000 miles above us"), never on the map. Its state is a
block at `[0x021694C0]` (`0x020F3604(9, 36000)` at the battle's setup):
+0x14 the hits it still takes (9), +0x1C its state (1 charging, 2 the
warning, 3 firing, 4 hit, 5 destroyed; `0x020F21A0`), +0x38 the full
charge (36000), +0x3C the charge.
- The mission's day-1 script ends with op 0x5A, 180000 frames: a
  countdown, drawn on the top screen as MM:SS (frames / 60: 49:59 at
  179940). The objective says it: "Shatter the black obelisk to win. The
  satellite will fire in 50 minutes, so you should take it out first."
  (Kindle: "In a mere...fifty minutes from now, its barrier field will be
  operational.")
- The charge rises by one a frame (`0x020F232C`, from the battle's frame
  `0x020C05D8`, with the countdown's own count) while the countdown runs,
  the satellite has hits left and the map runs its frame: on every army's
  turn and with a menu open; not while a script runs (dialogue), on the CO
  screen or the mini map (measured: 600 frames idle add 600; a menu open
  310 in 310; START's mini map 1 in 310; the dialogue 0). 36000 frames
  are ten minutes: the laser fires every ten minutes, five times in the 50.
- The header's seventh list (+0x18), tested every frame: at 90%
  (`0x0235172C`, `0x020F22C8`) the warning (`0x020F216C`: state 2, pink
  sparks under it; the first time "Yo! Check out Black Onyx!"); full
  (`0x02351738`) the laser (`0x020F2134`: state 3, the charge emptied; its
  task draws the beam on the top screen (`0x020F2014`), then on the map at
  the spot `0x020985D0(4, 0, 2)` scores best for Black Hole (army 4) a
  beam (`bmap/089`..`08d`) and 8 HP off every unit within 2 squares, never
  below 1, not Oozium (`0x020C6AE0(x, y, 80, 2)`: Sturm's meteor numbers),
  then 300 frames' wait; the first time on Normal "What happened?!",
  "It requires roughly ten minutes to power up, zero in on our position,
  and fire."); the countdown at 0 (`0x023516C8`) Black Hole wins: the
  mission is lost ("Dude. WEAK!" and Rachel's advice, DEFEAT, the campaign
  map; captured from 00:10 left to run in melonDS, scratchpad `onyx2/dst/cc`).
- The laser on the map (`0x020F1F38` → `0x020EB9DC(x, y, 2, 80)`, proc
  script `0x02169088`), after the top screen's beam (state 3, ~104 frames):
  the camera to the target (`0x020EB940`); the beam, a BG layer (`bmap/089`
  tiles, `08a` map, `08b` colours; additive, EVA 16 EVB 16), set up
  (`0x020EB738`) above its place and coming down 16 pixels a frame
  (`0x020EB6B0`: still `16y + 16 - 16(k + 1)` short); two frames after it
  is down the damage (`0x020EB668`: 8 HP within 2, `0x020C6AE0`), a white
  flash (`0x020041E4(4, 0, 20)`), the shake (`0x02003FA0(2, 90)`), the
  rings (`0x020EB5DC`: anim `0x0213BDA0` sequence 0, ten frames, 29 long,
  drawn by the 3D engine from `bmap/08c` as a linear 4bpp texture, colours
  `08d`) and the beam's fade (`0x020EB4E8`/`0x020EB434`: EVA 16 to 0 over 80
  frames, then the layer off). Frames: scratchpad `onyx2/work/fr`, `fc`
  (the target forced to the screen's middle).
- The computer's Launch (its action 0x16, `0x020B8FA8`) in the campaign
  (mode byte +0x58 0) on map 0xF2 fires nothing: `0x020DD9A0` runs the
  header's fifth list (+0x10) with 0x32 (`0x022AF308`), then the unit
  waits (`0x020DEAC4`). Crystal Calamity's list holds one record (kind 4,
  0x32, flag 0x0E): Black Hole says "We've captured one of the
  anti-satellite missile bases. The allied forces are no longer a threat.
  They cannot fire on Black Onyx.", "Aha ha ha! Bravo! Now the barrier
  field will be completed!", and its script jumps (op 0x1D) to op 0x41:
  Black Hole wins, the mission is lost. Only the player's menu Launch
  (`0x020BD358`, the same test) goes to the satellite. Nothing in the
  CPU's planning leaves the silos out (no other test of map 0xF2 there);
  any other map, or another mode, launches as usual (`0x020B8964`, the
  missile `0x020DD9B4`). Checked in melonDS by forcing the CPU's action to
  0x16 (`ds_script`'s `trappoke`): the two lines, "Dude. WEAK!", DEFEAT.
- A missile silo's Launch on map 0xF2 (`0x020BD358`) goes to the
  satellite instead of the map (`0x020DDA8C`, task `0x021693BC`): the
  camera to the silo, the missile rises on the top screen (state 4, the
  charge emptied), 80 frames later the hit lands (`0x020F20EC`: one hit
  less), the silo is spent. At 0 hits (state 5) it breaks apart and falls;
  the after-action list's `0x02351708` then plays "It can't be. I would
  never have believed Black Onyx could be destroyed." and op 0x5B stops
  the countdown. That does not win: the Black Obelisk does
  (`0x023505C0`).
- The top screen shows the satellite over the Earth, the time left, the
  warning's sparks, the beam, the missile and its explosion; no hit count.

*Here.* State in RAM `0x0203FFC8..0x0203FFE3` (`onyx::STATE`: on, hits,
phase, its frames, the charge, the countdown's state, Black Hole's army,
the launch's wait, the list's return address, the silo, the beam), set up
at Crystal Calamity's map start; the countdown is `ds_campaign::COUNTDOWN`
(op 0x5A / 0x5B set it, `onyx::set_countdown`). Both count a frame while
the battle map runs its own frame (main callback `0x08022049`), no event
script runs and the Setup phase is over: the CO screen and dialogues stop
them, a menu does not. The seventh list is converted with the others
(`MissionInfo::realtime`; Dual Strike's op 0x50, a flag cleared, is AW2's
op 0x45) and run by AW2's list runner (`sub_08074484`) from the battle's
frame (`0x08022048`, trapped; back through a stub to the callback) while
the map waits for orders (map state 0xD the player's cursor, 0xE the
computer between units, nothing busy): its scripts start as AW2 events,
its flags are AW2's local flags. The laser (`0x020F2134`, a magic call) is
AW2's meteor strike (`0x084A0858`, 8 HP, radius 2) started from the event,
its target the computer's for Black Hole (`sub_0805C290(army, 1)`), after
the panel's beam (a `PROC_WHILE` on the firing phase), the meteor's fade
from white left out. Its drawing and wait are crate::power_anim's (kind 3,
`ds_power_art::PowerEffect::BlackOnyx`), Dual Strike's laser converted from
the pack at run time: the beam on BG0 (its 42 tiles in the wave's space,
palette 8) coming down 16 pixels a frame and additive; two frames after
it is down the flash (`BLDY`; the beam hidden while it is 12/16 or more,
where Dual Strike's additive beam is white anyway), the shake, the rings
as OBJ sprites (the 3D texture cut into GBA tiles; OBJ `0x1CA..0x1F8`,
palette 3; two of their ten frames need 50 and 51 tiles and leave out a
sparkle each, `Effect::fit_frames`) and the beam's 80-frame fade. The
map's window 0 (the terrain box's, which keeps colour effects to itself)
is off while it plays. Not as Dual Strike: the damage shows when the
effect ends (AW2's meteor script), the sound is the meteor's. The panel
steps aside while AW2's match end runs (its DEFEAT banner).
The computer's Launch on Crystal Calamity's map (AW2's CPU action 20,
`0x080600D0`, trapped: `onyx::cpu_launch`) runs the converted fifth list
(`MissionInfo::unit_event_list`) with 0x32 through AW2's list runner, then
the unit waits (`sub_080424FC`) and the CPU goes on (`0x080600D6`): the
same two lines and the defeat. Every other map, mode and army launches as
AW2 does (`tests/test_silo_launch.py`: Versus, AW2's campaign, Healing
Touch; the player's and the computer's, the same results as v0.5.0's). A silo's Launch here
(`unit_actions::launch_selected` → `onyx::launch`) starts our proc
instead of the targeting: the map busy, the camera to the silo, AW2's
launch there (`sub_08040380`: the silo spent, tile 0x1A0), the missile's
hit on the satellite (80 frames, then one hit less; at 0 the destruction),
then the unit's action ends as at a silo's target (`sub_0804096C`: its
Wait and the after-action list, where the destruction's dialogue comes
from). The top screen is a panel under AW2's CO window, on its side (the
other side while the cursor is under it): Dual Strike's satellite
(`bmap/085`, its colours `bmap/086`, laid out by frame 0 of the animation
at ARM9 `0x0213B8AC`: four 64x64 pieces) made 32x32 at run time, the time
left (MM:SS, AW2's font), a diamond per hit still needed and the charge's
bar (pink and blinking from 90%), and the warning's sparks, the beam, the
missile and its explosion, the break-up drawn on the satellite. OBJ tiles
`0x1F9..0x208` and five columns of four from `0x2D2` (heal_effect's and the
two fronts', neither in use there while it shows; the panel steps aside
while a heal plays), OBJ palette 15's entries 5..15 (1..4 left as they
are). ROM `0x08E75000..0x08E753FF` (the launch and laser functions and
procs, the target function, `firing()`, the CPU Launch's way back, a magic
stub, id `0x2D000001` through the campaign's landing). A mission saved halfway keeps the
satellite (`onyx::saved`, 6 bytes after Means to an End's in the DS block:
hits, phase, countdown state, charge). Without the pack nothing of it
runs. Tests: `tests/test_ds_onyx.py` (the clock and the panel, the warning
and the laser with its damage, beam, flash and rings and dialogues, a
silo's hit, the destruction, the time running out: set to 00:10 once and
left to run, 00:00 after 600 frames, the defeat lines, DEFEAT, the world
map with the mission not cleared and the record unchanged; saved halfway,
the objective), `tests/test_silo_launch.py` (`ds_onyx_cpu_silo`).
Reclaim the Skies has a seventh list too: its day-1 script (after the
opening dialogue) starts a 30-minute countdown (op 0x5A, 108000 frames),
shown on the top screen as MM:SS over a missile's flight; the list's one
record tests `0x02350900` (the same code as `0x023516C8`: the countdown at
0) and its script (op 0x41) gives Black Hole the win ("Noooo! The
missile...", DEFEAT). Checked in melonDS (scratchpad `rel051/rts`): the
count is `[0x02189394]` frames run (its MM:SS copy `0x02175BBC`, set each
second), it runs with a menu open and stops on the START screen.
*Here* the same clock (`onyx::STATE` +0 is 2: the countdown without the
satellite; `ds_campaign_data::RECLAIM_THE_SKIES`), the list run as Crystal
Calamity's, the panel the time alone (its text tiles, by the screen's
edge); saved halfway with the clock's state (mark `T`; a save made before
it continues with the clock running while time is left). Tests:
`tests/test_ds_reclaim_timer.py` (the clock; the time out from 00:10 left
to run, and the whole 30 minutes from the mission's start with nothing
poked, 107935 frames in about 110 s headless: 00:00 on time, "Oh... I
didn't expect this.", "Noooo! The missile...", DEFEAT, the world map with
the mission not cleared; saved halfway).

Tests: `tools/aw2test/tests/test_ds_campaign.py` (the sub-menu with and
without the pack, AW2's campaign unchanged to its first mission card,
Survival and the DS Campaign in one boot, Jake's Trial against the .nds
(card laid out as AW2's, dialogue all Dual Strike's own words, map,
deployment, name), every mission in battle (tiles, terrain, deployment,
fog, weather, look, structure picture), five later missions, the world
map (Jake's Trial picked with the cursor and won through the pad, the map
after the win, saved to Flash and continued after a reboot), the Com Tower
capture, the lab flags and the score slot fixes, the Grand Bolt's spawns, the computer playing
three days on four missions with no army dropping out);
`aw2test/dscampaign.py` drives it and reads Dual Strike's missions directly.

AW2's own campaign stays AW2's (`tools/aw2test/tests/test_aw2_campaign_vanilla.py`):
its opening (New, the story, the world map, Mission 1's card, the first
battle) and its ending (`specialProperty` 0x10 put on its first mission so
its win starts AW2's ending proc `0x084A0A3C`; the scenes and staff roll
until Select Mode is back) are traced every 20 frames (the text shown, the
song, the screen, the game's frame count) without the pack, with it, and
after a DS Campaign session in the same boot, and must match exactly. The
runs press New at the same frame from the boot and write nothing to RAM.
A session's reference is a pack-off AW2 campaign session left with Yes at
the same frame: for the opening one entered with Continue (AW2's world map
from the menu, as the DS session enters it; AW2's proc pool is then left
the same way, and the next campaign starts its procs in the same slots,
which the world map's opening zoom and stamp depend on), for the ending
one entered with New (no AW2 campaign loaded, as in a DS session, so the
results' running total starts the same). Every sample matches (500 for
the opening, 683 for the ending).

**AW2's profile during a session.** AW2's save writer (`sub_0801A7D8`)
serializes the profile (`0x08016B2C`: 0x02028030, 0x0200C078, 0x0200C2D0,
0x0200C420 and the world map state 0x0202FDFC, 0x5CC bytes) into a new
slot-0 sector with every slot it writes, since the profile's header lists
the other slots' sectors. The DS Campaign's own record (slot 15) is written
so too, while the world map state holds the DS map's: before this fix
that took AW2's campaign away (no Continue, and New no longer warned).
The serializer is trapped at its end (`0x08016BA0`): while AW2's world map
state is in the session's backup (`ds_worldmap::backup_aw2_state`), the
buffer gets it from there, so the profile in Flash stays AW2's
(`aw2_campaign_kept_by_ds_session`: the profile byte for byte, Continue
and New's notice in the same boot and after a reboot, with and without
the pack).

## BH Campaign (`bh_campaign.rs`, `custom_campaign.rs`)

The BH Campaign is thirty missions played as Black Hole, defined **as data**
and played by the DS Campaign's engine (`ds_campaign.rs`): it needs the Dual
Strike pack (its COs, units and looks come from it). Act I (M1 Storm Landing,
M2 The Sleeping Foundry, M3 Blockade Runner, `bh_act1.rs`, "Act I" below) is
built and the prologue is the design's; the rest are added as `MissionDef`s
in their acts' files, no engine code needed. A sequel
("BH2") or any other campaign is another `CampaignDef` and another entry of
`campaign_model::SOURCES`.

**The dialogue** is not in the Rust: every scene is a keyed block of rows in `tango-gamesupport-aw2/src/bh_text/*.txt`
(one row is one dialogue box, up to two lines of 176 pixels in AW2's font; format in `bh_text/README.txt`, parsed by
`bh_text.rs`). `@IF`, `@OTHER`, `@WITH`, `@PARTNER` and `@BOND` groups, `[CO]` and `[CO2]` rows become the `Line`'s
`only`, `with`, `partner` and `bond` conditions. The compiler merges a run of boxes by one speaker into one text (up to six
boxes) and shares equal texts, so the 3,072 text ids (`0x7400..=0x7FFF`) go far; `bh_campaign::text_ids_stay_inside_the_budget`
and the `bh_text_budget` test fail when the ids or the data region (`0x08F00100..0x08FC0000`) run short. `tools/bhtext/lint.py`
checks every box against the font and the voice rules; `tools/bhtext/BIBLE.md` is the writers' brief. A second front's CO counts
as the player's partner for the scenes (`two_front::second_front_co`). `CoSpec::PickPartner(lead)` (M30): the lead is fixed and the
CO screen asks for the partner only.

**What changed in the engine.** The engine plays a `Model`
(`campaign_model.rs`), and there can now be several: `SOURCES` has the DS
Campaign (0) and the BH Campaign (1), at most four. The chooser's choice is
kept in `ds_campaign::SOURCE` (RAM `0x0203FD57`; `source(core)`), and
everything that was the DS Campaign's alone is per source: the loaded
campaign (`BUILT[source]`), the record's magic ("AWDC" DS, "AWBC" BH), the
Flash slots (below), the world map's art (`WorldArt::OmegaLand` or
`WorldArt::Aw2`), whether it has a Hard Campaign (`has_hard`; the BH
Campaign has none: New starts at once), and its rules (`Source::rules`; a
custom campaign's are `custom_campaign::rules`). The data blob is written
into the same ROM range as the DS Campaign's (`0x08F00000..0x08FBFFFF`; the
word at its start says whose is in: `magic_of(source)`), and rewritten when
the other campaign is chosen, so a campaign has the whole range and the text
ids `0x7400..` to itself; the world map's mission table is rewritten the
same way (`ds_worldmap::TABLE_OWNER`). Code that belongs to Dual Strike's own
missions (Means to an End's Grand Bolt and look, Crystal Calamity's Onyx,
Reclaim the Skies' clock, Omens and Signs' barrier) asks
`ds_campaign::ds_mission(core)` (0xFF in another campaign).

**Menu.** Select Mode > Campaign: AW2 CAMPAIGN, DS CAMPAIGN, BH CAMPAIGN
(`campaign_menu.rs`; the labels are the chooser's 5x10 letters, two shown at
a time, UP/DOWN through all three). It is listed only with the pack (a
source's `available`); without it the chooser does not exist and the box is
AW2's own (`bh_campaign_menu_entry`). Its box is Continue / New as the DS
Campaign's, with no Normal / Hard choice. A on its entry sets
`ds_campaign::SOURCE`.

**World map: AW2's own Wars World.** The campaign uses AW2's campaign map
screen on AW2's own art (nothing replaced: the tile, tilemap and palette
words keep pointing at AW2's), with a mission table of ours: each mission's
flag at the place its data gives, marker style and LEVEL stars, the same
panel (title, objective) and reveal flow as the DS Campaign's. AW2's map
does have Black Hole's land: the small island at the top, where AW2 puts its
own last two missions (map ids `0xAA`, `0xAB`, at about (191, 37) and (166,
21)). The campaign starts there and goes round the world as AW2's own lands
lie: **Black Hole** (the island, top centre, x 150..195, y 20..60), **Green
Earth** (the east land, x 300..390, y 85..230), **Yellow Comet** (the centre
land, x 225..300, y 50..180), **Blue Moon** (the south, x 85..220, y
150..235), **Orange Star** (the west, x 35..150, y 60..195). (The picture is `0x081CC5F0` / `0x081D0BAC` / `0x081D1504`, 432 x 256; AW2's mission
table is `0x08615194`; the camera stops at 192 x 96.) Six flag places
inside each land are listed in `bh_campaign::region` (map pixels; checked
against the picture in `tools/aw2test`'s world map shot). A flag's position
is the mission's `flag`; a won mission keeps a starred flag (AW2 paints its
region on its own mission ids only). Progression: each mission's `requires`
(`Requires::Start`, `All([..])` all of them won, `Any([..])` a branch);
`ds_campaign::available` returns the missions whose requirement holds and
that are not won, and the reveal flow shows the ones a win opens.

**Roster and unlocks.** `CampaignDef::roster` lists (AW2 CO id, open at the
start) in unlock order: Sturm (open), Von Bolt, Hawke, Kindle, Koal,
Jugger, Flak, Lash, Adder, Clone Andy, Sonja (the secret mission's recruit; Free Play only in effect), Crumb (index 11, the last of
the twelve the unlock mask holds under the bonds' bits: promoted at the end of M28). A mission's `recruits` are roster
indexes its win unlocks (`bh_campaign::roster::HAWKE` ...); `Action::Unlock(index)` unlocks one in the middle of a
mission (`bh_campaign::unlock_crumb()`). The record keeps
the unlocked set as a 24-bit mask of roster indexes at progress +0x0D..0x0F
(`ds_campaign::unlocked_mask`). Army colour and CO are independent in the
data (`ArmyDef { colour, co }`: Von Bolt can lead a Green Earth army, Kindle
a Yellow Comet one, as `placeholder_one` / `placeholder_two` do).

**CO screen.** `CoSpec` per army: `Fixed(co)` (no screen), `Pair(a, b)` (a
tag pair for the computer), `Pick` (the player picks one), `PickPair` (the
player picks two, a tag pair), and a second front's own `Pick` (one CO per
front: the main front's pick, then the second front's, with `PickPair` on
the main army as Dual Strike's `(0x1C, 0x1C)`). The CO screen offers the
mission's `pool` (else the roster) **among the unlocked ones**
(`ds_campaign::co_setup`), grouped by country (Black Hole's COs all in its
tab; Clone Andy is placed there). A custom campaign's picks lock no country
(`custom_co_screen`: AW2 locks a country per pick, which Dual Strike's
mixed countries suit but a roster of one country does not).

**Saves.** Flash is 16 sectors; each slot takes one sector for the payloads
here (a mission saved halfway on two fronts takes two). The layout:

| Slot | What | Written by |
| --- | --- | --- |
| 12 | a BH mission saved halfway (the block as slot 14's, with the session tail "DS" and, on two fronts, the other front) | map menu Save in a BH mission |
| 13 | the BH Campaign's record, 0x120 bytes: progress (0x20: "AWBC", next step, over, missions won (bits), flags 0x20..0x9F, unlocked COs at +0x0D) and the records (8 bytes a mission: CO, days << 8, score << 20; the best rank is the score's, AW2's thresholds) | BH New, mission start, after a win |
| 14 | a DS mission saved halfway | as before |
| 15 | the DS record and the CO skills (global to every mode) | as before |

AW2 uses 0 (profile), 2..4 (suspends), 5..7 (design maps), 8 (the design
map a suspended Versus game is on). With every slot in use at once (twelve
slots, `save_every_slot_at_once`) twelve sectors are held and four are free;
a write needs one free sector for the slot's new copy (two for a two-front
mission) and one for the new profile, so two-front missions saved halfway in
both campaigns at once leave exactly the two a write of either needs.
The BH Campaign never writes slots 2..8, 14, 15's progress and records, or
the profile but AW2's counters and the Battle Maps points a win earns;
`stage_slot` (the DS slot, written when the skills change in any mode) stages
the DS record from RAM only when it is the loaded one, else from Flash, so a
BH record in RAM never lands in slot 15. The DS slot's skill data grew
(`co_skills::COS` 30 for Crumb after Clone Andy's 29: 32 bytes more each; a shorter saved record
reads the rest as zeros) and `skills_panel`'s RAM moved to `0x0203E3F0` (Crumb: `grand_bolt`'s too, to `0x0203E3C8`).
Tests: `save_bh_campaign_beside_aw2_and_ds` (record, win, mission saved
halfway and continued, AW2's and the DS Campaign's saved missions and the
DS record byte for byte as they were, the profile as expected),
`save_every_slot_at_once` (twelve slots).

**Prologue and credits.** Same mechanism as the DS Campaign's: the prologue
is a script run from the session's copy of AW2's world map script before the
map takes the pad (once, flag 0x9E of the record); the credits flow starts
when the final mission's win is recorded (`CampaignDef::final_mission`): its
`after` scene on the map, then the map is left, the staff roll runs from a
copy of AW2's roll reading **the campaign's sections**
(`CampaignDef::credits`: heading and names, 120 frames a page; `ds_credits::
build_sections`), then Select Mode. `CampaignDef::prologue` pages are text
(`Page { text, picture, who }`): on AW2's map each is a dialogue box (a
Black Hole soldier unless `who` names a speaker); `picture` (an index of
`ds_story_art::NARRATION`) is Dual Strike's story picture, drawn over
Omega Land's map layer only: AW2's own map layer is not rebuilt after one,
so on AW2's map it is not used (a picture for the prologue needs a layer of
its own: not done).

### The mission data format

A `MissionDef` (build one with `MissionDef::new(key, title)` and set what the
mission has; `custom_campaign.rs` has the types, the comments are the
reference). `compile` turns it into the engine's `MissionInfo`, a map header
(0x5C bytes), a map, a deployment, AW2 event scripts and trigger lists and
texts; an error names the mission.

| Field | What | Status |
| --- | --- | --- |
| `map` | `MapSrc::Aw2 { id }` (one of AW2's maps: terrain and, unless `units` is set, deployment), `Ds { record }` (a Dual Strike campaign map, read from the player's ROM), `Tiles { width, height, tiles }` (AW2 tile ids), `Ascii(rows)` (text terrain: `. f m = r ~ s : c b a p 1..4`; roads, rivers and sea are the first tile of their class and do not join up: placeholder terrain) | tested: Ascii, Aw2 (map 0x8A) and Ds (Jake's Trial); Tiles compile-checked |
| `armies` | 2..=4 `ArmyDef { colour, team, co, funds }` in army order, army 1 the player's; `colour` (1 Orange Star .. 5 Black Hole) and `co` independent | tested |
| `co` | `CoSpec` as above | tested: Fixed, Pick, PickPair, Pair, a second front's Pick |
| `weather`, `fog`, `look` | `Weather::{Clear, Snow, Rain, Sandstorm}`, fog on at the start, Dual Strike's look (0 normal, 1 snow, 2 desert, 3 wasteland) | tested: rain, fog |
| deployment | `units: Vec<UnitDef>` (`UnitDef::new(army, kind, x, y).hp(1..100).hold().named("..")`; every unit starts with full ammo and fuel, `FULL` = 99 capped to its type's maximum by the loader, unless `.ammo(n)` / `.fuel(n)` ask for less: a Tank `.ammo(2).fuel(30)`; the deployment once wrote 0 ammo, which showed the low-ammo icon on every Tank, Md Tank, Artillery ... and kept them from firing); empty keeps an AW2 / Dual Strike map's own; a mission with none for an army starts it with no units (the player builds: pre-deployed or not is what `units` holds) | tested |
| `armies[].funds` | starting funds, set on day 1 (a stub run in Rust) | tested |
| `props`, `structures` | owned properties; Black Hole's structures stamped on the map (`Structure::{MiniCannon*, Laser, BlackCannon*, BlackFactory, Volcano, Deathray, BlackCrystal, BlackObelisk}`, the Design Room's footprints) | tested: factory, crystal, obelisk, laser |
| `front2` | a battle on two fronts: its map, props, structures, deployment, `cos` per army (`Pick` for the player's own), `send`, `sky`, weather, fog (`crate::two_front` plays it) | tested: tag pair on the main front, a pick for the second, round change |
| `day_limit`, `rank_days` | the days the player has (the header's counter; exceeding it loses) and the S rank's days | day limit tested in the header |
| `triggers` | `Trigger::new(when, cond, vec![actions])` (`.repeating()`; by default a trigger fires once: it latches a campaign flag of its own, 96 per campaign): `when` is `TurnStart` (the start of the player's turn: army 1's, army 5's in a five-army mission) or `AfterAction` (after each action). Conditions: `DayAtLeast`, `EveryDays{n, from}`, `UnitAt`, `NamedIn{name, area}`, `UnitAlive`, `UnitGone`, `UnitsIn{army, area, at_least}`, `ArmyUnitsAtMost`, `PropertiesAtLeast`, `OwnerAt{x, y, army}`, `ArmyDefeated(army)`, `PlayerPair{a, b}`, `OnyxHitsAtMost(n)`, `OnyxDestroyed`, `Flag`, `Not`, `All`, `Any`, `Custom(fn)`. Actions: `Scene`, `Win`, `Lose`, `SetFunds`, `AddFunds`, `Spawn(units)`, `SetCo`, `Strike{hp}`, `EarnBond(k)`, `Unlock(roster index)`, `Custom(fn)`. Win and lose also by AW2's own rules (rout, HQ) | tested: day, every days, named unit, funds, add funds, scene, win, lose, pair, spawn, strike, second stage, bond; compiled: the rest |
| special units | `UnitDef::named("courier")` (with `.hp(10)` for 1 HP): a named unit has a **persistent id**: its bit of the mission's death latch (`custom_campaign::LATCH`, the countdown word, kept by a mission saved halfway), set for good when its record empties, so a unit built into its slot is not it. "Must reach the extraction point within 15 days" is `AfterAction` `UnitAt` -> `Win` and `TurnStart` `All[DayAtLeast(16), Not(UnitAt)]` -> `Lose`; an evacuation is `UnitsIn` / `NamedIn` over a rectangle | tested |
| `intro`, `victory`, `after` | scenes: in the battle before day 1's first turn, before the winning end (inside `Action::Win`), and on the world map after the win (before the next mission's flag shows); between-mission scenes are `after` | tested |
| `music` | an AW2 song id: while the battle is on every CO's theme in the CO table is that song (put back after) | tested |
| `factory` | The Black Factory's own schedule: `(day, [door 1, door 2, door 3])` unit types (0 none; days not listed spawn nothing; the spawner reads row `day & 0x1F`); empty: Factory Blues' table. `factory::table_for` writes it to the spawner's table pointer (`0x030046B4`) at the AI turn setup and at a human Black Hole army's turn (the detour) | tested (`bh_act1_m2_foundry_waves_and_flow`) |
| `on_win` | Actions (`EarnBond`, `Custom`) run, then the `victory` scene, in the match-end list when the player's team wins by AW2's own rules (the enemy routed or its HQ taken: AW2 ends the match before an after-action trigger could look, so a trigger on `ArmyDefeated` never shows the scene); not used when the mission has a `Win` action of its own | tested (Act I's wins) |
| `recruits`, `needs`, `flag`, `style`, `stars`, `pool`, `setup` | roster entries unlocked; what opens it **by mission key** (`Needs::Start`, `All(vec!["bh01"])`, `Any(..)`, `Bonds(..)`: those won and every hidden bond earned); its world-map place, marker, LEVEL stars, the CO pool, the Setup phase (scout, then Deploy) when the player picks | tested |
| five armies | `armies` is 2..=5. In a **five-army mission the player is army 5, Black Hole** (the fifth army of `five.rs`; its colour must be Black Hole's), armies 1..4 are the header's four, units name armies 1..5, a map has five HQs (`1`..`5`); the player's CO is `Fixed` or `Pair` (a tag pair; no pick yet). The patched game (`five::set_campaign`, switched on at `ResetRulesAfterCampaignMap`) is on for the battle only; no mid-mission Save (as a Versus five-army game); no second front. `five.rs`' patched unit ids (51 an army) are handled by `custom_campaign`'s helpers (`unit_by_name`, `units_of`) | tested (`bh_campaign_five_armies`) |
| two fronts: own rules | `front2_triggers` / `front2_victory` on a `MissionDef`: the second front is compiled as a mission of its own (`compile_second` builds a synthetic `MissionDef` with the front's map, deployment, structures and these triggers), so its rules run while it is on the screen, on its own units; **a named unit of `front2.units` is the second front's** (`custom_campaign::SECOND_FRONT` flag on its latch bit: it is judged only while its front is live, so the other front's units in the same slots never trip it); `Cond::UnitGone("name")` is the "unit destroyed" condition for both fronts (the death latch keeps it true). The second front is played by the computer, whose actions do not run the after-action lists: use `When::TurnStart` triggers there. `Action::Win` on it wins the second front (its `front2_victory` scene) | tested (`bh_campaign_second_front_has_its_own_rules`) |
| pair pick | with Sonja (a Yellow Comet CO) in the roster the second pick could not reach the Black Hole tab: `tag::co_screen_partners` kept a DS campaign's partner on the leader's country tab; it now runs for the DS Campaign only. Every roster CO is a partner of every other; the one exception of the game's own rule: a Yellow Comet CO (Sonja) picked first does not lead a Black Hole army (the other becomes the lead) | tested (`bh_campaign_pair_pick_matches_every_partner`, 30 pairs by the pad) |
| marches | `MissionDef::marches` (`MarchDef::new(name, path, cells_a_day)` or `MarchDef::speed(name, path, move_points)`, `.from(day)`): a named unit (deployed, or spawned with a name) walks its fixed path on its own army's turn (the computer's dispatch), once a day, stopping at the first occupied cell (or the first cell it cannot afford: AW2's movement chart for its type, as the flood fill charges it) and trying again the next day. It stands on the path; the next day's start is its record's cell. The last day each march moved is a byte of the custom campaign's side table (`custom_campaign::SIDE`, `0x0203F3A0..0x0203F400`, cleared at a battle's first day: the unit record has no byte free for every type, +7/+8 are an APC's cargo) | tested (`bh_campaign_march_named_spawn_and_jammed_cannon`) |
| driven marches | `MarchDef::driven(name, path, 1)`: the computer moves the unit itself with AW2's own role code (role byte +0x0B, which every unit has as 1: advance on the enemy HQ; hold is +9), so it keeps its real speed, pathfinding (other teams' units in the way), the stop in front of a blocker and the normal move animation; only the place the role code goes to (`sub_08058F90`, the enemy HQ; `custom_campaign::goal_hook`, `0x0805ED2A`) is replaced by the path's last cell. The unit must not hold (+9 0). AW2 has no per-unit target-cell field: roles 0/1 (`0x0805ECD9`/`0x0805ECDD`) share the HQ place, 2, 3, 4, 5 and 6 pick targets of their own (`0x08059A0C`, `0x08059C00`, `0x08059C60`, `0x08059E3C`, `0x08059F24`/`0x0805A008`: nearest enemies and properties), 7 stays by the HQ | tested (the Recon of `bh_campaign_march_named_spawn_and_jammed_cannon`) |
| held foot soldiers | AW2's role 0 (the deployment's AI byte 0, record +0x0B) does nothing in the role code, but Infantry and Mechs still walk off to capture neutral cities. `custom_campaign::ai_unit` (called from `unit_actions::behaviour_row`, the CPU's per-unit entry `0x0805D496`) skips such a soldier (AW2's own skip of a unit that has acted, `0x0805D4A6`) unless an enemy stands next to it (then AW2 plays it) or its army has given up; no fuel trick is needed (zeroing the fuel does not stop it). A unit a scripted march moves is skipped too (an APC would load soldiers and leave its route). `UnitDef::stand()` is role 0 for a spawned unit too (the default role is 1: for the enemy HQ) | tested (`bh_campaign_march_named_spawn_and_jammed_cannon`) |
| spawned names | `Action::Spawn` with `UnitDef::named(..)`: the spawned unit's id and type are kept in the side table by its tag (the record is untouched: no phantom cargo in an APC), `Cond::UnitAlive/UnitGone/UnitAt` and marches find it by it (not there before it spawns, gone for good once it was seen and its tag is not found); a spawned unit's HP, ammo, fuel and AI order are set from its `UnitDef` (a spawned `.hold().fuel(0)` stays put) | tested |
| jammed structures | `MissionDef::jams` (`JamDef { at, until }`): the Black Hole structure on the inventions-list cell `at` cannot fire while `until` (any `Cond`: a day, a captured property, `Any` of them) does not hold (its counter is held); once it holds the structure is restored and fires from the next Black Hole turn start | tested |
| five-army pick | `CoSpec::Pick` / `PickPair` for a five-army mission's player (army 5): the CO screen's own pick (made for the header's army 1, whose header CO reads 0xFF) goes to army 5 and its partner (`five::set_army5_co`, `tag::set_cos` rewrites the list: army 1 gets its fixed CO, `Native::five_pick`), and army 1 is the computer's; army 1's spec must be `Fixed` | tested (`bh_campaign_five_army_player_picks_a_pair`; `bh_campaign_five_army_pick_reaches_every_co_and_tags`: Sonja and Clone Andy picked both ways, army 5 has the pair, Tag Power and Change work; a Yellow Comet CO (Sonja) picked first does not lead the Black Hole army: same pair, the partner leads) |
| Factory and Volcano on one map | `LoadInventionGraphics` (`0x0803FD80`) has one slot for a structure's own picture (header +0x10, then the Factory's `0x080D22C4`, then the Volcano's `0x080D3268`, the last present winning, at sprite tile field 0xE8 = OBJ tile 0x130), so a Factory next to a Volcano drew garbage from the Volcano's tiles. The Volcano keeps the slot; the Factory's picture is put in OBJ tiles 786..833 (`obelisk::FACTORY_OBJ_TILE`, 48 tiles, written by the sprite trap whenever they differ) and its three sprites drawn from a copy of AW2's definition (`FACTORY_DEF2`). Those tiles are clear of the Obelisk's (0x176..0x199) and the Crystal's (0x19A..0x1A1), so the Obelisk, Crystals, Factory and Volcano of mission 28 share a map. Free tiles were found by watching which OBJ tiles the battle's load writes and which play (menus, a day, an eruption) touches: 0x2B5..0x2D1 and 0x312..0x351 are untouched, 0x352.. are the cursor's and panel's. Not 800..: a Factory at exactly tile 800 stopped the Volcano's eruption damage with an Obelisk and a Crystal on the map (cause not found; 808, 812, 816 and 848 did not). **Palette**: the Volcano's colours went to sprite palette 12, the fourth army's buildings' (M28's Yellow Comet drew its cities in the lava's colours); a custom campaign's Volcano now goes to palette 2 like Versus's (`volcano.rs`; Dual Strike's colours with the pack). The Factory is Black Hole's own bank. | tested (`bh_campaign_factory_and_volcano_on_one_map`: a Factory, Volcano, Obelisk, Crystal and four armies; the Factory produces, the Volcano erupts; `bh_campaign_fortress_draws_factory_volcano_obelisk_and_crystals`: M28's map) |
| `volcano` | **A volcano as a neutral hazard**: `volcano: Some(VolcanoDef::new(first, interval, damage_hp, &[(x, y), ..]))` with a `Structure::Volcano` on the map (AW2's own Volcano: its turn-start show runs, AW2's eruption call at `0x0803EE3C` is hooked, `hazard.rs`): from day `first`, every `interval` days, on Black Hole's turn, the unit of **any army** on one of the (at most 12) cells loses `damage_hp` HP (AW2's queued impact: a unit is left on 1 internal HP, never destroyed); the cells are marked with orange-yellow diamonds all the day before (sprites, OBJ tiles 772.., palette bank 4). The DS Campaign's Volcano (Ring of Fire) and AW2's own are unchanged (this applies to a custom campaign only). The Volcano's show also moves the cursor: it ends where it last looked, so tests reset `CURSOR_X/Y` | tested (`bh_campaign_volcano_hazard`: the day before nothing, the eruption on the cells for own and enemy units, a 2 HP unit left on 1, a unit beside untouched, nothing on the day between) |
| human Black Hole structures | A Laser and minicannons owned by a human Black Hole army fire on its turn start as the computer's do (the game's own turn-start loop): the Laser every enemy in its row and column, a minicannon its line (about three squares) | tested (`bh_campaign_human_black_hole_laser_and_minicannon_fire`, enemy Tanks with `.fuel(0)` that cannot walk out of the lines) |
| the player's Black Factory | the smart spawner of the Versus pack (`bh_factory.rs`, `bh_smart.rs`) picks what the battle needs for the player's Black Hole factory, the table's schedule and cost caps kept (`in_scope`: Versus with the pack, and a custom campaign's missions; not the DS Campaign nor AW2's own) | tested (`bh_campaign_factory_counters_the_enemy`: against six Bombers it builds Missiles, against six Md Tanks an Oozium) |
| factory spawner | `factory::spawner_guard`: the spawner does nothing on a campaign or design map with no Black Factory in the invention list (the game's own lookup runs on past a list without an end entry) | tested: a computer Black Hole army with no factory plays 13 days on one front, 12 rounds on two fronts |
| `onyx` | **The reversed Black Onyx**: `onyx: Some(OnyxDef::new((x, y)))` (the Obelisk's top-left cell; `hits` 4, `first` 5, `period` 5, `radius` 4, `debris_hp` 3, `offline_turns` 3, `meters` 30 are the design's numbers). Black Hole's satellite on a day cycle, `onyx.rs` (`ON_REV`, RAM `0x0203FFC8`: hits left +1, phase +2, last shot's day +0x17, the Obelisk's offline turns +0x18, this turn's flag +0x19): on Black Hole's turn on day `first` and every `period` days, when the map waits for the cursor, it fires AW2's meteor strike (8 HP, radius 2, never below 1 HP, the spot the computer scores best for the player's army; the panel's beam as Crystal Calamity's); a foot soldier (Infantry or Mech) of **another team** on an unspent silo (tile `0x180`) launches at it (AW2's launch at the silo: camera, missile, the silo spent, the missile on the panel) - found each frame the map waits, on the computer's turn between two of its units too, so the computer's own walk onto a silo counts and a silo holding a Black Hole unit cannot launch; its own Launch action fires nothing; `hits` hits destroy it: every unit of the player's army within `radius` cells of the Obelisk's 3x3 loses `debris_hp` HP (never below 1 HP), the Obelisk and its heal effect are off for `offline_turns` Black Hole turns (`obelisk::heal`, `heal_turn`), the player's active CO and its tag partner lose `meters` % of their Super Power's cost (`tag::cut_meters`), the shots stop for good. Panel: the satellite (Dual Strike's picture), "NEXT SHOT" and the days to it ("4 DAYS", "1 DAY", "TODAY"), "HITS LEFT" with a diamond a hit still needed, the cycle's bar; from the day before a shot the satellite throws pink sparks and the line, diamonds and bar blink pink; the panel's tiny 3x5 letters are `onyx::glyph`; it hides once the satellite has fallen. A mission saved halfway keeps it (`saved` / `restore`, mark `R`). Scenes by the hits left: triggers `Cond::OnyxHitsAtMost(3)` ... `OnyxDestroyed` at `AfterAction` (once each). `five/bh/five_onyx.txt` is a test map: silos are `M` in the map tool | tested (`bh_campaign_reversed_onyx`: the warning, the day-5 shot, four silo hits, the scenes, the fall) |

Scenes: `Scene::new(vec![Line::say(co::STURM, "..."), Line::feel(co::VON_BOLT,
Mood::Sad, "..."), Line::soldier(colour::BLACK_HOLE, "..."), Line::narrate("...")])`;
`narrate` is a box with Black Hole's soldier face (AW2's speaker-less `0x1A` text is drawn
bare on the map in a battle: unreadable). A soldier with a mood is
`Line::feel(23, Mood::Happy, ..)` (faces are `co + 24 * mood`; 23 is Black Hole's
trooper). Text is plain; **a text written with its own `\r` line breaks keeps them**
when it is at most two lines that each fit AW2's box (176 pixels), else it is wrapped
(two lines of 176 pixels; a box that needs more spreads evenly); `\x0f` forces a new box. A scene compiles to AW2's
dialogue commands (`0x17` open with the first face, `0x38` a speaker,
`0x19` a text, `0x18` close).

### Act I (`bh_act1.rs`, `five/bh/bh01.txt` .. `bh03.txt`)

The design is docs/BH_CAMPAIGN.md (3.5, 4.1, 4.2, 4.11); the scenes are its text line for line, with its
own line breaks (`Compiler::dialogue` keeps a text's `\r` when each box is at most two lines that fit),
and the tests read the scenes out of `bh_act1.rs` and compare them with what the game shows
(`bh_act1_dialogue_is_the_designs_and_fits_its_boxes`). The flags sit on the Black Hole island (`region::
BLACK_HOLE[0]`, `[4]`, `[5]`: the north-west tip, the south, the south-east bulge). The prologue is the
design's eight pages (soldier boxes on AW2's map; no pictures or music there). A mission's win scene is
its `on_win` / `victory`; the days run out as `Cond::DayAtLeast(limit + 1)` -> `Lose` (AW2 only ranks
by days).

| | M1 Storm Landing | M2 The Sleeping Foundry | M3 Blockade Runner |
| --- | --- | --- | --- |
| Map | 22x15: a crater lake with two bridges over the river that cuts the map (every vehicle crosses at (7,7) or (14,7); foot wades), a south-west beach, Von Bolt's walled hall (west gate (16,3), south gate (19,5)), an Obelisk at (5,9), Crystals beside the bridge ends at (6,6) and (15,8) | 18x20: the Foundry (8..10, 3..6, doors on row 7) fed by a pipe from the HQ (9,1), a ring road round it, a Crystal at (6,7), a river with the road bridge (9,12) and a west-track bridge (3,12), a village, a ridge, Green Earth's south coast | 26x16: three islands, two straits, two-wide channels; Black Cannon at (12,6) on the middle isle with its ring road; ten beaches (shoals), four ports |
| Armies | Sturm (6000): HQ, 2 bases, 4 cities; Von Bolt in Green Earth's colours (10000): HQ, 3 bases, 3 cities, 5 neutral cities | Sturm or Von Bolt (pick; no bases, no funds), against Jess (8000) | Sturm + Von Bolt (a fixed tag pair, 12000) against Drake + Eagle (14000) |
| Rules | day 3 scene when a Black Hole unit is within 2 of a Crystal; day 4 two Md Tanks if Von Bolt owns 6+ properties; day 7 scene; the win earns Von Bolt's bond (`on_win`) and unlocks him; 20 days | the Foundry's own table (`factory`, from day 3), Green Earth's waves on days 3, 6 and 9 (day 9 with Jess's power charged), +3000 for Jess on days 4, 8, 12; the last line of the opening is Sturm's or the leader's; 14 days | day 4 and day 8 scenes (the latter once two of the isle's three cities are held); 25 days |

Tests (`test_bh_act1.py`, `-k bh_act1`): every mission loads as its sheet says; each mission's
opening, forced win with its scenes, unlocks, bond and next flag; M1's turn-start rules; M2's Foundry
(none before day 3, a Tank on the middle door on day 3, the wave); M3's pair and scenes; every mission
lost three ways (days, routed, HQ taken); the maps' reachability (the map tool plus foot, tires and treads
across the bridges, ships and Landers across M3's lanes); `bh_act1_m3_lander_unloads_on_every_beach`
(each army's Lander loads and unloads on all seven beaches it can use); a campaign chain saved halfway
and continued in each mission; pictures (`AW2TEST_PICS=<dir>`). `AW2TEST_BH_ACT1_BALANCE=1` adds
`bh_act1_balance_m{1,2,3}_{cpu,bot}` (the computer on both sides, and the test player of
`aw2test/bot.py` against it; `AW2TEST_BH_ACT1_BOT='{"stance":"defend"}'` changes the bot's options).

### Adding a mission (for whoever builds the thirty)

**Where.** One file per act: `bh_act1.rs` .. `bh_act5.rs` and `bh_secret.rs`
(the 31st), each a `pub fn missions() -> Vec<MissionDef>` in world-map order;
builders of different acts never touch the same file. `bh_campaign.rs` has
what is shared: the roster (`ROSTER`, `roster::*`), the world map's regions,
the prologue, the credits, the hidden bonds (`BONDS`) and `def()`, which
concatenates the acts. A mission names what it needs **by key**
(`Needs::All(vec!["bh12"])`), so no mission depends on another act's index;
`final_mission` is a key too.

1. In your act's file write `fn bh13() -> MissionDef` with
   `MissionDef::new("bh13", "Title")`; give it a map: build it with the map
   tool (`MapSrc::Built("bh13")`, below), or `MapSrc::Aw2 { id }`, `Ds { record }`,
   `Tiles`, or `Ascii` for a placeholder; then `armies`, `units` (or the built
   map's own), what its rules need, scenes.
2. Pick its flag from `region::*` (or any point of the 432 x 256 picture),
   its `needs`, its `stars`, `recruits` if it unlocks a CO (a recruit
   mission also earns its hidden bond: `Action::EarnBond(k)` in a trigger).
3. Add it to the act's `missions()`.
4. `cargo test --release -p tango-gamesupport-aw2 --lib` (`bh_campaign::tests`
   compile the campaign), then `python3 tools/aw2test/run.py -k bh_campaign`;
   `TANGOAW2_BH_FEATURES=1` plays `features_def()` (every field once) instead.
5. In a test: `bhcampaign.BhCampaign(g)`: `start_bh`, `start_at(won_mask,
   unlocked_mask)`, `pick_mission`, `wait_map`, `cp.win_here`; its `picks`
   dict says how many picks the CO screen asks per mission.

**The map tool** (`tango-gamesupport-aw2/five/bhmap.py`). Maps are text files
in `five/bh/*.txt`, in `five/maps.txt`'s format (legend: `five/map.py`: sea,
reefs, shoals, rivers, bridges, roads, pipes, woods, mountains, properties,
Black Hole's inventions) with `team`, `objective`, `owners`, `split` and `unit ARMY TYPE X Y
[hp=N] [hold] [name=id]` lines (`owners 1 2`: only those HQs decide who owns a property, the nearest; `split y 14`: the first HQ's army owns the properties up to row 14, the second's the rest; `Q` is a second HQ tile; a shoal strip wider than one cell and a sea moat are drawn, a river wider than one cell is not: AW2's maps have no such tile pairs). `python3 five/bhmap.py <aw2.gba>` joins every
road, river, pipe, sea edge, coast, shoal and mountain as AW2 draws them
(the rules learned from the game's own maps, `five/map.py`), checks every
neighbouring tile pair against the game's maps (`five/tilecheck.py`) and
writes `src/bh_map_data.rs` (the tiles and units; commit it); `--check` only
checks. It also checks reachability: the player's army (`objective` names
more) reaches every enemy HQ by land, or has a Lander or aircraft that can;
every Lander has a port or beach to load at next to its army's land and a
beach to unload on next to useful land (an HQ, a property, units) its army
cannot walk to; no stranded island (land with properties or units that
nobody reaches); no unit boxed in. A problem prints `PROBLEM ...` and the
exit status is 1 (`bh_map_tool_checks` runs it on good and bad maps).

**Recipes.**
- *Stage two (Nell, then Andy): the same army goes on.* The army has two HQ tiles on the map (`Q`: a second
  HQ of the army whose HQ is nearest, the Rail Yard), `MissionDef::held_hq = Some((x, y))` names the first one (the
  Great Hall): its capture defeats nobody (a trap at the HQ-mark instruction `0x08042822` skips the mark; whoever
  captures it, it only changes hands). A trigger `AfterAction` on `OwnerAt { x, y, army: 1 }` then plays the scene and
  does `Action::TakeOver { army: 2, co: ANDY, meter_pct: 30 }` (the same army, a new CO with its own meter at 30% of
  its first power's bar, no power in effect, its skills: `tag::replace_co`, deterministic, with or without a tag pair),
  `Spawn` (the reserves, as many as the 50-unit cap allows) and `AddFunds`. Capturing the other HQ defeats the army and
  wins. A mission's own variables live in EWRAM `0x0203FD7C..0x0203FD7F` (M30: the fall's day, "duel played").
- *Evacuation / escort.* Named units (`.named("crumb")`) and `UnitsIn` /
  `NamedIn` over the exit's rectangle, or `Cond::Custom(fn)` using
  `unit_by_name`, `units_of`, `day`; a death is `UnitGone`.
- *A CO pair in the player's pair triggers a scene.* `Cond::PlayerPair {
  a, b }` (either order) at `AfterAction` with a `Scene`.
- *A strike alone.* `Trigger::new(TurnStart, EveryDays { n: 5, from: 5 },
  vec![Action::Strike { hp: 8 }]).repeating()`: AW2's meteor strike (every
  unit within two cells, never below 1 HP) on the spot the CPU's scorer
  picks best for the player; no satellite is drawn. The satellite itself is
  `MissionDef::onyx` (table above).
- *Lose when a named city is captured.* The map marks the city as army 1's
  (Ascii `A`..`D`, or a built map's `C` near the player's HQ), then `Trigger::new(
  AfterAction, Cond::Not(Box::new(Cond::OwnerAt { x, y, army: 1 })),
  vec![Scene.., Action::Lose])` (`bh_campaign_lose_when_the_gate_city_is_captured`;
  in a five-army mission the player's army is 5).
- *Reinforcements.* `Action::Spawn(vec![UnitDef::new(army, kind, x, y)])`
  (full HP; a cell in use is skipped).
- *Hidden bonds.* `CampaignDef::bonds` (at most 12) lists the CO whose CO
  page shows each secret quote (it replaces that CO's bio page while a
  bond is earned, in the BH session); `Action::EarnBond(k)` earns bond k
  (saved in the record); `Needs::Bonds(vec![..])` opens the secret mission when
  every bond is earned (`bh_campaign_mission_data_fields`); the last
  `CampaignDef::extra_bonds` bonds are extras: they show their quote and are
  in the legend's count but not among those the secret mission needs. The BH
  Campaign has ten: the nine recruits' (the secret mission M31 opens with
  these nine, design 2.2) and Crumb's, `bh_campaign::bond::CRUMB_QUOTE` (9),
  earned by winning M14 on day 12 or sooner, whose CO page quote is "Nobody
  left me behind. Not once. I'm keeping count." (4.7b; AW2's page wraps it by
  pixel width, three lines).
  **Bond legend** (`bond_ui.rs`): nothing shows on the world map until a
  bond is earned; from the first earned bond on a small legend sits at the
  map's top left: a gold star, "RECRUIT WON OVER" and "BONDS n/m" (m: all the campaign's bonds, ten in the
  BH Campaign: `bh_campaign_legend_counts_crumbs_bond`), in AW2's
  font with its outline, below the "CAMPAIGN" title while that shows (its
  letters are tall sprites along the top edge) and at the very top without
  it (the mission panel open); hidden while a dialogue runs. Sprites in OBJ
  tiles 735.., 772.. and 848.. and an OBJ palette bank no sprite of the
  frame uses (the title's own bank, 14, must not be written: that once turned
  the title brown). The CO page keeps only the secret quote
  (`bh_campaign_bond_legend_on_the_world_map`,
  `bh_campaign_bond_quote_on_the_co_page`).

Limits and notes: a campaign has at most 32 missions (progress bits; 30 +
the secret one), the unlock mask has 12 roster bits and 12 bond bits, and
its blob must fit `0x08F00000..0x08FBFFFF` (checked at load; Dual Strike's
is about 360 KB); texts use ids `0x7400..0x7FF5`. The first mission opens at
`Requires::Start`, and at least one mission must be open at any time or the
map is empty. Mission ranks use AW2's results screen. A mission's start
CO screen and Setup phase need `bhcampaign.PICKS` in tests.

Tests: `tools/aw2test/tests/test_bh_campaign.py` (menu entry with and
without the pack; New, the prologue and the world map with one flag; mission
1 and Von Bolt unlocked; the CO screen offering only unlocked COs; the
credits; every data field; a named unit's extraction and death latch; two
fronts; five armies; the second stage; a built map; both campaigns in one
boot), `test_bh_map_tool.py` and the save tests above.

**Act II (`bh_act2.rs`, Green Earth: M4 to M11).** Maps `five/bh/bh04.txt` ..
`bh11.txt` (`bh08b.txt` is M8's second front), dialogue the design bible's
(section 4.3), tests `tools/aw2test/tests/test_bh_act2.py` (`-k bh_act2`; the
balance runs, `AW2TEST_ACT2_BALANCE=1 ... -k bh_act2_balance`, play the CPU on
both sides and `aw2test.bot` against it and write `balance.json`). Things the
format needed, all in `custom_campaign.rs`:
- **Conditional lines.** `Line::only(co)` (the design's `@IF CO`: the player's
  main CO), `.with(co)` (in the player's pair), `.only_partner(co)` (the
  partner / the second front's CO once joined) compile to a conditional jump
  (script op 0x1E on `Cond::PlayerCo` / `PlayerHas` / `PartnerCo`, relative
  until `script` makes it absolute; AW2's own op 0x43 compares the CO id
  modulo 24, which cannot tell the Dual Strike COs apart). With a tag pair the
  army's active CO is not the first pick (the pending pair of `tag::set_cos`
  leaves the other pick as the partner): tests compare the pair as a set.
- **A victory scene and a bond on a won mission.** AW2's own rout ends the
  match before any trigger can run, so `Action::Win`'s scene and
  `EarnBond` are on a trigger that looks one step early (`beaten()`: the
  enemy has at most one unit left, or its HQ is the player's). The HQ capture
  path was measured to run its trigger first.
- **The day limit is only the header's counter** (the HUD shows it); the loss
  is a trigger on day `limit + 1` (`missions()` adds it).
- **Black Factory tables.** `MissionDef::factory` (day, three doors' units)
  is a mission's own table (`Custom::factory`, `ds_campaign::factory_table`,
  used by `factory.rs` instead of Factory Blues' schedule); M7's is F7.
- **Once-latch flags** are 96 for the whole campaign: Act II's day events are
  `EveryDays { n: 1000, from: d }` triggers (`repeating`, which fire once and
  take no flag).
- **Auto CO on a second front.** A Black Hole army played by the computer
  (the player's second-front army) wrote garbage at AW2's factory spawner on
  a map without a Black Factory (the game reset on day 2) and its AI hung once
  it could build: M8's dusk gate has a dormant Black Factory (an all-zero
  table) and the player's army there has no base.

**Free Play.** Once the final mission is won (`ds_campaign::free_play`) the
map offers every mission again, the won ones cleared and open to replay. A
replay's win changes nothing of the progress (`end_of_battle`: the won bits,
the progress step and the recruits stay, the flags go back to the record, no
new records or bonds: `earn_bond` and the records ignore a won mission, no
staff roll), so the roster, the bonds and the records are the campaign's as
they were; the CO screen offers the whole unlocked roster. A mission not
yet won (the secret one, opened by its bonds) is played for real, wins
included. Test: `bh_campaign_free_play_replays_change_nothing`.

**The secret mission's extras.** `CampaignDef::secret_mission` (a key) names
the 31st mission; its win (`ds_campaign::secret_won`) adds the roll's
**secret sections**: a `CreditSection { secret: true, .. }` is in
`ds_credits::Credits::secret_list` and not in the plain `page_list`
(`ds_credits::tick` switches the pool words); the secret epilogue is such
sections (names of at most 21 letters a line: the roll's pages are text
only, so the epilogue is shown after the staff names as roll pages, not as
speaker boxes). The mission's `recruits` is Sonja (`roster::SONJA`, AW2 CO
7): she joins the roster and, with Von Bolt, the made-up pair **Vault
Breakers** (`sturm_pairs::DUOS`: compatibility 115, 2 stars, four victory
lines; wired through `tag::compatibility`, `special_pair`, `tag_extras::
pair_texts` and `partners_of`, the pack only). Test:
`bh_campaign_secret_mission_credits_and_sonja`, `tag_vault_breakers`.

**The Colonel's Vault** (`five/design_vault_map.py`): a 2-army, 30x20 Versus
map on the Vs. tab, listed with the pack only (`look pack` in the map file:
normal colours, pack-only), the BH Campaign's prize map. Its id is `0xF1` (`five_map::VAULT_ID`, past Survival's `0xC9..0xEF` with the Champion courses and the campaigns' `0xF0`). The list's "may this map be shown" test (`0x0803CA54`) reads a bit of the unlock block, `0x02028042 + id / 8`, which has no bits for ids from `0xF0` up (so the list had no cursor entry for them); `five_map::traps` answers yes for them while the larger map table is in use; the map table grew to
`0xF0` ids (`five_map::MAP_IDS`; the table at `0x08650000..0x08655583`, the
maps past the tenth now from `0x08656000`), and with the pack the list's walk
goes to `0xF1` (always: it is listed from the start, not only after the
secret mission). Survival's copy of the table includes it. The apostrophe
in a map's name is AW2's `~`. Test: `ds_map_the_colonel's_vault` (opened from
its tab, preview and tiles, every unit; the CPU plays six days).

**The Campaign chooser** shows all three entries at once (AW2 CAMPAIGN, DS
CAMPAIGN, BH CAMPAIGN): the game's box has two label sprites, the third is
added at the sprite flush (priority 0, so the girl's sprites do not cover it);
with more campaigns the three-row window scrolls (`campaign_menu::ROWS`).

## Clone Andy (`co_new.rs`)

The BH Campaign's last recruit. **What Dual Strike has for him**, found in
the .nds: no CO record of his own (CO records are ids 1..27, no 28th) and
no portraits, powers, quotes or tag data of a clone's. Dual Strike's clones
(Olaf, Drake, Kanbei and Andy; "Cloned COs, requiring massive amounts of
energy ...") are the original's CO id with bit 7 set in a mission record's
CO bytes, as a Black Hole army's tag partner: Dark Ambition has Kindle with
the Olaf clone `(25, 0x84)`, Pincer Strike Lash with the Drake clone
`(12, 0x8A)`, Ring of Fire Koal with the Kanbei clone `(14, 0x87)` and
Surrounded! Kindle with the Andy clone `(25, 0x82)` (Andy, id 2, | 0x80).
The story speaks of "an Andy clone"; the clone is drawn and plays as the
original, in Black Hole's army colours.

So Clone Andy is tangoAW2's tenth new CO (id 81, `co_new::CLONE_ANDY`), on
**Dual Strike's Andy's data** for everything it has: portraits, face, HUD,
mini portrait (all read as Andy's) and CO Power and Super CO Power (Hyper Repair / Hyper Upgrade, AW2's
own power code, the names and texts from Dual Strike's record 2), numbers,
quotes, victory quote, map theme (Andy's Dual Strike theme, converted like
the others'), tag compatibility row and column. **tangoAW2's own**, made up,
marked in code: his name "Clone Andy", his name graphic "Clone" (the
six-sprite name picture composed at run time from AW2's own letters: C, o, l, n
of Colin's and the e of Eagle's, outlines shared as in the game's names:
`co_new::clone_name`; the test `clone_andy_name_graphic` draws it beside other
CO names, `clone_andy_name.png`), and his CO page bio
(`CLONE_ANDY_NAME`, `CLONE_ANDY_BIO`), his place (Black Hole's Teams
group after Koal, Black Hole's battle style and army colour, Adder's CPU
profile and Black Hole power music: the `like` of his `NEW` entry), and
his pair with Sturm (below). With the pack only: he is on the Versus and
War Room CO lists and the Teams screen (`Teams list: 29 COs`), pickable
(`clone_andy_is_pickable_in_versus`), absent without the pack
(`clone_andy_absent_without_the_pack`), in the BH Campaign's roster, and the
Select-skills data (`co_skills::COS` 29).

**Tag.** Dual Strike has no tag data for a clone, so with any CO but Sturm
his compatibility is Andy's own (his row and column of Dual Strike's table,
`tag::compatibility`) and he has none of Andy's special pairs (`tag::
special_pair`, `tag_extras::partners_of`); his TAG page lists Sturm alone.
**Sturm + Clone Andy** (tangoAW2's own, in `sturm_pairs.rs` with Sturm's
other pairs, partners now named by AW2 CO id): compatibility 118, two stars,
Tag Power "Perfect Copy", victory exchanges ("Flawless. As built." /
"Orders done!", "Hold nothing back." / "Yes, sir!", and Clone Andy winning:
"Mission complete!" / "Acceptable.", "Who's next, sir?" / "Anyone."; measured
to fit the results box by `tag_extras`' `victory_exchanges_fit_the_box`).
Sturm's TAG page lists Clone Andy last. Test: `tag_clone_andy` (compatibility
in the damage calculator both ways round, Andy's value with the others, no
special pairs, both TAG pages, the Tag Power screen's name and 118%, the
exchange in battle).

## Crumb (`crumb.rs`, `crumb_art.rs`)

The BH Campaign's last new CO ("Pip Hobb", a Black Hole soldier promoted to
Commander; design in `docs/BH_CAMPAIGN.md` 3.9 and 4.7c): tangoAW2's eleventh
(id 82, `co_new::CRUMB`), **pack only**, **everything of his tangoAW2's own**.
Unlike Clone Andy he has no Dual Strike twin at all (no entry in
`co_new::NEW`, `co_new::ds_id` is `None`, as for AW2's Sturm): Dual Strike's
music, pictures, texts and tag data are not behind him, so he plays Adder's
AW2 theme (his `like`), his tag compatibility with every CO but Sturm is the
neutral 100 (no row, no column; `tag::compatibility`), and the tag screens
draw his figure as AW2's own path does for a CO without one (`tag_screens::
aw2_figure`: the CO page's body). On the Versus, War Room and Teams lists
after Clone Andy (Black Hole's group), Black Hole's battle style and army
colour, Adder's CPU profile (`like`), a Select-skills data slot
(`co_skills::COS` 30), and in the BH Campaign's roster (index 11).

**Rules** (`crumb::bonus`, called by `co_roster::stat` in place of a Dual
Strike block; the tests' calculator is `damage.crumb_bonus`):

| | |
|---|---|
| Day to day, **Rank and File** | Infantry and Mech +10% attack and +10% defence; his units on his cities and bases are fully resupplied (ammo and fuel) at the start of each of his turns. AW2's own turn-start property pass resupplies (and repairs) the units a property takes care of; a trap in it (`0x0802A08E`: the pass's "this property repairs this unit" test failed) fills ammo and fuel of the others (an aircraft on a city or base, a ship on a base), for his city (class 6) and base (14) only |
| CO Power, **Ration Run** (3 stars) | every unit: ammo and fuel to full and 1 HP healed, as a function the power's presentation row calls for each unit (Thumb in free ROM at `0x08749C00`: AW2's own `sub_08029978` / `sub_08029A48` / `RepairUnit(unit, 1, 0)` called through r3); Infantry and Mech +1 move (the power level's move bonus) |
| Super Power, **Gerald's Blessing** (6 stars) | every unit healed 2 HP (Andy's own unit effect, `0x080444ED`); Infantry and Mech +30% attack on top of Rank and File (and the +10% every power adds in Dual Strike's rules: 50 in all); luck 0..19% for every unit and no bad luck (his CO table row: luck 10 day to day and in the CO Power, 20 in the Super Power, bad luck 0; AW2's Nell has 20, 60, 100) |
| Tag with Sturm, **No One Left Behind** | 115%, 2 stars (`sturm_pairs::PAIRS`: made up for tangoAW2 like Sturm's others), victory exchanges from the design. The Tag Power fires both Super Powers; the second one's end (the army's power level 2 in its second half: `crumb::tick`) heals every unit of the army at 3 HP or below (internal 30) to 6 HP (60) and gives each one more move this turn |

**Why those star costs.** Dual Strike's most common meter is 3 stars for the
CO Power and 6 for the Super Power (Andy, Max, Jess, Javier, Kindle, Rachel;
Hachi 3 and 5, Koal 3 and 5): a support CO whose powers heal and resupply
without hitting anything charges no faster than Hachi's, no slower than Max's.
His powers need no more than the common 3 / 6 because neither deals damage
and his own battle numbers (+10% on two foot units) are weak.

**The extra move.** Per-unit move is not a thing the game's movement function
knows (it is called with an army and a type); the units healed by the rule are
bits in RAM (`0x0203F5D8`, 40 bytes: the unit slot is the bit), and
`GetUnitMovementWithCoBonus`'s trap (`co_skills::move_done`, which calls
`crumb::move_bonus`) adds one when the unit being selected (`0x030040D8`) has
its bit and the army is the pair's. The bits and the rule's state
(`tag::STATE + 0xD0`: the army, the rule's phase) go with the army's turn; they
are in emulated RAM, so rollback and netplay keep them.

**The power's quote.** AW2 picks one of a CO's six quotes at random for every
power; his are Ration Run's, Gerald's Blessing's and the Tag Power's, twice
over, and a trap at the pick (`0x080398E0`) takes the one of the power being
paid for (`PayForPower`'s entry, `0x0804438C`, writes it to `tag::STATE +
0xD2`). The defeat quote is kept in text slot 14 (`co_new::T_DEFEAT`): AW2's
results screen has no defeat quote.

**Pictures** (`crumb_art.rs`; the only stored art is the author's drawing, the rest is cut from the player's AW2 at the
start, like Clone Andy's name). The Black Hole trooper of the campaigns'
dialogue (CO presentation row 23: three alike 48x48 faces, a 32x24 mini
portrait, a palette; no HUD face, body or name) is every graphic:

| Graphic | Made of |
|---|---|
| CO select face (the Teams screen) | the trooper's face, as it is |
| Teams portrait | the trooper's mini portrait, as it is |
| HUD face (32x16) | a 32x16 cut of the face round the red lens (x 13, y 17), 1:1 |
| CO page figure, power and tag screens (128x160) | **the author's own drawing** (`art/crumb/crumb_user.png`, 104x118, 14 colours + transparency, a side view mirrored to look left as stored; `tools/crumb_art/reconstruct.py` rebuilt the native pixels from the upscaled JPG: grid detection, cell sampling, colour clustering and snapping, transparent background; a native PNG takes the same path), at its own size, centred and bottom aligned with the last two rows empty (the tag screens carry a figure's last row down). Its palette is the CO's, and the small faces below are moved to its nearest colours. If it fails to load: the face grown twice with nearest neighbour, framed (98 x 98, centred at y 24), the trooper's own palette |
| Name "Crumb" | C of Colin's name graphic, then r, u, m of Sturm's and b of Kanbei's, outlines shared as in a name |
| Palette | the trooper's in all eight schemes |

**BH Campaign.** `roster::CRUMB` (index 11) is in the roster; he is promoted
at the end of M28 and offered from M29 on: M28's builder gives the mission
`recruits = vec![roster::CRUMB]` (the win unlocks him) or ends a trigger's
`then` with `bh_campaign::unlock_crumb()` (`Action::Unlock(roster::CRUMB)`:
unlocks him at once, saved with the record, nothing in a replay). His
secret quote (earned by winning M14 on day 12 or sooner) is bond 9
(`bond::CRUMB_QUOTE`, `Action::EarnBond(9)`): the tenth bond-style CO page
quote (`crumb::SECRET_QUOTE`), which does not count for the secret mission
(opens with the first nine; `ds_campaign::bonds_all`) nor for the BONDS legend.

**CO page text.** The page holds six lines of 103 pixels. The bio is in AW2's
bio style for a Versus player: "A Black Hole soldier promoted by Sturm. Keeps
his troops fed and supplied." with "Hit: Biscuits" and "Miss: Being left
behind" (the design's story bio did not read as a CO description).

Tests (`test_crumb.py`, `tag_crumb*` in `test_tag.py`, `all_powers_crumb_*`,
`netplay_powers_crumb_*`): `crumb_is_pickable_in_versus`,
`crumb_absent_without_the_pack`, `crumb_rank_and_file` (the calculator both
ways), `crumb_ration_run`, `crumb_geralds_blessing` (heal, +50%, luck), `crumb_name_graphic`,
`crumb_resupplies_on_cities_and_bases`, `crumb_power_quotes`,
`tag_crumb` (compatibility, neutral 100, TAG pages, the screen's name and
115%, the exchange), `tag_crumb_no_one_left_behind` (both orders, the heal
rule, the extra move, gone with the turn), `crumb_netplay_is_deterministic`,
`crumb_tag_power_netplay_is_deterministic`, `bh_campaign_mission_data_fields`
(the unlock action), `crumb_screens` (pictures).

## Two fronts (`two_front.rs`)

Dual Strike's five two-front missions (Victory or Death!, Lightning Strikes,
Omens and Signs, Ring of Fire, Means to an End) are played on both fronts,
with the Dual Strike pack, offline.

**Dual Strike's two-front battles, as found** (the USA .nds, melonDS with
`tango-backend-melonds/examples/ds_script`; a battle in progress for each
mission was reached from Dual Strike's campaign map by setting the mission
record id the map hands on, `0x02183CC0`):

- **Two maps.** The mission's record (+0x10) names its second front's
  record (0xFC..0x100): its own map, deployment, look, weather and fog
  (+0x1A..+0x1C; Victory or Death!'s Black Arc flies in a sandstorm over a
  Desert look), the same armies, colours and teams, each army's tag CO (the
  second of its CO pair) leading it there, no day limit. The battle keeps a
  state per front (`[[0x027C027C] + 4 * front + 0x48]`, the front by
  `0x027C0284`); Dual Strike's palette function (`0x020F92B8`) gives only
  Means to an End's main front a palette of its own, every other front its
  look's (`0x02167DD4`: bmap/006 Normal, 00a Snow, 008 Desert, 009
  Wasteland). The second front is drawn in the Normal look whatever its
  record says (its record copies its main mission's look byte, +0x1A: 3 for
  Means to an End, whose second front is green): poked in melonDS, the main
  record's byte changes the bottom screen (Lightning Strikes in Snow) and
  neither record's changes the top one.
- **The top screen** is the 2D engine (engine B, read back in melonDS: its
  BG layers, palettes and sprites matched against the .nds's files): the
  map layer (BG0) draws the terrain and units. **In the sky** (Victory or
  Death!'s and Omens and Signs' second fronts, the Black Arc's: their
  deployments are all aircraft) it draws the units only: under them BG1 is
  a field of clouds (`bmap/098` tiles, `bmap/099` 32x32 tilemap, `bmap/09a`
  colours) blended over BG3, the ground far below (`bmap/092`, `093`,
  `094`; `BLDCNT` 0x3C42, `BLDALPHA` 0x1008: clouds 8/16, ground 16/16);
  the Black Arc is a 64x64 sprite (`bmap/0a7`, colours `bmap/0aa`) where a
  sea map has its fortress (`bmap/0a6`, the bytes of AW2's own fortress
  picture), its minicannons sprites in the same colours. No sandstorm is
  drawn there.
- **Turns.** Day 1: the main front's armies in order (the player, then Black
  Hole), then the second front's (in order), then day 2 on the main front;
  both fronts count the same day. The second front plays on the top screen
  (SWAP shows the top screen's info panel instead).
- **Who plays it.** "In Campaign mode, the second front is controlled
  automatically" (the tutorial, bank 0x31): the player's second CO's army is
  the computer's. **Auto CO** (melonDS, the states of each mission's battle
  and its Setup phase): Intel's menu (Status, Terms, Unit, General, then
  Auto CO) has a last item "Auto CO On" (bank 0xC0 text 102; its help line
  "Allow CPU to direct the secondary front.", text 740) in **Lightning
  Strikes and Ring of Fire only**: its test (arm9 `0x020BE908`, its twin
  `0x020BE7A8` for "Auto CO Off") shows it only on the front whose map
  record is 0xEA or 0xF5 (`cmp r0, #0xEA` / `#0xF5` on the record's +0x34)
  while the other front is not over; Victory or Death!, Omens and Signs and
  Means to an End have no such item. It is **on at the start** ("If it
  sounds too hard, I'd leave it on", bank 0x34 text 24). A chooses it and
  the item becomes "Auto CO Off" in place (text 103; "Direct the secondary
  front manually.", text 741), the menu staying open; A again turns it back.
  It is the controller byte of the player's army on the second front (its
  player record's +0x1A: 2 the computer, 1 the player; the test reads it,
  the item flips it). It is on the **main front's** Intel only (the second
  front's Intel is Status and Unit), in the Setup phase and on any later
  main-front turn ("You can turn Auto CO on or off anytime", bank 0x29
  text 23): turned on on day 2, day 2's second front was the computer's
  again. **Off**: after the main front's armies (the player's End, Black
  Hole's turn), the second front comes to the bottom screen with its own
  "Day 1" banner and waits for the player: the player's army there with
  its CO (the tag CO, the second front's: Jake), its own funds (5000 where
  the main front had 6000) and units; its menu CO, Intel, Options, Save,
  End (no Power: "CO Powers can't be used there, either. The action is too
  fast."); End: Black Hole's turn there (the computer's, top screen), then
  the next day on the main front.
- **General** (Intel's item after Unit, arm9 table `0x02165F30`, 0x20
  bytes an entry: test, help, handler, label): Dual Strike's ally posture,
  in **every two-front mission**. Four items, one shown at a time (each
  test, `0x020BE560`, `0x020BE358`, `0x020BE150`, `0x020BDF48`, shows its
  own posture), with the AI icon (the font's `\xC2\xA1`; `icon/res_icon0_cg`
  icon 0x5F, palette 0 of `icon/res_icon_cl`, pixel for pixel what the
  menu shows): **Strike** (bank 0xC0 text 98; help "Set ally to aggressive
  posture.", text 707), **Assault** (99; "Set ally to offensive posture.",
  708), **General** (100; "Set ally to general, all-purpose posture.", 709),
  **Defense** (101; "Set ally to defensive posture.", 710). A (handler
  `0x020BCB94`) turns it to the next, the menu staying up: General,
  Defense, Strike, Assault, General. It is the army's player record's
  +0x2E (0 Strike, 1 Assault, 2 General, 3 Defense), written on both
  fronts; the battle starts the player's army at the last choice, which
  the handler also keeps in the game's save data (`0x02290718` +0x17, +0x16
  in the other mode; setup `0x020C1444`), every other army at General (2):
  a first battle starts at General. Shown on the main front's Intel (and
  the Setup phase's), any main-front turn, while the second front is not
  over (the other front's record +0x30, poked in melonDS: General and Auto
  CO both gone); in Lightning Strikes and Ring of Fire with Auto CO's item
  (on or off), in the other three while the army's second-front controller
  is the computer (always there). Not on the second front's Intel (Status,
  Unit). **What it changes**: Dual Strike's CPU reads the current army's
  posture on its turns (15 reads, arm9): its per-turn plan (`0x0208CBA8`)
  sets each unit type's two advance ranges (base +/- half a spread, from
  the plan table `0x02162A90`) by a percent: General and Strike a random
  0..99 each turn, Assault 100 (the top), Defense 0 (the bottom); its
  type table (`0x0208C948`) the same at 100, Defense 0; Defense skips its
  advance steps (`0x0209B458` from `0x0209B2B0`; `0x020AEEFC` in the three
  unit-class steps `0x020A00C8`, `0x020A022C`, `0x020A0330`) and its
  attack check refuses some attacks (`0x020A90EC`); every posture but
  Strike marks an attack down when the trade costs it (a half or a
  quarter, `0x020A92C4`, `0x020A9394`) and refuses some more
  (`0x020A9140`), Strike does not; Assault turns on a step of its own
  (`0x0209B974`, `0x0209CB9C`). Seen (Lightning Strikes, day 2, Auto CO
  on, the same state played four times): General and Defense, the ally's
  units on the second front hold round their base; Strike and Assault,
  they cross the map toward Black Hole.
- **Send** (the unit command table at arm9 `0x02166000`, 0x20 bytes an
  entry: "Send" twice, `0x021661E0` and `0x02166200`, their handler
  `0x020BCE50`): a unit leaves the main front for the second ("Keep in mind
  that units sent to the second front can't come back"), at no cost. On a
  front in the sky only aircraft go ("You'll need to send fighters and
  bombers up to the second front ... You won't be able to send helicopters,
  because they can't fly high enough"); "On maps where both fronts are
  based on the ground, units can be sent to the second front from bases
  that build units. Oh, and from the HQ, too. Units you've sent will arrive
  in the area around the second-front HQ. Naval units will arrive in the
  waters near the second-front HQ." A full front refuses ("The secondary
  front is full--you can't send any more units to the top screen").
- **Ends.** Each front's own records (Dual Strike keeps both fronts' records
  in one list: a condition's op is 3 x AW2's op + its front, 0 main, 1
  second, 2 either; a fire's 0x17 + its front) and AW2's rules end it. "The
  battle won't end if you lose on the second front, but the CO remaining on
  the main front will be left alone facing two enemy COs"; won, "The second
  front has been secured. The CO will now report back to the main front."
  and "the surviving units will be added to the power meter"; lost, Black
  Hole's CO goes to the main front ("Return to the main front for tag
  battle."). Its result: "The <army> Army has won / lost on the secondary
  front!" (bank 0xC0). Every condition of the five missions:

| Mission | Main front | Second front | Across the fronts | Test |
|---|---|---|---|---|
| Victory or Death! | won: every Black Crystal there destroyed (`0x023505E8`, after an action: Black Hole loses), or AW2's rules; lost: AW2's rules | the Black Arc: won when its four minicannons are destroyed (`0x02350610`), lost when the player is routed | the Black Arc's bomb on the main front's (13, 5) each Black Hole turn until the second front's winning record sets the battle's flag 2; won: the survivors charge the power meter | `two_front_victory_or_death` |
| Lightning Strikes | AW2's rules (rout, HQ) | AW2's rules | won / lost: the outcome's hook | `two_front_lightning_strikes` |
| Omens and Signs | won: the ocean fortress's four minicannons destroyed (`0x02350610` on the main front); lost: AW2's rules | the Black Arc: won when its minicannons are destroyed, lost when the player is routed | the fortress shielded while the Black Arc stands ("Black Hole's utilizing a barrier field ... energy is flowing from the Black Arc"); its fall: "Black Arc fatal error. Ocean fortress barrier collapsing." | `two_front_omens_and_signs` |
| Ring of Fire | lost on day 18 (Black Hole's turn-start record); won: AW2's rules; four cities taken: the Volcano stilled (`0x02351804` -> `0x02351988`) | AW2's rules | won: its match-end record stills the main front's Volcano (`0x023518CC`: "We've seized a volcano-controlling unit!"); each front's Volcano erupts on its own cells (arm9 `0x02167E98`: list 1 the main front's, list 2 the second's) | `two_front_ring_of_fire` |
| Means to an End | lost on day 24; won: the Grand Bolt's three weak points destroyed (`0x02350560`) | its three Black Crystals: each shattered plays "We have shattered one of the black crystals!" (`0x02351C58`); every one shattered wins it (`0x023505E8`); lost when the player is routed | each crystal shattered opens one weak point (west to east), shielded until then | `two_front_means_to_an_end` |

**The description** (`campaign_model::TwoFront`, a `MissionInfo`'s
`two_front`): the battle's own map header is its main front; the
description names the second front (`second`: an index of `Built::headers`,
the second front's header, and of `Built::missions`, its look, weather, fog
and armies), each army's CO there (`cos`: AW2 ids, or `PICK`: the player
picks it on the CO screen after the main front's picks), who directs each
army there (`control`, per army slot: `Cpu`, `Owner` or `AutoCo { on }`,
below), what may be sent
(`send`: `None`, `Air`, `Ground`), whether CO powers work there
(`powers`) and whether Intel has General (`posture`, below). The second front's header carries its own event lists (for
Dual Strike's missions: its records of the shared list,
`ds_campaign_data::convert_triggers` with front 1), its map, deployment,
colours, teams and 4x4 structure's picture, and no day limit; its
`MissionInfo` has the Normal look (above) and its record's weather and
fog. The look is set at every swap and view (`ds_campaign::set_look` from
`two_front::arrive`, before the map's graphics load; the biome is in the
weather block, so the suspend block carries it too). Dual
Strike's source fills it from the record (`ds_campaign_data::two_front`: a
front whose deployment is aircraft only is in the sky; `AutoCo { on: true }`
for every army of the missions whose records Dual Strike's Auto CO test
names, read from its two `cmp` instructions, `Cpu` elsewhere; `posture`
for all five). Nothing in
`two_front.rs` is Dual Strike's: a custom campaign's mission describes its
second front the same way.

**The gate.** `two_front::battle` decides where any of it is on: a DS
Campaign mission whose description has a second front. Without it nothing
runs or is written (the menus' pool words keep the game's tables; the
state stays zero): one-front DS missions, AW2's campaign, Versus, the War
Room, Survival, the Design Room, netplay and the pack off are untouched
(`two_front_menus_only_there`; the pack-off battery).

**How it plays.**

- **The store.** A front not on the screen is kept as AW2's own suspend
  block (`CaptureBattleSaveState` `sub_08016F38`: day, army, gPlaySt with
  its fog, weather and rules, the weather block with the look, players,
  units, the tiles changed from its map, inventions, the pipe seams;
  0xE28 bytes) and tangoAW2's state that lasts past a turn (the rain's fog
  rule, CO skills, Ex Machina's stun) at `0x0203E500`. The battle's flags
  (AW2's mission flags `0x030033F4`, its records' "once" flags among them)
  are the battle's, not a front's: they go across with every swap. The DS
  Campaign's session state (flags 0x20.., the countdown, Means to an End's
  and Ring of Fire's state) is the mission's.
- **The swap** is a script of AW2's script slots (the kind AW2's Continue
  runs, `0x0848A1EC`; ops: 2 call, 0x18 wait, 0x1E / 0x1F wipe to / from
  black): wipe to black, capture the live front into the staging buffer
  (`0x02000000`), exchange it with the store, write the other front's
  header into the battle's map table entry, then as AW2's Continue rebuilds
  a saved battle (`ResumeScript_LoadSuspendSave` `sub_08017658`:
  `InitGameSettings`, `RestoreBattleSaveState` `sub_08017208`, the terrain
  plane `sub_0801759C`, the unit cycle `sub_08026798`, the map's graphics
  `sub_08023348`, its frame callbacks `sub_0803662C`), set the map state
  machine's state (`0x030032D8`), wipe in. A front never played starts as
  a battle starts (`InitMapGameState` `sub_08034890` on its header, with
  gPlaySt's armies, COs, controllers and rules set for it, then its
  deployment, `sub_080196C0`, as the battle start's script `0x0849D10C`
  does). Its steps are magic stubs (`two_front::magic`, ids `0x2F000000 |
  n` through the DS Campaign's landing) that tail-call the game's
  functions.
- **Rounds.** At the handover state (`MapState_TurnHandoverPrompt`
  `0x08034AF8`, trapped) with no army after the current one in the battle,
  the round's swap runs instead; the other front is brought back at its
  own handover (the next handover passes), so its next army (and day)
  begins as AW2's own turn change does. While the second front is fought,
  the main front plays a round, then the second front, then the next day.
- **Front** (the map menu: the game's table copied with Front after
  Options, `MAP_MENU_POOL` `0x0802D49C` pointing at the copy while the gate
  is on; Save's test made ours, hidden during a swap): the same swap, the other front shown with the map cursor (its
  army made the player's for as long, as AW2's dispatch gives a player's
  army the cursor) and every button but the D-pad kept from the game; B
  swaps back. The front looked at is put back as it was (its block still in
  the staging buffer, checked; a front set up only to be looked at is set
  up again at its first round); the front left comes back as AW2's
  Continue brings a saved turn back (`two_front_view_round_trip`: units,
  players, inventions, gPlaySt, the map's planes, day and army, weather,
  the battle's flags, the cursor, the skills byte for byte).
- **Panels.** The help line ("View the other front.", while Front is
  highlighted, where AW2's map menu has its own), the view's title and its
  B button ("Second front", or "Main front" when a human's second-front
  turn looks back at it; "Back"; top centre: while the other front is
  looked at its army's CO panel is not drawn, `co_panel` through
  `tag`'s `DrawArmyCoPanel` trap, its face's tiles being the turn's army's;
  nor the terrain and unit panels, put below the screen in their frame
  function, `0x0802AB34`, since they would sit on the front's units at its
  edge) and
  the second
  front's result ("Second front won!",
  "Second front lost.", on the player's turn): a window of AW2's own (its
  map menu's window cells on BG2, palette 8; the cells under it kept and
  put back; BG2 scrolls with the map, so the window goes where the scroll
  puts the screen, `BG2HOFS`/`BG2VOFS` read back, and waits while the map
  moves between cells) and AW2's proportional font (the menus' glyphs `0x084C32E4`,
  widths `0x084C36E4`) drawn into free OBJ tiles (`heal_effect`'s, which it
  uses only during a structure's heal) as 8x16 sprites. During the second
  front's rounds "Second front" stands at the top in the same font, white
  outlined in black, without a window (the game's own windows come and go
  there during CPU turns).
- **Send** (the unit command menu's copy, `UNIT_MENU_POOL` `0x0802D59C`):
  in the slot of the "Capt" with a star, which no sendable unit ever has
  (an aircraft never captures; a unit on its own HQ or base has nothing to
  capture), the command menu having room for 13 entries, all used. Shown
  by the description's rule (greyed when the army has 50 units there);
  chosen, the game's Wait ends the move, then (`RunMapEventsAfterUnitAction`
  `0x080743E8`, trapped) the unit leaves the main front and is written into
  the stored second front by its army's HQ there (else its units' cells),
  on the nearest free cell its movement can enter; before the second front
  starts it waits in a queue of 8 and arrives when it does.
- **The second front's end.** Its records (or AW2's rules) end its battle as
  any battle ends (`FinalizeMatchResult`, the match-end records, state
  0x12); at `MapState_EndOfGame` (`0x08034EF0`, trapped) on the second
  front, once its scenes are over, the outcome is kept and the main front
  comes back for good (its result panel shown). Won: the survivors' value
  (price x bars, as a battle's) charges army 1's power meter
  (`sub_080440E0`). Then `second_front_over`, **the hook for tag pairs**:
  `second_front_result` gives (won, the winning army, its second-front CO);
  a tag-pair module joins that CO to that army's main-front CO there.
- **The CO screen.** A two-front mission's second-front picks follow the
  main front's on AW2's own CO screen (`sub_0803BD14`, the number of picks,
  and `SetArmyCoIdsFromList` `sub_0803BCDC`, trapped while it shows):
  Lightning Strikes' main CO is fixed (Rachel) and the player picks the
  second front's.
- **Who plays a second-front turn** (`control`, per army; the engine never
  asks who "the player" is). An army's **owner** is its controller on the
  main front (AW2's per-army controller byte, the player record's +0x1B: 1
  a human, local or a netplay peer by its seat, 2 the computer), read from
  the main front's block in the store. The army's controller on the second
  front, written into its player record and gPlaySt each time the second
  front comes on the screen (set up or brought back): `Cpu` 2; `Owner` the
  owner's; `AutoCo` the owner's while that army's Auto CO is off, 2 while it
  is on (a computer owner's army is the computer's either way). AW2's own
  turn dispatch then gives a human's army the cursor and the computer's its
  CPU turn, as on any map: a human plays the second front's turn with that
  front's CO, funds, units and rules (CO powers as the description says).
- **Auto CO** (`AutoCo`): Intel's menu (the game's table `0x0849ABC0`,
  opened by `0x0802D504` from its pool word `0x0802D550`, pointed at a copy
  while the gate is on) gets Dual Strike's two items after AW2's own,
  "Auto CO On" and "Auto CO Off" (no icon, as Dual Strike's), one shown at a
  time, as AW2's Options menu shows Music On / Music Off: shown to the
  current army on its main-front turn (the Setup phase's Intel too) while
  the second front is fought and its description is `AutoCo`; chosen, the
  army's setting flips and the menu is redrawn in place (`0x08019E68`, what
  Music's handler calls). Its help line is Dual Strike's for the setting
  as it is (`two_front`'s panels). The setting is a bit per army
  (`0x0203E41B`, set means off: a save from before reads on), started from
  the description's `on`, saved with the battle; a change takes effect at
  the second front's next round. Not on the second front (Dual Strike's
  isn't either).
- **General** (`ally_posture.rs`, the description's `posture`): Intel's
  copy has Dual Strike's four posture items after AW2's four (Strike,
  Assault, General, Defense; text ids 0x7FF6..0x7FF9), one shown at a time,
  before Auto CO's: shown to the current army on its main-front turn (the
  Setup phase's Intel too) while the second front is fought, when its
  description is `AutoCo` (on or off) or the computer directs it there;
  chosen, the posture turns to the next (General, Defense, Strike, Assault)
  and the menu is redrawn in place, as Auto CO's. The labels, help lines
  and icon come from the .nds at run time: the names of bank 0xC0 texts
  98..101 after AW2's icon code `\x09\xE6`, padded with AW2's narrow
  spaces (0x18..0x1F) to the widest so the menu keeps its width; the help
  line (texts 707..710, one line) in `two_front`'s panel; the icon
  (`icon/res_icon0_cg_E` icon 0x5F) in BG0 tiles 0x34C..0x34F (the code
  0xE6's: AW2's menu icons are tiles `0x1B4 + 4 * (code - 0x80)`, palette
  10; AW2 has 0x80..0x95, and the battle map leaves those four tiles
  empty), written while the Intel menu is up and only over empty tiles,
  emptied when it closes; Dual Strike's icon palette is AW2's palette 10
  colour for colour, so its pixels go in as they are. The posture is two
  bits per army (`0x0203E41D`, posture XOR General: 0 is General, and a
  save from before reads General), started at the battle's first frame:
  each human army (gPlaySt's controller 1) at the last choice, kept in the
  DS Campaign's record (`0x0203FD3C`, saved with it), the computer's at
  General; saved with the battle. **Its effect** (the one mapping to AW2's
  CPU): AW2 moves each CPU unit, after its attack check, by the unit's role
  (its record's +0x0B: the deployment's AI byte or what the CPU's
  production gives a unit; `AiRunRoleMove` `0x0805F4CC`, trapped, through
  the table `0x085768E0`). While a two-front battle's army has a posture
  other than General, its units move by the posture's role instead:
  **Strike 4** (toward the nearest enemy units, and into them at any odds:
  Dual Strike's Strike does not mark down a trade that costs it),
  **Assault 3** (onto the enemy's properties, each unit given its own: the
  offensive push Dual Strike's Assault gets from its advance ranges at their
  top), **Defense 0** (where it stands: Dual Strike's Defense skips its
  advance steps; a unit still fires at what comes into reach),
  **General** the units' own roles. Measured on Lightning Strikes' second
  front (its ally units' roles 0 hold, 1 the enemy HQ, 3 enemy properties, 4
  enemy units, 7 by the HQ played from one state): 4 and 3 cross the map
  (mean distance to Black Hole 16 to 9 and 11 in a round), 0 holds; on Ring
  of Fire and Means to an End 4 also fights (Black Hole loses units), 1
  stays where the front has no enemy HQ, so Assault is 3. The computer
  reads the posture on every front (as Dual Strike does), but only the
  owner's armies have the item; outside a two-front battle the trap does
  nothing. Netplay: the posture and the current army are emulated RAM, the
  ROM writes follow it, nothing reads the host.
- **A mission saved halfway** keeps both fronts: the block of the front on
  the screen (the main front, or the second during a human's turn there:
  Dual Strike offers Save on both), then "T2FT", the two-front state and
  the store, in slot 14 (AW2's writer splits a record over sectors of
  0xFAD bytes: two parts); Continue brings them back
  (`two_front_saved_halfway`, `two_front_auto_co_saved`, across a reboot).
  Saved on the second front, Continue first writes that front's header into
  the map table entry (read from the record in Flash before AW2's resume
  runs, `suspend::resume_ds`), so `InitGameSettings` and the terrain load
  its map; its look is set once the block is restored, and the front stays
  live until the battle is on the screen (`0x0203E41C`).
- **In the sky** (`sky_front.rs`, the description's `sky`): every cell is
  drawn with the clouds (the picture's 16x16 at the cell's position,
  repeating) by `wasteland`'s painter (`BlitMapRow`/`BlitMapColumn`, with
  no look of Dual Strike's drawn), their 65 tiles in static terrain tiles
  1.. (nothing else is drawn there) and BG palette 1 (and its fogged copy
  5) in the clouds' colours blended over the ground's mean colour (one
  colour for the ground: AW2 has one map layer); the cells keep their
  terrain (sea: air units only). The fortress's picture (OBJ tile 0x130,
  `LoadInventionGraphics`' base 0x48 + 0xE8) becomes the Black Arc's and
  OBJ palette 10 (the structures' and minicannons') its colours while the
  front is on the screen, both put back after (`two_front_looks_and_deployments`).
  Its weather is clear (`ds_campaign_data`: Dual Strike draws no sandstorm
  there).
- **Means to an End**: its crystals stand on its second front only
  (`ds_campaign_data::MTE_CRYSTALS`, (1, 1), (8, 1), (14, 1), west to
  east); while the second front is on the screen each crystal shattered is
  kept (`0x0203F705`, a bit each) for the main front's weak points
  (`ds_campaign_rules::crystal_alive`). **Omens and Signs**: the main
  front's fortress minicannons keep their hit points while the second front
  is not won (a hit lands, its events see it, and is undone once the
  action and its scenes are over, `ds_campaign_rules::omens_barrier_tick`).

**RAM and ROM.** `0x0203E400..0x0203E4A5` the state (front on the screen,
the second front's course, the swap, the view, the queue, the shared
flags, the second front's COs and the mission they were picked for),
`0x0203E500..0x0203F396` the store (block and tangoAW2's state); the
staging buffer's tail (`0x02001D80..0x02001FFF`: the panel's BG2 cells,
the incoming front's tangoAW2 state; the state's `0x0203E41B` is Auto CO's
bits, `0x0203E41C` a Continue on the second front, `0x0203E41D` General's
postures); the DS Campaign's record `0x0203FD3C` (the last posture). ROM
`0x08E70000..0x08E73FFF` (stubs, the three swap scripts, the menus'
copies: map menu, unit menu, Intel at `0x08E71100`; the labels, General's
at `0x08E71040..0x08E7107F`; text ids 0x7FF6..0x7FF9 Strike, Assault,
General, Defense, 0x7FFA Auto CO Off, 0x7FFB Auto CO On, 0x7FFD Send, 0x7FFE
Front: a campaign's texts stay below 0x7FF6); BG0 tiles 0x34C..0x34F
(General's icon, while Intel is up); pool words `0x0802D49C`,
`0x0802D59C`, `0x0802D550`; `0x0203E4C0..0x0203E4E3` `sky_front`'s
borrowed OBJ palette. Traps: `0x08034AF8`, `0x08034EF0`,
`0x0803BD14`, `0x0803BCDC`, `0x080743E8`, `0x080743AA` (the unit layers'
rebuild after a Send returns there: alignment padding in
`UnitSelectedEvent_Init`, never run), `0x0802AB34` (the info panels,
below the screen in the view), `0x0805F4CC` (`ally_posture`: the CPU's role
move). Hooks in other modules:
`ds_campaign`'s landing (the stubs), `map_start` (the live front's rules,
its controllers), `script_end_match` (the main front's), `co_setup` (a
second-front pick opens the CO screen); `ds_campaign_rules` (crystals,
barrier, eruption cells, the Volcano), `grand_bolt::on` (the main front's),
`suspend` (both fronts), `pvp` (tick, menus, keys), `branding` (sprites).

**Compromises.**

- One screen: the second front is seen during its rounds and through Front;
  Dual Strike shows it on the top screen all the time.
- In the sky, the clouds are blended over one colour, not over Dual
  Strike's ground picture (AW2 has one map layer); the minicannons keep
  AW2's picture, in the Black Arc's colours; the terrain panel still says
  Sea.
- Auto CO: a human's second-front turn is on the one screen (Dual Strike
  brings that front to the bottom screen for it).
- General: AW2's CPU has no advance ranges or trade weights to set, so a
  posture picks the role every unit of the army moves by (above); its
  attack check stays AW2's. The last choice is kept in the DS Campaign's
  record, which is written when the campaign saves its progress (Dual
  Strike writes its save data when it saves).
- The second front's computer is AW2's own CPU: under General, units with
  nothing in reach hold by their own roles (Dual Strike's may advance);
  Intel > General's Strike or Assault sends them forward, and the player
  sends units to carry it.
- Tag pairs: the second front's winning CO joins its army on the main
  front (`tag.rs`, through the hook above); Black Hole's CO does not when
  the second front is lost.
- The survivors' power is a battle's measure (price x bars), not Dual
  Strike's own formula (not read).
- The swap's wipes take about a second each way.

**A two-front Versus map, later.** Control is already per army and by the
army's own controller, so a Versus map needs no change to the rounds, the
swap or the turns: it declares its fronts as a campaign mission does, a
`TwoFront` with `control` per army slot, e.g.

```rust
TwoFront {
    second: 1,                       // the second front's header and MissionInfo
    cos: [PICK, PICK, PICK, PICK],   // each army's second-front CO, picked
    control: [FrontControl::AutoCo { on: false }; 4], // each army's owner plays, unless it turns Auto CO on
    send: SendRule::Ground,
    powers: true,
    sky: false,
    posture: true,                   // Intel > General: each owner's own army's posture
}
```

(`Owner` instead of `AutoCo` for a map that always gives each seat both
fronts; `Cpu` for an army whose second front is always the computer's.)
Whoever controls an army on the Teams screen (a human, local or a netplay
peer, or the computer) is its owner and plays its second-front turns: two
humans each play their own, and `pvp`'s seat-by-army rule gives each
second-front turn to its army's seat as long as the armies keep their
slots; each human's Auto CO is their own army's bit, changed on their own
main-front turns. What it still needs: a source of descriptions besides the
campaign's `Built` (two map ids of the Versus map table, a `TwoFront` per
map, `header()` reading its headers); the gate extended to it (and, online,
to both players having the pack, as the matches' content flags do); the
Teams screen's COs per front; and its suspend (Versus slot 4, as slot 14
here). The state is netplay-safe as it is: the
store and every byte of the swap live in the emulated EWRAM, every ROM
write (the map table entry, the menus' pool words, the stubs) follows RAM
each frame, and nothing reads the host; rollback restores both fronts with
the rest of RAM.

**Tests** (`tools/aw2test/tests/test_two_fronts.py`, no bot play: the
units and structures are set up directly): `two_front_rounds`,
`two_front_view_round_trip`, `two_front_menus_only_there`,
`two_front_send`, `two_front_cpu_directs`, `two_front_saved_halfway`,
`two_front_looks_and_deployments` (each front's look on its rounds, in the
view and back; the Black Arc's picture and colours in the sky only and put
back; each second front's units per army as Dual Strike's record), and
one per mission above (each condition of each front triggered through the
game's state); Auto CO (`tools/aw2test/tests/test_auto_co.py`):
`two_front_auto_co_only_where_ds_has_it` (Lightning Strikes and Ring of
Fire, on at the start; the other three, a one-front mission and Versus
without), `two_front_auto_co_off_human_plays` (the item flipped in place
with its help line; the player's second-front turn: controller, CO, funds,
menu, Front back to the main front and back, a unit moved, End, Black
Hole's turn there, day 2; Auto CO on again: the computer's round),
`two_front_auto_co_on_cpu_plays`, `two_front_auto_co_in_setup`,
`two_front_auto_co_saved` (the setting across a reboot; saved on the
player's second-front turn and continued there); General
(`tools/aw2test/tests/test_ally_posture.py`):
`two_front_general_where_ds_has_it` (the five missions, General at the
start, kept with Auto CO off, not on the second front's Intel, gone once
the second front is over; a one-front mission and Versus without),
`two_front_general_menu` (the cycle and its help lines, only army 1's
changed, the record's last choice; the icon's tiles Dual Strike's, its
colours the .nds's, empty after; a new battle starts at the last choice,
Black Hole at General), `two_front_general_changes_cpu` (one state played
with each posture: Defense holds, General moves by the units' own roles,
Strike and Assault advance, each its own way),
`two_front_general_only_there` (a Versus CPU turn the same whatever the
bits), `two_front_general_saved` (across a reboot); `ally_posture`'s
`from_the_nds` (labels, help lines, icon); `ds_campaign_data`'s
`two_fronts_are_dual_strikes` (with Auto CO's missions) and
`day_limits_are_dual_strikes` (with the .nds).

## Setup phase (`setup_phase.rs`)

**Dual Strike, as found** (melonDS): a campaign mission with a CO for the
player to pick (its record's 0x1C; Jake's Trial, whose COs are set, has
none) opens on its map with a "Setup" title and no day yet (funds 0). The
cursor moves freely; the menu (Y) is Setup ("Select a CO.": the Select CO
screen), CO, Intel, Options, Save and Deploy ("Begin battle with the
current settings."): Deploy brings day 1 (bank 0xC0 texts 86, 87, 753,
758; "You know you can scout the map before taking the field ... When
you're ready to start fighting, tap the menu button and choose Deploy",
bank 0x3A text 19).

**Here**, AW2's way: the COs are picked on AW2's CO screen before the map,
as before, so the menu has no Setup item. At the battle's first turn start
(`MapState_TurnStart` `0x08034DCC`, state 5, day 1, army 1: before day 1's
title, its funds and its opening events; trapped) the map goes to its
cursor state instead, with "Setup" at the top (AW2's font, white outlined,
`two_front`'s sprites). A, wherever the cursor is (`HandleMapCursorA`
`0x0802E4B4`, trapped), opens the map menu (`0x0802D458`, as an empty cell
does): a copy (`0x08E74080`) with CO, Intel, Options, Front (a two-front
mission's: the second front looked at) and Deploy (End's looks, text id
0x7FFC), Deploy's help line Dual Strike's (`two_front`'s panels). Deploy
closes the menu and the turn starts. B, L, R and SELECT keep AW2's. No
Save. The phase byte is `0x0203F706` (the DS Campaign's mission state).
Compromise: no Setup item (the CO screen comes first); funds are not 0
during the phase where the mission's header gives some.

Tests (`tools/aw2test/tests/test_setup_phase.py`):
`setup_phase_before_day_one`, `setup_phase_only_with_a_pick`,
`setup_phase_two_fronts`; the harness's `wait_control` chooses Deploy for
every other test (`DsCampaign.auto_deploy`).

## CO skills (`co_skills.rs`, `skills_panel.rs`)

Dual Strike's CO skills, from its code (overlay 0's skill table at
`0x022F5ECC`: 12-byte records by id, {rank, name `0x7C<<24|i`, description
`0x7B<<24|i`}; its per-CO bitmap test `0x020E7EE0`):

- **Skills.** Its 43 player skills (ids 0x20..0x4A) less the three tag
  skills (0x35..0x37: the tag pairs, see CO tag pairs, leave them out). Each takes a slot; their effects
  stack. Names, ranks and descriptions come from the pack.
- **In battle.** Each army's skills are a bitmap in RAM (`ACTIVE`,
  `0x0203F7E0`, 6 bytes an army), cleared at every map start and set by
  the mode (`battle_start`): the player's armies get their CO's set of the
  mode (DS Campaign and AW2's campaign: Campaign; Survival; War Room);
  Versus with its Skills rule on gives every army, the computer's too, its
  CO's Versus set. A set gives only the skills open to the CO, as many as
  its slots. Everything reads that bitmap: with no skill on a battle plays
  as it always did.
- **Effects** (Dual Strike's numbers; its functions in the module's docs):
  attack (direct/indirect +5/+8, terrain +10, Backstab +15, weather +20),
  defence (direct/indirect +8/+12, APC Guard +10) through the firepower
  and defence hooks the CO code already has; funds (Gold Rush +100 per
  earning property, Combat Pay 2% of the value hit), repairs (+1/+2),
  Missile Guard (silo blasts and the Black Arc 10 less), Cannon Guard
  (structure shots 20 less, `0x0803ED12`); and traps in AW2's code: move
  (`GetUnitMovementWithCoBonus` 0x08042D42, APC Boost), vision
  (0x08042DA6), capture points (0x0804269A), price (`GetCoPriceMultiplier`
  0x08042CC0; not for the power meter, as Dual Strike), luck (0x08042E64 /
  0x08042E7A), the meter (0x080440E0, Star Power x1.1), hidden fuel (with
  crate::ds_weather's fuel trap), move costs (`CacheUnitMovementCosts`'
  end 0x0801F91E), and the special-ability bits in a Super Power
  (`GetPlayerSpecialAbilities` 0x08043050 / 0x08043066: Mistwalker
  strikes first, Soul of Hachi deploys from cities; the computer never
  builds at cities).
- **Rank and slots.** A CO's rank is its EXP / 1000 (up to 100); a skill
  opens at its rank; slots = min(rank, 4). The rank-10 skills open with
  Means to an End won instead (Eagle Eye, Gear Head, Conquerer on Normal;
  Mistwalker and Soul of Hachi on Hard), as Dual Strike's flags 0x21/0x22.
- **EXP** (a won battle; the humans' COs): the DS Campaign the mission's
  score, x2 (x1 in Dual Strike's first eight missions), x2 on Hard
  (`ds_campaign`'s best-score trap); at `EndOfGame_Finish` (0x0803832C):
  Survival half the score, the War Room x2.5 (x2 with skills on), AW2's
  campaign as the DS Campaign's but only once the player has set skills
  for some CO (until then it stays AW2's own); Versus none. Dual Strike's
  few extra points for its battle counters are left out.
- **Save.** Per CO (AW2's 19 and the ten new): EXP and seven sets
  (Campaign, Survival, War Room, four Versus), 32 bytes, at `0x0203E000`
  after a magic word; saved in Flash slot 15 after the DS Campaign's
  progress and records (one 0x4A4-byte record). The DS Campaign's save
  writes it; after any profile write (`sub_0801A7D8(0, ..)` returning at
  0x08016E2C, 0x0801AC40, 0x0801AE2E) it is written again if it changed.
- **The SET SKILLS screen** (`skills_panel.rs`). On the CO screen (War
  Room, Survival, the campaigns: `ProcScr_CoSelect`) SELECT opens it for the
  CO highlighted; on Versus' Teams screen SELECT on an army's CO stop, for
  its Versus set (R and L there change the army's colour). Versus'
  Skills rule is a row of the Rules screen (`versus_rules.rs`, see CO tag
  pairs), off by default. It is Dual Strike's SET SKILLS screen on
  one screen, converted at run time from the .nds: its SKILLS RANK board
  (`ohashi/res_skilledit`'s tilemap and palette, `res_skilledit_lang_E`'s
  banner and spot tiles; ten rank columns 24 pixels apart, Dual Strike's 32
  tiles less two filler ones, six rows), its skill icons
  (`ohashi/res_skill`: a palette and 44 16x16 icons, 0 none, then one per
  skill from id 0x20), its CO bar (name, rank, the set's icons on its slots)
  above and its help bar (the skill's icon, name, rank, description) below,
  in AW2's proportional font (`0x084C32E4` glyph pointers, `0x084C36E4`
  widths: 16 rows of 4bpp nibbles, `(width + 1) / 2` bytes a row, colour
  0xA ink, 0xE shade). Skills the CO has not reached are faded, the set's
  have a red frame, the cursor is Dual Strike's corner brackets. The D-pad
  moves over the board, A puts the skill on the set (up to the slots) or
  takes it off, B (or SELECT, START) keeps the set and closes, as Dual
  Strike's BACK; the game gets no button meanwhile. Drawn on BG0 (char
  block 0, screen 14 on both screens) with BG palettes 0..2 and the other
  layers and the sprites off (gDispIo's DISPCNT shadow `0x030030CC`); what
  it covers is kept in the ROM image's free space (`0x08EF0000..`) and put
  back when it closes. Comparison: Dual Strike's screen (melonDS,
  `tango-backend-melonds/examples/ds_script`) beside ours, tests
  `skills_panel_co_screen`, `skills_panel_teams_and_rule`.
- **Netplay.** The console boots from seat 0's save and both seats' buttons
  reach the Teams screen: both peers have the same sets and rule (the
  host's skill data).
- **Tests:** `tools/aw2test/tests/test_co_skills.py`: each effect against
  the damage calculator (its `skill_attack`/`skill_defence`) or the game's
  numbers (move, capture, price, income, repair, meter), EXP and sets in
  the DS Campaign (across a reboot) and the War Room (in Flash), the SET
  SKILLS screen on both screens (and what it covers put back), the Versus
  rule.

## CO tag pairs (`tag.rs`, `tag_ui.rs`, `versus_rules.rs`)

Dual Strike's tag pairs (Change and the Tag Power) in AW2's battles, with
the Dual Strike pack. Its tag-only skills (Teamwork, Synergy, Bodyguard)
stay out.

**What Dual Strike does** (its arm9, read statically and checked in melonDS,
`tango-backend-melonds/examples/ds_script`):

- A player record is 0x98 bytes (P1 at `0x02189300` in a battle); its CO
  slots are the words at +0x6C (the active CO) and +0x70 (the partner):
  bits 0..6 the CO, 10..11 the power on, 14..17 the powers used, 21..31
  the meter. Each CO keeps its own meter and power count.
- The map menu (table `0x02165BE4`) is CO, Intel, Power, Super, Tag,
  Options, Save, Change, End. **Change** (`0x020DD6BC`) turns a power off
  (`0x020E2CE0`), swaps the two slots and their skills (`0x020E19B4`),
  shows the incoming CO's tag-in line and its swap animation, and ends the
  turn. **Tag** (`0x020DD404`, both meters at their Super Powers:
  `0x020E2AC8`) sets the record's +0x25 to 1 and runs the active CO's Super
  Power; in that first half End is hidden and Change ("Switch COs and move
  again.") sets +0x25 to 2, swaps, makes every unit ready (`0x020C6F98`)
  and runs the partner's Super Power. +0x25 goes back to 0 at the army's
  next turn (`0x020C1950`).
- **Meters** (`0x020DCA..`): the active CO is charged as alone; the
  partner gets half of the active CO's amount (then its own Star Power);
  nothing while a power is on (`0x020E2E10`).
- **The Tag Power's firepower**: the pair's compatibility (the CO record's
  +0x84 table, by the partner: 65..130) adds compatibility - 100 to
  firepower in both halves (`0x020E5C40` -> `0x020E5508`); defence gets
  nothing (its callers pass 0). Every pair has a compatibility (most 100;
  Von Bolt 90 with nearly everyone, Koal and Rachel 65, Nell and Rachel
  130). **Special pairs** (+0x6C: 8 bytes an entry, the partner, a star
  rating 1..3 at +2, a pointer to five text ids: four victory lines and
  the pair's Tag Power name, e.g. Andy and Max 1 star "Power Wrench" 110,
  Sami and Eagle 3 stars "Earth and Sky" 120, Kanbei and Sonja 3 stars
  "Battle Standard" 130, Hachi and Sensei 2 stars "Grizzled Vets" 100):
  the stars are the CO page's TAG box rating and do nothing in battle (a
  2-star pair can be 100, a 1-star 115); the bonus is always the
  compatibility. 47 entries (both directions, symmetric).
- **Change** ends the turn: the help line is "Switch COs and end your
  turn.", the incoming CO says its tag-in line, DS plays "CO★SWAP", the
  next army moves (checked in melonDS). The swapped-in CO is the active one
  from then on (its day-to-day, through the enemy's turn too).
- **The computer** (`0x020995C4`): Tag when both are ready; keeps its
  Super Power while the partner's meter is past half (the threshold is a
  parameter); no CO Power when the partner's Super Power is ready. At its
  turn's end (`0x02099F88`): in the first half Change; else
  (`0x02099BA0`, CO powers on, none on) Change when the active CO is
  nearer its Super Power than the partner, the two alike by a rating
  (`0x02099DAC`: Max 1, Sami 4, Grit 5, the others 2).
- **EXP**: both COs of a pair get the full EXP (`0x020E9C24`).

**What tangoAW2 does:**

- **State** (RAM `0x0203F400..0x0203F4FF`, netplay and rollback safe: all
  in emulated RAM). A record of 0x20 bytes for each army 1..5: the
  partner's CO, the phase (0, 1 first half, 2 second half), its power
  count, announcement byte, meter (u32), skills (6 bytes, `co_skills`'
  layout), the computer's second-half flag. The active CO stays AW2's
  (player block +0x1D); Change swaps the partner's fields with the player
  block's.
- **Map menu.** A copy of AW2's table at `0x08780000` (free ROM) with Tag
  (after Super, Super's icon, text 0x7300) and Change (before End, text
  0x7301), the menu pool word `0x0802D49C` pointing at it only while a
  battle has pairs; the entries' tests and actions are 16-byte stubs that
  jump to one trap (`0x0803CC5A`, dead code in `sub_0803CC3C`). With nine
  entries the menu opens at the screen's top (`0x0802D484`): it fits,
  y 2..158. Tag sets the phase and runs `MapMenu_SuperPower`; Change turns
  the power off (as AW2's day change does), swaps and runs
  `MapMenu_End`; Change in the first half swaps, makes the units ready and
  runs `MapMenu_SuperPower` for the partner (AW2's own Super Power screen
  and quote for each CO). The phase resets at `StartArmyTurn`
  (`0x080267AC`).
- **Meters**: `AddCoPowerCharge` (`0x080440E0`, the trap `co_skills`
  shares): the partner gets half, then its Star Power, up to its Super
  Power's cost; nothing while a power is on. The firepower (compatibility
  - 100, from the pack's arm9 record table `0x0215360C` + 0x220 a CO,
  +0x84) goes through `com_tower`'s firepower hook.
- **The computer**: `AiDeliberateCoPower` (`0x0805DB70`, `0x0805DBCC`),
  `AiEndTurnStep`'s end (`0x08061ACE`: in the first half it pays the
  partner's Super Power and plays the turn again with it; else Dual
  Strike's Change test), `AiBeginTurn`'s Black Factory call
  (`0x08061900`, not twice). The hold threshold is half; Dual Strike's
  battle-state ratings for Kanbei, Sonja, Hachi and Colin are 2.
- **On screen** (`tag_ui.rs`): under AW2's CO panel a second strip in the
  panel's own style (its tiles and army colours) with the partner's HUD
  face and its meter drawn as AW2 draws the active CO's. Under a dialogue
  box at the screen's top the strip is left out: AW2 neither hides nor
  moves its panel for its own events (the computer's after-action events in
  `sub_080424FC`, the player's after the action proc unlocks the map); the
  box's HBlank handler (`0x08017880`) turns sprites off on rows 0..0x2C
  (less the box's slide, `0x030030A8`), which hides AW2's panel (rows
  3..34) whole, and the strip (to row 64) would stick out below it.
  The strip is left out too while a build menu (a factory, port or
  airport) or the unit information panel is up (procs `0x0802DA19` and
  `0x0803A441` in IWRAM, found by their two script pointers: a finished
  proc keeps its function word): AW2 keeps its panel at the top and starts
  the list under it (row 34), where the strip would be drawn over the
  list; and the unit picture's 64x64 sprite (OBJ tiles `0x2E8..0x327`,
  loaded for each unit) and its Move / Vision / fuel labels (OBJ palette 5)
  are the very tiles `0x309..0x310` and palette 5 the strip's face
  borrows: with the strip in, a band of the picture was the partner's
  face and the labels were in the partner's colours (checked against the
  same battle with no partner, every unit of all three menus, two and five
  armies: byte for byte the same). On Versus' Teams
  screen a partner slot (the CO's portrait at 30 pixels, or None) under
  each CO, the columns moved up 16 pixels.
- **Versus**, as Dual Strike's: there is no tag rule or tag screen. Dual
  Strike's Versus CO screen (Normal Battle: after the map list) gives every
  army a second CO slot, its COs and a blank; an army with a second CO is a
  tag team, one with the blank plays single (checked in melonDS). Here every
  army's partner slot is under its box on Teams, None by default: START on
  an army's CO stop, UP/DOWN through the COs and None, START again ("Choose
  a partner CO."). Humans and the computer alike: the player picks the
  computer's partner, as in Dual Strike, and the computer then plays the
  pair (Change, both powers, the Tag Power). Five-army games too (Black
  Hole the fifth: five partner slots, OBJ tiles 0x100..0x14F, the five
  armies' partners at state +0xA0..+0xA4). A special pair shows its star
  rating on the partner slot (AW2's own small star tiles, ROM 0x08102C24 /
  0x08102C64).
  In netplay both seats' buttons reach the Teams screen, so both peers
  start with the same pairs.
- **The DS Campaign**: a mission's record names each army's two COs
  (+0x56; `0x1C` the player picks, `0x80 | id` a clone): the computer's
  pairs are formed at map start (`ds_campaign::tag_pairs`); where the
  player has two picks the CO screen takes a second CO (pick count
  `0x0803BD42`, `SetArmyCoIdsFromList` `0x0803BCDC`) and the second is the
  partner (the CO screen's partner row shows its army's emblem and
  badge). **Two fronts** (`two_front.rs`): when the second front is won,
  its winner's CO joins that army on the main front as its partner
  (`two_front::second_front_over` calls `tag::form_pair`; the player's
  army or Black Hole's, as Dual Strike's "The CO will now report back to
  the main front." / "Return to the main front for tag battle."); the map
  menu's pool is left to `two_front` unless a pair needs ours, and
  `SetArmyCoIdsFromList`'s trap is `two_front`'s, which calls
  `tag::set_cos` first.
- **API** (`tag.rs`):
  `tag::form_pair(core, army, co, charge)` gives an army a partner (its
  active CO stays; `charge` the partner's meter in AW2's units; its
  skills are the mode's set); `tag::break_pair(core, army)` takes it away;
  `tag::set_pending(core, army, co, partner)` asks for a pair at the next
  map start. All write RAM only, and only with the pack.
- **Saves**: a suspended game (Versus, the campaigns) keeps the pairs, the
  phase, meters and power counts and the Versus rule Skills past AW2's
  block (`suspend.rs`: "TAG2" at +0xE28, a hash of the block, the rule and
  three spare bytes, 8 bytes an army; the write is made longer only then).
- **Without the pack** nothing of it: the menu, the Rules and Teams
  screens are AW2's and none of this RAM is written (battery and
  `compat_aw2_byte_identical`).
- **Measured in Dual Strike** (melonDS, computer against computer on Bean
  Island, `ds_script`'s `trapprints` at the firepower function's tag term
  `0x020E5D48` and the damage formula's CO bonus `0x020DFB94`, the army's
  pair and phase forced): Andy+Max +10, Andy+Eagle +15, Sami+Eagle +20,
  Andy+Von Bolt -10, Koal+Rachel -35, a 100 pair 0, each exactly the
  compatibility - 100 and in every attack the army made in a Tag Power;
  none with the pair outside a Tag Power (phase 0: the term is never
  called with its flag set) and none on defence (every call from the
  defence path, 1000+ a run, has the flag clear). `tag_boost_pairs` checks
  the whole 28x28 table and a representative set against the damage
  calculator.
- **The tag screens** (`tag_extras.rs`, `tag_screens.rs`): Dual Strike's
  tag screen full screen after the first quote, holding the power's script
  (`sub_08039914`'s quote test, `0x0803991C`) for Dual Strike's length
  (576 frames for a 110% pair, a frame more or less a point), then AW2's
  Super Power screen; Change runs a script of its own (ROM `0x08781400`:
  close the menu, the incoming CO's Dual Strike tag-in line, CO record +0x34
  or +0x38 by the day, in AW2's quote box `sub_08019818`, Dual Strike's CO
  SWAP screen, 191 frames, the swap, `MapMenu_End`); the computer's Change
  the same (ROM `0x08781480`, started from the trap on `AiEndTurnStep`'s
  `EndCurrentArmyTurn` call `0x08061ACE`, which waits until the swap is
  done). Both are animated as Dual Strike's, recorded frame by frame in
  melonDS (`ds_script`: the display registers, OAM and palettes every
  frame; Dual Strike's frames from the menu's choice):
  - *Tag Power*: the map dims and three bolts strike (`SE_TAG_BREAK` 234 at
    173, 209, 219; `BGM_TAG_BREAK_ALLY1` / `_ENEMY1`, 46 / 47, from 256),
    the map whitens (257..288); the screen fades in from white (304..316)
    on the army's emblem on white; the COs, head to foot (the body file,
    128x192 and a 16x192 strip, over the legs file, 128x128 and a strip:
    `ds_co_art::full_figure`), slide in vertically, the active CO down from
    94 pixels above (left, mirrored), the partner up from 94 below
    (304..418, eased); the POWER box rises (373..382,
    `SE_TAGPT_COUNT01_INIT` 235), counts a percent a frame from 384
    (`SE_TAGPT_COUNT01` 236 every second frame), its bar a pixel a percent
    (130 pixels), the bar's fill cycling through a 16-colour gradient every
    4 frames, the box orange from 98%; the bokeh blends in over the emblem
    (431..456, `BLDALPHA` EVA 0 -> 14, EVB 16 -> 4); the digits pop (2x ->
    1x over 8 frames, 495/498/502), the power's name pops a letter every 4
    frames from 16 after the count (`SE_TAG_BREAK_TYPE2` 187 each); the
    emblem goes (627, `SE_TAG_BREAK_EXPLOSE2` 189), a white burst blends in
    additively over the COs (629..644), all fades to white (655..679) and
    the map comes back from white (704..716). After the count the times
    move with the compatibility.
  - *CO SWAP*: the map fades to black (158..170), `SE_SYOGUN_CHANGE` 81
    (176), the red fades in from black (177..201); the incoming CO (as
    stored) comes in from the right and the outgoing CO (mirrored) from the
    left, crossing to stop back to back (209..257); CO★SWAP opens a letter
    every 4 frames from 208, each stretched from a line over 24 frames; the
    COs slide out apart (271..294) under a burst blended in additively
    (268..284), white (295..319), the map back from white (335..347).
  - Neither is skippable in Dual Strike (A, B, START do nothing), nor here.

  The pictures are converted from the .nds at run time:
  `ohashi/res_tagbreak` (the POWER box's sprite cells, LZ77 at +0: bar
  caps and middles filled 0..5 / 0..8 pixels at tiles 0..40, the digits
  0..9 16x16 from tile 42, the box 32x32 at 82 and 16x32 at 98; then raw
  its four palettes, white to orange, and the bar's gradient; then the
  bokeh: LZ77 tiles at +0x380, map at +0x2628, palette the last 32 bytes),
  `res_tagbreak_union` / `_black` / `_mix` (the emblem by the pair's
  sides: tiles, a 32x64 map, two palettes), `res_tagchange` (the Tag
  Power's burst: tiles, a map a screen, three palettes), `res_syogunchange`
  (CO SWAP's burst, three palettes, then a block and a palette whose colour
  1 is the red), `res_tagbreakfont` (the power's name: 32x32 glyphs, A..Z,
  a..z from 32), `res_changefont` (16x32 glyphs, A..Z then the star), the
  COs' full figures (AW2's Sturm, whom Dual Strike lacks: his AW2 body, its
  last row carried on down). The sounds are Dual Strike's, converted with
  the music (`ds_music::tag_se`; their ids read from its code, `mov r0,
  #id` at `0x0205B368`, `0x02058134`, `0x02058098`, `0x02059B94`,
  `0x020593E0`, `0x0205CCBC`), played through AW2's sound-effect call
  `sub_0803B4DC` on the frames Dual Strike plays them (pack version 6; an
  older saved pack has none and the screens play silent). The tag music
  stays AW2's power music.

  On the GBA the screen keeps Dual Strike's pixels, scale and timing, cut
  to the window the COs' heads are in (Dual Strike's two screens' x 8..,
  y 64..; CO SWAP's bottom screen's x 8.., y 8..), the name moved up across
  the COs' chests and the POWER box to the bottom left. It takes the
  display: all of BG VRAM (char block 0 the still layers' tiles, char
  block 2 each frame's, screen blocks 28..31 the maps), BG palettes 6..14,
  the backdrop; sprites and windows off. The Tag Power: BG0 the name and
  the box, BG1 the COs, BG2 the bokeh, BG3 the emblem on white (then the
  burst, raised over the COs); CO SWAP: BG0 the letters, BG1 the burst, BG2
  the COs over the red backdrop. Dual Strike's blends are the GBA's
  (`BLDCNT` / `BLDALPHA`, the same EVA/EVB); its master brightness is the
  palettes moved toward white or black, and on the map AW2's own display
  brightened or darkened (`BLDY`); the bolts are flashes of it (they are a
  layer over Dual Strike's 3D map, not drawn). The scaled letters and
  digits are drawn as Dual Strike's affine sprites scale them (nearest
  pixel, the same steps). A tile both COs share takes a palette of both
  COs' colours. Every frame is a function of the screen and its frame
  count in RAM (`0x0203F502`), written during VBlank, so netplay, rollback
  and replays draw the same, and the battle's random numbers are untouched
  (the same luck and the same computer turn after the 150-frame still
  screen of 0.5.1 and after the animation). What it covers (BG VRAM, the BG
  palettes, the display shadows `sub_08012420` copies) is kept
  at ROM `0x08790000..0x087A042F` and put back. A special pair's win puts
  the pair's exchange (one of its two by the day, the other if only that
  fits) in the results screen's quote box (`GetVictoryQuoteTextId`
  `0x0807A3AC`), the active CO's line alone when neither fits; the quote
  box prints from tile column 16 (`sub_0807A860`), 104 pixels to the
  screen's edge, and AW2's text does not wrap there (a longer line runs on
  into the next row at the screen's left), so every new CO's own victory
  line and the pair exchanges are broken at the words into lines of at most
  104 px and 3 lines, AW2's own longest (`co_new::wrap_quote`,
  `tag_extras::compose_victory`; a pair's line each when both fit, else the
  box's lines shared, else the active CO's alone); the CO page
  (`0x080852A8`, its input `0x08084C90`) gets a TAG page between the Super
  Power's and the unit charts: header "TAG", the CO's special partners,
  each with its rating's full stars (1..3, OBJ tile 0x321 and palette 12
  borrowed). **The CO page shows partners**, as Dual Strike's gives each
  CO of a pair its own tab (RIGHT: the active CO, the partner, the next
  army's; LEFT the other way; checked in melonDS): AW2's page reads its CO
  from the army's player block, so RIGHT on an army with a partner swaps
  its two COs (`tag::swap`: the CO, meter, power count and skills) and
  redraws the page as AW2 does for another army (traps `0x08084DF4` RIGHT,
  `0x08084D50` LEFT, `0x08084E7A` where the page's army change ends,
  jumping to its redraw `0x08084E32`, and `0x08084EE0` the page's close,
  where the swap is undone; `0x080849BC` the page's start is the safety
  net); state `PARTNER_VIEW` +0x10. Text ids 0x7305..0x7307, strings at `0x08781000..`; RAM
  `0x0203F500..0x0203F5D7` (0.5.0 had it at `0x0203F300..`, inside the two
  fronts' store, whose tail it could overwrite).
- **Sturm** (`sturm_pairs.rs`): AW2's Sturm is not in Dual Strike, so
  his pairs are **tangoAW2's own data, made up for tangoAW2** (symmetric,
  with the pack only): Von Bolt 125 (3 stars, "Black Apocalypse"), Hawke
  120 (2, "Storm Front"), Lash 115 (2, "Mad Genius"), Flak 110 (1, "Iron
  Fist"), Adder 110 (1, "Viper's Nest"; the tag font has no apostrophe:
  the top of its `l`), Kindle, Jugger and Koal 105 (no special pair),
  anyone else 95. They go through the same paths as Dual Strike's: the
  Tag Power's firepower, Sturm's TAG page (his five partners) and each
  partner's (Sturm last, after Dual Strike's), the Teams slot's stars, the
  tag screen; victory exchanges written for tangoAW2 (two a direction,
  each line inside the results box's 104 pixels); his tag-in line one of
  AW2's own Sturm power quotes (his CO table row +0x20). His body art on
  the tag screens is AW2's.
- **Left out**: the tag screens' bolts over the map and their drifting
  white specks (flashes of the map stand in for the bolts); the tag music
  (AW2's power music plays); tag skills. Market Crash and other meter
  drains reach only the active CO. The pad bot (`aw2test/bot.py`) fires
  Tag Powers but no longer wins four missions where the computer fights as
  a pair (The Long March, Verdant Hills, Into the Woods, Pincer Strike):
  those win tests are hand-played (skipped), as the two-front ones.
- **Tests:** `tools/aw2test/tests/test_tag.py`: single by default, the
  Rules screen's Skills row, Teams picks and the boxes, Change, meters, the
  Tag Power against the damage calculator (both halves, Max and Andy's
  110), the computer, a Versus suspend, netplay replay, the DS Campaign's
  pairs, pack off; the computer: a pair when the player gives it a partner
  (single with None),
  Change to the CO further from its Super Power, the new CO's CO Power the
  turn after, the Tag Power in Versus and in the DS Campaign's Tag Battle.

## Suspended games (`suspend.rs`)

The map menu's Save (`sub_08016D30`) writes the 0xE28-byte block
`CaptureBattleSaveState` (`sub_08016F38`) fills at `0x02000000`: day, army,
gPlaySt, the weather block, players, units, the tiles changed from the
map's own, the inventions; up to +0xDAC. The rest of the block goes to
Flash but is never read back (`sub_08017208`). With the Dual Strike pack,
tangoAW2's own battle state that lasts past a turn rides there: a mark
("TAW2", version 1) at +0xDAC, the Rules' fog flag kept while rain forces
fog on (`ds_weather`) at +0xDB1, Ex Machina's stun bits (`co_powers`,
pending then held, 40 bytes each) from +0xDB4. Traps: `0x08016D88`
(`sub_08016D30` after the capture, before the write) and `0x08016DD0`
(Continue, `sub_08016DB8` after `sub_08017208`, before a design map's own
slot is loaded over the buffer). Before this, a game continued after
Ex Machina had every marked unit free, and one saved while rain was coming
kept fog on for good once the rain stopped. The sandstorm and the map's
look are in the weather block (`0x03004490` +3), which AW2 saves itself;
Com Towers are counted on the map. Tag pairs and the Versus rule Skills
ride after the block (+0xE28, "TAG2", see CO tag pairs).
Without the pack nothing is written.
Tests: `save_versus_suspend_keeps_ex_machina_stun`,
`save_versus_suspend_in_rain_keeps_fog_rule`.

## Saves

AW2's 64 KiB Flash is 16 sectors of 0x1000 bytes. A sector is one part of a
slot (save tag): "2ars", 0x55/0xAA at +4 and its opposite at +0xFFF, 0x0F
at +5, the sector's 8-bit sum at +6 and its complement at +7 (AW2's check,
`sub_0801B09C`), the generation at +8, the part at +0xC, the slot at +0xD,
the payload's place at +0xE and length at +0x50, the payload from +0x52.
The newest profile's +0xFEF lists every sector's slot (the directory,
`sub_0801B2FC`). The writer (`sub_0801A7D8`) puts a slot's new copy in free
sectors, then a new profile serialized from RAM (`sub_08016B2C`), whose
directory drops the old copy; a delete (`sub_0801ABF8`) only drops the slot
from the directory.

| Slot | What | Written by |
| --- | --- | --- |
| 0 | profile, 0x5CC: unlocks and campaign flags (`0x02028030`), War Room scores (`0x0200C078`, 30 maps), campaign scores (`0x0200C2D0`), options (`0x0200C420`: points, save count, suspend marks +9..+B, options, results; tangoAW2's Survival records +0x15..+0x1E), AW2's world map (`0x0202FDFC`) | every write |
| 2 / 3 / 4 | Campaign / War Room / Versus game saved halfway, 0xE28 (tangoAW2's tail: `suspend.rs`) | map menu Save |
| 5..7 | design maps 1..3, 0x724 (tangoAW2: +0x4C4 the five-army mark, +0x723 the look) | Design Room Save |
| 8 | the design map a saved Versus game is on (its current terrain and units) | map menu Save on a design map |
| 12 | a BH Campaign mission saved halfway (tangoAW2; as slot 14) | map menu Save in a BH mission |
| 13 | the BH Campaign's record, 0x120: progress, unlocked COs, mission records (tangoAW2; "BH Campaign") | BH Campaign New, mission start, after a win |
| 14 | a DS Campaign mission saved halfway (tangoAW2); a two-front mission's second front and two-front state follow the block (two sectors) | map menu Save in a DS mission |
| 15 | the DS Campaign's record, 0x20 (tangoAW2), its records and the CO skills' data | DS Campaign New, mission start, after a win, a skills change |

Twelve slots at most (AW2's ten and the BH Campaign's two; each one sector, a two-front mission two); a write needs a free sector for the slot's new copy and one for the new profile. The Design Room has no
delete for one map: saving over a slot replaces it. The Battle Maps points
(options +0x00, +0x04) grow with every map won, a DS mission's and a
Survival map's too (as the War Room's). A netplay match runs
on player 1's save on both consoles and never writes either player's file
(only single-player sessions persist their save: `tango/src/session/launch.rs`).

**Tests** (`tools/aw2test/tests/test_save_integrity*.py`, `-k save_`; the
Flash read with `aw2test/saveimg.py`, AW2's own rules): every step exports
the Flash before and after and checks that every sector the directory lists
passes AW2's check and that only the expected slots and profile bytes
changed (AW2's save counter aside), then reboots a fresh console from the
written save: Versus saved and continued on 2P, 4P and design maps,
tangoAW2's maps (Wasteland in a sandstorm, Com Towers, Obelisk maps),
a Wasteland design with Dual Strike's units and COs, after Ex Machina, in
rain; Save hidden and nothing written on five-army maps; the Design Room's
three slots (normal and Wasteland, five armies, Black Hole's inventions,
towers of every owner, Dual Strike's units, a full design of 250 units),
every record byte for byte through save, load and reboot, played and saved
in Versus; AW2's campaign (a win, a mission saved and continued, the pack's
profile byte for byte AW2's own); the DS Campaign over an AW2 campaign in
progress (wins, a lab flag, the prologue flag, a mission saved halfway and
continued, a loss, New), AW2's data untouched; the War Room (a score, a
map saved and continued; its list only AW2's maps); Survival (each kind's
record, nothing of the War Room's, a War Room game saved halfway kept);
AW2's completion flags; every mode in one boot; every slot in use at once;
a game saved over netplay the same on both peers.

## Known limits

- Black Hole's unique buildings (Black Cannons and so on) are map
  features; ordinary Versus maps do not have them. Build them in the
  Design Room.
- Campaign and War Room are single-player. Netplay is Versus only.
- The CO screen's unit grid shows what AW2's shows: firepower, move and
  range. Defence (Javier's, Grimm's) and terrain firepower (Koal, Jake,
  Kindle) are not on it; AW2 has 13 bar lengths, so Dual Strike's other
  bonuses show the nearest (below -30 as -30, above 80 as 80).
- The game's mini maps (the map list's preview, the editor's overview)
  have colours for four armies; Black Hole's buildings show there as
  neutral grey. The editor's Intel screen counts the four armies and
  neutral, not Black Hole.
- Com Towers in the Design Room are not counted in the editor's "Surplus"
  (its 60-property limit) nor on its Intel screen (cities, bases, airports
  and ports only); the overview map shows them in their army's colour
  (Black Hole's dark).


### M29 and M30 (`bh_act5.rs`, maps `bh29.txt`, `bh30.txt`)

- **Beams hit friends.** The Laser and the Deathray hit up to four units, nearest first, of *any* army (measured by
  `bh_act5_m29_laser_probe` and `..._deathray_probe`: three Orange and one own unit on the Laser's row lost HP). The
  Deathray (one per map, always at the top) covers columns x..x+2 (x the footprint's left column) from the row
  under its footprint to the map's bottom edge, 8 HP each. Starting layouts keep every friendly off every beam, and
  the intros warn the player (Hawke).
- **AI roles of Orange's units** (`UnitDef::ai`: 0 stays and fires, 1 the enemy HQ, 3 enemy properties, 4 nearest
  enemy units; `.hold()` is role 1): the army pushes (foot soldiers capture, armour, air, indirects and Anti-Air attack, Neotanks and Megatanks go for the HQ). M29 holds nobody; M30 holds only the wall-top and keep infantry and the heavy armour until its release day. Both armies stop buying at the engine's 50-unit cap (M29's 55000+ unspent funds are that cap, not a bug). M31's units hold or march by design; its one port builds a Lander that sits on the port (nothing else to build with 4000 a day). `bh_cpu_m2x_the_enemy_acts` (test_bh_cpu_act5.py) logs moves, roles, captures and funds per day.
- **Start of the battle.** Nothing may be hit before the player moves: a unit starts out of every structure's reach. Measured (M30,
  `bh_act5_m30_cannon_reach_probe`): a Black Cannon reaches roughly nine columns either side of itself and twelve rows up from
  its row; a Laser takes its whole row and column; a minicannon its line. M30's Orange army therefore starts on rows 9 and up
  or in columns 16..20 (checked when the map is painted and by the picture test: every unit at full HP in the Setup phase and
  after the first turn start). The pictures are taken in the Setup phase, before any structure fires.
- **Balance (test bot, `bh_act5_m30_balance_run` and `..._balance_turtle`).** Tuned: Orange starts with 20000 funds and its treasury is
  capped at 6000 each morning (a CPU army rebuilds a few units a day, not to the cap); its heavy armour holds (role 0) until
  day 7 (Md Tanks), 9 (Neotanks) and 11 (Megatanks); its meter is held under the first power's bar except on the power days
  (COP day 5, Super days 9 and 15, `clamp_nell`). Result of the dig-in-then-push bot: Orange 50 to 23 units by day 10, Black Hole
  40 to 16, then 11 on day 15 and 8 on day 24 (Orange 17): the camp holds, the bot cannot push the Great Hall (a human has to).
  Earlier rounds: funds 90000 and no caps (Black Hole 7 units on day 8), 45000/20000 (14 on day 10, lost on day 18), 30000/10000
  (11 on day 10), releasing the Tanks only on day 3 made it worse (14 on day 11).
