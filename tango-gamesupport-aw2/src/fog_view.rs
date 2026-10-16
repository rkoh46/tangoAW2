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
    let armies = crate::five::armies(core) as usize;
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
const KEY_A: u32 = 1;
const KEY_B: u32 = 1 << 1;
/// The map menu's state: 5 once an item was chosen.
const MAP_MENU_STATE: u32 = 0x0300_14E2;

/// The CO panel's state (`0x03003130`, kept by the map's per-frame cursor routine `0x08027654`): +0 the side it has
/// slid to (1 right, 0 left), +4 its x (a word). The panel is at the top corner away from the cursor: with the cursor in
/// the screen's upper half, the right corner while the cursor's pixel x is 127 or less, else the left; with it in the
/// lower half, the side it last had. A panel changing sides slides off one edge and in from the other (about ten
/// frames), and the scratch console only runs a few.
const PANEL_STATE: u32 = 0x0300_3130;
const PANEL_X_LEFT: u32 = 3;
const PANEL_X_RIGHT: u32 = 173;

/// Puts the CO panel where the game would have it at rest for the cursor as it is now, so that the scratch picture
/// has it (the funds and the CO of the army it was told is the current one), not a panel sliding between two corners.
///
/// With the cursor in the lower half the panel keeps the side it last had: the seat's own (`last`, 1 left, 2 right, 0
/// none yet: the console's), so that the mover opening a menu, which moves the console's panel, does not move the
/// waiting window's. Returns the side the panel was put at.
fn settle_panel(core: &mut Core, last: i32) -> i32 {
    let sx = (core.raw_read_16(CURSOR, -1) as i32 * 16 - core.raw_read_16(MAP + 4, -1) as i32) as i16;
    let sy = (core.raw_read_16(CURSOR + 2, -1) as i32 * 16 - core.raw_read_16(MAP + 6, -1) as i32) as i16;
    let right = if sy <= 0x4F {
        sx <= 0x7F
    } else if last != 0 {
        last == 2
    } else {
        core.raw_read_8(PANEL_STATE, -1) == 1
    };
    core.raw_write_8(PANEL_STATE, -1, right as u8);
    core.raw_write_32(PANEL_STATE + 4, -1, if right { PANEL_X_RIGHT } else { PANEL_X_LEFT });
    if right { 2 } else { 1 }
}

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

/// Whether any cell of the 15 x 10 window at (`cx`, `cy`) is seen by the army the window belongs to.
fn window_sees(core: &Core, cx: i32, cy: i32, w: i32, h: i32) -> bool {
    (cy..(cy + 10).min(h)).any(|y| (cx..(cx + 15).min(w)).any(|x| seen(core, x, y)))
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
pub fn procs(core: &Core) -> Vec<u32> {
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

/// The console shows the plain map with nothing of the mover's UI on it.
pub fn plain_map(core: &Core) -> bool {
    phase(core) == Phase::Map && !ui_open(core) && steady_regs(core)
}

fn ui_open(core: &Core) -> bool {
    !procs(core).is_empty()
}

/// The procs of the mover's own UI, which B closes: the selection (`0x080228D9`), a unit picked up and walking
/// (`0x080363D1`), the command menu (`0x08035E25`), the menus' frame (`0x08019D0D`, `0x08019DED`), the build menu
/// (`0x0802DA19`, `0x0803A441`), the info pages opened with R on the map: the terrain's (`0x08046D31`, `0x08047079`)
/// and a unit's (`0x0803A69D`, `0x0803A5B9`), the Save question (`0x08014401`, `0x080195F9`), the map overview START
/// opens (`0x0802C391`, `0x0802C3D1`, `0x080375D5`) and the Intel table (`0x080466DD`).
const UI_PROCS: [u32; 17] = [
    0x0802_28D9, 0x0803_63D1, 0x0803_5E25, 0x0801_9D0D, 0x0801_9DED, 0x0802_DA19, 0x0803_A441, 0x0804_6D31, 0x0804_7079, 0x0803_A69D, 0x0803_A5B9,
    0x0801_4401, 0x0801_95F9, 0x0802_C391, 0x0802_C3D1, 0x0803_75D5, 0x0804_66DD,
];
/// Whether a proc belongs to the Rules page and its wipes (its own: `0x0806D000..0x0806E000`, and `0x08065961`).
fn rules_proc(f: u32) -> bool {
    (0x0806_D000..0x0806_E000).contains(&f) || f == 0x0806_5961
}

/// Test aid (`AW2_BUSY_LOG=1`): each distinct set of running procs that makes the phase Busy, once.
pub fn log_busy(core: &Core) {
    static SEEN: std::sync::Mutex<Vec<Vec<u32>>> = std::sync::Mutex::new(Vec::new());
    if std::env::var_os("AW2_BUSY_LOG").is_none() {
        return;
    }
    let mut p = procs(core);
    p.sort();
    let mut seen = SEEN.lock().unwrap();
    if !seen.contains(&p) {
        eprintln!("busy procs {:x?} loop {:08x} fog {} menu {} chosen {:?}", p, core.raw_read_32(MAIN_LOOP, -1), fog(core), core.raw_read_8(MAP_MENU_STATE, -1), crate::pvp::chosen_item(core));
        seen.push(p);
    }
}

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
    /// A battle scene (the combat animation with the COs' faces): with fog it is shown to the seats that see the attacker or
    /// its target, the others keep their last clean picture; without fog it is the console's for everybody.
    Scene,
    /// A wipe or fade into or out of the mover's menu or page, or between two screens: the waiting window keeps its last
    /// clean picture until the map is plain again.
    Moving,
}

/// The battle scene's procs (`0x080501DD`, many of them, while the scene plays; the main-loop callback is 0).
const SCENE_PROC: u32 = 0x0805_01DD;

/// What each seat's window last saw of the map (width, height, cells seen), for the seats' share of a battle scene.
static VISION: std::sync::Mutex<[Option<(i32, i32, Vec<bool>)>; 5]> = std::sync::Mutex::new([None, None, None, None, None]);

/// What `seat`'s window last saw of the map: width, height and the cells it saw (for the test tools).
pub fn seat_vision(seat: usize) -> Option<(i32, i32, Vec<bool>)> {
    VISION.lock().unwrap().get(seat).cloned().flatten()
}

/// The procs of the pages' wipes and fades in and out (the CO page's, the map overview's): the mover's, never shown.
const WIPE_PROCS: [u32; 2] = [0x0801_11AD, 0x0802_C451];

/// The registers of the plain map (what the game sets up once its screen is built): window 0 on with its inside and
/// outside layers, no mosaic, and no fade (the darkening behind the cursor's panel, BLDCNT 0x1FDF, is part of it).
fn steady_regs(core: &Core) -> bool {
    let io = |o: u32| core.raw_read_16(0x0400_0000 + o, -1);
    let (bldcnt, bldy) = (io(0x50), io(0x54));
    io(0) & 0x2000 != 0 && io(0x48) == 0x003F && io(0x4A) == 0x001F && io(0x4C) == 0 && (bldy == 0 || bldcnt == 0x1FDF)
}

/// The mover has chosen from the map menu or opened a page and the game is wiping into it or out of it, or is
/// between two screens (the main-loop callback is 0 or the map's while the registers are not the plain map's, or the
/// page wipe proc runs): the screen shows a transition, never a picture to copy. A turn's own banners (the menu state
/// is reset by then) and the hand-off are not this.
fn moving(core: &Core) -> bool {
    let menu = core.raw_read_8(MAP_MENU_STATE, -1);
    if !(menu == 4 || menu == 5) || crate::pvp::turn_ended(core) {
        return false;
    }
    let running = procs(core);
    if !running.iter().all(|f| UI_PROCS.contains(f) || WIPE_PROCS.contains(f)) {
        return false;
    }
    match core.raw_read_32(MAIN_LOOP, -1) {
        0 => true,
        MAP_LOOP => running.iter().any(|f| WIPE_PROCS.contains(f)) || !steady_regs(core),
        _ => false,
    }
}

/// The main-loop callback is 0 (between screens): the Intel menu's Rules page and the wipes of the mover's pages.
/// None when it is not 0.
fn between_screens(core: &Core) -> Option<Phase> {
    if core.raw_read_32(MAIN_LOOP, -1) != 0 {
        return None;
    }
    let running = procs(core);
    if running.iter().any(|&f| rules_proc(f)) {
        Some(Phase::Page)
    } else if running.contains(&SCENE_PROC) {
        Some(Phase::Scene)
    } else if moving(core) {
        Some(Phase::Moving)
    } else {
        None
    }
}

/// A screen between two others that belongs to the mover's own pages ([`between_screens`]): the waiting window is
/// made like on the map (there is no battle scene callback to ask).
pub fn between_screens_view(core: &Core) -> bool {
    between_screens(core).is_some()
}

pub fn phase(core: &Core) -> Phase {
    match core.raw_read_32(MAIN_LOOP, -1) {
        MAP_LOOP => {}
        CO_PAGE_LOOP => return Phase::Page,
        0 => return between_screens(core).unwrap_or(Phase::Busy),
        _ => return Phase::Busy,
    }
    let running = procs(core);
    if crate::online::input_log_on() {
        static LAST: std::sync::Mutex<(bool, u8, usize)> = std::sync::Mutex::new((false, 0, 0));
        let now = (crate::pvp::turn_ended(core), core.raw_read_8(MAP_MENU_STATE, -1), running.len());
        let mut last = LAST.lock().unwrap();
        if *last != now {
            log::info!("fog-phase: turn_ended {} menu_state {} procs {:x?}", now.0, now.1, running);
            *last = now;
        }
    }
    if running.is_empty() && crate::pvp::turn_ended(core) {
        return Phase::HandOff;
    }
    // A CO Power just chosen from the map menu: the game's own scene (the CO's lines over the map, the full-screen
    // cut-in). Without fog it is shown as it is; with fog the waiting window holds its last picture (the lines come over
    // the mover's own view of the map); until the plain map is back.
    if crate::pvp::chosen_item(core) == Some(crate::pvp::MENU_POWER)
        && !running.iter().any(|f| *f == 0x0801_9D0D || *f == 0x0801_9DED)
        && !(running.is_empty() && steady_regs(core))
    {
        return Phase::Busy;
    }
    if moving(core) {
        return Phase::Moving;
    }
    if running.iter().all(|f| UI_PROCS.contains(f)) {
        Phase::Map
    } else if running.iter().all(|f| ANIMATION_PROCS.contains(f)) {
        // A unit's own animation of the turn (walking, capturing, a build or an attack's result): the allowlist.
        Phase::Busy
    } else {
        // Anything else (the mover's UI with an animation, a screen nobody has listed): nothing of it is shown, the window
        // holds its last clean picture.
        Phase::Moving
    }
}

/// The animations of the mover's turn that may be shown as they are (without fog; with fog the window holds its picture):
/// the procs seen while units walk, capture, are built and fight on the map.
const ANIMATION_PROCS: [u32; 6] = [0x0802_A509, 0x0802_7DD9, 0x0802_7905, 0x0802_788D, 0x0802_9FE5, 0x0802_A3FD];

/// Test aid (`TANGOAW2_INPUT_LOG=1`): where the cursor is and which cells the army owns (HQ, factory, ...), for scripting.
pub(crate) fn log_cells(core: &Core, army: u8) {
    let (w, h) = size(core);
    let mut owned = Vec::new();
    for y in 0..h {
        for x in 0..w {
            let class = core.raw_read_8(MAP + 0x1432 + cell(core, x, y), -1);
            if class >> 5 == army && (5..=13).contains(&(class & 0x1F)) {
                owned.push(format!("({x},{y}):{}", class & 0x1F));
            }
        }
    }
    // (the Teams record's controller bytes, 1 human and 2 computer: every army of an online match is a human's)
    let rec = crate::tag_ui::record(core) + if crate::five::active(core) { 0x90 } else { 0x09 };
    let controllers: Vec<u8> = (0..5).map(|a| core.raw_read_8(rec + a, -1)).collect();
    log::info!(
        "cells: army {army} controllers {controllers:?} cursor ({},{}) map {w}x{h} owned {}",
        core.raw_read_16(CURSOR, -1),
        core.raw_read_16(CURSOR + 2, -1),
        owned.join(" ")
    );
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

/// A program of calls for the scratch console to run instead of the fog refresh's own list (the result screens'
/// view, crate::result_view): the game function, then r0 and r1. Host-side and presentation only (the scratch console
/// runs it and is dropped); empty when none is asked for.
static PROGRAM: std::sync::Mutex<Vec<(u32, i32, i32)>> = std::sync::Mutex::new(Vec::new());
/// In a program, r0 as the current army (what the fog refresh's own list passes where it takes one).
pub const ARMY: i32 = i32::MIN;

/// The `n`th call of the list being run: the function and what goes in r0 and r1 (`None`: as they are).
fn step(n: usize) -> Option<(u32, Option<i32>, Option<i32>)> {
    let prog = PROGRAM.lock().unwrap();
    if !prog.is_empty() {
        return prog.get(n).map(|&(f, r0, r1)| (f, Some(r0), Some(r1)));
    }
    CALLS.get(n).map(|&(f, army_arg)| (f, army_arg.then_some(ARMY), None))
}

/// Runs `calls` (function, r0, r1) on the scratch console at its next sprite flush, one after the other, and waits
/// for the last to return (a few frames at most).
pub fn call_program(scratch: Scratch, calls: &[(u32, i32, i32)]) -> Result<(), &'static str> {
    *PROGRAM.lock().unwrap() = calls.to_vec();
    let r = refresh(scratch, 0);
    PROGRAM.lock().unwrap().clear();
    r
}

/// The waiting seat's picture, on the scratch console: B closes whatever the mover has open (build, command and map
/// menus, a selected unit's range, an attack ring, info panels: it never sees them); with fog the game is told that
/// the waiting army is the current one and refreshes the map for it (the vision of its own units, the mover's units
/// in the cells it does not see gone); the cursor and the camera follow the mover only through cells the waiting
/// army sees, and stay where they were (the army's HQ at first) otherwise. False when the console is not showing the
/// map (a battle scene, a full-screen page): the caller keeps the last picture.
pub fn view(scratch: Scratch, seat: usize) -> bool {
    let r = view_inner(scratch, seat);
    if let (Err(e), true) = (&r, std::env::var_os("AW2_VIEW_DEBUG").is_some()) {
        eprintln!("view seat {seat}: {e} (phase {:?})", phase(scratch.core()));
    }
    r.is_ok()
}

/// A battle scene during a fog match: the seat is shown the console's picture when its last view of the map sees the
/// attacker's cell (where the cursor is now) or the target's (where it was last on the map).
fn scene_view(scratch: Scratch, seat: usize) -> Result<(), &'static str> {
    let core = scratch.core();
    let attacker = (core.raw_read_8(CURSOR, -1) as i32, core.raw_read_8(CURSOR + 2, -1) as i32);
    let target = (core.raw_read_8(crate::pvp::LAST_CELL, -1) as i32, core.raw_read_8(crate::pvp::LAST_CELL + 1, -1) as i32);
    let vision = VISION.lock().unwrap();
    let (w, h, seen) = vision.get(seat).and_then(|v| v.as_ref()).ok_or("no view of the map yet")?;
    let sees = |(x, y): (i32, i32)| x >= 0 && y >= 0 && x < *w && y < *h && seen[(y * w + x) as usize];
    if sees(attacker) || sees(target) {
        scratch.show_console();
        Ok(())
    } else {
        Err("the scene is out of sight")
    }
}

/// For the view log: the phase the waiting windows are decided by, the running procs, the registers, the cursor.
pub fn debug_line(core: &Core) -> String {
    let io = |o: u32| core.raw_read_16(0x0400_0000 + o, -1);
    format!("phase {:?} army {} fog {} loop {:08x} procs {:x?} disp {:04x} win {:04x}/{:04x} bld {:04x} menu {} cursor_up {} cutin {}", phase(core), core.raw_read_8(CURRENT_PLAYER, -1), fog(core), core.raw_read_32(MAIN_LOOP, -1), procs(core), io(0), io(0x48), io(0x4A), io(0x50), core.raw_read_8(MAP_MENU_STATE, -1), mover_cursor_up(core), power_cutin(core))
}

/// The cursor's corner sprites are in the sprite list the console is about to flush: the mover's own UI is on the picture.
pub fn mover_cursor_up(core: &Core) -> bool {
    let (start, end) = (core.raw_read_32(SPRITE_LIST, -1), core.raw_read_32(NEXT_SPRITE, -1));
    if !(0x0300_0000..0x0300_8000).contains(&start) || end < start || end - start > 128 * 8 {
        return false;
    }
    (start..end).step_by(8).any(|at| {
        let (a0, a2) = (core.raw_read_16(at, -1), core.raw_read_16(at + 4, -1));
        a2 >> 12 == 1 && matches!(a2 & 0x3FF, 0x365 | 0x369) && a0 & 0x300 != 0x200
    })
}

/// A CO Power chosen from the map menu is playing out (its lines over the map, the full-screen cut-in, the fades).
pub fn power_scene(core: &Core) -> bool {
    if core.raw_read_32(MAIN_LOOP, -1) != MAP_LOOP || crate::pvp::chosen_item(core) != Some(crate::pvp::MENU_POWER) {
        return false;
    }
    let running = procs(core);
    !running.iter().any(|f| *f == 0x0801_9D0D || *f == 0x0801_9DED) && !(running.is_empty() && steady_regs(core))
}

/// The power's full-screen cut-in is fully up (the CO's portrait, the red bands, the name of the power): BG 0 on its own, the
/// fade to and from the mover's map over (BLDALPHA 16 : 0), so there is no map in the picture.
pub fn power_cutin(core: &Core) -> bool {
    let io = |o: u32| core.raw_read_16(0x0400_0000 + o, -1);
    power_scene(core) && io(0) & 0x1F00 == 0x1F00 && io(0x50) == 0x1E41 && io(0x52) == 0x0010 && io(0x54) == 0
}

/// The banks of the background palette the units are drawn with (the army colours and the greyed moved units': bank 11
/// for the land units, the others for ships, aircraft and the rest; a moved Cruiser was blue on a blue window with bank
/// 11 alone): the refresh
/// that makes the waiting army's view rebuilds them for the army it was told is the current one, which draws the mover's
/// units that have moved in the viewer's colours. They are put back as the console has them.
const UNIT_BANKS: [usize; 8] = [8, 9, 10, 11, 12, 13, 14, 15];

fn banks_env() -> Vec<usize> {
    std::env::var("AW2_RESTORE_BANKS").ok().map(|v| v.split(',').filter_map(|x| x.parse().ok()).collect()).unwrap_or_else(|| UNIT_BANKS.to_vec())
}

fn restore_unit_palettes(core: &mut Core, buffer: &[u8], ram: &[u8]) {
    for bank in banks_env() {
        let (lo, hi) = (bank * 32, bank * 32 + 32);
        core.raw_write_range(0x0300_20C0 + lo as u32, -1, &buffer[lo..hi]);
        core.raw_write_range(0x0500_0000 + lo as u32, -1, &ram[lo..hi]);
    }
}

fn view_inner(scratch: Scratch, seat: usize) -> Result<(), &'static str> {
    if phase(scratch.core()) == Phase::Scene {
        return scene_view(scratch, seat);
    }
    if scratch.core().raw_read_8(FOG, -1) != 0 && power_cutin(scratch.core()) {
        // The mover's CO Power: every seat sees the cut-in (it has no map in it), not the lines or the fades over the mover's map.
        scratch.show_console();
        return Ok(());
    }
    if phase(scratch.core()) == Phase::Busy && scratch.core().raw_read_8(FOG, -1) == 0 {
        // Without fog the game's animations are shown as they are, but not with the mover's cursor, info panel and so on
        // on them (a unit walking with its range up): the next frame of the animation with those hidden.
        scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
        run(scratch, &[0])?;
        return Ok(());
    }
    let on_map = |s: &dyn tango_backend_mgba::Scratch| s.core().raw_read_32(MAIN_LOOP, -1) == MAP_LOOP;
    if phase(scratch.core()) == Phase::Page && scratch.memory()[0] == 0 {
        // The mover's full-screen CO page: never shown. On the scratch B closes it (a few dozen frames, and its fade),
        // so a seat that never had a picture still gets its map (the others keep their last one).
        for _ in 0..90 {
            if scratch.core().raw_read_32(MAIN_LOOP, -1) == MAP_LOOP {
                break;
            }
            run(scratch, &[KEY_B, 0])?;
        }
        run(scratch, &[0; 30])?;
    }
    if scratch.memory()[0] == 0 && matches!(phase(scratch.core()), Phase::Busy | Phase::Moving) && scratch.core().raw_read_8(FOG, -1) != 0 {
        // A seat with no picture of its own yet (the battle has just begun) while the turn's banners run: they are the
        // mover's view of the map, which is not to be shown; on the scratch A skips them, up to a few seconds of them.
        for _ in 0..360 {
            if phase(scratch.core()) == Phase::Map && steady_regs(scratch.core()) {
                break;
            }
            run(scratch, &[KEY_A, 0])?;
        }
    }
    // A unit's own animation of the turn (walking, capturing, being built, an attack's result) in a fog match: made on
    // the scratch like the map, for the waiting army's own fog; the sprites out of its sight are hidden at the flush
    // (`hide_fogged_sprites`), so a walk is seen while the sprite is on cells the seat sees and never where it does not.
    let anim = scratch.core().raw_read_8(FOG, -1) != 0 && phase(scratch.core()) == Phase::Busy && scratch.memory()[0] != 0;
    scratch.core_mut().raw_write_8(CALL + 3, -1, anim as u8);
    if phase(scratch.core()) != Phase::Map && !anim {
        return Err("not the plain map");
    }
    let fog = scratch.core().raw_read_8(FOG, -1) != 0;
    let mover_cell = (scratch.core().raw_read_16(CURSOR, -1) as i32, scratch.core().raw_read_16(CURSOR + 2, -1) as i32);
    for _ in 0..4 {
        if anim || !ui_open(scratch.core()) {
            break;
        }
        run(scratch, &[KEY_B, KEY_B, 0])?;
    }
    if !on_map(scratch) {
        return Err("left the map loop");
    }
    if !anim && ui_open(scratch.core()) {
        // (a page or question B does not close: the seat keeps its last clean picture, never a half-closed one)
        return Err("the mover's UI would not close");
    }
    if !fog {
        // (the turn as played, but the mover's menus closed and no cursor, and the CO panel of the waiting seat's own
        // army: its face and its funds)
        if let Some(army) = viewer_army(scratch.core(), seat) {
            scratch.core_mut().raw_write_8(CURRENT_PLAYER, -1, army);
        }
        let last = scratch.memory()[3] & 3;
        let side = settle_panel(scratch.core_mut(), last);
        scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
        run(scratch, &[0, 0, 0])?;
        close_ui(scratch)?;
        scratch.memory()[0] = 1;
        scratch.memory()[3] = side;
        return Ok(());
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
    let pal_before = {
        let mut a = vec![0u8; 0x400];
        scratch.core().raw_read_range(0x0300_20C0, -1, &mut a);
        let mut b = vec![0u8; 0x400];
        scratch.core().raw_read_range(0x0500_0000, -1, &mut b);
        Some((a, b))
    };
    let (mut cx, mut cy) = (mem[1], mem[2]);
    // (bit 2 of the fourth word: the camera is where a followed cell of the mover's put it, not at the army's own place)
    let followed = mem[3] & 4 != 0;
    let mut side = mem[3] & 3;
    place(scratch, cx, cy, (cx + 7, cy + 4));
    side = settle_panel(scratch.core_mut(), side);
    scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
    refresh(scratch, 2)?;
    // ... and if the mover's cursor is on a cell it sees, the camera follows it there and the cursor shows.
    let (x, y) = mover_cell;
    let follow = x < w && y < h && seen(scratch.core(), x, y);
    if std::env::var_os("AW2_VIEW_DEBUG").is_some() {
        eprintln!("follow seat {seat}: mover cell ({x},{y}) map {w}x{h} seen {follow} plane byte {:02x} army {army}", scratch.core().raw_read_8(MAP + 0x234A + cell(scratch.core(), x.min(w - 1), y.min(h - 1)), -1));
    }
    // (the waiting window shows no cursor at all, neither its own nor the mover's: the camera only follows it)
    scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
    if follow {
        cx = if x < cx { x } else if x > cx + 14 { x - 14 } else { cx }.clamp(0, (w - 15).max(0));
        cy = if y < cy { y } else if y > cy + 9 { y - 9 } else { cy }.clamp(0, (h - 10).max(0));
        place(scratch, cx, cy, mover_cell);
        side = settle_panel(scratch.core_mut(), side);
        refresh(scratch, 2)?;
    } else if followed || !window_sees(scratch.core(), cx, cy, w, h) {
        // (the camera was left where a cell of the mover's was seen once, or nothing in its window is seen now: grey
        // fogged terrain and no units; back to the army's own HQ)
        let (ax, ay) = anchor(scratch.core(), army);
        cx = (ax - 7).clamp(0, (w - 15).max(0));
        cy = (ay - 4).clamp(0, (h - 10).max(0));
        place(scratch, cx, cy, (cx + 7, cy + 4));
        side = settle_panel(scratch.core_mut(), side);
        scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
        refresh(scratch, 2)?;
        scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
        run(scratch, &[0, 0])?;
    } else {
        run(scratch, &[0, 0])?;
    }
    if !anim {
        close_ui(scratch)?;
    }
    if std::env::var_os("AW2_PAL_DEBUG").is_some() {
        // the tile entries of the 2 x 2 tiles of cell (10,5) in every background, with the camera as it is now
        let c = scratch.core();
        let (sx, sy) = ((10 * 16 - cx * 16) as u32 / 8, (5 * 16 - cy * 16) as u32 / 8);
        for bg in 0..4u32 {
            let cnt = c.raw_read_16(0x0400_0008 + 2 * bg, -1) as u32;
            let base = 0x0600_0000 + ((cnt >> 8) & 31) * 0x800;
            let ents: Vec<String> = [(0, 0), (1, 0), (0, 1), (1, 1)].iter().map(|(dx, dy)| format!("{:04x}", c.raw_read_16(base + 2 * (((sy + dy) % 32) * 32 + (sx + dx) % 32), -1))).collect();
            eprintln!("tiles seat {seat} bg{bg} cnt {cnt:04x} at ({sx},{sy}): {}", ents.join(" "));
        }
    }
    if let Some((a0, b0)) = pal_before {
        restore_unit_palettes(scratch.core_mut(), &a0, &b0);
        run(scratch, &[0])?;
        let mut a = vec![0u8; 0x400];
        scratch.core().raw_read_range(0x0300_20C0, -1, &mut a);
        let mut b = vec![0u8; 0x400];
        scratch.core().raw_read_range(0x0500_0000, -1, &mut b);
        let banks = |x: &[u8], y: &[u8]| (0..32).filter(|k| x[k * 32..k * 32 + 32] != y[k * 32..k * 32 + 32]).collect::<Vec<_>>();
        if std::env::var_os("AW2_PAL_DEBUG").is_some() { eprintln!("pal seat {seat}: buffer banks changed {:?}, pal ram banks changed {:?} (0-15 BG, 16-31 OBJ)", banks(&a0, &a), banks(&b0, &b)); }
    }
    if seat < 5 {
        let core = scratch.core();
        let seen_cells: Vec<bool> = (0..h).flat_map(|y| (0..w).map(move |x| (x, y))).map(|(x, y)| seen(core, x, y)).collect();
        VISION.lock().unwrap()[seat] = Some((w, h, seen_cells));
    }
    scratch.core_mut().raw_write_8(CALL + 3, -1, 0);
    *scratch.memory() = [1, cx, cy, side | if follow { 4 } else { 0 }];
    Ok(())
}

/// The scratch console shows the plain map: nothing of the mover's UI running and the registers of the plain map. A
/// button the mover pressed on the very tick the snapshot was taken is already latched in the game's state, and the
/// scratch's own ticks then open the menu or page it was meant to: B closes it again, up to four times, and a picture
/// that is still not the plain map is no picture (the caller keeps the last one).
fn close_ui(scratch: Scratch) -> Result<(), &'static str> {
    for _ in 0..4 {
        if phase(scratch.core()) == Phase::Map && !ui_open(scratch.core()) && steady_regs(scratch.core()) {
            return Ok(());
        }
        run(scratch, &[KEY_B, KEY_B, 0, 0, 0])?;
    }
    if phase(scratch.core()) == Phase::Map && !ui_open(scratch.core()) && steady_regs(scratch.core()) {
        return Ok(());
    }
    Err("the scratch picture is not the plain map")
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
        // (the cursor's four corner sprites are tiles 0x365 and 0x369 of palette 1, wherever they are: the game draws them
        // at its own scroll, which a scratch camera that is still sliding to the mover's cell does not match)
        let corner = a2 >> 12 == 1 && matches!(a2 & 0x3FF, 0x365 | 0x369);
        let cursor = corner || (a2 >> 12 == 1 && small && (sx - 12..sx + 24).contains(&x) && (sy - 12..sy + 24).contains(&y));
        // The info panel of the cell under it (terrain, unit), in the lower corners: sprites in the units' and
        // cursor's palettes, not the buildings' (8 to 13).
        let panel = y >= 88 && (a2 >> 12 < 8 || (a0 >> 10) & 3 == 1) && (x < 72 || x >= 168);
        if a0 & 0x300 != 0x200 && (cursor || panel) {
            core.raw_write_16(at, -1, (a0 & !0x300) | 0x200);
        }
        at += 8;
    }
}

/// A sprite's size in pixels (shape in attribute 0, size in attribute 1).
fn sprite_size(a0: u16, a1: u16) -> (i32, i32) {
    match (a0 >> 14, a1 >> 14) {
        (0, s) => (8 << s, 8 << s),
        (1, 0) => (16, 8),
        (1, 1) => (32, 8),
        (1, 2) => (32, 16),
        (1, _) => (64, 32),
        (2, 0) => (8, 16),
        (2, 1) => (8, 32),
        (2, 2) => (16, 32),
        (2, _) => (32, 64),
        _ => (8, 8),
    }
}

/// Hides every sprite whose middle is on a map cell the viewer does not see (a unit walking, fighting or being built
/// out of its sight), apart from the army's CO panel in its corner. The plane is the viewer's own (the scratch console
/// has been refreshed for the waiting army).
fn hide_fogged_sprites(core: &mut Core) {
    let start = core.raw_read_32(SPRITE_LIST, -1);
    let end = core.raw_read_32(NEXT_SPRITE, -1);
    if !(0x0300_0000..0x0300_8000).contains(&start) || end < start || end - start > 128 * 8 {
        return;
    }
    let (w, h) = size(core);
    if w <= 0 || h <= 0 || w > 64 || h > 64 {
        return;
    }
    let scroll_x = core.raw_read_16(MAP + 4, -1) as i16 as i32;
    let scroll_y = core.raw_read_16(MAP + 6, -1) as i16 as i32;
    let panel_x = if core.raw_read_8(PANEL_STATE, -1) == 1 { 170 } else { 0 };
    let mut at = start;
    while at + 8 <= end {
        let (a0, a1) = (core.raw_read_16(at, -1), core.raw_read_16(at + 2, -1));
        if a0 & 0x300 != 0x200 {
            let x = ((a1 & 0x1FF) as i32) << 23 >> 23;
            let y = (a0 & 0xFF) as i32;
            let (sw, sh) = sprite_size(a0, a1);
            // (the CO panel: a corner, the top 44 pixels)
            let in_panel = y + sh <= 48 && x >= panel_x - 4 && x + sw <= panel_x + 80;
            if !in_panel {
                let (mx, my) = (x + sw / 2 + scroll_x, y + sh / 2 + scroll_y);
                let (cx, cy) = (mx.div_euclid(16), my.div_euclid(16));
                let sees = cx >= 0 && cy >= 0 && cx < w && cy < h && seen(core, cx, cy);
                if !sees && (0..240).contains(&(x + sw / 2)) && (0..160).contains(&(y + sh / 2)) {
                    core.raw_write_16(at, -1, (a0 & !0x300) | 0x200);
                }
            }
        }
        at += 8;
    }
}

/// At the sprite flush: hides the cursor if asked, and starts the asked call.
pub fn at_flush(core: &mut Core) {
    if core.raw_read_8(CALL + 3, -1) == 1 {
        hide_fogged_sprites(core);
    }
    if core.raw_read_8(CALL + 2, -1) == 1 {
        hide_cursor(core);
        // The info panel's backing is a window with the game's darkening (BLDCNT mode 3): it goes with the panel
        // (as the game itself does when the panel closes), or an empty dark box stays in a lower corner.
        if (core.raw_read_16(0x0300_30E0, -1) >> 6) & 3 == 3 {
            for a in [0x0300_30E0, 0x0300_2020, 0x0300_2B28, 0x0300_1FFC] {
                core.raw_write_16(a, -1, 0);
            }
        }
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
    let first = step(0).map_or(CALLS[0].0, |(f, r0, r1)| {
        for (r, v) in [(0, r0), (1, r1)] {
            if let Some(v) = v {
                cpu.set_gpr(r, v);
            }
        }
        f
    });
    cpu.set_thumb_pc(first);
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
    if let Some((f, r0, r1)) = step(next) {
        core.raw_write_8(CALL + 1, -1, next as u8 + 1);
        let army = core.raw_read_8(CURRENT_PLAYER, -1) as i32;
        let cpu = core.gba_mut().cpu_mut();
        if let Some(v) = r0 {
            cpu.set_gpr(0, if v == ARMY { army } else { v });
        }
        if let Some(v) = r1 {
            cpu.set_gpr(1, v);
        }
        cpu.set_gpr(14, (RETURN | 1) as i32);
        cpu.set_thumb_pc(f);
        return;
    }
    PROGRAM.lock().unwrap().clear();
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
