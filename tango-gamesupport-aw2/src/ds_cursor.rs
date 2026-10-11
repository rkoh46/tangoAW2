//! Dual Strike's battle-map cursor, imported from the player's own ROM for
//! the tilted map ([`crate::ds_tilt`]): four blue dots on the corners of the
//! cursor's cell and a red arrow standing off one corner.
//!
//! Dual Strike draws both as 3D quads, so they are in the pack's texture
//! files, not in tile form: `bmap/027` holds 4-bit textures one after the
//! other, row by row with no tile order (the arrow is the first 16 x 16, 128
//! bytes, the dot the next 8 x 8, 32 bytes), and `bmap/028` is their 16-colour
//! palette (entry 0 transparent; entry 4 is a colour the game changes at run
//! time and no pixel of either picture uses). Found by dumping a melonDS
//! frame's texture and texture palette VRAM and matching it to the files.
//!
//! Placement, measured on the real frames (`tools/aw2test`: ten missions in
//! all four looks): the dots sit on the four corners of the cursor's cell
//! and are 8 x 8 *screen* pixels whatever the depth (51 of 51 dots match the
//! texture pixel for pixel); the arrow is a quad about one cell across that
//! stands off the cell's corner away from the picture's right and bottom
//! edges (below and right of the cell, flipped as the cell nears them).

use std::sync::OnceLock;

pub struct Art {
    /// 16 x 16 pixels, 0 transparent, else 0x8000 | RGB555.
    pub arrow: Vec<u16>,
    /// 8 x 8.
    pub dot: Vec<u16>,
}

const FILE: &str = "bmap/027";
const PALETTE: &str = "bmap/028";

/// The cursor's pictures, or `None` without the Dual Strike pack.
pub fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(build).as_ref()
}

fn build() -> Option<Art> {
    let pack = crate::ds_pack::pack()?;
    let tex = crate::ds_art::lz10(pack.file(FILE)?)?;
    let pal = pack.file(PALETTE)?;
    if pal.len() < 32 || tex.len() < 160 {
        return None;
    }
    let colour: Vec<u16> = (0..16).map(|i| u16::from_le_bytes([pal[2 * i], pal[2 * i + 1]]) & 0x7fff).collect();
    let decode = |at: usize, n: usize| -> Vec<u16> {
        (0..n)
            .map(|i| {
                let b = tex[at + i / 2];
                let idx = if i & 1 == 0 { b & 15 } else { b >> 4 };
                if idx == 0 {
                    0
                } else {
                    0x8000 | colour[idx as usize]
                }
            })
            .collect()
    };
    Some(Art { arrow: decode(0, 256), dot: decode(128, 64) })
}

/// Which way the arrow stands off the cell: `(left, up)`, from the cell's
/// top-left corner in Dual Strike's 256 x 192 picture. Right and below, unless
/// the cell is near the right edge or the bottom.
pub fn arrow_side(x: f32, y: f32) -> (bool, bool) {
    (x >= 200.0, y >= 135.0)
}

/// The arrow's quad (left, top, width, height) in cells from the cell's
/// top-left corner, per side (fitted to the real frames' red pixels).
fn arrow_box(left: bool, up: bool) -> (f32, f32, f32, f32) {
    match (left, up) {
        (false, false) => (1.0, 0.8, 0.925, 1.0),
        (false, true) => (0.8, -0.9, 1.075, 1.1),
        (true, true) => (-0.8, -0.8, 1.05, 0.925),
        (true, false) => (-0.8, 0.8, 1.0, 1.025),
    }
}

/// Draws the cursor over `map` (`w` x `h`, 0x8000 | RGB555) for the cell
/// `(cx, cy)`; `project` gives a ground point's screen position and the cell's
/// size there, in the picture's own pixels.
pub fn draw(map: &mut [u16], w: usize, h: usize, art: &Art, cell: (i32, i32), project: impl Fn(f32, f32) -> (f32, f32, f32)) {
    // Dual Strike's 256-wide picture is shown 240 wide.
    const S: f32 = 240.0 / 256.0;
    let (cu, cv) = (cell.0 as f32, cell.1 as f32);
    let blit = |map: &mut [u16], pix: &[u16], n: usize, x0: f32, y0: f32, qw: f32, qh: f32, flip: (bool, bool)| {
        for y in (y0.floor() as i32).max(0)..((y0 + qh).ceil() as i32).min(h as i32) {
            let mut v = (((y as f32 + 0.5 - y0) / qh) * n as f32).floor() as i32;
            if !(0..n as i32).contains(&v) {
                continue;
            }
            if flip.1 {
                v = n as i32 - 1 - v;
            }
            for x in (x0.floor() as i32).max(0)..((x0 + qw).ceil() as i32).min(w as i32) {
                let mut u = (((x as f32 + 0.5 - x0) / qw) * n as f32).floor() as i32;
                if !(0..n as i32).contains(&u) {
                    continue;
                }
                if flip.0 {
                    u = n as i32 - 1 - u;
                }
                let p = pix[v as usize * n + u as usize];
                if p != 0 {
                    map[y as usize * w + x as usize] = p;
                }
            }
        }
    };
    for (dx, dy) in [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)] {
        let (fx, fy, c) = project(cu + dx, cv + dy);
        let q = 8.0 * S;
        blit(map, &art.dot, 8, fx + 0.064 * c - q / 2.0, fy - 0.009 * c - q / 2.0, q, q, (false, false));
    }
    let (fx, fy, c) = project(cu, cv);
    let (xd, yd) = ((fx - 120.0) / S + 128.0, (fy - 80.0) / S + 96.0);
    let (left, up) = arrow_side(xd, yd);
    let (bx, by, bw, bh) = arrow_box(left, up);
    blit(map, &art.arrow, 16, fx + bx * c, fy + by * c, bw * c, bh * c, (left, up));
}
