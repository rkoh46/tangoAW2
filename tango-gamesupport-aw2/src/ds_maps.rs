//! Dual Strike's maps, read from the Dual Strike pack and converted to
//! Advance Wars 2's terms at run time (nothing of either game is in the
//! repository): one reader for any Dual Strike map id, which Survival
//! ([`crate::survival_maps`]) builds its maps from.
//!
//! Where Dual Strike (USA) keeps them: the header table `Ov000_gMapHeaders`,
//! overlay 0 (loaded at 0x022AD560) `0x022DBD28`, 0xA0 bytes per map id, ids
//! 0..0x10C (the decomp's `include/game/map_header.h`). A header:
//!
//! | Offset | What |
//! |---|---|
//! | +0x0C | the `bmap` file of its 4x4 structure's picture ("0a5" the missile pad, "0a6" the fortress; 0: none) |
//! | +0x10 | the second map of a two-map battle (its id; 0: none) |
//! | +0x14 | the name (a text id of the general bank) |
//! | +0x1A, +0x1B, +0x1C | look (0 Normal, 1 Snow, 2 Desert, 3 Wasteland), weather (0 clear, 1 snow, 2 rain, 3 sandstorm), fog |
//! | +0x24 | armies |
//! | +0x26 | the case: which list offers the map (2..6 Versus' Classic, Vs., Pre-Deployed, 3P, 4P; 7 the War Room, 8 a War Room battle's second map; 9 Survival) |
//! | +0x2C, +0x2E | par days (the speed score's), normal and hard |
//! | +0x44 | the tiles: LZ77 of width, height, then a u16 per cell in AW2's own tile ids, grown ([`convert_tile`]) |
//! | +0x4C | the pre-deployed units: 13-byte records (x, y, type, flags, HP, ammo, fuel, cargo, AI, -, AI x, AI y); `FE army` starts an army, `FF` ends |
//! | +0x54 | (front CO, back CO) per army slot 0..4, Dual Strike CO ids (0x1C: the player picks; 0: none) |
//! | +0x88, +0x8D | colour (1 Orange Star .. 5 Black Hole) and team, per army slot 0..4 |
//!
//! Names: Dual Strike's text table, overlay 0 `0x02306954` (a pointer per
//! text id to an ASCII string).
//!
//! Terrain: Dual Strike uses AW2's tile ids (its maps came from AW2's
//! format), plus a few of its own: 0x1A1 the Black Crystal (tangoAW2's
//! 0x192, [`crate::obelisk`]), 0x146/0x147 two more mountains (Dual Strike
//! draws every mountain cell as one of 0x020, 0x146, 0x147 by position,
//! [`crate::ds_look`]) and 0x1B9..0x1BD the Com Tower, neutral and armies
//! 1..4 (tangoAW2's Com Tower is the Lab, 0x1D9..0x1DD,
//! [`crate::com_tower`]). Everything else is AW2's own tile: pipes, reefs,
//! silos, minicannons, structures (the 4x4 blocks 0x1AA..0x1AD and
//! 0x1AE..0x1B1 are the same tiles AW2's T Minus 15 and Sea Fortress use).

/// Overlay 0's load address, the header table and a header's size.
pub const OV0: u32 = 0x022A_D560;
pub const HEADERS: u32 = 0x022D_BD28;
pub const HEADER: u32 = 0xA0;
/// The ids with a header (`MAP_COUNT`).
pub const IDS: u16 = 0x10D;
const TEXT: u32 = 0x0230_6954;

/// `MapHeader.mapCase`: the Versus lists (Classic .. 4P Maps), the War Room,
/// a War Room battle's second map, Survival.
pub const CASE_VERSUS_FIRST: u16 = 2;
pub const CASE_VERSUS_LAST: u16 = 6;
pub const CASE_WAR_ROOM: u16 = 7;
pub const CASE_WAR_ROOM_SECOND: u16 = 8;
pub const CASE_SURVIVAL: u16 = 9;
/// A CO slot the player fills (`co[slot][k]`).
const PICK: u8 = 0x1C;

/// A unit placed on a map: army 1.., position, tangoAW2 unit type, HP
/// (0..100), ammo, fuel.
#[derive(Clone, Debug, PartialEq)]
pub struct Unit {
    pub army: u8,
    pub x: u8,
    pub y: u8,
    pub kind: u8,
    pub hp: u8,
    pub ammo: u8,
    pub fuel: u8,
}

/// The 4x4 structures some maps stand on their map (tiles 0x1AA..0x1AD and
/// 0x1AE..0x1B1). Dual Strike's pictures of them (`bmap/0a5`, `bmap/0a6`)
/// are byte for byte AW2's (`0x080D2DA8`, `0x080D38AC`, which T Minus 15 /
/// Final Front and Show Stopper / Sea Fortress name in their headers'
/// +0x10).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Structure {
    MissilePad,
    Fortress,
}

impl Structure {
    /// AW2's picture: the map header's `tileGraphic4x4` (+0x10), which
    /// `LoadInventionGraphics` (`0x0803FD80`) loads into OBJ VRAM.
    pub fn aw2_picture(self) -> u32 {
        match self {
            Structure::MissilePad => 0x080D_2DA8,
            Structure::Fortress => 0x080D_38AC,
        }
    }
    /// The structure the tiles show.
    pub fn of_tiles(tiles: &[u16]) -> Option<Structure> {
        if tiles.iter().any(|t| (0x1AA..=0x1AD).contains(t)) {
            Some(Structure::MissilePad)
        } else if tiles.iter().any(|t| (0x1AE..=0x1B1).contains(t)) {
            Some(Structure::Fortress)
        } else {
            None
        }
    }
}

/// A Dual Strike map, converted.
#[derive(Clone, Debug)]
pub struct Map {
    /// Dual Strike's map id.
    pub ds_id: u16,
    pub name: String,
    pub width: u8,
    pub height: u8,
    /// AW2 tile ids, row by row (converted).
    pub tiles: Vec<u16>,
    pub units: Vec<Unit>,
    pub armies: u8,
    /// Colour of armies 1..4 (1 Orange Star .. 5 Black Hole).
    pub colours: [u8; 4],
    /// Team of armies 1..4.
    pub teams: [u8; 4],
    /// Each army's (front, back) CO as tangoAW2 CO ids, armies 1..4 (None:
    /// none, or the player's pick: [`Map::picks`]).
    pub cos: [(Option<u8>, Option<u8>); 4],
    /// The armies whose front CO the player picks.
    pub picks: [bool; 4],
    pub fog: bool,
    /// 0 clear, 1 snow, 2 rain, 3 sandstorm.
    pub weather: u8,
    /// Dual Strike's look: 0 normal, 1 snow, 2 desert, 3 wasteland.
    pub look: u8,
    /// Par days, normal and hard (the speed score's; Survival's day limit).
    pub par: (u16, u16),
    /// Which list offers the map (`CASE_*`).
    pub case: u16,
    /// The second map of a two-map battle (its Dual Strike id), if any.
    pub second: Option<u16>,
    /// The picture of the map's 4x4 structure, for maps with one.
    pub structure: Option<Structure>,
}

impl Map {
    /// The computer armies' front COs (armies 2..4).
    pub fn cpu_cos(&self) -> [Option<u8>; 3] {
        [self.cos[1].0, self.cos[2].0, self.cos[3].0]
    }
}

/// Dual Strike's tile -> tangoAW2's.
pub fn convert_tile(t: u16) -> u16 {
    match t {
        0x1A1 => 0x192,                     // Black Crystal
        // Dual Strike's other two mountains: AW2's mountain, as the DS
        // Campaign's maps (crate::ds_campaign_data).
        0x146 | 0x147 => 0x022,
        0x1B9..=0x1BD => t - 0x1B9 + 0x1D9, // Com Tower: the Lab tiles
        _ => t,
    }
}

/// Dual Strike's unit type -> tangoAW2's (Carrier and Oozium move up one).
pub fn convert_unit(t: u8) -> Option<u8> {
    match t {
        1..=24 => Some(t),
        25 => Some(crate::roster::CARRIER),
        26 => Some(crate::roster::OOZIUM),
        _ => None,
    }
}

/// Dual Strike's CO id -> tangoAW2's.
pub fn convert_co(ds: u8) -> Option<u8> {
    (0..crate::co_roster::AW2_COS)
        .chain(crate::co_new::FIRST..crate::co_new::FIRST + crate::co_new::NEW.len() as u8)
        .find(|&co| crate::co_roster::ds_co(co) == Some(ds))
}

/// Overlay 0 and its text, from the pack.
pub struct Reader<'a> {
    pack: &'a crate::ds_pack::Pack,
}

impl<'a> Reader<'a> {
    pub fn new(pack: &'a crate::ds_pack::Pack) -> Self {
        Reader { pack }
    }
    fn ov(&self, at: u32, len: usize) -> Option<&'a [u8]> {
        self.pack.overlay_at(0, OV0, at, len)
    }
    pub fn u8(&self, at: u32) -> Option<u8> {
        self.ov(at, 1).map(|b| b[0])
    }
    pub fn u16(&self, at: u32) -> Option<u16> {
        self.ov(at, 2).map(|b| u16::from_le_bytes([b[0], b[1]]))
    }
    pub fn u32(&self, at: u32) -> Option<u32> {
        self.ov(at, 4).map(|b| u32::from_le_bytes(b.try_into().unwrap()))
    }
    /// A text of the general table by its id.
    pub fn text(&self, id: u16) -> Option<String> {
        let p = self.u32(TEXT + 4 * id as u32)?;
        let mut s = String::new();
        for k in 0..64 {
            let c = self.u8(p + k)?;
            if c == 0 {
                break;
            }
            s.push(c as char);
        }
        Some(s)
    }

    /// A map's header (None past the table).
    pub fn header(&self, id: u16) -> Option<&'a [u8]> {
        (id < IDS).then(|| self.ov(HEADERS + HEADER * id as u32, HEADER as usize)).flatten()
    }

    /// The map with Dual Strike id `id`, converted. None for an id without
    /// map data (0, the Design Room's slots) or a damaged pack.
    pub fn map(&self, id: u16) -> Option<Map> {
        let h = self.header(id)?;
        let w32 = |o: usize| u32::from_le_bytes(h[o..o + 4].try_into().unwrap());
        let w16 = |o: usize| u16::from_le_bytes([h[o], h[o + 1]]);
        let name = self.text(w16(0x14))?;
        let tiles_at = w32(0x44);
        let head = self.ov(tiles_at, 4)?;
        let len = (u32::from_le_bytes(head.try_into().unwrap()) >> 8) as usize;
        let raw = crate::ds_art::lz10(self.ov(tiles_at, len * 9 / 8 + 16).or_else(|| self.ov(tiles_at, len + 4))?)?;
        let (w, ht) = (raw[0], raw[1]);
        let tiles: Vec<u16> = (0..w as usize * ht as usize)
            .map(|k| Some(convert_tile(u16::from_le_bytes([*raw.get(2 + 2 * k)?, *raw.get(3 + 2 * k)?]))))
            .collect::<Option<_>>()?;
        let mut units = Vec::new();
        let mut p = w32(0x4C);
        let mut army = 0;
        while p != 0 {
            let r = self.ov(p, 13)?;
            p += 13;
            match r[0] {
                0xFF => break,
                0xFE => army = r[1],
                _ => {
                    if let Some(kind) = convert_unit(r[2]) {
                        units.push(Unit { army, x: r[0], y: r[1], kind, hp: r[4], ammo: r[5], fuel: r[6] });
                    }
                }
            }
            if units.len() > 400 {
                return None;
            }
        }
        let co = |v: u8| if v == 0 || v == PICK { None } else { convert_co(v) };
        let mut cos = [(None, None); 4];
        let mut picks = [false; 4];
        for k in 0..4 {
            cos[k] = (co(h[0x56 + 2 * k]), co(h[0x57 + 2 * k]));
            picks[k] = h[0x56 + 2 * k] == PICK;
        }
        let structure = match w32(0x0C) {
            0 => None,
            p => {
                let name: String = (0..3).filter_map(|k| self.u8(p + k)).map(|c| c as char).collect();
                match name.as_str() {
                    "0a5" => Some(Structure::MissilePad),
                    "0a6" => Some(Structure::Fortress),
                    _ => None,
                }
            }
        }
        .or_else(|| Structure::of_tiles(&tiles));
        Some(Map {
            ds_id: id,
            name,
            width: w,
            height: ht,
            tiles,
            units,
            armies: h[0x24],
            colours: [h[0x89], h[0x8A], h[0x8B], h[0x8C]],
            teams: [h[0x8E], h[0x8F], h[0x90], h[0x91]],
            cos,
            picks,
            fog: h[0x1C] != 0,
            weather: h[0x1B],
            look: h[0x1A],
            par: (w16(0x2C), w16(0x2E)),
            case: w16(0x26),
            second: Some(w16(0x10)).filter(|&v| v != 0),
            structure,
        })
    }
}

/// The map with Dual Strike id `id` from the pack in use.
pub fn read(id: u16) -> Option<Map> {
    Reader::new(crate::ds_pack::pack()?).map(id)
}

// --- AW2's form ------------------------------------------------------------------

/// Each pre-deployed unit's AI byte (record +9): 4, the one tangoAW2's
/// Versus maps use, under which the computer moves every unit (with 0, as
/// many campaign units have, it keeps some where they stand).
pub const UNIT_AI: u8 = 4;

/// A map's tiles as AW2 loads them (LZ77 of width, height, tiles, padded to
/// a word) and its units (12-byte records; FE army, FF end).
pub fn blobs(map: &Map) -> (Vec<u8>, Vec<u8>) {
    let mut raw = vec![map.width, map.height];
    for t in &map.tiles {
        raw.extend_from_slice(&t.to_le_bytes());
    }
    let mut lz = crate::lz77::compress(&raw);
    while lz.len() % 4 != 0 {
        lz.push(0);
    }
    let mut units = Vec::new();
    for army in 1..=4u8 {
        let mine: Vec<&Unit> = map.units.iter().filter(|u| u.army == army).collect();
        if mine.is_empty() {
            continue;
        }
        units.extend_from_slice(&[0xFE, army, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        for u in mine {
            units.extend_from_slice(&[u.x, u.y, u.kind, 0, u.hp, u.ammo, u.fuel, 0, 0, UNIT_AI, 0, 0]);
        }
    }
    units.extend_from_slice(&[0xFF; 1]);
    units.extend_from_slice(&[0; 11]);
    (lz, units)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tiles_convert() {
        assert_eq!(convert_tile(0x1A1), 0x192);
        assert_eq!(convert_tile(0x146), 0x022);
        assert_eq!(convert_tile(0x1B9), 0x1D9);
        assert_eq!(convert_tile(0x1BD), 0x1DD);
        assert_eq!(convert_tile(0x02A), 0x02A);
        assert_eq!(convert_unit(25), Some(crate::roster::CARRIER));
        assert_eq!(convert_unit(0), None);
    }

    /// With a Dual Strike ROM (TANGOAW2_DS_ROM): the Versus and War Room
    /// maps read as Dual Strike has them.
    #[test]
    fn maps_from_the_rom() {
        let Some(path) = std::env::var_os("TANGOAW2_DS_ROM") else { return };
        let Ok(buf) = std::fs::read(path) else { return };
        crate::ds_art::offer(&buf);
        let m = |id| read(id).unwrap_or_else(|| panic!("map {id:#x}"));
        let bean = m(0x01);
        assert_eq!((bean.name.as_str(), bean.width, bean.height, bean.armies, bean.case), ("Bean Island", 16, 15, 2, 2));
        assert_eq!(bean.colours, [1, 2, 3, 4]);
        assert!(bean.units.is_empty() && bean.picks == [false; 4] && bean.cos[1] == (None, None));
        // Pre-deployed: Crater Reef, 28 units an army.
        let reef = m(0x47);
        assert_eq!((reef.name.as_str(), reef.armies, reef.units.len()), ("Crater Reef", 4, 112));
        // Dark City's snow, Clover Pond's Wasteland and sandstorm.
        assert_eq!(m(0x88).weather, 1);
        let clover = m(0x89);
        assert_eq!((clover.look, clover.weather), (3, 3));
        // The War Room: Spann Island, Andy; Lost Basin's teams; Whiplash's
        // second map and colours; Watery Downs' Black Hole army.
        let spann = m(0x8B);
        assert_eq!((spann.name.as_str(), spann.case, spann.picks[0]), ("Spann Island", CASE_WAR_ROOM, true));
        assert_eq!(spann.cos[1].0, convert_co(2)); // Andy (Dual Strike id 2)
        assert_eq!(m(0x9B).teams[..3], [1, 2, 2]);
        let whiplash = m(0xB3);
        assert_eq!((whiplash.name.as_str(), whiplash.second), ("Whiplash", Some(0xB8)));
        assert_eq!(whiplash.colours[..3], [1, 3, 2]);
        assert_eq!(m(0xB8).case, CASE_WAR_ROOM_SECOND);
        // Every Versus and War Room map fits AW2: 0x508 cells, 40 rows, its
        // tile ids, 51 units an army.
        for id in 1..=0xBB {
            let map = m(id);
            assert!(map.width as usize * map.height as usize <= 0x508 && map.height <= 40, "{}", map.name);
            assert!(map.tiles.iter().all(|&t| t < 0x200), "{}", map.name);
            for a in 1..=4 {
                assert!(map.units.iter().filter(|u| u.army == a).count() <= 50, "{}", map.name);
            }
            let (lz, units) = blobs(&map);
            assert!(lz.len() + units.len() <= 0x1000, "{}", map.name);
            assert!((2..=4).contains(&map.armies), "{}", map.name);
        }
    }
}
