//! The Gauntlet selector's hint for a two-map run ("Iron Crown *"): what the star means. Pressing SELECT on the row flips the picture and the faces to the run's second map ([`crate::gauntlet_ui`]),
//! and the hint says so: "SELECT: 2nd map" under the picture (it reads "SELECT: 1st map" while the second map shows).
//!
//! Drawn with AW2's own pieces ([`crate::online`]'s `Rgba`): the white window of the Teams screen's help plate (red above, blue below) and the text font the map list's names use, in the band
//! between the picture (it ends at y 127) and the faces (they start at y 144). Shown only while the cursor is on a two-map row.

use crate::gauntlet_mode::Entry;
use crate::online::{self, Rgba};
use mgba::core::Core;

/// The window's left edge, top edge and height (its width follows the text).
pub const X: i32 = 108;
pub const Y: i32 = 129;
pub const HEIGHT: i32 = 14;

/// What the key does now: "2nd map" while the first shows, "1st map" on the last of the run's maps (or the next number on a longer run).
fn next_map(stage: usize, maps: usize) -> String {
    let n = (stage + 1) % maps + 1;
    format!("{n}{} map", ["st", "nd", "rd", "th"][(n - 1).min(3)])
}

/// The hint for entry `e` with map `stage` (0 the first) showing; nothing for a one-map run.
pub fn paint(core: &Core, rgba: &mut [u8], e: &Entry, stage: usize) {
    if e.stage_titles.is_empty() {
        return;
    }
    let s = format!("SELECT: {}", next_map(stage, 1 + e.stage_titles.len()));
    let cv = &mut Rgba(rgba);
    cv.window(X, Y, online::text_width(core, &s) + 10, HEIGHT);
    cv.text(core, X + 5, Y + 1, &s, online::INK, online::GRAY_INK);
}
