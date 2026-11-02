# CPU unit use: boats, carriers and the ports they must not block

Code: `tango-gamesupport-aw2/src/cpu_units.rs` (with `cpu_defend::check` and `ds_ai_move::role_move` as its two doors). Tests: `tools/aw2test/tests/test_cpu_unit_use.py`
(`-k cpu_unit_use`). `inspect::SIM_VERSION` 46.

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
| Stealth, Black Bomb, Oozium, Megatank, Piperunner | As before (`cpu_tactics`, `oozium`, AW2's role moves). A Piperunner without a pipe path to anything has nowhere to go: that is not a soft lock. |

Not done here: the Black Boat does not plan cargo (it never carries Infantry or Mech for the CPU: AW2's foot-soldier loading looks for APCs, T Copters and Landers by type),
and a Carrier does not plan its air cargo (launching). The Lander's cargo logic is AW2's.

## Dev aids

`TANGOAW2_BH_LOG=<file>` logs `dsai move day N army A <Unit> at (x,y): (cx,cy) <why> (repair worth W, danger D, N away from <target>)` for every boat and Carrier move, and
the harness reads it as `<save>.bhlog`. `ds_ai::SWITCHES` bit 3 (`OFF_MOVE`) turns all of these moves off for A/B runs.

## Tests

`cpu_unit_use_versus_every_unit_acts` (a 30 x 20 map with a sea, pipes, two ports, bases and airports and one of every DS unit for the CPU: four CPU days; each of Black Boat,
Carrier, Stealth, Black Bomb, Piperunner, Oozium, Megatank and Lander takes an action, and no starting unit stands on a base, port or airport in two snapshots in a row),
`cpu_unit_use_black_boat_repairs_a_neighbour`, `cpu_unit_use_boat_frees_the_port_to_build`, `cpu_unit_use_gauntlet_cinder_sea` (the Gauntlet's Cinder Sea, five days, the
player passive: no enemy Black Boat sits on a port two days running) and `netplay_cpu_unit_use` (both rollback peers and the straight replay identical).
