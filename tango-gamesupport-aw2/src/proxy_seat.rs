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
//! - **The roster.** A seat under the yield command is a player who has left the room, whether it was playing, out of the
//!   match, or on the results screens: [`YIELD`] is the one word for it. The room goes on without that seat from the next
//!   match: when SELECT MAP is back after a battle ([`tick`] sees [`crate::unranked::back_from_battle`]) the seats still
//!   there are written down, the room's host first and the others by seat ([`seat_order`]), and the console is played by
//!   them alone from then on: the session's words for the seats that left are taken out of the keys the game's code sees
//!   (`tango_backend_mgba::SharedGame::seat_order`), so the READY of the armies page, the map proposals, the roulette and the
//!   rules are those of the players that are left, and the armies of the next map are theirs. A room that falls to one
//!   player is over ([`alone`]).

use mgba::core::Core;

pub use tango_match::keys::command::{strip as strip_command, BITS as COMMAND_BITS, HOST, YIELD};

/// tangoAW2's state for it in EWRAM (crate::ram_map): the seats under the yield command (a bit each), the room's host seat,
/// the keys held by the tap in progress and its age, a count of ticks at the hand-off screen, a count of ticks without
/// progress, the ticks since Yield was chosen (the game asks "Do you really yield?" and types the question out first),
/// and what the screen showed at the last progress. (Words, not bytes, on word addresses: the console reads whole words.)
pub const BASE: u32 = 0x0203_C620;
pub const LEN: u32 = 0x20;
const SEATS: u32 = BASE;
const HOST_SEAT: u32 = BASE + 1;
const HELD: u32 = BASE + 2;
const AGE: u32 = BASE + 4;
const WAIT: u32 = BASE + 5;
const STUCK: u32 = BASE + 6;
const CONFIRM: u32 = BASE + 8;
const SIG: u32 = BASE + 12;
/// The roster: how many seats play (0: all of the room's), their physical seats in the order the console plays them
/// (up to eight), the departed seats (a bit each) the roster was made with, and how many seats the room has.
const ROSTER_M: u32 = BASE + 0x10;
const ORDER: u32 = BASE + 0x11;
const APPLIED: u32 = BASE + 0x19;
const N_PHYS: u32 = BASE + 0x1A;
/// The note that a player left the room: frames left (u16, even address) and the seat.
const LEFT_T: u32 = BASE + 0x1C;
const LEFT_SEAT: u32 = BASE + 0x1E;
/// Ticks spent backing out.
const BACK_T: u32 = BASE + 0x1F;
/// How long the note is shown (console frames).
const LEFT_FRAMES: u16 = 360;

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
/// The map menu's End item (End turn).
const ITEM_END: u8 = 6;
const ITEM_EXIT_MAP: u8 = 8;
/// Terrain a cursor may stand on to open the map menu (plain, forest, road): nothing to select, nothing to build.
const OPEN_TERRAIN: [u8; 3] = [1, 4, 5];

/// The room's host seat as the console has it (0 until a command says another): a physical seat.
pub fn host_seat(core: &Core, players: usize) -> usize {
    let s = core.raw_read_8(HOST_SEAT, -1) as usize;
    if s < players {
        s
    } else {
        0
    }
}

/// The seats that left the room (a bit each, physical seats): every seat that was sent the yield command.
pub fn departed(core: &Core) -> u8 {
    core.raw_read_8(SEATS, -1)
}

/// The seats the console is played by, in its order (the physical seat of each), once players have left and a match has
/// begun without them; `None` while it is played by the whole room.
pub fn seat_order(core: &Core) -> Option<Vec<usize>> {
    let m = core.raw_read_8(ROSTER_M, -1) as usize;
    (2..=8)
        .contains(&m)
        .then(|| (0..m).map(|k| core.raw_read_8(ORDER + k as u32, -1) as usize).collect())
}

/// Only one player is left in the room: the match is over for it.
pub fn alone(core: &Core) -> bool {
    core.raw_read_8(ROSTER_M, -1) == 1
}

/// The index in the console's keys of the room's host (`players` keys).
pub fn host_index(core: &Core, players: usize) -> usize {
    let host = core.raw_read_8(HOST_SEAT, -1) as usize;
    match seat_order(core) {
        Some(order) => order.iter().position(|&p| p == host).unwrap_or(0),
        None => host_seat(core, players),
    }
}

/// The seats still in the room as the console plays them from the next match: the host first, then the others by seat.
fn make_roster(core: &mut Core, n: usize) {
    let gone = core.raw_read_8(SEATS, -1);
    let host = core.raw_read_8(HOST_SEAT, -1) as usize;
    let order = roster_order(n, host, gone);
    for (k, &s) in order.iter().enumerate() {
        core.raw_write_8(ORDER + k as u32, -1, s as u8);
    }
    core.raw_write_8(ROSTER_M, -1, order.len() as u8);
    let before = core.raw_read_8(APPLIED, -1);
    core.raw_write_8(APPLIED, -1, gone);
    // (who left since: the note says so, and the proposals begin again)
    if let Some(s) = (0..8usize).find(|&s| gone & !before & (1 << s) != 0) {
        core.raw_write_8(LEFT_SEAT, -1, s as u8);
        core.raw_write_16(LEFT_T, -1, LEFT_FRAMES);
    }
    if order.len() == 1 {
        log::info!("room: everyone else has left (seats gone {gone:#04x}); the match is over for the one left");
    }
    crate::unranked::restart(core);
}

/// The seats of a room of `n` that are still there (`gone` has a bit for each that left), in the order the console plays them:
/// the room's host first (it has the screens outside a battle, and seat 0's place on the pages), then the others by seat.
/// Every peer works it out from the console's RAM alone.
pub fn roster_order(n: usize, host: usize, gone: u8) -> Vec<usize> {
    let here = |s: usize| s < 8 && gone & (1 << s) == 0;
    let mut order: Vec<usize> = Vec::new();
    if host < n && here(host) {
        order.push(host);
    }
    order.extend((0..n.min(8)).filter(|&s| here(s) && s != host));
    order
}

/// The roster is up to date with the seats that left. It is made whenever SELECT MAP is up with the room's players not in a battle
/// (after a battle, or because a player left while the maps were being proposed, or after the game was backed out of the armies
/// and the rules, see [`backing_out`]): the proposals begin again for the players that are left.
fn roster_due(core: &Core) -> bool {
    core.raw_read_8(SEATS, -1) != core.raw_read_8(APPLIED, -1) && crate::unranked::setup_select(core)
}

/// A player left after the maps were drawn and before the battle began (the game is on the armies or the rules): the game is
/// backed out of them with B, by the console, to SELECT MAP, where the roster is made and the maps proposed again.
pub fn backing_out(core: &Core) -> bool {
    core.raw_read_8(SEATS, -1) != core.raw_read_8(APPLIED, -1) && crate::unranked::setup_past_select(core)
}

/// The keys of the back-out: B for 6 ticks of every 12.
pub fn back_key(core: &Core) -> u32 {
    if core.raw_read_8(BACK_T, -1) / 6 % 2 == 0 {
        crate::online::KEY_B
    } else {
        0
    }
}

/// Frames left of the note that a player left, and the seat that left (a physical seat).
pub fn left_note(core: &Core) -> Option<usize> {
    (core.raw_read_16(LEFT_T, -1) > 0).then(|| core.raw_read_8(LEFT_SEAT, -1) as usize)
}

/// Whether any seat is under the yield command.
pub fn any(core: &Core) -> bool {
    core.raw_read_8(SEATS, -1) != 0
}

/// Before every tick of a room's console: read the commands in `keys`, and give the seats under the yield command the keys
/// of their yield.
pub fn tick(core: &mut Core, keys: &mut [u32]) {
    let n = keys.len();
    if n < 2 {
        return;
    }
    if core.raw_read_8(N_PHYS, -1) != n as u8 {
        core.raw_write_8(N_PHYS, -1, n as u8);
    }
    let mut seats = core.raw_read_8(SEATS, -1);
    for (s, k) in keys.iter_mut().enumerate().take(8) {
        if tango_match::keys::command::is_pick(*k) {
            // (half of a map pick, a seat's own word: see crate::unranked)
            crate::unranked::pick_word(core, s, tango_match::keys::command::pick_half(*k));
            *k = 0;
            continue;
        }
        if *k & COMMAND_BITS != COMMAND_BITS {
            crate::unranked::pick_reset(core, s);
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
    if roster_due(core) {
        make_roster(core, n);
    }
    crate::online::note_order(seat_order(core));
    let back = if backing_out(core) {
        core.raw_read_8(BACK_T, -1).wrapping_add(1)
    } else {
        0
    };
    if core.raw_read_8(BACK_T, -1) != back {
        core.raw_write_8(BACK_T, -1, back);
    }
    let note = core.raw_read_16(LEFT_T, -1);
    if note > 0 {
        core.raw_write_16(LEFT_T, -1, note - 1);
    }
    if seats == 0 {
        return;
    }
    // (the seat whose army has the pad: the same army the merge gives it to, among the seats the console is played by)
    let order = seat_order(core);
    let m = order.as_ref().map_or(n, |o| o.len());
    let active = crate::online::pad_army(core, m).map(|a| {
        let seat = crate::pvp::seat_of_n(a, m);
        (a, order.as_ref().and_then(|o| o.get(seat).copied()).unwrap_or(seat))
    });
    // (the last army still in the match has the pad and the match is decided, but the game only looks at it when something
    // happens: the console ends the turn for it, a tap at a time, which is when VICTORY! comes, see [`force_yield`])
    let mut ending = false;
    if let Some((army, seat)) = active {
        if seats & (1 << seat) == 0 && crate::result_view::decided(core) && crate::result_view::alive(core, army) {
            keys[seat] = yield_keys(core, army, true);
            ending = true;
        }
    }
    for s in 0..n.min(8) {
        if seats & (1 << s) == 0 {
            continue;
        }
        keys[s] = match active {
            Some((army, seat)) if seat == s => yield_keys(core, army, false),
            _ => {
                // (the taps in progress are the ending turn's, if the match is decided)
                if !ending {
                    rest(core);
                }
                // (the player is gone and the pad is another army's: this seat's armies are yielded at once, out of turn)
                force_yield(core, s, n, &order, active.map(|a| a.0));
                0
            }
        };
    }
}

/// A seat under the yield command whose armies do not hold the pad (another player is mid-turn, or the screens that
/// follow are up): the armies are yielded at once, the way the map menu's Yield sets it (the player block's yielded flag),
/// so that the game's rules check ends them and the match does not wait for the departed player's turn to come, which can
/// be as long as the other player takes over its own. Only in a battle (`mover` is the army that has the pad).
fn force_yield(core: &mut Core, seat: usize, n: usize, order: &Option<Vec<usize>>, mover: Option<u8>) {
    if mover.is_none() {
        return;
    }
    let m = order.as_ref().map_or(n, |o| o.len());
    for army in 1..=crate::five::armies(core).clamp(2, 5) {
        if Some(army) == mover || !crate::result_view::alive(core, army) {
            continue;
        }
        let slot = crate::pvp::seat_of_n(army, m);
        let physical = order.as_ref().and_then(|o| o.get(slot).copied()).unwrap_or(slot);
        if physical != seat {
            continue;
        }
        // (what the game's own check does with a yielded army, `0x08028AEC` -> `0x08028874(army, 8)`: the day it was beaten on
        // and why)
        let block = crate::five::players(core) + PLAYER_STRIDE * army as u32;
        core.raw_write_8(block + P_YIELDED, -1, 1);
        core.raw_write_8(block + P_REASON, -1, REASON_YIELDED);
        let day = core.raw_read_16(DAY, -1).max(1);
        core.raw_write_16(block + P_DEFEATED, -1, day);
    }
}

const PLAYER_STRIDE: u32 = 0x3C;
/// A player block's yielded flag (the map menu's Yield sets it, the game's rules check then defeats the army).
const P_YIELDED: u32 = 0x31;
const P_DEFEATED: u32 = 0x14;
const P_REASON: u32 = 0x13;
const REASON_YIELDED: u8 = 8;
const DAY: u32 = 0x0300_4080;

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
fn yield_keys(core: &mut Core, army: u8, end_turn: bool) -> u32 {
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
    let key = decide(core, end_turn);
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
    let items: Vec<u8> = (0..8)
        .map(|r| core.raw_read_8(MENU_ITEMS + r, -1))
        .take_while(|&i| i != 0xFF)
        .collect();
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
fn decide(core: &mut Core, end_turn: bool) -> u32 {
    // Progress: whatever the screen shows changed since the last look (a stuck yield backs out after ten seconds).
    let (cx, cy) = (
        core.raw_read_16(CURSOR, -1) as u32,
        core.raw_read_16(CURSOR + 2, -1) as u32,
    );
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
        let want = if end_turn {
            ITEM_END
        } else if items.contains(&ITEM_EXIT_MAP) {
            ITEM_YIELD
        } else {
            ITEM_OPTIONS
        };
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
    fn the_roster_is_the_host_then_the_seats_still_there_by_seat() {
        // the host left a room of three: the others, by seat
        assert_eq!(roster_order(3, 1, 0b001), vec![1, 2]);
        // seat 0 left and seat 2 hosts: the host first
        assert_eq!(roster_order(3, 2, 0b001), vec![2, 1]);
        // a guest left a room of four
        assert_eq!(roster_order(4, 0, 0b0100), vec![0, 1, 3]);
        // two left a room of five, one of them the host: the successor hosts
        assert_eq!(roster_order(5, 3, 0b10001), vec![3, 1, 2]);
        // nobody left
        assert_eq!(roster_order(3, 0, 0), vec![0, 1, 2]);
        // one player left in the room: a roster of one
        assert_eq!(roster_order(3, 2, 0b011), vec![2]);
        assert_eq!(roster_order(2, 0, 0b10), vec![0]);
        // every peer works the same order out of the same bytes, whatever the room
        for n in 2..=5usize {
            for gone in 0u8..(1 << n) {
                for host in 0..n {
                    let a = roster_order(n, host, gone);
                    assert_eq!(a, roster_order(n, host, gone));
                    assert!(
                        a.iter().all(|&s| gone & (1 << s) == 0),
                        "a seat that left is not played"
                    );
                    assert_eq!(a.len(), n - (gone as u32).count_ones() as usize);
                    if gone & (1 << host) == 0 {
                        assert_eq!(a[0], host);
                    }
                }
            }
        }
    }

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
