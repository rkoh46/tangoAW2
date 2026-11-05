//! The Gauntlet selector's hint for a two-map run ("Iron Crown *"): three design options for telling the player what the star means (pressing SELECT on the row flips the picture and the faces to the
//! run's second map, [`crate::gauntlet_ui`]). DESIGN SWITCH, not final: `TANGOAW2_STAR_HINT=a|b|c` picks an option (unset: no hint). The chosen option stays, the others are deleted.
//!
//! The pieces are the button-prompt plates of the War Room's own screen: the pink letters on a dark green plate of "RECORD" ([`label`]) and the white letters on dark green of the "ENEMY" label ([`key`]); the letters are the plate's own (5 x 6, its R E C O D are copied from the screen), the rest drawn on the same grid. Shown only while the cursor is on a two-map row.

use crate::gauntlet_mode::Entry;
use crate::online::{Rgb, Rgba};

/// The plate's colours, as the screen's "R RECORD" plate has them.
const GREEN: Rgb = (0, 41, 0);
const PINK: Rgb = (255, 172, 172);
const WHITE: Rgb = (255, 255, 255);

/// The option chosen with `TANGOAW2_STAR_HINT` (lower case letter), if any.
pub fn option() -> Option<char> {
    static O: std::sync::OnceLock<Option<char>> = std::sync::OnceLock::new();
    *O.get_or_init(|| std::env::var("TANGOAW2_STAR_HINT").ok().and_then(|v| v.chars().next()).map(|c| c.to_ascii_lowercase()).filter(|c| matches!(c, 'a' | 'b' | 'c')))
}

/// A letter of the plate's face: 6 rows of 5 columns (`#` set).
fn glyph(c: char) -> [&'static str; 6] {
    match c {
        'A' => [".###.", "##.##", "##.##", "#####", "##.##", "##.##"],
        'C' => [".###.", "##.##", "##...", "##...", "##.##", ".###."],
        'D' => ["####.", "##.##", "##.##", "##.##", "##.##", "####."],
        'E' => ["#####", "##...", "####.", "##...", "##...", "#####"],
        'F' => ["#####", "##...", "####.", "##...", "##...", "##..."],
        'L' => ["##...", "##...", "##...", "##...", "##...", "#####"],
        'M' => ["##.##", "#####", "#####", "##.##", "##.##", "##.##"],
        'N' => ["##.##", "###.#", "#####", "#.###", "##.##", "##.##"],
        'O' => [".###.", "##.##", "##.##", "##.##", "##.##", ".###."],
        'P' => ["####.", "##.##", "##.##", "####.", "##...", "##..."],
        'R' => ["####.", "##.##", "##.##", "####.", "##.##", "##.##"],
        'S' => [".####", "##...", ".###.", "...##", "...##", "####."],
        'T' => ["#####", "..#..", "..#..", "..#..", "..#..", "..#.."],
        'Y' => ["##.##", "##.##", ".###.", "..#..", "..#..", "..#.."],
        '1' => ["..##.", "###..", "..##.", "..##.", "..##.", "#####"],
        '2' => [".###.", "##.##", "...##", "..##.", ".##..", "#####"],
        '/' => ["....#", "...##", "..##.", ".##..", "##...", "#...."],
        _ => [".....", ".....", ".....", ".....", ".....", "....."],
    }
}

/// Width of `s` on a plate: 5 columns a letter, 1 between; 2 columns of frame each side.
fn width(s: &str) -> i32 {
    s.chars().count() as i32 * 6 - 1 + 4
}

fn letters(cv: &mut Rgba, x: i32, y: i32, s: &str, ink: Rgb) {
    for (k, c) in s.chars().enumerate() {
        for (r, row) in glyph(c).iter().enumerate() {
            for (cx, b) in row.bytes().enumerate() {
                if b == b'#' {
                    cv.put(x + 6 * k as i32 + cx as i32, y + r as i32, ink);
                }
            }
        }
    }
}

/// A plate as "RECORD"'s: pink letters on dark green, 8 rows tall. Returns its width.
fn label(cv: &mut Rgba, x: i32, y: i32, s: &str) -> i32 {
    let w = width(s);
    cv.rect(x, y, w, 8, GREEN);
    letters(cv, x + 2, y + 1, s, PINK);
    w
}

/// A key name as "ENEMY"'s plate: white letters on dark green, 8 rows tall. Returns its width.
fn key(cv: &mut Rgba, x: i32, y: i32, s: &str) -> i32 {
    let w = width(s);
    cv.rect(x, y, w, 8, GREEN);
    letters(cv, x + 2, y + 1, s, WHITE);
    w
}

/// The hint of option `opt` for entry `e` with map `stage` (0 the first) showing; nothing for a one-map run.
pub fn paint(rgba: &mut [u8], opt: char, e: &Entry, stage: usize) {
    if e.stage_titles.is_empty() {
        return;
    }
    let maps = 1 + e.stage_titles.len();
    let cv = &mut Rgba(rgba);
    let n = |k: usize| char::from(b'1' + k as u8);
    match opt {
        // A: the prompt in the free band between the picture and the faces, in the plates' style: [SELECT] 2ND MAP (1ST MAP when the second is up).
        'a' => {
            let next = if stage + 1 < maps { format!("{}{} MAP", n(stage + 1), ["ST", "ND", "RD"][(stage + 1).min(2)]) } else { "1ST MAP".to_string() };
            let k = key(cv, 108, 132, "SELECT");
            label(cv, 108 + k + 2, 132, &next);
        }
        // B: a label in the picture's lower right corner: which map is shown, and the key to change it.
        'b' => {
            let m = format!("MAP {}/{}", n(stage), n(maps - 1));
            let k = width("SELECT");
            let l = width(&m);
            let x = 234 - l - k - 2;
            label(cv, x, 118, &m);
            key(cv, x + l + 2, 118, "SELECT");
        }
        // C: "ENEMY" over the faces says which map they are of ("MAP 1/2"), with the key beside it.
        _ => {
            let m = format!("MAP {}/{}", n(stage), n(maps - 1));
            let w = width(&m);
            key(cv, 240 - w, 136, &m);
            label(cv, 240 - w - 2 - width("SELECT"), 136, "SELECT");
        }
    }
}
