//! **Asuka**: Sonja after she defects to Black Hole (Japanese name: Asuka), tangoAW2's own CO 92 (`crate::co_new::ASUKA`; design and numbers `docs/dev/asuka.md`, data `cos/asuka.toml`, art
//! `art/cos/asuka/` from the project owner's picture, imported by `aw2dev co portrait import`).
//!
//! She is built from pieces that already run in the game:
//! - **Sonja's Dual Strike block** ([`SONJA_DS`], `co_roster::ds_co`): vision +1 / +2 / +2 in fog, her HP hidden from the enemy (Dual Strike's skill 0x01; the strike-first skill 0x04 and the
//!   sees-into-hiding-places skill 0x08 in her powers), the enemy's terrain stars cut by 1 / 2 / 3, luck 10 with bad luck 5, the power meter's usual +10% firepower in a power.
//!   Her **luck is Nell's** (maximum roll 20 in every level, no bad luck: the user's choice, replacing Sonja's quirk) and her **movement Sturm's**: every terrain costs 1 for ground units (his row's charts).
//! - **Her own day to day**: all her units attack and defend [`DAY_BONUS`]% better (`co_roster::stat`), in every power too.
//! - **Hawke's Black Wave and Black Storm** (AW2's own mass-HP procedure `sub_08044D70`, called by her own two power functions in `co_powers::asuka_fn`): her units regain 1 (2) HP, the enemy's
//!   lose 1 (2) HP, never below 1 HP; the sparkle and the cut-in are Hawke's (his presentation row is her template, [`LIKE`]).
//! - **Drake's halving, extended**: the same procedure's fuel flag (Drake's Tsunami and Typhoon) halves every enemy unit's fuel, rounded down, and `co_powers::mass_unit` halves every enemy unit's
//!   ammo the same way (a unit with no ammo stat has 0 and is unaffected). Not Drake's rain.
//! - **Sonja's art** (the project owner's decision): her presentation row's pictures, palette, expressions and HUD face are AW2's Sonja row; only her name graphic is hers. Her HQ is Black Hole's
//!   (her row's property style, as Hawke's and Lash's: the HQ follows the CO, not the colour slot).
//!
//! | | Day to day | CO Power, Dark Intel (3 stars) | Super Power, Event Horizon (9 stars in all) |
//! |---|---|---|---|
//! | Attack / defence | +5% / +5% | +5% / +5% | +5% / +5% |
//! | Vision | +1 | +2, sees into woods and reefs | +2, sees into hiding places |
//! | Terrain stars the enemy loses | 1 | 2 | 3 |
//! | HP | hidden from the enemy | own units +1 HP, enemy units -1 HP | own +2, enemy -2; strikes first when attacked |
//! | Enemy ammo and fuel | | halved | halved |
//! | Luck | 0..19% | 0..19% | 0..19% |
//! | Movement | every terrain costs 1 | same | same |
//! | Firepower | 0 | +10% (every power) | +10% |
//!
//! Stars: Eagle's, 3 / 9 (Sonja 3/5, Hawke 5/9). Not in the Emerald Sun Campaign (`aw2dev campaign check`) and reserved for the BH2 Campaign.

use crate::co_new::ASUKA;

/// Sonja's Dual Strike CO id: her block of numbers is Asuka's.
pub const SONJA_DS: u8 = 8;
/// AW2's Hawke (row 14): her presentation template (Black Hole's music, cut-in, the sparkle, the CPU's profile and her place in the lists) and the power procedures she borrows.
pub const LIKE: u8 = 14;
/// Stars of her CO Power and of her Super Power in all.
pub const STARS: (u32, u32) = (3, 9);
/// AW2's Sturm (row 10): her movement charts are his (every terrain costs 1 for ground units).
pub const MOVE_LIKE: u8 = 10;
/// Nell's day-to-day maximum luck roll (AW2's table: 20; her powers raise it to 60 and 100, Asuka's keep 20), no bad luck.
pub const LUCK: i16 = 20;
/// Her day to day: all her units attack and defend this much better (percent), in every power too.
pub const DAY_BONUS: i32 = 5;
/// Her CO Power's and Super Power's HP effect on her own units and on the enemy's (Hawke's Black Wave 1, Black Storm 2).
pub const HP_OWN: [i32; 3] = [0, 1, 2];
pub const HP_ENEMY: [i32; 3] = [0, 1, 2];

/// Whether `co` is Asuka.
pub fn is_asuka(co: u8) -> bool {
    co == ASUKA
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn she_is_between_sonja_and_hawke() {
        assert_eq!(STARS, (3, 9), "Eagle's meter (AW2's and Dual Strike's table): her powers are stronger than Sonja's 3/5 and Hawke's 5/9 together would be");
        assert_eq!(DAY_BONUS, 5);
        assert_eq!(ASUKA, 92);
        assert!((ASUKA as u32) < crate::co_roster::ROOM);
        assert_eq!(crate::co_roster::ds_co(ASUKA), Some(SONJA_DS));
        assert!(crate::co_new::is_new(ASUKA) && crate::co_new::is_own(ASUKA) && !crate::es_co::is_es(ASUKA));
        assert!(
            crate::co_new::listed(ASUKA),
            "in every Versus list, not behind the playtest flag"
        );
        assert_eq!(crate::co_new::like(ASUKA), 14);
    }

    #[test]
    fn her_texts_fit_the_game() {
        use crate::co_new::*;
        for w in [
            T_NAME,
            T_BIO,
            T_D2D,
            T_COP,
            T_SCOP,
            T_COP_NAME,
            T_SCOP_NAME,
            T_VICTORY,
            T_DEFEAT,
        ] {
            assert!(crate::es_cos::text(ASUKA, w).is_some(), "text slot {w}");
        }
        for q in 0..6 {
            let t = String::from_utf8(crate::es_cos::text(ASUKA, T_QUOTES + q).unwrap()).unwrap();
            assert!(
                t.split('\r').count() <= 2 && t.split('\r').all(|l| l.len() <= 26),
                "{t:?}"
            );
        }
        assert_eq!(crate::es_cos::name(ASUKA), Some(b"Asuka".to_vec()));
        assert!(
            0x0861_0A38 + 4 * (text_id(ASUKA, 16) as u32) <= 0x0863_0000,
            "her text slots stay inside the table's free ROM"
        );
    }
}
