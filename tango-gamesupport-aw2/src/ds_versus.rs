//! Dual Strike's Versus and War Room maps, with the Dual Strike pack: docs/AW2.md "Dual Strike's Versus and War
//! Room maps".
//!
//! With the pack, Versus lists Dual Strike's 138 Versus maps on AW2's own tabs (Classic, Vs. Maps, Pre-Deployed,
//! 3P Maps, 4P Maps: Dual Strike's cases 2..6 are the same lists) and the War Room Dual Strike's 44 maps, in place of
//! AW2's (AW2's 107 Versus maps and 30 War Room maps are among them, in Dual Strike's padded versions). Without the
//! pack nothing changes.
//!
//! - **A map table of its own** ([`TABLE`], 0x100 ids): a copy of [`crate::five_map`]'s (the Design Room's ids,
//!   tangoAW2's own maps, the Colonel's Vault) with Dual Strike's maps over AW2's ids. Dual Strike's ids are kept:
//!   0x01..0x8A Versus, 0x8B..0xB3 the War Room; the War Room's last three (0xB4..0xB6, two-front battles) are
//!   0xC1..0xC3, the ids of three of tangoAW2's eight Dual Strike-style maps, which give way to Dual Strike's real
//!   ones (their other three ids are hidden; the two 5-army maps, Black Wastes 0xC4 and Coral Crown 0xC8, stay for
//!   5-army Versus). The second maps of the War Room's five two-front battles have headers beside the table
//!   ([`SECOND_HEADERS`]), no id. Built once from the pack, in id order (the same bytes on every console with the
//!   pack), and written into the ROM image's free space once.
//! - **When.** The game reads this table in Versus and the War Room (the title menu's mode, `0x030033FC`, 2..5)
//!   while the pack's features are on (in a match: both players have the pack) and Survival is not open: each
//!   frame the 37 words that point at the map table are set from RAM ([`tick_tables`]), so rollback (which restores
//!   RAM, not ROM) keeps it. A game saved halfway records which table it was saved on (the suspend tail,
//!   [`crate::suspend`]); a game saved on AW2's table (before this, or without the pack) continues on it
//!   ([`TABLE_FLAG`], until the next map list is built).
//! - **Per map** (at its start): the look (Snow, Desert, Wasteland as Dual Strike draws them,
//!   [`crate::wasteland::set_ds_look`]), the weather (Dark City's snow, Clover Pond's sandstorm: fixed, over the
//!   Rules' choice, as Dual Strike's `SetupMapRules` sets it), fog.
//! - **The War Room**: enemy COs, colours and teams from Dual Strike's header, par days as the speed score's days,
//!   Com Towers as in Versus ([`crate::com_tower`]). Records: AW2 keeps a War Room record row (0x14 bytes, five
//!   places) per map by `id - 0x6C` in its profile (`0x0200C078`, 30 maps); Dual Strike's maps take rows of their
//!   own ([`ROWS`]) that the War Room's record code reads and writes while this table is in use (its five literal-pool words, [`crate::survival`]'s, and the
//!   insert's own, `0x0808E55C`), kept in Flash at the end of the DS Campaign's slot 15 and written right after
//!   the profile, as the COs' skill data is (crate::co_skills::profile_written). Dual Strike keeps four sets of
//!   records ("strips": tag or not, partner boost or not); this is strip 0, no tag.
//! - **Two fronts** ([`crate::two_front`], offline): Dual Strike's rule, any two 2P maps. On Versus' map list
//!   SELECT marks a 2P map as the second front (its name shows "2:" and is drawn again at once; SELECT again
//!   takes the mark back), and the 2P map picked then is the main front; the Teams screen's partner (crate::tag_ui)
//!   leads each army's second front (none: its CO), every army plays its own turns on both fronts (Dual Strike's
//!   Versus), the main front sends units to the second, Save is off. The War Room's five two-front maps are its
//!   fixed pairs: the CO screen asks for the second front's CO too, the computer directs the player's second front
//!   (Dual Strike's records strips 0 and 1) and the enemy's second front has its back CO. Either battle is played
//!   on map id [`BATTLE_ID`], whose entry is the live front's header, set from RAM ([`FRONTS`]) every frame.
//! - **The map list**: Dual Strike's longer tabs (up to 44 maps) outgrow the list's text tile cache; it starts
//!   over at every redraw ([`LIST_DRAWN`]).
//! - **Map ids AW2 treats as special**: AW2's campaign tables by `id - 0x8A` (the factory schedule a computer Black
//!   Hole reads, crate::factory, which gives these maps the design maps' rule; scripted CO power quotes, off here).

use std::sync::OnceLock;

use mgba::core::Core;

use crate::ds_maps::{self, Map, CASE_VERSUS_FIRST, CASE_WAR_ROOM, CASE_WAR_ROOM_SECOND};

// --- Where things are ------------------------------------------------------------------

/// The map table (0x100 ids of 0x5C bytes), the War Room's second maps' headers, a sentinel, the names, the
/// maps (tiles then units, [`MAP_DATA_SIZE`] each) in the ROM image's free space (past the DS Campaign's story
/// songs and power themes from 0x09000000, which end below crate::ds_music::STORY_END = TABLE; before the Dual Strike
/// graphics from 0x09E00000).
pub const TABLE: u32 = 0x09C0_0000;
const ENTRY: u32 = 0x5C;
pub const SECOND_HEADERS: u32 = 0x09C0_6000;
const SENTINEL: u32 = 0x09C0_7FFC;
const MAGIC: u32 = 0x3150_4D44; // "DMP1"
const STRINGS: u32 = 0x09C0_8000;
const STRING_SIZE: u32 = 0x20;
const MAP_DATA: u32 = 0x09C1_0000;
const MAP_DATA_SIZE: u32 = 0x1000;
const ROM_END: u32 = 0x09D0_0000;
/// (crate::five_map's map data starts where this area ends)
pub(crate) const ROM_END_FOR_MAPS: u32 = ROM_END;

/// Text ids from 0x7200 read their pointer from 0x0862D238 (free ROM; see crate::five_map for why that works).
const TEXT_TABLE: u32 = crate::campaign_model::TEXT_TABLE;
const FONT_WIDTHS: u32 = 0x084C_36E4;
pub const TEXT_BASE: u16 = 0x7200;
const TEXT_IDS: u16 = 0x100;

/// Dual Strike's War Room ids past AW2's design ids (0xB4..0xB7 are the Design Room's to AW2's code), and theirs
/// here: three of tangoAW2's Dual Strike-style maps' ids ([`crate::five_map::IDS`]).
const MOVED: [(u16, u8); 3] = [(0xB4, 0xC1), (0xB5, 0xC2), (0xB6, 0xC3)];
/// tangoAW2's Dual Strike-style maps hidden while this table is in use (the other three ids are [`MOVED`]'s; the
/// 5-army Black Wastes and Coral Crown stay).
const HIDDEN: [u8; 3] = [0xC5, 0xC6, 0xC7];
/// The map id a two-front battle is played on (its entry: the live front's header).
pub const BATTLE_ID: u8 = 0xFE;
/// The last Versus id and the War Room's first.
const LAST_VERSUS: u16 = 0x8A;
pub const FIRST_WAR_ROOM: u16 = 0x8B;
/// The War Room's 44 maps.
pub const WAR_ROOM_MAPS: usize = 44;

// --- RAM -----------------------------------------------------------------------------

/// This module's state (crate::ram_map): 0x0203C900..
pub const STATE: u32 = 0x0203_C900;
pub const STATE_LEN: u32 = 0x20;
/// The table a game continued from a save was saved on: 0 as usual, [`FORCED_AW2`] AW2's (until the next map
/// list is built).
pub const TABLE_FLAG: u32 = STATE;
const FORCED_AW2: u8 = 1;
/// The War Room's records in RAM: bit 0 loaded from Flash into [`ROWS`], bit 1 a record not yet saved.
const ROWS_STATE: u32 = STATE + 1;
const LOADED: u8 = 1;
const DIRTY: u8 = 2;
/// Two-front Versus may be set up (1: offline; crate::two_front runs offline only).
const TWO_ALLOWED: u32 = STATE + 2;
/// The 2P map marked on Versus' list as the second front (its id; 0 none).
const MARK: u32 = STATE + 3;
/// The two-front battle set up: 0 none, [`FRONTS_VERSUS`], [`FRONTS_WAR_ROOM`]; its main map's id and its second
/// map (Versus: the map's id; the War Room: its pair's index).
pub const FRONTS: u32 = STATE + 4;
const FRONTS_VERSUS: u8 = 1;
const FRONTS_WAR_ROOM: u8 = 2;
const MAIN_ID: u32 = STATE + 5;
const SECOND_ID: u32 = STATE + 6;
/// The list is to be drawn again (1), with the arguments `DrawMapList` last had (first, count, top).
const REDRAW: u32 = STATE + 7;
const LIST_ARGS: u32 = STATE + 8;

/// The War Room's record rows for Dual Strike's ids (0x8B..0xC3: AW2's `id - 0x6C` rows, 0x14 bytes each),
/// while the War Room's screens show. Time-shared (crate::ram_map): loaded from Flash on the War Room's screens,
/// given up during a two-front battle and outside the War Room.
pub const ROWS: u32 = 0x0203_E500;
const ROW: u32 = 0x14;
pub const ROWS_LEN: u32 = ROW * (0xC4 - FIRST_WAR_ROOM as u32);

/// The War Room's record table and the six literal-pool words its code reads it through (the readers' and the
/// writer's: crate::survival's five; the insert's search and store read the table's address from the word at
/// `0x0808E55C`, which [`INSERT_POOL`] is).
pub const RECORDS: u32 = 0x0200_C078;
pub const INSERT_POOL: u32 = 0x0808_E55C;

// --- The game ----------------------------------------------------------------------------

/// The title menu's mode: Versus' Continue 2 and New 3, the War Room's Continue 4 and New 5.
const TITLE_MODE: u32 = 0x0300_33FC;
const VERSUS: [u8; 2] = [2, 3];
const WAR_ROOM: [u8; 2] = [4, 5];
const PLAY_ST: u32 = 0x0300_3FC0;
const MAP_ID: u32 = PLAY_ST + 0x02;
const FOG: u32 = PLAY_ST + 0x0D;
const WEATHER: u32 = PLAY_ST + 0x2C;
const WEATHER_MODE: u32 = PLAY_ST + 0x2D;
const NEXT_WEATHER: u32 = PLAY_ST + 0x2E;
const DEFAULT_WEATHER: u32 = PLAY_ST + 0x2F;

// --- The table -----------------------------------------------------------------------------

/// What the game's code needs of a map here at run time.
#[derive(Clone, Debug)]
pub struct Entry {
    pub id: u8,
    pub ds_id: u16,
    pub name: String,
    pub armies: u8,
    pub look: u8,
    pub weather: u8,
    pub fog: bool,
    pub case: u16,
    /// The War Room's two-front battles: the second map (its Dual Strike id and header address).
    pub second: Option<(u16, u32)>,
    /// The CPU armies' (front, back) COs (armies 1..4; tangoAW2 ids).
    pub cos: [(Option<u8>, Option<u8>); 4],
}

pub struct Built {
    writes: Vec<(u32, Vec<u8>)>,
    /// The 2P Versus maps' names: (id, the word that points at its name, the name's string, its marked
    /// string, [`MARK`]).
    names: Vec<(u8, u32, u32, u32, String)>,
    pub entries: Vec<Entry>,
    /// The second maps (two-front battles): Dual Strike id, look, weather.
    pub seconds: Vec<Entry>,
}

static BUILT: OnceLock<Option<Built>> = OnceLock::new();

/// The table built from the pack (None without it).
pub fn built() -> Option<&'static Built> {
    BUILT.get_or_init(build).as_ref()
}

/// tangoAW2's id for a Dual Strike id (None: a second map or not in the table).
pub fn id_of(ds_id: u16) -> Option<u8> {
    if let Some(&(_, id)) = MOVED.iter().find(|m| m.0 == ds_id) {
        return Some(id);
    }
    (1..=0xB3).contains(&ds_id).then_some(ds_id as u8)
}

/// A map's header in AW2's form.
fn header(map: &Map, tiles: u32, units: u32, text: u16, tab: u16) -> [u8; 0x5C] {
    let mut h = [0u8; 0x5C];
    let w32 = |h: &mut [u8], at: usize, v: u32| h[at..at + 4].copy_from_slice(&v.to_le_bytes());
    let w16 = |h: &mut [u8], at: usize, v: u16| h[at..at + 2].copy_from_slice(&v.to_le_bytes());
    w32(&mut h, 0x00, tiles);
    w32(&mut h, 0x10, map.structure.map_or(0, |s| s.aw2_picture()));
    w16(&mut h, 0x14, text);
    // (AW2's Pre-Deployed maps have 2 here, the others 1)
    h[0x16] = if map.case == 4 { 2 } else { 1 };
    h[0x17] = map.fog as u8;
    h[0x18] = map.armies;
    w16(&mut h, 0x1A, tab);
    w16(&mut h, 0x1C, 1);
    w16(&mut h, 0x1E, 1);
    // The speed score's days: Dual Strike's par.
    w16(&mut h, 0x20, map.par.0.max(1));
    h[0x26] = 0xFF;
    w32(&mut h, 0x2C, tiles);
    w32(&mut h, 0x34, units);
    if map.case == CASE_WAR_ROOM || map.case == CASE_WAR_ROOM_SECOND {
        // The player picks army 1's CO (0xFF), the computer's are the map's.
        h[0x3C] = 0xFF;
        for k in 1..4 {
            if (k as u8) < map.armies {
                h[0x3C + k] = map.cos[k].0.unwrap_or(1);
            }
        }
    }
    h[0x40..0x44].copy_from_slice(&map.colours);
    h[0x44..0x48].copy_from_slice(&map.teams);
    for i in 0..4 {
        h[0x48 + 4 * i..0x4C + 4 * i].copy_from_slice(&[0xFF, 0xFF, 0, 0]);
    }
    h
}

fn entry(id: u8, map: &Map) -> Entry {
    Entry {
        id,
        ds_id: map.ds_id,
        name: map.name.clone(),
        armies: map.armies,
        look: map.look,
        weather: map.weather,
        fog: map.fog,
        case: map.case,
        second: None,
        cos: map.cos,
    }
}

fn build() -> Option<Built> {
    let pack = crate::ds_pack::pack()?;
    let r = ds_maps::Reader::new(pack);
    let mut writes = Vec::new();
    let mut names = Vec::new();
    let mut entries = Vec::new();
    let mut seconds = Vec::new();
    let mut slot = 0u32;
    let mut text = 0u16;
    // A map's name, tiles and units: (tiles, units, text id).
    let mut put = |writes: &mut Vec<(u32, Vec<u8>)>, map: &Map| -> (u32, u32, u16) {
        let (lz, units) = ds_maps::blobs(map);
        let at = MAP_DATA + MAP_DATA_SIZE * slot;
        assert!(lz.len() + units.len() <= MAP_DATA_SIZE as usize, "{}", map.name);
        assert!(at + MAP_DATA_SIZE <= ROM_END && text < TEXT_IDS);
        let units_at = at + lz.len() as u32;
        let t = TEXT_BASE + text;
        let s = STRINGS + STRING_SIZE * text as u32;
        // (the map list's font has the apostrophe)
        let mut name = map.name.as_bytes().to_vec();
        name.truncate(STRING_SIZE as usize - 1);
        name.push(0);
        writes.push((s, name));
        writes.push((TEXT_TABLE + 4 * t as u32, s.to_le_bytes().to_vec()));
        writes.push((at, lz));
        writes.push((units_at, units));
        slot += 1;
        text += 1;
        (at, units_at, t)
    };
    for ds_id in 1..=0xB6u16 {
        let map = r.map(ds_id)?;
        let id = id_of(ds_id)?;
        let tab = map.case;
        if !(CASE_VERSUS_FIRST..=CASE_WAR_ROOM).contains(&tab) || (ds_id <= LAST_VERSUS) == (tab == CASE_WAR_ROOM) {
            return None;
        }
        let (at, units_at, t) = put(&mut writes, &map);
        writes.push((TABLE + ENTRY * id as u32, header(&map, at, units_at, t, tab).to_vec()));
        if map.armies == 2 && ds_id <= LAST_VERSUS {
            let k = (t - TEXT_BASE) as u32;
            let marked = STRINGS + STRING_SIZE * (TEXT_IDS as u32 + names.len() as u32);
            names.push((id, TEXT_TABLE + 4 * t as u32, STRINGS + STRING_SIZE * k, marked, map.name.clone()));
        }
        let mut e = entry(id, &map);
        if let Some(second) = map.second {
            let s = r.map(second)?;
            let (sat, sunits, st) = put(&mut writes, &s);
            let hat = SECOND_HEADERS + ENTRY * seconds.len() as u32;
            writes.push((hat, header(&s, sat, sunits, st, crate::five_map::HIDDEN_TAB).to_vec()));
            e.second = Some((second, hat));
            seconds.push(entry(0, &s));
        }
        entries.push(e);
    }
    Some(Built { writes, names, entries, seconds })
}

fn installed(core: &Core) -> bool {
    core.raw_read_32(SENTINEL, -1) == MAGIC
}

fn install(core: &mut Core) -> bool {
    let Some(b) = built() else { return false };
    if !installed(core) {
        // crate::five_map's table (the Design Room's ids, tangoAW2's maps), with room for 0x100 ids.
        let mut table = vec![0u8; (crate::five_map::ENTRY * crate::five_map::MAP_IDS) as usize];
        core.raw_read_range(crate::five_map::MAP_TABLE, -1, &mut table);
        table.resize((ENTRY * 0x100) as usize, 0);
        core.raw_write_range(TABLE, -1, &table);
        for &id in &HIDDEN {
            core.raw_write_16(TABLE + ENTRY * id as u32 + 0x1A, -1, crate::five_map::HIDDEN_TAB);
        }
        for (at, bytes) in &b.writes {
            core.raw_write_range(*at, -1, bytes);
        }
        // The names marked as the second front: "2:" and the name, cut to the longest name's width in the list's
        // font (its widths, `0x084C36E4`).
        let width = |core: &Core, s: &str| s.bytes().map(|c| core.raw_read_8(FONT_WIDTHS + c as u32, -1) as u32).sum::<u32>();
        let room = b.names.iter().map(|n| width(core, &n.4)).max().unwrap_or(0);
        for (_, _, _, marked, name) in &b.names {
            let mut m = format!("2:{name}");
            while width(core, &m) > room {
                m.pop();
            }
            let mut bytes = m.into_bytes();
            bytes.truncate(STRING_SIZE as usize - 1);
            bytes.push(0);
            core.raw_write_range(*marked, -1, &bytes);
        }
        core.raw_write_32(SENTINEL, -1, MAGIC);
    }
    true
}

/// Whether the game reads this table now.
pub fn in_use(core: &Core) -> bool {
    crate::five_map::table(core) == TABLE
}

/// The map with id `id` while this table is in use.
pub fn map_of(core: &Core, id: u8) -> Option<&'static Entry> {
    if !in_use(core) {
        return None;
    }
    built()?.entries.iter().find(|e| e.id == id)
}

/// An id whose map in [`crate::five_map`]'s table is not this table's (crate::five_map keeps its tabs in
/// whichever table is in use).
pub fn replaced(id: u8) -> bool {
    MOVED.iter().any(|m| m.1 == id) || HIDDEN.contains(&id)
}

/// Whether this table should be in use: the pack's features (`on`), Versus or the War Room, not Survival, not a
/// game continued from a save made on AW2's table.
fn wanted(core: &Core, on: bool) -> bool {
    let mode = core.raw_read_8(TITLE_MODE, -1);
    on && (VERSUS.contains(&mode) || WAR_ROOM.contains(&mode)) && !crate::survival::on(core) && core.raw_read_8(TABLE_FLAG, -1) != FORCED_AW2
}

/// Every frame, from [`crate::survival::tick_tables`] (`on`: the pack's features, Survival's table installed):
/// this table when [`wanted`] (true returned), else Survival's.
pub fn tick_tables(core: &mut Core, on: bool) -> bool {
    if !wanted(core, on) || !install(core) {
        return false;
    }
    crate::five_map::use_table(core, TABLE);
    true
}

/// `BuildMapListForMode` (a map list being built, Versus' or the War Room's): a new game, so a continued game's
/// table is over; the list is built from this table when it is wanted.
pub const BUILD_LIST: u32 = 0x0803_75A4;
fn build_list(core: &mut Core) {
    // (a list opened afresh: no map marked yet)
    if core.raw_read_8(MARK, -1) != 0 {
        core.raw_write_8(MARK, -1, 0);
    }
    if core.raw_read_8(TABLE_FLAG, -1) != 0 {
        core.raw_write_8(TABLE_FLAG, -1, 0);
        // (Survival's table in use: the pack's features are on)
        let on = crate::five_map::table(core) == crate::survival::TABLE;
        if wanted(core, on) && install(core) {
            crate::five_map::use_table(core, TABLE);
        }
    }
}

/// A game saved halfway being continued (crate::suspend, its block loaded, before the map is): `ds_table`, the
/// save says it was played on this table. Saved on AW2's, it goes on on AW2's.
pub fn continued(core: &mut Core, ds_table: bool) {
    let want = if ds_table { 0 } else { FORCED_AW2 };
    if core.raw_read_8(TABLE_FLAG, -1) != want {
        core.raw_write_8(TABLE_FLAG, -1, want);
    }
    // The table now, before the map loads (the frame's tick would be too late): with the pack's features on
    // (Survival's table or this one in use).
    let on = in_use(core) || crate::five_map::table(core) == crate::survival::TABLE;
    if wanted(core, on) && install(core) {
        crate::five_map::use_table(core, TABLE);
    } else if in_use(core) {
        crate::five_map::use_table(core, crate::survival::TABLE);
    }
}

/// At every map start (crate::sandstorm's trap, after crate::wasteland's): a map of this table brings its look,
/// its weather (when it has one: fixed, over the Rules') and its fog (when it has fog).
pub fn map_start(core: &mut Core) {
    let id = core.raw_read_8(MAP_ID, -1);
    if id == BATTLE_ID && two_fronts(core).is_some() {
        return two_front_start(core);
    }
    let Some(e) = map_of(core, id) else { return };
    start_rules(core, e);
}

fn start_rules(core: &mut Core, e: &Entry) {
    crate::wasteland::set_ds_look(core, e.look);
    if e.weather != 0 {
        // 1 snow, 2 rain as AW2's fixed weather; 3 the sandstorm: fixed clear (crate::sandstorm).
        let w = if e.weather == 3 { 0 } else { e.weather };
        core.raw_write_8(WEATHER_MODE, -1, 3);
        core.raw_write_8(DEFAULT_WEATHER, -1, w);
        core.raw_write_8(WEATHER, -1, w);
        core.raw_write_8(NEXT_WEATHER, -1, w);
    }
    if e.fog {
        core.raw_write_8(FOG, -1, 1);
    }
}

/// `TryShowScriptedCoPowerQuote`: AW2's campaign quotes by `id - 0x8A` are no War Room map's here.
const POWER_QUOTE: u32 = 0x0803_9850;
fn power_quote(core: &mut Core) {
    if in_use(core) && core.raw_read_8(MAP_ID, -1) as u16 >= LAST_VERSUS {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(0, 0);
        let lr = cpu.gpr(14) as u32;
        cpu.set_thumb_pc(lr & !1);
    }
}

/// `DrawMapList`, past its `ClearBg0Tilemap` (every row is drawn again): the names' text tiles come from a cache
/// that only grows while the list is up (`ResetTextTileCache`, `gUnknown_03002B80`: +0 a "start over" flag,
/// +0x358 the next tile), with room for about 35 names; Dual Strike's tabs have up to 44, and the names past that
/// were drawn over the preview's tiles. Every row being drawn again here, the cache starts over (at the tile the
/// list's screen starts it at, `InitTextTileCache(0)`).
const LIST_DRAWN: u32 = 0x0808_6A6E;
const TEXT_CACHE: u32 = 0x0300_2B80;
const TEXT_CACHE_NEXT: u32 = TEXT_CACHE + 0x358;
const LIST_TEXT_FIRST: u16 = 0x29;
/// The tile the preview's start (the text tiles must stay below it), and the tiles the rows of one draw can need (9 names).
const LIST_TEXT_END: u16 = 0x1E1;
const LIST_TEXT_ROOM: u16 = 9 * 14;
fn list_drawn(core: &mut Core) {
    // (every Versus list: the lists by player count have up to 76 names, a tab of the game's own has 24 at most)
    if !(in_use(core) || crate::pvp::in_versus(core)) {
        return;
    }
    if in_use(core) {
        // (first, count, top: in sl, r7 and sb by now, for [`REDRAW`])
        let cpu = core.gba().cpu();
        let args = [cpu.gpr(10) as u8, cpu.gpr(7) as u8, cpu.gpr(9) as u8];
        core.raw_write_range(LIST_ARGS, -1, &args);
    }
    // The cache hands out tiles to the names it has not seen, from LIST_TEXT_FIRST up to the preview's tiles
    // (LIST_TEXT_END). It starts over only when the rows about to be drawn would not fit: the rows still on screen
    // while the list scrolls then keep their tiles (starting over at every redraw garbled them for a frame or two).
    if core.raw_read_16(TEXT_CACHE_NEXT, -1) + LIST_TEXT_ROOM > LIST_TEXT_END {
        core.raw_write_16(TEXT_CACHE_NEXT, -1, LIST_TEXT_FIRST);
        core.raw_write_8(TEXT_CACHE, -1, 1);
    }
}

// --- Two fronts ------------------------------------------------------------------------

/// The Select Mode list's proc, its idle callback (an empty function) and `DrawMapList`; the list's rows: the
/// ids, the highlighted row and each tab's first row shown.
const SELECT_MAP: u32 = 0x0861_6C54;
const SELECT_MAP_IDLE: u32 = 0x0808_5F90;
const DRAW_MAP_LIST: u32 = 0x0808_6A58;
const PROC_POOL: (u32, u32) = (0x0200_D610, 0x0200_E418);
const LIST_IDS: u32 = crate::five_map::LIST_IDS;
const LIST_LAST: u32 = crate::five_map::LIST_LAST;
const LIST_ROW: u32 = 0x0300_5980;
const LIST_TOP: u32 = 0x0300_5990;
const LIST_TAB: u32 = 0x0300_596C;
const KEY_SELECT: u32 = 1 << 2;

fn list_up(core: &Core) -> bool {
    (PROC_POOL.0..PROC_POOL.1).step_by(0x6C).any(|p| core.raw_read_32(p, -1) == SELECT_MAP && core.raw_read_32(p + 0x10, -1) == SELECT_MAP_IDLE | 1)
}

/// The map the Versus list's cursor is on.
fn highlighted(core: &Core) -> Option<u8> {
    let k = core.raw_read_8(LIST_ROW, -1) as u32 + core.raw_read_8(LIST_TOP + core.raw_read_8(LIST_TAB, -1) as u32, -1) as u32;
    (k <= core.raw_read_8(LIST_LAST, -1) as u32).then(|| core.raw_read_8(LIST_IDS + k, -1))
}

/// A map that can be either front of a two-map Versus battle: Dual Strike's 2P Versus maps.
fn two_player(id: u8) -> bool {
    built().is_some_and(|b| b.names.iter().any(|n| n.0 == id))
}

/// SELECT is the second-front mark here: the Dual Strike pack's list is up and the cursor is on a 2P map of it
/// (crate::online_maps keeps SELECT for its lists otherwise).
pub fn wants_select(core: &Core) -> bool {
    in_use(core) && list_up(core) && highlighted(core).is_some_and(two_player)
}

/// Every frame before the game (crate::pvp, `ds`: the pack's features; `allowed`: offline): on Versus' list,
/// SELECT marks the 2P map under the cursor as the second front (or takes the mark back), and the list is drawn
/// again. Returns the keys the game sees.
pub fn keys(core: &mut Core, ds: bool, allowed: bool, keys: u32, prev: u32) -> u32 {
    if core.raw_read_8(TWO_ALLOWED, -1) != allowed as u8 {
        core.raw_write_8(TWO_ALLOWED, -1, allowed as u8);
    }
    let versus = VERSUS.contains(&core.raw_read_8(TITLE_MODE, -1));
    if !ds || !allowed || !versus || !in_use(core) || !list_up(core) {
        return keys;
    }
    if keys & !prev & KEY_SELECT != 0 {
        if let Some(id) = highlighted(core).filter(|&id| two_player(id)) {
            let now = core.raw_read_8(MARK, -1);
            core.raw_write_8(MARK, -1, if now == id { 0 } else { id });
            core.raw_write_8(REDRAW, -1, 1);
            names(core);
        }
    }
    keys & !KEY_SELECT
}

/// The list's idle callback (`bx lr`): drawn again when asked, with `DrawMapList`'s last arguments (tail-called:
/// it returns to the proc runner).
fn list_idle(core: &mut Core) {
    if core.raw_read_8(REDRAW, -1) == 0 {
        return;
    }
    core.raw_write_8(REDRAW, -1, 0);
    let args = [core.raw_read_8(LIST_ARGS, -1), core.raw_read_8(LIST_ARGS + 1, -1), core.raw_read_8(LIST_ARGS + 2, -1)];
    if args[1] == 0 || !in_use(core) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, args[0] as i32);
    cpu.set_gpr(1, args[1] as i32);
    cpu.set_gpr(2, args[2] as i32);
    cpu.set_thumb_pc(DRAW_MAP_LIST);
}

/// `SetMapId` (`sub_0803BCD0`, at its store; r0 the map picked): a two-front battle is set up and played on
/// [`BATTLE_ID`] (the War Room's two-front maps; in Versus, a 2P map picked with another 2P map marked), any
/// other map clears it.
const SET_MAP_ID: u32 = 0x0803_BCD2;
fn set_map_id(core: &mut Core) {
    let id = core.gba().cpu().gpr(0) as u8;
    if id == BATTLE_ID {
        return;
    }
    let mode = core.raw_read_8(TITLE_MODE, -1);
    let mark = core.raw_read_8(MARK, -1);
    let pair = built().and_then(|b| b.entries.iter().filter(|e| e.second.is_some()).position(|e| e.id == id));
    let fronts = if !in_use(core) {
        None
    } else if WAR_ROOM.contains(&mode) && pair.is_some() {
        Some((FRONTS_WAR_ROOM, pair.unwrap_or(0) as u8))
    } else if VERSUS.contains(&mode) && core.raw_read_8(TWO_ALLOWED, -1) == 1 && mark != 0 && mark != id && two_player(id) && two_player(mark) {
        Some((FRONTS_VERSUS, mark))
    } else {
        None
    };
    core.raw_write_8(MARK, -1, 0);
    match fronts {
        Some((kind, second)) => {
            core.raw_write_8(FRONTS, -1, kind);
            core.raw_write_8(MAIN_ID, -1, id);
            core.raw_write_8(SECOND_ID, -1, second);
            write_entry(core, 0);
            core.gba_mut().cpu_mut().set_gpr(0, BATTLE_ID as i32);
        }
        None => {
            if core.raw_read_8(FRONTS, -1) != 0 {
                core.raw_write_8(FRONTS, -1, 0);
            }
        }
    }
}

/// The main front's description (the CO screen's picks: army 1's CO; the description's index 0, as
/// [`front_header`] takes it).
fn main_front() -> &'static crate::campaign_model::MissionInfo {
    static MAIN: OnceLock<crate::campaign_model::MissionInfo> = OnceLock::new();
    MAIN.get_or_init(|| crate::campaign_model::MissionInfo {
        index: 0,
        name: String::new(),
        info_text: 0,
        two_front: None,
        number: 0,
        cos: [(0x1C, 0x1C), (0, 0), (0, 0), (0, 0)],
        colours: [1, 2, 3, 4],
        teams: [1, 2, 3, 4],
        armies: 2,
        pool: Vec::new(),
        day_limit: 0,
        width: 0,
        height: 0,
        look: 0,
        weather: 0,
        fog: false,
        labs: Vec::new(),
        realtime: 0,
        unit_event_list: 0,
        native: None,
    })
}

/// Versus' two fronts (Dual Strike's): each army plays its own turns on both and picks its second front's CO
/// (Teams' partner), the main front sends units on the ground.
fn versus_fronts() -> &'static crate::campaign_model::TwoFront {
    use crate::campaign_model::{FrontControl, SendRule, TwoFront, PICK};
    static V: OnceLock<TwoFront> = OnceLock::new();
    V.get_or_init(|| TwoFront {
        second: 1,
        cos: [PICK, PICK, 0, 0],
        control: [FrontControl::Owner; 4],
        send: SendRule::Ground,
        powers: true,
        sky: false,
        posture: false,
    })
}

/// The War Room's five pairs: the computer directs the player's second front (records strip 0) and the enemy's
/// (its back CO leads it), the player picks the second front's CO and its posture (Intel > General).
fn war_room_fronts() -> &'static [crate::campaign_model::TwoFront] {
    use crate::campaign_model::{FrontControl, SendRule, TwoFront, PICK};
    static W: OnceLock<Vec<TwoFront>> = OnceLock::new();
    W.get_or_init(|| {
        built()
            .map(|b| {
                b.entries
                    .iter()
                    .filter(|e| e.second.is_some())
                    .map(|e| TwoFront {
                        second: 1,
                        cos: [PICK, e.cos[1].1.or(e.cos[1].0).unwrap_or(1), 0, 0],
                        control: [FrontControl::Cpu; 4],
                        send: SendRule::Ground,
                        powers: true,
                        sky: false,
                        posture: true,
                    })
                    .collect()
            })
            .unwrap_or_default()
    })
}

/// The two-front battle being played or set up (on [`BATTLE_ID`]): its main front and description
/// (crate::two_front's gate).
pub fn two_fronts(core: &Core) -> Option<(&'static crate::campaign_model::MissionInfo, &'static crate::campaign_model::TwoFront)> {
    if core.raw_read_8(MAP_ID, -1) != BATTLE_ID || !in_use(core) {
        return None;
    }
    match core.raw_read_8(FRONTS, -1) {
        FRONTS_VERSUS => Some((main_front(), versus_fronts())),
        FRONTS_WAR_ROOM => war_room_fronts().get(core.raw_read_8(SECOND_ID, -1) as usize).map(|f| (main_front(), f)),
        _ => None,
    }
}

/// A front's map: 0 the main front, 1 the second (its header's address, and what is needed of it).
fn front(core: &Core, index: u8) -> Option<(u32, &'static Entry)> {
    let b = built()?;
    let main = core.raw_read_8(MAIN_ID, -1);
    let second = core.raw_read_8(SECOND_ID, -1);
    let e = b.entries.iter().find(|e| e.id == main)?;
    match (index, core.raw_read_8(FRONTS, -1)) {
        (0, _) => Some((TABLE + ENTRY * main as u32, e)),
        (_, FRONTS_VERSUS) => Some((TABLE + ENTRY * second as u32, b.entries.iter().find(|e| e.id == second)?)),
        (_, FRONTS_WAR_ROOM) => {
            let (_, at) = e.second?;
            Some((at, b.seconds.get(second as usize)?))
        }
        _ => None,
    }
}

/// A front's header (crate::two_front).
pub fn front_header(core: &Core, index: u8) -> Option<[u8; 0x5C]> {
    let (at, _) = front(core, index)?;
    let mut h = [0u8; 0x5C];
    core.raw_read_range(at, -1, &mut h);
    Some(h)
}

/// The entry the battle is played on (crate::two_front writes the live front's header there).
pub fn two_front_entry(core: &Core) -> Option<u32> {
    in_use(core).then_some(TABLE + ENTRY * BATTLE_ID as u32)
}

/// [`BATTLE_ID`]'s entry: front `index`'s header.
fn write_entry(core: &mut Core, index: u8) {
    let Some(h) = front_header(core, index) else { return };
    let at = TABLE + ENTRY * BATTLE_ID as u32;
    let mut now = [0u8; 0x5C];
    core.raw_read_range(at, -1, &mut now);
    if now != h {
        core.raw_write_range(at, -1, &h);
    }
}

/// A front's look, as it comes on the screen (crate::two_front's swap).
pub fn front_look(core: &mut Core, index: u8) {
    if let Some((_, e)) = front(core, index) {
        crate::wasteland::set_ds_look(core, e.look);
    }
}

/// The front starting now on [`BATTLE_ID`] (the main front at the battle's start; the second front at its first
/// round, which a swap starts as a battle): its look, weather and fog; at the start the second front's COs
/// (Versus: each army's partner from the Teams screen, else its CO), and crate::two_front's own start.
fn two_front_start(core: &mut Core) {
    let live = crate::two_front::live(core).unwrap_or(0);
    if let Some((_, e)) = front(core, live) {
        start_rules(core, e);
    }
    if live == 0 && core.raw_read_8(FRONTS, -1) == FRONTS_VERSUS {
        let mut cos = [0xFFu8; 4];
        for (k, c) in cos.iter_mut().enumerate().take(2) {
            let main = core.raw_read_8(PLAY_ST + 0x3E + k as u32, -1);
            let partner = core.raw_read_8(crate::tag::TEAMS_PARTNER + k as u32, -1);
            *c = if partner == 0xFF { main } else { partner };
        }
        crate::two_front::set_second_cos(core, cos);
    }
    crate::two_front::map_start(core);
}

// --- The War Room's records ------------------------------------------------------------

/// The War Room on this table.
pub fn war_room(core: &Core) -> bool {
    in_use(core) && WAR_ROOM.contains(&core.raw_read_8(TITLE_MODE, -1))
}

/// The record table the War Room's code should read now (crate::survival's tick, Survival not open).
pub fn record_rows(core: &Core) -> u32 {
    if war_room(core) {
        ROWS.wrapping_sub(ROW * (FIRST_WAR_ROOM as u32 - 0x6C))
    } else {
        RECORDS
    }
}

/// The War Room's maps in record order (the order of the rows in Flash).
fn war_room_ids() -> impl Iterator<Item = u8> {
    (FIRST_WAR_ROOM..=0xB3).map(|i| i as u8).chain(MOVED.iter().map(|m| m.1))
}

fn row_at(id: u8) -> u32 {
    ROWS + ROW * (id as u32 - FIRST_WAR_ROOM as u32)
}

/// The mark after the records in slot 15's payload (they end it).
const RECORDS_MARK: u32 = 0x5257_5344; // "DSWR"
pub const RECORDS_TAIL_LEN: usize = WAR_ROOM_MAPS * ROW as usize + 4;

/// AW2's Flash: sectors of 0x1000; "2ars" at +0, generation +8, part +0x0C, slot +0x0D, length +0x50, payload
/// +0x52.
const FLASH: u32 = 0x0E00_0000;
const SECTOR_MAGIC: u32 = 0x7372_6132;

/// The records saved in the DS Campaign's slot (the newest copy), if any.
fn saved_tail(core: &Core) -> Option<Vec<u8>> {
    let mut best: Option<(u32, u32)> = None;
    for sector in 0..16 {
        let at = FLASH + 0x1000 * sector;
        if core.raw_read_32(at, -1) != SECTOR_MAGIC
            || core.raw_read_8(at + 0x0D, -1) != crate::ds_campaign::SAVE_SLOT
            || core.raw_read_8(at + 0x0C, -1) >> 4 != 0
        {
            continue;
        }
        let generation = core.raw_read_32(at + 8, -1);
        if best.is_none_or(|(g, _)| generation >= g) {
            best = Some((generation, at));
        }
    }
    let (_, at) = best?;
    let len = core.raw_read_16(at + 0x50, -1) as usize;
    if len < RECORDS_TAIL_LEN || len > 0xFAD {
        return None;
    }
    let mut b = vec![0u8; RECORDS_TAIL_LEN];
    core.raw_read_range(at + 0x52 + (len - RECORDS_TAIL_LEN) as u32, -1, &mut b);
    (u32::from_le_bytes(b[RECORDS_TAIL_LEN - 4..].try_into().unwrap()) == RECORDS_MARK).then_some(b)
}

/// The rows from Flash into [`ROWS`] (none saved: empty rows).
fn load_rows(core: &mut Core) {
    core.raw_write_range(ROWS, -1, &vec![0u8; ROWS_LEN as usize]);
    if let Some(t) = saved_tail(core) {
        for (k, id) in war_room_ids().enumerate() {
            core.raw_write_range(row_at(id), -1, &t[k * ROW as usize..(k + 1) * ROW as usize]);
        }
    }
    core.raw_write_8(ROWS_STATE, -1, LOADED);
}

/// The records to save at the end of slot 15's payload (crate::ds_campaign::stage_slot): the War Room's rows in
/// RAM while they are loaded, else the saved ones (none saved: nothing).
pub fn records_tail(core: &Core) -> Vec<u8> {
    if core.raw_read_8(ROWS_STATE, -1) & LOADED != 0 {
        let mut t = Vec::with_capacity(RECORDS_TAIL_LEN);
        for id in war_room_ids() {
            let mut row = [0u8; ROW as usize];
            core.raw_read_range(row_at(id), -1, &mut row);
            t.extend_from_slice(&row);
        }
        t.extend_from_slice(&RECORDS_MARK.to_le_bytes());
        t
    } else {
        saved_tail(core).unwrap_or_default()
    }
}

/// The names on Versus' list: the marked map's with its mark.
fn names(core: &mut Core) {
    if let Some(b) = built().filter(|_| installed(core)) {
        let mark = core.raw_read_8(MARK, -1);
        for &(id, word, name, marked, _) in &b.names {
            let want = if id == mark { marked } else { name };
            if core.raw_read_32(word, -1) != want {
                core.raw_write_32(word, -1, want);
            }
        }
    }
}

/// Every frame (crate::pvp, after the tables): the records are in RAM on the War Room's screens and given up
/// elsewhere (the rows' bytes are time-shared).
pub fn tick(core: &mut Core) {
    names(core);
    // A two-front battle being set up: its entry is the main front's (crate::two_front keeps the live front's
    // there during the battle).
    if core.raw_read_8(FRONTS, -1) != 0 && crate::two_front::on(core).is_none() && in_use(core) {
        write_entry(core, 0);
    }
    let s = core.raw_read_8(ROWS_STATE, -1);
    // (a record just made at a two-front battle's end stays: no swap writes the store after the battle)
    let keep = war_room(core) && (crate::two_front::on(core).is_none() || s & DIRTY != 0);
    if !keep {
        if s != 0 {
            core.raw_write_8(ROWS_STATE, -1, 0);
        }
    } else if s & LOADED == 0 {
        load_rows(core);
    }
}

/// `InsertBestScoreRecord`'s War Room branch (`subs r4, #0x6c`): the rows loaded (a two-front battle borrowed
/// their bytes) and marked to be saved.
const INSERT: u32 = 0x0801_774A;
fn insert(core: &mut Core) {
    if !war_room(core) {
        return;
    }
    // A two-front map's record is its main map's.
    if core.raw_read_8(MAP_ID, -1) == BATTLE_ID && core.raw_read_8(FRONTS, -1) == FRONTS_WAR_ROOM {
        let main = core.raw_read_8(MAIN_ID, -1);
        core.gba_mut().cpu_mut().set_gpr(4, main as i32);
    }
    if core.raw_read_8(ROWS_STATE, -1) & LOADED == 0 {
        load_rows(core);
    }
    let s = core.raw_read_8(ROWS_STATE, -1);
    core.raw_write_8(ROWS_STATE, -1, s | DIRTY);
}

/// A War Room record on Dual Strike's maps not yet saved (crate::co_skills writes slot 15 after the profile).
pub fn records_dirty(core: &Core) -> bool {
    war_room(core) && core.raw_read_8(ROWS_STATE, -1) == LOADED | DIRTY
}

/// Slot 15 is being written with [`records_tail`].
pub fn records_written(core: &mut Core) {
    let s = core.raw_read_8(ROWS_STATE, -1);
    if s & DIRTY != 0 {
        core.raw_write_8(ROWS_STATE, -1, s & !DIRTY);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (BUILD_LIST, Box::new(build_list)),
        (LIST_DRAWN, Box::new(list_drawn)),
        (SELECT_MAP_IDLE, Box::new(list_idle)),
        (SET_MAP_ID, Box::new(set_map_id)),
        (POWER_QUOTE, Box::new(power_quote)),
        (INSERT, Box::new(insert)),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout() {
        assert!(TABLE + ENTRY * 0x100 <= SECOND_HEADERS && SECOND_HEADERS + ENTRY * 5 <= SENTINEL);
        // (the names, then the marked names of the 2P Versus maps)
        assert!(STRINGS + STRING_SIZE * (TEXT_IDS as u32 + 0x8A) <= MAP_DATA);
        assert!(MAP_DATA + MAP_DATA_SIZE * (0xB6 + 5) <= ROM_END);
        // Text ids: past Survival's (0x7172..), before the tag pairs' (0x7300..).
        assert!(TEXT_BASE > crate::survival::TEXT_BASE + 0x40 && TEXT_BASE + TEXT_IDS <= crate::tag::TEXT_TAG);
        assert_eq!(war_room_ids().count(), WAR_ROOM_MAPS);
        assert!(war_room_ids().all(|id| row_at(id) + ROW <= ROWS + ROWS_LEN));
        // Every moved id is one of tangoAW2's Dual Strike-style maps, never a 5-army one.
        for id in MOVED.iter().map(|m| m.1).chain(HIDDEN) {
            assert!(crate::five_map::is_ds_map(id) && !crate::five_map::is_five_map(id));
        }
        assert!(RECORDS_TAIL_LEN + 0x20 + crate::ds_campaign::RECORDS_SIZE as usize + crate::co_skills::DATA_LEN as usize <= 0xFAD);
    }

    /// With a Dual Strike ROM (TANGOAW2_DS_ROM): Dual Strike's ids, tabs, the War Room's two-front battles.
    #[test]
    fn table_from_the_rom() {
        let Some(path) = std::env::var_os("TANGOAW2_DS_ROM") else { return };
        let Ok(buf) = std::fs::read(path) else { return };
        crate::ds_art::offer(&buf);
        let b = built().expect("table");
        assert_eq!(b.entries.len(), 0xB6);
        let tab = |c| b.entries.iter().filter(|e| e.case == c).count();
        assert_eq!([tab(2), tab(3), tab(4), tab(5), tab(6), tab(7)], [17, 27, 31, 27, 36, 44]);
        assert_eq!(b.seconds.len(), 5);
        let e = |id: u8| b.entries.iter().find(|e| e.id == id).unwrap();
        assert_eq!(e(0x01).name, "Bean Island");
        assert_eq!(e(0x8B).name, "Spann Island");
        assert_eq!((e(0xC1).name.as_str(), e(0xC1).second.map(|s| s.0)), ("Silo Nation", Some(0xB9)));
        assert_eq!(e(0xC3).name, "Helix Peninsula");
        assert_eq!(e(0xB2).second.map(|s| s.0), Some(0xB7));
        assert_eq!(b.entries.iter().filter(|e| e.second.is_some()).count(), 5);
        // The same bytes every time (netplay: both consoles build it).
        let again = build().unwrap();
        assert_eq!(again.writes, b.writes);
    }
}

#[cfg(test)]
mod rom_range_tests {
    #[test]
    fn the_maps_start_where_the_songs_must_end() {
        assert_eq!(crate::ds_music::STORY_END, super::TABLE);
        assert!(super::ROM_END <= 0x09E0_0000);
    }
}
