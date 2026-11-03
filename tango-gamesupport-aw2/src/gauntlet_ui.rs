//! The Gauntlet's two choosing screens (docs/dev/gauntlet-mode.md "The flow"): the **map selector** that opens when GAUNTLET is picked on Select Mode and, after the CO pick, the
//! **army colour pick** (the colours the map's enemies do not wear, as emblems in a row).
//!
//! The map selector is the game's own: the War Room's SELECT MAP (`ProcScr_PreviewMap`, `0x08616C54`: the map list, the map's picture, the enemy's face, the record box on R), run as a
//! child of the Gauntlet's start proc exactly as the War Room's flow runs it ([`crate::ds_campaign`]'s `gauntlet_start_script`). Its list is a tab of the map table
//! ([`crate::survival`]'s larger copy, as Survival's): one table entry per Gauntlet map ([`id_of`]: the mission's compiled header, its name, its tiles for the picture, its first enemy
//! CO for the face), shown on Survival's tab while the screen is up ([`TAB`], the War Room's tab byte `0x08090EF2`) with the game mode set to the War Room's (the list builder and the
//! screen read it) and put back when the screen ends ([`chosen`]). The record box reads War Room record rows, here a block of ours filled from the Gauntlet's records ([`rows`]).
//! A (the game's own handler) writes the map's id into the play state, B zeroes it: [`chosen`] reads which, as the War Room's flow does (`0x0803BD6D`).
//!
//! The colour pick is a screen of ours drawn over the finished picture ([`draw`], through `ds_coselect::apply` like the Teams cards): AW2's windows, font and portraits, the emblems of its
//! Teams screen, all read from the ROM at run time, nothing committed (the Teams screen's own colour choice is part of Versus' whole Teams screen and cannot be borrowed alone). The game
//! underneath is a proc of the start script that waits (a flow function that answers 1 while the step is up), so this module owns the pad while the colour pick is up ([`tick`] takes
//! every key) and says which button ended it ([`ANSWER`]).
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
/// The selector's cursor: the mission under the list's cursor (read from the game's list each frame).
const MAP_CURSOR: u32 = STATE + 2;
/// The map picked.
const MAP: u32 = STATE + 3;
/// The colour pick's cursor (an index into the map's free colours).
const COLOUR_CURSOR: u32 = STATE + 4;
/// 1 when the colour pick was left with B: the start script comes round again and goes to the CO screen, not to the selector.
const BACK_TO_CO: u32 = STATE + 5;
/// The play state's game mode as it was before the selector set the War Room's.
const SAVED_MODE: u32 = STATE + 6;
/// The last choice on each map (an army code, 0 none), 8 maps.
const LAST: u32 = STATE + 8;
const LAST_MAPS: usize = 8;
/// The War Room record rows the record box reads: [`LAST_MAPS`] rows of [`ROW`] bytes, in Survival's block of zeroed rows (Survival and the Gauntlet are never open together).
const ROWS: u32 = crate::survival::ROWS;
const ROW: u32 = 0x14;

/// What the step shows (for the tests, which cannot read the picture's words): +0 the maps listed, +1 how many enemies the highlighted map has, +2.. their (CO, colour) in the order they
/// come (6 at most), +0x0E how many colours are free to wear on the map picked, +0x0F.. those army codes (8 at most).
pub const SHOWN: u32 = STATE + 0x20;

/// The CO screen's picks (`gUnknown_030058D4`): the player's CO is the first.
const CO_PICKS: u32 = 0x0300_58D4;

/// The play state's game mode (the War Room's is 2) and map id.
const PLAY_MODE: u32 = 0x0300_3FC1;
const PLAY_MAP: u32 = 0x0300_3FC2;
const WAR_ROOM_MODE: u8 = 2;
/// The War Room's tab byte in the mode -> tab table ([`crate::survival`] sets it for its own list).
const WAR_ROOM_TAB: u32 = 0x0809_0EF2;
/// SELECT MAP's list: the first row shown, the cursor's row (words), the ids ([`crate::five_map::LIST_IDS`]).
const LIST_FIRST: u32 = 0x0300_5900;
const LIST_CURSOR: u32 = 0x0300_5930;
/// The first map-table id of ours (one per mission, [`LAST_MAPS`] at most, up to 0xFD: the table walk's last id with the pack).
pub const FIRST_ID: u8 = 0xF6;

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

/// The start script's call: the map selector opens (the War Room's SELECT MAP follows as a child proc) or, coming back from the colour pick, the CO screen follows at once (the step
/// stays 0, which the script reads as "skip the selector").
pub fn begin_select(core: &mut Core) {
    if core.raw_read_8(BACK_TO_CO, -1) == 1 {
        core.raw_write_8(BACK_TO_CO, -1, 0);
        core.raw_write_8(STEP, -1, 0);
        core.raw_write_8(ANSWER, -1, 1);
        return;
    }
    core.raw_write_8(ANSWER, -1, 0);
    core.raw_write_8(STEP, -1, SELECT);
    core.raw_write_8(MAP_CURSOR, -1, 0);
    // (the screen opens on the first map; it records its pick in the play state's map id, 0 until A)
    core.raw_write_32(LIST_FIRST, -1, 0);
    core.raw_write_32(LIST_CURSOR, -1, 0);
    core.raw_write_8(PLAY_MAP, -1, 0);
    core.raw_write_8(SAVED_MODE, -1, core.raw_read_8(PLAY_MODE, -1));
    frame(core);
}

/// The map-table id of the Gauntlet's mission `m` (one entry each, past the Versus maps' and Survival's).
pub fn id_of(mission: usize) -> u8 {
    FIRST_ID + mission.min(LAST_MAPS - 1) as u8
}

/// The mission of a map-table id of ours.
fn mission_of(id: u8) -> Option<usize> {
    let m = id.checked_sub(FIRST_ID)? as usize;
    (m < gm::entries().len().min(LAST_MAPS)).then_some(m)
}

/// Each frame the selector is up: what the game's list builder and SELECT MAP read is as the Gauntlet wants it. The game mode is the War Room's (the builder lists a tab only for Versus' and the
/// War Room's), the War Room's tab is ours, our maps' entries are in the table on that tab, and the record rows are ours.
fn frame(core: &mut Core) {
    set8(core, PLAY_MODE, WAR_ROOM_MODE);
    set8(core, WAR_ROOM_TAB, crate::survival::TAB as u8);
    entries_in_table(core, true);
    rows(core);
    let rows = ROWS.wrapping_sub(ROW * (FIRST_ID as u32 - 0x6C));
    for at in crate::survival::RECORD_POOLS.into_iter().chain([crate::ds_versus::INSERT_POOL]) {
        if core.raw_read_32(at, -1) != rows {
            core.raw_write_32(at, -1, rows);
        }
    }
}

fn set8(core: &mut Core, at: u32, v: u8) {
    if core.raw_read_8(at, -1) != v {
        core.raw_write_8(at, -1, v);
    }
}

/// The picture area of the screen holds a map of 32 x 22 cells (the largest of the War Room's); a bigger map (Iron Crown, 40 x 26) is shown by its middle part: the picture's tiles (header
/// +0x2C, the battle reads +0x00) are a cropped copy in free ROM past Survival's maps, [`PREVIEW_SIZE`] a mission. Without it the picture ran over the list.
const PREVIEW_ROM: u32 = 0x08E2_0000;
const PREVIEW_SIZE: u32 = 0x800;
const PREVIEW_CELLS: (usize, usize) = (32, 22);

/// The cropped picture's blob for `mission` (LZ77 of width, height, tiles), or None when the whole map fits.
fn preview_blob(e: &Entry) -> Option<&'static Vec<u8>> {
    static B: std::sync::OnceLock<Vec<Option<Vec<u8>>>> = std::sync::OnceLock::new();
    B.get_or_init(|| {
        gm::entries()
            .iter()
            .map(|e| {
                let m = crate::custom_campaign::built_map(e.key)?;
                let (w, h) = (m.width as usize, m.height as usize);
                if w <= PREVIEW_CELLS.0 && h <= PREVIEW_CELLS.1 {
                    return None;
                }
                let (cw, ch) = (w.min(PREVIEW_CELLS.0), h.min(PREVIEW_CELLS.1));
                let (x0, y0) = ((w - cw) / 2, (h - ch) / 2);
                let mut raw = vec![cw as u8, ch as u8];
                for y in 0..ch {
                    for x in 0..cw {
                        raw.extend_from_slice(&m.tiles[(y0 + y) * w + x0 + x].to_le_bytes());
                    }
                }
                let mut lz = crate::lz77::compress(&raw);
                while lz.len() % 4 != 0 {
                    lz.push(0);
                }
                assert!(lz.len() <= PREVIEW_SIZE as usize);
                Some(lz)
            })
            .collect()
    })
    .get(e.mission)?
    .as_ref()
}

/// The Gauntlet's map entries in the map table: each mission's compiled header with the tab the list shows ([`TAB`] while the selector is up, a tab no list shows otherwise).
fn entries_in_table(core: &mut Core, shown: bool) {
    let Some(table) = crate::ds_campaign::selector_table(core) else { return };
    for e in gm::entries().iter().take(LAST_MAPS) {
        let Some(mut h) = crate::ds_campaign::mission_header(core, e.mission) else { continue };
        let tab = if shown { crate::survival::TAB } else { crate::five_map::HIDDEN_TAB };
        h[0x1A..0x1C].copy_from_slice(&tab.to_le_bytes());
        // (the list's own form of a War Room map: the player's slot, then the enemies' COs in the order they come, as many as the screen has faces for)
        h[0x16] = 1;
        h[0x3C] = 0xFF;
        for k in 0..3 {
            h[0x3D + k] = e.enemies.get(k).map_or(0, |en| en.0);
        }
        if let Some(blob) = preview_blob(e) {
            let rom = PREVIEW_ROM + PREVIEW_SIZE * e.mission as u32;
            let mut have = vec![0u8; blob.len()];
            core.raw_read_range(rom, -1, &mut have);
            if &have != blob {
                core.raw_write_range(rom, -1, blob);
            }
            h[0x2C..0x30].copy_from_slice(&rom.to_le_bytes());
        }
        let at = table + crate::five_map::ENTRY * id_of(e.mission) as u32;
        let mut now = [0u8; 0x5C];
        core.raw_read_range(at, -1, &mut now);
        if now != h {
            core.raw_write_range(at, -1, &h);
        }
    }
}

/// The War Room's record rows for our maps (five records of four bytes, in the layout the Gauntlet's own record has: AW2's `CO | days << 8 | score << 20`), the first the Gauntlet's best on the map.
fn rows(core: &mut Core) {
    let mut b = vec![0u8; (ROW as usize) * LAST_MAPS];
    for e in gm::entries().iter().take(LAST_MAPS) {
        // (the map's five results as the War Room keeps them: best first, one word each)
        let at = ROW as usize * e.mission;
        for (k, w) in crate::gauntlet::results_of(core, e.mission).iter().enumerate() {
            b[at + 4 * k..at + 4 * k + 4].copy_from_slice(&w.to_le_bytes());
        }
    }
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(ROWS, -1, &mut now);
    if now != b {
        core.raw_write_range(ROWS, -1, &b);
    }
}

/// The selector's screen has ended (the start script's call): A put a map's id in the play state, B zeroed it. The game mode is put back; a map taken becomes the session's mission.
pub fn chosen(core: &mut Core) {
    let id = core.raw_read_8(PLAY_MAP, -1);
    leave(core);
    match mission_of(id) {
        Some(m) => {
            core.raw_write_8(MAP, -1, m as u8);
            // (the battle is played on the campaign's own entry, [`crate::ds_campaign::choose_gauntlet_map`] fills it)
            core.raw_write_8(PLAY_MAP, -1, crate::campaign_model::MAP_ID);
            crate::ds_campaign::choose_gauntlet_map(core, m);
            core.raw_write_8(ANSWER, -1, 1);
        }
        None => core.raw_write_8(ANSWER, -1, 0),
    }
}

/// The selector is over (or the session is not): the game mode as it was, our entries off every list.
fn leave(core: &mut Core) {
    if step(core) == SELECT {
        let saved = core.raw_read_8(SAVED_MODE, -1);
        core.raw_write_8(PLAY_MODE, -1, saved);
    }
    entries_in_table(core, false);
    core.raw_write_8(STEP, -1, 0);
}

/// The map selector is up.
pub fn selecting(core: &Core) -> bool {
    step(core) == SELECT
}

/// The scroll bar's track is drawn with a sprite for every 8 pixels of a length worked out as the rows a page shows over the list's last row, a length meant for a list of dozens of
/// maps: a list of two is a track of ~100 sprites, which overflows the sprite buffer into the registers the frame is shown with. The track is at most its own full length (`0x70`),
/// the thumb the whole of it. (`0x0808731A`: the length, in r0 after its division.)
const SCROLL_TRACK: u32 = 0x0808_731A;

fn scroll_track(core: &mut Core) {
    if !selecting(core) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    if cpu.gpr(0) as u32 > 0x70 {
        cpu.set_gpr(0, 0x70);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(SCROLL_TRACK, Box::new(scroll_track))]
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
        leave(core);
        return keys;
    }
    let pressed = keys & !prev;
    if s != SELECT {
        mirror(core);
    }
    match s {
        SELECT => {
            // The game's own screen takes the pad (A and B end it); only what it reads is kept as the Gauntlet wants it.
            frame(core);
            let list_at = crate::five_map::LIST_IDS + (core.raw_read_32(LIST_FIRST, -1) + core.raw_read_32(LIST_CURSOR, -1)).min(crate::five_map::LIST_CAP - 1);
            if let Some(m) = mission_of(core.raw_read_8(list_at, -1)) {
                core.raw_write_8(MAP_CURSOR, -1, m as u8);
            }
            mirror(core);
            return keys;
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
    // (the map selector is the game's own screen: nothing is drawn over it)
    if s != COLOUR {
        return false;
    }
    let mut cv = Rgba(rgba);
    cv.rect(0, 0, W as i32, online::H as i32, SEA);
    if let Some(e) = picked(core) {
        // (the CO screen's pick list outlives the screen: its first entry is the player's CO)
        colour_pick(&mut cv, core, e, core.raw_read_8(COLOUR_CURSOR, -1) as usize, core.raw_read_8(CO_PICKS, -1));
    }
    true
}

/// The colour pick's picture for map `e` (the text audit's page).
pub fn paint_colour_pick(core: &Core, rgba: &mut [u8], e: &Entry, cursor: usize, co: u8) {
    let mut cv = Rgba(rgba);
    cv.rect(0, 0, W as i32, online::H as i32, SEA);
    colour_pick(&mut cv, core, e, cursor, co);
}
