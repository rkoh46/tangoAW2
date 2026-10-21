//! The user's game library and its persistence, frontend-agnostic.
//!
//! * [`game`]: the registry of supported games everything else is keyed
//!   by, and the game-name localizer.
//! * [`scanner`]: the shared fingerprint-gated rescan machinery the
//!   content scans below build on.
//! * [`rom`] / [`save`] / [`patch`] / [`replays`]: one module per kind of
//!   content the library folders hold.
//! * [`catalog`]: the four scanners bundled, with the rescan pipeline
//!   and the preparation helpers that read them.
//! * [`config`]: the persisted settings model.
//!
//! The optional `ui` feature attaches save editors to registered games.
//! Core library operations use no UI toolkit and never access the
//! filesystem or the network directly: [`storage::Storage`] and
//! [`http::Http`] are the two seams, and a frontend supplies both. The
//! `native` feature (on by default) provides `std::fs` and reqwest
//! implementations; a browser build turns it off and hands in IndexedDB and
//! `fetch` instead.

pub mod catalog;
pub mod config;
pub mod game;
pub mod http;
pub mod lang;
pub mod loadout;
pub mod marker;
pub mod online;
#[cfg(feature = "gamesupport-aw2")]
pub use tango_gamesupport_aw2::ai_debug;
pub mod patch;
pub mod replays;
pub mod rom;
pub mod save;
pub mod scanner;
pub mod stats;
pub mod storage;

pub use catalog::Catalog;

/// This player's [`SHARED_CONTENT`](tango_net_protocol::control::SHARED_CONTENT)
/// bit for their match subtype: set when they can show the content their
/// game gates on (tangoAW2: the Dual Strike pack imported).
pub fn shared_content_flag() -> u8 {
    #[cfg(feature = "gamesupport-aw2")]
    if tango_gamesupport_aw2::ds_pack::pack().is_some() {
        return tango_net_protocol::control::SHARED_CONTENT;
    }
    0
}
/// tangoAW2: whether the Dual Strike pack is imported (Dual Strike tilt, a
/// display setting, is offered only then).
pub fn ds_pack_present() -> bool {
    #[cfg(feature = "gamesupport-aw2")]
    if tango_gamesupport_aw2::ds_pack::pack().is_some() {
        return true;
    }
    false
}

/// tangoAW2: the Dual Strike map graphics setting (see
/// `tango_gamesupport_aw2::ds_graphics`).
pub fn set_ds_graphics(on: bool) {
    #[cfg(feature = "gamesupport-aw2")]
    tango_gamesupport_aw2::ds_graphics::set_enabled(on);
    let _ = on;
}

/// tangoAW2: the Dual Strike tilt display setting (see
/// `tango_gamesupport_aw2::ds_tilt`).
pub fn set_ds_tilt(on: bool) {
    #[cfg(feature = "gamesupport-aw2")]
    tango_gamesupport_aw2::ds_tilt::set_enabled(on);
    let _ = on;
}

/// tangoAW2: how far the tilted map leans (0 Dual Strike's, 1 lighter).
pub fn set_ds_tilt_amount(amount: u8) {
    #[cfg(feature = "gamesupport-aw2")]
    tango_gamesupport_aw2::ds_tilt::set_amount(amount);
    let _ = amount;
}

/// tangoAW2: how many times the console's size the tilted map is drawn (1 to 8).
pub fn set_ds_tilt_scale(scale: u8) {
    #[cfg(feature = "gamesupport-aw2")]
    tango_gamesupport_aw2::ds_tilt::set_hires_scale(scale);
    let _ = scale;
}

/// tangoAW2: log the tilt's cost every 120 pictures (hidden `ds_tilt_log` setting).
pub fn set_ds_tilt_log(on: bool) {
    #[cfg(feature = "gamesupport-aw2")]
    tango_gamesupport_aw2::ds_tilt::set_timing_log(on);
    let _ = on;
}

/// tangoAW2: the Dual Strike pack in use is a saved one from an older
/// version and the .nds was not in the ROMs folder to rebuild it (the
/// play tab says so).
pub fn ds_pack_outdated() -> bool {
    #[cfg(feature = "gamesupport-aw2")]
    if tango_gamesupport_aw2::ds_pack::outdated() {
        return true;
    }
    false
}
pub use storage::Storage;

#[cfg(test)]
mod test_support;
