//! Dual Strike's weather rules, with the Dual Strike pack on.
//!
//! Dual Strike keeps AW2's weathers but changes what they do: snow and rain
//! no longer slow units down; snow doubles the fuel a move uses and so
//! halves how far fuel takes a unit (except for Olaf's army, with CO
//! abilities on); rain lowers vision by 1 (AW2 already does) and brings fog
//! of war with it. (Sandstorm, Dual Strike's fourth weather, is
//! [`crate::sandstorm`].) With the pack off everything is AW2's own.
//!
//! - Movement: snow's and rain's movement charts are clear's with the pack
//!   on ([`crate::roster`], which also gives the charts the new units' rows).
//! - Fuel (Dual Strike's `Player_GetFuelRate`, [`fuel_rate`]): a move's
//!   fuel (`SubtractFuel`, [`MOVE_FUEL`]) is the path's cost x the rate
//!   (none for an Oozium, `Unit_GetFuelUsed`), and a unit's reach is at
//!   most its fuel / the rate (`Unit_GetMovePoints`, [`reach`]). The daily
//!   burn takes no weather (`Unit_BurnDailyFuel`): [`FUEL`] only takes off
//!   Sneaky's and Stealthy's cut.
//! - Fog: while rain is coming the Rules' fog flag is set, and put back when
//!   it stops. The game rebuilds fog from that flag at every turn start
//!   (`sub_080213AC`), so the flag follows the *next* weather (decided at
//!   turn end, [`NEXT_WEATHER`]): fog comes and goes with the rain's first
//!   and last turns. Rain from a CO power brings fog from the next turn.

use mgba::core::Core;

/// Set every frame to 1 while the Dual Strike features are on, 0 otherwise
/// (for traps, which only see the core). In EWRAM, so saved with the state.
pub const DS_ON: u32 = 0x0203_FFA6;

const OLAF: u8 = 3;
/// The army whose turn it is (1..5).
const CURRENT_ARMY: u32 = 0x0300_33EC;

/// gPlaySt: the weather (0 clear, 1 snow, 2 rain) and the fog flag.
pub const WEATHER: u32 = 0x0300_3FEC;
/// The weather for the next turn, decided at turn end.
pub const NEXT_WEATHER: u32 = 0x0300_3FEE;
const FOG: u32 = 0x0300_3FCD;
const SNOW: u8 = 1;
const RAIN: u8 = 2;
/// The Rules' fog flag while rain has forced fog on (1 + flag; 0 = not
/// forced).
const RULE_FOG: u32 = 0x0203_FFA7;

/// The Rules' fog flag kept while rain forces fog on (1 + flag; 0 when
/// not forced), for a suspended game ([`crate::suspend`]): gPlaySt is
/// saved with the forced fog, so without it a game continued in rain
/// would keep fog on for good once the rain stops.
pub fn rule_fog(core: &Core) -> u8 {
    core.raw_read_8(RULE_FOG, -1) & !IN_BATTLE
}

/// [`RULE_FOG`]'s mark: set in the battle it was made in.
const IN_BATTLE: u8 = 0x80;

pub fn set_rule_fog(core: &mut Core, v: u8) {
    core.raw_write_8(RULE_FOG, -1, v);
}

pub fn is_on(core: &Core) -> bool {
    core.raw_read_8(DS_ON, -1) != 0
}

/// Every frame, before the game runs.
pub fn tick(core: &mut Core, on: bool) {
    core.raw_write_8(DS_ON, -1, on as u8);
    crate::sandstorm::tick(core, on);
    crate::wasteland::tick(core, on);
    crate::com_tower::tick(core, on);
    let raw = core.raw_read_8(RULE_FOG, -1);
    let forced = raw & !IN_BATTLE;
    // A battle left with the memory set gives the Rules' choice back and
    // drops it (it would else put that battle's fog choice over the next
    // one's); one restored by a Continue is kept until its battle is on
    // ([`IN_BATTLE`] not yet set). The animated battle scenes also leave
    // the map's callback for a while: the choice must be given back there
    // too, or the rain would force the fog again on top of its own fog and
    // take that for the Rules' choice, keeping it after the rain.
    if !crate::ds_campaign::in_battle(core) {
        if raw & IN_BATTLE != 0 {
            if forced != 0 {
                core.raw_write_8(FOG, -1, forced - 1);
            }
            core.raw_write_8(RULE_FOG, -1, 0);
        }
        return;
    }
    if forced != 0 && raw & IN_BATTLE == 0 {
        core.raw_write_8(RULE_FOG, -1, forced | IN_BATTLE);
    }
    if on && core.raw_read_8(NEXT_WEATHER, -1) == RAIN {
        if forced == 0 {
            let fog = core.raw_read_8(FOG, -1);
            core.raw_write_8(RULE_FOG, -1, (1 + fog) | IN_BATTLE);
        }
        core.raw_write_8(FOG, -1, 1);
    } else if forced != 0 {
        core.raw_write_8(FOG, -1, forced - 1);
        core.raw_write_8(RULE_FOG, -1, 0);
    }
}

/// The daily fuel burn is in r5 here (a signed byte, after the CO's
/// modifier; `sub_080253B0`): a dived Sub's or hidden Stealth's less
/// Sneaky / Stealthy (crate::co_skills).
pub const FUEL: u32 = 0x0802_5434;
pub fn fuel(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    let unit = core.gba().cpu().gpr(4) as u32;
    let burn = core.gba().cpu().gpr(5) as u8 as i8 as i32;
    if (0x0200_0000..0x0204_0000).contains(&unit) && core.raw_read_8(unit + 1, -1) & 0x20 != 0 {
        let cut = crate::co_skills::hidden_fuel_cut(core, army);
        if cut != 0 {
            core.gba_mut().cpu_mut().set_gpr(5, (burn - cut).clamp(0, 127));
        }
    }
}

const CO_ABILITIES: u32 = 0x0300_3FC8;
const UNITS_POINTER: u32 = 0x0849_9594;

/// Dual Strike's `Player_GetFuelRate` for an army: 2 in snow, else 1; 1
/// for Olaf's army with CO abilities on. 1 without the pack.
pub fn fuel_rate(core: &Core, army: u32) -> u32 {
    if !is_on(core) || core.raw_read_8(WEATHER, -1) != SNOW {
        return 1;
    }
    let co = core.raw_read_8(crate::five::players(core) + 0x3C * army + 0x1D, -1);
    if core.raw_read_8(CO_ABILITIES, -1) != 0 && co == OLAF {
        1
    } else {
        2
    }
}

fn unit_army(core: &Core, unit: u32) -> u32 {
    let units = core.raw_read_32(UNITS_POINTER, -1);
    crate::five::army_of_index(core, unit.wrapping_sub(units) / 12)
}

/// The most squares a unit's fuel takes it (`Unit_GetMovePoints`: its fuel
/// / its army's [`fuel_rate`]).
pub fn reach(core: &Core, unit: u32) -> u32 {
    (core.raw_read_8(unit + 6, -1) & 0x7F) as u32 / fuel_rate(core, unit_army(core, unit))
}

/// `SubtractFuel(unit r0, amount r1)` (a move's fuel, the path's cost:
/// after a move, a shown path in fog, a join): Dual Strike's
/// `Unit_GetFuelUsed`, the cost x the owner's [`fuel_rate`], none for an
/// Oozium (the function's own "more than it has: 0" is Dual Strike's cap).
const MOVE_FUEL: u32 = 0x0802_5B80;
fn move_fuel(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (unit, amount) = (cpu.gpr(0) as u32, cpu.gpr(1) as u32 & 0xFF);
    let v = if core.raw_read_8(unit, -1) == crate::roster::OOZIUM {
        0
    } else {
        (amount * fuel_rate(core, unit_army(core, unit))).min(0xFF)
    };
    if v != amount {
        core.gba_mut().cpu_mut().set_gpr(1, v as i32);
    }
}

/// A unit's move for its range is chosen (r3: the smaller of its fuel and
/// its movement), for its unit in `reg`: at most [`reach`].
fn cap_reach(core: &mut Core, move_reg: usize, unit: u32) {
    if !is_on(core) || core.raw_read_8(WEATHER, -1) != SNOW {
        return;
    }
    let mv = core.gba().cpu().gpr(move_reg) as u32 & 0xFFFF;
    let cap = reach(core, unit);
    if mv > cap {
        core.gba_mut().cpu_mut().set_gpr(move_reg, cap as i32);
    }
}

/// `sub_080202A4(unit r6)`, the move range's flood (the player's and the
/// CPU's), its move in r3.
const RANGE_MOVE: u32 = 0x0802_0308;
fn range_move(core: &mut Core) {
    let unit = core.gba().cpu().gpr(6) as u32;
    cap_reach(core, 3, unit);
}

/// `sub_08058224(unit r4)`, the CPU's usable movement, at its return (r0).
const CPU_MOVE: u32 = 0x0805_824E;
fn cpu_move(core: &mut Core) {
    let unit = core.gba().cpu().gpr(4) as u32;
    cap_reach(core, 0, unit);
}

/// `sub_08038C98`, the move shown for the selected unit (r0, stored at
/// +0x44; the unit `**r6`).
const SHOWN_MOVE: u32 = 0x0803_8D34;
fn shown_move(core: &mut Core) {
    let p = core.gba().cpu().gpr(6) as u32;
    let unit = core.raw_read_32(p, -1);
    cap_reach(core, 0, unit);
}

// --- Olaf's snow --------------------------------------------------------

/// A power's weather (`sub_08035144(weather)`: Olaf's Blizzard and Winter
/// Fury bring snow, Drake's Typhoon rain). Dual Strike's power snow lasts
/// two days (`Weather_SetDays`: 2 for `WEATHER_POWER_SNOW`, 1 for any
/// other), AW2's one: AW2 ends a weather when every army has ended a turn
/// since it began (`sub_08035080`: each army's turn-end count, at
/// `0x03004494 + army - 1`, all equal); for power snow the first time they
/// are all equal starts the count again ([`day_all_equal`]).
const POWER_WEATHER: u32 = 0x0803_5144;
const POWER_SNOW: u32 = crate::ram_map::POWER_SNOW.0;
fn power_weather(core: &mut Core) {
    if is_on(core) {
        let snow = core.gba().cpu().gpr(0) as u8 == SNOW;
        core.raw_write_8(POWER_SNOW, -1, snow as u8);
    }
}

/// `sub_08035080`'s "every army's count is equal" return (r0 = 1); 0x080350D6
/// returns 0.
const DAY_ALL_EQUAL: u32 = 0x0803_50DA;
const DAY_NOT_YET: u32 = 0x0803_50D6;
const DAY_COUNTS: u32 = 0x0300_4494;
fn day_all_equal(core: &mut Core) {
    if !is_on(core) || core.raw_read_8(POWER_SNOW, -1) == 0 {
        return;
    }
    core.raw_write_8(POWER_SNOW, -1, 0);
    for k in 0..4 {
        core.raw_write_8(DAY_COUNTS + k, -1, 0);
    }
    core.gba_mut().cpu_mut().set_thumb_pc(DAY_NOT_YET);
}

/// A map starts: no power snow's second day carries over.
pub fn map_start(core: &mut Core) {
    if core.raw_read_8(POWER_SNOW, -1) != 0 {
        core.raw_write_8(POWER_SNOW, -1, 0);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (FUEL, Box::new(fuel)),
        (MOVE_FUEL, Box::new(move_fuel)),
        (RANGE_MOVE, Box::new(range_move)),
        (CPU_MOVE, Box::new(cpu_move)),
        (SHOWN_MOVE, Box::new(shown_move)),
        (POWER_WEATHER, Box::new(power_weather)),
        (DAY_ALL_EQUAL, Box::new(day_all_equal)),
    ]
}
