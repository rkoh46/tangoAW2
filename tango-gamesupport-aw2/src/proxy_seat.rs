//! A seat whose player is not there any more, in a room whose host migrated (see `tango_session::pvp::migrate`).
//!
//! Two things in a room's console belong to the host: the screens outside a battle (the results pages, the way back to
//! SELECT MODE) take the host's pad (seat 0), and a living army whose player left would hold its turn for ever. Both are
//! settled by the room's one stream of words, which every peer plays alike, so they are settled in the simulation:
//!
//! - **Commands.** A word with all four directions down at once (`UP | DOWN | LEFT | RIGHT`, which no pad can make: the
//!   session strips it from every real word) is a command from the room's host, not keys: "this seat is the room's host from
//!   now" ([`HOST`]) or "play this seat for me: yield it" ([`YIELD`]). The state is console RAM (so rollback, snapshots and
//!   replays carry it).
//! - **The yielding seat.** Every tick of a seat under the command whose army holds the pad, [`tick`] decides the seat's
//!   keys from what the console shows, a tap at a time with the screen allowed to settle between taps, exactly what a
//!   player does to yield (a cell with nothing on it, A, Options, Yield, Yes). A tap is four ticks down and six up.
//!   Once the army is beaten the game ends its turn by itself and the next army's player has the pad.

use mgba::core::Core;

pub use tango_match::keys::command::{strip as strip_command, BITS as COMMAND_BITS, HOST, YIELD};

/// tangoAW2's state for it in EWRAM (crate::ram_map): the seats under the yield command (a bit each), the room's host seat,
/// the keys held by the tap in progress and its age, a count of ticks at the hand-off screen, a count of ticks without
/// progress, the ticks since Yield was chosen (the game asks "Do you really yield?" and types the question out first),
/// and what the screen showed at the last progress. (Words, not bytes, on word addresses: the console reads whole words.)
pub const BASE: u32 = 0x0203_C620;
pub const LEN: u32 = 16;
const SEATS: u32 = BASE;
const HOST_SEAT: u32 = BASE + 1;
const HELD: u32 = BASE + 2;
const AGE: u32 = BASE + 4;
const WAIT: u32 = BASE + 5;
const STUCK: u32 = BASE + 6;
const CONFIRM: u32 = BASE + 8;
const SIG: u32 = BASE + 12;

const KEY_A: u32 = 1 << 0;
const KEY_B: u32 = 1 << 1;
const KEY_RIGHT: u32 = 1 << 4;
const KEY_LEFT: u32 = 1 << 5;
const KEY_UP: u32 = 1 << 6;
const KEY_DOWN: u32 = 1 << 7;

const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const TERRAIN: u32 = MAP + 0x1432;
const PLANES: [u32; 2] = [MAP + 0x12, MAP + 0x51A];
const CURSOR: u32 = 0x0300_33E4;
const MENU_STATE: u32 = 0x0300_14E2;
const MENU_CURSOR: u32 = 0x0300_14F0;
const MENU_ITEMS: u32 = 0x0300_14A1;
/// The map menu's ids: Options; and the Options menu's: Yield, and its last item (Exit Map), which the map menu does not
/// have.
const ITEM_OPTIONS: u8 = 4;
const ITEM_YIELD: u8 = 1;
const ITEM_EXIT_MAP: u8 = 8;
/// Terrain a cursor may stand on to open the map menu (plain, forest, road): nothing to select, nothing to build.
const OPEN_TERRAIN: [u8; 3] = [1, 4, 5];

/// The room's host seat as the console has it (0 until a command says another).
pub fn host_seat(core: &Core, players: usize) -> usize {
    let s = core.raw_read_8(HOST_SEAT, -1) as usize;
    if s < players {
        s
    } else {
        0
    }
}

/// Whether any seat is under the yield command.
pub fn any(core: &Core) -> bool {
    core.raw_read_8(SEATS, -1) != 0
}

/// Before every tick of a room's console: read the commands in `keys`, and give the seats under the yield command the keys
/// of their yield.
pub fn tick(core: &mut Core, keys: &mut [u32]) {
    let n = keys.len();
    if n < 3 {
        return;
    }
    let mut seats = core.raw_read_8(SEATS, -1);
    for (s, k) in keys.iter_mut().enumerate().take(8) {
        if *k & COMMAND_BITS != COMMAND_BITS {
            continue;
        }
        match *k {
            HOST => core.raw_write_8(HOST_SEAT, -1, s as u8),
            YIELD => seats |= 1 << s,
            _ => {}
        }
        *k = 0;
    }
    if seats != core.raw_read_8(SEATS, -1) {
        core.raw_write_8(SEATS, -1, seats);
    }
    if seats == 0 {
        return;
    }
    // (the seat whose army has the pad: the same army the merge gives it to)
    let active = crate::online::pad_army(core, n).map(|a| (a, crate::pvp::seat_of_n(a, n)));
    for s in 0..n.min(8) {
        if seats & (1 << s) == 0 {
            continue;
        }
        keys[s] = match active {
            Some((army, seat)) if seat == s => yield_keys(core, army),
            _ => {
                rest(core);
                0
            }
        };
    }
}

/// Nothing to do for now: the counters start over.
fn rest(core: &mut Core) {
    for a in [HELD, STUCK, CONFIRM] {
        if core.raw_read_16(a, -1) != 0 {
            core.raw_write_16(a, -1, 0);
        }
    }
    for a in [AGE, WAIT] {
        if core.raw_read_8(a, -1) != 0 {
            core.raw_write_8(a, -1, 0);
        }
    }
}

/// The keys this tick for the seat of `army`, which has the pad.
fn yield_keys(core: &mut Core, army: u8) -> u32 {
    if !crate::result_view::alive(core, army) {
        rest(core);
        return 0;
    }
    // A tap in progress: four ticks down, six up.
    let age = core.raw_read_8(AGE, -1);
    if age > 0 {
        let held = core.raw_read_16(HELD, -1) as u32;
        let key = if age < 4 { held } else { 0 };
        if age >= 9 {
            core.raw_write_8(AGE, -1, 0);
            core.raw_write_16(HELD, -1, 0);
        } else {
            core.raw_write_8(AGE, -1, age + 1);
        }
        return key;
    }
    let key = decide(core);
    if key != 0 && std::env::var_os("AW2_PROXY_LOG").is_some() {
        eprintln!(
            "proxy: army {army} taps {key:#x} (cursor {},{} menu state {} row {} items {:?} loop {:08x})",
            core.raw_read_16(CURSOR, -1),
            core.raw_read_16(CURSOR + 2, -1),
            core.raw_read_8(MENU_STATE, -1),
            core.raw_read_8(MENU_CURSOR, -1),
            menu_items(core),
            core.raw_read_32(0x0300_0000, -1)
        );
    }
    if key != 0 {
        core.raw_write_16(HELD, -1, key as u16);
        core.raw_write_8(AGE, -1, 1);
        return key;
    }
    0
}

/// The menu's rows, once its list is up (state 4 and the list led by 0xFF): the ids, in order.
fn menu_items(core: &Core) -> Option<Vec<u8>> {
    if core.raw_read_8(MENU_STATE, -1) != 4 || core.raw_read_8(MENU_ITEMS - 1, -1) != 0xFF {
        return None;
    }
    let items: Vec<u8> = (0..8).map(|r| core.raw_read_8(MENU_ITEMS + r, -1)).take_while(|&i| i != 0xFF).collect();
    (!items.is_empty()).then_some(items)
}

fn cell_empty(core: &Core, x: i32, y: i32, w: i32, h: i32) -> bool {
    if x < 0 || y < 0 || x >= w || y >= h {
        return false;
    }
    let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
    if !OPEN_TERRAIN.contains(&(core.raw_read_8(TERRAIN + row + x as u32, -1) & 0x1F)) {
        return false;
    }
    PLANES.iter().all(|&p| core.raw_read_8(p + row + x as u32, -1) == 0)
}

/// The nearest cell a menu can be opened on (nothing on it), if the map has one.
fn nearest_open(core: &Core, cx: i32, cy: i32) -> Option<(i32, i32)> {
    let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
    if w <= 0 || h <= 0 || w > 64 || h > 64 {
        return None;
    }
    // (rings of growing distance around the cursor)
    for d in 0..(w + h) {
        for dy in -d..=d {
            let dx = d - dy.abs();
            for x in [cx - dx, cx + dx] {
                if cell_empty(core, x, cy + dy, w, h) {
                    return Some((x, cy + dy));
                }
            }
        }
    }
    None
}

/// What to tap now, or 0 to let the screen settle.
fn decide(core: &mut Core) -> u32 {
    // Progress: whatever the screen shows changed since the last look (a stuck yield backs out after ten seconds).
    let (cx, cy) = (core.raw_read_16(CURSOR, -1) as u32, core.raw_read_16(CURSOR + 2, -1) as u32);
    let sig = core.raw_read_8(MENU_STATE, -1) as u32
        | (core.raw_read_8(MENU_CURSOR, -1) as u32) << 8
        | cx << 12
        | cy << 20
        | (core.raw_read_32(0x0300_0000, -1) & 0xFFF) << 4;
    let last = core.raw_read_32(SIG, -1);
    let stuck = core.raw_read_16(STUCK, -1);
    if sig != last {
        core.raw_write_32(SIG, -1, sig);
        core.raw_write_16(STUCK, -1, 0);
    } else {
        core.raw_write_16(STUCK, -1, stuck.saturating_add(1));
    }
    if stuck > 600 {
        // (nothing moved for ten seconds: back out of whatever this is, and start over)
        core.raw_write_16(STUCK, -1, 0);
        return KEY_B;
    }

    // The yield's question is up (typed out first, which takes a few seconds): "Yes" is on the left, and the cursor starts on "No".
    let confirm = core.raw_read_16(CONFIRM, -1);
    if confirm != 0 {
        let t = confirm + 1;
        core.raw_write_16(CONFIRM, -1, if t >= 480 { 0 } else { t });
        return match t {
            260 => KEY_LEFT,
            300 => KEY_A,
            _ => 0,
        };
    }

    if let Some(items) = menu_items(core) {
        let row = core.raw_read_8(MENU_CURSOR, -1) as usize;
        // (the Options menu has Exit Map, the map menu has not)
        let want = if items.contains(&ITEM_EXIT_MAP) { ITEM_YIELD } else { ITEM_OPTIONS };
        return match items.iter().position(|&i| i == want) {
            Some(r) if r == row => {
                if want == ITEM_YIELD {
                    core.raw_write_16(CONFIRM, -1, 1);
                }
                KEY_A
            }
            Some(r) if r > row => KEY_DOWN,
            Some(_) => KEY_UP,
            None => KEY_B,
        };
    }

    // The map: put the cursor on a cell with nothing on it and open the menu there.
    if crate::fog_view::phase(core) == crate::fog_view::Phase::Map {
        let (cx, cy) = (cx as i32, cy as i32);
        let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
        if cell_empty(core, cx, cy, w, h) {
            return KEY_A;
        }
        return match nearest_open(core, cx, cy) {
            Some((x, _)) if x > cx => KEY_RIGHT,
            Some((x, _)) if x < cx => KEY_LEFT,
            Some((_, y)) if y > cy => KEY_DOWN,
            Some(_) => KEY_UP,
            None => KEY_B,
        };
    }

    // The turn coming up: the hand-off screen ("Next turn", with fog of war) waits for its player's A.
    if crate::fog_view::phase(core) == crate::fog_view::Phase::HandOff {
        let t = core.raw_read_8(WAIT, -1).wrapping_add(1);
        core.raw_write_8(WAIT, -1, t);
        if t % 30 == 0 {
            return KEY_A;
        }
    } else {
        core.raw_write_8(WAIT, -1, 0);
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_command_is_never_a_pad() {
        assert_eq!(HOST & COMMAND_BITS, COMMAND_BITS);
        assert_eq!(YIELD & COMMAND_BITS, COMMAND_BITS);
        assert_ne!(HOST, YIELD);
        // a real word that reads as one has a direction let go
        for w in [HOST, YIELD, 0x3FF, 0xF0, 0x2F0] {
            assert_ne!(strip_command(w) & COMMAND_BITS, COMMAND_BITS, "{w:#x}");
        }
        // anything else is as it was
        for w in [0u32, 1, 0x3F, 0x80 | 0x10, 0x60 | 0x30, 0x3CF] {
            assert_eq!(strip_command(w), w);
        }
        // the word of a command is a word the console takes (10 bits)
        assert!(HOST < 0x400 && YIELD < 0x400);
    }
}
