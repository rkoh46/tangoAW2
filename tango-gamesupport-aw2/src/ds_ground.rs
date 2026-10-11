//! The battle map's ground, drawn from the game's state rather than from
//! the console's picture: a cell's four tiles, and the peak or treetops of
//! the cell below over its bottom half, as `BlitMapRow` and Dual Strike's
//! upper layer put them in video memory ([`crate::wasteland`]) but for any
//! cell of the map, on or off the screen the console shows.
//!
//! Read-only: map RAM, fog flags, VRAM tiles (as animated now) and palette
//! RAM; display only (see [`crate::ds_tilt`]).

use mgba::core::Core;

use crate::ds_tilt::Vid;
use crate::wasteland::MAP;

/// Bytes of map RAM it reads: tiles (u16) at `MAP + 0xA22`, rows at `MAP + 0x417A`.
const TILES: u32 = MAP + 0xA22;
const ROWS: u32 = MAP + 0x417A;
const FOG: u32 = MAP + 0x234A;
/// BG3's tiles (the terrain): VRAM offset of its character block.
fn char_base(v: &Vid) -> usize {
    ((v.io[4 + 3] >> 2) & 3) as usize * 0x4000
}

pub struct Ground<'a> {
    look: &'static crate::wasteland::Built,
    pub w: i32,
    pub h: i32,
    v: &'a Vid,
    base: usize,
    tiles: Vec<u16>,
    fog: Vec<u8>,
    /// 16 x 16 pixels per cell, drawn on first use (0: not yet; else 0x8000 | colour).
    cache: Vec<Option<Box<[u16; 256]>>>,
    /// Means to an End's Grand Bolt: the picture's cell for each cell it covers.
    bolt: std::collections::HashMap<(i32, i32), (usize, bool, bool)>,
    /// A second front in the sky: the clouds' entries for each cell.
    sky: Vec<[u16; 4]>,
    /// The flat colour Dual Strike shows beyond the map's edge in this look, and fogged.
    outer: [u16; 2],
}

impl<'a> Ground<'a> {
    /// `v` must already hold BG3's tiles (see [`Ground::load`]).
    pub(crate) fn new(core: &Core, v: &'a Vid) -> Option<Ground<'a>> {
        let biome = crate::wasteland::drawn(core)?;
        let look = crate::wasteland::look(biome)?;
        let (w, h) = (core.raw_read_16(MAP, -1) as i32, core.raw_read_16(MAP + 2, -1) as i32);
        if !(1..=64).contains(&w) || !(1..=64).contains(&h) {
            return None;
        }
        let mut tiles = vec![0u16; (w * h) as usize];
        let mut fog = vec![1u8; (w * h) as usize];
        for y in 0..h {
            let row = core.raw_read_16(ROWS + 2 * y as u32, -1) as u32;
            for x in 0..w {
                let cell = row + x as u32;
                tiles[(y * w + x) as usize] = core.raw_read_16(TILES + 2 * cell, -1);
                fog[(y * w + x) as usize] = core.raw_read_8(FOG + cell, -1);
            }
        }
        let mut bolt = std::collections::HashMap::new();
        if crate::grand_bolt::on(core) {
            for y in 0..h {
                for x in 0..w {
                    if let Some(c) = crate::grand_bolt::cell_at(core, x as u32, y as u32) {
                        bolt.insert((x, y), c);
                    }
                }
            }
        }
        let mut sky = Vec::new();
        if crate::sky_front::on(core) {
            for y in 0..h {
                for x in 0..w {
                    sky.push(crate::sky_front::entries(core, x as u32, y as u32).unwrap_or([0; 4]));
                }
            }
        }
        // (measured on real Dual Strike frames: a flat pale colour, not the map repeated)
        let rgb = match biome {
            crate::wasteland::SNOW => (252u32, 252u32, 252u32),
            crate::wasteland::WASTELAND | crate::wasteland::DESERT | crate::wasteland::GRAND_BOLT_LOOK => (252, 244, 148),
            _ => (220, 244, 124),
        };
        let px = |(r, g, b): (u32, u32, u32)| 0x8000 | ((r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) as u16;
        let fogged = ((rgb.0 + 90) / 2, (rgb.1 + 34) / 2, (rgb.2 + 205) / 2);
        Some(Ground { look, w, h, v, base: char_base(v), tiles, fog, cache: vec![None; (w * h) as usize], bolt, sky, outer: [px(rgb), px(fogged)] })
    }

    /// Loads what [`Ground::new`] needs into `v`.
    pub(crate) fn load(core: &Core, v: &mut Vid) {
        v.ensure(core, char_base(v), 0x8000);
    }

    /// A number that changes when the map does (size and tiles).
    pub fn signature(&self) -> u64 {
        self.tiles
            .iter()
            .fold(((self.w as u64) << 32) | self.h as u64, |a, &t| a.wrapping_mul(1_000_003).wrapping_add(t as u64))
    }

    /// The metatile id of a cell.
    pub fn tile(&self, x: i32, y: i32) -> u16 {
        self.tiles[(y * self.w + x) as usize]
    }

    /// Whether the cell (by index, as [`Ground::locate`] gives it) is a wood or a mountain, which
    /// Dual Strike draws upright.
    pub fn is_tall(&self, ci: usize) -> bool {
        self.look.look.tall.get(self.tiles[ci] as usize).copied().unwrap_or(crate::ds_look::NOT_TALL) != crate::ds_look::NOT_TALL
    }

    /// Whether the cell is hidden by fog.
    pub fn fogged(&self, x: i32, y: i32) -> bool {
        self.fog[(y * self.w + x) as usize] == 0
    }

    fn quad_px(&self, e: u16, x: usize, y: usize) -> u16 {
        let sx = if e & 0x400 != 0 { 7 - x } else { x };
        let sy = if e & 0x800 != 0 { 7 - y } else { y };
        let a = self.base + 32 * (e & 0x3ff) as usize + sy * 4 + sx / 2;
        if a >= 0x18000 {
            return 0;
        }
        let b = self.v.vram[a];
        let c = if sx & 1 == 0 { b & 15 } else { b >> 4 } as usize;
        if c == 0 {
            return 0;
        }
        let bank = (e >> 12) as usize;
        let live = self.v.pal[bank * 16 + c] & 0x7fff;
        // Dual Strike's own colour of the pixel (the four palettes merged some of them): the live
        // palette's weather and fog change it only as they change the merged colour.
        let t = (e & 0x3ff) as usize;
        let k = 64 * t + sy * 8 + sx;
        let (full, merged) = if bank < 4 {
            (self.look.look.full.get(k).copied().unwrap_or(0), self.look.look.colours.get(16 * bank + c).copied().unwrap_or(0))
        } else {
            (
                self.look.look.full_fog.get(k).copied().unwrap_or(0),
                self.look.look.fog.get(16 * (bank & 3) + c).copied().unwrap_or(crate::ds_look::NO_FOG),
            )
        };
        if full & 0x8000 == 0 || merged == crate::ds_look::NO_FOG {
            return 0x8000 | live;
        }
        let (full, merged) = (full & 0x7fff, merged & 0x7fff);
        let ch = |s: u32| {
            let d = ((full >> s) & 31) as i32 - ((merged >> s) & 31) as i32;
            ((((live >> s) & 31) as i32 + d).clamp(0, 31)) as u16
        };
        0x8000 | ch(0) | ch(5) << 5 | ch(10) << 10
    }

    fn draw(&self, x: i32, y: i32) -> Box<[u16; 256]> {
        let l = &self.look.look;
        let fog_add: u16 = if self.fogged(x, y) { 0x4000 } else { 0 };
        let mut out = Box::new([0x8000 | (self.v.pal[0] & 0x7fff); 256]);
        // Means to an End's Grand Bolt has a picture of its own.
        if let (Some(&c), Some(b)) = (self.bolt.get(&(x, y)), crate::grand_bolt::bolt()) {
            let bank = (crate::grand_bolt::PALETTE + if self.fogged(x, y) { 4 } else { 0 }) as usize;
            for k in 0..4usize {
                let (tile, flips) = b.tile(c, k);
                let (qx, qy) = ((k % 2) * 8, (k / 2) * 8);
                for py in 0..8usize {
                    for px in 0..8usize {
                        let sx = if flips & 0x400 != 0 { 7 - px } else { px };
                        let sy = if flips & 0x800 != 0 { 7 - py } else { py };
                        let byte = tile[sy * 4 + sx / 2];
                        let ci = (if sx & 1 == 0 { byte & 15 } else { byte >> 4 }) as usize;
                        if ci != 0 {
                            out[(qy + py) * 16 + qx + px] = 0x8000 | (self.v.pal[bank * 16 + ci] & 0x7fff);
                        }
                    }
                }
            }
            return out;
        }
        let sky = self.sky.get((y * self.w + x) as usize).copied();
        let q = match sky {
            Some(q) => q.map(|e| e.wrapping_add(fog_add)),
            None => l.entries(self.tile(x, y), x as u32, y as u32).map(|e| e.wrapping_add(fog_add)),
        };
        for (k, &e) in q.iter().enumerate() {
            let (qx, qy) = ((k % 2) * 8, (k / 2) * 8);
            for py in 0..8 {
                for px in 0..8 {
                    let c = self.quad_px(e, px, py);
                    if c != 0 {
                        out[(qy + py) * 16 + qx + px] = c;
                    }
                }
            }
        }
        // The peak or treetops of the cell below, over the bottom half.
        if sky.is_none() {
            if let Some(up) = self.upper_pixels(x, y) {
                for (o, &c) in out.iter_mut().zip(up.iter()) {
                    if c != 0 {
                        *o = c;
                    }
                }
            }
        }
        out
    }

    /// The peak or treetops of the cell below (x, y + 1) as they cover the bottom half of cell
    /// (x, y): 16 x 16, 0 where nothing, else `0x8000 | colour`, in Dual Strike's own colours (the
    /// four palettes' merged ones would lose a shade: a desert mountain's pale highlight is a tenth
    /// of its pixels). The tilted map draws the same from the console's BG2 inside its window.
    pub fn upper_pixels(&self, x: i32, y: i32) -> Option<[u16; 256]> {
        if x < 0 || y < 0 || x >= self.w || y + 1 >= self.h {
            return None;
        }
        let l = &self.look.look;
        let o = l.upper_at(self.tile(x, y + 1), x as u32, (y + 1) as u32)?;
        let src = if self.fogged(x, y) { &l.overlays_fog } else { &l.overlays };
        let mut out = [0u16; 256];
        for side in 0..2usize {
            if let Some(over) = src.get(o as usize).and_then(|v| v.get(side)) {
                for py in 0..8usize {
                    for px in 0..8usize {
                        let c = over[py * 8 + px];
                        if c != crate::ds_look::TRANSPARENT {
                            out[(8 + py) * 16 + side * 8 + px] = 0x8000 | (c & 0x7fff);
                        }
                    }
                }
            }
        }
        Some(out)
    }

    /// The cell holding map pixel column `gx` and row `gy` (the map's edge
    /// repeats beyond it), with the pixel's place in it: (cell, x, y).
    pub fn locate(&self, gx: i32, gy: i32) -> (usize, usize, usize) {
        // Beyond the map the ground is mirrored (a repeated edge would streak).
        let reflect = |g: i32, n: i32| {
            let c = g.div_euclid(16);
            let l = g.rem_euclid(16);
            if c < 0 {
                ((-c - 1).min(n - 1), 15 - l)
            } else if c >= n {
                ((2 * n - 1 - c).max(0), 15 - l)
            } else {
                (c, l)
            }
        };
        let ((cx, lx), (cy, ly)) = (reflect(gx, self.w), reflect(gy, self.h));
        ((cy * self.w + cx) as usize, lx as usize, ly as usize)
    }

    /// The flat colour beyond the map's edge at map pixel (gx, gy), None inside the map. It is the
    /// fogged one where the nearest cell of the map is.
    pub fn outside(&self, gx: i32, gy: i32) -> Option<u16> {
        let (cx, cy) = (gx.div_euclid(16), gy.div_euclid(16));
        if (0..self.w).contains(&cx) && (0..self.h).contains(&cy) {
            return None;
        }
        let near = (cy.clamp(0, self.h - 1) * self.w + cx.clamp(0, self.w - 1)) as usize;
        Some(self.outer[(self.fog[near] == 0) as usize])
    }

    /// A cell's 16 x 16 pixels, drawn on first use.
    pub fn cell(&mut self, i: usize) -> &[u16; 256] {
        if self.cache[i].is_none() {
            let (x, y) = (i as i32 % self.w, i as i32 / self.w);
            self.cache[i] = Some(self.draw(x, y));
        }
        self.cache[i].as_ref().unwrap()
    }

    /// The ground pixel at map pixel (gx, gy) (16 per cell); the map's edge
    /// repeats beyond it.
    pub fn px(&mut self, gx: i32, gy: i32) -> u16 {
        let (cx, cy) = ((gx.div_euclid(16)).clamp(0, self.w - 1), (gy.div_euclid(16)).clamp(0, self.h - 1));
        let (lx, ly) = (
            if gx < 0 { 0 } else if gx >= self.w * 16 { 15 } else { gx.rem_euclid(16) },
            if gy < 0 { 0 } else if gy >= self.h * 16 { 15 } else { gy.rem_euclid(16) },
        );
        let i = (cy * self.w + cx) as usize;
        if self.cache[i].is_none() {
            self.cache[i] = Some(self.draw(cx, cy));
        }
        self.cache[i].as_ref().unwrap()[(ly * 16 + lx) as usize]
    }
}

/// The whole map's ground as RGB, 16 x 16 pixels a cell (for tools).
pub fn render_all(core: &Core) -> Option<(usize, usize, Vec<u8>)> {
    let mut v = Vid::read(core);
    Ground::load(core, &mut v);
    let mut g = Ground::new(core, &v)?;
    let (w, h) = (g.w as usize * 16, g.h as usize * 16);
    let lut = crate::ds_tilt::rgba_lut();
    let mut out = Vec::with_capacity(w * h * 3);
    for y in 0..h as i32 {
        for x in 0..w as i32 {
            let c = lut[(g.px(x, y) & 0x7fff) as usize];
            out.extend_from_slice(&c[..3]);
        }
    }
    Some((w, h, out))
}
