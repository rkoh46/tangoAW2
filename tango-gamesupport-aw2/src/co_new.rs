//! Dual Strike's nine new COs, with the Dual Strike pack: Jugger, Koal,
//! Kindle and Von Bolt (Black Hole), Grimm (Yellow Comet), Javier (Green
//! Earth), Sasha (Blue Moon), Jake and Rachel (Orange Star), as AW2 COs
//! 72..80, added after AW2's 19 (nobody is replaced).
//!
//! Why 72: AW2 names a face `co + 24 * expression` (normal, happy, sad)
//! and 19..23 are the troopers' faces, so ids up to 71 would read as
//! another CO's happy or sad face; from 72 every face id is unambiguous.
//! The six places that split a face id (`% 24`, `/ 24`) are given the
//! answer for ids from 72 ([`DECODE_SITES`]).
//!
//! Their data row is in tangoAW2's CO table ([`crate::co_roster`]); the
//! tables of pictures and texts AW2 keeps per CO (19 or 24 rows) are
//! copied with room for [`crate::co_roster::ROOM`] COs, their pool words
//! switched with the pack, and the new rows filled from the pack: the
//! pictures by [`crate::ds_co_art`], the texts (name, CO page, power names,
//! quotes) from Dual Strike's own text. The Versus Teams list gets them in
//! each army's group, and the CPU plays them with a like CO's profile.

use mgba::core::Core;
use std::sync::OnceLock;

use crate::ds_weather::is_on;

/// (Dual Strike id, the AW2 CO whose presentation, music, CPU profile and
/// place in the Teams list it takes after).
pub const NEW: [(u8, u8); 10] = [
    (12, 11), // Jugger, after Flak
    (14, 13), // Koal, after Adder
    (25, 12), // Kindle, after Lash
    (11, 10), // Von Bolt, after Sturm
    (24, 18), // Grimm, after Sensei
    (23, 17), // Javier, after Jess
    (22, 16), // Sasha, after Colin
    (20, 15), // Jake, after Hachi
    (21, 15), // Rachel, after Hachi (after Jake)
    // Clone Andy: Dual Strike has no CO record of his own. Its clones (Olaf,
    // Drake, Kanbei and Andy's) are the original's CO id with bit 7 set in
    // the mission record (Surrounded!: "(25, 0x82)", Kindle with Andy's
    // clone as her partner), drawn as the original; they play with the
    // original's data. So he takes Dual Strike's Andy (2) for everything
    // (art, powers, stats, quotes, tag compatibility) and Adder's place
    // among Black Hole's COs (music, CPU profile, Teams list). His name and
    // bio are tangoAW2's own ([`CLONE_ANDY_BIO`]).
    (2, 13),
];
pub const FIRST: u8 = 72;
/// Clone Andy: tangoAW2's tenth new CO (see `docs/AW2.md`, "Clone Andy").
pub const CLONE_ANDY: u8 = FIRST + 9;
/// Crumb: tangoAW2's eleventh new CO (see `docs/AW2.md`, "Crumb"). He has no
/// Dual Strike twin at all (no entry in [`NEW`], [`ds_id`] is `None` as for
/// AW2's Sturm): his art is derived from the Black Hole trooper's
/// ([`crate::crumb_art`]), his texts, numbers and powers are tangoAW2's own
/// ([`crate::crumb`]); Adder's place, music and CPU profile are his
/// [`like`].
pub const CRUMB: u8 = FIRST + 10;
/// The Dual Strike CO whose record fills the fields of Crumb's row nothing
/// of his own is set for (Andy's neutral numbers, as Clone Andy's).
const CRUMB_BASE: u8 = 2;
/// His name, tangoAW2's own (Dual Strike writes the clone as "Andy").
pub const CLONE_ANDY_NAME: &[u8] = b"Clone Andy";
/// His CO page's bio, **tangoAW2's own**, in AW2's terse voice (Dual Strike
/// has none for the clone): wrapped to the page like Dual Strike's.
pub const CLONE_ANDY_BIO: &[u8] = b"Black Hole's copy of Andy, made to fight for it. Cheerful, tireless and never doubts an order. Hit: Orders Miss: Giving up";

pub fn is_new(co: u8) -> bool {
    (FIRST..=CRUMB).contains(&co)
}

/// A new CO's Dual Strike id (Crumb has none).
pub fn ds_id(co: u8) -> Option<u8> {
    NEW.get((co.checked_sub(FIRST)?) as usize).map(|n| n.0)
}

/// The AW2 CO a new one takes after.
pub fn like(co: u8) -> u8 {
    match co {
        CRUMB => CRUMB_LIKE,
        _ if is_new(co) => NEW[(co - FIRST) as usize].1,
        _ => co,
    }
}

/// Adder, as Clone Andy: Black Hole's place in the Teams list, its power
/// music, a CPU profile.
const CRUMB_LIKE: u8 = 13;

/// The new COs as (CO id, the Dual Strike record its row is filled from,
/// the AW2 CO it takes after): [`NEW`]'s ten, then Crumb.
pub fn all() -> impl Iterator<Item = (u8, u8, u8)> {
    NEW.iter().enumerate().map(|(k, &(ds, like))| (FIRST + k as u8, ds, like)).chain([(CRUMB, CRUMB_BASE, CRUMB_LIKE)])
}

/// A CO of tangoAW2's own, with no Dual Strike record behind its pictures
/// and texts (Clone Andy's are Andy's but for his name, bio and pair).
pub fn is_own(co: u8) -> bool {
    co == CLONE_ANDY || co == CRUMB
}

const BLACK_HOLE_STYLE: u8 = 4;

// --- Where things are ------------------------------------------------------

const ROOM: u32 = crate::co_roster::ROOM;
const DATA: u32 = 0x0874_0000;
const PRESENTATION: u32 = DATA; // ROOM x 0x44: to +0x1980
const BODY_PAIRS: u32 = DATA + 0x2000; // ROOM x 8
const HUD: u32 = DATA + 0x3000; // ROOM x 0x100: to +0x9000
const DOSSIER: u32 = DATA + 0x9000; // ROOM x 4 u16
const BATTLE_STYLE: u32 = DATA + 0x9400; // ROOM bytes
const ORDER: u32 = DATA + 0x9500; // the Teams list's order, 0xFF-ended
const PICTURES: u32 = DATA + 0xA000; // LZ77 pictures, one after another
const STRINGS: u32 = DATA + 0x30000; // texts
const END: u32 = DATA + 0x40000;
const SENTINEL: u32 = END - 4;
const MAGIC: u32 = 0x3643_5344; // "DSC6"

const AW2_PRESENTATION: u32 = 0x084A_0090;
const PRESENTATION_ROW: u32 = 0x44;
const AW2_PRESENTATION_ROWS: u32 = 24;
const PRESENTATION_POOL: [u32; 13] = [
    0x0803_9B7C, 0x0804_3AF8, 0x0804_3B38, 0x0804_3BEC, 0x0804_3C1C, 0x0804_3E88, 0x0804_3FA4, 0x0804_3FD4,
    0x0804_45E8, 0x0804_4720, 0x0804_4B04, 0x0804_4B98, 0x0809_1384,
];
const AW2_HUD: u32 = 0x0810_2F64;
const HUD_FACE: u32 = 0x100;
const HUD_POOL: u32 = 0x0804_37EC;
const AW2_DOSSIER: u32 = 0x0861_6F0C;
const DOSSIER_POOL: u32 = 0x0808_53A0;
const AW2_BATTLE_STYLE: u32 = 0x0856_2128;
const BATTLE_STYLE_POOL: [u32; 8] =
    [0x0804_C564, 0x0804_CFE4, 0x0804_D0E8, 0x0804_DC48, 0x0804_FFD8, 0x0805_0DF4, 0x0805_0EB4, 0x0805_6B14];
const AW2_ORDER: u32 = 0x084A_077C;
const ORDER_POOL: u32 = 0x0809_1378;
/// `sub_08043CA0`'s loop over the order: `cmp r5, #0x12`.
const ORDER_BOUND: u32 = 0x0804_3CDC;
const AW2_ORDER_BOUND: u16 = 0x2D12;
/// The Teams list the game builds (16 bytes in AW2, 0x020288B0 right
/// after), moved to room tangoAW2 keeps free.
const AW2_LIST: u32 = 0x0202_88A0;
const LIST: u32 = 0x0203_FE80; // 128 bytes
const LIST_POOL: [u32; 5] = [0x0803_C12C, 0x0804_3C9C, 0x0809_0A5C, 0x0809_137C, 0x0809_1380];

const AW2_COS: u32 = crate::co_roster::AW2_COS as u32;
const ANDY: u32 = 1;

// Power presentation for the new COs: every unit sparkles, no unit
// effect, the power's +10% defence (`sub_08044534`).
const COND_ALWAYS: u32 = 0x0804_4409;
const EACH_NOTHING: u32 = 0x0804_4531;
const ON_ACTIVATE: u32 = 0x0804_4535;

// --- Text -------------------------------------------------------------------

/// Text ids: `0x08610A38 + 4 * id` is past AW2's table, in free ROM from
/// 0x0862C000 (five_map's and roster's ids are below).
const TEXT_TABLE: u32 = 0x0861_0A38;
pub const TEXT_BASE: u16 = 0x6D72;
const TEXTS_PER_CO: u16 = 16;
pub const T_NAME: u16 = 0;
pub const T_BIO: u16 = 1;
pub const T_D2D: u16 = 2;
pub const T_COP: u16 = 3;
pub const T_SCOP: u16 = 4;
pub const T_COP_NAME: u16 = 5;
pub const T_SCOP_NAME: u16 = 6;
pub const T_QUOTES: u16 = 7; // six
pub const T_VICTORY: u16 = 13;
/// A defeat quote (AW2's results screen has none; Crumb's is kept here).
pub const T_DEFEAT: u16 = 14;

pub fn text_id(co: u8, which: u16) -> u16 {
    TEXT_BASE + TEXTS_PER_CO * (co - FIRST) as u16 + which
}

const DS_OVERLAY_BASE: u32 = 0x022A_D560;
const DS_TEXT_GROUPS: u32 = DS_OVERLAY_BASE + 0x49690;

/// A Dual Strike text by its reference (group << 24 | index), as AW2
/// text: its line breaks and pauses are AW2's, other characters kept
/// to plain ASCII.
fn ds_text(r: u32) -> Option<Vec<u8>> {
    if r >> 24 == 0 {
        return None;
    }
    let pack = crate::ds_pack::pack()?;
    let ov = |a: u32, n: usize| pack.overlay_at(0, DS_OVERLAY_BASE, a, n);
    let mut p = DS_TEXT_GROUPS;
    let group = loop {
        let e = ov(p, 8)?;
        let (key, ptr) = (u32::from_le_bytes(e[0..4].try_into().ok()?), u32::from_le_bytes(e[4..8].try_into().ok()?));
        if key == u32::MAX {
            return None;
        }
        if key >> 24 == r >> 24 {
            break ptr;
        }
        p += 8;
    };
    let at = u32::from_le_bytes(ov(group + 4 * (r & 0xFF_FFFF), 4)?.try_into().ok()?);
    let mut out = Vec::new();
    for k in 0..0x400 {
        let c = ov(at + k, 1)?[0];
        match c {
            0 => break,
            0x0D | 0x0E | 0x20..=0x7E => out.push(c),
            0xE0..=0xE5 => out.push(b'a'),
            0xE8..=0xEB => out.push(b'e'),
            _ => {}
        }
    }
    Some(out)
}

/// A text of Clone Andy's that is tangoAW2's own, not Dual Strike's.
fn clone_text(which: u16, _name: &[u8]) -> Option<Vec<u8>> {
    match which {
        T_NAME => Some(CLONE_ANDY_NAME.to_vec()),
        T_BIO => Some(CLONE_ANDY_BIO.to_vec()),
        _ => None,
    }
}

fn record_ref(ds: u8, off: u32) -> u32 {
    crate::ds_pack::pack()
        .and_then(|p| p.arm9_at(0x0215_360C + 0x220 * ds as u32 + off, 4))
        .map(|b| u32::from_le_bytes(b.try_into().unwrap()))
        .unwrap_or(0)
}

/// AW2's CO page: 6 lines of at most 103 pixels (its own widest), in its
/// font (`sub_08014D38`: `widths[c]` a character, and 1 between two).
const PAGE_PIXELS: u32 = 103;
const PAGE_LINES: usize = 6;
pub const FONT_WIDTHS: u32 = 0x084C_36E4;

fn pixels(line: &str, widths: &[u8]) -> u32 {
    line.bytes().map(|c| widths[c as usize] as u32).sum::<u32>() + line.len().saturating_sub(1) as u32
}

fn wrap_to(paragraphs: &[String], widths: &[u8]) -> Vec<String> {
    wrap_pixels(paragraphs, widths, PAGE_PIXELS)
}

fn wrap_pixels(paragraphs: &[String], widths: &[u8], limit: u32) -> Vec<String> {
    let mut lines: Vec<String> = Vec::new();
    for p in paragraphs.iter().filter(|p| !p.is_empty()) {
        let mut line = String::new();
        for word in p.split(' ') {
            let longer = if line.is_empty() { word.to_string() } else { format!("{line} {word}") };
            if !line.is_empty() && pixels(&longer, widths) > limit {
                lines.push(std::mem::replace(&mut line, word.to_string()));
            } else {
                line = longer;
            }
        }
        lines.push(line);
    }
    lines
}

/// The results screen's quote box (`sub_0807A860`: its text printed from
/// tile column 16, so 104 pixels to the screen's edge; AW2's text does not
/// wrap there, a longer line runs on into the next row at the screen's left)
/// holds at most this many lines, as AW2's own victory quotes.
pub const QUOTE_PIXELS: u32 = 104;
pub const QUOTE_LINES: usize = 3;

/// A quote as plain words in single spaces (breaks and pauses dropped).
pub fn quote_text(t: &[u8]) -> String {
    let flat: String = t.iter().filter(|&&c| c == b'\r' || (0x20..0x7F).contains(&c)).map(|&c| if c == b'\r' { ' ' } else { c as char }).collect();
    flat.split(' ').filter(|w| !w.is_empty()).collect::<Vec<_>>().join(" ")
}

/// Plain words broken into lines of at most [`QUOTE_PIXELS`].
pub fn quote_lines(text: &str, widths: &[u8]) -> Vec<String> {
    wrap_pixels(&[text.to_string()], widths, QUOTE_PIXELS)
}

/// A quote for that box: Dual Strike's line breaks and pauses dropped, the
/// words broken into lines of at most [`QUOTE_PIXELS`]; if that takes more
/// than [`QUOTE_LINES`], the last sentences go.
pub fn wrap_quote(t: &[u8], widths: &[u8]) -> Vec<u8> {
    let mut text = quote_text(t);
    loop {
        let lines = quote_lines(&text, widths);
        if lines.len() <= QUOTE_LINES {
            return lines.join("\r").into_bytes();
        }
        let body = text.trim_end_matches(['.', '!', '?']);
        match body.rfind(['.', '!', '?']) {
            Some(i) => text.truncate(i + 1),
            None => return lines[..QUOTE_LINES].join("\r").into_bytes(),
        }
    }
}

/// Shorter wordings, tried in turn while a page is too long.
const SHORTER: [(&str, &str); 7] = [
    ("Adept at making quick decisions, he stores up energy", "He stores up energy"),
    (" at a faster rate than", " faster than"),
    (" is greatly increased", " rises greatly"),
    (" is increased", " rises"),
    (" are increased", " rise"),
    ("Damaged units must skip their next turn.", "Units hit skip a turn."),
    (" HP of damage", " HP damage"),
];

/// A CO page text wrapped to AW2's page: Dual Strike's line breaks are
/// dropped but for the ones before "Hit(s):" and "Miss:". If it is still
/// too long, a few wordings are shortened ([`SHORTER`]); then (a bio) the
/// last sentences of its first paragraph go, and Hit and Miss share a line.
pub fn wrap_page(t: &[u8], widths: &[u8]) -> Vec<u8> {
    let text = String::from_utf8_lossy(t).replace('\r', " ");
    let mut paragraphs: Vec<String> = vec![String::new()];
    for word in text.split(' ').filter(|w| !w.is_empty()) {
        if word.starts_with("Hit") || word.starts_with("Miss:") {
            paragraphs.push(String::new());
        }
        let p = paragraphs.last_mut().unwrap();
        if !p.is_empty() {
            p.push(' ');
        }
        p.push_str(word);
    }
    let mut lines = wrap_to(&paragraphs, widths);
    for (long, short) in SHORTER {
        if lines.len() <= PAGE_LINES {
            break;
        }
        for p in paragraphs.iter_mut() {
            *p = p.replace(long, short);
        }
        lines = wrap_to(&paragraphs, widths);
    }
    while lines.len() > PAGE_LINES && paragraphs.len() > 1 {
        let body = &paragraphs[0];
        let cut = body.trim_end_matches(['.', '!', '?']).rfind(['.', '!', '?']);
        match cut {
            Some(i) => {
                let kept = body[..=i].to_string();
                paragraphs[0] = kept;
                lines = wrap_to(&paragraphs, widths);
            }
            None => break,
        }
    }
    let n = paragraphs.len();
    if lines.len() > PAGE_LINES && n >= 2 && paragraphs[n - 2].starts_with("Hit") {
        let both = format!("{} {}", paragraphs[n - 2], paragraphs[n - 1]);
        if pixels(&both, widths) <= PAGE_PIXELS {
            let mut merged = paragraphs[..n - 2].to_vec();
            merged.push(both);
            lines = wrap_to(&merged, widths);
        }
    }
    lines.join("\r").into_bytes()
}

/// A CO's name as Dual Strike writes it (AW2's ids and the new COs), from
/// the pack.
pub fn ds_name(co: u8) -> Option<Vec<u8>> {
    if co == CLONE_ANDY {
        return Some(CLONE_ANDY_NAME.to_vec());
    }
    if co == CRUMB {
        return Some(crate::crumb::NAME.to_vec());
    }
    ds_text(record_ref(crate::co_roster::ds_co(co)?, 0x00)).filter(|t| !t.is_empty())
}

/// A new CO's texts, by [`text_id`] slot.
fn texts(co: u8, ds: u8, widths: &[u8]) -> Vec<(u16, Vec<u8>)> {
    let mut out = Vec::new();
    let clone = co == CLONE_ANDY;
    let crumb = co == CRUMB;
    let name = if clone {
        CLONE_ANDY_NAME.to_vec()
    } else if crumb {
        crate::crumb::NAME.to_vec()
    } else {
        ds_text(record_ref(ds, 0x00)).unwrap_or_default()
    };
    // Every slot gets a text: one the game reads but Dual Strike leaves
    // empty (Von Bolt has no CO Power) would otherwise point at nothing.
    let mut put = |which: u16, off: u32| {
        let own = if clone {
            clone_text(which, &name)
        } else if crumb {
            crate::crumb::text(which)
        } else {
            None
        };
        let t = own.or_else(|| ds_text(record_ref(ds, off))).filter(|t| !t.is_empty()).unwrap_or_else(|| {
            if which == T_COP {
                // As AW2 says of Sturm, who has none either.
                let n = String::from_utf8_lossy(&name);
                format!("{n} has no CO Power. He saves all his energy for his Super CO Power.").into_bytes()
            } else {
                Vec::new()
            }
        });
        let page = [T_BIO, T_D2D, T_COP, T_SCOP].contains(&which);
        out.push((
            which,
            if page {
                wrap_page(&t, widths)
            } else if which == T_VICTORY {
                wrap_quote(&t, widths)
            } else {
                t
            },
        ));
    };
    put(T_NAME, 0x00);
    put(T_BIO, 0x04);
    put(T_D2D, 0x08);
    put(T_COP, 0x0C);
    put(T_SCOP, 0x10);
    put(T_COP_NAME, 0x120);
    put(T_SCOP_NAME, 0x1A0);
    for q in 0..6 {
        put(T_QUOTES + q, 0x3C + 4 * q as u32);
    }
    put(T_VICTORY, 0x28);
    if crumb {
        put(T_DEFEAT, 0x28);
    }
    out
}

// --- Building ------------------------------------------------------------------

struct Built {
    /// (address, bytes) to write once.
    writes: Vec<(u32, Vec<u8>)>,
    order_len: u8,
}

fn read(core: &Core, at: u32, n: u32) -> Vec<u8> {
    let mut b = vec![0u8; n as usize];
    core.raw_read_range(at, -1, &mut b);
    b
}

/// A table of `rows` of `size` from AW2's (`aw2_rows` of them), the rest
/// copies of Andy's.
fn grown(core: &Core, at: u32, size: u32, aw2_rows: u32) -> Vec<u8> {
    let mut t = read(core, at, size * aw2_rows);
    let andy = read(core, at + size * ANDY, size);
    for _ in aw2_rows..ROOM {
        t.extend_from_slice(&andy);
    }
    t
}

/// AW2's power effect table (`sub_08043A80` / `sub_08043A90`): per entry
/// the pictures (LZ77) and the palette of the effect on each unit.
const AW2_POWER_EFFECTS: u32 = 0x084A_06F0;
const AW2_POWER_EFFECT_COUNT: u32 = 8;
/// Dual Strike's (arm9): per entry three file names, the pictures for the
/// 3D engine, for OBJ tiles, and the palette (`0x020D5C44`).
const DS_POWER_EFFECTS: u32 = 0x0216_8850;
const DS_POWER_EFFECT_COUNT: u32 = 9;

/// The power effect Dual Strike gives a new CO's CO Power (`power` 0) or
/// Super CO Power (1): its CO block's +0x30, the effect's pictures and
/// its palette, each an entry of Dual Strike's table. AW2's table holds
/// the same pictures and palettes (Dual Strike kept them and added one),
/// so each is found there by its data: (AW2's picture entry, AW2's
/// palette entry), as AW2's presentation row +0x1C takes them.
fn power_effect(core: &Core, ds: u8, power: u32) -> Option<(u8, u8)> {
    let pack = crate::ds_pack::pack()?;
    let block = pack.arm9_at(0x0215_360C + 0x220 * ds as u32 + 0x120 + 0x80 * power + 0x30, 2)?;
    let (anim, pal) = (block[0] as u32, block[1] as u32);
    if anim >= DS_POWER_EFFECT_COUNT || pal >= DS_POWER_EFFECT_COUNT {
        return None;
    }
    let name = |i: u32, k: u32| -> Option<String> {
        let at = u32::from_le_bytes(pack.arm9_at(DS_POWER_EFFECTS + 12 * i + 4 * k, 4)?.try_into().ok()?);
        let b = pack.arm9_at(at, 4)?;
        let s: Vec<u8> = b.iter().copied().take_while(|&c| c != 0).collect();
        Some(format!("bmap/{}", String::from_utf8(s).ok()?))
    };
    let pictures = crate::ds_art::lz10(pack.file(&name(anim, 1)?)?)?;
    let palette = pack.file(&name(pal, 2)?)?.get(..32)?.to_vec();
    let entry = |k: u32| (core.raw_read_32(AW2_POWER_EFFECTS + 8 * k, -1), core.raw_read_32(AW2_POWER_EFFECTS + 8 * k + 4, -1));
    let rom = |at: u32, n: usize| {
        let mut b = vec![0u8; n];
        core.raw_read_range(at, -1, &mut b);
        b
    };
    let a = (0..AW2_POWER_EFFECT_COUNT).find(|&k| {
        let (g, _) = entry(k);
        crate::ds_art::lz10(&rom(g, 0x2000)).is_some_and(|d| d == pictures)
    })?;
    let p = (0..AW2_POWER_EFFECT_COUNT).find(|&k| rom(entry(k).1, 32) == palette)?;
    Some((a as u8, p as u8))
}

// --- Clone Andy's name graphic ---------------------------------------------------

/// A name graphic (the CO presentation row's +4: six 8x16 sprites in a row,
/// tile 2k the top of column k, 2k + 1 its bottom, 4 bits a pixel) as 48 x 16
/// palette indexes; and back.
fn name_pixels(tiles: &[u8]) -> Option<[[u8; 48]; 16]> {
    if tiles.len() < 384 {
        return None;
    }
    let mut px = [[0u8; 48]; 16];
    for col in 0..6 {
        for half in 0..2 {
            let t = &tiles[32 * (2 * col + half)..][..32];
            for y in 0..8 {
                for x in 0..8 {
                    px[8 * half + y][8 * col + x] = t[4 * y + x / 2] >> (4 * (x & 1)) & 15;
                }
            }
        }
    }
    Some(px)
}

fn name_tiles(px: &[[u8; 48]; 16]) -> Vec<u8> {
    let mut out = vec![0u8; 384];
    for col in 0..6 {
        for half in 0..2 {
            for y in 0..8 {
                for x in (0..8).step_by(2) {
                    let (a, b) = (px[8 * half + y][8 * col + x], px[8 * half + y][8 * col + x + 1]);
                    out[32 * (2 * col + half) + 4 * y + x / 2] = a | b << 4;
                }
            }
        }
    }
    out
}

/// The letters of a name graphic: the columns of each letter's fill (palette
/// index 1), (first, last); a letter's outline is the column either side,
/// shared with its neighbour.
fn letters(px: &[[u8; 48]; 16]) -> Vec<(usize, usize)> {
    let fill: Vec<bool> = (0..48).map(|x| (0..16).any(|y| px[y][x] == 1)).collect();
    let mut out = Vec::new();
    let mut start = None;
    for x in 0..=48 {
        let on = x < 48 && fill[x];
        match (on, start) {
            (true, None) => start = Some(x),
            (false, Some(s)) => {
                out.push((s, x - 1));
                start = None;
            }
            _ => {}
        }
    }
    out
}

/// "Clone" in the style of the game's name graphics, from AW2's own letters
/// (**tangoAW2's own composition**, no new art): C, o, l and n of "Colin"
/// (AW2's CO 16), e of "Eagle" (8), set side by side as they are in a name:
/// each letter's outline column shared with the next (where two letters'
/// outlines differ in height, the taller shows), centred in the six sprites.
fn clone_name(core: &Core) -> Option<Vec<u8>> {
    let name_of = |co: u32| -> Option<[[u8; 48]; 16]> {
        let row = read(core, AW2_PRESENTATION + PRESENTATION_ROW * co, 8);
        let at = u32::from_le_bytes(row[4..8].try_into().ok()?);
        let raw = read(core, at, 0x300);
        name_pixels(&crate::ds_art::lz10(&raw)?)
    };
    let colin = name_of(16)?;
    let eagle = name_of(8)?;
    let (lc, le) = (letters(&colin), letters(&eagle));
    // Colin: C o l i n; Eagle: E a g l e.
    if lc.len() != 5 || le.len() != 5 {
        return None;
    }
    let pick = [(&colin, lc[0]), (&colin, lc[2]), (&colin, lc[1]), (&colin, lc[4]), (&eagle, le[4])];
    // The glyph columns left to right: the first letter's left outline, then
    // each letter's fill and its right outline (merged with the next
    // letter's left outline, the taller showing).
    let mut cols: Vec<[u8; 16]> = Vec::new();
    let column = |img: &[[u8; 48]; 16], x: usize| -> [u8; 16] {
        let mut c = [0u8; 16];
        for y in 0..16 {
            c[y] = img[y][x];
        }
        c
    };
    cols.push(column(pick[0].0, pick[0].1 .0 - 1));
    for (k, &(img, (s, e))) in pick.iter().enumerate() {
        for x in s..=e {
            cols.push(column(img, x));
        }
        let mut sep = column(img, e + 1);
        if let Some(&(next, (ns, _))) = pick.get(k + 1) {
            let other = column(next, ns - 1);
            for y in 0..16 {
                if sep[y] == 0 {
                    sep[y] = other[y];
                }
            }
        }
        cols.push(sep);
    }
    if cols.len() > 48 {
        return None;
    }
    let mut out = [[0u8; 48]; 16];
    let x0 = (48 - cols.len()) / 2;
    for (i, c) in cols.iter().enumerate() {
        for y in 0..16 {
            out[y][x0 + i] = c[y];
        }
    }
    Some(name_tiles(&out))
}

fn put32(t: &mut [u8], o: usize, v: u32) {
    t[o..o + 4].copy_from_slice(&v.to_le_bytes());
}

fn build(core: &Core) -> Option<Built> {
    let mut writes = Vec::new();
    let mut pres = grown(core, AW2_PRESENTATION, PRESENTATION_ROW, AW2_PRESENTATION_ROWS);
    let mut hud = grown(core, AW2_HUD, HUD_FACE, AW2_COS);
    let mut dossier = grown(core, AW2_DOSSIER, 8, AW2_COS);
    let mut style = grown(core, AW2_BATTLE_STYLE, 1, AW2_COS);
    let widths = read(core, FONT_WIDTHS, 256);
    let mut pictures: Vec<u8> = Vec::new();
    let mut picture = |data: &[u8], compress: bool| -> u32 {
        let at = PICTURES + pictures.len() as u32;
        if compress {
            pictures.extend_from_slice(&crate::lz77::compress(data));
        } else {
            pictures.extend_from_slice(data);
        }
        while pictures.len() % 4 != 0 {
            pictures.push(0);
        }
        at
    };
    crate::co_powers::presentation_changes(&mut pres);
    let mut pairs = vec![0u8; (8 * ROOM) as usize];
    let mut strings: Vec<u8> = Vec::new();
    let mut slots: Vec<(u32, u32)> = Vec::new();
    for (co, ds, like) in all() {
        let mut art = if co == CRUMB { crate::crumb_art::art(core)? } else { crate::ds_co_art::co_art(ds)? };
        if co == CLONE_ANDY {
            // His name graphic reads "Clone", cut from AW2's own letters.
            if let Some(n) = clone_name(core) {
                art.name = n;
            }
        }
        let row = PRESENTATION_ROW as usize * co as usize;
        let template = PRESENTATION_ROW as usize * like as usize;
        let t = pres[template..template + PRESENTATION_ROW as usize].to_vec();
        pres[row..row + PRESENTATION_ROW as usize].copy_from_slice(&t);
        let top = picture(&art.body_top, true);
        let bottom = picture(&art.body_bottom, true);
        put32(&mut pairs, 8 * co as usize, top);
        put32(&mut pairs, 8 * co as usize + 4, bottom);
        put32(&mut pres, row, BODY_PAIRS + 8 * co as u32);
        put32(&mut pres, row + 0x04, picture(&art.name, true));
        put32(&mut pres, row + 0x08, picture(&art.palette, false));
        for (f, face) in art.face.iter().enumerate() {
            put32(&mut pres, row + 0x0C + 4 * f, picture(face, true));
        }
        put32(&mut pres, row + 0x18, picture(&art.mini, false));
        for p in 0..2 {
            let o = row + 0x1C + 0x14 * p;
            put32(&mut pres, o + 4, COND_ALWAYS);
            put32(&mut pres, o + 8, EACH_NOTHING);
            put32(&mut pres, o + 12, ON_ACTIVATE);
            if co == CRUMB {
                // His powers' sparkle is Andy's (AW2's repair effect), the
                // unit effect his own ([`crate::crumb::each_unit`]).
                let andy = PRESENTATION_ROW as usize * ANDY as usize + 0x1C + 0x14 * p;
                let (anim, pal) = (pres[andy], pres[andy + 1]);
                pres[o] = anim;
                pres[o + 1] = pal;
                put32(&mut pres, o + 8, crate::crumb::each_unit(p as u8));
            } else if let Some((anim, pal)) = power_effect(core, ds, p as u32) {
                pres[o] = anim;
                pres[o + 1] = pal;
            }
        }
        let h = HUD_FACE as usize * co as usize;
        hud[h..h + HUD_FACE as usize].copy_from_slice(&art.hud[..HUD_FACE as usize]);
        for (i, page) in [T_BIO, T_D2D, T_COP, T_SCOP].iter().enumerate() {
            let o = 8 * co as usize + 2 * i;
            dossier[o..o + 2].copy_from_slice(&text_id(co, *page).to_le_bytes());
        }
        let ds_style = crate::ds_pack::pack()?.arm9_at(0x0215_360C + 0x220 * ds as u32 + 0x25, 1)?[0];
        // (Clone Andy and Crumb fight in Black Hole's style)
        style[co as usize] = if is_own(co) { BLACK_HOLE_STYLE } else { ds_style.min(BLACK_HOLE_STYLE) };
        for (which, text) in texts(co, ds, &widths) {
            let at = STRINGS + strings.len() as u32;
            strings.extend_from_slice(&text);
            strings.push(0);
            slots.push((TEXT_TABLE + 4 * text_id(co, which) as u32, at));
        }
    }
    if PICTURES + pictures.len() as u32 > STRINGS || STRINGS + strings.len() as u32 > SENTINEL {
        return None;
    }
    // The Teams list's order: AW2's, each new CO after the one it takes
    // after (in NEW's order).
    let mut order = read(core, AW2_ORDER, AW2_COS);
    for (co, _, like) in all() {
        let mut at = order.iter().position(|&c| c == like).map(|p| p + 1).unwrap_or(order.len());
        while at < order.len() && is_new(order[at]) {
            at += 1;
        }
        order.insert(at, co);
    }
    let order_len = order.len() as u8;
    order.push(0xFF);
    writes.push((PRESENTATION, pres));
    writes.push((BODY_PAIRS, pairs));
    writes.push((HUD, hud));
    writes.push((DOSSIER, dossier));
    writes.push((BATTLE_STYLE, style));
    writes.push((ORDER, order));
    writes.push((PICTURES, pictures));
    writes.push((STRINGS, strings));
    for (at, p) in slots {
        writes.push((at, p.to_le_bytes().to_vec()));
    }
    Some(Built { writes, order_len })
}

static BUILT: OnceLock<Option<Built>> = OnceLock::new();

fn install(core: &mut Core) -> Option<&'static Built> {
    let built = BUILT.get_or_init(|| build(core)).as_ref()?;
    if core.raw_read_32(SENTINEL, -1) != MAGIC {
        for (at, b) in &built.writes {
            core.raw_write_range(*at, -1, b);
        }
        core.raw_write_32(SENTINEL, -1, MAGIC);
    }
    Some(built)
}

fn switch32(core: &mut Core, at: u32, want: u32) {
    if core.raw_read_32(at, -1) != want {
        core.raw_write_32(at, -1, want);
    }
}

/// Every frame: the game reads the grown tables with the pack on, AW2's
/// without (idempotent; the same on both netplay peers).
pub fn tick(core: &mut Core, on: bool) {
    let built = if on { install(core) } else { None };
    let on = built.is_some();
    if !on && core.raw_read_32(SENTINEL, -1) != MAGIC {
        return;
    }
    let pick = |ds: u32, aw2: u32| if on { ds } else { aw2 };
    for at in PRESENTATION_POOL {
        switch32(core, at, pick(PRESENTATION, AW2_PRESENTATION));
    }
    switch32(core, HUD_POOL, pick(HUD, AW2_HUD));
    switch32(core, DOSSIER_POOL, pick(DOSSIER, AW2_DOSSIER));
    for at in BATTLE_STYLE_POOL {
        switch32(core, at, pick(BATTLE_STYLE, AW2_BATTLE_STYLE));
    }
    switch32(core, ORDER_POOL, pick(ORDER, AW2_ORDER));
    for at in LIST_POOL {
        switch32(core, at, pick(LIST, AW2_LIST));
    }
    let bound = match built {
        Some(b) => 0x2D00 | (b.order_len as u16 - 1),
        None => AW2_ORDER_BOUND,
    };
    if core.raw_read_16(ORDER_BOUND, -1) != bound {
        core.raw_write_16(ORDER_BOUND, -1, bound);
    }
}

// --- Traps ------------------------------------------------------------------------

/// Where a face id is split (`movs r1, #0x18` then `bl` the divide or the
/// modulo): for ids from 72 the answer is given and the call skipped.
/// (site, true for the quotient)
const DECODE_SITES: [(u32, bool); 6] = [
    (0x0804_3AA4, false),
    (0x0804_3AC6, false),
    (0x0804_3ACE, false),
    (0x0804_3E4C, true),
    (0x0804_3E58, false),
    (0x0804_3F6A, false),
];

fn decode(core: &mut Core, quotient: bool) {
    if !is_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (a, pc) = (cpu.gpr(0) as u32, cpu.thumb_pc());
    if a < FIRST as u32 {
        return;
    }
    let v = if quotient { (a - FIRST as u32) / 24 } else { FIRST as u32 + (a - FIRST as u32) % 24 };
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, v as i32);
    cpu.set_thumb_pc(pc + 6);
}

/// `GetLoadedCoPalette(co)` / `SetLoadedCoPalette(co, v)`: the chosen
/// colours, a byte per CO for 24: the new COs keep their first.
const GET_PALETTE: u32 = 0x0801_7860;
const SET_PALETTE: u32 = 0x0801_7870;
fn palette(core: &mut Core, get: bool) {
    if !is_on(core) || core.gba().cpu().gpr(0) < FIRST as i32 {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    let lr = cpu.gpr(14) as u32;
    if get {
        cpu.set_gpr(0, 0);
    }
    cpu.set_thumb_pc(lr & !1);
}

/// `sub_0803CAB8(co)`: whether a CO is unlocked (save bits for 24): the
/// new COs are.
const UNLOCKED: u32 = 0x0803_CAB8;
fn unlocked(core: &mut Core) {
    if is_on(core) && is_new(core.gba().cpu().gpr(0) as u8) {
        let cpu = core.gba_mut().cpu_mut();
        let lr = cpu.gpr(14) as u32;
        cpu.set_gpr(0, 1);
        cpu.set_thumb_pc(lr & !1);
    }
}

/// `sub_08044BA0(co)`: Black Hole's power music, for COs 10..14 in AW2.
const BLACK_HOLE_MUSIC: u32 = 0x0804_4BA0;
fn black_hole_music(core: &mut Core) {
    let co = core.gba().cpu().gpr(0) as u8;
    if is_on(core) && is_new(co) && (10..=14).contains(&like(co)) {
        let cpu = core.gba_mut().cpu_mut();
        let lr = cpu.gpr(14) as u32;
        cpu.set_gpr(0, 1);
        cpu.set_thumb_pc(lr & !1);
    }
}

/// The CPU's profile table is 19 COs wide (`row * 19 + co`): where the CO
/// is added in, a new CO reads as the one it takes after. (site, register)
const AI_PROFILE_SITES: [(u32, usize); 3] = [(0x0806_17C4, 2), (0x0806_1830, 2), (0x0806_1962, 4)];
fn ai_profile(core: &mut Core, reg: usize) {
    if !is_on(core) {
        return;
    }
    let co = core.gba().cpu().gpr(reg) as u8;
    if is_new(co) {
        core.gba_mut().cpu_mut().set_gpr(reg, like(co) as i32);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = Vec::new();
    for (at, q) in DECODE_SITES {
        t.push((at, Box::new(move |core: &mut Core| decode(core, q))));
    }
    t.push((GET_PALETTE, Box::new(|core: &mut Core| palette(core, true))));
    t.push((SET_PALETTE, Box::new(|core: &mut Core| palette(core, false))));
    t.push((UNLOCKED, Box::new(unlocked)));
    t.push((BLACK_HOLE_MUSIC, Box::new(black_hole_music)));
    for (at, reg) in AI_PROFILE_SITES {
        t.push((at, Box::new(move |core: &mut Core| ai_profile(core, reg))));
    }
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn page_wrap() {
        let widths = [4u8; 256];
        let t = wrap_page(b"A Green Earth CO who values chivalry and honor above all else. Often\rcommands his units to charge. Hit: Honor Miss: Retreating", &widths);
        let t = String::from_utf8(t).unwrap();
        assert!(t.split('\r').all(|l| pixels(l, &widths) <= PAGE_PIXELS), "{t}");
        assert!(t.split('\r').count() <= PAGE_LINES, "{t}");
        assert!(t.ends_with("Miss: Retreating"), "{t}");
    }

    #[test]
    fn ids_and_room() {
        assert_eq!(ds_id(72), Some(12));
        assert_eq!(ds_id(80), Some(21));
        assert_eq!(ds_id(81), Some(2), "Clone Andy takes Dual Strike's Andy");
        assert_eq!(ds_id(82), None);
        assert_eq!(CLONE_ANDY, 81);
        assert!((FIRST as u32 + NEW.len() as u32 + 1) <= ROOM);
        assert_eq!(CRUMB, 82);
        assert_eq!(ds_id(CRUMB), None, "Crumb has no Dual Strike twin");
        assert_eq!(like(CRUMB), 13);
        assert!(is_new(CRUMB) && !is_new(CRUMB + 1));
        assert!(TEXT_TABLE + 4 * text_id(CRUMB, TEXTS_PER_CO) as u32 <= 0x0863_0000);
        assert!(HUD + HUD_FACE * ROOM <= DOSSIER && PRESENTATION + PRESENTATION_ROW * ROOM <= BODY_PAIRS);
    }
}

#[cfg(test)]
mod pack_tests {
    use super::*;

    /// Every new CO's CO page texts fit AW2's page (needs `TANGOAW2_DS_ROM`).
    #[test]
    #[ignore]
    fn pages_fit() {
        for (co, ds, _) in all() {
            let widths = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").unwrap()).unwrap()
                [(FONT_WIDTHS - 0x0800_0000) as usize..][..256]
                .to_vec();
            for (which, t) in texts(co, ds, &widths) {
                if [T_BIO, T_D2D, T_COP, T_SCOP].contains(&which) {
                    let t = String::from_utf8(t).unwrap();
                    println!("{ds} {which}: {}", t.replace('\r', " | "));
                    assert!(t.split('\r').count() <= PAGE_LINES, "{ds} {which}");
                }
            }
        }
    }
}
