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
//!   armies' CO and colour (UP/DOWN, SELECT, L, R, START reach the pad from the seat of the army under the cursor,
//!   and all but A and B while a tag partner is picked; LEFT and RIGHT from both; A and B from the host's); every army is a human's (seat by army, as in any match:
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
pub const MESSAGE: u32 = STATE + 0xD0;
pub const MESSAGE_LEN: u32 = 0x30;
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
/// The level of RESUME's page (the others' numbers are taken by the other lobby pages).
pub const SAVED_LEVEL: u8 = 8;
/// RESUME's page: the cursor, and which saved match a request is about (the game's).
const RESUME_CUR: u32 = STATE + 0x6A;
const RESUME_ARG: u32 = STATE + 0x6B;
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
/// SELECT MAP's skip over maps for another number of players: the direction, the steps taken, a frame count.
const SKIP_DIR: u32 = STATE + 0x60;
const SKIP_STEPS: u32 = STATE + 0x61;
const SKIP_T: u32 = STATE + 0x62;
const SKIP_DONE: u32 = STATE + 0x63;
const SKIP_LAST: u32 = STATE + 0x66;
const SKIP_SAME: u32 = STATE + 0x67;
const SKIP_TAB: u32 = STATE + 0x68;
const PLAYERS_N_FOR_PROBE: u32 = crate::online_teams::SEL + 2;
/// 1 for the whole of a room's battle (from its map loading until it is left for good), and the frames out of it.
const BATTLE: u32 = STATE + 0x64;
const OUT_T: u32 = STATE + 0x65;
const STATE_END: u32 = PLAYERS + PLAYER_SIZE * MAX_PLAYERS as u32;
pub const PASSWORD_CHARS: usize = 4;

// --- The saved matches (ONLINE > LOBBY > RESUME; tangoAW2's 0x0203D100..0x0203D43F) -------------------------

/// The app's list of suspended matches, and a longer message than [`MESSAGE`] holds: how many (byte 0), the note
/// shown on the LOBBY menu when the game comes back from a match (zero-terminated, from +0x10), then the rows
/// ([`SAVED_AT`], [`SAVED_SIZE`] each: who played, the map, the day and date).
pub const SAVED: u32 = 0x0203_D100;
pub const SAVED_LEN: u32 = 0x340;
const SAVED_NOTE: u32 = SAVED + 0x10;
pub const SAVED_NOTE_LEN: usize = 0x70;
const SAVED_AT: u32 = SAVED + 0x80;
pub const SAVED_SIZE: u32 = 0x70;
pub const SAVED_MAX: usize = 6;
const SAVED_PLAYERS: usize = 0x40;
const SAVED_MAP: usize = 0x1C;
const SAVED_TAIL: usize = 0x14;
/// Players a match has (step 1: two; the room's page has a slot for each of [`MAX_PLAYERS`]).
pub const MATCH_PLAYERS: u8 = 2;

/// A match subtype bit: the match was made in the in-game lobby (boot to Versus, host's screens).
pub const ONLINE_MATCH: u8 = 0x01;
/// A match subtype bit: the room was made by UNRANKED's pairing (crate::unranked).
pub const UNRANKED_MATCH: u8 = 0x02;
/// Bit 2 of an UNRANKED match's subtype: the guest's map proposal is played (the room's host draws it from the match
/// seed). The same as `tango_net_protocol::control::UNRANKED_PICK_GUEST` (checked by the app).
pub const UNRANKED_PICK_GUEST: u8 = 0x04;
/// The room code's characters: every letter and digit. (The game's title font has only some letters, so the code is
/// drawn from the text font, doubled and outlined, letters and digits alike.)
pub const CODE_ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
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
        /// UNRANKED: look for an opponent.
        Unranked,
        /// Make a room to resume the saved match at this place in the list ([`write_saved`]).
        Resume { index: usize },
        /// Delete the saved match at this place in the list.
        DeleteSaved { index: usize },
    }

    /// One row of the list of saved matches.
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub struct SavedRow {
        pub players: String,
        pub map: String,
        pub tail: String,
    }

    /// The request numbered `serial`, if it is new (`seen` is the last serial the app has handled).
    pub fn read_request(read: &mut dyn FnMut(u32, &mut [u8]), seen: u8) -> Option<(u8, Request)> {
        let mut b = [0u8; 0x70];
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
            7 => Request::Unranked,
            8 => Request::Resume { index: b[0x6B] as usize },
            9 => Request::DeleteSaved { index: b[0x6B] as usize },
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

    /// The list of saved matches the RESUME page shows.
    pub fn write_saved(write: &mut dyn FnMut(u32, &[u8]), rows: &[SavedRow]) {
        let rows = &rows[..rows.len().min(SAVED_MAX)];
        let put = |b: &mut [u8], s: &str| {
            let n = b.len() - 1;
            for (k, c) in s.chars().filter(|c| c.is_ascii() && !c.is_ascii_control()).take(n).enumerate() {
                b[k] = c as u8;
            }
        };
        let mut all = vec![0u8; SAVED_MAX * SAVED_SIZE as usize];
        for (k, r) in rows.iter().enumerate() {
            let e = &mut all[k * SAVED_SIZE as usize..(k + 1) * SAVED_SIZE as usize];
            put(&mut e[..SAVED_PLAYERS], &r.players);
            put(&mut e[SAVED_PLAYERS..SAVED_PLAYERS + SAVED_MAP], &r.map);
            put(&mut e[SAVED_PLAYERS + SAVED_MAP..SAVED_PLAYERS + SAVED_MAP + SAVED_TAIL], &r.tail);
        }
        write(SAVED_AT, &all);
        write(SAVED, &[rows.len() as u8]);
    }

    /// The saved matches the game shows now (their count), for the app to know when to write them again.
    pub fn saved_count(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
        let mut b = [0u8];
        read(SAVED, &mut b);
        b[0]
    }

    /// The note shown on the LOBBY menu (how the last match ended), longer than a status message.
    pub fn write_note(write: &mut dyn FnMut(u32, &[u8]), text: &str) {
        let mut b = vec![0u8; SAVED_NOTE_LEN];
        for (k, c) in text
            .chars()
            .filter(|c| c.is_ascii() && !c.is_ascii_control())
            .take(SAVED_NOTE_LEN - 1)
            .enumerate()
        {
            b[k] = c as u8;
        }
        write(SAVED_NOTE, &b);
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

    /// The connection's status byte ([`Status`]).
    pub fn status(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
        let mut b = [0u8];
        read(STATUS, &mut b);
        b[0]
    }

    /// The players on the room's page: (ready, flags).
    pub fn players(read: &mut dyn FnMut(u32, &mut [u8])) -> Vec<(bool, u8)> {
        (0..MAX_PLAYERS)
            .filter_map(|k| {
                let mut b = [0u8; 2];
                read(PLAYERS + PLAYER_SIZE * k as u32, &mut b);
                (b[1] & PRESENT != 0).then_some((b[0] == 1, b[1]))
            })
            .collect()
    }

    /// A test aid's question of the console (`TANGOAW2_PAD_SCRIPT`'s `until`): see the app's `debug_aids`.
    pub fn condition(read: &mut dyn FnMut(u32, &mut [u8]), cond: &str) -> bool {
        if let Some(c) = cond.strip_prefix('!') {
            return !condition(read, c);
        }
        let bits = probe::bits();
        let flag = |f: u64| bits & f != 0;
        let (name, value) = cond.split_once('=').map_or((cond, None), |(n, v)| (n, v.parse::<u32>().ok()));
        match (name, value) {
            ("onmenu", None) => flag(probe::ONLINE_MENU),
            ("selectmode", None) => flag(probe::SELECT_MODE),
            ("selectmap", None) => flag(probe::SELECTING),
            ("teams", None) => flag(probe::TEAMS),
            ("battle", None) => flag(probe::BATTLE),
            ("versus", None) => flag(probe::VERSUS),
            ("nav", None) => flag(probe::NAV),
            ("turnended", None) => flag(probe::TURN_ENDED),
            ("cursor", Some(v)) => (bits >> 8) & 0xFF == v as u64,
            ("level", Some(v)) => level(read) as u32 == v,
            ("army", Some(v)) => (bits >> 24) & 0xFF == v as u64,
            ("maparmies", Some(v)) => (bits >> 32) & 0xFF == v as u64,
            ("status", Some(v)) => status(read) as u32 == v,
            ("players", Some(v)) => players(read).len() as u32 == v,
            ("ready", Some(v)) => players(read).iter().filter(|p| p.0).count() as u32 == v,
            _ => false,
        }
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

/// What the console shows right now, for the test aids of the app (a pad script that waits for a screen): kept in a
/// static on every tick, outside the simulation (nothing reads it back into the game).
pub mod probe {
    use super::*;
    use std::sync::atomic::AtomicU64;

    pub const SELECT_MODE: u64 = 1;
    pub const ONLINE_MENU: u64 = 2;
    pub const SELECTING: u64 = 4;
    pub const TEAMS: u64 = 8;
    pub const BATTLE: u64 = 16;
    pub const VERSUS: u64 = 32;
    pub const NAV: u64 = 64;
    pub const TURN_ENDED: u64 = 128;

    static BITS: AtomicU64 = AtomicU64::new(0);
    pub static LIST_DEBUG: AtomicU64 = AtomicU64::new(0);
    pub static MAP_DEBUG: AtomicU64 = AtomicU64::new(0);

    /// Every tick (any console): note the screen.
    pub fn store(core: &Core) {
        let mut b = 0u64;
        let mut flag = |on: bool, bit: u64| {
            if on {
                b |= bit;
            }
        };
        flag(crate::campaign_menu::on_select_mode(core), SELECT_MODE);
        flag(crate::online_menu::active(core), ONLINE_MENU);
        flag(crate::survival_ui::selecting(core), SELECTING);
        flag(crate::pvp::on_teams_screen(core), TEAMS);
        flag(crate::pvp::in_battle(core), BATTLE);
        flag(crate::pvp::in_versus(core), VERSUS);
        flag(navigating(core), NAV);
        flag(crate::pvp::turn_ended(core), TURN_ENDED);
        b |= (crate::online_menu::cursor(core).unwrap_or(0xFF) as u64) << 8;
        b |= (level(core) as u64) << 16;
        b |= (crate::pvp::current_army(core) as u64) << 24;
        b |= (super::map_armies(core, crate::ds_pack::pack().is_some()).unwrap_or(0) as u64) << 32;
        b |= (core.raw_read_8(super::SKIP_DIR, -1) as u64) << 40;
        b |= (core.raw_read_8(super::SKIP_STEPS, -1) as u64) << 48;
        b |= (crate::survival_ui::idle(core) as u64) << 56;
        b |= (core.raw_read_8(super::PLAYERS_N_FOR_PROBE, -1) as u64) << 57;
        BITS.store(b, Ordering::Relaxed);
        // (test aid: where SELECT MAP's cursor is, by both ways of telling)
        let first = core.raw_read_32(0x0300_5900, -1) & 0xFF;
        let cur = core.raw_read_32(0x0300_5930, -1) & 0xFF;
        let pcur = super::list_cursor(core).unwrap_or(0xFF) & 0xFF;
        let id_a = core.raw_read_8(super::LIST_IDS + (first + cur).min(0x31), -1) as u32;
        let id_b = core.raw_read_8(super::LIST_IDS + pcur.min(0x31), -1) as u32;
        let tab = crate::five_map::table(core);
        let arm = |id: u32| core.raw_read_8(tab + 0x5C * id + 0x18, -1) as u64;
        let ml = core.raw_read_32(0x0300_0000, -1) as u64;
        MAP_DEBUG.store(
            ml | (core.raw_read_8(0x0300_14E2, -1) as u64) << 32
                | (core.raw_read_8(0x0300_14F0, -1) as u64) << 40
                | (core.raw_read_8(0x0300_33EC, -1) as u64) << 48
                | ((core.raw_read_32(0x0300_0004, -1) != 0) as u64) << 56,
            Ordering::Relaxed,
        );
        LIST_DEBUG.store(
            first as u64 | (cur as u64) << 8 | (pcur as u64) << 16 | (id_a as u64) << 24 | (id_b as u64) << 32 | arm(id_a) << 40 | arm(id_b) << 48,
            Ordering::Relaxed,
        );
    }

    /// The last tick's note: flags in the low byte, then the ONLINE cursor (0xFF none), the lobby level and the army
    /// whose turn it is.
    pub fn bits() -> u64 {
        BITS.load(Ordering::Relaxed)
    }
}

static BOOT_TO_LOBBY: AtomicBool = AtomicBool::new(false);

// --- Keys -------------------------------------------------------------------------------------------

pub(crate) const KEY_A: u32 = 1 << 0;
pub(crate) const KEY_B: u32 = 1 << 1;
pub(crate) const KEY_SELECT: u32 = 1 << 2;
pub(crate) const KEY_START: u32 = 1 << 3;
pub(crate) const KEY_RIGHT: u32 = 1 << 4;
pub(crate) const KEY_LEFT: u32 = 1 << 5;
pub(crate) const KEY_UP: u32 = 1 << 6;
pub(crate) const KEY_DOWN: u32 = 1 << 7;
pub(crate) const KEY_R: u32 = 1 << 8;
pub(crate) const KEY_L: u32 = 1 << 9;
const ALL_KEYS: u32 = 0x3FF;

// --- The lobby (offline) ---------------------------------------------------------------------------

fn request(core: &mut Core, kind: u8) {
    core.raw_write_8(REQUEST, -1, kind);
    let s = core.raw_read_8(SERIAL, -1).wrapping_add(1);
    core.raw_write_8(SERIAL, -1, s);
    if kind <= 3 || kind == 7 {
        core.raw_write_8(STATUS, -1, 0);
        core.raw_write_range(MESSAGE, -1, &[0u8; MESSAGE_LEN as usize]);
        core.raw_write_range(PLAYERS, -1, &[0u8; (PLAYER_SIZE * MAX_PLAYERS as u32) as usize]);
    }
}

fn set_level(core: &mut Core, l: u8) {
    core.raw_write_8(LEVEL, -1, l);
}

/// The grid: the alphabet, then rub out and OK. Six columns.
const GRID_COLS: usize = 9;
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
        if matches!(level(core), 2 | 4 | 6) {
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
                if cursor == 0 {
                    // UNRANKED: look for an opponent.
                    request(core, 7);
                    set_level(core, 6);
                } else if cursor == 1 {
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
                    _ => {
                        core.raw_write_8(RESUME_CUR, -1, 0);
                        set_level(core, SAVED_LEVEL);
                    }
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
        SAVED_LEVEL => {
            let n = (core.raw_read_8(SAVED, -1) as usize).min(SAVED_MAX);
            let mut cur = core.raw_read_8(RESUME_CUR, -1) as usize;
            if n > 0 {
                cur = cur.min(n - 1);
                if pressed & KEY_UP != 0 {
                    cur = (cur + n - 1) % n;
                }
                if pressed & KEY_DOWN != 0 {
                    cur = (cur + 1) % n;
                }
                core.raw_write_8(RESUME_CUR, -1, cur as u8);
            }
            if pressed & KEY_B != 0 {
                set_level(core, 1);
            } else if n > 0 && pressed & KEY_A != 0 {
                // A room for the match: its page is the one CREATE shows.
                core.raw_write_8(RESUME_ARG, -1, cur as u8);
                core.raw_write_range(ROOM, -1, &[0u8; CODE_CHARS]);
                core.raw_write_range(PASSWORD, -1, &[0u8; PASSWORD_CHARS]);
                core.raw_write_8(PASSWORD_LEN, -1, 0);
                request(core, 8);
                set_level(core, 2);
            } else if n > 0 && pressed & KEY_START != 0 {
                core.raw_write_8(RESUME_ARG, -1, cur as u8);
                request(core, 9);
                core.raw_write_8(RESUME_CUR, -1, cur.saturating_sub(1) as u8);
            }
            keys & !ALL_KEYS
        }
        6 => {
            // (searching for an opponent: B stops)
            if pressed & KEY_B != 0 {
                request(core, 3);
                set_level(core, 0);
            }
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
    // The characters fill whole rows; Del and OK have a row of their own.
    let chars_rows = CODE_ALPHABET.len() / GRID_COLS;
    if pressed & (KEY_RIGHT | KEY_LEFT | KEY_UP | KEY_DOWN) != 0 {
        if g >= GRID_DEL {
            if pressed & (KEY_RIGHT | KEY_LEFT) != 0 {
                g = if g == GRID_DEL { GRID_OK } else { GRID_DEL };
            } else if pressed & KEY_UP != 0 {
                g = (chars_rows - 1) * GRID_COLS + if g == GRID_DEL { 0 } else { GRID_COLS / 2 + 1 };
            } else {
                g = if g == GRID_DEL { 0 } else { GRID_COLS / 2 + 1 };
            }
        } else {
            let (mut r, mut c) = (g / GRID_COLS, g % GRID_COLS);
            let action = |c: usize| if c <= GRID_COLS / 2 { GRID_DEL } else { GRID_OK };
            if pressed & KEY_RIGHT != 0 {
                c = (c + 1) % GRID_COLS;
            }
            if pressed & KEY_LEFT != 0 {
                c = (c + GRID_COLS - 1) % GRID_COLS;
            }
            g = r * GRID_COLS + c;
            if pressed & KEY_DOWN != 0 {
                if r + 1 == chars_rows {
                    g = action(c);
                } else {
                    r += 1;
                    g = r * GRID_COLS + c;
                }
            }
            if pressed & KEY_UP != 0 {
                if r == 0 {
                    g = action(c);
                } else {
                    r -= 1;
                    g = r * GRID_COLS + c;
                }
            }
        }
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
                } else if t % 24 >= 16 && room_known(core) {
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

/// The room's size is known (the session's first tick sets it, [`crate::online_teams::players`]).
fn room_known(core: &Core) -> bool {
    core.raw_read_8(PLAYERS_N_FOR_PROBE, -1) != 0
}

/// The walk to SELECT MAP stands at Versus' box on New until the session says how many players the room has (the
/// map list is made for them, crate::online_maps): the boot ends here and the session's first ticks go on.
fn waiting_for_room(core: &Core) -> bool {
    !room_known(core)
        && core.raw_read_8(NAV_GOAL, -1) == GOAL_VERSUS
        && core.raw_read_8(NAV_STEP, -1) == 3
        && crate::campaign_menu::box_cursor(core) == Some(BOX_NEW)
}

/// Whether the console should run another tick before its session takes over: the walk of an online match
/// (netplay: to SELECT MAP) or of a console asked to boot to the lobby.
pub fn boot_more(core: &Core, mode: Option<(u8, u8)>) -> bool {
    match mode {
        Some((_, sub)) if sub & ONLINE_MATCH != 0 => core.raw_read_8(MATCH, -1) == 0 || (navigating(core) && !waiting_for_room(core)),
        None => BOOT_TO_LOBBY.load(Ordering::Relaxed) || navigating(core),
        _ => false,
    }
}

/// Every frame on any console, first: an online match's walk, and its end. Returns the keys the game gets.
pub fn before(core: &mut Core, mode: Option<(u8, u8)>, keys: u32) -> u32 {
    match mode {
        Some((_, sub)) if sub & ONLINE_MATCH != 0 => {
            let pack = crate::ds_pack::features(mode);
            if core.raw_read_8(MATCH, -1) == 0 {
                core.raw_write_8(MATCH, -1, 1);
                core.raw_write_8(OVER, -1, 0);
                crate::unranked::init(core, sub);
                start_nav(core, GOAL_VERSUS);
            }
            if let Some(k) = nav(core) {
                return k;
            }
            if crate::campaign_menu::on_select_mode(core) || crate::unranked::finished(core) {
                core.raw_write_8(OVER, -1, 1);
            }
            let unranked = crate::unranked::on(core);
            let n = core.raw_read_8(NOTICE, -1);
            if n > 0 {
                core.raw_write_8(NOTICE, -1, n - 1);
            }
            // SELECT MAP: only a map for as many armies as there are players. (The previous keys kept are those the
            // game got, so an A held on such a map stays new, and refused, every frame.)
            let prev = core.raw_read_16(MATCH_PREV, -1) as u32;
            let mut keys = keys;
            // The list only lands on maps for as many armies as there are players: a move onto another map goes on
            // in the same direction (a press every few frames) until one fits.
            // (a room's SELECT MAP lists only maps for its count, crate::online_maps: none to skip or refuse)
            let paged = crate::online_maps::owns(core);
            if crate::survival_ui::idle(core) && !paged && !unranked {
                let want = crate::online_teams::players(core) as u8;
                let wrong = map_armies(core, pack).is_some_and(|n| n != want);
                let pressed = keys & !prev;
                let (mut dir, mut steps) = (core.raw_read_8(SKIP_DIR, -1) as u32, core.raw_read_8(SKIP_STEPS, -1));
                if pressed & (KEY_UP | KEY_DOWN) != 0 {
                    dir = pressed & (KEY_UP | KEY_DOWN);
                    steps = 0;
                } else if pressed & (KEY_LEFT | KEY_RIGHT) != 0 {
                    dir = KEY_DOWN;
                    steps = 0;
                }
                // (on first coming to the list: look for a fitting map from the top)
                if wrong && dir == 0 && core.raw_read_8(SKIP_DONE, -1) == 0 {
                    dir = KEY_DOWN;
                    steps = 0;
                }
                core.raw_write_8(SKIP_DONE, -1, 1);
                if wrong && dir != 0 && steps < 250 {
                    let t = core.raw_read_8(SKIP_T, -1).wrapping_add(1);
                    core.raw_write_8(SKIP_T, -1, t);
                    // (a press of 4 frames in 10)
                    if t % 10 < 4 {
                        keys |= dir;
                        if t % 10 == 0 {
                            steps += 1;
                            // The end of the list with no fitting map: on to the next tab, from its top.
                            let at = list_cursor(core).unwrap_or(0xFF) as u8;
                            let last = core.raw_read_8(SKIP_LAST, -1);
                            let same = core.raw_read_8(SKIP_SAME, -1);
                            let same = if at == last { same + 1 } else { 0 };
                            core.raw_write_8(SKIP_LAST, -1, at);
                            if same >= 2 && dir == KEY_DOWN {
                                core.raw_write_8(SKIP_SAME, -1, 0);
                                core.raw_write_8(SKIP_TAB, -1, 1);
                            } else {
                                core.raw_write_8(SKIP_SAME, -1, same);
                            }
                        }
                    } else {
                        keys &= !(KEY_UP | KEY_DOWN);
                    }
                    if core.raw_read_8(SKIP_TAB, -1) == 1 {
                        // (one RIGHT in place of the DOWN, then DOWN again)
                        keys = (keys & !KEY_DOWN) | KEY_RIGHT;
                        if t % 10 == 5 {
                            core.raw_write_8(SKIP_TAB, -1, 0);
                            core.raw_write_8(SKIP_SAME, -1, 0);
                        }
                    }
                } else {
                    dir = 0;
                    steps = 0;
                }
                core.raw_write_8(SKIP_DIR, -1, dir as u8);
                core.raw_write_8(SKIP_STEPS, -1, steps);
            } else {
                core.raw_write_8(SKIP_DONE, -1, 0);
            }
            if unranked {
                // (UNRANKED: the chosen map is walked to and chosen, the standard rules are set)
                keys = crate::unranked::drive(core, keys);
                keys = crate::unranked::rules(core, keys);
            }
            if keys & !prev & KEY_A != 0
                && !paged
                && crate::survival_ui::idle(core)
                && map_armies(core, pack).is_some_and(|n| n as usize != crate::online_teams::players(core))
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

pub(crate) const LIST_IDS: u32 = 0x0202_7F78;

/// SELECT MAP's list proc (the game's own: its cursor row is at +0x58) and where procs live.
const LIST_PROC: u32 = 0x0861_6CF4;
const PROCS: (u32, u32) = (0x0200_D610, 0x0200_E418);

/// The row the cursor is on in SELECT MAP's list (an index into [`LIST_IDS`]).
pub(crate) fn list_cursor(core: &Core) -> Option<u32> {
    let p = (PROCS.0..PROCS.1)
        .step_by(0x6C)
        .find(|&p| core.raw_read_32(p, -1) == LIST_PROC)?;
    Some(core.raw_read_16(p + 0x58, -1) as u32)
}

/// How many armies the map under SELECT MAP's cursor has.
fn map_armies(core: &Core, pack: bool) -> Option<u8> {
    let _ = pack;
    let i = list_cursor(core)?;
    if i > 0x31 {
        return None;
    }
    let id = core.raw_read_8(LIST_IDS + i, -1) as u32;
    let n = core.raw_read_8(crate::five_map::table(core) + 0x5C * id + 0x18, -1);
    (1..=5).contains(&n).then_some(n)
}

/// The online match's notes over its console (presentation only): a map for another number of players.
pub fn apply_match(core: &Core, rgba: &mut [u8]) {
    crate::online_teams::draw(core, rgba);
    crate::unranked::draw(core, rgba);
    if rgba.len() != W * H * 4 || core.raw_read_8(MATCH, -1) != 1 || core.raw_read_8(NOTICE, -1) == 0 {
        return;
    }
    if crate::survival_ui::selecting(core) {
        let mut cv = Rgba(rgba);
        bar(&mut cv, core, &format!("Pick a map for {} players.", crate::online_teams::players(core)));
    }
}

/// A room's match runs on this console.
pub fn in_room_match(core: &Core) -> bool {
    core.raw_read_8(MATCH, -1) == 1
}

/// Every tick, before the keys are merged: what each seat pressed (see [`crate::online_teams`]), and whether a battle
/// is on ([`BATTLE`]).
pub fn seat_keys(core: &mut Core, _mode: Option<(u8, u8)>, inputs: &[u32]) {
    crate::online_teams::tick(core, inputs);
    if core.raw_read_8(MATCH, -1) != 1 {
        return;
    }
    crate::unranked::tick(core, inputs);
    let battle = core.raw_read_8(BATTLE, -1) == 1;
    if crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        if !battle {
            core.raw_write_8(BATTLE, -1, 1);
        }
        core.raw_write_8(OUT_T, -1, 0);
    } else if battle {
        // Out of the battle for good (results, the save prompt, SELECT MAP again), not for a moment between its screens.
        let t = core.raw_read_8(OUT_T, -1).saturating_add(1);
        core.raw_write_8(OUT_T, -1, t);
        let menus = crate::survival_ui::selecting(core) || crate::pvp::on_teams_screen(core) || crate::campaign_menu::on_select_mode(core);
        if t > 150 || menus {
            core.raw_write_8(BATTLE, -1, 0);
            core.raw_write_8(OUT_T, -1, 0);
        }
    }
}

/// Who is who in the room, for the picture (presentation only, set by the app before the match starts).
struct RoomInfo {
    names: Vec<String>,
    local_seat: usize,
}

static ROOM_INFO: std::sync::Mutex<RoomInfo> = std::sync::Mutex::new(RoomInfo {
    names: Vec::new(),
    local_seat: 0,
});

/// The room's players' gamertags in seat order, and which seat this peer is.
pub fn set_room(names: Vec<String>, local_seat: usize) {
    *ROOM_INFO.lock().unwrap() = RoomInfo { names, local_seat };
}

pub fn room_name(seat: usize) -> String {
    ROOM_INFO.lock().unwrap().names.get(seat).cloned().unwrap_or_else(|| format!("Player {}", seat + 1))
}

pub fn room_local_seat() -> usize {
    ROOM_INFO.lock().unwrap().local_seat
}

/// How many players the room has, for the picture (2 when nobody said).
pub fn room_players() -> usize {
    ROOM_INFO.lock().unwrap().names.len().clamp(2, 5)
}

/// The match is over: its players left SELECT MAP for Select Mode.
pub fn match_over(core: &Core) -> bool {
    core.raw_read_8(MATCH, -1) == 1 && core.raw_read_8(OVER, -1) == 1
}

/// Who drives the pad on an online match's console, outside a battle's turns (`None`: the usual rules).
pub fn merge(core: &Core, inputs: &[u32]) -> Option<u32> {
    if core.raw_read_8(MATCH, -1) != 1 {
        return None;
    }
    if navigating(core) {
        return Some(0);
    }
    if let Some(keys) = crate::unranked::merge(core, inputs) {
        return Some(keys);
    }
    // The whole battle phase (every turn, its menus, banners, hand-offs, animations, the moments between): only the
    // army whose turn it is has the pad (the incoming army's player on the "Next turn" screen), and nobody else's
    // keys reach the game at any moment: not the host's, not ORed in. If that army cannot be told, nobody has it.
    if core.raw_read_8(BATTLE, -1) == 1 {
        let n = inputs.len().max(1);
        let current = crate::pvp::current_army(core);
        if !(1..=5).contains(&current) {
            return Some(0);
        }
        let army = if crate::pvp::turn_ended(core) { current % n as u8 + 1 } else { current };
        return Some(inputs[crate::pvp::seat_of_n(army, n)]);
    }
    if !crate::pvp::in_versus(core) {
        return None;
    }
    // Versus' Teams screen is not played: every player has a selector of their own (crate::online_teams).
    if crate::pvp::on_teams_screen(core) {
        return Some(crate::online_teams::merge(core).unwrap_or(0));
    }
    Some(inputs[0])
}

// --- Drawing (presentation only) ------------------------------------------------------------------

pub(crate) const W: usize = 240;
pub(crate) const H: usize = 160;
const FONT_GLYPHS: u32 = 0x084C_32E4;
const FONT_WIDTHS: u32 = 0x084C_36E4;

pub(crate) type Rgb = (u8, u8, u8);
pub(crate) const WHITE: Rgb = (255, 255, 255);
pub(crate) const INK: Rgb = (16, 16, 24);
pub(crate) const SHADE: Rgb = (176, 184, 200);
pub(crate) const RED: Rgb = (240, 48, 56);
pub(crate) const BLUE: Rgb = (48, 64, 232);
pub(crate) const LIGHT_GRAY: Rgb = (232, 232, 236);
pub(crate) const GRAY_INK: Rgb = (104, 112, 128);
pub(crate) const CREAM: Rgb = (255, 246, 214);
pub(crate) const YELLOW: Rgb = (255, 224, 64);
pub(crate) const BAR: Rgb = (24, 24, 32);

pub(crate) struct Rgba<'a>(pub(crate) &'a mut [u8]);

impl Rgba<'_> {
    pub(crate) fn put(&mut self, x: i32, y: i32, c: Rgb) {
        if (0..W as i32).contains(&x) && (0..H as i32).contains(&y) {
            let o = 4 * (W * y as usize + x as usize);
            self.0[o..o + 3].copy_from_slice(&[c.0, c.1, c.2]);
        }
    }
    pub(crate) fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: Rgb) {
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
    pub(crate) fn text(&mut self, core: &Core, x: i32, y: i32, s: &str, ink: Rgb, shade: Rgb) -> i32 {
        let mut x = x;
        for c in s.bytes() {
            if c.is_ascii_digit() {
                let (w, rows) = digit_glyph(core, c);
                for (r, bits) in rows.iter().enumerate() {
                    for cx in 0..w {
                        if bits >> cx & 1 != 0 {
                            self.put(x + cx as i32, y + r as i32, ink);
                        }
                    }
                }
                x += w as i32 + 1;
                continue;
            }
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

pub(crate) fn text_width(core: &Core, s: &str) -> i32 {
    s.bytes()
        .map(|c| if c.is_ascii_digit() { DIGIT_W as i32 + 1 } else { core.raw_read_8(FONT_WIDTHS + c as u32, -1) as i32 + 1 })
        .sum::<i32>()
        - 1
}

pub(crate) fn bgr(c: u16) -> Rgb {
    let f = |v: u16| ((v & 31) * 255 / 31) as u8;
    (f(c), f(c >> 5), f(c >> 10))
}

/// The digits, thin as the text font's letters (its own digits are bold): 6 wide, 9 tall, on the letters' rows.
const DIGIT_W: usize = 6;
const DIGITS: [[&str; 9]; 10] = [
    [".###..", "#...#.", "#..##.", "#.#.#.", "##..#.", "#...#.", "#...#.", "#...#.", ".###.."],
    ["..#...", ".##...", "#.#...", "..#...", "..#...", "..#...", "..#...", "..#...", "#####."],
    [".###..", "#...#.", "....#.", "....#.", "...#..", "..#...", ".#....", "#.....", "#####."],
    [".###..", "#...#.", "....#.", "....#.", "..##..", "....#.", "....#.", "#...#.", ".###.."],
    ["...#..", "..##..", ".#.#..", "#..#..", "#..#..", "#####.", "...#..", "...#..", "...#.."],
    ["#####.", "#.....", "#.....", "####..", "....#.", "....#.", "....#.", "#...#.", ".###.."],
    [".###..", "#.....", "#.....", "####..", "#...#.", "#...#.", "#...#.", "#...#.", ".###.."],
    ["#####.", "....#.", "....#.", "...#..", "...#..", "..#...", "..#...", ".#....", ".#...."],
    [".###..", "#...#.", "#...#.", "#...#.", ".###..", "#...#.", "#...#.", "#...#.", ".###.."],
    [".###..", "#...#.", "#...#.", "#...#.", ".####.", "....#.", "....#.", "....#.", ".###.."],
];

/// A digit's rows (bit x set: a pixel at x), in the 11 rows the text font's glyphs use, the digit's top on the
/// capitals' top row.
fn digit_glyph(core: &Core, c: u8) -> (usize, [u16; 11]) {
    // (the top of an H)
    let at = core.raw_read_32(FONT_GLYPHS + 4 * b'H' as u32, -1);
    let w = core.raw_read_8(FONT_WIDTHS + b'H' as u32, -1) as usize;
    let mut top = 1;
    if (0x0800_0000..0x0A00_0000).contains(&at) {
        let stride = w.div_ceil(2);
        top = (0..11)
            .find(|&r| {
                (0..w).any(|cx| (core.raw_read_8(at + (stride * (3 + r) + cx / 2) as u32, -1) >> (4 * (cx & 1))) & 15 != 0)
            })
            .unwrap_or(1);
    }
    let mut rows = [0u16; 11];
    for (i, line) in DIGITS[(c - b'0') as usize].iter().enumerate() {
        if top + i < 11 {
            rows[top + i] = line
                .bytes()
                .enumerate()
                .filter(|&(_, p)| p == b'#')
                .fold(0, |m, (x, _)| m | 1 << x);
        }
    }
    (DIGIT_W, rows)
}

/// A character's rows as [`digit_glyph`]'s (any set pixel of the text font's letter).
fn glyph_rows(core: &Core, c: u8) -> (usize, [u16; 11]) {
    if c.is_ascii_digit() {
        return digit_glyph(core, c);
    }
    let w = core.raw_read_8(FONT_WIDTHS + c as u32, -1) as usize;
    let at = core.raw_read_32(FONT_GLYPHS + 4 * c as u32, -1);
    let mut rows = [0u16; 11];
    if (0x0800_0000..0x0A00_0000).contains(&at) {
        let stride = w.div_ceil(2);
        for (r, row) in rows.iter_mut().enumerate() {
            for cx in 0..w {
                if (core.raw_read_8(at + (stride * (3 + r) + cx / 2) as u32, -1) >> (4 * (cx & 1))) & 15 != 0 {
                    *row |= 1 << cx;
                }
            }
        }
    }
    (w, rows)
}

/// A word of the room code: the text font doubled and outlined in the title's white and blue, letters and digits
/// alike, its outline's top at `y`.
fn title(cv: &mut Rgba, core: &Core, font: &crate::online_art::TitleFont, x: i32, y: i32, word: &str) {
    let pal: Vec<Rgb> = (0..16)
        .map(|i| bgr(core.raw_read_16(0x0500_0200 + 15 * 32 + 2 * i, -1)))
        .collect();
    // The title letters' fill and outline: across the middle of an I.
    let (fill, edge) = {
        let i = &font.px[crate::online_art::TitleFont::index('I').unwrap_or(0)];
        let row: Vec<u8> = (0..16).map(|x| i.get(x, 16)).collect();
        let first = row.iter().position(|&v| v != 0).unwrap_or(0);
        (row[(first + 4).min(15)], row[first])
    };
    let mut cx = x;
    for c in word.bytes() {
        let (w, rows) = glyph_rows(core, c);
        // (the letters' own rows: from the first used to the last)
        let used: Vec<usize> = (0..11).filter(|&r| rows[r] != 0).collect();
        let (top, bottom) = (
            used.first().copied().unwrap_or(0) as i32,
            used.last().copied().unwrap_or(0) as i32,
        );
        let on = |gx: i32, gy: i32| -> bool {
            if gx < 0 || gy < 0 || gx >= 2 * w as i32 || gy >= 2 * (bottom - top + 1) {
                return false;
            }
            rows[(top + gy / 2) as usize] >> (gx / 2) & 1 != 0
        };
        for gy in -1..2 * (bottom - top + 1) + 1 {
            for gx in -1..2 * w as i32 + 1 {
                let v = if on(gx, gy) {
                    fill
                } else if (-1..=1).any(|dy| (-1..=1).any(|dx| on(gx + dx, gy + dy))) {
                    edge
                } else {
                    continue;
                };
                cv.put(cx + gx + 1, y + gy + 1, pal[v as usize]);
            }
        }
        cx += 2 * w as i32 + 3;
    }
}

/// How wide [`title`] draws `word`.
fn title_width(core: &Core, _font: &crate::online_art::TitleFont, word: &str) -> i32 {
    word.bytes().map(|c| 2 * glyph_rows(core, c).0 as i32 + 3).sum::<i32>() - 1
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
pub(crate) fn bar(cv: &mut Rgba, core: &Core, s: &str) {
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
        Status::Waiting if !m.is_empty() => (wrap(core, &m, PANEL.2 - 12), INK),
        Status::Waiting => (vec!["Waiting for player(s)...".into()], INK),
        Status::Connecting => (vec!["Connecting...".into()], INK),
        Status::Connected => (vec![format!("Connected: {m}"), "The battle is starting!".into()], BLUE),
        Status::Failed => (
            wrap(core, if m.is_empty() { "Could not connect." } else { &m }, PANEL.2 - 12),
            RED,
        ),
    }
}

fn note(core: &Core) -> String {
    let mut b = [0u8; SAVED_NOTE_LEN];
    core.raw_read_range(SAVED_NOTE, -1, &mut b);
    b.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect()
}

/// A row of the list of saved matches: (who played, the map, the day and date).
fn saved_row(core: &Core, k: usize) -> (String, String, String) {
    let mut b = [0u8; SAVED_SIZE as usize];
    core.raw_read_range(SAVED_AT + SAVED_SIZE * k as u32, -1, &mut b);
    let text = |a: usize, n: usize| -> String { b[a..a + n].iter().take_while(|&&c| c != 0).map(|&c| c as char).collect() };
    (text(0, SAVED_PLAYERS), text(SAVED_PLAYERS, SAVED_MAP), text(SAVED_PLAYERS + SAVED_MAP, SAVED_TAIL))
}

/// `s` cut with ".." to fit `width` pixels.
fn fit(core: &Core, s: &str, width: i32) -> String {
    if text_width(core, s) <= width {
        return s.to_string();
    }
    let mut t: String = s.to_string();
    while !t.is_empty() && text_width(core, &format!("{t}..")) > width {
        t.pop();
    }
    format!("{t}..")
}

/// RESUME: the matches cut short, one under the cursor (UP and DOWN, A resumes it, START deletes it).
fn saved_page(cv: &mut Rgba, core: &Core) {
    let (x, y, w, h) = (6, 22, W as i32 - 12, 118);
    cv.window(x, y, w, h);
    let n = (core.raw_read_8(SAVED, -1) as usize).min(SAVED_MAX);
    cv.text(core, x + 6, y + 4, "Matches cut short", GRAY_INK, SHADE);
    if n == 0 {
        let t = "No saved matches.";
        cv.text(core, x + (w - text_width(core, t)) / 2, y + 48, t, GRAY_INK, SHADE);
        let t2 = "A match is kept when a player's connection drops.";
        let lines = wrap(core, t2, w - 20);
        for (k, l) in lines.iter().enumerate() {
            cv.text(core, x + (w - text_width(core, l)) / 2, y + 64 + 12 * k as i32, l, SHADE, LIGHT_GRAY);
        }
        bar(cv, core, "B: Back");
        return;
    }
    let cur = (core.raw_read_8(RESUME_CUR, -1) as usize).min(n - 1);
    // Four rows show at a time, the cursor's among them.
    let first = cur.saturating_sub(3).min(n.saturating_sub(4));
    for (row, k) in (first..n.min(first + 4)).enumerate() {
        let (players, map, tail) = saved_row(core, k);
        let ry = y + 16 + 25 * row as i32;
        if k == cur {
            cv.rect(x + 3, ry - 1, w - 6, 24, YELLOW);
        } else {
            cv.rect(x + 4, ry + 23, w - 8, 1, LIGHT_GRAY);
        }
        cv.text(core, x + 7, ry, &fit(core, &players, w - 14), INK, SHADE);
        cv.text(core, x + 7, ry + 11, &fit(core, &format!("{map}  {tail}"), w - 14), if k == cur { INK } else { GRAY_INK }, SHADE);
    }
    if first > 0 {
        cv.text(core, x + w - 14, y + 4, "^", GRAY_INK, SHADE);
    }
    if first + 4 < n {
        cv.text(core, x + w - 14, y + h - 12, "v", GRAY_INK, SHADE);
    }
    bar(cv, core, "A: Resume  START: Delete  B: Back");
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
            let note = (Status::of(core.raw_read_8(STATUS, -1)) == Status::Back).then(|| note(core)).filter(|m| !m.is_empty());
            let help = [
                "Make a room and give its code to a friend.",
                "Type in the code of a friend's room.",
                "Pick up a match cut short by a disconnect.",
            ];
            match note {
                // How the last match ended: longer than the bar, so in a box of its own over the menu.
                Some(m) => {
                    let lines = wrap(core, &m, W as i32 - 20);
                    let h = 8 + 12 * lines.len().min(4) as i32;
                    let y = 142 - h;
                    cv.window(4, y, W as i32 - 8, h);
                    for (k, l) in lines.iter().take(4).enumerate() {
                        cv.text(core, 10, y + 5 + 12 * k as i32, l, INK, SHADE);
                    }
                    bar(&mut cv, core, "UP or DOWN: Dismiss");
                }
                None => bar(&mut cv, core, help[cursor as usize % 3]),
            }
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
                title(&mut cv, core, font, x + (w - title_width(core, font, &code)) / 2, y + 18, &code);
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
                        let t = "Open";
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
                    let b = if hosting { "B: Close" } else { "B: Back" };
                    l.push_str("  ");
                    l.push_str(b);
                    // (the bar is the screen's width: the key matters more than the status, which the page shows)
                    if text_width(core, &l) > W as i32 - 8 {
                        l = b.to_string();
                    }
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
        6 => {
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            let status = Status::of(core.raw_read_8(STATUS, -1));
            cv.text(core, x + 6, y + 5, "Unranked", GRAY_INK, SHADE);
            let (lines, ink): (Vec<String>, Rgb) = match status {
                Status::Connected => (
                    vec!["Opponent found:".into(), message(core), "The match is starting!".into()],
                    BLUE,
                ),
                Status::Failed => status_lines(core, false),
                _ => (
                    wrap(core, "Looking for an opponent...", w - 16)
                        .into_iter()
                        .chain(wrap(core, "Another player has to be looking too.", w - 16))
                        .collect(),
                    INK,
                ),
            };
            for (k, l) in lines.iter().take(6).enumerate() {
                let ink = if k > 0 && status != Status::Connected && status != Status::Failed { GRAY_INK } else { ink };
                cv.text(core, x + (w - text_width(core, l)) / 2, y + 28 + 13 * k as i32, l, ink, SHADE);
            }
            bar(
                &mut cv,
                core,
                match status {
                    Status::Connected => "Starting...",
                    Status::Failed => "B: Back",
                    _ => "B: Cancel",
                },
            );
        }
        SAVED_LEVEL => saved_page(&mut cv, core),
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
                    title(&mut cv, core, font, cx + (bw - title_width(core, font, &s)) / 2, y + 22, &s);
                }
            }
            let g = core.raw_read_8(GRID, -1) as usize;
            let (cw, ch) = (15, 12);
            let gx = x + (w - cw * GRID_COLS as i32) / 2;
            let gy = y + 49;
            let (_, _, max, min) = field(core);
            let full = typed.len() >= min;
            for k in 0..GRID_CELLS {
                // Del and OK take half the width each of the row of their own.
                let (cx, cy, cwid, label) = match k {
                    GRID_DEL => (gx, gy + 4 * ch + 2, 4 * cw, "Del".to_string()),
                    GRID_OK => (gx + 5 * cw, gy + 4 * ch + 2, 4 * cw, "OK".to_string()),
                    _ => (
                        gx + (k % GRID_COLS) as i32 * cw,
                        gy + (k / GRID_COLS) as i32 * ch,
                        cw,
                        (CODE_ALPHABET[k] as char).to_string(),
                    ),
                };
                let ready = match k {
                    GRID_OK => full,
                    GRID_DEL => true,
                    _ => typed.len() < max,
                };
                if k == g {
                    cv.rect(cx + 1, cy, cwid - 2, ch, YELLOW);
                } else if k == GRID_OK && full {
                    // (an OK that can be pressed: a blue plate)
                    cv.rect(cx + 1, cy, cwid - 2, ch, BLUE);
                }
                let ink = if k == GRID_OK && full && k != g { WHITE } else if ready { INK } else { SHADE };
                cv.text(core, cx + (cwid - text_width(core, &label)) / 2, cy + 1, &label, ink, SHADE);
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
        assert!(MESSAGE + MESSAGE_LEN <= STATE + STATE_LEN);
        assert!(MESSAGE >= PLAYERS + PLAYER_SIZE * MAX_PLAYERS as u32);
    }

    #[test]
    fn codes_use_the_alphabet() {
        for seed in [1u64, 2, 99, 0xDEAD_BEEF] {
            let c = mailbox::new_code(seed);
            assert_eq!(c.len(), CODE_CHARS);
            assert!(c.bytes().all(|b| CODE_ALPHABET.contains(&b)), "{c}");
        }
        assert_ne!(mailbox::new_code(1), mailbox::new_code(2));
        // Every character is a letter or a digit.
        assert!(CODE_ALPHABET.iter().all(|&c| c.is_ascii_alphanumeric()));
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
