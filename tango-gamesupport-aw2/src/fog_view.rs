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
/// The camera pin: while byte `CALL + 0x40` is 1 the camera registers (pixels) at `CALL + 0x42` and `+ 0x44` are written at every flush, so a scroll the
/// console had begun does not go on in the scratch picture.
const PIN: u32 = CALL + 0x40;
/// While the window's camera is still sliding to a walking unit: byte `PIN + 6` is 1, and `PIN + 8` / `PIN + 10` the cell (as 16 bit)
/// the unit is made to be at for the game (the middle of the window), so its own scroll after the unit does not
/// begin; the sprites on that cell are hidden.
const FAKE: u32 = PIN + 6;

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

/// The cursor parked at the middle of the screen, so the CO panel's side (which the game chooses from where the cursor
/// is) is the same every frame: a waiting window has no cursor of its own and the mover's must not move the panel.
fn park_cursor(core: &mut Core) {
    let (cx, cy) = ((core.raw_read_16(MAP + 4, -1) as i16 as i32) / 16 + 7, (core.raw_read_16(MAP + 6, -1) as i16 as i32) / 16 + 4);
    core.raw_write_16(CURSOR, -1, cx as u16);
    core.raw_write_16(CURSOR + 2, -1, cy as u16);
    core.raw_write_16(CURSOR_PX, -1, (cx * 16) as u16);
    core.raw_write_16(CURSOR_PX + 2, -1, (cy * 16) as u16);
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

/// Pixels a waiting window's camera slides per view (the game's own scroll is four a tick, eight over a long way; a view is
/// every second tick: eight, or sixteen when the way is more than sixteen pixels).
const CAMERA_STEP: i32 = 8;

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

const UNITS_PTR: u32 = 0x0849_9594;
const SELECTED_UNIT: u32 = 0x0300_40D8;
const UNIT_PLANES: [u32; 2] = [0x12, 0x51A];

/// The selected unit's index, if it is a live record.
fn selected_unit(core: &Core) -> Option<u32> {
    let (ptr, base) = (core.raw_read_32(SELECTED_UNIT, -1), core.raw_read_32(UNITS_PTR, -1));
    if ptr < base || (ptr - base) % 12 != 0 {
        return None;
    }
    let id = (ptr - base) / 12;
    (id != 0 && id < 512 && core.raw_read_8(ptr, -1) != 0).then_some(id)
}

/// Puts unit `id` on cell `to` (when empty) in the scratch console: its record and both unit planes.
fn put_unit_at(core: &mut Core, id: u32, to: (i32, i32)) -> bool {
    let (w, h) = size(core);
    let rec = core.raw_read_32(UNITS_PTR, -1) + 12 * id;
    let from = (core.raw_read_8(rec + 2, -1) as i32, core.raw_read_8(rec + 3, -1) as i32);
    if std::env::var_os("AW2_CAM_LOG").is_some() {
        let p = |c: (i32, i32), plane: u32| core.raw_read_8(MAP + plane + core.raw_read_16(MAP + 0x417A + 2 * c.1 as u32, -1) as u32 + c.0 as u32, -1);
        eprintln!("put unit {id}: record at {from:?} flags {:02x}, planes at from {} {} at to {} {}", core.raw_read_8(rec + 1, -1), p(from, 0x12), p(from, 0x51A), p(to, 0x12), p(to, 0x51A));
    }
    if from == to || to.0 < 0 || to.1 < 0 || to.0 >= w || to.1 >= h {
        return false;
    }
    let at = |core: &Core, c: (i32, i32), plane: u32| core.raw_read_8(MAP + plane + core.raw_read_16(MAP + 0x417A + 2 * c.1 as u32, -1) as u32 + c.0 as u32, -1);
    if at(core, to, UNIT_PLANES[0]) != 0 || at(core, from, UNIT_PLANES[0]) as u32 != id {
        return false;
    }
    for plane in UNIT_PLANES {
        let row = |c: (i32, i32)| MAP + plane + core.raw_read_16(MAP + 0x417A + 2 * c.1 as u32, -1) as u32 + c.0 as u32;
        let (f, t) = (row(from), row(to));
        core.raw_write_8(f, -1, 0);
        core.raw_write_8(t, -1, id as u8);
    }
    core.raw_write_8(rec + 2, -1, to.0 as u8);
    core.raw_write_8(rec + 3, -1, to.1 as u8);
    true
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
    // (a unit's own command menu, over the unit that has walked: the plain map under it is made by closing the menu)
    if running.contains(&WALK_PROC) {
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
    if std::env::var_os("AW2_PROC_LOG").is_some() {
        static LAST: std::sync::Mutex<(Vec<u32>, bool)> = std::sync::Mutex::new((Vec::new(), false));
        let now = (running.clone(), moving(core));
        let mut last = LAST.lock().unwrap();
        if *last != now {
            eprintln!("procs {:x?} moving {} main loop {:08x} menu {}", now.0, now.1, core.raw_read_32(MAIN_LOOP, -1), core.raw_read_8(MAP_MENU_STATE, -1));
            *last = now;
        }
    }
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
    // A unit picked up and walking to the cell the mover chose (its proc alone: the range and the arrow are gone, the
    // command menu is not up yet): the walk is shown to every window as the console plays it, at the same speed.
    if running.as_slice() == [WALK_PROC] && !crate::pvp::turn_ended(core) {
        return Phase::Busy;
    }
    if dialog_for(core, &running) || capturing(&running) {
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

/// The proc of a unit picked up and walking (`0x080363D1`, among [`UI_PROCS`]: it goes on under the command menu).
const WALK_PROC: u32 = 0x0803_63D1;

/// The walking unit's place on the map while its proc runs, in pixels (the proc's own fields, found by its function).
fn walker_pixels(core: &Core) -> Option<(i32, i32)> {
    const AREAS: [(u32, u32); 2] = [(0x0300_0C00, 0x1300), (0x0200_C000, 0x2000)];
    let mut buf = vec![0u8; 0x2000];
    for (base, len) in AREAS {
        core.raw_read_range(base, -1, &mut buf[..len as usize]);
        for i in (0..len as usize - 12).step_by(4) {
            let word = |o: usize| u32::from_le_bytes(buf[o..o + 4].try_into().unwrap());
            if word(i + 8) == WALK_PROC && (0x0840_0000..0x0870_0000).contains(&word(i)) {
                let at = base + i as u32;
                let (x, y) = (core.raw_read_16(at + 0x3E, -1) as i32, core.raw_read_16(at + 0x40, -1) as i32);
                return ((0..2048).contains(&x) && (0..2048).contains(&y)).then_some((x, y));
            }
        }
    }
    None
}

fn set_walker_pixels(core: &mut Core, (x, y): (i32, i32)) {
    const AREAS: [(u32, u32); 2] = [(0x0300_0C00, 0x1300), (0x0200_C000, 0x2000)];
    let mut buf = vec![0u8; 0x2000];
    for (base, len) in AREAS {
        core.raw_read_range(base, -1, &mut buf[..len as usize]);
        for i in (0..len as usize - 12).step_by(4) {
            let word = |o: usize| u32::from_le_bytes(buf[o..o + 4].try_into().unwrap());
            if word(i + 8) == WALK_PROC && (0x0840_0000..0x0870_0000).contains(&word(i)) {
                let at = base + i as u32;
                core.raw_write_16(at + 0x3E, -1, x as u16);
                core.raw_write_16(at + 0x40, -1, y as u16);
                return;
            }
        }
    }
}

/// The dialogue box of the game's messages over the map ("The Green Earth Army has lost!"): `0x08013FF1` with the text box's
/// own proc `0x08014401` (the Save question has `0x080195F9` there): every window shows it, over its own map.
const DIALOG_PROC: u32 = 0x0801_3FF1;
/// A property being captured: the capture card (`0x08040C89`, `0x08040AFD`): shown to the seats that see the cell.
const CAPTURE_PROCS: [u32; 2] = [0x0804_0C89, 0x0804_0AFD];

/// The game's narration over the map ("The Green Earth Army has lost!") as opposed to the mover's own questions (Yield, Save, End
/// turn, CO Power: they come from a map-menu item, which is still the chosen one while they are up): only narration reaches every window.
fn dialog_for(core: &Core, running: &[u32]) -> bool {
    running.contains(&DIALOG_PROC) && !running.contains(&0x0801_95F9) && !matches!(crate::pvp::chosen_item(core), Some(0..=5))
}

fn capturing(running: &[u32]) -> bool {
    running.iter().any(|f| CAPTURE_PROCS.contains(f)) && running.iter().all(|f| UI_PROCS.contains(f) || CAPTURE_PROCS.contains(f))
}

/// A unit picked up is walking (see [`WALK_PROC`]).
pub fn walking(core: &Core) -> bool {
    procs(core).as_slice() == [WALK_PROC]
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

/// The walking unit's place after the last scratch tick and whether it did not move on it (the walk is over, the command
/// menu comes next: that tick's picture may already have it).
static WALK_TRACK: std::sync::Mutex<(Option<(i32, i32)>, bool)> = std::sync::Mutex::new((None, false));

fn run(scratch: Scratch, keys: &[u32]) -> Result<(), &'static str> {
    for &k in keys {
        if !scratch.tick(k) {
            return Err("tick failed");
        }
        let now = walker_pixels(scratch.core());
        let mut t = WALK_TRACK.lock().unwrap();
        t.1 = now.is_some() && t.0 == now;
        t.0 = now;
    }
    Ok(())
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
    // (only the CO panel's calls: its colours, face and palettes for the army)
    let n = if PANEL_ONLY.load(std::sync::atomic::Ordering::Relaxed) { if n < 3 { n + 1 } else { return None } } else { n };
    CALLS.get(n).map(|&(f, army_arg)| (f, army_arg.then_some(ARMY), None))
}

/// The next call list is only the CO panel's (the viewer's own header, without the fog refresh): Fog off.
static PANEL_ONLY: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

fn panel_call(scratch: Scratch) -> Result<(), &'static str> {
    PANEL_ONLY.store(true, std::sync::atomic::Ordering::Relaxed);
    let r = refresh(scratch, 0);
    PANEL_ONLY.store(false, std::sync::atomic::Ordering::Relaxed);
    r
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

/// What the picture of the view just made is, for [`hud_patch`] (taken by it once): 1 a walk (the game hides its CO panel while
/// a unit walks, and the window keeps the seat's own), 2 a plain map.
static WALK_VIEW: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);
/// Each seat's last plain-map CO panel: the side it was on and its pixels (RGBA, [`HUD_W`] x [`HUD_H`]).
static HUD: std::sync::Mutex<[Option<(bool, Vec<u8>)>; 5]> = std::sync::Mutex::new([None, None, None, None, None]);
const HUD_W: usize = 76;
const HUD_H: usize = 26;

fn hud_x(right: bool) -> usize {
    if right { 240 - HUD_W } else { 0 }
}

/// Display side: after the window's picture is made, the seat's own CO panel is put back over a walk's frames (the game
/// does not draw it while a unit walks, and the panel is the seat's own from the last plain-map picture), and on a plain
/// map its picture is kept.
pub fn hud_patch(core: &Core, seat: usize, rgba: &mut [u8]) {
    if seat >= 5 || rgba.len() != 240 * 160 * 4 {
        return;
    }
    let right = core.raw_read_8(PANEL_STATE, -1) == 1;
    let kind = WALK_VIEW.swap(0, std::sync::atomic::Ordering::Relaxed);
    if kind == 1 {
        if let Some((side, px)) = HUD.lock().unwrap()[seat].as_ref() {
            let x0 = hud_x(*side);
            for y in 0..HUD_H {
                let (d, s) = (4 * (240 * y + x0), 4 * HUD_W * y);
                rgba[d..d + 4 * HUD_W].copy_from_slice(&px[s..s + 4 * HUD_W]);
            }
        }
    } else if kind == 2 && phase(core) == Phase::Map && steady_regs(core) && !ui_open(core) {
        let x0 = hud_x(right);
        let mut px = Vec::with_capacity(4 * HUD_W * HUD_H);
        for y in 0..HUD_H {
            let d = 4 * (240 * y + x0);
            px.extend_from_slice(&rgba[d..d + 4 * HUD_W]);
        }
        HUD.lock().unwrap()[seat] = Some((right, px));
    }
}

fn view_inner(scratch: Scratch, seat: usize) -> Result<(), &'static str> {
    WALK_VIEW.store(0, std::sync::atomic::Ordering::Relaxed);
    *WALK_TRACK.lock().unwrap() = (None, false);
    let walk_start = walking(scratch.core());
    WALK_VIEW.store(if walk_start { 1 } else { 2 }, std::sync::atomic::Ordering::Relaxed);
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
        let pal_before = {
            let mut a = vec![0u8; 0x400];
            scratch.core().raw_read_range(0x0300_20C0, -1, &mut a);
            let mut b = vec![0u8; 0x400];
            scratch.core().raw_read_range(0x0500_0000, -1, &mut b);
            (a, b)
        };
        if let Some(army) = viewer_army(scratch.core(), seat) {
            // (the header is the seat's own, as on the plain map: the CO panel called for its army, the units' palettes kept)
            let mover = scratch.core().raw_read_8(CURRENT_PLAYER, -1);
            scratch.core_mut().raw_write_8(CURRENT_PLAYER, -1, army);
            scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
            park_cursor(scratch.core_mut());
            let last = scratch.memory()[3] & 3;
            let side = settle_panel(scratch.core_mut(), last);
            scratch.memory()[3] = (scratch.memory()[3] & !3) | side;
            panel_call(scratch)?;
            restore_unit_palettes(scratch.core_mut(), &pal_before.0, &pal_before.1);
            scratch.core_mut().raw_write_8(CURRENT_PLAYER, -1, mover);
        }
        scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
        run(scratch, &[0])?;
        if walk_start && WALK_TRACK.lock().unwrap().1 {
            // (the unit did not move on the last tick: the walk is over and the command menu may be in this picture)
            return Err("the walk has just stopped");
        }
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
    let running_now = procs(scratch.core());
    let (dialog_up, capture_up) = (dialog_for(scratch.core(), &running_now), capturing(&running_now));
    if std::env::var_os("AW2_VIEW_DEBUG").is_some() && (dialog_up || capture_up) {
        eprintln!("view seat {seat}: dialog {dialog_up} capture {capture_up} anim {anim} phase {:?}", phase(scratch.core()));
    }
    // (a message box over the map is no fogged sprite: its portrait is not hidden)
    scratch.core_mut().raw_write_8(CALL + 3, -1, (anim && !dialog_up) as u8);
    if phase(scratch.core()) != Phase::Map && !anim {
        return Err("not the plain map");
    }
    let fog = scratch.core().raw_read_8(FOG, -1) != 0;
    let mover_cell = (scratch.core().raw_read_16(CURSOR, -1) as i32, scratch.core().raw_read_16(CURSOR + 2, -1) as i32);
    // (a unit that has walked to the cell the mover chose and waits for its command: B closes the menu and puts it back
    // where it was, so it is put on its cell again after)
    let sel_before = selected_unit(scratch.core());
    let walked = {
        // (the selection's own proc is not up: the destination is chosen and the unit has walked, not the cursor browsing)
        let running = procs(scratch.core());
        if running.contains(&WALK_PROC) && !running.contains(&0x0802_28D9) { sel_before } else { None }
    };
    // (a menu that has only just opened takes no button for a dozen frames: up to eighty ticks are tried)
    for _ in 0..16 {
        if anim || !ui_open(scratch.core()) {
            break;
        }
        run(scratch, &[KEY_B, 0, KEY_B, 0, 0])?;
        if std::env::var_os("AW2_CAM_LOG").is_some() {
            eprintln!("  after B: procs {:x?} menu {} main loop {:08x}", procs(scratch.core()), scratch.core().raw_read_8(MAP_MENU_STATE, -1), scratch.core().raw_read_32(MAIN_LOOP, -1));
        }
    }
    if std::env::var_os("AW2_CAM_LOG").is_some() {
        let c = scratch.core();
        let ptr = c.raw_read_32(SELECTED_UNIT, -1);
        eprintln!(
            "walked {walked:?} selected ptr {ptr:08x} rec xy ({},{}) mover cell {mover_cell:?} cursor px ({},{}) cam ({},{}) ",
            c.raw_read_8(ptr + 2, -1),
            c.raw_read_8(ptr + 3, -1),
            c.raw_read_16(CURSOR_PX, -1),
            c.raw_read_16(CURSOR_PX + 2, -1),
            c.raw_read_16(MAP + 4, -1),
            c.raw_read_16(MAP + 6, -1)
        );
    }
    let relocated = match walked {
        Some(id) => put_unit_at(scratch.core_mut(), id, mover_cell),
        None => false,
    };
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
        park_cursor(scratch.core_mut());
        let side = settle_panel(scratch.core_mut(), last);
        // (the header is the seat's own: its CO's face and colours, drawn by the game's panel routines for its army)
        let pal_before = {
            let mut a = vec![0u8; 0x400];
            scratch.core().raw_read_range(0x0300_20C0, -1, &mut a);
            let mut b = vec![0u8; 0x400];
            scratch.core().raw_read_range(0x0500_0000, -1, &mut b);
            (a, b)
        };
        scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
        if relocated {
            // (a unit put on its cell: the game's refresh draws the units again, with the header)
            refresh(scratch, 2)?;
        } else {
            panel_call(scratch)?;
        }
        scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
        // (the panel's routines load the army's unit palettes too: the mover's units stay in their own colours)
        restore_unit_palettes(scratch.core_mut(), &pal_before.0, &pal_before.1);
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
    // The window's camera, in pixels, and the cell it is heading for (kept in the link: word 1 and 2 the pixels, word 3's
    // bits 0..1 the CO panel's side, 8..15 and 16..23 the target cell).
    if mem[0] == 0 {
        let (ax, ay) = anchor(scratch.core(), army);
        let (tx, ty) = ((ax - 7).clamp(0, (w - 15).max(0)), (ay - 4).clamp(0, (h - 10).max(0)));
        mem = [1, tx * 16, ty * 16, (tx << 8) | (ty << 16)];
    }
    // The camera and the cursor where the window last had them, the game's refresh for the waiting army...
    let place = |scratch: Scratch, px: i32, py: i32, cursor: (i32, i32)| {
        let core = scratch.core_mut();
        // (the pixels, their copy, the camera's cell and the remainder of a scroll the console had begun: none)
        for (at, v) in [(4u32, px), (6, py), (8, px), (0xA, py), (0xC, (px + 8) / 16), (0xE, (py + 8) / 16), (0x10, 0), (0x12, 0)] {
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
    let (mut px, mut py) = (mem[1], mem[2]);
    scratch.core_mut().raw_write_8(PIN, -1, 1);
    scratch.core_mut().raw_write_16(PIN + 2, -1, px as u16);
    scratch.core_mut().raw_write_16(PIN + 4, -1, py as u16);
    let (mut tx, mut ty) = ((mem[3] >> 8) & 0xFF, (mem[3] >> 16) & 0xFF);
    let mut side = mem[3] & 3;
    place(scratch, px, py, (px / 16 + 7, py / 16 + 4));
    side = settle_panel(scratch.core_mut(), side);
    scratch.core_mut().raw_write_8(CALL + 2, -1, 0);
    refresh(scratch, 2)?;
    // ... and the camera's target. The game scrolls its camera after the cursor in steps of a cell, four pixels a frame
    // (the same on every window; traced from the console's own camera): a cell the window sees that is outside the
    // camera's view moves the target the least that brings it in, and the camera slides there. Nothing else moves the
    // target: when the mover goes out of sight the camera stays where the last action was (never back to the HQ,
    // never between two places), apart from a window that sees nothing at all (the HQ).
    // (the cell the action is at: the walking unit's, else the cursor's)
    let (x, y) = match (anim || walked.is_some()).then(|| walker_pixels(scratch.core())).flatten() {
        Some((wx, wy)) => ((wx + 8).div_euclid(16), (wy + 8).div_euclid(16)),
        None => mover_cell,
    };
    // (only an action moves it: the walk and what follows it, never the cursor browsing)
    let follow = (anim || walked.is_some()) && x < w && y < h && seen(scratch.core(), x, y);
    if std::env::var_os("AW2_VIEW_DEBUG").is_some() {
        eprintln!("follow seat {seat}: mover cell ({x},{y}) map {w}x{h} seen {follow} plane byte {:02x} army {army}", scratch.core().raw_read_8(MAP + 0x234A + cell(scratch.core(), x.min(w - 1), y.min(h - 1)), -1));
    }
    let mut reason = "none";
    if follow {
        reason = "follow";
        // (the game's own camera scrolls after a unit that comes within a few cells of the window's edge, which on the
        // scratch console would carry the picture past the window's own camera: the target keeps the unit that far in)
        const MARGIN: i32 = 3;
        tx = if x < tx + MARGIN { x - MARGIN } else if x > tx + 14 - MARGIN { x - 14 + MARGIN } else { tx }.clamp(0, (w - 15).max(0));
        ty = if y < ty + MARGIN { y - MARGIN } else if y > ty + 9 - MARGIN { y - 9 + MARGIN } else { ty }.clamp(0, (h - 10).max(0));
    } else if !window_sees(scratch.core(), (px + 8) / 16, (py + 8) / 16, w, h) && (tx * 16, ty * 16) == (px, py) {
        // (nothing in the window is seen and it is at rest: grey fogged terrain and no units; the army's own HQ)
        reason = "hq";
        let (ax, ay) = anchor(scratch.core(), army);
        tx = (ax - 7).clamp(0, (w - 15).max(0));
        ty = (ay - 4).clamp(0, (h - 10).max(0));
    }
    // (the slide: eight pixels a view, sixteen over a long way)
    let step = |from: i32, to: i32| {
        let by = if (to - from).abs() > 2 * CAMERA_STEP { 2 * CAMERA_STEP } else { CAMERA_STEP };
        if (to - from).abs() <= by { to } else { from + by * (to - from).signum() }
    };
    let (nx, ny) = (step(px, tx * 16), step(py, ty * 16));
    if std::env::var_os("AW2_CAM_LOG").is_some() {
        eprintln!("cam seat {seat} phase {:?} cam ({px},{py}) -> ({nx},{ny}) target ({tx},{ty}) mover ({x},{y}) follow {follow} reason {reason}", phase(scratch.core()));
    }
    scratch.core_mut().raw_write_8(CALL + 2, -1, 1);
    // (a camera that has still to get to the unit: the game is told the unit is in the middle of the window, so it does
    // not scroll after it, and that unit is not drawn until the camera is there: the walk is seen from there on)
    let sliding = walk_start && follow && (px, py) != (tx * 16, ty * 16);
    scratch.core_mut().raw_write_8(FAKE, -1, sliding as u8);
    scratch.core_mut().raw_write_16(FAKE + 2, -1, ((nx + 112) / 16) as u16);
    scratch.core_mut().raw_write_16(FAKE + 4, -1, ((ny + 72) / 16) as u16);
    if capture_up && !seen(scratch.core(), mover_cell.0.clamp(0, w - 1), mover_cell.1.clamp(0, h - 1)) {
        // (a capture where the seat sees nothing: no card, no picture)
        return Err("the capture is out of sight");
    }
    if walk_start && !follow {
        // (a unit walking where the seat sees nothing: the window keeps its picture; the game's own camera follows the unit
        // on the scratch console, so no picture of it is made)
        return Err("the walking unit is out of sight");
    }
    if (nx, ny) != (px, py) || follow {
        (px, py) = (nx, ny);
        scratch.core_mut().raw_write_16(PIN + 2, -1, px as u16);
        scratch.core_mut().raw_write_16(PIN + 4, -1, py as u16);
        place(scratch, px, py, (px / 16 + 7, py / 16 + 4));
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
        let (sx, sy) = ((10 * 16 - px) as u32 / 8, (5 * 16 - py) as u32 / 8);
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
    scratch.core_mut().raw_write_8(PIN, -1, 0);
    scratch.core_mut().raw_write_8(FAKE, -1, 0);
    if std::env::var_os("AW2_CAM_LOG").is_some() {
        let c = scratch.core();
        eprintln!(
            "camend seat {seat} mine ({px},{py}) game map+4/6 ({},{})",
            c.raw_read_16(MAP + 4, -1) as i16,
            c.raw_read_16(MAP + 6, -1) as i16
        );
    }
    // (the camera is kept whatever picture comes of this view: a view that makes none must not leave the window's camera
    // where it was, or the next one starts from there and the picture goes back and forth)
    *scratch.memory() = [1, px, py, side | (tx << 8) | (ty << 16)];
    if walk_start && anim && !sliding && WALK_TRACK.lock().unwrap().1 {
        return Err("the walk has just stopped");
    }
    *scratch.memory() = [1, px, py, side | (tx << 8) | (ty << 16)];
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
                let fake = core.raw_read_8(FAKE, -1) == 1 && (cx, cy) == (core.raw_read_16(FAKE + 2, -1) as i32, core.raw_read_16(FAKE + 4, -1) as i32);
                let sees = !fake && cx >= 0 && cy >= 0 && cx < w && cy < h && seen(core, cx, cy);
                if !sees && (0..240).contains(&(x + sw / 2)) && (0..160).contains(&(y + sh / 2)) {
                    core.raw_write_16(at, -1, (a0 & !0x300) | 0x200);
                }
            }
        }
        at += 8;
    }
}

/// The camera pinned (see [`PIN`]): on the scratch console, before every tick and at every flush.
pub fn pin_camera(core: &mut Core) {
    if core.raw_read_8(FAKE, -1) == 1 {
        let (cx, cy) = (core.raw_read_16(FAKE + 2, -1) as i32, core.raw_read_16(FAKE + 4, -1) as i32);
        set_walker_pixels(core, (cx * 16, cy * 16));
    }
    if core.raw_read_8(PIN, -1) == 1 {
        let (px, py) = (core.raw_read_16(PIN + 2, -1), core.raw_read_16(PIN + 4, -1));
        for (at, v) in [(4u32, px), (6, py), (8, px), (0xA, py)] {
            core.raw_write_16(MAP + at, -1, v);
        }
    }
}

/// At the sprite flush: hides the cursor if asked, and starts the asked call.
pub fn at_flush(core: &mut Core) {
    pin_camera(core);
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
