//! Survival's SELECT MAP screen in Dual Strike's look, with the Dual Strike
//! pack (offline): what Dual Strike's Survival course screen shows (the
//! mode's title in its title font, the "BASIC COURSE" panel with the maps,
//! the budget and the best, the strip of the course's eleven maps, the map
//! under the cursor with its RECORD box) fitted to one GBA screen. The
//! Champion courses (open once the basic course is cleared) have the same
//! screen with Dual Strike's "CHAMPION COURSE" banner, "Infinite" for the
//! maps, the larger budget and the maps cleared as the best, with its rank.
//!
//! Dual Strike's own art, converted at run time from the pack (nothing of
//! it is in the repository):
//!
//! - the title font (`ohashi/res_modefont`: A..Z, the star, the dash, glyphs
//!   of 16x32 pixels, 2x4 tiles, its palette in the file's last 64 bytes),
//! - the "BASIC COURSE" banner (`ohashi/res_survival`: its first LZ stream,
//!   four sprite blocks of 4x2 tiles = 128x16; the palette bank in the last
//!   770 bytes) and the "CHAMPION COURSE" one (the next four blocks),
//! - the ring wallpaper (`ohashi/res_wall_base`: tiles and a 512x256
//!   tilemap in the first two LZ streams, one palette in the last 32 bytes).
//!
//! Its wording (Funds, Spent, Maps, Turn total, Turns used, Total time, Time
//! used, Funds left, Turns left, Time left, Maps clrd.) is read from the
//! overlay's string table (`0x022F6C3C`'s neighbours, `0x0230E718..`), the
//! rest is AW2's own proportional font (`0x084C32E4`, widths `0x084C36E4`)
//! and window colours (red above, blue below).
//!
//! Where: the War Room's SELECT MAP (`ProcScr_PreviewMap`), once its list is
//! in and takes the pad (the proc's callback `0x08085F91`). The picture is
//! drawn on BG0 (char block and screen as the screen has them: 0 and 14),
//! opaque over every other layer, and the game's sprites are dropped from
//! the frame ([`flush`]); the game keeps the list and its pad (UP and DOWN
//! change the course, A starts it, B leaves). LEFT and RIGHT browse the
//! course's maps, R shows the records, B closes them. Nothing is put back
//! when the screen goes: whatever loads next sets up its own BG0.
//!
//! Pack off: nothing here runs (every entry is behind Survival's own flag).

use mgba::core::Core;
use std::sync::OnceLock;

use crate::survival::{self as sv, PROFILE_RECORDS};
use crate::survival_maps::{self as maps, Kind, MAPS_PER_RUN};

// --- State (Survival's block, after the run's own fields) -------------------

const UI: u32 = sv::STATE + 0x26;
/// 1 while the picture is on screen.
const SHOWN: u32 = UI;
/// The browsed map of the course (0..MAPS_PER_RUN).
const BROWSE: u32 = UI + 1;
/// 1 while the record page is open.
const RECORDS: u32 = UI + 2;
/// The page's context (kind, phase, stage): a change starts a fresh page.
const CONTEXT: u32 = sv::STATE + 0x2C;
/// What the picture was drawn from (a hash): redrawn when it changes.
const SIGNATURE: u32 = sv::STATE + 0x30;
#[cfg(test)]
pub(crate) const STATE_END: u32 = SIGNATURE + 4;

// --- The game ------------------------------------------------------------------

/// The proc's callback while the list takes the pad.
const SELECT_MAP_IDLE: u32 = 0x0808_5F91;
const PROC_POOL: (u32, u32) = (0x0200_D610, 0x0200_E418);
const PROC_SIZE: u32 = 0x6C;
const SELECT_MAP: u32 = 0x0861_6C54;

const BG0CNT: u32 = 0x0400_0008;
/// The game's DISPCNT shadow: the screen moves its cursor under a window
/// (WIN1), which would cut the picture.
const DISP_CT: u32 = 0x0300_30CC;
const WINDOWS: u16 = 0xE000;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const TILE_CLASS: u32 = 0x080C_1BC4;
const FONT_GLYPHS: u32 = 0x084C_32E4;
const FONT_WIDTHS: u32 = 0x084C_36E4;

const KEY_A: u32 = 1 << 0;
const KEY_B: u32 = 1 << 1;
const KEY_RIGHT: u32 = 1 << 4;
const KEY_LEFT: u32 = 1 << 5;
const KEY_R: u32 = 1 << 8;
const KEY_L: u32 = 1 << 9;

/// SELECT MAP's list: the first row shown, the cursor's row, the ids.
const LIST_FIRST: u32 = 0x0300_5900;
const LIST_CURSOR: u32 = 0x0300_5930;
const LIST_IDS: u32 = 0x0202_7F78;

fn selecting(core: &Core) -> bool {
    (PROC_POOL.0..PROC_POOL.1)
        .step_by(PROC_SIZE as usize)
        .any(|p| core.raw_read_32(p, -1) == SELECT_MAP)
}

fn idle(core: &Core) -> bool {
    (PROC_POOL.0..PROC_POOL.1)
        .step_by(PROC_SIZE as usize)
        .any(|p| core.raw_read_32(p, -1) == SELECT_MAP && core.raw_read_32(p + 0x10, -1) == SELECT_MAP_IDLE)
}

/// The picture is up (the game's sprites are dropped).
pub fn shown(core: &Core) -> bool {
    core.raw_read_8(SHOWN, -1) == 1
}

// --- The canvas ----------------------------------------------------------------

const W: usize = 240;
const H: usize = 160;

/// Bank 0's colours (index 0 stays unused: it is clear on a BG): the rings'
/// four, white and the window colours, the title font's blues, AW2's text.
const WHITE: u8 = 1;
const CREAM: u8 = 2;
const PINK: u8 = 3;
const RING_BLUE: u8 = 4;
const RING_GREEN: u8 = 5;
const INK: u8 = 6;
const SHADE: u8 = 7;
const RED: u8 = 8;
const BLUE: u8 = 9;
const LIGHT_BLUE: u8 = 10;
const DARK_BLUE: u8 = 11;
const LIGHT_GRAY: u8 = 12;
const MID_BLUE: u8 = 13;
const YELLOW: u8 = 14;
const GRAY: u8 = 15;

/// RGB (0..255) of bank 0, index 0 the clear colour (cream, unused).
const BANK0: [(u8, u8, u8); 16] = [
    (255, 246, 214),
    (255, 255, 255),
    (255, 246, 214),
    (255, 208, 214),
    (206, 214, 240),
    (208, 237, 214),
    (16, 16, 24),
    (104, 112, 128),
    (240, 48, 56),
    (48, 64, 232),
    (120, 160, 248),
    (24, 32, 120),
    (232, 232, 236),
    (120, 136, 248),
    (255, 224, 64),
    (176, 184, 200),
];

/// The map picture's bank: sea, plain, wood, mountain, road, sand, other,
/// neutral, the five armies, frame.
const MAP_SEA: u8 = 2;
const MAP_PLAIN: u8 = 3;
const MAP_WOOD: u8 = 4;
const MAP_MOUNTAIN: u8 = 5;
const MAP_ROAD: u8 = 6;
const MAP_SAND: u8 = 7;
const MAP_OTHER: u8 = 8;
const MAP_NEUTRAL: u8 = 9;
const MAP_ARMY: u8 = 10; // 10..=14: Orange Star, Blue Moon, Green Earth, Yellow Comet, Black Hole
const BANK1: [(u8, u8, u8); 16] = [
    (255, 255, 255),
    (255, 255, 255),
    (92, 120, 232),
    (152, 224, 88),
    (56, 160, 64),
    (160, 104, 48),
    (176, 176, 184),
    (240, 224, 160),
    (112, 120, 136),
    (232, 232, 232),
    (240, 56, 40),
    (56, 96, 248),
    (48, 192, 72),
    (248, 216, 40),
    (40, 40, 56),
    (24, 32, 120),
];

fn rgb15(c: (u8, u8, u8)) -> u16 {
    ((c.0 as u16) >> 3) | ((c.1 as u16) >> 3) << 5 | ((c.2 as u16) >> 3) << 10
}

fn bgr15_to_rgb(c: u16) -> (u8, u8, u8) {
    let e = |v: u16| ((v << 3) | (v >> 2)) as u8;
    (e(c & 31), e((c >> 5) & 31), e((c >> 10) & 31))
}

fn nearest(c: (u8, u8, u8), among: &[u8]) -> u8 {
    let d = |i: u8| {
        let p = BANK0[i as usize];
        let (dr, dg, db) = (
            p.0 as i32 - c.0 as i32,
            p.1 as i32 - c.1 as i32,
            p.2 as i32 - c.2 as i32,
        );
        dr * dr + dg * dg + db * db
    };
    among.iter().copied().min_by_key(|&i| d(i)).unwrap_or(WHITE)
}

/// The colours Dual Strike's title font (blues, its white outline, the
/// star) and its banner (black, white, greys) are drawn in.
const TITLE_COLOURS: [u8; 7] = [WHITE, INK, LIGHT_BLUE, MID_BLUE, DARK_BLUE, BLUE, YELLOW];
const BANNER_COLOURS: [u8; 5] = [WHITE, INK, SHADE, LIGHT_GRAY, GRAY];
const WALL_COLOURS: [u8; 5] = [CREAM, PINK, RING_BLUE, RING_GREEN, WHITE];

struct Canvas {
    px: Vec<u8>,
    /// The palette bank of each 8x8 cell (0 or 1).
    bank: Vec<u8>,
}

impl Canvas {
    fn new(art: &Art) -> Canvas {
        Canvas {
            px: art.wall.clone(),
            bank: vec![0; (W / 8) * (H / 8)],
        }
    }
    fn put(&mut self, x: i32, y: i32, v: u8) {
        if (0..W as i32).contains(&x) && (0..H as i32).contains(&y) {
            self.px[W * y as usize + x as usize] = v;
        }
    }
    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, v: u8) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.put(xx, yy, v);
            }
        }
    }
    /// A window: white, red above, blue below, a light edge at the sides.
    fn window(&mut self, x: i32, y: i32, w: i32, h: i32) {
        self.rect(x, y, w, h, WHITE);
        self.rect(x + 1, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x + w - 2, y + 2, 1, h - 4, LIGHT_GRAY);
        self.rect(x, y, w, 2, RED);
        self.rect(x, y + h - 2, w, 2, BLUE);
    }
    /// AW2's proportional font from (x, y) (16 rows of 4bpp nibbles a glyph,
    /// 11 shown from the third); returns the x after the text.
    fn text(&mut self, core: &Core, x: i32, y: i32, s: &str, ink: u8, shade: u8) -> i32 {
        let mut x = x;
        for c in s.bytes() {
            let w = core.raw_read_8(FONT_WIDTHS + c as u32, -1) as usize;
            let at = core.raw_read_32(FONT_GLYPHS + 4 * c as u32, -1);
            if (0x0800_0000..0x0A00_0000).contains(&at) {
                let stride = w.div_ceil(2);
                for r in 0..11 {
                    for cx in 0..w {
                        let b = core.raw_read_8(at + (stride * (3 + r) + cx / 2) as u32, -1);
                        let v = (b >> (4 * (cx & 1))) & 15;
                        if v != 0 {
                            self.put(x + cx as i32, y + r as i32, if v == 0xA { ink } else { shade });
                        }
                    }
                }
            }
            x += w as i32 + 1;
        }
        x
    }
}

fn text_width(core: &Core, s: &str) -> i32 {
    s.bytes()
        .map(|c| core.raw_read_8(FONT_WIDTHS + c as u32, -1) as i32 + 1)
        .sum::<i32>()
        - 1
}

// --- Dual Strike's art -------------------------------------------------------------

struct Glyph {
    /// 16x32, 0 clear.
    px: Vec<u8>,
    /// The columns the glyph's pixels span.
    left: usize,
    right: usize,
}

struct Art {
    glyphs: Vec<Glyph>,
    title_pal: [u16; 16],
    /// Rows of the title font that carry pixels (the glyphs' common extent).
    title_top: usize,
    title_rows: usize,
    /// The banners, 128x16, 0 clear: BASIC COURSE, CHAMPION COURSE.
    banner: Vec<u8>,
    champion_banner: Vec<u8>,
    banner_pal: [u16; 16],
    /// The ring wallpaper cropped to the screen, as bank 0's indexes.
    wall: Vec<u8>,
}

/// One LZ10 stream at `p`: its bytes and where the next stream starts
/// (the files keep several one after another, each on a word).
fn lz10_stream(b: &[u8], p: usize) -> Option<(Vec<u8>, usize)> {
    if *b.get(p)? != 0x10 {
        return None;
    }
    let size = u32::from_le_bytes([*b.get(p + 1)?, *b.get(p + 2)?, *b.get(p + 3)?, 0]) as usize;
    let mut out: Vec<u8> = Vec::with_capacity(size);
    let mut q = p + 4;
    while out.len() < size {
        let flags = *b.get(q)?;
        q += 1;
        for bit in 0..8 {
            if out.len() >= size {
                break;
            }
            if flags & (0x80 >> bit) != 0 {
                let (b1, b2) = (*b.get(q)? as usize, *b.get(q + 1)? as usize);
                q += 2;
                let disp = ((b1 & 15) << 8 | b2) + 1;
                if disp > out.len() {
                    return None;
                }
                for _ in 0..(b1 >> 4) + 3 {
                    out.push(out[out.len() - disp]);
                }
            } else {
                out.push(*b.get(q)?);
                q += 1;
            }
        }
    }
    Some((out, (q + 3) & !3))
}

fn palette(b: &[u8], at: usize) -> Option<[u16; 16]> {
    let mut p = [0u16; 16];
    for (k, c) in p.iter_mut().enumerate() {
        *c = u16::from_le_bytes([*b.get(at + 2 * k)?, *b.get(at + 2 * k + 1)?]);
    }
    Some(p)
}

/// A 4bpp tile's pixels.
fn tile_px(tiles: &[u8], t: usize, x: usize, y: usize) -> u8 {
    tiles
        .get(32 * t + 4 * y + x / 2)
        .map_or(0, |b| (b >> (4 * (x & 1))) & 15)
}

fn build_art() -> Option<Art> {
    let pack = crate::ds_pack::pack()?;
    // The title font: 28 glyphs of 2x4 tiles.
    let f = pack.file("ohashi/res_modefont")?;
    let (tiles, _) = lz10_stream(f, 0)?;
    let title_pal = palette(f, f.len().checked_sub(64)?)?;
    if tiles.len() < 28 * 256 {
        return None;
    }
    let mut glyphs = Vec::new();
    let (mut top, mut bottom) = (32usize, 0usize);
    for g in 0..28 {
        let mut px = vec![0u8; 16 * 32];
        for t in 0..8 {
            for y in 0..8 {
                for x in 0..8 {
                    px[16 * (8 * (t / 2) + y) + 8 * (t % 2) + x] = tile_px(&tiles, g * 8 + t, x, y);
                }
            }
        }
        let cols: Vec<usize> = (0..16).filter(|&x| (0..32).any(|y| px[16 * y + x] != 0)).collect();
        let rows: Vec<usize> = (0..32).filter(|&y| (0..16).any(|x| px[16 * y + x] != 0)).collect();
        top = top.min(*rows.first()?);
        bottom = bottom.max(*rows.last()?);
        glyphs.push(Glyph {
            px,
            left: *cols.first()?,
            right: *cols.last()?,
        });
    }
    // The banner: four blocks of 4x2 tiles side by side.
    let f = pack.file("ohashi/res_survival")?;
    let (tiles, _) = lz10_stream(f, 0)?;
    let banner_pal = palette(f, f.len().checked_sub(770)?)?;
    if tiles.len() < 64 * 32 {
        return None;
    }
    let banner_at = |first: usize| {
        let mut banner = vec![0u8; 128 * 16];
        for blk in 0..4 {
            for t in 0..8 {
                for y in 0..8 {
                    for x in 0..8 {
                        banner[128 * (8 * (t / 4) + y) + 32 * blk + 8 * (t % 4) + x] =
                            tile_px(&tiles, (first + blk) * 8 + t, x, y);
                    }
                }
            }
        }
        banner
    };
    let banner = banner_at(0);
    let champion_banner = banner_at(4);
    // The wallpaper: its tiles, the first screen of its map, its palette.
    let f = pack.file("ohashi/res_wall_base")?;
    let (tiles, next) = lz10_stream(f, 0)?;
    let (map, _) = lz10_stream(f, next)?;
    let wall_pal = palette(f, f.len().checked_sub(32)?)?;
    let mut wall = vec![CREAM; W * H];
    for ty in 0..H / 8 {
        for tx in 0..W / 8 {
            let at = 2 * (32 * ty + tx);
            let e = u16::from_le_bytes([*map.get(at)?, *map.get(at + 1)?]) as usize;
            let (t, hf, vf) = (e & 0x3FF, e & 0x400 != 0, e & 0x800 != 0);
            for y in 0..8 {
                for x in 0..8 {
                    let v = tile_px(&tiles, t, if hf { 7 - x } else { x }, if vf { 7 - y } else { y });
                    if v != 0 {
                        wall[W * (8 * ty + y) + 8 * tx + x] =
                            nearest(bgr15_to_rgb(wall_pal[v as usize]), &WALL_COLOURS);
                    }
                }
            }
        }
    }
    Some(Art {
        glyphs,
        title_pal,
        title_top: top,
        title_rows: bottom - top + 1,
        banner,
        champion_banner,
        banner_pal,
        wall,
    })
}

fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(build_art).as_ref()
}

impl Art {
    fn glyph(&self, c: char) -> Option<&Glyph> {
        match c {
            'A'..='Z' => self.glyphs.get(c as usize - 'A' as usize),
            '*' | ' ' => self.glyphs.get(26),
            '-' => self.glyphs.get(27),
            _ => None,
        }
    }
    /// The title, centred, its top at `y`.
    fn title(&self, cv: &mut Canvas, y: i32, s: &str) {
        let list: Vec<&Glyph> = s.chars().filter_map(|c| self.glyph(c)).collect();
        // Neighbouring glyphs share their white outline's column.
        let total: i32 = list.iter().map(|g| (g.right - g.left) as i32).sum::<i32>() + 1;
        let mut x = (W as i32 - total) / 2;
        for g in list {
            for gy in 0..self.title_rows {
                for gx in g.left..=g.right {
                    let v = g.px[16 * (self.title_top + gy) + gx];
                    if v != 0 {
                        let c = bgr15_to_rgb(self.title_pal[v as usize]);
                        cv.put(x + (gx - g.left) as i32, y + gy as i32, nearest(c, &TITLE_COLOURS));
                    }
                }
            }
            x += (g.right - g.left) as i32;
        }
    }
    /// One title-font letter with its left edge at `x`.
    fn letter(&self, cv: &mut Canvas, x: i32, y: i32, c: char) -> i32 {
        let Some(g) = self.glyph(c) else { return x };
        for gy in 0..self.title_rows {
            for gx in g.left..=g.right {
                let v = g.px[16 * (self.title_top + gy) + gx];
                if v != 0 {
                    let col = bgr15_to_rgb(self.title_pal[v as usize]);
                    cv.put(x + (gx - g.left) as i32, y + gy as i32, nearest(col, &TITLE_COLOURS));
                }
            }
        }
        x + (g.right - g.left) as i32 + 1
    }
    fn banner(&self, cv: &mut Canvas, x: i32, y: i32, champion: bool) {
        let pixels = if champion { &self.champion_banner } else { &self.banner };
        for by in 0..16 {
            for bx in 0..128 {
                let v = pixels[128 * by + bx];
                let c = if v == 0 {
                    WHITE
                } else {
                    nearest(bgr15_to_rgb(self.banner_pal[v as usize]), &BANNER_COLOURS)
                };
                cv.put(x + bx as i32, y + by as i32, c);
            }
        }
    }
}

// --- Dual Strike's wording -----------------------------------------------------------

/// The overlay's survival strings (Funds, Spent, Maps, ...), as the course
/// panel reads them: 0x0230E718.. in the overlay (loaded at 0x022AD560).
const WORDS_AT: u32 = 0x0230_E718;

struct Words {
    funds: String,
    spent: String,
    maps: String,
    turn_total: String,
    turns_used: String,
    total_time: String,
    time_used: String,
    funds_left: String,
    turns_left: String,
    time_left: String,
    maps_cleared: String,
    infinite: String,
}

fn words() -> &'static Words {
    static WORDS: OnceLock<Words> = OnceLock::new();
    WORDS.get_or_init(|| {
        // The strings sit in a run: Funds, Spent, <flag byte> Maps, Turns,
        // Total, Infinite, Time used, Time left, Turns used, Turns left,
        // Funds left, Total time, Maps clrd., Turn total; read by scanning
        // the run for each (they are plain words), with Dual Strike's own
        // text as the fallback.
        let find = |want: &str, fallback: &str| -> String {
            let Some(pack) = crate::ds_pack::pack() else {
                return fallback.into();
            };
            let Some(b) = pack.overlay_at(0, 0x022A_D560, WORDS_AT, 0xA0) else {
                return fallback.into();
            };
            let mut it = b.split(|&c| c == 0).filter(|s| s.len() >= 2).map(|s| {
                s.iter()
                    .skip_while(|&&c| c < 0x20)
                    .map(|&c| c as char)
                    .collect::<String>()
            });
            it.find(|s| s == want).unwrap_or_else(|| fallback.into())
        };
        Words {
            funds: find("Funds", "Funds"),
            spent: find("Spent", "Spent"),
            maps: find("Maps", "Maps"),
            turn_total: find("Turn total", "Turn total"),
            turns_used: find("Turns used", "Turns used"),
            total_time: find("Total time", "Total time"),
            time_used: find("Time used", "Time used"),
            funds_left: find("Funds left", "Funds left"),
            turns_left: find("Turns left", "Turns left"),
            time_left: find("Time left", "Time left"),
            maps_cleared: find("Maps clrd.", "Maps clrd."),
            infinite: find("Infinite", "Infinite"),
        }
    })
}

fn clock(frames: u32) -> String {
    let s = frames / 60;
    format!("{}:{:02}", s / 60, s % 60)
}

/// A budget or what is left, as the panel writes it.
fn amount(k: Kind, v: u32) -> String {
    match k {
        Kind::Money => format!("{} G", v),
        Kind::Turn => format!("{}", v),
        Kind::Time => clock(v),
    }
}

fn co_name(co: u8) -> String {
    crate::co_new::ds_name(co)
        .map(|t| {
            t.iter()
                .filter(|&&c| (0x20..0x7F).contains(&c))
                .map(|&c| c as char)
                .collect::<String>()
        })
        .unwrap_or_default()
}

// --- Pages -------------------------------------------------------------------------------

fn title_of(k: Kind) -> &'static str {
    match k {
        Kind::Money => "MONEY*SURVIVAL",
        Kind::Turn => "TURN*SURVIVAL",
        Kind::Time => "TIME*SURVIVAL",
    }
}

fn row_labels(k: Kind) -> (&'static str, &'static str) {
    let w = words();
    match k {
        Kind::Money => (&w.funds, &w.spent),
        Kind::Turn => (&w.turn_total, &w.turns_used),
        Kind::Time => (&w.total_time, &w.time_used),
    }
}

fn left_label(k: Kind) -> &'static str {
    let w = words();
    match k {
        Kind::Money => &w.funds_left,
        Kind::Turn => &w.turns_left,
        Kind::Time => &w.time_left,
    }
}

/// What a record says was used (Dual Strike keeps what the course cost).
fn best_used(k: Kind, budget: u32, rec: Option<(u8, u8, u32)>) -> String {
    match rec {
        Some((_, _, left)) => amount(k, budget.saturating_sub(left)),
        None => "----".into(),
    }
}

fn right_text(cv: &mut Canvas, core: &Core, right: i32, y: i32, s: &str) {
    let w = text_width(core, s);
    cv.text(core, right - w, y, s, INK, SHADE);
}

/// The footer: the first of `lines` that fits.
fn hint(cv: &mut Canvas, core: &Core, lines: &[&str]) {
    let s = lines
        .iter()
        .find(|l| text_width(core, l) <= 232)
        .or(lines.last())
        .copied()
        .unwrap_or("");
    let w = text_width(core, s);
    cv.rect(0, 148, W as i32, 12, WHITE);
    cv.rect(0, 148, W as i32, 1, RED);
    cv.text(core, (W as i32 - w) / 2, 149, s, INK, SHADE);
}

/// A rank in a small box (Dual Strike's badge by the Champion course's best).
fn rank_badge(cv: &mut Canvas, core: &Core, x: i32, y: i32, rank: u8) {
    cv.rect(x, y, 12, 12, BLUE);
    let s = maps::rank_letter(rank).to_string();
    let w = text_width(core, &s);
    cv.text(core, x + 6 - w / 2, y + 1, &s, WHITE, LIGHT_BLUE);
}

/// One course's panel at `y`: the banner, the rows. `between`: a run in
/// progress (maps cleared, what is left, points).
fn course_panel(cv: &mut Canvas, core: &Core, a: &Art, k: Kind, champion: bool, between: Option<(u32, u32, u32)>) {
    let (x, y, w, h) = (8, 31, 224, 48);
    cv.window(x, y, w, h);
    a.banner(cv, 56, y + 3, champion);
    let run = maps::survival().map(|s| s.run(k));
    let budget = run.map_or(0, |r| if champion { r.champion_budget } else { r.budget });
    let right = x + w - 8;
    let (row1, row2) = (y + 21, y + 34);
    match between {
        None if champion => {
            // Dual Strike's Champion panel: Infinite, the budget, the maps
            // cleared (and the rank) of the best run.
            cv.text(core, x + 8, row1, &words().infinite, INK, SHADE);
            let (l1, _) = row_labels(k);
            cv.text(core, 108, row1, l1, INK, SHADE);
            right_text(cv, core, right, row1, &amount(k, budget));
            cv.text(core, 108, row2, &words().maps_cleared, INK, SHADE);
            match sv::champion_record(core, k) {
                Some(n) => {
                    rank_badge(cv, core, right - 11, row2 - 1, maps::champion_rank(n));
                    right_text(cv, core, right - 15, row2, &format!("{} {}", n, words().maps));
                }
                None => right_text(cv, core, right, row2, "----"),
            }
        }
        None => {
            let n = format!("{}", MAPS_PER_RUN);
            let nx = cv.text(core, x + 8, row1, &n, INK, SHADE);
            cv.text(core, nx + 3, row1, &words().maps, INK, SHADE);
            let (l1, l2) = row_labels(k);
            cv.text(core, 108, row1, l1, INK, SHADE);
            right_text(cv, core, right, row1, &amount(k, budget));
            cv.text(core, 108, row2, l2, INK, SHADE);
            right_text(cv, core, right, row2, &best_used(k, budget, sv::record(core, k)));
        }
        Some((stage, left, points)) => {
            let n = format!("{}", stage);
            let nx = cv.text(core, x + 8, row1, &n, INK, SHADE);
            cv.text(core, nx + 3, row1, &words().maps_cleared, INK, SHADE);
            if champion {
                // The list starts over after eleven maps: each round a wave.
                let wave = format!("Wave {}", stage / MAPS_PER_RUN as u32 + 1);
                cv.text(core, x + 8, row2, &wave, INK, SHADE);
            }
            cv.text(core, 108, row1, left_label(k), INK, SHADE);
            right_text(cv, core, right, row1, &amount(k, left));
            cv.text(core, 108, row2, "Points", INK, SHADE);
            right_text(cv, core, right, row2, &format!("{}", points));
        }
    }
}

/// The strip of the course's maps under the panel: cleared ones dark, the
/// next one yellow, the cursor's brackets on the browsed one.
fn strip(cv: &mut Canvas, core: &Core, cleared: usize, next: Option<usize>, browsed: usize) {
    let y = 83;
    for n in 0..MAPS_PER_RUN {
        let x = 12 + 20 * n as i32;
        let (fill, ink, shade) = if n < cleared {
            (DARK_BLUE, WHITE, LIGHT_BLUE)
        } else if Some(n) == next {
            (YELLOW, INK, SHADE)
        } else {
            (LIGHT_BLUE, DARK_BLUE, BLUE)
        };
        cv.rect(x, y, 14, 14, fill);
        for i in 0..14 {
            for (px, py) in [(x + i, y), (x + i, y + 13), (x, y + i), (x + 13, y + i)] {
                cv.put(px, py, WHITE);
            }
        }
        let s = format!("{}", n + 1);
        let w = text_width(core, &s);
        cv.text(core, x + 7 - w / 2, y + 1, &s, ink, shade);
        if n == browsed {
            // Dual Strike's cursor: corner brackets.
            for k in 0..4 {
                for (px, py) in [
                    (x - 3 + k, y - 3),
                    (x - 3, y - 3 + k),
                    (x + 16 - k, y - 3),
                    (x + 16, y - 3 + k),
                    (x - 3 + k, y + 16),
                    (x - 3, y + 16 - k),
                    (x + 16 - k, y + 16),
                    (x + 16, y + 16 - k),
                ] {
                    cv.put(px, py, INK);
                }
            }
        }
    }
}

/// The map's picture (the game's own terrain classes), in bank 1's colours,
/// on 8x5 cells.
fn minimap(cv: &mut Canvas, core: &Core, map: &maps::Map, x0: i32, y0: i32) {
    for cy in 0..5 {
        for cx in 0..8 {
            cv.bank[(W / 8) * ((y0 / 8 + cy) as usize) + (x0 / 8 + cx) as usize] = 1;
        }
    }
    cv.rect(x0, y0, 64, 40, MAP_SEA);
    let mut classes = vec![0u8; 0x400];
    core.raw_read_range(TILE_CLASS, -1, &mut classes);
    let (w, h) = (map.width as i32, map.height as i32);
    let s = (64 / w.max(1)).min(40 / h.max(1)).clamp(1, 4);
    let (ox, oy) = (x0 + (64 - s * w) / 2, y0 + (40 - s * h) / 2);
    for ty in 0..h {
        for tx in 0..w {
            let t = map.tiles[(ty * w + tx) as usize] as usize;
            let colour = match t {
                0x1B4..=0x1B8 => MAP_ARMY + 4,
                0x1C0..=0x1D8 => {
                    let owner = (t - 0x1C0) / 5;
                    if owner == 0 {
                        MAP_NEUTRAL
                    } else {
                        MAP_ARMY + owner as u8 - 1
                    }
                }
                _ => match classes.get(t).copied().unwrap_or(0) & 0x1F {
                    1 => MAP_PLAIN,
                    2 | 13 => MAP_SAND,
                    3 => MAP_MOUNTAIN,
                    4 => MAP_WOOD,
                    5 | 12 => MAP_ROAD,
                    7 | 19 => MAP_SEA,
                    15 => MAP_OTHER,
                    6 | 8 | 10 | 11 | 14 | 20 => MAP_NEUTRAL,
                    _ => MAP_ROAD,
                },
            };
            cv.rect(ox + s * tx, oy + s * ty, s, s, colour);
        }
    }
}

fn weather_name(w: u8) -> Option<&'static str> {
    match w {
        1 => Some("Snow"),
        2 => Some("Rain"),
        3 => Some("Sandstorm"),
        _ => None,
    }
}

/// The browsed map's RECORD box: its name, who fights it and where.
fn record_box(cv: &mut Canvas, core: &Core, map: &maps::Map, number: usize) {
    let (x, y, w, h) = (84, 114, 148, 32);
    cv.text(core, x + 2, y - 13, "MAP", INK, SHADE);
    cv.window(x, y, w, h);
    cv.text(core, x + 8, y + 3, &format!("{}. {}", number + 1, map.name), INK, SHADE);
    let cos: Vec<String> = map
        .cos
        .iter()
        .flatten()
        .map(|&c| co_name(c))
        .filter(|n| !n.is_empty())
        .collect();
    let enemy = if cos.is_empty() {
        "-".to_string()
    } else {
        cos.join(", ")
    };
    let ex = cv.text(core, x + 8, y + 15, "Enemy", GRAY_INK, SHADE);
    cv.text(core, ex + 5, y + 15, &enemy, INK, SHADE);
    let mut facts: Vec<&str> = Vec::new();
    if map.fog {
        facts.push("Fog");
    }
    if let Some(wn) = weather_name(map.weather) {
        facts.push(wn);
    }
    if !facts.is_empty() {
        right_text(cv, core, x + w - 8, y + 15, &facts.join(", "));
    }
}

/// The ink of captions.
const GRAY_INK: u8 = SHADE;

/// A small triangle (9 wide, 5 tall) pointing up or down: UP and DOWN
/// change the course.
fn arrow(cv: &mut Canvas, x: i32, y: i32, up: bool) {
    for r in 0..5 {
        let half = if up { r } else { 4 - r };
        cv.rect(x + 4 - half, y + r, 2 * half + 1, 1, INK);
    }
}

fn course_page(cv: &mut Canvas, core: &Core, a: &Art, k: Kind, champion: bool, phase: u8, browsed: usize) {
    let Some(s) = maps::survival() else { return };
    let run = s.run(k);
    a.title(cv, 1, title_of(k));
    if phase == sv::CHOOSING {
        for x in [5, 226] {
            arrow(cv, x, 8, true);
            arrow(cv, x, 18, false);
        }
    }
    let stage = core.raw_read_8(sv::STAGE, -1) as usize;
    let between = (phase == sv::BETWEEN).then(|| {
        (
            stage as u32,
            core.raw_read_32(sv::LEFT, -1),
            core.raw_read_32(sv::POINTS, -1),
        )
    });
    course_panel(cv, core, a, k, champion, between);
    // The strip: cleared maps dark, the next yellow. A Champion course goes
    // round again after eleven maps: the strip is the round's; before a run
    // the maps its best run reached are dark.
    let (cleared, next) = if phase == sv::BETWEEN {
        let n = if champion { stage % MAPS_PER_RUN } else { stage };
        (n, Some(n))
    } else if champion {
        (sv::champion_record(core, k).map_or(0, |n| (n as usize).min(MAPS_PER_RUN)), None)
    } else {
        (0, None)
    };
    strip(cv, core, cleared, next, browsed);
    let map = &s.maps[run.maps[browsed.min(MAPS_PER_RUN - 1)]];
    minimap(cv, core, map, 8, 104);
    record_box(cv, core, map, browsed);
    if phase == sv::BETWEEN {
        hint(
            cv,
            core,
            &[
                "A Next map   B Quit   Left/Right Maps   R Record",
                "A Next   B Quit   < > Maps   R Record",
            ],
        );
    } else {
        hint(
            cv,
            core,
            &[
                "A Start   B Back   Left/Right Maps   R Record",
                "A Start   B Back   < > Maps   R Record",
            ],
        );
    }
}

fn result_page(cv: &mut Canvas, core: &Core, a: &Art, k: Kind, champion: bool, phase: u8) {
    let cleared = phase == sv::CLEARED;
    a.title(cv, 1, if cleared { "CLEAR" } else { "GAME*OVER" });
    let (x, y, w, h) = (8, 36, 224, 108);
    cv.window(x, y, w, h);
    a.banner(cv, 56, y + 3, champion);
    let stage = core.raw_read_8(sv::STAGE, -1) as u32;
    let points = core.raw_read_32(sv::POINTS, -1);
    let mut rows = if champion {
        // An endless course: the maps cleared, no "of".
        vec![(words().maps_cleared.clone(), format!("{}", stage))]
    } else {
        vec![(words().maps_cleared.clone(), format!("{} / {}", stage, MAPS_PER_RUN))]
    };
    if cleared {
        rows.push((left_label(k).to_string(), amount(k, core.raw_read_32(sv::LEFT, -1))));
    }
    if cleared || champion {
        rows.push(("Bonus".to_string(), format!("{}", core.raw_read_32(sv::BONUS, -1))));
    }
    rows.push(("Points".to_string(), format!("{}", points)));
    // Rows left, the rank in the title font at the right.
    let ranked = cleared || champion;
    let right = if ranked { x + w - 52 } else { x + w - 10 };
    for (i, (l, v)) in rows.iter().enumerate() {
        let ry = y + 24 + 15 * i as i32;
        cv.text(core, x + 10, ry, l, INK, SHADE);
        right_text(cv, core, right, ry, v);
        cv.rect(x + 10, ry + 13, right - x - 10, 1, LIGHT_GRAY);
    }
    if ranked {
        cv.text(core, x + w - 44, y + 24, "Rank", GRAY_INK, SHADE);
        let r = maps::rank_letter(core.raw_read_8(sv::RANK, -1));
        a.letter(cv, x + w - 36, y + 40, r);
    }
    let name = if champion { k.champion_name() } else { k.name() };
    cv.text(core, x + 10, y + h - 15, name, GRAY_INK, SHADE);
    hint(cv, core, &["A Continue"]);
}

fn records_page(cv: &mut Canvas, core: &Core, a: &Art) {
    a.title(cv, 1, "RECORD");
    let (x, y, w, h) = (8, 34, 224, 112);
    cv.window(x, y, w, h);
    a.banner(cv, 56, y + 3, false);
    let heads = [("Course", x + 10), ("Rank", x + 100), ("CO", x + 130)];
    for (s, hx) in heads {
        cv.text(core, hx, y + 20, s, GRAY_INK, SHADE);
    }
    right_text(cv, core, x + w - 10, y + 20, "Used");
    // The three basic courses, then the three Champion courses.
    for (i, (k, champion)) in Kind::ALL.iter().map(|&k| (k, false)).chain(Kind::ALL.iter().map(|&k| (k, true))).enumerate() {
        let ry = y + 36 + 12 * i as i32;
        cv.rect(x + 10, ry - 2, w - 20, 1, LIGHT_GRAY);
        cv.text(core, x + 10, ry, if champion { k.champion_name() } else { k.name() }, INK, SHADE);
        if champion {
            match sv::champion_record(core, k) {
                Some(n) => {
                    cv.text(core, x + 100, ry, &format!("{}", maps::rank_letter(maps::champion_rank(n))), INK, SHADE);
                    right_text(cv, core, x + w - 10, ry, &format!("{} {}", n, words().maps));
                }
                None => {
                    cv.text(core, x + 100, ry, "-", INK, SHADE);
                    let used = if sv::champion_open(core, k) { "----" } else { "Locked" };
                    right_text(cv, core, x + w - 10, ry, used);
                }
            }
            continue;
        }
        let budget = maps::survival().map_or(0, |s| s.run(k).budget);
        let rec = sv::record(core, k);
        match rec {
            Some((rank, co, _)) => {
                cv.text(core, x + 100, ry, &format!("{}", maps::rank_letter(rank)), INK, SHADE);
                cv.text(core, x + 130, ry, &co_name(co), INK, SHADE);
            }
            None => {
                cv.text(core, x + 100, ry, "-", INK, SHADE);
            }
        }
        right_text(cv, core, x + w - 10, ry, &best_used(k, budget, rec));
    }
    hint(cv, core, &["B Back"]);
}

// --- On the screen -------------------------------------------------------------------------

/// The picture as tiles (the same ones shared), a 32x32 tilemap and the
/// two palettes.
fn tiles_of(cv: &Canvas) -> (Vec<u8>, Vec<u8>) {
    let mut tiles: Vec<[u8; 32]> = vec![[0u8; 32]];
    let mut index = std::collections::HashMap::new();
    index.insert([0u8; 32], 0u16);
    let mut map = vec![0u8; 0x800];
    for ty in 0..H / 8 {
        for tx in 0..W / 8 {
            let mut t = [0u8; 32];
            for y in 0..8 {
                for x in 0..8 {
                    let v = cv.px[W * (8 * ty + y) + 8 * tx + x] & 15;
                    t[4 * y + x / 2] |= v << (4 * (x & 1));
                }
            }
            let bank = cv.bank[(W / 8) * ty + tx] as u16;
            let k = match index.get(&t) {
                Some(&k) => k,
                None if tiles.len() < 512 => {
                    let k = tiles.len() as u16;
                    tiles.push(t);
                    index.insert(t, k);
                    k
                }
                None => 1,
            };
            map[2 * (32 * ty + tx)..2 * (32 * ty + tx) + 2].copy_from_slice(&(k | bank << 12).to_le_bytes());
        }
    }
    (tiles.concat(), map)
}

fn palettes(a: &Art) -> Vec<u8> {
    let _ = a;
    let mut out = Vec::new();
    for bank in [&BANK0, &BANK1] {
        for c in bank.iter() {
            out.extend_from_slice(&rgb15(*c).to_le_bytes());
        }
    }
    out
}

fn bg0(core: &Core) -> (u32, u32) {
    let c = core.raw_read_16(BG0CNT, -1) as u32;
    (
        0x0600_0000 + 0x4000 * ((c >> 2) & 3),
        0x0600_0000 + 0x800 * ((c >> 8) & 31),
    )
}

fn write_if_changed(core: &mut Core, at: u32, b: &[u8]) {
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != b {
        core.raw_write_range(at, -1, b);
    }
}

fn kind_on_list(core: &Core) -> Option<(Kind, bool)> {
    let (first, cursor) = (core.raw_read_32(LIST_FIRST, -1), core.raw_read_32(LIST_CURSOR, -1));
    let id = core.raw_read_8(LIST_IDS + (first + cursor).min(0x31), -1);
    sv::entry_kind_of(id)
}

fn hash(bytes: &[u8]) -> u32 {
    bytes
        .iter()
        .fold(0x811C_9DC5u32, |h, &b| (h ^ b as u32).wrapping_mul(0x0100_0193))
}

/// Which page the state asks for, and its signature (a hash of everything
/// the picture is drawn from).
fn page(core: &Core) -> Option<(Kind, bool, u8, u8, u32)> {
    let phase = core.raw_read_8(sv::PHASE, -1);
    let (k, champion) = if phase == sv::CHOOSING {
        kind_on_list(core)?
    } else {
        (sv::kind_now(core), sv::champion_now(core))
    };
    let mut b = vec![0u8; (UI - sv::STATE) as usize];
    core.raw_read_range(sv::STATE, -1, &mut b);
    let mut rec = [0u8; sv::PROFILE_RECORDS_LEN];
    core.raw_read_range(PROFILE_RECORDS, -1, &mut rec);
    b.extend_from_slice(&rec);
    b.push(k as u8);
    b.push(champion as u8);
    b.push(core.raw_read_8(BROWSE, -1));
    let records = core.raw_read_8(RECORDS, -1);
    b.push(records);
    Some((k, champion, phase, records, hash(&b)))
}

/// Survival's War Room is closed: nothing is up.
pub fn off(core: &mut Core, keys: u32) -> u32 {
    if core.raw_read_8(SHOWN, -1) != 0 {
        core.raw_write_8(SHOWN, -1, 0);
        core.raw_write_8(RECORDS, -1, 0);
        core.raw_write_32(CONTEXT, -1, 0);
    }
    keys
}

/// The picture: drawn once SELECT MAP takes the pad and again when what it
/// shows changes. Returns the keys the game gets.
pub fn tick(core: &mut Core, keys: u32, prev: u32) -> u32 {
    let mut keys = keys;
    if !selecting(core) {
        if core.raw_read_8(SHOWN, -1) != 0 {
            core.raw_write_8(SHOWN, -1, 0);
            core.raw_write_8(RECORDS, -1, 0);
            core.raw_write_32(CONTEXT, -1, 0);
        }
        return keys;
    }
    let Some(a) = art() else { return keys };
    if core.raw_read_8(SHOWN, -1) == 0 && !idle(core) {
        return keys;
    }
    let pressed = keys & !prev;
    let Some((k, champion, phase, recs, _)) = page(core) else {
        return keys;
    };
    // A fresh page when the course, the phase or the run's progress changes.
    let stage = core.raw_read_8(sv::STAGE, -1);
    let ctx = (k as u32) | (champion as u32) << 3 | (phase as u32) << 4 | (stage as u32) << 8 | 1 << 16;
    if core.raw_read_32(CONTEXT, -1) != ctx {
        core.raw_write_32(CONTEXT, -1, ctx);
        core.raw_write_8(
            BROWSE,
            -1,
            if phase == sv::BETWEEN {
                // A Champion course starts its list over every eleven maps.
                if champion { stage % MAPS_PER_RUN as u8 } else { stage.min(MAPS_PER_RUN as u8 - 1) }
            } else {
                0
            },
        );
        core.raw_write_8(RECORDS, -1, 0);
    }
    let mut browse = core.raw_read_8(BROWSE, -1) as usize % MAPS_PER_RUN;
    if core.raw_read_8(SHOWN, -1) == 1 {
        if recs == 1 {
            // The record page: B closes it; the game sees nothing.
            if pressed & (KEY_B | KEY_R | KEY_A) != 0 {
                core.raw_write_8(RECORDS, -1, 0);
            }
            keys &= !(KEY_A | KEY_B | KEY_R | KEY_L | KEY_LEFT | KEY_RIGHT);
        } else {
            if phase == sv::CHOOSING || phase == sv::BETWEEN {
                if pressed & KEY_RIGHT != 0 {
                    browse = (browse + 1) % MAPS_PER_RUN;
                }
                if pressed & KEY_LEFT != 0 {
                    browse = (browse + MAPS_PER_RUN - 1) % MAPS_PER_RUN;
                }
                if pressed & KEY_R != 0 {
                    core.raw_write_8(RECORDS, -1, 1);
                }
            }
            core.raw_write_8(BROWSE, -1, browse as u8);
            keys &= !(KEY_R | KEY_L | KEY_LEFT | KEY_RIGHT);
        }
    }
    let Some((k, champion, phase, recs, sig)) = page(core) else {
        return keys;
    };
    if core.raw_read_8(SHOWN, -1) == 1 {
        let d = core.raw_read_16(DISP_CT, -1);
        if d & WINDOWS != 0 {
            core.raw_write_16(DISP_CT, -1, d & !WINDOWS);
        }
    }
    if core.raw_read_8(SHOWN, -1) == 1 && core.raw_read_32(SIGNATURE, -1) == sig {
        return keys;
    }
    draw(core, a, k, champion, phase, recs == 1, browse);
    core.raw_write_32(SIGNATURE, -1, sig);
    core.raw_write_8(SHOWN, -1, 1);
    keys
}

fn draw(core: &mut Core, a: &Art, k: Kind, champion: bool, phase: u8, records: bool, browse: usize) {
    let mut cv = Canvas::new(a);
    if records {
        records_page(&mut cv, core, a);
    } else if phase == sv::CLEARED || phase == sv::LOST {
        result_page(&mut cv, core, a, k, champion, phase);
    } else {
        course_page(&mut cv, core, a, k, champion, phase, browse);
    }
    let (tiles, map) = tiles_of(&cv);
    let (chars, screen) = bg0(core);
    write_if_changed(core, chars, &tiles);
    write_if_changed(core, screen, &map);
    let pal = palettes(a);
    write_if_changed(core, PAL_BUFFER, &pal);
    write_if_changed(core, PAL_RAM, &pal);
    let d = core.raw_read_16(DISP_CT, -1);
    core.raw_write_16(DISP_CT, -1, d & !WINDOWS);
}

/// The budget on the battle map: lines of AW2's font, white outlined in
/// black, centred at the top, as 8x16 sprites in the OBJ tiles the map
/// leaves free ([`crate::two_front::free_tile_pairs`]). Skipped while a
/// structure's heal plays in those tiles.
pub fn hud(core: &mut Core, at: u32, end: u32, lines: &[String]) -> u32 {
    if crate::heal_effect::playing(core) {
        return at;
    }
    let mut at = at;
    let mut pairs = crate::two_front::free_tile_pairs().into_iter();
    for (i, s) in lines.iter().enumerate() {
        let cols = crate::two_front::outlined(core, s);
        let x = 120 - cols.len() as i32 / 2;
        let y = 1 + 12 * i as i32;
        for (k, chunk) in cols.chunks(8).enumerate() {
            let Some(t) = pairs.next() else { break };
            let mut tiles = [0u8; 64];
            for (cx, col) in chunk.iter().enumerate() {
                for (cy, &v) in col.iter().enumerate() {
                    tiles[32 * (cy / 8) + 4 * (cy % 8) + cx / 2] |= v << (4 * (cx & 1));
                }
            }
            let tile_at = 0x0601_0000 + 32 * t as u32;
            write_if_changed(core, tile_at, &tiles);
            if at + 8 > end {
                return at;
            }
            // 8x16: shape tall, size 0; priority 0, palette 0.
            core.raw_write_16(at, -1, (y as u16 & 0xFF) | 2 << 14);
            core.raw_write_16(at + 2, -1, (x + 8 * k as i32) as u16 & 0x1FF);
            core.raw_write_16(at + 4, -1, t);
            at += 8;
        }
    }
    at
}

/// At the VBlank sprite flush: with the picture up, none of the game's
/// sprites (its cursor, the properties' counts, the enemy CO: the picture
/// has its own). Each is switched off in the list, which the game copies
/// whole.
pub fn flush(core: &mut Core, start: u32, at: u32) -> u32 {
    if shown(core) && selecting(core) {
        let mut p = start;
        while p < at {
            let a0 = core.raw_read_16(p, -1);
            if a0 & 0x0300 != 0x0200 {
                core.raw_write_16(p, -1, (a0 & !0x0300) | 0x0200);
            }
            p += 8;
        }
    }
    at
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn colours() {
        assert_eq!(BANK0.len(), 16);
        assert_eq!(rgb15((255, 255, 255)), 0x7FFF);
        assert_eq!(nearest((250, 250, 250), &[WHITE, INK]), WHITE);
        assert_eq!(clock(90000), "25:00");
    }

    #[test]
    fn lz10_streams() {
        // A stream of four literal bytes, then another.
        let mut b = vec![0x10, 4, 0, 0, 0x00, 1, 2, 3, 4, 0, 0, 0];
        b.extend_from_slice(&[0x10, 2, 0, 0, 0x00, 9, 8, 0]);
        let (d, next) = lz10_stream(&b, 0).unwrap();
        assert_eq!(d, vec![1, 2, 3, 4]);
        assert_eq!(next, 12);
        assert_eq!(lz10_stream(&b, next).unwrap().0, vec![9, 8]);
    }

    #[test]
    fn state_fits() {
        // mGBA's 32-bit accesses are word-aligned: the words sit on words.
        assert_eq!(CONTEXT % 4, 0);
        assert_eq!(SIGNATURE % 4, 0);
        assert!(RECORDS < CONTEXT);
        assert!(STATE_END <= sv::STATE + 0x40);
    }

    /// Dual Strike's art and wording convert (needs `TANGOAW2_DS_ROM`):
    /// `cargo test -p tango-gamesupport-aw2 survival_ui -- --ignored`.
    #[test]
    #[ignore]
    fn art_converts() {
        let a = art().expect("the title font, the banner and the wallpaper");
        assert_eq!(a.glyphs.len(), 28);
        assert!(a.title_rows >= 20 && a.title_rows <= 32, "{}", a.title_rows);
        assert_eq!(a.banner.len(), 128 * 16);
        assert!(a.banner.iter().any(|&p| p != 0));
        assert!(a.champion_banner.iter().any(|&p| p != 0));
        assert_ne!(a.banner, a.champion_banner);
        assert_eq!(a.wall.len(), W * H);
        assert!(a.wall.iter().all(|&p| WALL_COLOURS.contains(&p)));
        // A title: its glyphs all exist.
        for c in "MONEY*SURVIVAL TURN TIME RECORD GAME*OVER CLEAR".chars() {
            assert!(a.glyph(c).is_some(), "{c}");
        }
        let w = words();
        assert_eq!(w.funds, "Funds");
        assert_eq!(w.spent, "Spent");
        assert_eq!(w.maps, "Maps");
        assert_eq!(w.turn_total, "Turn total");
        assert_eq!(w.turns_used, "Turns used");
        assert_eq!(w.total_time, "Total time");
        assert_eq!(w.time_used, "Time used");
        assert_eq!(w.funds_left, "Funds left");
        assert_eq!(w.turns_left, "Turns left");
        assert_eq!(w.time_left, "Time left");
        assert_eq!(w.maps_cleared, "Maps clrd.");
        assert_eq!(w.infinite, "Infinite");
        // Every Survival tile set fits the 512 tiles of BG0's char block
        // on every page (the tests render them; this one the first).
        assert!(maps::survival().is_some());
    }
}
