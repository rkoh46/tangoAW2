//! The shared-console engine: ONE emulated GBA that both peers drive.
//!
//! The Battle Network games link two GBAs over a cable, so the rest of
//! this crate simulates a pair. Turn-based games with a hot-seat versus
//! mode (Advance Wars 2) do not need a cable at all: both players sit at
//! the same console and take turns with its one joypad. Netplay for them
//! is that console, simulated identically on both peers, with each tick's
//! joypad built from both players' rollback-confirmed inputs.
//!
//! How the two inputs become one joypad word is the game's business
//! ([`SharedGame::merge`]): a game that knows whose turn it is lets only
//! that player's buttons through; the default ORs them, which is what
//! two people on one controller amount to.
//!
//! The seam still speaks in pairs (`side(0)`, `side(1)`), so both seats
//! answer with the same console. Presentation calls arrive per seat and
//! are folded: the console renders if either seat wants it rendered.

use std::sync::atomic::AtomicBool;

use mgba_rollback::{LinkOptions, Peripheral, SideOptions};
use num_rational::Ratio;
use tango_match::{HostInput, Side};

use crate::gba::{to_rgba, JOYFLAGS_MASK};

/// A waiting window's picture is made again after this many ticks.
/// Ticks between two clean pictures of a mover's own view kept for its window.
const OWN_EVERY: u32 = 20;
const WATCH_EVERY: u32 = 2;

/// The scratch copy of the console a [`SharedGame::view_as`] works on.
pub trait Scratch {
    fn core(&self) -> &mgba::core::Core;
    fn core_mut(&mut self) -> &mut mgba::core::Core;
    /// One tick with `keys` held, the game's [`before_tick`](SharedGame::before_tick) first; false if it failed.
    fn tick(&mut self, keys: u32) -> bool;
    /// Four words of the game's own that live as long as the link, per seat (not in the console: they are only ever
    /// read by [`view_as`](SharedGame::view_as), so the simulation cannot see them).
    fn memory(&mut self) -> &mut [i32; 4];
    /// The picture the scratch console shows now (RGBA8, 240x160), as the host would take it after the tick.
    fn frame(&self) -> Option<Vec<u8>>;
    /// Loads the console the game asked to keep ([`SharedGame::keep_for_view`]) into the scratch console; false when
    /// there is none. The caller's own snapshot is loaded back afterwards, as always.
    fn load_kept(&mut self) -> bool;
}

struct ScratchConsole<'a> {
    link: &'a mut mgba_rollback::Link,
    game: &'static (dyn SharedGame + Send + Sync),
    mode: Option<(u8, u8)>,
    memory: &'a mut [i32; 4],
    kept: Option<&'a mgba_rollback::Snapshot>,
}

impl Scratch for ScratchConsole<'_> {
    fn core(&self) -> &mgba::core::Core {
        self.link.core(0)
    }
    fn core_mut(&mut self) -> &mut mgba::core::Core {
        self.link.core_mut(0)
    }
    fn tick(&mut self, keys: u32) -> bool {
        let word = self.game.before_tick(self.link.core_mut(0), self.mode, keys & JOYFLAGS_MASK) & JOYFLAGS_MASK;
        self.link.try_tick(&[word]).is_ok()
    }
    fn memory(&mut self) -> &mut [i32; 4] {
        self.memory
    }
    fn frame(&self) -> Option<Vec<u8>> {
        self.link.video_buffer(0).map(to_rgba)
    }
    fn load_kept(&mut self) -> bool {
        self.kept.is_some_and(|snap| self.link.load(snap).is_ok())
    }
}

/// Game support for a shared-console title.
pub trait SharedGame: Sync {
    /// The game half of [`Backend::sim_version`](tango_match::Backend::sim_version).
    fn sim_version(&self) -> u16;

    /// The joypad word the console sees this tick, from both players'
    /// sanitized inputs in absolute seat order. Must be a pure function
    /// of `core`'s state and `inputs`, so both peers (and every
    /// re-simulation) build the same word.
    fn merge(&self, core: &mgba::core::Core, inputs: &[u32]) -> u32 {
        let _ = core;
        inputs.iter().fold(0, |a, &b| a | b)
    }

    /// Every tick, before [`merge`](Self::merge), with the console in hand and every seat's keys (2, or up to 5 in a
    /// room): for a game that keeps state of its own for each seat (tangoAW2's CO selection). Like everything that
    /// touches the simulation, a pure function of the console's state, `mode` and `inputs`.
    fn seat_keys(&self, core: &mut mgba::core::Core, mode: Option<(u8, u8)>, inputs: &[u32]) {
        let _ = (core, mode, inputs);
    }

    /// Test aid (see [`tango_match::Link::test_aid`]): the game's scenario script for this tick, with the console in
    /// hand. Only ever a pure function of `tick` and the console.
    fn test_aid(&self, core: &mut mgba::core::Core, tick: u32) {
        let _ = (core, tick);
    }

    /// Runs before every tick, with the console in hand: the place for a
    /// game's runtime patches (Slippi-style memory writes). `keys` is the
    /// joypad word about to reach the console (after [`merge`](Self::merge));
    /// what comes back is what the console actually sees, so a patch can
    /// take a button for itself. `mode` is the session's match type for a
    /// netplay match or its replay, and for a console played alone
    /// whatever its host picked (`None` for nothing). Must be a pure
    /// function of core state, `mode` and `keys`, like everything else
    /// that touches the simulation: state it keeps lives in the console's
    /// RAM, so snapshots carry it through rollback.
    fn before_tick(&self, core: &mut mgba::core::Core, mode: Option<(u8, u8)>, keys: u32) -> u32 {
        let _ = (core, mode);
        keys
    }

    /// Whether `seat` is watching a turn that is not its own, so that its window is made on a scratch copy of the
    /// console ([`view_as`](Self::view_as)) and not from the console's own picture, which is the mover's: its menus,
    /// its cursor, and with fog of war its vision. Presentation only, read after the tick.
    fn watching(&self, core: &mgba::core::Core, seat: usize) -> bool {
        let _ = (core, seat);
        false
    }

    /// Read after every tick: true while the console's state is one the game wants kept for presentation
    /// ([`Scratch::load_kept`]); the state is kept on the tick this turns true. For the moment before a screen that
    /// only some seats are to see as it is. A pure read of the console, like everything the simulation depends on.
    fn keep_for_view(&self, core: &mgba::core::Core) -> bool {
        let _ = core;
        false
    }

    /// Host-side state the game keeps outside the console (what must not follow the scratch console): kept before a
    /// scratch run and handed back to [`scratch_unstash`](Self::scratch_unstash) after it.
    fn scratch_stash(&self) -> Box<dyn std::any::Any> {
        Box::new(())
    }

    fn scratch_unstash(&self, stash: Box<dyn std::any::Any>) {
        let _ = stash;
    }

    /// On a scratch copy of the console (restored from a snapshot afterwards, so nothing done here persists),
    /// make the game draw what `seat` may see of the turn: run ticks as it likes through `scratch`. Returns whether
    /// the console now shows the picture (false: show the last one made).
    fn view_as(&self, scratch: &mut dyn Scratch, seat: usize) -> bool {
        let _ = (scratch, seat);
        false
    }

    /// Whether the console shows the plain map of the mover's own turn: nothing of its menus, pages or wipes, which is when
    /// a clean picture of the seat's own view can be made for it to keep ([`view_as`](Self::view_as)) until its first
    /// waiting picture of the next turn.
    fn plain_map(&self, core: &mgba::core::Core) -> bool {
        let _ = core;
        false
    }

    /// Whether `seat` should be shown nothing right now. The engine no longer blacks a window out (a waiting seat's
    /// picture is [`view_as`](Self::view_as)'s); kept for tools that still ask.
    fn conceal(&self, core: &mgba::core::Core, seat: usize) -> bool {
        let _ = (core, seat);
        false
    }

    /// Draw game-specific help onto `seat`'s picture (RGBA8, 240x160):
    /// labels a patched mode shows that the cartridge cannot draw itself.
    /// Presentation only, read after the tick, like
    /// [`conceal`](Self::conceal); `mode` as for
    /// [`before_tick`](Self::before_tick).
    fn overlay(&self, core: &mgba::core::Core, mode: Option<(u8, u8)>, seat: usize, rgba: &mut [u8]) {
        let _ = (core, mode, seat, rgba);
    }

    /// [`overlay`](Self::overlay) for a host that can show a picture larger than the console's: `rgba` is the
    /// console's 240x160 picture, and on `Some((w, h))` it has been replaced by the finished `w` x `h` one (a whole
    /// multiple of 240x160), every overlay included. `None` (the default) leaves `rgba` untouched and the host
    /// calls [`overlay`](Self::overlay) as before. Presentation only, like it.
    fn overlay_hires(&self, core: &mgba::core::Core, mode: Option<(u8, u8)>, seat: usize, rgba: &mut Vec<u8>) -> Option<(u32, u32)> {
        let _ = (core, mode, seat, rgba);
        None
    }

    /// Traps installed on the console at boot. Like the pair engine's
    /// primer traps they must be pure functions of emulation state.
    fn traps(&self) -> Vec<(u32, Box<dyn Fn(&mut mgba::core::Core)>)> {
        Vec::new()
    }

    /// Ticks to run with an idle pad right after power-on, before the
    /// session takes over (skipping boot logos costs nobody anything).
    fn boot_ticks(&self) -> u32 {
        0
    }

    /// After [`boot_ticks`](Self::boot_ticks): whether to run one more
    /// such tick (the pad is still [`before_tick`](Self::before_tick)'s to
    /// press: a game can walk its menus for the players before the
    /// session). Like everything here, a pure function of the console and
    /// `mode`, so both peers and a replay boot to the same state.
    fn boot_more(&self, core: &mgba::core::Core, mode: Option<(u8, u8)>) -> bool {
        let _ = (core, mode);
        false
    }

    /// What a console's memory shows for the list of saved matches (the map, the day, the rules), from a state's
    /// EWRAM and IWRAM: a match is suspended when a player's connection drops for good.
    /// `core` is a live console of the same game (its ROM and patches), not at the state.
    fn describe(&self, core: &mgba::core::Core, ewram: &[u8], iwram: &[u8]) -> Option<tango_match::StateInfo> {
        let _ = (core, ewram, iwram);
        None
    }

    /// Whether the players have left the match for good, as the game
    /// sees it: on a netplay console the session then completes (its
    /// replay finished) on the tick it turns true, on both peers.
    fn match_over(&self, core: &mgba::core::Core) -> bool {
        let _ = core;
        false
    }
}

/// The most ticks [`SharedGame::boot_more`] may add (a minute of play).
const MAX_BOOT_MORE: u32 = 3600;

/// Reports [`SharedGame::match_over`]'s rise as the match's end.
#[derive(Clone)]
struct OverPoller {
    game: &'static (dyn SharedGame + Send + Sync),
    over: bool,
}

impl tango_match::telemetry::CorePoller<mgba::core::Core> for OverPoller {
    fn poll(
        &mut self,
        core: &mut mgba::core::Core,
        events: &tango_match::telemetry::EventSink,
        _round: u32,
    ) -> Option<tango_match::telemetry::CoreObs> {
        let over = self.game.match_over(core);
        if over && !self.over {
            events.match_ended();
        }
        self.over = over;
        None
    }
}

struct SharedSnapshot {
    snap: mgba_rollback::Snapshot,
    tick: u32,
}

/// One console, both seats.
pub struct SharedLink {
    inner: mgba_rollback::Link,
    game: &'static (dyn SharedGame + Send + Sync),
    mode: Option<(u8, u8)>,
    /// What each seat last asked for; the console renders if either does.
    render: [bool; tango_match::MAX_SEATS],
    /// A netplay match's end watch ([`SharedGame::match_over`]), and the
    /// session's tick count it stamps.
    telemetry: Option<tango_match::telemetry::Telemetry<mgba::core::Core>>,
    tick: u32,
    /// How many players share the console (2; a room's, up to 5). A replay's rows are pairs: seats 2.. are in the
    /// second input's `extra`.
    players: usize,
    /// Each seat's last waiting picture (shown while the game cannot make one) and its view memory.
    watched: [Option<Vec<u8>>; tango_match::MAX_SEATS],
    watched_at: [Option<u32>; tango_match::MAX_SEATS],
    /// The console's own picture as of tick `.1`, taken before the first scratch run of that tick: the scratch run
    /// leaves its own picture in the video buffer (loading the snapshot back does not redraw), so a window showing the
    /// console's picture after another seat's scratch picture would show that one.
    console_frame: Option<(Vec<u8>, u32)>,
    /// When a seat's own clean picture was last made for it to keep.
    own_at: [Option<u32>; tango_match::MAX_SEATS],
    /// Each seat's last picture that was not black, and the tick it was shown.
    good: [Option<(Vec<u8>, u32)>; tango_match::MAX_SEATS],
    /// The tick each seat's last "black picture" log line was written (instrumentation).
    black_logged: [u32; tango_match::MAX_SEATS],
    view_memory: [[i32; 4]; tango_match::MAX_SEATS],
    /// The console as [`SharedGame::keep_for_view`] last asked to keep it.
    kept: Option<mgba_rollback::Snapshot>,
    keep_was: bool,
}

impl SharedLink {
    pub fn boot(
        rom: &[u8],
        save: Option<&[u8]>,
        rtc: Option<std::time::SystemTime>,
        game: &'static (dyn SharedGame + Send + Sync),
        mode: Option<(u8, u8)>,
        cancel: Option<&AtomicBool>,
    ) -> Result<Self, crate::Error> {
        let mut inner = mgba_rollback::Link::with_options(LinkOptions {
            sides: vec![SideOptions {
                rom: rom.to_vec(),
                save: save.map(<[u8]>::to_vec),
            }],
            rtc,
            peripheral: Peripheral::Cable,
        })?;
        inner.set_traps(0, game.traps());
        for _ in 0..game.boot_ticks() {
            if cancel.is_some_and(|c| c.load(std::sync::atomic::Ordering::Relaxed)) {
                return Err(crate::Error::Cancelled);
            }
            let word = game.before_tick(inner.core_mut(0), mode, 0);
            inner.try_tick(&[word])?;
        }
        let mut more = 0;
        while more < MAX_BOOT_MORE && game.boot_more(inner.core(0), mode) {
            if cancel.is_some_and(|c| c.load(std::sync::atomic::Ordering::Relaxed)) {
                return Err(crate::Error::Cancelled);
            }
            let word = game.before_tick(inner.core_mut(0), mode, 0);
            inner.try_tick(&[word])?;
            more += 1;
        }
        let core = inner.core_mut(0);
        core.set_audio_buffer_size(16384);
        core.audio_buffer().clear();
        Ok(SharedLink {
            inner,
            game,
            mode,
            render: [true; tango_match::MAX_SEATS],
            telemetry: None,
            tick: 0,
            players: 2,
            watched: Default::default(),
            watched_at: Default::default(),
            console_frame: None,
            own_at: Default::default(),
            good: Default::default(),
            black_logged: Default::default(),
            view_memory: Default::default(),
            kept: None,
            keep_was: false,
        })
    }

    /// A console started from a stored state ([`tango_match::Link::state_image`]) in place of the boot and the walk:
    /// the ROM and save as for [`boot`](Self::boot), the traps installed, the state loaded over them. The game's
    /// own state (the match's flags, whose turn it is, every seat's choices) is all in the state's RAM.
    pub fn boot_resumed(
        rom: &[u8],
        save: Option<&[u8]>,
        rtc: Option<std::time::SystemTime>,
        game: &'static (dyn SharedGame + Send + Sync),
        mode: Option<(u8, u8)>,
        state: &[u8],
    ) -> Result<Self, crate::Error> {
        if state.len() != std::mem::size_of::<mgba::state::State>() {
            return Err(mgba::Error::CallFailed("the saved state is not this emulator's").into());
        }
        let mut inner = mgba_rollback::Link::with_options(LinkOptions {
            sides: vec![SideOptions {
                rom: rom.to_vec(),
                save: save.map(<[u8]>::to_vec),
            }],
            rtc,
            peripheral: Peripheral::Cable,
        })?;
        inner.set_traps(0, game.traps());
        // (sound: exactly a state's size, from `Link::state_image` of a compatible console)
        let loaded = unsafe { mgba::state::State::from_slice(state) };
        inner.core_mut(0).load_state(&loaded)?;
        let core = inner.core_mut(0);
        core.set_audio_buffer_size(16384);
        core.audio_buffer().clear();
        Ok(SharedLink {
            inner,
            game,
            mode,
            render: [true; tango_match::MAX_SEATS],
            telemetry: None,
            tick: 0,
            players: 2,
            watched: Default::default(),
            watched_at: Default::default(),
            console_frame: None,
            own_at: Default::default(),
            good: Default::default(),
            black_logged: Default::default(),
            view_memory: Default::default(),
            kept: None,
            keep_was: false,
        })
    }

    /// How many players share this console (see the field).
    pub fn set_players(&mut self, players: usize) {
        self.players = players.clamp(2, tango_match::MAX_SEATS);
    }

    /// Watch for the match's end ([`SharedGame::match_over`]): the handle
    /// is the match's telemetry.
    fn watch_end(&mut self) -> tango_match::telemetry::TelemetryHandle {
        let events = tango_match::telemetry::EventSink::new();
        let poller = || -> Box<dyn tango_match::telemetry::CorePoller<mgba::core::Core>> {
            Box::new(OverPoller {
                game: self.game,
                over: false,
            })
        };
        let (telemetry, handle) = tango_match::telemetry::Telemetry::new([poller(), poller()], events);
        self.telemetry = Some(telemetry);
        self.tick = 0;
        handle
    }

    /// The picture as solo play shows it: one screen for whoever moves
    /// (every human army, and the computer's turns through the game's own
    /// fog), so nothing is concealed. Tools that stand in for Play offline
    /// read this rather than a seat's side.
    pub fn solo_side(&mut self) -> Box<dyn Side + '_> {
        Box::new(SharedSide {
            link: self,
            player: 0,
            conceal: false,
        })
    }

    /// The console, for tests and tools that read its memory.
    pub fn core(&self) -> &mgba::core::Core {
        self.inner.core(0)
    }

    /// The console, for tools that poke its memory (never the simulation's
    /// own path: that goes through [`SharedGame::before_tick`]).
    pub fn core_mut(&mut self) -> &mut mgba::core::Core {
        self.inner.core_mut(0)
    }

    /// `seat`'s window while another seat plays: the picture of a scratch copy of the console, made by the game
    /// ([`SharedGame::view_as`]), after which the console is loaded back from a snapshot taken first, the sound the
    /// ticks made is dropped and the frameskip is back, so the simulation never sees any of it. The seat's last
    /// picture stands in when the game cannot make one now (a battle scene, a full-screen page).
    fn watching_frame(&mut self, seat: usize) -> Option<Vec<u8>> {
        // (a window that updates every other tick: the scratch picture is the costly part of a frame)
        if let Some((f, at)) = self.watched[seat].as_ref().zip(self.watched_at[seat]) {
            if self.tick.wrapping_sub(at) < WATCH_EVERY {
                return Some(f.clone());
            }
        }
        let made = self.scratch_frame(seat);
        match made {
            Some(f) => {
                self.watched[seat] = Some(f.clone());
                self.watched_at[seat] = Some(self.tick);
                Some(f)
            }
            None => self.watched[seat].clone(),
        }
    }

    fn scratch_frame(&mut self, seat: usize) -> Option<Vec<u8>> {
        if self.console_frame.as_ref().is_none_or(|(_, at)| *at != self.tick) {
            self.console_frame = self.inner.video_buffer(0).map(to_rgba).map(|f| (f, self.tick));
        }
        let snap = self.inner.save().ok()?;
        let game = self.game;
        let mode = self.mode;
        let kept = {
            let buf = self.inner.core_mut(0).audio_buffer();
            let n = buf.available();
            let mut kept = vec![0i16; n * 2];
            buf.read(&mut kept, n);
            kept
        };
        let stash = game.scratch_stash();
        self.inner.set_frameskip(0, 0);
        let mut frame = None;
        {
            let mut scratch = ScratchConsole { link: &mut self.inner, game, mode, memory: &mut self.view_memory[seat], kept: self.kept.as_ref() };
            if game.view_as(&mut scratch, seat) {
                frame = scratch.link.video_buffer(0).map(to_rgba);
                // (a picture caught in a screen fade, forced blank or black is no picture: the last good one stays)
                if frame.as_ref().is_some_and(|f| dark(f)) {
                    frame = None;
                }
                if let Some(f) = frame.as_mut() {
                    let core = scratch.link.core(0);
                    if game.overlay_hires(core, mode, seat, f).is_none() {
                        game.overlay(core, mode, seat, f);
                    }
                }
            }
        }
        let _ = self.inner.load(&snap);
        game.scratch_unstash(stash);
        {
            let buf = self.inner.core_mut(0).audio_buffer();
            buf.clear();
            let n = kept.len() / 2;
            buf.write(&kept, n);
        }
        self.apply_render();
        frame
    }

    fn apply_render(&mut self) {
        let on = self.render.iter().any(|&r| r);
        self.inner.set_frameskip(0, if on { 0 } else { i32::MAX });
    }
}

impl tango_match::Link for SharedLink {
    fn sanitize(&self, input: HostInput) -> HostInput {
        HostInput {
            keys: input.keys & JOYFLAGS_MASK,
            touch: None,
            extra: input.extra.map(|w| w & JOYFLAGS_MASK as u16),
        }
    }

    fn tick(&mut self, inputs: [HostInput; 2]) {
        if self.players <= 2 {
            self.tick_n(&inputs);
            return;
        }
        let mut seats = vec![inputs[0], HostInput::keys(inputs[1].keys)];
        for k in 0..self.players - 2 {
            seats.push(HostInput::keys(inputs[1].extra[k] as u32));
        }
        self.tick_n(&seats);
    }

    fn tick_n(&mut self, inputs: &[HostInput]) {
        let keys: Vec<u32> = inputs.iter().map(|i| i.keys & JOYFLAGS_MASK).collect();
        self.game.seat_keys(self.inner.core_mut(0), self.mode, &keys);
        let word = self.game.merge(self.inner.core(0), &keys) & JOYFLAGS_MASK;
        let word = self.game.before_tick(self.inner.core_mut(0), self.mode, word) & JOYFLAGS_MASK;
        self.inner.tick(&[word]);
        // (kept on the tick it turns true, not on every tick it stays so)
        let keep = self.game.keep_for_view(self.inner.core(0));
        if keep && !self.keep_was {
            self.kept = self.inner.save().ok();
        }
        self.keep_was = keep;
        if let Some(telemetry) = self.telemetry.as_mut() {
            // (one console: the second poller only keeps the pair's shape)
            let obs = telemetry.poll(0, self.inner.core_mut(0));
            telemetry.observe(obs, None, self.tick);
        }
        self.tick += 1;
    }

    fn snapshot(
        &mut self,
        _recycled: Option<tango_match::Snapshot>,
    ) -> Result<tango_match::Snapshot, tango_match::Error> {
        let snap = self.inner.save().map_err(crate::Error::from)?;
        Ok(Box::new(SharedSnapshot { snap, tick: self.tick }))
    }

    fn restore(&mut self, snapshot: &tango_match::Snapshot) -> Result<(), tango_match::Error> {
        let snapshot = snapshot
            .downcast_ref::<SharedSnapshot>()
            .expect("a shared link can only restore its own snapshots");
        self.inner.load(&snapshot.snap).map_err(crate::Error::from)?;
        self.tick = snapshot.tick;
        self.keep_was = false;
        if let Some(telemetry) = self.telemetry.as_mut() {
            // (a snapshot's tick is a count: observations from it on are revoked)
            telemetry.on_rewind(snapshot.tick.saturating_sub(1));
        }
        Ok(())
    }

    fn side(&mut self, player: usize) -> Box<dyn Side + '_> {
        Box::new(SharedSide {
            link: self,
            player,
            conceal: true,
        })
    }

    fn state_image(&mut self, snapshot: &tango_match::Snapshot) -> Option<tango_match::StateImage> {
        let snapshot = snapshot.downcast_ref::<SharedSnapshot>()?;
        let state = snapshot.snap.core_state(0);
        // FNV-1a over what the simulation reads: the registers and both RAMs (the emulator's reserved parts of the
        // image are not written, and differ between peers).
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        let mut feed = |b: &[u8]| {
            for &x in b {
                h = (h ^ x as u64).wrapping_mul(0x0000_0100_0000_01b3);
            }
        };
        for r in 0..16 {
            feed(&state.gpr(r).to_le_bytes());
        }
        feed(&state.cpsr().to_le_bytes());
        feed(state.wram());
        feed(state.iwram());
        Some(tango_match::StateImage {
            state: state.as_slice().to_vec(),
            digest: h,
            info: self.game.describe(self.inner.core(0), state.wram(), state.iwram()),
        })
    }

    fn peek(&mut self, addr: u32, buf: &mut [u8]) -> bool {
        self.inner.core(0).raw_read_range(addr, -1, buf);
        true
    }

    fn poke(&mut self, addr: u32, bytes: &[u8]) -> bool {
        self.inner.core_mut(0).raw_write_range(addr, -1, bytes);
        true
    }

    fn test_aid(&mut self, tick: u32) {
        self.game.test_aid(self.inner.core_mut(0), tick);
    }
}

struct SharedSide<'a> {
    link: &'a mut SharedLink,
    player: usize,
    /// [`SharedGame::conceal`] applies: a seat of the two-seat link. Solo
    /// play is never concealed (it was: with fog on, every turn of armies
    /// 2 and 4, the computer's included, showed the concealed picture).
    conceal: bool,
}

/// Whether a 240x160 RGBA picture is (nearly) black: a fade or a blanked screen.
fn dark(rgba: &[u8]) -> bool {
    let total: u64 = rgba.chunks(4).map(|p| p[0] as u64 + p[1] as u64 + p[2] as u64).sum();
    total < (rgba.len() as u64 / 4) * 3 * 12
}

impl SharedSide<'_> {
    fn frame_raw(&mut self) -> Option<(Vec<u8>, &'static str)> {
        // (a waiting seat whose picture cannot be made, and none was made before, sees the console's own: never a
        // blacked-out window; the game's `watching` keeps to the moments the picture can be made)
        if self.conceal && self.link.game.watching(self.link.inner.core(0), self.player) {
            if let Some(f) = self.link.watching_frame(self.player) {
                return Some((f, "watch"));
            }
        }
        let mut frame = match self.link.console_frame.as_ref().filter(|(_, at)| *at == self.link.tick) {
            Some((f, _)) => f.clone(),
            None => self.link.inner.video_buffer(0).map(to_rgba)?,
        };
        let core = self.link.inner.core(0);
        if self.link.game.overlay_hires(core, self.link.mode, self.player, &mut frame).is_none() {
            self.link.game.overlay(core, self.link.mode, self.player, &mut frame);
        }
        // The seat's own turn: until the first picture of the next waiting turn is made, its window keeps a clean picture of
        // its own view (made on the scratch console while the console shows the plain map: no menu, no cursor), never the
        // console's frame itself, which has the menu and the cursor of the moment the turn ended.
        let mover = {
            let core = self.link.inner.core(0);
            let game = self.link.game;
            (0..self.link.players.max(2)).any(|s| s != self.player && game.watching(core, s))
        };
        let own = !self.link.game.watching(self.link.inner.core(0), self.player);
        if self.conceal && mover && own && self.link.game.plain_map(self.link.inner.core(0)) {
            let due = self.link.own_at[self.player].is_none_or(|at| self.link.tick.wrapping_sub(at) >= OWN_EVERY);
            if due {
                self.link.own_at[self.player] = Some(self.link.tick);
                if let Some(f) = self.link.scratch_frame(self.player) {
                    self.link.watched[self.player] = Some(f);
                    self.link.watched_at[self.player] = None;
                }
            }
        }
        Some((frame, "console"))
    }
}

impl Side for SharedSide<'_> {
    /// A window is never black through a fault of the app's: a waiting seat's picture (made on a scratch copy) that is
    /// entirely black while the console's own is not shows the seat's last good one (up to three seconds). The game's
    /// own fades and wipes (the console's picture black too) are shown as the game draws them, in every window.
    fn frame(&mut self) -> Option<Vec<u8>> {
        let (f, path) = self.frame_raw()?;
        let (tick, seat) = (self.link.tick, self.player);
        if dark(&f) {
            let native = path == "console"
                || match self.link.console_frame.as_ref().filter(|(_, at)| *at == tick) {
                    Some((c, _)) => dark(c),
                    None => self.link.inner.video_buffer(0).map(to_rgba).is_none_or(|c| dark(&c)),
                };
            if tick.wrapping_sub(self.link.black_logged[seat]) >= 60 {
                self.link.black_logged[seat] = tick;
                let core = self.link.inner.core(0);
                log::warn!(
                    "black picture: seat {seat} tick {tick} path {path} native {native} watching {} dispcnt {:04x} bldy {:04x} good_age {:?}",
                    self.link.game.watching(core, seat),
                    core.raw_read_16(0x0400_0000, -1),
                    core.raw_read_16(0x0400_0054, -1),
                    self.link.good[seat].as_ref().map(|(_, at)| tick.wrapping_sub(*at)),
                );
            }
            if !native {
                if let Some((g, at)) = self.link.good[seat].as_ref() {
                    if tick.wrapping_sub(*at) < 180 {
                        return Some(g.clone());
                    }
                }
            }
            return Some(f);
        }
        self.link.good[seat] = Some((f.clone(), tick));
        Some(f)
    }

    fn set_render(&mut self, on: bool) {
        self.link.render[self.player] = on;
        self.link.apply_render();
    }

    fn export_save(&mut self) -> Option<Vec<u8>> {
        self.link.inner.export_save(0)
    }

    fn audio_sample_rate(&mut self) -> Ratio<u32> {
        Ratio::from_integer(self.link.inner.core(0).audio_sample_rate())
    }

    fn drain_audio(&mut self, out: &mut [i16]) -> usize {
        let buf = self.link.inner.core_mut(0).audio_buffer();
        let available = buf.available();
        buf.read(out, (out.len() / 2).min(available));
        available
    }
}


/// A shared-console game as the engine-neutral backend its registration
/// holds.
pub struct SharedBackend {
    game: &'static (dyn SharedGame + Send + Sync),
}

impl SharedBackend {
    pub const fn new(game: &'static (dyn SharedGame + Send + Sync)) -> Self {
        SharedBackend { game }
    }
}

/// Engine half of the version: shared-console engine revisions.
const SHARED_SIM_VERSION: u16 = 0x5a00;

impl tango_match::Backend for SharedBackend {
    fn sim_version(&self) -> u32 {
        ((SHARED_SIM_VERSION as u32) << 16) | self.game.sim_version() as u32
    }

    fn screen_layout(&self, _mode: tango_match::SessionMode) -> tango_match::ScreenLayout {
        crate::gba::screen_layout()
    }

    fn keys_mask(&self) -> u32 {
        JOYFLAGS_MASK
    }

    fn tps(&self) -> Ratio<u32> {
        crate::gba::TPS
    }

    /// Both peers boot the same console from seat 0's ROM and save (the
    /// host's), so the match is one machine, not two.
    fn start(&self, config: tango_match::StartConfig) -> Result<tango_match::Match, tango_match::Error> {
        let link = SharedLink::boot(
            config.roms[0],
            config.saves[0],
            Some(config.rtc),
            self.game,
            Some(config.match_type),
            config.cancel,
        )?;
        let mut link = link;
        link.set_players(config.players);
        let handle = link.watch_end();
        let mut match_ = tango_match::Match::new_n(
            link,
            config.local_player,
            config.players,
            config.present_delay,
            config.audio,
        )?;
        match_.set_telemetry(handle);
        match_.keep_checkpoints();
        Ok(match_)
    }

    /// A suspended match resumed: the same console, started from the stored state.
    fn start_resumed(&self, config: tango_match::StartConfig, state: &[u8]) -> Result<tango_match::Match, tango_match::Error> {
        let mut link = SharedLink::boot_resumed(
            config.roms[0],
            config.saves[0],
            Some(config.rtc),
            self.game,
            Some(config.match_type),
            state,
        )?;
        link.set_players(config.players);
        let handle = link.watch_end();
        let mut match_ = tango_match::Match::new_n(
            link,
            config.local_player,
            config.players,
            config.present_delay,
            config.audio,
        )?;
        match_.set_telemetry(handle);
        match_.keep_checkpoints();
        Ok(match_)
    }

    /// Played alone, the console still gets the game's runtime patches.
    fn start_solo(&self, config: tango_match::SoloConfig) -> Result<tango_match::Solo, tango_match::Error> {
        let link = SharedLink::boot(config.rom, config.save, config.rtc, self.game, config.match_type, None)?;
        Ok(tango_match::Solo::new(SharedSolo(link), config.audio))
    }

    fn open_replay(&self, config: tango_match::ReplayConfig) -> Result<tango_match::ReplaySet, tango_match::Error> {
        let boot = SharedBoot {
            rom: config.roms[0].clone(),
            save: config.saves[0].clone(),
            rtc: config.rtc,
            game: self.game,
            mode: config.match_type,
            players: config.players,
        };
        Ok(tango_match::ReplaySet::new(&config, boot))
    }
}

struct SharedBoot {
    rom: Vec<u8>,
    save: Vec<u8>,
    rtc: std::time::SystemTime,
    game: &'static (dyn SharedGame + Send + Sync),
    mode: (u8, u8),
    players: usize,
}

impl SharedBoot {
    fn link(&self, cancel: Option<&AtomicBool>) -> Result<tango_match::BootedReplay, tango_match::Error> {
        let save = (!self.save.is_empty()).then_some(self.save.as_slice());
        let mut link = SharedLink::boot(&self.rom, save, Some(self.rtc), self.game, Some(self.mode), cancel)?;
        link.set_players(self.players);
        Ok(tango_match::BootedReplay {
            link: Box::new(link),
            telemetry: None,
        })
    }
}

impl tango_match::ReplayBoot for SharedBoot {
    fn boot(&self, _observe: bool, cancel: &AtomicBool) -> Result<tango_match::BootedReplay, tango_match::Error> {
        self.link(Some(cancel))
    }

    fn boot_unprimed(&self, _observe: bool) -> Result<tango_match::BootedReplay, tango_match::Error> {
        self.link(None)
    }
}

/// The shared console played by one person: the same console, the same
/// runtime patches, one pad.
struct SharedSolo(SharedLink);

impl tango_match::Console for SharedSolo {
    fn tick(&mut self, input: HostInput) -> Result<(), tango_match::Error> {
        let link = &mut self.0;
        let word = link
            .game
            .before_tick(link.inner.core_mut(0), link.mode, input.keys & JOYFLAGS_MASK)
            & JOYFLAGS_MASK;
        link.inner
            .try_tick(&[word])
            .map_err(|e| tango_match::Error::Backend(Box::new(crate::Error::from(e))))?;
        Ok(())
    }

    fn side(&mut self) -> Box<dyn Side + '_> {
        self.0.solo_side()
    }

    fn peek(&mut self, addr: u32, buf: &mut [u8]) -> bool {
        self.0.inner.core(0).raw_read_range(addr, -1, buf);
        true
    }

    fn poke(&mut self, addr: u32, bytes: &[u8]) -> bool {
        self.0.inner.core_mut(0).raw_write_range(addr, -1, bytes);
        true
    }
}
