//! Suspended matches (tangoAW2): a room's match that was cut short (a player's connection dropped for good) and is
//! kept by each remaining player to be resumed later.
//!
//! The shared console's state is checkpointed every [`CHECKPOINT_EVERY`] ticks, once the tick is settled (every
//! player's input for it, and everything before it, is in, so every peer holds the same state there). When the match
//! ends by a disconnect the newest few checkpoints are handed to the host app, which stores them as a
//! [`SuspendedMatch`]. A resumed match starts from one checkpoint (the resuming host's newest): the room ships it to
//! everyone, so every peer starts from the very same bytes.

/// A checkpoint is taken at every tick that is a multiple of this (half a second).
pub const CHECKPOINT_EVERY: u32 = 30;
/// How many of the newest settled checkpoints a match keeps in memory, and a suspended match stores.
pub const CHECKPOINTS_KEPT: usize = 12;
pub const CHECKPOINTS_STORED: usize = 3;

/// What the game says about a state, for the list of saved matches.
#[derive(Clone, Debug, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct StateInfo {
    pub map: String,
    pub day: u32,
    pub rules: String,
}

/// A console's state as bytes: the engine's own save-state image, and a digest of what matters in it (the same on
/// every peer at the same tick, which the raw bytes are not: the emulator leaves reserved parts unwritten).
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct StateImage {
    pub state: Vec<u8>,
    pub digest: u64,
    pub info: Option<StateInfo>,
}

/// A settled state at `tick` (the number of ticks played from the start of the match, or of the resumed state).
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Checkpoint {
    pub tick: u32,
    pub image: StateImage,
}

/// A match kept for resuming, as one player stores it.
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct SuspendedMatch {
    pub version: u32,
    /// Random, the host's choice when the room started; a resumed match keeps it.
    pub match_id: u64,
    /// How the build that played it simulates the game: a state only resumes on the same simulation.
    pub sim_version: u32,
    /// Everyone's gamertag in seat order.
    pub players: Vec<String>,
    /// The seat this player had.
    pub seat: u8,
    /// Who disconnected.
    pub disconnected: String,
    /// When it was saved (seconds since the unix epoch).
    pub saved_at: u64,
    /// The match clock the console was booted with.
    pub match_ts: u64,
    pub match_type: (u8, u8),
    /// The save (SRAM image) the match ran on.
    pub save: Vec<u8>,
    /// The newest checkpoints, oldest first.
    pub checkpoints: Vec<Checkpoint>,
}

pub const SUSPENDED_VERSION: u32 = 1;

impl SuspendedMatch {
    /// The newest checkpoint.
    pub fn newest(&self) -> Option<&Checkpoint> {
        self.checkpoints.last()
    }

    /// What the newest state shows.
    pub fn info(&self) -> StateInfo {
        self.newest().and_then(|c| c.image.info.clone()).unwrap_or_default()
    }
}
