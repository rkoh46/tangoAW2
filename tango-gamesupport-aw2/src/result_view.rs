//! The end of a room's match, for each window: the winner sees VICTORY!, everybody else DEFEAT.
//!
//! The console is shared, so the game draws one result screen: AW2 shows VICTORY! (the tank photo, the winning
//! CO's quote, then the WIN!/LOSE page) whenever a human army is left alive, and its DEFEAT screen (the battle map
//! under the word DEFEAT, dropping in and settling) only when none is. Everyone's window used to show the winner's
//! VICTORY!, the yielder's included.
//!
//! The game's own match-end proc (`0x08037FD0`: who is alive, then `0x08037FB4` to start DEFEAT or `0x08037F94` for
//! VICTORY) is not touched: the console still plays the winner's screens and everyone's simulation is the same. A
//! seat that did not win has its picture made on a scratch copy of the console (the waiting player's window,
//! tango-backend-mgba's `SharedGame::view_as`) while the VICTORY! banner and quote are up: the scratch console ends
//! the VICTORY! proc and starts the game's own DEFEAT proc (the same calls the match-end proc makes) for the seat's
//! own army, and runs it. That takes a hundred and fifty ticks, so it is made once for each army and the pictures are
//! kept (host-side, presentation only); the window plays them from the moment it first shows DEFEAT and holds the
//! last. The WIN!/LOSE page that follows (the winner above, the loser below, each in their own CO's face) is the
//! console's own and the same for everybody.
//!
//! The scratch console is dropped afterwards (`SharedLink::scratch_frame` loads the snapshot back), so nothing here
//! reaches the simulation. The music stays the console's (the winner's fanfare).

use mgba::core::Core;
use std::sync::{Arc, Mutex};

/// The game's procs: a script word, the current and the next command, ..., `0x6C` bytes each; `+0x14` is the
/// parent (a number up to 7 for a root, else the parent proc).
const PROCS: u32 = 0x0200_D610;
const PROC_SIZE: u32 = 0x6C;
const PROC_COUNT: u32 = 32;
/// The VICTORY! proc's script and the others it starts (the banner, the quote), up to the fade that follows.
const VICTORY: std::ops::Range<u32> = 0x0861_5CB0..0x0861_5E08;
/// The script that fades the VICTORY! screens out (the WIN!/LOSE page's proc comes next).
const FADE_OUT: u32 = 0x0861_5E08;
/// `EndProc(proc)`.
const END_PROC: u32 = 0x0801_C9EC;
/// The two calls the game makes before it starts VICTORY! or DEFEAT: the screen's registers cleared.
const CLEAR: [u32; 2] = [0x0801_237C, 0x0801_2358];
/// `StartDefeat(army, parent)`: the DEFEAT proc for an army, a child of `parent` (a proc, or a root's priority).
const START_DEFEAT: u32 = 0x0804_9F08;

/// The VICTORY! proc's own script: the match-end proc starts it (`StartVictory`, `0x08037F94`).
const MASTER: u32 = 0x0861_5CB0;
/// Where it waits after its first three commands (a fade of the map, in the game's own routine).
const MASTER_WAIT: u32 = 0x0861_5CC8;

const PLAYER_STRIDE: u32 = 0x3C;
/// A block's controller (0 none, 1 human, 2 computer) and its defeated flag.
const CONTROLLER: u32 = 0x1B;
const DEFEATED: u32 = 0x14;
const ARMIES: u32 = 0x0201_7C58;

/// Ticks of the DEFEAT screen kept (its soldier, the text dropping in, then still), every second one.
const TICKS: usize = 150;

type Frames = Arc<Vec<Arc<Vec<u8>>>>;

#[derive(Default)]
struct State {
    /// The pictures of DEFEAT for an army's colour.
    frames: Vec<(u8, Frames)>,
    /// The console's frame (`Core::frame_counter`, the same on both peers) at which each seat's window first showed it.
    since: [Option<u32>; 5],
    /// The picture [`view`] chose for a seat, for [`serve`] to put on its window.
    serve: [Option<Arc<Vec<u8>>>; 5],
}

static STATE: Mutex<State> = Mutex::new(State {
    frames: Vec::new(),
    since: [None; 5],
    serve: [None, None, None, None, None],
});

/// An army's player block (the table is the game's, or Five Seas' moved one; slot 0 is neutral).
fn block(core: &Core, army: u8) -> u32 {
    crate::five::players(core) + PLAYER_STRIDE * army as u32
}

fn alive(core: &Core, army: u8) -> bool {
    core.raw_read_8(block(core, army) + CONTROLLER, -1) != 0 && core.raw_read_16(block(core, army) + DEFEATED, -1) == 0
}

/// The army the game's VICTORY! is for: the first one still alive.
pub fn winner(core: &Core) -> Option<u8> {
    let armies = (core.raw_read_8(ARMIES, -1) as u8).clamp(2, 5);
    (1..=armies).find(|&a| alive(core, a))
}

fn procs(core: &Core) -> impl Iterator<Item = (u32, u32)> + '_ {
    (0..PROC_COUNT)
        .map(|k| PROCS + PROC_SIZE * k)
        .map(|p| (p, core.raw_read_32(p, -1)))
        .filter(|&(_, s)| s != 0)
}

/// The VICTORY! banner or the winner's quote is on the console (not yet fading to the WIN!/LOSE page).
pub fn victory_showing(core: &Core) -> bool {
    let mut any = false;
    for (_, script) in procs(core) {
        any |= VICTORY.contains(&script);
        if script == FADE_OUT {
            return false;
        }
    }
    any
}

/// `SharedGame::keep_for_view`: VICTORY! has just been started and the screen is still the map's: the VICTORY! proc
/// is there and waits at its first wait ([`MASTER_WAIT`]). The host keeps the console on the first tick of that (it
/// is true for as long as the wait lasts), from the console's state alone: nothing of the game's is written for it.
pub fn marked(core: &Core) -> bool {
    procs(core).any(|(p, script)| script == MASTER && core.raw_read_32(p + 8, -1) == MASTER_WAIT)
}

/// The seat's first army.
fn army_of(seat: usize, armies: u8, players: usize) -> u8 {
    (1..=armies)
        .find(|&a| crate::pvp::seat_of_n(a, players) == seat)
        .unwrap_or(1)
}

/// Whether `seat` should be shown DEFEAT: VICTORY! is up and the seat is not the winner's.
pub fn loser(core: &Core, seat: usize) -> bool {
    victory_showing(core)
        && winner(core).is_some_and(|w| crate::pvp::seat_of_n(w, crate::online::room_players()) != seat)
}

/// `SharedGame::watching`, and the bookkeeping of the window's clock.
pub fn watching(core: &Core, seat: usize) -> bool {
    let showing = victory_showing(core);
    let mine = showing && loser(core, seat);
    if let Ok(mut st) = STATE.lock() {
        if !showing {
            // (the screens are gone: the next match makes them again)
            if st.since.iter().any(Option::is_some) || !st.frames.is_empty() {
                *st = State::default();
            }
        } else if let Some(t) = st.since.get_mut(seat) {
            if mine && t.is_none() {
                *t = Some(core.frame_counter());
            }
        }
    }
    mine
}

/// The game's DEFEAT screen on a copy of the console showing VICTORY!: ends the VICTORY! proc (its children with
/// it) and starts DEFEAT as the match-end proc would, then runs it and keeps every second picture.
fn make(scratch: &mut dyn tango_backend_mgba::Scratch, army: u8) -> Result<Frames, &'static str> {
    if !scratch.load_kept() {
        return Err("no console kept");
    }
    let core = scratch.core();
    // The match-end proc started VICTORY! and waits for it: DEFEAT is started in its place, under the same parent, so
    // that it goes on waiting (the game's own `StartDefeat` call does the same).
    let (mut master, mut parent) = (None, 3);
    for (p, script) in procs(core) {
        let up = core.raw_read_32(p + 0x14, -1);
        let child =
            (PROCS..PROCS + PROC_SIZE * PROC_COUNT).contains(&up) && VICTORY.contains(&core.raw_read_32(up, -1));
        if VICTORY.contains(&script) && !child {
            (master, parent) = (Some(p), up);
        }
    }
    let Some(master) = master else {
        return Err("no VICTORY! proc");
    };
    let mut calls: Vec<(u32, i32, i32)> = CLEAR.iter().map(|&f| (f, 0, 0)).collect();
    calls.push((START_DEFEAT, army as i32, parent as i32));
    calls.push((END_PROC, master as i32, 0));
    crate::fog_view::call_program(scratch, &calls)?;
    let mut frames = Vec::with_capacity(TICKS / 2);
    for t in 0..TICKS {
        if !scratch.tick(0) {
            return Err("tick failed");
        }
        if t % 2 == 1 {
            let f = scratch.frame().ok_or("no picture")?;
            frames.push(Arc::new(f));
        }
    }
    Ok(Arc::new(frames))
}

/// `SharedGame::view_as` for a seat shown DEFEAT: the picture to put on its window is kept for [`serve`].
pub fn view(scratch: &mut dyn tango_backend_mgba::Scratch, seat: usize) -> bool {
    let now = scratch.core().frame_counter();
    let players = crate::online::room_players();
    let armies = (scratch.core().raw_read_8(ARMIES, -1) as u8).clamp(2, 5);
    let army = army_of(seat, armies, players);
    let known = STATE
        .lock()
        .ok()
        .and_then(|st| st.frames.iter().find(|(a, _)| *a == army).map(|(_, f)| f.clone()));
    let frames = match known {
        Some(f) => f,
        None => match make(scratch, army) {
            Ok(f) => {
                if let Ok(mut st) = STATE.lock() {
                    st.frames.push((army, f.clone()));
                }
                f
            }
            Err(_) => return false,
        },
    };
    let Ok(mut st) = STATE.lock() else { return false };
    let ticks = st
        .since
        .get(seat)
        .copied()
        .flatten()
        .map_or(0, |t| now.wrapping_sub(t) as usize);
    let Some(f) = frames.get((ticks / 2).min(frames.len().saturating_sub(1))) else {
        return false;
    };
    if let Some(slot) = st.serve.get_mut(seat) {
        *slot = Some(f.clone());
    }
    true
}

/// `SharedGame::overlay`: the window of a seat that was made DEFEAT gets that picture (the scratch console's own,
/// after the ticks that made the pictures, is not the one to show).
pub fn serve(seat: usize, rgba: &mut [u8]) {
    let Ok(mut st) = STATE.lock() else { return };
    if let Some(f) = st.serve.get_mut(seat).and_then(Option::take) {
        if f.len() == rgba.len() {
            rgba.copy_from_slice(&f);
        }
    }
}
