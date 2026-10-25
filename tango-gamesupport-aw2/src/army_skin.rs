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

/// The skins' state: +0.. the colour (1..5) each skin sits on, 0 for none ([`MAX_SKINS`] bytes); +4.. what each army of the
/// Teams screen has chosen (0: its colour as the game has it; else a skin's code, [`SKIN`] + its index); +0xF 1 once the
/// Teams screen has reset them.
pub const STATE: u32 = 0x0203_C500;
pub const STATE_LEN: u32 = 0x10;
const HOSTS: u32 = STATE;
const IDENT: u32 = STATE + 4;
const SEEN: u32 = STATE + 0xF;

/// How many skins a match can have at once (each has its own colour, its own map sprite slots and its own room in free ROM).
pub const MAX_SKINS: usize = 3;

/// Free ROM (a word marks it as ours): which skin is patched on each colour, the originals of everything patched (a list
/// for each colour), and every skin's own pictures and texts.
const DATA: u32 = 0x09FC_0000;
const MAGIC: u32 = 0x314B_5345; // "ESK1"
/// The skin (index + 1) patched on colour 1..5, and (the Dual Strike pack's picture palettes) on which colours.
fn applied_at(colour: u8) -> u32 {
    DATA + 0x10 + colour as u32
}
fn ds_applied_at(colour: u8) -> u32 {
    DATA + 0x20 + colour as u32
}
/// Set (per skin) once its pictures and texts are in free ROM (they follow the army, not the colour, and Crumb uses the
/// first skin's HQ with no skin on).
fn art_mark(skin: usize) -> u32 {
    DATA + 0x40 + 4 * skin as u32
}
fn backup(colour: u8) -> u32 {
    DATA + 0x100 + 0x1000 * (colour as u32 - 1)
}
const BACKUP_MAX: usize = 0xF00;
/// (The Dual Strike picture palettes' backups: 0x400 a colour, five colours from `DATA + 0x5000` to `DATA + 0x6400`, below the skins' figures at
/// `DATA + 0x7000`. They began at `DATA + 0x6000`, and colour 5's list (`DATA + 0x7000`) was written over the first skin's table of battle
/// figures and portraits: see [`portrait_blob`].)
fn ds_backup(colour: u8) -> u32 {
    DATA + 0x5000 + 0x400 * (colour as u32 - 1)
}
const DS_BACKUP_MAX: usize = 0x3F0;
const _: () = assert!(0x100 + 0x1000 * 4 + BACKUP_MAX <= 0x5000, "the colours' backups reach the Dual Strike backups");
const _: () = assert!(0x5000 + 0x400 * 4 + DS_BACKUP_MAX <= 0x7000, "the Dual Strike backups reach the skins' figures");
/// A skin's own pictures (see [`blobs`]).
fn art_at(skin: usize) -> u32 {
    DATA + 0x1_0000 + 0x4000 * skin as u32
}

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
    /// The buildings' OBJ palettes: as `Hue`, and entry 14 (magenta in every colour's row: no building uses it) is the skin's gold,
    /// which the skin's HQ uses for its trim.
    Building,
    /// The battle scenes' and the unit portraits' palettes (two rows a colour, the first the figures'): as `Hue`, and entries 14 and 15 of the first row (unused by the soldiers) are the
    /// skin's crest red and its dark, which its helmet's plume is drawn in.
    Power,
    /// The turn banner's stripe (entries 1..5, bright to dark).
    Banner,
}

/// (name, address of colour 1's rows, colours the table has, rows of 32 bytes per colour, kind).
pub const TABLES: &[(&str, u32, usize, usize, Kind)] = &[
    ("map units", 0x0810_E6E0, 5, 1, Kind::Unit),
    ("map units (copy)", 0x085A_D9E8, 5, 1, Kind::Unit),
    ("moved units", 0x0810_E780, 5, 1, Kind::Moved),
    ("moved units (copy)", 0x085A_DA88, 5, 1, Kind::Moved),
    ("moving units", 0x0810_EA60, 5, 1, Kind::Moving),
    ("buildings", 0x080D_3F04, 5, 1, Kind::Building),
    ("CO panel", 0x080D_4188, 5, 1, Kind::Hue),
    ("table 8104264", 0x0810_4264, 5, 1, Kind::Hue),
    ("table 8106984", 0x0810_6984, 5, 1, Kind::Hue),
    ("power colours", 0x084F_2BC8, 5, 2, Kind::Power),
    ("buildings (second set)", 0x080D_3E04, 5, 1, Kind::Building),
    ("battle gauge", 0x0816_D498, 5, 1, Kind::Hue),
    ("HUD panel (BG 8)", 0x0818_3C28, 5, 1, Kind::Hue),
    ("table 85A9BBC", 0x085A_9BBC, 5, 1, Kind::Hue),
    ("table 85AC8BC", 0x085A_C8BC, 5, 1, Kind::Hue),
    ("turn banner", 0x080A_1238, 4, 1, Kind::Banner),
];

/// Black Hole's own copies where the game's table has four (see `crate::five`, `crate::co_new`): (name, address, rows,
/// kind, the game's table, its colours).
const BLACK_HOLE_EXTRAS: &[(&str, u32, usize, Kind, u32, usize)] = &[
    ("power colours (5, battle)", 0x0857_65A0, 2, Kind::Power, 0x084F_2BC8, 4),
    ("power colours (5)", 0x0857_66A0, 2, Kind::Power, 0x084F_2BC8, 4),
    ("turn banner (5)", crate::five::BANNER5, 1, Kind::Banner, 0x080A_1238, 4),
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
    /// The buildings' own ramp (light to dark), when the skin's buildings are not in the units' tones (AWBW's Jade Sun has pale-green buildings and sage-grey units).
    pub building: Option<Vec<u16>>,
    pub trim: [u16; 3],
    pub crest: u16,
    /// The crest's dark (palette entry 15 of the battle palette): the shade of its plume.
    pub crest_dark: u16,
    pub gold: u16,
    pub gold_dark: u16,
    pub moved_tint: f32,
    /// How bright a unit that has moved stays (0..1 of its live colour's brightness): the skin's own dimmed ramp.
    pub moved_dim: f32,
    /// How much the darker entries (6 to 14) of a moved unit's greys are lifted before they take the ramp (0..1: 0 none): the done unit is not black.
    pub moved_lift: f32,
    pub infantry: UnitArt,
    pub mech: UnitArt,
    /// The helmet drawn over the Infantry's and the Mech's battle-scene figures (`[battle.infantry]`, `[battle.mech]`) and over their portraits (`[portrait.infantry]`, `[portrait.mech]`).
    pub battle: [Option<FigPatch>; 2],
    pub portrait: [Option<FigPatch>; 2],
    /// The HQ's picture: 32 rows of 16 characters, `.` clear, a hex digit the building palette's index.
    pub hq: Vec<String>,
    /// The emblem: 16 rows of 16; `1` white, `2` shadow, `a`, `b`, `c` the dark, mid and light colour of the emblem
    /// colour the skin sits on (Black Hole has one: all three are it).
    pub emblem: Vec<String>,
}

/// A helmet for a battle-scene figure or a portrait (32 x 32 pictures of 16 tiles): the figure's helmet is its army-coloured
/// block of `dome` (w, h) pixels above the face; `rows` (hex digits are the figure palette's entries, `.` keeps the pixel, `_`
/// clears it) are laid with their top-left at (`x`, `y`) from the helmet's top-left corner. Frames without such a block (a figure
/// falling) are left as they are.
#[derive(Clone, Debug, PartialEq)]
pub struct FigPatch {
    pub dome: (usize, usize),
    pub x: i32,
    pub y: i32,
    pub rows: Vec<String>,
}

/// A foot unit's picture: AW2's own picture of the colour `base`, then patches on top.
#[derive(Clone, Debug, Default)]
pub struct UnitArt {
    pub base: u8,
    pub patches: Vec<UnitPatch>,
    /// The moving pictures get a crest over the helmet's top row (red, as the skin's `crest`).
    pub moving_crest: bool,
}

/// `rows` laid on the 16x16 picture at (x, y) in the given frames (0..3). `.` keeps the pixel, `_` clears it, a hex
/// digit is the unit palette's index.
#[derive(Clone, Debug)]
pub struct UnitPatch {
    pub frames: Vec<usize>,
    pub x: usize,
    pub y: usize,
    pub rows: Vec<String>,
    /// The moving-sheet frames (0..9: 0..3 facing sideways, 3..6 front, 6..9 back) the patch is also laid on, anchored
    /// at the left outline of the helmet's top row (found in the frame); `anchor` is where that point lies in `rows`.
    pub moving: Vec<usize>,
    pub anchor: (usize, usize),
}

/// The skins' data files, in the order of their choice codes (6, 7, ...). To add an army, add its file here
/// (docs/dev/army-packs.md); at most [`MAX_SKINS`].
const FILES: &[&str] = &[include_str!("../skins/emerald_sun.toml")];
const _: () = assert!(FILES.len() <= MAX_SKINS);

/// Every skin, parsed once.
pub fn skins() -> &'static [Skin] {
    static S: std::sync::OnceLock<Vec<Skin>> = std::sync::OnceLock::new();
    S.get_or_init(|| FILES.iter().map(|t| Skin::parse(t).expect("a skin's data file")).collect())
}

pub fn skin(i: usize) -> &'static Skin {
    &skins()[i]
}

/// Emerald Sun, the first (the one Crumb's HQ borrows).
pub fn emerald_sun() -> &'static Skin {
    skin(0)
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
                let list = |k: &str, default: Vec<usize>| -> Vec<usize> {
                    p.get(k)
                        .and_then(|x| x.as_array())
                        .map(|a| a.iter().filter_map(|f| f.as_integer()).map(|f| f as usize).collect())
                        .unwrap_or(default)
                };
                let anchor = list("anchor", vec![0, 0]);
                patches.push(UnitPatch {
                    frames: list("frames", vec![0, 1, 2]),
                    moving: list("moving", vec![]),
                    anchor: (anchor.first().copied().unwrap_or(0), anchor.get(1).copied().unwrap_or(0)),
                    x: n("x"),
                    y: n("y"),
                    rows: strings(p.get("rows"), &format!("{name}.patch.rows"))?,
                });
            }
            let moving_crest = u.get("moving").and_then(|m| m.get("crest")).and_then(|c| c.as_bool()).unwrap_or(false);
            Ok(UnitArt { base, patches, moving_crest })
        };
        let fig = |section: &str, name: &str| -> Result<Option<FigPatch>, String> {
            let Some(t) = v.get(section).and_then(|b| b.get(name)) else { return Ok(None) };
            let int = |k: &str| t.get(k).and_then(|x| x.as_integer());
            let dome = t.get("dome").and_then(|d| d.as_array()).ok_or(format!("missing {section}.{name}.dome"))?;
            let d = |i: usize| dome.get(i).and_then(|x| x.as_integer()).ok_or(format!("{section}.{name}.dome needs [width, height]"));
            Ok(Some(FigPatch { dome: (d(0)? as usize, d(1)? as usize), x: int("x").unwrap_or(0) as i32, y: int("y").unwrap_or(0) as i32, rows: strings(t.get("rows"), &format!("{section}.{name}.rows"))? }))
        };
        let crest = one("crest")?;
        let crest_dark = match c.get("crest_dark").and_then(|x| x.as_str()) {
            Some(h) => hex(h)?,
            None => mix(0, crest, 0.6),
        };
        Ok(Skin {
            id: s("id")?,
            name: s("name")?,
            short: s("short")?,
            ramp: list("ramp", 6)?.try_into().unwrap(),
            building: if c.get("building").is_some() { Some(list("building", 4)?) } else { None },
            trim: list("trim", 3)?.try_into().unwrap(),
            crest,
            crest_dark,
            gold: one("gold")?,
            gold_dark: one("gold_dark")?,
            moved_tint: c.get("moved_tint").and_then(|x| x.as_float()).unwrap_or(0.3) as f32,
            moved_dim: c.get("moved_dim").and_then(|x| x.as_float()).unwrap_or(1.0) as f32,
            moved_lift: c.get("moved_lift").and_then(|x| x.as_float()).unwrap_or(0.0) as f32,
            infantry: unit("infantry")?,
            mech: unit("mech")?,
            battle: [fig("battle", "infantry")?, fig("battle", "mech")?],
            portrait: [fig("portrait", "infantry")?, fig("portrait", "mech")?],
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

    /// The grey of a unit that has moved: AW2 tints each colour's greys with the army's hue, so every entry of the row
    /// (but the clear one) is made neutral and then given a breath of the skin's ramp at its brightness.
    pub fn moved_row(&self, orig: &[u16; 16]) -> [u16; 16] {
        let mut out = *orig;
        for i in 1..16 {
            // (the darker entries, from 6 but the outline, are lifted: the three body tones the check compares keep their place)
            let lift = if (6..15).contains(&i) { self.moved_lift } else { 0.0 };
            let l = lift + (1.0 - lift) * lum(orig[i]);
            let g = (l * 255.0).round().clamp(0.0, 255.0) as u8;
            let c = mix(bgr555((g, g, g)), self.ramp_at(l), self.moved_tint);
            out[i] = if self.moved_dim < 1.0 { mix(0, c, self.moved_dim) } else { c };
        }
        out
    }

    /// A palette that has the army's colours among others': the entries that differ between the colours' versions of
    /// the palette (`rows`, the first four colours' rows of the table) are the army's; they take the skin's ramp by
    /// brightness rank (the lightest the ramp's lightest, the darkest its darkest, the rest between), so the skin looks the
    /// same whichever colour it sits on; the rest stay.
    pub fn hue_row(&self, orig: &[u16; 16], rows: &[[u16; 16]]) -> [u16; 16] {
        self.rank_map(orig, rows, &self.ramp)
    }

    /// [`Self::hue_row`] with another ramp (light to dark, any length).
    pub fn rank_map(&self, orig: &[u16; 16], rows: &[[u16; 16]], ramp: &[u16]) -> [u16; 16] {
        let mut out = *orig;
        let mut army: Vec<usize> = (1..16).filter(|&i| orig[i] != 0 && rows.iter().any(|r| r[i] != rows[0][i])).collect();
        army.sort_by(|&a, &b| lum(orig[b]).partial_cmp(&lum(orig[a])).unwrap().then(a.cmp(&b)));
        let m = army.len();
        let top = ramp.len() - 1;
        for (rank, &i) in army.iter().enumerate() {
            let at = if m > 1 { (rank * top + (m - 1) / 2) / (m - 1) } else { top / 2 };
            out[i] = ramp[at.min(top)];
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

/// Every write that gives the skin (the `idx`-th of [`skins`]) to colour `host` (1..5), as the ROM `rom` (unpatched) needs them.
pub fn plan(rom: &dyn Rom, skin: &Skin, idx: usize, host: u8) -> Vec<Patch> {
    let mut out = Vec::new();
    if !(1..=5).contains(&host) {
        return out;
    }
    let i = host as u32 - 1;
    let make = |kind: Kind, orig: &[u16; 16], siblings: &[[u16; 16]], r: u32| match kind {
        Kind::Unit => skin.unit_row(orig),
        Kind::Moved => skin.moved_row(orig),
        Kind::Moving => skin.moving_row(orig),
        Kind::Hue => skin.hue_row(orig, siblings),
        Kind::Power => {
            let mut row = skin.hue_row(orig, siblings);
            if r == 0 {
                row[14] = skin.crest;
                row[15] = skin.crest_dark;
            }
            row
        }
        Kind::Building => {
            let mut row = match &skin.building {
                Some(b) => skin.rank_map(orig, siblings, b),
                None => skin.hue_row(orig, siblings),
            };
            row[14] = skin.gold;
            row
        }
        Kind::Banner => skin.banner_row(orig),
    };
    for &(what, base, colours, span, kind) in TABLES {
        if i as usize >= colours {
            continue;
        }
        let at = base + 32 * (span as u32 * i);
        let mut data = Vec::new();
        for r in 0..span as u32 {
            // (the same row of the other colours' versions)
            let siblings: Vec<[u16; 16]> = (0..colours.min(4) as u32)
                .map(|c| row_of(rom, base + 32 * (span as u32 * c + r)))
                .collect();
            data.extend(bytes_of(&make(kind, &row_of(rom, at + 32 * r), &siblings, r)));
        }
        out.push(Patch {
            what: what.to_string(),
            addr: at,
            data,
        });
    }
    if host == 5 {
        // (Black Hole's own copies: the game's table has the other four colours' rows)
        for &(what, at, span, kind, table, colours) in BLACK_HOLE_EXTRAS {
            let mut data = Vec::new();
            for r in 0..span as u32 {
                let siblings: Vec<[u16; 16]> = (0..colours.min(4) as u32)
                    .map(|c| row_of(rom, table + 32 * (span as u32 * c + r)))
                    .collect();
                data.extend(bytes_of(&make(kind, &row_of(rom, at + 32 * r), &siblings, r)));
            }
            out.push(Patch {
                what: what.to_string(),
                addr: at,
                data,
            });
        }
    }
    art_plan(rom, skin, host, &mut out);
    text_plan(idx, host, &mut out);
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
        row[idx[0] as usize] = skin.ramp[0];
        row[idx[1] as usize] = skin.ramp[4];
        row[idx[2] as usize] = skin.ramp[2];
        out.push(Patch { what: "emblem colours".to_string(), addr: pal, data: bytes_of(&row) });
    }
}

/// The pictures that follow the army and not the colour (AW2 draws Infantry, Mech and the HQ by the country of the army's
/// CO): the skin's own copies in free ROM, which the traps below hand to the game for the skinned army. Written when the skin
/// is installed; (what, address, bytes).
pub fn blobs(rom: &dyn Rom, skin: &Skin, idx: usize) -> Vec<Patch> {
    let mut out = Vec::new();
    for unit in [1u8, 2] {
        let art = if unit == 1 { &skin.infantry } else { &skin.mech };
        let slot_of = |c: u8| u16_at(rom, SLOT_TABLE + 2 * (25 * (c as u32 - 1) + unit as u32)) as u32;
        let base = slot_of(art.base);
        for frame in 0..3u32 {
            let pic = rom.read(UNIT_SHEET + FRAME_BYTES * frame + 128 * base, 128);
            let g = skin.foot_grid(&pic, unit, frame as usize);
            out.push(Patch { what: format!("{} frame {frame}", if unit == 1 { "Infantry" } else { "Mech" }), addr: map_art(idx, unit, frame), data: grid_to_tiles(&g, 2) });
        }
    }
    moving_blobs(rom, skin, idx, &mut out);
    figure_blobs(rom, skin, idx, &mut out);
    text_blobs(skin, idx, &mut out);
    if let Some(g) = skin.hq_grid() {
        for (i, _) in HQ_ART.iter().enumerate() {
            out.push(Patch { what: "HQ".to_string(), addr: hq_art(idx, i), data: grid_to_tiles(&g, 2) });
        }
    }
    out
}

/// Where skin `skin`'s picture of Infantry (1) or Mech (2) in an idle frame is kept.
pub fn map_art(skin: usize, unit: u8, frame: u32) -> u32 {
    art_at(skin) + 128 * (2 * frame + unit as u32 - 1)
}

/// Where its HQ picture for clear (0) or snowy (1) weather is kept.
pub fn hq_art(skin: usize, snow: usize) -> u32 {
    art_at(skin) + 0x400 + 0x100 * snow as usize as u32
}

// ---------- applying ----------

/// The colour (1..5) skin `skin` sits on, 0 for none.
pub fn host_of(core: &Core, skin: usize) -> u8 {
    if skin < MAX_SKINS {
        core.raw_read_8(HOSTS + skin as u32, -1)
    } else {
        0
    }
}

/// Put skin `skin` on colour `host` (0: none).
pub fn set_host_of(core: &mut Core, skin: usize, host: u8) {
    if skin < MAX_SKINS {
        core.raw_write_8(HOSTS + skin as u32, -1, host);
    }
}

/// Every skin's colour.
pub fn hosts(core: &Core) -> [u8; MAX_SKINS] {
    std::array::from_fn(|i| host_of(core, i))
}

/// The skin (index) the state puts on colour `colour`, if any.
pub fn skin_on(core: &Core, colour: u8) -> Option<usize> {
    (colour != 0).then(|| (0..skins().len()).find(|&i| host_of(core, i) == colour)).flatten()
}

/// Dual Strike's 16-colour army palette `own` (one of `all`, the five armies' in order) as the skin `skin_index` has it: the entries the
/// armies differ in take the skin's ramp by brightness, exactly as the game's own tables ([`Skin::hue_row`]). The skin file is the one source of
/// the colours; the Dual Strike screens ask for them here.
pub fn ds_row(skin_index: usize, own: &[u16; 16], all: &[[u16; 16]]) -> [u16; 16] {
    skin(skin_index).hue_row(own, &all[..all.len().min(4)])
}

/// The entries `mask` (bit i: entry i) of a palette are the army's: they take the skin's ramp by brightness rank, the rest stay. For art whose army-coloured entries
/// are found by what the tiles use (Dual Strike's pick flags).
pub fn recolour_entries(skin_index: usize, orig: &[u16; 16], mask: u16) -> [u16; 16] {
    let sk = skin(skin_index);
    let mut out = *orig;
    let mut army: Vec<usize> = (0..16).filter(|&i| mask >> i & 1 == 1).collect();
    army.sort_by(|&a, &b| lum(orig[b]).partial_cmp(&lum(orig[a])).unwrap().then(a.cmp(&b)));
    let m = army.len();
    for (rank, &i) in army.iter().enumerate() {
        let at = if m > 1 { (rank * 5 + (m - 1) / 2) / (m - 1) } else { 2 };
        out[i] = sk.ramp[at.min(5)];
    }
    out
}

/// The same for a palette as bytes (BGR555, little endian, 32 bytes).
pub fn ds_row_bytes(skin_index: usize, own: &[u8; 32], all: &[[u8; 32]]) -> [u8; 32] {
    let w = |b: &[u8; 32]| -> [u16; 16] { std::array::from_fn(|i| u16::from_le_bytes([b[2 * i], b[2 * i + 1]])) };
    let (own16, all16): ([u16; 16], Vec<[u16; 16]>) = (w(own), all.iter().map(w).collect());
    let out = ds_row(skin_index, &own16, &all16);
    let mut bytes = [0u8; 32];
    for (i, c) in out.iter().enumerate() {
        bytes[2 * i..2 * i + 2].copy_from_slice(&c.to_le_bytes());
    }
    bytes
}

/// The skin (index) the Teams screen's army `slot` (0-based) has chosen.
pub fn teams_skin(core: &Core, slot: u32) -> Option<usize> {
    match core.raw_read_8(IDENT + slot, -1) {
        c if c >= SKIN && ((c - SKIN) as usize) < skins().len() => Some((c - SKIN) as usize),
        _ => None,
    }
}

/// The skin's emblem as 16 x 16 pixels (None clear): white, the shadow and the emblem's three tones from the skin's ramp, for the screens that draw
/// it themselves (Dual Strike's Teams cards).
pub fn emblem_pixels(skin_index: usize) -> Vec<Option<(u8, u8, u8)>> {
    let sk = skin(skin_index);
    let mut out = Vec::with_capacity(256);
    for row in &sk.emblem {
        for ch in row.chars() {
            out.push(match ch {
                '1' => Some((255, 255, 255)),
                '2' => Some(rgb_of(sk.ramp[5])),
                'a' => Some(rgb_of(sk.ramp[2])),
                'b' => Some(rgb_of(sk.ramp[4])),
                'c' => Some(rgb_of(sk.ramp[0])),
                _ => None,
            });
        }
    }
    out.resize(256, None);
    out
}

/// The skin the ROM image is patched with on colour `colour` (index), if any.
pub fn applied_on(core: &Core, colour: u8) -> Option<usize> {
    if !(1..=5).contains(&colour) || core.raw_read_32(DATA, -1) != MAGIC {
        return None;
    }
    match core.raw_read_8(applied_at(colour), -1) {
        0 => None,
        k => Some(k as usize - 1),
    }
}

/// Every tick: make the ROM image hold the skins the state asks for.
pub fn sync(core: &mut Core) {
    present(hosts(core));
    init(core);
    ensure_art(core);
    // (only a Versus match has skins, and the Emerald Sun Campaign's battles, where the player's army wears the first skin: the other modes' armies are
    // the story's)
    let campaign = crate::es_campaign::skin_colour(core);
    if let Some(c) = campaign {
        set_host_of(core, 0, c);
    }
    let versus = crate::pvp::in_versus(core) || campaign.is_some();
    for colour in 1..=5u8 {
        let want = if versus { skin_on(core, colour) } else { None };
        let have = applied_on(core, colour);
        if want == have {
            continue;
        }
        if have.is_some() {
            restore_colour(core, colour);
        }
        if let Some(i) = want {
            install(core, skin(i), i, colour);
        }
    }
}

/// The first time on a console: our marker word, nothing patched.
fn init(core: &mut Core) {
    if core.raw_read_32(DATA, -1) == MAGIC {
        return;
    }
    core.raw_write_32(DATA, -1, MAGIC);
    for c in 1..=5u8 {
        core.raw_write_8(applied_at(c), -1, 0);
        core.raw_write_8(ds_applied_at(c), -1, 0);
        core.raw_write_32(backup(c), -1, 0);
        core.raw_write_32(ds_backup(c), -1, 0);
    }
    for i in 0..MAX_SKINS {
        core.raw_write_32(art_mark(i), -1, 0);
    }
}

/// Every skin's pictures, texts and slot lists into free ROM (once).
fn ensure_art(core: &mut Core) {
    for (i, sk) in skins().iter().enumerate() {
        if core.raw_read_32(art_mark(i), -1) == MAGIC {
            continue;
        }
        for p in blobs(core, sk, i) {
            core.raw_write_range(p.addr, -1, &p.data);
        }
        for (u, v) in [0u16, slot_of(i, 1), slot_of(i, 2)].iter().enumerate() {
            core.raw_write_16(slot_list(i) + 2 * u as u32, -1, *v);
        }
        core.raw_write_32(art_mark(i), -1, MAGIC);
    }
}

/// Take the skin off colour `colour`: what it patched comes back.
fn restore_colour(core: &mut Core, colour: u8) {
    restore_backup(core, backup(colour), BACKUP_MAX);
    core.raw_write_8(applied_at(colour), -1, 0);
}

/// Put back what the backup list at `base` holds (entries: address, length, the bytes padded to a word; a zero address ends
/// the list, `max` bytes at most) and empty the list.
fn restore_backup(core: &mut Core, base: u32, max: usize) {
    let mut at = base;
    loop {
        let addr = core.raw_read_32(at, -1);
        let len = core.raw_read_32(at + 4, -1) as usize;
        if addr == 0 || len == 0 || (at - base) as usize + 8 + len > max {
            break;
        }
        let mut b = vec![0u8; len];
        core.raw_read_range(at + 8, -1, &mut b);
        let before = Rom::read(core, addr, len);
        core.raw_write_range(addr, -1, &b);
        refresh_palettes(core, &before, &b);
        at += 8 + ((len as u32 + 3) & !3);
    }
    core.raw_write_32(base, -1, 0);
}

/// Write `patches`, keeping what they replace in the backup list at `base`.
fn apply_backup(core: &mut Core, base: u32, max: usize, patches: &[Patch]) {
    let mut at = base;
    for p in patches {
        if (at - base) as usize + 8 + p.data.len() + 8 > max {
            log::error!("army skin: backup area full");
            break;
        }
        let orig = Rom::read(core, p.addr, p.data.len());
        core.raw_write_32(at, -1, p.addr);
        core.raw_write_32(at + 4, -1, p.data.len() as u32);
        core.raw_write_range(at + 8, -1, &orig);
        at += 8 + ((p.data.len() as u32 + 3) & !3);
    }
    core.raw_write_32(at, -1, 0);
    for p in patches {
        let before = Rom::read(core, p.addr, p.data.len());
        core.raw_write_range(p.addr, -1, &p.data);
        refresh_palettes(core, &before, &p.data);
    }
}

fn install(core: &mut Core, skin: &Skin, idx: usize, colour: u8) {
    let patches = plan(core, skin, idx, colour);
    apply_backup(core, backup(colour), BACKUP_MAX, &patches);
    core.raw_write_8(applied_at(colour), -1, idx as u8 + 1);
}

/// The Dual Strike pack's picture palettes of the seven new units (the build menu's panel and the unit pages), copied into free
/// ROM by `crate::ds_unit_pictures` once the pack is on: the skin's colours for the colour it sits on.
pub fn ds_plan(rom: &dyn Rom, skin: &Skin, host: u8) -> Vec<Patch> {
    use crate::ds_unit_pictures::{ARMIES, PALETTE, PALETTES};
    let mut out = Vec::new();
    for k in 0..crate::roster::NEW_UNITS.len() as u32 {
        let at = |a: u32| PALETTES + PALETTE as u32 * (k * ARMIES as u32 + a);
        let mut data = Vec::new();
        for half in 0..2u32 {
            let rows: Vec<[u16; 16]> = (0..4).map(|a| row_of(rom, at(a) + 32 * half)).collect();
            if rows.iter().all(|r| r.iter().all(|&c| c == 0xFFFF || c == 0)) {
                return Vec::new();
            }
            let own = row_of(rom, at(host as u32 - 1) + 32 * half);
            data.extend(bytes_of(&skin.hue_row(&own, &rows)));
        }
        out.push(Patch { what: "Dual Strike unit picture".to_string(), addr: at(host as u32 - 1), data });
    }
    out
}

/// After the Dual Strike pack's tables are in (every tick): the skins on those palettes too.
pub fn sync_ds(core: &mut Core) {
    if core.raw_read_32(DATA, -1) != MAGIC {
        return;
    }
    for colour in 1..=5u8 {
        let want = applied_on(core, colour).map_or(0, |i| i as u8 + 1);
        let have = core.raw_read_8(ds_applied_at(colour), -1);
        if want == have {
            continue;
        }
        if have != 0 {
            restore_backup(core, ds_backup(colour), DS_BACKUP_MAX);
            core.raw_write_8(ds_applied_at(colour), -1, 0);
        }
        if want != 0 {
            let patches = ds_plan(core, skin(want as usize - 1), colour);
            if !patches.is_empty() {
                apply_backup(core, ds_backup(colour), DS_BACKUP_MAX, &patches);
                core.raw_write_8(ds_applied_at(colour), -1, want);
            }
        }
    }
}

/// A palette the game has loaded already (the Teams screen loads its emblems' on entry) keeps the colours of the ROM it
/// was loaded from: where the palette buffer or palette RAM holds a bank equal to `before`, `after` goes in its place.
fn refresh_palettes(core: &mut Core, before: &[u8], after: &[u8]) {
    if before.len() != after.len() || before.len() % 32 != 0 || before == after {
        return;
    }
    for base in [0x0300_20C0u32, 0x0500_0000] {
        let mut ram = [0u8; 0x400];
        core.raw_read_range(base, -1, &mut ram);
        for (b, a) in before.chunks(32).zip(after.chunks(32)) {
            for bank in 0..32usize {
                if ram[bank * 32..bank * 32 + 32] == *b {
                    core.raw_write_range(base + bank as u32 * 32, -1, a);
                }
            }
        }
    }
}


// ---------- choosing the army ----------

/// The code of the first skin among the choices of an army; the five colours are 1..5, skin `i` is `SKIN + i`.
pub const SKIN: u8 = 6;

/// The order a seat's choice cycles through: Orange Star, Blue Moon, Yellow Comet, Green Earth, Black Hole, then the skins.
pub fn order() -> Vec<u8> {
    let mut v = vec![1, 2, 4, 3, 5];
    v.extend((0..skins().len() as u8).map(|i| SKIN + i));
    v
}

/// The next choice (`step` +1 or -1 in [`order`]) for a seat whose choice is `current`, skipping what the other seats
/// (`taken`) have. A skin can be chosen by one seat only.
pub fn step_choice(current: u8, taken: &[u8], step: isize) -> u8 {
    let order = order();
    let n = order.len() as isize;
    let start = order.iter().position(|&c| c == current).unwrap_or(0) as isize;
    (1..n)
        .map(|k| order[(start + step * k).rem_euclid(n) as usize])
        .find(|c| !taken.contains(c))
        .unwrap_or(current)
}

/// The colours the game paints the armies with for the seats' choices (distinct, one of the five or a skin): each
/// colour choice is its own colour; a skin's seat takes the lowest colour none of the others has (the colour choices
/// first, then the skins in order), and is that skin's host. Returns the colour of each seat and every skin's host (0
/// for a skin nobody chose).
pub fn assign(choices: &[u8]) -> (Vec<u8>, [u8; MAX_SKINS]) {
    let mut used: Vec<u8> = choices.iter().copied().filter(|c| (1..=5).contains(c)).collect();
    let mut hosts = [0u8; MAX_SKINS];
    for i in 0..MAX_SKINS {
        if choices.contains(&(SKIN + i as u8)) {
            let h = (1..=5u8).find(|c| !used.contains(c)).unwrap_or(1);
            hosts[i] = h;
            used.push(h);
        }
    }
    let values = choices
        .iter()
        .map(|&c| if c >= SKIN { hosts[(c - SKIN) as usize % MAX_SKINS] } else { c })
        .collect();
    (values, hosts)
}

/// The skins' colours as the presentation last saw them (the app's legend, the status bar): a copy of the state for code
/// that has no console at hand. Presentation only.
static PRESENT: [std::sync::atomic::AtomicU8; MAX_SKINS] = [const { std::sync::atomic::AtomicU8::new(0) }; MAX_SKINS];

pub fn present(hosts: [u8; MAX_SKINS]) {
    for (p, h) in PRESENT.iter().zip(hosts) {
        p.store(h, std::sync::atomic::Ordering::Relaxed);
    }
}

/// The skin (index) the presentation last saw on colour `colour`.
pub fn present_skin(colour: u8) -> Option<usize> {
    (colour != 0).then(|| (0..skins().len()).find(|&i| PRESENT[i].load(std::sync::atomic::Ordering::Relaxed) == colour)).flatten()
}

/// The skin's own colour for chips and legends (a mid tone of its ramp).
pub fn swatch(skin_index: usize) -> (u8, u8, u8) {
    rgb_of(skin(skin_index).ramp[2])
}

/// A choice's name for the pages: the colour's army, or the skin's.
pub fn choice_name(code: u8) -> &'static str {
    match code {
        1 => "Orange Star",
        2 => "Blue Moon",
        3 => "Green Earth",
        4 => "Yellow Comet",
        5 => "Black Hole",
        c if (c as usize) >= SKIN as usize && ((c - SKIN) as usize) < skins().len() => &skin((c - SKIN) as usize).name,
        _ => "",
    }
}

/// The name of the army on colour `colour` in this console: the skin's when one sits there.
pub fn colour_name(core: &Core, colour: u8) -> &'static str {
    match skin_on(core, colour) {
        Some(i) => &skin(i).name,
        None => choice_name(colour),
    }
}

/// The skin's name for texts (the first skin's).
pub fn name() -> &'static str {
    &emerald_sun().name
}

/// The first frame of a Teams screen: no skin, every army its colour. Cleared again when the battle starts.
pub fn teams_frame(core: &mut Core) {
    if core.raw_read_8(SEEN, -1) == 0 {
        core.raw_write_8(SEEN, -1, 1);
        core.raw_write_range(IDENT, -1, &[0u8; 5]);
        for i in 0..MAX_SKINS {
            set_host_of(core, i, 0);
        }
    }
}

pub fn teams_left(core: &mut Core) {
    core.raw_write_8(SEEN, -1, 0);
}

/// The Teams screen's R / L: army `slot` (0-based) of `armies` takes the next choice of the six (the colours of the
/// record at `colours_at`, the skins). On a five-army map the colours are the armies' own and R / L only put a skin on
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
        // (its colour, then each skin not on another army)
        let own = colour(core, slot);
        let mut options = vec![own];
        options.extend((0..skins().len() as u8).map(|i| SKIN + i));
        let at = options.iter().position(|&c| c == choices[slot as usize]).unwrap_or(0) as isize;
        let n = options.len() as isize;
        if let Some(c) = (1..n).map(|k| options[(at + step * k).rem_euclid(n) as usize]).find(|c| *c == own || !taken.contains(c)) {
            choices[slot as usize] = c;
        }
    } else {
        choices[slot as usize] = step_choice(choices[slot as usize], &taken, step);
    }
    let (values, hosts) = if five {
        let mut hosts = [0u8; MAX_SKINS];
        for (i, h) in hosts.iter_mut().enumerate().take(skins().len()) {
            if let Some(s) = choices.iter().position(|&c| c == SKIN + i as u8) {
                *h = colour(core, s as u32);
            }
        }
        ((0..armies).map(|s| colour(core, s)).collect::<Vec<_>>(), hosts)
    } else {
        assign(&choices)
    };
    for s in 0..armies {
        core.raw_write_8(IDENT + s, -1, if choices[s as usize] >= SKIN { choices[s as usize] } else { 0 });
        core.raw_write_8(colours_at + s, -1, values[s as usize]);
    }
    for (i, h) in hosts.iter().enumerate() {
        set_host_of(core, i, *h);
    }
}

// ---------- moving pictures ----------

/// The moving units' sheets: per unit type a record of nine words (a sheet per country, the animation, ...) at `0x0849CD88`;
/// the sheets are LZ77 of 9 frames (side, front, back, three each) of nine tiles, tile k at column 2 - k % 3, row 2 - k / 3 of
/// the 24x24 frame.
const MOVE_TABLE: u32 = 0x0849_CD88;
const MOVE_RECORD: u32 = 0x24;
fn move_list(skin: usize) -> u32 {
    art_at(skin) + 0x3E0
}
fn move_sheet_at(skin: usize, unit: u8) -> u32 {
    art_at(skin) + 0x1000 * unit as u32
}

/// BIOS LZ77 (type 0x10) decompression.
pub fn lz77_decode(rom: &dyn Rom, at: u32) -> Vec<u8> {
    let head = u32_at(rom, at);
    let n = (head >> 8) as usize;
    let src = rom.read(at + 4, n * 9 / 8 + 64);
    let (mut out, mut p) = (Vec::with_capacity(n), 0usize);
    while out.len() < n && p < src.len() {
        let flags = src[p];
        p += 1;
        for i in 0..8 {
            if out.len() >= n || p >= src.len() {
                break;
            }
            if flags & (0x80 >> i) != 0 {
                let (b1, b2) = (src[p] as usize, src[p + 1] as usize);
                p += 2;
                let (len, disp) = ((b1 >> 4) + 3, ((b1 & 15) << 8 | b2) + 1);
                for _ in 0..len {
                    let v = out[out.len() - disp];
                    out.push(v);
                }
            } else {
                out.push(src[p]);
                p += 1;
            }
        }
    }
    out.truncate(n);
    out
}

/// LZ77 (type 0x10) of `data` as literal blocks only (the game's decompressor takes any valid stream).
pub fn lz77_literal(data: &[u8]) -> Vec<u8> {
    let mut out = vec![0x10, data.len() as u8, (data.len() >> 8) as u8, (data.len() >> 16) as u8];
    for block in data.chunks(8) {
        out.push(0);
        out.extend_from_slice(block);
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

fn frame_grid(sheet: &[u8], f: usize) -> Vec<u8> {
    let mut g = vec![0u8; 24 * 24];
    for k in 0..9 {
        let (cx, cy) = (2 - k % 3, 2 - k / 3);
        let t = &sheet[(f * 9 + k) * 32..][..32];
        for y in 0..8 {
            for x in 0..8 {
                let b = t[y * 4 + x / 2];
                g[(cy * 8 + y) * 24 + cx * 8 + x] = if x & 1 == 1 { b >> 4 } else { b & 15 };
            }
        }
    }
    g
}

fn put_frame(sheet: &mut [u8], f: usize, g: &[u8]) {
    for k in 0..9 {
        let (cx, cy) = (2 - k % 3, 2 - k / 3);
        let t = &mut sheet[(f * 9 + k) * 32..][..32];
        for y in 0..8 {
            for x in (0..8).step_by(2) {
                t[y * 4 + x / 2] = g[(cy * 8 + y) * 24 + cx * 8 + x] | g[(cy * 8 + y) * 24 + cx * 8 + x + 1] << 4;
            }
        }
    }
}

/// The crest: an outline row above the topmost row of the helmet and the helmet's top row in `crest` (moving palette
/// indices: 9 the outline, 14 the skin's crest), a little plume behind on the side views.
pub fn crest_frame(g: &mut [u8], side: bool) {
    const OUTLINE: u8 = 9;
    const CREST: u8 = 14;
    let Some(y0) = (0..24).find(|&y| (0..24).any(|x| g[y * 24 + x] != 0)) else { return };
    let xs: Vec<usize> = (0..24).filter(|&x| g[y0 * 24 + x] != 0).collect();
    let (x0, x1) = (xs[0], xs[xs.len() - 1]);
    for x in x0 + 1..x1 {
        if g[y0 * 24 + x] != OUTLINE {
            g[y0 * 24 + x] = CREST;
        }
    }
    if y0 > 0 {
        for x in x0 + 1..x1 {
            g[(y0 - 1) * 24 + x] = OUTLINE;
        }
    }
    if side && x1 + 2 < 24 && y0 + 2 < 24 {
        // the plume behind the head
        for y in y0 + 1..y0 + 3 {
            g[y * 24 + x1 + 1] = CREST;
            g[y * 24 + x1 + 2] = OUTLINE;
        }
        g[y0 * 24 + x1 + 1] = OUTLINE;
        g[y0 * 24 + x1] = CREST;
    }
}

/// The helmet's top row in a 24x24 moving frame: AW2's outline (moving index 9) and four or more body pixels of the
/// darkest role (5), the first such row from the top; the position of its left outline.
fn helmet_anchor(g: &[u8]) -> Option<(usize, usize)> {
    for y in 0..24 {
        for x in 0..20 {
            if g[y * 24 + x] == 9 && g[y * 24 + x + 1..y * 24 + x + 4].iter().all(|&v| v == 5) {
                return Some((x, y));
            }
        }
    }
    None
}

/// The patches of a foot unit that are laid on moving frame `f`, anchored at the helmet (their hex digits are unit
/// palette roles; the moving sheet keeps them at other indices).
pub fn moving_patches(g: &mut [u8], art: &UnitArt, f: usize) {
    let Some((ax, ay)) = helmet_anchor(g) else { return };
    for p in art.patches.iter().filter(|p| p.moving.contains(&f)) {
        for (dy, row) in p.rows.iter().enumerate() {
            for (dx, c) in row.chars().enumerate() {
                let (x, y) = ((ax + dx) as i32 - p.anchor.0 as i32, (ay + dy) as i32 - p.anchor.1 as i32);
                if !(0..24).contains(&x) || !(0..24).contains(&y) {
                    continue;
                }
                let at = y as usize * 24 + x as usize;
                match c {
                    '.' => {}
                    '_' => g[at] = 0,
                    c => g[at] = MOVE_ROLE[digit(c).unwrap_or(0) as usize] as u8,
                }
            }
        }
    }
}

// ---------- battle figures and portraits ----------

/// AW2's battle-scene figures: the pictures a unit type (Infantry and Mech both use the soldier's, type 1) has for a country are
/// two LZ77 sheets of 32 x 32 frames (16 tiles in rows of four) at the first and the fifth word of its record, `FIG_TABLE[5 * type + country]`
/// (15 words); the scene decompresses the one it needs at `FIG_LOAD` (`sub_08056...`: r0 holds the sheet). The portrait on the unit panel is
/// a 32 x 32 LZ77 picture at `PORTRAIT_TABLE[15 * type + country]` (`sub_0803A190` loads it).
const FIG_TABLE: u32 = 0x085D_64A8;
const PORTRAIT_TABLE: u32 = 0x0849_DC18 + 0x14;
/// The country whose figures the skin's soldiers start from (Green Earth, as the map pictures' `base = 3`).
const FIG_BASE_COUNTRY: u32 = 2;
/// A skin's battle sheets and portraits in free ROM (12 KB each, in the room between the backups and the pictures of [`art_at`]; the ROM image
/// ends at `0x09FE0000`): a table of six words (for Infantry, then Mech: its two sheets and its portrait, 0 for none) and the compressed
/// pictures after it.
fn fig_at(skin: usize) -> u32 {
    DATA + 0x7000 + 0x3000 * skin as u32
}
const FIG_DATA: u32 = 0x20;
const FIG_LIMIT: usize = 0x3000;

/// Where skin `skin`'s sheet `which` (0, 1) of the soldiers of `unit` (1 Infantry, 2 Mech) or its portrait (`which` 2) is, from the table in the ROM image.
fn fig_slot(core: &Core, skin: usize, unit: u8, which: u32) -> u32 {
    let at = core.raw_read_32(fig_at(skin) + 4 * (3 * (unit as u32 - 1) + which), -1);
    // (a word of the table's own room and a LZ77 header only: anything else is not ours, and the game's decompressor would run over its memory with it)
    let room = fig_at(skin) + FIG_DATA..fig_at(skin) + FIG_LIMIT as u32;
    if at % 4 != 0 || !room.contains(&at) || core.raw_read_8(at, -1) != 0x10 {
        return 0;
    }
    at
}

/// GBA LZ77 (type 0x10) compression: greedy, a hash chain of earlier places of the next three bytes; the same bytes every time.
pub fn lz77_compress(data: &[u8]) -> Vec<u8> {
    let n = data.len();
    let mut out = vec![0x10, n as u8, (n >> 8) as u8, (n >> 16) as u8];
    let mut head = vec![usize::MAX; 1 << 12];
    let mut prev = vec![usize::MAX; n];
    let hash = |i: usize| ((data[i] as usize) << 4 ^ (data[i + 1] as usize) << 2 ^ data[i + 2] as usize) & 0xFFF;
    let mut i = 0;
    let mut flags_at = 0;
    let mut bit = 0;
    let insert = |i: usize, head: &mut Vec<usize>, prev: &mut Vec<usize>| {
        if i + 2 < n {
            let h = hash(i);
            prev[i] = head[h];
            head[h] = i;
        }
    };
    while i < n {
        if bit == 0 {
            flags_at = out.len();
            out.push(0);
        }
        let (mut best_len, mut best_at) = (0usize, 0usize);
        if i + 2 < n {
            let mut cand = head[hash(i)];
            let mut tries = 0;
            while cand != usize::MAX && i - cand <= 4096 && tries < 64 {
                let max = (n - i).min(18);
                let len = (0..max).take_while(|&k| data[cand + k] == data[i + k]).count();
                if len > best_len {
                    best_len = len;
                    best_at = cand;
                }
                cand = prev[cand];
                tries += 1;
            }
        }
        if best_len >= 3 {
            out[flags_at] |= 0x80 >> bit;
            let d = i - best_at - 1;
            out.push(((best_len - 3) << 4 | d >> 8) as u8);
            out.push(d as u8);
            for k in 0..best_len {
                insert(i + k, &mut head, &mut prev);
            }
            i += best_len;
        } else {
            out.push(data[i]);
            insert(i, &mut head, &mut prev);
            i += 1;
        }
        bit = (bit + 1) % 8;
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

/// The block of army-coloured pixels (entries 2..5 of the figure palette) above the face (the first row with a skin tone, entries 8..10)
/// of a 32 x 32 frame (`g`), when it is `size` big: its top-left corner. A figure without one (falling over) has none.
pub fn dome_of(g: &[u8], size: (usize, usize)) -> Option<(usize, usize)> {
    let top = (0..32).find(|&y| g[y * 32..y * 32 + 32].iter().any(|&v| v != 0))?;
    let face = (0..32).find(|&y| g[y * 32..y * 32 + 32].iter().any(|&v| (8..=10).contains(&v)))?;
    if face < top + 7 {
        return None;
    }
    let pts: Vec<(usize, usize)> = (top..face).flat_map(|y| (0..32).map(move |x| (x, y))).filter(|&(x, y)| (2..=5).contains(&g[y * 32 + x])).collect();
    let (x0, x1) = (pts.iter().map(|p| p.0).min()?, pts.iter().map(|p| p.0).max()?);
    let (y0, y1) = (pts.iter().map(|p| p.1).min()?, pts.iter().map(|p| p.1).max()?);
    (x1 - x0 + 1 == size.0 && (size.1 - 1..=size.1).contains(&(y1 - y0 + 1))).then_some((x0, y0))
}

/// Lay `p`'s rows on the 32 x 32 frame `g` at the helmet `at`.
pub fn put_fig(g: &mut [u8], at: (usize, usize), p: &FigPatch) {
    for (dy, row) in p.rows.iter().enumerate() {
        for (dx, ch) in row.chars().enumerate() {
            let (x, y) = (at.0 as i32 + p.x + dx as i32, at.1 as i32 + p.y + dy as i32);
            if ch == '.' || !(0..32).contains(&x) || !(0..32).contains(&y) {
                continue;
            }
            g[y as usize * 32 + x as usize] = if ch == '_' { 0 } else { digit(ch).unwrap_or(0) };
        }
    }
}

/// A sheet (or one portrait) of 512-byte frames with the helmet `p` on each frame that has a helmet block.
pub fn patch_figures(sheet: &[u8], p: &FigPatch) -> Vec<u8> {
    let mut out = sheet.to_vec();
    for f in 0..sheet.len() / 512 {
        let mut g = tiles_to_grid(&sheet[f * 512..f * 512 + 512], 4);
        if let Some(at) = dome_of(&g, p.dome) {
            put_fig(&mut g, at, p);
            out[f * 512..f * 512 + 512].copy_from_slice(&grid_to_tiles(&g, 4));
        }
    }
    out
}

fn figure_blobs(rom: &dyn Rom, skin: &Skin, idx: usize, out: &mut Vec<Patch>) {
    let record = u32_at(rom, FIG_TABLE + 4 * (5 + FIG_BASE_COUNTRY));
    let mut table = [0u32; 6];
    let mut data: Vec<u8> = Vec::new();
    let place = |bytes: Vec<u8>, data: &mut Vec<u8>| -> u32 {
        let at = fig_at(idx) + FIG_DATA + data.len() as u32;
        data.extend(&bytes);
        at
    };
    for unit in [1u8, 2] {
        let u = unit as usize - 1;
        if let Some(p) = &skin.battle[u] {
            for which in 0..2u32 {
                if unit == 2 && skin.battle[1] == skin.battle[0] {
                    // (the same helmet on the same sheets: one copy)
                    table[3 + which as usize] = table[which as usize];
                    continue;
                }
                let sheet = lz77_decode(rom, u32_at(rom, record + 16 * which));
                table[3 * u + which as usize] = place(lz77_compress(&patch_figures(&sheet, p)), &mut data);
            }
        }
        if let Some(p) = &skin.portrait[u] {
            let pic = lz77_decode(rom, u32_at(rom, PORTRAIT_TABLE + 4 * (15 * unit as u32 + FIG_BASE_COUNTRY)));
            table[3 * u + 2] = place(lz77_compress(&patch_figures(&pic, p)), &mut data);
        }
    }
    if table.iter().all(|&t| t == 0) {
        return;
    }
    assert!(FIG_DATA as usize + data.len() <= FIG_LIMIT, "the skin's battle pictures do not fit their room");
    let mut head: Vec<u8> = table.iter().flat_map(|t| t.to_le_bytes()).collect();
    head.resize(FIG_DATA as usize, 0);
    out.push(Patch { what: "battle figures: table".to_string(), addr: fig_at(idx), data: head });
    out.push(Patch { what: "battle figures and portraits".to_string(), addr: fig_at(idx) + FIG_DATA, data });
}

/// The scene decompresses a figure sheet (`r0`) for a side (the loop's counter at `sp + 0x20`): a skinned army's soldiers (Infantry and Mech)
/// get the skin's sheet in its place.
const FIG_LOAD: u32 = 0x0805_68E2;
const SIDE_UNITS: u32 = 0x0300_4528;
const SIDE_COLOURS: u32 = 0x0300_4500;

fn fig_sheet(core: &mut Core) {
    let (sp, r0) = {
        let c = core.gba().cpu();
        (c.gpr(13) as u32, c.gpr(0) as u32)
    };
    let side = core.raw_read_32(sp + 0x20, -1);
    if side > 1 {
        return;
    }
    let unit = core.raw_read_32(SIDE_UNITS + 4 * side, -1);
    if !(0x0200_0000..0x0400_0000).contains(&unit) {
        return;
    }
    let ty = core.raw_read_8(unit, -1);
    if !(1..=2).contains(&ty) {
        return;
    }
    let colour = core.raw_read_16(SIDE_COLOURS + 2 * side, -1) as u8 + 1;
    let Some(skin) = skin_installed_on(core, colour) else { return };
    for c in 0..5u32 {
        let record = core.raw_read_32(FIG_TABLE + 4 * (5 + c), -1);
        for which in 0..2u32 {
            if core.raw_read_32(record + 16 * which, -1) == r0 {
                let at = fig_slot(core, skin, ty, which);
                if at != 0 {
                    core.gba_mut().cpu_mut().set_gpr(0, at as i32);
                }
                return;
            }
        }
    }
}

/// The unit panel's and the build menu's portrait (`sub_0803A190`): after it reads the picture's pointer (`r0`); `r8` points at the unit type (a unit's
/// record on the cursor panel, `0x03004100` on the build menu's, the record the menu makes of the unit it shows: the type is its first byte either way),
/// the army is in the panel's state (at `*[*0x08090F70] + 8`). The callers are `0x0803A3FE` and `0x0803A4D0` (the panels opening) and `0x0803AA48` and
/// `0x0803AA9A` (a unit chosen).
///
/// The build menu's call was once left out (a guard on `r8`) because an Emerald Sun army that bought an Infantry or a Mech corrupted the game's memory
/// (the day, the mission's result byte). The call was not the cause: the skin's portrait is the right size for the game's buffer (`0x0200FD50`, 32 x 32 at 4 bits),
/// and the game decompresses it with the same routine as its own. The cause was the skin's room in free ROM: with the skin on colour 5 (a Black Hole
/// army outside a five-army game) the Dual Strike picture palettes' backup of colour 5 sat at `DATA + 0x7000`, over the table of the skin's figures and portraits
/// (`fig_at(0)`); the table's word read as an address in the middle of a palette backup, and the decompressor, handed that, ran over memory. The backups
/// moved below the figures (`ds_backup`, with compile-time checks of the layout) and `fig_slot` takes only a pointer into the skin's own room that starts a
/// LZ77 stream.
const PORTRAIT_LOAD: u32 = 0x0803_A1D8;

fn portrait_blob(core: &mut Core) {
    let r6 = core.gba().cpu().gpr(6) as u32;
    let r8 = core.gba().cpu().gpr(8) as u32;
    if !(0x0200_0000..0x0400_0000).contains(&r8) {
        return;
    }
    let ty = core.raw_read_8(r8, -1);
    if !(1..=2).contains(&ty) {
        return;
    }
    let state = core.raw_read_32(core.raw_read_32(r6, -1), -1);
    if !(0x0200_0000..0x0400_0000).contains(&state) {
        return;
    }
    let army = core.raw_read_8(state + 8, -1) as u32;
    let Some(skin) = skin_of_army(core, army) else { return };
    let at = fig_slot(core, skin, ty, 2);
    if at != 0 {
        core.gba_mut().cpu_mut().set_gpr(0, at as i32);
    }
}

fn moving_blobs(rom: &dyn Rom, skin: &Skin, idx: usize, out: &mut Vec<Patch>) {
    for unit in [1u8, 2] {
        let art = if unit == 1 { &skin.infantry } else { &skin.mech };
        let ptr = u32_at(rom, MOVE_TABLE + MOVE_RECORD * unit as u32 + 4 * (art.base as u32 - 1));
        let mut sheet = lz77_decode(rom, ptr);
        for f in 0..sheet.len() / (9 * 32) {
            if art.patches.iter().any(|p| p.moving.contains(&f)) {
                let mut g = frame_grid(&sheet, f);
                moving_patches(&mut g, art, f);
                put_frame(&mut sheet, f, &g);
            }
        }
        if art.moving_crest {
            for f in 0..sheet.len() / (9 * 32) {
                let mut g = frame_grid(&sheet, f);
                crest_frame(&mut g, f < 3);
                put_frame(&mut sheet, f, &g);
            }
        }
        let data = lz77_literal(&sheet);
        out.push(Patch { what: format!("{} moving sheet", if unit == 1 { "Infantry" } else { "Mech" }), addr: move_sheet_at(idx, unit), data });
        out.push(Patch { what: "moving sheet pointer".to_string(), addr: move_list(idx) + 4 * unit as u32, data: move_sheet_at(idx, unit).to_le_bytes().to_vec() });
    }
}

/// `sub_08035B3C(unit)`: a unit's moving sheet, by the country of its army's CO. At its third instruction (r0 the unit,
/// the first two ran): a skinned army's Infantry and Mech take the skin's sheet (r1 pointing at the word that holds it).
const MOVE_FN: u32 = 0x0803_5B40;
const MOVE_FN_LOAD: u32 = 0x0803_5B5C;

fn moving_sheet(core: &mut Core) {
    let unit = core.gba().cpu().gpr(0) as u32;
    if !(0x0200_0000..0x0400_0000).contains(&unit) {
        return;
    }
    let (army, ty) = (core.raw_read_8(unit + 0x37, -1) as u32 + 1, core.raw_read_8(unit + 0x36, -1));
    if !(1..=2).contains(&ty) {
        return;
    }
    if let Some(skin) = skin_of_army(core, army) {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(1, (move_list(skin) + 4 * ty as u32) as i32);
        cpu.set_thumb_pc(MOVE_FN_LOAD);
    }
}

// ---------- names ----------

/// The game's text table (word per id, tangoAW2's moved copy) and the ids that name an army: by colour 1..5
/// ("Orange Star" .. "Black Hole"), "The ... Army has lost!", and two lists in the order Orange Star, Blue Moon, Yellow
/// Comet, Green Earth, Black Hole.
const TEXT_TABLE: u32 = 0x0861_0A38;
const TEXT_NAME: u32 = 2269;
const TEXT_LOST: u32 = 3221;
const TEXT_LISTS: [u32; 2] = [3288, 3311];
/// By colour (1..5): its place in the lists in the other order.
const LIST_ORDER: [u32; 5] = [0, 1, 3, 2, 4];
fn text_at(skin: usize) -> u32 {
    art_at(skin) + 0x3000
}

fn text_blobs(skin: &Skin, idx: usize, out: &mut Vec<Patch>) {
    let mut put = |at: u32, s: String| {
        let mut b = s.into_bytes();
        b.push(0);
        out.push(Patch { what: "text".to_string(), addr: at, data: b });
    };
    put(text_at(idx), skin.name.clone());
    put(text_at(idx) + 0x20, format!("The {} Army has lost!\x0e\x0e", skin.name));
}

fn text_plan(idx: usize, host: u8, out: &mut Vec<Patch>) {
    let mut point = |id: u32, at: u32| {
        out.push(Patch { what: "army name".to_string(), addr: TEXT_TABLE + 4 * id, data: at.to_le_bytes().to_vec() });
    };
    let k = host as u32 - 1;
    point(TEXT_NAME + k, text_at(idx));
    point(TEXT_LOST + k, text_at(idx) + 0x20);
    for l in TEXT_LISTS {
        point(l + LIST_ORDER[k as usize], text_at(idx));
    }
}

/// Dual Strike's battle figures keep their palettes in the pack, one set per army (colour - 1): the skin's colours for
/// the army a skin sits on (`own` its palette halves, `siblings` the first four armies' of the same unit).
pub fn battle_palettes(core: &Core, army: usize, own: &[[u16; 16]; 2], siblings: &[[[u16; 16]; 2]]) -> [[u16; 16]; 2] {
    let Some(i) = skin_installed_on(core, army as u8 + 1) else { return *own };
    let skin = skin(i);
    std::array::from_fn(|half| {
        let rows: Vec<[u16; 16]> = siblings.iter().map(|s| s[half]).collect();
        skin.hue_row(&own[half], &rows)
    })
}

// ---------- the skinned army's pictures ----------

/// The skin (index) on colour `colour` (1..5) in this console's ROM image, if any: chosen and patched in.
fn skin_installed_on(core: &Core, colour: u8) -> Option<usize> {
    if !(1..=5).contains(&colour) {
        return None;
    }
    let i = applied_on(core, colour)?;
    (host_of(core, i) == colour && core.raw_read_32(art_mark(i), -1) == MAGIC).then_some(i)
}

/// The skin army `army` (1..5) wears.
pub fn skin_of_army(core: &Core, army: u32) -> Option<usize> {
    if !(1..=5).contains(&army) {
        return None;
    }
    skin_installed_on(core, core.raw_read_8(crate::five::players(core) + 0x3C * army + 0x1A, -1))
}

/// Whether army `army` (1..5) wears a skin.
pub fn skinned(core: &Core, army: u32) -> bool {
    skin_of_army(core, army).is_some()
}

/// The map's unit sprite slots of a skin's Infantry and Mech (the game's go to 26; Dual Strike's new units use 59..65,
/// `crate::roster`; the BG map memory begins at tile 0x340): their tiles are at 0x235 + 4 * slot, put there every frame by
/// [`sync_map_art`]. Two for each skin from 52.
fn slot_of(skin: usize, unit: u8) -> u16 {
    52 + 2 * skin as u16 + unit as u16 - 1
}
const _: () = assert!(52 + 2 * MAX_SKINS as u16 <= 59);
/// The map sprite slot a skinned army's unit of type `ty` has (Infantry and Mech: the skin's own pictures), for the renderers that work out
/// a unit's tiles themselves (the Dual Strike tilt reads the unit layer by slot, as `sub_080261A4` does); `None` for any other unit or army.
pub fn map_slot(core: &Core, army: u32, ty: u8) -> Option<u16> {
    if !(1..=2).contains(&ty) {
        return None;
    }
    skin_of_army(core, army).map(|skin| slot_of(skin, ty))
}

/// A skin's slot per unit type (halfwords: 0, Infantry, Mech), for the slot function to read.
fn slot_list(skin: usize) -> u32 {
    art_at(skin) + 0x3F0
}
const SHEET_TILE: u32 = 0x235;
const SHEET_VRAM: u32 = 0x0600_0000 + 32 * SHEET_TILE;
const SLOT_BYTES: u32 = 128;

/// The unit panel and the Design Room's unit bar copy a unit's four tiles of the first frame from the sheet in ROM, the
/// source being the sheet plus the slot's tiles; for a skin's slots (past the sheet) that is the skin's own picture.
pub fn icon_source(core: &Core, src: u32) -> Option<u32> {
    (0..skins().len()).find_map(|i| {
        if core.raw_read_32(art_mark(i), -1) != MAGIC {
            return None;
        }
        (1..=2u8).find(|&u| src == UNIT_SHEET + 128 * slot_of(i, u) as u32).map(|u| map_art(i, u, 0))
    })
}

/// `sub_080261A4(army, type)`: the map sprite slot of a unit, by the country of the army's CO. After its first
/// instruction (r0 the army, r1 the type): a skinned army's Infantry and Mech take the skin's slot.
const SLOT_FN: u32 = 0x0802_61A6;
const SLOT_FN_LOAD: u32 = 0x0802_61BA;

fn unit_slot(core: &mut Core) {
    let (army, ty) = {
        let c = core.gba().cpu();
        (c.gpr(0) as u32 & 0xFFFF, c.gpr(1) as u32 & 0xFFFF)
    };
    if !(1..=2).contains(&ty) {
        return;
    }
    if let Some(skin) = skin_of_army(core, army) {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(4, (slot_list(skin) + 2 * ty) as i32);
        cpu.set_thumb_pc(SLOT_FN_LOAD);
    }
}

/// On the battle map the game copies one of the sheet's three idle frames to the VRAM sheet; the skins' slots,
/// past the sheet, follow it (found by comparing, as `crate::roster` does for Dual Strike's units).
pub fn sync_map_art(core: &mut Core) {
    if (1..=5u8).all(|c| applied_on(core, c).is_none()) {
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
    for i in 0..skins().len() {
        if core.raw_read_32(art_mark(i), -1) != MAGIC || !(1..=5u8).any(|c| applied_on(core, c) == Some(i)) {
            continue;
        }
        for unit in [1u8, 2] {
            let mut want = [0u8; 128];
            core.raw_read_range(map_art(i, unit, f), -1, &mut want);
            let at = SHEET_VRAM + SLOT_BYTES * slot_of(i, unit) as u32;
            let mut have = [0u8; 128];
            core.raw_read_range(at, -1, &mut have);
            if have != want {
                core.raw_write_range(at, -1, &want);
            }
        }
    }
}

/// The skin whose HQ army `army` has: the one it wears, and (a placeholder for a picture of his own) the first skin's for
/// Crumb's.
fn hq_skin(core: &Core, army: u32) -> Option<usize> {
    let co = core.raw_read_8(crate::five::players(core) + 0x3C * army + 0x1D, -1);
    skin_of_army(core, army).or_else(|| (co == crate::co_new::CRUMB && core.raw_read_32(art_mark(0), -1) == MAGIC).then_some(0))
}

/// `sub_0803F5E4(weather, base)`: loads the building sheet and each army's HQ picture (by the country of its CO) into
/// OBJ VRAM; at its end (r6 the first tile, r8 the weather: 1 snow) a skinned army's HQ is the skin's.
const HQ_LOADER_END: u32 = 0x0803_F698;
const HQ_TILES: u32 = 0x5C;
/// Army 5's HQ in a five-army game: the lab's tiles of the sheet (`crate::five::HQ5_TILE` less the sheet's start).
const HQ5_OFFSET: u32 = 0x90 - 0x48;

fn hq_loaded(core: &mut Core) {
    let (base, snow) = {
        let c = core.gba().cpu();
        (c.gpr(6) as u32, (c.gpr(8) as u32 == 1) as usize)
    };
    for army in 1..=5u32 {
        if army == 5 && !crate::five::active(core) {
            continue;
        }
        let Some(skin) = hq_skin(core, army) else { continue };
        let mut art = [0u8; 0x100];
        core.raw_read_range(hq_art(skin, snow), -1, &mut art);
        let tile = if army == 5 { base + HQ5_OFFSET } else { base + HQ_TILES + 8 * (army - 1) } & 0x3FF;
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
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![(SLOT_FN, Box::new(unit_slot)), (MOVE_FN, Box::new(moving_sheet)), (HQ_LOADER_END, Box::new(hq_loaded)), (FIG_LOAD, Box::new(fig_sheet)), (PORTRAIT_LOAD, Box::new(portrait_blob))];
    // `AW2_PAL_LOG=1`: every palette the game loads, with its source (to find what an army's colour reaches).
    if std::env::var_os("AW2_LZ_LOG").is_some() {
        t.push((0x0801_1CAC, Box::new(|core: &mut Core| {
            let c = core.gba().cpu();
            eprintln!("lz src {:08x} dst {:08x} lr {:08x}", c.gpr(0) as u32, c.gpr(1) as u32, c.gpr(14) as u32);
        })));
    }
    if std::env::var_os("AW2_PAL_LOG").is_some() {
        t.push((LOAD_PALETTE, Box::new(log_load)));
        t.push((LOAD_PALETTE_FLUSH, Box::new(log_load)));
    }
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The rooms of the skins' free ROM never overlap (the Dual Strike backup of colour 5 once sat on the first skin's table of figures: a build menu
    /// portrait made the game decompress a palette over its memory).
    #[test]
    fn the_rooms_in_free_rom_are_apart() {
        let mut rooms: Vec<(u32, u32, String)> = vec![(DATA, DATA + 0x100, "header".into())];
        for c in 1..=5u8 {
            rooms.push((backup(c), backup(c) + BACKUP_MAX as u32, format!("backup {c}")));
            rooms.push((ds_backup(c), ds_backup(c) + DS_BACKUP_MAX as u32, format!("Dual Strike backup {c}")));
        }
        for k in 0..MAX_SKINS {
            rooms.push((fig_at(k), fig_at(k) + FIG_LIMIT as u32, format!("figures {k}")));
            rooms.push((art_at(k), art_at(k) + 0x4000, format!("art {k}")));
        }
        for (i, a) in rooms.iter().enumerate() {
            for b in &rooms[i + 1..] {
                assert!(a.1 <= b.0 || b.1 <= a.0, "{} ({:#x}..{:#x}) overlaps {} ({:#x}..{:#x})", a.2, a.0, a.1, b.2, b.0, b.1);
            }
        }
    }

    /// Dual Strike's screens ask the skin for their palettes: the entries the armies differ in take the ramp by brightness, the rest stay.
    #[test]
    fn a_dual_strike_palette_takes_the_skins_ramp() {
        let mut rows = [[0u16; 16]; 5];
        for (c, row) in rows.iter_mut().enumerate() {
            row[1] = 0x7FFF; // white: the same in every army
            for k in 0..4 {
                row[2 + k] = bgr555(((200 - 40 * k) as u8, (20 * (c + 1)) as u8, 30)); // the army's four tones, light to dark
            }
        }
        let out = ds_row(0, &rows[2], &rows);
        assert_eq!(out[1], 0x7FFF, "a shared colour stays");
        let ramp = &skin(0).ramp;
        assert_eq!(out[2], ramp[0], "the lightest army tone is the ramp's lightest");
        assert_eq!(out[5], ramp[5], "the darkest is the ramp's darkest");
        assert!(lum(out[2]) > lum(out[3]) && lum(out[3]) > lum(out[4]) && lum(out[4]) > lum(out[5]));
        assert_eq!(emblem_pixels(0).len(), 256);
    }

    /// The compressor's output decompresses to its input (and is smaller for a picture).
    #[test]
    fn lz77_round_trips() {
        struct Mem(Vec<u8>);
        impl Rom for Mem {
            fn read(&self, addr: u32, len: usize) -> Vec<u8> {
                let a = addr as usize;
                (a..a + len).map(|i| self.0.get(i).copied().unwrap_or(0)).collect()
            }
        }
        let mut data = Vec::new();
        for i in 0..2000u32 {
            data.push(((i / 7) % 5) as u8 * 3 + (i % 3 == 0) as u8);
        }
        data.extend((0..300u32).map(|i| i.wrapping_mul(2654435761u32).wrapping_shr(24) as u8));
        let packed = lz77_compress(&data);
        assert!(packed.len() < data.len());
        assert_eq!(lz77_decode(&Mem(packed), 0), data);
    }

    /// A helmet is found on a standing figure's frame and laid at its corner; a frame without one is left alone.
    #[test]
    fn a_helmet_is_laid_on_the_figures_dome() {
        let mut g = vec![0u8; 32 * 32];
        for y in 4..13 {
            for x in 10..22 {
                g[y * 32 + x] = 3;
            }
        }
        for x in 12..15 {
            g[13 * 32 + x] = 9; // skin
        }
        assert_eq!(dome_of(&g, (12, 9)), Some((10, 4)));
        assert_eq!(dome_of(&g, (11, 9)), None);
        let p = FigPatch { dome: (12, 9), x: 1, y: -2, rows: vec!["ee".to_string(), "_.".to_string()] };
        put_fig(&mut g, (10, 4), &p);
        assert_eq!((g[2 * 32 + 11], g[2 * 32 + 12], g[3 * 32 + 11]), (14, 14, 0));
        assert_eq!(g[3 * 32 + 12], 0);
    }

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
        assert_eq!(assign(&[1, 2, SKIN, 4, 5]), (vec![1, 2, 3, 4, 5], [3, 0, 0]));
        assert_eq!(assign(&[SKIN, 2]), (vec![1, 2], [1, 0, 0]));
        assert_eq!(assign(&[2, SKIN]), (vec![2, 1], [1, 0, 0]));
        assert_eq!(assign(&[1, 2, 3]), (vec![1, 2, 3], [0, 0, 0]));
        // two skins (a second army added to the registry) take the colours that are left, in order
        assert_eq!(assign(&[SKIN + 1, 1, SKIN]), (vec![3, 1, 2], [2, 3, 0]));
    }


    /// With `TANGOAW2_AW2_ROM`: on every colour the plan's writes do not overlap, change what the colour looks like, and put the skin's
    /// ramp where the unit palette's army colours are. `cargo test -p tango-gamesupport-aw2 army_skin -- --ignored`.
    #[test]
    #[ignore]
    fn the_plan_on_the_real_rom() {
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").expect("TANGOAW2_AW2_ROM")).unwrap();
        let rom = RomFile(&rom);
        let skin = emerald_sun();
        for host in 1..=5u8 {
            let plan = plan(&rom, skin, 0, host);
            assert!(plan.len() >= 20, "colour {host}: {} writes", plan.len());
            let mut spans: Vec<(u32, u32)> = plan.iter().map(|p| (p.addr, p.addr + p.data.len() as u32)).collect();
            spans.sort();
            for w in spans.windows(2) {
                assert!(w[0].1 <= w[1].0, "colour {host}: writes overlap at {:#x}", w[1].0);
            }
            let unit = plan.iter().find(|p| p.what == "map units").unwrap();
            let row: Vec<u16> = unit.data.chunks(2).map(|b| u16::from_le_bytes([b[0], b[1]])).collect();
            assert_eq!(&row[2..8], &skin.ramp);
            assert_ne!(unit.data, rom.read(unit.addr, 32), "colour {host}: the unit palette is unchanged");
            // the colour's own entries are in every table the skin patches
            for p in &plan {
                if p.what != "text" && p.what != "army name" {
                    assert_ne!(p.data, rom.read(p.addr, p.data.len()), "colour {host}: {} unchanged", p.what);
                }
            }
        }
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
