//! The player a room's match is waiting for to reconnect, as the session tells the game's presentation: who and the
//! seconds left. A static of the window's process and not console state: it is presentation only, each peer has its
//! own countdown, and rollback must not carry it. The game draws it as a message box over its picture
//! (tangoAW2's `hold_box`).

use std::sync::Mutex;

static HOLD: Mutex<Option<(String, u32)>> = Mutex::new(None);

/// Sets (or, with `None`, clears) the player waited for and the seconds left of their window.
pub fn set(hold: Option<(String, u32)>) {
    *HOLD.lock().unwrap() = hold;
}

/// The player waited for and the seconds left, if the match is on hold.
pub fn get() -> Option<(String, u32)> {
    HOLD.lock().unwrap().clone()
}
