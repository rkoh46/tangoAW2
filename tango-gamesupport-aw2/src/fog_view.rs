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
const CALLS: [(u32, bool); 5] = [(0x0802_0984, false), (0x0801_A548, true), (0x0801_A57C, true), (0x0804_3834, true), (REFRESH, false)];
/// The game's map refresh: vision planes of every army, then the terrain and unit layers redrawn.
const REFRESH: u32 = 0x0802_58CC;
/// Alignment padding between two functions (`movs r0, r0`), never executed: the refresh returns here.
pub const RETURN: u32 = 0x0802_0EDA;
/// The scratch call: +0 state (0 none, 1 asked, 2 running, 3 done), +4 the saved registers r0..r12, lr, pc.
pub const CALL: u32 = 0x0203_DF00;
const CALL_LEN: u32 = 4 + 15 * 4;

const CURRENT_PLAYER: u32 = 0x0300_33EC;

/// The army whose picture `seat` gets: its first army still playing after the current one in turn order, else any.
fn viewer_army(core: &Core, seat: usize) -> Option<u8> {
    let current = crate::pvp::current_army(core) as usize;
    let armies = core.raw_read_8(0x0201_7C58, -1) as usize;
    let alive = |a: usize| a <= armies;
    (1..=5).map(|k| (current + k - 1) % 5 + 1).find(|&a| alive(a) && crate::pvp::seat_of_n(a as u8, crate::online::room_players()) == seat).map(|a| a as u8)
}

const FOG: u32 = 0x0300_3FCD;
const MAIN_LOOP: u32 = 0x0300_0000;
/// The main-loop callback while the map is on screen and nothing else (no battle scene, no full-screen page).
const MAP_LOOP: u32 = 0x0802_2049;
/// The main-loop callback while the full-screen CO page is up.
const CO_PAGE_LOOP: u32 = 0x0804_3591;
/// gMap: size (halfwords), scroll in pixels at +4/+6 (the refresh copies them to +8/+0xA), row offsets at +0x417A,
/// terrain classes at +0x1432, the displayed vision plane at +0x234A.
const MAP: u32 = 0x0201_E450;
/// The cursor: cell and pixel position (halfword pairs).
const CURSOR: u32 = 0x0300_33E4;
const CURSOR_PX: u32 = 0x0300_33E0;
const KEY_B: u32 = 1 << 1;
/// The map menu's state: 5 once an item was chosen.
const MAP_MENU_STATE: u32 = 0x0300_14E2;

fn cell(core: &Core, x: i32, y: i32) -> u32 {
    core.raw_read_16(MAP + 0x417A + 2 * y as u32, -1) as u32 + x as u32
}

fn size(core: &Core) -> (i32, i32) {
    (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32)
}

/// Whether the army the window belongs to sees the cell now (the plane the game drew from).
fn seen(core: &Core, x: i32, y: i32) -> bool {
    core.raw_read_8(MAP + 0x234A + cell(core, x, y), -1) != 0
}

/// Where `army`'s window starts looking: its HQ.
fn anchor(core: &Core, army: u8) -> (i32, i32) {
    let (w, h) = size(core);
    for y in 0..h {
        for x in 0..w {
            let class = core.raw_read_8(MAP + 0x1432 + cell(core, x, y), -1);
            if class & 0x1F == 8 && class >> 5 == army {
                return (x, y);
            }
        }
    }
    (0, 0)
}

/// Whether the map's UI has anything running: a selected unit, a menu, a panel (the map's procs in IWRAM and in an
/// EWRAM pool, two script pointers and a Thumb function each; none while the map waits for the player), apart from
/// the two background ones.
fn procs(core: &Core) -> Vec<u32> {
    const AREAS: [(u32, u32); 2] = [(0x0300_0C00, 0x1300), (0x0200_C000, 0x2000)];
    const EVENT_SLOTS: std::ops::Range<u32> = 0x0200_C510..0x0200_C528 + 10 * 0x18;
    const BACKGROUND: [u32; 2] = [0x0803_4F8D, 0x0800_3891];
    let mut out = Vec::new();
    let mut buf = vec![0u8; 0x2000];
    for (base, len) in AREAS {
        core.raw_read_range(base, -1, &mut buf[..len as usize]);
        let word = |i: usize| u32::from_le_bytes(buf[i..i + 4].try_into().unwrap());
        for i in (0..len as usize - 12).step_by(4) {
            if EVENT_SLOTS.contains(&(base + i as u32)) {
                continue;
            }
            let (s0, s1, f) = (word(i), word(i + 4), word(i + 8));
            let script = |v: u32| (0x0840_0000..0x0870_0000).contains(&v);
            if script(s0) && script(s1) && (0x0800_0001..0x0810_0000).contains(&f) && f & 1 == 1 && !BACKGROUND.contains(&f) {
                out.push(f);
            }
        }
    }
    out
}

fn ui_open(core: &Core) -> bool {
    !procs(core).is_empty()
}

/// The procs of the mover's own UI, which B closes: the selection (`0x080228D9`), a unit picked up and walking
/// (`0x080363D1`), the command menu (`0x08035E25`), the menus' frame (`0x08019D0D`, `0x08019DED`), the build menu
/// (`0x0802DA19`, `0x0803A441`).
const UI_PROCS: [u32; 7] = [0x0802_28D9, 0x0803_63D1, 0x0803_5E25, 0x0801_9D0D, 0x0801_9DED, 0x0802_DA19, 0x0803_A441];

/// What the shared console shows, for the waiting windows.
#[derive(PartialEq, Eq, Debug)]
pub enum Phase {
    /// The battle map, with nothing on it or only the mover's own UI: the waiting window is made on a scratch console.
    Map,
    /// The "Next turn" hand-off screen (a map-menu item chosen and nothing running): the same picture for everybody.
    HandOff,
    /// Anything else running on the map (the turn's banners, a CO Power, a battle, an attack target being chosen):
    /// with fog the waiting window keeps its last picture, without it shows the console's.
    Busy,
    /// The mover's full-screen CO page: never shown; the waiting window keeps its last picture.
    Page,
}

pub fn phase(core: &Core) -> Phase {
    match core.raw_read_32(MAIN_LOOP, -1) {
        MAP_LOOP => {}
        CO_PAGE_LOOP => return Phase::Page,
        _ => return Phase::Busy,
    }
    let running = procs(core);
    // (End's place in the map menu is not always the same, so the hand-off is also told by its look: a map-menu item
    // chosen, nothing running, and the map's window (WIN0, always on while the map shows) off)
    let window_off = core.raw_read_16(0x0400_0000, -1) & 0x2000 == 0;
    if running.is_empty() && (crate::pvp::turn_ended(core) || (core.raw_read_8(MAP_MENU_STATE, -1) == 5 && window_off)) {
        return Phase::HandOff;
    }
    if running.iter().all(|f| UI_PROCS.contains(f)) {
        Phase::Map
    } else {
        Phase::Busy
    }
}

pub fn fog(core: &Core) -> bool {
    core.raw_read_8(FOG, -1) != 0
}

type Scratch<'a> = &'a mut dyn tango_backend_mgba::Scratch;

fn run(scratch: Scratch, keys: &[u32]) -> Result<(), &'static str> {
    keys.iter().all(|&k| scratch.tick(k)).then_some(()).ok_or("tick failed")
}

/// Calls the game's viewer setup and map refresh at the next flush, runs until they have returned (they can take more
/// than a frame), then `settle` more ticks.
fn refresh(scratch: Scratch, settle: usize) -> Result<(), &'static str> {
    let core = scratch.core_mut();
    core.raw_write_8(CALL, -1, 1);
    core.raw_write_8(CALL + 1, -1, 0);
    let mut n = 0;
    while scratch.core().raw_read_8(CALL, -1) != 3 {
        n += 1;
        if n > 30 {
            return Err("the refresh did not return");
        }
        run(scratch, &[0])?;
    }
    run(scratch, &vec![0; settle])
}

/// The waiting seat's picture, on the scratch console: B closes whatever the mover has open (build, command and map
/// menus, a selected unit's range, an attack ring, info panels: it never sees them); with fog the game is told that
/// the waiting army is the current one and refreshes the map for it (the vision of its own units, the mover's units
/// in the cells it does not see gone); the cursor and the camera follow the mover only through cells the waiting
/// army sees, and stay where they were (the army's HQ at first) otherwise. False when the console is not showing the
/// map (a battle scene, a full-screen page): the caller keeps the last picture.
pub fn view(scratch: Scratch, seat: usize) -> bool {
    let r = view_inner(scratch, seat);
    r.is_ok()
}

fn view_inner(scratch: Scratch, seat: usize) -> Result<(), &'static str> {
    let on_map = |s: &dyn tango_backend_mgba::Scratch| s.core().raw_read_32(MAIN_LOOP, -1) == MAP_LOOP;
    if phase(scratch.core()) != Phase::Map {
        return Err("not the plain map");
    }
    let fog = scratch.core().raw_read_8(FOG, -1) != 0;
    let mover_cell = (scratch.core().raw_read_16(CURSOR, -1) as i32, scratch.core().raw_read_16(CURSOR + 2, -1) as i32);
    for _ in 0..4 {
        if !ui_open(scratch.core()) {
            break;
        }
        run(scratch, &[KEY_B, KEY_B, 0])?;
    }
    if !on_map(scratch) {
        return Err("left the map loop");
    }
    if !fog {
        // (the turn as played, but the mover's menus closed)
        return run(scratch, &[0]);
    }
    let (w, h) = size(scratch.core());
    let mut mem = *scratch.memory();
    let army = viewer_army(scratch.core(), seat).ok_or("no army")?;
    scratch.core_mut().raw_write_8(CURRENT_PLAYER, -1, army);
    if mem[0] == 0 {
        let (ax, ay) = anchor(scratch.core(), army);
        mem = [1, (ax - 7).clamp(0, (w - 15).max(0)), (ay - 4).clamp(0, (h - 10).max(0)), 0];
    }
    // The camera and the cursor where the window last had them, the game's refresh for the waiting army...
    let place = |scratch: Scratch, cx: i32, cy: i32, cursor: (i32, i32)| {
        let core = scratch.core_mut();
        for (at, v) in [(4u32, cx * 16), (6, cy * 16), (8, cx * 16), (0xA, cy * 16)] {
            core.raw_write_16(MAP + at, -1, v as u16);
        }
        core.raw_write_16(CURSOR, -1, cursor.0 as u16);
        core.raw_write_16(CURSOR + 2, -1, cursor.1 as u16);
        core.raw_write_16(CURSOR_PX, -1, (cursor.0 * 16) as u16);
        core.raw_write_16(CURSOR_PX + 2, -1, (cursor.1 * 16) as u16);
    };
    let (mut cx, mut cy) = (mem[1], mem[2]);
    place(scratch, cx, cy, (cx + 7, cy + 4));
    scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
    refresh(scratch, 2)?;
    // ... and if the mover's cursor is on a cell it sees, the camera follows it there and the cursor shows.
    let (x, y) = mover_cell;
    let follow = x < w && y < h && seen(scratch.core(), x, y);
    // (the window has no cursor of its own: it is hidden unless it is the mover's, over a cell the window sees)
    scratch.core_mut().raw_write_8(CALL + 2, -1, !follow as u8);
    if follow {
        cx = if x < cx { x } else if x > cx + 14 { x - 14 } else { cx }.clamp(0, (w - 15).max(0));
        cy = if y < cy { y } else if y > cy + 9 { y - 9 } else { cy }.clamp(0, (h - 10).max(0));
        place(scratch, cx, cy, mover_cell);
        refresh(scratch, 2)?;
    } else {
        run(scratch, &[0, 0])?;
    }
    *scratch.memory() = [1, cx, cy, 0];
    Ok(())
}

/// The sprite list the game copies to OAM at the flush: its start and the next free entry, 8 bytes each.
const SPRITE_LIST: u32 = 0x0300_0268;
const NEXT_SPRITE: u32 = 0x0300_2F2C;

/// Hides the cursor's sprites (the small ones of palette 1 around its pixel position on the screen) and its info panel
/// from the frame's sprite list: the waiting window has no cursor of its own.
fn hide_cursor(core: &mut Core) {
    let start = core.raw_read_32(SPRITE_LIST, -1);
    let end = core.raw_read_32(NEXT_SPRITE, -1);
    if !(0x0300_0000..0x0300_8000).contains(&start) || end < start || end - start > 128 * 8 {
        return;
    }
    let sx = core.raw_read_16(CURSOR_PX, -1) as i32 - core.raw_read_16(MAP + 4, -1) as i16 as i32;
    let sy = core.raw_read_16(CURSOR_PX + 2, -1) as i32 - core.raw_read_16(MAP + 6, -1) as i16 as i32;
    let mut at = start;
    while at + 8 <= end {
        let (a0, a1, a2) = (core.raw_read_16(at, -1), core.raw_read_16(at + 2, -1), core.raw_read_16(at + 4, -1));
        let x = ((a1 & 0x1FF) as i32) << 23 >> 23;
        let y = (a0 & 0xFF) as i32;
        let small = a0 >> 14 != 2 && a1 >> 14 < 2; // (not a tall sprite, not 32 wide or more)
        let cursor = a2 >> 12 == 1 && small && (sx - 12..sx + 24).contains(&x) && (sy - 12..sy + 24).contains(&y);
        // The info panel of the cell under it (terrain, unit), in the lower corners: sprites in the units' and
        // cursor's palettes, not the buildings' (8 to 13).
        let panel = y >= 88 && (a2 >> 12 < 8 || (a0 >> 10) & 3 == 1) && (x < 72 || x >= 168);
        if a0 & 0x300 != 0x200 && (cursor || panel) {
            core.raw_write_16(at, -1, (a0 & !0x300) | 0x200);
        }
        at += 8;
    }
}

/// At the sprite flush: hides the cursor if asked, and starts the asked call.
pub fn at_flush(core: &mut Core) {
    if core.raw_read_8(CALL + 2, -1) == 1 {
        hide_cursor(core);
    }
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
    cpu.set_thumb_pc(CALLS[0].0);
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
    if let Some(&(f, army_arg)) = CALLS.get(next) {
        core.raw_write_8(CALL + 1, -1, next as u8 + 1);
        let army = core.raw_read_8(CURRENT_PLAYER, -1) as i32;
        let cpu = core.gba_mut().cpu_mut();
        if army_arg {
            cpu.set_gpr(0, army);
        }
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
