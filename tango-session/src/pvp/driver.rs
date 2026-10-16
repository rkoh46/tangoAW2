//! Boot and advance a match, publish frames, and finalize confirmed inputs.

use super::{EndState, Metrics, TpsCounter, MAX_FRAME_DELAY, MIN_FRAME_DELAY, PEER_END_GRACE};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use tango_match::telemetry;

/// What the driver needs to boot the [`tango_match::Match`].
pub(super) struct BootPieces {
    pub(super) roms: [Vec<u8>; 2],
    pub(super) saves: [Vec<u8>; 2],
    /// Both sides' netplay support, in seat order. Starting the match
    /// goes through these rather than an engine, so a DS game boots the
    /// same way a GBA one does.
    pub(super) pvp: [&'static (dyn tango_match::Backend + Send + Sync); 2],
    /// The peer's cartridge — a match can span two variants and two
    /// regions, and the local game's crate resolves that seat's engine
    /// support from it.
    pub(super) peer_rom: tango_match::PeerRom,
    pub(super) match_type: (u8, u8),
    pub(super) rng_seed: [u8; 16],
    pub(super) rtc: std::time::SystemTime,
    pub(super) local_player: usize,
    /// How many players share the match (2; a room's, up to 5).
    pub(super) players: usize,
    pub(super) present_delay: u32,
    pub(super) disable_bgm: bool,
    /// A suspended match being resumed: the console state to start from, in place of the boot.
    pub(super) resume_state: Option<Vec<u8>>,
}

/// What a room's match needs to be kept when a disconnect cuts it short.
pub(super) struct SuspendCtx {
    pub(super) match_id: u64,
    pub(super) players: Vec<String>,
    pub(super) seat: usize,
    pub(super) match_ts: u64,
    pub(super) match_type: (u8, u8),
    pub(super) save: Vec<u8>,
    pub(super) sim_version: u32,
    pub(super) sink: Arc<dyn Fn(tango_match::SuspendedMatch) + Send + Sync>,
}

pub(super) struct DriveContext {
    pub(super) local_input: Arc<crate::InputCell>,
    pub(super) frame_delay: Arc<AtomicU32>,
    pub(super) metrics: Arc<Metrics>,
    pub(super) drive_paused: Arc<crate::PauseGate>,
    pub(super) cancel: tokio_util::sync::CancellationToken,
    pub(super) completed: Arc<AtomicBool>,
    /// See the session's copy.
    pub(super) displayed_screens: Arc<std::sync::atomic::AtomicU8>,
    pub(super) end: EndState,
    /// What the links bring in, tagged with the link it came on (a room's host has one to each guest).
    pub(super) event_rx: std::sync::mpsc::Receiver<(usize, tango_net::data::Input)>,
    /// One sender to each link (two players: one; a room's guest: the host's; its host: one to each guest).
    pub(super) senders: Vec<tango_net::PvpSender>,
    /// A room of more than two players: this peer is its host (which joins the guests' inputs into one for each),
    /// or a guest (which hears the others as one).
    pub(super) room_host: bool,
    pub(super) in_matches: Vec<tango_net::InMatchTx>,
    pub(super) replay_writer: Option<tango_replay::Writer>,
    pub(super) stats: Arc<Mutex<tango_match::analysis::StatsBuilder>>,
    /// Recording identity and the host's optional statistics destination.
    pub(super) stats_key: Option<std::path::PathBuf>,
    pub(super) stats_sink: Option<Arc<dyn crate::stats::StatsSink>>,
    pub(super) tps_counter: Arc<Mutex<TpsCounter>>,
    pub(super) screen: Arc<crate::Framebuffer>,
    pub(super) wake: Arc<tokio::sync::Notify>,
    /// The ready gate. `local_primed` is set (and `announce_primed`
    /// notified) the moment our pair reaches its link battle;
    /// `peer_primed` is latched by the link's control watch when the
    /// peer says the same. [`PvpDriver::tick`] advances nothing until
    /// both are set.
    pub(super) local_primed: Arc<AtomicBool>,
    /// Each link's peer's say-so (a room's host waits for every guest).
    pub(super) peer_primed: Vec<Arc<AtomicBool>>,
    pub(super) announce_primed: Arc<tokio::sync::Notify>,
    pub(super) local_player: usize,
    /// The close signal as the priming walk can read it — a plain flag
    /// because backends know nothing of this crate's cancellation
    /// token, raised beside it by
    /// [`request_close`](crate::Session::request_close).
    pub(super) boot_cancel: Arc<AtomicBool>,
    /// A room's host seat (the guests' inputs are joined around it).
    pub(super) host_seat: usize,
    /// A room: how to keep the match if a disconnect ends it.
    pub(super) suspend: Option<SuspendCtx>,
}

impl DriveContext {
    /// Boot the match, then hand back the driver that runs it and a
    /// readout handle to its pair.
    fn boot(
        self,
        pieces: BootPieces,
        expected_fps: f32,
        audio: tango_match::AudioIn,
    ) -> Result<PvpDriver, tango_match::Error> {
        // The game's registration starts the match on whatever engine it
        // runs; this session never learns which.
        let local = pieces.pvp[pieces.local_player.min(1)];
        let config = tango_match::StartConfig {
            roms: [&pieces.roms[0], &pieces.roms[1]],
            saves: [Some(&pieces.saves[0]), Some(&pieces.saves[1])],
            rng_seed: pieces.rng_seed,
            rtc: pieces.rtc,
            match_type: pieces.match_type,
            peer_rom: pieces.peer_rom,
            local_player: pieces.local_player,
            players: pieces.players,
            present_delay: pieces.present_delay.clamp(MIN_FRAME_DELAY, MAX_FRAME_DELAY),
            disable_bgm: pieces.disable_bgm,
            // The pair pushes the local seat's sound into the ring the
            // host's stream is already bound to, on its way out of every
            // tick.
            audio: Some(audio),
            // The session is on screen (and leavable) for the whole
            // walk, so a close has to reach into it — otherwise the
            // host's drive-thread join waits the walk out.
            cancel: Some(&self.boot_cancel),
        };
        let match_ = match pieces.resume_state.as_deref() {
            Some(state) => local.start_resumed(config, state)?,
            None => local.start(config)?,
        };

        // Our half of the ready gate: the pair is at its link battle.
        // Release the announcer so the peer learns it — priming ran at
        // whatever speed this machine manages, and until both sides are
        // here neither may advance a tick.
        self.local_primed.store(true, Ordering::Release);
        self.announce_primed.notify_one();

        let agg = (self.room_host && pieces.players > 2).then(|| HostAgg::new(pieces.players, self.host_seat));
        Ok(PvpDriver {
            ctx: self,
            expected_fps,
            match_,
            throttler: tango_match::Throttler::new(),
            fired_end_of_match: false,
            confirmed_through: 0,
            agg,
        })
    }

    /// Fold a batch of confirmed telemetry into the stats builder (the
    /// shared [`tango_match::analysis::fold_confirmed`], so live stats
    /// and offline re-analysis stay byte-equivalent).
    fn fold_confirmed_telemetry(
        &mut self,
        samples: Vec<(u32, telemetry::BattleObs)>,
        events: Vec<(u32, telemetry::Event)>,
    ) {
        let mut stats = self.stats.lock().unwrap();
        tango_match::analysis::fold_confirmed(&mut stats, self.local_player, samples, events);
    }
}

/// The match as the thing a host drives: the first tick boots and
/// primes the pair, every tick after that runs the match.
///
/// The boot rides the drive loop rather than [`super::PvpSession::new`]
/// because priming the pair is seconds of blocking emulation and the
/// session is on screen for all of it — saying so ([`is_booting`](super::PvpSession::is_booting),
/// [`prime_error`](super::PvpSession::prime_error)) instead of making the
/// user wait at the lobby with nothing to read. Replay playback comes
/// up the same way, and for the same reason.
pub struct PvpBoot {
    /// What the first tick needs to bring the pair up, taken there.
    /// `None` once the boot has run, whichever way it went.
    pub(super) pending: Option<(BootPieces, DriveContext)>,
    /// The live match, once the boot has produced one.
    pub(super) driver: Option<PvpDriver>,
    /// The producing end of the ring the host's stream is already bound
    /// to, handed to the pair when the boot builds it. `None` once it
    /// has been. Until then the ring reads empty and the stream primes.
    pub(super) audio: Option<tango_match::AudioIn>,
    /// Where a failed boot leaves its reason, for the session to
    /// publish ([`super::PvpSession::prime_error`]).
    pub(super) prime_error: Arc<Mutex<Option<crate::Error>>>,
    pub(super) expected_fps: f32,
    pub(super) metrics: Arc<Metrics>,
    /// Repaint wake, so the failure reaches a host whose session is
    /// otherwise sitting on a frame that will never come.
    pub(super) wake: Arc<tokio::sync::Notify>,
    /// The engine the boot will run on, for its readiness gate.
    pub(super) backend: &'static (dyn tango_match::Backend + Send + Sync),
}

impl crate::Drive for PvpBoot {
    fn tick(&mut self) -> bool {
        // What `prepare` started may still be coming up — a browser
        // engine's worker threads finish starting only between ticks,
        // while the host's loop yields. Booting before then would spin
        // on threads that can never arrive, so the boot waits out the
        // gate; the priming notice is already up either way.
        if self.pending.is_some() && !self.backend.ready(2) {
            return true;
        }
        if let Some((pieces, drive)) = self.pending.take() {
            let audio = self.audio.take().expect("the boot runs once");
            let booted = drive.boot(pieces, self.expected_fps, audio);
            // Either outcome changes what the session shows, and
            // neither produces a frame — so wake the host itself.
            match booted {
                Ok(driver) => {
                    self.driver = Some(driver);
                    self.wake.notify_one();
                }
                // Cancelled is the session being torn down mid-walk,
                // not a failure to report: there is nobody left to
                // read it.
                Err(tango_match::Error::Cancelled) => return false,
                Err(e) => {
                    log::error!("pvp: boot failed: {e}");
                    *self.prime_error.lock().unwrap() = Some(e.into());
                    self.wake.notify_one();
                    return false;
                }
            }
        }
        match self.driver.as_mut() {
            Some(driver) => driver.tick(),
            // A boot that failed leaves the session up with its reason
            // on screen; there is simply nothing left to drive.
            None => false,
        }
    }

    fn finish(self) {
        // Only a match that ran has a replay tail to write.
        if let Some(driver) = self.driver {
            driver.finish();
        }
    }

    /// The throttler's target once the match runs; before that, the
    /// rate the pacer should idle the boot at.
    fn fps_target(&self) -> f32 {
        f32::from_bits(self.metrics.fps_target.load(Ordering::Relaxed))
    }
}

/// A received wire input in the seam's vocabulary. The wire's touch is
/// a byte per axis — every touch screen a backend has fits one — so
/// widening here is lossless.
fn host_input_of_wire(input: &tango_net::data::Input) -> tango_match::HostInput {
    tango_match::HostInput {
        keys: input.joyflags as u32,
        touch: input.touch.map(|(x, y)| (x as u16, y as u16)),
        extra: input.extra,
    }
}

/// A committed input as the wire ships it. The engine sanitized it
/// through the backend's conversions, so the narrowing casts cannot
/// truncate.
fn wire_input_of(input: tango_match::HostInput, tick_advantage: i16) -> tango_net::data::Input {
    tango_net::data::Input {
        joyflags: input.keys as u16,
        touch: input.touch.map(|(x, y)| (x.min(0xff) as u8, y.min(0xff) as u8)),
        tick_advantage,
        extra: [0; 3],
        others: 0,
    }
}

/// A confirmed input as the replay records it — same narrowing story as
/// [`wire_input_of`].
fn replay_input_of(input: tango_match::HostInput) -> tango_replay::stream::Input {
    tango_replay::stream::Input {
        keys: input.keys as u16,
        touch: input.touch.map(|(x, y)| (x.min(0xff) as u8, y.min(0xff) as u8)),
        extra: input.extra,
    }
}

/// A live match, one tick at a time.
///
/// The state below used to be locals of a `loop` on a thread of its
/// own; naming it is what lets a host drive the match instead — a
/// desktop thread paced by the wall clock today, an event loop once the
/// browser's signaling exists.
pub struct PvpDriver {
    ctx: DriveContext,
    expected_fps: f32,
    match_: tango_match::Match,
    throttler: tango_match::Throttler,
    fired_end_of_match: bool,
    /// Number of authoritative input rows consumed so far: the tick boundary
    /// shared by the replay stream and confirmed telemetry.
    confirmed_through: u32,
    /// A room's host: the guests' inputs joined tick by tick, and the host's own waiting to go out with them.
    agg: Option<HostAgg>,
}

/// A room's host joins its guests' inputs: its own engine hears them as one input (the guests' joypad words in
/// seat order), and each guest is sent one for everyone else (the other seats' in seat order, the host's among them).
struct HostAgg {
    guests: usize,
    /// The host's seat, and the guests' (ascending, as the links are).
    host_seat: usize,
    guest_seats: Vec<usize>,
    /// What each guest's link has brought, in tick order.
    queues: Vec<std::collections::VecDeque<tango_net::data::Input>>,
    /// Ticks every guest has an input for: the joypad words, and the guests' mean time-sync lead.
    rows: std::collections::VecDeque<(Vec<u16>, i16)>,
    /// The host's own inputs, one a tick, and its time-sync lead then.
    own: std::collections::VecDeque<(tango_match::HostInput, i16)>,
}

impl HostAgg {
    fn new(players: usize, host_seat: usize) -> Self {
        let guest_seats: Vec<usize> = (0..players).filter(|&s| s != host_seat).collect();
        let guests = guest_seats.len();
        HostAgg {
            guests,
            host_seat,
            guest_seats,
            queues: vec![Default::default(); guests],
            rows: Default::default(),
            own: Default::default(),
        }
    }

    /// An input from guest `link`'s link; the rows it completes, as the host's one remote input each.
    fn ingest(&mut self, link: usize, input: tango_net::data::Input) -> Vec<(tango_match::HostInput, i16)> {
        if link >= self.guests {
            return Vec::new();
        }
        self.queues[link].push_back(input);
        let mut done = Vec::new();
        while self.queues.iter().all(|q| !q.is_empty()) {
            let row: Vec<tango_net::data::Input> = self.queues.iter_mut().map(|q| q.pop_front().unwrap()).collect();
            let words: Vec<u16> = row.iter().map(|i| i.joyflags).collect();
            let adv = (row.iter().map(|i| i.tick_advantage as i32).sum::<i32>() / self.guests as i32) as i16;
            let get = |k: usize| words.get(k).copied().unwrap_or(0);
            done.push((
                tango_match::HostInput {
                    keys: get(0) as u32,
                    touch: None,
                    extra: [get(1), get(2), get(3)],
                },
                adv,
            ));
            self.rows.push_back((words, adv));
        }
        done
    }

    /// What each guest is owed for a tick: every seat's word but its own, in seat order.
    fn guest_views(&self, own: u16, guest_words: &[u16]) -> Vec<Vec<u16>> {
        let mut by_seat = vec![0u16; self.guests + 1];
        by_seat[self.host_seat] = own;
        for (k, &seat) in self.guest_seats.iter().enumerate() {
            by_seat[seat] = guest_words.get(k).copied().unwrap_or(0);
        }
        self.guest_seats
            .iter()
            .map(|&me| by_seat.iter().enumerate().filter(|&(s, _)| s != me).map(|(_, &w)| w).collect())
            .collect()
    }

    /// Send every guest the tick it is owed: the host's input and the other guests'.
    fn distribute(&mut self, senders: &mut [tango_net::PvpSender]) -> std::io::Result<()> {
        while !self.rows.is_empty() && !self.own.is_empty() {
            let (words, _) = self.rows.pop_front().unwrap();
            let (own, adv) = self.own.pop_front().unwrap();
            let per_guest = self.guest_views(own.keys as u16, &words);
            for (g, sender) in senders.iter_mut().enumerate() {
                let seats = &per_guest[g];
                let get = |k: usize| seats.get(k).copied().unwrap_or(0);
                sender.send(&tango_net::data::Input {
                    joyflags: get(0),
                    touch: None,
                    tick_advantage: adv,
                    extra: [get(1), get(2), get(3)],
                    others: self.guests as u8,
                })?;
            }
        }
        Ok(())
    }
}

impl PvpDriver {
    /// Advance the match one tick. `false` once it's over — cancelled,
    /// a dead link, or a failed advance — after which the host calls
    /// [`PvpDriver::finish`].
    pub fn tick(&mut self) -> bool {
        if self.ctx.cancel.is_cancelled() {
            return false;
        }
        if self.ctx.drive_paused.paused() {
            // The reconnect supervisor releases the gate on every
            // exit path. Nothing to advance meanwhile, so the tick
            // goes back to the host — which is also what lets a
            // browser pause without a thread to park.
            return true;
        }

        // The ready gate. Reaching `tick` means our own pair is primed;
        // hold here until the peer says the same, so both sides start
        // within a round trip of each other.
        //
        // Advancing alone is not merely early — `advance` buffers a
        // local input per tick that the absent peer cannot match, and at
        // `RECONNECT_QUEUE_LENGTH` (~3 s) the supervisor's stall watch
        // reads that as a dead link and tears the transport down for a
        // reconnect the peer never needed. Idling here keeps the
        // published `queue_len` at zero, so the watch stays quiet however
        // long the slower machine takes; the in-match heartbeat runs off
        // its own task and keeps the link alive meanwhile.
        //
        // The wait is bounded without a timer: a peer that never primes
        // fails its own boot (`MAX_PRIME_TICKS`) and tears down, which
        // reaches us as the control channel's `Goodbye` or EOF.
        if !self.ctx.peer_primed.iter().all(|p| p.load(Ordering::Acquire)) {
            return true;
        }

        // Live present-delay adjustment from the footer slider.
        let pd = self.ctx.frame_delay.load(Ordering::Relaxed);
        if pd != self.match_.present_delay() {
            self.match_.set_present_delay(pd);
        }

        // Drain the network before advancing: every confirmed tick we
        // ingest now is a rollback we don't take deeper.
        let arrived: Vec<(usize, tango_net::data::Input)> = self.ctx.event_rx.try_iter().collect();
        for (link, input) in arrived {
            self.ingest(link, input);
        }
        if let Err(e) = self.distribute() {
            log::warn!("pvp: send pump terminated; ending match ({e})");
            self.ctx.end.remote_disconnected.store(true, Ordering::Release);
            self.ctx.cancel.cancel();
            return false;
        }

        // Stall guard: the peer is too far behind (or gone) — advancing
        // further would run the input stream past the rennet horizon.
        // The in-match heartbeat keeps the redundancy window + acks
        // flowing while we wait; the supervisor watches queue_len and
        // decides whether this is a reconnect.
        //
        // But hold ONLY when advancing can't make progress. `advance` is
        // the sole thing that drains the local queue (it matches buffered
        // remote inputs against local ones and confirms the pairs); merely
        // ingesting remote inputs above just buffers them. So if the peer
        // is still feeding us matchable inputs — exactly the case during a
        // post-reconnect resend burst — we must keep advancing to settle
        // them, even at a full queue: each such advance nets the queue
        // *down* (drains ≥1, adds 1 local). Skipping advance whenever the
        // queue is full instead would leave those resends forever
        // unconsumed — the queue never drains, the stall never clears, and
        // the link "reconnects but never resumes". Only a genuinely dead
        // link (nothing matchable) parks here.
        let queue_len = self.match_.local_queue_length() as u32;
        self.ctx.metrics.queue_len.store(queue_len, Ordering::Relaxed);
        if queue_len as usize >= tango_net::data::RECONNECT_QUEUE_LENGTH && self.match_.matchable() == 0 {
            // Block on the event queue rather than poll it: the only
            // thing that clears a stall is the peer's next input, and
            // it arrives exactly here. Ingest it and loop — the drain
            // + stall re-check above decide whether we're unstuck.
            // The only thing that clears a stall is the peer's
            // next input. Take whatever has landed and give the
            // tick back; the drain + stall re-check above decide
            // next time whether we're unstuck. A dead channel
            // yields too — the supervisor owns what happens next,
            // and spinning on it would burn the host's loop.
            if let Ok((link, input)) = self.ctx.event_rx.try_recv() {
                self.ingest(link, input);
            }
            return true;
        }

        // Sample the skew before `advance` enqueues this tick's local
        // input, so our half matches the advantage we ship the peer.
        let skew = self.match_.skew();
        self.ctx.metrics.skew.store(skew, Ordering::Relaxed);

        let mut local = self.ctx.local_input.load();
        local.keys &= tango_match::keys::MASK;
        let advanced = match self.match_.advance(local) {
            Ok(r) => r,
            Err(e) => {
                log::error!("pvp: sio advance failed: {e}");
                self.ctx.cancel.cancel();
                return false;
            }
        };
        self.ctx
            .metrics
            .depth
            .store(self.match_.last_rollback_depth(), Ordering::Relaxed);

        // Test aid (`TANGOAW2_STATE_LOG=1`): a checksum of the console's memory every 120 ticks, to compare peers.
        if std::env::var("TANGOAW2_STATE_LOG").is_ok_and(|v| v == "1") && self.confirmed_through % 120 == 0 {
            let sums = self.match_.with_link(|link| {
                let mut out = Vec::new();
                for (name, at, len) in [("iwram", 0x0300_0000u32, 0x8000usize), ("ewram", 0x0200_0000, 0x40000)] {
                    let mut b = vec![0u8; len];
                    link.peek(at, &mut b);
                    let mut h: u64 = 0xcbf29ce484222325;
                    for x in &b {
                        h = (h ^ *x as u64).wrapping_mul(0x100000001b3);
                    }
                    out.push(format!("{name}={h:016x}"));
                }
                out.join(" ")
            });
            log::info!("state tick {}: {}", self.confirmed_through, sums);
        }
        // A successful advance returns every row it settled. Nothing else
        // settles the engine, so every early return below is already consumed
        // and teardown has no tail path.
        let tango_match::Advance {
            outgoing,
            tick_advantage,
            confirmed_inputs,
            ..
        } = advanced;
        self.confirmed_through += confirmed_inputs.len() as u32;
        let (samples, events) = match self.match_.telemetry() {
            Some(telemetry) => telemetry.lock().unwrap().take_through(self.confirmed_through),
            None => (Vec::new(), Vec::new()),
        };
        let match_ended = events
            .iter()
            .any(|(_, event)| matches!(event, telemetry::Event::MatchEnded));
        if let Some(w) = self.ctx.replay_writer.as_mut() {
            for inputs in &confirmed_inputs {
                if let Err(e) = w.write_input(inputs.map(replay_input_of)) {
                    log::warn!("pvp: replay write failed (recording stops): {e}");
                    self.ctx.replay_writer = None;
                    break;
                }
            }
        }
        if !samples.is_empty() || !events.is_empty() {
            self.ctx.fold_confirmed_telemetry(samples, events);
        }

        // Ship this tick's local input. Push-before-send semantics live
        // in the pump; a transport error is non-terminal (the heartbeat
        // retransmits once the reconnect swaps a live channel back in).
        let sent = match self.agg.as_mut() {
            // A room's host: its input goes out with the guests' (to each guest, once all have said theirs).
            Some(agg) => {
                agg.own.push_back((outgoing, tick_advantage));
                agg.distribute(&mut self.ctx.senders)
            }
            None => self.ctx.senders[0].send(&wire_input_of(outgoing, tick_advantage)),
        };
        if sent.is_err() {
            log::warn!("pvp: send pump terminated; ending match");
            self.ctx.end.remote_disconnected.store(true, Ordering::Release);
            self.ctx.cancel.cancel();
            return false;
        }

        // The players abandoned the match in-game before any battle
        // (the store's abort latch — see it for why this needs no
        // confirmation wait): end uncleanly, right now. The peer's
        // simulation raises the same latch on the same pair tick, so
        // both sessions end together — neither side's teardown reads
        // as a disconnect to the other (the supervisor checks this
        // flag on every trip).
        if self
            .match_
            .telemetry()
            .is_some_and(|handle| handle.lock().unwrap().aborted())
        {
            log::info!("pvp: match aborted in-game before any battle; ending uncleanly");
            self.ctx.end.aborted.store(true, Ordering::Release);
            self.ctx.cancel.cancel();
            return false;
        }

        // Completion: the games' own match-end path ran (confirmed —
        // both peers see it at the same pair tick). No runout needed:
        // the anchor fires after the result screens have played.
        if match_ended {
            self.ctx.completed.store(true, Ordering::Release);
        }
        if self.ctx.completed.load(Ordering::Acquire) && !self.fired_end_of_match {
            self.fired_end_of_match = true;
            let first_completion = {
                let mut completed_at = self.ctx.end.local_ended_at.lock().unwrap();
                if completed_at.is_some() {
                    false
                } else {
                    *completed_at = Some(web_time::Instant::now());
                    true
                }
            };
            if first_completion {
                // In-band EndOfMatch: rides the same ordered seq stream
                // as inputs, so the peer sees it exactly once and only
                // after every preceding input.
                for in_match in self.ctx.in_matches.clone() {
                    tango_platform::spawn(async move {
                        if let Err(e) = in_match.send_end_of_match().await {
                            log::warn!("pvp: send EndOfMatch failed: {e}");
                        }
                    });
                }
                // Wall-clock fallback wake so `is_ended` is rechecked
                // even if the peer never sends EndOfMatch.
                let wake = self.ctx.wake.clone();
                tango_platform::spawn(async move {
                    tango_platform::sleep(PEER_END_GRACE).await;
                    wake.notify_one();
                });
            }
        }

        // Present the local screen to the UI. (Audio needs no push —
        // the output stream pulls it straight off the pair.)
        if let Some(buf) = self.match_.frame() {
            self.ctx.screen.write(&buf);
        }
        self.ctx.tps_counter.lock().unwrap().mark();
        self.ctx.wake.notify_one();

        // Whatever the host is arranging to show, handed over each tick:
        // a console composes nothing for a screen nobody is looking at,
        // and the setting behind this can move mid-match.
        self.match_
            .set_displayed_screens(self.ctx.displayed_screens.load(Ordering::Relaxed));

        // Clock sync: only the leading peer shaves tick rate, and only
        // once the presented frame actually speculates past the present
        // delay.
        let slowdown = self.throttler.step(skew, self.match_.speculation_balance());
        let target = self.expected_fps - slowdown;
        self.ctx.metrics.fps_target.store(target.to_bits(), Ordering::Relaxed);

        true
    }

    /// Flush the replay tail and cache the match's stats. Called once,
    /// after [`PvpDriver::tick`] reports the match over — reached through
    /// [`crate::Drive::finish`], which is why a host must wind a driver
    /// down rather than drop it.
    pub fn finish(mut self) {
        self.suspend_if_cut_short();
        // Finalize (write the EOR sentinel) only if the match completed
        // — same policy as the trap engine, so an aborted match leaves
        // a truncated-but-parseable recording.
        if let Some(w) = self.ctx.replay_writer.take() {
            if self.ctx.completed.load(Ordering::Acquire) {
                if let Err(e) = w.finish() {
                    log::error!("finish replay failed: {e}");
                }
            }
            // Cache the match's stats, completed or not: the fold keeps
            // a round the match never decided (only its verdict is
            // absent), and writing the sidecar here is what spares the
            // Replays tab a full re-simulation of an aborted match — the
            // telemetry it would recover was already collected live.
            if let (Some(sink), Some(key)) = (self.ctx.stats_sink.as_ref(), self.ctx.stats_key.as_ref()) {
                let snapshot = self.ctx.stats.lock().unwrap().snapshot();
                if let Err(e) = sink.record(key, &snapshot) {
                    log::warn!("failed to write replay stats cache entry: {e}");
                }
            }
        }
    }
}

impl PvpDriver {
    /// A room's match that a disconnect cut short is kept for resuming: its newest settled checkpoints go to the
    /// app's sink (a match not in a battle, or not yet checkpointed, is not worth keeping).
    fn suspend_if_cut_short(&mut self) {
        let Some(ctx) = self.ctx.suspend.as_ref() else { return };
        if self.ctx.completed.load(Ordering::Acquire)
            || self.ctx.end.aborted.load(Ordering::Acquire)
            || !self.ctx.end.remote_disconnected.load(Ordering::Acquire)
        {
            return;
        }
        let mut checkpoints: Vec<tango_match::Checkpoint> = self
            .match_
            .checkpoints()
            .into_iter()
            .filter(|c| c.image.info.is_some())
            .collect();
        if checkpoints.len() > tango_match::suspend::CHECKPOINTS_STORED {
            checkpoints.drain(..checkpoints.len() - tango_match::suspend::CHECKPOINTS_STORED);
        }
        if checkpoints.is_empty() {
            log::info!("pvp: the match ended by a disconnect before a battle checkpoint; nothing to keep");
            return;
        }
        let disconnected = self.ctx.end.dropped.lock().unwrap().clone().unwrap_or_default();
        log::info!(
            "pvp: match {:016x} cut short by {disconnected:?}: keeping checkpoints {:?}",
            ctx.match_id,
            checkpoints.iter().map(|c| (c.tick, c.image.digest)).collect::<Vec<_>>()
        );
        (ctx.sink)(tango_match::SuspendedMatch {
            version: tango_match::suspend::SUSPENDED_VERSION,
            match_id: ctx.match_id,
            sim_version: ctx.sim_version,
            players: ctx.players.clone(),
            seat: ctx.seat as u8,
            disconnected,
            saved_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_or(0, |d| d.as_secs()),
            match_ts: ctx.match_ts,
            match_type: ctx.match_type,
            save: ctx.save.clone(),
            checkpoints,
        });
    }

    /// One input in from a link: the remote's (two players), the host's one for everyone else (a room's guest), or
    /// a guest's (a room's host, which joins them).
    fn ingest(&mut self, link: usize, input: tango_net::data::Input) {
        match self.agg.as_mut() {
            Some(agg) => {
                for (joined, adv) in agg.ingest(link, input) {
                    self.match_.add_remote_input(joined, adv);
                }
            }
            None => self
                .match_
                .add_remote_input(host_input_of_wire(&input), input.tick_advantage),
        }
    }

    fn distribute(&mut self) -> std::io::Result<()> {
        match self.agg.as_mut() {
            Some(agg) => agg.distribute(&mut self.ctx.senders),
            None => Ok(()),
        }
    }
}

impl crate::Drive for PvpDriver {
    fn tick(&mut self) -> bool {
        PvpDriver::tick(self)
    }

    fn finish(self) {
        PvpDriver::finish(self)
    }

    /// The throttler's target: the base rate minus whatever it shaved
    /// to bring the peers' clocks together.
    fn fps_target(&self) -> f32 {
        f32::from_bits(self.ctx.metrics.fps_target.load(Ordering::Relaxed))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn input(keys: u16) -> tango_net::data::Input {
        tango_net::data::Input { joyflags: keys, touch: None, tick_advantage: 0, extra: [0; 3], others: 0 }
    }

    /// A room of 3 and of 5: every guest's word reaches the host's engine as seat order, and every guest hears
    /// every other seat, so that all peers build the same seats' words (a guest's keys reach the shared console).
    #[test]
    fn room_inputs_reach_every_seat() {
        for players in [3usize, 4, 5] {
            for host_seat in [0usize, 1] {
                let mut agg = HostAgg::new(players, host_seat);
                let guest_seats = agg.guest_seats.clone();
                let words: Vec<u16> = guest_seats.iter().map(|&s| 0x10 << s).collect();
                let own = 0x1u16;
                let mut rows = Vec::new();
                for (k, w) in words.iter().enumerate() {
                    rows.extend(agg.ingest(k, input(*w)));
                }
                assert_eq!(rows.len(), 1);
                // The host's engine: seat_inputs puts the composite back into seats.
                let seats = tango_match::seat_inputs(host_seat, players, tango_match::HostInput::keys(own as u32), rows[0].0);
                assert_eq!(seats[host_seat].keys, own as u32);
                for (k, &s) in guest_seats.iter().enumerate() {
                    assert_eq!(seats[s].keys, words[k] as u32, "host hears seat {s} ({players} players)");
                }
                // Each guest's engine: the same seats' words.
                let views = agg.guest_views(own, &words);
                for (g, &me) in guest_seats.iter().enumerate() {
                    let v = &views[g];
                    let get = |k: usize| v.get(k).copied().unwrap_or(0);
                    let remote = tango_match::HostInput {
                        keys: get(0) as u32,
                        touch: None,
                        extra: [get(1), get(2), get(3)],
                    };
                    let local = tango_match::HostInput::keys(words[g] as u32);
                    let seats = tango_match::seat_inputs(me, players, local, remote);
                    assert_eq!(seats[host_seat].keys, own as u32);
                    for (k, &s) in guest_seats.iter().enumerate() {
                        assert_eq!(seats[s].keys, words[k] as u32, "guest {me} hears seat {s} ({players} players)");
                    }
                }
            }
        }
    }
}
