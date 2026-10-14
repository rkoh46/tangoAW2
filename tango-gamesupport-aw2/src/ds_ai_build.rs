//! Dual Strike's production for the CPU (phase A of docs/AW2.md "Dual Strike's CPU").
//!
//! **AW2's production** is its driver's state 5 (`0x080606D0`): `n = sub_08060DAC()` builds are tried, each by
//! `sub_08060718`, which counts the army's units, runs AW2's type pickers (they store the type at the action
//! struct `0x030046C0` +6) and then buys through `sub_080610D0`: the price check (funds, at most 0x3F units),
//! the new unit's role (`sub_08061178`, a roll against the CPU record's row bytes 4..10), the factory
//! (`sub_080611D8`) and `BuyUnit(x, y, type)`, the role going to the unit's +0x0B.
//!
//! **Dual Strike's** (`AiTurn_RunEndActions` `0x02093824`) runs after the units have moved, as AW2's does, in
//! ten steps; each step queues one build and runs again until it has nothing left (a factory builds once a turn,
//! and it stops at 50 units):
//! 0. the sites (every free base, airport and port the army owns), grouped by where an Infantry can walk from
//!    them, each rated by the units around it (enemies within the profile's radius that a Tank could reach
//!    count +2, foot units and units near a port +1, the army's own -1); the repair reserve (1.5 x what the
//!    units standing on a repairing property would cost to repair, at least 1000); the threat maps against an
//!    Anti-Air;
//! 1. an Anti-Air where a group of sites has enemy aircraft about and no cover (only with a sea domain: Dual
//!    Strike's own quirk, kept);
//! 2. a unit for each site with more enemies than friends around it, chosen against the units within its
//!    radius;
//! 3. a Fighter, against enemy aircraft, when the army has no Fighter at half health;
//! 4. and 5. Cruisers against enemy Subs that can reach a port;
//! 6. Infantry and Mechs: one free in each group with properties to take, then up to the profile's quota
//!    (Mechs by a chance that grows with the day);
//! 8. transports: a T-Copter and an APC by their share of the foot units, a Black Boat for every three armed
//!    ships (Dual Strike's Landers and Black Boats for waiting units need its units' transport requests, which
//!    AW2's units do not make: not built);
//! 9. the main pick, repeated: [`weigh`] scores every type against the enemy's army (all of it, fog or not, as
//!    Dual Strike does) less what the army already covers; the best one that the landmass rule, the indirect
//!    ratio, a safe factory and the funds allow is built, a Black Bomb or a Piperunner taking its place when
//!    wanted; a type it cannot pay for may start the army saving ([`Plan::should_save`]).
//!
//! **Here** the whole turn's list is worked out when state 5 starts (the return of `sub_08060DAC`, [`START`]),
//! stored in EWRAM ([`crate::ds_ai::BUILDS`]) and the loop's count set to its length; each pass of
//! `sub_08060718` then takes the next entry instead of AW2's pickers ([`TYPE`]), and `sub_080610D0` takes its
//! order ([`ROLE`]) and factory ([`SITE`]). AW2's price check and `BuyUnit` do the rest, so everything a
//! purchase does in AW2 (funds, the unit count, the new unit's records and picture) is AW2's own.
//!
//! The order (Dual Strike's `AiBuild_RollOrder`, weighted by the profile: 0 attack, 1 attack whatever the
//! odds, 2 enemy HQ, 3 contested properties, 4 escort foot units, 5 defend own properties, 6 defend the HQ) is
//! given to AW2 as its nearest role ([`role_of`]); units whose first weight is negative (foot units,
//! transports) and ships keep AW2's own roll.
//!
//! [`crate::cpu_tactics`]'s swap of Carriers, Ooziums and Piperunners into AW2's buys is off while this plays.

use mgba::core::Core;

use crate::ds_ai::*;

/// `sub_080606D0` just after `sub_08060DAC` returned the number of builds to try (r0).
pub const START: u32 = 0x0806_06E2;
/// `sub_08060718` before AW2's type pickers (r9: its argument; sl: the pointer to the action struct).
pub const TYPE: u32 = 0x0806_0794;
const TYPE_DONE: u32 = 0x0806_07AE;
/// `sub_080610D0` at its role roll (`bl sub_08061178` with the type - 1 in r0).
pub const ROLE: u32 = 0x0806_1102;
const ROLE_DONE: u32 = 0x0806_110E;
/// `sub_080610D0` at its factory pick (`mov r0, sp; bl sub_080611D8`): x, y at sp, sp + 2.
pub const SITE: u32 = 0x0806_1112;
const SITE_DONE: u32 = 0x0806_111E;
const ACTION: u32 = 0x0300_46C0;
/// The driver's state (`0x03004780`): 5 while production runs (all of it within one call of `sub_080606D0`).
const AI_STATE: u32 = 0x0300_4780;

/// One build: type, factory, AW2 role (0xFF: AW2's own roll).
#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Build {
    pub t: u8,
    pub x: i32,
    pub y: i32,
    pub role: u8,
}

/// AW2's role for a Dual Strike order: 0 and 1 attack (4, the nearest enemy units), 2 the enemy HQ (1), 3
/// contested properties (3, the enemy's properties), 4 escort foot units (4), 5 and 6 defend (7, by its HQ).
pub(crate) fn role_of(order: u8) -> u8 {
    match order {
        2 => 1,
        3 => 3,
        5 | 6 => 7,
        _ => 4,
    }
}

const NO_ROLE: u8 = 0xFF;

// --- Sites ----------------------------------------------------------------------------------

const BASE: u8 = 1;
const AIRPORT: u8 = 2;
const PORT: u8 = 3;
const ANY: u8 = 4;
/// Site marks: in use (built at this turn), nothing found for it (step 2), rejected while a type is tried.
const USED: u8 = 0xFD;
const NOTHING: u8 = 0xFE;
const REJECTED: u8 = 0xFF;
const FREE: u8 = 127;
const FAR: i32 = 110;

#[derive(Clone, Debug)]
struct Site {
    x: i32,
    y: i32,
    kind: u8,
    mark: u8,
    group: usize,
    balance: i32,
    enemies: i32,
    enemy_distance: i32,
    property_moves: i32,
    /// Infantry moves to the nearest own foot unit (`unk_09`).
    foot: i32,
    pipe: i32,
}

#[derive(Clone, Debug, Default)]
struct Group {
    threat: i32,
    skip_foot: bool,
    need_anti_air: bool,
    properties: i32,
    used_up: bool,
    /// `unk_03_2`: the first site's landmass holds no enemy armour and needs no sea transport.
    quiet: bool,
}

/// Anti-Air or Cruiser against aircraft (`AiBuild_PickAntiAir`).
const AA_NONE: u8 = 0;
const AA_AA: u8 = 1;
const AA_CRUISER: u8 = 2;
const AA_AA_MORE: u8 = 3;
const AA_CRUISER_MORE: u8 = 4;

/// Domain bits (`AI_DOMAIN_*`): ground, air, sea.
const D_GROUND: u8 = 1;
const D_AIR: u8 = 2;
const D_SEA: u8 = 4;

/// Target groups (`gAiTargetGroupType`): the type that stands for each.
const GROUPS: [u8; 9] = [INFANTRY, ARTILLERY, 3, BOMBER, 19, BATTLESHIP, CRUISER, LANDER, SUB];

fn target_group(t: u8) -> Option<usize> {
    Some(match t {
        1 | 2 => 0,
        RECON | APC | PIPERUNNER | ARTILLERY | 11 | 15 => 1,
        3 | TANK | 8 | ANTI_AIR => 2,
        STEALTH | BLACK_BOMB | FIGHTER | BOMBER => 3,
        19 | T_COPTER => 4,
        BATTLESHIP => 5,
        CRUISER => 6,
        BLACK_BOAT | LANDER | CARRIER => 7,
        SUB => 8,
        _ => return None,
    })
}

pub(crate) struct Plan<'a> {
    core: &'a Core,
    b: Board,
    army: u32,
    prof: Profile,
    funds: i64,
    income: i64,
    reserve: i64,
    saving: i64,
    skips: i32,
    own: i32,
    sites: Vec<Site>,
    groups: Vec<Group>,
    any: u8,
    own_domains: u8,
    own_factories: u8,
    aa_pick: u8,
    threat: (Vec<u8>, Vec<u8>),
    scores: [u64; 28],
    enemy_hp: [i64; 28],
    own_hp: [i64; 28],
    pub builds: Vec<Build>,
    pub notes: Vec<String>,
    k: u32,
    /// Floods already worked out this turn (the planned units are the army's own, and block no flood of its own).
    floods: std::cell::RefCell<std::collections::HashMap<(u32, u8, i32, i32, i32, bool), std::rc::Rc<Vec<i16>>>>,
}

impl<'a> Plan<'a> {
    fn new(core: &'a Core, army: u32) -> Option<Plan<'a>> {
        let (co, _) = army_co(core, army);
        let prof = profile(co)?;
        let b = Board::read(core);
        Some(Plan {
            core,
            army,
            prof,
            funds: funds(core, army) as i64,
            income: income(core, army) as i64,
            reserve: 0,
            saving: 0,
            skips: 2,
            own: 0,
            sites: Vec::new(),
            groups: Vec::new(),
            any: 0,
            own_domains: 0,
            own_factories: 0,
            aa_pick: AA_NONE,
            threat: (vec![0; b.class.len()], vec![0; b.class.len()]),
            scores: [0; 28],
            enemy_hp: [0; 28],
            own_hp: [0; 28],
            builds: Vec::new(),
            notes: Vec::new(),
            k: 0,
            floods: Default::default(),
            b,
        })
    }

    /// [`Board::flood`], remembered for the turn.
    fn flood(&self, army: u32, t: u8, x: i32, y: i32, budget: i32, ring: bool) -> std::rc::Rc<Vec<i16>> {
        let key = (army, t, x, y, budget, ring);
        if let Some(f) = self.floods.borrow().get(&key) {
            return f.clone();
        }
        let f = std::rc::Rc::new(self.b.flood(army, t, x, y, budget, ring));
        self.floods.borrow_mut().insert(key, f.clone());
        f
    }

    fn price(&self, t: u8) -> i64 {
        price(self.core, self.army, t) as i64
    }

    fn allows(&self, t: u8) -> bool {
        t != PIPERUNNER && t != OOZIUM && crate::roster::ds_id(t).is_some() && self.prof.unit(t).build != 0
    }

    fn header(&self, k: usize) -> i64 {
        self.prof.header[k] as i64
    }

    fn flag(&self, mask: u8) -> bool {
        self.prof.header[9] & mask != 0
    }

    fn own_units(&self) -> impl Iterator<Item = &Unit> {
        let a = self.army;
        self.b.units.iter().filter(move |u| u.army == a)
    }

    fn count(&self, t: u8) -> i64 {
        self.own_units().filter(|u| u.t == t).count() as i64
    }

    fn foot_count(&self) -> i64 {
        self.own_units().filter(|u| u.t == INFANTRY || u.t == MECH).count() as i64
    }

    fn enemy(&self, a: u32) -> bool {
        self.b.playing[a as usize % 6] && !self.b.same_team(a, self.army)
    }

    fn harmless(&self, u: &Unit) -> bool {
        attack(u.t) == Attack::None && !self.b.units.iter().any(|c| c.carried() && c.army == u.army && (c.x, c.y) == (u.x, u.y))
    }

    // --- Step 0 -------------------------------------------------------------------------

    fn start(&mut self) {
        let b = &self.b;
        let army = self.army;
        // Domains (`AiTurn_FindUnitDomains`).
        let (mut any, mut own) = (0u8, 0u8);
        for i in 0..b.class.len() {
            let bit = match b.class[i] {
                C_BASE => D_GROUND,
                C_AIRPORT => D_AIR,
                C_PORT => D_SEA,
                _ => 0,
            };
            any |= bit;
            if b.owns(i, army) {
                own |= bit;
            }
        }
        self.own_factories = own;
        for u in &b.units {
            let g = stats(u.t).group;
            let bit = if g & SEA != 0 { D_SEA } else if g & AIR != 0 { D_AIR } else { 0 };
            any |= bit;
            if u.army == army {
                own |= bit;
            }
        }
        self.any = any;
        self.own_domains = own;
        // Sites (`AiSites_Collect`): free factories of the army.
        for y in 0..b.h {
            for x in 0..b.w {
                let i = b.idx(x, y);
                let kind = match b.class[i] {
                    C_BASE => BASE,
                    C_AIRPORT => AIRPORT,
                    C_PORT => PORT,
                    _ => continue,
                };
                if !b.owns(i, army) || b.at[i] != 0 {
                    continue;
                }
                self.sites.push(Site {
                    x,
                    y,
                    kind,
                    mark: FREE,
                    group: usize::MAX,
                    balance: 0,
                    enemies: 0,
                    enemy_distance: 0xFF,
                    property_moves: 0xFF,
                    foot: 0xFF,
                    pipe: 0,
                });
            }
        }
        if logging() {
            let mut by = std::collections::BTreeMap::new();
            for i in 0..b.class.len() {
                if matches!(b.class[i], C_BASE | C_AIRPORT | C_PORT) {
                    *by.entry((b.owner[i], b.at[i] != 0)).or_insert(0) += 1;
                }
            }
            self.notes.push(format!("sites {} (factories by (owner, taken) {by:?})", self.sites.len()));
        }
        self.build_groups();
        // Own units and the repair reserve (`AiEndActions_Start`).
        self.own = self.own_units().count() as i32;
        let mut reserve = 0i64;
        for u in self.own_units() {
            if self.b.repairs(u) && u.hp < 91 {
                let shown = (u.hp + 9) / 10;
                reserve += (2.min(10 - shown)).max(0) as i64 * self.price(u.t) / 10;
            }
        }
        self.reserve = (reserve * 3 >> 1).max(1000);
        self.saving = 0;
        self.skips = 2;
        self.threat = self.threat_maps(ANTI_AIR);
    }

    /// `AiSites_BuildGroups` and `AiSiteGroup_RateSurroundings`.
    fn build_groups(&mut self) {
        let army = self.army;
        for s in 0..self.sites.len() {
            if self.sites[s].group != usize::MAX {
                continue;
            }
            let g = self.groups.len();
            let (sx, sy) = (self.sites[s].x, self.sites[s].y);
            let reach = self.flood(army, INFANTRY, sx, sy, FAR, false);
            for o in self.sites.iter_mut() {
                if reach[self.b.idx(o.x, o.y)] >= 0 {
                    o.group = g;
                }
            }
            let mut grp = Group::default();
            let (mut ground, mut air) = (0u8, 0u8);
            for i in 0..reach.len() {
                if reach[i] < 0 {
                    continue;
                }
                if let Some(k) = Some(self.b.at[i]).filter(|&k| k != 0) {
                    let u = self.b.units[k as usize - 1];
                    if self.b.same_team(u.army, army) {
                        if attack(u.t) != Attack::None {
                            grp.threat -= 1;
                        }
                        if u.t <= MECH && u.hp >= 61 {
                            grp.skip_foot = true;
                        }
                        if (u.t == ANTI_AIR || u.t == FIGHTER) && u.hp >= 61 {
                            air |= 1;
                        }
                    } else if !self.harmless(&u) {
                        grp.threat += 2;
                        let st = stats(u.t);
                        if st.group & GROUND != 0 && u.t > MECH {
                            ground |= 1;
                        }
                        if st.group & AIR != 0 && u.t != T_COPTER {
                            air |= 2;
                        }
                    }
                }
                if PROPERTIES.contains(&self.b.class[i]) && !self.owned_by_team(i) {
                    self.sites[s].property_moves = self.sites[s].property_moves.min(reach[i] as i32);
                    ground |= 2;
                    grp.properties += 1;
                }
            }
            if ground & 1 != 0 || ground & 2 == 0 {
                grp.skip_foot = true;
            }
            grp.need_anti_air = air & 1 == 0 && air & 2 != 0;
            let land = self.rate_landmass(sx, sy);
            grp.quiet = !(land & 0x100 != 0 || land & 0xFF == 0);
            self.groups.push(grp);
            self.rate_surroundings(g, sx, sy);
        }
    }

    fn owned_by_team(&self, i: usize) -> bool {
        self.b.team_owns(i, self.army)
    }

    /// `AiSite_UnitCanReach`: at a base a ground unit must stand where the reach (`reach`) gets to, a ship
    /// carry cargo; at a port ground units never count; aircraft always do.
    fn can_reach(&self, kind: u8, u: &Unit, reach: &[i16]) -> bool {
        let g = stats(u.t).group;
        if kind == BASE {
            if g & GROUND != 0 && reach[self.b.idx(u.x, u.y)] < 0 {
                return false;
            }
            if g & SEA != 0 && !self.b.units.iter().any(|c| c.carried() && c.army == u.army && (c.x, c.y) == (u.x, u.y)) {
                return false;
            }
        }
        !(kind == PORT && g & GROUND != 0)
    }

    fn rate_surroundings(&mut self, g: usize, fx: i32, fy: i32) {
        let army = self.army;
        // (Dual Strike's range map is the group's first site's Tank reach here, left by `AiSite_RateLandmass`.)
        let reach = self.flood(army, TANK, fx, fy, FAR, true);
        let r = self.header(8) as i32;
        let enemies: Vec<Unit> = self.b.units.iter().filter(|u| !u.carried() && self.enemy(u.army)).copied().collect();
        for s in 0..self.sites.len() {
            if self.sites[s].group != g {
                continue;
            }
            let kind = self.sites[s].kind;
            let (sx, sy) = (self.sites[s].x, self.sites[s].y);
            for u in &enemies {
                if self.can_reach(kind, u, &reach) {
                    let d = (u.x - sx).abs() + (u.y - sy).abs();
                    self.sites[s].enemy_distance = self.sites[s].enemy_distance.min(d);
                }
            }
            let near = self.flood(army, TANK, sx, sy, r, false);
            let (mut bal, mut count) = (0, 0);
            for u in self.b.units.iter().filter(|u| !u.carried()) {
                let d = (u.x - sx).abs() + (u.y - sy).abs();
                if d > r || !self.can_reach(kind, u, &reach) || self.harmless(u) {
                    continue;
                }
                if stats(u.t).group & GROUND != 0 && near[self.b.idx(u.x, u.y)] < 0 {
                    continue;
                }
                if self.b.same_team(u.army, army) {
                    bal -= 1;
                    continue;
                }
                if !self.b.playing[u.army as usize % 6] {
                    continue;
                }
                bal += if kind == PORT || u.t <= MECH { 1 } else { 2 };
                count += 1;
            }
            self.sites[s].balance = bal;
            self.sites[s].enemies = count;
            if self.sites[s].property_moves == 0xFF {
                let inf = self.flood(army, INFANTRY, sx, sy, FAR, false);
                for i in 0..inf.len() {
                    if inf[i] >= 0 && PROPERTIES.contains(&self.b.class[i]) && !self.owned_by_team(i) {
                        self.sites[s].property_moves = self.sites[s].property_moves.min(inf[i] as i32);
                    }
                }
            }
        }
    }

    /// `AiSite_RateLandmass`: 0 when the Tank reach from (x, y) holds a pipe seam, an enemy base or enemy
    /// armour (or an enemy Piperunner next to it); otherwise 1 when a unit there stands on a property to take,
    /// else the army's foot units there + 1; bit 8 when the landmass wants sea transport.
    fn rate_landmass(&self, x: i32, y: i32) -> i32 {
        let army = self.army;
        let reach = self.flood(army, TANK, x, y, FAR, true);
        let wants_sea = self.prof.header[9] & 0x0C != 0;
        let landers = self.count(LANDER) > 0;
        let (mut capturable, mut foot, mut transport) = (false, 0, false);
        for i in 0..reach.len() {
            let d = reach[i];
            if d < 0 {
                continue;
            }
            let class = self.b.class[i];
            if class == C_SEAM {
                return 0;
            }
            let unit = Some(self.b.at[i]).filter(|&k| k != 0).map(|k| self.b.units[k as usize - 1]);
            if d as i32 > FAR {
                if unit.is_some_and(|u| !self.b.same_team(u.army, army) && u.t == PIPERUNNER) {
                    return 0;
                }
                continue;
            }
            if class == C_BASE && self.b.owner[i] != 0 && !self.b.team_owns(i, army) {
                return 0;
            }
            if !transport {
                if class == C_PORT && (landers || wants_sea) {
                    transport = true;
                }
                if class == C_SHOAL && (landers || (self.own_factories & D_SEA != 0 && wants_sea)) {
                    transport = true;
                }
            }
            let Some(u) = unit else { continue };
            if PROPERTIES.contains(&class) && !self.owned_by_team(i) {
                capturable = true;
            }
            if !self.b.same_team(u.army, army) {
                if stats(u.t).group & GROUND != 0 && u.t > MECH {
                    return 0;
                }
            } else if u.army == army && u.t <= MECH {
                foot += 1;
            }
        }
        let low = if capturable { 1 } else { foot + 1 };
        low | if transport { 0x100 } else { 0 }
    }

    /// The threat maps against type `vs` (`AiEndActions_BuildThreatMaps`, `AiEndActions_AddEnemyThreat`): per cell
    /// the most a direct enemy that can get next to it would do (`threatMax`) and the sum of the indirect fire
    /// that covers it (`threatSum`). Empty under Strike and in a Tag Power's first half.
    fn threat_maps(&self, vs: u8) -> (Vec<u8>, Vec<u8>) {
        let n = self.b.class.len();
        let (mut max, mut sum) = (vec![0u8; n], vec![0u8; n]);
        if behaviour(self.core, self.army) == STRIKE || crate::tag::phase(self.core, self.army) == 1 {
            return (max, sum);
        }
        for u in self.b.units.iter().filter(|u| !u.carried() && self.enemy(u.army)) {
            let damage = rated_damage(u.t, vs);
            if damage < 25 {
                continue;
            }
            let direct = attack(u.t) == Attack::Direct;
            if direct && base_damage(vs, u.t) >= 50 {
                continue;
            }
            let mut hp = u.hp;
            if self.b.repairs(u) {
                hp += 20;
            }
            let threat = (damage * hp.min(100) / 100).min(255) as u8;
            if direct {
                let reach = self.flood(u.army, u.t, u.x, u.y, self.b.moves(u.army, u.t), true);
                for i in 0..n {
                    if reach[i] >= 0 && threat > max[i] {
                        max[i] = threat;
                    }
                }
            } else if attack(u.t) == Attack::Indirect {
                let (lo, hi) = (stats(u.t).min_range as i32, self.b.max_range(u.army, u.t));
                for y in (u.y - hi).max(0)..=(u.y + hi).min(self.b.h - 1) {
                    for x in (u.x - hi).max(0)..=(u.x + hi).min(self.b.w - 1) {
                        let d = (x - u.x).abs() + (y - u.y).abs();
                        if d >= lo && d <= hi {
                            let i = self.b.idx(x, y);
                            sum[i] = sum[i].saturating_add(threat);
                        }
                    }
                }
            }
        }
        (max, sum)
    }

    // --- Site picks ----------------------------------------------------------------------

    /// `AiSite_NearUnguardedOozium`: an enemy Oozium next to the site with none of the army's team beside it.
    fn near_oozium(&self, x: i32, y: i32) -> bool {
        if crate::tag::phase(self.core, self.army) == 1 {
            return false;
        }
        [(0, -1), (1, 0), (0, 1), (-1, 0)].iter().any(|&(dx, dy)| {
            let (ox, oy) = (x + dx, y + dy);
            self.b.unit_at(ox, oy).is_some_and(|u| u.t == OOZIUM && !self.b.same_team(u.army, self.army))
                && ![(0, -1), (1, 0), (0, 1), (-1, 0)]
                    .iter()
                    .any(|&(ex, ey)| self.b.unit_at(ox + ex, oy + ey).is_some_and(|v| self.b.same_team(v.army, self.army)))
        })
    }

    fn open(&self, s: usize, kind: u8) -> bool {
        let site = &self.sites[s];
        site.mark < USED && !self.near_oozium(site.x, site.y) && (kind == ANY || site.kind == kind)
    }

    /// The open site of `kind` (and group, if given) with the least `key` (ties: the first).
    fn pick_min(&self, kind: u8, group: Option<usize>, key: impl Fn(&Site) -> i32, limit: i32) -> Option<usize> {
        let mut best = None;
        let mut low = limit;
        for s in 0..self.sites.len() {
            if !self.open(s, kind) || group.is_some_and(|g| self.sites[s].group != g) {
                continue;
            }
            let v = key(&self.sites[s]);
            if low > v {
                low = v;
                best = Some(s);
            }
        }
        best
    }

    /// The open site with the most enemies about (more than 0).
    fn most_enemies(&self, kind: u8, group: Option<usize>) -> Option<usize> {
        self.pick_min(kind, group, |s| -s.enemies, 0)
    }

    fn first(&self, kind: u8) -> Option<usize> {
        (0..self.sites.len()).find(|&s| self.open(s, kind))
    }

    /// `AiSite_PickForBuild`: the most threatened group (with two or more), the most enemies, the nearest enemy
    /// (a base in a quiet group counting 255 further), the first.
    fn pick_for_build(&mut self, kind: u8) -> Option<usize> {
        if self.groups.len() >= 2 {
            for g in self.groups.iter_mut() {
                g.used_up = false;
            }
            loop {
                let found = (0..self.groups.len())
                    .filter(|&g| !self.groups[g].used_up && self.groups[g].threat > 0)
                    .max_by_key(|&g| (self.groups[g].threat, std::cmp::Reverse(g)));
                let Some(g) = found else { break };
                if let Some(s) = self.most_enemies(kind, Some(g)) {
                    return Some(s);
                }
                self.groups[g].used_up = true;
            }
        }
        if let Some(s) = self.most_enemies(kind, None) {
            return Some(s);
        }
        let groups = &self.groups;
        if let Some(s) = self.pick_min(
            kind,
            None,
            |s| s.enemy_distance + if s.kind == BASE && groups.get(s.group).is_some_and(|g| g.quiet) { 255 } else { 0 },
            0x7FFF,
        ) {
            return Some(s);
        }
        self.first(kind)
    }

    fn clear_rejected(&mut self) {
        for s in self.sites.iter_mut() {
            if s.mark == REJECTED {
                s.mark = FREE;
            }
        }
    }

    fn clear_marks(&mut self) {
        for s in self.sites.iter_mut() {
            if s.mark == REJECTED || s.mark == NOTHING {
                s.mark = FREE;
            }
        }
    }

    // --- Ratings ---------------------------------------------------------------------------

    /// `AiBuild_RateSiteDanger`: what the enemies 1..9 away that can hit a `t` built at (x, y) would do.
    fn site_danger(&self, x: i32, y: i32, t: u8) -> i32 {
        let air = stats(t).group & AIR != 0;
        let mut cover = 0;
        if air {
            let reach = self.flood(self.army, FIGHTER, x, y, self.b.moves(self.army, FIGHTER), true);
            for u in self.b.units.iter().filter(|u| !u.carried() && u.t == FIGHTER && self.b.same_team(u.army, self.army)) {
                if reach[self.b.idx(u.x, u.y)] >= 0 {
                    cover += u.hp;
                }
            }
        }
        let (mut total, mut air_max) = (0, 0);
        for u in self.b.units.iter().filter(|u| !u.carried() && !self.b.same_team(u.army, self.army)) {
            let d = (u.x - x).abs() + (u.y - y).abs();
            if !(1..=9).contains(&d) {
                continue;
            }
            let hits_next_to = |me: &Self| {
                let r = me.flood(u.army, u.t, u.x, u.y, me.b.moves(u.army, u.t), true);
                r[me.b.idx(x, y)] >= 0
            };
            let damage = base_damage(u.t, t) * u.hp / 100;
            if cover < 100 && (u.t == FIGHTER || u.t == STEALTH) && air {
                if !hits_next_to(self) {
                    continue;
                }
                if t != FIGHTER && t != STEALTH {
                    total += damage;
                } else {
                    air_max = air_max.max(damage);
                }
                continue;
            }
            if ((air || t == BLACK_BOAT) && u.t == CRUISER) || (air && u.t == ANTI_AIR) || ((t == BATTLESHIP || t == CARRIER) && u.t == SUB) {
                if !hits_next_to(self) {
                    continue;
                }
                total += if (t == BOMBER || t == STEALTH) && u.t == ANTI_AIR { damage >> 1 } else { damage };
                continue;
            }
            let range = self.b.max_range(u.army, u.t);
            if range <= 1 || range < d || (stats(u.t).min_range as i32) > d {
                continue;
            }
            total += damage;
        }
        total + air_max
    }

    /// `Ai_BestDamage` (`Ai_CoPairBestDamage` with `pair`, averaging the partner's) at power state `mode`.
    fn best_damage(&self, att: u8, def: u8, mode: u8, pair: bool) -> i64 {
        let one = |slot: u32, w: u32| self.b.slot_damage(self.core, self.army, slot, mode, att, def, w);
        let (mut p, mut s) = (one(0, 0), one(0, 1));
        if pair && crate::tag::partner(self.core, self.army).is_some() {
            p = (p + one(1, 0)) >> 1;
            s = (s + one(1, 1)) >> 1;
        }
        p.max(s) as i64
    }

    /// The best damage against a dived Sub.
    fn best_damage_dived(&self, att: u8, mode: u8, pair: bool) -> i64 {
        self.best_damage(att, crate::roster::DIVED_SUB, mode, pair)
    }

    /// `AiBuild_ScaleByReach`.
    fn scale_by_reach(&self, s: i64, t: u8) -> i64 {
        let st = stats(t);
        let mut s = if attack(t) == Attack::Indirect {
            s * (self.b.max_range(self.army, t) as i64 + 4 - st.min_range as i64) >> 3
        } else {
            s * self.b.moves(self.army, t) as i64 >> 3
        };
        if t == RECON {
            s >>= 1;
        }
        s
    }

    /// `AiBuild_RateAttackerVsTarget`, at Super power (state 2).
    fn rate(&self, a: u8, target: u8) -> i64 {
        let a = if a == ANTI_AIR && target <= MECH { TANK } else { a };
        let mut s = if target == INFANTRY {
            self.best_damage(a, target, 2, true) >> 1
        } else if target == SUB {
            (self.best_damage(a, target, 2, true) >> 1) + self.best_damage_dived(a, 2, true)
        } else {
            self.best_damage(a, target, 2, false)
        };
        let (ga, gt) = (stats(a).group, stats(target).group);
        if ga & GROUND != 0 && gt & SEA != 0 {
            s >>= 1;
        }
        if ga & SEA != 0 && gt & SEA != 0 {
            s <<= 1;
        }
        if a == SUB && target == BATTLESHIP {
            s <<= 1;
        }
        if gt & AIR != 0 {
            s <<= 1;
            if a == FIGHTER {
                s <<= 1;
            }
            if a == ANTI_AIR {
                if (self.aa_pick == AA_CRUISER || self.aa_pick == AA_CRUISER_MORE) && self.count(ANTI_AIR) != 0 {
                    s >>= 1;
                }
                if self.aa_pick == AA_AA_MORE {
                    s <<= 1;
                }
            }
            if a == CRUISER {
                if (self.aa_pick == AA_AA || self.aa_pick == AA_AA_MORE) && self.count(CRUISER) != 0 {
                    s >>= 1;
                }
                if self.aa_pick == AA_CRUISER_MORE {
                    s <<= 1;
                }
            }
        }
        self.scale_by_reach(s, a) * self.prof.unit(a).build as i64 / 100
    }

    /// `AiBuild_PickAntiAir`.
    fn pick_anti_air(&self) -> u8 {
        if self.own_domains & D_SEA == 0 {
            return AA_NONE;
        }
        let (mut aa, mut cruiser, mut air_hp) = (0i32, 0i32, 0i32);
        for u in &self.b.units {
            if !self.b.playing[u.army as usize % 6] {
                continue;
            }
            if self.b.same_team(u.army, self.army) {
                if u.t == ANTI_AIR {
                    aa -= 1;
                }
                if u.t == CRUISER {
                    cruiser -= 1;
                }
                if crate::roster::ds_record(u.t).is_some_and(|r| r[0x21] & 1 != 0) {
                    air_hp -= u.hp;
                }
            } else {
                if stats(u.t).group & AIR == 0 || !self.b.inside(u.x, u.y) {
                    continue;
                }
                let i = self.b.idx(u.x, u.y);
                if self.b.class[i] == C_AIRPORT && self.b.owns(i, u.army) {
                    continue;
                }
                if self.b.cost(self.army, CRUISER, u.x, u.y) != 0xFF {
                    cruiser += 1;
                } else {
                    aa += 1;
                }
                if u.t != T_COPTER && stats(u.t).category & 3 != 0 {
                    air_hp += u.hp;
                }
            }
        }
        if aa < 0 && cruiser < 0 {
            AA_NONE
        } else if aa > cruiser {
            if air_hp > 0 { AA_AA_MORE } else { AA_AA }
        } else if aa < cruiser {
            if air_hp > 0 { AA_CRUISER_MORE } else { AA_CRUISER }
        } else {
            AA_NONE
        }
    }

    /// `AiBuild_SumUnitHp` (`site`: `AiSite_SumNearbyUnitHp`, the units within the profile's radius, ground
    /// ones only where a Tank from the site gets within it), then `AiBuild_WeighUnitTypes`.
    fn weigh(&mut self, site: Option<usize>) {
        self.enemy_hp = [0; 28];
        self.own_hp = [0; 28];
        let r = self.header(8) as i32;
        let near = site.map(|s| (self.sites[s].x, self.sites[s].y, self.flood(self.army, TANK, self.sites[s].x, self.sites[s].y, r, false)));
        for u in &self.b.units {
            if !self.b.playing[u.army as usize % 6] {
                continue;
            }
            if let Some((sx, sy, reach)) = &near {
                if u.carried() || (u.x - sx).abs() + (u.y - sy).abs() > r {
                    continue;
                }
                if stats(u.t).group & GROUND != 0 && reach[self.b.idx(u.x, u.y)] < 0 {
                    continue;
                }
            }
            if self.b.same_team(u.army, self.army) {
                self.own_hp[u.t as usize % 28] += u.hp as i64;
            } else {
                self.enemy_hp[u.t as usize % 28] += u.hp as i64;
            }
        }
        self.aa_pick = self.pick_anti_air();
        self.scores = [0; 28];
        let mut g = [0i64; 9];
        for t in types() {
            if let Some(k) = target_group(t) {
                g[k] += self.enemy_hp[t as usize];
            }
        }
        if self.any & D_SEA != 0 && self.any & D_AIR == 0 {
            g[7] *= 2;
        }
        for a in types() {
            if !self.allows(a) {
                continue;
            }
            for k in 0..9 {
                if g[k] == 0 {
                    continue;
                }
                let rep = GROUPS[k];
                let base = if rep == SUB { self.best_damage_dived(a, 0, false) } else { self.best_damage(a, rep, 0, false) };
                let mut d = self.scale_by_reach(base * self.own_hp[a as usize], a);
                if stats(rep).group & AIR != 0 {
                    if a == ANTI_AIR && (self.aa_pick == AA_CRUISER || self.aa_pick == AA_CRUISER_MORE) {
                        d >>= 1;
                    }
                    if a == CRUISER && (self.aa_pick == AA_AA || self.aa_pick == AA_AA_MORE) {
                        d >>= 1;
                    }
                }
                g[k] -= d / 100;
            }
        }
        let has_air = self.any & D_AIR != 0;
        let candidates: Vec<u8> = types().filter(|&t| self.allows(t) && (t != ANTI_AIR || has_air)).collect();
        if g.iter().any(|&v| v > 0) {
            for &c in &candidates {
                let mut s: i64 = (0..9).filter(|&k| g[k] > 0).map(|k| self.rate(c, GROUPS[k]) * g[k]).sum();
                for _ in 0..self.count(c) {
                    s -= s >> 3;
                }
                self.scores[c as usize] = s.max(0) as u64;
            }
            return;
        }
        let least = g.iter().copied().min().unwrap_or(0).min(0);
        if least != 0 {
            for &c in &candidates {
                let mut s: i64 = (0..9).filter(|&k| g[k] != 0).map(|k| self.rate(c, GROUPS[k]) * (g[k] - (least - 1))).sum();
                for _ in 0..self.count(c) {
                    s -= s >> 2;
                }
                self.scores[c as usize] = s.max(0) as u64;
            }
            return;
        }
        for &c in &candidates {
            if self.best_damage(c, INFANTRY, 0, false) == 0 {
                continue;
            }
            let mut s = self.price(c) / 10;
            for _ in 0..self.count(c) {
                s -= s >> 2;
            }
            self.scores[c as usize] = s.max(0) as u64;
        }
    }

    // --- Queueing ------------------------------------------------------------------------------

    /// `AiTurn_QueueBuildAtSite`: the order roll, the site used, the unit counted as the army's.
    fn queue(&mut self, s: usize, t: u8, step: u8) {
        let site = self.sites[s].clone();
        self.sites[s].mark = USED;
        let order = self.roll_order(t);
        let role = order.map_or(NO_ROLE, role_of);
        self.funds -= self.price(t);
        self.own += 1;
        self.b.units.push(Unit { rec: 0, army: self.army, t, x: site.x, y: site.y, hp: 100, flags: 0 });
        let k = self.b.units.len() as u16;
        let i = self.b.idx(site.x, site.y);
        self.b.at[i] = k;
        self.builds.push(Build { t, x: site.x, y: site.y, role });
        if logging() {
            self.notes.push(format!(
                "step {step} {} at ({},{}) order {} role {} funds left {}",
                crate::bh_smart::NAMES[t as usize % 28],
                site.x,
                site.y,
                order.map_or("-".to_string(), |o| o.to_string()),
                if role == NO_ROLE { "AW2".to_string() } else { role.to_string() },
                self.funds
            ));
        }
    }

    /// `AiBuild_RollOrder`: None where AW2's own roll stands (a negative first weight, a ship).
    fn roll_order(&mut self, t: u8) -> Option<u8> {
        let w = self.prof.unit(t).weights;
        if w[0] < 0 || stats(t).group & SEA != 0 {
            return None;
        }
        let mut excluded = 0u8;
        if let Some((hx, hy)) = self.hq() {
            let base_near = (0..self.b.class.len()).any(|i| {
                let (x, y) = (i as i32 % self.b.w, i as i32 / self.b.w);
                self.b.class[i] == C_BASE && self.b.owns(i, self.army) && (x - hx).abs() + (y - hy).abs() <= 4
            });
            let enemy_near = self
                .b
                .units
                .iter()
                .any(|u| !u.carried() && !self.b.same_team(u.army, self.army) && (u.x - hx).abs() + (u.y - hy).abs() <= 6);
            if base_near && !enemy_near {
                excluded |= 1 << 6;
            }
        }
        let weights: Vec<u32> = (0..7).map(|i| if excluded & (1 << i) != 0 { 0 } else { w[i].max(0) as u32 }).collect();
        let total: u32 = weights.iter().sum();
        if total == 0 {
            return Some(0);
        }
        self.k += 1;
        let mut r = roll(self.core, self.army, Roll::Order, self.k, total);
        for (i, &wi) in weights.iter().enumerate() {
            if wi > r {
                return Some(i as u8);
            }
            r -= wi;
        }
        Some(0)
    }

    fn hq(&self) -> Option<(i32, i32)> {
        (0..self.b.class.len())
            .find(|&i| self.b.class[i] == C_HQ && self.b.owns(i, self.army))
            .map(|i| (i as i32 % self.b.w, i as i32 / self.b.w))
    }

    fn afford(&self, t: u8) -> bool {
        self.price(t) <= self.funds
    }

    // --- Steps -------------------------------------------------------------------------------

    /// Step 1 (`func_02091EB0`): an Anti-Air for a group with enemy aircraft about and no cover.
    fn step_anti_air(&mut self) -> bool {
        if self.own_domains & D_SEA == 0 || self.prof.unit(ANTI_AIR).build == 0 || !self.afford(ANTI_AIR) {
            return false;
        }
        for g in 0..self.groups.len() {
            if !self.groups[g].need_anti_air {
                continue;
            }
            // (Dual Strike asks for the most enemies, then, if that found one, for the nearest enemy.)
            let s = self.most_enemies(BASE, Some(g)).and_then(|_| self.pick_min(BASE, Some(g), |s| s.enemy_distance, 0x7FFF));
            if let Some(s) = s {
                let i = self.b.idx(self.sites[s].x, self.sites[s].y);
                if self.threat.0[i] < 50 && self.threat.1[i] < 50 {
                    self.groups[g].need_anti_air = false;
                    self.queue(s, ANTI_AIR, 1);
                    return true;
                }
            }
        }
        false
    }

    /// Step 2 (`AiTurn_TrySiteAction`): a unit for the site with the most enemies against friends around it.
    fn step_site(&mut self) -> bool {
        let Some(s) = self.pick_min(ANY, None, |s| -s.balance, 0) else { return false };
        self.weigh(Some(s));
        match self.choose_for_site(s) {
            Some(t) => self.queue(s, t, 2),
            None => self.sites[s].mark = NOTHING,
        }
        true
    }

    /// `AiSite_ChooseUnitToBuild`.
    fn choose_for_site(&mut self, s: usize) -> Option<u8> {
        let (kind, x, y) = (self.sites[s].kind, self.sites[s].x, self.sites[s].y);
        if kind == PORT && self.any & D_AIR != 0 {
            return None;
        }
        let mut retried = false;
        'pick: loop {
            let best = types()
                .filter(|&t| !(attack(t) == Attack::Indirect && stats(t).group & GROUND != 0))
                .filter(|&t| self.scores[t as usize] > 0)
                .max_by_key(|&t| (self.scores[t as usize], std::cmp::Reverse(t)))?;
            let ok = 'ok: {
                if supply(best) != kind || !self.afford(best) {
                    break 'ok false;
                }
                let air = stats(best).group & AIR != 0;
                if !retried || air {
                    if self.site_danger(x, y, best) < 90 {
                        break 'ok true;
                    }
                    if air {
                        break 'ok false;
                    }
                    retried = true;
                    continue 'pick;
                }
                let cost = self.price(best);
                !(cost > self.income >> 1 && cost > self.funds >> 1)
            };
            if ok {
                return Some(best);
            }
            self.scores[best as usize] = 0;
        }
    }

    /// Step 3 (`AiTurn_TryBuildFighter`).
    fn step_fighter(&mut self) -> bool {
        if self.own_factories & D_AIR == 0 || self.prof.unit(FIGHTER).build == 0 || !self.afford(FIGHTER) {
            return false;
        }
        if self.own_units().any(|u| u.t == FIGHTER && u.hp >= 50) {
            return false;
        }
        if !self.b.units.iter().any(|u| self.enemy(u.army) && stats(u.t).group & AIR != 0) {
            return false;
        }
        let threat = self.threat_maps(FIGHTER);
        let mut best = None;
        let (mut count, mut dist) = (0, 0x7FFF);
        for s in 0..self.sites.len() {
            if !self.open(s, AIRPORT) {
                continue;
            }
            let i = self.b.idx(self.sites[s].x, self.sites[s].y);
            if threat.0[i] >= 40 || threat.1[i] >= 40 {
                continue;
            }
            let site = &self.sites[s];
            if count > site.enemies || (count == site.enemies && dist < site.enemy_distance) {
                continue;
            }
            count = site.enemies;
            dist = site.enemy_distance;
            best = Some(s);
        }
        match best {
            Some(s) => {
                self.queue(s, FIGHTER, 3);
                true
            }
            None => false,
        }
    }

    /// The enemy Subs' reach: per cell, `count` the Subs that get there (or next to it), else the least move
    /// cost of one (127: none); a Sub with a Cruiser of the team (40 hp or more) in its reach is left out.
    fn sub_reach(&self, count: bool) -> Vec<i32> {
        let mut out = vec![if count { 0 } else { 127 }; self.b.class.len()];
        for u in self.b.units.iter().filter(|u| !u.carried() && u.t == SUB && u.hp > 20 && self.enemy(u.army)) {
            let reach = self.flood(u.army, SUB, u.x, u.y, FAR, true);
            let guarded = self.b.units.iter().any(|c| {
                !c.carried() && c.t == CRUISER && c.hp >= 40 && self.b.same_team(c.army, self.army) && reach[self.b.idx(c.x, c.y)] >= 0
            });
            if guarded {
                continue;
            }
            for i in 0..out.len() {
                if reach[i] >= 0 {
                    out[i] = if count { out[i] + 1 } else { out[i].min(reach[i] as i32) };
                }
            }
        }
        out
    }

    /// Steps 4 and 5 (`func_02091C54`, `AiTurn_TryBuildCruiser`): a Cruiser at the port enemy Subs reach most
    /// (danger under 60), or at the port nearest an enemy Sub (under 40).
    fn step_cruiser(&mut self, against_subs: bool) -> bool {
        if self.own_factories & D_SEA == 0 || self.prof.unit(CRUISER).build == 0 || !self.afford(CRUISER) {
            return false;
        }
        let reach = self.sub_reach(against_subs);
        let mut best = None;
        let mut bv = if against_subs { 0 } else { 126 };
        for s in 0..self.sites.len() {
            if !self.open(s, PORT) {
                continue;
            }
            let v = reach[self.b.idx(self.sites[s].x, self.sites[s].y)];
            let better = if against_subs { v > bv } else { v <= bv };
            if !better {
                continue;
            }
            let limit = if against_subs { 60 } else { 40 };
            if self.site_danger(self.sites[s].x, self.sites[s].y, CRUISER) < limit {
                bv = v;
                best = Some(s);
            }
        }
        match best {
            Some(s) => {
                self.queue(s, CRUISER, if against_subs { 4 } else { 5 });
                true
            }
            None => false,
        }
    }

    /// Step 6 (`AiTurn_TryBuildFootUnit`).
    fn step_foot(&mut self) -> bool {
        if !self.afford(INFANTRY) {
            return false;
        }
        let mut s = None;
        for g in 0..self.groups.len() {
            if self.groups[g].skip_foot {
                continue;
            }
            s = self.pick_min(BASE, Some(g), |s| s.property_moves, 0x7FFF);
            if s.is_some() {
                break;
            }
        }
        let s = s.or_else(|| self.pick_min(BASE, None, |s| s.property_moves, 0x7FFF)).or_else(|| self.first(BASE));
        let Some(s) = s else { return false };
        let g = self.sites[s].group;
        if !self.groups[g].skip_foot {
            self.groups[g].skip_foot = true;
        } else if self.foot_count() >= self.header(0) + self.header(1) {
            return false;
        }
        let day = self.b.day as i64;
        let chance = if day > 3 { (self.header(2) * day).min(80) } else { 0 };
        self.k += 1;
        let r = roll(self.core, self.army, Roll::Mech, self.k, 100) as i64;
        let t = if r < chance && self.funds >= self.price(MECH) * 2 { MECH } else { INFANTRY };
        self.queue(s, t, 6);
        true
    }

    /// Step 7 (`func_02092134`): each site's Infantry moves to the nearest own foot unit.
    fn foot_distances(&mut self) {
        let feet: Vec<(i32, i32)> = self.own_units().filter(|u| u.t <= MECH && !u.carried()).map(|u| (u.x, u.y)).collect();
        for s in 0..self.sites.len() {
            if feet.is_empty() {
                break;
            }
            let reach = self.flood(self.army, INFANTRY, self.sites[s].x, self.sites[s].y, FAR, false);
            self.sites[s].foot = feet.iter().map(|&(x, y)| reach[self.b.idx(x, y)] as i32).filter(|&d| d >= 0).min().unwrap_or(0xFF);
        }
    }

    /// Step 8 (`func_02090154`): T-Copter, Black Boat and APC by their ratios.
    fn step_transport(&mut self) -> bool {
        let foot = self.foot_count();
        let day = self.b.day as i64;
        // T-Copter (`AiTurn_TryBuildTCopter`; propertyRegions taken as 1).
        if self.afford(T_COPTER) && !(self.header(11) != 0 && day > self.header(11)) {
            let s = self.pick_min(AIRPORT, None, |s| s.foot, 0x7FFF).or_else(|| self.first(AIRPORT));
            if let Some(s) = s {
                if foot != 0 && self.count(T_COPTER) * 100 / foot < self.header(3) {
                    self.queue(s, T_COPTER, 8);
                    return true;
                }
            }
        }
        // Black Boat for the fleet (`AiTurn_TryBuildBlackBoat`).
        if self.flag(4) && self.afford(BLACK_BOAT) {
            if let Some(s) = self.pick_for_build(PORT) {
                let armed = self.own_units().filter(|u| stats(u.t).group & SEA != 0 && attack(u.t) != Attack::None).count() as i64;
                if armed + 1 >= (self.count(BLACK_BOAT) + 1) * 3 {
                    self.queue(s, BLACK_BOAT, 8);
                    return true;
                }
            }
        }
        // APC (`AiTurn_TryBuildApc`).
        if self.afford(APC) && !(self.header(10) != 0 && day > self.header(10)) {
            let groups = &self.groups;
            let s = self.pick_min(BASE, None, |s| if groups.get(s.group).is_some_and(|g| g.properties > 0) { s.foot } else { 0x7FFF }, 0x7FFF);
            if let Some(s) = s {
                let transports = self.count(APC) + self.count(T_COPTER);
                if foot != 0 && transports * 100 / foot < self.header(4) {
                    self.queue(s, APC, 8);
                    return true;
                }
            }
        }
        false
    }

    /// `AiSite_ScorePiperunnerNeed`: each base by a pipe, (armed enemies in a Piperunner's reach and range + 4)
    /// / 8 less the army's Piperunners there (an enemy Piperunner counting 4).
    fn score_piperunner_sites(&mut self) {
        let max = self.b.max_range(self.army, PIPERUNNER);
        for s in 0..self.sites.len() {
            let (x, y) = (self.sites[s].x, self.sites[s].y);
            if self.sites[s].mark == USED || self.sites[s].kind != BASE {
                continue;
            }
            let by_pipe = [(0, -1), (1, 0), (0, 1), (-1, 0)]
                .iter()
                .any(|&(dx, dy)| self.b.inside(x + dx, y + dy) && matches!(self.b.class[self.b.idx(x + dx, y + dy)], C_PIPE | C_SEAM));
            // (and tangoAW2's rule for a base's Piperunners: a network of at least six cells,
            // crate::cpu_tactics::MIN_PIPE_NETWORK)
            if !by_pipe || self.pipe_network(x, y) < crate::cpu_tactics::MIN_PIPE_NETWORK {
                continue;
            }
            let reach = self.flood(self.army, PIPERUNNER, x, y, FAR, false);
            // (the reach, and the cells within the Piperunner's range of it)
            let mut covered = vec![false; reach.len()];
            for j in (0..reach.len()).filter(|&j| reach[j] >= 0) {
                let (jx, jy) = (j as i32 % self.b.w, j as i32 / self.b.w);
                for cy in (jy - max).max(0)..=(jy + max).min(self.b.h - 1) {
                    for cx in (jx - max).max(0)..=(jx + max).min(self.b.w - 1) {
                        if (cx - jx).abs() + (cy - jy).abs() <= max {
                            covered[self.b.idx(cx, cy)] = true;
                        }
                    }
                }
            }
            let (mut own, mut foes) = (0, 0);
            for u in self.b.units.iter().filter(|u| !u.carried()) {
                let i = self.b.idx(u.x, u.y);
                if !covered[i] {
                    continue;
                }
                if u.army == self.army {
                    if reach[i] >= 0 && u.t == PIPERUNNER {
                        own += 1;
                    }
                } else if !self.b.same_team(u.army, self.army) && attack(u.t) != Attack::None {
                    foes += if u.t == PIPERUNNER { 4 } else { 1 };
                }
            }
            self.sites[s].pipe = ((foes + 4) >> 3) - own;
        }
    }

    /// The cells of pipe and intact seam in the networks touching (x, y).
    fn pipe_network(&self, x: i32, y: i32) -> usize {
        let pipe = |x: i32, y: i32| self.b.inside(x, y) && matches!(self.b.class[self.b.idx(x, y)], C_PIPE | C_SEAM);
        let mut seen = std::collections::HashSet::new();
        let mut stack: Vec<(i32, i32)> = [(0, -1), (1, 0), (0, 1), (-1, 0)].iter().map(|&(dx, dy)| (x + dx, y + dy)).filter(|&(a, b)| pipe(a, b)).collect();
        while let Some((a, b)) = stack.pop() {
            if !seen.insert((a, b)) {
                continue;
            }
            for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
                if pipe(a + dx, b + dy) {
                    stack.push((a + dx, b + dy));
                }
            }
        }
        seen.len()
    }

    fn piperunner_site(&self) -> Option<usize> {
        self.pick_min(BASE, None, |s| -s.pipe, 0)
    }

    fn wants_piperunner(&self, t: u8) -> bool {
        self.flag(1) && self.piperunner_site().is_some() && self.count(t) > self.count(PIPERUNNER)
    }

    /// `Ai_WantsBlackBomb(t)`: one can be paid for, the profile builds them, there is none, a safe airport, and
    /// the army has a `t`.
    fn black_bomb_site(&self, t: u8) -> Option<usize> {
        if !self.afford(BLACK_BOMB) || !self.flag(2) || self.count(BLACK_BOMB) != 0 || self.count(t) == 0 {
            return None;
        }
        let safe = |s: &Site| {
            let i = self.b.idx(s.x, s.y);
            self.threat.0[i] as i32 + self.threat.1[i] as i32 <= 50
        };
        self.pick_min(AIRPORT, None, |s| if safe(s) { -s.enemies } else { 0 }, 0)
            .or_else(|| self.pick_min(AIRPORT, None, |s| if safe(s) { s.enemy_distance } else { 0x7FFF }, 0x7FFF))
    }

    /// `AiBuild_ShouldSaveFunds`.
    fn should_save(&self, cost: i64) -> bool {
        if self.saving != 0 {
            return false;
        }
        let net = self.income - self.reserve;
        if cost <= net || cost > self.income * 2 - self.reserve {
            return false;
        }
        cost + self.price(INFANTRY) * 2 < self.funds + net
    }

    fn has_enough_indirects(&self, artillery: bool) -> bool {
        let (mut direct, mut indirect) = (0, 0);
        for u in self.own_units() {
            if stats(u.t).group & (TIRES | TREAD) == 0 {
                continue;
            }
            match attack(u.t) {
                Attack::Direct => direct += 1,
                Attack::Indirect => indirect += 1,
                _ => {}
            }
        }
        let range_co = self.b.abilities
            && crate::co_roster::stat(self.b.co[self.army as usize], self.b.mode[self.army as usize], ARTILLERY, crate::co_roster::RANGE)
                .unwrap_or(0)
                > 0;
        if artillery {
            if range_co {
                direct += 1;
            }
            return direct <= indirect * 3;
        }
        if range_co {
            !(indirect == 0 || direct > indirect)
        } else {
            direct <= indirect * 2
        }
    }

    /// Step 9: `AiTurn_PickUnitToBuild(1)` after weighing the whole battle. One build, or false.
    fn step_main(&mut self) -> bool {
        if self.first(ANY).is_none() {
            return false;
        }
        self.weigh(None);
        let info = self.pick_for_build(BASE).map_or(0, |s| self.rate_landmass(self.sites[s].x, self.sites[s].y));
        let (flag, count) = (info & 0x100 != 0, info & 0xFF);
        loop {
            let mut best = 0u8;
            let mut best_score = 0u64;
            for t in types() {
                let score = self.scores[t as usize];
                if best_score >= score {
                    continue;
                }
                if flag {
                    if t <= MECH && count - 1 >= 5 {
                        continue;
                    }
                } else if count != 0 && stats(t).group & GROUND != 0 {
                    if attack(t) != Attack::Direct || t == INFANTRY || t == MECH || t == ANTI_AIR {
                        if t == ARTILLERY || (t <= MECH && count - 1 >= 5) {
                            continue;
                        }
                        if best_score <= score >> 1 {
                            best_score = score >> 1;
                            best = t;
                        }
                    }
                    continue;
                }
                if t == ARTILLERY {
                    if self.has_enough_indirects(true) {
                        continue;
                    }
                } else if attack(t) == Attack::Indirect && stats(t).group & GROUND != 0 && self.has_enough_indirects(false) {
                    continue;
                }
                best = t;
                best_score = score;
            }
            if best == 0 {
                return false;
            }
            let kind = supply(best);
            let site = loop {
                let Some(s) = self.pick_for_build(kind) else { break None };
                if kind == BASE {
                    break Some(s);
                }
                if self.site_danger(self.sites[s].x, self.sites[s].y, best) >= 90 {
                    self.sites[s].mark = REJECTED;
                    continue;
                }
                self.clear_rejected();
                break Some(s);
            };
            let reject = |me: &mut Self, t: u8| {
                me.scores[t as usize] = 0;
                me.clear_rejected();
            };
            let Some(site) = site else {
                reject(self, best);
                continue;
            };
            let cost = self.price(best);
            if cost > self.funds {
                if self.should_save(cost) {
                    self.saving = cost - (self.income - self.reserve);
                    if logging() {
                        self.notes.push(format!("saving {} for a {}", self.saving, crate::bh_smart::NAMES[best as usize % 28]));
                    }
                }
                reject(self, best);
                continue;
            }
            if let Some(s) = self.black_bomb_site(best) {
                self.queue(s, BLACK_BOMB, 9);
                return true;
            }
            if self.saving != 0 {
                if self.afford(PIPERUNNER) && self.wants_piperunner(best) {
                    if let Some(s) = self.piperunner_site() {
                        self.queue(s, PIPERUNNER, 9);
                        return true;
                    }
                }
            } else if self.wants_piperunner(best) {
                let pipe = self.price(PIPERUNNER);
                if pipe > self.funds {
                    if self.should_save(pipe) {
                        self.saving = pipe - (self.income - self.reserve);
                        continue;
                    }
                } else if let Some(s) = self.piperunner_site() {
                    self.queue(s, PIPERUNNER, 9);
                    return true;
                }
            }
            if self.saving != 0 && self.skips != 0 {
                self.skips -= 1;
                if self.count(best) != 0 && cost > self.funds - self.saving {
                    reject(self, best);
                    continue;
                }
            } else if cost > self.funds - self.saving {
                reject(self, best);
                continue;
            }
            self.queue(site, best, 9);
            return true;
        }
    }

    /// The turn's builds (`AiTurn_RunEndActions`).
    pub fn run(&mut self) {
        let t0 = std::time::Instant::now();
        self.start();
        if logging() {
            self.notes.push(format!("start took {} us", t0.elapsed().as_micros()));
        }
        let day1 = self.b.day <= 1;
        let mut step = 1;
        let mut guard = 0;
        while step <= 9 && guard < 400 {
            guard += 1;
            if self.own >= 50 || self.builds.len() as u32 >= BUILDS_MAX {
                break;
            }
            let none = self.own == 0;
            let t0 = std::time::Instant::now();
            let again = match step {
                1 => self.step_anti_air(),
                2 if day1 && none => false,
                2 => self.step_site(),
                3 | 4 | 5 if day1 || none => false,
                3 => self.step_fighter(),
                4 => self.step_cruiser(true),
                5 => self.step_cruiser(false),
                6 => self.step_foot(),
                7 => {
                    self.foot_distances();
                    false
                }
                8 => self.step_transport(),
                _ => self.step_main(),
            };
            if logging() {
                let us = t0.elapsed().as_micros();
                if us > 500 {
                    self.notes.push(format!("step {step} took {us} us"));
                }
            }
            if !again {
                if step == 8 {
                    self.score_piperunner_sites();
                }
                if step != 7 {
                    self.clear_marks();
                }
                step += 1;
            }
        }
    }
}

/// The turn's build list for `army`, worked out now.
pub(crate) fn plan(core: &Core, army: u32) -> (Vec<Build>, Vec<String>) {
    match Plan::new(core, army) {
        Some(mut p) => {
            p.run();
            (p.builds, p.notes)
        }
        None => (Vec::new(), Vec::new()),
    }
}

// --- The traps ------------------------------------------------------------------------------

/// Dual Strike's production is playing this pass of state 5 (its list is for the army moving now).
pub(crate) fn active(core: &Core) -> bool {
    core.raw_read_8(BUILDS, -1) != 0 && core.raw_read_8(BUILDS + 2, -1) as u32 == current_army(core) && core.raw_read_16(AI_STATE, -1) == 5
}

fn entry(core: &Core, k: u32) -> Build {
    let at = BUILDS + 4 + 4 * k;
    Build {
        t: core.raw_read_8(at, -1),
        x: core.raw_read_8(at + 1, -1) as i32,
        y: core.raw_read_8(at + 2, -1) as i32,
        role: core.raw_read_8(at + 3, -1),
    }
}

/// State 5 starts: the list, and the loop's count (r0) set to its length.
fn start(core: &mut Core) {
    let army = current_army(core);
    core.raw_write_8(BUILDS, -1, 0);
    if !in_scope(core, army, OFF_BUILD) {
        return;
    }
    let started = std::time::Instant::now();
    let (builds, notes) = plan(core, army);
    let n = builds.len().min(BUILDS_MAX as usize);
    for (k, b) in builds.iter().take(n).enumerate() {
        core.raw_write_range(BUILDS + 4 + 4 * k as u32, -1, &[b.t, b.x as u8, b.y as u8, b.role]);
    }
    let day = core.raw_read_16(DAY, -1);
    core.raw_write_range(BUILDS, -1, &[n as u8, 0, army as u8, day as u8]);
    // (with no list the count is set to 0: Dual Strike decided to build nothing, or to save)
    core.gba_mut().cpu_mut().set_gpr(0, n as i32);
    if logging() {
        let (co, _) = army_co(core, army);
        log(&format!(
            "dsai build day {day} army {army} co {co} funds {} income {}: {} builds, {} us",
            funds(core, army),
            income(core, army),
            n,
            started.elapsed().as_micros()
        ));
        for l in notes {
            log(&format!("dsai   {l}"));
        }
    }
}

/// Each pass of `sub_08060718`: the next entry's type at the action struct's +6, AW2's pickers skipped.
fn pick_type(core: &mut Core) {
    if !active(core) {
        return;
    }
    let (n, next) = (core.raw_read_8(BUILDS, -1) as u32, core.raw_read_8(BUILDS + 1, -1) as u32);
    let t = if next < n { entry(core, next).t } else { 0 };
    core.raw_write_8(BUILDS + 1, -1, (next + 1).min(255) as u8);
    core.raw_write_8(ACTION + 6, -1, t);
    core.gba_mut().cpu_mut().set_thumb_pc(TYPE_DONE);
}

fn current(core: &Core) -> Option<Build> {
    let (n, next) = (core.raw_read_8(BUILDS, -1) as u32, core.raw_read_8(BUILDS + 1, -1) as u32);
    (next >= 1 && next <= n).then(|| entry(core, next - 1))
}

/// `sub_080610D0`'s role: the entry's (AW2's own roll where it has none).
fn pick_role(core: &mut Core) {
    if !active(core) {
        return;
    }
    let Some(b) = current(core) else { return };
    if b.role == NO_ROLE && b.t <= 24 {
        return;
    }
    let role = if b.role == NO_ROLE { 4 } else { b.role };
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, role as i32);
    cpu.set_thumb_pc(ROLE_DONE);
}

/// `sub_080610D0`'s factory: the entry's.
fn pick_site(core: &mut Core) {
    if !active(core) {
        return;
    }
    let Some(b) = current(core) else { return };
    let sp = core.gba().cpu().gpr(13) as u32;
    core.raw_write_16(sp, -1, b.x as u16);
    core.raw_write_16(sp + 2, -1, b.y as u16);
    core.gba_mut().cpu_mut().set_thumb_pc(SITE_DONE);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(START, Box::new(start)), (TYPE, Box::new(pick_type)), (ROLE, Box::new(pick_role)), (SITE, Box::new(pick_site))]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roles() {
        assert_eq!((0..7).map(role_of).collect::<Vec<_>>(), vec![4, 4, 1, 3, 4, 7, 7]);
    }

    #[test]
    fn groups() {
        for (k, &t) in GROUPS.iter().enumerate() {
            assert_eq!(target_group(t), Some(k));
        }
        assert_eq!(target_group(OOZIUM), None);
        assert_eq!(target_group(CARRIER), Some(7));
    }
}
