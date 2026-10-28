//! **Aria**: Nell's sister and Commander of the New Accord, tangoAW2's own Orange Star CO 93 (`crate::co_new::ARIA`; design `docs/dev/aria.md`, data `cos/aria.toml`, art `art/cos/aria/` from the
//! project owner's picture, imported by `aw2dev co portrait import`). The final opponent of the BH2 Campaign and Asuka's mirror.
//!
//! Her kit is two small rules, both her own:
//! - **Vengeance** (day to day, every level): a unit of hers with [`VENGEANCE_HP`] HP or less (displayed HP, so 50 or less of the unit's 100) attacks [`VENGEANCE_ATTACK`]% harder ([`vengeance`], added in
//!   `com_tower::side_firepower` to the battle's base damage like the other per-unit firepower terms, so the forecast and the CPU's estimates agree).
//! - **Build Anew** (Super Power, [`STARS`] 7 stars): every unit of hers recovers [`HEAL`] HP (`es_co::each_unit`: `RepairUnit(unit, 3, 0)`, for free) and attacks [`SCOP_ATTACK`]% harder (`stat`, on
//!   top of the power's own +10%). Nothing else: no defence, move or funds bonus.
//! - **No CO Power**, like AW2's Sturm and Dual Strike's Von Bolt: her CO row has 0 stars for it, so the map menu has no Power entry, the meter has one mark and the CO page says she has none. The computer
//!   plays her with Von Bolt's profile ([`AI_LIKE`]), a Super Power as soon as the meter allows.
//!
//! | | Day to day, Vengeance | Super Power, Build Anew (7 stars) |
//! |---|---|---|
//! | Attack | +20% for a unit on 5 HP or less | +20% for every unit (and the power's own +10%) |
//! | HP | | +3 to every unit |
//! | Luck, movement, defence | the game's own | the power's own +10% defence |
//!
//! Stars: no CO Power, Super Power 7 (63000 meter points at 9000 a star). Not in the Emerald Sun Campaign and reserved for the BH2 Campaign (M25).

use crate::co_new::ARIA;
use crate::co_roster::FIREPOWER;

/// AW2's Nell (row 0): her presentation template (the Teams list's and the War Room's place, the CPU's settings except the power's) and her sister.
pub const LIKE: u8 = 0;
/// Dual Strike's Von Bolt: the computer plays her with his profile (a Super Power only).
pub const AI_LIKE: u8 = 11;
/// AW2's Sturm (row 10): his CPU power settings fit a CO with no CO Power.
pub const NO_COP_LIKE: u8 = 10;
/// Stars of her CO Power (none) and of her Super Power in all.
pub const STARS: (u32, u32) = (0, 7);
/// Vengeance: displayed HP at or under which a unit attacks harder, and by how much (percent).
pub const VENGEANCE_HP: u8 = 5;
pub const VENGEANCE_ATTACK: i32 = 20;
/// Build Anew: attack (percent) and HP healed.
pub const SCOP_ATTACK: i32 = 20;
pub const HEAL: u8 = 3;

/// Whether `co` is Aria.
pub fn is_aria(co: u8) -> bool {
    co == ARIA
}

/// Her own firepower % for any unit type at power level `mode` (0 day to day, 1 CO Power (she has none), 2 Super Power), in `co_roster::stat`'s fields; nothing for defence, move or range. (The power's own
/// +10% firepower is added by the caller.)
pub fn bonus(mode: u8, field: usize) -> i32 {
    if field == FIREPOWER && mode >= 2 {
        SCOP_ATTACK
    } else {
        0
    }
}

/// Vengeance's firepower % for a unit with `hp` (the unit record's 0..100 HP): 20 at 5 displayed HP or less, else 0.
pub fn vengeance(hp: u8) -> i32 {
    let shown = (hp as u32 + 9) / 10;
    if hp > 0 && shown <= VENGEANCE_HP as u32 {
        VENGEANCE_ATTACK
    } else {
        0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::co_roster::{DEFENCE, MOVE};

    #[test]
    fn her_numbers() {
        assert_eq!(ARIA, 93);
        assert!((ARIA as u32) < crate::co_roster::ROOM);
        assert_eq!(STARS, (0, 7), "no CO Power, a Super Power of 7 stars");
        for t in [DEFENCE, MOVE, crate::co_roster::RANGE] {
            assert_eq!([0, 1, 2].map(|m| bonus(m, t)), [0, 0, 0]);
        }
        assert_eq!([0, 1, 2].map(|m| bonus(m, FIREPOWER)), [0, 0, 20]);
        assert!(crate::co_new::is_new(ARIA) && crate::co_new::is_own(ARIA) && !crate::es_co::is_es(ARIA));
        assert!(crate::co_new::listed(ARIA), "in every Versus list");
        assert_eq!(crate::co_new::like(ARIA), LIKE);
        assert_eq!(crate::co_roster::ds_co(ARIA), None, "her numbers are her own: no Dual Strike block");
    }

    #[test]
    fn vengeance_is_five_displayed_hp_or_less() {
        // displayed HP is the unit's HP in tenths, rounded up: 41..50 show 5, 51..60 show 6
        assert_eq!([100, 60, 51, 50, 41, 40, 10, 1].map(vengeance), [0, 0, 0, 20, 20, 20, 20, 20]);
        assert_eq!(vengeance(0), 0, "a dead unit");
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
