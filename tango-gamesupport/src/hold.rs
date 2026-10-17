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

static MIGRATION: Mutex<Option<(String, bool)>> = Mutex::new(None);

/// Sets (or clears) the host migration in progress: the new host's gamertag, and whether that is this player. The
/// game draws "Host left. <name> is hosting now... reconnecting" as a message box (tangoAW2's `hold_box`).
pub fn set_migration(m: Option<(String, bool)>) {
    *MIGRATION.lock().unwrap() = m;
}

/// The host migration in progress, if any.
pub fn migration() -> Option<(String, bool)> {
    MIGRATION.lock().unwrap().clone()
}

static HOST_WAIT: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// The player waited for is the room's host and the room goes on without it if it does not come back (instead of the match
/// being saved for RESUME): the box says so.
pub fn set_host_wait(on: bool) {
    HOST_WAIT.store(on, std::sync::atomic::Ordering::Relaxed);
}

pub fn host_wait() -> bool {
    HOST_WAIT.load(std::sync::atomic::Ordering::Relaxed)
}
