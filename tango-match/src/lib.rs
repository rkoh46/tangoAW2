//! The engine-neutral seam every Tango netplay match speaks.
//!
//! A match is two consoles linked together, simulated locally, with the
//! pair as the rollback unit — but *which* consoles, and what links
//! them, is the engine's business. The GBA games run on mgba over an
//! emulated link cable (`tango-backend-mgba`); BN5 Double Team DS runs
//! on melonDS over emulated local wireless (`tango-backend-melonds`).
//!
//! Nothing here names an emulator, so a game pulls in exactly the engine
//! it needs and no other.
//!
//! - [`link`]: [`Link`] — the linked pair — and [`Side`], one console
//!   of any boot; plus [`Backend`], what a `Game` registration holds.
//! - [`audio`]: the ring a simulation pushes its consoles' sound into
//!   and a host's device callback plays out of.
//! - [`engine`]: [`Match`], the rollback loop over any [`Link`] and the
//!   unified session surface a host drives.
//! - [`solo`]: [`Solo`], the single-console ride over any [`Console`].
//! - [`replay`]: [`ReplaySet`], playback + the statistics pass over any
//!   [`Link`] — an engine contributes only the boot.
//! - [`seek`]: requesting a seek and the chase that walks a playback
//!   between its captures to get there.
//! - [`analysis`]: folding per-tick samples and telemetry events into
//!   match statistics, live or offline.
//! - [`screens`]: re-arranging a multi-screen composition for display
//!   or export.
//! - [`input`]: [`HostInput`], the joypad word plus stylus a host
//!   collects for its player.
//! - [`throttler`]: the clock-sync governor both engines pace with.
//! - [`keys`]: the joypad bit vocabulary.

pub mod analysis;
pub mod audio;
pub mod engine;
#[cfg(target_arch = "wasm32")]
pub mod hosting;
pub mod input;
pub mod link;
pub mod replay;
pub mod screens;
pub mod seek;
pub mod solo;
pub mod suspend;
pub mod telemetry;
pub mod throttler;

pub use audio::{AudioIn, AudioOut};
pub use engine::{others_input, seat_inputs, Advance, Match, MAX_SEATS};
pub use input::HostInput;
pub use link::{Backend, Link, PeerRom, Screen, ScreenLayout, SessionMode, Side, Snapshot, StartConfig};
pub use replay::{BootedReplay, Capture, LiveFrames, Playback, Replay, ReplayBoot, ReplayConfig, ReplaySet, StatsPass};
pub use seek::SeekStep;
pub use solo::{Console, Solo, SoloConfig};
pub use suspend::{Checkpoint, StateImage, StateInfo, SuspendedMatch};

/// The clock-sync governor: feed it `skew()` + `speculation_balance()`
/// each frame and shave the returned fps off the tick rate. Shared by
/// every engine, so it lives here rather than in a backend.
pub use throttler::Throttler;

/// Why a match failed to start or advance.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// Priming never reached a link battle within the tick bound — a
    /// wedged menu walk, or the wrong ROM/save for the primer.
    #[error("priming did not reach a link battle within {0} ticks")]
    PrimeTimeout(u32),

    /// The caller's cancel flag flipped mid-simulation.
    #[error("cancelled")]
    Cancelled,

    /// Whatever the engine underneath reported. Boxed because every
    /// engine has its own error type and this crate refuses to name
    /// any of them.
    #[error(transparent)]
    Backend(Box<dyn std::error::Error + Send + Sync>),

    /// A ride this game's engine doesn't offer — a netplay-only game
    /// asked for single-player, say. Not a failure: the host reports
    /// the option isn't available and carries on.
    #[error("{0}")]
    Unsupported(&'static str),
}

/// The input bits a match speaks, engine-neutral.
///
/// This is the GBA layout, which the DS extends with X and Y — so one
/// vocabulary covers both consoles and hosts need no emulator
/// dependency to name a button.
pub mod keys {
    pub const A: u32 = 1 << 0;
    pub const B: u32 = 1 << 1;
    pub const SELECT: u32 = 1 << 2;
    pub const START: u32 = 1 << 3;
    pub const RIGHT: u32 = 1 << 4;
    pub const LEFT: u32 = 1 << 5;
    pub const UP: u32 = 1 << 6;
    pub const DOWN: u32 = 1 << 7;
    pub const R: u32 = 1 << 8;
    pub const L: u32 = 1 << 9;
    /// DS only.
    pub const X: u32 = 1 << 10;
    /// DS only.
    pub const Y: u32 = 1 << 11;

    /// DS only, and the one bit here that is not a button: white noise
    /// held on the console's microphone.
    ///
    /// It rides the pad word because everything that has to carry it
    /// already carries that word and nothing else — the netplay wire,
    /// the rollback engine's input queues and its prediction, the replay
    /// stream. A mic channel of its own would be the same bit spelled
    /// four more times, and every one of those places would have to be
    /// taught that a console can be blown into.
    pub const MIC: u32 = 1 << 12;

    /// Every named bit — the widest input this vocabulary can express,
    /// which is also what the netplay wire's input element carries.
    pub const MASK: u32 = 0x1fff;

    /// A room's host speaks to the consoles of the room in the pad words it joins (host migration, tangoAW2): a word with
    /// all four directions down at once, which no pad makes, is a command and not keys. The session strips that shape from
    /// every real word ([`strip`]), so only the host's own joining makes one.
    pub mod command {
        use super::{A, B, DOWN, L, LEFT, R, RIGHT, START, UP};

        /// The four directions together.
        pub const BITS: u32 = UP | DOWN | LEFT | RIGHT;
        /// The seat that sends it is the room's host from now on.
        pub const HOST: u32 = BITS | A;
        /// Play the seat that sends it: the player is gone, its armies yield when their turns come.
        pub const YIELD: u32 = BITS | B;

        /// A seat's choice of a map, made in private on its own window (tangoAW2's simultaneous map picks): the choice's two halves
        /// (an id of up to ten bits) follow each other in the seat's own words, five bits each, in the keys that are not
        /// directions: A, B, START, R and L. The word is [`BITS`] and SELECT with the five bits. Unlike the host's commands, a guest
        /// sends these itself: the host's session lets them through ([`strip_unless_pick`]).
        pub const PICK: u32 = BITS | super::SELECT;

        /// The word that carries `half` (five bits) of a pick.
        pub fn pick_word(half: u8) -> u32 {
            let h = (half & 0x1F) as u32;
            PICK | (h & 1) * A | (h >> 1 & 1) * B | (h >> 2 & 1) * START | (h >> 3 & 1) * R | (h >> 4 & 1) * L
        }

        /// Whether a word carries half of a pick.
        pub fn is_pick(word: u32) -> bool {
            word & PICK == PICK
        }

        /// The five bits a pick word carries.
        pub fn pick_half(word: u32) -> u8 {
            ((word & A) | (word & B) | (word & START) >> 1 | (word & R) >> 5 | (word & L) >> 5) as u8
        }

        /// The two words of a pick of the map `id` (below 1024), high half first.
        pub fn pick_words(id: u16) -> [u32; 2] {
            [pick_word((id >> 5 & 0x1F) as u8), pick_word((id & 0x1F) as u8)]
        }

        /// Whether a word is a command.
        pub fn is(word: u32) -> bool {
            word & BITS == BITS
        }

        /// A real word that would read as a command (a keyboard can press anything): one direction is let go.
        pub fn strip(word: u32) -> u32 {
            if is(word) {
                word & !RIGHT
            } else {
                word
            }
        }

        /// [`strip`], but a word that carries half of a pick is a guest's own and stays (a session reads its guests' words with this).
        pub fn strip_unless_pick(word: u32) -> u32 {
            if is_pick(word) {
                word
            } else {
                strip(word)
            }
        }
    }
}

#[cfg(test)]
mod pick_command_tests {
    use super::keys::command::*;

    #[test]
    fn a_pick_is_two_words_and_round_trips_for_every_map_id() {
        for id in 0u16..1024 {
            let [hi, lo] = pick_words(id);
            assert!(is(hi) && is(lo) && is_pick(hi) && is_pick(lo));
            assert_ne!(hi & super::keys::MASK, HOST);
            assert_eq!(((pick_half(hi) as u16) << 5) | pick_half(lo) as u16, id, "{id}");
            // (the words survive the session's reading of a guest's words, and not the stripping of a real pad's)
            assert_eq!(strip_unless_pick(hi), hi);
            assert_ne!(strip(hi), hi);
        }
    }

    #[test]
    fn host_and_yield_are_not_picks_and_are_still_stripped_from_a_guest() {
        assert!(!is_pick(HOST) && !is_pick(YIELD));
        assert_eq!(strip_unless_pick(HOST), strip(HOST));
        assert_eq!(strip_unless_pick(YIELD), strip(YIELD));
        // a plain word is untouched
        assert_eq!(strip_unless_pick(0x155), 0x155);
    }
}
