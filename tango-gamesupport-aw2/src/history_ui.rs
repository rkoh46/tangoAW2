//! The History screen (Dual Strike's `HistoryScreen_Init` and its tab list, docs/AW2.md "History"), with the pack,
//! offline: the record's counters (crate::history) in Dual Strike's four tabs (General, Built, Destroyed, Objects),
//! each row with its label, its value and its three medal slots, the medals earned of all there are, and the help
//! line of the row (or of the medal under the cursor), fitted to one GBA screen.
//!
//! Where: L on Survival's SELECT MAP (crate::survival_ui's screen, which this one takes over while it is open: the
//! same BG0 picture pipeline, Dual Strike's title font and wallpaper). UP and DOWN move the cursor over the rows,
//! LEFT and RIGHT over the row and its medals, L and R change the tab, B closes it; the game gets no button
//! meanwhile.
//!
//! Dual Strike's own wording and art, from the pack (nothing of it is in the repository): the rows' labels and help
//! texts (text bank 0x7A), the thresholds (the table `0x0215D6C4`), the medal (`ohashi/res_history_medal`: its
//! first LZ stream, a 16x16 quad of tiles, its palette at +0x2B4), drawn with BG palette bank 2 (the game's bank 2,
//! kept in [`STATE`] while the screen is open, is put back when it closes). The units' names (Built, Destroyed)
//! and the Objects' are tangoAW2's.

use mgba::core::Core;
use std::sync::OnceLock;

use crate::history::{self, Entry};
use crate::survival_ui::{self as ui, Art, Canvas};

// --- State (tangoAW2's 0x0203C340..0x0203C39F) -------------------------------------------

pub const STATE: u32 = 0x0203_C340;
pub const STATE_LEN: u32 = 0x60;
const OPEN: u32 = STATE;
const TAB: u32 = STATE + 1;
const TOP: u32 = STATE + 2;
const ROW: u32 = STATE + 3;
const COLUMN: u32 = STATE + 4;
const SIGNATURE: u32 = STATE + 8;
/// The game's BG palette bank 2 (its buffer's), while the screen has it.
const SAVED_BANK: u32 = STATE + 0x20;

const MEDAL_BANK: usize = 2;
const BANK_BYTES: u32 = 32;

pub fn open(core: &Core) -> bool {
    core.raw_read_8(OPEN, -1) == 1
}

/// L on SELECT MAP: the screen opens on the first tab.
pub fn open_now(core: &mut Core) {
    if history::tabs().is_none() || medal_art().is_none() {
        return;
    }
    history::ensure(core);
    let mut bank = [0u8; BANK_BYTES as usize];
    core.raw_read_range(ui::PAL_BUFFER + BANK_BYTES * MEDAL_BANK as u32, -1, &mut bank);
    core.raw_write_range(SAVED_BANK, -1, &bank);
    core.raw_write_range(OPEN, -1, &[1, 0, 0, 0, 0]);
    core.raw_write_32(SIGNATURE, -1, 0);
}

/// The screen closes (B, or SELECT MAP gone): the game's palette bank 2 back.
pub fn close(core: &mut Core) {
    if !open(core) {
        return;
    }
    core.raw_write_8(OPEN, -1, 0);
    let mut bank = [0u8; BANK_BYTES as usize];
    core.raw_read_range(SAVED_BANK, -1, &mut bank);
    let at = BANK_BYTES * MEDAL_BANK as u32;
    core.raw_write_range(ui::PAL_BUFFER + at, -1, &bank);
    core.raw_write_range(ui::PAL_RAM + at, -1, &bank);
}

// --- The medal ------------------------------------------------------------------------------

struct Medal {
    /// 16x16, 0 clear, indexes of `pal`.
    px: Vec<u8>,
    /// Bank 2: the medal's colours, and in its unused indexes the colours of the cells around it ([`Free`]).
    pal: [u16; 16],
}

/// Bank 2's indexes the medal leaves free, for the colours of the cells around it.
#[derive(Clone, Copy)]
struct Free {
    white: u8,
    cursor: u8,
    red: u8,
    gray: u8,
}

fn medal_art() -> Option<&'static (Medal, Free)> {
    static ART: OnceLock<Option<(Medal, Free)>> = OnceLock::new();
    ART.get_or_init(|| {
        let f = crate::ds_pack::pack()?.file("ohashi/res_history_medal")?;
        let (tiles, _) = ui::lz10_stream(f, 0)?;
        let mut pal = ui::palette(f, 0x2B4)?;
        let mut px = vec![0u8; 16 * 16];
        for t in 0..4 {
            for y in 0..8 {
                for x in 0..8 {
                    px[16 * (8 * (t / 2) + y) + 8 * (t % 2) + x] = ui::tile_px(&tiles, t, x, y);
                }
            }
        }
        let mut free = (1..16u8).filter(|&i| !px.contains(&i));
        let mut take = |c: (u8, u8, u8)| {
            let i = free.next()?;
            pal[i as usize] = ui::rgb15(c);
            Some(i)
        };
        let colour = |i: u8| ui::BANK0[i as usize];
        let free = Free {
            white: take(colour(ui::WHITE))?,
            cursor: take(colour(ui::CREAM))?,
            red: take(colour(ui::RED))?,
            gray: take(colour(ui::LIGHT_GRAY))?,
        };
        Some((Medal { px, pal }, free))
    })
    .as_ref()
}

// --- The rows -------------------------------------------------------------------------------

const TAB_NAMES: [&str; 4] = ["General", "Built", "Destroyed", "Objects"];

/// Unit names by Dual Strike's type (1..26).
const UNIT_NAMES: [&str; 27] = [
    "-", "Infantry", "Mech", "Md Tank", "Megatank", "Tank", "Recon", "APC", "Neotank", "Piperunner", "Artillery",
    "Rockets", "Stealth", "Black Bomb", "Anti-Air", "Missiles", "Fighter", "Bomber", "Black Boat", "B Copter",
    "T Copter", "Battleship", "Cruiser", "Lander", "Sub", "Carrier", "Oozium",
];

/// Dual Strike's text (its History's labels and help), in the characters AW2's font has.
fn ds_text(id: u32) -> String {
    let Some(pack) = crate::ds_pack::pack() else { return String::new() };
    let Some(ds) = crate::ds_campaign_data::Ds::from_pack(pack) else { return String::new() };
    let t = ds.text(id).unwrap_or_default();
    let s: String = t.iter().map(|&c| if (0x20..0x7F).contains(&c) { c as char } else { ' ' }).collect();
    // (the play time is this game's)
    s.trim().replace("Advance Wars: Dual Strike", "Advance Wars")
}

fn label(e: &Entry) -> String {
    if let Some(t) = e.unit {
        return UNIT_NAMES.get(t as usize).copied().unwrap_or("?").to_string();
    }
    match e.counter {
        history::BLACK_CANNONS => "Black Cannons".into(),
        history::MINICANNONS => "Minicannons".into(),
        history::OBELISKS => "Black Obelisks".into(),
        history::CRYSTALS => "Black Crystals".into(),
        history::PIPE_SEAMS => "Pipe seams".into(),
        // (Dual Strike's "top screen" is its other front)
        history::SENT => "Units sent to other front".into(),
        _ => ds_text(e.text),
    }
}

fn value_text(core: &Core, e: &Entry) -> String {
    let v = history::get(core, e.counter);
    if e.time {
        let minutes = v / 3600;
        format!("{}:{:02}", minutes / 60, minutes % 60)
    } else {
        v.to_string()
    }
}

fn help(e: &Entry, column: usize) -> String {
    ds_text(e.help[column.min(3)])
}

/// Words of `s` in lines of at most `width` pixels.
fn wrap(core: &Core, s: &str, width: i32) -> Vec<String> {
    let mut lines = Vec::new();
    let mut line = String::new();
    for w in s.split_whitespace() {
        let next = if line.is_empty() { w.to_string() } else { format!("{line} {w}") };
        if ui::text_width(core, &next) > width && !line.is_empty() {
            lines.push(std::mem::replace(&mut line, w.to_string()));
        } else {
            line = next;
        }
    }
    if !line.is_empty() {
        lines.push(line);
    }
    lines
}

// --- Drawing ----------------------------------------------------------------------------------

const ROWS: usize = 5;
const WIN: (i32, i32, i32, i32) = (8, 44, 224, 88);
const ROW_Y: i32 = 48;
const ROW_H: i32 = 16;
const MEDAL_X: i32 = 168;
const VALUE_RIGHT: i32 = 162;

/// A 16x16 medal cell (bank 2) at (x, y), 8-aligned: the medal, or its empty slot; the row's ground; a red frame
/// when the cursor is on it.
fn medal_cell(cv: &mut Canvas, x: i32, y: i32, earned: bool, ground: u8, framed: bool) {
    let Some((m, f)) = medal_art() else { return };
    for cy in 0..2 {
        for cx in 0..2 {
            let cell = (ui::W / 8) * ((y / 8 + cy) as usize) + (x / 8 + cx) as usize;
            if let Some(b) = cv.bank.get_mut(cell) {
                *b = MEDAL_BANK as u8;
            }
        }
    }
    for yy in 0..16 {
        for xx in 0..16 {
            let mut v = ground;
            if earned {
                let p = m.px[16 * yy + xx];
                if p != 0 {
                    v = p;
                }
            } else {
                // an empty slot: a small ring
                let (dx, dy) = (2 * xx as i32 - 15, 2 * yy as i32 - 17);
                let d = dx * dx + dy * dy;
                if (64..=100).contains(&d) {
                    v = f.gray;
                }
            }
            if framed && (xx == 0 || yy == 0 || xx == 15 || yy == 15) {
                v = f.red;
            }
            cv.put(x + xx as i32, y + yy as i32, v);
        }
    }
}

fn draw(core: &mut Core, a: &Art, tab: usize, top: usize, row: usize, column: usize) {
    let Some(tabs) = history::tabs() else { return };
    let Some((m, f)) = medal_art() else { return };
    let rows = &tabs[tab];
    let mut cv = Canvas::new(a);
    a.title(&mut cv, 1, "HISTORY");
    // The medals earned, at the right.
    let (earned, total) = history::medal_count(core);
    let n = format!("{earned}/{total}");
    let w = ui::text_width(core, &n).max(ui::text_width(core, "Medals"));
    cv.rect(232 - w - 6, 3, w + 6, 25, ui::WHITE);
    cv.rect(232 - w - 6, 3, w + 6, 1, ui::RED);
    cv.text(core, 232 - w - 3, 4, "Medals", ui::GRAY_INK, ui::SHADE);
    cv.text(core, 232 - ui::text_width(core, &n) - 3, 15, &n, ui::INK, ui::SHADE);
    // The tabs.
    for (k, name) in TAB_NAMES.iter().enumerate() {
        let x = 8 + 56 * k as i32;
        let on = k == tab;
        cv.rect(x, 31, 55, 12, if on { ui::WHITE } else { ui::LIGHT_GRAY });
        cv.rect(x, 31, 55, 2, if on { ui::RED } else { ui::GRAY });
        let tw = ui::text_width(core, name);
        cv.text(core, x + (55 - tw) / 2, 32, name, if on { ui::INK } else { ui::GRAY_INK }, ui::SHADE);
    }
    // The rows.
    let (x, y, w, h) = WIN;
    cv.window(x, y, w, h);
    for i in 0..ROWS {
        let Some(e) = rows.get(top + i) else { break };
        let ry = ROW_Y + ROW_H * i as i32;
        let here = top + i == row;
        let ground = if here { ui::CREAM } else { ui::WHITE };
        if here {
            cv.rect(x + 3, ry, w - 6, ROW_H, ui::CREAM);
        }
        cv.rect(x + 6, ry + ROW_H - 1, w - 12, 1, ui::LIGHT_GRAY);
        let l = label(e);
        let mut lx = x + 6;
        if e.unit.is_some() && tab == 2 {
            // (Destroyed: the enemy's units)
            lx = cv.text(core, lx, ry + 3, "Enemy", ui::GRAY_INK, ui::SHADE) + 4;
        }
        cv.text(core, lx, ry + 3, &l, ui::INK, ui::SHADE);
        let v = value_text(core, e);
        cv.text(core, VALUE_RIGHT - ui::text_width(core, &v), ry + 3, &v, ui::INK, ui::SHADE);
        let got = history::medals(core, e);
        for k in 0..3 {
            let mg = if here { f.cursor } else { f.white };
            medal_cell(&mut cv, MEDAL_X + 16 * k as i32, ry, k < got, mg, here && column == k + 1);
        }
        // (the separator under the medals, in their bank)
        for k in 0..3 {
            let mx = MEDAL_X + 16 * k as i32;
            for xx in 0..16 {
                let at = ui::W * (ry + ROW_H - 1) as usize + (mx + xx) as usize;
                if cv.px[at] == ground || cv.px[at] == f.white || cv.px[at] == f.cursor {
                    cv.px[at] = f.gray;
                }
            }
        }
    }
    if top > 0 {
        ui::arrow(&mut cv, 220, y + 4, true);
    }
    if top + ROWS < rows.len() {
        ui::arrow(&mut cv, 220, y + h - 9, false);
    }
    // Where the cursor is, of how many.
    let pos = format!("{}/{}", row + 1, rows.len());
    cv.text(core, 12, 18, &pos, ui::GRAY_INK, ui::SHADE);
    // The help: the row's, or its medal's.
    cv.rect(0, 134, ui::W as i32, 26, ui::WHITE);
    cv.rect(0, 134, ui::W as i32, 1, ui::RED);
    if let Some(e) = rows.get(row) {
        let lines = wrap(core, &help(e, column), 228);
        for (k, l) in lines.iter().take(2).enumerate() {
            cv.text(core, 6, 136 + 12 * k as i32, l, ui::INK, ui::SHADE);
        }
    }
    let (tiles, map) = ui::tiles_of(&cv);
    let (chars, screen) = ui::bg0(core);
    ui::write_if_changed(core, chars, &tiles);
    ui::write_if_changed(core, screen, &map);
    let mut pal = ui::palettes(a);
    for c in m.pal {
        pal.extend_from_slice(&c.to_le_bytes());
    }
    ui::write_if_changed(core, ui::PAL_BUFFER, &pal);
    ui::write_if_changed(core, ui::PAL_RAM, &pal);
}

/// While the screen is open (crate::survival_ui's tick, SELECT MAP up): the keys, then the picture when what it
/// shows changed. Returns the keys the game gets (none).
pub(crate) fn tick(core: &mut Core, a: &Art, keys: u32, prev: u32) -> u32 {
    let Some(tabs) = history::tabs() else {
        close(core);
        return keys;
    };
    let pressed = keys & !prev;
    let mut tab = (core.raw_read_8(TAB, -1) as usize).min(3);
    let mut row = core.raw_read_8(ROW, -1) as usize;
    let mut top = core.raw_read_8(TOP, -1) as usize;
    let mut column = (core.raw_read_8(COLUMN, -1) as usize).min(3);
    const UP: u32 = 1 << 6;
    const DOWN: u32 = 1 << 7;
    if pressed & ui::KEY_B != 0 {
        close(core);
        return keys & !0x3FF;
    }
    if pressed & (ui::KEY_R | ui::KEY_L) != 0 {
        tab = if pressed & ui::KEY_R != 0 { (tab + 1) % 4 } else { (tab + 3) % 4 };
        (row, top) = (0, 0);
    }
    let n = tabs[tab].len().max(1);
    if pressed & DOWN != 0 {
        row = (row + 1) % n;
    }
    if pressed & UP != 0 {
        row = (row + n - 1) % n;
    }
    if pressed & ui::KEY_RIGHT != 0 {
        column = (column + 1).min(3);
    }
    if pressed & ui::KEY_LEFT != 0 {
        column = column.saturating_sub(1);
    }
    row = row.min(n - 1);
    if row < top {
        top = row;
    }
    if row >= top + ROWS {
        top = row + 1 - ROWS;
    }
    core.raw_write_range(TAB, -1, &[tab as u8, top as u8, row as u8, column as u8]);
    // Redrawn when what it shows changes (the values as shown: play time by the minute).
    let mut sig = vec![tab as u8, top as u8, row as u8, column as u8];
    let (earned, _) = history::medal_count(core);
    sig.extend_from_slice(&earned.to_le_bytes());
    for e in tabs[tab].iter().skip(top).take(ROWS) {
        sig.extend_from_slice(value_text(core, e).as_bytes());
    }
    let sig = ui::hash(&sig) | 1;
    let d = core.raw_read_16(ui::DISP_CT, -1);
    if d & ui::WINDOWS != 0 {
        core.raw_write_16(ui::DISP_CT, -1, d & !ui::WINDOWS);
    }
    if core.raw_read_32(SIGNATURE, -1) != sig {
        draw(core, a, tab, top, row, column);
        core.raw_write_32(SIGNATURE, -1, sig);
    }
    keys & !0x3FF
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_fits() {
        assert!(SAVED_BANK + BANK_BYTES <= STATE + STATE_LEN);
        assert_eq!(UNIT_NAMES[25], "Carrier");
    }
}
