//! Dual Strike's CO selection screens on the GBA's one screen, with the pack and "Dual Strike map graphics" on (offline):
//! Versus' Teams screen (Dual Strike's NORMAL BATTLE: an army card for each army with its CO's and partner's portraits and
//! its P1 / CPU tab, up to five armies), and the CO screen of the campaigns and the War Room (Dual Strike's SELECT CO: the
//! armies' name cards over the grid of every CO's face, a locked CO a black cell).
//!
//! Everything is Dual Strike's own art, converted at run time from the pack ([`crate::ds_pack`]); what is laid out here is
//! where Dual Strike puts it (read from its video memory while the screens ran in melonDS), cut to 240 x 160:
//!
//! - **The wall** (`ohashi/res_wall_single`: 768 tiles, a 32 x 64 map, its palette the file's last 32 bytes) behind Versus,
//!   the ring wallpaper (`ohashi/res_wall_base`: its second pair of streams, tiles then a map, palette the last 32 bytes)
//!   behind the CO screen, as Dual Strike's bottom screens have them.
//! - **The title** NORMAL * BATTLE: `ohashi/res_modefont`'s 16 x 32 glyphs (A..Z, then the star; palette 10, the file's
//!   last 64 bytes' first half) and the two lion crests (its third stream: two 64 x 64 sprites, the second half of the
//!   palette).
//! - **An army card on Versus** is the card of `ohashi/res_versus` (stream 0: 128 tiles; the five armies' palettes at the
//!   end of the file, in the order Orange Star, Blue Moon, Green Earth, Yellow Comet, Black Hole; the emblems are tiles
//!   21.. four each, in that order): six columns of 8 pixels, a header (two lions and the emblem), the card (the "AWDS"
//!   crest) and a foot line; over it the two portraits, each the three middle columns of the 48 x 48 mug (Dual Strike's
//!   cell is 24 x 48). Above the card its tab: a 32 x 32 rounded box (the same tiles) with "P1".."P4" or "CPU"
//!   (`icon/res_icon4_cg_E`, tiles 395, 399, 403, 407 and 411, 16 x 16, the palette `0x0213_9288`).
//! - **The CO screen's cards and panel** are `ohashi/res_syogunselect_lang_E`'s tiles (stream 0), laid out as Dual Strike's
//!   BG1: a card 8 tiles wide (a header with the emblem, a plate of two rows for each name, the numerals 1 and 2 faint at
//!   the plates' ends, a foot), the "COs" panel (a header band of two rows, the body, the "AN" crest at its foot). The
//!   names are the CO's name graphics (the game's presentation table, `+0x04`, six 8 x 16 columns) in Dual Strike's name
//!   palette (`0x0213_4D48`); a cell is the CO's menu face (32 x 16, the HUD face) in a 48 x 16 box with a black outline;
//!   the picks' flags (`ohashi/res_syogunselect` stream 0: 1 and 2 for Orange Star, Blue Moon, Green Earth, Yellow
//!   Comet; Black Hole's in the grey the file has no flag for) lie at the cell's end.
//! - The cursor's corners are the selection's corner marks of Dual Strike's menus ([`crate::ds_menus`]); the arrows over
//!   and under a portrait `ohashi/res_tpicon2_lang_E` (tiles 48 up, 52 down; palette the one at 512 in `commo/res_wireless_icon`).
//!
//! What is read from the game: Versus' Teams record (armies, colours, controllers, COs, partners, the cursor) and the CO
//! screen's proc (the country tabs' lists, the cursor, the picks so far); nothing is written: the picture is drawn over the
//! finished frame, so the game's own choices, cursor moves and picks are untouched (with the mode off nothing here runs).

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use mgba::core::Core;

use crate::wasteland::ds_graphics;

pub const W: usize = 240;
pub const H: usize = 160;

// --- Pictures and their drawing ------------------------------------------------------------------

fn rgba_of(c: u16) -> [u8; 4] {
    let e = |v: u16| {
        let v = (v & 31) as u8;
        (v << 3) | (v >> 2)
    };
    [e(c), e(c >> 5), e(c >> 10), 255]
}

fn pal16(b: &[u8], at: usize) -> Option<[u16; 16]> {
    let p = b.get(at..at + 32)?;
    let mut o = [0u16; 16];
    for (i, c) in o.iter_mut().enumerate() {
        *c = u16::from_le_bytes([p[2 * i], p[2 * i + 1]]);
    }
    Some(o)
}

/// A 4bpp tile's pixel.
fn tile_px(tiles: &[u8], t: usize, x: usize, y: usize) -> u8 {
    tiles.get(32 * t + 4 * y + x / 2).map_or(0, |b| (b >> (4 * (x & 1))) & 15)
}

/// The 240 x 160 picture, RGBA.
pub struct Canvas<'a> {
    pub rgba: &'a mut [u8],
}

impl Canvas<'_> {
    fn put(&mut self, x: i32, y: i32, c: [u8; 4]) {
        if (0..W as i32).contains(&x) && (0..H as i32).contains(&y) {
            let o = 4 * (y as usize * W + x as usize);
            self.rgba[o..o + 4].copy_from_slice(&c);
        }
    }
    /// One 8 x 8 tile (colour 0 clear unless `opaque`).
    fn tile(&mut self, tiles: &[u8], t: usize, x: i32, y: i32, pal: &[u16; 16], flip: (bool, bool), opaque: bool) {
        for yy in 0..8 {
            for xx in 0..8 {
                let (sx, sy) = (if flip.0 { 7 - xx } else { xx }, if flip.1 { 7 - yy } else { yy });
                let v = tile_px(tiles, t, sx, sy) as usize;
                if v != 0 || opaque {
                    self.put(x + xx as i32, y + yy as i32, rgba_of(pal[v]));
                }
            }
        }
    }
    /// A sprite of `tw` x `th` tiles, taken in rows from tile `first`.
    fn sprite(&mut self, tiles: &[u8], first: usize, tw: usize, th: usize, x: i32, y: i32, pal: &[u16; 16]) {
        for ty in 0..th {
            for tx in 0..tw {
                self.tile(tiles, first + ty * tw + tx, x + 8 * tx as i32, y + 8 * ty as i32, pal, (false, false), false);
            }
        }
    }
    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: [u8; 4]) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.put(xx, yy, c);
            }
        }
    }
}

/// An LZ77 stream at `at` of a file, and where the next one starts (on a word).
fn stream(b: &[u8], at: usize) -> Option<(Vec<u8>, usize)> {
    let s = b.get(at..)?;
    let data = crate::ds_art::lz10(s)?;
    let end = crate::ds_art::lz10_end(s)?;
    Some((data, (at + end + 3) & !3))
}

struct Art {
    /// `res_versus`: the card's tiles and the five armies' palettes.
    versus: Vec<u8>,
    versus_pal: Vec<[u16; 16]>,
    /// The title's glyphs and crests, their palettes.
    font: Vec<u8>,
    crests: Vec<u8>,
    font_pal: [u16; 16],
    crest_pal: [u16; 16],
    /// `res_icon4_cg_E` (the tabs' labels), their palette.
    labels: Vec<u8>,
    label_pal: [u16; 16],
    /// `res_tpicon2_lang_E`'s arrows, their palette.
    arrows: Vec<u8>,
    arrow_pal: [u16; 16],
    /// `res_syogunselect_lang_E`: the CO screen's cards and panel.
    lang: Vec<u8>,
    /// `res_syogunselect`: the flags, their palette.
    badges: Vec<u8>,
    badge_pal: [u16; 16],
    name_pal: [u16; 16],
    /// The backgrounds, drawn once: Versus' (wall, crests, title) and the CO screen's (rings), RGBA.
    versus_bg: Vec<u8>,
    pick_bg: Vec<u8>,
    /// The cursor's corners (TL, TR, BL, BR), RGBA 8 x 8.
    corners: [[[u8; 4]; 64]; 4],
}

fn build_art() -> Option<Art> {
    let pack = crate::ds_pack::pack()?;
    let v = pack.file("ohashi/res_versus")?;
    let (versus, at) = stream(v, 0)?;
    let versus_pal = (0..5).map(|k| pal16(v, at + 32 * k)).collect::<Option<Vec<_>>>()?;
    let wall = pack.file("ohashi/res_wall_single")?;
    let (wall_tiles, at) = stream(wall, 0)?;
    let (wall_map, _) = stream(wall, at)?;
    let wall_pal = pal16(wall, wall.len().checked_sub(32)?)?;
    let f = pack.file("ohashi/res_modefont")?;
    let (font, at) = stream(f, 0)?;
    let (_, at) = stream(f, at)?;
    let (crests, _) = stream(f, at)?;
    let font_pal = pal16(f, f.len().checked_sub(64)?)?;
    let crest_pal = pal16(f, f.len().checked_sub(32)?)?;
    let sg = pack.file("ohashi/res_syogunselect")?;
    let (badges, at) = stream(sg, 0)?;
    let badge_pal = pal16(sg, at)?;
    let (lang, _) = stream(pack.file("ohashi/res_syogunselect_lang_E")?, 0)?;
    let (arrows, _) = stream(pack.file("ohashi/res_tpicon2_lang_E")?, 0)?;
    let ring = pack.file("ohashi/res_wall_base")?;
    let (_, at) = stream(ring, 0)?;
    let (_, at) = stream(ring, at)?;
    let (ring_tiles, at) = stream(ring, at)?;
    let (ring_map, _) = stream(ring, at)?;
    let ring_pal = pal16(ring, ring.len().checked_sub(32)?)?;
    let arm = |addr: u32| pal16(pack.arm9_at(addr, 32)?, 0);
    let mut art = Art {
        versus,
        versus_pal,
        font,
        crests,
        font_pal,
        crest_pal,
        labels: pack.file("icon/res_icon4_cg_E")?.to_vec(),
        label_pal: arm(0x0213_9288)?,
        arrows,
        arrow_pal: pal16(pack.file("commo/res_wireless_icon")?, 512)?,
        lang,
        badges,
        badge_pal,
        name_pal: arm(0x0213_4D48)?,
        versus_bg: Vec::new(),
        pick_bg: Vec::new(),
        corners: crate::ds_menus::corner_marks()?,
    };
    art.versus_bg = versus_background(&art, &wall_tiles, &wall_map, &wall_pal);
    art.pick_bg = ring_background(&ring_tiles, &ring_map, &ring_pal);
    Some(art)
}

fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(build_art).as_ref()
}

/// The tilemap entry `i` of a map: (tile, flips).
fn entry(map: &[u8], i: usize) -> (usize, (bool, bool)) {
    let e = map.get(2 * i..2 * i + 2).map_or(0, |b| u16::from_le_bytes([b[0], b[1]]));
    ((e & 0x3FF) as usize, (e & 0x400 != 0, e & 0x800 != 0))
}

/// Versus' wall as Dual Strike's bottom screen shows it (its map is 32 x 64 tiles; the picture is scrolled to where the
/// title bands lie behind the cards), the crests and the title over it.
const WALL_SCROLL_Y: usize = 446;

fn versus_background(a: &Art, tiles: &[u8], map: &[u8], pal: &[u16; 16]) -> Vec<u8> {
    let mut buf = vec![255u8; W * H * 4];
    let mut cv = Canvas { rgba: &mut buf };
    for y in 0..H {
        let wy = (y + WALL_SCROLL_Y) % 512;
        for x in 0..W {
            let (t, (hf, vf)) = entry(map, (wy / 8) * 32 + x / 8);
            let (px, py) = (x % 8, wy % 8);
            let v = tile_px(tiles, t, if hf { 7 - px } else { px }, if vf { 7 - py } else { py }) as usize;
            cv.put(x as i32, y as i32, rgba_of(pal[v]));
        }
    }
    cv.sprite(&a.crests, 0, 8, 8, -2, -3, &a.crest_pal);
    cv.sprite(&a.crests, 64, 8, 8, 181, -3, &a.crest_pal);
    // NORMAL * BATTLE: 12 pixels a glyph (Dual Strike's spacing).
    let mut x = 40;
    for ch in "NORMAL*BATTLE".chars() {
        let g = if ch == '*' { 26 } else { ch as usize - 'A' as usize };
        cv.sprite(&a.font, g * 8, 2, 4, x, 0, &a.font_pal);
        x += 12;
    }
    buf
}

fn ring_background(tiles: &[u8], map: &[u8], pal: &[u16; 16]) -> Vec<u8> {
    let mut buf = vec![255u8; W * H * 4];
    let mut cv = Canvas { rgba: &mut buf };
    for ty in 0..H / 8 {
        for tx in 0..W / 8 {
            let (t, flip) = entry(map, ty * 32 + tx);
            cv.tile(tiles, t, 8 * tx as i32, 8 * ty as i32, pal, flip, true);
        }
    }
    buf
}

// --- A CO's pictures ------------------------------------------------------------------------------------

/// A CO's 48 x 48 mug (36 tiles in rows of six) and its colours.
pub struct Mug {
    pub tiles: Vec<u8>,
    pub pal: [u16; 16],
    /// Where Dual Strike cuts the mug for its two cells: the 24-pixel cell of Versus' cards starts this many pixels from
    /// the mug's left, the grid's 16-pixel strip this many rows from its top.
    pub cell_x: usize,
    pub strip_y: usize,
}

/// Where Dual Strike's Versus cell starts in each CO's mug (pixels; measured in melonDS by cycling the P1 card through the
/// COs and fitting each cell to the mug file): 16 unless listed (Dual Strike ids).
const CELL_X: [(u8, usize); 14] = [(1, 8), (7, 8), (25, 8), (8, 24), (9, 24), (10, 24), (16, 24), (14, 21), (17, 21), (19, 20), (22, 19), (15, 10), (21, 10), (4, 16)];
/// The rows its grid strip (the CO screen's cells: 16 rows of the 48-pixel-wide mug) starts at: 16 unless listed.
const STRIP_Y: [(u8, usize); 7] = [(16, 8), (6, 8), (23, 8), (26, 8), (27, 8), (12, 8), (14, 24)];

fn crop_of(ds: Option<u8>) -> (usize, usize) {
    let find = |t: &[(u8, usize)]| ds.and_then(|d| t.iter().find(|e| e.0 == d)).map_or(16, |e| e.1);
    (find(&CELL_X), find(&STRIP_Y))
}

/// A CO's name (six 8 x 16 columns: each column's top tile then its bottom).
pub struct Name {
    pub tiles: Vec<u8>,
}

fn pal_of(b: &[u8]) -> [u16; 16] {
    pal16(b, 0).unwrap_or([0; 16])
}

/// A Dual Strike CO's pictures straight from the pack (previews).
pub fn art_mug(ds: u8) -> Option<Arc<Mug>> {
    let a = crate::ds_co_art::co_art(ds)?;
    let (cell_x, strip_y) = crop_of(Some(ds));
    Some(Arc::new(Mug { tiles: a.face[0].clone(), pal: pal_of(a.palette.get(..32)?), cell_x, strip_y }))
}

pub fn art_name(ds: u8) -> Option<Arc<Name>> {
    Some(Arc::new(Name { tiles: crate::ds_co_art::co_art(ds)?.name }))
}

const PRESENTATION_POOL: u32 = 0x0803_9B7C;
const PRESENTATION_ROW: u32 = 0x44;

/// A CO's row of the game's presentation table (AW2's, tangoAW2's with the new COs).
fn row(core: &Core, co: u8) -> Option<u32> {
    let row = core.raw_read_32(PRESENTATION_POOL, -1).checked_add(PRESENTATION_ROW * co as u32)?;
    (0x0800_0000..0x0A00_0000).contains(&row).then_some(row)
}

/// Dual Strike's own mug and name of a CO it has (AW2's and the nine new ones), kept: the screens ask every frame.
fn ds_pictures(co: u8) -> Option<(Arc<Mug>, Arc<Name>)> {
    static CACHE: OnceLock<Mutex<HashMap<u8, Option<(Arc<Mug>, Arc<Name>)>>>> = OnceLock::new();
    let ds = crate::tag::ds_id(co)?;
    let mut g = CACHE.get_or_init(Default::default).lock().ok()?;
    g.entry(ds).or_insert_with(|| Some((art_mug(ds)?, art_name(ds)?))).clone()
}

/// The mug: Dual Strike's for a CO it has, the game's own (`+0x0C`, LZ77; the CO's palette `+0x08`) for the others.
fn mug(core: &Core, co: u8) -> Option<Arc<Mug>> {
    if let Some((m, _)) = ds_pictures(co) {
        return Some(m);
    }
    let row = row(core, co)?;
    let mut tiles = crate::invention_art::lz77(core, core.raw_read_32(row + 0x0C, -1));
    tiles.resize(36 * 32, 0);
    let (cell_x, strip_y) = crop_of(None);
    Some(Arc::new(Mug { tiles, pal: pal_of(&crate::tag_ui::co_palette(core, co)), cell_x, strip_y }))
}

/// The name: Dual Strike's for a CO it has, the game's own (`+0x04`, LZ77) for the others.
fn name(core: &Core, co: u8) -> Option<Arc<Name>> {
    if let Some((_, n)) = ds_pictures(co) {
        return Some(n);
    }
    let row = row(core, co)?;
    let mut tiles = crate::invention_art::lz77(core, core.raw_read_32(row + 0x04, -1));
    tiles.resize(12 * 32, 0);
    Some(Arc::new(Name { tiles }))
}


// --- Versus ---------------------------------------------------------------------------------------------

/// The tab's label.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Tab {
    /// A human player: P1 .. P4.
    Player(u8),
    Cpu,
}

pub struct VersusArmy {
    /// 0 Orange Star .. 4 Black Hole.
    pub colour: u8,
    pub main: Option<Arc<Mug>>,
    pub partner: Option<Arc<Mug>>,
    pub tab: Tab,
}

/// What the Teams screen's cursor is on.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Stop {
    None,
    Main(usize),
    Partner(usize),
    Tab(usize),
}

/// Where the cards lie: 48 pixels each, 8 apart (none at five armies, which fill the screen).
fn card_x(n: usize, i: usize) -> i32 {
    let gap = if n <= 4 { 8 } else { 0 };
    let total = 48 * n as i32 + gap * (n as i32 - 1);
    (W as i32 - total) / 2 + i as i32 * (48 + gap)
}

const TAB_Y: i32 = 32;
const CARD_Y: i32 = 66;
/// The portraits' top.
const MUG_Y: i32 = CARD_Y + 16;

fn corners(cv: &mut Canvas, a: &Art, x: i32, y: i32, w: i32, h: i32) {
    let at = [(-2, -2), (w - 6, -2), (-2, h - 6), (w - 6, h - 6)];
    for (c, (dx, dy)) in a.corners.iter().zip(at) {
        for (i, p) in c.iter().enumerate() {
            if p[3] != 0 {
                cv.put(x + dx + (i % 8) as i32, y + dy + (i / 8) as i32, *p);
            }
        }
    }
}

fn arrow(cv: &mut Canvas, a: &Art, x: i32, y: i32, up: bool) {
    cv.sprite(&a.arrows, if up { 48 } else { 52 }, 2, 2, x, y, &a.arrow_pal);
}

/// The Teams screen.
pub fn draw_versus(a: &Art, cv: &mut Canvas, armies: &[VersusArmy], stop: Stop) {
    cv.rgba.copy_from_slice(&a.versus_bg);
    let n = armies.len().clamp(1, 5);
    for (i, army) in armies.iter().take(5).enumerate() {
        let x = card_x(n, i);
        let c = (army.colour as usize).min(4);
        let pal = &a.versus_pal[c];
        // The tab: a rounded box (tiles 1..4: corners 3, edges 4, sides 1, fill 2) with its label.
        let (bx, by) = (x + 8, TAB_Y);
        for r in 0..4usize {
            for col in 0..4usize {
                let t = [[3, 4, 4, 3], [1, 2, 2, 1], [1, 2, 2, 1], [3, 4, 4, 3]][r][col];
                cv.tile(&a.versus, t, bx + 8 * col as i32, by + 8 * r as i32, pal, (col == 3, r == 0), false);
            }
        }
        let label = match army.tab {
            Tab::Player(k) => 395 + 4 * (k.clamp(1, 4) as usize - 1),
            Tab::Cpu => 411,
        };
        cv.sprite(&a.labels, label, 2, 2, bx + 8, by + 8, &a.label_pal);
        // The card.
        let e = 21 + 4 * c;
        let head = [[7, 8, e, e + 1, 8, 7], [10, 11, e + 2, e + 3, 11, 10]];
        for (r, row) in head.iter().enumerate() {
            for (col, &t) in row.iter().enumerate() {
                cv.tile(&a.versus, t, x + 8 * col as i32, CARD_Y + 8 * r as i32, pal, (col >= 4, false), false);
            }
        }
        for r in 0..6usize {
            for col in 0..6usize {
                cv.tile(&a.versus, 41 + 6 * r + col, x + 8 * col as i32, CARD_Y + 16 + 8 * r as i32, pal, (false, false), false);
            }
        }
        for col in 0..6 {
            cv.tile(&a.versus, 4, x + 8 * col, CARD_Y + 64, pal, (false, false), false);
        }
        for (k, co) in [&army.main, &army.partner].into_iter().enumerate() {
            let cx = x + 24 * k as i32;
            // (a cell is white behind its portrait)
            cv.rect(cx, MUG_Y, 24, 48, rgba_of(pal[1]));
            match co {
                Some(co) => {
                    // The cell: 24 pixels of the mug, from where Dual Strike cuts it.
                    for y in 0..48usize {
                        for x in 0..24usize {
                            let sx = co.cell_x + x;
                            let v = tile_px(&co.tiles, (y / 8) * 6 + sx / 8, sx % 8, y % 8) as usize;
                            if v != 0 {
                                cv.put(cx + x as i32, MUG_Y + y as i32, rgba_of(co.pal[v]));
                            }
                        }
                    }
                }
                // (no partner: the empty slot's pale colour, the card's lightest)
                None if k == 1 => cv.rect(cx, MUG_Y, 24, 48, rgba_of(pal[0])),
                None => {}
            }
            // Dual Strike draws every cell in a thin dark green frame (the ink of its name plates).
            let green = rgba_of(a.name_pal[15]);
            for i in 0..24 {
                cv.put(cx + i, MUG_Y, green);
                cv.put(cx + i, MUG_Y + 47, green);
            }
            for j in 0..48 {
                cv.put(cx, MUG_Y + j, green);
                cv.put(cx + 23, MUG_Y + j, green);
            }
        }
        // The cursor.
        match stop {
            Stop::Main(s) | Stop::Partner(s) if s == i => {
                let k = if matches!(stop, Stop::Partner(_)) { 1 } else { 0 };
                let cx = x + 24 * k;
                corners(cv, a, cx, MUG_Y, 24, 48);
                arrow(cv, a, cx + 4, MUG_Y - 18, true);
                arrow(cv, a, cx + 4, MUG_Y + 50, false);
            }
            Stop::Tab(s) if s == i => {
                corners(cv, a, bx, by, 32, 32);
            }
            _ => {}
        }
    }
}

// --- The CO screen ---------------------------------------------------------------------------------------

/// What one name plate shows.
#[derive(Clone)]
pub struct Slot {
    pub name: Option<Arc<Name>>,
}

pub struct Card {
    pub colour: u8,
    pub main: Slot,
    pub partner: Option<Slot>,
}

pub struct Cell {
    /// None: a locked CO (a black cell).
    pub mug: Option<Arc<Mug>>,
    /// The pick's flag: (army colour 0..4, 1 or 2).
    pub flag: Option<(u8, u8)>,
}

pub struct PickView {
    pub cards: Vec<Card>,
    /// The plate being picked: (card, partner).
    pub active: Option<(usize, bool)>,
    pub cells: Vec<Cell>,
    /// The cell under the cursor.
    pub cursor: usize,
}

const PANEL_X: i32 = 4;
const CELL_COLUMNS: usize = 4;

/// A card's tiles (of `ohashi/res_syogunselect_lang_E`: 8 wide), by row: the header's emblem pieces are filled in.
const CARD_ROWS: [[(usize, bool); 8]; 7] = [
    [(6, false), (7, false), (8, false), (0, false), (0, false), (8, true), (7, true), (6, true)],
    [(9, false), (10, false), (11, false), (0, false), (0, false), (11, true), (10, true), (9, true)],
    [(1, false), (2, false), (2, false), (2, false), (2, false), (74, false), (75, false), (1, true)],
    [(1, false), (72, false), (73, false), (73, false), (73, false), (76, false), (77, false), (1, true)],
    [(1, false), (2, false), (2, false), (2, false), (2, false), (78, false), (79, false), (1, true)],
    [(1, false), (72, false), (73, false), (73, false), (73, false), (80, false), (81, false), (1, true)],
    [(3, false), (4, false), (4, false), (4, false), (4, false), (4, true), (4, true), (3, true)],
];

/// A card's height with one plate, and with two (the foot is its last row).
const CARD_ONE: i32 = 40;
const CARD_TWO: i32 = 56;

fn card(cv: &mut Canvas, a: &Art, x: i32, c: &Card, active: Option<bool>) {
    let pal = &a.versus_pal[(c.colour as usize).min(4)];
    let e = 21 + 4 * (c.colour as usize).min(4);
    let rows: Vec<usize> = if c.partner.is_some() { (0..7).collect() } else { vec![0, 1, 2, 3, 6] };
    for (k, &r) in rows.iter().enumerate() {
        for (col, &(t, hf)) in CARD_ROWS[r].iter().enumerate() {
            let cx = x + 8 * col as i32;
            let cy = 8 * k as i32;
            if r < 2 && (3..5).contains(&col) {
                // The emblem: the Versus file's tiles in the army's colours.
                cv.tile(&a.versus, e + 2 * r + (col - 3), cx, cy, pal, (false, false), false);
            } else if t != 0 {
                cv.tile(&a.lang, t, cx, cy, pal, (hf, false), false);
            }
        }
    }
    for (k, slot) in [Some(&c.main), c.partner.as_ref()].into_iter().enumerate() {
        let Some(nm) = slot.and_then(|s| s.name.as_ref()) else { continue };
        for col in 0..6usize {
            for h in 0..2usize {
                cv.tile(&nm.tiles, 2 * col + h, x + 8 + 8 * col as i32, 16 + 16 * k as i32 + 8 * h as i32, &a.name_pal, (false, false), false);
            }
        }
    }
    if let Some(p) = active {
        let y = if p { 32 } else { 16 };
        corners(cv, a, x + 8, y, 48, 16);
    }
}

/// The panel: a header band, the body (`rows` rows of tiles) and the crest at its foot.
fn panel(cv: &mut Canvas, a: &Art, x: i32, y: i32, body: usize) {
    let pal = &a.versus_pal[0];
    let band = |r: usize, col: usize| -> (usize, bool) {
        let (edge, fill, text0) = if r == 0 { ([6, 7, 8], 12, 82) } else { ([9, 10, 11], 13, 95) };
        match col {
            0..=2 => (edge[col], false),
            3 => (fill, false),
            4..=7 => (fill, true),
            8..=20 => (text0 + col - 8, false),
            21..=25 => (fill, true),
            26..=28 => (edge[28 - col], true),
            _ => (0, false),
        }
    };
    for r in 0..2usize {
        for col in 0..29usize {
            let (t, hf) = band(r, col);
            cv.tile(&a.lang, t, x + 8 * col as i32, y + 8 * r as i32, pal, (hf, false), false);
        }
    }
    for k in 0..body {
        for col in 0..29usize {
            let (t, hf) = match col {
                0 => (1, false),
                1..=26 => (2, false),
                27 => (2, true),
                _ => (1, true),
            };
            let crest = body >= 6 && k + 6 >= body && (21..=27).contains(&col);
            let (t, hf) = if crest { (30 + 7 * (k + 6 - body) + (col - 21), false) } else { (t, hf) };
            cv.tile(&a.lang, t, x + 8 * col as i32, y + 16 + 8 * k as i32, pal, (hf, false), !crest);
        }
    }
}

fn flag(cv: &mut Canvas, a: &Art, x: i32, y: i32, colour: u8, number: u8) {
    let mut pal = a.badge_pal;
    let k = if colour >= 4 {
        // Black Hole's flag: the red one in the grey of its card.
        pal[3] = a.versus_pal[4][4];
        number as usize - 1
    } else {
        colour as usize * 2 + (number as usize - 1)
    };
    cv.sprite(&a.badges, 12 + 4 * k, 2, 2, x, y, &pal);
}

fn cell(cv: &mut Canvas, a: &Art, x: i32, y: i32, c: &Cell) {
    cv.rect(x, y, 48, 16, [255, 255, 255, 255]);
    match &c.mug {
        Some(m) => {
            // The strip: 16 rows of the mug's whole width from where Dual Strike cuts it.
            for j in 0..16usize {
                for i in 0..48usize {
                    let sy = m.strip_y + j;
                    let v = tile_px(&m.tiles, (sy / 8) * 6 + i / 8, i % 8, sy % 8) as usize;
                    if v != 0 {
                        cv.put(x + i as i32, y + j as i32, rgba_of(m.pal[v]));
                    }
                }
            }
        }
        None => cv.rect(x, y, 41, 16, [0, 0, 0, 255]),
    }
    let black = [0, 0, 0, 255];
    for i in 0..48 {
        cv.put(x + i, y, black);
        cv.put(x + i, y + 15, black);
    }
    for j in 0..16 {
        cv.put(x, y + j, black);
        cv.put(x + 47, y + j, black);
    }
    if let Some((colour, n)) = c.flag {
        flag(cv, a, x + 32, y, colour, n);
    }
}

pub fn draw_pick(a: &Art, cv: &mut Canvas, v: &PickView) {
    cv.rgba.copy_from_slice(&a.pick_bg);
    let n = v.cards.len().clamp(1, 4);
    let tall = v.cards.iter().any(|c| c.partner.is_some());
    let gap = 8;
    let x0 = (W as i32 - (64 * n as i32 + gap * (n as i32 - 1))) / 2;
    for (i, c) in v.cards.iter().take(4).enumerate() {
        let active = v.active.and_then(|(k, p)| (k == i).then_some(p));
        card(cv, a, x0 + i as i32 * (64 + gap), c, active);
    }
    let top = if tall { CARD_TWO } else { CARD_ONE };
    let body = (H as i32 - top - 16 + 7) / 8;
    panel(cv, a, PANEL_X, top, body as usize);
    // Dual Strike's cells touch (16 rows a cell) on the War Room's screen, where all of them show, and lie 24 rows apart
    // (a gap between) on the campaigns', which show five rows. The grid scrolls a row at a time, the cursor's row kept in view.
    let pitch = if v.cards.len() == 1 && !tall { 16 } else { 24 };
    let rows = v.cells.len().div_ceil(CELL_COLUMNS);
    let start = top + 16;
    let visible = (((H as i32 - start) / pitch) as usize).max(1);
    let cur_row = v.cursor / CELL_COLUMNS;
    let first = cur_row.saturating_sub(visible.saturating_sub(1)).min(rows.saturating_sub(visible));
    for (k, c) in v.cells.iter().enumerate() {
        let (r, col) = (k / CELL_COLUMNS, k % CELL_COLUMNS);
        if r < first || r >= first + visible + 1 {
            continue;
        }
        cell(cv, a, PANEL_X + 8 + 56 * col as i32, start + pitch * (r - first) as i32, c);
    }
    if v.cursor < v.cells.len() {
        let (r, col) = (v.cursor / CELL_COLUMNS, v.cursor % CELL_COLUMNS);
        if r >= first {
            corners(cv, a, PANEL_X + 8 + 56 * col as i32, start + pitch * (r - first) as i32, 48, 16);
        }
    }
}

/// Draws the views into the 240 x 160 RGBA picture `rgba` (previews).
pub fn render_versus(rgba: &mut [u8], armies: &[VersusArmy], stop: Stop) -> bool {
    let Some(a) = art() else { return false };
    draw_versus(a, &mut Canvas { rgba }, armies, stop);
    true
}

pub fn render_pick(rgba: &mut [u8], v: &PickView) -> bool {
    let Some(a) = art() else { return false };
    draw_pick(a, &mut Canvas { rgba }, v);
    true
}

// --- The game's state -------------------------------------------------------------------------------------

const TEAMS: u32 = 0x0201_7C50;
const TEAMS_FIVE: u32 = 0x0203_0300;

/// Versus' Teams screen, as the Teams record has it.
fn versus_view(core: &Core) -> Option<(Vec<VersusArmy>, Stop)> {
    if !crate::pvp::in_versus(core) || !crate::pvp::on_teams_screen(core) {
        return None;
    }
    let five = crate::five::active(core);
    let rec = if five { TEAMS_FIVE } else { TEAMS };
    // The Teams stage (the Rules stage is the game's own).
    if core.raw_read_8(rec + 0x30, -1) != 1 {
        return None;
    }
    let n = crate::tag_ui::armies(core) as usize;
    let (controllers, colours) = if five { (rec + 0x90, rec + 0x98) } else { (rec + 0x09, rec + 0x0D) };
    let mut humans = 0u8;
    let mut armies = Vec::new();
    for k in 0..n {
        let colour = core.raw_read_8(colours + k as u32, -1).clamp(1, 5) - 1;
        let tab = if core.raw_read_8(controllers + k as u32, -1) == 1 {
            humans += 1;
            Tab::Player(humans)
        } else {
            Tab::Cpu
        };
        let main = crate::tag_ui::army_main(core, k as u32).and_then(|co| mug(core, co));
        let partner = match core.raw_read_8(crate::tag::TEAMS_PARTNER + k as u32, -1) {
            0xFF => None,
            co => mug(core, co),
        };
        armies.push(VersusArmy { colour, main, partner, tab });
    }
    let cursor = core.raw_read_8(rec + 0x32, -1) as usize;
    let army = cursor / 2;
    let stop = if army >= n {
        Stop::None
    } else if cursor % 2 == 1 {
        Stop::Tab(army)
    } else if crate::tag_ui::editing(core) == Some(army as u32) {
        Stop::Partner(army)
    } else {
        Stop::Main(army)
    };
    Some((armies, stop))
}

const PROC_POOL: (u32, u32) = (0x0200_D610, 0x0200_E418);
const PROC_SIZE: u32 = 0x6C;
const CO_SELECT: u32 = 0x0861_6638;
const CO_LIST: u32 = 0x0300_58E0;
const CO_GROUPS: u32 = 0x0300_5944;
const GROUP_SIZES: u32 = 0x0300_5948;
const PICKS: u32 = 0x0300_58D4;
const CO_TABLE_POOL: u32 = 0x0804_2DDC;

/// A CO's country (0 Orange Star .. 4 Black Hole): the CO table's byte.
fn country(core: &Core, co: u8) -> u8 {
    let table = core.raw_read_32(CO_TABLE_POOL, -1);
    core.raw_read_8(table + co as u32 * 0x104 + 0x15, -1).min(4)
}

/// The CO screen's cards, over the picks made and the CO under the cursor.
fn cards(core: &Core, picks: &[u8], cur: u8) -> (Vec<Card>, Option<(usize, bool)>, Vec<(u8, u8, u8)>) {
    // (colour, army, number) of each pick made, for the flags.
    let mut flags = Vec::new();
    let pic = |co: u8| Slot { name: name(core, co) };
    let done = picks.len();
    if let Some(m) = crate::ds_campaign::mission_info(core) {
        let (n, k) = crate::tag::ds_partner_picks(core);
        let (n, k) = (n as usize, k as usize);
        let armies = (m.armies as usize).min(4);
        let mut out = Vec::new();
        let mut active = None;
        let fixed = |k: usize, partner: bool| -> Option<u8> {
            let (a, b) = match &m.native {
                Some(nat) => nat.cos[k],
                None => (crate::ds_campaign_data::aw2_co(m.cos[k].0).unwrap_or(0xFF), crate::ds_campaign_data::aw2_co(m.cos[k].1).unwrap_or(0xFF)),
            };
            let co = if partner { b } else { a };
            (co != 0xFF).then_some(co)
        };
        let lead = m.native.as_ref().and_then(|nat| nat.lead_lock);
        let five_pick = m.native.as_ref().is_some_and(|nat| nat.five_pick.is_some());
        let slot = |idx: usize| -> Slot {
            if idx < done {
                pic(picks[idx])
            } else if idx == done {
                pic(cur)
            } else {
                Slot { name: None }
            }
        };
        for a in 0..armies {
            // (a mission whose player is the fifth army, Black Hole, picks on army 1's place)
            let colour = if five_pick && a == 0 { 4 } else { m.colours[a].clamp(1, 5) - 1 };
            let picking = a < n;
            let (main, partner) = if picking && a == 0 && lead.is_some() {
                // The army leads with a fixed CO and picks only its partner.
                if done == 0 {
                    active = Some((0, true));
                } else {
                    flags.push((colour, picks[0], 2));
                }
                (Slot { name: lead.and_then(|c| name(core, c)) }, Some(slot(0)))
            } else if picking {
                if a == done && done < n + k {
                    active = Some((a, false));
                }
                if a < done {
                    flags.push((colour, picks[a], 1));
                }
                let partner = (a < k).then(|| {
                    if n + a == done {
                        active = Some((a, true));
                    }
                    if n + a < done {
                        flags.push((colour, picks[n + a], 2));
                    }
                    slot(n + a)
                });
                (slot(a), partner)
            } else {
                let main = Slot { name: fixed(a, false).and_then(|c| name(core, c)) };
                let partner = fixed(a, true).map(|c| Slot { name: name(core, c) });
                (main, partner)
            };
            out.push(Card { colour, main, partner });
        }
        if n > 0 && !out.is_empty() {
            return (out, active, flags);
        }
    }
    // The War Room, AW2's campaign: one army, one CO; its colour its CO's country.
    let co = if done > 0 { picks[0] } else { cur };
    let colour = country(core, if done == 0 { cur } else { co });
    if done > 0 {
        flags.push((colour, picks[0], 1));
    }
    (vec![Card { colour, main: pic(if done == 0 { cur } else { picks[0] }), partner: None }], (done == 0).then_some((0, false)), flags)
}

/// The CO screen (the campaigns', the War Room's) while it is up.
fn pick_view(core: &Core) -> Option<PickView> {
    let proc = (PROC_POOL.0..PROC_POOL.1).step_by(PROC_SIZE as usize).find(|&p| core.raw_read_32(p, -1) == CO_SELECT)?;
    let groups = core.raw_read_32(CO_GROUPS, -1) as usize;
    if !(1..=5).contains(&groups) {
        return None;
    }
    let sizes: Vec<usize> = (0..groups).map(|g| core.raw_read_8(GROUP_SIZES + g as u32, -1) as usize).collect();
    let total: usize = sizes.iter().sum();
    if total == 0 || total > 63 {
        return None;
    }
    let offered: Vec<u8> = (0..total).map(|k| core.raw_read_8(CO_LIST + k as u32, -1)).collect();
    let group = core.raw_read_32(proc + 0x58, -1) as usize;
    let size = *sizes.get(group)?;
    if size == 0 {
        return None;
    }
    let k = core.raw_read_16(proc + 0x52, -1) as usize % size + core.raw_read_32(proc + 0x5C, -1) as usize;
    let cur = *offered.get(k)?;
    let idx = (core.raw_read_16(proc + 0x64, -1) as usize).min(8);
    let picks: Vec<u8> = (0..idx).map(|j| core.raw_read_8(PICKS + j as u32, -1)).collect();
    // Every CO of the roster, Dual Strike's way: by country, a CO the screen does not offer locked.
    let mut all: Vec<u8> = (0..19u8).chain(crate::co_new::all().map(|n| n.0)).collect();
    for &c in &offered {
        if !all.contains(&c) {
            all.push(c);
        }
    }
    all.sort_by_key(|&c| (country(core, c), c));
    let (cards, active, flags) = cards(core, &picks, cur);
    let cells: Vec<Cell> = all
        .iter()
        .map(|&c| {
            let flag = flags.iter().find(|f| f.1 == c).map(|f| (f.0, f.2));
            Cell { mug: offered.contains(&c).then(|| mug(core, c)).flatten(), flag }
        })
        .collect();
    let cursor = all.iter().position(|&c| c == cur)?;
    Some(PickView { cards, active, cells, cursor })
}

// --- The frame --------------------------------------------------------------------------------------------

/// Draws the screen over the finished picture, if one of ours is up.
pub fn apply(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 || !ds_graphics(core) {
        return;
    }
    if crate::ds_co_page::is_open() || crate::skills_panel::is_open(core) {
        return;
    }
    let Some(a) = art() else { return };
    if let Some((armies, stop)) = versus_view(core) {
        draw_versus(a, &mut Canvas { rgba }, &armies, stop);
    } else if let Some(v) = pick_view(core) {
        draw_pick(a, &mut Canvas { rgba }, &v);
    }
}

/// Whether Versus' Teams screen or the CO screen is Dual Strike's now (tests).
pub fn shown(core: &Core) -> bool {
    ds_graphics(core) && art().is_some() && (versus_view(core).is_some() || pick_view(core).is_some())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_cards_fill_the_screen_and_fewer_stay_inside_it() {
        assert_eq!(card_x(5, 0), 0);
        assert_eq!(card_x(5, 4) + 48, W as i32);
        for n in 1..=4 {
            assert!(card_x(n, 0) >= 0 && card_x(n, n - 1) + 48 <= W as i32, "{n} cards");
            // centred
            assert_eq!(card_x(n, 0), W as i32 - (card_x(n, n - 1) + 48));
        }
    }

    /// With `TANGOAW2_DS_ROM` naming a Dual Strike (USA) ROM: the art builds, the five armies have a palette each and the
    /// Versus screen draws all five emblems in their own colours (red, blue, green, yellow, grey).
    /// `cargo test -p tango-gamesupport-aw2 -- --ignored ds_coselect`.
    #[test]
    #[ignore]
    fn the_art_builds_and_five_armies_draw() {
        let rom = std::fs::read(std::env::var_os("TANGOAW2_DS_ROM").expect("TANGOAW2_DS_ROM")).unwrap();
        assert!(crate::ds_pack::offer_rom(&rom));
        let a = art().expect("art");
        assert_eq!(a.versus_pal.len(), 5);
        let armies: Vec<VersusArmy> = (0..5).map(|c| VersusArmy { colour: c, main: art_mug(2), partner: None, tab: Tab::Cpu }).collect();
        let mut buf = vec![0u8; W * H * 4];
        draw_versus(a, &mut Canvas { rgba: &mut buf }, &armies, Stop::None);
        // The fifth card's foot line is Black Hole's grey, the first's Orange Star's red.
        let at = |x: usize, y: usize| [buf[4 * (y * W + x)], buf[4 * (y * W + x) + 1], buf[4 * (y * W + x) + 2]];
        let foot = (CARD_Y + 64 + 3) as usize;
        let (first, last) = (at(4, foot), at(236, foot));
        assert!(first[0] > 200 && first[1] < 80, "Orange Star's card is red: {first:?}");
        assert!((last[0] as i32 - last[1] as i32).abs() < 12 && (last[1] as i32 - last[2] as i32).abs() < 12, "Black Hole's is grey: {last:?}");
    }
}
