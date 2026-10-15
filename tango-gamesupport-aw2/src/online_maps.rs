//! Choosing the map of a room's match (crate::online): a page organised by the room's number of players.
//!
//! On the netplay console of a room's match, Versus' SELECT MAP is not played: the game's own list waits underneath,
//! given no keys, while this page is drawn over it. The page lists only the maps for as many armies as the room has
//! players (the other counts show greyed on the title bar and cannot be picked), in two tabs, "3P" and "3P
//! Pre-Deployed" (the game's units already placed); each map shows its name, a preview drawn from its tile data, its
//! size and its properties. The host (seat 0) navigates, every peer sees the same page: its state is in EWRAM
//! ([`STATE`]) and moves only by [`tick`], which reads the host's keys from the netplay input stream every frame (so
//! both peers, and a replay, stay the same).
//!
//! On A the chosen id is written over the game's own list at its cursor row ([`LIST_IDS`]) and the game's A is
//! pulsed: its handler then does what it always does (the Versus setup is built from the id), and the game goes on
//! to the Teams screen. B pulses the game's B (back to Select Mode, which ends the match).
//!
//! [`list`] and [`preview`] / [`draw_preview`] are independent of the page (the UNRANKED proposals use them).
//!
//! Maps: the game's own map table ([`crate::five_map::table`]: AW2's, or with the Dual Strike pack in use
//! [`crate::ds_versus`]'s), every header on a Versus tab (2..=9) whose tab the game lists now (the Black Crystal and
//! Obelisk maps and the pack's maps sit on a hidden tab until their art is on, [`crate::five_map::show_maps`]).
//! Design Room maps are not listed (their tiles are in the save, not the ROM).

use crate::online::{Rgb, Rgba, KEY_A, KEY_B, KEY_DOWN, KEY_L, KEY_LEFT, KEY_R, KEY_RIGHT, KEY_UP};
use mgba::core::Core;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

/// tangoAW2's EWRAM for it (0x0203D100..0x0203D13F).
pub const STATE: u32 = 0x0203_D100;
pub const STATE_LEN: u32 = 0x40;
/// 1 while the page runs on this SELECT MAP.
const INIT: u32 = STATE;
/// 0 choosing, 1 a map chosen (the game's list is given it and its A), 2 leaving (the game's B).
const DONE: u32 = STATE + 1;
/// Frames since [`DONE`].
const PULSE: u32 = STATE + 2;
/// The tab: 0 the count's maps, 1 its Pre-Deployed maps.
const TAB: u32 = STATE + 3;
/// The chosen map's id.
const CHOSEN: u32 = STATE + 4;
/// Frames UP or DOWN has been held.
const HELD: u32 = STATE + 5;
/// The host's previous keys (u16, on an even address).
const PREV: u32 = STATE + 6;
/// Per tab: the cursor's index and the first row shown (u16 each).
const CURSOR: u32 = STATE + 8;
const SCROLL: u32 = STATE + 0xC;
/// Frames left of "the game did not take that map".
const FAIL: u32 = STATE + 0x10;

/// SELECT MAP's list: the game's ids by row, its proc (the cursor row is at +0x58) and where procs live.
const LIST_IDS: u32 = 0x0202_7F78;
const LIST_PROC: u32 = 0x0861_6CF4;
const PROCS: (u32, u32) = (0x0200_D610, 0x0200_E418);
const PLAY_ID: u32 = 0x0300_3FC2;
const TERRAIN_CLASSES: u32 = 0x080C_1BC4;

/// The Versus tabs of the game's list (header +0x1A): Classic .. 5P Maps. Others are not listed in Versus.
const TABS: std::ops::RangeInclusive<u16> = 2..=9;
/// Rows the list shows.
const ROWS: usize = 9;
const ROW_H: i32 = 10;

/// A map for the lists and the UNRANKED proposals.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MapEntry {
    pub id: u8,
    pub name: String,
    pub w: u8,
    pub h: u8,
    /// Properties (HQs, cities, bases, airports, ports, labs) in all.
    pub props: u16,
    /// Of them, the bases (factories).
    pub bases: u16,
    pub armies: u8,
    pub predeployed: bool,
}

// --- The maps ----------------------------------------------------------------------------------

fn rom(at: u32) -> bool {
    (0x0800_0000..0x0A00_0000).contains(&at)
}

/// The id of the last map header to look at in the table in use.
fn last_id(table: u32) -> u32 {
    if table == crate::ds_versus::TABLE {
        0xFF
    } else {
        crate::five_map::MAP_IDS - 1
    }
}

/// How many armies a map has (a 5-army map says 4 in its header: the fifth is tangoAW2's).
fn armies_of(core: &Core, table: u32, id: u32) -> u8 {
    let n = core.raw_read_8(table + 0x5C * id + 0x18, -1);
    let ours = id < 0x100 && crate::five_map::is_five_map(id as u8) && !(table == crate::ds_versus::TABLE && crate::ds_versus::replaced(id as u8));
    if ours {
        5
    } else {
        n
    }
}

/// The ids on the Versus tabs for `armies` players: (maps, Pre-Deployed maps), each in the game's order (tab, id).
fn scan(core: &Core, armies: usize) -> (Vec<u8>, Vec<u8>) {
    let table = crate::five_map::table(core);
    let mut found: Vec<(u16, u8, bool)> = Vec::new();
    for id in 0..=last_id(table) {
        let h = table + 0x5C * id;
        if !rom(core.raw_read_32(h, -1)) {
            continue;
        }
        let tab = core.raw_read_16(h + 0x1A, -1);
        if !TABS.contains(&tab) || armies_of(core, table, id) as usize != armies {
            continue;
        }
        let units = core.raw_read_32(h + 0x34, -1);
        let pre = rom(units) && core.raw_read_8(units, -1) == 0xFE;
        found.push((tab, id as u8, pre));
    }
    found.sort();
    let pick = |pre: bool| found.iter().filter(|f| f.2 == pre).map(|f| f.1).collect();
    (pick(false), pick(true))
}

/// What a map is made of, decoded once.
struct Info {
    name: String,
    w: u8,
    h: u8,
    props: u16,
    bases: u16,
    /// Per tile, row by row: a kind (`K_*`).
    cells: Vec<u8>,
}

// The picture's kinds of tile: terrain, then property owners.
const K_SEA: u8 = 0;
const K_PLAIN: u8 = 1;
const K_WOOD: u8 = 2;
const K_MOUNTAIN: u8 = 3;
const K_ROAD: u8 = 4;
const K_SAND: u8 = 5;
const K_OTHER: u8 = 6;
const K_NEUTRAL: u8 = 7;
/// 8 + the army's colour - 1.
const K_ARMY: u8 = 8;
const KINDS: usize = 13;

fn kind_rgb(k: u8) -> Rgb {
    match k {
        K_SEA => (44, 92, 176),
        K_PLAIN => (152, 208, 104),
        K_WOOD => (56, 140, 72),
        K_MOUNTAIN => (168, 124, 76),
        K_ROAD => (184, 184, 188),
        K_SAND => (236, 212, 132),
        K_OTHER => (124, 104, 168),
        K_NEUTRAL => (250, 250, 250),
        _ => colour_rgb(k - K_ARMY + 1),
    }
}

/// The five armies' colours (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole).
fn colour_rgb(c: u8) -> Rgb {
    match c {
        1 => (240, 48, 36),
        2 => (96, 160, 255),
        3 => (32, 200, 72),
        4 => (255, 224, 32),
        _ => (40, 28, 56),
    }
}

type InfoKey = (u32, u32, u32);
fn caches() -> &'static Mutex<HashMap<InfoKey, Arc<Info>>> {
    static C: OnceLock<Mutex<HashMap<InfoKey, Arc<Info>>>> = OnceLock::new();
    C.get_or_init(Default::default)
}

fn name_of(core: &Core, text: u32) -> String {
    let p = core.raw_read_32(0x0861_0A38 + 4 * text, -1);
    let mut name = String::new();
    if rom(p) {
        for k in 0..32 {
            let c = core.raw_read_8(p + k, -1);
            if c == 0 {
                break;
            }
            // (tangoAW2's own maps' names have the apostrophe at `~`)
            name.push(if c == b'~' { '\'' } else { c as char });
        }
    }
    name
}

fn info(core: &Core, id: u8) -> Option<Arc<Info>> {
    let table = crate::five_map::table(core);
    let h = table + 0x5C * id as u32;
    let tiles = core.raw_read_32(h, -1);
    if !rom(tiles) {
        return None;
    }
    let text = core.raw_read_16(h + 0x14, -1) as u32;
    let key = (table, id as u32, tiles ^ (text << 20));
    if let Some(i) = caches().lock().unwrap().get(&key) {
        return Some(i.clone());
    }
    let raw = crate::invention_art::lz77(core, tiles);
    if raw.len() < 2 {
        return None;
    }
    let (w, ht) = (raw[0], raw[1]);
    if w == 0 || ht == 0 || raw.len() < 2 + 2 * w as usize * ht as usize {
        return None;
    }
    let mut classes = vec![0u8; 0x400];
    core.raw_read_range(TERRAIN_CLASSES, -1, &mut classes);
    // The armies' colours by slot (the header's +0x40..).
    let colour = |slot: u8| -> u8 {
        let c = if slot <= 4 { core.raw_read_8(h + 0x40 + slot as u32 - 1, -1) } else { 5 };
        if (1..=5).contains(&c) {
            c
        } else {
            slot.min(5)
        }
    };
    let (mut props, mut bases) = (0u16, 0u16);
    let cells = (0..w as usize * ht as usize)
        .map(|i| {
            let t = u16::from_le_bytes([raw[2 + 2 * i], raw[3 + 2 * i]]) as usize;
            let class = classes.get(t).copied().unwrap_or(0);
            let (kind, owner) = (class & 0x1F, class >> 5);
            match kind {
                6 | 8 | 10 | 11 | 14 | 20 => {
                    props += 1;
                    bases += (kind == 14) as u16;
                    if (1..=5).contains(&owner) {
                        K_ARMY + colour(owner) - 1
                    } else {
                        K_NEUTRAL
                    }
                }
                1 => K_PLAIN,
                2 | 13 => K_SAND,
                3 => K_MOUNTAIN,
                4 => K_WOOD,
                5 | 12 => K_ROAD,
                7 | 19 => K_SEA,
                15 => K_OTHER,
                _ => K_ROAD,
            }
        })
        .collect();
    let info = Arc::new(Info { name: name_of(core, text), w, h: ht, props, bases, cells });
    caches().lock().unwrap().insert(key, info.clone());
    Some(info)
}

/// The maps a room of `armies` players can play, the Pre-Deployed ones or the others, in the game's order.
pub fn list(core: &Core, armies: usize, predeployed: bool) -> Vec<MapEntry> {
    let (plain, pre) = scan(core, armies);
    let ids = if predeployed { pre } else { plain };
    ids.into_iter()
        .filter_map(|id| {
            let i = info(core, id)?;
            Some(MapEntry { id, name: i.name.clone(), w: i.w, h: i.h, props: i.props, bases: i.bases, armies: armies as u8, predeployed })
        })
        .collect()
}

/// A map's picture: `w` x `h` pixels, row by row.
pub struct Preview {
    pub w: usize,
    pub h: usize,
    pub pixels: Vec<Rgb>,
}

type PreviewKey = (u32, u32, u32, usize, usize);
fn previews() -> &'static Mutex<HashMap<PreviewKey, Arc<Preview>>> {
    static C: OnceLock<Mutex<HashMap<PreviewKey, Arc<Preview>>>> = OnceLock::new();
    C.get_or_init(Default::default)
}

/// The map `id` drawn as large as fits in `max_w` x `max_h` pixels: whole pixels per tile when it can, else each
/// pixel shows what is most of its tiles (a property over anything).
pub fn preview(core: &Core, id: u8, max_w: usize, max_h: usize) -> Option<Arc<Preview>> {
    let i = info(core, id)?;
    let table = crate::five_map::table(core);
    let tiles = core.raw_read_32(table + 0x5C * id as u32, -1);
    let key = (table, id as u32, tiles, max_w, max_h);
    if let Some(p) = previews().lock().unwrap().get(&key) {
        return Some(p.clone());
    }
    let (w, h) = (i.w as usize, i.h as usize);
    let s = (max_w / w).min(max_h / h);
    let (ow, oh) = if s >= 1 {
        (w * s, h * s)
    } else {
        let f = (max_w as f32 / w as f32).min(max_h as f32 / h as f32);
        (((w as f32 * f) as usize).max(1), ((h as f32 * f) as usize).max(1))
    };
    let mut pixels = Vec::with_capacity(ow * oh);
    for py in 0..oh {
        for px in 0..ow {
            let (x0, x1) = (px * w / ow, ((px + 1) * w).div_ceil(ow).max(px * w / ow + 1).min(w));
            let (y0, y1) = (py * h / oh, ((py + 1) * h).div_ceil(oh).max(py * h / oh + 1).min(h));
            let mut count = [0u16; KINDS];
            for y in y0..y1 {
                for x in x0..x1 {
                    count[i.cells[y * w + x] as usize] += 1;
                }
            }
            let prop = (K_NEUTRAL as usize..KINDS).filter(|&k| count[k] > 0).max_by_key(|&k| count[k]);
            let k = prop.unwrap_or_else(|| (0..K_NEUTRAL as usize).max_by_key(|&k| (count[k], std::cmp::Reverse(k))).unwrap_or(0));
            pixels.push(kind_rgb(k as u8));
        }
    }
    let p = Arc::new(Preview { w: ow, h: oh, pixels });
    previews().lock().unwrap().insert(key, p.clone());
    Some(p)
}

/// The map's picture centred in the box (x, y, w, h) of the canvas.
pub(crate) fn draw_preview(core: &Core, cv: &mut Rgba<'_>, id: u8, x: i32, y: i32, w: i32, h: i32) {
    let Some(p) = preview(core, id, w.max(1) as usize, h.max(1) as usize) else { return };
    let (ox, oy) = (x + (w - p.w as i32) / 2, y + (h - p.h as i32) / 2);
    for py in 0..p.h {
        for px in 0..p.w {
            cv.put(ox + px as i32, oy + py as i32, p.pixels[py * p.w + px]);
        }
    }
}

// --- The page ----------------------------------------------------------------------------------

/// SELECT MAP's list proc's cursor row.
fn list_row(core: &Core) -> Option<u32> {
    let p = (PROCS.0..PROCS.1).step_by(0x6C).find(|&p| core.raw_read_32(p, -1) == LIST_PROC)?;
    Some(core.raw_read_16(p + 0x58, -1) as u32)
}

/// The page is up (a map is being chosen, or was and the game is taking it).
pub fn owns(core: &Core) -> bool {
    core.raw_read_8(INIT, -1) == 1
}

/// The keys the game gets while the page is up: none, then A's presses (or B's) once a choice is made.
pub fn merge(core: &Core) -> Option<u32> {
    if !owns(core) {
        return None;
    }
    let t = core.raw_read_8(PULSE, -1);
    let pulse = t >= 6 && t % 8 < 4;
    Some(match core.raw_read_8(DONE, -1) {
        1 if pulse => KEY_A,
        2 if pulse => KEY_B,
        _ => 0,
    })
}

fn cursor(core: &Core, tab: u32) -> usize {
    core.raw_read_16(CURSOR + 2 * tab, -1) as usize
}

/// Every tick (any console): on a room's SELECT MAP, the host's keys move the page.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    let on = crate::online::in_room_match(core) && crate::survival_ui::selecting(core);
    if !on {
        if core.raw_read_8(INIT, -1) != 0 {
            core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
        }
        return;
    }
    let n = crate::online_teams::players(core);
    let (plain, pre) = scan(core, n);
    if plain.is_empty() && pre.is_empty() {
        // (no map for this many players: the game's own list, the host's)
        return;
    }
    let keys = inputs.first().copied().unwrap_or(0);
    if core.raw_read_8(INIT, -1) == 0 {
        // Start on the map played last when it is for this many players.
        let last = core.raw_read_8(PLAY_ID, -1);
        let (mut tab, mut at) = (0u8, 0u16);
        if let Some(p) = plain.iter().position(|&i| i == last) {
            at = p as u16;
        } else if let Some(p) = pre.iter().position(|&i| i == last) {
            tab = 1;
            at = p as u16;
        } else if plain.is_empty() {
            tab = 1;
        }
        core.raw_write_8(INIT, -1, 1);
        core.raw_write_8(TAB, -1, tab);
        core.raw_write_16(CURSOR + 2 * tab as u32, -1, at);
        core.raw_write_16(PREV, -1, keys as u16);
        return;
    }
    let prev = core.raw_read_16(PREV, -1) as u32;
    core.raw_write_16(PREV, -1, keys as u16);
    let pressed = keys & !prev;
    let fail = core.raw_read_8(FAIL, -1);
    if fail > 0 {
        core.raw_write_8(FAIL, -1, fail - 1);
    }
    let tab = core.raw_read_8(TAB, -1) as usize;
    let group = |t: usize| if t == 0 { &plain } else { &pre };
    match core.raw_read_8(DONE, -1) {
        0 => {
            let len = group(tab).len();
            let mut at = cursor(core, tab as u32).min(len.saturating_sub(1));
            // UP and DOWN go on when held, after a moment (AW2's own lists').
            let dir = keys & (KEY_UP | KEY_DOWN);
            let mut step = pressed & (KEY_UP | KEY_DOWN);
            if dir == 0 || step != 0 {
                core.raw_write_8(HELD, -1, 0);
            } else {
                let h = core.raw_read_8(HELD, -1).saturating_add(1);
                if h >= 14 && (h - 14) % 4 == 0 {
                    step = dir;
                }
                core.raw_write_8(HELD, -1, h);
            }
            if len > 0 {
                if step & KEY_DOWN != 0 {
                    at = (at + 1) % len;
                } else if step & KEY_UP != 0 {
                    at = (at + len - 1) % len;
                }
            }
            core.raw_write_16(CURSOR + 2 * tab as u32, -1, at as u16);
            // (the first row shown follows the cursor)
            let mut top = (core.raw_read_16(SCROLL + 2 * tab as u32, -1) as usize).min(len.saturating_sub(1));
            if at < top {
                top = at;
            }
            if at >= top + ROWS {
                top = at + 1 - ROWS;
            }
            core.raw_write_16(SCROLL + 2 * tab as u32, -1, top as u16);
            // The other tab, when it has maps.
            if pressed & (KEY_LEFT | KEY_RIGHT | KEY_L | KEY_R) != 0 && !group(1 - tab).is_empty() {
                core.raw_write_8(TAB, -1, (1 - tab) as u8);
            }
            if pressed & KEY_A != 0 && len > 0 && crate::survival_ui::idle(core) {
                core.raw_write_8(CHOSEN, -1, group(tab)[at]);
                core.raw_write_8(DONE, -1, 1);
                core.raw_write_8(PULSE, -1, 0);
            } else if pressed & KEY_B != 0 {
                core.raw_write_8(DONE, -1, 2);
                core.raw_write_8(PULSE, -1, 0);
            }
        }
        done => {
            let t = core.raw_read_8(PULSE, -1);
            core.raw_write_8(PULSE, -1, t.saturating_add(1));
            if done == 1 {
                // The game's list takes the id at its cursor row.
                if let Some(row) = list_row(core).filter(|&r| r < 0x32) {
                    let id = core.raw_read_8(CHOSEN, -1);
                    if core.raw_read_8(LIST_IDS + row, -1) != id {
                        core.raw_write_8(LIST_IDS + row, -1, id);
                    }
                }
            }
            if t == 255 {
                // (the game did not go on: choose again)
                core.raw_write_8(DONE, -1, 0);
                core.raw_write_8(FAIL, -1, 150);
            }
        }
    }
}

// --- Drawing (presentation only) -----------------------------------------------------------------

const PANEL: Rgb = (60, 60, 76);

/// `s` cut to fit `w` pixels.
fn fit(core: &Core, s: &str, w: i32) -> String {
    let mut out = s.to_string();
    while crate::online::text_width(core, &out) > w && out.pop().is_some() {}
    out
}

fn text(cv: &mut Rgba<'_>, core: &Core, x: i32, y: i32, s: &str, ink: Rgb, shade: Rgb) -> i32 {
    cv.text(core, x, y, s, ink, shade)
}

pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || !owns(core) {
        return;
    }
    use crate::online::{BAR, BLUE, CREAM, GRAY_INK, INK, LIGHT_GRAY, SHADE, WHITE, YELLOW};
    let n = crate::online_teams::players(core);
    let (plain, pre) = scan(core, n);
    let tab = core.raw_read_8(TAB, -1) as usize;
    let group = if tab == 0 { &plain } else { &pre };
    let at = cursor(core, tab as u32).min(group.len().saturating_sub(1));
    let top = (core.raw_read_16(SCROLL + 2 * tab as u32, -1) as usize).min(group.len().saturating_sub(1));
    let done = core.raw_read_8(DONE, -1);
    let host = crate::online::room_local_seat() == 0;
    let mut canvas = Rgba(rgba);
    let cv = &mut canvas;
    let w = crate::online::W as i32;
    cv.rect(0, 0, w, 144, LIGHT_GRAY);
    // Title bar: the screen's name, and the player counts (only the room's can be picked).
    cv.rect(0, 0, w, 15, BAR);
    text(cv, core, 5, 2, "SELECT MAP", WHITE, GRAY_INK);
    for (k, count) in (2..=5usize).enumerate() {
        let x = 150 + 22 * k as i32;
        let label = format!("{count}P");
        let lw = crate::online::text_width(core, &label);
        if count == n {
            cv.rect(x, 2, 20, 12, YELLOW);
            text(cv, core, x + (20 - lw) / 2, 2, &label, INK, SHADE);
        } else {
            cv.rect(x, 2, 20, 12, PANEL);
            text(cv, core, x + (20 - lw) / 2, 2, &label, GRAY_INK, PANEL);
        }
    }
    // The tabs.
    let labels = [format!("{n}P"), format!("{n}P Pre-Deployed")];
    let mut x = 3;
    for (t, label) in labels.iter().enumerate() {
        let lw = crate::online::text_width(core, label);
        let empty = if t == 0 { plain.is_empty() } else { pre.is_empty() };
        let (bg, ink) = if t == tab {
            (BLUE, WHITE)
        } else if empty {
            (LIGHT_GRAY, SHADE)
        } else {
            (WHITE, INK)
        };
        cv.rect(x, 17, lw + 10, 12, bg);
        text(cv, core, x + 5, 18, label, ink, if t == tab { BLUE } else { SHADE });
        x += lw + 12;
    }
    // The list.
    cv.rect(2, 31, 116, ROWS as i32 * ROW_H + 3, WHITE);
    if group.is_empty() {
        text(cv, core, 8, 36, "No maps for this tab", GRAY_INK, SHADE);
    }
    for (k, &id) in group.iter().skip(top).take(ROWS).enumerate() {
        let y = 32 + ROW_H * k as i32;
        let selected = top + k == at;
        if selected {
            cv.rect(3, y, 112, ROW_H, YELLOW);
        }
        if let Some(i) = info(core, id) {
            text(cv, core, 7, y - 1, &fit(core, &i.name, 104), INK, SHADE);
        }
    }
    // (a bar at the list's side where the cursor is)
    if group.len() > ROWS {
        let (bar_top, bar_h) = (32, ROWS as i32 * ROW_H);
        cv.rect(115, bar_top, 2, bar_h, LIGHT_GRAY);
        let thumb = (bar_h * ROWS as i32 / group.len() as i32).max(4);
        let y = bar_top + (bar_h - thumb) * top as i32 / (group.len() - ROWS) as i32;
        cv.rect(115, y, 2, thumb, GRAY_INK);
    }
    // The map under the cursor: its picture and numbers.
    cv.rect(120, 17, 118, 84, CREAM);
    cv.rect(121, 18, 116, 82, (30, 56, 112));
    if let Some(&id) = group.get(at) {
        draw_preview(core, cv, id, 121, 18, 116, 82);
        if let Some(i) = info(core, id) {
            text(cv, core, 121, 103, &fit(core, &i.name, 116), INK, SHADE);
            text(cv, core, 121, 114, &format!("Size {} x {}", i.w, i.h), INK, SHADE);
            let count = format!("{}/{}", at + 1, group.len());
            let cw = crate::online::text_width(core, &count);
            text(cv, core, 237 - cw, 114, &count, GRAY_INK, SHADE);
            text(cv, core, 121, 125, &format!("Properties {}  Bases {}", i.props, i.bases), INK, SHADE);
        }
    }
    let fail = core.raw_read_8(FAIL, -1) > 0;
    let help = if done == 1 {
        "Starting...".to_string()
    } else if done == 2 {
        "Leaving...".to_string()
    } else if fail {
        "The game did not take that map.".to_string()
    } else if host {
        "Up Down: Map  Left Right: Tab  A: Choose  B: Back".to_string()
    } else {
        format!("{} is choosing the map...", crate::online::room_name(0))
    };
    crate::online::bar(cv, core, &help);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_fits() {
        assert!(FAIL < STATE + STATE_LEN);
        assert_eq!(PREV % 2, 0);
        assert_eq!(CURSOR % 2, 0);
        assert_eq!(SCROLL % 2, 0);
    }
}
