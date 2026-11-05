//! Gauntlet's mission card says GAUNTLET, not MISSION.
//!
//! The Gauntlet runs through AW2's campaign mission proc, so its map opens on AW2's title card: "MISSION n" above the map's
//! name and the seal behind it, stamped "MISSION START". In the Gauntlet the number means nothing (it is the map's place in
//! the definition, not in the selector's list) and the word is wrong, so while the Gauntlet's session is on:
//!
//! - the card's word (three 32x16 sprites, OBJ tiles 0..24, drawn at x = 104) is repainted as GAUNTLET and drawn 18 px to
//!   the right so it ends where the number did; the number's tiles (28 + 4 per digit) are blanked;
//! - the seal's band (BG2, an affine 256x256 picture of 8 bit tiles, the map at 0x06007800 and the tiles at 0x06008000;
//!   the band between the two rules is rows 74..=85, x 26..=132, its tiles used by no other cell) is cleared and set again
//!   as GAUNTLET in the stamp's own red ramp.
//!
//! The letters are the title font's (`online_art::TitleFont`, the letters the Gauntlet's army screen already says GAUNTLET
//! in): the fill's pixels, columns as they are, rows area-averaged down to the height the card's own word has (15 rows; 12
//! in the seal). Nothing from the game is stored: the art is made from the ROM's font when the card opens, and written each
//! frame the card runs (the card's own loads are not at a fixed point; the write is skipped when VRAM already has it). Every other
//! campaign's card is untouched (the traps do nothing outside the Gauntlet's session).

use std::sync::OnceLock;

use mgba::core::Core;

use crate::online_art::TitleFont;

/// The card's frame routines (the name typing, the settled card, the card's last frames): the pictures are in VRAM by the time
/// the first of them runs, so each starts by making sure the word and the stamp are the Gauntlet's.
const FRAME: [u32; 3] = [0x0807_C034, 0x0807_C2D4, 0x0807_C46C];
/// The two routines that draw the word's template (`movs r1, #0x68` just before): the call to each.
const WORD_DRAW: [u32; 2] = [0x0807_C362, 0x0807_C47A];
/// The word's x on AW2's card, and how far GAUNTLET moves it right (its right edge then sits where the number's did, x = 218).
const WORD_X: i32 = 0x68;
const SHIFT: i32 = 18;

const OBJ_VRAM: u32 = 0x0601_0000;
/// The word: three 32x16 sprites, 1D mapped (a sprite's 4 x 2 tiles in a row), 24 tiles; and the number's digit tiles.
const WORD_TILES: usize = 24;
const WORD_W: usize = 96;
const WORD_ROWS: usize = 15;
const DIGIT_TILES: std::ops::Range<usize> = 28..68;

const SEAL_MAP: u32 = 0x0600_7800;
const SEAL_TILES: u32 = 0x0600_8000;
/// The band between the seal's rules: rows and columns that hold the stamp's words and nothing of the ring.
const BAND_Y: std::ops::RangeInclusive<usize> = 74..=85;
const BAND_X: std::ops::RangeInclusive<usize> = 26..=132;
const BAND_CENTRE: i32 = 79;
const BAND_ROWS: usize = 12;

const WORD: &str = "GAUNTLET";

/// The stamp's ink ramp: palette index 1 is full colour, each next one dimmer (the red channel of the card's palette
/// words 0x14BF, 109D, 109B, 1098, 0C76, 0C73, 0851, 084E, 084C, 0429, 0427, 0005, 0002 over 31): the coverage each stands for.
const RAMP: [f32; 13] = [
    1.0, 0.94, 0.87, 0.77, 0.71, 0.61, 0.55, 0.45, 0.39, 0.29, 0.23, 0.16, 0.06,
];

/// A glyph's coverage: 32 rows of 16 columns, 1 where the letter is solid.
pub type Cov = Vec<[f32; 16]>;

/// A word's letters as one picture: the glyphs' solid columns side by side `gap` apart, their common rows area-averaged to
/// `rows`. Returns the rows (each as wide as the word).
pub fn compose(glyphs: &[Cov], gap: usize, rows: usize) -> Vec<Vec<f32>> {
    let used: Vec<usize> = (0..32)
        .filter(|&y| glyphs.iter().any(|g| g[y].iter().any(|&v| v > 0.0)))
        .collect();
    let (Some(&top), Some(&bottom)) = (used.first(), used.last()) else {
        return vec![];
    };
    let height = bottom - top + 1;
    let mut canvas: Vec<Vec<f32>> = vec![vec![]; height];
    for (n, g) in glyphs.iter().enumerate() {
        let cols: Vec<usize> = (0..16).filter(|&x| g.iter().any(|r| r[x] > 0.0)).collect();
        let (Some(&a), Some(&b)) = (cols.first(), cols.last()) else {
            continue;
        };
        if n > 0 {
            for row in canvas.iter_mut() {
                row.extend(std::iter::repeat_n(0.0, gap));
            }
        }
        for (y, row) in canvas.iter_mut().enumerate() {
            row.extend((a..=b).map(|x| g[top + y][x]));
        }
    }
    let w = canvas.first().map_or(0, Vec::len);
    let scale = height as f32 / rows as f32;
    (0..rows)
        .map(|j| {
            let (y0, y1) = (j as f32 * scale, (j + 1) as f32 * scale);
            (0..w)
                .map(|x| {
                    let mut sum = 0.0;
                    for (y, row) in canvas.iter().enumerate() {
                        let part = (y1.min(y as f32 + 1.0) - y0.max(y as f32)).max(0.0);
                        sum += row[x] * part;
                    }
                    sum / scale
                })
                .collect()
        })
        .collect()
}

/// The palette index of the stamp's ramp nearest a coverage (0, clear, for next to none).
pub fn ramp_index(c: f32) -> u8 {
    if c < 0.04 {
        return 0;
    }
    let mut best = 0;
    for (i, r) in RAMP.iter().enumerate() {
        if (r - c).abs() < (RAMP[best] - c).abs() {
            best = i;
        }
    }
    best as u8 + 1
}

/// The card's word's pixel for a coverage: the card's letter colour (index 1), its soft edge (5) or clear.
fn word_index(c: f32) -> u8 {
    if c >= 0.6 {
        1
    } else if c >= 0.3 {
        5
    } else {
        0
    }
}

fn glyphs(core: &Core) -> Option<Vec<Cov>> {
    static FONT: OnceLock<Option<TitleFont>> = OnceLock::new();
    let font = FONT.get_or_init(|| TitleFont::load(core)).as_ref()?;
    // The letters' fill and the edge value of their soft corners: across the middle of an I (as online.rs finds them).
    let i = &font.px[TitleFont::index('I')?];
    let row: Vec<u8> = (0..16).map(|x| i.get(x, 16)).collect();
    let first = row.iter().position(|&v| v != 0)?;
    let (fill, soft) = (row[(first + 4).min(15)], row[first].saturating_sub(1));
    WORD.chars()
        .map(|c| {
            let g = &font.px[TitleFont::index(c)?];
            Some(
                (0..32)
                    .map(|y| {
                        let mut r = [0.0; 16];
                        for (x, v) in r.iter_mut().enumerate() {
                            let p = g.get(x, y);
                            *v = if p == fill {
                                1.0
                            } else if p == soft {
                                0.5
                            } else {
                                0.0
                            };
                        }
                        r
                    })
                    .collect(),
            )
        })
        .collect()
}

/// The word's 24 tiles (4 bits a pixel), GAUNTLET right-aligned in the 96 x 16 the three sprites cover.
pub fn word_tiles(letters: &[Cov]) -> Vec<u8> {
    let pic = compose(letters, 2, WORD_ROWS);
    let mut out = vec![0u8; WORD_TILES * 32];
    let w = pic.first().map_or(0, Vec::len).min(WORD_W);
    let ox = WORD_W - w;
    for (y, row) in pic.iter().enumerate() {
        for (x, &c) in row.iter().take(w).enumerate() {
            let v = word_index(c);
            if v == 0 {
                continue;
            }
            let x = ox + x;
            let tile = (x / 32) * 8 + (y / 8) * 4 + (x % 32) / 8;
            let at = tile * 32 + (y % 8) * 4 + (x % 8) / 2;
            out[at] |= v << (4 * (x & 1));
        }
    }
    out
}

/// The seal's picture with the band's words replaced: `tiles` (256 tiles of 64 bytes) and `map` (32 x 32 cells), or None when a
/// band cell is shared with another part of the picture (then nothing is changed).
pub fn seal_band(map: &[u8], tiles: &mut [u8], letters: &[Cov]) -> Option<()> {
    let mut uses = [0u32; 256];
    for &t in map.iter().take(1024) {
        uses[t as usize] += 1;
    }
    let cell = |x: usize, y: usize| map[(y >> 3) * 32 + (x >> 3)] as usize;
    for y in BAND_Y {
        for x in BAND_X {
            let t = cell(x, y);
            if t == 0 || uses[t] != 1 {
                return None;
            }
        }
    }
    let pic = compose(letters, 1, BAND_ROWS);
    let w = pic.first().map_or(0, Vec::len) as i32;
    let x0 = BAND_CENTRE - w / 2;
    let y0 = *BAND_Y.start();
    let put = |tiles: &mut [u8], x: usize, y: usize, v: u8| {
        tiles[cell(x, y) * 64 + (y & 7) * 8 + (x & 7)] = v;
    };
    for y in BAND_Y {
        for x in BAND_X {
            put(tiles, x, y, 0);
        }
    }
    for (j, row) in pic.iter().enumerate() {
        for (i, &c) in row.iter().enumerate() {
            let x = x0 + i as i32;
            if x >= *BAND_X.start() as i32 && x <= *BAND_X.end() as i32 {
                put(tiles, x as usize, y0 + j, ramp_index(c));
            }
        }
    }
    Some(())
}

/// Writes `new` at `at` when VRAM is not already so.
fn put(core: &mut Core, at: u32, new: &[u8]) {
    let mut now = vec![0u8; new.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != new {
        core.raw_write_range(at, -1, new);
    }
}

fn frame(core: &mut Core) {
    if !crate::gauntlet::session(core) {
        return;
    }
    let Some(letters) = glyphs(core) else { return };
    static WORD_ART: OnceLock<Vec<u8>> = OnceLock::new();
    put(core, OBJ_VRAM, WORD_ART.get_or_init(|| word_tiles(&letters)));
    put(
        core,
        OBJ_VRAM + 32 * DIGIT_TILES.start as u32,
        &vec![0u8; 32 * DIGIT_TILES.len()],
    );
    let mut map = vec![0u8; 1024];
    core.raw_read_range(SEAL_MAP, -1, &mut map);
    let mut tiles = vec![0u8; 256 * 64];
    core.raw_read_range(SEAL_TILES, -1, &mut tiles);
    if seal_band(&map, &mut tiles, &letters).is_some() {
        put(core, SEAL_TILES, &tiles);
    }
}

/// At a draw call of the word's template: its x, in r1.
fn word_draw(core: &mut Core) {
    if !crate::gauntlet::session(core) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    if cpu.gpr(1) as i32 == WORD_X {
        cpu.set_gpr(1, WORD_X + SHIFT);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = Vec::new();
    for a in FRAME {
        t.push((a, Box::new(frame)));
    }
    for a in WORD_DRAW {
        t.push((a, Box::new(word_draw)));
    }
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A solid 6 x 20 block in rows 6..26 of a glyph, columns 3..9.
    fn block() -> Cov {
        (0..32)
            .map(|y| {
                let mut r = [0.0; 16];
                if (6..26).contains(&y) {
                    for v in &mut r[3..9] {
                        *v = 1.0;
                    }
                }
                r
            })
            .collect()
    }

    #[test]
    fn compose_keeps_columns_and_shrinks_rows() {
        let pic = compose(&[block(), block()], 2, 10);
        assert_eq!(pic.len(), 10);
        assert_eq!(pic[0].len(), 6 + 2 + 6);
        assert!(pic.iter().all(|r| r[0] == 1.0 && r[6] == 0.0 && r[8] == 1.0));
    }

    #[test]
    fn ramp_maps_full_to_one_and_none_to_clear() {
        assert_eq!(ramp_index(1.0), 1);
        assert_eq!(ramp_index(0.0), 0);
        assert_eq!(ramp_index(0.39), 9);
    }

    #[test]
    fn word_fits_the_sprites() {
        let t = word_tiles(&[block(), block(), block(), block(), block(), block(), block(), block()]);
        assert_eq!(t.len(), WORD_TILES * 32);
        assert!(t.iter().any(|&b| b != 0));
    }

    #[test]
    fn seal_band_refuses_shared_cells() {
        let mut map = vec![0u8; 1024];
        let mut tiles = vec![0u8; 256 * 64];
        assert!(seal_band(&map, &mut tiles, &[block()]).is_none());
        for (i, m) in map.iter_mut().enumerate() {
            *m = (i % 255 + 1) as u8;
        }
        // (cells repeat every 255: a band cell shared with a cell 255 away is refused)
        assert!(seal_band(&map, &mut tiles, &[block()]).is_none());
        let mut unique = vec![0u8; 1024];
        for y in 9..11 {
            for x in 0..32 {
                unique[y * 32 + x] = (1 + (y - 9) * 32 + x) as u8;
            }
        }
        assert!(seal_band(&unique, &mut tiles, &[block()]).is_some());
    }
}
