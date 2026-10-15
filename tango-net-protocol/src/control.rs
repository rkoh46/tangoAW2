//! Wire protocol for the reliable control/lobby channel: the `Packet`
//! enum + bincode framing (moved verbatim from the tango bin crate's
//! `net/control/protocol.rs`), the commit/reveal `NegotiatedState` and
//! its commitment construction, and the reveal's chunking constant.
//!
//! `VERSION` is derived from [`crate::PROTOCOL_VERSION`] (the
//! signaling-server reject path sends the full u32; the per-peer Hello
//! sends this u8), so the two can't disagree — but the Hello field is a
//! byte, so the version must stay ≤ 0xff. The assert below turns the
//! eventual overflow into a build failure instead of a silent wrap that
//! would let peers 256 versions apart negotiate as "equal".

use bincode::Options;
use std::sync::LazyLock;

pub const VERSION: u8 = crate::PROTOCOL_VERSION as u8;
const _: () = assert!(
    crate::PROTOCOL_VERSION <= u8::MAX as u32,
    "PROTOCOL_VERSION no longer fits the Hello packet's u8; widen the wire field before bumping past 0xff"
);

/// The reveal stream's chunking: the zstd'd [`NegotiatedState`] travels
/// as [`Chunk`] packets of at most this many payload bytes (the last
/// one smaller), inside the control channel's 64 KiB packet limit.
pub const REVEAL_CHUNK_SIZE: usize = 32 * 1024;

static BINCODE_OPTIONS: LazyLock<
    bincode::config::WithOtherLimit<
        bincode::config::WithOtherIntEncoding<bincode::config::DefaultOptions, bincode::config::VarintEncoding>,
        bincode::config::Bounded,
    >,
> = LazyLock::new(|| {
    bincode::DefaultOptions::new()
        .with_varint_encoding()
        .with_limit(64 * 1024)
});

static STATE_BINCODE_OPTIONS: LazyLock<
    bincode::config::WithOtherIntEncoding<bincode::config::DefaultOptions, bincode::config::VarintEncoding>,
> = LazyLock::new(|| bincode::DefaultOptions::new().with_varint_encoding());

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub enum Packet {
    // Handshake.
    Hello(Hello),

    // Ping.
    Ping(Ping),
    Pong(Pong),

    // Lobby.
    Settings(Settings),
    Commit(Commit),
    Uncommit(Uncommit),
    ChunkStart(ChunkStart),
    Chunk(Chunk),
    StartMatch(StartMatch),

    /// Sent once the sender's pair has finished priming to its link
    /// battle. Neither side advances a tick until it has both primed
    /// itself and seen this, so the two start within a round trip of
    /// each other however far apart their prime times land. See
    /// [`Primed`].
    Primed(Primed),

    // The live match's per-frame Input / EndOfRound / EndOfMatch traffic no
    // longer rides this reliable channel — it's the data plane's job, carried
    // as `data::wire` frames/markers over a separate unreliable channel (see
    // [`crate::data`]). Only lobby/handshake packets remain here, plus:
    /// Deliberate mid-match quit, sent just before teardown. The teardown's
    /// close_notify alone is ambiguous to the peer — its own reconnect
    /// produces the same clean EOF — so without this it burns the short
    /// reconnect path on us; the goodbye lets it end at once.
    /// A peer that predates this variant fails to decode it, which its
    /// mid-match watch ignores as stray traffic (hence no version bump) —
    /// it just falls back to that window.
    Goodbye(Goodbye),

    /// tangoAW2's rooms (the in-game lobby): the room's own conversation, see [`RoomMsg`]. Last in the enum so every
    /// other packet keeps its wire number.
    Room(RoomMsg),
}

/// What the players of a room say to each other on the control channel (tangoAW2): a guest joins the host, the
/// host tells everyone who is there, the guests say READY, and the host starts the match.
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub enum RoomMsg {
    /// Guest to host, first: who I am, the room's password (hashed, see [`room_password_hash`]), and my game.
    Join(RoomJoin),
    /// Host to guest: you are in, at this seat.
    Welcome(RoomRoster),
    /// Host to guest: you are not in.
    Reject(RoomReject),
    /// Host to every guest, when the room changes: who is in it.
    Roster(RoomRoster),
    /// Guest to host: READY, or not.
    Ready(bool),
    /// Host to every guest: the match starts. The host's save follows as `ChunkStart` / `Chunk` packets.
    Start(RoomStart),
    /// Guest to host: I have the start and the save, and am ready to hand over to the match.
    Loaded,
    /// Either: I am leaving.
    Leave,
    /// UNRANKED, both players, first: the two the pool paired each say a random number; the lower one hosts.
    Pool(u64),
    /// Host to every other guest, mid-match, while it waits for the player in `seat` to reconnect (repeated about
    /// once a second): the match is paused, show "Waiting for <name> to reconnect" and hold off any reconnect of
    /// your own.
    Hold(RoomHold),
    /// Host to every other guest: the player in `seat` is back; the match goes on.
    Unhold { seat: u8 },
    /// Host to every other guest: the player in `seat` did not come back in time; the match is over (it is saved
    /// for resuming by whoever can) and the host closes its links next.
    GiveUp { seat: u8, name: String },
}

/// A player the match is waiting for.
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct RoomHold {
    pub seat: u8,
    pub name: String,
    /// Milliseconds left of the reconnect window.
    pub left_ms: u32,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct RoomJoin {
    pub nickname: String,
    pub password: u64,
    pub game_info: Option<GameInfo>,
    /// This player can show the content their game gates ([`SHARED_CONTENT`]); the match has it only when everyone
    /// does.
    pub content: bool,
    /// The ids of the suspended matches this player has saved, so that a room resuming one can tell who is in it.
    pub saves: Vec<u64>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct RoomPlayer {
    pub nickname: String,
    pub ready: bool,
    /// The player's seat in the match (a room resuming a suspended match seats players as they were).
    pub seat: u8,
    pub host: bool,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct RoomRoster {
    /// The receiver's seat (0 is the host).
    pub seat: u8,
    /// Everyone in seat order, the host first.
    pub players: Vec<RoomPlayer>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct RoomReject {
    pub reason: RejectReason,
    /// Words for the player.
    pub text: String,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
pub enum RejectReason {
    WrongPassword,
    Full,
    Started,
    GameMismatch,
    NotTheHost,
    /// A room resuming a saved match, and you are not one of its players (or are already in it).
    NotInMatch,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct RoomStart {
    /// The match's RNG seed and clock (the host's), the same for everyone.
    pub seed: [u8; 16],
    pub ts: u64,
    /// Everyone in seat order.
    pub players: Vec<String>,
    /// The host's save, zstd'd: its length and its commitment hash ([`make_commitment`]), for the chunks that follow.
    pub save_len: u64,
    pub save_hash: [u8; 16],
    pub match_type: (u8, u8),
    /// The match's id (random, the host's choice; a resumed match keeps its own).
    pub match_id: u64,
    /// The seat of the host.
    pub host_seat: u8,
    /// A suspended match being resumed: the payload that follows is `bincode((save, state))` and not the save alone.
    pub resume: Option<ResumeInfo>,
}

/// What a resumed match starts from (the state itself travels in the start's payload).
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct ResumeInfo {
    /// The tick of the saved state in the original match, and its digest.
    pub tick: u32,
    pub digest: u64,
}

/// A room's password as it crosses the wire: not secret (the room's code is its only privacy), just enough to
/// tell a wrong one from the right one.
pub fn room_password_hash(code: &str, password: &str) -> u64 {
    use sha3::digest::{ExtendableOutput, Update, XofReader};
    let mut h = sha3::Shake128::default();
    h.update(b"tangoaw2:room:");
    h.update(code.to_ascii_lowercase().as_bytes());
    h.update(b":");
    h.update(password.to_ascii_lowercase().as_bytes());
    let mut out = [0u8; 8];
    h.finalize_xof().read(&mut out);
    u64::from_le_bytes(out)
}

impl Packet {
    pub fn serialize(&self) -> bincode::Result<Vec<u8>> {
        BINCODE_OPTIONS.serialize(self)
    }

    pub fn deserialize(d: &[u8]) -> bincode::Result<Self> {
        BINCODE_OPTIONS.deserialize(d)
    }
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Hello {
    pub protocol_version: u8,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Commit {
    pub commitment: [u8; 16],
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Uncommit {}

/// Opens a reveal stream: the total byte length of the zstd'd
/// NegotiatedState the Chunk packets that follow will carry. The
/// receiver counts arriving bytes against this — there is no
/// end-of-stream sentinel.
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct ChunkStart {
    pub len: u64,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Chunk {
    pub chunk: Vec<u8>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Ping {
    pub ts: u16,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Pong {
    pub ts: u16,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct PatchInfo {
    pub name: String,
    pub version: semver::Version,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, Default, PartialEq, Eq)]
pub struct GameInfo {
    pub family_and_variant: (String, u8),
    pub patch: Option<PatchInfo>,
    /// How the sender's build simulates this game
    /// (`tango_match::Backend::sim_version`, the same number its
    /// replays are stamped with). Two builds that disagree here would
    /// simulate the same inputs into different matches, so the lobby
    /// refuses the pairing before either side commits.
    ///
    /// This is what keeps a change to one game's netplay from costing
    /// every game a [`crate::PROTOCOL_VERSION`] bump: the protocol
    /// version gates the wire, this gates the simulation, and only the
    /// games that actually changed are turned away.
    pub sim_version: u32,
}

/// Bit 7 of a player's match subtype ([`Settings::match_type`]) is not part
/// of the match type: it says this player can show content their game gates
/// on (tangoAW2: the Black Crystal and Black Obelisk, whose art each player
/// imports from their own Dual Strike ROM). The lobby ignores it when it
/// compares match types, and the match terms keep it only when both
/// players set it, so both peers and the replay agree.
pub const SHARED_CONTENT: u8 = 0x80;

/// Bit 6 of a player's match subtype is not part of the match type either:
/// it says this player made the room they met in (tangoAW2's in-game
/// lobby). When exactly one of the two sets it, that player takes seat 0
/// (the room's host drives its menus); otherwise seats are drawn as ever.
/// The lobby ignores it when it compares match types, and the match terms
/// drop it.
pub const ROOM_HOST: u8 = 0x40;

/// Bit 2 of an UNRANKED match's subtype (tangoAW2): the match's map is the guest's proposal (clear: the host's).
/// The host draws it from the match seed when it starts the match, so both peers and the replay have the same.
pub const UNRANKED_PICK_GUEST: u8 = 0x04;

/// The local player's seat when [`ROOM_HOST`] decides it: `Some(0)` for the
/// room's host, `Some(1)` for its guest, `None` when it does not (neither
/// or both set it).
pub fn room_host_seat(local_subtype: u8, remote_subtype: u8) -> Option<u8> {
    match (local_subtype & ROOM_HOST != 0, remote_subtype & ROOM_HOST != 0) {
        (true, false) => Some(0),
        (false, true) => Some(1),
        _ => None,
    }
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, Default, PartialEq, Eq)]
pub struct Settings {
    pub nickname: String,
    pub match_type: (u8, u8),
    pub game_info: Option<GameInfo>,
    pub blind_setup: bool,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct StartMatch {}

/// "My pair is primed and I am ready to tick."
///
/// Priming is a pure function of ROM/save/rtc, so both peers walk to the
/// same state — but they take as long as their own hardware takes, and
/// nothing else on the wire marks the boundary. Without this the peer
/// that finishes first starts advancing alone, piling its own inputs up
/// with nothing to match them against, and trips the input-queue stall
/// watchdog into a spurious mid-match reconnect while the other side is
/// still walking menus.
#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Primed {}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct Goodbye {}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct NegotiatedState {
    pub nonce: [u8; 16],
    /// Sender's wall clock at commit time, milliseconds since the unix epoch.
    /// The offerer's value becomes the match clock: the fixed time every core
    /// on both sides pins its cart RTC to, and the `ts` recorded in the replay
    /// metadata — so RTC-reading games (exe45) run deterministically in PvP
    /// and on playback.
    pub ts: u64,
    pub save_data: Vec<u8>,
}

impl NegotiatedState {
    pub fn serialize(&self) -> bincode::Result<Vec<u8>> {
        STATE_BINCODE_OPTIONS.serialize(self)
    }

    pub fn deserialize(d: &[u8]) -> bincode::Result<Self> {
        STATE_BINCODE_OPTIONS.deserialize(d)
    }
}

/// `Shake128("tango:lobby:" || buf)` truncated to 16 bytes — the commitment
/// hash over the compressed reveal. Shared by the lobby challenge flow and the
/// peer-to-peer reveal verification so both ends agree on the construction.
pub fn make_commitment(buf: &[u8]) -> [u8; 16] {
    use sha3::digest::{ExtendableOutput, Update, XofReader};
    let mut h = sha3::Shake128::default();
    h.update(b"tango:lobby:");
    h.update(buf);
    let mut out = [0u8; 16];
    h.finalize_xof().read(&mut out);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_room_host_takes_seat_0() {
        assert_eq!(room_host_seat(ROOM_HOST | 1, 1), Some(0));
        assert_eq!(room_host_seat(SHARED_CONTENT | 1, ROOM_HOST), Some(1));
        assert_eq!(room_host_seat(0, 0), None);
        assert_eq!(room_host_seat(ROOM_HOST, ROOM_HOST), None);
    }
}
