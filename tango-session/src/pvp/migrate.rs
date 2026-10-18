//! HOST MIGRATION: a room whose host leaves goes on under one of its guests.
//!
//! The match is one console that every peer simulates; the host only joins the guests' inputs into one stream
//! (see `driver::HostAgg`) and the guests hear nothing but that stream. So when the host goes, all the room needs is
//! a new joiner that carries the stream on from the tick everyone has:
//!
//! 1. Every guest that sees the host gone (it said goodbye, its connection closed, it went silent, or a living
//!    host did not come back within the grace) computes the same succession order ([`successor_order`]): the
//!    remaining seats, those still in the match first, by seat. Rank 0 is the new host.
//! 2. The drive thread stops at a tick boundary and publishes a [`Snapshot`]: how many rows of the old stream it
//!    has taken in, how many ticks it has played, and the last rows with the words of every seat.
//! 3. The new host makes a rendezvous on the matchmaking server that only the room can name
//!    (`derive_migration_session_id`: the match seed and the rank), where the guests dial it like the room's
//!    own code. Each guest says its snapshot. The new host works out the longest stream any of them has
//!    ([`plan`]): peers that are ahead give the rows the others lack (`RoomMigrateGo::catchup`, every peer's
//!    own view of them), so nobody rolls back and nobody's console differs. From the tick `start` on,
//!    everyone's words come to the new host as ever and it joins them, the old host's seat idle.
//! 4. The links are handed to the drive thread, which turns into a host (or stays a guest) and resumes.
//!
//! Failing within [`RANK_WINDOW`] of the second candidate, the match ends as any other disconnect does: it is
//! saved for RESUME.

use super::supervisor::{spawn_supervisor, Pauses, RoomCtx, SupGroup, SupervisorContext};
use super::EndState;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tango_net_protocol::control::{MigrateRow, Packet, RejectReason, RoomMigrate, RoomMigrateGo, RoomMsg, RoomReject};

/// How long a candidate for the new host is waited for before the next one is tried.
pub(super) const RANK_WINDOW: Duration = Duration::from_secs(10);
/// The candidates tried: two, the first and the next in line.
const RANKS: usize = 2;
/// Once every seat still in the match is here, how long the new host waits for the others (seats that are out and
/// may have gone with the host) before it begins.
const OUT_SEATS_GRACE: Duration = Duration::from_millis(1500);
/// How long a link made for the migration waits for the other's words.
const FIRST_WORDS: Duration = Duration::from_secs(6);
/// How long the drive thread has to serve a request.
const SERVE_TIMEOUT: Duration = Duration::from_secs(5);

/// The seats that could host after `host_seat` left, in order of preference: those still in the match first, then
/// those that are out of it, each by seat. The seats that left the match earlier (`gone`) are not there. Every peer of
/// the room computes the same order from the same console state.
pub fn successor_order(players: usize, host_seat: usize, seats_out: u8, gone: u8) -> Vec<usize> {
    let mut left: Vec<usize> = (0..players.min(8)).filter(|&s| s != host_seat && gone & (1 << s) == 0).collect();
    left.sort_by_key(|&s| (seats_out & (1 << s) != 0, s));
    left
}

/// What the migration asks of the drive thread, and what it hands it.
#[derive(Default)]
pub(super) struct Mailbox {
    pub(super) want_snapshot: AtomicBool,
    pub(super) snapshot: Mutex<Option<Snapshot>>,
    pub(super) handover: Mutex<Option<Handover>>,
}

/// How far a peer got in the old host's stream.
pub(super) struct Snapshot {
    /// Rows of the stream taken in (the tick the next one is for), ticks played with local input, the last rows.
    pub(super) remote: u32,
    pub(super) local: u32,
    pub(super) tail: Vec<MigrateRow>,
}

/// The new topology, for the drive thread to take over.
pub(super) struct Handover {
    pub(super) host_seat: usize,
    pub(super) i_host: bool,
    /// Seats whose players are not in the room any more (the old host's among them).
    pub(super) gone: u8,
    /// The tick from which the new host's stream runs, and the rows this peer lacked before it.
    pub(super) start: u32,
    pub(super) catchup: Vec<[u16; 4]>,
    /// A host: one sender to each non-host seat in seat order (none for a seat that is not there). A guest: the host's.
    pub(super) senders: Vec<Option<tango_net::PvpSender>>,
    pub(super) in_matches: Vec<tango_net::InMatchTx>,
}

/// One peer's state, as the plan reads it.
#[derive(Clone, Debug)]
pub(super) struct PeerState {
    pub(super) seat: usize,
    pub(super) remote: u32,
    pub(super) tail: Vec<MigrateRow>,
}

/// What the new host sends everyone.
#[derive(Debug, PartialEq, Eq)]
pub(super) struct Plan {
    /// The tick from which words are joined afresh: the longest stream any peer has.
    pub(super) start: u32,
    /// For each peer, the rows of the old stream it lacks (`remote..start`), as its own view of them: the words of
    /// the other seats in seat order.
    pub(super) catchup: Vec<(usize, Vec<[u16; 4]>)>,
}

/// The words of every seat for a tick, from one peer's row: its view (all the other seats in order) and its own.
fn seat_words(players: usize, seat: usize, row: &MigrateRow) -> Vec<u16> {
    let mut words = vec![0u16; players];
    let mut k = 0;
    for (s, w) in words.iter_mut().enumerate() {
        if s == seat {
            *w = row.own;
        } else {
            *w = row.view.get(k).copied().unwrap_or(0);
            k += 1;
        }
    }
    words
}

/// A peer's view of a tick from the words of every seat.
fn view_of(seat: usize, words: &[u16]) -> [u16; 4] {
    let mut view = [0u16; 4];
    for (k, w) in words.iter().enumerate().filter(|&(s, _)| s != seat).map(|(_, w)| w).enumerate() {
        if let Some(v) = view.get_mut(k) {
            *v = *w;
        }
    }
    view
}

/// The new host's reading of everyone's snapshots: where the stream resumes and what each peer lacks. Fails when the
/// peers disagree about a tick they both took in (their consoles would differ) or nobody can give a row that is lacked.
pub(super) fn plan(players: usize, peers: &[PeerState]) -> Result<Plan, String> {
    let start = peers.iter().map(|p| p.remote).max().ok_or("nobody to plan for")?;
    let mut rows: std::collections::BTreeMap<u32, Vec<u16>> = Default::default();
    for p in peers {
        let first = p.remote.saturating_sub(p.tail.len() as u32);
        for (i, row) in p.tail.iter().enumerate() {
            let tick = first + i as u32;
            let words = seat_words(players, p.seat, row);
            match rows.get(&tick) {
                Some(have) if *have != words => {
                    return Err(format!("seat {} and another disagree about tick {tick}: {have:?} / {words:?}", p.seat));
                }
                Some(_) => {}
                None => {
                    rows.insert(tick, words);
                }
            }
        }
    }
    let mut catchup = Vec::new();
    for p in peers {
        let mut lacks = Vec::new();
        for tick in p.remote..start {
            let words = rows
                .get(&tick)
                .ok_or_else(|| format!("nobody can give tick {tick} to seat {}", p.seat))?;
            lacks.push(view_of(p.seat, words));
        }
        catchup.push((p.seat, lacks));
    }
    Ok(Plan { start, catchup })
}

/// Everything the migration needs from the session.
pub(super) struct MigHandle {
    pub(super) end: EndState,
    pub(super) pauses: Arc<Pauses>,
    pub(super) wake: Arc<tokio::sync::Notify>,
    pub(super) cancel: tokio_util::sync::CancellationToken,
    pub(super) completed: Arc<AtomicBool>,
    pub(super) metrics: Arc<super::Metrics>,
    pub(super) event_tx: std::sync::mpsc::Sender<(usize, tango_net::data::Input)>,
    pub(super) local_primed: Arc<AtomicBool>,
    pub(super) mailbox: Arc<Mailbox>,
    pub(super) links: Arc<Mutex<Vec<Arc<tango_net::link::Link>>>>,
    pub(super) group: Arc<SupGroup>,
    pub(super) players: Vec<String>,
    pub(super) my_seat: usize,
    pub(super) seed: [u8; 16],
    pub(super) endpoint: String,
    pub(super) use_relay: Option<bool>,
    pub(super) heartbeat: Duration,
    /// The links a phase made, until `install` takes them.
    pub(super) links_pending: Mutex<Option<Vec<(usize, Arc<tango_net::link::Link>)>>>,
}

/// Start the migration for a room whose host (`old_host`) is gone. The caller has already made the match wait
/// (`Pauses::enter`) and counted this task in the supervisor group (`SupGroup::add`).
pub(super) fn begin(h: Arc<MigHandle>, old_host: usize) {
    tango_platform::spawn(async move {
        let why = match migrate(&h, old_host).await {
            Ok(()) => None,
            Err(e) => Some(e),
        };
        if let Some(why) = why {
            log::warn!("pvp: host migration failed: {why}");
            // As any disconnect: the match is saved for RESUME.
            h.end.note_dropped(h.players.get(old_host).cloned().unwrap_or_default());
            h.end.remote_disconnected.store(true, Ordering::Release);
            *h.end.migrating.lock().unwrap() = None;
            h.cancel.cancel();
            h.pauses.release_all();
            h.wake.notify_one();
        }
        h.group.finish();
    });
}

async fn migrate(h: &Arc<MigHandle>, old_host: usize) -> Result<(), String> {
    let t0 = web_time::Instant::now();
    let name_of = |s: usize| h.players.get(s).cloned().unwrap_or_default();
    let order = successor_order(
        h.players.len(),
        old_host,
        h.end.seats_out.load(Ordering::Acquire),
        h.end.gone.load(Ordering::Acquire),
    );
    log::info!(
        "pvp: host migration: {:?} left; succession {:?} (out {:#04x}, gone {:#04x})",
        name_of(old_host),
        order.iter().map(|&s| name_of(s)).collect::<Vec<_>>(),
        h.end.seats_out.load(Ordering::Acquire),
        h.end.gone.load(Ordering::Acquire)
    );
    if order.is_empty() {
        return Err("nobody is left".into());
    }
    *h.end.migrating.lock().unwrap() = Some((name_of(order[0]), order[0] == h.my_seat));
    h.wake.notify_one();

    // How far this peer got, from the drive thread (which takes in what the old link delivered first).
    h.mailbox.snapshot.lock().unwrap().take();
    h.mailbox.want_snapshot.store(true, Ordering::Release);
    h.wake.notify_one();
    let snapshot = {
        let until = web_time::Instant::now() + SERVE_TIMEOUT;
        loop {
            if let Some(s) = h.mailbox.snapshot.lock().unwrap().take() {
                break s;
            }
            if h.cancel.is_cancelled() || web_time::Instant::now() > until {
                return Err("the drive thread did not answer".into());
            }
            tango_platform::sleep(Duration::from_millis(15)).await;
        }
    };
    log::info!(
        "pvp: host migration: this peer has {} rows of the stream, played {} ticks",
        snapshot.remote,
        snapshot.local
    );

    for (rank, &cand) in order.iter().enumerate().take(RANKS) {
        if h.cancel.is_cancelled() {
            return Err("closed".into());
        }
        *h.end.migrating.lock().unwrap() = Some((name_of(cand), cand == h.my_seat));
        h.wake.notify_one();
        let result = if cand == h.my_seat {
            host_phase(h, rank as u8, old_host, &snapshot).await
        } else {
            guest_phase(h, rank as u8, cand, &snapshot).await
        };
        match result {
            Ok(handover) => {
                install(h, handover, old_host, t0).await?;
                return Ok(());
            }
            Err(PhaseEnd::Refused(why)) => return Err(why),
            Err(PhaseEnd::Failed(why)) => {
                log::warn!("pvp: host migration: candidate {} ({:?}): {why}", rank, name_of(cand));
                // This peer was to host and could not (a living seat did not come): the room cannot go on.
                if cand == h.my_seat {
                    return Err(why);
                }
            }
        }
    }
    Err("no new host could be reached".into())
}

enum PhaseEnd {
    /// The new host turned this peer away: the match goes on without it.
    Refused(String),
    Failed(String),
}

/// The new host: collect the guests on the migration rendezvous and plan.
async fn host_phase(h: &Arc<MigHandle>, rank: u8, old_host: usize, snapshot: &Snapshot) -> Result<Handover, PhaseEnd> {
    let players = h.players.len();
    let me = h.my_seat;
    let gone0 = h.end.gone.load(Ordering::Acquire);
    let out = h.end.seats_out.load(Ordering::Acquire);
    let expected: Vec<usize> = (0..players).filter(|&s| s != me && s != old_host && gone0 & (1 << s) == 0).collect();
    let living: Vec<usize> = expected.iter().copied().filter(|&s| out & (1 << s) == 0).collect();
    let session = tango_net_protocol::derive::derive_migration_session_id(&h.seed, rank);
    log::info!("pvp: host migration: hosting; expecting seats {expected:?} (still in the match: {living:?})");

    // The dial: one at a time (two open dials of one session could pair with each other).
    let stop = tokio_util::sync::CancellationToken::new();
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<(tango_net::channel::Channels, RoomMigrate)>();
    {
        let (endpoint, use_relay, stop, cancel) = (h.endpoint.clone(), h.use_relay, stop.clone(), h.cancel.clone());
        tango_platform::spawn(async move {
            loop {
                if stop.is_cancelled() || cancel.is_cancelled() {
                    return;
                }
                let route = tango_net::connect::Route::Matchmaking {
                    endpoint: &endpoint,
                    session_id: &session,
                    use_relay,
                };
                let opened = tokio::select! {
                    _ = stop.cancelled() => return,
                    _ = cancel.cancelled() => return,
                    r = tango_net::open_channels(route, |_| {}) => r,
                };
                match opened {
                    Ok(mut channels) => {
                        let first = tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await;
                        match first {
                            Ok(Ok(Packet::Room(RoomMsg::Migrate(m)))) => {
                                let _ = tx.send((channels, m));
                            }
                            // (another guest looking for the host too, or noise: let go)
                            _ => {
                                let _ = channels
                                    .control
                                    .0
                                    .send_packet(&Packet::Room(RoomMsg::Reject(RoomReject {
                                        reason: RejectReason::NotTheHost,
                                        text: String::new(),
                                    })))
                                    .await;
                            }
                        }
                    }
                    Err(e) => {
                        log::debug!("pvp: host migration: dial: {e}");
                        tokio::select! {
                            _ = stop.cancelled() => return,
                            _ = tango_platform::sleep(Duration::from_millis(400)) => {}
                        }
                    }
                }
            }
        });
    }

    let deadline = web_time::Instant::now() + RANK_WINDOW;
    let mut peers: Vec<(usize, tango_net::channel::Channels, RoomMigrate)> = Vec::new();
    let mut living_done_at: Option<web_time::Instant> = None;
    loop {
        let have = |s: usize| peers.iter().any(|p| p.0 == s);
        if living.iter().all(|&s| have(s)) {
            if expected.iter().all(|&s| have(s)) {
                break;
            }
            let at = *living_done_at.get_or_insert_with(web_time::Instant::now);
            if at.elapsed() >= OUT_SEATS_GRACE {
                break;
            }
        }
        let now = web_time::Instant::now();
        if now >= deadline || h.cancel.is_cancelled() {
            break;
        }
        let wait = deadline.saturating_duration_since(now).min(Duration::from_millis(100));
        tokio::select! {
            got = rx.recv() => {
                let Some((mut channels, m)) = got else { break };
                let seat = m.seat as usize;
                let valid = m.rank == rank && expected.contains(&seat) && !have(seat);
                if !valid {
                    log::info!("pvp: host migration: turned seat {seat} (rank {}) away", m.rank);
                    let _ = channels.control.0.send_packet(&Packet::Room(RoomMsg::Reject(RoomReject {
                        reason: RejectReason::Started,
                        text: "The match goes on without you.".into(),
                    }))).await;
                    continue;
                }
                log::info!(
                    "pvp: host migration: seat {seat} ({:?}) is here: {} rows, {} played",
                    h.players.get(seat),
                    m.remote,
                    m.local
                );
                peers.push((seat, channels, m));
            }
            _ = tango_platform::sleep(wait) => {}
        }
    }
    stop.cancel();
    if let Some(&missing) = living.iter().find(|&&s| !peers.iter().any(|p| p.0 == s)) {
        return Err(PhaseEnd::Failed(format!("seat {missing} ({:?}) did not come", h.players.get(missing))));
    }
    if peers.is_empty() {
        return Err(PhaseEnd::Failed("no guest came".into()));
    }
    peers.sort_by_key(|p| p.0);

    // Where the stream resumes, and what each peer lacks.
    let mut states = vec![PeerState { seat: me, remote: snapshot.remote, tail: snapshot.tail.clone() }];
    states.extend(peers.iter().map(|p| PeerState { seat: p.0, remote: p.2.remote, tail: p.2.tail.clone() }));
    let plan = plan(players, &states).map_err(PhaseEnd::Failed)?;
    for p in &peers {
        if p.2.local < plan.start {
            return Err(PhaseEnd::Failed(format!("seat {} has played {} ticks, the stream is at {}", p.0, p.2.local, plan.start)));
        }
    }
    let mut gone = gone0 | (1 << old_host);
    for &s in &expected {
        if !peers.iter().any(|p| p.0 == s) {
            gone |= 1 << s;
        }
    }
    let mine = plan.catchup.iter().find(|c| c.0 == me).map(|c| c.1.clone()).unwrap_or_default();
    log::info!(
        "pvp: host migration: the stream resumes at tick {} (this peer lacks {}, guests lack {:?}); gone {:#04x}",
        plan.start,
        mine.len(),
        plan.catchup.iter().filter(|c| c.0 != me).map(|c| (c.0, c.1.len())).collect::<Vec<_>>(),
        gone
    );

    // Links to the guests, each told what it lacks.
    let mut links = Vec::new();
    let mut senders: Vec<Option<tango_net::PvpSender>> = Vec::new();
    let mut in_matches = Vec::new();
    let non_host: Vec<usize> = (0..players).filter(|&s| s != me).collect();
    let mut by_seat: std::collections::HashMap<usize, (Arc<tango_net::link::Link>, tango_net::PvpSender)> = Default::default();
    for (seat, channels, _) in peers {
        let go = RoomMigrateGo {
            start: plan.start,
            host_seat: me as u8,
            gone,
            catchup: plan.catchup.iter().find(|c| c.0 == seat).map(|c| c.1.clone()).unwrap_or_default(),
        };
        let link = link_of(h, channels, Some(Packet::Room(RoomMsg::MigrateGo(go)))).await.map_err(PhaseEnd::Failed)?;
        let sender = tango_net::PvpSender::new(link.in_match().clone());
        by_seat.insert(seat, (link, sender));
    }
    for &s in &non_host {
        match by_seat.remove(&s) {
            Some((link, sender)) => {
                in_matches.push(link.in_match().clone());
                links.push((s, link));
                senders.push(Some(sender));
            }
            None => senders.push(None),
        }
    }
    h.links_pending.lock().unwrap().replace(links);
    Ok(Handover {
        host_seat: me,
        i_host: true,
        gone,
        start: plan.start,
        catchup: mine,
        senders,
        in_matches,
    })
}

/// A guest: find the new host and tell it where this peer is.
async fn guest_phase(h: &Arc<MigHandle>, rank: u8, cand: usize, snapshot: &Snapshot) -> Result<Handover, PhaseEnd> {
    let session = tango_net_protocol::derive::derive_migration_session_id(&h.seed, rank);
    let hello = RoomMigrate {
        seat: h.my_seat as u8,
        rank,
        remote: snapshot.remote,
        local: snapshot.local,
        gone: h.end.gone.load(Ordering::Acquire),
        tail: snapshot.tail.clone(),
    };
    let deadline = web_time::Instant::now() + RANK_WINDOW;
    log::info!("pvp: host migration: dialling {:?} (rank {rank})", h.players.get(cand));
    loop {
        let left = deadline.saturating_duration_since(web_time::Instant::now());
        if left.is_zero() || h.cancel.is_cancelled() {
            return Err(PhaseEnd::Failed(format!("{:?} did not host", h.players.get(cand))));
        }
        let route = tango_net::connect::Route::Matchmaking {
            endpoint: &h.endpoint,
            session_id: &session,
            use_relay: h.use_relay,
        };
        let opened = tokio::select! {
            _ = h.cancel.cancelled() => return Err(PhaseEnd::Failed("closed".into())),
            r = tango_platform::timeout(left.min(Duration::from_secs(8)), tango_net::open_channels(route, |_| {})) => r,
        };
        let mut channels = match opened {
            Ok(Ok(c)) => c,
            Ok(Err(e)) => {
                log::debug!("pvp: host migration: dial: {e}");
                tango_platform::sleep(Duration::from_millis(400)).await;
                continue;
            }
            Err(_) => continue,
        };
        if channels.control.0.send_packet(&Packet::Room(RoomMsg::Migrate(hello.clone()))).await.is_err() {
            continue;
        }
        let first = tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await;
        match first {
            Ok(Ok(Packet::Room(RoomMsg::MigrateGo(go)))) => {
                if snapshot.remote as usize + go.catchup.len() != go.start as usize || go.start > snapshot.local {
                    return Err(PhaseEnd::Failed(format!(
                        "the new host's plan does not fit: have {} rows, it sends {} up to {}, played {}",
                        snapshot.remote,
                        go.catchup.len(),
                        go.start,
                        snapshot.local
                    )));
                }
                let link = link_of(h, channels, None).await.map_err(PhaseEnd::Failed)?;
                let sender = tango_net::PvpSender::new(link.in_match().clone());
                h.links_pending.lock().unwrap().replace(vec![(go.host_seat as usize, link.clone())]);
                return Ok(Handover {
                    host_seat: go.host_seat as usize,
                    i_host: false,
                    gone: go.gone,
                    start: go.start,
                    catchup: go.catchup,
                    senders: vec![Some(sender)],
                    in_matches: vec![link.in_match().clone()],
                });
            }
            Ok(Ok(Packet::Room(RoomMsg::Reject(r)))) => {
                if r.reason == RejectReason::Started {
                    return Err(PhaseEnd::Refused(r.text));
                }
                // another guest, not the host: look again
                tango_platform::sleep(Duration::from_millis(300 + rand::random::<u64>() % 700)).await;
            }
            Ok(Ok(Packet::Room(RoomMsg::Migrate(_)))) => {
                let _ = channels
                    .control
                    .0
                    .send_packet(&Packet::Room(RoomMsg::Reject(RoomReject {
                        reason: RejectReason::NotTheHost,
                        text: String::new(),
                    })))
                    .await;
                tango_platform::sleep(Duration::from_millis(300 + rand::random::<u64>() % 700)).await;
            }
            _ => tango_platform::sleep(Duration::from_millis(400)).await,
        }
    }
}

/// A link over the channels a migration made (the first words, if any, are sent before the link is up).
async fn link_of(
    h: &Arc<MigHandle>,
    channels: tango_net::channel::Channels,
    first: Option<Packet>,
) -> Result<Arc<tango_net::link::Link>, String> {
    let tango_net::channel::Channels {
        control: (mut sender, receiver),
        in_match,
        peer_conn,
        is_offerer: _,
        local_dtls_fingerprint,
        peer_dtls_fingerprint,
    } = channels;
    if let Some(p) = first {
        sender.send_packet(&p).await.map_err(|e| format!("the link broke: {e}"))?;
    }
    let (tx, rx) = tokio::sync::oneshot::channel();
    let _ = tx.send(receiver);
    let session_id = tango_net_protocol::derive::derive_reconnect_session_id(&h.seed, &local_dtls_fingerprint, &peer_dtls_fingerprint);
    let parts = tango_net::link::LinkParts {
        control_sender: Arc::new(tokio::sync::Mutex::new(sender)),
        control_receiver_rx: rx,
        in_match_sender: in_match.0,
        in_match_receiver: in_match.1,
        peer_conn,
        recipe: Some(tango_net::link::ReconnectRecipe::Matchmaking {
            endpoint: h.endpoint.clone(),
            session_id,
            use_relay: h.use_relay,
        }),
        rng_seed: h.seed,
    };
    tango_net::link::Link::bring_up(parts, h.heartbeat, h.cancel.clone())
        .await
        .map(Arc::new)
        .map_err(|e| format!("link: {e}"))
}

/// Give the drive thread the new links, wait for it to take them, and start watching them.
async fn install(h: &Arc<MigHandle>, handover: Handover, old_host: usize, t0: web_time::Instant) -> Result<(), String> {
    let new_links: Vec<(usize, Arc<tango_net::link::Link>)> = h.links_pending.lock().unwrap().take().unwrap_or_default();
    let host_seat = handover.host_seat;
    let i_host = handover.i_host;
    let gone = handover.gone;
    h.mailbox.handover.lock().unwrap().replace(handover);
    h.wake.notify_one();
    let until = web_time::Instant::now() + SERVE_TIMEOUT;
    while h.mailbox.handover.lock().unwrap().is_some() {
        if h.cancel.is_cancelled() || web_time::Instant::now() > until {
            return Err("the drive thread did not take the new links".into());
        }
        tango_platform::sleep(Duration::from_millis(15)).await;
    }
    // The links the session shows, and the supervisors that watch them.
    let all: Vec<Arc<tango_net::link::Link>> = new_links.iter().map(|(_, l)| l.clone()).collect();
    *h.links.lock().unwrap() = all.clone();
    h.end.host_seat.store(host_seat as u8, Ordering::Release);
    h.end.migrations.fetch_add(1, Ordering::AcqRel);
    let players = h.players.len();
    // The event tag of a link: a host's guests are its non-host seats in order, a guest has the one link.
    let non_host: Vec<usize> = (0..players).filter(|&s| s != h.my_seat).collect();
    let room = Arc::new(RoomCtx {
        players: h.players.clone(),
        host_seat,
        is_host: i_host,
        links: all,
        clock: web_time::Instant::now(),
    });
    for (seat, link) in new_links {
        let link_idx = if i_host { non_host.iter().position(|&s| s == seat).unwrap_or(0) } else { 0 };
        let in_match = link.in_match().clone();
        h.group.add();
        spawn_supervisor(SupervisorContext {
            link,
            in_match,
            link_idx,
            peer_seat: seat,
            event_tx: h.event_tx.clone(),
            end: h.end.clone(),
            completed: h.completed.clone(),
            cancel: h.cancel.clone(),
            metrics: h.metrics.clone(),
            pauses: h.pauses.clone(),
            wake: h.wake.clone(),
            room: Some(room.clone()),
            last_rx: Arc::new(std::sync::atomic::AtomicU64::new(0)),
            local_primed: h.local_primed.clone(),
            group: h.group.clone(),
            mig: Some(h.clone()),
        });
    }
    *h.end.migrating.lock().unwrap() = None;
    h.pauses.leave();
    h.wake.notify_one();
    log::info!(
        "pvp: host migration done in {:?}: {:?} (seat {host_seat}) hosts{}, seat {old_host} gone (gone mask {:#04x})",
        t0.elapsed(),
        h.players.get(host_seat),
        if i_host { " (this peer)" } else { "" },
        gone
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(view: &[u16], own: u16) -> MigrateRow {
        let mut v = [0u16; 4];
        v[..view.len()].copy_from_slice(view);
        MigrateRow { view: v, own }
    }

    #[test]
    fn the_successor_is_the_lowest_seat_still_in_the_match() {
        // host 0 left; seat 1 is out, seat 2 is in: seat 2 hosts, then seat 1
        assert_eq!(successor_order(3, 0, 0b010, 0), vec![2, 1]);
        // all in: the lowest seat
        assert_eq!(successor_order(5, 0, 0, 0), vec![1, 2, 3, 4]);
        // the host was not seat 0, and a seat that left earlier is not a candidate
        assert_eq!(successor_order(5, 2, 0b00001, 0b00010), vec![3, 4, 0]);
        // everyone left is out: still the lowest seat
        assert_eq!(successor_order(3, 0, 0b110, 0), vec![1, 2]);
        // a room of two has no successor but the guest itself
        assert_eq!(successor_order(2, 0, 0, 0), vec![1]);
    }

    /// Every peer computes the order from what it knows alone: the same input gives the same order.
    #[test]
    fn every_peer_picks_the_same_host() {
        for players in 3..=5usize {
            for host in 0..players {
                for out in 0u8..(1 << players) {
                    let a = successor_order(players, host, out, 0);
                    let b = successor_order(players, host, out, 0);
                    assert_eq!(a, b);
                    assert!(!a.contains(&host));
                    // those in the match come before those out
                    let first_out = a.iter().position(|&s| out & (1 << s) != 0).unwrap_or(a.len());
                    assert!(a[first_out..].iter().all(|&s| out & (1 << s) != 0));
                }
            }
        }
    }

    /// Three seats, old host 0. Seat 1 has taken in 10 rows, seat 2 12: the stream resumes at 12; seat 1 is given the
    /// two rows it lacks as its own view of them (the words of seats 0 and 2).
    #[test]
    fn the_peer_ahead_gives_the_rows_the_others_lack() {
        // the truth: tick t has words [100 + t, 200 + t, 300 + t] for seats 0, 1, 2
        let word = |t: u32, s: usize| (100 * (s as u32 + 1) + t) as u16;
        let row_of = |seat: usize, t: u32| {
            let view: Vec<u16> = (0..3).filter(|&s| s != seat).map(|s| word(t, s)).collect();
            row(&view, word(t, seat))
        };
        let tail = |seat: usize, remote: u32| (remote - 8..remote).map(|t| row_of(seat, t)).collect::<Vec<_>>();
        let peers = [
            PeerState { seat: 1, remote: 10, tail: tail(1, 10) },
            PeerState { seat: 2, remote: 12, tail: tail(2, 12) },
        ];
        let p = plan(3, &peers).unwrap();
        assert_eq!(p.start, 12);
        assert_eq!(p.catchup[1], (2, vec![]));
        let lacks = &p.catchup[0].1;
        assert_eq!(p.catchup[0].0, 1);
        assert_eq!(lacks.len(), 2);
        for (i, v) in lacks.iter().enumerate() {
            let t = 10 + i as u32;
            assert_eq!(v[..2], [word(t, 0), word(t, 2)], "seat 1 hears seats 0 and 2 for tick {t}");
        }
    }

    /// The host that took over lags behind a guest: it is given the rows too, from the guest's view plus the guest's
    /// own word, with its own seat left out.
    #[test]
    fn the_new_host_can_lack_rows_too() {
        let word = |t: u32, s: usize| (10 * (s as u32 + 1) + t % 7) as u16;
        let row_of = |seat: usize, t: u32| {
            let view: Vec<u16> = (0..4).filter(|&s| s != seat).map(|s| word(t, s)).collect();
            row(&view, word(t, seat))
        };
        let tail = |seat: usize, remote: u32| (remote - 5..remote).map(|t| row_of(seat, t)).collect::<Vec<_>>();
        let peers = [
            PeerState { seat: 1, remote: 20, tail: tail(1, 20) },
            PeerState { seat: 2, remote: 23, tail: tail(2, 23) },
            PeerState { seat: 3, remote: 21, tail: tail(3, 21) },
        ];
        let p = plan(4, &peers).unwrap();
        assert_eq!(p.start, 23);
        for (seat, lacks) in &p.catchup {
            let remote = peers.iter().find(|x| x.seat == *seat).unwrap().remote;
            assert_eq!(lacks.len() as u32, 23 - remote);
            for (i, v) in lacks.iter().enumerate() {
                let t = remote + i as u32;
                let want: Vec<u16> = (0..4).filter(|s| s != seat).map(|s| word(t, s)).collect();
                assert_eq!(v[..3], want[..], "seat {seat} tick {t}");
            }
        }
    }

    #[test]
    fn peers_that_disagree_about_a_tick_are_caught() {
        let a = PeerState { seat: 1, remote: 3, tail: vec![row(&[1, 2], 3); 3] };
        // seat 2 says seat 1's word was different
        let b = PeerState { seat: 2, remote: 3, tail: vec![row(&[1, 9], 2); 3] };
        assert!(plan(3, &[a, b]).is_err());
    }

    #[test]
    fn a_row_nobody_has_cannot_be_given() {
        let a = PeerState { seat: 1, remote: 3, tail: vec![] };
        let b = PeerState { seat: 2, remote: 9, tail: vec![row(&[0, 0], 0); 2] };
        let e = plan(3, &[a, b]).unwrap_err();
        assert!(e.contains("nobody can give"), "{e}");
    }

    #[test]
    fn equal_streams_need_no_catch_up() {
        let a = PeerState { seat: 1, remote: 50, tail: vec![] };
        let b = PeerState { seat: 2, remote: 50, tail: vec![] };
        let p = plan(3, &[a, b]).unwrap();
        assert_eq!(p.start, 50);
        assert!(p.catchup.iter().all(|c| c.1.is_empty()));
    }
}
