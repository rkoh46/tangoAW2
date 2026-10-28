//! **Aria**: Nell's sister and Commander of the New Accord, tangoAW2's own Orange Star CO 93 (`crate::co_new::ARIA`; design `docs/dev/aria.md`, data `cos/aria.toml`, art `art/cos/aria/` from the
//! project owner's picture, imported by `aw2dev co portrait import`). The final opponent of the BH2 Campaign and Asuka's mirror.
//!
//! She is built from pieces that already run in the game, and her own numbers are [`bonus`]:
//! - **Common Cause** (day to day): all her units attack [`DAY_ATTACK`]% harder and take [`DAY_DEFENCE`]% less damage (`co_roster::stat`, in every power too); her luck is **Nell's** (maximum roll 20, no bad
//!   luck) and her movement **Sturm's** (every terrain costs 1 for ground units), both exactly as Asuka's Black Insight does it (`co_roster::build`: `asuka::LUCK`, `asuka::MOVE_LIKE`).
//! - **No CO Power**, like AW2's Sturm and Dual Strike's Von Bolt: her CO row has 0 stars for it, so the map menu has no Power entry, the meter has one mark and the CO page says she has none. The computer
//!   plays her with Von Bolt's profile ([`AI_LIKE`]), a Super Power as soon as the meter allows.
//! - **Build Anew** (Super Power, [`STARS`] 7): every unit of hers recovers [`HEAL`] HP (`es_co::each_unit`: `RepairUnit(unit, 3, 0)`, for free), attacks [`SCOP_ATTACK`]% harder, takes [`SCOP_DEFENCE`]% less
//!   damage and moves [`SCOP_MOVE`] space more (on top of the power's own +10% firepower and defence), and she is paid **one day's income at once**: [`income_grant`], the Funds rule's value for a
//!   property times the properties that earn (the same count and value as the day's income), added to her funds when the power is paid for (`power_paid`, the trap on `PayForPower`). With a day's
//!   income of 0 (a mode that pays none) the grant is 0.
//!
//! | | Day to day, Common Cause | Super Power, Build Anew (7 stars) |
//! |---|---|---|
//! | Attack / defence | +3% / +10% | +3% + 20% / +10% + 30% (and the power's own +10% / +10%) |
//! | Move | Sturm's: every terrain costs 1 | +1 |
//! | HP | | +3 to every unit |
//! | Funds | | one day's income, once |
//! | Luck | 0..19% (Nell's), no bad luck | same |
//!
//! Stars: no CO Power, Super Power 7 (63000 meter points at 9000 a star). Not in the Emerald Sun Campaign and reserved for the BH2 Campaign (M25).

use mgba::core::Core;

use crate::co_new::ARIA;
use crate::co_roster::{DEFENCE, FIREPOWER, MOVE};

/// AW2's Nell (row 0): her presentation template (the Teams list's and the War Room's place, the CPU's settings except the power's) and her sister.
pub const LIKE: u8 = 0;
/// Dual Strike's Von Bolt: the computer plays her with his profile (a Super Power only).
pub const AI_LIKE: u8 = 11;
/// AW2's Sturm (row 10): his CPU power settings fit a CO with no CO Power; her movement charts are Asuka's, his (`asuka::MOVE_LIKE`).
pub const NO_COP_LIKE: u8 = 10;
/// Stars of her CO Power (none) and of her Super Power in all.
pub const STARS: (u32, u32) = (0, 7);
/// Her day to day: all her units attack and defend this much better (percent), in every power too.
pub const DAY_ATTACK: i32 = 3;
pub const DAY_DEFENCE: i32 = 10;
/// Build Anew, on top: attack and defence (percent), move, HP healed.
pub const SCOP_ATTACK: i32 = 20;
pub const SCOP_DEFENCE: i32 = 30;
pub const SCOP_MOVE: i32 = 1;
pub const HEAL: u8 = 3;

/// Whether `co` is Aria.
pub fn is_aria(co: u8) -> bool {
    co == ARIA
}

/// Her own firepower %, defence %, move and range for any unit type at power level `mode` (0 day to day, 1 CO Power (she has none), 2 Super Power), in `co_roster::stat`'s fields (the power's own
/// +10% firepower is added by the caller).
pub fn bonus(mode: u8, field: usize) -> i32 {
    let scop = mode >= 2;
    let on = |v: i32| if scop { v } else { 0 };
    match field {
        FIREPOWER => DAY_ATTACK + on(SCOP_ATTACK),
        DEFENCE => DAY_DEFENCE + on(SCOP_DEFENCE),
        MOVE => on(SCOP_MOVE),
        _ => 0,
    }
}

/// Build Anew's funds: one day's income, the Funds rule's value for a property (`per_property`, 1000 by default, 0 when a mode pays no income) times the properties that earn.
pub fn income_grant(earners: i32, per_property: i32) -> i32 {
    per_property.max(0) * earners.max(0)
}

/// `PayForPower(army, mode)`'s entry (the map menu's Super Power, the computer's choice): when the army's CO is Aria and the power is her Super Power, one day's income is added to her funds at once.
pub fn power_paid(core: &mut Core) {
    use crate::co_roster::army_co;
    if !crate::ds_weather::is_on(core) {
        return;
    }
    let mode = core.gba().cpu().gpr(1) as u8;
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if mode != 2 || !(1..=5).contains(&army) || army_co(core, army).0 != ARIA {
        return;
    }
    let grant = income_grant(
        crate::co_powers::earners(core, army),
        core.raw_read_32(FUNDS_PER_PROPERTY, -1) as i32,
    );
    if grant == 0 {
        return;
    }
    let p = crate::five::players(core) + PLAYER * army;
    let funds = core.raw_read_32(p, -1) as i64 + grant as i64;
    core.raw_write_32(p, -1, funds.clamp(0, 999_999) as u32);
}

const CURRENT_ARMY: u32 = 0x0300_33EC;
const PLAYER: u32 = 0x3C;
/// gPlaySt's funds per property (the Rules screen's Funds; `co_powers::income` reads the same word).
const FUNDS_PER_PROPERTY: u32 = 0x0300_3FE8;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn her_numbers() {
        assert_eq!(ARIA, 93);
        assert!((ARIA as u32) < crate::co_roster::ROOM);
        assert_eq!(STARS, (0, 7), "no CO Power, a Super Power of 7 stars");
        for t in [FIREPOWER, DEFENCE, MOVE] {
            assert_eq!(bonus(1, t), bonus(0, t), "no CO Power: level 1 is never entered");
        }
        assert_eq!((bonus(0, FIREPOWER), bonus(0, DEFENCE), bonus(0, MOVE)), (3, 10, 0));
        assert_eq!((bonus(2, FIREPOWER), bonus(2, DEFENCE), bonus(2, MOVE)), (23, 40, 1));
        assert_eq!(bonus(2, crate::co_roster::RANGE), 0);
        assert!(crate::co_new::is_new(ARIA) && crate::co_new::is_own(ARIA) && !crate::es_co::is_es(ARIA));
        assert!(crate::co_new::listed(ARIA), "in every Versus list");
        assert_eq!(crate::co_new::like(ARIA), LIKE);
        assert_eq!(crate::co_roster::ds_co(ARIA), None, "her numbers are her own: no Dual Strike block");
    }

    #[test]
    fn a_days_income() {
        assert_eq!(income_grant(12, 1000), 12_000);
        assert_eq!(income_grant(12, 2000), 24_000, "the Funds rule's value");
        assert_eq!(income_grant(12, 0), 0, "a mode that pays no income");
        assert_eq!(income_grant(0, 1000), 0);
    }

    #[test]
    fn her_texts_fit_the_game() {
        use crate::co_new::*;
        for w in [T_NAME, T_BIO, T_D2D, T_COP, T_SCOP, T_COP_NAME, T_SCOP_NAME, T_VICTORY, T_DEFEAT] {
            assert!(crate::es_cos::text(ARIA, w).is_some(), "text slot {w}");
        }
        for q in 0..6 {
            let t = String::from_utf8(crate::es_cos::text(ARIA, T_QUOTES + q).unwrap()).unwrap();
            assert!(t.split('\r').count() <= 2 && t.split('\r').all(|l| l.len() <= 26), "{t:?}");
        }
        assert_eq!(crate::es_cos::name(ARIA), Some(b"Aria".to_vec()));
        assert!(
            0x0861_0A38 + 4 * (text_id(ARIA, 16) as u32) <= 0x0863_0000,
            "her text slots stay inside the table's free ROM"
        );
    }
}
