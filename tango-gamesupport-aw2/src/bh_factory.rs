//! The Black Factory in Versus with the Dual Strike pack: its spawns also
//! take Dual Strike's units, and ships next to the sea.
//!
//! AW2's factory spawner (`0x080607E8`, see [`crate::factory`]) walks the
//! three door tiles under the factory (x..x+2, y+4) each turn; for each one
//! that is empty it reads the unit type from the map's table
//! (`table[(day & 0x1F) * 3 + slot]`, 0 = none) and calls create-unit at
//! `0x08060856` with r0 = x, r1 = y, r2 = the type (r5 holds it too, for
//! the AI group call that follows). Which slots spawn something, and how
//! many, stays the table's: this module only changes what a slot spawns.
//!
//! A trap at that create call (Versus, with the pack, not the DS Campaign)
//! picks, from a hash of the day, the slot, the army and the factory's
//! square (RAM only: no RNG is touched, so the spawner draws what it drew
//! before, and rollback and both netplay peers agree):
//! - half the time the table's own unit;
//! - a quarter of the time a Dual Strike land unit (Megatank, Oozium, and a
//!   Piperunner when a pipe is by the door);
//! - a quarter of the time a ship (Lander, Cruiser, Battleship, Sub, Black
//!   Boat, Carrier) when one can be placed, else a land unit.
//!
//! A unit is only placed where its movement chart lets it in and the square
//! is empty: a ship on a door tile or the square beside a door tile (the
//! door row's two ends, the row under the doors) that is sea, reef or shoal
//! as that ship allows; a land unit on its own door tile, never on sea or
//! reef. When no square is free the table's unit spawns, as before; the
//! table's unit on sea or reef is dropped. A blocked door tile still blocks
//! its slot (the spawner checks it before this trap).

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

fn at_create(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (x, y, table_unit, slot) = (cpu.gpr(0), cpu.gpr(1), cpu.gpr(5) as u32 as u8, cpu.gpr(7));
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    let day = core.raw_read_16(DAY, -1) as u32;
    let door_x = x - slot;
    let map = core.raw_read_8(MAP_ID, -1) as u32;
    let h = hash(&[day, slot as u32, army, door_x as u32, y as u32, map]);

    // A type with a square, picked evenly, then one of its squares.
    let pick = |units: &[u8], h: u32| -> Option<(u8, i32, i32)> {
        let options: Vec<(u8, Vec<(i32, i32)>)> = units
            .iter()
            .map(|&t| (t, squares(core, army, t, door_x, x, y)))
            .filter(|(_, spots)| !spots.is_empty())
            .collect();
        let (t, spots) = options.get((h >> 8) as usize % options.len().max(1))?;
        let (sx, sy) = spots[(h >> 16) as usize % spots.len()];
        Some((*t, sx, sy))
    };
    let land = pick(&[MEGATANK, OOZIUM, PIPERUNNER], h);
    let ships = pick(&SHIPS, h.rotate_left(7));
    let chosen = match h & 7 {
        4 | 5 => land,
        6 | 7 => ships.or(land),
        _ => None,
    };
    // The table's unit stays unless a Dual Strike one was picked, and it
    // never stands on sea or reef.
    let (t, px, py) = chosen.unwrap_or((table_unit, x, y));
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
