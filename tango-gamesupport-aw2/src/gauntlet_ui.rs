//! The Gauntlet's two choosing screens, in Advance Wars 2's own look (docs/dev/gauntlet-mode.md "The flow"): the **map selector** that opens when GAUNTLET is picked on Select Mode
//! (a list of the Gauntlet's maps, the map's picture, the enemies it brings in the order they come, the best result) and, after the CO pick, the **army colour pick** (the colours the
//! map's enemies do not wear, as emblems in a row).
//!
//! Both are screens of our own drawn over the finished picture ([`draw`], through `ds_coselect::apply` like the Teams cards): AW2's windows, font and portraits, the emblems of its Teams
//! screen, all read from the ROM at run time, nothing committed. The game underneath is a proc of the Gauntlet's start script that waits ([`crate::ds_campaign`]'s `gauntlet_start_script`:
//! a flow function that answers 1 while a step is up), so this module only owns the pad while a step is up ([`tick`] takes every key) and says which button ended it ([`ANSWER`]).
//!
//! The maps and their enemies come from [`crate::gauntlet_mode::entries`] (a new map's mission lists itself), the colours from [`crate::gauntlet_mode::Entry::free`] (the five minus the
//! enemies' fixed ones, plus Silver Nova). The choice is an army code of the Teams screen (1..5, or `army_skin::SKIN + i` for a skin); [`crate::gauntlet::keep_colour`] puts it on the
//! player's army when the battle starts.
//!
//! State: [`STATE`] in EWRAM (`ram_map`): the step, the answer, the cursors, and the last colour worn on each map.

use mgba::core::Core;

use crate::gauntlet_mode::{self as gm, Entry};
use crate::online::{self, Rgb, Rgba, GRAY_INK, INK, SHADE, W, WHITE, YELLOW};

pub const STATE: u32 = 0x0203_D080;
pub const STATE_LEN: u32 = 0x40;
/// 0 nothing up, 1 the map selector, 2 the colour pick.
pub const STEP: u32 = STATE;
/// How the last step ended: 1 A (on to the next), 0 B (back).
pub const ANSWER: u32 = STATE + 1;
/// The selector's cursor (a map).
const MAP_CURSOR: u32 = STATE + 2;
/// The map picked.
const MAP: u32 = STATE + 3;
/// The colour pick's cursor (an index into the map's free colours).
const COLOUR_CURSOR: u32 = STATE + 4;
/// 1 when the colour pick was left with B: the start script comes round again and goes to the CO screen, not to the selector.
const BACK_TO_CO: u32 = STATE + 5;
/// The last choice on each map (an army code, 0 none), 8 maps.
const LAST: u32 = STATE + 8;
const LAST_MAPS: usize = 8;

/// What the step shows (for the tests, which cannot read the picture's words): +0 the maps listed, +1 how many enemies the highlighted map has, +2.. their (CO, colour) in the order they
/// come (6 at most), +0x0E how many colours are free to wear on the map picked, +0x0F.. those army codes (8 at most).
pub const SHOWN: u32 = STATE + 0x20;

/// The CO screen's picks (`gUnknown_030058D4`): the player's CO is the first.
const CO_PICKS: u32 = 0x0300_58D4;

pub const SELECT: u8 = 1;
pub const COLOUR: u8 = 2;

const KEY_A: u32 = 1 << 0;
const KEY_B: u32 = 1 << 1;
const KEY_RIGHT: u32 = 1 << 4;
const KEY_LEFT: u32 = 1 << 5;
const KEY_UP: u32 = 1 << 6;
const KEY_DOWN: u32 = 1 << 7;

pub fn step(core: &Core) -> u8 {
    core.raw_read_8(STEP, -1)
}

/// A step is up (the start script waits for it).
pub fn up(core: &Core) -> bool {
    step(core) != 0
}

/// The start script's call: the map selector opens (or, coming back from the colour pick, the CO screen follows at once).
pub fn begin_select(core: &mut Core) {
    if core.raw_read_8(BACK_TO_CO, -1) == 1 {
        core.raw_write_8(BACK_TO_CO, -1, 0);
        core.raw_write_8(STEP, -1, 0);
        core.raw_write_8(ANSWER, -1, 1);
        return;
    }
    core.raw_write_8(ANSWER, -1, 0);
    core.raw_write_8(STEP, -1, SELECT);
}

/// The start script's call after the CO pick: the colour pick opens on the colour last worn on this map. A map with one colour (or none) free has nothing to pick.
pub fn begin_colour(core: &mut Core) {
    let e = picked(core);
    let free = e.map(Entry::free).unwrap_or_default();
    core.raw_write_8(ANSWER, -1, 1);
    match free.len() {
        0 => crate::ds_campaign::set_gauntlet_choice(core, 0),
        1 => crate::ds_campaign::set_gauntlet_choice(core, free[0]),
        _ => {
            let last = last_choice(core, e.map_or(0, |e| e.mission));
            let at = free.iter().position(|&c| c == last).unwrap_or(0);
            core.raw_write_8(COLOUR_CURSOR, -1, at as u8);
            core.raw_write_8(ANSWER, -1, 0);
            core.raw_write_8(STEP, -1, COLOUR);
        }
    }
}

/// The map the selector picked.
pub fn picked(core: &Core) -> Option<&'static Entry> {
    gm::entries().get(core.raw_read_8(MAP, -1) as usize)
}

/// The selector's cursor and the colour pick's, for the tests.
pub fn cursors(core: &Core) -> (u8, u8) {
    (core.raw_read_8(MAP_CURSOR, -1), core.raw_read_8(COLOUR_CURSOR, -1))
}

fn last_choice(core: &Core, mission: usize) -> u8 {
    if mission < LAST_MAPS {
        core.raw_read_8(LAST + mission as u32, -1)
    } else {
        0
    }
}

/// Each frame: while a step is up it takes the pad (the game sees no key) and moves the cursor; A and B end the step.
pub fn tick(core: &mut Core, on: bool, keys: u32, prev: u32) -> u32 {
    let s = step(core);
    if s == 0 {
        return keys;
    }
    if !on || !crate::gauntlet::session(core) {
        core.raw_write_8(STEP, -1, 0);
        return keys;
    }
    let pressed = keys & !prev;
    let entries = gm::entries();
    mirror(core);
    match s {
        SELECT => {
            let n = entries.len().max(1) as u8;
            let mut c = core.raw_read_8(MAP_CURSOR, -1) % n;
            if pressed & KEY_DOWN != 0 {
                c = (c + 1) % n;
            }
            if pressed & KEY_UP != 0 {
                c = (c + n - 1) % n;
            }
            core.raw_write_8(MAP_CURSOR, -1, c);
            if pressed & KEY_A != 0 && !entries.is_empty() {
                core.raw_write_8(MAP, -1, c);
                crate::ds_campaign::choose_gauntlet_map(core, entries[c as usize].mission);
                core.raw_write_8(ANSWER, -1, 1);
                core.raw_write_8(STEP, -1, 0);
            } else if pressed & KEY_B != 0 {
                core.raw_write_8(ANSWER, -1, 0);
                core.raw_write_8(STEP, -1, 0);
            }
        }
        _ => {
            let free = picked(core).map(Entry::free).unwrap_or_default();
            let n = free.len().max(1) as u8;
            let mut c = core.raw_read_8(COLOUR_CURSOR, -1) % n;
            if pressed & KEY_RIGHT != 0 {
                c = (c + 1) % n;
            }
            if pressed & KEY_LEFT != 0 {
                c = (c + n - 1) % n;
            }
            core.raw_write_8(COLOUR_CURSOR, -1, c);
            if pressed & KEY_A != 0 && !free.is_empty() {
                let code = free[c as usize];
                crate::ds_campaign::set_gauntlet_choice(core, code);
                let mission = picked(core).map_or(0, |e| e.mission);
                if mission < LAST_MAPS {
                    core.raw_write_8(LAST + mission as u32, -1, code);
                }
                core.raw_write_8(ANSWER, -1, 1);
                core.raw_write_8(STEP, -1, 0);
            } else if pressed & KEY_B != 0 {
                core.raw_write_8(BACK_TO_CO, -1, 1);
                core.raw_write_8(ANSWER, -1, 0);
                core.raw_write_8(STEP, -1, 0);
            }
        }
    }
    0
}

/// Writes [`SHOWN`]: what the selector lists for the map under the cursor and what the colour pick offers for the map picked.
fn mirror(core: &mut Core) {
    let entries = gm::entries();
    let cursor = core.raw_read_8(MAP_CURSOR, -1) as usize;
    let mut b = [0u8; 0x17];
    b[0] = entries.len() as u8;
    let shown = if step(core) == SELECT { entries.get(cursor) } else { picked(core) };
    if let Some(e) = shown {
        b[1] = e.enemies.len().min(6) as u8;
        for (k, en) in e.enemies.iter().take(6).enumerate() {
            b[2 + 2 * k] = en.0;
            b[3 + 2 * k] = en.1;
        }
        let free = e.free();
        b[0x0E] = free.len().min(8) as u8;
        for (k, c) in free.iter().take(8).enumerate() {
            b[0x0F + k] = *c;
        }
    }
    core.raw_write_range(SHOWN, -1, &b);
}

// --- Drawing ------------------------------------------------------------------------------------------------------------------------------------------

/// The sea behind the windows (the game's own Teams and SELECT MAP pictures lie on one).
const SEA: Rgb = (152, 224, 232);

/// An army code's name: AW2's five, or a skin's.
pub fn colour_name(code: u8) -> String {
    match code {
        1 => "Orange Star".into(),
        2 => "Blue Moon".into(),
        3 => "Green Earth".into(),
        4 => "Yellow Comet".into(),
        5 => "Black Hole".into(),
        c => crate::army_skin::skins().get((c.saturating_sub(crate::army_skin::SKIN)) as usize).map(|s| s.name.clone()).unwrap_or_default(),
    }
}

/// The title window and the keys it names.
fn header(cv: &mut Rgba<'_>, core: &Core, what: &str, keys: &str) {
    cv.window(4, 3, W as i32 - 8, 16);
    cv.text(core, 10, 7, "GAUNTLET", INK, SHADE);
    let x = 10 + online::text_width(core, "GAUNTLET") + 8;
    cv.text(core, x, 7, what, GRAY_INK, SHADE);
    let w = online::text_width(core, keys);
    cv.text(core, W as i32 - 10 - w, 7, keys, GRAY_INK, SHADE);
}

fn fit(core: &Core, s: &str, max: i32) -> String {
    let mut t = s.to_string();
    while t.len() > 1 && online::text_width(core, &t) > max {
        t.pop();
    }
    t
}

/// The map's picture (the game's own terrain classes), `s` pixels a cell, centred in (x, y, w, h). Properties wear their owner's army colour.
fn minimap(cv: &mut Rgba<'_>, core: &Core, e: &Entry, (x, y, w, h): (i32, i32, i32, i32)) {
    let Some(map) = crate::custom_campaign::built_map(e.key) else { return };
    let mut classes = vec![0u8; 0x400];
    core.raw_read_range(0x080C_1BC4, -1, &mut classes);
    let (mw, mh) = (map.width as i32, map.height as i32);
    let s = (w / mw.max(1)).min(h / mh.max(1)).max(1);
    let (ox, oy) = (x + (w - s * mw) / 2, y + (h - s * mh) / 2);
    let army: [Rgb; 6] = [(176, 176, 184), (240, 56, 40), (56, 96, 248), (48, 192, 72), (248, 216, 40), (60, 60, 76)];
    let colour_of = |owner: usize| -> Rgb {
        // (army 1 is the player's: its own colour is not chosen yet, so Orange Star's; the others wear the map's fixed colours)
        let col = match owner {
            0 => 0,
            1 => crate::custom_campaign::colour::ORANGE_STAR,
            k => e.enemies.get(k - 2).map_or(0, |en| en.1),
        };
        army[(col as usize).min(5)]
    };
    for ty in 0..mh {
        for tx in 0..mw {
            let t = map.tiles[(ty * mw + tx) as usize] as usize;
            let c: Rgb = match t {
                0x1B4..=0x1B8 => army[5],
                0x1C0..=0x1D8 => colour_of((t - 0x1C0) / 5),
                _ => match classes.get(t).copied().unwrap_or(0) & 0x1F {
                    1 => (152, 224, 88),
                    2 | 13 => (240, 224, 160),
                    3 => (160, 104, 48),
                    4 => (56, 160, 64),
                    5 | 12 => (176, 176, 184),
                    7 | 19 => (92, 120, 232),
                    15 => (112, 120, 136),
                    6 | 8 | 10 | 11 | 14 | 20 => (232, 232, 232),
                    _ => (176, 176, 184),
                },
            };
            cv.rect(ox + s * tx, oy + s * ty, s, s, c);
        }
    }
    cv.rect(ox - 1, oy - 1, s * mw + 2, 1, INK);
    cv.rect(ox - 1, oy + s * mh, s * mw + 2, 1, INK);
    cv.rect(ox - 1, oy - 1, 1, s * mh + 2, INK);
    cv.rect(ox + s * mw, oy - 1, 1, s * mh + 2, INK);
}

/// The enemies you will face: a window at (4, y) with each line's face, the army's emblem and the order they come in, the CO's name under them.
fn enemies(cv: &mut Rgba<'_>, core: &Core, e: &Entry, y: i32) {
    let (x, w, h) = (4, W as i32 - 8, 56);
    cv.window(x, y, w, h);
    cv.text(core, x + 6, y + 3, "Enemies you will face", GRAY_INK, SHADE);
    let n = e.enemies.len().max(1) as i32;
    let slot = ((w - 8) / n).min(74);
    // (a face and the army's emblem side by side; with many enemies the face shrinks, and the order's number goes when there is no room)
    let face = (slot - 20).clamp(16, 24);
    for (k, &(co, colour)) in e.enemies.iter().enumerate() {
        let sx = x + 6 + slot * k as i32;
        cv.rect(sx - 1, y + 15, face + 2, face + 2, INK);
        crate::online_teams::draw_face(core, cv, co, sx, y + 16, face);
        crate::army_cards::emblem(core, cv, colour, sx + face + 3, y + 17);
        if slot >= 62 {
            cv.text(core, sx + face + 22, y + 20, &(k + 1).to_string(), INK, SHADE);
        }
        let name = fit(core, &crate::online_teams::co_label(core, co), slot - 3);
        cv.text(core, sx, y + 42, &name, INK, SHADE);
    }
}

fn selector(cv: &mut Rgba<'_>, core: &Core, entries: &[Entry], cursor: usize) {
    let cursor = cursor.min(entries.len().saturating_sub(1));
    header(cv, core, "Select Map", "A: Choose  B: Back");
    // The list: three rows, scrolled so the cursor shows.
    let (lx, ly, lw, lh) = (4, 22, 104, 40);
    cv.window(lx, ly, lw, lh);
    let first = cursor.saturating_sub(2).min(entries.len().saturating_sub(3));
    for (row, e) in entries.iter().enumerate().skip(first).take(3) {
        let ry = ly + 3 + 12 * (row - first) as i32;
        if row == cursor {
            cv.rect(lx + 4, ry, lw - 8, 12, YELLOW);
        }
        let t = fit(core, e.title, lw - 22);
        cv.text(core, lx + 8, ry + 1, &t, INK, SHADE);
    }
    if first > 0 {
        cv.text(core, lx + lw - 12, ly + 3, "^", GRAY_INK, SHADE);
    }
    if first + 3 < entries.len() {
        cv.text(core, lx + lw - 12, ly + lh - 14, "v", GRAY_INK, SHADE);
    }
    let Some(e) = entries.get(cursor) else { return };
    // The best result.
    let (bx, by, bw, bh) = (4, 64, 104, 34);
    cv.window(bx, by, bw, bh);
    match crate::gauntlet::best(core, e.mission as u8) {
        Some(b) => {
            cv.text(core, bx + 6, by + 4, &format!("Best {} pts", b.score), INK, SHADE);
            let co = fit(core, &crate::online_teams::co_label(core, b.co), bw - 12 - online::text_width(core, &format!(", {} days", b.days)));
            cv.text(core, bx + 6, by + 17, &format!("{co}, {} days", b.days), GRAY_INK, SHADE);
        }
        None => {
            cv.text(core, bx + 6, by + 4, "Best", INK, SHADE);
            cv.text(core, bx + 6, by + 17, "No record yet", GRAY_INK, SHADE);
        }
    }
    // The map.
    let (px, py, pw, ph) = (112, 22, W as i32 - 116, 76);
    cv.window(px, py, pw, ph);
    minimap(cv, core, e, (px + 4, py + 4, pw - 8, ph - 8));
    enemies(cv, core, e, 100);
}

fn colour_pick(cv: &mut Rgba<'_>, core: &Core, e: &Entry, cursor: usize, co: u8) {
    header(cv, core, "Army Colour", "A: Choose  B: Back");
    let free = e.free();
    let cursor = cursor.min(free.len().saturating_sub(1));
    let (x, y, w, h) = (4, 22, W as i32 - 8, 74);
    cv.window(x, y, w, h);
    // The player's CO, as the CO screen picked it.
    cv.text(core, x + 6, y + 5, "Your army", GRAY_INK, SHADE);
    if co != 0xFF && co != 0 {
        cv.rect(x + 5, y + 19, 34, 34, INK);
        crate::online_teams::draw_face(core, cv, co, x + 6, y + 20, 32);
        let name = fit(core, &crate::online_teams::co_label(core, co), 48);
        cv.text(core, x + 6, y + 56, &name, INK, SHADE);
    }
    // The colours left: emblems in a row, the chosen one framed.
    let pitch = 30;
    let (ex, ey) = (x + 62, y + 22);
    cv.text(core, ex, y + 5, "Choose a colour", GRAY_INK, SHADE);
    for (k, &code) in free.iter().enumerate() {
        let cx = ex + pitch * k as i32;
        if k == cursor {
            cv.rect(cx - 3, ey - 3, 22, 22, YELLOW);
            cv.rect(cx - 2, ey - 2, 20, 20, WHITE);
        }
        crate::army_cards::emblem(core, cv, code, cx, ey);
    }
    if let Some(&code) = free.get(cursor) {
        cv.text(core, ex, ey + 23, &colour_name(code), INK, SHADE);
    }
    cv.text(core, ex, ey + 35, "The enemy wears the rest.", GRAY_INK, SHADE);
    enemies(cv, core, e, 100);
}

/// The step's picture over the finished one. `true` when one is up.
pub fn draw(core: &Core, rgba: &mut [u8]) -> bool {
    if rgba.len() != W * online::H * 4 {
        return false;
    }
    let s = step(core);
    if s == 0 || !crate::gauntlet::session(core) {
        return false;
    }
    let mut cv = Rgba(rgba);
    cv.rect(0, 0, W as i32, online::H as i32, SEA);
    match s {
        SELECT => selector(&mut cv, core, gm::entries(), core.raw_read_8(MAP_CURSOR, -1) as usize),
        _ => {
            if let Some(e) = picked(core) {
                // (the CO screen's pick list outlives the screen: its first entry is the player's CO)
                colour_pick(&mut cv, core, e, core.raw_read_8(COLOUR_CURSOR, -1) as usize, core.raw_read_8(CO_PICKS, -1));
            }
        }
    }
    true
}

/// The selector's picture of `entries` with the cursor on `cursor` (the text audit's page: any entries, whether or not a session is up).
pub fn paint_selector(core: &Core, rgba: &mut [u8], entries: &[Entry], cursor: usize) {
    let mut cv = Rgba(rgba);
    cv.rect(0, 0, W as i32, online::H as i32, SEA);
    selector(&mut cv, core, entries, cursor);
}

/// The colour pick's picture for map `e` (the text audit's page).
pub fn paint_colour_pick(core: &Core, rgba: &mut [u8], e: &Entry, cursor: usize, co: u8) {
    let mut cv = Rgba(rgba);
    cv.rect(0, 0, W as i32, online::H as i32, SEA);
    colour_pick(&mut cv, core, e, cursor, co);
}
