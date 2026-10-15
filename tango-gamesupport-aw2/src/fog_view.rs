//! The waiting player's window in a Fog of War match: the other army's turn, live, through the waiting player's own
//! fog.
//!
//! The console is shared, and with fog on the game draws the picture of the army whose turn it is: the mover's
//! vision, so what the waiting player would see on the console's own picture is the mover's secrets. Presentation
//! only, the window of the waiting seat is made on a scratch copy of the console (tango-backend-mgba's `shared.rs`
//! snapshots it, runs the ticks [`begin`] asks for, takes the picture and loads the snapshot back, so nothing here
//! reaches the simulation): the scratch console is told that the waiting player's army is the current one and the
//! game is asked, by its own routine, to refresh the map (`sub_080258CC`: the vision planes of the armies, then the
//! terrain and unit layers of the screen), the way it does at the start of every turn. The game then draws what that
//! army sees: fogged cells dark, the other army's units in them gone, its own units shown.
//!
//! The routine is called from the sprite flush trap (once per frame, after the frame's logic) as a call and return
//! on the emulated CPU: the registers are kept in EWRAM, a trap at padding that is never executed catches the
//! return, and the interrupted code carries on. All of it is in the scratch console's RAM, which is dropped.

use mgba::core::Core;

/// The game's choice of which armies' vision the next refresh builds (`sub_08020984`: from the current army and its
/// controller, which armies are viewers), then the map refresh, as a turn start runs them.
const CALLS: [u32; 2] = [0x0802_0984, REFRESH];
/// The game's map refresh: vision planes of every army, then the terrain and unit layers redrawn.
const REFRESH: u32 = 0x0802_58CC;
/// Alignment padding between two functions (`movs r0, r0`), never executed: the refresh returns here.
pub const RETURN: u32 = 0x0802_0EDA;
/// The scratch call: +0 state (0 none, 1 asked, 2 running, 3 done), +4 the saved registers r0..r12, lr, pc.
pub const CALL: u32 = 0x0203_DF00;
const CALL_LEN: u32 = 4 + 15 * 4;

const CURRENT_PLAYER: u32 = 0x0300_33EC;

/// Ticks the scratch console runs: the call at the first flush, then the frames that carry the redraw to the screen.
pub const TICKS: u32 = 4;

/// The army whose picture `seat` gets: its first army still playing after the current one in turn order (the army
/// that will play next, whose "Next turn" screen it will see), else any.
pub fn viewer_army(core: &Core, seat: usize) -> Option<u8> {
    let current = crate::pvp::current_army(core) as usize;
    let armies = core.raw_read_8(0x0201_7C58, -1) as usize;
    let alive = |a: usize| a <= armies;
    (1..=5).map(|k| (current + k - 1) % 5 + 1).find(|&a| alive(a) && crate::pvp::seat_of(a as u8) == seat).map(|a| a as u8)
}

/// Prepares the scratch console for `seat`'s picture and returns the ticks to run.
pub fn begin(core: &mut Core, seat: usize) -> u32 {
    let Some(army) = viewer_army(core, seat) else { return 0 };
    core.raw_write_8(CURRENT_PLAYER, -1, army);
    core.raw_write_8(CALL, -1, 1);
    core.raw_write_8(CALL + 1, -1, 0);
    TICKS
}

/// At the sprite flush: starts the asked call.
pub fn at_flush(core: &mut Core) {
    if core.raw_read_8(CALL, -1) != 1 {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    let mut saved = [0u8; CALL_LEN as usize - 4];
    for r in 0..13 {
        saved[4 * r..4 * r + 4].copy_from_slice(&(cpu.gpr(r) as u32).to_le_bytes());
    }
    saved[52..56].copy_from_slice(&(cpu.gpr(14) as u32).to_le_bytes());
    saved[56..60].copy_from_slice(&cpu.thumb_pc().to_le_bytes());
    cpu.set_gpr(14, (RETURN | 1) as i32);
    cpu.set_thumb_pc(CALLS[0]);
    core.raw_write_range(CALL + 4, -1, &saved);
    core.raw_write_8(CALL, -1, 2);
    core.raw_write_8(CALL + 1, -1, 1);
}

/// The refresh has returned: back to the flush.
pub fn returned(core: &mut Core) {
    if core.raw_read_8(CALL, -1) != 2 {
        return;
    }
    let next = core.raw_read_8(CALL + 1, -1) as usize;
    if let Some(&f) = CALLS.get(next) {
        core.raw_write_8(CALL + 1, -1, next as u8 + 1);
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(14, (RETURN | 1) as i32);
        cpu.set_thumb_pc(f);
        return;
    }
    let mut saved = [0u8; CALL_LEN as usize - 4];
    core.raw_read_range(CALL + 4, -1, &mut saved);
    let word = |i: usize| u32::from_le_bytes(saved[4 * i..4 * i + 4].try_into().unwrap());
    let cpu = core.gba_mut().cpu_mut();
    for r in 0..13 {
        cpu.set_gpr(r, word(r) as i32);
    }
    cpu.set_gpr(14, word(13) as i32);
    cpu.set_thumb_pc(word(14));
    core.raw_write_8(CALL, -1, 3);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(RETURN, Box::new(returned))]
}
