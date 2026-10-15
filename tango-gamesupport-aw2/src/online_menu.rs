//! ONLINE in place of LINK, played alone (offline): the Select Mode wheel's LINK reads ONLINE, its help line
//! "Play online with friends.", and the screen it opens (AW2's link-cable screen, `ProcScr` `0x0849BC50`, its
//! cursor at +0x36: 0 Single-Pak, 1 Multi-Pak, 2 Trade Maps) is the ONLINE screen: titled ONLINE, its items
//! UNRANKED, LOBBY and STATS with their own help lines. A on LOBBY goes a level down on the same screen (titled
//! LOBBY: CREATE, JOIN, RESUME; B goes back up, as BACK did); A on CREATE or JOIN opens the lobby's own pages
//! ([`crate::online`]). UNRANKED and STATS say they are coming soon. The game never sees A or START on this
//! screen, so its link-cable modes never start.
//!
//! How (the lettering is [`crate::online_art`]'s):
//!
//! - **Wheel**: LINK's two label pointers (`0x08616AC0 + 8 * 4`) point at ONLINE's labels, LZ77 streams in free
//!   ROM ([`WHEEL_BIG_AT`], [`WHEEL_SMALL_AT`]).
//! - **ONLINE screen**: the pointer to its label sheet (`0x08033AE4`) points at a sheet of the three words; the
//!   label tiles are also kept in OBJ VRAM by item (big 700, 764, 828; small 892, 924, 956), so the LOBBY level
//!   writes its words there and the game's own cursor, its labels' growing and shrinking, carry on as they are.
//! - **Title**: the screen's LINK is four 16x32 sprites (OBJ tiles 236.., palette 15) in the game's title font;
//!   its glyphs for the level's word go to tiles 236.. (268.. are unused on this screen) and at the sprite flush
//!   ([`flush`]) the four sprites are set to them and the rest added.
//! - **Help lines**: text ids 0x9CE (the wheel's), 0xCBE..0xCC0 (the screen's, by item) read tangoAW2's strings
//!   ([`TEXTS_AT`]).
//!
//! Everything is put back while a netplay console runs (its menus are the game's own; the in-game lobby is the
//! offline console's).

use mgba::core::Core;
use std::sync::OnceLock;

use crate::online_art::{self as art, LinkFont, TitleFont};

/// The ONLINE screen's menu proc.
const LINK_MENU: u32 = 0x0849_BC50;
const CURSOR: u32 = 0x36;
const PROCS: u32 = 0x0200_D610;
const PROCS_END: u32 = 0x0200_E418;
const PROC_SIZE: u32 = 0x6C;

/// AW2's text table (a pointer per text id).
const TEXT_TABLE: u32 = 0x0861_0A38;
/// (text id, the game's string): the wheel's Link line, then the screen's three items'.
const TEXT_IDS: [(u32, u32); 4] = [
    (0x9CE, 0x0860_783C),
    (0xCBE, 0x0861_06A0),
    (0xCBF, 0x0861_06C8),
    (0xCC0, 0x0861_06E4),
];
const HELP: [&str; 4] = [
    "Play online with friends.",
    "Coming soon: play someone at random.",
    "Create a room or join a friend's room.",
    "Coming soon: your online record.",
];

/// The game's label pointers for LINK, and its sheet.
const WHEEL_LINK_BIG: u32 = 0x0823_CB14;
const WHEEL_LINK_SMALL: u32 = 0x0823_D768;

/// tangoAW2's data in free ROM (0x08E50000..0x08E5FFFF).
const TEXTS_AT: u32 = 0x08E5_0000;
const TEXT_SIZE: u32 = 0x40;
pub const WHEEL_BIG_AT: u32 = 0x08E5_0400;
pub const WHEEL_SMALL_AT: u32 = 0x08E5_0E00;
const SHEET_AT: u32 = 0x08E5_1400;
const SENTINEL: u32 = 0x08E5_FFFC;
const MAGIC: u32 = 0x4E4C_4E4F; // "ONLN"

/// OBJ VRAM's label slots by item (big, small) and the title's tiles.
const OBJ_VRAM: u32 = 0x0601_0000;
const BIG_SLOTS: [u32; 3] = [700, 764, 828];
const SMALL_SLOTS: [u32; 3] = [892, 924, 956];
const TITLE_TILE: u32 = 236;
const TITLE_PALETTE: u16 = 15;

pub const WORDS: [[&str; 3]; 2] = [["UNRANKED", "LOBBY", "STATS"], ["CREATE", "JOIN", "RESUME"]];
pub const TITLES: [&str; 2] = ["ONLINE", "LOBBY"];

struct Built {
    wheel_big: Vec<u8>,
    wheel_small: Vec<u8>,
    /// Each level's sheet as tiles (three big labels, three small).
    sheets: [Vec<u8>; 2],
    title: TitleFont,
}

static BUILT: OnceLock<Option<Built>> = OnceLock::new();

fn built(core: &Core) -> Option<&'static Built> {
    BUILT
        .get_or_init(|| {
            let font = LinkFont::load(core)?;
            Some(Built {
                wheel_big: art::wheel_big(core)?,
                wheel_small: art::wheel_small(core)?,
                sheets: [font.sheet(WORDS[0]), font.sheet(WORDS[1])],
                title: TitleFont::load(core)?,
            })
        })
        .as_ref()
}

fn install(core: &mut Core) -> bool {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return true;
    }
    let Some(b) = built(core) else { return false };
    for (k, s) in HELP.iter().enumerate() {
        let mut bytes = s.as_bytes().to_vec();
        bytes.truncate(TEXT_SIZE as usize - 1);
        bytes.push(0);
        core.raw_write_range(TEXTS_AT + TEXT_SIZE * k as u32, -1, &bytes);
    }
    let big = art::lz_literal(&b.wheel_big);
    let small = art::lz_literal(&b.wheel_small);
    let sheet = art::lz_literal(&b.sheets[0]);
    debug_assert!(WHEEL_BIG_AT + big.len() as u32 <= WHEEL_SMALL_AT);
    debug_assert!(WHEEL_SMALL_AT + small.len() as u32 <= SHEET_AT);
    core.raw_write_range(WHEEL_BIG_AT, -1, &big);
    core.raw_write_range(WHEEL_SMALL_AT, -1, &small);
    core.raw_write_range(SHEET_AT, -1, &sheet);
    core.raw_write_32(SENTINEL, -1, MAGIC);
    true
}

/// Whether the ONLINE patches are in (read by the sprite flush, which has no mode).
pub fn active(core: &Core) -> bool {
    core.raw_read_32(art::SHEET_POOL, -1) == SHEET_AT
}

/// The ONLINE screen's menu proc, while it is up.
pub fn menu_proc(core: &Core) -> Option<u32> {
    (PROCS..PROCS_END)
        .step_by(PROC_SIZE as usize)
        .find(|&p| core.raw_read_32(p, -1) == LINK_MENU)
}

/// The item under the ONLINE screen's cursor (0..2).
pub fn cursor(core: &Core) -> Option<u8> {
    menu_proc(core).map(|p| (core.raw_read_16(p + CURSOR, -1) % 3) as u8)
}

fn w32(core: &mut Core, at: u32, v: u32) {
    if core.raw_read_32(at, -1) != v {
        core.raw_write_32(at, -1, v);
    }
}

/// Every frame: the patches in (offline) or out (a netplay console, or the art could not be made).
pub fn patch(core: &mut Core, offline: bool) {
    let on = offline && install(core);
    if !on && core.raw_read_32(SENTINEL, -1) != MAGIC {
        return;
    }
    let label = art::WHEEL_LABELS + 8 * art::LINK_ITEM;
    w32(core, label, if on { WHEEL_BIG_AT } else { WHEEL_LINK_BIG });
    w32(core, label + 4, if on { WHEEL_SMALL_AT } else { WHEEL_LINK_SMALL });
    w32(core, art::SHEET_POOL, if on { SHEET_AT } else { art::SHEET });
    for (k, &(id, game)) in TEXT_IDS.iter().enumerate() {
        w32(
            core,
            TEXT_TABLE + 4 * id,
            if on { TEXTS_AT + TEXT_SIZE * k as u32 } else { game },
        );
    }
}

fn write_if_changed(core: &mut Core, at: u32, b: &[u8]) {
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != b {
        core.raw_write_range(at, -1, b);
    }
}

/// While the ONLINE screen is up: the level's words in the label slots and its title's glyphs.
pub fn draw(core: &mut Core, level: usize) {
    if !active(core) || menu_proc(core).is_none() {
        return;
    }
    let Some(b) = built(core) else { return };
    let level = level.min(1);
    let sheet = &b.sheets[level];
    let tile = 32 * art::BIG_TILES;
    for i in 0..3 {
        write_if_changed(core, OBJ_VRAM + 32 * BIG_SLOTS[i], &sheet[i * tile..(i + 1) * tile]);
        let s = 3 * tile + i * 32 * art::SMALL_TILES;
        write_if_changed(
            core,
            OBJ_VRAM + 32 * SMALL_SLOTS[i],
            &sheet[s..s + 32 * art::SMALL_TILES],
        );
    }
    let mut tiles = Vec::new();
    for c in TITLES[level].chars() {
        if let Some(t) = b.title.tiles(c) {
            tiles.extend_from_slice(t);
        }
    }
    write_if_changed(core, OBJ_VRAM + 32 * TITLE_TILE, &tiles);
}

/// At the sprite flush: the title's sprites spell the level's word (the game draws four, LINK's).
pub fn flush(core: &mut Core, start: u32, at: u32, end: u32) -> u32 {
    if !active(core) || menu_proc(core).is_none() {
        return at;
    }
    let Some(b) = built(core) else { return at };
    // The lobby's pages are drawn over the screen: the menu's cursor arrows (tile 0, palette 6) are off.
    if crate::online::level(core) >= 2 {
        let mut s = start;
        while s < at {
            if core.raw_read_16(s + 4, -1) == 0x6000 {
                core.raw_write_16(s, -1, (core.raw_read_16(s, -1) & !0x0300) | 0x0200);
            }
            s += 8;
        }
    }
    let level = (crate::online::level(core) as usize).min(1);
    let word = TITLES[level];
    // The game's title sprites, left to right.
    let mut ours: Vec<u32> = Vec::new();
    let mut s = start;
    while s < at {
        let a2 = core.raw_read_16(s + 4, -1);
        let tile = (a2 & 0x3FF) as u32;
        if a2 >> 12 == TITLE_PALETTE && (TITLE_TILE..TITLE_TILE + 32).contains(&tile) {
            ours.push(s);
        }
        s += 8;
    }
    let Some(&first) = ours.first() else { return at };
    let (a0, a1, a2) = (
        core.raw_read_16(first, -1),
        core.raw_read_16(first + 2, -1),
        core.raw_read_16(first + 4, -1),
    );
    let x0 = ours
        .iter()
        .map(|&s| core.raw_read_16(s + 2, -1) & 0x1FF)
        .min()
        .unwrap_or(4) as i32;
    let layout = b.title.layout(word, x0);
    let mut at = at;
    for (k, &(_, x)) in layout.iter().enumerate() {
        let slot = match ours.get(k) {
            Some(&s) => s,
            None if at + 8 <= end => {
                at += 8;
                at - 8
            }
            None => break,
        };
        core.raw_write_16(slot, -1, a0);
        core.raw_write_16(slot + 2, -1, (a1 & !0x1FF) | (x as u16 & 0x1FF));
        core.raw_write_16(slot + 4, -1, (a2 & !0x3FF) | (TITLE_TILE as u16 + 8 * k as u16));
        if ours.get(k).is_none() {
            core.raw_write_16(slot + 6, -1, 0);
        }
    }
    // (a shorter word than the game's: its last sprites off)
    for &s in ours.iter().skip(layout.len()) {
        core.raw_write_16(s, -1, (core.raw_read_16(s, -1) & !0x0300) | 0x0200);
    }
    at
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn data_fits() {
        assert!(TEXTS_AT + TEXT_SIZE * HELP.len() as u32 <= WHEEL_BIG_AT);
        // ONLINE's labels as literal LZ77: 2 KiB and 1 KiB of tiles, an eighth more.
        assert!(WHEEL_BIG_AT + 2048 * 9 / 8 + 8 <= WHEEL_SMALL_AT);
        assert!(WHEEL_SMALL_AT + 1024 * 9 / 8 + 8 <= SHEET_AT);
        assert!(SHEET_AT + (3 * 64 + 3 * 32) * 32 * 9 / 8 + 8 <= SENTINEL);
        assert!(HELP.iter().all(|h| h.len() < TEXT_SIZE as usize));
        // The title's six glyphs fit before the girl's tiles (380..).
        assert!(TITLE_TILE + 8 * 6 <= 380);
    }
}
