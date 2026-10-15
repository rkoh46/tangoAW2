//! Online play from inside the game (Slippi-style): the ONLINE screen's LOBBY ([`crate::online_menu`]) makes or
//! joins a room, the host app connects the two players, and the battle runs on the shared netplay console.
//!
//! **Played alone (the offline console)**, this module is the lobby's pages, drawn over the ONLINE screen
//! ([`apply`], presentation only) from its state in EWRAM ([`STATE`]):
//!
//! - level 1, the LOBBY menu (the game's own menu, relabelled): only the help line is ours;
//! - level 2, a room made (CREATE): its code, in the game's title font, and how the connection stands;
//! - level 3, a code to type (JOIN): six boxes and a grid of the code's letters, driven by the pad (arrows, A types,
//!   B rubs out, START or OK joins) or typed on the keyboard (the app puts the characters in [`TYPED`]);
//! - level 4, joining that room: the code and how the connection stands.
//!
//! The game and the app talk through a mailbox in the same block ([`mailbox`]): the game asks for a room to be
//! made, joined or left ([`REQUEST`], numbered by [`SERIAL`]); the app answers with the room's code and the state
//! of the connection ([`STATUS`], [`MESSAGE`]). The app reads and writes it between frames; nothing here depends
//! on it for the emulation (a console nobody answers just shows "Connecting...").
//!
//! **On the netplay console** of a match made this way (its match subtype has [`ONLINE_MATCH`]):
//!
//! - the console boots straight to Versus' SELECT MAP: the title, Select Mode, Versus and New are pressed for the
//!   players before the match starts ([`boot_more`], the same on both peers and in the replay);
//! - who drives the pad ([`merge`]): SELECT MAP, the Rules screen, the results and the save prompt are the room
//!   host's (seat 0, see `tango_net_protocol::control::ROOM_HOST`); on the Teams screen each player picks their own
//!   armies' CO and colour (UP/DOWN, SELECT, L, R reach the pad from the seat of the army under the cursor; LEFT
//!   and RIGHT from both; A, B, START from the host's); every army is a human's (seat by army, as in any match:
//!   odd armies the host's, even ones the guest's);
//! - back on SELECT MAP after a battle the host picks the next map (a rematch); B there, back to Select Mode, ends
//!   the match for both ([`match_over`]), and the app takes both players back to the offline lobby.
//!
//! The same screens serve the later UNRANKED (random opponents): the Teams screen is where each player picks a
//! colour no other army has (Black Hole too, with the pack) and a CO.

use mgba::core::Core;
use std::sync::atomic::{AtomicBool, Ordering};

// --- State (tangoAW2's 0x0203CA00..0x0203CAFF) -------------------------------------------------------------

pub const STATE: u32 = 0x0203_CA00;
pub const STATE_LEN: u32 = 0x100;
/// 0 the ONLINE menu, 1 LOBBY, 2 a room made, 3 typing a code, 4 a room joined, 5 typing a password (to make a
/// room, or to join one: [`ENTRY`]).
const LEVEL: u32 = STATE;
/// The code grid's cursor.
const GRID: u32 = STATE + 1;
const CODE_LEN: u32 = STATE + 2;
/// Frames left of the "coming soon" notice.
const NOTICE: u32 = STATE + 3;
/// The code typed (JOIN), [`CODE_CHARS`] letters.
const CODE: u32 = STATE + 4;
/// The game's request: 0 none, 1 make a room (with [`PASSWORD`]), 2 join [`CODE`] (with [`PASSWORD`]), 3 leave,
/// 4 ready, 5 not ready, 6 start (the host, everyone ready).
pub const REQUEST: u32 = STATE + 0x0C;
/// Counts requests, so the app sees each once.
pub const SERIAL: u32 = STATE + 0x0D;
/// The app's answer: see [`Status`].
pub const STATUS: u32 = STATE + 0x10;
/// The room's code (the app's, for a room made).
pub const ROOM: u32 = STATE + 0x12;
/// The app's message: the opponent's name, or what went wrong (zero-terminated).
pub const MESSAGE: u32 = STATE + 0x18;
pub const MESSAGE_LEN: u32 = 0x20;
/// Characters typed on the keyboard (the app's), and how many.
pub const TYPED: u32 = STATE + 0x38;
pub const TYPED_LEN: u32 = STATE + 0x48;
pub const TYPED_MAX: u32 = 0x10;
/// The pressing-for-the-players walk: its goal (1 the lobby, 2 Versus' SELECT MAP), step (0xFF done), frames in
/// the step and in all.
const NAV_GOAL: u32 = STATE + 0x50;
const NAV_STEP: u32 = STATE + 0x51;
const NAV_T: u32 = STATE + 0x52;
const NAV_TOTAL: u32 = STATE + 0x54;
/// A netplay console of an online match: 1 once it has started.
const MATCH: u32 = STATE + 0x56;
/// The match is over (B back to Select Mode after SELECT MAP).
const OVER: u32 = STATE + 0x57;
/// What the password page is for: 0 a room to make, 1 the room to join.
const ENTRY: u32 = STATE + 0x58;
const PASSWORD_LEN: u32 = STATE + 0x59;
/// The password (up to [`PASSWORD_CHARS`] letters of [`CODE_ALPHABET`]; none is no password).
pub const PASSWORD: u32 = STATE + 0x5A;
/// The room's players as the app knows them ([`MAX_PLAYERS`] slots of [`PLAYER_SIZE`]): ready (1), flags
/// ([`PRESENT`], [`HOST`], [`YOU`]), the name (zero-terminated).
pub const PLAYERS: u32 = STATE + 0x80;
pub const PLAYER_SIZE: u32 = 0x10;
pub const MAX_PLAYERS: usize = 5;
pub const PRESENT: u8 = 1;
pub const HOST: u8 = 2;
pub const YOU: u8 = 4;
/// An online match's previous frame's keys (its map pick's A).
const MATCH_PREV: u32 = STATE + 0x5E;
const STATE_END: u32 = PLAYERS + PLAYER_SIZE * MAX_PLAYERS as u32;
pub const PASSWORD_CHARS: usize = 4;
/// Players a match has (step 1: two; the room's page has a slot for each of [`MAX_PLAYERS`]).
pub const MATCH_PLAYERS: u8 = 2;

/// A match subtype bit: the match was made in the in-game lobby (boot to Versus, host's screens).
pub const ONLINE_MATCH: u8 = 0x01;
/// The room code's letters: those the game's title font has, less I and O (read as 1 and 0) and B (as 8).
pub const CODE_ALPHABET: &[u8] = b"ACDEGHKLMNPRSTUWY";
pub const CODE_CHARS: usize = 6;

/// What the app says about the connection.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum Status {
    /// Nothing yet (the request is on its way).
    None = 0,
    /// The room is open: waiting for the other player.
    Waiting = 1,
    Connecting = 2,
    /// Both in: [`MESSAGE`] is the other player's name; the battle is starting.
    Connected = 3,
    /// [`MESSAGE`] says why.
    Failed = 4,
    /// Back from a match: [`MESSAGE`] says how it ended (shown on the LOBBY menu).
    Back = 5,
}

impl Status {
    fn of(v: u8) -> Status {
        match v {
            1 => Status::Waiting,
            2 => Status::Connecting,
            3 => Status::Connected,
            4 => Status::Failed,
            5 => Status::Back,
            _ => Status::None,
        }
    }
}

pub fn level(core: &Core) -> u8 {
    core.raw_read_8(LEVEL, -1)
}

// --- The mailbox (the host app's side) ---------------------------------------------------------------

/// The host app's side of the mailbox, over its own reads and writes of the console's memory (between frames).
pub mod mailbox {
    use super::*;

    /// What the game asks for.
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub enum Request {
        /// Make a room (the app picks its code: [`write_room`]), with this password (may be empty).
        Host {
            password: String,
        },
        /// Join the room with this code and password.
        Join {
            code: String,
            password: String,
        },
        Leave,
        Ready,
        NotReady,
        /// The host starts the match (every player is ready).
        Start,
    }

    /// The request numbered `serial`, if it is new (`seen` is the last serial the app has handled).
    pub fn read_request(read: &mut dyn FnMut(u32, &mut [u8]), seen: u8) -> Option<(u8, Request)> {
        let mut b = [0u8; 0x60];
        read(STATE, &mut b);
        let (kind, serial) = (b[0x0C], b[0x0D]);
        if serial == seen {
            return None;
        }
        let text = |at: usize, n: usize| -> String {
            b[at..at + n]
                .iter()
                .take_while(|&&c| c != 0)
                .map(|&c| c as char)
                .collect()
        };
        let code = text(4, CODE_CHARS);
        let pl = (b[0x59] as usize).min(PASSWORD_CHARS);
        let password = text(0x5A, pl);
        let r = match kind {
            1 => Request::Host { password },
            2 => Request::Join { code, password },
            4 => Request::Ready,
            5 => Request::NotReady,
            6 => Request::Start,
            _ => Request::Leave,
        };
        Some((serial, r))
    }

    /// One player's slot on the room's page (`slot` 0 is the host).
    pub fn write_player(write: &mut dyn FnMut(u32, &[u8]), slot: usize, player: Option<(&str, bool, u8)>) {
        let mut b = [0u8; PLAYER_SIZE as usize];
        if let Some((name, ready, flags)) = player {
            b[0] = ready as u8;
            b[1] = flags | PRESENT;
            for (k, c) in name
                .chars()
                .filter(|c| c.is_ascii() && !c.is_ascii_control())
                .take(PLAYER_SIZE as usize - 3)
                .enumerate()
            {
                b[2 + k] = c as u8;
            }
        }
        write(PLAYERS + PLAYER_SIZE * slot as u32, &b);
    }

    /// The serial of the last request (for an app that starts watching a console already running).
    pub fn serial(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
        let mut b = [0u8];
        read(SERIAL, &mut b);
        b[0]
    }

    /// The level the lobby is on (0 the ONLINE menu .. 4 joining).
    pub fn level(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
        let mut b = [0u8];
        read(LEVEL, &mut b);
        b[0]
    }

    pub fn write_status(write: &mut dyn FnMut(u32, &[u8]), status: Status, message: &str) {
        let mut m = vec![0u8; MESSAGE_LEN as usize];
        for (k, c) in message
            .chars()
            .filter(|c| c.is_ascii() && !c.is_ascii_control())
            .take(MESSAGE_LEN as usize - 1)
            .enumerate()
        {
            m[k] = c as u8;
        }
        write(MESSAGE, &m);
        write(STATUS, &[status as u8]);
    }

    pub fn write_room(write: &mut dyn FnMut(u32, &[u8]), code: &str) {
        let mut b = [0u8; CODE_CHARS];
        for (k, c) in code.bytes().take(CODE_CHARS).enumerate() {
            b[k] = c;
        }
        write(ROOM, &b);
    }

    /// Characters typed on the keyboard, for the code being typed: letters, 8 to rub one out, 13 to join.
    /// Returns false when the lobby is not taking typing (nothing written).
    pub fn type_chars(read: &mut dyn FnMut(u32, &mut [u8]), write: &mut dyn FnMut(u32, &[u8]), chars: &[u8]) -> bool {
        if !matches!(level(read), 3 | 5) {
            return false;
        }
        let mut n = [0u8];
        read(TYPED_LEN, &mut n);
        let mut q = vec![0u8; TYPED_MAX as usize];
        read(TYPED, &mut q);
        let mut n = n[0].min(TYPED_MAX as u8) as usize;
        for &c in chars {
            if n < TYPED_MAX as usize {
                q[n] = c;
                n += 1;
            }
        }
        write(TYPED, &q);
        write(TYPED_LEN, &[n as u8]);
        true
    }

    /// A fresh room code.
    pub fn new_code(seed: u64) -> String {
        let mut x = seed | 1;
        (0..CODE_CHARS)
            .map(|_| {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                CODE_ALPHABET[(x % CODE_ALPHABET.len() as u64) as usize] as char
            })
            .collect()
    }

    /// The matchmaking code a room's code stands for (the prefix keeps it apart from other Tango players' codes).
    /// A password is part of the code: a wrong one meets nobody.
    pub fn link_code(room: &str, password: &str) -> String {
        if password.is_empty() {
            format!("tangoaw2-room-{}", room.to_ascii_lowercase())
        } else {
            format!(
                "tangoaw2-room-{}-{}",
                room.to_ascii_lowercase(),
                password.to_ascii_lowercase()
            )
        }
    }

    /// Asks the console just booted to go straight to the LOBBY menu (offline; the next boot only).
    pub fn boot_to_lobby() {
        BOOT_TO_LOBBY.store(true, Ordering::Relaxed);
    }
}

static BOOT_TO_LOBBY: AtomicBool = AtomicBool::new(false);

// --- Keys -------------------------------------------------------------------------------------------

const KEY_A: u32 = 1 << 0;
const KEY_B: u32 = 1 << 1;
const KEY_SELECT: u32 = 1 << 2;
const KEY_START: u32 = 1 << 3;
const KEY_RIGHT: u32 = 1 << 4;
const KEY_LEFT: u32 = 1 << 5;
const KEY_UP: u32 = 1 << 6;
const KEY_DOWN: u32 = 1 << 7;
const KEY_R: u32 = 1 << 8;
const KEY_L: u32 = 1 << 9;
const ALL_KEYS: u32 = 0x3FF;

// --- The lobby (offline) ---------------------------------------------------------------------------

fn request(core: &mut Core, kind: u8) {
    core.raw_write_8(REQUEST, -1, kind);
    let s = core.raw_read_8(SERIAL, -1).wrapping_add(1);
    core.raw_write_8(SERIAL, -1, s);
    if kind <= 3 {
        core.raw_write_8(STATUS, -1, 0);
        core.raw_write_range(MESSAGE, -1, &[0u8; MESSAGE_LEN as usize]);
        core.raw_write_range(PLAYERS, -1, &[0u8; (PLAYER_SIZE * MAX_PLAYERS as u32) as usize]);
    }
}

fn set_level(core: &mut Core, l: u8) {
    core.raw_write_8(LEVEL, -1, l);
}

/// The grid: the alphabet, then rub out and OK. Six columns.
const GRID_COLS: usize = 6;
const GRID_DEL: usize = CODE_ALPHABET.len();
const GRID_OK: usize = CODE_ALPHABET.len() + 1;
const GRID_CELLS: usize = CODE_ALPHABET.len() + 2;

/// The text being typed: the room's code (level 3) or a password (level 5): (where, its length's byte, at most,
/// at least).
fn field(core: &Core) -> (u32, u32, usize, usize) {
    if level(core) == 5 {
        (PASSWORD, PASSWORD_LEN, PASSWORD_CHARS, 0)
    } else {
        (CODE, CODE_LEN, CODE_CHARS, CODE_CHARS)
    }
}

fn read_text(core: &Core, at: u32, len_at: u32, max: usize) -> String {
    let n = (core.raw_read_8(len_at, -1) as usize).min(max);
    (0..n).map(|k| core.raw_read_8(at + k as u32, -1) as char).collect()
}

fn code(core: &Core) -> String {
    read_text(core, CODE, CODE_LEN, CODE_CHARS)
}

fn password(core: &Core) -> String {
    read_text(core, PASSWORD, PASSWORD_LEN, PASSWORD_CHARS)
}

fn typed(core: &Core) -> String {
    let (at, len, max, _) = field(core);
    read_text(core, at, len, max)
}

fn type_char(core: &mut Core, c: u8) {
    let c = c.to_ascii_uppercase();
    let (at, len, max, _) = field(core);
    let n = core.raw_read_8(len, -1) as u32;
    if CODE_ALPHABET.contains(&c) && (n as usize) < max {
        core.raw_write_8(at + n, -1, c);
        core.raw_write_8(len, -1, n as u8 + 1);
    }
}

fn rub_out(core: &mut Core) -> bool {
    let (at, len, _, _) = field(core);
    let n = core.raw_read_8(len, -1);
    if n == 0 {
        return false;
    }
    core.raw_write_8(len, -1, n - 1);
    core.raw_write_8(at + n as u32 - 1, -1, 0);
    true
}

fn clear_field(core: &mut Core, at: u32, len: u32, max: usize) {
    core.raw_write_8(len, -1, 0);
    core.raw_write_range(at, -1, &vec![0u8; max]);
}

/// OK on the typing page: a code goes on to its password; a password makes or joins the room.
fn accept(core: &mut Core) {
    let (_, len, _, min) = field(core);
    if (core.raw_read_8(len, -1) as usize) < min {
        return;
    }
    if level(core) == 3 {
        clear_field(core, PASSWORD, PASSWORD_LEN, PASSWORD_CHARS);
        core.raw_write_8(ENTRY, -1, 1);
        core.raw_write_8(GRID, -1, GRID_OK as u8);
        set_level(core, 5);
    } else if core.raw_read_8(ENTRY, -1) == 1 {
        request(core, 2);
        set_level(core, 4);
    } else {
        core.raw_write_range(ROOM, -1, &[0u8; CODE_CHARS]);
        request(core, 1);
        set_level(core, 2);
    }
}

/// Back from the typing page.
fn back_from_typing(core: &mut Core) {
    if level(core) == 5 && core.raw_read_8(ENTRY, -1) == 1 {
        core.raw_write_8(GRID, -1, 0);
        set_level(core, 3);
    } else {
        set_level(core, 1);
    }
}

fn player(core: &Core, slot: usize) -> Option<(String, bool, u8)> {
    let mut b = [0u8; PLAYER_SIZE as usize];
    core.raw_read_range(PLAYERS + PLAYER_SIZE * slot as u32, -1, &mut b);
    (b[1] & PRESENT != 0).then(|| {
        (
            b[2..].iter().take_while(|&&c| c != 0).map(|&c| c as char).collect(),
            b[0] == 1,
            b[1],
        )
    })
}

/// The players in the room, and whether every one but the host is ready (the host's START).
fn room_state(core: &Core) -> (usize, bool, bool) {
    let players: Vec<(String, bool, u8)> = (0..MAX_PLAYERS).filter_map(|k| player(core, k)).collect();
    let me = players.iter().find(|p| p.2 & YOU != 0);
    let my_ready = me.is_some_and(|p| p.1);
    let others_ready =
        players.len() >= MATCH_PLAYERS as usize && players.iter().filter(|p| p.2 & HOST == 0).all(|p| p.1);
    (players.len(), my_ready, others_ready)
}

/// Every frame on the offline console: the walk to the lobby, the ONLINE screen's menu levels and the lobby's
/// pages. Returns the keys the game gets.
pub fn tick(core: &mut Core, offline: bool, keys: u32, prev: u32) -> u32 {
    if !offline {
        return keys;
    }
    if let Some(k) = nav(core) {
        return k;
    }
    let n = core.raw_read_8(NOTICE, -1);
    if n > 0 {
        core.raw_write_8(NOTICE, -1, n - 1);
    }
    let Some(cursor) = crate::online_menu::cursor(core).filter(|_| crate::online_menu::active(core)) else {
        // Left the ONLINE screen: the lobby closes (a room made or joined is left).
        if matches!(level(core), 2 | 4) {
            request(core, 3);
        }
        if level(core) != 0 {
            set_level(core, 0);
        }
        return keys;
    };
    let pressed = keys & !prev;
    let level = level(core);
    crate::online_menu::draw(core, level as usize);
    match level {
        0 => {
            if pressed & (KEY_A | KEY_START) != 0 {
                if cursor == 1 {
                    set_level(core, 1);
                } else {
                    core.raw_write_8(NOTICE, -1, 120);
                }
            }
            keys & !(KEY_A | KEY_START)
        }
        1 => {
            if pressed & (KEY_A | KEY_START) != 0 {
                match cursor {
                    0 => {
                        // CREATE: a password first (none is fine: OK or START).
                        clear_field(core, PASSWORD, PASSWORD_LEN, PASSWORD_CHARS);
                        core.raw_write_8(ENTRY, -1, 0);
                        core.raw_write_8(GRID, -1, GRID_OK as u8);
                        core.raw_write_8(TYPED_LEN, -1, 0);
                        set_level(core, 5);
                    }
                    1 => {
                        clear_field(core, CODE, CODE_LEN, CODE_CHARS);
                        core.raw_write_8(GRID, -1, 0);
                        core.raw_write_8(TYPED_LEN, -1, 0);
                        set_level(core, 3);
                    }
                    _ => set_level(core, 0),
                }
            } else if pressed & KEY_B != 0 {
                set_level(core, 0);
            }
            if pressed & (KEY_UP | KEY_DOWN) != 0 && Status::of(core.raw_read_8(STATUS, -1)) == Status::Back {
                core.raw_write_8(STATUS, -1, 0);
            }
            keys & !(KEY_A | KEY_B | KEY_START)
        }
        2 | 4 => {
            let (_, my_ready, others_ready) = room_state(core);
            let host = level == 2;
            let connected = Status::of(core.raw_read_8(STATUS, -1)) == Status::Connected;
            if pressed & KEY_B != 0 {
                request(core, 3);
                set_level(core, 1);
            } else if connected && !host && pressed & KEY_A != 0 {
                request(core, if my_ready { 5 } else { 4 });
            } else if connected && host && others_ready && !my_ready && pressed & (KEY_START | KEY_A) != 0 {
                request(core, 6);
            }
            keys & !ALL_KEYS
        }
        3 | 5 => {
            code_entry(core, pressed);
            keys & !ALL_KEYS
        }
        _ => {
            set_level(core, 0);
            keys
        }
    }
}

fn code_entry(core: &mut Core, pressed: u32) {
    // The keyboard first.
    let n = (core.raw_read_8(TYPED_LEN, -1) as u32).min(TYPED_MAX);
    if n > 0 {
        let mut q = vec![0u8; n as usize];
        core.raw_read_range(TYPED, -1, &mut q);
        core.raw_write_8(TYPED_LEN, -1, 0);
        let start = level(core);
        for c in q {
            match c {
                8 => {
                    rub_out(core);
                }
                13 => accept(core),
                27 => back_from_typing(core),
                c => type_char(core, c),
            }
            if level(core) != start {
                return;
            }
        }
    }
    let mut g = (core.raw_read_8(GRID, -1) as usize).min(GRID_CELLS - 1);
    let rows = GRID_CELLS.div_ceil(GRID_COLS);
    let (mut r, mut c) = (g / GRID_COLS, g % GRID_COLS);
    if pressed & KEY_RIGHT != 0 {
        c = (c + 1) % GRID_COLS;
    }
    if pressed & KEY_LEFT != 0 {
        c = (c + GRID_COLS - 1) % GRID_COLS;
    }
    if pressed & KEY_DOWN != 0 {
        r = (r + 1) % rows;
    }
    if pressed & KEY_UP != 0 {
        r = (r + rows - 1) % rows;
    }
    if pressed & (KEY_RIGHT | KEY_LEFT | KEY_UP | KEY_DOWN) != 0 {
        g = (r * GRID_COLS + c).min(GRID_CELLS - 1);
        core.raw_write_8(GRID, -1, g as u8);
    }
    if pressed & KEY_A != 0 {
        match g {
            GRID_DEL => {
                rub_out(core);
            }
            GRID_OK => accept(core),
            _ => {
                type_char(core, CODE_ALPHABET[g]);
                let (_, len, max, _) = field(core);
                if core.raw_read_8(len, -1) as usize == max {
                    core.raw_write_8(GRID, -1, GRID_OK as u8);
                }
            }
        }
    } else if pressed & KEY_START != 0 {
        accept(core);
    } else if pressed & KEY_B != 0 && !rub_out(core) {
        back_from_typing(core);
    }
}

// --- Pressing for the players (the walk to the lobby, or to Versus' SELECT MAP) -----------------------------

const GOAL_LOBBY: u8 = 1;
const GOAL_VERSUS: u8 = 2;
const NAV_DONE: u8 = 0xFF;
/// The Select Mode wheel's position (Link 1, Versus 3).
const WHEEL_CURSOR: u32 = 0x0300_591C;
const WHEEL_LINK: u8 = 1;
const WHEEL_VERSUS: u8 = 3;
/// The wheel's box: its bottom row (New).
const BOX_NEW: u16 = 7;
/// Give up walking after this many frames (the player has the pad then).
const NAV_MAX: u16 = 4000;

fn start_nav(core: &mut Core, goal: u8) {
    core.raw_write_8(NAV_GOAL, -1, goal);
    core.raw_write_8(NAV_STEP, -1, 0);
    core.raw_write_16(NAV_T, -1, 0);
    core.raw_write_16(NAV_TOTAL, -1, 0);
}

fn navigating(core: &Core) -> bool {
    let g = core.raw_read_8(NAV_GOAL, -1);
    (g == GOAL_LOBBY || g == GOAL_VERSUS) && core.raw_read_8(NAV_STEP, -1) != NAV_DONE
}

/// A press: `key` held for 6 frames of every `period`.
fn pulse(t: u16, period: u16, key: u32) -> u32 {
    if t % period < 6 {
        key
    } else {
        0
    }
}

/// One frame of the walk: the keys to press, or `None` once it is done (or there is none).
fn nav(core: &mut Core) -> Option<u32> {
    if !navigating(core) {
        return None;
    }
    let goal = core.raw_read_8(NAV_GOAL, -1);
    let step = core.raw_read_8(NAV_STEP, -1);
    let t = core.raw_read_16(NAV_T, -1);
    let total = core.raw_read_16(NAV_TOTAL, -1).saturating_add(1);
    core.raw_write_16(NAV_TOTAL, -1, total);
    let next = |core: &mut Core, s: u8| {
        core.raw_write_8(NAV_STEP, -1, s);
        core.raw_write_16(NAV_T, -1, 0);
    };
    if total > NAV_MAX {
        next(core, NAV_DONE);
        return None;
    }
    core.raw_write_16(NAV_T, -1, t.wrapping_add(1));
    let keys = match step {
        // The title: START, then A, until Select Mode is up.
        0 => {
            if crate::campaign_menu::on_select_mode(core) {
                next(core, 1);
                0
            } else {
                pulse(t, 40, KEY_START) | pulse(t + 20, 40, KEY_A)
            }
        }
        // Select Mode: let the wheel come in, then turn it to the goal's entry.
        1 => {
            let target = if goal == GOAL_LOBBY { WHEEL_LINK } else { WHEEL_VERSUS };
            let cur = core.raw_read_8(WHEEL_CURSOR, -1);
            if t < 60 {
                0
            } else if cur == target {
                if t % 48 >= 40 {
                    next(core, 2);
                }
                0
            } else {
                let n = if crate::mode_menu::active(core) { 7 } else { 6 };
                let up = (target as i32 - cur as i32).rem_euclid(n) <= n / 2;
                pulse(t, 48, if up { KEY_UP } else { KEY_DOWN })
            }
        }
        // A on it.
        2 => {
            if t >= 6 {
                next(core, 3);
            }
            KEY_A
        }
        3 => {
            if goal == GOAL_LOBBY {
                if crate::online_menu::menu_proc(core).is_some() {
                    next(core, 4);
                }
                0
            } else if crate::survival_ui::selecting(core) {
                next(core, 4);
                0
            } else if let Some(row) = crate::campaign_menu::box_cursor(core) {
                // Versus' box: New (a suspended Versus game is never continued).
                if t < 20 {
                    0
                } else if row != BOX_NEW {
                    pulse(t, 24, KEY_DOWN)
                } else if t % 24 >= 16 {
                    next(core, 5);
                    0
                } else {
                    0
                }
            } else {
                0
            }
        }
        4 => {
            if goal == GOAL_LOBBY {
                if t >= 30 && crate::online_menu::active(core) {
                    set_level(core, 1);
                    next(core, NAV_DONE);
                }
            } else if crate::survival_ui::idle(core) {
                next(core, NAV_DONE);
            }
            0
        }
        // Versus' box: A on New, then on to SELECT MAP.
        5 => {
            if t >= 6 {
                next(core, 3);
            }
            KEY_A
        }
        _ => {
            next(core, NAV_DONE);
            0
        }
    };
    Some(keys)
}

/// Whether the console should run another tick before its session takes over: the walk of an online match
/// (netplay: to SELECT MAP) or of a console asked to boot to the lobby.
pub fn boot_more(core: &Core, mode: Option<(u8, u8)>) -> bool {
    match mode {
        Some((_, sub)) if sub & ONLINE_MATCH != 0 => core.raw_read_8(MATCH, -1) == 0 || navigating(core),
        None => BOOT_TO_LOBBY.load(Ordering::Relaxed) || navigating(core),
        _ => false,
    }
}

/// Every frame on any console, first: an online match's walk, and its end. Returns the keys the game gets.
pub fn before(core: &mut Core, mode: Option<(u8, u8)>, keys: u32) -> u32 {
    match mode {
        Some((_, sub)) if sub & ONLINE_MATCH != 0 => {
            if core.raw_read_8(MATCH, -1) == 0 {
                core.raw_write_8(MATCH, -1, 1);
                core.raw_write_8(OVER, -1, 0);
                start_nav(core, GOAL_VERSUS);
            }
            if let Some(k) = nav(core) {
                return k;
            }
            if crate::campaign_menu::on_select_mode(core) {
                core.raw_write_8(OVER, -1, 1);
            }
            let n = core.raw_read_8(NOTICE, -1);
            if n > 0 {
                core.raw_write_8(NOTICE, -1, n - 1);
            }
            // SELECT MAP: only a map for as many armies as there are players. (The previous keys kept are those the
            // game got, so an A held on such a map stays new, and refused, every frame.)
            let prev = core.raw_read_16(MATCH_PREV, -1) as u32;
            let mut keys = keys;
            if keys & !prev & KEY_A != 0
                && crate::survival_ui::idle(core)
                && map_armies(core).is_some_and(|n| n != MATCH_PLAYERS)
            {
                keys &= !KEY_A;
                core.raw_write_8(NOTICE, -1, 120);
            }
            core.raw_write_16(MATCH_PREV, -1, keys as u16);
            // Every army is a player's.
            if crate::pvp::on_teams_screen(core) {
                for (rec, at) in [(0x0201_7C50u32, 0x09u32), (0x0203_0300, 0x90)] {
                    let n = if at == 0x09 {
                        core.raw_read_8(rec + 8, -1).min(4)
                    } else {
                        5
                    };
                    for a in 0..n as u32 {
                        if core.raw_read_8(rec + at + a, -1) == 2 {
                            core.raw_write_8(rec + at + a, -1, 1);
                        }
                    }
                }
            }
            keys
        }
        None => {
            if BOOT_TO_LOBBY.swap(false, Ordering::Relaxed) {
                start_nav(core, GOAL_LOBBY);
            }
            keys
        }
        _ => keys,
    }
}

const LIST_FIRST: u32 = 0x0300_5900;
const LIST_CURSOR: u32 = 0x0300_5930;
const LIST_IDS: u32 = 0x0202_7F78;

/// How many armies the map under SELECT MAP's cursor has.
fn map_armies(core: &Core) -> Option<u8> {
    let i = core
        .raw_read_32(LIST_FIRST, -1)
        .wrapping_add(core.raw_read_32(LIST_CURSOR, -1));
    if i > 0x31 {
        return None;
    }
    let id = core.raw_read_8(LIST_IDS + i, -1) as u32;
    let n = core.raw_read_8(crate::five_map::table(core) + 0x5C * id + 0x18, -1);
    (1..=5).contains(&n).then_some(n)
}

/// The online match's notes over its console (presentation only): a map for another number of players.
pub fn apply_match(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 || core.raw_read_8(MATCH, -1) != 1 || core.raw_read_8(NOTICE, -1) == 0 {
        return;
    }
    if crate::survival_ui::selecting(core) {
        let mut cv = Rgba(rgba);
        bar(&mut cv, core, &format!("Pick a map for {MATCH_PLAYERS} players."));
    }
}

/// The match is over: its players left SELECT MAP for Select Mode.
pub fn match_over(core: &Core) -> bool {
    core.raw_read_8(MATCH, -1) == 1 && core.raw_read_8(OVER, -1) == 1
}

/// Who drives the pad on an online match's console, outside a battle's turns (`None`: the usual rules).
pub fn merge(core: &Core, inputs: [u32; 2]) -> Option<u32> {
    if core.raw_read_8(MATCH, -1) != 1 {
        return None;
    }
    if navigating(core) {
        return Some(0);
    }
    if !crate::pvp::in_versus(core) || crate::pvp::in_battle(core) {
        return None;
    }
    if crate::pvp::on_teams_screen(core) && !crate::five::active(core) {
        let slot = (core.raw_read_8(0x0201_7C50 + 0x32, -1) / 2) as u8;
        let owner = crate::pvp::seat_of(slot + 1);
        let both = inputs[0] | inputs[1];
        return Some(
            (inputs[owner] & (KEY_UP | KEY_DOWN | KEY_SELECT | KEY_L | KEY_R))
                | (both & (KEY_LEFT | KEY_RIGHT))
                | (inputs[0] & (KEY_A | KEY_B | KEY_START)),
        );
    }
    if crate::pvp::on_teams_screen(core) {
        return Some(inputs[0] | inputs[1]);
    }
    Some(inputs[0])
}

// --- Drawing (presentation only) ------------------------------------------------------------------

const W: usize = 240;
const H: usize = 160;
const FONT_GLYPHS: u32 = 0x084C_32E4;
const FONT_WIDTHS: u32 = 0x084C_36E4;

type Rgb = (u8, u8, u8);
const WHITE: Rgb = (255, 255, 255);
const INK: Rgb = (16, 16, 24);
const SHADE: Rgb = (176, 184, 200);
const RED: Rgb = (240, 48, 56);
const BLUE: Rgb = (48, 64, 232);
const LIGHT_GRAY: Rgb = (232, 232, 236);
const GRAY_INK: Rgb = (104, 112, 128);
const CREAM: Rgb = (255, 246, 214);
const YELLOW: Rgb = (255, 224, 64);
const BAR: Rgb = (24, 24, 32);

struct Rgba<'a>(&'a mut [u8]);

impl Rgba<'_> {
    fn put(&mut self, x: i32, y: i32, c: Rgb) {
        if (0..W as i32).contains(&x) && (0..H as i32).contains(&y) {
            let o = 4 * (W * y as usize + x as usize);
            self.0[o..o + 3].copy_from_slice(&[c.0, c.1, c.2]);
        }
    }
    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: Rgb) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.put(xx, yy, c);
            }
        }
    }
    /// A window as the game's: white, red above, blue below, a light edge at the sides.
    fn window(&mut self, x: i32, y: i32, w: i32, h: i32) {
        self.rect(x - 1, y - 1, w + 2, h + 2, INK);
        self.rect(x, y, w, h, WHITE);
        self.rect(x + 1, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x + w - 2, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x, y, w, 2, RED);
        self.rect(x, y + h - 2, w, 2, BLUE);
    }
    /// AW2's proportional font; returns the x after the text.
    fn text(&mut self, core: &Core, x: i32, y: i32, s: &str, ink: Rgb, shade: Rgb) -> i32 {
        let mut x = x;
        for c in s.bytes() {
            let w = core.raw_read_8(FONT_WIDTHS + c as u32, -1) as usize;
            let at = core.raw_read_32(FONT_GLYPHS + 4 * c as u32, -1);
            if (0x0800_0000..0x0A00_0000).contains(&at) {
                let stride = w.div_ceil(2);
                for r in 0..11 {
                    for cx in 0..w {
                        let b = core.raw_read_8(at + (stride * (3 + r) + cx / 2) as u32, -1);
                        let v = (b >> (4 * (cx & 1))) & 15;
                        if v != 0 {
                            self.put(x + cx as i32, y + r as i32, if v == 0xA { ink } else { shade });
                        }
                    }
                }
            }
            x += w as i32 + 1;
        }
        x
    }
}

fn text_width(core: &Core, s: &str) -> i32 {
    s.bytes()
        .map(|c| core.raw_read_8(FONT_WIDTHS + c as u32, -1) as i32 + 1)
        .sum::<i32>()
        - 1
}

fn bgr(c: u16) -> Rgb {
    let f = |v: u16| ((v & 31) * 255 / 31) as u8;
    (f(c), f(c >> 5), f(c >> 10))
}

/// A word in the game's title font (its OBJ palette 15, as the screen's title), from (x, y).
fn title(cv: &mut Rgba, core: &Core, font: &crate::online_art::TitleFont, x: i32, y: i32, word: &str) {
    let pal: Vec<Rgb> = (0..16)
        .map(|i| bgr(core.raw_read_16(0x0500_0200 + 15 * 32 + 2 * i, -1)))
        .collect();
    for (c, gx) in font.layout(word, x) {
        let Some(g) = crate::online_art::TitleFont::index(c).and_then(|i| font.px.get(i)) else {
            continue;
        };
        for py in 0..32 {
            for px in 0..16 {
                let v = g.get(px, py);
                if v != 0 {
                    cv.put(gx + px as i32, y + py as i32 - 4, pal[v as usize]);
                }
            }
        }
    }
}

fn title_font(core: &Core) -> Option<&'static crate::online_art::TitleFont> {
    static FONT: std::sync::OnceLock<Option<crate::online_art::TitleFont>> = std::sync::OnceLock::new();
    FONT.get_or_init(|| crate::online_art::TitleFont::load(core)).as_ref()
}

fn message(core: &Core) -> String {
    let mut b = [0u8; MESSAGE_LEN as usize];
    core.raw_read_range(MESSAGE, -1, &mut b);
    b.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect()
}

fn room(core: &Core) -> String {
    let mut b = [0u8; CODE_CHARS];
    core.raw_read_range(ROOM, -1, &mut b);
    b.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect()
}

/// The help bar at the bottom, over the game's.
fn bar(cv: &mut Rgba, core: &Core, s: &str) {
    cv.rect(0, 144, W as i32, 16, BAR);
    let w = text_width(core, s);
    cv.text(core, (W as i32 - w) / 2, 147, s, WHITE, GRAY_INK);
}

/// Lines of at most `width` pixels.
fn wrap(core: &Core, s: &str, width: i32) -> Vec<String> {
    let mut lines = Vec::new();
    let mut line = String::new();
    for w in s.split_whitespace() {
        let next = if line.is_empty() {
            w.to_string()
        } else {
            format!("{line} {w}")
        };
        if text_width(core, &next) > width && !line.is_empty() {
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

const PANEL: (i32, i32, i32, i32) = (92, 26, 142, 114);

/// How the connection stands, in words.
fn status_lines(core: &Core, hosting: bool) -> (Vec<String>, Rgb) {
    let m = message(core);
    match Status::of(core.raw_read_8(STATUS, -1)) {
        Status::None | Status::Back => (
            vec![if hosting {
                "Opening the room..."
            } else {
                "Connecting..."
            }
            .into()],
            GRAY_INK,
        ),
        Status::Waiting => (vec!["Waiting for a player...".into()], INK),
        Status::Connecting => (vec!["Connecting...".into()], INK),
        Status::Connected => (vec![format!("Connected: {m}"), "The battle is starting!".into()], BLUE),
        Status::Failed => (
            wrap(core, if m.is_empty() { "Could not connect." } else { &m }, PANEL.2 - 12),
            RED,
        ),
    }
}

/// The lobby's pages over the ONLINE screen (offline): see the module's docs.
pub fn apply(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 || !crate::online_menu::active(core) {
        return;
    }
    let Some(cursor) = crate::online_menu::cursor(core) else {
        return;
    };
    let mut cv = Rgba(rgba);
    let level = level(core);
    match level {
        0 => {
            if core.raw_read_8(NOTICE, -1) > 0 && cursor != 1 {
                bar(&mut cv, core, "Coming soon!");
            }
        }
        1 => {
            let back = (Status::of(core.raw_read_8(STATUS, -1)) == Status::Back)
                .then(|| message(core))
                .filter(|m| !m.is_empty());
            let help = [
                "Make a room and give its code to a friend.",
                "Type in the code of a friend's room.",
                "Back to ONLINE.",
            ];
            bar(&mut cv, core, back.as_deref().unwrap_or(help[cursor as usize % 3]));
        }
        2 | 4 => {
            let Some(font) = title_font(core) else { return };
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            let hosting = level == 2;
            let head = if hosting { "Your room" } else { "Room" };
            let code = if hosting { room(core) } else { code(core) };
            cv.text(core, x + 6, y + 5, head, GRAY_INK, SHADE);
            let pw = password(core);
            if !pw.is_empty() {
                let t = format!("Password {pw}");
                cv.text(core, x + w - 6 - text_width(core, &t), y + 5, &t, GRAY_INK, SHADE);
            }
            if code.is_empty() {
                cv.text(
                    core,
                    x + (w - text_width(core, "- - - - - -")) / 2,
                    y + 24,
                    "- - - - - -",
                    GRAY_INK,
                    SHADE,
                );
            } else {
                title(&mut cv, core, font, x + (w - font.width(&code)) / 2, y + 16, &code);
            }
            // The players: a row a slot.
            let status = Status::of(core.raw_read_8(STATUS, -1));
            let (count, my_ready, others_ready) = room_state(core);
            for k in 0..MAX_PLAYERS {
                let ry = y + 46 + 11 * k as i32;
                cv.rect(x + 4, ry + 10, w - 8, 1, LIGHT_GRAY);
                let n = format!("{}", k + 1);
                cv.text(core, x + 6, ry, &n, GRAY_INK, SHADE);
                match player(core, k) {
                    Some((name, ready, flags)) => {
                        let name = if name.is_empty() { "Player".to_string() } else { name };
                        let you = if flags & YOU != 0 { " (you)" } else { "" };
                        cv.text(core, x + 16, ry, &format!("{name}{you}"), INK, SHADE);
                        let tag = if flags & HOST != 0 {
                            if ready {
                                "START"
                            } else {
                                "HOST"
                            }
                        } else if ready {
                            "READY"
                        } else {
                            "..."
                        };
                        let ink = if ready { BLUE } else { GRAY_INK };
                        cv.text(core, x + w - 6 - text_width(core, tag), ry, tag, ink, SHADE);
                    }
                    None => {
                        let t = if (k as u8) < MATCH_PLAYERS { "Open" } else { "-" };
                        cv.text(core, x + 16, ry, t, SHADE, LIGHT_GRAY);
                    }
                }
            }
            let _ = count;
            let hint: String = match status {
                Status::Connected if hosting && others_ready && !my_ready => "Everyone is ready.  START: Start".into(),
                Status::Connected if hosting && my_ready => "Starting...".into(),
                Status::Connected if hosting => "Waiting for READY...  B: Close".into(),
                Status::Connected if my_ready => "Ready!  A: Not ready  B: Leave".into(),
                Status::Connected => "A: Ready  B: Leave".into(),
                _ => {
                    let (lines, _) = status_lines(core, hosting);
                    let mut l = lines.join(" ");
                    l.push_str(if hosting { "  B: Close" } else { "  B: Back" });
                    l
                }
            };
            bar(&mut cv, core, &hint);
            if status == Status::Failed {
                let (lines, ink) = status_lines(core, hosting);
                cv.rect(x + 3, y + 45, w - 6, 56, WHITE);
                for (k, l) in lines.iter().take(4).enumerate() {
                    cv.text(
                        core,
                        x + (w - text_width(core, l)) / 2,
                        y + 50 + 13 * k as i32,
                        l,
                        ink,
                        SHADE,
                    );
                }
            }
        }
        3 | 5 => {
            let Some(font) = title_font(core) else { return };
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            let joining = level == 3 || core.raw_read_8(ENTRY, -1) == 1;
            let head = match (level, joining) {
                (3, _) => "Type the room's code",
                (_, true) => "Its password (if it has one)",
                _ => "A password? (none: OK)",
            };
            cv.text(core, x + (w - text_width(core, head)) / 2, y + 5, head, GRAY_INK, SHADE);
            let chars = if level == 3 { CODE_CHARS } else { PASSWORD_CHARS };
            let typed: Vec<char> = typed(core).chars().collect();
            let bw = 18;
            let bx = x + (w - (bw + 3) * chars as i32 + 3) / 2;
            for k in 0..chars as i32 {
                let cx = bx + k * (bw + 3);
                let here = k as usize == typed.len();
                cv.rect(cx, y + 19, bw, 26, if here { CREAM } else { LIGHT_GRAY });
                cv.rect(cx, y + 43, bw, 2, if here { RED } else { SHADE });
                if let Some(&c) = typed.get(k as usize) {
                    let s = c.to_string();
                    title(&mut cv, core, font, cx + (bw - font.width(&s)) / 2, y + 17, &s);
                }
            }
            let g = core.raw_read_8(GRID, -1) as usize;
            let (cw, ch) = (22, 13);
            let gx = x + (w - cw * GRID_COLS as i32) / 2;
            let gy = y + 50;
            let (_, _, max, min) = field(core);
            for k in 0..GRID_CELLS {
                let (r, c) = ((k / GRID_COLS) as i32, (k % GRID_COLS) as i32);
                let (cx, cy) = (gx + c * cw, gy + r * ch);
                let label = match k {
                    GRID_DEL => "Del".to_string(),
                    GRID_OK => "OK".to_string(),
                    _ => (CODE_ALPHABET[k] as char).to_string(),
                };
                if k == g {
                    cv.rect(cx + 1, cy, cw - 2, ch, YELLOW);
                }
                let ready = match k {
                    GRID_OK => typed.len() >= min,
                    GRID_DEL => true,
                    _ => typed.len() < max,
                };
                cv.text(
                    core,
                    cx + (cw - text_width(core, &label)) / 2,
                    cy + 1,
                    &label,
                    if ready { INK } else { SHADE },
                    SHADE,
                );
            }
            bar(
                &mut cv,
                core,
                if level == 3 {
                    "A: Type  B: Rub out  START: OK"
                } else {
                    "A: Type  B: Rub out  START: OK (none)"
                },
            );
        }
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_fits() {
        assert!(STATE_END <= STATE + STATE_LEN);
        assert!(TYPED + TYPED_MAX <= TYPED_LEN);
        assert!(MESSAGE + MESSAGE_LEN <= TYPED);
    }

    #[test]
    fn codes_use_the_alphabet() {
        for seed in [1u64, 2, 99, 0xDEAD_BEEF] {
            let c = mailbox::new_code(seed);
            assert_eq!(c.len(), CODE_CHARS);
            assert!(c.bytes().all(|b| CODE_ALPHABET.contains(&b)), "{c}");
        }
        assert_ne!(mailbox::new_code(1), mailbox::new_code(2));
        // Every code letter is one the title font draws.
        assert!(CODE_ALPHABET
            .iter()
            .all(|&c| crate::online_art::TITLE_ORDER.contains(c as char)));
    }

    #[test]
    fn requests_are_read_once() {
        let mut ram = vec![0u8; STATE_LEN as usize];
        ram[0x0C] = 2;
        ram[0x0D] = 1;
        ram[4..10].copy_from_slice(b"ACDEGH");
        ram[0x59] = 2;
        ram[0x5A..0x5C].copy_from_slice(b"KM");
        let mut read = |a: u32, b: &mut [u8]| {
            let o = (a - STATE) as usize;
            b.copy_from_slice(&ram[o..o + b.len()]);
        };
        assert_eq!(
            mailbox::read_request(&mut read, 0),
            Some((
                1,
                mailbox::Request::Join {
                    code: "ACDEGH".into(),
                    password: "KM".into()
                }
            ))
        );
        assert_eq!(mailbox::read_request(&mut read, 1), None);
    }
}
