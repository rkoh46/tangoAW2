//! Network readiness, receive pumping, reconnection, and orderly shutdown.

use super::silence::{self, SilenceWatch};
use super::{EndState, Metrics};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// Session-redraw cadence while reconnecting (~30 fps), so the give-up progress
/// bar drains smoothly even though the paused drive loop emits no frames. Purely
/// cosmetic.
const RECONNECT_UI_TICK: std::time::Duration = std::time::Duration::from_millis(33);

/// Grace window after a successful reconnect during which the stall watchdog
/// is suppressed. On reconnect the local input queue is still pegged at
/// [`tango_net::data::RECONNECT_QUEUE_LENGTH`] — that's *why* we reconnected
/// — and the resumed drive loop only drains it back down as the peer's resent
/// window arrives. Without this grace the still-high `queue_len` would re-trip
/// the stall the instant the supervisor loops back, re-pausing the drive loop
/// before it could ingest a single resend: the transport renegotiates forever
/// while the sim never resumes. The grace ends early the moment the queue
/// recovers (drops below the threshold); the deadline only bounds the wait so
/// a reconnect that genuinely fails to recover still re-trips.
const RECONNECT_DRAIN_GRACE: std::time::Duration = std::time::Duration::from_secs(5);

// ---------------------------------------------------------------------------
// The ready gate's announcer.

/// Tell the peer our pair is primed, once the boot says so.
///
/// A task of its own because the boot is synchronous and the host
/// chooses where it runs — a blocking thread on the desktop, the event
/// loop in a browser — so it can't await a send itself.
pub(super) fn spawn_primed_announcer(
    link: Arc<tango_net::link::Link>,
    local_primed: Arc<AtomicBool>,
    announce: Arc<tokio::sync::Notify>,
    end: EndState,
    cancel: tokio_util::sync::CancellationToken,
) {
    tango_platform::spawn(async move {
        while !local_primed.load(Ordering::Acquire) {
            tokio::select! {
                _ = cancel.cancelled() => return,
                // `notify_one` before the first `notified()` still wakes
                // it: Notify holds the permit. Re-checking the flag on
                // each pass is what makes the ordering irrelevant.
                _ = announce.notified() => {}
            }
        }
        match link.send_primed().await {
            Ok(()) => log::info!("pvp: announced primed"),
            Err(e) => {
                // The control channel is reliable and ordered, so this
                // only fails when it is dead or dying — its status
                // settled to Error/Closed, or libdatachannel refused the
                // write. There is nothing to retry into: the peer's gate
                // never opens without this packet, and a gate that never
                // opens is a match that hangs with both sides idle. End
                // it as the disconnect it is.
                log::warn!("pvp: could not announce primed, ending match: {e}");
                end.remote_disconnected.store(true, Ordering::Release);
                cancel.cancel();
            }
        }
    });
}

/// A room's host tells every guest it is primed, once it is and every guest has said it is (so no guest ticks
/// before the others are ready to).
pub(super) fn spawn_room_primed_announcer(
    links: Vec<Arc<tango_net::link::Link>>,
    local_primed: Arc<AtomicBool>,
    announce: Arc<tokio::sync::Notify>,
    end: EndState,
    cancel: tokio_util::sync::CancellationToken,
) {
    tango_platform::spawn(async move {
        while !local_primed.load(Ordering::Acquire) {
            tokio::select! {
                _ = cancel.cancelled() => return,
                _ = announce.notified() => {}
            }
        }
        loop {
            if links.iter().all(|l| l.peer_primed().load(Ordering::Acquire)) {
                break;
            }
            tokio::select! {
                _ = cancel.cancelled() => return,
                _ = tango_platform::sleep(std::time::Duration::from_millis(20)) => {}
            }
        }
        for link in &links {
            if let Err(e) = link.send_primed().await {
                log::warn!("pvp: could not announce primed, ending match: {e}");
                end.remote_disconnected.store(true, Ordering::Release);
                cancel.cancel();
                return;
            }
        }
        log::info!("pvp: announced primed to the room");
    });
}

// ---------------------------------------------------------------------------
// The receive pump + link supervisor.

/// The supervisors a session has, counted: its `done` token is cancelled when the last one has finished (a host
/// migration replaces the supervisors, and counts its own task until the new ones are up).
pub(super) struct SupGroup {
    n: std::sync::atomic::AtomicUsize,
    done: tokio_util::sync::CancellationToken,
}

impl SupGroup {
    pub(super) fn new(done: tokio_util::sync::CancellationToken) -> Self {
        SupGroup { n: Default::default(), done }
    }
    pub(super) fn add(&self) {
        self.n.fetch_add(1, Ordering::AcqRel);
    }
    pub(super) fn finish(&self) {
        if self.n.fetch_sub(1, Ordering::AcqRel) <= 1 {
            self.done.cancel();
        }
    }
}

pub(super) struct SupervisorContext {
    pub(super) link: Arc<tango_net::link::Link>,
    pub(super) in_match: tango_net::InMatchTx,
    /// Which of the session's links this one is (what its inputs are tagged with).
    pub(super) link_idx: usize,
    /// The seat of the peer on this link.
    pub(super) peer_seat: usize,
    pub(super) event_tx: std::sync::mpsc::Sender<(usize, tango_net::data::Input)>,
    pub(super) end: EndState,
    pub(super) completed: Arc<AtomicBool>,
    pub(super) cancel: tokio_util::sync::CancellationToken,
    pub(super) metrics: Arc<Metrics>,
    pub(super) pauses: Arc<Pauses>,
    pub(super) wake: Arc<tokio::sync::Notify>,
    /// A room's players and links (`None`: a plain two-player match).
    pub(super) room: Option<Arc<RoomCtx>>,
    /// When this link's peer was last heard from (milliseconds on the room's clock, [`RoomCtx::clock`]).
    pub(super) last_rx: Arc<std::sync::atomic::AtomicU64>,
    /// Whether our own pair is primed, so a reconnect can re-announce it
    /// (the rebuild drops anything the old transport hadn't delivered).
    pub(super) local_primed: Arc<AtomicBool>,
    /// Process-exit waiter, cancelled after the bounded quit announcement and
    /// the rest of supervisor teardown have completed (when the last supervisor has).
    pub(super) group: Arc<SupGroup>,
    /// A room of more than two: what a host migration needs (the guests' supervisor of the host's link starts one).
    pub(super) mig: Option<Arc<super::migrate::MigHandle>>,
}

/// How long a link's peer has been silent before a full input queue counts as a dead link, in a room. The host
/// decides first (and tells the guests why the match went quiet, [`RoomMsg::Hold`]); a guest waits longer for that.
const STALL_QUIET_HOST: std::time::Duration = std::time::Duration::from_secs(3);
const STALL_QUIET_GUEST: std::time::Duration = std::time::Duration::from_secs(7);

/// How long past the window a returning player who is being let in is waited for.
const REJOIN_EXTRA: std::time::Duration = std::time::Duration::from_secs(25);

/// The match is paused while anyone is waited for: the drive loop's gate, held by as many reasons as there are
/// (a link of ours being rebuilt, a player the host says it is waiting for), released with the last.
pub(super) struct Pauses {
    n: std::sync::Mutex<u32>,
    gate: Arc<crate::PauseGate>,
}

impl Pauses {
    pub(super) fn new(gate: Arc<crate::PauseGate>) -> Self {
        Pauses { n: Default::default(), gate }
    }
    pub(super) fn enter(&self) {
        *self.n.lock().unwrap() += 1;
        self.gate.set(true);
    }
    pub(super) fn leave(&self) {
        let mut n = self.n.lock().unwrap();
        *n = n.saturating_sub(1);
        if *n == 0 {
            self.gate.set(false);
        }
    }
    /// Teardown: let the drive loop go whatever is held.
    pub(super) fn release_all(&self) {
        *self.n.lock().unwrap() = 0;
        self.gate.set(false);
    }
}

/// A room's players as the supervisors see them.
pub(super) struct RoomCtx {
    /// Gamertags in seat order.
    pub(super) players: Vec<String>,
    pub(super) host_seat: usize,
    pub(super) is_host: bool,
    /// Every link of the session, in order (a host's: one to each guest by ascending seat).
    pub(super) links: Vec<Arc<tango_net::link::Link>>,
    pub(super) clock: web_time::Instant,
}

impl RoomCtx {
    /// The seat of the peer on link `idx`.
    pub(crate) fn seat_of_link(&self, idx: usize) -> usize {
        if self.is_host {
            (0..self.players.len()).filter(|&s| s != self.host_seat).nth(idx).unwrap_or(0)
        } else {
            self.host_seat
        }
    }
}

/// Pump one receiver until error/EOF, forwarding events to the drive
/// thread. Returns when the channel dies (the reconnect decision is the
/// supervisor's).
async fn run_receive_pump(
    mut receiver: tango_net::PvpReceiver,
    link_idx: usize,
    event_tx: std::sync::mpsc::Sender<(usize, tango_net::data::Input)>,
    wake: Arc<tokio::sync::Notify>,
    last_rx: Option<(Arc<std::sync::atomic::AtomicU64>, web_time::Instant)>,
) -> std::io::Error {
    loop {
        match receiver.receive().await {
            Ok(input) => {
                if let Some((at, clock)) = last_rx.as_ref() {
                    at.store(clock.elapsed().as_millis() as u64, Ordering::Relaxed);
                }
                if event_tx.send((link_idx, input)).is_err() {
                    return std::io::Error::new(std::io::ErrorKind::BrokenPipe, "drive thread gone");
                }
                // Remote inputs settle ticks; make sure a paused/idle UI
                // still observes progress.
                wake.notify_one();
            }
            Err(e) => return e,
        }
    }
}

/// Receive loop + link supervisor. Reads peer frames into the drive
/// thread's queue until the match ends (completion / cancel) or, when the
/// link drops, until reconnection gives up. Policy lives here — deciding
/// when a trip is worth reconnecting and freezing/unfreezing the drive
/// loop around the attempt. The transport surgery (silent teardown,
/// rebuild, hot-swap under the persistent rennet streams) is
/// [`tango_net::link::Link::reconnect`]'s; the lockstep sim treats the
/// whole gap as a pause, so no state resync is needed.
pub(super) fn spawn_supervisor(ctx: SupervisorContext) {
    let SupervisorContext {
        link,
        in_match,
        link_idx,
        event_tx,
        end,
        completed,
        cancel,
        metrics,
        pauses,
        wake,
        room,
        last_rx,
        local_primed,
        group,
        mig,
        peer_seat,
    } = ctx;

    let make_receiver = {
        let link = link.clone();
        let in_match = in_match.clone();
        let end = end.clone();
        let wake = wake.clone();
        let last_rx = last_rx.clone();
        let clock = room.as_ref().map(|r| r.clock);
        move || -> Option<tango_net::PvpReceiver> {
            let rx = tango_net::PvpReceiver::new(
                link.take_match_receiver()?,
                in_match.clone(),
                link.latency_handle(),
                end.remote_ended.clone(),
                wake.clone(),
            );
            // (any frame is a sign of life: inputs, and the bare acks of the peer's keepalive heartbeat)
            Some(match clock {
                Some(c) => {
                    let last_rx = last_rx.clone();
                    rx.with_frame_hook(move || last_rx.store(c.elapsed().as_millis() as u64, Ordering::Relaxed))
                }
                None => rx,
            })
        }
    };

    tango_platform::spawn(async move {
        // Why the receive loop ended this iteration.
        enum Trip {
            /// Clean local teardown (user closed / cancelled). Announces the
            /// quit to the peer (best-effort `Goodbye`), never reconnects.
            Cancelled,
            /// The peer announced a deliberate quit (the control channel's
            /// `Goodbye`): it is leaving and will never be at a rendezvous,
            /// so the match ends at once — no reconnect window at all.
            PeerQuit,
            /// A channel hit EOF without a goodbye — the peer's reconnect
            /// dropping its old transport (libdatachannel closes gracefully;
            /// there is no silent teardown), its transport declaring the
            /// link dead, or a quit whose goodbye was lost. An unannounced
            /// close is treated as recoverable link loss and gets the normal
            /// per-transport reconnect window.
            Closed,
            /// The local input queue climbed to `RECONNECT_QUEUE_LENGTH`:
            /// the peer stopped matching our inputs, i.e. a quiet/dead link.
            /// Reconnects on the full per-transport window.
            Stalled,
            /// A room notice arrived (the host says who the match is waiting for).
            Notice,
            /// A room: no frame from the peer for [`silence::SILENT_AFTER`] while its connection is still open (a frozen
            /// app, a sleeping machine). The reconnect box comes up and the match waits for the peer's frames to come
            /// back before the transport is rebuilt.
            Silent,
            /// The silent peer's frames are back: the box goes away and the match goes on.
            Resumed,
        }

        /// The box for a silent peer is up and its frames are awaited.
        struct SilentHold {
            lost_ms: u64,
            since: web_time::Instant,
            deadline: web_time::Instant,
            announce_stop: tokio_util::sync::CancellationToken,
        }

        let clock = room.as_ref().map(|r| r.clock);
        let rx_tag = || clock.map(|c| (last_rx.clone(), c));
        let peer_seat = peer_seat as u8;
        let peer_name = room.as_ref().and_then(|r| r.players.get(peer_seat as usize).cloned()).unwrap_or_default();
        let quiet = match room.as_ref() {
            Some(r) if r.is_host => STALL_QUIET_HOST,
            Some(_) => STALL_QUIET_GUEST,
            None => std::time::Duration::ZERO,
        };
        // The other guests' links (a room's host): who to tell what it waits for.
        let others: Vec<Arc<tango_net::link::Link>> = match room.as_ref() {
            Some(r) if r.is_host => r
                .links
                .iter()
                .filter(|l| !Arc::ptr_eq(l, &link))
                .cloned()
                .collect(),
            _ => Vec::new(),
        };
        let notice_wake = link.notice_wake();
        // Seats the host told us it waits for (each holds a pause).
        let mut notice_held: std::collections::HashSet<u8> = Default::default();

        let mut silence = clock.map(|c| SilenceWatch::new(c.elapsed().as_millis() as u64));
        let mut silent: Option<SilentHold> = None;
        // The match waits for this peer: the box, the pause, and (a room's host) the word to the other guests.
        let begin_hold = |timeout: std::time::Duration| -> tokio_util::sync::CancellationToken {
            end.hold_add(peer_seat, peer_name.clone(), web_time::Instant::now() + timeout);
            // (a room's guest waiting for its host: the box says the room goes on without it, not that the match is saved)
            end.host_wait
                .store(mig.is_some() && room.as_ref().is_some_and(|r| !r.is_host && r.players.len() >= 2), Ordering::Release);
            pauses.enter();
            wake.notify_one();
            // A room's host tells the other guests who the match waits for, about once a second.
            let announce_stop = tokio_util::sync::CancellationToken::new();
            if !others.is_empty() {
                let others = others.clone();
                let stop = announce_stop.clone();
                let session = cancel.clone();
                let name = peer_name.clone();
                let deadline = web_time::Instant::now() + timeout;
                tango_platform::spawn(async move {
                    loop {
                        let left = deadline.saturating_duration_since(web_time::Instant::now());
                        tell_others(
                            &others,
                            RoomMsgOut::Hold(peer_seat, name.clone(), left.as_millis().min(u32::MAX as u128) as u32),
                        )
                        .await;
                        tokio::select! {
                            _ = stop.cancelled() => return,
                            _ = session.cancelled() => return,
                            _ = tango_platform::sleep(std::time::Duration::from_secs(1)) => {}
                        }
                    }
                });
            }
            announce_stop
        };

        let mut pump = Box::pin(run_receive_pump(
            make_receiver().expect("bring_up parks the in-match receiver"),
            link_idx,
            event_tx.clone(),
            wake.clone(),
            rx_tag(),
        ));
        let mut watch = Some(Box::pin(link.watch_control()));
        // Set after each successful reconnect to `now + RECONNECT_DRAIN_GRACE`:
        // the stall watch stays quiet until the queue recovers or this passes,
        // so the just-reconnected (still-full) queue can't instantly re-trip.
        let mut drain_until: Option<web_time::Instant> = None;
        loop {
            // The stall watch: poll the drive thread's published queue
            // length. Coarse (10 Hz) is fine — the queue takes seconds to
            // climb to the trip point. A queue below the threshold clears any
            // post-reconnect drain grace (the link recovered); a queue at or
            // above it trips a stall — unless we're still inside the grace,
            // where a high queue is the expected pre-drain state. In a room
            // the queue is shared by every link, so a stall also needs this
            // link's peer to have gone quiet (and nobody to be waited for
            // already): the silent one is the one to rebuild.
            let stall_watch = async {
                loop {
                    let queue_len = metrics.queue_len.load(Ordering::Relaxed) as usize;
                    if queue_len < tango_net::data::RECONNECT_QUEUE_LENGTH {
                        drain_until = None;
                    } else if clock.is_none() && drain_until.is_none_or(|t| web_time::Instant::now() >= t) {
                        // (a room never calls a slow or busy peer dead: only the transport closing, or its own
                        // dead-peer timeout, starts the wait for a player to reconnect)
                        let silent = clock.is_none_or(|c| {
                            let now = c.elapsed().as_millis() as u64;
                            now.saturating_sub(last_rx.load(Ordering::Relaxed)) >= quiet.as_millis() as u64
                        });
                        if silent && !end.any_hold() {
                            return;
                        }
                    }
                    tango_platform::sleep(std::time::Duration::from_millis(100)).await;
                }
            };
            // The silence watch (a room): first the peer's frames stopping, then (box up) their coming back or the
            // window for that running out.
            let silence_watch = async {
                let Some(c) = clock else { return std::future::pending::<Trip>().await };
                match silent.as_ref() {
                    None => {
                        let sw = silence.as_mut().expect("a room has its silence watch");
                        loop {
                            let now = c.elapsed().as_millis() as u64;
                            let lost = sw.lost(now, last_rx.load(Ordering::Relaxed));
                            if lost
                                && !completed.load(Ordering::Acquire)
                                && !end.remote_ended.load(Ordering::Acquire)
                                && !end.aborted.load(Ordering::Acquire)
                            {
                                return Trip::Silent;
                            }
                            tango_platform::sleep(silence::POLL).await;
                        }
                    }
                    Some(s) => loop {
                        if SilenceWatch::heard_since(last_rx.load(Ordering::Relaxed), s.lost_ms) {
                            return Trip::Resumed;
                        }
                        if s.since.elapsed() >= silence::RESUME_WINDOW {
                            return Trip::Stalled;
                        }
                        tango_platform::sleep(silence::POLL).await;
                    },
                }
            };
            let trip = tokio::select! {
                biased;
                _ = cancel.cancelled() => Trip::Cancelled,
                ctl = async { watch.as_mut().expect("the watch is up").await } => match ctl {
                    tango_net::link::ControlEnd::Goodbye => {
                        log::info!("pvp: peer announced a quit");
                        Trip::PeerQuit
                    }
                    tango_net::link::ControlEnd::Eof => Trip::Closed,
                },
                e = &mut pump => {
                    log::info!("pvp in-match channel closed: {e:?}");
                    Trip::Closed
                }
                _ = notice_wake.notified() => Trip::Notice,
                _ = stall_watch => Trip::Stalled,
                t = silence_watch => t,
            };

            if matches!(trip, Trip::Resumed) {
                if let Some(s) = silent.take() {
                    s.announce_stop.cancel();
                }
                end.hold_remove(peer_seat);
                pauses.leave();
                tell_others(&others, RoomMsgOut::Unhold(peer_seat)).await;
                drain_until = Some(web_time::Instant::now() + RECONNECT_DRAIN_GRACE);
                if let (Some(sw), Some(c)) = (silence.as_mut(), clock) {
                    *sw = SilenceWatch::new(c.elapsed().as_millis() as u64);
                }
                wake.notify_one();
                log::info!("pvp: {peer_name:?} is heard from again: the match goes on");
                continue;
            }

            if matches!(trip, Trip::Notice) {
                for msg in link.take_notices() {
                    use tango_net_protocol::control::RoomMsg;
                    match msg {
                        RoomMsg::Hold(h) => {
                            end.hold_add(h.seat, h.name, web_time::Instant::now() + std::time::Duration::from_millis(h.left_ms as u64));
                            if notice_held.insert(h.seat) {
                                pauses.enter();
                            }
                        }
                        RoomMsg::Unhold { seat } => {
                            end.hold_remove(seat);
                            if notice_held.remove(&seat) {
                                pauses.leave();
                                drain_until = Some(web_time::Instant::now() + RECONNECT_DRAIN_GRACE);
                            }
                        }
                        RoomMsg::GiveUp { name, .. } => end.note_dropped(name),
                        RoomMsg::Gone { seats } => {
                            end.gone.fetch_or(seats, Ordering::AcqRel);
                        }
                        _ => {}
                    }
                }
                wake.notify_one();
                continue;
            }

            // Our own deliberate close: announce it, then stop. The
            // session's teardown drops the peer connection gracefully, and
            // its DTLS close_notify hands the peer a prompt EOF — but that
            // EOF alone is ambiguous over there (our reconnect's transport
            // drop looks identical), so send the goodbye first to let the
            // peer end at once instead of entering its reconnect path on us.
            // Best-effort: if it's lost, ordinary reconnect is the fallback.
            if matches!(trip, Trip::Cancelled) {
                if let Some(s) = silent.take() {
                    s.announce_stop.cancel();
                }
                // (a session that a rejoin replaces is no leaving: the others' sessions are being replaced too, and a goodbye would
                // have the host yield this player's army while the way back is being made)
                if !end.swapped.load(Ordering::Acquire) {
                    link.send_goodbye().await;
                }
                break;
            }

            // A room's guest whose HOST is gone: the room goes on under a successor (see `migrate`). A host that is out
            // of the match already has nothing to come back for: its leaving, its connection closing or its going
            // quiet starts the migration at once. A host that is still playing and tells us it is leaving does the same
            // (its army is yielded by the console, see `migrate`); one that is simply lost gets the reconnect window
            // below first and the migration after it.
            let host_link = mig.is_some()
                && room.as_ref().is_some_and(|r| !r.is_host && r.players.len() >= 2);
            let host_out = super::is_out(end.seats_out.load(Ordering::Acquire), peer_seat);
            if host_link
                && matches!(trip, Trip::PeerQuit | Trip::Closed | Trip::Stalled | Trip::Silent)
                && !completed.load(Ordering::Acquire)
                && !end.remote_ended.load(Ordering::Acquire)
                && !end.aborted.load(Ordering::Acquire)
                && (host_out || matches!(trip, Trip::PeerQuit))
            {
                log::info!(
                    "pvp: the host {peer_name:?} is gone{}: the room goes on without it",
                    if host_out { " after being out of the match" } else { " (it left)" }
                );
                let m = mig.clone().expect("a host link has its migration");
                // (the migration holds the match from here; what this supervisor held is let go after)
                m.pauses.enter();
                m.group.add();
                if let Some(s) = silent.take() {
                    s.announce_stop.cancel();
                    pauses.leave();
                }
                end.hold_remove(peer_seat);
                for seat in notice_held.drain() {
                    end.hold_remove(seat);
                    pauses.leave();
                }
                drop(pump);
                drop(watch);
                link.send_goodbye().await;
                link.retire_latency();
                super::migrate::begin(m, peer_seat as usize);
                group.finish();
                return;
            }
            // Reconnect on any mid-match link loss — a stalled input queue
            // *or* a bare channel close — as long as the transport can
            // rebuild and the match isn't ending (our completion, the
            // peer's EndOfMatch, or an in-game abort). An announced quit
            // (`PeerQuit`) never reconnects — the peer told us it isn't
            // coming back; every unannounced loss uses the normal transport
            // budget.
            // A player that is out of the match leaves it without ending it (a room's host: the others play on, that seat's
            // input is idle from now on; no pause, no countdown, no saved match).
            if matches!(trip, Trip::PeerQuit | Trip::Closed | Trip::Stalled | Trip::Silent)
                && !completed.load(Ordering::Acquire)
                && !end.remote_ended.load(Ordering::Acquire)
                && !end.aborted.load(Ordering::Acquire)
                && end.benign_drop(room.as_ref().is_some_and(|r| r.is_host), peer_seat)
            {
                log::info!("pvp: {peer_name:?} left after being out of the match: the match goes on without it");
                end.given_up.lock().unwrap().push(link.clone());
                end.note_gone(peer_seat);
                wake.notify_one();
                drop(watch);
                link.retire_latency();
                // (the other guests are told: should the host go, they all know who is left)
                tell_others(&others, RoomMsgOut::Gone(end.gone.load(Ordering::Acquire))).await;
                group.finish();
                return;
            }
            // A room's host whose guest drops while a battle is on: the guest gets the reconnect window like a host that is still
            // playing; when it runs out (or the guest said it is leaving, or there is nothing to rebuild) the guest's armies
            // yield, driven by the console, and the match goes on without it: no save, no end.
            let ended = completed.load(Ordering::Acquire) || end.remote_ended.load(Ordering::Acquire) || end.aborted.load(Ordering::Acquire);
            let yieldable = !ended
                && matches!(trip, Trip::PeerQuit | Trip::Closed | Trip::Stalled | Trip::Silent)
                && end.yieldable(room.as_ref().is_some_and(|r| r.is_host));
            if yieldable && (matches!(trip, Trip::PeerQuit) || !link.can_reconnect()) {
                log::info!(
                    "pvp: {peer_name:?} {}: its army yields, the match goes on without it",
                    if matches!(trip, Trip::PeerQuit) { "left" } else { "is gone for good" }
                );
                if let Some(s) = silent.take() {
                    s.announce_stop.cancel();
                    pauses.leave();
                }
                end.hold_remove(peer_seat);
                for seat in notice_held.drain() {
                    end.hold_remove(seat);
                    pauses.leave();
                }
                seat_yields(&end, &wake, &others, peer_seat, &link).await;
                drop(watch);
                link.retire_latency();
                group.finish();
                return;
            }
            let reconnectable = matches!(trip, Trip::Stalled | Trip::Closed | Trip::Silent)
                && link.can_reconnect()
                && !completed.load(Ordering::Acquire)
                && !end.remote_ended.load(Ordering::Acquire)
                && !end.aborted.load(Ordering::Acquire);
            if !reconnectable {
                // An in-game abort ends BOTH sessions from their own
                // simulations at (nearly) the same instant — the peer's
                // teardown racing ours to the wire (its goodbye, its
                // channel's EOF) is expected, not a disconnect, so don't
                // dress the end as one.
                if !end.aborted.load(Ordering::Acquire) {
                    end.remote_disconnected.store(true, Ordering::Release);
                    if !completed.load(Ordering::Acquire) && !end.remote_ended.load(Ordering::Acquire) {
                        end.note_dropped(peer_name.clone());
                        // (the other guests hear who it was before the host's own goodbye)
                        tell_others(&others, RoomMsgOut::GiveUp(peer_seat, peer_name.clone())).await;
                    }
                }
                if let Some(s) = silent.take() {
                    s.announce_stop.cancel();
                }
                cancel.cancel();
                break;
            }

            // The peer went quiet with its connection open: the box comes up now, its frames are awaited for a while
            // (the rebuild below follows if they do not come), and the grace runs from here.
            if matches!(trip, Trip::Silent) {
                let lost_ms = clock.map_or(0, |c| c.elapsed().as_millis() as u64);
                log::info!(
                    "pvp: nothing from {peer_name:?} for {:?} (last at {} ms, now {lost_ms} ms): waiting for it",
                    silence::SILENT_AFTER,
                    last_rx.load(Ordering::Relaxed)
                );
                for seat in notice_held.drain() {
                    end.hold_remove(seat);
                    pauses.leave();
                }
                let timeout = link.reconnect_timeout().unwrap_or_default();
                let announce_stop = begin_hold(timeout);
                let now = web_time::Instant::now();
                silent = Some(SilentHold { lost_ms, since: now, deadline: now + timeout, announce_stop });
                continue;
            }

            // Freeze the drive loop so its speculative lead can't run past
            // the rollback horizon while the link is down. Both peers
            // converge on the rebuild: whoever trips first goes silent,
            // which stall-trips the other within RECONNECT_QUEUE_LENGTH
            // frames.
            // (what the host told us about someone else is moot now: it is the host we wait for)
            for seat in notice_held.drain() {
                end.hold_remove(seat);
                pauses.leave();
            }
            // The control watch holds the control receiver; the rebuild replaces it.
            watch = None;
            let (timeout, announce_stop) = match silent.take() {
                // (the box has been up since the peer went quiet: the grace runs on from there)
                Some(sh) => (sh.deadline.saturating_duration_since(web_time::Instant::now()), sh.announce_stop),
                None => {
                    let timeout = link.reconnect_timeout().unwrap_or_default();
                    let stop = begin_hold(timeout);
                    (timeout, stop)
                }
            };
            log::info!("pvp link dropped — pausing to reconnect (waiting for {peer_name:?})");

            // Rebuild + hot-swap (the link's job), ticking the UI at
            // ~30 fps so the give-up bar drains smoothly while the paused
            // drive loop produces no frames.
            let restored = {
                let ui_tick = async {
                    let mut iv = tango_platform::Ticker::immediate(RECONNECT_UI_TICK);
                    loop {
                        iv.tick().await;
                        wake.notify_one();
                    }
                };
                let watchdog_done = tokio_util::sync::CancellationToken::new();
                // (a room's guest waiting for its host does not end the match when the window runs out: the room goes on
                // without the host, see below)
                if !host_link && !yieldable {
                    let end = end.clone();
                    let cancel = cancel.clone();
                    let pauses_w = pauses.clone();
                    let wake = wake.clone();
                    let watchdog_done = watchdog_done.clone();
                    let others = others.clone();
                    let name = peer_name.clone();
                    // This task is deliberately independent of the reconnect
                    // future: when the displayed budget runs out, end the
                    // session even if WebRTC cleanup is still stuck.
                    tango_platform::spawn(async move {
                        tokio::select! {
                            biased;
                            _ = watchdog_done.cancelled() => {}
                            _ = cancel.cancelled() => {}
                            _ = tango_platform::sleep(timeout) => {
                                end.note_dropped(name.clone());
                                tell_others(&others, RoomMsgOut::GiveUp(peer_seat, name)).await;
                                end.remote_disconnected.store(true, Ordering::Release);
                                pauses_w.release_all();
                                cancel.cancel();
                                wake.notify_one();
                            }
                        }
                    });
                }

                let restored = if host_link || yieldable {
                    tokio::select! {
                        restored = tango_platform::timeout(timeout + std::time::Duration::from_secs(2), link.reconnect()) => restored.unwrap_or(false),
                        // (UNRANKED: the returning player said it gives up)
                        _ = end.give_up.cancelled() => false,
                        _ = ui_tick => unreachable!(),
                    }
                } else {
                    tokio::select! {
                        restored = link.reconnect() => restored,
                        _ = ui_tick => unreachable!(),
                    }
                };
                watchdog_done.cancel();
                restored
            };
            // UNRANKED: a returning player is being let in when the window runs out: the wait goes on a little (the app
            // replaces this session as soon as the player is in), unless it gave up.
            if !restored && (host_link || yieldable) && !end.give_up.is_cancelled() && end.rejoin_busy.load(Ordering::Acquire) {
                log::info!("pvp: the window is over but {peer_name:?} is being let back in: waiting for it");
                let until = web_time::Instant::now() + REJOIN_EXTRA;
                while web_time::Instant::now() < until
                    && !cancel.is_cancelled()
                    && end.rejoin_busy.load(Ordering::Acquire)
                    && !end.give_up.is_cancelled()
                {
                    wake.notify_one();
                    tango_platform::sleep(std::time::Duration::from_millis(100)).await;
                }
            }
            announce_stop.cancel();
            end.hold_remove(peer_seat);
            end.host_wait.store(false, Ordering::Release);

            if !restored && host_link && !cancel.is_cancelled() && !completed.load(Ordering::Acquire) && !end.remote_ended.load(Ordering::Acquire) && !end.aborted.load(Ordering::Acquire) {
                // The host did not come back within its window: the room goes on without it, its army yielded.
                log::info!("pvp: the host {peer_name:?} did not come back: the room goes on without it");
                let m = mig.clone().expect("a host link has its migration");
                m.pauses.enter();
                m.group.add();
                pauses.leave();
                drop(pump);
                drop(watch);
                link.retire_latency();
                super::migrate::begin(m, peer_seat as usize);
                group.finish();
                return;
            }
            if !restored && yieldable && !cancel.is_cancelled() && !completed.load(Ordering::Acquire) && !end.remote_ended.load(Ordering::Acquire) && !end.aborted.load(Ordering::Acquire) {
                log::info!("pvp: {peer_name:?} did not come back: its army yields, the match goes on without it");
                seat_yields(&end, &wake, &others, peer_seat, &link).await;
                pauses.leave();
                drop(pump);
                link.retire_latency();
                group.finish();
                return;
            }
            if !restored {
                // Timed out or cancelled — give up and end the match.
                end.note_dropped(peer_name.clone());
                tell_others(&others, RoomMsgOut::GiveUp(peer_seat, peer_name.clone())).await;
                end.remote_disconnected.store(true, Ordering::Release);
                cancel.cancel();
                pauses.release_all();
                break;
            }
            tell_others(&others, RoomMsgOut::Unhold(peer_seat)).await;

            // Fresh receiver over the swapped channel, same `in_match` —
            // the rennet in-stream (seq/ack) carries across the swap, so
            // the peer's resent window fills our gap contiguously. The
            // drive loop resumes; its stall guard holds it below the
            // horizon until the resends drain the queue.
            pump = Box::pin(run_receive_pump(
                make_receiver().expect("reconnect parks a fresh receiver"),
                link_idx,
                event_tx.clone(),
                wake.clone(),
                rx_tag(),
            ));
            watch = Some(Box::pin(link.watch_control()));
            // The swap rebuilds the control channel too, so an earlier
            // `Primed` may have died with the old transport. Say it again:
            // a peer still waiting on the ready gate has nothing else to
            // wait for, and one it has already latched is a no-op. A
            // rejected send means the fresh channel is already gone —
            // same as the first announcement, there is nothing to retry
            // into, so end rather than leave the peer at a gate that
            // never opens.
            if local_primed.load(Ordering::Acquire) {
                if let Err(e) = link.send_primed().await {
                    log::warn!("pvp: primed re-announce failed after reconnect, ending match: {e}");
                    end.note_dropped(peer_name.clone());
                    end.remote_disconnected.store(true, Ordering::Release);
                    cancel.cancel();
                    pauses.release_all();
                    break;
                }
            }
            // Hold the stall watch off until the resumed drive loop drains the
            // still-full queue back below the threshold (or the grace lapses),
            // so the stale-high `queue_len` can't instantly re-trip the stall
            // and bounce us straight back into another reconnect.
            drain_until = Some(web_time::Instant::now() + RECONNECT_DRAIN_GRACE);
            // (a restored peer is not silent: its clock starts over)
            if let Some(c) = clock {
                last_rx.store(c.elapsed().as_millis() as u64, Ordering::Relaxed);
            }
            pauses.leave();
            wake.notify_one();
            log::info!("pvp transparently reconnected the link");
        }

        // Teardown: retire latency so `latency()` reads `None` and the
        // telemetry panel retires, and wake the session to re-check
        // `is_ended` (the drive loop may already be gone, so no frame is
        // coming).
        drop(watch);
        link.retire_latency();
        pauses.release_all();
        wake.notify_one();
        group.finish();
    });
}

/// What a room's host tells the other guests.
enum RoomMsgOut {
    Gone(u8),
    Hold(u8, String, u32),
    Unhold(u8),
    GiveUp(u8, String),
}

/// A guest's player is gone while a battle is on and does not come back: the host marks the seat gone (its words are idle from
/// the next tick and the console is told to yield its armies, see `driver::HostAgg`), lets the others go on (they were told to
/// wait for it) and says who is gone, so that they all know who is left should the host leave.
async fn seat_yields(end: &EndState, wake: &tokio::sync::Notify, others: &[Arc<tango_net::link::Link>], seat: u8, link: &Arc<tango_net::link::Link>) {
    end.given_up.lock().unwrap().push(link.clone());
    end.note_gone(seat);
    wake.notify_one();
    tell_others(others, RoomMsgOut::Unhold(seat)).await;
    tell_others(others, RoomMsgOut::Gone(end.gone.load(Ordering::Acquire))).await;
}

/// Say it to every link in `others` (best effort, a second at most each).
async fn tell_others(others: &[Arc<tango_net::link::Link>], msg: RoomMsgOut) {
    use tango_net_protocol::control::{RoomHold, RoomMsg};
    for l in others {
        let m = match &msg {
            RoomMsgOut::Gone(seats) => RoomMsg::Gone { seats: *seats },
            RoomMsgOut::Hold(seat, name, left_ms) => RoomMsg::Hold(RoomHold {
                seat: *seat,
                name: name.clone(),
                left_ms: *left_ms,
            }),
            RoomMsgOut::Unhold(seat) => RoomMsg::Unhold { seat: *seat },
            RoomMsgOut::GiveUp(seat, name) => RoomMsg::GiveUp {
                seat: *seat,
                name: name.clone(),
            },
        };
        let _ = tango_platform::timeout(std::time::Duration::from_secs(1), l.send_room(m)).await;
    }
}
