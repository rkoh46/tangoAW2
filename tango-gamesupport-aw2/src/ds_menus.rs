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
//! is drawn by tangoAW2: the selection's corner marks and the B CANCEL
//! tag (Dual Strike builds them in code, no file has their pixels).
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

const W: usize = 240;
const H: usize = 160;

// --- The game's menu ---------------------------------------------------------

/// The menu procs' slot array (`CreateMenu` hands the proc out of it) and
/// the script every menu proc runs.
const SLOTS: u32 = 0x0300_1470;
const SLOT_SIZE: u32 = 0x60;
const SLOT_COUNT: u32 = 32;
const MENU_SCRIPT: u32 = 0x0848_A42C;
/// The literal-pool words naming the map menu's and the unit menu's tables
/// (they point at tangoAW2's copies while those are in use).
const MAP_MENU_POOL: u32 = 0x0802_D49C;
const UNIT_MENU_POOL: u32 = 0x0802_D59C;
const ENTRY: u32 = 0x20;
/// The text table: a pointer per text id.
const TEXT_TABLE: u32 = 0x0861_0A38;
const CURSOR_X: u32 = 0x0300_33E4;
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

fn label(core: &Core, tid: u16) -> Vec<u8> {
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
fn parse_label(bytes: &[u8]) -> (u8, u8, String) {
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
    let mut order: Vec<u32> = ptrs.iter().copied().filter(|p| (OV0_BASE..OV0_BASE + ov.len() as u32).contains(p)).collect();
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
    let sheet = n(pack.file("icon/res_icon0_cg_E").or_else(|| pack.file("icon/res_icon0_cg")), "icon sheet")?;
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
        strings,
    })
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
/// (the sheets agree silhouette for silhouette). The Fire command takes
/// Dual Strike's crossed guns, not the flame it shares a code with.
fn icon_index(page: u8, code: u8, text: &str) -> Option<usize> {
    if page == 0x0A {
        // The Drop commands show the cargo's picture in AW2; Dual Strike's
        // arrow out of the box.
        return Some(89);
    }
    if text == "Fire" {
        return Some(22);
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
        0x8A => 25,
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
    s.bytes().map(|b| a.glyphs[b as usize].as_ref().map_or(4, |g| g.adv)).sum()
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
                    cv.put(x + 8 * tx + px, y + 8 * ty + py, a.pal[tile[(py * 8 + px) as usize] as usize]);
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

/// The selection's corner marks (tangoAW2's drawing: Dual Strike builds
/// them in code): black triangles with a white inside.
const CORNER: [&str; 8] = [
    "fffffff.", "f11111ff", "f1111fff", "f111fff.", "f11fff..", "f1fff...", "ffff....", ".ff.....",
];

fn draw_corner(cv: &mut Canvas, x: i32, y: i32, flip_x: bool, flip_y: bool) {
    for (ry, row) in CORNER.iter().enumerate() {
        for (rx, ch) in row.bytes().enumerate() {
            let c = match ch {
                b'f' => [0, 0, 0, 255],
                b'1' => [255, 255, 255, 255],
                _ => continue,
            };
            let px = if flip_x { 7 - rx } else { rx } as i32;
            let py = if flip_y { 7 - ry } else { ry } as i32;
            cv.put(x + px, y + py, c);
        }
    }
}

/// The B CANCEL tag: a glass ball with a blue B over chunky white letters
/// (tangoAW2's drawing; the tag is built in code on the DS).
fn draw_cancel(cv: &mut Canvas, x: i32, y: i32) {
    const LETTERS: [(&str, [&str; 5]); 5] = [
        ("C", ["xxxx", "x...", "x...", "x...", "xxxx"]),
        ("A", [".xx.", "x..x", "xxxx", "x..x", "x..x"]),
        ("N", ["x..x", "xx.x", "xxxx", "x.xx", "x..x"]),
        ("E", ["xxxx", "x...", "xxx.", "x...", "xxxx"]),
        ("L", ["x...", "x...", "x...", "x...", "xxxx"]),
    ];
    // The letters: C A N C E L, 5 px a cell, outlined.
    let word = ['C', 'A', 'N', 'C', 'E', 'L'];
    let mut mask = vec![false; 40 * 9];
    for (k, ch) in word.iter().enumerate() {
        let g = LETTERS.iter().find(|(c, _)| c.starts_with(*ch)).unwrap().1;
        for (gy, row) in g.iter().enumerate() {
            for (gx, c) in row.bytes().enumerate() {
                if c == b'x' {
                    mask[(gy + 2) * 40 + 1 + k * 5 + gx] = true;
                }
            }
        }
    }
    let ox = x + 1;
    let oy = y + 10;
    for my in 0..9i32 {
        for mx in 0..40i32 {
            let on = mask[(my * 40 + mx) as usize];
            let near = (-1..=1).any(|dy| {
                (-1..=1).any(|dx| {
                    let (qx, qy) = (mx + dx, my + dy);
                    (0..40).contains(&qx) && (0..9).contains(&qy) && mask[(qy * 40 + qx) as usize]
                })
            });
            if on {
                cv.put(ox + mx, oy + my, [255, 255, 255, 255]);
            } else if near {
                cv.put(ox + mx, oy + my, [0, 0, 0, 255]);
            }
        }
    }
    // The ball: 12 across, a grey-green ring, a blue B.
    let (cx, cy) = (x + 8, y + 6);
    for dy in -6i32..=6 {
        for dx in -6i32..=6 {
            let d2 = dx * dx + dy * dy;
            if d2 <= 36 {
                let c = if d2 > 25 { [0, 0, 0, 255] } else if d2 > 16 { [150, 170, 160, 255] } else { [215, 225, 220, 255] };
                cv.put(cx + dx, cy + dy, c);
            }
        }
    }
    const B: [&str; 7] = ["xxx.", "x..x", "x..x", "xxx.", "x..x", "x..x", "xxx."];
    for (by, row) in B.iter().enumerate() {
        for (bx, c) in row.bytes().enumerate() {
            if c == b'x' {
                cv.put(cx - 2 + bx as i32, cy - 3 + by as i32, [50, 100, 160, 255]);
            }
        }
    }
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
    let mut cv = Canvas { rgba };
    let n = menu.rows.len() as i32;
    let tw = menu.rows.iter().map(|r| text_width(a, &r.text)).max().unwrap_or(0);
    let wt = 4 + (tw + 7) / 8;
    let (bw, bh) = (8 * wt, 16 * n + 16);
    let (bx, by) = match menu.kind {
        Kind::Map => (72, within(TAG_H, 0, H as i32 - bh)),
        Kind::Unit => {
            let (ux, uy) = unit_screen(core);
            let x = if ux + 16 + 4 + bw <= W as i32 { ux + 20 } else { ux - bw - 4 };
            (within(x, 0, W as i32 - bw), within(uy + 8 - bh / 2, TAG_H - 6, H as i32 - bh))
        }
    };
    draw_frame(&mut cv, a, bx, by, wt, 2 * n + 2);
    for (i, row) in menu.rows.iter().enumerate() {
        let ry = by + 8 + 16 * i as i32;
        if let Some(ic) = icon_index(row.page, row.icon, &row.text) {
            draw_icon(&mut cv, a, bx + 8, ry, ic);
        }
        draw_text(&mut cv, a, bx + 24, ry, &row.text, row.grey);
    }
    // The selection.
    let ry = by + 8 + 16 * menu.cursor as i32;
    let (x0, x1, y0, y1) = (bx + 4, bx + bw - 4, ry - 4, ry + 20);
    draw_corner(&mut cv, x0, y0, false, false);
    draw_corner(&mut cv, x1 - 8, y0, true, false);
    draw_corner(&mut cv, x0, y1 - 8, false, true);
    draw_corner(&mut cv, x1 - 8, y1 - 8, true, true);
    // The tag, top centre.
    draw_cancel(&mut cv, 102, 0);
    // The map menu's description, one line, bottom right.
    if menu.kind == Kind::Map {
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
        let rows = [("CO", 0x94u8, false), ("Intel", 0x86, false), ("Options", 0x88, false), ("Load", 0x83, true), ("Save", 0x87, false), ("End", 0x8b, false)];
        draw_frame(&mut cv, &a, 88, 16, 8, 14);
        for (i, (t, code, grey)) in rows.iter().enumerate() {
            let ry = 16 + 8 + 16 * i as i32;
            draw_icon(&mut cv, &a, 96, ry, icon_index(9, *code, t).unwrap());
            draw_text(&mut cv, &a, 112, ry, t, *grey);
        }
        std::fs::write(std::env::var_os("TANGOAW2_MENU_OUT").expect("out"), &buf).unwrap();
    }
}
