//! A campaign world map made from a picture (`WorldArt::Picture`): the owner's artwork converted by `aw2dev worldmap convert` into GBA
//! background tiles, nine palettes, a region mask per nation and the Black Hole colours of every nation's entries (docs/dev/worldmap.md).
//! The converted file (`art/worldmap/<name>.bin`, format in `devkit/aw2/worldmaplib/binfmt.py`) is checked in; nothing is read from a ROM.
//!
//! - Tiles and palettes go where Omega Land's go ([`crate::ds_worldmap`]: the map layer's 767 tiles beside a blank one, BG palettes 6..14).
//! - **Regions.** Every pixel has a class (0 the sea, 1.. the nations). A mission's flag lies in a nation; once every mission whose flag is in
//!   a nation is won, the nation is *conquered* and its palette entries (the ones tagged with it) are drawn in Black Hole's colours.
//! - The map is at most 512 x 256 (the map layer); the camera and cursor stop at its edges.

use std::sync::OnceLock;

/// The conversion's file for the BH2 Campaign's map.
pub static BH2: PictureSource = PictureSource::new("bh2", include_bytes!("../art/worldmap/bh2_world.bin"));

/// The nations' names by class number (class 0 is the sea).
pub const REGION_NAMES: [&str; 6] = ["Sea", "Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole"];

/// The class of Black Hole's own island (the grey island, bottom left). It is Black Hole's from the start: [`PictureMap::conquered`] always
/// includes it, so it is drawn in Black Hole's colours, and its missions (M1, M2, M26) never change it.
pub const BLACK_HOLE_REGION: u8 = 5;

/// Where each mission's flag stands on the BH2 picture: (mission number, nation class, x, y) in map pixels (docs/dev/bh2-maps.md). Every flag must lie inside
/// its own nation's mask (`world_picture::tests::bh2_flags_lie_in_their_nation`, `aw2dev bh2 check`). M1, M2 and the secret M26 are on Black Hole's island,
/// M3 to M5 in Green Earth's south. The rest of the campaign's flags are placed with their missions.
pub const BH2_FLAGS: &[(u8, u8, i16, i16)] = &[
    (1, 5, 38, 204),
    (2, 5, 18, 214),
    (3, 3, 96, 173),
    (4, 3, 150, 215),
    (5, 3, 115, 140),
    (6, 4, 203, 194),
    (7, 4, 190, 176),
    (8, 4, 222, 168),
    (9, 4, 235, 92),
    (10, 4, 222, 130),
    (11, 2, 120, 100),
    (12, 2, 198, 46),
    (13, 2, 112, 76),
    (14, 2, 168, 22),
    (15, 1, 100, 44),
    (16, 1, 106, 56),
    (17, 1, 60, 48),
    (18, 5, 28, 198),
    (19, 1, 60, 80),
    (20, 1, 90, 72),
    (21, 1, 108, 36),
    (22, 1, 44, 80),
    (23, 1, 24, 40),
    (24, 1, 80, 30),
    (25, 1, 60, 60),
    (26, 5, 30, 222),
];

/// A converted picture, parsed on first use.
pub struct PictureSource {
    pub name: &'static str,
    bin: &'static [u8],
    parsed: OnceLock<PictureMap>,
}

impl PictureSource {
    pub const fn new(name: &'static str, bin: &'static [u8]) -> PictureSource {
        PictureSource {
            name,
            bin,
            parsed: OnceLock::new(),
        }
    }

    pub fn map(&'static self) -> &'static PictureMap {
        self.parsed
            .get_or_init(|| PictureMap::parse(self.bin).unwrap_or_else(|e| panic!("world map {}: {e}", self.name)))
    }
}

impl PartialEq for PictureSource {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name
    }
}
impl Eq for PictureSource {}
impl std::fmt::Debug for PictureSource {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Picture({})", self.name)
    }
}

pub struct PictureMap {
    pub width: u16,
    pub height: u16,
    /// 4bpp tiles as the GBA wants them (32 bytes each; tile 0 blank).
    pub tiles: Vec<u8>,
    /// The tilemap entries, row-major (`width / 8` by `height / 8`).
    pub cells: Vec<u16>,
    /// BGR555: 9 palettes of 16; the same as Black Hole's land; the class each entry draws.
    pub palette: Vec<u16>,
    pub tinted: Vec<u16>,
    pub tags: Vec<u8>,
    /// The class of every pixel, row-major.
    pub mask: Vec<u8>,
    /// Dummy flag places (class, x, y) for the development aid.
    pub slots: Vec<(u8, i16, i16)>,
}

fn rd16(b: &[u8], o: usize) -> Result<u16, String> {
    Ok(u16::from_le_bytes(b.get(o..o + 2).ok_or("truncated")?.try_into().unwrap()))
}

impl PictureMap {
    pub fn parse(b: &[u8]) -> Result<PictureMap, String> {
        if b.get(0..4) != Some(b"PWM1") {
            return Err("not a PWM1 file".into());
        }
        let (w, h, nt) = (rd16(b, 4)?, rd16(b, 6)?, rd16(b, 8)? as usize);
        let npal = *b.get(10).ok_or("truncated")? as usize;
        let mut o = 12;
        let tiles = b.get(o..o + 32 * nt).ok_or("truncated tiles")?.to_vec();
        o += 32 * nt;
        let ncell = (w as usize / 8) * (h as usize / 8);
        let cells = (0..ncell).map(|i| rd16(b, o + 2 * i)).collect::<Result<Vec<_>, _>>()?;
        o += 2 * ncell;
        let palette = (0..npal * 16).map(|i| rd16(b, o + 2 * i)).collect::<Result<Vec<_>, _>>()?;
        o += 2 * npal * 16;
        let tinted = (0..npal * 16).map(|i| rd16(b, o + 2 * i)).collect::<Result<Vec<_>, _>>()?;
        o += 2 * npal * 16;
        let tags = b.get(o..o + npal * 16).ok_or("truncated tags")?.to_vec();
        o += npal * 16;
        let runs = u32::from_le_bytes(b.get(o..o + 4).ok_or("truncated")?.try_into().unwrap()) as usize;
        o += 4;
        let mut mask = Vec::with_capacity(w as usize * h as usize);
        for _ in 0..runs {
            let v = *b.get(o).ok_or("truncated mask")?;
            let n = rd16(b, o + 1)? as usize;
            mask.extend(std::iter::repeat(v).take(n));
            o += 3;
        }
        if mask.len() != w as usize * h as usize {
            return Err("the mask does not cover the picture".into());
        }
        let ns = *b.get(o).ok_or("truncated")? as usize;
        o += 1;
        let mut slots = Vec::new();
        for _ in 0..ns {
            slots.push((*b.get(o).ok_or("truncated")?, rd16(b, o + 1)? as i16, rd16(b, o + 3)? as i16));
            o += 5;
        }
        if o != b.len() {
            return Err("trailing bytes".into());
        }
        Ok(PictureMap {
            width: w,
            height: h,
            tiles,
            cells,
            palette,
            tinted,
            tags,
            mask,
            slots,
        })
    }

    /// The nation (1..) at a map pixel; 0 the sea or off the map.
    pub fn region_at(&self, x: i32, y: i32) -> u8 {
        if x < 0 || y < 0 || x >= self.width as i32 || y >= self.height as i32 {
            return 0;
        }
        self.mask[y as usize * self.width as usize + x as usize]
    }

    /// The map layer's tilemap as the screen wants it: two 32 x 32 screens side by side (the cells past the picture blank).
    pub fn tilemap(&self) -> Vec<u8> {
        let cols = self.width as usize / 8;
        let mut out = vec![0u8; 0x1000];
        for (i, &e) in self.cells.iter().enumerate() {
            let (cx, cy) = (i % cols, i / cols);
            let at = 0x800 * (cx / 32) + 2 * (32 * cy + cx % 32);
            out[at..at + 2].copy_from_slice(&e.to_le_bytes());
        }
        out
    }

    /// The nine palettes' bytes with the nations in `conquered` (bit n = class n) drawn as Black Hole's.
    pub fn palette_bytes(&self, conquered: u8) -> Vec<u8> {
        let mut out = Vec::with_capacity(self.palette.len() * 2);
        for (i, &c) in self.palette.iter().enumerate() {
            let t = self.tags[i];
            let c = if t != 0 && t < 8 && conquered & (1 << t) != 0 { self.tinted[i] } else { c };
            out.extend_from_slice(&c.to_le_bytes());
        }
        out
    }

    /// The nations conquered: bit n is set when class n has missions and every one of them (by the place of its flag) is won.
    pub fn conquered(&self, points: &[(i16, i16)], won: impl Fn(usize) -> bool) -> u8 {
        let (mut total, mut done) = ([0u32; 8], [0u32; 8]);
        for (m, &(x, y)) in points.iter().enumerate() {
            let r = self.region_at(x as i32, y as i32) as usize;
            if r != 0 && r < 8 {
                total[r] += 1;
                done[r] += won(m) as u32;
            }
        }
        // (Black Hole's own island is Black Hole's from the start, whatever its missions)
        (1..8)
            .filter(|&r| r == BLACK_HOLE_REGION as usize || (total[r] > 0 && total[r] == done[r]))
            .fold(0u8, |a, r| a | 1 << r)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bh2_parses_and_keeps_the_budgets() {
        let m = BH2.map();
        assert!(m.tiles.len() / 32 <= 768, "the map layer holds 768 tiles");
        assert_eq!(m.palette.len(), 9 * 16, "BG palettes 6..14");
        assert!(m.width % 8 == 0 && m.height % 8 == 0 && m.width <= 512 && m.height <= 256);
        assert!(m.tiles[..32].iter().all(|&b| b == 0), "tile 0 is blank");
        for &e in &m.cells {
            assert!((e & 0x3FF) as usize * 32 < m.tiles.len());
            assert!((6..15).contains(&(e >> 12)), "palette {}", e >> 12);
        }
        // every slot lies inside its nation
        for &(r, x, y) in &m.slots {
            assert_eq!(m.region_at(x as i32, y as i32), r);
        }
        assert!(m.slots.len() >= 31, "a flag place for each of the BH Campaign's 31 missions");
        assert_eq!(m.tilemap().len(), 0x1000);
    }

    #[test]
    fn bh2_flags_lie_in_their_nation() {
        let m = BH2.map();
        for &(mission, region, x, y) in BH2_FLAGS {
            assert_eq!(m.region_at(x as i32, y as i32), region, "M{mission}'s flag at ({x}, {y}) is not inside {}", REGION_NAMES[region as usize]);
            assert!(region != 0, "M{mission}'s flag is on the sea");
        }
        // the owner's plan: M1, M2 and M26 on Black Hole's island, M3 to M5 in Green Earth, M6 to M10 in Yellow Comet, M11 to M14 in Blue Moon, M15 to M20 in Orange Star (M18 on Black Hole's own island)
        for &(mission, region, ..) in BH2_FLAGS {
            let want = if matches!(mission, 1 | 2 | 18 | 26) { BLACK_HOLE_REGION } else if mission >= 15 { 1 } else if mission >= 11 { 2 } else if mission >= 6 { 4 } else { 3 };
            assert_eq!(region, want, "M{mission}");
        }
    }

    #[test]
    fn every_nation_has_land_and_entries_to_tint() {
        let m = BH2.map();
        for r in 1..REGION_NAMES.len() as u8 {
            assert!(m.mask.iter().any(|&v| v == r), "{} has no land", REGION_NAMES[r as usize]);
            assert!(m.tags.iter().any(|&v| v == r), "{} has no palette entries", REGION_NAMES[r as usize]);
        }
    }

    #[test]
    fn conquest_tints_only_the_conquered_nation() {
        let m = BH2.map();
        let base = m.palette_bytes(0);
        let os = m.palette_bytes(1 << 1);
        assert_ne!(base, os);
        for (i, (a, b)) in base.chunks(2).zip(os.chunks(2)).enumerate() {
            assert_eq!(a != b, m.tags[i] == 1 && m.palette[i] != m.tinted[i], "entry {i}");
        }
        // a nation is conquered when all of its missions are won, and only then
        let pts: Vec<(i16, i16)> = m.slots.iter().filter(|s| s.0 == 1 || s.0 == 2).map(|s| (s.1, s.2)).collect();
        let os_n = m.slots.iter().filter(|s| s.0 == 1).count();
        let home = 1 << BLACK_HOLE_REGION;
        assert_eq!(m.conquered(&pts, |i| i < os_n), home | 1 << 1);
        assert_eq!(m.conquered(&pts, |i| i + 1 < os_n), home);
        assert_eq!(m.conquered(&pts, |_| true), home | (1 << 1) | (1 << 2));
    }
}
