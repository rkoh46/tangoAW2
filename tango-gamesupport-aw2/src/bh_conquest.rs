//! The BH Campaign's conquest of AW2's own world map: when a mission is won, its part of the land turns Black Hole's colours (dark purple, the
//! BH2 picture map's look, `world_picture`), so the map shows how far Black Hole has come (docs/dev/worldmap.md "AW2's own map").
//!
//! - **How AW2 draws the map.** BG3 is a 512 x 256 layer: tiles (LZ77, 704 of them), a tilemap of 2 x 32 x 32 cells and ten palettes (BG banks 6..15). The nations'
//!   land is in banks 11 (Orange Star), 12 (Blue Moon), 13 (Yellow Comet), 14 (Green Earth) and 10 (Black Hole's island at the top, grey); each bank also holds
//!   the sea (entries 10..14), the labels and the region borders (entry 15). Land is entries 1..=9. Banks 6..9 are the nations' vivid colours of AW2's own campaign
//!   and no cell of the tilemap uses them in a session.
//! - **Conquest.** Entries 1..=9 of a bank are re-tinted (same lightness mapping as the picture map: dark purple to light purple). Black Hole's island (bank 10)
//!   is Black Hole's from the start. A nation's other banks get a dark twin: banks 6..9 become the tinted copies of banks 11..14, and the tilemap cells of the
//!   conquered land point at the twin. The land is split into the regions AW2's white (entry 15) border lines enclose (the dashed lines are widened by two
//!   pixels, a flood fill per bank, specks join the land beside them; a cell goes to the region most of its land pixels are in). A region holding the flag of a
//!   won mission is dark; a region with no flag goes with the nearest flagged region of its nation; when all of a nation's missions are won all its land is dark.
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

/// One of AW2's white-bordered regions of a nation's land.
pub struct Region {
    pub bank: u16,
    /// The centre of its land pixels.
    pub centre: (f64, f64),
}

/// What the ROM's map is made of.
pub struct Layout {
    /// The tilemap entries as the ROM has them (two screens, row by row).
    pub map: Vec<u16>,
    /// The palettes (banks 6..15, 16 entries each).
    pub pal: Vec<u16>,
    /// Per cell: it draws land (a few pixels of entries 1..=9).
    pub land: Vec<bool>,
    /// The regions the white border lines (entry 15) enclose.
    pub regions: Vec<Region>,
    /// Per cell: its region (the one most of its land pixels are in).
    pub cell_region: Vec<Option<usize>>,
    /// Per map pixel (512 x 256): its region.
    pix: Vec<i32>,
}

const W: usize = 512;
const H: usize = 256;
/// A region's core is at least this many pixels (smaller specks join the land around them); borders are dashed, so they are widened by this many
/// pixels before the regions are told apart.
const MIN_REGION: usize = 40;
const GAP: usize = 2;

/// The cell's place (cell x, cell y) on the 64 x 32 layer.
fn cell_xy(i: usize) -> (i32, i32) {
    let (screen, within) = (i / 1024, i % 1024);
    ((screen * 32 + within % 32) as i32, (within / 32) as i32)
}

impl Layout {
    /// Reads the map's cells, finds the land, the border lines and the regions between them.
    pub fn new(map: Vec<u16>, pal: Vec<u16>, tiles: &[u8]) -> Layout {
        // the pixels: entry and bank per map pixel
        let mut idx = vec![0u8; W * H];
        let mut bank = vec![0u16; W * H];
        let mut land = vec![false; map.len()];
        for (i, &e) in map.iter().enumerate() {
            let (cx, cy) = cell_xy(i);
            let t = (e & 0x3FF) as usize;
            let (hf, vf, b) = (e >> 10 & 1 != 0, e >> 11 & 1 != 0, e >> 12);
            let Some(px) = tiles.get(t * 32..t * 32 + 32) else { continue };
            let mut n = 0;
            for y in 0..8 {
                for x in 0..8 {
                    let (yy, xx) = (if vf { 7 - y } else { y }, if hf { 7 - x } else { x });
                    let byte = px[yy * 4 + xx / 2];
                    let v = if xx & 1 != 0 { byte >> 4 } else { byte & 15 };
                    let at = (cy as usize * 8 + y) * W + cx as usize * 8 + x;
                    idx[at] = v;
                    bank[at] = b;
                    n += (1..=9).contains(&v) as usize;
                }
            }
            land[i] = b >= 10 && n >= 6;
        }
        let is_land = |at: usize| bank[at] >= 10 && (1..=9).contains(&idx[at]);
        let mut wall: Vec<bool> = (0..W * H).map(|at| bank[at] >= 10 && idx[at] == 15).collect();
        for _ in 0..GAP {
            let prev = wall.clone();
            for y in 0..H {
                for x in 0..W {
                    if !prev[y * W + x] {
                        'n: for dy in -1i32..=1 {
                            for dx in -1i32..=1 {
                                let (ny, nx) = (y as i32 + dy, x as i32 + dx);
                                if ny >= 0 && nx >= 0 && (ny as usize) < H && (nx as usize) < W && prev[ny as usize * W + nx as usize] {
                                    wall[y * W + x] = true;
                                    break 'n;
                                }
                            }
                        }
                    }
                }
            }
        }
        // the cores: land away from the borders, connected within a bank; the small ones are left out
        let mut pix = vec![-1i32; W * H];
        let mut n = 0i32;
        let step = |at: usize| {
            let (y, x) = (at / W, at % W);
            [(y > 0).then(|| at - W), (y + 1 < H).then(|| at + W), (x > 0).then(|| at - 1), (x + 1 < W).then(|| at + 1)]
        };
        let mut seen = vec![false; W * H];
        for start in 0..W * H {
            if seen[start] || !is_land(start) || wall[start] {
                continue;
            }
            let mut comp = vec![start];
            seen[start] = true;
            let mut k = 0;
            while k < comp.len() {
                let at = comp[k];
                k += 1;
                for nb in step(at).into_iter().flatten() {
                    if !seen[nb] && is_land(nb) && !wall[nb] && bank[nb] == bank[start] {
                        seen[nb] = true;
                        comp.push(nb);
                    }
                }
            }
            if comp.len() >= MIN_REGION {
                for &at in &comp {
                    pix[at] = n;
                }
                n += 1;
            }
        }
        // the rest of the land (the widened borders, specks) joins the nearest core
        let mut queue: std::collections::VecDeque<usize> = (0..W * H).filter(|&at| pix[at] >= 0).collect();
        while let Some(at) = queue.pop_front() {
            for nb in step(at).into_iter().flatten() {
                if pix[nb] < 0 && is_land(nb) && bank[nb] == bank[at] {
                    pix[nb] = pix[at];
                    queue.push_back(nb);
                }
            }
        }
        let mut sums = vec![(0.0f64, 0.0f64, 0usize, 0u16); n as usize];
        for at in 0..W * H {
            if pix[at] >= 0 {
                let s = &mut sums[pix[at] as usize];
                s.0 += (at % W) as f64;
                s.1 += (at / W) as f64;
                s.2 += 1;
                s.3 = bank[at];
            }
        }
        let regions = sums.iter().map(|s| Region { bank: s.3, centre: (s.0 / s.2.max(1) as f64, s.1 / s.2.max(1) as f64) }).collect();
        let cell_region = (0..map.len())
            .map(|i| {
                let (cx, cy) = cell_xy(i);
                let mut count = std::collections::HashMap::new();
                for y in 0..8 {
                    for x in 0..8 {
                        let r = pix[(cy as usize * 8 + y) * W + cx as usize * 8 + x];
                        if r >= 0 {
                            *count.entry(r).or_insert(0) += 1;
                        }
                    }
                }
                count.into_iter().max_by_key(|&(r, c)| (c, -r)).map(|(r, _)| r as usize)
            })
            .collect();
        Layout { map, pal, land, regions, cell_region, pix }
    }

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

    /// The region of the land pixel nearest a map point.
    fn region_at(&self, x: i32, y: i32) -> Option<usize> {
        for r in 0..48i32 {
            let mut best: Option<(i32, usize)> = None;
            for dy in -r..=r {
                for dx in -r..=r {
                    if dx.abs().max(dy.abs()) != r {
                        continue;
                    }
                    let (px, py) = (x + dx, y + dy);
                    if px >= 0 && py >= 0 && (px as usize) < W && (py as usize) < H {
                        let p = self.pix[py as usize * W + px as usize];
                        if p >= 0 && best.is_none_or(|b| dx * dx + dy * dy < b.0) {
                            best = Some((dx * dx + dy * dy, p as usize));
                        }
                    }
                }
            }
            if let Some((_, p)) = best {
                return Some(p);
            }
        }
        None
    }

    /// The regions drawn dark when the missions at `points` flagged in `won` are won. A region with flags in it is dark when one of them is won; a region
    /// without goes with the nearest flagged region of its nation; a nation with all its missions won is dark whole.
    pub fn dark_regions(&self, points: &[(i16, i16)], won: u32) -> Vec<bool> {
        let is_won = |m: usize| m < 31 && won & (1 << m) != 0;
        let n = self.regions.len();
        let home: Vec<Option<usize>> = points.iter().map(|&(x, y)| self.region_at(x as i32, y as i32)).collect();
        let mut flagged = vec![false; n];
        let mut dark = vec![false; n];
        for (m, h) in home.iter().enumerate() {
            if let Some(r) = *h {
                flagged[r] = true;
                dark[r] |= is_won(m);
            }
        }
        let base = dark.clone();
        for r in 0..n {
            let bank = self.regions[r].bank;
            if flagged[r] {
                continue;
            }
            let (cx, cy) = self.regions[r].centre;
            let near = (0..n).filter(|&q| flagged[q] && self.regions[q].bank == bank).min_by(|&a, &b| {
                let d = |q: usize| (self.regions[q].centre.0 - cx).powi(2) + (self.regions[q].centre.1 - cy).powi(2);
                d(a).total_cmp(&d(b))
            });
            dark[r] = near.is_some_and(|q| base[q]);
        }
        for bank in self.conquered_banks(points, won) {
            (0..n).filter(|&r| self.regions[r].bank == bank).for_each(|r| dark[r] = true);
        }
        dark
    }

    /// The nations (banks 11..=14) whose missions, by the region of their flags, are all won.
    fn conquered_banks(&self, points: &[(i16, i16)], won: u32) -> Vec<u16> {
        let is_won = |m: usize| m < 31 && won & (1 << m) != 0;
        let home: Vec<Option<usize>> = points.iter().map(|&(x, y)| self.region_at(x as i32, y as i32)).collect();
        (11..=14u16)
            .filter(|&bank| {
                let ms: Vec<usize> = (0..points.len()).filter(|&m| home[m].is_some_and(|r| self.regions[r].bank == bank)).collect();
                !ms.is_empty() && ms.iter().all(|&m| is_won(m))
            })
            .collect()
    }

    /// The cells drawn dark (see [`Layout::dark_regions`]); a cell is in the region most of its land is in.
    pub fn dark_cells(&self, points: &[(i16, i16)], won: u32) -> Vec<bool> {
        let dark = self.dark_regions(points, won);
        let done = self.conquered_banks(points, won);
        (0..self.map.len())
            .map(|i| {
                let b = self.bank(i);
                (11..=14).contains(&b) && match self.cell_region[i] {
                    Some(r) => dark[r],
                    // (a speck of land too small to be a region: with its nation)
                    None => self.land[i] && done.contains(&b),
                }
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
        Some(Layout::new(map, pal, &tiles))
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

    /// Bank 11's land in three rows of cells: columns 0..4 (a region), a border column, 5..9 (a region), a border column, 10..13 (a region without a flag).
    fn toy() -> Layout {
        let mut map = vec![0u16; 2048];
        for r in 0..3 {
            for c in 0..14 {
                map[r * 32 + c] = 11 << 12 | if c == 4 || c == 9 { 2 } else { 1 };
            }
        }
        let mut tiles = vec![0u8; 3 * 32];
        tiles[32..64].fill(0x33);
        tiles[64..96].fill(0xFF);
        Layout::new(map, (0..160).map(|i| 0x6000 | i as u16).collect(), &tiles)
    }

    fn dark_cols(l: &Layout, d: &[bool]) -> Vec<usize> {
        (0..14).filter(|&c| (0..3).all(|r| d[r * 32 + c])).collect()
    }

    #[test]
    fn the_borders_split_the_land_into_regions() {
        let l = toy();
        assert_eq!(l.regions.len(), 3);
        assert!(l.cell_region[4].is_none() && l.cell_region[0] != l.cell_region[5] && l.cell_region[5] != l.cell_region[10]);
    }

    #[test]
    fn a_won_mission_darkens_its_whole_region_and_an_unflagged_one_follows_its_neighbour() {
        let l = toy();
        let pts = [(8i16, 12i16), (56, 12)];
        assert!(l.dark_cells(&pts, 0).iter().all(|&d| !d));
        assert_eq!(dark_cols(&l, &l.dark_cells(&pts, 1)), vec![0, 1, 2, 3], "the left region only");
        assert_eq!(dark_cols(&l, &l.dark_cells(&pts, 2)), vec![5, 6, 7, 8, 10, 11, 12, 13], "the right region and the one with no flag beside it");
        assert_eq!(dark_cols(&l, &l.dark_cells(&pts, 3)), vec![0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13], "all missions won: the whole nation");
    }

    #[test]
    fn dark_cells_use_the_twin_banks_and_the_palette_twins_are_tinted() {
        let l = toy();
        let dark = l.dark_cells(&[(8, 12), (56, 12)], 1);
        let map = l.tilemap(&dark);
        assert_eq!(u16::from_le_bytes([map[0], map[1]]) >> 12, 6, "bank 11's twin is 6");
        assert_eq!(u16::from_le_bytes([map[2 * 5], map[2 * 5 + 1]]) >> 12, 11, "an open region keeps its bank");
        let pal = l.palette();
        let at = |bank: usize, k: usize| u16::from_le_bytes([pal[(bank * 16 + k) * 2], pal[(bank * 16 + k) * 2 + 1]]);
        assert_eq!(at(0, 10), l.pal[5 * 16 + 10], "the twin's sea entries are the nation's own");
        assert_eq!(at(0, 3), tint(l.pal[5 * 16 + 3]));
        assert_eq!(at(4, 3), tint(l.pal[4 * 16 + 3]), "Black Hole's island is tinted from the start");
        assert_eq!(at(0, 15), l.pal[5 * 16 + 15], "the border entry keeps its colour");
    }

    #[test]
    fn tint_runs_from_dark_to_light_and_keeps_order() {
        let (dark, light) = (tint(0x0000), tint(0x7FFF));
        assert_ne!(dark, light);
        let lum = |c: u16| (c & 31) + (c >> 5 & 31) + (c >> 10 & 31);
        assert!(lum(dark) < lum(light));
        assert!(lum(tint(0x6F9F)) < lum(light) + 1);
    }
}
