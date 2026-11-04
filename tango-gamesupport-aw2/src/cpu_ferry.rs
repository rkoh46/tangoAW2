//! The CPU's transports of the Dual Strike units: a Black Boat ferries foot soldiers across water, a Carrier takes in and
//! launches aircraft (docs/dev/cpu-unit-use.md).
//!
//! AW2's foot-soldier logic picks transports by type (APC, T Copter, Lander) and its Lander logic needs the beaches of a campaign
//! map; the Black Boat and the Carrier are neither, so they never carried anything for the computer. The loads and drops are made
//! here, as the player's would be, in emulated RAM (the same on both netplay peers, in replays and after a rollback), on the
//! records AW2's Load and Drop leave (measured with a player's own Load and Drop):
//!
//! - **Load**: the passenger's flags get `0x0B` (carried, acted), its cell becomes the transport's, its map cell is cleared; the
//!   transport's flags get `0x10` and the passenger's unit id goes into its first free cargo byte (record +7, +8).
//! - **Drop**: the passenger gets the free cell, the map cell, flags `0x01` (it has acted); the cargo byte is cleared, and the
//!   transport's `0x10` with the last passenger.
//!
//! **Black Boat.** The units that need it: the army's Infantry and Mechs that cannot reach any property that is not their
//! team's (or enemy HQ) over land ([`Ferry::land_to`], one reverse flood). The *landings* are shoal cells with a free,
//! standable land cell next to them from which the way to such a property is open: so a drop never strands anybody. The
//! *beach* is the shoal the first of those soldiers (lowest unit slot) reaches soonest, with the army's first Black Boat able
//! to sail there ([`survey`]). The soldiers walk to the beach ([`plan_foot`], the game's own planner), the boat sails there
//! ([`crate::cpu_units`]), loads those within a turn's walk of it when it stands on the beach (two at most), sails towards the
//! nearest landing and drops its cargo there the turn it is on one. With nothing to ferry it repairs, as before.
//!
//! **Carrier.** An aircraft with fuel or hit points low that can reach a friendly Carrier with room lands on it ([`plan_air`]):
//! the Carrier's turn-start resupply ([`crate::unit_actions`]) refuels and re-arms its cargo. A Carrier launches its cargo
//! ([`launch`]) when an enemy unit is within [`LAUNCH_RANGE`] of it and the cargo is fit (fuel and hit points over
//! [`FIT`] %): each aircraft to a free cell next to the Carrier, which it has acted on, and next turn it flies as any aircraft.

use mgba::core::Core;

use crate::ds_ai::*;
use crate::roster::{BLACK_BOAT, CARRIER};

const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const PLANES: [u32; 2] = [MAP + 0x12, MAP + 0x51A];
const FAR: i32 = 999;
const LOADED_FLAGS: u8 = 0x0B;
const HAS_CARGO: u8 = 0x10;
const MOVED: u8 = 0x01;

/// An enemy this close to a Carrier (Manhattan) makes it launch fit aircraft.
pub(crate) const LAUNCH_RANGE: i32 = 14;
/// Fuel and hit points (in %) that make aircraft fit to launch / not to need a landing.
const FIT: i32 = 60;
const NEEDS_LANDING: i32 = 40;

pub(crate) fn id_of(core: &Core, rec: u32) -> u32 {
    (rec - core.raw_read_32(UNITS_POINTER, -1)) / UNIT
}

fn rec_of(core: &Core, id: u32) -> u32 {
    core.raw_read_32(UNITS_POINTER, -1) + UNIT * id
}

pub(crate) fn set_cell(core: &mut Core, x: i32, y: i32, id: u8) {
    let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
    for plane in PLANES {
        core.raw_write_8(plane + row + x as u32, -1, id);
    }
}

/// (capacity, whether it carries type `t`) of transport type `tt`.
fn carries(core: &Core, tt: u8, t: u8) -> (u32, bool) {
    let ptr = core.raw_read_32(crate::roster::table(core) + 0x5C * tt as u32 + 0x14, -1);
    if !(0x0800_0000..0x0A00_0000).contains(&ptr) && !(0x0200_0000..0x0204_0000).contains(&ptr) {
        return (0, false);
    }
    (
        core.raw_read_8(ptr, -1) as u32,
        t < 25 && core.raw_read_8(ptr + 1 + t as u32, -1) != 0,
    )
}

/// The unit ids a transport record holds.
pub(crate) fn cargo(core: &Core, transport: u32) -> Vec<u32> {
    [7, 8]
        .iter()
        .map(|&o| core.raw_read_8(transport + o, -1) as u32)
        .filter(|&i| i != 0)
        .collect()
}

/// A Load as the game leaves it.
pub(crate) fn load(core: &mut Core, transport: u32, passenger: u32) -> bool {
    let Some(slot) = [7u32, 8].into_iter().find(|&o| core.raw_read_8(transport + o, -1) == 0) else {
        return false;
    };
    let id = id_of(core, passenger);
    let (x, y) = (
        core.raw_read_8(passenger + 2, -1) as i32,
        core.raw_read_8(passenger + 3, -1) as i32,
    );
    set_cell(core, x, y, 0);
    let (tx, ty) = (core.raw_read_8(transport + 2, -1), core.raw_read_8(transport + 3, -1));
    core.raw_write_8(passenger + 2, -1, tx);
    core.raw_write_8(passenger + 3, -1, ty);
    let f = core.raw_read_8(passenger + 1, -1);
    core.raw_write_8(passenger + 1, -1, f | LOADED_FLAGS);
    core.raw_write_8(transport + slot, -1, id as u8);
    let f = core.raw_read_8(transport + 1, -1);
    core.raw_write_8(transport + 1, -1, f | HAS_CARGO);
    true
}

/// A Drop as the game leaves it, onto cell `to`.
pub(crate) fn unload(core: &mut Core, transport: u32, passenger: u32, to: (i32, i32)) {
    let id = id_of(core, passenger);
    for o in [7u32, 8] {
        if core.raw_read_8(transport + o, -1) as u32 == id {
            core.raw_write_8(transport + o, -1, 0);
        }
    }
    if cargo(core, transport).is_empty() {
        let f = core.raw_read_8(transport + 1, -1);
        core.raw_write_8(transport + 1, -1, f & !HAS_CARGO);
    }
    core.raw_write_8(passenger + 2, -1, to.0 as u8);
    core.raw_write_8(passenger + 3, -1, to.1 as u8);
    core.raw_write_8(passenger + 1, -1, MOVED);
    set_cell(core, to.0, to.1, id as u8);
}

// --- Black Boat -----------------------------------------------------------------------------------

/// What a Black Boat's army has to ferry, and where.
pub(crate) struct Ferry {
    /// The army's first Black Boat (lowest record), the one that does the ferrying.
    pub boat: Option<Unit>,
    /// Foot soldiers that cannot walk to anything worth taking.
    pub needing: Vec<Unit>,
    /// The foot cost from each cell to the nearest property not of the army's team (-1: no way).
    pub land_to: Vec<i32>,
    /// A shoal cell's value as a landing: the foot cost left from its best free land neighbour (None: not a landing).
    pub landing: Vec<Option<i32>>,
    /// The shoal where the soldiers are picked up.
    pub beach: Option<usize>,
}

fn neighbours(b: &Board, i: usize) -> Vec<usize> {
    let (x, y) = (i as i32 % b.w, i as i32 / b.w);
    [(0, -1), (1, 0), (0, 1), (-1, 0)]
        .iter()
        .filter(|&&(dx, dy)| b.inside(x + dx, y + dy))
        .map(|&(dx, dy)| b.idx(x + dx, y + dy))
        .collect()
}

pub(crate) fn survey(core: &Core, b: &Board, army: u32) -> Option<Ferry> {
    let targets: Vec<usize> = (0..b.class.len())
        .filter(|&i| PROPERTIES.contains(&b.class[i]) && !b.team_owns(i, army))
        .collect();
    if targets.is_empty() {
        return None;
    }
    let hold = |u: &Unit| crate::ds_campaign::active(core) && core.raw_read_8(u.rec + 0x0B, -1) == 0;
    let land_to = crate::ds_ai_move::distance_to(b, army, INFANTRY, &targets);
    let mut mine: Vec<Unit> = b
        .units
        .iter()
        .filter(|u| u.army == army && !u.carried())
        .copied()
        .collect();
    mine.sort_by_key(|u| u.rec);
    let boat = mine.iter().find(|u| u.t == BLACK_BOAT).copied();
    let needing: Vec<Unit> = mine
        .iter()
        .filter(|u| matches!(u.t, INFANTRY | MECH) && land_to[b.idx(u.x, u.y)] < 0 && !hold(u))
        .copied()
        .collect();
    let mut landing = vec![None; b.class.len()];
    let mut any = false;
    for i in 0..b.class.len() {
        if b.class[i] != C_SHOAL {
            continue;
        }
        let best = neighbours(b, i)
            .into_iter()
            .filter(|&n| {
                b.cost(army, INFANTRY, n as i32 % b.w, n as i32 / b.w) != 0xFF && b.at[n] == 0 && land_to[n] >= 0
            })
            .map(|n| land_to[n])
            .min();
        if best.is_some() {
            landing[i] = best;
            any = true;
        }
    }
    if !any {
        return None;
    }
    let mut beach = None;
    if let (Some(f), Some(bt)) = (needing.first(), boat) {
        let reach_f = b.flood(army, f.t, f.x, f.y, FAR, false);
        let sea = b.flood(army, BLACK_BOAT, bt.x, bt.y, FAR, false);
        beach = (0..b.class.len())
            .filter(|&s| b.class[s] == C_SHOAL && (sea[s] >= 0 || s == b.idx(bt.x, bt.y)))
            .filter_map(|s| {
                neighbours(b, s)
                    .into_iter()
                    .filter(|&n| reach_f[n] >= 0)
                    .map(|n| reach_f[n] as i32)
                    .min()
                    .map(|c| (c, sea[s].max(0) as i32, s))
            })
            .min()
            .map(|(_, _, s)| s);
    }
    Some(Ferry {
        boat,
        needing,
        land_to,
        landing,
        beach,
    })
}

/// Before a Black Boat plays: its cargo is dropped where it stands on a landing; soldiers within a turn's walk board it where it
/// stands on a shoal. `true` when something was loaded or dropped (the caller reads the board again).
fn exchange(core: &mut Core, army: u32, rec: u32) -> bool {
    let mut changed = false;
    for _ in 0..2 {
        let b = Board::read(core);
        let Some(u) = b.units.iter().find(|u| u.rec == rec).copied() else {
            return changed;
        };
        let here = b.idx(u.x, u.y);
        if b.class[here] != C_SHOAL {
            return changed;
        }
        let Some(ferry) = survey(core, &b, army) else {
            return changed;
        };
        let held = cargo(core, rec);
        if !held.is_empty() && ferry.landing[here].is_some() {
            // Drop: each passenger onto the free neighbour with the way left shortest.
            let Some(&id) = held.first() else { return changed };
            let p = rec_of(core, id);
            let to = neighbours(&b, here)
                .into_iter()
                .filter(|&n| {
                    b.cost(army, if u.t == BLACK_BOAT { INFANTRY } else { core.raw_read_8(p, -1) }, n as i32 % b.w, n as i32 / b.w) != 0xFF
                        && b.at[n] == 0
                        && ferry.land_to[n] >= 0
                })
                .min_by_key(|&n| (ferry.land_to[n], n));
            if let Some(n) = to {
                if crate::ds_ai::logging() {
                    crate::ds_ai::log(&format!(
                        "dsai ferry day {} army {army}: the Black Boat at ({},{}) drops a soldier at ({},{})",
                        b.day,
                        u.x,
                        u.y,
                        n as i32 % b.w,
                        n as i32 / b.w
                    ));
                }
                unload(core, rec, p, (n as i32 % b.w, n as i32 / b.w));
                changed = true;
                continue;
            }
            return changed;
        }
        let (cap, _) = carries(core, BLACK_BOAT, INFANTRY);
        if u.t == BLACK_BOAT && (held.len() as u32) < cap {
            // Board: a soldier that needs the ferry, unmoved, whose walk reaches the boat's neighbour (or already is).
            let next = ferry.needing.iter().find(|f| {
                if f.flags & MOVED != 0 || !carries(core, BLACK_BOAT, f.t).1 {
                    return false;
                }
                let fuel = (core.raw_read_8(f.rec + 6, -1) & 0x7F) as i32;
                let reach = b.flood(army, f.t, f.x, f.y, b.moves(army, f.t).min(fuel), false);
                neighbours(&b, here)
                    .into_iter()
                    .any(|n| n == b.idx(f.x, f.y) || (reach[n] >= 0 && b.at[n] == 0))
            });
            if let Some(f) = next {
                if crate::ds_ai::logging() {
                    crate::ds_ai::log(&format!(
                        "dsai ferry day {} army {army}: the Black Boat at ({},{}) takes the soldier at ({},{})",
                        b.day, u.x, u.y, f.x, f.y
                    ));
                }
                if load(core, rec, f.rec) {
                    changed = true;
                    continue;
                }
            }
        }
        return changed;
    }
    changed
}

/// The cells a Black Boat heads for: its landings while it carries soldiers, else the beach where soldiers wait.
pub(crate) fn mission(core: &Core, b: &Board, army: u32, u: &Unit) -> Option<(Vec<usize>, &'static str)> {
    let ferry = survey(core, b, army)?;
    if !cargo(core, u.rec).is_empty() {
        let cells: Vec<usize> = (0..ferry.landing.len())
            .filter(|&i| ferry.landing[i].is_some())
            .collect();
        return Some((cells, "the landing with its soldiers"));
    }
    if ferry.boat.is_some_and(|f| f.rec == u.rec) {
        return ferry.beach.map(|s| (vec![s], "the beach for soldiers"));
    }
    None
}

/// A foot soldier that needs the ferry walks to the beach: the cell it goes to (None: it plays as AW2 plays it).
pub(crate) fn plan_foot(core: &Core, rec: u32) -> Option<(i32, i32)> {
    let army = current_army(core);
    if !in_scope(core, army, OFF_MOVE) || !matches!(core.raw_read_8(rec, -1), 1 | 2) {
        return None;
    }
    let b = Board::read(core);
    let u = b.units.iter().find(|u| u.rec == rec).copied()?;
    if u.army != army || u.carried() || u.flags & MOVED != 0 {
        return None;
    }
    let ferry = survey(core, &b, army)?;
    if !ferry.needing.iter().any(|f| f.rec == rec) {
        return None;
    }
    let beach = ferry.beach?;
    let spots: Vec<usize> = neighbours(&b, beach)
        .into_iter()
        .filter(|&n| b.cost(army, u.t, n as i32 % b.w, n as i32 / b.w) != 0xFF)
        .collect();
    let here = b.idx(u.x, u.y);
    if spots.contains(&here) {
        return None;
    }
    let to = crate::ds_ai_move::distance_to(&b, army, u.t, &spots);
    let fuel = (core.raw_read_8(u.rec + 6, -1) & 0x7F) as i32;
    let reach = b.flood(army, u.t, u.x, u.y, b.moves(army, u.t).min(fuel), false);
    let pick = (0..reach.len())
        .filter(|&i| reach[i] >= 0 && b.at[i] == 0 && to[i] >= 0 && (to[here] < 0 || to[i] < to[here]))
        .min_by_key(|&i| (to[i], i))?;
    Some((pick as i32 % b.w, pick as i32 / b.w))
}

// --- Carrier ---------------------------------------------------------------------------------------

fn percent(core: &Core, u: &Unit) -> (i32, i32) {
    let stats = crate::roster::table(core) + 0x5C * u.t as u32;
    let fuel_max = (core.raw_read_8(stats + 0x10, -1) & 0x7F) as i32;
    let fuel = (core.raw_read_8(u.rec + 6, -1) & 0x7F) as i32;
    (if fuel_max > 0 { fuel * 100 / fuel_max } else { 100 }, u.hp)
}

/// The start of a CPU army's turn, before its units are played ([`crate::cpu_tactics::cpu_unit`]: the game's unit queue lifts a
/// unit off the map while it plays it, so a Load or a Drop cannot be made in the middle of a unit's play; the units made
/// to act here carry the acted flag and the queue passes them by): Black Boats drop and take soldiers, Carriers launch fit
/// aircraft, aircraft low on fuel or hit points land on a Carrier.
pub(crate) fn turn_start(core: &mut Core, army: u32) {
    if !in_scope(core, army, OFF_MOVE) {
        return;
    }
    let b = Board::read(core);
    let mine: Vec<(u32, u8)> = b
        .units
        .iter()
        .filter(|u| u.army == army && !u.carried())
        .map(|u| (u.rec, u.t))
        .collect();
    drop(b);
    for &(rec, t) in &mine {
        if t == BLACK_BOAT || (t == LANDER && crate::custom_campaign::ferry_landers(core) && !cargo(core, rec).is_empty()) {
            exchange(core, army, rec);
        }
    }
    for &(rec, t) in &mine {
        if t == CARRIER {
            launch(core, army, rec);
        }
    }
    for &(rec, t) in &mine {
        if stats(t).group & AIR != 0 && t != CARRIER {
            plan_air(core, rec);
        }
    }
}

/// An aircraft low on fuel or hit points lands on a friendly Carrier it can reach, with room for it. `true` when it did.
fn plan_air(core: &mut Core, rec: u32) -> bool {
    let army = current_army(core);
    let t = core.raw_read_8(rec, -1);
    if !in_scope(core, army, OFF_MOVE) || stats(t).group & AIR == 0 {
        return false;
    }
    let b = Board::read(core);
    let Some(u) = b.units.iter().find(|u| u.rec == rec).copied() else {
        return false;
    };
    if u.army != army || u.carried() || u.flags & MOVED != 0 {
        return false;
    }
    let (fuel, hp) = percent(core, &u);
    if fuel > NEEDS_LANDING && hp > NEEDS_LANDING {
        return false;
    }
    let fuel_left = (core.raw_read_8(rec + 6, -1) & 0x7F) as i32;
    let reach = b.flood(army, u.t, u.x, u.y, b.moves(army, u.t).min(fuel_left), false);
    let ship = b
        .units
        .iter()
        .filter(|c| c.army == army && c.t == CARRIER && !c.carried())
        .filter(|c| {
            let (cap, ok) = carries(core, CARRIER, u.t);
            ok && (cargo(core, c.rec).len() as u32) < cap && reach[b.idx(c.x, c.y)] >= 0
        })
        .min_by_key(|c| (reach[b.idx(c.x, c.y)], c.rec))
        .copied();
    let Some(c) = ship else { return false };
    if crate::ds_ai::logging() {
        crate::ds_ai::log(&format!(
            "dsai ferry day {} army {army}: {} at ({},{}) lands on the Carrier at ({},{}) (fuel {fuel}%, hp {hp})",
            b.day,
            crate::bh_smart::NAMES[u.t as usize % 28],
            u.x,
            u.y,
            c.x,
            c.y
        ));
    }
    load(core, c.rec, rec)
}

/// A Carrier's cargo is launched when an enemy is within [`LAUNCH_RANGE`] and the aircraft are fit.
fn launch(core: &mut Core, army: u32, rec: u32) {
    let held = cargo(core, rec);
    if held.is_empty() {
        return;
    }
    let b = Board::read(core);
    let Some(c) = b.units.iter().find(|u| u.rec == rec).copied() else {
        return;
    };
    let near = b.units.iter().any(|e| {
        !e.carried()
            && b.playing[e.army as usize % 6]
            && !b.same_team(e.army, army)
            && (e.x - c.x).abs() + (e.y - c.y).abs() <= LAUNCH_RANGE
    });
    if !near {
        return;
    }
    for id in held {
        let p = rec_of(core, id);
        let t = core.raw_read_8(p, -1);
        let pu = Unit {
            rec: p,
            army,
            t,
            x: c.x,
            y: c.y,
            hp: (core.raw_read_16(p + 4, -1) & 0x7F) as i32,
            flags: 0,
        };
        let (fuel, hp) = percent(core, &pu);
        if fuel < FIT || hp < FIT {
            continue;
        }
        let b = Board::read(core);
        let to = neighbours(&b, b.idx(c.x, c.y))
            .into_iter()
            .filter(|&n| b.cost(army, t, n as i32 % b.w, n as i32 / b.w) != 0xFF && b.at[n] == 0)
            .min();
        if let Some(n) = to {
            if crate::ds_ai::logging() {
                crate::ds_ai::log(&format!(
                    "dsai ferry day {} army {army}: the Carrier at ({},{}) launches its {} to ({},{})",
                    b.day,
                    c.x,
                    c.y,
                    crate::bh_smart::NAMES[t as usize % 28],
                    n as i32 % b.w,
                    n as i32 / b.w
                ));
            }
            unload(core, rec, p, (n as i32 % b.w, n as i32 / b.w));
        }
    }
}
