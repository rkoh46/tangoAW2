//! tangoAW2: the in-game lobby's mailbox, for the host app (see
//! `tango_gamesupport_aw2::online`): what the game asks for, and what the app
//! answers, over the app's own reads and writes of the running console's
//! memory. Without the game compiled in, nothing is ever asked.

#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::online::mailbox::{boot_to_lobby, link_code, new_code, Request, SavedRow};
#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::online_browse::{Net as BrowseNet, Row as BrowseRow};
#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::online::{Status, CODE_ALPHABET, HOST, MAX_PLAYERS, ONLINE_MATCH, UNRANKED_MATCH, UNRANKED_PICK_GUEST, YOU};

/// The match type a room made in the in-game lobby is played as.
#[cfg(feature = "gamesupport-aw2")]
pub const MATCH_TYPE: (u8, u8) = (0, ONLINE_MATCH);

/// The game's request, if one is new since `seen` (its serial).
#[cfg(feature = "gamesupport-aw2")]
pub fn read_request(read: &mut dyn FnMut(u32, &mut [u8]), seen: u8) -> Option<(u8, Request)> {
    tango_gamesupport_aw2::online::mailbox::read_request(read, seen)
}

/// The serial of the game's last request.
#[cfg(feature = "gamesupport-aw2")]
pub fn serial(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
    tango_gamesupport_aw2::online::mailbox::serial(read)
}

/// Which page the in-game lobby is on (0 the ONLINE menu, 1 LOBBY, 2 a room made, 3 a code being typed, 4 a room
/// joined, 5 a password being typed).
#[cfg(feature = "gamesupport-aw2")]
pub fn level(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
    tango_gamesupport_aw2::online::mailbox::level(read)
}

#[cfg(feature = "gamesupport-aw2")]
pub fn write_status(write: &mut dyn FnMut(u32, &[u8]), status: Status, message: &str) {
    tango_gamesupport_aw2::online::mailbox::write_status(write, status, message)
}

/// The list of suspended matches the RESUME page shows.
#[cfg(feature = "gamesupport-aw2")]
pub fn write_saved(write: &mut dyn FnMut(u32, &[u8]), rows: &[SavedRow]) {
    tango_gamesupport_aw2::online::mailbox::write_saved(write, rows)
}

/// How many saved matches the game is showing now.
#[cfg(feature = "gamesupport-aw2")]
pub fn saved_count(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
    tango_gamesupport_aw2::online::mailbox::saved_count(read)
}

/// The note on the LOBBY menu when the game comes back from a match (longer than a status message).
#[cfg(feature = "gamesupport-aw2")]
pub fn write_note(write: &mut dyn FnMut(u32, &[u8]), text: &str) {
    tango_gamesupport_aw2::online::mailbox::write_note(write, text)
}

#[cfg(feature = "gamesupport-aw2")]
pub fn write_room(write: &mut dyn FnMut(u32, &[u8]), code: &str) {
    tango_gamesupport_aw2::online::mailbox::write_room(write, code)
}

/// One player's slot on the room's page: (name, ready, [`HOST`] / [`YOU`] flags), or an open slot.
#[cfg(feature = "gamesupport-aw2")]
pub fn write_player(write: &mut dyn FnMut(u32, &[u8]), slot: usize, player: Option<(&str, bool, u8)>) {
    tango_gamesupport_aw2::online::mailbox::write_player(write, slot, player)
}

/// Keyboard typing for a code or password being typed (letters, 8 rub out, 13 OK, 27 back). False when the lobby
/// takes no typing now.
#[cfg(feature = "gamesupport-aw2")]
pub fn type_chars(read: &mut dyn FnMut(u32, &mut [u8]), write: &mut dyn FnMut(u32, &[u8]), chars: &[u8]) -> bool {
    tango_gamesupport_aw2::online::mailbox::type_chars(read, write, chars)
}

/// A test aid's question of the console (see the app's `debug_aids`).
#[cfg(feature = "gamesupport-aw2")]
pub fn condition(read: &mut dyn FnMut(u32, &mut [u8]), cond: &str) -> bool {
    tango_gamesupport_aw2::online::mailbox::condition(read, cond)
}

#[cfg(feature = "gamesupport-aw2")]
pub fn status(read: &mut dyn FnMut(u32, &mut [u8])) -> u8 {
    tango_gamesupport_aw2::online::mailbox::status(read)
}

#[cfg(feature = "gamesupport-aw2")]
pub fn players(read: &mut dyn FnMut(u32, &mut [u8])) -> Vec<(bool, u8)> {
    tango_gamesupport_aw2::online::mailbox::players(read)
}

/// What the console showed on its last tick (see the game's `online::probe`).
#[cfg(feature = "gamesupport-aw2")]
pub fn probe_bits() -> u64 {
    tango_gamesupport_aw2::online::probe::bits()
}

/// Who is who in the room (gamertags in seat order, and this peer's seat), for the game's pictures.
#[cfg(feature = "gamesupport-aw2")]
pub fn set_room(names: Vec<String>, local_seat: usize) {
    tango_gamesupport_aw2::online::set_room(names, local_seat)
}

/// The room's player count, the name of a seat and this peer's seat (for the status bar).
pub fn room_players() -> usize {
    tango_gamesupport_aw2::online::room_players()
}
pub fn room_name(seat: usize) -> String {
    tango_gamesupport_aw2::online::room_name(seat)
}
pub fn room_local_seat() -> usize {
    tango_gamesupport_aw2::online::room_local_seat()
}

#[cfg(feature = "gamesupport-aw2")]
pub fn list_debug() -> u64 {
    tango_gamesupport_aw2::online::probe::LIST_DEBUG.load(std::sync::atomic::Ordering::Relaxed)
}

#[cfg(feature = "gamesupport-aw2")]
pub fn map_debug() -> u64 {
    tango_gamesupport_aw2::online::probe::MAP_DEBUG.load(std::sync::atomic::Ordering::Relaxed)
}

/// The lobby browser's rows and how the search stands, for the game's page (the app's half of
/// `tango_gamesupport_aw2::online_browse`).
#[cfg(feature = "gamesupport-aw2")]
pub fn write_browse(write: &mut dyn FnMut(u32, &[u8]), rows: &[BrowseRow], net: BrowseNet, version: &str) {
    tango_gamesupport_aw2::online_browse::mailbox::write(write, rows, net, version)
}
