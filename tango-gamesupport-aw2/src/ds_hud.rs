//! Dual Strike's battle HUD on AW2's map: the CO panel and the terrain /
//! unit information panel, drawn by the GBA's own sprite hardware from
//! Dual Strike's art ([`crate::ds_pack`]).
//!
//! Only with "Dual Strike map graphics" on ([`crate::wasteland::ds_graphics`]:
//! the pack, offline), so with the setting off nothing here reads or writes
//! anything. It works on the sprite list at the flush
//! ([`crate::branding::flush`]), as [`crate::tag_ui`] does: AW2 still draws
//! its panels (its game logic, flips and slides are untouched); this hides
//! the pieces that are Advance Wars 2's art and puts Dual Strike's in their
//! place.
//!
//! - **CO panel** (`DrawArmyCoPanel`, `0x080436DC`): Dual Strike's panel at
//!   the screen's top corner (the corner AW2 chose): for a pair its two
//!   rows (the active CO over its partner: a face, a power meter of small
//!   and big stars in four states, the army's colour for the plate) with the
//!   funds between ("G." and digits, 8x8 sprites); for a single CO its one
//!   row and the funds under it. The plate, stars, "G." and digits are Dual
//!   Strike's HUD sheet (overlay 0 `0x214F0`, 32 of its tiles); the plate's
//!   colours are Dual Strike's five army palettes (arm9 `0x0213FD2C`, 0x20
//!   an army); the faces are the Dual Strike COs' HUD faces
//!   ([`crate::ds_co_art`], arm9 menu mugs; AW2's own for Sturm, who has none).
//!   The sheet goes into the OBJ tiles AW2 keeps its own header and stars in
//!   (0..41), saved while ours are there and put back whenever no panel is
//!   drawn this way (the CO page's), with OBJ palette 7.
//! - **Terrain and unit panel** (`0x0802A8DC`): AW2's own pictures, names and
//!   icons (pixel for pixel Dual Strike's icons) moved into Dual Strike's
//!   layout, its numbers in Dual Strike's style (two digits with a leading
//!   zero for the defence stars, the capture points, the fuel and the ammo,
//!   the unit's hit points out of 100), the digits from Dual Strike's icon
//!   sheet (`icon/res_icon4_cg_E`), and the translucent backing (AW2's
//!   window and its darkening) moved to the panel's new rectangle.
//!   The sides follow AW2's: left, or right with the unit's column first.

use mgba::core::Core;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU32, Ordering};
use std::sync::{Mutex, OnceLock};

const OBJ_VRAM: u32 = 0x0601_0000;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
/// The game's window 0 shadows (IWRAM bytes its VBlank copy,
/// `0x080128D0`, stores into WIN0H / WIN0V: IO cannot be written from here).
const WIN_LEFT: u32 = 0x0300_2B40;
const WIN_RIGHT: u32 = 0x0300_2B4C;
const WIN_TOP: u32 = 0x0300_2EFC;
const WIN_BOTTOM: u32 = 0x0300_2B44;

/// The window shadows (left, right, top, bottom) as the game left them and as
/// we wrote them, while they are ours.
static WINDOW: Mutex<Option<([u8; 4], [u8; 4])>> = Mutex::new(None);

fn window_now(core: &Core) -> [u8; 4] {
    [WIN_LEFT, WIN_RIGHT, WIN_TOP, WIN_BOTTOM].map(|a| core.raw_read_8(a, -1))
}

fn window_set(core: &mut Core, w: [u8; 4]) {
    for (a, v) in [WIN_LEFT, WIN_RIGHT, WIN_TOP, WIN_BOTTOM].into_iter().zip(w) {
        core.raw_write_8(a, -1, v);
    }
}

/// Our rectangle for the backing; what the game had (it writes its window
/// only when it changes it, so the last of its values is kept, and put back
/// by [`window_release`] when no panel is drawn this way).
fn window_take(core: &mut Core, mine: [u8; 4]) {
    let now = window_now(core);
    let aw2 = match WINDOW.lock().ok().and_then(|w| *w) {
        Some((ours, aw2)) if now == ours => aw2,
        _ => now,
    };
    window_set(core, mine);
    if let Ok(mut w) = WINDOW.lock() {
        *w = Some((mine, aw2));
    }
}

/// The game's window back (once), if it is still ours.
fn window_release(core: &mut Core) {
    let state = WINDOW.lock().ok().and_then(|mut w| w.take());
    if let Some((ours, aw2)) = state {
        if window_now(core) == ours {
            window_set(core, aw2);
        }
    }
}

/// Whether the HUD is Dual Strike's now.
pub fn on(core: &Core) -> bool {
    crate::wasteland::ds_graphics(core)
}

// --- Art -----------------------------------------------------------------------------------------

/// Dual Strike's HUD sheet: overlay 0 at this offset is OBJ tile 16 of its
/// battle screen; tiles 16..48 are what the CO panel uses (the plate 16..24,
/// the small stars 24..28, the big stars 28..36, "G." 36..38, the digits 38..48).
const SHEET_AT: usize = 0x214F0;
const SHEET_TILES: usize = 32;
/// Our OBJ tile for Dual Strike's tile 16 (the header's first tile).
const T0: u16 = 0;
const T_PLATE_A: u16 = T0; // DS 16: a 32x8 piece
const T_PLATE_B: u16 = T0 + 4; // DS 20
const T_STAR_SMALL: u16 = T0 + 8; // DS 24..28
const T_STAR_BIG: u16 = T0 + 12; // DS 28, 30, 32, 34 (8x16 each)
const T_GOLD: u16 = T0 + 20; // DS 36: "G." (16x8)
const T_FUNDS_DIGIT: u16 = T0 + 22; // DS 38..48: 0..9
/// The terrain panel's digits (Dual Strike's icon sheet), after the sheet.
const T_DIGIT: u16 = 32;
const DIGIT_TILES: usize = 10;
const BORROWED_TILES: usize = SHEET_TILES;
const DAMAGE_FILE: &str = "bmap/02d";
const DAMAGE_TILES: usize = 36;
const DIGITS_FILE: &str = "icon/res_icon4_cg_E";
const DIGITS_AT: usize = 21184;
/// Dual Strike's army palettes for OBJ palette 7 (colour 1..5: Orange Star,
/// Blue Moon, Green Earth, Yellow Comet, Black Hole).
const ARMY_PALETTES: u32 = 0x0213_FD2C;
/// The 16 colours Dual Strike runs the stars' fill through (arm9 table: light
/// blue to purple to red to pink), one step every two frames.
const STAR_PULSE: u32 = 0x0213_FDEC;
static FRAME: AtomicU32 = AtomicU32::new(0);

struct Art {
    sheet: Vec<u8>,
    digits: Vec<u8>,
    palettes: [[u8; 32]; 5],
    /// Colours the meter's stars' fill (palette index 15) runs through.
    pulse: [u16; 16],
    /// The damage forecast box's 36 tiles (`bmap/02d`: ten digits of 8 x 16, then the 32 x 32 frame).
    damage: Vec<u8>,
}

static ART: OnceLock<Option<Art>> = OnceLock::new();

fn art() -> Option<&'static Art> {
    ART.get_or_init(|| {
        let pack = crate::ds_pack::pack()?;
        let sheet = pack.overlays.first()?.get(SHEET_AT..SHEET_AT + 32 * SHEET_TILES)?.to_vec();
        let digits = pack.file(DIGITS_FILE)?.get(DIGITS_AT..DIGITS_AT + 32 * DIGIT_TILES)?.to_vec();
        let mut palettes = [[0u8; 32]; 5];
        for (i, p) in palettes.iter_mut().enumerate() {
            p.copy_from_slice(pack.arm9_at(ARMY_PALETTES + 0x20 * i as u32, 32)?);
        }
        let mut pulse = [0u16; 16];
        for (i, c) in pulse.iter_mut().enumerate() {
            let b = pack.arm9_at(STAR_PULSE + 2 * i as u32, 2)?;
            *c = u16::from_le_bytes([b[0], b[1]]);
        }
        let damage = crate::ds_art::lz10(pack.file(DAMAGE_FILE)?)?.get(..32 * DAMAGE_TILES)?.to_vec();
        Some(Art { sheet, digits, palettes, pulse, damage })
    })
    .as_ref()
}

/// A CO's HUD face (8 tiles) and its palette: Dual Strike's own for every
/// CO that has a Dual Strike id; the game's (AW2's, tangoAW2's) otherwise.
fn face(core: &Core, co: u8) -> ([u8; 256], [u8; 32]) {
    static CACHE: OnceLock<Mutex<HashMap<u8, Option<([u8; 256], [u8; 32])>>>> = OnceLock::new();
    let cache = CACHE.get_or_init(Default::default);
    let ds = crate::co_roster::ds_co(co).and_then(|d| {
        let mut g = cache.lock().ok()?;
        g.entry(d)
            .or_insert_with(|| {
                let a = crate::ds_co_art::co_art(d)?;
                Some((a.hud.get(..256)?.try_into().ok()?, a.palette.get(..32)?.try_into().ok()?))
            })
            .clone()
    });
    ds.unwrap_or_else(|| (crate::tag_ui::hud_face(core, co), crate::tag_ui::co_palette(core, co)))
}

// --- Sprite list helpers -------------------------------------------------------------------------

#[derive(Clone, Copy)]
struct Spr {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    tile: u16,
    pal: u16,
    hflip: bool,
    vflip: bool,
    mode: u16,
}

impl Spr {
    fn new(x: i32, y: i32, w: i32, h: i32, tile: u16, pal: u16) -> Spr {
        Spr { x, y, w, h, tile, pal, hflip: false, vflip: false, mode: 0 }
    }
    fn flip(mut self, h: bool, v: bool) -> Spr {
        self.hflip = h;
        self.vflip = v;
        self
    }
    fn mode(mut self, m: u16) -> Spr {
        self.mode = m;
        self
    }
    fn attrs(&self) -> [u16; 3] {
        let (shape, size) = match (self.w, self.h) {
            (8, 8) => (0, 0),
            (16, 16) => (0, 1),
            (32, 32) => (0, 2),
            (16, 8) => (1, 0),
            (32, 8) => (1, 1),
            (32, 16) => (1, 2),
            (8, 16) => (2, 0),
            (8, 32) => (2, 1),
            (16, 32) => (2, 2),
            _ => (0, 0),
        };
        [
            (self.y as u16 & 0xFF) | (self.mode << 10) | (shape << 14),
            (self.x as u16 & 0x1FF) | ((self.hflip as u16) << 12) | ((self.vflip as u16) << 13) | (size << 14),
            self.tile | (self.pal << 12),
        ]
    }
}

/// A sprite of the frame's list as the game left it.
#[derive(Clone, Copy)]
struct Entry {
    at: u32,
    a0: u16,
    a1: u16,
    a2: u16,
}

impl Entry {
    fn tile(&self) -> u16 {
        self.a2 & 0x3FF
    }
    fn pal(&self) -> u16 {
        self.a2 >> 12
    }
    fn mode(&self) -> u16 {
        (self.a0 >> 10) & 3
    }
    fn hidden(&self) -> bool {
        self.a0 & 0x300 == 0x200
    }
    fn dims(&self) -> (i32, i32) {
        const SZ: [[(i32, i32); 4]; 3] = [
            [(8, 8), (16, 16), (32, 32), (64, 64)],
            [(16, 8), (32, 8), (32, 16), (64, 32)],
            [(8, 16), (8, 32), (16, 32), (32, 64)],
        ];
        let shape = (self.a0 >> 14) as usize;
        if shape > 2 {
            return (8, 8);
        }
        SZ[shape][(self.a1 >> 14) as usize]
    }
    fn x(&self) -> i32 {
        let x = (self.a1 & 0x1FF) as i32;
        if x >= 256 {
            x - 512
        } else {
            x
        }
    }
    fn y(&self) -> i32 {
        let y = (self.a0 & 0xFF) as i32;
        if y >= 160 {
            y - 256
        } else {
            y
        }
    }
}

fn entries(core: &Core, start: u32, at: u32) -> Vec<Entry> {
    let mut v = Vec::new();
    let mut e = start;
    while e + 8 <= at {
        v.push(Entry {
            at: e,
            a0: core.raw_read_16(e, -1),
            a1: core.raw_read_16(e + 2, -1),
            a2: core.raw_read_16(e + 4, -1),
        });
        e += 8;
    }
    v
}

fn hide(core: &mut Core, e: &Entry) {
    core.raw_write_16(e.at, -1, (e.a0 & !0x300) | 0x200);
}

fn move_to(core: &mut Core, e: &Entry, x: i32, y: i32) {
    core.raw_write_16(e.at, -1, (e.a0 & !0xFF) | (y as u16 & 0xFF));
    core.raw_write_16(e.at + 2, -1, (e.a1 & !0x1FF) | (x as u16 & 0x1FF));
}

/// Put `sprites` into the list in front of the entry at `before` (so over
/// everything the game drew after it), moving the rest up. The new end.
fn insert(core: &mut Core, before: u32, at: u32, end: u32, sprites: &[Spr]) -> u32 {
    let n = sprites.len() as u32;
    if n == 0 || at + 8 * n > end {
        return at;
    }
    let mut buf = vec![0u8; (at - before) as usize];
    core.raw_read_range(before, -1, &mut buf);
    core.raw_write_range(before + 8 * n, -1, &buf);
    for (k, s) in sprites.iter().enumerate() {
        let a = s.attrs();
        let p = before + 8 * k as u32;
        core.raw_write_16(p, -1, a[0]);
        core.raw_write_16(p + 2, -1, a[1]);
        core.raw_write_16(p + 4, -1, a[2]);
        core.raw_write_16(p + 6, -1, 0);
    }
    at + 8 * n
}

// --- Borrowed tiles and palettes -----------------------------------------------------------------

/// What AW2 had in the OBJ tiles and palette 7 we borrow, while ours are in.
struct Saved {
    tiles: Vec<u8>,
}

static SAVED: Mutex<Option<Saved>> = Mutex::new(None);

fn write_tiles(core: &mut Core, tile: u32, b: &[u8]) {
    let at = OBJ_VRAM + 32 * tile;
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != b {
        core.raw_write_range(at, -1, b);
    }
}

fn write_palette(core: &mut Core, pal: u32, p: &[u8; 32]) {
    for base in [PAL_BUFFER, PAL_RAM] {
        let at = base + 0x200 + 32 * pal;
        let mut now = [0u8; 32];
        core.raw_read_range(at, -1, &mut now);
        if &now != p {
            core.raw_write_range(at, -1, p);
        }
    }
}

/// AW2's army colours for the CO panel's palette 7 (loaded at each turn's
/// start from this table, 0x20 an army colour).
const AW2_HEADER_PALETTES: u32 = 0x0810_4264;
const CURRENT_ARMY: u32 = 0x0300_33EC;

/// AW2's palette 7 for the turn's army, from the game's own table.
fn aw2_header_palette(core: &Core) -> Option<[u8; 32]> {
    let army = core.raw_read_16(CURRENT_ARMY, -1) as u32;
    if !(1..=5).contains(&army) {
        return None;
    }
    let colour = core.raw_read_8(crate::five::players(core) + 0x3C * army + PL_COLOUR, -1) as u32;
    if !(1..=5).contains(&colour) {
        return None;
    }
    let mut p = [0u8; 32];
    core.raw_read_range(AW2_HEADER_PALETTES + 32 * (colour - 1), -1, &mut p);
    Some(p)
}

/// What AW2 had in the panel's digit tiles while ours are in. The digits are the info panel's own, loaded while the
/// panel shows, whether or not the CO panel is (it is not while an attack target is chosen: the digits once went back
/// to AW2's stars and dots then).
static SAVED_DIGITS: Mutex<Option<Vec<u8>>> = Mutex::new(None);

fn digits_borrow(core: &mut Core, a: &Art) {
    if let Ok(mut s) = SAVED_DIGITS.lock() {
        if s.is_none() {
            let mut tiles = vec![0u8; 32 * DIGIT_TILES];
            core.raw_read_range(OBJ_VRAM + 32 * T_DIGIT as u32, -1, &mut tiles);
            *s = Some(tiles);
        }
    }
    write_tiles(core, T_DIGIT as u32, &a.digits);
}

fn digits_restore(core: &mut Core) {
    let saved = SAVED_DIGITS.lock().ok().and_then(|mut s| s.take());
    if let Some(t) = saved {
        write_tiles(core, T_DIGIT as u32, &t);
    }
}

/// Put AW2's tiles and palette 7 back (once).
fn restore(core: &mut Core) {
    let saved = SAVED.lock().ok().and_then(|mut s| s.take());
    if let Some(s) = saved {
        write_tiles(core, 0, &s.tiles);
        if let Some(p) = aw2_header_palette(core) {
            write_palette(core, 7, &p);
        }
    }
}

/// Borrow the tiles and palette 7 (saving AW2's the first time).
fn borrow(core: &mut Core, a: &Art, colour: u8, step: usize) {
    let first = SAVED.lock().map(|s| s.is_none()).unwrap_or(false);
    if first {
        let mut tiles = vec![0u8; 32 * BORROWED_TILES];
        core.raw_read_range(OBJ_VRAM, -1, &mut tiles);
        if let Ok(mut s) = SAVED.lock() {
            *s = Some(Saved { tiles });
        }
    }
    write_tiles(core, T0 as u32, &a.sheet);
    let mut pal = a.palettes[(colour.clamp(1, 5) - 1) as usize];
    pal[30..32].copy_from_slice(&a.pulse[step % 16].to_le_bytes());
    // The sandstorm's grains are drawn in this palette's colours 5 to 7 ([`crate::sandstorm`]).
    if crate::sandstorm::active(core) {
        for (i, c) in crate::sandstorm::grain_colours().iter().enumerate() {
            pal[10 + 2 * i..12 + 2 * i].copy_from_slice(&c.to_le_bytes());
        }
    }
    write_palette(core, 7, &pal);
}

// --- The CO panel's call ---------------------------------------------------------------------------

static PANEL_X: AtomicI32 = AtomicI32::new(0);
static PANEL_Y: AtomicI32 = AtomicI32::new(0);
static PANEL_ARMY: AtomicU32 = AtomicU32::new(0);
static PANEL_DRAWN: AtomicBool = AtomicBool::new(false);

/// `DrawArmyCoPanel(x, y, army)` was called: the panel's place this frame
/// (called from [`crate::tag`]'s trap, after the two-front view has moved it
/// out of sight).
pub fn note_panel(core: &Core) {
    if !on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (x, y, a) = (cpu.gpr(0) as u16 as i16 as i32, cpu.gpr(1) as u16 as i16 as i32, cpu.gpr(2) as u32);
    PANEL_X.store(x, Ordering::Relaxed);
    PANEL_Y.store(y, Ordering::Relaxed);
    PANEL_ARMY.store(a, Ordering::Relaxed);
    PANEL_DRAWN.store(true, Ordering::Relaxed);
}

const PL_FUNDS: u32 = 0x00;
const PL_COLOUR: u32 = 0x1A;
const PL_CO: u32 = 0x1D;
const PL_MODE: u32 = 0x1E;
const PL_CHARGE: u32 = 0x20;
const PL_USES: u32 = 0x25;
const PLAY_ST_POWERS: u32 = 0x0300_3FC7;

/// Star level 0..3 of star `k` for a meter of `charge`, a star costing `per`.
fn level(charge: u32, per: u32, k: u32) -> usize {
    let per = per.max(1);
    let have = charge.saturating_sub(per * k).min(per) * 3;
    if have >= per * 3 {
        3
    } else if have >= per * 2 {
        2
    } else if have >= per {
        1
    } else {
        0
    }
}

struct Row {
    co: u8,
    cop: u32,
    scop: u32,
    charge: u32,
    per: u32,
    /// A power is on (the meter shows full, as Dual Strike's does).
    lit: bool,
    /// The face's tile and palette.
    face_tile: u16,
    face_pal: u16,
}

/// The CO panel's sprites for rows (the active CO, its partner) with the
/// funds between, on the left (`left`) or right edge of a screen 240 wide.
fn co_panel(left: bool, rows: &[Row], funds: u32, powers: bool) -> Vec<Spr> {
    const W: i32 = 240;
    let mut v: Vec<Spr> = Vec::new();
    // x of a sprite `w` wide at `x` on the left, as it is drawn on the right.
    let mx = |x: i32, w: i32| if left { x } else { W - x - w };
    // The funds: "G." and the digits, right-aligned to the panel's inner
    // edge (60 pixels in).
    let digits: Vec<u32> = funds.to_string().bytes().map(|b| (b - b'0') as u32).collect();
    let n = digits.len().min(6) as i32;
    let fy = 14;
    let gx = if left { 0 } else { W - 60 };
    v.push(Spr::new(gx, fy, 16, 8, T_GOLD, 7));
    let last = if left { 60 - 8 } else { W - 8 };
    for (i, d) in digits.iter().rev().take(n as usize).enumerate() {
        v.push(Spr::new(last - 7 * i as i32, fy, 8, 8, T_FUNDS_DIGIT + *d as u16, 7));
    }
    // The rows, the last (lowest) first so the active one is drawn over the
    // plate edge it shares.
    for (r, row) in rows.iter().enumerate().rev() {
        let ry = 20 * r as i32;
        if powers {
            let small = row.cop.min(10);
            let total = row.scop.min(10).max(small);
            // Stars: the small ones (the CO Power's) nearest the face, the big
            // ones (the rest of the Super Power) after them.
            for k in (0..total).rev() {
                let lv = if row.lit { 3 } else { level(row.charge, row.per, k) };
                if k < small {
                    let x = 32 + 6 * k as i32;
                    v.push(Spr::new(mx(x, 8), ry + 6, 8, 8, T_STAR_SMALL + lv as u16, 7));
                } else {
                    let x = 32 + 6 * k as i32;
                    v.push(Spr::new(mx(x, 8), ry - 3, 8, 16, T_STAR_BIG + 2 * lv as u16, 7));
                }
            }
        }
        v.push(Spr::new(mx(0, 32), ry + 2, 32, 16, row.face_tile, row.face_pal).flip(!left, false));
        for (dy, vf) in [(0, false), (8, true)] {
            v.push(Spr::new(mx(0, 32), ry + dy, 32, 8, T_PLATE_A, 7).flip(!left, vf));
            v.push(Spr::new(mx(32, 32), ry + dy, 32, 8, T_PLATE_B, 7).flip(!left, vf));
        }
    }
    v
}

/// Whether AW2's header (a 64x32 sprite, tile 0, palette 7) is `e`.
fn is_header(e: &Entry) -> bool {
    (e.a0 >> 14) == 1 && (e.a1 >> 14) == 3 && e.tile() == 0 && e.pal() == 7 && !e.hidden()
}

const ACTIVE_FACE_TILE: u16 = 58;
const PARTNER_FACE_TILE: u16 = 0x309;
const PARTNER_FACE_PAL: u16 = 5;

fn co_flush(core: &mut Core, list: &[Entry], at: u32, end: u32) -> Option<u32> {
    let a = art()?;
    if !PANEL_DRAWN.swap(false, Ordering::Relaxed) {
        return None;
    }
    let (px, py, army) = (PANEL_X.load(Ordering::Relaxed), PANEL_Y.load(Ordering::Relaxed), PANEL_ARMY.load(Ordering::Relaxed));
    // The map's panel only (the CO page draws one at its foot).
    if !(0..64).contains(&py) || !(1..=5).contains(&army) {
        return None;
    }
    let header = list.iter().find(|e| is_header(e) && (e.x() - px).abs() <= 2)?;
    let player = crate::five::players(core) + 0x3C * army;
    let co = core.raw_read_8(player + PL_CO, -1);
    let colour = core.raw_read_8(player + PL_COLOUR, -1);
    let funds = core.raw_read_32(player + PL_FUNDS, -1);
    let mode = core.raw_read_8(player + PL_MODE, -1);
    let uses = core.raw_read_8(player + PL_USES, -1);
    let charge = if mode == 0 { core.raw_read_32(player + PL_CHARGE, -1) } else { 0 };
    let powers = core.raw_read_8(PLAY_ST_POWERS, -1) != 0;
    let (cop, scop) = crate::tag::co_stars(core, co);
    let mut rows = vec![Row {
        co,
        cop,
        scop,
        charge,
        per: crate::tag::star_cost(uses),
        lit: mode != 0 || crate::tag::phase(core, army) != 0,
        face_tile: ACTIVE_FACE_TILE,
        face_pal: 14,
    }];
    let partner = crate::tag::partner(core, army);
    if let Some(p) = partner {
        let (pc, ps) = crate::tag::co_stars(core, p);
        let uses = crate::tag::partner_uses(core, army);
        rows.push(Row {
            co: p,
            cop: pc,
            scop: ps,
            charge: crate::tag::partner_charge(core, army),
            per: crate::tag::star_cost(uses),
            lit: crate::tag::phase(core, army) != 0,
            face_tile: PARTNER_FACE_TILE,
            face_pal: PARTNER_FACE_PAL,
        });
    }
    // The partner's face borrows tiles the heal effect draws in.
    if partner.is_some() && crate::heal_effect::playing(core) {
        rows.truncate(1);
    }
    // ... and the build menu's unit picture (OBJ tiles 0x2E8..0x327) and labels (palette 5): the
    // partner's row is left out while the menu is up, as [`crate::tag_ui`]'s strip is.
    if partner.is_some() && crate::tag_ui::build_menu_up(core) {
        rows.truncate(1);
    }
    let left = px < 120;
    // AW2's own pieces of the panel go: the header, the stars, the face and
    // the funds' digits.
    for e in list {
        if e.hidden() {
            continue;
        }
        let (w, h) = e.dims();
        let inside = e.x() >= px - 4 && e.x() + w <= px + 70 && e.y() >= py - 4 && e.y() + h <= py + 40;
        let ours = (e.pal() == 7 && (e.a0 >> 8) & 3 != 2 && inside)
            || (e.pal() == 14 && e.tile() == ACTIVE_FACE_TILE && inside)
            || (e.pal() == 1 && (976..986).contains(&e.tile()) && w == 8 && h == 8 && inside && e.y() == py + 3);
        if ours {
            hide(core, e);
        }
    }
    let step = (FRAME.fetch_add(1, Ordering::Relaxed) / 2) as usize;
    borrow(core, a, colour, step);
    // The faces (the game reloads the active one every call: written after it).
    let (tiles, pal) = face(core, rows[0].co);
    write_tiles(core, ACTIVE_FACE_TILE as u32, &tiles);
    write_palette(core, 14, &pal);
    if let Some(r) = rows.get(1) {
        let (tiles, pal) = face(core, r.co);
        write_tiles(core, PARTNER_FACE_TILE as u32, &tiles);
        write_palette(core, PARTNER_FACE_PAL as u32, &pal);
    }
    let mut sprites = co_panel(left, &rows, funds, powers);
    // AW2 slides its panel in and out (its x and y move): ours with it, from
    // the place AW2's rests at.
    let (dx, dy) = (px - if left { 3 } else { 173 }, py - 3);
    for sp in sprites.iter_mut() {
        sp.x += dx;
        sp.y += dy;
    }
    Some(insert(core, header.at, at, end, &sprites))
}

// --- The terrain and unit panel ----------------------------------------------------------------

const T_STAR_ICON: u16 = 850;
const T_CAP_ICON: u16 = 854;
const T_HEART: u16 = 862;
/// The heart of a structure's hit points in the terrain column (a Black Crystal, Cannon, Factory...): AW2's own tile, not
/// the unit's 862.
const T_STRUCT_HEART: u16 = 858;
static LAST_STRUCT_HP: Mutex<Option<u32>> = Mutex::new(None);
/// AW2's "?" (a hidden hit point number's stand-in).
const T_QUESTION: u16 = 988;
const T_AMMO: u16 = 863;
const T_FUEL: u16 = 864;
const T_TERRAIN_NAME: u16 = 458;
const T_UNIT_NAME: u16 = 466;
const T_UNIT_PIC: u16 = 474;

const CURSOR_X: u32 = 0x0300_33E4;
const CURSOR_Y: u32 = 0x0300_33E6;

/// Dual Strike's panel: its size (terrain only, with a unit) and the
/// margin from the screen's bottom and sides.
const PANEL_H: i32 = 61;
const PANEL_W_TERRAIN: i32 = 42;
const PANEL_W_UNIT: i32 = 78;
const MARGIN: i32 = 2;
const TOP: i32 = 160 - PANEL_H - MARGIN;

fn digit_value(e: &Entry) -> Option<u32> {
    (e.pal() == 1 && e.mode() == 1 && (976..986).contains(&e.tile()) && e.dims() == (8, 8)).then(|| (e.tile() - 976) as u32)
}

/// A number's digit sprites, right-aligned to `right` (each 7 pixels, a
/// narrow 1 6 as Dual Strike's `100`), `pad` digits at least.
fn number(v: &mut Vec<Spr>, value: u32, pad: usize, right: i32, y: i32) {
    let mut s = value.to_string();
    while s.len() < pad {
        s.insert(0, '0');
    }
    let ds: Vec<u32> = s.bytes().map(|b| (b - b'0') as u32).collect();
    let mut x = right - 8;
    for (i, d) in ds.iter().rev().enumerate() {
        if i > 0 {
            x -= if *d == 1 { 6 } else { 7 };
        }
        v.push(Spr::new(x, y, 8, 8, T_DIGIT + *d as u16, 1).mode(1));
    }
}

fn unit_hp(core: &Core) -> Option<u32> {
    let (x, y) = (core.raw_read_8(CURSOR_X, -1) as i32, core.raw_read_8(CURSOR_Y, -1) as i32);
    let u = crate::unit_actions::unit_at(core, x, y)?;
    Some((core.raw_read_16(u + 4, -1) & 0x7F) as u32)
}

fn info_flush(core: &mut Core, list: &[Entry], at: u32, end: u32) -> Option<u32> {
    let a = art()?;
    // AW2's panel: its semi-transparent sprites in the lower corners.
    let panel: Vec<&Entry> = list.iter().filter(|e| e.mode() == 1 && !e.hidden() && e.y() >= 90 && e.y() < 160).collect();
    if panel.is_empty() {
        return None;
    }
    let find = |tile: u16| panel.iter().find(|e| e.tile() == tile && e.pal() == 1).copied();
    let terrain_name = find(T_TERRAIN_NAME);
    let unit_name = find(T_UNIT_NAME);
    let terrain_pic = panel.iter().find(|e| e.pal() == 6 && e.dims() == (16, 32)).copied();
    let unit_pic = panel.iter().find(|e| e.tile() == T_UNIT_PIC && e.dims() == (16, 16)).copied();
    let icon = |t: u16| panel.iter().find(|e| e.tile() == t && e.pal() == 1).copied();
    let (star, cap, heart, fuel, ammo) = (icon(T_STAR_ICON), icon(T_CAP_ICON), icon(T_HEART), icon(T_FUEL), icon(T_AMMO));
    let struct_heart = icon(T_STRUCT_HEART);
    // A unit whose hit points AW2 hides (Sonja's) shows a "?" where the number would be.
    let hidden_hp = panel.iter().find(|e| e.tile() == T_QUESTION && e.pal() == 1 && e.dims() == (8, 8)).copied();
    // (a panel has its terrain's name or picture)
    if terrain_name.is_none() && terrain_pic.is_none() {
        return None;
    }
    let first = panel.iter().map(|e| e.at).min()?;
    digits_borrow(core, a);
    // The side: AW2's window (or, failing that, its sprites).
    let xs = panel.iter().map(|e| e.x()).min()?;
    let left = xs < 120;
    PANEL_SIDE.store(if left { 1 } else { 2 }, Ordering::Relaxed);
    let with_unit = unit_name.is_some();
    let w = if with_unit { PANEL_W_UNIT } else { PANEL_W_TERRAIN };
    let px = if left { MARGIN } else { 240 - MARGIN - w };
    // Blocks' origins: the terrain's and the unit's.
    let (tx, ux) = if left { (px, px + 34) } else if with_unit { (px + 41, px + 3) } else { (px + 4, 0) };
    // The numbers AW2 shows, by the icon they follow.
    // (the structure's heart comes after the star: the later icon wins a tie of x, and its row is the lower)
    let icons: Vec<(&str, &Entry)> = [("star", star), ("cap", cap), ("heart", heart), ("fuel", fuel), ("ammo", ammo), ("shp", struct_heart)]
        .into_iter()
        .filter_map(|(n, e)| e.map(|e| (n, e)))
        .collect();
    let mut shown: HashMap<&str, Vec<(i32, u32)>> = HashMap::new();
    for e in &panel {
        let Some(d) = digit_value(e) else { continue };
        let owner = icons
            .iter()
            .filter(|(_, i)| {
                let (_, ih) = i.dims();
                e.x() > i.x() && e.y() >= i.y() - 2 && e.y() < i.y() + ih
            })
            .max_by_key(|(_, i)| i.x());
        if let Some((n, _)) = owner {
            shown.entry(*n).or_default().push((e.x(), d));
        }
    }
    let value = |n: &str| -> Option<u32> {
        let mut v = shown.get(n)?.clone();
        v.sort();
        Some(v.iter().fold(0, |acc, (_, d)| acc * 10 + d))
    };
    // Hide the digits; every other piece of AW2's moves.
    for e in &panel {
        if digit_value(e).is_some() {
            hide(core, e);
        }
    }
    let mut mine: Vec<Spr> = Vec::new();
    let y0 = TOP;
    if let Some(e) = terrain_name {
        move_to(core, e, tx + 3, y0 + 3);
    }
    if let Some(e) = terrain_pic {
        move_to(core, e, tx + 11, y0 - 2);
    }
    if let Some(e) = star {
        move_to(core, e, tx + 4, y0 + 29);
        number(&mut mine, value("star").unwrap_or(0), 2, tx + 32, y0 + 33);
    }
    if let Some(e) = cap {
        move_to(core, e, tx + 4, y0 + 40);
        number(&mut mine, value("cap").unwrap_or(0), 2, tx + 32, y0 + 44);
    }
    // A structure with hit points: AW2's heart and number go where a property's capture points are (a structure has none),
    // under the defence row, the number right-aligned in the box (up to three digits: the Black Factory's 200).
    if let Some(e) = struct_heart {
        move_to(core, e, tx + 4, y0 + 40);
        // AW2 blinks the hit points' digits off for a few frames now and then: the last number stands in for those.
        let v = value("shp").or_else(|| LAST_STRUCT_HP.lock().ok().and_then(|l| *l)).unwrap_or(0);
        if let Ok(mut l) = LAST_STRUCT_HP.lock() {
            *l = Some(v);
        }
        number(&mut mine, v, 1, tx + 37, y0 + 44);
    } else if let Ok(mut l) = LAST_STRUCT_HP.lock() {
        *l = None;
    }
    if with_unit {
        if let Some(e) = unit_name {
            move_to(core, e, ux, y0 + 3);
        }
        if let Some(e) = unit_pic {
            move_to(core, e, ux + 8, y0 + 14);
        }
        let mut row = 0;
        for (e, n, pad) in [(heart, "heart", 1usize), (fuel, "fuel", 2), (ammo, "ammo", 2)] {
            let Some(e) = e else { continue };
            let y = y0 + [28, 37, 45][row];
            move_to(core, e, ux + 4, y);
            if n == "heart" && hidden_hp.is_some() {
                // (the number is not drawn at all: it is not the player's to read)
                if let Some(q) = hidden_hp {
                    move_to(core, &q, ux + 31 - 8, y + 1);
                }
                row += 1;
                continue;
            }
            let v = if n == "heart" { unit_hp(core).or(value(n).map(|d| d * 10)).unwrap_or(0) } else { value(n).unwrap_or(0) };
            if n == "heart" {
                number(&mut mine, v, pad, ux + 31, y + 1);
            } else {
                number(&mut mine, v, pad, ux + 28, y);
            }
            row += 1;
        }
    }
    // The backing: AW2's window, at Dual Strike's rectangle.
    let (wx0, wx1) = (px, px + w);
    window_take(core, [wx0 as u8, wx1 as u8, y0 as u8, (y0 + PANEL_H) as u8]);
    // Our digits go in front of the panel's first sprite (the list's order
    // is priority: the map's cursor and units stay behind the panel).
    Some(insert(core, first, at, end, &mine))
}


// --- The damage forecast box --------------------------------------------------------------------------

/// AW2's box: ten digits of 8 x 16 (OBJ tiles 422..441) and a 32 x 32 frame (442..457), palette 1. Dual Strike's box is
/// the same layout in `bmap/02d` (its tiles in the same order), so its tiles go into AW2's and the sprites move.
const T_BOX_DIGITS: u16 = 422;
const T_BOX_FRAME: u16 = 442;
const T_BOX_END: u16 = 458;
/// Which side the info panel took this frame: 0 none, 1 left, 2 right (set by [`info_flush`]).
static PANEL_SIDE: AtomicU32 = AtomicU32::new(0);
static SAVED_BOX: Mutex<Option<Vec<u8>>> = Mutex::new(None);

fn box_restore(core: &mut Core) {
    let saved = SAVED_BOX.lock().ok().and_then(|mut s| s.take());
    if let Some(t) = saved {
        write_tiles(core, T_BOX_DIGITS as u32, &t);
    }
}

/// Dual Strike's forecast box: its art in AW2's tiles, put on the info panel's side (away from the target) just
/// above the panel: left from x 34, right 35 from the screen's edge (Dual Strike's, read from real frames), the
/// number AW2's.
fn box_flush(core: &mut Core, list: &[Entry]) -> bool {
    let Some(a) = art() else { return false };
    let frame = list.iter().find(|e| e.tile() == T_BOX_FRAME && e.pal() == 1 && e.dims() == (32, 32) && !e.hidden());
    let Some(frame) = frame else { return false };
    let side = PANEL_SIDE.load(Ordering::Relaxed);
    let left = match side {
        1 => true,
        2 => false,
        _ => frame.x() < 120 - 16,
    };
    // (the tiles go in once, AW2's kept for the setting going off)
    if let Ok(mut s) = SAVED_BOX.lock() {
        if s.is_none() {
            let mut t = vec![0u8; 32 * DAMAGE_TILES];
            core.raw_read_range(OBJ_VRAM + 32 * T_BOX_DIGITS as u32, -1, &mut t);
            *s = Some(t);
        }
    }
    write_tiles(core, T_BOX_DIGITS as u32, &a.damage);
    let (fx, fy) = if left { (34, TOP - 28) } else { (240 - 35 - 32, TOP - 26) };
    let (ox, oy) = (fx - frame.x(), fy - frame.y());
    for e in list {
        let t = e.tile();
        let ours = e.pal() == 1 && !e.hidden() && (e.at == frame.at || ((T_BOX_DIGITS..T_BOX_FRAME).contains(&t) && e.dims() == (8, 16)));
        if ours {
            move_to(core, e, e.x() + ox, e.y() + oy);
        }
    }
    true
}

// --- The flush ---------------------------------------------------------------------------------------

/// At the sprite flush ([`crate::branding::flush`]): `start..at` is the
/// frame's list; returns its new end.
pub fn flush(core: &mut Core, start: u32, at: u32, end: u32) -> u32 {
    // (the Design Room's map editor has no CO or terrain panel: its translucent sprites at the foot are its own
    // Feature box, not a panel to take the backing window for)
    if !on(core) || crate::design::in_map_editor(core) {
        restore(core);
        digits_restore(core);
        box_restore(core);
        window_release(core);
        PANEL_DRAWN.store(false, Ordering::Relaxed);
        return at;
    }
    let mut at = at;
    let list = entries(core, start, at);
    match co_flush(core, &list, at, end) {
        Some(n) => at = n,
        None => restore(core),
    }
    // (the CO panel's insertion moved entries up: read the list again)
    let list = entries(core, start, at);
    match info_flush(core, &list, at, end) {
        Some(n) => at = n,
        None => {
            digits_restore(core);
            window_release(core);
            PANEL_SIDE.store(0, Ordering::Relaxed);
        }
    }
    // (the box's sprites sit in the list as the game drew them: the lists' entries moved up are read again)
    let list = entries(core, start, at);
    if !box_flush(core, &list) {
        box_restore(core);
    }
    at
}

/// Where Dual Strike's CO panel is drawn this frame: `Some(true)` the left
/// corner (for [`crate::survival`]'s budget, which keeps clear of it).
pub fn panel_corner(core: &Core) -> Option<bool> {
    if !on(core) || art().is_none() || !PANEL_DRAWN.load(Ordering::Relaxed) {
        return None;
    }
    let (x, y) = (PANEL_X.load(Ordering::Relaxed), PANEL_Y.load(Ordering::Relaxed));
    (0..64).contains(&y).then_some(x < 120)
}

/// Whether the HUD is Dual Strike's and drew the CO panel this frame (for
/// [`crate::tag_ui`], which then leaves its own strip out).
pub fn draws_co_panel(core: &Core) -> bool {
    on(core) && art().is_some()
}
