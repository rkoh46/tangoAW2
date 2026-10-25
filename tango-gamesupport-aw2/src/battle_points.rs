//! Dual Strike's battle points and the CO experience they give (docs/AW2.md "CO skills", EXP), with the pack.
//!
//! AW2's own end of battle (`UpdateAllArmyScores`) already works out speed, power, technique, their total and the
//! rank with Dual Strike's formulas; what Dual Strike adds is here (its `BattleScore_Compute`, `BattleResults_Fill`,
//! `BattleResults_AwardExperience`, `ExpBonus_Scale`, `Survival_AwardCoExperience`):
//!
//! - **Bonus points** for what the human armies destroyed in the battle, each count kept per army and capped at 99
//!   (Dual Strike's `Player.destroyedCounts`, counted by `ObjectAttack_ShowHit` and `Combat_ApplyResult`): a Black
//!   Cannon 30, a minicannon 10, a Black Crystal 20, a pipe seam 5, an Oozium 40 (that row at most 999); 30 more on
//!   Crystal Calamity and For the Future! (Dual Strike's maps 242 and 247). The battle's points are the score plus
//!   the bonus; 0 when player 1's team lost and in Versus; x2 in a Hard campaign.
//! - **EXP** for each CO of each human army (a tag pair's partner too, `crate::tag::partner`): the points, scaled
//!   by the mode: the campaigns x2 for a lone CO, x1 for each CO of a pair, x1 in Dual Strike's first eight
//!   missions on Normal (AW2's campaign: its first eight); the War Room x2.5, x2 with skills on, x1.5 for a pair,
//!   x1 for a pair with skills. In a campaign the mission's best before this win (its record) is taken off first,
//!   scaled the same way and never below 0 EXP, so a replay gives only what it beats the record by. Survival gives
//!   none per map: at the end of a run player 1's COs get the run's points (its bonus for what is left in them),
//!   at most 9999 ([`survival_run_over`]). Versus gives none.
//!
//! Where: AW2's `InsertBestScoreRecord` (`0x08017720`, crate::ds_campaign's trap), which every battle's end calls
//! with the results army's score just worked out and before any record changes ([`results`]). The counts live in
//! EWRAM ([`STATE`]), cleared at a battle's start and after its results.

use mgba::core::Core;

use crate::ds_weather::is_on;

// --- RAM (tangoAW2's 0x0203C170..0x0203C18F) ---------------------------------------

/// The battle's counts: per army 1..4, five bytes (Dual Strike's order: Black Cannons, minicannons, pipe seams,
/// Oozium, Black Crystals), then the last battle's bonus points (u16, for crate::survival's run points).
pub const STATE: u32 = 0x0203_C170;
pub const STATE_LEN: u32 = 0x20;
const KINDS: u32 = 5;
const LAST_BONUS: u32 = STATE + 4 * KINDS;

pub const CANNON: u32 = 0;
pub const MINICANNON: u32 = 1;
pub const PIPE_SEAM: u32 = 2;
pub const OOZIUM: u32 = 3;
pub const CRYSTAL: u32 = 4;
/// Points per destroyed thing, by kind.
const VALUE: [u32; KINDS as usize] = [30, 10, 5, 40, 20];
const COUNT_CAP: u8 = 99;
const OOZIUM_CAP: u32 = 999;
/// Crystal Calamity and For the Future! (DS Campaign record indexes; Dual Strike's maps 242 and 247).
const BONUS_MISSIONS: [u8; 2] = [18, 23];
const MAP_BONUS: u32 = 30;

// --- The game ---------------------------------------------------------------------

const GAME_MODE: u32 = 0x0300_3FC1;
const MAP_ID: u32 = 0x0300_3FC2;
const DAY: u32 = 0x0300_4080;
const CAMPAIGN: u8 = 1;
const WAR_ROOM: u8 = 2;
const VERSUS: u8 = 3;
/// AW2's campaign maps start at this id; its records (`0x0200C2D0`, per map a Normal and a Hard word: CO, days << 8,
/// score << 20).
const FIRST_CAMPAIGN_MAP: u8 = 0x8A;
const AW2_CAMPAIGN_RECORDS: u32 = 0x0200_C2D0;
/// AW2's flag 0x60 (Hard Campaign being played), as `IsHardCampaignMode` reads it outside a DS session.
const AW2_HARD_FLAG: u32 = 0x0202_8038;
const P_HUMAN: u32 = 0x1B;
const P_CO: u32 = 0x1D;
const P_DEFEATED: u32 = 0x14;
const P_YIELD: u32 = 0x31;
const P_TEAM: u32 = 0x2A;

fn player(core: &Core, army: u32) -> u32 {
    crate::five::players(core) + 0x3C * army
}

/// Army `army` (1..5) is in the battle and played by a human.
pub fn human(core: &Core, army: u32) -> bool {
    (1..=5).contains(&army) && core.raw_read_8(player(core, army) + P_HUMAN, -1) == 1
}

fn out(core: &Core, army: u32) -> bool {
    let p = player(core, army);
    core.raw_read_16(p + P_DEFEATED, -1) != 0 || core.raw_read_8(p + P_YIELD, -1) != 0
}

/// Player 1's team still has an army in the battle (AW2's `IsPlayer1TeamAlive`).
pub fn player1_team_in(core: &Core) -> bool {
    let team = core.raw_read_8(player(core, 1) + P_TEAM, -1);
    (1..=5).any(|a| {
        let p = player(core, a);
        core.raw_read_8(p + P_HUMAN, -1) != 0 && !out(core, a) && core.raw_read_8(p + P_TEAM, -1) == team
    })
}

/// A campaign battle on Hard (the DS session's flag, else AW2's).
fn hard(core: &Core) -> bool {
    if crate::ds_campaign::active(core) {
        crate::ds_campaign::hard(core)
    } else {
        core.raw_read_8(AW2_HARD_FLAG, -1) & 1 != 0
    }
}

// --- The counts --------------------------------------------------------------------

/// A battle starts: no counts. (A battle continued from a save starts later than day 1 and keeps nothing either:
/// the counts are not saved with it.)
pub fn clear(core: &mut Core) {
    core.raw_write_range(STATE, -1, &[0u8; (4 * KINDS) as usize]);
}

/// Army `army` destroyed one thing of `kind` ([`CANNON`]..[`CRYSTAL`]): counted for a human army, up to 99.
pub fn count(core: &mut Core, army: u32, kind: u32) {
    if !is_on(core) || !(1..=4).contains(&army) || kind >= KINDS || !human(core, army) {
        return;
    }
    let at = STATE + KINDS * (army - 1) + kind;
    let n = core.raw_read_8(at, -1);
    core.raw_write_8(at, -1, (n + 1).min(COUNT_CAP));
}

/// The bonus points of the human armies' counts (Dual Strike adds the humans' counts up before it multiplies).
pub fn bonus(core: &Core) -> u32 {
    let mut sums = [0u32; KINDS as usize];
    for a in 1..=4u32 {
        if !human(core, a) {
            continue;
        }
        for (k, s) in sums.iter_mut().enumerate() {
            *s += core.raw_read_8(STATE + KINDS * (a - 1) + k as u32, -1) as u32;
        }
    }
    let mut total: u32 = sums
        .iter()
        .zip(VALUE)
        .enumerate()
        .filter(|(k, _)| *k != OOZIUM as usize)
        .map(|(_, (n, v))| n * v)
        .sum();
    total += (sums[OOZIUM as usize] * VALUE[OOZIUM as usize]).min(OOZIUM_CAP);
    if crate::ds_campaign::active(core)
        && crate::ds_campaign::is_ds(core)
        && BONUS_MISSIONS.contains(&crate::ds_campaign::mission(core))
    {
        total += MAP_BONUS;
    }
    total
}

/// The last battle's bonus points (Survival adds them to the run's points).
pub fn last_bonus(core: &Core) -> u32 {
    core.raw_read_16(LAST_BONUS, -1) as u32
}

// --- Where things are destroyed -----------------------------------------------------

const CURRENT_ARMY: u32 = 0x0300_33EC;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
/// The battle records (`BattleUnit`) of the attacker and the defender: +8 the HP left after the battle (s16).
const BATTLE_ATTACKER: u32 = 0x0300_13D0;
const BATTLE_DEFENDER: u32 = 0x0300_13B0;
const OOZIUM_TYPE: u8 = crate::roster::OOZIUM;
/// The structure hit step's proc (r3 at crate::factory_hp's trap): its kind (u16 +0x64), its invention entry
/// (+0x4C). Kinds: 1 Laser, 3 and 5 Black Cannons (a 3 on tangoAW2's Obelisk tile the Black Obelisk), 4 minicannon
/// (on the Crystal's tile the Black Crystal), 6 pipe seam.
const KIND_CANNON: u16 = 3;
const KIND_MINICANNON: u16 = 4;
const KIND_CANNON_DOWN: u16 = 5;
const KIND_SEAM: u16 = 6;

/// One side of a unit battle: the unit's record, its army, its HP left after the battle (the battle record's).
#[derive(Clone, Copy, Debug)]
pub struct Side {
    pub unit: u32,
    pub army: u32,
    pub hp_after: i32,
}

/// The battle `sub_08041978` has just worked out (crate::co_powers' trap where the meters are charged): the
/// attacker (the selected unit) and the defender (unit index `defender`).
pub fn fight(core: &Core, attacker: u32, defender: u32) -> [Side; 2] {
    let units = core.raw_read_32(UNITS_POINTER, -1);
    let side = |unit: u32, record: u32| Side {
        unit,
        army: crate::five::army_of_index(core, unit.wrapping_sub(units) / UNIT),
        hp_after: core.raw_read_16(record + 8, -1) as i16 as i32,
    };
    [
        side(attacker, BATTLE_ATTACKER),
        side(units + UNIT * defender, BATTLE_DEFENDER),
    ]
}

/// A unit battle was fought (crate::co_powers' trap): an Oozium destroyed counts for the other side's army
/// (`Combat_ApplyResult`).
pub fn battle_fought(core: &mut Core, attacker: u32, defender: u32) {
    let sides = fight(core, attacker, defender);
    for (k, s) in sides.iter().enumerate() {
        if s.hp_after <= 0 && core.raw_read_8(s.unit, -1) == OOZIUM_TYPE {
            count(core, sides[1 - k].army, OOZIUM);
        }
    }
}

/// What the structure hit step destroyed (r3 its proc), as a kind of [`count`] (`ObjectAttack_ShowHit`), with
/// whether it is a Black Obelisk (which Dual Strike counts in its records but gives no points).
pub fn destroyed_structure(core: &Core) -> Option<(Option<u32>, bool)> {
    let proc = core.gba().cpu().gpr(3) as u32;
    if !(0x0200_0000..0x0400_0000).contains(&proc) {
        return None;
    }
    let kind = core.raw_read_16(proc + 0x64, -1);
    let entry = core.raw_read_32(proc + 0x4C, -1);
    let ours = || {
        (0x0200_0000..0x0400_0000)
            .contains(&entry)
            .then(|| crate::obelisk::structure(core, entry))
            .flatten()
    };
    use crate::obelisk::Structure;
    Some(match kind {
        KIND_CANNON if ours() == Some(Structure::Obelisk) => (None, true),
        KIND_CANNON | KIND_CANNON_DOWN => (Some(CANNON), false),
        KIND_MINICANNON => match ours() {
            Some(Structure::Crystal) => (Some(CRYSTAL), false),
            Some(Structure::Part) => return None,
            _ => (Some(MINICANNON), false),
        },
        KIND_SEAM => (Some(PIPE_SEAM), false),
        _ => return None,
    })
}

/// The structure hit step's destroy branch (crate::factory_hp's trap): the army whose turn it is (its unit hit
/// the structure) counts it.
pub fn structure_destroyed(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    if let Some((Some(kind), _)) = destroyed_structure(core) {
        let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
        count(core, army, kind);
    }
}

// --- EXP ---------------------------------------------------------------------------

/// Dual Strike's EXP multipliers (`EXP_BONUS_*`).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mult {
    X1,
    X1_5,
    X2,
    X2_5,
}

/// `ExpBonus_Scale`.
pub fn scale(points: u32, m: Mult) -> u32 {
    match m {
        Mult::X1 => points,
        Mult::X1_5 => points + (points >> 1),
        Mult::X2 => points << 1,
        Mult::X2_5 => (points << 1) + (points >> 1),
    }
}

/// The multiplier for an army's COs (`BattleResults_Fill`): `early` Dual Strike's first eight missions on Normal,
/// `paired` the army has a partner, `skills` it has skills on.
pub fn mult(mode: u8, early: bool, paired: bool, skills: bool) -> Mult {
    match mode {
        CAMPAIGN if early || paired => Mult::X1,
        CAMPAIGN => Mult::X2,
        WAR_ROOM => match (paired, skills) {
            (false, false) => Mult::X2_5,
            (false, true) => Mult::X2,
            (true, false) => Mult::X1_5,
            (true, true) => Mult::X1,
        },
        _ => Mult::X1,
    }
}

/// A CO's EXP after a battle (`BattleResults_Fill` and `_AwardExperience`): `taken` off first (not below 0; a CO
/// at 100000 or more loses nothing), then `gain` added.
pub fn award(exp: u32, taken: u32, gain: u32) -> u32 {
    let e = if exp < 100_000 { exp.saturating_sub(taken) } else { exp };
    (e + gain).min(crate::co_skills::MAX_EXP)
}

fn skills_on(core: &Core, army: u32) -> bool {
    (0..6).any(|k| core.raw_read_8(crate::co_skills::ACTIVE + 6 * (army - 1) + k, -1) != 0)
}

/// The mission's best score before this battle (campaigns; the record's Normal or Hard word), as points.
fn previous_best(core: &Core, hard: bool) -> u32 {
    let at = if crate::ds_campaign::active(core) {
        crate::ds_campaign::RECORDS + 8 * crate::ds_campaign::mission(core) as u32
    } else {
        let id = core.raw_read_8(MAP_ID, -1);
        if id < FIRST_CAMPAIGN_MAP {
            return 0;
        }
        AW2_CAMPAIGN_RECORDS + 8 * (id - FIRST_CAMPAIGN_MAP) as u32
    };
    let score = core.raw_read_32(at + 4 * hard as u32, -1) >> 20;
    // (the records keep the score; the points of a Hard battle are doubled)
    score * if hard { 2 } else { 1 }
}

/// `InsertBestScoreRecord(co, map, score r2, days)` at its entry, at every battle's end (before the results and
/// any record): the battle's points, each human army's COs' EXP, the History's battle counters
/// ([`crate::history::battle_over`]). Then the counts are cleared.
pub fn results(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    crate::ds_campaign::skills_loaded(core);
    let score = core.gba().cpu().gpr(2) as u32 & 0xFFF;
    let mode = core.raw_read_8(GAME_MODE, -1);
    let survival = crate::survival::on(core);
    let ds_session = crate::ds_campaign::active(core);
    let bonus = bonus(core);
    let mut total = score + bonus;
    if !player1_team_in(core) {
        total = 0;
    }
    let hard = mode == CAMPAIGN && hard(core);
    if hard {
        total *= 2;
    }
    if mode == VERSUS && !survival {
        total = 0;
    }
    let prev = if mode == CAMPAIGN {
        previous_best(core, hard).min(total)
    } else {
        0
    };
    core.raw_write_16(LAST_BONUS, -1, if total == 0 { 0 } else { bonus.min(0xFFFF) as u16 });
    // AW2's campaign plays as AW2's own (and saves nothing more) until the player has set skills for some CO.
    let aw2_campaign_plain = mode == CAMPAIGN && !ds_session && !crate::co_skills::any_set(core);
    if total > 0 && !survival && (mode == CAMPAIGN || mode == WAR_ROOM) && !aw2_campaign_plain {
        let early = !hard && {
            if ds_session {
                crate::ds_campaign::is_ds(core) && crate::ds_campaign::mission(core) < 8
            } else {
                core.raw_read_8(MAP_ID, -1).wrapping_sub(FIRST_CAMPAIGN_MAP) < 8
            }
        };
        for a in 1..=4u32 {
            if !human(core, a) {
                continue;
            }
            let front = core.raw_read_8(player(core, a) + P_CO, -1);
            let partner = crate::tag::partner(core, a);
            let m = mult(mode, early, partner.is_some(), skills_on(core, a));
            for co in std::iter::once(front).chain(partner) {
                let e = award(crate::co_skills::exp(core, co), scale(prev, m), scale(total, m));
                crate::co_skills::set_exp(core, co, e);
            }
        }
    }
    crate::history::battle_over(core, score, total, prev, survival, !aw2_campaign_plain);
    clear(core);
}

/// A Survival run is over (cleared, or lost): player 1's COs (its partner too) get the run's points, which hold
/// its bonus for what is left, at most 9999 (`Survival_AwardCoExperience`).
pub fn survival_run_over(core: &mut Core, points: u32) {
    if !is_on(core) || !human(core, 1) {
        return;
    }
    crate::ds_campaign::skills_loaded(core);
    let gain = points.min(9999);
    let front = core.raw_read_8(player(core, 1) + P_CO, -1);
    for co in std::iter::once(front).chain(crate::tag::partner(core, 1)) {
        let e = (crate::co_skills::exp(core, co) + gain).min(crate::co_skills::MAX_EXP);
        crate::co_skills::set_exp(core, co, e);
    }
    crate::history::co_ranks(core);
}

/// Every map start (crate::sandstorm's trap): a battle's first day, on its main front, starts with no counts.
pub fn map_start(core: &mut Core) {
    if is_on(core) && core.raw_read_16(DAY, -1) <= 1 && !crate::two_front::second_live(core) {
        clear(core);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scaling() {
        assert_eq!(scale(101, Mult::X1), 101);
        assert_eq!(scale(101, Mult::X1_5), 151);
        assert_eq!(scale(101, Mult::X2), 202);
        assert_eq!(scale(101, Mult::X2_5), 252);
    }

    #[test]
    fn multipliers() {
        assert_eq!(mult(CAMPAIGN, false, false, false), Mult::X2);
        assert_eq!(mult(CAMPAIGN, true, false, false), Mult::X1);
        assert_eq!(mult(CAMPAIGN, false, true, true), Mult::X1);
        assert_eq!(mult(WAR_ROOM, false, false, false), Mult::X2_5);
        assert_eq!(mult(WAR_ROOM, false, false, true), Mult::X2);
        assert_eq!(mult(WAR_ROOM, false, true, false), Mult::X1_5);
        assert_eq!(mult(WAR_ROOM, false, true, true), Mult::X1);
    }

    #[test]
    fn awards() {
        // A replay: the record's points off first, then the new points.
        assert_eq!(award(1000, 300, 350), 1050);
        assert_eq!(award(100, 300, 350), 350);
        assert_eq!(award(100_000, 300, 350), crate::co_skills::MAX_EXP);
    }

    #[test]
    fn ram_fits() {
        assert!(LAST_BONUS + 2 <= STATE + STATE_LEN);
    }
}
