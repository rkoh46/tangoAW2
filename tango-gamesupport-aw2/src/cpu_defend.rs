//! The computer defends its HQ in the custom campaigns (BH, BH2, Silver Nova, the gauntlet): docs/AW2.md, "The CPU defends its HQ".
//!
//! A mission gives the enemy's units orders (docs/AW2.md "AI roles": hold, stand, freeze, go for the properties...). AW2's
//! unit queue plays a unit by its order, and a soldier that holds (role 0) or is frozen is skipped altogether unless an
//! enemy stands next to it ([`crate::custom_campaign::ai_unit`]); the attack check that follows is AW2's, which weighs a
//! target by what the trade is worth and knows nothing of an HQ under capture. So a player could walk a foot soldier onto
//! the enemy HQ with the enemy's units standing round it, and take the mission.
//!
//! The rule, for a unit of a CPU army whose team owns an HQ that a foot soldier (Infantry, Mech) of another team stands on:
//!
//! 1. **Attack.** A unit that can hurt the soldier (its chart damage is above 0: a weapon with ammunition, or the machine
//!    gun) and can reach a free cell next to it (a direct unit; within its movement points and fuel, other teams' units
//!    in the way) or has it in its range from where it stands (an indirect unit, which cannot move and fire) attacks it,
//!    whatever its order. The cell is the nearest one (the lowest move cost; a hold order is kept as far as it goes: the
//!    unit that is already next to the soldier fires from where it stands). The attack is AW2's own: the planner
//!    `sub_0805D648` is called with the attack kind and the target, so the executor, the battle scene and the counter-attack
//!    are the game's.
//! 2. **Close in.** A direct unit that can hurt the soldier but has no cell to attack from this turn (they are taken, or
//!    out of reach) moves up to the nearest free cell within 2 of the HQ, if that is nearer than it stands (a Wait, the
//!    game's own move planner). Soldiers that are taking a property of their own do not leave it for this.
//!
//! Fair: the CPU sees what the owner of a property sees (the soldier stands on its HQ), reads the same RAM as a person
//! looking at the screen, and moves by the same movement costs; it is a response, not a bonus. Deterministic: only
//! emulated memory is read, and the call in flight is a flag in the CPU's RAM ([`CALLED`]), so peers, replays and
//! rollback agree. `inspect::SIM_VERSION` 38.

use mgba::core::Core;

use crate::ds_ai::{attack, Attack, Board, C_HQ};

const CURRENT_ARMY: u32 = 0x0300_33EC;
const CURRENT_UNIT: u32 = 0x0300_40D8;
/// The unit queue's call of the attack check (`bl sub_0805E9DC` in `sub_0805D438`): the trap stands before it.
pub const CHECK: u32 = 0x0805_D54C;
/// What follows the call: the check's work is done (flags cleared, the action ready when `+0x13` of the action struct is set).
const AFTER: u32 = 0x0805_D550;
/// `sub_0805D648(x, y, kind, target, extra)`: fills the action struct (`0x030046C0`) for the unit queue's current unit and
/// works out the path.
const PLAN_ACTION: u32 = 0x0805_D648;
const KIND_ATTACK: u32 = 4;
const KIND_WAIT: u32 = 2;
/// A call of the planner is in flight (the trap stands at the return address): a byte of the Dual Strike CPU's RAM.
const CALLED: u32 = crate::ds_ai::STATE + 0xF8;

/// A development switch for A/B runs (`tools/aw2test`, [`crate::ds_ai::SWITCHES`] bit 4): the rule is off.
pub const OFF_DEFEND: u8 = 16;

const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const TERRAIN: u32 = MAP + 0x1432;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const CARRIED: u8 = 0x08;
const INFANTRY: u8 = 1;
const MECH: u8 = 2;

/// A foot soldier of another team standing on an HQ of the army's team.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Threat {
    pub rec: u32,
    pub index: u32,
    pub t: u8,
    pub x: i32,
    pub y: i32,
}

/// What a unit does.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Plan {
    /// Moves to (x, y) and attacks the soldier with this unit index.
    Attack { x: i32, y: i32, target: u32 },
    /// Moves to (x, y) and waits.
    Close { x: i32, y: i32 },
}

fn players(core: &Core) -> u32 {
    crate::five::players(core)
}

fn team(core: &Core, army: u32) -> u8 {
    core.raw_read_8(players(core) + 0x3C * army + 0x2A, -1)
}

/// The custom campaigns' computer armies play (not the Dual Strike Campaign's own, not Versus).
fn in_scope(core: &Core, army: u32) -> bool {
    crate::ds_weather::is_on(core)
        && crate::ds_campaign::active(core)
        && !crate::ds_campaign::is_ds(core)
        && !crate::survival::on(core)
        && crate::ds_ai::is_cpu(core, army)
        && core.raw_read_8(crate::ds_ai::SWITCHES, -1) & OFF_DEFEND == 0
}

/// The soldiers of other teams on the HQs of `army`'s team, by cell. Reads the unit records and the cell under each foot
/// soldier only (no board).
pub fn threats(core: &Core, army: u32) -> Vec<Threat> {
    let base = core.raw_read_32(UNITS_POINTER, -1);
    let mine = team(core, army);
    let mut out = Vec::new();
    for i in 1..255u32 {
        let r = base + UNIT * i;
        let t = core.raw_read_8(r, -1);
        if t != INFANTRY && t != MECH {
            continue;
        }
        if core.raw_read_8(r + 1, -1) & CARRIED != 0 {
            continue;
        }
        let a = crate::five::army_of_index(core, i);
        if !(1..=5).contains(&a) || team(core, a) == mine {
            continue;
        }
        let (x, y) = (core.raw_read_8(r + 2, -1) as u32, core.raw_read_8(r + 3, -1) as u32);
        let row = core.raw_read_16(ROWS + 2 * y, -1) as u32;
        let cell = core.raw_read_8(TERRAIN + row + x, -1);
        if cell & 0x1F != C_HQ {
            continue;
        }
        let owner = ((cell >> 5) % 6) as u32;
        if owner == 0 || team(core, owner) != mine {
            continue;
        }
        out.push(Threat {
            rec: r,
            index: i,
            t,
            x: x as i32,
            y: y as i32,
        });
    }
    out.sort_by_key(|t| (t.y, t.x));
    out
}

/// Whether `att` (with `ammo` rounds) can hurt a `def`: the machine gun, or a cannon with ammunition.
fn hurts(att: u8, ammo: u16, def: u8) -> bool {
    crate::roster::chart(att, def, 1) > 0 || (ammo > 0 && crate::roster::chart(att, def, 0) > 0)
}

fn dist(a: (i32, i32), b: (i32, i32)) -> i32 {
    (a.0 - b.0).abs() + (a.1 - b.1).abs()
}

/// What the unit at record `u` does about the soldiers on its team's HQs, if anything.
pub fn plan(core: &Core, u: u32) -> Option<Plan> {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !in_scope(core, army) {
        return None;
    }
    let found = threats(core, army);
    if found.is_empty() {
        return None;
    }
    let b = Board::read(core);
    let me = *b.units.iter().find(|m| m.rec == u)?;
    if me.army != army || me.carried() || me.flags & 1 != 0 {
        return None;
    }
    let kind = attack(me.t);
    if kind == Attack::None {
        return None;
    }
    let ammo = (core.raw_read_16(u + 4, -1) >> 7) & 0xF;
    let fuel = (core.raw_read_8(u + 6, -1) & 0x7F) as i32;
    let foes: Vec<&Threat> = found.iter().filter(|t| hurts(me.t, ammo, t.t)).collect();
    if foes.is_empty() {
        return None;
    }
    let here = (me.x, me.y);
    let budget = b.moves(army, me.t).min(fuel);
    let reach = if kind == Attack::Direct {
        b.flood(army, me.t, me.x, me.y, budget, false)
    } else {
        Vec::new()
    };
    let free = |c: (i32, i32)| c == here || b.unit_at(c.0, c.1).is_none();
    let steps = [(0, -1), (1, 0), (0, 1), (-1, 0)];
    // 1. Attack: (cost, target cell, cell to fire from)
    let mut best: Option<((i32, i32, i32, i32, i32), Plan)> = None;
    for t in &foes {
        let tc = (t.x, t.y);
        let mut cells: Vec<((i32, i32), i32)> = Vec::new();
        if kind == Attack::Direct {
            for (dx, dy) in steps {
                let c = (t.x + dx, t.y + dy);
                if !b.inside(c.0, c.1) || !free(c) {
                    continue;
                }
                let d = reach[b.idx(c.0, c.1)];
                if d >= 0 {
                    cells.push((c, d as i32));
                }
            }
        } else {
            let s = crate::ds_ai::stats(me.t);
            let d = dist(here, tc);
            if d >= s.min_range as i32 && d <= b.max_range(army, me.t) {
                cells.push((here, 0));
            }
        }
        for (c, cost) in cells {
            let key = (cost, t.y, t.x, c.1, c.0);
            if best.map_or(true, |(k, _)| key < k) {
                best = Some((
                    key,
                    Plan::Attack {
                        x: c.0,
                        y: c.1,
                        target: t.index,
                    },
                ));
            }
        }
    }
    if let Some((_, p)) = best {
        return Some(p);
    }
    // 2. Close in: a direct unit goes to the nearest free cell within 2 of the soldier, if that is nearer than it stands.
    if kind != Attack::Direct || budget <= 0 {
        return None;
    }
    // (a soldier that is taking a property of the other side does not leave it)
    if matches!(me.t, INFANTRY | MECH) {
        let i = b.idx(me.x, me.y);
        if b.owner[i] != 0 && !b.team_owns(i, army) {
            return None;
        }
    }
    let t0 = foes.iter().min_by_key(|t| (dist(here, (t.x, t.y)), t.y, t.x))?;
    let tc = (t0.x, t0.y);
    let now = dist(here, tc);
    let mut near: Option<((i32, i32, i32, i32), (i32, i32))> = None;
    for y in (t0.y - 2)..=(t0.y + 2) {
        for x in (t0.x - 2)..=(t0.x + 2) {
            if !b.inside(x, y) || (x, y) == here || !free((x, y)) {
                continue;
            }
            let d = dist((x, y), tc);
            if d > 2 || d >= now || reach[b.idx(x, y)] < 0 {
                continue;
            }
            let key = (d, reach[b.idx(x, y)] as i32, y, x);
            if near.map_or(true, |(k, _)| key < k) {
                near = Some((key, (x, y)));
            }
        }
    }
    near.map(|(_, (x, y))| Plan::Close { x, y })
}

/// The unit at record `u` has something to do about an HQ under capture: [`crate::custom_campaign::ai_unit`] does not skip it.
pub fn engaged(core: &Core, u: u32) -> bool {
    plan(core, u).is_some()
}

/// The unit queue is about to run the attack check for the current unit. With a plan, the planner `sub_0805D648` is called
/// instead (its return comes back to this address with [`CALLED`] set, and goes on past the check).
pub fn check(core: &mut Core) {
    if core.raw_read_8(CALLED, -1) != 0 {
        core.raw_write_8(CALLED, -1, 0);
        let cpu = core.gba_mut().cpu_mut();
        let sp = cpu.gpr(13);
        cpu.set_gpr(13, sp + 4);
        cpu.set_thumb_pc(AFTER);
        return;
    }
    let u = core.raw_read_32(CURRENT_UNIT, -1);
    if u < 0x0200_0000 {
        return;
    }
    let (x, y, kind, target) = if let Some(p) = plan(core, u) {
        crate::ds_ai::log(&format!("cpu defend: unit {u:#x} {p:?}"));
        match p {
            Plan::Attack { x, y, target } => (x, y, KIND_ATTACK, target),
            Plan::Close { x, y } => (x, y, KIND_WAIT, 0),
        }
    } else if let Some((x, y)) = crate::cpu_units::plan(core, u) {
        // (a Black Boat's move, crate::cpu_units: the planner moves it and it waits)
        (x, y, KIND_WAIT, 0)
    } else {
        return;
    };
    core.raw_write_8(CALLED, -1, 1);
    let cpu = core.gba().cpu();
    let sp = cpu.gpr(13) as u32 - 4;
    core.raw_write_32(sp, -1, 0);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, x);
    cpu.set_gpr(1, y);
    cpu.set_gpr(2, kind as i32);
    cpu.set_gpr(3, target as i32);
    cpu.set_gpr(13, sp as i32);
    cpu.set_gpr(14, (CHECK | 1) as i32);
    cpu.set_thumb_pc(PLAN_ACTION);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(CHECK, Box::new(check))]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_flag_is_inside_the_cpu_ram() {
        assert!(CALLED < crate::ram_map::DS_AI.0 + crate::ram_map::DS_AI.1);
        assert!(CALLED > crate::ds_ai::SWITCHES);
    }

    #[test]
    fn distances() {
        assert_eq!(dist((1, 1), (3, 0)), 3);
    }
}
