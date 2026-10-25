//! Dual Strike's menus on the GBA screen, with the pack and "Dual Strike map
//! graphics" on (offline): the unit command menu (the list beside the unit,
//! the B CANCEL tag) and the map menu (the list, a one-line description
//! box, the tag), drawn as Dual Strike draws them.
//!
//! Dual Strike's own art is read from the player's ROM (the pack): the
//! frame's tiles (`bmap/09f`, colours `bmap/0a0`), the icons
//! (`icon/res_icon0_cg_E`, colours `icon/res_icon_cl`) and the text font,
//! which is kept in overlay 0 (a pointer per character at `0x022F67D8`, 4
//! bits a pixel, 16 rows, one to four bytes a row; a letter takes the
//! width of its ink and a pixel more, a space three). The descriptions are
//! Dual Strike's strings from the same overlay. What the files do not hold
//! is drawn by tangoAW2: nothing now. The selection's corner marks and the B
//! CANCEL tag are Dual Strike's own sprites, from a compressed sheet in
//! overlay 0 (`0x022CF9B0`, LZ77, 80 tiles: the corners are tiles 8, 10, 12
//! and 14, the tag 8 tiles from 56) in the colours at `0x02138C68` in the ARM9
//! image; the Drop commands show the cargo's picture, as in Dual Strike.
//!
//! How it works. AW2 builds a menu in a proc whose script is
//! [`MENU_SCRIPT`]: the table of entries (`+0x20`), the shown entries
//! (`+0x31`), their number (`+0x41`), the cursor (`+0x42`). While the mode
//! is on, the calls that would draw the unit and map menus' items, frame and
//! hand are skipped (traps, so the game's own menu never shows, not even
//! for a frame) and [`apply`] draws Dual Strike's menu over the finished
//! picture, from the game's state alone: display only, nothing it keeps
//! is in the console. With the mode off nothing here does anything.

use mgba::core::Core;
use std::sync::OnceLock;

use crate::wasteland::ds_graphics;

/// Where AW2's dialogue box at the screen's bottom starts.
const BOX_BOTTOM_TOP: i32 = 112;
const W: usize = 240;
const H: usize = 160;

// --- The game's menu ---------------------------------------------------------

/// The menu procs' slot array (`CreateMenu` hands the proc out of it) and
/// the script every menu proc runs.
pub(crate) const SLOTS: u32 = 0x0300_1470;
pub(crate) const SLOT_SIZE: u32 = 0x60;
pub(crate) const SLOT_COUNT: u32 = 32;
pub(crate) const MENU_SCRIPT: u32 = 0x0848_A42C;
/// The literal-pool words naming the map menu's and the unit menu's tables
/// (they point at tangoAW2's copies while those are in use).
pub(crate) const MAP_MENU_POOL: u32 = 0x0802_D49C;
pub(crate) const UNIT_MENU_POOL: u32 = 0x0802_D59C;
pub(crate) const ENTRY: u32 = 0x20;
/// The text table: a pointer per text id.
pub(crate) const TEXT_TABLE: u32 = 0x0861_0A38;
const CURSOR_X: u32 = 0x0300_33E4;
/// The selected unit's record while a unit menu is open.
const SELECTED_UNIT: u32 = 0x0300_40D8;
const CURSOR_Y: u32 = 0x0300_33E6;
const BG3_HOFS: u32 = 0x0400_001C;
const BG3_VOFS: u32 = 0x0400_001E;

/// The calls skipped while a menu is Dual Strike's: `CreateMenu` and the
/// rebuild draw the items (`sub_08019C40`, proc in r4 / r5) and the frame
/// (`sub_0801A444`); the hand is a proc of its own (`+0x44`).
const CREATE_ITEMS: u32 = 0x0801_A0C6;
const CREATE_FRAME: u32 = 0x0801_A0E0;
const REBUILD_ITEMS: u32 = 0x0801_9EF6;
const REBUILD_FRAME: u32 = 0x0801_9F16;
const HAND_START: u32 = 0x0801_9DCC;
const HAND_FRAME: u32 = 0x0801_9DEC;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Kind {
    Unit,
    Map,
}

#[derive(Clone, Debug)]
struct Row {
    /// The icon's page (0x09, 0x0A) and code (0x80..).
    page: u8,
    icon: u8,
    text: String,
    grey: bool,
}

#[derive(Clone, Debug)]
struct Menu {
    kind: Kind,
    cursor: usize,
    rows: Vec<Row>,
}

/// The most rows the 160-pixel screen holds (2 + 2n tiles).
const MAX_ROWS: usize = 9;
/// The tag's height; the lists start below it.
const TAG_H: i32 = 18;

fn r8(core: &Core, a: u32) -> u8 {
    core.raw_read_8(a, -1)
}
fn r16(core: &Core, a: u32) -> u16 {
    core.raw_read_16(a, -1)
}
fn r32(core: &Core, a: u32) -> u32 {
    core.raw_read_32(a, -1)
}

pub(crate) fn label(core: &Core, tid: u16) -> Vec<u8> {
    let p = r32(core, TEXT_TABLE + 4 * tid as u32);
    if !(0x0800_0000..0x0A00_0000).contains(&p) {
        return Vec::new();
    }
    let mut out = Vec::new();
    for k in 0..48 {
        let b = r8(core, p + k);
        if b == 0 {
            break;
        }
        out.push(b);
    }
    out
}

/// Icon page and code, then the name (control codes dropped; the star
/// glyph `0x19` takes its operand with it).
pub(crate) fn parse_label(bytes: &[u8]) -> (u8, u8, String) {
    let (mut page, mut icon) = (0u8, 0u8);
    let mut text = String::new();
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if (b == 0x09 || b == 0x0A) && i + 1 < bytes.len() {
            page = b;
            icon = bytes[i + 1];
            i += 2;
        } else if b == 0x19 {
            i += 2;
        } else if b < 0x20 {
            i += 1;
        } else {
            text.push(b as char);
            i += 1;
        }
    }
    (page, icon, text)
}

/// The game's slot of a menu proc and what kind it is, if it is the unit or
/// the map menu (the others, Intel's and Options' lists, stay AW2's).
fn menu_slot(core: &Core, slot: u32) -> Option<Kind> {
    if r32(core, slot) != MENU_SCRIPT {
        return None;
    }
    let table = r32(core, slot + 0x20);
    let count = r8(core, slot + 0x41) as usize;
    if count == 0 || count > MAX_ROWS {
        return None;
    }
    if table == r32(core, MAP_MENU_POOL) {
        Some(Kind::Map)
    } else if table == r32(core, UNIT_MENU_POOL) {
        Some(Kind::Unit)
    } else {
        None
    }
}

fn find(core: &Core) -> Option<(u32, Menu)> {
    for i in 0..SLOT_COUNT {
        let slot = SLOTS + SLOT_SIZE * i;
        let Some(kind) = menu_slot(core, slot) else { continue };
        let table = r32(core, slot + 0x20);
        let count = r8(core, slot + 0x41) as usize;
        let mut rows = Vec::new();
        for k in 0..count {
            let idx = r8(core, slot + 0x31 + k as u32) as u32;
            let tid = r16(core, table + ENTRY * idx + 0x1C);
            let (page, icon, text) = parse_label(&label(core, tid));
            let flags = r8(core, slot + 0x24 + idx);
            rows.push(Row {
                page,
                icon,
                text,
                grey: flags & 2 != 0,
            });
        }
        let cursor = (r8(core, slot + 0x42) as usize).min(rows.len().saturating_sub(1));
        return Some((slot, Menu { kind, cursor, rows }));
    }
    None
}

// --- Traps: the game's own menu is not drawn -------------------------------------------

fn skip(core: &mut Core, to: u32) {
    core.gba_mut().cpu_mut().set_thumb_pc(to);
}

fn proc_is_ours(core: &Core, proc: u32) -> bool {
    ds_graphics(core)
        && art().is_some()
        && proc >= SLOTS
        && proc < SLOTS + SLOT_SIZE * SLOT_COUNT
        && (proc - SLOTS) % SLOT_SIZE == 0
        && menu_slot(core, proc).is_some()
}

/// A trap that skips the 4-byte `bl` it stands on when the proc in `reg`
/// is a menu of ours.
fn skip_bl(reg: usize, at: u32) -> (u32, Box<dyn Fn(&mut Core)>) {
    (
        at,
        Box::new(move |core: &mut Core| {
            let proc = core.gba().cpu().gpr(reg) as u32;
            if proc_is_ours(core, proc) {
                skip(core, at + 4);
            }
        }),
    )
}

/// The hand: its proc's functions return at once, so it is never placed.
fn hand(at: u32) -> (u32, Box<dyn Fn(&mut Core)>) {
    (
        at,
        Box::new(move |core: &mut Core| {
            if !ds_graphics(core) || art().is_none() {
                return;
            }
            let hand = core.gba().cpu().gpr(0) as u32;
            let ours = (0..SLOT_COUNT).any(|i| {
                let s = SLOTS + SLOT_SIZE * i;
                r32(core, s + 0x44) == hand && menu_slot(core, s).is_some()
            });
            if ours {
                let lr = core.gba().cpu().gpr(14) as u32;
                skip(core, lr & !1);
            }
        }),
    )
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        skip_bl(4, CREATE_ITEMS),
        skip_bl(4, CREATE_FRAME),
        skip_bl(5, REBUILD_ITEMS),
        skip_bl(5, REBUILD_FRAME),
        hand(HAND_START),
        hand(HAND_FRAME),
    ]
}

// --- Dual Strike's art, from the pack ----------------------------------------------------

/// Overlay 0: where it loads, the font's pointer table.
const OV0_BASE: u32 = 0x022A_D560;
const FONT_TABLE: u32 = 0x022F_67D8;
/// The button sprites (corner marks, B CANCEL tag): an LZ77 sheet in overlay 0, its colours in the ARM9 image.
const SPRITE_SHEET: u32 = 0x022C_F9B0;
const SPRITE_PALETTE: u32 = 0x0213_8C68;

struct Glyph {
    /// 16 rows of `cols` pixels (palette indices of the DS font).
    cols: usize,
    px: Vec<u8>,
    adv: i32,
}

struct Art {
    /// The frame's tiles 1..=10 (palette indices, 8x8), the colours.
    frame: Vec<[u8; 64]>,
    pal: [[u8; 4]; 16],
    glyphs: Vec<Option<Glyph>>,
    /// Icons by DS index: 16x16 RGBA.
    icons: Vec<[[u8; 4]; 256]>,
    /// The selection's corners (TL, TR, BL, BR; 8 x 8) and the B CANCEL tag (32 x 16), RGBA.
    corners: [[[u8; 4]; 64]; 4],
    tag: Vec<[u8; 4]>,
    strings: Strings,
}

/// Dual Strike's description lines, found in overlay 0.
struct Strings {
    co: String,
    intel: String,
    options: String,
    save: String,
    end: String,
    power: String,
    tag: String,
    change: String,
    yield_: String,
    rules: String,
    status: String,
}

/// A string of the overlay's pool, as `s` (its lines, where Dual Strike
/// breaks it, are separated by a carriage return there and a space here).
fn find_str(ov: &[u8], s: &str) -> Option<String> {
    let mut pat = s.replace(' ', " ").as_bytes().to_vec();
    pat.push(0);
    let found = |pat: &[u8]| ov.windows(pat.len()).any(|w| w == pat);
    if found(&pat) {
        return Some(s.to_string());
    }
    // Broken over lines: try each space as the break.
    for (i, _) in s.match_indices(' ') {
        let mut p = s.as_bytes()[..i].to_vec();
        p.push(b'\r');
        p.extend_from_slice(&s.as_bytes()[i + 1..]);
        p.push(0);
        if found(&p) {
            return Some(s.to_string());
        }
    }
    None
}

fn rgba_of(c: u16) -> [u8; 4] {
    crate::ds_tilt::rgba_lut()[(c & 0x7FFF) as usize]
}

fn n<T>(o: Option<T>, what: &str) -> Option<T> {
    if o.is_none() {
        log::warn!("ds_menus: {what} missing from the pack");
    }
    o
}

/// `v` within `lo..=hi`, `hi` winning where they cross (a menu taller than the
/// screen).
fn within(v: i32, lo: i32, hi: i32) -> i32 {
    v.max(lo).min(hi)
}

fn build_art() -> Option<Art> {
    let pack = n(crate::ds_pack::pack(), "pack")?;
    let ov = n(pack.overlays.first(), "overlay 0")?;
    // Frame.
    let tiles = n(pack.file("bmap/09f").and_then(crate::ds_art::lz10), "bmap/09f")?;
    let palette = n(pack.file("bmap/0a0"), "bmap/0a0")?;
    let mut pal = [[0u8; 4]; 16];
    for (i, p) in pal.iter_mut().enumerate() {
        let c = u16::from_le_bytes([*palette.get(2 * i)?, *palette.get(2 * i + 1)?]);
        *p = rgba_of(c);
    }
    pal[0] = [0, 0, 0, 0];
    let mut frame = Vec::new();
    for t in 0..=10usize {
        let mut px = [0u8; 64];
        let b = n(tiles.get(32 * t..32 * t + 32), "frame tile")?;
        for y in 0..8 {
            for x in 0..8 {
                px[y * 8 + x] = (b[y * 4 + x / 2] >> (4 * (x & 1))) & 15;
            }
        }
        frame.push(px);
    }
    // Font.
    let mut ptrs = Vec::new();
    for i in 0..256u32 {
        let b = n(pack.overlay_at(0, OV0_BASE, FONT_TABLE + 4 * i, 4), "font table")?;
        ptrs.push(u32::from_le_bytes([b[0], b[1], b[2], b[3]]));
    }
    let mut order: Vec<u32> = ptrs
        .iter()
        .copied()
        .filter(|p| (OV0_BASE..OV0_BASE + ov.len() as u32).contains(p))
        .collect();
    order.sort_unstable();
    order.dedup();
    let mut glyphs = Vec::new();
    for ch in 0..256usize {
        let p = ptrs[ch];
        if !(OV0_BASE..OV0_BASE + ov.len() as u32).contains(&p) {
            glyphs.push(None);
            continue;
        }
        let size = order.iter().find(|&&q| q > p).map_or(48, |&q| (q - p) as usize);
        let rb = (size / 16).clamp(1, 4);
        let Some(data) = pack.overlay_at(0, OV0_BASE, p, 16 * rb) else {
            glyphs.push(None);
            continue;
        };
        let cols = rb * 2;
        let mut px = vec![0u8; 16 * cols];
        let mut last = -1i32;
        for y in 0..16 {
            for x in 0..cols {
                let v = (data[y * rb + x / 2] >> (4 * (x & 1))) & 15;
                px[y * cols + x] = v;
                if v != 0 {
                    last = last.max(x as i32);
                }
            }
        }
        let adv = if ch == 0x20 || last < 0 { 3 } else { last + 2 };
        glyphs.push(Some(Glyph { cols, px, adv }));
    }
    // Icons.
    let sheet = n(
        pack.file("icon/res_icon0_cg_E")
            .or_else(|| pack.file("icon/res_icon0_cg")),
        "icon sheet",
    )?;
    let cl = n(pack.file("icon/res_icon_cl"), "icon colours")?;
    let mut ipal = [[0u8; 4]; 16];
    for (i, p) in ipal.iter_mut().enumerate() {
        let c = u16::from_le_bytes([*cl.get(2 * i)?, *cl.get(2 * i + 1)?]);
        *p = rgba_of(c);
    }
    let mut icons = Vec::new();
    for n in 0..sheet.len() / 128 {
        let mut px = [[0u8; 4]; 256];
        for q in 0..4usize {
            let (tx, ty) = ((q % 2) * 8, (q / 2) * 8);
            for y in 0..8 {
                for x in 0..8 {
                    let v = (sheet[(4 * n + q) * 32 + y * 4 + x / 2] >> (4 * (x & 1))) & 15;
                    if v != 0 {
                        px[(ty + y) * 16 + tx + x] = ipal[v as usize];
                    }
                }
            }
        }
        icons.push(px);
    }
    // The button sprites' sheet and colours.
    let sheet_raw = n(pack.overlay_at(0, OV0_BASE, SPRITE_SHEET, 0x800), "button sheet")?;
    let sprites = n(crate::ds_art::lz10(sheet_raw), "button sheet")?;
    let sp_pal = n(pack.arm9_at(SPRITE_PALETTE, 32), "button colours")?;
    let mut spal = [[0u8; 4]; 16];
    for (i, p) in spal.iter_mut().enumerate().skip(1) {
        *p = rgba_of(u16::from_le_bytes([sp_pal[2 * i], sp_pal[2 * i + 1]]));
    }
    let sprite_px = |t: usize, x: usize, y: usize| -> [u8; 4] {
        let b = sprites.get(32 * t + y * 4 + x / 2).copied().unwrap_or(0);
        spal[((b >> (4 * (x & 1))) & 15) as usize]
    };
    let mut corners = [[[0u8; 4]; 64]; 4];
    for (k, c) in corners.iter_mut().enumerate() {
        for i in 0..64 {
            c[i] = sprite_px(8 + 2 * k, i % 8, i / 8);
        }
    }
    let mut tag = vec![[0u8; 4]; 32 * 16];
    for (i, p) in tag.iter_mut().enumerate() {
        let (x, y) = (i % 32, i / 32);
        *p = sprite_px(56 + 4 * (y / 8) + x / 8, x % 8, y % 8);
    }
    let need = |s: &str| n(find_str(ov, s), s);
    let strings = Strings {
        co: need("View CO info.")?,
        intel: need("View Intel menu.")?,
        options: need("View Options menu.")?,
        save: need("Save progress.")?,
        end: need("End your turn.")?,
        power: need("Use a CO Power.")?,
        tag: need("Use a Tag Power.")?,
        change: need("Switch COs and end your turn.")?,
        yield_: need("Yield and concede.")?,
        rules: need("View the rules.")?,
        status: need("View battle status.")?,
    };
    Some(Art {
        frame,
        pal,
        glyphs,
        icons,
        corners,
        tag,
        strings,
    })
}

/// The selection's corner marks (TL, TR, BL, BR; 8 x 8 RGBA), for [`crate::ds_coselect`]'s cursors.
pub(crate) fn corner_marks() -> Option<[[[u8; 4]; 64]; 4]> {
    art().map(|a| a.corners)
}

fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(|| {
        let a = std::panic::catch_unwind(build_art).ok().flatten();
        if a.is_none() {
            log::warn!("ds_menus: the pack lacks the menu art; Dual Strike's menus are off");
        }
        a
    })
    .as_ref()
}

/// AW2's icon codes and the Dual Strike icons that are the same pictures
/// (the sheets agree silhouette for silhouette). Dual Strike's command label table has two "Fire" entries: the first with code
/// 0x81 (the flame, as AW2's Fire and Dual Strike's Launch and Explode have) and a second with 0x92 (crossed guns); the flame is
/// the ordinary Fire, as AW2 shows it, and what Fire takes here.
fn icon_index(page: u8, code: u8, text: &str) -> Option<usize> {
    if page == 0x0A {
        // The Drop commands show the cargo's picture, in AW2 and in Dual
        // Strike ([`cargo_picture`]).
        return None;
    }
    Some(match code {
        0x80 => 5,
        0x81 => 0,
        0x82 => 4,
        0x83 => 8,
        0x84 => 18,
        0x85 => 6,
        0x86 => 2,
        0x87 => 9,
        0x88 => 27,
        0x89 => 11,
        0x8A => 1,
        0x8B => 12,
        0x8C => 17,
        0x8D => 13,
        0x8E => 14,
        0x8F => 19,
        0x90 => 20,
        0x91 => 15,
        0x92 => 22,
        0x93 => 16,
        0x94 => 21,
        _ => return None,
    })
}

// --- Drawing ---------------------------------------------------------------------------

struct Canvas<'a> {
    rgba: &'a mut [u8],
}

impl Canvas<'_> {
    fn put(&mut self, x: i32, y: i32, c: [u8; 4]) {
        if c[3] == 0 || !(0..W as i32).contains(&x) || !(0..H as i32).contains(&y) {
            return;
        }
        let o = (y as usize * W + x as usize) * 4;
        self.rgba[o..o + 4].copy_from_slice(&[c[0], c[1], c[2], 255]);
    }
}

fn text_width(a: &Art, s: &str) -> i32 {
    s.bytes()
        .map(|b| a.glyphs[b as usize].as_ref().map_or(4, |g| g.adv))
        .sum()
}

fn draw_text(cv: &mut Canvas, a: &Art, x: i32, y: i32, s: &str, grey: bool) {
    let mut x = x;
    for b in s.bytes() {
        let Some(g) = a.glyphs[b as usize].as_ref() else {
            x += 4;
            continue;
        };
        for gy in 0..16 {
            for gx in 0..g.cols {
                let v = g.px[gy * g.cols + gx];
                if v == 0 {
                    continue;
                }
                // 10 is the ink, 14 its soft corners; a disabled command's
                // ink is 11.
                let idx = if grey && v == 10 { 11 } else { v };
                cv.put(x + gx as i32, y + gy as i32, a.pal[idx as usize]);
            }
        }
        x += g.adv;
    }
}

/// Dual Strike's frame: `w` x `h` tiles, rows alternating tile 5 and 10.
fn draw_frame(cv: &mut Canvas, a: &Art, x: i32, y: i32, w: i32, h: i32) {
    for ty in 0..h {
        for tx in 0..w {
            let t = match (ty, tx) {
                (0, 0) => 1,
                (0, t) if t == w - 1 => 3,
                (0, _) => 2,
                (r, 0) if r == h - 1 => 7,
                (r, t) if r == h - 1 && t == w - 1 => 9,
                (r, _) if r == h - 1 => 8,
                (_, 0) => 4,
                (_, t) if t == w - 1 => 6,
                (r, _) if r % 2 == 1 => 5,
                _ => 10,
            };
            let tile = &a.frame[t];
            for py in 0..8 {
                for px in 0..8 {
                    cv.put(
                        x + 8 * tx + px,
                        y + 8 * ty + py,
                        a.pal[tile[(py * 8 + px) as usize] as usize],
                    );
                }
            }
        }
    }
}

fn draw_icon(cv: &mut Canvas, a: &Art, x: i32, y: i32, n: usize) {
    let Some(icon) = a.icons.get(n) else { return };
    for i in 0..256usize {
        cv.put(x + (i % 16) as i32, y + (i / 16) as i32, icon[i]);
    }
}

/// A sprite of the button sheet (`w` x `h`, RGBA, 0 alpha transparent) at (x, y).
fn draw_sprite(cv: &mut Canvas, x: i32, y: i32, w: usize, px: &[[u8; 4]]) {
    for (i, p) in px.iter().enumerate() {
        cv.put(x + (i % w) as i32, y + (i / w) as i32, *p);
    }
}

/// The cargo's picture for a Drop row (page 0x0A: code 0x80 is the first passenger, 0x81 the
/// second; Dual Strike draws the passenger's own picture there).
fn cargo_picture(core: &Core, code: u8) -> Option<Vec<[u8; 4]>> {
    let unit = r32(core, SELECTED_UNIT);
    if !(0x0200_0000..0x0400_0000).contains(&unit) {
        return None;
    }
    let id = r8(core, unit + 7 + (code & 1) as u32);
    let pic = crate::ds_tilt::unit_picture(core, id)?;
    Some(pic.iter().map(|&p| if p == 0 { [0; 4] } else { rgba_of(p) }).collect())
}

fn description(a: &Art, text: &str) -> Option<String> {
    let s = &a.strings;
    Some(
        match text {
            "CO" => &s.co,
            "Intel" => &s.intel,
            "Options" => &s.options,
            "Save" => &s.save,
            "End" => &s.end,
            "Power" | "Super" => &s.power,
            "Tag" => &s.tag,
            "Change" => &s.change,
            "Yield" => &s.yield_,
            "Rules" => &s.rules,
            "Status" => &s.status,
            "Front" => return Some(crate::two_front::FRONT_HELP.to_string()),
            "Deploy" => return Some(crate::setup_phase::DEPLOY_HELP.to_string()),
            _ => return None,
        }
        .clone(),
    )
}

/// Whether a map menu of Dual Strike's is open, drawing the help lines
/// tangoAW2's other screens would put under it ([`crate::two_front`]).
pub fn owns_help(core: &Core) -> bool {
    ds_graphics(core) && art().is_some() && find(core).map_or(false, |(_, m)| m.kind == Kind::Map)
}

/// Whether one of Dual Strike's menus is open, with its B CANCEL tag at the top
/// centre ([`crate::survival`] keeps its header clear of it).
pub fn tag_shown(core: &Core) -> bool {
    ds_graphics(core) && art().is_some() && find(core).is_some()
}

/// The cursor's tile on the screen, in pixels (the camera is the terrain
/// layer's scroll).
fn unit_screen(core: &Core) -> (i32, i32) {
    let (tx, ty) = (r16(core, CURSOR_X) as i32, r16(core, CURSOR_Y) as i32);
    // (the tilted map shows the cell elsewhere; the middle, less the half
    // cell the flat picture's corner is from it)
    if let Some((sx, sy)) = crate::ds_tilt::cell_screen(tx, ty) {
        return (sx - 8, sy - 8);
    }
    let (hx, hy) = (r16(core, BG3_HOFS) as i32 & 0x1FF, r16(core, BG3_VOFS) as i32 & 0x1FF);
    let wrap = |v: i32| {
        let m = v.rem_euclid(512);
        if m > 256 + 16 {
            m - 512
        } else {
            m
        }
    };
    (wrap(tx * 16 - hx), wrap(ty * 16 - hy))
}

/// Draws the menu over the picture, if one of ours is open.
pub fn apply(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != W * H * 4 || !ds_graphics(core) {
        return;
    }
    let Some(a) = art() else { return };
    let Some((_, menu)) = find(core) else { return };
    // (a menu whose rows have no text yet, the frame the game builds it: nothing is drawn until they are known)
    if menu.rows.is_empty() || menu.rows.iter().all(|r| r.text.trim().is_empty()) {
        return;
    }
    let mut cv = Canvas { rgba };
    let n = menu.rows.len() as i32;
    let tw = menu.rows.iter().map(|r| text_width(a, &r.text)).max().unwrap_or(0);
    let wt = 4 + (tw + 7) / 8;
    let (bw, bh) = (8 * wt, 16 * n + 16);
    // A dialogue box (the campaign's tutorials) takes the screen's top (to row 0x2D) or its bottom (from row 112): the menu
    // stays clear of it, and Dual Strike's help box (bottom right) is left out under a bottom one.
    let talking = crate::tag_ui::dialogue_up(core);
    let top_box = talking && crate::tag_ui::top_box_rows(core) > 0;
    let (lo, hi) = (
        if top_box { 46 } else { 0 },
        if talking && !top_box { BOX_BOTTOM_TOP } else { H as i32 },
    );
    let (bx, by) = match menu.kind {
        Kind::Map => (72, within(TAG_H.max(lo), lo, hi - bh)),
        Kind::Unit => {
            let (ux, uy) = unit_screen(core);
            let x = if ux + 16 + 4 + bw <= W as i32 {
                ux + 20
            } else {
                ux - bw - 4
            };
            (
                within(x, 0, W as i32 - bw),
                within(uy + 8 - bh / 2, (TAG_H - 6).max(lo), hi - bh),
            )
        }
    };
    draw_frame(&mut cv, a, bx, by, wt, 2 * n + 2);
    for (i, row) in menu.rows.iter().enumerate() {
        let ry = by + 8 + 16 * i as i32;
        if row.page == 0x0A {
            if let Some(pic) = cargo_picture(core, row.icon) {
                draw_sprite(&mut cv, bx + 8, ry, 16, &pic);
            }
        } else if let Some(ic) = icon_index(row.page, row.icon, &row.text) {
            // (a Fire with nothing to fire at is greyed, and Dual Strike draws it with the crossed guns, checked on its artillery)
            let ic = if row.grey && row.text == "Fire" { 22 } else { ic };
            draw_icon(&mut cv, a, bx + 8, ry, ic);
        }
        draw_text(&mut cv, a, bx + 24, ry, &row.text, row.grey);
    }
    // The selection.
    let ry = by + 8 + 16 * menu.cursor as i32;
    let (x0, x1, y0, y1) = (bx + 4, bx + bw - 4, ry - 4, ry + 20);
    draw_sprite(&mut cv, x0, y0, 8, &a.corners[0]);
    draw_sprite(&mut cv, x1 - 8, y0, 8, &a.corners[1]);
    draw_sprite(&mut cv, x0, y1 - 8, 8, &a.corners[2]);
    draw_sprite(&mut cv, x1 - 8, y1 - 8, 8, &a.corners[3]);
    // The tag, top centre.
    draw_sprite(&mut cv, (W as i32 - 32) / 2, 0, 32, &a.tag);
    // The map menu's description, one line, bottom right.
    if menu.kind == Kind::Map && !(talking && !top_box) {
        if let Some(d) = description(a, &menu.rows[menu.cursor].text) {
            let dw = (8 * ((text_width(a, &d) + 16 + 7) / 8)).clamp(64, 232);
            draw_frame(&mut cv, a, W as i32 - dw, 128, dw / 8, 4);
            draw_text(&mut cv, a, W as i32 - dw + 8, 136, &d, false);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// With `TANGOAW2_DS_ROM` naming a Dual Strike (USA) ROM: the menu art
    /// builds from the pack. `cargo test -p tango-gamesupport-aw2 -- --ignored ds_menus`.
    #[test]
    #[ignore]
    fn the_art_builds() {
        let rom = std::fs::read(std::env::var_os("TANGOAW2_DS_ROM").expect("TANGOAW2_DS_ROM")).unwrap();
        assert!(crate::ds_pack::offer_rom(&rom));
        let a = build_art().expect("art");
        assert_eq!(text_width(&a, "Wait"), 20);
        assert_eq!(a.glyphs[b'I' as usize].as_ref().unwrap().adv, 2);
        assert_eq!(text_width(&a, "View CO info."), 56);
    }

    /// Writes the DS map menu's six rows (the Load row greyed) to the raw RGBA
    /// file `TANGOAW2_MENU_OUT` at (88, 16) for comparing with the real
    /// screen (the verification tool compares pixels).
    #[test]
    #[ignore]
    fn the_six_rows_picture() {
        let rom = std::fs::read(std::env::var_os("TANGOAW2_DS_ROM").expect("TANGOAW2_DS_ROM")).unwrap();
        assert!(crate::ds_pack::offer_rom(&rom));
        let a = build_art().expect("art");
        let mut buf = vec![0u8; W * H * 4];
        let mut cv = Canvas { rgba: &mut buf };
        let rows = [
            ("CO", 0x94u8, false),
            ("Intel", 0x86, false),
            ("Options", 0x88, false),
            ("Load", 0x83, true),
            ("Save", 0x87, false),
            ("End", 0x8b, false),
        ];
        draw_frame(&mut cv, &a, 88, 16, 8, 14);
        for (i, (t, code, grey)) in rows.iter().enumerate() {
            let ry = 16 + 8 + 16 * i as i32;
            draw_icon(&mut cv, &a, 96, ry, icon_index(9, *code, t).unwrap());
            draw_text(&mut cv, &a, 112, ry, t, *grey);
        }
        std::fs::write(std::env::var_os("TANGOAW2_MENU_OUT").expect("out"), &buf).unwrap();
    }
}
