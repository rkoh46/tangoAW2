//! The BH Campaign's conquest of AW2's own world map: when a mission is won, its part of the land turns Black Hole's colours (dark purple, the
//! BH2 picture map's look, `world_picture`), so the map shows how far Black Hole has come (docs/dev/worldmap.md "AW2's own map").
//!
//! - **How AW2 draws the map.** BG3 is a 512 x 256 layer: tiles (LZ77, 704 of them), a tilemap of 2 x 32 x 32 cells and ten palettes (BG banks 6..15). The nations'
//!   land is in banks 11 (Orange Star), 12 (Blue Moon), 13 (Yellow Comet), 14 (Green Earth) and 10 (Black Hole's island at the top, grey); each bank also holds
//!   the sea (entries 10..14), the labels and the region borders (entry 15). Land is entries 1..=9. Banks 6..9 are the nations' vivid colours of AW2's own campaign
//!   and no cell of the tilemap uses them in a session.
//! - **Conquest.** Entries 1..=9 of a bank are re-tinted (same lightness mapping as the picture map: dark purple to light purple). Black Hole's island (bank 10)
//!   is Black Hole's from the start. A nation's other banks get a dark twin: banks 6..9 become the tinted copies of banks 11..14, and the tilemap cells of the
//!   conquered land point at the twin. A cell belongs to the mission whose flag is nearest among the nation's (the nation of a flag is the bank of the nearest
//!   land cell), so progress shows mission by mission; when all of a nation's missions are won all its land is dark.
//! - **Where it lives.** The campaign's own copies of the tilemap (LZ77) and the palettes sit in the ROM image ([`TILEMAP`], [`PALETTE`]); in a BH Campaign
//!   session the map screen's literal-pool words point at them (`ds_worldmap::tick`), so the screen's setup, fades and a saved game's Continue all draw
//!   the conquest. With the map up the tilemap in VRAM and the palette RAM are rewritten when the set of won missions changes. Nothing outside the BH
//!   Campaign's session (AW2's campaign, the DS and ES campaigns, the BH2 and Gauntlet modes) uses it, and no ROM data is stored: the layout is read from
//!   the ROM at run time.

use mgba::core::Core;
use std::sync::OnceLock;

const TILES_ROM: u32 = 0x081C_C5F0;
const TILEMAP_ROM: u32 = 0x081D_0BAC;
const PALETTE_ROM: u32 = 0x081D_1504;
/// The campaign's copies in the ROM image (`ds_worldmap::BASE`'s block).
pub const TILEMAP: u32 = crate::ds_worldmap::BASE + 0xC000;
pub const PALETTE: u32 = crate::ds_worldmap::BASE + 0xE000;
/// The set of won missions (bit m) the image's copies are drawn for, with [`VALID`].
const IMAGE_SET: u32 = crate::ds_worldmap::BASE + 0xB910;
/// The set the live tilemap and palette RAM show.
const LIVE_SET: u32 = crate::ds_worldmap::BASE + 0xB914;
const VALID: u32 = 1 << 31;
/// BG3's tilemap (screens 30 and 31) in VRAM.
const BG3_MAP: u32 = 0x0600_F000;
/// BG palette bank 6 in the palette buffer and palette RAM.
const BANK6: u32 = 0xC0;

/// The BH Campaign's source index (`campaign_model::SOURCES`).
const BH_SOURCE: usize = 1;

/// The BH colours (the picture map's `[tint]`: dark and light purple) and the lightness range of AW2's land they stretch over.
const DARK: [f64; 3] = [48.0, 34.0, 70.0];
const LIGHT: [f64; 3] = [128.0, 106.0, 150.0];
const LO: f64 = 190.0;
const HI: f64 = 255.0;

/// The BH Campaign's session is on.
pub fn on(core: &Core) -> bool {
    crate::ds_campaign::active(core) && crate::ds_campaign::source(core) == BH_SOURCE
}

/// A land colour as Black Hole's (BGR555).
pub fn tint(c: u16) -> u16 {
    let ch = [(c & 31) as f64 * 255.0 / 31.0, ((c >> 5) & 31) as f64 * 255.0 / 31.0, ((c >> 10) & 31) as f64 * 255.0 / 31.0];
    let lum = ch[0] * 0.3 + ch[1] * 0.59 + ch[2] * 0.11;
    let u = ((lum - LO) / (HI - LO)).clamp(0.0, 1.0);
    let q = |k: usize| ((DARK[k] * (1.0 - u) + LIGHT[k] * u) / 255.0 * 31.0).round() as u16;
    q(0) | q(1) << 5 | q(2) << 10
}

/// What the ROM's map is made of.
pub struct Layout {
    /// The tilemap entries as the ROM has them (two screens, row by row).
    pub map: Vec<u16>,
    /// The palettes (banks 6..15, 16 entries each).
    pub pal: Vec<u16>,
    /// Per cell: it draws land (a few pixels of entries 1..=9).
    pub land: Vec<bool>,
}

/// The cell's place (cell x, cell y) on the 64 x 32 layer.
fn cell_xy(i: usize) -> (i32, i32) {
    let (screen, within) = (i / 1024, i % 1024);
    ((screen * 32 + within % 32) as i32, (within / 32) as i32)
}

impl Layout {
    pub fn bank(&self, i: usize) -> u16 {
        self.map[i] >> 12
    }

    /// The tilemap with the cells in `dark` pointing at the twin banks 6..9.
    pub fn tilemap(&self, dark: &[bool]) -> Vec<u8> {
        let mut out = Vec::with_capacity(self.map.len() * 2);
        for (i, &e) in self.map.iter().enumerate() {
            let b = e >> 12;
            let e = if dark.get(i).copied().unwrap_or(false) && (11..=14).contains(&b) { (e & 0x0FFF) | (b - 5) << 12 } else { e };
            out.extend_from_slice(&e.to_le_bytes());
        }
        out
    }

    /// The ten palettes: Black Hole's island (bank 10) tinted, banks 6..9 the tinted twins of the nations' 11..14.
    pub fn palette(&self) -> Vec<u8> {
        let mut pal = self.pal.clone();
        let tinted = |bank: usize, p: &[u16]| -> Vec<u16> { (0..16).map(|k| if (1..=9).contains(&k) { tint(p[bank * 16 + k]) } else { p[bank * 16 + k] }).collect() };
        for twin in 0..4 {
            let t = tinted(twin + 5, &self.pal);
            pal[twin * 16..twin * 16 + 16].copy_from_slice(&t);
        }
        let island = tinted(4, &self.pal);
        pal[4 * 16..5 * 16].copy_from_slice(&island);
        pal.iter().flat_map(|c| c.to_le_bytes()).collect()
    }

    /// The nation (bank) of a map point: the bank of the nearest land cell.
    fn nation_at(&self, x: i32, y: i32) -> Option<u16> {
        (0..self.map.len())
            .filter(|&i| self.land[i])
            .min_by_key(|&i| {
                let (cx, cy) = cell_xy(i);
                (cx * 8 + 4 - x).pow(2) + (cy * 8 + 4 - y).pow(2)
            })
            .map(|i| self.bank(i))
    }

    /// The cells drawn dark when the missions at `points` flagged in `won` are won: a nation's land cell goes to the nearest of the nation's flags;
    /// it is dark when that mission is won, or when all the nation's missions are.
    pub fn dark_cells(&self, points: &[(i16, i16)], won: u32) -> Vec<bool> {
        let nation: Vec<Option<u16>> = points.iter().map(|&(x, y)| self.nation_at(x as i32, y as i32)).collect();
        let is_won = |m: usize| m < 31 && won & (1 << m) != 0;
        (0..self.map.len())
            .map(|i| {
                let b = self.bank(i);
                if !self.land[i] || !(11..=14).contains(&b) {
                    return false;
                }
                let (cx, cy) = cell_xy(i);
                let mine: Vec<usize> = (0..points.len()).filter(|&m| nation[m] == Some(b)).collect();
                let Some(&near) = mine.iter().min_by_key(|&&m| {
                    let (x, y) = points[m];
                    (cx * 8 + 4 - x as i32).pow(2) + (cy * 8 + 4 - y as i32).pow(2)
                }) else {
                    return false;
                };
                is_won(near) || mine.iter().all(|&m| is_won(m))
            })
            .collect()
    }
}

/// The ROM's map (read once).
pub fn layout(core: &Core) -> Option<&'static Layout> {
    static L: OnceLock<Option<Layout>> = OnceLock::new();
    L.get_or_init(|| {
        let mut raw = vec![0u8; 0x8000];
        core.raw_read_range(TILES_ROM, -1, &mut raw);
        let tiles = crate::ds_art::lz10(&raw)?;
        let mut raw = vec![0u8; 0x2000];
        core.raw_read_range(TILEMAP_ROM, -1, &mut raw);
        let map = crate::ds_art::lz10(&raw)?;
        if map.len() != 0x1000 || tiles.len() % 32 != 0 {
            return None;
        }
        let mut pal_raw = vec![0u8; 320];
        core.raw_read_range(PALETTE_ROM, -1, &mut pal_raw);
        let map: Vec<u16> = map.chunks(2).map(|c| u16::from_le_bytes([c[0], c[1]])).collect();
        let pal: Vec<u16> = pal_raw.chunks(2).map(|c| u16::from_le_bytes([c[0], c[1]])).collect();
        let land = map
            .iter()
            .map(|&e| {
                let t = (e & 0x3FF) as usize;
                let Some(px) = tiles.get(t * 32..t * 32 + 32) else { return false };
                e >> 12 >= 10 && px.iter().flat_map(|&b| [b & 15, b >> 4]).filter(|v| (1..=9).contains(v)).count() >= 6
            })
            .collect();
        Some(Layout { map, pal, land })
    })
    .as_ref()
}

/// The set of won missions of the session (bit m: mission m cleared).
fn won_set(core: &Core, n: usize) -> u32 {
    (0..n.min(31)).fold(0u32, |a, m| a | ((core.raw_read_8(crate::ds_worldmap::S_FLAGS + m as u32, -1) & crate::ds_worldmap::CLEARED != 0) as u32) << m)
}

/// Every frame of a BH Campaign session: the image's copies follow the won missions; with the map up (`live`) so do the tilemap in VRAM and the palette RAM.
/// Returns false when the copies are not in place (the pool words then keep AW2's art).
pub fn tick(core: &mut Core, live: bool) -> bool {
    let Some(l) = layout(core) else { return false };
    let pts = crate::ds_worldmap::points(core);
    let now = won_set(core, pts.len()) | VALID;
    if core.raw_read_32(IMAGE_SET, -1) != now {
        let dark = l.dark_cells(&pts, now & !VALID);
        let map = crate::lz77::compress(&l.tilemap(&dark));
        assert!(map.len() <= 0x2000, "the tilemap's copy fits");
        core.raw_write_range(TILEMAP, -1, &map);
        core.raw_write_range(PALETTE, -1, &l.palette());
        core.raw_write_32(IMAGE_SET, -1, now);
    }
    if !live {
        core.raw_write_32(LIVE_SET, -1, now);
    } else if core.raw_read_32(LIVE_SET, -1) != now {
        let dark = l.dark_cells(&pts, now & !VALID);
        core.raw_write_range(BG3_MAP, -1, &l.tilemap(&dark));
        crate::ds_worldmap::write_palettes(core, BANK6, &l.palette());
        core.raw_write_32(LIVE_SET, -1, now);
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A map of two nations' land side by side: bank 11 left (cells 0..4), bank 12 right (cells 4..8), one row (the rest is sea).
    fn toy() -> Layout {
        let mut map = vec![0u16; 2048];
        let mut land = vec![false; 2048];
        for c in 0..8 {
            map[c] = (if c < 4 { 11 } else { 12 }) << 12 | 5;
            land[c] = true;
        }
        let pal = (0..160).map(|i| 0x6000 | i as u16).collect();
        Layout { map, pal, land }
    }

    #[test]
    fn tint_runs_from_dark_to_light_and_keeps_order() {
        let (dark, light) = (tint(0x0000), tint(0x7FFF));
        assert_ne!(dark, light);
        let lum = |c: u16| (c & 31) + (c >> 5 & 31) + (c >> 10 & 31);
        assert!(lum(dark) < lum(light));
        assert!(lum(tint(0x6F9F)) < lum(light) + 1);
    }

    #[test]
    fn a_won_mission_darkens_its_nearest_cells_and_a_whole_nation_all_of_its() {
        let l = toy();
        // two missions in nation 11 (cells 0..4: x 4..32), one in nation 12
        let pts = [(4i16, 4i16), (28, 4), (50, 4)];
        let none = l.dark_cells(&pts, 0);
        assert!(none.iter().all(|&d| !d));
        let first = l.dark_cells(&pts, 1);
        assert_eq!((0..8).filter(|&c| first[c]).collect::<Vec<_>>(), vec![0, 1], "the first mission's half");
        let nation = l.dark_cells(&pts, 0b011);
        assert_eq!((0..8).filter(|&c| nation[c]).collect::<Vec<_>>(), vec![0, 1, 2, 3], "all missions of a nation: all its land");
        let other = l.dark_cells(&pts, 0b100);
        assert_eq!((0..8).filter(|&c| other[c]).collect::<Vec<_>>(), vec![4, 5, 6, 7]);
    }

    #[test]
    fn dark_cells_use_the_twin_banks_and_the_palette_twins_are_tinted() {
        let l = toy();
        let dark = l.dark_cells(&[(4, 4), (28, 4), (50, 4)], 0b100);
        let map = l.tilemap(&dark);
        assert_eq!(u16::from_le_bytes([map[0], map[1]]) >> 12, 11, "unconquered cells keep their bank");
        assert_eq!(u16::from_le_bytes([map[8], map[9]]) >> 12, 7, "bank 12's twin is 7");
        let pal = l.palette();
        let at = |bank: usize, k: usize| u16::from_le_bytes([pal[(bank * 16 + k) * 2], pal[(bank * 16 + k) * 2 + 1]]);
        assert_eq!(at(1, 10), l.pal[(6 * 16) + 10], "the twin's sea entries are the nation's own");
        assert_eq!(at(1, 3), tint(l.pal[6 * 16 + 3]));
        assert_eq!(at(4, 3), tint(l.pal[4 * 16 + 3]), "Black Hole's island is tinted from the start");
        assert_eq!(at(0, 15), l.pal[5 * 16 + 15], "the border entry keeps its colour");
    }
}
