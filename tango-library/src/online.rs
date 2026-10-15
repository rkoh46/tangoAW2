//! tangoAW2: the in-game lobby's mailbox, for the host app (see
//! `tango_gamesupport_aw2::online`): what the game asks for, and what the app
//! answers, over the app's own reads and writes of the running console's
//! memory. Without the game compiled in, nothing is ever asked.

#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::online::mailbox::{boot_to_lobby, link_code, new_code, Request};
#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::online::{Status, HOST, MAX_PLAYERS, ONLINE_MATCH, YOU};

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
