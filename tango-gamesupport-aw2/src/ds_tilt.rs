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

static TIMING_LOG: AtomicBool = AtomicBool::new(false);

/// The frontend's frame-time log (the hidden `ds_tilt_log` setting in config.json): every 120
/// tilted pictures one `ds_tilt: ...` log line with the mean and worst time, for checking the cost
/// on a device.
pub fn set_timing_log(on: bool) {
    TIMING_LOG.store(on, Ordering::Relaxed);
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
const FOCAL: f32 = 305.417;
/// Pitch from straight down, radians (16.88 degrees).
const PITCH: f32 = 0.2345;
/// Camera height over the ground, in cells.
const HEIGHT: f32 = 21.8576;
/// The screen's centre, where the camera looks.
const CX: f32 = 109.526;
const CY: f32 = 66.998;
/// Billboards stand this far in front of their cell's bottom edge (cells):
/// Dual Strike's units' feet are just below it.
const FOOT_DROP: f32 = 0.135;
/// The properties' (and structures') feet, the woods' and mountains' (BG2), measured against real
/// frames the same way (cells, from the cell's bottom edge).
const PROP_DROP: f32 = 0.0;
const TERRAIN_DROP: f32 = -0.16;
/// Woods and mountains' pictures on the flat ground are drawn this many source pixels (16 a cell)
/// higher (Dual Strike's upright ones stand a little further back than their flat tiles lie).
const TALL_LIFT: i32 = 2;

/// Where the fitted camera's principal ray meets the ground, from the cursor
/// cell's corner (cells).
const CAM_BIAS: (f32, f32) = (-0.7223, -0.8956);
/// The camera's numbers, from the constants above unless `TANGOAW2_TILT_CAM` overrides them
/// (a development aid for fitting the camera to real Dual Strike frames):
/// `focal,pitch,height,cx,cy,bias_u,bias_v,foot_drop,terrain_drop,prop_drop,tall_lift` (focal in pixels of the 240-wide picture,
/// pitch in radians; any field may be left empty to keep its default).
#[derive(Clone, Copy)]
struct CamParams {
    focal: f32,
    pitch: f32,
    height: f32,
    cx: f32,
    cy: f32,
    bias: (f32, f32),
    foot_drop: f32,
    terrain_drop: f32,
    prop_drop: f32,
    tall_lift: i32,
}

fn cp() -> &'static CamParams {
    static P: OnceLock<CamParams> = OnceLock::new();
    P.get_or_init(|| {
        let mut p = CamParams { focal: FOCAL, pitch: PITCH, height: HEIGHT, cx: CX, cy: CY, bias: CAM_BIAS, foot_drop: FOOT_DROP, terrain_drop: TERRAIN_DROP, prop_drop: PROP_DROP, tall_lift: TALL_LIFT };
        if let Ok(v) = std::env::var("TANGOAW2_TILT_CAM") {
            let f: Vec<Option<f32>> = v.split(',').map(|t| t.trim().parse::<f32>().ok()).collect();
            let g = |i: usize| f.get(i).copied().flatten();
            p.focal = g(0).unwrap_or(p.focal);
            p.pitch = g(1).unwrap_or(p.pitch);
            p.height = g(2).unwrap_or(p.height);
            p.cx = g(3).unwrap_or(p.cx);
            p.cy = g(4).unwrap_or(p.cy);
            p.bias.0 = g(5).unwrap_or(p.bias.0);
            p.bias.1 = g(6).unwrap_or(p.bias.1);
            p.foot_drop = g(7).unwrap_or(p.foot_drop);
            p.terrain_drop = g(8).unwrap_or(p.terrain_drop);
            p.prop_drop = g(9).unwrap_or(p.prop_drop);
            p.tall_lift = g(10).map(|v| v as i32).unwrap_or(p.tall_lift);
        }
        p
    })
}

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
    /// The console's frame counter at the last picture (the glide runs on console frames, not on pictures: a picture
    /// is not made for every frame, as in a test that waits before a shot).
    at: u32,
}
static FOLLOW: std::sync::Mutex<Option<Follow>> = std::sync::Mutex::new(None);

/// The camera's centre for a cursor on a `w` x `h` map: it stays while the
/// cursor's cell is within 5 cells to its left, 6 to its right, 3 above and 4
/// below (the cell inside +-6 and +-4 by its far edge), never shows beyond the
/// map's edge (centre at least 8 cells from the sides and 6 from the top and
/// bottom) and centres a map smaller than that; it glides there.
fn follow(cursor: (i32, i32), w: i32, h: i32, now: u32) -> (f32, f32) {
    let (cx, cy) = (cursor.0 as f32, cursor.1 as f32);
    let clamp_to_map = |x: f32, y: f32| {
        (
            if w >= 16 { x.clamp(8.0, (w - 8) as f32) } else { w as f32 / 2.0 },
            if h >= 12 { y.clamp(6.0, (h - 6) as f32) } else { h as f32 / 2.0 },
        )
    };
    let mut st = FOLLOW.lock().unwrap();
    let fresh = st.as_ref().map_or(true, |f| f.map != (w, h));
    let f = st.get_or_insert(Follow { logical: (cx, cy), shown: (0.0, 0.0), map: (w, h), at: now });
    if fresh {
        *f = Follow { logical: (cx, cy), shown: (0.0, 0.0), map: (w, h), at: now };
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
        // 0.3 of the way a frame, for the frames since the last picture (a counter that went back: one).
        let n = if now >= f.at { (now - f.at).min(60) } else { 1 };
        let k = 1.0 - 0.7f32.powi(n as i32);
        f.shown.0 += (target.0 - f.shown.0) * k;
        f.shown.1 += (target.1 - f.shown.1) * k;
        if (target.0 - f.shown.0).abs() < 0.02 {
            f.shown.0 = target.0;
        }
        if (target.1 - f.shown.1).abs() < 0.02 {
            f.shown.1 = target.1;
        }
    }
    f.at = now;
    f.shown
}

/// Where the middle of map cell (`x`, `y`) shows in the tilted picture, in
/// screen pixels (the picture last drawn: other drawings that must sit by a
/// unit, [`crate::ds_menus`], ask here). `None` with the tilt off.
pub fn cell_screen(x: i32, y: i32) -> Option<(i32, i32)> {
    if !enabled() {
        return None;
    }
    let st = FOLLOW.lock().ok()?;
    let f = st.as_ref()?;
    let cam = Cam::new(f.shown.0 + cp().bias.0, f.shown.1 + cp().bias.1);
    let (sx, sy, _) = cam.project(x as f32 + 0.5, y as f32 + 0.5);
    Some((sx.round() as i32, sy.round() as i32))
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
        Cam { cu, cv, sin: cp().pitch.sin(), cos: cp().pitch.cos(), tan: cp().pitch.tan() }
    }

    /// The screen position of the ground point (u, v) in cells, and the size
    /// of a cell there in pixels across.
    fn project(&self, u: f32, v: f32) -> (f32, f32, f32) {
        let dx = u - self.cu;
        let dy = v - self.cv - cp().height * self.tan;
        let depth = cp().height * self.cos - dy * self.sin;
        let up = -dy * self.cos - cp().height * self.sin;
        (cp().cx + cp().focal * dx / depth, cp().cy - cp().focal * up / depth, cp().focal / depth)
    }

    /// The ground point (cells) under a screen position.
    fn unproject(&self, xs: f32, ys: f32) -> (f32, f32) {
        let a = (xs - cp().cx) / cp().focal;
        let b = -(ys - cp().cy) / cp().focal;
        let lam = -cp().height / (b * self.sin - self.cos);
        (self.cu + lam * a, self.cv + cp().height * self.tan + lam * (-b * self.cos - self.sin))
    }

    /// How far the screen reaches from the looked-at point: left, right, up,
    /// down, in cells (the widest row for the sides).
    fn reach(&self) -> (f32, f32, f32, f32) {
        let (ul0, vt) = self.unproject(0.0, 0.0);
        let (ur0, _) = self.unproject(W as f32, 0.0);
        let (_, vb) = self.unproject(cp().cx, H as f32);
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
    /// The nine pieces put together: the unit that is moving, upright.
    Mover,
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

/// The Black Obelisk's picture is a plaza with the tower on it, drawn top-down: standing it up
/// would put a second plaza beside the real one, so it lies on the ground (as the console draws it).
fn is_obelisk_part(o: &Obj) -> bool {
    o.class == Class::Billboard && matches!(o.tile as u32, 374 | 390 | 398 | 406)
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
/// The palette the structures of this mission are drawn with (9 until the console shows one).
static STRUCT_PAL: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(9);
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


/// The moving unit's sprite as the console last showed it: the nine pieces' places and flips
/// (its facing) relative to the picture's corner, and where that corner was against the
/// unit's place in the game's own record of the move ([`find_mover`]).
struct MoverSeen {
    /// (tile, x, y, hflip, vflip) of each piece.
    pieces: Vec<(u16, i32, i32, bool, bool)>,
    w: i32,
    h: i32,
    delta: Option<(i32, i32)>,
}
static MOVER_SEEN: std::sync::Mutex<Option<MoverSeen>> = std::sync::Mutex::new(None);

/// The proc that holds the selected or moving unit's sprite (function `0x080363D1`): the
/// unit's place in map pixels at +0x3E and +0x40, as the game moves it along its path (a
/// cell's 16 pixels in four frames for a vehicle). The sprite's pieces are at that place
/// minus the camera, less (10, 8): they are parked when it is off the console's picture.
fn find_mover(core: &Core) -> Option<(i32, i32)> {
    const MOVER_FN: u32 = 0x0803_63D1;
    for (base, len) in [(0x0300_0C00u32, 0x1300usize), (0x0200_C000, 0x2000)] {
        let mut b = vec![0u8; len];
        core.raw_read_range(base, -1, &mut b);
        let word = |i: usize| u32::from_le_bytes([b[i], b[i + 1], b[i + 2], b[i + 3]]);
        let mut i = 0;
        while i + 0x44 <= len {
            if word(i + 8) == MOVER_FN
                && (0x0840_0000..0x0870_0000).contains(&word(i))
                && (0x0840_0000..0x0870_0000).contains(&word(i + 4))
            {
                let at = |o: usize| i16::from_le_bytes([b[i + o], b[i + o + 1]]) as i32;
                return Some((at(0x3E), at(0x40)));
            }
            i += 4;
        }
    }
    None
}

/// The nine pieces at tiles 666-674 are a target's glow (flat on the ground)
/// when the crosshair is up, else the unit that is moving (one upright
/// picture, drawn where it is as it goes).
fn resolve_groups(mut objs: Vec<Obj>) -> Vec<Obj> {
    let targeting = objs.iter().any(|o| o.class == Class::Ground && is_crosshair(o.tile));
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
    if pieces.len() == 9 {
        // The picture's layout and facing (the pieces' flips), kept for when the game
        // parks the sprites (the unit is off the console's picture).
        let mut seen: Vec<(u16, i32, i32, bool, bool)> =
            pieces.iter().map(|o| (o.tile, o.x - x0, o.y - y0, o.flip.0, o.flip.1)).collect();
        seen.sort();
        *MOVER_SEEN.lock().unwrap() = Some(MoverSeen { pieces: seen, w, h, delta: None });
    }
    let first = pieces.iter().min_by_key(|o| o.idx).unwrap();
    rest.push(Obj {
        x: x0,
        y: y0,
        w,
        h,
        pri: first.pri,
        idx: first.idx,
        class: Class::Mover,
        pix,
        tile: first.tile,
        pal: first.pal,
        flip: first.flip,
    });
    rest
}

/// The attack target's crosshair: four 16 x 16 pieces whose tiles run through six frames, 886, 890, 894, 898,
/// 902 and 906 (the menu's hand, 910, comes after them).
fn is_crosshair(tile: u16) -> bool {
    (884..=909).contains(&tile)
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
        (16, 16, 884..=909) if pal == 1 => Class::Ground,
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
        let class = obj_class(a0, a2, w, h);
        if x + w <= 0 || y + h <= 0 || x >= W as i32 || y >= H as i32 {
            // Off the console's picture. The tilted view shows a little more than that, so the
            // sprites that lie on the map (the cursor, its brackets, the move arrow, the target
            // glow, the moving unit) are kept where the game put them, unless the game has
            // parked them (x 0, y 160) or they are far away.
            let parked = (a1 & 511) == 0 && (a0 & 255) == 160;
            let near_x = if (a1 & 511) >= 256 { (a1 & 511) as i32 - 512 } else { (a1 & 511) as i32 };
            let near_y = if (a0 & 255) >= 224 { (a0 & 255) as i32 - 256 } else { (a0 & 255) as i32 };
            let wanted = matches!(class, Class::Piece | Class::Ground | Class::Pointer)
                && !parked
                && near_x + w > -48
                && near_y + h > -48
                && near_x < W as i32 + 48
                && near_y < H as i32 + 48;
            if !wanted {
                continue;
            }
            x = near_x;
            y = near_y;
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
            class,
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

/// What the pictures shown so far count (display only: it drives the clouds' drift and the range's glow).
static CLOCK: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);

/// Dual Strike's way of showing a range, measured on its frames (a range shown and the same
/// picture with it off): the ground outside the range is dimmed to 3/4 exactly, and each cell in it
/// is lit by a soft gradient screened over the ground (white in the cell's bottom left corner, a
/// fraction of that, warm, toward its top right) that breathes slowly. `t` is the console's
/// tint pixel there (0: none; a reddish one is an attack range: the same glow, redder), `(lx, ly)`
/// the pixel's place in its 16 x 16 cell. Upright things (peaks and treetops) are lit the way
/// Dual Strike shows them: brightened by a factor (1.3 at the cell's top right, up to 1.8) instead.
/// How quickly a lit cell's glow falls from white at its corner to its far colour (an exponent on the 0..1 position).
const KNEE: f32 = 0.6;
/// The far colour of an attack-only cell's glow (5-bit channels), Dual Strike's pink.
const PINK_FAR: (f32, f32, f32) = (31.0, 18.0, 23.0);
/// How much of the ground the pink covers (0..1).
const ATTACK_COVER: f32 = 0.85;
fn range_look(p: Px, t: Px, lx: i32, ly: i32, upright: bool) -> Px {
    let ch = |c: Px, s: u32| (c as u32 >> s) & 31;
    let (mut r, mut g, mut b) = (ch(p, 0), ch(p, 5), ch(p, 10));
    if t == 0 {
        (r, g, b) = (r * 3 / 4, g * 3 / 4, b * 3 / 4);
    } else {
        let attack = ch(t, 0) > ch(t, 10) + 5;
        let breath = (CLOCK.load(Ordering::Relaxed) as f32 * 0.07).sin() * 0.12;
        // 0 at the bottom left corner, 1 at the top right
        let k = (((lx as f32 + 0.5) / 16.0 + (1.0 - (ly as f32 + 0.5) / 16.0)) * 0.5 + breath).clamp(0.0, 1.0);
        if upright {
            let f = 1.3 + 0.5 * (1.0 - k);
            let lift = |c: u32| ((c as f32 * f + 0.5) as u32).min(31);
            return 0x8000 | (lift(r) | lift(g) << 5 | lift(b) << 10) as u16;
        }
        // (measured against real frames: the glow falls off sooner than linearly, so less of a cell is white)
        let k = k.powf(KNEE);
        if attack {
            // Dual Strike's pink is nearly the same over any ground (measured on real frames over grass, road and
            // snow): the ground shows through a little, the glow runs from white to pink.
            let to = |c: u32, far: f32| {
                let target = 31.0 + (far - 31.0) * k;
                (c as f32 + (target - c as f32) * ATTACK_COVER + 0.5) as u32
            };
            (r, g, b) = (to(r, PINK_FAR.0).min(31), to(g, PINK_FAR.1).min(31), to(b, PINK_FAR.2).min(31));
            return 0x8000 | (r | g << 5 | b << 10) as u16;
        }
        let far = (10.0, 12.0, 5.0);
        let screen = |c: u32, far: f32| {
            let glow = 31.0 + (far - 31.0) * k;
            31 - ((31 - c) as f32 * (31.0 - glow) / 31.0 + 0.5) as u32
        };
        (r, g, b) = (screen(r, far.0), screen(g, far.1), screen(b, far.2));
    }
    0x8000 | (r | g << 5 | b << 10) as u16
}

/// One pixel of the sandstorm: a pale or dark grain here and there, drifting right and down.
fn sand_grain(p: Px, x: u32, y: u32, t: u32) -> Px {
    let (gx, gy) = (x.wrapping_sub(t * 3), y.wrapping_sub(t));
    let mut h = gx.wrapping_mul(0x9E37_79B1) ^ gy.wrapping_mul(0x85EB_CA6B);
    h ^= h >> 15;
    h = h.wrapping_mul(0x2C1B_3C6D);
    h ^= h >> 12;
    let r = h % 1000;
    let mix = |a: Px, to: (u32, u32, u32), k: u32| {
        let m = |s: u32, t: u32| {
            let v = ((a as u32 >> s) & 31) as i32;
            (v + ((t as i32 - v) * k as i32 >> 8)).clamp(0, 31) as u32
        };
        0x8000 | (m(0, to.0) | m(5, to.1) << 5 | m(10, to.2) << 10) as u16
    };
    if r < 45 {
        mix(p, (31, 31, 28), 190)
    } else if r < 70 {
        mix(p, (26, 20, 10), 120)
    } else {
        p
    }
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

/// Colours of the tilted map as Dual Strike's 3D engine shows them: a 5-bit
/// channel `c` is `2c + 1` of 63 (its 2D layers use `2c`; the console's
/// own picture, which this one keeps for the HUD, `c` of 31), so the map's
/// black is 4 and its white 255 (checked against melonDS frames: 4, 101,
/// 133, 165, 246 ...).
fn rgba_lut_3d() -> &'static Vec<[u8; 4]> {
    static LUT: OnceLock<Vec<[u8; 4]>> = OnceLock::new();
    LUT.get_or_init(|| {
        let ch = |c: usize| (((2 * c + 1) * 255) / 63) as u8;
        (0..0x8000usize).map(|i| [ch(i & 31), ch((i >> 5) & 31), ch((i >> 10) & 31), 255]).collect()
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
    /// Source pixels per 1/16 cell: 1 for the console's pictures, 1/2 for Dual Strike's 32 x 32 ones.
    scale: f32,
    /// A unit drawn from its record, for the debug log: its cell and low-ammunition / fuel icon.
    tag: Option<(i32, i32, u8)>,
}

/// Keeps the facing the console drew a unit with (its picture's mirror flag), and in the check
/// mode counts the times it differs from the rule the records give.
fn note_facing(u: &RamUnit, mirrored: bool, map: u64) {
    let mut f = FACING.lock().unwrap();
    if f.0 != map {
        *f = (map, std::collections::HashMap::new());
    }
    if mirrored != u.mirrored && debug_check() {
        dbg_line(&format!(
            "ds_tilt: facing: unit {} drawn {} by the console, {} by the rule",
            u.id,
            if mirrored { "mirrored" } else { "as stored" },
            if u.mirrored { "mirrored" } else { "as stored" }
        ));
    }
    f.1.insert(u.id, (u.facing_key(), mirrored));
}

/// The unit as it is drawn beyond the console's window: its remembered facing, if what it
/// depends on has not changed since the console showed the unit.
fn with_facing(u: &RamUnit, map: u64) -> RamUnit {
    let mut u = u.clone();
    let f = FACING.lock().unwrap();
    if f.0 == map {
        if let Some(&(key, mirrored)) = f.1.get(&u.id) {
            if key == u.facing_key() {
                u.mirrored = mirrored;
                if debug_check() {
                    dbg_line(&format!(
                        "ds_tilt: facing: unit {} at ({}, {}) beyond the window kept the console's ({})",
                        u.id,
                        u.x,
                        u.y,
                        if mirrored { "mirrored" } else { "as stored" }
                    ));
                }
            }
        }
    }
    u
}

/// Zeroes tile `k` (0 TL, 1 TR, 2 BL, 3 BR) of a 16 x 16 picture.
fn clear_quarter(pix: &mut [Px], k: usize) {
    for y in 0..8 {
        for x in 0..8 {
            pix[((k / 2) * 8 + y) * 16 + (k % 2) * 8 + x] = 0;
        }
    }
}

/// Dual Strike's 16 x 16 unit tiles by (Dual Strike id, frame, country), as the unit art conversion makes them.
fn ds_tiles(ds: u8, frame: usize, country: usize) -> Option<[u8; 128]> {
    static CACHE: std::sync::LazyLock<std::sync::Mutex<std::collections::HashMap<(u8, usize, usize), Option<[u8; 128]>>>> =
        std::sync::LazyLock::new(|| std::sync::Mutex::new(std::collections::HashMap::new()));
    *CACHE.lock().unwrap().entry((ds, frame, country)).or_insert_with(|| crate::ds_unit_art::map_tiles_ds(ds, frame, country))
}

/// Dual Strike's own 32 x 32 picture of a unit the console draws from the four tiles at `base`
/// (BG1's tile RAM holds the conversion of Dual Strike's art, one of its three idle frames), in the
/// palette bank the console used and mirrored as it was: found by matching the tiles to the
/// conversion of each frame and country. `None` when the tiles are not Dual Strike's.
fn ds_unit_art(v: &Vid, bg: &Bg, kind: u8, base: u16, mirrored: bool, bank: u16) -> Option<Vec<Px>> {
    let ds = crate::roster::ds_id(kind)?;
    let at = bg.char_base + 32 * base as usize;
    let have = v.vram.get(at..at + 128)?;
    let found = (0..3).flat_map(|f| (0..5).map(move |c| (f, c))).find(|&(f, c)| ds_tiles(ds, f, c).map_or(false, |t| t[..] == *have));
    let (frame, country) = found?;
    let bmp = crate::ds_unit_art::idle_bitmap(ds, frame, country)?;
    let mut out = vec![0u16; 1024];
    for y in 0..32usize {
        for x in 0..32usize {
            let c = bmp[y * 32 + if mirrored { 31 - x } else { x }] as usize;
            if c != 0 {
                out[y * 32 + x] = 0x8000 | (v.pal[bank as usize * 16 + c] & 0x7fff);
            }
        }
    }
    Some(out)
}

/// The low ammunition / fuel icon over a unit's 16 x 16 picture, in the top-right tile. The
/// game draws it on BG2 (in front of the units' BG1 here), but with Dual Strike map graphics
/// BG2 holds the terrain's upper parts and is rewritten every frame, so the console never
/// shows it: it is drawn here from the unit's record, for every unit.
fn overlay_low_icon(pix: &mut [Px], u: &RamUnit, bg2: &Bg, bg1_pri: u8, v: &Vid) {
    let Some(icon) = u.low_icon() else { return };
    if !bg2.on {
        return;
    }
    let front = bg2.pri < bg1_pri;
    for py in 0..8usize {
        for px in 0..8usize {
            let p = bg2.tile_px(v, icon, px, py);
            let at = py * 16 + 8 + px;
            if p != 0 && (front || pix[at] == 0) {
                pix[at] = p;
            }
        }
    }
}

/// Whether the last picture was made tilted. Where the tilt leaves a picture as the console drew it (a screen that is not
/// the battle map: the other front's view, say) the flat map's Dual Strike cursor and range look are drawn instead.
static TILTED: AtomicBool = AtomicBool::new(false);

fn tilted() -> bool {
    enabled() && TILTED.load(Ordering::Relaxed)
}

/// Rewrites `rgba` (the console's 240 x 160 picture) as Dual Strike's tilted
/// battle map, when that is what is on screen. Nothing else changes.
pub fn apply(core: &Core, rgba: &mut [u8]) {
    TILTED.store(false, Ordering::Relaxed);
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

/// Dual Strike's cursor on the flat map (the tilt off, "Dual Strike map graphics" on): the console's
/// picture is kept, AW2's pointer and corner brackets (tiles 869 and 873) are taken out of it (the
/// pixels they cover are redone from what lies under them) and Dual Strike's own cursor
/// ([`crate::ds_cursor`]) is drawn flat, 16 pixels a cell, in their place. Whatever else the game
/// draws there (the drop cursor, the move arrow, the menus) is left as it is; the attack crosshair is Dual Strike's ring.
pub fn apply_flat_cursor(core: &Core, rgba: &mut [u8]) {
    static FAILED: AtomicBool = AtomicBool::new(false);
    if tilted() || FAILED.load(Ordering::Relaxed) || rgba.len() != W * H * 4 {
        return;
    }
    if core.raw_read_32(MAIN_LOOP, -1) != BATTLE_MAIN || !crate::wasteland::ds_graphics(core) || crate::design::in_map_editor(core) {
        return;
    }
    let Some(art) = crate::ds_cursor::art() else { return };
    let before = rgba.to_vec();
    if std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| flat_cursor(core, rgba, art))).is_err() {
        FAILED.store(true, Ordering::Relaxed);
        rgba.copy_from_slice(&before);
        eprintln!("ds_tilt: the flat cursor failed; it is off for this session");
    }
}

fn flat_cursor(core: &Core, rgba: &mut [u8], art: &crate::ds_cursor::Art) {
    let mut v = Vid::read(core);
    let d = v.dispcnt();
    // (the dialogue box's per-line effects, a fade, a mosaic: the console's picture stays)
    if v.io[2] & 0x10 != 0 || d & 7 != 0 || d & 0x80 != 0 || d & 0x1000 == 0 {
        return;
    }
    let bldcnt = v.io[0x28];
    let win = Windows::new(&v);
    // (a fade over everything is not ours; a window's darkening is the terrain panel's)
    if (((bldcnt >> 6) & 3) >= 2 && (!win.any() || win.outside & 0x20 != 0)) || v.io[0x26] & 0xff != 0 {
        return;
    }
    let (Some(b0), Some(b1), Some(b2), Some(b3)) = (Bg::new(&v, 0), Bg::new(&v, 1), Bg::new(&v, 2), Bg::new(&v, 3)) else {
        return;
    };
    let bgs = [b0, b1, b2, b3];
    let Some(objs) = read_objs(core, &mut v) else { return };
    let is_cursor_piece = |o: &Obj| o.class == Class::Pointer || (o.class == Class::Ground && (o.tile == 873 || is_crosshair(o.tile)));
    if !objs.iter().any(|o| is_cursor_piece(o)) {
        return;
    }
    let targeting = objs.iter().any(|o| o.class == Class::Ground && is_crosshair(o.tile));
    for bg in &bgs {
        if bg.on {
            bg.load(core, &mut v);
        }
    }
    let mut layers: Vec<Vec<Px>> = Vec::with_capacity(4);
    for bg in &bgs {
        let mut l = vec![0u16; W * H];
        if bg.on {
            bg.render(&v, &mut l);
        }
        layers.push(l);
    }
    let fr = FlatRange::new(core, &bgs, &layers);
    // The top sprite per pixel without the cursor's pieces.
    let mut obj_top: Vec<u32> = vec![u32::MAX; W * H];
    let mut obj_color: Vec<Px> = vec![0; W * H];
    let mut covered = vec![false; W * H];
    for o in &objs {
        let cursor = is_cursor_piece(o);
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
                if cursor {
                    covered[i] = true;
                } else if key < obj_top[i] {
                    obj_top[i] = key;
                    obj_color[i] = p;
                }
            }
        }
    }
    let backdrop = 0x8000 | (v.pal[0] & 0x7fff);
    let mut order: Vec<usize> = (0..4).filter(|&b| bgs[b].on).collect();
    order.sort_by_key(|&b| (bgs[b].pri, b));
    let any_win = win.any();
    let lut = rgba_lut();
    for i in 0..W * H {
        if !covered[i] {
            continue;
        }
        let bits = if any_win { win.bits((i % W) as i32, (i / W) as i32) } else { 0x3f };
        let obj = if bits & 0x10 != 0 { obj_top[i] } else { u32::MAX };
        let obj_pri = if obj == u32::MAX { 9 } else { (obj >> 8) as u8 };
        let mut color = backdrop;
        let mut found = false;
        for &b in &order {
            if bits & (1 << b) == 0 || layers[b][i] == 0 || (b == 0 && fr.is_some()) {
                continue;
            }
            if obj_pri <= bgs[b].pri {
                break;
            }
            color = layers[b][i];
            // (a range: the ground under the cursor's pieces has Dual Strike's look as well)
            if let (Some(fr), 2 | 3) = (&fr, b) {
                color = fr.look(i, color, b == 2);
            }
            found = true;
            break;
        }
        if !found && obj != u32::MAX {
            color = obj_color[i];
        }
        rgba[i * 4..i * 4 + 4].copy_from_slice(&lut[(color & 0x7fff) as usize]);
    }
    // Dual Strike's cursor, flat: a cell is 16 pixels, the map's scroll puts it on the picture.
    let cam = (core.raw_read_16(MAP + 4, -1) as i16 as f32, core.raw_read_16(MAP + 6, -1) as i16 as f32);
    let cursor = (core.raw_read_8(CURSOR_X, -1) as i32, core.raw_read_8(CURSOR_Y, -1) as i32);
    let mut map = vec![0u16; W * H];
    let flat = |u: f32, v: f32| (u * 16.0 - cam.0, v * 16.0 - cam.1, 16.0);
    if targeting {
        // (Dual Strike's ring is 30 pixels across where its cell is 15)
        crate::ds_cursor::draw_crosshair(&mut map, W, H, art, cursor, Some(30.0), crate::ds_cursor::next_tick(), flat);
    } else {
        crate::ds_cursor::draw(&mut map, W, H, art, cursor, flat);
    }
    let lut3 = rgba_lut_3d();
    for (i, &p) in map.iter().enumerate() {
        if p != 0 {
            rgba[i * 4..i * 4 + 4].copy_from_slice(&lut3[(p & 0x7fff) as usize]);
        }
    }
}



/// The game's reach table at a map cell (0xFF: the selected unit cannot go there).
fn reach_at(core: &Core, w: i32, h: i32, x: i32, y: i32) -> u8 {
    if x < 0 || y < 0 || x >= w || y >= h {
        return 0xff;
    }
    let row = core.raw_read_16(MAP + 0x417A + 2 * y as u32, -1) as u32;
    core.raw_read_8(REACH + row + x as u32, -1)
}

/// The cell the table's costs start from (the selected unit's), if the table has one.
fn reach_origin(core: &Core, w: i32, h: i32) -> Option<(i32, i32)> {
    let mut origin = None;
    for y in 0..h {
        for x in 0..w {
            if reach_at(core, w, h, x, y) == 0 {
                if origin.is_some() {
                    return None;
                }
                origin = Some((x, y));
            }
        }
    }
    origin
}

/// The tint pixel the attack-only cells get (a reddish one: [`range_look`] shows it Dual Strike's pink).
const ATTACK_TINT: Px = 0x801F;

/// Dual Strike shows, with the white cells a selected unit can move to, the cells it can attack beyond
/// them in pink. AW2 marks only the move cells (BG0) for a unit that has not moved, so the pink ones are
/// worked out: the selected unit is the one standing on the zero-cost cell of the game's reach table, its
/// range is AW2's unit table's (Dual Strike's with the pack: [`crate::ds_units`]). A direct unit (range 1)
/// hits the cells next to the ones it can reach; an indirect one (it cannot move and fire) the cells
/// from its range's minimum to its maximum around where it stands. Returns the cells' tint (map cells).
/// Only while the console shows the move range (a target choice shows an attack range, and the table is stale).
fn attack_cells(core: &Core, w: i32, h: i32) -> std::collections::HashMap<(i32, i32), Px> {
    let mut out = std::collections::HashMap::new();
    if w <= 0 || h <= 0 || w > 64 || h > 64 {
        return out;
    }
    let reach = |x: i32, y: i32| reach_at(core, w, h, x, y);
    let Some((ox, oy)) = reach_origin(core, w, h) else { return out };
    // (the selected unit: the game's pointer, or the one on the origin cell)
    let sel = core.raw_read_32(0x0300_40D8, -1);
    let u = if (0x0200_0000..0x0400_0000).contains(&sel) { sel } else { crate::unit_actions::unit_at(core, ox, oy).unwrap_or(0) };
    if u == 0 {
        return out;
    }
    let kind = core.raw_read_8(u, -1) as u32;
    if !(1..=24).contains(&kind) {
        return out;
    }
    let rec = crate::ds_units::UNITS + 0x5C * kind;
    let (min, max) = (core.raw_read_8(rec + 0x0E, -1) as i32, core.raw_read_8(rec + 0x0F, -1) as i32);
    if max == 0 {
        return out;
    }
    if max == 1 {
        for y in 0..h {
            for x in 0..w {
                if reach(x, y) == 0xff && [(1, 0), (-1, 0), (0, 1), (0, -1)].iter().any(|(dx, dy)| reach(x + dx, y + dy) != 0xff) {
                    out.insert((x, y), ATTACK_TINT);
                }
            }
        }
    } else {
        for y in 0..h {
            for x in 0..w {
                let d = (x - ox).abs() + (y - oy).abs();
                if (min..=max).contains(&d) {
                    out.insert((x, y), ATTACK_TINT);
                }
            }
        }
    }
    out
}

/// A tint pixel is an attack range's (reddish).
fn is_attack_tint(t: Px) -> bool {
    t != 0 && (t as u32 & 31) > ((t as u32 >> 10) & 31) + 5
}

/// Dual Strike's range look on the flat map ([`range_look`]): which cells the console's range
/// overlay (BG0, while it is below the units) tints, and the map's scroll.
struct FlatRange {
    cam: (i32, i32),
    /// The tint pixel of each cell of the picture's grid (cell column, row at the scroll's offset), 0: none.
    cells: std::collections::HashMap<(i32, i32), Px>,
}

impl FlatRange {
    fn new(core: &Core, bgs: &[Bg; 4], layers: &[Vec<Px>]) -> Option<FlatRange> {
        if !(bgs[0].on && bgs[0].pri > bgs[1].pri) {
            return None;
        }
        let cam = (core.raw_read_16(MAP + 4, -1) as i16 as i32, core.raw_read_16(MAP + 6, -1) as i16 as i32);
        let mut cells = std::collections::HashMap::new();
        for (i, &t) in layers[0].iter().enumerate() {
            if t != 0 {
                let (gx, gy) = ((i % W) as i32 + cam.0, (i / W) as i32 + cam.1);
                cells.entry((gx.div_euclid(16), gy.div_euclid(16))).or_insert(t);
            }
        }
        // (no tinted cell: BG0 is not a range, say the cursor's glow or text)
        if cells.is_empty() {
            return None;
        }
        // The cells beyond the move range the unit can attack, pink: the console's own tint on a cell the unit
        // cannot move to is one too, and the move cells' tint is the move glow's whatever colour the console gave
        // it. (With no tinted cell reachable the console shows an attack range, a target choice.)
        let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
        if reach_origin(core, w, h).is_some() && cells.keys().any(|&(cx, cy)| reach_at(core, w, h, cx, cy) != 0xff) {
            for (&(cx, cy), t) in cells.iter_mut() {
                *t = if reach_at(core, w, h, cx, cy) == 0xff { ATTACK_TINT } else { 0x7fff };
            }
            // (a computed cell is pink even where the unit can move: an indirect unit's range lies inside it)
            for (c, t) in attack_cells(core, w, h) {
                cells.insert(c, t);
            }
        }
        Some(FlatRange { cam, cells })
    }

    fn look(&self, i: usize, p: Px, upright: bool) -> Px {
        let (gx, gy) = ((i % W) as i32 + self.cam.0, (i / W) as i32 + self.cam.1);
        let t = self.cells.get(&(gx.div_euclid(16), gy.div_euclid(16))).copied().unwrap_or(0);
        range_look(p, t, gx.rem_euclid(16), gy.rem_euclid(16), upright)
    }
}

/// Dual Strike's range on the flat map (the tilt off, "Dual Strike map graphics" on): the console's
/// picture is kept and its ground (terrain and the peaks and treetops over it; not the units, the
/// arrow or the panels) is redone without the console's own striped tint, in Dual Strike's look
/// ([`range_look`]). Run before [`apply_flat_cursor`], which keeps the look under the cursor's pieces.
pub fn apply_flat_range(core: &Core, rgba: &mut [u8]) {
    static FAILED: AtomicBool = AtomicBool::new(false);
    if tilted() || FAILED.load(Ordering::Relaxed) || rgba.len() != W * H * 4 {
        return;
    }
    if core.raw_read_32(MAIN_LOOP, -1) != BATTLE_MAIN || !crate::wasteland::ds_graphics(core) || crate::design::in_map_editor(core) {
        return;
    }
    let before = rgba.to_vec();
    if std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| flat_range(core, rgba))).is_err() {
        FAILED.store(true, Ordering::Relaxed);
        rgba.copy_from_slice(&before);
        eprintln!("ds_tilt: the flat range failed; it is off for this session");
    }
}

fn flat_range(core: &Core, rgba: &mut [u8]) {
    let mut v = Vid::read(core);
    let d = v.dispcnt();
    if v.io[2] & 0x10 != 0 || d & 7 != 0 || d & 0x80 != 0 || d & 0x1000 == 0 || d & 0x0e00 != 0x0e00 {
        return;
    }
    let win = Windows::new(&v);
    let bldcnt = v.io[0x28];
    if (((bldcnt >> 6) & 3) >= 2 && (!win.any() || win.outside & 0x20 != 0)) || v.io[0x26] & 0xff != 0 {
        return;
    }
    let (Some(b0), Some(b1), Some(b2), Some(b3)) = (Bg::new(&v, 0), Bg::new(&v, 1), Bg::new(&v, 2), Bg::new(&v, 3)) else {
        return;
    };
    let bgs = [b0, b1, b2, b3];
    if !(bgs[0].on && bgs[0].pri > bgs[1].pri) {
        return;
    }
    let Some(objs) = read_objs(core, &mut v) else { return };
    for bg in &bgs {
        if bg.on {
            bg.load(core, &mut v);
        }
    }
    let mut layers: Vec<Vec<Px>> = Vec::with_capacity(4);
    for bg in &bgs {
        let mut l = vec![0u16; W * H];
        if bg.on {
            bg.render(&v, &mut l);
        }
        layers.push(l);
    }
    let Some(fr) = FlatRange::new(core, &bgs, &layers) else { return };
    // The top sprite per pixel.
    let mut obj_top: Vec<u32> = vec![u32::MAX; W * H];
    for o in &objs {
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
                if key < obj_top[i] {
                    obj_top[i] = key;
                }
            }
        }
    }
    let mut order: Vec<usize> = (1..4).filter(|&b| bgs[b].on).collect();
    order.sort_by_key(|&b| (bgs[b].pri, b));
    let any_win = win.any();
    let lut = rgba_lut();
    for i in 0..W * H {
        let bits = if any_win { win.bits((i % W) as i32, (i / W) as i32) } else { 0x3f };
        // (a window with the colour effects off is a panel's: it keeps the console's picture)
        if any_win && bits & 0x20 == 0 {
            continue;
        }
        let obj = if bits & 0x10 != 0 { obj_top[i] } else { u32::MAX };
        let obj_pri = if obj == u32::MAX { 9 } else { (obj >> 8) as u8 };
        for &b in &order {
            if bits & (1 << b) == 0 || layers[b][i] == 0 {
                continue;
            }
            if obj_pri <= bgs[b].pri {
                break;
            }
            // BG1 holds the units, BG2 the peaks and treetops, BG3 the terrain (the units are not dimmed)
            if b != 1 {
                let c = fr.look(i, layers[b][i], b == 2);
                rgba[i * 4..i * 4 + 4].copy_from_slice(&lut[(c & 0x7fff) as usize]);
            }
            break;
        }
    }
}

fn apply_timed(core: &Core, rgba: &mut [u8]) {
    static TIME: OnceLock<bool> = OnceLock::new();
    if TIMING_LOG.load(Ordering::Relaxed) || env_on("TANGOAW2_TILT_TIME", &TIME) {
        let t = std::time::Instant::now();
        apply_inner(core, rgba);
        // (total ns, worst ns, pictures)
        static STATS: std::sync::Mutex<(u128, u128, u32)> = std::sync::Mutex::new((0, 0, 0));
        let ns = t.elapsed().as_nanos();
        let mut st = STATS.lock().unwrap();
        st.0 += ns;
        st.1 = st.1.max(ns);
        st.2 += 1;
        if st.2 >= 120 {
            log::info!(
                "ds_tilt: {} us a picture (worst {} us) over {} pictures",
                st.0 / st.2 as u128 / 1000,
                st.1 / 1000,
                st.2
            );
            *st = (0, 0, 0);
        }
    } else {
        apply_inner(core, rgba);
    }
}

fn apply_inner(core: &Core, rgba: &mut [u8]) {
    if !enabled() || rgba.len() != W * H * 4 {
        return;
    }
    // (the Design Room's map editor runs the battle map's loop over records it does not keep)
    if core.raw_read_32(MAIN_LOOP, -1) != BATTLE_MAIN || !crate::wasteland::ds_graphics(core) || crate::design::in_map_editor(core) {
        return;
    }
    let t0 = std::time::Instant::now();
    let mut v = Vid::read(core);
    let t_read = t0.elapsed();
    // A picture drawn with changes between its lines (HBlank interrupts on:
    // the dialogue box over the map's top) is not one this can redo.
    // The campaign dialogue box at the top is the one such effect we can carry: its rows (0x2D less the box's slide)
    // keep the console's picture and the map is tilted below them.
    let mut keep_rows = 0usize;
    // The bottom dialogue box (a handler in IWRAM that switches the background registers at the line the box's top is
    // on, `0x6F` plus the box's slide `0x030030A8`, and back in the vertical blank): its rows from there keep the
    // console's picture too.
    let mut keep_from = H;
    if v.io[2] & 0x10 != 0 {
        match core.raw_read_32(0x0300_2FE4, -1) {
            0x0801_7881 => {
                keep_rows = if core.raw_read_16(0x0300_2EDC, -1) & 0x1000 != 0 {
                    0
                } else {
                    (0x2D - core.raw_read_16(0x0300_30A8, -1) as i16 as i32).clamp(0, H as i32) as usize
                };
            }
            0x0300_5DC1 => {
                keep_from = (core.raw_read_16(0x0300_30A8, -1) as i16 as i32 + 0x6F).clamp(0, H as i32) as usize;
                // (the registers read now are the box's, which the handler wrote at its line: the map's are the
                // values it puts back in the vertical blank, in these shadows)
                let r16 = |a: u32| core.raw_read_16(a, -1);
                let r32 = |a: u32| core.raw_read_32(a, -1);
                v.io[0] = r16(0x0300_2F38);
                v.io[4] = r32(0x0300_2010) as u16;
                v.io[5] = (r32(0x0300_2010) >> 16) as u16;
                v.io[8] = r32(0x0300_3030) as u16;
                v.io[9] = (r32(0x0300_3030) >> 16) as u16;
                v.io[10] = r32(0x0300_2B3C) as u16;
                v.io[11] = (r32(0x0300_2B3C) >> 16) as u16;
                v.io[0x28] = r16(0x0300_2014);
                v.io[0x29] = r16(0x0300_30C0).wrapping_add(r16(0x0300_1FEC) << 8);
                v.io[0x2a] = r16(0x0300_1FB4);
            }
            _ => return,
        }
    }
    let d = v.dispcnt();
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
                        // (Darkening is the terrain panel's; a lightening window is a flash on the console's
                        // own screen position, which on the tilted map would be a ghost rectangle.)
                        owner[i] = if bld_mode == 3 {
                            Owner::MapFx
                        } else if bld_mode == 2 {
                            Owner::Map
                        } else {
                            Owner::Hud
                        };
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
    let (fx, fy) = follow(cursor, ground.w, ground.h, core.frame_counter());
    let cam = Cam::new(fx + cp().bias.0, fy + cp().bias.1);

    // What lies on the ground, as the console shows it: BG0's range tint
    // (while it is below the units) and the sprites that lie flat.
    // Dual Strike's own cursor art replaces AW2's pointer and corner brackets
    // (with the pack; without it AW2's stay).
    let ds_cursor = crate::ds_cursor::art();
    let is_cursor_piece = |o: &Obj| o.class == Class::Pointer || (o.class == Class::Ground && o.tile == 873);
    let cursor_shown = ds_cursor.is_some() && objs.iter().any(|o| is_cursor_piece(o));
    // The attack target's ring (four crosshair pieces) is Dual Strike's as well.
    let is_ring_piece = |o: &Obj| o.class == Class::Ground && is_crosshair(o.tile);
    let ring_shown = ds_cursor.is_some() && objs.iter().any(|o| is_ring_piece(o));
    // (with a margin: the tilted view shows ground the console's picture does not, and the
    // sprites that lie on it (the cursor's brackets, the move arrow, a target's glow) go there too)
    const DM: i32 = 48;
    const DW: usize = W + 2 * DM as usize;
    let mut decal = vec![0u16; DW * (H + 2 * DM as usize)];
    for o in objs
        .iter()
        .filter(|o| (o.class == Class::Ground || is_obelisk_part(o)) && !(cursor_shown && is_cursor_piece(o)) && !(ring_shown && is_ring_piece(o)))
    {
        for y in 0..o.h {
            let sy = o.y + y;
            if !(-DM..H as i32 + DM).contains(&sy) {
                continue;
            }
            for x in 0..o.w {
                let sx = o.x + x;
                let p = o.pix[(y * o.w + x) as usize];
                if p != 0 && (-DM..W as i32 + DM).contains(&sx) {
                    decal[(sy + DM) as usize * DW + (sx + DM) as usize] = p;
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
    // The console's tint on the cells the unit can reach is the move range; with none there (a target choice: the
    // table is stale) the tinted cells are an attack range already.
    let move_stage = tint.is_some() && reach_origin(core, ground.w, ground.h).is_some()
        && layers[0].iter().enumerate().any(|(i, &t)| {
            let (cx, cy) = (((i % W) as i32 + cam_px.0).div_euclid(16), ((i / W) as i32 + cam_px.1).div_euclid(16));
            t != 0 && cx >= 0 && cy >= 0 && cx < ground.w && cy < ground.h && reach[(cy * ground.w + cx) as usize] != 0xff
        });
    // The cells it can attack beyond them, in pink.
    let pink = if move_stage { attack_cells(core, ground.w, ground.h) } else { std::collections::HashMap::new() };

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
                // (the ground is drawn in Dual Strike's own colours, the console's picture in the
                // four merged palettes: near is the same)
                let (a, b) = (ground.px(cam_px.0 + x, cam_px.1 + y), layers[3][i]);
                let near = |s: u32| (((a >> s) & 31) as i32 - ((b >> s) & 31) as i32).abs();
                if (a ^ b) & 0x8000 != 0 || near(0) + near(5) + near(10) > 14 {
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
    // Every unit on the map, from the game's records.
    let records = ram_units(core);
    let unit_in: std::collections::HashMap<(i32, i32), &RamUnit> = records
        .iter()
        .filter(|u| u.flags & 0x0e == 0)
        .map(|u| ((u.x as i32, u.y as i32), u))
        .collect();
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
                let mut art_board: Option<Vec<Px>> = None;
                if b == 1 {
                    if let Some(u) = unit_in.get(&(mx, my)) {
                        // (the console's picture of the unit: whether it is mirrored)
                        let e0 = bg.entry(&v, cx * 2, cy * 2);
                        // (only where it is this unit's picture: the plane may hold another's, not yet
                        // redrawn)
                        let mirrored = e0 & 0x400 != 0;
                        if (e0 & 0x3ff) == u.base + mirrored as u16 {
                            note_facing(u, mirrored, ground.signature());
                            // Dual Strike's own 32 x 32 picture instead of the 16 x 16 conversion;
                            // what is left of the console's cell is the HP digit and the marks.
                            if let Some(a) = ds_unit_art(&v, bg, u.kind, u.base, mirrored, (e0 >> 12) & 15) {
                                let tiles = if mirrored { [u.base + 1, u.base, u.base + 3, u.base + 2] } else { [u.base, u.base + 1, u.base + 2, u.base + 3] };
                                for (k, &t) in tiles.iter().enumerate() {
                                    let e = bg.entry(&v, cx * 2 + (k as i32 % 2), cy * 2 + (k as i32 / 2));
                                    if e & 0x3ff == t {
                                        clear_quarter(&mut pix, k);
                                    }
                                }
                                art_board = Some(a);
                            }
                        }
                        overlay_low_icon(&mut pix, u, &bgs[2], bgs[1].pri, &v);
                    }
                }
                // Peaks and treetops (BG2) in Dual Strike's own colours, not the four
                // palettes' merged ones.
                if b == 2 {
                    if let Some(up) = ground.upper_pixels(mx, my) {
                        for (p, &e) in pix.iter_mut().zip(up.iter()) {
                            if *p != 0 && e != 0 {
                                *p = e;
                            }
                        }
                    }
                    // A range lights the peaks and treetops of its cells and dims the others', as
                    // it does the ground they stand on.
                    if tint.is_some() && mx >= 0 && my >= 0 && mx < ground.w && my < ground.h {
                        let on = reach[(my * ground.w + mx) as usize] != 0xff;
                        let sample = layers[0].get(((sy0 + 8).max(0) as usize) * W + (sx0 + 8).max(0) as usize).copied().unwrap_or(0);
                        let t = match pink.get(&(mx, my)) {
                            Some(&q) => q,
                            None => if on { if sample != 0 && !move_stage { sample } else { 0x7fff } } else { 0 },
                        };
                        for (i, p) in pix.iter_mut().enumerate().filter(|(_, p)| **p != 0) {
                            *p = range_look(*p, t, i as i32 % 16, i as i32 / 16, true);
                        }
                    }
                }
                let foot_x = (mx * 16 - cam_px.0 + 8) as f32;
                let foot_y = (my * 16 - cam_px.1 + 16) as f32;
                // Units stand a little in front of the edge; the peaks and
                // treetops (BG2) stand on it.
                let drop = if b == 1 { cp().foot_drop } else { cp().terrain_drop };
                if let Some(a) = art_board {
                    if debug_check() {
                        dbg_line(&format!("ds_tilt: unit art: Dual Strike's 32 x 32 at ({mx}, {my})"));
                    }
                    boards.push(Billboard {
                        pix: a,
                        w: 32,
                        h: 32,
                        fu: mx as f32 + 0.5,
                        fv: my as f32 + 1.0 + drop,
                        ox: sx0 as f32 - foot_x,
                        oy: sy0 as f32 - foot_y,
                        rank: (3 - bg.pri) * 2,
                        last: false,
                        scale: 0.5,
                        tag: None,
                    });
                }
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
                    scale: 1.0,
                    tag: None,
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
        let mut checked = 0;
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
                if drawn || want.is_some() {
                    checked += 1;
                }
                let ok = match (drawn, want) {
                    (false, None) => true,
                    (true, Some(w)) => w.iter().zip(&got).all(|(a, b)| a == b),
                    _ => false,
                };
                if !ok {
                    bad += 1;
                    if bad <= 6 {
                        dbg_line(&format!(
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
                        ));
                    }
                }
            }
        }
        dbg_line(&format!(
            "ds_tilt: units check: {} units in the console's window, {} cells where the records and the console's picture differ",
            checked, bad
        ));
    }
    if bgs[1].on {
        let seen: std::collections::HashSet<(i32, i32)> = boards
            .iter()
            .filter(|b| !b.last && b.rank == (3 - bgs[1].pri) * 2)
            .map(|b| ((b.fu - 0.5) as i32, (b.fv - 1.0 - cp().foot_drop).round() as i32 - 0))
            .collect();
        // The cells the console's picture shows (those the plane loop above drew a billboard
        // for, empty or not): its plane is 16 x 16 cells but only 15 x 10 and the edge
        // pixels of the next are on the screen.
        let console_shows = |mx: i32, my: i32| {
            let (cx, cy) = (mx - map_x0 + ground_cx0, my - map_y0 + ground_cy0);
            let (cx0, cy0) = (bgs[1].hofs.div_euclid(16), bgs[1].vofs.div_euclid(16));
            let (sx0, sy0) = (cx * 16 - bgs[1].hofs, cy * 16 - bgs[1].vofs);
            (cx0 - 1..=cx0 + 15).contains(&cx)
                && (cy0 - 1..=cy0 + 10).contains(&cy)
                && sx0 + 16 > 0
                && sy0 + 16 > 0
                && sx0 < W as i32
                && sy0 < H as i32
        };
        let bob = {
            let d = (bgs[1].vofs - bgs[3].vofs).rem_euclid(512);
            if d < 16 { d } else { 0 }
        };
        for u in records.iter() {
            let (ux, uy) = (u.x as i32, u.y as i32);
            if console_shows(ux, uy) || seen.contains(&(ux, uy)) {
                continue;
            }
            if ux >= ground.w || uy >= ground.h || ground.fogged(ux, uy) || u.flags & 0x0e != 0 {
                continue;
            }
            let u = with_facing(u, ground.signature());
            let Some(entries) = u.entries() else { continue };
            let mut pix = vec![0u16; 256];
            for (k, &e) in entries.iter().enumerate() {
                for py in 0..8usize {
                    for px in 0..8usize {
                        pix[((k / 2) * 8 + py) * 16 + (k % 2) * 8 + px] = bgs[1].tile_px(&v, e, px, py);
                    }
                }
            }
            let art = ds_unit_art(&v, &bgs[1], u.kind, u.base, u.mirrored, u.bank);
            if art.is_some() {
                let tiles = if u.mirrored { [u.base + 1, u.base, u.base + 3, u.base + 2] } else { [u.base, u.base + 1, u.base + 2, u.base + 3] };
                for (k, &t) in tiles.iter().enumerate() {
                    if entries[k] & 0x3ff == t {
                        clear_quarter(&mut pix, k);
                    }
                }
            }
            overlay_low_icon(&mut pix, &u, &bgs[2], bgs[1].pri, &v);
            if let Some(a) = art {
                if debug_check() {
                    dbg_line(&format!("ds_tilt: unit art: Dual Strike's 32 x 32 at ({ux}, {uy}) from its record"));
                }
                boards.push(Billboard {
                    pix: a,
                    w: 32,
                    h: 32,
                    fu: ux as f32 + 0.5,
                    fv: uy as f32 + 1.0 + cp().foot_drop,
                    ox: -8.0,
                    oy: -16.0 - bob as f32,
                    rank: (3 - bgs[1].pri) * 2,
                    last: false,
                    scale: 0.5,
                    tag: None,
                });
            }
            boards.push(Billboard {
                pix,
                w: 16,
                h: 16,
                fu: ux as f32 + 0.5,
                fv: uy as f32 + 1.0 + cp().foot_drop,
                ox: -8.0,
                oy: -16.0 - bob as f32,
                rank: (3 - bgs[1].pri) * 2,
                last: false,
                scale: 1.0,
                tag: Some((ux, uy, u.low)),
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
            STRUCT_PAL.store(9, Ordering::Relaxed);
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
                for (k, &(dx, dy, w, h, pt, pp, _phf, _pvf)) in crate::ds_plans::PLANS[i].1.iter().enumerate() {
                    let (px, py) = (mx * 16 - cam_px.0 + dx as i32, my * 16 - cam_px.1 + dy as i32);
                    if let Some(o) = objs.iter().find(|o| {
                        o.class == Class::Billboard && (o.x, o.y, o.w, o.h) == (px, py, w as i32, h as i32)
                    }) {
                        {
                            cache.1.insert((t, k as u8), (o.tile, o.pal, o.flip));
                            // (the structures share a palette in a mission: 9 in all but the
                            // mission the plans were recorded in)
                            if pp == 13 && pt >= STATIC_SHEET {
                                STRUCT_PAL.store(o.pal as u32, Ordering::Relaxed);
                            }
                        }
                        // (a fogged property is drawn in another palette: learn it)
                        if ground.fogged(mx, my) && o.tile < STATIC_SHEET as u16 {
                            FOG_PAL.store(o.pal as u32, Ordering::Relaxed);
                        }
                    }
                }
            }
        }
        // Draw.
        let volcano_here = (0..16u32).any(|k| (core.raw_read_16(0x0202_8362 + 8 * k, -1) >> 6) & 0xF == 2);
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
                        // Not drawn by the console yet: the sprite plan's own tiles (the
                        // loader's slots are the same in every mission; the palette may
                        // be another one until the console shows one).
                        let pal = if pal == 13 { STRUCT_PAL.load(Ordering::Relaxed) as u8 } else { pal };
                        // (With a Volcano in the mission the loader puts the Factory's
                        // pictures at 786, 818 and 826 instead of 304, 336 and 344.)
                        let tile = if volcano_here && t == 0x18d {
                            [786, 818, 826].get(k).copied().unwrap_or(tile)
                        } else {
                            tile
                        };
                        (tile, pal, (hf, vf))
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
                        fv: my as f32 + (dy as f32 + h as f32) / 16.0 + cp().prop_drop,
                        ox: -(w as f32) / 2.0,
                        oy: -(h as f32),
                        rank: 1,
                        last: false,
                        scale: 1.0,
                        tag: None,
                    });
                }
            }
        }
    }
    for o in objs
        .iter()
        .filter(|o| matches!(o.class, Class::Billboard | Class::Pointer | Class::Mover) && !is_obelisk_part(o) && !(cursor_shown && is_cursor_piece(o)))
    {
        let fx = o.x as f32 + o.w as f32 / 2.0;
        let fy = (o.y + o.h) as f32;
        let pix = o.pix.clone();
        boards.push(Billboard {
            pix,
            w: o.w,
            h: o.h,
            fu: (cam_px.0 as f32 + fx) / 16.0,
            fv: (cam_px.1 as f32 + fy) / 16.0 + if o.class == Class::Pointer { 0.0 } else { cp().prop_drop },
            ox: -(o.w as f32) / 2.0,
            oy: -(o.h as f32),
            rank: (3 - o.pri) * 2 + 1,
            last: o.class == Class::Pointer,
            scale: 1.0,
            tag: None,
        });
    }
    // The moving unit where the console has no picture of it: its sprite is parked while the
    // unit is off the console's screen (the tilted view shows more), so it is drawn from the
    // game's record of the move, with the pieces and facing the console last showed.
    // (`TANGOAW2_TILT_NO_RAM_MOVER=1` leaves it out, for a test's comparison)
    static NO_RAM_MOVER: OnceLock<bool> = OnceLock::new();
    let mover = if env_on("TANGOAW2_TILT_NO_RAM_MOVER", &NO_RAM_MOVER) { None } else { find_mover(core) };
    {
        let mut seen = MOVER_SEEN.lock().unwrap();
        if let (Some(sn), Some((mx, my))) = (seen.as_mut(), mover) {
            if let Some(o) = objs.iter().find(|o| o.class == Class::Mover) {
                // (the picture's corner against the record's place, learned while it shows)
                sn.delta = Some((o.x - (mx - cam_px.0 - 10), o.y - (my - cam_px.1 - 8)));
            } else if let Some((dx, dy)) = sn.delta {
                let (left, top) = (mx - 10 + dx, my - 8 + dy);
                let (cx, cy) = ((mx + 8).div_euclid(16), (my + 8).div_euclid(16));
                if (0..ground.w).contains(&cx)
                    && (0..ground.h).contains(&cy)
                    && !ground.fogged(cx, cy)
                    && !objs.iter().any(|o| o.class == Class::Ground && is_crosshair(o.tile))
                {
                    let mut pix = vec![0u16; (sn.w * sn.h) as usize];
                    let one_d = v.dispcnt() & 0x40 != 0;
                    for &(tile, px, py, hf, vf) in sn.pieces.iter() {
                        let piece = obj_pixels_ro(&v, one_d, tile as usize, 4, 8, 8, hf, vf, false);
                        for y in 0..8 {
                            for x in 0..8 {
                                let p = piece[y * 8 + x];
                                if p != 0 {
                                    pix[((py + y as i32) * sn.w + px + x as i32) as usize] = p;
                                }
                            }
                        }
                    }
                    boards.push(Billboard {
                        pix,
                        w: sn.w,
                        h: sn.h,
                        fu: (left as f32 + sn.w as f32 / 2.0) / 16.0,
                        fv: (top as f32 + sn.h as f32) / 16.0 + cp().prop_drop,
                        ox: -(sn.w as f32) / 2.0,
                        oy: -(sn.h as f32),
                        rank: 1,
                        last: false,
                        scale: 1.0,
                        tag: Some((-1, -1, 0)),
                    });
                }
            }
        }
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
    let clock = CLOCK.fetch_add(1, Ordering::Relaxed) as f32;
    const SHADOW_STEP: f32 = 0.25;
    // (measured on Dual Strike's frames: the water's darkest cloud shadow is 12% darker than its clear water)
    const SHADOW_DARK: f32 = 0.12;
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
            let t = ((f - 0.2) / 1.1).clamp(0.0, 1.0);
            shadow[j * sw + i] = t * t * (3.0 - 2.0 * t);
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
        let (u_mid, vv) = cam.unproject(cp().cx, y as f32 + 0.5);
        let (u_edge, _) = cam.unproject(cp().cx + 1.0, y as f32 + 0.5);
        let du = u_edge - u_mid;
        let gy = (vv * 16.0).floor() as i32;
        let sy = gy - cam_px.1;
        let mut shade_here = 0.0f32;
        let mut cur = (usize::MAX, [0u16; 256]);
        for x in 0..W {
            let u = u_mid + du * (x as f32 + 0.5 - cp().cx);
            let gx = (u * 16.0).floor() as i32;
            let outer = ground.outside(gx, gy);
            let mut p = if let Some(c) = outer {
                c
            } else {
                let (mut ci, mut lx, mut ly) = ground.locate(gx, gy);
                if cp().tall_lift != 0 && gy + cp().tall_lift < ground.h * 16 {
                    let (c2, x2, y2) = ground.locate(gx, gy + cp().tall_lift);
                    if ground.is_tall(c2) {
                        (ci, lx, ly) = (c2, x2, y2);
                    }
                }
                if cur.0 != ci {
                    cur = (ci, *ground.cell(ci));
                }
                cur.1[ly * 16 + lx]
            };
            if x & 1 == 0 {
                shade_here = shade(u, vv);
            }
            if shade_here > 0.0 {
                let k = 1.0 - SHADOW_DARK * shade_here;
                let ch = |s: u32| (((p as u32 >> s) & 31) as f32 * k + 0.5) as u32;
                p = 0x8000 | (ch(0) | ch(5) << 5 | ch(10) << 10) as u16;
            }
            // The console's overlays, where it drew them.
            let sx = gx - cam_px.0;
            if (0..W as i32).contains(&sx) && (0..H as i32).contains(&sy) {
                let i = sy as usize * W + sx as usize;
                if tint.is_some() && outer.is_none() {
                    let mut t = layers[0][i];
                    let (cx, cy) = (gx.div_euclid(16), gy.div_euclid(16));
                    if t != 0 && move_stage && cx >= 0 && cy >= 0 && cx < ground.w && cy < ground.h {
                        // (a move cell's tint is the move glow's whatever colour the console gave it)
                        t = if reach[(cy * ground.w + cx) as usize] == 0xff { ATTACK_TINT } else { 0x7fff };
                    }
                    if let Some(&q) = pink.get(&(cx, cy)) {
                        t = q;
                    }
                    p = range_look(p, t, gx.rem_euclid(16), gy.rem_euclid(16), false);
                }
            } else if tint.is_some() && outer.is_none() {
                let (cx, cy) = (gx.div_euclid(16), gy.div_euclid(16));
                let on = cx >= 0
                    && cy >= 0
                    && cx < ground.w
                    && cy < ground.h
                    && reach[(cy * ground.w + cx) as usize] != 0xff;
                let t = pink.get(&(cx, cy)).copied().unwrap_or(if on { 0x7fff } else { 0 });
                p = range_look(p, t, gx.rem_euclid(16), gy.rem_euclid(16), false);
            }
            if (-DM..W as i32 + DM).contains(&sx) && (-DM..H as i32 + DM).contains(&sy) {
                let d = decal[(sy + DM) as usize * DW + (sx + DM) as usize];
                if d != 0 {
                    p = d;
                }
            }
            map[y * W + x] = p;
        }
    }
    for bb in boards.iter() {
        let (fx, fy, cell) = cam.project(bb.fu, bb.fv);
        let sc = cell / 16.0;
        let left = fx + bb.ox * sc;
        let top = fy + bb.oy * sc;
        let ssc = sc * bb.scale;
        let right = left + bb.w as f32 * ssc;
        let bottom = top + bb.h as f32 * ssc;
        let (x0, x1) = ((left.floor() as i32).max(0), (right.ceil() as i32).min(W as i32));
        let (y0, y1) = ((top.floor() as i32).max(0), (bottom.ceil() as i32).min(H as i32));
        if debug_check() && bb.tag.is_none() {
            // (a test finds a unit's picture on the screen by its cell: `fu`, `fv` are its foot)
            dbg_line(&format!(
                "ds_tilt: board {:.2} {:.2} {}x{} at ({:.0}, {:.0}) to ({:.0}, {:.0})",
                bb.fu, bb.fv, bb.w, bb.h, left, top, right, bottom
            ));
        }
        if let (true, Some((cx, cy, low))) = (debug_check(), bb.tag) {
            dbg_line(&format!(
                "ds_tilt: record-drawn {} ({}, {}) low {} at ({:.0}, {:.0}) to ({:.0}, {:.0})",
                if cx < 0 { "moving unit" } else { "unit" },
                cx,
                cy,
                low,
                left,
                top,
                right,
                bottom
            ));
        }
        for y in y0..y1 {
            let v = ((y as f32 + 0.5 - top) / ssc).floor() as i32;
            if !(0..bb.h).contains(&v) {
                continue;
            }
            for x in x0..x1 {
                let u = ((x as f32 + 0.5 - left) / ssc).floor() as i32;
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

    if let (Some(art), true) = (ds_cursor, cursor_shown) {
        crate::ds_cursor::draw(&mut map, W, H, art, cursor, |u, v| cam.project(u, v));
    }
    if let (Some(art), true) = (ds_cursor, ring_shown) {
        crate::ds_cursor::draw_crosshair(&mut map, W, H, art, cursor, None, crate::ds_cursor::next_tick(), |u, v| cam.project(u, v));
    }

    // A sandstorm (Dual Strike's fourth weather; AW2 draws no particles for it): drifting grains over
    // the map, as many fine speckles as Dual Strike shows.
    let sand = crate::sandstorm::active(core);
    let t_map = t0.elapsed();
    // --- Out ---
    TILTED.store(true, Ordering::Relaxed);
    let lut = rgba_lut_3d();
    let evy = (bldy & 31).min(16) as u32;
    for i in 0..W * H {
        let p = match owner[i] {
            _ if i / W < keep_rows || i / W >= keep_from => continue,
            Owner::Hud => continue,
            Owner::Map => {
                let p = map[i];
                if sand {
                    sand_grain(p, (i % W) as u32, (i / W) as u32, clock as u32)
                } else {
                    p
                }
            }
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

/// A line of the check's output: stderr, and the end of the file `TANGOAW2_TILT_LOG` names
/// (so a test can read what its console printed).
fn dbg_line(s: &str) {
    eprintln!("{s}");
    if let Ok(path) = std::env::var("TANGOAW2_TILT_LOG") {
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(f, "{s}");
        }
    }
}

/// The units' table (a ROM word names it), the players' (colours), and five
/// armies' slot count.
const UNITS_PTR: u32 = 0x0849_9594;
const PLAYERS_PTR: u32 = 0x0849_9598;
/// A pool word naming the CO table (0x104 bytes a CO, the country at +0x15).
const CO_TABLE_PTR: u32 = 0x0804_2DDC;

#[derive(Clone)]
struct RamUnit {
    /// The record's number (the army's slots in turn).
    id: u8,
    kind: u8,
    flags: u8,
    x: u8,
    y: u8,
    hp: u8,
    army: u8,
    /// The army's CO's country: Infantry and Mech are drawn by it.
    country: u8,
    /// The army's colour (1 Orange Star .. 5 Black Hole).
    colour: u8,
    raw: [u8; 12],
    /// A five-army game (a moved unit's palette is another one).
    five: bool,
    /// The picture is mirrored, in this palette bank and by this army's CO (the
    /// game draws a moved unit as the army whose turn it is).
    mirrored: bool,
    bank: u16,
    /// The first BG tile of the picture (`0x080261A4`: the game's slot table, a row a
    /// country, a slot of four tiles from 0x235).
    base: u16,
    /// The HP is hidden ("?" in the corner): the unit's army's CO hides it and the
    /// army the picture is drawn for is not the viewer's side.
    hide_hp: bool,
    /// The fourth status icon (0x2AE).
    icon4: bool,
    /// The army the picture is drawn for, and whether the unit has moved: what its facing and
    /// palette depend on (see [`note_facing`]).
    shown_by: u8,
    moved: bool,
    /// Low ammunition (1) and low fuel (2): at most a third of the type's own (the game's
    /// `0x08022618`, which puts the icon in the top-right tile of the cell on BG2).
    low: u8,
}

/// The facing the console drew a unit with while it was in its window (the picture's mirror
/// flag), kept for when the unit is beyond it: the console draws only its own window, and the
/// unit's picture then comes from the record. It applies while what the facing depends on (the
/// army the picture is drawn for, whether the unit has moved, its type) is as it was.
type FacingKey = (u8, u8, bool);
static FACING: std::sync::LazyLock<std::sync::Mutex<(u64, std::collections::HashMap<u8, (FacingKey, bool)>)>> =
    std::sync::LazyLock::new(|| std::sync::Mutex::new((0, std::collections::HashMap::new())));

impl RamUnit {
    fn facing_key(&self) -> FacingKey {
        (self.kind, self.shown_by, self.moved)
    }

    /// The BG2 tilemap entry the console draws in the top-right of the unit's cell: the
    /// low ammunition / low fuel icon (tiles 0x33D to 0x33F, palette 10), if any.
    fn low_icon(&self) -> Option<u16> {
        (self.low != 0).then(|| 0xA33C + self.low as u16)
    }

    /// The four tilemap entries the console draws the unit with.
    fn entries(&self) -> Option<[u16; 4]> {
        if self.kind == 25 {
            return None;
        }
        let base = self.base;
        let bank = self.bank << 12;
        // (`0x0802216C`: armies 1 and 3 are drawn mirrored; a unit that has moved is
        // drawn as the army whose turn it is.)
        let mut e = if self.mirrored {
            [base + 1, base, base + 3, base + 2].map(|t| t | 0x400)
        } else {
            [base, base + 1, base + 2, base + 3]
        }
        .map(|t| t | bank);
        // The bottom-left tile: the fourth icon, the cargo mark, the capture mark, the
        // hidden mark, in that order of the game's.
        if self.icon4 {
            e[2] = 0x2ae | bank;
        } else if self.raw[7] | self.raw[8] != 0 {
            e[2] = 0x2ab | bank;
        } else if self.raw[5] >> 3 != 0 {
            e[2] = 0x2ac | bank;
        } else if self.flags & 0x20 != 0 {
            e[2] = 0x2ad | bank;
        }
        // The bottom-right tile: "?" when the HP is hidden, else the HP digit (1 to 9).
        if self.hide_hp {
            e[3] = 0x2af | bank;
        } else if self.hp != 0 {
            let digit = (self.hp as u16 - 1) / 10 + 1;
            if digit <= 9 {
                e[3] = 0x2a1 + digit | bank;
            }
        }
        Some(e)
    }
}

/// Every unit on the map.
/// The 16 x 16 picture of unit record `id` as the console draws it (its four tiles in BG tile
/// RAM, the army's palette bank, mirrored as the army is), 0 transparent, else 0x8000 | RGB555.
/// For the menus' Drop icon (the cargo's picture); no HP digit or marks.
pub(crate) fn unit_picture(core: &Core, id: u8) -> Option<Vec<u16>> {
    let u = ram_units(core).into_iter().find(|u| u.id == id)?;
    let tiles = if u.mirrored { [u.base + 1, u.base, u.base + 3, u.base + 2] } else { [u.base, u.base + 1, u.base + 2, u.base + 3] };
    let mut out = vec![0u16; 256];
    // (BG1's tiles; the army's own colours, not the greyed ones a unit that has moved wears)
    let char_base = 0x0600_0000 + ((core.raw_read_16(0x0400_000A, -1) as u32 >> 2) & 3) * 0x4000;
    let bank = if u.five { if u.army >= 5 { 11 } else { 12 + (u.army as u32 - 1).min(3) } } else { 12 + ((u.army as u32 - 1) & 3) };
    for (k, &t) in tiles.iter().enumerate() {
        let mut data = [0u8; 32];
        core.raw_read_range(char_base + 32 * t as u32, -1, &mut data);
        for y in 0..8usize {
            for x in 0..8usize {
                let sx = if u.mirrored { 7 - x } else { x };
                let b = data[y * 4 + sx / 2];
                let c = (if sx & 1 == 0 { b & 15 } else { b >> 4 }) as u32;
                if c != 0 {
                    let rgb = core.raw_read_16(0x0500_0000 + 2 * (bank * 16 + c), -1);
                    out[((k / 2) * 8 + y) * 16 + (k % 2) * 8 + x] = 0x8000 | (rgb & 0x7FFF);
                }
            }
        }
    }
    Some(out)
}

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
        let moved = buf[1] & 1 != 0;
        let (mirrored, bank, shown_by) = if five {
            (army % 2 == 1, if moved { 9 } else if army >= 5 { 11 } else { 12 + (army as u16 - 1).min(3) }, army)
        } else {
            let r2 = if moved { core.raw_read_16(0x0300_3F2C, -1) as u32 } else { 64 * (army as u32 - 1) };
            let idx = (r2 >> 6) & 3;
            (idx % 2 == 0, if moved { 11 } else { 12 + idx as u16 }, idx as u8 + 1)
        };
        // (The game's own tests: `0x08043050` for the CO pair's table, `0x0802706C`.)
        let player = |a: u8, off: u32| core.raw_read_8(players + 0x3C * a as u32 + off, -1);
        let have_players = (0x0200_0000..0x0400_0000).contains(&players);
        let not_ours = have_players && player(shown_by, 0x1C) & 2 == 0;
        let hide_hp = have_players && not_ours && core.raw_read_8(0x0300_3FC0 + 8, -1) != 0 && {
            let (c1, c2) = (player(army, 0x1D) as u32, player(army, 0x1E) as u32);
            core.raw_read_32(cos + 0x40 + 4 * (c1 * 65 + c2 * 17), -1) & 1 != 0
        };
        let base = {
            let slots = core.raw_read_32(0x0802_61C4, -1);
            let stride = (core.raw_read_16(0x0802_61B2, -1) & 0xFF) as u32;
            let cty = if (0x0800_0000..0x0A00_0000).contains(&cos) && have_players {
                core.raw_read_8(cos + 0x104 * player(shown_by, 0x1D) as u32 + 0x15, -1) as u32
            } else {
                0
            };
            0x235 + 4 * core.raw_read_16(slots + stride * cty + 2 * buf[0] as u32, -1)
        };
        let icon4 = not_ours
            && core.raw_read_8(0x0300_3FC0 + 0xD, -1) != 0
            && core.raw_read_32(crate::roster::table(core) + 0x5C * buf[0] as u32 + 0x14, -1) != 0;
        // (`0x08022618`: ammunition and fuel at most a third of the type's; the table's +0xB
        // and +0x10 are the types' own, 0 for none.)
        let low = {
            let t = crate::roster::table(core) + 0x5C * buf[0] as u32;
            let (max_ammo, max_fuel) = (core.raw_read_8(t + 0xB, -1) as i32, core.raw_read_8(t + 0x10, -1) as i32);
            let ammo = ((u16::from_le_bytes([buf[4], buf[5]]) >> 7) & 0xF) as i32;
            let fuel = (buf[6] & 0x7f) as i32;
            (max_ammo != 0 && ammo <= max_ammo / 3) as u8 + 2 * (max_fuel != 0 && fuel <= max_fuel / 3) as u8
        };
        out.push(RamUnit {
            id: id as u8,
            shown_by,
            moved,
            kind: buf[0],
            flags: buf[1],
            x: buf[2],
            y: buf[3],
            hp: (u16::from_le_bytes([buf[4], buf[5]]) & 0x7f) as u8,
            army,
            country,
            colour,
            raw: buf,
            five,
            mirrored,
            bank,
            base,
            hide_hp,
            icon4,
            low,
        });
    }
    out
}
