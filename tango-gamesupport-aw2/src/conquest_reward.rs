//! Conquest Run's reward page (docs/dev/conquest.md "The reward"): after a map is won, over the map just won, before the next map's fade, the player takes one of three rewards: the war chest, a free
//! unit of three offered, or the field repair. Drawn over the finished frame with AW2's own pieces ([`crate::online`]'s `Rgba`: the white window with its red and blue edges that every AW2 box
//! has, the pink plate of SELECT MAP's boxes, AW2's font), the way the army screen and the star hint are; the logic and the pad are [`crate::conquest`]'s (`tick`).

use mgba::core::Core;

use crate::conquest as cq;
use crate::custom_campaign::unit;
use crate::online::{self, Rgba, GRAY_INK, INK, PLATE_GREY, PLATE_INK, YELLOW};

/// A card: its window's size and where the three stand.
const CARD_W: i32 = 70;
const CARD_H: i32 = 76;
const CARD_Y: i32 = 30;
const CARD_X: [i32; 3] = [8, 85, 162];
/// The banner over the cards and the help plate under them.
const BANNER: (i32, i32, i32, i32) = (8, 5, 224, 17);
const PLATE: (i32, i32, i32, i32) = (8, 114, 224, 40);
/// The widest a line may be inside a card (its window less the margins).
const CARD_TEXT: i32 = CARD_W - 10;

/// What a reward page says of each reward after map `k`: (heading, lines).
fn rewards(k: u8) -> [(String, Vec<String>); 3] {
    [
        (
            "War chest".to_string(),
            vec![
                format!("+{}", cq::chest_funds(k)),
                "funds for the".to_string(),
                "next map".to_string(),
            ],
        ),
        (
            "Reinforce".to_string(),
            vec![
                "One free unit,".to_string(),
                "your pick of".to_string(),
                "three".to_string(),
            ],
        ),
        (
            "Field repair".to_string(),
            vec![
                "Every unit to".to_string(),
                "10 HP, with".to_string(),
                "full fuel".to_string(),
                "and ammo".to_string(),
            ],
        ),
    ]
}

/// AW2's name for a unit type.
pub fn unit_name(kind: u8) -> &'static str {
    match kind {
        unit::INFANTRY => "Infantry",
        unit::MECH => "Mech",
        unit::MD_TANK => "Md Tank",
        unit::MEGATANK => "Megatank",
        unit::TANK => "Tank",
        unit::RECON => "Recon",
        unit::APC => "APC",
        unit::NEOTANK => "Neotank",
        unit::ARTILLERY => "Artillery",
        unit::ROCKETS => "Rockets",
        unit::ANTI_AIR => "Anti-Air",
        unit::MISSILES => "Missiles",
        unit::FIGHTER => "Fighter",
        unit::BOMBER => "Bomber",
        unit::B_COPTER => "B Copter",
        unit::T_COPTER => "T Copter",
        _ => "Unit",
    }
}

/// What a unit card says: its funds cost and its kind of ground.
fn unit_lines(core: &Core, kind: u8) -> Vec<String> {
    let cost = core.raw_read_16(crate::roster::table(core) + 0x5C * kind as u32 + 6, -1) as u32 * 10;
    let domain = match kind {
        unit::FIGHTER | unit::BOMBER | unit::B_COPTER | unit::T_COPTER => "Air unit",
        unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => "Indirect fire",
        _ => "Ground unit",
    };
    vec![domain.to_string(), "Costs".to_string(), format!("{cost}")]
}

/// A card at slot `slot`: the window (the chosen one has a yellow edge round it), the heading and the lines.
fn card(core: &Core, cv: &mut Rgba<'_>, slot: usize, chosen: bool, heading: &str, lines: &[String]) {
    let x = CARD_X[slot];
    if chosen {
        cv.rect(x - 3, CARD_Y - 3, CARD_W + 6, CARD_H + 6, YELLOW);
    }
    cv.window(x, CARD_Y, CARD_W, CARD_H);
    cv.text(core, x + 5, CARD_Y + 6, heading, INK, GRAY_INK);
    cv.rect(x + 4, CARD_Y + 20, CARD_W - 8, 1, GRAY_INK);
    for (i, l) in lines.iter().enumerate() {
        cv.text(core, x + 5, CARD_Y + 26 + 12 * i as i32, l, INK, GRAY_INK);
    }
}

/// The text centred in a box.
fn centred(
    core: &Core,
    cv: &mut Rgba<'_>,
    b: (i32, i32, i32, i32),
    y: i32,
    s: &str,
    ink: online::Rgb,
    shade: online::Rgb,
) {
    let w = online::text_width(core, s);
    cv.text(core, b.0 + (b.2 - w) / 2, y, s, ink, shade);
}

/// The reward page over the finished frame; `true` when one is up.
pub fn draw(core: &Core, rgba: &mut [u8]) -> bool {
    if rgba.len() != online::W * online::H * 4 || cq::page(core) == 0 || !cq::session(core) {
        return false;
    }
    paint(
        core,
        rgba,
        cq::won_map(core),
        cq::page(core),
        cq::cursor(core) as usize % 3,
        cq::offer(core),
    );
    true
}

/// The page for map `k` just won: `page` 1 (the rewards) or 2 (the units `offer`), the card under `cursor` marked. Also the text audit's page (`aw2dev audit text`).
pub fn paint(core: &Core, rgba: &mut [u8], k: u8, page: u8, cursor: usize, offer: [u8; 3]) {
    let cv = &mut Rgba(rgba);
    // (the banner: the map cleared and what to do)
    cv.window(BANNER.0, BANNER.1, BANNER.2, BANNER.3);
    let name = cq::MAPS.get(k as usize).map_or("Map", |m| m.name);
    let title = if page == 1 {
        format!("{name} cleared: choose a reward")
    } else {
        "Choose a free unit".to_string()
    };
    centred(core, cv, BANNER, BANNER.1 + 3, &title, INK, GRAY_INK);
    let help;
    if page == 1 {
        let r = rewards(k);
        for (slot, (heading, lines)) in r.iter().enumerate() {
            card(core, cv, slot, slot == cursor, heading, lines);
        }
        help = [
            [
                "Take funds to build with on the next map.",
                "Take a free unit from three offered.",
                "Heal and refill every unit you keep.",
            ][cursor],
            "Left Right: Choose  A: Take",
        ];
    } else {
        for (slot, kind) in offer.into_iter().enumerate() {
            card(core, cv, slot, slot == cursor, unit_name(kind), &unit_lines(core, kind));
        }
        help = ["It joins you at full strength.", "Left Right: Choose  A: Take  B: Back"];
    }
    cv.plate(PLATE.0, PLATE.1, PLATE.2, PLATE.3);
    cv.text(core, PLATE.0 + 8, PLATE.1 + 8, help[0], PLATE_INK, PLATE_GREY);
    cv.text(core, PLATE.0 + 8, PLATE.1 + 22, help[1], PLATE_INK, PLATE_GREY);
    debug_assert!(CARD_TEXT > 0);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_cards_and_plates_lie_inside_the_screen_and_do_not_overlap() {
        for x in CARD_X {
            assert!(x - 3 >= 0 && x + CARD_W + 3 <= online::W as i32);
        }
        assert!(CARD_X[0] + CARD_W + 3 < CARD_X[1] - 3 && CARD_X[1] + CARD_W + 3 < CARD_X[2] - 3);
        assert!(BANNER.1 + BANNER.3 < CARD_Y - 3);
        assert!(CARD_Y + CARD_H + 3 < PLATE.1);
        assert!(PLATE.1 + PLATE.3 <= online::H as i32);
    }

    #[test]
    fn every_offered_unit_has_a_name() {
        for k in 0..4 {
            for u in cq::offered(k) {
                assert_ne!(unit_name(u), "Unit", "kind {u}");
            }
        }
    }
}
