//! The gamertag and the online record (docs/AW2.md "Gamertag and STATS").
//!
//! **Gamertag.** The name a player goes by online (the app's `config.nickname`): the LOBBY level's third item
//! (GAMERTAG) opens a typing page (level 6 of [`crate::online`], the code grid's letters and digits, up to
//! [`TAG_CHARS`], or the keyboard); the first visit to the ONLINE screen asks when none is set. The game keeps the
//! committed name at [`GAMERTAG`] and asks the app to keep it (request 7); the app also writes it there when the
//! console starts ([`SYNCED`]). The ONLINE and LOBBY screens show it ([`draw_tag`]).
//!
//! **STATS.** The ONLINE screen's third item shows the player's own record, kept by the app in the profile's data
//! folder: the app writes the page's lines into [`LINES`] ("label", a tab, "value") and the game draws them, UP and
//! DOWN scrolling ([`draw_stats`]). Nothing here is read back by the simulation.
//!
//! **Where the record comes from.** On a room's netplay console, [`track`] (every tick, a pure function of the
//! console) notes the battle: when it starts a number counts up ([`BATTLE_NO`]) and the CO powers used are counted
//! per army ([`power_used`], AW2's `ActivateCoPower`); while it lasts, and until the game is back on the menus, each
//! army's player record is read ([`snapshot`]): AW2's own end-of-battle statistics at `+0x3A` (units built, counting
//! the units the map starts with) and `+0x3B` (units lost), which its results screen turns into Speed, Power and
//! Technique (`0x08026368`..`0x08026520`; Power is the other teams' losses). When the battle is over for good the
//! last snapshot is kept for the app ([`take_battles`]), which works out who won and whose it was.

use mgba::core::Core;
use std::sync::Mutex;

use crate::online::{bar, text_width, Rgba, BLUE, GRAY_INK, INK, LIGHT_GRAY, SHADE, W, WHITE, YELLOW};

// --- State (tangoAW2's 0x0203D100..0x0203D4FF) -------------------------------------------------------------

pub const BASE: u32 = 0x0203_D100;
pub const LEN: u32 = 0x400;
/// The committed gamertag (zero-terminated), at most [`TAG_CHARS`].
pub const GAMERTAG: u32 = BASE;
pub const TAG_CHARS: usize = 10;
/// 1 once the app has put the gamertag and the record's lines here.
pub const SYNCED: u32 = BASE + 0x0C;
/// 1 once the first-visit question has been asked on this console.
const ASKED: u32 = BASE + 0x0D;
/// The level the typing page goes back to.
const FROM: u32 = BASE + 0x0E;
/// The name being typed, and its length.
pub const TAG_BUF: u32 = BASE + 0x10;
pub const TAG_LEN: u32 = BASE + 0x1C;
/// The STATS page's first line shown, and how many lines there are.
const SCROLL: u32 = BASE + 0x20;
pub const LINE_COUNT: u32 = BASE + 0x21;
/// CO powers used in the battle, by army 1..5.
const POWERS: u32 = BASE + 0x30;
/// Counts the battles of a room's match.
const BATTLE_NO: u32 = BASE + 0x38;
/// The record's lines: [`LINE_SIZE`] bytes each, zero-terminated, "label", a tab, "value".
pub const LINES: u32 = BASE + 0x100;
pub const LINE_SIZE: u32 = 0x20;
pub const MAX_LINES: usize = 24;

// --- The game's records -----------------------------------------------------------------------------

const PLAYER_SIZE: u32 = 0x3C;
const P_FUNDS: u32 = 0x00;
const P_DEFEATED: u32 = 0x14;
const P_HUMAN: u32 = 0x1B;
const P_CO: u32 = 0x1D;
const P_TEAM: u32 = 0x2A;
const P_YIELD: u32 = 0x31;
/// Units built (counting a map's starting units) and units lost, `AW2`'s own counters.
const P_BUILT: u32 = 0x3A;
const P_LOST: u32 = 0x3B;
const DAY: u32 = 0x0300_4080;

/// One army at the end of a battle.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ArmySummary {
    /// 1..5.
    pub army: u8,
    pub team: u8,
    pub human: bool,
    /// Routed, defeated (HQ captured) or yielded.
    pub out: bool,
    pub built: u8,
    pub lost: u8,
    pub co: u8,
    pub funds: u32,
    pub powers: u8,
}

/// A battle as the console showed it last.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct BattleSummary {
    /// Counts the match's battles (wraps).
    pub no: u8,
    pub day: u16,
    pub armies: Vec<ArmySummary>,
}

static LIVE: Mutex<Option<BattleSummary>> = Mutex::new(None);
static DONE: Mutex<Vec<BattleSummary>> = Mutex::new(Vec::new());

/// The armies of the battle now (the human ones; a room has no others).
pub fn snapshot(core: &Core) -> BattleSummary {
    let players = crate::five::players(core);
    let armies = (1..=5u32)
        .filter_map(|a| {
            let p = players + PLAYER_SIZE * a;
            let human = core.raw_read_8(p + P_HUMAN, -1);
            (1..=2).contains(&human).then(|| ArmySummary {
                army: a as u8,
                team: core.raw_read_8(p + P_TEAM, -1),
                human: human == 1,
                out: core.raw_read_16(p + P_DEFEATED, -1) != 0 || core.raw_read_8(p + P_YIELD, -1) != 0,
                built: core.raw_read_8(p + P_BUILT, -1),
                lost: core.raw_read_8(p + P_LOST, -1),
                co: core.raw_read_8(p + P_CO, -1),
                funds: core.raw_read_32(p + P_FUNDS, -1),
                powers: core.raw_read_8(POWERS + a, -1),
            })
        })
        .collect();
    BattleSummary {
        no: core.raw_read_8(BATTLE_NO, -1),
        day: core.raw_read_16(DAY, -1),
        armies,
    }
}

/// A battle starts on a room's console: the next number, no powers used.
pub fn battle_started(core: &mut Core) {
    let n = core.raw_read_8(BATTLE_NO, -1).wrapping_add(1);
    core.raw_write_8(BATTLE_NO, -1, n);
    core.raw_write_range(POWERS, -1, &[0u8; 8]);
}

/// While a room's battle lasts (every tick): note how it stands.
pub fn track(core: &Core) {
    *LIVE.lock().unwrap() = Some(snapshot(core));
}

/// The battle is over for good (the game is back on the menus): keep its last note for the app (a battle replayed
/// after a rollback replaces its own note).
pub fn battle_ended() {
    let Some(b) = LIVE.lock().unwrap().take() else { return };
    let mut done = DONE.lock().unwrap();
    done.retain(|d| d.no != b.no);
    done.push(b);
}

/// The battles finished since the last call, oldest first.
pub fn take_battles() -> Vec<BattleSummary> {
    std::mem::take(&mut *DONE.lock().unwrap())
}

/// Forget all notes (a match is built).
pub fn forget() {
    *LIVE.lock().unwrap() = None;
    DONE.lock().unwrap().clear();
}

/// `ActivateCoPower` (crate::co_powers' trap): a CO Power or Super CO Power of `army` in a room's battle.
pub fn power_used(core: &mut Core, army: u32, mode: u8) {
    if !crate::online::in_room_match(core) || !(1..=5).contains(&army) || !(1..=2).contains(&mode) {
        return;
    }
    let at = POWERS + army;
    let n = core.raw_read_8(at, -1);
    core.raw_write_8(at, -1, n.saturating_add(1));
}

// --- The gamertag -------------------------------------------------------------------------------------

fn text_at(core: &Core, at: u32, max: usize) -> String {
    (0..max)
        .map(|k| core.raw_read_8(at + k as u32, -1))
        .take_while(|&c| c != 0)
        .map(|c| c as char)
        .collect()
}

/// The committed gamertag ("" when none is set).
pub fn gamertag(core: &Core) -> String {
    text_at(core, GAMERTAG, TAG_CHARS)
}

/// The gamertag as the mailbox gives it to the app (from the console's bytes).
pub fn read_gamertag(read: &mut dyn FnMut(u32, &mut [u8])) -> String {
    let mut b = [0u8; TAG_CHARS];
    read(GAMERTAG, &mut b);
    b.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect()
}

/// The name as it is kept: printable ASCII, trimmed, at most [`TAG_CHARS`].
pub fn clean(name: &str) -> String {
    let s: String = name.chars().filter(|c| c.is_ascii_graphic() || *c == ' ').collect();
    s.trim().chars().take(TAG_CHARS).collect::<String>().trim_end().to_string()
}

/// The app puts the gamertag and the record's lines in the console's memory (a console just started).
pub fn sync(write: &mut dyn FnMut(u32, &[u8]), gamertag: &str, lines: &[String]) {
    let mut b = [0u8; TAG_CHARS + 1];
    for (k, c) in clean(gamertag).bytes().enumerate() {
        b[k] = c;
    }
    write(GAMERTAG, &b);
    let lines: Vec<&String> = lines.iter().take(MAX_LINES).collect();
    let mut block = vec![0u8; LINE_SIZE as usize * MAX_LINES];
    for (k, l) in lines.iter().enumerate() {
        for (i, c) in l
            .chars()
            .filter(|c| (c.is_ascii() && !c.is_ascii_control()) || *c == '\t')
            .take(LINE_SIZE as usize - 1)
            .enumerate()
        {
            block[LINE_SIZE as usize * k + i] = c as u8;
        }
    }
    write(LINES, &block);
    write(LINE_COUNT, &[lines.len() as u8]);
    write(SYNCED, &[1]);
}

/// Whether the console wants the app's [`sync`].
pub fn needs_sync(read: &mut dyn FnMut(u32, &mut [u8])) -> bool {
    let mut b = [0u8];
    read(SYNCED, &mut b);
    b[0] == 0
}

/// Starting the typing page: from `level`, with the current name to edit.
pub fn open_entry(core: &mut Core, from: u8) {
    core.raw_write_8(FROM, -1, from);
    let tag = gamertag(core);
    core.raw_write_range(TAG_BUF, -1, &[0u8; 12]);
    for (k, c) in tag.bytes().enumerate() {
        core.raw_write_8(TAG_BUF + k as u32, -1, c);
    }
    core.raw_write_8(TAG_LEN, -1, tag.len() as u8);
}

/// The level the typing page goes back to.
pub fn entry_from(core: &Core) -> u8 {
    core.raw_read_8(FROM, -1)
}

/// OK on the typing page: the name typed is the gamertag.
pub fn commit(core: &mut Core) {
    let name = text_at(core, TAG_BUF, TAG_CHARS);
    let mut b = [0u8; TAG_CHARS + 1];
    for (k, c) in name.bytes().enumerate() {
        b[k] = c;
    }
    core.raw_write_range(GAMERTAG, -1, &b);
}

/// The first visit to the ONLINE screen asks for a gamertag when none is set: true once (this console).
pub fn should_ask(core: &mut Core) -> bool {
    if core.raw_read_8(SYNCED, -1) == 1 && core.raw_read_8(ASKED, -1) == 0 && gamertag(core).is_empty() {
        core.raw_write_8(ASKED, -1, 1);
        return true;
    }
    false
}

pub fn open_stats(core: &mut Core) {
    core.raw_write_8(SCROLL, -1, 0);
}

/// UP and DOWN on the STATS page.
pub fn scroll(core: &mut Core, down: bool) {
    let n = core.raw_read_8(LINE_COUNT, -1).min(MAX_LINES as u8) as i32;
    let max = (n - STATS_ROWS as i32).max(0);
    let s = core.raw_read_8(SCROLL, -1) as i32 + if down { 1 } else { -1 };
    core.raw_write_8(SCROLL, -1, s.clamp(0, max) as u8);
}

// --- Drawing (presentation only) ------------------------------------------------------------------------

/// The gamertag in the screen's top right corner (the ONLINE and LOBBY menus).
pub fn draw_tag(cv: &mut Rgba, core: &Core) {
    let tag = gamertag(core);
    let s = if tag.is_empty() { "No gamertag".to_string() } else { tag };
    let w = text_width(core, &s);
    let (x, y) = (W as i32 - w - 9, 4);
    cv.rect(x - 4, y - 2, w + 8, 15, crate::online::BAR);
    cv.text(core, x, y, &s, if gamertag(core).is_empty() { GRAY_INK } else { WHITE }, GRAY_INK);
}

/// The typing page.
pub fn draw_entry(cv: &mut Rgba, core: &Core, panel: (i32, i32, i32, i32)) {
    let (x, y, w, _) = panel;
    let head = "Your gamertag";
    cv.text(core, x + (w - text_width(core, head)) / 2, y + 5, head, GRAY_INK, SHADE);
    let name = text_at(core, TAG_BUF, TAG_CHARS);
    let (bx, by, bw, bh) = (x + 10, y + 20, w - 20, 20);
    cv.rect(bx, by, bw, bh, LIGHT_GRAY);
    cv.rect(bx, by + bh - 2, bw, 2, crate::online::RED);
    let tw = text_width(core, &name).max(0);
    let nx = bx + (bw - tw - 6) / 2;
    cv.text(core, nx, by + 4, &name, INK, SHADE);
    if name.len() < TAG_CHARS {
        cv.rect(nx + tw + 2, by + 14, 5, 2, INK);
    }
}

/// How many lines the STATS page shows at a time.
const STATS_ROWS: usize = 9;

/// The STATS page.
pub fn draw_stats(cv: &mut Rgba, core: &Core, panel: (i32, i32, i32, i32)) {
    let (x, y, w, h) = panel;
    let n = core.raw_read_8(LINE_COUNT, -1).min(MAX_LINES as u8) as usize;
    let top = (core.raw_read_8(SCROLL, -1) as usize).min(n.saturating_sub(STATS_ROWS));
    let head = "Your online record";
    cv.text(core, x + (w - text_width(core, head)) / 2, y + 5, head, GRAY_INK, SHADE);
    if n == 0 {
        let t = "No online battles yet.";
        cv.text(core, x + (w - text_width(core, t)) / 2, y + 40, t, GRAY_INK, SHADE);
    }
    for (row, k) in (top..n.min(top + STATS_ROWS)).enumerate() {
        let line = text_at(core, LINES + LINE_SIZE * k as u32, LINE_SIZE as usize - 1);
        let ry = y + 20 + 10 * row as i32;
        let (label, value) = line.split_once('\t').unwrap_or((&line, ""));
        let heading = value.is_empty() && !label.starts_with(' ');
        if heading {
            cv.rect(x + 4, ry + 9, w - 8, 1, LIGHT_GRAY);
            cv.text(core, x + 6, ry, label, BLUE, SHADE);
        } else {
            cv.text(core, x + 6, ry, label, INK, SHADE);
            cv.text(core, x + w - 6 - text_width(core, value), ry, value, INK, SHADE);
        }
    }
    // (more above or below)
    if top > 0 {
        cv.rect(x + w - 12, y + 6, 5, 1, YELLOW);
        cv.rect(x + w - 11, y + 5, 3, 1, YELLOW);
        cv.rect(x + w - 10, y + 4, 1, 1, YELLOW);
    }
    if top + STATS_ROWS < n {
        cv.rect(x + w - 12, y + h - 6, 5, 1, BLUE);
        cv.rect(x + w - 11, y + h - 5, 3, 1, BLUE);
        cv.rect(x + w - 10, y + h - 4, 1, 1, BLUE);
    }
    bar(cv, core, if n > STATS_ROWS { "UP/DOWN: Scroll  B: Back" } else { "B: Back" });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_fits() {
        assert!(LINES + LINE_SIZE * MAX_LINES as u32 <= BASE + LEN);
        assert!(TAG_BUF + 12 <= TAG_LEN + 1 + 0x10);
        assert!(GAMERTAG + TAG_CHARS as u32 + 1 <= SYNCED);
        assert!(POWERS + 8 <= BATTLE_NO);
        assert!(BATTLE_NO < LINES);
    }

    #[test]
    fn names_are_cleaned() {
        assert_eq!(clean("  Daniel the Great  "), "Daniel the");
        assert_eq!(clean("é!ab"), "!ab");
        assert_eq!(clean(""), "");
    }
}
