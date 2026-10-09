//! The hidden bonds on the BH Campaign's world map: nothing shows until a
//! bond is earned; from the first earned bond on a small legend sits at the
//! map's top left (below the "CAMPAIGN" title while that shows, at the very
//! top left otherwise): a gold star, "RECRUIT WON OVER" and "BONDS n/m" (the
//! campaign's bonds), in AW2's own font with its outline. Sprites in OBJ
//! tiles the world map leaves free, in an OBJ palette bank no sprite of the
//! frame uses (the title's is one the game uses itself).

use mgba::core::Core;

const OBJ_TILES: u32 = 0x0601_0000;
/// Free OBJ tiles on the world map: the legend's 32 (four 32x16 sprites) and
/// its 16 (four 32x8), and the star's 4.
const LEGEND_A: u32 = 735;
const LEGEND_B: u32 = 772;
const STAR: u32 = 848;
/// OBJ palette banks tried, in order, for the first one no sprite of the frame uses.
const BANKS: [u16; 8] = [13, 12, 11, 10, 9, 7, 6, 4];
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const FONT_GLYPHS: u32 = 0x084C_32E4;
const FONT_WIDTHS: u32 = 0x084C_36E4;
const FONT_TOP: usize = 2;
const FONT_ROWS: usize = 14;

const LEGEND_W: usize = 128;
const LEGEND_H: usize = 24;
const LEGEND_X: i32 = 4;
/// Below the title while it shows, at the top when it is not up.
const LEGEND_Y_TITLE: i32 = 32;
const LEGEND_Y_TOP: i32 = 3;

/// Palette entries: 1 black, 2 white, 3 gold, 4 dark gold, 5 highlight.
const COLOURS: [(usize, u16); 5] = [(1, 0x0000), (2, 0x7FFF), (3, 0x0B5F), (4, 0x01F8), (5, 0x43FF)];

/// A star mask: inside the five-pointed star of radius `r` at the centre.
fn in_star(x: f32, y: f32, cx: f32, cy: f32, r: f32) -> bool {
    let (dx, dy) = (x - cx, cy - y);
    let d = (dx * dx + dy * dy).sqrt();
    if d > r {
        return false;
    }
    let a = dy.atan2(dx);
    let step = std::f32::consts::PI * 2.0 / 5.0;
    let t = (a - std::f32::consts::FRAC_PI_2).rem_euclid(step) - step / 2.0;
    let k = t.abs() / (step / 2.0);
    d <= r * (0.42 + (1.0 - 0.42) * (1.0 - k))
}

/// The 16x16 star, palette indices, outlined.
fn star_pixels() -> Vec<u8> {
    let mut px = vec![0u8; 256];
    for y in 0..16 {
        for x in 0..16 {
            if in_star(x as f32 + 0.5, y as f32 + 0.5, 8.0, 8.6, 7.6) {
                px[y * 16 + x] = if (x + y) % 8 < 3 && y < 8 { 5 } else { 3 };
            }
        }
    }
    let src = px.clone();
    for y in 0..16i32 {
        for x in 0..16i32 {
            if src[(y * 16 + x) as usize] == 0
                && [(-1, 0), (1, 0), (0, -1), (0, 1)].iter().any(|&(dx, dy)| {
                    let (nx, ny) = (x + dx, y + dy);
                    (0..16).contains(&nx) && (0..16).contains(&ny) && src[(ny * 16 + nx) as usize] != 0
                })
            {
                px[(y * 16 + x) as usize] = 1;
            }
        }
    }
    px
}

/// 4bpp tiles of a w x h bitmap in 1D order.
fn to_tiles(px: &[u8], w: usize, h: usize) -> Vec<u8> {
    let mut out = vec![0u8; w * h / 2];
    for ty in 0..h / 8 {
        for tx in 0..w / 8 {
            let t = ty * (w / 8) + tx;
            for r in 0..8 {
                for c in 0..8 {
                    out[32 * t + 4 * r + c / 2] |= (px[(8 * ty + r) * w + 8 * tx + c] & 15) << (4 * (c & 1));
                }
            }
        }
    }
    out
}

fn write_if_changed(core: &mut Core, at: u32, bytes: &[u8]) {
    let mut now = vec![0u8; bytes.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != bytes {
        core.raw_write_range(at, -1, bytes);
    }
}

/// A string in AW2's font into `on` at (x, y); returns the width.
fn font_draw(core: &Core, on: &mut [Vec<bool>], s: &str, x0: usize, y0: usize) -> usize {
    let mut x = x0;
    for c in s.bytes() {
        let cw = core.raw_read_8(FONT_WIDTHS + c as u32, -1) as usize;
        let at = core.raw_read_32(FONT_GLYPHS + 4 * c as u32, -1);
        if (0x0800_0000..0x0A00_0000).contains(&at) {
            let stride = cw.div_ceil(2);
            for cx in 0..cw {
                for r in 0..FONT_ROWS {
                    let b = core.raw_read_8(at + (stride * (FONT_TOP + r) + cx / 2) as u32, -1);
                    if (b >> (4 * (cx & 1))) & 15 != 0 && x + cx < on.len() && y0 + r < on[0].len() {
                        on[x + cx][y0 + r] = true;
                    }
                }
            }
        }
        x += cw + 1;
    }
    x - x0
}

/// The legend's bitmap: room for the star, "RECRUIT WON OVER", "BONDS n/m";
/// white, outlined in black.
fn legend_pixels(core: &Core, n: u32, total: usize) -> Vec<u8> {
    let mut on = vec![vec![false; LEGEND_H]; LEGEND_W];
    font_draw(core, &mut on, "RECRUIT WON OVER", 20, 1);
    font_draw(core, &mut on, &format!("BONDS {n}/{total}"), 1, 12);
    let mut px = vec![0u8; LEGEND_W * LEGEND_H];
    for x in 0..LEGEND_W {
        for y in 0..LEGEND_H {
            if on[x][y] {
                px[y * LEGEND_W + x] = 2;
            } else if [(-1i32, 0i32), (1, 0), (0, -1), (0, 1)].iter().any(|&(dx, dy)| {
                let (nx, ny) = (x as i32 + dx, y as i32 + dy);
                (0..LEGEND_W as i32).contains(&nx) && (0..LEGEND_H as i32).contains(&ny) && on[nx as usize][ny as usize]
            }) {
                px[y * LEGEND_W + x] = 1;
            }
        }
    }
    px
}

fn sprite(core: &mut Core, at: &mut u32, end: u32, x: i32, y: i32, shape: u16, size: u16, tile: u32, pal: u16) {
    if *at + 8 > end || !(-32..240).contains(&x) || !(-32..160).contains(&y) {
        return;
    }
    core.raw_write_16(*at, -1, (y as u16 & 0xFF) | shape << 14);
    core.raw_write_16(*at + 2, -1, (x as u16 & 0x1FF) | size << 14);
    core.raw_write_16(*at + 4, -1, tile as u16 | pal << 12);
    core.raw_write_16(*at + 6, -1, 0);
    *at += 8;
}

/// The sprites of the frame so far (`start..at`): the palette banks they use,
/// and whether one stands at the top left (the title's letters).
fn frame_sprites(core: &Core, start: u32, at: u32) -> (u16, bool) {
    let mut banks = 0u16;
    let mut title = false;
    let mut p = start;
    while p + 8 <= at {
        let (a0, a1, a2) = (core.raw_read_16(p, -1), core.raw_read_16(p + 2, -1), core.raw_read_16(p + 4, -1));
        if a0 & 0x300 != 0x200 {
            banks |= 1 << (a2 >> 12);
            let (y, x) = ((a0 & 0xFF) as i32, (a1 & 0x1FF) as i32);
            // (the title's letters: tall sprites along the top edge)
            if a0 >> 14 == 2 && y < 8 && x < 110 {
                title = true;
            }
        }
        p += 8;
    }
    (banks, title)
}

/// The legend's top: below the title while a sprite stands at the top left
/// (the title's letters), else at the very top.
pub fn legend_y(title: bool) -> i32 {
    if title {
        LEGEND_Y_TITLE
    } else {
        LEGEND_Y_TOP
    }
}

/// At the sprite flush on the world map: the legend, from the first earned
/// bond on, while no dialogue runs.
pub fn flush(core: &mut Core, start: u32, mut at: u32, end: u32) -> u32 {
    if !crate::ds_worldmap::map_screen_up(core) || !crate::ds_campaign::active(core) || crate::onyx::events_running_pub(core) {
        return at;
    }
    let Some(c) = crate::ds_campaign::campaign(core) else { return at };
    let Some(custom) = c.model.custom.as_ref() else { return at };
    let total = custom.counted;
    let n = (crate::ds_campaign::bonds_earned(core) & ((1u32 << total) - 1)).count_ones();
    if n == 0 {
        return at;
    }
    let (banks, title) = frame_sprites(core, start, at);
    let Some(&bank) = BANKS.iter().find(|&&b| banks >> b & 1 == 0) else { return at };
    let mut pal = [0u8; 32];
    for &(i, col) in &COLOURS {
        pal[2 * i..2 * i + 2].copy_from_slice(&col.to_le_bytes());
    }
    for base in [PAL_BUFFER, PAL_RAM] {
        write_if_changed(core, base + 0x200 + 32 * bank as u32, &pal);
    }
    write_if_changed(core, OBJ_TILES + 32 * STAR, &to_tiles(&star_pixels(), 16, 16));
    let px = legend_pixels(core, n, total);
    for s in 0..4usize {
        let mut sub = vec![0u8; 32 * 16];
        for y in 0..16 {
            sub[y * 32..y * 32 + 32].copy_from_slice(&px[y * LEGEND_W + 32 * s..y * LEGEND_W + 32 * s + 32]);
        }
        write_if_changed(core, OBJ_TILES + 32 * (LEGEND_A + 8 * s as u32), &to_tiles(&sub, 32, 16));
        let mut sub = vec![0u8; 32 * 8];
        for y in 0..8 {
            sub[y * 32..y * 32 + 32].copy_from_slice(&px[(16 + y) * LEGEND_W + 32 * s..(16 + y) * LEGEND_W + 32 * s + 32]);
        }
        write_if_changed(core, OBJ_TILES + 32 * (LEGEND_B + 4 * s as u32), &to_tiles(&sub, 32, 8));
    }
    let y = legend_y(title);
    // (the star first: an earlier sprite draws over a later one)
    sprite(core, &mut at, end, LEGEND_X + 1, y - 2, 0, 1, STAR, bank);
    for s in 0..4i32 {
        sprite(core, &mut at, end, LEGEND_X + 32 * s, y, 1, 2, LEGEND_A + 8 * s as u32, bank);
        sprite(core, &mut at, end, LEGEND_X + 32 * s, y + 16, 1, 1, LEGEND_B + 4 * s as u32, bank);
    }
    at
}
