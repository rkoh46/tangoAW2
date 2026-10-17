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
    pub(super) senders: Vec<Option<tango_net::PvpSender>>,
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
    /// A room: what the host migration hands the drive thread and asks of it.
    pub(super) mig: Arc<super::migrate::Mailbox>,
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
        let players = pieces.players;
        Ok(PvpDriver {
            players,
            log: TickLog::default(),
            ctx: self,
            expected_fps,
            match_,
            throttler: tango_match::Throttler::new(),
            fired_end_of_match: false,
            confirmed_through: 0,
            agg,
            guard: crate::black_guard::BlackGuard::new(),
            hold_shown: None,
            hold_up: false,
            hold_b: true,
            keys_released: false,
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

/// The newest ticks' inputs, kept for a host migration: what this peer sent for each of its own ticks, and the rows of
/// the old host's stream (the other seats' words) it received, by tick.
#[derive(Default)]
pub(super) struct TickLog {
    local: std::collections::VecDeque<(u32, tango_match::HostInput, i16)>,
    remote: std::collections::VecDeque<(u32, [u16; 4])>,
    /// Ticks of the stream received (the next row's tick), and ticks played with local input.
    pub(super) remote_count: u32,
    pub(super) local_count: u32,
}

/// Ticks kept in the log: far more than the peers can be apart.
const LOG_KEEP: usize = 600;

impl TickLog {
    fn push_local(&mut self, tick: u32, input: tango_match::HostInput, adv: i16) {
        self.local.push_back((tick, input, adv));
        self.local_count = tick + 1;
        while self.local.len() > LOG_KEEP {
            self.local.pop_front();
        }
    }

    fn push_remote(&mut self, input: tango_match::HostInput) {
        self.remote
            .push_back((self.remote_count, [input.keys as u16, input.extra[0], input.extra[1], input.extra[2]]));
        self.remote_count += 1;
        while self.remote.len() > LOG_KEEP {
            self.remote.pop_front();
        }
    }

    fn local_at(&self, tick: u32) -> Option<tango_match::HostInput> {
        let first = self.local.front()?.0;
        self.local.get(tick.checked_sub(first)? as usize).filter(|e| e.0 == tick).map(|e| e.1)
    }

    fn remote_at(&self, tick: u32) -> Option<[u16; 4]> {
        let first = self.remote.front()?.0;
        self.remote.get(tick.checked_sub(first)? as usize).filter(|e| e.0 == tick).map(|e| e.1)
    }

    /// The last [`MIGRATE_TAIL`](tango_net_protocol::control::MIGRATE_TAIL) ticks before `remote_count` that both logs hold.
    pub(super) fn tail(&self) -> Vec<tango_net_protocol::control::MigrateRow> {
        let to = self.remote_count;
        let from = to.saturating_sub(tango_net_protocol::control::MIGRATE_TAIL as u32);
        let mut rows = Vec::new();
        for t in from..to {
            match (self.remote_at(t), self.local_at(t)) {
                (Some(view), Some(own)) => rows.push(tango_net_protocol::control::MigrateRow { view, own: own.keys as u16 }),
                // (a hole: only what follows it is contiguous)
                _ => rows.clear(),
            }
        }
        rows
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
    /// How many players share the match.
    players: usize,
    /// The newest ticks' inputs, for a host migration.
    log: TickLog,
    expected_fps: f32,
    match_: tango_match::Match,
    throttler: tango_match::Throttler,
    fired_end_of_match: bool,
    /// Number of authoritative input rows consumed so far: the tick boundary
    /// shared by the replay stream and confirmed telemetry.
    confirmed_through: u32,
    /// A room's host: the guests' inputs joined tick by tick, and the host's own waiting to go out with them.
    agg: Option<HostAgg>,
    /// The window is never black while the match is live ([`crate::black_guard`]).
    guard: crate::black_guard::BlackGuard,
    /// The reconnect box ((tangoAW2's `hold_box`)): when its picture was last handed over, whether it is
    /// up, and whether B was down at the last look (a B held when it came up is not a press).
    hold_shown: Option<std::time::Instant>,
    hold_up: bool,
    hold_b: bool,
    /// The pad has been let go since the match began ([`PvpDriver::tick`]).
    keys_released: bool,
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
    /// Which guests have sent a first input (the host's first tick waits for them all: [`START_WAIT_TICKS`]).
    heard: Vec<bool>,
    /// Guests whose player left after being out of the match (by link): their words are idle and nothing is sent to them.
    gone: Vec<bool>,
    /// The host has begun to advance.
    started: bool,
    /// Idle ticks spent waiting for the guests' first inputs.
    waited: u32,
}

/// A room's host holds its first tick until every guest has sent its first input, at most this many idle ticks
/// (3 s). The guests begin ticking a little after the host does (a few hundred ms, more with more guests: each
/// one primes and hears the others on its own), and a host that starts first runs that many ticks ahead of them
/// for good, until the clock sync has shaved its rate (a room's host ran at 56 fps on SELECT MAP for its first
/// seconds). Starting when the guests' inputs are in, the host is where it should be: a trip behind them.
const START_WAIT_TICKS: u32 = 180;

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
            heard: vec![false; guests],
            gone: vec![false; guests],
            started: false,
            waited: 0,
        }
    }

    /// The host after a migration (this seat took the host over; `gone` are the seats whose players are not there, the
    /// old host's among them): the guests' words begin at the migration's start tick, and the host's own words that
    /// were not joined yet wait in `own`.
    fn migrated(players: usize, host_seat: usize, gone: u8, own: Vec<(tango_match::HostInput, i16)>) -> Self {
        let mut agg = HostAgg::new(players, host_seat);
        for (k, &seat) in agg.guest_seats.clone().iter().enumerate() {
            if gone & (1 << seat) != 0 {
                agg.gone[k] = true;
                agg.heard[k] = true;
            }
        }
        agg.started = true;
        agg.own = own.into();
        agg
    }

    /// An input from guest `link`'s link; the rows it completes, as the host's one remote input each.
    fn ingest(&mut self, link: usize, input: tango_net::data::Input) -> Vec<(tango_match::HostInput, i16)> {
        if link >= self.guests || self.gone[link] {
            return Vec::new();
        }
        self.queues[link].push_back(input);
        self.heard[link] = true;
        self.complete()
    }

    /// Guests (by seat bit) whose player has left: their words are idle from now on, and the rows that waited for them are done.
    fn set_gone(&mut self, seats: u8) -> Vec<(tango_match::HostInput, i16)> {
        let mut changed = false;
        for (k, &seat) in self.guest_seats.iter().enumerate() {
            if seats & (1 << seat) != 0 && !self.gone[k] {
                self.gone[k] = true;
                self.heard[k] = true;
                self.queues[k].clear();
                changed = true;
            }
        }
        if changed {
            self.complete()
        } else {
            Vec::new()
        }
    }

    fn complete(&mut self) -> Vec<(tango_match::HostInput, i16)> {
        let mut done = Vec::new();
        while (0..self.guests).all(|k| self.gone[k] || !self.queues[k].is_empty()) && (0..self.guests).any(|k| !self.gone[k]) {
            let mut words = vec![0u16; self.guests];
            let mut advs = Vec::new();
            for k in 0..self.guests {
                if self.gone[k] {
                    continue;
                }
                let i = self.queues[k].pop_front().unwrap();
                words[k] = i.joyflags;
                advs.push(i.tick_advantage as i32);
            }
            let adv = (advs.iter().sum::<i32>() / advs.len().max(1) as i32) as i16;
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
    fn distribute(&mut self, senders: &mut [Option<tango_net::PvpSender>]) -> std::io::Result<()> {
        while !self.rows.is_empty() && !self.own.is_empty() {
            let (words, _) = self.rows.pop_front().unwrap();
            let (own, adv) = self.own.pop_front().unwrap();
            let per_guest = self.guest_views(own.keys as u16, &words);
            for (g, sender) in senders.iter_mut().enumerate() {
                let Some(sender) = sender.as_mut() else { continue };
                if self.gone.get(g).copied().unwrap_or(false) {
                    continue;
                }
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
    /// The reconnect box of a room's hold (the game's own message box, see (tangoAW2's `hold_box`)): up
    /// while the match is paused for a player it waits for, with a fresh picture ten times a second (the paused
    /// loop makes none) and B to leave. A pause with nobody named (a plain link being rebuilt) has the host's modal.
    fn hold_box(&mut self, paused: bool) {
        // A host migration in progress outranks a wait for a player (the old host's own wait has ended by then).
        let migrating = if paused { self.ctx.end.migrating.lock().unwrap().clone() } else { None };
        let hold = if paused && migrating.is_none() {
            let holds = self.ctx.end.holds.lock().unwrap();
            holds.iter().min_by_key(|h| h.deadline).map(|h| {
                let left = h.deadline.saturating_duration_since(std::time::Instant::now());
                (h.name.clone(), left.as_secs_f32().ceil() as u32)
            })
        } else {
            None
        };
        let hold = hold.filter(|(n, _)| !n.is_empty());
        if hold.is_none() && migrating.is_none() {
            if self.hold_up {
                self.hold_up = false;
                self.hold_shown = None;
                self.hold_b = true;
                tango_gamesupport::hold::set(None);
                tango_gamesupport::hold::set_migration(None);
                if let Some(buf) = self.match_.frame() {
                    let buf = self.guard.filter(buf);
                    self.ctx.screen.write(&buf);
                    self.ctx.wake.notify_one();
                }
            }
            return;
        }
        // (B pressed anew since the box came up)
        let b = self.ctx.local_input.load().keys & tango_match::keys::B != 0;
        if b && !self.hold_b {
            log::info!("pvp: B on the reconnect box: leaving the match");
            self.ctx.end.leave.store(true, Ordering::Release);
            self.ctx.wake.notify_one();
        }
        self.hold_b = b;
        if !self.hold_up {
            match (&hold, &migrating) {
                (_, Some((name, _))) => log::info!("pvp: host migration box up (new host {name:?})"),
                (Some(h), _) => log::info!("pvp: reconnect box up for {:?}", h.0),
                _ => {}
            }
        }
        tango_gamesupport::hold::set(hold);
        tango_gamesupport::hold::set_migration(migrating);
        self.hold_up = true;
        if self.hold_shown.is_none_or(|t| t.elapsed() >= std::time::Duration::from_millis(100)) {
            self.hold_shown = Some(std::time::Instant::now());
            if let Some(buf) = self.match_.frame() {
                let buf = self.guard.filter(buf);
                self.ctx.screen.write(&buf);
                self.ctx.wake.notify_one();
            }
        }
    }

    /// Advance the match one tick. `false` once it's over — cancelled,
    /// a dead link, or a failed advance — after which the host calls
    /// [`PvpDriver::finish`].
    pub fn tick(&mut self) -> bool {
        if self.ctx.cancel.is_cancelled() {
            self.hold_box(false);
            return false;
        }
        self.serve_migration();
        if self.ctx.drive_paused.paused() {
            self.hold_box(true);
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
        if self.players > 2 {
            // The seats the game says are out (the supervisors read them when a link drops; every peer of a room knows
            // them: a guest decides by them whether the host's leaving is a migration)
            self.ctx.end.seats_out.store(self.match_.seats_out(), Ordering::Release);
        }
        if self.ctx.room_host {
            // The seats whose player has left since: their input is idle from here on.
            let gone = self.ctx.end.gone.load(Ordering::Acquire);
            if gone != 0 {
                if let Some(agg) = self.agg.as_mut() {
                    let rows = agg.set_gone(gone);
                    for (joined, adv) in rows {
                        self.add_remote(joined, adv);
                    }
                }
            }
        }
        if let Err(e) = self.distribute() {
            log::warn!("pvp: send pump terminated; ending match ({e})");
            self.ctx.end.remote_disconnected.store(true, Ordering::Release);
            self.ctx.cancel.cancel();
            return false;
        }

        // A room's host starts once every guest has begun (see [`START_WAIT_TICKS`]).
        if let Some(agg) = self.agg.as_mut() {
            if !agg.started {
                if agg.heard.iter().all(|&h| h) || agg.waited >= START_WAIT_TICKS {
                    agg.started = true;
                } else {
                    agg.waited += 1;
                    return true;
                }
            }
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

        if self.hold_up {
            self.hold_box(false);
        }

        // Sample the skew before `advance` enqueues this tick's local
        // input, so our half matches the advantage we ship the peer.
        let skew = self.match_.skew();
        self.ctx.metrics.skew.store(skew, Ordering::Relaxed);

        let mut local = self.ctx.local_input.load();
        local.keys &= tango_match::keys::MASK;
        // Keys held as the match comes up (the START that began the room, the A of READY) are not presses: the match gets
        // none until the pad has been released once (a resumed match opened AW2's overview on the host).
        if !self.keys_released {
            if local.keys == 0 {
                self.keys_released = true;
            }
            local.keys = 0;
        }
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
            tick,
            outgoing,
            tick_advantage,
            confirmed_inputs,
        } = advanced;
        if self.players > 2 {
            self.log.push_local(tick, outgoing, tick_advantage);
        }
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
            None => match self.ctx.senders[0].as_mut() {
                Some(sender) => sender.send(&wire_input_of(outgoing, tick_advantage)),
                None => Ok(()),
            },
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
            let buf = self.guard.filter(buf);
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
        // Test aid (`TANGOAW2_PACE_LOG=1`): the clock sync's inputs and result every 120 ticks.
        if self.confirmed_through % 120 == 0 && std::env::var("TANGOAW2_PACE_LOG").is_ok_and(|v| v == "1") {
            log::info!(
                "pace: tick {} skew {skew} balance {} slowdown {slowdown:.2} fps target {target:.2} depth {}",
                self.confirmed_through,
                self.match_.speculation_balance(),
                self.match_.last_rollback_depth()
            );
        }
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
                let rows = agg.ingest(link, input);
                for (joined, adv) in rows {
                    self.add_remote(joined, adv);
                }
            }
            None => self.add_remote(host_input_of_wire(&input), input.tick_advantage),
        }
    }

    /// One row of the (joined) remote stream into the engine, and into the log.
    fn add_remote(&mut self, joined: tango_match::HostInput, adv: i16) {
        self.log.push_remote(joined);
        self.match_.add_remote_input(joined, adv);
    }

    /// The host migration's requests of the drive thread, served between ticks even while the match is paused: a
    /// snapshot of how far this peer got in the old host's stream (after taking in what the old link had delivered),
    /// and the handover to the new host's links.
    fn serve_migration(&mut self) {
        let mig = self.ctx.mig.clone();
        if mig.want_snapshot.swap(false, Ordering::AcqRel) {
            let arrived: Vec<(usize, tango_net::data::Input)> = self.ctx.event_rx.try_iter().collect();
            for (link, input) in arrived {
                self.ingest(link, input);
            }
            *mig.snapshot.lock().unwrap() = Some(super::migrate::Snapshot {
                remote: self.log.remote_count,
                local: self.log.local_count,
                tail: self.log.tail(),
            });
            self.ctx.wake.notify_one();
        }
        let handover = mig.handover.lock().unwrap().take();
        if let Some(h) = handover {
            self.apply_handover(h);
            self.ctx.wake.notify_one();
        }
    }

    fn apply_handover(&mut self, h: super::migrate::Handover) {
        // (whatever the old links still had queued is moot: the stream goes on from the migration's rows)
        while self.ctx.event_rx.try_recv().is_ok() {}
        self.ctx.in_matches = h.in_matches;
        self.ctx.senders = h.senders;
        self.ctx.peer_primed = vec![Arc::new(AtomicBool::new(true))];
        self.ctx.host_seat = h.host_seat;
        self.ctx.room_host = h.i_host;
        self.ctx.end.gone.fetch_or(h.gone, Ordering::AcqRel);
        let lacking = h.catchup.len();
        for row in h.catchup {
            let joined = tango_match::HostInput { keys: row[0] as u32, touch: None, extra: [row[1], row[2], row[3]] };
            self.add_remote(joined, 0);
        }
        log::info!(
            "pvp: host migration: {} ticks taken in, the stream resumes at tick {} (we have {}); host is seat {}{}",
            lacking,
            h.start,
            self.log.remote_count,
            h.host_seat,
            if h.i_host { " (us)" } else { "" }
        );
        let words: Vec<(tango_match::HostInput, i16)> =
            self.log.local.iter().filter(|(t, ..)| *t >= h.start).map(|(_, i, a)| (*i, *a)).collect();
        if h.i_host {
            self.agg = Some(HostAgg::migrated(self.players, h.host_seat, h.gone | self.ctx.end.gone.load(Ordering::Acquire), words));
        } else {
            self.agg = None;
            // our own words from the start tick on go to the new host again (the old one never joined them)
            if let Some(sender) = self.ctx.senders.first_mut().and_then(|s| s.as_mut()) {
                for (input, adv) in words {
                    if sender.send(&wire_input_of(input, adv)).is_err() {
                        log::warn!("pvp: could not resend our inputs to the new host");
                        break;
                    }
                }
            }
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
    fn a_gone_guest_is_idle_and_the_rest_go_on() {
        let mut agg = HostAgg::new(3, 0);
        // guests are seats 1 and 2 (links 0 and 1); guest 2 has sent nothing when its player leaves
        assert!(agg.ingest(0, input(0x10)).is_empty());
        let done = agg.set_gone(1 << 2);
        assert_eq!(done.len(), 1, "the row that waited for the gone seat is done");
        assert_eq!(done[0].0.keys, 0x10);
        assert_eq!(done[0].0.extra[0], 0, "the gone seat's word is idle");
        // from now on guest 1's inputs alone make rows, and the gone guest's link is ignored
        assert_eq!(agg.ingest(0, input(0x20)).len(), 1);
        assert!(agg.ingest(1, input(0x40)).is_empty());
        assert_eq!(agg.ingest(0, input(0x30)).len(), 1);
        assert_eq!(agg.rows.len(), 3);
        assert!(agg.rows.iter().all(|(w, _)| w[1] == 0));
    }

    /// The host left and seat 1 took the room over (3 players): the old host's seat is idle from the first row, the
    /// remaining guest's words alone make the rows, the new host's own unsent words are paired with them, and the guest
    /// hears the idle old host and the new host's word in seat order.
    #[test]
    fn the_new_host_joins_from_the_migration_tick_with_the_old_host_idle() {
        let own: Vec<(tango_match::HostInput, i16)> =
            (0..3).map(|k| (tango_match::HostInput::keys(0x100 + k), 0)).collect();
        let mut agg = HostAgg::migrated(3, 1, 1 << 0, own);
        // guests are seats 0 (gone) and 2: the link of seat 2 is guest 1
        assert_eq!(agg.guest_seats, vec![0, 2]);
        let r = agg.ingest(1, input(0x20));
        assert_eq!(r.len(), 1, "a row needs only the seat that is there");
        // the new host's engine hears [seat 0 = idle, seat 2]
        assert_eq!(r[0].0.keys, 0);
        assert_eq!(r[0].0.extra[0], 0x20);
        assert_eq!(agg.ingest(1, input(0x30)).len(), 1);
        assert_eq!(agg.rows.len(), 2);
        // the guest in seat 2 is owed [seat 0 = idle, seat 1 = the host's word]
        let views = agg.guest_views(0x100, &agg.rows[0].0.clone());
        assert_eq!(views[1], vec![0, 0x100]);
        // the gone seat's link is ignored
        assert!(agg.ingest(0, input(0x99)).is_empty());
        // the host's own words wait to go out with the rows
        assert_eq!(agg.own.len(), 3);
    }

    /// The log keeps what a migration needs: the last rows of the stream with this seat's own words beside them, as many as
    /// both logs hold, and the counts.
    #[test]
    fn the_tick_log_gives_the_tail_of_the_stream_for_a_migration() {
        let mut log = TickLog::default();
        for t in 0..300u32 {
            log.push_local(t, tango_match::HostInput::keys(0x100 + (t % 16)), 0);
        }
        for t in 0..290u32 {
            log.push_remote(tango_match::HostInput { keys: t, touch: None, extra: [t as u16 + 1, 0, 0] });
        }
        assert_eq!((log.remote_count, log.local_count), (290, 300));
        let tail = log.tail();
        assert_eq!(tail.len(), tango_net_protocol::control::MIGRATE_TAIL);
        let last = tail.last().unwrap();
        assert_eq!(last.view, [289, 290, 0, 0]);
        assert_eq!(last.own, 0x100 + (289 % 16) as u16);
        // a log that holds more than it keeps drops the oldest
        for t in 300..1000u32 {
            log.push_local(t, tango_match::HostInput::keys(1), 0);
            log.push_remote(tango_match::HostInput::keys(2));
        }
        assert!(log.local.len() <= LOG_KEEP && log.remote.len() <= LOG_KEEP);
        assert_eq!(log.tail().len(), tango_net_protocol::control::MIGRATE_TAIL);
    }

    #[test]
    fn only_a_host_lets_an_out_seat_leave() {
        use super::super::is_benign_drop;
        assert!(is_benign_drop(true, 0b100, 2));
        assert!(!is_benign_drop(true, 0b100, 1), "a seat still in the match is a disconnect");
        assert!(!is_benign_drop(false, 0b100, 2), "a guest cannot go on without the host's join");
        assert!(!is_benign_drop(true, 0xFF, 9));
    }

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
