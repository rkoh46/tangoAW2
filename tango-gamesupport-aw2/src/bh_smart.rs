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
    /// Airports owned by the enemy, and Black Hole's own HQ.
    foe_airports: Vec<(i32, i32)>,
    own_hq: Vec<(i32, i32)>,
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
        let mut f = Field { w, h, terrain: Vec::new(), foes: Vec::new(), own: Vec::new(), props: Vec::new(), targets: Vec::new(), hidden_foes: 0, fog, foe_airports: Vec::new(), own_hq: Vec::new() };
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
                        Some(tm) if owner != 0 && tm == my_team => {
                            mine.push((x, y, 1));
                            if k == 0 {
                                f.own_hq.push((x, y));
                            }
                        }
                        other => {
                            if k == 3 && owner != 0 && other.is_some() {
                                f.foe_airports.push((x, y));
                            }
                            f.props.push((x, y))
                        }
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
    /// Every candidate, best first, with its top reasons (for the audit log).
    pub all: Vec<(u8, i32, String)>,
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
pub fn choose(core: &Core, army: u32, door_x: i32, y: i32, options: &[(u8, Vec<(i32, i32)>)], heavy: &[u8], recent: &[u8], seed: u32) -> Option<Decision> {
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

    // What the enemy is made of near the doors, and what could hit a unit placed there next turn.
    let doors: Vec<(i32, i32)> = (door_x..door_x + 3).map(|x| (x, y)).collect();
    let (mut air_w, mut armour_w) = (0, 0);
    for (s, w) in &weights {
        if AIR.contains(&s.t) {
            air_w += *w;
        }
        if matches!(role(s.t), Role::Heavy) {
            armour_w += *w;
        }
    }
    let air_share = if total_w > 0 { air_w * 100 / total_w } else { 0 };
    let armour_share = if total_w > 0 { armour_w * 100 / total_w } else { 0 };
    let (mut reach_n, mut adjacent) = (0, 0);
    for s in &f.foes {
        let d = doors.iter().map(|&c| manhattan((s.x, s.y), c)).min().unwrap_or(99);
        let rmax = stat(core, s.t, 0x0F).max(1);
        let reach = if stat(core, s.t, 0x0E) > 1 { rmax } else { stat(core, s.t, 0x0A) + rmax };
        if d <= reach {
            reach_n += 1;
        }
        if d <= 2 && stat(core, s.t, 0x0E) <= 1 {
            adjacent += 1;
        }
    }
    let pressed = reach_n >= 1;
    let hot = adjacent >= 1 || reach_n >= 3;
    let airport_near = f.foe_airports.iter().any(|&a| manhattan(a, mid) <= 12);
    let hq_threat = f.own_hq.iter().any(|&h| f.foes.iter().any(|s| manhattan((s.x, s.y), h) <= 7));
    let campaign = crate::ds_campaign::active(core);

    // Air only when it fits: Fighters need enemy air on the field now; Bombers and B Copters stay away from enemy
    // Anti-Air, Missiles, Cruisers and Fighters near the doors (or two anywhere).
    let aa_all = f.foes.iter().filter(|s| matches!(s.t, 14 | 15 | 16 | 22)).count();
    let aa_near = f.foes.iter().filter(|s| matches!(s.t, 14 | 15 | 16 | 22) && manhattan((s.x, s.y), mid) <= 10).count();
    let aa_hard_near = f.foes.iter().filter(|s| matches!(s.t, 14 | 15 | 22) && manhattan((s.x, s.y), mid) <= 10).count();
    let options: Vec<&(u8, Vec<(i32, i32)>)> = options
        .into_iter()
        .filter(|o| match o.0 {
            16 => air_w > 0 && aa_hard_near < 2,
            17 | 19 => aa_near == 0 && aa_all < 2,
            _ => true,
        })
        .collect();
    if options.is_empty() {
        return None;
    }
    let mut juicy_w = 0;
    let mut soft_w = 0;
    for (s, w) in &weights {
        if matches!(role(s.t), Role::Heavy | Role::Indirect) {
            juicy_w += *w;
        }
        if matches!(s.t, 1 | 2 | 6 | 10 | 11) {
            soft_w += *w;
        }
    }
    let juicy_share = if total_w > 0 { juicy_w * 100 / total_w } else { 0 };
    let soft_share = if total_w > 0 { soft_w * 100 / total_w } else { 0 };

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
    let frontline = own_roles[Role::Foot as usize] + own_roles[Role::Light as usize] + own_roles[Role::Heavy as usize];
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

        // Door safety: what could hit a unit standing on the doors next turn.
        let indirect = matches!(role(t), Role::Indirect) || t == 15;
        if pressed {
            if indirect {
                parts.push(("fragile at a door the enemy can reach".to_string(), if hot { -70 } else { -40 }));
            }
            if hot && matches!(role(t), Role::Heavy) {
                parts.push(("enemies at the doors: the sturdiest direct unit".to_string(), (price(core, t) / 400).min(55)));
            } else if hot && matches!(role(t), Role::Light | Role::Foot) {
                parts.push(("enemies at the doors: a thin unit".to_string(), -8));
            } else if hot && t == 19 {
                parts.push(("enemies at the doors: a copter is soft".to_string(), -20));
            }
        }

        // Counters by kind of threat.
        if matches!(role(t), Role::Heavy) && t != 5 && armour_share > 0 {
            parts.push((format!("armour is {armour_share}% of the threat"), (armour_share * 2 / 5).min(40)));
        } else if t == 5 && armour_share > 0 {
            parts.push((format!("armour is {armour_share}% of the threat"), (armour_share / 4).min(25)));
        }
        if role(t) == Role::AntiAir && air_w > 0 {
            parts.push((format!("air is {air_share}% of the threat"), (air_share * 3 / 5 + 10).min(60)));
            if own_types[14] + own_types[15] == 0 {
                parts.push(("no anti-air yet".to_string(), 15));
            }
        }

        // Indirect fire needs a protected backline and targets within 2-3 turns.
        if matches!(role(t), Role::Indirect) && !pressed {
            let guards = f.own.iter().filter(|s| matches!(role(s.t), Role::Foot | Role::Light | Role::Heavy) && manhattan((s.x, s.y), mid) <= 6).count();
            let turns = f.engage(&cost, &f.targets).map(|d| d.saturating_sub(rmax - 1).div_ceil(mv));
            if guards >= 2 && turns.is_some_and(|n| n <= 3) {
                parts.push(("protected backline, targets within 3 turns".to_string(), 10));
            } else {
                parts.push(("no protected backline or targets too far".to_string(), -35));
            }
        }

        // Fill the gaps: a thin front line.
        if frontline < 3 && matches!(role(t), Role::Heavy | Role::Light | Role::Foot) {
            parts.push(("too few front-line units".to_string(), if role(t) == Role::Heavy { 10 } else { 5 }));
        }

        // Objectives: the HQ under threat wants units that get back in two turns; a few distant foes want speed.
        if hq_threat && !indirect && !f.own_hq.is_empty() {
            if let Some(d) = f.engage(&cost, &f.own_hq) {
                if d.div_ceil(mv) <= 2 {
                    parts.push(("can defend the HQ in two turns".to_string(), 12));
                }
            }
        }
        if campaign && !pressed && f.foes.len() <= 3 && !f.foes.is_empty() && !indirect && mv >= 6 {
            parts.push(("few distant foes: speed to chase".to_string(), 6));
        }

        // Black Hole's army.
        let same = own_types[t as usize].min(8);
        if same > 0 {
            parts.push((format!("already has {} {}", own_types[t as usize], NAMES[t as usize]), -10 * same));
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

        // Air: a real reason each.
        if t == 17 {
            parts.push(if juicy_share >= 25 { (format!("juicy ground targets ({juicy_share}%), AA thin"), (juicy_share * 2 / 3).min(45)) } else { ("no armour or artillery to bomb".to_string(), -40) });
        }
        if t == 19 {
            parts.push(if soft_share >= 20 { (format!("soft targets ({soft_share}%), AA light"), (soft_share * 2 / 5).min(30)) } else { ("nothing soft to harass".to_string(), -20) });
        }
        if t == 16 {
            parts.push((format!("enemy air {air_share}%"), (air_share / 3).min(30)));
        }
        if matches!(t, 21 | 22 | 24) && f.engage(&cost, &f.targets).is_none() {
            parts.push(("no naval target to reach".to_string(), -25));
        }

        // Foot soldiers only to capture something nobody is capturing.
        if matches!(t, INFANTRY | MECH) {
            let free = f.props.iter().any(|&(px, py)| {
                f.at(px, py).is_some_and(|i| cost[i] != INF && cost[i] <= 24) && !f.own.iter().any(|u| matches!(role(u.t), Role::Foot) && manhattan((u.x, u.y), (px, py)) <= 1)
            });
            if !free {
                parts.push(("nothing to capture".to_string(), -30));
            }
        }

        // Variety: the last picks count against a repeat.
        for (k, &r) in recent.iter().take(4).enumerate() {
            if r == t {
                parts.push((format!("picked {} turns of spawns ago", k + 1), if k == 0 { -20 } else { -12 }));
            }
        }

        // Specialists with nothing to shoot at.
        if role(t) == Role::AntiAir && air_w == 0 {
            // (an enemy airport near can build air: a little forethought, never a habit)
            parts.push(if airport_near { ("anti-air, no air yet but an airport near".to_string(), -22) } else { ("anti-air with no air in sight".to_string(), -50) });
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
    let all = scored
        .iter()
        .map(|(s, _)| {
            let mut p: Vec<&(String, i32)> = s.parts.iter().collect();
            p.sort_by_key(|p| Reverse(p.1.abs()));
            (s.t, s.total, p.iter().take(3).map(|p| format!("{} {:+}", p.0, p.1)).collect::<Vec<_>>().join("; "))
        })
        .collect();
    let (mut best, _) = scored.swap_remove(pick);
    best.parts.sort_by_key(|p| Reverse(p.1.abs()));
    let summary = format!(
        "foes {} (+{} unseen) near {} threat {} air {}% armour {}% reach {} adj {} | own {} | to target {:?} / foe {:?}",
        f.foes.len(),
        f.hidden_foes,
        nearest,
        threat,
        air_share,
        armour_share,
        reach_n,
        adjacent,
        own_total,
        nearest_target,
        foe_target
    );
    let _ = fog_text(&f);
    Some(Decision { best, pool, next, all, summary })
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
