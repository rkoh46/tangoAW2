# CPU unit use: boats, carriers, idle units and the ports they must not block

Code: `tango-gamesupport-aw2/src/cpu_units.rs` (with `cpu_defend::check` and `ds_ai_move::role_move` as its two doors). Tests: `tools/aw2test/tests/test_cpu_unit_use.py`
(`-k cpu_unit_use`). `inspect::SIM_VERSION` 47 (46 was 0.9.3; 47 adds the portidle changes and the War Room).

## What was broken

AW2's computer plays a unit through a pass chosen by the unit's role byte (unit record +0x1B: 1 foot, 2 APC / T Copter, 3, 4 indirect, 5 direct, 6 Lander).
Dual Strike's Black Boat is the APC's role 2 in tangoAW2's table (`roster::NEW`), and that pass never calls the role move for the unit: whatever the map or mission
gave it as its order, a CPU Black Boat sat where it was built. On a port that is the soft lock the owner saw (Gauntlet, Cinder Sea: the fleets build Black Boats; a
boat on the port keeps the port from building and never repairs anything). A Lander with no soldiers to carry sat on its port the same way, and a Carrier (indirect,
role 4) was moved only when an enemy aircraft was in reach, so it too waited in port while the way to the enemy HQ was sea-locked.

## The rules (all from emulated RAM and ROM: the same on both netplay peers, in replays and after a rollback)

| Unit | Rule |
|---|---|
| Black Boat | Played at the unit queue's attack check (`cpu_defend::check` calls `cpu_units::plan`, which has the game's own planner `sub_0805D648` move and wait). It scores every cell it can reach (movement costs, fuel, free cells): a Repair there (1 HP of every damaged unit of its army next to the cell while funds last, as `unit_actions::repair_around`: its cost per HP plus a little, and a little for supplies it would give, ammo or fuel at half or less; all times 4; **-100000 on a base, port or airport of its team** (it never ends a turn there when any other cell is reachable); -30000 and its danger on a cell Dual Strike's threat maps call unsafe for it (the profile's limits, `ds_ai_move::threat_maps`: it retreats when its own cell is unsafe); -10 a step of distance to where it heads when no Repair is in reach: its army's damaged units, else its warships, else any unit of its army. The Repair itself is the turn-end action (`cpu_tactics::end_of_turn_plan`), unchanged. |
| Lander | AW2's own loading and unloading logic moves it (unchanged) unless it is empty (cargo bytes +7, +8 of its record) on a base, port or airport of its team: then it steps off the same way, towards its army's foot soldiers. |
| Carrier | `ds_ai_move::role_move` (a combat unit's threat-aware advance, with a Cruiser's limits where the pack has none) on the nearest enemy it can hit, else the enemy HQ; where the sea does not reach it drifts towards the nearest enemy (never closer than 3, never onto a port). |
| Ship or aircraft whose target is out of reach | `ds_ai_move::choose` found no cell nearer (the sea does not reach the enemy HQ it was sent to): `cpu_units::drift` instead of AW2's role move, which does nothing: the nearest safe cell towards the nearest enemy unit (else enemy HQ), off the ports. |
| Missiles | The indirect Anti-Air has no ground target in AW2's role 4 and used to stay where it was built: it takes the Carrier's path (`handles`), the advance towards the nearest enemy it can hit, else the enemy HQ, by the safe cells. |
| Any unit parked on a building of its team | **Backstop.** A unit standing on a base, port or airport of its team (not being repaired there: hit points under 91 on the kind of property that repairs it) is taken off it: at the attack check (`cpu_units::plan` -> `parked_leave`, when no enemy it can hurt is within its reach, AW2's attack check being then the one to decide) and in AW2's role move (`ds_ai_move::role_move`, an indirect gun or a ship AW2 leaves where it stands: `leave`) by Dual Strike's advance on its order's target, else a drift towards the nearest enemy, else the nearest safe cell off the building (`step_off`; a guard of its HQ, role 7, only steps aside); and, for the units AW2's queue never plays (an indirect gun with no target in reach), by `cpu_units::sweep` just before the army's production (`ds_ai_build::start`): the unit steps to the nearest safe free cell off the building in emulated RAM (as the ferry's loads and drops are), so the building builds that turn. Not a garrison (role 0), a march, a transport waiting for cargo (APC, T Copter), Stealth, Black Bomb, Oozium, Piperunner. |
| Infantry or Mech bought with role 0 | AW2's role roll answers 0 for a foot soldier when the army's personality row has no weights, and the campaign engine keeps a role-0 soldier where it stands (a designer's garrison): the soldiers Cinder Sea's and 25 of the BH missions' computers built stood on their base for good. A soldier bought during a mission takes role 3 (`custom_campaign::built_foot_role`, in Versus and the custom campaigns; not AW2's own campaign, Survival, the War Room or the DS Campaign). |
| Stealth, Black Bomb, Oozium, Megatank, Piperunner | As before (`cpu_tactics`, `oozium`, AW2's role moves). A Piperunner without a pipe path to anything has nowhere to go: that is not a soft lock. |

The Lander's own cargo logic is AW2's. Cargo of the Black Boat and the Carrier is `cpu_ferry.rs`:

## Cargo: Black Boat ferries, Carrier launches and takes in

AW2's foot-soldier logic picks transports by type (APC, T Copter, Lander) and its Lander logic wants the beaches of a campaign map, so the Black Boat and the Carrier never carried anything for the CPU.
Loads and drops are made in emulated RAM as the game's own Load and Drop leave the records (measured with a player's: passenger flags `0x0B`, cell = the transport's, transport flags `0x10`, unit id in cargo byte +7 / +8;
a drop gives the passenger the free cell and flags `0x01`). The unit queue lifts the unit it plays off the map, so they are made once at the start of a CPU army's turn (`cpu_tactics::cpu_unit` -> `cpu_ferry::turn_start`), and
the units that acted carry the acted flag, which the queue passes by. Deterministic: only RAM, no host state.

| | Rule |
|---|---|
| Who needs a ferry | the army's Infantry and Mechs with no land way (one reverse flood, `ds_ai_move::distance_to`) to any property not of their team's (enemy HQ included); campaign holders (role 0) are left. |
| Landing | a shoal with a free, standable land neighbour from which that way is open: a drop never strands anybody. |
| Beach | the shoal the first such soldier reaches soonest that the army's first Black Boat can sail to. The soldiers walk there (`cpu_ferry::plan_foot`, the game's planner); the boat sails there (`cpu_units::boat`, job from `cpu_ferry::mission`). |
| Boarding / dropping | at turn start the boat on a shoal takes up to two soldiers whose walk reaches it, then sails to the nearest landing (its cargo is dropped at turn start when it stands on one). With no job it repairs as before; it never ends on a port. |
| Carrier | aircraft (not Carriers) with fuel or hit points at 40 % or less land on a friendly Carrier they can reach with room for them (its turn-start resupply refuels them); the Carrier launches fit cargo (60 %+) onto free cells next to it when an enemy is within 14 cells: `launch` / `plan_air`. Launched aircraft have acted and fly next turn. |

Not done: repairing aircraft on a Carrier (only resupply, which the game's own Cruiser rule gives), planning the Lander's cargo (AW2's).

## Dev aids

`TANGOAW2_BH_LOG=<file>` logs `dsai move day N army A <Unit> at (x,y): (cx,cy) <why> (repair worth W, danger D, N away from <target>)` for every boat and Carrier move, and
the harness reads it as `<save>.bhlog`. `ds_ai::SWITCHES` bit 3 (`OFF_MOVE`) turns all of these moves off for A/B runs.

## Tests

`cpu_unit_use_versus_every_unit_acts` (a 30 x 20 map with a sea, pipes, two ports, bases and airports and one of every DS unit for the CPU: four CPU days; each of Black Boat,
Carrier, Stealth, Black Bomb, Piperunner, Oozium, Megatank and Lander takes an action, and no starting unit stands on a base, port or airport in two snapshots in a row),
`cpu_unit_use_black_boat_repairs_a_neighbour`, `cpu_unit_use_boat_frees_the_port_to_build`, `cpu_unit_use_gauntlet_cinder_sea` (the Gauntlet's Cinder Sea, five days, the
player passive: no enemy Black Boat sits on a port two days running) and `netplay_cpu_unit_use` (both rollback peers and the straight replay identical).

## The port-idle tests: every mission and map

`tests/test_cpu_port_idle.py` (`-k cpu_port_idle`; helpers in `aw2test/cpuports.py` and `versusmaps.py`) is one test per mission and map, made from the real lists: every BH (31, the second fronts of 8, 15, 20 and 25 too), BH2 (32, the fronts of 4, 13 and 25), Silver Nova (16) and DS Campaign (28) mission,
the Gauntlet's maps (`five/gauntlet/gauntlet_NN.txt`), every map SELECT MAP lists with the pack (read once from the game's own list buffer into `out/versus_map_list.json`, so a new map is picked up), two Design Room maps with ports on both sides, and, as
the original AI's report only (`cpu_port_idle_aw2campaign_mNN`, `_survival_`, `_warroom_ds_` / `_warroom_aw2_`: AW2's own CPU plays them; nothing was changed for them), AW2's campaign, the first map of each Survival run and the War Room's maps. The player ends every turn without acting
and the test takes a snapshot at each of his turn starts; it fails when a computer unit that could get off stays on the same base, port or airport of its team in two snapshots in a row (a unit built on a turn is in the first snapshot, so it must leave by its second turn: a port its owner or an ally keeps occupied
cannot build). Exempt, with the reason in the test's log and `cpuports.py`'s header: a unit that cannot get off (no fuel, boxed in, or every free cell it reaches is another building of its team: detected from the snapshot with the game's own movement chart), a unit riding in a transport,
a soldier on the building it captured the turn before, a damaged unit the property is repairing, a unit in a fight (it lost hit points or an enemy is within two cells) or whose army's HQ is under capture, and a unit that was on the map in the first snapshot with role 0 (a mission's or a map's own garrison). Only pairs of snapshots in
which the army played count (its funds changed or one of its units moved). What the tests found: the role-0 soldiers above, and indirect guns, ships and leftover units AW2's queue leaves on their building.

## Measuring idle units, and what is left

`tests/test_cpu_unit_use.py` measures, for each CPU turn, how many of the CPU's units that were on the field at its start moved, lost hit points or used ammo
(`acted_fractions`; the idle ones are logged by type) and whether the CPU closes in on the passive player (`closing_in`: the mean distance of its units to the nearest
player unit fell by 3, or the player lost hit points). `cpu_progress_versus` (a land map with an army of every ground type: 80 % act), `cpu_progress_gauntlet_cinder_sea`
(60 %), `cpu_progress_gauntlet_iron_crown` (60 %), and the cargo tests `cpu_unit_use_black_boat_ferries_infantry` (a strait only a Black Boat crosses: a soldier boards, crosses, is dropped on the far shore within six days), `cpu_unit_use_low_fuel_fighters_land_on_a_carrier`, `cpu_unit_use_carrier_launches_its_fighters`; `cpu_progress_gauntlet_cinder_sea` also needs a Black Boat to take soldiers aboard and drop them. Measured with this change: Versus 13..17 units, 13..16 act a turn (the idle ones: a Mech or Tank behind a jam); Cinder Sea 12..15
units, 7..12 act (the rest: Infantry waiting on an island for the Lander's next trip, which AW2's own loading logic ferries one at a time, and ships that hold because nothing nearer is safe,
Dual Strike's own rule); Iron Crown 29..35 units, 25..29 act.

The campaigns' CPU audits are the existing ones (`bh_cpuai_acts` for every BH mission: the enemy moves, captures and builds; `ds_campaign`, `es_`, `bh2_` mission tests). Where a
mission declares a unit a holder (role 0, `UnitDef::freeze`, `STAND`, a march) it stays; nothing in this change touches those.

Scope: Dual Strike's CPU (and so every rule above) plays in Versus, the War Room (title mode 5, `ds_ai::in_scope`; its maps' AW2 personalities are mapped onto Dual Strike's profiles by the CO the army has, as Versus does), the DS Campaign and the custom campaigns (BH, BH2, Silver Nova, the Gauntlet). AW2's own campaign and Survival keep AW2's own CPU.


## Foot soldiers: garrisons that sally, ships' land cousins

Silver Nova M1 (Landfall) deploys all six of Green Earth's soldiers with role 0 (the map's `hold`); AW2's hold plus the campaign engine's skip (`custom_campaign::ai_unit`) kept them on the fort for the whole mission, with neutral cities two turns' walk away.
Two rules, both deterministic (emulated memory only; `inspect::SIM_VERSION` needs a bump for them):

- **Sally** (`custom_campaign::sally`): a role-0 Infantry or Mech with no enemy next to it is released to role 3 (capture) for good when no HQ of its team is within 3 cells (the HQ's guards stay) and a building not of its team's (neutral or an enemy's) is within two turns' walk. A soldier with nothing to take stays, so a roadblock between walls is still one.
- **Shore drift** (`ds_ai_move::choose`): a land unit that no land way takes to any target of its role (the enemy across the water: M1's sandbar) drifts to the safe cell nearest the enemy, as a ship does (`cpu_units::drift`), instead of sitting where it was deployed.

Tests and tools: `-k cpu_foot_idle` (`tests/test_cpu_foot_idle.py`): M1 with the player passive (foot soldiers take property, at least 60% of their turns are work) and with the test player landing (Green Earth takes property, at least 60% of its units act each turn),
plus a log-only report per Silver Nova mission; `cpuports.report` now also logs, for every mission and map of `-k cpu_port_idle`, the idle foot soldiers (`foot_idle`), the share of units that acted (`acting_share`) and the neutral buildings within three turns' walk of a soldier at the end (`neutral_reachable`).
