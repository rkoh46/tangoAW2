# Map design principles (`aw2dev maps study`, rules MD01 to MD08)

How a good Advance Wars map is built, measured on the community's best maps and turned into numbers our maps are held to. The model is
**Advance Wars By Web's Hall of Fame** (the maps its players voted the best): 23 two-player Hall of Fame maps, and, because the Hall of Fame has no
three- to five-player map, the 20 four-player maps ranked S or A. They are the creators' work under their copyright: we fetch them for study into a
scratchpad, measure them, look at them, and **never copy a layout or a grid into the repo**. The same measures run on AW2's own maps (179), Dual
Strike's (256), our Versus maps (20), the BH Campaign (35) and the Emerald Sun Campaign (16), so every number below has the games beside it.

Code: `devkit/aw2/maplint/study.py` (the measures, AWBW's terrain ids, pictures), `devkit/aw2/maplint/principles.py` (the rules MD01..MD08),
`devkit/aw2/commands/maps.py` (`maps study`). Tests: `devkit/aw2/maplint/test_study.py`. Skill: `.claude/skills/aw2-map-lint`.

## The command
`aw2dev maps study [DIR] [--source es bh versus aw2 ds] [--map NAME ..] [--rows] [--png DIR] [--json FILE]`
- `DIR`: a folder of AWBW study files: a `# <id> players=N size=WxH [name=...] cats=...` line, then the map's CSV rows of AWBW terrain ids
  (AWBW's `text_map.php?maps_id=N`). Fetch politely (one request at a time, a pause between) into a scratchpad. A `README.md` table `| id | name |` names them.
- `--source`: our maps and the games' (read from the ROMs at run time).
- Prints the 10th percentile / median / 90th percentile of every measure per set, the share of maps with each feature, and how many maps of each set trip
  each principle rule; `--rows` one line per map, `--png` a picture per map in our own colours (keep AWBW pictures in a scratchpad), `--json` everything.

AWBW terrain ids, confirmed against AWBW's own pages (the preview's tile names, the map API's country codes): 1 plain, 2 mountain, 3 wood, 4-14 river,
15-25 road, 26-27 bridge, 28 sea, 29-32 shoal, 33 reef, 34-37 neutral city / base / airport / port; 38-57 and 81-100 the first eight armies in groups of
five (city, base, airport, port, HQ); 101-110 pipe, 111 silo, 112 fired silo, 113-114 seam, 115-116 broken seam; 117-126 Amber Blaze and Jade Sun in
groups of five (airport, base, city, HQ, port); 127-137 com towers (133 neutral); 138-148 labs (145 neutral, the rest by army in alphabetical order);
from 149 the later armies in groups of seven (airport, base, city, com tower, HQ, lab, port), 195 the teleport tile. Some four-player maps have labs
instead of HQs: the study seats an army at its lab then.

## The numbers (p10 / median / p90)
| Measure | AWBW HoF 2P (23) | AWBW S/A 4P (20) | AW2 (179) | Dual Strike (256) | BH Campaign (35) | Emerald Sun before (16) | Emerald Sun after (16, with the 12% cut) |
|---|---|---|---|---|---|---|---|
| properties per 100 cells | 9.5 / 11.5 / 13.7 | 10.4 / 13.2 / 15.2 | 4.0 / 8.4 / 13.3 | 2.4 / 8.5 / 13.5 | 2.4 / 4.6 / 5.9 | 1.7 / 2.2 / 3.0 | 4.1 / 5.2 / 7.2 |
| properties per 100 land cells | 10.3 / 12.3 / 15.0 | 10.9 / 13.9 / 16.0 | 5.3 / 11.6 / 22.7 | 4.2 / 11.5 / 21.9 | 2.4 / 4.9 / 10.6 | 1.9 / 2.6 / 4.2 | 5.2 / 6.0 / 8.3 |
| nearest property (cells, median) | 3 | 3 | 2 | 2 | 3 | 4 | 3 |
| farthest ground from any property | 2 / 2 / 3 (max 5) | 2 / 2 / 3 | 3 / 4 / 7 | 3 / 4 / 7 | 3 / 5.5 / 9 | 7 / 10 / 11.5 | 4 / 5 / 6 |
| cities / bases / airports / ports (share) | .70 / .14 / .05 / 0-.11 | .64 / .14 / .06 / 0-.09 | .57 / .25 / 0-.17 / 0-.14 | .55 / .23 / 0-.15 / 0-.13 | .66 / .17 / .03 / 0-.2 | .52 / .16 / .07 / .07 | .80 / .10 / .02 / 0-.08 |
| neutral share of the properties | .83 / .86 / .89 | .73 / .81 / .83 | .18 / .50 / .67 | 0 / .48 / .68 | .17 / .33 / .49 | .19 / .30 / .51 | .60 / .72 / .80 |
| income per side on day 1 | 3000 (HQ + 2 bases) | 3250 | 6500 | 6000 | 7500 | 5750 | 7000 |
| HQ to HQ (cells, Manhattan) | 10 / 16 / 22 | 6 / 15 / 25 | 8 / 19 / 32 | 7 / 17 / 28 | 17 / 21 / 35 | 19 / 30 / 40 | 19 / 30 / 40 |
| base to base (tank moves) | 15 / 18 / 30 | 5 / 14 / 19 | 11 / 21 / 40 | 9 / 21 / 36 | 13 / 19 / 27 | 19 / 25 / 34 | 19 / 25 / 34 |
| days an enemy infantry needs to reach your base | 4 / 5.5 / 8 (min 3.5) | 2 / 3 / 6 | 4 / 6 / 12 | 2 / 6 / 10 | 5 / 7 / 9 | 4 / 8.5 / 11 | 4.4 / 8 / 11.8 |
| roads crossing the middle (approach roads) | 1 / 3 / 3 | 1 / 2 / 4 | 0 / 1 / 2 | 0 / 1 / 2 | 1 / 3 / 4 | 0.5 / 3 / 3 | 1 / 3 / 4 |
| walled-off lanes (split by mountains, water, rivers) | 1 / 1 / 3 | 1 / 1.5 / 3 | 1 / 2 / 3 | 1 / 2 / 3 | 1 / 1 / 3 | 1.5 / 2 / 3 | 1 / 2 / 3 |
| narrowest single corridor (if the only way) | never under 8 | never under 8 | 0 in 5 maps | 0 in many | 0 in 4 | 1 (the sea maps) | never under 6 on land |
| forward bases (35%+ of the way to the enemy) | 2 / 6 / 6 | 6 / 8 / 12 | 0 / 3 / 11 | 0 / 3 / 11 | 0 / 0 / 3 | 0 / 1 / 3 | 0.5 / 2 / 4 |
| a property in the middle between the sides | 100% of maps | 95% | 65% | 57% | 83% | 75% | 100% |
| plain / wood / mountain (share of land) | .31 / .11 / .08 | .33 / .10 / .06 | .39 / .15 / .05 | .36 / .13 / .04 | .45 / .13 / .10 | .55 / .07 / .12 | .52 / .10 / .11 |
| road / river / shoal (share of land) | .15 / .03 / .08 | .15 / .04 / .08 | .14 / .01 / 0 | .13 / 0 / .02 | .16 / .02 / 0 | .13 / .03 / .01 | .15 / .03 / .01 |
| river cells per bridge | 1.5 / 2.4 / 6.3 | 0.5 / 1.7 / 4 | 1.9 / 6.3 / 15 | 2 / 5.8 / 17 | 3.9 / 6.9 / 10.5 | 7.9 / 9.7 / 13.7 | 4.5 / 7 / 8.7 |
| longest river with no crossing | max 9 (p90 8) | p90 6 | p90 10 | p90 8 | p90 8 | 0 / 11.5 / 15 | 0 / 7 / 9 |
| coast that is beach (shoal) | 0 / .45 / .82 | .21 / .40 / .61 | 0 / .10 / .47 | 0 / .16 / .54 | 0 / .07 / .69 | 0 / .57 / .93 | 0 / .69 / 1 |
| properties with a road within 2 cells | .65 / .83 / 1 | .78 / .92 / 1 | 0 / .81 / 1 | 0 / .70 / 1 | .62 / .87 / 1 | .74 / .86 / 1 | .66 / .76 / .86 |
| maps with com towers / silos / pipes / airports / ports / rivers | 78 / 61 / 39 / 91 / 39 / 65% | 85 / 80 / 75 / 90 / 40 / 80% | 3 / 19 / 10 / 44 / 34 / 55% | 18 / 24 / 20 / 41 / 32 / 48% | 11 / 3 / 23 / 51 / 29 / 60% | 6 / 38 / 31 / 75 / 56 / 81% | 6 / 38 / 25 / 75 / 38 / 75% |

(The four-player maps' teams are not in the grid: the study pairs the seats of a "2v2" map by mutual nearness and treats the rest as free-for-all, so
their distance and base-safety rows are rougher.)

## What the best maps do (the principles)
1. **Properties everywhere, close together.** 10 to 16 properties per 100 land cells, the nearest one 3 cells away, no ground more than 5 cells from a
   property (median 2). Cities are 64-70% of them, bases 14%, airports 5%, ports only on naval maps. A property is a reason to move, cover (a city defends
   like a wood) and income: the map is a field of objectives, not a field with a few objectives on it.
2. **Most of it is neutral and contested.** 80-86% of the properties start neutral; each side starts with its HQ and two or three bases (3000 a day).
   The neutral ones split evenly between the sides (a city is as near to one side as the mirror city is to the other) and a property always stands in the
   middle: the game is a race to capture outward, then a fight over the middle.
3. **Production forward.** Two to six bases sit a third or more of the way to the enemy (neutral, to be captured): a front that moves needs factories near
   it. An enemy infantry needs four or more days to reach your base (never fewer than 3.5): no base falls to a day-one rush.
4. **One wide front with texture, not walled lanes.** The maps are rarely cut into separate lanes by walls (median one walled lane); the front is the
   whole width of the map (17 to 19 cells), and woods, mountains, cities and rivers give it texture: small patches of 1 to 4 cells, scattered, so every
   advance has cover a few cells ahead and every line has a gap. Two to four roads cross the middle (the approach routes). A single narrow corridor as the
   only way between the sides does not occur (never under 8 cells).
5. **Terrain mix.** About a third of the land is plain (.31; never over .52), a tenth wood, a twelfth mountain, a seventh road, a few percent river.
   Plain is the open ground between cover, not the background.
6. **Roads join things.** Many short road pieces (median 8 on a 20x20 map), each linking a cluster of cities, a base and a bridge; 83-92% of the
   properties have a road within 2 cells. There are no roads that go nowhere and few long straight highways.
7. **Rivers are crossed often.** A bridge for every 2 river cells (median); no river runs more than 9 cells with no bridge or ford. Rivers frame the
   field and make bridgeheads, they do not wall it off.
8. **Coasts are beaches.** 40-45% of the coast is shoal: landings everywhere. Naval maps (ports on 39-40%) give the fleets open sea and ports facing it.
9. **Air and special terrain are common and balanced.** Airports on 9 of 10 maps (one each, or a neutral one in the middle); com towers on 8 of 10 (in
   the middle, contested); silos on 6 of 10 (mostly fired ones used as cover); pipes on 4 of 10 as borders and walls with a seam to break.
10. **Shapes vary.** Rectangles are framed by sea, pipes, mountains or a ring; HQs sit in corners, on edges, or in the middle; the field is mirrored
    (left-right, diagonal or rotational) for fairness.

AW2's and Dual Strike's own maps (the campaign and versus maps together) agree with most of this but are sparser at the low end (a tenth of them under
5.3 and 4.2 properties per 100 land cells) and leave more open plain (p90 .53): the campaign maps are asymmetric and often a fortress or a sea crossing.

## For the Emerald Sun Campaign (asymmetric maps)
A campaign map is the player against the mission's enemies, never mirrored, but the craft is the same. The targets for the Emerald Sun maps:
- **Properties:** 5 or more per 100 land cells (aim 6 to 9), no ground more than 6 cells from a property (aim 4 or 5), most of them neutral in the
  contested middle, the enemy's own in its zone, the player's at its landing or camp. Each property has a job (income, a forward base, cover on a road,
  an airport for the answer to an air threat, a port facing open sea).
- **A front, not a maze:** two to four approach roads between the player and each enemy, no single corridor under 6 cells as the only way (a fortress
  has two or three gates), the middle textured with small woods, hills and cities; something to fight over in the middle (a city cluster, a neutral base or
  airport, a com tower, a silo).
- **Terrain:** plain at most 53% of the land (aim 35 to 45%), woods 10-15%, mountains 6-12% (ranges, not walls), roads 12-16%.
- **Rivers** reach the edge, the sea or a lake at both ends (RV05) and have a bridge or ford at least every 10 cells.
- **Beaches** long on every landing coast (40% or more shoal); ports only on navigable sea (PT01).
- **Safety:** an enemy infantry needs two or more days to reach the player's base or HQ (and no enemy foot soldier starts within a day of them).
- **Room** (SP01): units per vehicle cell .12 or less.

## The rules (warnings everywhere; failing for the Emerald Sun maps, like the DQ rules)
| Rule | Measures | Limit | AWBW 2P / 4P | AW2 / DS | BH / Versus | ES before | ES after |
|---|---|---|---|---|---|---|---|
| MD01 | properties per 100 land cells (maps of 60+ land cells) | at least 5 | 0 / 0 | 17 / 34 | 19 / 1 | 15 | 0 |
| MD02 | the farthest ground cell from any property (Chebyshev; the inside of a mountain mass excepted) | at most 6 | 0 / 0 | 20 / 30 | 11 / 0 | 15 | 0 |
| MD03 | the only way across a cut between two sides is one corridor (cuts mostly over water: a naval front, skipped) | at least 6 wide, or two ways | 0 / 0 | 9 / 15 | 0 / 0 | 0 | 0 |
| MD04 | days an infantry from an enemy base needs to reach your base or HQ; an enemy foot soldier starting a day from it | at least 2 | 0 / 3* | 1 / 1 | 0 / 0 | 0 | 0 |
| MD05 | a property within a fifth of the HQ distance (at least 3) of the middle between two sides | one | 0 / 1* | 44 / 78 | 6 / 8 | 5 | 0 |
| MD06 | plain share of the land | at most 53% | 0 / 0 | 19 / 26 | 8 / 13 | 10 | 0 |
| MD07 | river cells with no bridge or ford | at most 10 | 0 / 0 | 18 / 17 | 2 / 1 | 10 | 0 |
| MD08 | properties with a road within 2 cells (6+ properties) | at least 50% | 0 / 0 | 40 / 68 | 0 / 8 | 0 | 0 |

\* team-mates' bases: the four-player grids do not say who is allied (see above). Every two-player Hall of Fame map passes every rule.
The Emerald Sun maps must pass all eight (`aw2dev maps lint --source es` counts an MD finding as a failure); the BH Campaign, Versus and the games' maps only report them.

## Before the rework: the Emerald Sun maps (Oct 2026)
| Map | Size | Props | per 100 land | farthest from a property | plain | wood | mountain | road | river run | road approaches | middle property |
|---|---|---|---|---|---|---|---|---|---|---|---|
| es01 | 30x27 | 14 | 2.4 | 10 | 51% | 12% | 13% | 10% | 12 | 1 | no |
| es02 | 28x19 | 12 | 2.3 | 12 | 42% | 12% | 27% | 15% | 7 | 2 | yes |
| es03 | 32x24 | 14 | 2.0 | 10 | 49% | 6% | 18% | 19% | 16 | 3 | yes |
| es04 | 32x22 | 14 | 2.0 | 12 | 62% | 10% | 10% | 12% | 10 | 3 | yes |
| es05 | 42x24 | 20 | 2.0 | 10 | 62% | 7% | 10% | 12% | 11 | 3 | yes |
| es06 | 40x32 | 33 | 2.7 | 9 | 57% | 18% | 4% | 16% | 11 | 4 | yes |
| es07 | 38x24 | 19 | 4.1 | 7 | 44% | 14% | 8% | 10% | 0 | 0 | yes |
| es08 | 38x24 | 15 | 1.6 | 11 | 63% | 10% | 9% | 14% | 15 | 1 | no |
| es09 | 34x22 | 24 | 3.9 | 7 | 55% | 1% | 12% | 13% | 13 | 2 | yes |
| es10 | 34x26 | 18 | 2.0 | 9 | 48% | 8% | 27% | 11% | 13 | 3 | no |
| es11 | 40x22 | 22 | 2.7 | 8 | 60% | 6% | 12% | 12% | 12 | 2 | yes |
| es12 | 42x30 | 22 | 1.7 | 10 | 57% | 5% | 24% | 11% | 0 | 3 | no |
| es13 | 38x33 | 42 | 5.3 | 6 | 62% | 6% | 4% | 15% | 9 | 3 | yes |
| es14 | 46x28 | 29 | 2.8 | 10 | 56% | 7% | 18% | 13% | 15 | 3.5 | yes |
| es15 | 46x27 | 30 | 4.2 | 7 | 55% | 11% | 11% | 8% | 0 | 0 | yes |
| es16 | 44x28 | 34 | 3.6 | 10 | 53% | 6% | 18% | 15% | 14 | 3 | yes |

The pattern: big fields with a property every 10 cells (a fifth of the Hall of Fame's density and a quarter of AW2's), more than half the land open plain,
long rivers with a bridge or two, mountains drawn as long ranges. 55 MD findings (map and rule) in 16 maps.

## After the rework (Oct 2026, branch `esmaps`)
Every spec (`five/es/spec/esNN.py`) was drawn again by hand with a design note in its docstring (the situation, the lanes, where the fight happens, what
each property is for, the answer to each threat). Sizes, HQs and every cell a mission's Rust names (spawn cells, objectives, the harbours, the Office,
the camp) are kept, so the mission code did not move; `Canvas.reserve` keeps the reinforcement cells free of start units.

| Map | Size | Props before / after | per 100 land | farthest from a property | plain | wood | mountain | road | river run | road approaches | middle property |
|---|---|---|---|---|---|---|---|---|---|---|---|
| es01 | 30x27 | 14 / 41 | 2.4 / 7.3 | 10 / 5 | 51% / 50% | 12% / 9% | 13% / 6% | 10% / 16% | 12 / 7 | 1 / 2 | no / yes |
| es02 | 28x19 | 12 / 43 | 2.3 / 8.1 | 12 / 3 | 42% / 53% | 12% / 10% | 27% / 12% | 15% / 16% | 7 / 0 | 2 / 2 | yes / yes |
| es03 | 32x24 | 14 / 60 | 2.0 / 8.6 | 10 / 4 | 49% / 47% | 6% / 5% | 18% / 14% | 19% / 18% | 16 / 9 | 3 / 3 | yes / yes |
| es04 | 32x22 | 14 / 42 | 2.0 / 6.0 | 12 / 4 | 62% / 52% | 10% / 17% | 10% / 7% | 12% / 15% | 10 / 8 | 3 / 3 | yes / yes |
| es05 | 42x24 | 20 / 51 | 2.0 / 5.1 | 10 / 5 | 62% / 52% | 7% / 9% | 10% / 15% | 12% / 12% | 11 / 7 | 3 / 4 | yes / yes |
| es06 | 40x32 | 33 / 73 | 2.7 / 6.1 | 9 / 4 | 57% / 53% | 18% / 15% | 4% / 3% | 16% / 19% | 11 / 8 | 4 / 3 | yes / yes |
| es07 | 38x24 | 19 / 44 | 4.1 / 9.4 | 7 / 4 | 44% / 40% | 14% / 13% | 8% / 8% | 10% / 10% | - | sea | yes / yes |
| es08 | 38x24 | 15 / 48 | 1.6 / 5.3 | 11 / 4 | 63% / 53% | 10% / 13% | 9% / 8% | 14% / 18% | 15 / 6 | 1 / 4 | no / yes |
| es09 | 34x22 | 24 / 35 | 3.9 / 5.8 | 7 / 6 | 55% / 53% | 1% / 2% | 12% / 12% | 13% / 13% | 13 / 8 | 2 / 3 | yes / yes |
| es10 | 34x26 | 18 / 59 | 2.0 / 6.7 | 9 / 5 | 48% / 45% | 8% / 6% | 27% / 29% | 11% / 10% | 13 / 9 | 3 / 3 | no / yes |
| es11 | 40x22 | 22 / 46 | 2.7 / 5.5 | 8 / 5 | 60% / 52% | 6% / 13% | 12% / 9% | 12% / 14% | 12 / 7 | 2 / 3 | yes / yes |
| es12 | 42x30 | 22 / 66 | 1.7 / 5.2 | 10 / 4 | 57% / 52% | 5% / 17% | 24% / 10% | 11% / 11% | - | 3 / 4 | no / yes |
| es13 | 38x33 | 42 / 53 | 5.3 / 6.7 | 6 / 5 | 62% / 53% | 6% / 11% | 4% / 6% | 15% / 15% | 9 / 9 | 3 / 3 | yes / yes |
| es14 | 46x28 | 29 / 52 | 2.8 / 5.0 | 10 / 6 | 56% / 52% | 7% / 8% | 18% / 18% | 13% / 14% | 15 / 8 | 3.5 / 3.5 | yes / yes |
| es15 | 46x27 | 30 / 45 | 4.2 / 6.4 | 7 / 6 | 55% / 53% | 11% / 11% | 11% / 11% | 8% / 8% | - | sea | yes / yes |
| es16 | 44x28 | 34 / 56 | 3.6 / 6.0 | 10 / 5 | 53% / 46% | 6% / 5% | 18% / 20% | 15% / 16% | 14 / 5 | 3 / 3 | yes / yes |

0 MD findings. Where the maps still differ from the Hall of Fame, on purpose or not: they are sparser (6.1 properties per 100 land cells, after the 12% cut of neutral cities, against 12;
a campaign mission's armies are pre-deployed and its funds are set, so the economy is not the whole game) and plainer (52% plain against 31%: the rule's
limit is AW2's 90th percentile, and most of the maps sit just under it; a future pass could thin the plains further). The middle is always contested and
the rivers are crossed every 7 cells or so (HoF: 2.4).

## Then 12% fewer neutral cities (the user's rule, Oct 2026)
Each spec ends with `m.thin_neutral_cities(0.12, keep=...)` (the objectives as `keep`): neutral cities before -> after: M1 31->27, M2 35->31, M3 58->51,
M4 34->30, M5 38->35, M6 58->51, M7 27->24, M8 33->29, M9 23->20, M10 55->48, M11 33->29, M12 54->48, M13 38->33, M14 42->39, M15 32->28, M16 31->27.
M5 and M14 lose 3 instead of 5: one more would take them under MD01's 5 properties per 100 land cells. M6's target falls with its houses: 22 of 73
(it was 24 of 80).

## Building a map to the principles (the kit)
- `Canvas.ascii(rows)` draws a whole map by hand (rows checked for size; drawing in groups of eight columns `|`-separated keeps the count: see `es03.py`, `es10.py`);
  `Canvas.tidy()` turns shoal cells the game has no tile for into plain; `Canvas.reserve(cells)` keeps a mission's reinforcement cells free of start units.
- `Canvas.study()` / `Canvas.principles()` measure the map as drawn (no ROM): `aw2dev maps gen --map esNN --no-build --principles` prints the measures and the MD findings of each spec.
- Tile joins the games never draw (TJ01, learned from AW2's maps) bite most on rivers and roads: a river's horizontal run must come from a bend that turns east from the
  north (a river going east, then south, then east again is fine; one going west and then south is not); a road bend or T-junction right under a north-south bridge,
  and two parallel roads side by side, are joins AW2 never has; a volcano stands among mountains (its rim beside plain is not a join of the games).

## BH2 Campaign: what we learned from a wide sample of AWBW maps
The owner asked for AWBW's whole range, not only the top-rated maps. Sample: the 44 ranked maps above (23 Hall of Fame, 20 S/A four-player, measured with `aw2dev maps study`) plus 64 ordinary community maps
fetched from id windows 48000..100000 (all ranks and none: themed, fog, naval, fortress, joke and blank test maps; the search form needs a login, so ids were sampled one request at a time with a pause; the grids and pictures
stay in a scratchpad, nothing is copied). Among the ordinary maps 8 to 17 of 64 trip each MD rule (dead corners, nothing in the middle, open fields, uncrossed rivers, roads to nowhere): the lint is the guard against what the unranked maps do.
Shares below are of the 44 ranked maps, the ordinary set in brackets. Used as inspiration only.
1. **Com Towers** are in 36 of 44 maps (52% of the ordinary ones), about 2 a map, in mirrored pairs on the flanks of the middle (median 0.46 of the way from the centre to the corner), always beside a road or a cluster of cities. A tower is a prize you must hold,
   not a corner pickup: BH2 puts two on the contested ground either side of M3's and M5's river, and one inside M2's massif behind a spur road.
2. **Missile silos** appear in 30 of 44 (44%): in the neutral middle ground away from the HQs (median 0.56 from the centre), a reward for the flank push; on island maps on the islet in the strait (M1's farm silo, M4's islet).
3. **Pipes and seams** are in 23 of 44 (41%), seams in 15: the good ones are walls with one or two gated seams where a road runs into the seam, the wall ending in mountains, sea or the map edge, and a long open way round. The failure mode in the ordinary set is a closed fortress ring with
   no gate. M3 and M5 follow the good pattern: the road meets the seam, and the open road round the massif is longer by 6+ cells (PP04).
4. **Bases sit behind the front**: the first enemy base is about 18 cells from your HQ (5 infantry days) in the ranked 2-player maps; forward bases are neutral and few (2 to 6, 66% of the ordinary maps have some). BH2: each side's bases ring its own HQ, neutral bases stand in the middle.
5. **Property mix**: 10 to 14 properties per 100 land cells, spacing about 3, 70% cities, 14% bases, 5% airports, ports only on a sea map: our MD01 and `Canvas.place`.
6. **The middle is contested**: all the ranked maps and 83% of the ordinary ones have neutral production or cities in the middle (MD05).
7. **Roads guide the play**: two or three roads cross the middle, short spur roads end at what is worth taking (tower, silo, port), and every road over a river has a bridge (median 3.8 river cells per bridge).
8. **Islands and beaches**: AWBW's beaches are two or three cells wide (beach share median 0.32 of the coast, 0.68 on the fog naval maps), ports sit on islets with a village and a road, reefs are scattered. AW2's tile set has one-cell beaches and long runs only on north- and south-facing coasts,
   so BH2's islands face their beaches north and south and run them for 8 to 12 cells (rule TJ01/TJ02 refuses the rest).
9. **Fog maps** are littered with villages along coasts and roads (vision for whoever holds them), small islets halfway, the HQs 16 or more cells apart: M1 follows.
10. **Terrain mix**: plain 24 to 40%, wood 8 to 16%, mountain 0 to 21%; mountains as ridges at chokes and around fortresses, woods beside property clusters.
11. **Fortress and campaign-style maps** wall the HQ with a ring and two or three gates, production just outside: M5's capital behind its pipe wall, the airport district (with the second HQ) behind the capital.
12. **Rich maps** (the 6000-fund four-player ones) have 14 to 15 properties per 100 land and more airports: M3's and M5's enemy gets bases, airports and funds to match the player's Black Factory and strong pair.
13. **Air**: airports are 1 or 2 a side plus a neutral one (58% of the ordinary maps have one): an army fields Anti-Air only where the enemy has or can capture an airport.
14. **Symmetry**: 41 of 44 ranked maps mirror; the campaign's maps are asymmetric on purpose, so fairness is kept in density per side, not in shape.
15. **Sky and joke maps** show what not to do: blank grids, no terrain, all-property fields; the sky front is the one legitimate blank (open air with air units only).
