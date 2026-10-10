//! "Dual Strike tilt": a display-only look for the battle map.
//!
//! Dual Strike draws its battle map as a 3D plane tilted away from the
//! viewer (rows near the bottom are wider and taller than rows near the top,
//! columns converge toward the top), with units, buildings and treetops as
//! upright billboards on it, and the HUD flat on the screen. This module
//! turns the Game Boy Advance picture into that, after the emulator has
//! drawn it. It reads the console's video memory (never writes it) and
//! rewrites the RGBA picture the host shows, so the simulation, RAM, netplay
//! and rollback are untouched and the result is a pure function of the
//! console's state: the same on every peer and after every rollback.
//!
//! How it works, per frame (about 0.2 ms; a tiny framebuffer):
//!
//! 1. Gate. Only the battle map in Dual Strike graphics mode
//!    ([`crate::wasteland::ds_graphics`]), tile mode 0, no fade: anything
//!    else (menus screens, dialogue, the world map, battle animations, the
//!    title) is left exactly as the console drew it.
//! 2. The layers are decoded from VRAM, palette RAM, OAM and the video
//!    registers. The map's: BG3 (terrain), BG1 (units, their HP digits and
//!    status icons), BG2 (peaks and treetops over the cell above), BG0 while
//!    it is the movement/attack range overlay (below the units), the OBJs of
//!    priority 3 (buildings), the move arrow and the cursor. Everything else
//!    (BG0 as text, the CO and terrain panels, menus, other OBJs) is HUD.
//! 3. The hardware's own priority and window rules are replayed to find, for
//!    every pixel, which layer is on top. Pixels whose top layer is HUD keep
//!    the console's pixel; the others are replaced by the tilted map.
//!    Where a window darkens the map (the terrain panel's tint) the tilted
//!    map is darkened the same way.
//! 4. The tilted map: the flat ground (terrain, range overlay, move arrow,
//!    cursor brackets) is projected onto a perspective plane; then the upright
//!    things (16 x 16 cells of the unit and peak layers, the buildings, the
//!    cursor's pointer) are drawn back to front as billboards standing on their
//!    cell's front edge, scaled with depth but not squashed.

use crate::ds_ground::Ground;
use crate::wasteland::MAP;
use mgba::core::Core;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;

static ENABLED: AtomicBool = AtomicBool::new(false);

/// The frontend's setting (Settings > Graphics > Dual Strike tilt).
pub fn set_enabled(on: bool) {
    ENABLED.store(on, Ordering::Relaxed);
}

fn env_on(name: &str, cache: &'static OnceLock<bool>) -> bool {
    *cache.get_or_init(|| std::env::var(name).map(|v| v == "1").unwrap_or(false))
}

/// Whether the tilt is switched on: the setting, or `TANGOAW2_TILT=1` (for
/// the test runner, which has no settings).
pub fn enabled() -> bool {
    static ENV: OnceLock<bool> = OnceLock::new();
    ENABLED.load(Ordering::Relaxed) || env_on("TANGOAW2_TILT", &ENV)
}

const W: usize = 240;
const H: usize = 160;
/// The battle map's main-loop callback (word at 0x03000000).
const BATTLE_MAIN: u32 = 0x0802_2049;
const MAIN_LOOP: u32 = 0x0300_0000;

// --- The camera ---------------------------------------------------------------
//
// Fitted to real Dual Strike frames (melonDS, Snow Hunters, five cursor
// positions): the pipe walls, coast lines and trees of the registered
// ground land within 1 pixel (mean 0.94, 90th percentile 1.0, on 256 x 192
// pixels). A pinhole camera pitched 16.9 degrees from straight down, 49.9
// cells high, with a focal length of 758 pixels (a narrow field of view: the
// map is seen from far away): about 14 pixels a cell across at the top of the
// screen and 15 at the bottom, 13 pixels a row at the top and 14.9 at the
// bottom. Its picture is 256 x 192 and ours 240 x 160, so everything is
// scaled by 240 / 256 to keep the width.

/// Focal length in our pixels.
const FOCAL: f32 = 757.8 * 240.0 / 256.0;
/// Pitch from straight down, radians (16.88 degrees).
const PITCH: f32 = 0.2947;
/// Camera height over the ground, in cells.
const HEIGHT: f32 = 49.93;
/// The screen's centre, where the camera looks.
const CX: f32 = W as f32 / 2.0;
const CY: f32 = H as f32 / 2.0;
/// Billboards stand this far in front of their cell's bottom edge (cells):
/// Dual Strike's units' feet are just below it.
const FOOT_DROP: f32 = 0.1;

/// Where the fitted camera's principal ray meets the ground, from the cursor
/// cell's corner (cells).
const CAM_BIAS: (f32, f32) = (0.03, 0.08);
/// The table of the steps the selected unit's move costs to each cell (a byte a
/// cell, rows by the map's row table; 0xFF: out of reach).
const REACH: u32 = 0x0202_0CA2;
const CURSOR_X: u32 = 0x0300_33E4;
const CURSOR_Y: u32 = 0x0300_33E6;

/// What the camera has done so far (display only: it follows what is shown).
struct Follow {
    /// Where the dead zone has left it, and where it shows.
    logical: (f32, f32),
    shown: (f32, f32),
    map: (i32, i32),
}
static FOLLOW: std::sync::Mutex<Option<Follow>> = std::sync::Mutex::new(None);

/// The camera's centre for a cursor on a `w` x `h` map: it stays while the
/// cursor's cell is within 5 cells to its left, 6 to its right, 3 above and 4
/// below (the cell inside +-6 and +-4 by its far edge), never shows beyond the
/// map's edge (centre at least 8 cells from the sides and 6 from the top and
/// bottom) and centres a map smaller than that; it glides there.
fn follow(cursor: (i32, i32), w: i32, h: i32) -> (f32, f32) {
    let (cx, cy) = (cursor.0 as f32, cursor.1 as f32);
    let clamp_to_map = |x: f32, y: f32| {
        (
            if w >= 16 { x.clamp(8.0, (w - 8) as f32) } else { w as f32 / 2.0 },
            if h >= 12 { y.clamp(6.0, (h - 6) as f32) } else { h as f32 / 2.0 },
        )
    };
    let mut st = FOLLOW.lock().unwrap();
    let fresh = st.as_ref().map_or(true, |f| f.map != (w, h));
    let f = st.get_or_insert(Follow { logical: (cx, cy), shown: (0.0, 0.0), map: (w, h) });
    if fresh {
        *f = Follow { logical: (cx, cy), shown: (0.0, 0.0), map: (w, h) };
        f.logical = (
            f.logical.0.clamp(cx - 5.0, cx + 6.0),
            f.logical.1.clamp(cy - 3.0, cy + 4.0),
        );
    }
    f.logical = (
        f.logical.0.clamp(cx - 5.0, cx + 6.0),
        f.logical.1.clamp(cy - 3.0, cy + 4.0),
    );
    let target = clamp_to_map(f.logical.0, f.logical.1);
    static SNAP: OnceLock<bool> = OnceLock::new();
    if fresh || env_on("TANGOAW2_TILT_SNAP", &SNAP) {
        f.shown = target;
    } else {
        f.shown.0 += (target.0 - f.shown.0) * 0.3;
        f.shown.1 += (target.1 - f.shown.1) * 0.3;
        if (target.0 - f.shown.0).abs() < 0.02 {
            f.shown.0 = target.0;
        }
        if (target.1 - f.shown.1).abs() < 0.02 {
            f.shown.1 = target.1;
        }
    }
    f.shown
}

/// The camera over the ground point (`cu`, `cv`), in cells, that it looks at.
#[derive(Clone, Copy)]
struct Cam {
    cu: f32,
    cv: f32,
    sin: f32,
    cos: f32,
    tan: f32,
}

impl Cam {
    fn new(cu: f32, cv: f32) -> Cam {
        Cam { cu, cv, sin: PITCH.sin(), cos: PITCH.cos(), tan: PITCH.tan() }
    }

    /// The screen position of the ground point (u, v) in cells, and the size
    /// of a cell there in pixels across.
    fn project(&self, u: f32, v: f32) -> (f32, f32, f32) {
        let dx = u - self.cu;
        let dy = v - self.cv - HEIGHT * self.tan;
        let depth = HEIGHT * self.cos - dy * self.sin;
        let up = -dy * self.cos - HEIGHT * self.sin;
        (CX + FOCAL * dx / depth, CY - FOCAL * up / depth, FOCAL / depth)
    }

    /// The ground point (cells) under a screen position.
    fn unproject(&self, xs: f32, ys: f32) -> (f32, f32) {
        let a = (xs - CX) / FOCAL;
        let b = -(ys - CY) / FOCAL;
        let lam = -HEIGHT / (b * self.sin - self.cos);
        (self.cu + lam * a, self.cv + HEIGHT * self.tan + lam * (-b * self.cos - self.sin))
    }

    /// How far the screen reaches from the looked-at point: left, right, up,
    /// down, in cells (the widest row for the sides).
    fn reach(&self) -> (f32, f32, f32, f32) {
        let (ul0, vt) = self.unproject(0.0, 0.0);
        let (ur0, _) = self.unproject(W as f32, 0.0);
        let (_, vb) = self.unproject(CX, H as f32);
        (self.cu - ul0, ur0 - self.cu, self.cv - vt, vb - self.cv)
    }
}

// --- Video memory ---------------------------------------------------------------

pub(crate) struct Vid {
    pub(crate) io: [u16; 0x30],
    pub(crate) pal: [u16; 512],
    pub(crate) oam: [u16; 512],
    pub(crate) vram: Vec<u8>,
    /// 4 KiB pages of `vram` read so far.
    loaded: [bool; 24],
}

impl Vid {
    pub(crate) fn read(core: &Core) -> Vid {
        let mut io = [0u16; 0x30];
        for (i, v) in io.iter_mut().enumerate() {
            *v = core.raw_read_16(0x0400_0000 + 2 * i as u32, -1);
        }
        let mut pal = [0u16; 512];
        for i in 0..256 {
            let w = core.raw_read_32(0x0500_0000 + 4 * i as u32, -1);
            pal[2 * i] = w as u16;
            pal[2 * i + 1] = (w >> 16) as u16;
        }
        let mut oam = [0u16; 512];
        for i in 0..256 {
            let w = core.raw_read_32(0x0700_0000 + 4 * i as u32, -1);
            oam[2 * i] = w as u16;
            oam[2 * i + 1] = (w >> 16) as u16;
        }
        Vid {
            io,
            pal,
            oam,
            vram: vec![0u8; 0x18000],
            loaded: [false; 24],
        }
    }

    /// Makes `[addr, addr + len)` of VRAM available.
    pub(crate) fn ensure(&mut self, core: &Core, addr: usize, len: usize) {
        let end = (addr + len).min(0x18000);
        let mut page = addr / 0x1000;
        while page * 0x1000 < end {
            if !self.loaded[page] {
                let base = page * 0x1000;
                for i in 0..0x400 {
                    let w = core.raw_read_32(0x0600_0000 + (base + 4 * i) as u32, -1);
                    self.vram[base + 4 * i..base + 4 * i + 4].copy_from_slice(&w.to_le_bytes());
                }
                self.loaded[page] = true;
            }
            page += 1;
        }
    }

    pub(crate) fn u16_at(&self, a: usize) -> u16 {
        u16::from_le_bytes([self.vram[a], self.vram[a + 1]])
    }

    fn dispcnt(&self) -> u16 {
        self.io[0]
    }
}

/// A pixel: 0 is transparent, otherwise 0x8000 | BGR555.
type Px = u16;

struct Bg {
    on: bool,
    pri: u8,
    char_base: usize,
    screen_base: usize,
    size: u8,
    hofs: i32,
    vofs: i32,
}

impl Bg {
    fn new(v: &Vid, i: usize) -> Option<Bg> {
        let cnt = v.io[4 + i];
        if cnt & 0x80 != 0 {
            // 256-colour backgrounds are not used by the battle map.
            return None;
        }
        Some(Bg {
            on: v.dispcnt() & (0x100 << i) != 0,
            pri: (cnt & 3) as u8,
            char_base: ((cnt >> 2) & 3) as usize * 0x4000,
            screen_base: ((cnt >> 8) & 31) as usize * 0x800,
            size: (cnt >> 14) as u8,
            hofs: (v.io[8 + 2 * i] & 0x1ff) as i32,
            vofs: (v.io[9 + 2 * i] & 0x1ff) as i32,
        })
    }

    fn plane_w(&self) -> i32 {
        if self.size & 1 != 0 {
            512
        } else {
            256
        }
    }

    fn plane_h(&self) -> i32 {
        if self.size & 2 != 0 {
            512
        } else {
            256
        }
    }

    /// Loads what the layer reads.
    fn load(&self, core: &Core, v: &mut Vid) {
        let screens = match self.size {
            0 => 1,
            1 | 2 => 2,
            _ => 4,
        };
        v.ensure(core, self.screen_base, 0x800 * screens);
        // (tile numbers run to 1023: past the 16 KiB block into the next ones)
        v.ensure(core, self.char_base, 0x8000);
    }

    fn entry(&self, v: &Vid, tx: i32, ty: i32) -> u16 {
        let tx = tx.rem_euclid(self.plane_w() / 8) as usize;
        let ty = ty.rem_euclid(self.plane_h() / 8) as usize;
        let block = match self.size {
            0 => 0,
            1 => tx / 32,
            2 => ty / 32,
            _ => tx / 32 + 2 * (ty / 32),
        };
        v.u16_at(self.screen_base + block * 0x800 + 2 * ((ty % 32) * 32 + tx % 32))
    }

    fn tile_blank(&self, v: &Vid, tile: usize) -> bool {
        let a = self.char_base + 32 * tile;
        a + 32 > 0x18000 || v.vram[a..a + 32].iter().all(|&b| b == 0)
    }

    /// The screen pixels drawn by tiles outside the unit pictures' range
    /// (what is not a unit on the units' layer: a panel the Front view puts there).
    fn foreign(&self, v: &Vid, lo: usize, hi: usize) -> Vec<bool> {
        let mut out = vec![false; W * H];
        let tx0 = self.hofs.div_euclid(8);
        let ty0 = self.vofs.div_euclid(8);
        for ty in ty0..=ty0 + 20 {
            let sy0 = ty * 8 - self.vofs;
            for tx in tx0..=tx0 + 30 {
                let sx0 = tx * 8 - self.hofs;
                let tile = (self.entry(v, tx, ty) & 0x3ff) as usize;
                if (lo..hi).contains(&tile) || self.tile_blank(v, tile) {
                    continue;
                }
                for y in 0..8 {
                    for x in 0..8 {
                        let (sx, sy) = (sx0 + x, sy0 + y);
                        if (0..W as i32).contains(&sx) && (0..H as i32).contains(&sy) {
                            out[sy as usize * W + sx as usize] = true;
                        }
                    }
                }
            }
        }
        out
    }

    /// One pixel of the 8 x 8 tile a tilemap entry names (flips, palette bank).
    pub(crate) fn tile_px(&self, v: &Vid, e: u16, x: usize, y: usize) -> Px {
        let sx = if e & 0x400 != 0 { 7 - x } else { x };
        let sy = if e & 0x800 != 0 { 7 - y } else { y };
        let a = self.char_base + 32 * (e & 0x3ff) as usize + sy * 4 + sx / 2;
        if a >= 0x18000 {
            return 0;
        }
        let b = v.vram[a];
        let c = if sx & 1 == 0 { b & 15 } else { b >> 4 } as usize;
        if c == 0 {
            0
        } else {
            0x8000 | (v.pal[(e >> 12) as usize * 16 + c] & 0x7fff)
        }
    }

    /// One plane pixel (plane coordinates, wrapping).
    fn px(&self, v: &Vid, px: i32, py: i32) -> Px {
        let px = px.rem_euclid(self.plane_w());
        let py = py.rem_euclid(self.plane_h());
        let e = self.entry(v, px / 8, py / 8);
        let mut x = (px % 8) as usize;
        let mut y = (py % 8) as usize;
        if e & 0x400 != 0 {
            x = 7 - x;
        }
        if e & 0x800 != 0 {
            y = 7 - y;
        }
        let a = self.char_base + 32 * (e & 0x3ff) as usize + y * 4 + x / 2;
        if a >= 0x18000 {
            return 0;
        }
        let b = v.vram[a];
        let c = if x & 1 == 0 { b & 15 } else { b >> 4 } as usize;
        if c == 0 {
            0
        } else {
            0x8000 | (v.pal[(e >> 12) as usize * 16 + c] & 0x7fff)
        }
    }

    /// The layer as the screen shows it.
    fn render(&self, v: &Vid, out: &mut [Px]) {
        for px in out.iter_mut() {
            *px = 0;
        }
        let tx0 = self.hofs.div_euclid(8);
        let ty0 = self.vofs.div_euclid(8);
        for ty in ty0..=ty0 + 20 {
            let sy0 = ty * 8 - self.vofs;
            for tx in tx0..=tx0 + 30 {
                let sx0 = tx * 8 - self.hofs;
                let e = self.entry(v, tx, ty);
                let tile = (e & 0x3ff) as usize;
                if self.tile_blank(v, tile) {
                    continue;
                }
                let a = self.char_base + 32 * tile;
                let pb = (e >> 12) as usize * 16;
                for y in 0..8usize {
                    let sy = sy0 + y as i32;
                    if !(0..H as i32).contains(&sy) {
                        continue;
                    }
                    let ry = if e & 0x800 != 0 { 7 - y } else { y };
                    for x in 0..8usize {
                        let sx = sx0 + x as i32;
                        if !(0..W as i32).contains(&sx) {
                            continue;
                        }
                        let rx = if e & 0x400 != 0 { 7 - x } else { x };
                        let b = v.vram[a + ry * 4 + rx / 2];
                        let c = if rx & 1 == 0 { b & 15 } else { b >> 4 } as usize;
                        if c != 0 {
                            out[sy as usize * W + sx as usize] = 0x8000 | (v.pal[pb + c] & 0x7fff);
                        }
                    }
                }
            }
        }
    }
}

// --- Sprites --------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Debug)]
enum Class {
    /// Anything that is not the map's.
    Hud,
    /// An upright thing standing on the map (buildings).
    Billboard,
    /// The cursor's pointer: upright, always in front.
    Pointer,
    /// Lies on the ground (the cursor's corner brackets, the move arrow).
    Ground,
    /// One of the nine 8 x 8 pieces at tiles 666-674 (palette 4): the attack
    /// target's glow beside its crosshair, else the unit that is moving
    /// ([`resolve_groups`]).
    Piece,
}

struct Obj {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    pri: u8,
    idx: usize,
    class: Class,
    pix: Vec<Px>,
    /// The first tile, palette bank and flips it was drawn with.
    tile: u16,
    pal: u8,
    flip: (bool, bool),
}

const OBJ_TILES: usize = 0x10000;
/// The tiles of the units' pictures, digits and marks.
const UNIT_TILES_LO: usize = 0x200;
const UNIT_TILES_HI: usize = 0x360;
/// OBJ tiles below this number hold the properties' sheet (fixed).
const STATIC_SHEET: u16 = 200;
/// What the console drew for each part of a terrain id: its tile, palette and
/// flips, for the map with this signature.
type SpriteCache = (u64, std::collections::HashMap<(u16, u8), (u16, u8, (bool, bool))>);
/// The palette the console draws a fogged property with (once seen).
static FOG_PAL: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(u32::MAX);
static SPRITES: std::sync::LazyLock<std::sync::Mutex<SpriteCache>> =
    std::sync::LazyLock::new(|| std::sync::Mutex::new((0, std::collections::HashMap::new())));


/// The pixels of a sprite picture (0 transparent, else 0x8000 | colour); its
/// tiles are read from the console first.
#[allow(clippy::too_many_arguments)]
fn obj_pixels(
    core: &Core,
    v: &mut Vid,
    one_d: bool,
    tile: usize,
    pal_bank: usize,
    w: i32,
    h: i32,
    hflip: bool,
    vflip: bool,
    color8: bool,
) -> Vec<Px> {
    let (tw, th) = ((w / 8) as usize, (h / 8) as usize);
    for k in 0..tw * th * if color8 { 2 } else { 1 } {
        let t = if one_d { tile + k } else { tile + (k / tw) * 32 + k % tw } & 0x3ff;
        v.ensure(core, OBJ_TILES + t * 32, 32);
    }
    obj_pixels_ro(v, one_d, tile, pal_bank, w, h, hflip, vflip, color8)
}

/// [`obj_pixels`] once the tiles are in.
#[allow(clippy::too_many_arguments)]
fn obj_pixels_ro(
    v: &Vid,
    one_d: bool,
    tile: usize,
    pal_bank: usize,
    w: i32,
    h: i32,
    hflip: bool,
    vflip: bool,
    color8: bool,
) -> Vec<Px> {
    let (tw, th) = ((w / 8) as usize, (h / 8) as usize);
    let mut pix = vec![0u16; (w * h) as usize];
    for ty in 0..th {
        for tx in 0..tw {
            let src_tx = if hflip { tw - 1 - tx } else { tx };
            let src_ty = if vflip { th - 1 - ty } else { ty };
            let step = if color8 { 2 } else { 1 };
            let mut t = if one_d {
                tile + src_ty * tw * step + src_tx * step
            } else {
                tile + src_ty * 32 + src_tx * step
            };
            t &= 0x3ff;
            let bytes = if color8 { 64 } else { 32 };
            let addr = OBJ_TILES + t * 32;
            if addr + bytes > 0x18000 {
                continue;
            }
            for py in 0..8usize {
                for pxl in 0..8usize {
                    let (sx, sy) = (if hflip { 7 - pxl } else { pxl }, if vflip { 7 - py } else { py });
                    let c = if color8 {
                        v.vram[addr + sy * 8 + sx] as usize
                    } else {
                        let b = v.vram[addr + sy * 4 + sx / 2];
                        (if sx & 1 == 0 { b & 15 } else { b >> 4 }) as usize
                    };
                    if c != 0 {
                        let color = if color8 { v.pal[256 + c] } else { v.pal[256 + pal_bank * 16 + c] };
                        pix[(ty * 8 + py) * w as usize + tx * 8 + pxl] = 0x8000 | (color & 0x7fff);
                    }
                }
            }
        }
    }
    pix
}


/// The nine pieces at tiles 666-674 are a target's glow (flat on the ground)
/// when the crosshair is up, else the unit that is moving (one upright
/// picture, drawn where it is as it goes).
fn resolve_groups(mut objs: Vec<Obj>) -> Vec<Obj> {
    let targeting = objs.iter().any(|o| o.class == Class::Ground && (884..=895).contains(&o.tile));
    if targeting {
        for o in objs.iter_mut().filter(|o| o.class == Class::Piece) {
            o.class = Class::Ground;
        }
        return objs;
    }
    let (pieces, mut rest): (Vec<Obj>, Vec<Obj>) = objs.into_iter().partition(|o| o.class == Class::Piece);
    if pieces.is_empty() {
        return rest;
    }
    let (x0, y0) = (pieces.iter().map(|o| o.x).min().unwrap(), pieces.iter().map(|o| o.y).min().unwrap());
    let (x1, y1) = (
        pieces.iter().map(|o| o.x + o.w).max().unwrap(),
        pieces.iter().map(|o| o.y + o.h).max().unwrap(),
    );
    let (w, h) = (x1 - x0, y1 - y0);
    let mut pix = vec![0u16; (w * h) as usize];
    for o in pieces.iter().rev() {
        for y in 0..o.h {
            for x in 0..o.w {
                let p = o.pix[(y * o.w + x) as usize];
                if p != 0 {
                    pix[((o.y - y0 + y) * w + o.x - x0 + x) as usize] = p;
                }
            }
        }
    }
    let first = pieces.iter().min_by_key(|o| o.idx).unwrap();
    rest.push(Obj {
        x: x0,
        y: y0,
        w,
        h,
        pri: first.pri,
        idx: first.idx,
        class: Class::Billboard,
        pix,
        tile: first.tile,
        pal: first.pal,
        flip: first.flip,
    });
    rest
}

fn obj_class(a0: u16, a2: u16, w: i32, h: i32) -> Class {
    let mode = (a0 >> 10) & 3;
    let pri = (a2 >> 10) & 3;
    let tile = a2 & 0x3ff;
    let pal = a2 >> 12;
    if mode != 0 {
        return Class::Hud;
    }
    match (w, h, tile) {
        (16, 16, 869) => Class::Pointer,
        (8, 8, 873) => Class::Ground,
        // The attack target's glow (3 x 3 pieces of 8 x 8, palette 4) and its
        // crosshair (four 16 x 16 pieces).
        (8, 8, 666..=674) if pal == 4 => Class::Piece,
        (16, 16, 884..=895) if pal == 1 => Class::Ground,
        // The move arrow (palette 3, 16 x 16 pieces).
        (16, 16, _) if pal == 3 && pri == 0 => Class::Ground,
        _ if pri == 3 => Class::Billboard,
        _ => Class::Hud,
    }
}

/// The sprites that show, or `None` when one is affine (not handled: the
/// frame is left alone).
fn read_objs(core: &Core, v: &mut Vid) -> Option<Vec<Obj>> {
    let one_d = v.dispcnt() & 0x40 != 0;
    let mut out = Vec::new();
    for idx in 0..128 {
        let a0 = v.oam[4 * idx];
        let a1 = v.oam[4 * idx + 1];
        let a2 = v.oam[4 * idx + 2];
        if a0 & 0x100 != 0 {
            // An affine sprite is not handled: the frame is left alone
            // (unless it is parked off screen).
            let y = a0 & 255;
            if !(160..224).contains(&y) {
                return None;
            }
            continue;
        }
        if a0 & 0x200 != 0 {
            continue;
        }
        let shape = (a0 >> 14) as usize;
        let size = (a1 >> 14) as usize;
        if shape == 3 {
            continue;
        }
        const DIMS: [[(i32, i32); 4]; 3] = [
            [(8, 8), (16, 16), (32, 32), (64, 64)],
            [(16, 8), (32, 8), (32, 16), (64, 32)],
            [(8, 16), (8, 32), (16, 32), (32, 64)],
        ];
        let (w, h) = DIMS[shape][size];
        let mut y = (a0 & 255) as i32;
        if y >= 160 {
            y -= 256;
        }
        let mut x = (a1 & 511) as i32;
        if x >= 240 {
            x -= 512;
        }
        if x + w <= 0 || y + h <= 0 || x >= W as i32 || y >= H as i32 {
            continue;
        }
        if (a0 >> 10) & 3 == 2 {
            // OBJ window: no picture.
            continue;
        }
        let color8 = a0 & 0x2000 != 0;
        let pix = obj_pixels(core, v, one_d, (a2 & 0x3ff) as usize, (a2 >> 12) as usize, w, h, a1 & 0x1000 != 0, a1 & 0x2000 != 0, color8);
        out.push(Obj {
            x,
            y,
            w,
            h,
            pri: ((a2 >> 10) & 3) as u8,
            idx,
            class: obj_class(a0, a2, w, h),
            pix,
            tile: a2 & 0x3ff,
            pal: (a2 >> 12) as u8,
            flip: (a1 & 0x1000 != 0, a1 & 0x2000 != 0),
        });
    }
    Some(resolve_groups(out))
}

// --- Compositing ----------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum Owner {
    /// The tilted map replaces the pixel.
    Map,
    /// The tilted map, darkened or lightened as the window effect does.
    MapFx,
    /// Keep the console's pixel.
    Hud,
}

struct Windows {
    on: [bool; 2],
    /// x1, x2, y1, y2 of each.
    rect: [[i32; 4]; 2],
    inside: [u8; 2],
    outside: u8,
}

impl Windows {
    fn new(v: &Vid) -> Windows {
        let d = v.dispcnt();
        let mut rect = [[0; 4]; 2];
        for i in 0..2 {
            let h = v.io[0x20 + i];
            let vv = v.io[0x22 + i];
            rect[i] = [(h >> 8) as i32, (h & 255) as i32, (vv >> 8) as i32, (vv & 255) as i32];
        }
        Windows {
            on: [d & 0x2000 != 0, d & 0x4000 != 0],
            rect,
            inside: [v.io[0x24] as u8 & 0x3f, (v.io[0x24] >> 8) as u8 & 0x3f],
            outside: v.io[0x25] as u8 & 0x3f,
        }
    }

    fn any(&self) -> bool {
        self.on[0] || self.on[1]
    }

    fn contains(&self, i: usize, x: i32, y: i32) -> bool {
        let r = self.rect[i];
        let xin = if r[0] <= r[1] {
            x >= r[0] && x < r[1]
        } else {
            x >= r[0] || x < r[1]
        };
        let yin = if r[2] <= r[3] {
            y >= r[2] && y < r[3]
        } else {
            y >= r[2] || y < r[3]
        };
        xin && yin
    }

    /// Layer-enable bits (BG0-3, OBJ, effects) at a pixel.
    fn bits(&self, x: i32, y: i32) -> u8 {
        if !self.any() {
            return 0x3f;
        }
        for i in 0..2 {
            if self.on[i] && self.contains(i, x, y) {
                return self.inside[i];
            }
        }
        self.outside
    }
}

/// Dual Strike's way of showing a range: the cells in it light up (red where
/// the console's tint is a reddish one: an attack range) and the rest of the
/// ground dims. `t` is the console's tint pixel there (0: none).
fn range_look(p: Px, t: Px) -> Px {
    let ch = |c: Px, s: u32| (c as u32 >> s) & 31;
    let (mut r, mut g, mut b) = (ch(p, 0), ch(p, 5), ch(p, 10));
    if t == 0 {
        (r, g, b) = (r * 3 / 4, g * 3 / 4, b * 3 / 4);
    } else {
        let target = if ch(t, 0) > ch(t, 10) + 5 { (31, 14, 14) } else { (31, 31, 31) };
        r = (r * 9 + target.0 * 11) / 20;
        g = (g * 9 + target.1 * 11) / 20;
        b = (b * 9 + target.2 * 11) / 20;
    }
    0x8000 | (r | g << 5 | b << 10) as u16
}

fn brightness(a: Px, mode: u16, evy: u32) -> Px {
    let ch = |s: u32| {
        let x = (a as u32 >> s) & 31;
        if mode == 3 {
            x - (x * evy >> 4)
        } else {
            x + ((31 - x) * evy >> 4)
        }
    };
    0x8000 | (ch(0) | ch(5) << 5 | ch(10) << 10) as u16
}

pub(crate) fn rgba_lut() -> &'static Vec<[u8; 4]> {
    static LUT: OnceLock<Vec<[u8; 4]>> = OnceLock::new();
    LUT.get_or_init(|| {
        let mut src = vec![0u8; 0x8000 * 2];
        for i in 0..0x8000usize {
            src[2 * i..2 * i + 2].copy_from_slice(&(i as u16).to_le_bytes());
        }
        let mut dst = vec![0u8; 0x8000 * 4];
        mgba::gba::bgr555_to_rgba8(&src, &mut dst);
        dst.chunks_exact(4).map(|c| [c[0], c[1], c[2], c[3]]).collect()
    })
}

struct Billboard {
    pix: Vec<Px>,
    w: i32,
    h: i32,
    /// The ground point it stands on, in cells.
    fu: f32,
    fv: f32,
    /// Top-left of the picture relative to the foot, in source pixels (16 a cell).
    ox: f32,
    oy: f32,
    /// Draw order among equal depths: higher is in front.
    rank: u8,
    last: bool,
}

/// Rewrites `rgba` (the console's 240 x 160 picture) as Dual Strike's tilted
/// battle map, when that is what is on screen. Nothing else changes.
pub fn apply(core: &Core, rgba: &mut [u8]) {
    // A picture that goes wrong must never take the game down: the frame is
    // left as the console drew it and the tilt stays off for the session.
    static FAILED: AtomicBool = AtomicBool::new(false);
    if !enabled() || FAILED.load(Ordering::Relaxed) {
        return;
    }
    let before = rgba.to_vec();
    if std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| apply_timed(core, rgba))).is_err() {
        FAILED.store(true, Ordering::Relaxed);
        rgba.copy_from_slice(&before);
        eprintln!("ds_tilt: failed; the tilt is off for this session");
    }
}

fn apply_timed(core: &Core, rgba: &mut [u8]) {
    static TIME: OnceLock<bool> = OnceLock::new();
    if env_on("TANGOAW2_TILT_TIME", &TIME) {
        let t = std::time::Instant::now();
        apply_inner(core, rgba);
        static STATS: std::sync::Mutex<(u128, u32)> = std::sync::Mutex::new((0, 0));
        let mut st = STATS.lock().unwrap();
        st.0 += t.elapsed().as_nanos();
        st.1 += 1;
        if st.1 % 1 == 0 {
            eprintln!(
                "ds_tilt: {} us per frame (mean of {})",
                st.0 / st.1 as u128 / 1000,
                st.1
            );
        }
    } else {
        apply_inner(core, rgba);
    }
}

fn apply_inner(core: &Core, rgba: &mut [u8]) {
    if !enabled() || rgba.len() != W * H * 4 {
        return;
    }
    if core.raw_read_32(MAIN_LOOP, -1) != BATTLE_MAIN || !crate::wasteland::ds_graphics(core) {
        return;
    }
    let t0 = std::time::Instant::now();
    let mut v = Vid::read(core);
    let t_read = t0.elapsed();
    let d = v.dispcnt();
    // A picture drawn with changes between its lines (HBlank interrupts on:
    // the dialogue box over the map's top) is not one this can redo.
    if v.io[2] & 0x10 != 0 {
        return;
    }
    // Tile mode 0, display on, BG1-3 and OBJ on.
    if d & 7 != 0 || d & 0x80 != 0 || d & 0x0e00 != 0x0e00 || d & 0x1000 == 0 {
        return;
    }
    let (Some(bgs0), Some(bgs1), Some(bgs2), Some(bgs3)) =
        (Bg::new(&v, 0), Bg::new(&v, 1), Bg::new(&v, 2), Bg::new(&v, 3))
    else {
        return;
    };
    let bgs = [bgs0, bgs1, bgs2, bgs3];
    let win = Windows::new(&v);
    let bldcnt = v.io[0x28];
    let bldy = v.io[0x2a];
    let bld_mode = (bldcnt >> 6) & 3;
    // A fade over everything is not ours to redo.
    if (bld_mode >= 2 && (!win.any() || win.outside & 0x20 != 0)) || v.io[0x26] & 0xff != 0 {
        return;
    }
    for bg in &bgs {
        if bg.on {
            bg.load(core, &mut v);
        }
    }
    let t_load = t0.elapsed();
    let Some(objs) = read_objs(core, &mut v) else {
        return;
    };
    let t_objs = t0.elapsed();

    // BG0 is the range overlay while it is below the units.
    let bg0_ground = bgs[0].on && bgs[0].pri > bgs[1].pri;
    let class_of_bg = |i: usize| -> Owner {
        match i {
            0 => {
                if bg0_ground {
                    Owner::Map
                } else {
                    Owner::Hud
                }
            }
            _ => Owner::Map,
        }
    };

    // Flat layers.
    let mut layers: Vec<Vec<Px>> = Vec::with_capacity(4);
    for bg in &bgs {
        let mut l = vec![0u16; W * H];
        if bg.on {
            bg.render(&v, &mut l);
        }
        layers.push(l);
    }
    // Anything on the units' layer that is not a unit stays the HUD's.
    let foreign2 = if bgs[2].on { bgs[2].foreign(&v, 0, 0x361) } else { Vec::new() };
    let foreign1 = if bgs[1].on { bgs[1].foreign(&v, UNIT_TILES_LO, UNIT_TILES_HI) } else { Vec::new() };
    let t_layers = t0.elapsed();
    // Top sprite per pixel: (priority, index) lowest wins.
    let mut obj_top: Vec<u32> = vec![u32::MAX; W * H];
    let mut obj_color: Vec<Px> = vec![0; W * H];
    let mut class_of_obj = [Class::Hud; 128];
    for o in &objs {
        class_of_obj[o.idx] = o.class;
        let key = (o.pri as u32) << 8 | o.idx as u32;
        for y in 0..o.h {
            let sy = o.y + y;
            if !(0..H as i32).contains(&sy) {
                continue;
            }
            for x in 0..o.w {
                let sx = o.x + x;
                if !(0..W as i32).contains(&sx) {
                    continue;
                }
                let p = o.pix[(y * o.w + x) as usize];
                if p == 0 {
                    continue;
                }
                let i = sy as usize * W + sx as usize;
                if key < obj_top[i] {
                    obj_top[i] = key;
                    obj_color[i] = p;
                }
            }
        }
    }

    let t_objtop = t0.elapsed();
    // Who is on top, per pixel. Everything starts as the map's; the HUD's
    // sprites and (when it is HUD) BG0 claim the pixels where they are on top.
    let owner_of_bg = [class_of_bg(0), class_of_bg(1), class_of_bg(2), class_of_bg(3)];
    let any_win = win.any();
    let bits_at = |x: i32, y: i32| if any_win { win.bits(x, y) } else { 0x3f };
    let mut owner = vec![Owner::Map; W * H];
    for o in objs.iter().filter(|o| o.class == Class::Hud) {
        let key = (o.pri as u32) << 8 | o.idx as u32;
        for y in 0..o.h {
            let sy = o.y + y;
            if !(0..H as i32).contains(&sy) {
                continue;
            }
            for x in 0..o.w {
                let sx = o.x + x;
                if !(0..W as i32).contains(&sx) || o.pix[(y * o.w + x) as usize] == 0 {
                    continue;
                }
                let i = sy as usize * W + sx as usize;
                let bits = bits_at(sx, sy);
                // (a sprite the window hides, or one under another sprite)
                if bits & 0x10 == 0 || obj_top[i] != key {
                    continue;
                }
                let covered =
                    (1..4).any(|b| bgs[b].on && bits & (1 << b) != 0 && bgs[b].pri < o.pri && layers[b][i] != 0);
                if !covered {
                    owner[i] = Owner::Hud;
                }
            }
        }
    }
    if bgs[0].on && !bg0_ground {
        for i in 0..W * H {
            if layers[0][i] == 0 {
                continue;
            }
            let (x, y) = ((i % W) as i32, (i / W) as i32);
            let bits = bits_at(x, y);
            if bits & 1 == 0 {
                continue;
            }
            let obj = if bits & 0x10 != 0 { obj_top[i] } else { u32::MAX };
            let sprite_above = obj != u32::MAX && ((obj >> 8) as u8) <= bgs[0].pri;
            let bg_above =
                (1..4).any(|b| bgs[b].on && bits & (1 << b) != 0 && bgs[b].pri < bgs[0].pri && layers[b][i] != 0);
            if !sprite_above && !bg_above {
                owner[i] = Owner::Hud;
            }
        }
    }
    for (fb, fm) in [(1usize, &foreign1), (2usize, &foreign2)] {
    if !fm.is_empty() {
        for i in 0..W * H {
            if fm[i] && layers[fb][i] != 0 {
                let (x, y) = ((i % W) as i32, (i / W) as i32);
                let bits = bits_at(x, y);
                if bits & (1 << fb) == 0 {
                    continue;
                }
                let obj = if bits & 0x10 != 0 { obj_top[i] } else { u32::MAX };
                let sprite_above = obj != u32::MAX && ((obj >> 8) as u8) <= bgs[fb].pri;
                let bg_above = [0usize, 1, 2, 3].iter().filter(|&&b| b != fb).any(|&b| {
                    bgs[b].on && bits & (1 << b) != 0 && layers[b][i] != 0 && (bgs[b].pri, b) < (bgs[fb].pri, fb)
                });
                if !sprite_above && !bg_above {
                    owner[i] = Owner::Hud;
                }
            }
        }
    }
    }
    // A window effect on the pixel.
    if any_win && bld_mode != 0 {
        for wi in 0..2 {
            if !win.on[wi] || win.inside[wi] & 0x20 == 0 {
                continue;
            }
            let r = win.rect[wi];
            let (x0, x1, y0, y1) = if r[0] <= r[1] && r[2] <= r[3] {
                (r[0].max(0), r[1].min(W as i32), r[2].max(0), r[3].min(H as i32))
            } else {
                (0, W as i32, 0, H as i32)
            };
            for y in y0..y1 {
                for x in x0..x1 {
                    let i = y as usize * W + x as usize;
                    if owner[i] == Owner::Map && win.bits(x, y) & 0x20 != 0 {
                        owner[i] = if bld_mode >= 2 { Owner::MapFx } else { Owner::Hud };
                    }
                }
            }
        }
    }
    let backdrop = 0x8000 | (v.pal[0] & 0x7fff);

    if debug_check() {
        // The hardware's rules replayed pixel by pixel, against the console's
        // picture (where nothing blends) and against the owner map above.
        let lut = rgba_lut();
        let mut order: Vec<usize> = (0..4).filter(|&b| bgs[b].on).collect();
        order.sort_by_key(|&b| (bgs[b].pri, b));
        let (mut bad_color, mut bad_owner) = (0, 0);
        for i in 0..W * H {
            let bits = bits_at((i % W) as i32, (i / W) as i32);
            let obj = if bits & 0x10 != 0 { obj_top[i] } else { u32::MAX };
            let obj_pri = if obj == u32::MAX { 9 } else { (obj >> 8) as u8 };
            let mut who = Owner::Map;
            let mut color = backdrop;
            let mut found = false;
            for &b in &order {
                if bits & (1 << b) == 0 || layers[b][i] == 0 {
                    continue;
                }
                if obj_pri <= bgs[b].pri {
                    break;
                }
                who = owner_of_bg[b];
                color = layers[b][i];
                found = true;
                break;
            }
            if !found && obj != u32::MAX {
                who = if class_of_obj[(obj & 0xff) as usize] == Class::Hud {
                    Owner::Hud
                } else {
                    Owner::Map
                };
                color = obj_color[i];
            }
            let fx = bits & 0x20 != 0 && bld_mode != 0;
            if !fx && who != owner[i] {
                bad_owner += 1;
            }
            if !fx && bld_mode != 1 {
                let want = lut[(color & 0x7fff) as usize];
                if rgba[i * 4..i * 4 + 3] != want[..3] {
                    bad_color += 1;
                }
            }
        }
        if bad_color > 0 || bad_owner > 0 {
            eprintln!(
                "ds_tilt: {} pixels differ from the console's picture, {} owners differ",
                bad_color, bad_owner
            );
        }
    }

    let t_owner = t0.elapsed();
    // --- The camera and the ground ---
    Ground::load(core, &mut v);
    v.ensure(core, OBJ_TILES, 0x8000);
    let Some(mut ground) = Ground::new(core, &v) else {
        return;
    };
    let cam_px = (
        core.raw_read_16(MAP + 4, -1) as i16 as i32,
        core.raw_read_16(MAP + 6, -1) as i16 as i32,
    );
    // Dual Strike's camera follows the cursor with a dead zone and keeps the
    // map's edge in view (fitted to melonDS frames, see the module notes).
    let cursor = (
        core.raw_read_8(CURSOR_X, -1) as i32,
        core.raw_read_8(CURSOR_Y, -1) as i32,
    );
    let (fx, fy) = follow(cursor, ground.w, ground.h);
    let cam = Cam::new(fx + CAM_BIAS.0, fy + CAM_BIAS.1);

    // What lies on the ground, as the console shows it: BG0's range tint
    // (while it is below the units) and the sprites that lie flat.
    let mut decal = vec![0u16; W * H];
    for o in objs.iter().filter(|o| o.class == Class::Ground) {
        for y in 0..o.h {
            let sy = o.y + y;
            if !(0..H as i32).contains(&sy) {
                continue;
            }
            for x in 0..o.w {
                let sx = o.x + x;
                let p = o.pix[(y * o.w + x) as usize];
                if p != 0 && (0..W as i32).contains(&sx) {
                    decal[sy as usize * W + sx as usize] = p;
                }
            }
        }
    }
    let tint = bg0_ground.then_some(());
    // The cells the selected unit can reach (the game's own table: the steps
    // it costs, 0xFF where it cannot): known beyond the console's window,
    // where BG0 is not drawn.
    let reach: Vec<u8> = if tint.is_some() {
        (0..ground.w * ground.h)
            .map(|i| {
                let (x, y) = (i % ground.w, i / ground.w);
                let row = core.raw_read_16(MAP + 0x417A + 2 * y as u32, -1) as u32;
                core.raw_read_8(REACH + row + x as u32, -1)
            })
            .collect()
    } else {
        Vec::new()
    };

    // The ground drawn from the map's RAM must be the console's BG3 (with the
    // peaks over it) where that shows; when it is not (a scroll, a fade or a
    // scene change in progress) the frame is left as the console drew it.
    {
        let mut bad = 0;
        let mut seen = 0;
        for y in (0..H as i32).step_by(3) {
            for x in (0..W as i32).step_by(3) {
                let i = y as usize * W + x as usize;
                if layers[3][i] == 0 || layers[2][i] != 0 {
                    continue;
                }
                seen += 1;
                if ground.px(cam_px.0 + x, cam_px.1 + y) != layers[3][i] {
                    bad += 1;
                }
            }
        }
        if debug_check() && bad > 0 {
            eprintln!("ds_tilt: ground from RAM differs from BG3 at {} of {} sampled pixels", bad, seen);
        }
        if bad * 12 > seen {
            return;
        }
    }

    // --- Billboards ---
    let mut boards: Vec<Billboard> = Vec::new();
    // A cell of the console's plane is map cell (camx / 16 + cell - scroll / 16).
    let (map_x0, map_y0) = (cam_px.0.div_euclid(16), cam_px.1.div_euclid(16));
    let ground_cx0 = bgs[3].hofs.div_euclid(16);
    let ground_cy0 = bgs[3].vofs.div_euclid(16);
    for b in [1usize, 2] {
        let bg = &bgs[b];
        if !bg.on {
            continue;
        }
        let cx0 = bg.hofs.div_euclid(16);
        let cy0 = bg.vofs.div_euclid(16);
        for cy in cy0 - 1..=cy0 + 10 {
            for cx in cx0 - 1..=cx0 + 15 {
                // A cell with something else on it is not a unit's.
                if (b == 1 || b == 2) && {
                    let (sx0, sy0) = (cx * 16 - bg.hofs, cy * 16 - bg.vofs);
                    let fm = if b == 1 { &foreign1 } else { &foreign2 };
                    (0..16).any(|k| {
                        let (x, y) = (sx0 + k, sy0 + k);
                        (0..W as i32).contains(&x) && (0..H as i32).contains(&y) && fm[y as usize * W + x as usize]
                    }) || b == 1 && (0..4).any(|k| {
                        let e = bg.entry(&v, cx * 2 + k % 2, cy * 2 + k / 2);
                        let t = (e & 0x3ff) as usize;
                        !bg.tile_blank(&v, t) && !(UNIT_TILES_LO..UNIT_TILES_HI).contains(&t)
                    })
                } {
                    continue;
                }
                // Anything in the cell? (Its four tiles.)
                if (0..4).all(|k| {
                    let e = bg.entry(&v, cx * 2 + k % 2, cy * 2 + k / 2);
                    bg.tile_blank(&v, (e & 0x3ff) as usize)
                }) {
                    continue;
                }
                let (sx0, sy0) = (cx * 16 - bg.hofs, cy * 16 - bg.vofs);
                if sx0 + 16 <= 0 || sy0 + 16 <= 0 || sx0 >= W as i32 || sy0 >= H as i32 {
                    // (not in view: the console does not keep that part of its plane current)
                    continue;
                }
                let inside = sx0 >= 0 && sy0 >= 0 && sx0 + 16 <= W as i32 && sy0 + 16 <= H as i32;
                let mut pix = vec![0u16; 256];
                let mut any = false;
                for y in 0..16 {
                    for x in 0..16 {
                        let p = if inside {
                            layers[b][(sy0 + y) as usize * W + (sx0 + x) as usize]
                        } else {
                            bg.px(&v, cx * 16 + x, cy * 16 + y)
                        };
                        any |= p != 0;
                        pix[(y * 16 + x) as usize] = p;
                    }
                }
                if !any {
                    continue;
                }
                // The map cell it stands in, and where the console draws that cell's foot.
                let (mx, my) = (map_x0 + cx - ground_cx0, map_y0 + cy - ground_cy0);
                let foot_x = (mx * 16 - cam_px.0 + 8) as f32;
                let foot_y = (my * 16 - cam_px.1 + 16) as f32;
                // Units stand a little in front of the edge; the peaks and
                // treetops (BG2) stand on it.
                let drop = if b == 1 { FOOT_DROP } else { 0.0 };
                boards.push(Billboard {
                    pix,
                    w: 16,
                    h: 16,
                    fu: mx as f32 + 0.5,
                    fv: my as f32 + 1.0 + drop,
                    ox: sx0 as f32 - foot_x,
                    oy: sy0 as f32 - foot_y,
                    rank: (3 - bg.pri) * 2,
                    last: false,
                });
            }
        }
    }
    // Units beyond the console's window, from the game's own records: the
    // console draws only the cells it shows. A unit is drawn as the console
    // draws it (the first tile of its picture by type and country, mirrored
    // for armies 1 and 3, in its army's palette, greyed once it has moved, the
    // HP digit or the cargo mark in the corner), where its cell is in view.
    if debug_check() && bgs[1].on {
        // The units' records against what the console drew, in its window.
        let mut cells = std::collections::HashMap::new();
        for u in ram_units(core) {
            if u.flags & 0x0e == 0 {
                cells.insert((u.x as i32, u.y as i32), u);
            }
        }
        let mut bad = 0;
        for my in map_y0..=map_y0 + 9 {
            for mx in map_x0..=map_x0 + 14 {
                if mx < 0 || my < 0 || mx >= ground.w || my >= ground.h {
                    continue;
                }
                let got: Vec<u16> = (0..4)
                    // (the console's plane cell of a map cell: its place in the window
                        // plus where the plane's scroll puts the window)
                        .map(|k| {
                            bgs[1].entry(
                                &v,
                                2 * ((mx - map_x0 + ground_cx0) & 15) + k % 2,
                                2 * ((my - map_y0 + ground_cy0) & 15) + k / 2,
                            )
                        })
                    .collect();
                let drawn = got.iter().any(|&e| !bgs[1].tile_blank(&v, (e & 0x3ff) as usize));
                let want = cells.get(&(mx, my)).filter(|_| !ground.fogged(mx, my)).and_then(|u| u.entries());
                let ok = match (drawn, want) {
                    (false, None) => true,
                    (true, Some(w)) => w.iter().zip(&got).all(|(a, b)| a == b),
                    _ => false,
                };
                if !ok {
                    bad += 1;
                    if bad <= 6 {
                        eprintln!(
                            "ds_tilt: unit at ({}, {}): console {:03x?} ({}), records {:03x?} (record {}, fog {}) {}",
                            mx,
                            my,
                            got,
                            drawn,
                            want,
                            cells.contains_key(&(mx, my)),
                            ground.fogged(mx, my),
                            cells
                                .get(&(mx, my))
                                .map(|u| format!("kind {} flags {:02x} hp {} army {} colour {} country {} raw {:02x?}", u.kind, u.flags, u.hp, u.army, u.colour, u.country, u.raw))
                                .unwrap_or_default()
                        );
                    }
                }
            }
        }
        if bad > 0 {
            eprintln!("ds_tilt: {} cells where the units' records and the console's picture differ", bad);
        }
    }
    if bgs[1].on {
        let seen: std::collections::HashSet<(i32, i32)> = boards
            .iter()
            .filter(|b| !b.last && b.rank == (3 - bgs[1].pri) * 2)
            .map(|b| ((b.fu - 0.5) as i32, (b.fv - 1.0 - FOOT_DROP).round() as i32 - 0))
            .collect();
        let (win_x, win_y) = (map_x0..=map_x0 + 15, map_y0..=map_y0 + 10);
        let bob = {
            let d = (bgs[1].vofs - bgs[3].vofs).rem_euclid(512);
            if d < 16 { d } else { 0 }
        };
        for u in ram_units(core) {
            let (ux, uy) = (u.x as i32, u.y as i32);
            if win_x.contains(&ux) && win_y.contains(&uy) || seen.contains(&(ux, uy)) {
                continue;
            }
            if ux >= ground.w || uy >= ground.h || ground.fogged(ux, uy) || u.flags & 0x0e != 0 {
                continue;
            }
            let Some(entries) = u.entries() else { continue };
            let mut pix = vec![0u16; 256];
            for (k, &e) in entries.iter().enumerate() {
                for py in 0..8usize {
                    for px in 0..8usize {
                        pix[((k / 2) * 8 + py) * 16 + (k % 2) * 8 + px] = bgs[1].tile_px(&v, e, px, py);
                    }
                }
            }
            boards.push(Billboard {
                pix,
                w: 16,
                h: 16,
                fu: ux as f32 + 0.5,
                fv: uy as f32 + 1.0 + FOOT_DROP,
                ox: -8.0,
                oy: -16.0 - bob as f32,
                rank: (3 - bgs[1].pri) * 2,
                last: false,
            });
        }
    }
    // Buildings and structures beyond the console's window, from the map's
    // tile ids and the sprite parts the console draws for each (`ds_plans`).
    // Where a part sits is the same everywhere; which tiles and palette hold
    // its picture is, for the structures, the mission's (the console gives them
    // their slots as it loads the mission), so those are learned from the
    // console's own sprites whenever one is in its window.
    {
        let one_d = d & 0x40 != 0;
        let (win_x, win_y) = (map_x0..=map_x0 + 15, map_y0..=map_y0 + 10);
        let mut cache = SPRITES.lock().unwrap();
        let sig = ground.signature();
        if cache.0 != sig {
            *cache = (sig, std::collections::HashMap::new());
        }
        // Learn.
        for my in win_y.clone() {
            for mx in win_x.clone() {
                if mx < 0 || my < 0 || mx >= ground.w || my >= ground.h {
                    continue;
                }
                let t = ground.tile(mx, my);
                let Ok(i) = crate::ds_plans::PLANS.binary_search_by_key(&t, |p| p.0) else {
                    continue;
                };
                for (k, &(dx, dy, w, h, _, _, _, _)) in crate::ds_plans::PLANS[i].1.iter().enumerate() {
                    let (px, py) = (mx * 16 - cam_px.0 + dx as i32, my * 16 - cam_px.1 + dy as i32);
                    if let Some(o) = objs.iter().find(|o| {
                        o.class == Class::Billboard && (o.x, o.y, o.w, o.h) == (px, py, w as i32, h as i32)
                    }) {
                        cache.1.insert((t, k as u8), (o.tile, o.pal, o.flip));
                        // (a fogged property is drawn in another palette: learn it)
                        if ground.fogged(mx, my) && o.tile < STATIC_SHEET as u16 {
                            FOG_PAL.store(o.pal as u32, Ordering::Relaxed);
                        }
                    }
                }
            }
        }
        // Draw.
        let (rl, rr, rt, rb) = cam.reach();
        let (x_lo, x_hi) = ((cam.cu - rl).floor() as i32 - 4, (cam.cu + rr).ceil() as i32 + 1);
        let (y_lo, y_hi) = ((cam.cv - rt).floor() as i32 - 1, (cam.cv + rb).ceil() as i32 + 4);
        for my in y_lo.max(0)..y_hi.min(ground.h) {
            for mx in x_lo.max(0)..x_hi.min(ground.w) {
                if win_x.contains(&mx) && win_y.contains(&my) {
                    continue;
                }
                let t = ground.tile(mx, my);
                let Ok(i) = crate::ds_plans::PLANS.binary_search_by_key(&t, |p| p.0) else {
                    continue;
                };
                for (k, &(dx, dy, w, h, tile, pal, hf, vf)) in crate::ds_plans::PLANS[i].1.iter().enumerate() {
                    let (w, h) = (w as i32, h as i32);
                    // The properties' sheet is fixed; a structure's picture is
                    // known once the console has drawn one.
                    let (tile, pal, (hf, vf)) = if tile < STATIC_SHEET {
                        let fp = FOG_PAL.load(Ordering::Relaxed);
                        if ground.fogged(mx, my) && fp != u32::MAX {
                            (tile, fp as _, (hf, vf))
                        } else {
                            (tile, pal, (hf, vf))
                        }
                    } else if let Some(&(tl, pl, fl)) = cache.1.get(&(t, k as u8)) {
                        (tl, pl, fl)
                    } else {
                        continue;
                    };
                    let pix = obj_pixels_ro(&v, one_d, tile as usize, pal as usize, w, h, hf, vf, false);
                    if pix.iter().all(|&p| p == 0) {
                        continue;
                    }
                    boards.push(Billboard {
                        pix,
                        w,
                        h,
                        fu: mx as f32 + (dx as f32 + w as f32 / 2.0) / 16.0,
                        fv: my as f32 + (dy as f32 + h as f32) / 16.0 + FOOT_DROP,
                        ox: -(w as f32) / 2.0,
                        oy: -(h as f32),
                        rank: 1,
                        last: false,
                    });
                }
            }
        }
    }
    for o in objs
        .iter()
        .filter(|o| matches!(o.class, Class::Billboard | Class::Pointer))
    {
        let fx = o.x as f32 + o.w as f32 / 2.0;
        let fy = (o.y + o.h) as f32;
        boards.push(Billboard {
            pix: o.pix.clone(),
            w: o.w,
            h: o.h,
            fu: (cam_px.0 as f32 + fx) / 16.0,
            fv: (cam_px.1 as f32 + fy) / 16.0 + if o.class == Class::Billboard { FOOT_DROP } else { 0.0 },
            ox: -(o.w as f32) / 2.0,
            oy: -(o.h as f32),
            rank: (3 - o.pri) * 2 + 1,
            last: o.class == Class::Pointer,
        });
    }
    boards.sort_by(|a, b| {
        (a.last, a.fv, a.rank)
            .partial_cmp(&(b.last, b.fv, b.rank))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let t_boards = t0.elapsed();
    // --- Cloud shadows ---
    // Dual Strike lays soft darker patches (about 5 cells across, 10% darker)
    // over its ground that drift slowly. Display only: the drift counts the
    // pictures shown.
    static CLOCK: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
    let clock = CLOCK.fetch_add(1, Ordering::Relaxed) as f32;
    const SHADOW_STEP: f32 = 0.25;
    let (rl, rr, rt, rb) = cam.reach();
    let (su0, sv0) = ((cam.cu - rl - 1.0).floor(), (cam.cv - rt - 1.0).floor());
    let (sw, sh) = (((rl + rr + 2.0) / SHADOW_STEP) as usize + 4, ((rt + rb + 2.0) / SHADOW_STEP) as usize + 4);
    let mut shadow = vec![0f32; sw * sh];
    for j in 0..sh {
        let v = sv0 + j as f32 * SHADOW_STEP;
        for i in 0..sw {
            let u = su0 + i as f32 * SHADOW_STEP;
            let f = (((0.55 * u + 0.8 * (0.31 * v + clock * 0.013).sin() + clock * 0.011).sin()
                + (0.47 * v - 0.3 * u + clock * 0.007).sin()
                + (0.93 * u + 0.71 * v - clock * 0.009 + (0.4 * u).sin()).sin())
                / 3.0)
                * 1.4;
            shadow[j * sw + i] = ((f - 0.15) * 1.8).clamp(0.0, 1.0);
        }
    }
    let shade = |u: f32, v: f32| -> f32 {
        let (fu, fv) = ((u - su0) / SHADOW_STEP, (v - sv0) / SHADOW_STEP);
        let (i, j) = (fu.floor().max(0.0) as usize, fv.floor().max(0.0) as usize);
        if i + 1 >= sw || j + 1 >= sh {
            return 0.0;
        }
        let (a, b) = (fu - i as f32, fv - j as f32);
        let s = |x: usize, y: usize| shadow[y * sw + x];
        (s(i, j) * (1.0 - a) + s(i + 1, j) * a) * (1.0 - b) + (s(i, j + 1) * (1.0 - a) + s(i + 1, j + 1) * a) * b
    };
    // --- The tilted map ---
    let mut map = vec![0u16; W * H];
    for y in 0..H {
        // (Along a row the ground's v and the scale are constant; u runs on.)
        let (u_mid, vv) = cam.unproject(CX, y as f32 + 0.5);
        let (u_edge, _) = cam.unproject(CX + 1.0, y as f32 + 0.5);
        let du = u_edge - u_mid;
        let gy = (vv * 16.0).floor() as i32;
        let sy = gy - cam_px.1;
        let mut shade_here = 0.0f32;
        let mut cur = (usize::MAX, [0u16; 256]);
        for x in 0..W {
            let u = u_mid + du * (x as f32 + 0.5 - CX);
            let gx = (u * 16.0).floor() as i32;
            let (ci, lx, ly) = ground.locate(gx, gy);
            if cur.0 != ci {
                cur = (ci, *ground.cell(ci));
            }
            let mut p = cur.1[ly * 16 + lx];
            if x & 1 == 0 {
                shade_here = shade(u, vv);
            }
            if shade_here > 0.0 {
                let k = 1.0 - 0.08 * shade_here;
                let ch = |s: u32| (((p as u32 >> s) & 31) as f32 * k) as u32;
                p = 0x8000 | (ch(0) | ch(5) << 5 | ch(10) << 10) as u16;
            }
            // The console's overlays, where it drew them.
            let sx = gx - cam_px.0;
            if (0..W as i32).contains(&sx) && (0..H as i32).contains(&sy) {
                let i = sy as usize * W + sx as usize;
                if tint.is_some() {
                    p = range_look(p, layers[0][i]);
                }
                if decal[i] != 0 {
                    p = decal[i];
                }
            } else if tint.is_some() {
                let (cx, cy) = (gx.div_euclid(16), gy.div_euclid(16));
                let on = cx >= 0
                    && cy >= 0
                    && cx < ground.w
                    && cy < ground.h
                    && reach[(cy * ground.w + cx) as usize] != 0xff;
                p = range_look(p, if on { 0x7fff } else { 0 });
            }
            map[y * W + x] = p;
        }
    }
    for bb in &boards {
        let (fx, fy, cell) = cam.project(bb.fu, bb.fv);
        let sc = cell / 16.0;
        let left = fx + bb.ox * sc;
        let top = fy + bb.oy * sc;
        let right = left + bb.w as f32 * sc;
        let bottom = top + bb.h as f32 * sc;
        let (x0, x1) = ((left.floor() as i32).max(0), (right.ceil() as i32).min(W as i32));
        let (y0, y1) = ((top.floor() as i32).max(0), (bottom.ceil() as i32).min(H as i32));
        for y in y0..y1 {
            let v = ((y as f32 + 0.5 - top) / sc).floor() as i32;
            if !(0..bb.h).contains(&v) {
                continue;
            }
            for x in x0..x1 {
                let u = ((x as f32 + 0.5 - left) / sc).floor() as i32;
                if !(0..bb.w).contains(&u) {
                    continue;
                }
                let p = bb.pix[(v * bb.w + u) as usize];
                if p != 0 {
                    map[y as usize * W + x as usize] = p;
                }
            }
        }
    }

    let t_map = t0.elapsed();
    // --- Out ---
    let lut = rgba_lut();
    let evy = (bldy & 31).min(16) as u32;
    for i in 0..W * H {
        let p = match owner[i] {
            Owner::Hud => continue,
            Owner::Map => map[i],
            Owner::MapFx => brightness(map[i], bld_mode, evy),
        };
        rgba[i * 4..i * 4 + 4].copy_from_slice(&lut[(p & 0x7fff) as usize]);
    }
    if debug_time() {
        eprintln!(
            "ds_tilt stages us: read {} load {} objs {} layers {} objtop {} owner {} boards {} map {} total {}",
            t_read.as_micros(),
            t_load.as_micros(),
            t_objs.as_micros(),
            t_layers.as_micros(),
            t_objtop.as_micros(),
            t_owner.as_micros(),
            t_boards.as_micros(),
            t_map.as_micros(),
            t0.elapsed().as_micros()
        );
    }
}

fn debug_time() -> bool {
    static ENV: OnceLock<bool> = OnceLock::new();
    env_on("TANGOAW2_TILT_TIME", &ENV)
}

fn debug_check() -> bool {
    static ENV: OnceLock<bool> = OnceLock::new();
    env_on("TANGOAW2_TILT_CHECK", &ENV)
}

/// The units' table (a ROM word names it), the players' (colours), and five
/// armies' slot count.
const UNITS_PTR: u32 = 0x0849_9594;
const PLAYERS_PTR: u32 = 0x0849_9598;
/// A pool word naming the CO table (0x104 bytes a CO, the country at +0x15).
const CO_TABLE_PTR: u32 = 0x0804_2DDC;

/// First tile of each unit type's picture (the console's, Orange Star's
/// art): the map sheet's slots. (A submerged Sub, type 25, is never drawn from
/// its record: who may see it is the game's to say.)
const UNIT_TILES: [u16; 28] = [
    0, 0x279, 0x27d, 0x235, 0x321, 0x23d, 0x241, 0x245, 0x239, 0x325, 0x249, 0x24d, 0x329, 0x32d, 0x251, 0x255, 0x259,
    0x25d, 0x331, 0x261, 0x265, 0x269, 0x26d, 0x271, 0x275, 0, 0x335, 0x339,
];

struct RamUnit {
    kind: u8,
    flags: u8,
    x: u8,
    y: u8,
    hp: u8,
    cargo: bool,
    army: u8,
    /// The army's CO's country: Infantry and Mech are drawn by it.
    country: u8,
    /// The army's colour (1 Orange Star .. 5 Black Hole).
    colour: u8,
    raw: [u8; 12],
    /// A five-army game (a moved unit's palette is another one).
    five: bool,
}

impl RamUnit {
    /// The four tilemap entries the console draws the unit with.
    fn entries(&self) -> Option<[u16; 4]> {
        let mut base = *UNIT_TILES.get(self.kind as usize)? & 0x3ff;
        if base == 0 {
            return None;
        }
        // Infantry and Mech have a picture a country.
        if matches!(self.kind, 1 | 2) {
            base += 8 * self.country.min(4) as u16;
        }
        let bank = if self.flags & 1 != 0 {
            if self.five { 9 } else { 11 }
        } else if self.army >= 5 {
            11
        } else {
            12 + (self.army as u16 - 1).min(3)
        } << 12;
        // (Facing: odd armies are mirrored; a unit that has moved keeps its army's facing.)
        let mut e = if self.army % 2 == 1 {
            [base + 1, base, base + 3, base + 2].map(|t| t | 0x400)
        } else {
            [base, base + 1, base + 2, base + 3]
        }
        .map(|t| t | bank);
        // The corner: army 4's mark, the HP digit (from 9 down), else the cargo mark.
        if self.hp <= 90 && self.hp > 0 {
            let digit = (self.hp as u16 + 9) / 10;
            e[3] = 0x2a1 + digit | bank;
        }
        // The capture mark (an infantry or mech taking a property) sits at the third tile.
        if matches!(self.kind, 1 | 2) && self.raw[5] & 0x40 != 0 {
            e[2] = 0x2ac | bank;
        }
        if !(self.hp <= 90 && self.hp > 0) && self.cargo {
            // (the cargo mark sits at the corner on the side the unit is not facing)
            let mirrored = self.army % 2 == 1;
            e[if mirrored { 3 } else { 2 }] = 0x2ab | bank;
        }
        Some(e)
    }
}

/// Every unit on the map.
fn ram_units(core: &Core) -> Vec<RamUnit> {
    let base = core.raw_read_32(UNITS_PTR, -1);
    let players = core.raw_read_32(PLAYERS_PTR, -1);
    let cos = core.raw_read_32(CO_TABLE_PTR, -1);
    if !(0x0200_0000..0x0400_0000).contains(&base) {
        return Vec::new();
    }
    let five = crate::five::active(core);
    let per = if five { 51 } else { 64 };
    let mut out = Vec::new();
    let mut buf = [0u8; 12];
    for id in 0..256u32 {
        if id % per == 0 {
            continue;
        }
        core.raw_read_range(base + 12 * id, -1, &mut buf);
        if buf[0] == 0 {
            continue;
        }
        let army = (id / per + 1) as u8;
        let country = if (0x0200_0000..0x0400_0000).contains(&players) && (0x0800_0000..0x0A00_0000).contains(&cos) {
            let co = core.raw_read_8(players + 0x3C * army as u32 + 0x1D, -1) as u32;
            core.raw_read_8(cos + 0x104 * co + 0x15, -1)
        } else {
            0
        };
        let colour = if (0x0200_0000..0x0400_0000).contains(&players) {
            core.raw_read_8(players + 0x3C * army as u32 + 0x1A, -1)
        } else {
            army
        };
        out.push(RamUnit {
            kind: buf[0],
            flags: buf[1],
            x: buf[2],
            y: buf[3],
            hp: (u16::from_le_bytes([buf[4], buf[5]]) & 0x7f) as u8,
            cargo: buf[1] & 0x10 != 0,
            army,
            country,
            colour,
            raw: buf,
            five,
        });
    }
    out
}
