//! The hidden bonds on the BH Campaign's world map (nothing shows until a
//! bond is earned): a small badge on the recruit mission's panel once its
//! bond is earned, and a legend that explains it, from the first earned bond
//! on: the badge, "RECRUIT WON OVER" and "BONDS n/m" (the count of the
//! campaign's bonds), in AW2's own font, in a framed box at the map's bottom left (or, with
//! `TANGOAW2_BOND_LEGEND=key`, only while SELECT is held). The badge's art
//! is `TANGOAW2_BOND_BADGE` 1 a drawn gold star, 2 AW2's own small tag star
//! (ROM `0x08102C64`), 3 a Black Hole roundel with a star (default 3).
//! Sprites in OBJ tiles the world map leaves free.

use mgba::core::Core;

const OBJ_TILES: u32 = 0x0601_0000;
/// Free OBJ tiles on the world map: the legend's 32 (four 32x16 sprites)
/// and its 16 (four 32x8), and the badge's 4.
const LEGEND_A: u32 = 735;
const LEGEND_B: u32 = 772;
const BADGE: u32 = 848;
const PALETTE: u16 = 14;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const FONT_GLYPHS: u32 = 0x084C_32E4;
const FONT_WIDTHS: u32 = 0x084C_36E4;
const FONT_TOP: usize = 2;
const FONT_ROWS: usize = 14;
const TAG_STAR: u32 = 0x0810_2C64;
const INFO_LOOP: u32 = 0x0807_7791;
const KEYINPUT: u32 = 0x0400_0130;
const SELECT: u16 = 1 << 2;

const LEGEND_W: usize = 128;
const LEGEND_H: usize = 24;
/// The legend's place and the badge's on the mission panel.
const LEGEND_AT: (i32, i32) = (4, 128);
const BADGE_AT: (i32, i32) = (219, 47);

/// Palette entries: 1 black, 2 white, 3 gold, 4 dark gold, 5 highlight, 6
/// purple, 7 light purple; 9..15 the tag star's.
const COLOURS: [(usize, u16); 15] = [
    (1, 0x0000),
    (2, 0x7FFF),
    (3, 0x0B5F),
    (4, 0x01F8),
    (5, 0x43FF),
    (6, 0x50D0),
    (7, 0x71D8),
    (8, 0x77DF),
    (9, 0x0000),
    (10, 0x5FFF),
    (11, 0x027F),
    (12, 0x77DC),
    (13, 0x6B39),
    (14, 0x35F1),
    (15, 0x0000),
];

fn style() -> u8 {
    static S: std::sync::OnceLock<u8> = std::sync::OnceLock::new();
    *S.get_or_init(|| std::env::var("TANGOAW2_BOND_BADGE").ok().and_then(|v| v.parse().ok()).filter(|v| (1..=3).contains(v)).unwrap_or(3))
}

fn key_legend() -> bool {
    static S: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *S.get_or_init(|| std::env::var("TANGOAW2_BOND_LEGEND").is_ok_and(|v| v == "key"))
}

/// A star mask: inside the five-pointed star of radius `r` at the centre.
fn in_star(x: f32, y: f32, cx: f32, cy: f32, r: f32) -> bool {
    let (dx, dy) = (x - cx, cy - y);
    let d = (dx * dx + dy * dy).sqrt();
    if d > r {
        return false;
    }
    let a = dy.atan2(dx);
    // The star's edge radius at this angle (points up): inner 0.42 r.
    let step = std::f32::consts::PI * 2.0 / 5.0;
    let t = (a - std::f32::consts::FRAC_PI_2).rem_euclid(step) - step / 2.0;
    let k = t.abs() / (step / 2.0);
    d <= r * (0.42 + (1.0 - 0.42) * (1.0 - k))
}

/// The 16x16 badge, palette indices.
fn badge_pixels() -> Vec<u8> {
    let mut px = vec![0u8; 256];
    match style() {
        1 => {
            for y in 0..16 {
                for x in 0..16 {
                    if in_star(x as f32 + 0.5, y as f32 + 0.5, 8.0, 8.6, 7.6) {
                        px[y * 16 + x] = if (x + y) % 8 < 3 && y < 8 { 5 } else { 3 };
                    }
                }
            }
        }
        2 => {
            // (set below from the ROM's tag star: 8x8 at the badge's top left)
        }
        _ => {
            for y in 0..16 {
                for x in 0..16 {
                    let (dx, dy) = (x as f32 + 0.5 - 8.0, y as f32 + 0.5 - 8.0);
                    let d = (dx * dx + dy * dy).sqrt();
                    px[y * 16 + x] = if d > 7.7 {
                        0
                    } else if d > 6.7 {
                        1
                    } else if d > 5.2 {
                        7
                    } else if in_star(x as f32 + 0.5, y as f32 + 0.5, 8.0, 8.4, 5.4) {
                        3
                    } else {
                        6
                    };
                }
            }
        }
    }
    // Outline the drawn star.
    if style() == 1 {
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

/// The legend's bitmap: the badge's room, "RECRUIT WON OVER", "BONDS n/m".
fn legend_pixels(core: &Core, n: u32, total: usize) -> Vec<u8> {
    let mut on = vec![vec![false; LEGEND_H]; LEGEND_W];
    font_draw(core, &mut on, "RECRUIT WON OVER", 22, 2);
    font_draw(core, &mut on, &format!("BONDS {n}/{total}"), 22, 11);
    // A framed box in the panels' style: cream, a purple frame.
    let mut px = vec![8u8; LEGEND_W * LEGEND_H];
    for x in 0..LEGEND_W {
        for y in 0..LEGEND_H {
            let edge = x.min(LEGEND_W - 1 - x).min(y).min(LEGEND_H - 1 - y);
            px[y * LEGEND_W + x] = match edge {
                0 => 6,
                1 => 7,
                _ if on[x][y] => 1,
                _ => 8,
            };
        }
    }
    px
}

fn info_open(core: &Core) -> bool {
    (0..30).any(|k| core.raw_read_32(0x0200_D610 + 0x6C * k + 0x10, -1) == INFO_LOOP && core.raw_read_32(0x0200_D610 + 0x6C * k, -1) != 0)
}

fn sprite(core: &mut Core, at: &mut u32, end: u32, x: i32, y: i32, shape: u16, size: u16, tile: u32) {
    if *at + 8 > end || !(-32..240).contains(&x) || !(-32..160).contains(&y) {
        return;
    }
    core.raw_write_16(*at, -1, (y as u16 & 0xFF) | shape << 14);
    core.raw_write_16(*at + 2, -1, (x as u16 & 0x1FF) | size << 14);
    core.raw_write_16(*at + 4, -1, tile as u16 | PALETTE << 12);
    core.raw_write_16(*at + 6, -1, 0);
    *at += 8;
}

/// At the sprite flush on the world map: the badge on the open panel of a
/// recruit mission whose bond is earned, and the legend.
pub fn flush(core: &mut Core, mut at: u32, end: u32) -> u32 {
    if !crate::ds_worldmap::map_screen_up(core) || !crate::ds_campaign::active(core) {
        return at;
    }
    let Some(c) = crate::ds_campaign::campaign(core) else { return at };
    let Some(custom) = c.model.custom.as_ref() else { return at };
    let earned = crate::ds_campaign::bonds_earned(core);
    let n = (earned & ((1u32 << custom.bonds.len()) - 1)).count_ones();
    if n == 0 {
        return at;
    }
    let mission = core.raw_read_32(crate::ds_worldmap::S_MISSION, -1) as u8;
    let on_panel = info_open(core) && custom.marks.iter().any(|&(m, k)| m == mission && earned >> k & 1 != 0);
    // (the open panel brings the ENEMY strip along the bottom: no legend then)
    let legend = !info_open(core) && (!key_legend() || core.raw_read_16(KEYINPUT, -1) & SELECT == 0);
    let total = custom.bonds.len();
    // Palette 14 and the badge's tiles.
    let mut pal = [0u8; 32];
    for &(i, col) in &COLOURS {
        pal[2 * i..2 * i + 2].copy_from_slice(&col.to_le_bytes());
    }
    for base in [PAL_BUFFER, PAL_RAM] {
        write_if_changed(core, base + 0x200 + 32 * PALETTE as u32, &pal);
    }
    let mut art = badge_pixels();
    if style() == 2 {
        let mut star = [0u8; 32];
        core.raw_read_range(TAG_STAR, -1, &mut star);
        for r in 0..8 {
            for c in 0..8 {
                art[r * 16 + c] = (star[4 * r + c / 2] >> (4 * (c & 1))) & 15;
            }
        }
    }
    write_if_changed(core, OBJ_TILES + 32 * BADGE, &to_tiles(&art, 16, 16));
    // (a 16x16 sprite reads its four tiles as two rows of two: 1D order of the 2x2 block)
    let badge_shape = if style() == 2 { (0, 0) } else { (0, 1) };
    if on_panel {
        sprite(core, &mut at, end, BADGE_AT.0, BADGE_AT.1, badge_shape.0, badge_shape.1, BADGE);
    }
    if legend {
        let px = legend_pixels(core, n, total);
        // Rows 0..16 in four 32x16 sprites, rows 16..24 in four 32x8.
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
        // (the badge first: an earlier sprite draws over a later one)
        // The badge itself beside the legend's first line.
        sprite(core, &mut at, end, LEGEND_AT.0 + 4, LEGEND_AT.1 + 4, badge_shape.0, badge_shape.1, BADGE);
        for s in 0..4i32 {
            // 32x16: wide (shape 1), size 2; 32x8: wide, size 1.
            sprite(core, &mut at, end, LEGEND_AT.0 + 32 * s, LEGEND_AT.1, 1, 2, LEGEND_A + 8 * s as u32);
            sprite(core, &mut at, end, LEGEND_AT.0 + 32 * s, LEGEND_AT.1 + 16, 1, 1, LEGEND_B + 4 * s as u32);
        }
    }
    at
}
