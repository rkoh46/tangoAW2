//! tangoAW2's Versus maps (five/maps.txt): their tiles, units and names in
//! the ROM image's free space, through map-table entries the game never
//! uses ([`IDS`]). The 5-army ones are listed on a new Versus tab, "5P
//! Maps"; the 2-, 3- and 4-army ones on the game's own tabs. Maps with a
//! Black Crystal or Obelisk are listed only with their art, maps with Dual
//! Strike content (Com Towers, Piperunners, the Wasteland look) only with
//! the Dual Strike pack ([`show_maps`]). Also
//! Black Hole's own property tiles
//! (0x1B4..0x1B9), which army 5 owns: they look like the other property
//! tiles (the buildings are sprites drawn over plain grass).

use mgba::core::Core;

use crate::five_map_data::MAPS;

/// The game's map table: 0xC0 entries of 0x5C bytes, one per map id.
const GAME_MAP_TABLE: u32 = 0x085C_77A0;
const GAME_MAP_IDS: u32 = 0xC0;
pub(crate) const ENTRY: u32 = 0x5C;
/// tangoAW2 copies it to free space in the ROM image with room for more,
/// and gives the game the copy: every literal-pool word pointing at the
/// table (or at a field of its first entry: +0x3C, +0x40), and the two
/// loops that walk it (`sub_080206B0`, find a map by its tiles, and the
/// map list builder at `0x08037482`), which stop after id 0xBF.
pub(crate) const MAP_TABLE: u32 = 0x0865_0000;
/// The table has a row for every byte id (the pool above reaches 0xFF); the copies in crate::survival and crate::ds_versus are sized for it.
pub(crate) const MAP_IDS: u32 = 0x100;
pub(crate) const TABLE_POINTERS: [(u32, u32); 37] = [
    (0x0801_96EC, 0x00),
    (0x0802_06E0, 0x00),
    (0x0802_4814, 0x00),
    (0x0802_492C, 0x00),
    (0x0802_4970, 0x00),
    (0x0802_49B8, 0x00),
    (0x0802_63E8, 0x00),
    (0x0802_6AE4, 0x00),
    (0x0802_6D38, 0x00),
    (0x0802_C678, 0x00),
    (0x0802_C7D4, 0x00),
    (0x0802_C814, 0x00),
    (0x0803_4750, 0x40),
    (0x0803_477C, 0x00),
    (0x0803_500C, 0x00),
    (0x0803_6600, 0x3C),
    (0x0803_74D4, 0x00),
    (0x0803_BD4C, 0x00),
    (0x0803_C1D0, 0x40),
    (0x0803_E404, 0x00),
    (0x0803_FDCC, 0x00),
    (0x0804_3650, 0x00),
    (0x0806_17E0, 0x00),
    (0x0806_ADC4, 0x00),
    (0x0806_AF64, 0x00),
    (0x0807_73A8, 0x00),
    (0x0807_7558, 0x00),
    (0x0807_7B68, 0x40),
    (0x0807_8E8C, 0x00),
    (0x0807_B900, 0x00),
    (0x0807_BA5C, 0x00),
    (0x0807_C5C4, 0x00),
    (0x0807_F6D4, 0x00),
    (0x0808_7C04, 0x3C),
    (0x0809_0A6C, 0x00),
    (0x0809_0D68, 0x00),
    (0x0809_0EC0, 0x00),
];
/// `cmp rN, #0xBF` in the two loops: the game's, then the last id without
/// the Dual Strike pack (0xC0), then with it (0xFD, past the Colonel's Vault at 0xF1 and the pool of new maps; a bound of 0xFF would never end (the id counter is a byte) and 0xFE is ds_versus::BATTLE_ID: the ids between, [`BIG_FIVE_ID`]'s among them,
/// are Dual Strike content and walked only with the pack, [`show_maps`]).
const TABLE_LOOPS: [(u32, u16, u16, u16); 2] = [
    (0x0802_06C8, 0x29BF, 0x29C0, 0x29FD),
    (0x0803_74B4, 0x2CBF, 0x2CC0, 0x2CFD),
];
/// Each map's tiles and units: 4 KiB apiece, in one run from [`MAP_DATA`] in the ROM image's free space past the Dual Strike Versus maps
/// (0x09C00000..0x09CFFFFF, crate::ds_versus): room for [`MAP_CAPACITY`] maps (0x09D00000..0x09D3FFFF; the free run goes on to the Dual
/// Strike Normal look at 0x09E00000, so the capacity can grow to 256 by changing one constant).
pub(crate) const MAP_DATA: u32 = 0x09D0_0000;
const MAP_DATA_SIZE: u32 = 0x1000;
pub const MAP_CAPACITY: usize = 64;
/// The moved map table ends before the next owner of free ROM (the design-map owner table, crate::design5).
const MAP_TABLE_LIMIT: u32 = 0x0866_0000;

pub(crate) fn map_data(k: usize) -> u32 {
    MAP_DATA + MAP_DATA_SIZE * k as u32
}

/// Tile -> terrain table (copied to RAM when a map loads) and metatiles.
const TERRAIN_TABLE: u32 = 0x080C_1BC4;
const METATILES: u32 = 0x080B_FBC4;
const NEUTRAL_HQ_TILE: u32 = 0x1C0;
/// Army 5's HQ, base, city, airport, port and lab.
const ARMY5_TILES: [(u32, u8); 6] = [
    (0x1B4, 0xA8),
    (0x1B5, 0xAE),
    (0x1B6, 0xA6),
    (0x1B7, 0xAA),
    (0x1B8, 0xAB),
    (0x1B9, 0xB4),
];

/// The map list's tabs run 2..8 (Classic .. Design Maps); these raise the
/// last one to 9, the 5P tab: (address, original, patched).
const TAB_BOUNDS: [(u32, u16, u16); 6] = [
    (0x0808_5AFA, 0x3008, 0x3009), // init: clear the cursor memory of tabs 0..9
    (0x0808_5C52, 0x2008, 0x2009), // setup: skipping empty tabs wraps to 9
    (0x0808_64A4, 0x2008, 0x2009), // L/Left wraps 2 -> 9
    (0x0808_64D6, 0x2008, 0x2009),
    (0x0808_65A4, 0x2808, 0x2809), // R/Right reaches 9, then wraps to 2
    (0x0808_65D6, 0x2808, 0x2809),
];
pub const CATEGORY: u16 = 9;
/// Each map's id, in five/maps.txt's order: map-table entry 0 (a dummy the
/// game never lists), design-map ids 0xB8..0xBF (the Design Room has three
/// slots, 0xB4..0xB6, and a suspend copy, 0xB7; the rest serve only
/// multi-cartridge link play), and 0xC0.., past the game's own table.
pub use crate::five_map_data::IDS;
/// Free ids for new maps: the pool five/map.py hands out (0xF2..=0xFD, 12 ids; five/map_ids.txt). A map there is pack content: the Versus list
/// walks the ids past 0xC0 only with the Dual Strike pack on.
pub const NEW_ID_POOL: std::ops::RangeInclusive<u8> = 0xF2..=0xFD;
/// The big pre-deployed 5-army map (Pentagon Atoll: Megatanks, Stealths and T-Copters, so the pack's): the first id
/// past the Dual Strike maps'.
pub const BIG_FIVE_ID: u8 = 0xC9;
/// The Colonel's Vault (the BH Campaign's prize map), past Survival's ids
/// (0xC9..0xEF, with the Champion courses) and the campaigns' mission map
/// (0xF0); the walk of the map list reaches it with the pack on
/// ([`show_maps`]) and [`MAP_SHOWN`] lets it list.
pub const VAULT_ID: u8 = 0xF1;

/// Map ids 0xB4..0xBF are design maps to the game. These make 0xB8..0xBF
/// ordinary maps (header blob, name, unit list, preview): (address,
/// original, patched).
const ORDINARY_IDS: &[(u32, u16, u16)] = &[
    // (u8)(id + 0x4C) <= 0xB, the design range 0xB4..0xBF -> 0xB4..0xB7
    (0x0801_6D6E, 0x280B, 0x2803), // suspend save
    (0x0801_6DDA, 0x280B, 0x2803), // suspend load
    (0x0801_701C, 0x280B, 0x2803), // suspend tile changes
    (0x0801_733C, 0x280B, 0x2803), // resume
    (0x0801_73E6, 0x280B, 0x2803), // resume: changed tiles
    (0x0802_164C, 0x280B, 0x2803), // map setup
    (0x0802_1828, 0x280B, 0x2803), // property census
    (0x0802_47B0, 0x280B, 0x2803), // LoadMapData
    (0x0802_4918, 0x280B, 0x2803), // army count
    (0x0802_4950, 0x280B, 0x2803), // name
    (0x0803_C158, 0x280B, 0x2803), // Teams colours
    // the list filter rejects 0xB7..0xBF; now 0xB7 only
    (0x0803_7424, 0x2808, 0x2800),
    // the map list's preview tests `id <= 0xB3`: a helper in dead code
    // (sub_0803CC3C, no callers) that answers as for an ordinary id for
    // 0xB8..0xBF. Entries per register the id is loaded from.
    (0x0803_CC3C, 0xB500, 0x7808), // entry_r1: ldrb r0,[r1]
    (0x0803_CC3E, 0x0400, 0xE004), //   b 0x0803CC4A
    (0x0803_CC40, 0x0C00, 0x7828), // entry_r5: ldrb r0,[r5]
    (0x0803_CC42, 0x1C01, 0xE002), //   b 0x0803CC4A
    (0x0803_CC44, 0x39B4, 0x7880), // entry_link: ldrb r0,[r0,#2]
    (0x0803_CC46, 0x0408, 0xE000), //   b 0x0803CC4A
    (0x0803_CC48, 0x0C00, 0x7820), // entry_r4: ldrb r0,[r4]
    (0x0803_CC4A, 0x280B, 0x28B7), // cmp r0,#0xb7
    (0x0803_CC4C, 0xD807, 0xD801), // bhi (a new id)
    (0x0803_CC4E, 0x1C08, 0x28B3), // cmp r0,#0xb3
    (0x0803_CC50, 0x2103, 0x4770), // bx lr
    (0x0803_CC52, 0xF04D, 0x4280), // new id: cmp r0,r0 (as for id <= 0xB3)
    (0x0803_CC54, 0xFF2B, 0x4770), // bx lr
    // callers: `ldrb r0,[rX]; cmp r0,#0xb3` -> `bl entry`
    (0x0808_6EBE, 0x7820, 0xF7B5),
    (0x0808_6EC0, 0x28B3, 0xFEC3),
    (0x0808_6EF8, 0x7820, 0xF7B5),
    (0x0808_6EFA, 0x28B3, 0xFEA6),
    (0x0808_6F4A, 0x7820, 0xF7B5),
    (0x0808_6F4C, 0x28B3, 0xFE7D),
    (0x0808_6FC0, 0x7820, 0xF7B5),
    (0x0808_6FC2, 0x28B3, 0xFE42),
    (0x0808_7110, 0x7808, 0xF7B5),
    (0x0808_7112, 0x28B3, 0xFD94),
];
/// Tab titles, a text id per tab.
const TAB_TITLES: u32 = 0x0849_9CE4;
/// The text table has no room to grow, but ids are 16 bits and the table is
/// read without a bound: id 0x3D72 + k reads its string pointer from
/// 0x08620000 + 4k, in the ROM image's free space. crate::roster has slots 32..56; ours start at 64: [`TAB_TEXT`] is the tab's
/// title, the next ids the maps' names; the strings are at [`STRINGS`].
const TEXT_TABLE: u32 = 0x0861_0A38;
const TAB_TEXT: u16 = 0x3D72 + 64;
const STRINGS: u32 = 0x0862_2000;
/// This module's text ids are [`TAB_TEXT`] + slot: their pointers (4 bytes a slot) start at 0x08620100, after the roster's (crate::roster, slots
/// 32..56 of the 0x3D72 range), and the strings (0x20 a slot from [`STRINGS`], where the first ten maps' data used to be) hold the tab title,
/// a name per map and two tab titles per player count.
const TEXT_SLOTS: usize = 1 + MAP_CAPACITY + 8;
pub const TAB_NAME_TEXT: &str = "5P Maps";

/// Whether a map of tangoAW2's needs the Dual Strike pack (its art, its units or its look): listed online only when
/// every peer has the pack ([`crate::ds_art::SHARED_ART`]), offline only with it.
pub fn needs_pack(map: &crate::five_map_data::Map) -> bool {
    map.ds || map.obelisk
}

/// A 5-army map's id.
pub fn is_five_map(id: u8) -> bool {
    map_of(id).is_some_and(|m| m.armies == 5)
}

/// tangoAW2's map with this id, if any.
pub fn map_of(id: u8) -> Option<&'static crate::five_map_data::Map> {
    MAPS.iter().zip(IDS.iter()).find(|(_, &i)| i == id).map(|(m, _)| m)
}

/// A map with Dual Strike content (listed only with the pack).
pub fn is_ds_map(id: u8) -> bool {
    id != 0 && map_of(id).is_some_and(|m| m.ds)
}

/// A map drawn in the Wasteland look ([`crate::wasteland`]).
pub fn is_wasteland_map(id: u8) -> bool {
    id != 0 && map_of(id).is_some_and(|m| m.wasteland)
}

/// A room's Versus tabs read "<n>P" and "<n>P - <pre>" (a room of n players: [`crate::online_maps`]): the titles of the
/// Classic tab (2) and the Pre-Deployed tab (4), each a text of its own (the ones after the maps' names, two for each
/// count), so no other tab changes. Idempotent.
pub fn name_room_tabs(core: &mut Core, players: usize, plain: &str, pre: &str) {
    for (k, (tab, text)) in [(2u32, plain), (4, pre)].into_iter().enumerate() {
        name_tab(core, tab, players, k, text);
    }
}

/// Tab `tab`'s title is the text for `players` players' plain (k 0) or Pre-Deployed (k 1) list. Idempotent.
pub fn name_tab(core: &mut Core, tab: u32, players: usize, k: usize, text: &str) {
    let slot_k = 1 + MAP_CAPACITY as u32 + 2 * (players as u32 - 2) + k as u32;
    let at = STRINGS + 0x20 * slot_k;
    let id = TAB_TEXT as u32 + slot_k;
    let slot = TEXT_TABLE + 4 * id;
    if core.raw_read_32(slot, -1) != at {
        let mut bytes = text
            .bytes()
            .map(|b| if b == b'\'' { b'~' } else { b })
            .collect::<Vec<u8>>();
        assert!(bytes.len() < 0x20);
        bytes.push(0);
        core.raw_write_range(at, -1, &bytes);
        core.raw_write_32(slot, -1, at);
    }
    if core.raw_read_16(TAB_TITLES + 2 * tab, -1) != id as u16 {
        core.raw_write_16(TAB_TITLES + 2 * tab, -1, id as u16);
    }
}

/// The game's own tab titles (a text id per tab 2..=8, [`TAB_TITLES`]); tab 9 is [`TAB_TEXT`].
pub fn native_tab_title(tab: u32) -> u16 {
    if tab == CATEGORY as u32 {
        TAB_TEXT
    } else {
        2603 + tab as u16
    }
}

pub fn set_tab_title(core: &mut Core, tab: u32, id: u16) {
    if core.raw_read_16(TAB_TITLES + 2 * tab, -1) != id {
        core.raw_write_16(TAB_TITLES + 2 * tab, -1, id);
    }
}

// --- The map list's buffer ---------------------------------------------------------------------------------
//
// The game's SELECT MAP list keeps its rows in a small struct in EWRAM (0x02027F74: four bytes, the ids of up to 50
// maps from +4, then the cursor at +0x36 and the last row at +0x37) and its builder stops at 50 maps. A Versus tab can
// hold more (60 maps for 2 players, 76 with the Dual Strike pack), so the struct moves to [`LIST`] with room for
// [`LIST_CAP`] ids, every literal that points to it (or to its ids) follows, the two fields move behind the ids and the
// builder's stop moves up. The other modes' builders (up to 107 rows, the ids are their own) fill it as before.

/// The list's struct: four bytes, [`LIST_CAP`] ids, the cursor row, the last row.
pub const LIST: u32 = 0x0203_DC20;
pub const LIST_IDS: u32 = LIST + 4;
pub const LIST_CAP: u32 = 0x6E;
pub const LIST_CURSOR: u32 = LIST + 4 + LIST_CAP;
pub const LIST_LAST: u32 = LIST_CURSOR + 1;
pub const LIST_BYTES: u32 = 8 + LIST_CAP;
const OLD_LIST: u32 = 0x0202_7F74;
/// Literal words that hold the struct's address (and its ids', +4).
const LIST_LITERALS: [u32; 33] = [
    0x0803_74DC,
    0x0803_7504,
    0x0803_7538,
    0x0803_756C,
    0x0803_75A0,
    0x0803_7938,
    0x0803_7C94,
    0x0808_615C,
    0x0808_6250,
    0x0808_63C4,
    0x0808_6544,
    0x0808_6648,
    0x0808_6ACC,
    0x0808_6BA4,
    0x0808_6C9C,
    0x0808_6D50,
    0x0808_6DB0,
    0x0808_6EEC,
    0x0808_6FA4,
    0x0808_7140,
    0x0808_71B0,
    0x0808_7218,
    0x0808_73AC,
    0x0808_74C0,
    0x0808_75A0,
    0x0808_7668,
    0x0808_7934,
    0x0808_7B1C,
    0x0808_7BFC,
    0x081D_9414,
    0x081D_9448,
    0x0861_7A64,
    0x0861_7CE8,
];
const LIST_IDS_LITERALS: [u32; 5] = [0x0803_74D8, 0x0803_7534, 0x0803_7568, 0x0803_759C, 0x0808_7C70];
/// `adds rN, #0x36` (the cursor row) and `adds rN, #0x37` (the last row) on the struct's pointer.
const LIST_CURSOR_SITES: [u32; 6] = [
    0x0803_74C0,
    0x0803_74F4,
    0x0803_7526,
    0x0803_755A,
    0x0803_758E,
    0x0808_6126,
];
const LIST_LAST_SITES: [u32; 17] = [
    0x0803_74C8,
    0x0803_74FA,
    0x0803_752C,
    0x0803_7560,
    0x0803_7594,
    0x0808_6212,
    0x0808_64FC,
    0x0808_6600,
    0x0808_6B3E,
    0x0808_6C32,
    0x0808_6CF2,
    0x0808_718A,
    0x0808_71CE,
    0x0808_72F8,
    0x0808_7362,
    0x0808_7404,
    0x0808_7476,
];
/// The Versus builder's `cmp r5, #0x31` (it stops when 50 maps are in).
const LIST_BUILDER_STOP: u32 = 0x0803_74AA;

fn patch_list(core: &mut Core) {
    for at in LIST_LITERALS {
        if core.raw_read_32(at, -1) == OLD_LIST {
            core.raw_write_32(at, -1, LIST);
        }
    }
    for at in LIST_IDS_LITERALS {
        if core.raw_read_32(at, -1) == OLD_LIST + 4 {
            core.raw_write_32(at, -1, LIST_IDS);
        }
    }
    for (sites, old, new) in [
        (&LIST_CURSOR_SITES[..], 0x36u16, (LIST_CAP + 4) as u16),
        (&LIST_LAST_SITES[..], 0x37, (LIST_CAP + 5) as u16),
    ] {
        for &at in sites {
            let h = core.raw_read_16(at, -1);
            if h & 0xFF == old {
                core.raw_write_16(at, -1, (h & 0xFF00) | new);
            }
        }
    }
    if core.raw_read_16(LIST_BUILDER_STOP, -1) == 0x2D31 {
        core.raw_write_16(LIST_BUILDER_STOP, -1, 0x2D00 | (LIST_CAP as u16 - 1));
    }
}

pub fn install(core: &mut Core) {
    patch_list(core);
    let mut names = vec![TAB_NAME_TEXT];
    names.extend(MAPS.iter().map(|m| m.name));
    for (k, text) in names.iter().enumerate() {
        let at = STRINGS + 0x20 * k as u32;
        // (AW2's font draws its apostrophe at `~`, as the staff roll's names do)
        let mut bytes: Vec<u8> = text.bytes().map(|b| if b == b'\'' { b'~' } else { b }).collect();
        bytes.push(0);
        assert!(bytes.len() <= 0x20);
        core.raw_write_range(at, -1, &bytes);
        core.raw_write_32(TEXT_TABLE + 4 * (TAB_TEXT as u32 + k as u32), -1, at);
    }
    core.raw_write_16(TAB_TITLES + 2 * CATEGORY as u32, -1, TAB_TEXT);
    for &(addr, old, new) in TAB_BOUNDS.iter().chain(ORDINARY_IDS) {
        if core.raw_read_16(addr, -1) == old {
            core.raw_write_16(addr, -1, new);
        }
    }
    // The map table, moved (see MAP_TABLE).
    let mut table = vec![0u8; (GAME_MAP_IDS * ENTRY) as usize];
    core.raw_read_range(GAME_MAP_TABLE, -1, &mut table);
    core.raw_write_range(MAP_TABLE, -1, &table);
    for (at, field) in TABLE_POINTERS {
        if core.raw_read_32(at, -1) == GAME_MAP_TABLE + field {
            core.raw_write_32(at, -1, MAP_TABLE + field);
        }
    }
    for (at, old, new, _) in TABLE_LOOPS {
        if core.raw_read_16(at, -1) == old {
            core.raw_write_16(at, -1, new);
        }
    }
    assert_eq!(MAPS.len(), IDS.len());
    assert!(IDS.iter().all(|&id| (id as u32) < MAP_IDS));
    assert!(MAPS.len() <= MAP_CAPACITY, "more maps than five_map::MAP_CAPACITY");
    assert!(MAP_TABLE + ENTRY * MAP_IDS <= MAP_TABLE_LIMIT);
    for (k, (map, &id)) in MAPS.iter().zip(IDS.iter()).enumerate() {
        let tiles = map_data(k);
        let units = tiles + map.tiles.len() as u32;
        assert!(map.tiles.len() + map.units.len() <= MAP_DATA_SIZE as usize);
        core.raw_write_range(tiles, -1, map.tiles);
        core.raw_write_range(units, -1, map.units);

        let mut h = [0u8; 0x5C];
        let w32 = |h: &mut [u8], at: usize, v: u32| h[at..at + 4].copy_from_slice(&v.to_le_bytes());
        let w16 = |h: &mut [u8], at: usize, v: u16| h[at..at + 2].copy_from_slice(&v.to_le_bytes());
        w32(&mut h, 0x00, tiles);
        w16(&mut h, 0x14, TAB_TEXT + 1 + k as u16);
        h[0x16] = 2; // pre-deployed art
                     // armies in the header (a 5-army map says 4: army 5 is tangoAW2's)
        h[0x18] = map.armies.min(4);
        w16(&mut h, 0x1A, map.tab);
        w16(&mut h, 0x1C, 1);
        w16(&mut h, 0x1E, 1);
        w16(&mut h, 0x20, 0x16);
        h[0x26] = 0xFF;
        w32(&mut h, 0x2C, tiles);
        w32(&mut h, 0x34, units);
        for (i, &c) in map.colours.iter().take(4).enumerate() {
            h[0x40 + i] = c;
        }
        h[0x44..0x48].copy_from_slice(&[1, 2, 3, 4]);
        for i in 0..4 {
            h[0x48 + 4 * i..0x4C + 4 * i].copy_from_slice(&[0xFF, 0xFF, 0, 0]);
        }
        core.raw_write_range(MAP_TABLE + 0x5C * id as u32, -1, &h);
    }

    let mut quad = [0u8; 8];
    core.raw_read_range(METATILES + NEUTRAL_HQ_TILE * 8, -1, &mut quad);
    for (tile, terrain) in ARMY5_TILES {
        core.raw_write_8(TERRAIN_TABLE + tile, -1, terrain);
        core.raw_write_range(METATILES + tile * 8, -1, &quad);
    }
}

/// The list's "may this map be shown" test (a bit of the unlock block,
/// `0x02028042 + id / 8`: 26 bytes for the Battle Maps, then the COs' bits,
/// which pvp.rs sets): the ids from 0xF0 up have no bit there (the byte past
/// it is something else), so with a larger map table in use (Survival's,
/// or Dual Strike's Versus maps', crate::ds_versus) they are all shown. The map list then lists and previews the Colonel's Vault (0xF1).
const MAP_SHOWN: u32 = 0x0803_CA54;

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut v: Vec<(u32, Box<dyn Fn(&mut Core)>)> = Vec::new();
    v.push((
        MAP_SHOWN,
        Box::new(|core: &mut Core| {
            let id = core.gba().cpu().gpr(0) as u32;
            let t = table(core);
            if id >= 0xF0 && (t == crate::survival::TABLE || t == crate::ds_versus::TABLE) {
                let cpu = core.gba_mut().cpu_mut();
                cpu.set_gpr(0, 1);
                let lr = cpu.gpr(14) as u32;
                cpu.set_thumb_pc(lr & !1);
            }
        }),
    ));
    v
}

/// A Versus tab no map list shows: where a map goes to be hidden.
pub(crate) const HIDDEN_TAB: u16 = 0x7F;

/// The map table the game reads now: [`MAP_TABLE`], or (with the Dual
/// Strike pack) [`crate::survival`]'s larger copy.
pub(crate) fn table(core: &Core) -> u32 {
    let (at, field) = TABLE_POINTERS[0];
    core.raw_read_32(at, -1).wrapping_sub(field)
}

/// Point the game at the map table at `base` (a copy of [`MAP_TABLE`]).
pub(crate) fn use_table(core: &mut Core, base: u32) {
    for (at, field) in TABLE_POINTERS {
        let now = core.raw_read_32(at, -1);
        if now != base + field {
            core.raw_write_32(at, -1, base + field);
        }
    }
}

/// Every frame: list the maps with a Black Crystal or Black Obelisk on
/// their tabs only when `art` ([`crate::ds_art::features`]), and the maps
/// with Dual Strike content only when `pack` is on too
/// ([`crate::ds_pack::features`]); otherwise they sit on a tab no list
/// shows.
pub fn show_maps(core: &mut Core, art: bool, pack: bool, last_id: Option<u8>) {
    for (at, _, without, with) in TABLE_LOOPS {
        let now = core.raw_read_16(at, -1);
        let want = match last_id {
            // Dual Strike's Survival maps (crate::survival), past 0xC8.
            Some(id) if art && pack => (with & 0xFF00) | (id as u16).max(with & 0xFF),
            _ if art && pack => with,
            _ => without,
        };
        let ours = now == without || now == with || (now & 0xFF00 == with & 0xFF00 && now & 0xFF > with & 0xFF);
        if ours && now != want {
            core.raw_write_16(at, -1, want);
        }
    }
    let table = table(core);
    for (map, &id) in MAPS.iter().zip(IDS.iter()) {
        // (Dual Strike's Versus maps' table has its own maps at some of these ids, crate::ds_versus)
        if (!map.obelisk && !map.ds) || (table == crate::ds_versus::TABLE && crate::ds_versus::replaced(id)) {
            continue;
        }
        let on = !needs_pack(map) || (art && pack);
        let at = table + 0x5C * id as u32 + 0x1A;
        let tab = if on { map.tab } else { HIDDEN_TAB };
        if core.raw_read_16(at, -1) != tab {
            core.raw_write_16(at, -1, tab);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_fit_their_slots() {
        assert_eq!(MAPS.len(), IDS.len());
        let mut ids = IDS.to_vec();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), IDS.len(), "every map has its own id");
        assert!(IDS.iter().all(|&id| (id as u32) < MAP_IDS));
        assert!(MAPS.len() <= MAP_CAPACITY);
        assert!(MAP_TABLE + ENTRY * MAP_IDS <= MAP_TABLE_LIMIT);
        // the data run stays clear of the Dual Strike Versus maps below it and the Normal look above
        assert!(MAP_DATA >= crate::ds_versus::ROM_END_FOR_MAPS && map_data(MAP_CAPACITY) <= 0x09E0_0000);
        // the text slots: pointers after the roster's (slots 32..56) and before its strings (0x08620500), strings in the old first map-data run
        let ptr0 = TEXT_TABLE + 4 * TAB_TEXT as u32;
        assert!(ptr0 >= 0x0862_0000 + 4 * 56 && ptr0 + 4 * TEXT_SLOTS as u32 <= 0x0862_0500);
        assert!(STRINGS >= 0x0862_2000 && STRINGS + 0x20 * TEXT_SLOTS as u32 <= 0x0862_C000);
        // the new-map pool is inside the table and past every id something else uses
        assert!(
            *NEW_ID_POOL.end() < crate::ds_versus::BATTLE_ID
                && *NEW_ID_POOL.end() as u32 + 1 < MAP_IDS
                && *NEW_ID_POOL.start() > crate::five_map::VAULT_ID
        );
        for (k, &id) in IDS.iter().enumerate() {
            assert!(
                !NEW_ID_POOL.contains(&id) || MAPS[k].ds,
                "{} is in the new-map pool, so it is pack content",
                MAPS[k].name
            );
        }
        // The list loops' bound with the pack: a byte counter never passes 0xFF, so a bound of 0xFF never ends the walk (the list then fills with
        // the table over and over, 110 rows, and the tabs cannot be switched: the 5P room lost its "5P Predeploy" tab). It must also stay below
        // ds_versus::BATTLE_ID (0xFE), and reach every id of the pool.
        for (_, _, _, with) in TABLE_LOOPS {
            assert!(
                (with & 0xFF) < 0xFE && (with & 0xFF) as u8 >= *NEW_ID_POOL.end(),
                "loop bound {:#x}",
                with & 0xFF
            );
        }
        assert_eq!(map_of(BIG_FIVE_ID).map(|m| m.name), Some("Pentagon Atoll"));
        assert_eq!(map_of(VAULT_ID).map(|m| m.name), Some("The Colonel's Vault"));
        for m in MAPS {
            assert!(m.name.len() < 0x20, "{}", m.name);
            assert!(m.tiles.len() + m.units.len() <= MAP_DATA_SIZE as usize, "{}", m.name);
            // the Wasteland look is the pack's
            assert!(!m.wasteland || m.ds, "{}", m.name);
        }
    }

    #[test]
    fn dual_strike_maps_are_the_new_ids() {
        // The loops walk past 0xC0 only while the Dual Strike maps can be
        // listed, so every map up to 0xC0 must not need the pack.
        for (m, &id) in MAPS.iter().zip(IDS.iter()) {
            assert_eq!(m.ds, id > 0xC0, "{}", m.name);
            assert!(id <= VAULT_ID);
        }
        assert_eq!(MAPS.iter().filter(|m| m.wasteland).count(), 4);
        for armies in 2..=5 {
            assert_eq!(
                MAPS.iter().filter(|m| m.ds && m.armies == armies).count(),
                match armies {
                    2 => 3,
                    5 => 3,
                    _ => 2,
                }
            );
        }
        assert!(is_wasteland_map(0xC1) && !is_wasteland_map(0xC5) && !is_wasteland_map(0));
        assert!(is_five_map(0xC4) && is_five_map(0xC8) && !is_five_map(0xC3));
        // the Colonel's Vault: a 2-army map with the pack's tab, the last id
        assert!(!is_five_map(VAULT_ID) && is_ds_map(VAULT_ID) && !is_wasteland_map(VAULT_ID));
        assert_eq!(map_of(VAULT_ID).unwrap().name, "The Colonel's Vault");
    }

    /// The armies of a map counted from its data, not its label: the owners of its property tiles and of the
    /// units placed on it (both by army slot; the colours are the header's). Returns (armies, armies with an HQ, units placed, production properties: bases, airports, ports, owned or neutral).
    fn counted(m: &crate::five_map_data::Map) -> (u32, u32, u32, u32) {
        // (BIOS LZ77: literal blocks, or matches back)
        let size = u32::from_le_bytes([m.tiles[0], m.tiles[1], m.tiles[2], m.tiles[3]]) as usize >> 8;
        let mut bytes: Vec<u8> = Vec::new();
        let mut p = 4;
        while bytes.len() < size {
            let flags = m.tiles[p];
            p += 1;
            for bit in 0..8 {
                if bytes.len() >= size {
                    break;
                }
                if flags & (0x80 >> bit) != 0 {
                    let (b1, b2) = (m.tiles[p] as usize, m.tiles[p + 1] as usize);
                    p += 2;
                    let disp = ((b1 & 15) << 8 | b2) + 1;
                    for _ in 0..(b1 >> 4) + 3 {
                        bytes.push(bytes[bytes.len() - disp]);
                    }
                } else {
                    bytes.push(m.tiles[p]);
                    p += 1;
                }
            }
        }
        let (w, h) = (bytes[0] as usize, bytes[1] as usize);
        let (mut owners, mut hqs, mut prod) = (0u32, 0u32, 0u32);
        for t in 0..w * h {
            let id = u16::from_le_bytes([bytes[2 + 2 * t], bytes[3 + 2 * t]]) as u32;
            // (production: base +1, airport +3, port +4 in each owner's five tiles, neutral's included)
            if matches!(id, 0x1C0..=0x1D8 if matches!((id - 0x1C0) % 5, 1 | 3 | 4))
                || matches!(id, 0x1B5 | 0x1B7 | 0x1B8)
            {
                prod += 1;
            }
            let (army, hq) = match id {
                // (neutral 0x1C0.. is owner 0; armies 1..4 follow, then the fifth's 0x1B4..)
                0x1C5..=0x1D8 => ((id - 0x1C0) / 5, (id - 0x1C0) % 5 == 0),
                0x1B4..=0x1B8 => (5, id == 0x1B4),
                _ => continue,
            };
            owners |= 1 << army;
            hqs |= (hq as u32) << army;
        }
        let (mut placed, mut army) = (0, 0);
        for rec in m.units.chunks(12) {
            match rec[0] {
                0xFF => break,
                0xFE => army = rec[1] as u32,
                _ => {
                    placed += 1;
                    owners |= 1 << army;
                }
            }
        }
        (owners.count_ones(), hqs.count_ones(), placed, prod)
    }

    #[test]
    fn every_map_has_the_armies_it_is_listed_for() {
        for m in MAPS {
            let (armies, hqs, _, _) = counted(m);
            assert_eq!(armies, m.armies as u32, "{}: armies counted from its data", m.name);
            assert!(hqs <= armies && hqs >= 1, "{}", m.name);
            assert_eq!(m.colours.len(), m.armies as usize, "{}", m.name);
        }
        // the groups the online tabs use (armies, pre-deployed): none empty is asserted by the audit example
        for m in MAPS {
            let (_, _, placed, prod) = counted(m);
            let group = (m.armies, placed > 0 && prod == 0);
            assert!((2..=5).contains(&group.0), "{}", m.name);
        }
    }
}
