//! The Black Factory's choice in Versus with the pack: which unit helps
//! Black Hole most at this moment ([`crate::bh_factory`] has the trap and the
//! rules of where a unit may stand; this module only ranks the legal ones).
//!
//! Every spawn is decided again from the battle as it is now, a pure
//! function of emulated RAM and ROM (no randomness, no host state, so both
//! netplay peers and a replay agree). Each candidate scores:
//! - *counter*: what it does to the enemy units Black Hole can see, minus
//!   what they do to it, from Dual Strike's own damage chart
//!   ([`crate::roster::chart`]), each enemy weighted by price x HP bars x
//!   how near it is to the factory;
//! - *travel*: turns to get within reach of the nearest enemy unit or
//!   enemy/neutral property, by the unit's own movement chart over the real
//!   map (rivers, mountains, woods, sea, pipes), 5 points a turn; a unit that
//!   cannot get there at all loses 45;
//! - *threat*: enemies near the factory make the counter count half again
//!   and travel stop mattering, and favour sturdy units, an Oozium among
//!   them; an indirect unit has no use for an enemy at its feet;
//! - *army*: -7 for each unit of the same type Black Hole already has, -3 for
//!   each of the same role, and a bonus for the roles it lacks (indirect fire,
//!   infantry to capture the properties on the map);
//! - *size*: a little for price, so the stronger of two equal answers wins.
//!
//! Fog of war is followed: an enemy counts only when a Black Hole unit or
//! property sees it (vision from the unit table, adjacent only for units in
//! woods, on reefs, dived or hidden); the terrain and the properties on the
//! map are always known.

use mgba::core::Core;
use std::cmp::Reverse;
use std::collections::BinaryHeap;

use crate::roster::{chart, BLACK_BOAT, CARRIER, OOZIUM, STEALTH};

pub const NAMES: [&str; 28] = [
    "-", "Infantry", "Mech", "Md Tank", "Megatank", "Tank", "Recon", "APC", "Neotank", "Piperunner", "Artillery",
    "Rockets", "Stealth", "Black Bomb", "Anti-Air", "Missiles", "Fighter", "Bomber", "Black Boat", "B Copter",
    "T Copter", "Battleship", "Cruiser", "Lander", "Sub", "-", "Carrier", "Oozium",
];

const MAP: u32 = 0x0201_E450;
const UNIT_PLANE: u32 = MAP + 0x51A;
const TILES: u32 = MAP + 0xA22;
const TERRAIN_PLANE: u32 = MAP + 0x1432;
const ROWS: u32 = MAP + 0x417A;
const UNITS_POINTER: u32 = 0x0849_9594;
const FOG: u32 = 0x0300_3FCD;
const UNIT: u32 = 12;
const CARRIED: u8 = 0x08;
const HIDDEN: u8 = 0x20;

const INF: u32 = u32::MAX;
const SEA: u8 = 7;
const SHOAL: u8 = 13;
const REEF: u8 = 19;
const WOOD: u8 = 4;

pub const INFANTRY: u8 = 1;
pub const MECH: u8 = 2;
const SUB: u8 = 24;
const LANDER: u8 = 23;
const AIR: [u8; 6] = [STEALTH, 13, 16, 17, 19, 20];
const SEA_UNITS: [u8; 6] = [BLACK_BOAT, 21, 22, 23, 24, CARRIER];

/// A property tile per kind (HQ, base, city, airport, port, lab) and owner
/// colour (0 neutral, 1..4, 5 Black Hole), as in [`crate::five`].
const PROPERTY_TILES: [[u16; 6]; 6] = [
    [0x1C0, 0x1C5, 0x1CA, 0x1CF, 0x1D4, 0x1B4],
    [0x1C1, 0x1C6, 0x1CB, 0x1D0, 0x1D5, 0x1B5],
    [0x1C2, 0x1C7, 0x1CC, 0x1D1, 0x1D6, 0x1B6],
    [0x1C3, 0x1C8, 0x1CD, 0x1D2, 0x1D7, 0x1B7],
    [0x1C4, 0x1C9, 0x1CE, 0x1D3, 0x1D8, 0x1B8],
    [0x1D9, 0x1DA, 0x1DB, 0x1DC, 0x1DD, 0x1B9],
];

#[derive(Clone, Copy, PartialEq)]
enum Role {
    Foot,
    Light,
    Heavy,
    Indirect,
    AntiAir,
    Air,
    Naval,
    Special,
}

fn role(t: u8) -> Role {
    match t {
        1 | 2 => Role::Foot,
        6 => Role::Light,
        3 | 4 | 5 | 8 => Role::Heavy,
        10 | 11 | 21 => Role::Indirect,
        14 | 15 => Role::AntiAir,
        16 | 17 | 19 | 20 | 12 => Role::Air,
        18 | 22 | 23 | 24 | CARRIER => Role::Naval,
        _ => Role::Special,
    }
}

#[derive(Clone, Copy)]
struct Seen {
    t: u8,
    x: i32,
    y: i32,
    bars: i32,
    hidden: bool,
}

struct Field {
    w: i32,
    h: i32,
    terrain: Vec<u8>,
    foes: Vec<Seen>,
    own: Vec<Seen>,
    /// Enemy and neutral properties, and the visible enemy units.
    props: Vec<(i32, i32)>,
    targets: Vec<(i32, i32)>,
    hidden_foes: usize,
    fog: bool,
}

fn players(core: &Core) -> u32 {
    crate::five::players(core)
}

fn team(core: &Core, army: u32) -> u8 {
    core.raw_read_8(players(core) + 0x3C * army + 0x2A, -1)
}

fn bars(hp: u16) -> i32 {
    if hp == 0 { 0 } else { (hp as i32 - 1) / 10 + 1 }
}

fn manhattan(a: (i32, i32), b: (i32, i32)) -> i32 {
    (a.0 - b.0).abs() + (a.1 - b.1).abs()
}

fn stat(core: &Core, t: u8, off: u32) -> i32 {
    core.raw_read_8(crate::roster::table(core) + 0x5C * t as u32 + off, -1) as i32
}

fn price(core: &Core, t: u8) -> i32 {
    core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as i32 * 10
}

impl Field {
    fn read(core: &Core, army: u32) -> Field {
        let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
        let fog = core.raw_read_8(FOG, -1) != 0;
        let base = core.raw_read_32(UNITS_POINTER, -1);
        let p = players(core);
        let my_team = team(core, army);
        // Owner colour -> army, for the properties.
        let mut colour_team = [None::<u8>; 8];
        for a in 1..=5u32 {
            let c = core.raw_read_8(p + 0x3C * a + 0x1A, -1) as usize;
            if c < 8 {
                colour_team[c] = Some(team(core, a));
            }
        }
        let mut f = Field { w, h, terrain: Vec::new(), foes: Vec::new(), own: Vec::new(), props: Vec::new(), targets: Vec::new(), hidden_foes: 0, fog };
        let mut mine: Vec<(i32, i32, i32)> = Vec::new(); // vision sources
        let mut every: Vec<(Seen, bool, i32)> = Vec::new(); // (unit, enemy, wood-or-reef)
        for y in 0..h {
            let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
            for x in 0..w {
                let c = row + x as u32;
                let class = core.raw_read_8(TERRAIN_PLANE + c, -1) & 0x1F;
                f.terrain.push(class);
                let kind = match class {
                    8 => Some(0),
                    14 => Some(1),
                    6 => Some(2),
                    10 => Some(3),
                    11 => Some(4),
                    20 => Some(5),
                    _ => None,
                };
                if let Some(k) = kind {
                    let tile = core.raw_read_16(TILES + 2 * c, -1) & 0x1FF;
                    let owner = PROPERTY_TILES[k].iter().position(|&t| t == tile).unwrap_or(0);
                    match colour_team[owner] {
                        Some(tm) if owner != 0 && tm == my_team => mine.push((x, y, 1)),
                        _ => f.props.push((x, y)),
                    }
                }
                let id = core.raw_read_8(UNIT_PLANE + c, -1) as u32;
                if id == 0 {
                    continue;
                }
                let u = base + UNIT * id;
                let t = core.raw_read_8(u, -1);
                if t == 0 || core.raw_read_8(u + 1, -1) & CARRIED != 0 {
                    continue;
                }
                let flags = core.raw_read_8(u + 1, -1);
                let a = crate::five::army_of_index(core, id);
                let hp = core.raw_read_16(u + 4, -1) & 0x7F;
                let s = Seen { t, x, y, bars: bars(hp), hidden: flags & HIDDEN != 0 };
                if team(core, a) == my_team {
                    mine.push((x, y, stat(core, t, 0x0C)));
                    f.own.push(s);
                } else {
                    every.push((s, true, (class == WOOD || class == REEF) as i32));
                }
            }
        }
        for (s, _, cover) in every {
            let near = mine
                .iter()
                .filter(|m| {
                    let d = manhattan((m.0, m.1), (s.x, s.y));
                    d <= 1 || (d <= m.2 && !s.hidden && cover == 0)
                })
                .count();
            if !fog || near > 0 {
                f.foes.push(s);
                f.targets.push((s.x, s.y));
            } else {
                f.hidden_foes += 1;
            }
        }
        f.targets.extend(f.props.iter().copied());
        f
    }

    fn at(&self, x: i32, y: i32) -> Option<usize> {
        (x >= 0 && y >= 0 && x < self.w && y < self.h).then(|| (y * self.w + x) as usize)
    }

    /// Cheapest cost to reach every square from `starts` with a terrain
    /// cost row.
    fn reach(&self, row: &[u8; 32], starts: &[(i32, i32)]) -> Vec<u32> {
        let mut cost = vec![INF; self.terrain.len()];
        let mut heap = BinaryHeap::new();
        for &(x, y) in starts {
            if let Some(i) = self.at(x, y) {
                cost[i] = 0;
                heap.push(Reverse((0u32, x, y)));
            }
        }
        while let Some(Reverse((c, x, y))) = heap.pop() {
            if cost[self.at(x, y).unwrap()] < c {
                continue;
            }
            for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
                let (nx, ny) = (x + dx, y + dy);
                let Some(i) = self.at(nx, ny) else { continue };
                let step = row[(self.terrain[i] & 0x1F) as usize];
                if step == 0xFF {
                    continue;
                }
                let n = c + step.max(1) as u32;
                if n < cost[i] {
                    cost[i] = n;
                    heap.push(Reverse((n, nx, ny)));
                }
            }
        }
        cost
    }

    /// The cost to be next to (or on) the nearest of `targets`.
    fn engage(&self, cost: &[u32], targets: &[(i32, i32)]) -> Option<u32> {
        let mut best = INF;
        for &(x, y) in targets {
            for (dx, dy) in [(0, 0), (0, -1), (1, 0), (0, 1), (-1, 0)] {
                if let Some(i) = self.at(x + dx, y + dy) {
                    best = best.min(cost[i]);
                }
            }
        }
        (best != INF).then_some(best)
    }
}

fn soft(d: i32) -> i32 {
    if d <= 100 { d } else { 100 + (d - 100) / 4 }
}

fn column(f: &Seen) -> u8 {
    match (f.t, f.hidden) {
        (SUB, true) => crate::roster::DIVED_SUB,
        (STEALTH, true) => crate::roster::HIDDEN_STEALTH,
        (t, _) => t,
    }
}

/// The best damage `att` does to a unit in defender column `def` (an
/// Oozium eats any unit on ground).
fn blow(att: u8, def: u8) -> i32 {
    if att == OOZIUM {
        return if AIR.contains(&def) || SEA_UNITS.contains(&def) { 0 } else { 100 };
    }
    chart(att, def, 0).max(chart(att, def, 1)) as i32
}

fn cost_of(t: u8) -> i32 {
    match t {
        16 | 17 => -25,
        19 => -10,
        _ => 0,
    }
}

pub struct Scored {
    pub t: u8,
    pub total: i32,
    pub parts: Vec<(String, i32)>,
}

pub struct Decision {
    /// The pick: one of [`Decision::pool`], not always the top score.
    pub best: Scored,
    /// The candidates the pick was drawn from (the best and the up to two
    /// next whose scores are within [`margin`] of it): `(type, score, weight)`.
    pub pool: Vec<(u8, i32, i32)>,
    pub next: Vec<(u8, i32)>,
    pub summary: String,
}

/// How far below the best score a candidate may be and still be drawn: 15%
/// of the best score, at least 6 points.
pub fn margin(best: i32) -> i32 {
    (best.abs() * 15 / 100).max(6)
}

/// The candidates a pick is drawn from, in score order, with their weights:
/// the top three whose score is within [`margin`] of the best; a weight is
/// the score above the pool's floor, plus one, so the best weighs most.
pub fn pool_of(scores: &[(u8, i32)]) -> Vec<(u8, i32, i32)> {
    let Some(&(_, best)) = scores.first() else { return Vec::new() };
    let floor = best - margin(best);
    scores.iter().take(3).take_while(|s| s.1 >= floor).map(|&(t, v)| (t, v, v - floor + 1)).collect()
}

/// Picks one of `pool` by `seed` (weighted by score).
pub fn draw(pool: &[(u8, i32, i32)], seed: u32) -> usize {
    let total: u32 = pool.iter().map(|p| p.2 as u32).sum();
    let mut r = seed % total.max(1);
    for (i, p) in pool.iter().enumerate() {
        if r < p.2 as u32 {
            return i;
        }
        r -= p.2 as u32;
    }
    0
}

/// Ranks `options` (unit types with the squares each may take) for the
/// factory whose door row starts at `door_x`, row `y`, for `army`.
///
/// The pick is drawn, weighted by score, from the best few (see
/// [`pool_of`]) by `seed`, which the caller derives from emulated memory
/// only (AW2's RNG state read, never advanced; day, door, army, square).
pub fn choose(core: &Core, army: u32, door_x: i32, y: i32, options: &[(u8, Vec<(i32, i32)>)], heavy: &[u8], seed: u32) -> Option<Decision> {
    let f = Field::read(core, army);
    let alive = |t: u8| f.own.iter().any(|s| s.t == t);
    let options: Vec<&(u8, Vec<(i32, i32)>)> = options.iter().filter(|o| !(heavy.contains(&o.0) && alive(o.0))).collect();
    if options.is_empty() {
        return None;
    }
    let mid = (door_x + 1, y);

    // Enemy composition, weighted.
    let mut weights: Vec<(Seen, i32)> = Vec::new();
    let mut total_w = 0;
    for s in &f.foes {
        let d = manhattan((s.x, s.y), mid).min(12);
        let w = (price(core, s.t) / 1000).max(1) * s.bars.max(1) * (16 - d);
        total_w += w;
        weights.push((*s, w));
    }
    let mut kinds = [0i32; 28];
    for (s, w) in &weights {
        kinds[s.t as usize] += *w;
    }
    let mut ranked: Vec<(u8, i32)> = (1..28u8).filter(|&t| kinds[t as usize] > 0).map(|t| (t, kinds[t as usize])).collect();
    ranked.sort_by_key(|&(t, w)| (Reverse(w), t));
    let main_foes: Vec<String> = ranked.iter().take(2).map(|&(t, _)| NAMES[t as usize].to_string()).collect();
    let foes_text = if main_foes.is_empty() { "no enemy in sight".to_string() } else { main_foes.join("+") };

    // Threat to the factory.
    let mut threat = 0;
    let mut nearest = 99;
    for s in &f.foes {
        let d = manhattan((s.x, s.y), mid);
        nearest = nearest.min(d);
        if d <= 6 {
            threat += (7 - d) * s.bars.max(1) / 4 + 1;
        }
    }
    let threatened = threat >= 6;

    // Black Hole's own army.
    let mut own_types = [0i32; 28];
    let mut own_roles = [0i32; 8];
    let mut hurt = 0;
    for s in &f.own {
        own_types[s.t as usize] += 1;
        own_roles[role(s.t) as usize] += 1;
        if s.bars <= 5 {
            hurt += 1;
        }
    }
    let own_total = f.own.len() as i32;
    let foot_count = own_roles[Role::Foot as usize];
    let indirect_count = own_roles[Role::Indirect as usize] + own_roles[Role::AntiAir as usize].min(own_types[15]);

    let nearest_target = f.targets.iter().map(|&t| manhattan(t, mid)).min();
    let foe_target = f.foes.iter().map(|s| manhattan((s.x, s.y), mid)).min();

    let mut scored: Vec<(Scored, Vec<(i32, i32)>)> = Vec::new();
    for (t, spots) in options {
        let t = *t;
        let mut parts: Vec<(String, i32)> = Vec::new();
        if heavy.contains(&t) {
            parts.push(("rare: one at a time".to_string(), -20));
        }

        // Counter.
        if total_w > 0 {
            let (mut off, mut def) = (0, 0);
            for (s, w) in &weights {
                off += w * soft(blow(t, column(s)));
                def += w * blow(s.t, t);
            }
            let (off, def) = (off / total_w, def / total_w);
            let mut m = off - def * 6 / 10;
            if threatened {
                m = m * 3 / 2;
            }
            parts.push((format!("counters {foes_text} (deals {off}, takes {def})"), m));
        }

        // Travel.
        let row = crate::oozium::move_row(core, army, t);
        let cost = f.reach(&row, spots);
        let mv = stat(core, t, 0x0A).max(1) as u32;
        let rmax = stat(core, t, 0x0F).max(1) as u32;
        if !f.targets.is_empty() && !threatened {
            match f.engage(&cost, &f.targets) {
                Some(d) => {
                    let turns = d.saturating_sub(rmax - 1).div_ceil(mv) as i32;
                    parts.push((format!("{turns} turns to the enemy"), -5 * turns.min(10)));
                }
                None => parts.push(("cannot get to the enemy".to_string(), -45)),
            }
        }

        // Threat to the factory.
        if threatened {
            parts.push(("enemies at the factory: sturdy".to_string(), price(core, t) / 1500));
            if t == OOZIUM && nearest <= 3 {
                parts.push(("Oozium eats what is at the door".to_string(), 25));
            }
            if matches!(role(t), Role::Indirect) && nearest <= 2 && stat(core, t, 0x0E) > 1 {
                parts.push(("indirect fire with the enemy at its feet".to_string(), -20));
            }
        }

        // Black Hole's army.
        let same = own_types[t as usize].min(8);
        if same > 0 {
            parts.push((format!("already has {} {}", own_types[t as usize], NAMES[t as usize]), -7 * same));
        }
        let kin = own_roles[role(t) as usize].min(8);
        if kin > 0 {
            parts.push(("more of the same role".to_string(), -3 * kin));
        }
        if own_total >= 3 && indirect_count == 0 && matches!(role(t), Role::Indirect) && cost.iter().any(|&c| c != INF) {
            parts.push(("no indirect fire yet".to_string(), 10));
        }
        if matches!(t, INFANTRY | MECH) {
            let reachable = f.props.iter().any(|&(px, py)| f.at(px, py).is_some_and(|i| cost[i] != INF && cost[i] <= 24));
            if reachable {
                let lack = if foot_count == 0 { 8 } else if foot_count < 3 { 4 } else { 0 };
                parts.push(("properties to capture within reach".to_string(), 8 + lack));
            }
        }

        // Specialists with nothing to shoot at.
        if role(t) == Role::AntiAir && !f.foes.iter().any(|s| AIR.contains(&s.t)) {
            parts.push(("anti-air with no air in sight".to_string(), -30));
        }
        if t == SUB && !f.foes.iter().any(|s| SEA_UNITS.contains(&s.t)) {
            parts.push(("no ships in sight".to_string(), -15));
        }

        // Special units.
        if t == LANDER {
            let beach = f
                .terrain
                .iter()
                .enumerate()
                .filter(|&(i, &c)| !matches!(c, SEA | SHOAL | REEF) && cost[i] == INF)
                .filter(|&(i, _)| {
                    let (x, y) = ((i as i32) % f.w, (i as i32) / f.w);
                    [(0, -1), (1, 0), (0, 1), (-1, 0)].iter().any(|&(dx, dy)| f.at(x + dx, y + dy).is_some_and(|j| cost[j] != INF))
                })
                .map(|(i, _)| ((i as i32) % f.w, (i as i32) / f.w))
                .filter_map(|c| nearest_target.map(|_| f.targets.iter().map(|&t| manhattan(c, t)).min().unwrap_or(99)))
                .min();
            match (beach, nearest_target) {
                (Some(b), Some(n)) if b + 5 <= n && foot_count >= 2 => parts.push(("land to ferry troops to".to_string(), 30)),
                _ => parts.push(("no land to ferry to".to_string(), -40)),
            }
        }
        if t == BLACK_BOAT {
            parts.push(if hurt >= 2 { ("hurt units to repair".to_string(), 25) } else { ("nothing to repair".to_string(), -30) });
        }
        if cost_of(t) != 0 {
            parts.push(("air units burn fuel".to_string(), cost_of(t)));
        }
        parts.push(("size".to_string(), price(core, t) / 2500));
        let total = parts.iter().map(|p| p.1).sum();
        scored.push((Scored { t, total, parts }, spots.clone()));
    }
    scored.sort_by_key(|(s, _)| (Reverse(s.total), s.t));
    let ranked_scores: Vec<(u8, i32)> = scored.iter().map(|(s, _)| (s.t, s.total)).collect();
    let pool = pool_of(&ranked_scores);
    let pick = draw(&pool, seed);
    let next = scored.iter().filter(|(s, _)| s.t != pool[pick].0).take(2).map(|(s, _)| (s.t, s.total)).collect();
    let (mut best, _) = scored.swap_remove(pick);
    best.parts.sort_by_key(|p| Reverse(p.1.abs()));
    let summary = format!(
        "foes {} (+{} unseen) near {} threat {} | own {} | to target {:?} / foe {:?}",
        f.foes.len(),
        f.hidden_foes,
        nearest,
        threat,
        own_total,
        nearest_target,
        foe_target
    );
    let _ = fog_text(&f);
    Some(Decision { best, pool, next, summary })
}

fn fog_text(f: &Field) -> &'static str {
    if f.fog { "fog" } else { "clear" }
}

/// The squares of the chosen type, the one nearest an enemy first.
pub fn nearest_spot(core: &Core, army: u32, door_x: i32, y: i32, spots: &[(i32, i32)], tie: u32) -> (i32, i32) {
    let f = Field::read(core, army);
    let mut best: Vec<(i32, i32)> = Vec::new();
    let mut best_d = i32::MAX;
    for &s in spots {
        let d = f.targets.iter().map(|&t| manhattan(s, t)).min().unwrap_or_else(|| manhattan(s, (door_x + 1, y)));
        if d < best_d {
            best_d = d;
            best.clear();
        }
        if d == best_d {
            best.push(s);
        }
    }
    best[tie as usize % best.len()]
}

#[cfg(test)]
mod pick_tests {
    use super::*;

    #[test]
    fn pool_is_the_top_three_within_the_margin() {
        // 15% of 100 is 15: 85 and above.
        let scores = [(5, 100), (3, 90), (8, 85), (10, 84), (1, 10)];
        let pool = pool_of(&scores);
        assert_eq!(pool.iter().map(|p| p.0).collect::<Vec<_>>(), [5, 3, 8]);
        // A clear winner stands alone; the margin is at least 6 points.
        assert_eq!(pool_of(&[(5, 100), (3, 80)]).len(), 1);
        assert_eq!(pool_of(&[(5, 10), (3, 4), (8, 3)]).len(), 2);
        assert_eq!(pool_of(&[(5, -50), (3, -56), (8, -58)]).len(), 2);
        assert!(pool_of(&[]).is_empty());
    }

    #[test]
    fn the_draw_follows_the_weights_and_stays_in_the_pool() {
        let pool = pool_of(&[(5, 100), (3, 90), (8, 86)]);
        let mut hits = [0usize; 3];
        for seed in 0..30_000u32 {
            hits[draw(&pool, seed.wrapping_mul(0x9E37_79B1) ^ (seed >> 3))] += 1;
        }
        assert!(hits.iter().all(|&h| h > 0), "{hits:?}");
        assert!(hits[0] > hits[1] && hits[1] > hits[2], "{hits:?}");
        // The weights are the score above the floor (85) plus one: 16, 6, 2.
        assert_eq!(pool.iter().map(|p| p.2).collect::<Vec<_>>(), [16, 6, 2]);
        assert_eq!(draw(&pool, 0), 0);
        assert_eq!(draw(&pool, 16), 1);
        assert_eq!(draw(&pool, 22), 2);
        assert_eq!(draw(&pool, 24), 0);
    }
}
