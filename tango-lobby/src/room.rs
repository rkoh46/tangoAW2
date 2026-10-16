//! tangoAW2's rooms: up to five players, one host.
//!
//! A room is made by a host and joined by guests with its code (the room's matchmaking session id is the code, see
//! [`room_session`]); the matchmaking server pairs two clients at a time, so the host keeps one dial open: when a
//! guest has come through it dials again for the next. Every guest has a link of its own to the host (a star): the
//! host is the one who knows everyone, the guests never meet. In the match the host's one input for each guest is
//! the others' together (`tango_match::HostInput::extra`), see `tango_session::pvp`.
//!
//! The conversation on the control channel is [`RoomMsg`]: a guest says who it is (`Join`), the host welcomes it
//! with its seat or turns it away (a wrong password, a full room, another game version), tells everyone who is
//! there (`Roster`) whenever that changes, guests say READY, and the host starts the match: its RNG seed and clock
//! and its save (the match runs on the host's save: seat 0's), which every guest answers with `Loaded`. Then each
//! link is handed over, as it is, to the match ([`RoomMatch`]).
//!
//! A [`Room`] is a handle on all this, polled by the app (no events to route): [`Room::view`], [`Room::set_ready`],
//! [`Room::start`], [`Room::leave`], and [`Room::take_match`] once the match is ready.

use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio_util::sync::CancellationToken;

use tango_net::channel::Channels;
use tango_net::link::{LinkParts, ReconnectRecipe};
use tango_net_protocol::control::{
    make_commitment, room_password_hash, Packet, RejectReason, RoomJoin, RoomMsg, RoomPlayer, RoomReject, RoomRoster,
    RoomStart,
};

/// The most players a room holds.
pub const MAX_PLAYERS: usize = 5;

/// How long a guest keeps looking for the host before saying there is no such room.
const GUEST_DEADLINE: Duration = Duration::from_secs(25);
/// How long a host or guest waits for the other's first words after the connection came up.
const FIRST_WORDS: Duration = Duration::from_secs(8);
/// How long the host waits for every guest to have its save.
const LOAD_DEADLINE: Duration = Duration::from_secs(40);
/// A silent link this long is a dead one.
const SILENCE: Duration = Duration::from_secs(15);

/// The matchmaking session id of a room: its code (the password is inside the conversation, so that a wrong one can
/// be told apart from a room that is not there).
pub fn room_session(code: &str) -> String {
    format!("tangoaw2-room-{}", code.to_ascii_lowercase())
}

// UNRANKED's discovery (a child module: it works on the room's state).
#[path = "unranked.rs"]
pub mod unranked;

/// What a room needs to be made or joined.
#[derive(Clone)]
pub struct RoomParams {
    pub endpoint: String,
    pub use_relay: Option<bool>,
    pub code: String,
    pub password: String,
    pub nickname: String,
    pub game_info: Option<tango_net_protocol::control::GameInfo>,
    /// The match type's subtype (tangoAW2: Versus, the room's match), the same for everyone.
    pub match_type: (u8, u8),
    /// The host's save (SRAM image): the match runs on it. Unused by guests.
    pub save: Vec<u8>,
    /// This player can show the content the game gates (tangoAW2: Dual Strike's, from their own ROM): the match
    /// has it only when everyone can.
    pub content: bool,
    /// The ids of the suspended matches this player has saved (a guest says them to the host when joining).
    pub saves: Vec<u64>,
    /// A room made to resume a suspended match (the host's).
    pub resume: Option<ResumeParams>,
}

/// A suspended match a room is made to resume (the host's copy of it).
#[derive(Clone)]
pub struct ResumeParams {
    pub match_id: u64,
    /// Everyone's gamertag in seat order, as saved.
    pub players: Vec<String>,
    /// The seat the host had.
    pub seat: usize,
    /// The state to start from: its tick in the original match, its digest, the emulator's bytes.
    pub tick: u32,
    pub digest: u64,
    pub state: Vec<u8>,
    /// The match clock and type the console was started with, and the save it ran on.
    pub match_ts: u64,
    pub match_type: (u8, u8),
    pub save: Vec<u8>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RoomPhase {
    /// Dialling (a host before the first guest; a guest looking for the host).
    Connecting,
    /// In the room.
    Open,
    /// The match is being started.
    Starting,
    /// The match is ready to be taken ([`Room::take_match`]).
    Ready,
    /// It did not work; [`RoomView::message`] says why.
    Failed,
    Closed,
}

pub use tango_net::channel::Kind as LinkKind;

/// How a peer is reached and how long a round trip takes, for the room page's diagnostic line. Never an address.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct LinkView {
    /// Direct, through the TURN relay, or `None` when it can't be told.
    pub kind: Option<LinkKind>,
    /// The latest round trip over the room's link, in ms, once a pong has come back.
    pub rtt_ms: Option<u32>,
}

impl LinkView {
    /// Fold a new round-trip sample in (a quarter of the way: steady, but it follows a change within seconds).
    fn sample(&mut self, rtt: Duration) {
        let ms = rtt.as_millis().min(60_000) as u32;
        self.rtt_ms = Some(match self.rtt_ms {
            Some(old) => (old * 3 + ms) / 4,
            None => ms,
        });
    }

    fn of(peer_conn: &tango_net::channel::PeerConnection) -> Self {
        Self {
            kind: tango_net::channel::Channels::kind(peer_conn),
            rtt_ms: None,
        }
    }
}

#[derive(Clone, Debug)]
pub struct PlayerView {
    /// The host's link to this player (a guest's own link to the host is on the host's row); `None` on your own
    /// row and for players you have no link to.
    pub link: Option<LinkView>,
    pub nickname: String,
    pub ready: bool,
    pub host: bool,
    pub you: bool,
}

#[derive(Clone, Debug)]
pub struct RoomView {
    pub phase: RoomPhase,
    /// In seat order, the host first. A guest not yet welcomed sees just a host placeholder.
    pub players: Vec<PlayerView>,
    pub message: String,
    /// A guest: welcomed by the host.
    pub joined: bool,
    /// Every guest is READY (and there is one, and in a room resuming a match every player of it is here): the host
    /// may start.
    pub all_ready: bool,
    /// A room resuming a suspended match: the players of it who are not in the room yet.
    pub waiting_for: Vec<String>,
    pub resuming: bool,
}

/// A room's match, ready to be played: everything the session needs from the lobby.
pub struct RoomMatch {
    pub is_host: bool,
    /// This peer's seat (the host is 0, a guest its place in the roster).
    pub seat: usize,
    /// Everyone's gamertag in seat order.
    pub players: Vec<String>,
    pub seed: [u8; 16],
    /// The match clock, milliseconds since the unix epoch.
    pub ts: u64,
    /// The host's save: the console boots from it on every peer.
    pub host_save: Vec<u8>,
    pub match_type: (u8, u8),
    pub code: String,
    /// The host: a link to each guest in seat order (1..). A guest: the link to the host.
    pub links: Vec<LinkParts>,
    /// The host's seat (0, unless the room resumes a match the host was not the first seat of).
    pub host_seat: usize,
    /// The match's id (random; a resumed match keeps its own).
    pub match_id: u64,
    /// A suspended match being resumed: the console state it starts from.
    pub resume_state: Option<Vec<u8>>,
}

impl RoomMatch {
    /// The match as the session's first-link handoff (`local` and `remote` settings are what the game library
    /// resolves the games from) and the links after the first (a room's host has one to each guest).
    pub fn into_pre_match(
        mut self,
        local: tango_net_protocol::control::Settings,
        remote: tango_net_protocol::control::Settings,
    ) -> (tango_net::handoff::PreMatchData, Vec<LinkParts>) {
        let first = self.links.remove(0);
        (
            tango_net::handoff::PreMatchData {
                terms: tango_net::handoff::MatchTerms {
                    is_offerer: self.is_host,
                    rng_seed: self.seed,
                    match_ts: self.ts,
                    local_save_data: self.host_save.clone(),
                    remote_save_data: self.host_save,
                    local_settings: local,
                    remote_settings: remote,
                    link_code: self.code,
                    match_type: self.match_type,
                },
                link_parts: first,
            },
            self.links,
        )
    }
}

impl std::fmt::Debug for RoomMatch {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("RoomMatch")
            .field("seat", &self.seat)
            .field("players", &self.players)
            .finish_non_exhaustive()
    }
}

/// What a host keeps of a guest's connection until the match takes it over.
struct Parts {
    in_match: (tango_net::data::Sender, tango_net::data::Receiver),
    peer_conn: tango_net::channel::PeerConnection,
    local_fp: Vec<u8>,
    peer_fp: Vec<u8>,
}

struct HostPeer {
    id: u64,
    nickname: String,
    /// Its seat in a room resuming a match (otherwise by order of joining).
    seat: Option<u8>,
    ready: bool,
    loaded: bool,
    content: bool,
    link: LinkView,
    sender: Arc<tokio::sync::Mutex<tango_net::Sender>>,
    /// Fired to make the peer's task give its control receiver back for the match.
    handoff: CancellationToken,
    receiver_back: Option<tokio::sync::oneshot::Receiver<tango_net::Receiver>>,
    parts: Option<Parts>,
}

struct Inner {
    host: bool,
    /// UNRANKED: a room of two made by the pool's pairing (see [`Room::unranked`]).
    unranked: bool,
    params: RoomParams,
    phase: RoomPhase,
    message: String,
    // The host's side.
    peers: Vec<HostPeer>,
    next_id: u64,
    // A guest's side.
    welcomed: bool,
    roster: Vec<RoomPlayer>,
    my_seat: usize,
    my_ready: bool,
    to_host: Option<tokio::sync::mpsc::UnboundedSender<RoomMsg>>,
    /// A guest's link to the host.
    host_link: LinkView,
    // Both.
    matched: Option<RoomMatch>,
    started: bool,
    /// The host's open dial for the next guest; stopped when the match starts.
    dial: CancellationToken,
}

/// A handle on a room. Cheap to hold; dropping it does not close the room, [`leave`](Self::leave) does.
pub struct Room {
    inner: Arc<Mutex<Inner>>,
    cancel: CancellationToken,
}

fn fail(inner: &Arc<Mutex<Inner>>, message: impl Into<String>) {
    let mut g = inner.lock().unwrap();
    if !matches!(g.phase, RoomPhase::Ready | RoomPhase::Closed) {
        g.phase = RoomPhase::Failed;
        g.message = message.into();
    }
}

impl Room {
    /// Make a room: dial for guests.
    pub fn host(params: RoomParams) -> Room {
        let room = Room::new(true, params);
        let inner = room.inner.clone();
        let cancel = room.cancel.clone();
        tango_platform::spawn(async move { host_main(inner, cancel).await });
        room
    }

    /// Join the room with `params.code`.
    pub fn join(params: RoomParams) -> Room {
        let room = Room::new(false, params);
        let inner = room.inner.clone();
        let cancel = room.cancel.clone();
        tango_platform::spawn(async move { guest_main(inner, cancel).await });
        room
    }

    /// UNRANKED: look for another player who is looking too (the pool of [`unranked::unranked_session`]); the two the server
    /// pairs draw lots over their link (the lower number hosts) and play a room of two, the guest READY and the host
    /// starting as soon as it is. `params.code` and `password` are only labels; `match_type` carries the UNRANKED
    /// bits.
    pub fn unranked(params: RoomParams) -> Room {
        let room = Room::new(false, params);
        room.inner.lock().unwrap().unranked = true;
        let inner = room.inner.clone();
        let cancel = room.cancel.clone();
        tango_platform::spawn(async move { unranked::unranked_main(inner, cancel).await });
        room
    }

    pub fn is_unranked(&self) -> bool {
        self.inner.lock().unwrap().unranked
    }

    fn new(host: bool, params: RoomParams) -> Room {
        Room {
            inner: Arc::new(Mutex::new(Inner {
                host,
                unranked: false,
                params,
                phase: RoomPhase::Connecting,
                message: String::new(),
                peers: Vec::new(),
                next_id: 1,
                welcomed: false,
                roster: Vec::new(),
                my_seat: 0,
                my_ready: false,
                to_host: None,
                host_link: LinkView::default(),
                matched: None,
                started: false,
                dial: CancellationToken::new(),
            })),
            cancel: CancellationToken::new(),
        }
    }

    pub fn code(&self) -> String {
        self.inner.lock().unwrap().params.code.clone()
    }

    pub fn is_host(&self) -> bool {
        self.inner.lock().unwrap().host
    }

    pub fn view(&self) -> RoomView {
        let g = self.inner.lock().unwrap();
        let mut players = Vec::new();
        if g.host {
            for p in roster_of(&g) {
                let link = if p.host {
                    None
                } else {
                    g.peers.iter().find(|q| q.nickname == p.nickname).map(|q| q.link)
                };
                players.push(PlayerView {
                    link,
                    you: p.host,
                    nickname: p.nickname,
                    ready: p.ready,
                    host: p.host,
                });
            }
        } else if g.welcomed {
            for p in g.roster.iter() {
                players.push(PlayerView {
                    link: (p.host && p.seat as usize != g.my_seat).then_some(g.host_link),
                    nickname: p.nickname.clone(),
                    ready: p.ready,
                    host: p.host,
                    you: p.seat as usize == g.my_seat,
                });
            }
        } else {
            players.push(PlayerView {
                link: Some(g.host_link),
                nickname: "Host".to_string(),
                ready: false,
                host: true,
                you: false,
            });
            players.push(PlayerView {
                link: None,
                nickname: g.params.nickname.clone(),
                ready: false,
                host: false,
                you: true,
            });
        }
        let waiting_for: Vec<String> = match (g.host, g.params.resume.as_ref()) {
            (true, Some(r)) => r
                .players
                .iter()
                .filter(|n| **n != g.params.nickname && !g.peers.iter().any(|p| &p.nickname == *n))
                .cloned()
                .collect(),
            _ => Vec::new(),
        };
        let all_ready = g.host && !g.peers.is_empty() && g.peers.iter().all(|p| p.ready) && waiting_for.is_empty();
        RoomView {
            phase: g.phase,
            players,
            message: g.message.clone(),
            joined: g.host || g.welcomed,
            all_ready,
            waiting_for,
            resuming: g.params.resume.is_some(),
        }
    }

    /// A guest's READY (or not).
    pub fn set_ready(&self, ready: bool) {
        let mut g = self.inner.lock().unwrap();
        if g.host {
            g.my_ready = ready;
        } else {
            g.my_ready = ready;
            if let Some(tx) = g.to_host.as_ref() {
                let _ = tx.send(RoomMsg::Ready(ready));
            }
        }
    }

    /// The host starts the match (every guest READY).
    pub fn start(&self) {
        start_room(&self.inner, &self.cancel);
    }

    /// The match, once the room is [`RoomPhase::Ready`] (taken once).
    pub fn take_match(&self) -> Option<RoomMatch> {
        self.inner.lock().unwrap().matched.take()
    }

    /// Leave (or close) the room.
    pub fn leave(&self) {
        {
            let mut g = self.inner.lock().unwrap();
            if let Some(tx) = g.to_host.as_ref() {
                let _ = tx.send(RoomMsg::Leave);
            }
            if !matches!(g.phase, RoomPhase::Ready | RoomPhase::Failed) {
                g.phase = RoomPhase::Closed;
            }
        }
        // (a moment for the goodbye to go out before the links are dropped)
        let cancel = self.cancel.clone();
        tango_platform::spawn(async move {
            tango_platform::sleep(Duration::from_millis(300)).await;
            cancel.cancel();
        });
    }
}

impl Drop for Room {
    fn drop(&mut self) {
        // (a handle that is gone with the room still open: nobody can ever start it)
        let g = self.inner.lock().unwrap();
        if !matches!(g.phase, RoomPhase::Ready) {
            self.cancel.cancel();
        }
    }
}

// --- Shared ---------------------------------------------------------------------------------------------

/// The host's START, when there is a guest and every guest is READY.
fn start_room(inner: &Arc<Mutex<Inner>>, cancel: &CancellationToken) {
    let (inner, cancel) = (inner.clone(), cancel.clone());
    {
        let mut g = inner.lock().unwrap();
        let complete = g.params.resume.as_ref().is_none_or(|r| g.peers.len() + 1 == r.players.len());
        if !g.host || g.started || g.peers.is_empty() || !g.peers.iter().all(|p| p.ready) || !complete {
            return;
        }
        g.started = true;
        g.phase = RoomPhase::Starting;
        g.dial.cancel();
    }
    tango_platform::spawn(async move { host_start(inner, cancel).await });
}

/// The seat of each guest, by index among the host's peers (a room resuming a match: as saved; otherwise in order of
/// joining, around the host's seat). Keyed by the link, not the nickname: two guests may share one.
fn peer_seats(g: &Inner) -> Vec<u8> {
    let host_seat = g.params.resume.as_ref().map_or(0, |r| r.seat as u8);
    let mut next = 0u8;
    g.peers
        .iter()
        .map(|p| match p.seat {
            Some(s) => s,
            None => {
                if next == host_seat {
                    next += 1;
                }
                let s = next;
                next += 1;
                s
            }
        })
        .collect()
}

/// Everyone in the room by seat: the host's, then each guest's (in a room resuming a match, as saved; otherwise in
/// order of joining).
fn roster_of(g: &Inner) -> Vec<RoomPlayer> {
    let host_seat = g.params.resume.as_ref().map_or(0, |r| r.seat as u8);
    let mut v = vec![RoomPlayer {
        nickname: g.params.nickname.clone(),
        ready: g.my_ready,
        seat: host_seat,
        host: true,
    }];
    for (p, seat) in g.peers.iter().zip(peer_seats(g)) {
        v.push(RoomPlayer {
            nickname: p.nickname.clone(),
            ready: p.ready,
            seat,
            host: false,
        });
    }
    v.sort_by_key(|p| p.seat);
    v
}

/// The seat of the guest at `index` among the host's peers.
fn peer_seat(g: &Inner, index: usize) -> u8 {
    peer_seats(g).get(index).copied().unwrap_or(index as u8 + 1)
}

/// Tell every guest who is in the room (each its own seat).
fn broadcast_roster(inner: &Arc<Mutex<Inner>>) {
    let (roster, senders): (Vec<RoomPlayer>, Vec<_>) = {
        let g = inner.lock().unwrap();
        (
            roster_of(&g),
            (0..g.peers.len()).map(|k| (peer_seat(&g, k), g.peers[k].sender.clone())).collect(),
        )
    };
    for (seat, sender) in senders {
        let msg = Packet::Room(RoomMsg::Roster(RoomRoster {
            seat,
            players: roster.clone(),
        }));
        tango_platform::spawn(async move {
            let _ = sender.lock().await.send_packet(&msg).await;
        });
    }
}

fn game_differs(host: &Option<tango_net_protocol::control::GameInfo>, guest: &Option<tango_net_protocol::control::GameInfo>) -> Option<String> {
    match (host, guest) {
        (Some(h), Some(g)) => {
            if h.family_and_variant != g.family_and_variant || h.patch != g.patch {
                Some("The host has another game or patch.".to_string())
            } else if h.sim_version != g.sim_version {
                Some(if g.sim_version < h.sim_version {
                    "Your tangoAW2 is older: update it to play.".to_string()
                } else {
                    "The host's tangoAW2 is older: they must update.".to_string()
                })
            } else {
                None
            }
        }
        _ => Some("The host's game is not one you have.".to_string()),
    }
}

// --- The host ---------------------------------------------------------------------------------------------

async fn host_main(inner: Arc<Mutex<Inner>>, cancel: CancellationToken) {
    let (endpoint, session, use_relay, dial) = {
        let g = inner.lock().unwrap();
        (
            g.params.endpoint.clone(),
            room_session(&g.params.code),
            g.params.use_relay,
            g.dial.clone(),
        )
    };
    loop {
        // (a full room waits; a guest who leaves makes room)
        let (over, full) = {
            let g = inner.lock().unwrap();
            (
                g.started || matches!(g.phase, RoomPhase::Failed | RoomPhase::Closed),
                g.peers.len() + 1 >= MAX_PLAYERS,
            )
        };
        if over {
            return;
        }
        if full {
            tokio::select! {
                _ = cancel.cancelled() => return,
            _ = dial.cancelled() => return,
                _ = tango_platform::sleep(Duration::from_millis(400)) => {}
            }
            continue;
        }
        let route = tango_net::connect::Route::Matchmaking {
            endpoint: &endpoint,
            session_id: &session,
            use_relay,
        };
        let opened = tokio::select! {
            _ = cancel.cancelled() => return,
            _ = dial.cancelled() => return,
            r = tango_net::open_channels(route, |_| {}) => r,
        };
        match opened {
            Ok(channels) => {
                {
                    let mut g = inner.lock().unwrap();
                    if g.phase == RoomPhase::Connecting {
                        g.phase = RoomPhase::Open;
                    }
                }
                let inner2 = inner.clone();
                let cancel2 = cancel.clone();
                tango_platform::spawn(async move { serve_guest(inner2, cancel2, channels).await });
            }
            Err(tango_net::ConnectError::Signaling(e)) => {
                log::warn!("room: the matchmaking server: {e}");
                let text = format!("{e}");
                if text.contains("Websocket") || text.contains("Io") {
                    fail(&inner, "The matchmaking server cannot be reached.");
                    return;
                }
                tokio::select! {
                    _ = cancel.cancelled() => return,
            _ = dial.cancelled() => return,
                    _ = tango_platform::sleep(Duration::from_secs(1)) => {}
                }
            }
            Err(e) => {
                log::warn!("room: a guest did not come through: {e}");
                tokio::select! {
                    _ = cancel.cancelled() => return,
            _ = dial.cancelled() => return,
                    _ = tango_platform::sleep(Duration::from_millis(500)) => {}
                }
            }
        }
    }
}

/// A room resuming a match takes only its players, each once, with the content the match needs.
fn resume_refusal(g: &Inner, nickname: &str, content: bool) -> Option<String> {
    let r = g.params.resume.as_ref()?;
    if !r.players.iter().any(|n| n == nickname) {
        return Some("You are not in the match this room resumes.".to_string());
    }
    if nickname == g.params.nickname || g.peers.iter().any(|p| p.nickname == nickname) {
        return Some("Your gamertag is already in this room.".to_string());
    }
    if r.match_type.1 & tango_net_protocol::control::SHARED_CONTENT != 0 && !content {
        return Some("This match needs the Dual Strike pack.".to_string());
    }
    None
}

async fn reject(sender: &Arc<tokio::sync::Mutex<tango_net::Sender>>, reason: RejectReason, text: &str) {
    let msg = Packet::Room(RoomMsg::Reject(RoomReject {
        reason,
        text: text.to_string(),
    }));
    let _ = sender.lock().await.send_packet(&msg).await;
    // (a moment for it to arrive before the connection goes)
    tango_platform::sleep(Duration::from_millis(400)).await;
}

/// One guest's connection, from its `Join` to its leaving or the match's taking the link over.
async fn serve_guest(inner: Arc<Mutex<Inner>>, cancel: CancellationToken, channels: Channels) {
    let Channels {
        control: (sender, mut receiver),
        in_match,
        peer_conn,
        is_offerer: _,
        local_dtls_fingerprint,
        peer_dtls_fingerprint,
    } = channels;
    let sender = Arc::new(tokio::sync::Mutex::new(sender));
    let first = tango_platform::timeout(FIRST_WORDS, receiver.receive()).await;
    let join = match first {
        Ok(Ok(Packet::Room(RoomMsg::Join(j)))) => j,
        Ok(Ok(Packet::Room(_))) | Ok(Ok(_)) => return,
        _ => return,
    };
    let nickname: String = join.nickname.chars().filter(|c| !c.is_control()).take(12).collect();
    // Let in, or turn away.
    let resume_seat: Option<u8>;
    let verdict: Result<(u64, CancellationToken, tokio::sync::oneshot::Sender<tango_net::Receiver>), (RejectReason, String)> = {
        let mut g = inner.lock().unwrap();
        if g.started {
            Err((RejectReason::Started, "The match has already started.".into()))
        } else if g.peers.len() + 1 >= MAX_PLAYERS {
            Err((RejectReason::Full, "The room is full.".into()))
        } else if join.password != room_password_hash(&g.params.code, &g.params.password) {
            Err((RejectReason::WrongPassword, "Wrong password.".into()))
        } else if let Some(why) = game_differs(&g.params.game_info, &join.game_info) {
            Err((RejectReason::GameMismatch, why))
        } else if let Some(why) = resume_refusal(&g, &nickname, join.content) {
            Err((RejectReason::NotInMatch, why))
        } else {
            resume_seat = g
                .params
                .resume
                .as_ref()
                .and_then(|r| r.players.iter().position(|n| *n == nickname))
                .map(|k| k as u8);
            let id = g.next_id;
            g.next_id += 1;
            let handoff = CancellationToken::new();
            let (back_tx, back_rx) = tokio::sync::oneshot::channel();
            let link = LinkView::of(&peer_conn);
            // (the receiver goes back through `back_tx` when the match takes the link)
            g.peers.push(HostPeer {
                id,
                nickname: nickname.clone(),
                seat: resume_seat,
                ready: false,
                loaded: false,
                content: join.content,
                link,
                sender: sender.clone(),
                handoff: handoff.clone(),
                receiver_back: Some(back_rx),
                parts: Some(Parts {
                    in_match,
                    peer_conn,
                    local_fp: local_dtls_fingerprint,
                    peer_fp: peer_dtls_fingerprint,
                }),
            });
            Ok((id, handoff, back_tx))
        }
    };
    let (id, handoff, back_tx) = match verdict {
        Ok(v) => v,
        Err((reason, text)) => {
            log::info!("room: turned a guest away: {text}");
            reject(&sender, reason, &text).await;
            return;
        }
    };
    log::info!("room: {} joined", join.nickname);
    let welcome = {
        let g = inner.lock().unwrap();
        let seat = g.peers.iter().position(|p| p.id == id).map_or(1, |k| peer_seat(&g, k));
        Packet::Room(RoomMsg::Welcome(RoomRoster {
            seat,
            players: roster_of(&g),
        }))
    };
    let _ = sender.lock().await.send_packet(&welcome).await;
    broadcast_roster(&inner);

    let mut last_heard = web_time::Instant::now();
    let mut ping = 0u16;
    let mut ping_sent = web_time::Instant::now();
    let mut ticks = 0u32;
    let ended: Option<String> = loop {
        tokio::select! {
            biased;
            _ = cancel.cancelled() => break Some("closed".into()),
            _ = handoff.cancelled() => {
                // The match takes the link: give the control receiver back for it.
                let _ = back_tx.send(receiver);
                return;
            }
            _ = tango_platform::sleep(Duration::from_secs(1)) => {
                if last_heard.elapsed() > SILENCE {
                    break Some("silent".into());
                }
                ping = ping.wrapping_add(1);
                ping_sent = web_time::Instant::now();
                let _ = sender.lock().await.send_ping(ping).await;
                // (the route can change after the first pair: ICE may move from a relay to a better path)
                ticks += 1;
                if ticks % 4 == 0 {
                    let mut g = inner.lock().unwrap();
                    if let Some(p) = g.peers.iter_mut().find(|p| p.id == id) {
                        if let Some(parts) = p.parts.as_ref() {
                            p.link.kind = tango_net::channel::Channels::kind(&parts.peer_conn);
                        }
                    }
                }
            }
            pkt = receiver.receive() => {
                match pkt {
                    Ok(Packet::Ping(p)) => {
                        last_heard = web_time::Instant::now();
                        let _ = sender.lock().await.send_pong(p.ts).await;
                    }
                    Ok(Packet::Pong(p)) => {
                        last_heard = web_time::Instant::now();
                        if p.ts == ping {
                            let rtt = last_heard.saturating_duration_since(ping_sent);
                            let mut g = inner.lock().unwrap();
                            if let Some(q) = g.peers.iter_mut().find(|q| q.id == id) {
                                q.link.sample(rtt);
                            }
                        }
                    }
                    Ok(Packet::Room(RoomMsg::Ready(r))) => {
                        last_heard = web_time::Instant::now();
                        {
                            let mut g = inner.lock().unwrap();
                            if let Some(p) = g.peers.iter_mut().find(|p| p.id == id) {
                                p.ready = r;
                            }
                        }
                        broadcast_roster(&inner);
                    }
                    Ok(Packet::Room(RoomMsg::Loaded)) => {
                        last_heard = web_time::Instant::now();
                        let mut g = inner.lock().unwrap();
                        if let Some(p) = g.peers.iter_mut().find(|p| p.id == id) {
                            p.loaded = true;
                        }
                    }
                    Ok(Packet::Room(RoomMsg::Leave)) => break None,
                    Ok(_) => last_heard = web_time::Instant::now(),
                    Err(_) => break None,
                }
            }
        }
    };
    // Gone before the match took it.
    let started = {
        let mut g = inner.lock().unwrap();
        g.peers.retain(|p| p.id != id);
        g.started
    };
    if ended.as_deref() == Some("closed") {
        return;
    }
    if started {
        fail(&inner, "A player left before the match began.");
    } else {
        log::info!("room: a guest left");
        broadcast_roster(&inner);
    }
}

/// The host's START: the seed, the clock and the save to every guest, wait for each to say it has them, then hand
/// every link to the match.
async fn host_start(inner: Arc<Mutex<Inner>>, cancel: CancellationToken) {
    use rand::RngCore;
    let mut seed = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut seed);
    let ts = web_time::SystemTime::now()
        .duration_since(web_time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    let (players, save, match_type, senders, host_seat, match_id, resume, ts) = {
        let mut g = inner.lock().unwrap();
        // (the links go to the match by seat: ascending)
        let order: Vec<u8> = (0..g.peers.len()).map(|k| peer_seat(&g, k)).collect();
        let mut idx: Vec<usize> = (0..g.peers.len()).collect();
        idx.sort_by_key(|&k| order[k]);
        let mut sorted = Vec::new();
        let mut taken: Vec<Option<HostPeer>> = std::mem::take(&mut g.peers).into_iter().map(Some).collect();
        for k in idx {
            sorted.push(taken[k].take().unwrap());
        }
        g.peers = sorted;
        let resume = g.params.resume.clone();
        let mut names = vec![g.params.nickname.clone()];
        names.extend(g.peers.iter().map(|p| p.nickname.clone()));
        let (names, host_seat) = match resume.as_ref() {
            // (as saved: every player of it is here, which `start` checked)
            Some(r) => (r.players.clone(), r.seat),
            None => (names, 0),
        };
        let all_content = g.params.content && g.peers.iter().all(|p| p.content);
        let mut match_type = g.params.match_type;
        if all_content {
            match_type.1 |= tango_net_protocol::control::SHARED_CONTENT;
        }
        // UNRANKED: whose proposed map is played, drawn from the match seed (the guest gets it in `Start`).
        if g.unranked && seed[0] & 1 != 0 {
            match_type.1 |= tango_net_protocol::control::UNRANKED_PICK_GUEST;
        }
        let (save, match_type, ts) = match resume.as_ref() {
            Some(r) => (r.save.clone(), r.match_type, r.match_ts),
            None => (g.params.save.clone(), match_type, ts),
        };
        let match_id = resume.as_ref().map_or_else(rand::random::<u64>, |r| r.match_id);
        (
            names,
            save,
            match_type,
            g.peers.iter().map(|p| p.sender.clone()).collect::<Vec<_>>(),
            host_seat,
            match_id,
            resume,
            ts,
        )
    };
    // The payload: the host's save, and for a match being resumed the state as well.
    let payload = match resume.as_ref() {
        Some(r) => bincode::serialize(&(&save, &r.state)).unwrap_or_default(),
        None => save.clone(),
    };
    let compressed = match zstd::stream::encode_all(std::io::Cursor::new(&payload), 3) {
        Ok(c) => c,
        Err(e) => {
            log::warn!("room: could not pack the save: {e}");
            fail(&inner, "Could not pack the save.");
            return;
        }
    };
    let start = Packet::Room(RoomMsg::Start(RoomStart {
        seed,
        ts,
        players: players.clone(),
        save_len: compressed.len() as u64,
        save_hash: make_commitment(&compressed),
        match_type,
        match_id,
        host_seat: host_seat as u8,
        resume: resume.as_ref().map(|r| tango_net_protocol::control::ResumeInfo {
            tick: r.tick,
            digest: r.digest,
        }),
    }));
    for sender in &senders {
        let mut s = sender.lock().await;
        let sent = async {
            s.send_packet(&start).await?;
            s.send_chunk_start(compressed.len() as u64).await?;
            for chunk in compressed.chunks(tango_net_protocol::control::REVEAL_CHUNK_SIZE) {
                s.send_chunk(chunk.to_vec()).await?;
            }
            std::io::Result::Ok(())
        };
        if let Err(e) = sent.await {
            log::warn!("room: a player's link broke while the match was starting: {e}");
            fail(&inner, "A player's link broke as the match began.");
            return;
        }
    }
    // Everyone has it?
    let deadline = web_time::Instant::now() + LOAD_DEADLINE;
    loop {
        {
            let g = inner.lock().unwrap();
            if matches!(g.phase, RoomPhase::Failed | RoomPhase::Closed) {
                return;
            }
            if !g.peers.is_empty() && g.peers.iter().all(|p| p.loaded) && g.peers.len() == senders.len() {
                break;
            }
            if g.peers.len() != senders.len() {
                drop(g);
                fail(&inner, "A player left before the match began.");
                return;
            }
        }
        if web_time::Instant::now() > deadline {
            fail(&inner, "A player did not get the start in time.");
            return;
        }
        tokio::select! {
            _ = cancel.cancelled() => return,
            _ = tango_platform::sleep(Duration::from_millis(50)) => {}
        }
    }
    // Hand the links over.
    let (handoffs, mut backs): (Vec<CancellationToken>, Vec<tokio::sync::oneshot::Receiver<tango_net::Receiver>>) = {
        let mut g = inner.lock().unwrap();
        let h = g.peers.iter().map(|p| p.handoff.clone()).collect();
        let b = g.peers.iter_mut().filter_map(|p| p.receiver_back.take()).collect();
        (h, b)
    };
    for h in &handoffs {
        h.cancel();
    }
    let mut links = Vec::new();
    let mut taken: Vec<(Arc<tokio::sync::Mutex<tango_net::Sender>>, Parts)> = {
        let mut g = inner.lock().unwrap();
        g.peers
            .iter_mut()
            .filter_map(|p| p.parts.take().map(|parts| (p.sender.clone(), parts)))
            .collect()
    };
    let (endpoint, use_relay, code) = {
        let g = inner.lock().unwrap();
        (g.params.endpoint.clone(), g.params.use_relay, g.params.code.clone())
    };
    for ((sender, parts), back) in taken.drain(..).zip(backs.drain(..)) {
        let (tx, rx) = tokio::sync::oneshot::channel();
        // (the task that owns the receiver sends it back on `back`; forward it to this link's)
        tango_platform::spawn(async move {
            if let Ok(r) = back.await {
                let _ = tx.send(r);
            }
        });
        let session_id = tango_net::link::derive_reconnect_session_id(&seed, &parts.local_fp, &parts.peer_fp);
        links.push(LinkParts {
            control_sender: sender,
            control_receiver_rx: rx,
            in_match_sender: parts.in_match.0,
            in_match_receiver: parts.in_match.1,
            peer_conn: parts.peer_conn,
            recipe: Some(ReconnectRecipe::Matchmaking {
                endpoint: endpoint.clone(),
                session_id,
                use_relay,
            }),
            rng_seed: seed,
        });
    }
    let mut g = inner.lock().unwrap();
    g.matched = Some(RoomMatch {
        is_host: true,
        seat: host_seat,
        players,
        seed,
        ts,
        host_save: save,
        match_type,
        code,
        links,
        host_seat,
        match_id,
        resume_state: resume.map(|r| r.state),
    });
    g.phase = RoomPhase::Ready;
}

// --- A guest ----------------------------------------------------------------------------------------------

async fn guest_main(inner: Arc<Mutex<Inner>>, cancel: CancellationToken) {
    let (endpoint, session, use_relay, join) = {
        let g = inner.lock().unwrap();
        (
            g.params.endpoint.clone(),
            room_session(&g.params.code),
            g.params.use_relay,
            RoomJoin {
                nickname: g.params.nickname.clone(),
                password: room_password_hash(&g.params.code, &g.params.password),
                game_info: g.params.game_info.clone(),
                content: g.params.content,
                saves: g.params.saves.clone(),
            },
        )
    };
    let deadline = web_time::Instant::now() + GUEST_DEADLINE;
    // Looking for the host.
    let (channels, welcome) = loop {
        let left = deadline.saturating_duration_since(web_time::Instant::now());
        if left.is_zero() {
            fail(&inner, "No room with that code is open.");
            return;
        }
        let route = tango_net::connect::Route::Matchmaking {
            endpoint: &endpoint,
            session_id: &session,
            use_relay,
        };
        let opened = tokio::select! {
            _ = cancel.cancelled() => return,
            r = tango_platform::timeout(left, tango_net::open_channels(route, |_| {})) => r,
        };
        let mut channels = match opened {
            Err(_) => {
                fail(&inner, "No room with that code is open.");
                return;
            }
            Ok(Ok(c)) => c,
            Ok(Err(tango_net::ConnectError::Signaling(e))) => {
                let text = format!("{e}");
                log::warn!("room: the matchmaking server: {text}");
                if text.contains("Websocket") || text.contains("Io") {
                    fail(&inner, "The matchmaking server cannot be reached.");
                    return;
                }
                tango_platform::sleep(Duration::from_secs(1)).await;
                continue;
            }
            Ok(Err(e)) => {
                log::warn!("room: could not connect: {e}");
                tango_platform::sleep(Duration::from_millis(700)).await;
                continue;
            }
        };
        {
            let mut g = inner.lock().unwrap();
            g.message = "Connected: joining...".into();
        }
        if channels.control.0.send_packet(&Packet::Room(RoomMsg::Join(join.clone()))).await.is_err() {
            continue;
        }
        let first = tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await;
        match first {
            Ok(Ok(Packet::Room(RoomMsg::Welcome(w)))) | Ok(Ok(Packet::Room(RoomMsg::Roster(w)))) => break (channels, w),
            Ok(Ok(Packet::Room(RoomMsg::Reject(r)))) => {
                if r.reason == RejectReason::NotTheHost {
                    // (another guest: try again)
                    tango_platform::sleep(Duration::from_millis(300 + rand::random::<u64>() % 700)).await;
                    continue;
                }
                fail(&inner, r.text);
                return;
            }
            // The other one is a guest looking for the host too: let go and look again.
            Ok(Ok(Packet::Room(RoomMsg::Join(_)))) => {
                let _ = channels.control.0.send_packet(&Packet::Room(RoomMsg::Reject(RoomReject {
                    reason: RejectReason::NotTheHost,
                    text: String::new(),
                }))).await;
                tango_platform::sleep(Duration::from_millis(300 + rand::random::<u64>() % 700)).await;
                continue;
            }
            _ => {
                tango_platform::sleep(Duration::from_millis(500)).await;
                continue;
            }
        }
    };
    guest_session(inner, cancel, channels, welcome).await;
}

/// A guest welcomed by the host over `channels`: its READY, the roster and the start, then the hand-over to the match.
async fn guest_session(inner: Arc<Mutex<Inner>>, cancel: CancellationToken, channels: Channels, welcome: RoomRoster) {
    let Channels {
        control: (sender, mut receiver),
        in_match,
        peer_conn,
        is_offerer: _,
        local_dtls_fingerprint,
        peer_dtls_fingerprint,
    } = channels;
    let sender = Arc::new(tokio::sync::Mutex::new(sender));
    let (to_host, mut commands) = tokio::sync::mpsc::unbounded_channel::<RoomMsg>();
    {
        let mut g = inner.lock().unwrap();
        g.welcomed = true;
        g.phase = RoomPhase::Open;
        g.message.clear();
        g.my_seat = welcome.seat as usize;
        g.roster = welcome.players;
        g.to_host = Some(to_host);
        // (a READY pressed before the welcome)
        if g.my_ready {
            if let Some(tx) = g.to_host.as_ref() {
                let _ = tx.send(RoomMsg::Ready(true));
            }
        }
    }
    let mut last_heard = web_time::Instant::now();
    let mut ping = 0u16;
    let mut ping_sent = web_time::Instant::now();
    let mut ticks = 0u32;
    let mut start: Option<RoomStart> = None;
    let mut chunks: Option<(u64, Vec<u8>)> = None;
    let mut in_match = Some(in_match);
    inner.lock().unwrap().host_link = LinkView::of(&peer_conn);
    let mut peer_conn = Some(peer_conn);
    loop {
        tokio::select! {
            biased;
            _ = cancel.cancelled() => {
                let _ = sender.lock().await.send_packet(&Packet::Room(RoomMsg::Leave)).await;
                return;
            }
            cmd = commands.recv() => {
                if let Some(msg) = cmd {
                    let _ = sender.lock().await.send_packet(&Packet::Room(msg)).await;
                }
            }
            _ = tango_platform::sleep(Duration::from_secs(1)) => {
                if last_heard.elapsed() > SILENCE {
                    fail(&inner, "The host stopped answering.");
                    return;
                }
                ping = ping.wrapping_add(1);
                ping_sent = web_time::Instant::now();
                let _ = sender.lock().await.send_ping(ping).await;
                ticks += 1;
                if ticks % 4 == 0 {
                    if let Some(pc) = peer_conn.as_ref() {
                        inner.lock().unwrap().host_link.kind = tango_net::channel::Channels::kind(pc);
                    }
                }
            }
            pkt = receiver.receive() => {
                last_heard = web_time::Instant::now();
                match pkt {
                    Ok(Packet::Ping(p)) => { let _ = sender.lock().await.send_pong(p.ts).await; }
                    Ok(Packet::Pong(p)) => {
                        if p.ts == ping {
                            inner.lock().unwrap().host_link.sample(last_heard.saturating_duration_since(ping_sent));
                        }
                    }
                    Ok(Packet::Room(RoomMsg::Roster(r))) => {
                        let mut g = inner.lock().unwrap();
                        g.my_seat = r.seat as usize;
                        g.roster = r.players;
                    }
                    Ok(Packet::Room(RoomMsg::Start(s))) => {
                        {
                            let mut g = inner.lock().unwrap();
                            g.started = true;
                            g.phase = RoomPhase::Starting;
                        }
                        start = Some(s);
                    }
                    Ok(Packet::ChunkStart(c)) if start.is_some() => chunks = Some((c.len, Vec::new())),
                    Ok(Packet::Chunk(c)) if start.is_some() => {
                        if let Some((want, got)) = chunks.as_mut() {
                            got.extend_from_slice(&c.chunk);
                            if got.len() as u64 >= *want {
                                let s = start.take().unwrap();
                                let (_, bytes) = chunks.take().unwrap();
                                if make_commitment(&bytes) != s.save_hash {
                                    fail(&inner, "The host's save did not arrive intact.");
                                    return;
                                }
                                let Ok(payload) = zstd::stream::decode_all(std::io::Cursor::new(&bytes)) else {
                                    fail(&inner, "The host's save did not unpack.");
                                    return;
                                };
                                // (a match being resumed brings its state with the save)
                                let (save, resume_state) = if s.resume.is_some() {
                                    match bincode::deserialize::<(Vec<u8>, Vec<u8>)>(&payload) {
                                        Ok((save, state)) => (save, Some(state)),
                                        Err(_) => {
                                            fail(&inner, "The host's saved match did not unpack.");
                                            return;
                                        }
                                    }
                                } else {
                                    (payload, None)
                                };
                                let _ = sender.lock().await.send_packet(&Packet::Room(RoomMsg::Loaded)).await;
                                // Hand over: the control receiver is ours to give straight away.
                                let (tx, rx) = tokio::sync::oneshot::channel();
                                let _ = tx.send(receiver);
                                let (endpoint, use_relay, code) = {
                                    let g = inner.lock().unwrap();
                                    (g.params.endpoint.clone(), g.params.use_relay, g.params.code.clone())
                                };
                                let session_id = tango_net::link::derive_reconnect_session_id(
                                    &s.seed, &local_dtls_fingerprint, &peer_dtls_fingerprint);
                                let (in_tx, in_rx) = in_match.take().unwrap();
                                let parts = LinkParts {
                                    control_sender: sender.clone(),
                                    control_receiver_rx: rx,
                                    in_match_sender: in_tx,
                                    in_match_receiver: in_rx,
                                    peer_conn: peer_conn.take().unwrap(),
                                    recipe: Some(ReconnectRecipe::Matchmaking { endpoint, session_id, use_relay }),
                                    rng_seed: s.seed,
                                };
                                let mut g = inner.lock().unwrap();
                                let seat = g.my_seat;
                                g.matched = Some(RoomMatch {
                                    is_host: false,
                                    seat,
                                    players: s.players,
                                    seed: s.seed,
                                    ts: s.ts,
                                    host_save: save,
                                    match_type: s.match_type,
                                    code,
                                    links: vec![parts],
                                    host_seat: s.host_seat as usize,
                                    match_id: s.match_id,
                                    resume_state,
                                });
                                g.phase = RoomPhase::Ready;
                                return;
                            }
                        }
                    }
                    Ok(Packet::Room(RoomMsg::Leave)) | Err(_) => {
                        log::info!("room: the host's link ended: {:?}", pkt.as_ref().map(|p| format!("{p:?}")).map_err(|e| e.to_string()));
                        fail(&inner, "The host closed the room.");
                        return;
                    }
                    Ok(_) => {}
                }
            }
        }
    }
}

#[cfg(test)]
mod text_tests {
    /// What the game's mailbox holds of a message (`tango_gamesupport_aw2::online::MESSAGE_LEN` minus the zero):
    /// a longer one is cut off on the console's page.
    const MESSAGE_CHARS: usize = 47;

    fn literals(line: &str) -> Vec<&str> {
        line.split('"').skip(1).step_by(2).collect()
    }

    /// Every message this module (and UNRANKED's) puts on the game's room pages fits the mailbox whole.
    #[test]
    fn messages_fit_the_game_mailbox() {
        let mut seen = 0;
        for (file, src) in [("room.rs", include_str!("room.rs")), ("unranked.rs", include_str!("unranked.rs"))] {
            let body = src.split("mod text_tests").next().unwrap();
            let mut in_texts = false;
            for line in body.lines() {
                if line.starts_with("fn game_differs") || line.starts_with("fn resume_refusal") {
                    in_texts = true;
                }
                if line.starts_with("async fn ") || line.starts_with("// ---") {
                    in_texts = false;
                }
                let is_text = in_texts || line.contains("fail(&inner,") || line.contains("RejectReason::") && line.contains("Err((")
                    || line.contains("g.message = ");
                if !is_text || line.trim_start().starts_with("//") || line.contains("log::") {
                    continue;
                }
                for l in literals(line) {
                    if l.chars().next().is_some_and(|c| c.is_ascii_uppercase()) && l.contains(' ') && !l.contains("{}") {
                        seen += 1;
                        assert!(l.len() <= MESSAGE_CHARS, "{file}: {} chars, the console shows {MESSAGE_CHARS}: {l}", l.len());
                    }
                }
            }
        }
        assert!(seen >= 25, "only {seen} messages found");
    }
}
