# CO verify: every ability of the custom COs against the specification (`aw2dev co verify`, `aw2dev co sheet powers`)

Code: `devkit/aw2/colib/verify.py` (runs the scenarios, collects the tags, prints the table), `verify_net.py` (online determinism), `powersheet.py` (contact sheets); the scenarios
`tools/aw2test/tests/test_co_verify.py` with their library `tools/aw2test/aw2test/coverify.py`; the specification `tools/aw2test/aw2test/cospec.py`; the pictures
`tools/aw2test/aw2test/copics.py`. Unit tests (no ROM): `devkit/aw2/colib/test_verify.py` (run by `aw2dev test`). Skill: `aw2-add-co` (step 5).

## What is checked, and against what
The COs: Klaus, Aurelia, Cassius, Livia (Emerald Sun), Varro (boss only), Crumb (Black Hole), Clone Andy, Asuka (Black Hole; her cells are filled from her own suite, `tests/test_asuka.py`, through `LEGACY`). `aw2dev co verify sonja` is a different check (`colib/verify_sonja.py`): Sonja against the v0.8.7 build. **Every number is played in a real Versus battle on the harness console (the Dual Strike pack,
`TANGOAW2_ES_VERSUS=1`) and compared with the SPECIFICATION, never with the engine's own tables** (`es_co::bonus`, `crumb::bonus`) and not with `damage.es_bonus` (the Python mirror of the
engine, still used by the older tests). `cospec.py` reads the data files `cos/<id>.toml` (`mods`, `income`, `tribute`, `heal`, `stars`, `luck`), `cos/tags.toml`, and for Crumb and Varro the numbers in
`crumb.rs` / `es_co.rs`'s module docs (they have no data file). A class word of a `mods` line means (docs/ES_CAMPAIGN.md 2.1): `foot` Infantry and Mech; `vehicle` Recon, APC, Tank, Md. Tank, Neotank and
Anti-Air; `indirect` Artillery, Rockets, Missiles, Battleship; `naval` every ship. Every power adds the game's own +10% firepower and +10% defence on top of its `mods`. Clone Andy's specification is his data file
(`cos/cloneandy.toml`: day to day +2 / +2 on every unit, Hyper Repair heal 2 and nothing of its own, Hyper Upgrade heal 4, +30 / +20, no move bonus: 102/102, 112/112, 142/132 in all), played like the others,
and the `cloneandy` facet plays him beside Andy as a before / after.

| Facet (test names `co_verify_<facet>_<co>[_<level>]`) | What is played | Compared with |
|---|---|---|
| `stats` (day to day, CO Power, Super Power) | AW2's nineteen unit types (the Dual Strike units, Megatank, Piperunner, Stealth, Black Boat, Carrier, Black Bomb, are not in the unit table the calculator reads) each attack an Andy unit, then Andy's aircraft hit them: base damage, luck range, HP loss, counter, forecast, both power meters, the target's total defence | `damage.battle` with `cospec` numbers (`SpecRules`) and the game's own player blocks |
| `move` | one unit of each type on its own road (sea) lane: the farthest cell it reaches | base move + the specification's move bonus |
| `range` | Artillery, Rockets, Missiles, Battleship and a Tank: Fire offered at max range + bonus, not one cell farther (two boots a CO and level) | base range + the specification's range bonus |
| `economy` | an Infantry and a Tank bought (cost), the day's income at 1000 and at 2000 a property (the Rules screen's Funds), CO Power and Super Power funds, HP healed, the enemy's units untouched | `cost`, `income`, `tribute`, `heal` of the data file |
| `meter` | the CO table's stars; the map menu offers Power and Super at exactly stars x 9000 and not one point less, again after one power used (+20%) | `stars` |
| `hooks` | Testudo (counter cut to 75%: damage number and forecast), Onager (splash 1 HP to the enemy units beside the target, never the last, never her own, diagonals or two cells away), Triumph (a Tank that attacked is not done, no Fire, one move, then done) | the rule's sentence in the data file |
| `tag` | both meters full: the map menu offers Tag; the tag screen shows POWER n% (Dual Strike's digits cell by cell); the first half is the active CO's Super Power with the pair's firepower and luck (5 per star), then Change: the partner's; heal and funds of each half; Onager and Triumph inside a half; the TAG page lists the partners with their stars | `cos/tags.toml` |
| `cpu` | the computer plays the CO with the power paid for: it uses it within three turns (CO Power and Super Power), its hurt units are healed; with a partner and both meters full it uses the Tag Power and both Super Powers run | |
| `hq` | the HQ of each CO's army on the map: a Versus game per CO, the pairs (the lead decides) and each Emerald Sun mission (M1..M16): the OBJ tiles hold the Emerald Sun HQ picture (`army_skin::hq_art`) once for every army whose CO's data file says `hq = "emerald_sun"` or that wears the skin, and not otherwise; `aw2dev campaign check --hq` runs the missions | `hq` of `cos/<id>.toml` |
| `vehicles` | Megatank and Piperunner of Cassius and Aurelia against Andy's: move, base damage and the Piperunner's range at each power level | the vehicle bonus / penalty of the data file |
| `cloneandy` | Andy (before) and Clone Andy (after) play the same fights and moves; `before/after` log lines give each fight's base damage and defence for both | his attacks at least Andy's with the target's defence unchanged, his defence Andy's + the file's difference, his moves Andy's (less Andy's Hyper Upgrade +1) |
| `limits` | Cassius's Triumph for the computer and after suspend and continue: measured and reported as LIMIT lines | |
| net (`--net`) | each CO's `co_<co>_cop` and `co_<co>_scop` through `aw2dev net repeat` (two real clients, the CO poked into army 1, the meter filled, the power and its special rule played) | the two peers' hashes equal, the scripts run to the end |

Older tests that back a cell are run with it (`verify.LEGACY`: Crumb's resupply, Ration Run, Gerald's Blessing, the Sturm pair; Clone Andy's pair; the Emerald Sun rule tests).

## Running it
```
aw2dev build --all                      # the harness examples and the app (aw2dev refuses stale binaries)
aw2dev co verify                        # every CO, about 10 minutes with -j 4 (devkit/work/co_verify/report.md has the numbers)
aw2dev co verify klaus livia            # some
aw2dev co verify --quick                # one scenario per facet and CO: the suite's smoke run (suite entry `co_verify`)
aw2dev co verify --net --net-runs 3     # plus the online runs (about 90 s each, one live run at a time)
python3 tools/aw2test/run.py -k co_verify_stats_klaus -v     # one scenario with its log
aw2dev co sheet powers [CO ...]         # the pictures (below)
aw2dev co sheet hq                      # the Roman COs' HQ on the map: Versus, the tilted map (the real app), the missions (hq_check.png)
```
Pass means exit 0 and `co verify done bad=0`. Every check in a log is tagged `[<co> <ability>] <detail>: ...`; the table groups them by CO and ability (Day to day, CO Power, Super Power, Meter / stars, Tag Powers,
CPU use, Online determinism) and `report.md` lists the first line of every kind of check, with its numbers.

## Pictures (`aw2dev co sheet powers`)
Real frames of the game (the harness console with `TANGOAW2_DS_GRAPHICS=1`, the look the app has), one `<co>_powers.png` per CO and `all_cos_overview.png`: the Teams screen's CO select card, the CO page,
the HUD with the power bar charging and full, the CO Power and the Super Power (before, quote box, cut-in begins, whole, ends, the screen effect, after), each Tag Power with its partner (the map menu, quote,
tag screen with both COs and the percentage, each half's cut-in), and a battle that shows the effect (Testudo's counter against a plain one, Onager's splash with the HP of each unit, Triumph's second move, Tribute's funds, heals).
The frames are picked by what is on them (a cut-in is a frame the map does not show through with a dark figure on it; the quote is the box with the most text). LOOK at every sheet: a wrong name, missing art,
a garbled cut-in or a wrong colour is a bug.

## Adding a CO
Give `cospec.py` its numbers (a `cos/<id>.toml`, or a function like `crumb()`), add it to `COS` in `verify.py`, to `NAMES` in `test_co_verify.py` and `NAMES` in `copics.py`; the scenarios are generic. A power with a special rule
needs its own `hooks` scenario (copy `hook_onager`) and a net scenario (`scenarios.co_actions`).

## Limits
- The unit types: only AW2's nineteen play in the `stats` fights; the Megatank and the Piperunner (vehicles, the owner's ruling) are pinned by the `vehicles` facet by comparison with Andy.
- Tag Powers are not played through `net repeat` (a pad script for the Tag, Change and End sequence stalled before the second half; the hashes were equal); the harness plays them (`tag`) and Aurelia's Onager and Cassius's Triumph rules are checked on two consoles (`es_*_is_deterministic`); the Aurelia net scenario plays the power only (a poked Artillery has no ammo).
- Onager in fog (hidden units beside the target) is not played.
- Cassius's Triumph: the computer's Cassius gets no extra move and a suspend and continue loses the extra-move bit (the Tank may fire again): reported as LIMIT lines (the `bugfix` branch is working on them).
- The net scenarios poke the CO into army 1 (a real room picks it on the Teams screen); `net repeat`'s leak check is not part of the verdict (it flags the same episodes for Andy and Kanbei with these scripts).
