# Map integrity: `aw2dev maps`

`aw2dev maps lint` finds what makes a map look or play broken before a player does: unfinished rivers, puddles, joins the game never draws, bridges that end
in water, units on ground they cannot stand on, properties nobody reaches, tiles the game would draw as garbage. It reads the user's ROMs at run time and stores
nothing from them. Code: `devkit/aw2/commands/maps.py` (CLI), `devkit/aw2/maplint/` (`load.py` sources, `terrain.py` tile -> terrain, `rules.py` the rules,
`spawns.py` units the BH missions place from Rust, `render.py` pictures, `test_maplint.py` tests). Skill: `.claude/skills/aw2-map-lint`.

## Commands
| Command | What |
|---|---|
| `aw2dev maps lint [--source bh\|versus\|aw2\|ds\|all] [--map NAME ...] [--rule ID ...] [--warn] [--png DIR \| --no-png] [--json]` | lint the BH Campaign's maps (default), tangoAW2's Versus maps, AW2's own (ROM) or Dual Strike's (the .nds); one line per problem (rule id, level, cell, text); an annotated picture per map in `devkit/work/maps/lint/<source>/` (errors red, warnings amber, rule list beside the map); exit 1 on an error in a bh / versus map (AW2's and DS's own hits are reference, only reported) |
| `aw2dev maps rules [--md]` | every rule with the number of maps of each source that trip it: what the games themselves do |
| `aw2dev maps compare --base REV [--out DIR]` | BH maps at git REV against the working tree: tiles changed per map and a before / after picture (changed cells outlined white) |
| `aw2dev maps boot [--mission N ...]` | enter BH missions in the offline harness (`tools/aw2test` `bh_review_m*`) and keep the game's own whole-map picture of each: the proof that a mission loads |

`aw2dev suite` runs `maps lint` (BH maps clean) and `aw2dev test python` runs `test_maplint.py` (a planted map for each rule, the same map finished properly, the
BH maps clean, AW2's own maps quiet on the rules learned from them).

## How the rules know what the games allow
Ground truth is the games' own maps: AW2's 179 map-table entries (`load.aw2_maps`: the table at `0x085C77A0`, 0xC0 rows of 0x5C bytes, LZ77 tiles) and Dual Strike's 256
(`load.ds_maps`: overlay 0's header table `0x022DBD28`, 0xA0 bytes a map, tiles at +0x44; Dual Strike's extra tile ids converted as `ds_maps.rs: convert_tile`).
Every tile is read as a terrain character (`terrain.py`) from the ROM's terrain-class table (`0x080C1BC4`, class in the low 5 bits: 1 plain, 2 river, 3 mountain,
4 wood, 5 road, 7 sea, 12 bridge, 13 shoal, 15 pipe, 16 seam, 19 reef, 17 silo) and ranges for properties (`0x1B4..0x1DD`) and inventions (`0x180..0x1B3`).

Tables found in the ROM and used:
- **The sea-edge table** at file offset `0x485DC4` (512 `s16` tile ids, indexed by the 3x3 mask of which neighbours are land): the Design Room's coast auto-tiler. `five/map.py sea_edges`
  reads it; rule SE03 checks every sea cell of a map against it (AW2's own maps agree with it everywhere except the river mouths, which use their own tiles, `map.RIVER_INTO_SEA`).
- **No other transition table exists in the ROM data**: the Design Room draws roads, rivers, shoals and bridges with code, not tables. Their transition tiles are LEARNED from the
  games' maps (`rules.learned`, `trans_key`): for each river / bridge / shoal cell the tuple of what lies N, E, S, W (river, sea, bridge or road, other) -> the set of tiles
  the games draw there. TJ02 flags a tile outside that set. `five/tilecheck.py` learns every neighbour tile pair the games place (TJ01) and how mountains are drawn (TJ03).
- Wide bridges: the games draw a bridge two or more lanes wide with 0x13 (crossing east-west, `Sea Fortress`) or 0x16 (crossing north-south); a single lane crossing north-south is 0x36.
  `five/map.py water_tile` follows this since the BH Campaign's 3-wide bridge of M29 was drawn with 0x36 on every lane (a TJ02 hit).

## The rules (hits per source: how many maps of each trip it)
| Rule | Level | What | AW2 (179 maps) | DS (256) | Versus (20) | BH (35) |
|---|---|---|---|---|---|---|
| RV01 | error | river ends dry against plain, wood, road, pipe or a building: a river runs from a source (map edge or mountain) to the sea | 4 | 3 | 4 | 0 |
| RV02 | error | a single river cell with no river or water beside it | 0 | 0 | 0 | 0 |
| RV03 | error | a river that reaches neither the sea or a lake nor the map edge | 4 | 5 | 1 | 0 |
| RV04 | error | a road meets a river with no bridge (road on both sides of a river cell, or a road running into a river's end) | 1 | 0 | 1 | 0 |
| BR01 | error | a bridge end meets water or a tile no unit can stand on, not ground | 0 | 1 | 0 | 0 |
| BR02 | warn | a bridge end meets a mountain, a wood, a pipe or a structure: vehicles cannot cross | 35 | 43 | 0 | 0 |
| BR03 | error | a bridge with no water beside it | 0 | 0 | 0 | 0 |
| SE01 | error | a one-tile sea or reef with no bridge over it, not at the map edge (a puddle) | 2 | 11 | 0 | 0 |
| SE02 | warn | shoal that touches no sea, reef or river | 1 | 2 | 0 | 0 |
| SE03 | error | a sea cell is not drawn with the coast tile AW2's table gives for the land around it | 0 | 0 | 1 | 0 |
| TJ01 | error | two neighbouring tiles that no AW2 map places side by side (a broken join) | 0 | 107 | 0 | 0 |
| TJ02 | error | a river, shoal, bridge or sea tile that no game map uses for these neighbours (wrong transition tile) | 0 | 0 | 0 | 0 |
| TJ03 | warn | a mountain or the plain over it not drawn as the game draws it | 21 | 0 | 0 | 0 |
| RD01 | warn | a single road tile that joins no road, bridge or property | 12 | 5 | 0 | 0 |
| RD02 | warn | two road ends one or two tiles apart in line, the gap left plain | 9 | 4 | 0 | 0 |
| PP01 | error | a pipe tile that opens onto a tile it does not join | 0 | 1 | 0 | 0 |
| PP02 | error | a pipe seam that is not inside a straight run | 0 | 0 | 0 | 0 |
| UN01 | error | a unit on terrain its kind cannot occupy | 0 | 0 | 0 | 0 |
| UN02 | error | two units on one cell | 0 | 0 | 0 | 0 |
| UN03 | error | a unit boxed in with no free neighbour to move to | 0 | 0 | 0 | 0 |
| UN04 | error | a unit off the map | 0 | 0 | 0 | 0 |
| RC01 | error | a property or unit on land that no army or Lander can reach | 0 | 0 | 0 | 0 |
| RC02 | error | an army cannot reach an enemy HQ it must take | 0 | 0 | 0 | 0 |
| RC03 | error | an HQ or production property no unit can leave (no ground, or no sea for a port) | 0 | 7 | 1 | 0 |
| RC04 | error | a Lander with no beach or port to load or unload at | 0 | 0 | 0 | 0 |
| GB01 | error | a tile id no game map uses (drawn as garbage) | 0 | 0 | 0 | 0 |
| GB02 | error | a building or structure with part of its footprint missing or wrong | 0 | 2 | 0 | 0 |

Levels: **error** = AW2 and Dual Strike do it in at most a few percent of their maps (the rule's hits there are listed above, they are the games' own slips or deliberate shapes;
`aw2dev maps lint --source aw2 --rule RV01` names them); **warn** = the games do it regularly, reported with `--warn` only (bridge ends in woods, single road tiles, mountains drawn
differently). An error in a tangoAW2 map fails `aw2dev maps lint`, the suite and the tests.

What each rule looks at (all on tiles, so the same code reads a text map, a Versus map and a ROM map):
- **Rivers.** A river cell that has no river or water beside it is RV02. A river end with one wet neighbour is a source: allowed against the map edge or a mountain (a spring);
  against a lake or the sea it is a mouth; against plain, wood, a road, a pipe or a building it is RV01. A river whose cells touch neither the sea / a lake / a shoal nor the map
  edge is RV03 (it starts and ends nowhere). A road on both sides of a river cell, or a road running into a river's end, is RV04: the road needs a bridge (`=`), and the river goes on
  under it.
- **Bridges.** BR01: an end that meets sea, reef, river or an unknown tile (a shoal is a ford and fine); BR02 (warn): an end in a mountain, wood, pipe or structure; BR03: a bridge
  with no water beside it (a lane of a wide bridge counts the water at the edge of the lanes).
- **Sea and shoal.** SE01: a one-tile sea or reef that no bridge crosses and that is not at the map edge (the games do two-cell ponds and bridge lattices, never a lone puddle);
  SE02 (warn): a shoal touching no water; SE03: a coast tile that is not the sea-edge table's for the land around it.
- **Joins and garbage.** TJ01 / TJ02 / TJ03 above; GB01: a tile id no game map uses; GB02: a Black Hole structure (Black Cannon, Factory, Volcano, Deathray, Obelisk) with part of its
  footprint missing.
- **Roads and pipes.** RD01 (warn): a single road tile; RD02 (warn): two road ends in line one or two plain tiles apart; PP01: a pipe tile that opens onto a tile it does not join;
  PP02: a seam outside a straight run. Dead-end roads are NOT a rule: the games end roads against plain, wood, mountains and the sea all the time (measured: 54 plain, 54 wood, 19 mountain
  ends in 179 maps).
- **Units** (BH maps: the `unit` lines of the map file and every `UnitDef::new(army, unit::KIND, x, y)` a mission places from `bh_act*.rs`: reinforcements, paratroopers, scripted columns;
  a second-front pair `bh08` / `bh08b` is checked against both maps, a unit must fit at least one): UN01 on terrain its kind cannot occupy (`bhmap.py passable`: foot, tires, treads, sea,
  Lander, air), UN02 two on one cell (a spawn on a unit of the map file), UN03 boxed in, UN04 off the map.
- **Reachability** (`bhmap.py check_reach`): RC01 land with properties or units no army or Lander reaches, RC02 an army that must take an enemy HQ and cannot by land, Lander or aircraft,
  RC04 a Lander with no beach or port to load or unload at. RC03: an HQ, base or airport with no ground beside it, a port with no sea beside it.

## Fixing a BH map
Edit `tango-gamesupport-aw2/five/bh/bh*.txt` (legend: `docs/dev/maps.md`), `python3 tango-gamesupport-aw2/five/bhmap.py "<aw2.gba>"` (it runs `tilecheck` and the reachability checks and
writes `src/bh_map_data.rs`), `aw2dev maps lint`, `aw2dev build --examples` and `aw2dev maps boot --mission N` to look at the game's own picture. Keep the mission's design: a river that a road cuts
becomes a bridge on the road cell and runs on to the edge; a spring with no outlet gets a mouth at the map edge; a spawn that lands on shoal moves to the nearest legal cell
(`bh_act*.rs`).

## BH Campaign, October 2026 pass (what the first run found)
Before: bh07 (two aircraft on one cell), bh10 (a river from mountain to mountain with no outlet), bh19 (a river cut into four by three roads with no bridge, ending dry), bh21 (the same, twice, and a
road crossing with no bridge), bh29 / bh30 (3- and 2-wide bridges drawn with the single-lane tile), bh31 (a river cut by a road), M20's Carrier spawned on a shoal. All fixed; the other 25 maps were clean.
Limits: the linter reads a map as its tiles; mission-level data that is not a literal (computed spawn cells) is not checked, and fairness (distance, funds) is not a rule.
