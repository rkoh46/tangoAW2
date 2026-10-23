//! Army skins: a custom army's look (Emerald Sun is the first) on top of one of AW2's five army colours.
//!
//! **The idea.** AW2 draws an army by its *colour* (1 Orange Star .. 5 Black Hole): palette rows, a few
//! per-colour pictures (Infantry and Mech, the HQ, the emblem) and nothing else. A skin takes over one of
//! those colours: while a match has a skin, the ROM image in the console holds the skin's palette rows and
//! pictures where the game looks for that colour's. The army keeps the colour's number everywhere the game's
//! rules look; only what is drawn (and the names tangoAW2 writes) says the skin's. Armies' colours are distinct,
//! so one skin on one colour is one more army to choose, on any map; the colour it sits on is the one the seat
//! would have had, so any army can be replaced and the other four stay as they were.
//!
//! **State.** One byte in EWRAM ([`STATE`]): the colour (1..5) the skin sits on, 0 for none. The Teams pages
//! write it with the colours ([`crate::online_teams`], [`crate::pvp`]); it is part of the shared console, so
//! rollback, replays and every peer agree.
//!
//! **The patch.** [`sync`] runs every tick: when the byte differs from what the ROM image holds
//! ([`DATA`]: a marker and the originals of everything patched), the originals are put back and the
//! new colour's patches are written. [`plan`] is a pure function of the ROM and the skin (the
//! `aw2_skin_dump` example and `aw2dev armyskin` use it). The skin itself is a data file
//! (`skins/<id>.toml`, docs/dev/army-packs.md): colours and pixel art of this repository's own; AW2's own
//! pictures are read from the player's ROM.

use mgba::core::Core;

/// The skin's state: +0 the colour (1..5) it sits on, 0 for none.
pub const STATE: u32 = 0x0203_CA00;
pub const STATE_LEN: u32 = 0x10;

/// Free ROM: a marker word, the applied colour, and the originals of everything patched.
const DATA: u32 = 0x09FC_0000;
const MAGIC: u32 = 0x314B_5345; // "ESK1"
const APPLIED: u32 = DATA + 4;
const BACKUP: u32 = DATA + 0x100;
const BACKUP_MAX: usize = 0x10000 - 0x100;
/// The skin's own pictures (see [`blobs`]).
const ART: u32 = DATA + 0x1_0000;

pub mod names {
    pub const EMERALD_SUN: &str = "Emerald Sun";
}

/// A palette table indexed by colour (row `colour - 1`, 32 bytes a row).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind {
    /// AW2's map-unit palette: roles 2..7 the army's ramp, 11..13 trim greys, 14 unused.
    Unit,
    /// The moved units' greys: the unit palette's layout, tinted.
    Moved,
    /// The moving units' palette (`0x0810EA60`): the unit roles in another order.
    Moving,
    /// Any palette whose army-coloured entries share the army's hue: recoloured by brightness.
    Hue,
    /// The turn banner's stripe (entries 1..5, bright to dark).
    Banner,
}

/// (name, address of colour 1's rows, colours the table has, rows of 32 bytes per colour, kind).
pub const TABLES: &[(&str, u32, usize, usize, Kind)] = &[
    ("map units", 0x0810_E6E0, 5, 1, Kind::Unit),
    ("map units (copy)", 0x085A_D9E8, 5, 1, Kind::Unit),
    ("moved units", 0x0810_E780, 5, 1, Kind::Moved),
    ("moving units", 0x0810_EA60, 5, 1, Kind::Moving),
    ("buildings", 0x080D_3F04, 5, 1, Kind::Hue),
    ("CO panel", 0x080D_4188, 5, 1, Kind::Hue),
    ("table 8104264", 0x0810_4264, 5, 1, Kind::Hue),
    ("table 8106984", 0x0810_6984, 5, 1, Kind::Hue),
    ("power colours", 0x084F_2BC8, 4, 2, Kind::Hue),
    ("turn banner", 0x080A_1238, 4, 1, Kind::Banner),
];

/// Black Hole's own copies where the game's table has four (see `crate::five`, `crate::co_new`): (name, address, kind).
const BLACK_HOLE_EXTRAS: &[(&str, u32, usize, Kind)] = &[
    ("power colours (5)", 0x0857_66A0, 2, Kind::Hue),
    ("turn banner (5)", crate::five::BANNER5, 1, Kind::Banner),
];

/// AW2's moving-unit palette index of each map-unit role (see `ds_unit_art::MOVE_ROLES`).
const MOVE_ROLE: [usize; 16] = [0, 1, 6, 2, 7, 8, 4, 5, 3, 10, 13, 11, 12, 15, 14, 9];

/// A skin, parsed from its data file.
#[derive(Clone, Debug)]
pub struct Skin {
    pub id: String,
    pub name: String,
    pub short: String,
    /// BGR555.
    pub ramp: [u16; 6],
    pub trim: [u16; 3],
    pub crest: u16,
    pub gold: u16,
    pub gold_dark: u16,
    pub moved_tint: f32,
    pub infantry: UnitArt,
    pub mech: UnitArt,
    /// The HQ's picture: 32 rows of 16 characters, `.` clear, a hex digit the building palette's index.
    pub hq: Vec<String>,
    /// The emblem: 16 rows of 16; `1` white, `2` shadow, `a`, `b`, `c` the dark, mid and light colour of the emblem
    /// colour the skin sits on (Black Hole has one: all three are it).
    pub emblem: Vec<String>,
}

/// A foot unit's picture: AW2's own picture of the colour `base`, then patches on top.
#[derive(Clone, Debug, Default)]
pub struct UnitArt {
    pub base: u8,
    pub patches: Vec<UnitPatch>,
}

/// `rows` laid on the 16x16 picture at (x, y) in the given frames (0..3). `.` keeps the pixel, `_` clears it, a hex
/// digit is the unit palette's index.
#[derive(Clone, Debug)]
pub struct UnitPatch {
    pub frames: Vec<usize>,
    pub x: usize,
    pub y: usize,
    pub rows: Vec<String>,
}

pub const EMERALD_SUN_TOML: &str = include_str!("../skins/emerald_sun.toml");

pub fn emerald_sun() -> &'static Skin {
    static S: std::sync::OnceLock<Skin> = std::sync::OnceLock::new();
    S.get_or_init(|| Skin::parse(EMERALD_SUN_TOML).expect("skins/emerald_sun.toml"))
}

pub fn bgr555(rgb: (u8, u8, u8)) -> u16 {
    (rgb.0 >> 3) as u16 | ((rgb.1 >> 3) as u16) << 5 | ((rgb.2 >> 3) as u16) << 10
}

pub fn rgb_of(c: u16) -> (u8, u8, u8) {
    let f = |v: u16| ((v & 31) * 255 / 31) as u8;
    (f(c), f(c >> 5), f(c >> 10))
}

fn hex(s: &str) -> Result<u16, String> {
    let v = u32::from_str_radix(s.trim_start_matches('#'), 16).map_err(|e| format!("{s}: {e}"))?;
    Ok(bgr555(((v >> 16) as u8, (v >> 8) as u8, v as u8)))
}

impl Skin {
    pub fn parse(text: &str) -> Result<Skin, String> {
        let v: toml::Value = toml::from_str(text).map_err(|e| e.to_string())?;
        let s = |k: &str| {
            v.get(k)
                .and_then(|x| x.as_str())
                .map(str::to_string)
                .ok_or(format!("missing {k}"))
        };
        let c = v.get("colours").ok_or("missing [colours]")?;
        let list = |k: &str, n: usize| -> Result<Vec<u16>, String> {
            let a = c
                .get(k)
                .and_then(|x| x.as_array())
                .ok_or(format!("missing colours.{k}"))?;
            if a.len() != n {
                return Err(format!("colours.{k} needs {n} colours"));
            }
            a.iter().map(|x| hex(x.as_str().unwrap_or(""))).collect()
        };
        let one = |k: &str| {
            hex(c
                .get(k)
                .and_then(|x| x.as_str())
                .ok_or(format!("missing colours.{k}"))?)
        };
        let strings = |t: Option<&toml::Value>, what: &str| -> Result<Vec<String>, String> {
            let a = t.and_then(|x| x.as_array()).ok_or(format!("missing {what}"))?;
            Ok(a.iter().map(|x| x.as_str().unwrap_or("").to_string()).collect())
        };
        let unit = |name: &str| -> Result<UnitArt, String> {
            let u = v.get(name).ok_or(format!("missing [{name}]"))?;
            let base = u
                .get("base")
                .and_then(|x| x.as_integer())
                .ok_or(format!("missing {name}.base"))? as u8;
            let mut patches = Vec::new();
            for p in u
                .get("patch")
                .and_then(|x| x.as_array())
                .map(|a| a.as_slice())
                .unwrap_or(&[])
            {
                let n = |k: &str| p.get(k).and_then(|x| x.as_integer()).unwrap_or(0) as usize;
                patches.push(UnitPatch {
                    frames: p
                        .get("frames")
                        .and_then(|x| x.as_array())
                        .map(|a| a.iter().filter_map(|f| f.as_integer()).map(|f| f as usize).collect())
                        .unwrap_or_else(|| vec![0, 1, 2]),
                    x: n("x"),
                    y: n("y"),
                    rows: strings(p.get("rows"), &format!("{name}.patch.rows"))?,
                });
            }
            Ok(UnitArt { base, patches })
        };
        Ok(Skin {
            id: s("id")?,
            name: s("name")?,
            short: s("short")?,
            ramp: list("ramp", 6)?.try_into().unwrap(),
            trim: list("trim", 3)?.try_into().unwrap(),
            crest: one("crest")?,
            gold: one("gold")?,
            gold_dark: one("gold_dark")?,
            moved_tint: c.get("moved_tint").and_then(|x| x.as_float()).unwrap_or(0.3) as f32,
            infantry: unit("infantry")?,
            mech: unit("mech")?,
            hq: strings(v.get("hq").and_then(|h| h.get("rows")), "hq.rows")?,
            emblem: strings(v.get("emblem").and_then(|h| h.get("rows")), "emblem.rows")?,
        })
    }
}

// ---------- colours ----------

fn lum(c: u16) -> f32 {
    let (r, g, b) = rgb_of(c);
    (0.299 * r as f32 + 0.587 * g as f32 + 0.114 * b as f32) / 255.0
}

fn hsv(c: u16) -> (f32, f32, f32) {
    let (r, g, b) = rgb_of(c);
    let (r, g, b) = (r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0);
    let mx = r.max(g).max(b);
    let mn = r.min(g).min(b);
    let d = mx - mn;
    let h = if d == 0.0 {
        0.0
    } else if mx == r {
        ((g - b) / d).rem_euclid(6.0)
    } else if mx == g {
        (b - r) / d + 2.0
    } else {
        (r - g) / d + 4.0
    } * 60.0;
    (h, if mx == 0.0 { 0.0 } else { d / mx }, mx)
}

fn mix(a: u16, b: u16, t: f32) -> u16 {
    let (a, b) = (rgb_of(a), rgb_of(b));
    let m = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t).round().clamp(0.0, 255.0) as u8;
    bgr555((m(a.0, b.0), m(a.1, b.1), m(a.2, b.2)))
}

impl Skin {
    /// The skin's ramp read at a brightness 0..1 (the ramp is light to dark; brighter than its lightest
    /// goes towards white, darker than its darkest towards black).
    pub fn ramp_at(&self, l: f32) -> u16 {
        let mut pts: Vec<(f32, u16)> = self.ramp.iter().map(|&c| (lum(c), c)).collect();
        pts.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        let (lo, hi) = (pts[0], pts[pts.len() - 1]);
        if l <= lo.0 {
            return mix(0, lo.1, if lo.0 > 0.0 { l / lo.0 } else { 1.0 });
        }
        if l >= hi.0 {
            return mix(hi.1, 0x7FFF, ((l - hi.0) / (1.0 - hi.0)).min(1.0));
        }
        for w in pts.windows(2) {
            if l <= w[1].0 {
                return mix(w[0].1, w[1].1, (l - w[0].0) / (w[1].0 - w[0].0).max(1e-6));
            }
        }
        hi.1
    }

    /// AW2's map-unit palette row of this skin on top of `orig` (the colour's own row).
    pub fn unit_row(&self, orig: &[u16; 16]) -> [u16; 16] {
        let mut out = *orig;
        out[2..8].copy_from_slice(&self.ramp);
        out[11..14].copy_from_slice(&self.trim);
        out[14] = self.crest;
        out
    }

    /// The moving-unit row: the same roles at AW2's other indices.
    pub fn moving_row(&self, orig: &[u16; 16]) -> [u16; 16] {
        let mut out = *orig;
        let unit = self.unit_row(&[0u16; 16]);
        for role in (2..8).chain(11..15) {
            out[MOVE_ROLE[role]] = unit[role];
        }
        out
    }

    /// The grey of a unit that has moved: the colour's own grey with a breath of the ramp.
    pub fn moved_row(&self, orig: &[u16; 16]) -> [u16; 16] {
        let mut out = *orig;
        for i in (2..8).chain(11..14) {
            out[i] = mix(orig[i], self.ramp_at(lum(orig[i])), self.moved_tint);
        }
        out
    }

    /// A palette of the army's hue (`army` is the colour's unit row, to know which hue is its): the entries
    /// of that hue take the skin's ramp at their brightness, the rest stay.
    pub fn hue_row(&self, orig: &[u16; 16], army_unit_row: &[u16; 16]) -> [u16; 16] {
        let (ah, _, _) = hsv(army_unit_row[4]);
        let near = |h: f32| {
            let d = (h - ah).abs();
            d.min(360.0 - d) <= 30.0
        };
        let mut out = *orig;
        for i in 1..16 {
            let (h, s, v) = hsv(orig[i]);
            if s >= 0.22 && v >= 0.15 && near(h) {
                out[i] = self.ramp_at(lum(orig[i]));
            }
        }
        out
    }

    /// The turn banner's colours: stripe 1..5 from the ramp (the numerals, 6.., are shared).
    pub fn banner_row(&self, orig: &[u16; 16]) -> [u16; 16] {
        let mut out = *orig;
        for i in 0..5 {
            out[1 + i] = self.ramp[1 + i];
        }
        out
    }
}

// ---------- the plan ----------

/// A reader of ROM bytes: the live console, or a ROM file.
pub trait Rom {
    fn read(&self, addr: u32, len: usize) -> Vec<u8>;
}

impl Rom for Core {
    fn read(&self, addr: u32, len: usize) -> Vec<u8> {
        let mut b = vec![0u8; len];
        self.raw_read_range(addr, -1, &mut b);
        b
    }
}

/// A ROM file's bytes as the GBA maps them from 0x08000000.
pub struct RomFile<'a>(pub &'a [u8]);

impl Rom for RomFile<'_> {
    fn read(&self, addr: u32, len: usize) -> Vec<u8> {
        let o = (addr & 0x01FF_FFFF) as usize;
        self.0
            .get(o..o + len)
            .map(<[u8]>::to_vec)
            .unwrap_or_else(|| vec![0xFF; len])
    }
}

/// One write: `data` at `addr`.
#[derive(Clone, Debug, PartialEq)]
pub struct Patch {
    pub what: String,
    pub addr: u32,
    pub data: Vec<u8>,
}

fn row_of(rom: &dyn Rom, addr: u32) -> [u16; 16] {
    let b = rom.read(addr, 32);
    let mut r = [0u16; 16];
    for (i, c) in r.iter_mut().enumerate() {
        *c = u16::from_le_bytes([b[2 * i], b[2 * i + 1]]);
    }
    r
}

fn bytes_of(r: &[u16; 16]) -> Vec<u8> {
    r.iter().flat_map(|c| c.to_le_bytes()).collect()
}

/// Every write that gives the skin to colour `host` (1..5), as the ROM `rom` (unpatched) needs them.
pub fn plan(rom: &dyn Rom, skin: &Skin, host: u8) -> Vec<Patch> {
    let mut out = Vec::new();
    if !(1..=5).contains(&host) {
        return out;
    }
    let i = host as u32 - 1;
    let unit_orig = row_of(rom, 0x0810_E6E0 + 32 * i);
    let make = |kind: Kind, orig: &[u16; 16]| match kind {
        Kind::Unit => skin.unit_row(orig),
        Kind::Moved => skin.moved_row(orig),
        Kind::Moving => skin.moving_row(orig),
        Kind::Hue => skin.hue_row(orig, &unit_orig),
        Kind::Banner => skin.banner_row(orig),
    };
    for &(what, base, colours, span, kind) in TABLES {
        if i as usize >= colours {
            continue;
        }
        let at = base + 32 * (span as u32 * i);
        let mut data = Vec::new();
        for r in 0..span as u32 {
            data.extend(bytes_of(&make(kind, &row_of(rom, at + 32 * r))));
        }
        out.push(Patch {
            what: what.to_string(),
            addr: at,
            data,
        });
    }
    if host == 5 {
        for &(what, at, span, kind) in BLACK_HOLE_EXTRAS {
            let mut data = Vec::new();
            for r in 0..span as u32 {
                data.extend(bytes_of(&make(kind, &row_of(rom, at + 32 * r))));
            }
            out.push(Patch {
                what: what.to_string(),
                addr: at,
                data,
            });
        }
    }
    art_plan(rom, skin, host, &mut out);
    out
}

// ---------- pictures ----------

/// AW2's idle map units: three frames of 27 slots of 4 tiles (TL, TR, BL, BR), 0xD80 bytes a frame; the slot of a
/// unit type for a colour is in a u16 table `[5][25]`.
const UNIT_SHEET: u32 = 0x0810_BE60;
const FRAME_BYTES: u32 = 0xD80;
const SLOT_TABLE: u32 = 0x0849_9608;
/// The HQ's pictures (8 tiles, 16x32, per country 1..5) for clear and for snowy weather.
const HQ_ART: [u32; 2] = [0x080D_16C4, 0x080D_1BC4];
/// The emblems: a sprite group's rows (base, palette, first id) and the sprite sizes (see `pvp::sprite_source`).
const SPRITE_ROWS: u32 = 0x0848_B738;
const SPRITE_SIZES: u32 = 0x0848_B780;
const EMBLEM_GROUP: u32 = 1;
const EMBLEM_BASE_ID: u32 = 0x3D;
/// Each colour's own entries of the emblem palette: (light, mid, dark); Black Hole has one.
const EMBLEM_INDICES: [[u8; 3]; 5] = [[3, 4, 5], [6, 7, 8], [12, 13, 14], [9, 10, 11], [15, 15, 15]];

fn u16_at(rom: &dyn Rom, a: u32) -> u16 {
    let b = rom.read(a, 2);
    u16::from_le_bytes([b[0], b[1]])
}

fn u32_at(rom: &dyn Rom, a: u32) -> u32 {
    let b = rom.read(a, 4);
    u32::from_le_bytes([b[0], b[1], b[2], b[3]])
}

/// Tiles (4bpp, `wt` tiles wide, in 1D order) as a grid of palette indices, `wt * 8` wide.
pub fn tiles_to_grid(tiles: &[u8], wt: usize) -> Vec<u8> {
    let ht = tiles.len() / 32 / wt;
    let w = wt * 8;
    let mut g = vec![0u8; w * ht * 8];
    for k in 0..wt * ht {
        let (tx, ty) = (k % wt, k / wt);
        for y in 0..8 {
            for x in 0..8 {
                let b = tiles[k * 32 + y * 4 + x / 2];
                g[(ty * 8 + y) * w + tx * 8 + x] = if x & 1 == 1 { b >> 4 } else { b & 15 };
            }
        }
    }
    g
}

pub fn grid_to_tiles(g: &[u8], wt: usize) -> Vec<u8> {
    let w = wt * 8;
    let ht = g.len() / w / 8;
    let mut out = Vec::with_capacity(wt * ht * 32);
    for k in 0..wt * ht {
        let (tx, ty) = (k % wt, k / wt);
        for y in 0..8 {
            for x in (0..8).step_by(2) {
                out.push(g[(ty * 8 + y) * w + tx * 8 + x] | g[(ty * 8 + y) * w + tx * 8 + x + 1] << 4);
            }
        }
    }
    out
}

fn digit(c: char) -> Option<u8> {
    c.to_digit(16).map(|d| d as u8)
}

/// A grid of `rows` (a `.` is `clear`, else a hex digit) of `w` x `h`; None when the rows do not fit.
fn parse_rows(rows: &[String], w: usize, h: usize, mut each: impl FnMut(char) -> Option<u8>) -> Option<Vec<u8>> {
    if rows.len() != h || rows.iter().any(|r| r.chars().count() != w) {
        return None;
    }
    Some(
        rows.iter()
            .flat_map(|r| r.chars().map(&mut each).collect::<Vec<_>>())
            .map(|v| v.unwrap_or(0))
            .collect(),
    )
}

impl Skin {
    /// The picture of a foot unit (`unit` 1 Infantry, 2 Mech) in one idle frame: AW2's own of the base colour,
    /// patched.
    pub fn foot_grid(&self, base_pic: &[u8], unit: u8, frame: usize) -> Vec<u8> {
        let mut g = tiles_to_grid(base_pic, 2);
        let art = if unit == 1 { &self.infantry } else { &self.mech };
        for p in art.patches.iter().filter(|p| p.frames.contains(&frame)) {
            for (dy, row) in p.rows.iter().enumerate() {
                for (dx, c) in row.chars().enumerate() {
                    let (x, y) = (p.x + dx, p.y + dy);
                    if x >= 16 || y >= 16 {
                        continue;
                    }
                    match c {
                        '.' => {}
                        '_' => g[y * 16 + x] = 0,
                        c => g[y * 16 + x] = digit(c).unwrap_or(0),
                    }
                }
            }
        }
        g
    }

    pub fn hq_grid(&self) -> Option<Vec<u8>> {
        parse_rows(&self.hq, 16, 32, |c| digit(c))
    }

    /// The emblem for the colour `host` as a grid of palette indices of the shared emblem palette.
    pub fn emblem_grid(&self, host: u8) -> Option<Vec<u8>> {
        let idx = EMBLEM_INDICES[host as usize - 1];
        parse_rows(&self.emblem, 16, 16, |c| match c {
            '1' => Some(1),
            '2' => Some(2),
            'c' => Some(idx[0]),
            'b' => Some(idx[1]),
            'a' => Some(idx[2]),
            _ => None,
        })
    }
}

/// Where the emblem of colour `colour` starts in ROM (the game's own lookup).
pub fn emblem_source(rom: &dyn Rom, colour: u32) -> u32 {
    let row = SPRITE_ROWS + EMBLEM_GROUP * 12;
    let base = u32_at(rom, row);
    let first = u32_at(rom, row + 8) & 0xFFFF;
    let tiles = |i: u32| {
        let b = rom.read(SPRITE_SIZES + i * 4, 2);
        b[0] as u32 * b[1] as u32
    };
    let before: u32 = (first..EMBLEM_BASE_ID + colour).map(tiles).sum();
    base + (before & 0x3FF) * 32
}

pub fn emblem_palette(rom: &dyn Rom) -> u32 {
    u32_at(rom, SPRITE_ROWS + EMBLEM_GROUP * 12 + 4)
}

/// The pictures that follow the colour: the emblem and its colours.
fn art_plan(rom: &dyn Rom, skin: &Skin, host: u8, out: &mut Vec<Patch>) {
    if let Some(g) = skin.emblem_grid(host) {
        out.push(Patch { what: "emblem".to_string(), addr: emblem_source(rom, host as u32), data: grid_to_tiles(&g, 2) });
        let pal = emblem_palette(rom);
        let idx = EMBLEM_INDICES[host as usize - 1];
        let mut row = row_of(rom, pal);
        row[idx[0] as usize] = skin.ramp[1];
        row[idx[1] as usize] = skin.ramp[3];
        row[idx[2] as usize] = skin.ramp[5];
        out.push(Patch { what: "emblem colours".to_string(), addr: pal, data: bytes_of(&row) });
    }
}

/// The pictures that follow the army and not the colour (AW2 draws Infantry, Mech and the HQ by the country of the army's
/// CO): the skin's own copies in free ROM, which the traps below hand to the game for the skinned army. Written when the skin
/// is installed; (what, address, bytes).
pub fn blobs(rom: &dyn Rom, skin: &Skin) -> Vec<Patch> {
    let mut out = Vec::new();
    for unit in [1u8, 2] {
        let art = if unit == 1 { &skin.infantry } else { &skin.mech };
        let slot_of = |c: u8| u16_at(rom, SLOT_TABLE + 2 * (25 * (c as u32 - 1) + unit as u32)) as u32;
        let base = slot_of(art.base);
        for frame in 0..3u32 {
            let pic = rom.read(UNIT_SHEET + FRAME_BYTES * frame + 128 * base, 128);
            let g = skin.foot_grid(&pic, unit, frame as usize);
            out.push(Patch { what: format!("{} frame {frame}", if unit == 1 { "Infantry" } else { "Mech" }), addr: map_art(unit, frame), data: grid_to_tiles(&g, 2) });
        }
    }
    if let Some(g) = skin.hq_grid() {
        for (i, _) in HQ_ART.iter().enumerate() {
            out.push(Patch { what: "HQ".to_string(), addr: hq_art(i), data: grid_to_tiles(&g, 2) });
        }
    }
    out
}

/// Where the skin's picture of Infantry (1) or Mech (2) in an idle frame is kept.
pub fn map_art(unit: u8, frame: u32) -> u32 {
    ART + 128 * (2 * frame + unit as u32 - 1)
}

/// Where the skin's HQ picture for clear (0) or snowy (1) weather is kept.
pub fn hq_art(snow: usize) -> u32 {
    ART + 0x400 + 0x100 * snow as u32
}

// ---------- applying ----------

/// The colour the skin sits on, 0 for none.
pub fn host(core: &Core) -> u8 {
    core.raw_read_8(STATE, -1)
}

/// Put the skin on colour `host` (0: none).
pub fn set_host(core: &mut Core, host: u8) {
    core.raw_write_8(STATE, -1, host);
}

/// The colour the ROM image is patched for (0 none).
pub fn applied(core: &Core) -> u8 {
    if core.raw_read_32(DATA, -1) != MAGIC {
        0
    } else {
        core.raw_read_8(APPLIED, -1)
    }
}

/// Every tick: make the ROM image hold the skin the state asks for.
pub fn sync(core: &mut Core) {
    present(host(core));
    // (only a Versus match has the skin: the other modes' armies are the story's)
    let want = if crate::pvp::in_versus(core) { host(core) } else { 0 };
    let want = if (1..=5).contains(&want) { want } else { 0 };
    if applied(core) == want {
        return;
    }
    restore(core);
    if want != 0 {
        install(core, emerald_sun(), want);
    }
}

fn restore(core: &mut Core) {
    if core.raw_read_32(DATA, -1) != MAGIC {
        core.raw_write_32(DATA, -1, MAGIC);
        core.raw_write_8(APPLIED, -1, 0);
        core.raw_write_32(BACKUP, -1, 0);
        return;
    }
    let mut at = BACKUP;
    loop {
        let len = core.raw_read_16(at, -1) as usize;
        if len == 0 {
            break;
        }
        let addr = core.raw_read_32(at + 2, -1);
        let mut b = vec![0u8; len];
        core.raw_read_range(at + 6, -1, &mut b);
        core.raw_write_range(addr, -1, &b);
        at += 6 + len as u32;
    }
    core.raw_write_16(BACKUP, -1, 0);
    core.raw_write_8(APPLIED, -1, 0);
}

fn install(core: &mut Core, skin: &Skin, host: u8) {
    let patches = plan(core, skin, host);
    let mut at = BACKUP;
    for p in &patches {
        if (at - BACKUP) as usize + 6 + p.data.len() + 2 > BACKUP_MAX {
            log::error!("army skin: backup area full");
            break;
        }
        let orig = Rom::read(core, p.addr, p.data.len());
        core.raw_write_16(at, -1, p.data.len() as u16);
        core.raw_write_32(at + 2, -1, p.addr);
        core.raw_write_range(at + 6, -1, &orig);
        at += 6 + p.data.len() as u32;
    }
    core.raw_write_16(at, -1, 0);
    for p in &patches {
        core.raw_write_range(p.addr, -1, &p.data);
    }
    for p in blobs(core, skin) {
        core.raw_write_range(p.addr, -1, &p.data);
    }
    for (i, v) in ES_SLOT.iter().enumerate() {
        core.raw_write_16(SLOT_LIST + 2 * i as u32, -1, *v);
    }
    core.raw_write_8(APPLIED, -1, host);
}


// ---------- choosing the army ----------

/// The identity code of the skin among the choices of an army: the five colours are 1..5.
pub const SKIN: u8 = 6;
/// The order a seat's choice cycles through: Orange Star, Blue Moon, Yellow Comet, Green Earth, Black Hole, the skin.
pub const ORDER: [u8; 6] = [1, 2, 4, 3, 5, SKIN];

/// The next choice (`step` +1 or -1 in [`ORDER`]) for a seat whose choice is `current`, skipping what the other seats
/// (`taken`) have. The skin can be chosen by one seat only.
pub fn step_choice(current: u8, taken: &[u8], step: isize) -> u8 {
    let n = ORDER.len() as isize;
    let start = ORDER.iter().position(|&c| c == current).unwrap_or(0) as isize;
    (1..n)
        .map(|k| ORDER[(start + step * k).rem_euclid(n) as usize])
        .find(|c| !taken.contains(c))
        .unwrap_or(current)
}

/// The colours the game paints the armies with for the seats' choices (distinct, one of the five or the skin): each
/// choice is its own colour; the skin's seat takes the lowest colour none of the others has, and is the skin's host.
/// Returns the colour of each seat and the host (0 without the skin).
pub fn assign(choices: &[u8]) -> (Vec<u8>, u8) {
    let used = |c: u8| choices.iter().any(|&x| x == c);
    let host = if used(SKIN) { (1..=5u8).find(|&c| !used(c)).unwrap_or(1) } else { 0 };
    (choices.iter().map(|&c| if c == SKIN { host } else { c }).collect(), host)
}

/// The colour the skin sits on as the presentation last saw it (the app's legend, the status bar): a copy of the state
/// for code that has no console at hand. Presentation only.
static PRESENT: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);

pub fn present(host: u8) {
    PRESENT.store(host, std::sync::atomic::Ordering::Relaxed);
}

pub fn present_host() -> u8 {
    PRESENT.load(std::sync::atomic::Ordering::Relaxed)
}

/// The skin's own colour for chips and legends (a mid tone of its ramp).
pub fn swatch() -> (u8, u8, u8) {
    rgb_of(emerald_sun().ramp[2])
}

/// The skin's name for texts and menus.
pub fn name() -> &'static str {
    &emerald_sun().name
}

/// The colour the game paints (`colour` 1..5) or, as the skin, its name.
pub fn colour_name(core: &Core, colour: u8) -> &'static str {
    if host(core) == colour && colour != 0 {
        return name();
    }
    match colour {
        1 => "Orange Star",
        2 => "Blue Moon",
        3 => "Green Earth",
        4 => "Yellow Comet",
        5 => "Black Hole",
        _ => "",
    }
}


/// What the Teams screen of the game's own flow keeps of the choices: +1.. each army's choice (0: its colour as the game has
/// it), +0xF 1 once the screen's first frame has reset them.
const IDENT: u32 = STATE + 1;
const SEEN: u32 = STATE + 0xF;

/// The first frame of a Teams screen: no skin, every army its colour. Cleared again when the battle starts.
pub fn teams_frame(core: &mut Core) {
    if core.raw_read_8(SEEN, -1) == 0 {
        core.raw_write_8(SEEN, -1, 1);
        core.raw_write_range(IDENT, -1, &[0u8; 5]);
        set_host(core, 0);
    }
}

pub fn teams_left(core: &mut Core) {
    core.raw_write_8(SEEN, -1, 0);
}

/// The Teams screen's R / L: army `slot` (0-based) of `armies` takes the next choice of the six (the colours of the
/// record at `colours_at`, the skin). On a five-army map the colours are the armies' own and R / L only put the skin on
/// the army or take it off.
pub fn teams_step(core: &mut Core, colours_at: u32, slot: u32, armies: u32, step: isize, five: bool) {
    let colour = |core: &Core, s: u32| core.raw_read_8(colours_at + s, -1);
    let mut choices: Vec<u8> = (0..armies)
        .map(|s| match core.raw_read_8(IDENT + s, -1) {
            0 => colour(core, s),
            c => c,
        })
        .collect();
    let taken: Vec<u8> = (0..armies).filter(|&s| s != slot).map(|s| choices[s as usize]).collect();
    if five {
        let here = choices[slot as usize];
        choices[slot as usize] = if here == SKIN { colour(core, slot) } else if taken.contains(&SKIN) { here } else { SKIN };
    } else {
        choices[slot as usize] = step_choice(choices[slot as usize], &taken, step);
    }
    let _ = step;
    let (values, host) = if five {
        let es = choices.iter().position(|&c| c == SKIN);
        (
            (0..armies).map(|s| colour(core, s)).collect::<Vec<_>>(),
            es.map(|s| colour(core, s as u32)).unwrap_or(0),
        )
    } else {
        assign(&choices)
    };
    for s in 0..armies {
        core.raw_write_8(IDENT + s, -1, if choices[s as usize] == SKIN { SKIN } else { 0 });
        core.raw_write_8(colours_at + s, -1, values[s as usize]);
    }
    set_host(core, host);
}

// ---------- the skinned army's pictures ----------

/// Whether army `army` (1..5) wears the skin.
pub fn skinned(core: &Core, army: u32) -> bool {
    let host = host(core);
    if !(1..=5).contains(&host) || !(1..=5).contains(&army) {
        return false;
    }
    core.raw_read_8(crate::five::players(core) + 0x3C * army + 0x1A, -1) == host
}

/// The skin is installed in this console.
fn installed(core: &Core) -> bool {
    applied(core) != 0
}

/// The map's unit sprite slots of the skin's Infantry and Mech (the game's go to 26; Dual Strike's new units
/// use 59..65, `crate::roster`; the BG map memory begins at tile 0x340, slot 66): their tiles are at 0x235 + 4 * slot, put there every frame by [`sync_map_art`].
const ES_SLOT: [u16; 3] = [0, 52, 53];
const SLOT_LIST: u32 = ART + 0x3F0;
const SHEET_TILE: u32 = 0x235;
const SHEET_VRAM: u32 = 0x0600_0000 + 32 * SHEET_TILE;
const SLOT_BYTES: u32 = 128;

/// `sub_080261A4(army, type)`: the map sprite slot of a unit, by the country of the army's CO. After its first
/// instruction (r0 the army, r4 the type): a skinned army's Infantry and Mech take the skin's slot.
const SLOT_FN: u32 = 0x0802_61A6;
const SLOT_FN_LOAD: u32 = 0x0802_61BA;

fn unit_slot(core: &mut Core) {
    let (army, ty) = {
        let c = core.gba().cpu();
        (c.gpr(0) as u32 & 0xFFFF, c.gpr(1) as u32 & 0xFFFF)
    };
    if std::env::var_os("AW2_SKIN_LOG").is_some() {
        eprintln!("skin: slot army {army} type {ty} r4 {:x} installed {} skinned {} host {}", core.gba().cpu().gpr(4) as u32, installed(core), skinned(core, army), host(core));
    }
    if (1..=2).contains(&ty) && installed(core) && skinned(core, army) {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(4, (SLOT_LIST + 2 * ty) as i32);
        cpu.set_thumb_pc(SLOT_FN_LOAD);
    }
}

/// On the battle map the game copies one of the sheet's three idle frames to the VRAM sheet; the skin's slots,
/// past the sheet, follow it (found by comparing, as `crate::roster` does for Dual Strike's units).
pub fn sync_map_art(core: &mut Core) {
    if !installed(core) {
        return;
    }
    const FRAME: u32 = 0x6C * 32;
    let mut now = vec![0u8; FRAME as usize];
    core.raw_read_range(SHEET_VRAM, -1, &mut now);
    let mut frame = None;
    for f in 0..3u32 {
        let mut b = vec![0u8; FRAME as usize];
        core.raw_read_range(UNIT_SHEET + FRAME_BYTES * f, -1, &mut b);
        if b == now {
            frame = Some(f);
            break;
        }
    }
    let Some(f) = frame else { return };
    for unit in [1u8, 2] {
        let mut want = [0u8; 128];
        core.raw_read_range(map_art(unit, f), -1, &mut want);
        let at = SHEET_VRAM + SLOT_BYTES * ES_SLOT[unit as usize] as u32;
        let mut have = [0u8; 128];
        core.raw_read_range(at, -1, &mut have);
        if have != want {
            core.raw_write_range(at, -1, &want);
        }
    }
}

/// `sub_0803F5E4(weather, base)`: loads the building sheet and each army's HQ picture (by the country of its CO) into
/// OBJ VRAM; at its end (r6 the first tile, r8 the weather: 1 snow) a skinned army's HQ is the skin's.
const HQ_LOADER_END: u32 = 0x0803_F698;
const HQ_TILES: u32 = 0x5C;
/// Army 5's HQ in a five-army game: the lab's tiles of the sheet (`crate::five::HQ5_TILE` less the sheet's start).
const HQ5_OFFSET: u32 = 0x90 - 0x48;

fn hq_loaded(core: &mut Core) {
    if !installed(core) {
        return;
    }
    let (base, snow) = {
        let c = core.gba().cpu();
        (c.gpr(6) as u32, (c.gpr(8) as u32 == 1) as usize)
    };
    let mut art = [0u8; 0x100];
    core.raw_read_range(hq_art(snow), -1, &mut art);
    for army in 1..=4u32 {
        if skinned(core, army) {
            let tile = (base + HQ_TILES + 8 * (army - 1)) & 0x3FF;
            core.raw_write_range(0x0601_0000 + tile * 32, -1, &art);
        }
    }
    if crate::five::active(core) && skinned(core, 5) {
        let tile = (base + HQ5_OFFSET) & 0x3FF;
        core.raw_write_range(0x0601_0000 + tile * 32, -1, &art);
    }
}

// ---------- test aids ----------

fn log_load(core: &mut Core) {
    let c = core.gba().cpu();
    eprintln!(
        "palload src {:08x} off {:03x} size {:x} lr {:08x}",
        c.gpr(0) as u32,
        c.gpr(1) as u32 & 0xFFFF,
        c.gpr(2) as u32 & 0xFFFF,
        c.gpr(14) as u32
    );
}

/// The game's palette loaders: (r0 source, r1 byte offset in the palette buffer, r2 size).
const LOAD_PALETTE: u32 = 0x0801_35F4;
const LOAD_PALETTE_FLUSH: u32 = 0x0801_3618;

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![(SLOT_FN, Box::new(unit_slot)), (HQ_LOADER_END, Box::new(hq_loaded))];
    // `AW2_PAL_LOG=1`: every palette the game loads, with its source (to find what an army's colour reaches).
    if std::env::var_os("AW2_PAL_LOG").is_some() {
        t.push((LOAD_PALETTE, Box::new(log_load)));
        t.push((LOAD_PALETTE_FLUSH, Box::new(log_load)));
    }
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_skin_parses() {
        let s = emerald_sun();
        assert_eq!(s.name, "Emerald Sun");
        assert!(lum(s.ramp[0]) > lum(s.ramp[5]));
    }

    #[test]
    fn ramp_reading_is_monotonic() {
        let s = emerald_sun();
        let mut last = -1.0;
        for k in 0..=20 {
            let c = s.ramp_at(k as f32 / 20.0);
            assert!(lum(c) + 0.02 >= last, "{k}");
            last = lum(c);
        }
    }

    #[test]
    fn choices_cycle_and_the_skin_takes_a_free_colour() {
        // Orange Star, Blue Moon, Yellow Comet, Green Earth, Black Hole, then the skin
        assert_eq!(step_choice(1, &[], 1), 2);
        assert_eq!(step_choice(5, &[], 1), SKIN);
        assert_eq!(step_choice(SKIN, &[], 1), 1);
        assert_eq!(step_choice(1, &[], -1), SKIN);
        // what others have is skipped, the skin included
        assert_eq!(step_choice(1, &[2, 4], 1), 3);
        assert_eq!(step_choice(5, &[SKIN], 1), 1);
        assert_eq!(step_choice(2, &[1, 4, 3, 5], 1), SKIN);
        assert_eq!(step_choice(2, &[1, 4, 3, 5, SKIN], 1), 2);
        // the skin on a 5-seat map stands in for the colour nobody else has
        assert_eq!(assign(&[1, 2, SKIN, 4, 5]), (vec![1, 2, 3, 4, 5], 3));
        assert_eq!(assign(&[SKIN, 2]), (vec![1, 2], 1));
        assert_eq!(assign(&[2, SKIN]), (vec![2, 1], 1));
        assert_eq!(assign(&[1, 2, 3]), (vec![1, 2, 3], 0));
    }

    #[test]
    fn unit_row_keeps_the_roles() {
        let s = emerald_sun();
        let orig: [u16; 16] = std::array::from_fn(|i| i as u16 * 100);
        let r = s.unit_row(&orig);
        assert_eq!((r[0], r[1], r[8], r[15]), (orig[0], orig[1], orig[8], orig[15]));
        assert_eq!(r[2], s.ramp[0]);
        assert_eq!(r[14], s.crest);
        let m = s.moving_row(&orig);
        assert_eq!(m[6], s.ramp[0], "role 2 sits at moving index 6");
    }
}
