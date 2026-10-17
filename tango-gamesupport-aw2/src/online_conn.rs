//! How the online side is doing, shown with the game's own pages: a small status in the ONLINE and LOBBY screens'
//! top middle ([`draw_corner`]: a flag and one word, Online / Limited / Offline) and the Connection page (R on the
//! ONLINE screen; the same window, header and rows as STATS: [`draw_page`]). The app keeps both up to date from its
//! health table of the relay services (`tango_net::endpoints`) and writes them into [`BASE`] ([`write`]); nothing
//! here is read back by the simulation.

use mgba::core::Core;

use crate::online::{bar, fit, text_width, Rgb, Rgba, BAR, BLUE, GRAY_INK, INK, RED, SHADE, WHITE, YELLOW};

/// tangoAW2's 0x0203D440..0x0203D500 (free between the saved matches' list and the lobby browser).
pub const BASE: u32 = 0x0203_D440;
pub const LEN: u32 = 0xC0;
/// 0 not checked yet, 1 Online, 2 Limited, 3 Offline.
pub const STATE: u32 = BASE;
const COUNT: u32 = BASE + 2;
const LINES: u32 = BASE + 8;
pub const LINE_SIZE: u32 = 0x24;
pub const MAX_LINES: usize = 5;

const GREEN: Rgb = (40, 150, 70);
const AMBER: Rgb = (200, 140, 0);

/// The app's side: the overall state (0..3) and the page's lines, "T|label<TAB>value" (T: g good, y middling, r bad).
pub fn write(write: &mut dyn FnMut(u32, &[u8]), state: u8, lines: &[String]) {
    let mut block = vec![0u8; LINE_SIZE as usize * MAX_LINES];
    let n = lines.len().min(MAX_LINES);
    for (k, l) in lines.iter().take(MAX_LINES).enumerate() {
        for (i, c) in l.chars().filter(|c| (c.is_ascii() && !c.is_ascii_control()) || *c == '\t').take(LINE_SIZE as usize - 1).enumerate() {
            block[LINE_SIZE as usize * k + i] = c as u8;
        }
    }
    write(LINES, &block);
    write(COUNT, &[n as u8]);
    write(STATE, &[state.min(3)]);
}

pub fn state(core: &Core) -> u8 {
    core.raw_read_8(STATE, -1)
}

fn line(core: &Core, k: usize) -> String {
    (0..LINE_SIZE as usize - 1)
        .map(|i| core.raw_read_8(LINES + LINE_SIZE * k as u32 + i as u32, -1))
        .take_while(|&c| c != 0)
        .map(|c| c as char)
        .collect()
}

fn tone(c: char) -> Rgb {
    match c {
        'g' => GREEN,
        'y' => AMBER,
        _ => RED,
    }
}

/// A small flag on a pole (the capture marker's look) in `c`.
fn flag(cv: &mut Rgba, x: i32, y: i32, c: Rgb) {
    cv.rect(x, y, 1, 9, WHITE);
    cv.rect(x + 1, y, 6, 4, c);
    cv.rect(x + 1, y + 4, 4, 1, c);
    cv.rect(x + 1, y, 6, 1, WHITE);
}

/// The status in the screen's top middle, between the title and the gamertag, with the key to the page.
pub fn draw_corner(cv: &mut Rgba, core: &Core) {
    let (word, c) = match state(core) {
        1 => ("Online", GREEN),
        2 => ("Limited", YELLOW),
        3 => ("Offline", RED),
        _ => ("Checking", GRAY_INK),
    };
    let hint = "R: Details";
    let w = text_width(core, word).max(text_width(core, hint)).max(40);
    let x = 80;
    cv.rect(x - 2, 2, w + 8 + 8, 26, BAR);
    flag(cv, x + 1, 5, c);
    cv.text(core, x + 12, 4, word, WHITE, GRAY_INK);
    cv.text(core, x + 2, 16, hint, GRAY_INK, GRAY_INK);
}

/// The Connection page's rows in the STATS page's frame.
pub fn draw_page(cv: &mut Rgba, core: &Core, panel: (i32, i32, i32, i32)) {
    let (x, y, w, _) = panel;
    let head = "Connection";
    cv.text(core, x + (w - text_width(core, head)) / 2, y + 5, head, GRAY_INK, SHADE);
    let n = core.raw_read_8(COUNT, -1).min(MAX_LINES as u8) as usize;
    if n == 0 {
        let t = "Checking...";
        cv.text(core, x + (w - text_width(core, t)) / 2, y + 40, t, GRAY_INK, SHADE);
    }
    for k in 0..n {
        let l = line(core, k);
        let (t, rest) = l.split_once('|').map_or(('g', l.as_str()), |(t, r)| (t.chars().next().unwrap_or('g'), r));
        let (label, value) = rest.split_once('\t').unwrap_or((rest, ""));
        let ry = y + 22 + 16 * k as i32;
        cv.rect(x + 4, ry + 13, w - 8, 1, crate::online::LIGHT_GRAY);
        let vw = text_width(core, value);
        let label = fit(core, label, w - 12 - vw - 6);
        cv.text(core, x + 6, ry, &label, INK, SHADE);
        cv.text(core, x + w - 6 - vw, ry, value, tone(t), SHADE);
    }
    let _ = BLUE;
    bar(cv, core, "B: Back");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_fits() {
        assert!(LINES + LINE_SIZE * MAX_LINES as u32 <= BASE + LEN);
    }
}
