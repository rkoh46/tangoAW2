//! Dual Strike's threat maps and threat-aware moves for the CPU's units (phases C and D of docs/AW2.md "Dual
//! Strike's CPU").
//!
//! **Dual Strike** rebuilds two maps for every unit it moves (`Ai_BuildThreatMaps`), rated against that unit's
//! type: per cell, `threatMax`, the most one direct enemy that can get next to it would deal (its rated base damage
//! x its hp, the enemy's move range and the ring round it), and `threatSum`, the indirect fire covering it (summed
//! over the enemies' current fire ranges). An enemy that would deal under 25, or that cannot get within the unit's
//! move plus its own move (or range) plus 1, is left out; in fog only the enemies seen count; under the Assault
//! behaviour a direct or unarmed unit ignores direct enemies. A cell is unsafe for the unit when `threatMax` reaches
//! its type's `threatMaxLimit` or `threatSum` its `threatSumLimit`: the limits come from the CO's profile
//! (base +/- half a spread) by the turn's roll (`AiProfile_Build`: Defense 0, Assault 100, General a new roll each
//! turn, [`crate::ds_ai::profile_roll`]), so the same army is bold on some days and careful on others. Under
//! Strike (and in a Tag Power's first half) there are no threat maps at all. Danger compares cells as
//! `threatMax + 2 x threatSum`.
//!
//! **Here** AW2's own attack check (`0x0805E9DC`) still decides the attacks; where it found none, AW2 moves the unit
//! by its role (`AiRunRoleMove`, `0x0805F4CC`). For a direct combat unit with an advancing role (1 the enemy HQ, 3
//! the enemy's properties, 4 the nearest enemy units; its army's behaviour's role where it has one), not a foot
//! soldier, not on a campaign march and not of a Defense army, the place it goes this turn is chosen here: its
//! target by its role (the nearest enemy unit it can hurt, the nearest enemy HQ, the nearest property not its
//! team's, by its own movement costs), then of the cells it can reach this turn the one nearest that target among
//! those that are safe, so that it gets closer without stepping into danger (ties: the lower danger, then the more
//! terrain stars); with no safe cell that gets closer it stays where it is if that is safe, or else moves to the
//! safest cell (Dual Strike's `AiUnit_MoveToSafestTile`: the lowest danger, the most stars, the shortest move).
//! Where no free cell it can reach is nearer at all, the way is blocked, not dangerous, and AW2's own move finds its
//! way round. A cell to go to is given to AW2's "move towards a place" (the role 1 code, its place replaced at
//! [`GOAL_HOOK`], the mechanism [`crate::cpu_inventions`] proved), which moves the unit there; a unit that stays
//! takes AW2's role 0 (it waits where it is). Foot soldiers (their captures), indirect units, transports, holders
//! and AW2's other roles move as AW2 moves them.
//!
//! The cost is a few floods per unit (its reach, the reverse distance to its target, each nearby enemy's reach), a
//! fraction of a millisecond, once per unit moved; the time is in the log (`dsai move` lines).

use mgba::core::Core;

use crate::ds_ai::*;

const CURRENT_UNIT: u32 = 0x0300_40D8;
const ROLE_MOVES: u32 = 0x0857_68E0;
/// Role 1's call that finds the place to go (`sub_08058F90`) has returned: the place at r4, r0 the answer.
pub const GOAL_HOOK: u32 = crate::cpu_inventions::GOAL_HOOK;
/// The goal in force: flag, x, y, then the unit (a word).
const GOAL: u32 = STATE + 0xD0;
const GOAL_UNIT: u32 = STATE + 0xD4;
const TERRAIN_INFO: u32 = 0x085D_583C;
const FAR: i32 = 999;

fn stars(core: &Core, class: u8) -> i32 {
    core.raw_read_32(TERRAIN_INFO + 0x14 * (class as u32 & 0x1F) + 0x10, -1) as i32
}

/// The cells army `army`'s units and properties see (all of them without fog).
fn seen(b: &Board, army: u32) -> Vec<bool> {
    let n = b.class.len();
    if !b.fog {
        return vec![true; n];
    }
    let mut out = vec![false; n];
    for i in 0..n {
        if b.team_owns(i, army) {
            out[i] = true;
        }
    }
    for u in b.units.iter().filter(|u| !u.carried() && b.same_team(u.army, army)) {
        let v = crate::roster::ds_record(u.t).map_or(1, |r| r[0x12] as i32).max(1);
        for y in (u.y - v).max(0)..=(u.y + v).min(b.h - 1) {
            for x in (u.x - v).max(0)..=(u.x + v).min(b.w - 1) {
                if (x - u.x).abs() + (y - u.y).abs() <= v {
                    out[b.idx(x, y)] = true;
                }
            }
        }
    }
    out
}

/// An enemy unit `army` knows of: seen (in woods and reefs, and a dived Sub or hidden Stealth, only from next to
/// it).
fn visible(b: &Board, sight: &[bool], army: u32, e: &Unit) -> bool {
    if !b.fog {
        return true;
    }
    let i = b.idx(e.x, e.y);
    let close = matches!(b.class[i], 4 | 19) || e.flags & 0x20 != 0;
    if close {
        return b
            .units
            .iter()
            .any(|u| !u.carried() && b.same_team(u.army, army) && (u.x - e.x).abs() + (u.y - e.y).abs() == 1);
    }
    sight[i]
}

/// `Ai_UnitUsesThreatMaps`'s Eagle rule: before the last power check, while his Super (both, with a partner) is
/// paid for, his units other than foot soldiers ignore the threat maps (Lightning Strike will move them again).
fn eagle_rush(core: &Core, army: u32, t: u8) -> bool {
    let (co, _) = army_co(core, army);
    if crate::tag::ds_id(co) != Some(9) || t <= MECH {
        return false;
    }
    let pass = core.raw_read_32(0x0300_4770, -1);
    let last = if core.raw_read_8(0x0300_3FCD, -1) != 0 { 22 } else { 18 };
    pass < last && crate::ds_ai_power::super_ready(core, army)
}

/// Dual Strike's threat maps against a unit of type `t` of `army` at (x, y) with `moves` move points
/// (`Ai_BuildThreatMaps` / `Ai_AddEnemyThreat`): (`threatMax`, `threatSum`).
pub(crate) fn threat_maps(core: &Core, b: &Board, army: u32, t: u8, x: i32, y: i32, moves: i32) -> (Vec<u8>, Vec<u8>) {
    let n = b.class.len();
    let (mut max, mut sum) = (vec![0u8; n], vec![0u8; n]);
    let beh = behaviour(core, army);
    if beh == STRIKE || crate::tag::phase(core, army) == 1 || eagle_rush(core, army, t) {
        return (max, sum);
    }
    let sight = seen(b, army);
    let me_direct = matches!(attack(t), Attack::Direct | Attack::None);
    for e in b
        .units
        .iter()
        .filter(|e| !e.carried() && b.playing[e.army as usize % 6] && !b.same_team(e.army, army))
    {
        if !visible(b, &sight, army, e) {
            continue;
        }
        let damage = rated_damage(e.t, t);
        if damage < 25 {
            continue;
        }
        let kind = attack(e.t);
        let em = b.moves(e.army, e.t);
        let reach = if kind == Attack::Indirect {
            b.max_range(e.army, e.t)
        } else {
            em + 1
        };
        if (e.x - x).abs() + (e.y - y).abs() > moves + reach + 1 {
            continue;
        }
        if kind == Attack::Direct && beh == ASSAULT && me_direct {
            continue;
        }
        let threat = (damage * e.hp.min(100) / 100).min(255) as u8;
        match kind {
            Attack::Direct => {
                let r = b.flood(e.army, e.t, e.x, e.y, em, true);
                for i in 0..n {
                    if r[i] >= 0 && threat > max[i] {
                        max[i] = threat;
                    }
                }
            }
            Attack::Indirect => {
                let (lo, hi) = (stats(e.t).min_range as i32, b.max_range(e.army, e.t));
                for cy in (e.y - hi).max(0)..=(e.y + hi).min(b.h - 1) {
                    for cx in (e.x - hi).max(0)..=(e.x + hi).min(b.w - 1) {
                        let d = (cx - e.x).abs() + (cy - e.y).abs();
                        if d >= lo && d <= hi {
                            let i = b.idx(cx, cy);
                            sum[i] = sum[i].saturating_add(threat);
                        }
                    }
                }
            }
            Attack::None => {}
        }
    }
    (max, sum)
}

/// The move cost from every cell to the nearest of `targets` for `army`'s `t` (a reverse flood: the cost of a
/// step is the cost of entering the cell stepped into), enemy units in the way.
fn distance_to(b: &Board, army: u32, t: u8, targets: &[usize]) -> Vec<i32> {
    use std::cmp::Reverse;
    use std::collections::BinaryHeap;
    let mut d = vec![-1i32; b.class.len()];
    let mut heap = BinaryHeap::new();
    for &i in targets {
        d[i] = 0;
        heap.push(Reverse((0i32, i)));
    }
    while let Some(Reverse((c, i))) = heap.pop() {
        if c > d[i] {
            continue;
        }
        let (x, y) = (i as i32 % b.w, i as i32 / b.w);
        let step = b.cost(army, t, x, y);
        if step == 0xFF || step == 0 {
            continue;
        }
        for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
            let (nx, ny) = (x + dx, y + dy);
            if !b.inside(nx, ny) {
                continue;
            }
            if b.unit_at(nx, ny).is_some_and(|u| !b.same_team(u.army, army)) {
                continue;
            }
            let j = b.idx(nx, ny);
            let nc = c + step as i32;
            if d[j] < 0 || nc < d[j] {
                d[j] = nc;
                heap.push(Reverse((nc, j)));
            }
        }
    }
    d
}

/// Where the unit's role sends it: the cells to stand on (next to the nearest enemy unit it can hurt, the
/// nearest enemy HQ, the nearest property not its team's), by its own move costs from where it is.
fn target_cells(b: &Board, army: u32, u: &Unit, role: u8, sight: &[bool]) -> Option<(Vec<usize>, &'static str)> {
    let reach = b.flood(army, u.t, u.x, u.y, FAR, false);
    let near = |i: usize| reach[i] as i32;
    let adjacent = |x: i32, y: i32| -> Vec<usize> {
        [(0, -1), (1, 0), (0, 1), (-1, 0)]
            .iter()
            .filter(|&&(dx, dy)| b.inside(x + dx, y + dy))
            .map(|&(dx, dy)| b.idx(x + dx, y + dy))
            .collect()
    };
    let best_of =
        |cands: Vec<(i32, Vec<usize>)>| cands.into_iter().filter(|c| c.0 >= 0).min_by_key(|c| c.0).map(|c| c.1);
    let enemy_units = || -> Option<Vec<usize>> {
        let cands = b
            .units
            .iter()
            .filter(|e| {
                !e.carried()
                    && b.playing[e.army as usize % 6]
                    && !b.same_team(e.army, army)
                    && visible(b, sight, army, e)
            })
            .filter(|e| {
                base_damage(
                    u.t,
                    if e.t == SUB && e.flags & 0x20 != 0 {
                        crate::roster::DIVED_SUB
                    } else {
                        e.t
                    },
                ) > 0
            })
            .map(|e| {
                let cells: Vec<usize> = adjacent(e.x, e.y)
                    .into_iter()
                    .filter(|&i| b.at[i] == 0 || (b.idx(u.x, u.y) == i))
                    .collect();
                let c = cells.iter().map(|&i| near(i)).filter(|&d| d >= 0).min().unwrap_or(-1);
                (c, cells)
            })
            .collect();
        best_of(cands)
    };
    let properties = |hq_only: bool| -> Option<Vec<usize>> {
        let cands = (0..b.class.len())
            .filter(|&i| {
                if hq_only {
                    b.class[i] == C_HQ && b.owner[i] != 0 && !b.team_owns(i, army)
                } else {
                    PROPERTIES.contains(&b.class[i]) && !b.team_owns(i, army)
                }
            })
            .map(|i| {
                let (x, y) = (i as i32 % b.w, i as i32 / b.w);
                let cells: Vec<usize> = if b.at[i] == 0 || b.idx(u.x, u.y) == i {
                    vec![i]
                } else {
                    adjacent(x, y)
                };
                let c = cells.iter().map(|&j| near(j)).filter(|&d| d >= 0).min().unwrap_or(-1);
                (c, cells)
            })
            .collect();
        best_of(cands)
    };
    match role {
        4 => enemy_units()
            .map(|c| (c, "enemy unit"))
            .or_else(|| properties(true).map(|c| (c, "enemy HQ"))),
        1 => properties(true)
            .map(|c| (c, "enemy HQ"))
            .or_else(|| enemy_units().map(|c| (c, "enemy unit"))),
        _ => properties(false)
            .map(|c| (c, "property"))
            .or_else(|| enemy_units().map(|c| (c, "enemy unit"))),
    }
}

/// The cell unit `u` of `army` goes to this turn, and why.
pub(crate) fn choose(core: &Core, b: &Board, army: u32, u: &Unit, role: u8, roll: u32) -> Option<((i32, i32), String)> {
    let sight = seen(b, army);
    let (targets, what) = target_cells(b, army, u, role, &sight)?;
    let to = distance_to(b, army, u.t, &targets);
    let fuel = (core.raw_read_8(u.rec + 6, -1) & 0x7F) as i32;
    let moves = b.moves(army, u.t).min(fuel);
    let reach = b.flood(army, u.t, u.x, u.y, moves, false);
    let prof = profile(army_co(core, army).0)?;
    let up = prof.unit(u.t);
    let (max_limit, sum_limit) = (
        randomise(up.threat_max.0, up.threat_max.1, roll),
        randomise(up.threat_sum.0, up.threat_sum.1, roll),
    );
    let (tmax, tsum) = threat_maps(core, b, army, u.t, u.x, u.y, moves);
    let here = b.idx(u.x, u.y);
    let danger = |i: usize| tmax[i] as i32 + 2 * tsum[i] as i32;
    let safe = |i: usize| tmax[i] < max_limit && tsum[i] < sum_limit;
    let cells: Vec<usize> = (0..reach.len())
        .filter(|&i| reach[i] >= 0 && (b.at[i] == 0 || i == here))
        .collect();
    let progress = |i: usize| to[i] >= 0 && (to[here] < 0 || to[i] < to[here]);
    let star = |i: usize| stars(core, b.class[i]);
    let pick = cells
        .iter()
        .copied()
        .filter(|&i| safe(i) && progress(i))
        .min_by_key(|&i| (to[i], danger(i), -star(i), i));
    // (no reachable free cell nearer at all: the way is blocked, not dangerous; AW2's own move finds its way round)
    if pick.is_none() && !cells.iter().any(|&i| progress(i)) {
        if logging() {
            log(&format!(
                "dsai move day {} army {army} {} at ({},{}) role {role} to {what} {} away: blocked, AW2's move ({} cells in reach)",
                b.day,
                crate::bh_smart::NAMES[u.t as usize % 28],
                u.x,
                u.y,
                to[here],
                cells.len()
            ));
        }
        return None;
    }
    let (cell, why) = if let Some(i) = pick {
        (i, "safe, nearer")
    } else if safe(here) {
        (here, "holds: nothing nearer is safe")
    } else {
        let i = cells
            .iter()
            .copied()
            .min_by_key(|&i| (danger(i), -star(i), reach[i], i))
            .unwrap_or(here);
        (i, "safest cell")
    };
    let note = format!(
        "{} at ({},{}) role {role} to {what} {} away: ({},{}) {why} (danger {} limits {}/{} roll {roll})",
        crate::bh_smart::NAMES[u.t as usize % 28],
        u.x,
        u.y,
        to[here],
        cell as i32 % b.w,
        cell as i32 / b.w,
        danger(cell),
        max_limit,
        sum_limit
    );
    Some(((cell as i32 % b.w, cell as i32 / b.w), note))
}

/// `AiRunRoleMove` for the unit in hand (from [`crate::ally_posture`]'s trap): `true` when Dual Strike's move
/// takes it (the caller returns).
pub fn role_move(core: &mut Core) -> bool {
    core.raw_write_8(GOAL, -1, 0);
    let army = current_army(core);
    if !in_scope(core, army, OFF_MOVE) || behaviour(core, army) == DEFENSE {
        return false;
    }
    let rec = core.raw_read_32(CURRENT_UNIT, -1);
    if rec == 0 {
        return false;
    }
    let t = core.raw_read_8(rec, -1);
    // (the army's behaviour's role where it has one: Strike the nearest enemy units, Assault the properties)
    let own = core.raw_read_8(rec + 0x0B, -1);
    let role = crate::ally_posture::role(behaviour(core, army)).map_or(own, |r| r as u8);
    if !matches!(role, 1 | 3 | 4)
        || t <= MECH
        || attack(t) != Attack::Direct
        || crate::custom_campaign::driven_goal(core, rec).is_some()
    {
        return false;
    }
    let started = std::time::Instant::now();
    let roll = profile_roll(core, army);
    let b = Board::read(core);
    let Some(u) = b.units.iter().find(|u| u.rec == rec).copied() else {
        return false;
    };
    let Some((cell, note)) = choose(core, &b, army, &u, role, roll) else {
        return false;
    };
    if logging() {
        log(&format!(
            "dsai move day {} army {army} {note}, {} us",
            b.day,
            started.elapsed().as_micros()
        ));
    }
    // Staying where it is is AW2's role 0 (hold: the unit waits there, an action like any other, so the turn's
    // checks after actions run and the unit is done); going somewhere is role 1 with the place replaced.
    let role = if (cell.0, cell.1) == (u.x, u.y) {
        0
    } else {
        core.raw_write_range(GOAL, -1, &[1, cell.0 as u8, cell.1 as u8]);
        core.raw_write_32(GOAL_UNIT, -1, rec);
        1
    };
    let f = core.raw_read_32(ROLE_MOVES + 4 * role, -1);
    core.gba_mut().cpu_mut().set_thumb_pc(f & !1);
    true
}

/// Role 1's place (from [`crate::cpu_inventions::goal_hook`]): ours, for the unit it was chosen for.
pub fn goal_hook(core: &mut Core) {
    if core.raw_read_8(GOAL, -1) == 0 || core.raw_read_32(CURRENT_UNIT, -1) != core.raw_read_32(GOAL_UNIT, -1) {
        return;
    }
    core.raw_write_8(GOAL, -1, 0);
    let (x, y) = (
        core.raw_read_8(GOAL + 1, -1) as u16,
        core.raw_read_8(GOAL + 2, -1) as u16,
    );
    let out = core.gba().cpu().gpr(4) as u32;
    core.raw_write_16(out, -1, x);
    core.raw_write_16(out + 2, -1, y);
    core.gba_mut().cpu_mut().set_gpr(0, 0);
}
