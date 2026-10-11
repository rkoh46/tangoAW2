//! The CO info page in Dual Strike's style, on the GBA's 240 x 160 screen,
//! with the Dual Strike pack and the "Dual Strike map graphics" setting
//! (offline only).
//!
//! The map menu's CO entry opens AW2's full-screen CO page (its main loop
//! `0x08043591`, the page's process `0x08616BE4`); while it is up this module
//! draws Dual Strike's page over it instead: the page frame's header strip
//! (`info/000`: nine-patch tiles, the CO's country tab, the partner tab, the
//! CO's face cropped in at the right), the page counter (`icon/res_icon4_cg`)
//! and the BACK button (`ohashi/res_tpicon_lang_E`), Dual Strike's own font
//! (overlay 0: glyph pointers `0x49278`, widths `0x49178`; 16 rows of 4bpp,
//! `(width + 1) / 2` bytes a row; the digits are its bold ones), the CO's
//! picture beside the text, and the pages as Dual Strike has them:
//!
//! 1. **the description**: the CO's bio with Hit and Miss, then the day to
//!    day text, re-wrapped to the room the picture leaves;
//! 2. **skills**: the skills the army has on (and its tag partners);
//! 3. **powers**: the CO Power and the Super Power, name and text;
//! 4. **the unit chart**, which is AW2's own page (the game draws it; this
//!    module steps aside for it).
//!
//! Dual Strike's text for every CO it has (AW2's too), tangoAW2's for the
//! ones it lacks (Sturm: AW2's own, Clone Andy, Crumb).
//!
//! **How.** Everything is drawn on BG0 (the page's own layer: char block 0,
//! screen block 14, priority 0), every tile opaque, so the page's other
//! layers are covered; the game's sprites are hidden by the VBlank flush
//! ([`flush`]). The 8 x 8 cells of a layer share one palette bank, so the
//! picture, the face, the tabs, the counter and the BACK button sit on cell
//! boundaries and the text is wrapped around them. LEFT and RIGHT (the army
//! walk, the partner tabs) and B are the game's own; DOWN and UP move this
//! page. Nothing here is in emulated memory but the layer itself: it runs only
//! offline (no netplay, no replay), where nothing needs it to agree.

use mgba::core::Core;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};

/// Pages that fitted no layout and were left with the frame only (a bug a
/// test looks for).
static FALLBACKS: AtomicUsize = AtomicUsize::new(0);

pub fn fallbacks() -> usize {
    FALLBACKS.load(Ordering::Relaxed)
}

// --- Where the game's CO page is -----------------------------------------------------

const MAIN_LOOP: u32 = 0x0300_0000;
/// The CO page's main loop (the battle scene is unloaded while it is up).
const CO_PAGE_LOOP: u32 = 0x0804_3591;
const PROC_POOL: (u32, u32) = (0x0200_D610, 0x0200_E418);
const PROC_SIZE: u32 = 0x6C;
/// The page's process (its script word) and its army (+0x66).
const CO_PAGE_PROC: u32 = 0x0861_6BE4;
const PROC_ARMY: u32 = 0x66;
/// The page the game itself is on (0 the bio .. 4 the unit chart).
const GAME_PAGE: u32 = 0x0300_5940;
/// Its Super Power's page: where the game stays under this module's pages.
const GAME_SCOP_PAGE: u32 = 3;
/// The CO page's ROM presentation rows (see [`crate::ds_co_art`]).
const PRESENTATION_POOL: u32 = 0x0803_9B7C;
const PRESENTATION_ROW: u32 = 0x44;

const KEY_DOWN: u32 = 1 << 7;
const KEY_UP: u32 = 1 << 6;

/// How many pages Dual Strike's CO page has.
pub const PAGES: usize = 4;

fn page_proc(core: &Core) -> Option<u32> {
    if core.raw_read_32(MAIN_LOOP, -1) != CO_PAGE_LOOP {
        return None;
    }
    (PROC_POOL.0..PROC_POOL.1).step_by(PROC_SIZE as usize).find(|&p| core.raw_read_32(p, -1) == CO_PAGE_PROC)
}

// --- State --------------------------------------------------------------------------

struct State {
    open: bool,
    page: usize,
    /// BG0's tiles from 512 on, which the page does not use, as they were.
    saved: Vec<u8>,
    /// The built layer (key, tiles, tilemap, palettes), so a still page
    /// costs nothing.
    built: Option<(u64, Vec<u8>, Vec<u8>, Vec<u8>)>,
    /// The page's layer bits of DISPCNT as they were, while only BG0 shows.
    layers: Option<u16>,
    /// The game's own BG palettes when the page opened (put back when it closes).
    pal: Vec<u8>,
    /// What BG2's tiles and tilemap held under the wall, as (address, bytes).
    wall_saved: Vec<(u32, Vec<u8>)>,
}

static STATE: Mutex<State> = Mutex::new(State { open: false, page: 0, saved: Vec::new(), built: None, layers: None, pal: Vec::new(), wall_saved: Vec::new() });

pub fn is_open() -> bool {
    STATE.lock().map(|s| s.open).unwrap_or(false)
}

// --- Dual Strike's font -----------------------------------------------------------

const OV_BASE: u32 = 0x022A_D560;
const GLYPH_TABLE: usize = 0x49278;
const WIDTH_TABLE: usize = 0x49178;
const GLYPH_ROWS: usize = 16;
/// The glyph rows a line shows (ink spans rows 3 to 15).
const TOP_ROW: usize = 3;
pub const INK_ROWS: usize = 13;

pub struct Font {
    w: [u8; 256],
    /// Per character: 4bpp rows of `(w + 1) / 2` bytes.
    glyph: Vec<Vec<u8>>,
}

fn build_font() -> Option<Font> {
    let ov = crate::ds_pack::pack()?.overlays.first()?;
    let mut w = [0u8; 256];
    let mut glyph = vec![Vec::new(); 256];
    for c in 0x20..0x7Fusize {
        w[c] = *ov.get(WIDTH_TABLE + c)?;
        let p = u32::from_le_bytes(ov.get(GLYPH_TABLE + 4 * c..GLYPH_TABLE + 4 * c + 4)?.try_into().ok()?);
        let off = p.checked_sub(OV_BASE)? as usize;
        let len = GLYPH_ROWS * (w[c] as usize).div_ceil(2);
        glyph[c] = ov.get(off..off + len)?.to_vec();
    }
    Some(Font { w, glyph })
}

pub fn font() -> Option<&'static Font> {
    static FONT: OnceLock<Option<Font>> = OnceLock::new();
    FONT.get_or_init(build_font).as_ref()
}

impl Font {
    fn adv(&self, c: u8) -> i32 {
        if (0x20..0x7F).contains(&c) {
            self.w[c as usize] as i32 + 1
        } else {
            0
        }
    }
    /// A string's width in pixels (no space after the last character).
    pub fn width(&self, s: &str) -> i32 {
        (s.bytes().map(|c| self.adv(c)).sum::<i32>() - 1).max(0)
    }
    /// Pixel `(x, y)` of a glyph: 0 clear, 10 ink, 14 edge.
    fn pixel(&self, c: u8, x: usize, y: usize) -> u8 {
        let g = &self.glyph[c as usize];
        let bpr = (self.w[c as usize] as usize).div_ceil(2);
        match g.get(bpr * y + x / 2) {
            Some(b) => (b >> (4 * (x & 1))) & 15,
            None => 0,
        }
    }
}

// --- The canvas -----------------------------------------------------------------------

/// BG palette banks.
const UI: u8 = 0;
const CO: u8 = 1;
const TAB: u8 = 2;
const DIGITS: u8 = 3;
const BACK: u8 = 4;
/// The unit chart's pictures (the army's colours).
const UNIT: u8 = 5;
/// The headings' pictures (Existing skills, the power's stars).
const HEAD: u8 = 6;
const INK: u8 = 10;
const EDGE: u8 = 14;
const WHITE: u16 = 0x7FFF;

/// The UI bank: Dual Strike's page colours (white, the strip's reds and
/// blues, the text's ink and edge).
const UI_PALETTE: [u16; 16] = [
    WHITE, WHITE, 0x631F, 0x421F, 0x14BF, 0x7BDD, 0x7F18, 0x7E10, 0x7D08, 0x77BF, 0x0000, 0x4210, 0x779B, 0x6B38, 0x5AF8, 0x3E11,
];

const fn rgb15(r: u16, g: u16, b: u16) -> u16 {
    (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
}

/// The colours of the heading pictures (res_icon0_cg's icons 88, 19 and 20), read from real frames.
const HEAD_PALETTE: [u16; 16] = [
    WHITE,
    rgb15(250, 250, 250),
    WHITE,
    rgb15(186, 178, 170),
    rgb15(121, 113, 89),
    rgb15(250, 153, 113),
    rgb15(250, 242, 32),
    WHITE,
    WHITE,
    WHITE,
    rgb15(210, 153, 97),
    rgb15(121, 145, 250),
    rgb15(97, 105, 218),
    rgb15(170, 186, 250),
    WHITE,
    rgb15(186, 129, 89),
];
/// res_icon0_cg's pictures for the skills heading and the one-star and two-star powers.
const ICON_SKILLS: usize = 88;
const ICON_COP: usize = 19;
const ICON_SCOP: usize = 20;
/// A heading's picture sits here, its text beside it.
const HEAD_X: i32 = 72;

pub struct Canvas {
    px: Vec<u8>,
    bank: Vec<u8>,
    /// Cells holding something with another bank than the UI's.
    owned: Vec<bool>,
    /// The eight BG palette banks.
    pals: Vec<[u16; 16]>,
}

impl Canvas {
    fn new() -> Self {
        Canvas { px: vec![0; 240 * 160], bank: vec![UI; 30 * 20], owned: vec![false; 30 * 20], pals: vec![UI_PALETTE; 8] }
    }
    fn put(&mut self, x: i32, y: i32, bank: u8, v: u8) {
        if (0..240).contains(&x) && (0..160).contains(&y) {
            let cell = 30 * (y as usize / 8) + x as usize / 8;
            if bank != UI {
                self.bank[cell] = bank;
                self.owned[cell] = true;
            } else if self.owned[cell] {
                return;
            }
            self.px[240 * y as usize + x as usize] = v;
        }
    }
    /// Whether `(x, y)` is in a cell of another bank.
    fn taken(&self, x: i32, y: i32) -> bool {
        (0..240).contains(&x) && (0..160).contains(&y) && self.owned[30 * (y as usize / 8) + x as usize / 8]
    }
    /// A picture of 4bpp tiles in rows, `w` x `h` pixels, at a cell boundary.
    fn tiles(&mut self, x: i32, y: i32, tiles: &[u8], w: usize, h: usize, bank: u8) {
        debug_assert!(x % 8 == 0 && y % 8 == 0);
        let tw = w / 8;
        for k in 0..tw * (h / 8) {
            let t = match tiles.get(32 * k..32 * k + 32) {
                Some(t) => t,
                None => return,
            };
            for yy in 0..8 {
                for xx in 0..8 {
                    let v = (t[4 * yy + xx / 2] >> (4 * (xx & 1))) & 15;
                    self.put(x + (8 * (k % tw) + xx) as i32, y + (8 * (k / tw) + yy) as i32, bank, v);
                }
            }
        }
    }
    /// A linear picture of palette indices, `w` x `h`, at a cell boundary.
    fn picture(&mut self, x: i32, y: i32, px: &[u8], w: usize, h: usize, bank: u8) {
        debug_assert!(x % 8 == 0 && y % 8 == 0);
        for yy in 0..h {
            for xx in 0..w {
                self.put(x + xx as i32, y + yy as i32, bank, px[w * yy + xx]);
            }
        }
    }
    /// One line of text in Dual Strike's font (ink rows only), x the first
    /// pixel; returns the x after it. Pixels in cells of another bank are
    /// not drawn (the layout keeps clear of them).
    pub fn text(&mut self, f: &Font, x: i32, y: i32, s: &str) -> i32 {
        let mut x = x;
        for c in s.bytes() {
            if (0x20..0x7F).contains(&c) {
                let w = f.w[c as usize] as usize;
                for r in 0..INK_ROWS {
                    for cx in 0..w {
                        let v = f.pixel(c, cx, TOP_ROW + r);
                        if v != 0 {
                            debug_assert!(!self.taken(x + cx as i32, y + r as i32), "text over a picture");
                            self.put(x + cx as i32, y + r as i32, UI, if v == 10 { INK } else { EDGE });
                        }
                    }
                }
            }
            x += f.adv(c);
        }
        x
    }
    fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, v: u8) {
        for yy in y..y + h {
            for xx in x..x + w {
                self.put(xx, yy, UI, v);
            }
        }
    }
}

// --- What the page shows -------------------------------------------------------------

/// A CO's picture: the body (128 x 160 indices) and the face's top 16 rows
/// (48 x 16), in one 16-colour palette.
pub struct Portrait {
    pub body: Vec<u8>,
    pub mug: Vec<u8>,
    pub pal: [u16; 16],
}

pub struct View {
    pub name: String,
    /// The two tabs' countries (0 Orange Star .. 4 Black Hole): the army's
    /// active CO and its partner (`None` when it has none), and the tab the
    /// page is on.
    pub tabs: [Option<u8>; 2],
    pub tab: usize,
    pub bio: Vec<u8>,
    pub d2d: Vec<u8>,
    pub cop_name: String,
    pub cop: Vec<u8>,
    pub scop_name: String,
    pub scop: Vec<u8>,
    /// (name, description) of each skill the army has on.
    pub skills: Vec<(String, String)>,
    /// Tag partners: (name, stars).
    pub partners: Vec<(String, u8)>,
    pub portrait: Option<Portrait>,
    /// The unit chart: the army's colour (0 Orange Star .. 4 Black Hole) and a row for each unit.
    pub colour: usize,
    pub chart: Vec<ChartUnit>,
}

/// A unit of the chart: its picture, and the CO's stats for it in gauge steps of 5 %.
#[derive(Clone, Copy)]
pub struct ChartUnit {
    pub icon: usize,
    /// The attack gauge's steps (`None`: the unit has no weapon, so no gauge).
    pub attack: Option<i32>,
    pub defence: i32,
    pub range: i32,
}

/// The units the chart lists, in Dual Strike's order (our unit type, Dual Strike's picture, whether it carries a weapon): the
/// rows are `CHART_ROWS` long (four, five, five, four, four, four).
const CHART_UNITS: [(u8, usize, bool); 26] = [
    (1, 24, true),   // Infantry
    (2, 26, true),   // Mech
    (6, 2, true),    // Recon
    (7, 3, false),   // APC
    (14, 6, true),   // Anti-Air
    (5, 1, true),    // Tank
    (3, 0, true),    // Md Tank
    (8, 16, true),   // Neotank
    (4, 17, true),   // Megatank
    (10, 4, true),   // Artillery
    (11, 5, true),   // Rockets
    (15, 7, true),   // Missiles
    (9, 18, true),   // Piperunner
    (27, 23, false), // Oozium
    (16, 8, true),   // Fighter
    (17, 9, true),   // Bomber
    (12, 19, true),  // Stealth
    (13, 20, false), // Black Bomb
    (19, 10, true),  // B Copter
    (20, 11, false), // T Copter
    (21, 12, true),  // Battleship
    (26, 22, true),  // Carrier
    (22, 13, true),  // Cruiser
    (24, 15, true),  // Sub
    (23, 14, false), // Lander
    (18, 21, false), // Black Boat
];
const CHART_ROWS: [usize; 6] = [4, 5, 5, 4, 4, 4];
/// The chart's rows for `co` at power level `mode`.
fn chart_for(co: u8, mode: u8) -> Vec<ChartUnit> {
    use crate::co_roster::{stat, DEFENCE, FIREPOWER, RANGE};
    CHART_UNITS
        .iter()
        .map(|&(t, icon, armed)| {
            let steps = |field: usize| (stat(co, mode, t, field).unwrap_or(0) as f32 / 5.0).round() as i32;
            ChartUnit {
                icon,
                attack: armed.then(|| steps(FIREPOWER)),
                defence: steps(DEFENCE),
                range: stat(co, mode, t, RANGE).unwrap_or(0),
            }
        })
        .collect()
}

/// A text as plain ASCII words in single spaces.
fn plain(t: &[u8]) -> String {
    let s: String = t.iter().map(|&c| if (0x20..0x7F).contains(&c) { c as char } else { ' ' }).collect();
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// A bio or a power's text as paragraphs: Dual Strike's line breaks are
/// dropped (the words are wrapped again), but a line starting "Hit" or
/// "Miss:" starts a paragraph of its own.
pub fn paragraphs(t: &[u8]) -> Vec<String> {
    let text = plain(t);
    let mut out: Vec<String> = vec![String::new()];
    for word in text.split(' ').filter(|w| !w.is_empty()) {
        if (word.starts_with("Hit") && word.ends_with(':')) || word.starts_with("Miss:") || (word == "Hits:") {
            if !out.last().unwrap().is_empty() {
                out.push(String::new());
            }
        }
        let p = out.last_mut().unwrap();
        if !p.is_empty() {
            p.push(' ');
        }
        p.push_str(word);
    }
    out.retain(|p| !p.is_empty());
    out
}

/// Pixel limits of a page's text.
const LEFT: i32 = 8;
const RIGHT: i32 = 234;
const TEXT_TOP: i32 = 36;
const BOTTOM: i32 = 160;

/// A rectangle (on cell boundaries) the text keeps clear of.
#[derive(Clone, Copy)]
struct Obstacle {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
}

struct Flow<'a> {
    f: &'a Font,
    obstacles: Vec<Obstacle>,
    y: i32,
    pitch: i32,
    /// What it drew: lines, and whether anything did not fit.
    overflow: bool,
}

impl<'a> Flow<'a> {
    /// The right limit for a line at `y` (13 ink rows).
    fn right_at(&self, y: i32) -> i32 {
        let mut r = RIGHT;
        for o in &self.obstacles {
            if y < o.y + o.h && y + INK_ROWS as i32 > o.y {
                r = r.min(o.x - 3);
            }
        }
        r
    }
    fn left_at(&self, y: i32) -> i32 {
        let mut l = LEFT;
        for o in &self.obstacles {
            if y < o.y + o.h && y + INK_ROWS as i32 > o.y && o.x + o.w <= 120 {
                l = l.max(o.x + o.w + 3);
            }
        }
        l
    }
    /// The words broken into lines that fit (a word wider than its line
    /// goes on a line of its own and counts as overflow).
    fn lines(&self, text: &str, indent: i32, mut y: i32) -> Vec<(i32, String)> {
        let mut out = Vec::new();
        let mut line = String::new();
        let mut first = true;
        for word in text.split(' ').filter(|w| !w.is_empty()) {
            let x0 = self.left_at(y) + if first { 0 } else { indent };
            let r = self.right_at(y);
            let longer = if line.is_empty() { word.to_string() } else { format!("{line} {word}") };
            if !line.is_empty() && x0 + self.f.width(&longer) > r {
                out.push((y, std::mem::replace(&mut line, word.to_string())));
                y += self.pitch;
                first = false;
            } else {
                line = longer;
            }
        }
        if !line.is_empty() {
            out.push((y, line));
        }
        out
    }
    /// Lays a paragraph out at the flow's `y` and draws it; `false` and
    /// nothing drawn when it does not fit above the bottom.
    fn para(&mut self, cv: &mut Canvas, text: &str, indent: i32) -> bool {
        let lines = self.lines(text, indent, self.y);
        let end = lines.last().map(|l| l.0 + INK_ROWS as i32).unwrap_or(self.y);
        let wide = lines.iter().any(|(y, l)| self.left_at(*y) + self.f.width(l) > self.right_at(*y));
        if end > BOTTOM || wide {
            self.overflow = true;
            return false;
        }
        for (k, (y, l)) in lines.iter().enumerate() {
            let x = self.left_at(*y) + if k == 0 { 0 } else { indent };
            cv.text(self.f, x, *y, l);
        }
        self.y = lines.last().map(|l| l.0).unwrap_or(self.y) + self.pitch;
        true
    }
}

// --- Dual Strike's art ---------------------------------------------------------------

struct Art {
    /// The header strip's nine-patch tiles (info/000), tile 1..=10.
    strip: Vec<u8>,
    /// res_icon1_cg: 16x16 icons as four tiles each (0 the red star .. 4 the
    /// grey box are icons 10 to 14).
    icons: Vec<u8>,
    icon_pal: [u16; 16],
    /// res_icon0_cg: the headings' 16x16 pictures.
    heads: Vec<u8>,
    /// res_icon4_cg's digits.
    digits: Vec<u8>,
    digit_pal: [u16; 16],
    /// res_tpicon_lang_E's tiles and the button's palette.
    pad: Vec<u8>,
    back_pal: [u16; 16],
    /// The unit chart's pictures (arm9: 16 x 16 as four tiles each) and the five armies' palettes.
    units: Vec<u8>,
    unit_pals: Vec<[u16; 16]>,
}

/// Dual Strike's unit pictures for the chart (arm9) and the five armies' palettes before them.
const UNIT_ICONS: u32 = 0x0214_06F8;
const UNIT_ICON_COUNT: usize = 32;
const UNIT_PALETTES: u32 = 0x0214_05B8;

fn pal16(b: &[u8]) -> [u16; 16] {
    let mut p = [0u16; 16];
    for (k, c) in p.iter_mut().enumerate() {
        *c = u16::from_le_bytes([b[2 * k], b[2 * k + 1]]);
    }
    p
}

fn build_art() -> Option<Art> {
    let pack = crate::ds_pack::pack()?;
    let strip = crate::ds_art::lz10(pack.file("info/000")?)?;
    let icons = pack.file("icon/res_icon1_cg")?.to_vec();
    let cl = pack.file("icon/res_icon_cl")?;
    let digits = pack.file("icon/res_icon4_cg")?.to_vec();
    let pad = crate::ds_art::lz10(pack.file("ohashi/res_tpicon_lang_E")?)?;
    Some(Art {
        strip,
        icons,
        icon_pal: pal16(cl.get(32..64)?),
        heads: pack.file("icon/res_icon0_cg")?.to_vec(),
        digits,
        digit_pal: pal16(pack.arm9_at(0x0213_9288, 32)?),
        pad,
        back_pal: pal16(pack.arm9_at(0x0213_8C68, 32)?),
        units: pack.arm9_at(UNIT_ICONS, 128 * UNIT_ICON_COUNT)?.to_vec(),
        unit_pals: (0..5).map(|k| Some(pal16(pack.arm9_at(UNIT_PALETTES + 32 * k, 32)?))).collect::<Option<Vec<_>>>()?,
    })
}

fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(build_art).as_ref()
}

impl Art {
    fn tile(&self, t: usize) -> &[u8] {
        &self.strip[32 * t..32 * t + 32]
    }
    /// A 16x16 icon of res_icon1_cg.
    fn icon(&self, k: usize) -> &[u8] {
        &self.icons[128 * k..128 * k + 128]
    }
    fn head(&self, k: usize) -> &[u8] {
        &self.heads[128 * k..128 * k + 128]
    }
    fn digit(&self, c: char) -> &[u8] {
        let slot = match c {
            '0'..='9' => c as usize - '0' as usize,
            _ => 12,
        };
        &self.digits[0x1500 + 32 * slot..0x1500 + 32 * slot + 32]
    }
    /// One of the chart's unit pictures (`k` the picture's number in the table), 16 x 16 as four tiles.
    fn unit_icon(&self, k: usize) -> &[u8] {
        &self.units[128 * k..128 * k + 128]
    }
    /// The chart's gauge for a stat `px` pixels from the middle (a pixel is 5 %): 24 x 8, three tiles. The sheet holds
    /// one for each step, a run of blue (the stat is below 0: the white is what is left of the gauge), the plain white
    /// gauge, then a run of pink (above 0), 20 steps each way.
    fn bar(&self, px: i32) -> &[u8] {
        let first = BAR_FIRST + 3 * (BAR_ZERO + px.clamp(-BAR_STEPS, BAR_STEPS) as usize);
        &self.digits[32 * first..32 * first + 96]
    }
    /// The chart's "range" note for a change of `delta` cells (an arrow, the sign, the digit): 24 x 8, three tiles.
    fn range_note(&self, delta: i32) -> Option<Vec<u8>> {
        let (sign, digit) = match delta {
            -1 => (194, 197),
            -2 => (194, 195),
            1 => (198, 199),
            2 => (198, 201),
            3 => (198, 203),
            _ => return None,
        };
        let mut v = Vec::with_capacity(96);
        for t in [RANGE_ARROW, sign, digit] {
            v.extend_from_slice(self.digits.get(32 * t..32 * t + 32)?);
        }
        Some(v)
    }
}

/// res_icon4_cg's gauges: three tiles each from this tile, the one for no change at `BAR_ZERO` steps on.
const BAR_FIRST: usize = 522;
const BAR_ZERO: usize = 21;
const BAR_STEPS: i32 = 20;
const RANGE_ARROW: usize = 193;

/// Dual Strike's red star (Orange Star) .. grey box icons by country; the
/// grey box also stands for a tab nobody is on.
const ICON_FIRST: usize = 10;
const ICON_NONE: usize = 14;

// --- Composing the pages --------------------------------------------------------------

/// The BACK button's centre letter (Dual Strike's circle: fill `d`, edge `e`,
/// letter `7`), from column 10 and row 9 of the 32 x 32 button.
const B_LETTER: [&str; 12] = [
    "eeeeeeeeed", "e777777777", "e777777777", "e77dddd777", "e77dddde77", "e777eeee7d", "e77777777d", "e77dddd777", "e77dddde77",
    "e777eeee77", "e777777777", "e77777777d",
];

/// A small star (yellow, for the power rows and the tag partners).
const STAR: [&str; 7] = ["...e...", "..ece..", "eecccee", ".eccce.", ".eccce.", ".ec.ce.", ".e...e."];

fn hex(c: char) -> u8 {
    c.to_digit(16).unwrap_or(0) as u8
}

const COUNTER: Obstacle = Obstacle { x: 184, y: 32, w: 56, h: 8 };
const BACK_BOX: Obstacle = Obstacle { x: 208, y: 128, w: 32, h: 32 };

/// Dual Strike's strip, tabs, face, counter and BACK button: what every page
/// has. `page` is 0-based.
fn frame(cv: &mut Canvas, a: &Art, v: &View, page: usize) {
    // The strip: a nine-patch of tiles 1..=10 (28 columns, 4 rows).
    const LEFT_T: [usize; 4] = [1, 4, 4, 7];
    const MID_T: [usize; 4] = [2, 5, 10, 8];
    const RIGHT_T: [usize; 4] = [3, 6, 6, 9];
    for r in 0..4 {
        for c in 0..28 {
            let t = if c == 0 {
                LEFT_T[r]
            } else if c == 27 {
                RIGHT_T[r]
            } else {
                MID_T[r]
            };
            let tile = a.tile(t);
            for y in 0..8 {
                for x in 0..8 {
                    let v = (tile[4 * y as usize + x as usize / 2] >> (4 * (x & 1))) & 15;
                    // (the strip's own white: the wall shows around the strip, not through it)
                    cv.put(8 + 8 * c as i32 + x, 8 * r as i32 + y, UI, if v == 0 && (1..27).contains(&c) { 1 } else { v });
                }
            }
        }
    }
    // The tabs: the CO's country (selected, in Dual Strike's corner marks)
    // and the partner's (or the empty box).
    let icon = |c: Option<u8>| match c {
        Some(c) if c < 4 => ICON_FIRST + c as usize,
        _ => ICON_NONE,
    };
    cv.tiles(24, 8, a.icon(icon(v.tabs[0])), 16, 16, TAB);
    cv.tiles(64, 8, a.icon(icon(v.tabs[1])), 16, 16, TAB);
    for (cx, cy) in [(24 + 40 * v.tab as i32, 8)] {
        for k in 0..5 {
            for t in 0..2 {
                for (x, y) in [
                    (cx - 4 + k, cy - 4 + t),
                    (cx - 4 + t, cy - 4 + k),
                    (cx + 19 - k, cy - 4 + t),
                    (cx + 19 - t, cy - 4 + k),
                    (cx - 4 + k, cy + 19 - t),
                    (cx - 4 + t, cy + 19 - k),
                    (cx + 19 - k, cy + 19 - t),
                    (cx + 19 - t, cy + 19 - k),
                ] {
                    if !cv.taken(x, y) {
                        cv.put(x, y, UI, INK);
                    }
                }
            }
        }
    }
    // The CO's face, its top 16 rows.
    if let Some(p) = &v.portrait {
        cv.picture(176, 8, &p.mug, 48, 16, CO);
    }
    // The page counter.
    for (k, c) in format!("{}/{}", page + 1, PAGES).chars().enumerate() {
        let t = a.digit(c);
        cv.tiles(208 + 8 * k as i32, 32, t, 8, 8, DIGITS);
    }
    // More pages up and down: Dual Strike's arrows (red up, blue down).
    if page > 0 {
        arrow(cv, 190, 33, true);
    }
    if page + 1 < PAGES {
        arrow(cv, 197, 33, false);
    }
    back_button(cv, a);
}

/// A 7 x 6 triangle: red pointing up, blue down.
fn arrow(cv: &mut Canvas, x: i32, y: i32, up: bool) {
    for r in 0..4 {
        let w = if up { 1 + 2 * r } else { 7 - 2 * r };
        for c in 0..w {
            cv.put(x + 3 - w / 2 + c, y + 1 + r, UI, if up { 3 } else { 8 });
        }
        for c in [3 - w / 2 - 1, 3 - w / 2 + w] {
            cv.put(x + c, y + 1 + r, UI, INK);
        }
    }
}

fn back_button(cv: &mut Canvas, a: &Art) {
    let mut px = vec![0u8; 32 * 32];
    for k in 0..16usize {
        let t = if k < 4 { 96 + k } else { 16 + k };
        let tile = &a.pad[32 * t..32 * t + 32];
        for y in 0..8 {
            for x in 0..8 {
                px[32 * (8 * (k / 4) + y) + 8 * (k % 4) + x] = (tile[4 * y + x / 2] >> (4 * (x & 1))) & 15;
            }
        }
    }
    // The label tiles carry a sliver of their neighbours at the left.
    for y in 4..8 {
        for x in 0..2 {
            px[32 * y + x] = 0;
        }
    }
    // The centre: the circle's fill, then Dual Strike's B.
    for y in 9..21 {
        for x in 10..20 {
            px[32 * y + x] = 13;
        }
    }
    for (r, row) in B_LETTER.iter().enumerate() {
        for (c, ch) in row.chars().enumerate() {
            px[32 * (9 + r) + 10 + c] = hex(ch);
        }
    }
    cv.picture(208, 128, &px, 32, 32, BACK);
}

fn star(cv: &mut Canvas, x: i32, y: i32) {
    for (r, row) in STAR.iter().enumerate() {
        for (c, ch) in row.chars().enumerate() {
            match ch {
                'e' => cv.put(x + c as i32, y + r as i32, UI, INK),
                'c' => cv.put(x + c as i32, y + r as i32, UI, 12),
                _ => {}
            }
        }
    }
}

/// One way to lay a page out.
#[derive(Clone, Copy)]
struct Cfg {
    pitch: i32,
    /// The space before the day to day text, and before the Hit line (Dual Strike leaves a gap at both).
    gap: i32,
    lead: i32,
}

const CFGS: [Cfg; 4] = [Cfg { pitch: 14, gap: 8, lead: 10 }, Cfg { pitch: 14, gap: 4, lead: 5 }, Cfg { pitch: 13, gap: 2, lead: 0 }, Cfg { pitch: 12, gap: 0, lead: 0 }];

/// Page 1: the bio, Hit and Miss and the day to day text, over the page's full width.
fn description(f: &Font, a: &Art, v: &View, page: usize, cfg: Cfg, bio: &[String], d2d: &[String]) -> Option<Canvas> {
    let mut cv = Canvas::new();
    frame(&mut cv, a, v, page);
    // (Dual Strike's page has no picture of the CO in the text: it runs the full width under the strip, whose corner has the face)
    let obstacles = vec![COUNTER, BACK_BOX];
    let mut fl = Flow { f, obstacles, y: TEXT_TOP, pitch: cfg.pitch, overflow: false };
    for (k, p) in bio.iter().enumerate() {
        if k == 1 {
            fl.y += cfg.lead;
        }
        if !fl.para(&mut cv, p, 0) {
            return None;
        }
    }
    fl.y += cfg.gap;
    for p in d2d {
        if !fl.para(&mut cv, p, 0) {
            return None;
        }
    }
    Some(cv)
}

/// Shorter wordings, tried in turn while a text is too long.
const SHORTER: [(&str, &str); 9] = [
    ("Adept at making quick decisions, he stores up energy", "He stores up energy"),
    (" at a faster rate than", " faster than"),
    (" is greatly increased", " rises greatly"),
    (" is increased", " rises"),
    (" are increased", " rise"),
    ("Damaged units must skip their next turn.", "Units hit skip a turn."),
    (" HP of damage", " HP damage"),
    (" increased on plains", " up on plains"),
    ("Firepower of all units", "All units' firepower"),
];

/// The last sentence of a paragraph dropped (`false` if it has one only).
fn drop_sentence(p: &mut String) -> bool {
    let body = p.trim_end_matches(['.', '!', '?']);
    match body.rfind(['.', '!', '?']) {
        Some(i) => {
            p.truncate(i + 1);
            true
        }
        None => false,
    }
}

fn page_description(f: &Font, a: &Art, v: &View) -> Canvas {
    let mut bio = paragraphs(&v.bio);
    let mut d2d = paragraphs(&v.d2d);
    let mut last = None;
    for step in 0..=SHORTER.len() + 6 {
        for cfg in CFGS {
            if let Some(cv) = description(f, a, v, 0, cfg, &bio, &d2d) {
                return cv;
            }
        }
        // Still too long: a shorter wording, then the last sentences of the
        // day to day text, then of the bio's first paragraph.
        if step < SHORTER.len() {
            for p in bio.iter_mut().chain(d2d.iter_mut()) {
                *p = p.replace(SHORTER[step].0, SHORTER[step].1);
            }
        } else if let Some(p) = d2d.last_mut().filter(|_| step < SHORTER.len() + 3) {
            drop_sentence(p);
        } else if let Some(p) = bio.first_mut() {
            drop_sentence(p);
        }
        last = Some(step);
    }
    let _ = last;
    FALLBACKS.fetch_add(1, Ordering::Relaxed);
    let mut cv = Canvas::new();
    frame(&mut cv, a, v, 0);
    cv
}

/// A heading: Dual Strike's picture and the text beside it; `y` on a cell boundary. Returns the y the text below starts at.
fn heading(cv: &mut Canvas, f: &Font, a: &Art, icon: usize, y: i32, text: &str) -> i32 {
    cv.tiles(HEAD_X, y, a.head(icon), 16, 16, HEAD);
    cv.text(f, HEAD_X + 17, y + 1, text);
    y + 18
}

/// Page 2: the skills the army has on, then the tag partners (one a line, or in two columns when
/// one column leaves them no room: Sturm has seven).
fn page_skills(f: &Font, a: &Art, v: &View) -> Canvas {
    for cols in [1usize, 2] {
        if cols == 2 && v.partners.len() < 2 {
            break;
        }
        for pitch in [14, 13] {
            for with_desc in [true, false] {
                let mut cv = Canvas::new();
                frame(&mut cv, a, v, 1);
                let mut fl = Flow { f, obstacles: vec![COUNTER, BACK_BOX], y: 32, pitch, overflow: false };
                fl.y = heading(&mut cv, f, a, ICON_SKILLS, 32, "Existing skills");
                let mut ok = true;
                if v.skills.is_empty() {
                    ok &= fl.para(&mut cv, "None set.", 0);
                }
                for (name, desc) in &v.skills {
                    ok &= fl.para(&mut cv, name, 0);
                    if with_desc && !desc.is_empty() {
                        ok &= fl.para(&mut cv, desc, 6);
                    }
                }
                if !v.partners.is_empty() {
                    fl.y += 3;
                    ok &= fl.para(&mut cv, "TAG partners", 0);
                    let rows = v.partners.len().div_ceil(cols);
                    let span = (RIGHT - LEFT) / cols as i32;
                    for (i, (name, stars)) in v.partners.iter().enumerate() {
                        let (col, row) = ((i / rows) as i32, (i % rows) as i32);
                        let y = fl.y + row * pitch;
                        let x0 = LEFT + 6 + span * col;
                        let limit = if col as usize + 1 == cols { RIGHT } else { LEFT + span * (col + 1) - 3 };
                        let w = f.width(name) + 5 + 9 * *stars as i32;
                        if y + INK_ROWS as i32 > BOTTOM || x0 + w > limit {
                            ok = false;
                            break;
                        }
                        let x = cv.text(f, x0, y, name);
                        for s in 0..*stars as i32 {
                            star(&mut cv, x + 5 + 9 * s, y + 3);
                        }
                    }
                    fl.y += rows as i32 * pitch;
                }
                if ok {
                    return cv;
                }
            }
        }
    }
    FALLBACKS.fetch_add(1, Ordering::Relaxed);
    let mut cv = Canvas::new();
    frame(&mut cv, a, v, 1);
    cv
}

/// Page 3: the CO Power and the Super Power, each with its name and text.
fn page_powers(f: &Font, a: &Art, v: &View) -> Canvas {
    let blocks: [(&str, &[u8], u8); 2] = [(&v.cop_name, &v.cop, 1), (&v.scop_name, &v.scop, 2)];
    let mut cops: Vec<Vec<String>> = blocks.iter().map(|b| paragraphs(b.1)).collect();
    for step in 0..=SHORTER.len() + 8 {
        for (pitch, gap) in [(14, 4), (14, 2), (13, 2), (13, 0), (12, 0)] {
            let mut cv = Canvas::new();
            frame(&mut cv, a, v, 2);
            let mut fl = Flow { f, obstacles: vec![COUNTER, BACK_BOX], y: 32, pitch, overflow: false };
            let mut ok = true;
            for (k, (name, _, stars)) in blocks.iter().enumerate() {
                if !name.is_empty() {
                    // (a heading's picture sits on a cell boundary)
                    let y = (fl.y + 7) / 8 * 8;
                    fl.y = heading(&mut cv, f, a, if *stars == 1 { ICON_COP } else { ICON_SCOP }, y, name);
                }
                for p in &cops[k] {
                    ok &= fl.para(&mut cv, p, 0);
                }
                fl.y += gap;
            }
            if ok {
                return cv;
            }
        }
        if step < SHORTER.len() {
            for ps in cops.iter_mut() {
                for p in ps.iter_mut() {
                    *p = p.replace(SHORTER[step].0, SHORTER[step].1);
                }
            }
        } else {
            let k = step % 2;
            if let Some(p) = cops[k].last_mut() {
                drop_sentence(p);
            }
        }
    }
    FALLBACKS.fetch_add(1, Ordering::Relaxed);
    let mut cv = Canvas::new();
    frame(&mut cv, a, v, 2);
    cv
}

/// Page `page` (0..3) of the CO page for `v`; `None` without the pack.
/// The INFO button (Dual Strike's, res_tpicon_lang_E's first 16 tiles) above BACK.
const INFO_BOX: Obstacle = Obstacle { x: 208, y: 96, w: 32, h: 32 };

fn info_button(cv: &mut Canvas, a: &Art) {
    cv.tiles(INFO_BOX.x, INFO_BOX.y, &a.pad[..32 * 16], 32, 32, BACK);
}

/// Page 4: the unit chart, Dual Strike's: each unit's picture with one thin gauge beside it (the CO's change to the unit's
/// attack; a unit with no weapon has none) and, under the gauge, a note when the unit's range changes. Rows of four and
/// five, as `CHART_ROWS`.
fn page_chart(_f: &Font, a: &Art, v: &View) -> Canvas {
    let mut cv = Canvas::new();
    frame(&mut cv, a, v, 3);
    info_button(&mut cv, a);
    let mut units = v.chart.iter();
    for (row, n) in CHART_ROWS.iter().enumerate() {
        for col in 0..*n {
            let Some(u) = units.next() else { break };
            let (x, y) = (8 + 48 * col as i32, 40 + 20 * row as i32);
            cv.tiles(x, y, a.unit_icon(u.icon), 16, 16, UNIT);
            if let Some(px) = u.attack {
                cv.tiles(x + 16, y, a.bar(px), 24, 8, DIGITS);
            }
            if let Some(note) = a.range_note(u.range) {
                cv.tiles(x + 16, y + 8, &note, 24, 8, DIGITS);
            }
        }
    }
    cv
}

pub fn compose(v: &View, page: usize) -> Option<Canvas> {
    let (f, a) = (font()?, art()?);
    let mut cv = match page {
        0 => page_description(f, a, v),
        1 => page_skills(f, a, v),
        2 => page_powers(f, a, v),
        _ => page_chart(f, a, v),
    };
    cv.pals = bank_palettes(a, v);
    Some(cv)
}

/// The canvas as RGBA (for previews).
pub fn rgba(cv: &Canvas) -> Vec<u8> {
    let pals = &cv.pals;
    let mut out = Vec::with_capacity(240 * 160 * 4);
    for y in 0..160 {
        for x in 0..240 {
            let b = cv.bank[30 * (y / 8) + x / 8] as usize;
            let i = (cv.px[240 * y + x] & 15) as usize;
            let c = match crate::ds_co_wall::wall() {
                Some(w) if i == 0 && y >= 32 => w.pix[240 * y + x],
                _ => pals[b][i],
            };
            out.extend_from_slice(&[((c & 31) * 255 / 31) as u8, (((c >> 5) & 31) * 255 / 31) as u8, (((c >> 10) & 31) * 255 / 31) as u8, 255]);
        }
    }
    out
}

fn bank_palettes(a: &Art, v: &View) -> Vec<[u16; 16]> {
    let mut p = vec![[WHITE; 16]; 8];
    p[UI as usize] = UI_PALETTE;
    if let Some(po) = &v.portrait {
        p[CO as usize] = po.pal;
    }
    p[TAB as usize] = a.icon_pal;
    p[DIGITS as usize] = a.digit_pal;
    p[BACK as usize] = a.back_pal;
    p[UNIT as usize] = a.unit_pals.get(v.colour).copied().unwrap_or(a.unit_pals[0]);
    p[HEAD as usize] = HEAD_PALETTE;
    for b in p.iter_mut().skip(1) {
        b[0] = WHITE;
    }
    p
}

// --- Getting the page's data -----------------------------------------------------------

/// AW2's text table (`0x08610A38 + 4 * id` points at the string).
const TEXT_TABLE: u32 = 0x0861_0A38;
/// Sturm's texts in AW2's own table: bio, day to day, CO Power, Super Power;
/// his Super Power's name.
const STURM_TEXTS: [u32; 4] = [2461, 2462, 2463, 2464];
const STURM_SCOP_NAME: u32 = 2311;

fn aw2_text(core: &Core, id: u32) -> Vec<u8> {
    let p = core.raw_read_32(TEXT_TABLE + 4 * id, -1);
    let mut out = Vec::new();
    if (0x0800_0000..0x0A00_0000).contains(&p) {
        for k in 0..400 {
            let c = core.raw_read_8(p + k, -1);
            if c == 0 {
                break;
            }
            out.push(if c == b'\r' { b' ' } else { c });
        }
    }
    out
}

/// A body from Dual Strike's two files (the six sprites of AW2's page).
fn body_of(top: &[u8], bottom: &[u8]) -> Vec<u8> {
    let mut px = vec![0u8; 128 * 160];
    let mut sprite = |data: &[u8], w: usize, h: usize, x0: usize, y0: usize| {
        let tw = w / 8;
        for k in 0..tw * (h / 8) {
            let Some(t) = data.get(32 * k..32 * k + 32) else { return };
            for y in 0..8 {
                for x in 0..8 {
                    px[128 * (y0 + 8 * (k / tw) + y) + x0 + 8 * (k % tw) + x] = (t[4 * y + x / 2] >> (4 * (x & 1))) & 15;
                }
            }
        }
    };
    sprite(top.get(..2048).unwrap_or(&[]), 64, 64, 0, 0);
    sprite(top.get(2048..4096).unwrap_or(&[]), 64, 64, 64, 0);
    sprite(bottom.get(..2048).unwrap_or(&[]), 64, 64, 0, 64);
    sprite(bottom.get(2048..4096).unwrap_or(&[]), 64, 64, 64, 64);
    sprite(bottom.get(4096..5120).unwrap_or(&[]), 64, 32, 0, 128);
    sprite(bottom.get(5120..6144).unwrap_or(&[]), 64, 32, 64, 128);
    px
}

fn portrait_of(a: &crate::ds_co_art::CoArt) -> Portrait {
    let mut mug = vec![0u8; 48 * 16];
    // The strip shows the face's third and fourth tile rows (the eyes).
    for k in 0..12 {
        let Some(t) = a.face[0].get(32 * (12 + k)..32 * (12 + k) + 32) else { break };
        for y in 0..8 {
            for x in 0..8 {
                mug[48 * (8 * (k / 6) + y) + 8 * (k % 6) + x] = (t[4 * y + x / 2] >> (4 * (x & 1))) & 15;
            }
        }
    }
    // The face's own background colour (its corner) is the strip's white.
    let bg = a.face[0].first().map(|b| b & 15).unwrap_or(0);
    if bg != 0 {
        for v in mug.iter_mut().filter(|v| **v == bg) {
            *v = 0;
        }
    }
    Portrait { body: body_of(&a.body_top, &a.body_bottom), mug, pal: pal16(&a.palette) }
}

/// The CO's pictures as the game's presentation table holds them (Sturm's,
/// Crumb's, Clone Andy's: no Dual Strike twin).
fn game_art(core: &Core, co: u8) -> Option<crate::ds_co_art::CoArt> {
    use crate::ds_art::lz10;
    let table = core.raw_read_32(PRESENTATION_POOL, -1);
    if !(0x0800_0000..0x0A00_0000).contains(&table) {
        return None;
    }
    let row = table + PRESENTATION_ROW * co as u32;
    let rom = |a: u32, n: usize| {
        let mut b = vec![0u8; n];
        core.raw_read_range(a, -1, &mut b);
        b
    };
    let word = |a: u32| core.raw_read_32(a, -1);
    let lz = |a: u32| lz10(&rom(a, 0x4000));
    let body = word(row);
    Some(crate::ds_co_art::CoArt {
        face: [lz(word(row + 0x0C))?, lz(word(row + 0x10))?, lz(word(row + 0x14))?],
        mini: Vec::new(),
        hud: Vec::new(),
        body_top: lz(word(body))?,
        body_bottom: lz(word(body + 4))?,
        name: Vec::new(),
        palette: rom(word(row + 8), 0x100),
    })
}

fn string(t: Option<Vec<u8>>) -> String {
    plain(&t.unwrap_or_default())
}

/// A CO's page data. `core` gives Sturm's text (AW2's own), the game's
/// pictures for the COs with no Dual Strike twin, and the army's skills and
/// partners; without it (a preview) Dual Strike's COs only.
pub fn view_for(core: Option<&Core>, army: Option<u32>, co: u8) -> View {
    use crate::co_new::{self, CLONE_ANDY, CRUMB};
    let ds = crate::co_roster::ds_co(co);
    let name = co_new::ds_name(co).map(|n| plain(&n)).unwrap_or_else(|| if co == crate::sturm_pairs::STURM { "Sturm".into() } else { format!("CO {co}") });
    let text = |off: u32| ds.and_then(|d| co_new::ds_text(co_new::record_ref(d, off))).unwrap_or_default();
    let (mut bio, mut d2d, mut cop, mut scop, mut cop_name, mut scop_name) =
        (text(0x04), text(0x08), text(0x0C), text(0x10), string(Some(text(0x120))), string(Some(text(0x1A0))));
    if co == CRUMB {
        bio = crate::crumb::BIO.to_vec();
        d2d = crate::crumb::DAY_TO_DAY.to_vec();
        cop = crate::crumb::COP_PAGE.to_vec();
        scop = crate::crumb::SCOP_PAGE.to_vec();
        cop_name = string(Some(crate::crumb::COP_NAME.to_vec()));
        scop_name = string(Some(crate::crumb::SCOP_NAME.to_vec()));
    } else if co == CLONE_ANDY {
        bio = co_new::CLONE_ANDY_BIO.to_vec();
    } else if co == crate::sturm_pairs::STURM {
        if let Some(c) = core {
            bio = aw2_text(c, STURM_TEXTS[0]);
            d2d = aw2_text(c, STURM_TEXTS[1]);
            cop = aw2_text(c, STURM_TEXTS[2]);
            scop = aw2_text(c, STURM_TEXTS[3]);
            scop_name = plain(&aw2_text(c, STURM_SCOP_NAME));
            cop_name.clear();
        }
    }
    if cop.is_empty() && cop_name.is_empty() {
        cop = format!("{name} has no CO Power. He saves all his energy for his Super CO Power.").into_bytes();
    }
    let mut skills = Vec::new();
    let mut partners = Vec::new();
    if let (Some(c), Some(army)) = (core, army) {
        for id in crate::co_skills::ids() {
            if crate::co_skills::has(c, army, id) {
                if let Some((_, n, d)) = crate::co_skills::info(id) {
                    skills.push((plain(&n), plain(&d)));
                }
            }
        }
        for (p, stars) in crate::tag_extras::partners_of(c, co) {
            let pn = co_new::ds_name(p).map(|n| plain(&n)).unwrap_or_else(|| if p == crate::sturm_pairs::STURM { "Sturm".into() } else { String::new() });
            if !pn.is_empty() {
                partners.push((pn, stars));
            }
        }
    }
    let art = match ds {
        Some(d) if !co_new::is_own(co) || co == CLONE_ANDY => crate::ds_co_art::co_art(d),
        _ => core.and_then(|c| game_art(c, co)),
    };
    // (the army's colour, and the power the page's CO is in: a partner's page shows its day to day numbers)
    let (mut colour, mut mode) = (0usize, 0u8);
    if let (Some(c), Some(army)) = (core, army) {
        colour = (c.raw_read_8(crate::five::players(c) + 0x3C * army + 0x1A, -1).clamp(1, 5) - 1) as usize;
        let (active, m) = crate::co_roster::army_co(c, army);
        if active == co {
            mode = m;
        }
    }
    let own = Some(crate::custom_campaign::country(co));
    let mut tabs = [own, None];
    let mut tab = 0;
    if let (Some(c), Some(army)) = (core, army) {
        if let Some(p) = crate::tag::partner(c, army) {
            tabs[1] = Some(crate::custom_campaign::country(p));
            // On the partner's page the army's two COs are swapped: the
            // tabs stay in the pair's order.
            if c.raw_read_8(crate::tag_extras::STATE + 0x10, -1) == 1 {
                tabs = [Some(crate::custom_campaign::country(p)), own];
                tab = 1;
            }
        }
    }
    View {
        name,
        tabs,
        tab,
        bio,
        d2d,
        cop_name,
        cop,
        scop_name,
        scop,
        skills,
        partners,
        portrait: art.as_ref().map(portrait_of),
        colour,
        chart: chart_for(co, mode),
    }
}

// --- On the screen --------------------------------------------------------------------

const BG0CNT: u32 = 0x0400_0008;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const VRAM: u32 = 0x0600_0000;
/// BG0's tiles go up to the screen block 14 (0x7000); the page itself uses
/// the first 512 (0x4000 bytes).
const CHARS_END: u32 = 0x7000;
const SPARE_FROM: u32 = 0x4000;
const MAX_TILES: usize = (CHARS_END / 32) as usize;

/// Colour 0 of a tile is transparent on the hardware (and shows what the
/// backdrop is, which the game manages): every bank gets a white colour of
/// its own for the clear pixels, the UI's 1, another bank's last index its
/// pictures leave unused; a picture that uses all fifteen gives up the
/// colour it uses least for its nearest (the table maps the indices).
fn white_indices(cv: &Canvas) -> ([u8; 8], [[u8; 16]; 8]) {
    let mut count = [[0usize; 16]; 8];
    for y in 0..160 {
        for x in 0..240 {
            count[cv.bank[30 * (y / 8) + x / 8] as usize][(cv.px[240 * y + x] & 15) as usize] += 1;
        }
    }
    let rgb = |c: u16| ((c & 31) as i32, ((c >> 5) & 31) as i32, ((c >> 10) & 31) as i32);
    let mut w = [0u8; 8];
    let mut remap = [[0u8; 16]; 8];
    for b in 0..8 {
        for i in 0..16 {
            remap[b][i] = i as u8;
        }
        w[b] = if b == UI as usize {
            1
        } else if let Some(i) = (1..16).rev().find(|&i| count[b][i] == 0) {
            i as u8
        } else {
            let least = (1..16).min_by_key(|&i| count[b][i]).unwrap_or(15);
            let (lr, lg, lb) = rgb(cv.pals[b][least]);
            let near = (1..16)
                .filter(|&i| i != least)
                .min_by_key(|&i| {
                    let (r, g, bl) = rgb(cv.pals[b][i]);
                    (r - lr).pow(2) + (g - lg).pow(2) + (bl - lb).pow(2)
                })
                .unwrap_or(1);
            remap[b][least] = near as u8;
            least as u8
        };
    }
    (w, remap)
}

/// The canvas as BG0's tiles (identical ones shared), its 32 x 32 tilemap
/// and the eight palette banks.
fn layer_of(cv: &Canvas) -> (Vec<u8>, Vec<u8>, Vec<u8>) {
    let (white, remap) = white_indices(cv);
    let mut tiles: Vec<[u8; 32]> = Vec::new();
    let mut index = std::collections::HashMap::new();
    let mut map = vec![0u8; 0x800];
    for ty in 0..20 {
        for tx in 0..30 {
            let bank = cv.bank[30 * ty + tx] as usize;
            let mut t = [0u8; 32];
            for y in 0..8 {
                for x in 0..8 {
                    // A clear pixel shows the wall behind the page (BG2), except in the strip at the top, which has its own white.
                    let v = match cv.px[240 * (8 * ty + y) + 8 * tx + x] & 15 {
                        0 if ty < 4 || crate::ds_co_wall::wall().is_none() => white[bank],
                        0 => 0,
                        v => remap[bank][v as usize],
                    };
                    t[4 * y + x / 2] |= v << (4 * (x & 1));
                }
            }
            let k = match index.get(&t) {
                Some(&k) => k,
                None if tiles.len() < MAX_TILES => {
                    let k = tiles.len() as u16;
                    tiles.push(t);
                    index.insert(t, k);
                    k
                }
                None => 0,
            };
            let e = k | (bank as u16) << 12;
            map[2 * (32 * ty + tx)..2 * (32 * ty + tx) + 2].copy_from_slice(&e.to_le_bytes());
        }
    }
    let mut pals = cv.pals.clone();
    for (b, p) in pals.iter_mut().enumerate() {
        p[white[b] as usize] = WHITE;
        p[0] = WHITE;
    }
    let pal = pals.iter().flat_map(|p| p.iter().flat_map(|c| c.to_le_bytes())).collect();
    if tiles.is_empty() {
        tiles.push([0u8; 32]);
    }
    (tiles.concat(), map, pal)
}

/// How many distinct tiles a canvas needs (the layer holds [`MAX_TILES`]).
pub fn tile_count(cv: &Canvas) -> usize {
    layer_of(cv).0.len() / 32
}

#[allow(dead_code)]
fn tile_count_raw(cv: &Canvas) -> usize {
    let mut set = std::collections::HashSet::new();
    for ty in 0..20 {
        for tx in 0..30 {
            let mut t = [0u8; 32];
            for y in 0..8 {
                for x in 0..8 {
                    t[4 * y + x / 2] |= (cv.px[240 * (8 * ty + y) + 8 * tx + x] & 15) << (4 * (x & 1));
                }
            }
            set.insert(t);
        }
    }
    set.len()
}

fn bg0(core: &Core) -> Option<(u32, u32)> {
    let c = core.raw_read_16(BG0CNT, -1) as u32;
    if (c >> 2) & 3 != 0 {
        return None;
    }
    Some((VRAM, VRAM + 0x800 * ((c >> 8) & 31)))
}

fn write_if_changed(core: &mut Core, at: u32, b: &[u8]) {
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != b {
        core.raw_write_range(at, -1, b);
    }
}

fn hash(parts: &[&[u8]]) -> u64 {
    let mut h = 0xCBF2_9CE4_8422_2325u64;
    for p in parts {
        for &b in *p {
            h = (h ^ b as u64).wrapping_mul(0x100_0000_01B3);
        }
        h = (h ^ 0xFF).wrapping_mul(0x100_0000_01B3);
    }
    h
}

fn draw(core: &mut Core, st: &mut State, army: u32, co: u8) {
    let Some((chars, map)) = bg0(core) else { return };
    // What the page shows only changes with the CO, the army's skills and
    // partners, and the page: the built layer is kept until one does.
    let mut ids = Vec::new();
    for id in crate::co_skills::ids() {
        if crate::co_skills::has(core, army, id) {
            ids.push(id);
        }
    }
    let partner = crate::tag_extras::partners_of(core, co).iter().flat_map(|p| [p.0, p.1]).collect::<Vec<u8>>();
    let pair = [
        crate::tag::partner(core, army).unwrap_or(255),
        core.raw_read_8(crate::tag_extras::STATE + 0x10, -1),
        army as u8,
    ];
    let key = hash(&[&[co, st.page as u8], &ids, &partner, &pair]);
    if st.built.as_ref().map(|b| b.0) != Some(key) {
        let view = view_for(Some(core), Some(army), co);
        let before = fallbacks();
        let Some(cv) = compose(&view, st.page) else { return };
        // (a test's view of what the page lists: `TANGOAW2_CO_PAGE_LOG` names a file it appends to)
        if let Ok(path) = std::env::var("TANGOAW2_CO_PAGE_LOG") {
            use std::io::Write;
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
                let partners: Vec<String> = view.partners.iter().map(|(n, s)| format!("{n}={s}")).collect();
                let _ = writeln!(f, "ds_co_page: co {co} page {} fitted {} partners {}", st.page + 1, fallbacks() == before, partners.join(","));
            }
        }
        let (tiles, tilemap, pal) = layer_of(&cv);
        st.built = Some((key, tiles, tilemap, pal));
    }
    let Some((_, tiles, tilemap, pal)) = &st.built else { return };
    write_if_changed(core, chars, tiles);
    write_if_changed(core, map, tilemap);
    write_if_changed(core, PAL_BUFFER, pal);
    write_if_changed(core, PAL_RAM, pal);
    draw_wall(core, st);
}

const BG2CNT: u32 = 0x0400_000C;

/// The wall ([`crate::ds_co_wall`]) on BG2, under the page: its tiles and map where the game's BG2 has its own (hidden
/// while the page is up; what was there is kept and put back), its palette banks after the page's eight.
fn draw_wall(core: &mut Core, st: &mut State) {
    let Some(w) = crate::ds_co_wall::wall() else { return };
    let c = core.raw_read_16(BG2CNT, -1) as u32;
    // (a 4bpp, 256 x 256 text layer: the game's page layer)
    if c & 0x80 != 0 || c >> 14 != 0 {
        return;
    }
    let chars = VRAM + 0x4000 * ((c >> 2) & 3);
    let map = VRAM + 0x800 * ((c >> 8) & 31);
    if st.wall_saved.is_empty() {
        for (at, len) in [(chars, w.chars.len()), (map, w.map.len())] {
            let mut b = vec![0u8; len];
            core.raw_read_range(at, -1, &mut b);
            st.wall_saved.push((at, b));
        }
    }
    write_if_changed(core, chars, &w.chars);
    write_if_changed(core, map, &w.map);
    write_if_changed(core, PAL_BUFFER + 0x100, &w.pal);
    write_if_changed(core, PAL_RAM + 0x100, &w.pal);
}

const DISP_CT: u32 = 0x0300_30CC;
const LAYERS: u16 = 0x1F00;
const BG0_ONLY: u16 = 0x0100;
const BG0_BG2: u16 = 0x0500;

/// The layers the page shows: BG0 (the page), and BG2 (the wall) when there is one.
fn shown() -> u16 {
    if crate::ds_co_wall::wall().is_some() {
        BG0_BG2
    } else {
        BG0_ONLY
    }
}

/// Only BG0 shows (the page's other layers and the sprites are covered).
fn hide_layers(core: &mut Core, st: &mut State) {
    let d = core.raw_read_16(DISP_CT, -1);
    if st.layers.is_none() {
        st.layers = Some(d & LAYERS);
    }
    if d & LAYERS != shown() {
        core.raw_write_16(DISP_CT, -1, (d & !LAYERS) | shown());
    }
}

/// The layers back as the game had them (unless the game has set its own
/// since: the page closing).
fn show_layers(core: &mut Core, st: &mut State) {
    if let Some(l) = st.layers.take() {
        let d = core.raw_read_16(DISP_CT, -1);
        if d & LAYERS == shown() {
            core.raw_write_16(DISP_CT, -1, (d & !LAYERS) | l);
        }
    }
}

/// The game's BG palettes back (the pages here drew their own over them).
fn restore_palette(core: &mut Core, st: &mut State) {
    if st.pal.is_empty() {
        return;
    }
    for base in [PAL_BUFFER, PAL_RAM] {
        write_if_changed(core, base, &st.pal);
    }
}

/// What the layer covered beyond the page's own tiles, put back.
fn close(core: &mut Core, st: &mut State) {
    show_layers(core, st);
    restore_palette(core, st);
    if st.open && !st.saved.is_empty() {
        let saved = std::mem::take(&mut st.saved);
        core.raw_write_range(VRAM + SPARE_FROM, -1, &saved);
    }
    for (at, b) in std::mem::take(&mut st.wall_saved) {
        core.raw_write_range(at, -1, &b);
    }
    st.open = false;
    st.built = None;
}

/// Every frame (before the game reads the pad): while the game's CO page is
/// up (and `on`: Dual Strike graphics, offline), draw Dual Strike's. DOWN and
/// UP turn this page's pages; every other button is the game's own. Returns
/// the keys the game gets.
pub fn tick(core: &mut Core, on: bool, keys: u32, prev: u32) -> u32 {
    let mut st = match STATE.lock() {
        Ok(s) => s,
        Err(e) => e.into_inner(),
    };
    let proc = if on && crate::wasteland::ds_graphics(core) { page_proc(core) } else { None };
    let Some(proc) = proc else {
        if st.open {
            close(core, &mut st);
        }
        return keys;
    };
    if !st.open {
        st.open = true;
        st.page = 0;
        let mut b = vec![0u8; (CHARS_END - SPARE_FROM) as usize];
        core.raw_read_range(VRAM + SPARE_FROM, -1, &mut b);
        st.saved = b;
        st.built = None;
        let mut p = vec![0u8; 0x200];
        core.raw_read_range(PAL_BUFFER, -1, &mut p);
        st.pal = p;
    }
    let army = core.raw_read_16(proc + PROC_ARMY, -1) as u32;
    if !(1..=5).contains(&army) {
        return keys;
    }
    let co = crate::tag::army_co_of(core, army);
    let pressed = keys & !prev;
    let mut out = keys;
    if pressed & KEY_DOWN != 0 && st.page + 1 < PAGES {
        st.page += 1;
    } else if pressed & KEY_UP != 0 && st.page > 0 {
        st.page -= 1;
    }
    // (the game stays on its Super Power's page under these: DOWN and UP are this module's)
    out &= !(KEY_DOWN | KEY_UP);
    core.raw_write_32(GAME_PAGE, -1, GAME_SCOP_PAGE);
    hide_layers(core, &mut st);
    draw(core, &mut st, army, co);
    out
}

/// At the VBlank sprite flush (crate::branding::flush, last): the game's own
/// sprites are hidden while Dual Strike's page is up (the page is all layer).
pub fn flush(core: &mut Core, start: u32, at: u32, _end: u32) -> u32 {
    if is_open() {
        let mut p = start;
        while p < at {
            let a0 = core.raw_read_16(p, -1);
            core.raw_write_16(p, -1, (a0 & !0x0300) | 0x0200);
            p += 8;
        }
    }
    at
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bios_split_before_hit_and_miss() {
        let p = paragraphs(b"A young CO\rwho tanks.\r\rHit: Clubbin'\rMiss: Easy listening\r");
        assert_eq!(p, ["A young CO who tanks.", "Hit: Clubbin'", "Miss: Easy listening"]);
        // AW2's "Hits:" too, and plain text stays one paragraph.
        assert_eq!(paragraphs(b"Likes it.\rHits: Ramen\rMiss: Fondue").len(), 3);
        assert_eq!(paragraphs(b"Restores 2 HP\rto all units."), ["Restores 2 HP to all units."]);
    }

    #[test]
    fn sentences_drop_from_the_end() {
        let mut p = "One. Two! Three.".to_string();
        assert!(drop_sentence(&mut p));
        assert_eq!(p, "One. Two!");
        let mut q = "Only one.".to_string();
        assert!(!drop_sentence(&mut q));
    }

    #[test]
    fn the_layer_fits_its_room() {
        // BG0's tiles stop at the screen block (0x7000); the page's own
        // first 512 are what the game's page uses.
        assert_eq!(CHARS_END, 0x7000);
        assert!(SPARE_FROM < CHARS_END && MAX_TILES == 896);
        // Obstacles are on cell boundaries (a cell has one palette bank).
        for o in [COUNTER, BACK_BOX] {
            assert!(o.x % 8 == 0 && o.y % 8 == 0 && o.w % 8 == 0 && o.h % 8 == 0);
        }
        // The chart: Dual Strike's rows (four, five, five, four, four, four), within the screen and clear of INFO and BACK.
        assert_eq!(CHART_ROWS.iter().sum::<usize>(), CHART_UNITS.len());
        for (row, n) in CHART_ROWS.iter().enumerate() {
            let y = 40 + 20 * row as i32;
            assert!(y + 16 <= 160);
            for col in 0..*n as i32 {
                let (x0, x1) = (8 + 48 * col, 8 + 48 * col + 40);
                for o in [INFO_BOX, BACK_BOX] {
                    assert!(x1 <= o.x || x0 >= o.x + o.w || y + 16 <= o.y || y >= o.y + o.h, "row {row} column {col} under a button");
                }
            }
        }
    }

    /// With `TANGOAW2_DS_ROM`: the unit chart's gauges are the CO's stats in steps of 5 %: Max's direct vehicles
    /// +20 % attack (4 steps), his indirect ones' range -1; Grit's direct ones -20 %, his indirect +20 % and +1 range;
    /// Andy's nothing. And the wall behind the pages builds within BG2's tiles.
    #[test]
    #[ignore]
    fn the_chart_shows_the_cos_stats() {
        crate::ds_pack::pack().expect("TANGOAW2_DS_ROM");
        let unit = |c: &[ChartUnit], icon: usize| *c.iter().find(|u| u.icon == icon).unwrap();
        // (icons: 24 Infantry, 1 Tank, 4 Artillery, 3 APC)
        let max = chart_for(2, 0);
        assert_eq!((unit(&max, 24).attack, unit(&max, 1).attack, unit(&max, 4).range), (Some(0), Some(4), -1));
        assert_eq!(unit(&max, 3).attack, None, "an APC has no attack gauge");
        let grit = chart_for(5, 0);
        assert_eq!((unit(&grit, 1).attack, unit(&grit, 4).attack, unit(&grit, 4).range), (Some(-4), Some(4), 1));
        let andy = chart_for(1, 0);
        assert!(andy.iter().all(|u| u.attack.unwrap_or(0) == 0 && u.defence == 0 && u.range == 0));
        let wall = crate::ds_co_wall::wall().expect("the wall");
        assert!(wall.chars.len() / 32 <= crate::ds_co_wall::MAX_TILES);
    }

    /// With `TANGOAW2_DS_ROM`: Dual Strike's font reads (A is 5 wide, I and i
    /// 1), and every CO's three pages fit a layout within the layer's tiles
    /// (none is left with the strip only). `cargo test -p
    /// tango-gamesupport-aw2 ds_co_page -- --ignored`.
    #[test]
    #[ignore]
    fn every_co_page_fits() {
        crate::ds_pack::pack().expect("TANGOAW2_DS_ROM");
        let f = font().expect("font");
        assert_eq!((f.w[b'A' as usize], f.w[b'I' as usize], f.w[b'i' as usize], f.w[b' ' as usize]), (5, 1, 1, 2));
        assert_eq!(f.width("A"), 5);
        let before = fallbacks();
        for co in (0..19u8).chain(72..81) {
            let v = view_for(None, None, co);
            for page in 0..3 {
                let cv = compose(&v, page).unwrap();
                assert!(tile_count(&cv) <= MAX_TILES, "CO {co} page {page}");
            }
        }
        assert_eq!(fallbacks(), before, "a page fitted no layout");
    }
}
