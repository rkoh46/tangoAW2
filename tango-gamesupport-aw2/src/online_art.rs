//! The ONLINE menus' lettering, made at run time from AW2's own art (nothing of it is in the repository): the
//! Select Mode wheel's ONLINE (in place of LINK), the ONLINE screen's UNRANKED / LOBBY / STATS and the LOBBY
//! level's CREATE / JOIN / BACK (in place of Single-Pak / Multi-Pak / Trade Maps), and the screen's title in the
//! game's title font (ONLINE, LOBBY).
//!
//! - **The wheel** (`0x08616AC0`: a big and a small label per item, LZ77): ONLINE is LINK's plate with the letters
//!   of DESIGN ROOM and BATTLEMAPS (big: O, N, I, E of DESIGN ROOM, L of BATTLEMAPS, spread over the plate as
//!   LINK's are, coloured by the plate's 16-pixel column bands; small: O and E of DESIGN ROOM, L, I, N of LINK).
//! - **The Link screen's labels** (one LZ77 sheet, `0x081D8A54`: three big labels of 128x32, 64 tiles each, then
//!   three small ones of 128x16, 32 tiles each; a label is drawn in its item's own palette): the words are set
//!   from the letters of SINGLE-PAK, MULTI-PAK and TRADE MAPS. The letters those lack are drawn from theirs, as the
//!   font draws its own: O is D with its round side mirrored, B is R's top over D's bottom, Y is U's arms over T's
//!   stem, C is O open on the right, J is U without its left arm's top.
//! - **The title** (`0x081CC038`: 16x32 glyphs of A C D E G H I K L M N O P R S T U W Y, the star and B, 2x4 tiles
//!   each): the glyphs, and where each goes (neighbours share their outline's column, as the game sets LINK).

use mgba::core::Core;

/// A label's pixels: 128 wide, `h` rows, palette indexes.
#[derive(Clone)]
pub struct Px {
    pub w: usize,
    pub h: usize,
    pub v: Vec<u8>,
}

impl Px {
    fn new(w: usize, h: usize, fill: u8) -> Px {
        Px {
            w,
            h,
            v: vec![fill; w * h],
        }
    }
    pub fn get(&self, x: usize, y: usize) -> u8 {
        self.v[y * self.w + x]
    }
    fn set(&mut self, x: usize, y: usize, c: u8) {
        self.v[y * self.w + x] = c;
    }
    /// Columns `a..=b`, every row.
    fn cut(&self, a: usize, b: usize, rows: std::ops::Range<usize>) -> Px {
        let mut g = Px::new(b - a + 1, rows.len(), 0);
        for (gy, y) in rows.enumerate() {
            for x in a..=b {
                g.set(x - a, gy, self.get(x, y));
            }
        }
        g
    }
    fn mirror(&self) -> Px {
        let mut g = self.clone();
        for y in 0..self.h {
            for x in 0..self.w {
                g.set(x, y, self.get(self.w - 1 - x, y));
            }
        }
        g
    }
}

// --- LZ77 and tiles ------------------------------------------------------------------------

/// `data` as a GBA LZ77 stream of literals only (the BIOS and the game's decompressor read it as any other).
pub fn lz_literal(data: &[u8]) -> Vec<u8> {
    let n = data.len();
    let mut out = vec![0x10, n as u8, (n >> 8) as u8, (n >> 16) as u8];
    for chunk in data.chunks(8) {
        out.push(0);
        out.extend_from_slice(chunk);
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

/// Pixels of `h_tiles` rows of tiles laid out as sprites `sw` tiles wide, left to right (1D mapping).
pub fn sprites_to_px(data: &[u8], w: usize, h_tiles: usize, sw: usize) -> Px {
    let mut px = Px::new(w, 8 * h_tiles, 0);
    let mut t = 0;
    for s in 0..w / (8 * sw) {
        for ty in 0..h_tiles {
            for tx in 0..sw {
                for y in 0..8 {
                    for x in 0..8 {
                        let b = data.get(32 * t + 4 * y + x / 2).copied().unwrap_or(0);
                        px.set(8 * (s * sw + tx) + x, 8 * ty + y, (b >> (4 * (x & 1))) & 15);
                    }
                }
                t += 1;
            }
        }
    }
    px
}

pub fn px_to_sprites(px: &Px, sw: usize) -> Vec<u8> {
    let h_tiles = px.h / 8;
    let mut out = vec![0u8; px.w / 8 * h_tiles * 32];
    let mut t = 0;
    for s in 0..px.w / (8 * sw) {
        for ty in 0..h_tiles {
            for tx in 0..sw {
                for y in 0..8 {
                    for x in 0..8 {
                        let v = px.get(8 * (s * sw + tx) + x, 8 * ty + y) & 15;
                        out[32 * t + 4 * y + x / 2] |= v << (4 * (x & 1));
                    }
                }
                t += 1;
            }
        }
    }
    out
}

fn rom_lz(core: &Core, at: u32, max: usize) -> Option<Vec<u8>> {
    let mut b = vec![0u8; max];
    core.raw_read_range(at, -1, &mut b);
    crate::ds_art::lz10(&b)
}

// --- The wheel ------------------------------------------------------------------------------

/// The wheel's labels: (big, small) LZ77 per item.
pub const WHEEL_LABELS: u32 = 0x0861_6AC0;
/// LINK's item.
pub const LINK_ITEM: u32 = 4;
const DESIGN_ROOM: u32 = 3;
const BATTLE_MAPS: u32 = 2;

/// The game's wheel label of `item` as it is in the cartridge (big: 128x32, sprites 8 tiles wide; small: 128x16,
/// sprites 4 wide). `table` is the label table to read (the game's).
fn wheel_label(core: &Core, item: u32, big: bool) -> Option<Px> {
    let at = core.raw_read_32(WHEEL_LABELS + 8 * item + if big { 0 } else { 4 }, -1);
    let d = rom_lz(core, at, 0x1000)?;
    Some(if big {
        sprites_to_px(&d, 128, 4, 8)
    } else {
        sprites_to_px(&d, 128, 2, 4)
    })
}

/// A small wheel label's letter cells: column runs between all-dark columns inside its dark box (rows 4..10).
fn wheel_cells(px: &Px) -> Vec<(usize, usize)> {
    let rows = 4..11;
    let dark = |x: usize| rows.clone().all(|y| px.get(x, y) == 1);
    let light = |x: usize| rows.clone().all(|y| px.get(x, y) == 5);
    let boxed: Vec<usize> = (4..124).filter(|&x| !light(x)).collect();
    let (Some(&lo), Some(&hi)) = (boxed.first(), boxed.last()) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    let mut start = None;
    for x in lo..=hi + 1 {
        let d = x > hi || dark(x);
        match (d, start) {
            (false, None) => start = Some(x),
            (true, Some(s)) => {
                out.push((s, x - 1));
                start = None;
            }
            _ => {}
        }
    }
    out
}

/// ONLINE's big wheel label (LZ77-ready tiles: 128x32 as two 64x32 sprites).
pub fn wheel_big(core: &Core) -> Option<Vec<u8>> {
    let design = wheel_label(core, DESIGN_ROOM, true)?;
    let battle = wheel_label(core, BATTLE_MAPS, true)?;
    let mut out = wheel_label(core, LINK_ITEM, true)?;
    // O N L I N E (DESIGN ROOM: D 4..14, E 16..25, S, I 39..45, G, N 60..71, R, O 87..97; BATTLEMAPS: L 51..60)
    let letters: [(&Px, usize, usize); 6] = [
        (&design, 87, 97),
        (&design, 60, 71),
        (&battle, 51, 60),
        (&design, 39, 45),
        (&design, 60, 71),
        (&design, 16, 25),
    ];
    for y in 2..22 {
        for x in 4..124 {
            out.set(x, y, 1);
        }
    }
    // Spread over the plate as LINK's letters are: the first at its left edge, the last at its right.
    let widths: usize = letters.iter().map(|&(_, a, b)| b - a + 1).sum();
    let gaps = letters.len() - 1;
    let spare = 120 - widths;
    let mut x = 4;
    for (k, &(src, a, b)) in letters.iter().enumerate() {
        for sx in a..=b {
            for y in 2..22 {
                let mut v = src.get(sx, y);
                if (5..=12).contains(&v) {
                    v = (5 + x / 16).min(12) as u8;
                }
                out.set(x, y, v);
            }
            x += 1;
        }
        if k < gaps {
            x += spare / gaps + usize::from(k < spare % gaps);
        }
    }
    Some(px_to_sprites(&out, 8))
}

/// ONLINE's small wheel label (128x16 as four 32x16 sprites).
pub fn wheel_small(core: &Core) -> Option<Vec<u8>> {
    let design = wheel_label(core, DESIGN_ROOM, false)?;
    let link = wheel_label(core, LINK_ITEM, false)?;
    let (d, l) = (wheel_cells(&design), wheel_cells(&link));
    if d.len() != 10 || l.len() != 4 {
        return None;
    }
    // O (DESIGN ROOM's 8th cell), N, L, I, N (LINK), E (DESIGN ROOM's 2nd)
    let letters: [(&Px, (usize, usize)); 6] = [
        (&design, d[7]),
        (&link, l[2]),
        (&link, l[0]),
        (&link, l[1]),
        (&link, l[2]),
        (&design, d[1]),
    ];
    let mut out = link.clone();
    for y in 4..11 {
        for x in 4..124 {
            out.set(x, y, 5);
        }
    }
    Some(px_to_sprites(
        &small_text(&mut out, &letters.map(|(p, (a, b))| p.cut(a, b, 4..11)), 1),
        4,
    ))
}

/// Letters (7 rows each) set in a small label's text row (4..10) as the game sets them: centred, a dark column
/// before, between and after them. `dark` is the box's index.
fn small_text(out: &mut Px, letters: &[Px], dark: u8) -> Px {
    let total: usize = letters.iter().map(|g| g.w).sum::<usize>() + letters.len() + 1;
    let mut x = 4 + (120 - total.min(120)) / 2;
    let dark_col = |out: &mut Px, x: usize| {
        for y in 4..11 {
            out.set(x, y, dark);
        }
    };
    dark_col(out, x);
    x += 1;
    for g in letters {
        for gx in 0..g.w {
            if x >= 124 {
                break;
            }
            for gy in 0..7 {
                out.set(x, 4 + gy, g.get(gx, gy));
            }
            x += 1;
        }
        if x < 124 {
            dark_col(out, x);
        }
        x += 1;
    }
    out.clone()
}

// --- The Link screen ---------------------------------------------------------------------

/// The pointer to the Link screen's label sheet (a literal-pool word of its loader).
pub const SHEET_POOL: u32 = 0x0803_3AE4;
pub const SHEET: u32 = 0x081D_8A54;
const SHEET_BYTES: usize = 0x2400;
/// Tiles of a big label, of a small one.
pub const BIG_TILES: usize = 64;
pub const SMALL_TILES: usize = 32;

/// The letters of SINGLE-PAK (0), MULTI-PAK (1) and TRADE MAPS (2): (label, first column, last column), big then
/// small.
const BIG: &[(char, usize, usize, usize)] = &[
    ('S', 0, 4, 15),
    ('I', 0, 17, 25),
    ('N', 0, 27, 39),
    ('G', 0, 41, 52),
    ('L', 0, 54, 63),
    ('E', 0, 65, 74),
    ('K', 0, 111, 123),
    ('M', 1, 4, 20),
    ('U', 1, 22, 34),
    ('T', 2, 4, 14),
    ('R', 2, 16, 26),
    ('A', 2, 28, 42),
    ('D', 2, 44, 54),
    ('P', 2, 101, 111),
];
const SMALL: &[(char, usize, usize, usize)] = &[
    ('S', 0, 33, 38),
    ('I', 0, 40, 41),
    ('N', 0, 43, 48),
    ('G', 0, 50, 55),
    ('L', 0, 57, 62),
    ('E', 0, 64, 69),
    ('K', 0, 90, 95),
    ('M', 1, 37, 42),
    ('U', 1, 44, 49),
    ('T', 2, 31, 36),
    ('R', 2, 38, 43),
    ('A', 2, 45, 51),
    ('D', 2, 53, 58),
    ('P', 2, 84, 89),
];

/// The Link screen's font, cut from its sheet: big glyphs are 20 rows (the labels' rows 2..21), small ones 7 (rows
/// 4..10); index 1 is the box behind them.
pub struct LinkFont {
    big: Vec<(char, Px)>,
    small: Vec<(char, Px)>,
    /// The sheet's labels as pixels: big 0..2, small 0..2.
    pub big_plates: Vec<Px>,
    pub small_plates: Vec<Px>,
}

/// `rows` of `g` replaced by those of `from` (same width).
fn rows_from(g: &mut Px, from: &Px, rows: std::ops::Range<usize>) {
    for y in rows {
        for x in 0..g.w.min(from.w) {
            g.set(x, y, from.get(x, y));
        }
    }
}

/// O: D with its round side mirrored onto the straight one.
fn make_o(d: &Px) -> Px {
    let m = d.mirror();
    let mut o = d.clone();
    for y in 0..d.h {
        for x in 0..d.w / 2 {
            o.set(x, y, m.get(x, y));
        }
    }
    o
}

/// C: O without the right stroke between its top and bottom curves (big: rows 5..14; small: rows 2..4).
fn make_c(o: &Px, rows: std::ops::Range<usize>) -> Px {
    let mut c = o.clone();
    for y in rows {
        for x in o.w / 2..o.w {
            c.set(x, y, 1);
        }
    }
    c
}

impl LinkFont {
    pub fn load(core: &Core) -> Option<LinkFont> {
        let sheet = rom_lz(core, SHEET, SHEET_BYTES + 0x400)?;
        if sheet.len() < SHEET_BYTES {
            return None;
        }
        let big_plates: Vec<Px> = (0..3)
            .map(|i| sprites_to_px(&sheet[i * BIG_TILES * 32..], 128, 4, 8))
            .collect();
        let small_plates: Vec<Px> = (0..3)
            .map(|i| sprites_to_px(&sheet[(3 * BIG_TILES + i * SMALL_TILES) * 32..], 128, 2, 4))
            .collect();
        let big: Vec<(char, Px)> = BIG
            .iter()
            .map(|&(c, l, a, b)| (c, big_plates[l].cut(a, b, 2..22)))
            .collect();
        let small: Vec<(char, Px)> = SMALL
            .iter()
            .map(|&(c, l, a, b)| (c, small_plates[l].cut(a, b, 4..11)))
            .collect();
        let mut f = LinkFont {
            big,
            small,
            big_plates,
            small_plates,
        };
        f.synthesize();
        Some(f)
    }

    fn glyph(list: &[(char, Px)], c: char) -> Option<&Px> {
        list.iter().find(|(k, _)| *k == c).map(|(_, g)| g)
    }

    /// The letters the three labels lack.
    fn synthesize(&mut self) {
        let g = |l: &[(char, Px)], c| Self::glyph(l, c).cloned();
        // Big (20 rows): D, R, U, T are 11, 11, 13 and 11 wide.
        if let (Some(d), Some(r), Some(u), Some(t)) = (
            g(&self.big, 'D'),
            g(&self.big, 'R'),
            g(&self.big, 'U'),
            g(&self.big, 'T'),
        ) {
            let o = make_o(&d);
            let c = make_c(&o, 5..15);
            let mut b = r.clone();
            rows_from(&mut b, &d, 13..20);
            // Y: U's arms (its rows 0..6), its bottom curve (15..19) and T's stem under it.
            let mut y = Px::new(u.w, 20, 1);
            for gy in 0..20 {
                let src = if gy < 7 {
                    Some((&u, gy))
                } else if gy < 12 {
                    Some((&u, gy + 8))
                } else {
                    None
                };
                for gx in 0..u.w {
                    let v = match src {
                        Some((p, sy)) => p.get(gx, sy),
                        // T's stem (its columns 3..7) in U's middle.
                        None => {
                            let tx = gx as i32 - (u.w as i32 - t.w as i32) / 2;
                            if (0..t.w as i32).contains(&tx) {
                                t.get(tx as usize, 10)
                            } else {
                                1
                            }
                        }
                    };
                    y.set(gx, gy, v);
                }
            }
            // J: U without the top of its left arm.
            let mut j = u.clone();
            for gy in 0..12 {
                for gx in 0..u.w / 2 - 1 {
                    j.set(gx, gy, 1);
                }
            }
            self.big.extend([('O', o), ('C', c), ('B', b), ('Y', y), ('J', j)]);
        }
        // Small (7 rows, 6 wide).
        if let (Some(d), Some(r), Some(u), Some(t)) = (
            g(&self.small, 'D'),
            g(&self.small, 'R'),
            g(&self.small, 'U'),
            g(&self.small, 'T'),
        ) {
            let o = make_o(&d);
            let c = make_c(&o, 2..5);
            // B: R's top and waist (rows 0..3), D's bottom (4..6).
            let mut b = r.clone();
            rows_from(&mut b, &d, 4..7);
            // Y: U's arms (rows 0..1), its bottom (5..6), T's stem.
            let mut y = Px::new(u.w, 7, 1);
            for gy in 0..7 {
                for gx in 0..u.w {
                    let v = match gy {
                        0 | 1 => u.get(gx, gy),
                        2 | 3 => u.get(gx, gy + 3),
                        _ => t.get(gx.min(t.w - 1), 4),
                    };
                    y.set(gx, gy, v);
                }
            }
            let mut j = u.clone();
            for gy in 0..4 {
                for gx in 0..u.w / 2 {
                    j.set(gx, gy, 1);
                }
            }
            self.small.extend([('O', o), ('C', c), ('B', b), ('Y', y), ('J', j)]);
        }
    }

    /// `word` as a big label on plate `plate` (its box, bars and palette kept): centred, as wide as the box allows.
    pub fn big_label(&self, plate: usize, word: &str) -> Px {
        let mut out = self.big_plates[plate].clone();
        for y in 2..22 {
            for x in 4..124 {
                out.set(x, y, 1);
            }
        }
        let glyphs: Vec<&Px> = word.chars().filter_map(|c| Self::glyph(&self.big, c)).collect();
        let widths: usize = glyphs.iter().map(|g| g.w).sum();
        let n = glyphs.len().max(1);
        // One column apart as the game sets its words, wider when the word is short (at most four).
        let gap = if n > 1 {
            ((120usize.saturating_sub(widths)) / (n - 1)).clamp(1, 4)
        } else {
            0
        };
        let total = widths + gap * (n - 1);
        let mut x = 4 + (120usize.saturating_sub(total)) / 2;
        for g in glyphs {
            for gx in 0..g.w {
                if x + gx >= 124 {
                    break;
                }
                for gy in 0..20 {
                    out.set(x + gx, 2 + gy, g.get(gx, gy));
                }
            }
            x += g.w + gap;
        }
        out
    }

    /// `word` as a small label on plate `plate`.
    pub fn small_label(&self, plate: usize, word: &str) -> Px {
        let mut out = self.small_plates[plate].clone();
        for y in 4..11 {
            for x in 4..124 {
                out.set(x, y, 4);
            }
        }
        let glyphs: Vec<Px> = word
            .chars()
            .filter_map(|c| Self::glyph(&self.small, c).cloned())
            .collect();
        small_text(&mut out, &glyphs, 1)
    }

    /// A whole sheet as the Link screen loads it: three big labels, then three small ones.
    pub fn sheet(&self, words: [&str; 3]) -> Vec<u8> {
        let mut out = Vec::new();
        for (i, w) in words.iter().enumerate() {
            out.extend(px_to_sprites(&self.big_label(i, w), 8));
        }
        for (i, w) in words.iter().enumerate() {
            out.extend(px_to_sprites(&self.small_label(i, w), 4));
        }
        out
    }

    pub fn has(&self, c: char) -> bool {
        Self::glyph(&self.big, c).is_some() && Self::glyph(&self.small, c).is_some()
    }
}

// --- The title font ---------------------------------------------------------------------------

pub const TITLE_FONT: u32 = 0x081C_C038;
/// The glyphs' order in the font.
pub const TITLE_ORDER: &str = "ACDEGHIKLMNOPRSTUWY*B";

/// The title font: each glyph's 8 tiles (16x32, 2 wide) and its last column (the next glyph starts there: the
/// two share their outline's column).
pub struct TitleFont {
    tiles: Vec<u8>,
    pub px: Vec<Px>,
    right: Vec<usize>,
}

impl TitleFont {
    pub fn load(core: &Core) -> Option<TitleFont> {
        let tiles = rom_lz(core, TITLE_FONT, 0x1800)?;
        let n = TITLE_ORDER.len();
        if tiles.len() < n * 256 {
            return None;
        }
        let px: Vec<Px> = (0..n).map(|g| sprites_to_px(&tiles[g * 256..], 16, 4, 2)).collect();
        let right = px
            .iter()
            .map(|p| {
                (0..16)
                    .filter(|&x| (0..32).any(|y| p.get(x, y) != 0))
                    .max()
                    .unwrap_or(15)
            })
            .collect();
        Some(TitleFont { tiles, px, right })
    }

    pub fn index(c: char) -> Option<usize> {
        TITLE_ORDER.find(c)
    }

    /// A glyph's 8 tiles.
    pub fn tiles(&self, c: char) -> Option<&[u8]> {
        let g = Self::index(c)?;
        self.tiles.get(g * 256..g * 256 + 256)
    }

    /// Where each letter of `word` goes, from `x`.
    pub fn layout(&self, word: &str, x: i32) -> Vec<(char, i32)> {
        let mut out = Vec::new();
        let mut x = x;
        for c in word.chars() {
            let Some(g) = Self::index(c) else { continue };
            out.push((c, x));
            x += self.right[g] as i32;
        }
        out
    }

    /// How far a letter moves the next one on.
    pub fn advance(&self, c: char) -> i32 {
        Self::index(c).map_or(0, |g| self.right[g] as i32)
    }

    pub fn width(&self, word: &str) -> i32 {
        let l = self.layout(word, 0);
        l.last()
            .map_or(0, |&(c, x)| x + self.right[Self::index(c).unwrap_or(0)] as i32 + 1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn literal_lz_round_trips() {
        let data: Vec<u8> = (0..300u32).map(|i| (i * 7) as u8).collect();
        let lz = lz_literal(&data);
        assert_eq!(lz.len() % 4, 0);
        assert_eq!(crate::ds_art::lz10(&lz).unwrap(), data);
    }

    #[test]
    fn sprites_round_trip() {
        let mut px = Px::new(128, 32, 0);
        for (i, v) in px.v.iter_mut().enumerate() {
            *v = (i % 13) as u8;
        }
        let tiles = px_to_sprites(&px, 8);
        assert_eq!(tiles.len(), 64 * 32);
        assert_eq!(sprites_to_px(&tiles, 128, 4, 8).v, px.v);
    }

    #[test]
    fn the_words_have_their_letters() {
        // The letters the sheet gives plus the five drawn from them cover every word the screens show.
        let have: String = BIG.iter().map(|b| b.0).chain("OCBYJ".chars()).collect();
        for w in ["UNRANKED", "LOBBY", "STATS", "CREATE", "JOIN", "GAMERTAG"] {
            assert!(w.chars().all(|c| have.contains(c)), "{w}");
            assert!(
                w.chars().all(|c| SMALL.iter().any(|s| s.0 == c) || "OCBYJ".contains(c)),
                "{w}"
            );
        }
        for w in ["ONLINE", "LOBBY"] {
            assert!(w.chars().all(|c| TITLE_ORDER.contains(c)), "{w}");
        }
    }
}
