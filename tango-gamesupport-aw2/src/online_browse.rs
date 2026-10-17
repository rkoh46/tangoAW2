//! The lobby browser (level 7 of the in-game lobby, [`crate::online`]): JOIN lists the public lobbies, drawn in the
//! lobby's own window and bar. The first line is "Enter a code" (the code page of old); the others are the lobbies
//! the app found on the public relays (`tango_lobby::browse`), each with its host's gamertag, a padlock when it has
//! a password and how many of its seats are taken. UP and DOWN pick, A joins (a locked one asks for its password on
//! the password page first), B goes back.
//!
//! The mailbox (EWRAM [`STATE`], the app's half in [`mailbox`]): the app writes the rows and how the search stands;
//! the game keeps its own cursor and remembers *which lobby* it is on (by code), so a list that changes under the
//! cursor does not move it onto another lobby.

use mgba::core::Core;

use crate::online::{
    bar, text_width, Rgb, Rgba, BLUE, GRAY_INK, INK, KEY_A, KEY_B, KEY_DOWN, KEY_UP, LIGHT_GRAY, RED, SHADE, WHITE,
    YELLOW,
};

pub const STATE: u32 = 0x0203_D500;
pub const STATE_LEN: u32 = 0x100;
/// Rows the app wrote.
const COUNT: u32 = STATE;
/// The item under the cursor (0 is "Enter a code", n the nth lobby).
const CURSOR: u32 = STATE + 1;
/// The first item shown.
const TOP: u32 = STATE + 2;
/// How the search stands (the app's): see [`Net`].
const NET: u32 = STATE + 3;
/// 1 when the code or password page was opened from here (B comes back here).
pub const FROM: u32 = STATE + 4;
/// The code of the lobby under the cursor (zero-padded; empty on "Enter a code").
const SELECTED: u32 = STATE + 6;
/// The game version, drawn in the title line (zero-terminated).
const VERSION: u32 = STATE + 0x0C;
const VERSION_LEN: usize = 0x0C;
/// The rows: [`ROW_SIZE`] bytes each: the code (6), players, seats, flags (1 padlock), the host (zero-terminated).
const ROWS: u32 = STATE + 0x18;
pub const ROW_SIZE: u32 = 24;
pub const MAX_ROWS: usize = 9;
const HOST_AT: usize = 9;
pub const HOST_CHARS: usize = ROW_SIZE as usize - HOST_AT - 1;

/// How the search for lobbies stands.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum Net {
    /// Not answered yet.
    Looking = 0,
    /// The relays answer: an empty list is an empty list.
    Ok = 1,
    /// No relay could be reached.
    Offline = 2,
}

/// One lobby as the game shows it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Row {
    pub code: String,
    pub host: String,
    pub players: u8,
    pub max: u8,
    pub locked: bool,
}

const LOCKED: u8 = 1;

/// The app's half.
pub mod mailbox {
    use super::*;

    /// Writes the rows (at most [`MAX_ROWS`]), the search's state and the version drawn on the page.
    pub fn write(write: &mut dyn FnMut(u32, &[u8]), rows: &[Row], net: Net, version: &str) {
        let mut b = vec![0u8; ROW_SIZE as usize * MAX_ROWS];
        for (k, r) in rows.iter().take(MAX_ROWS).enumerate() {
            let o = k * ROW_SIZE as usize;
            for (i, c) in r.code.bytes().take(6).enumerate() {
                b[o + i] = c;
            }
            b[o + 6] = r.players;
            b[o + 7] = r.max;
            b[o + 8] = if r.locked { LOCKED } else { 0 };
            for (i, c) in r
                .host
                .chars()
                .filter(|c| c.is_ascii() && !c.is_ascii_control())
                .take(HOST_CHARS)
                .enumerate()
            {
                b[o + HOST_AT + i] = c as u8;
            }
        }
        write(ROWS, &b);
        let mut v = [0u8; VERSION_LEN];
        for (i, c) in version.bytes().filter(|c| c.is_ascii_graphic()).take(VERSION_LEN - 1).enumerate() {
            v[i] = c;
        }
        write(VERSION, &v);
        write(COUNT, &[rows.len().min(MAX_ROWS) as u8]);
        write(NET, &[net as u8]);
    }
}

fn rows(core: &Core) -> Vec<Row> {
    let n = (core.raw_read_8(COUNT, -1) as usize).min(MAX_ROWS);
    (0..n)
        .map(|k| {
            let mut b = [0u8; ROW_SIZE as usize];
            core.raw_read_range(ROWS + ROW_SIZE * k as u32, -1, &mut b);
            let text = |s: &[u8]| s.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect::<String>();
            Row {
                code: text(&b[..6]),
                players: b[6],
                max: b[7],
                locked: b[8] & LOCKED != 0,
                host: text(&b[HOST_AT..]),
            }
        })
        .collect()
}

fn net(core: &Core) -> Net {
    match core.raw_read_8(NET, -1) {
        1 => Net::Ok,
        2 => Net::Offline,
        _ => Net::Looking,
    }
}

/// Items visible at once (the page's window holds 8 lines; "Enter a code" is the first item).
pub const VISIBLE: usize = 8;

/// The cursor after a move (wrapping), and the first item shown.
pub fn step(cursor: usize, top: usize, items: usize, down: bool) -> (usize, usize) {
    let cursor = if down { (cursor + 1) % items } else { (cursor + items - 1) % items };
    (cursor, scroll(cursor, top, items))
}

/// The first item shown so that `cursor` is in view.
pub fn scroll(cursor: usize, top: usize, items: usize) -> usize {
    let top = top.min(items.saturating_sub(VISIBLE));
    if cursor < top {
        cursor
    } else if cursor >= top + VISIBLE {
        cursor + 1 - VISIBLE
    } else {
        top
    }
}

/// Where the cursor is after the list changed: on the lobby that was selected if it is still there; a vanished one
/// puts it on "Enter a code" rather than on another lobby by surprise.
pub fn settle(selected: &str, rows: &[Row]) -> usize {
    if selected.is_empty() {
        return 0;
    }
    match rows.iter().position(|r| r.code == selected) {
        Some(k) => k + 1,
        None => 0,
    }
}

/// Opened from the LOBBY menu's JOIN.
pub fn open(core: &mut Core) {
    core.raw_write_8(CURSOR, -1, 0);
    core.raw_write_8(TOP, -1, 0);
    core.raw_write_range(SELECTED, -1, &[0u8; 6]);
    core.raw_write_8(FROM, -1, 0);
    core.raw_write_8(crate::online::TYPED_LEN, -1, 0);
}

/// Every frame at level 7: moves the cursor, A and B. Returns what the game should do next.
pub fn tick(core: &mut Core, pressed: u32) -> Pick {
    let rows = rows(core);
    let items = rows.len() + 1;
    // The lobby that was selected, wherever it is now.
    let mut sel = [0u8; 6];
    core.raw_read_range(SELECTED, -1, &mut sel);
    let selected: String = sel.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect();
    let mut cursor = (core.raw_read_8(CURSOR, -1) as usize).min(items - 1);
    if !selected.is_empty() {
        cursor = settle(&selected, &rows);
    }
    let mut top = core.raw_read_8(TOP, -1) as usize;
    if pressed & KEY_DOWN != 0 {
        (cursor, top) = step(cursor, top, items, true);
    } else if pressed & KEY_UP != 0 {
        (cursor, top) = step(cursor, top, items, false);
    }
    top = scroll(cursor, top, items);
    core.raw_write_8(CURSOR, -1, cursor as u8);
    core.raw_write_8(TOP, -1, top as u8);
    let mut s = [0u8; 6];
    if cursor > 0 {
        for (k, c) in rows[cursor - 1].code.bytes().take(6).enumerate() {
            s[k] = c;
        }
    }
    core.raw_write_range(SELECTED, -1, &s);
    if pressed & KEY_B != 0 {
        Pick::Back
    } else if pressed & KEY_A != 0 {
        if cursor == 0 {
            Pick::Code
        } else {
            let r = &rows[cursor - 1];
            if r.players >= r.max {
                Pick::Full
            } else if r.locked {
                Pick::Locked(r.code.clone())
            } else {
                Pick::Open(r.code.clone())
            }
        }
    } else {
        Pick::Nothing
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Pick {
    Nothing,
    Back,
    /// Type a code.
    Code,
    /// Join this one at once.
    Open(String),
    /// This one asks for a password.
    Locked(String),
    /// The lobby is full (said in the bar).
    Full,
}

/// A padlock, 5 wide and 7 tall.
pub(crate) fn padlock(cv: &mut Rgba, x: i32, y: i32, ink: Rgb) {
    cv.rect(x + 1, y, 3, 1, ink);
    cv.rect(x, y + 1, 1, 2, ink);
    cv.rect(x + 4, y + 1, 1, 2, ink);
    cv.rect(x, y + 3, 5, 4, ink);
}

/// `s` cut with ".." so that it is at most `width` pixels wide.
pub fn fit(core: &Core, s: &str, width: i32) -> String {
    if text_width(core, s) <= width {
        return s.to_string();
    }
    let mut t: String = s.to_string();
    while !t.is_empty() && text_width(core, &format!("{t}..")) > width {
        t.pop();
    }
    format!("{t}..")
}

/// The first of `options` that fits the bar (the last if none does, cut by [`fit`]).
fn bar_text(core: &Core, options: &[&str]) -> String {
    let max = crate::online::W as i32 - 8;
    options
        .iter()
        .find(|o| text_width(core, o) <= max)
        .map_or_else(|| fit(core, options[options.len() - 1], max), |o| o.to_string())
}

/// The browser's page, over the ONLINE screen.
pub(crate) fn apply(cv: &mut Rgba, core: &Core) {
    let (x, y, w, h) = crate::online::PANEL;
    cv.window(x, y, w, h);
    let rows = rows(core);
    let items = rows.len() + 1;
    let cursor = (core.raw_read_8(CURSOR, -1) as usize).min(items - 1);
    let top = scroll(cursor, core.raw_read_8(TOP, -1) as usize, items);
    // The title line: what this is, and the version whose lobbies are listed.
    let mut v = [0u8; VERSION_LEN];
    core.raw_read_range(VERSION, -1, &mut v);
    let version: String = v.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect();
    cv.text(core, x + 6, y + 5, "Lobbies", GRAY_INK, SHADE);
    if !version.is_empty() {
        // (a pre-release suffix is left off: "v0.10.12", never cut)
        let t = format!("v{}", version.split('-').next().unwrap_or(&version));
        cv.text(core, x + w - 6 - text_width(core, &t), y + 5, &t, GRAY_INK, SHADE);
    }
    let line = 12;
    let ly = y + 17;
    let state = net(core);
    for slot in 0..VISIBLE {
        let item = top + slot;
        if item >= items {
            break;
        }
        let ry = ly + line * slot as i32;
        let on = item == cursor;
        if on {
            cv.rect(x + 3, ry - 1, w - 6, line, YELLOW);
        } else {
            cv.rect(x + 4, ry + line - 2, w - 8, 1, LIGHT_GRAY);
        }
        if item == 0 {
            cv.text(core, x + 8, ry, "Enter a code", INK, SHADE);
            continue;
        }
        let r = &rows[item - 1];
        let seats = format!("{}/{}", r.players, r.max);
        let full = r.players >= r.max;
        let sw = text_width(core, &seats);
        let ink = if full { GRAY_INK } else { INK };
        cv.text(core, x + w - 7 - sw, ry, &seats, if full { RED } else { BLUE }, SHADE);
        if r.locked {
            padlock(cv, x + 6, ry + 1, ink);
        }
        let name = fit(core, &if r.host.is_empty() { "Player".to_string() } else { r.host.clone() }, w - 7 - sw - 8 - 14);
        cv.text(core, x + 14, ry, &name, ink, SHADE);
    }
    // More above or below.
    if top > 0 {
        // (mid-title, clear of the version at the right)
        let ax = x + w / 2 - 6;
        cv.rect(ax, y + 7, 5, 1, GRAY_INK);
        cv.rect(ax + 1, y + 6, 3, 1, GRAY_INK);
        cv.rect(ax + 2, y + 5, 1, 1, GRAY_INK);
    }
    if top + VISIBLE < items {
        // (in the title line too, beside the up arrow: the last row owns the panel's foot)
        let ax = x + w / 2 + 4;
        cv.rect(ax, y + 5, 5, 1, GRAY_INK);
        cv.rect(ax + 1, y + 6, 3, 1, GRAY_INK);
        cv.rect(ax + 2, y + 7, 1, 1, GRAY_INK);
    }
    // Only the list itself is empty (the first line is always there): say so under it.
    if rows.is_empty() {
        let (a, ink) = match state {
            Net::Looking => ("Searching for lobbies...", GRAY_INK),
            Net::Ok => ("No lobbies right now", GRAY_INK),
            Net::Offline => ("The lobby list cannot be reached.", RED),
        };
        // (a line that is too long goes to two, whole)
        let mut at = ly + line + 14;
        for t in crate::online::wrap(core, a, w - 12) {
            cv.text(core, x + (w - text_width(core, &t)) / 2, at, &t, ink, SHADE);
            at += 13;
        }
        if state == Net::Offline {
            for t in crate::online::wrap(core, "Type a room's code instead.", w - 12) {
                cv.text(core, x + (w - text_width(core, &t)) / 2, at + 1, &t, GRAY_INK, SHADE);
                at += 13;
            }
        }
    }
    let text = if cursor == 0 {
        bar_text(core, &["A: Type a code  B: Back", "A: Code  B: Back"])
    } else {
        let r = &rows[cursor - 1];
        if r.players >= r.max {
            bar_text(core, &["This lobby is full.  B: Back", "Full.  B: Back"])
        } else if r.locked {
            bar_text(core, &["A: Join (needs a password)  B: Back", "A: Join (password)  B: Back", "A: Join  B: Back"])
        } else {
            bar_text(core, &["A: Join  B: Back"])
        }
    };
    bar(cv, core, &text);
    let _ = WHITE;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(code: &str) -> Row {
        Row {
            code: code.into(),
            host: "x".into(),
            players: 1,
            max: 5,
            locked: false,
        }
    }

    #[test]
    fn layout_fits() {
        assert!(ROWS + ROW_SIZE * MAX_ROWS as u32 <= STATE + STATE_LEN);
        assert!(VERSION + VERSION_LEN as u32 <= ROWS);
        assert!(SELECTED + 6 <= VERSION);
        assert_eq!(HOST_AT, 9);
        assert!(HOST_CHARS >= 12);
    }

    #[test]
    fn cursor_wraps_and_scrolls() {
        // 4 items: down from the last wraps to the first.
        assert_eq!(step(3, 0, 4, true), (0, 0));
        assert_eq!(step(0, 0, 4, false), (3, 0));
        // 10 items, 8 visible: going down past the window scrolls it; wrapping to the end shows the end.
        assert_eq!(step(7, 0, 10, true), (8, 1));
        assert_eq!(step(0, 0, 10, false), (9, 2));
        assert_eq!(step(9, 2, 10, true), (0, 0));
        // (a list that got shorter)
        assert_eq!(scroll(1, 5, 3), 0);
    }

    #[test]
    fn the_cursor_follows_its_lobby() {
        let rows = vec![row("AAAAAA"), row("BBBBBB"), row("CCCCCC")];
        assert_eq!(settle("BBBBBB", &rows), 2);
        let after = vec![row("CCCCCC"), row("BBBBBB")];
        assert_eq!(settle("BBBBBB", &after), 2);
        // gone: back on "Enter a code" rather than on someone else's lobby
        assert_eq!(settle("AAAAAA", &after), 0);
        assert_eq!(settle("", &after), 0);
    }
}
