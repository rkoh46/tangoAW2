//! The mission title card's long titles.
//!
//! AW2's card ("MISSION n" above the mission's name in the big font, over the world map and the seal) lays the
//! name's glyph sprites out right-aligned at x = 224 (`0x0807C278`: x = cum[i] - cum[typed] + 224, y = 24), so a
//! name wider than the screen ran off the left edge ("The Sleeping Foundry" is 243 px) and one only a little
//! narrower sat against it. AW2's own names are short; the campaigns' are not.
//!
//! A name wider than [`MAX_LINE`] (the right margin is 16 px; this keeps 8 px at the left) is set on two lines
//! instead, broken at the space that leaves the shorter longest line. Both lines stay right-aligned like the
//! one-line card and keep the typing effect (the first line types, then the second); the underline that sits
//! under the name moves down by the second line. Names that fit are untouched, so AW2's own card is byte for
//! byte what it was.

use std::sync::atomic::{AtomicI32, Ordering};
use std::sync::Mutex;

use mgba::core::Core;

/// The title font: 12-byte entries (character, glyph data, width), ended by a 0 character.
const FONT_TABLE: u32 = 0x0861_6194;
/// (The card keeps `cum[i]`, the advance of glyphs 0..i, in bytes at 0x0202FF78, so it wraps past 255 px: a name that
/// wide would lose its glyphs' places, which is why the offsets here are worked out again, in [`CUM`].)
/// The right edge the lines are aligned to, and the widest a line may be (8 px kept at the left).
pub const RIGHT: i32 = 224;
pub const MAX_LINE: i32 = 216;
/// A glyph's sprite row (y) for the first line, and the distance to the second.
pub const TITLE_Y: i32 = 24;
pub const LINE_PITCH: i32 = 30;

/// `sub_08024944`'s return (the name's text) in r0, in the card's init.
const NAME_READY: u32 = 0x0807_BAD2;
/// In the glyph loop of `0x0807C278`: r5 the glyph, r6 the typed count's address, r1 its x and r2 its y.
const GLYPH_PLACED: u32 = 0x0807_C2AE;
/// While the name types, a typed glyph is placed in `0x0807C034`'s loop (r8 its tile, 0x80 + 8 per glyph; r10 the address
/// of the frame counter, a glyph every 10 frames; r1 x, r2 y at the draw call), and the glyph being typed pops in as a
/// bigger sprite (the draw call at `GLYPH_POP`: r8 its tile, r2 its y).
const TYPED_GLYPH: u32 = 0x0807_C234;
const GLYPH_POP: u32 = 0x0807_C1CA;
/// The underline's sprites (`movs r2, #0x30 / #0x32` just before each draw call), at the typing and afterwards.
const RULE: [u32; 4] = [0x0807_C436, 0x0807_C44A, 0x0807_C538, 0x0807_C546];

/// The glyph (its index) the title breaks at (a space, shown on neither line), or -1 for one line.
static BREAK: AtomicI32 = AtomicI32::new(-1);
/// The name's glyph offsets: `CUM[i]` is the advance of glyphs 0..i (a glyph advances by its width + 1).
static CUM: Mutex<Vec<i32>> = Mutex::new(Vec::new());

/// The advances (width + 1) of the glyphs a text makes: characters the font has, as the card's loader takes them.
pub fn advances(width_of: impl Fn(u8) -> Option<u32>, text: &[u8]) -> Vec<(u8, i32)> {
    text.iter().filter_map(|&c| width_of(c).map(|w| (c, w as i32 + 1))).collect()
}

/// Where a title breaks: the glyph index of the space, or `None` for one line.
pub fn break_at(glyphs: &[(u8, i32)]) -> Option<usize> {
    let total: i32 = glyphs.iter().map(|g| g.1).sum();
    if total <= MAX_LINE {
        return None;
    }
    let mut best: Option<(i32, usize)> = None;
    let mut before = 0;
    for (j, g) in glyphs.iter().enumerate() {
        if g.0 == b' ' && j > 0 && j + 1 < glyphs.len() {
            let longest = before.max(total - before - g.1);
            if best.is_none_or(|b| longest < b.0) {
                best = Some((longest, j));
            }
        }
        before += g.1;
    }
    best.map(|b| b.1)
}

fn width_of(core: &Core, c: u8) -> Option<u32> {
    for k in 0..80 {
        let e = FONT_TABLE + 12 * k;
        let ch = core.raw_read_8(e, -1);
        if ch == 0 {
            return None;
        }
        if ch == c {
            return Some(core.raw_read_32(e + 8, -1));
        }
    }
    None
}

fn name_ready(core: &mut Core) {
    let p = core.gba().cpu().gpr(0) as u32;
    let mut text = Vec::new();
    if p >> 24 == 0x02 || p >> 24 == 0x08 {
        for k in 0..64 {
            let c = core.raw_read_8(p + k, -1);
            if c == 0 {
                break;
            }
            text.push(c);
        }
    }
    let glyphs = advances(|c| width_of(core, c), &text);
    let mut cum = vec![0];
    for g in &glyphs {
        cum.push(cum.last().unwrap() + g.1);
    }
    *CUM.lock().unwrap() = cum;
    BREAK.store(break_at(&glyphs).map_or(-1, |b| b as i32), Ordering::Relaxed);
}

/// Where glyph `i` is when `typed` glyphs have been typed: right-aligned on its line, the first line done once the
/// second begins.
fn place(i: i32, typed: i32, b: i32) -> (i32, i32) {
    let table = CUM.lock().unwrap();
    let cum = |k: i32| *table.get(k.max(0) as usize).or(table.last()).unwrap_or(&0);
    if i < b {
        (cum(i) - cum(typed.min(b)) + RIGHT, TITLE_Y)
    } else if i == b {
        (RIGHT, TITLE_Y)
    } else {
        (cum(i) - cum(typed) + RIGHT, TITLE_Y + LINE_PITCH)
    }
}

fn set_xy(core: &mut Core, (x, y): (i32, i32)) {
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(1, x);
    cpu.set_gpr(2, y);
}

/// The settled name (`0x0807C278`, glyph r5 of the count at the address in r6).
fn glyph_placed(core: &mut Core) {
    let b = BREAK.load(Ordering::Relaxed);
    if b < 0 {
        return;
    }
    let (i, typed_at) = {
        let cpu = core.gba().cpu();
        (cpu.gpr(5) as i32, cpu.gpr(6) as u32)
    };
    let typed = core.raw_read_16(typed_at, -1) as i16 as i32;
    set_xy(core, place(i, typed, b));
}

/// The glyph (its index) whose tile is in r8.
fn tile_glyph(core: &Core) -> i32 {
    (core.gba().cpu().gpr(8) as i32 - 0x80) / 8
}

fn typed_glyph(core: &mut Core) {
    let b = BREAK.load(Ordering::Relaxed);
    if b < 0 {
        return;
    }
    let counter = core.raw_read_16(core.gba().cpu().gpr(10) as u32, -1) as i16 as i32;
    let typed = counter / 10 + 1;
    let i = tile_glyph(core);
    set_xy(core, place(i, typed, b));
}

fn glyph_pop(core: &mut Core) {
    let b = BREAK.load(Ordering::Relaxed);
    if b >= 0 && tile_glyph(core) > b {
        let cpu = core.gba_mut().cpu_mut();
        let y = cpu.gpr(2);
        cpu.set_gpr(2, y + LINE_PITCH);
    }
}

fn rule(core: &mut Core) {
    if BREAK.load(Ordering::Relaxed) >= 0 {
        let cpu = core.gba_mut().cpu_mut();
        let y = cpu.gpr(2);
        cpu.set_gpr(2, y + LINE_PITCH);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![
        (NAME_READY, Box::new(name_ready)),
        (GLYPH_PLACED, Box::new(glyph_placed)),
        (TYPED_GLYPH, Box::new(typed_glyph)),
        (GLYPH_POP, Box::new(glyph_pop)),
    ];
    for a in RULE {
        t.push((a, Box::new(rule)));
    }
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    fn g(s: &str) -> Vec<(u8, i32)> {
        // (the font's widths are in the card; a fixed 12 + 1 per letter and 4 + 1 per space here)
        s.bytes().map(|c| (c, if c == b' ' { 5 } else { 13 })).collect()
    }

    #[test]
    fn short_titles_stay_on_one_line() {
        assert_eq!(break_at(&g("Echo")), None);
        assert_eq!(break_at(&g("Comet Keep")), None);
    }

    #[test]
    fn long_titles_break_at_the_space_that_balances_the_lines() {
        let t = g("Home Is Where The Black Is");
        let b = break_at(&t).unwrap();
        assert_eq!(t[b].0, b' ');
        let before: i32 = t[..b].iter().map(|x| x.1).sum();
        let after: i32 = t[b + 1..].iter().map(|x| x.1).sum();
        assert!(before <= MAX_LINE && after <= MAX_LINE, "{before} {after}");
    }
}
