//! The computer goes for Black Hole's inventions when a human owns them.
//!
//! AW2's CPU knows nothing of an invention: its attack check looks at units
//! (and pipe seams), its role moves at HQs, properties and units. Black Hole's
//! inventions (Black Cannons, minicannons, Lasers, the Deathray, Black Crystals
//! and Obelisks, the Black Factory) belong to the army in Black Hole's colour,
//! and in AW2's own campaign and in Dual Strike's that army is the computer,
//! so nothing needed to attack them. Here a *human* owns them, in two places:
//!
//! - the **BH Campaign** (the campaign source is tangoAW2's, the player is
//!   Black Hole), and
//! - **Versus** with the Dual Strike pack, when a human army is in Black
//!   Hole's colour.
//!
//! Everywhere else this module does nothing ([`owner`] is `None`): AW2's
//! campaign, the DS Campaign, Survival, the War Room, Versus without the pack
//! and Versus where Black Hole is a computer play exactly as before.
//!
//! What the computer does, all from emulated RAM (no host randomness, nothing
//! that differs between netplay peers or a replay):
//!
//! - **Which inventions are targets** ([`targets`]): the entries of the game's
//!   invention list with hit points left that the game lets a unit attack
//!   (`sub_0803DFE0`: kinds 1, 3, 4, 5, and the factory's 7 where the factory
//!   can be destroyed, [`crate::factory_hp`]), told apart as the Black Cannon
//!   (3), the Obelisk (a Black Cannon on its tile), the minicannon (4), the
//!   Crystal (a minicannon on its tile), the Laser (1) and the Deathray (5).
//! - **What each is worth** ([`worth`]): the funds the computer would be
//!   spared by losing it, more for those that hurt it: a cannon, Laser or
//!   Deathray with computer units in its firing zone ([`zone`], as the game
//!   builds it), an Obelisk or Crystal with Black Hole's hurt units in its
//!   reach, a factory (it spawns); more again when it is low on hit points.
//! - **Strikes** ([`plan`], at the start of a computer army's turn): a unit
//!   that has a target's square in its range from where it stands and a weapon
//!   that harms a structure hits it through the game's own structure attack
//!   (`sub_08042634`, as for a pipe seam) when the hit is worth at least what
//!   its best unit target in range is worth (and always when it has none);
//!   up to [`SLOTS`] a turn, never more hits than the target has hit points
//!   left for ([`damage`]).
//! - **Goals** ([`role_move`], where the game moves a unit by its role): a
//!   unit whose own role advances (roles 1 to 6), with no capture under way
//!   and a weapon that harms a structure, takes AW2's own "move towards a
//!   place" (the role 1 code, whose destination is replaced: [`goal_hook`]) to
//!   the best square to attack a target from (inside its weapon's range of the
//!   target's square: artillery and rockets stop in range, tanks and infantry
//!   beside it), the unit's path being computed from AW2's own movement costs
//!   (a Dijkstra, [`reach`]) with enemy units in the way and walls (the
//!   inventions' footprints) out of it. Squares in the firing zone of another
//!   cannon cost the target some of its worth ([`DANGER`]), so units come in
//!   from the side and do not stand in a cannon's line for nothing. At most
//!   half of the army's advancing units are sent a turn ([`diverted`]).
//!
//! Rollback and netplay: nothing here keeps state but the strike queue and
//! three bytes in [`RAM`], all in emulated memory.

use mgba::core::Core;

use crate::unit_actions::{army_of, unit_at};

const INVENTIONS: u32 = 0x0202_8360;
const INVENTION_COUNT: u32 = 16;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const MAP: u32 = 0x0201_E450;
const CURRENT_ARMY: u32 = 0x0300_33EC;
/// The computer's unit in hand (`gUnknown_030040D8`): its record.
const CURRENT_UNIT: u32 = 0x0300_40D8;

/// The campaign source index of the BH Campaign ([`crate::campaign_model::SOURCES`]).
const BH_SOURCE: usize = 1;
const BLACK_HOLE: u8 = 5;

const MOVED: u8 = 0x01;
const CARRIED: u8 = 0x08;

/// RAM tangoAW2 keeps for this: the second half of the strike queue (the
/// first is [`crate::cpu_tactics`]'s `PENDING`), the goal in force for the
/// role move in hand, and how many units this turn were sent.
pub const RAM: u32 = 0x0203_FE58;
/// Strikes queued by a computer army's turn: 4 here, 4 in `PENDING`.
pub const EXTRA: u32 = RAM;
pub const EXTRA_SLOTS: u32 = 4;
/// Goal in force: flag, x, y (bytes).
const GOAL: u32 = RAM + 0x10;
/// Units sent to an invention this turn, and the army it is counted for.
const SENT: u32 = RAM + 0x14;
const SENT_ARMY: u32 = RAM + 0x15;
/// The unit the goal is for (a word).
const GOAL_UNIT: u32 = RAM + 0x18;
/// A development hook (`tools/aw2test`, in emulated memory): [`OFF`] here and the
/// computer ignores inventions, as before this module.
pub const DEV_OFF: u32 = RAM + 0x16;
pub const OFF: u8 = 0xA5;
/// The most strikes a computer army makes in a turn.
pub const SLOTS: u32 = 8;
/// A queued strike: this flag, then unit id (8 bits), x (8), y (8).
pub const QUEUED: u32 = 0x4000_0000;

// --- Where it is on ---------------------------------------------------------------

fn players(core: &Core) -> u32 {
    crate::five::players(core)
}

fn colour(core: &Core, army: u32) -> u8 {
    core.raw_read_8(players(core) + 0x3C * army + 0x1A, -1)
}

fn controller(core: &Core, army: u32) -> u8 {
    core.raw_read_8(players(core) + 0x3C * army + 0x1B, -1)
}

pub fn team(core: &Core, army: u32) -> u8 {
    core.raw_read_8(players(core) + 0x3C * army + 0x2A, -1)
}

/// The army the computer attacks the inventions of: the human in Black Hole's
/// colour, in the BH Campaign and in Versus with the pack; `None` anywhere else.
pub fn owner(core: &Core) -> Option<u32> {
    if !crate::ds_weather::is_on(core) || core.raw_read_8(DEV_OFF, -1) == OFF {
        return None;
    }
    let ok = if crate::ds_campaign::active(core) {
        crate::ds_campaign::source(core) == BH_SOURCE
    } else {
        crate::pvp::in_versus(core)
    };
    if !ok {
        return None;
    }
    (1..=5u32).find(|&a| colour(core, a) == BLACK_HOLE && controller(core, a) == 1)
}

/// The BH Campaign is being played (the factory can be destroyed there too;
/// not with [`OFF`], the development byte, which is the campaign as it was).
pub fn in_bh_campaign(core: &Core) -> bool {
    crate::ds_campaign::active(core) && crate::ds_campaign::source(core) == BH_SOURCE && core.raw_read_8(DEV_OFF, -1) != OFF
}

/// The army moving now is on the team of the human who owns the inventions.
pub fn moving_army_owns(core: &Core) -> bool {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    (1..=5).contains(&army) && owner(core).is_some_and(|o| team(core, army) == team(core, o))
}

fn is_cpu(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army) && controller(core, army) == 2
}

fn map_size(core: &Core) -> (i32, i32) {
    (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32)
}

fn pos(core: &Core, u: u32) -> (i32, i32) {
    (core.raw_read_8(u + 2, -1) as i32, core.raw_read_8(u + 3, -1) as i32)
}

fn hp(core: &Core, u: u32) -> u32 {
    (core.raw_read_16(u + 4, -1) & 0x7F) as u32
}

fn bars(hp: u32) -> u32 {
    if hp == 0 { 0 } else { (hp - 1) / 10 + 1 }
}

fn price(core: &Core, t: u8) -> u32 {
    core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as u32 * 10
}

fn dist(a: (i32, i32), b: (i32, i32)) -> i32 {
    (a.0 - b.0).abs() + (a.1 - b.1).abs()
}

// --- The inventions -------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Cannon,
    Deathray,
    Laser,
    Mini,
    Obelisk,
    Crystal,
    Factory,
}

impl Kind {
    pub fn name(self) -> &'static str {
        match self {
            Kind::Cannon => "cannon",
            Kind::Deathray => "deathray",
            Kind::Laser => "laser",
            Kind::Mini => "minicannon",
            Kind::Obelisk => "obelisk",
            Kind::Crystal => "crystal",
            Kind::Factory => "factory",
        }
    }
    /// Fires on Black Hole's turn.
    fn fires(self) -> bool {
        matches!(self, Kind::Cannon | Kind::Deathray | Kind::Laser | Kind::Mini)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Target {
    pub entry: u32,
    pub kind: Kind,
    /// The entry's corner.
    pub at: (i32, i32),
    /// The square units aim at.
    pub aim: (i32, i32),
    pub hp: u32,
    pub max_hp: u32,
    /// The firing direction (the entry's +3 >> 6).
    pub facing: u32,
}

fn max_hp(kind: Kind) -> u32 {
    if kind == Kind::Factory { crate::factory_hp::HP as u32 } else { 99 }
}

/// Every invention of the list a unit may attack and that still stands.
pub fn targets(core: &Core) -> Vec<Target> {
    let mut out = Vec::new();
    for i in 0..INVENTION_COUNT {
        let e = INVENTIONS + 8 * i;
        let word = core.raw_read_16(e + 2, -1);
        let k = (word >> 6) & 15;
        if k == 0 {
            break;
        }
        let hp = core.raw_read_8(e + 4, -1) as u32;
        if hp == 0 || crate::custom_campaign::is_jammed(core, e) {
            continue;
        }
        let (x, y) = (core.raw_read_8(e, -1) as i32, core.raw_read_8(e + 1, -1) as i32);
        let tile = |dx: i32, dy: i32| crate::obelisk::tile_at(core, (x + dx) as u32, (y + dy) as u32);
        let facing = (core.raw_read_8(e + 3, -1) >> 6) as u32;
        let (kind, aim) = match k {
            1 => (Kind::Laser, (x, y)),
            3 if tile(1, 1) == crate::obelisk::OBELISK_TILE => (Kind::Obelisk, (x + 1, y + 2)),
            3 => (Kind::Cannon, (x + 1, y + 2)),
            4 if tile(0, 0) == crate::obelisk::CRYSTAL_TILE => (Kind::Crystal, (x, y)),
            4 if tile(0, 0) == crate::grand_bolt::PART_TILE => continue,
            4 => (Kind::Mini, (x, y)),
            5 => (Kind::Deathray, (x + 1, y + 2)),
            7 if crate::factory_hp::in_scope(core) => {
                let height = (core.raw_read_8(e + 2, -1) as i32 >> 3) & 7;
                (Kind::Factory, (x + 1, y + height - 1))
            }
            _ => continue,
        };
        out.push(Target { entry: e, kind, at: (x, y), aim, hp, max_hp: max_hp(kind), facing });
    }
    out
}

/// The cells a cone of `length` rows, widening by one cell each side a row, covers
/// from `apex` in `facing` (0 down, 1 up, 2 left, 3 right): AW2's `sub_0801FAC4`.
fn cone(apex: (i32, i32), facing: u32, length: i32, w: i32, h: i32, out: &mut Vec<(i32, i32)>) {
    for k in 0..length {
        for s in -k..=k {
            let c = match facing {
                0 => (apex.0 + s, apex.1 + k),
                1 => (apex.0 + s, apex.1 - k),
                2 => (apex.0 - k, apex.1 + s),
                _ => (apex.0 + k, apex.1 + s),
            };
            if c.0 >= 0 && c.1 >= 0 && c.0 < w && c.1 < h {
                out.push(c);
            }
        }
    }
}

/// The cells a firing invention hits on Black Hole's turn (the game's own
/// geometry: a Black Cannon a cone of ten rows from the middle of its facing
/// edge, a minicannon one of four from the cell in front of it, a Laser its row
/// and column, the Deathray three columns below it). Empty for the others.
pub fn zone(core: &Core, t: &Target) -> Vec<(i32, i32)> {
    let (w, h) = map_size(core);
    let mut out = Vec::new();
    match t.kind {
        Kind::Cannon => {
            // (x + dx, y + dy) of the apex by facing: `0x0849F688` (down, up).
            let apex = if t.facing == 1 { (t.at.0 + 1, t.at.1 - 1) } else { (t.at.0 + 1, t.at.1 + 2) };
            cone(apex, if t.facing == 1 { 1 } else { 0 }, 10, w, h, &mut out);
        }
        Kind::Mini => {
            // `0x0849F698`: the cell in front of it.
            let apex = match t.facing {
                0 => (t.at.0, t.at.1 + 1),
                1 => (t.at.0, t.at.1 - 1),
                2 => (t.at.0 - 1, t.at.1),
                _ => (t.at.0 + 1, t.at.1),
            };
            cone(apex, t.facing, 4, w, h, &mut out);
        }
        Kind::Laser => {
            out.extend((0..w).filter(|&x| x != t.at.0).map(|x| (x, t.at.1)));
            out.extend((0..h).filter(|&y| y != t.at.1).map(|y| (t.at.0, y)));
        }
        Kind::Deathray => {
            for y in t.at.1 + 3..h {
                for x in t.at.0..t.at.0 + 3 {
                    if x < w {
                        out.push((x, y));
                    }
                }
            }
        }
        _ => {}
    }
    out
}

/// A unit of an army that is not Black Hole's side, on the map.
fn units_of_team(core: &Core, owner: u32, hostile: bool) -> Vec<u32> {
    let base = core.raw_read_32(UNITS_POINTER, -1);
    let mine = team(core, owner);
    (1..255u32)
        .map(|i| (base + UNIT * i, i))
        .filter(|&(u, i)| {
            core.raw_read_8(u, -1) != 0
                && core.raw_read_8(u + 1, -1) & CARRIED == 0
                && ((team(core, crate::five::army_of_index(core, i)) != mine) == hostile)
        })
        .map(|(u, _)| u)
        .collect()
}

/// Funds the computer is spared by losing `t` (before its hit points):
/// the invention's own worth, what its fire costs the computer now and
/// what it gives Black Hole now.
pub fn worth(core: &Core, t: &Target, owner: u32) -> u32 {
    let base = match t.kind {
        Kind::Cannon => 16000,
        Kind::Deathray => 24000,
        Kind::Laser => 14000,
        Kind::Mini => 6000,
        Kind::Obelisk => 11000,
        Kind::Crystal => 5000,
        Kind::Factory => 13000,
    };
    let mut extra = 0;
    if t.kind.fires() {
        let cells = zone(core, t);
        for v in units_of_team(core, owner, true) {
            if cells.contains(&pos(core, v)) {
                // (five of ten bars a hit)
                extra += price(core, core.raw_read_8(v, -1)) * bars(hp(core, v)) / 10 / 2;
            }
        }
    }
    let reach = match t.kind {
        Kind::Crystal => Some((t.at.0, t.at.1, t.at.0, t.at.1, 2)),
        Kind::Obelisk => Some((t.at.0, t.at.1, t.at.0 + 2, t.at.1 + 2, 4)),
        _ => None,
    };
    if let Some((x0, y0, x1, y1, range)) = reach {
        for v in units_of_team(core, owner, false) {
            let (ux, uy) = pos(core, v);
            let dx = if ux < x0 { x0 - ux } else if ux > x1 { ux - x1 } else { 0 };
            let dy = if uy < y0 { y0 - uy } else if uy > y1 { uy - y1 } else { 0 };
            if dx + dy <= range && hp(core, v) < 100 {
                // (two bars a turn to units that are hurt)
                extra += price(core, core.raw_read_8(v, -1)) * (100 - hp(core, v)).min(20) / 100;
            }
        }
    }
    // Low on hit points: the less it has, the sooner it is gone.
    let low = base * (t.max_hp.saturating_sub(t.hp)) / t.max_hp / 2;
    base + extra + low
}

// --- What a unit can do to an invention -----------------------------------------------

fn range(core: &Core, t: u8) -> (i32, i32) {
    let table = crate::roster::table(core);
    (
        core.raw_read_8(table + 0x5C * t as u32 + 0x0E, -1).max(1) as i32,
        core.raw_read_8(table + 0x5C * t as u32 + 0x0F, -1).max(1) as i32,
    )
}

/// The damage chart's value (percent) of `u` against a structure: the
/// game's own column 3 (`sub_080251D8`); the secondary weapon without ammo.
fn structure_chart(core: &Core, u: u32) -> u32 {
    let t = core.raw_read_8(u, -1);
    let ammo = (core.raw_read_16(u + 4, -1) >> 7) & 0xF;
    let secondary = crate::roster::chart(t, 3, 1) as u32;
    let primary = if ammo > 0 { crate::roster::chart(t, 3, 0) as u32 } else { 0 };
    secondary.max(primary)
}

/// The hit points a hit by `u` takes off an invention: its chart value
/// against a structure (an Artillery's 45, a Tank's 15) by its hit points.
pub fn damage(core: &Core, u: u32) -> u32 {
    structure_chart(core, u) * hp(core, u) / 100
}

/// The squares a unit of type `t` attacks `aim` from.
fn attack_squares(core: &Core, t: u8, aim: (i32, i32)) -> Vec<(i32, i32)> {
    let (rmin, rmax) = range(core, t);
    let (w, h) = map_size(core);
    let mut out = Vec::new();
    for y in (aim.1 - rmax).max(0)..=(aim.1 + rmax).min(h - 1) {
        for x in (aim.0 - rmax).max(0)..=(aim.0 + rmax).min(w - 1) {
            let d = dist((x, y), aim);
            if d >= rmin && d <= rmax {
                out.push((x, y));
            }
        }
    }
    out
}

/// What the best unit target `u` has in its range from where it stands is
/// worth to it, in funds (0 with none).
fn unit_alternative(core: &Core, u: u32, hostile: &[u32]) -> u32 {
    let t = core.raw_read_8(u, -1);
    let (rmin, rmax) = range(core, t);
    let p = pos(core, u);
    let ammo = (core.raw_read_16(u + 4, -1) >> 7) & 0xF;
    let mut best = 0;
    for &v in hostile {
        let d = dist(p, pos(core, v));
        if d < rmin || d > rmax {
            continue;
        }
        let vt = core.raw_read_8(v, -1);
        let c = (crate::roster::chart(t, vt, 1) as u32).max(if ammo > 0 { crate::roster::chart(t, vt, 0) as u32 } else { 0 });
        if c == 0 {
            continue;
        }
        let dealt = (c * hp(core, u) / 100).min(hp(core, v));
        best = best.max(price(core, vt) * dealt / 100);
    }
    best
}

/// What a hit of `dmg` hit points is worth against an invention worth `w` with `hp` of `max_hp` left: its
/// share of the worth, and when it destroys the invention a third more of it.
fn gain_of(w: u32, hp: u32, max_hp: u32, dmg: u32) -> u32 {
    let mut gain = w * dmg.min(hp) / max_hp;
    if dmg >= hp {
        gain += w * 3 / 10;
    }
    gain
}

fn target_gain(core: &Core, t: &Target, owner: u32, dmg: u32) -> u32 {
    gain_of(worth(core, t, owner), t.hp, t.max_hp, dmg)
}

// --- Strikes ----------------------------------------------------------------------------

/// A strike to queue: (unit record, the square aimed at).
pub fn plan(core: &Core, army: u32) -> Vec<(u32, (i32, i32))> {
    let Some(owner) = owner(core) else { return Vec::new() };
    if !is_cpu(core, army) || team(core, army) == team(core, owner) {
        return Vec::new();
    }
    let ts = targets(core);
    if ts.is_empty() {
        return Vec::new();
    }
    let hostile = units_of_team(core, army, true);
    let base = core.raw_read_32(UNITS_POINTER, -1);
    let mut left: Vec<i32> = ts.iter().map(|t| t.hp as i32).collect();
    // Units that can hit something now, the strongest hitter first.
    let mut strikers: Vec<(u32, u32)> = (1..255u32)
        .filter(|&i| crate::five::army_of_index(core, i) == army)
        .map(|i| base + UNIT * i)
        .filter(|&u| core.raw_read_8(u, -1) != 0 && core.raw_read_8(u + 1, -1) & (MOVED | CARRIED) == 0)
        .map(|u| (damage(core, u), u))
        .filter(|&(d, _)| d > 0)
        .collect();
    strikers.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    let mut out = Vec::new();
    for (dmg, u) in strikers {
        if out.len() as u32 >= SLOTS {
            break;
        }
        let t = core.raw_read_8(u, -1);
        let (rmin, rmax) = range(core, t);
        let p = pos(core, u);
        let mut best: Option<(u32, usize)> = None;
        for (i, tg) in ts.iter().enumerate() {
            let d = dist(p, tg.aim);
            if d < rmin || d > rmax || left[i] <= 0 {
                continue;
            }
            let g = target_gain(core, tg, owner, dmg);
            if best.map_or(true, |(bg, _)| g > bg) {
                best = Some((g, i));
            }
        }
        let Some((gain, i)) = best else { continue };
        let alt = unit_alternative(core, u, &hostile);
        if alt > 0 && gain < alt {
            continue;
        }
        left[i] -= dmg as i32;
        out.push((u, ts[i].aim));
    }
    out
}

/// A queued strike's value for the pending list.
pub fn encode(core: &Core, u: u32, aim: (i32, i32)) -> u32 {
    let id = (u - core.raw_read_32(UNITS_POINTER, -1)) / UNIT;
    QUEUED | ((aim.1 as u32) << 16) | ((aim.0 as u32) << 8) | id
}

/// The game's own structure attack by a queued strike, returning to `ret`.
/// `false` when the unit or the target is gone.
pub fn strike(core: &mut Core, value: u32, ret: u32) -> bool {
    let (id, aim) = ((value & 0xFF), (((value >> 8) & 0xFF) as i32, ((value >> 16) & 0xFF) as i32));
    let u = core.raw_read_32(UNITS_POINTER, -1) + UNIT * id;
    if core.raw_read_8(u, -1) == 0 || !targets(core).iter().any(|t| t.aim == aim) {
        return false;
    }
    let (x, y) = pos(core, u);
    let hp_before = targets(core).iter().find(|t| t.aim == aim).map_or(0, |t| t.hp);
    if crate::bh_factory::logging() {
        crate::bh_factory::log(&format!(
            "inv strike: unit {id} type {} hp {} at ({x},{y}) aims at {aim:?}, target hp {hp_before}, predicted damage {} (chart {})",
            core.raw_read_8(u, -1),
            hp(core, u),
            damage(core, u),
            structure_chart(core, u)
        ));
    }
    const STRUCTURE_ATTACK: u32 = 0x0804_2634;
    const SELECTED: u32 = 0x0300_40D8;
    const SELECTED_ID: u32 = 0x0300_3F38;
    const DEST: u32 = 0x0300_3100;
    const ORIGIN: u32 = 0x0300_3F24;
    core.raw_write_8(SELECTED_ID, -1, id as u8);
    core.raw_write_32(SELECTED, -1, u);
    for at in [DEST, ORIGIN] {
        core.raw_write_16(at, -1, x as u16);
        core.raw_write_16(at + 2, -1, y as u16);
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, aim.0);
    cpu.set_gpr(1, aim.1);
    cpu.set_gpr(14, ret as i32);
    cpu.set_thumb_pc(STRUCTURE_ATTACK);
    true
}

// --- Goals ------------------------------------------------------------------------------------

/// The AI's role move for the unit in hand (`AiRunRoleMove`, `0x0805F4CC`):
/// a unit given a goal runs the role 1 code (towards a place) with the place
/// replaced ([`goal_hook`]). `true` when it did (the caller returns).
pub fn role_move(core: &mut Core) -> bool {
    let Some(owner) = owner(core) else { return false };
    // (the goal of an earlier unit is never kept)
    core.raw_write_8(GOAL, -1, 0);
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !is_cpu(core, army) || team(core, army) == team(core, owner) {
        return false;
    }
    let u = core.raw_read_32(CURRENT_UNIT, -1);
    // (a campaign mission's driven march goes to a place of its own)
    if u == 0 || crate::custom_campaign::driven_goal(core, u).is_some() {
        return false;
    }
    let Some(goal) = goal_for(core, army, owner, u) else {
        if crate::bh_factory::logging() {
            crate::bh_factory::log(&format!(
                "inv role: unit {} type {} role {} hp word {:04x} dmg {} plays as AW2 does",
                (u - core.raw_read_32(UNITS_POINTER, -1)) / UNIT,
                core.raw_read_8(u, -1),
                role(core, u),
                core.raw_read_16(u + 4, -1),
                damage(core, u)
            ));
        }
        return false;
    };
    core.raw_write_8(GOAL, -1, 1);
    core.raw_write_8(GOAL + 1, -1, goal.0 as u8);
    core.raw_write_8(GOAL + 2, -1, goal.1 as u8);
    core.raw_write_32(GOAL_UNIT, -1, u);
    let f = core.raw_read_32(ROLE_MOVES + 4, -1);
    core.gba_mut().cpu_mut().set_thumb_pc(f & !1);
    true
}

const ROLE_MOVES: u32 = 0x0857_68E0;
/// After role 1's call that finds the place to go (`sub_08058F90`): the place
/// is at the out pointer in r4 (two halfwords), r0 the answer (-1: none).
pub const GOAL_HOOK: u32 = 0x0805_ED2A;

pub fn goal_hook(core: &mut Core) {
    // (a campaign mission's driven march goes to a place of its own)
    crate::custom_campaign::goal_hook(core);
    // (only for the unit the goal was made for, where this module is on)
    if core.raw_read_8(GOAL, -1) == 0 || owner(core).is_none() || core.raw_read_32(CURRENT_UNIT, -1) != core.raw_read_32(GOAL_UNIT, -1) {
        return;
    }
    core.raw_write_8(GOAL, -1, 0);
    let (x, y) = (core.raw_read_8(GOAL + 1, -1) as u16, core.raw_read_8(GOAL + 2, -1) as u16);
    let out = core.gba().cpu().gpr(4) as u32;
    core.raw_write_16(out, -1, x);
    core.raw_write_16(out + 2, -1, y);
    core.gba_mut().cpu_mut().set_gpr(0, 0);
}

/// Units sent this turn (reset when the army changes).
fn sent(core: &mut Core, army: u32) -> u32 {
    if core.raw_read_8(SENT_ARMY, -1) as u32 != army {
        core.raw_write_8(SENT_ARMY, -1, army as u8);
        core.raw_write_8(SENT, -1, 0);
    }
    core.raw_read_8(SENT, -1) as u32
}

/// A computer army's turn begins: nobody is sent yet.
pub fn turn_begins(core: &mut Core, army: u32) {
    core.raw_write_8(SENT_ARMY, -1, army as u8);
    core.raw_write_8(SENT, -1, 0);
}

/// The most squares (movement-cost units) the search looks ahead.
const HORIZON_TURNS: i32 = 8;
/// Percent of a unit's worth lost for each firing invention covering the square it ends its turn on.
const EXPOSED: i64 = 60;

fn role(core: &Core, u: u32) -> u8 {
    core.raw_read_8(u + 0x0B, -1)
}

/// Movement points of a unit type.
fn move_points(core: &Core, t: u8) -> i32 {
    core.raw_read_8(crate::roster::table(core) + 0x5C * t as u32 + 0x0A, -1).max(1) as i32
}

/// The cost of getting from `u`'s square to every square (-1: not at all):
/// AW2's movement costs for its army, enemy units in the way.
fn reach(core: &Core, army: u32, u: u32) -> Vec<i32> {
    use std::cmp::Reverse;
    use std::collections::BinaryHeap;
    let (w, h) = map_size(core);
    let t = core.raw_read_8(u, -1);
    let mut d = vec![-1i32; (w * h).max(0) as usize];
    let start = pos(core, u);
    if start.0 < 0 || start.1 < 0 || start.0 >= w || start.1 >= h {
        return d;
    }
    let mut heap = BinaryHeap::new();
    d[(start.1 * w + start.0) as usize] = 0;
    heap.push(Reverse((0i32, start.1, start.0)));
    let mine = team(core, army);
    while let Some(Reverse((c, y, x))) = heap.pop() {
        if c > d[(y * w + x) as usize] {
            continue;
        }
        for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
            let (nx, ny) = (x + dx, y + dy);
            if nx < 0 || ny < 0 || nx >= w || ny >= h {
                continue;
            }
            let step = crate::oozium::move_cost(core, army, t, nx, ny);
            if step == 0xFF {
                continue;
            }
            if let Some(v) = unit_at(core, nx, ny) {
                if team(core, army_of(core, v)) != mine {
                    continue;
                }
            }
            let nc = c + step as i32;
            let i = (ny * w + nx) as usize;
            if d[i] < 0 || nc < d[i] {
                d[i] = nc;
                heap.push(Reverse((nc, ny, nx)));
            }
        }
    }
    d
}

/// Where the unit in hand is sent, if anywhere.
fn goal_for(core: &mut Core, army: u32, owner: u32, u: u32) -> Option<(i32, i32)> {
    // (the time is only for the log: it changes nothing)
    let started = std::time::Instant::now();
    let r = role(core, u);
    if !(1..=6).contains(&r) {
        return None;
    }
    // A capture under way is finished first.
    if core.raw_read_8(u + 5, -1) & 0xF8 != 0 {
        return None;
    }
    let t = core.raw_read_8(u, -1);
    let dmg = damage(core, u);
    if dmg == 0 {
        return None;
    }
    // What the unit is worth (price by bars of hit points).
    let value = (price(core, t) * bars(hp(core, u)) / 10) as i64;
    let ts = targets(core);
    if ts.is_empty() {
        return None;
    }
    // At most half of the army's advancing units are sent.
    let advancing = {
        let base = core.raw_read_32(UNITS_POINTER, -1);
        (1..255u32)
            .filter(|&i| crate::five::army_of_index(core, i) == army)
            .map(|i| base + UNIT * i)
            .filter(|&v| core.raw_read_8(v, -1) != 0 && (1..=6).contains(&role(core, v)) && damage(core, v) > 0)
            .count() as u32
    };
    let cap = advancing.div_ceil(2).max(1);
    let done = sent(core, army);
    let here = pos(core, u);
    let (w, _) = map_size(core);
    let cost = reach(core, army, u);
    let speed = move_points(core, t);
    // Zones of the firing inventions, for the danger of a square.
    let zones: Vec<(usize, Vec<(i32, i32)>)> =
        ts.iter().enumerate().filter(|(_, t)| t.kind.fires()).map(|(i, t)| (i, zone(core, t))).collect();
    let mut best: Option<(i64, (i32, i32), usize, i32)> = None;
    for (i, tg) in ts.iter().enumerate() {
        let gain = target_gain(core, tg, owner, dmg) as i64;
        for c in attack_squares(core, t, tg.aim) {
            let k = cost[(c.1 * w + c.0) as usize];
            if k < 0 {
                continue;
            }
            // The square is free for the unit (or its own).
            if c != here {
                if let Some(v) = unit_at(core, c.0, c.1) {
                    if v != u {
                        continue;
                    }
                }
            }
            let turns = (k + speed - 1) / speed;
            if turns > HORIZON_TURNS {
                continue;
            }
            // A square in the line of a firing invention (the target's own included) costs the unit: it is hit
            // at Black Hole's next turn (the Black Cannon and the minicannon take five of ten bars) and again after,
            // so one covering invention costs it more than half its worth, two all of it.
            let hits = zones.iter().filter(|(_, z)| z.contains(&c)).count() as i64;
            let loss = value * (hits * EXPOSED).min(100) / 100;
            let score = (gain - loss) * 10 / (10 + 6 * turns as i64);
            if score > 0 && best.map_or(true, |(bs, bc, ..)| score > bs || (score == bs && (c.1, c.0) < (bc.1, bc.0))) {
                best = Some((score, c, i, turns));
            }
        }
    }
    let Some((_, goal, i, turns)) = best else {
        if crate::bh_factory::logging() {
            crate::bh_factory::log(&format!("inv none: unit type {t} at {here:?}: no square worth the walk ({} targets)", ts.len()));
        }
        return None;
    };
    if goal != here && done >= cap {
        if crate::bh_factory::logging() {
            crate::bh_factory::log(&format!("inv capped: unit type {t} at {here:?}: {done} of {cap} sent already"));
        }
        return None;
    }
    if goal != here {
        core.raw_write_8(SENT, -1, (done + 1).min(255) as u8);
    }
    let (id, ty) = ((u - core.raw_read_32(UNITS_POINTER, -1)) / UNIT, t);
    if crate::bh_factory::logging() {
        crate::bh_factory::log(&format!(
            "inv goal: unit {id} type {ty} role {r} (hp word {:04x}) at {here:?} -> {goal:?} for the {} at {:?} (hp {}), {turns} turns | {} us",
            core.raw_read_16(u + 4, -1),
            ts[i].kind.name(),
            ts[i].aim,
            ts[i].hp,
            started.elapsed().as_micros()
        ));
    }
    Some(goal)
}

/// Black Hole's inventions belong to the army in Black Hole's colour. The army moving now is on that army's
/// team (itself, or an ally: a Versus team, the BH Campaign's allied armies).
pub fn moving_army_is_inventions_team(core: &Core) -> bool {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    (1..=5).contains(&army) && (1..=5u32).any(|a| colour(core, a) == BLACK_HOLE && team(core, a) == team(core, army))
}

/// `sub_0803DF54(x, y)`, the invention at an aimed-at square, after it found one (`ldrb r0, [r4, #4]`).
const FIND_FOUND: u32 = 0x0803_DF84;
const FIND_NONE: u32 = 0x0803_DF8E;
/// The calls that collect what a unit may attack (the attack menu, the cursor's targets, the attack itself);
/// the terrain panel's call (`0x0802B1CC`) stays, so an own structure's hit points still show.
const FIND_CALLERS: [u32; 3] = [0x0802_0C2B, 0x0804_1435, 0x0804_182F];

/// An army never targets its own or an allied army's invention: the lookup finds none for it.
fn own_not_a_target(core: &mut Core) {
    if !crate::ds_weather::is_on(core) || core.raw_read_8(DEV_OFF, -1) == OFF {
        return;
    }
    let sp = core.gba().cpu().gpr(13) as u32;
    let lr = core.raw_read_32(sp + 20, -1);
    if !FIND_CALLERS.contains(&lr) || !moving_army_is_inventions_team(core) {
        return;
    }
    core.gba_mut().cpu_mut().set_thumb_pc(FIND_NONE);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(GOAL_HOOK, Box::new(goal_hook)), (FIND_FOUND, Box::new(own_not_a_target))]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cone_widens() {
        let mut v = Vec::new();
        cone((5, 5), 0, 3, 20, 20, &mut v);
        assert_eq!(v.len(), 1 + 3 + 5);
        assert!(v.contains(&(5, 5)) && v.contains(&(3, 7)) && v.contains(&(7, 7)) && !v.contains(&(2, 7)));
        let mut up = Vec::new();
        cone((5, 5), 1, 2, 20, 20, &mut up);
        assert!(up.contains(&(4, 4)) && up.contains(&(6, 4)));
        let mut left = Vec::new();
        cone((5, 5), 2, 2, 20, 20, &mut left);
        assert!(left.contains(&(4, 4)) && left.contains(&(4, 6)));
    }

    #[test]
    fn cone_clips() {
        let mut v = Vec::new();
        cone((0, 0), 0, 3, 2, 2, &mut v);
        assert_eq!(v.len(), 3);
    }

    #[test]
    fn a_low_invention_is_worth_more_to_hit() {
        // The same invention with 20 of 99 hit points left against a whole one: a Tank's 15 destroys it...
        let whole = gain_of(16000, 99, 99, 15);
        let low = gain_of(16000 + 16000 * 79 / 99 / 2, 20, 99, 15);
        assert!(low > whole, "{low} against {whole}");
        // ...and a hit that destroys is worth more than the same share of one that does not.
        assert!(gain_of(10000, 15, 99, 15) > gain_of(10000, 16, 99, 15) + 1000);
        // Against a whole one, a threatening kind is worth more than a benign one.
        assert!(gain_of(16000, 99, 99, 45) > gain_of(5000, 99, 99, 45));
    }

    #[test]
    fn ram() {
        assert!(EXTRA + 4 * EXTRA_SLOTS <= GOAL && SENT_ARMY < 0x0203_FE80);
    }
}
