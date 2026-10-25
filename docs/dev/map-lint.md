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
| Rule | Level | What | AW2 (179 maps) | DS (256) | Versus (20) | BH (35) | ES (16) |
|---|---|---|---|---|---|---|---|
| RV01 | error | river ends dry against plain, wood, road, pipe or a building: a river runs from a source (map edge or mountain) to the sea | 4 | 3 | 4 | 0 | 0 |
| RV02 | error | a single river cell with no river or water beside it | 0 | 0 | 0 | 0 | 0 |
| RV03 | error | a river that reaches neither the sea or a lake nor the map edge | 4 | 5 | 1 | 0 | 0 |
| RV05 | error | a river ends on land against a mountain: AW2 has no source or end tile, so a river must run from the map edge, the sea, a shoal or a lake to the map edge, the sea, a shoal or a lake | 3 | 2 | 0 | 2 | 0 |
| RV04 | error | a road meets a river with no bridge (road on both sides of a river cell, or a road running into a river's end) | 1 | 0 | 1 | 0 | 0 |
| BR01 | error | a bridge end meets water or a tile no unit can stand on, not ground | 0 | 1 | 0 | 0 | 0 |
| BR02 | warn | a bridge end meets a mountain, a wood, a pipe or a structure: vehicles cannot cross | 35 | 43 | 0 | 0 | 0 |
| BR03 | error | a bridge with no water beside it | 0 | 0 | 0 | 0 | 0 |
| SE01 | error | a one-tile sea or reef with no bridge over it, not at the map edge (a puddle) | 2 | 11 | 0 | 0 | 0 |
| SE02 | warn | shoal that touches no sea, reef or river | 1 | 2 | 0 | 0 | 0 |
| SE03 | error | a sea cell is not drawn with the coast tile AW2's table gives for the land around it | 0 | 0 | 1 | 0 | 0 |
| TJ01 | error | two neighbouring tiles that no AW2 map places side by side (a broken join) | 0 | 107 | 0 | 0 | 0 |
| TJ02 | error | a river, shoal, bridge or sea tile that no game map uses for these neighbours (wrong transition tile) | 0 | 0 | 0 | 0 | 0 |
| TJ03 | warn | a mountain or the plain over it not drawn as the game draws it | 21 | 0 | 0 | 0 | 0 |
| RD01 | warn | a single road tile that joins no road, bridge or property | 12 | 5 | 0 | 0 | 0 |
| RD02 | warn | two road ends one or two tiles apart in line, the gap left plain | 9 | 4 | 0 | 0 | 0 |
| PP01 | error | a pipe tile that opens onto a tile it does not join | 0 | 1 | 0 | 0 | 0 |
| PP02 | error | a pipe seam that is not inside a straight run | 0 | 0 | 0 | 0 | 0 |
| UN01 | error | a unit on terrain its kind cannot occupy | 0 | 0 | 0 | 0 | 0 |
| UN02 | error | two units on one cell | 0 | 0 | 0 | 0 | 0 |
| UN03 | error | a unit boxed in with no free neighbour to move to | 0 | 0 | 0 | 0 | 0 |
| UN04 | error | a unit off the map | 0 | 0 | 0 | 0 | 0 |
| RC01 | error | a property or unit on land that no army or Lander can reach | 0 | 0 | 0 | 0 | 0 |
| RC02 | error | an army cannot reach an enemy HQ it must take | 0 | 0 | 0 | 0 | 0 |
| RC03 | error | an HQ or production property no unit can leave (no ground, or no sea for a port) | 0 | 7 | 1 | 0 | 0 |
| RC04 | error | a Lander with no beach or port to load or unload at | 0 | 0 | 0 | 0 | 0 |
| GB01 | error | a tile id no game map uses (drawn as garbage) | 0 | 0 | 0 | 0 | 0 |
| GB02 | error | a building or structure with part of its footprint missing or wrong | 0 | 2 | 0 | 0 | 0 |
| DQ01 | warn | a long river with no bend: rivers wander | 8 | 9 | 3 | 13 | 0 |
| DQ02 | warn | most mountain or wood patches are exact rectangles: drawn blocks, not terrain | 1 | 2 | 1 | 13 | 0 |
| DQ03 | warn | blocks of parallel identical rows of mountains or woods: the procedural look | 1 | 2 | 0 | 5 | 0 |
| DQ04 | warn | too little of the land is anything but plain: empty fields and decorative filler | 6 | 12 | 8 | 1 | 0 |
| DQ05 | warn | a big empty plain field: a dead corner | 0 | 5 | 1 | 1 | 0 |
| DQ06 | warn | a very long straight road with no bend or junction | 1 | 2 | 0 | 3 | 0 |
| DQ07 | warn | an army's units start as a solid block (a blob, not a formation) | 0 | 0 | 0 | 6 | 0 |
| DQ08 | warn | a property with no road or other property near it: no reason to go there | 3 | 10 | 3 | 1 | 0 |
| DQ09 | warn | an HQ in a pocket: little walkable ground around it | 4 | 9 | 0 | 0 | 0 |
| DQ10 | warn | a Lander with too few shore cells to unload on | 0 | 0 | 0 | 0 | 0 |
| RN01 | error | a river, shoal, bridge or coast tile drawn in the game's picture in a way none of the games' drawings of that tile and 4-neighbour class is (`aw2dev maps render-check`) | 0 | 0 | 0 | 0 | 0 |
| DQ12 | warn | a long straight line of mountains away from the map edge: a drawn wall, not a range | 9 | 10 | 0 | 5 | 0 |
| DQ11 | warn | a map meant to be fair (Versus, or a `fair` line) with unequal properties per army | 0 | 0 | 0 | 0 | 0 |
| SP01 | warn | not enough room to fight: too many units for the walkable ground or for the frontage between the sides | 0 | 0 | 0 | 7 | 0 |
| ES01 | error | Black Hole's inventions on an Emerald Sun map that is not one of the (at most two) missions against Black Hole (the map file's `blackhole` line) | 0 | 0 | 0 | 0 | 0 |

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

## Design quality ("bad game design"): `maplint/design.py`
The integrity rules ask whether a map is *broken*; these ask whether it looks machine-made or plays cramped. All are warnings (the Emerald Sun maps are held to them: a
DQ.. or SP.. finding fails `maps lint --source es`; the BH Campaign's and Versus maps only report). Every threshold (`design.LIMITS`) sits where AW2's and Dual Strike's own
maps (435 of them) almost never go; the unit rules are calibrated on the BH Campaign's 35 maps, the only source with unit positions in the files.

| Rule | Measures | Limit | Games' hits (AW2 / DS / BH) |
|---|---|---|---|
| DQ01 | a river of 10+ cells with no bend (bends per 10 cells: AW2 median 1.5) | 0 bends | 8 / 9 / 13 |
| DQ02 | mountain or wood patches (6+ cells) that are exact rectangles: 3+ and half of them | 3 | 1 / 2 / 13 |
| DQ03 | blocks of 3+ parallel runs of 4+ identical mountain or wood cells | 3 blocks | 1 / 2 / 5 |
| DQ04 | share of land that is not plain (AW2 p10 .43) | .36 | 6 / 12 / 1 |
| DQ05 | the largest empty plain window (AW2 p99 5) | 6 | 0 / 5 / 1 |
| DQ06 | a straight road run with no bend (AW2 max 27) | 27 | 1 / 2 / 3 |
| DQ07 | an army's units as a solid rectangle (9+ cells), or 10+ units filling 75% of their box | 9 | - / - / 6 |
| DQ08 | a property with no road or property within 5 cells (HQs excepted) | - | 3 / 10 / 1 |
| DQ09 | an HQ with fewer than 7 walkable cells within 2 | 7 | 4 / 9 / 0 |
| DQ10 | a Lander with fewer than 6 shore cells to unload on | 6 | 0 / 0 / 0 |
| DQ11 | Versus (or `fair`) maps with unequal properties per army (more than a third apart) | 1.34 | 0 / 0 / 0 |
| SP01 | room to fight: units per vehicle-walkable cell, and the smaller ground side's units per cell of the narrowest frontage between the sides; no vehicle crossing at all | .17 and 1.25 | - / - / 9 |

Room to fight (SP01): the density is all units over all cells a vehicle can drive on (BH Campaign: .07 to .23, median .12). The frontage runs the axis between the two strongest
sides' unit centroids and counts, at nine points between 30% and 70% of it, the cells (any ground a foot soldier can cross) within half a cell of the perpendicular; the units of the smaller
side divided by the narrowest count must not pass 1.25 (BH median .8). Fleets and air wings are exempt (they cross water and sky): the rule looks at maps where ground units are 60% or more.
For the Emerald Sun maps the aim is stricter than the limits: density .12 or less, so a 40-unit army has room to flank and to put its artillery behind a line.

Calibration, what was tried: the mirror symmetry of a map is no sign of a machine (a quarter of AW2's own maps are mirrored, 19 of 20 Versus maps), so it is not a rule. Diagonal neighbours for
river, road and shoal tile choice (to catch a wrong autotile the 4-neighbour key misses) found 4409 distinct contexts in the games' maps and would flag hand-made Versus maps by the dozen:
the learned 4-neighbour key of TJ02 stays the check of what the game draws (the picture of a cell is a function of its tile id alone: the review pictures of
`aw2dev campaign sheets` are the render check by eye).

## The river rule (RV05), and the render check (RN01)
- **Both ends of every river reach the map edge, the sea, a shoal or a lake.** AW2 has no river source or end tile, so a river that stops on land always looks cut off, and a mountain "spring" is no exception
  (RV01 already refused plain, wood, road, pipe and buildings; RV05 refuses a mountain). AW2's and Dual Strike's own maps break it in 3 + 2 of 435 (about 1%): `aw2_69`, `aw2_7A`, `aw2_92`, `ds_07D`, `ds_099`.
  It is an **error** for the BH Campaign, the Emerald Sun Campaign and Versus. The BH Campaign trips it in `bh10` and `bh31`, Versus in none; the user has not approved changing the BH maps, so those two are
  listed in `rules.KNOWN` (reported by every lint, not failing the suite; nothing may be added there for an Emerald Sun map). Emerald Sun: M1, M2, M3, M13 (two), M14 and M16 broke it; each river now starts in a
  small lake (`Canvas.lake`: the map builder draws a river mouth only on a straight shore, so the lake has a flat 3-cell shore row at the river's end) or runs to the edge.
- **Render check (RN01), `aw2dev maps render-check [--source es|bh] [--pictures DIR] [--corpus DIR ...]`.** For river, shoal, bridge and coast tiles only: every cell of the game's own picture of a map (the
  `m<N>_full.png` pictures of `aw2dev campaign sheets` or `maps boot`, 16 pixels a cell, no unit on the cell) is compared with the drawings the reference pictures have of the same tile id, 4-neighbour class
  (`rules.trans_key`), shade (a tall neighbour on its left) and look (the plain's colour). The pixels all reference drawings agree on must agree; water is animated, so a cell is flagged only when more than 30%
  of those pixels differ (a wrongly drawn tile differs in most of them; a phase of the animation in a few). The reference is the BH Campaign's 35 pictures (`maps boot`, about 8 minutes) and, for Emerald Sun, the
  other Emerald Sun pictures. A key with fewer than 6 reference drawings has no verdict. Result: 0 findings in the BH and Emerald Sun pictures. A planted wrong drawing is flagged by the unit test.
  The diagonal-neighbour variant (which flagged hand-made maps) is not used.
- **DQ12:** a straight line of 11 or more mountains away from the map edge (AW2 and Dual Strike have one in about 5% of their maps). `Canvas.ragged` breaks such lines.

## Armies and reachability (AR01 to AR03)
- **AR01** two armies of a map wear the same colour; **AR02** an army has more than one HQ. Errors for the BH Campaign, Emerald Sun and Versus (0 hits in AW2's and Dual Strike's own maps; the BH Campaign has `bh30`, two HQs for one army, kept in `rules.KNOWN`; Versus none). The mission side is checked by `aw2dev campaign check` and the Rust test `no_two_armies_share_a_colour`.
- **AR03** a missile silo or an airport must be reachable on foot from some HQ (a port or a Lander lets infantry cross water and land on any shore). AW2 breaks it in 12 of 179 maps, Dual Strike in 24 of 256, BH, Versus and Emerald Sun in none. A silo is AW2's own terrain (tile 0x180), so ES01 no longer counts it as a Black Hole invention.

## Pipelines, ports (PP03, PP04, PT01) and the port audit
- **PP03** a pipeline must be infrastructure: 6 or more cells (a wall with gates of up to 3 cells counts as one line) and no end hanging in open terrain: every end stops at the map edge, the sea, a river, a mountain, a gate, or a building or structure it feeds. **PP04** the seam of a barrier pipeline must change something: broken, it joins ground that was cut off, or shortens the way between two HQs by 6 cells or more (a supply line's seam, one that ends in a base or factory, only cuts the feed). Warnings everywhere; failing for Emerald Sun maps. AW2 and Dual Strike pipes mostly break them (15 of 18 and 43 of 50 maps with pipes: the games end pipes in open ground all the time), so the rule is this campaign's taste, not the games'. The supply pipe of a Black Hole factory or cannon is exempt.
- **PT01** every port touches navigable sea of a body of 12 or more cells (AW2's smallest is 23, Dual Strike's 16, the BH Campaign's 14); on a wasteland map (look 3, read from the mission's Rust `m.look`) the water is lava and no ship sails there. Error. Findings: Emerald Sun M9 (2 ports) and M13 (5 ports) on lava, Versus `Crystal Isles` (3 ports with no sea: kept in `rules.KNOWN`); BH none.
- **`aw2dev maps ports [--source es|bh|versus]`** prints every port (map, army digit or N neutral, cell, water, OK or FIX).

