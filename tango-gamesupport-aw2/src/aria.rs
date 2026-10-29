//! **Aria**: Nell's sister and Commander of the New Accord, tangoAW2's own Orange Star CO 93 (`crate::co_new::ARIA`; design `docs/dev/aria.md`, data `cos/aria.toml`, art `art/cos/aria/` from the
//! project owner's picture, imported by `aw2dev co portrait import`). The final opponent of the BH2 Campaign and Asuka's mirror.
//!
//! Her kit is two small rules, both her own:
//! - **Vengeance** (day to day, every level): a unit of hers with [`VENGEANCE_HP`] (8) HP or less (displayed HP, so 80 or less of the unit's 100) attacks AND defends harder, the more the lower its HP
//!   ([`VENGEANCE`]: +25% at 8, 6% more for each HP lost down to +61% at 2, then +85% at 1; 9 and 10 HP nothing; an Oozium never). [`vengeance`] is added to the battle's firepower in
//!   `com_tower::side_firepower` (like the other per-unit terms, so the forecast and the CPU's estimates agree) and to the defender's total defence in `co_roster::defence_total` (under AW2's 200 cap).
//! - **Build Anew** (Super Power, [`STARS`] 7 stars): every unit of hers recovers [`HEAL`] HP (`es_co::each_unit`: `RepairUnit(unit, 3, 0)`, for free) and attacks [`SCOP_ATTACK`]% harder (`stat`, on
//!   top of the power's own +10%). Nothing else: no defence, move or funds bonus.
//! - **No CO Power**, like AW2's Sturm and Dual Strike's Von Bolt: her CO row has 0 stars for it, so the map menu has no Power entry, the meter has one mark and the CO page says she has none. The computer
//!   plays her with Von Bolt's profile ([`AI_LIKE`]), a Super Power as soon as the meter allows.
//!
//! | | Day to day, Vengeance | Super Power, Build Anew (7 stars) |
//! |---|---|---|
//! | Attack | +7% for every unit, and +25% at 8 HP, +6% per HP lost to +61% at 2, +85% at 1 (not an Oozium) | +20% for every unit (and the power's own +10%) |
//! | Defence | +7% for every unit, and the same as attack by the unit's HP | the power's own +10% defence |
//! | HP | | +3 to every unit |
//! | Luck, movement | the game's own | |
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
/// Vengeance: displayed HP at or under which a unit attacks and defends harder, and by how much (percent, for attack and defence alike) at 1..8 displayed HP.
pub const VENGEANCE_HP: u8 = 8;
pub const VENGEANCE: [i32; 8] = [85, 61, 55, 49, 43, 37, 31, 25];
/// Her flat bonus: every unit of hers (not an Oozium: no CO changes one, `co_roster::stat`) attacks and defends this much harder (percent), at every HP and power level.
pub const FLAT: i32 = 7;
/// Build Anew: attack (percent) and HP healed.
pub const SCOP_ATTACK: i32 = 20;
pub const HEAL: u8 = 3;

/// Whether `co` is Aria.
pub fn is_aria(co: u8) -> bool {
    co == ARIA
}

/// Her own % for any unit type at power level `mode` (0 day to day, 1 CO Power (she has none), 2 Super Power), in `co_roster::stat`'s fields: [`FLAT`] firepower and defence always, Build Anew's
/// [`SCOP_ATTACK`] on top; nothing for move or range. (The power's own +10% firepower and defence are added by the caller.)
pub fn bonus(mode: u8, field: usize) -> i32 {
    match field {
        FIREPOWER => FLAT + if mode >= 2 { SCOP_ATTACK } else { 0 },
        crate::co_roster::DEFENCE => FLAT,
        _ => 0,
    }
}

/// Vengeance's firepower and defence % for a unit with `hp` (the unit record's 0..100 HP; displayed HP is its tenths rounded up): [`VENGEANCE`] at 1..8 displayed HP, 0 at 9 and 10 (and for a dead unit).
/// (An Oozium never has it: [`vengeance_for`].)
pub fn vengeance(hp: u8) -> i32 {
    let shown = (hp as usize + 9) / 10;
    if hp > 0 && shown <= VENGEANCE_HP as usize {
        VENGEANCE[shown - 1]
    } else {
        0
    }
}

/// Vengeance for a unit of type `t`: every unit but the Oozium.
pub fn vengeance_for(t: u8, hp: u8) -> i32 {
    if t == crate::roster::OOZIUM {
        0
    } else {
        vengeance(hp)
    }
}

/// The sign players read ([`crate::aria_sign`]): Vengeance's and her flat bonus together, for a unit of type `t` with `hp` (record HP) on the map or in the unit window: `Some((displayed HP, percent))` at 8 to 1
/// displayed HP (8 HP +32%, 7 +38% ... 2 +68%, 1 +92%), `None` at 9 and 10 HP, for a dead unit and for an Oozium.
pub fn sign(t: u8, hp: u8) -> Option<(u8, i32)> {
    let v = vengeance_for(t, hp);
    (v > 0).then(|| (((hp as u32 + 9) / 10) as u8, FLAT + v))
}

/// The HP number's colour on the map by displayed HP 8..1 (8-bit channels as the picture drawn for the owner, the game's palette holds each as 5 bits: `c >> 3`): orange at 8 HP, red at 4, dark red at 1.
pub const RAMP: [(u8, u8, u8); 8] = [
    (168, 0, 0),
    (200, 0, 0),
    (224, 16, 0),
    (240, 40, 0),
    (248, 72, 0),
    (248, 104, 0),
    (248, 136, 0),
    (248, 168, 0),
];

/// [`RAMP`] for displayed HP `shown` (1..8) as the GBA's colour word (RGB555).
pub fn ramp_colour(shown: u8) -> u16 {
    let (r, g, b) = RAMP[(shown as usize - 1).min(7)];
    (r as u16 >> 3) | ((g as u16 >> 3) << 5) | ((b as u16 >> 3) << 10)
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
        for t in [MOVE, crate::co_roster::RANGE] {
            assert_eq!([0, 1, 2].map(|m| bonus(m, t)), [0, 0, 0]);
        }
        assert_eq!([0, 1, 2].map(|m| bonus(m, DEFENCE)), [7, 7, 7], "a flat 7% defence");
        assert_eq!([0, 1, 2].map(|m| bonus(m, FIREPOWER)), [7, 7, 27], "a flat 7% attack, Build Anew's 20% on top");
        assert!(crate::co_new::is_new(ARIA) && crate::co_new::is_own(ARIA) && !crate::es_co::is_es(ARIA));
        assert!(crate::co_new::listed(ARIA), "in every Versus list");
        assert_eq!(crate::co_new::like(ARIA), LIKE);
        assert_eq!(crate::co_roster::ds_co(ARIA), None, "her numbers are her own: no Dual Strike block");
    }

    #[test]
    fn vengeance_is_eight_displayed_hp_or_less() {
        // displayed HP is the unit's HP in tenths, rounded up: 71..80 show 8, 81..90 show 9
        assert_eq!([100, 91, 90, 81].map(vengeance), [0, 0, 0, 0], "9 and 10 HP: nothing");
        assert_eq!([80, 70, 60, 50, 40, 30, 20, 10].map(vengeance), [25, 31, 37, 43, 49, 55, 61, 85], "8 HP down to 1");
        assert_eq!([71, 61, 51, 41, 31, 21, 11, 1].map(vengeance), [25, 31, 37, 43, 49, 55, 61, 85], "the same displayed HP");
        assert_eq!(vengeance(0), 0, "a dead unit");
        assert_eq!(vengeance_for(crate::roster::OOZIUM, 10), 0, "an Oozium never");
        assert_eq!(vengeance_for(4, 10), 85);
    }

    #[test]
    fn the_sign_is_the_flat_bonus_and_vengeance() {
        let shown = |hp: u8| sign(4, hp).map(|(_, p)| p);
        assert_eq!([100, 90, 81].map(shown), [None, None, None], "9 and 10 HP show nothing");
        assert_eq!([80, 70, 60, 50, 40, 30, 20, 10].map(shown), [32, 38, 44, 50, 56, 62, 68, 92].map(Some));
        assert_eq!(sign(4, 71), Some((8, 32)));
        assert_eq!(sign(crate::roster::OOZIUM, 10), None, "never an Oozium");
        assert_eq!(sign(4, 0), None);
        assert_eq!(ramp_colour(8), 31 | (21 << 5), "orange at 8 HP");
        assert_eq!(ramp_colour(1), 21, "dark red at 1 HP");
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
