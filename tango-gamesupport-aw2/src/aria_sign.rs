//! **Aria's Vengeance, shown** (option E of the sign mock-ups, `devkit/aw2/colib/vengeance_mockups.py`; the rule is [`crate::aria`], nothing here changes a number):
//!
//! - **On the map** ([`map_flush`]): the HP number of a unit of hers with 8 to 1 displayed HP is drawn in a colour that goes from orange at 8 HP to dark red at 1 ([`crate::aria::RAMP`]) instead of white;
//!   the black box round it stays, 10 and 9 HP stay white, and so does every other CO's unit and an Oozium. The game draws a unit's HP number as BG1 tile `0x2A1 + HP` (the overlay tiles
//!   `sub_08026198` returns, tiles `0x2A2..0x2AA` for 1..9) in the unit's army bank (12..15, 11 once it has moved). At the end of every frame (after the game wrote its tile map) the digit cell of each
//!   such unit is pointed at one of eight tiles of our own, BG tiles `0x340..0x347` (free in every battle screen: they are the first tiles of an unused screen block; they are written only
//!   while empty or ours), a copy of the game's own digit tile with the colour index 1 (the digit) moved to index HP; and at a BG palette bank that holds the ramp in its indices 1..8 and black in 15. The bank is one
//!   no tile map refers to (4..7, the fog's terrain banks, in clear weather; 9, the menu's) and the game's own palette of it is kept in EWRAM ([`STATE`]) and put back when the bank is
//!   needed (a tile map refers to it) or nothing needs the ramp. AW2's low fuel / ammo icons are BG2 tiles in the cell's top-right corner and the capture / cargo mark is the bottom-left: only the
//!   bottom-right tile of a cell is touched. Everything is in VRAM, palette RAM and [`STATE`] (rollback and save states carry it), found again each frame from the unit records: a cell is
//!   changed only where the tile map holds the digit tile of that unit's HP (so never a hidden "?" or a fogged unit), and put back (the bank is worked out from the unit's record) when
//!   the unit no longer qualifies (a power healed it, Aria left the army by a Tag swap).
//! - **In the unit window** ([`crate::ds_hud`]): with the cursor on such a unit, a strip as wide as the window, in its fill, on top of it: "Vengeance" and below it "+NN%" (the unit's
//!   [`crate::aria::sign`]: her flat 5% and Vengeance). The same strip stands above the window while a damage forecast targets the unit, with the DAMAGE box lifted by its height.
//!   [`Strip`] builds the lettering at run time from the game's own window words (the letters e, c, n of "Recon", g of "Bridge", a of "Tank", cut out by their connected white pixels), the digits of the
//!   window's HP number (Dual Strike's, `ds_hud::digit_tiles`) and a V, "+" and "%" drawn here in the same style (small bitmaps below); nothing of the game's art is stored.

use mgba::core::Core;

use crate::co_new::ARIA;

/// Where the state lives in EWRAM (`ram_map.rs`): +0 the BG palette bank we hold plus one (0: none), +0x10 the game's 32 bytes of it.
pub const STATE: u32 = 0x0203_C3A0;
pub const STATE_LEN: u32 = 0x30;

const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const VRAM: u32 = 0x0600_0000;
/// The BG tiles of our eight digits (HP 1..8).
pub const BASE_TILE: u16 = 0x340;
const DIGIT_TILE: u16 = 0x2A1;
const CO_ABILITIES: u32 = 0x0300_3FC8;
const MAP_POINTER: u32 = 0x0849_9590;
const UNITS_POINTER: u32 = 0x0849_9594;
const MOVED_KEY: u32 = 0x0300_3F2C;
/// BG palette banks tried for the ramp, in order.
const BANKS: [u32; 5] = [4, 5, 6, 7, 9];

fn on_map(core: &Core) -> bool {
    crate::ds_battle::on_map(core)
}

/// The armies (1..5) whose CO is Aria, with the CO abilities on.
fn aria_armies(core: &Core) -> Vec<u32> {
    if core.raw_read_8(CO_ABILITIES, -1) == 0 {
        return Vec::new();
    }
    (1..=5)
        .filter(|&a| crate::co_roster::army_co(core, a).0 == ARIA)
        .collect()
}

/// Which army a unit record belongs to and the BG bank the game draws it in.
fn unit_bank(core: &Core, army: u32, moved: bool) -> u16 {
    if crate::five::active(core) {
        if moved {
            9
        } else if army >= 5 {
            11
        } else {
            12 + (army as u16 - 1).min(3)
        }
    } else {
        let key = if moved { core.raw_read_16(MOVED_KEY, -1) as u32 } else { 64 * (army - 1) };
        if moved {
            11
        } else {
            12 + ((key >> 6) & 3) as u16
        }
    }
}

fn read_bytes(core: &Core, at: u32, n: usize) -> Vec<u8> {
    let mut b = vec![0u8; n];
    core.raw_read_range(at, -1, &mut b);
    b
}

fn write_if_changed(core: &mut Core, at: u32, bytes: &[u8]) {
    if read_bytes(core, at, bytes.len()) != bytes {
        core.raw_write_range(at, -1, bytes);
    }
}

fn bank_bytes(core: &Core, bank: u32) -> Vec<u8> {
    read_bytes(core, PAL_BUFFER + 32 * bank, 32)
}

/// Our ramp bank's colours: index 1..8 the ramp for that HP, 15 black.
fn ramp_palette() -> Vec<u8> {
    let mut p = vec![0u8; 32];
    for h in 1..=8u8 {
        p[2 * h as usize..2 * h as usize + 2].copy_from_slice(&crate::aria::ramp_colour(h).to_le_bytes());
    }
    p
}

/// The game's palette of the bank we held, put back (once).
fn release(core: &mut Core) {
    let st = core.raw_read_8(STATE, -1) as u32;
    if st == 0 {
        return;
    }
    let bank = st - 1;
    // (when the bank is no longer ours the game wrote it again, for what now refers to it: that stays)
    if bank_bytes(core, bank) == ramp_palette() {
        let saved = read_bytes(core, STATE + 0x10, 32);
        for base in [PAL_BUFFER, PAL_RAM] {
            core.raw_write_range(base + 32 * bank, -1, &saved);
        }
    }
    core.raw_write_8(STATE, -1, 0);
}

/// The tile maps' references to each BG palette bank (bit per bank), our own digit cells left out.
fn banks_referenced(core: &Core) -> u32 {
    let mut refs = 0u32;
    for i in 0..4u32 {
        let cnt = core.raw_read_16(0x0400_0008 + 2 * i, -1) as u32;
        let base = VRAM + ((cnt >> 8) & 31) * 0x800;
        let n = match cnt >> 14 {
            0 => 1,
            1 | 2 => 2,
            _ => 4,
        };
        let b = read_bytes(core, base, 0x800 * n);
        for e in b.chunks_exact(2) {
            let e = u16::from_le_bytes([e[0], e[1]]);
            let tile = e & 0x3FF;
            if tile != 0 && !(BASE_TILE..BASE_TILE + 8).contains(&tile) {
                refs |= 1 << (e >> 12);
            }
        }
    }
    refs
}

/// Our digit tiles: the game's digit tile for HP 1..8 with colour 1 (the digit) at index HP.
fn digit_tiles(core: &Core) -> Vec<u8> {
    let mut out = Vec::with_capacity(8 * 32);
    for h in 1..=8u32 {
        let mut t = read_bytes(core, VRAM + 32 * (DIGIT_TILE as u32 + h), 32);
        for b in t.iter_mut() {
            let lo = if *b & 15 == 1 { h as u8 } else { *b & 15 };
            let hi = if *b >> 4 == 1 { h as u8 } else { *b >> 4 };
            *b = lo | (hi << 4);
        }
        out.extend(t);
    }
    out
}

/// One unit whose digit cell is in the tile map as the game or we drew it.
struct Cell {
    addr: u32,
    entry: u16,
    /// the unit's own bank
    bank: u16,
    /// the displayed HP of the unit whose cell this is, when the unit is Aria's and has the sign
    sign: Option<u8>,
}

/// The cells of the units' digits this frame.
fn cells(core: &Core, armies: &[u32]) -> Vec<Cell> {
    let mut out = Vec::new();
    let cnt = core.raw_read_16(0x0400_000A, -1) as u32;
    if cnt >> 14 != 0 {
        return out;
    }
    let sb = VRAM + ((cnt >> 8) & 31) * 0x800;
    let map = core.raw_read_32(MAP_POINTER, -1);
    let units = core.raw_read_32(UNITS_POINTER, -1);
    if !(0x0200_0000..0x0400_0000).contains(&map) || !(0x0200_0000..0x0400_0000).contains(&units) {
        return out;
    }
    let cam = (core.raw_read_16(map + 4, -1) as i16 as i32, core.raw_read_16(map + 6, -1) as i16 as i32);
    let (map_x0, map_y0) = (cam.0.div_euclid(16), cam.1.div_euclid(16));
    // the units' plane is 16 x 16 cells whose place in the window is the ground's scroll (BG3), as `ds_tilt` reads it
    let gx = ((core.raw_read_16(0x0400_001C, -1) & 0x1FF) as i32).div_euclid(16);
    let gy = ((core.raw_read_16(0x0400_001E, -1) & 0x1FF) as i32).div_euclid(16);
    let five = crate::five::active(core);
    let per = if five { 51 } else { 64 };
    let all = read_bytes(core, units, 12 * 256);
    for id in 0..256u32 {
        if id % per == 0 {
            continue;
        }
        let u = &all[12 * id as usize..12 * id as usize + 12];
        if u[0] == 0 {
            continue;
        }
        let (dx, dy) = (u[2] as i32 - map_x0, u[3] as i32 - map_y0);
        if !(0..=14).contains(&dx) || !(0..=10).contains(&dy) {
            continue;
        }
        let (col, row) = (2 * ((dx + gx) & 15) as u32 + 1, 2 * ((dy + gy) & 15) as u32 + 1);
        let addr = sb + 2 * (row * 32 + col);
        let entry = core.raw_read_16(addr, -1);
        let tile = entry & 0x3FF;
        let digit = (DIGIT_TILE + 1..=DIGIT_TILE + 9).contains(&tile);
        let ours = (BASE_TILE..BASE_TILE + 8).contains(&tile);
        if !digit && !ours {
            continue;
        }
        let army = id / per + 1;
        let hp = u[4] & 0x7F;
        let sign = armies
            .contains(&army)
            .then(|| crate::aria::sign(u[0], hp))
            .flatten()
            .map(|(shown, _)| shown)
            .filter(|&shown| tile == DIGIT_TILE + shown as u16 || tile == BASE_TILE + shown as u16 - 1);
        out.push(Cell {
            addr,
            entry,
            bank: unit_bank(core, army, u[1] & 1 != 0),
            sign,
        });
    }
    out
}

/// At the end of each frame of a battle (the sprite flush, [`crate::branding::flush`]): the HP numbers of Aria's wounded units in the ramp.
pub fn map_flush(core: &mut Core) {
    let held = core.raw_read_8(STATE, -1) != 0;
    let armies = if on_map(core) { aria_armies(core) } else { Vec::new() };
    if armies.is_empty() && !held {
        return;
    }
    let cells = if armies.is_empty() { Vec::new() } else { cells(core, &armies) };
    // Whether anything has to be in the ramp, and the cells that are ours and no longer should be.
    let wanted = cells.iter().any(|c| c.sign.is_some());
    let stale = cells.iter().any(|c| c.sign.is_none() && (BASE_TILE..BASE_TILE + 8).contains(&(c.entry & 0x3FF)));
    let bank = if wanted { claim(core) } else { None };
    for c in &cells {
        let (tile, flips) = (c.entry & 0x3FF, c.entry & 0xC00);
        let want = match (c.sign, bank) {
            (Some(shown), Some(b)) => Some(BASE_TILE + shown as u16 - 1 | flips | (b as u16) << 12),
            _ => None,
        };
        let new = match want {
            Some(w) => w,
            // (ours but no longer wanted: the game's digit of that number in the unit's own bank)
            None if (BASE_TILE..BASE_TILE + 8).contains(&tile) => DIGIT_TILE + 1 + (tile - BASE_TILE) | flips | c.bank << 12,
            None => continue,
        };
        if new != c.entry {
            core.raw_write_16(c.addr, -1, new);
        }
    }
    if bank.is_none() && (held || stale || !wanted) {
        // (the cells are back: the palette goes back too)
        release(core);
    }
}

/// The BG bank for the ramp, with our tiles written: `None` when none is free (the numbers stay white).
fn claim(core: &mut Core) -> Option<u32> {
    // the tiles: empty, or ours
    let tiles = digit_tiles(core);
    let now = read_bytes(core, VRAM + 32 * BASE_TILE as u32, tiles.len());
    if now != tiles && now.iter().any(|&b| b != 0) {
        return None;
    }
    let refs = banks_referenced(core);
    let held = core.raw_read_8(STATE, -1) as u32;
    let bank = if held != 0 && refs >> (held - 1) & 1 == 0 {
        held - 1
    } else {
        *BANKS.iter().find(|&&b| refs >> b & 1 == 0)?
    };
    if held != 0 && held - 1 != bank {
        release(core);
    }
    let mine = ramp_palette();
    let cur = bank_bytes(core, bank);
    let st = core.raw_read_8(STATE, -1) as u32;
    if st == 0 {
        core.raw_write_range(STATE + 0x10, -1, &cur);
        core.raw_write_8(STATE, -1, bank as u8 + 1);
    } else if cur != mine {
        // (the game wrote the bank again: that is what it is to be given back)
        core.raw_write_range(STATE + 0x10, -1, &cur);
    }
    for base in [PAL_BUFFER, PAL_RAM] {
        write_if_changed(core, base + 32 * bank, &mine);
    }
    write_if_changed(core, VRAM + 32 * BASE_TILE as u32, &tiles);
    Some(bank)
}

// --- The window's strip -----------------------------------------------------------------------------

/// The window words the letters come from (AW2's name pictures: 32 x 16 pixels, 4 bits, 1D tiles; index 1 the white, 15 the dark outline): the Tank, the Recon and the Bridge.
const WORD_TANK: u32 = 0x0810_8664;
const WORD_RECON: u32 = 0x0810_8764;
const WORD_BRIDGE: u32 = 0x0810_7564;

/// A capital V drawn in the letters' style (2-pixel strokes, the capitals' height), since no window word has one.
const V_ROWS: [&str; 9] = ["##...##", "##...##", "##...##", ".##.##.", ".##.##.", ".##.##.", "..###..", "..###..", "...#..."];
/// The row of the 16-row word box its first row is on.
const V_TOP: i32 = 5;
/// Where a name picture's first row is in that box.
const NAME_ROW: i32 = 2;
/// "+" and "%" in the digits' style (2-pixel strokes, 6 rows).
const PLUS_ROWS: [&str; 6] = ["..##..", "..##..", "######", "######", "..##..", "..##.."];
const PERCENT_ROWS: [&str; 6] = ["##...#", "##..#.", "...#..", "..#...", ".#..##", "#...##"];

/// What the strip adds above the window: its height (the window grows up by this much), the lettering's place.
pub const STRIP_H: i32 = 26;

type Glyph = Vec<(i32, i32)>;

/// The 32 x 16 pixels (colour indices) of a name picture at `at` in the ROM.
fn word(core: &Core, at: u32) -> Vec<u8> {
    let d = read_bytes(core, at, 0x100);
    let mut px = vec![0u8; 32 * 16];
    for y in 0..16usize {
        for x in 0..32usize {
            let t = (y / 8) * 4 + x / 8;
            let b = d[32 * t + (y % 8) * 4 + (x % 8) / 2];
            px[y * 32 + x] = if x & 1 == 1 { b >> 4 } else { b & 15 };
        }
    }
    px
}

/// The letters of a picture: the 8-connected runs of pixels of colour `fill`, left to right.
fn letters(px: &[u8], w: usize, h: usize, fill: u8) -> Vec<Glyph> {
    let mut seen = vec![false; w * h];
    let mut out: Vec<Glyph> = Vec::new();
    for y in 0..h {
        for x in 0..w {
            if px[y * w + x] != fill || seen[y * w + x] {
                continue;
            }
            let mut stack = vec![(x as i32, y as i32)];
            seen[y * w + x] = true;
            let mut g = Vec::new();
            while let Some((cx, cy)) = stack.pop() {
                g.push((cx, cy));
                for (dx, dy) in [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)] {
                    let (nx, ny) = (cx + dx, cy + dy);
                    if nx >= 0 && ny >= 0 && (nx as usize) < w && (ny as usize) < h && px[ny as usize * w + nx as usize] == fill && !seen[ny as usize * w + nx as usize] {
                        seen[ny as usize * w + nx as usize] = true;
                        stack.push((nx, ny));
                    }
                }
            }
            out.push(g);
        }
    }
    out.sort_by_key(|g| g.iter().map(|p| p.0).min().unwrap_or(0));
    out
}

fn rows_glyph(rows: &[&str], top: i32) -> Glyph {
    let mut g = Vec::new();
    for (y, r) in rows.iter().enumerate() {
        for (x, c) in r.bytes().enumerate() {
            if c == b'#' {
                g.push((x as i32, y as i32 + top));
            }
        }
    }
    g
}

/// The letters of "Vengeance" in the window's lettering, each a glyph by letter.
fn lettering(core: &Core) -> Option<Vec<(char, Glyph)>> {
    let recon = letters(&word(core, WORD_RECON), 32, 16, 1);
    let bridge = letters(&word(core, WORD_BRIDGE), 32, 16, 1);
    let tank = letters(&word(core, WORD_TANK), 32, 16, 1);
    // (R e c o n, B r d g, T a n k)
    if recon.len() != 5 || bridge.len() != 4 || tank.len() != 4 {
        return None;
    }
    // (a name picture's row 0 is the second row of the 16-row box the V's rows are counted in: the panel puts the picture's sprite two rows below the box's top)
    let low = |g: &Glyph| -> Glyph { g.iter().map(|&(x, y)| (x, y + NAME_ROW)).collect() };
    let pick = |c: char| -> Glyph {
        match c {
            'V' => rows_glyph(&V_ROWS, V_TOP),
            'e' => low(&recon[1]),
            'c' => low(&recon[2]),
            'n' => low(&recon[4]),
            'g' => low(&bridge[3]),
            _ => low(&tank[1]),
        }
    };
    Some("Vengeance".chars().map(|c| (c, pick(c))).collect())
}

/// Glyphs set left to right (one blank column between, the first at x 1): the fill and the width after the last.
fn set_line(glyphs: &[Glyph]) -> (Vec<(i32, i32)>, i32) {
    let mut fill = Vec::new();
    let mut x = 1;
    for g in glyphs {
        let gx0 = g.iter().map(|p| p.0).min().unwrap_or(0);
        let gx1 = g.iter().map(|p| p.0).max().unwrap_or(0);
        for &(px, py) in g {
            fill.push((x + px - gx0, py));
        }
        x += gx1 - gx0 + 2;
    }
    (fill, x)
}

/// A line's pixels (1 the white, 15 the dark outline round it on the four sides), `w` x `h` with the line's own origin at (`ox`, `oy`) in it.
fn render(fill: &[(i32, i32)], w: usize, h: usize, ox: i32, oy: i32) -> Vec<u8> {
    let mut px = vec![0u8; w * h];
    let put = |px: &mut Vec<u8>, x: i32, y: i32, c: u8, over: bool| {
        let (x, y) = (x + ox, y + oy);
        if x >= 0 && y >= 0 && (x as usize) < w && (y as usize) < h && (over || px[y as usize * w + x as usize] == 0) {
            px[y as usize * w + x as usize] = c;
        }
    };
    for &(x, y) in fill {
        for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
            put(&mut px, x + dx, y + dy, 15, false);
        }
    }
    for &(x, y) in fill {
        put(&mut px, x, y, 1, true);
    }
    px
}

/// 4-bit tiles of `px` (`w` x `h`), 1D order: a sprite's tiles in rows of `w / 8`.
fn to_tiles(px: &[u8], w: usize, h: usize) -> Vec<u8> {
    let mut out = vec![0u8; w * h / 2];
    for ty in 0..h / 8 {
        for tx in 0..w / 8 {
            let t = ty * (w / 8) + tx;
            for r in 0..8 {
                for c in 0..8 {
                    out[32 * t + 4 * r + c / 2] |= (px[(8 * ty + r) * w + 8 * tx + c] & 15) << (4 * (c & 1));
                }
            }
        }
    }
    out
}

/// The strip's two lines as sprite tiles and widths.
pub struct Strip {
    /// "Vengeance": two 32 x 16 sprites, 16 tiles; its line's width (the line is placed so that this is centred)
    pub line1: Vec<u8>,
    pub w1: i32,
    /// "+NN%": one 32 x 8 sprite, 4 tiles
    pub line2: Vec<u8>,
    pub w2: i32,
}

fn digit_glyph(tile: &[u8]) -> Glyph {
    let mut g = Vec::new();
    for y in 0..8i32 {
        for x in 0..8i32 {
            let b = tile[(y * 4 + x / 2) as usize];
            let c = if x & 1 == 1 { b >> 4 } else { b & 15 };
            if c == 1 {
                g.push((x, y));
            }
        }
    }
    let y0 = g.iter().map(|p| p.1).min().unwrap_or(0);
    g.iter().map(|&(x, y)| (x, y - y0)).collect()
}

impl Strip {
    /// `digits`: Dual Strike's ten window digits (0..9, 8 x 8 tiles). `None` when a piece is not where it should be (the lettering is then left out).
    pub fn new(core: &Core, digits: &[u8], percent: i32) -> Option<Strip> {
        let letters = lettering(core)?;
        let (fill1, w1) = set_line(&letters.iter().map(|l| l.1.clone()).collect::<Vec<_>>());
        let mut glyphs = vec![rows_glyph(&PLUS_ROWS, 0)];
        for c in percent.to_string().bytes() {
            glyphs.push(digit_glyph(digits.get(32 * (c - b'0') as usize..32 * (c - b'0') as usize + 32)?));
        }
        glyphs.push(rows_glyph(&PERCENT_ROWS, 0));
        let (fill2, w2) = set_line(&glyphs);
        // (one row up: the g's outline is the 17th row of the 16-row box the letters are laid out in)
        let p1 = render(&fill1, 64, 16, 0, -1);
        // two sprites: the left half then the right half
        let mut line1 = Vec::new();
        for half in 0..2 {
            let mut sub = vec![0u8; 32 * 16];
            for y in 0..16 {
                sub[y * 32..y * 32 + 32].copy_from_slice(&p1[y * 64 + 32 * half..y * 64 + 32 * half + 32]);
            }
            line1.extend(to_tiles(&sub, 32, 16));
        }
        // (the line's own row 0 is the sprite's row 1: the outline above the digits' top row)
        let line2 = to_tiles(&render(&fill2, 32, 8, 0, 1), 32, 8);
        Some(Strip { line1, w1, line2, w2 })
    }
}

/// The ramp colour (RGB555) of a unit's HP number for a renderer that draws units from their records (the tilted map): `Some` for a unit of Aria's with the sign.
pub fn unit_ramp(core: &Core, army: u32, kind: u8, hp: u8) -> Option<u16> {
    if core.raw_read_8(CO_ABILITIES, -1) == 0 || !(1..=5).contains(&army) || crate::co_roster::army_co(core, army).0 != ARIA {
        return None;
    }
    crate::aria::sign(kind, hp).map(|(shown, _)| crate::aria::ramp_colour(shown))
}

/// The unit under the map cursor, if it is Aria's and has the sign: the percent shown.
pub fn cursor_percent(core: &Core, unit: u32) -> Option<i32> {
    if core.raw_read_8(CO_ABILITIES, -1) == 0 {
        return None;
    }
    let army = crate::unit_actions::army_of(core, unit);
    if !(1..=5).contains(&army) || crate::co_roster::army_co(core, army).0 != ARIA {
        return None;
    }
    crate::aria::sign(core.raw_read_8(unit, -1), core.raw_read_8(unit + 4, -1) & 0x7F).map(|(_, p)| p)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn letters_split_a_picture_by_its_white_runs() {
        // two letters one column apart, the second touching diagonally inside itself
        let mut px = vec![0u8; 32 * 16];
        for (x, y) in [(1, 1), (1, 2), (4, 1), (5, 2), (5, 3)] {
            px[y * 32 + x] = 1;
        }
        let l = letters(&px, 32, 16, 1);
        assert_eq!(l.len(), 2);
        assert_eq!(l[0].len(), 2);
        assert_eq!(l[1].len(), 3);
    }

    #[test]
    fn a_line_is_outlined_on_four_sides() {
        let fill = vec![(1, 1), (2, 1)];
        let px = render(&fill, 8, 8, 0, 0);
        assert_eq!(px[8 + 1], 1);
        assert_eq!(px[8], 15, "outline left");
        assert_eq!(px[8 + 3], 15, "outline right");
        assert_eq!(px[1], 15, "outline above");
        assert_eq!(px[2 * 8 + 2], 15, "outline below");
        assert_eq!(px[0], 0, "no outline on the corner");
    }

    #[test]
    fn tiles_are_in_one_d_order() {
        let mut px = vec![0u8; 32 * 16];
        px[8 * 32 + 8] = 3; // tile row 1, column 1: tile 5, its first pixel
        let t = to_tiles(&px, 32, 16);
        assert_eq!(t.len(), 256);
        assert_eq!(t[32 * 5] & 15, 3);
    }

    #[test]
    fn the_drawn_letters_have_pixels() {
        assert_eq!(rows_glyph(&V_ROWS, V_TOP).len(), 31);
        assert_eq!(rows_glyph(&PLUS_ROWS, 0).len(), 2 * 2 + 2 * 6 + 2 * 2);
        assert_eq!(rows_glyph(&PERCENT_ROWS, 0).iter().map(|p| p.1).max(), Some(5));
    }
}
