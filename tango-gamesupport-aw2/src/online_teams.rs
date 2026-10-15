//! Choosing armies in a room (crate::online): every player their own CO, colour and partner, all at the same time.
//!
//! On the netplay console of a room's match, Versus' Teams screen is not played: the game's own screen waits
//! underneath, given no keys, while this page is drawn over it. Each seat has a selector of its own in EWRAM
//! ([`SEL`]: its choices, which field it is on, whether it is READY), moved only by that seat's keys, which
//! [`tick`] reads from the netplay input stream every frame (so both peers, and a replay, apply the same keys and
//! stay the same). When every seat is READY the choices are written into the game's Teams record (each army's
//! controller is a human's, never the computer's) and the game's screen is told to go on to the Rules.
//!
//! Colours are distinct (a colour another player has is skipped; Black Hole is one of the five). The partner row
//! shows with Dual Strike's tag pairs.

use crate::online::{KEY_A, KEY_B, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_START, KEY_UP};
use mgba::core::Core;

/// tangoAW2's EWRAM for it (0x0203CB00..0x0203CBFF).
pub const SEL: u32 = 0x0203_CB00;
pub const SEL_LEN: u32 = 0x100;
/// 1 while the page runs on this Teams screen.
const INIT: u32 = SEL;
/// 1 once every seat is READY: the choices are written and the game's screen is told to go on.
const DONE: u32 = SEL + 1;
/// How many seats the room has (set from the inputs, every tick).
const PLAYERS: u32 = SEL + 2;
/// Frames since [`DONE`].
const PULSE: u32 = SEL + 3;
const SEATS: u32 = SEL + 0x10;
const SEAT_SIZE: u32 = 0x10;
// A seat: +0 CO (index into the Teams list), +1 colour, +2 partner CO (0xFF none), +3 field, +4 READY, +6 the
// previous keys (u16, on an even address: the GBA's halfword accesses are aligned), +8 frames the direction has
// been held, +9 the direction held.
const S_CO: u32 = 0;
const S_COLOUR: u32 = 1;
const S_PARTNER: u32 = 2;
const S_FIELD: u32 = 3;
const S_READY: u32 = 4;
const S_PREV: u32 = 6;
const S_HELD: u32 = 8;
const S_DIR: u32 = 9;

const NONE: u8 = 0xFF;
/// The fields, top to bottom: CO, colour, partner (with tag pairs), READY.
const F_CO: u8 = 0;
const F_COLOUR: u8 = 1;
const F_PARTNER: u8 = 2;
const F_READY: u8 = 3;

/// The five armies' colour codes in the order the pick cycles through them.
const COLOURS: [u8; 5] = [1, 2, 4, 3, 5];
const COLOUR_NAMES: [&str; 6] = ["", "Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole"];

pub fn players(core: &Core) -> usize {
    (core.raw_read_8(PLAYERS, -1) as usize).clamp(2, 5)
}

/// The page is up (the choices are being made).
pub fn active(core: &Core) -> bool {
    core.raw_read_8(INIT, -1) == 1 && core.raw_read_8(DONE, -1) == 0
}

/// Every seat is READY and the game's Teams screen is being sent on.
pub fn done(core: &Core) -> bool {
    core.raw_read_8(INIT, -1) == 1 && core.raw_read_8(DONE, -1) == 1
}

/// The keys the game gets while the page is up or finishing: none, then A's presses (the game's screen goes on to
/// the Rules on one). `None` when the page does not apply.
pub fn merge(core: &Core) -> Option<u32> {
    if active(core) {
        return Some(0);
    }
    if done(core) {
        // (A for 4 frames of 8, once the choices have been in a few frames)
        let t = core.raw_read_8(PULSE, -1);
        return Some(if t >= 6 && t % 8 < 4 { KEY_A } else { 0 });
    }
    None
}

fn seat(s: usize) -> u32 {
    SEATS + SEAT_SIZE * s as u32
}

struct Record {
    controller: u32,
    colour: u32,
    co: u32,
    armies: u32,
}

fn record(core: &Core) -> Record {
    let rec = crate::tag_ui::record(core);
    let five = crate::five::active(core);
    Record {
        controller: rec + if five { 0x90 } else { 0x09 },
        colour: rec + if five { 0x98 } else { 0x0D },
        co: rec + if five { 0xA8 } else { 0x1C },
        armies: crate::tag_ui::armies(core),
    }
}

fn tags(core: &Core) -> bool {
    // (UNRANKED has no tag pairs)
    crate::ds_weather::is_on(core) && !crate::unranked::on(core)
}

fn next_colour(core: &Core, n: usize, s: usize, step: isize) -> u8 {
    let current = core.raw_read_8(seat(s) + S_COLOUR, -1);
    let taken: Vec<u8> = (0..n)
        .filter(|&o| o != s)
        .map(|o| core.raw_read_8(seat(o) + S_COLOUR, -1))
        .collect();
    let start = COLOURS.iter().position(|&c| c == current).unwrap_or(0) as isize;
    (1..COLOURS.len() as isize)
        .map(|k| COLOURS[(start + step * k).rem_euclid(COLOURS.len() as isize) as usize])
        .find(|c| !taken.contains(c))
        .unwrap_or(current)
}

/// Every tick (any console): the room's size, and on a room's Teams screen the seats' selectors.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    let n = inputs.len().clamp(2, 5);
    if core.raw_read_8(PLAYERS, -1) != n as u8 {
        core.raw_write_8(PLAYERS, -1, n as u8);
    }
    let on = crate::online::in_room_match(core) && crate::pvp::in_versus(core) && crate::pvp::on_teams_screen(core);
    if !on {
        if core.raw_read_8(INIT, -1) != 0 {
            core.raw_write_range(SEL, -1, &[0u8; SEL_LEN as usize]);
            core.raw_write_8(PLAYERS, -1, n as u8);
        }
        return;
    }
    let rec = record(core);
    if core.raw_read_8(INIT, -1) == 0 {
        // Start from what the game's screen holds.
        for s in 0..n {
            let a = s as u32;
            let co = core.raw_read_8(rec.co + a, -1);
            let colour = core.raw_read_8(rec.colour + a, -1);
            core.raw_write_8(seat(s) + S_CO, -1, co);
            core.raw_write_8(seat(s) + S_COLOUR, -1, if COLOURS.contains(&colour) { colour } else { COLOURS[s % 5] });
            core.raw_write_8(seat(s) + S_PARTNER, -1, NONE);
            core.raw_write_8(seat(s) + S_FIELD, -1, F_CO);
            core.raw_write_8(seat(s) + S_READY, -1, 0);
            core.raw_write_16(seat(s) + S_PREV, -1, inputs[s] as u16);
        }
        // (two armies that came with one colour: the later one takes the next free one)
        for s in 1..n {
            let c = core.raw_read_8(seat(s) + S_COLOUR, -1);
            if (0..s).any(|o| core.raw_read_8(seat(o) + S_COLOUR, -1) == c) {
                let free = COLOURS.iter().copied().find(|c| !(0..s).any(|o| core.raw_read_8(seat(o) + S_COLOUR, -1) == *c));
                if let Some(free) = free {
                    core.raw_write_8(seat(s) + S_COLOUR, -1, free);
                }
            }
        }
        core.raw_write_8(INIT, -1, 1);
        return;
    }
    if core.raw_read_8(DONE, -1) == 1 {
        let t = core.raw_read_8(PULSE, -1);
        core.raw_write_8(PULSE, -1, t.saturating_add(1));
        write_choices(core, n);
        return;
    }
    let list = crate::tag_ui::teams_list(core);
    let tag_on = tags(core);
    for s in 0..n {
        let keys = inputs[s];
        let prev = core.raw_read_16(seat(s) + S_PREV, -1) as u32;
        core.raw_write_16(seat(s) + S_PREV, -1, keys as u16);
        let pressed = keys & !prev;
        // A held left or right goes on after a moment (AW2's own menus' repeat).
        let dir = if keys & KEY_LEFT != 0 {
            KEY_LEFT
        } else if keys & KEY_RIGHT != 0 {
            KEY_RIGHT
        } else {
            0
        };
        let mut step_dir = pressed & (KEY_LEFT | KEY_RIGHT);
        if dir == 0 || pressed & (KEY_LEFT | KEY_RIGHT) != 0 {
            core.raw_write_8(seat(s) + S_HELD, -1, 0);
        } else {
            let h = core.raw_read_8(seat(s) + S_HELD, -1).saturating_add(1);
            if h >= 18 && (h - 18) % 5 == 0 {
                step_dir = dir;
            }
            core.raw_write_8(seat(s) + S_HELD, -1, h);
        }
        core.raw_write_8(seat(s) + S_DIR, -1, dir as u8);
        let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
        let mut field = core.raw_read_8(seat(s) + S_FIELD, -1);
        if ready {
            if pressed & KEY_B != 0 {
                core.raw_write_8(seat(s) + S_READY, -1, 0);
            }
            continue;
        }
        let rows: Vec<u8> = if tag_on {
            vec![F_CO, F_COLOUR, F_PARTNER, F_READY]
        } else {
            vec![F_CO, F_COLOUR, F_READY]
        };
        let at = rows.iter().position(|&f| f == field).unwrap_or(0);
        if pressed & KEY_DOWN != 0 {
            field = rows[(at + 1) % rows.len()];
        }
        if pressed & KEY_UP != 0 {
            field = rows[(at + rows.len() - 1) % rows.len()];
        }
        core.raw_write_8(seat(s) + S_FIELD, -1, field);
        let step: isize = if step_dir == KEY_RIGHT {
            1
        } else if step_dir == KEY_LEFT {
            -1
        } else {
            0
        };
        if step != 0 {
            match field {
                F_CO if !list.is_empty() => {
                    let cur = core.raw_read_8(seat(s) + S_CO, -1) as isize;
                    let n = list.len() as isize;
                    core.raw_write_8(seat(s) + S_CO, -1, (cur + step).rem_euclid(n) as u8);
                    // (a partner is another CO than the main one)
                    let main = list[(cur + step).rem_euclid(n) as usize];
                    if core.raw_read_8(seat(s) + S_PARTNER, -1) == main {
                        core.raw_write_8(seat(s) + S_PARTNER, -1, NONE);
                    }
                }
                F_COLOUR => {
                    let c = next_colour(core, n, s, step);
                    core.raw_write_8(seat(s) + S_COLOUR, -1, c);
                }
                F_PARTNER if !list.is_empty() => {
                    let main = list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied();
                    let mut options: Vec<u8> = vec![NONE];
                    options.extend(list.iter().copied().filter(|&c| Some(c) != main));
                    let cur = core.raw_read_8(seat(s) + S_PARTNER, -1);
                    let i = options.iter().position(|&c| c == cur).unwrap_or(0) as isize;
                    let k = options.len() as isize;
                    core.raw_write_8(seat(s) + S_PARTNER, -1, options[(i + step).rem_euclid(k) as usize]);
                }
                _ => {}
            }
        }
        if pressed & (KEY_A | KEY_START) != 0 {
            // (A is READY wherever the cursor is, as the legend says; Up and Down only choose what to change)
            core.raw_write_8(seat(s) + S_READY, -1, 1);
        }
    }
    if (0..n).all(|s| core.raw_read_8(seat(s) + S_READY, -1) == 1) {
        core.raw_write_8(DONE, -1, 1);
        core.raw_write_8(PULSE, -1, 0);
        write_choices(core, n);
    }
}

/// The choices into the game's Teams record.
fn write_choices(core: &mut Core, n: usize) {
    let rec = record(core);
    let tag_on = tags(core);
    for s in 0..n.min(rec.armies as usize).max(n.min(5)) {
        let a = s as u32;
        core.raw_write_8(rec.controller + a, -1, 1);
        let co = core.raw_read_8(seat(s) + S_CO, -1);
        let colour = core.raw_read_8(seat(s) + S_COLOUR, -1);
        if core.raw_read_8(rec.co + a, -1) != co {
            core.raw_write_8(rec.co + a, -1, co);
        }
        if core.raw_read_8(rec.colour + a, -1) != colour {
            core.raw_write_8(rec.colour + a, -1, colour);
        }
        if tag_on {
            let p = core.raw_read_8(seat(s) + S_PARTNER, -1);
            core.raw_write_8(crate::tag::TEAMS_PARTNER + a, -1, p);
        }
    }
}

// --- Drawing (presentation only) -----------------------------------------------------------------

type Rgb = (u8, u8, u8);

fn colour_rgb(c: u8) -> Rgb {
    match c {
        1 => (232, 56, 40),
        2 => (56, 96, 216),
        3 => (48, 168, 72),
        4 => (232, 192, 32),
        _ => (64, 52, 72),
    }
}

fn faces() -> &'static std::sync::Mutex<std::collections::HashMap<u8, (Vec<u8>, [u8; 32])>> {
    static F: std::sync::OnceLock<std::sync::Mutex<std::collections::HashMap<u8, (Vec<u8>, [u8; 32])>>> =
        std::sync::OnceLock::new();
    F.get_or_init(Default::default)
}

/// A CO's name as the game writes it.
pub fn co_label(core: &Core, co: u8) -> String {
    let name = crate::co_new::ds_name(co).filter(|n| !n.is_empty()).unwrap_or_else(|| crate::tag_extras::co_name(core, co));
    name.iter().filter(|&&c| (0x20..0x7F).contains(&c)).map(|&c| c as char).collect()
}

/// `text` with selection arrows, cut down so it (and the highlight round it) never passes `max_w` pixels: "< text >",
/// else "<text>", else the text shortened with the arrows kept.
fn fit_arrows(core: &Core, text: &str, on: bool, max_w: i32) -> String {
    let w = |t: &str| crate::online::text_width(core, t);
    if !on {
        return text.to_string();
    }
    for cand in [format!("< {text} >"), format!("<{text}>")] {
        if w(&cand) <= max_w {
            return cand;
        }
    }
    let mut t: String = text.to_string();
    while !t.is_empty() && w(&format!("<{t}>")) > max_w {
        t.pop();
    }
    format!("<{t}>")
}

/// A CO's portrait scaled to `sz` pixels square at (x, y).
fn draw_face(core: &Core, cv: &mut crate::online::Rgba<'_>, co: u8, x: i32, y: i32, sz: i32) {
    let mut f = faces().lock().unwrap();
    let (px, pal) = f.entry(co).or_insert_with(|| {
        crate::ds_coselect::mug_for_face(core, co).unwrap_or_else(|| crate::tag_ui::portrait48(core, co))
    });
    for yy in 0..sz {
        for xx in 0..sz {
            let (sx, sy) = ((xx * 48 / sz) as usize, (yy * 48 / sz) as usize);
            let t = 6 * (sy / 8) + sx / 8;
            let b = px.get(32 * t + 4 * (sy % 8) + (sx % 8) / 2).copied().unwrap_or(0);
            let v = ((b >> (4 * (sx & 1))) & 15) as usize;
            let c = u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]]);
            cv.put(x + xx, y + yy, crate::online::bgr(c));
        }
    }
}

pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || (!active(core) && !done(core)) {
        return;
    }
    let n = players(core);
    let list = crate::tag_ui::teams_list(core);
    let tag_on = tags(core);
    let local = crate::online::room_local_seat();
    {
        let mut canvas = crate::online::Rgba(rgba);
        let cv = &mut canvas;
        cv.rect(0, 0, crate::online::W as i32, 160, crate::online::LIGHT_GRAY);
        cv.rect(0, 0, crate::online::W as i32, 15, crate::online::BAR);
        let title = "SELECT YOUR ARMY";
        let w = crate::online::text_width(core, title);
        cv.text(core, (crate::online::W as i32 - w) / 2, 2, title, crate::online::WHITE, crate::online::GRAY_INK);
        let top = 17;
        let rows_h = 143 - top;
        let rh = (rows_h / n as i32).min(46);
        for s in 0..n {
            let y = top + rh * s as i32;
            if n >= 4 {
                draw_compact(core, cv, s, y, rh, &list, tag_on, local);
                continue;
            }
            let co = list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied();
            let colour = core.raw_read_8(seat(s) + S_COLOUR, -1);
            let partner = core.raw_read_8(seat(s) + S_PARTNER, -1);
            let field = core.raw_read_8(seat(s) + S_FIELD, -1);
            let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
            let mine = s == local;
            cv.rect(2, y, 236, rh - 2, if mine { crate::online::CREAM } else { crate::online::WHITE });
            cv.rect(2, y, 4, rh - 2, colour_rgb(colour));
            // The portrait.
            let fsz = (rh - 4).clamp(12, 32);
            if let Some(co) = co {
                draw_face(core, cv, co, 8, y + 1, fsz);
            }
            let tx = 8 + fsz + 4;
            let name = crate::online::room_name(s);
            let name: String = name.chars().take(10).collect();
            let name_ink = if mine { crate::online::BLUE } else { crate::online::INK };
            cv.text(core, tx, y + 1, &name, name_ink, crate::online::SHADE);
            let co_name = co.map(|c| co_label(core, c)).unwrap_or_default();
            let sel = |f: u8| mine && !ready && field == f;
            let arrows = |on: bool, s: &str, max_w: i32| fit_arrows(core, s, on, max_w);
            let line = |cv: &mut crate::online::Rgba<'_>, core: &Core, x: i32, yy: i32, text: &str, on: bool| {
                let w = crate::online::text_width(core, text);
                if on {
                    cv.rect(x - 2, yy - 1, w + 4, 12, crate::online::YELLOW);
                }
                cv.text(core, x, yy, text, crate::online::INK, crate::online::SHADE);
            };
            let row2 = y + (rh / 2).max(11);
            line(cv, core, tx, row2, &arrows(sel(F_CO), &co_name, 104 - tx), sel(F_CO));
            // Colour.
            let cx = 112;
            if sel(F_COLOUR) {
                cv.rect(cx - 3, y + 2, 34, rh - 6, crate::online::YELLOW);
            }
            cv.rect(cx, y + 4, 28, rh - 10, colour_rgb(colour));
            if sel(F_COLOUR) {
                cv.text(core, cx - 9, y + (rh / 2) - 5, "<", crate::online::INK, crate::online::SHADE);
                cv.text(core, cx + 31, y + (rh / 2) - 5, ">", crate::online::INK, crate::online::SHADE);
            }
            // Partner.
            if tag_on {
                let px = 148;
                let pname = if partner == NONE { "none".to_string() } else { co_label(core, partner) };
                cv.text(core, px, y + 1, "Partner", crate::online::GRAY_INK, crate::online::SHADE);
                line(cv, core, px, row2, &arrows(sel(F_PARTNER), &pname, 196 - px), sel(F_PARTNER));
            }
            // READY.
            let (rx, rw) = (200, 36);
            let (label, plate, ink) = if ready {
                ("READY", crate::online::BLUE, crate::online::WHITE)
            } else if sel(F_READY) {
                ("READY?", crate::online::YELLOW, crate::online::INK)
            } else {
                ("...", crate::online::LIGHT_GRAY, crate::online::GRAY_INK)
            };
            cv.rect(rx, y + 3, rw, rh - 8, plate);
            let lw = crate::online::text_width(core, label);
            cv.text(core, rx + (rw - lw) / 2, y + (rh / 2) - 5, label, ink, crate::online::SHADE);
        }
        let help = match core.raw_read_8(seat(local.min(n - 1)) + S_READY, -1) {
            1 => "B: Change   Waiting for the others...",
            _ => "Up Down: Field  Left Right: Change  A: READY",
        };
        crate::online::bar(cv, core, if done(core) { "Everyone is ready!" } else { help });
        let _ = COLOUR_NAMES;
    }
}

/// One seat's row when four or five players share the screen: face, gamertag over CO, colour chip, partner face,
/// READY badge (presentation only; the same fields and focus as the full-size row).
#[allow(clippy::too_many_arguments)]
fn draw_compact(core: &Core, cv: &mut crate::online::Rgba<'_>, s: usize, y: i32, rh: i32, list: &[u8], tag_on: bool, local: usize) {
    let co = list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied();
    let colour = core.raw_read_8(seat(s) + S_COLOUR, -1);
    let partner = core.raw_read_8(seat(s) + S_PARTNER, -1);
    let field = core.raw_read_8(seat(s) + S_FIELD, -1);
    let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
    let mine = s == local;
    let sel = |f: u8| mine && !ready && field == f;
    let h = rh - 2;
    cv.rect(2, y, 236, h, if mine { crate::online::CREAM } else { crate::online::WHITE });
    cv.rect(2, y, 4, h, colour_rgb(colour));
    let sz = (h - 2).min(24);
    if let Some(co) = co {
        draw_face(core, cv, co, 8, y + 1, sz);
    }
    let tx = 8 + sz + 3;
    let name: String = crate::online::room_name(s).chars().take(10).collect();
    let name_ink = if mine { crate::online::BLUE } else { crate::online::INK };
    cv.text(core, tx, y, &name, name_ink, crate::online::SHADE);
    let co_name = co.map(|c| co_label(core, c)).unwrap_or_default();
    let co_text = fit_arrows(core, &co_name, sel(F_CO), 112 - tx);
    let row2 = y + h - 11;
    let w = crate::online::text_width(core, &co_text);
    if sel(F_CO) {
        cv.rect(tx - 2, row2 - 1, w + 4, 11, crate::online::YELLOW);
    }
    cv.text(core, tx, row2, &co_text, crate::online::INK, crate::online::SHADE);
    // Colour chip.
    let cx = 118;
    let cy = y + 3;
    let ch = h - 6;
    if sel(F_COLOUR) {
        cv.rect(cx - 10, y + 1, 36, h - 2, crate::online::YELLOW);
        cv.text(core, cx - 9, y + h / 2 - 5, "<", crate::online::INK, crate::online::SHADE);
        cv.text(core, cx + 20, y + h / 2 - 5, ">", crate::online::INK, crate::online::SHADE);
    }
    cv.rect(cx, cy, 16, ch, colour_rgb(colour));
    // Partner: a small face, "-" for none.
    if tag_on {
        let px = 160;
        if sel(F_PARTNER) {
            cv.rect(px - 10, y + 1, 36, h - 2, crate::online::YELLOW);
            cv.text(core, px - 9, y + h / 2 - 5, "<", crate::online::INK, crate::online::SHADE);
            cv.text(core, px + 20, y + h / 2 - 5, ">", crate::online::INK, crate::online::SHADE);
        }
        if partner == NONE {
            let w = crate::online::text_width(core, "-");
            cv.text(core, px + 8 - w / 2, y + h / 2 - 5, "-", crate::online::GRAY_INK, crate::online::SHADE);
        } else {
            draw_face(core, cv, partner, px, y + (h - 16) / 2, 16);
        }
    }
    // READY badge.
    let (rx, rw) = (197, 39);
    let (label, plate, ink) = if ready {
        ("READY", crate::online::BLUE, crate::online::WHITE)
    } else if sel(F_READY) {
        ("READY?", crate::online::YELLOW, crate::online::INK)
    } else {
        ("...", crate::online::LIGHT_GRAY, crate::online::GRAY_INK)
    };
    cv.rect(rx, y + 3, rw, h - 6, plate);
    let lw = crate::online::text_width(core, label);
    cv.text(core, rx + (rw - lw) / 2, y + h / 2 - 5, label, ink, crate::online::SHADE);
}
