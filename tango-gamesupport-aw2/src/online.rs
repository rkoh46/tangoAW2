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
/// The name being typed for a room to make ([`NAME_LEVEL`]) and its length: at most [`NAME_TYPED_CHARS`] letters, digits and spaces; none
/// is the default ("<gamertag>'s room", made by the app).
pub const NAME_BUF: u32 = STATE + 0x1C;
pub const NAME_LEN: u32 = STATE + 0x29;
pub const NAME_TYPED_CHARS: usize = 12;
/// The most characters a room's name has anywhere (the default "<gamertag>'s room" is longer than a typed one can be).
pub const ROOM_NAME_CHARS: usize = 18;
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
/// UNRANKED's rejoin box (the player's app crashed during an UNRANKED match that is still on): the app's offer in the saved
/// matches' block, 0 none, 1 offered (A: Rejoin, B: Give up), 2 rejoining (the app is on it, [`STATUS`] says how it goes).
pub const REJOIN: u32 = 0x0203_D100 + 4;
/// The level of the rejoin box.
pub const REJOIN_LEVEL: u8 = 12;
/// The level of CREATE's first page: the room's name, typed on the same grid as the code and the password.
pub const NAME_LEVEL: u8 = 13;
/// The level of RESUME's page (the others' numbers are taken by the other lobby pages).
pub const SAVED_LEVEL: u8 = 8;
/// The gamertag's typing page and the STATS page ([`crate::online_stats`]).
pub const TAG_LEVEL: u8 = 9;
/// The request that tells the app the gamertag changed.
pub const REQUEST_GAMERTAG: u8 = 10;
pub const STATS_LEVEL: u8 = 10;
/// The Connection page ([`crate::online_conn`]): R on the ONLINE screen.
pub const CONN_LEVEL: u8 = 11;
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
/// ([`PRESENT`], [`HOST`], [`YOU`]), the name (zero-terminated, at most [`NAME_CHARS`] letters), the round trip to
/// the player in ms ([`LINK_RTT`], 0 not known) and how the link flows ([`LINK_KIND`]: [`LINK_DIRECT`], [`LINK_RELAY`]).
pub const PLAYERS: u32 = STATE + 0x80;
pub const PLAYER_SIZE: u32 = 0x10;
pub const NAME_CHARS: usize = PLAYER_SIZE as usize - 4;
const LINK_RTT: usize = PLAYER_SIZE as usize - 2;
const LINK_KIND: usize = PLAYER_SIZE as usize - 1;
/// A link's kind: not known (0), peer to peer, or through the TURN relay.
pub const LINK_DIRECT: u8 = 1;
pub const LINK_RELAY: u8 = 2;
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
/// The army whose End was chosen while the turn-ended screen is up (0: none), kept in the console so every peer and
/// every re-simulation agrees: the game moves its current army on before the screen's state is reset.
const ENDER: u32 = STATE + 0x6C;
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

/// A name as it is kept anywhere (a gamertag, a room's name): printable ASCII, runs of spaces made one, none at either end, at most
/// `max` characters (and none at the end after the cut). An all-space name is nothing.
pub fn clean_name(name: &str, max: usize) -> String {
    let mut out = String::new();
    for c in name.chars().filter(|c| c.is_ascii() && !c.is_ascii_control()) {
        if c == ' ' && (out.is_empty() || out.ends_with(' ')) {
            continue;
        }
        out.push(c);
    }
    let cut: String = out.chars().take(max).collect();
    cut.trim_end().to_string()
}

// --- The mailbox (the host app's side) ---------------------------------------------------------------

/// The host app's side of the mailbox, over its own reads and writes of the console's memory (between frames).
pub mod mailbox {
    use super::*;

    /// What the game asks for.
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub enum Request {
        /// Make a room (the app picks its code: [`write_room`]), with this password (may be empty) and name (empty: the app's
        /// default, "<gamertag>'s room").
        Host {
            password: String,
            name: String,
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
        /// The player set a gamertag in the game.
        SetGamertag(String),
        /// UNRANKED: look for an opponent.
        Unranked,
        /// Make a room to resume the saved match at this place in the list ([`write_saved`]).
        Resume {
            index: usize,
        },
        /// Delete the saved match at this place in the list.
        DeleteSaved {
            index: usize,
        },
        /// UNRANKED: the player's match is still on (their app crashed): go back into it.
        Rejoin,
        /// UNRANKED: the player gives up the match that is still on (their army yields).
        GiveUp,
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
            1 => Request::Host {
                password,
                name: clean_name(&text(0x1C, (b[0x29] as usize).min(NAME_TYPED_CHARS)), ROOM_NAME_CHARS),
            },
            2 => Request::Join { code, password },
            4 => Request::Ready,
            5 => Request::NotReady,
            6 => Request::Start,
            REQUEST_GAMERTAG => {
                let mut tag = [0u8; crate::online_stats::TAG_CHARS];
                read(crate::online_stats::GAMERTAG, &mut tag);
                Request::SetGamertag(tag.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect())
            }
            7 => Request::Unranked,
            8 => Request::Resume {
                index: b[0x6B] as usize,
            },
            9 => Request::DeleteSaved {
                index: b[0x6B] as usize,
            },
            11 => Request::Rejoin,
            12 => Request::GiveUp,
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
                .take(NAME_CHARS)
                .enumerate()
            {
                b[2 + k] = c as u8;
            }
        }
        write(PLAYERS + PLAYER_SIZE * slot as u32, &b);
    }

    /// The connection's diagnostic for one player's slot (after [`write_player`], which clears it): the round trip
    /// in ms (0 not known) and the kind ([`LINK_DIRECT`], [`LINK_RELAY`], 0 not known).
    pub fn write_link(write: &mut dyn FnMut(u32, &[u8]), slot: usize, kind: u8, rtt_ms: u32) {
        write(
            PLAYERS + PLAYER_SIZE * slot as u32 + LINK_RTT as u32,
            &[rtt_ms.clamp(0, 255) as u8, kind],
        );
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

    /// The words for the players a saved match waits for, within what [`MESSAGE`] holds: "Waiting for A, B", and
    /// "+N" for the names that do not fit.
    pub fn waiting_for(names: &[String]) -> String {
        const MAX: usize = MESSAGE_LEN as usize - 1;
        let name = |n: &String| {
            n.chars()
                .filter(|c| c.is_ascii() && !c.is_ascii_control())
                .collect::<String>()
        };
        let full = format!("Waiting for {}", names.iter().map(name).collect::<Vec<_>>().join(", "));
        if full.len() <= MAX {
            return full;
        }
        for shown in (1..names.len()).rev() {
            let t = format!(
                "Waiting for {} +{}",
                names[..shown].iter().map(name).collect::<Vec<_>>().join(", "),
                names.len() - shown
            );
            if t.len() <= MAX {
                return t;
            }
        }
        format!("Waiting for {} players", names.len())
    }

    /// The text a message is kept as: ASCII, and when it is longer than the mailbox holds, cut at a word's end
    /// with ".." (the pages show a message whole or not at all).
    pub fn message_text(message: &str) -> String {
        const MAX: usize = MESSAGE_LEN as usize - 1;
        let s: String = message
            .chars()
            .filter(|c| c.is_ascii() && !c.is_ascii_control())
            .collect();
        if s.len() <= MAX {
            return s;
        }
        let cut = &s[..MAX - 2];
        let cut = cut.rsplit_once(' ').map_or(cut, |(a, _)| a);
        format!("{cut}..")
    }

    pub fn write_status(write: &mut dyn FnMut(u32, &[u8]), status: Status, message: &str) {
        let mut m = vec![0u8; MESSAGE_LEN as usize];
        for (k, c) in message_text(message).bytes().enumerate() {
            m[k] = c;
        }
        write(MESSAGE, &m);
        write(STATUS, &[status as u8]);
    }

    /// The list of saved matches the RESUME page shows.
    pub fn write_saved(write: &mut dyn FnMut(u32, &[u8]), rows: &[SavedRow]) {
        let rows = &rows[..rows.len().min(SAVED_MAX)];
        let put = |b: &mut [u8], s: &str| {
            let n = b.len() - 1;
            for (k, c) in s
                .chars()
                .filter(|c| c.is_ascii() && !c.is_ascii_control())
                .take(n)
                .enumerate()
            {
                b[k] = c as u8;
            }
        };
        let mut all = vec![0u8; SAVED_MAX * SAVED_SIZE as usize];
        for (k, r) in rows.iter().enumerate() {
            let e = &mut all[k * SAVED_SIZE as usize..(k + 1) * SAVED_SIZE as usize];
            put(&mut e[..SAVED_PLAYERS], &r.players);
            put(&mut e[SAVED_PLAYERS..SAVED_PLAYERS + SAVED_MAP], &r.map);
            put(
                &mut e[SAVED_PLAYERS + SAVED_MAP..SAVED_PLAYERS + SAVED_MAP + SAVED_TAIL],
                &r.tail,
            );
        }
        write(SAVED_AT, &all);
        write(SAVED, &[rows.len() as u8]);
    }

    /// The rejoin box (see [`REJOIN`]): 0 away, 1 offered, 2 rejoining; the room of the match is named for the page.
    pub fn write_rejoin(write: &mut dyn FnMut(u32, &[u8]), state: u8, room: &str) {
        crate::online_browse::mailbox::write_own_name(write, room);
        write(REJOIN, &[state]);
    }

    /// What the game shows of the rejoin box.
    pub fn rejoin(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
        let mut b = [0u8];
        read(REJOIN, &mut b);
        b[0]
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
        if !matches!(level(read), 3 | 5 | TAG_LEVEL | NAME_LEVEL) {
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
        let (name, value) = cond
            .split_once('=')
            .map_or((cond, None), |(n, v)| (n, v.parse::<u32>().ok()));
        match (name, value) {
            ("onmenu", None) => flag(probe::ONLINE_MENU),
            ("selectmode", None) => flag(probe::SELECT_MODE),
            ("selectmap", None) => flag(probe::SELECTING),
            ("teams", None) => flag(probe::TEAMS),
            ("battle", None) => flag(probe::BATTLE),
            ("versus", None) => flag(probe::VERSUS),
            ("nav", None) => flag(probe::NAV),
            ("turnended", None) => flag(probe::TURN_ENDED),
            ("myturn", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 1 != 0,
            ("banner", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 2 != 0,
            ("acting", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 4 != 0,
            ("over", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 8 != 0,
            // (the reconnect box is up: a test cue)
            ("reconnect", None) => crate::hold_box::shown(),
            ("mapup", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 16 != 0,
            ("pickturn", Some(v)) => {
                (probe::CUES.load(std::sync::atomic::Ordering::Relaxed) >> 8) & 0xF == v as u64 + 1
            }
            ("rules", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 128 != 0,
            ("chosen", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 64 != 0,
            ("mypick", None) => probe::CUES.load(std::sync::atomic::Ordering::Relaxed) & 32 != 0,
            ("cursor", Some(v)) => (bits >> 8) & 0xFF == v as u64,
            ("level", Some(v)) => level(read) as u32 == v,
            ("army", Some(v)) => (bits >> 24) & 0xFF == v as u64,
            // the map cursor's cell (the cursor starts a turn where the last one left it)
            ("cx" | "cy", Some(v)) => {
                let c = probe::CURSOR_CELL.load(std::sync::atomic::Ordering::Relaxed);
                (if name == "cy" { c >> 16 } else { c } & 0xFFFF) as u32 == v
            }
            // the cursor left of / right of (cxlt: its x is below the value) / above / below the cell
            ("cxlt" | "cxgt" | "cylt" | "cygt", Some(v)) => {
                let c = probe::CURSOR_CELL.load(std::sync::atomic::Ordering::Relaxed);
                let at = (if name.starts_with("cy") { c >> 16 } else { c } & 0xFFFF) as u32;
                if name.ends_with("lt") {
                    at < v
                } else {
                    at > v
                }
            }
            // the map waits for the cursor and nothing runs (a test script's cue to press)
            ("idle", None) => bits >> 63 & 1 != 0,
            // the map menu's selected row (0 CO, 1 Intel, 2 Options, 3 Save, 4 End; the menu keeps its row between uses)
            // the map menu's cursor is on its End item (the row End had when the menu was last shown, kept in RAM)
            ("onend", None) => {
                let m = probe::MAP_DEBUG.load(std::sync::atomic::Ordering::Relaxed);
                let end = (m >> 57) & 0xF;
                end != 0 && ((m >> 40) & 0xFF) + 1 == end
            }
            ("menu", Some(v)) => (probe::MAP_DEBUG.load(std::sync::atomic::Ordering::Relaxed) >> 40) & 0xFF == v as u64,
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
    /// The map cursor's cell (x, then y << 16), noted every tick: a test script's `cx`/`cy` in a netplay session, whose
    /// console the script cannot read.
    pub static CURSOR_CELL: AtomicU64 = AtomicU64::new(0);
    /// State-driven test cues (`TANGOAW2_PAD_SCRIPT` conditions): bit 0 `myturn` (this window's seat has the turn),
    /// bit 1 `banner` (the NEXT TURN banner is up and this seat is the incoming mover: its A dismisses it), bit 2
    /// `acting` (my turn, the plain map with no menu, page or banner on it), bit 3 `over` (the match is decided).
    pub static CUES: AtomicU64 = AtomicU64::new(0);

    /// Every tick (any console): note the screen.
    pub fn store(core: &Core) {
        {
            let n = super::room_players();
            let me = super::room_local_seat();
            let current = crate::pvp::current_army(core);
            let mut c = 0u64;
            if crate::pvp::in_battle(core) && (1..=5).contains(&current) {
                let ended = crate::pvp::turn_ended(core);
                // (who has the pad, as `merge` tells: the incoming army's seat on the Next turn screen)
                let ender = core.raw_read_8(super::ENDER, -1);
                let army = if ended {
                    super::incoming_alive(core, if (1..=5).contains(&ender) { ender } else { current }, n)
                } else {
                    current
                };
                let mine = crate::pvp::seat_of_n(army, n) == me;
                if mine && !ended {
                    c |= 1;
                }
                // (steady for a moment: the turn start cycles the army byte through the other armies)
                static BANNER: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
                if mine && ended {
                    if BANNER.fetch_add(1, Ordering::Relaxed) >= 20 {
                        c |= 2;
                    }
                } else {
                    BANNER.store(0, Ordering::Relaxed);
                }
                static STEADY: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
                if mine && !ended && crate::fog_view::plain_map(core) {
                    if STEADY.fetch_add(1, Ordering::Relaxed) >= 30 {
                        c |= 4;
                    }
                } else {
                    STEADY.store(0, Ordering::Relaxed);
                }
                if crate::result_view::decided(core) {
                    c |= 8;
                }
                // (the battle map is up, with or without a menu on it: the opening pages are over)
                if crate::fog_view::phase(core) == crate::fog_view::Phase::Map {
                    c |= 16;
                }
            }
            // (SELECT MAP: the maps are being picked, this seat has not picked, and the list is up and still)
            if crate::unranked::picking(core)
                && !crate::unranked::has_picked(core, me)
                && crate::survival_ui::idle(core)
            {
                c |= 32;
            }
            if crate::unranked::rules_up(core) {
                c |= 128;
            }
            // (how many seats have picked: bits 8..11, plus one while the maps are being picked)
            if crate::unranked::picking(core) {
                c |= (crate::unranked::picks_made(core) as u64 + 1) << 8;
            }
            // (the draw is made: the bar tells whose map is played)
            if crate::unranked::chosen(core) {
                c |= 64;
            }
            CUES.store(c, Ordering::Relaxed);
        }
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
        b |= ((crate::fog_view::phase(core) == crate::fog_view::Phase::Map) as u64) << 63;
        BITS.store(b, Ordering::Relaxed);
        CURSOR_CELL.store(
            core.raw_read_16(0x0300_33E4, -1) as u64 | (core.raw_read_16(0x0300_33E6, -1) as u64) << 16,
            Ordering::Relaxed,
        );
        // (test aid: where SELECT MAP's cursor is, by both ways of telling)
        let first = core.raw_read_32(0x0300_5900, -1) & 0xFF;
        let cur = core.raw_read_32(0x0300_5930, -1) & 0xFF;
        let pcur = super::list_cursor(core).unwrap_or(0xFF) & 0xFF;
        let id_a = core.raw_read_8(super::LIST_IDS + (first + cur).min(crate::five_map::LIST_CAP - 1), -1) as u32;
        let id_b = core.raw_read_8(super::LIST_IDS + pcur.min(crate::five_map::LIST_CAP - 1), -1) as u32;
        let tab = crate::five_map::table(core);
        let arm = |id: u32| core.raw_read_8(tab + 0x5C * id + 0x18, -1) as u64;
        let ml = core.raw_read_32(0x0300_0000, -1) as u64;
        MAP_DEBUG.store(
            ml | (core.raw_read_8(0x0300_14E2, -1) as u64) << 32
                | (core.raw_read_8(0x0300_14F0, -1) as u64) << 40
                | (core.raw_read_8(0x0300_33EC, -1) as u64) << 48
                | ((core.raw_read_32(0x0300_0004, -1) != 0) as u64) << 56
                | ((core.raw_read_8(crate::pvp::END_ROW, -1) & 0xF) as u64) << 57,
            Ordering::Relaxed,
        );
        LIST_DEBUG.store(
            first as u64
                | (cur as u64) << 8
                | (pcur as u64) << 16
                | (id_a as u64) << 24
                | (id_b as u64) << 32
                | arm(id_a) << 40
                | arm(id_b) << 48,
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

/// The grid, laid out like a keyboard: the digits, then Q to P, A to L and Z to M (each row starts further in, half a key
/// and one key), then a row of its own with rub out and OK.
const GRID_ROWS: [&[u8]; 4] = [b"1234567890", b"QWERTYUIOP", b"ASDFGHJKL", b"ZXCVBNM"];
/// The first cell of each row in the flat order, and each row's indent in half keys.
const GRID_START: [usize; 4] = [0, 10, 20, 29];
const GRID_INDENT: [usize; 4] = [0, 0, 1, 2];
const GRID_COLS: usize = 10;
const GRID_DEL: usize = CODE_ALPHABET.len();
const GRID_OK: usize = CODE_ALPHABET.len() + 1;
/// The space bar, between Del and OK on the bottom row of the pages that type a name (a gamertag, a room's name): the code and the
/// password have none.
const GRID_SPACE: usize = CODE_ALPHABET.len() + 2;
const GRID_CELLS: usize = CODE_ALPHABET.len() + 3;

/// Whether the page being typed on takes spaces: a gamertag and a room's name do, a room's code and a password do not.
fn allow_space(core: &Core) -> bool {
    matches!(level(core), TAG_LEVEL | NAME_LEVEL)
}

/// The character in cell `g` of the flat order.
fn grid_char(g: usize) -> u8 {
    let r = (0..4).rev().find(|&r| g >= GRID_START[r]).unwrap_or(0);
    GRID_ROWS[r][g - GRID_START[r]]
}

/// The row and column of a character cell.
fn grid_rc(g: usize) -> (usize, usize) {
    let r = (0..4).rev().find(|&r| g >= GRID_START[r]).unwrap_or(0);
    (r, g - GRID_START[r])
}

/// The horizontal middle of a character cell in half keys (so that Up and Down keep the nearest column).
fn grid_mid(g: usize) -> usize {
    let (r, c) = grid_rc(g);
    GRID_INDENT[r] + 2 * c + 1
}

/// The cell of row `r` whose middle is nearest to `mid`.
fn grid_nearest(r: usize, mid: usize) -> usize {
    (0..GRID_ROWS[r].len())
        .map(|c| GRID_START[r] + c)
        .min_by_key(|&g| grid_mid(g).abs_diff(mid))
        .unwrap_or(GRID_START[r])
}

/// The text being typed: the room's code (level 3) or a password (level 5): (where, its length's byte, at most,
/// at least).
fn field(core: &Core) -> (u32, u32, usize, usize) {
    if level(core) == NAME_LEVEL {
        (NAME_BUF, NAME_LEN, NAME_TYPED_CHARS, 0)
    } else if level(core) == TAG_LEVEL {
        (
            crate::online_stats::TAG_BUF,
            crate::online_stats::TAG_LEN,
            crate::online_stats::TAG_CHARS,
            1,
        )
    } else if level(core) == 5 {
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
    // (a space is never first and never twice in a row: a name is whole words)
    let space_ok = c == b' ' && allow_space(core) && n > 0 && core.raw_read_8(at + n - 1, -1) != b' ';
    if (CODE_ALPHABET.contains(&c) || space_ok) && (n as usize) < max {
        core.raw_write_8(at + n, -1, c);
        core.raw_write_8(len, -1, n as u8 + 1);
    }
}

/// What is typed on the page being typed, whole words only: no space at the end (it was typed to go on with).
fn trim_typed(core: &mut Core) {
    loop {
        let (at, len, _, _) = field(core);
        let n = core.raw_read_8(len, -1) as u32;
        if n > 0 && core.raw_read_8(at + n - 1, -1) == b' ' {
            rub_out(core);
        } else {
            break;
        }
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
    trim_typed(core);
    let (_, len, _, min) = field(core);
    if (core.raw_read_8(len, -1) as usize) < min {
        return;
    }
    if level(core) == NAME_LEVEL {
        // The room's name is typed: the password comes next (none is fine), and B on it comes back here.
        clear_field(core, PASSWORD, PASSWORD_LEN, PASSWORD_CHARS);
        core.raw_write_8(ENTRY, -1, 0);
        core.raw_write_8(GRID, -1, GRID_OK as u8);
        core.raw_write_8(TYPED_LEN, -1, 0);
        set_level(core, 5);
        return;
    }
    if level(core) == TAG_LEVEL {
        // The gamertag: kept here at once, the app keeps it too.
        crate::online_stats::commit(core);
        request(core, REQUEST_GAMERTAG);
        let back = crate::online_stats::entry_from(core);
        set_level(core, back.min(1));
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
    if level(core) == TAG_LEVEL {
        let back = crate::online_stats::entry_from(core);
        set_level(core, back.min(1));
    } else if level(core) == 5 && core.raw_read_8(ENTRY, -1) == 1 {
        if core.raw_read_8(crate::online_browse::FROM, -1) == 1 {
            // (the password of a lobby picked from the list: back to the list)
            set_level(core, 7);
            return;
        }
        core.raw_write_8(GRID, -1, 0);
        set_level(core, 3);
    } else if level(core) == 5 {
        // (the password of a room to make: back to its name)
        core.raw_write_8(GRID, -1, GRID_OK as u8);
        set_level(core, NAME_LEVEL);
    } else {
        set_level(core, 1);
    }
}

fn player(core: &Core, slot: usize) -> Option<(String, bool, u8)> {
    let mut b = [0u8; PLAYER_SIZE as usize];
    core.raw_read_range(PLAYERS + PLAYER_SIZE * slot as u32, -1, &mut b);
    (b[1] & PRESENT != 0).then(|| {
        (
            b[2..2 + NAME_CHARS]
                .iter()
                .take_while(|&&c| c != 0)
                .map(|&c| c as char)
                .collect(),
            b[0] == 1,
            b[1],
        )
    })
}

/// A player's link diagnostic: (kind, round trip in ms).
fn player_link(core: &Core, slot: usize) -> (u8, u8) {
    let mut b = [0u8; PLAYER_SIZE as usize];
    core.raw_read_range(PLAYERS + PLAYER_SIZE * slot as u32, -1, &mut b);
    (b[LINK_KIND], b[LINK_RTT])
}

/// The words for a link in at most `avail` pixels ("direct 23ms", "relay 140ms", or shorter), or nothing when
/// nothing is known or no form fits.
fn link_label(core: &Core, kind: u8, rtt: u8, avail: i32) -> Option<String> {
    if kind == 0 && rtt == 0 {
        return None;
    }
    let word = match kind {
        LINK_DIRECT => "direct",
        LINK_RELAY => "relay",
        _ => "",
    };
    let short = match kind {
        LINK_DIRECT => "D",
        LINK_RELAY => "R",
        _ => "",
    };
    let rtt = if rtt == 255 {
        "255+".to_string()
    } else {
        rtt.to_string()
    };
    let forms = [
        format!("{word} {rtt}ms"),
        format!("{word} {rtt}"),
        format!("{short} {rtt}ms"),
        format!("{short} {rtt}"),
        format!("{word}"),
        format!("{short}"),
    ];
    forms
        .into_iter()
        .map(|f| f.trim().to_string())
        .find(|f| !f.is_empty() && text_width(core, f) <= avail)
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
    // UNRANKED's match is still on (the app crashed): the rejoin box comes before everything else on the menus.
    if level(core) <= 1 && matches!(core.raw_read_8(REJOIN, -1), 1 | 2) {
        set_level(core, REJOIN_LEVEL);
        return keys & !ALL_KEYS;
    }
    // The first visit asks for a gamertag when none is set.
    // (SELECT on the ONLINE and LOBBY menus sets it, too.)
    if level(core) <= 1 && (crate::online_stats::should_ask(core) || pressed & KEY_SELECT != 0) {
        let from = level(core);
        crate::online_stats::open_entry(core, from);
        core.raw_write_8(GRID, -1, 0);
        core.raw_write_8(TYPED_LEN, -1, 0);
        set_level(core, TAG_LEVEL);
        return keys & !ALL_KEYS;
    }
    let level = level(core);
    crate::online_menu::draw(core, level as usize);
    match level {
        0 => {
            if pressed & KEY_R != 0 {
                set_level(core, CONN_LEVEL);
                return keys & !ALL_KEYS;
            }
            if pressed & (KEY_A | KEY_START) != 0 {
                if cursor == 0 {
                    // UNRANKED: look for an opponent.
                    request(core, 7);
                    set_level(core, 6);
                } else if cursor == 1 {
                    set_level(core, 1);
                } else if cursor == 2 {
                    crate::online_stats::open_stats(core);
                    set_level(core, STATS_LEVEL);
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
                        // CREATE: the room's name first (none is fine: OK or START takes the default), then a password
                        // (none is fine too).
                        clear_field(core, NAME_BUF, NAME_LEN, NAME_TYPED_CHARS + 1);
                        core.raw_write_8(ENTRY, -1, 0);
                        core.raw_write_8(GRID, -1, GRID_OK as u8);
                        core.raw_write_8(TYPED_LEN, -1, 0);
                        set_level(core, NAME_LEVEL);
                    }
                    1 => {
                        // JOIN: the public lobbies, with "Enter a code" first.
                        crate::online_browse::open(core);
                        set_level(core, 7);
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
                // (a lobby joined from the list: back to the list)
                let back = level == 4 && core.raw_read_8(crate::online_browse::FROM, -1) == 1;
                set_level(core, if back { 7 } else { 1 });
            } else if connected && !host && pressed & KEY_A != 0 {
                request(core, if my_ready { 5 } else { 4 });
            } else if connected && host && others_ready && !my_ready && pressed & (KEY_START | KEY_A) != 0 {
                request(core, 6);
            }
            keys & !ALL_KEYS
        }
        3 | 5 | TAG_LEVEL | NAME_LEVEL => {
            code_entry(core, pressed);
            keys & !ALL_KEYS
        }
        CONN_LEVEL => {
            if pressed & KEY_B != 0 {
                set_level(core, 0);
            }
            keys & !ALL_KEYS
        }
        STATS_LEVEL => {
            if pressed & KEY_B != 0 {
                set_level(core, 0);
            } else if pressed & (KEY_UP | KEY_DOWN) != 0 {
                crate::online_stats::scroll(core, pressed & KEY_DOWN != 0);
            }
            keys & !ALL_KEYS
        }
        REJOIN_LEVEL => {
            let state = core.raw_read_8(REJOIN, -1);
            let failed = Status::of(core.raw_read_8(STATUS, -1)) == Status::Failed;
            if state == 1 && pressed & KEY_START != 0 {
                // (later: the match stays offered, on the JOIN list above "Enter a code")
                core.raw_write_8(REJOIN, -1, 3);
                set_level(core, 1);
            } else if state == 1 && pressed & KEY_A != 0 {
                core.raw_write_8(REJOIN, -1, 2);
                core.raw_write_8(STATUS, -1, 0);
                request(core, 11);
            } else if (state != 0
                && pressed & KEY_B != 0
                && Status::of(core.raw_read_8(STATUS, -1)) != Status::Connected)
                || state == 0
            {
                // (B: the army yields, unless the way back already failed: then the match is over and it is just left)
                if !failed && state != 0 {
                    request(core, 12);
                }
                core.raw_write_8(REJOIN, -1, 0);
                set_level(core, 1);
            }
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
        7 => {
            use crate::online_browse::Pick;
            match crate::online_browse::tick(core, pressed) {
                Pick::Back => set_level(core, 1),
                Pick::Code => {
                    clear_field(core, CODE, CODE_LEN, CODE_CHARS);
                    core.raw_write_8(GRID, -1, 0);
                    core.raw_write_8(TYPED_LEN, -1, 0);
                    core.raw_write_8(crate::online_browse::FROM, -1, 0);
                    set_level(core, 3);
                }
                Pick::Open(c) => join_listed(core, &c, false),
                Pick::Locked(c) => join_listed(core, &c, true),
                Pick::Rejoin => {
                    // (the player's own match that is still on: the same as A on the rejoin box)
                    core.raw_write_8(REJOIN, -1, 2);
                    core.raw_write_8(STATUS, -1, 0);
                    request(core, 11);
                    set_level(core, REJOIN_LEVEL);
                }
                _ => {}
            }
            keys & !ALL_KEYS
        }
        _ => {
            set_level(core, 0);
            keys
        }
    }
}

/// A lobby picked from the list: its code goes where a typed one would, and its password (if it has one) is asked for
/// on the password page; B comes back to the list.
fn join_listed(core: &mut Core, code: &str, locked: bool) {
    clear_field(core, CODE, CODE_LEN, CODE_CHARS);
    for c in code.bytes().take(CODE_CHARS) {
        type_field(core, CODE, CODE_LEN, c);
    }
    clear_field(core, PASSWORD, PASSWORD_LEN, PASSWORD_CHARS);
    core.raw_write_8(TYPED_LEN, -1, 0);
    core.raw_write_8(ENTRY, -1, 1);
    core.raw_write_8(crate::online_browse::FROM, -1, 1);
    if locked {
        core.raw_write_8(GRID, -1, GRID_OK as u8);
        set_level(core, 5);
    } else {
        request(core, 2);
        set_level(core, 4);
    }
}

fn type_field(core: &mut Core, at: u32, len: u32, c: u8) {
    let n = core.raw_read_8(len, -1) as u32;
    core.raw_write_8(at + n, -1, c);
    core.raw_write_8(len, -1, n as u8 + 1);
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
    // The bottom row: Del and OK (and the space bar between them where a name is typed). Left and Right go round their row; Up
    // and Down keep the nearest column.
    let spaces = allow_space(core);
    if !spaces && g == GRID_SPACE {
        g = GRID_OK;
    }
    let bottom: &[usize] = if spaces {
        &[GRID_DEL, GRID_SPACE, GRID_OK]
    } else {
        &[GRID_DEL, GRID_OK]
    };
    // (the cell of the bottom row under a key of the row above, by its middle in half keys)
    let last_row_mid = |g: usize| {
        let mid = grid_mid(g);
        if spaces {
            if mid <= 6 {
                GRID_DEL
            } else if mid <= 13 {
                GRID_SPACE
            } else {
                GRID_OK
            }
        } else if mid <= 10 {
            GRID_DEL
        } else {
            GRID_OK
        }
    };
    if pressed & (KEY_RIGHT | KEY_LEFT | KEY_UP | KEY_DOWN) != 0 {
        if g >= GRID_DEL {
            let at = bottom.iter().position(|&b| b == g).unwrap_or(0);
            if pressed & KEY_RIGHT != 0 {
                g = bottom[(at + 1) % bottom.len()];
            } else if pressed & KEY_LEFT != 0 {
                g = bottom[(at + bottom.len() - 1) % bottom.len()];
            } else {
                // (Del is under the left of the row above, OK under its right, the space bar between)
                let mids: &[usize] = if spaces { &[5, 9, 13] } else { &[5, 13] };
                let top_mids: &[usize] = if spaces { &[5, 10, 15] } else { &[5, 15] };
                g = if pressed & KEY_UP != 0 {
                    grid_nearest(3, mids[at])
                } else {
                    grid_nearest(0, top_mids[at])
                };
            }
        } else {
            let (r, c) = grid_rc(g);
            let len = GRID_ROWS[r].len();
            if pressed & KEY_RIGHT != 0 {
                g = GRID_START[r] + (c + 1) % len;
            }
            if pressed & KEY_LEFT != 0 {
                g = GRID_START[r] + (c + len - 1) % len;
            }
            if pressed & KEY_DOWN != 0 {
                g = if r == 3 {
                    last_row_mid(g)
                } else {
                    grid_nearest(r + 1, grid_mid(g))
                };
            }
            if pressed & KEY_UP != 0 {
                g = if r == 0 {
                    last_row_mid(g)
                } else {
                    grid_nearest(r - 1, grid_mid(g))
                };
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
            GRID_SPACE => type_char(core, b' '),
            _ => {
                type_char(core, grid_char(g));
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
        Some((_, sub)) if sub & ONLINE_MATCH != 0 => {
            core.raw_read_8(MATCH, -1) == 0 || (navigating(core) && !waiting_for_room(core))
        }
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
                note_order(None);
                crate::unranked::init(core, sub);
                start_nav(core, GOAL_VERSUS);
            }
            if let Some(k) = nav(core) {
                return k;
            }
            // (a room that has fallen to one player ends too, crate::proxy_seat)
            if crate::campaign_menu::on_select_mode(core)
                || crate::unranked::finished(core)
                || crate::proxy_seat::alone(core)
            {
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
            // (the chosen map is walked to and chosen; UNRANKED: the standard rules are set)
            keys = crate::unranked::drive(core, keys);
            keys = crate::unranked::rules(core, keys);
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
            crate::online_maps::offline_before(core, keys)
        }
        _ => crate::online_maps::offline_before(core, keys),
    }
}

pub(crate) const LIST_IDS: u32 = crate::five_map::LIST_IDS;

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
    if i >= crate::five_map::LIST_CAP {
        return None;
    }
    let id = core.raw_read_8(LIST_IDS + i, -1) as u32;
    let n = core.raw_read_8(crate::five_map::table(core) + 0x5C * id + 0x18, -1);
    (1..=5).contains(&n).then_some(n)
}

/// The online match's notes over its console (presentation only): a map for another number of players.
pub fn apply_match(core: &Core, rgba: &mut [u8]) {
    // The walk to SELECT MAP presses the game's own menus (Select Mode, Versus): the players see none of it.
    // (a room that has fallen to one player is over: SELECT MAP is not shown to it, the lobby follows)
    if rgba.len() == W * H * 4
        && core.raw_read_8(MATCH, -1) == 1
        && (navigating(core) || crate::proxy_seat::alone(core))
    {
        for px in rgba.chunks_exact_mut(4) {
            px.copy_from_slice(&[0, 0, 0, 255]);
        }
        return;
    }
    crate::online_teams::draw(core, rgba);
    crate::unranked::draw(core, rgba);
    crate::online_maps::draw_hint(core, rgba);
    if rgba.len() == W * H * 4 && core.raw_read_8(MATCH, -1) == 1 {
        if let Some(seat) = crate::proxy_seat::left_note(core) {
            let mut cv = Rgba(rgba);
            let name = room_physical_name(seat);
            let name = fit(
                core,
                &name,
                W as i32 - 2 * 8 - text_width(core, " left the room. Pick a map again."),
            );
            bar(&mut cv, core, &format!("{name} left the room. Pick a map again."));
            return;
        }
    }
    if rgba.len() != W * H * 4 || core.raw_read_8(MATCH, -1) != 1 || core.raw_read_8(NOTICE, -1) == 0 {
        return;
    }
    if crate::survival_ui::selecting(core) {
        let mut cv = Rgba(rgba);
        bar(
            &mut cv,
            core,
            &format!("Pick a map for {} players.", crate::online_teams::players(core)),
        );
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
    if battle && crate::pvp::turn_ended(core) {
        if core.raw_read_8(ENDER, -1) == 0 {
            core.raw_write_8(ENDER, -1, crate::pvp::current_army(core));
        }
    } else if core.raw_read_8(ENDER, -1) != 0 {
        core.raw_write_8(ENDER, -1, 0);
    }
    if crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        if !battle {
            core.raw_write_8(BATTLE, -1, 1);
            if input_log_on() {
                log::info!(
                    "input-drop: battle started, Teams record controller bytes (1 = human) {:?}",
                    crate::online_teams::controller_bytes(core)
                );
            }
            crate::online_stats::battle_started(core);
        }
        core.raw_write_8(OUT_T, -1, 0);
        crate::online_stats::track(core);
    } else if battle {
        // Out of the battle for good (results, the save prompt, SELECT MAP again), not for a moment between its screens.
        let t = core.raw_read_8(OUT_T, -1).saturating_add(1);
        core.raw_write_8(OUT_T, -1, t);
        let menus = crate::survival_ui::selecting(core)
            || crate::pvp::on_teams_screen(core)
            || crate::campaign_menu::on_select_mode(core);
        if !menus {
            crate::online_stats::track(core);
        }
        if t > 150 || menus {
            core.raw_write_8(BATTLE, -1, 0);
            core.raw_write_8(OUT_T, -1, 0);
            crate::online_stats::battle_ended();
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

/// Each seat's (team 0..=4, army colour code) as last seen on the console, for the status bar (presentation only).
static ROOM_PICKS: std::sync::Mutex<Vec<(u8, u8)>> = std::sync::Mutex::new(Vec::new());

pub(crate) fn set_picks(picks: Vec<(u8, u8)>) {
    let mut p = ROOM_PICKS.lock().unwrap();
    if *p != picks {
        *p = picks;
    }
}

/// Each seat's (team 0..=4, army colour code, 1 Orange Star .. 5 Black Hole) in the room's match, once chosen.
pub fn room_picks() -> Vec<(u8, u8)> {
    ROOM_PICKS.lock().unwrap().clone()
}

/// The room's players' gamertags in seat order, and which seat this peer is.
pub fn set_room(names: Vec<String>, local_seat: usize) {
    let none = names.is_empty();
    *ROOM_INFO.lock().unwrap() = RoomInfo { names, local_seat };
    ROOM_PICKS.lock().unwrap().clear();
    // (the console's tick notes who has left, from its own RAM; a room that is gone has nobody)
    if none {
        *ROOM_ORDER.lock().unwrap() = None;
    }
}

/// The seats the room's console plays now, in its order (a physical seat each), once players have left (see
/// [`crate::proxy_seat`]); `None` while the room is whole. Presentation only, noted by the console's tick from its RAM.
static ROOM_ORDER: std::sync::Mutex<Option<Vec<usize>>> = std::sync::Mutex::new(None);

pub(crate) fn note_order(order: Option<Vec<usize>>) {
    let mut o = ROOM_ORDER.lock().unwrap();
    if *o != order {
        *o = order;
    }
}

/// The room's seats as the console plays them: the physical seat of each, in order.
fn order() -> Option<Vec<usize>> {
    ROOM_ORDER.lock().unwrap().clone()
}

/// The room's seat of each console seat, in the console's order: whole while no one has left, else the players still there.
pub fn room_seats() -> Vec<usize> {
    let n = ROOM_INFO.lock().unwrap().names.len();
    order().unwrap_or_else(|| (0..n).collect())
}

/// The gamertag of a seat of the room itself (not counted without the players who left).
pub fn room_physical_name(seat: usize) -> String {
    ROOM_INFO
        .lock()
        .unwrap()
        .names
        .get(seat)
        .cloned()
        .unwrap_or_else(|| format!("Player {}", seat + 1))
}

/// A seat of the console (counted without the players who left) as the room's name for it.
pub fn room_name(seat: usize) -> String {
    let info = ROOM_INFO.lock().unwrap();
    let physical = order().and_then(|o| o.get(seat).copied()).unwrap_or(seat);
    info.names
        .get(physical)
        .cloned()
        .unwrap_or_else(|| format!("Player {}", physical + 1))
}

/// The console's seat of this peer (its place among the players still in the room).
pub fn room_local_seat() -> usize {
    let local = ROOM_INFO.lock().unwrap().local_seat;
    order()
        .and_then(|o| o.iter().position(|&p| p == local))
        .unwrap_or(local)
}

/// How many gamertags the room's match has (0: none were told, e.g. a link-code game).
pub fn room_named() -> usize {
    let n = ROOM_INFO.lock().unwrap().names.len();
    order().map_or(n, |o| o.len().min(n))
}

/// How many players the room has, for the picture (2 when nobody said).
pub fn room_players() -> usize {
    let n = ROOM_INFO.lock().unwrap().names.len();
    order().map_or(n, |o| o.len()).clamp(2, 5)
}

/// The match is over: its players left SELECT MAP for Select Mode.
pub fn match_over(core: &Core) -> bool {
    core.raw_read_8(MATCH, -1) == 1 && core.raw_read_8(OVER, -1) == 1
}

/// Test aid (`TANGOAW2_INPUT_LOG=1`): log the keys of the seats that are not the active one, which the merge drops,
/// whenever they change.
pub(crate) fn input_log_on() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("TANGOAW2_INPUT_LOG").is_ok_and(|v| v == "1"))
}

fn log_dropped(active: usize, army: u8, inputs: &[u32]) {
    static LAST: std::sync::Mutex<Vec<u32>> = std::sync::Mutex::new(Vec::new());
    let dropped: Vec<u32> = inputs
        .iter()
        .enumerate()
        .map(|(k, &v)| if k == active { 0 } else { v & 0x3FF })
        .collect();
    let mut last = LAST.lock().unwrap();
    if *last != dropped {
        if dropped.iter().any(|&v| v != 0) {
            let list: Vec<String> = dropped
                .iter()
                .enumerate()
                .filter(|(_, &v)| v != 0)
                .map(|(k, v)| format!("seat{k}={v:#05x}"))
                .collect();
            log::info!(
                "input-drop: active seat {active} (army {army}) kept {:#05x}; dropped {}",
                inputs[active] & 0x3FF,
                list.join(" ")
            );
        } else if !last.is_empty() {
            log::info!("input-drop: none (active seat {active}, army {army})");
        }
        *last = dropped;
    }
}

/// The army that takes over when `current`'s turn has ended in a room of `n` players (army 5 hands to 1).
fn incoming_army(current: u8, n: usize) -> u8 {
    current % n.max(1) as u8 + 1
}

/// [`incoming_army`] that skips the armies that are out (the game plays the next one still in).
fn incoming_alive(core: &Core, current: u8, n: usize) -> u8 {
    let mut a = incoming_army(current, n);
    for _ in 0..n {
        if crate::result_view::alive(core, a) {
            return a;
        }
        a = incoming_army(a, n);
    }
    incoming_army(current, n)
}

/// Test aid (`TANGOAW2_INPUT_LOG=1`): every unit on the map (army, kind, cell, hit points), logged whenever the list
/// changes (looked at twice a second), so the pictures can be checked against the game's own state.
fn log_units(core: &Core) {
    use std::sync::atomic::{AtomicU32, Ordering::Relaxed};
    static TICK: AtomicU32 = AtomicU32::new(0);
    if TICK.fetch_add(1, Relaxed) % 30 != 0 {
        return;
    }
    const MAP: u32 = 0x0201_E450;
    let (w, h) = (core.raw_read_16(MAP, -1) as u32, core.raw_read_16(MAP + 2, -1) as u32);
    if w == 0 || w > 64 || h == 0 || h > 64 {
        return;
    }
    let base = core.raw_read_32(0x0849_9594, -1);
    let mut out = format!(" [map {w}x{h}]");
    for y in 0..h {
        let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
        for x in 0..w {
            let id = core.raw_read_8(MAP + 0x51A + row + x, -1) as u32;
            if id == 0 {
                continue;
            }
            let u = base + 12 * id;
            let t = core.raw_read_8(u, -1) as usize;
            if t == 0 {
                continue;
            }
            let hp = core.raw_read_16(u + 4, -1) & 0x7F;
            let name = crate::bh_smart::NAMES.get(t).copied().unwrap_or("?");
            out.push_str(&format!(
                " A{} {name}({x},{y}) hp{hp};",
                crate::five::army_of_index(core, id)
            ));
        }
    }
    static TERRAIN_DONE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
    if !TERRAIN_DONE.swap(true, Relaxed) {
        // (once per run: the terrain class of every cell, two hex digits each, for working out routes offline)
        for y in 0..h {
            let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
            let line: String = (0..w)
                .map(|x| format!("{:02x} ", core.raw_read_8(MAP + 0x1432 + row + x, -1) & 0x1F))
                .collect();
            log::info!("terrain y={y:02}: {line}");
        }
    }
    static LAST: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
    let mut last = LAST.lock().unwrap();
    if *last != out {
        log::info!("units:{out}");
        *last = out;
    }
}

/// Test aid (`TANGOAW2_INPUT_LOG=1`): while a screen other than the plain map is up in a battle (a battle scene, a page),
/// once a second the main-loop callback, the fog byte and the two battle records, to see what tells who fights.
fn log_scene(core: &Core) {
    use std::sync::atomic::{AtomicU32, Ordering::Relaxed};
    static TICK: AtomicU32 = AtomicU32::new(0);
    if TICK.fetch_add(1, Relaxed) % 60 != 0 {
        return;
    }
    let ml = core.raw_read_32(0x0300_0000, -1);
    if ml == 0x0802_2049 {
        return;
    }
    let words = |at: u32| {
        (0..8)
            .map(|k| format!("{:08x}", core.raw_read_32(at + 4 * k, -1)))
            .collect::<Vec<_>>()
            .join(" ")
    };
    log::info!(
        "scene: loop {ml:08x} fog byte {} attacker record {} | defender record {}",
        core.raw_read_8(0x0300_3FCD, -1),
        words(0x0300_13D0),
        words(0x0300_13B0)
    );
}

/// Who drives the pad on an online match's console, outside a battle's turns (`None`: the usual rules).
pub fn merge(core: &Core, inputs: &[u32]) -> Option<u32> {
    if core.raw_read_8(MATCH, -1) != 1 {
        return None;
    }
    if navigating(core) {
        return Some(0);
    }
    // (a player left after the map was drawn: B, every other few frames, takes the game back to SELECT MAP)
    if crate::proxy_seat::backing_out(core) {
        return Some(crate::proxy_seat::back_key(core));
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
        let Some(army) = pad_army(core, n) else { return Some(0) };
        let active = crate::pvp::seat_of_n(army, n);
        if input_log_on() {
            log_dropped(active, army, inputs);
            log_units(core);
            log_scene(core);
            static CELLS_FOR: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);
            if CELLS_FOR.swap(current, std::sync::atomic::Ordering::Relaxed) != current {
                crate::fog_view::log_cells(core, current);
            }
            static CURSOR_WAS: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
            let at = core.raw_read_16(0x0300_33E4, -1) as u32 | (core.raw_read_16(0x0300_33E6, -1) as u32) << 16;
            if CURSOR_WAS.swap(at, std::sync::atomic::Ordering::Relaxed) != at {
                log::info!("cursor ({},{}) army {current}", at & 0xFFFF, at >> 16);
            }
        }
        return Some(inputs[active]);
    }
    if !crate::pvp::in_versus(core) {
        return None;
    }
    // Versus' Teams screen is not played: every player has a selector of their own (crate::online_teams).
    if crate::pvp::on_teams_screen(core) {
        return Some(crate::online_teams::merge(core).unwrap_or(0));
    }
    // (the screens outside a battle are the room's host's: seat 0, or the seat a host migration gave the room to)
    Some(inputs[crate::proxy_seat::host_index(core, inputs.len())])
}

/// The army that has the pad in a room's battle: the army whose turn it is, or, from the moment a turn has ended until the
/// next begins, the army that takes over (a yielded army's turn ends by itself). `None` outside a battle, or when no army
/// can be told.
pub(crate) fn pad_army(core: &Core, n: usize) -> Option<u8> {
    if core.raw_read_8(MATCH, -1) != 1 || core.raw_read_8(BATTLE, -1) != 1 {
        return None;
    }
    let current = crate::pvp::current_army(core);
    if !(1..=5).contains(&current) {
        return None;
    }
    // (the incoming army: the one after the army that chose End, which stays the same when the game has already moved
    // its current army on while the End screen is still up)
    let ender = core.raw_read_8(ENDER, -1);
    Some(if crate::pvp::turn_ended(core) {
        incoming_alive(core, if (1..=5).contains(&ender) { ender } else { current }, n)
    } else {
        current
    })
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
/// The game's pink plate (SELECT MAP's boxes): black edge, red frame, pink page; grey and lavender-blue ink on it.
pub(crate) const PLATE_RED: Rgb = (246, 82, 57);
pub(crate) const PLATE_PINK: Rgb = (255, 238, 238);
pub(crate) const PLATE_GREY: Rgb = (131, 123, 115);
pub(crate) const PLATE_INK: Rgb = (88, 72, 150);

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
    pub(crate) fn window(&mut self, x: i32, y: i32, w: i32, h: i32) {
        audit::window(x, y, w, h);
        self.rect(x - 1, y - 1, w + 2, h + 2, INK);
        self.rect(x, y, w, h, WHITE);
        self.rect(x + 1, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x + w - 2, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x, y, w, 2, RED);
        self.rect(x, y + h - 2, w, 2, BLUE);
    }
    /// A plate as the game's SELECT MAP boxes: a black edge, a red frame, a pink page.
    pub(crate) fn plate(&mut self, x: i32, y: i32, w: i32, h: i32) {
        audit::window(x, y, w, h);
        self.rect(x - 1, y - 1, w + 2, h + 2, (0, 0, 0));
        self.rect(x, y, w, h, PLATE_RED);
        self.rect(x + 2, y + 2, w - 4, h - 4, PLATE_PINK);
    }
    /// AW2's proportional font; returns the x after the text.
    pub(crate) fn text(&mut self, core: &Core, x: i32, y: i32, s: &str, ink: Rgb, shade: Rgb) -> i32 {
        if audit::on() {
            audit::text(x, y, text_width(core, s), s);
        }
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

/// A record of what a page draws, for the text audit (`examples/aw2_online_text_audit.rs`): every string with
/// its extent and every window, so a string that leaves the window it starts in (or the screen) is found.
/// Off (one atomic load a string) unless the audit turns it on.
pub mod audit {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Mutex;

    static ON: AtomicBool = AtomicBool::new(false);
    static LOG: Mutex<(Vec<(i32, i32, i32, i32)>, Vec<(i32, i32, i32, String)>)> = Mutex::new((Vec::new(), Vec::new()));

    /// A box drawn over what is under it: the strings that start in it are hidden.
    pub(crate) fn cover(x: i32, y: i32, w: i32, h: i32) {
        if ON.load(Ordering::Relaxed) {
            LOG.lock()
                .unwrap()
                .1
                .retain(|&(tx, ty, _, _)| !(tx >= x && tx < x + w && ty >= y && ty < y + h));
        }
    }

    pub(crate) fn on() -> bool {
        ON.load(Ordering::Relaxed)
    }

    pub(crate) fn window(x: i32, y: i32, w: i32, h: i32) {
        if ON.load(Ordering::Relaxed) {
            LOG.lock().unwrap().0.push((x, y, w, h));
        }
    }

    pub(crate) fn text(x: i32, y: i32, w: i32, s: &str) {
        if ON.load(Ordering::Relaxed) {
            LOG.lock().unwrap().1.push((x, y, w, s.to_string()));
        }
    }

    /// Starts recording (and forgets what was).
    pub fn start() {
        *LOG.lock().unwrap() = (Vec::new(), Vec::new());
        ON.store(true, Ordering::Relaxed);
    }

    /// Stops recording; the problems found in the picture drawn since [`start`]: a string whose extent leaves the
    /// innermost window it starts in (2 px of the window's edge are its frame), or the screen (2 px margin).
    pub fn finish() -> Vec<String> {
        ON.store(false, Ordering::Relaxed);
        let (wins, texts) = std::mem::take(&mut *LOG.lock().unwrap());
        let mut bad = Vec::new();
        let texts_kept: Vec<_> = texts.iter().filter(|t| !t.3.trim().is_empty()).cloned().collect();
        for (x, y, w, s) in texts {
            if s.trim().is_empty() {
                continue;
            }
            let end = x + w;
            if x < 0 || end > 240 - 2 {
                bad.push(format!("off the screen: {s:?} x {x}..{end}"));
                continue;
            }
            // (the innermost window: the last drawn that holds the string's start)
            if let Some(&(wx, wy, ww, wh)) = wins
                .iter()
                .rev()
                .find(|&&(wx, wy, ww, wh)| x >= wx && x < wx + ww && y >= wy && y < wy + wh)
            {
                if end > wx + ww - 2 {
                    bad.push(format!(
                        "leaves its window: {s:?} x {x}..{end}, window {wx}..{}",
                        wx + ww
                    ));
                }
            }
        }
        // (two strings on one line that run into each other)
        let ts: Vec<&(i32, i32, i32, String)> = texts_kept.iter().collect();
        for (i, a) in ts.iter().enumerate() {
            for b in &ts[i + 1..] {
                if (a.1 - b.1).abs() < 9 && a.0 < b.0 + b.2 && b.0 < a.0 + a.2 {
                    bad.push(format!(
                        "overlap: {:?} x {}..{} and {:?} x {}..{} (y {}/{})",
                        a.3,
                        a.0,
                        a.0 + a.2,
                        b.3,
                        b.0,
                        b.0 + b.2,
                        a.1,
                        b.1
                    ));
                }
            }
        }
        bad
    }
}

pub fn text_width(core: &Core, s: &str) -> i32 {
    s.bytes()
        .map(|c| {
            if c.is_ascii_digit() {
                DIGIT_W as i32 + 1
            } else {
                core.raw_read_8(FONT_WIDTHS + c as u32, -1) as i32 + 1
            }
        })
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
    [
        ".###..", "#...#.", "#..##.", "#.#.#.", "##..#.", "#...#.", "#...#.", "#...#.", ".###..",
    ],
    [
        "..#...", ".##...", "#.#...", "..#...", "..#...", "..#...", "..#...", "..#...", "#####.",
    ],
    [
        ".###..", "#...#.", "....#.", "....#.", "...#..", "..#...", ".#....", "#.....", "#####.",
    ],
    [
        ".###..", "#...#.", "....#.", "....#.", "..##..", "....#.", "....#.", "#...#.", ".###..",
    ],
    [
        "...#..", "..##..", ".#.#..", "#..#..", "#..#..", "#####.", "...#..", "...#..", "...#..",
    ],
    [
        "#####.", "#.....", "#.....", "####..", "....#.", "....#.", "....#.", "#...#.", ".###..",
    ],
    [
        ".###..", "#.....", "#.....", "####..", "#...#.", "#...#.", "#...#.", "#...#.", ".###..",
    ],
    [
        "#####.", "....#.", "....#.", "...#..", "...#..", "..#...", "..#...", ".#....", ".#....",
    ],
    [
        ".###..", "#...#.", "#...#.", "#...#.", ".###..", "#...#.", "#...#.", "#...#.", ".###..",
    ],
    [
        ".###..", "#...#.", "#...#.", "#...#.", ".####.", "....#.", "....#.", "....#.", ".###..",
    ],
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
                (0..w).any(|cx| {
                    (core.raw_read_8(at + (stride * (3 + r) + cx / 2) as u32, -1) >> (4 * (cx & 1))) & 15 != 0
                })
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

/// A room's battle has begun and is not left yet (the screens after it, VICTORY and the results, belong to it).
pub(crate) fn battle_begun(core: &Core) -> bool {
    core.raw_read_8(BATTLE, -1) == 1
}

/// The help bar at the bottom, over the game's.
pub(crate) fn bar(cv: &mut Rgba, core: &Core, s: &str) {
    cv.rect(0, 144, W as i32, 16, BAR);
    let w = text_width(core, s);
    cv.text(core, (W as i32 - w) / 2, 147, s, WHITE, GRAY_INK);
}

/// Lines of at most `width` pixels.
pub(crate) fn wrap(core: &Core, s: &str, width: i32) -> Vec<String> {
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

pub(crate) const PANEL: (i32, i32, i32, i32) = (92, 26, 142, 114);

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

/// The code grid (letters, Del, OK) of the typing pages, its top `top` pixels below the panel's.
fn draw_grid(cv: &mut Rgba, core: &Core, panel: (i32, i32, i32, i32), top: i32) {
    let (x, y, w, _) = panel;
    let g = core.raw_read_8(GRID, -1) as usize;
    let (cw, ch) = (13, 12);
    let gx = x + (w - cw * GRID_COLS as i32) / 2;
    let gy = y + top;
    let typed: Vec<char> = typed(core).chars().collect();
    let (_, _, max, min) = field(core);
    let full = typed.len() >= min;
    let spaces = allow_space(core);
    for k in 0..GRID_CELLS {
        if k == GRID_SPACE && !spaces {
            continue;
        }
        // The bottom row has a row of its own: Del and OK half the width each, or (a name) Del and OK three keys wide and the
        // space bar four between them.
        let by = gy + 4 * ch + 2;
        let (cx, cy, cwid, label) = match k {
            GRID_DEL if spaces => (gx, by, 3 * cw, "Del".to_string()),
            GRID_SPACE => (gx + 3 * cw, by, 4 * cw, "Space".to_string()),
            GRID_OK if spaces => (gx + 7 * cw, by, 3 * cw, "OK".to_string()),
            GRID_DEL => (gx, by, 5 * cw, "Del".to_string()),
            GRID_OK => (gx + 5 * cw, by, 5 * cw, "OK".to_string()),
            _ => {
                let (r, c) = grid_rc(k);
                (
                    gx + (GRID_INDENT[r] as i32 * cw) / 2 + c as i32 * cw,
                    gy + r as i32 * ch,
                    cw,
                    (grid_char(k) as char).to_string(),
                )
            }
        };
        let ready = match k {
            GRID_OK => full,
            GRID_DEL => true,
            GRID_SPACE => typed.len() < max && typed.last().is_some_and(|&c| c != ' '),
            _ => typed.len() < max,
        };
        if k == g {
            cv.rect(cx + 1, cy, cwid - 2, ch, YELLOW);
        } else if k == GRID_OK && full {
            // (an OK that can be pressed: a blue plate)
            cv.rect(cx + 1, cy, cwid - 2, ch, BLUE);
        }
        let ink = if k == GRID_OK && full && k != g {
            WHITE
        } else if ready {
            INK
        } else {
            SHADE
        };
        cv.text(
            core,
            cx + (cwid - text_width(core, &label)) / 2,
            cy + 1,
            &label,
            ink,
            SHADE,
        );
    }
}

/// The name a room gets when none is typed: "<gamertag>'s room" ("Player" while there is no gamertag).
pub fn default_room_name(gamertag: &str) -> String {
    let tag = clean_name(gamertag, crate::online_stats::TAG_CHARS);
    format!("{}'s room", if tag.is_empty() { "Player" } else { &tag })
}

/// The room's name typing page: the name typed in a box (the default, greyed, while none is typed), the grid with its space bar below.
fn draw_name_entry(cv: &mut Rgba, core: &Core, panel: (i32, i32, i32, i32)) {
    let (x, y, w, _) = panel;
    let head = "Name your room";
    cv.text(core, x + (w - text_width(core, head)) / 2, y + 5, head, GRAY_INK, SHADE);
    let name = typed(core);
    let (bx, by, bw, bh) = (x + 10, y + 19, w - 20, 20);
    cv.rect(bx, by, bw, bh, LIGHT_GRAY);
    cv.rect(bx, by + bh - 2, bw, 2, RED);
    if name.is_empty() {
        let d = default_room_name(&crate::online_stats::gamertag(core));
        let shown = fit(core, &d, bw - 8);
        cv.text(
            core,
            bx + (bw - text_width(core, &shown)) / 2,
            by + 4,
            &shown,
            SHADE,
            LIGHT_GRAY,
        );
        cv.rect(bx + 3, by + 14, 5, 2, INK);
    } else {
        let tw = text_width(core, &name);
        let nx = bx + (bw - tw - 6) / 2;
        cv.text(core, nx, by + 4, &name, INK, SHADE);
        if name.chars().count() < NAME_TYPED_CHARS {
            cv.rect(nx + tw + 2, by + 14, 5, 2, INK);
        }
    }
}

/// The name shown for the room that is open (the app's), if it has told one.
pub(crate) fn room_name_shown(core: &Core) -> String {
    let mut b = [0u8; ROOM_NAME_CHARS + 1];
    core.raw_read_range(crate::online_browse::ROOM_NAME, -1, &mut b);
    b.iter().take_while(|&&c| c != 0).map(|&c| c as char).collect()
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
    let text = |a: usize, n: usize| -> String {
        b[a..a + n]
            .iter()
            .take_while(|&&c| c != 0)
            .map(|&c| c as char)
            .collect()
    };
    (
        text(0, SAVED_PLAYERS),
        text(SAVED_PLAYERS, SAVED_MAP),
        text(SAVED_PLAYERS + SAVED_MAP, SAVED_TAIL),
    )
}

/// `s` cut with ".." to fit `width` pixels.
pub(crate) fn fit(core: &Core, s: &str, width: i32) -> String {
    if text_width(core, s) <= width {
        return s.to_string();
    }
    let mut t: String = s.to_string();
    while !t.is_empty() && text_width(core, &format!("{t}..")) > width {
        t.pop();
    }
    format!("{t}..")
}

/// The rejoin box: AW2's message window over the ONLINE screen (the same frame, font and bar as every page here). A match of
/// UNRANKED has no room name; a lobby's room is named.
pub(crate) fn rejoin_page(cv: &mut Rgba, core: &Core) {
    let (x, y, w, h) = (10, 38, W as i32 - 20, 68);
    cv.window(x, y, w, h);
    let state = core.raw_read_8(REJOIN, -1);
    let status = Status::of(core.raw_read_8(STATUS, -1));
    let room = crate::online_browse::own(core).unwrap_or_default();
    let (kind, still_on, over) = if room.is_empty() {
        (
            "Unranked",
            "Your Unranked match is still on.".to_string(),
            "Your Unranked match is over.",
        )
    } else {
        (
            "Lobby",
            format!("Your match in {room} is still on."),
            "Your match is over.",
        )
    };
    cv.text(core, x + 8, y + 6, kind, GRAY_INK, SHADE);
    let (lines, ink, hint): (Vec<String>, Rgb, &str) = match (state, status) {
        (1, _) => (
            wrap(core, &still_on, w - 24)
                .into_iter()
                .chain(std::iter::once("Rejoin?".to_string()))
                .collect(),
            INK,
            "A: Rejoin  B: Give up  START: Later",
        ),
        (_, Status::Failed) => {
            let m = message(core);
            (wrap(core, if m.is_empty() { over } else { &m }, w - 24), RED, "B: Back")
        }
        (_, Status::Connected) => (
            vec!["The others are here.".into(), "The match is resuming!".into()],
            BLUE,
            "Resuming...",
        ),
        _ => (
            vec![
                "Rejoining your match...".into(),
                "The others are waiting for you.".into(),
            ],
            INK,
            "B: Give up",
        ),
    };
    for (k, l) in lines.iter().take(3).enumerate() {
        let ink = if state == 1 && k + 1 == lines.len() { BLUE } else { ink };
        cv.text(
            core,
            x + (w - text_width(core, l)) / 2,
            y + 22 + 13 * k as i32,
            l,
            ink,
            SHADE,
        );
    }
    bar(cv, core, hint);
}

/// RESUME: the matches cut short, one under the cursor (UP and DOWN, A resumes it, START deletes it).
fn saved_page(cv: &mut Rgba, core: &Core) {
    let (x, y, w, h) = (6, 28, W as i32 - 12, 114);
    cv.window(x, y, w, h);
    let n = (core.raw_read_8(SAVED, -1) as usize).min(SAVED_MAX);
    cv.text(core, x + 6, y + 4, "Matches cut short", GRAY_INK, SHADE);
    if n == 0 {
        let t = "No saved matches.";
        cv.text(core, x + (w - text_width(core, t)) / 2, y + 48, t, GRAY_INK, SHADE);
        let t2 = "A match is kept when a player's connection drops.";
        let lines = wrap(core, t2, w - 20);
        for (k, l) in lines.iter().enumerate() {
            cv.text(
                core,
                x + (w - text_width(core, l)) / 2,
                y + 64 + 12 * k as i32,
                l,
                SHADE,
                LIGHT_GRAY,
            );
        }
        bar(cv, core, "B: Back");
        return;
    }
    let cur = (core.raw_read_8(RESUME_CUR, -1) as usize).min(n - 1);
    // Four rows show at a time, the cursor's among them.
    let first = cur.saturating_sub(3).min(n.saturating_sub(4));
    for (row, k) in (first..n.min(first + 4)).enumerate() {
        let (players, map, tail) = saved_row(core, k);
        let ry = y + 15 + 24 * row as i32;
        if k == cur {
            cv.rect(x + 3, ry - 1, w - 6, 23, YELLOW);
        } else {
            cv.rect(x + 4, ry + 22, w - 8, 1, LIGHT_GRAY);
        }
        cv.text(core, x + 7, ry, &fit(core, &players, w - 14), INK, SHADE);
        // (the day and date stay whole at the right; a long map name gives way to them)
        let ink = if k == cur { INK } else { GRAY_INK };
        let tail_w = text_width(core, &tail);
        cv.text(core, x + w - 7 - tail_w, ry + 11, &tail, ink, SHADE);
        cv.text(core, x + 7, ry + 11, &fit(core, &map, w - 14 - tail_w - 6), ink, SHADE);
    }
    if first > 0 {
        cv.text(core, x + w - 24, y + 4, "^", GRAY_INK, SHADE);
    }
    if first + 4 < n {
        cv.text(core, x + w - 14, y + 4, "v", GRAY_INK, SHADE);
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
    if level <= 1 {
        crate::online_stats::draw_tag(&mut cv, core);
        crate::online_conn::draw_corner(&mut cv, core);
    }
    match level {
        0 => {
            if core.raw_read_8(NOTICE, -1) > 0 && cursor == 0 {
                bar(&mut cv, core, "Coming soon!");
            }
        }
        1 => {
            let note = (Status::of(core.raw_read_8(STATUS, -1)) == Status::Back)
                .then(|| note(core))
                .filter(|m| !m.is_empty());
            let help = [
                "Make a room and give its code to a friend.",
                "Find a lobby, or type in a room's code.",
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
            let name = room_name_shown(core);
            let fallback = if hosting { "Your room" } else { "Room" };
            // (what the heading leaves room for: the right side has the host's password, or the guest's "Locked" with its padlock)
            let right = match (password(core).is_empty(), hosting) {
                (true, _) => 0,
                (false, true) => text_width(core, &format!("PW: {}", password(core))) + 8,
                (false, false) => text_width(core, "Locked") + 8 + 8,
            };
            let head_room = w - 12 - right;
            let head = if name.is_empty() {
                fallback.to_string()
            } else {
                fit(core, &name, head_room)
            };
            let head = head.as_str();
            let code = if hosting { room(core) } else { code(core) };
            cv.text(core, x + 6, y + 5, head, GRAY_INK, SHADE);
            let pw = password(core);
            if !pw.is_empty() && hosting {
                // The host sees the password it set ("Password: AB", or shorter when the heading leaves no room: the
                // value always shows whole).
                let room = w - 12 - text_width(core, head) - 8;
                let t = [format!("Password: {pw}"), format!("Pass: {pw}"), format!("PW: {pw}")]
                    .into_iter()
                    .find(|t| text_width(core, t) <= room)
                    .unwrap_or_else(|| pw.clone());
                cv.text(core, x + w - 6 - text_width(core, &t), y + 5, &t, GRAY_INK, SHADE);
            } else if !pw.is_empty() {
                // A guest sees only that the room is locked (the password is the host's to give).
                let t = "Locked";
                let tx = x + w - 6 - text_width(core, t);
                cv.text(core, tx, y + 5, t, GRAY_INK, SHADE);
                crate::online_browse::padlock(&mut cv, tx - 8, y + 7, GRAY_INK);
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
                title(
                    &mut cv,
                    core,
                    font,
                    x + (w - title_width(core, font, &code)) / 2,
                    y + 18,
                    &code,
                );
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
                        let tag_x = x + w - 6 - text_width(core, tag);
                        // (the name gives way before the tag does: its tail is cut with ".." and "(you)" stays)
                        let room = tag_x - 4 - (x + 16);
                        let shown = if text_width(core, &format!("{name}{you}")) <= room {
                            format!("{name}{you}")
                        } else {
                            format!("{}{you}", fit(core, &name, room - text_width(core, you)))
                        };
                        cv.text(core, x + 16, ry, &shown, INK, SHADE);
                        cv.text(core, tag_x, ry, tag, ink, SHADE);
                        // How this player is reached and the round trip, between the name and the tag.
                        let (kind, rtt) = player_link(core, k);
                        let from = x + 16 + text_width(core, &shown) + 5;
                        if let Some(l) = link_label(core, kind, rtt, tag_x - 6 - from) {
                            let at = tag_x - 6 - text_width(core, &l);
                            cv.text(core, at, ry, &l, if kind == LINK_RELAY { INK } else { GRAY_INK }, SHADE);
                        }
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
                        // (a saved match's "Waiting for ..." is shown nowhere else: it goes before the key)
                        let alone = lines.join(" ");
                        l = if status == Status::Waiting && text_width(core, &alone) <= W as i32 - 8 {
                            alone
                        } else {
                            b.to_string()
                        };
                    }
                    l
                }
            };
            bar(&mut cv, core, &hint);
            if status == Status::Failed {
                let (lines, ink) = status_lines(core, hosting);
                audit::cover(x + 3, y + 45, w - 6, 56);
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
                let ink = if k > 0 && status != Status::Connected && status != Status::Failed {
                    GRAY_INK
                } else {
                    ink
                };
                cv.text(
                    core,
                    x + (w - text_width(core, l)) / 2,
                    y + 28 + 13 * k as i32,
                    l,
                    ink,
                    SHADE,
                );
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
        REJOIN_LEVEL => rejoin_page(&mut cv, core),
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
                    title(
                        &mut cv,
                        core,
                        font,
                        cx + (bw - title_width(core, font, &s)) / 2,
                        y + 22,
                        &s,
                    );
                }
            }
            draw_grid(&mut cv, core, PANEL, 49);
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
        7 => crate::online_browse::apply(&mut cv, core),
        NAME_LEVEL => {
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            draw_name_entry(&mut cv, core, PANEL);
            draw_grid(&mut cv, core, PANEL, 44);
            bar(
                &mut cv,
                core,
                if typed(core).is_empty() {
                    "A: Type  B: Back  START: OK (default)"
                } else {
                    "A: Type  B: Rub out  START: OK"
                },
            );
        }
        TAG_LEVEL => {
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            crate::online_stats::draw_entry(&mut cv, core, PANEL);
            draw_grid(&mut cv, core, PANEL, 44);
            bar(&mut cv, core, "A: Type  B: Rub out  START: OK");
        }
        STATS_LEVEL => {
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            crate::online_stats::draw_stats(&mut cv, core, PANEL);
        }
        CONN_LEVEL => {
            let (x, y, w, h) = PANEL;
            cv.window(x, y, w, h);
            crate::online_conn::draw_page(&mut cv, core, PANEL);
        }
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hand_off_goes_to_the_next_seat_and_wraps() {
        for n in 2..=5usize {
            for current in 1..=n as u8 {
                let next = incoming_army(current, n);
                assert_eq!(
                    crate::pvp::seat_of_n(next, n),
                    (crate::pvp::seat_of_n(current, n) + 1) % n,
                    "n {n} army {current}"
                );
            }
            assert_eq!(incoming_army(n as u8, n), 1);
        }
    }

    #[test]
    fn state_fits() {
        assert!(STATE_END <= STATE + STATE_LEN);
        assert!(TYPED + TYPED_MAX <= TYPED_LEN);
        assert!(MESSAGE + MESSAGE_LEN <= STATE + STATE_LEN);
        assert!(MESSAGE >= PLAYERS + PLAYER_SIZE * MAX_PLAYERS as u32);
    }

    #[test]
    fn names_keep_their_spaces_one_at_a_time_and_none_at_the_ends() {
        assert_eq!(clean_name("  Ann   Lee ", 12), "Ann Lee");
        assert_eq!(clean_name("    ", 12), "");
        assert_eq!(clean_name("Big Pent Room Today", 12), "Big Pent Roo");
        // (the cut never leaves a space at the end)
        assert_eq!(clean_name("ABCDEFGHIJK LMN", 12), "ABCDEFGHIJK");
        assert_eq!(clean_name("Caf\u{e9} \u{1}Bar", 12), "Caf Bar");
        assert_eq!(crate::online_stats::clean("Ann  Lee Jr Third"), "Ann Lee Jr");
        assert_eq!(default_room_name("Ann Lee"), "Ann Lee's room");
        assert_eq!(default_room_name(""), "Player's room");
    }

    #[test]
    fn a_room_made_asks_with_its_name_and_password() {
        let mut mem = vec![0u8; STATE_LEN as usize];
        mem[0x0C] = 1; // CREATE
        mem[0x0D] = 9; // serial
        for (k, c) in b"BIG ROOM".iter().enumerate() {
            mem[0x1C + k] = *c;
        }
        mem[0x29] = 8;
        mem[0x59] = 2;
        mem[0x5A] = b'A';
        mem[0x5B] = b'B';
        let mut read = |at: u32, b: &mut [u8]| {
            let o = (at - STATE) as usize;
            b.copy_from_slice(&mem[o..o + b.len()]);
        };
        let (serial, request) = mailbox::read_request(&mut read, 8).expect("a new request");
        assert_eq!(serial, 9);
        assert_eq!(
            request,
            mailbox::Request::Host {
                password: "AB".into(),
                name: "BIG ROOM".into()
            }
        );
    }

    #[test]
    fn messages_are_kept_whole_or_cut_at_a_word() {
        let long = "A player's link broke while the match was starting and then it did not come back";
        let t = mailbox::message_text(long);
        assert!(t.len() < MESSAGE_LEN as usize, "{t}");
        assert!(t.ends_with(".."), "{t}");
        assert!(!t.trim_end_matches("..").ends_with(char::is_alphabetic) || long.starts_with(t.trim_end_matches("..")));
        assert_eq!(mailbox::message_text("Wrong password."), "Wrong password.");
    }

    #[test]
    fn waiting_names_fit_the_message() {
        let n = |k: usize, len: usize| -> Vec<String> { (0..k).map(|_| "W".repeat(len)).collect() };
        for (k, len) in [(1, 12), (2, 12), (3, 12), (4, 12), (4, 3)] {
            let t = mailbox::waiting_for(&n(k, len));
            assert!(t.len() < MESSAGE_LEN as usize, "{t}");
            assert!(t.starts_with("Waiting for "), "{t}");
        }
        assert_eq!(
            mailbox::waiting_for(&["Ann".into(), "Bo".into()]),
            "Waiting for Ann, Bo"
        );
        assert_eq!(
            mailbox::waiting_for(&n(4, 12)),
            "Waiting for WWWWWWWWWWWW, WWWWWWWWWWWW +2"
        );
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
    fn the_grid_is_a_keyboard() {
        // every character of the alphabet is on the grid exactly once, in four rows of 10, 10, 9 and 7
        let mut seen: Vec<u8> = (0..CODE_ALPHABET.len()).map(grid_char).collect();
        assert_eq!(seen[0], b'1');
        assert_eq!(seen[10], b'Q');
        assert_eq!(seen[20], b'A');
        assert_eq!(seen[29], b'Z');
        seen.sort();
        let mut all = CODE_ALPHABET.to_vec();
        all.sort();
        assert_eq!(seen, all);
        // Down from E (middle 5 half keys in) lands on D, Up from Z lands on A or S, whichever is nearest
        let e = (0..36).find(|&g| grid_char(g) == b'E').unwrap();
        assert_eq!(grid_char(grid_nearest(2, grid_mid(e))), b'S');
        let z = (0..36).find(|&g| grid_char(g) == b'Z').unwrap();
        assert!(matches!(grid_char(grid_nearest(2, grid_mid(z))), b'A' | b'S'));
        // the rows wrap: Left from the first key of a row is its last
        assert_eq!(grid_rc(GRID_START[3]), (3, 0));
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
