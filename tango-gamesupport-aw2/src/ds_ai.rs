//! Dual Strike's CPU in AW2's, with the Dual Strike pack (docs/AW2.md "Dual Strike's CPU").
//!
//! AW2's computer plays its turn in passes (`AiDriverStep`, `0x0806171C`: begin, the pass list, each pass's
//! unit queue, the action executor, production, end). Dual Strike's is the same design grown up (its turn
//! driver `AiTurn_Update` `0x0208C2A4`, phases, end actions and power step), and both keep a per-CO personality
//! of the same shape (7 order weights a unit type, rolled when a unit is bought). So Dual Strike's decisions are
//! made here, in Rust, from the battle in emulated RAM, and handed to AW2's driver at the points where it makes
//! the same decision:
//! - what to build, where, and the new unit's order ([`crate::ds_ai_build`]);
//! - when to use a CO Power, a Super CO Power or a Tag Power ([`crate::ds_ai_power`]; the Change at the turn's
//!   end is [`crate::tag`]'s, with Dual Strike's ranks);
//! - the per-CO profile and the army's behaviour (Strike, Assault, General, Defense), below.
//!
//! This module has what they share: when Dual Strike's CPU plays ([`in_scope`]), its RAM, the profile tables
//! read from the pack (Dual Strike's arm9, never committed), a snapshot of the battle ([`Board`]) with
//! movement floods, and the deterministic roll.
//!
//! **Netplay and rollback.** Everything is decided from emulated RAM and ROM, the same on both peers and in
//! replays. AW2's random number generator (`0x03001FD4`) is read, never advanced: where Dual Strike draws
//! (`Rng_Next`), a roll is a hash of that state with the day, the army and what the roll is for ([`roll`]).
//! What must last across frames (the turn's build list, the turn's profile roll) is in EWRAM
//! ([`crate::ram_map::DS_AI`]), never in host statics.
//!
//! **Data.** Dual Strike's profile tables are in its arm9 (the pack's `arm9_at`):
//! - `0x02161B8C`, 42 sets of 29 bytes: a mods id, then a template id per Dual Strike CO id. Versus and
//!   tangoAW2 use set 1 (mods 0), as Dual Strike does for a map whose header names no set;
//! - `gAiProfileMods` `0x02162050`, 0x40 bytes each: 12 header bytes (foot quotas, Mech %, transport ratios,
//!   site radius, build flags, day gates), then per unit type its build percentage and a roll threshold;
//! - `gAiProfileTemplates` `0x02162A90`, 0x15C bytes each: the power hook (a function pointer, named by
//!   [`Hook`]), six power bytes, then per unit type its threat limits (base, spread, twice), the supply and
//!   repair thresholds and 7 signed order weights.
//!   (docs/AW2.md once called `0x02162A90` "the plan table" and `0x0208CBA8` "the per-turn plan": they are
//!   these templates and `AiProfile_Build`.)

use mgba::core::Core;

use crate::ds_weather::is_on;

// --- When ----------------------------------------------------------------------------

const CURRENT_ARMY: u32 = 0x0300_33EC;
const PLAY_ST: u32 = 0x0300_3FC0;
const FOG: u32 = PLAY_ST + 0x0D;
const ABILITIES_ON: u32 = PLAY_ST + 0x08;
const POWERS_ON: u32 = PLAY_ST + 0x07;
pub(crate) const DAY: u32 = 0x0300_4080;
/// AW2's random number generator state: read, never advanced.
const RNG: u32 = 0x0300_1FD4;

/// The RAM (crate::ram_map::DS_AI): +0x00 the build list (+0 count, +1 next, +2 army, +3 day, then four bytes an
/// entry: type, x, y, role), +0xB0 per army (1..5) the turn's profile roll and the day it was rolled for (two bytes
/// each), +0xC0 per army its behaviour + 1 (0: General), +0xD0 the move in hand ([`crate::ds_ai_move`]: flag, x, y,
/// then the unit's record), +0xF0 the development switches.
pub(crate) const STATE: u32 = crate::ram_map::DS_AI.0;
pub(crate) const BUILDS: u32 = STATE;
pub(crate) const BUILDS_MAX: u32 = 40;
const ROLLS: u32 = STATE + 0xB0;
const BEHAVIOURS: u32 = STATE + 0xC0;
/// A development switch for A/B runs (`tools/aw2test`): bit 0 turns Dual Strike's CPU off (AW2's decides),
/// bit 1 turns only its production off, bit 2 only its powers. Emulated memory, so it replays and rolls back.
pub(crate) const SWITCHES: u32 = STATE + 0xF0;
pub(crate) const OFF: u8 = 1;
pub(crate) const OFF_BUILD: u8 = 2;
pub(crate) const OFF_POWER: u8 = 4;
/// Bit 3: only its unit moves ([`crate::ds_ai_move`]) off.
pub(crate) const OFF_MOVE: u8 = 8;

fn players(core: &Core) -> u32 {
    crate::five::players(core)
}

/// A CPU army: player +0x1B is 2 (1 is human).
pub(crate) fn is_cpu(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army) && core.raw_read_8(players(core) + 0x3C * army + 0x1B, -1) == 2
}

/// Dual Strike's CPU plays army `army`'s turn: the pack is on, the army is the computer's, in Versus, the DS
/// Campaign or the BH Campaign (not AW2's campaign, whose maps name AW2's own personalities, nor Survival).
/// `part` is one of the [`SWITCHES`] bits ([`OFF_BUILD`], [`OFF_POWER`]).
pub(crate) fn in_scope(core: &Core, army: u32, part: u8) -> bool {
    if !is_on(core) || !is_cpu(core, army) || crate::survival::on(core) {
        return false;
    }
    let sw = core.raw_read_8(SWITCHES, -1);
    if sw & (OFF | part) != 0 {
        return false;
    }
    crate::pvp::in_versus(core) || crate::ds_campaign::active(core)
}

pub(crate) fn current_army(core: &Core) -> u32 {
    core.raw_read_16(CURRENT_ARMY, -1) as u32
}

// --- Rolls ----------------------------------------------------------------------------

/// The same mix as [`crate::bh_factory`]'s: a few u32s to one.
pub(crate) fn hash(parts: &[u32]) -> u32 {
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

/// What a roll is for (part of its hash, so two rolls of one moment differ).
#[derive(Clone, Copy)]
pub(crate) enum Roll {
    Profile = 1,
    Order = 2,
    Mech = 3,
    Power = 4,
}

/// A roll in 0..n where Dual Strike calls `Rng_Next`: AW2's generator state (read, not advanced), the day, the
/// army, what it is for and `k` (which one of its kind).
pub(crate) fn roll(core: &Core, army: u32, what: Roll, k: u32, n: u32) -> u32 {
    let day = core.raw_read_16(DAY, -1) as u32;
    hash(&[core.raw_read_32(RNG, -1), day, army, what as u32, k]) % n.max(1)
}

pub(crate) fn log(line: &str) {
    crate::bh_factory::log(line);
}

pub(crate) fn logging() -> bool {
    crate::bh_factory::logging()
}

// --- Behaviours -------------------------------------------------------------------------

pub use crate::two_front::{ASSAULT, DEFENSE, GENERAL, STRIKE};

/// Army `army`'s behaviour (Dual Strike's player +0x2E: Strike, Assault, General, Defense). A two-front
/// battle's is its Intel > General ([`crate::two_front::cpu_posture`]); elsewhere the army's own byte here,
/// General unless set.
pub fn behaviour(core: &Core, army: u32) -> u8 {
    let two = crate::two_front::cpu_posture(core, army);
    if !is_on(core) {
        return two;
    }
    if two != GENERAL || !(1..=5).contains(&army) {
        return two;
    }
    match core.raw_read_8(BEHAVIOURS + army - 1, -1) {
        0 => GENERAL,
        b => (b - 1).min(DEFENSE),
    }
}

pub fn set_behaviour(core: &mut Core, army: u32, b: u8) {
    if (1..=5).contains(&army) {
        core.raw_write_8(BEHAVIOURS + army - 1, -1, if b == GENERAL { 0 } else { b.min(DEFENSE) + 1 });
    }
}

/// The turn's profile roll (`AiProfile_Build`): 0 for Defense, 100 for Assault and while a Tag Power's second
/// half plays, otherwise 0..99, drawn once per army and day and kept ([`ROLLS`]).
pub(crate) fn profile_roll(core: &mut Core, army: u32) -> u32 {
    match behaviour(core, army) {
        DEFENSE => return 0,
        ASSAULT => return 100,
        _ => {}
    }
    if crate::tag::phase(core, army) == 2 {
        return 100;
    }
    // (a roll set after a power stands for the rest of the day)
    let at = ROLLS + 2 * (army.clamp(1, 5) - 1);
    let day = core.raw_read_16(DAY, -1) as u8;
    if core.raw_read_8(at + 1, -1) != day.wrapping_add(1) {
        let r = roll(core, army, Roll::Profile, 0, 100) as u8;
        core.raw_write_8(at, -1, r);
        core.raw_write_8(at + 1, -1, day.wrapping_add(1));
    }
    core.raw_read_8(at, -1) as u32
}

/// Sets the turn's profile roll (after a power: Dual Strike's `AiProfile_RerollThreatLimits`).
pub(crate) fn set_profile_roll(core: &mut Core, army: u32, r: u32) {
    let at = ROLLS + 2 * (army.clamp(1, 5) - 1);
    let day = core.raw_read_16(DAY, -1) as u8;
    core.raw_write_8(at, -1, r.min(100) as u8);
    core.raw_write_8(at + 1, -1, day.wrapping_add(1));
}

/// `AiProfile_Randomise`: a limit from its base and spread by the roll.
pub(crate) fn randomise(base: u8, spread: u8, roll: u32) -> u8 {
    let (b, s) = (base as i32, spread as i32);
    (b + s * roll as i32 / 100 - s / 2).clamp(1, 255) as u8
}

// --- Profiles -----------------------------------------------------------------------------

const SETS: u32 = 0x0216_1B8C;
const SET: u32 = 29;
const MODS: u32 = 0x0216_2050;
const MOD: u32 = 0x40;
const TEMPLATES: u32 = 0x0216_2A90;
const TEMPLATE: u32 = 0x15C;
const TEMPLATE_COUNT: u8 = 34;
/// Dual Strike's unit types (Infantry .. Oozium).
pub(crate) const DS_TYPES: usize = 26;

/// A template's power hook (its function pointer at +0), by what it agrees to.
#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) enum Hook {
    Never,
    /// `AiTurn_IsPhase3`: the first power check of the turn.
    First,
    /// Andy: the first check, with a unit (not carried) under 91 hp.
    Hurt,
    /// Olaf: always; in snow only the Super.
    NotSnow,
    /// Sonja: the CO Power only in fog or rain (at the first check); the Super at the first check.
    FogPower,
    /// Sasha: the Super at the first check; either with 30000 funds and an enemy CO nearer its power.
    Funds,
    /// Drake: always in fog or rain; otherwise not the Super at the first check.
    Drake,
    /// Eagle: only at the last check.
    Last,
    /// Colin: the CO Power while he owns a factory; the Super at the first check.
    Colin,
    /// Hawke: always.
    Always,
    /// Hachi: anything while he owns a factory; else the Super at the first check or with a free city.
    Hachi,
    /// Kindle: the Super at the first check; the CO Power with enemies on properties.
    Kindle,
}

fn hook_of(addr: u32) -> Hook {
    match addr {
        0 => Hook::Never,
        0x0209_95A4 => Hook::First,
        0x0209_91F4 => Hook::Hurt,
        0x0209_91B0 => Hook::NotSnow,
        0x0209_8E7C => Hook::FogPower,
        0x0209_90C4 => Hook::Funds,
        0x0209_92C8 => Hook::Drake,
        0x0209_9338 => Hook::Last,
        0x0209_94B8 => Hook::Colin,
        0x0209_9520 => Hook::Always,
        0x0209_937C => Hook::Hachi,
        0x0209_8EF0 => Hook::Kindle,
        _ => Hook::First,
    }
}

/// One unit type's row of a profile.
#[derive(Clone, Copy, Default, Debug)]
pub(crate) struct UnitProfile {
    /// Build weight in % (0: only the dedicated build steps make it), from the mods.
    pub build: u8,
    pub threat_max: (u8, u8),
    pub threat_sum: (u8, u8),
    /// Fuel % and hp under which the unit wants supply or repair (Dual Strike's service steps, which AW2's passes
    /// keep: read for the record, not used).
    #[allow(dead_code)]
    pub fuel: u8,
    #[allow(dead_code)]
    pub repair: u8,
    pub weights: [i8; 7],
}

#[derive(Clone, Debug)]
pub(crate) struct Profile {
    pub template: u8,
    pub hook: Hook,
    /// Template bytes 4..9: the CO Power's gap % and roll alone, then with a partner, then the Super's partner
    /// meter limit and roll.
    pub power: [u8; 6],
    /// The mods' 12 header bytes (`unk_08`).
    pub header: [u8; 12],
    pub units: [UnitProfile; DS_TYPES],
}

impl Profile {
    /// The row of tangoAW2 unit type `t`.
    pub fn unit(&self, t: u8) -> UnitProfile {
        match crate::roster::ds_id(t) {
            Some(d) if (1..=DS_TYPES as u8).contains(&d) => self.units[d as usize - 1],
            _ => UnitProfile::default(),
        }
    }
}

/// The template Dual Strike gives CO `co` (an AW2 or new CO) in set 1.
pub(crate) fn template_of(co: u8) -> Option<u8> {
    let pack = crate::ds_pack::pack()?;
    let set = pack.arm9_at(SETS + SET, SET as usize)?;
    // (Asuka has no Dual Strike twin of her own: the computer plays her with Hawke's profile, whose powers she shares: Black Wave and Black Storm, always when the meter allows)
    let ds = crate::tag::ds_id(co).or_else(|| (co == crate::co_new::ASUKA).then_some(15)).unwrap_or(0) as usize;
    set.get(1 + ds).copied().filter(|&t| t < TEMPLATE_COUNT)
}

/// CO `co`'s profile (set 1, mods 0).
pub(crate) fn profile(co: u8) -> Option<Profile> {
    let pack = crate::ds_pack::pack()?;
    let mods_id = pack.arm9_at(SETS + SET, 1)?[0] as u32;
    let mods = pack.arm9_at(MODS + MOD * mods_id, MOD as usize)?;
    let template = template_of(co)?;
    let t = pack.arm9_at(TEMPLATES + TEMPLATE * template as u32, TEMPLATE as usize)?;
    let mut p = Profile {
        template,
        hook: hook_of(u32::from_le_bytes(t[0..4].try_into().ok()?)),
        power: t[4..10].try_into().ok()?,
        header: mods[0..12].try_into().ok()?,
        units: [UnitProfile::default(); DS_TYPES],
    };
    for (k, u) in p.units.iter_mut().enumerate() {
        let r = &t[0x0A + 13 * k..0x0A + 13 * (k + 1)];
        let mut weights = [0i8; 7];
        for (w, &b) in weights.iter_mut().zip(&r[6..13]) {
            *w = b as i8;
        }
        *u = UnitProfile {
            build: mods[12 + 2 * k],
            threat_max: (r[0], r[1]),
            threat_sum: (r[2], r[3]),
            fuel: r[4],
            repair: r[5],
            weights,
        };
    }
    Some(p)
}

/// Army `army`'s CO (its active one) and power mode.
pub(crate) fn army_co(core: &Core, army: u32) -> (u8, u8) {
    let p = players(core) + 0x3C * army;
    (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x1E, -1))
}

// --- Unit types ------------------------------------------------------------------------

pub(crate) const INFANTRY: u8 = 1;
pub(crate) const MECH: u8 = 2;
pub(crate) const TANK: u8 = 5;
pub(crate) const RECON: u8 = 6;
pub(crate) const APC: u8 = 7;
pub(crate) const ARTILLERY: u8 = 10;
pub(crate) const ANTI_AIR: u8 = 14;
pub(crate) const FIGHTER: u8 = 16;
pub(crate) const BOMBER: u8 = 17;
pub(crate) const T_COPTER: u8 = 20;
pub(crate) const BATTLESHIP: u8 = 21;
pub(crate) const CRUISER: u8 = 22;
pub(crate) const LANDER: u8 = 23;
pub(crate) const SUB: u8 = 24;
pub use crate::roster::{BLACK_BOAT, BLACK_BOMB, CARRIER, MEGATANK, OOZIUM, PIPERUNNER, STEALTH};

/// Every unit type, in Dual Strike's order (Carrier before Oozium).
pub(crate) fn types() -> impl Iterator<Item = u8> {
    (1u8..=24).chain([CARRIER, OOZIUM])
}

pub(crate) const FOOT: u8 = 0x01;
pub(crate) const TIRES: u8 = 0x02;
pub(crate) const TREAD: u8 = 0x04;
pub(crate) const GROUND: u8 = FOOT | TIRES | TREAD;
pub(crate) const AIR: u8 = 0x10;
pub(crate) const SEA: u8 = 0x20;

#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Attack {
    Direct,
    Indirect,
    None,
}

/// What Dual Strike's unit record says of a type.
#[derive(Clone, Copy)]
pub(crate) struct Stats {
    pub group: u8,
    pub min_range: u8,
    pub max_range: u8,
    pub moves: u8,
    pub category: u8,
}

pub(crate) fn stats(t: u8) -> Stats {
    match crate::roster::ds_record(t) {
        Some(r) => Stats { group: r[0x1F], min_range: r[0x14], max_range: r[0x15], moves: r[0x10], category: r[0x22] },
        None => Stats { group: 0, min_range: 0, max_range: 0, moves: 0, category: 0 },
    }
}

/// `UnitType_GetAttackKind`, for the build and threat rules (a Black Bomb and an Oozium do not attack).
pub(crate) fn attack(t: u8) -> Attack {
    let s = stats(t);
    if t == BLACK_BOMB || t == OOZIUM || s.min_range == 0 {
        Attack::None
    } else if s.min_range >= 2 {
        Attack::Indirect
    } else {
        Attack::Direct
    }
}

/// The factory kind that builds a type (1 base, 2 airport, 3 port; `gUnitSupplyKind`).
pub(crate) fn supply(t: u8) -> u8 {
    let g = stats(t).group;
    if g & AIR != 0 {
        2
    } else if g & SEA != 0 {
        3
    } else {
        1
    }
}

/// `UnitType_BestBaseDamage`: the better weapon's chart value (no CO).
pub(crate) fn base_damage(att: u8, def: u8) -> i32 {
    crate::roster::chart(att, def, 0).max(crate::roster::chart(att, def, 1)) as i32
}

/// `Ai_RatedBaseDamage`: the same, raised for a Fighter (by half) or an Anti-Air (twice) against a Fighter.
pub(crate) fn rated_damage(att: u8, def: u8) -> i32 {
    let d = base_damage(att, def);
    match (att, def) {
        (FIGHTER, FIGHTER) => d * 3 >> 1,
        (ANTI_AIR, FIGHTER) => d * 2,
        _ => d,
    }
}

// --- The battle --------------------------------------------------------------------------

const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const TERRAIN: u32 = MAP + 0x1432;
const UNIT_PLANE: u32 = MAP + 0x12;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
pub(crate) const CARRIED: u8 = 0x08;

pub(crate) const C_HQ: u8 = 8;
pub(crate) const C_CITY: u8 = 6;
pub(crate) const C_AIRPORT: u8 = 10;
pub(crate) const C_PORT: u8 = 11;
pub(crate) const C_BASE: u8 = 14;
pub(crate) const C_SHOAL: u8 = 13;
pub(crate) const C_PIPE: u8 = 15;
pub(crate) const C_SEAM: u8 = 16;

#[derive(Clone, Copy, Debug)]
pub(crate) struct Unit {
    pub rec: u32,
    pub army: u32,
    pub t: u8,
    pub x: i32,
    pub y: i32,
    /// 0..100.
    pub hp: i32,
    pub flags: u8,
}

impl Unit {
    pub fn carried(&self) -> bool {
        self.flags & CARRIED != 0
    }
}

/// The battle as the CPU sees it at one moment: the map, its properties' owners, every unit, the players.
pub(crate) struct Board {
    pub w: i32,
    pub h: i32,
    pub class: Vec<u8>,
    /// The army (1..5) owning the property on each cell (0: none or neutral): the terrain plane's top three bits,
    /// the army slot, not its colour (a campaign's army 2 may wear Green Earth's colours).
    pub owner: Vec<u8>,
    /// Index + 1 into `units` of the unit on each cell (0: none).
    pub at: Vec<u16>,
    pub units: Vec<Unit>,
    pub team: [u8; 6],
    pub playing: [bool; 6],
    pub co: [u8; 6],
    pub mode: [u8; 6],
    pub abilities: bool,
    pub fog: bool,
    pub weather: u8,
    pub day: u32,
    /// Each playing army's movement costs by unit type (index army * 32 + type), 0xFF where it cannot go.
    rows: Vec<[u8; 32]>,
}

pub(crate) const PROPERTIES: [u8; 6] = [C_HQ, C_BASE, C_CITY, C_AIRPORT, C_PORT, 20];

impl Board {
    pub fn read(core: &Core) -> Board {
        let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
        let p = players(core);
        let mut team = [0u8; 6];
        let mut playing = [false; 6];
        let mut co = [0u8; 6];
        let mut mode = [0u8; 6];

        for a in 1..=5u32 {
            let r = p + 0x3C * a;
            team[a as usize] = core.raw_read_8(r + 0x2A, -1);
            playing[a as usize] = matches!(core.raw_read_8(r + 0x1B, -1), 1 | 2);
            co[a as usize] = core.raw_read_8(r + 0x1D, -1);
            mode[a as usize] = core.raw_read_8(r + 0x1E, -1);
        }
        let n = (w.max(0) * h.max(0)) as usize;
        let mut b = Board {
            w,
            h,
            class: vec![0; n],
            owner: vec![0; n],
            at: vec![0; n],
            units: Vec::new(),
            team,
            playing,
            co,
            mode,
            abilities: core.raw_read_8(ABILITIES_ON, -1) != 0,
            fog: core.raw_read_8(FOG, -1) != 0,
            weather: core.raw_read_8(crate::ds_weather::WEATHER, -1),
            day: core.raw_read_16(DAY, -1) as u32,
            rows: vec![[0xFF; 32]; 6 * 32],
        };
        let base = core.raw_read_32(UNITS_POINTER, -1);
        let mut ids = vec![0u8; n];
        for y in 0..h {
            let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
            for x in 0..w {
                let c = row + x as u32;
                let i = (y * w + x) as usize;
                let t = core.raw_read_8(TERRAIN + c, -1);
                b.class[i] = t & 0x1F;
                if PROPERTIES.contains(&b.class[i]) {
                    b.owner[i] = (t >> 5) % 6;
                }
                ids[i] = core.raw_read_8(UNIT_PLANE + c, -1);
            }
        }
        let mut rec = [0u8; 12];
        let mut index_of = vec![0u16; 256];
        for i in 1..255u32 {
            let r = base + UNIT * i;
            core.raw_read_range(r, -1, &mut rec);
            if rec[0] == 0 {
                continue;
            }
            let army = crate::five::army_of_index(core, i);
            if !(1..=5).contains(&army) {
                continue;
            }
            b.units.push(Unit {
                rec: r,
                army,
                t: rec[0],
                x: rec[2] as i32,
                y: rec[3] as i32,
                hp: (u16::from_le_bytes([rec[4], rec[5]]) & 0x7F) as i32,
                flags: rec[1],
            });
            index_of[i as usize] = b.units.len() as u16;
        }
        for (i, &id) in ids.iter().enumerate() {
            if id != 0 {
                let k = index_of[id as usize];
                if k != 0 && !b.units[k as usize - 1].carried() {
                    b.at[i] = k;
                }
            }
        }
        for a in 1..=5u32 {
            if !b.playing[a as usize] {
                continue;
            }
            for t in types() {
                b.rows[a as usize * 32 + t as usize] = crate::oozium::move_row(core, a, t);
            }
        }
        b
    }

    pub fn inside(&self, x: i32, y: i32) -> bool {
        x >= 0 && y >= 0 && x < self.w && y < self.h
    }

    pub fn idx(&self, x: i32, y: i32) -> usize {
        (y * self.w + x) as usize
    }

    pub fn unit_at(&self, x: i32, y: i32) -> Option<&Unit> {
        if !self.inside(x, y) {
            return None;
        }
        match self.at[self.idx(x, y)] {
            0 => None,
            k => Some(&self.units[k as usize - 1]),
        }
    }

    /// The property on cell `i` is army `army`'s.
    pub fn owns(&self, i: usize, army: u32) -> bool {
        self.owner[i] != 0 && self.owner[i] as u32 == army
    }

    /// The property on cell `i` is owned by army `army`'s team.
    pub fn team_owns(&self, i: usize, army: u32) -> bool {
        self.owner[i] != 0 && self.same_team(self.owner[i] as u32, army)
    }

    pub fn same_team(&self, a: u32, b: u32) -> bool {
        self.team[a as usize % 6] == self.team[b as usize % 6]
    }

    pub fn cost(&self, army: u32, t: u8, x: i32, y: i32) -> u8 {
        self.rows[army as usize % 6 * 32 + t as usize % 32][self.class[self.idx(x, y)] as usize % 32]
    }

    /// Army `army`'s move points for type `t` (with its CO's).
    pub fn moves(&self, army: u32, t: u8) -> i32 {
        let base = stats(t).moves as i32;
        base + if self.abilities {
            crate::co_roster::stat(self.co[army as usize % 6], self.mode[army as usize % 6], t, crate::co_roster::MOVE).unwrap_or(0)
        } else {
            0
        }
    }

    /// Army `army`'s max range for type `t` (with its CO's, for indirect units).
    pub fn max_range(&self, army: u32, t: u8) -> i32 {
        let s = stats(t);
        let bonus = if self.abilities && s.max_range > 1 {
            crate::co_roster::stat(self.co[army as usize % 6], self.mode[army as usize % 6], t, crate::co_roster::RANGE).unwrap_or(0)
        } else {
            0
        };
        (s.max_range as i32 + bonus).max(s.min_range as i32)
    }

    /// `RangeMap_FillMoves`: the move cost from (x, y) to every cell for `army`'s `t` within `budget` (-1: not
    /// reached), units of other teams in the way; with `ring`, the cells next to the reach get `budget + 1`
    /// (`RangeMap_MarkAdjacentTiles(111)`).
    pub fn flood(&self, army: u32, t: u8, x: i32, y: i32, budget: i32, ring: bool) -> Vec<i16> {
        use std::cmp::Reverse;
        use std::collections::BinaryHeap;
        let mut d = vec![-1i16; self.class.len()];
        if !self.inside(x, y) {
            return d;
        }
        let mut heap = BinaryHeap::new();
        d[self.idx(x, y)] = 0;
        heap.push(Reverse((0i32, y, x)));
        while let Some(Reverse((c, y, x))) = heap.pop() {
            if c > d[self.idx(x, y)] as i32 {
                continue;
            }
            for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
                let (nx, ny) = (x + dx, y + dy);
                if !self.inside(nx, ny) {
                    continue;
                }
                let step = self.cost(army, t, nx, ny);
                if step == 0xFF || step == 0 {
                    continue;
                }
                let nc = c + step as i32;
                if nc > budget {
                    continue;
                }
                if let Some(u) = self.unit_at(nx, ny) {
                    if !self.same_team(u.army, army) {
                        continue;
                    }
                }
                let i = self.idx(nx, ny);
                if d[i] < 0 || nc < d[i] as i32 {
                    d[i] = nc as i16;
                    heap.push(Reverse((nc, ny, nx)));
                }
            }
        }
        if ring {
            let reached: Vec<usize> = (0..d.len()).filter(|&i| d[i] >= 0).collect();
            for i in reached {
                let (x, y) = (i as i32 % self.w, i as i32 / self.w);
                for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
                    if self.inside(x + dx, y + dy) {
                        let j = self.idx(x + dx, y + dy);
                        if d[j] < 0 {
                            d[j] = (budget + 1) as i16;
                        }
                    }
                }
            }
        }
        d
    }

    /// `Unit_CanRepairAt`: a unit on a property of its army's team that repairs it (ground: HQ, city, base; air:
    /// airport; sea: port).
    pub fn repairs(&self, u: &Unit) -> bool {
        if !self.inside(u.x, u.y) {
            return false;
        }
        let i = self.idx(u.x, u.y);
        if !self.team_owns(i, u.army) {
            return false;
        }
        let g = stats(u.t).group;
        match self.class[i] {
            C_HQ | C_CITY | C_BASE => g & GROUND != 0,
            C_AIRPORT => g & AIR != 0,
            C_PORT => g & SEA != 0,
            _ => false,
        }
    }

    /// Army `army`'s firepower % for type `t` at power state `mode` with its CO in slot `slot` (0 the active CO,
    /// 1 the partner).
    pub fn firepower(&self, core: &Core, army: u32, slot: u32, mode: u8, t: u8) -> i32 {
        if !self.abilities {
            return 0;
        }
        let co = if slot == 0 { Some(self.co[army as usize % 6]) } else { crate::tag::partner(core, army) };
        co.and_then(|c| crate::co_roster::stat(c, mode, t, crate::co_roster::FIREPOWER)).unwrap_or(0)
    }

    /// `Co_GetSlotChartDamage`: a weapon's chart value with the firepower.
    pub fn slot_damage(&self, core: &Core, army: u32, slot: u32, mode: u8, att: u8, def: u8, weapon: u32) -> i32 {
        let c = crate::roster::chart(att, def, weapon) as i32;
        if c == 0 {
            return 0;
        }
        c * (100 + self.firepower(core, army, slot, mode, att)) / 100
    }
}

/// Weather's effect on the AI: fog, or rain (which brings fog in Dual Strike).
pub(crate) fn foggy(core: &Core) -> bool {
    core.raw_read_8(FOG, -1) != 0 || core.raw_read_8(crate::ds_weather::WEATHER, -1) == 2
}

pub(crate) fn powers_on(core: &Core) -> bool {
    core.raw_read_8(POWERS_ON, -1) != 0
}

pub(crate) fn abilities_on(core: &Core) -> bool {
    core.raw_read_8(ABILITIES_ON, -1) != 0
}

/// The CPU's price of type `t` for army `army` (AW2's `0x08042C9C` x 10: the table's cost and the CO's cost %).
pub(crate) fn price(core: &Core, army: u32, t: u8) -> u32 {
    let base = core.raw_read_16(crate::roster::table(core) + 0x5C * t as u32 + 6, -1) as i32;
    let (co, mode) = army_co(core, army);
    let pct = if abilities_on(core) {
        let table = core.raw_read_32(crate::tag::CO_TABLE_POOL, -1);
        core.raw_read_16(table + 0x104 * co as u32 + 0x44 * mode as u32 + 0x4C, -1) as i16 as i32
    } else {
        0
    };
    ((pct + 100) * base / 100).max(0) as u32 * 10
}

pub(crate) fn funds(core: &Core, army: u32) -> u32 {
    core.raw_read_32(players(core) + 0x3C * army, -1)
}

/// The day's income (player +8, AW2's sum of its properties' income).
pub(crate) fn income(core: &Core, army: u32) -> u32 {
    core.raw_read_32(players(core) + 0x3C * army + 8, -1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn randomise_matches_dual_strike() {
        // Andy's Md Tank: base 50, spread 30.
        assert_eq!(randomise(50, 30, 0), 35);
        assert_eq!(randomise(50, 30, 100), 65);
        assert_eq!(randomise(0, 0, 50), 1);
        assert_eq!(randomise(255, 80, 100), 255);
    }

    #[test]
    fn ram() {
        assert!(BUILDS + 4 + 4 * BUILDS_MAX <= ROLLS);
        assert!(ROLLS + 10 <= BEHAVIOURS && BEHAVIOURS + 5 <= STATE + 0xD0 && STATE + 0xD8 <= SWITCHES);
        assert!(SWITCHES < crate::ram_map::DS_AI.0 + crate::ram_map::DS_AI.1);
    }

    #[test]
    fn hooks() {
        assert_eq!(hook_of(0x0209_95A4), Hook::First);
        assert_eq!(hook_of(0), Hook::Never);
    }
}
