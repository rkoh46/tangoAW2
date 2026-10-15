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

#[derive(Clone, Debug)]
pub struct PlayerView {
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
    /// Every guest is READY (and there is one): the host may start.
    pub all_ready: bool,
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
    ready: bool,
    loaded: bool,
    sender: Arc<tokio::sync::Mutex<tango_net::Sender>>,
    /// Fired to make the peer's task give its control receiver back for the match.
    handoff: CancellationToken,
    receiver_back: Option<tokio::sync::oneshot::Receiver<tango_net::Receiver>>,
    parts: Option<Parts>,
}

struct Inner {
    host: bool,
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

    fn new(host: bool, params: RoomParams) -> Room {
        Room {
            inner: Arc::new(Mutex::new(Inner {
                host,
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
            players.push(PlayerView {
                nickname: g.params.nickname.clone(),
                ready: g.my_ready,
                host: true,
                you: true,
            });
            for p in &g.peers {
                players.push(PlayerView {
                    nickname: p.nickname.clone(),
                    ready: p.ready,
                    host: false,
                    you: false,
                });
            }
        } else if g.welcomed {
            for (k, p) in g.roster.iter().enumerate() {
                players.push(PlayerView {
                    nickname: p.nickname.clone(),
                    ready: p.ready,
                    host: k == 0,
                    you: k == g.my_seat,
                });
            }
        } else {
            players.push(PlayerView {
                nickname: "Host".to_string(),
                ready: false,
                host: true,
                you: false,
            });
            players.push(PlayerView {
                nickname: g.params.nickname.clone(),
                ready: false,
                host: false,
                you: true,
            });
        }
        let all_ready = g.host && !g.peers.is_empty() && g.peers.iter().all(|p| p.ready);
        RoomView {
            phase: g.phase,
            players,
            message: g.message.clone(),
            joined: g.host || g.welcomed,
            all_ready,
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
        let inner = self.inner.clone();
        let cancel = self.cancel.clone();
        {
            let mut g = inner.lock().unwrap();
            if !g.host || g.started || g.peers.is_empty() || !g.peers.iter().all(|p| p.ready) {
                return;
            }
            g.started = true;
            g.phase = RoomPhase::Starting;
            g.dial.cancel();
        }
        tango_platform::spawn(async move { host_start(inner, cancel).await });
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

fn roster_of(g: &Inner) -> Vec<RoomPlayer> {
    let mut v = vec![RoomPlayer {
        nickname: g.params.nickname.clone(),
        ready: g.my_ready,
    }];
    v.extend(g.peers.iter().map(|p| RoomPlayer {
        nickname: p.nickname.clone(),
        ready: p.ready,
    }));
    v
}

/// Tell every guest who is in the room (each its own seat).
fn broadcast_roster(inner: &Arc<Mutex<Inner>>) {
    let (roster, senders): (Vec<RoomPlayer>, Vec<_>) = {
        let g = inner.lock().unwrap();
        (roster_of(&g), g.peers.iter().map(|p| p.sender.clone()).collect())
    };
    for (k, sender) in senders.into_iter().enumerate() {
        let msg = Packet::Room(RoomMsg::Roster(RoomRoster {
            seat: k as u8 + 1,
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
                Some("The host's game (or patch) is not the one you have.".to_string())
            } else if h.sim_version != g.sim_version {
                Some(if g.sim_version < h.sim_version {
                    "Your tangoAW2 is older than the host's: update it to play.".to_string()
                } else {
                    "The host's tangoAW2 is older than yours: they need to update.".to_string()
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
    // Let in, or turn away.
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
        } else {
            let id = g.next_id;
            g.next_id += 1;
            let handoff = CancellationToken::new();
            let (back_tx, back_rx) = tokio::sync::oneshot::channel();
            // (the receiver goes back through `back_tx` when the match takes the link)
            g.peers.push(HostPeer {
                id,
                nickname: join.nickname.chars().filter(|c| !c.is_control()).take(12).collect(),
                ready: false,
                loaded: false,
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
    {
        let g = inner.lock().unwrap();
        let seat = g.peers.iter().position(|p| p.id == id).map_or(1, |k| k + 1);
        let welcome = Packet::Room(RoomMsg::Welcome(RoomRoster {
            seat: seat as u8,
            players: roster_of(&g),
        }));
        let sender = sender.clone();
        tango_platform::spawn(async move {
            let _ = sender.lock().await.send_packet(&welcome).await;
        });
    }
    broadcast_roster(&inner);

    let mut last_heard = web_time::Instant::now();
    let mut ping = 0u16;
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
                let _ = sender.lock().await.send_ping(ping).await;
            }
            pkt = receiver.receive() => {
                match pkt {
                    Ok(Packet::Ping(p)) => {
                        last_heard = web_time::Instant::now();
                        let _ = sender.lock().await.send_pong(p.ts).await;
                    }
                    Ok(Packet::Pong(_)) => last_heard = web_time::Instant::now(),
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
    let (players, save, match_type, senders) = {
        let g = inner.lock().unwrap();
        let mut names = vec![g.params.nickname.clone()];
        names.extend(g.peers.iter().map(|p| p.nickname.clone()));
        (
            names,
            g.params.save.clone(),
            g.params.match_type,
            g.peers.iter().map(|p| p.sender.clone()).collect::<Vec<_>>(),
        )
    };
    let compressed = match zstd::stream::encode_all(std::io::Cursor::new(&save), 3) {
        Ok(c) => c,
        Err(e) => {
            fail(&inner, format!("Could not pack the save ({e})."));
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
            fail(&inner, format!("A player's link broke while the match was starting ({e})."));
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
    let (endpoint, use_relay, code, match_type) = {
        let g = inner.lock().unwrap();
        (
            g.params.endpoint.clone(),
            g.params.use_relay,
            g.params.code.clone(),
            g.params.match_type,
        )
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
    let host_save = g.params.save.clone();
    g.matched = Some(RoomMatch {
        is_host: true,
        seat: 0,
        players,
        seed,
        ts,
        host_save,
        match_type,
        code,
        links,
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
            },
        )
    };
    let deadline = web_time::Instant::now() + GUEST_DEADLINE;
    // Looking for the host.
    let (channels, welcome) = loop {
        let left = deadline.saturating_duration_since(web_time::Instant::now());
        if left.is_zero() {
            fail(&inner, "No such room: nobody has it open with that code.");
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
                fail(&inner, "No such room: nobody has it open with that code.");
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
        match tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await {
            Ok(Ok(Packet::Room(RoomMsg::Welcome(w)))) => break (channels, w),
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
    let mut start: Option<RoomStart> = None;
    let mut chunks: Option<(u64, Vec<u8>)> = None;
    let mut in_match = Some(in_match);
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
                let _ = sender.lock().await.send_ping(ping).await;
            }
            pkt = receiver.receive() => {
                last_heard = web_time::Instant::now();
                match pkt {
                    Ok(Packet::Ping(p)) => { let _ = sender.lock().await.send_pong(p.ts).await; }
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
                                let Ok(save) = zstd::stream::decode_all(std::io::Cursor::new(&bytes)) else {
                                    fail(&inner, "The host's save did not unpack.");
                                    return;
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
                                });
                                g.phase = RoomPhase::Ready;
                                return;
                            }
                        }
                    }
                    Ok(Packet::Room(RoomMsg::Leave)) | Err(_) => {
                        fail(&inner, "The host closed the room.");
                        return;
                    }
                    Ok(_) => {}
                }
            }
        }
    }
}
