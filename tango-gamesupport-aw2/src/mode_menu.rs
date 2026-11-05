//! Two extra entries on the Select Mode wheel, with the Dual Strike pack, offline:
//! Survival ([`crate::survival`]) and Gauntlet ([`crate::gauntlet`]).
//!
//! The wheel (`ProcScr_MainMenu`, the `MainMenuCarousel*` procs, names from
//! the aw2bhr decompilation) turns six tiles: a table of six item ids
//! (`0x0861696C`: War Room 5, Battle Maps 2, Link 4, Design Room 3, Versus 1,
//! Campaign 0, read at `(position + 2) % 6`), each item with a big label
//! (the centre tile), a small one (the sides), a palette and a highlight
//! palette, and a help line per position. With the pack, offline, it turns
//! seven:
//!
//! - **Positions.** Every `DivRem(x, 6)` of the wheel's code (`movs r1, #6`
//!   before `bl DivRem` (`0x0808AAB0`) in `0x08080F00..0x08084C00`, found
//!   by scanning the ROM) becomes `DivRem(x, 8)`, the position's wrap at 5
//!   becomes 7 (the input loop `0x08081DF0`/`0x08081E2C`, the rotation
//!   `0x0808280C`/`0x08082830`, `SetMainMenuCarouselPosition` `0x08080F7E`),
//!   and the 34 words pointing at the item table point at an eight-entry
//!   copy (`[5, 8, 2, 4, 3, 1, 9, 0]`, read at `(position + 2) % 8`). The
//!   wheel turns by position and the screen lists positions from the top
//!   down, highest first: Battle Maps 0, Online 1, Design Room 2, Versus 3 keep
//!   theirs, **Gauntlet is position 4 (directly above Versus)**, then Campaign
//!   5, War Room 6 and Survival 7 (they were 4, 5 and 6 with Survival alone).
//! - **Items 8 and 9.** Their labels and palettes are tangoAW2's: traps at
//!   `LoadMainMenuCentreTileGraphic` (`0x080845A8`, the big label into OBJ
//!   VRAM `0x06013300`), `GetMainMenuTilePalette` (`0x08084864`),
//!   `GetMainMenuTileHighlightPalette` (`0x0808488C`) and
//!   `IsMainMenuTileComplete` (`0x08084858`, never complete). The game draws an
//!   item's side tile at `0x1D8 + 32 * item` with palette `item + 2`, so at the
//!   sprite flush ([`remap`]) those of items 8 and 9 are pointed at ours: each
//!   [`Extra`] has its own small label tiles and OBJ palette. Free on this
//!   screen (an OBJ survey of the wheel, all its item boxes, Survival and Gauntlet:
//!   `tests/test_gauntlet_mode.py`, `gauntlet_wheel_obj_resources_are_free`): OBJ
//!   palette 13 (Survival's) and 14 (Gauntlet's: unused by the game and by the
//!   Campaign chooser, 8 and 10..12); OBJ tiles 0x320..0x33F (Survival's small
//!   label) and 0x2E0..0x2FF (Gauntlet's).
//! - **Picking them.** Items 8 and 9 behave like Battle Maps and Link (A starts
//!   the mode, no Continue/New): traps at the three `cmp r0, #4` that send an
//!   item there (`0x08081498` in `MainMenuCarouselWheel_Init`, `0x08081E94`
//!   and `0x08081EEE` in its input loop) answer 4 for them, and the
//!   mode store (`0x08081EF6`) stores the entry's mode and tells the entry it
//!   was picked: Survival's is the War Room's New (5); Gauntlet's is Campaign's
//!   New (1) with a request for the Gauntlet's source ([`crate::gauntlet`]).
//! - **Help line.** `MainMenuCarousel_DrawDescriptionText` (`0x08084600`)
//!   indexes a table by position with 6 and 7 for the Sound Room and Hard
//!   Campaign lines: the table (`0x08616FA4`) is copied reordered to the new
//!   positions with the entries' lines at 4 and 7, those two become 8 and 9,
//!   and its Hard Campaign test (table index 0, Campaign) becomes index 7; the
//!   open item's choices' lines (`0x08616FB4`, two per line index) are copied
//!   likewise.
//!
//! Everything is switched every frame from the pack's state (the ROM image
//! is put back without it), so the wheel is AW2's own with the pack off.
//! Further entries need an OBJ palette and small-label tiles each (see
//! docs/dev/gauntlet-mode.md, "Adding a wheel entry") and wraps for the new count.

use mgba::core::Core;
use std::sync::OnceLock;

/// The items' ids (0..5 are the game's, 6 and 7 are the Sound Room's and
/// Hard Campaign's label graphics).
pub const ITEM: u8 = 8;
pub const GAUNTLET: u8 = 9;
/// The wheel's positions, by table index (the game reads `table[(position +
/// 2) % 8]`): War Room, Survival, Battle Maps, Link, Design Room, Versus,
/// Gauntlet, Campaign.
const TABLE: [u8; 8] = [5, ITEM, 2, 4, 3, 1, GAUNTLET, 0];
/// The entries on the wheel with the pack.
const N: usize = 8;

const GAME_TABLE: u32 = 0x0861_696C;
const HELP_TABLE: u32 = 0x0861_6FA4;
const HELP_POOL: u32 = 0x0808_4680;
/// The open item's two choices' lines, two per position (the same 6 and 7
/// for the Sound Room and Hard Campaign).
const OPTIONS_TABLE: u32 = 0x0861_6FB4;
const OPTIONS_POOL: u32 = 0x0808_46C0;
const DIV_REM: u32 = 0x0808_AAB0;
const WHEEL_CODE: (u32, u32) = (0x0808_0F00, 0x0808_4C00);

/// tangoAW2's wheel data in the ROM image's free space (0x08E40000..0x08E41FFF).
pub(crate) const DATA: u32 = 0x08E4_0000;
const DATA_TABLE: u32 = DATA;
const DATA_HELP: u32 = DATA + 0x10;
const DATA_OPTIONS: u32 = DATA + 0x80;
/// Each extra entry's data: Survival's (palette, highlight, big label 2 KiB, small label 1 KiB).
const SURVIVAL_AT: u32 = DATA + 0x40;
const GAUNTLET_AT: u32 = DATA + 0x1000;
pub(crate) const SENTINEL: u32 = DATA + 0x1FFC;
const MAGIC: u32 = 0x554E_454E; // "NEMU"

/// One extra entry of the wheel.
struct Extra {
    item: u8,
    /// Its data: palette (32 bytes), highlight (32), the big label (2 KiB at +0xC0), the small one (1 KiB at +0x8C0).
    at: u32,
    /// Its OBJ palette and the first OBJ tile of its small label on the Select Mode screen.
    palette: u32,
    tile: u32,
}

impl Extra {
    fn pal(&self) -> u32 {
        self.at
    }
    fn highlight(&self) -> u32 {
        self.at + 0x20
    }
    fn big(&self) -> u32 {
        self.at + 0xC0
    }
    fn small(&self) -> u32 {
        self.at + 0x8C0
    }
    /// The game's side tile for the item, and its palette.
    fn game_tile(&self) -> u32 {
        0x1D8 + 32 * self.item as u32
    }
    fn game_palette(&self) -> u32 {
        self.item as u32 + 2
    }
}

/// Survival: teal; the small label in OBJ tiles 0x320.., palette 13. Gauntlet: orange, tiles 0x2E0.., palette 14.
const EXTRAS: [Extra; 2] = [
    Extra {
        item: ITEM,
        at: SURVIVAL_AT,
        palette: 13,
        tile: 0x320,
    },
    Extra {
        item: GAUNTLET,
        at: GAUNTLET_AT,
        palette: 14,
        tile: 0x2E0,
    },
];

fn extra(item: u32) -> Option<&'static Extra> {
    EXTRAS.iter().find(|e| e.item as u32 == item)
}

/// The wheel's proc (`ProcScr_MainMenuC1`), running while Select Mode is up.
const MAIN_MENU: u32 = 0x0861_6990;
const PROCS: u32 = 0x0200_D610;
const PROCS_END: u32 = 0x0200_E418;
const PROC_SIZE: u32 = 0x6C;

const OBJ_VRAM: u32 = 0x0601_0000;
const CENTRE_VRAM: u32 = 0x0601_3300;
const CENTRE_TILES: (u32, u32) = (0x198, 0x1D8);
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;

/// (address, original, patched) halfwords besides the DivRem sites.
const HALVES: [(u32, u16, u16); 9] = [
    (0x0808_0F68, 0x1D08, 0x1D88), // SetMainMenuCarouselPosition: (i + 4) % 6 -> (i + 6) % 8
    (0x0808_1DF0, 0x2805, 0x2807), // UP: position 5 -> 0 becomes 7 -> 0
    (0x0808_1E2C, 0x2005, 0x2007), // DOWN: 0 -> 5 becomes 0 -> 7
    (0x0808_280C, 0x2805, 0x2807), // the rotation's own wraps
    (0x0808_2830, 0x2005, 0x2007),
    (0x0808_0F7E, 0x2905, 0x2907), // SetMainMenuCarouselPosition: i <= 7
    (0x0808_4630, 0x2506, 0x2508), // help: Sound Room line 6 -> 8
    (0x0808_464E, 0x2507, 0x2509), // help: Hard Campaign line 7 -> 9
    (0x0808_464A, 0x2800, 0x2807), // help: Campaign is table index 7
];

struct Built {
    divrem_sites: Vec<u32>,
    table_pools: Vec<u32>,
}

static BUILT: OnceLock<Built> = OnceLock::new();

fn scan(core: &Core) -> Built {
    let (lo, hi) = WHEEL_CODE;
    let mut code = vec![0u8; (hi - lo) as usize];
    core.raw_read_range(lo, -1, &mut code);
    let h = |o: usize| u16::from_le_bytes([code[o], code[o + 1]]);
    let mut divrem_sites = Vec::new();
    for o in (0..code.len() - 6).step_by(2) {
        if h(o) != 0x2106 {
            continue;
        }
        let (hi16, lo16) = (h(o + 2), h(o + 4));
        if hi16 >> 11 != 0x1E || lo16 >> 11 != 0x1F {
            continue;
        }
        let mut off = (((hi16 & 0x7FF) as i32) << 12) | (((lo16 & 0x7FF) as i32) << 1);
        if off & 0x40_0000 != 0 {
            off -= 0x80_0000;
        }
        let pc = lo + o as u32 + 2 + 4;
        if pc.wrapping_add(off as u32) == DIV_REM {
            divrem_sites.push(lo + o as u32);
        }
    }
    // Every word pointing at the item table, in the wheel's code and its
    // read-only data (0x081D938C..).
    let mut table_pools = Vec::new();
    for (from, to) in [(lo, hi), (0x081D_9300, 0x081D_9400)] {
        let mut b = vec![0u8; (to - from) as usize];
        core.raw_read_range(from, -1, &mut b);
        for o in (0..b.len()).step_by(4) {
            if u32::from_le_bytes(b[o..o + 4].try_into().unwrap()) == GAME_TABLE {
                table_pools.push(from + o as u32);
            }
        }
    }
    Built {
        divrem_sites,
        table_pools,
    }
}

// --- The label art -----------------------------------------------------------

/// The game's labels: (big, small) LZ77 per item.
const LABELS: u32 = 0x0861_6AC0;
/// Item palettes: 16 colours per item, the highlight ones from item 6.
const PALETTES: u32 = 0x0823_DC38;

fn label(core: &Core, item: u32, which: u32) -> Option<Vec<u8>> {
    let at = core.raw_read_32(LABELS + 8 * item + 4 * which, -1);
    let mut b = vec![0u8; 0x1000];
    core.raw_read_range(at, -1, &mut b);
    crate::ds_art::lz10(&b)
}

/// A label as pixels (128 wide), from tiles laid out as sprites `sw` tiles
/// wide, left to right.
fn to_pixels(data: &[u8], h_tiles: usize, sw: usize) -> Vec<Vec<u8>> {
    let mut px = vec![vec![0u8; 128]; 8 * h_tiles];
    let mut t = 0;
    for s in 0..16 / sw {
        for ty in 0..h_tiles {
            for tx in 0..sw {
                for y in 0..8 {
                    for x in 0..8 {
                        let b = data[32 * t + 4 * y + x / 2];
                        px[8 * ty + y][8 * (s * sw + tx) + x] = (b >> (4 * (x & 1))) & 15;
                    }
                }
                t += 1;
            }
        }
    }
    px
}

fn to_tiles(px: &[Vec<u8>], h_tiles: usize, sw: usize) -> Vec<u8> {
    let mut out = vec![0u8; 16 * h_tiles * 32];
    let mut t = 0;
    for s in 0..16 / sw {
        for ty in 0..h_tiles {
            for tx in 0..sw {
                for y in 0..8 {
                    for x in 0..8 {
                        let v = px[8 * ty + y][8 * (s * sw + tx) + x] & 15;
                        out[32 * t + 4 * y + x / 2] |= v << (4 * (x & 1));
                    }
                }
                t += 1;
            }
        }
    }
    out
}

/// "SURVIVAL": the letters of the game's own labels (item, first and last
/// column), on Campaign's plate. Letter colours (5..12) follow the
/// 16-pixel column bands every big label has.
const SURVIVAL_LETTERS: [(u32, usize, usize); 8] = [
    (3, 27, 37),  // S of DESIGN ROOM
    (1, 84, 101), // U of VERSUS
    (3, 75, 85),  // R of DESIGN ROOM
    (1, 6, 24),   // V of VERSUS
    (3, 39, 45),  // I of DESIGN ROOM
    (1, 6, 24),   // V
    (2, 87, 99),  // A of BATTLEMAPS
    (2, 51, 60),  // L of BATTLEMAPS
];

/// "GAUNTLET".
const GAUNTLET_LETTERS: [(u32, usize, usize); 8] = [
    (3, 47, 58),  // G of DESIGN ROOM
    (2, 87, 99),  // A of BATTLEMAPS
    (1, 84, 101), // U of VERSUS
    (3, 60, 71),  // N of DESIGN ROOM
    (2, 39, 49),  // T of BATTLEMAPS
    (2, 51, 60),  // L of BATTLEMAPS
    (2, 62, 70),  // E of BATTLEMAPS
    (2, 39, 49),  // T
];

fn big(core: &Core, letters: &[(u32, usize, usize)]) -> Option<Vec<u8>> {
    let src: Vec<Vec<Vec<u8>>> = (0..4)
        .map(|i| label(core, i, 0).map(|d| to_pixels(&d, 4, 8)))
        .collect::<Option<_>>()?;
    let mut out = src[0].clone();
    for row in out.iter_mut().take(22).skip(2) {
        for v in row.iter_mut().take(124).skip(4) {
            *v = 1;
        }
    }
    let total: usize = letters.iter().map(|&(_, a, b)| b - a + 1).sum::<usize>() + letters.len() - 1;
    let mut x = 4 + (120 - total) / 2;
    for &(item, a, b) in letters {
        for sx in a..=b {
            for y in 2..22 {
                let mut v = src[item as usize][y][sx];
                if (5..=12).contains(&v) {
                    v = (5 + x / 16).min(12) as u8;
                }
                out[y][x] = v;
            }
            x += 1;
        }
        x += 1;
    }
    Some(to_tiles(&out, 4, 8))
}

/// A small label's letter cells: column runs between all-dark columns
/// inside its dark box (rows 4..10).
fn cells(px: &[Vec<u8>]) -> Vec<(usize, usize)> {
    let rows = 4..11;
    let dark = |x: usize| rows.clone().all(|y| px[y][x] == 1);
    let light = |x: usize| rows.clone().all(|y| px[y][x] == 5);
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

/// The small labels' pixels by item (Campaign 0, Versus 1, Battle Maps 2, Link 4) and their letter cells, which must be the counts the letters below were picked from.
fn small_sources(core: &Core) -> Option<Vec<(Vec<Vec<u8>>, Vec<(usize, usize)>)>> {
    let mut out = Vec::new();
    for (item, count) in [(0u32, 8usize), (1, 6), (2, 9), (4, 4)] {
        let px = to_pixels(&label(core, item, 1)?, 2, 4);
        let c = cells(&px);
        if c.len() != count {
            return None;
        }
        out.push((px, c));
    }
    Some(out)
}

/// A small label from letters: (source index in [`small_sources`], the letter's cell index).
fn small(core: &Core, letters: &[(usize, usize)]) -> Option<Vec<u8>> {
    let src = small_sources(core)?;
    let mut out = src[0].0.clone();
    for row in out.iter_mut().take(11).skip(4) {
        for v in row.iter_mut().take(124).skip(4) {
            *v = 5;
        }
    }
    let widths: Vec<(usize, usize)> = letters.iter().map(|&(s, c)| src[s].1[c]).collect();
    let total: usize = widths.iter().map(|(a, b)| b - a + 1).sum::<usize>() + widths.len() + 1;
    let mut x = 4 + (120 - total) / 2;
    let dark_col = |out: &mut Vec<Vec<u8>>, x: usize| {
        for row in out.iter_mut().take(11).skip(4) {
            row[x] = 1;
        }
    };
    dark_col(&mut out, x);
    x += 1;
    for (&(s, _), (a, b)) in letters.iter().zip(widths) {
        for sx in a..=b {
            for y in 4..11 {
                out[y][x] = src[s].0[y][sx];
            }
            x += 1;
        }
        dark_col(&mut out, x);
        x += 1;
    }
    Some(to_tiles(&out, 2, 4))
}

/// S U R V I V A L (Campaign 0, Versus 1, Battle Maps 2, Link 3 of the sources).
const SURVIVAL_SMALL: [(usize, usize); 8] = [(1, 3), (1, 4), (1, 2), (1, 0), (0, 5), (1, 0), (0, 1), (3, 0)];
/// G A U N T L E T: G and N of CAMPAIGN, A of CAMPAIGN, U of VERSUS, T L E of BATTLE MAPS.
const GAUNTLET_SMALL: [(usize, usize); 8] = [(0, 6), (0, 1), (1, 4), (0, 7), (2, 2), (2, 3), (2, 4), (2, 2)];

/// A palette: each colour, channel by channel, `f(a, b)` of two items' palettes (`first` is the index of the palette table's entries: items, or 6 + item for the highlights).
fn palette(core: &Core, a: u32, b: u32, f: fn(usize, u16, u16) -> u16) -> [u8; 32] {
    let mut out = [0u8; 32];
    for i in 0..16 {
        let ca = core.raw_read_16(PALETTES + 32 * a + 2 * i, -1);
        let cb = core.raw_read_16(PALETTES + 32 * b + 2 * i, -1);
        let mut c = 0u16;
        for ch in 0..3 {
            let va = (ca >> (5 * ch)) & 31;
            let vb = (cb >> (5 * ch)) & 31;
            c |= f(ch, va, vb) << (5 * ch);
        }
        out[2 * i as usize..2 * i as usize + 2].copy_from_slice(&c.to_le_bytes());
    }
    out
}

/// Teal, from Campaign's blue and Link's green: the lesser red, the greater green and blue.
fn teal(ch: usize, a: u16, b: u16) -> u16 {
    if ch == 0 {
        a.min(b)
    } else {
        a.max(b)
    }
}

/// Orange, from Versus' red and Battle Maps' gold: the mean of the two.
fn orange(_ch: usize, a: u16, b: u16) -> u16 {
    (a + b) / 2
}

fn installed(core: &Core) -> bool {
    core.raw_read_32(SENTINEL, -1) == MAGIC
}

/// The Gauntlet's help line: a text id of Survival's block (its spare slot), whose string and table word are written with the rest of the wheel's data.
pub const GAUNTLET_HELP: &str = "Beat a map's COs one after another.";
const GAUNTLET_HELP_ID: u16 = crate::survival::TEXT_BASE + 4;
/// The Gauntlet's box (a run saved halfway: Continue / New) lines, shown under the box as AW2's "Continue a campaign in progress." / "Start a new campaign." are (Survival's text slots 41 and 42: its
/// block ends at 40, Dual Strike Versus' ids start far above).
pub const GAUNTLET_CONTINUE: &str = "Continue your saved Gauntlet run.";
pub const GAUNTLET_NEW: &str = "Start a new run. The saved run is dropped.";
const GAUNTLET_CONTINUE_K: u16 = 41;
const GAUNTLET_NEW_K: u16 = 42;

fn install(core: &mut Core, help_text: u16) -> bool {
    BUILT.get_or_init(|| scan(core));
    if installed(core) {
        return true;
    }
    let (Some(sbig), Some(ssmall), Some(gbig), Some(gsmall)) = (
        big(core, &SURVIVAL_LETTERS),
        small(core, &SURVIVAL_SMALL),
        big(core, &GAUNTLET_LETTERS),
        small(core, &GAUNTLET_SMALL),
    ) else {
        return false;
    };
    core.raw_write_range(DATA_TABLE, -1, &TABLE);
    // Help lines by position: the game's positions 0..3 (Battle Maps, Link, Design Room, Versus), Gauntlet's, the game's 4 and 5 (Campaign,
    // War Room), Survival's, then the Sound Room's and Hard Campaign's.
    let game = |core: &Core, i: u32| core.raw_read_16(HELP_TABLE + 2 * i, -1);
    let mut help = Vec::new();
    for i in 0..4 {
        help.push(game(core, i));
    }
    help.push(GAUNTLET_HELP_ID);
    help.push(game(core, 4));
    help.push(game(core, 5));
    help.push(help_text);
    help.push(game(core, 6));
    help.push(game(core, 7));
    for (i, h) in help.iter().enumerate() {
        core.raw_write_16(DATA_HELP + 2 * i as u32, -1, *h);
    }
    // Choices' lines (two a position), the same order: none for ours.
    let opt = |core: &Core, i: u32| core.raw_read_16(OPTIONS_TABLE + 2 * i, -1);
    let mut options = Vec::new();
    for i in 0..8 {
        options.push(opt(core, i));
    }
    // (Gauntlet's, at position 4: Continue, New)
    options.extend([crate::survival::TEXT_BASE + GAUNTLET_CONTINUE_K, crate::survival::TEXT_BASE + GAUNTLET_NEW_K]);
    for i in 8..12 {
        options.push(opt(core, i));
    }
    options.extend([0, 0]);
    for i in 12..16 {
        options.push(opt(core, i));
    }
    for (i, h) in options.iter().enumerate() {
        core.raw_write_16(DATA_OPTIONS + 2 * i as u32, -1, *h);
    }
    // Survival's teal and Gauntlet's orange.
    for (e, big, small, pal, hi) in [
        (&EXTRAS[0], &sbig, &ssmall, palette(core, 0, 4, teal), palette(core, 6, 10, teal)),
        (&EXTRAS[1], &gbig, &gsmall, palette(core, 1, 2, orange), palette(core, 7, 8, orange)),
    ] {
        core.raw_write_range(e.pal(), -1, &pal);
        core.raw_write_range(e.highlight(), -1, &hi);
        core.raw_write_range(e.big(), -1, big);
        core.raw_write_range(e.small(), -1, small);
    }
    // The Gauntlet's help string and its text-table word.
    let at = crate::survival::string_at(4);
    let mut s = GAUNTLET_HELP.as_bytes().to_vec();
    s.push(0);
    core.raw_write_range(at, -1, &s);
    core.raw_write_32(crate::survival::text_slot(4), -1, at);
    for (k, text) in [(GAUNTLET_CONTINUE_K, GAUNTLET_CONTINUE), (GAUNTLET_NEW_K, GAUNTLET_NEW)] {
        let at = crate::survival::string_at(k);
        let mut s = text.as_bytes().to_vec();
        s.push(0);
        core.raw_write_range(at, -1, &s);
        core.raw_write_32(crate::survival::text_slot(k), -1, at);
    }
    core.raw_write_32(SENTINEL, -1, MAGIC);
    true
}

/// The item at a wheel position (the game reads `table[(position + 2) %
/// n]`, n = 6, or 8 with the extra entries).
pub fn item(core: &Core, position: u32) -> u8 {
    if active(core) {
        TABLE[(position as usize + 2) % N]
    } else {
        core.raw_read_8(GAME_TABLE + (position + 2) % 6, -1)
    }
}

/// The wheel's position of an item (None: not on this wheel).
pub fn position_of(core: &Core, item_id: u8) -> Option<u32> {
    let n = if active(core) { N as u32 } else { 6 };
    (0..n).find(|&p| item(core, p) == item_id)
}

/// Whether the wheel has eight entries now (the patches are in).
pub fn active(core: &Core) -> bool {
    BUILT.get().is_some_and(|b| {
        b.table_pools
            .first()
            .is_some_and(|&p| core.raw_read_32(p, -1) == DATA_TABLE)
    })
}

fn running(core: &Core) -> bool {
    (PROCS..PROCS_END)
        .step_by(PROC_SIZE as usize)
        .any(|p| core.raw_read_32(p, -1) == MAIN_MENU)
}

/// Every frame: the wheel gets the entries with the pack on (offline), and
/// is the game's own otherwise.
pub fn tick(core: &mut Core, on: bool, help_text: u16) {
    let on = on && install(core, help_text);
    let Some(built) = BUILT.get() else { return };
    if !on && !installed(core) {
        return;
    }
    let w16 = |core: &mut Core, at: u32, v: u16| {
        if core.raw_read_16(at, -1) != v {
            core.raw_write_16(at, -1, v);
        }
    };
    let w32 = |core: &mut Core, at: u32, v: u32| {
        if core.raw_read_32(at, -1) != v {
            core.raw_write_32(at, -1, v);
        }
    };
    for &at in &built.divrem_sites {
        w16(core, at, if on { 0x2100 + N as u16 } else { 0x2106 });
    }
    for &(at, old, new) in &HALVES {
        let now = core.raw_read_16(at, -1);
        if now == old || now == new {
            w16(core, at, if on { new } else { old });
        }
    }
    for &at in &built.table_pools {
        w32(core, at, if on { DATA_TABLE } else { GAME_TABLE });
    }
    w32(core, HELP_POOL, if on { DATA_HELP } else { HELP_TABLE });
    w32(core, OPTIONS_POOL, if on { DATA_OPTIONS } else { OPTIONS_TABLE });
    if on && running(core) {
        for e in &EXTRAS {
            // The small label and its palette (the game never loads these items').
            let mut small = vec![0u8; 1024];
            core.raw_read_range(e.small(), -1, &mut small);
            let at = OBJ_VRAM + 32 * e.tile;
            let mut now = vec![0u8; 1024];
            core.raw_read_range(at, -1, &mut now);
            if now != small {
                core.raw_write_range(at, -1, &small);
            }
            let mut pal = [0u8; 32];
            core.raw_read_range(e.pal(), -1, &mut pal);
            for base in [PAL_BUFFER, PAL_RAM] {
                let mut now = [0u8; 32];
                core.raw_read_range(base + 0x200 + 32 * e.palette, -1, &mut now);
                if now != pal {
                    core.raw_write_range(base + 0x200 + 32 * e.palette, -1, &pal);
                }
            }
        }
    }
}

/// At the sprite flush ([`crate::branding::flush`]): the extra items' side
/// tiles and their tile on its way to the centre use our tiles and palette.
pub fn remap(core: &mut Core, start: u32, end: u32) {
    if !active(core) || !running(core) {
        return;
    }
    let mut at = start;
    while at + 8 <= end {
        let a2 = core.raw_read_16(at + 4, -1) as u32;
        let (tile, pal) = (a2 & 0x3FF, a2 >> 12);
        if let Some(e) = EXTRAS.iter().find(|e| e.game_palette() == pal) {
            let game = e.game_tile();
            let new = if (game..game + 32).contains(&tile) {
                Some(tile - game + e.tile)
            } else if (CENTRE_TILES.0..CENTRE_TILES.1).contains(&tile) {
                Some(tile)
            } else {
                None
            };
            if let Some(t) = new {
                core.raw_write_16(at + 4, -1, ((e.palette << 12) | (a2 & 0x0C00) | t) as u16);
            }
        }
        at += 8;
    }
    // The Gauntlet's box rows are drawn as the War Room's (OBJ palette 7 for the row that is not under the cursor): in the Gauntlet's own colour.
    if matches!(crate::campaign_menu::wheel_info(core), Some((_, GAUNTLET, true))) {
        let e = &EXTRAS[1];
        let mut at = start;
        while at + 8 <= end {
            let a2 = core.raw_read_16(at + 4, -1) as u32;
            let (tile, pal) = (a2 & 0x3FF, a2 >> 12);
            if pal == WAR_ROOM_PALETTE && (BOX_LABEL_TILES.0..BOX_LABEL_TILES.1).contains(&tile) {
                core.raw_write_16(at + 4, -1, ((e.palette << 12) | (a2 & 0x0FFF)) as u16);
            }
            at += 8;
        }
    }
}

/// The War Room's OBJ palette (item 5 + 2) and the box labels' OBJ tiles (CONTINUE at 664.., NEW at 676..).
const WAR_ROOM_PALETTE: u32 = 7;
const BOX_LABEL_TILES: (u32, u32) = (664, 696);

// --- Traps -----------------------------------------------------------------------

fn ret(core: &mut Core, r0: u32) {
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, r0 as i32);
    let lr = cpu.gpr(14) as u32;
    cpu.set_thumb_pc(lr & !1);
}

fn r0(core: &Core) -> u32 {
    core.gba().cpu().gpr(0) as u32
}

/// The extra entry the trapped function's r0 names (the wheel has the entries on).
fn named(core: &Core) -> Option<&'static Extra> {
    if active(core) {
        extra(r0(core))
    } else {
        None
    }
}

/// The extra item the trapped function's r0 names when it starts its mode at once (A, no box): Survival always; the Gauntlet unless a run is saved (then its box offers Continue and New, [`box_commit`]).
fn direct(core: &Core) -> Option<&'static Extra> {
    named(core).filter(|e| e.item != GAUNTLET || !crate::gauntlet::saved(core))
}

const CENTRE_GRAPHIC: u32 = 0x0808_45A8;
fn centre_graphic(core: &mut Core) {
    if let Some(e) = named(core) {
        let mut big = vec![0u8; 2048];
        core.raw_read_range(e.big(), -1, &mut big);
        core.raw_write_range(CENTRE_VRAM, -1, &big);
        ret(core, 0);
    }
}

const TILE_COMPLETE: u32 = 0x0808_4858;
fn tile_complete(core: &mut Core) {
    if named(core).is_some() {
        ret(core, 0);
    }
}

const TILE_PALETTE: u32 = 0x0808_4864;
fn tile_palette(core: &mut Core) {
    if let Some(e) = named(core) {
        ret(core, e.pal());
    }
}

const TILE_HIGHLIGHT: u32 = 0x0808_488C;
fn tile_highlight(core: &mut Core) {
    if let Some(e) = named(core) {
        ret(core, e.highlight());
    }
}

/// `cmp r0, #4` with the item in r0: the extra items answer as Link.
const LIKE_LINK: [u32; 2] = [0x0808_1498, 0x0808_1E94];
fn like_link(core: &mut Core) {
    if direct(core).is_some() {
        core.gba_mut().cpu_mut().set_gpr(0, 4);
    }
}

/// The last `cmp r0, #4` before the mode is stored: an extra item is picked.
const PICKED: u32 = 0x0808_1EEE;
fn picked(core: &mut Core) {
    if let Some(e) = direct(core) {
        core.gba_mut().cpu_mut().set_gpr(0, 4);
        if e.item == GAUNTLET {
            crate::gauntlet::picked(core, false);
        } else {
            core.raw_write_8(crate::survival::MENU_PICKED, -1, 1);
        }
    }
}

/// `str r0, [r1]`: the mode (`0x030033FC`) Link would start; Survival's is the
/// War Room's New (5), [`crate::survival`] taking over from there; the Gauntlet's
/// is Campaign's New (1), [`crate::gauntlet`] taking over.
const MODE_STORE: u32 = 0x0808_1EF6;
const WAR_ROOM_NEW: u32 = 5;
const CAMPAIGN_NEW: u32 = 1;
fn mode_store(core: &mut Core) {
    if !active(core) {
        return;
    }
    if crate::gauntlet::is_picked(core) {
        core.gba_mut().cpu_mut().set_gpr(0, CAMPAIGN_NEW as i32);
    } else if core.raw_read_8(crate::survival::MENU_PICKED, -1) != 0 {
        core.gba_mut().cpu_mut().set_gpr(0, WAR_ROOM_NEW as i32);
    }
}

/// The open box's A, as its choice is committed for an item the game has no case for (`ldr r1, [pc, #..]` after the item chain: the Campaign's, Versus', Design Room's and War Room's cases store
/// their mode and branch past it): the Gauntlet's box (Continue the top row, New the bottom) stores Campaign's New, with the request for its source ([`crate::gauntlet::picked`]).
const BOX_COMMIT: u32 = 0x0808_2352;
fn box_commit(core: &mut Core) {
    if !active(core) {
        return;
    }
    let Some((_, item, true)) = crate::campaign_menu::wheel_info(core) else { return };
    let Some(cursor) = crate::campaign_menu::box_cursor(core) else { return };
    if item == GAUNTLET {
        crate::gauntlet::picked(core, cursor % 2 == 0);
        core.raw_write_32(MODE, -1, CAMPAIGN_NEW);
    }
}

/// The game mode word.
const MODE: u32 = 0x0300_33FC;

/// The box's rows are drawn each frame by a chain on the item (`cmp r0, #0`, `#1`, `#5`, `#3`: Campaign's, Versus', War Room's rows, which are the CONTINUE and NEW labels at OBJ tile 664, and Design Room's):
/// at the `cmp r0, #5` the Gauntlet is the War Room (its labels, in the palettes of its two rows), whose Continue is dimmed by `GetWarRoomSaveFlag`, answered true for the Gauntlet's box (it only
/// opens over a saved run).
const DRAW_IS_WAR_ROOM: u32 = 0x0808_3C50;
fn draw_like_war_room(core: &mut Core) {
    if active(core) && r0(core) == GAUNTLET as u32 {
        core.gba_mut().cpu_mut().set_gpr(0, 5);
    }
}

const WAR_ROOM_SAVE_FLAG: u32 = 0x0803_BC94;
fn war_room_save_flag(core: &mut Core) {
    if active(core) && matches!(crate::campaign_menu::wheel_info(core), Some((_, GAUNTLET, true))) {
        ret(core, 1);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (BOX_COMMIT, Box::new(box_commit)),
        (DRAW_IS_WAR_ROOM, Box::new(draw_like_war_room)),
        (WAR_ROOM_SAVE_FLAG, Box::new(war_room_save_flag)),
        (CENTRE_GRAPHIC, Box::new(centre_graphic)),
        (TILE_COMPLETE, Box::new(tile_complete)),
        (TILE_PALETTE, Box::new(tile_palette)),
        (TILE_HIGHLIGHT, Box::new(tile_highlight)),
        (LIKE_LINK[0], Box::new(like_link)),
        (LIKE_LINK[1], Box::new(like_link)),
        (PICKED, Box::new(picked)),
        (MODE_STORE, Box::new(mode_store)),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_gauntlets_box_lines_have_text_slots_of_their_own() {
        // Survival's block: help at 0, kinds 1..3, spare 4 (the Gauntlet's help), maps 5..37, champions 38..40; the box's two lines follow, in the 0x40-byte string slots below the wheel's data.
        assert!(GAUNTLET_CONTINUE_K > 40 && GAUNTLET_NEW_K == GAUNTLET_CONTINUE_K + 1);
        assert!(crate::survival::TEXT_BASE + GAUNTLET_NEW_K < crate::ds_versus::TEXT_BASE);
        for t in [GAUNTLET_CONTINUE, GAUNTLET_NEW, GAUNTLET_HELP] {
            assert!(t.len() < 0x40, "{t} fits its string slot");
        }
        assert!(crate::survival::string_at(GAUNTLET_NEW_K) + 0x40 <= DATA);
    }

    #[test]
    fn table_keeps_every_position_but_the_three_after_versus() {
        // (position + 2) % 8 in the new table gives what (position + 2) % 6 gave in the game's for Battle Maps, Link, Design Room and Versus (positions 0..3);
        // Gauntlet is 4 (directly above Versus on the screen), then Campaign, War Room and Survival.
        const GAME: [u8; 6] = [0, 5, 2, 4, 3, 1];
        for p in 0..4 {
            assert_eq!(TABLE[(p + 2) % N], GAME[(p + 2) % 6]);
        }
        let order: Vec<u8> = (0..N).map(|p| TABLE[(p + 2) % N]).collect();
        assert_eq!(order, [2, 4, 3, 1, GAUNTLET, 0, 5, ITEM]);
        let mut sorted = TABLE;
        sorted.sort();
        assert_eq!(sorted, [0, 1, 2, 3, 4, 5, ITEM, GAUNTLET], "every item once");
    }

    #[test]
    fn the_extras_resources_do_not_overlap_and_stay_off_the_games() {
        // OBJ tiles: Survival's 0x320..0x33F and Gauntlet's 0x2E0..0x2FF are 32 tiles each, clear of the Campaign chooser's 0x340.., the badge's 0x3E0 and the game's (up to 734 = 0x2DE).
        let (s, g) = (&EXTRAS[0], &EXTRAS[1]);
        assert!(g.tile > 734 && g.tile + 32 <= s.tile && s.tile + 32 <= 0x340);
        // Palettes: distinct, and not the Campaign chooser's (8, 10, 11, 12) or the game's items' (2..7 sides, 0, 1).
        assert!(s.palette != g.palette && [s.palette, g.palette].iter().all(|p| *p >= 13));
        // ROM: each entry's data fits its page, the sentinel is past them.
        assert!(SURVIVAL_AT + 0x8C0 + 0x400 <= GAUNTLET_AT);
        assert!(GAUNTLET_AT + 0x8C0 + 0x400 <= SENTINEL);
        assert!(DATA_OPTIONS >= SURVIVAL_AT + 0x40 && DATA_OPTIONS + 40 <= SURVIVAL_AT + 0xC0);
        assert!(DATA_HELP + 20 <= DATA_OPTIONS);
    }
}
