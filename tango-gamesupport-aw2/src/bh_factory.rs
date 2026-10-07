//! The Black Factory in Versus with the Dual Strike pack: what its doors
//! spawn is chosen from the battle as it is now ([`crate::bh_smart`]), and
//! it can be destroyed ([`crate::factory_hp`]).
//!
//! AW2's factory spawner (`0x080607E8`, see [`crate::factory`]) walks the
//! three door tiles under the factory (x..x+2, y+4) each turn; for each one
//! that is empty it reads the unit type from the map's table
//! (`table[(day & 0x1F) * 3 + slot]`, 0 = none) and calls create-unit at
//! `0x08060856` with r0 = x, r1 = y, r2 = the type (r5 holds it too, for
//! the AI group call that follows). Which slots spawn something, and how
//! many, stays the table's: this module only changes what a slot spawns.
//!
//! A trap at that create call (Versus, with the pack, not the DS Campaign;
//! for a human Black Hole army's detour and the CPU's turn alike, whichever
//! army is moving) lists the units that may be placed now, and
//! [`crate::bh_smart::choose`] ranks them by what the battle needs (the
//! scoring is in that module and docs/AW2.md). It reads RAM and ROM only: no
//! RNG is touched (the spawner draws what it drew before), so rollback and
//! both netplay peers agree.
//!
//! What may be placed:
//! - the candidates are the land units, three air units and the ships;
//! - the cost rule ([`HEAVY`]);
//! - a unit is only placed where its movement chart lets it in and the
//!   square is empty: a ship on a door tile or the square beside a door
//!   tile (the door row's two ends, the row under the doors) that is sea,
//!   reef or shoal as that ship allows; a land or air unit on its own door
//!   tile, never on sea or reef (air units never on a door tile in the
//!   water). With no candidate the table's unit spawns as before (dropped
//!   if it would stand on sea or reef). A blocked door tile still blocks its
//!   slot (the spawner checks it before this trap).
//! - a destroyed factory spawns nothing.

use mgba::core::Core;

use crate::ds_weather::is_on;
use crate::roster::{BLACK_BOAT, CARRIER, MEGATANK, OOZIUM, PIPERUNNER};

/// The spawner's create-unit call, and the loop's next slot.
const CREATE: u32 = 0x0806_0856;
const NEXT_SLOT: u32 = 0x0806_086E;
const DAY: u32 = 0x0300_4080;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const TERRAIN_PLANE: u32 = MAP + 0x1432;
const MAP_ID: u32 = 0x0300_3FC2;

const LANDER: u8 = 23;
const CRUISER: u8 = 22;
const BATTLESHIP: u8 = 21;
const SUB: u8 = 24;
const SHIPS: [u8; 6] = [LANDER, CRUISER, BATTLESHIP, SUB, BLACK_BOAT, CARRIER];
const SEA: u8 = 7;
const REEF: u8 = 19;
const NO_ENTRY: u8 = 0xFF;
/// A development hook for balance runs (`tools/aw2test`): while this byte of
/// free RAM is non-zero the factory spawns the table's units, as AW2's does.
/// It is emulated memory, so it replays and rolls back like the rest.
const TABLE_ONLY: u32 = 0x0203_E3FF;

fn in_scope(core: &Core) -> bool {
    is_on(core) && crate::pvp::in_versus(core) && !crate::ds_campaign::active(core)
}

fn hash(parts: &[u32]) -> u32 {
    let mut h: u32 = 0x811C_9DC5;
    for p in parts {
        h ^= p.wrapping_mul(0x9E37_79B1);
        h = h.rotate_left(13).wrapping_mul(0x85EB_CA6B);
        h ^= h >> 16;
    }
    h ^= h >> 15;
    h = h.wrapping_mul(0x2C1B_3C6D);
    h ^ (h >> 12)
}

fn terrain(core: &Core, x: i32, y: i32) -> Option<u8> {
    let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
    if x < 0 || y < 0 || x >= w || y >= h {
        return None;
    }
    let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
    Some(core.raw_read_8(TERRAIN_PLANE + row + x as u32, -1) & 0x1F)
}

/// `t` may stand on (x, y) now: on the map, empty, and its movement chart
/// lets it in.
fn open(core: &Core, army: u32, t: u8, x: i32, y: i32) -> bool {
    terrain(core, x, y).is_some()
        && crate::unit_actions::unit_at(core, x, y).is_none()
        && crate::oozium::move_cost(core, army, t, x, y) != NO_ENTRY
}

/// The squares a ship or Piperunner of the factory with doors at
/// (door_x.., y) may be placed on, row by row: the door row and its two
/// ends, then the row under it.
fn around(door_x: i32, y: i32) -> Vec<(i32, i32)> {
    let mut out: Vec<(i32, i32)> = (door_x - 1..=door_x + 3).map(|x| (x, y)).collect();
    out.extend((door_x..door_x + 3).map(|x| (x, y + 1)));
    out
}

/// Where a unit of type `t` could be placed for the slot whose door tile is
/// (x, y).
fn squares(core: &Core, army: u32, t: u8, door_x: i32, x: i32, y: i32) -> Vec<(i32, i32)> {
    if SHIPS.contains(&t) || t == PIPERUNNER {
        around(door_x, y).into_iter().filter(|&(sx, sy)| open(core, army, t, sx, sy)).collect()
    } else if open(core, army, t, x, y) {
        vec![(x, y)]
    } else {
        Vec::new()
    }
}

/// What the factory may pick from: land (on the door tile), air (likewise,
/// but never over water), ships and the Piperunner (squares beside the doors).
const LAND: [u8; 13] = [1, 2, 3, MEGATANK, 5, 6, 8, PIPERUNNER, 10, 11, 14, 15, OOZIUM];
const AIR: [u8; 3] = [16, 17, 19];

fn price(core: &Core, t: u8) -> i32 {
    core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as i32 * 10
}

/// The cost rule (the factory is not a free army): a spawn is never dearer
/// than the table's unit for that day and slot, so over any stretch of days
/// the factory spawns no more value than AW2's table would. The [`HEAVY`]
/// units (Megatank, Battleship, Carrier, Oozium) may cost up to 30% more
/// than the slot's unit (in practice they take the place of a big table
/// unit), and only one of each may stand on Black Hole's side at a time.
const HEAVY: [u8; 4] = [MEGATANK, 21, CARRIER, OOZIUM];

pub(crate) fn log(line: &str) {
    use std::io::Write;
    static PATH: std::sync::OnceLock<Option<String>> = std::sync::OnceLock::new();
    if let Some(p) = PATH.get_or_init(|| std::env::var("TANGOAW2_BH_LOG").ok()) {
        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(p) {
            let _ = writeln!(f, "{line}");
        }
    }
}

fn at_create(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    // A destroyed factory spawns nothing.
    if crate::factory_hp::destroyed(core) {
        core.gba_mut().cpu_mut().set_thumb_pc(NEXT_SLOT);
        return;
    }
    if core.raw_read_8(TABLE_ONLY, -1) != 0 {
        return;
    }
    let cpu = core.gba().cpu();
    let (x, y, table_unit, slot) = (cpu.gpr(0), cpu.gpr(1), cpu.gpr(5) as u32 as u8, cpu.gpr(7));
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    let day = core.raw_read_16(DAY, -1) as u32;
    let door_x = x - slot;
    let map = core.raw_read_8(MAP_ID, -1) as u32;
    let h = hash(&[day, slot as u32, army, door_x as u32, y as u32, map]);

    let cap = price(core, table_unit);
    let door_water = matches!(terrain(core, x, y), Some(SEA) | Some(REEF));
    let mut options: Vec<(u8, Vec<(i32, i32)>)> = Vec::new();
    for &t in LAND.iter().chain(AIR.iter()).chain(SHIPS.iter()) {
        if AIR.contains(&t) && door_water {
            continue;
        }
        let cost = price(core, t);
        let allowed = if HEAVY.contains(&t) { cost * 10 <= cap * 13 } else { cost <= cap };
        if !allowed {
            continue;
        }
        let spots = squares(core, army, t, door_x, x, y);
        if !spots.is_empty() {
            options.push((t, spots));
        }
    }
    let started = std::time::Instant::now();
    let decision = crate::bh_smart::choose(core, army, door_x, y, &options, &HEAVY);
    let micros = started.elapsed().as_micros();
    let (t, px, py) = match &decision {
        Some(d) => {
            let spots = &options.iter().find(|o| o.0 == d.best.t).unwrap().1;
            let (sx, sy) = crate::bh_smart::nearest_spot(core, army, door_x, y, spots, h >> 8);
            (d.best.t, sx, sy)
        }
        None => (table_unit, x, y),
    };
    if let Some(d) = &decision {
        let why: Vec<String> = d.best.parts.iter().take(3).map(|p| format!("{} {:+}", p.0, p.1)).collect();
        let next: Vec<String> = d.next.iter().map(|n| format!("{} {}", crate::bh_smart::NAMES[n.0 as usize], n.1)).collect();
        log(&format!(
            "day {day} army {army} slot {slot} table {} -> {} at ({px},{py}) score {} | {} | then {} | {} | {micros} us",
            crate::bh_smart::NAMES[table_unit as usize],
            crate::bh_smart::NAMES[t as usize],
            d.best.total,
            why.join("; "),
            next.join(", "),
            d.summary
        ));
    }
    // The table's unit never stands on sea or reef.
    let on_water = !SHIPS.contains(&t) && matches!(terrain(core, px, py), Some(SEA) | Some(REEF));
    let cpu = core.gba_mut().cpu_mut();
    if on_water {
        cpu.set_thumb_pc(NEXT_SLOT);
        return;
    }
    cpu.set_gpr(0, px);
    cpu.set_gpr(1, py);
    cpu.set_gpr(2, t as i32);
    cpu.set_gpr(5, t as i32);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(CREATE, Box::new(at_create))]
}
