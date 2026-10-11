//! The wall behind Dual Strike's CO pages ([`crate::ds_co_page`]): the faint watermark of the army crests, the Dual Strike
//! title bands and the arc at the right edge, as Dual Strike's page shows them.
//!
//! Dual Strike builds the page's background from two layers of its own: BG3 is the wall (`ohashi/res_wall_single`: 768 tiles,
//! a 256 x 512 map and its palette), and BG2 over it a white sheet with the arc cut out
//! (`ohashi/res_syoguninfo`: 128 tiles, a 32 x 24 map and a palette) that the hardware blends in at 12/16, so the wall
//! shows through the sheet at a quarter of its strength and in full where the sheet is not. This module redoes that blend
//! once, at the page's scroll, for the part of the picture our 240 x 160 page shows (its bottom right: the BACK button is
//! at the same place as Dual Strike's) and fits it into eight 15-colour banks of BG2 tiles. Everything that is read comes
//! from the pack (the player's own cartridge); with no pack the pages keep their plain white.

use std::collections::HashMap;
use std::sync::OnceLock;

/// Where our 240 x 160 picture lies in Dual Strike's 256 x 192 one.
const ORIGIN: (usize, usize) = (16, 32);
/// The wall's vertical scroll (Dual Strike scrolls it slowly; this puts the title bands under the page's header).
const SCROLL_Y: usize = 213;
/// Where the sheet's palette is in `ohashi/res_syoguninfo`.
const SHEET_PALETTE: usize = 2024;
/// BG2's sheet is blended over BG3 at EVA 12, EVB 4 (of 16).
const EVA: u32 = 12;
const EVB: u32 = 4;

/// The wall as BG2's tiles, tilemap (32 x 32 entries; the page uses 30 x 20) and the eight palette banks it is
/// fitted to (BG palette banks 8 to 15), and the picture they make.
pub struct Wall {
    pub chars: Vec<u8>,
    pub map: Vec<u8>,
    pub pal: Vec<u8>,
    /// The 240 x 160 picture the tiles make (BGR555), for previews and tests.
    pub pix: Vec<u16>,
    /// Each of the 600 cells' palette bank (8 to 15).
    pub banks: Vec<u8>,
}

fn rgb(c: u16) -> [i32; 3] {
    [(c & 31) as i32, ((c >> 5) & 31) as i32, ((c >> 10) & 31) as i32]
}

fn dist(a: u16, b: u16) -> u32 {
    let (x, y) = (rgb(a), rgb(b));
    (0..3).map(|i| ((x[i] - y[i]) * (x[i] - y[i])) as u32).sum()
}

/// The 4bpp tile data's index at pixel `(x, y)` of tile `t` with the map entry's flips.
fn tile_px(tiles: &[u8], e: u16, x: usize, y: usize) -> u8 {
    let t = (e & 0x3FF) as usize;
    let x = if e & 0x400 != 0 { 7 - x } else { x };
    let y = if e & 0x800 != 0 { 7 - y } else { y };
    match tiles.get(32 * t + 4 * y + x / 2) {
        Some(b) => (b >> (4 * (x & 1))) & 15,
        None => 0,
    }
}

fn entry(map: &[u8], i: usize) -> u16 {
    match map.get(2 * i..2 * i + 2) {
        Some(b) => u16::from_le_bytes([b[0], b[1]]),
        None => 0,
    }
}

/// Dual Strike's blended picture, 256 x 192 (BGR555).
fn composite() -> Option<Vec<u16>> {
    let pack = crate::ds_pack::pack()?;
    let wall = pack.file("ohashi/res_wall_single")?;
    let sheet = pack.file("ohashi/res_syoguninfo")?;
    // Their palettes: the wall's are the file's last 32 bytes, the sheet's 32 bytes at 2024 (the page puts them in banks 15
    // and 1).
    let pal_at = |b: &[u8], at: usize| -> Option<Vec<u16>> {
        let p = b.get(at..at + 32)?;
        Some((0..16).map(|i| u16::from_le_bytes([p[2 * i], p[2 * i + 1]])).collect())
    };
    let pal3 = pal_at(wall, wall.len().checked_sub(32)?)?;
    let pal2 = pal_at(sheet, SHEET_PALETTE)?;
    // The wall: tiles, then (on the next four-byte boundary) its 256 x 512 map.
    let t3 = crate::ds_art::lz10(wall)?;
    let m3 = crate::ds_art::lz10(wall.get((crate::ds_art::lz10_end(wall)? + 3) & !3..)?)?;
    // The sheet: a palette of its own (not used here), tiles, then the 32 x 24 map.
    let s0 = 32;
    let t2 = crate::ds_art::lz10(sheet.get(s0..)?)?;
    let m2 = crate::ds_art::lz10(sheet.get((s0 + crate::ds_art::lz10_end(sheet.get(s0..)?)? + 3) & !3..)?)?;
    let mut out = vec![0u16; 256 * 192];
    for y in 0..192usize {
        for x in 0..256usize {
            let y3 = (y + SCROLL_Y) % 512;
            // (a 256 x 512 map is two screen blocks, one under the other)
            let e3 = entry(&m3, (y3 / 8 / 32) * 1024 + (y3 / 8 % 32) * 32 + x / 8);
            let i3 = tile_px(&t3, e3, x % 8, y3 % 8) as usize;
            let c3 = if i3 != 0 { pal3[i3] } else { 0 };
            let e2 = entry(&m2, (y / 8) * 32 + x / 8);
            let i2 = tile_px(&t2, e2, x % 8, y % 8) as usize;
            out[256 * y + x] = if i2 != 0 {
                let (a, b) = (rgb(pal2[i2]), rgb(c3));
                let ch = |k: usize| ((EVA * a[k] as u32 + EVB * b[k] as u32) / 16).min(31) as u16;
                ch(0) | ch(1) << 5 | ch(2) << 10
            } else {
                c3
            };
        }
    }
    Some(out)
}

/// The picture fitted to tiles and banks: (the banks' colours, each cell's bank, each pixel's index).
fn quantize(pix: &[u16]) -> (Vec<Vec<u16>>, Vec<usize>, Vec<u8>) {
    // Each cell's colours and how many pixels have them.
    let mut cells: Vec<Vec<(u16, u32)>> = Vec::new();
    for cy in 0..20 {
        for cx in 0..30 {
            let mut m: HashMap<u16, u32> = HashMap::new();
            for y in 0..8 {
                for x in 0..8 {
                    *m.entry(pix[240 * (8 * cy + y) + 8 * cx + x]).or_default() += 1;
                }
            }
            let mut v: Vec<(u16, u32)> = m.into_iter().collect();
            v.sort_by_key(|&(c, n)| (std::cmp::Reverse(n), c));
            cells.push(v);
        }
    }
    let mut order: Vec<usize> = (0..cells.len()).collect();
    order.sort_by_key(|&i| (std::cmp::Reverse(cells[i].len()), i));
    let mut banks: Vec<Vec<u16>> = Vec::new();
    let mut of = vec![0usize; cells.len()];
    for &i in &order {
        let cell = &cells[i];
        // The bank that holds this cell's colours with the fewest new ones.
        let mut best: Option<(usize, usize)> = None;
        for (b, bank) in banks.iter().enumerate() {
            let new = cell.iter().filter(|(c, _)| !bank.contains(c)).count();
            if bank.len() + new <= 15 && best.map_or(true, |(_, n)| new < n) {
                best = Some((b, new));
            }
        }
        if let Some((b, _)) = best {
            for (c, _) in cell {
                if !banks[b].contains(c) {
                    banks[b].push(*c);
                }
            }
            of[i] = b;
        } else if banks.len() < 8 {
            banks.push(cell.iter().take(15).map(|(c, _)| *c).collect());
            of[i] = banks.len() - 1;
        } else {
            // No room: the bank that costs the least error (the colours it lacks go to their nearest).
            let cost = |bank: &Vec<u16>| -> u64 {
                cell.iter()
                    .map(|&(c, n)| bank.iter().map(|&k| dist(c, k)).min().unwrap_or(0) as u64 * n as u64)
                    .sum()
            };
            of[i] = (0..banks.len()).min_by_key(|&b| cost(&banks[b])).unwrap_or(0);
        }
    }
    let mut idx = vec![0u8; 240 * 160];
    for cy in 0..20 {
        for cx in 0..30 {
            let bank = &banks[of[30 * cy + cx]];
            for y in 0..8 {
                for x in 0..8 {
                    let c = pix[240 * (8 * cy + y) + 8 * cx + x];
                    let k = (0..bank.len()).min_by_key(|&k| dist(c, bank[k])).unwrap_or(0);
                    idx[240 * (8 * cy + y) + 8 * cx + x] = 1 + k as u8;
                }
            }
        }
    }
    (banks, of, idx)
}

fn build() -> Option<Wall> {
    let full = composite()?;
    let mut pix = vec![0u16; 240 * 160];
    for y in 0..160 {
        for x in 0..240 {
            pix[240 * y + x] = full[256 * (y + ORIGIN.1) + x + ORIGIN.0];
        }
    }
    let (banks, of, idx) = quantize(&pix);
    let mut tiles: Vec<[u8; 32]> = Vec::new();
    let mut index: HashMap<[u8; 32], u16> = HashMap::new();
    let mut map = vec![0u8; 0x800];
    for cy in 0..20 {
        for cx in 0..30 {
            let bank = of[30 * cy + cx];
            let mut t = [0u8; 32];
            for y in 0..8 {
                for x in 0..8 {
                    t[4 * y + x / 2] |= idx[240 * (8 * cy + y) + 8 * cx + x] << (4 * (x & 1));
                }
            }
            let k = *index.entry(t).or_insert_with(|| {
                tiles.push(t);
                (tiles.len() - 1) as u16
            });
            let e = k | ((8 + bank) as u16) << 12;
            map[2 * (32 * cy + cx)..2 * (32 * cy + cx) + 2].copy_from_slice(&e.to_le_bytes());
        }
    }
    if tiles.len() > MAX_TILES {
        return None;
    }
    // What the tiles make, through their banks.
    let mut made = vec![0u16; 240 * 160];
    for cy in 0..20 {
        for cx in 0..30 {
            let bank = &banks[of[30 * cy + cx]];
            for y in 0..8 {
                for x in 0..8 {
                    let i = idx[240 * (8 * cy + y) + 8 * cx + x] as usize;
                    made[240 * (8 * cy + y) + 8 * cx + x] = bank.get(i - 1).copied().unwrap_or(0);
                }
            }
        }
    }
    let mut pal = Vec::with_capacity(256);
    for b in 0..8 {
        let bank = banks.get(b).cloned().unwrap_or_default();
        for i in 0..16 {
            let c = if i == 0 { bank.first().copied().unwrap_or(0) } else { bank.get(i - 1).copied().unwrap_or(0) };
            pal.extend_from_slice(&c.to_le_bytes());
        }
    }
    Some(Wall { chars: tiles.concat(), map, pal, pix: made, banks: of.iter().map(|&b| 8 + b as u8).collect() })
}

/// BG2's char block (0x8000) holds this many tiles before BG3's screen block.
pub const MAX_TILES: usize = 960;

/// The wall, built once from the pack.
pub fn wall() -> Option<&'static Wall> {
    static WALL: OnceLock<Option<Wall>> = OnceLock::new();
    WALL.get_or_init(build).as_ref()
}
