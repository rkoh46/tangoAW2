//! The CPU uses the Dual Strike units AW2's role moves leave where they stand (docs/dev/cpu-unit-use.md).
//!
//! AW2's driver moves a unit by its role (`AiRunRoleMove`), and its role code knows the AW2 unit types: a Black
//! Boat or a Carrier, whatever its role, never left the port it was built on (the Gauntlet's Cinder Sea fleets sat
//! in their ports for good, and a boat on the port also keeps the port from building). Here, for the units of
//! [`handles`], the place the unit goes this turn is chosen from the battle in emulated RAM and handed to AW2's
//! "move towards a place" ([`crate::ds_ai_move::role_move`] writes it, the mechanism [`crate::cpu_inventions`]
//! proved). Everything is read from RAM and ROM: the same on both netplay peers, in replays and after a rollback.
//!
//! - **Black Boat**: it goes where its Repair is worth most (its army's damaged units next to the cell, one HP
//!   each while funds last, [`crate::unit_actions::repair_around`], and units short of ammo or fuel, which the
//!   Repair also supplies); with none in reach it goes towards the nearest damaged unit of its army, else the
//!   nearest warship, else any unit of its army; a cell where an enemy could hurt it too much
//!   ([`crate::ds_ai_move::threat_maps`], the limits of its profile) is avoided and, when its own cell is
//!   unsafe, it retreats to the safest. It never ends a turn on a base, port or airport of its team where it
//!   can stand anywhere else: that blocks the building.
//! - **Carrier**: the threat-aware advance of a combat unit on the nearest enemy it can hit (aircraft), else
//!   the enemy HQ; where the way is blocked it drifts towards the nearest enemy; never parked on a port.
//!
//! The Lander and the APC keep AW2's own loading and unloading logic (the boats' cargo is not planned here).

use mgba::core::Core;

use crate::ds_ai::*;
use crate::roster::{BLACK_BOAT, CARRIER};

const MISSILES: u8 = 15;

/// The unit types this module moves.
pub(crate) fn handles(t: u8) -> bool {
    matches!(t, CARRIER | MISSILES)
}

/// The unit queue is about to run the attack check for the current unit ([`crate::cpu_defend::check`]): a Black
/// Boat (role 2 in AW2's table, the APC's, which AW2 never moves with the role code) goes where [`boat`] says.
/// `Some(cell)` when it moves.
pub(crate) fn plan(core: &mut Core, rec: u32) -> Option<(i32, i32)> {
    let army = current_army(core);
    let t = core.raw_read_8(rec, -1);
    if !matches!(t, BLACK_BOAT | LANDER)
        || core.raw_read_8(rec + 1, -1) & 1 != 0
        || !in_scope(core, army, OFF_MOVE)
        || crate::custom_campaign::driven_goal(core, rec).is_some()
    {
        return None;
    }
    let roll = profile_roll(core, army);
    let b = Board::read(core);
    let u = b.units.iter().find(|u| u.rec == rec).copied()?;
    if u.army != army || u.carried() {
        return None;
    }
    // (a Lander is AW2's to move, loading and unloading, except where it sits idle on a port of its own: it then
    // steps off, towards its soldiers, so the port can build)
    if t == LANDER
        && (!on_production(&b, army, b.idx(u.x, u.y))
            || core.raw_read_8(rec + 7, -1) != 0
            || core.raw_read_8(rec + 8, -1) != 0)
    {
        return None;
    }
    let (cell, note) = boat(core, &b, army, &u, roll)?;
    if logging() {
        log(&format!("dsai move day {} army {army} {note}", b.day));
    }
    ((cell.0, cell.1) != (u.x, u.y)).then_some(cell)
}

const NEIGHBOURS: [(i32, i32); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];

/// A base, port or airport of the army's team: standing on it blocks building there.
fn on_production(b: &Board, army: u32, i: usize) -> bool {
    b.team_owns(i, army) && matches!(b.class[i], C_BASE | C_PORT | C_AIRPORT)
}

fn low_on_supplies(core: &Core, o: &Unit) -> bool {
    let stats = crate::roster::table(core) + 0x5C * o.t as u32;
    let ammo_max = core.raw_read_8(stats + 0x0B, -1) as u16 & 0xF;
    let fuel_max = (core.raw_read_8(stats + 0x10, -1) & 0x7F) as i32;
    let ammo = (core.raw_read_16(o.rec + 4, -1) >> 7) & 0xF;
    let fuel = (core.raw_read_8(o.rec + 6, -1) & 0x7F) as i32;
    (ammo_max > 0 && ammo * 2 <= ammo_max) || (fuel_max > 0 && fuel * 2 <= fuel_max)
}

/// What a Repair at cell `i` is worth to `army`'s boat `u`, in funds: 1 HP of every damaged unit of its army
/// next to the cell (while the funds last), and a little for units it would resupply.
fn repair_worth(core: &Core, b: &Board, army: u32, u: &Unit, i: usize) -> i32 {
    let (x, y) = (i as i32 % b.w, i as i32 / b.w);
    let mut funds = funds(core, army) as i64;
    let mut worth = 0i32;
    for (dx, dy) in NEIGHBOURS {
        let Some(o) = b.unit_at(x + dx, y + dy) else { continue };
        if o.rec == u.rec || o.army != army || o.carried() {
            continue;
        }
        let cost = crate::co_powers::value_per_hp(core, army, o.t) as i64;
        if o.hp < 91 && funds >= cost {
            funds -= cost;
            worth += cost as i32 + 200;
        }
        if low_on_supplies(core, o) {
            worth += 300;
        }
    }
    worth
}

/// The cells next to the units `pick` selects.
fn cells_next_to(b: &Board, units: impl Iterator<Item = (i32, i32)>) -> Vec<usize> {
    let mut out = Vec::new();
    for (x, y) in units {
        for (dx, dy) in NEIGHBOURS {
            if b.inside(x + dx, y + dy) {
                out.push(b.idx(x + dx, y + dy));
            }
        }
    }
    out.sort_unstable();
    out.dedup();
    out
}

/// The cell unit `u` (a [`handles`] type) of `army` goes to, and why.
pub(crate) fn choose(core: &Core, b: &Board, army: u32, u: &Unit, role: u8, roll: u32) -> Option<((i32, i32), String)> {
    match u.t {
        BLACK_BOAT => boat(core, b, army, u, roll),
        _ => carrier(core, b, army, u, role, roll),
    }
}

/// The reach, the limits and the threat maps both share.
struct Ground {
    cells: Vec<usize>,
    here: usize,
    tmax: Vec<u8>,
    tsum: Vec<u8>,
    max_limit: u8,
    sum_limit: u8,
}

impl Ground {
    fn new(core: &Core, b: &Board, army: u32, u: &Unit, roll: u32) -> Option<Ground> {
        let fuel = (core.raw_read_8(u.rec + 6, -1) & 0x7F) as i32;
        let moves = b.moves(army, u.t).min(fuel);
        let reach = b.flood(army, u.t, u.x, u.y, moves, false);
        let prof = profile(army_co(core, army).0)?;
        let up = crate::ds_ai_move::limits_of(&prof, u.t);
        let (tmax, tsum) = crate::ds_ai_move::threat_maps(core, b, army, u.t, u.x, u.y, moves);
        let here = b.idx(u.x, u.y);
        let cells = (0..reach.len())
            .filter(|&i| reach[i] >= 0 && (b.at[i] == 0 || i == here))
            .collect();
        Some(Ground {
            cells,
            here,
            tmax,
            tsum,
            max_limit: randomise(up.threat_max.0, up.threat_max.1, roll),
            sum_limit: randomise(up.threat_sum.0, up.threat_sum.1, roll),
        })
    }

    fn safe(&self, i: usize) -> bool {
        self.tmax[i] < self.max_limit && self.tsum[i] < self.sum_limit
    }

    fn danger(&self, i: usize) -> i32 {
        self.tmax[i] as i32 + 2 * self.tsum[i] as i32
    }
}

fn xy(b: &Board, i: usize) -> (i32, i32) {
    (i as i32 % b.w, i as i32 / b.w)
}

fn boat(core: &Core, b: &Board, army: u32, u: &Unit, roll: u32) -> Option<((i32, i32), String)> {
    let g = Ground::new(core, b, army, u, roll)?;
    // Where to head when no Repair is in reach: damaged units of its army, else its warships, else any unit of its army.
    let mine = || {
        b.units
            .iter()
            .filter(|o| o.army == army && o.rec != u.rec && !o.carried())
    };
    let repairs = u.t == BLACK_BOAT;
    let hurt: Vec<(i32, i32)> = mine()
        .filter(|o| {
            if repairs {
                o.hp < 91
            } else {
                matches!(o.t, INFANTRY | MECH)
            }
        })
        .map(|o| (o.x, o.y))
        .collect();
    let fleet: Vec<(i32, i32)> = mine()
        .filter(|o| stats(o.t).group & SEA != 0 && attack(o.t) != Attack::None)
        .map(|o| (o.x, o.y))
        .collect();
    let any: Vec<(i32, i32)> = mine().map(|o| (o.x, o.y)).collect();
    let (targets, what) = if !hurt.is_empty() {
        (
            cells_next_to(b, hurt.into_iter()),
            if repairs { "damaged units" } else { "its soldiers" },
        )
    } else if !fleet.is_empty() {
        (cells_next_to(b, fleet.into_iter()), "its fleet")
    } else {
        (cells_next_to(b, any.into_iter()), "its army")
    };
    let to = crate::ds_ai_move::distance_to(b, army, u.t, &targets);
    let worth = |i: usize| if repairs { repair_worth(core, b, army, u, i) } else { 0 };
    let score = |i: usize| -> i64 {
        let mut s = worth(i) as i64 * 4;
        if on_production(b, army, i) {
            s -= 100_000;
        }
        if !g.safe(i) {
            s -= 30_000 + 100 * g.danger(i) as i64;
        } else {
            s -= g.danger(i) as i64;
        }
        if to[i] >= 0 {
            s -= 10 * to[i] as i64;
        } else {
            s -= 2_000;
        }
        s += crate::ds_ai_move::stars(core, b.class[i]) as i64;
        s
    };
    let pick = g
        .cells
        .iter()
        .copied()
        .max_by_key(|&i| (score(i), std::cmp::Reverse(i)))?;
    let why = if worth(pick) > 0 {
        "repairs here"
    } else if !g.safe(g.here) && g.safe(pick) {
        "retreats"
    } else if on_production(b, army, g.here) && !on_production(b, army, pick) {
        "leaves the port"
    } else {
        what
    };
    let (x, y) = xy(b, pick);
    Some((
        (x, y),
        format!(
            "{} at ({},{}): ({x},{y}) {why} (repair worth {}, danger {}, {} away from {what})",
            crate::bh_smart::NAMES[u.t as usize % 28],
            u.x,
            u.y,
            worth(pick),
            g.danger(pick),
            to[pick]
        ),
    ))
}

fn carrier(core: &Core, b: &Board, army: u32, u: &Unit, role: u8, roll: u32) -> Option<((i32, i32), String)> {
    if let Some(c) = crate::ds_ai_move::choose(core, b, army, u, if role == 0 { 4 } else { role }, roll) {
        if !(on_production(b, army, b.idx(c.0 .0, c.0 .1)) && (c.0 .0, c.0 .1) != (u.x, u.y)) {
            return Some((c.0, c.1));
        }
    }
    drift(core, b, army, u, roll)
}

/// A unit whose target the sea (or its fuel) does not reach this turn: it drifts towards the nearest enemy unit
/// (else enemy HQ or property) over the safe cells it can reach, never closer than 3 to a foe while it can help it,
/// never onto a port, base or airport of its team: the turn is not spent in a harbour.
pub(crate) fn drift(core: &Core, b: &Board, army: u32, u: &Unit, roll: u32) -> Option<((i32, i32), String)> {
    let g = Ground::new(core, b, army, u, roll)?;
    let mut foes: Vec<(i32, i32)> = b
        .units
        .iter()
        .filter(|e| !e.carried() && b.playing[e.army as usize % 6] && !b.same_team(e.army, army))
        .map(|e| (e.x, e.y))
        .collect();
    if foes.is_empty() {
        foes = (0..b.class.len())
            .filter(|&i| b.owner[i] != 0 && !b.team_owns(i, army) && b.class[i] == C_HQ)
            .map(|i| xy(b, i))
            .collect();
    }
    if foes.is_empty() {
        return None;
    }
    let gap = |i: usize| {
        let (x, y) = xy(b, i);
        foes.iter()
            .map(|&(fx, fy)| (fx - x).abs() + (fy - y).abs())
            .min()
            .unwrap_or(0)
    };
    let pick = g
        .cells
        .iter()
        .copied()
        .filter(|&i| g.safe(i))
        .min_by_key(|&i| (on_production(b, army, i), gap(i).max(3), g.danger(i), i))?;
    if pick == g.here {
        return None;
    }
    let (x, y) = xy(b, pick);
    Some((
        (x, y),
        format!(
            "{} at ({},{}): ({x},{y}) drifts towards the enemy ({} away)",
            crate::bh_smart::NAMES[u.t as usize % 28],
            u.x,
            u.y,
            gap(pick)
        ),
    ))
}
