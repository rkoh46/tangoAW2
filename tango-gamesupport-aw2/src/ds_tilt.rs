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

// --- The plane -----------------------------------------------------------------
//
// Measured on a real Dual Strike frame (melonDS): rows are about 13 pixels per
// cell near the top and 16.6 near the bottom (a ratio of 1.28) and the columns
// converge toward the top. A pinhole camera looking down at a plane has
// horizontal scale s = S0 / (1 - C v) and row pitch proportional to s squared,
// so the same ratio 1.28 in row pitch is a ratio of sqrt(1.28) = 1.13 in
// width: 0.885 = (1 - C * 160) below. The plane is scaled up about 10% so the
// 160 source rows fill the 160 screen rows (the console's picture has no more
// rows to show than that): cells are 14.1 pixels tall at the top and 18 at
// the bottom, 15.5 and 17.6 wide.

/// Horizontal scale at the top row.
const S0: f32 = 0.97;
/// 1 - C * 160 at the bottom row.
const D_BOT: f32 = 0.885;
const C: f32 = (1.0 - D_BOT) / H as f32;
/// Row pitch at the top; chosen so the 160 source rows end on row 160.
const A: f32 = D_BOT;
const CX: f32 = W as f32 / 2.0;

/// Horizontal scale at source row `v`.
fn scale(v: f32) -> f32 {
    S0 / (1.0 - C * v)
}

/// Screen row of source row `v`.
fn fwd_y(v: f32) -> f32 {
    A * v / (1.0 - C * v)
}

/// Source row under screen row `y`.
fn inv_v(y: f32) -> f32 {
    y / (A + C * y)
}

// --- Video memory ---------------------------------------------------------------

struct Vid {
    io: [u16; 0x30],
    pal: [u16; 512],
    oam: [u16; 512],
    vram: Vec<u8>,
    /// 4 KiB pages of `vram` read so far.
    loaded: [bool; 24],
}

impl Vid {
    fn read(core: &Core) -> Vid {
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
    fn ensure(&mut self, core: &Core, addr: usize, len: usize) {
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

    fn u16_at(&self, a: usize) -> u16 {
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
}

const OBJ_TILES: usize = 0x10000;

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
        (8, 8, 666..=674) if pal == 4 => Class::Ground,
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
        let tile = (a2 & 0x3ff) as usize;
        let pal_bank = (a2 >> 12) as usize;
        let (tw, th) = ((w / 8) as usize, (h / 8) as usize);
        let mut pix = vec![0u16; (w * h) as usize];
        for ty in 0..th {
            for tx in 0..tw {
                let src_tx = if a1 & 0x1000 != 0 { tw - 1 - tx } else { tx };
                let src_ty = if a1 & 0x2000 != 0 { th - 1 - ty } else { ty };
                let mut t = if one_d {
                    tile + src_ty * tw * if color8 { 2 } else { 1 } + src_tx * if color8 { 2 } else { 1 }
                } else {
                    tile + src_ty * 32 + src_tx * if color8 { 2 } else { 1 }
                };
                t &= 0x3ff;
                let bytes = if color8 { 64 } else { 32 };
                let addr = OBJ_TILES + t * 32;
                if addr + bytes > 0x18000 {
                    continue;
                }
                v.ensure(core, addr, bytes);
                for py in 0..8usize {
                    for pxl in 0..8usize {
                        let (sx, sy) = (
                            if a1 & 0x1000 != 0 { 7 - pxl } else { pxl },
                            if a1 & 0x2000 != 0 { 7 - py } else { py },
                        );
                        let c = if color8 {
                            v.vram[addr + sy * 8 + sx] as usize
                        } else {
                            let b = v.vram[addr + sy * 4 + sx / 2];
                            (if sx & 1 == 0 { b & 15 } else { b >> 4 }) as usize
                        };
                        if c != 0 {
                            let color = if color8 {
                                v.pal[256 + c]
                            } else {
                                v.pal[256 + pal_bank * 16 + c]
                            };
                            pix[(ty * 8 + py) * w as usize + tx * 8 + pxl] = 0x8000 | (color & 0x7fff);
                        }
                    }
                }
            }
        }
        out.push(Obj {
            x,
            y,
            w,
            h,
            pri: ((a2 >> 10) & 3) as u8,
            idx,
            class: obj_class(a0, a2, w, h),
            pix,
        });
    }
    Some(out)
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

    /// Layer-enable bits along a row.
    fn row(&self, y: i32) -> [u8; W] {
        let mut out = [self.outside; W];
        for i in (0..2).rev() {
            if !self.on[i] {
                continue;
            }
            let r = self.rect[i];
            let yin = if r[2] <= r[3] {
                y >= r[2] && y < r[3]
            } else {
                y >= r[2] || y < r[3]
            };
            if !yin {
                continue;
            }
            for (x, o) in out.iter_mut().enumerate() {
                let x = x as i32;
                let xin = if r[0] <= r[1] {
                    x >= r[0] && x < r[1]
                } else {
                    x >= r[0] || x < r[1]
                };
                if xin {
                    *o = self.inside[i];
                }
            }
        }
        out
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

fn blend_alpha(a: Px, b: Px, eva: u32, evb: u32) -> Px {
    let ch = |s: u32| {
        let x = (a as u32 >> s) & 31;
        let y = (b as u32 >> s) & 31;
        ((x * eva + y * evb) >> 4).min(31)
    };
    0x8000 | (ch(0) | ch(5) << 5 | ch(10) << 10) as u16
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

fn rgba_lut() -> &'static Vec<[u8; 4]> {
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
    /// The foot's source position: the point on the ground it stands on.
    fx: f32,
    fy: f32,
    /// Top-left of the picture relative to the foot, in source pixels.
    ox: f32,
    oy: f32,
    /// Draw order among equal depths: higher is in front.
    rank: u8,
    last: bool,
}

/// Rewrites `rgba` (the console's 240 x 160 picture) as Dual Strike's tilted
/// battle map, when that is what is on screen. Nothing else changes.
pub fn apply(core: &Core, rgba: &mut [u8]) {
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
    let bldalpha = v.io[0x29];
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
    // --- The flat ground ---
    let mut ground = vec![backdrop; W * H];
    for i in 0..W * H {
        if layers[3][i] != 0 {
            ground[i] = layers[3][i];
        }
    }
    if bg0_ground {
        let first = bldcnt & 1 != 0;
        let second = bldcnt & 0x0800 != 0;
        let (eva, evb) = ((bldalpha & 31).min(16) as u32, ((bldalpha >> 8) & 31).min(16) as u32);
        for i in 0..W * H {
            let p = layers[0][i];
            if p != 0 {
                ground[i] = if bld_mode == 1 && first && second {
                    blend_alpha(p, ground[i], eva, evb)
                } else {
                    p
                };
            }
        }
    }
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
                    ground[sy as usize * W + sx as usize] = p;
                }
            }
        }
    }

    // --- Billboards ---
    let mut boards: Vec<Billboard> = Vec::new();
    let ground_hofs = bgs[3].hofs;
    let ground_vofs = bgs[3].vofs;
    for b in [1usize, 2] {
        let bg = &bgs[b];
        if !bg.on {
            continue;
        }
        let cx0 = bg.hofs.div_euclid(16);
        let cy0 = bg.vofs.div_euclid(16);
        for cy in cy0 - 1..=cy0 + 10 {
            for cx in cx0 - 1..=cx0 + 15 {
                // Anything in the cell? (Its four tiles.)
                if (0..4).all(|k| {
                    let e = bg.entry(&v, cx * 2 + k % 2, cy * 2 + k / 2);
                    bg.tile_blank(&v, (e & 0x3ff) as usize)
                }) {
                    continue;
                }
                let (sx0, sy0) = (cx * 16 - bg.hofs, cy * 16 - bg.vofs);
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
                let fx = (cx * 16 - ground_hofs + 8) as f32;
                let fy = (cy * 16 - ground_vofs + 16) as f32;
                boards.push(Billboard {
                    pix,
                    w: 16,
                    h: 16,
                    fx,
                    fy,
                    ox: sx0 as f32 - fx,
                    oy: sy0 as f32 - fy,
                    rank: (3 - bg.pri) * 2,
                    last: false,
                });
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
            fx,
            fy,
            ox: o.x as f32 - fx,
            oy: o.y as f32 - fy,
            rank: (3 - o.pri) * 2 + 1,
            last: o.class == Class::Pointer,
        });
    }
    boards.sort_by(|a, b| {
        (a.last, a.fy, a.rank)
            .partial_cmp(&(b.last, b.fy, b.rank))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let t_boards = t0.elapsed();
    // --- The tilted map ---
    let mut map = vec![0u16; W * H];
    for y in 0..H {
        let v_src = inv_v(y as f32 + 0.5);
        let s = scale(v_src);
        let sy = (v_src.floor() as i32).clamp(0, H as i32 - 1) as usize;
        for x in 0..W {
            let sx = (CX + ((x as f32 + 0.5) - CX) / s).floor() as i32;
            // Beyond the picture's sides: mirrored.
            let sx = if sx < 0 {
                -sx - 1
            } else if sx >= W as i32 {
                2 * W as i32 - sx - 1
            } else {
                sx
            }
            .clamp(0, W as i32 - 1) as usize;
            map[y * W + x] = ground[sy * W + sx];
        }
    }
    for bb in &boards {
        let s = scale(bb.fy);
        let dfx = CX + (bb.fx - CX) * s;
        let dfy = fwd_y(bb.fy);
        let left = dfx + bb.ox * s;
        let top = dfy + bb.oy * s;
        let right = left + bb.w as f32 * s;
        let bottom = top + bb.h as f32 * s;
        let (x0, x1) = ((left.floor() as i32).max(0), (right.ceil() as i32).min(W as i32));
        let (y0, y1) = ((top.floor() as i32).max(0), (bottom.ceil() as i32).min(H as i32));
        for y in y0..y1 {
            let v = ((y as f32 + 0.5 - top) / s).floor() as i32;
            if !(0..bb.h).contains(&v) {
                continue;
            }
            for x in x0..x1 {
                let u = ((x as f32 + 0.5 - left) / s).floor() as i32;
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
