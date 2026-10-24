# Emerald Sun missions: authoring brief (maps, mission code, tests), version 2

You rebuild some of the Emerald Sun Campaign's missions so that they feel hand-made, roomy and like a CONQUEST. You own, for your missions only: the map spec (`tango-gamesupport-aw2/five/es/spec/esNN.py`),
the mission's Rust function in `tango-gamesupport-aw2/src/es_actN.rs` (coordinates, objectives, reinforcement cells, day limits), and the mission's line in `BOT = {...}` of `tools/aw2test/tests/test_es_sim.py` (the test player's goal
cells) and its rows in `tools/aw2test/aw2test/escampaign.py` / `test_es_boot.py` if a number there depends on the map (army list, size). Do NOT touch other missions, dialogue (`src/es_text/*`), docs, portraits, `cos/art`,
`es_map_data.rs` (generated), or git history of others. You work in your OWN git worktree (the lead gives its path); commit there on your branch, one commit per mission, ending the message with
`Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (author is whoever git config says: rkoh). Never push. Never touch /Applications, the user's running TangoAW2, or ~/Documents/TangoAW2.
Toolchain: `export PATH=$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin:$PATH`. Your worktree has its own `target/` (first `./aw2dev build --examples` takes ~4 minutes). Kill only your own processes. When finished, leave `target/` and `devkit/work/` in place
(the lead deletes the worktree) but report.

Read first: `docs/ES_CAMPAIGN.md` (story, section 4 table; the lead has updated the premise and the M14 to M16 rows), `docs/dev/es-campaign.md`, `docs/dev/maps.md` (legend, unit kinds), `docs/dev/map-lint.md` (all rules incl. the
design-quality section), the docstring of `devkit/aw2/esmaplib/__init__.py` (API: `rect line road river bridge blob cluster meander scatter spread beach put unit units header note`), your missions' current specs and Rust.
Look at the pictures of two BH maps for feel (`tango-gamesupport-aw2/five/bh/bh12.txt`, `bh16.txt`, `bh26.txt`) and at the contact sheets in the lead's folder if given.

## The theme: conquest
The Aurean legion is invading and conquering: landings, marches into enemy lands, sieges, cities and HQs taken, provinces falling one by one, the frontier pushed outward. Favour "capture / rout / take" objectives and
offensive pressure over holdouts. Only M2 (Testudo) and M11 (Treasure Train, an escort) are defensive by design. The map should read as the enemy's LAND: villages, a river valley, a coast road, a border fort, a walled
town, fields; the player is the one coming in. Name places in the spec comment as a province (the dialogue agent uses your notes).

## Room to fight (the user's rule)
The armies are large and the old maps crammed them into blocks and corridors. Make each map bigger where needed (width x height <= 1288, width <= 64, height <= 40; the old sizes were 18x15 to 36x30; most missions
should grow by 20 to 60%): open fields for flanking, two or three approaches (not one corridor), room behind each line for artillery, and room for the enemy to counterattack. Lint rule SP01 measures it (units per
vehicle-walkable cell <= .17 and units of the smaller side per cell of frontage <= 1.25); AIM LOWER: density <= .12 and frontage ratio <= .9. Start forces can stay as they are; a bigger map with the same units is the cure.

## It must not look procedural (lint DQ01..DQ11)
No straight river or road from edge to edge (use `m.meander` for rivers, `m.road` legs with bends and junctions: roads connect properties and bend around terrain); no rectangular woods or mountain blocks and no parallel rows
(use `m.cluster` and `m.blob` for irregular patches, vary woods / mountains / plain, ridges that curve); coastlines with shape (coves, spits); no big empty plain fields (give them hedgerow woods, a hamlet, a road, a
ruin); no unit blocks (use `m.spread(army, {kind: n}, box, seed=..., gap=1)` or lay formations by hand: a screen line, a column on the road, a reserve behind, garrisons in the buildings, a battery on the hill);
no property far from roads and other property; an HQ with room around it. Rivers: a spring at a mountain or the map edge, bends, a mouth in the sea or a lake or off the map; bridges where roads cross (lint RV/BR/TJ rules).
Every wood, mountain, road and river is there for a reason (cover, a route, a choke, a defensive ring); do not scatter noise. A map is not finished if the picture looks plain, empty or implausible.

## Your loop
1. Edit the spec (header of es01.py: the `sys.path` line and `from aw2.esmaplib import *`; `def build(): m = Canvas("esNN", W, H); ...; return m`). Keep the header's colours as in the mission's Rust (`m.header(colours=(..))`:
   player first; the kit checks that the map file's colours equal `ArmyDef`'s). 1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole. The player's colour is never one an enemy or ally wears and never 5 (except Black Hole enemy missions).
2. `./aw2dev maps gen --no-build --map esNN`, then `./aw2dev maps lint --source es --map esNN --warn`: ZERO errors AND zero DQ/SP findings (a finding is fixed by changing the map, never by changing `design.LIMITS`). Look at
   `devkit/work/maps/lint/es/esNN.png` with the Read tool every iteration.
3. Update the mission's Rust to the new coordinates (objective cells, reinforcement cells, triggers, rects) and, if you changed the objective, the `objective` text (one short line, no day numbers unless a limit is real).
4. Build and test: `./aw2dev maps gen --map esNN` (this rewrites `es_map_data.rs`: that is fine in your worktree, the lead regenerates after merging), `./aw2dev build --examples`, then
   `python3 tools/aw2test/run.py -k es_boot_mN --mode ds` (boots), `python3 tools/aw2test/run.py -k es_colours_mN --mode ds` (colours), `AW2TEST_REVIEW_DIR=/tmp/<yourdir> python3 tools/aw2test/run.py -k es_review_mN --mode ds` and LOOK at `m<N>_full.png`
   (the real game's picture: check the rivers, coasts, roads and units as the player sees them), then the bot sim: `AW2TEST_ES_SIM=N AW2TEST_ES_PLAYER=bot AW2TEST_ES_SEED=0 AW2TEST_ES_DAYS=40 AW2TEST_ES_OUT=/tmp/<yourdir>/simN.jsonl python3 tools/aw2test/run.py -k es_sim_mN --mode ds`
   (and `AW2TEST_ES_SCALE=60` for a handicap run): it must at least not lose instantly, the enemy must act (`es_cpu_mN`), and the mission must be winnable by a player who knows the answers; report the result honestly (the weak test bot is not a human).
5. `cargo test --release -p tango-gamesupport-aw2 --lib es_` and `./aw2dev campaign check` stay green. `python3 -m unittest devkit/aw2/esmaplib/test_esmaplib.py` stays green (it checks every committed text map equals its spec: run `maps gen --no-build` first).

## Rules every mission keeps (the user's)
- **Answer to every enemy threat** (aircraft: Anti-Air / Missiles / Fighters on the map or buildable; heavy indirect fire: Recon to find it, range or Bombers; ships: Bombers / subs / Battleships); list threat-to-answer pairs in the spec `comment`.
- **Deployed units start with full ammo and fuel** (never set `hp=`). No army starts with more than 40 units (AW2 stops production and reinforcements at 50).
- **Beaches generous** on landings (a shoal strip along the coast, 3 to 5 spare sand cells behind each landing, ports both sides; every Lander has a beach or port; DQ10 wants 6+ shore cells).
- **One battlefield a mission** (no two fronts). Forced routes come from rivers, mountains, pipes: never from decorative walls. Distinct territories for multi-army maps. Exactly one HQ `1`..`N` per army.
- **No Black Hole inventions** (`S N W E L v n F D X O #`, silos `M`) except M9 and M13, the two missions against Black Hole (`m.header(blackhole=True)`, inventions owned by that Black Hole enemy army, at most one Deathray at the top edge).
- Unit lines: `m.unit(army, kind, x, y, hold=?)`; army 1 is the player; `hold=True` defenders stay, others advance. Properties `B C A P` belong to the army whose HQ is nearest (`m.header(owners=..)` / `split` change that); neutral ones are lowercase.
- Day limits only where the clock is the mission. Win by capture or rout unless the mission is M2 / M11 / M13.

## When you finish
Commit in your worktree. Reply with a short report per mission: the new size, army list and colours, both start forces, the named places (key, x, y), the forced routes, threat/answer table, lint result (must be clean), bot sim result
(win/loss, days) at 100% and 60%, what you changed in the Rust (objective text, coordinates), anything the dialogue must change (new objective, new places, new names), and any rule you could not meet and why.
