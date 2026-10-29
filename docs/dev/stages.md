# Stages: a mission that goes on, in the same battle, on another map

A custom campaign's mission can declare later **stages** (`MissionDef::stages: Vec<StageDef>`). The trigger action `Action::NextStage` swaps the running battle to the next stage in place: the trigger's
scenes play, the screen fades out, the stage's map, armies, COs, units and rules are set up, the player's survivors land on the stage's deploy cells, the screen fades in, and play goes on. There is no
world map and no results screen between stages; the mission, its progress and its flags stay the mission's, and its win is the last stage's. Code: `src/stage.rs`; BH2's M31 The Last Accord is the example
(`bh2_campaign.rs`, `bh2_31` stage 1, `bh2_31b` stage 2).

## Declaring a stage

```rust
let mut st = StageDef::new(MapSrc::Built("bh2_31b"));
st.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Keep),                  // the player's army: its COs come along
                 ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(ARIA_CO)).funds(90000)];
st.units = ...;            // the enemy's units (not the player's: the survivors replace them)
st.deploy = vec![(5, 22), (6, 22), ...];   // where the survivors land, in order (the nearest free cell each can enter)
st.carry = Carry::All;     // or Carry::UpTo(n) (the dearest n), Carry::Kinds(vec![..])
st.funds = None;           // None: the player's funds carry over; Some(f): the stage sets them
st.look = 1; st.weather = Weather::Clear; st.fog = false;
st.triggers = vec![...];   // the stage's own rules (a Win wins the mission)
st.intro = Scene::new(...);  // plays at the stage's first turn (its day-one trigger)
m.stages = vec![st];
```
and in a trigger of the mission (or of an earlier stage): `Trigger::new(When::AfterAction, cond, vec![Action::Scene(..), Action::NextStage])`.

A stage is compiled as a mission record of its own after the fronts (`compile_stage`), so it has its own header, deployment, trigger lists and rules; `stage::record(core)` is the record the battle is on and
`ds_campaign` reads it for the weather, fog, look and controllers. `CoSpec::Keep` is the player's CO or tag pair as it is when the switch comes.

## What happens, step by step

`Action::NextStage` runs `stage::request` from the trigger's script: the survivors (the player's army, filtered by `Carry`) with their whole unit record (type, HP, ammo, fuel, capture points; AW2 keeps no
experience), the player's funds, its CO and tag partner and their meters go into the carry buffer; then the swap script starts (`START_SLOT_SCRIPT`). The script waits for the trigger's own scripts, fades to
black, and calls the stubs: `Setup` (the stage's header into the battle's map table entry, gPlaySt's colours, teams, COs and controllers, the five-army game on or off), `PatchWait` (until the patched
five-army game is in the state the stage wants: its unit table has 51 slots an army, the normal game 64), `Load` (the game's own `InitMapGameState`: the battle starts afresh on the new header, as a two-front
battle starts a second front never played), `Restore` (the unit table and plane emptied, the stage's deployment placed, `ApplyUnitSpawnTable`), `Arrive` (armies the stage does not have emptied so no phantom
army keeps the match from ending; the survivors placed; funds, meter and partner), then the scene's rebuild (`RESET_UNITS`, `MAP_GRAPHICS`, `FRAME_CALLBACKS`), the music, the turn's start, the fade in.
`ds_campaign::map_start` runs again inside `InitMapGameState` for the stage's record (its weather, fog, look; the Setup phase is not offered).

Both directions work for the five-army game: M31's stage 1 is five-army (the player is army 5), stage 2 four-army (the player is army 1).

## Limits

- At most 40 units are carried (the carry buffer, `ram_map::STAGE`); the campaigns' armies start with at most 40.
- A stage has no second front, marches, jams, volcano, onyx, Black Factory table or held HQs of its own (the mission's apply to stage 1; held HQs are off after a switch). Named units of different stages
  share the mission's latch namespace: do not name two units alike across stages.
- A battle saved on stage 1 of a five-army mission (M31's gauntlet) and one on a four-army later stage both resume (`docs/dev/five-suspend.md`); a *five-army later stage* saved is written (the stage mark, then the five-army record) but untested.
- The day counter restarts at 1 on the new stage; the intro and any day-one trigger of the stage play again.
- A five-army *destination* stage is wired (`set_campaign(true, ..)`) but untested.

## Suspend and resume

The suspend record gains a mark and the stage number after AW2's block (`stage::saved_state`: 5 bytes; no new Flash sector: the record already has room, a two-front mission's is the larger). Continue puts
the stage's header in place before AW2's resume loads the map (`stage::continue_on`) and the stage number comes back with the block (`restore_saved`); AW2's own block holds the rest. Test:
`bh2_m31_stage_two_suspend_and_resume`.

## Memory

EWRAM `ram_map::STAGE` (0x0203DCA0, 0x200 bytes: the stage, the swap's flags, 40 carried unit records, funds, CO, partner, meters), registered in the overlap test; ROM `0x08E76000..0x08E76800` (ten stubs and the
script), listed in `rom_layout.rs`.

## Determinism

The switch reads and writes only emulated RAM: no clock, no random number, no host state, so netplay peers, replays and save states agree. `bh2_m31_switch_is_deterministic` plays the mission twice up to the
switch and a computer turn of the new stage and compares a fingerprint (both armies' unit tables, players, gPlaySt, the stage state, the unit plane, the random state). A Versus battle cannot declare
stages today (stages are a custom campaign's); the mechanism does not depend on the campaign (it runs in the frame from RAM) and could be given to a Versus mode later.

## Tests

`tools/aw2test/tests/test_bh2_progression.py`: `bh2_m31_progression` (one continuous run through both stages with real captures; carry-over count, HP, ammo, fuel, positions, funds, the new armies, the sheet
`m31_progression.png`), `bh2_m31_stage_two_suspend_and_resume`, `bh2_m31_switch_is_deterministic`.

## Inspecting and forcing a switch (`aw2dev stage`)

`aw2dev stage next 31` enters the mission in the offline harness, plays it to its stage switch with real captures and prints what the switch did: the stage, the map size, each army's units and funds before and after,
the player's units by type before and after, and its power meter; pictures of the moment before and of the new stage's first frame are in the run's folder (`tools/aw2test/out/ds/stage_tool_m31/`).
The captures are the mission's own triggers: `tools/aw2test/tests/test_stage_tool.py`'s `STAGE_TRIGGERS` has one row a mission with stages (the player's army, the HQs in order). A new mission with stages adds its row; the
test `stage_tool_m31` (default suite) checks the report. `aw2dev stage show FILE.sav` says which stage a suspended game was saved on (the rest of the save: `aw2dev save inspect`).
