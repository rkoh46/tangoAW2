//! The Gauntlet selector's hint for a two-map run ("Iron Crown *"): what the star means (pressing SELECT on the row flips the picture and the faces to the run's second map,
//! [`crate::gauntlet_ui`]). DESIGN SWITCH, not final: `TANGOAW2_STAR_HINT=1|2|3` picks a variant of option A (unset: no hint); the chosen one stays, the others are deleted.
//!
//! Drawn with AW2's own pieces ([`crate::online`]'s `Rgba`): the pink plate of SELECT MAP's boxes (black edge, red frame, pink page) or the game's white window (the Teams screen help plate's), and the
//! text font the map list's names use. Shown only while the cursor is on a two-map row, in the band between the picture (ends at y 127) and the faces (start at y 144).

use crate::gauntlet_mode::Entry;
use crate::online::{self, Rgba, PLATE_GREY, PLATE_INK};
use mgba::core::Core;

/// The variant chosen with `TANGOAW2_STAR_HINT` (1, 2 or 3), if any.
pub fn option() -> Option<u8> {
    static O: std::sync::OnceLock<Option<u8>> = std::sync::OnceLock::new();
    *O.get_or_init(|| std::env::var("TANGOAW2_STAR_HINT").ok().and_then(|v| v.parse().ok()).filter(|c| (1..=3).contains(c)))
}

/// What the key does now: "2nd map" while the first shows, "1st map" on the last of the run's maps (or "3rd map" for a longer run).
fn next_map(stage: usize, maps: usize) -> String {
    let n = (stage + 1) % maps + 1;
    format!("{n}{} map", ["st", "nd", "rd", "th"][(n - 1).min(3)])
}

/// The hint of variant `opt` for entry `e` with map `stage` (0 the first) showing; nothing for a one-map run.
pub fn paint(core: &Core, rgba: &mut [u8], opt: u8, e: &Entry, stage: usize) {
    if e.stage_titles.is_empty() {
        return;
    }
    let s = format!("SELECT: {}", next_map(stage, 1 + e.stage_titles.len()));
    let w = online::text_width(core, &s);
    let cv = &mut Rgba(rgba);
    match opt {
        // 1: a pink plate under the picture.
        1 => {
            let (x, y, h) = (108, 129, 14);
            cv.plate(x, y, w + 10, h);
            cv.text(core, x + 5, y + 1, &s, PLATE_INK, PLATE_GREY);
        }
        // 2: the white window of the Teams screen's help plate.
        2 => {
            let (x, y, h) = (108, 129, 14);
            cv.window(x, y, w + 10, h);
            cv.text(core, x + 5, y + 1, &s, online::INK, online::GRAY_INK);
        }
        // 3: a pink tab hanging from the picture's frame (as "R RECORD" hangs from the list's), its top edge the picture's bottom.
        _ => {
            let (x, y, h) = (107, 128, 14);
            cv.plate(x, y, w + 10, h);
            cv.text(core, x + 5, y + 2, &s, PLATE_INK, PLATE_GREY);
        }
    }
}
